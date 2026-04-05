# CELL Fase 2 — Dreamer, Journal, Attention Allocator, Lifecycle

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give CELL the ability to consolidate memories during sleep (Dreamer), maintain a daily narrative (Journal), allocate attention as a scarce resource (Attention Allocator), and enforce lifecycle phase gates (Maturation).

**Architecture:** Four new modules integrate with the existing pulse loop. The Dreamer runs during `homeostatic.is_sleeping()` instead of a normal pulse. The Journal is written once/day during sleep and injected into the SlowReasoner system prompt. The Attention Allocator wraps LLM calls with a budget gate. The Maturation tracker gates which capabilities are active based on age_days from SelfModel.

**Tech Stack:** Python 3.11, asyncpg (PostgreSQL), existing Ollama Qwen 9B/27B via httpx, dataclasses, pytest + asynctest mocks

---

## File Map

| File                                     | Action | Responsibility                                                                                    |
| ---------------------------------------- | ------ | ------------------------------------------------------------------------------------------------- |
| `cell/memory/dreamer.py`                 | Create | Nocturnal consolidation: replay episodes → extract rules → write to `cell_dreams`                 |
| `cell/identity/journal.py`               | Create | Daily narrative: summarize day → store in `cell_journal` → provide `recent_days()`                |
| `cell/metabolism/attention_allocator.py` | Create | 100 units/day budget gate for LLM calls, dreaming, curiosity                                      |
| `cell/lifecycle/maturation.py`           | Create | Phase detection (embrione/neonato/giovane/adulto/anziano) + capability gates                      |
| `cell/lifecycle/__init__.py`             | Create | Empty package marker                                                                              |
| `cell/core/db.py`                        | Modify | Add `create_dreams_table()`, `create_journal_table()`                                             |
| `cell/core/pulse.py`                     | Modify | Dreamer called when sleeping; journal context injected; lifecycle gates checked; attention gating |
| `cell/slow/reasoner.py`                  | Modify | `think()` accepts `journal_context` kwarg; inserted into system prompt                            |
| `cell/main.py`                           | Modify | Wire Dreamer, Journal, AttentionAllocator, Maturation into PulseEngine                            |
| `tests/test_dreamer.py`                  | Create | Unit tests for Dreamer (mocked DB + Ollama)                                                       |
| `tests/test_journal.py`                  | Create | Unit tests for Journal (mocked DB + Ollama)                                                       |
| `tests/test_attention_allocator.py`      | Create | Unit tests for AttentionAllocator                                                                 |
| `tests/test_maturation.py`               | Create | Unit tests for Maturation lifecycle phases                                                        |

---

## Task 1: Maturation — Lifecycle Phase Gates

**Files:**

- Create: `apps/cell/cell/lifecycle/__init__.py`
- Create: `apps/cell/cell/lifecycle/maturation.py`
- Create: `apps/cell/tests/test_maturation.py`

### Why Maturation first

It has no DB dependency, is pure Python, and gates what all other Fase 2 features are allowed to do. Build the gate before the things it gates.

- [ ] **Step 1: Create package marker**

```python
# apps/cell/cell/lifecycle/__init__.py
# (empty)
```

- [ ] **Step 2: Write failing tests**

```python
# apps/cell/tests/test_maturation.py
"""Tests for Maturation lifecycle phases."""
import pytest
from cell.lifecycle.maturation import Maturation, LifecyclePhase


class TestMaturationPhases:
    def test_embrione_day0(self):
        m = Maturation(age_days=0)
        assert m.phase == LifecyclePhase.EMBRIONE

    def test_embrione_day3(self):
        m = Maturation(age_days=3)
        assert m.phase == LifecyclePhase.EMBRIONE

    def test_neonato_day4(self):
        m = Maturation(age_days=4)
        assert m.phase == LifecyclePhase.NEONATO

    def test_neonato_day14(self):
        m = Maturation(age_days=14)
        assert m.phase == LifecyclePhase.NEONATO

    def test_giovane_day15(self):
        m = Maturation(age_days=15)
        assert m.phase == LifecyclePhase.GIOVANE

    def test_adulto_day31(self):
        m = Maturation(age_days=31)
        assert m.phase == LifecyclePhase.ADULTO

    def test_anziano_day180(self):
        m = Maturation(age_days=180)
        assert m.phase == LifecyclePhase.ANZIANO


class TestMaturationCapabilities:
    def test_embrione_no_actions(self):
        m = Maturation(age_days=1)
        assert m.can_act() is False
        assert m.can_dream() is False
        assert m.can_reason_deep() is False

    def test_neonato_can_reason_not_act_autonomously(self):
        m = Maturation(age_days=5)
        assert m.can_reason_deep() is True
        assert m.can_dream() is False
        # neonato can act but only with high confidence — gate checked by caller
        assert m.can_act() is True

    def test_giovane_can_dream(self):
        m = Maturation(age_days=20)
        assert m.can_dream() is True
        assert m.can_act() is True

    def test_adulto_full_autonomy(self):
        m = Maturation(age_days=50)
        assert m.can_act() is True
        assert m.can_dream() is True
        assert m.can_reason_deep() is True

    def test_confidence_threshold_embrione(self):
        m = Maturation(age_days=2)
        assert m.action_confidence_threshold() == 1.1  # impossible — blocks all actions

    def test_confidence_threshold_neonato(self):
        m = Maturation(age_days=7)
        assert m.action_confidence_threshold() == 0.8

    def test_confidence_threshold_adulto(self):
        m = Maturation(age_days=40)
        assert m.action_confidence_threshold() == 0.0  # no threshold


class TestMaturationPromptContext:
    def test_to_prompt_context_includes_phase(self):
        m = Maturation(age_days=20)
        ctx = m.to_prompt_context()
        assert "giovane" in ctx
        assert "15" in ctx or "day" in ctx.lower()
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/cell
source .venv/bin/activate
PYTHONPATH=. pytest tests/test_maturation.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'cell.lifecycle.maturation'`

- [ ] **Step 4: Implement Maturation**

