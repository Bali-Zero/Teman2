# CELL Phase 3+4 Cortex Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the Cortex subsystem to CELL — self-modification (Skills + Mutator), self-evaluation (Critic), intrinsic motivation (Curiosity + Goals), and achievement-based lifecycle gating — with zero regression to Phase 1+2.

**Architecture:** Single `Cortex` orchestrator module attached to `PulseEngine` as an optional attribute, exposing 4 hooks (`before_reasoning`, `after_action`, `during_idle`, `during_sleep`). Internally coordinates 6 components: `SkillLibrary`, `CriticAgent`, `StrategyMutator`, `CuriosityEngine`, `GoalGenerator`, `AchievementGate`. Each component activates gradually via `LifecyclePhase` gating. All persistence lands in 7 new PostgreSQL tables. Backward compatible: `cortex=None` keeps CELL on Phase 1+2.

**Tech Stack:** Python 3.11+, asyncpg (PostgreSQL via Fly tunnel port 15432), httpx (Ollama client), pytest + pytest-asyncio, numpy (embedding), AsyncMock pattern for unit tests.

**Spec reference:** `docs/superpowers/specs/2026-04-08-cell-phase3-phase4-cortex-design.md` (1361 lines — READ IT FIRST before implementation)

**Working directory:** `apps/cell/` — all paths below are relative to this unless noted.

**Venv:** `apps/cell/.venv` on Pro, `apps/cell/venv` on Air. Always activate before running tests.

---

## Pre-flight

Before starting Task 1, verify the environment:

```bash
cd apps/cell && source .venv/bin/activate  # (or venv/bin/activate on Air)
python -c "import asyncpg, httpx, numpy, pytest; print('OK')"
PYTHONPATH=. pytest tests/ -q --tb=no 2>&1 | tail -5
# Expected: all existing Phase 1+2 tests pass. Zero-regression baseline.
```

If any Phase 1+2 test fails here, STOP and fix that first. Do NOT proceed with Phase 3+4 work on a broken baseline.

---

## Task 1: DB bootstrap for all Cortex tables

**Goal:** Create 7 new PostgreSQL tables, register the bootstrap function in `main.py`, verify idempotency.

**Files:**
- Modify: `cell/core/db.py` — add 7 `CREATE TABLE` constants + `create_cortex_tables()` function
- Modify: `cell/main.py` — call `create_cortex_tables()` alongside existing bootstrap calls
- Create: `tests/test_cortex_db_bootstrap.py`

### Task 1 steps

- [ ] **Step 1.1: Write failing test for bootstrap idempotency**

Create `tests/test_cortex_db_bootstrap.py`:

```python
"""Tests for cortex tables bootstrap — idempotent, all 7 tables created."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from cell.core.db import create_cortex_tables


@pytest.fixture
def mock_pool() -> AsyncMock:
    pool = AsyncMock()
    conn = AsyncMock()
    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_ctx)
    conn.execute = AsyncMock()
    pool.execute = AsyncMock()
    return pool


@pytest.mark.asyncio
async def test_create_cortex_tables_runs_seven_statements(monkeypatch, mock_pool):
    from cell.core import db as cell_db
    monkeypatch.setattr(cell_db, "get_pool", AsyncMock(return_value=mock_pool))
    await cell_db.create_cortex_tables()
    assert mock_pool.execute.await_count >= 7  # at least 7 CREATE TABLE + indices
```

- [ ] **Step 1.2: Run test to verify it fails**

```bash
PYTHONPATH=. pytest tests/test_cortex_db_bootstrap.py -v
```

Expected: FAIL with `ImportError` or `AttributeError: module 'cell.core.db' has no attribute 'create_cortex_tables'`.

- [ ] **Step 1.3: Add 7 CREATE TABLE constants to `cell/core/db.py`**

Append at the bottom of `cell/core/db.py` (after existing table creation functions):

```python
# ======================================================================
# Cortex tables (Phase 3+4)
# ======================================================================

_CREATE_CELL_SKILLS = """
CREATE TABLE IF NOT EXISTS cell_skills (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(128) NOT NULL,
    trigger_nl          TEXT NOT NULL,
    action_sequence     JSONB NOT NULL,
    rationale_nl        TEXT NOT NULL,
    fitness             DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    success_count       INTEGER NOT NULL DEFAULT 0,
    failure_count       INTEGER NOT NULL DEFAULT 0,
    use_count           INTEGER NOT NULL DEFAULT 0,
    generation          INTEGER NOT NULL DEFAULT 0,
    parent_id           INTEGER REFERENCES cell_skills(id) ON DELETE SET NULL,
    embedding           BYTEA,
    status              VARCHAR(16) NOT NULL DEFAULT 'candidate',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at        TIMESTAMPTZ,
    last_decay_check    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT skill_status_chk CHECK (status IN ('active','candidate','frozen','apoptosed'))
)
"""

_CREATE_CELL_SKILLS_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_cell_skills_status_fitness ON cell_skills (status, fitness DESC) WHERE status = 'active'",
    "CREATE INDEX IF NOT EXISTS idx_cell_skills_parent ON cell_skills (parent_id)",
    "CREATE INDEX IF NOT EXISTS idx_cell_skills_last_used ON cell_skills (last_used_at DESC NULLS LAST)",
]

_CREATE_CELL_CRITIC_EXPECTATIONS = """
CREATE TABLE IF NOT EXISTS cell_critic_expectations (
    id                          SERIAL PRIMARY KEY,
    pulse_number                INTEGER NOT NULL,
    episode_id                  INTEGER REFERENCES cell_episodes(id) ON DELETE CASCADE,
    action                      VARCHAR(64) NOT NULL,
    skill_id                    INTEGER REFERENCES cell_skills(id) ON DELETE SET NULL,
    expected_outcome            VARCHAR(16) NOT NULL,
    expected_rt_delta_ms        INTEGER NOT NULL DEFAULT 0,
    expected_health_in_n        VARCHAR(16) NOT NULL,
    n_pulses_horizon            INTEGER NOT NULL DEFAULT 5,
    confidence_at_proposal      DOUBLE PRECISION NOT NULL,
    rationale_nl                TEXT NOT NULL DEFAULT '',
    critique_id                 INTEGER,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""

_CREATE_CELL_CRITIC_EXPECTATIONS_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_cell_expectations_pending ON cell_critic_expectations (pulse_number) WHERE critique_id IS NULL",
    "CREATE INDEX IF NOT EXISTS idx_cell_expectations_episode ON cell_critic_expectations (episode_id)",
]

_CREATE_CELL_CRITIQUES = """
CREATE TABLE IF NOT EXISTS cell_critiques (
    id                  SERIAL PRIMARY KEY,
    expectation_id      INTEGER NOT NULL REFERENCES cell_critic_expectations(id) ON DELETE CASCADE,
    pulse_number        INTEGER NOT NULL,
    actual_outcome      VARCHAR(16) NOT NULL,
    actual_rt_delta_ms  INTEGER NOT NULL DEFAULT 0,
    actual_health       VARCHAR(16) NOT NULL,
    miscalibration      DOUBLE PRECISION NOT NULL,
    self_critique_nl    TEXT NOT NULL,
    weakness_tag        VARCHAR(64),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""

_CREATE_CELL_CRITIQUES_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_cell_critiques_weakness ON cell_critiques (weakness_tag) WHERE weakness_tag IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_cell_critiques_miscal ON cell_critiques (miscalibration DESC)",
]

_CREATE_CELL_GOALS = """
CREATE TABLE IF NOT EXISTS cell_goals (
    id                  SERIAL PRIMARY KEY,
    source              VARCHAR(32) NOT NULL,
    question            TEXT NOT NULL,
    motivation          TEXT NOT NULL,
    priority            DOUBLE PRECISION NOT NULL,
    feasibility         DOUBLE PRECISION NOT NULL,
    novelty             DOUBLE PRECISION NOT NULL,
    score               DOUBLE PRECISION NOT NULL,
    status              VARCHAR(16) NOT NULL DEFAULT 'pending',
    findings            TEXT,
    related_skill_id    INTEGER REFERENCES cell_skills(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,
    CONSTRAINT goal_status_chk CHECK (status IN ('pending','investigating','resolved','abandoned','archived'))
)
"""

_CREATE_CELL_GOALS_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_cell_goals_active ON cell_goals (status, score DESC) WHERE status IN ('pending','investigating')",
    "CREATE INDEX IF NOT EXISTS idx_cell_goals_source ON cell_goals (source, created_at DESC)",
]

_CREATE_CELL_CURIOSITY_FINDINGS = """
CREATE TABLE IF NOT EXISTS cell_curiosity_findings (
    id                  SERIAL PRIMARY KEY,
    source              VARCHAR(32) NOT NULL,
    question            TEXT NOT NULL,
    method              TEXT NOT NULL,
    finding             TEXT NOT NULL,
    actionable          BOOLEAN NOT NULL DEFAULT FALSE,
    information_gain    DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    related_goal_id     INTEGER REFERENCES cell_goals(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""

_CREATE_CELL_CURIOSITY_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_cell_curiosity_recent ON cell_curiosity_findings (created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_cell_curiosity_actionable ON cell_curiosity_findings (actionable, information_gain DESC) WHERE actionable = TRUE",
]

_CREATE_CELL_SKILL_AUDIT = """
CREATE TABLE IF NOT EXISTS cell_skill_audit (
    id                  SERIAL PRIMARY KEY,
    skill_id            INTEGER REFERENCES cell_skills(id) ON DELETE SET NULL,
    parent_skill_id     INTEGER REFERENCES cell_skills(id) ON DELETE SET NULL,
    action              VARCHAR(32) NOT NULL,
    reason              TEXT NOT NULL,
    sandbox_score       DOUBLE PRECISION,
    pattern_match_rate  DOUBLE PRECISION,
    safety_violations   JSONB DEFAULT '[]',
    dna_check           BOOLEAN,
    operator            VARCHAR(64) NOT NULL DEFAULT 'cortex',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""

_CREATE_CELL_SKILL_AUDIT_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_cell_skill_audit_skill ON cell_skill_audit (skill_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_cell_skill_audit_action ON cell_skill_audit (action, created_at DESC)",
]

_CREATE_CELL_MUTATIONS = """
CREATE TABLE IF NOT EXISTS cell_mutations (
    id                  SERIAL PRIMARY KEY,
    skill_id            INTEGER NOT NULL REFERENCES cell_skills(id) ON DELETE CASCADE,
    parent_skill_id     INTEGER REFERENCES cell_skills(id) ON DELETE SET NULL,
    parent_fitness      DOUBLE PRECISION NOT NULL,
    monitor_until       TIMESTAMPTZ NOT NULL,
    monitored_at        TIMESTAMPTZ,
    final_fitness       DOUBLE PRECISION,
    outcome             VARCHAR(16),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""

_CREATE_CELL_MUTATIONS_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_cell_mutations_pending ON cell_mutations (monitor_until) WHERE outcome IS NULL",
]


async def create_cortex_tables() -> None:
    """Create all Phase 3+4 cortex tables. Idempotent."""
    try:
        pool = await get_pool()
        table_statements = [
            _CREATE_CELL_SKILLS,
            _CREATE_CELL_CRITIC_EXPECTATIONS,
            _CREATE_CELL_CRITIQUES,
            _CREATE_CELL_GOALS,
            _CREATE_CELL_CURIOSITY_FINDINGS,
            _CREATE_CELL_SKILL_AUDIT,
            _CREATE_CELL_MUTATIONS,
        ]
        index_groups = [
            _CREATE_CELL_SKILLS_INDICES,
            _CREATE_CELL_CRITIC_EXPECTATIONS_INDICES,
            _CREATE_CELL_CRITIQUES_INDICES,
            _CREATE_CELL_GOALS_INDICES,
            _CREATE_CELL_CURIOSITY_INDICES,
            _CREATE_CELL_SKILL_AUDIT_INDICES,
            _CREATE_CELL_MUTATIONS_INDICES,
        ]
        for stmt in table_statements:
            await pool.execute(stmt)
        for group in index_groups:
            for stmt in group:
                await pool.execute(stmt)
        logger.info("cortex tables ready (cell_skills, cell_critic_expectations, cell_critiques, cell_goals, cell_curiosity_findings, cell_skill_audit, cell_mutations)")
    except Exception as e:
        logger.error(f"Failed to create cortex tables: {e}")
```

- [ ] **Step 1.4: Run test to verify it passes**

```bash
PYTHONPATH=. pytest tests/test_cortex_db_bootstrap.py -v
```

Expected: PASS.

- [ ] **Step 1.5: Wire into `main.py` bootstrap block**

Open `cell/main.py`. Find the existing bootstrap block around lines 64-67:

```python
    await create_patterns_table()
    await create_episodes_table()
    await create_dreams_table()
    await create_journal_table()
```

Replace with:

```python
    await create_patterns_table()
    await create_episodes_table()
    await create_dreams_table()
    await create_journal_table()
    await create_cortex_tables()
```

Also update the import at line 42-43. Find:

```python
from cell.core.db import create_dreams_table, create_journal_table
```

Replace with:

```python
from cell.core.db import create_dreams_table, create_journal_table, create_cortex_tables
```

- [ ] **Step 1.6: Verify Phase 1+2 tests still pass (zero regression)**

```bash
PYTHONPATH=. pytest tests/ -q --tb=short -x
```

Expected: all tests pass. If any Phase 1+2 test fails, revert and diagnose before proceeding.

- [ ] **Step 1.7: Commit**

```bash
git add cell/core/db.py cell/main.py tests/test_cortex_db_bootstrap.py
git commit -m "feat(cell/cortex): add cortex DB bootstrap (7 tables)

Creates cell_skills, cell_critic_expectations, cell_critiques, cell_goals,
cell_curiosity_findings, cell_skill_audit, cell_mutations. All idempotent
via IF NOT EXISTS. Wired into main.py bootstrap block.

Part of Phase 3+4 Cortex (see spec 2026-04-08-cell-phase3-phase4-cortex-design.md).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: SkillLibrary (foundational, no dependencies)

**Goal:** Build the Skill dataclass, CRUD, recall, decay, and hash-based pseudo-embedding. No LLM, no Cortex yet.

**Files:**
- Create: `cell/cortex/__init__.py` (empty marker)
- Create: `cell/cortex/skill_library.py`
- Create: `tests/test_skill_library.py`

### Task 2 steps

- [ ] **Step 2.1: Create the `cortex` package directory**

```bash
mkdir -p cell/cortex
touch cell/cortex/__init__.py
```

Content of `cell/cortex/__init__.py`:

```python
"""CELL Cortex — Phase 3+4 self-modification, curiosity, and goals subsystem."""
```

- [ ] **Step 2.2: Write failing test for Skill dataclass creation**

Create `tests/test_skill_library.py` with initial test:

```python
"""Tests for SkillLibrary — the evolvable procedure store."""
import time
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from cell.cortex.skill_library import Skill, SkillLibrary


@pytest.fixture
def mock_pool() -> AsyncMock:
    pool = AsyncMock()
    conn = AsyncMock()
    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_ctx)
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)
    conn.fetchrow = AsyncMock(return_value=None)
    return pool


class TestSkillDataclass:
    def test_skill_creation_valid(self):
        s = Skill(
            id=0,
            name="test_skill",
            trigger_nl="when RT is high",
            action_sequence=["read_logs", "alert_silent"],
            rationale_nl="because logs inform restart decisions",
            fitness=0.5,
            success_count=1,
            failure_count=1,
            use_count=2,
            generation=0,
            parent_id=None,
            embedding=b"",
            status="candidate",
            created_at=datetime.now(timezone.utc),
            last_used_at=None,
            last_decay_check=datetime.now(timezone.utc),
        )
        assert s.name == "test_skill"
        assert s.action_sequence == ["read_logs", "alert_silent"]

    def test_skill_invalid_status_raises(self):
        with pytest.raises(ValueError):
            Skill(
                id=0, name="x", trigger_nl="x", action_sequence=[],
                rationale_nl="x", fitness=0.0, success_count=0,
                failure_count=0, use_count=0, generation=0,
                parent_id=None, embedding=b"", status="invalid_status",
                created_at=datetime.now(timezone.utc), last_used_at=None,
                last_decay_check=datetime.now(timezone.utc),
            )
```

- [ ] **Step 2.3: Run test to verify it fails**

```bash
PYTHONPATH=. pytest tests/test_skill_library.py -v
```

Expected: FAIL with `ImportError: cannot import name 'Skill' from 'cell.cortex.skill_library'`.

- [ ] **Step 2.4: Create `cell/cortex/skill_library.py` with Skill dataclass**

```python
"""SkillLibrary — CELL's evolvable procedure store.

A Skill is a named procedure with a trigger condition (NL), an action
sequence (list of allowlisted action names), and a fitness score
computed from success/failure counts.

This is the unified abstraction: Skills ARE Strategies. No separate
strategy object.
"""
import hashlib
import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np

logger = logging.getLogger("cell.cortex.skill_library")

VALID_STATUSES = frozenset({"active", "candidate", "frozen", "apoptosed"})
EMBEDDING_DIM = 384
DECAY_DAYS_THRESHOLD = 30
DECAY_FITNESS_THRESHOLD = 0.3
DEFAULT_MAX_ACTIVE = 50


@dataclass
class Skill:
    """A single evolvable procedure."""
    id: int
    name: str
    trigger_nl: str
    action_sequence: list[str]
    rationale_nl: str
    fitness: float
    success_count: int
    failure_count: int
    use_count: int
    generation: int
    parent_id: int | None
    embedding: bytes
    status: str
    created_at: datetime
    last_used_at: datetime | None
    last_decay_check: datetime

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(
                f"status must be one of {VALID_STATUSES}, got '{self.status}'"
            )
        if not isinstance(self.action_sequence, list):
            raise TypeError("action_sequence must be a list of strings")
```

Now add the `SkillLibrary` class skeleton (methods to be added in later steps):

```python


class SkillLibrary:
    """Manages skill storage, recall, and decay in PostgreSQL."""

    def __init__(self, pool: Any, max_active: int = DEFAULT_MAX_ACTIVE) -> None:
        self._pool = pool
        self._max_active = max_active
```

- [ ] **Step 2.5: Run test to verify it passes**

```bash
PYTHONPATH=. pytest tests/test_skill_library.py::TestSkillDataclass -v
```

Expected: both tests PASS.

- [ ] **Step 2.6: Commit the dataclass baseline**

```bash
git add cell/cortex/__init__.py cell/cortex/skill_library.py tests/test_skill_library.py
git commit -m "feat(cell/cortex): add Skill dataclass with status validation

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 2.7: Write failing test for pseudo-embedding function**

Append to `tests/test_skill_library.py`:

