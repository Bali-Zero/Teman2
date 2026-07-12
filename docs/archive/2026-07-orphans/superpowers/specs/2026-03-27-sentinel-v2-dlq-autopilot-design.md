# Sentinel V2 + DLQ Autopilot — Implementation Spec

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the 4 operational gaps in the existing Sentinel (12 frozen circuit breakers, 18 rotting DLQ entries, no OpenClaw pattern, broken LLM classifier) and add a DLQ Autopilot that autonomously fixes jobs via Aider, escalating to Claude Code when Aider cannot.

**Architecture:** Patch-and-extend the existing `~/scripts/` infrastructure. No new frameworks. Three changes to existing files + two new files (`dlq_autopilot.py` + LaunchAgent plist). Circuit breaker writes become atomic via fcntl. DLQ processing has a pre-flight that skips misdiagnosed entries. Aider is gated by an explicit safelist and requires `test_cmd` + known files.

**Tech Stack:** Python 3.11, macOS LaunchAgent, fcntl locking, OpenClaw CLI, Aider, Claude CLI (`claude --print`), Telegram Bot API, existing `sentinel_lib/`.

**Review:** Design reviewed by DeepSeek R1 671b + Codex CLI. 3 blockers identified and incorporated (CB file lock, Aider gate, no_api_key pre-flight). `claude --print` Fix 2 reverted per Codex recommendation.

---

## Current State (measured)

| Metric                | Value                                              |
| --------------------- | -------------------------------------------------- |
| Jobs monitored        | 45                                                 |
| Healthy per run       | 32/45                                              |
| Circuit breakers OPEN | 12 (never auto-probe)                              |
| DLQ entries           | 18 (all `subtype: no_api_key` — misdiagnosed)      |
| Main failure pattern  | `OpenClaw consecutiveErrors=N` — no fix_pattern    |
| LLM classifier        | Fails silently (`no_api_key` subtype) in every run |

---

## File Map

| File                                                       | Action                                            | Lines |
| ---------------------------------------------------------- | ------------------------------------------------- | ----- |
| `~/scripts/sentinel_lib/circuit_breaker.py`                | MODIFY — atomic writes via fcntl                  | +15   |
| `~/scripts/sentinel_lib/classifier.py`                     | MODIFY — OpenClaw patterns                        | +12   |
| `~/scripts/nuzantara-sentinel.py`                          | MODIFY — forced HALF_OPEN probe in run_sentinel() | +25   |
| `~/scripts/dlq_autopilot.py`                               | NEW — DLQ autopilot main                          | ~250  |
| `~/Library/LaunchAgents/com.nuzantara.dlq-autopilot.plist` | NEW — 30min schedule                              | ~30   |
| `~/.agent/decisions/job_registry.json`                     | MODIFY — +1 entry                                 | +10   |
| `~/Desktop/nuzantara/CLAUDE.md`                            | MODIFY — +§19 claude_tasks escalations            | +15   |

---

## Task 1: Atomic writes in circuit_breaker.py

**Files:**

- Modify: `~/scripts/sentinel_lib/circuit_breaker.py`

### What to change

Replace the bare `open(STATE_FILE, "w")` in `_save()` with an atomic write using `fcntl.flock`. Add a helper `_atomic_save()`. Update `record_success()`, `record_failure()`, `_set_state()` to all go through `_atomic_save()`.

The pattern:

```python
import fcntl, tempfile, os

def _atomic_save(data: dict) -> None:
    dir_ = os.path.dirname(STATE_FILE)
    fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            json.dump(data, f, indent=2)
            fcntl.flock(f, fcntl.LOCK_UN)
        os.replace(tmp, STATE_FILE)
    except Exception:
        os.unlink(tmp)
        raise
```

Remove the old `_save()` function. Replace all 3 call sites.

**Test:** Run two concurrent processes that call `record_failure("test_job")` 100 times each. Verify final `failures` count is exactly 200, not lower (no lost writes).

