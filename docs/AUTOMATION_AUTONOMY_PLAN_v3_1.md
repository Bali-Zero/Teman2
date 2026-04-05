# AUTOMATION AUTONOMY SYSTEM v3.1 — Final Implementation Plan

_Generated: 2026-03-31 — Synthesized from 3-agent review (Gemini Explore + DeepSeek Reasoning + Codex SRE)_
_Validated: 2026-03-31 — Gemini 2.5 Pro architectural review (NB-1 Oracle substitute — NLM auth expired)_
_Status: ✅ APPROVED — VERDICT GO on all 5 phases_

---

## Executive Summary

- The 65-automation registry exists as a CSV with all structural metadata but zero live runtime data; phases 0-1 wire the state layer that closes this gap.
- The existing `sentinel_lib/` is further along than assumed: `circuit_breaker.py` has atomic writes; only `repairer.py` (`_save_dlq`) needs the atomic fix.
- The biggest architecture risk is double-writer chaos: Watchdog, Surgeon, Sentinel, and DLQ Autopilot all touch overlapping state files; the plan enforces single-writer contracts per file.
- Auto-healing scope is deliberately limited to the ~60% of jobs that have a local `restart_cmd` and `is_idempotent=true`; the remaining 40% (Fly.io, GitHub Actions, webhooks, pg_triggers) are OBSERVE_ONLY.
- Removed from scope: Temporal workflow engine (overkill), Grok integration (no clear ROI), standalone chaos scheduler (too risky for production with 5000+ live clients).

---

## Context: Current System State

**Registry (`data/automations_registry.csv`):**

- 65 automations across 7 types: launchd, cron_air, cron_pro, apscheduler_fly, github_actions, webhook, pg_trigger, mcp_chain
- 31 columns including `repair_scope` (not yet populated), `is_idempotent`, `side_effects`, `has_lock`, `restart_cmd`, `critical`, `blast_radius`
- Columns `last_success_at`, `last_failure_at`, `failure_count_7d` exist in schema but are empty — they are the live data gap this plan closes

**Existing `sentinel_lib/` state:**

- `circuit_breaker.py`: has `_atomic_save()` with `fcntl.LOCK_EX` + `os.replace` — CORRECT
- `repairer.py`: uses plain `open(..., "w")` for `dlq.json` — RACE CONDITION, needs fix
- `watchdog.py` (Core Guardian): has `atomic_write_json()` (tempfile+os.replace+fsync) — reference implementation
- `auto_sentinel.sh`: hardcoded bot token fallback — SECURITY SCAR (cicatrix-scars.md)

**system_doctor.py:** Reads staleness from hardcoded dicts (`STALENESS`, `AIR_LOGS`, `PRO_LOGS`). All log paths and thresholds are static Python literals, not read from the registry. This is the circular dependency the plan must break: CLAUDE.md describes crons, system_doctor hardcodes them, CSV is the emerging source of truth.

---

## Revised 4-Phase Timeline

| Phase | Name                            | Duration   | Output                                                                 |
| ----- | ------------------------------- | ---------- | ---------------------------------------------------------------------- |
| 0     | State Foundation                | Week 1     | `job_state.py`, atomic fixes, cmd allowlist                            |
| 1     | Live Registry Builder           | Weeks 2-3  | `registry_builder.py`, `_registry_live.json`                           |
| 2     | Integrated Healer (in Watchdog) | Weeks 4-6  | Watchdog v2 with healing decision tree                                 |
| 3     | Auto-Documentation              | Weeks 7-8  | Auto-generated docs from CSV, system_doctor reads live registry        |
| 4     | MVP Extensions                  | Weeks 9-12 | LangGraph checkpoint, Exa search in DLQ, performance baseline alerting |

**Total: 12 weeks** (corrected from original 4-week estimate — 3 agents unanimous)

---

## Phase 0 — State Foundation (Week 1)

**Goal:** Atomic, race-free per-job state. No LLMs. No new processes.

### Deliverables

**`scripts/sentinel_lib/job_state.py`** — new file

- Pure stdlib (json, os, tempfile, pathlib, hashlib, datetime)
- State directory: `~/.agent/decisions/state/<job_id>.json`
- Schema per state file:
  ```json
  {
    "job_id": "air-cron-sentinel",
    "status": "ok|failing|open|unknown",
    "last_run_at": "2026-03-31T03:00:00+08:00",
    "last_success_at": "2026-03-31T03:00:00+08:00",
    "last_failure_at": null,
    "duration_sec": 12.4,
    "error": null,
    "run_count": 147,
    "fail_count_7d": 0,
    "_failure_timestamps": []
  }
  ```
