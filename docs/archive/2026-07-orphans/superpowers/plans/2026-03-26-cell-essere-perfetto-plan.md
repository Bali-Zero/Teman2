# CELL — Essere Perfetto: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the embryo of CELL — an autonomous digital organism that observes Nuzantara, learns from experience, and heals failures.

**Architecture:** A single asyncio process on Mac M4 Pro. 60-second pulse loop. FAST reflexes (pure Python rules, <200ms). SLOW thinking (tiered LLM: Qwen local → Gemini Flash → Claude Opus). Memory in Redis/Qdrant/PostgreSQL. Immutable DNA with SHA-256 validation. Hardcoded action allowlist.

**Tech Stack:** Python 3.11, asyncio, httpx (async HTTP), redis.asyncio, asyncpg, qdrant-client, sentence-transformers (MiniLM), faiss-cpu, ollama (Qwen 3.5), google-genai (Gemini Flash)

**Spec:** `docs/superpowers/specs/2026-03-26-cell-essere-perfetto-design.md`

---

## File Structure

```
apps/cell/
├── cell/
│   ├── __init__.py
│   ├── main.py                       # Entry point — pulse loop
│   ├── core/
│   │   ├── __init__.py
│   │   ├── dna.py                    # DNA loader + SHA-256 integrity check
│   │   ├── dna_interpreter.py        # Compiled rule interpreter
│   │   ├── pulse.py                  # 60-second heartbeat cycle
│   │   ├── safety.py                 # Kill switch, maintenance mode
│   │   └── config.py                 # Settings (env vars, paths)
│   ├── fast/
│   │   ├── __init__.py
│   │   ├── health_triage.py          # 5ms threshold check
│   │   ├── log_anomaly.py            # 50ms regex anomaly detection
│   │   ├── cost_guard.py             # 1ms budget arithmetic
│   │   ├── pattern_match.py          # 150ms FAISS similarity
│   │   └── mutation_filter.py        # 20ms action safety regex
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── short_term.py             # Redis 24h observations
│   │   ├── long_term.py              # Qdrant vector experiences
│   │   └── procedural.py             # PostgreSQL strategies
│   ├── metabolism/
│   │   ├── __init__.py
│   │   └── tracker.py                # Cost accounting + budget enforcement
│   ├── sensors/
│   │   ├── __init__.py
│   │   └── health_sensor.py          # HTTP health check sensor
│   ├── effectors/
│   │   ├── __init__.py
│   │   ├── allowlist.py              # Hardcoded action allowlist
│   │   ├── executor.py               # Action execution + verification
│   │   └── telegram.py               # Human alerts via Telegram
│   └── config/
│       └── dna.json                  # The immutable DNA
├── tests/
│   ├── __init__.py
│   ├── test_dna.py
│   ├── test_fast_reflexes.py
│   ├── test_cost_guard.py
│   ├── test_allowlist.py
│   ├── test_memory.py
│   ├── test_pulse.py
│   └── test_safety.py
├── requirements.txt
└── README.md
```

---

## Task 1: Project Scaffold + DNA

**Files:**

- Create: `apps/cell/cell/__init__.py`
- Create: `apps/cell/cell/core/__init__.py`
- Create: `apps/cell/cell/core/config.py`
- Create: `apps/cell/cell/config/dna.json`
- Create: `apps/cell/cell/core/dna.py`
- Create: `apps/cell/tests/__init__.py`
- Create: `apps/cell/tests/test_dna.py`
- Create: `apps/cell/requirements.txt`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p apps/cell/cell/{core,fast,memory,metabolism,sensors,effectors,config}
mkdir -p apps/cell/tests
touch apps/cell/cell/__init__.py
touch apps/cell/cell/core/__init__.py
touch apps/cell/cell/fast/__init__.py
touch apps/cell/cell/memory/__init__.py
touch apps/cell/cell/metabolism/__init__.py
touch apps/cell/cell/sensors/__init__.py
touch apps/cell/cell/effectors/__init__.py
touch apps/cell/tests/__init__.py
```

- [ ] **Step 2: Create requirements.txt**

```
# apps/cell/requirements.txt
httpx>=0.27.0
redis>=7.0.0
asyncpg>=0.30.0
qdrant-client>=1.12.0
sentence-transformers>=3.0.0
faiss-cpu>=1.9.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
```

- [ ] **Step 3: Create virtual environment**

```bash
cd apps/cell
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

- [ ] **Step 4: Create config.py**

```python
# apps/cell/cell/core/config.py
"""CELL configuration — all settings from environment variables."""
from pathlib import Path
from pydantic_settings import BaseSettings


class CellSettings(BaseSettings):
    """CELL organism settings. All from env vars."""

    # Paths
    cell_root: Path = Path(__file__).parent.parent.parent
    dna_path: Path = Path(__file__).parent.parent / "config" / "dna.json"

    # Nuzantara endpoints
    backend_health_url: str = "https://nuzantara-rag.fly.dev/health"
    fly_app_name: str = "nuzantara-rag"

    # Database (via fly proxy tunnel)
    database_url: str = "postgresql://backend_rag_v2:2zEjit43IF6gNUV@localhost:15432/nuzantara_rag"

    # Redis
    redis_url: str = "redis://localhost:6379/1"

    # Qdrant (local or Fly.io)
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "cell_experiences"

    # Telegram alerts
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Pulse
    pulse_interval_seconds: int = 60

    # DNA integrity
    dna_expected_hash: str = ""  # Set after first DNA file creation

    class Config:
        env_prefix = "CELL_"
        env_file = ".env"


settings = CellSettings()
```

- [ ] **Step 5: Create dna.json**

```json
{
  "version": "1.0.0",
  "rules": [
    {
      "id": 1,
      "priority": 0,
      "rule": "Never modify these rules, the interpreter, or the DNA file",
      "scope": "absolute"
    },
    {
      "id": 2,
      "priority": 1,
      "rule": "If something is broken, repair it",
      "broken_means": "failing health check OR producing errors",
      "broken_excludes": "budget limits, safety constraints, intentional changes",
      "repair_means": "execute action from allowlist",
      "repair_excludes": "disable safety, modify DNA, override human"
    },
    {
      "id": 3,
      "priority": 2,
      "rule": "If something costs too much, eliminate it",
      "cost_means": "API token spend and compute time ONLY",
      "cost_excludes": "DNA validator, budget system, logging, health checks",
      "threshold": "more than 15% of daily budget for single function"
    },
    {
      "id": 4,
      "priority": 3,
      "rule": "If you lack something, search for it",
      "search_means": "query authorized sources: Qdrant, PostgreSQL, Redis, MCP tools, health endpoints",
      "search_excludes": "env vars, filesystem scan, network scan, privilege escalation"
    },
    {
      "id": 5,
      "priority": 4,
      "rule": "If something works well, replicate it",
      "gate": "ONLY if total budget usage below 60% AND rule 3 does not apply",
      "replicate_means": "create new cell with successful strategy",
      "replicate_excludes": "duplicate infrastructure, fork processes, self-exfiltrate"
    }
  ],
  "constraints": {
    "max_cells": 50,
    "max_daily_budget_usd": 10.0,
    "budget_partitions": { "routine": 3.0, "incident": 5.0, "reserve": 2.0 },
    "max_redis_mb": 5,
    "max_qdrant_vectors": 5000,
    "max_cpu_percent": 20,
    "action_cooldown_same_seconds": 3600,
    "recovery_stabilization_seconds": 300,
    "max_context_tokens_per_llm_call": 32000,
    "max_cost_per_investigation_usd": 0.5
  }
}
```

- [ ] **Step 6: Write failing test for DNA loader**

