# Automation Autonomy System — Plan v3.3

**Date:** 2026-03-31
**Reviewed by:** Claude Code (orchestrator) · Codex SRE · Gemini Architecture · DeepSeek Reasoning (Round 2)
**Codebase verified:** `scripts/nuzantara-sentinel.py`, `scripts/sentinel_lib/`, `scripts/dlq_autopilot.py`, `scripts/circuit_breaker.py`, `shared/escalations.json`, `~/.agent/decisions/dlq.json`
**Status:** LIVE DLQ has 41 entries — `comfyui_server` and `seo_auto_fixer` at 162 `autopilot_attempts`, status `abandoned`. Healing loop already in production. Phase 0 is URGENT.

---

## CHANGES FROM v3.2

### Critical corrections from Round 2 review

| ID               | Source                                       | Finding                                                                                                                                                                                                                   | Change in v3.3                                                                                                                                                                                                |
| ---------------- | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| N1/NP-1/NC-1     | Codex + Gemini + DeepSeek (triple-confirmed) | `O_APPEND` on `escalations.jsonl` is atomic locally but NOT cross-machine — Pro and Air write to separate git-synced filesystem copies, linearization depends on git-sync, not on `O_APPEND`                              | Replace single `escalations.jsonl` with per-machine files `escalations_pro.jsonl` / `escalations_air.jsonl`. Merge at read time. No cross-machine lock required. ADR-3 updated.                               |
| N2/NC-2          | Codex + DeepSeek (confirmed)                 | Registry checksum mismatch "warn + update + continue" turns integrity gate into a notification system. An agent can corrupt `is_idempotent`, system sends 1 warning, updates checksum, proceeds with compromised registry | **HALT + Telegram CRITICAL on mismatch**. Resume only after human confirms via `~/.agent/decisions/REGISTRY_OVERRIDE` file. Deliverable 0.4 rewritten. ADR-7 added.                                           |
| N3               | Codex                                        | `max_attempts` in `job_registry.json` shares the same unprotected registry — if N2 is correctly resolved (HALT on mismatch), N3 is automatically resolved                                                                 | No separate action needed. Noted as resolved-by-N2 in risk register.                                                                                                                                          |
| NP-2             | Gemini                                       | `preclassify_jobs.py` modifies `job_registry.json` → next Sentinel run detects checksum mismatch → false HALT on every commit                                                                                             | `preclassify_jobs.py` must recompute and update `_registry_checksum.json` as the last step of its own execution. Deliverable 0.5 updated.                                                                     |
| NP-3             | Gemini                                       | `phase` field in `circuit_breakers.json` not reset on `OPEN→CLOSED` transition — recovered job keeps `phase=T3` indefinitely                                                                                              | `record_success()` resets `phase` to `T0`. `_set_phase()` enforces transition matrix. Deliverable 4.1 updated.                                                                                                |
| PARTIAL C16      | DeepSeek                                     | `llm_suggested_only=true` flag has no enforcement point in `process_entry()` — LLM action could be executed despite the flag                                                                                              | Add explicit guard in `process_entry()`: if `llm_suggested_only=True`, log suggestion and skip to deterministic decision tree. Never execute. Deliverable 4.2 hardened.                                       |
| PARTIAL C17      | DeepSeek                                     | `preclassify_jobs.py` auto-classifies openclaw jobs but `automation_type=github_actions\|webhook\|pg_trigger` jobs remain unclassified as "suggested"                                                                     | Add deterministic rule: `automation_type` in `{github_actions, webhook, pg_trigger}` → `repair_scope=OBSERVE_ONLY` automatically. Deliverable 0.5 updated.                                                    |
| PARTIAL C5       | Codex                                        | `validate_restart_cmd()` blocklist missing `\x00`, `\n`, `\r` — null byte and newline injection can bypass shell-level guards                                                                                             | Add `\x00`, `\n`, `\r` to the metacharacter blocklist. Deliverable 2.1 updated.                                                                                                                               |
| PARTIAL C19      | Codex                                        | `_writer` field has no runtime enforcement — accepted as design choice                                                                                                                                                    | Explicitly documented in ADR-1 that enforcement is via code review only, not runtime.                                                                                                                         |
| Gemini Finding 2 | Gemini Round 1                               | No deliverable existed for `dlq clear <job>` CLI command despite being referenced in ADR-2 and Verification Criteria                                                                                                      | Add Deliverable 0.7: `dlq_autopilot.py clear <job_id>` command that removes `status=TERMINAL` entries from `dlq.json`.                                                                                        |
| Gemini Finding 4 | Gemini Round 1                               | No transition guard for retrograde phase transitions — `phase` could regress without explicit authorization                                                                                                               | Add transition matrix in `_set_phase()`. Valid forward: `T0→T1→T2→T3→T4→TERMINAL`. Authorized retrograde: only `record_success()` → `T0`. Implemented as `assert` in `_set_phase()`. Deliverable 4.1 updated. |
| Gemini Finding 7 | Gemini Round 1                               | Phase 0 does not mention Air-side coordination — deployments were Pro-only in the plan                                                                                                                                    | All Phase 0 deliverables must be deployed on **both** machines via `git pull` + `launchd reload`. Explicit note added to Phase 0.                                                                             |

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
- `shared/escalations_pro.jsonl` + `shared/escalations_air.jsonl` — federation escalation bus (per-machine, merged at read)
- `~/.agent/decisions/dlq.json` — dead letter queue (41 entries live, 2 at 162 attempts)

