# CELL Fase 1 — Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give CELL its first three "alive" properties — adaptive homeostasis, episodic memory, and a persistent self-model — so it transitions from a reactive automaton to the foundations of a living organism.

**Architecture:** Three new modules plug into the existing pulse loop. The HomeostatiController runs in the FAST layer (no LLM, <5ms) and modulates pulse interval + stress state. EpisodicMemory stores significant events in PostgreSQL with ACT-R activation-based retrieval. SelfModel tracks lifetime counters, sensor reliability scores, and learned preferences in a JSON file that persists across restarts.

**Tech Stack:** Python 3.11, asyncpg (PostgreSQL), dataclasses, math (EMA/ACT-R), JSON file persistence. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-04-03-cell-vivente-autonomo-roadmap.md` (sections 3.1, 3.2, 3.5)

**Codebase:** `apps/cell/` — working directory for all file paths below.

---

## File Structure

| Action | File                                  | Responsibility                                                                                                         |
| ------ | ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Create | `cell/fast/homeostatic_controller.py` | HomeostaticState dataclass + HomeostaticController class — adaptive setpoints, stress/energy/arousal, circadian rhythm |
| Create | `cell/memory/episodic.py`             | Episode dataclass + EpisodicMemory class — store/retrieve/forget episodes with ACT-R activation                        |
| Create | `cell/identity/__init__.py`           | Package init                                                                                                           |
| Create | `cell/identity/self_model.py`         | SelfModel dataclass + SelfModelManager — lifetime counters, sensor reliability, preferences, JSON persistence          |
| Modify | `cell/core/pulse.py`                  | Inject homeostatic state update + episode recording + self-model update into each pulse                                |
| Modify | `cell/main.py`                        | Initialize HomeostaticController + EpisodicMemory + SelfModelManager at bootstrap, pass to PulseEngine                 |
| Create | `tests/test_homeostasis.py`           | Unit tests for homeostatic controller                                                                                  |
| Create | `tests/test_episodic.py`              | Unit tests for episodic memory                                                                                         |
| Create | `tests/test_self_model.py`            | Unit tests for self-model                                                                                              |

---

## Task 1: Homeostatic Controller

**Files:**

- Create: `cell/fast/homeostatic_controller.py`
- Test: `tests/test_homeostasis.py`

### Step 1: Write the failing tests

- [ ] **Step 1a: Create test file with core tests**

```python
# tests/test_homeostasis.py
"""Tests for the homeostatic controller — CELL's body regulation."""
import math
import pytest
from cell.fast.homeostatic_controller import HomeostaticState, HomeostaticController


class TestHomeostaticState:
    def test_initial_state_is_calm(self) -> None:
        state = HomeostaticState()
        assert state.stress_level == 0.0
        assert state.energy_level == 1.0
        assert state.arousal == 0.5
        assert state.circadian_phase == "awake"

    def test_stress_clamped_0_1(self) -> None:
        state = HomeostaticState(stress_level=1.5)
        assert state.stress_level == 1.0
        state2 = HomeostaticState(stress_level=-0.3)
        assert state2.stress_level == 0.0


class TestHomeostaticController:
    def test_setpoint_adapts_to_readings(self) -> None:
        ctrl = HomeostaticController()
        # Feed 10 pulses at 200ms — setpoint should move toward 200
        for _ in range(10):
            ctrl.update(response_time_ms=200, health_status="green")
        assert 180 < ctrl.state.setpoint_rt_ms < 220

    def test_stress_rises_outside_comfort_zone(self) -> None:
        ctrl = HomeostaticController()
        # Establish baseline at 100ms
        for _ in range(20):
            ctrl.update(response_time_ms=100, health_status="green")
        baseline_stress = ctrl.state.stress_level
        # Spike to 5000ms — stress should rise
        ctrl.update(response_time_ms=5000, health_status="red")
        assert ctrl.state.stress_level > baseline_stress

    def test_stress_decays_when_stable(self) -> None:
        ctrl = HomeostaticController()
        # Create stress
        for _ in range(5):
            ctrl.update(response_time_ms=5000, health_status="red")
        high_stress = ctrl.state.stress_level
        # Return to normal — stress should decay
        for _ in range(20):
            ctrl.update(response_time_ms=100, health_status="green")
        assert ctrl.state.stress_level < high_stress

    def test_energy_drains_with_actions(self) -> None:
        ctrl = HomeostaticController()
        initial_energy = ctrl.state.energy_level
        ctrl.record_action_cost(0.1)
        assert ctrl.state.energy_level < initial_energy

    def test_energy_recovers_during_green(self) -> None:
        ctrl = HomeostaticController()
        ctrl.record_action_cost(0.5)  # drain energy
        low_energy = ctrl.state.energy_level
        for _ in range(10):
            ctrl.update(response_time_ms=100, health_status="green")
        assert ctrl.state.energy_level > low_energy

    def test_circadian_phase_asleep(self) -> None:
        ctrl = HomeostaticController(sleep_hours=(2, 6))  # UTC
        ctrl.update(response_time_ms=100, health_status="green", hour_utc=3)
        assert ctrl.state.circadian_phase == "asleep"

    def test_circadian_phase_awake(self) -> None:
        ctrl = HomeostaticController(sleep_hours=(2, 6))
        ctrl.update(response_time_ms=100, health_status="green", hour_utc=10)
        assert ctrl.state.circadian_phase == "awake"

    def test_circadian_phase_drowsy(self) -> None:
        ctrl = HomeostaticController(sleep_hours=(2, 6))
        # Hour 1 = 1 hour before sleep start → drowsy
        ctrl.update(response_time_ms=100, health_status="green", hour_utc=1)
        assert ctrl.state.circadian_phase == "drowsy"

    def test_recommended_interval_increases_when_asleep(self) -> None:
        ctrl = HomeostaticController(sleep_hours=(2, 6))
        ctrl.update(response_time_ms=100, health_status="green", hour_utc=3)
        interval = ctrl.recommended_pulse_interval()
        assert interval >= 120  # at least 2 minutes when asleep

    def test_recommended_interval_decreases_under_stress(self) -> None:
        ctrl = HomeostaticController()
        ctrl.update(response_time_ms=100, health_status="green", hour_utc=10)
        calm_interval = ctrl.recommended_pulse_interval()
        for _ in range(5):
            ctrl.update(response_time_ms=5000, health_status="red", hour_utc=10)
        stressed_interval = ctrl.recommended_pulse_interval()
        assert stressed_interval < calm_interval

    def test_comfort_zone_widens_with_variance(self) -> None:
        ctrl = HomeostaticController()
        # Low variance readings
        for _ in range(20):
            ctrl.update(response_time_ms=100, health_status="green")
        narrow_zone = ctrl.state.comfort_zone
        # High variance readings
        ctrl2 = HomeostaticController()
        readings = [50, 200, 80, 300, 100, 400, 150, 500]
        for rt in readings * 3:
            ctrl2.update(response_time_ms=rt, health_status="green")
        wide_zone = ctrl2.state.comfort_zone
        assert (wide_zone[1] - wide_zone[0]) > (narrow_zone[1] - narrow_zone[0])