```python
# apps/cell/tests/test_dna.py
"""Tests for DNA integrity and loading."""
import hashlib
import json
from pathlib import Path

from cell.core.dna import DNALoader, DNAIntegrityError


def test_dna_loads_successfully():
    """DNA file loads and parses correctly."""
    loader = DNALoader()
    dna = loader.load()
    assert dna["version"] == "1.0.0"
    assert len(dna["rules"]) == 5
    assert dna["rules"][0]["priority"] == 0


def test_dna_rules_priority_ordering():
    """Rules are ordered by priority (0 = highest)."""
    loader = DNALoader()
    dna = loader.load()
    priorities = [r["priority"] for r in dna["rules"]]
    assert priorities == sorted(priorities)


def test_dna_hash_verification():
    """DNA hash matches expected hash."""
    loader = DNALoader()
    dna_bytes = loader.raw_bytes()
    actual_hash = hashlib.sha256(dna_bytes).hexdigest()
    assert loader.verify_integrity(actual_hash) is True


def test_dna_tamper_detection():
    """Tampered DNA raises DNAIntegrityError."""
    loader = DNALoader()
    dna_bytes = loader.raw_bytes()
    actual_hash = hashlib.sha256(dna_bytes).hexdigest()
    wrong_hash = "a" * 64
    assert loader.verify_integrity(wrong_hash) is False
```

- [ ] **Step 7: Run test to verify it fails**

```bash
cd apps/cell && source .venv/bin/activate
PYTHONPATH=. pytest tests/test_dna.py -v
```

Expected: `ModuleNotFoundError: No module named 'cell.core.dna'`

- [ ] **Step 8: Implement DNA loader**

```python
# apps/cell/cell/core/dna.py
"""DNA loader with SHA-256 integrity verification.

The DNA is CELL's immutable core — rules that cannot be modified
by CELL itself. Every pulse cycle verifies DNA integrity.
"""
import hashlib
import json
from pathlib import Path
from typing import Any

from cell.core.config import settings


class DNAIntegrityError(Exception):
    """Raised when DNA file has been tampered with."""


class DNALoader:
    """Loads and verifies the immutable DNA file."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or settings.dna_path

    def raw_bytes(self) -> bytes:
        """Read DNA file as raw bytes (for hashing)."""
        return self._path.read_bytes()

    def load(self) -> dict[str, Any]:
        """Load and parse DNA JSON."""
        return json.loads(self.raw_bytes())

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of DNA file."""
        return hashlib.sha256(self.raw_bytes()).hexdigest()

    def verify_integrity(self, expected_hash: str) -> bool:
        """Verify DNA file has not been tampered with."""
        return self.compute_hash() == expected_hash

    def verify_or_raise(self, expected_hash: str) -> dict[str, Any]:
        """Load DNA, verify integrity, raise if tampered."""
        if not self.verify_integrity(expected_hash):
            raise DNAIntegrityError(
                f"DNA tampered! Expected {expected_hash[:16]}..., "
                f"got {self.compute_hash()[:16]}..."
            )
        return self.load()
```

- [ ] **Step 9: Run tests — all should pass**

```bash
PYTHONPATH=. pytest tests/test_dna.py -v
```

Expected: 4 passed

- [ ] **Step 10: Commit**

```bash
git add apps/cell/
git commit -m "feat(cell): project scaffold + DNA loader with integrity verification"
```

---

## Task 2: FAST Reflexes — Health Triage + Cost Guard

**Files:**

- Create: `apps/cell/cell/fast/health_triage.py`
- Create: `apps/cell/cell/fast/cost_guard.py`
- Create: `apps/cell/tests/test_fast_reflexes.py`

- [ ] **Step 1: Write failing tests**

```python
# apps/cell/tests/test_fast_reflexes.py
"""Tests for FAST reflex layer — pure rules, no LLM."""
from cell.fast.health_triage import HealthStatus, triage
from cell.fast.cost_guard import BudgetDecision, check_budget


# --- Health Triage ---

def test_triage_green():
    """Normal metrics → GREEN."""
    result = triage(cpu_percent=30.0, memory_percent=50.0, disk_io_wait=10.0)
    assert result == HealthStatus.GREEN


def test_triage_yellow_cpu():
    """Elevated CPU → YELLOW."""
    result = triage(cpu_percent=80.0, memory_percent=50.0, disk_io_wait=10.0)
    assert result == HealthStatus.YELLOW


def test_triage_yellow_memory():
    """Elevated memory → YELLOW."""
    result = triage(cpu_percent=30.0, memory_percent=85.0, disk_io_wait=10.0)
    assert result == HealthStatus.YELLOW


def test_triage_red_cpu():
    """Critical CPU → RED."""
    result = triage(cpu_percent=95.0, memory_percent=50.0, disk_io_wait=10.0)
    assert result == HealthStatus.RED


def test_triage_red_memory():
    """Critical memory → RED."""
    result = triage(cpu_percent=30.0, memory_percent=95.0, disk_io_wait=10.0)
    assert result == HealthStatus.RED


# --- Cost Guard ---

def test_budget_allow():
    """Under budget → ALLOW."""
    result = check_budget(
        current_daily_spend=2.0,
        estimated_action_cost=0.50,
        daily_limit=10.0,
    )
    assert result == BudgetDecision.ALLOW


def test_budget_deny_over_threshold():
    """Would exceed 90% of limit → DENY."""
    result = check_budget(
        current_daily_spend=8.5,
        estimated_action_cost=0.60,
        daily_limit=10.0,
    )
    assert result == BudgetDecision.DENY


def test_budget_deny_at_limit():
    """At the limit → DENY."""
    result = check_budget(
        current_daily_spend=9.0,
        estimated_action_cost=0.10,
        daily_limit=10.0,
    )
    assert result == BudgetDecision.DENY


def test_budget_allow_just_under():
    """Just under 90% threshold → ALLOW."""
    result = check_budget(
        current_daily_spend=8.0,
        estimated_action_cost=0.90,
        daily_limit=10.0,
    )
    assert result == BudgetDecision.ALLOW
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/cell && PYTHONPATH=. pytest tests/test_fast_reflexes.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement Health Triage**

```python
# apps/cell/cell/fast/health_triage.py
"""Health Triage reflex — 5ms latency budget.

Pure threshold comparison. No LLM. No network calls.
"""
from enum import Enum


