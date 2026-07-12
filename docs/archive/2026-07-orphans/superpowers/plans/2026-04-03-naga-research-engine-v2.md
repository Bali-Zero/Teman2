# Naga Agentic Research Engine — Implementation Plan v2

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a multi-model agentic research engine inside backend-rag that orchestrates 4 search agents, verifies claims through a quality pipeline, and produces actionable intelligence reports.

**Architecture:** Gateway classifier → LangGraph orchestrator (Opus) → 4 Search Agents (parallel) → Gemini Bulk Reader → Quality Pipeline (source scoring → shared claim extraction → adversarial convergence) → Report Writer → Action Engine. All inside `backend/services/naga/`. Pointer State Pattern for large data.

**Tech Stack:** Python 3.11, asyncio, asyncpg, httpx, FastAPI, LangGraph, google-generativeai

**Spec:** `docs/superpowers/specs/2026-04-03-naga-agentic-research-engine-design.md`

---

## Phase Overview

| Phase                            | What it builds                                                      | Tasks | Outcome                                              |
| -------------------------------- | ------------------------------------------------------------------- | ----- | ---------------------------------------------------- |
| **Phase 1: Foundation**          | DB schema, shared claims lib, config, state management, gateway     | 1-5   | Can classify queries and persist sessions            |
| **Phase 2: Search Layer**        | BaseSearchAgent, Exa, Brave, Indonesia Domain agents                | 6-9   | Can search across 4 sources, return ranked results   |
| **Phase 3: Quality + Synthesis** | Source scorer, CRAG-light, Gemini reader, convergence, reports      | 10-14 | Full research loop: search → verify → synthesize     |
| **Phase 4: Integration**         | LangGraph orchestrator, FastAPI, MCP tools, Action Engine, e2e test | 15-19 | Production-ready system accessible from all channels |

---

## File Structure

```
apps/backend-rag/backend/
├── services/naga/                     # Naga engine (ALL code lives here)
│   ├── __init__.py
│   ├── gateway.py                     # Tier/domain/mode classifier
│   ├── orchestrator.py                # LangGraph StateGraph orchestrator
│   ├── search_agents/
│   │   ├── __init__.py
│   │   ├── base.py                    # BaseSearchAgent ABC + SearchResult
│   │   ├── exa_agent.py              # Exa neural search
│   │   ├── brave_agent.py            # Brave web search
│   │   └── domain_agent.py           # Indonesia domain (ask_legal + intel + NLM + .go.id)
│   ├── quality/
│   │   ├── __init__.py
│   │   ├── source_scorer.py          # Configurable domain credibility
│   │   ├── crag_light.py             # Fast relevance gate (Haiku)
│   │   └── convergence.py            # Coverage + novelty + adversarial check
│   ├── synthesis/
│   │   ├── __init__.py
│   │   └── report_writer.py          # flash/deep/exhaustive templates
│   ├── actions/
│   │   ├── __init__.py
│   │   └── action_engine.py          # Deterministic trigger + audit trail
│   ├── readers/
│   │   ├── __init__.py
│   │   └── gemini_reader.py          # Bulk read → evidence_map file (Pointer State)
│   ├── state/
│   │   ├── __init__.py
│   │   ├── budget_tracker.py         # Cost + calls + TTL tracker
│   │   └── url_history.py            # Cross-iteration dedup
│   └── config/
│       ├── __init__.py
│       ├── naga_config.py            # Tier budgets, TTLs, thresholds
│       └── source_weights.json       # Configurable domain credibility scores
│
├── core/claims/                       # SHARED claim library (Naga + NLM)
│   ├── __init__.py
│   ├── extractor.py                   # Claim extraction from text
│   ├── models.py                      # ClaimRecord, ClaimCategory
│   └── confidence.py                  # 6-factor confidence scoring
│
├── app/routers/naga.py                # FastAPI endpoints
└── migrations/migration_079_naga_tables.py  # DB schema (079 because 078 exists)

# MCP integration (HTTP calls only, never direct imports):
apps/nuzantara-mcp/nuzantara_mcp/tools/naga.py
```

---

## PHASE 1: Foundation (Tasks 1-5)

### Task 1: Database Migration 079 — Naga Tables

**Files:**

- Create: `apps/backend-rag/backend/migrations/migration_079_naga_tables.py`

**Why 079:** Migration 078 already exists (`migration_078_ppq_step_tracking.py`).

- [ ] **Step 1: Write the test**

```python
# apps/backend-rag/backend/tests/migrations/test_migration_079_naga.py
"""Tests for Naga database migration 079."""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

logger = logging.getLogger(__name__)


@pytest.fixture
def mock_conn() -> AsyncMock:
    """Mock asyncpg connection that tracks executed SQL."""
    conn = AsyncMock()
    conn.executed_sql: list[str] = []

    async def capture_execute(sql: str, *args) -> None:
        conn.executed_sql.append(sql)

    conn.execute = AsyncMock(side_effect=capture_execute)
    return conn


@pytest.mark.asyncio
async def test_apply_creates_all_tables(mock_conn: AsyncMock) -> None:
    """Migration must create 5 tables + indexes."""
    from backend.migrations.migration_079_naga_tables import apply

    await apply(mock_conn)
    sql_joined = " ".join(mock_conn.executed_sql)

    # Core tables
    assert "naga_sessions" in sql_joined
    assert "naga_sources" in sql_joined
    assert "naga_claims" in sql_joined
    assert "naga_claim_evidence" in sql_joined
    assert "naga_claim_transitions" in sql_joined

    # Key columns
    assert "evidence_map_uri" in sql_joined
    assert "langgraph_thread_id" in sql_joined
    assert "review_status" in sql_joined

    # Indexes
    assert "idx_naga_claims_domain" in sql_joined
    assert "idx_naga_claims_review" in sql_joined
    assert "idx_naga_claim_evidence_claim" in sql_joined


@pytest.mark.asyncio
async def test_apply_is_idempotent(mock_conn: AsyncMock) -> None:
    """Running migration twice must not error (IF NOT EXISTS)."""
    from backend.migrations.migration_079_naga_tables import apply

    await apply(mock_conn)
    await apply(mock_conn)  # Second run must not raise
    assert mock_conn.execute.call_count >= 2  # Called at least twice (one per run)


@pytest.mark.asyncio
async def test_apply_uses_review_status_default(mock_conn: AsyncMock) -> None:
    """review_status must default to 'auto_extracted'."""
    from backend.migrations.migration_079_naga_tables import apply

    await apply(mock_conn)
    sql_joined = " ".join(mock_conn.executed_sql)
    assert "auto_extracted" in sql_joined
```

- [ ] **Step 2: Write the migration**

```python
# apps/backend-rag/backend/migrations/migration_079_naga_tables.py
"""
Migration 079: Naga Agentic Research Engine tables.

Creates:
  - naga_sessions: research session tracking + LangGraph thread
  - naga_sources: fetched source URLs with credibility
  - naga_claims: atomic verified claims with review gate
  - naga_claim_evidence: claim <-> source join table (replaces source_ids array)
  - naga_claim_transitions: claim supersession chain (replaces superseded_by)

Design: docs/superpowers/specs/2026-04-03-naga-agentic-research-engine-design.md
"""

import logging

logger = logging.getLogger(__name__)


async def apply(conn) -> None:
    """Create Naga tables and indexes."""

    # -- Sessions --
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS naga_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            parent_session_id UUID REFERENCES naga_sessions(id),
            query TEXT NOT NULL,
            tier VARCHAR(20) NOT NULL,
            domain VARCHAR(20) NOT NULL,
            mode VARCHAR(20) NOT NULL DEFAULT 'oneshot',
            channel VARCHAR(30),
            ttl_seconds INTEGER,
            trusted_mode BOOLEAN DEFAULT FALSE,
            status VARCHAR(20) DEFAULT 'running',
            duration_ms INTEGER,
            iterations INTEGER DEFAULT 0,
            search_calls INTEGER DEFAULT 0,
            sources_found INTEGER DEFAULT 0,
            claims_extracted INTEGER DEFAULT 0,
            avg_confidence FLOAT,
            report_markdown TEXT,
            report_drive_path TEXT,
            action_items JSONB DEFAULT '[]'::jsonb,
            evidence_map_uri TEXT,
            sub_questions JSONB,
            url_history TEXT[],
            langgraph_thread_id TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        );
    """)
    logger.info("Migration 079: created naga_sessions")

    # -- Sources --
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS naga_sources (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id UUID REFERENCES naga_sessions(id) ON DELETE CASCADE,
            url TEXT NOT NULL,
            title TEXT,
            domain VARCHAR(255),
            source_type VARCHAR(20),
            credibility_score FLOAT,
            freshness_date DATE,
            content_hash VARCHAR(64),
            content_archived BOOLEAN DEFAULT FALSE,
            drive_archive_path TEXT,
            fetched_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(url, session_id)
        );
    """)
    logger.info("Migration 079: created naga_sources")

    # -- Claims --
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS naga_claims (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id UUID REFERENCES naga_sessions(id) ON DELETE CASCADE,
            claim_text TEXT NOT NULL,
            claim_key VARCHAR(255),
            domain VARCHAR(20),
            topic_tags TEXT[],
            jurisdiction VARCHAR(50),
            verification_level VARCHAR(20),
            confidence FLOAT,
            cross_ref_count INTEGER DEFAULT 0,
            review_status VARCHAR(20) DEFAULT 'auto_extracted',
            valid_as_of DATE,
            expires_at DATE,
            resolution_hint TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)
    logger.info("Migration 079: created naga_claims")

    # -- Claim-Evidence join table --
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS naga_claim_evidence (
            id SERIAL PRIMARY KEY,
            claim_id UUID REFERENCES naga_claims(id) ON DELETE CASCADE,
            source_id UUID REFERENCES naga_sources(id) ON DELETE CASCADE,
            relation VARCHAR(20) NOT NULL,
            extraction_method VARCHAR(30),
            source_span_hint TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(claim_id, source_id, relation)
        );
    """)
    logger.info("Migration 079: created naga_claim_evidence")

    # -- Claim transitions --
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS naga_claim_transitions (
            id SERIAL PRIMARY KEY,
            from_claim_id UUID REFERENCES naga_claims(id) ON DELETE CASCADE,
            to_claim_id UUID REFERENCES naga_claims(id) ON DELETE CASCADE,
            transition_type VARCHAR(30) NOT NULL,
            reason TEXT,
            detected_by VARCHAR(30),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(from_claim_id, to_claim_id, transition_type)
        );
    """)
    logger.info("Migration 079: created naga_claim_transitions")

    # -- Indexes --
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_naga_sessions_parent ON naga_sessions(parent_session_id);
        CREATE INDEX IF NOT EXISTS idx_naga_sessions_status ON naga_sessions(status);
        CREATE INDEX IF NOT EXISTS idx_naga_sources_url ON naga_sources(url);
        CREATE INDEX IF NOT EXISTS idx_naga_sources_hash ON naga_sources(content_hash);
        CREATE INDEX IF NOT EXISTS idx_naga_claims_domain ON naga_claims(domain);
        CREATE INDEX IF NOT EXISTS idx_naga_claims_topic ON naga_claims USING GIN(topic_tags);
        CREATE INDEX IF NOT EXISTS idx_naga_claims_confidence ON naga_claims(confidence DESC);
        CREATE INDEX IF NOT EXISTS idx_naga_claims_valid ON naga_claims(valid_as_of DESC);
        CREATE INDEX IF NOT EXISTS idx_naga_claims_verification ON naga_claims(verification_level);
        CREATE INDEX IF NOT EXISTS idx_naga_claims_review ON naga_claims(review_status);
        CREATE INDEX IF NOT EXISTS idx_naga_claims_key ON naga_claims(claim_key);
        CREATE INDEX IF NOT EXISTS idx_naga_claim_evidence_claim ON naga_claim_evidence(claim_id);
        CREATE INDEX IF NOT EXISTS idx_naga_claim_evidence_source ON naga_claim_evidence(source_id);
        CREATE INDEX IF NOT EXISTS idx_naga_claim_transitions_from ON naga_claim_transitions(from_claim_id);
        CREATE INDEX IF NOT EXISTS idx_naga_claim_transitions_to ON naga_claim_transitions(to_claim_id);
    """)
    logger.info("Migration 079: created all Naga indexes")
```

- [ ] **Step 3: Run test**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/migrations/test_migration_079_naga.py -v
# Expected: 3 passed
```

- [ ] **Step 4: Apply migration to local DB**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. python -c "
import asyncio, asyncpg, os
from backend.migrations.migration_079_naga_tables import apply

async def run():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])
    try:
        await apply(conn)
        print('Migration 079 applied successfully')
    finally:
        await conn.close()

asyncio.run(run())
"
```

- [ ] **Step 5: Verify tables exist**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. python -c "
import asyncio, asyncpg, os

