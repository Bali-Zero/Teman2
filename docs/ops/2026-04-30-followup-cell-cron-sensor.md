# Renaissance Follow-up #1 — Cell cron sensor obsolete entries (2026-04-30)

Discovery during live test phase of the renaissance:
`apps/cell/cell/sensors/cron_sensor.py::_JOB_PERIODS` watches 10 cron
jobs, but **2 of them no longer exist**:

| Job                | Reason                                                                                | Age of stale state |
| ------------------ | ------------------------------------------------------------------------------------- | ------------------ |
| `core_guardian`    | PR #367 (PR-C5) deleted the cron line — 30 weeks of `candidates=0 fixed=0`, dead code | 382 h              |
| `fly_health_check` | Migrated 2026-04-14 to `fly-watcher` (per crontab Pro comment)                        | 373 h              |

The state files (`~/.agent/decisions/state/{core_guardian,fly_health_check}.last.json`) still exist on disk, frozen at 16+ days old. The sensor classifies them as `red` (`age > 3× period`) on every pulse, which:

1. Makes Cell pulse `health=red` permanently
2. Floods `stale_jobs` and `failed_jobs` lists in pulse metadata
3. Prevents the Critic agent (PR-D3) from seeing real changes — every pulse looks identical, no fresh expectations to evaluate

## Fix

Remove `core_guardian` and `fly_health_check` from `_JOB_PERIODS`. Add inline comments documenting why (with PR pointers) so a future maintainer doesn't re-add them on a cargo-cult pass.

State files left in place (no harm; not read after dict removal).

## Why not delete the state files

Deleting them on Pro is reversible only by re-running the dead jobs. Leaving them satisfies the principle "discovery is destructive — keep the trail of the previous regime." The dict change is the source-controlled action; the disk artifacts are forensic.

## Pre-existing broken state files NOT touched by this fix

| Job                       | Age   | Status | Note                                                                                                                                                                                        |
| ------------------------- | ----- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `t4_monitor_daily`        | 384 h | failed | 16 days offline — separate investigation                                                                                                                                                    |
| `nlm_deep_research`       | 387 h | failed | Same                                                                                                                                                                                        |
| `system_doctor`           | 49 h  | failed | The cron-wrapper (PR-C5 deleted) wrote `failed` for TCC error. cron-agent-python version writes elsewhere. State file should be removed once cron-agent-python state path is canonicalized. |
| `knowledge_graph_builder` | 98 h  | ok     | Expected ≤24h, currently 4× over. Likely cron not firing — separate investigation.                                                                                                          |
| `fly_pg_backup`           | 0.8 h | failed | Recent, wrote failed — separate investigation.                                                                                                                                              |

These remain `red`/`yellow` after this fix. The sensor still flags them, which is **correct** — they're real legitimate degradations to investigate, not zombies like core_guardian.

## Verification

- `python3 -m py_compile apps/cell/cell/sensors/cron_sensor.py` → OK
- `pytest tests/test_new_sensors.py -k 'cron or Cron'` → **4/4 passed**
- Manual sensor live test: 10 entries → 8 entries (correct delta)

## Test plan

- [x] py_compile + 4 cron unit tests
- [x] Manual sensor live test with sample state files
- [ ] (Post-merge, after cell-organism restart) Cell pulse health flips from `red` to at least `yellow` — `core_guardian` and `fly_health_check` no longer in `stale_jobs`/`failed_jobs` metadata. Verify in `~/Library/Logs/cell-organism.log`.
- [ ] (Post-merge, 24-72 h soak) Critic agent forms expectations on pulses with non-frozen sensor state. Cortex episodes count increments past 21,938 plateau (was 21,937 pre-restart).

## Related

- Renaissance summary: `docs/ops/2026-04-30-renaissance-summary.md`
- Predecessor PR-C5: `docs/ops/2026-04-30-pr-c5-dead-code.md` (deleted core_guardian cron)
- Predecessor PR-D3: `docs/ops/2026-04-30-pr-d3-cell-critic-json-parse.md` (Critic JSON parse fix)
- MOS unresolved id 1969 (this discovery)
