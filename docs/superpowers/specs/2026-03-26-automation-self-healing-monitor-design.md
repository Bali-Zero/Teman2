# Automation Self-Healing Monitor — Design Spec

**Date:** 2026-03-26
**Status:** Approved (Option C — File-Based State Machine)
**Scope:** All 24 Nuzantara automations (5 LaunchAgents + 19 OpenClaw cron + 8 shell scripts)

---

## 1. Core Problem: Who Fixes the Code?

**The question:** An automation fails because of a code bug. Who fixes it?

**Answer — Three-Tier Repair System:**

| Tier       | Who                    | What They Fix                                                                                     | How                                                                                                                                                                                                                                                                                     |
| ---------- | ---------------------- | ------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Tier 1** | Sentinel (automatic)   | Transient errors only: network timeout, service restart, temp file missing                        | Retry 3x with exponential backoff. No code changes.                                                                                                                                                                                                                                     |
| **Tier 2** | Aider (AI-dispatched)  | Deterministic errors with known fix patterns: Python 3.9 type syntax, missing env var, wrong path | LLM log classifier (Haiku) identifies root cause → dispatches `ai-dispatch.sh aider-fix` → validates fix with a test run                                                                                                                                                                |
| **Tier 3** | Claude Code (summoned) | Complex bugs, multi-file refactors, architecture issues — anything Aider can't fix confidently    | Sentinel writes structured problem report to `~/.agent/decisions/dlq.json` + sends Telegram alert with full log, classification, and suggested approach. **Claude Code is summoned** (via OpenClaw or manual session) with full context pre-loaded. Claude fixes, verifies, clears DLQ. |
| **Tier 4** | Zero (human)           | Security issues, business logic changes, anything requiring human judgment or authorization       | Telegram CRITICAL alert. Claude Code escalates explicitly: "Cannot fix autonomously — requires human decision."                                                                                                                                                                         |

**Transient vs Deterministic classification (pre-LLM, deterministic rules first):**

```
TRANSIENT (retry automatically):
- HTTP 5xx, connection refused, ETIMEDOUT
- "service unavailable", "temporarily unavailable"
- Exit codes: 1, 124 (timeout), 130 (SIGINT)

DETERMINISTIC (escalate immediately):
- "SyntaxError", "ImportError", "ModuleNotFoundError"
- "Permission denied", "No such file or directory"
- "NameError", "AttributeError", "TypeError"
- Exit code: 2 (bash syntax error)
- Pattern: error repeats identically 2+ times in a row
```