```bash
python3 -c "
import subprocess, json, os
# spawn 2 processes
p1 = subprocess.Popen(['python3', '-c', '''
import sys; sys.path.insert(0, os.path.expanduser(\"~/scripts\")); from sentinel_lib.circuit_breaker import record_failure
for _ in range(10): record_failure(\"atomic_test\")
'''])
p2 = subprocess.Popen(['python3', '-c', '''
import sys; sys.path.insert(0, os.path.expanduser(\"~/scripts\")); from sentinel_lib.circuit_breaker import record_failure
for _ in range(10): record_failure(\"atomic_test\")
'''])
p1.wait(); p2.wait()
import json
d = json.load(open(os.path.expanduser('~/.agent/decisions/circuit_breakers.json')))
failures = d.get('atomic_test', {}).get('failures', 0)
print('PASS' if failures == 20 else f'FAIL: got {failures}, expected 20')
"
```

---

## Task 2: OpenClaw patterns in classifier.py

**Files:**

- Modify: `~/scripts/sentinel_lib/classifier.py`

### What to change

Add to `TRANSIENT_PATTERNS`:

```python
r"consecutiveErrors=[12][,\s]",  # 1-2 consecutive errors → transient, worth retrying
```

Add to `DETERMINISTIC_PATTERNS`:

```python
(r"consecutiveErrors=[3-9]\d*[,\s]", "openclaw_persistent_error"),
```

Add to `FIX_PATTERNS`:

```python
"openclaw_persistent_error": {
    "description": "OpenClaw job failing 3+ consecutive times — restart needed",
    "fix_instruction": (
        "Trigger the job manually: openclaw cron run <openclaw_id> --timeout 30000. "
        "If it fails again, check ~/.openclaw/workspace/logs/ for the agent turn error."
    ),
    "confidence": 0.90,
},
```

**Test:**

```python
from sentinel_lib.classifier import classify

# 1 error → TRANSIENT
r = classify("OpenClaw consecutiveErrors=1, lastStatus=error", 0)
assert r["type"] == "TRANSIENT", f"Expected TRANSIENT, got {r}"

# 3 errors → DETERMINISTIC
r = classify("OpenClaw consecutiveErrors=3, lastStatus=error", 0)
assert r["type"] == "DETERMINISTIC", f"Expected DETERMINISTIC, got {r}"
assert r["subtype"] == "openclaw_persistent_error"
assert r["fix_pattern"]["confidence"] == 0.90

# Existing pattern still works
r = classify("SyntaxError: invalid syntax", 0)
assert r["type"] == "DETERMINISTIC"
assert r["subtype"] == "syntax_error"

print("All classifier tests PASS")
```

---

## Task 3: Forced HALF_OPEN probe in nuzantara-sentinel.py

**Files:**

- Modify: `~/scripts/nuzantara-sentinel.py`

### What to change

In `run_sentinel()`, before the main `for job_id, state in states.items()` loop, add a forced HALF_OPEN probe pass. This unblocks circuit breakers that have been OPEN for > `FORCED_HALFOPEN_AGE_S` seconds.

```python
FORCED_HALFOPEN_AGE_S = 7200  # 2 hours

def _force_halfopen_stale_circuits(registry: dict) -> None:
    """
    Force HALF_OPEN on any circuit that has been OPEN for > 2h.
    Runs inside run_sentinel() only — single writer, no external caller.
    """
    from sentinel_lib.circuit_breaker import _load, _atomic_save, OPEN_TIMEOUT_S
    data = _load()
    forced = []
    for job, cb in data.items():
        if cb.get("state") != "OPEN":
            continue
        age = time.time() - cb.get("opened_at", 0)
        if age > FORCED_HALFOPEN_AGE_S:
            data[job]["state"] = "HALF_OPEN"
            forced.append(job)
    if forced:
        _atomic_save(data)
        logger.info(f"Forced HALF_OPEN on {len(forced)} stale circuits: {forced}")
```

Call it at the top of `run_sentinel()`, before the states loop, after `check_dead_man_switch()`:

```python
_force_halfopen_stale_circuits(registry)
```

**Important:** `_force_halfopen_stale_circuits` must import `_atomic_save` from `circuit_breaker` — not call `_save` directly.

**Test:**

