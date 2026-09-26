---
date: 2026-05-23
domain: operations
client_case: NB-automations hardening loop W44 — wr2_supervisor heartbeat task died silently, frozen 16h57m, restart restored
sources: 6
---

# W44 — `_heartbeat_loop` task died silently in supervisor, frozen 16h57m

## Summary

Investigated W43's reported "WR2 pipeline frozen 5h" finding. **Pipeline was NOT actually frozen** — `wr2_supervisor` daemon was running and processing draft state transitions normally. The issue was **`wr2_supervisor_heartbeat` table stopped receiving rows** at 2026-05-22 20:13:24 UTC = 04:13 WITA. Watchdog correctly reported "supervisor_down" based on stale heartbeat. Restart (kickstart -k) at 2026-05-23 02:40 UTC restored heartbeat writes within 1s.

## Diagnosis (W44 root cause)

**The heartbeat task died silently while the main supervisor process kept running.**

Pre-restart state:
- `ps -p 25650`: process alive, elapsed 16:57:24, started 2026-05-22 17:42
- `~/logs/wr2_supervisor.launchd.err.log`: continuous activity through 2026-05-23 02:38:52 UTC (reconnect loops, LISTEN active, heartbeat conn open reported)
- `wr2_supervisor_heartbeat` table: last row 2026-05-22 20:13:24 UTC = 16h27m before restart

**Critical finding**: at 2026-05-22 21:48:37 UTC the supervisor reconnected after a connection loss and logged "heartbeat conn open" + called `_write_heartbeat(conn_hb, "startup")`. **That "startup" row never landed in the DB.** Subsequent ticks also missing. So the post-reconnect heartbeat writes were silently swallowed.

Code path analysis (`scripts/wr2_supervisor.py:459-535`):

```python
async def _write_heartbeat(conn_hb, note):
    _write_organism_heartbeat("wr2.supervisor", "ok", note)  # file write
    try:
        await conn_hb.execute("INSERT INTO ... VALUES ($1)", note[:200])
    except asyncpg.UndefinedTableError:
        logger.debug(...)
    except (asyncpg.PostgresError, asyncpg.InterfaceError, OSError, asyncio.TimeoutError) as e:
        logger.warning("heartbeat write failed: %s", e)
        # ← swallows error, _heartbeat_loop continues with dead conn_hb
```

```python
async def _heartbeat_loop(conn_hb):
    await _write_heartbeat(conn_hb, "tick")
    while not _shutdown_event.is_set():
        await asyncio.sleep(HEARTBEAT_INTERVAL_SEC)
        await _write_heartbeat(conn_hb, "tick")
        # ← if conn_hb is dead, _write_heartbeat will silently fail every cycle
```

`_heartbeat_loop` is dispatched via `asyncio.create_task(_heartbeat_loop(conn_hb))` at line 644. **If the task itself raises an unhandled exception** (e.g. an exception class NOT in the catch tuple — `RuntimeError`, `AttributeError`, etc.), `asyncio.create_task` returns immediately and the exception sits in the task object until garbage collected. **No `add_done_callback` handler is registered to log it.** The main `_run_loop` never awaits the task except in finally-cleanup. So a task exception = silent death.

Compounding: even when the LISTEN conn drops + reconnects (which DOES tear down conn_hb in the finally block at line 679 and re-spawns the task), the NEW conn_hb is also subject to the same silent-death mode if any unexpected exception class fires.

The proximate cause of the original 20:13:24 death is not in logs (no traceback). Most likely candidates:
1. asyncpg version-specific exception not in the catch tuple
2. Network blip raising `ConnectionResetError` (a subclass of `OSError` — should be caught, but worth checking subprocess instrumentation)
3. Race condition during reconcile_task vs heartbeat_task contention (despite the comment about dedicated conn — possibly a shared state issue elsewhere)
4. Backpressure: `_write_organism_heartbeat` writes to filesystem; if `~/.organism/last_seen/` disk fills, the function silently passes (line 515 `except Exception: pass`) but the task may have raised before reaching the DB INSERT

## Immediate fix (shipped — restart)

```bash
launchctl kickstart -k gui/$(id -u)/com.balizero.wr2.supervisor
# new pid 71991
```

Verification (60s post-restart):
```sql
SELECT written_at, note FROM wr2_supervisor_heartbeat ORDER BY written_at DESC LIMIT 3;
-- 2026-05-23T02:40:00.277Z | tick
-- 2026-05-23T02:40:00.193Z | startup
-- 2026-05-22T20:13:24.593Z | tick   (the death row, 6h27m gap)
```