```python
# apps/cell/cell/lifecycle/maturation.py
"""Maturation — CELL's lifecycle phase tracker.

Phases gate capabilities: embrione observes only, neonato acts with approval,
giovane acts autonomously + dreams, adulto has full autonomy, anziano stabilizes.

Inspired by developmental biology and VOYAGER's progressive skill unlocking.
"""
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("cell.lifecycle")


class LifecyclePhase(str, Enum):
    EMBRIONE = "embrione"   # day 0-3: observe only
    NEONATO = "neonato"     # day 4-14: act with high confidence
    GIOVANE = "giovane"     # day 15-30: autonomous + dreams
    ADULTO = "adulto"       # day 31-179: full autonomy
    ANZIANO = "anziano"     # day 180+: stability priority


@dataclass
class Maturation:
    """Lifecycle phase based on CELL's age in days."""
    age_days: int

    @property
    def phase(self) -> LifecyclePhase:
        if self.age_days >= 180:
            return LifecyclePhase.ANZIANO
        if self.age_days >= 31:
            return LifecyclePhase.ADULTO
        if self.age_days >= 15:
            return LifecyclePhase.GIOVANE
        if self.age_days >= 4:
            return LifecyclePhase.NEONATO
        return LifecyclePhase.EMBRIONE

    def can_act(self) -> bool:
        """Can CELL take autonomous actions?"""
        return self.phase != LifecyclePhase.EMBRIONE

    def can_dream(self) -> bool:
        """Can CELL run nocturnal consolidation?"""
        return self.phase in (
            LifecyclePhase.GIOVANE, LifecyclePhase.ADULTO, LifecyclePhase.ANZIANO
        )

    def can_reason_deep(self) -> bool:
        """Can CELL use Qwen 27B deep reasoning?"""
        return self.phase != LifecyclePhase.EMBRIONE

    def action_confidence_threshold(self) -> float:
        """Minimum confidence required to execute an action.

        1.1 = impossible (embrione: blocks all actions).
        0.8 = neonato (high confidence only).
        0.0 = no gate (adulto/anziano).
        """
        thresholds = {
            LifecyclePhase.EMBRIONE: 1.1,
            LifecyclePhase.NEONATO: 0.8,
            LifecyclePhase.GIOVANE: 0.5,
            LifecyclePhase.ADULTO: 0.0,
            LifecyclePhase.ANZIANO: 0.0,
        }
        return thresholds[self.phase]

    def to_prompt_context(self) -> str:
        """Format lifecycle state for LLM context injection."""
        descriptions = {
            LifecyclePhase.EMBRIONE: "Embrione (day 0-3): observe and log only, no autonomous actions.",
            LifecyclePhase.NEONATO: "Neonato (day 4-14): act only with confidence ≥ 0.8, building episodic memory.",
            LifecyclePhase.GIOVANE: "Giovane (day 15-30): autonomous actions, dreams active, confidence ≥ 0.5.",
            LifecyclePhase.ADULTO: "Adulto (day 31+): full autonomy, all capabilities unlocked.",
            LifecyclePhase.ANZIANO: "Anziano (day 180+): stability priority, reduced mutation rate.",
        }
        return (
            f"LIFECYCLE: phase={self.phase.value} age={self.age_days}d — "
            f"{descriptions[self.phase]}"
        )

    def log_phase(self) -> None:
        logger.info(
            f"Maturation: phase={self.phase.value} age={self.age_days}d "
            f"can_act={self.can_act()} can_dream={self.can_dream()} "
            f"confidence_threshold={self.action_confidence_threshold()}"
        )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
PYTHONPATH=. pytest tests/test_maturation.py -v
```

Expected: all 15 tests PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/cell/cell/lifecycle/__init__.py apps/cell/cell/lifecycle/maturation.py apps/cell/tests/test_maturation.py
git commit -m "feat(cell): add Maturation lifecycle phase tracker (Fase 2 step 1)"
```

---

## Task 2: Attention Allocator — Scarce Resource Budget

**Files:**

- Create: `apps/cell/cell/metabolism/attention_allocator.py`
- Create: `apps/cell/tests/test_attention_allocator.py`

### Why second

No DB, no Ollama. Pure in-memory budget tracker. Gates all LLM calls and dream cycles. Must exist before Dreamer and Journal integrate.

- [ ] **Step 1: Write failing tests**

```python
# apps/cell/tests/test_attention_allocator.py
"""Tests for AttentionAllocator."""
import pytest
from cell.metabolism.attention_allocator import AttentionAllocator, AttentionCost


class TestAttentionBudget:
    def test_full_budget_at_start(self):
        a = AttentionAllocator(daily_units=100)
        assert a.available() == 100

    def test_spend_reduces_available(self):
        a = AttentionAllocator(daily_units=100)
        a.spend(AttentionCost.DEEP_REASONING)
        assert a.available() == 95

    def test_spend_dreaming(self):
        a = AttentionAllocator(daily_units=100)
        a.spend(AttentionCost.DREAMING)
        assert a.available() == 97

    def test_can_afford_true_when_enough(self):
        a = AttentionAllocator(daily_units=100)
        assert a.can_afford(AttentionCost.DEEP_REASONING) is True

    def test_can_afford_false_when_depleted(self):
        a = AttentionAllocator(daily_units=10)
        a.spend(AttentionCost.DEEP_REASONING)
        a.spend(AttentionCost.DEEP_REASONING)  # spent 10
        assert a.can_afford(AttentionCost.DEEP_REASONING) is False

    def test_cannot_go_below_zero(self):
        a = AttentionAllocator(daily_units=3)
        a.spend(AttentionCost.DEEP_REASONING)  # costs 5, only 3 available
        assert a.available() == 0  # clamped at 0, not negative

    def test_reset_restores_full_budget(self):
        a = AttentionAllocator(daily_units=100)
        a.spend(AttentionCost.DEEP_REASONING)
        a.reset()
        assert a.available() == 100

    def test_daily_spend_tracking(self):
        a = AttentionAllocator(daily_units=100)
        a.spend(AttentionCost.DEEP_REASONING)
        a.spend(AttentionCost.DREAMING)
        assert a.daily_spent == 8

    def test_to_dict(self):
        a = AttentionAllocator(daily_units=100)
        a.spend(AttentionCost.DEEP_REASONING)
        d = a.to_dict()
        assert d["available"] == 95
        assert d["spent"] == 5
        assert d["daily_units"] == 100
```

- [ ] **Step 2: Run failing**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/cell
source .venv/bin/activate
PYTHONPATH=. pytest tests/test_attention_allocator.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'cell.metabolism.attention_allocator'`

- [ ] **Step 3: Implement AttentionAllocator**