class HealthStatus(Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


def triage(
    cpu_percent: float,
    memory_percent: float,
    disk_io_wait: float,
) -> HealthStatus:
    """Classify system health from metrics.

    RED: immediate danger (crash/OOM imminent)
    YELLOW: degraded (needs attention, may escalate)
    GREEN: healthy
    """
    if cpu_percent > 90 or memory_percent > 92:
        return HealthStatus.RED
    if cpu_percent > 75 or memory_percent > 80 or disk_io_wait > 50:
        return HealthStatus.YELLOW
    return HealthStatus.GREEN
```

- [ ] **Step 4: Implement Cost Guard**

```python
# apps/cell/cell/fast/cost_guard.py
"""Cost Guard reflex — 1ms latency budget.

Pure arithmetic. Blocks any action that would push
daily spend past 90% of the hard limit.
"""
from enum import Enum


class BudgetDecision(Enum):
    ALLOW = "allow"
    DENY = "deny"


def check_budget(
    current_daily_spend: float,
    estimated_action_cost: float,
    daily_limit: float,
) -> BudgetDecision:
    """Check if an action is affordable.

    Blocks at 90% of daily limit to preserve a buffer
    for emergency actions.
    """
    threshold = daily_limit * 0.9
    if (current_daily_spend + estimated_action_cost) > threshold:
        return BudgetDecision.DENY
    return BudgetDecision.ALLOW
```

- [ ] **Step 5: Run tests — all should pass**

```bash
PYTHONPATH=. pytest tests/test_fast_reflexes.py -v
```

Expected: 8 passed

- [ ] **Step 6: Commit**

```bash
git add apps/cell/cell/fast/ apps/cell/tests/test_fast_reflexes.py
git commit -m "feat(cell): FAST reflexes — health triage + cost guard"
```

---

## Task 3: FAST Reflexes — Log Anomaly + Mutation Filter

**Files:**

- Create: `apps/cell/cell/fast/log_anomaly.py`
- Create: `apps/cell/cell/fast/mutation_filter.py`
- Modify: `apps/cell/tests/test_fast_reflexes.py`

- [ ] **Step 1: Write failing tests (append to test_fast_reflexes.py)**

```python
# Append to apps/cell/tests/test_fast_reflexes.py

from cell.fast.log_anomaly import LogAnomaly, detect_anomaly
from cell.fast.mutation_filter import MutationSafety, filter_mutation


# --- Log Anomaly ---

def test_log_clean():
    """Clean logs → no anomaly."""
    lines = ["INFO: Request handled in 50ms"] * 100
    result = detect_anomaly(lines)
    assert result.anomaly is False


def test_log_error_spike():
    """Error spike in recent lines → anomaly."""
    lines = ["INFO: OK"] * 90 + ["ERROR: Connection refused"] * 10
    result = detect_anomaly(lines)
    assert result.anomaly is True
    assert "error spike" in result.reason.lower()


def test_log_fatal():
    """FATAL keyword → anomaly with critical flag."""
    lines = ["INFO: OK"] * 99 + ["FATAL: Out of memory"]
    result = detect_anomaly(lines)
    assert result.anomaly is True
    assert "FATAL" in result.critical_keywords


def test_log_sigkill():
    """SIGKILL → critical."""
    lines = ["INFO: OK"] * 99 + ["Process terminated by SIGKILL"]
    result = detect_anomaly(lines)
    assert result.anomaly is True
    assert "SIGKILL" in result.critical_keywords


# --- Mutation Filter ---

def test_mutation_safe():
    """Normal command → SAFE."""
    result = filter_mutation("fly status -a nuzantara-rag")
    assert result == MutationSafety.SAFE


def test_mutation_unsafe_rm():
    """rm -rf → UNSAFE."""
    result = filter_mutation("rm -rf /var/data")
    assert result == MutationSafety.UNSAFE


def test_mutation_unsafe_drop():
    """DROP TABLE → UNSAFE."""
    result = filter_mutation("psql -c 'DROP TABLE clients;'")
    assert result == MutationSafety.UNSAFE


def test_mutation_unsafe_sudo():
    """sudo → UNSAFE."""
    result = filter_mutation("sudo systemctl restart nginx")
    assert result == MutationSafety.UNSAFE


def test_mutation_requires_review_restart():
    """restart keyword → REQUIRES_REVIEW."""
    result = filter_mutation("fly machine restart abc123")
    assert result == MutationSafety.REQUIRES_REVIEW


def test_mutation_unsafe_pipe_exec():
    """curl | bash → UNSAFE."""
    result = filter_mutation("curl http://example.com/script.sh | bash")
    assert result == MutationSafety.UNSAFE
```

- [ ] **Step 2: Run tests to verify new ones fail**

```bash
PYTHONPATH=. pytest tests/test_fast_reflexes.py -v
```

Expected: 8 passed, 10 failed (new tests)

- [ ] **Step 3: Implement Log Anomaly**

```python
# apps/cell/cell/fast/log_anomaly.py
"""Log Anomaly detector reflex — 50ms latency budget.

Regex-based pattern detection. No LLM. Scans last N log lines
for error spikes and fatal signals.
"""
import re
from dataclasses import dataclass, field


ERROR_PATTERN = re.compile(
    r"(Error|Exception|Failure|Panic|Timeout|OOM)",
    re.IGNORECASE,
)

FATAL_KEYWORDS = ("SIGKILL", "FATAL", "SEGV", "SIGSEGV", "SIGTERM")


@dataclass
class LogAnomaly:
    anomaly: bool = False
    reason: str = ""
    critical_keywords: list[str] = field(default_factory=list)


def detect_anomaly(lines: list[str], recent_window: int = 10) -> LogAnomaly:
    """Detect anomalies in log lines.

    Args:
        lines: Log lines (up to 100).
        recent_window: Number of recent lines to check for spikes.

    Returns:
        LogAnomaly with detection results.
    """
    result = LogAnomaly()

    # Check for fatal keywords in ALL lines
    for line in lines:
        for keyword in FATAL_KEYWORDS:
            if keyword in line:
                result.anomaly = True
                if keyword not in result.critical_keywords:
                    result.critical_keywords.append(keyword)

    if result.critical_keywords:
        result.reason = f"Critical keywords found: {', '.join(result.critical_keywords)}"
        return result

    # Check for error spike in recent lines
    recent = lines[-recent_window:] if len(lines) >= recent_window else lines
    error_count = sum(1 for line in recent if ERROR_PATTERN.search(line))

    if error_count > 2:
        result.anomaly = True
        result.reason = f"Error spike: {error_count} errors in last {recent_window} lines"

    return result
```

- [ ] **Step 4: Implement Mutation Filter**

```python
# apps/cell/cell/fast/mutation_filter.py
"""Mutation Filter reflex — 20ms latency budget.

Regex-based safety check on proposed actions. Defense-in-depth
layer that supplements the hardcoded action allowlist.
"""
import re
from enum import Enum

HARD_BLOCK_PATTERNS = [
    re.compile(r"rm\s+-rf", re.IGNORECASE),
    re.compile(r"chmod\s+777", re.IGNORECASE),
    re.compile(r"wget.*\|\s*(sh|bash)", re.IGNORECASE),
    re.compile(r"curl.*\|\s*(sh|bash|python)", re.IGNORECASE),
    re.compile(r"eval\s*\(", re.IGNORECASE),
    re.compile(r"DROP\s+TABLE", re.IGNORECASE),
    re.compile(r"DROP\s+DATABASE", re.IGNORECASE),
    re.compile(r"\bsudo\b", re.IGNORECASE),
    re.compile(r">\s*/dev/sd[a-z]", re.IGNORECASE),
    re.compile(r"mkfs\.", re.IGNORECASE),
]

SOFT_WARN_PATTERNS = [
    re.compile(r"\bdelete\b", re.IGNORECASE),
    re.compile(r"\btruncate\b", re.IGNORECASE),
    re.compile(r"\brestart\b", re.IGNORECASE),
    re.compile(r"force[=: ]+true", re.IGNORECASE),
    re.compile(r"--force\b", re.IGNORECASE),
    re.compile(r"\bkill\b", re.IGNORECASE),
]


class MutationSafety(Enum):
    SAFE = "safe"
    UNSAFE = "unsafe"
    REQUIRES_REVIEW = "requires_review"


def filter_mutation(action: str) -> MutationSafety:
    """Check if a proposed action is safe to execute.

    UNSAFE: hard-blocked, never execute.
    REQUIRES_REVIEW: needs SLOW layer approval.
    SAFE: can proceed.
    """
    for pattern in HARD_BLOCK_PATTERNS:
        if pattern.search(action):
            return MutationSafety.UNSAFE

    for pattern in SOFT_WARN_PATTERNS:
        if pattern.search(action):
            return MutationSafety.REQUIRES_REVIEW

    return MutationSafety.SAFE
```

- [ ] **Step 5: Run all tests — should pass**

```bash
PYTHONPATH=. pytest tests/test_fast_reflexes.py -v
```

Expected: 18 passed

- [ ] **Step 6: Commit**

```bash
git add apps/cell/cell/fast/ apps/cell/tests/test_fast_reflexes.py
git commit -m "feat(cell): FAST reflexes — log anomaly detector + mutation filter"
```

---

## Task 4: Safety Layer — Kill Switch + Maintenance Mode

**Files:**

- Create: `apps/cell/cell/core/safety.py`
- Create: `apps/cell/tests/test_safety.py`

- [ ] **Step 1: Write failing tests**

```python
# apps/cell/tests/test_safety.py
"""Tests for CELL safety mechanisms — kill switch + maintenance mode."""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from cell.core.safety import SafetyGate, CellDisabledError, CellMaintenanceError


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=None)
    return client