Heartbeat restored. Watchdog will see fresh row on next 60s probe + reset its internal "alert active" cooldown state when probe returns OK age < 300s.

## Permanent fix (DEFERRED — needs patch + careful test)

Three layers needed:

### Layer 1 — surface task exceptions
`heartbeat_task = asyncio.create_task(_heartbeat_loop(conn_hb))` at line 644 should gain a done callback:

```python
def _on_heartbeat_task_done(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error("heartbeat_task DIED with exception: %s", exc, exc_info=exc)
        # Trigger outer reconnect via shutdown_event if available, OR
        # set a flag that the next 5s keepalive will check.

heartbeat_task = asyncio.create_task(_heartbeat_loop(conn_hb))
heartbeat_task.add_done_callback(_on_heartbeat_task_done)
```

Mirror for `reconcile_task`.

### Layer 2 — broaden exception catch in `_write_heartbeat`
Convert the narrow tuple to `except Exception as e` + re-raise after logging if the exception is unexpected. Logging on its own is fine for transient errors; re-raising forces `_heartbeat_loop` to exit → done callback fires → outer reconnect.

```python
except Exception as e:  # was: 4-tuple
    logger.exception("heartbeat write failed (unexpected): %s", e)
    # Re-raise so the task exits and the outer loop reconnects.
    raise
```

### Layer 3 — independent heartbeat liveness probe
The outer `_run_loop` already does `SELECT 1` every 5s on `conn`. Should ALSO probe `conn_hb` liveness with a `SELECT 1` every 5s — that way, if `conn_hb` silently fails (TCP half-close, Fly proxy stale), the outer loop notices within seconds and triggers reconnect.

### Why deferred

- Sibling agent active on this same file 30min ago (4 session-stop stashes during W43). Need to verify race is clear before patching.
- Layer 2 + 3 change exception handling — needs unit tests + integration smoke. Not safe to ship without test coverage.
- W43 (tiered escalation watchdog) is the COMPLEMENTARY fix on the other side. Both needed for proper observability + fast recovery.

## What W44 still leaves open

- **Why did `_heartbeat_loop` die at 20:13?** No traceback in stderr. Possible: macOS launchd EX_IOERR (last exit code = 74) is from a PRIOR restart, not the current process. The supervisor itself never crashed — it just had the heartbeat task die quietly. To diagnose: enable `asyncio.create_task(..., name="heartbeat_loop")` + `asyncio.get_running_loop().set_exception_handler(...)` to capture unhandled exceptions globally.
- **W42's WR2 supervisor exit code 74 EX_IOERR**: that was from the PREVIOUS launchctl session ending. Current pid 25650 had no exit yet (now restarted as 71991).
- **`_replay_outbox` at line 626**: ran on every reconnect for 16h. Was it accidentally re-firing duplicate events? Worth auditing `events_outbox` for `consumed_at` patterns.

## Bonus: makes W43 (tiered escalation) more important

Even with W44's heartbeat fix, the W43 watchdog still uses flat 24h cooldown. If a NEW class of silent death happens, operator gets ONE alert + 24h silence. W43's tier escalation would have re-pinged Antonello at 2h, 4h, 8h — providing 4 chances to notice instead of 1. **W43 + W44 are complementary, not competing.**

## Sources

1. `scripts/wr2_supervisor.py:459-535` — `_write_heartbeat` + `_heartbeat_loop`
2. `scripts/wr2_supervisor.py:644` — `asyncio.create_task(_heartbeat_loop)` without done callback
3. `scripts/wr2_supervisor.py:660-666` — outer reconnect exception tuple
4. `wr2_supervisor_heartbeat` table state pre/post restart (Postgres MCP queries)
5. `~/logs/wr2_supervisor.launchd.err.log` — continuous activity 17:42 → 02:38 UTC with no death traceback
6. `ps -p 25650` — process elapsed 16:57:24 confirms process never crashed, only heartbeat task did

## Next

- [ ] W45 candidate: implement Layer 1+2+3 permanent fix when sibling race subsides
- [ ] W46 candidate: audit `events_outbox` for duplicate-replay artifacts during the 16h window (outbox replay fired every reconnect)
- [ ] W43 still pending: tiered escalation watchdog (complementary to W44 fix)