```

- [ ] **Step 1b: Run tests to verify they fail**

Run: `cd /Users/nuzantara/Desktop/nuzantara/apps/cell && python -m pytest tests/test_homeostasis.py -v --tb=short 2>&1 | head -30`

Expected: `ModuleNotFoundError: No module named 'cell.fast.homeostatic_controller'`

### Step 2: Implement the homeostatic controller

- [ ] **Step 2a: Create `cell/fast/homeostatic_controller.py`**

```python
# cell/fast/homeostatic_controller.py
"""Homeostatic Controller — CELL's body regulation.

Adaptive setpoints via exponential moving average.
Stress/energy/arousal as continuous 0-1 variables.
Circadian rhythm: awake → drowsy → asleep cycle.

Inspired by Bio-RegNet (Bayesian homeostatic framework).
Runs in FAST layer: no LLM, no network, <1ms per update.
"""
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger("cell.homeostasis")

# EMA smoothing factor — 0.1 means ~10-pulse memory
_EMA_ALPHA = 0.1
# Stress decay per green pulse
_STRESS_DECAY = 0.05
# Stress rise per non-green pulse (scaled by deviation)
_STRESS_RISE_BASE = 0.15
# Energy recovery per green pulse
_ENERGY_RECOVERY = 0.02
# Arousal decay toward baseline (0.5) per pulse
_AROUSAL_DECAY = 0.03


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass
class HomeostaticState:
    """The organism's internal physiological state."""
    stress_level: float = 0.0
    energy_level: float = 1.0
    arousal: float = 0.5
    comfort_zone: tuple[float, float] = (50.0, 200.0)
    setpoint_rt_ms: float = 100.0
    circadian_phase: str = "awake"  # "awake" | "drowsy" | "asleep"

    def __post_init__(self) -> None:
        self.stress_level = _clamp(self.stress_level)
        self.energy_level = _clamp(self.energy_level)
        self.arousal = _clamp(self.arousal)


class HomeostaticController:
    """Maintains CELL's internal equilibrium.

    Called once per pulse with the latest sensor readings.
    Outputs: updated HomeostaticState + recommended pulse interval.
    """

    def __init__(self, sleep_hours: tuple[int, int] = (2, 6)) -> None:
        """
        Args:
            sleep_hours: (start_hour_utc, end_hour_utc) for circadian sleep.
                         Default 2-6 UTC = 10:00-14:00 WITA (low traffic).
        """
        self.state = HomeostaticState()
        self._sleep_start = sleep_hours[0]
        self._sleep_end = sleep_hours[1]
        self._rt_history: list[float] = []
        self._max_history = 100

    def update(
        self,
        response_time_ms: int,
        health_status: str,
        hour_utc: int | None = None,
    ) -> HomeostaticState:
        """Process one pulse reading and update internal state.

        Args:
            response_time_ms: Backend response time in milliseconds.
            health_status: "green", "yellow", or "red".
            hour_utc: Current hour in UTC (0-23). If None, uses system clock.

        Returns:
            Updated HomeostaticState.
        """
        rt = float(response_time_ms)

        # Track history for variance calculation
        self._rt_history.append(rt)
        if len(self._rt_history) > self._max_history:
            self._rt_history = self._rt_history[-self._max_history:]

        # 1. Update setpoint (EMA)
        self.state.setpoint_rt_ms = (
            _EMA_ALPHA * rt + (1 - _EMA_ALPHA) * self.state.setpoint_rt_ms
        )

        # 2. Update comfort zone (setpoint ± 1 sigma)
        if len(self._rt_history) >= 5:
            mean = sum(self._rt_history) / len(self._rt_history)
            variance = sum((x - mean) ** 2 for x in self._rt_history) / len(self._rt_history)
            sigma = math.sqrt(variance) if variance > 0 else 25.0
            sigma = max(sigma, 25.0)  # floor at 25ms to avoid overly tight zone
            self.state.comfort_zone = (
                max(0.0, self.state.setpoint_rt_ms - sigma),
                self.state.setpoint_rt_ms + sigma,
            )

        # 3. Update stress
        low, high = self.state.comfort_zone
        if rt < low or rt > high:
            # Outside comfort zone — stress rises proportionally to deviation
            if rt > high:
                deviation = (rt - high) / max(high, 1.0)
            else:
                deviation = (low - rt) / max(low, 1.0)
            rise = _STRESS_RISE_BASE * min(deviation, 2.0)
            self.state.stress_level = _clamp(self.state.stress_level + rise)
        else:
            # Inside comfort zone — stress decays
            self.state.stress_level = _clamp(self.state.stress_level - _STRESS_DECAY)

        # Non-green status adds stress regardless of RT
        if health_status != "green":
            bump = 0.1 if health_status == "yellow" else 0.25
            self.state.stress_level = _clamp(self.state.stress_level + bump)

        # 4. Update energy (recovers during green, stable otherwise)
        if health_status == "green":
            self.state.energy_level = _clamp(self.state.energy_level + _ENERGY_RECOVERY)

        # 5. Update arousal (trends toward 0.5 baseline, stress pushes up)
        target_arousal = 0.5 + self.state.stress_level * 0.4
        diff = target_arousal - self.state.arousal
        self.state.arousal = _clamp(self.state.arousal + diff * _AROUSAL_DECAY * 3)

        # 6. Circadian phase
        if hour_utc is None:
            hour_utc = datetime.now(timezone.utc).hour

        if self._sleep_start <= hour_utc < self._sleep_end:
            self.state.circadian_phase = "asleep"
        elif hour_utc == (self._sleep_start - 1) % 24:
            self.state.circadian_phase = "drowsy"
        elif hour_utc == self._sleep_end:
            self.state.circadian_phase = "drowsy"
        else:
            self.state.circadian_phase = "awake"

        logger.debug(
            f"Homeostasis: stress={self.state.stress_level:.2f} "
            f"energy={self.state.energy_level:.2f} "
            f"arousal={self.state.arousal:.2f} "
            f"phase={self.state.circadian_phase} "
            f"setpoint={self.state.setpoint_rt_ms:.0f}ms "
            f"zone={self.state.comfort_zone[0]:.0f}-{self.state.comfort_zone[1]:.0f}ms"
        )

        return self.state

    def record_action_cost(self, cost: float) -> None:
        """Drain energy when an action is taken.

        Args:
            cost: Energy cost 0.0-1.0 (e.g., LLM call = 0.1, restart = 0.2).
        """
        self.state.energy_level = _clamp(self.state.energy_level - cost)

    def recommended_pulse_interval(self) -> int:
        """Calculate recommended pulse interval in seconds.

        - Asleep: 300s (5 min) — conserve energy
        - Drowsy: 120s (2 min)
        - Awake + stressed: 15s (fast response)
        - Awake + calm: 60s (normal)

        Returns:
            Seconds between pulses.
        """
        phase = self.state.circadian_phase
        stress = self.state.stress_level

        if phase == "asleep":
            return 300
        if phase == "drowsy":
            return 120

        # Awake: interpolate between 15s (max stress) and 60s (no stress)
        # stress=0 → 60s, stress=1 → 15s
        interval = int(60 - stress * 45)
        return max(15, min(60, interval))

    def is_sleeping(self) -> bool:
        """True if CELL is in sleep phase (for dreamer/consolidation)."""
        return self.state.circadian_phase == "asleep"

    def to_dict(self) -> dict:
        """Serialize state for STM/logging."""
        return {
            "stress_level": round(self.state.stress_level, 3),
            "energy_level": round(self.state.energy_level, 3),
            "arousal": round(self.state.arousal, 3),
            "comfort_zone_low": round(self.state.comfort_zone[0], 1),
            "comfort_zone_high": round(self.state.comfort_zone[1], 1),
            "setpoint_rt_ms": round(self.state.setpoint_rt_ms, 1),
            "circadian_phase": self.state.circadian_phase,
        }
