# cell-core Shared Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the biological lifecycle engine from `apps/cell/` into `packages/cell-core/` — a shared Python package that any Nuzantara agent imports to become a living cell.

**Architecture:** Protocol + Composition. PulseLoop is a concrete orchestrator that takes Sensor/Thinker/Actor/MemoryStore protocol implementations via constructor injection. SQLite is the default memory backend (zero deps). PostgreSQL is optional. All protocols are async.

**Tech Stack:** Python 3.11+ stdlib only (`sqlite3`, `asyncio`, `dataclasses`, `typing`, `json`, `math`, `pathlib`, `hashlib`). No external dependencies required.

**Spec:** `docs/superpowers/specs/2026-04-10-cell-core-shared-package-design.md`

---

## File Map

### New files (packages/cell-core/)

| File | Responsibility |
|------|---------------|
| `packages/cell-core/pyproject.toml` | Package metadata, zero deps |
| `packages/cell-core/cell_core/__init__.py` | Public API exports |
| `packages/cell-core/cell_core/types.py` | All dataclasses: Phase, CellConfig, SensorReading, Proposal, Episode, etc. |
| `packages/cell-core/cell_core/protocols.py` | Protocol definitions: Sensor, Thinker, Actor, STMStore, LTMStore, EpisodicStore |
| `packages/cell-core/cell_core/lifecycle.py` | Maturation phases + confidence gates |
| `packages/cell-core/cell_core/safety.py` | SafetyGate (kill switch) + DNALoader + DNAInterpreter |
| `packages/cell-core/cell_core/homeostasis.py` | HomeostaticController + TrendDetector |
| `packages/cell-core/cell_core/identity.py` | SelfModel + SelfModelManager (JSON persistence) |
| `packages/cell-core/cell_core/memory_sqlite.py` | SqliteSTM, SqliteLTM, SqliteEpisodic, SqliteMemoryStack |
| `packages/cell-core/cell_core/reasoner.py` | TierConfig + ReasonerFramework (subprocess escalation) |
| `packages/cell-core/cell_core/pulse.py` | PulseLoop — the lifecycle runner |

### Test files (packages/cell-core/tests/)

| File | Tests |
|------|-------|
| `tests/conftest.py` | Fake protocols, tmp paths, shared fixtures |
| `tests/test_types.py` | Dataclass creation, validation, defaults |
| `tests/test_protocols.py` | runtime_checkable compliance |
| `tests/test_lifecycle.py` | Phase transitions, confidence gates, tick |
| `tests/test_safety.py` | Kill switch, DNA load/verify/validate |
| `tests/test_homeostasis.py` | Stress/energy/arousal, circadian, trend detection |
| `tests/test_identity.py` | SelfModel load/save, record_pulse, sensor reliability |
| `tests/test_memory_sqlite.py` | All 3 SQLite stores: CRUD, TTL, ACT-R, FTS5, forget |
| `tests/test_reasoner.py` | Tier escalation, timeout, allowlist |
| `tests/test_pulse.py` | Full lifecycle: sense→think→act→reflect→dream→mature |

---

### Task 1: Package scaffold + types.py

**Files:**
- Create: `packages/cell-core/pyproject.toml`
- Create: `packages/cell-core/cell_core/__init__.py`
- Create: `packages/cell-core/cell_core/types.py`
- Create: `packages/cell-core/tests/__init__.py`
- Create: `packages/cell-core/tests/test_types.py`

- [ ] **Step 1: Create pyproject.toml**

```bash
mkdir -p packages/cell-core/cell_core packages/cell-core/tests
```

Create `packages/cell-core/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[project]
name = "cell-core"
version = "0.1.0"
description = "Biological lifecycle engine for Nuzantara agents"
requires-python = ">=3.11"
# Zero external dependencies — stdlib only
dependencies = []

[project.optional-dependencies]
postgres = ["asyncpg>=0.29"]
redis = ["redis>=5.0"]
dev = ["pytest>=8.0", "pytest-asyncio>=0.24"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create empty __init__ files**

Create `packages/cell-core/cell_core/__init__.py`:

```python
"""cell-core — Biological lifecycle engine for Nuzantara agents."""
```

Create `packages/cell-core/tests/__init__.py`:

```python
```

- [ ] **Step 3: Write failing test for types**

Create `packages/cell-core/tests/test_types.py`:

```python
"""Tests for cell_core.types — shared vocabulary."""
import time
from datetime import datetime, timezone

import pytest


def test_phase_enum_values():
    from cell_core.types import Phase
    assert Phase.EMBRIONE.value == "embrione"
    assert Phase.NEONATO.value == "neonato"
    assert Phase.GIOVANE.value == "giovane"
    assert Phase.ADULTO.value == "adulto"
    assert Phase.ANZIANO.value == "anziano"


def test_phase_is_str_enum():
    from cell_core.types import Phase
    assert isinstance(Phase.EMBRIONE, str)
    assert f"phase={Phase.ADULTO}" == "phase=adulto"


def test_cell_config_defaults():
    from cell_core.types import CellConfig
    cfg = CellConfig(name="test", dna_path="dna.json")
    assert cfg.pulse_interval_seconds == 60
    assert cfg.memory_backend == "sqlite"
    assert cfg.db_path == "cell.db"
    assert cfg.sleep_hours == (2, 6)
    assert cfg.birth_date is None


def test_cell_config_custom():
    from cell_core.types import CellConfig
    bd = datetime(2026, 3, 26, tzinfo=timezone.utc)
    cfg = CellConfig(
        name="mata-garuda", dna_path="mg.json",
        pulse_interval_seconds=3600, birth_date=bd,
        memory_backend="postgres", db_path="mg.db",
        sleep_hours=(1, 5),
    )
    assert cfg.name == "mata-garuda"
    assert cfg.birth_date == bd
    assert cfg.pulse_interval_seconds == 3600


def test_sensor_reading_defaults():
    from cell_core.types import SensorReading
    r = SensorReading(sensor_name="health", status="green")
    assert r.sensor_name == "health"
    assert r.status == "green"
    assert r.value is None
    assert isinstance(r.timestamp, datetime)
    assert r.metadata == {}


def test_sensor_reading_with_value():
    from cell_core.types import SensorReading
    r = SensorReading(sensor_name="db", status="yellow", value={"latency_ms": 150})
    assert r.value == {"latency_ms": 150}


def test_proposal_defaults():
    from cell_core.types import Proposal
    p = Proposal(action="restart_service", reason="high latency", confidence=0.9, tier_used=0)
    assert p.cost_usd == 0.0


def test_episode_defaults():
    from cell_core.types import Episode
    e = Episode(
        situation={"status": "red"}, emotion="stressed",
        action_taken="restart", outcome="success", lesson="restart helps",
    )
    assert e.id == 0
    assert e.recall_count == 0
    assert e.activation == 0.0
    assert e.timestamp == 0.0


def test_episode_compute_activation():
    from cell_core.types import Episode
    now = time.time()
    e = Episode(
        situation={}, emotion="calm", action_taken="none",
        outcome="success", lesson="ok", timestamp=now, recall_count=5,
    )
    act = e.compute_activation()
    assert act > 0.5  # base + recency + frequency should be substantial
    # More recalls = higher activation
    e2 = Episode(
        situation={}, emotion="calm", action_taken="none",
        outcome="success", lesson="ok", timestamp=now, recall_count=0,
    )
    assert e.compute_activation() > e2.compute_activation()


def test_episode_old_has_lower_activation():
    from cell_core.types import Episode
    old = Episode(
        situation={}, emotion="calm", action_taken="none",
        outcome="success", lesson="ok",
        timestamp=time.time() - 86400 * 7,  # 7 days ago
    )
    recent = Episode(
        situation={}, emotion="calm", action_taken="none",
        outcome="success", lesson="ok",
        timestamp=time.time(),
    )
    assert recent.compute_activation() > old.compute_activation()


def test_learned_rule():
    from cell_core.types import LearnedRule
    r = LearnedRule(rule_text="When latency > 500ms, restart", support_count=3)
    assert r.created_at == ""


def test_homeostatic_state_defaults():
    from cell_core.types import HomeostaticState
    s = HomeostaticState()
    assert s.stress_level == 0.0
    assert s.energy_level == 1.0
    assert s.arousal == 0.5
    assert s.circadian_phase == "awake"


def test_homeostatic_state_clamp():
    from cell_core.types import HomeostaticState
    s = HomeostaticState(stress_level=1.5, energy_level=-0.5, arousal=2.0)
    assert 0.0 <= s.stress_level <= 1.0
    assert 0.0 <= s.energy_level <= 1.0
    assert 0.0 <= s.arousal <= 1.0


def test_pulse_result_defaults():
    from cell_core.types import PulseResult
    now = datetime.now(timezone.utc)
    r = PulseResult(timestamp=now, pulse_number=1)
    assert r.halted is False
    assert r.action_taken is None


def test_safety_check_result():
    from cell_core.types import SafetyCheckResult
    ok = SafetyCheckResult(can_proceed=True)
    assert ok.reason == ""
    blocked = SafetyCheckResult(can_proceed=False, reason="disabled", detail="file exists")
    assert not blocked.can_proceed


def test_dna_rule():
    from cell_core.types import DNARule
    r = DNARule(text="Never modify DNA", priority=1)
    assert r.text == "Never modify DNA"


def test_dna_config():
    from cell_core.types import DNAConfig, DNARule
    cfg = DNAConfig(
        rules=[DNARule(text="Rule 1", priority=1)],
        constraints={"max_daily_budget_usd": 10.0},
    )
    assert len(cfg.rules) == 1
    assert cfg.constraints["max_daily_budget_usd"] == 10.0
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd packages/cell-core && pip install -e ".[dev]" && pytest tests/test_types.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'cell_core.types'`

- [ ] **Step 5: Implement types.py**

Create `packages/cell-core/cell_core/types.py`:

```python
"""Shared vocabulary — all dataclasses that every cell uses."""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


class Phase(str, Enum):
    """Lifecycle phases — from embryo to elder."""
    EMBRIONE = "embrione"   # day 0-3: observe only
    NEONATO = "neonato"     # day 4-14: act with high confidence
    GIOVANE = "giovane"     # day 15-30: autonomous + dreams
    ADULTO = "adulto"       # day 31-179: full autonomy
    ANZIANO = "anziano"     # day 180+: stability priority


@dataclass
class CellConfig:
    """Configuration for one organ/agent."""
    name: str
    dna_path: str
    pulse_interval_seconds: int = 60
    birth_date: datetime | None = None
    memory_backend: str = "sqlite"
    db_path: str = "cell.db"
    sleep_hours: tuple[int, int] = (2, 6)


@dataclass
class SensorReading:
    """One sensor's perception of the environment."""
    sensor_name: str
    status: Literal["green", "yellow", "red"]
    value: Any = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Proposal:
    """A reasoner's proposed action."""
    action: str
    reason: str
    confidence: float
    tier_used: int
    cost_usd: float = 0.0


# ACT-R activation parameters
_RECENCY_WEIGHT = 1.0
_FREQUENCY_WEIGHT = 0.5
_BASE_ACTIVATION = 0.5


@dataclass
class Episode:
    """A single episodic memory — a moment the cell experienced."""
    situation: dict[str, Any]
    emotion: str           # calm, alert, stressed, panic
    action_taken: str
    outcome: str           # success, partial, failure
    lesson: str
    id: int = 0
    timestamp: float = 0.0
    recall_count: int = 0
    activation: float = 0.0

    def compute_activation(self) -> float:
        """ACT-R activation: base + recency + frequency."""
        ts = self.timestamp if self.timestamp > 0 else time.time()
        age_seconds = max(time.time() - ts, 1.0)
        age_days = age_seconds / 86400.0
        recency = _RECENCY_WEIGHT * (1.0 / (1.0 + math.log1p(age_days)))
        frequency = _FREQUENCY_WEIGHT * math.log1p(self.recall_count)
        return _BASE_ACTIVATION + recency + frequency


@dataclass
class LearnedRule:
    """A condensed rule extracted from episodic memory."""
    rule_text: str
    support_count: int
    created_at: str = ""


@dataclass
class HomeostaticState:
    """The organism's internal physiological state."""
    stress_level: float = 0.0
    energy_level: float = 1.0
    arousal: float = 0.5
    comfort_zone: tuple[float, float] = (50.0, 200.0)
    setpoint_rt_ms: float = 100.0
    circadian_phase: str = "awake"

    def __post_init__(self) -> None:
        self.stress_level = _clamp(self.stress_level)
        self.energy_level = _clamp(self.energy_level)
        self.arousal = _clamp(self.arousal)