---

## Phase 0 — Emergency Stabilization (2 days)

**Goal:** Stop the existing infinite healing loop, fix the two critical security issues, add PID lock, and instrument the system for Phase 1.

**DEPLOYMENT NOTE (Gemini Finding 7):** All Phase 0 deliverables must be deployed on **both** Pro and Air machines. After merging to `main` on Pro, Air receives the changes via the git post-commit auto-pull hook. Verify on Air with `ssh air 'launchd list | grep sentinel'` and reload any affected LaunchAgents with `ssh air 'launchctl unload/load <plist>'`.

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

### Deliverable 0.4 — CSV registry integrity check — HALT on mismatch (C13, N2, NC-2 — HARDENED)

**Problem (v3.2):** The original fix was "warn + update + continue" on SHA256 mismatch. This was identified by Codex SRE (N2) and DeepSeek (NC-2) as transforming an integrity gate into a notification system. An AI agent (Aider, Codex) that modifies `job_registry.json` to change `is_idempotent` or `repair_scope` would generate one warning, have the checksum silently updated, and then proceed with a compromised registry — wrong decision tree branches for 5000+ client-affecting jobs.

**Fix (v3.3 — HALT behavior):**

1. Compute SHA256 of `job_registry.json` on every Sentinel startup.
2. Compare against `~/.agent/decisions/_registry_checksum.json`.
3. **If mismatch:**
   - Send Telegram **CRITICAL** alert with field-level diff (not raw bytes).
   - Write `~/.agent/decisions/REGISTRY_HALT` marker file with timestamp and diff summary.
   - **HALT sentinel execution** — do not proceed to job processing.
   - Log halt to `SENTINEL_LOG` (JSONL) with `reason=registry_integrity_mismatch`.
4. **Resume condition:** Human creates `~/.agent/decisions/REGISTRY_OVERRIDE` file (manually, after reviewing the diff). On next Sentinel run, if `REGISTRY_OVERRIDE` exists:
   - Update `_registry_checksum.json` to the new hash.
   - Delete `REGISTRY_HALT` and `REGISTRY_OVERRIDE`.
   - Proceed normally.
   - Log `reason=registry_override_accepted` to `SENTINEL_LOG`.
5. **First-run bootstrap:** If `_registry_checksum.json` does not exist, compute and write it silently (no alert, no halt) — this is the initial trusted state.

**Files:** `scripts/nuzantara-sentinel.py` (`load_registry()` function), `~/.agent/decisions/_registry_checksum.json`

**Operational notes (Round 3 — Codex + Gemini):**