```

- [ ] **Step 2b: Run tests to verify they pass**

Run: `cd /Users/nuzantara/Desktop/nuzantara/apps/cell && python -m pytest tests/test_homeostasis.py -v`

Expected: All 11 tests PASS

- [ ] **Step 2c: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/cell
git add cell/fast/homeostatic_controller.py tests/test_homeostasis.py
git commit -m "feat(cell): add homeostatic controller with adaptive setpoints and circadian rhythm

Bio-RegNet inspired: EMA setpoints, comfort zone ±1σ, stress/energy/arousal 0-1,
circadian sleep phase (2-6 UTC). FAST layer, no LLM, <1ms per update."
```

---

## Task 2: Episodic Memory

**Files:**

- Create: `cell/memory/episodic.py`
- Modify: `cell/core/db.py` (add `cell_episodes` table creation)
- Test: `tests/test_episodic.py`

### Step 1: Write the failing tests

- [ ] **Step 1a: Create test file**

```python
# tests/test_episodic.py
"""Tests for episodic memory — CELL remembers moments, not statistics."""
import time
import math
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from cell.memory.episodic import Episode, EpisodicMemory


@pytest.fixture
def mock_pool() -> AsyncMock:
    pool = AsyncMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)
    return pool


class TestEpisode:
    def test_episode_creation(self) -> None:
        ep = Episode(
            situation={"health": "red", "rt_ms": 5000},
            emotion="stressed",
            action_taken="restart_service",
            outcome="success",
            lesson="High RT resolved by restart",
        )
        assert ep.emotion == "stressed"
        assert ep.activation > 0

    def test_activation_decays_with_age(self) -> None:
        old_ep = Episode(
            situation={},
            emotion="calm",
            action_taken="none",
            outcome="success",
            lesson="All green",
            timestamp=time.time() - 86400 * 7,  # 7 days ago
        )
        new_ep = Episode(
            situation={},
            emotion="calm",
            action_taken="none",
            outcome="success",
            lesson="All green",
            timestamp=time.time(),
        )
        assert new_ep.compute_activation() > old_ep.compute_activation()

    def test_emotion_must_be_valid(self) -> None:
        with pytest.raises(ValueError):
            Episode(
                situation={},
                emotion="happy",  # not a valid emotion
                action_taken="none",
                outcome="success",
                lesson="test",
            )


class TestEpisodicMemory:
    @pytest.mark.asyncio
    async def test_store_episode(self, mock_pool: AsyncMock) -> None:
        mem = EpisodicMemory(pool=mock_pool, max_episodes=1000)
        ep = Episode(
            situation={"health": "red"},
            emotion="alert",
            action_taken="read_logs",
            outcome="success",
            lesson="Logs showed OOM",
        )
        await mem.store(ep)
        conn = await mock_pool.acquire().__aenter__()
        conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_recall_returns_most_activated(self, mock_pool: AsyncMock) -> None:
        mem = EpisodicMemory(pool=mock_pool, max_episodes=1000)
        # Simulate DB returning 2 episodes
        conn = await mock_pool.acquire().__aenter__()
        now = time.time()
        conn.fetch.return_value = [
            {
                "id": 1, "timestamp": now - 86400, "situation": '{"health":"red"}',
                "emotion": "stressed", "action_taken": "restart_service",
                "outcome": "success", "lesson": "restart fixed it",
                "recall_count": 5,
            },
            {
                "id": 2, "timestamp": now - 3600, "situation": '{"health":"red"}',
                "emotion": "alert", "action_taken": "read_logs",
                "outcome": "partial", "lesson": "logs unclear",
                "recall_count": 1,
            },
        ]
        episodes = await mem.recall(situation={"health": "red"}, limit=2)
        assert len(episodes) <= 2
        # Most recent OR most recalled should rank higher
        assert episodes[0].id in (1, 2)

    @pytest.mark.asyncio
    async def test_forget_below_threshold(self, mock_pool: AsyncMock) -> None:
        mem = EpisodicMemory(pool=mock_pool, max_episodes=10)
        conn = await mock_pool.acquire().__aenter__()
        conn.fetchval.return_value = 15  # more than max
        await mem.forget_weak()
        # Should have called DELETE
        assert conn.execute.call_count >= 1

    @pytest.mark.asyncio
    async def test_should_record_filters_green(self) -> None:
        mem = EpisodicMemory(pool=AsyncMock(), max_episodes=1000)
        # Green with no action → not worth recording
        assert not mem.should_record(health_status="green", action_taken=None)
        # Red → always record
        assert mem.should_record(health_status="red", action_taken=None)
        # Green with action → record
        assert mem.should_record(health_status="green", action_taken="read_logs")

    @pytest.mark.asyncio
    async def test_episode_count(self, mock_pool: AsyncMock) -> None:
        mem = EpisodicMemory(pool=mock_pool, max_episodes=1000)
        conn = await mock_pool.acquire().__aenter__()
        conn.fetchval.return_value = 42
        count = await mem.count()
        assert count == 42
```

