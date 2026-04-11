# Mata Garuda cell-core Wrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wrap Mata Garuda's existing runtime with cell-core's PulseLoop, giving MG homeostasis, maturation, and dream cycles without modifying any existing code.

**Architecture:** PulseLoop wraps MG. MetaChain loop becomes the Actor. KnowledgeBase becomes LTM backend via bridge adapter. Fitness feeds HomeostaticController as a Sensor. Reflection becomes the dream phase. DNA (immutable constitution) coexists with GENOME (mutable personality).

**Tech Stack:** cell-core (local package), existing MG runtime (pydantic, pytest, subprocess CLI). Zero new external dependencies.

**Spec:** `docs/superpowers/specs/2026-04-10-mg-cell-core-wrap-design.md`

---

## File Map

### New files (apps/mata-garuda/)

| File | Responsibility |
|------|---------------|
| `mata_garuda/cell/__init__.py` | Package marker |
| `mata_garuda/cell/sensors.py` | RegulationSensor, FitnessSensor — read MG state as SensorReadings |
| `mata_garuda/cell/actor.py` | MetaChainActor — wraps run_with_lamarckian_feedback via asyncio.to_thread |
| `mata_garuda/cell/thinker.py` | PassthroughThinker — MG decides internally, PulseLoop just gates |
| `mata_garuda/cell/memory_bridge.py` | KnowledgeBridgeLTM + ReflectionEpisodicStore — adapts existing KB |
| `mata_garuda/cell/runner.py` | Builds and runs the PulseLoop |
| `mata_garuda/dna.json` | Immutable constitutional rules |
| `tests/test_cell_sensors.py` | Sensor tests |
| `tests/test_cell_actor.py` | Actor wrapper tests |
| `tests/test_cell_memory.py` | Memory bridge tests |
| `tests/test_cell_runner.py` | Integration: full pulse cycle |

### Modified files

| File | Change |
|------|--------|
| `pyproject.toml` | Add cell-core as local dependency |

### NOT modified (188 existing tests untouched)

All files in `mata_garuda/runtime/`, `mata_garuda/agents/`, `mata_garuda/tools/`, `mata_garuda/security/`.

---

### Task 1: Add cell-core dependency + dna.json

**Files:**
- Modify: `apps/mata-garuda/pyproject.toml`
- Create: `apps/mata-garuda/mata_garuda/dna.json`
- Create: `apps/mata-garuda/mata_garuda/cell/__init__.py`

- [ ] **Step 1: Add cell-core to pyproject.toml**

Read `apps/mata-garuda/pyproject.toml`, then add cell-core as a local dependency:

```toml
[project]
dependencies = [
    "pydantic>=2",
    "cell-core @ file:///${PROJECT_ROOT}/../../packages/cell-core",
]
```

If pyproject.toml uses a different format for local deps, use:
```toml
[tool.setuptools]
# ... existing config ...

[project.optional-dependencies]
cell = ["cell-core"]
```

And install with: `pip install -e "../../packages/cell-core" && pip install -e ".[dev]"`

- [ ] **Step 2: Create dna.json**

Create `apps/mata-garuda/mata_garuda/dna.json`:

```json
{
    "rules": [
        {"text": "Never modify DNA", "priority": 1},
        {"text": "Never send OSINT data outside Pro", "priority": 2},
        {"text": "Never import anthropic/openai/google-generativeai SDK", "priority": 3},
        {"text": "Never deploy to cloud", "priority": 4},
        {"text": "If broken, log and retry with progressive hints", "priority": 5}
    ],
    "constraints": {
        "max_daily_budget_usd": 5.0,
        "max_cost_per_investigation_usd": 0.5,
        "max_retry_per_agent": 3,
        "osint_destinations": ["garuda:raw", "telegram:zero"]
    }
}
```

- [ ] **Step 3: Create cell package marker**

Create `apps/mata-garuda/mata_garuda/cell/__init__.py`:

```python
"""cell — cell-core wrapper layer for Mata Garuda."""
```

- [ ] **Step 4: Verify cell-core is importable**

```bash
cd ~/Desktop/nuzantara/apps/mata-garuda
source .venv/bin/activate
pip install -e "../../packages/cell-core"
pip install -e ".[dev]"
python -c "from cell_core import PulseLoop, Maturation, Phase; print('cell-core OK')"
```

Expected: `cell-core OK`

- [ ] **Step 5: Verify existing tests still pass**

```bash
cd ~/Desktop/nuzantara/apps/mata-garuda && pytest tests/ -v --tb=short -q
```

Expected: 188 passed

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/mata-garuda/pyproject.toml apps/mata-garuda/mata_garuda/dna.json apps/mata-garuda/mata_garuda/cell/__init__.py
git commit -m "feat(mata-garuda): add cell-core dependency + dna.json constitution

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: sensors.py — Read MG state as SensorReadings

**Files:**
- Create: `apps/mata-garuda/mata_garuda/cell/sensors.py`
- Create: `apps/mata-garuda/tests/test_cell_sensors.py`