- `record_run(job_id, success, duration_sec, error)` — atomic write via tempfile + os.replace
- `get_state(job_id)` — safe load with quarantine on corrupt
- `fail_count_7d(job_id)` — computed from `_failure_timestamps` filtered to last 168h
- **Idempotency token:** `sha256(job_id + date.isoformat())` — date-level granularity, NOT hour-level (fixes hour-boundary duplicate bug: job fails at 23:55, retried at 00:05 = different hour = duplicate escalation)

**Fix `repairer.py`:**

- Replace `_save_dlq(data)` with the same `atomic_write_json()` pattern from `watchdog.py` (tempfile + os.replace + fsync)
- `circuit_breaker.py` `_atomic_save()` is already correct — no change needed

**`scripts/sentinel_lib/allowed_cmds.txt`** — new file

- One restart_cmd prefix per line (allowlist)
- Enforced in `repairer.py` `retry_job()` before any `subprocess.run`
- No `shell=True` for unknown commands
- Safe prefixes: `launchctl kickstart`, `brew services restart`, `python3 scripts/`, `bash scripts/`, `scripts/*.sh`, `fly ssh`

**Fix `auto_sentinel.sh`:**

- Remove hardcoded `TELEGRAM_BOT_TOKEN` fallback (security scar)
- Token must be required env var; fail fast with `exit 1` and logged error if absent

**Dependencies:** None. Pure stdlib.

---

## Phase 1 — Live Registry Builder (Weeks 2-3)

**Goal:** Single live view that merges static CSV with runtime state JSONs.

### Deliverables

**`scripts/sentinel_lib/registry_builder.py`** — new file

- Reads `data/automations_registry.csv` (semicolon-delimited, 31 cols) as SINGLE SOURCE OF TRUTH
- Reads all `~/.agent/decisions/state/<job_id>.json` files
- Merges into a unified dict, adding 6 live columns per job:

| Live Column           | Source                                  |
| --------------------- | --------------------------------------- |
| `last_success_at`     | `state/<job_id>.json`                   |
| `last_failure_at`     | `state/<job_id>.json`                   |
| `failure_count_7d`    | computed from `_failure_timestamps`     |
| `avg_duration_sec`    | rolling 14-run average                  |
| `current_status_live` | `ok / failing / open / stale / unknown` |
| `circuit_state`       | `circuit_breaker.json` lookup           |

- Output: `~/.agent/decisions/state/_registry_live.json` (atomic write)
- Called by Sentinel at end of each run (idempotent regeneration)

**CSV `repair_scope` back-fill (manual + script):**

| Value          | Criteria                                                                                                                     |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `LOCAL`        | has local `restart_cmd` + `is_idempotent=true`                                                                               |
| `OBSERVE_ONLY` | `host=fly_io` OR `automation_type=github_actions/webhook/pg_trigger` OR `is_idempotent=false` with `side_effects=email_sent` |
| `REMOTE_SSH`   | restart_cmd requires SSH to other machine                                                                                    |

Estimated distribution: ~60% LOCAL, ~40% OBSERVE_ONLY.
`fly-apscheduler-notification-hourly` is explicitly `OBSERVE_ONLY` (`is_idempotent=false`, `side_effects=email_sent` → would send duplicate emails to 5000+ clients).

**`system_doctor.py` partial integration (Phase 1):**

- Add `load_live_registry()` function that reads `_registry_live.json` if it exists
- Fallback to existing hardcoded dicts if file absent (cold start safety)
- Full migration deferred to Phase 3

**Dependencies:** Phase 0 complete.

---

## Phase 2 — Integrated Healer in Watchdog (Weeks 4-6)

**Goal:** Replace the conceptual "auto_healer" with a decision tree merged into `watchdog.py`. One process, one writer per state file.

**Architecture decision:** Do NOT create a separate `auto_healer.py` process. Merge healing logic into `watchdog.py` as a new `_healing_core()` function called after `_watchdog_core()`. This eliminates the double-writer chaos risk.

### Decision Tree

```
For each job in _registry_live.json where repair_scope != OBSERVE_ONLY:

  circuit_state == OPEN?
    → skip (already in recovery, log only)

  current_status_live == failing AND critical == true AND fail_count_7d >= 1?
    → send_telegram_alert (CRITICAL tier)
    → write to escalations.json (NOT claude_tasks — that's DLQ Autopilot domain)

  current_status_live == failing AND is_idempotent == true AND fail_count_7d >= 3?
    → check allowed_cmds.txt → subprocess.run(restart_cmd, shell=False)
    → success: record_run(success) + send_telegram_recovery
    → failure: DLQ Autopilot picks up on next 30min cycle

  current_status_live == failing AND is_idempotent == false?
    → alert only (Telegram) — NO auto-retry

  current_status_live == stale?
    → log only (system_doctor surfaces in morning report)
```

