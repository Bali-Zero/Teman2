# Automation Autonomy System — Plan v3.2

**Date:** 2026-03-31
**Reviewed by:** Claude Code (orchestrator) · Codex SRE · Gemini Architecture · DeepSeek Reasoning
**Codebase verified:** `scripts/nuzantara-sentinel.py`, `scripts/sentinel_lib/`, `scripts/dlq_autopilot.py`, `scripts/circuit_breaker.py`, `shared/escalations.json`, `~/.agent/decisions/dlq.json`
**Status:** LIVE DLQ has 41 entries — `comfyui_server` and `seo_auto_fixer` at 162 `autopilot_attempts`, status `abandoned`. Healing loop already in production. Phase 0 is URGENT.

---

## CHANGES FROM v3.1

### Critical corrections (blocking Phase 0 completeness)

| ID  | Source                                      | Finding                                                                                                                                                    | Change                                                                                                                              |
| --- | ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| C1  | Gemini Arch.                                | DLQ already has jobs at 162 `autopilot_attempts` with `abandoned` status — infinite healing loop IS IN PRODUCTION                                          | `max_attempts` enforcement with TERMINAL state moved from Phase 2 → **Phase 0**. Immediate fix required.                            |
| C2  | Source 1 + DeepSeek (confirming each other) | `shared/escalations.json` has dual physical writers (Pro + Air) — JSON race condition can produce malformed file                                           | **JSONL append-only** format adopted. See ADR-3.                                                                                    |
| C3  | Codex SRE                                   | `circuit_breaker.py` `_load()` + modify + `_atomic_save()` is TOCTOU — flock acquired only at write, not at read                                           | Fix: flock at read time (`_load_locked()`), held until save completes. Single transaction per mutation.                             |
| C4  | Codex SRE                                   | `retry_job()` in `repairer.py` relies on caller to enforce allowlist; no defense-in-depth inside the function itself                                       | Defense-in-depth: `retry_job()` validates `restart_cmd` against allowlist independently of caller.                                  |
| C5  | Codex SRE                                   | `allowed_cmds.txt` bypassable via path traversal (`python3 scripts/../../etc/...`)                                                                         | `os.path.realpath()` normalization + blocklist for shell metacharacters (`&&`, `;`, `                                               | `, `$()`) added to allowlist validator.                               |
| C6  | Codex SRE                                   | `fail_count_7d >= 1` on critical job generates 7 identical Telegram escalations per week                                                                   | `escalation_sent_at` field in state file + 4h cooldown.                                                                             |
| C7  | Codex SRE                                   | `HEALING_DISABLED=1` env var not inherited by LaunchAgent — flag has no effect in production                                                               | Replace with file flag `~/.agent/decisions/HEALING_DISABLED`.                                                                       |
| C8  | Gemini Arch.                                | Sentinel has no PID lock — if a healing cycle exceeds its cron interval, concurrent runs can corrupt state                                                 | `/tmp/nuzantara_sentinel.lock` with `LOCK_NB` added. Same pattern as `dlq_autopilot.py`.                                            |
| C9  | Gemini Arch.                                | No observability aggregator — cannot assess system health at a glance                                                                                      | `sentinel_status.json` written after every run (moved to Phase 1, not Phase 3).                                                     |
| C10 | Gemini Arch.                                | OpenClaw jobs are idempotent by design (restart = safe) — manual `repair_scope` classification wastes triage time                                          | Auto-classify `type=openclaw` as `repair_scope=LOCAL` in pre-classification script. Reduces manual backlog ~50–60%.                 |
| C11 | DeepSeek                                    | Decision tree has ambiguous double-trigger for `critical=true AND idempotent=true AND fail_count >= 3` — job enters both rule 2 (alert) and rule 3 (retry) | Explicit `elif` chains — mutually exclusive branches.                                                                               |
| C12 | DeepSeek                                    | `_failure_timestamps` has no pruning — unbounded growth confirmed by two review sources                                                                    | Inline pruning to 14 days on every write.                                                                                           |
| C13 | DeepSeek                                    | CSV/SSOT job registry has no integrity check — AI agent can silently corrupt `is_idempotent`                                                               | SHA256 checksum of registry file stored in `_registry_live.json`; verified before every Sentinel run.                               |
| C14 | DeepSeek                                    | Idempotency token uses date-level granularity — wrong for sub-daily jobs (RAG Canary every 6h)                                                             | Token granularity derived from job's nominal interval, not hardcoded to date.                                                       |
| C15 | Gemini Arch. + DeepSeek                     | LangGraph + Postgres (Phase 4) has WAL contention; SQLite also problematic under concurrent writers                                                        | **Drop LangGraph entirely.** Replace with `phase` field (`T0..T4                                                                    | TERMINAL`) in `circuit_breaker.py`. ~20 lines, zero new dependencies. |
| C16 | Gemini Arch. + DeepSeek                     | LLM (Exa/Claude) as **executor** in Phase 4 DLQ introduces non-determinism into a deterministic system                                                     | LLM role = **classifier/explain ONLY**. Flag `llm_suggested_only=true` on all LLM-derived actions. Execution remains deterministic. |
| C17 | DeepSeek                                    | "60% LOCAL" repair estimate is unverified. Realistic empirical estimate: 40–50%                                                                            | Pre-classification script moved to Phase 0 with instrumentation to measure actual rate.                                             |
| C18 | Codex SRE                                   | `watchdog cutoff 03:25` is absolute wall clock — should be relative to sentinel start (monotonic)                                                          | Cutoff becomes `start_time + MAX_DURATION_S`, not absolute time.                                                                    |
| C19 | Codex SRE                                   | Single-writer contracts in comments only — no runtime enforcement                                                                                          | `_writer` field added to JSON/JSONL state files for audit trail.                                                                    |
| C20 | Source 1 (original)                         | `doc_generator` auto-touching `CLAUDE.md` creates noisy git diffs                                                                                          | `doc_generator` targets `docs/AUTOMATIONS_REFERENCE.md` only — `CLAUDE.md` is human-only. See Phase 3 note.                         |
| C21 | Gemini Arch.                                | Phase 0 is acceleratable to 2 days given `circuit_breaker.py` is already ~correct (flock exists)                                                           | Timeline revised downward. Phase 0: 2 days. Phase 1: 3 days.                                                                        |