- [ ] **Step 1b: Run tests to verify they fail**

Run: `cd /Users/nuzantara/Desktop/nuzantara/apps/cell && python -m pytest tests/test_episodic.py -v --tb=short 2>&1 | head -20`

Expected: `ModuleNotFoundError: No module named 'cell.memory.episodic'`

### Step 2: Add `cell_episodes` table creation to db.py

- [ ] **Step 2a: Add `create_episodes_table` function to `cell/core/db.py`**

Append after the existing `log_alert` function (end of file):

```python
async def create_episodes_table() -> None:
    """Create cell_episodes table for episodic memory."""
    try:
        pool = await get_pool()
        await pool.execute("""
            CREATE TABLE IF NOT EXISTS cell_episodes (
                id              SERIAL PRIMARY KEY,
                timestamp       DOUBLE PRECISION NOT NULL,
                situation       JSONB NOT NULL,
                emotion         VARCHAR(16) NOT NULL,
                action_taken    VARCHAR(64) NOT NULL,
                outcome         VARCHAR(16) NOT NULL,
                lesson          TEXT NOT NULL,
                recall_count    INTEGER NOT NULL DEFAULT 0,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await pool.execute("""
            CREATE INDEX IF NOT EXISTS idx_cell_episodes_timestamp
            ON cell_episodes (timestamp DESC)
        """)
        await pool.execute("""
            CREATE INDEX IF NOT EXISTS idx_cell_episodes_emotion
            ON cell_episodes (emotion)
        """)
        logger.info("cell_episodes table ready.")
    except Exception as e:
        logger.error(f"Failed to create cell_episodes table: {e}")
```

### Step 3: Implement episodic memory

- [ ] **Step 3a: Create `cell/memory/episodic.py`**