- If `REGISTRY_HALT` activates on Air, the operator must SSH to Air and create `~/.agent/decisions/REGISTRY_OVERRIDE` manually. Remote creation via the Pro→Air post-commit hook is not sufficient because the hook only pulls git changes, not arbitrary file creation.
- If `REGISTRY_HALT` activates during a legitimate git pull window (Pro committed, Air has not yet pulled), this is a false halt: the registry on Air is temporarily behind. The false halt auto-resolves after the next git pull (within 5 minutes via the post-commit hook) — the incoming pull will update `job_registry.json` and if the updated hash matches what Pro intended, operator can then create `REGISTRY_OVERRIDE`. No code change needed for this case — the 5-minute auto-pull window is the resolution path. Document this in runbooks.

### Deliverable 0.5 — OpenClaw + non-OpenClaw pre-classification script (C10, C17, NP-2, PARTIAL C17)

**Problem:** All `type=openclaw` jobs enter the same triage flow as shell jobs, consuming DLQ autopilot slots. OpenClaw job restarts are idempotent by design. Additionally, `automation_type=github_actions|webhook|pg_trigger` jobs have no deterministic classification for `repair_scope`. Finally (NP-2), running `preclassify_jobs.py` modifies `job_registry.json` — without updating the checksum, the next Sentinel run would detect a mismatch and HALT (a false positive introduced by N2 fix).

**Fix:** Python script `scripts/preclassify_jobs.py` that:

1. Reads `job_registry.json`.
2. For all `type=openclaw` jobs: sets `repair_scope=LOCAL` and `is_idempotent=true` if not already set.
3. For all jobs with `automation_type` in `{github_actions, webhook, pg_trigger}`: sets `repair_scope=OBSERVE_ONLY` deterministically (matching the v3.1 original spec).
4. Emits a report of how many entries were auto-classified.
5. Records empirical `repair_scope` distribution to `~/.agent/decisions/repair_scope_stats.json` for validation of the "40–50% LOCAL" estimate.
6. **As the final step:** recomputes SHA256 of the (now-modified) `job_registry.json` and updates `~/.agent/decisions/_registry_checksum.json`. This prevents a false HALT on the next Sentinel run caused by the preclassify modifications.

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

### Deliverable 0.7 — `dlq clear <job_id>` CLI command (Gemini Finding 2)

**Problem:** ADR-2 and the Verification Criteria both reference `dlq clear <job>` as the mechanism for manually removing TERMINAL entries, but no such CLI deliverable was defined in v3.1 or v3.2. The command was described as a future intent with no implementation path.

**Fix:** Add a `clear` subcommand to `scripts/dlq_autopilot.py`:

```bash
python scripts/dlq_autopilot.py clear <job_id>
```

Behavior:

- Loads `~/.agent/decisions/dlq.json`.
- Finds entry with matching `job_id`.
- Refuses to clear if `status != "TERMINAL"` (guard: cannot clear an actively-processing entry).
- Removes the entry from the queue.
- Writes updated `dlq.json`.
- Logs the removal to `SENTINEL_LOG` with `action=dlq_clear_manual`, `operator=human` (distinguished from automated removal).
- Prints confirmation: `Cleared TERMINAL entry: <job_id> (was at <attempts> attempts)`.

**File:** `scripts/dlq_autopilot.py`

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

**Fix:** Add `"_writer": "<process_name>"` to every JSON/JSONL write. Process names: `"sentinel"`, `"dlq_autopilot"`, `"circuit_breaker"`, `"preclassify"`. No runtime enforcement (by design — see ADR-1), but provides audit trail for post-incident analysis. Log a WARNING if a file is read with a `_writer` field that doesn't match the expected writer for that file.

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

### Deliverable 2.1 — Path traversal fix in allowed_cmds.txt (C5, PARTIAL C5 — complete fix)

**Problem (v3.2):** A command like `python3 scripts/../../etc/passwd` passes the allowlist prefix check (`python3 scripts/` matches) but resolves outside the allowed directory. The v3.2 fix added `&&`, `||`, `;`, `|`, `$()`, backtick, `>`, `<`, `>>` to the blocklist but omitted null byte (`\x00`), newline (`\n`), and carriage return (`\r`) — which can bypass shell-level guards and are confirmed injection vectors (Codex Round 2, PARTIAL C5).

**Fix (v3.3 — complete):**

