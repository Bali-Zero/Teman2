---
date: 2026-05-12
domain: symbiosis
client_case: SYMBIOSIS gap-closure loop · Gap 1 CLOSED EMPIRICALLY
sources: 6
status: closed
loop_branch: feat/symbiosis-loop-2026-05-12
empirical_verification_wita: 2026-05-12 11:47:52
---

# Gap 1 — Cell silenti EMPIRICALLY CLOSED

**First non-`cell` pulse in observatory.db**: `seo-guardian | red | 2026-05-12 11:47:52 WITA`

## What it took (4 layers, not 1)

The original loop and even the NLM bipolar verifier review identified only **Layer 1** (env var missing). Empirical iteration discovered 3 more gating layers between `cell_core.pulse:265` and `~/.cell-observatory/observatory.db` populated:

### Layer 1 — `CELL_OBSERVATORY_EMIT=true` env var

`observatory.is_enabled()` returns `os.getenv("CELL_OBSERVATORY_EMIT","").lower() == "true"`. Without it, `emit_pulse_observed()` returns silently before the pool init. **Fixed via OVERRIDE 3 + 4** (script env export + plist EnvironmentVariables).

### Layer 2 — `EVENTBUS_DATABASE_URL` set + reachable

`_get_or_create_pool()` reads `os.environ.get("EVENTBUS_DATABASE_URL")` and creates an asyncpg pool. On Pro the EventBus PG is on Fly.io at `nuzantara-postgres.flycast` which doesn't resolve over Pro's system DNS. Workaround: `flyctl proxy 15432:5432 -a nuzantara-postgres` already running (PID 2397) maps Fly PG to `127.0.0.1:15432`. Set `EVENTBUS_DATABASE_URL=postgresql://backend_rag_v2:***@localhost:15432/nuzantara_rag` (same as `com.cell.organism.plist`).

**Fixed via**:

- `~/scripts/openclaw-cron/seo-cell-daily.sh` export (OVERRIDE 3 extension)
- `~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist` `EnvironmentVariables` block

### Layer 3 — `asyncio.run()` exits before fire-and-forget emit task completes

`cell_core.pulse:265` schedules `asyncio.create_task(observatory.emit_pulse_observed(...))`. In `apps/evaluator/seo_cell/run_seo_cell.py`, `asyncio.run(_run_one_pulse())` returns immediately after `single_pulse()` and tears down the loop — the emit task is canceled before its PG INSERT + NOTIFY can complete.

**Fix in `run_seo_cell.py`** (commit `9a4f3f544`):

```python
pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
if pending:
    await asyncio.wait(pending, timeout=10.0)
```

### Layer 3 bis — `pg_notify` 8000-byte payload limit + collector schema contract

`pg_notify(channel, payload)` has a hard 8000-byte payload limit. Cells with rich sensor metadata (seo_cell: 7 sensors with kg/ga4/war_room_event etc) easily exceed it: emit fails with `payload string too long`. The events_outbox row INSERT succeeded (no size limit on BYTEA/JSON), but the wire NOTIFY did not.

**Fix in `cell_core.observatory`** (commit `9a4f3f544` + schema fix `6ec45a25f`): NOTIFY a minimal stub instead of full payload:

```python
notify_stub = {
    "_outbox_id": outbox_id,
    "cell_id": cell_id,
    "cell_kind": cell_kind,
    "pulse_id": pulse_id,
    "pulse_timestamp": pulse_timestamp_ms,
    "phase": phase,
    "pulse_result": {
        "classifier_self": pulse_result.get("classifier_self"),
    },
}
```

The stub must nest `classifier_self` under `pulse_result` because the collector at `apps/cell-observatory-collector/cell_observatory/storage.py` reads `payload["pulse_result"]["classifier_self"]`. Initial Layer 3 fix flattened it; the collector silently crashed on KeyError. Fixed in commit `6ec45a25f`.

Full payload (sensors + homeostatic_state + scar_signals) remains in `events_outbox` row, queryable by `_outbox_id` for full-detail consumers.

## Empirical timeline

