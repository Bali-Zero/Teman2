# Automation Self-Healing Sentinel — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 4-tier self-healing system that monitors all 24 Nuzantara automations (Pro + Air), detects failures, retries transients automatically, dispatches Aider for known code fixes, and summons Claude Code for complex bugs.

**Architecture:** File-based state machine — each job writes `~/.agent/decisions/state/<job>.last.json` as a heartbeat. The Sentinel on Air reads Pro's state via SSH every 5 minutes, detects failures and staleness, then escalates through tiers: Sentinel retry → Aider fix → Claude Code → Zero.

**Tech Stack:** Python 3.9+ (stdlib only for Sentinel), bash (heartbeat wrappers), launchd (scheduling on Air), existing `ai-dispatch.sh` for Tier 2, Telegram bot API for alerts.

---

## File Map

| File                                                  | Action             | Responsibility                                                                  |
| ----------------------------------------------------- | ------------------ | ------------------------------------------------------------------------------- |
| `~/.agent/decisions/state/`                           | Create dir         | Per-job heartbeat files                                                         |
| `~/.agent/decisions/job_registry.json`                | Create             | Expected schedules, restart commands                                            |
| `~/.agent/decisions/dlq.json`                         | Create (empty)     | Dead letter queue for failed jobs                                               |
| `~/.agent/decisions/circuit_breakers.json`            | Create (empty)     | Per-job circuit breaker state                                                   |
| `~/scripts/nuzantara-sentinel.py`                     | Create             | Main sentinel process (Pro)                                                     |
| `~/scripts/sentinel_lib/classifier.py`                | Create             | Failure classification (rules + Haiku)                                          |
| `~/scripts/sentinel_lib/circuit_breaker.py`           | Create             | 3-state circuit breaker                                                         |
| `~/scripts/sentinel_lib/alerter.py`                   | Create             | Telegram alerts with dedup                                                      |
| `~/scripts/sentinel_lib/repairer.py`                  | Create             | Tier 1/2/3/4 dispatch logic                                                     |
| `~/Library/LaunchAgents/com.nuzantara.sentinel.plist` | Create             | Runs sentinel every 5min on **Pro** (Air unavailable for SSH from this session) |
| `~/scripts/vector-reindex-check.py`                   | Modify lines 49,68 | Fix Python 3.9 type union syntax                                                |
| `~/scripts/fly-health-check.sh`                       | Modify             | Add heartbeat write                                                             |
| `~/scripts/fly-pg-backup.sh`                          | Modify             | Add heartbeat write                                                             |
| `~/scripts/fly-qdrant-backup.sh`                      | Modify             | Add heartbeat write                                                             |
| `~/scripts/expiry_alerter.py`                         | Modify             | Add heartbeat write                                                             |
| `~/scripts/nlm_nb1_daily_refresh.py`                  | Modify             | Add heartbeat write                                                             |
| `~/scripts/openclaw-cron/*.sh`                        | Modify (all)       | Add sentinel_ping wrapper                                                       |

---

## Task 1: Fix Pre-Existing Bugs (before Sentinel generates false alerts)

**Files:**

- Modify: `~/scripts/vector-reindex-check.py` lines 49, 68

- [ ] **Step 1: Fix Python 3.9 type union syntax**

```python
# In /Users/nuzantara/scripts/vector-reindex-check.py
# Replace line 49:
def http_get(url: str, headers: dict[str, str] | None = None, timeout: int = 15) -> dict[str, Any]:
# With:
def http_get(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 15) -> Dict[str, Any]:

# Replace line 68:
def http_post(url: str, data: dict[str, Any], headers: dict[str, str] | None = None, timeout: int = 10) -> dict[str, Any]:
# With:
def http_post(url: str, data: Dict[str, Any], headers: Optional[Dict[str, str]] = None, timeout: int = 10) -> Dict[str, Any]:

# Also add to imports (after "from typing import Any"):
from typing import Any, Dict, Optional
```

- [ ] **Step 2: Verify syntax is valid on Python 3.9**

```bash
python3 --version  # confirm 3.9.x or 3.11.x
python3 -c "import ast; ast.parse(open('/Users/nuzantara/scripts/vector-reindex-check.py').read()); print('OK')"
```

Expected: `OK` (no SyntaxError)

- [ ] **Step 3: Run dry-run to confirm it executes**

```bash
QDRANT_URL=http://localhost:6333 python3 /Users/nuzantara/scripts/vector-reindex-check.py --dry-run 2>&1 | tail -5
```

Expected: no SyntaxError, may get connection errors (fine — Qdrant might be up or down)