async def check():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])
    tables = await conn.fetch(\"\"\"
        SELECT tablename FROM pg_tables
        WHERE tablename LIKE 'naga_%'
        ORDER BY tablename
    \"\"\")
    for t in tables:
        print(f'  {t[\"tablename\"]}')
    assert len(tables) == 5, f'Expected 5 tables, got {len(tables)}'
    print(f'All {len(tables)} Naga tables created')
    await conn.close()

asyncio.run(check())
"
# Expected: naga_claim_evidence, naga_claim_transitions, naga_claims, naga_sessions, naga_sources
```

- [ ] **Step 6: Commit**

```bash
git add apps/backend-rag/backend/migrations/migration_079_naga_tables.py \
        apps/backend-rag/backend/tests/migrations/test_migration_079_naga.py
git commit -m "feat(naga): add migration 079 — Naga research engine tables"
```

---

### Task 2: Config + source_weights.json

**Files:**

- Create: `apps/backend-rag/backend/services/naga/__init__.py`
- Create: `apps/backend-rag/backend/services/naga/config/__init__.py`
- Create: `apps/backend-rag/backend/services/naga/config/naga_config.py`
- Create: `apps/backend-rag/backend/services/naga/config/source_weights.json`

- [ ] **Step 1: Write the test**

```python
# apps/backend-rag/backend/tests/services/naga/test_config.py
"""Tests for Naga configuration module."""

import json
from pathlib import Path

import pytest


class TestNagaConfig:
    """Test NagaConfig tier/budget/threshold settings."""

    def test_tier_budgets_have_all_tiers(self) -> None:
        from backend.services.naga.config.naga_config import NagaConfig

        config = NagaConfig()
        assert "flash" in config.tier_budgets
        assert "deep" in config.tier_budgets
        assert "exhaustive" in config.tier_budgets

    def test_flash_tier_has_correct_limits(self) -> None:
        from backend.services.naga.config.naga_config import NagaConfig

        config = NagaConfig()
        flash = config.tier_budgets["flash"]
        assert flash.max_searches <= 5
        assert flash.max_gemini_sources == 0  # Flash does not use Gemini
        assert flash.max_iterations == 1

    def test_deep_tier_allows_gemini(self) -> None:
        from backend.services.naga.config.naga_config import NagaConfig

        config = NagaConfig()
        deep = config.tier_budgets["deep"]
        assert deep.max_gemini_sources > 0
        assert deep.max_iterations >= 2

    def test_exhaustive_is_highest(self) -> None:
        from backend.services.naga.config.naga_config import NagaConfig

        config = NagaConfig()
        exh = config.tier_budgets["exhaustive"]
        deep = config.tier_budgets["deep"]
        assert exh.max_searches > deep.max_searches
        assert exh.max_iterations >= deep.max_iterations

    def test_convergence_defaults(self) -> None:
        from backend.services.naga.config.naga_config import NagaConfig

        config = NagaConfig()
        assert 0 < config.convergence_coverage_threshold <= 1.0
        assert 0 < config.convergence_novelty_threshold <= 1.0

    def test_source_score_min_threshold(self) -> None:
        from backend.services.naga.config.naga_config import NagaConfig

        config = NagaConfig()
        assert 0.0 < config.source_score_min < 1.0


class TestSourceWeights:
    """Test source_weights.json schema and content."""

    def test_source_weights_file_exists(self) -> None:
        weights_path = (
            Path(__file__).parent.parent.parent.parent
            / "services"
            / "naga"
            / "config"
            / "source_weights.json"
        )
        assert weights_path.exists(), f"source_weights.json not found at {weights_path}"

    def test_source_weights_is_valid_json(self) -> None:
        weights_path = (
            Path(__file__).parent.parent.parent.parent
            / "services"
            / "naga"
            / "config"
            / "source_weights.json"
        )
        data = json.loads(weights_path.read_text())
        assert isinstance(data, dict)
        assert "default" in data
        assert "domain_overrides" in data

    def test_default_weights_have_required_keys(self) -> None:
        weights_path = (
            Path(__file__).parent.parent.parent.parent
            / "services"
            / "naga"
            / "config"
            / "source_weights.json"
        )
        data = json.loads(weights_path.read_text())
        defaults = data["default"]
        required = ["gov", "academic", "major_news", "blog", "forum"]
        for key in required:
            assert key in defaults, f"Missing default weight: {key}"
            assert 0.0 <= defaults[key] <= 1.0

    def test_gov_id_domains_present(self) -> None:
        weights_path = (
            Path(__file__).parent.parent.parent.parent
            / "services"
            / "naga"
            / "config"
            / "source_weights.json"
        )
        data = json.loads(weights_path.read_text())
        overrides = data["domain_overrides"]
        assert ".go.id" in overrides or "go.id" in overrides
```

- [ ] **Step 2: Create init files and config module**

```python
# apps/backend-rag/backend/services/naga/__init__.py
"""Naga Agentic Research Engine — multi-model research with verified claims."""
```

```python
# apps/backend-rag/backend/services/naga/config/__init__.py
"""Naga configuration: tier budgets, source weights, thresholds."""

from backend.services.naga.config.naga_config import NagaConfig

__all__ = ["NagaConfig"]
```

```python
# apps/backend-rag/backend/services/naga/config/naga_config.py
"""Naga research engine configuration.

Defines tier budgets, convergence thresholds, model selection,
and source scoring parameters. All values are overridable via
environment variables with NAGA_ prefix.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_WEIGHTS_PATH = Path(__file__).parent / "source_weights.json"


@dataclass(frozen=True)
class TierBudget:
    """Budget constraints for a research tier."""

    max_searches: int
    max_gemini_sources: int
    max_iterations: int
    default_ttl_seconds: int


@dataclass
class NagaConfig:
    """Central configuration for the Naga research engine.

    Attributes:
        tier_budgets: Per-tier resource limits.
        convergence_coverage_threshold: Min % sub-questions answered to converge.
        convergence_novelty_threshold: Max novelty ratio to consider saturated.
        source_score_min: Sources below this score are discarded.
        source_weights: Domain credibility weights loaded from JSON.
    """

    tier_budgets: dict[str, TierBudget] = field(default_factory=lambda: {
        "flash": TierBudget(
            max_searches=3,
            max_gemini_sources=0,
            max_iterations=1,
            default_ttl_seconds=15,
        ),
        "deep": TierBudget(
            max_searches=25,
            max_gemini_sources=20,
            max_iterations=3,
            default_ttl_seconds=300,
        ),
        "exhaustive": TierBudget(
            max_searches=80,
            max_gemini_sources=50,
            max_iterations=5,
            default_ttl_seconds=1800,
        ),
    })

    convergence_coverage_threshold: float = 0.80
    convergence_novelty_threshold: float = 0.10
    source_score_min: float = 0.30
    adversarial_enabled: bool = True

    # Model selection
    model_classifier: str = field(
        default_factory=lambda: os.getenv("NAGA_MODEL_CLASSIFIER", "claude-haiku-4-5-20251001")
    )
    model_orchestrator: str = field(
        default_factory=lambda: os.getenv("NAGA_MODEL_ORCHESTRATOR", "claude-opus-4-6")
    )
    model_crag: str = field(
        default_factory=lambda: os.getenv("NAGA_MODEL_CRAG", "claude-haiku-4-5-20251001")
    )
    model_reader: str = field(
        default_factory=lambda: os.getenv("NAGA_MODEL_READER", "gemini-2.5-pro")
    )

    # Paths
    evidence_base_dir: str = field(
        default_factory=lambda: os.getenv("NAGA_EVIDENCE_DIR", "/tmp/naga")
    )

    source_weights: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Load source weights from JSON if not already set."""
        if not self.source_weights:
            self.source_weights = self._load_source_weights()

    @staticmethod
    def _load_source_weights() -> dict[str, Any]:
        """Load source credibility weights from JSON file."""
        if _WEIGHTS_PATH.exists():
            try:
                data = json.loads(_WEIGHTS_PATH.read_text(encoding="utf-8"))
                logger.info("Loaded source weights from %s", _WEIGHTS_PATH)
                return data
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load source_weights.json: %s", exc)
        return {
            "default": {"gov": 0.9, "academic": 0.85, "major_news": 0.6, "blog": 0.4, "forum": 0.2},
            "domain_overrides": {},
        }

    def get_source_weight(self, domain: str, source_type: str) -> float:
        """Look up credibility weight for a domain + source_type.

        Args:
            domain: URL domain (e.g., 'pajak.go.id').
            source_type: Category (gov/academic/major_news/blog/forum).

        Returns:
            Credibility weight 0.0-1.0.
        """
        overrides = self.source_weights.get("domain_overrides", {})
        # Check exact domain first, then suffix match
        if domain in overrides:
            return float(overrides[domain])
        for suffix, weight in overrides.items():
            if domain.endswith(suffix):
                return float(weight)
        defaults = self.source_weights.get("default", {})
        return float(defaults.get(source_type, 0.5))
```

- [ ] **Step 3: Create source_weights.json**

```json
{
  "default": {
    "gov": 0.9,
    "academic": 0.85,
    "major_news": 0.6,
    "blog": 0.4,
    "forum": 0.2
  },
  "domain_overrides": {
    ".go.id": 0.9,
    "pajak.go.id": 0.95,
    "imigrasi.go.id": 0.95,
    "oss.go.id": 0.92,
    "kemenkumham.go.id": 0.92,
    "bkpm.go.id": 0.9,
    "reuters.com": 0.75,
    "thejakartapost.com": 0.65,
    "kompas.com": 0.6,
    "tempo.co": 0.6,
    "detik.com": 0.5,
    "coconuts.co": 0.45,
    "expat.or.id": 0.4,
    "kaskus.co.id": 0.25,
    "reddit.com": 0.2
  },
  "freshness_decay": {
    "days_30": 1.0,
    "days_365": 0.7,
    "days_1095": 0.5,
    "older": 0.3
  }
}
```

- [ ] **Step 4: Run test**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/naga/test_config.py -v
# Expected: 8 passed
```

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/services/naga/__init__.py \
        apps/backend-rag/backend/services/naga/config/ \
        apps/backend-rag/backend/tests/services/naga/test_config.py
git commit -m "feat(naga): add config module + source_weights.json"
```

---

### Task 3: Shared Claims Library

Promote `apps/evaluator/nlm_deep_research/claim_extractor.py` to `backend/core/claims/`. Both Naga and NLM will import from here. The original file becomes a thin re-export wrapper.

**Files:**

- Create: `apps/backend-rag/backend/core/claims/__init__.py`
- Create: `apps/backend-rag/backend/core/claims/models.py`
- Create: `apps/backend-rag/backend/core/claims/confidence.py`
- Create: `apps/backend-rag/backend/core/claims/extractor.py`

- [ ] **Step 1: Write the test**

```python
# apps/backend-rag/backend/tests/core/test_claims.py
"""Tests for the shared claims library (core/claims/)."""

import pytest

from backend.core.claims.models import ClaimRecord, CLAIM_CATEGORIES
from backend.core.claims.confidence import (
    compute_confidence,
    classify_confidence,
    CONFIDENCE_VERIFIED,
    CONFIDENCE_PROVISIONAL,
)
from backend.core.claims.extractor import extract_claims_from_response


class TestClaimRecord:
    """Test ClaimRecord dataclass."""

    def test_create_minimal(self) -> None:
        claim = ClaimRecord(
            claim_id="NB2-abc12345",
            claim_text="KITAS E23 requires RPTKA.",
            category="DOCUMENT_REQUIREMENT",
            confidence_class="VERIFIED",
            confidence_score=0.85,
            source_ids=["src-1"],
            extracted="2026-04-03T00:00:00Z",
        )
        assert claim.claim_id == "NB2-abc12345"
        assert claim.status == "active"

    def test_to_dict_omits_empty(self) -> None:
        claim = ClaimRecord(
            claim_id="NB2-abc12345",
            claim_text="Test claim.",
            category="LEGAL_CHANGE",
            confidence_class="LIKELY",
            confidence_score=0.60,
            source_ids=["s1"],
            extracted="2026-04-03T00:00:00Z",
        )
        d = claim.to_dict()
        assert "affected_visa_types" not in d  # Empty list omitted
        assert "claim_id" in d

    def test_categories_include_required(self) -> None:
        required = [
            "LEGAL_CHANGE",
            "OPERATIONAL_CHANGE",
            "ENFORCEMENT_ACTION",
            "FEE_CHANGE",
            "PROCEDURAL_STEP",
            "DOCUMENT_REQUIREMENT",
            "ELIGIBILITY_RULE",
        ]
        for cat in required:
            assert cat in CLAIM_CATEGORIES


class TestConfidence:
    """Test 6-factor confidence scoring."""

    def test_perfect_score(self) -> None:
        score = compute_confidence(
            highest_tier=0,
            source_count=3,
            has_specific_pasal=True,
            is_regulatory=True,
            days_since_pub=10,
            is_bali_specific=False,
        )
        assert score >= 0.90

    def test_single_weak_source(self) -> None:
        score = compute_confidence(
            highest_tier=6,
            source_count=1,
            has_specific_pasal=False,
            is_regulatory=False,
            days_since_pub=400,
            is_bali_specific=False,
        )
        assert score < 0.55

    def test_classify_verified(self) -> None:
        assert classify_confidence(0.80) == "VERIFIED"

    def test_classify_provisional(self) -> None:
        assert classify_confidence(0.60) == "PROVISIONAL"

    def test_classify_low(self) -> None:
        assert classify_confidence(0.30) == "LOW"

    def test_confidence_bounded_0_1(self) -> None:
        score = compute_confidence(
            highest_tier=0,
            source_count=100,
            has_specific_pasal=True,
            is_regulatory=True,
            days_since_pub=1,
            is_bali_specific=True,
        )
        assert 0.0 <= score <= 1.0


class TestExtractor:
    """Test claim extraction from response text."""

    def test_extract_from_regulatory_text(self) -> None:
        text = (
            "Berdasarkan Peraturan Pemerintah Nomor 28 Tahun 2025 Pasal 45, "
            "biaya PNBP untuk KITAS E23 ditetapkan sebesar Rp 3.500.000 yang "
            "berlaku sejak tanggal diundangkan."
        )
        claims = extract_claims_from_response(
            response_text=text,
            source_ids=["src-1"],
            query_cluster="A",
        )
        assert len(claims) >= 1
        assert claims[0].category in CLAIM_CATEGORIES
        assert claims[0].confidence_score > 0

    def test_extract_skips_short_text(self) -> None:
        text = "Short text.\nAnother short."
        claims = extract_claims_from_response(
            response_text=text,
            source_ids=["src-1"],
            query_cluster="A",
        )
        assert len(claims) == 0  # Both under 50 chars

    def test_extract_detects_visa_types(self) -> None:
        text = (
            "The KITAS E23 work permit (TKA) requires an approved RPTKA from "
            "the Ministry of Manpower before the foreign worker can commence "
            "employment in Indonesia."
        )
        claims = extract_claims_from_response(
            response_text=text,
            source_ids=["src-1"],
            query_cluster="A",
        )
        assert len(claims) >= 1
        visa_types = claims[0].affected_visa_types
        assert "KITAS_E23" in visa_types
```

- [ ] **Step 2: Create models.py**

```python
# apps/backend-rag/backend/core/claims/models.py
"""Claim data models shared between Naga and NLM pipelines.

This is the single source of truth for claim categories, ClaimRecord,
and verification levels. Both `backend.services.naga` and
`apps.evaluator.nlm_deep_research` import from here.
"""

import re
import uuid
from dataclasses import asdict, dataclass, field
from typing import Optional

# 15 claim categories (from NLM Deep Research spec section 3)
CLAIM_CATEGORIES: list[str] = [
    "LEGAL_CHANGE",
    "OPERATIONAL_CHANGE",
    "ENFORCEMENT_ACTION",
    "ENFORCEMENT_PATTERN",
    "POLICY_SIGNAL",
    "PROCEDURAL_STEP",
    "LOCAL_REGULATION",
    "DOCUMENT_REQUIREMENT",
    "FEE_CHANGE",
    "SOURCE_GAP",
    "SOURCE_REGISTRATION",
    "BASELINE_EXISTING",
    "SYSTEM_STATUS",
    "PROCESSING_TIME",
    "ELIGIBILITY_RULE",
]

# Verification levels (from Naga spec section 4)
VERIFICATION_LEVELS: list[str] = [
    "VERIFIED",     # 0.85-1.0 — 3+ concordant sources
    "LIKELY",       # 0.50-0.84 — 1-2 sources, no contradiction
    "CONTESTED",    # 0.30-0.49 — sources in contradiction
    "UNVERIFIED",   # 0.15-0.29 — single unreliable source
    "ABSTAIN",      # <0.15 — no usable source
]

# Review status lifecycle
REVIEW_STATUSES: list[str] = [
    "auto_extracted",
    "pending_review",
    "human_verified",
    "active",
    "rejected",
]


@dataclass
class ClaimRecord:
    """Atomic verifiable claim extracted from a research source.

    Attributes:
        claim_id: Unique ID (prefix-8hex, e.g. 'NB2-a3f8c012').
        claim_text: The claim statement (max 500 chars).
        category: One of CLAIM_CATEGORIES.
        confidence_class: VERIFIED/PROVISIONAL/LOW.
        confidence_score: 0.0-1.0 from 6-factor formula.
        source_ids: IDs of backing sources.
        extracted: ISO 8601 timestamp of extraction.
        status: active/superseded/rejected.
        geographic_scope: NATIONAL/LOCAL_BALI.
        affected_visa_types: Visa types mentioned in claim.
        affected_services: Business services affected.
        flags: Additional metadata.
    """

    claim_id: str
    claim_text: str
    category: str
    confidence_class: str
    confidence_score: float
    source_ids: list[str]
    extracted: str
    status: str = "active"
    geographic_scope: str = "NATIONAL"
    affected_visa_types: list[str] = field(default_factory=list)
    affected_services: list[str] = field(default_factory=list)
    flags: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to dict, omitting empty values."""
        return {k: v for k, v in asdict(self).items() if v}


def generate_claim_id(prefix: str = "NB2") -> str:
    """Generate unique claim ID with prefix.

    Args:
        prefix: ID prefix (NB2 for NLM, NAGA for Naga engine).

    Returns:
        String like 'NB2-a3f8c012'.
    """
    short_uuid = uuid.uuid4().hex[:8]
    return f"{prefix}-{short_uuid}"


def detect_visa_types(text: str) -> list[str]:
    """Detect visa type references in claim text.

    Args:
        text: Claim text to scan.

    Returns:
        List of detected visa type codes.
    """
    types: list[str] = []
    patterns: dict[str, str] = {
        "KITAS_E23": r"(?i)(E23|KITAS\s*kerja|TKA)",
        "KITAS_E28": r"(?i)(E28[ABCD]|golden\s*visa|investit)",
        "KITAS_E31": r"(?i)(E31|family|keluarga|dependent)",
        "KITAS_E33": r"(?i)(E33[A-G]|second\s*home|pensiun|silver\s*hair|digital\s*nomad)",
        "VISA_C1": r"(?i)(C1|B211A|tourist|wisata)",
        "VISA_C2": r"(?i)(C2|bisnis|business\s*visit)",
        "VOA": r"(?i)(VOA|visa\s*on\s*arrival|e-?VOA)",
        "KITAP": r"(?i)(KITAP|izin\s*tinggal\s*tetap|permanent)",
    }
    for vtype, pattern in patterns.items():
        if re.search(pattern, text):
            types.append(vtype)
    return types
```

- [ ] **Step 3: Create confidence.py**

```python
# apps/backend-rag/backend/core/claims/confidence.py
"""6-factor confidence scoring for claims.

Shared by Naga and NLM pipelines. Uses the same weights and thresholds
defined in NLM Deep Research spec section 3.
"""

# Confidence thresholds
CONFIDENCE_VERIFIED: float = 0.75
CONFIDENCE_PROVISIONAL: float = 0.55
CONFIDENCE_MONITORING: float = 0.35

# Factor weights (from NLM spec)
W_AUTH: float = 0.30
W_CORR: float = 0.25
W_SPEC: float = 0.15
W_TYPE: float = 0.12
W_RECENCY: float = 0.10
W_GEO: float = 0.08

# Tier authority scores
TIER_AUTHORITY: dict[int, float] = {
    0: 1.00,   # T0: primary legislation (UU)
    1: 0.95,   # T1: government regulation (PP)
    2: 0.90,   # T2: ministerial regulation (Permen)
    3: 0.80,   # T3: official agency guidance
    4: 0.75,   # T4: reputable news/analysis
    5: 0.60,   # T5: community/practice sources
    6: 0.30,   # T6: unverified/forum
}


def compute_confidence(
    highest_tier: int,
    source_count: int,
    has_specific_pasal: bool,
    is_regulatory: bool,
    days_since_pub: int,
    is_bali_specific: bool,
) -> float:
    """Compute confidence score using 6-factor weighted formula.

    Args:
        highest_tier: Best (lowest) tier among backing sources (0=T0, 6=T6).
        source_count: Number of distinct sources backing this claim.
        has_specific_pasal: Whether claim cites specific pasal/ayat.
        is_regulatory: Whether claim is about a regulation.
        days_since_pub: Days since source publication.
        is_bali_specific: Whether claim is specific to Bali.

    Returns:
        Confidence score in [0.0, 1.0].
    """
    s_auth = TIER_AUTHORITY.get(highest_tier, 0.50)
    s_corr = min(1.0, source_count / 3)
    s_spec = 1.0 if has_specific_pasal else 0.6
    s_type = 1.0 if is_regulatory else 0.7

    if days_since_pub <= 30:
        s_recency = 1.0
    elif days_since_pub <= 180:
        s_recency = 0.8
    elif days_since_pub <= 365:
        s_recency = 0.6
    else:
        s_recency = 0.4

    s_geo = 0.9 if is_bali_specific else 1.0

    score = (
        W_AUTH * s_auth
        + W_CORR * s_corr
        + W_SPEC * s_spec
        + W_TYPE * s_type
        + W_RECENCY * s_recency
        + W_GEO * s_geo
    )
    return round(min(1.0, max(0.0, score)), 3)


def classify_confidence(score: float) -> str:
    """Classify confidence score into VERIFIED/PROVISIONAL/LOW.

    Args:
        score: Confidence score 0.0-1.0.

    Returns:
        'VERIFIED', 'PROVISIONAL', or 'LOW'.
    """
    if score >= CONFIDENCE_VERIFIED:
        return "VERIFIED"
    elif score >= CONFIDENCE_PROVISIONAL:
        return "PROVISIONAL"
    return "LOW"
```

- [ ] **Step 4: Create extractor.py**

```python
# apps/backend-rag/backend/core/claims/extractor.py
"""Claim extraction from text responses.

Extracts atomic claims from NLM/Naga responses by splitting into
paragraphs, classifying category via keyword matching, and scoring
confidence via the 6-factor formula.

For production Naga, the orchestrator may use LLM-assisted extraction
in addition to this rule-based extractor.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from backend.core.claims.confidence import classify_confidence, compute_confidence
from backend.core.claims.models import (
    CLAIM_CATEGORIES,
    ClaimRecord,
    detect_visa_types,
    generate_claim_id,
)

logger = logging.getLogger(__name__)


def extract_claims_from_response(
    response_text: str,
    source_ids: list[str],
    query_cluster: str,
    sources_metadata: Optional[dict] = None,
    claim_id_prefix: str = "NB2",
) -> list[ClaimRecord]:
    """Extract atomic claims from an NLM/Naga query response.

    Splits response into paragraphs, identifies claim-like statements
    (>50 chars, not headers/tables), classifies category via keywords,
    and scores confidence via 6-factor formula.

    Args:
        response_text: Raw response text.
        source_ids: Source IDs cited in response.
        query_cluster: Cluster letter (A-E) for context.
        sources_metadata: Optional source registry for tier lookup.
        claim_id_prefix: Prefix for generated claim IDs.

    Returns:
        List of extracted ClaimRecord objects.
    """
    claims: list[ClaimRecord] = []
    now = datetime.now(timezone.utc).isoformat()

    paragraphs = [
        p.strip()
        for p in response_text.split("\n")
        if p.strip()
        and not p.strip().startswith("#")
        and not p.strip().startswith("**Nama File")
        and len(p.strip()) > 50
    ]

    for para in paragraphs:
        if para.startswith("*") and para.endswith("*"):
            continue
        if para.startswith("|") or para.startswith("---"):
            continue

        has_pasal = bool(
            re.search(r"(?i)(pasal|ayat|UU|PP|Permen|Kepmen|SE\s)", para)
        )
        is_regulatory = bool(
            re.search(
                r"(?i)(peraturan|undang|regulasi|ketentuan|ditetapkan|berlaku)",
                para,
            )
        )
        is_bali = bool(
            re.search(r"(?i)(bali|ngurah rai|denpasar|badung|gianyar)", para)
        )

        highest_tier = 2
        if sources_metadata:
            for sid in source_ids:
                src = sources_metadata.get(sid, {})
                tier = src.get("tier", 2)
                highest_tier = min(highest_tier, tier)

        confidence = compute_confidence(
            highest_tier=highest_tier,
            source_count=len(source_ids),
            has_specific_pasal=has_pasal,
            is_regulatory=is_regulatory,
            days_since_pub=30,
            is_bali_specific=is_bali,
        )

        category = _classify_category(para)
        geo = "LOCAL_BALI" if is_bali else "NATIONAL"
        visa_types = detect_visa_types(para)

        claim = ClaimRecord(
            claim_id=generate_claim_id(claim_id_prefix),
            claim_text=para[:500],
            category=category,
            confidence_class=classify_confidence(confidence),
            confidence_score=confidence,
            source_ids=source_ids,
            extracted=now,
            geographic_scope=geo,
            affected_visa_types=visa_types,
        )
        claims.append(claim)

    logger.info(
        "Extracted %d claims from response (%d paragraphs)",
        len(claims),
        len(paragraphs),
    )
    return claims


def _classify_category(text: str) -> str:
    """Classify claim category via keyword matching.

    Args:
        text: Claim text.

    Returns:
        One of CLAIM_CATEGORIES.
    """
    text_lower = text.lower()

    rules: list[tuple[list[str], str]] = [
        (["mencabut", "menggantikan", "perubahan", "amended", "revoked"], "LEGAL_CHANGE"),
        (["tarif", "biaya", "pnbp", "fee", "rp ", "usd "], "FEE_CHANGE"),
        (["deportasi", "overstay", "pelanggaran", "sanksi"], "ENFORCEMENT_ACTION"),
        (["tim pora", "sidak", "operasi gabungan", "razia"], "ENFORCEMENT_PATTERN"),
        (["prosedur", "langkah", "step", "tahap"], "PROCEDURAL_STEP"),
        (["syarat", "persyaratan", "dokumen", "requirement"], "DOCUMENT_REQUIREMENT"),
        (["perda", "pergub", "kabupaten", "provinsi"], "LOCAL_REGULATION"),
        (["wajib", "dilarang", "eligible", "minimum"], "ELIGIBILITY_RULE"),
        (["sistem", "portal", "online", "digital"], "SYSTEM_STATUS"),
        (["hari kerja", "working days", "waktu proses"], "PROCESSING_TIME"),
    ]
    for keywords, category in rules:
        if any(w in text_lower for w in keywords):
            return category
    return "OPERATIONAL_CHANGE"
```

- [ ] **Step 5: Create **init**.py**

```python
# apps/backend-rag/backend/core/claims/__init__.py
"""Shared claim extraction library.

Used by both Naga research engine and NLM Deep Research pipeline.
Single source of truth for claim categories, confidence scoring,
and ClaimRecord format.
"""

from backend.core.claims.confidence import classify_confidence, compute_confidence
from backend.core.claims.extractor import extract_claims_from_response
from backend.core.claims.models import (
    CLAIM_CATEGORIES,
    ClaimRecord,
    generate_claim_id,
)

__all__ = [
    "CLAIM_CATEGORIES",
    "ClaimRecord",
    "classify_confidence",
    "compute_confidence",
    "extract_claims_from_response",
    "generate_claim_id",
]
```

- [ ] **Step 6: Run test**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/core/test_claims.py -v
# Expected: 10 passed
```

- [ ] **Step 7: Commit**

```bash
git add apps/backend-rag/backend/core/claims/ \
        apps/backend-rag/backend/tests/core/test_claims.py
git commit -m "feat(claims): create shared claims library in backend/core/claims/"
```

---

### Task 4: State Management — BudgetTracker + URLHistory

**Files:**

- Create: `apps/backend-rag/backend/services/naga/state/__init__.py`
- Create: `apps/backend-rag/backend/services/naga/state/budget_tracker.py`
- Create: `apps/backend-rag/backend/services/naga/state/url_history.py`

- [ ] **Step 1: Write the test**

```python
# apps/backend-rag/backend/tests/services/naga/test_state.py
"""Tests for Naga state management: BudgetTracker + URLHistory."""

import time

import pytest

from backend.services.naga.state.budget_tracker import BudgetTracker
from backend.services.naga.state.url_history import URLHistory


class TestBudgetTracker:
    """Test search/source/TTL budget tracking."""

    def test_initial_budget(self) -> None:
        bt = BudgetTracker(max_searches=10, max_gemini_sources=5, ttl_seconds=300)
        assert bt.searches_remaining == 10
        assert bt.gemini_sources_remaining == 5
        assert bt.is_expired is False

    def test_consume_search(self) -> None:
        bt = BudgetTracker(max_searches=3, max_gemini_sources=0, ttl_seconds=60)
        bt.consume_search(count=2)
        assert bt.searches_remaining == 1
        bt.consume_search()
        assert bt.searches_remaining == 0

    def test_consume_search_raises_on_overbudget(self) -> None:
        bt = BudgetTracker(max_searches=1, max_gemini_sources=0, ttl_seconds=60)
        bt.consume_search()
        with pytest.raises(ValueError, match="budget"):
            bt.consume_search()

    def test_consume_gemini(self) -> None:
        bt = BudgetTracker(max_searches=10, max_gemini_sources=3, ttl_seconds=60)
        bt.consume_gemini_sources(2)
        assert bt.gemini_sources_remaining == 1

    def test_ttl_expiry(self) -> None:
        bt = BudgetTracker(max_searches=10, max_gemini_sources=5, ttl_seconds=0)
        # TTL=0 means already expired
        assert bt.is_expired is True

    def test_has_budget(self) -> None:
        bt = BudgetTracker(max_searches=1, max_gemini_sources=0, ttl_seconds=300)
        assert bt.has_budget is True
        bt.consume_search()
        assert bt.has_budget is False

    def test_summary(self) -> None:
        bt = BudgetTracker(max_searches=10, max_gemini_sources=5, ttl_seconds=300)
        bt.consume_search(3)
        s = bt.summary()
        assert s["searches_used"] == 3
        assert s["searches_remaining"] == 7


class TestURLHistory:
    """Test cross-iteration URL dedup."""

    def test_add_and_contains(self) -> None:
        h = URLHistory()
        h.add("https://example.com/page1")
        assert h.contains("https://example.com/page1") is True
        assert h.contains("https://example.com/page2") is False

    def test_add_returns_is_new(self) -> None:
        h = URLHistory()
        assert h.add("https://a.com") is True   # New
        assert h.add("https://a.com") is False   # Duplicate

    def test_dedup_filters_list(self) -> None:
        h = URLHistory()
        h.add("https://a.com")
        h.add("https://b.com")
        urls = ["https://a.com", "https://c.com", "https://d.com"]
        new_urls = h.dedup(urls)
        assert new_urls == ["https://c.com", "https://d.com"]

    def test_url_normalization(self) -> None:
        h = URLHistory()
        h.add("https://example.com/page?a=1&b=2#section")
        # Same URL without fragment should match
        assert h.contains("https://example.com/page?a=1&b=2") is True

    def test_count(self) -> None:
        h = URLHistory()
        h.add("https://a.com")
        h.add("https://b.com")
        h.add("https://a.com")  # Duplicate
        assert h.count == 2

    def test_export_as_list(self) -> None:
        h = URLHistory()
        h.add("https://a.com")
        h.add("https://b.com")
        exported = h.to_list()
        assert isinstance(exported, list)
        assert len(exported) == 2
```

- [ ] **Step 2: Create budget_tracker.py**

```python
# apps/backend-rag/backend/services/naga/state/budget_tracker.py
"""Budget tracker for Naga research sessions.

Tracks search API calls, Gemini source consumption, and wall-clock TTL.
Prevents runaway research loops by enforcing hard limits.
"""

import logging
import time

logger = logging.getLogger(__name__)


class BudgetTracker:
    """Tracks resource consumption against tier limits.

    Attributes:
        max_searches: Maximum search API calls allowed.
        max_gemini_sources: Maximum sources to send to Gemini reader.
        ttl_seconds: Wall-clock deadline from creation time.
    """

    def __init__(
        self,
        max_searches: int,
        max_gemini_sources: int,
        ttl_seconds: int,
    ) -> None:
        self._max_searches = max_searches
        self._max_gemini_sources = max_gemini_sources
        self._ttl_seconds = ttl_seconds
        self._start_time = time.monotonic()
        self._searches_used = 0
        self._gemini_sources_used = 0

    @property
    def searches_remaining(self) -> int:
        return max(0, self._max_searches - self._searches_used)

    @property
    def gemini_sources_remaining(self) -> int:
        return max(0, self._max_gemini_sources - self._gemini_sources_used)

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self._start_time

    @property
    def is_expired(self) -> bool:
        return self.elapsed_seconds >= self._ttl_seconds

    @property
    def has_budget(self) -> bool:
        return self.searches_remaining > 0 and not self.is_expired

    def consume_search(self, count: int = 1) -> None:
        """Record search API call(s).

        Args:
            count: Number of calls to record.

        Raises:
            ValueError: If budget exhausted.
        """
        if self._searches_used + count > self._max_searches:
            raise ValueError(
                f"Search budget exhausted: {self._searches_used}/{self._max_searches} "
                f"used, requested {count} more"
            )
        self._searches_used += count
        logger.debug(
            "Budget: search %d/%d used",
            self._searches_used,
            self._max_searches,
        )

    def consume_gemini_sources(self, count: int = 1) -> None:
        """Record Gemini source slots consumed.

        Args:
            count: Number of sources to record.

        Raises:
            ValueError: If Gemini budget exhausted.
        """
        if self._gemini_sources_used + count > self._max_gemini_sources:
            raise ValueError(
                f"Gemini budget exhausted: {self._gemini_sources_used}/{self._max_gemini_sources}"
            )
        self._gemini_sources_used += count

    def summary(self) -> dict:
        """Return a serializable summary of budget state."""
        return {
            "searches_used": self._searches_used,
            "searches_remaining": self.searches_remaining,
            "gemini_sources_used": self._gemini_sources_used,
            "gemini_sources_remaining": self.gemini_sources_remaining,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "ttl_seconds": self._ttl_seconds,
            "is_expired": self.is_expired,
            "has_budget": self.has_budget,
        }
```

- [ ] **Step 3: Create url_history.py**

```python
# apps/backend-rag/backend/services/naga/state/url_history.py
"""Cross-iteration URL deduplication for Naga sessions.

Tracks URLs already fetched/processed to prevent redundant API calls
across research iterations.
"""

import logging
from urllib.parse import urldefrag, urlparse

logger = logging.getLogger(__name__)


class URLHistory:
    """Tracks seen URLs for deduplication across research iterations.

    URLs are normalized (fragment stripped) before comparison.
    """

    def __init__(self, initial: list[str] | None = None) -> None:
        self._seen: set[str] = set()
        if initial:
            for url in initial:
                self._seen.add(self._normalize(url))

    @staticmethod
    def _normalize(url: str) -> str:
        """Normalize URL by stripping fragment.

        Args:
            url: Raw URL.

        Returns:
            URL without fragment.
        """
        defragged, _ = urldefrag(url)
        return defragged

    def add(self, url: str) -> bool:
        """Add a URL. Returns True if new, False if already seen.

        Args:
            url: URL to add.

        Returns:
            True if this URL was not previously tracked.
        """
        normalized = self._normalize(url)
        if normalized in self._seen:
            return False
        self._seen.add(normalized)
        return True

    def contains(self, url: str) -> bool:
        """Check if a URL has been seen.

        Args:
            url: URL to check.

        Returns:
            True if previously tracked.
        """
        return self._normalize(url) in self._seen

    def dedup(self, urls: list[str]) -> list[str]:
        """Filter a list of URLs, returning only unseen ones.

        Does NOT add them to history — caller must explicitly add after processing.

        Args:
            urls: List of URLs to filter.

        Returns:
            List of URLs not previously seen.
        """
        return [u for u in urls if not self.contains(u)]

    @property
    def count(self) -> int:
        return len(self._seen)

    def to_list(self) -> list[str]:
        """Export as sorted list for DB persistence."""
        return sorted(self._seen)
```

- [ ] **Step 4: Create **init**.py**

```python
# apps/backend-rag/backend/services/naga/state/__init__.py
"""Naga session state: budget tracking and URL dedup."""

from backend.services.naga.state.budget_tracker import BudgetTracker
from backend.services.naga.state.url_history import URLHistory

__all__ = ["BudgetTracker", "URLHistory"]
```

- [ ] **Step 5: Run test**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/naga/test_state.py -v
# Expected: 13 passed
```

- [ ] **Step 6: Commit**

```bash
git add apps/backend-rag/backend/services/naga/state/ \
        apps/backend-rag/backend/tests/services/naga/test_state.py
git commit -m "feat(naga): add BudgetTracker + URLHistory state management"
```

---

### Task 5: Gateway Classifier

**Files:**

- Create: `apps/backend-rag/backend/services/naga/gateway.py`

- [ ] **Step 1: Write the test**

```python
# apps/backend-rag/backend/tests/services/naga/test_gateway.py
"""Tests for Naga Gateway classifier."""

import pytest

from backend.services.naga.gateway import (
    GatewayResult,
    classify_query,
    detect_domain,
    detect_tier,
)


class TestDetectDomain:
    """Test domain routing (indonesia/general/hybrid)."""

    def test_indonesia_visa_query(self) -> None:
        assert detect_domain("Apa persyaratan KITAS E23?") == "indonesia"

    def test_indonesia_kbli_query(self) -> None:
        assert detect_domain("KBLI code for restaurant in Bali") == "indonesia"

    def test_indonesia_tax_query(self) -> None:
        assert detect_domain("PPh 21 rates for PT PMA employees") == "indonesia"

    def test_general_tech_query(self) -> None:
        assert detect_domain("Compare React vs Vue for web apps") == "general"

    def test_hybrid_query(self) -> None:
        result = detect_domain("Compare golden visa Indonesia vs Portugal")
        assert result in ("hybrid", "indonesia")  # Both acceptable

    def test_default_is_general(self) -> None:
        assert detect_domain("What is quantum computing?") == "general"


class TestDetectTier:
    """Test tier classification (flash/deep/exhaustive)."""

    def test_simple_factual_is_flash(self) -> None:
        tier = detect_tier("What is the PNBP fee for KITAS?", channel="telegram")
        assert tier == "flash"

    def test_complex_research_is_deep(self) -> None:
        tier = detect_tier(
            "Analyze the impact of PP 28/2025 on foreign worker regulations "
            "and compare with previous PP 34/2021",
            channel="claude_code",
        )
        assert tier in ("deep", "exhaustive")

    def test_telegram_forces_flash(self) -> None:
        tier = detect_tier("Deep analysis of Indonesian tax reform", channel="telegram")
        assert tier == "flash"

    def test_api_allows_exhaustive(self) -> None:
        tier = detect_tier(
            "Comprehensive research on all visa categories for digital nomads "
            "in Southeast Asia with regulatory comparison across 5 countries",
            channel="api",
        )
        assert tier == "exhaustive"


class TestClassifyQuery:
    """Test full gateway classification."""

    def test_returns_gateway_result(self) -> None:
        result = classify_query("What is KITAS?", channel="web")
        assert isinstance(result, GatewayResult)
        assert result.tier in ("flash", "deep", "exhaustive")
        assert result.domain in ("indonesia", "general", "hybrid")
        assert result.mode in ("oneshot", "conversational")
        assert result.ttl_seconds > 0

    def test_flash_has_short_ttl(self) -> None:
        result = classify_query("KITAS fee?", channel="telegram")
        assert result.ttl_seconds <= 30

    def test_deep_has_medium_ttl(self) -> None:
        result = classify_query(
            "Analyze the regulatory impact of the new immigration law "
            "on foreign investment in Bali's property sector",
            channel="claude_code",
        )
        assert result.ttl_seconds >= 60
```

- [ ] **Step 2: Create gateway.py**

```python
# apps/backend-rag/backend/services/naga/gateway.py
"""Naga Gateway — query classification into tier/domain/mode/TTL.

This is a fast, deterministic classifier using keyword rules.
For v1 it is entirely rule-based. Future versions may use Haiku/Qwen
for ambiguous queries.

Architecture:
    Query → detect_domain() + detect_tier() + detect_mode() → GatewayResult
"""

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Domain detection keywords
_INDONESIA_KEYWORDS: list[str] = [
    "kitas", "kitap", "vitas", "visa", "rptka", "imta", "imigrasi", "immigration",
    "kbli", "oss", "nib", "pt pma", "pt lokal", "cv", "perorangan", "perseroan",
    "pph", "ppn", "npwp", "pajak", "tax indonesia", "fiscal indonesia",
    "bali", "jakarta", "indonesia", "denpasar", "badung",
    "hak pakai", "hgb", "hak milik", "shm", "notaris",
    "permen", "peraturan", "undang-undang", "pp ", "uu ",
    "golden visa", "second home", "digital nomad visa",
    "pergub", "perda", "gubernur", "kemenaker", "kemenkumham",
    "pnbp", "biaya", "tarif",
]

_ACADEMIC_SIGNALS: list[str] = [
    "research", "study", "paper", "journal", "meta-analysis",
    "systematic review", "literature", "citation",
]

# Tier detection signals
_COMPLEXITY_HIGH: list[str] = [
    "comprehensive", "analyze", "compare", "impact", "research",
    "all categories", "regulatory comparison", "multi-country",
    "history of", "evolution of", "deep dive",
]
_COMPLEXITY_MEDIUM: list[str] = [
    "explain", "overview", "summary", "how does", "what are the implications",
    "differences between", "pros and cons",
]

# Channel → max tier mapping
_CHANNEL_MAX_TIER: dict[str, str] = {
    "telegram": "flash",
    "web": "deep",
    "claude_code": "exhaustive",
    "openclaw": "exhaustive",
    "api": "exhaustive",
    "cron": "exhaustive",
}

# Channel → default TTL
_CHANNEL_TTL: dict[str, int] = {
    "telegram": 30,
    "web": 60,
    "claude_code": 1800,
    "openclaw": 1800,
    "api": 3600,
    "cron": 3600,
}

_TIER_ORDER = {"flash": 0, "deep": 1, "exhaustive": 2}


@dataclass(frozen=True)
class GatewayResult:
    """Output of the gateway classifier.

    Attributes:
        tier: Research depth (flash/deep/exhaustive).
        domain: indonesia/general/hybrid.
        mode: oneshot/conversational.
        ttl_seconds: Max wall-clock time for this research session.
    """

    tier: str
    domain: str
    mode: str
    ttl_seconds: int


def detect_domain(query: str) -> str:
    """Classify query domain.

    Args:
        query: User query text.

    Returns:
        'indonesia', 'general', or 'hybrid'.
    """
    query_lower = query.lower()
    indonesia_score = sum(1 for kw in _INDONESIA_KEYWORDS if kw in query_lower)

    # Check for explicit comparison signals (hybrid)
    has_comparison = bool(re.search(
        r"(?i)(compare|vs\.?|versus|confronto|rispetto a|dibanding)",
        query,
    ))
    has_non_indonesia = bool(re.search(
        r"(?i)(portugal|thailand|malaysia|singapore|europe|usa|global|worldwide)",
        query,
    ))

    if indonesia_score >= 1 and has_comparison and has_non_indonesia:
        return "hybrid"
    if indonesia_score >= 1:
        return "indonesia"
    return "general"


def detect_tier(query: str, channel: str = "api") -> str:
    """Classify research depth.

    Considers query complexity and channel constraints.

    Args:
        query: User query text.
        channel: Origin channel (telegram/web/claude_code/api/cron).

    Returns:
        'flash', 'deep', or 'exhaustive'.
    """
    query_lower = query.lower()
    max_tier = _CHANNEL_MAX_TIER.get(channel, "deep")
    max_tier_idx = _TIER_ORDER.get(max_tier, 1)

    # Score complexity
    high_signals = sum(1 for s in _COMPLEXITY_HIGH if s in query_lower)
    medium_signals = sum(1 for s in _COMPLEXITY_MEDIUM if s in query_lower)
    word_count = len(query.split())

    if high_signals >= 2 or word_count >= 30:
        desired = "exhaustive"
    elif high_signals >= 1 or medium_signals >= 2 or word_count >= 15:
        desired = "deep"
    else:
        desired = "flash"

    desired_idx = _TIER_ORDER.get(desired, 0)
    final_idx = min(desired_idx, max_tier_idx)

    tier_names = ["flash", "deep", "exhaustive"]
    return tier_names[final_idx]


def detect_mode(query: str) -> str:
    """Detect if query needs conversational (multi-turn) mode.

    Args:
        query: User query text.

    Returns:
        'oneshot' or 'conversational'.
    """
    # For v1, everything is oneshot. Conversational deferred to v1.1.
    return "oneshot"


def classify_query(
    query: str,
    channel: str = "api",
    tier_override: str | None = None,
    domain_override: str | None = None,
) -> GatewayResult:
    """Full gateway classification.

    Args:
        query: User query text.
        channel: Origin channel.
        tier_override: Force a specific tier (e.g., user typed /deep).
        domain_override: Force a specific domain.

    Returns:
        GatewayResult with tier, domain, mode, ttl_seconds.
    """
    domain = domain_override or detect_domain(query)
    tier = tier_override or detect_tier(query, channel)
    mode = detect_mode(query)
    ttl = _CHANNEL_TTL.get(channel, 60)

    # Override TTL for deep/exhaustive
    if tier == "deep" and ttl < 60:
        ttl = 300
    if tier == "exhaustive" and ttl < 300:
        ttl = 1800

    result = GatewayResult(tier=tier, domain=domain, mode=mode, ttl_seconds=ttl)
    logger.info(
        "Gateway: tier=%s domain=%s mode=%s ttl=%ds channel=%s query=%s",
        result.tier,
        result.domain,
        result.mode,
        result.ttl_seconds,
        channel,
        query[:80],
    )
    return result
```

- [ ] **Step 3: Run test**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/naga/test_gateway.py -v
# Expected: 11 passed
```

- [ ] **Step 4: Commit**

```bash
git add apps/backend-rag/backend/services/naga/gateway.py \
        apps/backend-rag/backend/tests/services/naga/test_gateway.py
git commit -m "feat(naga): add Gateway classifier (tier/domain/mode/TTL)"
```

---

## PHASE 2: Search Layer (Tasks 6-9)

### Task 6: BaseSearchAgent + SearchResult Types

**Files:**

- Create: `apps/backend-rag/backend/services/naga/search_agents/__init__.py`
- Create: `apps/backend-rag/backend/services/naga/search_agents/base.py`

- [ ] **Step 1: Write the test**

```python
# apps/backend-rag/backend/tests/services/naga/test_search_base.py
"""Tests for BaseSearchAgent and SearchResult types."""

from datetime import date, datetime, timezone

import pytest

from backend.services.naga.search_agents.base import (
    BaseSearchAgent,
    SearchResult,
)


class TestSearchResult:
    """Test SearchResult dataclass."""

    def test_create_minimal(self) -> None:
        sr = SearchResult(
            url="https://example.com",
            title="Example",
            content="Some content",
            source_type="web",
            agent_name="test_agent",
        )
        assert sr.url == "https://example.com"
        assert sr.relevance_score is None
        assert sr.freshness_date is None

    def test_create_full(self) -> None:
        sr = SearchResult(
            url="https://imigrasi.go.id/visa",
            title="Visa Info",
            content="Full content here",
            source_type="gov",
            agent_name="domain_agent",
            relevance_score=0.85,
            freshness_date=date(2026, 3, 15),
            domain="imigrasi.go.id",
            content_hash="abc123",
            metadata={"lang": "id"},
        )
        assert sr.source_type == "gov"
        assert sr.relevance_score == 0.85

    def test_to_dict(self) -> None:
        sr = SearchResult(
            url="https://a.com",
            title="A",
            content="text",
            source_type="web",
            agent_name="test",
        )
        d = sr.to_dict()
        assert "url" in d
        assert "agent_name" in d


class ConcreteAgent(BaseSearchAgent):
    """Concrete implementation for testing."""

    @property
    def name(self) -> str:
        return "test_agent"

    async def search(self, query: str, max_results: int = 10) -> list[SearchResult]:
        return [
            SearchResult(
                url="https://test.com",
                title="Test",
                content="Result",
                source_type="web",
                agent_name=self.name,
            )
        ]


class TestBaseSearchAgent:
    """Test BaseSearchAgent ABC contract."""

    def test_concrete_has_name(self) -> None:
        agent = ConcreteAgent()
        assert agent.name == "test_agent"

    @pytest.mark.asyncio
    async def test_concrete_search_returns_results(self) -> None:
        agent = ConcreteAgent()
        results = await agent.search("test query")
        assert len(results) == 1
        assert results[0].agent_name == "test_agent"

    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            BaseSearchAgent()  # type: ignore[abstract]
```

- [ ] **Step 2: Create base.py**

```python
# apps/backend-rag/backend/services/naga/search_agents/base.py
"""Base search agent protocol and result types for Naga.

All search agents inherit from BaseSearchAgent and return
SearchResult objects. The orchestrator dispatches to agents
in parallel and collects results.
"""

import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Single result from a search agent.

    Attributes:
        url: Source URL.
        title: Document title.
        content: Extracted content (markdown preferred).
        source_type: gov/academic/major_news/blog/forum/internal.
        agent_name: Which agent produced this result.
        relevance_score: 0.0-1.0 relevance (from search API or CRAG).
        freshness_date: Publication or last-updated date.
        domain: URL domain (e.g., 'imigrasi.go.id').
        content_hash: SHA256 of content for dedup.
        metadata: Agent-specific extra fields.
    """

    url: str
    title: str
    content: str
    source_type: str
    agent_name: str
    relevance_score: Optional[float] = None
    freshness_date: Optional[date] = None
    domain: Optional[str] = None
    content_hash: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Auto-compute domain and content_hash if not set."""
        if not self.domain and self.url:
            try:
                from urllib.parse import urlparse
                self.domain = urlparse(self.url).netloc
            except Exception:
                pass
        if not self.content_hash and self.content:
            self.content_hash = hashlib.sha256(
                self.content.encode("utf-8", errors="replace")
            ).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for JSON."""
        d = asdict(self)
        if d.get("freshness_date"):
            d["freshness_date"] = str(d["freshness_date"])
        return d


class BaseSearchAgent(ABC):
    """Abstract base for all Naga search agents.

    Subclasses must implement:
        name: Agent identifier string.
        search(): Execute search and return results.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique agent identifier (e.g., 'exa', 'brave', 'domain')."""
        ...

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[SearchResult]:
        """Execute a search query.

        Args:
            query: Search query text.
            max_results: Max results to return.

        Returns:
            List of SearchResult objects.
        """
        ...
```

- [ ] **Step 3: Create **init**.py**

```python
# apps/backend-rag/backend/services/naga/search_agents/__init__.py
"""Naga search agents — pluggable search providers."""

from backend.services.naga.search_agents.base import BaseSearchAgent, SearchResult

__all__ = ["BaseSearchAgent", "SearchResult"]
```

- [ ] **Step 4: Run test**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/naga/test_search_base.py -v
# Expected: 5 passed
```

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/services/naga/search_agents/ \
        apps/backend-rag/backend/tests/services/naga/test_search_base.py
git commit -m "feat(naga): add BaseSearchAgent ABC + SearchResult types"
```

---

### Task 7: Exa Neural Search Agent

**Files:**

- Create: `apps/backend-rag/backend/services/naga/search_agents/exa_agent.py`

- [ ] **Step 1: Write the test**

```python
# apps/backend-rag/backend/tests/services/naga/test_exa_agent.py
"""Tests for Exa Neural Search Agent."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.naga.search_agents.base import SearchResult
from backend.services.naga.search_agents.exa_agent import ExaSearchAgent


@pytest.fixture
def agent() -> ExaSearchAgent:
    return ExaSearchAgent(api_key="test-key")


class TestExaSearchAgent:
    """Test Exa agent logic."""

    def test_name(self, agent: ExaSearchAgent) -> None:
        assert agent.name == "exa"

    @pytest.mark.asyncio
    async def test_search_returns_results(self, agent: ExaSearchAgent) -> None:
        mock_response = {
            "results": [
                {
                    "url": "https://example.com/article",
                    "title": "Test Article",
                    "text": "Article content about KITAS requirements.",
                    "score": 0.85,
                    "publishedDate": "2026-03-15",
                },
                {
                    "url": "https://imigrasi.go.id/info",
                    "title": "Official Info",
                    "text": "Government source content.",
                    "score": 0.92,
                    "publishedDate": "2026-04-01",
                },
            ]
        }

        with patch.object(agent, "_call_exa", new_callable=AsyncMock, return_value=mock_response):
            results = await agent.search("KITAS requirements")

        assert len(results) == 2
        assert all(isinstance(r, SearchResult) for r in results)
        assert results[0].agent_name == "exa"
        assert results[1].domain == "imigrasi.go.id"

    @pytest.mark.asyncio
    async def test_search_with_domain_filter(self, agent: ExaSearchAgent) -> None:
        mock_response = {"results": []}

        with patch.object(agent, "_call_exa", new_callable=AsyncMock, return_value=mock_response) as mock_call:
            await agent.search("visa info", domain_filter=".go.id")
            call_kwargs = mock_call.call_args
            assert call_kwargs is not None

    @pytest.mark.asyncio
    async def test_search_handles_api_error(self, agent: ExaSearchAgent) -> None:
        with patch.object(
            agent,
            "_call_exa",
            new_callable=AsyncMock,
            side_effect=Exception("API Error"),
        ):
            results = await agent.search("test query")
            assert results == []

    @pytest.mark.asyncio
    async def test_search_empty_results(self, agent: ExaSearchAgent) -> None:
        mock_response = {"results": []}
        with patch.object(agent, "_call_exa", new_callable=AsyncMock, return_value=mock_response):
            results = await agent.search("obscure query")
            assert results == []
```

- [ ] **Step 2: Create exa_agent.py**

```python
# apps/backend-rag/backend/services/naga/search_agents/exa_agent.py
"""Exa Neural Search Agent for Naga.

Uses Exa's neural search API for semantic web search.
Supports domain filtering (e.g., .go.id for government sources).

API: https://docs.exa.ai
"""

import logging
import os
from datetime import date
from typing import Any, Optional

import httpx

from backend.services.naga.search_agents.base import BaseSearchAgent, SearchResult

logger = logging.getLogger(__name__)

EXA_API_URL = "https://api.exa.ai/search"


class ExaSearchAgent(BaseSearchAgent):
    """Exa neural search agent.

    Args:
        api_key: Exa API key. Falls back to EXA_API_KEY env var.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.getenv("EXA_API_KEY", "")

    @property
    def name(self) -> str:
        return "exa"

    async def search(
        self,
        query: str,
        max_results: int = 10,
        domain_filter: str | None = None,
    ) -> list[SearchResult]:
        """Execute Exa neural search.

        Args:
            query: Search query.
            max_results: Max results to return.
            domain_filter: Optional domain suffix filter (e.g., '.go.id').

        Returns:
            List of SearchResult.
        """
        try:
            payload: dict[str, Any] = {
                "query": query,
                "numResults": max_results,
                "type": "neural",
                "useAutoprompt": True,
                "contents": {"text": True},
            }
            if domain_filter:
                payload["includeDomains"] = [domain_filter]

            response = await self._call_exa(payload)
            results: list[SearchResult] = []

            for item in response.get("results", []):
                freshness = None
                pub_date = item.get("publishedDate", "")
                if pub_date:
                    try:
                        freshness = date.fromisoformat(pub_date[:10])
                    except ValueError:
                        pass

                url = item.get("url", "")
                domain = ""
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(url).netloc
                except Exception:
                    pass

                # Infer source type from domain
                source_type = "web"
                if domain.endswith(".go.id"):
                    source_type = "gov"
                elif domain.endswith(".edu") or domain.endswith(".ac.id"):
                    source_type = "academic"

                results.append(SearchResult(
                    url=url,
                    title=item.get("title", ""),
                    content=item.get("text", ""),
                    source_type=source_type,
                    agent_name=self.name,
                    relevance_score=item.get("score"),
                    freshness_date=freshness,
                    domain=domain,
                ))

            logger.info("Exa: %d results for '%s'", len(results), query[:60])
            return results

        except Exception as exc:
            logger.warning("Exa search failed: %s", exc)
            return []

    async def _call_exa(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Make authenticated call to Exa API.

        Args:
            payload: JSON request body.

        Returns:
            Parsed JSON response.
        """
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                EXA_API_URL,
                json=payload,
                headers={
                    "x-api-key": self._api_key,
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            return resp.json()
```

- [ ] **Step 3: Run test**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/naga/test_exa_agent.py -v
# Expected: 5 passed
```

- [ ] **Step 4: Commit**

```bash
git add apps/backend-rag/backend/services/naga/search_agents/exa_agent.py \
        apps/backend-rag/backend/tests/services/naga/test_exa_agent.py
git commit -m "feat(naga): add Exa neural search agent"
```

---

### Task 8: Brave Web Search Agent

**Files:**

- Create: `apps/backend-rag/backend/services/naga/search_agents/brave_agent.py`

- [ ] **Step 1: Write the test**

```python
# apps/backend-rag/backend/tests/services/naga/test_brave_agent.py
"""Tests for Brave Web Search Agent."""

from unittest.mock import AsyncMock, patch

import pytest

from backend.services.naga.search_agents.base import SearchResult
from backend.services.naga.search_agents.brave_agent import BraveSearchAgent


@pytest.fixture
def agent() -> BraveSearchAgent:
    return BraveSearchAgent(api_key="test-key")


class TestBraveSearchAgent:
    """Test Brave agent."""

    def test_name(self, agent: BraveSearchAgent) -> None:
        assert agent.name == "brave"

    @pytest.mark.asyncio
    async def test_search_returns_results(self, agent: BraveSearchAgent) -> None:
        mock_response = {
            "web": {
                "results": [
                    {
                        "url": "https://thejakartapost.com/article",
                        "title": "Jakarta Post Article",
                        "description": "Article about visa changes.",
                        "page_age": "2026-03-20",
                    },
                ]
            }
        }

        with patch.object(agent, "_call_brave", new_callable=AsyncMock, return_value=mock_response):
            results = await agent.search("visa changes Indonesia")

        assert len(results) == 1
        assert results[0].agent_name == "brave"
        assert results[0].source_type == "major_news"

    @pytest.mark.asyncio
    async def test_search_handles_empty(self, agent: BraveSearchAgent) -> None:
        mock_response = {"web": {"results": []}}
        with patch.object(agent, "_call_brave", new_callable=AsyncMock, return_value=mock_response):
            results = await agent.search("nonexistent topic")
            assert results == []

    @pytest.mark.asyncio
    async def test_search_handles_error(self, agent: BraveSearchAgent) -> None:
        with patch.object(
            agent, "_call_brave", new_callable=AsyncMock, side_effect=Exception("timeout")
        ):
            results = await agent.search("query")
            assert results == []
```

- [ ] **Step 2: Create brave_agent.py**

```python
# apps/backend-rag/backend/services/naga/search_agents/brave_agent.py
"""Brave Web Search Agent for Naga.

Uses Brave Search API as an independent web index diversifier.
Returns titles + descriptions; full content fetch handled separately
by the Gemini reader step.

API: https://brave.com/search/api/
"""

import logging
import os
from datetime import date
from typing import Any

import httpx

from backend.services.naga.search_agents.base import BaseSearchAgent, SearchResult

logger = logging.getLogger(__name__)

BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"

# Known major news domains for source_type classification
_MAJOR_NEWS_DOMAINS: set[str] = {
    "reuters.com", "thejakartapost.com", "kompas.com", "tempo.co",
    "cnnindonesia.com", "bbc.com", "bloomberg.com", "nikkei.com",
    "ft.com", "scmp.com",
}


class BraveSearchAgent(BaseSearchAgent):
    """Brave web search agent.

    Args:
        api_key: Brave Search API key. Falls back to BRAVE_API_KEY env var.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.getenv("BRAVE_API_KEY", "")

    @property
    def name(self) -> str:
        return "brave"

    async def search(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[SearchResult]:
        """Execute Brave web search.

        Args:
            query: Search query.
            max_results: Max results to return.

        Returns:
            List of SearchResult.
        """
        try:
            response = await self._call_brave(query, max_results)
            web_results = response.get("web", {}).get("results", [])
            results: list[SearchResult] = []

            for item in web_results:
                url = item.get("url", "")
                domain = ""
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(url).netloc.lstrip("www.")
                except Exception:
                    pass

                # Classify source type
                source_type = "web"
                if domain.endswith(".go.id"):
                    source_type = "gov"
                elif domain in _MAJOR_NEWS_DOMAINS:
                    source_type = "major_news"
                elif domain.endswith(".edu") or domain.endswith(".ac.id"):
                    source_type = "academic"

                freshness = None
                page_age = item.get("page_age", "")
                if page_age:
                    try:
                        freshness = date.fromisoformat(page_age[:10])
                    except ValueError:
                        pass

                results.append(SearchResult(
                    url=url,
                    title=item.get("title", ""),
                    content=item.get("description", ""),
                    source_type=source_type,
                    agent_name=self.name,
                    freshness_date=freshness,
                    domain=domain,
                ))

            logger.info("Brave: %d results for '%s'", len(results), query[:60])
            return results

        except Exception as exc:
            logger.warning("Brave search failed: %s", exc)
            return []

    async def _call_brave(self, query: str, count: int) -> dict[str, Any]:
        """Make authenticated call to Brave Search API.

        Args:
            query: Search query.
            count: Number of results.

        Returns:
            Parsed JSON response.
        """
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                BRAVE_API_URL,
                params={"q": query, "count": min(count, 20)},
                headers={
                    "X-Subscription-Token": self._api_key,
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            return resp.json()
```

- [ ] **Step 3: Run test**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/naga/test_brave_agent.py -v
# Expected: 4 passed
```

- [ ] **Step 4: Commit**

```bash
git add apps/backend-rag/backend/services/naga/search_agents/brave_agent.py \
        apps/backend-rag/backend/tests/services/naga/test_brave_agent.py
git commit -m "feat(naga): add Brave web search agent"
```

---

### Task 9: Indonesia Domain Agent

Uses existing backend MCP tools via internal HTTP calls (ask_legal, search_intel, recall_similar) plus Exa with `.go.id` domain filter. Academic Agent deferred to v1.1.

**Files:**

- Create: `apps/backend-rag/backend/services/naga/search_agents/domain_agent.py`

- [ ] **Step 1: Write the test**

```python
# apps/backend-rag/backend/tests/services/naga/test_domain_agent.py
"""Tests for Indonesia Domain Search Agent."""

from unittest.mock import AsyncMock, patch

import pytest

from backend.services.naga.search_agents.base import SearchResult
from backend.services.naga.search_agents.domain_agent import IndonesiaDomainAgent


@pytest.fixture
def agent() -> IndonesiaDomainAgent:
    return IndonesiaDomainAgent(backend_url="http://localhost:8000")


class TestIndonesiaDomainAgent:
    """Test Indonesia domain agent."""

    def test_name(self, agent: IndonesiaDomainAgent) -> None:
        assert agent.name == "indonesia_domain"

    @pytest.mark.asyncio
    async def test_ask_legal_produces_results(self, agent: IndonesiaDomainAgent) -> None:
        mock_response = {
            "answer": "KITAS E23 requires RPTKA approval from Kemnaker.",
            "sources": [
                {"title": "UU 6/2011", "url": "internal://legal/uu-6-2011"},
            ],
        }
        with patch.object(
            agent, "_call_backend", new_callable=AsyncMock, return_value=mock_response
        ):
            results = await agent._search_ask_legal("KITAS E23 requirements")

        assert len(results) >= 1
        assert results[0].source_type == "internal"
        assert results[0].agent_name == "indonesia_domain"

    @pytest.mark.asyncio
    async def test_search_intel_produces_results(self, agent: IndonesiaDomainAgent) -> None:
        mock_response = {
            "results": [
                {
                    "title": "New immigration regulation",
                    "url": "https://imigrasi.go.id/news/123",
                    "snippet": "Regulation content",
                },
            ],
        }
        with patch.object(
            agent, "_call_backend", new_callable=AsyncMock, return_value=mock_response
        ):
            results = await agent._search_intel("immigration regulation")

        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_search_combines_all_sources(self, agent: IndonesiaDomainAgent) -> None:
        with patch.object(
            agent, "_search_ask_legal", new_callable=AsyncMock, return_value=[
                SearchResult(url="internal://1", title="Legal", content="text",
                           source_type="internal", agent_name="indonesia_domain"),
            ]
        ), patch.object(
            agent, "_search_intel", new_callable=AsyncMock, return_value=[
                SearchResult(url="https://news.com", title="News", content="text",
                           source_type="major_news", agent_name="indonesia_domain"),
            ]
        ), patch.object(
            agent, "_search_recall", new_callable=AsyncMock, return_value=[]
        ), patch.object(
            agent, "_search_exa_gov", new_callable=AsyncMock, return_value=[]
        ):
            results = await agent.search("KITAS requirements")

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_handles_partial_failures(self, agent: IndonesiaDomainAgent) -> None:
        with patch.object(
            agent, "_search_ask_legal", new_callable=AsyncMock,
            side_effect=Exception("backend down"),
        ), patch.object(
            agent, "_search_intel", new_callable=AsyncMock, return_value=[
                SearchResult(url="https://a.com", title="A", content="text",
                           source_type="web", agent_name="indonesia_domain"),
            ]
        ), patch.object(
            agent, "_search_recall", new_callable=AsyncMock, return_value=[]
        ), patch.object(
            agent, "_search_exa_gov", new_callable=AsyncMock, return_value=[]
        ):
            results = await agent.search("visa info")

        assert len(results) == 1  # Intel result survived
```

- [ ] **Step 2: Create domain_agent.py**

```python
# apps/backend-rag/backend/services/naga/search_agents/domain_agent.py
"""Indonesia Domain Search Agent for Naga.

Combines multiple internal sources:
  1. ask_legal — normativa/visa/tax from RAG
  2. search_intel — recent regulatory news
  3. recall_similar — validated past episodes
  4. Exa with .go.id domain filter — official government sources

All backend calls use HTTP via httpx (never direct imports).
"""

import asyncio
import logging
import os
from typing import Any

import httpx

from backend.services.naga.search_agents.base import BaseSearchAgent, SearchResult
from backend.services.naga.search_agents.exa_agent import ExaSearchAgent

logger = logging.getLogger(__name__)


class IndonesiaDomainAgent(BaseSearchAgent):
    """Indonesia-specialized multi-source agent.

    Args:
        backend_url: Base URL for backend API.
        api_key: Backend API key.
        exa_api_key: Exa API key for .go.id filtered search.
    """

    def __init__(
        self,
        backend_url: str | None = None,
        api_key: str | None = None,
        exa_api_key: str | None = None,
    ) -> None:
        self._backend_url = backend_url or os.getenv(
            "NUZANTARA_BACKEND_URL", "https://nuzantara-rag.fly.dev"
        )
        self._api_key = api_key or os.getenv("NUZANTARA_API_KEY", "")
        self._exa = ExaSearchAgent(api_key=exa_api_key)

    @property
    def name(self) -> str:
        return "indonesia_domain"

    async def search(
        self,
        query: str,
        max_results: int = 10,
    ) -> list[SearchResult]:
        """Search across all Indonesia domain sources in parallel.

        Combines ask_legal, search_intel, recall_similar, and Exa .go.id.
        Failures in individual sources are logged but do not halt the search.

        Args:
            query: Search query.
            max_results: Max results per sub-source.

        Returns:
            Combined list of SearchResult from all sources.
        """
        tasks = [
            self._safe_search(self._search_ask_legal, query),
            self._safe_search(self._search_intel, query),
            self._safe_search(self._search_recall, query),
            self._safe_search(self._search_exa_gov, query, max_results=5),
        ]
        results_lists = await asyncio.gather(*tasks)
        combined: list[SearchResult] = []
        for results in results_lists:
            combined.extend(results)

        logger.info(
            "IndonesiaDomain: %d total results from %d sources for '%s'",
            len(combined),
            sum(1 for r in results_lists if r),
            query[:60],
        )
        return combined

    async def _safe_search(self, fn: Any, *args: Any, **kwargs: Any) -> list[SearchResult]:
        """Execute a sub-search, returning empty list on failure."""
        try:
            return await fn(*args, **kwargs)
        except Exception as exc:
            logger.warning("IndonesiaDomain sub-search %s failed: %s", fn.__name__, exc)
            return []

    async def _search_ask_legal(self, query: str) -> list[SearchResult]:
        """Query ask_legal endpoint for normative/visa/tax content."""
        response = await self._call_backend(
            "/api/legal/ask", method="POST", json={"query": query, "limit": 5}
        )
        results: list[SearchResult] = []
        answer = response.get("answer", "")
        if answer:
            results.append(SearchResult(
                url=f"internal://ask_legal/{hash(query) & 0xFFFFFFFF:08x}",
                title=f"Legal RAG: {query[:60]}",
                content=answer,
                source_type="internal",
                agent_name=self.name,
                relevance_score=0.80,
            ))
        for src in response.get("sources", []):
            results.append(SearchResult(
                url=src.get("url", f"internal://legal/{src.get('title', '')}"),
                title=src.get("title", ""),
                content=src.get("snippet", src.get("content", "")),
                source_type="internal",
                agent_name=self.name,
            ))
        return results

    async def _search_intel(self, query: str) -> list[SearchResult]:
        """Query search_intel endpoint for recent regulatory news."""
        response = await self._call_backend(
            "/api/intel/search", params={"q": query, "limit": 5}
        )
        results: list[SearchResult] = []
        for item in response.get("results", []):
            results.append(SearchResult(
                url=item.get("url", ""),
                title=item.get("title", ""),
                content=item.get("snippet", item.get("content", "")),
                source_type="major_news",
                agent_name=self.name,
            ))
        return results

    async def _search_recall(self, query: str) -> list[SearchResult]:
        """Query recall_similar for validated past episodes."""
        response = await self._call_backend(
            "/api/memory/recall-similar",
            method="POST",
            json={"query": query, "limit": 3},
        )
        results: list[SearchResult] = []
        for ep in response.get("episodes", response.get("results", [])):
            results.append(SearchResult(
                url=f"internal://episode/{ep.get('id', '')}",
                title=ep.get("title", ep.get("summary", "")[:80]),
                content=ep.get("content", ep.get("summary", "")),
                source_type="internal",
                agent_name=self.name,
                relevance_score=ep.get("score"),
            ))
        return results

    async def _search_exa_gov(self, query: str, max_results: int = 5) -> list[SearchResult]:
        """Search Exa with .go.id domain filter for official gov sources."""
        results = await self._exa.search(
            query=query,
            max_results=max_results,
            domain_filter=".go.id",
        )
        # Re-tag agent_name
        for r in results:
            r.metadata["original_agent"] = r.agent_name
            # Keep agent_name as indonesia_domain for unified tracking
            object.__setattr__(r, "agent_name", self.name) if hasattr(r, "__dataclass_fields__") else None
        return results

    async def _call_backend(
        self,
        endpoint: str,
        method: str = "GET",
        json: dict | None = None,
        params: dict | None = None,
    ) -> dict[str, Any]:
        """Authenticated HTTP call to backend.

        Args:
            endpoint: API path (e.g., '/api/legal/ask').
            method: HTTP method.
            json: JSON body.
            params: Query params.

        Returns:
            Parsed JSON response.
        """
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
            headers["X-API-Key"] = self._api_key

        async with httpx.AsyncClient(
            base_url=self._backend_url, timeout=30
        ) as client:
            resp = await client.request(
                method=method,
                url=endpoint,
                json=json,
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()
```

- [ ] **Step 3: Run test**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/naga/test_domain_agent.py -v
# Expected: 5 passed
```

- [ ] **Step 4: Commit**

```bash
git add apps/backend-rag/backend/services/naga/search_agents/domain_agent.py \
        apps/backend-rag/backend/tests/services/naga/test_domain_agent.py
git commit -m "feat(naga): add Indonesia Domain search agent (ask_legal + intel + .go.id)"
```

> **NOTE:** Academic Agent deferred to v1.1. The 4 agents in v1.0 are: Exa, Brave, Indonesia Domain, and (placeholder) Academic which is not dispatched. This reduces scope for first ship.

---

## PHASE 3: Quality + Synthesis (Tasks 10-14)

### Task 10: Source Scorer

**Files:**

- Create: `apps/backend-rag/backend/services/naga/quality/__init__.py`
- Create: `apps/backend-rag/backend/services/naga/quality/source_scorer.py`

- [ ] **Step 1: Write the test**

```python
# apps/backend-rag/backend/tests/services/naga/test_source_scorer.py
"""Tests for Source Scorer."""

from datetime import date

import pytest

from backend.services.naga.quality.source_scorer import SourceScorer, ScoredSource
from backend.services.naga.search_agents.base import SearchResult
from backend.services.naga.config.naga_config import NagaConfig


@pytest.fixture
def scorer() -> SourceScorer:
    return SourceScorer(config=NagaConfig())


class TestSourceScorer:
    """Test source credibility + freshness scoring."""

    def test_gov_source_scores_high(self, scorer: SourceScorer) -> None:
        result = SearchResult(
            url="https://imigrasi.go.id/visa",
            title="Official Visa Info",
            content="Content",
            source_type="gov",
            agent_name="exa",
            freshness_date=date(2026, 3, 15),
            domain="imigrasi.go.id",
        )
        scored = scorer.score(result)
        assert scored.final_score >= 0.7

    def test_forum_source_scores_low(self, scorer: SourceScorer) -> None:
        result = SearchResult(
            url="https://kaskus.co.id/thread/123",
            title="Forum Post",
            content="Content",
            source_type="forum",
            agent_name="brave",
            freshness_date=date(2024, 1, 1),
            domain="kaskus.co.id",
        )
        scored = scorer.score(result)
        assert scored.final_score < 0.4

    def test_fresh_content_beats_stale(self, scorer: SourceScorer) -> None:
        fresh = SearchResult(
            url="https://a.com", title="A", content="text",
            source_type="web", agent_name="brave",
            freshness_date=date(2026, 3, 30), domain="a.com",
        )
        stale = SearchResult(
            url="https://b.com", title="B", content="text",
            source_type="web", agent_name="brave",
            freshness_date=date(2022, 1, 1), domain="b.com",
        )
        assert scorer.score(fresh).freshness_score > scorer.score(stale).freshness_score

    def test_filter_below_threshold(self, scorer: SourceScorer) -> None:
        results = [
            SearchResult(url="https://imigrasi.go.id", title="Gov", content="text",
                        source_type="gov", agent_name="exa",
                        freshness_date=date(2026, 3, 1), domain="imigrasi.go.id"),
            SearchResult(url="https://random-forum.com", title="Forum", content="text",
                        source_type="forum", agent_name="brave",
                        freshness_date=date(2020, 1, 1), domain="random-forum.com"),
        ]
        scored = scorer.score_and_filter(results)
        # Gov source should survive, forum might be filtered
        assert any(s.source.domain == "imigrasi.go.id" for s in scored)

    def test_score_returns_all_components(self, scorer: SourceScorer) -> None:
        result = SearchResult(
            url="https://a.com", title="A", content="text",
            source_type="web", agent_name="brave", domain="a.com",
        )
        scored = scorer.score(result)
        assert 0.0 <= scored.credibility_score <= 1.0
        assert 0.0 <= scored.freshness_score <= 1.0
        assert 0.0 <= scored.final_score <= 1.0
```

- [ ] **Step 2: Create source_scorer.py**

```python
# apps/backend-rag/backend/services/naga/quality/source_scorer.py
"""Source scoring for Naga quality pipeline.

Combines domain credibility (from source_weights.json) with temporal
freshness to produce a composite source score. Sources below threshold
are filtered out before further processing.
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from backend.services.naga.config.naga_config import NagaConfig
from backend.services.naga.search_agents.base import SearchResult

logger = logging.getLogger(__name__)


@dataclass
class ScoredSource:
    """A search result enriched with quality scores.

    Attributes:
        source: Original SearchResult.
        credibility_score: Domain credibility 0.0-1.0.
        freshness_score: Temporal freshness 0.0-1.0.
        relevance_score: From search API (pass-through).
        final_score: Weighted combination.
    """

    source: SearchResult
    credibility_score: float
    freshness_score: float
    relevance_score: float
    final_score: float


class SourceScorer:
    """Scores sources by credibility and freshness.

    Args:
        config: NagaConfig with source weights and thresholds.
    """

    # Weight distribution for final score
    W_CREDIBILITY: float = 0.45
    W_FRESHNESS: float = 0.30
    W_RELEVANCE: float = 0.25

    def __init__(self, config: NagaConfig) -> None:
        self._config = config

    def score(self, result: SearchResult) -> ScoredSource:
        """Score a single SearchResult.

        Args:
            result: SearchResult to score.

        Returns:
            ScoredSource with component scores.
        """
        credibility = self._compute_credibility(result)
        freshness = self._compute_freshness(result.freshness_date)
        relevance = result.relevance_score if result.relevance_score is not None else 0.5

        final = (
            self.W_CREDIBILITY * credibility
            + self.W_FRESHNESS * freshness
            + self.W_RELEVANCE * relevance
        )

        return ScoredSource(
            source=result,
            credibility_score=round(credibility, 3),
            freshness_score=round(freshness, 3),
            relevance_score=round(relevance, 3),
            final_score=round(final, 3),
        )

    def score_and_filter(
        self,
        results: list[SearchResult],
        min_score: float | None = None,
    ) -> list[ScoredSource]:
        """Score all results and filter below threshold.

        Args:
            results: List of SearchResult.
            min_score: Override minimum score. Defaults to config.source_score_min.

        Returns:
            Sorted (descending) list of ScoredSource above threshold.
        """
        threshold = min_score if min_score is not None else self._config.source_score_min
        scored = [self.score(r) for r in results]
        filtered = [s for s in scored if s.final_score >= threshold]
        filtered.sort(key=lambda s: s.final_score, reverse=True)

        logger.info(
            "SourceScorer: %d/%d sources above threshold %.2f",
            len(filtered),
            len(scored),
            threshold,
        )
        return filtered

    def _compute_credibility(self, result: SearchResult) -> float:
        """Look up domain credibility from config weights."""
        domain = result.domain or ""
        source_type = result.source_type or "web"
        return self._config.get_source_weight(domain, source_type)

    @staticmethod
    def _compute_freshness(pub_date: Optional[date]) -> float:
        """Score freshness based on publication date."""
        if pub_date is None:
            return 0.5  # Unknown = moderate
        today = date.today()
        age_days = (today - pub_date).days
        if age_days <= 30:
            return 1.0
        elif age_days <= 365:
            return 0.7
        elif age_days <= 1095:
            return 0.5
        return 0.3
```

- [ ] **Step 3: Create **init**.py**

```python
# apps/backend-rag/backend/services/naga/quality/__init__.py
"""Naga quality pipeline: scoring, CRAG, convergence."""
```

- [ ] **Step 4: Run test**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/naga/test_source_scorer.py -v
# Expected: 5 passed
```

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/services/naga/quality/ \
        apps/backend-rag/backend/tests/services/naga/test_source_scorer.py
git commit -m "feat(naga): add Source Scorer with configurable domain weights"
```

---

### Task 11: CRAG-Light Fast Relevance Gate

**Files:**

- Create: `apps/backend-rag/backend/services/naga/quality/crag_light.py`

- [ ] **Step 1: Write the test**

```python
# apps/backend-rag/backend/tests/services/naga/test_crag_light.py
"""Tests for CRAG-Light fast relevance gate."""

from unittest.mock import AsyncMock, patch

import pytest

from backend.services.naga.quality.crag_light import CRAGLight, RelevanceVerdict
from backend.services.naga.quality.source_scorer import ScoredSource
from backend.services.naga.search_agents.base import SearchResult


def _make_scored(content: str, score: float = 0.6) -> ScoredSource:
    sr = SearchResult(
        url="https://test.com",
        title="Test",
        content=content,
        source_type="web",
        agent_name="test",
    )
    return ScoredSource(
        source=sr,
        credibility_score=0.5,
        freshness_score=0.5,
        relevance_score=0.5,
        final_score=score,
    )


class TestCRAGLight:
    """Test fast relevance filtering."""

    @pytest.mark.asyncio
    async def test_relevant_passes(self) -> None:
        gate = CRAGLight()
        mock_result = RelevanceVerdict(relevant=True, confidence=0.9)
        with patch.object(gate, "_check_relevance", new_callable=AsyncMock, return_value=mock_result):
            source = _make_scored("KITAS E23 requires RPTKA.")
            result = await gate.check(source, query="KITAS requirements")
            assert result.relevant is True

    @pytest.mark.asyncio
    async def test_irrelevant_filtered(self) -> None:
        gate = CRAGLight()
        mock_result = RelevanceVerdict(relevant=False, confidence=0.8)
        with patch.object(gate, "_check_relevance", new_callable=AsyncMock, return_value=mock_result):
            source = _make_scored("Completely unrelated content about cooking.")
            result = await gate.check(source, query="KITAS requirements")
            assert result.relevant is False

    @pytest.mark.asyncio
    async def test_batch_filter(self) -> None:
        gate = CRAGLight()
        sources = [
            _make_scored("Relevant content about visa.", 0.8),
            _make_scored("Irrelevant content about food.", 0.3),
        ]
        verdicts = [
            RelevanceVerdict(relevant=True, confidence=0.9),
            RelevanceVerdict(relevant=False, confidence=0.7),
        ]
        with patch.object(gate, "_check_relevance", new_callable=AsyncMock, side_effect=verdicts):
            filtered = await gate.filter_batch(sources, query="visa requirements")
            assert len(filtered) == 1

    @pytest.mark.asyncio
    async def test_fallback_on_error(self) -> None:
        gate = CRAGLight()
        with patch.object(
            gate, "_check_relevance",
            new_callable=AsyncMock,
            side_effect=Exception("LLM down"),
        ):
            source = _make_scored("Content", 0.7)
            result = await gate.check(source, query="test")
            # On error, should default to allowing high-scored sources
            assert result.relevant is True
```

- [ ] **Step 2: Create crag_light.py**

```python
# apps/backend-rag/backend/services/naga/quality/crag_light.py
"""CRAG-Light: fast relevance gate using Haiku.

Corrective RAG (CRAG) light implementation. For each source,
asks a fast LLM whether the content is relevant to the query.
Irrelevant sources are discarded before expensive Gemini bulk read.

For v1, uses a keyword/heuristic fallback when LLM is unavailable.
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Optional

import httpx

from backend.services.naga.quality.source_scorer import ScoredSource

logger = logging.getLogger(__name__)


@dataclass
class RelevanceVerdict:
    """Result of a relevance check.

    Attributes:
        relevant: Whether the source is relevant.
        confidence: Confidence in the verdict 0.0-1.0.
    """

    relevant: bool
    confidence: float


class CRAGLight:
    """Fast relevance gate using Haiku or keyword heuristics.

    Falls back to heuristic scoring if LLM is unavailable.
    """

    def __init__(self) -> None:
        self._anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")

    async def check(
        self,
        source: ScoredSource,
        query: str,
    ) -> RelevanceVerdict:
        """Check if a single source is relevant to the query.

        Args:
            source: ScoredSource to evaluate.
            query: Original research query.

        Returns:
            RelevanceVerdict with decision and confidence.
        """
        try:
            return await self._check_relevance(source, query)
        except Exception as exc:
            logger.warning("CRAG check failed, using fallback: %s", exc)
            # Fallback: trust source scorer — high-scored sources pass
            return RelevanceVerdict(
                relevant=source.final_score >= 0.4,
                confidence=0.5,
            )

    async def filter_batch(
        self,
        sources: list[ScoredSource],
        query: str,
    ) -> list[ScoredSource]:
        """Filter a batch of sources for relevance.

        Args:
            sources: List of ScoredSource to evaluate.
            query: Original research query.

        Returns:
            Only relevant sources.
        """
        tasks = [self.check(s, query) for s in sources]
        verdicts = await asyncio.gather(*tasks)
        filtered = [s for s, v in zip(sources, verdicts) if v.relevant]
        logger.info(
            "CRAG: %d/%d sources passed relevance gate for '%s'",
            len(filtered),
            len(sources),
            query[:60],
        )
        return filtered

    async def _check_relevance(
        self,
        source: ScoredSource,
        query: str,
    ) -> RelevanceVerdict:
        """Call Haiku for relevance check. Override in tests.

        Args:
            source: Source to check.
            query: Research query.

        Returns:
            RelevanceVerdict.
        """
        if not self._anthropic_key:
            return self._heuristic_check(source, query)

        content_snippet = source.source.content[:1000]
        prompt = (
            f"Is the following content relevant to answering this research query?\n\n"
            f"Query: {query}\n\n"
            f"Content: {content_snippet}\n\n"
            f"Reply with ONLY 'relevant' or 'irrelevant' followed by confidence 0.0-1.0.\n"
            f"Example: relevant 0.85"
        )

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 20,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            text = resp.json()["content"][0]["text"].strip().lower()

        # Parse response
        parts = text.split()
        is_relevant = parts[0] == "relevant" if parts else True
        confidence = float(parts[1]) if len(parts) > 1 else 0.5
        return RelevanceVerdict(relevant=is_relevant, confidence=confidence)

    @staticmethod
    def _heuristic_check(source: ScoredSource, query: str) -> RelevanceVerdict:
        """Fallback keyword overlap check when LLM unavailable."""
        query_words = set(query.lower().split())
        content_words = set(source.source.content.lower().split()[:200])
        overlap = len(query_words & content_words)
        ratio = overlap / max(len(query_words), 1)
        return RelevanceVerdict(
            relevant=ratio > 0.15 or source.final_score > 0.5,
            confidence=min(1.0, ratio + 0.3),
        )
```

- [ ] **Step 3: Run test**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/naga/test_crag_light.py -v
# Expected: 4 passed
```

- [ ] **Step 4: Commit**

```bash
git add apps/backend-rag/backend/services/naga/quality/crag_light.py \
        apps/backend-rag/backend/tests/services/naga/test_crag_light.py
git commit -m "feat(naga): add CRAG-Light fast relevance gate"
```

---

### Task 12: Gemini Bulk Reader (Pointer State Pattern)

**Files:**

- Create: `apps/backend-rag/backend/services/naga/readers/__init__.py`
- Create: `apps/backend-rag/backend/services/naga/readers/gemini_reader.py`

- [ ] **Step 1: Write the test**

```python
# apps/backend-rag/backend/tests/services/naga/test_gemini_reader.py
"""Tests for Gemini Bulk Reader with Pointer State Pattern."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.naga.readers.gemini_reader import GeminiBulkReader
from backend.services.naga.quality.source_scorer import ScoredSource
from backend.services.naga.search_agents.base import SearchResult


def _make_scored(url: str, content: str) -> ScoredSource:
    sr = SearchResult(url=url, title="Test", content=content,
                     source_type="web", agent_name="test")
    return ScoredSource(source=sr, credibility_score=0.7,
                       freshness_score=0.8, relevance_score=0.7, final_score=0.7)


class TestGeminiBulkReader:
    """Test bulk read + evidence map generation."""

    @pytest.mark.asyncio
    async def test_read_produces_evidence_map(self) -> None:
        reader = GeminiBulkReader()
        sources = [
            _make_scored("https://a.com", "KITAS E23 requires RPTKA approval."),
            _make_scored("https://b.com", "The RPTKA fee is Rp 100 per position."),
        ]
        sub_questions = ["What are KITAS E23 requirements?", "What are the fees?"]

        mock_evidence = {
            "facts": [
                {"sub_question": sub_questions[0], "fact": "KITAS E23 requires RPTKA",
                 "source_ids": ["https://a.com"], "confidence": 0.85},
            ],
            "contradictions": [],
            "gaps": ["Processing time not covered"],
            "data_points": [{"value": "Rp 100", "context": "RPTKA fee"}],
        }

        with tempfile.TemporaryDirectory() as tmpdir, \
             patch.object(reader, "_call_gemini", new_callable=AsyncMock, return_value=mock_evidence):
            uri = await reader.read_and_save(
                sources=sources,
                sub_questions=sub_questions,
                session_id="test-session",
                evidence_dir=tmpdir,
            )
            assert uri.startswith(tmpdir)
            assert Path(uri).exists()
            data = json.loads(Path(uri).read_text())
            assert "facts" in data
            assert len(data["facts"]) >= 1

    @pytest.mark.asyncio
    async def test_pointer_state_only_uri(self) -> None:
        """Evidence map saved to file, only URI returned (Pointer State)."""
        reader = GeminiBulkReader()
        with tempfile.TemporaryDirectory() as tmpdir, \
             patch.object(reader, "_call_gemini", new_callable=AsyncMock,
                         return_value={"facts": [], "contradictions": [], "gaps": [], "data_points": []}):
            uri = await reader.read_and_save(
                sources=[],
                sub_questions=["test?"],
                session_id="s1",
                evidence_dir=tmpdir,
            )
            # URI is a string path, not the data itself
            assert isinstance(uri, str)
            assert "evidence" in uri

    @pytest.mark.asyncio
    async def test_handles_gemini_error(self) -> None:
        reader = GeminiBulkReader()
        with tempfile.TemporaryDirectory() as tmpdir, \
             patch.object(reader, "_call_gemini", new_callable=AsyncMock,
                         side_effect=Exception("Gemini quota exceeded")):
            uri = await reader.read_and_save(
                sources=[_make_scored("https://a.com", "content")],
                sub_questions=["test?"],
                session_id="s2",
                evidence_dir=tmpdir,
            )
            # Should still write a partial/empty evidence map
            assert Path(uri).exists()
            data = json.loads(Path(uri).read_text())
            assert "error" in data
```

- [ ] **Step 2: Create gemini_reader.py**

````python
# apps/backend-rag/backend/services/naga/readers/gemini_reader.py
"""Gemini Bulk Reader — processes multiple sources via Gemini's 1M context.

Uses the Pointer State Pattern: the evidence_map is saved to a file
(local disk or Drive), and only the URI is stored in LangGraph state
and the database. This prevents TOAST bloat on the 2GB Fly.io database.

Architecture:
    Scored sources → Gemini prompt → evidence_map JSON → file on disk → URI pointer
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

from backend.services.naga.quality.source_scorer import ScoredSource

logger = logging.getLogger(__name__)


class GeminiBulkReader:
    """Reads multiple sources through Gemini for structured evidence extraction.

    The reader builds a prompt containing all source content and sub-questions,
    sends it to Gemini, and parses the structured response into an evidence_map.

    The evidence_map is saved to a local file (Pointer State Pattern).
    """

    def __init__(self) -> None:
        self._api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLEAISTUDIO_API_KEY", "")

    async def read_and_save(
        self,
        sources: list[ScoredSource],
        sub_questions: list[str],
        session_id: str,
        evidence_dir: str | None = None,
    ) -> str:
        """Read sources via Gemini and save evidence_map to file.

        Args:
            sources: Scored sources to read.
            sub_questions: Sub-questions to extract facts for.
            session_id: Session ID for file naming.
            evidence_dir: Base directory for evidence files.

        Returns:
            File path URI to the saved evidence_map JSON.
        """
        base_dir = evidence_dir or os.getenv("NAGA_EVIDENCE_DIR", "/tmp/naga")
        session_dir = Path(base_dir) / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        evidence_path = session_dir / "evidence.json"

        try:
            evidence_map = await self._call_gemini(sources, sub_questions)
        except Exception as exc:
            logger.error("Gemini bulk read failed: %s", exc)
            evidence_map = {
                "facts": [],
                "contradictions": [],
                "gaps": [f"Gemini read failed: {exc}"],
                "data_points": [],
                "error": str(exc),
            }

        evidence_path.write_text(
            json.dumps(evidence_map, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        uri = str(evidence_path)
        logger.info(
            "GeminiBulkReader: evidence_map saved to %s (%d facts, %d gaps)",
            uri,
            len(evidence_map.get("facts", [])),
            len(evidence_map.get("gaps", [])),
        )
        return uri

    async def _call_gemini(
        self,
        sources: list[ScoredSource],
        sub_questions: list[str],
    ) -> dict[str, Any]:
        """Call Gemini API with source content + sub-questions.

        Args:
            sources: Sources to include in prompt.
            sub_questions: Questions to extract facts for.

        Returns:
            Parsed evidence_map dict.
        """
        import httpx

        if not self._api_key:
            raise ValueError("No GOOGLE_API_KEY set for Gemini bulk reader")

        # Build prompt
        source_blocks = []
        for i, scored in enumerate(sources):
            s = scored.source
            block = (
                f"[SOURCE_{i+1}] URL: {s.url}\n"
                f"Title: {s.title}\n"
                f"Type: {s.source_type} | Credibility: {scored.credibility_score}\n"
                f"Content:\n{s.content[:8000]}\n"
            )
            source_blocks.append(block)

        questions_text = "\n".join(f"  Q{i+1}: {q}" for i, q in enumerate(sub_questions))
        sources_text = "\n---\n".join(source_blocks)

        prompt = (
            "You are a research analyst. Read all sources below and extract structured evidence.\n\n"
            f"SUB-QUESTIONS:\n{questions_text}\n\n"
            f"SOURCES:\n{sources_text}\n\n"
            "Reply with ONLY valid JSON (no markdown fences):\n"
            "{\n"
            '  "facts": [{"sub_question": "...", "fact": "...", "source_ids": ["SOURCE_1"], "confidence": 0.0-1.0}],\n'
            '  "contradictions": [{"topic": "...", "position_a": "...", "source_a": "SOURCE_1", "position_b": "...", "source_b": "SOURCE_2"}],\n'
            '  "gaps": ["what is NOT covered by any source"],\n'
            '  "data_points": [{"value": "...", "context": "...", "source_id": "SOURCE_1"}]\n'
            "}"
        )

        model = os.getenv("NAGA_MODEL_READER", "gemini-2.5-pro")
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}"
            f":generateContent?key={self._api_key}"
        )

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                url,
                json={"contents": [{"parts": [{"text": prompt}]}]},
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

        # Parse response
        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
            .strip()
        )

        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3].strip()
        if text.startswith("json"):
            text = text[4:].strip()

        return json.loads(text)
````

- [ ] **Step 3: Create **init**.py**

```python
# apps/backend-rag/backend/services/naga/readers/__init__.py
"""Naga readers: Gemini bulk reader for evidence extraction."""
```

- [ ] **Step 4: Run test**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/naga/test_gemini_reader.py -v
# Expected: 3 passed
```

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/services/naga/readers/ \
        apps/backend-rag/backend/tests/services/naga/test_gemini_reader.py
git commit -m "feat(naga): add Gemini Bulk Reader with Pointer State Pattern"
```

---

### Task 13: Convergence Detector (with adversarial check)

**Files:**

- Create: `apps/backend-rag/backend/services/naga/quality/convergence.py`

- [ ] **Step 1: Write the test**

```python
# apps/backend-rag/backend/tests/services/naga/test_convergence.py
"""Tests for Convergence Detector."""

import pytest

from backend.services.naga.quality.convergence import (
    ConvergenceDetector,
    ConvergenceDecision,
)
from backend.services.naga.config.naga_config import NagaConfig


@pytest.fixture
def detector() -> ConvergenceDetector:
    return ConvergenceDetector(config=NagaConfig())


class TestConvergenceDetector:
    """Test convergence logic."""

    def test_converged_when_coverage_high(self, detector: ConvergenceDetector) -> None:
        decision = detector.evaluate(
            sub_questions=["Q1", "Q2", "Q3", "Q4", "Q5"],
            answered_questions={"Q1", "Q2", "Q3", "Q4", "Q5"},
            new_claims_count=1,
            total_claims_count=20,
            budget_remaining=True,
            iteration=2,
        )
        assert decision == ConvergenceDecision.CONVERGED

    def test_iterate_when_low_coverage(self, detector: ConvergenceDetector) -> None:
        decision = detector.evaluate(
            sub_questions=["Q1", "Q2", "Q3", "Q4", "Q5"],
            answered_questions={"Q1"},
            new_claims_count=5,
            total_claims_count=5,
            budget_remaining=True,
            iteration=1,
        )
        assert decision == ConvergenceDecision.ITERATE

    def test_timeout_when_no_budget(self, detector: ConvergenceDetector) -> None:
        decision = detector.evaluate(
            sub_questions=["Q1", "Q2"],
            answered_questions=set(),
            new_claims_count=0,
            total_claims_count=0,
            budget_remaining=False,
            iteration=3,
        )
        assert decision == ConvergenceDecision.TIMEOUT

    def test_high_novelty_prevents_convergence(self, detector: ConvergenceDetector) -> None:
        decision = detector.evaluate(
            sub_questions=["Q1", "Q2", "Q3"],
            answered_questions={"Q1", "Q2", "Q3"},
            new_claims_count=8,
            total_claims_count=10,
            budget_remaining=True,
            iteration=2,
        )
        # 80% novelty = still finding new stuff, should iterate
        assert decision == ConvergenceDecision.ITERATE

    def test_saturation_triggers_convergence(self, detector: ConvergenceDetector) -> None:
        decision = detector.evaluate(
            sub_questions=["Q1", "Q2", "Q3"],
            answered_questions={"Q1", "Q2", "Q3"},
            new_claims_count=1,
            total_claims_count=30,
            budget_remaining=True,
            iteration=3,
        )
        assert decision == ConvergenceDecision.CONVERGED
```

- [ ] **Step 2: Create convergence.py**

```python
# apps/backend-rag/backend/services/naga/quality/convergence.py
"""Convergence Detector for Naga research loops.

Decides whether to iterate, converge, or timeout based on:
  - coverage: % sub-questions answered with at least 1 VERIFIED/LIKELY claim
  - novelty: ratio of new claims in last iteration vs total
  - budget: remaining search calls and TTL

Before declaring CONVERGED, an adversarial check placeholder is invoked
(v1: logged only, v1.1: active contradiction search).
"""

import enum
import logging

from backend.services.naga.config.naga_config import NagaConfig

logger = logging.getLogger(__name__)


class ConvergenceDecision(enum.Enum):
    """Outcome of convergence evaluation."""

    CONVERGED = "converged"
    ITERATE = "iterate"
    TIMEOUT = "timeout"


class ConvergenceDetector:
    """Evaluates whether a research session should continue or stop.

    Args:
        config: NagaConfig with convergence thresholds.
    """

    def __init__(self, config: NagaConfig) -> None:
        self._config = config

    def evaluate(
        self,
        sub_questions: list[str],
        answered_questions: set[str],
        new_claims_count: int,
        total_claims_count: int,
        budget_remaining: bool,
        iteration: int,
    ) -> ConvergenceDecision:
        """Evaluate convergence based on coverage, novelty, and budget.

        Args:
            sub_questions: All sub-questions for this session.
            answered_questions: Sub-questions with at least 1 VERIFIED/LIKELY claim.
            new_claims_count: Claims extracted in the latest iteration.
            total_claims_count: Total claims across all iterations.
            budget_remaining: Whether search budget is available.
            iteration: Current iteration number.

        Returns:
            ConvergenceDecision: CONVERGED, ITERATE, or TIMEOUT.
        """
        # Budget check first
        if not budget_remaining:
            logger.info("Convergence: TIMEOUT — budget exhausted at iteration %d", iteration)
            return ConvergenceDecision.TIMEOUT

        # Coverage
        total_q = max(len(sub_questions), 1)
        coverage = len(answered_questions) / total_q

        # Novelty
        if total_claims_count > 0:
            novelty = new_claims_count / total_claims_count
        else:
            novelty = 1.0  # No claims yet = high novelty

        logger.info(
            "Convergence: coverage=%.2f (threshold=%.2f) novelty=%.2f (threshold=%.2f) "
            "iteration=%d budget=%s",
            coverage,
            self._config.convergence_coverage_threshold,
            novelty,
            self._config.convergence_novelty_threshold,
            iteration,
            budget_remaining,
        )

        # Check convergence
        coverage_ok = coverage >= self._config.convergence_coverage_threshold
        saturated = novelty <= self._config.convergence_novelty_threshold

        if coverage_ok and saturated:
            # Adversarial check placeholder (v1: always passes)
            adversarial_pass = self._adversarial_check(iteration)
            if adversarial_pass:
                logger.info(
                    "Convergence: CONVERGED at iteration %d (coverage=%.2f, novelty=%.2f)",
                    iteration,
                    coverage,
                    novelty,
                )
                return ConvergenceDecision.CONVERGED
            else:
                logger.info("Convergence: ITERATE — adversarial check found contradictions")
                return ConvergenceDecision.ITERATE

        logger.info(
            "Convergence: ITERATE — coverage=%s saturated=%s",
            "OK" if coverage_ok else "LOW",
            "YES" if saturated else "NO",
        )
        return ConvergenceDecision.ITERATE

    def _adversarial_check(self, iteration: int) -> bool:
        """Placeholder for adversarial contradiction search.

        In v1.1, this will use Opus to search for contradictions
        to the top VERIFIED claims. For v1.0, always passes.

        Args:
            iteration: Current iteration number.

        Returns:
            True if no contradictions found (safe to converge).
        """
        if not self._config.adversarial_enabled:
            return True

        # v1.0: always pass. v1.1: active search.
        logger.info("Adversarial check: PASS (v1.0 placeholder, iteration=%d)", iteration)
        return True
```

- [ ] **Step 3: Run test**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/naga/test_convergence.py -v
# Expected: 5 passed
```

- [ ] **Step 4: Commit**

```bash
git add apps/backend-rag/backend/services/naga/quality/convergence.py \
        apps/backend-rag/backend/tests/services/naga/test_convergence.py
git commit -m "feat(naga): add Convergence Detector with adversarial check placeholder"
```

---

### Task 14: Report Writer

**Files:**

- Create: `apps/backend-rag/backend/services/naga/synthesis/__init__.py`
- Create: `apps/backend-rag/backend/services/naga/synthesis/report_writer.py`

- [ ] **Step 1: Write the test**

```python
# apps/backend-rag/backend/tests/services/naga/test_report_writer.py
"""Tests for Report Writer."""

from unittest.mock import AsyncMock, patch

import pytest

from backend.services.naga.synthesis.report_writer import ReportWriter


class TestReportWriter:
    """Test multi-tier report generation."""

    @pytest.mark.asyncio
    async def test_flash_report_is_short(self) -> None:
        writer = ReportWriter()
        mock_report = "KITAS E23 requires RPTKA. The fee is Rp 3.5M. [1]"
        with patch.object(writer, "_generate_report", new_callable=AsyncMock, return_value=mock_report):
            report = await writer.write(
                tier="flash",
                query="KITAS E23 fees",
                evidence_map={"facts": [{"fact": "Fee is Rp 3.5M", "source_ids": ["1"]}],
                              "contradictions": [], "gaps": [], "data_points": []},
                claims=[],
            )
        assert isinstance(report, str)
        assert len(report) > 0

    @pytest.mark.asyncio
    async def test_deep_report_has_sections(self) -> None:
        writer = ReportWriter()
        mock_report = (
            "## Executive Summary\nSummary here.\n\n"
            "## Findings\nDetails here.\n\n"
            "## Research Limitations\nLimitations noted.\n\n"
            "## Sources\n[1] example.com"
        )
        with patch.object(writer, "_generate_report", new_callable=AsyncMock, return_value=mock_report):
            report = await writer.write(
                tier="deep",
                query="Impact of PP 28/2025",
                evidence_map={"facts": [], "contradictions": [], "gaps": [], "data_points": []},
                claims=[],
            )
        assert "## " in report

    @pytest.mark.asyncio
    async def test_handles_error(self) -> None:
        writer = ReportWriter()
        with patch.object(writer, "_generate_report", new_callable=AsyncMock,
                         side_effect=Exception("LLM error")):
            report = await writer.write(
                tier="flash",
                query="test",
                evidence_map={"facts": [], "contradictions": [], "gaps": [], "data_points": []},
                claims=[],
            )
        assert "error" in report.lower() or "could not" in report.lower()

    def test_build_flash_prompt(self) -> None:
        writer = ReportWriter()
        prompt = writer._build_prompt(
            tier="flash",
            query="KITAS fee?",
            evidence_map={"facts": [{"fact": "Rp 3.5M"}], "contradictions": [],
                         "gaps": [], "data_points": []},
            claims=[],
        )
        assert "KITAS fee?" in prompt
        assert "Rp 3.5M" in prompt

    def test_build_deep_prompt_has_sections(self) -> None:
        writer = ReportWriter()
        prompt = writer._build_prompt(
            tier="deep",
            query="Impact analysis",
            evidence_map={"facts": [], "contradictions": [], "gaps": [], "data_points": []},
            claims=[],
        )
        assert "Executive Summary" in prompt
        assert "Contradictions" in prompt or "Research Limitations" in prompt
```

- [ ] **Step 2: Create report_writer.py**

```python
# apps/backend-rag/backend/services/naga/synthesis/report_writer.py
"""Report Writer for Naga research engine.

Generates markdown reports in three tiers:
  - flash: 1-3 paragraphs with inline citations
  - deep: Structured report with executive summary, sections, limitations
  - exhaustive: Multi-perspective STORM-style synthesis

Uses Opus for synthesis (or falls back to Gemini).
"""

import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ReportWriter:
    """Generates research reports from evidence maps and claims.

    The writer does NOT access sources directly. It works from the
    evidence_map (facts, contradictions, gaps) and extracted claims.
    """

    def __init__(self) -> None:
        self._anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")

    async def write(
        self,
        tier: str,
        query: str,
        evidence_map: dict[str, Any],
        claims: list[dict],
    ) -> str:
        """Generate a research report.

        Args:
            tier: Report tier (flash/deep/exhaustive).
            query: Original research query.
            evidence_map: Structured evidence from Gemini reader.
            claims: Extracted claims with verification levels.

        Returns:
            Markdown report string.
        """
        try:
            prompt = self._build_prompt(tier, query, evidence_map, claims)
            report = await self._generate_report(prompt, tier)
            return report
        except Exception as exc:
            logger.error("Report generation failed: %s", exc)
            return (
                f"## Research Report\n\n"
                f"**Query:** {query}\n\n"
                f"Could not generate full report due to error: {exc}\n\n"
                f"**Raw facts found:** {len(evidence_map.get('facts', []))}\n"
                f"**Gaps identified:** {len(evidence_map.get('gaps', []))}\n"
            )

    def _build_prompt(
        self,
        tier: str,
        query: str,
        evidence_map: dict[str, Any],
        claims: list[dict],
    ) -> str:
        """Build the synthesis prompt for the LLM.

        Args:
            tier: Report tier.
            query: Research query.
            evidence_map: Structured evidence.
            claims: Extracted claims.

        Returns:
            Prompt string.
        """
        facts_text = json.dumps(evidence_map.get("facts", []), indent=2, ensure_ascii=False)
        contradictions_text = json.dumps(
            evidence_map.get("contradictions", []), indent=2, ensure_ascii=False
        )
        gaps_text = json.dumps(evidence_map.get("gaps", []), indent=2, ensure_ascii=False)
        data_points_text = json.dumps(
            evidence_map.get("data_points", []), indent=2, ensure_ascii=False
        )

        if tier == "flash":
            return (
                f"Write a concise research answer (1-3 paragraphs) with inline citations [1][2].\n\n"
                f"Query: {query}\n\n"
                f"Evidence:\n{facts_text}\n\n"
                f"Data points:\n{data_points_text}\n\n"
                f"Gaps (mention if critical):\n{gaps_text}\n\n"
                f"Rules: Only state facts from evidence. If uncertain, say so. "
                f"Cite source IDs inline like [SOURCE_1]."
            )
        elif tier == "deep":
            return (
                f"Write a structured research report in markdown.\n\n"
                f"Query: {query}\n\n"
                f"## Required Sections:\n"
                f"1. Executive Summary (2-3 sentences)\n"
                f"2. Detailed Findings (organized thematically)\n"
                f"3. Contradictions & Uncertainty\n"
                f"4. Research Limitations (including gaps)\n"
                f"5. Sources (numbered list)\n\n"
                f"Evidence:\n{facts_text}\n\n"
                f"Contradictions:\n{contradictions_text}\n\n"
                f"Gaps:\n{gaps_text}\n\n"
                f"Data points:\n{data_points_text}\n\n"
                f"Rules: Use [SOURCE_N] citations. Flag CONTESTED claims explicitly. "
                f"Include confidence indicators."
            )
        else:  # exhaustive
            return (
                f"Write a comprehensive multi-perspective research report in markdown.\n\n"
                f"Query: {query}\n\n"
                f"## Required Sections:\n"
                f"1. Executive Summary with aggregated confidence\n"
                f"2. Perspective Analysis (3+ viewpoints: legal, practical, comparative)\n"
                f"3. Evidence Status Map (VERIFIED / LIKELY / CONTESTED)\n"
                f"4. Timeline of Changes (if regulatory)\n"
                f"5. Operational Recommendations\n"
                f"6. Contradictions & Uncertainty\n"
                f"7. Research Limitations\n"
                f"8. Appendix: All Sources with Scores\n\n"
                f"Evidence:\n{facts_text}\n\n"
                f"Contradictions:\n{contradictions_text}\n\n"
                f"Gaps:\n{gaps_text}\n\n"
                f"Data points:\n{data_points_text}\n\n"
                f"Claims:\n{json.dumps(claims[:20], indent=2, ensure_ascii=False)}\n\n"
                f"Rules: Comprehensive, cite everything, flag contradictions, "
                f"include confidence levels for each major finding."
            )

    async def _generate_report(self, prompt: str, tier: str) -> str:
        """Call LLM to generate the report. Override in tests.

        Args:
            prompt: Full synthesis prompt.
            tier: Tier for model/token selection.

        Returns:
            Generated markdown report.
        """
        max_tokens = {"flash": 1024, "deep": 4096, "exhaustive": 8192}.get(tier, 4096)
        model = os.getenv("NAGA_MODEL_ORCHESTRATOR", "claude-opus-4-6")

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._anthropic_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            return resp.json()["content"][0]["text"]
```

- [ ] **Step 3: Create **init**.py**

```python
# apps/backend-rag/backend/services/naga/synthesis/__init__.py
"""Naga synthesis: report generation from evidence."""
```

- [ ] **Step 4: Run test**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/naga/test_report_writer.py -v
# Expected: 5 passed
```

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/services/naga/synthesis/ \
        apps/backend-rag/backend/tests/services/naga/test_report_writer.py
git commit -m "feat(naga): add Report Writer (flash/deep/exhaustive templates)"
```

---

## PHASE 4: Integration (Tasks 15-19)

### Task 15: LangGraph Orchestrator

The orchestrator uses `StateGraph` from LangGraph with `AsyncPostgresSaver` for checkpoint/resume, following the pattern in `backend/services/rag/kg_langgraph_orchestrator.py`.

**Files:**

- Create: `apps/backend-rag/backend/services/naga/orchestrator.py`

- [ ] **Step 1: Write the test**

```python
# apps/backend-rag/backend/tests/services/naga/test_orchestrator.py
"""Tests for Naga LangGraph Orchestrator."""

import json
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.naga.orchestrator import (
    NagaResearchState,
    build_naga_workflow,
    convergence_router,
)


class TestNagaResearchState:
    """Test state TypedDict structure."""

    def test_minimal_state(self) -> None:
        state: NagaResearchState = {
            "query": "test",
            "tier": "flash",
            "domain": "general",
            "mode": "oneshot",
            "channel": "api",
            "ttl_seconds": 60,
            "session_id": "test-123",
            "sub_questions": [],
            "search_results": [],
            "scored_sources": [],
            "evidence_map_uri": "",
            "claims": [],
            "answered_questions": set(),
            "iteration": 0,
            "budget_summary": {},
            "convergence_decision": "",
            "report_markdown": "",
            "action_items": [],
            "errors": [],
            "langgraph_thread_id": "",
        }
        assert state["query"] == "test"
        assert state["iteration"] == 0


class TestConvergenceRouter:
    """Test convergence routing logic."""

    def test_converged_routes_to_synthesize(self) -> None:
        state: NagaResearchState = {
            "query": "", "tier": "deep", "domain": "general", "mode": "oneshot",
            "channel": "api", "ttl_seconds": 300, "session_id": "",
            "sub_questions": [], "search_results": [], "scored_sources": [],
            "evidence_map_uri": "", "claims": [], "answered_questions": set(),
            "iteration": 2, "budget_summary": {"has_budget": True},
            "convergence_decision": "converged", "report_markdown": "",
            "action_items": [], "errors": [], "langgraph_thread_id": "",
        }
        assert convergence_router(state) == "synthesize"

    def test_iterate_routes_to_search(self) -> None:
        state: NagaResearchState = {
            "query": "", "tier": "deep", "domain": "general", "mode": "oneshot",
            "channel": "api", "ttl_seconds": 300, "session_id": "",
            "sub_questions": [], "search_results": [], "scored_sources": [],
            "evidence_map_uri": "", "claims": [], "answered_questions": set(),
            "iteration": 1, "budget_summary": {"has_budget": True},
            "convergence_decision": "iterate", "report_markdown": "",
            "action_items": [], "errors": [], "langgraph_thread_id": "",
        }
        assert convergence_router(state) == "search"

    def test_timeout_routes_to_synthesize(self) -> None:
        state: NagaResearchState = {
            "query": "", "tier": "deep", "domain": "general", "mode": "oneshot",
            "channel": "api", "ttl_seconds": 300, "session_id": "",
            "sub_questions": [], "search_results": [], "scored_sources": [],
            "evidence_map_uri": "", "claims": [], "answered_questions": set(),
            "iteration": 5, "budget_summary": {"has_budget": False},
            "convergence_decision": "timeout", "report_markdown": "",
            "action_items": [], "errors": [], "langgraph_thread_id": "",
        }
        assert convergence_router(state) == "synthesize"


class TestBuildWorkflow:
    """Test workflow graph construction."""

    def test_build_returns_state_graph(self) -> None:
        from langgraph.graph import StateGraph
        wf = build_naga_workflow()
        assert isinstance(wf, StateGraph)
```

- [ ] **Step 2: Create orchestrator.py**

```python
# apps/backend-rag/backend/services/naga/orchestrator.py
"""Naga LangGraph Orchestrator.

Uses StateGraph + conditional edges to implement the research loop:
  decompose → search → evaluate → converge? → synthesize → output

Follows the pattern in services/rag/kg_langgraph_orchestrator.py.
State uses Pointer State Pattern: only IDs and URIs, no large content.
"""

import asyncio
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from backend.core.claims.extractor import extract_claims_from_response
from backend.core.claims.models import ClaimRecord
from backend.services.naga.config.naga_config import NagaConfig
from backend.services.naga.gateway import GatewayResult
from backend.services.naga.quality.convergence import ConvergenceDecision, ConvergenceDetector
from backend.services.naga.quality.crag_light import CRAGLight
from backend.services.naga.quality.source_scorer import ScoredSource, SourceScorer
from backend.services.naga.readers.gemini_reader import GeminiBulkReader
from backend.services.naga.search_agents.base import SearchResult
from backend.services.naga.state.budget_tracker import BudgetTracker
from backend.services.naga.state.url_history import URLHistory
from backend.services.naga.synthesis.report_writer import ReportWriter

logger = logging.getLogger(__name__)

# Optional: PostgreSQL checkpointing
try:
    from langgraph.checkpoint.postgres import PostgresSaver
except ImportError:
    PostgresSaver = None  # type: ignore[assignment,misc]
    logger.warning("langgraph-checkpoint-postgres not installed, Naga checkpointing disabled")


# ============================================================================
# State Definition (Pointer State Pattern)
# ============================================================================


class NagaResearchState(TypedDict):
    """LangGraph state for Naga research sessions.

    Uses Pointer State Pattern: only IDs, URIs, and small metadata.
    Large data (evidence_map, source content) stored as files.
    """

    # Input (from Gateway)
    query: str
    tier: str
    domain: str
    mode: str
    channel: str
    ttl_seconds: int

    # Session
    session_id: str
    langgraph_thread_id: str

    # Decomposition
    sub_questions: list[str]

    # Search results (lightweight references only)
    search_results: list[dict[str, Any]]  # [{url, title, agent_name, source_type}]
    scored_sources: list[dict[str, Any]]  # [{url, final_score, credibility, freshness}]

    # Evidence (Pointer State: URI to file, not inline data)
    evidence_map_uri: str

    # Claims (lightweight)
    claims: list[dict[str, Any]]  # [{claim_id, claim_text, confidence, category}]
    answered_questions: set[str]

    # Loop control
    iteration: int
    budget_summary: dict[str, Any]
    convergence_decision: str

    # Output
    report_markdown: str
    action_items: list[dict[str, Any]]

    # Errors
    errors: list[str]


# ============================================================================
# Node Implementations
# ============================================================================


async def decompose_node(state: NagaResearchState) -> NagaResearchState:
    """Decompose query into sub-questions.

    For v1.0, uses simple heuristic decomposition.
    Future: Opus-assisted decomposition.
    """
    query = state["query"]

    # Simple decomposition: the query itself is the primary sub-question.
    # For complex queries, split on "and" / comma.
    sub_questions = [query]
    if " and " in query.lower() or "," in query:
        parts = query.replace(",", " and ").split(" and ")
        sub_questions = [p.strip() for p in parts if len(p.strip()) > 10]
        if not sub_questions:
            sub_questions = [query]

    state["sub_questions"] = sub_questions
    state["iteration"] = 0
    logger.info("Decompose: %d sub-questions from '%s'", len(sub_questions), query[:60])
    return state


async def search_node(state: NagaResearchState) -> NagaResearchState:
    """Dispatch search to agents and collect results.

    Selects agents based on domain, runs them in parallel.
    """
    from backend.services.naga.search_agents.brave_agent import BraveSearchAgent
    from backend.services.naga.search_agents.exa_agent import ExaSearchAgent
    from backend.services.naga.search_agents.domain_agent import IndonesiaDomainAgent

    state["iteration"] += 1
    query = state["query"]
    domain = state["domain"]

    # Select agents based on domain
    agents = [ExaSearchAgent(), BraveSearchAgent()]
    if domain in ("indonesia", "hybrid"):
        agents.append(IndonesiaDomainAgent())

    # Run agents in parallel
    tasks = [agent.search(query, max_results=10) for agent in agents]
    results_lists = await asyncio.gather(*tasks, return_exceptions=True)

    all_results: list[SearchResult] = []
    for result_or_exc in results_lists:
        if isinstance(result_or_exc, Exception):
            state["errors"].append(f"Search agent error: {result_or_exc}")
            continue
        all_results.extend(result_or_exc)

    # Store lightweight references
    state["search_results"] = [
        {"url": r.url, "title": r.title, "agent_name": r.agent_name, "source_type": r.source_type}
        for r in all_results
    ]

    logger.info("Search: %d results from %d agents (iteration %d)",
                len(all_results), len(agents), state["iteration"])
    return state


async def evaluate_node(state: NagaResearchState) -> NagaResearchState:
    """Score sources, run CRAG filter, bulk read via Gemini, extract claims."""
    config = NagaConfig()
    scorer = SourceScorer(config=config)
    crag = CRAGLight()
    reader = GeminiBulkReader()

    # Reconstruct SearchResults from state (lightweight → full objects for scoring)
    # In production, this would fetch content from URL history/cache
    search_results = [
        SearchResult(
            url=r["url"],
            title=r["title"],
            content="",  # Content fetched separately
            source_type=r["source_type"],
            agent_name=r["agent_name"],
        )
        for r in state["search_results"]
    ]

    # Score and filter
    scored = scorer.score_and_filter(search_results)

    # CRAG relevance gate
    relevant = await crag.filter_batch(scored, query=state["query"])

    # Store scored sources (lightweight)
    state["scored_sources"] = [
        {"url": s.source.url, "final_score": s.final_score,
         "credibility": s.credibility_score, "freshness": s.freshness_score}
        for s in relevant
    ]

    # Gemini bulk read (skip for flash tier)
    if state["tier"] != "flash" and relevant:
        evidence_uri = await reader.read_and_save(
            sources=relevant,
            sub_questions=state["sub_questions"],
            session_id=state["session_id"],
        )
        state["evidence_map_uri"] = evidence_uri

        # Extract claims from evidence map
        evidence_path = Path(evidence_uri)
        if evidence_path.exists():
            evidence_map = json.loads(evidence_path.read_text())
            facts_text = "\n".join(
                f.get("fact", "") for f in evidence_map.get("facts", [])
            )
            if facts_text:
                claim_records = extract_claims_from_response(
                    response_text=facts_text,
                    source_ids=[s.source.url for s in relevant[:5]],
                    query_cluster="NAGA",
                    claim_id_prefix="NAGA",
                )
                state["claims"].extend([c.to_dict() for c in claim_records])

                # Track answered questions
                for fact in evidence_map.get("facts", []):
                    sq = fact.get("sub_question", "")
                    if sq and sq in state["sub_questions"]:
                        state["answered_questions"].add(sq)

    # Convergence check
    detector = ConvergenceDetector(config=config)
    budget_remaining = state["iteration"] < config.tier_budgets[state["tier"]].max_iterations

    new_claims = len(state["claims"])  # Simplified: all claims are "new" in iteration 1
    decision = detector.evaluate(
        sub_questions=state["sub_questions"],
        answered_questions=state["answered_questions"],
        new_claims_count=new_claims,
        total_claims_count=max(new_claims, 1),
        budget_remaining=budget_remaining,
        iteration=state["iteration"],
    )
    state["convergence_decision"] = decision.value
    state["budget_summary"] = {"has_budget": budget_remaining, "iteration": state["iteration"]}

    logger.info("Evaluate: %d scored, %d relevant, %d claims, decision=%s",
                len(scored), len(relevant), len(state["claims"]), decision.value)
    return state


async def synthesize_node(state: NagaResearchState) -> NagaResearchState:
    """Generate the final research report from evidence and claims."""
    writer = ReportWriter()

    # Load evidence map from file (Pointer State)
    evidence_map: dict[str, Any] = {"facts": [], "contradictions": [], "gaps": [], "data_points": []}
    if state["evidence_map_uri"]:
        evidence_path = Path(state["evidence_map_uri"])
        if evidence_path.exists():
            evidence_map = json.loads(evidence_path.read_text())

    report = await writer.write(
        tier=state["tier"],
        query=state["query"],
        evidence_map=evidence_map,
        claims=state["claims"],
    )
    state["report_markdown"] = report

    logger.info("Synthesize: report generated (%d chars) for tier=%s",
                len(report), state["tier"])
    return state


# ============================================================================
# Routing
# ============================================================================


def convergence_router(state: NagaResearchState) -> str:
    """Route based on convergence decision.

    Returns:
        'search' (iterate), 'synthesize' (converged/timeout), or END.
    """
    decision = state.get("convergence_decision", "")
    if decision == "converged":
        return "synthesize"
    elif decision == "iterate":
        return "search"
    elif decision == "timeout":
        return "synthesize"
    return "synthesize"  # Default: synthesize what we have


# ============================================================================
# Graph Construction
# ============================================================================


def build_naga_workflow() -> StateGraph:
    """Build the Naga research LangGraph workflow.

    Graph:
        decompose → search → evaluate → [converge?] → synthesize → END
                                          ↓ iterate
                                        search (loop)

    Returns:
        StateGraph (not compiled — caller compiles with optional checkpointer).
    """
    workflow = StateGraph(NagaResearchState)

    workflow.add_node("decompose", decompose_node)
    workflow.add_node("search", search_node)
    workflow.add_node("evaluate", evaluate_node)
    workflow.add_node("synthesize", synthesize_node)

    workflow.set_entry_point("decompose")
    workflow.add_edge("decompose", "search")
    workflow.add_edge("search", "evaluate")

    workflow.add_conditional_edges(
        "evaluate",
        convergence_router,
        {
            "search": "search",
            "synthesize": "synthesize",
        },
    )
    workflow.add_edge("synthesize", END)

    logger.info("Built Naga workflow: decompose → search → evaluate → [converge?] → synthesize")
    return workflow


# ============================================================================
# Public API
# ============================================================================


class NagaOrchestrator:
    """High-level orchestrator for Naga research.

    Usage:
        orchestrator = NagaOrchestrator(db_pool)
        result = await orchestrator.research(
            query="Impact of PP 28/2025 on KITAS",
            gateway=GatewayResult(tier="deep", domain="indonesia", mode="oneshot", ttl_seconds=300),
            channel="claude_code",
        )
    """

    def __init__(self, db_pool: Any = None) -> None:
        self._db_pool = db_pool
        self._app = None

    async def initialize(self) -> None:
        """Compile the workflow (call once at startup)."""
        if self._app is not None:
            return

        workflow = build_naga_workflow()

        checkpointer = None
        if PostgresSaver is not None and self._db_pool is not None:
            try:
                checkpointer = PostgresSaver(self._db_pool)
                await checkpointer.setup()
                logger.info("Naga: PostgreSQL checkpointer initialized")
            except Exception as exc:
                logger.warning("Naga: PostgresSaver setup failed: %s", exc)
                checkpointer = None

        self._app = workflow.compile(checkpointer=checkpointer)
        logger.info("Naga orchestrator initialized (checkpointer=%s)",
                     "postgres" if checkpointer else "none")

    async def research(
        self,
        query: str,
        gateway: GatewayResult,
        channel: str = "api",
    ) -> dict[str, Any]:
        """Execute a research session.

        Args:
            query: Research query.
            gateway: Gateway classification result.
            channel: Origin channel.

        Returns:
            Final state dict with report_markdown, claims, action_items.
        """
        if self._app is None:
            await self.initialize()

        session_id = str(uuid.uuid4())
        thread_id = f"naga_{session_id}"

        initial_state: NagaResearchState = {
            "query": query,
            "tier": gateway.tier,
            "domain": gateway.domain,
            "mode": gateway.mode,
            "channel": channel,
            "ttl_seconds": gateway.ttl_seconds,
            "session_id": session_id,
            "langgraph_thread_id": thread_id,
            "sub_questions": [],
            "search_results": [],
            "scored_sources": [],
            "evidence_map_uri": "",
            "claims": [],
            "answered_questions": set(),
            "iteration": 0,
            "budget_summary": {},
            "convergence_decision": "",
            "report_markdown": "",
            "action_items": [],
            "errors": [],
        }

        config = {"configurable": {"thread_id": thread_id}}

        try:
            final_state = await self._app.ainvoke(initial_state, config=config)
            logger.info(
                "Naga research complete: session=%s iterations=%d claims=%d",
                session_id,
                final_state.get("iteration", 0),
                len(final_state.get("claims", [])),
            )
            return final_state
        except Exception as exc:
            logger.error("Naga research failed: %s", exc, exc_info=True)
            return {
                "session_id": session_id,
                "error": str(exc),
                "report_markdown": f"Research failed: {exc}",
                "claims": [],
                "action_items": [],
            }
```

- [ ] **Step 3: Run test**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/naga/test_orchestrator.py -v
# Expected: 4 passed
```

- [ ] **Step 4: Commit**

```bash
git add apps/backend-rag/backend/services/naga/orchestrator.py \
        apps/backend-rag/backend/tests/services/naga/test_orchestrator.py
git commit -m "feat(naga): add LangGraph orchestrator with StateGraph + convergence routing"
```

---

### Task 16: FastAPI Router

**Files:**

- Create: `apps/backend-rag/backend/app/routers/naga.py`

- [ ] **Step 1: Write the test**

```python
# apps/backend-rag/backend/tests/routers/test_naga.py
"""Tests for Naga FastAPI router."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers.naga import router


@pytest.fixture
def app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


class TestNagaRouter:
    """Test Naga API endpoints."""

    def test_research_endpoint_exists(self, client: TestClient) -> None:
        # Without auth, should get 422 or 401, not 404
        resp = client.post("/api/naga/research", json={"query": "test"})
        assert resp.status_code != 404

    def test_research_requires_query(self, client: TestClient) -> None:
        resp = client.post("/api/naga/research", json={})
        assert resp.status_code == 422

    @patch("backend.app.routers.naga._get_orchestrator")
    def test_research_returns_report(self, mock_get_orch: MagicMock, client: TestClient) -> None:
        mock_orch = AsyncMock()
        mock_orch.research.return_value = {
            "session_id": "test-123",
            "report_markdown": "## Report\nTest findings.",
            "claims": [],
            "action_items": [],
            "iteration": 1,
            "errors": [],
        }
        mock_get_orch.return_value = mock_orch

        resp = client.post("/api/naga/research", json={
            "query": "KITAS E23 requirements",
            "tier": "flash",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert "report_markdown" in data

    def test_claims_search_endpoint_exists(self, client: TestClient) -> None:
        resp = client.get("/api/naga/claims/search", params={"q": "KITAS"})
        assert resp.status_code != 404

    def test_session_endpoint_exists(self, client: TestClient) -> None:
        resp = client.get("/api/naga/session/test-123")
        assert resp.status_code != 404
```

- [ ] **Step 2: Create naga.py router**

```python
# apps/backend-rag/backend/app/routers/naga.py
"""Naga Research Engine — FastAPI endpoints.

Endpoints:
  POST /api/naga/research       — Start a research session
  GET  /api/naga/session/{id}   — Get session status/results
  GET  /api/naga/claims/search  — Search claims DB
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.services.naga.gateway import GatewayResult, classify_query
from backend.services.naga.orchestrator import NagaOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/naga", tags=["naga"])

# Module-level singleton
_orchestrator: NagaOrchestrator | None = None


def _get_orchestrator() -> NagaOrchestrator:
    """Get or create Naga orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = NagaOrchestrator()
    return _orchestrator


# ─── Request/Response Models ───


class ResearchRequest(BaseModel):
    """Research request body."""

    query: str = Field(..., min_length=3, max_length=2000, description="Research query")
    tier: Optional[str] = Field(None, description="Override tier: flash/deep/exhaustive")
    domain: Optional[str] = Field(None, description="Override domain: indonesia/general/hybrid")
    channel: str = Field("api", description="Origin channel")
    trusted_mode: bool = Field(False, description="Enable auto-execute actions")


class ResearchResponse(BaseModel):
    """Research response."""

    session_id: str
    tier: str
    domain: str
    report_markdown: str
    claims_count: int
    iterations: int
    action_items: list[dict[str, Any]] = []
    errors: list[str] = []


class ClaimSearchResponse(BaseModel):
    """Claims search response."""

    claims: list[dict[str, Any]]
    total: int


class SessionResponse(BaseModel):
    """Session status response."""

    session_id: str
    status: str
    tier: str
    domain: str
    iterations: int
    claims_count: int
    report_markdown: str = ""


# ─── Endpoints ───


@router.post("/research", response_model=ResearchResponse)
async def research(request: ResearchRequest) -> ResearchResponse:
    """Start a Naga research session.

    Classifies the query via the Gateway, then runs the LangGraph
    orchestrator to search, verify, and synthesize.
    """
    logger.info("Naga research request: query='%s' tier=%s", request.query[:60], request.tier)

    gateway = classify_query(
        query=request.query,
        channel=request.channel,
        tier_override=request.tier,
        domain_override=request.domain,
    )

    orchestrator = _get_orchestrator()
    result = await orchestrator.research(
        query=request.query,
        gateway=gateway,
        channel=request.channel,
    )

    return ResearchResponse(
        session_id=result.get("session_id", ""),
        tier=gateway.tier,
        domain=gateway.domain,
        report_markdown=result.get("report_markdown", ""),
        claims_count=len(result.get("claims", [])),
        iterations=result.get("iteration", 0),
        action_items=result.get("action_items", []),
        errors=result.get("errors", []),
    )


@router.get("/session/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, request: Request) -> SessionResponse:
    """Get research session status and results.

    In v1.0, sessions are not persisted to DB yet.
    Returns a placeholder for session lookup.
    """
    # v1.0: session persistence not implemented yet
    # v1.1: will query naga_sessions table
    logger.info("Naga session lookup: %s", session_id)
    raise HTTPException(
        status_code=501,
        detail="Session persistence not yet implemented (v1.1)",
    )


@router.get("/claims/search", response_model=ClaimSearchResponse)
async def search_claims(
    q: str = Query(..., min_length=2, description="Search query"),
    domain: Optional[str] = Query(None, description="Filter by domain"),
    verification: Optional[str] = Query(None, description="Filter by verification level"),
    limit: int = Query(20, ge=1, le=100),
    request: Request = None,
) -> ClaimSearchResponse:
    """Search the Naga claims database.

    In v1.0, returns empty results. Claims DB query will be added in v1.1
    after migration 079 is deployed and claims are being persisted.
    """
    logger.info("Naga claims search: q='%s' domain=%s", q, domain)
    # v1.0: placeholder — no claims persisted yet
    return ClaimSearchResponse(claims=[], total=0)
```

- [ ] **Step 3: Run test**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/routers/test_naga.py -v
# Expected: 5 passed
```

- [ ] **Step 4: Register router in router_registration.py**

Add to `apps/backend-rag/backend/app/setup/router_registration.py`:

```python
# In the lazy-loaded router section, add:
from backend.app.routers.naga import router as naga_router
app.include_router(naga_router)
```

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/app/routers/naga.py \
        apps/backend-rag/backend/tests/routers/test_naga.py \
        apps/backend-rag/backend/app/setup/router_registration.py
git commit -m "feat(naga): add FastAPI router (/api/naga/research, /session, /claims/search)"
```

---

### Task 17: MCP Tool Registration

MCP tools use HTTP `_call()` to the backend. Never direct Python imports.

**Files:**

- Create: `apps/nuzantara-mcp/nuzantara_mcp/tools/naga.py`

- [ ] **Step 1: Write the test**

```python
# apps/nuzantara-mcp/tests/test_naga_tools.py
"""Tests for Naga MCP tool registration."""

from unittest.mock import AsyncMock, patch

import pytest


class TestNagaMCPTools:
    """Test MCP tool definitions."""

    def test_tools_import(self) -> None:
        # Should not raise on import
        import nuzantara_mcp.tools.naga  # noqa: F401

    @pytest.mark.asyncio
    async def test_naga_research_calls_backend(self) -> None:
        from nuzantara_mcp.tools.naga import _naga_research_impl

        mock_response = {
            "session_id": "test-123",
            "report_markdown": "## Report\nFindings here.",
            "claims_count": 3,
            "iterations": 2,
        }

        with patch("nuzantara_mcp.tools.naga._call", new_callable=AsyncMock, return_value=mock_response):
            result = await _naga_research_impl(
                query="KITAS requirements",
                tier="deep",
                domain=None,
            )
            assert result["session_id"] == "test-123"

    @pytest.mark.asyncio
    async def test_naga_claims_search_calls_backend(self) -> None:
        from nuzantara_mcp.tools.naga import _naga_claims_search_impl

        mock_response = {"claims": [], "total": 0}

        with patch("nuzantara_mcp.tools.naga._call", new_callable=AsyncMock, return_value=mock_response):
            result = await _naga_claims_search_impl(query="visa", domain="indonesia")
            assert "claims" in result
```

- [ ] **Step 2: Create naga.py MCP tools**

```python
# apps/nuzantara-mcp/nuzantara_mcp/tools/naga.py
"""Naga Research Engine MCP tools.

IMPORTANT: Tools use HTTP _call() to backend API.
Never import from backend/ directly.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger("nuzantara-mcp.naga")

# Lazy import to avoid circular deps at module load
_call = None
_mcp = None


def _get_call():
    global _call
    if _call is None:
        from nuzantara_mcp.server import _call as server_call
        _call = server_call
    return _call


def _get_mcp():
    global _mcp
    if _mcp is None:
        from nuzantara_mcp.server import mcp
        _mcp = mcp
    return _mcp


async def _naga_research_impl(
    query: str,
    tier: str | None = None,
    domain: str | None = None,
    channel: str = "mcp",
) -> dict[str, Any]:
    """Implementation for naga_research tool."""
    call = _get_call()
    payload: dict[str, Any] = {"query": query, "channel": channel}
    if tier:
        payload["tier"] = tier
    if domain:
        payload["domain"] = domain

    return await call(
        "/api/naga/research",
        method="POST",
        json=payload,
        timeout=1800,  # Research can take up to 30 min
    )


async def _naga_claims_search_impl(
    query: str,
    domain: str | None = None,
    verification: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Implementation for naga_claims_search tool."""
    call = _get_call()
    params: dict[str, Any] = {"q": query, "limit": limit}
    if domain:
        params["domain"] = domain
    if verification:
        params["verification"] = verification

    return await call("/api/naga/claims/search", params=params)


def register_naga_tools() -> None:
    """Register Naga MCP tools with the server."""
    mcp = _get_mcp()

    @mcp.tool()
    async def naga_research(
        query: str,
        tier: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> str:
        """Run a Naga agentic research session.

        Multi-model research engine that searches, verifies, and synthesizes.
        Returns a structured report with verified claims and inline citations.

        Args:
            query: Research query (e.g., "Impact of PP 28/2025 on KITAS").
            tier: Override: flash (5-15s), deep (1-5min), exhaustive (5-30min).
            domain: Override: indonesia, general, or hybrid.
        """
        import json
        result = await _naga_research_impl(query, tier, domain)
        if "error" in result:
            return f"Research failed: {result['error']}"
        report = result.get("report_markdown", "No report generated.")
        claims = result.get("claims_count", 0)
        session = result.get("session_id", "unknown")
        return f"Session: {session}\nClaims: {claims}\n\n{report}"

    @mcp.tool()
    async def naga_claims_search(
        query: str,
        domain: Optional[str] = None,
        verification: Optional[str] = None,
    ) -> str:
        """Search verified claims from Naga research sessions.

        Queries the claims database for previously verified facts.

        Args:
            query: Search text (e.g., "KITAS E23 fee").
            domain: Filter: indonesia, general.
            verification: Filter: VERIFIED, LIKELY, CONTESTED.
        """
        import json
        result = await _naga_claims_search_impl(query, domain, verification)
        claims = result.get("claims", [])
        if not claims:
            return "No claims found matching query."
        return json.dumps(claims, indent=2, ensure_ascii=False)

    logger.info("Registered 2 Naga MCP tools: naga_research, naga_claims_search")


# Auto-register on import
try:
    register_naga_tools()
except Exception as exc:
    logger.warning("Failed to register Naga MCP tools: %s", exc)
```

- [ ] **Step 3: Register in server.py tool imports**

Add to `apps/nuzantara-mcp/nuzantara_mcp/server.py` in the tool import section:

```python
import nuzantara_mcp.tools.naga  # noqa: F401  # Naga research engine
```

- [ ] **Step 4: Run test**

```bash
cd apps/nuzantara-mcp
PYTHONPATH=. pytest tests/test_naga_tools.py -v
# Expected: 3 passed
```

- [ ] **Step 5: Commit**

```bash
git add apps/nuzantara-mcp/nuzantara_mcp/tools/naga.py \
        apps/nuzantara-mcp/nuzantara_mcp/server.py \
        apps/nuzantara-mcp/tests/test_naga_tools.py
git commit -m "feat(naga): add MCP tools (naga_research, naga_claims_search) via HTTP _call()"
```

---

### Task 18: Action Engine

**Files:**

- Create: `apps/backend-rag/backend/services/naga/actions/__init__.py`
- Create: `apps/backend-rag/backend/services/naga/actions/action_engine.py`

- [ ] **Step 1: Write the test**

```python
# apps/backend-rag/backend/tests/services/naga/test_action_engine.py
"""Tests for Naga Action Engine."""

import pytest

from backend.services.naga.actions.action_engine import ActionEngine, ActionItem


class TestActionEngine:
    """Test deterministic action trigger detection."""

    def test_no_actions_for_empty_claims(self) -> None:
        engine = ActionEngine()
        actions = engine.evaluate(claims=[], domain="general")
        assert actions == []

    def test_verified_client_impact_generates_notify(self) -> None:
        engine = ActionEngine()
        claims = [
            {
                "claim_id": "NAGA-abc123",
                "claim_text": "KITAS E23 fee increased to Rp 5,000,000",
                "category": "FEE_CHANGE",
                "confidence_score": 0.90,
                "affected_visa_types": ["KITAS_E23"],
                "confidence_class": "VERIFIED",
            },
        ]
        actions = engine.evaluate(claims=claims, domain="indonesia")
        assert len(actions) >= 1
        assert actions[0].action_type == "notify"

    def test_newsworthy_claim_generates_article_draft(self) -> None:
        engine = ActionEngine()
        claims = [
            {
                "claim_id": "NAGA-def456",
                "claim_text": "Indonesia launches new digital nomad visa category E33G",
                "category": "LEGAL_CHANGE",
                "confidence_score": 0.88,
                "affected_visa_types": ["KITAS_E33"],
                "confidence_class": "VERIFIED",
            },
        ]
        actions = engine.evaluate(claims=claims, domain="indonesia")
        has_draft = any(a.action_type == "draft_article" for a in actions)
        assert has_draft is True

    def test_low_confidence_no_action(self) -> None:
        engine = ActionEngine()
        claims = [
            {
                "claim_id": "NAGA-low",
                "claim_text": "Some unverified rumor",
                "category": "POLICY_SIGNAL",
                "confidence_score": 0.25,
                "confidence_class": "LOW",
            },
        ]
        actions = engine.evaluate(claims=claims, domain="general")
        assert actions == []

    def test_action_item_has_audit_fields(self) -> None:
        engine = ActionEngine()
        claims = [
            {
                "claim_id": "NAGA-audit",
                "claim_text": "New fee for work permit",
                "category": "FEE_CHANGE",
                "confidence_score": 0.85,
                "affected_visa_types": ["KITAS_E23"],
                "confidence_class": "VERIFIED",
            },
        ]
        actions = engine.evaluate(claims=claims, domain="indonesia")
        assert len(actions) >= 1
        assert actions[0].claim_id == "NAGA-audit"
        assert actions[0].rationale != ""
```

- [ ] **Step 2: Create action_engine.py**

```python
# apps/backend-rag/backend/services/naga/actions/action_engine.py
"""Naga Action Engine — deterministic trigger detection.

Analyzes verified claims and proposes actions based on deterministic
rules (NOT LLM inference). All actions are logged with claim_id and
matched rule for audit trail.

Action types:
  - notify: Telegram alert to team (auto-execute)
  - draft_article: Article draft for intel pipeline (auto-draft, publish=approval)
  - escalate: Write to shared/escalations.json (auto)
  - schedule_followup: Schedule 48h re-research (auto)
"""

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Categories that impact clients
_CLIENT_IMPACT_CATEGORIES: set[str] = {
    "FEE_CHANGE",
    "LEGAL_CHANGE",
    "DOCUMENT_REQUIREMENT",
    "ELIGIBILITY_RULE",
    "PROCESSING_TIME",
    "ENFORCEMENT_ACTION",
}

# Categories that are newsworthy
_NEWSWORTHY_CATEGORIES: set[str] = {
    "LEGAL_CHANGE",
    "POLICY_SIGNAL",
    "FEE_CHANGE",
    "ENFORCEMENT_PATTERN",
}

# Min confidence for actions
_MIN_CONFIDENCE_NOTIFY: float = 0.75
_MIN_CONFIDENCE_DRAFT: float = 0.80


@dataclass
class ActionItem:
    """Proposed action from the engine.

    Attributes:
        action_type: Type of action (notify/draft_article/escalate/schedule_followup).
        claim_id: ID of the triggering claim.
        payload: Action-specific data.
        rationale: Why this action was proposed.
        trust_level: Auto-execute level (notify=auto, draft=auto, publish=approval).
        matched_rule: Which rule triggered this action.
    """

    action_type: str
    claim_id: str
    payload: dict[str, Any]
    rationale: str
    trust_level: str
    matched_rule: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "claim_id": self.claim_id,
            "payload": self.payload,
            "rationale": self.rationale,
            "trust_level": self.trust_level,
            "matched_rule": self.matched_rule,
        }


class ActionEngine:
    """Deterministic action trigger engine.

    Evaluates claims against rule tables and proposes actions.
    No LLM calls — all matching is keyword/category-based.
    """

    def evaluate(
        self,
        claims: list[dict[str, Any]],
        domain: str,
    ) -> list[ActionItem]:
        """Evaluate claims and produce action proposals.

        Args:
            claims: List of claim dicts from the orchestrator.
            domain: Research domain (indonesia/general/hybrid).

        Returns:
            List of ActionItem proposals.
        """
        actions: list[ActionItem] = []

        for claim in claims:
            confidence = claim.get("confidence_score", 0)
            category = claim.get("category", "")
            claim_id = claim.get("claim_id", "")
            claim_text = claim.get("claim_text", "")
            confidence_class = claim.get("confidence_class", "")

            # Rule 1: Client impact notification
            if (
                confidence >= _MIN_CONFIDENCE_NOTIFY
                and category in _CLIENT_IMPACT_CATEGORIES
                and domain in ("indonesia", "hybrid")
            ):
                visa_types = claim.get("affected_visa_types", [])
                actions.append(ActionItem(
                    action_type="notify",
                    claim_id=claim_id,
                    payload={
                        "message": f"[{category}] {claim_text[:200]}",
                        "affected_visa_types": visa_types,
                        "confidence": confidence,
                    },
                    rationale=f"VERIFIED claim in {category} affecting clients",
                    trust_level="auto",
                    matched_rule="client_impact_notify",
                ))

            # Rule 2: Newsworthy article draft
            if (
                confidence >= _MIN_CONFIDENCE_DRAFT
                and category in _NEWSWORTHY_CATEGORIES
                and confidence_class in ("VERIFIED", "LIKELY")
            ):
                actions.append(ActionItem(
                    action_type="draft_article",
                    claim_id=claim_id,
                    payload={
                        "headline_seed": claim_text[:100],
                        "category": category,
                        "domain": domain,
                    },
                    rationale=f"Newsworthy {confidence_class} claim: {category}",
                    trust_level="auto_draft",
                    matched_rule="newsworthy_draft",
                ))

            # Rule 3: Contested claim escalation
            if confidence_class == "CONTESTED":
                actions.append(ActionItem(
                    action_type="escalate",
                    claim_id=claim_id,
                    payload={
                        "reason": f"Contested claim needs human review: {claim_text[:200]}",
                        "resolution_hint": claim.get("resolution_hint", ""),
                    },
                    rationale="Contested claim requiring human judgment",
                    trust_level="auto",
                    matched_rule="contested_escalate",
                ))

        logger.info(
            "ActionEngine: %d actions from %d claims (domain=%s)",
            len(actions),
            len(claims),
            domain,
        )
        return actions
```

- [ ] **Step 3: Create **init**.py**

```python
# apps/backend-rag/backend/services/naga/actions/__init__.py
"""Naga Action Engine: deterministic triggers from verified claims."""
```

- [ ] **Step 4: Run test**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/naga/test_action_engine.py -v
# Expected: 5 passed
```

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/services/naga/actions/ \
        apps/backend-rag/backend/tests/services/naga/test_action_engine.py
git commit -m "feat(naga): add Action Engine with deterministic triggers + audit trail"
```

---

### Task 19: End-to-End Integration Test

**Files:**

- Create: `apps/backend-rag/backend/tests/services/naga/test_integration.py`

- [ ] **Step 1: Write the integration test**

```python
# apps/backend-rag/backend/tests/services/naga/test_integration.py
"""End-to-end integration tests for Naga research engine.

Tests the full pipeline: Gateway → Orchestrator → Search → Evaluate → Synthesize.
All external services are mocked (Exa, Brave, Gemini, Anthropic).
"""

import json
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.naga.gateway import classify_query, GatewayResult
from backend.services.naga.orchestrator import NagaOrchestrator, NagaResearchState
from backend.services.naga.search_agents.base import SearchResult


@pytest.fixture
def mock_search_results() -> list[SearchResult]:
    return [
        SearchResult(
            url="https://imigrasi.go.id/kitas-e23",
            title="KITAS E23 Official Requirements",
            content=(
                "Berdasarkan Peraturan Pemerintah Nomor 28 Tahun 2025 Pasal 45, "
                "KITAS E23 requires an approved RPTKA from the Ministry of Manpower. "
                "The PNBP fee is Rp 3,500,000. Processing time is 5 working days."
            ),
            source_type="gov",
            agent_name="exa",
            domain="imigrasi.go.id",
        ),
        SearchResult(
            url="https://thejakartapost.com/immigration-update",
            title="New Immigration Rules 2026",
            content=(
                "The Indonesian government has updated KITAS requirements. "
                "Digital nomad visa E33G now available for remote workers."
            ),
            source_type="major_news",
            agent_name="brave",
            domain="thejakartapost.com",
        ),
    ]


class TestGatewayIntegration:
    """Test gateway → orchestrator handoff."""

    def test_indonesia_query_classified_correctly(self) -> None:
        result = classify_query("Apa persyaratan KITAS E23?", channel="api")
        assert result.domain == "indonesia"
        assert result.tier in ("flash", "deep", "exhaustive")
        assert result.ttl_seconds > 0

    def test_general_query_classified_correctly(self) -> None:
        result = classify_query("Compare React and Vue frameworks", channel="api")
        assert result.domain == "general"


class TestOrchestratorIntegration:
    """Test full orchestrator flow with mocked externals."""

    @pytest.mark.asyncio
    async def test_flash_research_produces_report(self, mock_search_results: list[SearchResult]) -> None:
        """Flash tier: search → evaluate → synthesize (1 iteration, no Gemini)."""

        with patch(
            "backend.services.naga.orchestrator.ExaSearchAgent"
        ) as MockExa, patch(
            "backend.services.naga.orchestrator.BraveSearchAgent"
        ) as MockBrave, patch(
            "backend.services.naga.orchestrator.IndonesiaDomainAgent"
        ) as MockDomain, patch(
            "backend.services.naga.synthesis.report_writer.ReportWriter._generate_report",
            new_callable=AsyncMock,
            return_value="## KITAS E23\n\nRequires RPTKA. Fee: Rp 3.5M. [1]",
        ):
            # Mock search agents
            mock_exa = AsyncMock()
            mock_exa.search.return_value = [mock_search_results[0]]
            MockExa.return_value = mock_exa

            mock_brave = AsyncMock()
            mock_brave.search.return_value = [mock_search_results[1]]
            MockBrave.return_value = mock_brave

            mock_domain = AsyncMock()
            mock_domain.search.return_value = []
            MockDomain.return_value = mock_domain

            orchestrator = NagaOrchestrator()
            gateway = GatewayResult(tier="flash", domain="indonesia", mode="oneshot", ttl_seconds=15)

            result = await orchestrator.research(
                query="KITAS E23 requirements",
                gateway=gateway,
                channel="api",
            )

        assert "report_markdown" in result
        assert len(result["report_markdown"]) > 0
        assert result.get("iteration", 0) >= 1

    @pytest.mark.asyncio
    async def test_error_handling_produces_partial_report(self) -> None:
        """When all search agents fail, still produces error report."""

        with patch(
            "backend.services.naga.orchestrator.ExaSearchAgent"
        ) as MockExa, patch(
            "backend.services.naga.orchestrator.BraveSearchAgent"
        ) as MockBrave, patch(
            "backend.services.naga.orchestrator.IndonesiaDomainAgent"
        ) as MockDomain, patch(
            "backend.services.naga.synthesis.report_writer.ReportWriter._generate_report",
            new_callable=AsyncMock,
            return_value="## Research Report\n\nNo relevant sources found.",
        ):
            mock_exa = AsyncMock()
            mock_exa.search.side_effect = Exception("Exa API down")
            MockExa.return_value = mock_exa

            mock_brave = AsyncMock()
            mock_brave.search.side_effect = Exception("Brave API down")
            MockBrave.return_value = mock_brave

            mock_domain = AsyncMock()
            mock_domain.search.return_value = []
            MockDomain.return_value = mock_domain

            orchestrator = NagaOrchestrator()
            gateway = GatewayResult(tier="flash", domain="general", mode="oneshot", ttl_seconds=15)

            result = await orchestrator.research(
                query="test query",
                gateway=gateway,
            )

        # Should not crash
        assert "report_markdown" in result
        assert len(result.get("errors", [])) >= 1


class TestClaimsIntegration:
    """Test claim extraction from evidence."""

    def test_claims_extracted_from_regulatory_text(self) -> None:
        from backend.core.claims.extractor import extract_claims_from_response

        text = (
            "Berdasarkan Peraturan Pemerintah Nomor 28 Tahun 2025 Pasal 45, "
            "biaya PNBP untuk KITAS E23 ditetapkan sebesar Rp 3,500,000 yang "
            "berlaku sejak tanggal diundangkan pada Maret 2026."
        )
        claims = extract_claims_from_response(
            response_text=text,
            source_ids=["https://imigrasi.go.id"],
            query_cluster="NAGA",
            claim_id_prefix="NAGA",
        )
        assert len(claims) >= 1
        assert claims[0].claim_id.startswith("NAGA-")
        assert claims[0].confidence_score > 0.5


class TestActionEngineIntegration:
    """Test action generation from claims."""

    def test_verified_fee_change_triggers_notify(self) -> None:
        from backend.services.naga.actions.action_engine import ActionEngine

        engine = ActionEngine()
        claims = [
            {
                "claim_id": "NAGA-int-test",
                "claim_text": "KITAS E23 PNBP fee raised to Rp 5,000,000",
                "category": "FEE_CHANGE",
                "confidence_score": 0.90,
                "confidence_class": "VERIFIED",
                "affected_visa_types": ["KITAS_E23"],
            },
        ]
        actions = engine.evaluate(claims=claims, domain="indonesia")
        action_types = [a.action_type for a in actions]
        assert "notify" in action_types
        assert "draft_article" in action_types  # Fee change is also newsworthy
```

- [ ] **Step 2: Create **init**.py for test package**

```python
# apps/backend-rag/backend/tests/services/naga/__init__.py
"""Naga test package."""
```

- [ ] **Step 3: Run integration test**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/naga/test_integration.py -v
# Expected: 5 passed
```

- [ ] **Step 4: Run ALL Naga tests**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/naga/ backend/tests/core/test_claims.py backend/tests/migrations/test_migration_079_naga.py backend/tests/routers/test_naga.py -v --tb=short
# Expected: ~65 tests passed
```

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/tests/services/naga/test_integration.py \
        apps/backend-rag/backend/tests/services/naga/__init__.py
git commit -m "feat(naga): add end-to-end integration tests"
```

---

## Post-Implementation Checklist

After all 19 tasks are complete:

- [ ] **Verify import chain**

```bash
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.services.naga.orchestrator import NagaOrchestrator; print('OK')"
python -c "from backend.core.claims.extractor import extract_claims_from_response; print('OK')"
python -c "from backend.app.routers.naga import router; print('OK')"
```

- [ ] **Run full test suite (no regressions)**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/rag/test_confidence.py backend/tests/services/rag/test_kg_langgraph.py -q --tb=no
# Expected: existing tests still pass
```

- [ ] **Final commit with all inits**

```bash
git add apps/backend-rag/backend/services/naga/ \
        apps/backend-rag/backend/core/claims/ \
        apps/backend-rag/backend/app/routers/naga.py \
        apps/backend-rag/backend/migrations/migration_079_naga_tables.py
git commit -m "feat(naga): complete Naga v1.0 — agentic research engine with LangGraph"
```

---

## Summary: What Ships in v1.0

| Component                                      | Status | Notes                              |
| ---------------------------------------------- | ------ | ---------------------------------- |
| DB Migration 079 (5 tables)                    | v1.0   | All tables + indexes               |
| Shared Claims Library (core/claims/)           | v1.0   | Naga + NLM use same ontology       |
| Gateway Classifier                             | v1.0   | Rule-based (Haiku deferred)        |
| 3 Search Agents (Exa, Brave, Indonesia Domain) | v1.0   | Academic deferred to v1.1          |
| Source Scorer                                  | v1.0   | Configurable weights               |
| CRAG-Light                                     | v1.0   | Haiku + heuristic fallback         |
| Gemini Bulk Reader (Pointer State)             | v1.0   | evidence_map to file, URI in state |
| Convergence Detector                           | v1.0   | Adversarial = placeholder          |
| Report Writer (3 tiers)                        | v1.0   | flash/deep/exhaustive              |
| LangGraph Orchestrator                         | v1.0   | StateGraph + AsyncPostgresSaver    |
| FastAPI Router (3 endpoints)                   | v1.0   | /research, /session, /claims       |
| MCP Tools (2 tools)                            | v1.0   | HTTP \_call() only                 |
| Action Engine                                  | v1.0   | Deterministic rules + audit        |
| Human Review Gate                              | v1.0   | review_status mandatory on claims  |
| Integration Tests                              | v1.0   | ~65 tests across all modules       |

## Deferred to v1.1

| Feature                                               | Reason                                |
| ----------------------------------------------------- | ------------------------------------- |
| Academic Agent (Semantic Scholar, arXiv)              | Reduce v1.0 scope                     |
| Active adversarial search (Opus contradiction finder) | Need v1.0 baseline data first         |
| Session persistence to DB                             | Router placeholder ready              |
| Conversational mode                                   | Gateway classifies oneshot only       |
| NLM claim_extractor wrapper migration                 | Backward compat after v1.0 validation |
| Drive archival of evidence_map                        | Local disk first, Drive in v1.1       |
| Qdrant ingest of research results                     | After claims DB validates quality     |
| Audio briefing via NLM studio                         | After report writer stabilizes        |
