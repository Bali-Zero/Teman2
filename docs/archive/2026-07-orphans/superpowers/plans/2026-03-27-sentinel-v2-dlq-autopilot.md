# Sentinel V2 + DLQ Autopilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the 4 operational gaps in the existing Sentinel (12 frozen circuit breakers, 18 rotting DLQ entries, no OpenClaw pattern, broken LLM classifier) and add a DLQ Autopilot LaunchAgent that autonomously fixes jobs via Aider, escalating to Claude Code when Aider cannot.

**Architecture:** Patch-and-extend the existing `~/scripts/` infrastructure — no new frameworks. Three surgical edits to existing files + two new files (`dlq_autopilot.py` + LaunchAgent plist). Circuit breaker writes become atomic via `fcntl.flock + tempfile.mkstemp + os.replace`. DLQ processing pre-flights skip misdiagnosed entries. Aider is gated by an explicit blocklist, real file paths, and `test_cmd` presence.

**Tech Stack:** Python 3.11 (pyenv 3.11.11), macOS LaunchAgent, fcntl locking, Aider, Claude CLI (`claude --print`), Telegram Bot API, existing `sentinel_lib/` library.

---

## File Map

| File                                                       | Action | Change                                                            |
| ---------------------------------------------------------- | ------ | ----------------------------------------------------------------- |
| `~/scripts/sentinel_lib/circuit_breaker.py`                | MODIFY | Replace `_save()` with atomic `_atomic_save()` via fcntl          |
| `~/scripts/sentinel_lib/classifier.py`                     | MODIFY | Add OpenClaw `consecutiveErrors` patterns                         |
| `~/scripts/nuzantara-sentinel.py`                          | MODIFY | Add `_force_halfopen_stale_circuits()` called in `run_sentinel()` |
| `~/scripts/dlq_autopilot.py`                               | CREATE | DLQ autopilot main (~250 lines)                                   |
| `~/Library/LaunchAgents/com.nuzantara.dlq-autopilot.plist` | CREATE | 30-min LaunchAgent                                                |
| `~/.agent/decisions/job_registry.json`                     | MODIFY | Add `dlq_autopilot` entry                                         |
| `~/Desktop/nuzantara/CLAUDE.md`                            | MODIFY | Add §19 escalation tasks instruction                              |

**Rollout order:** Task 1 → Task 2 → Task 3 → Task 6 → Tasks 4+5 (last, after smoke test).

---

## Task 1: Atomic writes in circuit_breaker.py

**Files:**

- Modify: `~/scripts/sentinel_lib/circuit_breaker.py`
- Test: inline Python (no pytest — standalone script)

**Context:** `_save()` currently uses bare `open(STATE_FILE, "w")`. The Sentinel (5min) and new DLQ Autopilot (30min) can overlap and corrupt the JSON file. Replace with an atomic write via `fcntl.flock + tempfile.mkstemp + os.replace`. The function is called from `record_success()`, `record_failure()`, and `_set_state()` — all three must use the new function. Also export `_atomic_save` so `nuzantara-sentinel.py` can call it from `_force_halfopen_stale_circuits()` (Task 3).

- [ ] **Step 1: Read the current file**

```bash
cat ~/scripts/sentinel_lib/circuit_breaker.py
```

Expected: 66 lines. Functions: `_load`, `_save`, `get_state`, `record_success`, `record_failure`, `_set_state`.

- [ ] **Step 2: Write the updated file**

Replace `~/scripts/sentinel_lib/circuit_breaker.py` with this complete file:

```python
"""Per-job circuit breaker: CLOSED → OPEN → HALF_OPEN → CLOSED."""
import fcntl
import json
import os
import tempfile
import time
from typing import Literal

STATE_FILE = os.path.expanduser("~/.agent/decisions/circuit_breakers.json")
OPEN_TIMEOUT_S = 1800  # 30 min before HALF_OPEN test
CircuitState = Literal["CLOSED", "OPEN", "HALF_OPEN"]


def _load() -> dict:
    try:
        return json.loads(open(STATE_FILE).read())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _atomic_save(data: dict) -> None:
    """Atomic write via fcntl + tempfile + os.replace. Safe for concurrent callers."""
    dir_ = os.path.dirname(STATE_FILE)
    os.makedirs(dir_, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            json.dump(data, f, indent=2)
            fcntl.flock(f, fcntl.LOCK_UN)
        os.replace(tmp, STATE_FILE)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def get_state(job: str) -> CircuitState:
    data = _load()
    job_data = data.get(job, {})
    state = job_data.get("state", "CLOSED")
    opened_at = job_data.get("opened_at", 0)

    if state == "OPEN" and (time.time() - opened_at) > OPEN_TIMEOUT_S:
        # Transition to HALF_OPEN for a test
        _set_state(job, "HALF_OPEN")
        return "HALF_OPEN"
    return state


def record_success(job: str) -> None:
    """Call after a successful run — resets to CLOSED."""
    data = _load()
    data[job] = {"state": "CLOSED", "failures": 0, "opened_at": 0}
    _atomic_save(data)


def record_failure(job: str) -> CircuitState:
    """Call after a failed run — may trip to OPEN. Returns new state."""
    data = _load()
    job_data = data.get(job, {"state": "CLOSED", "failures": 0, "opened_at": 0})
    job_data["failures"] = job_data.get("failures", 0) + 1

    if job_data["failures"] >= 3 or job_data.get("state") == "HALF_OPEN":
        job_data["state"] = "OPEN"
        job_data["opened_at"] = time.time()
    data[job] = job_data
    _atomic_save(data)
    return job_data["state"]


def _set_state(job: str, state: CircuitState) -> None:
    data = _load()
    job_data = data.get(job, {})
    job_data["state"] = state
    if state == "HALF_OPEN":
        job_data["opened_at"] = time.time()
    data[job] = job_data
    _atomic_save(data)
```