@dataclass
class PulseResult:
    """Result of one lifecycle tick."""
    timestamp: datetime
    pulse_number: int
    halted: bool = False
    halt_reason: str = ""
    skipped: bool = False
    skip_reason: str = ""
    health_status: str | None = None
    action_taken: str | None = None
    action_reason: str | None = None
    thought_tier: int | None = None
    error: str | None = None


@dataclass
class SafetyCheckResult:
    """Result of a safety gate check."""
    can_proceed: bool
    reason: str = ""
    detail: str = ""


@dataclass
class DNARule:
    """One immutable rule in the organism's DNA."""
    text: str
    priority: int


@dataclass
class DNAConfig:
    """Complete DNA configuration loaded from JSON."""
    rules: list[DNARule]
    constraints: dict[str, Any]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd packages/cell-core && pytest tests/test_types.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
cd ~/Desktop/nuzantara
git add packages/cell-core/
git commit -m "feat(cell-core): scaffold package + types.py with full test coverage"
```

---

### Task 2: protocols.py

**Files:**
- Create: `packages/cell-core/cell_core/protocols.py`
- Create: `packages/cell-core/tests/test_protocols.py`

- [ ] **Step 1: Write failing test**

Create `packages/cell-core/tests/test_protocols.py`:

```python
"""Tests for cell_core.protocols — runtime_checkable Protocol compliance."""
import pytest


class TestSensorProtocol:
    def test_valid_sensor_is_instance(self):
        from cell_core.protocols import Sensor
        from cell_core.types import SensorReading

        class MySensor:
            name = "test"
            async def read(self, **context):
                return SensorReading(sensor_name="test", status="green")

        assert isinstance(MySensor(), Sensor)

    def test_missing_name_is_not_sensor(self):
        from cell_core.protocols import Sensor

        class BadSensor:
            async def read(self, **context):
                return None

        assert not isinstance(BadSensor(), Sensor)


class TestThinkerProtocol:
    def test_valid_thinker(self):
        from cell_core.protocols import Thinker
        from cell_core.types import Proposal, HomeostaticState, SensorReading

        class MyThinker:
            async def think(self, readings, state, memory_context):
                return Proposal(action="none", reason="ok", confidence=1.0, tier_used=-1)

        assert isinstance(MyThinker(), Thinker)


class TestActorProtocol:
    def test_valid_actor(self):
        from cell_core.protocols import Actor
        from cell_core.types import Proposal

        class MyActor:
            async def act(self, proposal):
                return "done"
            def can_execute(self, action_name):
                return True

        assert isinstance(MyActor(), Actor)

    def test_missing_can_execute_is_not_actor(self):
        from cell_core.protocols import Actor

        class BadActor:
            async def act(self, proposal):
                return "done"

        assert not isinstance(BadActor(), Actor)


class TestSTMStoreProtocol:
    def test_valid_stm(self):
        from cell_core.protocols import STMStore

        class MySTM:
            async def store(self, event_type, data):
                pass
            async def recent(self, event_type, limit):
                return []

        assert isinstance(MySTM(), STMStore)


class TestLTMStoreProtocol:
    def test_valid_ltm(self):
        from cell_core.protocols import LTMStore

        class MyLTM:
            async def store_rule(self, rule):
                pass
            async def load_rules(self, limit):
                return []
            async def condense(self, episodes):
                return []

        assert isinstance(MyLTM(), LTMStore)


class TestEpisodicStoreProtocol:
    def test_valid_episodic(self):
        from cell_core.protocols import EpisodicStore

        class MyEpisodic:
            async def store(self, episode):
                return 1
            async def recall(self, situation, limit):
                return []
            async def recall_recent(self, hours, limit):
                return []
            async def forget_weak(self, keep):
                return 0

        assert isinstance(MyEpisodic(), EpisodicStore)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/cell-core && pytest tests/test_protocols.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'cell_core.protocols'`

- [ ] **Step 3: Implement protocols.py**

Create `packages/cell-core/cell_core/protocols.py`:

```python
"""Protocol definitions — the contracts every organ must implement."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from cell_core.types import (
    Episode,
    HomeostaticState,
    LearnedRule,
    Proposal,
    SensorReading,
)


@runtime_checkable
class Sensor(Protocol):
    """Perceives one aspect of the environment."""
    name: str

    async def read(self, **context: Any) -> SensorReading: ...


@runtime_checkable
class Thinker(Protocol):
    """Reasons about sensor readings and proposes actions."""

    async def think(
        self,
        readings: list[SensorReading],
        state: HomeostaticState,
        memory_context: dict[str, Any],
    ) -> Proposal: ...


@runtime_checkable
class Actor(Protocol):
    """Executes a proposed action."""

    async def act(self, proposal: Proposal) -> str: ...
    def can_execute(self, action_name: str) -> bool: ...


@runtime_checkable
class STMStore(Protocol):
    """Short-term memory — volatile, TTL-based."""

    async def store(self, event_type: str, data: dict[str, Any]) -> None: ...
    async def recent(self, event_type: str, limit: int) -> list[dict[str, Any]]: ...


@runtime_checkable
class LTMStore(Protocol):
    """Long-term memory — persistent learned rules."""

    async def store_rule(self, rule: LearnedRule) -> None: ...
    async def load_rules(self, limit: int) -> list[LearnedRule]: ...
    async def condense(self, episodes: list[Episode]) -> list[LearnedRule]: ...


@runtime_checkable
class EpisodicStore(Protocol):
    """Episodic memory — significant moments with ACT-R activation."""

    async def store(self, episode: Episode) -> int: ...
    async def recall(self, situation: dict[str, Any], limit: int) -> list[Episode]: ...
    async def recall_recent(self, hours: int, limit: int) -> list[Episode]: ...
    async def forget_weak(self, keep: int) -> int: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/cell-core && pytest tests/test_protocols.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add packages/cell-core/cell_core/protocols.py packages/cell-core/tests/test_protocols.py
git commit -m "feat(cell-core): protocol definitions for Sensor, Thinker, Actor, Memory stores"
```

---

### Task 3: lifecycle.py

**Files:**
- Create: `packages/cell-core/cell_core/lifecycle.py`
- Create: `packages/cell-core/tests/test_lifecycle.py`

**Reference:** Extract from `apps/cell/cell/lifecycle/maturation.py` (lines 1-84)

- [ ] **Step 1: Write failing test**

Create `packages/cell-core/tests/test_lifecycle.py`:

```python
"""Tests for cell_core.lifecycle — maturation phases and confidence gates."""
from datetime import datetime, timedelta, timezone

import pytest


class TestMaturation:
    def _make(self, age_days: int):
        from cell_core.lifecycle import Maturation
        birth = datetime.now(timezone.utc) - timedelta(days=age_days)
        return Maturation(birth_date=birth)

    def test_embrione_phase(self):
        from cell_core.types import Phase
        m = self._make(0)
        assert m.phase == Phase.EMBRIONE
        m2 = self._make(3)
        assert m2.phase == Phase.EMBRIONE

    def test_neonato_phase(self):
        from cell_core.types import Phase
        m = self._make(4)
        assert m.phase == Phase.NEONATO
        m2 = self._make(14)
        assert m2.phase == Phase.NEONATO

    def test_giovane_phase(self):
        from cell_core.types import Phase
        m = self._make(15)
        assert m.phase == Phase.GIOVANE
        m2 = self._make(30)
        assert m2.phase == Phase.GIOVANE

    def test_adulto_phase(self):
        from cell_core.types import Phase
        m = self._make(31)
        assert m.phase == Phase.ADULTO
        m2 = self._make(179)
        assert m2.phase == Phase.ADULTO

    def test_anziano_phase(self):
        from cell_core.types import Phase
        m = self._make(180)
        assert m.phase == Phase.ANZIANO
        m2 = self._make(365)
        assert m2.phase == Phase.ANZIANO

    def test_can_act(self):
        assert not self._make(0).can_act()   # embrione
        assert self._make(5).can_act()       # neonato
        assert self._make(20).can_act()      # giovane
        assert self._make(50).can_act()      # adulto

    def test_can_dream(self):
        assert not self._make(0).can_dream()   # embrione
        assert not self._make(5).can_dream()   # neonato
        assert self._make(20).can_dream()      # giovane
        assert self._make(50).can_dream()      # adulto
        assert self._make(200).can_dream()     # anziano

    def test_can_reason_deep(self):
        assert not self._make(0).can_reason_deep()
        assert not self._make(5).can_reason_deep()
        assert self._make(20).can_reason_deep()

    def test_confidence_thresholds(self):
        assert self._make(0).action_confidence_threshold() == 1.1    # embrione
        assert self._make(5).action_confidence_threshold() == 0.8    # neonato
        assert self._make(20).action_confidence_threshold() == 0.5   # giovane
        assert self._make(50).action_confidence_threshold() == 0.0   # adulto
        assert self._make(200).action_confidence_threshold() == 0.0  # anziano

    def test_tick_increments_total_pulses(self):
        m = self._make(10)
        assert m.total_pulses == 0
        m.tick(1)
        assert m.total_pulses == 1
        m.tick(2)
        assert m.total_pulses == 2

    def test_age_days_property(self):
        m = self._make(42)
        assert m.age_days == 42

    def test_to_prompt_context(self):
        m = self._make(50)
        ctx = m.to_prompt_context()
        assert "adulto" in ctx.lower()
        assert "50" in ctx
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/cell-core && pytest tests/test_lifecycle.py -v`
Expected: FAIL

- [ ] **Step 3: Implement lifecycle.py**

Create `packages/cell-core/cell_core/lifecycle.py`:

```python
"""Maturation — lifecycle phase tracker.

Phases gate capabilities: embrione observes only, neonato acts cautiously,
giovane acts autonomously + dreams, adulto has full autonomy, anziano stabilizes.

Extracted from apps/cell/cell/lifecycle/maturation.py.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from cell_core.types import Phase

logger = logging.getLogger("cell_core.lifecycle")

_THRESHOLDS = {
    Phase.EMBRIONE: 1.1,
    Phase.NEONATO: 0.8,
    Phase.GIOVANE: 0.5,
    Phase.ADULTO: 0.0,
    Phase.ANZIANO: 0.0,
}

_DESCRIPTIONS = {
    Phase.EMBRIONE: "Embrione (day 0-3): observe and log only, no autonomous actions.",
    Phase.NEONATO: "Neonato (day 4-14): act only with confidence >= 0.8, building episodic memory.",
    Phase.GIOVANE: "Giovane (day 15-30): autonomous actions, dreams active, confidence >= 0.5.",
    Phase.ADULTO: "Adulto (day 31-179): full autonomy, all capabilities unlocked.",
    Phase.ANZIANO: "Anziano (day 180+): stability priority, reduced mutation rate.",
}