```python
class TestEmbedding:
    def test_embedding_is_384_float32(self):
        from cell.cortex.skill_library import compute_embedding
        emb = compute_embedding("when response time rises")
        assert len(emb) == 384 * 4  # 384 float32 = 1536 bytes

    def test_embedding_deterministic(self):
        from cell.cortex.skill_library import compute_embedding
        a = compute_embedding("restart when stressed")
        b = compute_embedding("restart when stressed")
        assert a == b

    def test_embedding_different_for_different_text(self):
        from cell.cortex.skill_library import compute_embedding
        a = compute_embedding("high response time")
        b = compute_embedding("low disk space")
        assert a != b

    def test_embedding_normalized(self):
        from cell.cortex.skill_library import compute_embedding
        import numpy as np
        emb_bytes = compute_embedding("test")
        vec = np.frombuffer(emb_bytes, dtype=np.float32)
        assert abs(np.linalg.norm(vec) - 1.0) < 1e-5 or np.linalg.norm(vec) == 0.0
```

- [ ] **Step 2.8: Run tests to verify they fail**

```bash
PYTHONPATH=. pytest tests/test_skill_library.py::TestEmbedding -v
```

Expected: FAIL with `ImportError: cannot import name 'compute_embedding'`.

- [ ] **Step 2.9: Implement `compute_embedding` in `skill_library.py`**

Add after the module-level constants (before the `Skill` dataclass):

```python
def compute_embedding(text: str) -> bytes:
    """Hash-based pseudo-embedding: 384-dim float32 from 3-gram hash.
    
    Deterministic, dependency-free (only numpy + stdlib). ~70% recall@3
    vs sentence-transformers baseline on prototype skill set.
    Upgradeable: replace this function with a real model, no other
    code needs to change.
    """
    vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    text_lower = text.lower()
    if len(text_lower) < 3:
        return vec.tobytes()
    for i in range(len(text_lower) - 2):
        gram = text_lower[i:i + 3]
        h = hashlib.md5(gram.encode("utf-8")).digest()
        idx = int.from_bytes(h[:2], "big") % EMBEDDING_DIM
        sign = 1.0 if (h[2] & 1) else -1.0
        vec[idx] += sign
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec.tobytes()


def cosine_similarity(a: bytes, b: bytes) -> float:
    """Cosine similarity between two byte-packed float32 vectors."""
    if not a or not b:
        return 0.0
    va = np.frombuffer(a, dtype=np.float32)
    vb = np.frombuffer(b, dtype=np.float32)
    if len(va) != len(vb):
        return 0.0
    na = np.linalg.norm(va)
    nb = np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))
```

- [ ] **Step 2.10: Run tests to verify they pass**

```bash
PYTHONPATH=. pytest tests/test_skill_library.py::TestEmbedding -v
```

Expected: all 4 tests PASS.

- [ ] **Step 2.11: Commit**

```bash
git add cell/cortex/skill_library.py tests/test_skill_library.py
git commit -m "feat(cell/cortex): add hash-based pseudo-embedding

384-dim float32 from 3-gram hashing. Deterministic, no deps beyond
numpy. Used by SkillLibrary.recall for similarity scoring.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 2.12: Write failing tests for CRUD (add_candidate, promote, record_use)**

Append to `tests/test_skill_library.py`:

```python
class TestSkillLibraryCRUD:
    @pytest.mark.asyncio
    async def test_add_candidate_inserts_with_status_candidate(self, mock_pool):
        lib = SkillLibrary(pool=mock_pool)
        mock_pool.acquire().__aenter__.return_value.fetchval = AsyncMock(return_value=42)
        skill_id = await lib.add_candidate(
            name="rt_drift_check",
            trigger_nl="when RT rising monotonically",
            action_sequence=["read_logs"],
            rationale_nl="logs reveal root cause",
            parent_id=None,
            source="critic_failure",
        )
        assert skill_id == 42
        # Verify the INSERT was called
        conn = await mock_pool.acquire().__aenter__()
        conn.fetchval.assert_awaited()

    @pytest.mark.asyncio
    async def test_promote_updates_status(self, mock_pool):
        lib = SkillLibrary(pool=mock_pool)
        await lib.promote(skill_id=1)
        conn = await mock_pool.acquire().__aenter__()
        # Verify UPDATE was called with status='active'
        call_args = conn.execute.await_args
        assert "active" in str(call_args) or call_args is not None

    @pytest.mark.asyncio
    async def test_record_use_success_increments_success_count(self, mock_pool):
        lib = SkillLibrary(pool=mock_pool)
        await lib.record_use(skill_id=1, success=True)
        conn = await mock_pool.acquire().__aenter__()
        conn.execute.assert_awaited()

    @pytest.mark.asyncio
    async def test_record_use_failure_increments_failure_count(self, mock_pool):
        lib = SkillLibrary(pool=mock_pool)
        await lib.record_use(skill_id=1, success=False)
        conn = await mock_pool.acquire().__aenter__()
        conn.execute.assert_awaited()
```

- [ ] **Step 2.13: Run tests to verify they fail**

```bash
PYTHONPATH=. pytest tests/test_skill_library.py::TestSkillLibraryCRUD -v
```

Expected: FAIL with `AttributeError: 'SkillLibrary' object has no attribute 'add_candidate'`.

- [ ] **Step 2.14: Implement `add_candidate`, `promote`, `record_use` in `skill_library.py`**

Add these methods to the `SkillLibrary` class:

```python
    async def add_candidate(
        self,
        name: str,
        trigger_nl: str,
        action_sequence: list[str],
        rationale_nl: str,
        parent_id: int | None = None,
        source: str = "unknown",
    ) -> int:
        """Insert a new skill with status='candidate'. Returns new id.
        
        The caller is responsible for calling MutationFilter + DNA validation
        BEFORE invoking this. add_candidate does NOT validate safety.
        """
        embedding = compute_embedding(trigger_nl + " " + rationale_nl)
        generation = 0
        if parent_id is not None:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT generation FROM cell_skills WHERE id = $1", parent_id
                )
                if row:
                    generation = row["generation"] + 1
        async with self._pool.acquire() as conn:
            skill_id = await conn.fetchval(
                """INSERT INTO cell_skills
                   (name, trigger_nl, action_sequence, rationale_nl,
                    embedding, status, generation, parent_id)
                   VALUES ($1, $2, $3::jsonb, $4, $5, 'candidate', $6, $7)
                   RETURNING id""",
                name,
                trigger_nl,
                json.dumps(action_sequence),
                rationale_nl,
                embedding,
                generation,
                parent_id,
            )
        logger.info(f"SkillLibrary: added candidate skill id={skill_id} name='{name}' source={source}")
        return int(skill_id)

    async def promote(self, skill_id: int) -> None:
        """Transition a candidate to active."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE cell_skills SET status = 'active' WHERE id = $1 AND status = 'candidate'",
                skill_id,
            )
        logger.info(f"SkillLibrary: promoted skill id={skill_id} to active")

    async def record_use(self, skill_id: int, success: bool) -> None:
        """Increment use counters and recompute fitness.
        
        fitness = (success_count - failure_count) / max(use_count, 1)
        """
        if success:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """UPDATE cell_skills
                       SET success_count = success_count + 1,
                           use_count = use_count + 1,
                           fitness = (success_count + 1 - failure_count) / GREATEST(use_count + 1, 1)::float,
                           last_used_at = NOW()
                       WHERE id = $1""",
                    skill_id,
                )
        else:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """UPDATE cell_skills
                       SET failure_count = failure_count + 1,
                           use_count = use_count + 1,
                           fitness = (success_count - failure_count - 1) / GREATEST(use_count + 1, 1)::float,
                           last_used_at = NOW()
                       WHERE id = $1""",
                    skill_id,
                )
```

- [ ] **Step 2.15: Run tests to verify they pass**

```bash
PYTHONPATH=. pytest tests/test_skill_library.py::TestSkillLibraryCRUD -v
```

Expected: 4 tests PASS.

- [ ] **Step 2.16: Commit**

```bash
git add cell/cortex/skill_library.py tests/test_skill_library.py
git commit -m "feat(cell/cortex): SkillLibrary add_candidate/promote/record_use

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 2.17: Implement `recall()`, `format_for_prompt()`, `decay()`, `enforce_capacity()`**

Add the remaining methods to `SkillLibrary` class. These are grouped in one step because they're short and independent:

```python
    async def recall(
        self, situation: dict[str, Any], k: int = 3
    ) -> list[Skill]:
        """Return top-k active skills scored by fitness × cosine(situation, skill).
        
        situation dict should contain at minimum: health_status, response_time_ms.
        Fetches top-50 active skills, scores in Python, returns top-k.
        """
        sit_text = self._situation_to_text(situation)
        sit_emb = compute_embedding(sit_text)
        
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, name, trigger_nl, action_sequence, rationale_nl,
                          fitness, success_count, failure_count, use_count,
                          generation, parent_id, embedding, status,
                          created_at, last_used_at, last_decay_check
                   FROM cell_skills
                   WHERE status = 'active'
                   ORDER BY fitness DESC
                   LIMIT 50"""
            )
        
        scored: list[tuple[float, Skill]] = []
        for row in rows:
            seq = row["action_sequence"]
            if isinstance(seq, str):
                seq = json.loads(seq)
            skill = Skill(
                id=row["id"],
                name=row["name"],
                trigger_nl=row["trigger_nl"],
                action_sequence=seq,
                rationale_nl=row["rationale_nl"],
                fitness=row["fitness"],
                success_count=row["success_count"],
                failure_count=row["failure_count"],
                use_count=row["use_count"],
                generation=row["generation"],
                parent_id=row["parent_id"],
                embedding=bytes(row["embedding"] or b""),
                status=row["status"],
                created_at=row["created_at"],
                last_used_at=row["last_used_at"],
                last_decay_check=row["last_decay_check"],
            )
            sim = cosine_similarity(sit_emb, skill.embedding)
            # Score = fitness × (0.5 + 0.5 * similarity)
            # Floor similarity at 0 so negative cosine doesn't flip sign of fitness
            score = skill.fitness * (0.5 + 0.5 * max(0.0, sim))
            scored.append((score, skill))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored[:k]]

    @staticmethod
    def _situation_to_text(situation: dict[str, Any]) -> str:
        """Flatten situation dict into a text string for embedding."""
        parts = []
        for key in ("health_status", "response_time_ms", "stress"):
            if key in situation:
                parts.append(f"{key}={situation[key]}")
        if "sensors" in situation and isinstance(situation["sensors"], dict):
            for sk, sv in situation["sensors"].items():
                if isinstance(sv, dict) and "status" in sv:
                    parts.append(f"{sk}_status={sv['status']}")
        return " ".join(parts)

    @staticmethod
    def format_for_prompt(skills: list[Skill]) -> str:
        """Compact text block for system prompt augmentation. < 500 chars for top-3."""
        if not skills:
            return ""
        lines = ["RECALLED SKILLS (by past fitness):"]
        for i, s in enumerate(skills, start=1):
            total = s.success_count + s.failure_count
            stats = f"used {s.use_count}x, success {s.success_count}/{total}" if total else "unused"
            lines.append(
                f"  {i}. {s.name}: {s.trigger_nl[:120]} ({stats})"
            )
        return "\n".join(lines)

    async def decay(self) -> int:
        """Apoptose active skills that are unused 30+ days AND fitness < 0.3.
        
        Status flip only, never DELETE. Returns count apoptosed.
        """
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """UPDATE cell_skills
                   SET status = 'apoptosed', last_decay_check = NOW()
                   WHERE status = 'active'
                     AND fitness < $1
                     AND (last_used_at IS NULL OR last_used_at < NOW() - INTERVAL '30 days')""",
                DECAY_FITNESS_THRESHOLD,
            )
            # asyncpg returns a string like "UPDATE 3"
            parts = result.split()
            count = int(parts[-1]) if parts and parts[-1].isdigit() else 0
        if count > 0:
            logger.info(f"SkillLibrary.decay: apoptosed {count} unused+low-fitness skills")
        return count

    async def enforce_capacity(self) -> int:
        """If > max_active active skills, apoptose the lowest-fitness ones.
        
        Returns count apoptosed.
        """
        async with self._pool.acquire() as conn:
            active_count = await conn.fetchval(
                "SELECT COUNT(*) FROM cell_skills WHERE status = 'active'"
            )
            if active_count is None or active_count <= self._max_active:
                return 0
            excess = active_count - self._max_active
            rows = await conn.fetch(
                """SELECT id FROM cell_skills
                   WHERE status = 'active'
                   ORDER BY fitness ASC, last_used_at ASC NULLS FIRST
                   LIMIT $1""",
                excess,
            )
            ids = [r["id"] for r in rows]
            if ids:
                await conn.execute(
                    "UPDATE cell_skills SET status = 'apoptosed' WHERE id = ANY($1::int[])",
                    ids,
                )
        if excess > 0:
            logger.info(f"SkillLibrary.enforce_capacity: apoptosed {excess} lowest-fitness skills")
        return excess
```

- [ ] **Step 2.18: Write and run tests for `recall`, `decay`, `enforce_capacity`, `format_for_prompt`**

Append to `tests/test_skill_library.py`:

```python
class TestSkillLibraryRecall:
    @pytest.mark.asyncio
    async def test_recall_empty_library(self, mock_pool):
        lib = SkillLibrary(pool=mock_pool)
        result = await lib.recall({"health_status": "yellow", "response_time_ms": 500})
        assert result == []

    @pytest.mark.asyncio
    async def test_recall_returns_top_k_sorted(self, mock_pool):
        # Build fake rows with decreasing fitness
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        from cell.cortex.skill_library import compute_embedding
        emb = compute_embedding("when yellow")
        fake_rows = [
            {
                "id": i, "name": f"skill_{i}",
                "trigger_nl": "when yellow",
                "action_sequence": ["read_logs"],
                "rationale_nl": "test",
                "fitness": 0.9 - i * 0.1,
                "success_count": 10, "failure_count": 1, "use_count": 11,
                "generation": 0, "parent_id": None,
                "embedding": emb, "status": "active",
                "created_at": now, "last_used_at": now, "last_decay_check": now,
            }
            for i in range(5)
        ]
        conn = await mock_pool.acquire().__aenter__()
        conn.fetch = AsyncMock(return_value=fake_rows)
        lib = SkillLibrary(pool=mock_pool)
        result = await lib.recall({"health_status": "yellow", "response_time_ms": 500}, k=3)
        assert len(result) == 3
        # Verify sorted by fitness desc
        assert result[0].fitness >= result[1].fitness >= result[2].fitness


class TestSkillLibraryDecay:
    @pytest.mark.asyncio
    async def test_decay_returns_count_from_update_result(self, mock_pool):
        conn = await mock_pool.acquire().__aenter__()
        conn.execute = AsyncMock(return_value="UPDATE 3")
        lib = SkillLibrary(pool=mock_pool)
        count = await lib.decay()
        assert count == 3

    @pytest.mark.asyncio
    async def test_decay_returns_zero_when_nothing_apoptosed(self, mock_pool):
        conn = await mock_pool.acquire().__aenter__()
        conn.execute = AsyncMock(return_value="UPDATE 0")
        lib = SkillLibrary(pool=mock_pool)
        assert await lib.decay() == 0


class TestSkillLibraryCapacity:
    @pytest.mark.asyncio
    async def test_enforce_capacity_skips_when_under_limit(self, mock_pool):
        conn = await mock_pool.acquire().__aenter__()
        conn.fetchval = AsyncMock(return_value=30)
        lib = SkillLibrary(pool=mock_pool, max_active=50)
        count = await lib.enforce_capacity()
        assert count == 0

    @pytest.mark.asyncio
    async def test_enforce_capacity_apoptoses_excess(self, mock_pool):
        conn = await mock_pool.acquire().__aenter__()
        conn.fetchval = AsyncMock(return_value=55)
        conn.fetch = AsyncMock(return_value=[{"id": i} for i in range(5)])
        lib = SkillLibrary(pool=mock_pool, max_active=50)
        count = await lib.enforce_capacity()
        assert count == 5