- [ ] **Step 3: Write the concurrency test**

```bash
cat > /tmp/test_atomic_cb.py << 'EOF'
"""Test that concurrent record_failure() calls don't lose writes."""
import subprocess, json, os, sys, time

# Spawn 2 subprocesses, each calling record_failure 10 times
script = '''
import sys, os
sys.path.insert(0, os.path.expanduser("~/scripts"))
from sentinel_lib.circuit_breaker import record_failure
for _ in range(10):
    record_failure("atomic_test_job")
'''

p1 = subprocess.Popen([sys.executable, "-c", script])
p2 = subprocess.Popen([sys.executable, "-c", script])
p1.wait()
p2.wait()

import json
cb_file = os.path.expanduser("~/.agent/decisions/circuit_breakers.json")
data = json.loads(open(cb_file).read())
failures = data.get("atomic_test_job", {}).get("failures", 0)

# Clean up test key
del data["atomic_test_job"]
import tempfile, fcntl
dir_ = os.path.dirname(cb_file)
fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
with os.fdopen(fd, "w") as f:
    fcntl.flock(f, fcntl.LOCK_EX)
    json.dump(data, f, indent=2)
    fcntl.flock(f, fcntl.LOCK_UN)
os.replace(tmp, cb_file)

if failures == 20:
    print(f"PASS: failures={failures} (expected 20)")
else:
    print(f"FAIL: failures={failures}, expected 20 — writes were lost")
    sys.exit(1)
EOF
```

- [ ] **Step 4: Run the test**

```bash
/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3 /tmp/test_atomic_cb.py
```

Expected output: `PASS: failures=20 (expected 20)`

- [ ] **Step 5: Verify sentinel still imports correctly**

```bash
/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3 -c "
import sys; sys.path.insert(0, '/Users/nuzantara/scripts')
from sentinel_lib.circuit_breaker import _load, _atomic_save, record_success, record_failure, get_state
print('Import OK')
"
```

Expected: `Import OK`

- [ ] **Step 6: Commit**

```bash
cd ~/scripts
git add sentinel_lib/circuit_breaker.py
git commit -m "fix(sentinel): atomic writes in circuit_breaker via fcntl+tempfile"
```

---

## Task 2: OpenClaw patterns in classifier.py

**Files:**

- Modify: `~/scripts/sentinel_lib/classifier.py`
- Test: inline Python

**Context:** The classifier has no rule for `consecutiveErrors=N` — the most common OpenClaw failure pattern. Every such error hits the UNKNOWN fallback and goes to DLQ unclassified. Add:

- 1-2 consecutive errors → TRANSIENT (safe to retry)
- 3+ consecutive errors → DETERMINISTIC `openclaw_persistent_error` (restart needed)

The current `TRANSIENT_PATTERNS` is a list of regex strings (line 9-27). The current `DETERMINISTIC_PATTERNS` is a list of `(regex, subtype)` tuples (line 31-43). `FIX_PATTERNS` is a dict (line 45-82). Add to all three.

- [ ] **Step 1: Read the current file to confirm line numbers**

```bash
grep -n "TRANSIENT_PATTERNS\|DETERMINISTIC_PATTERNS\|FIX_PATTERNS\|consecutiveErrors" ~/scripts/sentinel_lib/classifier.py
```

Expected: `TRANSIENT_PATTERNS` at line 9, `DETERMINISTIC_PATTERNS` at line 31, `FIX_PATTERNS` at line 45. No `consecutiveErrors` matches.

- [ ] **Step 2: Add transient pattern for 1-2 consecutive errors**

Insert after the last entry in `TRANSIENT_PATTERNS` (after `r"cron: job execution timed out"` at line 27, before the closing `]`):

In the file `~/scripts/sentinel_lib/classifier.py`, replace:

```python
    # Gateway-side timeout: job was too slow, not a code error.
    r"cron: job execution timed out",
]
```

with:

```python
    # Gateway-side timeout: job was too slow, not a code error.
    r"cron: job execution timed out",
    # OpenClaw 1-2 consecutive errors — transient blip, safe to retry.
    r"consecutiveErrors=[12][,\s]",
]
```

- [ ] **Step 3: Add deterministic pattern for 3+ consecutive errors**

In `DETERMINISTIC_PATTERNS`, replace:

```python
    # OpenClaw job config errors: wrong payload type or missing API key in the agent env.
    (r"isolated job requires payload\.kind=agentTurn", "job_config_error"),
    (r"No API key found for provider", "missing_api_key"),
]
```

with:

```python
    # OpenClaw job config errors: wrong payload type or missing API key in the agent env.
    (r"isolated job requires payload\.kind=agentTurn", "job_config_error"),
    (r"No API key found for provider", "missing_api_key"),
    # OpenClaw persistent failure: 3+ consecutive errors → restart needed.
    (r"consecutiveErrors=[3-9]\d*[,\s]", "openclaw_persistent_error"),
]
```

- [ ] **Step 4: Add fix pattern for openclaw_persistent_error**

In `FIX_PATTERNS`, after the closing brace of `"job_config_error"` entry (before the final `}`), add:

```python
    "openclaw_persistent_error": {
        "description": "OpenClaw job failing 3+ consecutive times — restart needed",
        "fix_instruction": (
            "Trigger the job manually via the OpenClaw UI or: "
            "openclaw cron run <openclaw_id> --timeout 30000. "
            "If it fails again, check ~/.openclaw/workspace/logs/ for the agent turn error."
        ),
        "confidence": 0.90,
    },
```

- [ ] **Step 5: Write the classifier test**

```bash
cat > /tmp/test_classifier.py << 'EOF'
import sys, os
sys.path.insert(0, os.path.expanduser("~/scripts"))
from sentinel_lib.classifier import classify

# 1 consecutive error → TRANSIENT
r = classify("OpenClaw consecutiveErrors=1, lastStatus=error", 0)
assert r["type"] == "TRANSIENT", f"Expected TRANSIENT, got {r['type']}"
print(f"Test 1 PASS: consecutiveErrors=1 → TRANSIENT")

# 2 consecutive errors → TRANSIENT
r = classify("OpenClaw consecutiveErrors=2, lastStatus=error", 0)
assert r["type"] == "TRANSIENT", f"Expected TRANSIENT, got {r['type']}"
print(f"Test 2 PASS: consecutiveErrors=2 → TRANSIENT")

# 3 consecutive errors → DETERMINISTIC openclaw_persistent_error
r = classify("OpenClaw consecutiveErrors=3, lastStatus=error", 0)
assert r["type"] == "DETERMINISTIC", f"Expected DETERMINISTIC, got {r['type']}"
assert r["subtype"] == "openclaw_persistent_error", f"Expected openclaw_persistent_error, got {r['subtype']}"
assert r["fix_pattern"]["confidence"] == 0.90, f"Expected 0.90 confidence, got {r['fix_pattern']['confidence']}"
print(f"Test 3 PASS: consecutiveErrors=3 → DETERMINISTIC openclaw_persistent_error confidence=0.90")

# 15 consecutive errors → DETERMINISTIC (matches [3-9]\d*)
r = classify("OpenClaw consecutiveErrors=15, lastStatus=error", 0)
assert r["type"] == "DETERMINISTIC", f"Expected DETERMINISTIC, got {r['type']}"
assert r["subtype"] == "openclaw_persistent_error"
print(f"Test 4 PASS: consecutiveErrors=15 → DETERMINISTIC")

# Existing pattern unaffected
r = classify("SyntaxError: invalid syntax on line 42", 0)
assert r["type"] == "DETERMINISTIC"
assert r["subtype"] == "syntax_error"
print(f"Test 5 PASS: SyntaxError still classified correctly")

print("\nAll 5 classifier tests PASS")
EOF
```

- [ ] **Step 6: Run the test**

```bash
/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3 /tmp/test_classifier.py
```

Expected output:

```
Test 1 PASS: consecutiveErrors=1 → TRANSIENT
Test 2 PASS: consecutiveErrors=2 → TRANSIENT
Test 3 PASS: consecutiveErrors=3 → DETERMINISTIC openclaw_persistent_error confidence=0.90
Test 4 PASS: consecutiveErrors=15 → DETERMINISTIC
Test 5 PASS: SyntaxError still classified correctly

All 5 classifier tests PASS
```

- [ ] **Step 7: Commit**

```bash
cd ~/scripts
git add sentinel_lib/classifier.py
git commit -m "feat(sentinel): add OpenClaw consecutiveErrors classification patterns"
```

---

## Task 3: Forced HALF_OPEN probe in nuzantara-sentinel.py

**Files:**

- Modify: `~/scripts/nuzantara-sentinel.py`
- Test: inline Python