1. `os.path.realpath()` normalization on the command before allowlist check.
2. Block all shell metacharacters: `&&`, `||`, `;`, `|`, `$()`, backtick, `>`, `<`, `>>`, **plus** `\x00` (null byte), `\n` (newline), `\r` (carriage return).
3. Pin the allowed root: realpath must start with `NUZANTARA_ROOT` or `/usr/bin`, `/opt/homebrew/bin`.
4. Harden `allowed_cmds.txt` with mode `0o444` (read-only) on first load — AI agents cannot modify it during a session.

**Files:** `scripts/sentinel_lib/repairer.py`, `~/.agent/decisions/allowed_cmds.txt`

### Deliverable 2.2 — Defense-in-depth in retry_job() (C4)

**Problem:** `retry_job()` trusts the caller to have validated `restart_cmd`. If the caller has a bug or is called directly from a test, the validation is bypassed.

**Fix:** `retry_job()` performs its own allowlist + realpath check before executing. If validation fails, return `(False, "command rejected by retry_job allowlist")` — do not raise, to preserve caller error handling.

**File:** `scripts/sentinel_lib/repairer.py`

### Deliverable 2.3 — escalations: per-machine JSONL files (C2, N1, NP-1, NC-1 — ADR-3 REVISED)

**Problem (v3.2):** `shared/escalations.jsonl` was a single file with `O_APPEND` claimed as atomic. Three independent reviewers (Codex N1, Gemini NP-1, DeepSeek NC-1) identified that `O_APPEND` atomicity applies to a single local filesystem — but Pro and Air each have a local copy of this file synchronized via git. There is no shared filesystem. A write on Pro and a write on Air are both locally atomic, but they target different physical files. After git-sync, a merge conflict or interleaved append is possible if both machines write between sync cycles.

**Fix (v3.3 — per-machine files):**

- `shared/escalations_pro.jsonl` — written exclusively by Pro. Air never writes this file.
- `shared/escalations_air.jsonl` — written exclusively by Air. Pro never writes this file.
- Each file uses `O_APPEND` for local atomicity (writes < PIPE_BUF = 4096 bytes, guaranteed atomic on macOS).
- **Readers** (both machines): read both files, parse each line as JSON, merge in-memory, filter by `status != "resolved"`, sort by `ts` for display.
- **Migration:** `scripts/migrate_escalations.py` splits existing `shared/escalations.json` / `shared/escalations.jsonl` into the two per-machine files based on `writer` field (if present) or assigns to Pro by default.
- **Git-sync:** Both files are tracked in git. Each machine only appends to its own file. Merge conflicts are structurally impossible because each file has a single writer.
- No cross-machine lock required. No broker required.

Backward compatibility: during Phase 2, migration script runs once on both machines. The old `shared/escalations.jsonl` is archived to `shared/archive/escalations_legacy.jsonl`.

**Files:** `shared/escalations_pro.jsonl` (new), `shared/escalations_air.jsonl` (new), `scripts/migrate_escalations.py` (new), `scripts/nuzantara-sentinel.py`, any Air-side scripts that write escalations

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

### Deliverable 4.1 — Drop LangGraph, add phase field with transition matrix (C15, NP-3, Gemini Finding 4)

**Problem (v3.2):** The v3.1 plan proposed LangGraph + Postgres for tracking the progression of a job through T0→T4 healing phases. Both LangGraph and Postgres add WAL contention risk. SQLite is also problematic under concurrent writer conditions.

**Additional problem (v3.3 — NP-3 + Gemini Finding 4):** The `phase` field was added in v3.2 but with two unaddressed gaps:

1. `record_success()` did not reset `phase` back to `T0` on `OPEN→CLOSED` transition. A job that recovered after reaching `phase=T3` would permanently show `phase=T3` even when healthy.
2. No transition guard existed for retrograde moves. Any code path could set `phase=T3` from `T0` directly, skipping the T1→T2→T3 progression and making the phase field meaningless as a diagnostic.

**Solution (v3.3 — complete):**