---

## System Overview

The Automation Autonomy System is a 4-tier self-healing loop running on the Pro/Air machine pair. It monitors all scheduled jobs (currently 31 in registry), detects failures, and escalates through tiers without human intervention:

```
Tier 0: OpenClaw gateway health + staleness check
Tier 1: Retry with exponential backoff (TRANSIENT)
Tier 2: Aider auto-fix (DETERMINISTIC, high-confidence pattern)
Tier 3: DLQ + Claude Code task file (low-confidence or Aider failed)
Tier 4: Zero alert (UNKNOWN)
```

**Components (production):**

- `scripts/nuzantara-sentinel.py` — main loop, runs every 5min via LaunchAgent
- `scripts/sentinel_lib/` — circuit breaker, classifier, repairer, alerter
- `scripts/dlq_autopilot.py` — DLQ processor, runs every 30min via LaunchAgent
- `scripts/circuit_breaker.py` — per-job state (root-level, separate from sentinel_lib version)
- `shared/escalations.json` — federation escalation bus (Pro ↔ Air)
- `~/.agent/decisions/dlq.json` — dead letter queue (41 entries live, 2 at 162 attempts)

---

## Phase 0 — Emergency Stabilization (2 days)

**Goal:** Stop the existing infinite healing loop, fix the two critical security issues, add PID lock, and instrument the system for Phase 1.

### Deliverable 0.1 — max_attempts enforcement + TERMINAL state (URGENT — production burning)

**Problem:** `dlq_autopilot.py` has `MAX_ATTEMPTS = 3` but the check is `if attempts >= MAX_ATTEMPTS: escalate_to_claude_code(entry, None); return "abandoned"` — entries with `abandoned` status are still kept in the queue and re-processed on the next cycle (see `updated_queue.append(entry)` block). Result: `comfyui_server` and `seo_auto_fixer` are at 162 attempts.