**Context:** 12 circuit breakers are stuck OPEN. They transition to HALF_OPEN only when `process_job()` is called for them AND the 30-min `OPEN_TIMEOUT_S` has expired. But stale jobs never write a state file, so they're never in `states` and never processed — they stay OPEN forever. Fix: at the top of `run_sentinel()`, after `check_dead_man_switch()` (line 455), add a call to `_force_halfopen_stale_circuits()` which directly force-updates any CB that has been OPEN > 2 hours. This function must import `_atomic_save` from `circuit_breaker` (Task 1) — not use any old `_save`.

The `run_sentinel()` function starts at line 450. The `check_dead_man_switch()` call is at line 455. The `check_and_repair_openclaw()` call is at line 458.

- [ ] **Step 1: Read lines 448-465 of nuzantara-sentinel.py to confirm structure**

```bash
sed -n '448,465p' ~/scripts/nuzantara-sentinel.py
```

Expected output:

```python
# ─── Main ─────────────────────────────────────────────────────────────────────

def run_sentinel() -> None:
    logger.info("=== Sentinel run start ===")
    start = time.time()
    registry = load_registry()
    states = collect_state_files()
    check_dead_man_switch()

    # Tier 0: verify OpenClaw gateway health before processing jobs
    openclaw_is_down = not check_and_repair_openclaw()
```

- [ ] **Step 2: Add FORCED_HALFOPEN_AGE_S constant and the function**

Add these lines after the `OPENCLAW_RESTART_COOLDOWN_S = 600` constant at line 53 (i.e. after the block of module-level constants):

Find this block:

```python
MAX_RETRIES = 3
BACKOFF_BASE_S = 60
BACKOFF_CAP_S = 600
OPENCLAW_RESTART_COOLDOWN_S = 600  # 10 minutes between restarts
```

Replace with:

```python
MAX_RETRIES = 3
BACKOFF_BASE_S = 60
BACKOFF_CAP_S = 600
OPENCLAW_RESTART_COOLDOWN_S = 600  # 10 minutes between restarts
FORCED_HALFOPEN_AGE_S = 7200      # 2 hours — force HALF_OPEN on stuck-OPEN circuits


def _force_halfopen_stale_circuits() -> None:
    """
    Force HALF_OPEN on any circuit that has been OPEN for > FORCED_HALFOPEN_AGE_S.
    Called inside run_sentinel() only — single writer, no race condition with DLQ autopilot.
    Imports _atomic_save from circuit_breaker to use the safe write path (Task 1).
    """
    from sentinel_lib.circuit_breaker import _load, _atomic_save
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

- [ ] **Step 3: Call the function inside run_sentinel()**

Find in `run_sentinel()`:

```python
    registry = load_registry()
    states = collect_state_files()
    check_dead_man_switch()

    # Tier 0: verify OpenClaw gateway health before processing jobs
    openclaw_is_down = not check_and_repair_openclaw()
```

Replace with:

```python
    registry = load_registry()
    states = collect_state_files()
    check_dead_man_switch()
    _force_halfopen_stale_circuits()  # Unblock circuits stuck OPEN > 2h

    # Tier 0: verify OpenClaw gateway health before processing jobs
    openclaw_is_down = not check_and_repair_openclaw()
```

- [ ] **Step 4: Write the probe test**

```bash
cat > /tmp/test_halfopen_probe.py << 'EOF'
import sys, os, time, json
sys.path.insert(0, os.path.expanduser("~/scripts"))
from sentinel_lib.circuit_breaker import _load, _atomic_save

# 1. Plant a stale OPEN CB (opened 8000 seconds ago)
data = _load()
data["test_stale_circuit_abc"] = {
    "state": "OPEN",
    "failures": 5,
    "opened_at": time.time() - 8000,
}
# Also plant a fresh OPEN CB (opened 30 seconds ago — should NOT be touched)
data["test_fresh_circuit_xyz"] = {
    "state": "OPEN",
    "failures": 2,
    "opened_at": time.time() - 30,
}
_atomic_save(data)

# 2. Run the probe function
from nuzantara_sentinel import _force_halfopen_stale_circuits
_force_halfopen_stale_circuits()

# 3. Verify
data2 = _load()
stale_state = data2.get("test_stale_circuit_abc", {}).get("state")
fresh_state = data2.get("test_fresh_circuit_xyz", {}).get("state")

assert stale_state == "HALF_OPEN", f"FAIL: stale CB should be HALF_OPEN, got {stale_state}"
assert fresh_state == "OPEN", f"FAIL: fresh CB should remain OPEN, got {fresh_state}"
print(f"PASS: stale → HALF_OPEN, fresh → OPEN (unchanged)")