If classification is ambiguous → treat as TRANSIENT once, then DETERMINISTIC on repeat.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  PRO (Nuzantara) — Dev Machine, 48GB M4 Pro                     │
│                                                                  │
│  ┌──────────────────┐  ┌─────────────────┐  ┌───────────────┐  │
│  │  5 LaunchAgents  │  │  19 OpenClaw    │  │  8 Shell      │  │
│  │  (launchd)       │  │  cron jobs      │  │  Scripts      │  │
│  └────────┬─────────┘  └────────┬────────┘  └───────┬───────┘  │
│           │                     │                    │          │
│           └─────────────────────┼────────────────────┘          │
│                                 │ write .last.json               │
│                                 ▼                                │
│            ~/.agent/decisions/state/<job>.last.json              │
│                                                                  │
│   Dead Man's Switch: cron @hourly writes ssh air 'touch ~/.pro_heartbeat'  │
└─────────────────────────────────────────────────────────────────┘
                         │ SSH (read state files)
                         │ ssh nuzantara@Nuzantara 'cat ~/.agent/...'
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  AIR (Nuzantara-9) — H24 Server, 16GB M4                        │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  nuzantara-sentinel.py  (LaunchAgent, every 5min)        │   │
│  │                                                          │   │
│  │  1. Glob state files (Pro via SSH + Air local)           │   │
│  │  2. Staleness check: daily job not run in 26h → ALERT    │   │
│  │  3. Classify failure: rules → Haiku LLM                  │   │
│  │  4. Circuit breaker: CLOSED/OPEN/HALF-OPEN per job       │   │
│  │  5. Tier dispatch:                                       │   │
│  │     TRANSIENT → retry via ssh + launchctl/openclaw       │   │
│  │     DETERMINISTIC → ai-dispatch aider-fix → test run     │   │
│  │     COMPLEX → Telegram alert + DLQ                       │   │
│  │  6. Self-log: automation_runs.jsonl                      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ~/.pro_heartbeat — checked every 2h (dead man's switch)        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. State File Schema

**Location:** `~/.agent/decisions/state/<job_id>.last.json`
**Written by:** each job at start AND end
**Read by:** Sentinel on Air via SSH

```json
{
  "ts": 1711234567.89,
  "job": "intel_scraper",
  "status": "ok",
  "duration_s": 127.3,
  "exit_code": 0,
  "host": "Nuzantara",
  "next_expected_run": 1711320967.89,
  "circuit_state": "CLOSED",
  "retry_attempt": 0,
  "last_error": null
}
```

**Status values:** `running` | `ok` | `failed` | `skipped`
**Circuit states:** `CLOSED` (normal) | `OPEN` (disabled) | `HALF_OPEN` (testing recovery)

**Minimum heartbeat** (what every job must write, nothing more):

```bash
echo '{"job":"nome_job","ts":'$(date +%s)',"status":"ok","host":"'$(hostname)'"}' \
  > ~/.agent/decisions/state/nome_job.last.json
```

---

## 4. Job Registry (Source of Truth)

`~/.agent/decisions/job_registry.json` — defines expected schedules for staleness detection:

```json
{
  "jobs": {
    "intel_scraper": {
      "host": "Nuzantara",
      "type": "launchagent",
      "schedule_seconds": 86400,
      "staleness_threshold_s": 93600,
      "restart_cmd": "launchctl kickstart -k gui/$(id -u)/com.balizero.intel.nightly",
      "fix_cmd": "cd ~/Desktop/nuzantara && ./scripts/ai-dispatch.sh aider-fix 'intel_scraper error: {error_summary}'"
    },
    "daily_ops": {
      "host": "Nuzantara",
      "type": "openclaw",
      "schedule_seconds": 86400,
      "staleness_threshold_s": 93600,
      "restart_cmd": "curl -s -X POST http://loopback:18789/api/trigger/daily_ops"
    }
  }
}
```

**Auto-discovery**: Sentinel also watches `state/` for `.last.json` files NOT in the registry — these get added automatically with default thresholds (2x expected interval). New jobs require only a heartbeat write; the Sentinel discovers them within 5 minutes.

---

## 5. Sentinel Logic (nuzantara-sentinel.py)

```
EVERY 5 MINUTES:

1. COLLECT STATE
   - Read Air local state: glob ~/.agent/decisions/state/*.last.json
   - Read Pro state via SSH: ssh Nuzantara 'cat ~/.agent/decisions/state/*.last.json'
   - If SSH fails: alert "Pro unreachable" (not per-job failure)

2. FOR EACH JOB:
   a. STALENESS CHECK
      age = now - state["ts"]
      if age > registry[job]["staleness_threshold_s"]:
        → classify as STALE_JOB (special failure type)

   b. FAILURE CHECK
      if state["status"] == "failed":
        error_type = classify_failure(state["last_error"])

   c. CIRCUIT BREAKER CHECK
      if circuit_state == "OPEN":
        → skip, check again in 30min

   d. DISPATCH
      if error_type == TRANSIENT:
        retry with exponential backoff (max 3x)
        if retries exhausted: → DLQ + Telegram CRITICAL

      elif error_type == DETERMINISTIC:
        → LLM log analysis (Haiku)
        → if fix_pattern known: dispatch aider-fix → verify with test run
        → if fix_pattern unknown: DLQ + Telegram CRITICAL with full log

      elif error_type == STALE_JOB:
        → check if machine is up (ping/SSH)
        → if machine up: trigger job restart
        → if machine down: Telegram CRITICAL "Machine offline"

3. DEAD MAN'S SWITCH
   if last Pro heartbeat > 2 hours ago:
     alert "Pro not responding - manual check required"

4. SELF-LOG
   append to ~/logs/sentinel.jsonl: {ts, jobs_checked, failures_detected, fixes_applied}
```

---

## 6. AI-Driven Code Repair (Tier 2)

When the LLM classifier identifies a **known fix pattern**, the Sentinel dispatches an automated repair:

```bash
# Sentinel calls this after Haiku classification:
./scripts/ai-dispatch.sh aider-fix "Fix {job_name}: {error_summary}
  Error: {last_error}
  File: {inferred_file}
  Pattern: {fix_pattern}
  Verify by running: {test_cmd}"
```

**Known fix patterns** (hardcoded in Sentinel, updated by Zero):

```python
FIX_PATTERNS = {
    r"dict\[.*\] \| None": {
        "description": "Python 3.9 type union syntax",
        "fix": "Replace X | None with Optional[X] from typing",
        "confidence": 0.95
    },
    r"No module named '(\w+)'": {
        "description": "Missing Python package",
        "fix": "pip install {match[1]} in the correct venv",
        "confidence": 0.90
    },
    r"SMTP Authentication Failed": {
        "description": "Wrong SMTP credentials",
        "fix": "Check SMTP_LOGIN and SMTP_PASS env vars",
        "confidence": 0.85
    }
}
```

**Confidence threshold:** Only auto-dispatch Tier 2 if fix confidence >= 0.85. Below that → Tier 3 (human).

**Verification:** After Tier 2 repair, Sentinel runs a test invocation of the job. If exit_code == 0 → fix confirmed, circuit resets. If still failing → escalate to Tier 3.

---

## 7. Alert System (Telegram)

**No duplication:** md5sum of `{job}:{error_summary}` used as dedup key (same pattern as fly-health-check.sh). Same error not re-alerted within 1 hour.

**Alert levels:**

```
🟡 WARNING: Job stale (>1 scheduled interval missed)
🔴 CRITICAL: Job failed + auto-fix failed + entering DLQ
⚫ DEAD MAN: Pro machine unreachable >2h
🔧 INFO: Tier 2 fix applied successfully (daily summary, not per-fix)
```

**Daily fleet report** (08:00 WITA):

```
🤖 Fleet Status — 2026-03-26 08:00
✅ 22/24 automations healthy
⚠️ 1 stale: vector-reindex-check (last run: 3d ago)
🔴 1 in DLQ: nuzantara-sync (lsof missing)
📊 Fixes applied this week: 3 (2 auto, 1 human)
```

---

## 8. Dead Letter Queue

`~/.agent/decisions/dlq.json` — jobs that exceeded max_retries or need human attention:

```json
{
  "queue": [
    {
      "job": "nuzantara-sync",
      "added_ts": 1711234567.89,
      "error_summary": "lsof not found — cascade: port 15432 not freed → SSH tunnel fails",
      "classification": "DETERMINISTIC",
      "fix_attempt": null,
      "status": "needs_human"
    }
  ]
}
```

Jobs in DLQ are **paused** (circuit OPEN). Sentinel does not retry them. Zero clears them manually after fix.

---

## 9. Bootstrapping Existing Automations

To integrate existing jobs into the system, each job needs ONE addition — a heartbeat write at the end:

**Shell scripts** (e.g., `fly-health-check.sh`):

```bash
# Add at end of script (before exit):
echo '{"job":"fly_health_check","ts":'$(date +%s)',"status":"ok","host":"'$(hostname)'"}' \
  > ~/.agent/decisions/state/fly_health_check.last.json
```

**OpenClaw cron jobs** — wrapper function added to each job's shell script:

```bash
sentinel_ping() {
  local status="${1:-ok}"
  local job_name="$2"
  echo '{"job":"'"$job_name"'","ts":'$(date +%s)',"status":"'"$status"'","host":"'$(hostname)'"}' \
    > ~/.agent/decisions/state/"$job_name".last.json
}
```

**LaunchAgents** — heartbeat added to the script they invoke. No plist changes needed.

**Priority order for bootstrapping** (by failure frequency from log analysis):

1. `vector-reindex-check` (BROKEN — needs fix first)
2. `nuzantara-sync` (cascade failure — needs lsof fix)
3. `fly-pg-backup` (intermittent, already has retry)
4. `fly-health-check` (healthy, easy to add)
5. All 19 OpenClaw jobs (script wrapper)
6. Remaining LaunchAgents

---

## 10. Files and Locations

| File                         | Location                                                   | Purpose               |
| ---------------------------- | ---------------------------------------------------------- | --------------------- |
| `nuzantara-sentinel.py`      | Air: `~/scripts/`                                          | Main sentinel process |
| `sentinel.launchagent.plist` | Air: `~/Library/LaunchAgents/com.nuzantara.sentinel.plist` | Runs every 5min       |
| `job_registry.json`          | Both: `~/.agent/decisions/job_registry.json`               | Expected schedules    |
| `<job>.last.json`            | Both: `~/.agent/decisions/state/<job>.last.json`           | Per-job heartbeat     |
| `dlq.json`                   | Air: `~/.agent/decisions/dlq.json`                         | Failed jobs queue     |
| `circuit_breakers.json`      | Air: `~/.agent/decisions/circuit_breakers.json`            | Per-job circuit state |
| `sentinel.jsonl`             | Air: `~/logs/sentinel.jsonl`                               | Sentinel run log      |
| `automation_runs.jsonl`      | Both: `~/logs/automation_runs.jsonl`                       | Job history           |

---

## 11. Immediate Fixes (Before Sentinel)

Two existing bugs must be fixed BEFORE implementing the Sentinel (they'd otherwise generate false alerts):

1. **`vector-reindex-check.py`**: `dict[str, str] | None` → `Optional[Dict[str, str]]` (Python 3.9 incompatibility)
2. **`nuzantara-sync` lsof dependency**: Install `lsof` via Homebrew on Pro, or replace with `lsof` equivalent (`netstat -an | grep LISTEN`)

---

## 12. Summoning Claude Code (Tier 3 Detail)

When Sentinel escalates to Tier 3, it prepares a **context bundle** that makes Claude Code immediately productive:

**DLQ entry format** (pre-filled by Sentinel):

```json
{
  "job": "vector_reindex_check",
  "error_summary": "SyntaxError: dict[str, str] | None requires Python 3.10+",
  "log_tail": "..last 50 lines of log...",
  "classification": "DETERMINISTIC",
  "files_implicated": ["~/scripts/vector-reindex-check.py"],
  "aider_attempts": 1,
  "aider_failure_reason": "Fix introduced new ImportError",
  "suggested_approach": "Replace all X | Y type unions with Optional[X] + Union syntax",
  "test_cmd": "python ~/scripts/vector-reindex-check.py --dry-run",
  "status": "needs_claude_code"
}
```

**Telegram alert format:**

```
🤖 Tier 3 Escalation — Claude Code needed

Job: vector_reindex_check
Error: SyntaxError (Python 3.9 type syntax)
Aider tried: yes — introduced new ImportError
File: ~/scripts/vector-reindex-check.py

Run: claude ~/.agent/decisions/dlq.json
→ Fix → clear DLQ → job auto-resumes
```

This means Claude Code arrives with: the error, the file, what Aider already tried, why it failed, and the exact test command to verify the fix. No investigation needed — straight to the fix.

---

## 13. Out of Scope

- Client-facing notifications (WhatsApp, email to clients) — internal only
- Fly.io VM management (fly-health-check.sh already handles this)
- Frontend/UI dashboard (fleet_status.json can be consumed later)
- Multi-region distributed state (single Mac cluster only)

---

## Summary

The Sentinel is a **4-tier repair system** where:

- **Tier 1 (automatic)**: transient errors → retry silently
- **Tier 2 (Aider)**: known code patterns → `aider-fix` → verify → circuit reset
- **Tier 3 (Claude Code)**: complex bugs → summoned with full context pre-loaded → fix → clear DLQ
- **Tier 4 (Zero)**: security/business decisions → human judgment required

New automations are auto-discovered by globbing the `state/` directory. Each job needs only a one-line heartbeat write. The entire system runs on Air (H24) and monitors both machines.