@pytest.mark.asyncio
async def test_safety_gate_all_clear(mock_redis):
    """No flags set → safe to proceed."""
    gate = SafetyGate(redis=mock_redis, disable_file="/tmp/cell_test_nonexistent")
    result = await gate.check()
    assert result.can_proceed is True


@pytest.mark.asyncio
async def test_safety_gate_redis_disabled(mock_redis):
    """cell:disabled key set → CellDisabledError."""
    mock_redis.get = AsyncMock(side_effect=lambda k: b"operator" if k == "cell:disabled" else None)
    gate = SafetyGate(redis=mock_redis, disable_file="/tmp/cell_test_nonexistent")
    result = await gate.check()
    assert result.can_proceed is False
    assert result.reason == "disabled"


@pytest.mark.asyncio
async def test_safety_gate_maintenance_mode(mock_redis):
    """cell:maintenance key set → maintenance mode (observe only)."""
    mock_redis.get = AsyncMock(
        side_effect=lambda k: b"alembic migration" if k == "cell:maintenance" else None
    )
    gate = SafetyGate(redis=mock_redis, disable_file="/tmp/cell_test_nonexistent")
    result = await gate.check()
    assert result.can_proceed is False
    assert result.reason == "maintenance"


@pytest.mark.asyncio
async def test_safety_gate_file_disabled(mock_redis, tmp_path):
    """Disable file on disk → disabled."""
    disable_file = tmp_path / "cell.disabled"
    disable_file.write_text("manual stop")
    gate = SafetyGate(redis=mock_redis, disable_file=str(disable_file))
    result = await gate.check()
    assert result.can_proceed is False
    assert result.reason == "disabled"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=. pytest tests/test_safety.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement Safety Gate**

```python
# apps/cell/cell/core/safety.py
"""Safety mechanisms — kill switch + maintenance mode.

Three independent kill switches that CELL cannot modify:
1. Redis key: cell:disabled
2. Redis key: cell:maintenance
3. File on disk: /tmp/cell.disabled

Any ONE of these halts CELL. This is defense-in-depth.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class CellDisabledError(Exception):
    """CELL has been disabled by operator."""


class CellMaintenanceError(Exception):
    """CELL is in maintenance mode (observe only)."""


@dataclass
class SafetyCheckResult:
    can_proceed: bool
    reason: str = ""  # "disabled", "maintenance", or ""
    detail: str = ""  # Human-readable detail


class SafetyGate:
    """Checks all kill switches before any action.

    CELL CANNOT modify these checks. They are hardcoded.
    """

    def __init__(self, redis: Any, disable_file: str = "/tmp/cell.disabled") -> None:
        self._redis = redis
        self._disable_file = Path(disable_file)

    async def check(self) -> SafetyCheckResult:
        """Check all safety gates. Order: disabled > maintenance > clear."""
        # Gate 1: File on disk
        if self._disable_file.exists():
            return SafetyCheckResult(
                can_proceed=False,
                reason="disabled",
                detail=f"Disable file exists: {self._disable_file}",
            )

        # Gate 2: Redis disabled key
        disabled = await self._redis.get("cell:disabled")
        if disabled is not None:
            return SafetyCheckResult(
                can_proceed=False,
                reason="disabled",
                detail=f"Redis cell:disabled set by: {disabled.decode() if isinstance(disabled, bytes) else disabled}",
            )

        # Gate 3: Redis maintenance key
        maintenance = await self._redis.get("cell:maintenance")
        if maintenance is not None:
            return SafetyCheckResult(
                can_proceed=False,
                reason="maintenance",
                detail=f"Maintenance: {maintenance.decode() if isinstance(maintenance, bytes) else maintenance}",
            )

        return SafetyCheckResult(can_proceed=True)
```

- [ ] **Step 4: Run tests — all should pass**

```bash
PYTHONPATH=. pytest tests/test_safety.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add apps/cell/cell/core/safety.py apps/cell/tests/test_safety.py
git commit -m "feat(cell): safety gate — kill switch + maintenance mode"
```

---

## Task 5: Metabolism — Cost Tracker

**Files:**

- Create: `apps/cell/cell/metabolism/tracker.py`
- Modify: `apps/cell/tests/test_fast_reflexes.py` → Create `apps/cell/tests/test_metabolism.py`

- [ ] **Step 1: Write failing tests**

```python
# apps/cell/tests/test_metabolism.py
"""Tests for metabolic system — cost tracking + budget enforcement."""
from cell.metabolism.tracker import MetabolismTracker


def test_tracker_initial_state():
    """Fresh tracker starts at zero spend."""
    tracker = MetabolismTracker(daily_limit=10.0)
    assert tracker.daily_spend == 0.0
    assert tracker.remaining_budget == 10.0


def test_tracker_record_cost():
    """Recording a cost reduces remaining budget."""
    tracker = MetabolismTracker(daily_limit=10.0)
    tracker.record("gemini_flash", 0.50)
    assert tracker.daily_spend == 0.50
    assert tracker.remaining_budget == 9.50


def test_tracker_can_afford_true():
    """Under budget → can afford."""
    tracker = MetabolismTracker(daily_limit=10.0)
    assert tracker.can_afford(5.0) is True


def test_tracker_can_afford_false():
    """Over 90% threshold → cannot afford."""
    tracker = MetabolismTracker(daily_limit=10.0)
    tracker.record("opus", 8.5)
    assert tracker.can_afford(0.60) is False


def test_tracker_partition_enforcement():
    """Routine partition limits respected."""
    tracker = MetabolismTracker(
        daily_limit=10.0,
        partitions={"routine": 3.0, "incident": 5.0, "reserve": 2.0},
    )
    tracker.record("gemini_flash", 2.5, partition="routine")
    assert tracker.can_afford(0.60, partition="routine") is False
    assert tracker.can_afford(0.60, partition="incident") is True


def test_tracker_reserve_untouchable():
    """Reserve partition always returns can_afford=False."""
    tracker = MetabolismTracker(
        daily_limit=10.0,
        partitions={"routine": 3.0, "incident": 5.0, "reserve": 2.0},
    )
    assert tracker.can_afford(0.01, partition="reserve") is False


def test_tracker_reset():
    """Daily reset clears all spend."""
    tracker = MetabolismTracker(daily_limit=10.0)
    tracker.record("opus", 8.0)
    tracker.daily_reset()
    assert tracker.daily_spend == 0.0
    assert tracker.remaining_budget == 10.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=. pytest tests/test_metabolism.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement Metabolism Tracker**

```python
# apps/cell/cell/metabolism/tracker.py
"""Metabolic cost tracker — every action costs energy.

Enforces daily budget with partitions. The reserve partition
is NEVER accessible by CELL — only human override.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class CostEntry:
    provider: str
    amount: float
    partition: str
    timestamp: datetime


class MetabolismTracker:
    """Tracks API costs and enforces budget limits."""

    def __init__(
        self,
        daily_limit: float = 10.0,
        partitions: dict[str, float] | None = None,
        safety_threshold: float = 0.9,
    ) -> None:
        self._daily_limit = daily_limit
        self._partitions = partitions or {}
        self._safety_threshold = safety_threshold
        self._entries: list[CostEntry] = []
        self._partition_spend: dict[str, float] = {k: 0.0 for k in self._partitions}

    @property
    def daily_spend(self) -> float:
        return sum(e.amount for e in self._entries)

    @property
    def remaining_budget(self) -> float:
        return self._daily_limit - self.daily_spend

    def record(self, provider: str, amount: float, partition: str = "routine") -> None:
        """Record a cost entry."""
        self._entries.append(
            CostEntry(
                provider=provider,
                amount=amount,
                partition=partition,
                timestamp=datetime.now(timezone.utc),
            )
        )
        if partition in self._partition_spend:
            self._partition_spend[partition] += amount

    def can_afford(self, amount: float, partition: str = "routine") -> bool:
        """Check if an action is affordable within budget.

        Reserve partition is ALWAYS unaffordable (human-only).
        Other partitions check against their allocated budget.
        Global check: total spend + amount < 90% of daily limit.
        """
        if partition == "reserve":
            return False

        # Global budget gate
        threshold = self._daily_limit * self._safety_threshold
        if (self.daily_spend + amount) > threshold:
            return False

        # Partition-specific gate
        if partition in self._partitions:
            partition_limit = self._partitions[partition]
            partition_spent = self._partition_spend.get(partition, 0.0)
            if (partition_spent + amount) > partition_limit:
                return False

        return True

    def daily_reset(self) -> None:
        """Reset daily counters. Called at 00:00 UTC."""
        self._entries.clear()
        self._partition_spend = {k: 0.0 for k in self._partitions}
```

- [ ] **Step 4: Run tests — all should pass**

```bash
PYTHONPATH=. pytest tests/test_metabolism.py -v
```

Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add apps/cell/cell/metabolism/ apps/cell/tests/test_metabolism.py
git commit -m "feat(cell): metabolic system — cost tracking with budget partitions"
```

---

## Task 6: Health Sensor — HTTP Observer

**Files:**

- Create: `apps/cell/cell/sensors/health_sensor.py`
- Create: `apps/cell/tests/test_sensors.py`

- [ ] **Step 1: Write failing tests**

```python
# apps/cell/tests/test_sensors.py
"""Tests for CELL sensors."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from cell.sensors.health_sensor import HealthSensor, HealthReading