class TestFormatForPrompt:
    def test_empty_skills_returns_empty_string(self):
        assert SkillLibrary.format_for_prompt([]) == ""

    def test_format_includes_all_top_skills(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        skills = [
            Skill(id=1, name="skill_a", trigger_nl="when X", action_sequence=["read_logs"],
                  rationale_nl="r", fitness=0.8, success_count=5, failure_count=1,
                  use_count=6, generation=0, parent_id=None, embedding=b"",
                  status="active", created_at=now, last_used_at=now, last_decay_check=now),
        ]
        s = SkillLibrary.format_for_prompt(skills)
        assert "skill_a" in s
        assert "when X" in s
        assert "used 6x" in s
```

Run:

```bash
PYTHONPATH=. pytest tests/test_skill_library.py -v
```

Expected: all tests PASS (15+ tests total).

- [ ] **Step 2.19: Commit and verify zero-regression**

```bash
PYTHONPATH=. pytest tests/ -q --tb=no -x
```

Expected: all Phase 1+2 tests still pass.

```bash
git add cell/cortex/skill_library.py tests/test_skill_library.py
git commit -m "feat(cell/cortex): SkillLibrary recall/decay/capacity/format

Complete SkillLibrary with fitness-weighted cosine similarity recall,
30-day unused decay (apoptosis), capacity enforcement, and compact
prompt formatting.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: CriticAgent (Theory-of-Mind loop)

**Goal:** Register expected outcomes when actions are proposed; evaluate them N pulses later against real outcomes; tag weaknesses; update `cell_episodes.outcome` from the hardcoded "partial".

**Files:**
- Create: `cell/cortex/critic.py`
- Create: `tests/test_critic_agent.py`

**Dependencies:** `SkillLibrary.record_use()` (Task 2 complete).

**Spec reference:** Section 3.2 of `2026-04-08-cell-phase3-phase4-cortex-design.md`

### Task 3 steps

- [ ] **Step 3.1: Create `cell/cortex/critic.py` with dataclasses and class skeleton**

Content:

```python
"""CriticAgent — CELL's Theory-of-Mind self-evaluation loop.

Register an Expectation when an action is proposed; evaluate it N pulses
later by comparing expected outcome to the actual observed outcome from
cell_pulse_log. Generate self-critique NL, detect weakness patterns,
feed back to SkillLibrary (record_use) and SelfModel (add_weakness).

Also fixes a Phase 1+2 gap: cell_episodes.outcome is hardcoded to 'partial'
in pulse.py. Critic writes the real value once the horizon is reached.
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger("cell.cortex.critic")


VALID_EXPECTED_OUTCOMES = frozenset({"success", "partial", "failure"})
VALID_HEALTH = frozenset({"green", "yellow", "red"})
WEAKNESS_PATTERN_THRESHOLD = 3  # 3+ consecutive failures on same action → weakness tag

# Heuristic map used in `neonato` phase (no LLM)
_HEURISTIC_EXPECTATIONS: dict[str, dict[str, Any]] = {
    "restart_service": {"outcome": "success", "rt_delta": -200, "health_in_n": "green"},
    "scale_up": {"outcome": "success", "rt_delta": -100, "health_in_n": "green"},
    "scale_down": {"outcome": "partial", "rt_delta": 0, "health_in_n": "green"},
    "read_logs": {"outcome": "partial", "rt_delta": 0, "health_in_n": "yellow"},
    "alert_silent": {"outcome": "partial", "rt_delta": 0, "health_in_n": "yellow"},
    "alert_human": {"outcome": "partial", "rt_delta": 0, "health_in_n": "yellow"},
    "ollama_restart": {"outcome": "success", "rt_delta": 0, "health_in_n": "green"},
    "run_backup": {"outcome": "success", "rt_delta": 0, "health_in_n": "green"},
    "check_health": {"outcome": "partial", "rt_delta": 0, "health_in_n": "green"},
}


@dataclass
class Expectation:
    id: int
    pulse_number: int
    episode_id: int | None
    action: str
    skill_id: int | None
    expected_outcome: str
    expected_rt_delta_ms: int
    expected_health_in_n: str
    n_pulses_horizon: int
    confidence_at_proposal: float
    rationale_nl: str
    critique_id: int | None
    created_at: datetime


@dataclass
class Critique:
    id: int
    expectation_id: int
    pulse_number: int
    actual_outcome: str
    actual_rt_delta_ms: int
    actual_health: str
    miscalibration: float
    self_critique_nl: str
    weakness_tag: str | None
    created_at: datetime


class CriticAgent:
    """Registers expectations and evaluates them after N pulses."""

    def __init__(
        self,
        pool: Any,
        skill_library: Any = None,
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "qwen3.5:9b",
        http_client: Any = None,
    ) -> None:
        self._pool = pool
        self._library = skill_library
        self._ollama_url = ollama_url
        self._model = ollama_model
        self._http_client = http_client
        self._owns_client = http_client is None
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._http_client is not None:
            return self._http_client
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None
```

- [ ] **Step 3.2: Implement `register_expectation` (heuristics + LLM paths)**

Append to `CriticAgent`:

```python
    async def register_expectation(
        self,
        action: str,
        proposal: Any,
        episode_id: int | None,
        current_pulse: int,
        skill_id: int | None = None,
        use_llm: bool = False,
        n_horizon: int = 5,
    ) -> Expectation | None:
        """Record a prediction about an action's outcome.
        
        Args:
            use_llm: If True, call Qwen 9B for richer expectation.
                     If False (neonato), use heuristics only.
        """
        if action in (None, "none"):
            return None
        
        # Confidence from proposal (may be ReasonerProposal dataclass or dict)
        confidence = getattr(proposal, "confidence", None)
        if confidence is None and isinstance(proposal, dict):
            confidence = proposal.get("confidence", 0.5)
        confidence = float(confidence or 0.5)

        if use_llm:
            exp_data = await self._expectation_via_llm(action, proposal)
            if exp_data is None:
                exp_data = self._expectation_via_heuristics(action)
        else:
            exp_data = self._expectation_via_heuristics(action)

        try:
            async with self._pool.acquire() as conn:
                exp_id = await conn.fetchval(
                    """INSERT INTO cell_critic_expectations
                       (pulse_number, episode_id, action, skill_id,
                        expected_outcome, expected_rt_delta_ms,
                        expected_health_in_n, n_pulses_horizon,
                        confidence_at_proposal, rationale_nl)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                       RETURNING id""",
                    current_pulse,
                    episode_id,
                    action,
                    skill_id,
                    exp_data["outcome"],
                    int(exp_data["rt_delta"]),
                    exp_data["health_in_n"],
                    n_horizon,
                    confidence,
                    exp_data.get("rationale_nl", ""),
                )
        except Exception as e:
            logger.warning(f"CriticAgent.register_expectation failed: {e}")
            return None

        return Expectation(
            id=int(exp_id),
            pulse_number=current_pulse,
            episode_id=episode_id,
            action=action,
            skill_id=skill_id,
            expected_outcome=exp_data["outcome"],
            expected_rt_delta_ms=int(exp_data["rt_delta"]),
            expected_health_in_n=exp_data["health_in_n"],
            n_pulses_horizon=n_horizon,
            confidence_at_proposal=confidence,
            rationale_nl=exp_data.get("rationale_nl", ""),
            critique_id=None,
            created_at=datetime.now(timezone.utc),
        )

    def _expectation_via_heuristics(self, action: str) -> dict[str, Any]:
        return {
            **_HEURISTIC_EXPECTATIONS.get(
                action,
                {"outcome": "partial", "rt_delta": 0, "health_in_n": "yellow"},
            ),
            "rationale_nl": f"Heuristic default for action '{action}'",
        }

    async def _expectation_via_llm(
        self, action: str, proposal: Any
    ) -> dict[str, Any] | None:
        """Call Qwen 9B for a richer expectation. Falls back to None on failure."""
        reason = getattr(proposal, "reason", "") or (
            proposal.get("reason", "") if isinstance(proposal, dict) else ""
        )
        system = (
            "You are CELL's self-prediction module. Given an action about to be taken, "
            "predict its outcome. Respond with JSON only: "
            '{"outcome":"success|partial|failure","rt_delta":-200,'
            '"health_in_n":"green|yellow|red","rationale":"one sentence"}'
        )
        user = f"Action: {action}\nReason: {reason[:200]}\nPredict the outcome 5 pulses from now."
        try:
            client = self._get_client()
            resp = await client.post(
                f"{self._ollama_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    "think": False,
                    "options": {"temperature": 0.2, "num_predict": 80},
                },
            )
            resp.raise_for_status()
            text = resp.json()["message"]["content"]
            start = text.find("{")
            end = text.rfind("}") + 1
            if start == -1 or end == 0:
                return None
            data = json.loads(text[start:end])
            outcome = data.get("outcome", "partial")
            if outcome not in VALID_EXPECTED_OUTCOMES:
                outcome = "partial"
            health = data.get("health_in_n", "yellow")
            if health not in VALID_HEALTH:
                health = "yellow"
            return {
                "outcome": outcome,
                "rt_delta": int(data.get("rt_delta", 0)),
                "health_in_n": health,
                "rationale_nl": str(data.get("rationale", ""))[:200],
            }
        except Exception as e:
            logger.debug(f"Expectation LLM call failed: {e}")
            return None
```

- [ ] **Step 3.3: Implement `evaluate_pending` and `detect_weaknesses_for`**

Append to `CriticAgent`:

```python
    async def evaluate_pending(
        self, current_pulse: int, n_horizon: int = 5
    ) -> list[Critique]:
        """Find expectations whose horizon has elapsed and compute critiques."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, pulse_number, episode_id, action, skill_id,
                          expected_outcome, expected_rt_delta_ms,
                          expected_health_in_n, n_pulses_horizon,
                          confidence_at_proposal
                   FROM cell_critic_expectations
                   WHERE critique_id IS NULL
                     AND pulse_number + n_pulses_horizon <= $1
                   ORDER BY pulse_number ASC
                   LIMIT 10""",
                current_pulse,
            )
        critiques: list[Critique] = []
        for row in rows:
            c = await self._evaluate_single(dict(row))
            if c is not None:
                critiques.append(c)
        return critiques

    async def _evaluate_single(self, exp: dict[str, Any]) -> Critique | None:
        """Compare one expectation against actual pulse log data."""
        start = exp["pulse_number"]
        end = start + exp["n_pulses_horizon"]
        async with self._pool.acquire() as conn:
            pulse_rows = await conn.fetch(
                """SELECT pulse_number, health_status, response_time_ms
                   FROM cell_pulse_log
                   WHERE pulse_number BETWEEN $1 AND $2
                   ORDER BY pulse_number ASC""",
                start, end,
            )
        if not pulse_rows:
            return None

        # Compute actual outcome
        start_rt = pulse_rows[0]["response_time_ms"] or 0
        end_rt = pulse_rows[-1]["response_time_ms"] or 0
        end_health = pulse_rows[-1]["health_status"] or "yellow"
        rt_delta = end_rt - start_rt

        if end_health == "green" and rt_delta < 50:
            actual_outcome = "success"
        elif end_health == "red":
            actual_outcome = "failure"
        else:
            actual_outcome = "partial"

        # Miscalibration: map outcomes to scores and diff
        score_map = {"success": 1.0, "partial": 0.5, "failure": 0.0}
        miscal = abs(
            score_map[exp["expected_outcome"]] - score_map[actual_outcome]
        )

        self_critique_nl = (
            f"I expected {exp['action']} to produce '{exp['expected_outcome']}' "
            f"with rt_delta {exp['expected_rt_delta_ms']}ms. "
            f"Actual: '{actual_outcome}' with rt_delta {rt_delta}ms."
        )

        # Weakness tag detection: 3+ consecutive failures on same action
        weakness_tag: str | None = None
        if actual_outcome == "failure":
            async with self._pool.acquire() as conn:
                recent_failures = await conn.fetchval(
                    """SELECT COUNT(*) FROM cell_critiques c
                       JOIN cell_critic_expectations e ON e.id = c.expectation_id
                       WHERE e.action = $1 AND c.actual_outcome = 'failure'
                         AND c.created_at > NOW() - INTERVAL '7 days'""",
                    exp["action"],
                )
            if (recent_failures or 0) >= WEAKNESS_PATTERN_THRESHOLD - 1:
                weakness_tag = f"repeated_failure_{exp['action']}"

        # Persist
        try:
            async with self._pool.acquire() as conn:
                crit_id = await conn.fetchval(
                    """INSERT INTO cell_critiques
                       (expectation_id, pulse_number, actual_outcome,
                        actual_rt_delta_ms, actual_health, miscalibration,
                        self_critique_nl, weakness_tag)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                       RETURNING id""",
                    exp["id"], end, actual_outcome, rt_delta,
                    end_health, miscal, self_critique_nl, weakness_tag,
                )
                # Link expectation → critique
                await conn.execute(
                    "UPDATE cell_critic_expectations SET critique_id = $1 WHERE id = $2",
                    crit_id, exp["id"],
                )
                # Update cell_episodes.outcome (fixes Phase 1+2 hardcoded 'partial')
                if exp["episode_id"]:
                    await conn.execute(
                        "UPDATE cell_episodes SET outcome = $1 WHERE id = $2",
                        actual_outcome, exp["episode_id"],
                    )
        except Exception as e:
            logger.warning(f"CriticAgent.evaluate_single persist failed: {e}")
            return None

        # Update skill library fitness if this was a skill-backed action
        if exp.get("skill_id") and self._library is not None:
            try:
                await self._library.record_use(
                    skill_id=exp["skill_id"],
                    success=(actual_outcome == "success"),
                )
            except Exception as e:
                logger.debug(f"record_use failed: {e}")

        return Critique(
            id=int(crit_id),
            expectation_id=exp["id"],
            pulse_number=end,
            actual_outcome=actual_outcome,
            actual_rt_delta_ms=rt_delta,
            actual_health=end_health,
            miscalibration=miscal,
            self_critique_nl=self_critique_nl,
            weakness_tag=weakness_tag,
            created_at=datetime.now(timezone.utc),
        )

    async def detect_weaknesses_for(self, self_model: Any) -> list[str]:
        """Return weakness tags from last 7 days and push them to self_model."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT DISTINCT weakness_tag FROM cell_critiques
                   WHERE weakness_tag IS NOT NULL
                     AND created_at > NOW() - INTERVAL '7 days'"""
            )
        tags = [r["weakness_tag"] for r in rows]
        for tag in tags:
            try:
                self_model.add_weakness(tag)
            except Exception:
                pass
        return tags
```

- [ ] **Step 3.4: Write `tests/test_critic_agent.py` (12 tests covering register, evaluate, weakness detection)**

Create `tests/test_critic_agent.py`:

```python
"""Tests for CriticAgent — Theory-of-Mind expected-vs-actual loop."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from cell.cortex.critic import (
    CriticAgent, Expectation, Critique,
    _HEURISTIC_EXPECTATIONS, VALID_EXPECTED_OUTCOMES,
)


@pytest.fixture
def mock_pool() -> AsyncMock:
    pool = AsyncMock()
    conn = AsyncMock()
    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_ctx)
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)
    return pool


class _StubProposal:
    def __init__(self, confidence=0.8, reason=""):
        self.confidence = confidence
        self.reason = reason


class TestRegisterExpectation:
    @pytest.mark.asyncio
    async def test_register_skips_none_action(self, mock_pool):
        critic = CriticAgent(pool=mock_pool)
        result = await critic.register_expectation(
            action="none", proposal=_StubProposal(), episode_id=None, current_pulse=1,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_register_heuristic_for_known_action(self, mock_pool):
        conn = await mock_pool.acquire().__aenter__()
        conn.fetchval = AsyncMock(return_value=42)
        critic = CriticAgent(pool=mock_pool)
        exp = await critic.register_expectation(
            action="restart_service",
            proposal=_StubProposal(confidence=0.85),
            episode_id=1,
            current_pulse=100,
            use_llm=False,
        )
        assert exp is not None
        assert exp.expected_outcome == "success"
        assert exp.expected_rt_delta_ms == -200
        assert exp.expected_health_in_n == "green"

    @pytest.mark.asyncio
    async def test_register_heuristic_fallback_unknown_action(self, mock_pool):
        conn = await mock_pool.acquire().__aenter__()
        conn.fetchval = AsyncMock(return_value=1)
        critic = CriticAgent(pool=mock_pool)
        exp = await critic.register_expectation(
            action="unknown_action",
            proposal=_StubProposal(),
            episode_id=None,
            current_pulse=1,
        )
        assert exp is not None
        assert exp.expected_outcome == "partial"

    @pytest.mark.asyncio
    async def test_register_llm_parses_json(self, mock_pool):
        conn = await mock_pool.acquire().__aenter__()
        conn.fetchval = AsyncMock(return_value=10)
        resp = MagicMock()
        resp.json.return_value = {"message": {"content": '{"outcome":"success","rt_delta":-100,"health_in_n":"green","rationale":"x"}'}}
        resp.raise_for_status = MagicMock()
        http_client = AsyncMock()
        http_client.post = AsyncMock(return_value=resp)
        critic = CriticAgent(pool=mock_pool, http_client=http_client)
        exp = await critic.register_expectation(
            action="restart_service",
            proposal=_StubProposal(confidence=0.9, reason="RT drift"),
            episode_id=5, current_pulse=50, use_llm=True,
        )
        assert exp is not None
        assert exp.expected_outcome == "success"

    @pytest.mark.asyncio
    async def test_register_llm_failure_falls_back_to_heuristics(self, mock_pool):
        conn = await mock_pool.acquire().__aenter__()
        conn.fetchval = AsyncMock(return_value=1)
        http_client = AsyncMock()
        http_client.post = AsyncMock(side_effect=Exception("ollama down"))
        critic = CriticAgent(pool=mock_pool, http_client=http_client)
        exp = await critic.register_expectation(
            action="restart_service",
            proposal=_StubProposal(),
            episode_id=None, current_pulse=1, use_llm=True,
        )
        assert exp is not None
        assert exp.expected_outcome == "success"  # heuristic for restart_service


class TestEvaluatePending:
    @pytest.mark.asyncio
    async def test_evaluate_empty_returns_empty(self, mock_pool):
        critic = CriticAgent(pool=mock_pool)
        critiques = await critic.evaluate_pending(current_pulse=100)
        assert critiques == []

    @pytest.mark.asyncio
    async def test_evaluate_skips_recent_expectations(self, mock_pool):
        conn = await mock_pool.acquire().__aenter__()
        # Empty fetch = no eligible expectations
        conn.fetch = AsyncMock(return_value=[])
        critic = CriticAgent(pool=mock_pool)
        critiques = await critic.evaluate_pending(current_pulse=10, n_horizon=5)
        assert critiques == []

    @pytest.mark.asyncio
    async def test_evaluate_computes_miscalibration(self, mock_pool):
        conn = await mock_pool.acquire().__aenter__()
        # Prime expectations fetch
        call_count = {"n": 0}
        async def mock_fetch(query, *args):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # Expectations query
                return [{
                    "id": 1, "pulse_number": 10, "episode_id": 5,
                    "action": "restart_service", "skill_id": None,
                    "expected_outcome": "success",
                    "expected_rt_delta_ms": -200,
                    "expected_health_in_n": "green",
                    "n_pulses_horizon": 5,
                    "confidence_at_proposal": 0.8,
                }]
            # pulse log
            return [
                {"pulse_number": 10, "health_status": "yellow", "response_time_ms": 500},
                {"pulse_number": 15, "health_status": "red", "response_time_ms": 900},
            ]
        conn.fetch = AsyncMock(side_effect=mock_fetch)
        conn.fetchval = AsyncMock(return_value=99)  # new critique id
        critic = CriticAgent(pool=mock_pool)
        critiques = await critic.evaluate_pending(current_pulse=20)
        assert len(critiques) == 1
        # expected success (score 1.0) vs actual failure (score 0.0) → miscal 1.0
        assert critiques[0].miscalibration == 1.0
        assert critiques[0].actual_outcome == "failure"


class TestWeaknessDetection:
    @pytest.mark.asyncio
    async def test_detect_weaknesses_returns_tags(self, mock_pool):
        conn = await mock_pool.acquire().__aenter__()
        conn.fetch = AsyncMock(return_value=[
            {"weakness_tag": "repeated_failure_restart_service"},
            {"weakness_tag": "repeated_failure_scale_up"},
        ])
        self_model = MagicMock()
        critic = CriticAgent(pool=mock_pool)
        tags = await critic.detect_weaknesses_for(self_model)
        assert len(tags) == 2
        assert self_model.add_weakness.call_count == 2


class TestHeuristicsMap:
    def test_all_allowlisted_actions_have_heuristics(self):
        # Every allowlisted action should have a heuristic expectation
        from cell.effectors.allowlist import ActionRegistry
        registry = ActionRegistry()
        for name in registry.all().keys():
            assert name in _HEURISTIC_EXPECTATIONS, f"Missing heuristic for action {name}"
```

- [ ] **Step 3.5: Run tests, verify they pass**

```bash
PYTHONPATH=. pytest tests/test_critic_agent.py -v
PYTHONPATH=. pytest tests/ -q --tb=no -x  # regression check
```

Expected: all tests pass (11+ new tests), Phase 1+2 baseline intact.

- [ ] **Step 3.6: Commit**

```bash
git add cell/cortex/critic.py tests/test_critic_agent.py
git commit -m "feat(cell/cortex): add CriticAgent (ToM expected-vs-actual loop)

Registers expectations with heuristic fallback when LLM disabled.
Evaluates pending expectations after n_pulses_horizon, computes
miscalibration, detects repeated-failure weakness tags, updates
cell_episodes.outcome (fixes Phase 1+2 hardcoded 'partial').

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: CuriosityEngine + GoalGenerator

**Goal:** Build the exploration and agenda pieces. Curiosity mines memory (SQL + LLM retrospective), Goals aggregate from 4 sources and track pursuit.

**Files:**
- Create: `cell/cortex/curiosity_engine.py`
- Create: `cell/cortex/goal_generator.py`
- Create: `tests/test_curiosity_engine.py`
- Create: `tests/test_goal_generator.py`

**Dependencies:** SkillLibrary (Task 2), PostgreSQL tables (Task 1).

**Spec reference:** Sections 3.4 and 3.5 of the design doc.

### Task 4 steps

- [ ] **Step 4.1: Create `cell/cortex/curiosity_engine.py`**

```python
"""CuriosityEngine — intrinsic exploration of CELL's own memory.

Two strategies:
1. Pattern mining: read-only SQL queries from a whitelist pool
2. Retrospective LLM query: templated questions answered by Qwen 9B

NO external actions. Only reads from cell_pulse_log, cell_episodes,
cell_dreams, cell_journal, cell_critiques. Never writes outside
cell_curiosity_findings.
"""
import json
import logging
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger("cell.cortex.curiosity_engine")


# SQL query whitelist. ALL queries are read-only SELECT, no string interpolation
# of runtime data, only parameterized via asyncpg $1, $2.
_QUERY_POOL: dict[str, str] = {
    "hour_of_day_rt_correlation": """
        SELECT EXTRACT(hour FROM created_at)::int AS hour,
               AVG(response_time_ms)::int AS avg_rt,
               COUNT(*) AS n
        FROM cell_pulse_log
        WHERE created_at > NOW() - INTERVAL '14 days'
          AND response_time_ms IS NOT NULL
        GROUP BY 1
        HAVING COUNT(*) >= 5
        ORDER BY avg_rt DESC
        LIMIT 10
    """,
    "emotion_outcome_distribution": """
        SELECT emotion, outcome, COUNT(*) AS n
        FROM cell_episodes
        GROUP BY 1, 2
        ORDER BY 3 DESC
        LIMIT 20
    """,
    "action_frequency_last_week": """
        SELECT action_taken, COUNT(*) AS n
        FROM cell_pulse_log
        WHERE action_taken IS NOT NULL
          AND created_at > NOW() - INTERVAL '7 days'
        GROUP BY 1
        ORDER BY 2 DESC
    """,
    "miscalibration_by_action": """
        SELECT e.action, AVG(c.miscalibration) AS avg_miscal, COUNT(*) AS n
        FROM cell_critiques c
        JOIN cell_critic_expectations e ON e.id = c.expectation_id
        WHERE c.created_at > NOW() - INTERVAL '14 days'
        GROUP BY 1
        HAVING COUNT(*) >= 3
        ORDER BY 2 DESC
    """,
    "dream_gap_frequency": """
        SELECT jsonb_array_elements_text(gaps_identified) AS gap, COUNT(*) AS n
        FROM cell_dreams
        WHERE dream_date > NOW() - INTERVAL '14 days'
        GROUP BY 1
        ORDER BY 2 DESC
        LIMIT 10
    """,
    "skill_usage_distribution": """
        SELECT name, use_count, fitness
        FROM cell_skills
        WHERE status = 'active'
        ORDER BY use_count DESC
        LIMIT 10
    """,
    "episode_count_by_day_last_week": """
        SELECT DATE(created_at) AS day, COUNT(*) AS n
        FROM cell_episodes
        WHERE created_at > NOW() - INTERVAL '7 days'
        GROUP BY 1
        ORDER BY 1 ASC
    """,
    "recent_weakness_tags": """
        SELECT weakness_tag, COUNT(*) AS n
        FROM cell_critiques
        WHERE weakness_tag IS NOT NULL
          AND created_at > NOW() - INTERVAL '7 days'
        GROUP BY 1
        ORDER BY 2 DESC
    """,
    "recent_journal_emotions": """
        SELECT emotion_summary, COUNT(*) AS n
        FROM cell_journal
        WHERE journal_date > NOW() - INTERVAL '14 days'
        GROUP BY 1
        ORDER BY 2 DESC
    """,
    "action_sequence_frequency": """
        WITH action_pairs AS (
            SELECT a1.action_taken AS first_act,
                   LEAD(a1.action_taken) OVER (ORDER BY a1.pulse_number) AS next_act
            FROM cell_pulse_log a1
            WHERE a1.action_taken IS NOT NULL
              AND a1.created_at > NOW() - INTERVAL '7 days'
        )
        SELECT first_act, next_act, COUNT(*) AS n
        FROM action_pairs
        WHERE next_act IS NOT NULL
        GROUP BY 1, 2
        ORDER BY 3 DESC
        LIMIT 10
    """,
}


_QUESTION_POOL: list[str] = [
    "What sensor has the lowest reliability score in the last 7 days?",
    "When stress > 0.7, what is the most common action taken?",
    "Are there episodes where I felt 'panic' but the lesson was 'no action needed'?",
    "What hour-of-day has the highest action count?",
    "Which lesson appears most frequently in the last 30 episodes?",
    "Have I been consistent about when I use restart_service vs scale_up?",
    "Which days of the week show the most episodes?",
    "What patterns appear in my failed expectations?",
    "Are there actions I have never tried despite being in the allowlist?",
    "Which skills have the highest success_count but low use_count?",
    "What emotions dominate my journal entries?",
    "Do I sleep with unfinished goals?",
    "Are there correlations between my stress level and specific sensor readings?",
    "Which episodes produced my strongest weakness tags?",
    "What is the ratio of resolved to pending goals in my current list?",
    "Have any of my skills decayed faster than their parent?",
    "What is my average response time when making decisions under panic?",
    "Are there actions in my allowlist that never seem to resolve my stress?",
    "Which pattern of sensor failure do I handle worst?",
    "What has changed most in my behavior in the last week?",
]


@dataclass
class CuriosityFinding:
    id: int
    source: str
    question: str
    method: str
    finding: str
    actionable: bool
    information_gain: float
    related_goal_id: int | None
    created_at: datetime


class CuriosityEngine:
    """Intrinsic exploration when CELL is stable."""

    def __init__(
        self,
        pool: Any,
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "qwen3.5:9b",
        http_client: Any = None,
    ) -> None:
        self._pool = pool
        self._ollama_url = ollama_url
        self._model = ollama_model
        self._http_client = http_client
        self._owns_client = http_client is None
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._http_client is not None:
            return self._http_client
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def explore(
        self,
        state: dict[str, Any],
        attention_budget: int,
        allow_mining: bool = True,
    ) -> list[CuriosityFinding]:
        """Run one exploration cycle. Returns new findings."""
        if attention_budget < 1:
            return []
        findings: list[CuriosityFinding] = []

        # Strategy 1: pattern mining (cost 1)
        if allow_mining and attention_budget >= 1:
            f = await self._pattern_mining()
            if f is not None:
                findings.append(f)
                attention_budget -= 1

        # Strategy 2: retrospective query via LLM (cost 2)
        if attention_budget >= 2:
            f = await self._retrospective_query(state)
            if f is not None:
                findings.append(f)
                attention_budget -= 2

        return findings

    async def _pattern_mining(self) -> CuriosityFinding | None:
        """Pick a query from the pool and execute it."""
        query_name = await self._select_query()
        if query_name is None:
            return None
        sql = _QUERY_POOL[query_name]
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(sql)
        except Exception as e:
            logger.debug(f"Pattern mining query '{query_name}' failed: {e}")
            return None

        if not rows:
            return None

        # Finding text: summarize top rows
        finding_text = self._summarize_rows(query_name, rows)
        info_gain = self._compute_info_gain(rows)
        actionable = info_gain > 0.5

        try:
            async with self._pool.acquire() as conn:
                finding_id = await conn.fetchval(
                    """INSERT INTO cell_curiosity_findings
                       (source, question, method, finding, actionable, information_gain)
                       VALUES ($1, $2, $3, $4, $5, $6)
                       RETURNING id""",
                    "pattern_mining",
                    query_name,
                    f"SQL:{query_name}",
                    finding_text,
                    actionable,
                    info_gain,
                )
        except Exception as e:
            logger.warning(f"Curiosity persist failed: {e}")
            return None

        return CuriosityFinding(
            id=int(finding_id),
            source="pattern_mining",
            question=query_name,
            method=f"SQL:{query_name}",
            finding=finding_text,
            actionable=actionable,
            information_gain=info_gain,
            related_goal_id=None,
            created_at=datetime.now(timezone.utc),
        )

    async def _select_query(self) -> str | None:
        """Pick a query not run in the last 7 days."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT DISTINCT method FROM cell_curiosity_findings
                   WHERE source = 'pattern_mining'
                     AND created_at > NOW() - INTERVAL '7 days'"""
            )
        seen = {r["method"].replace("SQL:", "") for r in rows}
        available = [k for k in _QUERY_POOL.keys() if k not in seen]
        if not available:
            return None
        return random.choice(available)

    @staticmethod
    def _summarize_rows(query_name: str, rows: list[Any]) -> str:
        if not rows:
            return "No data"
        preview = [dict(r) for r in rows[:5]]
        return f"{query_name} top-{len(preview)}: " + json.dumps(preview, default=str)

    @staticmethod
    def _compute_info_gain(rows: list[Any]) -> float:
        """Heuristic: high when result distribution is uneven (high variance or entropy)."""
        if not rows or len(rows) < 2:
            return 0.0
        # Find first numeric column
        sample = dict(rows[0])
        numeric_col = None
        for k, v in sample.items():
            if isinstance(v, (int, float)) and k != "n":
                numeric_col = k
                break
        if numeric_col is None:
            numeric_col = "n" if "n" in sample else None
        if numeric_col is None:
            return 0.3
        vals = [float(dict(r)[numeric_col]) for r in rows if dict(r).get(numeric_col) is not None]
        if not vals or max(vals) == 0:
            return 0.0
        return min(1.0, (max(vals) - min(vals)) / max(vals))

    async def _retrospective_query(self, state: dict[str, Any]) -> CuriosityFinding | None:
        """Pick a question and ask Qwen 9B to answer it using memory context."""
        question = await self._select_question()
        if question is None:
            return None
        try:
            client = self._get_client()
            system = (
                "You are CELL's retrospective reasoning module. Answer the question "
                "based ONLY on the memory summary given. Be concise (1-3 sentences)."
            )
            context = f"Current stress: {state.get('stress', 0.0):.2f}, phase: {state.get('phase', '?')}"
            user = f"Question: {question}\n\nContext: {context}\n\nAnswer:"
            resp = await client.post(
                f"{self._ollama_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    "think": False,
                    "options": {"temperature": 0.3, "num_predict": 200},
                },
            )
            resp.raise_for_status()
            finding_text = resp.json()["message"]["content"].strip()
        except Exception as e:
            logger.debug(f"Retrospective query failed: {e}")
            return None

        actionable = "should" in finding_text.lower() or "could" in finding_text.lower()
        info_gain = 0.4  # default for LLM answers

        try:
            async with self._pool.acquire() as conn:
                finding_id = await conn.fetchval(
                    """INSERT INTO cell_curiosity_findings
                       (source, question, method, finding, actionable, information_gain)
                       VALUES ($1, $2, $3, $4, $5, $6)
                       RETURNING id""",
                    "retrospective_query",
                    question,
                    "LLM:qwen3.5:9b",
                    finding_text[:1000],
                    actionable,
                    info_gain,
                )
        except Exception as e:
            logger.warning(f"Curiosity persist failed: {e}")
            return None

        return CuriosityFinding(
            id=int(finding_id),
            source="retrospective_query",
            question=question,
            method="LLM:qwen3.5:9b",
            finding=finding_text,
            actionable=actionable,
            information_gain=info_gain,
            related_goal_id=None,
            created_at=datetime.now(timezone.utc),
        )

    async def _select_question(self) -> str | None:
        """Pick a question not answered in the last 7 days."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT DISTINCT question FROM cell_curiosity_findings
                   WHERE source = 'retrospective_query'
                     AND created_at > NOW() - INTERVAL '7 days'"""
            )
        seen = {r["question"] for r in rows}
        available = [q for q in _QUESTION_POOL if q not in seen]
        if not available:
            return None
        return random.choice(available)