```bash
python3 -c "
import sys, time, json, os
sys.path.insert(0, os.path.expanduser('~/scripts'))
from sentinel_lib.circuit_breaker import _atomic_save, _load

# Plant a stale OPEN CB
data = _load()
data['test_stale_job'] = {'state': 'OPEN', 'failures': 5, 'opened_at': time.time() - 8000}
_atomic_save(data)

# Run the probe function (import it after patching)
from nuzantara_sentinel import _force_halfopen_stale_circuits
_force_halfopen_stale_circuits({})

data2 = _load()
state = data2.get('test_stale_job', {}).get('state')
print('PASS' if state == 'HALF_OPEN' else f'FAIL: state={state}')

# Cleanup
del data2['test_stale_job']
_atomic_save(data2)
"
```

---

## Task 4: dlq_autopilot.py

**Files:**

- Create: `~/scripts/dlq_autopilot.py`

### Full implementation

```python
#!/usr/bin/env python3
"""
DLQ Autopilot — processes rotting DLQ entries autonomously.

Pipeline per entry:
  Pre-flight → Claude CLI reasoning → retry / aider-fix / escalate_to_claude_code

Runs every 30min via LaunchAgent com.nuzantara.dlq-autopilot.
Lock: ~/.agent/locks/dlq_autopilot.lock (fcntl, stale-lock detection).
"""
import fcntl
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="[DLQAutopilot %(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(os.path.expanduser("~/logs/dlq_autopilot.log")),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("dlq_autopilot")

# ── Paths ──────────────────────────────────────────────────────────────────────
HOME = Path.home()
AGENT_DIR = HOME / ".agent" / "decisions"
DLQ_FILE = AGENT_DIR / "dlq.json"
REGISTRY_FILE = AGENT_DIR / "job_registry.json"
LOCKS_DIR = AGENT_DIR / "locks"
LOCK_FILE = LOCKS_DIR / "dlq_autopilot.lock"
CLAUDE_TASKS_DIR = AGENT_DIR / "claude_tasks"
NUZANTARA_ROOT = HOME / "Desktop" / "nuzantara"

# ── Tuning constants ───────────────────────────────────────────────────────────
LOCK_STALE_AGE_S = 1500          # 25min — if lock older than this, treat as stale
MAX_ATTEMPTS = 3                  # per DLQ entry
DLQ_TTL_S = 172800                # 48h — abandon entries older than this with empty error
MIN_ERROR_LEN = 20                # skip reasoning if error_summary shorter than this
CONFIDENCE_RETRY = 0.95           # no-code-change retry threshold
CONFIDENCE_AIDER = 0.90           # code-change aider threshold
REASONING_TIMEOUT_S = 90          # claude --print timeout

# Jobs that Aider must never touch
AIDER_BLOCKLIST = {
    "core_guardian",
    "daily_ops_autopilot",
    "learning_pipeline",
    "seo_auto_fixer",
    "weekly_review",
    "weekly_report",
}

# Subtypes that indicate the classifier itself failed — no LLM reasoning needed
CLASSIFIER_FAILURE_SUBTYPES = {"no_api_key", "llm_failed", "no_error_text", "unclassified"}


# ── Lock helpers ───────────────────────────────────────────────────────────────

def acquire_lock() -> Optional[int]:
    """Acquire lock file. Returns fd or None if already locked."""
    LOCKS_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = str(LOCK_FILE)

    # Stale lock detection
    if LOCK_FILE.exists():
        age = time.time() - LOCK_FILE.stat().st_mtime
        if age > LOCK_STALE_AGE_S:
            logger.warning(f"Stale lock detected ({age:.0f}s old) — removing")
            LOCK_FILE.unlink(missing_ok=True)

    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        os.write(fd, str(os.getpid()).encode())
        return fd
    except BlockingIOError:
        logger.info("Lock held by another process — skipping this run")
        return None


def release_lock(fd: int) -> None:
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
        LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass


# ── DLQ I/O ───────────────────────────────────────────────────────────────────

def load_dlq() -> list:
    try:
        return json.loads(DLQ_FILE.read_text()).get("queue", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_dlq(queue: list) -> None:
    tmp = DLQ_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps({"queue": queue}, indent=2))
    tmp.replace(DLQ_FILE)


def load_registry() -> dict:
    try:
        return json.loads(REGISTRY_FILE.read_text()).get("jobs", {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


# ── Telegram ──────────────────────────────────────────────────────────────────

def send_telegram(message: str) -> None:
    import urllib.request, urllib.parse
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "413539912")
    if not token:
        return
    try:
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": f"🤖 DLQAutopilot | {message}"}).encode()
        urllib.request.urlopen(
            urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data),
            timeout=10
        )
    except Exception:
        pass


# ── Claude CLI reasoning ───────────────────────────────────────────────────────

def claude_reason(entry: dict) -> Optional[dict]:
    """
    Ask Claude CLI to reason about a DLQ entry.
    Returns {fix_type, fix_instruction, confidence, needs_code_change} or None.
    """
    job = entry["job"]
    error = entry.get("error_summary", "")
    log_tail = entry.get("log_tail", "")[-500:]
    files = entry.get("files_implicated", [])

    prompt = f"""You are diagnosing a failed automation job on a macOS production server.

Job name: {job}
Error summary: {error}
Log tail (last 500 chars): {log_tail}
Files implicated: {files}

Respond with JSON only (no markdown, no explanation):
{{
  "fix_type": "restart|config|code|unknown",
  "fix_instruction": "one concrete sentence describing the exact fix",
  "confidence": 0.0,
  "needs_code_change": false
}}

Rules:
- confidence must be 0.0-1.0
- needs_code_change=true only if source code files need editing
- If error is empty or ambiguous, set confidence <= 0.5
- Do not fabricate fixes for empty errors"""

    try:
        result = subprocess.run(
            ["claude", "--print", prompt],
            capture_output=True, text=True, timeout=REASONING_TIMEOUT_S,
            env={**os.environ, "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"},
        )
        if result.returncode != 0:
            logger.warning(f"{job}: claude --print exit {result.returncode}")
            return None

        # Strip ANSI codes and extract JSON
        clean = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
        match = re.search(r"\{.*\}", clean, re.DOTALL)
        if not match:
            logger.warning(f"{job}: no JSON in claude output")
            return None

        data = json.loads(match.group())
        # Validate required keys
        required = {"fix_type", "fix_instruction", "confidence", "needs_code_change"}
        if not required.issubset(data.keys()):
            return None
        data["confidence"] = float(data["confidence"])
        return data

    except subprocess.TimeoutExpired:
        logger.warning(f"{job}: claude --print timed out after {REASONING_TIMEOUT_S}s")
        return None
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"{job}: JSON parse error: {e}")
        return None
    except FileNotFoundError:
        logger.error("claude CLI not found — check PATH")
        return None


# ── Aider dispatch ────────────────────────────────────────────────────────────

def dispatch_aider(entry: dict, reasoning: dict, registry: dict) -> tuple[bool, str]:
    """
    Dispatch aider-fix via ai-dispatch.sh. Returns (success, output).
    Pre-conditions (caller must verify):
      - files_implicated contains ≥1 real path
      - test_cmd is present in registry
      - job not in AIDER_BLOCKLIST
    """
    job = entry["job"]
    files = entry.get("files_implicated", [])
    test_cmd = registry.get(job, {}).get("test_cmd", "")
    fix_instruction = reasoning["fix_instruction"]

    prompt = (
        f"Fix automation job '{job}'.\n"
        f"Error: {entry.get('error_summary', '')}\n"
        f"Fix: {fix_instruction}\n"
        f"Files: {', '.join(files)}\n"
        f"Verify by running: {test_cmd}"
    )

    dispatch_script = str(NUZANTARA_ROOT / "scripts" / "ai-dispatch.sh")
    if not os.path.exists(dispatch_script):
        return False, f"ai-dispatch.sh not found at {dispatch_script}"

    # Stash before aider runs
    stash_label = f"dlq_autopilot_{job}_{int(time.time())}"
    subprocess.run(
        ["git", "stash", "push", "-m", stash_label],
        cwd=str(NUZANTARA_ROOT), capture_output=True
    )

    try:
        result = subprocess.run(
            ["bash", dispatch_script, "aider-fix", prompt],
            capture_output=True, text=True, timeout=300, cwd=str(NUZANTARA_ROOT),
        )
        success = result.returncode == 0
        output = (result.stdout + result.stderr)[:500]

        if not success:
            # Restore stash on failure
            subprocess.run(
                ["git", "stash", "pop"],
                cwd=str(NUZANTARA_ROOT), capture_output=True
            )

        return success, output
    except subprocess.TimeoutExpired:
        subprocess.run(["git", "stash", "pop"], cwd=str(NUZANTARA_ROOT), capture_output=True)
        return False, "aider-fix timed out after 5min"
    except Exception as e:
        return False, str(e)


def verify_fix(test_cmd: str) -> tuple[bool, str]:
    """Run test_cmd to verify a fix worked."""
    try:
        result = subprocess.run(
            ["bash", "-c", test_cmd],
            capture_output=True, text=True, timeout=60,
        )
        return result.returncode == 0, (result.stdout + result.stderr)[:300]
    except subprocess.TimeoutExpired:
        return False, "test_cmd timed out after 60s"
    except Exception as e:
        return False, str(e)


# ── Escalation ────────────────────────────────────────────────────────────────

def escalate_to_claude_code(
    entry: dict,
    reasoning: Optional[dict],
    aider_failure: Optional[str] = None,
) -> None:
    """Write a claude_tasks JSON file and send Telegram alert."""
    job = entry["job"]
    CLAUDE_TASKS_DIR.mkdir(parents=True, exist_ok=True)
    task_file = CLAUDE_TASKS_DIR / f"{job}_{int(time.time())}.json"

    payload = {
        "job": job,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "error_summary": entry.get("error_summary", ""),
        "log_tail": entry.get("log_tail", "")[-1000:],
        "files_implicated": entry.get("files_implicated", []),
        "classification": entry.get("classification", {}),
        "dlq_reasoning": reasoning,
        "fix_instruction": reasoning.get("fix_instruction") if reasoning else None,
        "aider_failure_reason": aider_failure,
        "test_cmd": None,  # filled below if available
        "priority": "HIGH" if entry.get("classification", {}).get("type") == "DETERMINISTIC" else "NORMAL",
    }

    # Try to get test_cmd from registry
    try:
        reg = load_registry()
        payload["test_cmd"] = reg.get(job, {}).get("test_cmd")
    except Exception:
        pass

    task_file.write_text(json.dumps(payload, indent=2))
    logger.info(f"{job}: escalated to Claude Code → {task_file}")

    send_telegram(
        f"🔴 Escalated to Claude Code: `{job}`\n"
        f"Error: {entry.get('error_summary','(empty)')[:80]}\n"
        f"Task file: {task_file}"
    )


# ── Main entry processor ──────────────────────────────────────────────────────

def process_entry(entry: dict, registry: dict) -> str:
    """
    Process one DLQ entry. Returns action taken:
    'skipped_preflight', 'retried_ok', 'aider_fixed', 'escalated', 'abandoned'
    """
    job = entry["job"]
    error = entry.get("error_summary", "")
    classification = entry.get("classification", {})
    subtype = classification.get("subtype", "")
    attempts = entry.get("autopilot_attempts", 0)
    files = entry.get("files_implicated", [])
    reg = registry.get(job, {})

    # ── Pre-flight checks ──────────────────────────────────────────────────────

    # 1. Max attempts exceeded
    if attempts >= MAX_ATTEMPTS:
        logger.info(f"{job}: max attempts ({MAX_ATTEMPTS}) reached → abandoning")
        escalate_to_claude_code(entry, None)
        return "abandoned"

    # 2. Entry too old with empty error — misdiagnosed artifact
    added_ts = entry.get("added_ts", 0)
    if not error and (time.time() - added_ts) > DLQ_TTL_S:
        logger.info(f"{job}: empty error + >48h old → archiving")
        return "archived"

    # 3. Classifier itself failed — no point in running LLM reasoning again
    if subtype in CLASSIFIER_FAILURE_SUBTYPES:
        logger.info(f"{job}: subtype={subtype} (classifier failure) → escalating directly")
        escalate_to_claude_code(entry, None)
        return "skipped_preflight"

    # 4. Error too short to reason about
    if len(error) < MIN_ERROR_LEN:
        logger.info(f"{job}: error too short ({len(error)} chars) → escalating directly")
        escalate_to_claude_code(entry, None)
        return "skipped_preflight"

    # ── LLM Reasoning ─────────────────────────────────────────────────────────
    reasoning = claude_reason(entry)
    if reasoning is None:
        logger.warning(f"{job}: reasoning failed → escalating")
        escalate_to_claude_code(entry, None)
        return "escalated"

    confidence = reasoning["confidence"]
    needs_code = reasoning["needs_code_change"]
    logger.info(f"{job}: reasoning → confidence={confidence:.2f} needs_code={needs_code} type={reasoning['fix_type']}")

    # ── Tier 1: high-confidence no-code retry ─────────────────────────────────
    if confidence >= CONFIDENCE_RETRY and not needs_code:
        restart_cmd = reg.get("restart_cmd")
        if restart_cmd:
            try:
                result = subprocess.run(
                    ["bash", "-c", restart_cmd],
                    capture_output=True, text=True, timeout=60,
                )
                if result.returncode == 0:
                    logger.info(f"{job}: retry OK ✅")
                    send_telegram(f"✅ Auto-retried `{job}` successfully")
                    return "retried_ok"
            except Exception as e:
                logger.warning(f"{job}: retry failed: {e}")

    # ── Tier 2: high-confidence code change via Aider ─────────────────────────
    if (
        confidence >= CONFIDENCE_AIDER
        and needs_code
        and job not in AIDER_BLOCKLIST
        and files and files != ["unknown"]
        and any(os.path.exists(os.path.expanduser(f)) for f in files if f != "unknown")
        and reg.get("test_cmd")
    ):
        logger.info(f"{job}: dispatching Aider")
        aider_ok, aider_out = dispatch_aider(entry, reasoning, registry)

        if aider_ok:
            verified, _ = verify_fix(reg["test_cmd"])
            if verified:
                logger.info(f"{job}: Aider fix verified ✅")
                send_telegram(f"✅ Aider auto-fixed `{job}`: {reasoning['fix_instruction'][:80]}")
                return "aider_fixed"

        logger.warning(f"{job}: Aider failed or unverified → escalating")
        escalate_to_claude_code(entry, reasoning, aider_out)
        return "escalated"

    # ── Tier 3: escalate to Claude Code ──────────────────────────────────────
    logger.info(f"{job}: confidence={confidence:.2f} or conditions not met → escalating")
    escalate_to_claude_code(entry, reasoning)
    return "escalated"


# ── Main ──────────────────────────────────────────────────────────────────────

def run_autopilot() -> None:
    logger.info("=== DLQ Autopilot run start ===")
    start = time.time()

    fd = acquire_lock()
    if fd is None:
        return

    try:
        queue = load_dlq()
        registry = load_registry()
        logger.info(f"DLQ entries: {len(queue)}")

        if not queue:
            logger.info("DLQ empty — nothing to do")
            return

        results = {}
        updated_queue = []

        for entry in queue:
            job = entry["job"]
            action = process_entry(entry, registry)
            results[job] = action

            if action in ("retried_ok", "aider_fixed", "archived"):
                # Remove from DLQ on success or archive
                pass
            elif action == "abandoned":
                entry["status"] = "abandoned"
                entry["autopilot_attempts"] = entry.get("autopilot_attempts", 0) + 1
                updated_queue.append(entry)
            else:
                # escalated / skipped_preflight — keep in DLQ, increment attempts
                entry["autopilot_attempts"] = entry.get("autopilot_attempts", 0) + 1
                updated_queue.append(entry)

        save_dlq(updated_queue)

        duration = time.time() - start
        fixed = sum(1 for a in results.values() if a in ("retried_ok", "aider_fixed"))
        escalated = sum(1 for a in results.values() if a == "escalated")
        skipped = sum(1 for a in results.values() if a == "skipped_preflight")

        logger.info(
            f"=== DLQ Autopilot done: {len(queue)} processed, "
            f"{fixed} fixed, {escalated} escalated, {skipped} skipped "
            f"in {duration:.1f}s ==="
        )

        # Write sentinel state
        state_dir = AGENT_DIR / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        state_file = state_dir / "dlq_autopilot.last.json"
        state_file.write_text(json.dumps({
            "job": "dlq_autopilot",
            "status": "ok",
            "detail": f"processed={len(queue)} fixed={fixed} escalated={escalated}",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }))

    finally:
        release_lock(fd)


if __name__ == "__main__":
    run_autopilot()
```