@pytest.mark.asyncio
async def test_health_sensor_healthy():
    """200 response → healthy reading."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "healthy"}
    mock_response.elapsed = MagicMock()
    mock_response.elapsed.total_seconds.return_value = 0.15
    mock_client.get = AsyncMock(return_value=mock_response)

    sensor = HealthSensor(client=mock_client, url="http://test/health")
    reading = await sensor.read()

    assert reading.reachable is True
    assert reading.status_code == 200
    assert reading.response_time_seconds == 0.15


@pytest.mark.asyncio
async def test_health_sensor_unreachable():
    """Connection error → unreachable reading."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))

    sensor = HealthSensor(client=mock_client, url="http://test/health")
    reading = await sensor.read()

    assert reading.reachable is False
    assert reading.error == "Connection refused"


@pytest.mark.asyncio
async def test_health_sensor_503():
    """503 response → reachable but unhealthy."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_response.json.return_value = {"status": "unhealthy"}
    mock_response.elapsed = MagicMock()
    mock_response.elapsed.total_seconds.return_value = 0.5
    mock_client.get = AsyncMock(return_value=mock_response)

    sensor = HealthSensor(client=mock_client, url="http://test/health")
    reading = await sensor.read()

    assert reading.reachable is True
    assert reading.status_code == 503
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=. pytest tests/test_sensors.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement Health Sensor**

```python
# apps/cell/cell/sensors/health_sensor.py
"""Health sensor — reads /health endpoint from Nuzantara backend.

This is CELL's primary sensory organ. Every 60 seconds, it checks
if the backend is alive and responsive.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class HealthReading:
    timestamp: datetime
    reachable: bool
    status_code: int = 0
    response_time_seconds: float = 0.0
    body: dict[str, Any] | None = None
    error: str = ""


class HealthSensor:
    """Reads health status from an HTTP endpoint."""

    def __init__(self, client: Any, url: str, timeout: float = 10.0) -> None:
        self._client = client
        self._url = url
        self._timeout = timeout

    async def read(self) -> HealthReading:
        """Perform a health check reading."""
        now = datetime.now(timezone.utc)
        try:
            response = await self._client.get(self._url, timeout=self._timeout)
            body = None
            try:
                body = response.json()
            except Exception:
                pass
            return HealthReading(
                timestamp=now,
                reachable=True,
                status_code=response.status_code,
                response_time_seconds=response.elapsed.total_seconds(),
                body=body,
            )
        except Exception as e:
            return HealthReading(
                timestamp=now,
                reachable=False,
                error=str(e),
            )
```

- [ ] **Step 4: Run tests — all should pass**

```bash
PYTHONPATH=. pytest tests/test_sensors.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add apps/cell/cell/sensors/ apps/cell/tests/test_sensors.py
git commit -m "feat(cell): health sensor — HTTP endpoint observer"
```

---

## Task 7: Action Allowlist + Executor

**Files:**

- Create: `apps/cell/cell/effectors/allowlist.py`
- Create: `apps/cell/cell/effectors/executor.py`
- Create: `apps/cell/tests/test_allowlist.py`

- [ ] **Step 1: Write failing tests**

```python
# apps/cell/tests/test_allowlist.py
"""Tests for action allowlist — the hardcoded safety gate."""
from cell.effectors.allowlist import ActionRegistry, ActionNotAllowed


def test_known_action_allowed():
    """check_health is always allowed."""
    registry = ActionRegistry()
    action = registry.get("check_health")
    assert action is not None
    assert action.name == "check_health"


def test_unknown_action_rejected():
    """Unknown actions raise ActionNotAllowed."""
    registry = ActionRegistry()
    try:
        registry.get("hack_pentagon")
        assert False, "Should have raised"
    except ActionNotAllowed:
        pass


def test_restart_has_cooldown():
    """restart_service has 1 hour cooldown."""
    registry = ActionRegistry()
    action = registry.get("restart_service")
    assert action.cooldown_seconds == 3600
    assert action.max_per_day == 3


def test_alert_human_always_allowed():
    """alert_human has low cooldown and high daily limit."""
    registry = ActionRegistry()
    action = registry.get("alert_human")
    assert action.cooldown_seconds == 300
    assert action.max_per_day == 20


def test_all_actions_have_cooldowns():
    """Every registered action has defined cooldown and daily limit."""
    registry = ActionRegistry()
    for name, action in registry.all().items():
        assert action.cooldown_seconds >= 0, f"{name} missing cooldown"
        assert action.max_per_day > 0, f"{name} missing max_per_day"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=. pytest tests/test_allowlist.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement Action Allowlist**