```python
# cell/memory/episodic.py
"""Episodic Memory — CELL remembers moments, not statistics.

Each significant event becomes an Episode with emotion, outcome, and lesson.
Retrieval uses ACT-R activation: log(recency) + frequency_bonus + similarity.
Max episodes enforced via forget_weak() — drops lowest activation.

Inspired by MemGPT (OS-inspired paging) + ACT-R (activation-based retrieval).
"""
import json
import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("cell.memory.episodic")

VALID_EMOTIONS = ("calm", "alert", "stressed", "panic")
VALID_OUTCOMES = ("success", "partial", "failure")

# ACT-R activation parameters
_RECENCY_WEIGHT = 1.0
_FREQUENCY_WEIGHT = 0.5
_BASE_ACTIVATION = 0.5


@dataclass
class Episode:
    """A single episodic memory — a moment CELL experienced."""
    situation: dict[str, Any]
    emotion: str
    action_taken: str
    outcome: str
    lesson: str
    id: int = 0
    timestamp: float = 0.0
    recall_count: int = 0
    activation: float = 0.0

    def __post_init__(self) -> None:
        if self.emotion not in VALID_EMOTIONS:
            raise ValueError(f"emotion must be one of {VALID_EMOTIONS}, got '{self.emotion}'")
        if self.outcome not in VALID_OUTCOMES:
            raise ValueError(f"outcome must be one of {VALID_OUTCOMES}, got '{self.outcome}'")
        if self.timestamp == 0.0:
            self.timestamp = time.time()
        self.activation = self.compute_activation()

    def compute_activation(self) -> float:
        """ACT-R activation: base + log(recency_days) + frequency_bonus.

        Recent + frequently-recalled episodes have higher activation.
        """
        age_seconds = max(time.time() - self.timestamp, 1.0)
        age_days = age_seconds / 86400.0
        recency = _RECENCY_WEIGHT * (1.0 / (1.0 + math.log1p(age_days)))
        frequency = _FREQUENCY_WEIGHT * math.log1p(self.recall_count)
        return _BASE_ACTIVATION + recency + frequency


class EpisodicMemory:
    """Manages episodic storage and retrieval in PostgreSQL."""

    def __init__(self, pool: Any, max_episodes: int = 1000) -> None:
        self._pool = pool
        self._max_episodes = max_episodes

    def should_record(self, health_status: str, action_taken: str | None) -> bool:
        """Decide if this pulse is worth recording as an episode.

        Record when: non-green status, action was taken, or anomaly detected.
        Skip: routine green pulses with no action.
        """
        if health_status != "green":
            return True
        if action_taken is not None:
            return True
        return False

    async def store(self, episode: Episode) -> None:
        """Persist an episode to PostgreSQL."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO cell_episodes
                   (timestamp, situation, emotion, action_taken, outcome, lesson, recall_count)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                episode.timestamp,
                json.dumps(episode.situation),
                episode.emotion,
                episode.action_taken,
                episode.outcome,
                episode.lesson,
                episode.recall_count,
            )
        logger.info(f"Episode stored: emotion={episode.emotion} action={episode.action_taken} outcome={episode.outcome}")

    async def recall(self, situation: dict[str, Any], limit: int = 5) -> list[Episode]:
        """Retrieve the most relevant episodes for a given situation.

        Retrieves recent episodes and ranks by ACT-R activation.
        Increments recall_count for retrieved episodes (strengthens memory).
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, timestamp, situation, emotion, action_taken,
                          outcome, lesson, recall_count
                   FROM cell_episodes
                   ORDER BY timestamp DESC
                   LIMIT $1""",
                limit * 3,  # fetch extra, then rank by activation
            )

        if not rows:
            return []

        episodes = []
        for row in rows:
            sit = row["situation"]
            if isinstance(sit, str):
                sit = json.loads(sit)
            ep = Episode(
                id=row["id"],
                timestamp=float(row["timestamp"]),
                situation=sit,
                emotion=row["emotion"],
                action_taken=row["action_taken"],
                outcome=row["outcome"],
                lesson=row["lesson"],
                recall_count=row["recall_count"],
            )
            episodes.append(ep)

        # Sort by activation (highest first) and take top N
        episodes.sort(key=lambda e: e.activation, reverse=True)
        top = episodes[:limit]

        # Increment recall_count for retrieved episodes (fire-and-forget)
        if top:
            try:
                async with self._pool.acquire() as conn:
                    ids = [e.id for e in top if e.id > 0]
                    if ids:
                        await conn.execute(
                            "UPDATE cell_episodes SET recall_count = recall_count + 1 WHERE id = ANY($1::int[])",
                            ids,
                        )
            except Exception as e:
                logger.debug(f"Failed to update recall_count: {e}")

        return top

    async def count(self) -> int:
        """Count total episodes in storage."""
        async with self._pool.acquire() as conn:
            return await conn.fetchval("SELECT COUNT(*) FROM cell_episodes") or 0

    async def forget_weak(self) -> int:
        """Remove episodes with lowest activation when over capacity.

        Returns number of episodes deleted.
        """
        async with self._pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM cell_episodes") or 0

        if total <= self._max_episodes:
            return 0

        to_delete = total - self._max_episodes

        # Delete oldest with lowest recall_count (proxy for low activation)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """DELETE FROM cell_episodes
                   WHERE id IN (
                       SELECT id FROM cell_episodes
                       ORDER BY recall_count ASC, timestamp ASC
                       LIMIT $1
                   )""",
                to_delete,
            )

        logger.info(f"Episodic forgetting: deleted {to_delete} weak episodes (was {total}, max {self._max_episodes})")
        return to_delete

    async def recent_lessons(self, limit: int = 5) -> list[str]:
        """Get recent lessons for context injection into reasoner."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT lesson, emotion, action_taken, outcome
                   FROM cell_episodes
                   ORDER BY timestamp DESC
                   LIMIT $1""",
                limit,
            )
        return [
            f"[{r['emotion']}] {r['action_taken']} → {r['outcome']}: {r['lesson']}"
            for r in rows
        ]

    def format_for_prompt(self, episodes: list[Episode]) -> str:
        """Format episodes as compact context for LLM injection."""
        if not episodes:
            return ""
        lines = ["EPISODIC MEMORY (past experiences):"]
        for ep in episodes[:5]:
            lines.append(
                f"  - [{ep.emotion}] {ep.action_taken} → {ep.outcome}: {ep.lesson}"
            )
        return "\n".join(lines)
```

- [ ] **Step 3b: Run tests to verify they pass**

Run: `cd /Users/nuzantara/Desktop/nuzantara/apps/cell && python -m pytest tests/test_episodic.py -v`

Expected: All 6 tests PASS

- [ ] **Step 3c: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/cell
git add cell/memory/episodic.py cell/core/db.py tests/test_episodic.py
git commit -m "feat(cell): add episodic memory with ACT-R activation retrieval

Episodes store situation/emotion/action/outcome/lesson.
Activation = base + log(recency) + frequency_bonus.
PostgreSQL cell_episodes table with forgetting when >1000 episodes."
```

---

## Task 3: Self-Model

**Files:**

- Create: `cell/identity/__init__.py`
- Create: `cell/identity/self_model.py`
- Test: `tests/test_self_model.py`

### Step 1: Write the failing tests

- [ ] **Step 1a: Create test file**

```python
# tests/test_self_model.py
"""Tests for CELL's self-model — persistent identity across restarts."""
import json
import os
import tempfile
import pytest
from cell.identity.self_model import SelfModel, SelfModelManager


class TestSelfModel:
    def test_default_model(self) -> None:
        model = SelfModel()
        assert model.age_days == 0
        assert model.total_pulses == 0
        assert model.total_actions == 0
        assert model.capabilities == {}
        assert model.preferences == []
        assert model.weaknesses == []

    def test_record_pulse_increments_counter(self) -> None:
        model = SelfModel()
        model.total_pulses += 1
        assert model.total_pulses == 1

    def test_serialization_roundtrip(self) -> None:
        model = SelfModel(
            capabilities={"health_sensor": 0.95, "ollama_sensor": 0.7},
            preferences=["restart before scale_up"],
            weaknesses=["slow to detect flapping"],
            total_pulses=1000,
            total_actions=42,
            age_days=7,
        )
        data = model.to_dict()
        restored = SelfModel.from_dict(data)
        assert restored.capabilities == model.capabilities
        assert restored.preferences == model.preferences
        assert restored.weaknesses == model.weaknesses
        assert restored.total_pulses == 1000
        assert restored.age_days == 7