**Tests:**

```bash
# 1. Dry run on current DLQ — should not fix anything (all no_api_key subtype → skipped_preflight)
python3 ~/scripts/dlq_autopilot.py
# Expected: all entries → skipped_preflight, all escalated to claude_tasks/

# 2. Lock test — run two instances in parallel
python3 ~/scripts/dlq_autopilot.py & python3 ~/scripts/dlq_autopilot.py &
wait
# Expected: one run proceeds, one logs "Lock held by another process"

# 3. State file written
cat ~/.agent/decisions/state/dlq_autopilot.last.json
# Expected: {"job": "dlq_autopilot", "status": "ok", ...}
```

---

## Task 5: LaunchAgent plist for dlq_autopilot

**Files:**

- Create: `~/Library/LaunchAgents/com.nuzantara.dlq-autopilot.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nuzantara.dlq-autopilot</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3</string>
        <string>/Users/nuzantara/scripts/dlq_autopilot.py</string>
    </array>
    <key>StartInterval</key>
    <integer>1800</integer>
    <key>RunAtLoad</key>
    <false/>
    <key>StandardOutPath</key>
    <string>/Users/nuzantara/logs/dlq_autopilot.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/nuzantara/logs/dlq_autopilot.error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/Users/nuzantara/.pyenv/versions/3.11.11/bin</string>
        <key>HOME</key>
        <string>/Users/nuzantara</string>
        <key>TELEGRAM_BOT_TOKEN</key>
        <string>8295471667:AAHglwz8p8LxFnDgctmXuCs5aZa6lY78QO8</string>
        <key>TELEGRAM_ADMIN_CHAT_ID</key>
        <string>1813875994</string>
    </dict>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.nuzantara.dlq-autopilot.plist
launchctl list | grep dlq-autopilot
# Expected: entry present, exit code 0
```

