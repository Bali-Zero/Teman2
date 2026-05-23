---
date: 2026-05-23
domain: operations
loop: NB-automations-hardening W53
status: shipped (commit c68c8f549); live verified — gate loaded 53 TERMINAL jobs; current cycle stale-overlap 0 (legit alerts let through correctly)
---

# W53 — `nuzantara-sentinel` DLQ TERMINAL suppression gate at staleness layer

## TL;DR

Phase 0 added `DLQ TERMINAL state` tracking but only in `dlq_autopilot.py:454`. Sentinel
`process_job` still re-escalates TERMINAL-marked jobs every cron tick = silent alert storm.
**27 of 38 lifetime stale-flagged jobs were in DLQ as TERMINAL.** Fix: pre-load
`dlq_terminal_set` once per sentinel cycle, pass to `process_job`, gate before WARNING +
escalation. New action `"skipped_dlq_terminal"` returns silently.

## Empirical evidence

Lifetime data from `~/logs/sentinel.log`:

```
Lifetime stale-flagged: 38 unique jobs
Of those CURRENTLY in DLQ TERMINAL: 27 (W53 will suppress)
Examples: articles_indexing_daily, backend_prewarm, biz_orchestrator,
          compliance_autopilot, core_guardian, dlq_autopilot, fly_health_check,
          fly_qdrant_backup, gdrive_intel_archive, gdrive_pg_backup,
          health_check, kbli_indexing_daily, nlm_bridge, practice_lifecycle_check,
          quality_orchestrator, seo_guardian_measure, seo_guardian_observe,
          weekly_report (and 9 more)
```