class TestSelfModelManager:
    def test_save_and_load(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            mgr = SelfModelManager(path=path)
            mgr.model.total_pulses = 500
            mgr.model.capabilities["health_sensor"] = 0.99
            mgr.save()

            mgr2 = SelfModelManager(path=path)
            mgr2.load()
            assert mgr2.model.total_pulses == 500
            assert mgr2.model.capabilities["health_sensor"] == 0.99
        finally:
            os.unlink(path)

    def test_load_missing_file_creates_default(self) -> None:
        mgr = SelfModelManager(path="/tmp/cell_self_model_nonexistent_test.json")
        mgr.load()
        assert mgr.model.total_pulses == 0

    def test_update_sensor_reliability(self) -> None:
        mgr = SelfModelManager(path="/dev/null")
        mgr.update_sensor_reliability("health_sensor", success=True)
        mgr.update_sensor_reliability("health_sensor", success=True)
        mgr.update_sensor_reliability("health_sensor", success=False)
        # 2 success / 3 total ≈ 0.667
        assert 0.5 < mgr.model.capabilities["health_sensor"] < 0.8

    def test_add_preference_no_duplicates(self) -> None:
        mgr = SelfModelManager(path="/dev/null")
        mgr.add_preference("restart before scale_up")
        mgr.add_preference("restart before scale_up")
        assert mgr.model.preferences.count("restart before scale_up") == 1

    def test_record_pulse_updates_age(self) -> None:
        mgr = SelfModelManager(path="/dev/null")
        mgr.record_pulse()
        assert mgr.model.total_pulses == 1

    def test_to_prompt_context(self) -> None:
        mgr = SelfModelManager(path="/dev/null")
        mgr.model.total_pulses = 100
        mgr.model.age_days = 3
        mgr.model.capabilities = {"health_sensor": 0.95}
        ctx = mgr.to_prompt_context()
        assert "age_days: 3" in ctx
        assert "health_sensor" in ctx
```

- [ ] **Step 1b: Run tests to verify they fail**

Run: `cd /Users/nuzantara/Desktop/nuzantara/apps/cell && python -m pytest tests/test_self_model.py -v --tb=short 2>&1 | head -20`

Expected: `ModuleNotFoundError: No module named 'cell.identity'`

### Step 2: Implement self-model

- [ ] **Step 2a: Create `cell/identity/__init__.py`**

```python
# cell/identity/__init__.py
```

- [ ] **Step 2b: Create `cell/identity/self_model.py`**

```python
# cell/identity/self_model.py
"""Self-Model — CELL knows itself.

Persistent identity that survives restarts: lifetime counters,
sensor reliability scores, learned preferences, acknowledged weaknesses.
Stored as JSON file (not DB) — simple, local, fast.

Inspired by Stanford Smallville (persistent agent identity).
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("cell.identity")

_DEFAULT_PATH = Path(__file__).parent.parent.parent / "data" / "self_model.json"


@dataclass
class SelfModel:
    """CELL's understanding of itself."""
    capabilities: dict[str, float] = field(default_factory=dict)
    preferences: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    personality_traits: dict[str, float] = field(default_factory=dict)
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
            "age_days": self.age_days,
            "total_pulses": self.total_pulses,
            "total_actions": self.total_actions,
            "birth_date": self.birth_date,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SelfModel":
        return cls(
            capabilities=data.get("capabilities", {}),
            preferences=data.get("preferences", []),
            weaknesses=data.get("weaknesses", []),
            personality_traits=data.get("personality_traits", {}),
            age_days=data.get("age_days", 0),
            total_pulses=data.get("total_pulses", 0),
            total_actions=data.get("total_actions", 0),
            birth_date=data.get("birth_date", ""),
        )


class SelfModelManager:
    """Manages loading, updating, and saving the self-model."""

    def __init__(self, path: str | Path = _DEFAULT_PATH) -> None:
        self._path = Path(path)
        self.model = SelfModel()
        self._sensor_history: dict[str, list[bool]] = {}

    def load(self) -> None:
        """Load self-model from JSON file. Creates default if missing."""
        if not self._path.exists() or str(self._path) == "/dev/null":
            logger.info(f"Self-model not found at {self._path}, using defaults")
            return
        try:
            data = json.loads(self._path.read_text())
            self.model = SelfModel.from_dict(data)
            logger.info(
                f"Self-model loaded: age={self.model.age_days}d "
                f"pulses={self.model.total_pulses} "
                f"actions={self.model.total_actions}"
            )
        except Exception as e:
            logger.warning(f"Failed to load self-model: {e}")

    def save(self) -> None:
        """Persist self-model to JSON file."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self.model.to_dict(), indent=2))
        except Exception as e:
            logger.warning(f"Failed to save self-model: {e}")

    def record_pulse(self) -> None:
        """Called once per pulse to update lifetime counters."""
        self.model.total_pulses += 1
        # Update age_days from birth_date
        if self.model.birth_date:
            try:
                birth = datetime.fromisoformat(self.model.birth_date)
                now = datetime.now(timezone.utc)
                self.model.age_days = (now - birth).days
            except (ValueError, TypeError):
                pass

    def record_action(self) -> None:
        """Called when an action is executed."""
        self.model.total_actions += 1

    def update_sensor_reliability(self, sensor_name: str, success: bool) -> None:
        """Track sensor reliability as rolling success rate.

        Keeps last 100 readings per sensor.
        """
        if sensor_name not in self._sensor_history:
            self._sensor_history[sensor_name] = []
        history = self._sensor_history[sensor_name]
        history.append(success)
        if len(history) > 100:
            self._sensor_history[sensor_name] = history[-100:]
        # Reliability = success rate
        self.model.capabilities[sensor_name] = sum(history) / len(history)

    def add_preference(self, preference: str) -> None:
        """Add a learned preference (deduplicated)."""
        if preference not in self.model.preferences:
            self.model.preferences.append(preference)
            logger.info(f"Self-model: learned preference '{preference}'")

    def add_weakness(self, weakness: str) -> None:
        """Acknowledge a limitation (deduplicated)."""
        if weakness not in self.model.weaknesses:
            self.model.weaknesses.append(weakness)
            logger.info(f"Self-model: acknowledged weakness '{weakness}'")

    def to_prompt_context(self) -> str:
        """Format self-model as context for LLM injection."""
        lines = [
            "SELF-MODEL (who I am):",
            f"  age_days: {self.model.age_days}",
            f"  total_pulses: {self.model.total_pulses}",
            f"  total_actions: {self.model.total_actions}",
        ]
        if self.model.capabilities:
            caps = ", ".join(f"{k}: {v:.0%}" for k, v in sorted(self.model.capabilities.items()))
            lines.append(f"  sensor_reliability: {caps}")
        if self.model.preferences:
            lines.append(f"  preferences: {'; '.join(self.model.preferences[:5])}")
        if self.model.weaknesses:
            lines.append(f"  weaknesses: {'; '.join(self.model.weaknesses[:5])}")
        return "\n".join(lines)
```

- [ ] **Step 2c: Run tests to verify they pass**

Run: `cd /Users/nuzantara/Desktop/nuzantara/apps/cell && python -m pytest tests/test_self_model.py -v`

Expected: All 7 tests PASS

- [ ] **Step 2d: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/cell
git add cell/identity/__init__.py cell/identity/self_model.py tests/test_self_model.py
git commit -m "feat(cell): add self-model with persistent identity and sensor reliability

JSON-persisted: capabilities, preferences, weaknesses, lifetime counters.
Sensor reliability tracked as rolling success rate (last 100 readings)."
```

---

## Task 4: Integrate into PulseEngine

**Files:**

- Modify: `cell/core/pulse.py`
- Modify: existing test `tests/test_pulse.py`

### Step 1: Update PulseEngine constructor and single_pulse

- [ ] **Step 1a: Add homeostatic_controller, episodic_memory, and self_model parameters to `PulseEngine.__init__`**

In `cell/core/pulse.py`, add three new optional parameters to `__init__`:

```python
# Add to __init__ signature after trend_detector:
    homeostatic: Any = None,
    episodic: Any = None,
    self_model: Any = None,
```

And store them:

```python
    self._homeostatic = homeostatic
    self._episodic = episodic
    self._self_model = self_model
```

- [ ] **Step 1b: Add homeostatic update at the start of single_pulse (after safety check)**

After the SAFETY GATES section (after `safety = await self._safety.check()` block, before `# 3. SENSE`), add:

```python
        # HOMEOSTASIS — update internal state
        homeo_state = None
        if self._homeostatic is not None:
            from datetime import datetime, timezone as tz
            hour_utc = datetime.now(tz.utc).hour
            # We'll update with actual RT after sensing — pre-update with last known
            homeo_state = self._homeostatic.state
```

- [ ] **Step 1c: Add homeostatic update after sensing (with actual RT)**

After `response_ms = int(reading.response_time_seconds * 1000) if reading.reachable else 0`, add:

```python
        # Update homeostasis with actual reading
        if self._homeostatic is not None:
            from datetime import datetime, timezone as tz
            self._homeostatic.update(
                response_time_ms=response_ms,
                health_status=http_status.value,
                hour_utc=datetime.now(tz.utc).hour,
            )
            homeo_state = self._homeostatic.state
```

- [ ] **Step 1d: Add self-model pulse recording and episodic memory after action execution**

After the `# 7. PERSIST to PostgreSQL for dashboard` section, before the `return PulseResult(...)`, add:

```python
        # 8. SELF-MODEL — record pulse
        if self._self_model is not None:
            self._self_model.record_pulse()
            if action:
                self._self_model.record_action()
            # Update sensor reliability based on reachability
            self._self_model.update_sensor_reliability("health_sensor", reading.reachable)
            # Save every 60 pulses (~1h)
            if pulse_number % 60 == 0:
                self._self_model.save()

        # 9. EPISODIC MEMORY — record significant events
        if self._episodic is not None and self._episodic.should_record(
            health_status=status.value, action_taken=action
        ):
            from cell.memory.episodic import Episode
            emotion = "calm"
            if status == HealthStatus.RED:
                emotion = "stressed"
            elif status == HealthStatus.YELLOW:
                emotion = "alert"
            if self._homeostatic and self._homeostatic.state.stress_level > 0.8:
                emotion = "panic"
            try:
                ep = Episode(
                    situation={
                        "health_status": status.value,
                        "response_time_ms": response_ms,
                        "sensors": sensor_metadata,
                    },
                    emotion=emotion,
                    action_taken=action or "observe",
                    outcome="pending",  # updated by next pulse
                    lesson=action_reason or "no action needed",
                )
                await self._episodic.store(ep)
            except Exception as e:
                logger.debug(f"Episodic memory store failed: {e}")
```

- [ ] **Step 1e: Add homeostatic state to STM write**

In the STM write section, add homeostatic data to the `data` dict:

```python
                    # In the STM store Observation data dict, add:
                    "stress": self._homeostatic.state.stress_level if self._homeostatic else 0,
                    "energy": self._homeostatic.state.energy_level if self._homeostatic else 1,
                    "circadian": self._homeostatic.state.circadian_phase if self._homeostatic else "awake",
```

### Step 2: Update existing tests

- [ ] **Step 2a: Verify existing tests still pass (no regressions)**

Run: `cd /Users/nuzantara/Desktop/nuzantara/apps/cell && python -m pytest tests/test_pulse.py -v`

Expected: All 3 existing tests PASS (new params are optional, default None)

- [ ] **Step 2b: Add integration test for homeostatic pulse**

Append to `tests/test_pulse.py`:

```python
@pytest.mark.asyncio
async def test_pulse_updates_homeostatic_state(mock_deps: dict) -> None:
    """Homeostatic controller gets updated each pulse."""
    from cell.fast.homeostatic_controller import HomeostaticController
    homeo = HomeostaticController()

    mock_deps["dna_loader"].verify_integrity.return_value = True
    safety_result = MagicMock()
    safety_result.can_proceed = True
    mock_deps["safety_gate"].check.return_value = safety_result
    health_reading = MagicMock()
    health_reading.reachable = True
    health_reading.status_code = 200
    health_reading.response_time_seconds = 0.5
    mock_deps["health_sensor"].read.return_value = health_reading

    engine = PulseEngine(**mock_deps, dna_expected_hash="somehash", homeostatic=homeo)
    await engine.single_pulse(pulse_number=1)

    # Setpoint should have moved toward 500ms
    assert homeo.state.setpoint_rt_ms != 100.0  # changed from default
```

- [ ] **Step 2c: Run all pulse tests**

Run: `cd /Users/nuzantara/Desktop/nuzantara/apps/cell && python -m pytest tests/test_pulse.py -v`

Expected: All 4 tests PASS

- [ ] **Step 2d: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/cell
git add cell/core/pulse.py tests/test_pulse.py
git commit -m "feat(cell): integrate homeostasis + episodic memory + self-model into pulse loop

Pulse now: updates homeostatic state, records episodes for non-green events,
tracks sensor reliability, and persists self-model every 60 pulses."
```

---

## Task 5: Integrate into main.py bootstrap

**Files:**

- Modify: `cell/main.py`

### Step 1: Add imports and initialization

- [ ] **Step 1a: Add imports at the top of `cell/main.py`**

After the existing imports (after `from cell.slow.reasoner import SlowReasoner`), add:

```python
from cell.core.db import create_episodes_table
from cell.fast.homeostatic_controller import HomeostaticController
from cell.memory.episodic import EpisodicMemory
from cell.identity.self_model import SelfModelManager
```

- [ ] **Step 1b: Add initialization in `main()` function**

After `await create_patterns_table()`, add:

```python
    await create_episodes_table()
```

After `trend_detector = TrendDetector()` (before `engine = PulseEngine(`), add:

```python
        # Homeostatic Controller — CELL's body regulation
        # Sleep 2-6 UTC = 10:00-14:00 WITA (low traffic window)
        homeostatic = HomeostaticController(sleep_hours=(2, 6))
        logger.info("HomeostaticController initialized (sleep 02:00-06:00 UTC)")

        # Episodic Memory — moments, not statistics
        _db_pool_ep = await _get_pool()
        episodic = EpisodicMemory(pool=_db_pool_ep, max_episodes=1000)
        ep_count = await episodic.count()
        logger.info(f"EpisodicMemory initialized ({ep_count} episodes)")

        # Self-Model — persistent identity
        self_model_path = settings.cell_root / "data" / "self_model.json"
        self_model = SelfModelManager(path=self_model_path)
        self_model.load()
        logger.info(
            f"SelfModel loaded: age={self_model.model.age_days}d "
            f"pulses={self_model.model.total_pulses} actions={self_model.model.total_actions}"
        )
```

- [ ] **Step 1c: Pass new components to PulseEngine**

Add three new kwargs to the `engine = PulseEngine(...)` call:

```python
            homeostatic=homeostatic,
            episodic=episodic,
            self_model=self_model,
```

- [ ] **Step 1d: Use homeostatic interval in pulse loop**

Replace the fixed adaptive interval logic:

```python
            # Adaptive interval: 15s during stress, 60s when healthy
            interval = 15 if _last_status != "green" else settings.pulse_interval_seconds
```

With:

```python
            # Adaptive interval: homeostatic controller decides
            if homeostatic:
                interval = homeostatic.recommended_pulse_interval()
            else:
                interval = 15 if _last_status != "green" else settings.pulse_interval_seconds
```

- [ ] **Step 1e: Save self-model on shutdown**

Before `logger.info("CELL organism shutdown complete.")`, add:

```python
    # Persist self-model before shutdown
    self_model.save()
    logger.info(f"Self-model saved: pulses={self_model.model.total_pulses}")
```

- [ ] **Step 1f: Add episodic forgetting to weekly cycle**

After the sleep interval logic, add periodic forgetting (every 1000 pulses):

```python
                # Episodic forgetting — every 1000 pulses (~17h)
                if pulse_count % 1000 == 0 and episodic:
                    try:
                        forgotten = await episodic.forget_weak()
                        if forgotten > 0:
                            logger.info(f"Episodic forgetting: {forgotten} weak episodes removed")
                    except Exception as e:
                        logger.debug(f"Episodic forgetting failed: {e}")
```

- [ ] **Step 1g: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/cell
git add cell/main.py
git commit -m "feat(cell): bootstrap homeostasis + episodic memory + self-model in main loop

HomeostaticController drives pulse interval adaptively.
EpisodicMemory stores significant events, forgets weak ones every 1000 pulses.
SelfModel persists across restarts via JSON, saves every 60 pulses + on shutdown."
```

---

## Task 6: Create `data/` directory and run full test suite

**Files:**

- Create: `data/.gitkeep`

- [ ] **Step 6a: Create data directory for self-model persistence**

```bash
mkdir -p /Users/nuzantara/Desktop/nuzantara/apps/cell/data
touch /Users/nuzantara/Desktop/nuzantara/apps/cell/data/.gitkeep
echo "self_model.json" > /Users/nuzantara/Desktop/nuzantara/apps/cell/data/.gitignore
```

- [ ] **Step 6b: Run full test suite**

Run: `cd /Users/nuzantara/Desktop/nuzantara/apps/cell && python -m pytest tests/ -v --tb=short 2>&1 | tail -40`

Expected: All tests PASS (existing + 24 new tests)

- [ ] **Step 6c: Final commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/cell
git add data/.gitkeep data/.gitignore
git commit -m "chore(cell): add data/ directory for self-model persistence"
```

---

## Verification Checklist

After all tasks complete:

- [ ] `python -m pytest tests/test_homeostasis.py -v` — 11 tests pass
- [ ] `python -m pytest tests/test_episodic.py -v` — 6 tests pass
- [ ] `python -m pytest tests/test_self_model.py -v` — 7 tests pass
- [ ] `python -m pytest tests/test_pulse.py -v` — 4 tests pass (including new integration test)
- [ ] `python -m pytest tests/ -v` — full suite passes, no regressions
- [ ] `python -c "from cell.fast.homeostatic_controller import HomeostaticController; print('OK')"` — import works
- [ ] `python -c "from cell.memory.episodic import EpisodicMemory; print('OK')"` — import works
- [ ] `python -c "from cell.identity.self_model import SelfModelManager; print('OK')"` — import works