class Maturation:
    """Lifecycle phase based on age in days."""

    def __init__(self, birth_date: datetime) -> None:
        self.birth_date = birth_date
        self.total_pulses: int = 0

    @property
    def age_days(self) -> int:
        now = datetime.now(timezone.utc)
        birth = self.birth_date
        if birth.tzinfo is None:
            birth = birth.replace(tzinfo=timezone.utc)
        return (now - birth).days

    @property
    def phase(self) -> Phase:
        days = self.age_days
        if days >= 180:
            return Phase.ANZIANO
        if days >= 31:
            return Phase.ADULTO
        if days >= 15:
            return Phase.GIOVANE
        if days >= 4:
            return Phase.NEONATO
        return Phase.EMBRIONE

    def can_act(self) -> bool:
        return self.phase != Phase.EMBRIONE

    def can_dream(self) -> bool:
        return self.phase in (Phase.GIOVANE, Phase.ADULTO, Phase.ANZIANO)

    def can_reason_deep(self) -> bool:
        return self.phase in (Phase.GIOVANE, Phase.ADULTO, Phase.ANZIANO)

    def action_confidence_threshold(self) -> float:
        return _THRESHOLDS[self.phase]

    def tick(self, pulse_count: int) -> None:
        self.total_pulses = pulse_count

    def to_prompt_context(self) -> str:
        return (
            f"LIFECYCLE: phase={self.phase.value} age={self.age_days}d — "
            f"{_DESCRIPTIONS[self.phase]}"
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/cell-core && pytest tests/test_lifecycle.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add packages/cell-core/cell_core/lifecycle.py packages/cell-core/tests/test_lifecycle.py
git commit -m "feat(cell-core): lifecycle maturation with 5 phases and confidence gates"
```

---

### Task 4: safety.py

**Files:**
- Create: `packages/cell-core/cell_core/safety.py`
- Create: `packages/cell-core/tests/test_safety.py`

**Reference:** Extract from `apps/cell/cell/core/safety.py` + `apps/cell/cell/core/dna.py`

- [ ] **Step 1: Write failing test**

Create `packages/cell-core/tests/test_safety.py`:

```python
"""Tests for cell_core.safety — kill switches, DNA loader, DNA interpreter."""
import json
import tempfile
from pathlib import Path

import pytest

from cell_core.types import DNAConfig, DNARule, Proposal, SafetyCheckResult


class TestSafetyGate:
    @pytest.mark.asyncio
    async def test_proceeds_when_no_disable_file(self, tmp_path):
        from cell_core.safety import SafetyGate
        gate = SafetyGate(disable_file=str(tmp_path / "nonexistent"))
        result = await gate.check()
        assert result.can_proceed is True

    @pytest.mark.asyncio
    async def test_halts_when_disable_file_exists(self, tmp_path):
        from cell_core.safety import SafetyGate
        disable = tmp_path / "cell.disabled"
        disable.write_text("disabled by operator")
        gate = SafetyGate(disable_file=str(disable))
        result = await gate.check()
        assert result.can_proceed is False
        assert "disabled" in result.reason


class TestDNALoader:
    def test_load_valid_dna(self, tmp_path):
        from cell_core.safety import DNALoader
        dna_file = tmp_path / "dna.json"
        dna_file.write_text(json.dumps({
            "rules": [
                {"text": "Never modify DNA", "priority": 1},
                {"text": "If broken, repair it", "priority": 2},
            ],
            "constraints": {"max_daily_budget_usd": 10.0},
        }))
        loader = DNALoader(str(dna_file))
        config = loader.load()
        assert len(config.rules) == 2
        assert config.rules[0].text == "Never modify DNA"
        assert config.constraints["max_daily_budget_usd"] == 10.0

    def test_verify_hash_matches(self, tmp_path):
        from cell_core.safety import DNALoader
        dna_file = tmp_path / "dna.json"
        dna_file.write_text('{"rules": [], "constraints": {}}')
        loader = DNALoader(str(dna_file))
        h = loader.compute_hash()
        assert loader.verify_integrity(h) is True

    def test_verify_hash_mismatch(self, tmp_path):
        from cell_core.safety import DNALoader
        dna_file = tmp_path / "dna.json"
        dna_file.write_text('{"rules": [], "constraints": {}}')
        loader = DNALoader(str(dna_file))
        assert loader.verify_integrity("badhash") is False

    def test_verify_or_raise(self, tmp_path):
        from cell_core.safety import DNALoader, DNAIntegrityError
        dna_file = tmp_path / "dna.json"
        dna_file.write_text('{"rules": [], "constraints": {}}')
        loader = DNALoader(str(dna_file))
        with pytest.raises(DNAIntegrityError):
            loader.verify_or_raise("badhash")

    def test_load_missing_file_raises(self):
        from cell_core.safety import DNALoader
        loader = DNALoader("/nonexistent/dna.json")
        with pytest.raises(FileNotFoundError):
            loader.load()


class TestDNAInterpreter:
    def _make_dna(self):
        return DNAConfig(
            rules=[DNARule(text="Never modify DNA", priority=1)],
            constraints={
                "max_daily_budget_usd": 10.0,
                "max_cost_per_investigation_usd": 0.5,
            },
        )

    def test_approve_within_budget(self):
        from cell_core.safety import DNAInterpreter
        interp = DNAInterpreter(self._make_dna())
        proposal = Proposal(action="restart_service", reason="test", confidence=0.9, tier_used=0, cost_usd=0.1)
        result = interp.validate(proposal, budget_spent=5.0)
        assert result.can_proceed is True

    def test_reject_over_budget(self):
        from cell_core.safety import DNAInterpreter
        interp = DNAInterpreter(self._make_dna())
        proposal = Proposal(action="restart_service", reason="test", confidence=0.9, tier_used=0, cost_usd=0.1)
        result = interp.validate(proposal, budget_spent=9.5)
        assert result.can_proceed is False
        assert "budget" in result.reason.lower()

    def test_reject_expensive_investigation(self):
        from cell_core.safety import DNAInterpreter
        interp = DNAInterpreter(self._make_dna())
        proposal = Proposal(action="investigate", reason="test", confidence=0.9, tier_used=1, cost_usd=0.8)
        result = interp.validate(proposal, budget_spent=0.0)
        assert result.can_proceed is False

    def test_approve_no_action(self):
        from cell_core.safety import DNAInterpreter
        interp = DNAInterpreter(self._make_dna())
        proposal = Proposal(action="none", reason="stable", confidence=1.0, tier_used=-1)
        result = interp.validate(proposal, budget_spent=0.0)
        assert result.can_proceed is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/cell-core && pytest tests/test_safety.py -v`
Expected: FAIL

- [ ] **Step 3: Implement safety.py**

Create `packages/cell-core/cell_core/safety.py`:

```python
"""Safety mechanisms — kill switches + DNA integrity + budget validation.

Kill switches cannot be overridden by the organism:
1. File on disk (works without any external service)
2. Optional Redis keys (for remote disable)
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from cell_core.types import DNAConfig, DNARule, Proposal, SafetyCheckResult

logger = logging.getLogger("cell_core.safety")


class DNAIntegrityError(Exception):
    """Raised when DNA file has been tampered with."""


class SafetyGate:
    """Kill switch + maintenance mode. Organ-agnostic."""

    def __init__(
        self,
        disable_file: str = "/tmp/cell.disabled",
        redis: Any = None,
        cell_name: str = "cell",
    ) -> None:
        self._disable_file = Path(disable_file)
        self._redis = redis
        self._cell_name = cell_name

    async def check(self) -> SafetyCheckResult:
        # File kill switch — always works, even without Redis
        if self._disable_file.exists():
            return SafetyCheckResult(
                can_proceed=False,
                reason="disabled",
                detail=f"Disable file exists: {self._disable_file}",
            )

        # Redis kill switches — fail-open if Redis unavailable
        if self._redis is not None:
            try:
                disabled = await self._redis.get(f"cell:{self._cell_name}:disabled")
                if disabled is not None:
                    return SafetyCheckResult(
                        can_proceed=False,
                        reason="disabled",
                        detail="Redis kill switch active",
                    )
                maintenance = await self._redis.get(f"cell:{self._cell_name}:maintenance")
                if maintenance is not None:
                    return SafetyCheckResult(
                        can_proceed=False,
                        reason="maintenance",
                        detail="Maintenance mode via Redis",
                    )
            except Exception as e:
                # Fail-open: if Redis is down, continue
                logger.debug(f"Redis unavailable for safety check: {e}")

        return SafetyCheckResult(can_proceed=True)


class DNALoader:
    """Loads and verifies the immutable DNA file."""

    def __init__(self, path: str) -> None:
        self._path = Path(path)

    def raw_bytes(self) -> bytes:
        return self._path.read_bytes()

    def load(self) -> DNAConfig:
        data = json.loads(self.raw_bytes())
        rules = [
            DNARule(text=r["text"], priority=r.get("priority", i + 1))
            for i, r in enumerate(data.get("rules", []))
        ]
        return DNAConfig(
            rules=rules,
            constraints=data.get("constraints", {}),
        )

    def compute_hash(self) -> str:
        return hashlib.sha256(self.raw_bytes()).hexdigest()

    def verify_integrity(self, expected_hash: str) -> bool:
        return self.compute_hash() == expected_hash

    def verify_or_raise(self, expected_hash: str) -> DNAConfig:
        if not self.verify_integrity(expected_hash):
            raise DNAIntegrityError(
                f"DNA tampered! Expected {expected_hash[:16]}..., "
                f"got {self.compute_hash()[:16]}..."
            )
        return self.load()


class DNAInterpreter:
    """Validates proposed actions against DNA rules + constraints."""

    def __init__(self, dna: DNAConfig) -> None:
        self._dna = dna

    def validate(self, proposal: Proposal, budget_spent: float) -> SafetyCheckResult:
        # "none" actions always pass
        if proposal.action == "none":
            return SafetyCheckResult(can_proceed=True)

        max_budget = self._dna.constraints.get("max_daily_budget_usd", 10.0)
        max_investigation = self._dna.constraints.get("max_cost_per_investigation_usd", 0.5)

        # Check daily budget
        if budget_spent + proposal.cost_usd > max_budget * 0.9:
            return SafetyCheckResult(
                can_proceed=False,
                reason="Budget exceeded",
                detail=f"Spent {budget_spent:.2f} + cost {proposal.cost_usd:.2f} > {max_budget * 0.9:.2f} (90% of {max_budget})",
            )

        # Check per-investigation cost
        if proposal.cost_usd > max_investigation:
            return SafetyCheckResult(
                can_proceed=False,
                reason="Investigation cost too high",
                detail=f"Cost {proposal.cost_usd:.2f} > max {max_investigation:.2f}",
            )

        return SafetyCheckResult(can_proceed=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/cell-core && pytest tests/test_safety.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add packages/cell-core/cell_core/safety.py packages/cell-core/tests/test_safety.py
git commit -m "feat(cell-core): safety gates, DNA loader with SHA-256, DNA interpreter"
```

---

### Task 5: homeostasis.py

**Files:**
- Create: `packages/cell-core/cell_core/homeostasis.py`
- Create: `packages/cell-core/tests/test_homeostasis.py`

**Reference:** Extract from `apps/cell/cell/fast/homeostatic_controller.py` + `apps/cell/cell/fast/trend_detector.py`

- [ ] **Step 1: Write failing test**

Create `packages/cell-core/tests/test_homeostasis.py`:

```python
"""Tests for cell_core.homeostasis — homeostatic controller + trend detector."""
import pytest

from cell_core.types import HomeostaticState


class TestHomeostaticController:
    def _make(self, **kwargs):
        from cell_core.homeostasis import HomeostaticController
        return HomeostaticController(**kwargs)

    def test_initial_state(self):
        hc = self._make()
        assert hc.state.stress_level == 0.0
        assert hc.state.energy_level == 1.0
        assert hc.state.arousal == 0.5
        assert hc.state.circadian_phase == "awake"

    def test_green_pulse_reduces_stress(self):
        hc = self._make()
        hc.state.stress_level = 0.5
        hc.update(response_time_ms=100, health_status="green", hour_utc=12)
        assert hc.state.stress_level < 0.5

    def test_red_pulse_increases_stress(self):
        hc = self._make()
        hc.update(response_time_ms=100, health_status="red", hour_utc=12)
        assert hc.state.stress_level > 0.0

    def test_high_rt_increases_stress(self):
        hc = self._make()
        # First establish a low setpoint
        for _ in range(10):
            hc.update(response_time_ms=100, health_status="green", hour_utc=12)
        stress_before = hc.state.stress_level
        hc.update(response_time_ms=5000, health_status="green", hour_utc=12)
        assert hc.state.stress_level > stress_before

    def test_green_pulse_recovers_energy(self):
        hc = self._make()
        hc.state.energy_level = 0.5
        hc.update(response_time_ms=100, health_status="green", hour_utc=12)
        assert hc.state.energy_level > 0.5

    def test_circadian_asleep(self):
        hc = self._make(sleep_hours=(2, 6))
        hc.update(response_time_ms=100, health_status="green", hour_utc=3)
        assert hc.state.circadian_phase == "asleep"

    def test_circadian_awake(self):
        hc = self._make(sleep_hours=(2, 6))
        hc.update(response_time_ms=100, health_status="green", hour_utc=12)
        assert hc.state.circadian_phase == "awake"

    def test_circadian_drowsy(self):
        hc = self._make(sleep_hours=(2, 6))
        hc.update(response_time_ms=100, health_status="green", hour_utc=1)
        assert hc.state.circadian_phase == "drowsy"

    def test_is_sleeping(self):
        hc = self._make(sleep_hours=(2, 6))
        hc.update(response_time_ms=100, health_status="green", hour_utc=3)
        assert hc.is_sleeping() is True
        hc.update(response_time_ms=100, health_status="green", hour_utc=12)
        assert hc.is_sleeping() is False

    def test_recommended_pulse_interval_asleep(self):
        hc = self._make(sleep_hours=(2, 6))
        hc.update(response_time_ms=100, health_status="green", hour_utc=3)
        assert hc.recommended_pulse_interval() == 300

    def test_recommended_pulse_interval_stressed(self):
        hc = self._make()
        hc.state.stress_level = 0.9
        hc.state.circadian_phase = "awake"
        interval = hc.recommended_pulse_interval()
        assert interval <= 20

    def test_record_action_cost_drains_energy(self):
        hc = self._make()
        hc.record_action_cost(0.3)
        assert hc.state.energy_level == pytest.approx(0.7, abs=0.01)

    def test_ema_setpoint_adapts(self):
        hc = self._make()
        initial = hc.state.setpoint_rt_ms
        for _ in range(20):
            hc.update(response_time_ms=500, health_status="green", hour_utc=12)
        assert hc.state.setpoint_rt_ms > initial


class TestTrendDetector:
    def _make(self):
        from cell_core.homeostasis import TrendDetector
        return TrendDetector()

    def test_no_trend_on_empty(self):
        td = self._make()
        result = td.detect([])
        assert result.monotonic_drift is False
        assert result.flapping is False
        assert result.sustained_degraded is False

    def test_monotonic_drift(self):
        td = self._make()
        pulses = [
            {"response_time_ms": 100 + i * 50, "health_status": "green"}
            for i in range(6)
        ]
        result = td.detect(pulses)
        assert result.monotonic_drift is True

    def test_no_drift_when_stable(self):
        td = self._make()
        pulses = [
            {"response_time_ms": 100, "health_status": "green"}
            for _ in range(6)
        ]
        result = td.detect(pulses)
        assert result.monotonic_drift is False

    def test_flapping(self):
        td = self._make()
        pulses = [
            {"response_time_ms": 100, "health_status": "green" if i % 2 == 0 else "red"}
            for i in range(8)
        ]
        result = td.detect(pulses)
        assert result.flapping is True

    def test_sustained_degraded(self):
        td = self._make()
        pulses = [
            {"response_time_ms": 100, "health_status": "red"}
            for _ in range(5)
        ]
        result = td.detect(pulses)
        assert result.sustained_degraded is True

    def test_no_sustained_when_mixed(self):
        td = self._make()
        pulses = [
            {"response_time_ms": 100, "health_status": "red"},
            {"response_time_ms": 100, "health_status": "green"},
            {"response_time_ms": 100, "health_status": "red"},
            {"response_time_ms": 100, "health_status": "red"},
        ]
        result = td.detect(pulses)
        assert result.sustained_degraded is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/cell-core && pytest tests/test_homeostasis.py -v`
Expected: FAIL

- [ ] **Step 3: Implement homeostasis.py**

Create `packages/cell-core/cell_core/homeostasis.py`:

```python
"""Homeostatic Controller + Trend Detector — the organism's governor.

Adaptive setpoints via EMA. Stress/energy/arousal as continuous 0-1 variables.
Circadian rhythm: awake → drowsy → asleep cycle.
Trend detection: monotonic drift, flapping, sustained degraded.

Extracted from apps/cell/cell/fast/homeostatic_controller.py + trend_detector.py.
Runs in FAST layer: no LLM, no network, <1ms per update.
"""
from __future__ import annotations

import dataclasses
import logging
import math
from dataclasses import dataclass
from typing import Any

from cell_core.types import HomeostaticState

logger = logging.getLogger("cell_core.homeostasis")

_EMA_ALPHA = 0.2
_STRESS_DECAY = 0.05
_STRESS_RISE_BASE = 0.15
_ENERGY_RECOVERY = 0.02
_AROUSAL_DECAY = 0.03


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


class HomeostaticController:
    """Maintains internal equilibrium. <1ms per update."""

    def __init__(self, sleep_hours: tuple[int, int] = (2, 6)) -> None:
        self.state = HomeostaticState()
        self._sleep_start = sleep_hours[0]
        self._sleep_end = sleep_hours[1]
        self._rt_history: list[float] = []
        self._max_history = 100

    def update(
        self,
        response_time_ms: int,
        health_status: str,
        hour_utc: int,
    ) -> HomeostaticState:
        """Process one pulse reading and update internal state."""
        rt = float(response_time_ms)
        status = health_status.value if hasattr(health_status, "value") else health_status

        self._rt_history.append(rt)
        if len(self._rt_history) > self._max_history:
            self._rt_history = self._rt_history[-self._max_history:]

        # 1. Update setpoint (EMA)
        self.state.setpoint_rt_ms = (
            _EMA_ALPHA * rt + (1 - _EMA_ALPHA) * self.state.setpoint_rt_ms
        )

        # 2. Update comfort zone (setpoint +/- 1 sigma)
        if len(self._rt_history) >= 5:
            mean = sum(self._rt_history) / len(self._rt_history)
            variance = sum((x - mean) ** 2 for x in self._rt_history) / len(self._rt_history)
            sigma = math.sqrt(variance) if variance > 0 else 25.0
            sigma = max(sigma, 25.0)
            self.state.comfort_zone = (
                max(0.0, self.state.setpoint_rt_ms - sigma),
                self.state.setpoint_rt_ms + sigma,
            )

        # 3. Update stress
        low, high = self.state.comfort_zone
        if rt < low or rt > high:
            if rt > high:
                deviation = (rt - high) / max(high, 1.0)
            else:
                deviation = (low - rt) / max(low, 1.0)
            rise = _STRESS_RISE_BASE * min(deviation, 2.0)
            self.state.stress_level = _clamp(self.state.stress_level + rise)
        else:
            self.state.stress_level = _clamp(self.state.stress_level - _STRESS_DECAY)

        if status != "green":
            bump = 0.1 if status == "yellow" else 0.25
            self.state.stress_level = _clamp(self.state.stress_level + bump)

        # 4. Update energy
        if status == "green":
            self.state.energy_level = _clamp(self.state.energy_level + _ENERGY_RECOVERY)

        # 5. Update arousal
        target_arousal = 0.5 + self.state.stress_level * 0.4
        diff = target_arousal - self.state.arousal
        self.state.arousal = _clamp(self.state.arousal + diff * _AROUSAL_DECAY * 3)

        # 6. Circadian phase
        if self._sleep_start <= hour_utc < self._sleep_end:
            self.state.circadian_phase = "asleep"
        elif hour_utc == (self._sleep_start - 1) % 24:
            self.state.circadian_phase = "drowsy"
        elif hour_utc == self._sleep_end:
            self.state.circadian_phase = "drowsy"
        else:
            self.state.circadian_phase = "awake"

        return dataclasses.replace(self.state)

    def record_action_cost(self, cost: float) -> None:
        self.state.energy_level = _clamp(self.state.energy_level - cost)

    def recommended_pulse_interval(self) -> int:
        phase = self.state.circadian_phase
        stress = self.state.stress_level
        if phase == "asleep":
            return 300
        if phase == "drowsy":
            return 120
        interval = int(60 - stress * 45)
        return max(15, min(60, interval))

    def is_sleeping(self) -> bool:
        return self.state.circadian_phase == "asleep"


@dataclass
class TrendResult:
    monotonic_drift: bool = False
    flapping: bool = False
    sustained_degraded: bool = False
    details: dict[str, Any] | None = None


class TrendDetector:
    """Stateless trend detector. Call detect() on every pulse."""

    def __init__(
        self,
        drift_window: int = 5,
        flap_window: int = 6,
        flap_threshold: int = 3,
        sustained_window: int = 4,
    ) -> None:
        self._drift_window = drift_window
        self._flap_window = flap_window
        self._flap_threshold = flap_threshold
        self._sustained_window = sustained_window

    def detect(self, recent_pulses: list[dict[str, Any]]) -> TrendResult:
        if len(recent_pulses) < 2:
            return TrendResult()

        details: dict[str, Any] = {}

        # 1. Monotonic drift
        drift = False
        if len(recent_pulses) >= self._drift_window:
            window = recent_pulses[-self._drift_window:]
            rts = [p.get("response_time_ms", 0) for p in window]
            if all(rts[i] < rts[i + 1] for i in range(len(rts) - 1)) and rts[0] > 0:
                drift = True
                details["drift_rts_ms"] = rts

        # 2. Flapping
        flapping = False
        if len(recent_pulses) >= self._flap_window:
            window = recent_pulses[-self._flap_window:]
            statuses = [p.get("health_status", "green") for p in window]
            alternations = sum(
                1 for i in range(len(statuses) - 1)
                if (statuses[i] == "green") != (statuses[i + 1] == "green")
            )
            if alternations >= self._flap_threshold:
                flapping = True
                details["flap_alternations"] = alternations

        # 3. Sustained degraded
        sustained = False
        if len(recent_pulses) >= self._sustained_window:
            window = recent_pulses[-self._sustained_window:]
            statuses = [p.get("health_status", "green") for p in window]
            if all(s != "green" for s in statuses):
                sustained = True

        return TrendResult(
            monotonic_drift=drift,
            flapping=flapping,
            sustained_degraded=sustained,
            details=details if details else None,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/cell-core && pytest tests/test_homeostasis.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add packages/cell-core/cell_core/homeostasis.py packages/cell-core/tests/test_homeostasis.py
git commit -m "feat(cell-core): homeostatic controller + trend detector"
```

---

### Task 6: identity.py

**Files:**
- Create: `packages/cell-core/cell_core/identity.py`
- Create: `packages/cell-core/tests/test_identity.py`

**Reference:** Extract from `apps/cell/cell/identity/self_model.py`

- [ ] **Step 1: Write failing test**

Create `packages/cell-core/tests/test_identity.py`:

```python
"""Tests for cell_core.identity — SelfModel persistence."""
import json

import pytest


class TestSelfModel:
    def test_default_birth_date(self):
        from cell_core.identity import SelfModel
        m = SelfModel()
        assert m.birth_date != ""
        assert m.total_pulses == 0

    def test_from_dict_round_trip(self):
        from cell_core.identity import SelfModel
        m = SelfModel(total_pulses=100, total_actions=5)
        m.capabilities = {"health": 0.95}
        d = m.to_dict()
        m2 = SelfModel.from_dict(d)
        assert m2.total_pulses == 100
        assert m2.capabilities["health"] == 0.95


class TestSelfModelManager:
    def test_load_creates_default(self, tmp_path):
        from cell_core.identity import SelfModelManager
        mgr = SelfModelManager(path=tmp_path / "model.json")
        mgr.load()
        assert mgr.model.total_pulses == 0

    def test_save_and_load(self, tmp_path):
        from cell_core.identity import SelfModelManager
        path = tmp_path / "model.json"
        mgr = SelfModelManager(path=path)
        mgr.model.total_pulses = 42
        mgr.save()

        mgr2 = SelfModelManager(path=path)
        mgr2.load()
        assert mgr2.model.total_pulses == 42

    def test_record_pulse(self, tmp_path):
        from cell_core.identity import SelfModelManager
        mgr = SelfModelManager(path=tmp_path / "model.json")
        mgr.record_pulse()
        assert mgr.model.total_pulses == 1
        mgr.record_pulse()
        assert mgr.model.total_pulses == 2

    def test_record_action(self, tmp_path):
        from cell_core.identity import SelfModelManager
        mgr = SelfModelManager(path=tmp_path / "model.json")
        mgr.record_action("restart_service")
        assert mgr.model.total_actions == 1

    def test_sensor_reliability(self, tmp_path):
        from cell_core.identity import SelfModelManager
        mgr = SelfModelManager(path=tmp_path / "model.json")
        for _ in range(8):
            mgr.update_sensor_reliability("health", True)
        mgr.update_sensor_reliability("health", False)
        mgr.update_sensor_reliability("health", False)
        # 8 successes out of 10 = 0.8
        assert mgr.model.capabilities["health"] == pytest.approx(0.8)

    def test_atomic_write(self, tmp_path):
        from cell_core.identity import SelfModelManager
        path = tmp_path / "model.json"
        mgr = SelfModelManager(path=path)
        mgr.model.total_pulses = 99
        mgr.save()
        # No .tmp file left behind
        assert not (tmp_path / "model.tmp").exists()
        # File is valid JSON
        data = json.loads(path.read_text())
        assert data["total_pulses"] == 99

    def test_to_prompt_context(self, tmp_path):
        from cell_core.identity import SelfModelManager
        mgr = SelfModelManager(path=tmp_path / "model.json")
        mgr.model.total_pulses = 100
        mgr.model.capabilities = {"health": 0.95}
        ctx = mgr.to_prompt_context()
        assert "100" in ctx
        assert "health" in ctx
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/cell-core && pytest tests/test_identity.py -v`
Expected: FAIL

- [ ] **Step 3: Implement identity.py**

Create `packages/cell-core/cell_core/identity.py`:

```python
"""SelfModel — the organism knows itself.

Persistent identity that survives restarts: lifetime counters,
sensor reliability scores, learned preferences, acknowledged weaknesses.
Stored as JSON file — simple, local, fast.

Extracted from apps/cell/cell/identity/self_model.py.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cell_core.identity")


@dataclass
class SelfModel:
    """The organism's understanding of itself."""
    capabilities: dict[str, float] = field(default_factory=dict)
    preferences: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    personality_traits: dict[str, float] = field(default_factory=dict)
    sensor_history: dict[str, list[bool]] = field(default_factory=dict)
    age_days: int = 0
    total_pulses: int = 0
    total_actions: int = 0
    birth_date: str = ""

    def __post_init__(self) -> None:
        if not self.birth_date:
            self.birth_date = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "capabilities": self.capabilities,
            "preferences": self.preferences,
            "weaknesses": self.weaknesses,
            "personality_traits": self.personality_traits,
            "sensor_history": self.sensor_history,
            "age_days": self.age_days,
            "total_pulses": self.total_pulses,
            "total_actions": self.total_actions,
            "birth_date": self.birth_date,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SelfModel:
        return cls(
            capabilities=data.get("capabilities", {}),
            preferences=data.get("preferences", []),
            weaknesses=data.get("weaknesses", []),
            personality_traits=data.get("personality_traits", {}),
            sensor_history=data.get("sensor_history", {}),
            age_days=data.get("age_days", 0),
            total_pulses=data.get("total_pulses", 0),
            total_actions=data.get("total_actions", 0),
            birth_date=data.get("birth_date", ""),
        )


class SelfModelManager:
    """Manages loading, updating, and saving the self-model."""

    def __init__(self, path: str | Path = "data/self_model.json") -> None:
        self._path = Path(path)
        self.model = SelfModel()
        self._sensor_history: dict[str, list[bool]] = {}

    def load(self) -> None:
        if not self._path.exists():
            logger.info(f"Self-model not found at {self._path}, using defaults")
            return
        try:
            data = json.loads(self._path.read_text())
            self.model = SelfModel.from_dict(data)
            self._sensor_history = {k: list(v) for k, v in self.model.sensor_history.items()}
        except Exception as e:
            logger.warning(f"Failed to load self-model: {e}")

    def save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.model.to_dict(), indent=2))
            tmp.replace(self._path)  # atomic on POSIX
        except Exception as e:
            logger.warning(f"Failed to save self-model: {e}")

    def record_pulse(self) -> None:
        self.model.total_pulses += 1
        if self.model.birth_date:
            try:
                birth = datetime.fromisoformat(self.model.birth_date)
                now = datetime.now(timezone.utc)
                self.model.age_days = (now - birth).days
            except (ValueError, TypeError):
                pass

    def record_action(self, action_name: str) -> None:
        self.model.total_actions += 1

    def update_sensor_reliability(self, sensor_name: str, success: bool) -> None:
        if sensor_name not in self._sensor_history:
            self._sensor_history[sensor_name] = []
        history = self._sensor_history[sensor_name]
        history.append(success)
        if len(history) > 100:
            self._sensor_history[sensor_name] = history[-100:]
            history = self._sensor_history[sensor_name]
        self.model.capabilities[sensor_name] = sum(history) / len(history)
        self.model.sensor_history = dict(self._sensor_history)

    def to_prompt_context(self) -> str:
        lines = [
            "SELF-MODEL:",
            f"  age_days: {self.model.age_days}",
            f"  total_pulses: {self.model.total_pulses}",
            f"  total_actions: {self.model.total_actions}",
        ]
        if self.model.capabilities:
            caps = ", ".join(f"{k}: {v:.0%}" for k, v in sorted(self.model.capabilities.items()))
            lines.append(f"  sensor_reliability: {caps}")
        if self.model.preferences:
            lines.append(f"  preferences: {', '.join(self.model.preferences)}")
        if self.model.weaknesses:
            lines.append(f"  weaknesses: {', '.join(self.model.weaknesses)}")
        return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/cell-core && pytest tests/test_identity.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add packages/cell-core/cell_core/identity.py packages/cell-core/tests/test_identity.py