| Time WITA | Event                                                                               |
| --------- | ----------------------------------------------------------------------------------- | --- | ----------------------- |
| 04:35     | User authorized OVERRIDE phase: "Sì, tutti e 4 (full override)"                     |
| 04:38     | OVERRIDE 3: seo-cell-daily.sh patched with `export CELL_OBSERVATORY_EMIT=true`      |
| 04:39     | First seo-cell test: pulse OK, emit silent (EVENTBUS_DATABASE_URL unset)            |
| 04:41     | OVERRIDE 4: com.matagaruda.sentinel.hourly.plist installed + bootstrap              |
| 11:32     | Sentinel plist updated with EVENTBUS_DATABASE_URL env                               |
| 11:33     | seo-cell-daily.sh patched with EVENTBUS_DATABASE_URL export                         |
| 11:36     | seo-cell test 2: pulse OK, emit attempted, fails "payload string too long"          |
| 11:38     | events_outbox row 12332 written for seo-guardian (INSERT works, NOTIFY fails)       |
| 11:38     | events_outbox row 12333 written (INSERT works, NOTIFY fails)                        |
| 11:39     | Layer 3 fix: notify_stub <8000 bytes                                                |
| 11:41     | Layer 3 bis fix: notify_stub schema nested classifier_self under pulse_result       |
| 11:47     | seo-cell test 3: pulse OK, emit completes, **observatory.db gets seo-guardian row** |
| 11:47:52  | First non-`cell` pulse in local observatory: `seo-guardian                          | red | 2026-05-12 11:47:52` ✅ |

## events_outbox state on Fly PG

```
id=12333 2026-05-12 03:43:31 UTC consumed=False cell=seo-guardian
id=12332 2026-05-12 03:38:36 UTC consumed=False cell=seo-guardian
```

Both rows are present in `events_outbox` (the durable substrate). The collector will mark `consumed_at` on the next NOTIFY-driven `insert_pulse_event()` call OR via the replay-on-reconnect path (max_age 60min).

## Commits closing Gap 1

| SHA         | Layer               | What                                                                               |
| ----------- | ------------------- | ---------------------------------------------------------------------------------- |
| `5ac38cce5` | governance          | VADEMECUM point 17 silent-birth prevention checklist                               |
| `b8820e759` | governance          | SYMBIOSIS Law 3 PG_CHANNEL_MAP=13 corrected                                        |
| Pro-local   | Layer 1             | `~/scripts/openclaw-cron/seo-cell-daily.sh` export `CELL_OBSERVATORY_EMIT=true`    |
| Pro-local   | Layer 2             | Same script: export `EVENTBUS_DATABASE_URL=postgresql://...@localhost:15432/...`   |
| Pro-local   | Layer 1+2           | `~/Library/LaunchAgents/com.matagaruda.sentinel.hourly.plist` EnvironmentVariables |
| `9a4f3f544` | Layer 3 + Layer 3.0 | `run_seo_cell.py` await pending tasks + `observatory.py` notify_stub <8000 bytes   |
| `6ec45a25f` | Layer 3 bis         | `observatory.py` notify_stub schema nest classifier_self under pulse_result        |

## What's still open (Layer B from NB-1 R6 audit)

Sentinel cron `com.matagaruda.sentinel.hourly` invokes `apps/mata-garuda/scripts/run_sentinel_py.py:120-134` which executes the legacy worker pipeline directly (normalizer → scorer → nlm_feeder → digest), NOT `PulseLoop.tick()`. The REFLECT phase never fires, so sentinel will never emit even with Layer 1+2 fixed. Deferred to HGT TICKET C in `2026-05-12-hgt-fase4-recovery-spec.md`.

## What "closed empirically" means

Gap 1 = "Cell families silenti" → solved for seo-cell (one of the 3 silent cells identified in the original briefing). The other 2:

- **mata-garuda sentinel_cell**: blocked by Layer B (NB-1 R6 anti-pattern), not by env vars. Needs HGT TICKET C scope rewrite of `run_sentinel_py.py`.
- **intel-scraper-cell**: blocked by HGT TICKET B (not invoked by `run_intel_pipeline.py`). Same scope.

So Gap 1 is **structurally closed** (root cause + 4-layer fix recipe documented + 1 silent cell empirically emitting), but full closure for the other 2 silent cells requires the HGT recovery work outside this loop's scope.

## Sources

1. `~/logs/seo-cell/pulse-20260512-114752.log` (final successful emit log)
2. `sqlite3 ~/.cell-observatory/observatory.db "SELECT cell_id..."` 2026-05-12 11:47:52 WITA
3. Fly events_outbox rows id=12332, 12333 (asyncpg query via flyctl proxy)
4. Commits `5ac38cce5`, `b8820e759`, `9a4f3f544`, `6ec45a25f` on `feat/symbiosis-loop-2026-05-12`
5. `apps/cell-observatory-collector/cell_observatory/storage.py:insert_pulse_event` (collector schema contract)
6. `~/scripts/openclaw-cron/seo-cell-daily.sh` (patched script, Pro-local)