Add a `phase` field to the existing `circuit_breakers.json` per-job entry. Values: `T0` (healthy baseline), `T1` (retry attempted), `T2` (aider dispatched), `T3` (in DLQ), `T4` (escalated to Claude Code), `TERMINAL` (max_attempts reached).

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

**Transition matrix** — implemented as `_set_phase(job, new_phase)` with explicit ValueError:

```
Valid forward transitions:
  T0 → T1 → T2 → T3 → T4 → TERMINAL

Authorized retrograde (record_success() only):
  ANY → T0

All other retrograde transitions: raise ValueError (see requirement below)
```

**REQUIREMENT (Round 3 — DeepSeek CRITICA):** The transition guard in `_set_phase()` **must** use `raise ValueError(f"Invalid phase transition: {current} → {new}")` — NOT `assert valid_transition`. Python `assert` statements are no-ops when the interpreter runs with the `-O` (optimize) flag, making the guard completely skippable in optimized deployments. Since this is a security-critical gate controlling which repair actions are applied to 5000+ client-affecting jobs, it must raise a real exception that cannot be silenced. Use `raise ValueError`, never `assert`, in `_set_phase()`.

`record_success()` must explicitly call `_set_phase(job, "T0")` to reset phase on recovery. This is the **only** path back to T0.

This requires ~20 lines of changes to `circuit_breaker.py` and `nuzantara-sentinel.py`. Zero new dependencies.

### Deliverable 4.2 — LLM as classifier/explainer only — explicit enforcement (C16, PARTIAL C16)

**Problem (v3.2):** The v3.1 plan allowed LLM to suggest execution paths (executor role). v3.2 added `llm_suggested_only=true` flag. However (DeepSeek PARTIAL C16), there was no enforcement point in `process_entry()` — the flag was set on the output object but nothing in `process_entry()` checked it before dispatching the action. A code path that reads `entry["action"]` without checking `entry.get("llm_suggested_only")` would silently execute an LLM-suggested action.

**Constraint for Phase 4 (v3.3 — enforced):**

- `claude_reason()` in `dlq_autopilot.py` returns classification and explanation only.
- The `fix_type` field from LLM output maps to a deterministic execution rule (same as `FIX_PATTERNS` dict in `classifier.py`).
- LLM output sets `llm_suggested_only=true` on the suggestion object.
- **`process_entry()` contains an explicit guard** (early in the function, before any action dispatch):

```python
if action.get("llm_suggested_only"):
    logger.info(
        "llm_suggested_action_skipped",
        job_id=entry["job_id"],
        suggestion=action,
    )
    # Fall through to deterministic decision tree — do NOT execute action
    action = None  # discard LLM action, proceed with rule-based path
```

- Execution uses only pre-defined handlers from `FIX_PATTERNS`, never raw LLM output.
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

## Risk Register (updated v3.3)