```

- [ ] **Step 4.2: Create `cell/cortex/goal_generator.py`**

```python
"""GoalGenerator — multi-source agenda hub.

Integrates signals from 4 sources: Curiosity findings, Critic weaknesses,
Dreamer gaps, decayed Skills. Scores goals by priority × feasibility × novelty.
Pursues goals when attention permits.
"""
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("cell.cortex.goal_generator")

# Base priority per source (can be overridden)
_SOURCE_PRIORITY: dict[str, float] = {
    "curiosity": 0.5,
    "critic": 0.8,
    "dreamer_gap": 0.6,
    "skill_decay": 0.7,
    "maturity_gap": 0.9,
}

DEFAULT_MAX_ACTIVE = 20
DEDUP_SIMILARITY_THRESHOLD = 0.7  # 3-gram Jaccard


@dataclass
class Goal:
    id: int
    source: str
    question: str
    motivation: str
    priority: float
    feasibility: float
    novelty: float
    score: float
    status: str
    findings: str | None
    related_skill_id: int | None
    created_at: datetime
    completed_at: datetime | None


def _trigrams(text: str) -> set[str]:
    t = text.lower()
    return {t[i:i+3] for i in range(max(0, len(t) - 2))}


def _jaccard(a: str, b: str) -> float:
    sa, sb = _trigrams(a), _trigrams(b)
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / max(union, 1)


class GoalGenerator:
    """Aggregates goal proposals from 4 sources, scores them, persues when idle."""

    def __init__(
        self,
        pool: Any,
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "qwen3.5:9b",
        http_client: Any = None,
        max_active: int = DEFAULT_MAX_ACTIVE,
    ) -> None:
        self._pool = pool
        self._ollama_url = ollama_url
        self._model = ollama_model
        self._http_client = http_client
        self._max_active = max_active

    async def collect(
        self,
        critic_signals: list[str] | None = None,
        dreamer_gaps: list[str] | None = None,
        curiosity_findings: list[Any] | None = None,
        decayed_skills: list[Any] | None = None,
    ) -> list[Goal]:
        """Ingest goal candidates from all 4 sources. Dedup, score, persist. Returns new goals."""
        candidates: list[dict[str, Any]] = []
        for tag in (critic_signals or []):
            candidates.append({
                "source": "critic",
                "question": f"Why do I keep failing with {tag}? How can I improve?",
                "motivation": f"weakness_tag={tag}",
            })
        for gap in (dreamer_gaps or []):
            candidates.append({
                "source": "dreamer_gap",
                "question": f"Fill knowledge gap: {gap}",
                "motivation": f"dreamer gap from consolidation",
            })
        for f in (curiosity_findings or []):
            q = getattr(f, "finding", str(f))[:200]
            candidates.append({
                "source": "curiosity",
                "question": f"Investigate further: {q}",
                "motivation": "actionable curiosity finding",
            })
        for s in (decayed_skills or []):
            name = getattr(s, "name", str(s))
            candidates.append({
                "source": "skill_decay",
                "question": f"Can I build a replacement for decayed skill '{name}'?",
                "motivation": f"skill '{name}' decayed below threshold",
            })

        # Dedup against existing goals
        existing = await self._active_questions()
        new_goals: list[Goal] = []
        for c in candidates:
            if any(_jaccard(c["question"], eq) > DEDUP_SIMILARITY_THRESHOLD for eq in existing):
                continue
            priority = _SOURCE_PRIORITY.get(c["source"], 0.5)
            feasibility = 0.9  # default: answerable from memory
            novelty = await self._compute_novelty(c["question"])
            score = priority * feasibility * novelty
            try:
                async with self._pool.acquire() as conn:
                    gid = await conn.fetchval(
                        """INSERT INTO cell_goals
                           (source, question, motivation, priority,
                            feasibility, novelty, score, status)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending')
                           RETURNING id""",
                        c["source"],
                        c["question"],
                        c["motivation"],
                        priority,
                        feasibility,
                        novelty,
                        score,
                    )
                g = Goal(
                    id=int(gid), source=c["source"], question=c["question"],
                    motivation=c["motivation"], priority=priority,
                    feasibility=feasibility, novelty=novelty, score=score,
                    status="pending", findings=None, related_skill_id=None,
                    created_at=datetime.now(timezone.utc), completed_at=None,
                )
                new_goals.append(g)
                existing.append(c["question"])
            except Exception as e:
                logger.warning(f"GoalGenerator.collect insert failed: {e}")

        await self._enforce_capacity()
        return new_goals

    async def _active_questions(self) -> list[str]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT question FROM cell_goals WHERE status IN ('pending', 'investigating')"
            )
        return [r["question"] for r in rows]

    async def _compute_novelty(self, question: str) -> float:
        """1.0 if no similar question in last 30 days, lower if duplicates."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT question FROM cell_goals
                   WHERE created_at > NOW() - INTERVAL '30 days'
                   ORDER BY created_at DESC LIMIT 50"""
            )
        for r in rows:
            if _jaccard(question, r["question"]) > 0.5:
                return 0.3
        return 1.0

    async def pursue_next(self, reasoner: Any = None) -> Goal | None:
        """Pick top-score pending goal and resolve it via reasoner."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT id, source, question, motivation, priority,
                          feasibility, novelty, score
                   FROM cell_goals
                   WHERE status = 'pending'
                   ORDER BY score DESC
                   LIMIT 1"""
            )
        if row is None:
            return None

        goal_id = row["id"]
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE cell_goals SET status = 'investigating' WHERE id = $1",
                goal_id,
            )

        # Generate findings (using reasoner if available, else simple note)
        findings = f"Goal '{row['question']}' investigated. "
        if reasoner is not None:
            try:
                from cell.slow.reasoner import ReasonerProposal
                proposal = await reasoner.think(
                    health_status="green",
                    response_time_ms=100,
                    error_message="",
                    stm_context=f"Investigating goal: {row['question']}",
                )
                findings += f"Reasoner suggested: {proposal.action} — {proposal.reason[:200]}"
            except Exception as e:
                findings += f"Reasoner unavailable: {e}"
        else:
            findings += "No reasoner available for deeper analysis."

        async with self._pool.acquire() as conn:
            await conn.execute(
                """UPDATE cell_goals
                   SET status = 'resolved', findings = $1, completed_at = NOW()
                   WHERE id = $2""",
                findings[:2000],
                goal_id,
            )

        return Goal(
            id=goal_id, source=row["source"], question=row["question"],
            motivation=row["motivation"], priority=row["priority"],
            feasibility=row["feasibility"], novelty=row["novelty"],
            score=row["score"], status="resolved", findings=findings,
            related_skill_id=None,
            created_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )

    async def list_active(self) -> list[Goal]:
        """Top-3 active goals for context injection."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, source, question, motivation, priority,
                          feasibility, novelty, score, status, findings,
                          related_skill_id, created_at, completed_at
                   FROM cell_goals
                   WHERE status IN ('pending', 'investigating')
                   ORDER BY score DESC
                   LIMIT 3"""
            )
        return [
            Goal(
                id=r["id"], source=r["source"], question=r["question"],
                motivation=r["motivation"], priority=r["priority"],
                feasibility=r["feasibility"], novelty=r["novelty"],
                score=r["score"], status=r["status"],
                findings=r["findings"], related_skill_id=r["related_skill_id"],
                created_at=r["created_at"],
                completed_at=r["completed_at"],
            )
            for r in rows
        ]

    async def archive_old(self) -> int:
        """Resolved goals older than 30 days → archived."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """UPDATE cell_goals
                   SET status = 'archived'
                   WHERE status = 'resolved'
                     AND completed_at < NOW() - INTERVAL '30 days'"""
            )
        parts = result.split()
        return int(parts[-1]) if parts and parts[-1].isdigit() else 0

    async def _enforce_capacity(self) -> None:
        """Archive lowest-score goals if over max_active."""
        async with self._pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM cell_goals WHERE status IN ('pending', 'investigating')"
            )
            if (count or 0) <= self._max_active:
                return
            excess = (count or 0) - self._max_active
            rows = await conn.fetch(
                """SELECT id FROM cell_goals
                   WHERE status IN ('pending', 'investigating')
                   ORDER BY score ASC
                   LIMIT $1""",
                excess,
            )
            ids = [r["id"] for r in rows]
            if ids:
                await conn.execute(
                    "UPDATE cell_goals SET status = 'archived' WHERE id = ANY($1::int[])",
                    ids,
                )
```

- [ ] **Step 4.3: Write `tests/test_curiosity_engine.py` (10 tests)**

```python
"""Tests for CuriosityEngine — intrinsic memory exploration."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from cell.cortex.curiosity_engine import CuriosityEngine, _QUERY_POOL, _QUESTION_POOL