- [ ] **Step 4: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add scripts/vector-reindex-check.py
git commit -m "fix(scripts): Python 3.9 type union syntax in vector-reindex-check"
```

---

## Task 2: Create State Directory and Job Registry

**Files:**

- Create: `~/.agent/decisions/state/` (directory)
- Create: `~/.agent/decisions/job_registry.json`
- Create: `~/.agent/decisions/dlq.json`
- Create: `~/.agent/decisions/circuit_breakers.json`

- [ ] **Step 1: Create directories**

```bash
mkdir -p ~/.agent/decisions/state
touch ~/.agent/decisions/dlq.json
touch ~/.agent/decisions/circuit_breakers.json
echo '{"queue": []}' > ~/.agent/decisions/dlq.json
echo '{}' > ~/.agent/decisions/circuit_breakers.json
```

- [ ] **Step 2: Write job registry**

```bash
cat > ~/.agent/decisions/job_registry.json << 'EOF'
{
  "jobs": {
    "fly_health_check": {
      "host": "Nuzantara",
      "type": "launchagent",
      "plist": "com.balizero.backend-prewarm",
      "schedule_seconds": 300,
      "staleness_threshold_s": 900,
      "restart_cmd": "launchctl kickstart -k gui/$(id -u)/com.balizero.backend-prewarm",
      "test_cmd": "bash /Users/nuzantara/scripts/fly-health-check.sh"
    },
    "intel_scraper": {
      "host": "Nuzantara",
      "type": "launchagent",
      "plist": "com.balizero.intel.nightly",
      "schedule_seconds": 86400,
      "staleness_threshold_s": 93600,
      "restart_cmd": "launchctl kickstart -k gui/$(id -u)/com.balizero.intel.nightly",
      "test_cmd": null
    },
    "client_value_predictor": {
      "host": "Nuzantara",
      "type": "launchagent",
      "plist": "com.balizero.client-value-predictor",
      "schedule_seconds": 86400,
      "staleness_threshold_s": 93600,
      "restart_cmd": "launchctl kickstart -k gui/$(id -u)/com.balizero.client-value-predictor",
      "test_cmd": null
    },
    "nlm_bridge": {
      "host": "Nuzantara",
      "type": "launchagent",
      "plist": "com.balizero.nlm-bridge",
      "schedule_seconds": 60,
      "staleness_threshold_s": 300,
      "restart_cmd": "launchctl kickstart -k gui/$(id -u)/com.balizero.nlm-bridge",
      "test_cmd": "curl -s http://localhost:5100/health | grep -q ok"
    },
    "vector_reindex_check": {
      "host": "Nuzantara",
      "type": "launchagent",
      "plist": "com.nuzantara.vector-reindex-check",
      "schedule_seconds": 604800,
      "staleness_threshold_s": 691200,
      "restart_cmd": "launchctl kickstart -k gui/$(id -u)/com.nuzantara.vector-reindex-check",
      "test_cmd": "python3 /Users/nuzantara/scripts/vector-reindex-check.py --dry-run"
    },
    "fly_pg_backup": {
      "host": "Nuzantara",
      "type": "shell",
      "schedule_seconds": 86400,
      "staleness_threshold_s": 93600,
      "restart_cmd": "bash /Users/nuzantara/scripts/fly-pg-backup.sh",
      "test_cmd": null
    },
    "fly_qdrant_backup": {
      "host": "Nuzantara",
      "type": "shell",
      "schedule_seconds": 86400,
      "staleness_threshold_s": 93600,
      "restart_cmd": "bash /Users/nuzantara/scripts/fly-qdrant-backup.sh",
      "test_cmd": null
    },
    "nlm_nb1_daily_refresh": {
      "host": "Nuzantara",
      "type": "shell",
      "schedule_seconds": 86400,
      "staleness_threshold_s": 93600,
      "restart_cmd": "python3 /Users/nuzantara/scripts/nlm_nb1_daily_refresh.py",
      "test_cmd": null
    },
    "expiry_alerter": {
      "host": "Nuzantara",
      "type": "launchagent",
      "plist": "com.balizero.renewal-alerts",
      "schedule_seconds": 86400,
      "staleness_threshold_s": 93600,
      "restart_cmd": "launchctl kickstart -k gui/$(id -u)/com.balizero.renewal-alerts",
      "test_cmd": "python3 /Users/nuzantara/Desktop/nuzantara/scripts/expiry_alerter.py --dry-run"
    },
    "health_check": {
      "host": "Nuzantara",
      "type": "openclaw",
      "schedule_seconds": 300,
      "staleness_threshold_s": 900,
      "restart_cmd": "curl -s -X POST http://localhost:18789/api/trigger/health-check",
      "test_cmd": null
    },
    "daily_ops_autopilot": {
      "host": "Nuzantara",
      "type": "openclaw",
      "schedule_seconds": 86400,
      "staleness_threshold_s": 93600,
      "restart_cmd": "curl -s -X POST http://localhost:18789/api/trigger/daily-ops-autopilot",
      "test_cmd": null
    },
    "conversation_trainer": {
      "host": "Nuzantara",
      "type": "openclaw",
      "schedule_seconds": 86400,
      "staleness_threshold_s": 93600,
      "restart_cmd": "curl -s -X POST http://localhost:18789/api/trigger/conversation-trainer",
      "test_cmd": null
    },
    "knowledge_graph_builder": {
      "host": "Nuzantara",
      "type": "openclaw",
      "schedule_seconds": 86400,
      "staleness_threshold_s": 93600,
      "restart_cmd": "curl -s -X POST http://localhost:18789/api/trigger/knowledge-graph-builder",
      "test_cmd": null
    }
  }
}
EOF
```

- [ ] **Step 3: Verify registry is valid JSON**

```bash
python3 -c "import json; d=json.load(open(os.path.expanduser('~/.agent/decisions/job_registry.json'))); print(f'OK — {len(d[\"jobs\"])} jobs registered')" 2>/dev/null || python3 -c "import json,os; d=json.load(open(os.path.expanduser('~/.agent/decisions/job_registry.json'))); print(f'OK — {len(d[\"jobs\"])} jobs registered')"
```

Expected: `OK — 13 jobs registered`

---

## Task 3: Sentinel Library — classifier.py

**Files:**

- Create: `~/scripts/sentinel_lib/__init__.py`
- Create: `~/scripts/sentinel_lib/classifier.py`

- [ ] **Step 1: Create the module**

```bash
mkdir -p ~/scripts/sentinel_lib
touch ~/scripts/sentinel_lib/__init__.py
```

- [ ] **Step 2: Write classifier.py**

```python
# ~/scripts/sentinel_lib/classifier.py
"""Failure classifier: deterministic rules first, Haiku LLM fallback."""
import re
import os
import json
import urllib.request
import urllib.parse
from typing import Optional

TRANSIENT_PATTERNS = [
    r"HTTP 5\d\d",
    r"connection refused",
    r"ETIMEDOUT",
    r"temporarily unavailable",
    r"service unavailable",
    r"Connection reset",
    r"timeout expired",
    r"SIGTERM",
]

DETERMINISTIC_PATTERNS = [
    (r"SyntaxError", "syntax_error"),
    (r"ImportError|ModuleNotFoundError", "import_error"),
    (r"Permission denied", "permission_error"),
    (r"No such file or directory", "missing_file"),
    (r"NameError|AttributeError|TypeError", "code_bug"),
    (r"dict\[.*\] \| None", "py39_type_syntax"),
    (r"lsof: command not found", "missing_binary"),
    (r"SMTP.*[Ff]ailed|Authentication.*[Ff]ailed", "smtp_auth"),
]