| ID  | Risk                                                                               | Severity | Likelihood | Mitigation                                                                                                                                                                                                                                                                                        | Owner   | Phase |
| --- | ---------------------------------------------------------------------------------- | -------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- | ----- |
| R1  | Infinite healing loop (CONFIRMED IN PROD)                                          | CRITICAL | CONFIRMED  | TERMINAL state + max_attempts (Phase 0.1)                                                                                                                                                                                                                                                         | Phase 0 | 0     |
| R2  | Healing loop — PID lock missing                                                    | HIGH     | HIGH       | `/tmp/sentinel.lock` with LOCK_NB (Phase 0.2)                                                                                                                                                                                                                                                     | Phase 0 | 0     |
| R3  | Registry integrity corruption by AI agent — silent proceed                         | CRITICAL | MEDIUM     | **HALT + REGISTRY_OVERRIDE gate** (Phase 0.4, N2/NC-2 hardened)                                                                                                                                                                                                                                   | Phase 0 | 0     |
| R4  | TOCTOU race in circuit_breaker.py                                                  | HIGH     | LOW        | Flock held from read through write (Phase 0.3)                                                                                                                                                                                                                                                    | Phase 0 | 0     |
| R5  | Command injection via allowed_cmds.txt path traversal + null/newline bypass        | HIGH     | LOW        | realpath + complete metachar blocklist incl. `\x00\n\r` (Phase 2.1)                                                                                                                                                                                                                               | Phase 2 | 2     |
| R6  | escalations cross-machine interleaved writes (O_APPEND not cross-machine)          | HIGH     | MEDIUM     | Per-machine files escalations_pro.jsonl / escalations_air.jsonl (Phase 2.3)                                                                                                                                                                                                                       | Phase 2 | 2     |
| R7  | Escalation alert flooding (2016 messages/week)                                     | MEDIUM   | HIGH       | 4h cooldown per job per alert (Phase 1.2)                                                                                                                                                                                                                                                         | Phase 1 | 1     |
| R8  | HEALING_DISABLED has no effect in LaunchAgent                                      | MEDIUM   | CONFIRMED  | File flag instead of env var (Phase 0.6)                                                                                                                                                                                                                                                          | Phase 0 | 0     |
| R9  | Sub-daily job dedup broken (idempotency token)                                     | MEDIUM   | HIGH       | Interval-based token (Phase 1.4)                                                                                                                                                                                                                                                                  | Phase 1 | 1     |
| R10 | LLM executor introduces non-determinism                                            | MEDIUM   | MEDIUM     | LLM = classify/explain only + explicit guard in process_entry() (Phase 4.2)                                                                                                                                                                                                                       | Phase 4 | 4     |
| R11 | \_failure_timestamps unbounded growth                                              | LOW      | HIGH       | 14-day inline pruning (Phase 1.6)                                                                                                                                                                                                                                                                 | Phase 1 | 1     |
| R12 | Watchdog absolute cutoff fires at wrong time after restart                         | LOW      | LOW        | Monotonic deadline (Phase 1.7)                                                                                                                                                                                                                                                                    | Phase 1 | 1     |
| R13 | OpenClaw jobs classified as REMOTE repair — clogs manual backlog                   | LOW      | CONFIRMED  | Auto-classify openclaw as LOCAL + github_actions/webhook/pg_trigger as OBSERVE_ONLY (Phase 0.5)                                                                                                                                                                                                   | Phase 0 | 0     |
| R14 | preclassify_jobs.py causes false HALT via N2 mechanism (NP-2)                      | MEDIUM   | HIGH       | preclassify updates checksum as last step (Phase 0.5)                                                                                                                                                                                                                                             | Phase 0 | 0     |
| R15 | Recovered job shows stale phase=T3 indefinitely (NP-3)                             | LOW      | HIGH       | record_success() resets phase to T0 + transition matrix assertion (Phase 4.1)                                                                                                                                                                                                                     | Phase 4 | 4     |
| R16 | dlq clear command referenced in ADR/criteria but unimplemented                     | MEDIUM   | CONFIRMED  | Deliverable 0.7 adds dlq_autopilot.py clear subcommand                                                                                                                                                                                                                                            | Phase 0 | 0     |
| R17 | Air not updated when Phase 0 deployed on Pro only                                  | HIGH     | MEDIUM     | Explicit Air deployment step in Phase 0 preamble (Gemini Finding 7)                                                                                                                                                                                                                               | Phase 0 | 0     |
| R18 | REGISTRY_HALT false-positive blocks entire Sentinel — including live critical jobs | HIGH     | MEDIUM     | Progressive alert escalation: T+30min second Telegram CRITICAL; T+4h email to zero@balizero.com. Max halt duration: 24h, then auto-resume with WARNING (not HALT) to avoid permanent lock. `REGISTRY_HALT` marker file must include `_halt_started_at` timestamp to enable this escalation timer. | Phase 0 | 0     |

---

## Critical Architecture Decisions (updated v3.3)

### ADR-1: Circuit Breaker State File — Single Writer Per File

**Decision:** Each state JSON file has one designated writer (field `_writer`). Cross-process writes go through a message-passing layer (currently JSONL append for escalations; file-per-job for sentinel state).
**Rationale:** Eliminates TOCTOU races without requiring a broker process.
**Enforcement:** Via code review only — not enforced at runtime. This is an accepted trade-off (Codex PARTIAL C19). The `_writer` field in every write provides audit evidence for post-incident analysis.

### ADR-2: TERMINAL State — Hard Stop