# 4. Cleanup
del data2["test_stale_circuit_abc"]
del data2["test_fresh_circuit_xyz"]
_atomic_save(data2)
EOF
```

- [ ] **Step 5: Run the test**

```bash
/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3 /tmp/test_halfopen_probe.py
```

Expected: `PASS: stale → HALF_OPEN, fresh → OPEN (unchanged)`

- [ ] **Step 6: Verify sentinel dry-run still works**

```bash
/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3 -c "
import sys; sys.path.insert(0, '/Users/nuzantara/scripts')
from nuzantara_sentinel import load_registry, _force_halfopen_stale_circuits
r = load_registry()
print(f'Registry loaded: {len(r)} jobs')
_force_halfopen_stale_circuits()
print('_force_halfopen_stale_circuits() OK — no exceptions')
"
```

Expected: `Registry loaded: N jobs` then `_force_halfopen_stale_circuits() OK — no exceptions`

- [ ] **Step 7: Commit**

```bash
cd ~/scripts
git add nuzantara-sentinel.py
git commit -m "feat(sentinel): force HALF_OPEN on circuits stuck OPEN > 2h"
```

---

## Task 4: dlq_autopilot.py

**Files:**

- Create: `~/scripts/dlq_autopilot.py`
- Test: manual smoke run

**Context:** The DLQ has 18 rotting entries, all with `subtype: no_api_key` (the LLM classifier silently fails because `ANTHROPIC_API_KEY` is not set in LaunchAgent env — and must NOT be set, as it conflicts with Claude CLI Max subscription). The autopilot pre-flight detects `subtype in CLASSIFIER_FAILURE_SUBTYPES` and escalates directly to `~/.agent/decisions/claude_tasks/` without calling the LLM again. For entries with real errors, it uses `claude --print` for one-shot reasoning, then dispatches Aider (with a hard blocklist) or escalates. A `fcntl` lock prevents concurrent runs. The script also writes `~/.agent/decisions/state/dlq_autopilot.last.json` so the Sentinel can monitor it.

Key constants:

- `AIDER_BLOCKLIST` = `{core_guardian, daily_ops_autopilot, learning_pipeline, seo_auto_fixer, weekly_review, weekly_report}`
- `CLASSIFIER_FAILURE_SUBTYPES` = `{no_api_key, llm_failed, no_error_text, unclassified}`
- `CONFIDENCE_RETRY` = 0.95 (no-code retry threshold)
- `CONFIDENCE_AIDER` = 0.90 (code change threshold)
- `LOCK_STALE_AGE_S` = 1500 (25min — stale lock detection)

- [ ] **Step 1: Create the logs directory**

```bash
mkdir -p ~/logs
```

- [ ] **Step 2: Write the file**

Create `~/scripts/dlq_autopilot.py` with this complete content:

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
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": f"🤖 DLQAutopilot | {message}",
        }).encode()
        urllib.request.urlopen(
            urllib.request.Request(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data=data,
            ),
            timeout=10,
        )
    except Exception:
        pass


# ── Claude CLI reasoning ───────────────────────────────────────────────────────

def claude_reason(entry: dict) -> Optional[dict]:
    """
    Ask Claude CLI to reason about a DLQ entry.
    Returns {fix_type, fix_instruction, confidence, needs_code_change} or None.
    Falls back gracefully on timeout, missing CLI, or JSON parse failure.
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
            capture_output=True,
            text=True,
            timeout=REASONING_TIMEOUT_S,
            env={**os.environ, "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"},
        )
        if result.returncode != 0:
            logger.warning(f"{job}: claude --print exit {result.returncode}")
            return None

        # Strip ANSI codes and extract first JSON object
        clean = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
        match = re.search(r"\{.*?\}", clean, re.DOTALL)
        if not match:
            logger.warning(f"{job}: no JSON in claude output")
            return None

        data = json.loads(match.group())
        required = {"fix_type", "fix_instruction", "confidence", "needs_code_change"}
        if not required.issubset(data.keys()):
            logger.warning(f"{job}: claude output missing required keys")
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
    Pre-conditions verified by caller:
      - files_implicated has ≥1 real path on disk
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

    # Stash before aider runs — allow git rollback on failure
    stash_label = f"dlq_autopilot_{job}_{int(time.time())}"
    subprocess.run(
        ["git", "stash", "push", "-m", stash_label],
        cwd=str(NUZANTARA_ROOT),
        capture_output=True,
    )

    try:
        result = subprocess.run(
            ["bash", dispatch_script, "aider-fix", prompt],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(NUZANTARA_ROOT),
        )
        success = result.returncode == 0
        output = (result.stdout + result.stderr)[:500]

        if not success:
            # Restore stash on failure
            subprocess.run(
                ["git", "stash", "pop"],
                cwd=str(NUZANTARA_ROOT),
                capture_output=True,
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
            capture_output=True,
            text=True,
            timeout=60,
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

    payload: dict = {
        "job": job,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "error_summary": entry.get("error_summary", ""),
        "log_tail": entry.get("log_tail", "")[-1000:],
        "files_implicated": entry.get("files_implicated", []),
        "classification": entry.get("classification", {}),
        "dlq_reasoning": reasoning,
        "fix_instruction": reasoning.get("fix_instruction") if reasoning else None,
        "aider_failure_reason": aider_failure,
        "test_cmd": None,
        "priority": (
            "HIGH"
            if entry.get("classification", {}).get("type") == "DETERMINISTIC"
            else "NORMAL"
        ),
    }

    try:
        reg = load_registry()
        payload["test_cmd"] = reg.get(job, {}).get("test_cmd")
    except Exception:
        pass

    task_file.write_text(json.dumps(payload, indent=2))
    logger.info(f"{job}: escalated to Claude Code → {task_file}")

    send_telegram(
        f"🔴 Escalated to Claude Code: `{job}`\n"
        f"Error: {entry.get('error_summary', '(empty)')[:80]}\n"
        f"Task file: {task_file.name}"
    )


# ── Main entry processor ──────────────────────────────────────────────────────

def process_entry(entry: dict, registry: dict) -> str:
    """
    Process one DLQ entry. Returns action taken:
    'skipped_preflight', 'retried_ok', 'aider_fixed', 'escalated', 'abandoned', 'archived'
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

    # 2. Entry too old with empty error — misdiagnosed artifact, safe to archive
    added_ts = entry.get("added_ts", 0)
    if not error and (time.time() - added_ts) > DLQ_TTL_S:
        logger.info(f"{job}: empty error + >48h old → archiving")
        return "archived"

    # 3. Classifier itself failed — LLM reasoning would fail for the same reason
    if subtype in CLASSIFIER_FAILURE_SUBTYPES:
        logger.info(f"{job}: subtype={subtype} (classifier failure) → escalating directly")
        escalate_to_claude_code(entry, None)
        return "skipped_preflight"

    # 4. Error too short to reason about reliably
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
    logger.info(
        f"{job}: reasoning → confidence={confidence:.2f} "
        f"needs_code={needs_code} type={reasoning['fix_type']}"
    )

    # ── Tier 1: high-confidence no-code retry ─────────────────────────────────
    if confidence >= CONFIDENCE_RETRY and not needs_code:
        restart_cmd = reg.get("restart_cmd")
        if restart_cmd:
            try:
                result = subprocess.run(
                    ["bash", "-c", restart_cmd],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode == 0:
                    logger.info(f"{job}: retry OK ✅")
                    send_telegram(f"✅ Auto-retried `{job}` successfully")
                    return "retried_ok"
            except Exception as e:
                logger.warning(f"{job}: retry failed: {e}")

    # ── Tier 2: high-confidence code change via Aider ─────────────────────────
    real_files = [
        f for f in files
        if f != "unknown" and os.path.exists(os.path.expanduser(f))
    ]
    if (
        confidence >= CONFIDENCE_AIDER
        and needs_code
        and job not in AIDER_BLOCKLIST
        and real_files
        and reg.get("test_cmd")
    ):
        logger.info(f"{job}: dispatching Aider (files: {real_files})")
        aider_ok, aider_out = dispatch_aider(entry, reasoning, registry)

        if aider_ok:
            verified, _ = verify_fix(reg["test_cmd"])
            if verified:
                logger.info(f"{job}: Aider fix verified ✅")
                send_telegram(
                    f"✅ Aider auto-fixed `{job}`: {reasoning['fix_instruction'][:80]}"
                )
                return "aider_fixed"

        logger.warning(f"{job}: Aider failed or unverified → escalating")
        escalate_to_claude_code(entry, reasoning, aider_out)
        return "escalated"

    # ── Tier 3: escalate to Claude Code ───────────────────────────────────────
    reason = (
        f"confidence={confidence:.2f}<threshold"
        if confidence < CONFIDENCE_AIDER
        else f"job_in_blocklist={job in AIDER_BLOCKLIST} no_real_files={not real_files}"
    )
    logger.info(f"{job}: {reason} → escalating to Claude Code")
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

        results: dict[str, str] = {}
        updated_queue = []

        for entry in queue:
            job = entry["job"]
            action = process_entry(entry, registry)
            results[job] = action

            if action in ("retried_ok", "aider_fixed", "archived"):
                pass  # Remove from DLQ
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

        # Write sentinel state file so Sentinel can monitor autopilot staleness
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

- [ ] **Step 3: Make the script executable**

```bash
chmod +x ~/scripts/dlq_autopilot.py
```

- [ ] **Step 4: Verify syntax**

```bash
/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3 -m py_compile ~/scripts/dlq_autopilot.py && echo "Syntax OK"
```

Expected: `Syntax OK`

- [ ] **Step 5: Smoke run — process current DLQ**

```bash
/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3 ~/scripts/dlq_autopilot.py
```

Expected log lines (all 18 entries have `subtype: no_api_key`):

```
DLQ entries: 18
<job>: subtype=no_api_key (classifier failure) → escalating directly
... (18 times)
DLQ Autopilot done: 18 processed, 0 fixed, 0 escalated, 18 skipped in ...s
```

18 JSON files should appear in `~/.agent/decisions/claude_tasks/`.

- [ ] **Step 6: Verify state file written**

```bash
cat ~/.agent/decisions/state/dlq_autopilot.last.json
```

Expected: `{"job": "dlq_autopilot", "status": "ok", "detail": "processed=18 fixed=0 escalated=0", "ts": "..."}`

- [ ] **Step 7: Test lock exclusion**

```bash
/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3 ~/scripts/dlq_autopilot.py &
/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3 ~/scripts/dlq_autopilot.py &
wait
```

Expected: one instance logs `Lock held by another process — skipping this run`

- [ ] **Step 8: Commit**

```bash
cd ~/scripts
git add dlq_autopilot.py
git commit -m "feat(dlq-autopilot): autonomous DLQ processor with Aider+Claude Code escalation"
```

---

## Task 5: LaunchAgent plist for dlq_autopilot

**Files:**

- Create: `~/Library/LaunchAgents/com.nuzantara.dlq-autopilot.plist`

**Context:** The autopilot runs every 30 minutes (1800 seconds). It must NOT have `ANTHROPIC_API_KEY` in its env — that would conflict with Claude CLI Max subscription. It needs `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ADMIN_CHAT_ID`. `RunAtLoad=false` so it doesn't trigger immediately on session login.

- [ ] **Step 1: Write the plist**

Create `~/Library/LaunchAgents/com.nuzantara.dlq-autopilot.plist`:

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

- [ ] **Step 2: Validate plist syntax**

```bash
plutil -lint ~/Library/LaunchAgents/com.nuzantara.dlq-autopilot.plist
```

Expected: `/Users/nuzantara/Library/LaunchAgents/com.nuzantara.dlq-autopilot.plist: OK`

- [ ] **Step 3: Load the LaunchAgent**

```bash
launchctl load ~/Library/LaunchAgents/com.nuzantara.dlq-autopilot.plist
```

Expected: no error output.

- [ ] **Step 4: Verify it is registered**

```bash
launchctl list | grep dlq-autopilot
```

Expected: one line like `- 0 com.nuzantara.dlq-autopilot` (PID empty = not currently running, exit 0 = no prior error).

- [ ] **Step 5: Trigger a manual run via launchctl to confirm plist is valid**

```bash
launchctl kickstart -k gui/$(id -u)/com.nuzantara.dlq-autopilot
sleep 5
tail -20 ~/logs/dlq_autopilot.log
```

Expected: log lines showing `=== DLQ Autopilot run start ===` and `=== DLQ Autopilot done ===`.

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/nuzantara
git add ~/Library/LaunchAgents/com.nuzantara.dlq-autopilot.plist
# Note: plist is outside the git repo — commit the spec/plan update only
git commit -m "feat(dlq-autopilot): install LaunchAgent plist (30min schedule)"
```