### Single-Writer Contracts

| File                    | Single Writer                          | Readers                                   |
| ----------------------- | -------------------------------------- | ----------------------------------------- |
| `circuit_breakers.json` | `circuit_breaker.py` (sentinel_lib)    | Watchdog, DLQ Autopilot                   |
| `dlq.json`              | `repairer.py` / DLQ Autopilot          | Watchdog (read-only)                      |
| `escalations.json`      | Watchdog (job failures) + Air Sentinel | Pro reads at session start                |
| `claude_tasks/`         | **DLQ Autopilot ONLY**                 | Claude Code, human                        |
| `state/<job_id>.json`   | `job_state.py` (via Sentinel wrapper)  | Watchdog, registry_builder, system_doctor |

### Additional Phase 2 Rules

**KeepAlive=true jobs are immune to chaos:** Jobs with `KeepAlive=true` in launchd (OpenClaw, Ollama, Fly tunnel, PostgreSQL, Redis) cannot be circuit-broken — launchd restarts them regardless. Do not apply chaos or circuit breaker to these.

**Idempotency token for dedup:** `sha256(job_id + datetime.utcnow().date().isoformat()).hexdigest()[:12]` — prevents duplicate DLQ entries or escalations within same calendar day.

**Sentinel wrapper records state:** `auto_sentinel.sh` calls `job_state.record_run()` for each monitored job. Job list read from `_registry_live.json`, not hardcoded.

**Dependencies:** Phase 0 + Phase 1 fully complete.

---

## Phase 3 — Auto-Documentation (Weeks 7-8)

**Goal:** CSV is the single source of truth; docs are generated artifacts, never hand-edited.

### Deliverables

**`scripts/sentinel_lib/doc_generator.py`** — new file

- Reads `data/automations_registry.csv`
- Generates `docs/AUTOMATIONS_REFERENCE.md` (one-way: CSV → doc)
- Generates CLAUDE.md §18 "Cron Air" table from filter `host=air AND automation_type=cron_air`
- Trigger: called by Sentinel after each run if CSV `last_modified_at` has changed (idempotent)
- Generated sections marked: `<!-- AUTO-GENERATED from data/automations_registry.csv — do not hand-edit -->`

**`system_doctor.py` full migration:**

- Replace `AIR_LOGS`, `PRO_LOGS`, `STALENESS` hardcoded dicts with `load_live_registry()`
- Map `staleness_threshold_h` from CSV column directly
- Map `log_path` from CSV column for staleness detection
- Fallback: if `_registry_live.json` absent → hardcoded dicts + WARNING log

**Dependencies:** Phase 1 stable for ≥1 week, Phase 2 running (live data populates healing stats).

---

## Phase 4 — MVP Extensions (Weeks 9-12)

**Goal:** Increase intelligence, not operational complexity.

### LangGraph Checkpoint in watchdog.py

- Use `langgraph-checkpoint-postgres` (already in requirements for agent layer)
- Makes healing cycles resumable across Watchdog crashes mid-healing
- Scope: only `_healing_core()` function, not existing `_watchdog_core()` test logic

### Exa Search in DLQ Autopilot

- When `repairer.py` reaches T3 escalation threshold (would create `claude_task`):
  1. Call `mcp__exa__web_search_exa` with `error_summary + job_id`
  2. If matching fix pattern found with high confidence → try Aider fix (T2 retry)
  3. If no match → escalate to `claude_task` as normal
- Extends autonomous healing window before human escalation

### Performance Baseline Alerting

- `avg_duration_sec` tracked in `job_state.py` (from Phase 0)
- `registry_builder.py` computes `baseline_duration_sec` (14-run rolling average)
- Telegram alert if `current_duration > 3x baseline` for any job
- Priority monitoring: `air-cron-kb-ingest` (Qdrant-dependent), `pro-cron-kg-builder` (56K nodes), `fly-apscheduler-self-healing`

---

## What Was REMOVED and Why