**Decision:** A job that reaches `max_attempts` transitions to `TERMINAL`. It is never automatically processed again. Removal from DLQ requires explicit human action via `dlq_autopilot.py clear <job_id>` (Deliverable 0.7).
**Rationale:** `abandoned` status re-entering the processing loop is the root cause of the 162-attempt entries currently in production. TERMINAL must be a true dead end.

### ADR-3: escalations — Per-Machine JSONL (REVISED from v3.2)

**Decision:** `shared/escalations_pro.jsonl` (written only by Pro) and `shared/escalations_air.jsonl` (written only by Air) replace the single `shared/escalations.jsonl`.
**Rationale (v3.3 revision):** Three independent reviewers (Codex N1, Gemini NP-1, DeepSeek NC-1) confirmed that `O_APPEND` is atomic on a single local filesystem but does NOT provide cross-machine linearization. Pro and Air each have a local git-tracked copy; writes to one copy do not affect the other until git-sync. Interleaved appends are possible if both machines write between sync cycles. Per-machine files have a single physical writer by construction — no locking needed, no merge conflicts possible.
**PIPE_BUF constraint (Round 3 — DeepSeek):** Each escalation entry appended to a `*.jsonl` file must remain under 4096 bytes (PIPE_BUF on macOS). Entries containing long stack traces or verbose error payloads must be truncated to 2000 characters before append. Writers must enforce this limit before calling `O_APPEND` write — otherwise the atomicity guarantee of `O_APPEND` no longer holds for entries exceeding PIPE_BUF.

### ADR-4: LangGraph Dropped

**Decision:** No LangGraph, no SQLite for job phase tracking. `phase` field in `circuit_breakers.json` is sufficient.
**Rationale:** LangGraph adds a dependency and WAL contention risk for what is 20 lines of state machine logic. The existing `circuit_breaker.py` already has the right structure.

### ADR-5: LLM Role = Classify Only (HARDENED from v3.2)

**Decision:** LLM output (from `claude_reason()` or `classify_with_llm()`) may influence classification and explain suggestions to the human reviewer, but may never directly trigger execution. `process_entry()` contains an explicit guard that discards any action with `llm_suggested_only=True` and falls through to the deterministic `FIX_PATTERNS` handler.
**Rationale:** A non-deterministic executor in an autonomous healing loop can mask systemic errors, retry the wrong fix, or interact badly with the Aider executor path. The explicit guard (not just a flag convention) prevents future refactors from accidentally re-enabling LLM execution.

### ADR-6: HEALING_DISABLED = File Flag

**Decision:** `~/.agent/decisions/HEALING_DISABLED` (presence of file) disables all Tier 1-3 actions system-wide. Env var `HEALING_DISABLED` is deprecated.
**Rationale:** LaunchAgent on macOS does not inherit shell environment variables. File flags work reliably regardless of process ancestry.

### ADR-7: Registry Integrity = HALT Gate (NEW — v3.3)

**Decision:** A SHA256 mismatch on `job_registry.json` halts all Sentinel processing and requires human confirmation via `~/.agent/decisions/REGISTRY_OVERRIDE` before resuming. The previous "warn + update + continue" behavior is removed.
**Rationale:** The registry controls `is_idempotent`, `critical`, `repair_scope`, and `max_attempts` for all 31 jobs affecting 5000+ clients. An AI agent silently corrupting these fields while the system continues operating is a higher risk than a false-positive halt requiring a 1-minute human review. The HALT + REGISTRY_OVERRIDE flow ensures every registry change is acknowledged. The `preclassify_jobs.py` script avoids false halts by self-updating the checksum as its final step (NP-2 fix).

---

## Implementation Timeline

