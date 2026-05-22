---
date: 2026-05-23
domain: operations
client_case: NB automations hardening — W29 watchdog asyncpg fix + live W27 production test during real outage
sources: 6
---

# W29 + W30: watchdog asyncpg fix + live W27 empirical test during real outage

## W29 — watchdog asyncpg.InterfaceError fix

### Trauma

`wr2_supervisor_watchdog` emitting 1 `asyncpg.InterfaceError: connection is closed` error per minute since 04:40 WITA. Watchdog kept running but `_probe_heartbeat_age` failed silently on stale connection.

### Root cause

`scripts/wr2_supervisor_watchdog.py:399` inner `except (asyncpg.PostgresError, OSError, asyncio.TimeoutError)` did NOT include `asyncpg.InterfaceError` (sibling class in asyncpg hierarchy, NOT subclass of PostgresError). When pg-proxy briefly hiccups, connection becomes InterfaceError → falls through to `except Exception` which only logs (`logger.exception`) but does NOT raise → outer reconnect loop never fires → closed conn stays in use → burn.

### Fix shipped (commit `e60b6bf77`)

Added `asyncpg.InterfaceError` to both inner (re-raise) and outer (reconnect) except tuples:

```python
except (
    asyncpg.PostgresError,
    asyncpg.InterfaceError,  # W29: stale connection after pg-proxy hiccup
    OSError,
    asyncio.TimeoutError,
):
    raise  # let outer reconnect handle it
```

### Empirical verification

Post-kickstart at 04:51 WITA, 4 min monitoring:

- 15 log lines, **ALL INFO** ✅
- 0 Tracebacks ✅
- 0 asyncpg exceptions ✅
- Watchdog correctly emits INFO "supervisor_down stale but cooldown active" (real WR2 supervisor health alarm, separate concern)

## W30 — wr2_supervisor heartbeat 42min stale

### Discovery

W29 cleanup unmasked: watchdog correctly throttling repeated `supervisor_down` alerts (heartbeat age=2524s = ~42min) via 24h cooldown.

### Diagnosis

wr2_supervisor process running (PID 25650, ~12h elapsed) but unable to write heartbeats. Backend api machine `7847d95ce257d8` showed `1 total, 1 critical` checks. Curl `https://nuzantara-rag.fly.dev/health` timed out 30s.

**Root cause:** downstream effect of backend api machine being unhealthy. wr2_supervisor writes heartbeat to PG via DATABASE_URL_LOCAL → pg-proxy → Fly api machine. If api machine is unhealthy, pg-proxy connections die, supervisor can't persist heartbeat.

### Action

Manually invoked `fly machine restart 7847d95ce257d8 -a nuzantara-rag` to recover from outage. Closes W30 (not a supervisor bug — supervisor was correctly trying but blocked by backend down).

## W27 live production test 🎯

### Setup

During the W30 outage (backend api machine unreachable), Cell daemon happened to be running the W27 Path A patched pulse.py (after I restarted it at 05:00 WITA to pick up new emit logic). Cell entered sustained-red state.

### Empirical sequence (verbatim from logs)

```
Cell restart      05:00:23  Pulse #1  Health: red → read_logs
                  05:01:37  Pulse #2  Health: red → read_logs (streak=2)
                  05:02:14  Pulse #3  Health: red (streak=3 ≥ THRESHOLD)
                  05:02:15  WARNING cell_core.observatory:
                            W27: cell_pulse_sustained_red emitted
                            (cell=cell consecutive=3 outbox_id=25010)
                            ✅✅✅
```

events_outbox row 25010 verified via psql:

```
 25010 | cell_pulse_sustained_red | sustained-red-3 | 3
```

### Pipeline bottleneck discovered: pg-bridge silent connection death

events_outbox row was written but pg-bridge JSONL last entry was at 04:13:54 (50min before W27 emit). pg-bridge PID 2409 was `state=running` but had ZERO open TCP connections to PG (`lsof -p PID | grep 5432` empty).

**Same W29 pattern, but in pg-bridge code.** Connection silently died, pg-bridge didn't detect, never reconnected, all NOTIFY events from PG dropped.

Recovery: `launchctl kickstart -k com.nuzantara.pg-organism-bridge`. Bridge re-listened on 15 channels.

### Post-recovery empirical test (synthetic emit)

```
emit smoke (cell=cell consecutive=3 outbox_id=25016) ✅
pg-bridge JSONL: kind=cell_pulse_sustained_red cid=25016 ✅
Organism decisions: kind=cell_pulse_sustained_red actuator=fly_machines_start outcome=dispatched ✅
Follow-up:        kind=fly_machines_start_done (NOT _failed — actuator ran successfully) ✅
```

**Full chain Cell → PG → Redis → Organism → FlyCLI WIRED AND WORKING** ✅✅✅

### Issue discovered: wrong actuator for this outage class

`fly_machines_start` was a no-op because machine was already in `started` state. The W30 outage pattern is "STARTED but UNHEALTHY", not "STOPPED". Needs `fly_machines_restart` actuator.

**Manual restart fixed the outage**: `fly machine restart 7847d95ce257d8 -a nuzantara-rag` (executed at 05:08 WITA).

## W31 candidate (deferred)

Add `apps/organism/organism/actuators/fly_machines_restart.py`:

- `_build_argv`: `["fly", "machines", "restart", "-a", app, machine_id?]`
- Register in `build_actuator_registry`
- Add to `dispatch.py` SAFE_ACTUATORS
- Update yaml rule `cell_sustained_red_restart`: action=`fly_machines_restart` instead of `fly_machines_start`, OR keep both with conditional dispatch based on machine state probe

Also W31: pg-bridge should add `asyncpg.InterfaceError` handling (same W29 pattern). Audit candidate.

## Sources

1. `~/logs/wr2_supervisor_watchdog.launchd.err.log` — pre/post-fix evidence
2. `~/logs/cell/organism.stderr.log` — W27 emit live sequence
3. `~/logs/pg-organism-bridge.error.log` — bridge silent death evidence
4. `~/logs/organism/decisions.jsonl` — Organism dispatch trail
5. `events_outbox` psql query — row 25010 + 25016 confirmation
6. `fly status -a nuzantara-rag` — machine state during outage