git commit -m "feat(cell-core): self-model identity with atomic JSON persistence"
```

---

### Task 7: memory_sqlite.py

**Files:**
- Create: `packages/cell-core/cell_core/memory_sqlite.py`
- Create: `packages/cell-core/tests/test_memory_sqlite.py`

- [ ] **Step 1: Write failing test**

Create `packages/cell-core/tests/test_memory_sqlite.py`:

```python
"""Tests for cell_core.memory_sqlite — SQLite-backed memory stores."""
import asyncio
import time

import pytest

from cell_core.types import Episode, LearnedRule


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_cell.db")


class TestSqliteSTM:
    @pytest.mark.asyncio
    async def test_store_and_recent(self, db_path):
        from cell_core.memory_sqlite import SqliteSTM
        stm = SqliteSTM(db_path, ttl_seconds=3600)
        await stm.store("health", {"status": "green", "rt": 100})
        await stm.store("health", {"status": "yellow", "rt": 200})
        results = await stm.recent("health", limit=10)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_recent_respects_limit(self, db_path):
        from cell_core.memory_sqlite import SqliteSTM
        stm = SqliteSTM(db_path)
        for i in range(10):
            await stm.store("sensor", {"i": i})
        results = await stm.recent("sensor", limit=3)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_recent_filters_by_event_type(self, db_path):
        from cell_core.memory_sqlite import SqliteSTM
        stm = SqliteSTM(db_path)
        await stm.store("health", {"v": 1})
        await stm.store("db", {"v": 2})
        results = await stm.recent("health", limit=10)
        assert len(results) == 1
        assert results[0]["v"] == 1

    @pytest.mark.asyncio
    async def test_recent_empty_type_returns_all(self, db_path):
        from cell_core.memory_sqlite import SqliteSTM
        stm = SqliteSTM(db_path)
        await stm.store("a", {"v": 1})
        await stm.store("b", {"v": 2})
        results = await stm.recent("", limit=10)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_ttl_cleanup(self, db_path):
        from cell_core.memory_sqlite import SqliteSTM
        stm = SqliteSTM(db_path, ttl_seconds=1)
        await stm.store("x", {"v": 1})
        await asyncio.sleep(1.1)
        await stm.store("x", {"v": 2})  # triggers cleanup
        results = await stm.recent("x", limit=10)
        assert len(results) == 1
        assert results[0]["v"] == 2