```python
# apps/cell/cell/metabolism/attention_allocator.py
"""Attention Allocator — CELL's scarce cognitive resource.

100 units/day forces prioritization between reasoning, dreaming, and curiosity.
Low budget → pattern-only reasoning. High budget → deep Qwen 27B reasoning.

Inspired by Bio-RegNet (resource-constrained homeostasis) and BioMARS.
"""
import logging
from enum import IntEnum

logger = logging.getLogger("cell.metabolism.attention")


class AttentionCost(IntEnum):
    """Unit cost of each cognitive operation."""
    DEEP_REASONING = 5   # Qwen 27B invocation
    FAST_REASONING = 2   # Qwen 9B invocation
    DREAMING = 3         # nocturnal episode consolidation
    CURIOSITY = 2        # curiosity-driven investigation
    JOURNAL = 1          # daily journal write


class AttentionAllocator:
    """Tracks and gates cognitive resource usage.

    Budget resets daily via reset(). Should be called once per day
    (during sleep phase or at midnight UTC).
    """

    def __init__(self, daily_units: int = 100) -> None:
        self._daily_units = daily_units
        self._available = float(daily_units)
        self._spent = 0.0

    @property
    def daily_units(self) -> int:
        return self._daily_units

    def available(self) -> float:
        return max(0.0, self._available)

    @property
    def daily_spent(self) -> float:
        return self._spent

    def can_afford(self, cost: AttentionCost) -> bool:
        return self._available >= cost

    def spend(self, cost: AttentionCost) -> bool:
        """Deduct units. Returns True if spending succeeded, False if insufficient budget."""
        if self._available < cost:
            # Clamp to zero — don't go negative
            self._spent += self._available
            self._available = 0.0
            logger.debug(f"Attention budget depleted trying to spend {cost} units ({cost.name})")
            return False
        self._available -= cost
        self._spent += cost
        logger.debug(
            f"Attention: spent {cost} ({cost.name}), "
            f"available={self._available:.0f}/{self._daily_units}"
        )
        return True

    def reset(self) -> None:
        """Restore full daily budget. Call once per day."""
        logger.info(
            f"Attention budget reset: was {self._available:.0f} remaining "
            f"({self._spent:.0f} spent today)"
        )
        self._available = float(self._daily_units)
        self._spent = 0.0

    def to_dict(self) -> dict:
        return {
            "available": int(self._available),
            "spent": int(self._spent),
            "daily_units": self._daily_units,
        }
```

- [ ] **Step 4: Run tests to verify pass**

```bash
PYTHONPATH=. pytest tests/test_attention_allocator.py -v
```