FIX_PATTERNS = {
    "py39_type_syntax": {
        "description": "Python 3.9 type union syntax — requires 3.10+",
        "fix_instruction": "Replace all `X | Y` type annotations with `Optional[X]` or `Union[X, Y]` from typing",
        "confidence": 0.95,
    },
    "import_error": {
        "description": "Missing Python package or wrong import path",
        "fix_instruction": "Check virtualenv activation and install missing package. Check absolute import paths.",
        "confidence": 0.85,
    },
    "missing_binary": {
        "description": "Required binary not in PATH",
        "fix_instruction": "Install missing tool via brew or replace with stdlib equivalent",
        "confidence": 0.90,
    },
    "smtp_auth": {
        "description": "SMTP authentication failure",
        "fix_instruction": "Check SMTP_LOGIN and SMTP_PASS environment variables",
        "confidence": 0.85,
    },
}


def classify(error_text: str, retry_count: int = 0) -> dict:
    """
    Returns dict with keys: type (TRANSIENT|DETERMINISTIC|UNKNOWN),
    subtype (str), fix_pattern (dict|None), confidence (float).
    """
    if not error_text:
        return {"type": "UNKNOWN", "subtype": "no_error_text", "fix_pattern": None, "confidence": 0.0}

    # Check transient first
    for pattern in TRANSIENT_PATTERNS:
        if re.search(pattern, error_text, re.IGNORECASE):
            # If same error repeats 2+ times, escalate to DETERMINISTIC
            if retry_count >= 2:
                return {"type": "DETERMINISTIC", "subtype": "repeated_transient", "fix_pattern": None, "confidence": 0.8}
            return {"type": "TRANSIENT", "subtype": "network_or_service", "fix_pattern": None, "confidence": 0.9}

    # Check deterministic
    for pattern, subtype in DETERMINISTIC_PATTERNS:
        if re.search(pattern, error_text, re.IGNORECASE):
            fix = FIX_PATTERNS.get(subtype)
            return {
                "type": "DETERMINISTIC",
                "subtype": subtype,
                "fix_pattern": fix,
                "confidence": fix["confidence"] if fix else 0.7,
            }

    # Fallback: unknown — treat as TRANSIENT once, then escalate
    return {"type": "UNKNOWN", "subtype": "unclassified", "fix_pattern": None, "confidence": 0.0}


def classify_with_llm(error_text: str, job_name: str) -> dict:
    """
    Call Claude Haiku to classify failure when rules return UNKNOWN.
    Returns same shape as classify(). Falls back to UNKNOWN if API fails.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"type": "UNKNOWN", "subtype": "no_api_key", "fix_pattern": None, "confidence": 0.0}

    prompt = f"""You are diagnosing a failed automation job named "{job_name}".
Error output (last 20 lines):
{error_text[-2000:]}

Classify this failure as one of:
- TRANSIENT: network issue, service temporarily down, timeout — safe to retry
- DETERMINISTIC: code bug, missing file, permission error — retrying won't help
- UNKNOWN: cannot determine

Respond with JSON only:
{{"type": "TRANSIENT|DETERMINISTIC|UNKNOWN", "subtype": "one_word_reason", "fix_suggestion": "one sentence fix", "confidence": 0.0-1.0}}"""

    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 256,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    try:
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read())
            text = body["content"][0]["text"]
            result = json.loads(text)
            return {
                "type": result.get("type", "UNKNOWN"),
                "subtype": result.get("subtype", "llm_classified"),
                "fix_pattern": {"fix_instruction": result.get("fix_suggestion"), "confidence": result.get("confidence", 0.5)} if result.get("fix_suggestion") else None,
                "confidence": result.get("confidence", 0.5),
            }
    except Exception:
        return {"type": "UNKNOWN", "subtype": "llm_failed", "fix_pattern": None, "confidence": 0.0}
```

- [ ] **Step 3: Write unit test for classifier**

```bash
cat > /tmp/test_classifier.py << 'EOF'
import sys
sys.path.insert(0, '/Users/nuzantara/scripts')
from sentinel_lib.classifier import classify

# TRANSIENT
r = classify("Connection refused to http://localhost:6333")
assert r["type"] == "TRANSIENT", f"Expected TRANSIENT, got {r}"

# DETERMINISTIC - py39 syntax
r = classify("SyntaxError: dict[str, str] | None invalid syntax")
assert r["type"] == "DETERMINISTIC", f"Expected DETERMINISTIC, got {r}"
assert r["subtype"] == "syntax_error", f"Expected syntax_error, got {r['subtype']}"

# Repeated transient escalates
r = classify("Connection refused", retry_count=2)
assert r["type"] == "DETERMINISTIC", f"Expected DETERMINISTIC after 2 retries, got {r}"

# Missing binary
r = classify("lsof: command not found")
assert r["type"] == "DETERMINISTIC"
assert r["fix_pattern"] is not None

print("✅ All classifier tests passed")
EOF
python3 /tmp/test_classifier.py
```

Expected: `✅ All classifier tests passed`

---

## Task 4: Sentinel Library — circuit_breaker.py

**Files:**

- Create: `~/scripts/sentinel_lib/circuit_breaker.py`

- [ ] **Step 1: Write circuit_breaker.py**

```python
# ~/scripts/sentinel_lib/circuit_breaker.py
"""Per-job circuit breaker: CLOSED → OPEN → HALF_OPEN → CLOSED."""
import json
import os
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


def _save(state: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


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
    _save(data)


def record_failure(job: str) -> CircuitState:
    """Call after a failed run — may trip to OPEN. Returns new state."""
    data = _load()
    job_data = data.get(job, {"state": "CLOSED", "failures": 0, "opened_at": 0})
    job_data["failures"] = job_data.get("failures", 0) + 1

    if job_data["failures"] >= 3 or job_data.get("state") == "HALF_OPEN":
        job_data["state"] = "OPEN"
        job_data["opened_at"] = time.time()
    data[job] = job_data
    _save(data)
    return job_data["state"]


def _set_state(job: str, state: CircuitState) -> None:
    data = _load()
    job_data = data.get(job, {})
    job_data["state"] = state
    if state == "HALF_OPEN":
        job_data["opened_at"] = time.time()
    data[job] = job_data
    _save(data)
```

- [ ] **Step 2: Test circuit breaker**

```bash
cat > /tmp/test_cb.py << 'EOF'
import sys, os, json, time
sys.path.insert(0, '/Users/nuzantara/scripts')

# Use temp file for test
import sentinel_lib.circuit_breaker as cb
cb.STATE_FILE = '/tmp/test_cb_state.json'

cb.record_success("test_job")
assert cb.get_state("test_job") == "CLOSED"

cb.record_failure("test_job")
cb.record_failure("test_job")
state = cb.record_failure("test_job")
assert state == "OPEN", f"Expected OPEN after 3 failures, got {state}"

cb.record_success("test_job")
assert cb.get_state("test_job") == "CLOSED", "Should reset to CLOSED after success"

print("✅ All circuit breaker tests passed")
os.unlink('/tmp/test_cb_state.json')
EOF
python3 /tmp/test_cb.py
```

Expected: `✅ All circuit breaker tests passed`

---

## Task 5: Sentinel Library — alerter.py

**Files:**

- Create: `~/scripts/sentinel_lib/alerter.py`

- [ ] **Step 1: Write alerter.py**

```python
# ~/scripts/sentinel_lib/alerter.py
"""Telegram alerter with md5 dedup (same pattern as fly-health-check.sh)."""
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request

DEDUP_FILE = os.path.expanduser("~/.agent/decisions/alert_dedup.json")
DEDUP_WINDOW_S = 3600  # 1 hour


def _load_dedup() -> dict:
    try:
        return json.loads(open(DEDUP_FILE).read())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_dedup(data: dict) -> None:
    with open(DEDUP_FILE, "w") as f:
        json.dump(data, f)


def _is_duplicate(key: str) -> bool:
    data = _load_dedup()
    entry = data.get(key)
    if not entry:
        return False
    return (time.time() - entry["ts"]) < DEDUP_WINDOW_S


def _mark_sent(key: str) -> None:
    data = _load_dedup()
    data[key] = {"ts": time.time()}
    # Prune old entries
    data = {k: v for k, v in data.items() if (time.time() - v["ts"]) < DEDUP_WINDOW_S * 24}
    _save_dedup(data)


def send_alert(message: str, level: str = "INFO") -> bool:
    """
    Send Telegram message with dedup. Returns True if sent, False if deduped or failed.
    level: INFO | WARNING | CRITICAL | DEADMAN
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_ADMIN_CHAT_ID", os.getenv("TELEGRAM_CHAT_ID", "413539912"))

    if not bot_token:
        print(f"[ALERT-NO-TOKEN] {level}: {message[:100]}")
        return False

    # Dedup key = md5 of message content (not timestamp)
    dedup_key = hashlib.md5(message.encode()).hexdigest()
    if _is_duplicate(dedup_key):
        return False

    prefix = {"INFO": "🔧", "WARNING": "🟡", "CRITICAL": "🔴", "DEADMAN": "⚫"}.get(level, "ℹ️")
    full_message = f"{prefix} *Sentinel* | {message}"

    try:
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": full_message, "parse_mode": "Markdown"}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data=data,
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                _mark_sent(dedup_key)
                return True
    except Exception as e:
        print(f"[ALERT-FAILED] {e}")
    return False