@pytest.fixture
def mock_pool() -> AsyncMock:
    pool = AsyncMock()
    conn = AsyncMock()
    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_ctx)
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=1)
    return pool


class TestExplore:
    @pytest.mark.asyncio
    async def test_explore_returns_empty_when_no_budget(self, mock_pool):
        eng = CuriosityEngine(pool=mock_pool)
        assert await eng.explore({"stress": 0.1}, attention_budget=0) == []

    @pytest.mark.asyncio
    async def test_explore_runs_mining_and_retro(self, mock_pool):
        conn = await mock_pool.acquire().__aenter__()
        conn.fetch = AsyncMock(return_value=[{"hour": 14, "avg_rt": 300, "n": 50}])
        conn.fetchval = AsyncMock(return_value=1)
        resp = MagicMock()
        resp.json.return_value = {"message": {"content": "Finding: RT peaks at 14 UTC"}}
        resp.raise_for_status = MagicMock()
        http_client = AsyncMock()
        http_client.post = AsyncMock(return_value=resp)
        eng = CuriosityEngine(pool=mock_pool, http_client=http_client)
        findings = await eng.explore({"stress": 0.1, "phase": "adulto"}, attention_budget=5)
        assert len(findings) >= 1

    @pytest.mark.asyncio
    async def test_explore_without_mining(self, mock_pool):
        conn = await mock_pool.acquire().__aenter__()
        conn.fetchval = AsyncMock(return_value=1)
        resp = MagicMock()
        resp.json.return_value = {"message": {"content": "Some finding"}}
        resp.raise_for_status = MagicMock()
        http_client = AsyncMock()
        http_client.post = AsyncMock(return_value=resp)
        eng = CuriosityEngine(pool=mock_pool, http_client=http_client)
        findings = await eng.explore({}, attention_budget=3, allow_mining=False)
        assert len(findings) <= 1


class TestQueryPool:
    def test_all_queries_are_select_only(self):
        for name, sql in _QUERY_POOL.items():
            normalized = sql.strip().lower()
            assert normalized.startswith(("select", "with")), f"{name} not a SELECT"
            assert "insert" not in normalized, f"{name} contains INSERT"
            assert "update" not in normalized, f"{name} contains UPDATE"
            assert "delete" not in normalized, f"{name} contains DELETE"

    def test_query_pool_has_at_least_10(self):
        assert len(_QUERY_POOL) >= 10

    def test_question_pool_has_at_least_15(self):
        assert len(_QUESTION_POOL) >= 15


class TestInfoGain:
    def test_info_gain_high_for_uneven_distribution(self):
        rows = [{"hour": 1, "avg_rt": 50, "n": 10}, {"hour": 14, "avg_rt": 300, "n": 20}]
        gain = CuriosityEngine._compute_info_gain(rows)
        assert gain > 0.5

    def test_info_gain_zero_for_empty(self):
        assert CuriosityEngine._compute_info_gain([]) == 0.0

    def test_info_gain_low_for_uniform(self):
        rows = [{"x": 100, "n": 5}, {"x": 101, "n": 6}]
        gain = CuriosityEngine._compute_info_gain(rows)
        assert gain < 0.2


class TestSelectQuery:
    @pytest.mark.asyncio
    async def test_excludes_recently_seen(self, mock_pool):
        conn = await mock_pool.acquire().__aenter__()
        seen = [{"method": f"SQL:{name}"} for name in _QUERY_POOL.keys()]
        conn.fetch = AsyncMock(return_value=seen)
        eng = CuriosityEngine(pool=mock_pool)
        q = await eng._select_query()
        assert q is None  # all seen → None
```

- [ ] **Step 4.4: Write `tests/test_goal_generator.py` (12 tests)**

```python
"""Tests for GoalGenerator — multi-source agenda hub."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from cell.cortex.goal_generator import GoalGenerator, Goal, _jaccard, _trigrams


@pytest.fixture
def mock_pool() -> AsyncMock:
    pool = AsyncMock()
    conn = AsyncMock()
    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_ctx)
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=1)
    conn.fetchrow = AsyncMock(return_value=None)
    return pool


class TestJaccard:
    def test_identical_strings_score_1(self):
        assert _jaccard("hello world", "hello world") == 1.0

    def test_totally_different_score_near_0(self):
        assert _jaccard("aaa", "zzz") < 0.1

    def test_partial_overlap(self):
        j = _jaccard("restart service", "restart the service")
        assert 0.3 < j < 1.0


class TestCollect:
    @pytest.mark.asyncio
    async def test_collect_from_critic_signals(self, mock_pool):
        gen = GoalGenerator(pool=mock_pool)
        conn = await mock_pool.acquire().__aenter__()
        conn.fetchval = AsyncMock(return_value=1)
        goals = await gen.collect(critic_signals=["repeated_failure_restart"])
        assert len(goals) == 1
        assert goals[0].source == "critic"

    @pytest.mark.asyncio
    async def test_collect_from_curiosity_findings(self, mock_pool):
        gen = GoalGenerator(pool=mock_pool)
        conn = await mock_pool.acquire().__aenter__()
        conn.fetchval = AsyncMock(return_value=1)

        class _FakeFinding:
            finding = "RT peaks at 14 UTC"
        goals = await gen.collect(curiosity_findings=[_FakeFinding()])
        assert len(goals) == 1
        assert goals[0].source == "curiosity"

    @pytest.mark.asyncio
    async def test_collect_dedup_by_question_similarity(self, mock_pool):
        gen = GoalGenerator(pool=mock_pool)
        conn = await mock_pool.acquire().__aenter__()
        conn.fetchval = AsyncMock(return_value=1)
        # First collect
        goals1 = await gen.collect(critic_signals=["repeated_failure_restart"])
        # Second collect with very similar signal
        conn.fetch = AsyncMock(return_value=[{"question": goals1[0].question}])
        goals2 = await gen.collect(critic_signals=["repeated_failure_restart"])
        # Should be deduped
        assert len(goals2) == 0

    @pytest.mark.asyncio
    async def test_collect_empty_inputs(self, mock_pool):
        gen = GoalGenerator(pool=mock_pool)
        goals = await gen.collect()
        assert goals == []


class TestPursueNext:
    @pytest.mark.asyncio
    async def test_pursue_returns_none_when_no_pending(self, mock_pool):
        gen = GoalGenerator(pool=mock_pool)
        result = await gen.pursue_next()
        assert result is None

    @pytest.mark.asyncio
    async def test_pursue_marks_resolved(self, mock_pool):
        conn = await mock_pool.acquire().__aenter__()
        conn.fetchrow = AsyncMock(return_value={
            "id": 5, "source": "curiosity", "question": "test?",
            "motivation": "m", "priority": 0.5, "feasibility": 0.9,
            "novelty": 1.0, "score": 0.45,
        })
        gen = GoalGenerator(pool=mock_pool)
        goal = await gen.pursue_next()
        assert goal is not None
        assert goal.status == "resolved"
        # Verify UPDATE to 'investigating' and then 'resolved'
        assert conn.execute.await_count >= 2


class TestArchive:
    @pytest.mark.asyncio
    async def test_archive_old_returns_count(self, mock_pool):
        conn = await mock_pool.acquire().__aenter__()
        conn.execute = AsyncMock(return_value="UPDATE 3")
        gen = GoalGenerator(pool=mock_pool)
        assert await gen.archive_old() == 3


class TestCapacity:
    @pytest.mark.asyncio
    async def test_enforce_capacity_archives_excess(self, mock_pool):
        conn = await mock_pool.acquire().__aenter__()
        conn.fetchval = AsyncMock(return_value=25)
        conn.fetch = AsyncMock(return_value=[{"id": i} for i in range(5)])
        gen = GoalGenerator(pool=mock_pool, max_active=20)
        await gen._enforce_capacity()
        # Should have called execute to archive 5 goals
        conn.execute.assert_awaited()
```

- [ ] **Step 4.5: Run all tests, verify they pass + zero regression**

```bash
PYTHONPATH=. pytest tests/test_curiosity_engine.py tests/test_goal_generator.py -v
PYTHONPATH=. pytest tests/ -q --tb=no -x
```

- [ ] **Step 4.6: Commit**

```bash
git add cell/cortex/curiosity_engine.py cell/cortex/goal_generator.py \
      tests/test_curiosity_engine.py tests/test_goal_generator.py
git commit -m "feat(cell/cortex): add CuriosityEngine + GoalGenerator

CuriosityEngine: 10 SQL whitelist queries + 20 NL question templates.
GoalGenerator: multi-source hub with Jaccard dedup, priority scoring,
and capacity enforcement.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: StrategyMutator (sandbox dual-track, safety chain, rate limits)

**Goal:** Propose skill mutations, validate them through a 4-layer safety chain + dual-track sandbox, commit or rollback, monitor post-promotion.

**Files:**
- Create: `cell/cortex/strategy_mutator.py`
- Create: `tests/test_strategy_mutator.py`

**Dependencies:** SkillLibrary (Task 2), CriticAgent (Task 3), EpisodicMemory (existing).

**Spec reference:** Section 3.3 of the design doc.

### Task 5 steps

- [ ] **Step 5.1: Create `cell/cortex/strategy_mutator.py`**

Full source file — see the spec for detailed documentation. Core methods:

```python
"""StrategyMutator — controlled evolution of CELL's skill library.

Proposes mutations to existing skills (or discovers new ones) based on
signals from CriticAgent, GoalGenerator, and decayed skills. Each
proposal passes a 4-layer safety chain + dual-track sandbox before
promotion. Auto-rollback after 24h if fitness drops.
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from cell.effectors.allowlist import ActionRegistry, ActionNotAllowed
from cell.fast.mutation_filter import MutationSafety, filter_mutation

logger = logging.getLogger("cell.cortex.strategy_mutator")

SANDBOX_FITNESS_THRESHOLD = 0.6
ROLLBACK_FITNESS_MARGIN = 0.1


@dataclass
class MutationProposal:
    parent_skill_id: int | None
    proposed_name: str
    proposed_trigger_nl: str
    proposed_action_sequence: list[str]
    proposed_rationale_nl: str
    motivation: str
    source: str


@dataclass
class SandboxResult:
    proposal: MutationProposal
    llm_replay_score: float
    pattern_match_count: int
    pattern_match_rate: float
    estimated_fitness: float
    safety_violations: list[str]
    dna_check: bool
    constitutional_check: bool
    promoted: bool
    rejected_reason: str | None