class TestSqliteEpisodic:
    @pytest.mark.asyncio
    async def test_store_and_recall(self, db_path):
        from cell_core.memory_sqlite import SqliteEpisodic
        ep = SqliteEpisodic(db_path)
        episode = Episode(
            situation={"status": "red"}, emotion="stressed",
            action_taken="restart", outcome="success", lesson="restart works",
            timestamp=time.time(),
        )
        eid = await ep.store(episode)
        assert eid > 0
        results = await ep.recall_recent(hours=1, limit=10)
        assert len(results) == 1
        assert results[0].action_taken == "restart"

    @pytest.mark.asyncio
    async def test_recall_orders_by_activation(self, db_path):
        from cell_core.memory_sqlite import SqliteEpisodic
        ep = SqliteEpisodic(db_path)
        # Old episode
        old = Episode(
            situation={}, emotion="calm", action_taken="none",
            outcome="success", lesson="ok",
            timestamp=time.time() - 86400 * 5,
        )
        # Recent episode
        recent = Episode(
            situation={}, emotion="alert", action_taken="scale",
            outcome="success", lesson="scale helps",
            timestamp=time.time(),
        )
        await ep.store(old)
        await ep.store(recent)
        results = await ep.recall({}, limit=2)
        assert results[0].action_taken == "scale"  # more recent = higher activation

    @pytest.mark.asyncio
    async def test_forget_weak(self, db_path):
        from cell_core.memory_sqlite import SqliteEpisodic
        ep = SqliteEpisodic(db_path)
        for i in range(10):
            e = Episode(
                situation={"i": i}, emotion="calm", action_taken="none",
                outcome="success", lesson=f"lesson {i}",
                timestamp=time.time() - (10 - i) * 3600,
            )
            await ep.store(e)
        removed = await ep.forget_weak(keep=5)
        assert removed == 5
        remaining = await ep.recall_recent(hours=24, limit=100)
        assert len(remaining) == 5

    @pytest.mark.asyncio
    async def test_recall_increments_recall_count(self, db_path):
        from cell_core.memory_sqlite import SqliteEpisodic
        ep = SqliteEpisodic(db_path)
        episode = Episode(
            situation={}, emotion="calm", action_taken="none",
            outcome="success", lesson="ok", timestamp=time.time(),
        )
        eid = await ep.store(episode)
        await ep.recall({}, limit=1)
        await ep.recall({}, limit=1)
        results = await ep.recall_recent(hours=1, limit=1)
        assert results[0].recall_count == 2


class TestSqliteLTM:
    @pytest.mark.asyncio
    async def test_store_and_load(self, db_path):
        from cell_core.memory_sqlite import SqliteLTM
        ltm = SqliteLTM(db_path)
        rule = LearnedRule(rule_text="When latency > 500ms, restart", support_count=3)
        await ltm.store_rule(rule)
        rules = await ltm.load_rules(limit=10)
        assert len(rules) == 1
        assert rules[0].rule_text == "When latency > 500ms, restart"

    @pytest.mark.asyncio
    async def test_load_respects_limit(self, db_path):
        from cell_core.memory_sqlite import SqliteLTM
        ltm = SqliteLTM(db_path)
        for i in range(10):
            await ltm.store_rule(LearnedRule(rule_text=f"Rule {i}", support_count=1))
        rules = await ltm.load_rules(limit=3)
        assert len(rules) == 3

    @pytest.mark.asyncio
    async def test_condense_extracts_patterns(self, db_path):
        from cell_core.memory_sqlite import SqliteLTM
        ltm = SqliteLTM(db_path)
        episodes = [
            Episode(
                situation={"status": "red"}, emotion="stressed",
                action_taken="restart", outcome="success", lesson="restart works",
                timestamp=time.time(),
            )
            for _ in range(5)
        ]
        rules = await ltm.condense(episodes)
        assert len(rules) >= 1
        assert any("restart" in r.rule_text.lower() for r in rules)