Note: the plist file itself is at `~/Library/LaunchAgents/` which is outside the git repo. Only the spec/plan documents go into git. To record the plist permanently, copy it to `~/Desktop/nuzantara/docs/infra/launchagents/com.nuzantara.dlq-autopilot.plist` and commit that copy.

---

## Task 6: job_registry.json + CLAUDE.md §19

**Files:**

- Modify: `~/.agent/decisions/job_registry.json`
- Modify: `~/Desktop/nuzantara/CLAUDE.md`

**Context:** Two registry/doc updates. First, add the `dlq_autopilot` job to `job_registry.json` so Sentinel can monitor the autopilot for staleness. Second, add §19 to `CLAUDE.md` so future Claude Code sessions read `claude_tasks/` at startup.

- [ ] **Step 1: Read the current registry structure**

```bash
/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3 -c "
import json
d = json.load(open('/Users/nuzantara/.agent/decisions/job_registry.json'))
jobs = d.get('jobs', {})
print(f'Total jobs: {len(jobs)}')
# Show one example entry structure
first = next(iter(jobs.items()))
print('Example key:', first[0])
print('Example value keys:', list(first[1].keys()))
"
```

Expected: `Total jobs: 29`, plus the key names of one entry (e.g. `host`, `type`, `plist`, `schedule_seconds`, `staleness_threshold_s`...).