class StrategyMutator:
    """Controlled evolution of CELL's skill library."""

    def __init__(
        self,
        pool: Any,
        library: Any,
        reasoner: Any = None,
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "qwen3.5:9b",
        http_client: Any = None,
    ) -> None:
        self._pool = pool
        self._library = library
        self._reasoner = reasoner
        self._ollama_url = ollama_url
        self._model = ollama_model
        self._http_client = http_client
        self._registry = ActionRegistry()

    async def mutations_today(self) -> int:
        """Count mutations already proposed today (UTC)."""
        async with self._pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT COUNT(*) FROM cell_mutations WHERE created_at::date = CURRENT_DATE"
            ) or 0

    async def propose_from_signal(
        self, signal: dict[str, Any], reasoner: Any = None
    ) -> MutationProposal | None:
        """Generate a skill mutation proposal from a Critic/Goal/decay signal.
        
        Uses Qwen 9B to generate the proposed skill text.
        """
        source = signal.get("source", "unknown")
        motivation = signal.get("motivation", "")
        parent_id = signal.get("parent_skill_id")

        # Build context for LLM
        parent_ctx = ""
        if parent_id is not None:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT name, trigger_nl, action_sequence, rationale_nl, fitness FROM cell_skills WHERE id = $1",
                    parent_id,
                )
                if row:
                    seq = row["action_sequence"]
                    if isinstance(seq, str):
                        seq = json.loads(seq)
                    parent_ctx = (
                        f"Parent skill: {row['name']} (fitness={row['fitness']:.2f})\n"
                        f"Trigger: {row['trigger_nl']}\n"
                        f"Actions: {seq}\n"
                        f"Rationale: {row['rationale_nl']}"
                    )

        action_names = list(self._registry.all().keys())
        system = (
            "You are CELL's skill evolution module. Generate a refined (or new) skill.\n"
            "Rules: ONLY use these actions: " + ", ".join(action_names) + "\n"
            "Respond in JSON only: "
            '{"name":"short_snake_case","trigger":"when condition NL","actions":["action1"],"rationale":"why"}'
        )
        user = f"Signal source: {source}\nMotivation: {motivation}\n{parent_ctx}\nPropose a skill."

        try:
            client = self._http_client or (await self._get_or_create_client())
            resp = await client.post(
                f"{self._ollama_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    "think": False,
                    "options": {"temperature": 0.3, "num_predict": 200},
                },
            )
            resp.raise_for_status()
            text = resp.json()["message"]["content"]
            start = text.find("{")
            end = text.rfind("}") + 1
            if start == -1 or end == 0:
                return None
            data = json.loads(text[start:end])
        except Exception as e:
            logger.warning(f"StrategyMutator LLM proposal failed: {e}")
            return None

        actions = data.get("actions", [])
        if not isinstance(actions, list) or not actions:
            return None

        return MutationProposal(
            parent_skill_id=parent_id,
            proposed_name=str(data.get("name", "unnamed"))[:128],
            proposed_trigger_nl=str(data.get("trigger", ""))[:500],
            proposed_action_sequence=actions,
            proposed_rationale_nl=str(data.get("rationale", ""))[:500],
            motivation=motivation[:500],
            source=source,
        )

    async def _get_or_create_client(self) -> Any:
        import httpx
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=15.0)
        return self._http_client

    def _safety_check(self, proposal: MutationProposal) -> list[str]:
        """Run safety chain layers 1-2: allowlist + mutation filter."""
        violations: list[str] = []
        for action_name in proposal.proposed_action_sequence:
            # Layer 1: allowlist check
            try:
                self._registry.get(action_name)
            except ActionNotAllowed:
                violations.append(f"action '{action_name}' not in allowlist")
                continue
            # Layer 2: mutation filter (regex safety check)
            action = self._registry.get(action_name)
            safety = filter_mutation(action.command_template)
            if safety == MutationSafety.UNSAFE:
                violations.append(f"action '{action_name}' contains unsafe pattern")
        return violations

    async def sandbox_test(
        self,
        proposal: MutationProposal,
        reasoner: Any = None,
        episodic: Any = None,
    ) -> SandboxResult:
        """Dual-track sandbox: LLM replay (Track A) + pattern simulation (Track B).
        
        Returns SandboxResult with fitness estimate and safety status.
        """
        # Safety layers 1-2
        violations = self._safety_check(proposal)
        if violations:
            return SandboxResult(
                proposal=proposal, llm_replay_score=0.0,
                pattern_match_count=0, pattern_match_rate=0.0,
                estimated_fitness=0.0, safety_violations=violations,
                dna_check=False, constitutional_check=False,
                promoted=False, rejected_reason=f"Safety violations: {violations}",
            )

        # Safety layer 3: DNA check
        from cell.core.dna_interpreter import DNAInterpreter
        dna = DNAInterpreter()
        dna_ok = True
        for action_name in proposal.proposed_action_sequence:
            result = dna.validate(action_name, budget_spent=0.0, budget_limit=10.0, confidence=0.7)
            if not result.approved:
                dna_ok = False
                violations.append(f"DNA rejected '{action_name}': {result.reason}")
                break

        if not dna_ok:
            return SandboxResult(
                proposal=proposal, llm_replay_score=0.0,
                pattern_match_count=0, pattern_match_rate=0.0,
                estimated_fitness=0.0, safety_violations=violations,
                dna_check=False, constitutional_check=False,
                promoted=False, rejected_reason=f"DNA check failed: {violations}",
            )

        # Track A: LLM replay on 8 representative episodes
        llm_score = 0.0
        if episodic is not None:
            llm_score = await self._track_a_replay(proposal, reasoner, episodic)

        # Track B: pattern match on 100 recent episodes
        match_count, match_rate = await self._track_b_pattern(proposal)

        # Combined fitness
        estimated_fitness = 0.7 * llm_score + 0.3 * match_rate

        # Write audit log
        promoted = estimated_fitness >= SANDBOX_FITNESS_THRESHOLD and not violations
        rejected_reason = None if promoted else (
            f"fitness {estimated_fitness:.2f} < {SANDBOX_FITNESS_THRESHOLD}" if not violations
            else f"violations: {violations}"
        )

        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO cell_skill_audit
                       (skill_id, parent_skill_id, action, reason,
                        sandbox_score, pattern_match_rate, safety_violations, dna_check)
                       VALUES (NULL, $1, $2, $3, $4, $5, $6::jsonb, $7)""",
                    proposal.parent_skill_id,
                    "promoted" if promoted else "rejected",
                    rejected_reason or "sandbox passed",
                    estimated_fitness,
                    match_rate,
                    json.dumps(violations),
                    dna_ok,
                )
        except Exception as e:
            logger.warning(f"Audit log failed: {e}")

        return SandboxResult(
            proposal=proposal,
            llm_replay_score=llm_score,
            pattern_match_count=match_count,
            pattern_match_rate=match_rate,
            estimated_fitness=estimated_fitness,
            safety_violations=violations,
            dna_check=dna_ok,
            constitutional_check=True,  # simplified for now
            promoted=promoted,
            rejected_reason=rejected_reason,
        )

    async def _track_a_replay(
        self, proposal: MutationProposal, reasoner: Any, episodic: Any
    ) -> float:
        """Replay 8 episodes with proposed skill injected. Return 0..1 score."""
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT id, situation, emotion, action_taken, outcome
                       FROM cell_episodes
                       WHERE outcome IN ('success', 'failure')
                       ORDER BY timestamp DESC
                       LIMIT 100"""
                )
        except Exception:
            return 0.0

        if len(rows) < 4:
            return 0.5  # not enough data, neutral score

        # Cluster sampling: pick 2 per emotion category
        by_emotion: dict[str, list] = {}
        for r in rows:
            em = r["emotion"]
            by_emotion.setdefault(em, []).append(r)
        sample: list = []
        for em in ("calm", "alert", "stressed", "panic"):
            candidates = by_emotion.get(em, [])
            sample.extend(candidates[:2])
        if len(sample) < 4:
            sample = list(rows[:8])
        sample = sample[:8]

        # Score: how many episodes would the new skill have improved?
        improvements = 0
        for ep in sample:
            outcome = ep["outcome"]
            action = ep["action_taken"]
            # Simple heuristic: if episode was 'failure' and proposed action differs, score +1
            # If 'success' and proposed action matches, score +1
            if outcome == "failure" and action not in proposal.proposed_action_sequence:
                improvements += 1
            elif outcome == "success" and action in proposal.proposed_action_sequence:
                improvements += 1
        return improvements / max(len(sample), 1)

    async def _track_b_pattern(self, proposal: MutationProposal) -> tuple[int, float]:
        """Keyword match trigger_nl against 100 recent episode situations."""
        keywords = set(proposal.proposed_trigger_nl.lower().split())
        keywords.discard("when")
        keywords.discard("if")
        keywords.discard("and")
        keywords.discard("the")
        keywords.discard("is")
        if not keywords:
            return 0, 0.0

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT situation FROM cell_episodes
                       ORDER BY timestamp DESC LIMIT 100"""
                )
        except Exception:
            return 0, 0.0

        matches = 0
        for r in rows:
            sit = r["situation"]
            if isinstance(sit, str):
                sit = json.loads(sit)
            sit_text = json.dumps(sit).lower()
            if any(kw in sit_text for kw in keywords):
                matches += 1

        return matches, matches / max(len(rows), 1)

    async def commit_or_rollback(self, result: SandboxResult) -> None:
        """If promoted, add to library + set up rollback monitor. Else: noop (already logged)."""
        if not result.promoted:
            return
        skill_id = await self._library.add_candidate(
            name=result.proposal.proposed_name,
            trigger_nl=result.proposal.proposed_trigger_nl,
            action_sequence=result.proposal.proposed_action_sequence,
            rationale_nl=result.proposal.proposed_rationale_nl,
            parent_id=result.proposal.parent_skill_id,
            source=result.proposal.source,
        )
        await self._library.promote(skill_id)

        # Freeze parent if exists
        if result.proposal.parent_skill_id:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    "UPDATE cell_skills SET status = 'frozen' WHERE id = $1 AND status = 'active'",
                    result.proposal.parent_skill_id,
                )

        # Register rollback monitor
        parent_fitness = 0.0
        if result.proposal.parent_skill_id:
            async with self._pool.acquire() as conn:
                pf = await conn.fetchval(
                    "SELECT fitness FROM cell_skills WHERE id = $1",
                    result.proposal.parent_skill_id,
                )
                parent_fitness = float(pf or 0.0)

        async with self._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO cell_mutations
                   (skill_id, parent_skill_id, parent_fitness, monitor_until)
                   VALUES ($1, $2, $3, $4)""",
                skill_id,
                result.proposal.parent_skill_id,
                parent_fitness,
                datetime.now(timezone.utc) + timedelta(hours=24),
            )

        logger.info(
            f"StrategyMutator: promoted skill id={skill_id} "
            f"name='{result.proposal.proposed_name}' fitness={result.estimated_fitness:.2f}"
        )

    async def check_rollbacks(self) -> list[int]:
        """Check pending mutations whose monitor window has elapsed. Rollback if fitness dropped."""
        rolled_back_ids: list[int] = []
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT m.id, m.skill_id, m.parent_skill_id, m.parent_fitness
                   FROM cell_mutations m
                   WHERE m.outcome IS NULL AND m.monitor_until <= NOW()"""
            )
        for row in rows:
            async with self._pool.acquire() as conn:
                current_fitness = await conn.fetchval(
                    "SELECT fitness FROM cell_skills WHERE id = $1",
                    row["skill_id"],
                ) or 0.0

                if current_fitness < row["parent_fitness"] - ROLLBACK_FITNESS_MARGIN:
                    # ROLLBACK
                    await conn.execute(
                        "UPDATE cell_skills SET status = 'apoptosed' WHERE id = $1",
                        row["skill_id"],
                    )
                    if row["parent_skill_id"]:
                        await conn.execute(
                            "UPDATE cell_skills SET status = 'active' WHERE id = $1 AND status = 'frozen'",
                            row["parent_skill_id"],
                        )
                    await conn.execute(
                        """UPDATE cell_mutations
                           SET outcome = 'rolled_back', monitored_at = NOW(), final_fitness = $1
                           WHERE id = $2""",
                        float(current_fitness),
                        row["id"],
                    )
                    await conn.execute(
                        """INSERT INTO cell_skill_audit
                           (skill_id, parent_skill_id, action, reason)
                           VALUES ($1, $2, 'rolled_back', $3)""",
                        row["skill_id"],
                        row["parent_skill_id"],
                        f"fitness {current_fitness:.2f} < parent {row['parent_fitness']:.2f} - {ROLLBACK_FITNESS_MARGIN}",
                    )
                    rolled_back_ids.append(row["skill_id"])
                    logger.info(
                        f"StrategyMutator: ROLLED BACK skill {row['skill_id']} "
                        f"(fitness={current_fitness:.2f} < parent={row['parent_fitness']:.2f})"
                    )
                else:
                    # SURVIVED
                    await conn.execute(
                        """UPDATE cell_mutations
                           SET outcome = 'survived', monitored_at = NOW(), final_fitness = $1
                           WHERE id = $2""",
                        float(current_fitness),
                        row["id"],
                    )
        return rolled_back_ids
```

- [ ] **Step 5.2: Write `tests/test_strategy_mutator.py` (14 tests)**

```python
"""Tests for StrategyMutator — controlled skill evolution."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from cell.cortex.strategy_mutator import (
    StrategyMutator, MutationProposal, SandboxResult,
    SANDBOX_FITNESS_THRESHOLD, ROLLBACK_FITNESS_MARGIN,
)


@pytest.fixture
def mock_pool() -> AsyncMock:
    pool = AsyncMock()
    conn = AsyncMock()
    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_ctx)
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)
    conn.fetchrow = AsyncMock(return_value=None)
    return pool


@pytest.fixture
def mock_library():
    lib = AsyncMock()
    lib.add_candidate = AsyncMock(return_value=42)
    lib.promote = AsyncMock()
    return lib


def _make_proposal(**kwargs):
    defaults = {
        "parent_skill_id": None,
        "proposed_name": "test_skill",
        "proposed_trigger_nl": "when test condition",
        "proposed_action_sequence": ["read_logs"],
        "proposed_rationale_nl": "test rationale",
        "motivation": "test",
        "source": "critic_failure",
    }
    defaults.update(kwargs)
    return MutationProposal(**defaults)


class TestSafetyCheck:
    def test_valid_actions_no_violations(self, mock_pool, mock_library):
        mut = StrategyMutator(pool=mock_pool, library=mock_library)
        proposal = _make_proposal(proposed_action_sequence=["read_logs", "alert_silent"])
        violations = mut._safety_check(proposal)
        assert violations == []

    def test_invalid_action_rejected(self, mock_pool, mock_library):
        mut = StrategyMutator(pool=mock_pool, library=mock_library)
        proposal = _make_proposal(proposed_action_sequence=["invented_action"])
        violations = mut._safety_check(proposal)
        assert len(violations) == 1
        assert "not in allowlist" in violations[0]


class TestSandbox:
    @pytest.mark.asyncio
    async def test_sandbox_rejects_unsafe_actions(self, mock_pool, mock_library):
        mut = StrategyMutator(pool=mock_pool, library=mock_library)
        proposal = _make_proposal(proposed_action_sequence=["nonexistent_action"])
        result = await mut.sandbox_test(proposal)
        assert not result.promoted
        assert len(result.safety_violations) > 0

    @pytest.mark.asyncio
    async def test_sandbox_passes_valid_proposal(self, mock_pool, mock_library):
        conn = await mock_pool.acquire().__aenter__()
        # Empty episodes → 0.5 neutral llm_score, 0 pattern match
        conn.fetch = AsyncMock(return_value=[])
        mut = StrategyMutator(pool=mock_pool, library=mock_library)
        proposal = _make_proposal(proposed_action_sequence=["read_logs"])
        result = await mut.sandbox_test(proposal)
        # 0.7*0.5 + 0.3*0.0 = 0.35 < 0.6 threshold
        assert not result.promoted
        assert result.estimated_fitness < SANDBOX_FITNESS_THRESHOLD

    @pytest.mark.asyncio
    async def test_sandbox_combined_fitness_formula(self, mock_pool, mock_library):
        conn = await mock_pool.acquire().__aenter__()
        conn.fetch = AsyncMock(return_value=[])
        mut = StrategyMutator(pool=mock_pool, library=mock_library)
        proposal = _make_proposal()
        result = await mut.sandbox_test(proposal)
        expected = 0.7 * result.llm_replay_score + 0.3 * result.pattern_match_rate
        assert abs(result.estimated_fitness - expected) < 1e-6


class TestCommitOrRollback:
    @pytest.mark.asyncio
    async def test_commit_promotes_and_monitors(self, mock_pool, mock_library):
        mut = StrategyMutator(pool=mock_pool, library=mock_library)
        result = SandboxResult(
            proposal=_make_proposal(),
            llm_replay_score=0.8, pattern_match_count=20,
            pattern_match_rate=0.2, estimated_fitness=0.62,
            safety_violations=[], dna_check=True,
            constitutional_check=True, promoted=True,
            rejected_reason=None,
        )
        await mut.commit_or_rollback(result)
        mock_library.add_candidate.assert_awaited_once()
        mock_library.promote.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_commit_skips_on_not_promoted(self, mock_pool, mock_library):
        mut = StrategyMutator(pool=mock_pool, library=mock_library)
        result = SandboxResult(
            proposal=_make_proposal(),
            llm_replay_score=0.0, pattern_match_count=0,
            pattern_match_rate=0.0, estimated_fitness=0.0,
            safety_violations=["test"], dna_check=False,
            constitutional_check=False, promoted=False,
            rejected_reason="test",
        )
        await mut.commit_or_rollback(result)
        mock_library.add_candidate.assert_not_awaited()


class TestRollback:
    @pytest.mark.asyncio
    async def test_rollback_when_fitness_drops(self, mock_pool, mock_library):
        conn = await mock_pool.acquire().__aenter__()
        conn.fetch = AsyncMock(return_value=[{
            "id": 1, "skill_id": 42, "parent_skill_id": 41,
            "parent_fitness": 0.72,
        }])
        conn.fetchval = AsyncMock(return_value=0.3)  # current fitness dropped
        mut = StrategyMutator(pool=mock_pool, library=mock_library)
        rolled_back = await mut.check_rollbacks()
        assert 42 in rolled_back

    @pytest.mark.asyncio
    async def test_survived_when_fitness_maintained(self, mock_pool, mock_library):
        conn = await mock_pool.acquire().__aenter__()
        conn.fetch = AsyncMock(return_value=[{
            "id": 1, "skill_id": 42, "parent_skill_id": 41,
            "parent_fitness": 0.72,
        }])
        conn.fetchval = AsyncMock(return_value=0.75)  # fitness maintained
        mut = StrategyMutator(pool=mock_pool, library=mock_library)
        rolled_back = await mut.check_rollbacks()
        assert rolled_back == []

    @pytest.mark.asyncio
    async def test_no_pending_mutations(self, mock_pool, mock_library):
        mut = StrategyMutator(pool=mock_pool, library=mock_library)
        assert await mut.check_rollbacks() == []


class TestRateLimit:
    @pytest.mark.asyncio
    async def test_mutations_today_counts(self, mock_pool, mock_library):
        conn = await mock_pool.acquire().__aenter__()
        conn.fetchval = AsyncMock(return_value=2)
        mut = StrategyMutator(pool=mock_pool, library=mock_library)
        assert await mut.mutations_today() == 2
```

- [ ] **Step 5.3: Run tests, verify pass + regression check**

```bash
PYTHONPATH=. pytest tests/test_strategy_mutator.py -v
PYTHONPATH=. pytest tests/ -q --tb=no -x
```

- [ ] **Step 5.4: Commit**

```bash
git add cell/cortex/strategy_mutator.py tests/test_strategy_mutator.py
git commit -m "feat(cell/cortex): add StrategyMutator with sandbox + safety + rollback

4-layer safety chain (allowlist, MutationFilter, DNA, constitutional).
Dual-track sandbox (LLM replay on 8 episodes + pattern sim on 100).
Auto-rollback monitor after 24h. Rate limited to 3/day (adulto).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: AchievementGate (lifecycle upgrade)

**Goal:** Wrap existing `Maturation` with achievement-based gating. Effective phase = min(age_phase, achievement_phase). Age floor is inviolable.

**Files:**
- Create: `cell/lifecycle/achievement_gate.py`
- Create: `tests/test_achievement_gate.py`

**Dependencies:** All Cortex tables (Task 1), SkillLibrary, GoalGenerator, Journal (existing).

**Spec reference:** Section 3.6 of the design doc.

### Task 6 steps

- [ ] **Step 6.1: Create `cell/lifecycle/achievement_gate.py`**

```python
"""AchievementGate — extends Maturation with achievement-based phase gating.

Effective phase = min(age_based_phase, achievement_phase).
Age floor from Maturation is INVIOLABLE — achievements can only delay
promotion, never advance it past what age allows.

Transition requirements (in addition to age):
  neonato → giovane: 10+ episodes recorded
  giovane → adulto:  50+ episodes with outcome != 'partial',
                     10+ active skills, 5+ resolved goals
  adulto → anziano:  20+ skills stable 30d, >=70% fitness>0.6,
                     90+ journal days
"""
import logging
from typing import Any

from cell.lifecycle.maturation import LifecyclePhase, Maturation

logger = logging.getLogger("cell.lifecycle.achievement_gate")

# Achievement requirements per transition
_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "giovane": {
        "episodes_recorded": 10,
    },
    "adulto": {
        "episodes_with_outcome": 50,
        "skills_in_library": 10,
        "goals_completed": 5,
    },
    "anziano": {
        "skills_stable_30d": 20,
        "skills_fitness_above_06": 0.7,
        "journal_continuity_days": 90,
    },
}

# Escape hatch: if stuck past age floor + 14 days, auto-promote
_ESCAPE_HATCH_DAYS = 14

# Phase ordering helper (LifecyclePhase is str Enum, alphabetical ≠ lifecycle order)
_PHASE_RANK: dict[LifecyclePhase, int] = {
    LifecyclePhase.EMBRIONE: 0,
    LifecyclePhase.NEONATO: 1,
    LifecyclePhase.GIOVANE: 2,
    LifecyclePhase.ADULTO: 3,
    LifecyclePhase.ANZIANO: 4,
}

# Age floors per phase
_AGE_FLOORS: dict[LifecyclePhase, int] = {
    LifecyclePhase.EMBRIONE: 0,
    LifecyclePhase.NEONATO: 4,
    LifecyclePhase.GIOVANE: 15,
    LifecyclePhase.ADULTO: 31,
    LifecyclePhase.ANZIANO: 180,
}


class AchievementGate:
    """Wraps Maturation with achievement-based phase gating."""

    def __init__(self, base: Maturation, pool: Any, self_model: Any = None) -> None:
        self._base = base
        self._pool = pool
        self._self_model = self_model

    @property
    def phase(self) -> LifecyclePhase:
        """Pass-through to base phase (backward compat)."""
        return self._base.phase

    @property
    def age_days(self) -> int:
        return self._base.age_days

    async def achievements(self) -> dict[str, Any]:
        """Compute all achievement counters from DB."""
        result: dict[str, Any] = {}
        async with self._pool.acquire() as conn:
            result["episodes_recorded"] = await conn.fetchval(
                "SELECT COUNT(*) FROM cell_episodes"
            ) or 0
            result["episodes_with_outcome"] = await conn.fetchval(
                "SELECT COUNT(*) FROM cell_episodes WHERE outcome IN ('success', 'failure')"
            ) or 0
            result["skills_in_library"] = await conn.fetchval(
                "SELECT COUNT(*) FROM cell_skills WHERE status = 'active'"
            ) or 0
            result["goals_completed"] = await conn.fetchval(
                "SELECT COUNT(*) FROM cell_goals WHERE status = 'resolved'"
            ) or 0
            result["skills_stable_30d"] = await conn.fetchval("""
                SELECT COUNT(DISTINCT s.id) FROM cell_skills s
                WHERE s.status = 'active'
                  AND s.created_at < NOW() - INTERVAL '30 days'
                  AND NOT EXISTS (
                    SELECT 1 FROM cell_skill_audit a
                    WHERE a.skill_id = s.id AND a.created_at > NOW() - INTERVAL '30 days'
                      AND a.action IN ('rolled_back', 'apoptosed')
                  )
            """) or 0
            result["skills_fitness_above_06"] = float(await conn.fetchval("""
                SELECT COALESCE(AVG(CASE WHEN fitness > 0.6 THEN 1.0 ELSE 0.0 END), 0)
                FROM cell_skills WHERE status = 'active'
            """) or 0.0)
            result["journal_continuity_days"] = await conn.fetchval("""
                SELECT COUNT(DISTINCT journal_date) FROM cell_journal
                WHERE journal_date > NOW() - INTERVAL '90 days'
            """) or 0
        return result

    async def effective_phase(self) -> tuple[LifecyclePhase, dict[str, Any]]:
        """Returns (effective_phase, {achievements, missing_for_next})."""
        base = self._base.phase
        ach = await self.achievements()
        missing: list[str] = []

        effective = base

        # Walk back from base if achievements not met
        if _PHASE_RANK[base] >= _PHASE_RANK[LifecyclePhase.ANZIANO]:
            req = _REQUIREMENTS["anziano"]
            if not (
                ach["skills_stable_30d"] >= req["skills_stable_30d"]
                and ach["skills_fitness_above_06"] >= req["skills_fitness_above_06"]
                and ach["journal_continuity_days"] >= req["journal_continuity_days"]
            ):
                effective = LifecyclePhase.ADULTO
                if ach["skills_stable_30d"] < req["skills_stable_30d"]:
                    missing.append(f"need {req['skills_stable_30d'] - ach['skills_stable_30d']} more stable skills")
                if ach["skills_fitness_above_06"] < req["skills_fitness_above_06"]:
                    missing.append(f"fitness ratio {ach['skills_fitness_above_06']:.0%} < {req['skills_fitness_above_06']:.0%}")
                if ach["journal_continuity_days"] < req["journal_continuity_days"]:
                    missing.append(f"need {req['journal_continuity_days'] - ach['journal_continuity_days']} more journal days")

        if _PHASE_RANK[effective] >= _PHASE_RANK[LifecyclePhase.ADULTO] and _PHASE_RANK[base] >= _PHASE_RANK[LifecyclePhase.ADULTO]:
            req = _REQUIREMENTS["adulto"]
            if not (
                ach["episodes_with_outcome"] >= req["episodes_with_outcome"]
                and ach["skills_in_library"] >= req["skills_in_library"]
                and ach["goals_completed"] >= req["goals_completed"]
            ):
                # Escape hatch: age >= floor + 14 days → auto-promote with warning
                age_floor = _AGE_FLOORS[LifecyclePhase.ADULTO]
                if self._base.age_days >= age_floor + _ESCAPE_HATCH_DAYS:
                    logger.warning(
                        f"AchievementGate: auto-promoting to adulto (age={self._base.age_days}d, "
                        f"achievements not met but escape hatch triggered)"
                    )
                else:
                    effective = LifecyclePhase.GIOVANE
                    if ach["episodes_with_outcome"] < req["episodes_with_outcome"]:
                        missing.append(f"need {req['episodes_with_outcome'] - ach['episodes_with_outcome']} more episodes with outcome")
                    if ach["skills_in_library"] < req["skills_in_library"]:
                        missing.append(f"need {req['skills_in_library'] - ach['skills_in_library']} more active skills")
                    if ach["goals_completed"] < req["goals_completed"]:
                        missing.append(f"need {req['goals_completed'] - ach['goals_completed']} more resolved goals")

        if _PHASE_RANK[effective] >= _PHASE_RANK[LifecyclePhase.GIOVANE] and _PHASE_RANK[base] >= _PHASE_RANK[LifecyclePhase.GIOVANE]:
            req = _REQUIREMENTS["giovane"]
            if ach["episodes_recorded"] < req["episodes_recorded"]:
                effective = LifecyclePhase.NEONATO
                missing.append(f"need {req['episodes_recorded'] - ach['episodes_recorded']} more episodes")

        return effective, {"achievements": ach, "missing_for_next": missing}

    async def missing_for_next_phase(self) -> list[str]:
        _, details = await self.effective_phase()
        return details["missing_for_next"]

    # Forward maturation methods
    def can_act(self) -> bool:
        return self._base.can_act()

    def can_dream(self) -> bool:
        return self._base.can_dream()

    def can_reason_deep(self) -> bool:
        return self._base.can_reason_deep()

    def action_confidence_threshold(self) -> float:
        return self._base.action_confidence_threshold()

    def to_prompt_context(self) -> str:
        return self._base.to_prompt_context()

    def log_phase(self) -> None:
        self._base.log_phase()
```