| Removed Item                      | Original Phase | Reason                                                                                                           |
| --------------------------------- | -------------- | ---------------------------------------------------------------------------------------------------------------- |
| Temporal.io workflow engine       | Phase 4        | Overkill for 65-job registry. LangGraph checkpoint achieves resumability at zero additional infra cost.          |
| Grok integration                  | Phase 4        | No validated use case in current workflows. X/Twitter channel already broken (CRC). Deferred to post-MVP.        |
| Standalone chaos scheduler        | Phase 2        | Too risky with live client-facing jobs (WhatsApp, notifications, Fly.io). KeepAlive=true jobs are immune anyway. |
| Separate `auto_healer.py` process | Phase 2        | Double-writer chaos risk on shared state files. Merged into watchdog.py instead.                                 |
| CLAUDE.md as data source          | Phase 3        | Circular dependency: agents update it, system_doctor reads it, generation scripts overwrite it. CSV wins.        |

---

## Critical Architecture Decisions

**Decision 1 — CSV as Single Source of Truth, not CLAUDE.md.**
CLAUDE.md is a narrative document that human and AI agents both read and write. Using it as a data source creates a circular dependency. The 31-column CSV is machine-readable, version-controlled, and contains all structural metadata. CLAUDE.md §18 becomes a generated artifact.

**Decision 2 — Merge healer into watchdog, no new process.**
A separate `auto_healer.py` would require coordination on circuit_breakers.json, dlq.json, and escalations.json with Watchdog. Both would run at 03:00 WITA — concurrent writes guaranteed. The merged approach has one lock, one execution context, sequential read-modify-write.

**Decision 3 — Single-writer contracts per state file.**
Each file has exactly one writer. Readers never write. Enforced by convention (same-user, same-machine, same timezone). Violation = blocking code review.

**Decision 4 — repair_scope=OBSERVE_ONLY for all Fly.io, GitHub Actions, webhooks, non-idempotent jobs.**
`fly-apscheduler-notification-hourly` is the canonical example: `is_idempotent=false`, `side_effects=email_sent`. Auto-retry would send duplicate emails to 5000+ clients. The 40% OBSERVE_ONLY scope is non-negotiable.

**Decision 5 — Idempotency token uses date granularity, not hour.**
`sha256(job_id + date.isoformat())` = at most one escalation per job per day. Fixes the 23:55 → 00:05 failure causing two escalations in quick succession.

---

## Risk Register

| #   | Risk                                                                                                                         | P   | I        | Mitigation                                                                                                                                                            |
| --- | ---------------------------------------------------------------------------------------------------------------------------- | --- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | **State file corruption on concurrent write**                                                                                | Med | High     | `atomic_write_json()` (tempfile+os.replace+fsync) in Phase 0. `fcntl.LOCK_EX` already in circuit_breaker.py.                                                          |
| 2   | **restart_cmd injection via CSV**                                                                                            | Low | Critical | Phase 0 allowlist: `allowed_cmds.txt`. Prefix-check before any exec. No `shell=True` for non-listed commands.                                                         |
| 3   | **Auto-retry of non-idempotent job** (duplicate emails/WhatsApp)                                                             | Low | Critical | `repair_scope=OBSERVE_ONLY` in CSV + `is_idempotent` check in decision tree (two independent guards).                                                                 |
| 4   | **CSV drift** (new launchd jobs not added to CSV)                                                                            | Med | Med      | Phase 3 doc_generator: "jobs in launchctl not in CSV" warning section. system_doctor daily Telegram surfaces unknown jobs.                                            |
| 5   | **Watchdog regression** from healing merge (execution time exceeds 03:00-03:30 window)                                       | Low | Med      | Healing adds <60s overhead (2-3 subprocess.run per failing job). Monitor first-run duration before enabling all jobs. Watchdog timeout is separate.                   |
| 6   | **I/O scalability** — one JSON per job works for 65 jobs, could bottleneck at 10x scale                                      | Low | Low      | Acceptable for current scope. If jobs exceed ~500, migrate state to SQLite (`~/.agent/decisions/state.db`). Not a concern for 12-week plan.                           |
| 7   | **CSV schema validation** — malformed CSV (missing semicolon, extra column) causes silent runtime errors in registry_builder | Med | Med      | Add `validate_registry_csv()` in registry_builder.py: check row count, required columns present, no empty automation_id. Fail fast with Telegram alert on load error. |
| 8   | **Watchdog window exceeded** — if many jobs fail simultaneously, healing loop adds >30min to watchdog execution              | Low | Med      | Add per-healing-cycle timeout (30s max per job retry). Skip remaining jobs if watchdog exceeds 03:25 WITA. Log skipped jobs for next cycle.                           |

---

## Success Metrics Per Phase

**Phase 0**

- `repairer._save_dlq()` uses atomic write ✓ (code review)
- `allowed_cmds.txt` covers all restart_cmd patterns in CSV ✓ (grep check)
- `auto_sentinel.sh` exits 1 if `TELEGRAM_BOT_TOKEN` absent ✓ (unit test)
- `job_state.py` imports with stdlib only ✓ (`python3 -c "import sentinel_lib.job_state"` no venv)