| Phase       | Duration | Prerequisite                                     | Deliverables                                                                                                                                                                      |
| ----------- | -------- | ------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Phase 0** | 2 days   | —                                                | 0.1 (TERMINAL), 0.2 (PID lock), 0.3 (TOCTOU), 0.4 (registry HALT gate), 0.5 (preclassify + checksum update + OBSERVE_ONLY rule), 0.6 (HEALING_DISABLED flag), 0.7 (dlq clear CLI) |
| **Phase 1** | 3 days   | Phase 0 complete                                 | 1.1 (elif decision tree), 1.2 (cooldown), 1.3 (sentinel_status.json), 1.4 (idempotency token), 1.5 (\_writer field), 1.6 (pruning), 1.7 (monotonic cutoff)                        |
| **Phase 2** | 2 days   | Phase 1 complete                                 | 2.1 (path traversal + null/newline blocklist), 2.2 (retry_job defense-in-depth), 2.3 (per-machine JSONL escalations)                                                              |
| **Phase 3** | 2 days   | Phase 0 complete (can run parallel to Phase 1-2) | 3.1 (doc_generator scope), 3.2 (AUTOMATIONS_REFERENCE.md auto-gen)                                                                                                                |
| **Phase 4** | 3 days   | Phase 1 complete                                 | 4.1 (phase field + transition matrix + record_success reset), 4.2 (LLM classify-only + process_entry guard), 4.3 (DLQ dashboard)                                                  |

**Total: 12 days elapsed (7 days net, with Phase 3 parallel)**

---

## Verification Criteria

Each phase is complete when:

- **Phase 0:**
  - `comfyui_server` and `seo_auto_fixer` show `phase=TERMINAL` in `circuit_breakers.json`; no new Telegram alerts for these jobs
  - Sentinel starts with PID lock visible in `/tmp/nuzantara_sentinel.lock`
  - Modifying `job_registry.json` without running `preclassify_jobs.py` causes Sentinel to HALT with `~/.agent/decisions/REGISTRY_HALT` present; creating `REGISTRY_OVERRIDE` resumes processing
  - `python scripts/dlq_autopilot.py clear comfyui_server` removes the TERMINAL entry and logs `dlq_clear_manual`
  - Both Pro and Air confirm Phase 0 deliverables are live: `ssh air 'launchctl list | grep sentinel'` returns active agent

- **Phase 1:**
  - `sentinel_status.json` exists and updates every 5min
  - No duplicate Telegram alerts within 4h for same job
  - RAG Canary 6h runs use distinct idempotency tokens across runs in the same calendar day

- **Phase 2:**
  - `python3 -c "from scripts.sentinel_lib.repairer import retry_job; ok, msg = retry_job('python3 ../../etc/passwd'); assert not ok"` returns `False`
  - `python3 -c "from scripts.sentinel_lib.repairer import retry_job; ok, msg = retry_job('echo \x00foo'); assert not ok"` returns `False`
  - Concurrent append to `escalations_pro.jsonl` on Pro and `escalations_air.jsonl` on Air produces two valid JSONL files with no parse errors after git-sync and merge read

- **Phase 3:**
  - `git diff --name-only HEAD | grep CLAUDE.md` returns empty after a `doc_generator` run

- **Phase 4:**
  - `circuit_breakers.json` contains `phase` field for all jobs; a job recovering from OPEN to CLOSED shows `phase=T0`
  - Attempting `_set_phase(job, "T3")` directly from `T0` raises `AssertionError`
  - `dlq_autopilot.py` `claude_reason()` output sets `llm_suggested_only=true` on all returned dicts; `process_entry()` logs `llm_suggested_action_skipped` and does not execute the action

---

_Plan v3.3 synthesized from 5 independent review sources (Round 1) + 3 independent Round 2 sources (Codex SRE, Gemini Architecture, DeepSeek Reasoning) + 4 conditions from Round 3. 13 new findings incorporated from Round 2. 4 conditions incorporated from Round 3. Codebase state verified 2026-03-31._
_Next review: NB-1 Oracle validation — see `docs/AUTOMATION_AUTONOMY_NB1_SUBMISSION.md`._

---

## VALIDATION STATUS

| Round | Codex SRE          | Gemini Architecture | DeepSeek Reasoning |
| ----- | ------------------ | ------------------- | ------------------ |
| R1    | 9 findings         | 7 findings          | 7 findings         |
| R2    | GO+3 new           | GO+3 new            | GO+2 partial       |
| R3    | GO WITH CONDITIONS | GO WITH CONDITIONS  | GO WITH CONDITIONS |

**Pending: NB-1 Oracle validation**