- [ ] **Step 2: Add the dlq_autopilot entry**

Open `~/.agent/decisions/job_registry.json`, find the `"jobs"` dict, and add the following entry (it can go at the end of the dict, before the closing `}`):

```json
"dlq_autopilot": {
  "host": "Nuzantara",
  "type": "launchagent",
  "plist": "com.nuzantara.dlq-autopilot",
  "schedule_seconds": 1800,
  "staleness_threshold_s": 5400,
  "restart_cmd": "launchctl kickstart -k gui/501/com.nuzantara.dlq-autopilot",
  "test_cmd": "/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3 /Users/nuzantara/scripts/dlq_autopilot.py",
  "_note": "DLQ autopilot: Aider+Claude Code self-healer. State: ~/.agent/decisions/state/dlq_autopilot.last.json"
}
```

- [ ] **Step 3: Validate the registry JSON**

```bash
/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3 -c "
import json
d = json.load(open('/Users/nuzantara/.agent/decisions/job_registry.json'))
assert 'dlq_autopilot' in d['jobs'], 'dlq_autopilot entry missing'
entry = d['jobs']['dlq_autopilot']
assert entry['schedule_seconds'] == 1800
assert entry['staleness_threshold_s'] == 5400
print(f'Registry valid: {len(d[\"jobs\"])} jobs total, dlq_autopilot present')
"
```