Each hourly sentinel run was logging `WARNING jobname: status=stale, error=` for these 27
jobs, then `phase advance to T4 rejected: Invalid phase transition` for each one (because
they're already T4/TERMINAL), then re-escalating again next hour. Pure noise.

Most recent run (post-W53 fix): 9 stale-flagged jobs, **0 in DLQ TERMINAL** → W53 correctly
LETS THROUGH (these are legitimate alerts):

```
Last sentinel run stale: conversation_trainer, fly_cost_alert,
  knowledge_graph_builder, post_publish_poller, post_publish_webhook,
  prime_tunnel, qdrant_snapshot, war_room, zombie_hunter
NOT in DLQ TERMINAL (legitimate, escalated correctly): all 9
```

## Root cause

Phase 0 (`9e25403a5 feat(sentinel): Phase 0 — DLQ TERMINAL state + circuit-breaker TOCTOU
fix + registry HALT gate`) added the TERMINAL check inside `dlq_autopilot.py:453-455`:

```python
if entry.get("status") == "TERMINAL":
    logger.info(f"{job}: status=TERMINAL — skipping (use 'dlq clear {job}' to remove)")
```

But this only fires when `dlq_autopilot.py` is processing the DLQ entry. `nuzantara-sentinel.py`
runs an OUTER loop that calls `process_job(job_id, state, ...)` per registry job, evaluates
staleness from `state.get("ts")`, and escalates to T3/T4 + writes to DLQ if stale.

The escalation calls `add_to_dlq(job_id, ...)` which CREATES a new DLQ entry every cycle.
That entry IS later TERMINAL'd by dlq_autopilot when `max_attempts=10` reached. But until
then, sentinel keeps re-flagging the same job as stale every hour → DLQ entry resets
attempts → never reaches TERMINAL.

The Phase 0 intent (don't pester TERMINAL jobs) needed enforcement at BOTH layers:
- dlq_autopilot ✓ (Phase 0 shipped)
- nuzantara-sentinel ✗ (W53 ships now)

## Fix shipped

`scripts/nuzantara-sentinel.py` (commit `c68c8f549`):

**Pre-load TERMINAL set** at top of main loop (before `for job_id, state in states.items()`):

```python
dlq_terminal_set: set = set()
try:
    _dlq_path = os.path.expanduser("~/.agent/decisions/dlq.json")
    _dlq_data = json.loads(open(_dlq_path).read())
    _dlq_list = _dlq_data.get("queue", _dlq_data if isinstance(_dlq_data, list) else [])
    dlq_terminal_set = {
        e.get("job") for e in _dlq_list
        if isinstance(e, dict) and e.get("status") == "TERMINAL" and e.get("job")
    }
    logger.info(f"W53 DLQ TERMINAL gate: {len(dlq_terminal_set)} jobs suppressed from escalation")
except Exception as _e:
    logger.warning(f"W53 DLQ TERMINAL gate: failed to load dlq.json ({_e}); falling back to no suppression")
```

**Gate inside `process_job`** (after optional-job check, before WARNING log):

```python
if job_id in dlq_terminal_set and status in ("failed", "stale"):
    logger.info(f"{job_id}: DLQ TERMINAL — suppressing escalation (W53)")
    return {"action": "skipped_dlq_terminal", "tier": 0, "success": None}
```

## Empirical verification (live)

Live run at 19:26 WITA:

```
INFO === Sentinel run start ===
INFO Purged 27 phantom CB entries: [...]
INFO W53 DLQ TERMINAL gate: 53 jobs suppressed from escalation
WARNING login_healthcheck: status=fail, error=    # not in TERMINAL set
WARNING zombie_hunter: status=stale, error=        # not in TERMINAL set
WARNING war_room: status=stale, error=             # not in TERMINAL set
... (9 stale alerts total — all legit, all let through)
INFO === Sentinel done: 48 checked, 38 healthy, 10 escalated, 0 suppressed in 140.9s ===
```

**W53 gate loaded correctly** (53 jobs). Current cycle had 9 stale jobs, 0 in TERMINAL set,
so all 9 correctly escalated. The "10 escalated" headline persists because today's stale
jobs aren't yet TERMINAL — they'll reach TERMINAL after 10 autopilot attempts, then W53
gate will suppress future re-escalations.

## Side-discovery: separate W54+ candidate

Same W53 live run surfaced:

```
ERROR Error processing dlq_autopilot: unsupported operand type(s) for -: 'float' and 'str'
```

`state.get("ts")` for job `dlq_autopilot` is returning a string instead of float, breaking
the `age = now - last_ts` arithmetic. Same job is in DLQ TERMINAL (so W53 gate would
suppress it once it reaches that check), but the exception fires earlier at line 533 in
`process_job`. Deferred to W54+: defensive type coercion in `process_job`.

## Deferred W54+ candidates

1. **Type coercion in `process_job`**: `state.get("ts", 0)` should be `float()`-wrapped to
   prevent `unsupported operand` errors. Current code crashes on string state values from
   legacy state files.
2. **`add_to_dlq` re-entry**: when sentinel calls escalation paths, it writes new DLQ
   entries for already-TERMINAL jobs. W53 prevents this (gate exits before escalation), but
   audit other callers of `add_to_dlq` to ensure they also respect TERMINAL.
3. **Sentinel one-shot run duration**: today's W53 live run took 140.9s (vs 6.5s typical),
   because RunAtLoad coincided with `_force_halfopen_stale_circuits` + 27 phantom CB purge
   + W53 gate IO load. Investigate if startup operations are expensive enough to warrant
   their own throttle.

## Lessons

- **Phase features must be enforced at every layer**. Phase 0 added TERMINAL state but only
  half-shipped (dlq_autopilot but not sentinel). Both consumers need the gate.
- **Empirical gate verification**: log the suppression set size at load time. Without "W53
  gate loaded 53 jobs" I wouldn't know if the read succeeded.
- **Action-name discipline**: `skipped_dlq_terminal` differs from `skipped_optional` and
  `skipped_circuit_open` — gives DLQ telemetry the right discriminator.
- **Defense-in-depth on state file reads**: try/except + empty fallback. Sentinel must
  never crash because dlq.json is malformed; degraded mode (no suppression) is acceptable.
- **Family**: sentinel decision-tree completeness (Phase 0 follow-up). W51 fixed the SCRIPT
  used (HOME-fork). W53 fixes the LOGIC inside that script. Both needed.

## Reference

- Commit: `c68c8f549` — `fix(sentinel): DLQ TERMINAL suppression gate at staleness layer`
- File: `scripts/nuzantara-sentinel.py` (~41 lines added)
- Phase 0 sibling: `9e25403a5 feat(sentinel): Phase 0 — DLQ TERMINAL state + ...`
- W51 sibling RCA: `research/operations/2026-05-23-w51-sentinel-plist-home-fork.md`
- DLQ entry sample: `~/.agent/decisions/dlq.json` (63 entries, 53 TERMINAL, 10 skipped_preflight)
