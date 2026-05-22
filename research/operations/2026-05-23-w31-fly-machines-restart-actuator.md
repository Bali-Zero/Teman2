---
date: 2026-05-23
domain: operations
client_case: NB automations hardening — W31 fly_machines_restart actuator closes W27 chain for STARTED-but-UNHEALTHY outages
sources: 4
---

# W31 — fly_machines_restart actuator (W27 chain close)

## Why this exists

W27 (2026-05-23 ~03:00 WITA) shipped a 5-file chain wiring Cell sustained-red → PG NOTIFY → Redis bridge → Organism dispatch → `fly_machines_start` actuator. Designed to auto-recover backend api machine outages without operator intervention beyond Telegram informational alerts.

Live production test 2026-05-23 04:42-05:25 WITA revealed a flaw: **`fly machines start` is a no-op on machines already in `started` state**. The W27 outage class is "STARTED but UNHEALTHY" (machine running, but `/health` failing critical checks). Manual `fly machine restart` fixed it.

W31 closes the loop by introducing the right actuator for this outage class.

## Changes shipped (commit `6cd4e3166`)

### 1. New actuator: `apps/organism/organism/actuators/fly_machines_restart.py` (92 lines)

```python
class FlyMachinesRestart(ActuatorBase):
    name = "fly_machines_restart"

    def _build_argv(self, params: dict) -> list[str]:
        argv = ["fly", "machines", "restart", "-a", params["app"]]
        if (m := params.get("machine") or params.get("machine_id")):
            argv.append(str(m))
        if params.get("skip_health_checks"):
            argv.append("--skip-health-checks")
        return argv
```

Differs from `fly_machines_start`:

- 180s timeout (was 60s) — fly CLI waits for health checks by default
- `skip_health_checks` param for emergency mode (skip wait)
- Restart primitive handles BOTH stopped (cold start) AND started-but-unhealthy (warm restart) cases — strictly more general than start

### 2. Registry registration: `apps/organism/organism/actuators/__init__.py`

Added import + `__all__` entry + `build_actuator_registry` instantiation. Three diff hunks per file. No breakage to existing tests.

### 3. SAFE_ACTUATORS whitelist: `apps/organism/organism/supervisor/dispatch.py`

```python
SAFE_ACTUATORS = frozenset({
    ...
    "fly_machines_start",
    "fly_machines_restart",  # W31
})
```

Critical guard — without this, even a correctly-built rule referencing `fly_machines_restart` would be rejected at dispatch time with `REJECTED_UNKNOWN`. Discovered as W27 footgun; codified as W31 unit test (`test_safe_actuators_includes_restart`).

### 4. YAML rule swap: `apps/organism/organism/rules/base.yaml`

```yaml
- id: cell_sustained_red_restart
  match: { kind: cell_pulse_sustained_red, payload.consecutive_gte: 3 }
  action: { actuator: fly_machines_restart, params: { app: "{payload.app}" } }
  confidence: 0.90
```

Changed actuator from `fly_machines_start` to `fly_machines_restart`. Threshold unchanged at 3 (panel-decided).

### 5. Unit tests: `apps/organism/tests/test_fly_machines_restart.py` (11 tests, 11/11 PASS)

Coverage: \_build_argv variants (5 cases), \_dry_run (2 paths), \_execute ValueError on missing app, registry registration, SAFE_ACTUATORS whitelist guard, name attribute. Full organism regression: 264 passed, 1 skipped, 0 regressions.

## Anti-loop guards (defense-in-depth)

Three layers prevent restart loops during the natural 90-120s uvicorn warmup window when Cell sees red post-restart:

1. **Cell-level idempotency flag**: `_sustained_red_emitted = True` set on first emit. Resets to False only when `status_value != "red"` (any green/yellow pulse). During restart warmup, Cell stays red but emit is **suppressed** because flag stays True. Implemented in `apps/cell/cell/core/pulse.py` (W27 path A).

2. **Circuit breaker** (organism layer): `max_tries=2 / cooldown=15min` per `(actuator, target)` tuple. If two `fly_machines_restart` calls on `nuzantara-rag` fail within 15min, further attempts return `DEFERRED_CB`. Recorded only on failures, not successful actions.

3. **fly CLI semantics**: `fly machines restart` itself is idempotent. A redundant call during an in-flight restart returns quickly with no harm.

## Why W31 is empirically better than W27

W27 production test outcome (verbatim from `~/logs/organism/decisions.jsonl`):

```
kind=cell_pulse_sustained_red actuator=fly_machines_start outcome=dispatched
follow-up: kind=fly_machines_start_done payload={returncode: 0, stdout: "machine started"}
```

`returncode=0 stdout="machine started"` looks like success but is misleading — fly CLI returns 0 when the machine is **already** started (idempotent no-op). The W27 actuator did its job correctly. The problem was the chain dispatched the wrong primitive.

After W31, the same event will dispatch `fly machines restart -a nuzantara-rag` which actively cycles the machine. Empirically (manual restart at 05:08 WITA): machine entered `started, 0/1` for ~90s then transitioned to healthy. Cell pulse went red → red → red (suppressed) → eventually yellow → green.

## Open items (deferred to W32+)

These were raised by Codex non-negotiable list during W27 panel review but not all addressed yet:

| Item                                             | Status          | Notes                                                                                                                           |
| ------------------------------------------------ | --------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Kill switch `CELL_AUTOREMEDIATION_ENABLED=false` | not implemented | Sets in apps/cell/.env; gates whole chain. W32 candidate.                                                                       |
| Durable incident ledger                          | partial         | events_outbox + organism decisions.jsonl provide some audit trail but no dedicated incident table. W33 candidate.               |
| flock on action execution                        | exists (mutex)  | organism Dispatcher uses Redis mutex per `(actuator, target)` tuple with 300s TTL. Sufficient for now.                          |
| Stale-event TTL                                  | not implemented | Old cell_pulse_sustained_red events from yesterday could theoretically re-fire on bridge replay. Need TTL guard. W32 candidate. |
| pg-bridge asyncpg.InterfaceError handling        | not implemented | Discovered during W27 test: bridge silently died on connection drop, same W29 pattern. W32 candidate.                           |

## Sources

1. `~/logs/cell/organism.stderr.log` — W27 sustained_red emit + dispatch trace
2. `~/logs/organism/decisions.jsonl` — `fly_machines_start_done` confirmation
3. `apps/organism/tests/test_fly_machines_restart.py` — 11/11 PASS evidence
4. fly CLI manual restart 05:08 WITA — empirical "restart fixes STARTED-but-UNHEALTHY" proof