class TestSqliteMemoryStack:
    @pytest.mark.asyncio
    async def test_creates_all_three_stores(self, db_path):
        from cell_core.memory_sqlite import SqliteMemoryStack
        from cell_core.protocols import STMStore, LTMStore, EpisodicStore
        stack = SqliteMemoryStack(db_path)
        assert isinstance(stack.stm, STMStore)
        assert isinstance(stack.ltm, LTMStore)
        assert isinstance(stack.episodic, EpisodicStore)

    @pytest.mark.asyncio
    async def test_shared_db_file(self, db_path):
        from cell_core.memory_sqlite import SqliteMemoryStack
        stack = SqliteMemoryStack(db_path)
        await stack.stm.store("test", {"v": 1})
        episode = Episode(
            situation={}, emotion="calm", action_taken="none",
            outcome="success", lesson="ok", timestamp=time.time(),
        )
        await stack.episodic.store(episode)
        await stack.ltm.store_rule(LearnedRule(rule_text="rule", support_count=1))
        # All use same DB file — just verify no errors
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/cell-core && pytest tests/test_memory_sqlite.py -v`
Expected: FAIL

- [ ] **Step 3: Implement memory_sqlite.py**

Create `packages/cell-core/cell_core/memory_sqlite.py`:

```python
"""SQLite-backed memory stores — zero external dependencies.

All async methods use asyncio.to_thread() for I/O to keep the event loop clean.
Each store creates its own tables on first use (idempotent).

This is the default backend for lightweight organs like Mata Garuda.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from collections import Counter
from pathlib import Path
from typing import Any

from cell_core.types import Episode, LearnedRule

logger = logging.getLogger("cell_core.memory.sqlite")


def _get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


class SqliteSTM:
    """Short-term memory in SQLite with TTL cleanup."""

    def __init__(self, db_path: str, ttl_seconds: int = 86400) -> None:
        self._db_path = db_path
        self._ttl = ttl_seconds
        self._ensure_table()

    def _ensure_table(self) -> None:
        conn = _get_conn(self._db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stm (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                data_json TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_stm_type ON stm(event_type)")
        conn.commit()
        conn.close()

    def _store_sync(self, event_type: str, data: dict[str, Any]) -> None:
        conn = _get_conn(self._db_path)
        now = time.time()
        conn.execute(
            "INSERT INTO stm (event_type, data_json, created_at) VALUES (?, ?, ?)",
            (event_type, json.dumps(data), now),
        )
        # TTL cleanup
        cutoff = now - self._ttl
        conn.execute("DELETE FROM stm WHERE created_at < ?", (cutoff,))
        conn.commit()
        conn.close()

    def _recent_sync(self, event_type: str, limit: int) -> list[dict[str, Any]]:
        conn = _get_conn(self._db_path)
        if event_type:
            rows = conn.execute(
                "SELECT data_json FROM stm WHERE event_type = ? ORDER BY created_at DESC LIMIT ?",
                (event_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT data_json FROM stm ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        conn.close()
        return [json.loads(row["data_json"]) for row in rows]

    async def store(self, event_type: str, data: dict[str, Any]) -> None:
        await asyncio.to_thread(self._store_sync, event_type, data)

    async def recent(self, event_type: str, limit: int) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._recent_sync, event_type, limit)


class SqliteEpisodic:
    """Episodic memory in SQLite with ACT-R activation scoring."""

    def __init__(self, db_path: str, max_episodes: int = 1000) -> None:
        self._db_path = db_path
        self._max_episodes = max_episodes
        self._ensure_table()

    def _ensure_table(self) -> None:
        conn = _get_conn(self._db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                situation_json TEXT NOT NULL,
                emotion TEXT NOT NULL,
                action_taken TEXT NOT NULL,
                outcome TEXT NOT NULL,
                lesson TEXT NOT NULL,
                timestamp REAL NOT NULL,
                recall_count INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()

    def _store_sync(self, episode: Episode) -> int:
        conn = _get_conn(self._db_path)
        ts = episode.timestamp if episode.timestamp > 0 else time.time()
        cursor = conn.execute(
            """INSERT INTO episodes (situation_json, emotion, action_taken, outcome, lesson, timestamp, recall_count)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (json.dumps(episode.situation), episode.emotion, episode.action_taken,
             episode.outcome, episode.lesson, ts, episode.recall_count),
        )
        conn.commit()
        eid = cursor.lastrowid
        conn.close()
        return eid

    def _recall_sync(self, situation: dict[str, Any], limit: int) -> list[Episode]:
        conn = _get_conn(self._db_path)
        rows = conn.execute(
            "SELECT * FROM episodes ORDER BY timestamp DESC LIMIT ?",
            (limit * 3,),
        ).fetchall()
        episodes = []
        for row in rows:
            ep = Episode(
                id=row["id"],
                situation=json.loads(row["situation_json"]),
                emotion=row["emotion"],
                action_taken=row["action_taken"],
                outcome=row["outcome"],
                lesson=row["lesson"],
                timestamp=row["timestamp"],
                recall_count=row["recall_count"],
            )
            ep.activation = ep.compute_activation()
            episodes.append(ep)
        episodes.sort(key=lambda e: e.activation, reverse=True)
        top = episodes[:limit]
        # Increment recall_count
        if top:
            ids = [e.id for e in top if e.id > 0]
            if ids:
                placeholders = ",".join("?" * len(ids))
                conn.execute(
                    f"UPDATE episodes SET recall_count = recall_count + 1 WHERE id IN ({placeholders})",
                    ids,
                )
                conn.commit()
        conn.close()
        return top

    def _recall_recent_sync(self, hours: int, limit: int) -> list[Episode]:
        conn = _get_conn(self._db_path)
        cutoff = time.time() - hours * 3600
        rows = conn.execute(
            "SELECT * FROM episodes WHERE timestamp >= ? ORDER BY timestamp DESC LIMIT ?",
            (cutoff, limit),
        ).fetchall()
        conn.close()
        episodes = []
        for row in rows:
            ep = Episode(
                id=row["id"],
                situation=json.loads(row["situation_json"]),
                emotion=row["emotion"],
                action_taken=row["action_taken"],
                outcome=row["outcome"],
                lesson=row["lesson"],
                timestamp=row["timestamp"],
                recall_count=row["recall_count"],
            )
            ep.activation = ep.compute_activation()
            episodes.append(ep)
        return episodes

    def _forget_weak_sync(self, keep: int) -> int:
        conn = _get_conn(self._db_path)
        count = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        if count <= keep:
            conn.close()
            return 0
        # Get all, compute activation, delete weakest
        rows = conn.execute("SELECT id, timestamp, recall_count FROM episodes").fetchall()
        scored = []
        for row in rows:
            ep = Episode(
                situation={}, emotion="calm", action_taken="",
                outcome="", lesson="",
                timestamp=row["timestamp"], recall_count=row["recall_count"],
            )
            scored.append((row["id"], ep.compute_activation()))
        scored.sort(key=lambda x: x[1], reverse=True)
        to_delete = [s[0] for s in scored[keep:]]
        if to_delete:
            placeholders = ",".join("?" * len(to_delete))
            conn.execute(f"DELETE FROM episodes WHERE id IN ({placeholders})", to_delete)
            conn.commit()
        conn.close()
        return len(to_delete)

    async def store(self, episode: Episode) -> int:
        return await asyncio.to_thread(self._store_sync, episode)

    async def recall(self, situation: dict[str, Any], limit: int) -> list[Episode]:
        return await asyncio.to_thread(self._recall_sync, situation, limit)

    async def recall_recent(self, hours: int, limit: int) -> list[Episode]:
        return await asyncio.to_thread(self._recall_recent_sync, hours, limit)

    async def forget_weak(self, keep: int) -> int:
        return await asyncio.to_thread(self._forget_weak_sync, keep)


class SqliteLTM:
    """Long-term rules in SQLite with FTS5 search."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._ensure_table()

    def _ensure_table(self) -> None:
        conn = _get_conn(self._db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ltm (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_text TEXT NOT NULL,
                support_count INTEGER NOT NULL DEFAULT 1,
                created_at REAL NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def _store_rule_sync(self, rule: LearnedRule) -> None:
        conn = _get_conn(self._db_path)
        conn.execute(
            "INSERT INTO ltm (rule_text, support_count, created_at) VALUES (?, ?, ?)",
            (rule.rule_text, rule.support_count, time.time()),
        )
        conn.commit()
        conn.close()

    def _load_rules_sync(self, limit: int) -> list[LearnedRule]:
        conn = _get_conn(self._db_path)
        rows = conn.execute(
            "SELECT rule_text, support_count, created_at FROM ltm ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [
            LearnedRule(
                rule_text=row["rule_text"],
                support_count=row["support_count"],
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]

    def _condense_sync(self, episodes: list[Episode]) -> list[LearnedRule]:
        """Extract patterns from episodes — group by action+outcome, count support."""
        patterns: Counter[str] = Counter()
        for ep in episodes:
            key = f"When {ep.emotion}, {ep.action_taken} → {ep.outcome}"
            patterns[key] += 1
        rules = []
        for pattern, count in patterns.most_common():
            if count >= 2:  # minimum support
                rules.append(LearnedRule(rule_text=pattern, support_count=count))
        return rules

    async def store_rule(self, rule: LearnedRule) -> None:
        await asyncio.to_thread(self._store_rule_sync, rule)

    async def load_rules(self, limit: int) -> list[LearnedRule]:
        return await asyncio.to_thread(self._load_rules_sync, limit)

    async def condense(self, episodes: list[Episode]) -> list[LearnedRule]:
        return await asyncio.to_thread(self._condense_sync, episodes)


class SqliteMemoryStack:
    """Convenience: creates all 3 stores from one SQLite DB path."""

    def __init__(self, db_path: str = "cell.db") -> None:
        self.stm = SqliteSTM(db_path)
        self.ltm = SqliteLTM(db_path)
        self.episodic = SqliteEpisodic(db_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/cell-core && pytest tests/test_memory_sqlite.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add packages/cell-core/cell_core/memory_sqlite.py packages/cell-core/tests/test_memory_sqlite.py
git commit -m "feat(cell-core): SQLite memory stores (STM, LTM, Episodic) with ACT-R"
```

---

### Task 8: reasoner.py

**Files:**
- Create: `packages/cell-core/cell_core/reasoner.py`
- Create: `packages/cell-core/tests/test_reasoner.py`

- [ ] **Step 1: Write failing test**

Create `packages/cell-core/tests/test_reasoner.py`:

```python
"""Tests for cell_core.reasoner — tier escalation framework."""
import asyncio
import json

import pytest

from cell_core.types import Proposal


class TestTierConfig:
    def test_creation(self):
        from cell_core.reasoner import TierConfig
        t = TierConfig(tier=0, name="fast", command=["echo", "test"], max_cost_usd=0.0, timeout_seconds=5.0)
        assert t.tier == 0
        assert t.name == "fast"


class TestReasonerFramework:
    def _make(self, tiers=None, allowlist=None):
        from cell_core.reasoner import ReasonerFramework, TierConfig
        if tiers is None:
            tiers = [
                TierConfig(
                    tier=0, name="echo_reasoner",
                    command=["echo", json.dumps({"action": "none", "reason": "stable", "confidence": 1.0})],
                    max_cost_usd=0.0, timeout_seconds=5.0,
                ),
            ]
        if allowlist is None:
            allowlist = ["restart_service", "alert_human", "none"]
        return ReasonerFramework(tiers=tiers, allowlist=allowlist)

    @pytest.mark.asyncio
    async def test_reason_returns_proposal(self):
        rf = self._make()
        proposal = await rf.reason("system is healthy", {})
        assert isinstance(proposal, Proposal)
        assert proposal.action == "none"

    @pytest.mark.asyncio
    async def test_tiers_sorted_by_cost(self):
        from cell_core.reasoner import TierConfig
        expensive = TierConfig(
            tier=1, name="expensive",
            command=["echo", json.dumps({"action": "none", "reason": "ok", "confidence": 1.0})],
            max_cost_usd=1.0, timeout_seconds=5.0,
        )
        cheap = TierConfig(
            tier=0, name="cheap",
            command=["echo", json.dumps({"action": "none", "reason": "ok", "confidence": 1.0})],
            max_cost_usd=0.0, timeout_seconds=5.0,
        )
        rf = self._make(tiers=[expensive, cheap])
        assert rf._tiers[0].name == "cheap"

    @pytest.mark.asyncio
    async def test_timeout_escalates(self):
        from cell_core.reasoner import TierConfig
        slow = TierConfig(
            tier=0, name="slow",
            command=["sleep", "10"],
            max_cost_usd=0.0, timeout_seconds=0.1,
        )
        fast = TierConfig(
            tier=1, name="fast",
            command=["echo", json.dumps({"action": "none", "reason": "fallback", "confidence": 0.5})],
            max_cost_usd=0.1, timeout_seconds=5.0,
        )
        rf = self._make(tiers=[slow, fast])
        proposal = await rf.reason("test", {})
        assert proposal.tier_used == 1  # escalated to fast

    @pytest.mark.asyncio
    async def test_invalid_json_escalates(self):
        from cell_core.reasoner import TierConfig
        bad = TierConfig(
            tier=0, name="bad",
            command=["echo", "not json"],
            max_cost_usd=0.0, timeout_seconds=5.0,
        )
        good = TierConfig(
            tier=1, name="good",
            command=["echo", json.dumps({"action": "none", "reason": "ok", "confidence": 0.8})],
            max_cost_usd=0.1, timeout_seconds=5.0,
        )
        rf = self._make(tiers=[bad, good])
        proposal = await rf.reason("test", {})
        assert proposal.tier_used == 1

    @pytest.mark.asyncio
    async def test_all_tiers_fail_returns_none_proposal(self):
        from cell_core.reasoner import TierConfig
        bad = TierConfig(
            tier=0, name="bad",
            command=["false"],  # exits with code 1
            max_cost_usd=0.0, timeout_seconds=2.0,
        )
        rf = self._make(tiers=[bad])
        proposal = await rf.reason("test", {})
        assert proposal.action == "none"
        assert proposal.tier_used == -1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd packages/cell-core && pytest tests/test_reasoner.py -v`
Expected: FAIL

- [ ] **Step 3: Implement reasoner.py**

Create `packages/cell-core/cell_core/reasoner.py`:

```python
"""Tier-based reasoning framework — tries cheapest tier first.