def send_daily_report(fleet_status: dict) -> None:
    """Send daily fleet health summary."""
    healthy = sum(1 for j in fleet_status.values() if j.get("status") == "ok")
    total = len(fleet_status)
    stale = [j for j, s in fleet_status.items() if s.get("status") == "stale"]
    failed = [j for j, s in fleet_status.items() if s.get("status") == "failed"]

    lines = [f"🤖 *Fleet Status* — {total} automations"]
    lines.append(f"✅ {healthy}/{total} healthy")
    if stale:
        lines.append(f"⚠️ Stale: {', '.join(stale)}")
    if failed:
        lines.append(f"🔴 Failed: {', '.join(failed)}")

    send_alert("\n".join(lines), level="INFO")
```

- [ ] **Step 2: Test alerter (dry run — no real Telegram)**

```bash
cat > /tmp/test_alerter.py << 'EOF'
import sys, os
sys.path.insert(0, '/Users/nuzantara/scripts')
import sentinel_lib.alerter as alerter
alerter.DEDUP_FILE = '/tmp/test_dedup.json'

# Without token — should return False but not crash
result = alerter.send_alert("test message", "WARNING")
assert result == False, "Expected False without token"

# Test dedup
import sentinel_lib.alerter as a2
a2.DEDUP_FILE = '/tmp/test_dedup2.json'
a2._mark_sent("test_key")
assert a2._is_duplicate("test_key") == True
assert a2._is_duplicate("other_key") == False

print("✅ All alerter tests passed")
EOF
python3 /tmp/test_alerter.py
```

Expected: `✅ All alerter tests passed`

---

## Task 6: Sentinel Library — repairer.py

**Files:**

- Create: `~/scripts/sentinel_lib/repairer.py`

- [ ] **Step 1: Write repairer.py**

```python
# ~/scripts/sentinel_lib/repairer.py
"""Tier dispatch: retry (T1), aider-fix (T2), Claude Code alert (T3), Zero alert (T4)."""
import json
import os
import subprocess
import time
from typing import Optional

DLQ_FILE = os.path.expanduser("~/.agent/decisions/dlq.json")
NUZANTARA_ROOT = os.path.expanduser("~/Desktop/nuzantara")


def _load_dlq() -> dict:
    try:
        return json.loads(open(DLQ_FILE).read())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"queue": []}


def _save_dlq(data: dict) -> None:
    with open(DLQ_FILE, "w") as f:
        json.dump(data, f, indent=2)


def add_to_dlq(job: str, error_summary: str, classification: dict, log_tail: str,
               files_implicated: list, aider_attempts: int = 0,
               aider_failure_reason: Optional[str] = None) -> None:
    """Add job to DLQ. Idempotent — won't add duplicate entries."""
    data = _load_dlq()
    # Remove existing entry for this job (will re-add with fresh info)
    data["queue"] = [e for e in data["queue"] if e.get("job") != job]
    data["queue"].append({
        "job": job,
        "added_ts": time.time(),
        "error_summary": error_summary,
        "log_tail": log_tail[-2000:],  # last 2000 chars
        "classification": classification,
        "files_implicated": files_implicated,
        "aider_attempts": aider_attempts,
        "aider_failure_reason": aider_failure_reason,
        "status": "needs_claude_code" if aider_attempts > 0 else "needs_aider",
    })
    _save_dlq(data)