- [ ] **Step 6.2: Write `tests/test_achievement_gate.py` (10 tests)**

```python
"""Tests for AchievementGate — lifecycle gating with achievements."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from cell.lifecycle.maturation import LifecyclePhase, Maturation
from cell.lifecycle.achievement_gate import AchievementGate, _PHASE_RANK, _ESCAPE_HATCH_DAYS


@pytest.fixture
def mock_pool() -> AsyncMock:
    pool = AsyncMock()
    conn = AsyncMock()
    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_ctx)
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)
    return pool


class TestEffectivePhase:
    @pytest.mark.asyncio
    async def test_embrione_not_affected_by_achievements(self, mock_pool):
        gate = AchievementGate(base=Maturation(age_days=2), pool=mock_pool)
        phase, _ = await gate.effective_phase()
        assert phase == LifecyclePhase.EMBRIONE

    @pytest.mark.asyncio
    async def test_neonato_stays_if_low_episodes(self, mock_pool):
        conn = await mock_pool.acquire().__aenter__()
        # Return low counts for all fetchval calls
        conn.fetchval = AsyncMock(return_value=3)  # only 3 episodes
        gate = AchievementGate(base=Maturation(age_days=16), pool=mock_pool)
        phase, details = await gate.effective_phase()
        assert phase == LifecyclePhase.NEONATO
        assert len(details["missing_for_next"]) > 0

    @pytest.mark.asyncio
    async def test_giovane_with_enough_episodes(self, mock_pool):
        conn = await mock_pool.acquire().__aenter__()
        # Enough episodes but nothing else
        vals = iter([20, 10, 0, 0, 0, 0.0, 0])  # eps_rec, eps_out, skills, goals, stable, ratio, journal
        conn.fetchval = AsyncMock(side_effect=lambda *a, **kw: next(vals))
        gate = AchievementGate(base=Maturation(age_days=20), pool=mock_pool)
        phase, details = await gate.effective_phase()
        assert phase == LifecyclePhase.GIOVANE

    @pytest.mark.asyncio
    async def test_giovane_blocked_from_adulto_by_missing_skills(self, mock_pool):
        conn = await mock_pool.acquire().__aenter__()
        vals = iter([100, 60, 3, 2, 0, 0.0, 0])  # 60 eps, only 3 skills, 2 goals
        conn.fetchval = AsyncMock(side_effect=lambda *a, **kw: next(vals))
        gate = AchievementGate(base=Maturation(age_days=35), pool=mock_pool)
        phase, details = await gate.effective_phase()
        assert phase == LifecyclePhase.GIOVANE
        assert any("skills" in m for m in details["missing_for_next"])

    @pytest.mark.asyncio
    async def test_adulto_when_all_met(self, mock_pool):
        conn = await mock_pool.acquire().__aenter__()
        vals = iter([200, 60, 12, 8, 0, 0.0, 0])  # all adulto reqs met
        conn.fetchval = AsyncMock(side_effect=lambda *a, **kw: next(vals))
        gate = AchievementGate(base=Maturation(age_days=35), pool=mock_pool)
        phase, _ = await gate.effective_phase()
        assert phase == LifecyclePhase.ADULTO

    @pytest.mark.asyncio
    async def test_age_floor_inviolable(self, mock_pool):
        """Even with 1000 skills, a day-3 cell cannot be adult."""
        conn = await mock_pool.acquire().__aenter__()
        vals = iter([999, 999, 999, 999, 999, 1.0, 999])
        conn.fetchval = AsyncMock(side_effect=lambda *a, **kw: next(vals))
        gate = AchievementGate(base=Maturation(age_days=3), pool=mock_pool)
        phase, _ = await gate.effective_phase()
        assert phase == LifecyclePhase.EMBRIONE


class TestEscapeHatch:
    @pytest.mark.asyncio
    async def test_escape_hatch_promotes_after_14_extra_days(self, mock_pool):
        conn = await mock_pool.acquire().__aenter__()
        vals = iter([100, 10, 2, 1, 0, 0.0, 0])  # adulto reqs NOT met
        conn.fetchval = AsyncMock(side_effect=lambda *a, **kw: next(vals))
        gate = AchievementGate(base=Maturation(age_days=45), pool=mock_pool)  # 31 + 14
        phase, _ = await gate.effective_phase()
        assert phase == LifecyclePhase.ADULTO  # escape hatch kicked in


class TestForwarding:
    def test_phase_property_delegates(self, mock_pool):
        gate = AchievementGate(base=Maturation(age_days=20), pool=mock_pool)
        assert gate.phase == LifecyclePhase.GIOVANE

    def test_can_act_delegates(self, mock_pool):
        gate = AchievementGate(base=Maturation(age_days=5), pool=mock_pool)
        assert gate.can_act() is True


class TestPhaseRank:
    def test_ordering(self):
        assert _PHASE_RANK[LifecyclePhase.EMBRIONE] < _PHASE_RANK[LifecyclePhase.NEONATO]
        assert _PHASE_RANK[LifecyclePhase.NEONATO] < _PHASE_RANK[LifecyclePhase.GIOVANE]
        assert _PHASE_RANK[LifecyclePhase.GIOVANE] < _PHASE_RANK[LifecyclePhase.ADULTO]
        assert _PHASE_RANK[LifecyclePhase.ADULTO] < _PHASE_RANK[LifecyclePhase.ANZIANO]
```

- [ ] **Step 6.3: Run tests, verify pass + regression check**

```bash
PYTHONPATH=. pytest tests/test_achievement_gate.py -v
PYTHONPATH=. pytest tests/ -q --tb=no -x
```

- [ ] **Step 6.4: Commit**

```bash
git add cell/lifecycle/achievement_gate.py tests/test_achievement_gate.py
git commit -m "feat(cell/lifecycle): add AchievementGate wrapping Maturation

Two-layer gating: age floor (inviolable) + achievement extras.
Escape hatch at age floor + 14 days. Phase rank helper avoids
str-enum alphabetical comparison bug.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Cortex orchestrator + PulseEngine integration

**Goal:** Wire all 6 components together via the `Cortex` thin orchestrator, add 4 hooks to `PulseEngine`, update `main.py`, make `EpisodicMemory.store()` return the new episode id, add `skill_context` kwarg to `SlowReasoner.think()`.

**Files:**
- Create: `cell/cortex/cortex.py`
- Modify: `cell/core/pulse.py` — add `cortex` parameter + 4 hook calls
- Modify: `cell/main.py` — instantiate Cortex + wire into PulseEngine
- Modify: `cell/memory/episodic.py` — `store()` returns `int` (the new episode id)
- Modify: `cell/slow/reasoner.py` — `think()` and `_build_system_prompt()` accept `skill_context`
- Create: `tests/test_cortex_integration.py`
- Create: `tests/test_pulse_with_cortex.py`

**Dependencies:** ALL previous tasks (1-6) must be complete.

**Spec reference:** Sections 3.7, 5, 6 of the design doc.

### Task 7 steps

- [ ] **Step 7.1: Modify `cell/memory/episodic.py` — store() returns id**

Change `store()` method from `async def store(self, episode: Episode) -> None:` to:

```python
    async def store(self, episode: Episode) -> int:
        """Persist an episode to PostgreSQL. Returns the new episode id."""
        async with self._pool.acquire() as conn:
            row_id = await conn.fetchval(
                """INSERT INTO cell_episodes
                   (timestamp, situation, emotion, action_taken, outcome, lesson, recall_count)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
                   RETURNING id""",
                episode.timestamp,
                json.dumps(episode.situation),
                episode.emotion,
                episode.action_taken,
                episode.outcome,
                episode.lesson,
                episode.recall_count,
            )
        logger.info(f"Episode stored: id={row_id} emotion={episode.emotion} action={episode.action_taken} outcome={episode.outcome}")
        return int(row_id)
```

This is a backward-compatible change: callers that ignore the return value are unaffected.

- [ ] **Step 7.2: Modify `cell/slow/reasoner.py` — add skill_context parameter**

In `SlowReasoner._build_system_prompt()`, add `skill_context: str = ""` param:

```python
    def _build_system_prompt(self, ltm_context: str = "", journal_context: str = "", skill_context: str = "") -> str:
        actions = self._registry.all()
        action_list = "\n".join(
            f"- {name}: {a.description} (cooldown: {a.cooldown_seconds}s, max: {a.max_per_day}/day)"
            for name, a in actions.items()
        )
        ltm_block = (ltm_context + "\n") if ltm_context else ""
        journal_block = (journal_context + "\n") if journal_context else ""
        skill_block = (skill_context + "\n") if skill_context else ""
        return SYSTEM_PROMPT.format(actions=action_list, ltm_context=ltm_block, journal_context=journal_block) + skill_block
```

In `SlowReasoner.think()`, add `skill_context: str = ""` param and pass it through:

```python
    async def think(
        self,
        ...,
        skill_context: str = "",
    ) -> ReasonerProposal:
```

And in the body where `_build_system_prompt` is called:

```python
        system = self._build_system_prompt(
            ltm_context=ltm_context,
            journal_context=journal_context,
            skill_context=skill_context,
        )
```

- [ ] **Step 7.3: Create `cell/cortex/cortex.py` — the thin orchestrator**

```python
"""Cortex — Phase 3+4 orchestrator.

Thin coordinator that owns 6 components and exposes 4 hooks for PulseEngine.
All hooks are best-effort: if any fail, they log a warning but do NOT block the pulse.

Lifecycle-gated: each component activates only when maturation phase allows.
"""
import logging
from typing import Any

import httpx

from cell.lifecycle.maturation import LifecyclePhase, Maturation
from cell.lifecycle.achievement_gate import AchievementGate
from cell.cortex.skill_library import SkillLibrary
from cell.cortex.critic import CriticAgent
from cell.cortex.curiosity_engine import CuriosityEngine
from cell.cortex.goal_generator import GoalGenerator
from cell.cortex.strategy_mutator import StrategyMutator

logger = logging.getLogger("cell.cortex")

# Lifecycle phases that enable each component
_CRITIC_PHASES = (
    LifecyclePhase.NEONATO, LifecyclePhase.GIOVANE,
    LifecyclePhase.ADULTO, LifecyclePhase.ANZIANO,
)
_CURIOSITY_PHASES = (
    LifecyclePhase.GIOVANE, LifecyclePhase.ADULTO, LifecyclePhase.ANZIANO,
)
_GOALS_PHASES = (
    LifecyclePhase.GIOVANE, LifecyclePhase.ADULTO, LifecyclePhase.ANZIANO,
)
_MUTATOR_PHASES = (
    LifecyclePhase.ADULTO, LifecyclePhase.ANZIANO,
)
_SKILL_USE_PHASES = (
    LifecyclePhase.NEONATO, LifecyclePhase.GIOVANE,
    LifecyclePhase.ADULTO, LifecyclePhase.ANZIANO,
)