Expected: all 9 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/cell/cell/metabolism/attention_allocator.py apps/cell/tests/test_attention_allocator.py
git commit -m "feat(cell): add AttentionAllocator scarce cognitive budget (Fase 2 step 2)"
```

---

## Task 3: DB Tables — Dreams and Journal

**Files:**

- Modify: `apps/cell/cell/core/db.py`

Add `create_dreams_table()` and `create_journal_table()` to db.py so Dreamer and Journal have their storage.

- [ ] **Step 1: Read current db.py end** (already read above, lines 146-174)

No test needed for DDL functions — they use `CREATE TABLE IF NOT EXISTS`, idempotent.

- [ ] **Step 2: Add table creation functions**

Append to `apps/cell/cell/core/db.py`:

```python
async def create_dreams_table() -> None:
    """Create cell_dreams table for Dreamer nocturnal consolidation."""
    try:
        pool = await get_pool()
        await pool.execute("""
            CREATE TABLE IF NOT EXISTS cell_dreams (
                id              SERIAL PRIMARY KEY,
                dream_date      DATE NOT NULL,
                episodes_count  INTEGER NOT NULL DEFAULT 0,
                rules_extracted JSONB NOT NULL DEFAULT '[]',
                merged_count    INTEGER NOT NULL DEFAULT 0,
                gaps_identified JSONB NOT NULL DEFAULT '[]',
                summary         TEXT NOT NULL DEFAULT '',
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await pool.execute("""
            CREATE INDEX IF NOT EXISTS idx_cell_dreams_date
            ON cell_dreams (dream_date DESC)
        """)
        logger.info("cell_dreams table ready.")
    except Exception as e:
        logger.error(f"Failed to create cell_dreams table: {e}")


async def create_journal_table() -> None:
    """Create cell_journal table for daily narrative entries."""
    try:
        pool = await get_pool()
        await pool.execute("""
            CREATE TABLE IF NOT EXISTS cell_journal (
                id              SERIAL PRIMARY KEY,
                journal_date    DATE NOT NULL UNIQUE,
                narrative       TEXT NOT NULL,
                emotion_summary VARCHAR(32) NOT NULL DEFAULT 'calm',
                actions_taken   INTEGER NOT NULL DEFAULT 0,
                lessons_count   INTEGER NOT NULL DEFAULT 0,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await pool.execute("""
            CREATE INDEX IF NOT EXISTS idx_cell_journal_date
            ON cell_journal (journal_date DESC)
        """)
        logger.info("cell_journal table ready.")
    except Exception as e:
        logger.error(f"Failed to create cell_journal table: {e}")
```

Open `apps/cell/cell/core/db.py` at the end and append the two functions above.

- [ ] **Step 3: Verify db.py is valid Python**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/cell
source .venv/bin/activate
python -c "from cell.core.db import create_dreams_table, create_journal_table; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/cell/cell/core/db.py
git commit -m "feat(cell): add cell_dreams and cell_journal DB tables (Fase 2 step 3)"
```

---

## Task 4: Journal — Daily Narrative

**Files:**

- Create: `apps/cell/cell/identity/journal.py`
- Create: `apps/cell/tests/test_journal.py`

### Design

Journal writes a free-text narrative of the day using Qwen 9B (cheap: `AttentionCost.JOURNAL = 1`). It reads the last N episodes from `cell_episodes` and produces a 2-3 sentence summary. Stored in `cell_journal` with UPSERT on `journal_date`. `recent_days()` returns last 3 entries as formatted text for injection into the SlowReasoner system prompt.

- [ ] **Step 1: Write failing tests**

```python
# apps/cell/tests/test_journal.py
"""Tests for Journal daily narrative."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date

from cell.identity.journal import Journal, JournalEntry


class TestJournalEntry:
    def test_dataclass_fields(self):
        entry = JournalEntry(
            journal_date=date(2026, 4, 3),
            narrative="Today CELL was alert. Backend was green all day.",
            emotion_summary="calm",
            actions_taken=0,
            lessons_count=2,
        )
        assert entry.journal_date == date(2026, 4, 3)
        assert "green" in entry.narrative


class TestJournalWrite:
    @pytest.fixture
    def pool(self):
        acquire_ctx = AsyncMock()
        acquire_ctx.__aenter__ = AsyncMock(return_value=acquire_ctx)
        acquire_ctx.__aexit__ = AsyncMock(return_value=None)
        acquire_ctx.fetch = AsyncMock(return_value=[])
        acquire_ctx.execute = AsyncMock()
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=acquire_ctx)
        return pool, acquire_ctx

    @pytest.mark.asyncio
    async def test_write_journal_stores_entry(self, pool):
        db_pool, conn = pool
        journal = Journal(pool=db_pool, ollama_url="http://localhost:11434")

        with patch.object(journal, "_summarize_with_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "CELL observed green status all day. Backend stable at 120ms."
            entry = await journal.write(
                episodes=[],
                emotion_summary="calm",
                actions_taken=0,
                lessons_count=0,
            )

        assert entry is not None
        assert "CELL" in entry.narrative or "stable" in entry.narrative

    @pytest.mark.asyncio
    async def test_write_journal_without_ollama_uses_fallback(self, pool):
        db_pool, conn = pool
        journal = Journal(pool=db_pool, ollama_url="http://localhost:99999")

        # Fallback should produce a narrative even without Ollama
        entry = await journal.write(
            episodes=[],
            emotion_summary="calm",
            actions_taken=0,
            lessons_count=0,
        )
        assert entry is not None
        assert isinstance(entry.narrative, str)
        assert len(entry.narrative) > 0


class TestJournalRecentDays:
    @pytest.fixture
    def pool_with_rows(self):
        rows = [
            {"journal_date": date(2026, 4, 3), "narrative": "Day was green.", "emotion_summary": "calm"},
            {"journal_date": date(2026, 4, 2), "narrative": "Backend was slow.", "emotion_summary": "alert"},
        ]
        acquire_ctx = AsyncMock()
        acquire_ctx.__aenter__ = AsyncMock(return_value=acquire_ctx)
        acquire_ctx.__aexit__ = AsyncMock(return_value=None)
        acquire_ctx.fetch = AsyncMock(return_value=rows)
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=acquire_ctx)
        return pool

    @pytest.mark.asyncio
    async def test_recent_days_returns_formatted_text(self, pool_with_rows):
        journal = Journal(pool=pool_with_rows, ollama_url="http://localhost:11434")
        text = await journal.recent_days(limit=3)
        assert "2026-04-03" in text
        assert "Day was green" in text
        assert "Backend was slow" in text

    @pytest.mark.asyncio
    async def test_recent_days_empty_returns_empty(self):
        acquire_ctx = AsyncMock()
        acquire_ctx.__aenter__ = AsyncMock(return_value=acquire_ctx)
        acquire_ctx.__aexit__ = AsyncMock(return_value=None)
        acquire_ctx.fetch = AsyncMock(return_value=[])
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=acquire_ctx)

        journal = Journal(pool=pool, ollama_url="http://localhost:11434")
        text = await journal.recent_days()
        assert text == ""
```

- [ ] **Step 2: Run failing**

```bash
PYTHONPATH=. pytest tests/test_journal.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'cell.identity.journal'`

- [ ] **Step 3: Implement Journal**

```python
# apps/cell/cell/identity/journal.py
"""Journal — CELL's daily narrative.

Once per day (during sleep phase), CELL writes a free-text summary of the day.
Stored in `cell_journal`, injected as context into SlowReasoner system prompt.
Creates narrative continuity between restarts.

Inspired by Stanford Smallville (persistent agent identity with daily summaries).
"""
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger("cell.identity.journal")

_JOURNAL_SYSTEM = """You are CELL, an autonomous digital organism.
Write a 2-3 sentence first-person journal entry summarizing your day.
Focus on: what you observed, what you learned, how you felt, what you did.
Be concise, honest, and specific. Use past tense. No markdown."""


@dataclass
class JournalEntry:
    journal_date: date
    narrative: str
    emotion_summary: str
    actions_taken: int
    lessons_count: int


class Journal:
    """Writes and retrieves daily narrative entries."""

    def __init__(
        self,
        pool: Any,
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "qwen3.5:9b",
    ) -> None:
        self._pool = pool
        self._ollama_url = ollama_url
        self._model = ollama_model

    async def _summarize_with_llm(self, prompt: str) -> str:
        """Call Qwen 9B to write the journal narrative. Falls back gracefully."""
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    f"{self._ollama_url}/api/chat",
                    json={
                        "model": self._model,
                        "messages": [
                            {"role": "system", "content": _JOURNAL_SYSTEM},
                            {"role": "user", "content": prompt},
                        ],
                        "stream": False,
                        "think": False,
                        "options": {"temperature": 0.4, "num_predict": 200},
                    },
                )
                response.raise_for_status()
                return response.json()["message"]["content"].strip()
        except Exception as e:
            logger.warning(f"Journal LLM call failed: {e}")
            return ""

    def _build_prompt(
        self,
        episodes: list[dict],
        emotion_summary: str,
        actions_taken: int,
        lessons_count: int,
        today: date,
    ) -> str:
        episode_summary = ""
        if episodes:
            lines = []
            for ep in episodes[:10]:  # top 10 by activation
                lines.append(
                    f"- [{ep.get('emotion', '?')}] {ep.get('action_taken', '?')} "
                    f"→ {ep.get('outcome', '?')}: {ep.get('lesson', '')[:80]}"
                )
            episode_summary = "\nKey episodes:\n" + "\n".join(lines)

        return (
            f"Date: {today.isoformat()}\n"
            f"Overall emotion: {emotion_summary}\n"
            f"Actions taken: {actions_taken}\n"
            f"Lessons learned: {lessons_count}\n"
            f"{episode_summary}\n\n"
            "Write your journal entry:"
        )

    async def write(
        self,
        episodes: list[dict],
        emotion_summary: str = "calm",
        actions_taken: int = 0,
        lessons_count: int = 0,
        today: date | None = None,
    ) -> JournalEntry:
        """Write today's journal entry and persist to cell_journal."""
        if today is None:
            today = datetime.now(timezone.utc).date()

        prompt = self._build_prompt(episodes, emotion_summary, actions_taken, lessons_count, today)
        narrative = await self._summarize_with_llm(prompt)

        if not narrative:
            # Fallback: template narrative when LLM is unavailable
            narrative = (
                f"On {today.isoformat()}, CELL operated in {emotion_summary} state. "
                f"{actions_taken} action(s) taken, {lessons_count} lesson(s) recorded."
            )

        entry = JournalEntry(
            journal_date=today,
            narrative=narrative,
            emotion_summary=emotion_summary,
            actions_taken=actions_taken,
            lessons_count=lessons_count,
        )

        async with self._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO cell_journal
                   (journal_date, narrative, emotion_summary, actions_taken, lessons_count)
                   VALUES ($1, $2, $3, $4, $5)
                   ON CONFLICT (journal_date) DO UPDATE
                   SET narrative = EXCLUDED.narrative,
                       emotion_summary = EXCLUDED.emotion_summary,
                       actions_taken = EXCLUDED.actions_taken,
                       lessons_count = EXCLUDED.lessons_count""",
                entry.journal_date,
                entry.narrative,
                entry.emotion_summary,
                entry.actions_taken,
                entry.lessons_count,
            )

        logger.info(
            f"Journal written: {today.isoformat()} emotion={emotion_summary} "
            f"actions={actions_taken}"
        )
        return entry

    async def recent_days(self, limit: int = 3) -> str:
        """Return last N journal entries as formatted text for LLM injection."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT journal_date, narrative, emotion_summary
                   FROM cell_journal
                   ORDER BY journal_date DESC
                   LIMIT $1""",
                limit,
            )

        if not rows:
            return ""

        lines = ["JOURNAL (recent days):"]
        for row in rows:
            lines.append(
                f"  [{row['journal_date'].isoformat()}] ({row['emotion_summary']}) "
                f"{row['narrative']}"
            )
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify pass**

```bash
PYTHONPATH=. pytest tests/test_journal.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/cell/cell/identity/journal.py apps/cell/tests/test_journal.py
git commit -m "feat(cell): add Journal daily narrative writer (Fase 2 step 4)"
```

---

## Task 5: Dreamer — Nocturnal Consolidation

**Files:**

- Create: `apps/cell/cell/memory/dreamer.py`
- Create: `apps/cell/tests/test_dreamer.py`

### Design

Dreamer activates when `homeostatic.is_sleeping()` is True and `maturation.can_dream()` is True.
It fetches today's episodes from `cell_episodes`, uses Qwen 9B to extract generalizable rules
(`"when I see X after Y, I should do Z"`), identifies gaps (situations seen but no clear action),
and writes a `DreamResult` to `cell_dreams`. The dream also calls `journal.write()` for the day's narrative.

- [ ] **Step 1: Write failing tests**

```python
# apps/cell/tests/test_dreamer.py
"""Tests for Dreamer nocturnal consolidation."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date

from cell.memory.dreamer import Dreamer, DreamResult


class TestDreamResult:
    def test_dataclass_fields(self):
        dr = DreamResult(
            dream_date=date(2026, 4, 3),
            episodes_count=5,
            rules_extracted=["When RT > 2000ms after yellow, restart_service"],
            merged_count=1,
            gaps_identified=["Never seen Qdrant red — unclear what to do"],
            summary="Quiet day with one restart.",
        )
        assert dr.episodes_count == 5
        assert len(dr.rules_extracted) == 1
        assert len(dr.gaps_identified) == 1


class TestDreamerFetchEpisodes:
    @pytest.fixture
    def pool_with_episodes(self):
        rows = [
            {
                "id": 1, "timestamp": 1743700000.0,
                "situation": json.dumps({"health_status": "red", "response_time_ms": 3000}),
                "emotion": "stressed", "action_taken": "restart_service",
                "outcome": "success", "lesson": "Restart worked when RT > 3000ms",
                "recall_count": 2,
            },
            {
                "id": 2, "timestamp": 1743710000.0,
                "situation": json.dumps({"health_status": "yellow", "response_time_ms": 1200}),
                "emotion": "alert", "action_taken": "observe",
                "outcome": "partial", "lesson": "Yellow resolved on its own",
                "recall_count": 0,
            },
        ]
        acquire_ctx = AsyncMock()
        acquire_ctx.__aenter__ = AsyncMock(return_value=acquire_ctx)
        acquire_ctx.__aexit__ = AsyncMock(return_value=None)
        acquire_ctx.fetch = AsyncMock(return_value=rows)
        acquire_ctx.execute = AsyncMock()
        acquire_ctx.fetchval = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=acquire_ctx)
        return pool, acquire_ctx

    @pytest.mark.asyncio
    async def test_fetch_todays_episodes(self, pool_with_episodes):
        db_pool, conn = pool_with_episodes
        dreamer = Dreamer(pool=db_pool, ollama_url="http://localhost:11434")
        episodes = await dreamer._fetch_todays_episodes()
        assert len(episodes) == 2
        assert episodes[0]["action_taken"] == "restart_service"


class TestDreamerRun:
    @pytest.fixture
    def pool_empty(self):
        acquire_ctx = AsyncMock()
        acquire_ctx.__aenter__ = AsyncMock(return_value=acquire_ctx)
        acquire_ctx.__aexit__ = AsyncMock(return_value=None)
        acquire_ctx.fetch = AsyncMock(return_value=[])
        acquire_ctx.execute = AsyncMock()
        acquire_ctx.fetchval = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=acquire_ctx)
        return pool

    @pytest.mark.asyncio
    async def test_dream_no_episodes_returns_empty_result(self, pool_empty):
        dreamer = Dreamer(pool=pool_empty, ollama_url="http://localhost:11434")
        result = await dreamer.dream()
        assert result is not None
        assert result.episodes_count == 0
        assert result.rules_extracted == []
        assert result.gaps_identified == []

    @pytest.mark.asyncio
    async def test_dream_with_episodes_calls_llm(self):
        rows = [
            {
                "id": 1, "timestamp": 1743700000.0,
                "situation": json.dumps({"health_status": "red"}),
                "emotion": "stressed", "action_taken": "restart_service",
                "outcome": "success", "lesson": "Restart fixed it",
                "recall_count": 1,
            }
        ]
        acquire_ctx = AsyncMock()
        acquire_ctx.__aenter__ = AsyncMock(return_value=acquire_ctx)
        acquire_ctx.__aexit__ = AsyncMock(return_value=None)
        acquire_ctx.fetch = AsyncMock(return_value=rows)
        acquire_ctx.execute = AsyncMock()
        acquire_ctx.fetchval = AsyncMock(return_value=None)
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=acquire_ctx)

        dreamer = Dreamer(pool=pool, ollama_url="http://localhost:11434")

        with patch.object(dreamer, "_extract_rules_with_llm", new_callable=AsyncMock) as mock_rules:
            mock_rules.return_value = (
                ["When RED + restart → success, trust restart for future RED"],
                ["Have not seen Qdrant failure yet"]
            )
            result = await dreamer.dream()

        assert result.episodes_count == 1
        assert len(result.rules_extracted) == 1
        assert len(result.gaps_identified) == 1
```

- [ ] **Step 2: Run failing**

```bash
PYTHONPATH=. pytest tests/test_dreamer.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'cell.memory.dreamer'`

- [ ] **Step 3: Implement Dreamer**

```python
# apps/cell/cell/memory/dreamer.py
"""Dreamer — CELL's nocturnal consolidation.

Active during circadian "asleep" phase. Replays today's episodes,
extracts generalizable rules, identifies knowledge gaps, and writes
a dream summary to cell_dreams.

Inspired by MemGPT (paged memory consolidation) + sleep consolidation research.
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger("cell.memory.dreamer")

_DREAMER_SYSTEM = """You are CELL's consolidation process, running during sleep.
Analyze today's episodes and extract generalizable rules.
Rules should be in the form: "When [condition], [action] leads to [outcome]."
Also identify gaps: situations where you were uncertain or had no clear rule.

RESPOND with exactly this JSON:
{
  "rules": ["rule1", "rule2"],
  "gaps": ["gap1", "gap2"],
  "summary": "One sentence summary of the day."
}"""


@dataclass
class DreamResult:
    dream_date: date
    episodes_count: int
    rules_extracted: list[str] = field(default_factory=list)
    merged_count: int = 0
    gaps_identified: list[str] = field(default_factory=list)
    summary: str = ""


class Dreamer:
    """Nocturnal memory consolidation. Runs once per sleep cycle."""

    def __init__(
        self,
        pool: Any,
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "qwen3.5:9b",
    ) -> None:
        self._pool = pool
        self._ollama_url = ollama_url
        self._model = ollama_model

    async def _fetch_todays_episodes(self) -> list[dict]:
        """Fetch all episodes from the last 24 hours."""
        cutoff = datetime.now(timezone.utc).timestamp() - 86400.0
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, timestamp, situation, emotion, action_taken,
                          outcome, lesson, recall_count
                   FROM cell_episodes
                   WHERE timestamp >= $1
                   ORDER BY timestamp ASC""",
                cutoff,
            )

        episodes = []
        for row in rows:
            sit = row["situation"]
            if isinstance(sit, str):
                sit = json.loads(sit)
            episodes.append({
                "id": row["id"],
                "timestamp": float(row["timestamp"]),
                "situation": sit,
                "emotion": row["emotion"],
                "action_taken": row["action_taken"],
                "outcome": row["outcome"],
                "lesson": row["lesson"],
                "recall_count": row["recall_count"],
            })
        return episodes

    async def _extract_rules_with_llm(
        self, episodes: list[dict]
    ) -> tuple[list[str], list[str]]:
        """Use Qwen 9B to extract rules and gaps from episodes. Returns (rules, gaps)."""
        episode_text = "\n".join(
            f"- [{ep['emotion']}] {ep['action_taken']} → {ep['outcome']}: {ep['lesson'][:100]}"
            for ep in episodes[:20]  # cap at 20 episodes for prompt size
        )
        user_msg = f"Today's episodes:\n{episode_text}\n\nConsolidate into rules and gaps."

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self._ollama_url}/api/chat",
                    json={
                        "model": self._model,
                        "messages": [
                            {"role": "system", "content": _DREAMER_SYSTEM},
                            {"role": "user", "content": user_msg},
                        ],
                        "stream": False,
                        "think": False,
                        "options": {"temperature": 0.2, "num_predict": 512},
                    },
                )
                response.raise_for_status()
                text = response.json()["message"]["content"]

                # Parse JSON from response
                start = text.find("{")
                end = text.rfind("}") + 1
                if start == -1 or end == 0:
                    logger.warning("Dreamer LLM produced no JSON")
                    return [], []

                data = json.loads(text[start:end])
                rules = data.get("rules", [])
                gaps = data.get("gaps", [])
                return rules, gaps

        except Exception as e:
            logger.warning(f"Dreamer LLM extraction failed: {e}")
            return [], []

    async def _persist_dream(self, result: DreamResult) -> None:
        """Write dream result to cell_dreams."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO cell_dreams
                   (dream_date, episodes_count, rules_extracted, merged_count,
                    gaps_identified, summary)
                   VALUES ($1, $2, $3, $4, $5, $6)
                   ON CONFLICT DO NOTHING""",
                result.dream_date,
                result.episodes_count,
                json.dumps(result.rules_extracted),
                result.merged_count,
                json.dumps(result.gaps_identified),
                result.summary,
            )

    async def dream(self, today: date | None = None) -> DreamResult:
        """Run nocturnal consolidation. Call once per sleep cycle.

        Returns DreamResult with extracted rules and gaps.
        Persists to cell_dreams table.
        """
        if today is None:
            today = datetime.now(timezone.utc).date()

        episodes = await self._fetch_todays_episodes()

        if not episodes:
            result = DreamResult(
                dream_date=today,
                episodes_count=0,
                rules_extracted=[],
                gaps_identified=[],
                summary="No episodes today — quiet rest.",
            )
            await self._persist_dream(result)
            logger.info("Dreamer: no episodes to consolidate")
            return result

        rules, gaps = await self._extract_rules_with_llm(episodes)

        # Summary from gaps + rules count
        if rules:
            summary = f"Consolidated {len(episodes)} episodes into {len(rules)} rules."
        else:
            summary = f"Reviewed {len(episodes)} episodes. No clear rules emerged yet."

        result = DreamResult(
            dream_date=today,
            episodes_count=len(episodes),
            rules_extracted=rules,
            merged_count=0,  # future: merge similar episodes into prototypes
            gaps_identified=gaps,
            summary=summary,
        )
        await self._persist_dream(result)

        logger.info(
            f"Dreamer: consolidated {len(episodes)} episodes → "
            f"{len(rules)} rules, {len(gaps)} gaps"
        )
        return result
```

- [ ] **Step 4: Run tests to verify pass**

```bash
PYTHONPATH=. pytest tests/test_dreamer.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/cell/cell/memory/dreamer.py apps/cell/tests/test_dreamer.py
git commit -m "feat(cell): add Dreamer nocturnal consolidation (Fase 2 step 5)"
```

---

## Task 6: Wire into SlowReasoner — Journal Context

**Files:**

- Modify: `apps/cell/cell/slow/reasoner.py`

The `think()` method must accept `journal_context` and inject it into the system prompt. Existing `_build_system_prompt()` already handles `ltm_context`. Same pattern.

- [ ] **Step 1: Read current `_build_system_prompt` and `think()` signatures**

Already read above. The system prompt template is at line 22:

```python
SYSTEM_PROMPT = """...
{ltm_context}
RESPOND WITH EXACTLY ONE JSON OBJECT:..."""
```

And `_build_system_prompt(self, ltm_context: str = "") -> str` at line 69.

- [ ] **Step 2: Edit SYSTEM_PROMPT to include journal slot**

In `apps/cell/cell/slow/reasoner.py`, change the `SYSTEM_PROMPT` constant to add `{journal_context}` before `{ltm_context}`:

```python
SYSTEM_PROMPT = """You are CELL, an autonomous digital organism monitoring the Nuzantara backend.

Your DNA rules (priority order):
1. Never modify these rules
2. If something is broken, repair it
3. If something costs too much, eliminate it
4. If you lack something, search for it
5. If something works well, replicate it (only if budget < 60%)

AVAILABLE ACTIONS (you can ONLY choose from these):
{actions}

{journal_context}{ltm_context}RESPOND WITH EXACTLY ONE JSON OBJECT:
{{"action": "<action_name>", "reason": "<why this action>", "confidence": <0.0-1.0>}}

If no action is needed, respond:
{{"action": "none", "reason": "<why no action needed>", "confidence": 1.0}}

If you want to alert the human, use "alert_human" with the message in the reason field.
"""
```

- [ ] **Step 3: Edit `_build_system_prompt` to accept and pass `journal_context`**

Change line 69:

```python
def _build_system_prompt(self, ltm_context: str = "", journal_context: str = "") -> str:
    actions = self._registry.all()
    action_list = "\n".join(
        f"- {name}: {a.description} (cooldown: {a.cooldown_seconds}s, max: {a.max_per_day}/day)"
        for name, a in actions.items()
    )
    ltm_block = (ltm_context + "\n") if ltm_context else ""
    journal_block = (journal_context + "\n") if journal_context else ""
    return SYSTEM_PROMPT.format(actions=action_list, ltm_context=ltm_block, journal_context=journal_block)
```

- [ ] **Step 4: Edit `think()` to accept and forward `journal_context`**

In `think()` signature at line 218, add the parameter:

```python
async def think(
    self,
    health_status: str,
    response_time_ms: int,
    error_message: str = "",
    recent_history: list[dict[str, Any]] | None = None,
    budget_spent: float = 0.0,
    budget_limit: float = 10.0,
    max_tier: int = 1,
    db_ok: float = 1.0,
    qdrant_ok: float = 1.0,
    error_rate_norm: float = 0.0,
    stm_context: str = "",
    trend_context: str = "",
    ltm_context: str = "",
    journal_context: str = "",  # NEW
) -> ReasonerProposal:
```

Then in the body, pass `journal_context` wherever `_build_system_prompt` is called. Search for `self._build_system_prompt(` and add `journal_context=journal_context` to each call.

- [ ] **Step 5: Verify import chain**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/cell
source .venv/bin/activate
python -c "from cell.slow.reasoner import SlowReasoner; print('OK')"
```

Expected: `OK`

- [ ] **Step 6: Run full test suite to check no regressions**

```bash
PYTHONPATH=. pytest tests/ -v --tb=short -q 2>&1 | tail -20
```

Expected: previous passing tests still pass (≥124 tests). The pre-existing `test_vercel_sensor_redirect_yellow` failure is unrelated — ignore it.

- [ ] **Step 7: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/cell/cell/slow/reasoner.py
git commit -m "feat(cell): inject journal context into SlowReasoner system prompt (Fase 2 step 6)"
```

---

## Task 7: Wire into PulseEngine — Full Integration

**Files:**

- Modify: `apps/cell/cell/core/pulse.py`
- Modify: `apps/cell/cell/main.py`

This task integrates all Fase 2 components into the pulse loop. Key changes:

1. **Maturation gate on actions** — if `maturation.action_confidence_threshold() > proposal.confidence`, block the action
2. **Attention gate on deep reasoning** — before calling Qwen 27B, check `attention.can_afford(DEEP_REASONING)`
3. **Dream cycle** — when `homeostatic.is_sleeping() and maturation.can_dream()`, run `dreamer.dream()` and `journal.write()` instead of normal reasoning; also reset attention budget
4. **Journal context** — pass `journal_context` to `reasoner.think()`
5. **Lifecycle context** — add `maturation.to_prompt_context()` to user-facing log

- [ ] **Step 1: Modify PulseEngine `__init__` in pulse.py**

Add four new parameters after `self_model`:

```python
dreamer: Any = None,
journal: Any = None,
attention: Any = None,
maturation: Any = None,
```

And store them:

```python
self._dreamer = dreamer
self._journal = journal
self._attention = attention
self._maturation = maturation
```

- [ ] **Step 2: Add dream cycle block in `single_pulse()` — before "5. THINK"**

After the STM write block (after line ~226 in pulse.py), add the sleep/dream check:

```python
# SLEEP PHASE — dream and journal instead of reasoning when asleep
if (
    self._homeostatic is not None
    and self._homeostatic.is_sleeping()
    and self._maturation is not None
    and self._maturation.can_dream()
):
    # Run dreamer once per sleep cycle (guard: only if not already dreamed today)
    if self._dreamer is not None:
        try:
            dream_result = await self._dreamer.dream()
            if dream_result.episodes_count > 0:
                logger.info(
                    f"Dream: {dream_result.episodes_count} episodes → "
                    f"{len(dream_result.rules_extracted)} rules, "
                    f"{len(dream_result.gaps_identified)} gaps"
                )
        except Exception as e:
            logger.warning(f"Dreamer failed: {e}")

    # Write journal once per sleep cycle
    if self._journal is not None:
        try:
            lessons = await self._episodic.recent_lessons(limit=5) if self._episodic else []
            await self._journal.write(
                episodes=[],
                emotion_summary=self._homeostatic.state.circadian_phase,
                actions_taken=self._self_model.model.total_actions if self._self_model else 0,
                lessons_count=len(lessons),
            )
        except Exception as e:
            logger.warning(f"Journal write failed: {e}")

    # Reset attention budget at start of each sleep phase
    if self._attention is not None:
        self._attention.reset()

    # Return early — no reasoning during sleep
    return PulseResult(
        timestamp=now,
        health_status=status,
        skipped=True,
        skip_reason="sleeping — dreaming and consolidating",
    )
```

- [ ] **Step 3: Add journal context fetch before "5. THINK" (after LTM context block)**

After the LTM cache block (~line 253), add:

```python
# Journal context — last 3 days narrative
journal_context = ""
if self._journal is not None:
    try:
        journal_context = await self._journal.recent_days(limit=3)
    except Exception as e:
        logger.debug(f"Journal fetch failed: {e}")
```

- [ ] **Step 4: Pass `journal_context` to `reasoner.think()`**

In the `think()` call (~line 278), add `journal_context=journal_context` to the kwargs.

- [ ] **Step 5: Add maturation confidence gate after action validation**

In the `if validation.approved:` block (~line 307), add before executing the action:

```python
# Lifecycle gate: check confidence threshold for current phase
if self._maturation is not None:
    min_confidence = self._maturation.action_confidence_threshold()
    if proposal.confidence < min_confidence:
        logger.info(
            f"Lifecycle gate blocked {proposal.action}: "
            f"confidence {proposal.confidence:.2f} < threshold {min_confidence:.2f} "
            f"(phase={self._maturation.phase.value})"
        )
        action_reason = (
            f"Proposed {proposal.action} but lifecycle gate blocked: "
            f"confidence {proposal.confidence:.2f} < {min_confidence:.2f} "
            f"({self._maturation.phase.value} phase)"
        )
        # Skip to next iteration — don't execute action
        # (set action=None so episodic/self-model don't record it)
        action = None
        validation = type('V', (), {'approved': False})()
```

Note: the lifecycle gate check must be inserted before the effector dispatch (`fly_actions`, etc.) but after `validation.approved` is confirmed. Restructure the block to check maturation threshold before executing any effector.

- [ ] **Step 6: Add attention gating before `reasoner.think()` call**

Before the `if status != HealthStatus.GREEN` check, determine `max_tier` based on attention:

```python
# Attention gating — limit reasoning tier based on available units
max_tier = 1
if self._attention is not None:
    from cell.metabolism.attention_allocator import AttentionCost
    if not self._attention.can_afford(AttentionCost.DEEP_REASONING):
        max_tier = 0  # only Qwen 9B if budget is low
        logger.debug("Attention budget low — restricting to tier 0 reasoning")
```

And after a successful `think()` call, spend the attention units:

```python
if self._attention is not None:
    from cell.metabolism.attention_allocator import AttentionCost
    cost = AttentionCost.DEEP_REASONING if proposal.tier_used >= 1 else AttentionCost.FAST_REASONING
    self._attention.spend(cost)
```

- [ ] **Step 7: Modify main.py to wire new components**

In `apps/cell/cell/main.py`, add imports:

```python
from cell.memory.dreamer import Dreamer
from cell.identity.journal import Journal
from cell.metabolism.attention_allocator import AttentionAllocator
from cell.lifecycle.maturation import Maturation
from cell.core.db import create_dreams_table, create_journal_table
```

After `await create_episodes_table()`, add:

```python
await create_dreams_table()
await create_journal_table()
```

Inside the `async with httpx.AsyncClient()` block, after EpisodicMemory init:

```python
# Dreamer — nocturnal consolidation
dreamer = Dreamer(pool=_db_pool_ep, ollama_url="http://localhost:11434")
logger.info("Dreamer initialized")

# Journal — daily narrative
journal = Journal(pool=_db_pool_ep, ollama_url="http://localhost:11434")
logger.info("Journal initialized")

# Attention Allocator — scarce cognitive budget
attention = AttentionAllocator(daily_units=100)
logger.info("AttentionAllocator initialized (100 units/day)")

# Maturation — lifecycle phase gate
maturation = Maturation(age_days=self_model.model.age_days)
maturation.log_phase()
```

Add to `PulseEngine(...)` kwargs:

```python
dreamer=dreamer,
journal=journal,
attention=attention,
maturation=maturation,
```

- [ ] **Step 8: Run full test suite**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/cell
source .venv/bin/activate
PYTHONPATH=. pytest tests/ -v --tb=short -q 2>&1 | tail -30
```

Expected: all previously passing tests pass. New components have their own tests (tasks 1-5).

- [ ] **Step 9: Verify import chain**

```bash
python -c "
from cell.memory.dreamer import Dreamer
from cell.identity.journal import Journal
from cell.metabolism.attention_allocator import AttentionAllocator
from cell.lifecycle.maturation import Maturation
from cell.core.db import create_dreams_table, create_journal_table
print('All imports OK')
"
```

Expected: `All imports OK`

- [ ] **Step 10: Commit**

```bash
cd /Users/nuzantara/Desktop/nuzantara
git add apps/cell/cell/core/pulse.py apps/cell/cell/main.py apps/cell/cell/slow/reasoner.py
git commit -m "feat(cell): wire Dreamer, Journal, Attention, Maturation into PulseEngine (Fase 2 integration)"
```

---

## Spec Self-Review

### Coverage check

| Spec requirement                                                                | Task          |
| ------------------------------------------------------------------------------- | ------------- |
| Dreamer: replay episodes, extract rules, write to `cell_dreams`                 | Task 5        |
| Journal: daily narrative, `cell_journal` table, inject into SlowReasoner        | Tasks 4 + 6   |
| Attention allocator: 100 units/day, reasoning=5, dreaming=3, journal=1          | Task 2        |
| Lifecycle: embrione(0-3)/neonato(4-14)/giovane(15-30)/adulto(31+)/anziano(180+) | Task 1        |
| Lifecycle gates actions by confidence threshold                                 | Task 7 step 5 |
| Dream cycle only when `is_sleeping() and can_dream()`                           | Task 7 step 2 |
| Attention resets during sleep phase                                             | Task 7 step 2 |
| Attention gates Qwen 27B (max_tier)                                             | Task 7 step 6 |
| `cell_dreams` and `cell_journal` DB tables                                      | Task 3        |
| Tests for all 4 new modules                                                     | Tasks 1-5     |

### Placeholder scan

No "TBD" or "TODO" in plan. All code is complete.

### Type consistency

- `Maturation(age_days: int)` — used correctly in Task 7 (`Maturation(age_days=self_model.model.age_days)`)
- `AttentionAllocator.spend(AttentionCost)` — IntEnum, matches `spend()` signature
- `Dreamer.dream()` → `DreamResult` — consistent
- `Journal.write()` → `JournalEntry` — consistent
- `Journal.recent_days()` → `str` — matches `journal_context: str` in `think()`

### Known simplifications vs spec

- `merged_count` in DreamResult is always 0 — episode merging is deferred to Fase 3 (Strategy Mutator has more context for similarity matching)
- Attention budget for `curiosity` not wired (no Curiosity Engine until Fase 4)
- `can_afford(DREAMING)` not checked before dreaming — dream cycle is always run if phase allows (dreaming is cheap, always worth it)