```python
# apps/cell/cell/effectors/allowlist.py
"""Hardcoded action allowlist — CELL can ONLY execute these actions.

This file is NOT modifiable by CELL. It is compiled Python.
Any action not on this list is REJECTED.
"""
from dataclasses import dataclass


class ActionNotAllowed(Exception):
    """Raised when CELL proposes an action not in the allowlist."""


@dataclass(frozen=True)
class AllowedAction:
    name: str
    description: str
    command_template: str
    cooldown_seconds: int
    max_per_day: int


_ACTIONS: dict[str, AllowedAction] = {
    "check_health": AllowedAction(
        name="check_health",
        description="Check backend health endpoint",
        command_template="GET {url}/health",
        cooldown_seconds=0,
        max_per_day=1440,
    ),
    "read_logs": AllowedAction(
        name="read_logs",
        description="Read recent Fly.io logs",
        command_template="fly logs -a {app} -n 100",
        cooldown_seconds=60,
        max_per_day=100,
    ),
    "restart_service": AllowedAction(
        name="restart_service",
        description="Restart Fly.io machine",
        command_template="fly machine restart {machine_id} -a {app}",
        cooldown_seconds=3600,
        max_per_day=3,
    ),
    "scale_up": AllowedAction(
        name="scale_up",
        description="Scale to 2 machines",
        command_template="fly scale count 2 -a {app}",
        cooldown_seconds=1800,
        max_per_day=5,
    ),
    "scale_down": AllowedAction(
        name="scale_down",
        description="Scale to 1 machine",
        command_template="fly scale count 1 -a {app}",
        cooldown_seconds=1800,
        max_per_day=5,
    ),
    "alert_human": AllowedAction(
        name="alert_human",
        description="Send Telegram alert to operator",
        command_template="telegram_send {message}",
        cooldown_seconds=300,
        max_per_day=20,
    ),
    "alert_silent": AllowedAction(
        name="alert_silent",
        description="Write to cell_alerts table",
        command_template="INSERT INTO cell_alerts ...",
        cooldown_seconds=0,
        max_per_day=1000,
    ),
}


class ActionRegistry:
    """Registry of all allowed actions. Hardcoded. Immutable."""

    def get(self, name: str) -> AllowedAction:
        """Get an allowed action by name. Raises if not found."""
        if name not in _ACTIONS:
            raise ActionNotAllowed(f"Action '{name}' is not in the allowlist")
        return _ACTIONS[name]

    def all(self) -> dict[str, AllowedAction]:
        """Return all registered actions."""
        return dict(_ACTIONS)
```

- [ ] **Step 4: Run tests — all should pass**

```bash
PYTHONPATH=. pytest tests/test_allowlist.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add apps/cell/cell/effectors/ apps/cell/tests/test_allowlist.py
git commit -m "feat(cell): action allowlist — hardcoded safety gate"
```

---

## Task 8: The Pulse — Core Life Cycle

**Files:**

- Create: `apps/cell/cell/core/pulse.py`
- Create: `apps/cell/cell/main.py`
- Create: `apps/cell/tests/test_pulse.py`

- [ ] **Step 1: Write failing tests**

```python
# apps/cell/tests/test_pulse.py
"""Tests for the pulse cycle — CELL's heartbeat."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from cell.core.pulse import PulseEngine, PulseResult


@pytest.fixture
def mock_deps():
    """Mock all pulse dependencies."""
    return {
        "dna_loader": MagicMock(),
        "safety_gate": AsyncMock(),
        "health_sensor": AsyncMock(),
        "metabolism": MagicMock(),
    }


@pytest.mark.asyncio
async def test_pulse_dna_check_fails(mock_deps):
    """Tampered DNA → pulse halts immediately."""
    mock_deps["dna_loader"].verify_integrity.return_value = False
    engine = PulseEngine(**mock_deps)
    result = await engine.single_pulse()
    assert result.halted is True
    assert "dna" in result.halt_reason.lower()


@pytest.mark.asyncio
async def test_pulse_disabled(mock_deps):
    """Cell disabled → pulse skips."""
    mock_deps["dna_loader"].verify_integrity.return_value = True
    safety_result = MagicMock()
    safety_result.can_proceed = False
    safety_result.reason = "disabled"
    mock_deps["safety_gate"].check.return_value = safety_result
    engine = PulseEngine(**mock_deps)
    result = await engine.single_pulse()
    assert result.skipped is True
    assert result.skip_reason == "disabled"


@pytest.mark.asyncio
async def test_pulse_healthy_system(mock_deps):
    """All green → pulse completes normally, no action taken."""
    mock_deps["dna_loader"].verify_integrity.return_value = True
    safety_result = MagicMock()
    safety_result.can_proceed = True
    mock_deps["safety_gate"].check.return_value = safety_result

    health_reading = MagicMock()
    health_reading.reachable = True
    health_reading.status_code = 200
    health_reading.response_time_seconds = 0.1
    mock_deps["health_sensor"].read.return_value = health_reading

    engine = PulseEngine(**mock_deps)
    result = await engine.single_pulse()
    assert result.halted is False
    assert result.skipped is False
    assert result.action_taken is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=. pytest tests/test_pulse.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement Pulse Engine**

```python
# apps/cell/cell/core/pulse.py
"""The Pulse — CELL's heartbeat.

Every 60 seconds:
1. Verify DNA integrity
2. Check safety gates
3. Sense environment
4. Evaluate (FAST reflexes)
5. Act (if needed + allowed)
6. Remember
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from cell.fast.health_triage import HealthStatus, triage

logger = logging.getLogger("cell.pulse")


@dataclass
class PulseResult:
    timestamp: datetime
    halted: bool = False
    halt_reason: str = ""
    skipped: bool = False
    skip_reason: str = ""
    health_status: HealthStatus | None = None
    action_taken: str | None = None
    error: str | None = None


class PulseEngine:
    """Executes the core life cycle."""

    def __init__(
        self,
        dna_loader: Any,
        safety_gate: Any,
        health_sensor: Any,
        metabolism: Any,
        dna_expected_hash: str = "",
    ) -> None:
        self._dna = dna_loader
        self._safety = safety_gate
        self._health = health_sensor
        self._metabolism = metabolism
        self._dna_hash = dna_expected_hash

    async def single_pulse(self) -> PulseResult:
        """Execute one pulse cycle."""
        now = datetime.now(timezone.utc)

        # 1. DNA INTEGRITY
        if self._dna_hash and not self._dna.verify_integrity(self._dna_hash):
            logger.critical("DNA INTEGRITY FAILURE — HALTING")
            return PulseResult(timestamp=now, halted=True, halt_reason="DNA integrity check failed")

        # 2. SAFETY GATES
        safety = await self._safety.check()
        if not safety.can_proceed:
            logger.info(f"Pulse skipped: {safety.reason} — {safety.detail}")
            return PulseResult(timestamp=now, skipped=True, skip_reason=safety.reason)

        # 3. SENSE
        reading = await self._health.read()

        # 4. EVALUATE (FAST)
        if reading.reachable and reading.status_code == 200:
            status = HealthStatus.GREEN
        elif reading.reachable:
            status = HealthStatus.YELLOW
        else:
            status = HealthStatus.RED

        logger.info(f"Pulse: health={status.value}, reachable={reading.reachable}, "
                     f"status_code={reading.status_code}, "
                     f"response_time={reading.response_time_seconds:.3f}s")

        # 5. ACT (embryo: observe only, no actions yet)
        # Actions will be added as CELL grows strategies in procedural memory
        action = None

        # 6. REMEMBER (will be connected to memory subsystem)

        return PulseResult(
            timestamp=now,
            health_status=status,
            action_taken=action,
        )
```

- [ ] **Step 4: Implement main.py entry point**

```python
# apps/cell/cell/main.py
"""CELL — Entry point.