All LLM invocations via subprocess (SYMBIOSIS Law #1: CLI-only).
Each organ configures its own tiers and commands.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

from cell_core.types import Proposal

logger = logging.getLogger("cell_core.reasoner")


@dataclass
class TierConfig:
    """Configuration for one reasoning tier."""
    tier: int
    name: str
    command: list[str]
    max_cost_usd: float
    timeout_seconds: float


class ReasonerFramework:
    """Tier-based escalation. Tries cheapest tier first."""

    def __init__(self, tiers: list[TierConfig], allowlist: list[str]) -> None:
        self._tiers = sorted(tiers, key=lambda t: t.max_cost_usd)
        self._allowlist = set(allowlist) | {"none"}

    async def reason(
        self,
        situation: str,
        context: dict[str, Any],
    ) -> Proposal:
        """Escalate through tiers until one produces a valid proposal."""
        for tier_cfg in self._tiers:
            try:
                proposal = await self._try_tier(tier_cfg, situation, context)
                if proposal is not None:
                    return proposal
            except Exception as e:
                logger.warning(f"Tier {tier_cfg.name} failed: {e}")
                continue

        # All tiers failed — return safe default
        return Proposal(
            action="none",
            reason="All reasoning tiers failed",
            confidence=0.0,
            tier_used=-1,
        )

    async def _try_tier(
        self,
        tier_cfg: TierConfig,
        situation: str,
        context: dict[str, Any],
    ) -> Proposal | None:
        """Run one tier. Returns Proposal or None if tier fails."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *tier_cfg.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=tier_cfg.timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Tier {tier_cfg.name} timed out after {tier_cfg.timeout_seconds}s")
            return None

        if proc.returncode != 0:
            logger.warning(f"Tier {tier_cfg.name} exited with code {proc.returncode}")
            return None

        output = stdout.decode().strip()
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            # Try to extract JSON from output (LLMs sometimes wrap in markdown)
            import re
            match = re.search(r'\{[^{}]+\}', output)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    logger.warning(f"Tier {tier_cfg.name}: no valid JSON in output")
                    return None
            else:
                logger.warning(f"Tier {tier_cfg.name}: no valid JSON in output")
                return None

        action = data.get("action", "none")
        if action not in self._allowlist:
            logger.warning(f"Tier {tier_cfg.name}: action '{action}' not in allowlist")
            action = "none"

        return Proposal(
            action=action,
            reason=data.get("reason", ""),
            confidence=float(data.get("confidence", 0.0)),
            tier_used=tier_cfg.tier,
            cost_usd=tier_cfg.max_cost_usd,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd packages/cell-core && pytest tests/test_reasoner.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add packages/cell-core/cell_core/reasoner.py packages/cell-core/tests/test_reasoner.py
git commit -m "feat(cell-core): tier-based reasoner framework with subprocess escalation"
```

---

### Task 9: pulse.py + conftest.py — The Lifecycle Runner

**Files:**
- Create: `packages/cell-core/cell_core/pulse.py`
- Create: `packages/cell-core/tests/conftest.py`
- Create: `packages/cell-core/tests/test_pulse.py`

- [ ] **Step 1: Write conftest.py with fakes**

Create `packages/cell-core/tests/conftest.py`:

```python
"""Shared fixtures — fake protocol implementations for testing."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from cell_core.types import (
    CellConfig, Episode, HomeostaticState, LearnedRule, Proposal, SensorReading,
)


class FakeSensor:
    def __init__(self, name: str = "fake", status: str = "green"):
        self.name = name
        self._status = status

    async def read(self, **ctx: Any) -> SensorReading:
        return SensorReading(sensor_name=self.name, status=self._status)


class FakeThinker:
    def __init__(self, action: str = "none", confidence: float = 1.0):
        self._action = action
        self._confidence = confidence
        self.call_count = 0

    async def think(self, readings, state, memory_context) -> Proposal:
        self.call_count += 1
        return Proposal(action=self._action, reason="fake", confidence=self._confidence, tier_used=0)


class FakeActor:
    def __init__(self, allowlist: set[str] | None = None):
        self._allowlist = allowlist or {"restart_service", "alert_human"}
        self.executed: list[str] = []

    async def act(self, proposal: Proposal) -> str:
        self.executed.append(proposal.action)
        return f"executed:{proposal.action}"

    def can_execute(self, action_name: str) -> bool:
        return action_name in self._allowlist


class FakeSTM:
    def __init__(self):
        self.stored: list[tuple[str, dict]] = []

    async def store(self, event_type: str, data: dict) -> None:
        self.stored.append((event_type, data))

    async def recent(self, event_type: str, limit: int) -> list[dict]:
        return [d for et, d in self.stored if et == event_type or not event_type][:limit]


class FakeLTM:
    def __init__(self):
        self.rules: list[LearnedRule] = []

    async def store_rule(self, rule: LearnedRule) -> None:
        self.rules.append(rule)

    async def load_rules(self, limit: int) -> list[LearnedRule]:
        return self.rules[:limit]

    async def condense(self, episodes: list[Episode]) -> list[LearnedRule]:
        if episodes:
            return [LearnedRule(rule_text="condensed rule", support_count=len(episodes))]
        return []


class FakeEpisodic:
    def __init__(self):
        self.episodes: list[Episode] = []
        self._next_id = 1

    async def store(self, episode: Episode) -> int:
        episode.id = self._next_id
        self._next_id += 1
        self.episodes.append(episode)
        return episode.id

    async def recall(self, situation: dict, limit: int) -> list[Episode]:
        return self.episodes[-limit:]

    async def recall_recent(self, hours: int, limit: int) -> list[Episode]:
        return self.episodes[-limit:]

    async def forget_weak(self, keep: int) -> int:
        if len(self.episodes) <= keep:
            return 0
        removed = len(self.episodes) - keep
        self.episodes = self.episodes[-keep:]
        return removed


@pytest.fixture
def cell_config():
    return CellConfig(
        name="test",
        dna_path="test_dna.json",
        birth_date=datetime.now(timezone.utc) - timedelta(days=50),
    )
```

- [ ] **Step 2: Write failing test for pulse**

Create `packages/cell-core/tests/test_pulse.py`:

```python
"""Tests for cell_core.pulse — the lifecycle runner."""
import pytest
from datetime import datetime, timedelta, timezone

from cell_core.types import CellConfig, PulseResult, SafetyCheckResult

from conftest import (
    FakeSensor, FakeThinker, FakeActor, FakeSTM, FakeLTM, FakeEpisodic,
)


def _make_pulse_loop(
    config=None,
    sensors=None,
    thinker=None,
    actor=None,
    safety_proceeds=True,
    **kwargs,
):
    from cell_core.pulse import PulseLoop
    from cell_core.lifecycle import Maturation
    from cell_core.safety import SafetyGate
    from cell_core.homeostasis import HomeostaticController

    if config is None:
        config = CellConfig(
            name="test", dna_path="test.json",
            birth_date=datetime.now(timezone.utc) - timedelta(days=50),
        )

    class FakeSafetyGate:
        async def check(self):
            return SafetyCheckResult(can_proceed=safety_proceeds)

    return PulseLoop(
        config=config,
        sensors=sensors or [FakeSensor()],
        thinker=thinker or FakeThinker(),
        actor=actor or FakeActor(),
        stm=kwargs.get("stm", FakeSTM()),
        ltm=kwargs.get("ltm", FakeLTM()),
        episodic=kwargs.get("episodic", FakeEpisodic()),
        lifecycle=Maturation(config.birth_date),
        safety=FakeSafetyGate(),
        homeostasis=HomeostaticController(config.sleep_hours),
    )


class TestPulseLoopLifecycle:
    @pytest.mark.asyncio
    async def test_single_pulse_returns_result(self):
        pl = _make_pulse_loop()
        result = await pl.single_pulse()
        assert isinstance(result, PulseResult)
        assert result.pulse_number == 1
        assert result.halted is False

    @pytest.mark.asyncio
    async def test_pulse_increments_count(self):
        pl = _make_pulse_loop()
        await pl.single_pulse()
        await pl.single_pulse()
        assert pl.pulse_count == 2

    @pytest.mark.asyncio
    async def test_halts_when_safety_fails(self):
        pl = _make_pulse_loop(safety_proceeds=False)
        result = await pl.single_pulse()
        assert result.halted is True

    @pytest.mark.asyncio
    async def test_sense_collects_all_sensors(self):
        sensors = [FakeSensor("a"), FakeSensor("b"), FakeSensor("c")]
        stm = FakeSTM()
        pl = _make_pulse_loop(sensors=sensors, stm=stm)
        await pl.single_pulse()
        event_types = {et for et, _ in stm.stored}
        assert event_types == {"a", "b", "c"}

    @pytest.mark.asyncio
    async def test_sensor_error_produces_red_reading(self):
        class BrokenSensor:
            name = "broken"
            async def read(self, **ctx):
                raise ConnectionError("down")

        pl = _make_pulse_loop(sensors=[BrokenSensor()])
        result = await pl.single_pulse()
        assert result.health_status == "red"

    @pytest.mark.asyncio
    async def test_think_not_called_when_green(self):
        thinker = FakeThinker()
        pl = _make_pulse_loop(thinker=thinker)
        await pl.single_pulse()
        assert thinker.call_count == 0

    @pytest.mark.asyncio
    async def test_think_called_when_red(self):
        thinker = FakeThinker(action="restart_service", confidence=0.9)
        pl = _make_pulse_loop(
            sensors=[FakeSensor(status="red")],
            thinker=thinker,
        )
        await pl.single_pulse()
        assert thinker.call_count == 1

    @pytest.mark.asyncio
    async def test_act_executed_when_proposed(self):
        actor = FakeActor()
        thinker = FakeThinker(action="restart_service", confidence=0.9)
        pl = _make_pulse_loop(
            sensors=[FakeSensor(status="red")],
            thinker=thinker,
            actor=actor,
        )
        result = await pl.single_pulse()
        assert "restart_service" in actor.executed
        assert result.action_taken is not None

    @pytest.mark.asyncio
    async def test_act_blocked_by_confidence_threshold(self):
        """Embrione phase (day 0) blocks all actions (threshold 1.1)."""
        actor = FakeActor()
        config = CellConfig(
            name="test", dna_path="test.json",
            birth_date=datetime.now(timezone.utc),  # age = 0 = embrione
        )
        pl = _make_pulse_loop(
            config=config,
            sensors=[FakeSensor(status="red")],
            thinker=FakeThinker(action="restart_service", confidence=0.9),
            actor=actor,
        )
        result = await pl.single_pulse()
        assert len(actor.executed) == 0  # embrione blocks actions

    @pytest.mark.asyncio
    async def test_act_blocked_by_allowlist(self):
        actor = FakeActor(allowlist={"alert_human"})
        thinker = FakeThinker(action="restart_service", confidence=0.9)
        pl = _make_pulse_loop(
            sensors=[FakeSensor(status="red")],
            thinker=thinker,
            actor=actor,
        )
        result = await pl.single_pulse()
        assert len(actor.executed) == 0

    @pytest.mark.asyncio
    async def test_reflect_stores_episode_on_action(self):
        episodic = FakeEpisodic()
        pl = _make_pulse_loop(
            sensors=[FakeSensor(status="red")],
            thinker=FakeThinker(action="restart_service", confidence=0.9),
            episodic=episodic,
        )
        await pl.single_pulse()
        assert len(episodic.episodes) >= 1

    @pytest.mark.asyncio
    async def test_reflect_skips_when_green_and_no_action(self):
        episodic = FakeEpisodic()
        pl = _make_pulse_loop(episodic=episodic)
        await pl.single_pulse()
        assert len(episodic.episodes) == 0

    @pytest.mark.asyncio
    async def test_recent_pulses_capped_at_50(self):
        pl = _make_pulse_loop()
        for _ in range(60):
            await pl.single_pulse()
        assert len(pl._recent_pulses) == 50

    @pytest.mark.asyncio
    async def test_on_pulse_callback(self):
        results = []
        async def on_pulse(result):
            results.append(result)

        from cell_core.pulse import PulseLoop
        from cell_core.lifecycle import Maturation
        from cell_core.homeostasis import HomeostaticController

        config = CellConfig(
            name="test", dna_path="test.json",
            birth_date=datetime.now(timezone.utc) - timedelta(days=50),
        )

        class FakeSafety:
            async def check(self):
                return SafetyCheckResult(can_proceed=True)

        pl = PulseLoop(
            config=config,
            sensors=[FakeSensor()],
            thinker=FakeThinker(),
            actor=FakeActor(),
            stm=FakeSTM(), ltm=FakeLTM(), episodic=FakeEpisodic(),
            lifecycle=Maturation(config.birth_date),
            safety=FakeSafety(),
            homeostasis=HomeostaticController(),
            on_pulse=on_pulse,
        )
        # Can't test run() (infinite loop), but single_pulse doesn't call on_pulse
        # on_pulse is called only in run()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd packages/cell-core && pytest tests/test_pulse.py -v`