def clear_dlq_entry(job: str) -> None:
    """Remove job from DLQ after successful fix."""
    data = _load_dlq()
    data["queue"] = [e for e in data["queue"] if e.get("job") != job]
    _save_dlq(data)


def retry_job(restart_cmd: str, host: str = "Nuzantara") -> tuple[bool, str]:
    """
    Execute restart_cmd (locally or via SSH if host != current hostname).
    Returns (success, output).
    """
    import socket
    current_host = socket.gethostname()

    if host != current_host and host != "localhost":
        cmd = ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes", host, restart_cmd]
    else:
        cmd = ["bash", "-c", restart_cmd]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        success = result.returncode == 0
        output = result.stdout + result.stderr
        return success, output
    except subprocess.TimeoutExpired:
        return False, "Retry command timed out after 30s"
    except Exception as e:
        return False, str(e)


def dispatch_aider_fix(job: str, error_summary: str, fix_instruction: str,
                        files_implicated: list, test_cmd: Optional[str]) -> tuple[bool, str]:
    """
    Dispatch ai-dispatch.sh aider-fix with structured prompt.
    Returns (success, output).
    """
    files_str = ", ".join(files_implicated) if files_implicated else "unknown"
    verify_str = f"\nVerify by running: {test_cmd}" if test_cmd else ""

    prompt = (
        f"Fix automation job '{job}'.\n"
        f"Error: {error_summary}\n"
        f"Fix: {fix_instruction}\n"
        f"Files: {files_str}"
        f"{verify_str}"
    )

    dispatch_script = os.path.join(NUZANTARA_ROOT, "scripts", "ai-dispatch.sh")
    if not os.path.exists(dispatch_script):
        return False, f"ai-dispatch.sh not found at {dispatch_script}"

    try:
        result = subprocess.run(
            ["bash", dispatch_script, "aider-fix", prompt],
            capture_output=True, text=True, timeout=300, cwd=NUZANTARA_ROOT
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "aider-fix timed out after 5min"
    except Exception as e:
        return False, str(e)


def verify_fix(test_cmd: str, host: str = "Nuzantara") -> tuple[bool, str]:
    """Run test_cmd to verify a fix worked. Returns (passed, output)."""
    return retry_job(test_cmd, host)
```

- [ ] **Step 2: Test repairer DLQ functions**

```bash
cat > /tmp/test_repairer.py << 'EOF'
import sys, os, json
sys.path.insert(0, '/Users/nuzantara/scripts')
import sentinel_lib.repairer as repairer
repairer.DLQ_FILE = '/tmp/test_dlq.json'

# Add entry
repairer.add_to_dlq(
    job="test_job",
    error_summary="SyntaxError: dict[str] | None",
    classification={"type": "DETERMINISTIC", "subtype": "py39_type_syntax"},
    log_tail="..error..",
    files_implicated=["~/scripts/test.py"],
)
data = json.loads(open('/tmp/test_dlq.json').read())
assert len(data["queue"]) == 1
assert data["queue"][0]["job"] == "test_job"

# Idempotent re-add
repairer.add_to_dlq(job="test_job", error_summary="same error",
    classification={}, log_tail="", files_implicated=[])
data = json.loads(open('/tmp/test_dlq.json').read())
assert len(data["queue"]) == 1, "Should deduplicate"

# Clear
repairer.clear_dlq_entry("test_job")
data = json.loads(open('/tmp/test_dlq.json').read())
assert len(data["queue"]) == 0

print("✅ All repairer DLQ tests passed")
os.unlink('/tmp/test_dlq.json')
EOF
python3 /tmp/test_repairer.py
```

Expected: `✅ All repairer DLQ tests passed`

---

## Task 7: Main Sentinel Process

**Files:**

- Create: `~/scripts/nuzantara-sentinel.py`

- [ ] **Step 1: Write nuzantara-sentinel.py**

```python
#!/usr/bin/env python3
"""
Nuzantara Sentinel — 4-tier self-healing automation monitor.
Runs every 5 minutes via launchd. Monitors Pro + Air.
"""
import glob
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# Add sentinel_lib to path
sys.path.insert(0, str(Path(__file__).parent))
from sentinel_lib.classifier import classify, classify_with_llm
from sentinel_lib.circuit_breaker import get_state, record_success, record_failure
from sentinel_lib.alerter import send_alert, send_daily_report
from sentinel_lib.repairer import retry_job, dispatch_aider_fix, verify_fix, add_to_dlq, clear_dlq_entry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(os.path.expanduser("~/logs/sentinel.log")),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

STATE_DIR = os.path.expanduser("~/.agent/decisions/state")
REGISTRY_FILE = os.path.expanduser("~/.agent/decisions/job_registry.json")
HEARTBEAT_FILE = os.path.expanduser("~/.pro_heartbeat")
SENTINEL_LOG = os.path.expanduser("~/logs/sentinel.jsonl")
PRO_HOST = "Nuzantara"
DEAD_MAN_THRESHOLD_S = 7200  # 2 hours

MAX_RETRIES = 3
BACKOFF_BASE_S = 60
BACKOFF_CAP_S = 600


def load_registry() -> dict:
    try:
        return json.loads(open(REGISTRY_FILE).read()).get("jobs", {})
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning("Registry not found or invalid")
        return {}


def collect_state_files() -> dict[str, dict]:
    """Read local + Pro state files. Returns {job_id: state_dict}."""
    states = {}

    # Local state files
    for path in glob.glob(os.path.join(STATE_DIR, "*.last.json")):
        try:
            job_id = os.path.basename(path).replace(".last.json", "")
            states[job_id] = json.loads(open(path).read())
        except Exception:
            pass

    # Pro state files via SSH (skip if we are Pro)
    import socket
    if socket.gethostname() != PRO_HOST:
        try:
            result = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes",
                 PRO_HOST, f"cat {STATE_DIR}/*.last.json 2>/dev/null || echo '{{}}'"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0 and result.stdout.strip():
                # Output is concatenated JSONs — parse each
                for chunk in result.stdout.strip().split("\n"):
                    chunk = chunk.strip()
                    if chunk and chunk != "{}":
                        try:
                            s = json.loads(chunk)
                            job_id = s.get("job")
                            if job_id:
                                states[job_id] = s
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            send_alert(f"Pro unreachable via SSH: {e}", level="CRITICAL")

    return states


def check_dead_man_switch() -> None:
    """Alert if Pro hasn't sent a heartbeat in >2 hours."""
    import socket
    if socket.gethostname() == PRO_HOST:
        return  # We ARE Pro, skip

    try:
        mtime = os.path.getmtime(HEARTBEAT_FILE)
        age = time.time() - mtime
        if age > DEAD_MAN_THRESHOLD_S:
            send_alert(
                f"Pro machine heartbeat STALE — last seen {age/3600:.1f}h ago. Manual check required.",
                level="DEADMAN"
            )
    except FileNotFoundError:
        send_alert("Pro heartbeat file missing — Pro never connected?", level="WARNING")


def exponential_backoff(attempt: int) -> float:
    """Full jitter backoff: random(0, min(cap, base * 2^attempt))."""
    import random
    return random.uniform(0, min(BACKOFF_CAP_S, BACKOFF_BASE_S * (2 ** attempt)))


def process_job(job_id: str, state: dict, registry: dict) -> dict:
    """
    Evaluate one job. Returns action taken: {action, tier, success}.
    """
    now = time.time()
    circuit = get_state(job_id)
    reg = registry.get(job_id, {})

    # Circuit OPEN → skip
    if circuit == "OPEN":
        logger.info(f"{job_id}: circuit OPEN, skipping")
        return {"action": "skipped_circuit_open", "tier": 0, "success": None}

    status = state.get("status", "unknown")
    last_ts = state.get("ts", 0)
    last_error = state.get("last_error", "") or ""
    retry_attempt = state.get("retry_attempt", 0)

    # Staleness check
    threshold = reg.get("staleness_threshold_s", 93600)
    age = now - last_ts
    if status == "ok" and age > threshold:
        status = "stale"

    if status == "ok":
        record_success(job_id)
        return {"action": "healthy", "tier": 0, "success": True}

    if status == "running":
        # Job is currently running — don't interfere
        return {"action": "running", "tier": 0, "success": None}

    # --- FAILURE PATH ---
    logger.warning(f"{job_id}: status={status}, error={last_error[:80]}")

    # Classify failure
    classification = classify(last_error, retry_attempt)
    if classification["type"] == "UNKNOWN":
        classification = classify_with_llm(last_error, job_id)

    failure_type = classification["type"]
    fix_pattern = classification.get("fix_pattern")
    new_circuit = record_failure(job_id)

    if failure_type == "TRANSIENT" and retry_attempt < MAX_RETRIES:
        # Tier 1: retry
        restart_cmd = reg.get("restart_cmd")
        if restart_cmd:
            host = reg.get("host", "Nuzantara")
            backoff = exponential_backoff(retry_attempt)
            logger.info(f"{job_id}: Tier 1 retry (attempt {retry_attempt+1}), backoff {backoff:.0f}s")
            time.sleep(backoff)
            success, output = retry_job(restart_cmd, host)
            if success:
                record_success(job_id)
                return {"action": "retried_ok", "tier": 1, "success": True}
        # Retry failed or no restart_cmd
        return {"action": "retry_failed", "tier": 1, "success": False}

    if failure_type == "DETERMINISTIC" and fix_pattern and fix_pattern.get("confidence", 0) >= 0.85:
        # Tier 2: Aider fix
        files_implicated = _infer_files(job_id, last_error)
        test_cmd = reg.get("test_cmd")
        logger.info(f"{job_id}: Tier 2 aider-fix (confidence {fix_pattern['confidence']})")
        success, output = dispatch_aider_fix(
            job=job_id,
            error_summary=last_error[:500],
            fix_instruction=fix_pattern["fix_instruction"],
            files_implicated=files_implicated,
            test_cmd=test_cmd,
        )
        if success and test_cmd:
            verified, _ = verify_fix(test_cmd, reg.get("host", "Nuzantara"))
            if verified:
                record_success(job_id)
                clear_dlq_entry(job_id)
                send_alert(f"✅ Auto-fixed `{job_id}`: {fix_pattern['fix_instruction'][:80]}", level="INFO")
                return {"action": "aider_fixed", "tier": 2, "success": True}

        # Aider failed — escalate to Tier 3
        add_to_dlq(job_id, last_error[:500], classification, last_error,
                   files_implicated, aider_attempts=1, aider_failure_reason=output[:200])
        send_alert(
            f"Tier 3 needed — `{job_id}`\nError: {last_error[:100]}\nAider failed: {output[:80]}\n\nCheck DLQ: `~/.agent/decisions/dlq.json`",
            level="CRITICAL"
        )
        return {"action": "escalated_tier3", "tier": 3, "success": False}

    # Tier 3/4: Unknown or low confidence — add to DLQ
    add_to_dlq(job_id, last_error[:500], classification, last_error,
               _infer_files(job_id, last_error))
    level = "CRITICAL" if failure_type == "DETERMINISTIC" else "WARNING"
    send_alert(
        f"{'Tier 3' if failure_type != 'UNKNOWN' else 'Tier 4'} needed — `{job_id}`\n"
        f"Type: {failure_type} / {classification.get('subtype')}\n"
        f"Error: {last_error[:120]}",
        level=level
    )
    return {"action": "escalated", "tier": 3, "success": False}


def _infer_files(job_id: str, error_text: str) -> list:
    """Extract file paths from error text."""
    import re
    paths = re.findall(r'(?:File |in )[""]?(/[^\s"\']+\.(?:py|sh))', error_text)
    # Also try common script locations
    for pattern in [f"~/scripts/{job_id.replace('_', '-')}.py",
                    f"~/scripts/{job_id.replace('_', '-')}.sh",
                    f"~/Desktop/nuzantara/scripts/{job_id.replace('_', '-')}.py"]:
        expanded = os.path.expanduser(pattern)
        if os.path.exists(expanded):
            paths.append(expanded)
    return list(set(paths)) or ["unknown"]


def run_sentinel() -> None:
    logger.info("=== Sentinel run start ===")
    start = time.time()
    registry = load_registry()
    states = collect_state_files()
    check_dead_man_switch()

    results = {}
    for job_id, state in states.items():
        try:
            results[job_id] = process_job(job_id, state, registry)
        except Exception as e:
            logger.error(f"Error processing {job_id}: {e}", exc_info=True)

    # Self-log
    duration = time.time() - start
    log_entry = {
        "ts": time.time(),
        "duration_s": round(duration, 2),
        "jobs_checked": len(states),
        "healthy": sum(1 for r in results.values() if r.get("action") == "healthy"),
        "retried": sum(1 for r in results.values() if "retried" in r.get("action", "")),
        "escalated": sum(1 for r in results.values() if "escalated" in r.get("action", "")),
    }
    os.makedirs(os.path.dirname(SENTINEL_LOG), exist_ok=True)
    with open(SENTINEL_LOG, "a") as f:
        f.write(json.dumps(log_entry) + "\n")

    logger.info(f"=== Sentinel done: {log_entry['jobs_checked']} checked, "
                f"{log_entry['healthy']} healthy, {log_entry['escalated']} escalated "
                f"in {duration:.1f}s ===")


if __name__ == "__main__":
    run_sentinel()
```

- [ ] **Step 2: Make executable and test dry run (no jobs yet)**

```bash
chmod +x ~/scripts/nuzantara-sentinel.py
mkdir -p ~/logs
python3 ~/scripts/nuzantara-sentinel.py
```

Expected: `=== Sentinel run start ===` → `=== Sentinel done: 0 checked, 0 healthy, 0 escalated in X.Xs ===`

---

## Task 8: LaunchAgent for Sentinel (Pro, every 5min)

**Files:**

- Create: `~/Library/LaunchAgents/com.nuzantara.sentinel.plist`

- [ ] **Step 1: Write plist**

```bash
cat > ~/Library/LaunchAgents/com.nuzantara.sentinel.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nuzantara.sentinel</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/nuzantara/scripts/nuzantara-sentinel.py</string>
    </array>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/nuzantara/logs/sentinel.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/nuzantara/logs/sentinel.error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
        <key>HOME</key>
        <string>/Users/nuzantara</string>
    </dict>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
EOF
```

- [ ] **Step 2: Load LaunchAgent**

```bash
launchctl load ~/Library/LaunchAgents/com.nuzantara.sentinel.plist
launchctl list | grep sentinel
```

Expected: line showing `com.nuzantara.sentinel` with PID (or 0 if just loaded)

---

## Task 9: Add Heartbeats to Existing Scripts

**Files:**

- Modify: `~/scripts/fly-health-check.sh`
- Modify: `~/scripts/fly-pg-backup.sh`
- Modify: `~/scripts/fly-qdrant-backup.sh`
- Modify: `~/Desktop/nuzantara/scripts/expiry_alerter.py`
- Modify: `~/Desktop/nuzantara/scripts/nlm_nb1_daily_refresh.py`

- [ ] **Step 1: Add heartbeat to fly-health-check.sh**

Find the final `else` block (successful run) and add before the closing `fi`:

```bash
# At the end of fly-health-check.sh, before final `fi`, add:
echo '{"job":"fly_health_check","ts":'$(date +%s)',"status":"ok","host":"'$(hostname -s)'","exit_code":0}' \
  > ~/.agent/decisions/state/fly_health_check.last.json
```

Also add failure heartbeat at start of the failures block:

```bash
# When FAILURES is non-empty, before the HASH check, add:
echo '{"job":"fly_health_check","ts":'$(date +%s)',"status":"failed","host":"'$(hostname -s)'","last_error":"'"${FAILURES//\"/\'}"'"}' \
  > ~/.agent/decisions/state/fly_health_check.last.json
```

- [ ] **Step 2: Add heartbeat to fly-pg-backup.sh (end of script)**

```bash
# Add at end of fly-pg-backup.sh (after final log message):
echo '{"job":"fly_pg_backup","ts":'$(date +%s)',"status":"ok","host":"'$(hostname -s)'"}' \
  > ~/.agent/decisions/state/fly_pg_backup.last.json
```

- [ ] **Step 3: Add heartbeat to fly-qdrant-backup.sh**

```bash
# Add at end of fly-qdrant-backup.sh (after "Backup complete" log):
echo '{"job":"fly_qdrant_backup","ts":'$(date +%s)',"status":"ok","host":"'$(hostname -s)'"}' \
  > ~/.agent/decisions/state/fly_qdrant_backup.last.json
```

- [ ] **Step 4: Add heartbeat to expiry_alerter.py (in main() after completion)**

```python
# In scripts/expiry_alerter.py, at end of main() function, add:
import pathlib
state_dir = pathlib.Path.home() / ".agent" / "decisions" / "state"
state_dir.mkdir(parents=True, exist_ok=True)
(state_dir / "expiry_alerter.last.json").write_text(
    f'{{"job":"expiry_alerter","ts":{int(__import__("time").time())},"status":"ok","host":"{__import__("socket").gethostname()}"}}'
)
```

- [ ] **Step 5: Add heartbeat to nlm_nb1_daily_refresh.py (in main() after completion)**

```python
# In scripts/nlm_nb1_daily_refresh.py, at end of main() function, add:
import pathlib
state_dir = pathlib.Path.home() / ".agent" / "decisions" / "state"
state_dir.mkdir(parents=True, exist_ok=True)
(state_dir / "nlm_nb1_daily_refresh.last.json").write_text(
    f'{{"job":"nlm_nb1_daily_refresh","ts":{int(time.time())},"status":"ok","host":"{__import__(\"socket\").gethostname()}"}}'
)
```

- [ ] **Step 6: Create sentinel_ping wrapper for OpenClaw scripts**

```bash
# Create shared wrapper sourced by all OpenClaw scripts:
cat > ~/scripts/openclaw-cron/sentinel_ping.sh << 'EOF'
#!/bin/bash
# Usage: source sentinel_ping.sh && sentinel_ping ok|failed job_name [error_msg]
sentinel_ping() {
  local status="${1:-ok}"
  local job_name="${2:-unknown}"
  local error_msg="${3:-}"
  local state_dir="$HOME/.agent/decisions/state"
  mkdir -p "$state_dir"
  local ts
  ts=$(date +%s)
  local host
  host=$(hostname -s)
  if [[ "$status" == "failed" && -n "$error_msg" ]]; then
    printf '{"job":"%s","ts":%s,"status":"%s","host":"%s","last_error":"%s"}\n' \
      "$job_name" "$ts" "$status" "$host" "${error_msg//\"/\'}" \
      > "$state_dir/${job_name}.last.json"
  else
    printf '{"job":"%s","ts":%s,"status":"%s","host":"%s"}\n' \
      "$job_name" "$ts" "$status" "$host" \
      > "$state_dir/${job_name}.last.json"
  fi
}
EOF
chmod +x ~/scripts/openclaw-cron/sentinel_ping.sh
```

- [ ] **Step 7: Add sentinel_ping to knowledge-graph-builder.sh and conversation-trainer.sh**

```bash
# In ~/scripts/openclaw-cron/knowledge-graph-builder.sh, add at top (after shebang):
source "$(dirname "$0")/sentinel_ping.sh"
# Add at end (before exit):
sentinel_ping ok knowledge_graph_builder

# Same for conversation-trainer.sh:
source "$(dirname "$0")/sentinel_ping.sh"
# At end:
sentinel_ping ok conversation_trainer
```

- [ ] **Step 8: Verify state files are being written**

```bash
# Write a test heartbeat manually
echo '{"job":"test_manual","ts":'$(date +%s)',"status":"ok","host":"'$(hostname -s)'"}' \
  > ~/.agent/decisions/state/test_manual.last.json

# Run sentinel — should detect 1 healthy job
python3 ~/scripts/nuzantara-sentinel.py 2>&1 | tail -3
```

Expected: `=== Sentinel done: 1 checked, 1 healthy, 0 escalated in X.Xs ===`

- [ ] **Step 9: Clean up test file**

```bash
rm ~/.agent/decisions/state/test_manual.last.json
```

---

## Task 10: Dead Man's Switch (Pro → Air heartbeat)

**Files:**

- Modify: crontab on Pro

- [ ] **Step 1: Add hourly heartbeat to Pro crontab**

```bash
# Add to crontab (non-destructive):
(crontab -l 2>/dev/null; echo "0 * * * * touch ~/.pro_heartbeat 2>/dev/null; ssh -o ConnectTimeout=3 -o BatchMode=yes air 'touch ~/.pro_heartbeat' 2>/dev/null || true") | sort -u | crontab -
crontab -l | grep pro_heartbeat
```

Expected: line with `touch ~/.pro_heartbeat`

- [ ] **Step 2: Create initial heartbeat file**

```bash
touch ~/.pro_heartbeat
```

---

## Task 11: End-to-End Test

- [ ] **Step 1: Simulate a failed job**

```bash
# Write a failed state file
cat > ~/.agent/decisions/state/test_failure.last.json << 'EOF'
{"job":"test_failure","ts":1000000,"status":"failed","host":"Nuzantara","last_error":"Connection refused to http://localhost:6333","retry_attempt":0}
EOF
```

- [ ] **Step 2: Run sentinel and verify it classifies as TRANSIENT**

```bash
python3 ~/scripts/nuzantara-sentinel.py 2>&1
```

Expected: logs showing `test_failure: Tier 1 retry` (transient classification)

- [ ] **Step 3: Simulate a deterministic failure**

```bash
cat > ~/.agent/decisions/state/test_det.last.json << 'EOF'
{"job":"test_det","ts":1000000,"status":"failed","host":"Nuzantara","last_error":"SyntaxError: dict[str, str] | None requires Python 3.10+","retry_attempt":0}
EOF
python3 ~/scripts/nuzantara-sentinel.py 2>&1
```

Expected: logs showing `test_det: Tier 2 aider-fix` or `escalated` (deterministic, no restart_cmd in registry)

- [ ] **Step 4: Verify DLQ was populated**

```bash
python3 -c "import json,os; d=json.load(open(os.path.expanduser('~/.agent/decisions/dlq.json'))); print(json.dumps(d, indent=2))"
```

Expected: entry for `test_det`

- [ ] **Step 5: Simulate staleness**

```bash
cat > ~/.agent/decisions/state/test_stale.last.json << 'EOF'
{"job":"test_stale","ts":1000000,"status":"ok","host":"Nuzantara"}
EOF
python3 ~/scripts/nuzantara-sentinel.py 2>&1 | grep stale
```

Expected: log line mentioning `stale` classification

- [ ] **Step 6: Clean up test files**

```bash
rm -f ~/.agent/decisions/state/test_failure.last.json \
      ~/.agent/decisions/state/test_det.last.json \
      ~/.agent/decisions/state/test_stale.last.json
# Clear DLQ
echo '{"queue":[]}' > ~/.agent/decisions/dlq.json
```

- [ ] **Step 7: Commit everything**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add scripts/vector-reindex-check.py scripts/expiry_alerter.py scripts/nlm_nb1_daily_refresh.py
git commit -m "feat(sentinel): add self-healing automation monitor with 4-tier repair system

- Fix Python 3.9 type union syntax in vector-reindex-check.py
- Add heartbeat writes to 5 existing scripts
- Create sentinel_lib (classifier, circuit_breaker, alerter, repairer)
- Create nuzantara-sentinel.py (main sentinel process)
- Create LaunchAgent com.nuzantara.sentinel (every 5min)
- Create job_registry.json with 13 automations registered
- Add dead man's switch (Pro→Air hourly heartbeat)
- Add sentinel_ping wrapper for OpenClaw scripts"
```

---

## Self-Review

**Spec coverage check:**

- ✅ 4-tier repair system (Tasks 6, 7)
- ✅ File-based state machine (Tasks 2, 9)
- ✅ Circuit breaker CLOSED/OPEN/HALF_OPEN (Task 4)
- ✅ Staleness detection (Task 7 process_job)
- ✅ Dead man's switch (Task 10)
- ✅ Telegram alerts with dedup (Task 5)
- ✅ DLQ with context bundle (Tasks 6, 7)
- ✅ Auto-discovery (state/ glob in collect_state_files)
- ✅ Pre-existing bug fixes (Task 1)
- ✅ Heartbeat bootstrapping for existing scripts (Task 9)
- ✅ LaunchAgent scheduling (Task 8)

**No placeholders found.**

**Type consistency:** All functions use consistent names across tasks (e.g., `retry_job`, `dispatch_aider_fix`, `verify_fix`, `add_to_dlq`, `clear_dlq_entry`, `record_success`, `record_failure`, `get_state`).