**Fix:**

1. Add `status == "TERMINAL"` check as the **first** condition in `process_entry()`. If `status == "TERMINAL"`, skip entirely (do not increment, do not re-escalate).
2. When `attempts >= MAX_ATTEMPTS`, set `entry["status"] = "TERMINAL"` (not `"abandoned"`), keep in queue for audit visibility, send **one** Telegram CRITICAL alert with explicit instruction to remove manually or via `dlq clear <job>`.
3. Add `max_attempts` as a per-job registry override (default: 10, matching Gemini's recommendation). `comfyui_server` and `seo_auto_fixer` should have `max_attempts: 5` given their known instability.
4. Add `first_abandoned_at` timestamp on first TERMINAL transition for audit.

**Files:** `scripts/dlq_autopilot.py`, `~/.agent/decisions/job_registry.json`

### Deliverable 0.2 — PID lock for Sentinel

**Problem:** `nuzantara-sentinel.py` has no concurrency guard. If a healing cycle (Tier 2 Aider, Tier 3 escalation) takes longer than 5min, the next LaunchAgent fire starts a second instance. Two sentinel instances writing to `circuit_breakers.json` simultaneously can produce corrupt state.

**Fix:** `/tmp/nuzantara_sentinel.lock` using `fcntl.LOCK_EX | fcntl.LOCK_NB`. Pattern identical to `dlq_autopilot.py`'s `acquire_lock()`. If lock is held and is older than `LOCK_STALE_AGE_S=600` (10min), remove and retry once.

**File:** `scripts/nuzantara-sentinel.py` (wrap `run_sentinel()` call in `main`)

### Deliverable 0.3 — circuit_breaker TOCTOU fix (C3)

**Problem:** `_load()` reads the file without holding the lock. Between `_load()` and `_atomic_save()`, another process can write. The flock in `_atomic_save()` protects the write but not the read-modify-write sequence.

**Fix:** Add `_load_locked(f)` that accepts an already-open, already-locked file descriptor. Callers that need atomic read-modify-write (`record_success`, `record_failure`, `_set_state`) open the file with `LOCK_EX`, read, modify, then call `_atomic_save_to_fd()` on the same fd without releasing the lock between operations.

**File:** `scripts/sentinel_lib/circuit_breaker.py`

### Deliverable 0.4 — CSV registry integrity check (C13)

**Problem:** `job_registry.json` is the SSOT for `is_idempotent`, `critical`, `repair_scope`, and `max_attempts`. An AI agent (Aider, Codex) that modifies this file can silently change these flags, causing wrong decision tree branches.

**Fix:**

- Compute SHA256 of `job_registry.json` on every Sentinel startup.
- Compare against `~/.agent/decisions/_registry_checksum.json`.
- If mismatch: send Telegram WARNING with the diff (field-level, not raw bytes), update checksum, continue (do not abort — registry change may be intentional).
- Log checksum verification to `SENTINEL_LOG` (JSONL).

**File:** `scripts/nuzantara-sentinel.py` (`load_registry()` function)

### Deliverable 0.5 — OpenClaw pre-classification script (C10, C17)

**Problem:** All `type=openclaw` jobs enter the same triage flow as shell jobs, consuming DLQ autopilot slots. OpenClaw job restarts are idempotent by design: `openclaw cron run <id>` is safe to call repeatedly.

**Fix:** Python script `scripts/preclassify_jobs.py` that:

1. Reads `job_registry.json`
2. For all `type=openclaw` jobs: sets `repair_scope=LOCAL` and `is_idempotent=true` if not already set
3. Emits a report of how many entries were auto-classified
4. Records empirical `repair_scope` distribution to `~/.agent/decisions/repair_scope_stats.json` for validation of the "40–50% LOCAL" estimate

Run once (Phase 0) and then on every registry modification (pre-commit hook).

**File:** `scripts/preclassify_jobs.py` (new)

### Deliverable 0.6 — HEALING_DISABLED file flag (C7)

**Problem:** `HEALING_DISABLED=1` environment variable is not inherited by LaunchAgent processes on macOS. The flag exists in code but has no effect in production.

**Fix:** Check for presence of `~/.agent/decisions/HEALING_DISABLED` (file, not env var). If present, Sentinel skips all Tier 1-3 actions and only logs. Create/remove via:

```bash
touch ~/.agent/decisions/HEALING_DISABLED    # disable
rm ~/.agent/decisions/HEALING_DISABLED       # re-enable
```

**Files:** `scripts/nuzantara-sentinel.py`, `scripts/dlq_autopilot.py`

---

## Phase 1 — Decision Tree Hardening + Observability (3 days)

**Goal:** Fix all logic flaws in the decision tree, add escalation deduplication, and make the system observable via a status JSON.

### Deliverable 1.1 — Decision tree elif correction (C11)

**Problem:** The current decision tree for `critical=true AND idempotent=true AND fail_count >= 3` can enter both the escalation branch (rule 2) and the auto-retry branch (rule 3). The tree uses `if / if` rather than `if / elif`.

**Corrected decision tree (pseudocode):**

```
function process_job(job, state):
    if circuit == OPEN:
        return skipped_circuit_open

    if status == "ok":
        record_success(); return healthy

    if status == "running":
        return running  # never interfere

    if optional and status in (failed, stale):
        return skipped_optional

    # FAILURE PATH — mutually exclusive elif chain
    classify(error)

    if HEALING_DISABLED:
        log + alert; return healing_disabled

    elif type=openclaw and openclaw_is_down:
        return suppressed_gateway_down

    elif failure_type == TRANSIENT and retry_attempt < MAX_RETRIES:
        # Tier 1: retry
        ...

    elif failure_type == DETERMINISTIC and fix_pattern.confidence >= 0.85 and not critical:
        # Tier 2: Aider fix (only for non-critical jobs)
        ...

    elif critical == true and not is_idempotent:
        # Tier 3: immediate alert + DLQ, NO auto-retry
        escalate_to_dlq(); send_alert(CRITICAL); return escalated_critical_non_idempotent

    elif critical == true and is_idempotent and fail_count >= 3:
        # Tier 1 with escalation: retry + alert (not Tier 2)
        retry(); send_alert(WARNING); return retried_with_alert

    else:
        # Tier 3/4: DLQ
        add_to_dlq(); return escalated
```

**Files:** `scripts/nuzantara-sentinel.py` (`process_job()`)

### Deliverable 1.2 — Escalation cooldown (C6)

**Problem:** `fail_count_7d >= 1` on a critical job sends a Telegram alert every Sentinel cycle (every 5min). Over 7 days this is 2016 identical messages.

**Fix:** Add `escalation_sent_at: float` to the per-job state file. Before sending any Telegram alert for a job, check `time.time() - state.get("escalation_sent_at", 0) > ESCALATION_COOLDOWN_S` where `ESCALATION_COOLDOWN_S = 14400` (4h). Update `escalation_sent_at` on every sent alert.

**Files:** `scripts/nuzantara-sentinel.py`, `scripts/sentinel_lib/alerter.py`

### Deliverable 1.3 — sentinel_status.json aggregator (C9)

**Problem:** No single file describes the current health of the automation system. Diagnosing system state requires reading JSONL logs and individual state files.

**Fix:** After every `run_sentinel()` completion, write `~/.agent/decisions/sentinel_status.json`:

```json
{
  "ts": 1743400000,
  "generated_at": "2026-03-31T12:00:00Z",
  "jobs_total": 31,
  "jobs_healthy": 18,
  "jobs_circuit_open": 3,
  "jobs_circuit_terminal": 2,
  "jobs_healing": 4,
  "jobs_suppressed": 4,
  "dlq_entries": 41,
  "dlq_terminal": 8,
  "healing_actions_24h": 12,
  "openclaw_gateway": "healthy",
  "last_sentinel_duration_s": 4.2,
  "writer": "sentinel"
}
```

This file is the single observable for external dashboards, MCP tools, and the `get_agents_status` endpoint.

**Files:** `scripts/nuzantara-sentinel.py`

### Deliverable 1.4 — idempotency token granularity fix (C14)

**Problem:** Idempotency deduplication uses `date.today()` as token. For jobs running multiple times per day (RAG Canary every 6h, Drive Watchdog every 6h), all runs within the same calendar day use the same token and are deduplicated as duplicates.

**Fix:** Token = `f"{job_id}:{int(time.time() // nominal_interval_s)}"` where `nominal_interval_s` comes from the registry field `interval_s`. If `interval_s` is not set, fallback to 86400 (daily). This makes the token a "run slot" identifier rather than a calendar date.

**Files:** `scripts/sentinel_lib/repairer.py` (or wherever dedup is applied)

### Deliverable 1.5 — \_writer audit field (C19)

**Problem:** Single-writer contracts are documented only in comments. Any process can write to any JSON state file without leaving evidence.

**Fix:** Add `"_writer": "<process_name>"` to every JSON/JSONL write. Process names: `"sentinel"`, `"dlq_autopilot"`, `"circuit_breaker"`, `"preclassify"`. No enforcement (would require a broker), but provides audit trail for post-incident analysis. Log a WARNING if a file is read with a `_writer` field that doesn't match the expected writer for that file.

### Deliverable 1.6 — \_failure_timestamps pruning (C12)

**Problem:** `_failure_timestamps` list in circuit breaker state grows indefinitely. Confirmed by two independent review sources. At 5min intervals with persistent failures, this accumulates 8640 entries per 30 days per job.

**Fix:** Inline pruning on every write: `data[job]["_failure_timestamps"] = [t for t in timestamps if time.time() - t <= 14 * 86400]`. No separate pruning job needed — happens atomically with every `record_failure()` call.

**File:** `scripts/sentinel_lib/circuit_breaker.py`

### Deliverable 1.7 — monotonic watchdog cutoff (C18)

**Problem:** Sentinel has a cutoff at absolute wall clock `03:25` for certain batch operations. If the machine clock is adjusted or if the sentinel is started at different times (e.g., after a crash restart), the cutoff fires at unexpected times.

**Fix:** Replace absolute time checks with `start_time + MAX_RUN_DURATION_S` using `time.monotonic()`. Each Sentinel run computes `deadline = start_monotonic + MAX_DURATION_S` and checks `time.monotonic() < deadline` before each job iteration.

---

## Phase 2 — Security Hardening + allowlist enforcement (2 days)

**Goal:** Fix the two security-class vulnerabilities (path traversal, command injection) and close the remaining attack surface.

### Deliverable 2.1 — Path traversal fix in allowed_cmds.txt (C5)

**Problem:** A command like `python3 scripts/../../etc/passwd` passes the allowlist prefix check (`python3 scripts/` matches) but resolves outside the allowed directory.

**Fix:**

1. `os.path.realpath()` normalization on the command before allowlist check.
2. Block all shell metacharacters: `&&`, `||`, `;`, `|`, `$()`, backtick, `>`, `<`, `>>` — these enable chaining of secondary commands.
3. Pin the allowed root: realpath must start with `NUZANTARA_ROOT` or `/usr/bin`, `/opt/homebrew/bin`.
4. Harden `allowed_cmds.txt` with mode `0o444` (read-only) on first load — AI agents cannot modify it during a session.

**Files:** `scripts/sentinel_lib/repairer.py`, `~/.agent/decisions/allowed_cmds.txt`

### Deliverable 2.2 — Defense-in-depth in retry_job() (C4)

**Problem:** `retry_job()` trusts the caller to have validated `restart_cmd`. If the caller has a bug or is called directly from a test, the validation is bypassed.

**Fix:** `retry_job()` performs its own allowlist + realpath check before executing. If validation fails, return `(False, "command rejected by retry_job allowlist")` — do not raise, to preserve caller error handling.

**File:** `scripts/sentinel_lib/repairer.py`

### Deliverable 2.3 — escalations.json → JSONL (C2, ADR-3)

**Problem:** `shared/escalations.json` is written by both Pro and Air. With concurrent writes, the file can become malformed JSON (partial write from one machine overwrites the other's write).

**Fix:** Rename to `shared/escalations.jsonl`. Each escalation is one JSON object per line. Writers append atomically (open with `O_APPEND`, write a single line terminated by `\n`). Readers read all lines, parse each as JSON, filter by `status != "resolved"`. No locking needed — `O_APPEND` on a local filesystem is atomic for writes smaller than PIPE_BUF (4096 bytes on macOS).

Backward compatibility: during Phase 2, a migration script converts the existing JSON format to JSONL. Both `nuzantara-sentinel.py` and any Air-side writer are updated simultaneously.

**Files:** `shared/escalations.jsonl` (new), `scripts/nuzantara-sentinel.py`, any Air-side scripts that write escalations

---

## Phase 3 — Documentation Automation (2 days, low risk)

**Goal:** Keep `docs/AUTOMATIONS_REFERENCE.md` auto-updated without polluting `CLAUDE.md`.

### Deliverable 3.1 — doc_generator scope restriction (C20)

The doc_generator automation (if/when built) must target **only** `docs/AUTOMATIONS_REFERENCE.md`. `CLAUDE.md` is a human-maintained file checked into git. Auto-generation of `CLAUDE.md` creates noisy diffs that obscure intentional manual changes and confuses AI agents reading the file.

Rule: `CLAUDE.md` is in the write-blocklist for all automated doc generators, alongside `zantara_core.py`, `fly.toml`, `.env*`.

### Deliverable 3.2 — AUTOMATIONS_REFERENCE.md structure

`docs/AUTOMATIONS_REFERENCE.md` should be auto-generated from `job_registry.json` + live `sentinel_status.json`. Fields: job name, type, schedule, repair_scope, is_idempotent, critical, current circuit state, last run status.

This document is the single source of truth for "what is the automation system doing right now" — suitable for reading by both AI agents and humans.

**Note:** The existing `docs/AUTOMATIONS_REFERENCE.md` (manual) is superseded. Archive it as `docs/archive/AUTOMATIONS_REFERENCE_manual_2026-03-31.md`.

---

## Phase 4 — DLQ Intelligence Upgrade (3 days)

**Goal:** Make DLQ processing smarter without introducing non-determinism or new infrastructure dependencies.

### Deliverable 4.1 — Drop LangGraph, add phase field to circuit_breaker (C15)

**Problem:** The v3.1 plan proposed LangGraph + Postgres for tracking the progression of a job through T0→T4 healing phases. Both LangGraph and Postgres add WAL contention risk. SQLite is also problematic under concurrent writer conditions.

**Solution:** Add a `phase` field to the existing `circuit_breakers.json` per-job entry. Values: `T0` (healthy), `T1` (retry attempted), `T2` (aider dispatched), `T3` (in DLQ), `T4` (escalated to Claude Code), `TERMINAL` (max_attempts reached).

```json
{
  "comfyui_server": {
    "state": "OPEN",
    "failures": 3,
    "opened_at": 1743300000,
    "phase": "TERMINAL",
    "first_terminal_at": 1743300000
  }
}
```

This requires ~20 lines of changes to `circuit_breaker.py` and `nuzantara-sentinel.py`. Zero new dependencies.

### Deliverable 4.2 — LLM as classifier/explainer only (C16)

**Problem:** The v3.1 plan allowed LLM to suggest execution paths (executor role). This introduces non-determinism: two identical DLQ entries might get different fix suggestions on different runs.

**Constraint for Phase 4:**

- `claude_reason()` in `dlq_autopilot.py` returns classification and explanation only.
- The `fix_type` field from LLM output maps to a deterministic execution rule (same as `FIX_PATTERNS` dict in `classifier.py`).
- LLM output sets `llm_suggested_only=true` on the suggestion object. Actual execution uses pre-defined handlers, never raw LLM output.
- This preserves the existing `CONFIDENCE_RETRY` / `CONFIDENCE_AIDER` thresholds as deterministic gates.

**File:** `scripts/dlq_autopilot.py` (`claude_reason()`, `process_entry()`)

### Deliverable 4.3 — DLQ entry lifecycle dashboard

Extend `sentinel_status.json` with DLQ phase distribution:

```json
"dlq_phase_distribution": {
  "T1": 3,
  "T2": 1,
  "T3": 12,
  "T4": 5,
  "TERMINAL": 8,
  "abandoned_legacy": 12
}
```

`abandoned_legacy` is the count of entries with the old `abandoned` status that predate the TERMINAL system — these should be manually triaged and either cleared or re-classified in Phase 0.

---

## Risk Register (updated)

| ID  | Risk                                                             | Severity | Likelihood | Mitigation                                        | Owner   | Phase |
| --- | ---------------------------------------------------------------- | -------- | ---------- | ------------------------------------------------- | ------- | ----- |
| R1  | Infinite healing loop (CONFIRMED IN PROD)                        | CRITICAL | CONFIRMED  | TERMINAL state + max_attempts (Phase 0.1)         | Phase 0 | 0     |
| R2  | Healing loop — PID lock missing                                  | HIGH     | HIGH       | `/tmp/sentinel.lock` with LOCK_NB (Phase 0.2)     | Phase 0 | 0     |
| R3  | CSV registry integrity corruption by AI agent                    | HIGH     | MEDIUM     | SHA256 checksum + Telegram diff alert (Phase 0.4) | Phase 0 | 0     |
| R4  | TOCTOU race in circuit_breaker.py                                | HIGH     | LOW        | Flock held from read through write (Phase 0.3)    | Phase 0 | 0     |
| R5  | Command injection via allowed_cmds.txt path traversal            | HIGH     | LOW        | realpath + metachar blocklist (Phase 2.1)         | Phase 2 | 2     |
| R6  | escalations.json dual-writer JSON corruption                     | HIGH     | MEDIUM     | JSONL append-only (Phase 2.3)                     | Phase 2 | 2     |
| R7  | Escalation alert flooding (2016 messages/week)                   | MEDIUM   | HIGH       | 4h cooldown per job per alert (Phase 1.2)         | Phase 1 | 1     |
| R8  | HEALING_DISABLED has no effect in LaunchAgent                    | MEDIUM   | CONFIRMED  | File flag instead of env var (Phase 0.6)          | Phase 0 | 0     |
| R9  | Sub-daily job dedup broken (idempotency token)                   | MEDIUM   | HIGH       | Interval-based token (Phase 1.4)                  | Phase 1 | 1     |
| R10 | LLM executor introduces non-determinism                          | MEDIUM   | MEDIUM     | LLM = classify/explain only (Phase 4.2)           | Phase 4 | 4     |
| R11 | \_failure_timestamps unbounded growth                            | LOW      | HIGH       | 14-day inline pruning (Phase 1.6)                 | Phase 1 | 1     |
| R12 | Watchdog absolute cutoff fires at wrong time after restart       | LOW      | LOW        | Monotonic deadline (Phase 1.7)                    | Phase 1 | 1     |
| R13 | OpenClaw jobs classified as REMOTE repair — clogs manual backlog | LOW      | CONFIRMED  | Auto-classify openclaw as LOCAL (Phase 0.5)       | Phase 0 | 0     |

---

## Critical Architecture Decisions (updated)

### ADR-1: Circuit Breaker State File — Single Writer Per File

**Decision:** Each state JSON file has one designated writer (field `_writer`). Cross-process writes go through a message-passing layer (currently JSONL append for escalations; file-per-job for sentinel state).
**Rationale:** Eliminates TOCTOU races without requiring a broker process.

### ADR-2: TERMINAL State — Hard Stop

**Decision:** A job that reaches `max_attempts` transitions to `TERMINAL`. It is never automatically processed again. Removal from DLQ requires explicit human action (`dlq clear <job>`) or a future scheduled sweep.
**Rationale:** `abandoned` status re-entering the processing loop is the root cause of the 162-attempt entries currently in production. TERMINAL must be a true dead end.

### ADR-3: escalations.jsonl — Append-Only JSONL

**Decision:** `shared/escalations.jsonl` replaces `shared/escalations.json`. Writers use `O_APPEND`. Readers stream all lines and filter.
**Rationale:** `O_APPEND` on POSIX is atomic for writes < PIPE_BUF. Eliminates the dual-writer JSON corruption risk without requiring a lock file or broker.

### ADR-4: LangGraph Dropped

**Decision:** No LangGraph, no SQLite for job phase tracking. `phase` field in `circuit_breakers.json` is sufficient.
**Rationale:** LangGraph adds a dependency and WAL contention risk for what is 20 lines of state machine logic. The existing `circuit_breaker.py` already has the right structure.

### ADR-5: LLM Role = Classify Only

**Decision:** LLM output (from `claude_reason()` or `classify_with_llm()`) may influence classification and explain suggestions to the human reviewer, but may never directly trigger execution. Execution is always routed through deterministic handlers from `FIX_PATTERNS`.
**Rationale:** A non-deterministic executor in an autonomous healing loop can mask systemic errors, retry the wrong fix, or interact badly with the Aider executor path.

### ADR-6: HEALING_DISABLED = File Flag

**Decision:** `~/.agent/decisions/HEALING_DISABLED` (presence of file) disables all Tier 1-3 actions system-wide. Env var `HEALING_DISABLED` is deprecated.
**Rationale:** LaunchAgent on macOS does not inherit shell environment variables. File flags work reliably regardless of process ancestry.

---

## Implementation Timeline

| Phase       | Duration | Prerequisite                                     | Deliverables                                                                                                                                               |
| ----------- | -------- | ------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Phase 0** | 2 days   | —                                                | 0.1 (TERMINAL), 0.2 (PID lock), 0.3 (TOCTOU), 0.4 (registry checksum), 0.5 (preclassify), 0.6 (HEALING_DISABLED flag)                                      |
| **Phase 1** | 3 days   | Phase 0 complete                                 | 1.1 (elif decision tree), 1.2 (cooldown), 1.3 (sentinel_status.json), 1.4 (idempotency token), 1.5 (\_writer field), 1.6 (pruning), 1.7 (monotonic cutoff) |
| **Phase 2** | 2 days   | Phase 1 complete                                 | 2.1 (path traversal), 2.2 (retry_job defense-in-depth), 2.3 (JSONL escalations)                                                                            |
| **Phase 3** | 2 days   | Phase 0 complete (can run parallel to Phase 1-2) | 3.1 (doc_generator scope), 3.2 (AUTOMATIONS_REFERENCE.md auto-gen)                                                                                         |
| **Phase 4** | 3 days   | Phase 1 complete                                 | 4.1 (phase field, drop LangGraph), 4.2 (LLM classify-only), 4.3 (DLQ dashboard)                                                                            |

**Total: 12 days elapsed (7 days net, with Phase 3 parallel)**

---

## Verification Criteria

Each phase is complete when:

- **Phase 0:** `comfyui_server` and `seo_auto_fixer` show `phase=TERMINAL` in circuit_breakers.json; no new Telegram alerts for these jobs; Sentinel starts with PID lock visible in `/tmp/nuzantara_sentinel.lock`
- **Phase 1:** `sentinel_status.json` exists and updates every 5min; no duplicate Telegram alerts within 4h for same job; RAG Canary 6h runs use distinct idempotency tokens
- **Phase 2:** `python3 -c "from scripts.sentinel_lib.repairer import retry_job; ok, msg = retry_job('python3 ../../etc/passwd'); assert not ok"` returns `False`; escalations.jsonl accumulates append-only entries with no JSON parse errors after concurrent Pro+Air writes
- **Phase 3:** `git diff --name-only HEAD | grep CLAUDE.md` returns empty after a doc_generator run
- **Phase 4:** `circuit_breakers.json` contains `phase` field for all jobs; `dlq_autopilot.py` `claude_reason()` output sets `llm_suggested_only=true` on all returned dicts

---

_Plan v3.2 synthesized from 5 independent review sources. Codebase state verified 2026-03-31._
_Next review: after Phase 0 completion._