---

## Task 6: job_registry.json + CLAUDE.md

**Files:**

- Modify: `~/.agent/decisions/job_registry.json`
- Modify: `~/Desktop/nuzantara/CLAUDE.md`

### job_registry.json — add entry

```json
"dlq_autopilot": {
  "host": "Nuzantara",
  "type": "launchagent",
  "plist": "com.nuzantara.dlq-autopilot",
  "schedule_seconds": 1800,
  "staleness_threshold_s": 5400,
  "restart_cmd": "launchctl kickstart -k gui/$(id -u)/com.nuzantara.dlq-autopilot",
  "test_cmd": "python3 /Users/nuzantara/scripts/dlq_autopilot.py --dry-run",
  "sentinel_state": "dlq_autopilot",
  "_note": "DLQ autopilot — Aider+Claude Code self-healer. State: .agent/decisions/state/dlq_autopilot.last.json"
}
```

### CLAUDE.md — add §19

After §18 (CRITICAL OPERATIONAL RULES), add:

````markdown
## 19. Claude Code Escalation Tasks (leggere a inizio sessione)

Quando il DLQ Autopilot non riesce a fixare un job (Aider fallisce o confidenza bassa),
crea un file in `~/.agent/decisions/claude_tasks/`. **Leggi sempre questa directory
a inizio sessione**, esattamente come `shared/escalations.json`.

```bash
ls ~/.agent/decisions/claude_tasks/ 2>/dev/null | head -10
```
````

Ogni file contiene `job`, `error_summary`, `log_tail`, `files_implicated`,
`dlq_reasoning` (output DeepSeek/Claude), `fix_instruction`, `test_cmd`.

**Regola:** lavora sui claude_tasks in ordine di `priority` (HIGH prima), poi `created_at`.
Dopo aver fixato: cancella il file + esegui `test_cmd` per verifica.

```

---

## Rollout Order

1. Task 1 (CB atomic) — nessun rischio, deploy immediato
2. Task 2 (classifier patterns) — deploy + reload sentinel
3. Task 3 (forced HALF_OPEN) — dopo Task 1 (dipende da `_atomic_save`)
4. Task 6 (CLAUDE.md + registry) — deploy
5. Task 4 + 5 (dlq_autopilot + plist) — deploy per ultimi, dopo smoke test

Ogni task è atomico e reversibile. In caso di problemi: `launchctl unload` + `git stash`.
```