- [ ] **Step 1: Write failing test**

Create `apps/mata-garuda/tests/test_cell_sensors.py`:

```python
"""Tests for mata_garuda.cell.sensors — cell-core Sensor protocol implementations."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from cell_core.types import SensorReading
from cell_core.protocols import Sensor


class TestFitnessSensor:
    def test_implements_sensor_protocol(self):
        from mata_garuda.cell.sensors import FitnessSensor
        sensor = FitnessSensor(agent_name="test")
        assert isinstance(sensor, Sensor)
        assert sensor.name == "fitness:test"

    @pytest.mark.asyncio
    async def test_reads_success_rate(self, tmp_path):
        from mata_garuda.cell.sensors import FitnessSensor

        # Write fake fitness data
        fitness_file = tmp_path / "test_fitness.jsonl"
        for i in range(5):
            fitness_file.open("a").write(
                json.dumps({"success": i < 4, "mutation_version": 0}) + "\n"
            )

        with patch("mata_garuda.cell.sensors.fitness.get_success_rate", return_value=0.8):
            sensor = FitnessSensor(agent_name="test")
            reading = await sensor.read()

        assert reading.sensor_name == "fitness:test"
        assert reading.status == "green"  # 0.8 > 0.5 threshold
        assert reading.value == pytest.approx(0.8)

    @pytest.mark.asyncio
    async def test_low_fitness_is_yellow(self):
        from mata_garuda.cell.sensors import FitnessSensor

        with patch("mata_garuda.cell.sensors.fitness.get_success_rate", return_value=0.4):
            sensor = FitnessSensor(agent_name="test")
            reading = await sensor.read()

        assert reading.status == "yellow"

    @pytest.mark.asyncio
    async def test_very_low_fitness_is_red(self):
        from mata_garuda.cell.sensors import FitnessSensor

        with patch("mata_garuda.cell.sensors.fitness.get_success_rate", return_value=0.1):
            sensor = FitnessSensor(agent_name="test")
            reading = await sensor.read()

        assert reading.status == "red"

    @pytest.mark.asyncio
    async def test_no_runs_is_yellow(self):
        from mata_garuda.cell.sensors import FitnessSensor

        with patch("mata_garuda.cell.sensors.fitness.get_success_rate", return_value=None):
            sensor = FitnessSensor(agent_name="test")
            reading = await sensor.read()

        assert reading.status == "yellow"
        assert reading.value is None


class TestRegulationSensor:
    def test_implements_sensor_protocol(self):
        from mata_garuda.cell.sensors import RegulationSensor
        sensor = RegulationSensor()
        assert isinstance(sensor, Sensor)
        assert sensor.name == "regulation_source"

    @pytest.mark.asyncio
    async def test_reads_source_availability(self):
        from mata_garuda.cell.sensors import RegulationSensor

        with patch("mata_garuda.cell.sensors.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0, stdout="HTTP/2 200")
            sensor = RegulationSensor()
            reading = await sensor.read()

        assert reading.status == "green"

    @pytest.mark.asyncio
    async def test_source_down_is_red(self):
        from mata_garuda.cell.sensors import RegulationSensor

        with patch("mata_garuda.cell.sensors.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=1, stdout="")
            sensor = RegulationSensor()
            reading = await sensor.read()

        assert reading.status == "red"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Desktop/nuzantara/apps/mata-garuda && pytest tests/test_cell_sensors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mata_garuda.cell.sensors'`

- [ ] **Step 3: Implement sensors.py**

Create `apps/mata-garuda/mata_garuda/cell/sensors.py`:

```python
"""Sensors — read MG state as cell-core SensorReadings.

Each sensor wraps an existing MG capability as a Sensor protocol implementation.
No new logic — just adapters.
"""
from __future__ import annotations

import asyncio
import logging
import subprocess

from cell_core.types import SensorReading
from mata_garuda.runtime import fitness

logger = logging.getLogger("mata_garuda.cell")

# Thresholds for fitness → status mapping
_FITNESS_GREEN = 0.5
_FITNESS_YELLOW = 0.2


class FitnessSensor:
    """Reads agent fitness (success rate) as a SensorReading."""

    def __init__(self, agent_name: str = "Regulation Watcher") -> None:
        self.name = f"fitness:{agent_name}"
        self._agent_name = agent_name

    async def read(self, **context) -> SensorReading:
        rate = await asyncio.to_thread(fitness.get_success_rate, self._agent_name)
        if rate is None:
            return SensorReading(
                sensor_name=self.name, status="yellow",
                value=None, metadata={"reason": "no runs recorded"},
            )
        if rate >= _FITNESS_GREEN:
            status = "green"
        elif rate >= _FITNESS_YELLOW:
            status = "yellow"
        else:
            status = "red"
        return SensorReading(
            sensor_name=self.name, status=status,
            value=rate, metadata={"agent": self._agent_name},
        )


class RegulationSensor:
    """Checks if the regulation source (peraturan.go.id) is reachable."""

    SOURCE_URL = "https://peraturan.go.id"

    def __init__(self) -> None:
        self.name = "regulation_source"

    async def read(self, **context) -> SensorReading:
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["curl", "-sI", "--max-time", "10", self.SOURCE_URL],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and "200" in result.stdout:
                return SensorReading(
                    sensor_name=self.name, status="green",
                    value=result.stdout[:100],
                )
            return SensorReading(
                sensor_name=self.name, status="red",
                value=result.stdout[:100],
                metadata={"returncode": result.returncode},
            )
        except Exception as e:
            return SensorReading(
                sensor_name=self.name, status="red",
                metadata={"error": str(e)},
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Desktop/nuzantara/apps/mata-garuda && pytest tests/test_cell_sensors.py -v`
Expected: All PASS