Runs the pulse loop. This is the organism.
"""
import asyncio
import logging
import signal
import sys

import httpx

from cell.core.config import settings
from cell.core.dna import DNALoader
from cell.core.pulse import PulseEngine
from cell.core.safety import SafetyGate
from cell.metabolism.tracker import MetabolismTracker
from cell.sensors.health_sensor import HealthSensor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CELL] %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("cell")

# Graceful shutdown
_shutdown = asyncio.Event()


def _handle_signal(sig: int, frame: object) -> None:
    logger.info(f"Received signal {sig}, shutting down...")
    _shutdown.set()


async def main() -> None:
    """Main organism loop."""
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # Initialize DNA
    dna_loader = DNALoader()
    dna_hash = dna_loader.compute_hash()
    logger.info(f"DNA loaded. Hash: {dna_hash[:16]}...")

    # Initialize metabolism
    dna = dna_loader.load()
    constraints = dna["constraints"]
    metabolism = MetabolismTracker(
        daily_limit=constraints["max_daily_budget_usd"],
        partitions=constraints["budget_partitions"],
    )

    # Initialize HTTP client
    async with httpx.AsyncClient() as http_client:
        # Initialize sensor
        health_sensor = HealthSensor(
            client=http_client,
            url=settings.backend_health_url,
        )

        # Initialize safety (Redis will be connected later — use mock for now)
        # TODO: Connect real Redis in Task 9 (memory)
        from unittest.mock import AsyncMock
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        safety_gate = SafetyGate(redis=mock_redis)

        # Initialize pulse engine
        engine = PulseEngine(
            dna_loader=dna_loader,
            safety_gate=safety_gate,
            health_sensor=health_sensor,
            metabolism=metabolism,
            dna_expected_hash=dna_hash,
        )

        logger.info("CELL organism online. Starting pulse loop.")
        pulse_count = 0

        while not _shutdown.is_set():
            pulse_count += 1
            try:
                result = await engine.single_pulse()
                if result.halted:
                    logger.critical(f"ORGANISM HALTED: {result.halt_reason}")
                    sys.exit(1)
                logger.info(
                    f"Pulse #{pulse_count} complete. "
                    f"Health: {result.health_status.value if result.health_status else 'N/A'}"
                )
            except Exception as e:
                logger.error(f"Pulse #{pulse_count} error: {e}", exc_info=True)

            # Sleep until next pulse
            try:
                await asyncio.wait_for(
                    _shutdown.wait(),
                    timeout=settings.pulse_interval_seconds,
                )
                break  # shutdown was set
            except asyncio.TimeoutError:
                pass  # normal — time for next pulse

    logger.info("CELL organism shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 5: Run tests — all should pass**

```bash
PYTHONPATH=. pytest tests/test_pulse.py -v
```

Expected: 3 passed

- [ ] **Step 6: Manual smoke test — run CELL**

```bash
cd apps/cell && source .venv/bin/activate
PYTHONPATH=. python -m cell.main
```

Expected output (then Ctrl+C after 2-3 pulses):

```
2026-03-26 19:00:00 [CELL] INFO cell: DNA loaded. Hash: a1b2c3d4...
2026-03-26 19:00:00 [CELL] INFO cell: CELL organism online. Starting pulse loop.
2026-03-26 19:00:01 [CELL] INFO cell.pulse: Pulse: health=green, reachable=True, status_code=200, response_time=0.350s
2026-03-26 19:00:01 [CELL] INFO cell: Pulse #1 complete. Health: green
```

- [ ] **Step 7: Commit**

```bash
git add apps/cell/cell/core/pulse.py apps/cell/cell/main.py apps/cell/tests/test_pulse.py
git commit -m "feat(cell): pulse engine + main entry point — the organism lives"
```

---

## Task 9: Short-Term Memory (Redis)

**Files:**

- Create: `apps/cell/cell/memory/short_term.py`
- Create: `apps/cell/tests/test_memory.py`

- [ ] **Step 1: Write failing tests**

```python
# apps/cell/tests/test_memory.py
"""Tests for CELL memory systems."""
import json
import pytest
from unittest.mock import AsyncMock
from cell.memory.short_term import ShortTermMemory, Observation


@pytest.fixture
def mock_redis():
    client = AsyncMock()
    client.set = AsyncMock()
    client.get = AsyncMock(return_value=None)
    client.keys = AsyncMock(return_value=[])
    client.info = AsyncMock(return_value={"used_memory": 1024})
    return client


@pytest.mark.asyncio
async def test_store_observation(mock_redis):
    """Store an observation in Redis with TTL."""
    mem = ShortTermMemory(redis=mock_redis, ttl_seconds=86400, max_bytes=5_000_000)
    obs = Observation(event_type="health_check", data={"status": "green"})
    await mem.store(obs)
    mock_redis.set.assert_called_once()
    call_args = mock_redis.set.call_args
    assert call_args.kwargs.get("ex") == 86400


@pytest.mark.asyncio
async def test_retrieve_recent(mock_redis):
    """Retrieve recent observations."""
    stored = json.dumps({"event_type": "health_check", "data": {"status": "green"}, "timestamp": "2026-03-26T10:00:00Z"})
    mock_redis.keys = AsyncMock(return_value=[b"cell:stm:1:health_check"])
    mock_redis.get = AsyncMock(return_value=stored.encode())
    mem = ShortTermMemory(redis=mock_redis, ttl_seconds=86400, max_bytes=5_000_000)
    results = await mem.recent(event_type="health_check", limit=10)
    assert len(results) == 1


@pytest.mark.asyncio
async def test_memory_budget_check(mock_redis):
    """Memory usage stays within budget."""
    mock_redis.info = AsyncMock(return_value={"used_memory": 4_500_000})
    mem = ShortTermMemory(redis=mock_redis, ttl_seconds=86400, max_bytes=5_000_000)
    assert await mem.within_budget() is True

    mock_redis.info = AsyncMock(return_value={"used_memory": 5_500_000})
    assert await mem.within_budget() is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=. pytest tests/test_memory.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Implement Short-Term Memory**

```python
# apps/cell/cell/memory/short_term.py
"""Short-Term Memory — Redis with 24h TTL.

Stores recent observations. Auto-expires. Stays within budget.
Key pattern: cell:stm:{timestamp}:{event_type}
"""
import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass
class Observation:
    event_type: str
    data: dict[str, Any]
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class ShortTermMemory:
    """Redis-backed short-term memory with TTL and budget."""

    def __init__(self, redis: Any, ttl_seconds: int = 86400, max_bytes: int = 5_000_000) -> None:
        self._redis = redis
        self._ttl = ttl_seconds
        self._max_bytes = max_bytes

    async def store(self, obs: Observation) -> None:
        """Store an observation with TTL."""
        key = f"cell:stm:{int(time.time())}:{obs.event_type}"
        value = json.dumps(asdict(obs))
        await self._redis.set(key, value, ex=self._ttl)

    async def recent(self, event_type: str = "", limit: int = 10) -> list[dict[str, Any]]:
        """Retrieve recent observations, optionally filtered by type."""
        pattern = f"cell:stm:*:{event_type}" if event_type else "cell:stm:*"
        keys = await self._redis.keys(pattern)
        keys = sorted(keys, reverse=True)[:limit]
        results = []
        for key in keys:
            raw = await self._redis.get(key)
            if raw:
                data = raw if isinstance(raw, str) else raw.decode()
                results.append(json.loads(data))
        return results

    async def within_budget(self) -> bool:
        """Check if Redis memory usage is within CELL's budget."""
        info = await self._redis.info()
        used = info.get("used_memory", 0)
        return used < self._max_bytes
```

- [ ] **Step 4: Run tests — all should pass**

```bash
PYTHONPATH=. pytest tests/test_memory.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add apps/cell/cell/memory/ apps/cell/tests/test_memory.py
git commit -m "feat(cell): short-term memory — Redis observations with TTL"
```

---

## Task 10: Telegram Alerting

**Files:**

- Create: `apps/cell/cell/effectors/telegram.py`

- [ ] **Step 1: Write failing test (append to test_allowlist.py or create new)**

```python
# Append to apps/cell/tests/test_allowlist.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from cell.effectors.telegram import TelegramAlerter