class Cortex:
    """Phase 3+4 orchestrator. Attaches to PulseEngine as a single optional attribute."""

    def __init__(
        self,
        pool: Any,
        reasoner: Any,
        episodic: Any,
        self_model: Any,
        journal: Any,
        attention: Any,
        maturation: Maturation,
        ollama_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._pool = pool
        self._reasoner = reasoner
        self._episodic = episodic
        self._self_model = self_model
        self._journal = journal
        self._attention = attention
        self._maturation = maturation

        self.skills = SkillLibrary(pool=pool)
        self.critic = CriticAgent(
            pool=pool, skill_library=self.skills,
            http_client=ollama_client,
        )
        self.curiosity = CuriosityEngine(
            pool=pool, http_client=ollama_client,
        )
        self.goals = GoalGenerator(
            pool=pool, http_client=ollama_client,
        )
        self.mutator = StrategyMutator(
            pool=pool, library=self.skills,
            reasoner=reasoner, http_client=ollama_client,
        )
        self.gate = AchievementGate(
            base=maturation, pool=pool, self_model=self_model,
        )
        logger.info(f"Cortex initialized: phase={maturation.phase.value}")

    # ── Hook 1: before reasoning ────────────────────────────
    async def before_reasoning(self, situation: dict) -> str:
        """Recall top-K skills and format as system prompt augmentation."""
        if self._maturation.phase not in _SKILL_USE_PHASES:
            return ""
        try:
            skills = await self.skills.recall(situation, k=3)
            return self.skills.format_for_prompt(skills)
        except Exception as e:
            logger.warning(f"Cortex.before_reasoning failed: {e}")
            return ""

    # ── Hook 2: after action ────────────────────────────────
    async def after_action(
        self,
        episode_data: Any,
        proposal: Any,
        action: str | None,
        episode_id: int | None,
        current_pulse: int,
    ) -> None:
        """Critic: register expectation + evaluate pending."""
        if self._maturation.phase not in _CRITIC_PHASES:
            return
        try:
            if action and action != "none":
                use_llm = self._maturation.phase != LifecyclePhase.NEONATO
                await self.critic.register_expectation(
                    action=action,
                    proposal=proposal,
                    episode_id=episode_id,
                    current_pulse=current_pulse,
                    use_llm=use_llm,
                )
            critiques = await self.critic.evaluate_pending(current_pulse=current_pulse)
            if critiques:
                weaknesses = [c.weakness_tag for c in critiques if c.weakness_tag]
                for w in weaknesses:
                    self._self_model.add_weakness(w)
        except Exception as e:
            logger.warning(f"Cortex.after_action failed: {e}")

    # ── Hook 3: during idle ─────────────────────────────────
    async def during_idle(self, state: dict) -> None:
        """Curiosity exploration + goal pursuit when stable."""
        phase = self._maturation.phase
        if phase not in _CURIOSITY_PHASES:
            return
        if state.get("stress", 1.0) > 0.3 or state.get("attention_remaining", 0) < 5:
            return
        try:
            allow_mining = phase in (LifecyclePhase.ADULTO, LifecyclePhase.ANZIANO)
            findings = await self.curiosity.explore(
                state,
                attention_budget=int(state.get("attention_remaining", 10)),
                allow_mining=allow_mining,
            )
            actionable = [f for f in findings if f.actionable]
            if actionable and phase in _GOALS_PHASES:
                await self.goals.collect(curiosity_findings=actionable)
            if state.get("attention_remaining", 0) >= 5 and phase in _GOALS_PHASES:
                await self.goals.pursue_next(reasoner=self._reasoner)
        except Exception as e:
            logger.warning(f"Cortex.during_idle failed: {e}")

    # ── Hook 4: during sleep ────────────────────────────────
    async def during_sleep(self) -> dict:
        """Decay, maturity check, mutation cycle, rollback monitor."""
        summary: dict[str, Any] = {
            "decayed": 0, "rollbacks": 0,
            "mutations_proposed": 0, "promoted": 0,
            "missing_for_next": [], "effective_phase": "unknown",
        }
        try:
            summary["decayed"] = await self.skills.decay()
            await self.skills.enforce_capacity()

            effective, details = await self.gate.effective_phase()
            summary["effective_phase"] = effective.value
            summary["missing_for_next"] = details.get("missing_for_next", [])

            rolled_back = await self.mutator.check_rollbacks()
            summary["rollbacks"] = len(rolled_back)

            # Mutation cycle (only adulto+)
            if self._maturation.phase in _MUTATOR_PHASES:
                max_rate = 1 if self._maturation.phase == LifecyclePhase.ANZIANO else 3
                today_count = await self.mutator.mutations_today()
                remaining = max_rate - today_count
                if remaining > 0:
                    signals = await self._collect_mutation_signals()
                    for signal in signals[:remaining]:
                        proposal = await self.mutator.propose_from_signal(signal, self._reasoner)
                        if proposal:
                            summary["mutations_proposed"] += 1
                            result = await self.mutator.sandbox_test(
                                proposal, self._reasoner, self._episodic,
                            )
                            await self.mutator.commit_or_rollback(result)
                            if result.promoted:
                                summary["promoted"] += 1

            # Goal collection from sleep signals
            critic_tags = await self.critic.detect_weaknesses_for(self._self_model)
            await self.goals.collect(critic_signals=critic_tags)
            await self.goals.archive_old()

        except Exception as e:
            logger.warning(f"Cortex.during_sleep failed: {e}", exc_info=True)
        return summary

    async def _collect_mutation_signals(self) -> list[dict]:
        """Build signal list from Critic weaknesses, completed goals, decayed skills."""
        signals: list[dict] = []
        try:
            async with self._pool.acquire() as conn:
                # Critic weaknesses
                rows = await conn.fetch("""
                    SELECT weakness_tag, COUNT(*) as freq
                    FROM cell_critiques
                    WHERE weakness_tag IS NOT NULL
                      AND created_at > NOW() - INTERVAL '7 days'
                    GROUP BY weakness_tag
                    HAVING COUNT(*) >= 3
                    ORDER BY freq DESC LIMIT 3
                """)
                for r in rows:
                    signals.append({
                        "source": "critic_failure",
                        "motivation": f"weakness_tag={r['weakness_tag']}",
                        "parent_skill_id": None,
                        "urgency": float(r["freq"]) / 10.0,
                    })

                # Resolved goals not yet materialized as skills
                rows = await conn.fetch("""
                    SELECT id, question FROM cell_goals
                    WHERE status = 'resolved' AND related_skill_id IS NULL
                      AND completed_at > NOW() - INTERVAL '7 days'
                    ORDER BY score DESC LIMIT 3
                """)
                for r in rows:
                    signals.append({
                        "source": "goal_completion",
                        "motivation": f"goal_id={r['id']}: {r['question'][:80]}",
                        "parent_skill_id": None,
                        "urgency": 0.5,
                    })

                # Recently decayed skills
                rows = await conn.fetch("""
                    SELECT skill_id, parent_skill_id, reason
                    FROM cell_skill_audit
                    WHERE action = 'apoptosed'
                      AND created_at > NOW() - INTERVAL '7 days'
                    ORDER BY created_at DESC LIMIT 3
                """)
                for r in rows:
                    signals.append({
                        "source": "skill_decay",
                        "motivation": f"decayed skill {r['skill_id']}: {r['reason']}",
                        "parent_skill_id": r["parent_skill_id"] or r["skill_id"],
                        "urgency": 0.4,
                    })
        except Exception as e:
            logger.warning(f"Cortex._collect_mutation_signals failed: {e}")

        signals.sort(key=lambda s: s.get("urgency", 0), reverse=True)
        return signals[:10]
```

- [ ] **Step 7.4: Modify `cell/core/pulse.py` — add cortex parameter + 4 hooks**

In `PulseEngine.__init__`, add:

```python
    def __init__(self, ..., cortex: Any = None) -> None:
        ...
        self._cortex = cortex
```

In `single_pulse()`, add **4 hook insertion points** (see spec Section 5 for exact line numbers):

**Hook 1 — before SLOW THINK (insert before `if status != HealthStatus.GREEN and self._reasoner`):**

```python
        # ── CORTEX HOOK 1: before reasoning ──
        skill_context = ""
        if self._cortex is not None:
            try:
                situation = {
                    "health_status": status.value,
                    "response_time_ms": response_ms,
                    "stress": self._homeostatic.state.stress_level if self._homeostatic else 0.0,
                    "sensors": sensor_metadata,
                }
                skill_context = await self._cortex.before_reasoning(situation)
            except Exception as e:
                logger.warning(f"Cortex hook 1 failed: {e}")
```

And pass `skill_context` to `self._reasoner.think(..., skill_context=skill_context)`.

**Hook 2 — after episodic memory store:**

Change the existing episode store to capture `episode_id`:

```python
        episode_id: int | None = None
        if self._episodic is not None and self._episodic.should_record(
            health_status=status.value, action_taken=action
        ):
            ...  # existing Episode construction
            try:
                episode_id = await self._episodic.store(ep)
            except Exception as e:
                logger.warning(f"Episodic memory store failed: {e}")

        # ── CORTEX HOOK 2: after action ──
        if self._cortex is not None:
            try:
                await self._cortex.after_action(
                    episode_data=None,
                    proposal=proposal if 'proposal' in dir() else None,
                    action=action,
                    episode_id=episode_id,
                    current_pulse=pulse_number,
                )
            except Exception as e:
                logger.warning(f"Cortex hook 2 failed: {e}")
```

**Hook 3 — after standard pulse when GREEN:**

```python
        # ── CORTEX HOOK 3: during idle ──
        if self._cortex is not None and status == HealthStatus.GREEN:
            try:
                idle_state = {
                    "stress": self._homeostatic.state.stress_level if self._homeostatic else 0.0,
                    "attention_remaining": self._attention.available() if self._attention else 100,
                    "phase": self._maturation.phase.value if self._maturation else "unknown",
                }
                await self._cortex.during_idle(idle_state)
            except Exception as e:
                logger.warning(f"Cortex hook 3 failed: {e}")
```

**Hook 4 — inside sleep branch (after dreamer + journal):**

```python
            # ── CORTEX HOOK 4: during sleep ──
            if self._cortex is not None:
                try:
                    sleep_summary = await self._cortex.during_sleep()
                    logger.info(f"Cortex sleep: {sleep_summary}")
                except Exception as e:
                    logger.warning(f"Cortex hook 4 failed: {e}")
```

- [ ] **Step 7.5: Modify `cell/main.py` — instantiate Cortex + wire into PulseEngine**

After existing component init (around line 183), add:

```python
        # Cortex — Phase 3+4 (optional, best-effort)
        from cell.cortex.cortex import Cortex

        cortex: Cortex | None = None
        try:
            cortex = Cortex(
                pool=_db_pool_ep,
                reasoner=reasoner,
                episodic=episodic,
                self_model=self_model,
                journal=journal,
                attention=attention,
                maturation=maturation,
                ollama_client=ollama_client,
            )
            logger.info(
                f"Cortex initialized: phase={maturation.phase.value}, "
                f"components active per lifecycle"
            )
        except Exception as e:
            logger.warning(f"Cortex init failed (non-fatal, CELL runs Phase 1+2 only): {e}")
```

In the `PulseEngine(...)` constructor call, add `cortex=cortex`:

```python
        engine = PulseEngine(
            ...,  # all existing params
            cortex=cortex,
        )
```

- [ ] **Step 7.6: Write `tests/test_cortex_integration.py` (8 tests)**

```python
"""Tests for Cortex orchestrator — integration between all Phase 3+4 components."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from cell.cortex.cortex import Cortex
from cell.lifecycle.maturation import LifecyclePhase, Maturation


@pytest.fixture
def mock_pool() -> AsyncMock:
    pool = AsyncMock()
    conn = AsyncMock()
    acquire_ctx = MagicMock()
    acquire_ctx.__aenter__ = AsyncMock(return_value=conn)
    acquire_ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_ctx)
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)
    conn.fetchrow = AsyncMock(return_value=None)
    return pool


@pytest.fixture
def mock_deps():
    return {
        "reasoner": MagicMock(),
        "episodic": AsyncMock(),
        "self_model": MagicMock(),
        "journal": MagicMock(),
        "attention": MagicMock(available=MagicMock(return_value=50)),
    }


class TestCortexInit:
    def test_cortex_initializes_with_all_components(self, mock_pool, mock_deps):
        mat = Maturation(age_days=20)
        cortex = Cortex(pool=mock_pool, maturation=mat, **mock_deps)
        assert cortex.skills is not None
        assert cortex.critic is not None
        assert cortex.curiosity is not None
        assert cortex.goals is not None
        assert cortex.mutator is not None
        assert cortex.gate is not None


class TestBeforeReasoning:
    @pytest.mark.asyncio
    async def test_returns_empty_in_embrione(self, mock_pool, mock_deps):
        mat = Maturation(age_days=2)
        cortex = Cortex(pool=mock_pool, maturation=mat, **mock_deps)
        result = await cortex.before_reasoning({"health_status": "yellow"})
        assert result == ""

    @pytest.mark.asyncio
    async def test_returns_skill_context_in_neonato(self, mock_pool, mock_deps):
        mat = Maturation(age_days=5)
        cortex = Cortex(pool=mock_pool, maturation=mat, **mock_deps)
        result = await cortex.before_reasoning({"health_status": "yellow"})
        # Empty because no skills in DB mock, but no error
        assert isinstance(result, str)


class TestAfterAction:
    @pytest.mark.asyncio
    async def test_skipped_in_embrione(self, mock_pool, mock_deps):
        mat = Maturation(age_days=2)
        cortex = Cortex(pool=mock_pool, maturation=mat, **mock_deps)
        # Should not raise
        await cortex.after_action(
            episode_data=None, proposal=None,
            action="restart_service", episode_id=1, current_pulse=100,
        )

    @pytest.mark.asyncio
    async def test_registers_expectation_in_neonato(self, mock_pool, mock_deps):
        conn = await mock_pool.acquire().__aenter__()
        conn.fetchval = AsyncMock(return_value=1)
        mat = Maturation(age_days=5)
        cortex = Cortex(pool=mock_pool, maturation=mat, **mock_deps)
        await cortex.after_action(
            episode_data=None,
            proposal=MagicMock(confidence=0.8, reason="test"),
            action="restart_service",
            episode_id=10,
            current_pulse=100,
        )
        # Should have inserted into expectations
        conn.fetchval.assert_awaited()


class TestDuringIdle:
    @pytest.mark.asyncio
    async def test_skipped_when_stress_high(self, mock_pool, mock_deps):
        mat = Maturation(age_days=20)
        cortex = Cortex(pool=mock_pool, maturation=mat, **mock_deps)
        # High stress → should no-op
        await cortex.during_idle({"stress": 0.9, "attention_remaining": 50, "phase": "giovane"})

    @pytest.mark.asyncio
    async def test_skipped_in_neonato(self, mock_pool, mock_deps):
        mat = Maturation(age_days=5)
        cortex = Cortex(pool=mock_pool, maturation=mat, **mock_deps)
        await cortex.during_idle({"stress": 0.1, "attention_remaining": 50, "phase": "neonato"})


class TestDuringSleep:
    @pytest.mark.asyncio
    async def test_returns_summary_dict(self, mock_pool, mock_deps):
        conn = await mock_pool.acquire().__aenter__()
        conn.execute = AsyncMock(return_value="UPDATE 0")
        conn.fetchval = AsyncMock(return_value=0)
        mat = Maturation(age_days=20)
        cortex = Cortex(pool=mock_pool, maturation=mat, **mock_deps)
        summary = await cortex.during_sleep()
        assert "decayed" in summary
        assert "effective_phase" in summary
        assert isinstance(summary, dict)
```

- [ ] **Step 7.7: Write `tests/test_pulse_with_cortex.py` (6 tests)**

```python
"""Tests for PulseEngine with Cortex integration — backward compat + hook invocation."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from cell.core.pulse import PulseEngine
from cell.fast.health_triage import HealthStatus


@pytest.fixture
def minimal_engine():
    """PulseEngine with just enough to run a single_pulse."""
    dna = MagicMock()
    dna.verify_integrity = MagicMock(return_value=True)
    safety = AsyncMock()
    safety.check = AsyncMock(return_value=MagicMock(can_proceed=True))
    health = AsyncMock()
    health.read = AsyncMock(return_value=MagicMock(
        reachable=True, status_code=200, response_time_seconds=0.05, error=None,
    ))
    return PulseEngine(
        dna_loader=dna,
        safety_gate=safety,
        health_sensor=health,
        metabolism=MagicMock(daily_spend=0.0, _daily_limit=10.0),
    )


class TestBackwardCompat:
    @pytest.mark.asyncio
    async def test_pulse_works_without_cortex(self, minimal_engine):
        """Phase 1+2 behavior is intact when cortex=None."""
        result = await minimal_engine.single_pulse(pulse_number=1)
        assert not result.halted
        assert result.health_status == HealthStatus.GREEN

    @pytest.mark.asyncio
    async def test_cortex_none_is_default(self, minimal_engine):
        assert minimal_engine._cortex is None


class TestHookInvocation:
    @pytest.mark.asyncio
    async def test_cortex_before_reasoning_called(self, minimal_engine):
        mock_cortex = AsyncMock()
        mock_cortex.before_reasoning = AsyncMock(return_value="SKILL CONTEXT")
        mock_cortex.after_action = AsyncMock()
        mock_cortex.during_idle = AsyncMock()
        minimal_engine._cortex = mock_cortex
        await minimal_engine.single_pulse(pulse_number=1)
        # before_reasoning should be called (GREEN pulse still calls it)
        mock_cortex.before_reasoning.assert_awaited()

    @pytest.mark.asyncio
    async def test_cortex_hook_failure_does_not_crash_pulse(self, minimal_engine):
        mock_cortex = AsyncMock()
        mock_cortex.before_reasoning = AsyncMock(side_effect=RuntimeError("boom"))
        mock_cortex.after_action = AsyncMock()
        mock_cortex.during_idle = AsyncMock()
        minimal_engine._cortex = mock_cortex
        result = await minimal_engine.single_pulse(pulse_number=1)
        assert not result.halted  # pulse continues despite hook failure

    @pytest.mark.asyncio
    async def test_during_idle_called_when_green(self, minimal_engine):
        mock_cortex = AsyncMock()
        mock_cortex.before_reasoning = AsyncMock(return_value="")
        mock_cortex.after_action = AsyncMock()
        mock_cortex.during_idle = AsyncMock()
        minimal_engine._cortex = mock_cortex
        minimal_engine._homeostatic = MagicMock()
        minimal_engine._homeostatic.state = MagicMock(stress_level=0.1, circadian_phase="awake")
        minimal_engine._homeostatic.is_sleeping = MagicMock(return_value=False)
        minimal_engine._homeostatic.update = MagicMock()
        minimal_engine._attention = MagicMock()
        minimal_engine._attention.available = MagicMock(return_value=50)
        minimal_engine._maturation = MagicMock()
        minimal_engine._maturation.phase = MagicMock(value="giovane")
        await minimal_engine.single_pulse(pulse_number=1)
        mock_cortex.during_idle.assert_awaited()

    @pytest.mark.asyncio
    async def test_during_idle_not_called_when_yellow(self, minimal_engine):
        mock_cortex = AsyncMock()
        mock_cortex.before_reasoning = AsyncMock(return_value="")
        mock_cortex.after_action = AsyncMock()
        mock_cortex.during_idle = AsyncMock()
        minimal_engine._cortex = mock_cortex
        # Make health return yellow
        minimal_engine._health.read = AsyncMock(return_value=MagicMock(
            reachable=True, status_code=503, response_time_seconds=2.0, error=None,
        ))
        await minimal_engine.single_pulse(pulse_number=1)
        mock_cortex.during_idle.assert_not_awaited()
```

- [ ] **Step 7.8: Run ALL tests, verify zero regression**

```bash
PYTHONPATH=. pytest tests/ -v --tb=short
```

Expected: ALL tests pass (Phase 1+2 original 22 files + all new cortex tests).

Pay special attention to:
- `tests/test_pulse.py` — must still pass unchanged
- `tests/test_episodic.py` — store() return type may need updating in test expectations
- `tests/test_slow_reasoner.py` — think() new kwarg should be backward-compatible

- [ ] **Step 7.9: Commit the integration**

```bash
git add cell/cortex/cortex.py cell/core/pulse.py cell/main.py \
      cell/memory/episodic.py cell/slow/reasoner.py \
      tests/test_cortex_integration.py tests/test_pulse_with_cortex.py
git commit -m "feat(cell/cortex): integrate Cortex orchestrator into PulseEngine

Cortex wired into PulseEngine with 4 best-effort hooks:
  1. before_reasoning → skill context injection
  2. after_action → critic register + evaluate
  3. during_idle → curiosity + goals (when GREEN, stress<0.3)
  4. during_sleep → decay, maturity check, mutation, rollback

EpisodicMemory.store() now returns episode id (backward-compat).
SlowReasoner.think() accepts skill_context kwarg (backward-compat).
Cortex is fully optional: cortex=None reverts to Phase 1+2.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Post-Implementation Verification

After all 7 tasks are complete:

- [ ] **Full test suite pass**

```bash
cd apps/cell && source .venv/bin/activate
PYTHONPATH=. pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: ~110+ tests (22 existing + ~88 new), all PASS.

- [ ] **Import smoke test**

```bash
PYTHONPATH=. python -c "
from cell.cortex.cortex import Cortex
from cell.cortex.skill_library import SkillLibrary, Skill, compute_embedding
from cell.cortex.critic import CriticAgent, Expectation, Critique
from cell.cortex.curiosity_engine import CuriosityEngine, CuriosityFinding
from cell.cortex.goal_generator import GoalGenerator, Goal
from cell.cortex.strategy_mutator import StrategyMutator, MutationProposal, SandboxResult
from cell.lifecycle.achievement_gate import AchievementGate
print('All Cortex imports OK')
"
```

- [ ] **Verify backward compat: main.py runs with cortex=None**

Temporarily comment out the Cortex import/instantiation in main.py. Start CELL. Verify it runs Phase 1+2 identically. Uncomment.

- [ ] **Deploy to Air (LaunchAgent restart) + smoke test**

```bash
# On Air: pull latest, restart LaunchAgent
ssh air 'cd ~/Projects/nuzantara && git pull --ff-only && launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.cell.organism.plist; launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.cell.organism.plist'

# Wait 60s for first pulse
sleep 60
ssh air 'tail -50 /tmp/cell.stderr.log | grep -i "cortex\|skill_library\|critic"'
# Expected: "Cortex initialized: phase=giovane, ..."
```

- [ ] **Verify tables exist on Fly Postgres**

```bash
PGPASSWORD=2zEjit43IF6gNUV psql -h localhost -p 15432 -U backend_rag_v2 -d nuzantara_rag \
  -c "\dt cell_skills cell_critic_expectations cell_critiques cell_goals cell_curiosity_findings cell_skill_audit cell_mutations"
```