- [ ] **Step 5: Verify existing tests untouched**

Run: `pytest tests/ -v --tb=short -q`
Expected: 188 + new sensor tests all pass

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/mata-garuda/mata_garuda/cell/sensors.py apps/mata-garuda/tests/test_cell_sensors.py
git commit -m "feat(mata-garuda): cell-core sensors wrapping fitness + regulation source

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: actor.py — Wrap MetaChain as Actor

**Files:**
- Create: `apps/mata-garuda/mata_garuda/cell/actor.py`
- Create: `apps/mata-garuda/tests/test_cell_actor.py`

- [ ] **Step 1: Write failing test**

Create `apps/mata-garuda/tests/test_cell_actor.py`:

```python
"""Tests for mata_garuda.cell.actor — MetaChain wrapped as cell-core Actor."""
import pytest
from unittest.mock import patch, MagicMock

from cell_core.types import Proposal
from cell_core.protocols import Actor


class TestMetaChainActor:
    def test_implements_actor_protocol(self):
        from mata_garuda.cell.actor import MetaChainActor
        actor = MetaChainActor()
        assert isinstance(actor, Actor)

    def test_can_execute_known_actions(self):
        from mata_garuda.cell.actor import MetaChainActor
        actor = MetaChainActor()
        assert actor.can_execute("run_regulation_watcher") is True
        assert actor.can_execute("run_meta_agent") is True
        assert actor.can_execute("unknown_action") is False

    @pytest.mark.asyncio
    async def test_act_runs_agent(self):
        from mata_garuda.cell.actor import MetaChainActor
        from mata_garuda.types import Response

        mock_response = Response(
            messages=[{"role": "assistant", "content": "Case resolved. The result is: done"}],
        )

        with patch("mata_garuda.cell.actor.run_with_lamarckian_feedback", return_value=mock_response):
            actor = MetaChainActor()
            proposal = Proposal(
                action="run_regulation_watcher",
                reason="daily harvest",
                confidence=0.9,
                tier_used=0,
            )
            result = await actor.act(proposal)

        assert "resolved" in result.lower() or "done" in result.lower()

    @pytest.mark.asyncio
    async def test_act_returns_failure_on_error(self):
        from mata_garuda.cell.actor import MetaChainActor

        with patch("mata_garuda.cell.actor.run_with_lamarckian_feedback", side_effect=Exception("boom")):
            actor = MetaChainActor()
            proposal = Proposal(action="run_regulation_watcher", reason="test", confidence=0.9, tier_used=0)
            result = await actor.act(proposal)

        assert "error" in result.lower()

    def test_executed_actions_tracked(self):
        from mata_garuda.cell.actor import MetaChainActor
        actor = MetaChainActor()
        assert actor.last_run_success is None  # no runs yet
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Desktop/nuzantara/apps/mata-garuda && pytest tests/test_cell_actor.py -v`
Expected: FAIL

- [ ] **Step 3: Implement actor.py**

Create `apps/mata-garuda/mata_garuda/cell/actor.py`:

```python
"""MetaChainActor — wraps MG's run_with_lamarckian_feedback as cell-core Actor.

The existing MetaChain loop is synchronous. This adapter runs it via
asyncio.to_thread() to keep PulseLoop's event loop clean.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from cell_core.types import Proposal
from mata_garuda.registry import get_agent
from mata_garuda.runtime.knowledge import KnowledgeBase
from mata_garuda.runtime.lamarckian import run_with_lamarckian_feedback
from mata_garuda.types import Response

logger = logging.getLogger("mata_garuda.cell")

# Map PulseLoop action names to MG agent names
_ACTION_TO_AGENT = {
    "run_regulation_watcher": "Regulation Watcher",
    "run_meta_agent": "Meta Agent",
}


class MetaChainActor:
    """Wraps MG's Lamarckian loop as a cell-core Actor protocol."""

    def __init__(self, kb: Optional[KnowledgeBase] = None) -> None:
        self._kb = kb
        self.last_run_success: Optional[bool] = None
        self.last_response: Optional[Response] = None

    def can_execute(self, action_name: str) -> bool:
        return action_name in _ACTION_TO_AGENT

    async def act(self, proposal: Proposal) -> str:
        agent_name = _ACTION_TO_AGENT.get(proposal.action)
        if not agent_name:
            return f"[ERROR] Unknown action: {proposal.action}"

        try:
            response = await asyncio.to_thread(
                self._run_sync, agent_name, proposal.reason,
            )
            self.last_response = response

            # Determine success from messages
            last_msg = response.messages[-1]["content"] if response.messages else ""
            if "case resolved" in last_msg.lower() or "case_resolved" in last_msg.lower():
                self.last_run_success = True
                return f"resolved: {last_msg[:200]}"
            elif "case not resolved" in last_msg.lower() or "case_not_resolved" in last_msg.lower():
                self.last_run_success = False
                return f"not_resolved: {last_msg[:200]}"
            else:
                self.last_run_success = None
                return f"completed: {last_msg[:200]}"
        except Exception as e:
            self.last_run_success = False
            logger.error(f"[actor] MetaChain failed: {e}")
            return f"[ERROR] {e}"

    def _run_sync(self, agent_name: str, query: str) -> Response:
        """Run MG agent synchronously — called via asyncio.to_thread."""
        agent = get_agent(agent_name)
        if agent is None:
            raise ValueError(f"Agent '{agent_name}' not registered")
        return run_with_lamarckian_feedback(
            agent=agent, query=query, kb=self._kb,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Desktop/nuzantara/apps/mata-garuda && pytest tests/test_cell_actor.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/mata-garuda/mata_garuda/cell/actor.py apps/mata-garuda/tests/test_cell_actor.py
git commit -m "feat(mata-garuda): MetaChainActor wraps Lamarckian loop as cell-core Actor

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: thinker.py — Passthrough decision gate

**Files:**
- Create: `apps/mata-garuda/mata_garuda/cell/thinker.py`
- Create: `apps/mata-garuda/tests/test_cell_thinker.py`

- [ ] **Step 1: Write failing test**

Create `apps/mata-garuda/tests/test_cell_thinker.py`:

```python
"""Tests for mata_garuda.cell.thinker — passthrough decision gate."""
import pytest

from cell_core.types import HomeostaticState, Proposal, SensorReading
from cell_core.protocols import Thinker


class TestPassthroughThinker:
    def test_implements_thinker_protocol(self):
        from mata_garuda.cell.thinker import PassthroughThinker
        thinker = PassthroughThinker()
        assert isinstance(thinker, Thinker)

    @pytest.mark.asyncio
    async def test_proposes_run_when_red_fitness(self):
        from mata_garuda.cell.thinker import PassthroughThinker
        thinker = PassthroughThinker()
        readings = [
            SensorReading(sensor_name="fitness:Regulation Watcher", status="red", value=0.1),
        ]
        state = HomeostaticState(stress_level=0.8)
        proposal = await thinker.think(readings, state, {})
        assert proposal.action != "none"

    @pytest.mark.asyncio
    async def test_proposes_run_when_regulation_source_green(self):
        from mata_garuda.cell.thinker import PassthroughThinker
        thinker = PassthroughThinker()
        readings = [
            SensorReading(sensor_name="regulation_source", status="green"),
            SensorReading(sensor_name="fitness:Regulation Watcher", status="green", value=0.9),
        ]
        state = HomeostaticState()
        proposal = await thinker.think(readings, state, {})
        # Green across the board — still propose run (it's harvest time)
        assert proposal.action == "run_regulation_watcher"

    @pytest.mark.asyncio
    async def test_proposes_none_when_source_down(self):
        from mata_garuda.cell.thinker import PassthroughThinker
        thinker = PassthroughThinker()
        readings = [
            SensorReading(sensor_name="regulation_source", status="red"),
            SensorReading(sensor_name="fitness:Regulation Watcher", status="green", value=0.9),
        ]
        state = HomeostaticState()
        proposal = await thinker.think(readings, state, {})
        # Source down — don't try to scrape
        assert proposal.action == "none"

    @pytest.mark.asyncio
    async def test_proposes_none_when_sleeping(self):
        from mata_garuda.cell.thinker import PassthroughThinker
        thinker = PassthroughThinker()
        readings = [
            SensorReading(sensor_name="regulation_source", status="green"),
        ]
        state = HomeostaticState(circadian_phase="asleep")
        proposal = await thinker.think(readings, state, {})
        assert proposal.action == "none"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Desktop/nuzantara/apps/mata-garuda && pytest tests/test_cell_thinker.py -v`
Expected: FAIL

- [ ] **Step 3: Implement thinker.py**

Create `apps/mata-garuda/mata_garuda/cell/thinker.py`:

```python
"""PassthroughThinker — MG decides internally, PulseLoop just gates.

MG's real reasoning happens inside MetaChain (the Actor). The Thinker's job
is simpler: look at sensor readings and decide IF we should run at all.
"""
from __future__ import annotations

import logging

from cell_core.types import HomeostaticState, Proposal, SensorReading

logger = logging.getLogger("mata_garuda.cell")