**Phase 1**

- `_registry_live.json` timestamp within 30min of 03:00 WITA daily
- All 65 CSV rows have `repair_scope` populated
- `system_doctor.py` reads live registry without errors when file exists

**Phase 2**

- Zero duplicate DLQ entries for same job within 24h (verifiable from `dlq.json`)
- Healing decision tree never touches OBSERVE_ONLY jobs (logged)
- ≥1 successful auto-recovery of a LOCAL job within first 2 weeks

**Phase 3**

- `AUTOMATIONS_REFERENCE.md` auto-regenerated on CSV change (git log)
- CLAUDE.md §18 matches CSV filter `host=air,automation_type=cron_air` (diff check)
- `system_doctor.py` hardcoded dicts removed (grep)

**Phase 4**

- Watchdog survives simulated mid-healing crash and resumes on next run (LangGraph checkpoint)
- T3 escalations (claude_tasks/) reduced ≥20% over 4 weeks (file count)
- ≥1 true-positive performance alert within first month

---

## Implementation Order (Dependency Graph)

```
Phase 0 (no deps)
  ├── job_state.py
  ├── Fix repairer._save_dlq() → atomic
  ├── allowed_cmds.txt + allowlist check
  └── Fix auto_sentinel.sh token

Phase 1 (requires Phase 0)
  ├── registry_builder.py
  ├── Back-fill repair_scope in CSV
  └── system_doctor.py: add load_live_registry() with fallback

Phase 2 (requires Phase 0 + Phase 1)
  ├── _healing_core() merged into watchdog.py
  ├── Decision tree implementation
  ├── Single-writer contract enforcement
  └── Sentinel records job_state per job

Phase 3 (requires Phase 1 + Phase 2 stable ≥1 week)
  ├── doc_generator.py: CSV → AUTOMATIONS_REFERENCE.md + CLAUDE.md §18
  └── system_doctor.py: remove hardcoded dicts

Phase 4 (requires Phase 2 + Phase 3)
  ├── LangGraph checkpoint in _healing_core()
  ├── Exa search in DLQ before T3 escalation
  └── Performance baseline alerting in registry_builder
```

---

## Critical Files for Implementation

| File                                       | Phase | Action                                          |
| ------------------------------------------ | ----- | ----------------------------------------------- |
| `scripts/sentinel_lib/repairer.py`         | 0     | Fix `_save_dlq()` atomic write                  |
| `scripts/sentinel_lib/job_state.py`        | 0     | CREATE (new file)                               |
| `scripts/sentinel_lib/allowed_cmds.txt`    | 0     | CREATE (new file)                               |
| `scripts/auto_sentinel.sh`                 | 0     | Remove hardcoded token                          |
| `scripts/sentinel_lib/registry_builder.py` | 1     | CREATE (new file)                               |
| `data/automations_registry.csv`            | 1     | Back-fill `repair_scope` column                 |
| `scripts/system_doctor.py`                 | 1+3   | Add `load_live_registry()`, then full migration |
| `apps/evaluator/core_guardian/watchdog.py` | 2     | Add `_healing_core()`                           |
| `scripts/sentinel_lib/doc_generator.py`    | 3     | CREATE (new file)                               |
| `docs/AUTOMATIONS_REFERENCE.md`            | 3     | Make generated artifact                         |
| `CLAUDE.md §18`                            | 3     | Make generated section                          |

---

---

## Validation Record

| Validator          | Method                          | Date       | Verdict                                     |
| ------------------ | ------------------------------- | ---------- | ------------------------------------------- |
| Gemini Explore     | 3-agent brainstorm (CSV schema) | 2026-03-30 | GO (31-col schema approved)                 |
| DeepSeek Reasoning | Architectural analysis          | 2026-03-31 | CONDITIONAL GO → incorporated into v3.1     |
| Codex SRE          | Code-level review               | 2026-03-31 | CONDITIONAL GO → 10 gaps fixed in v3.1      |
| Gemini 2.5 Pro     | Oracle architectural review     | 2026-03-31 | ✅ **GO on all 5 phases**                   |
| NB-1 (NotebookLM)  | Pending re-auth (`nlm login`)   | —          | Deferred — run `! nlm login` then re-upload |

_Note: NLM auth expired on Air. Re-authenticate with `! nlm login` then upload with `nlm source add docs/AUTOMATION_AUTONOMY_PLAN_v3_1.md` to NB-1 for permanent codebase grounding._