Expected: FAIL

- [ ] **Step 4: Implement pulse.py**

Create `packages/cell-core/cell_core/pulse.py`:

```python
"""PulseLoop — the lifecycle runner.

Concrete class that orchestrates: sense→think→act→reflect→dream→mature.
Takes Protocol implementations via constructor injection.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from cell_core.homeostasis import HomeostaticController, TrendDetector
from cell_core.lifecycle import Maturation
from cell_core.protocols import Actor, EpisodicStore, LTMStore, Sensor, STMStore, Thinker
from cell_core.types import (
    CellConfig,
    Episode,
    HomeostaticState,
    Proposal,
    PulseResult,
    SensorReading,
)

logger = logging.getLogger("cell_core.pulse")


class PulseLoop:
    """The heartbeat. Orchestrates: sense→think→act→reflect→dream→mature."""

    def __init__(
        self,
        config: CellConfig,
        sensors: list[Sensor],
        thinker: Thinker,
        actor: Actor,
        stm: STMStore,
        ltm: LTMStore,
        episodic: EpisodicStore,
        lifecycle: Maturation,
        safety: Any,  # SafetyGate or any object with async check() -> SafetyCheckResult
        homeostasis: HomeostaticController | None = None,
        identity: Any | None = None,  # SelfModelManager
        on_pulse: Callable[[PulseResult], Awaitable[None]] | None = None,
    ) -> None:
        self.config = config
        self.sensors = sensors
        self.thinker = thinker
        self.actor = actor
        self.stm = stm
        self.ltm = ltm
        self.episodic = episodic
        self.lifecycle = lifecycle
        self.safety = safety
        self.homeostasis = homeostasis or HomeostaticController(config.sleep_hours)
        self.identity = identity
        self.on_pulse = on_pulse
        self.pulse_count: int = 0
        self._recent_pulses: list[dict[str, Any]] = []
        self._trend_detector = TrendDetector()

    async def run(self) -> None:
        """Infinite loop. Call this and the cell lives."""
        while True:
            result = await self.single_pulse()
            if self.on_pulse:
                await self.on_pulse(result)
            interval = self.homeostasis.recommended_pulse_interval()
            await asyncio.sleep(interval)

    async def single_pulse(self) -> PulseResult:
        """One complete lifecycle tick."""
        self.pulse_count += 1
        now = datetime.now(timezone.utc)

        # 0. SAFETY CHECK
        safety_result = await self.safety.check()
        if not safety_result.can_proceed:
            return PulseResult(
                timestamp=now,
                pulse_number=self.pulse_count,
                halted=True,
                halt_reason=safety_result.reason,
            )

        # 1. SENSE — collect all sensor readings
        readings: list[SensorReading] = []
        for sensor in self.sensors:
            try:
                reading = await sensor.read()
                readings.append(reading)
            except Exception as e:
                readings.append(SensorReading(
                    sensor_name=sensor.name,
                    status="red",
                    metadata={"error": str(e)},
                ))

        # 2. EVALUATE — fast homeostatic update
        worst_status = self._worst_status(readings)
        # Use a default response time for homeostasis when not available
        state = self.homeostasis.update(
            response_time_ms=100,  # default; organs can override via sensor metadata
            health_status=worst_status,
            hour_utc=now.hour,
        )
        trend = self._trend_detector.detect(self._recent_pulses)

        # Store in STM
        for reading in readings:
            await self.stm.store(reading.sensor_name, {
                "status": reading.status,
                "value": reading.value,
                "stress": state.stress_level,
                "energy": state.energy_level,
            })

        self._recent_pulses.append({
            "pulse": self.pulse_count,
            "health_status": worst_status,
            "stress": state.stress_level,
            "timestamp": now.isoformat(),
        })
        if len(self._recent_pulses) > 50:
            self._recent_pulses = self._recent_pulses[-50:]

        # 3. THINK — if needed
        proposal = Proposal(action="none", reason="stable", confidence=0.0, tier_used=-1)
        should_think = (
            worst_status != "green"
            or trend.monotonic_drift
            or trend.flapping
            or trend.sustained_degraded
        )
        if should_think and self.lifecycle.can_act():
            ltm_rules = await self.ltm.load_rules(limit=10)
            recent_episodes = await self.episodic.recall_recent(hours=24, limit=5)
            memory_context = {
                "ltm_rules": [r.rule_text for r in ltm_rules],
                "recent_episodes": [
                    {"action": e.action_taken, "outcome": e.outcome, "lesson": e.lesson}
                    for e in recent_episodes
                ],
            }
            proposal = await self.thinker.think(readings, state, memory_context)

        # 4. ACT — if approved
        action_taken = None
        if proposal.action != "none":
            threshold = self.lifecycle.action_confidence_threshold()
            if (
                proposal.confidence >= threshold
                and self.actor.can_execute(proposal.action)
            ):
                action_taken = await self.actor.act(proposal)

        # 5. REFLECT — store episode if significant
        if action_taken or worst_status != "green":
            emotion = self._derive_emotion(state)
            episode = Episode(
                situation={
                    "readings": [
                        {"sensor": r.sensor_name, "status": r.status}
                        for r in readings
                    ],
                    "stress": state.stress_level,
                    "energy": state.energy_level,
                },
                emotion=emotion,
                action_taken=proposal.action,
                outcome=action_taken or "no_action",
                lesson="",
            )
            await self.episodic.store(episode)

        # 6. DREAM — during sleep window
        if self.homeostasis.is_sleeping() and self.lifecycle.can_dream():
            recent = await self.episodic.recall_recent(hours=24, limit=50)
            if recent:
                new_rules = await self.ltm.condense(recent)
                for rule in new_rules:
                    await self.ltm.store_rule(rule)
                await self.episodic.forget_weak(keep=500)

        # 7. MATURE — lifecycle tick
        self.lifecycle.tick(self.pulse_count)

        # Update identity if present
        if self.identity:
            self.identity.record_pulse()
            if action_taken:
                self.identity.record_action(proposal.action)

        return PulseResult(
            timestamp=now,
            pulse_number=self.pulse_count,
            health_status=worst_status,
            action_taken=action_taken,
            action_reason=proposal.reason if action_taken else None,
            thought_tier=proposal.tier_used if should_think else None,
        )

    @staticmethod
    def _worst_status(readings: list[SensorReading]) -> str:
        rank = {"green": 0, "yellow": 1, "red": 2}
        if not readings:
            return "green"
        return max(readings, key=lambda r: rank.get(r.status, 0)).status

    @staticmethod
    def _derive_emotion(state: HomeostaticState) -> str:
        if state.stress_level > 0.8:
            return "panic"
        if state.stress_level > 0.5:
            return "stressed"
        if state.stress_level > 0.2:
            return "alert"
        return "calm"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd packages/cell-core && pytest tests/test_pulse.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add packages/cell-core/cell_core/pulse.py packages/cell-core/tests/conftest.py packages/cell-core/tests/test_pulse.py
git commit -m "feat(cell-core): PulseLoop lifecycle runner with full test coverage"
```

---

### Task 10: __init__.py exports + full test suite run

**Files:**
- Modify: `packages/cell-core/cell_core/__init__.py`

- [ ] **Step 1: Update __init__.py with public API**

Edit `packages/cell-core/cell_core/__init__.py`:

```python
"""cell-core — Biological lifecycle engine for Nuzantara agents."""
from cell_core.homeostasis import HomeostaticController, TrendDetector, TrendResult
from cell_core.identity import SelfModel, SelfModelManager
from cell_core.lifecycle import Maturation
from cell_core.protocols import Actor, EpisodicStore, LTMStore, Sensor, STMStore, Thinker
from cell_core.pulse import PulseLoop
from cell_core.reasoner import ReasonerFramework, TierConfig
from cell_core.safety import DNAInterpreter, DNAIntegrityError, DNALoader, SafetyGate
from cell_core.types import (
    CellConfig,
    DNAConfig,
    DNARule,
    Episode,
    HomeostaticState,
    LearnedRule,
    Phase,
    Proposal,
    PulseResult,
    SafetyCheckResult,
    SensorReading,
)

__all__ = [
    # Types
    "CellConfig", "DNAConfig", "DNARule", "Episode", "HomeostaticState",
    "LearnedRule", "Phase", "Proposal", "PulseResult", "SafetyCheckResult",
    "SensorReading",
    # Protocols
    "Actor", "EpisodicStore", "LTMStore", "Sensor", "STMStore", "Thinker",
    # Core
    "PulseLoop", "Maturation", "HomeostaticController", "TrendDetector", "TrendResult",
    # Safety
    "SafetyGate", "DNALoader", "DNAInterpreter", "DNAIntegrityError",
    # Identity
    "SelfModel", "SelfModelManager",
    # Reasoner
    "ReasonerFramework", "TierConfig",
]
```

- [ ] **Step 2: Run full test suite**

Run: `cd packages/cell-core && pytest tests/ -v --tb=short`
Expected: All tests PASS

- [ ] **Step 3: Run with coverage**

Run: `cd packages/cell-core && pip install pytest-cov && pytest tests/ --cov=cell_core --cov-report=term-missing`
Expected: >90% coverage

- [ ] **Step 4: Commit**

```bash
git add packages/cell-core/cell_core/__init__.py
git commit -m "feat(cell-core): public API exports, all tests passing"
```

---

### Task 11: Update SYMBIOSIS.md + final verification

**Files:**
- Modify: `SYMBIOSIS.md`

- [ ] **Step 1: Read current SYMBIOSIS.md to find insertion point**

Run: `head -80 ~/Desktop/nuzantara/SYMBIOSIS.md`

- [ ] **Step 2: Add L0 Cellular layer**

Add the following section to SYMBIOSIS.md after the Condivisione/Sharing section (L1):

```markdown
### L0 Cellular — cell-core

Every organ is a differentiated cell. `packages/cell-core/` provides:
- **PulseLoop** — concrete lifecycle runner (sense→think→act→reflect→dream→mature)
- **Memory stack** — STM/LTM/Episodic protocols with SQLite default + PostgreSQL optional
- **Lifecycle** — Maturation phases (embrione→neonato→giovane→adulto→anziano)
- **Safety** — DNA integrity + kill switches + budget validation
- **Homeostasis** — stress/energy/arousal governor + trend detection
- **Identity** — SelfModel persistence across restarts

Organs implement: `Sensor`, `Thinker`, `Actor` protocols.
Communication between organs: L1 (Redis Streams) unchanged.
```

- [ ] **Step 3: Run full test suite one final time**

Run: `cd packages/cell-core && pytest tests/ -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add SYMBIOSIS.md
git commit -m "docs: add L0 Cellular layer to SYMBIOSIS.md for cell-core package"
```

- [ ] **Step 5: Verify package installs cleanly**

Run: `cd packages/cell-core && pip install -e ".[dev]" && python -c "from cell_core import PulseLoop, Maturation, SqliteMemoryStack; print('cell-core OK')"`

Note: `SqliteMemoryStack` is not in `__init__.py` — import directly:
Run: `python -c "from cell_core.memory_sqlite import SqliteMemoryStack; print('SQLite OK')"`
Expected: Both print OK