class PassthroughThinker:
    """Decides whether to trigger a MetaChain run based on sensor state."""

    async def think(
        self,
        readings: list[SensorReading],
        state: HomeostaticState,
        memory_context: dict,
    ) -> Proposal:
        # During sleep, don't run agents (dream phase handles consolidation)
        if state.circadian_phase == "asleep":
            return Proposal(action="none", reason="sleeping — dream phase only", confidence=1.0, tier_used=-1)

        # Check regulation source
        source_reading = next(
            (r for r in readings if r.sensor_name == "regulation_source"), None
        )
        if source_reading and source_reading.status == "red":
            return Proposal(action="none", reason="regulation source unreachable", confidence=0.9, tier_used=-1)

        # Check fitness — if very low, prioritize running to recover
        fitness_reading = next(
            (r for r in readings if r.sensor_name.startswith("fitness:")), None
        )
        if fitness_reading and fitness_reading.status == "red":
            return Proposal(
                action="run_regulation_watcher",
                reason=f"fitness critical ({fitness_reading.value}), need recovery run",
                confidence=0.7,
                tier_used=0,
            )

        # Default: run the watcher (it's what MG does)
        return Proposal(
            action="run_regulation_watcher",
            reason="routine harvest cycle",
            confidence=0.9,
            tier_used=0,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Desktop/nuzantara/apps/mata-garuda && pytest tests/test_cell_thinker.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/mata-garuda/mata_garuda/cell/thinker.py apps/mata-garuda/tests/test_cell_thinker.py
git commit -m "feat(mata-garuda): PassthroughThinker gates MetaChain runs on sensor state

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: memory_bridge.py — Adapt existing KnowledgeBase as cell-core memory

**Files:**
- Create: `apps/mata-garuda/mata_garuda/cell/memory_bridge.py`
- Create: `apps/mata-garuda/tests/test_cell_memory.py`

- [ ] **Step 1: Write failing test**

Create `apps/mata-garuda/tests/test_cell_memory.py`:

```python
"""Tests for mata_garuda.cell.memory_bridge — adapts KnowledgeBase as cell-core memory."""
import time
import pytest
from pathlib import Path

from cell_core.types import Episode, LearnedRule
from cell_core.protocols import LTMStore, EpisodicStore, STMStore


@pytest.fixture
def kb(tmp_path):
    from mata_garuda.runtime.knowledge import KnowledgeBase
    return KnowledgeBase(db_path=tmp_path / "test_kb.db")


class TestKnowledgeBridgeLTM:
    def test_implements_ltm_protocol(self, kb):
        from mata_garuda.cell.memory_bridge import KnowledgeBridgeLTM
        ltm = KnowledgeBridgeLTM(kb)
        assert isinstance(ltm, LTMStore)

    @pytest.mark.asyncio
    async def test_store_and_load_rules(self, kb):
        from mata_garuda.cell.memory_bridge import KnowledgeBridgeLTM
        ltm = KnowledgeBridgeLTM(kb)
        rule = LearnedRule(rule_text="Always check HTTP 200 before scraping", support_count=3)
        await ltm.store_rule(rule)
        rules = await ltm.load_rules(limit=10)
        assert len(rules) >= 1
        assert "HTTP 200" in rules[0].rule_text

    @pytest.mark.asyncio
    async def test_condense_extracts_patterns(self, kb):
        from mata_garuda.cell.memory_bridge import KnowledgeBridgeLTM
        ltm = KnowledgeBridgeLTM(kb)
        episodes = [
            Episode(situation={}, emotion="calm", action_taken="scrape",
                    outcome="success", lesson="curl first", timestamp=time.time())
            for _ in range(5)
        ]
        rules = await ltm.condense(episodes)
        assert len(rules) >= 1


class TestReflectionEpisodicStore:
    def test_implements_episodic_protocol(self, kb):
        from mata_garuda.cell.memory_bridge import ReflectionEpisodicStore
        ep = ReflectionEpisodicStore(kb)
        assert isinstance(ep, EpisodicStore)

    @pytest.mark.asyncio
    async def test_store_episode(self, kb):
        from mata_garuda.cell.memory_bridge import ReflectionEpisodicStore
        ep = ReflectionEpisodicStore(kb)
        episode = Episode(
            situation={"status": "red"}, emotion="stressed",
            action_taken="restart", outcome="success", lesson="restart works",
            timestamp=time.time(),
        )
        eid = await ep.store(episode)
        assert eid > 0

    @pytest.mark.asyncio
    async def test_recall_recent(self, kb):
        from mata_garuda.cell.memory_bridge import ReflectionEpisodicStore
        ep = ReflectionEpisodicStore(kb)
        for i in range(3):
            await ep.store(Episode(
                situation={"i": i}, emotion="calm", action_taken="scrape",
                outcome="success", lesson=f"lesson {i}", timestamp=time.time(),
            ))
        results = await ep.recall_recent(hours=1, limit=10)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_forget_weak(self, kb):
        from mata_garuda.cell.memory_bridge import ReflectionEpisodicStore
        ep = ReflectionEpisodicStore(kb)
        for i in range(10):
            await ep.store(Episode(
                situation={}, emotion="calm", action_taken="x",
                outcome="success", lesson=f"l{i}",
                timestamp=time.time() - (10 - i) * 3600,
            ))
        removed = await ep.forget_weak(keep=5)
        assert removed == 5


class TestBridgeSTM:
    def test_implements_stm_protocol(self, kb):
        from mata_garuda.cell.memory_bridge import BridgeSTM
        stm = BridgeSTM()
        assert isinstance(stm, STMStore)

    @pytest.mark.asyncio
    async def test_store_and_recent(self):
        from mata_garuda.cell.memory_bridge import BridgeSTM
        stm = BridgeSTM()
        await stm.store("health", {"status": "green"})
        results = await stm.recent("health", limit=5)
        assert len(results) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Desktop/nuzantara/apps/mata-garuda && pytest tests/test_cell_memory.py -v`
Expected: FAIL

- [ ] **Step 3: Implement memory_bridge.py**

Create `apps/mata-garuda/mata_garuda/cell/memory_bridge.py`:

```python
"""Memory bridge — adapts MG's KnowledgeBase as cell-core memory protocols.

KnowledgeBridgeLTM wraps knowledge.py as LTMStore.
ReflectionEpisodicStore wraps knowledge.py as EpisodicStore (episodes = reflections).
BridgeSTM is in-memory (MG doesn't need Redis STM).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import Counter
from typing import Any

from cell_core.types import Episode, LearnedRule
from mata_garuda.runtime.knowledge import KnowledgeBase

logger = logging.getLogger("mata_garuda.cell")


class KnowledgeBridgeLTM:
    """Wraps KnowledgeBase as cell-core LTMStore protocol."""

    def __init__(self, kb: KnowledgeBase) -> None:
        self._kb = kb

    async def store_rule(self, rule: LearnedRule) -> None:
        await asyncio.to_thread(
            self._kb.store,
            agent="cell",
            entry_type="rule",
            content=rule.rule_text,
            source="ltm_condense",
            confidence=min(rule.support_count / 10.0, 1.0),
        )

    async def load_rules(self, limit: int) -> list[LearnedRule]:
        rows = await asyncio.to_thread(self._kb.get_by_type, "rule", limit)
        return [
            LearnedRule(
                rule_text=row["content"],
                support_count=int(row.get("confidence", 0.5) * 10),
                created_at=row.get("created_at", ""),
            )
            for row in rows
        ]

    async def condense(self, episodes: list[Episode]) -> list[LearnedRule]:
        """Extract patterns from episodes — group by action+outcome."""
        def _condense() -> list[LearnedRule]:
            patterns: Counter[str] = Counter()
            for ep in episodes:
                key = f"When {ep.emotion}, {ep.action_taken} → {ep.outcome}"
                patterns[key] += 1
            return [
                LearnedRule(rule_text=pattern, support_count=count)
                for pattern, count in patterns.most_common()
                if count >= 2
            ]
        return await asyncio.to_thread(_condense)


class ReflectionEpisodicStore:
    """Wraps KnowledgeBase as cell-core EpisodicStore.

    Episodes are stored as type='episode' in the KB.
    """

    def __init__(self, kb: KnowledgeBase) -> None:
        self._kb = kb

    async def store(self, episode: Episode) -> int:
        content = json.dumps({
            "situation": episode.situation,
            "emotion": episode.emotion,
            "action_taken": episode.action_taken,
            "outcome": episode.outcome,
            "lesson": episode.lesson,
        })
        return await asyncio.to_thread(
            self._kb.store,
            agent="cell",
            entry_type="episode",
            content=content,
            source=f"pulse_{episode.emotion}",
            confidence=0.5,
        )

    async def recall(self, situation: dict[str, Any], limit: int) -> list[Episode]:
        rows = await asyncio.to_thread(self._kb.get_by_type, "episode", limit)
        return self._rows_to_episodes(rows)

    async def recall_recent(self, hours: int, limit: int) -> list[Episode]:
        rows = await asyncio.to_thread(self._kb.get_by_type, "episode", limit)
        return self._rows_to_episodes(rows)

    async def forget_weak(self, keep: int) -> int:
        rows = await asyncio.to_thread(self._kb.get_by_type, "episode", 1000)
        if len(rows) <= keep:
            return 0
        to_delete = rows[keep:]
        for row in to_delete:
            await asyncio.to_thread(
                self._kb._execute,
                "DELETE FROM knowledge WHERE id = ?",
                (row["id"],),
            )
        return len(to_delete)

    @staticmethod
    def _rows_to_episodes(rows: list[dict]) -> list[Episode]:
        episodes = []
        for row in rows:
            try:
                data = json.loads(row["content"])
                episodes.append(Episode(
                    id=row["id"],
                    situation=data.get("situation", {}),
                    emotion=data.get("emotion", "calm"),
                    action_taken=data.get("action_taken", ""),
                    outcome=data.get("outcome", ""),
                    lesson=data.get("lesson", ""),
                    timestamp=time.time(),
                ))
            except (json.JSONDecodeError, KeyError):
                continue
        return episodes


class BridgeSTM:
    """In-memory STM for MG. No Redis needed — lightweight."""

    def __init__(self, max_entries: int = 100) -> None:
        self._store: list[tuple[str, dict[str, Any]]] = []
        self._max = max_entries

    async def store(self, event_type: str, data: dict[str, Any]) -> None:
        self._store.append((event_type, data))
        if len(self._store) > self._max:
            self._store = self._store[-self._max:]

    async def recent(self, event_type: str, limit: int) -> list[dict[str, Any]]:
        if event_type:
            filtered = [d for et, d in reversed(self._store) if et == event_type]
        else:
            filtered = [d for _, d in reversed(self._store)]
        return filtered[:limit]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Desktop/nuzantara/apps/mata-garuda && pytest tests/test_cell_memory.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/mata-garuda/mata_garuda/cell/memory_bridge.py apps/mata-garuda/tests/test_cell_memory.py
git commit -m "feat(mata-garuda): memory bridge adapts KnowledgeBase as cell-core LTM/Episodic

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: runner.py — Build and run the PulseLoop

**Files:**
- Create: `apps/mata-garuda/mata_garuda/cell/runner.py`
- Create: `apps/mata-garuda/tests/test_cell_runner.py`

- [ ] **Step 1: Write failing test**

Create `apps/mata-garuda/tests/test_cell_runner.py`:

```python
"""Tests for mata_garuda.cell.runner — builds and runs PulseLoop."""
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock

from cell_core.types import PulseResult, Phase


class TestBuildPulseLoop:
    def test_builds_pulse_loop(self, tmp_path):
        from mata_garuda.cell.runner import build_pulse_loop

        with patch("mata_garuda.cell.runner.KnowledgeBase") as MockKB:
            MockKB.return_value = MagicMock()
            pl = build_pulse_loop(
                dna_path=str(tmp_path / "nonexistent.json"),
                kb_path=str(tmp_path / "test.db"),
            )

        from cell_core.pulse import PulseLoop
        assert isinstance(pl, PulseLoop)

    def test_lifecycle_phase(self):
        from mata_garuda.cell.runner import MG_BIRTH_DATE
        from cell_core.lifecycle import Maturation

        m = Maturation(birth_date=MG_BIRTH_DATE)
        # MG born 2026-04-01, should be past embrione
        assert m.age_days >= 9
        assert m.can_act() is True


class TestSinglePulse:
    @pytest.mark.asyncio
    async def test_single_pulse_runs(self, tmp_path):
        """Verify a single pulse completes with fake sensors."""
        from mata_garuda.cell.runner import build_pulse_loop
        from cell_core.types import SensorReading, SafetyCheckResult

        # Build with fakes
        from mata_garuda.cell.memory_bridge import BridgeSTM, KnowledgeBridgeLTM, ReflectionEpisodicStore
        from mata_garuda.cell.thinker import PassthroughThinker
        from cell_core.pulse import PulseLoop
        from cell_core.lifecycle import Maturation
        from cell_core.homeostasis import HomeostaticController

        class FakeSensor:
            name = "fake"
            async def read(self, **ctx):
                return SensorReading(sensor_name="fake", status="green")

        class FakeActor:
            async def act(self, proposal):
                return "done"
            def can_execute(self, action_name):
                return True

        class FakeSafety:
            async def check(self):
                return SafetyCheckResult(can_proceed=True)

        from mata_garuda.runtime.knowledge import KnowledgeBase
        kb = KnowledgeBase(db_path=tmp_path / "test.db")

        pl = PulseLoop(
            config=MagicMock(name="test", dna_path="x", sleep_hours=(2, 6)),
            sensors=[FakeSensor()],
            thinker=PassthroughThinker(),
            actor=FakeActor(),
            stm=BridgeSTM(),
            ltm=KnowledgeBridgeLTM(kb),
            episodic=ReflectionEpisodicStore(kb),
            lifecycle=Maturation(birth_date=datetime(2026, 4, 1, tzinfo=timezone.utc)),
            safety=FakeSafety(),
            homeostasis=HomeostaticController(),
        )

        result = await pl.single_pulse()
        assert isinstance(result, PulseResult)
        assert result.halted is False
        assert result.pulse_number == 1

        kb.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Desktop/nuzantara/apps/mata-garuda && pytest tests/test_cell_runner.py -v`
Expected: FAIL

- [ ] **Step 3: Implement runner.py**

Create `apps/mata-garuda/mata_garuda/cell/runner.py`:

```python
"""Runner — builds and runs the PulseLoop for Mata Garuda.

Entry points:
  python -m mata_garuda.cell.runner          # run forever
  python -m mata_garuda.cell.runner --once   # single pulse
"""
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from cell_core import CellConfig, PulseLoop, Maturation, SafetyGate
from cell_core.homeostasis import HomeostaticController
from cell_core.identity import SelfModelManager

from mata_garuda.cell.actor import MetaChainActor
from mata_garuda.cell.memory_bridge import BridgeSTM, KnowledgeBridgeLTM, ReflectionEpisodicStore
from mata_garuda.cell.sensors import FitnessSensor, RegulationSensor
from mata_garuda.cell.thinker import PassthroughThinker
from mata_garuda.runtime.knowledge import KnowledgeBase

logger = logging.getLogger("mata_garuda.cell")

MG_BIRTH_DATE = datetime(2026, 4, 1, tzinfo=timezone.utc)
MG_DNA_PATH = str(Path(__file__).parent.parent / "dna.json")
MG_KB_PATH = str(Path(__file__).parent.parent.parent / "data" / "knowledge.db")
MG_SELF_MODEL_PATH = str(Path(__file__).parent.parent.parent / "data" / "self_model.json")


def build_pulse_loop(
    dna_path: str = MG_DNA_PATH,
    kb_path: str = MG_KB_PATH,
    self_model_path: str = MG_SELF_MODEL_PATH,
) -> PulseLoop:
    """Build a fully wired PulseLoop for Mata Garuda."""
    config = CellConfig(
        name="mata-garuda",
        dna_path=dna_path,
        pulse_interval_seconds=3600,  # hourly
        birth_date=MG_BIRTH_DATE,
        memory_backend="sqlite",
        db_path=kb_path,
        sleep_hours=(2, 6),  # UTC — 10:00-14:00 WITA
    )

    kb = KnowledgeBase(db_path=Path(kb_path))

    # Identity
    identity = SelfModelManager(path=self_model_path)
    identity.load()

    return PulseLoop(
        config=config,
        sensors=[
            RegulationSensor(),
            FitnessSensor(agent_name="Regulation Watcher"),
        ],
        thinker=PassthroughThinker(),
        actor=MetaChainActor(kb=kb),
        stm=BridgeSTM(),
        ltm=KnowledgeBridgeLTM(kb),
        episodic=ReflectionEpisodicStore(kb),
        lifecycle=Maturation(birth_date=MG_BIRTH_DATE),
        safety=SafetyGate(
            disable_file="/tmp/mata-garuda.disabled",
            cell_name="mata-garuda",
        ),
        homeostasis=HomeostaticController(sleep_hours=config.sleep_hours),
        identity=identity,
    )


async def main(once: bool = False) -> None:
    """Entry point."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    logger.info("Building Mata Garuda PulseLoop...")

    pl = build_pulse_loop()
    lifecycle = pl.lifecycle
    logger.info(
        f"MG alive: age={lifecycle.age_days}d phase={lifecycle.phase.value} "
        f"can_act={lifecycle.can_act()} can_dream={lifecycle.can_dream()}"
    )

    if once:
        result = await pl.single_pulse()
        logger.info(f"Pulse #{result.pulse_number}: status={result.health_status} action={result.action_taken}")
    else:
        logger.info("Starting PulseLoop (Ctrl+C to stop)...")
        await pl.run()


if __name__ == "__main__":
    once = "--once" in sys.argv
    asyncio.run(main(once=once))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Desktop/nuzantara/apps/mata-garuda && pytest tests/test_cell_runner.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `cd ~/Desktop/nuzantara/apps/mata-garuda && pytest tests/ -v --tb=short -q`
Expected: 188 existing + all new cell tests pass

- [ ] **Step 6: Commit**

```bash
cd ~/Desktop/nuzantara
git add apps/mata-garuda/mata_garuda/cell/runner.py apps/mata-garuda/tests/test_cell_runner.py
git commit -m "feat(mata-garuda): PulseLoop runner — MG becomes a living cell

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Smoke test — run a single pulse

**Files:** None new — validation only.

- [ ] **Step 1: Run single pulse**

```bash
cd ~/Desktop/nuzantara/apps/mata-garuda
source .venv/bin/activate
python -m mata_garuda.cell.runner --once
```

Expected output (approximate):
```
Building Mata Garuda PulseLoop...
MG alive: age=9d phase=neonato can_act=True can_dream=False
Pulse #1: status=green action=run_regulation_watcher
```

If it fails (e.g., regulation source unreachable), that's fine — the pulse should still complete with status=red and action=none.

- [ ] **Step 2: Verify kill switch works**

```bash
touch /tmp/mata-garuda.disabled
python -m mata_garuda.cell.runner --once
```

Expected: Pulse halted with reason "disabled"

```bash
rm /tmp/mata-garuda.disabled
```

- [ ] **Step 3: Run full test suite one final time**

```bash
pytest tests/ -v --tb=short -q
```

Expected: All tests pass (188 existing + ~25 new)

- [ ] **Step 4: Commit any fixes from smoke test**

```bash
cd ~/Desktop/nuzantara
git add -A apps/mata-garuda/
git commit -m "fix(mata-garuda): smoke test fixes for cell-core wrap

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

(Skip this commit if no fixes needed.)