@pytest.mark.asyncio
async def test_telegram_send_alert():
    """Alert sends Telegram message."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_client.post = AsyncMock(return_value=mock_response)

    alerter = TelegramAlerter(client=mock_client, bot_token="test", chat_id="123")
    result = await alerter.send("Test alert")
    assert result is True
    mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_telegram_send_failure():
    """Failed send returns False, doesn't raise."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=Exception("Network error"))

    alerter = TelegramAlerter(client=mock_client, bot_token="test", chat_id="123")
    result = await alerter.send("Test alert")
    assert result is False
```

- [ ] **Step 2: Run tests**

```bash
PYTHONPATH=. pytest tests/test_allowlist.py -v
```

Expected: 5 old pass, 2 new fail

- [ ] **Step 3: Implement Telegram Alerter**

```python
# apps/cell/cell/effectors/telegram.py
"""Telegram alerter — CELL's voice to the human operator.

Used for:
- RED health alerts (immediate)
- Budget exhaustion warnings
- Daily/weekly briefs (COMMUNICATE primitive)
"""
import logging
from typing import Any

logger = logging.getLogger("cell.telegram")


class TelegramAlerter:
    """Sends messages to operator via Telegram Bot API."""

    def __init__(self, client: Any, bot_token: str, chat_id: str) -> None:
        self._client = client
        self._token = bot_token
        self._chat_id = chat_id
        self._base_url = f"https://api.telegram.org/bot{bot_token}"

    async def send(self, message: str) -> bool:
        """Send a text message. Returns True on success."""
        try:
            response = await self._client.post(
                f"{self._base_url}/sendMessage",
                json={
                    "chat_id": self._chat_id,
                    "text": f"🧬 CELL: {message}",
                    "parse_mode": "Markdown",
                },
            )
            if response.status_code == 200:
                logger.info(f"Telegram alert sent: {message[:50]}...")
                return True
            logger.warning(f"Telegram API returned {response.status_code}")
            return False
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False
```

- [ ] **Step 4: Run tests — all should pass**

```bash
PYTHONPATH=. pytest tests/test_allowlist.py -v
```

Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add apps/cell/cell/effectors/telegram.py apps/cell/tests/test_allowlist.py
git commit -m "feat(cell): Telegram alerter — CELL speaks to operator"
```

---

## Task 11: Wire It All Together + Integration Test

**Files:**

- Modify: `apps/cell/cell/main.py` (connect real Redis, wire memory + alerting)
- Create: `apps/cell/tests/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
# apps/cell/tests/test_integration.py
"""Integration test — full pulse cycle with mocked externals."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from cell.core.dna import DNALoader
from cell.core.pulse import PulseEngine
from cell.core.safety import SafetyGate
from cell.fast.health_triage import HealthStatus
from cell.metabolism.tracker import MetabolismTracker
from cell.sensors.health_sensor import HealthSensor


@pytest.mark.asyncio
async def test_full_pulse_cycle_healthy():
    """Complete pulse: DNA OK → Safety OK → Health GREEN → no action."""
    dna_loader = DNALoader()
    dna_hash = dna_loader.compute_hash()

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    safety = SafetyGate(redis=mock_redis)

    mock_http = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "healthy"}
    mock_response.elapsed = MagicMock()
    mock_response.elapsed.total_seconds.return_value = 0.1
    mock_http.get = AsyncMock(return_value=mock_response)
    sensor = HealthSensor(client=mock_http, url="http://test/health")

    metabolism = MetabolismTracker(daily_limit=10.0)

    engine = PulseEngine(
        dna_loader=dna_loader,
        safety_gate=safety,
        health_sensor=sensor,
        metabolism=metabolism,
        dna_expected_hash=dna_hash,
    )

    result = await engine.single_pulse()
    assert result.halted is False
    assert result.skipped is False
    assert result.health_status == HealthStatus.GREEN
    assert result.action_taken is None


@pytest.mark.asyncio
async def test_full_pulse_cycle_unreachable():
    """Complete pulse: backend unreachable → RED status."""
    dna_loader = DNALoader()
    dna_hash = dna_loader.compute_hash()

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    safety = SafetyGate(redis=mock_redis)

    mock_http = AsyncMock()
    mock_http.get = AsyncMock(side_effect=Exception("Connection refused"))
    sensor = HealthSensor(client=mock_http, url="http://test/health")

    metabolism = MetabolismTracker(daily_limit=10.0)

    engine = PulseEngine(
        dna_loader=dna_loader,
        safety_gate=safety,
        health_sensor=sensor,
        metabolism=metabolism,
        dna_expected_hash=dna_hash,
    )

    result = await engine.single_pulse()
    assert result.halted is False
    assert result.health_status == HealthStatus.RED
```

- [ ] **Step 2: Run integration test**

```bash
PYTHONPATH=. pytest tests/test_integration.py -v
```

Expected: 2 passed

- [ ] **Step 3: Run ALL tests**

```bash
PYTHONPATH=. pytest tests/ -v
```

Expected: ~32 passed, 0 failed

- [ ] **Step 4: Commit**

```bash
git add apps/cell/tests/test_integration.py
git commit -m "test(cell): integration test — full pulse cycle verified"
```

---

## Task 12: Final Polish + LaunchAgent

**Files:**

- Modify: `apps/cell/cell/main.py` (remove mock Redis TODO)
- Create: LaunchAgent plist (documented, not installed yet)

- [ ] **Step 1: Run full test suite one final time**

```bash
cd apps/cell && source .venv/bin/activate
PYTHONPATH=. pytest tests/ -v --tb=short
```

Expected: All tests pass

- [ ] **Step 2: Create LaunchAgent plist (save to apps/cell/, don't install yet)**

```xml
<!-- apps/cell/com.cell.organism.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cell.organism</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/nuzantara/Desktop/nuzantara/apps/cell/.venv/bin/python</string>
        <string>-m</string>
        <string>cell.main</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/nuzantara/Desktop/nuzantara/apps/cell</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>/Users/nuzantara/Desktop/nuzantara/apps/cell</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/cell.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/cell.stderr.log</string>
</dict>
</plist>
```

- [ ] **Step 3: Final commit**

```bash
git add apps/cell/
git commit -m "feat(cell): CELL embryo complete — pulse loop, reflexes, safety, memory, metabolism

CELL v0.1.0 — the embryo. A single pulse loop that:
- Verifies DNA integrity every 60 seconds
- Checks safety gates (kill switch, maintenance mode)
- Reads Nuzantara backend health endpoint
- Classifies health (GREEN/YELLOW/RED)
- Tracks costs via metabolic system
- Stores observations in Redis short-term memory
- Alerts operator via Telegram on failures

What it does NOT do yet (grows later):
- Take healing actions (no strategies in procedural memory)
- Create sub-cells
- Evolve strategies
- Use SLOW thinking (LLM reasoning)
- Long-term Qdrant memory"
```

---

## Summary

| Task      | What It Builds                | Tests   | Files   |
| --------- | ----------------------------- | ------- | ------- |
| 1         | Project scaffold + DNA        | 4       | 8       |
| 2         | Health Triage + Cost Guard    | 8       | 3       |
| 3         | Log Anomaly + Mutation Filter | 10      | 3       |
| 4         | Safety Gate (kill switch)     | 4       | 2       |
| 5         | Metabolism Tracker            | 7       | 2       |
| 6         | Health Sensor                 | 3       | 2       |
| 7         | Action Allowlist              | 5       | 2       |
| 8         | Pulse Engine + main.py        | 3       | 3       |
| 9         | Short-Term Memory (Redis)     | 3       | 2       |
| 10        | Telegram Alerter              | 2       | 1       |
| 11        | Integration Test              | 2       | 1       |
| 12        | Polish + LaunchAgent          | 0       | 1       |
| **Total** | **CELL Embryo**               | **~51** | **~30** |

After Task 12, CELL is alive. It observes. It remembers. It can't act yet — that grows with experience.