Expected: `Registry valid: 30 jobs total, dlq_autopilot present`

- [ ] **Step 4: Add §19 to CLAUDE.md**

Open `~/Desktop/nuzantara/CLAUDE.md`. Find the last section (currently `## 18. CRITICAL OPERATIONAL RULES` or similar). After the last content of that section, append the following new section:

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
`dlq_reasoning` (output Claude CLI reasoning), `fix_instruction`, `test_cmd`.

**Regola:** lavora sui claude_tasks in ordine di `priority` (HIGH prima), poi `created_at`.
Dopo aver fixato: cancella il file con `rm ~/.agent/decisions/claude_tasks/<filename>.json`
e verifica con `test_cmd`.

````

- [ ] **Step 5: Verify CLAUDE.md has the new section**

```bash
grep -n "Claude Code Escalation Tasks\|claude_tasks" ~/Desktop/nuzantara/CLAUDE.md | head -10
````

Expected: at least 3 matching lines (the section header + `ls` command + `rm` command).

- [ ] **Step 6: Commit both changes**

```bash
cd ~/Desktop/nuzantara
git add CLAUDE.md
git commit -m "docs(sentinel): add §19 Claude Code escalation tasks to CLAUDE.md"

# Also copy plist to docs/infra for git tracking
mkdir -p docs/infra/launchagents
cp ~/Library/LaunchAgents/com.nuzantara.dlq-autopilot.plist docs/infra/launchagents/
git add docs/infra/launchagents/com.nuzantara.dlq-autopilot.plist
git commit -m "docs(infra): track dlq-autopilot LaunchAgent plist in repo"
```

The `job_registry.json` is at `~/.agent/decisions/` which is outside the git repo — no commit needed for that file.

---

## Verification: Full end-to-end smoke test

After all 6 tasks are complete:

- [ ] **Smoke test 1: Sentinel imports all new code cleanly**

```bash
/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3 -c "
import sys; sys.path.insert(0, '/Users/nuzantara/scripts')
from sentinel_lib.circuit_breaker import _atomic_save, _load, record_success, record_failure
from sentinel_lib.classifier import classify
r = classify('OpenClaw consecutiveErrors=5, lastStatus=error', 0)
assert r['subtype'] == 'openclaw_persistent_error', r
from nuzantara_sentinel import _force_halfopen_stale_circuits, run_sentinel
import dlq_autopilot
print('All imports and assertions PASS')
"
```

Expected: `All imports and assertions PASS`

- [ ] **Smoke test 2: Sentinel dry-run (read-only — do NOT actually run; check logs)**

```bash
# Check the Sentinel is running from LaunchAgent
launchctl list | grep com.nuzantara.sentinel
# Expected: entry present
tail -5 ~/logs/sentinel.log
# Expected: recent run line with "=== Sentinel done ==="
```

- [ ] **Smoke test 3: DLQ autopilot registered in Sentinel monitoring**

```bash
/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3 -c "
import json
reg = json.load(open('/Users/nuzantara/.agent/decisions/job_registry.json'))
assert 'dlq_autopilot' in reg['jobs']
print('dlq_autopilot in registry: OK')
"
```

Expected: `dlq_autopilot in registry: OK`

- [ ] **Smoke test 4: claude_tasks populated from previous smoke run (Task 4 Step 5)**

```bash
ls ~/.agent/decisions/claude_tasks/ | wc -l
```

Expected: 18 files (one per DLQ entry that had `subtype: no_api_key`)

- [ ] **Smoke test 5: Check one claude_tasks file has correct structure**

```bash
ls ~/.agent/decisions/claude_tasks/ | head -1 | xargs -I{} /Users/nuzantara/.pyenv/versions/3.11.11/bin/python3 -c "
import json, sys
d = json.load(open('/Users/nuzantara/.agent/decisions/claude_tasks/' + sys.argv[1]))
assert 'job' in d and 'error_summary' in d and 'priority' in d
print(f'Task file OK: job={d[\"job\"]} priority={d[\"priority\"]}')
" {}
```

Expected: `Task file OK: job=<name> priority=NORMAL` (or HIGH)
