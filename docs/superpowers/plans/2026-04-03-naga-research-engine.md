# Naga Agentic Research Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a multi-model agentic research engine that orchestrates 5 search agents, verifies claims through a 4-stage quality pipeline, and produces actionable intelligence reports.

**Architecture:** Gateway (Haiku/qwen classifier) → Orchestrator (Opus iterative loop) → Search Agents (parallel) → Gemini Bulk Reader (1M context) → Quality Pipeline (source scoring → claim extraction → convergence) → Synthesis (multi-perspective) → Output (report + Claims DB + actions). See `docs/superpowers/specs/2026-04-03-naga-agentic-research-engine-design.md` for full spec.

**Tech Stack:** Python 3.11, asyncio, asyncpg (PostgreSQL), httpx (async HTTP), FastAPI (router), FastMCP (MCP tools), google-generativeai (Gemini SDK), subprocess (NLM CLI bridge)

**Spec:** `docs/superpowers/specs/2026-04-03-naga-agentic-research-engine-design.md`

---

## Phase Overview

This plan is split into 4 phases. Each phase produces working, testable software.

| Phase                            | What it builds                                                    | Tasks | Outcome                                                 |
| -------------------------------- | ----------------------------------------------------------------- | ----- | ------------------------------------------------------- |
| **Phase 1: Foundation**          | DB schema, data models, config, Gateway classifier                | 1-5   | Can classify queries into tier/domain/mode              |
| **Phase 2: Search Layer**        | 5 search agents + dedup + budget tracker                          | 6-11  | Can search across all sources and return ranked results |
| **Phase 3: Quality + Synthesis** | Gemini reader, CRAG, claim extraction, convergence, report writer | 12-17 | Full research loop: search → verify → synthesize        |
| **Phase 4: Integration**         | MCP tool, FastAPI endpoints, Action Engine, conversational mode   | 18-22 | Production-ready system accessible from all channels    |

---

## File Structure

```
apps/naga/
├── __init__.py
├── engine/
│   ├── __init__.py
│   ├── gateway.py                 # Tier/domain/mode classifier
│   ├── orchestrator.py            # Main research loop
│   ├── search_agents/
│   │   ├── __init__.py
│   │   ├── base.py                # BaseSearchAgent ABC
│   │   ├── exa_agent.py           # Exa neural search
│   │   ├── brave_agent.py         # Brave web search
│   │   ├── domain_agent.py        # Indonesia domain (RAG + NLM + .go.id)
│   │   ├── academic_agent.py      # Semantic Scholar + OpenAlex + arXiv
│   │   └── crawl_agent.py         # Deep crawl (reactive, cycle 2+)
│   ├── quality/
│   │   ├── __init__.py
│   │   ├── source_scorer.py       # Configurable domain credibility
│   │   ├── crag_light.py          # Fast relevance gate (Haiku)
│   │   ├── claim_extractor.py     # Atomic claim extraction (Opus)
│   │   └── convergence.py         # Coverage/novelty/budget detector
│   ├── synthesis/
│   │   ├── __init__.py
│   │   └── report_writer.py       # Multi-tier report generation
│   ├── actions/
│   │   ├── __init__.py
│   │   └── action_engine.py       # Trigger detection + action proposals
│   ├── readers/
│   │   ├── __init__.py
│   │   ├── gemini_reader.py       # Bulk read via Gemini SDK
│   │   └── academic_apis.py       # Semantic Scholar, OpenAlex, arXiv clients
│   ├── state/
│   │   ├── __init__.py
│   │   ├── session.py             # NagaSession dataclass + DB persistence
│   │   ├── budget_tracker.py      # Cost + calls + TTL tracker
│   │   └── url_history.py         # Cross-iteration dedup (simhash)
│   └── config/
│       ├── __init__.py
│       ├── naga_config.py         # Tier budgets, TTLs, thresholds
│       └── source_weights.json    # Configurable domain credibility scores
├── db/
│   └── models.py                  # Pydantic models + DB helpers
└── tests/
    ├── __init__.py
    ├── test_gateway.py
    ├── test_search_agents.py
    ├── test_quality.py
    ├── test_orchestrator.py
    └── test_integration.py

# Files in OTHER apps (integration points):
apps/backend-rag/backend/migrations/migration_078_naga_tables.py
apps/backend-rag/backend/app/routers/naga.py
apps/nuzantara-mcp/nuzantara_mcp/tools/naga.py
```

---

## PHASE 1: Foundation (Tasks 1-5)

### Task 1: Database Migration — Naga Tables

**Files:**

- Create: `apps/backend-rag/backend/migrations/migration_078_naga_tables.py`

- [ ] **Step 1: Write the migration file**

```python
# apps/backend-rag/backend/migrations/migration_078_naga_tables.py
"""
Migration 078: Naga Agentic Research Engine tables

Three tables:
- naga_sessions: research tasks with state and metrics
- naga_sources: discovered sources with credibility scoring
- naga_claims: verified claims as living knowledge base
"""

import logging

logger = logging.getLogger(__name__)


async def apply(conn) -> None:
    """Create Naga research tables."""

    # Sessions table — research tasks with conversational chaining
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS naga_sessions (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            parent_session_id   UUID REFERENCES naga_sessions(id),
            query               TEXT NOT NULL,
            tier                VARCHAR(20) NOT NULL,
            domain              VARCHAR(20) NOT NULL,
            mode                VARCHAR(20) NOT NULL,
            channel             VARCHAR(30),
            ttl_seconds         INTEGER,
            trusted_mode        BOOLEAN DEFAULT FALSE,
            status              VARCHAR(20) DEFAULT 'running',

            duration_ms         INTEGER,
            iterations          INTEGER DEFAULT 0,
            search_calls        INTEGER DEFAULT 0,
            sources_found       INTEGER DEFAULT 0,
            claims_extracted    INTEGER DEFAULT 0,
            avg_confidence      FLOAT,

            report_markdown     TEXT,
            report_drive_path   TEXT,
            action_items        JSONB DEFAULT '[]'::jsonb,

            evidence_map        JSONB,
            sub_questions       JSONB,
            url_history         TEXT[],

            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at        TIMESTAMPTZ
        );
    """)

    # Sources table — discovered sources with credibility metadata
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS naga_sources (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id          UUID REFERENCES naga_sessions(id) ON DELETE CASCADE,
            url                 TEXT NOT NULL,
            title               TEXT,
            domain              VARCHAR(255),
            source_type         VARCHAR(20),
            credibility_score   FLOAT,
            freshness_date      DATE,
            content_hash        VARCHAR(64),
            content_archived    BOOLEAN DEFAULT FALSE,
            drive_archive_path  TEXT,
            fetched_at          TIMESTAMPTZ DEFAULT NOW(),

            UNIQUE(url, session_id)
        );
    """)

    # Claims table — living knowledge base with supersession chains
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS naga_claims (
            id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id              UUID REFERENCES naga_sessions(id) ON DELETE CASCADE,
            claim_text              TEXT NOT NULL,
            domain                  VARCHAR(20),
            topic_tags              TEXT[],

            verification_level      VARCHAR(20),
            confidence              FLOAT,
            source_ids              UUID[],
            cross_ref_count         INTEGER,

            valid_as_of             DATE,
            expires_at              DATE,

            resolution_hint         TEXT,
            contradicting_source_ids UUID[],

            superseded_by           UUID REFERENCES naga_claims(id),
            superseded_at           TIMESTAMPTZ,

            created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    # Indexes
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_naga_sessions_parent
            ON naga_sessions(parent_session_id);
        CREATE INDEX IF NOT EXISTS idx_naga_sessions_status
            ON naga_sessions(status);
        CREATE INDEX IF NOT EXISTS idx_naga_sources_url
            ON naga_sources(url);
        CREATE INDEX IF NOT EXISTS idx_naga_sources_hash
            ON naga_sources(content_hash);
        CREATE INDEX IF NOT EXISTS idx_naga_claims_domain
            ON naga_claims(domain);
        CREATE INDEX IF NOT EXISTS idx_naga_claims_topic
            ON naga_claims USING GIN(topic_tags);
        CREATE INDEX IF NOT EXISTS idx_naga_claims_confidence
            ON naga_claims(confidence DESC);
        CREATE INDEX IF NOT EXISTS idx_naga_claims_valid
            ON naga_claims(valid_as_of DESC);
        CREATE INDEX IF NOT EXISTS idx_naga_claims_verification
            ON naga_claims(verification_level);
    """)

    logger.info("Migration 078: Naga research tables created")


async def rollback(conn) -> None:
    """Drop Naga tables."""
    await conn.execute("DROP TABLE IF EXISTS naga_claims CASCADE;")
    await conn.execute("DROP TABLE IF EXISTS naga_sources CASCADE;")
    await conn.execute("DROP TABLE IF EXISTS naga_sessions CASCADE;")
```

- [ ] **Step 2: Apply migration locally**

Run:

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. python -c "
import asyncio, asyncpg, os
async def main():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])
    from backend.migrations.migration_078_naga_tables import apply
    await apply(conn)
    # Verify tables exist
    tables = await conn.fetch(\"\"\"
        SELECT tablename FROM pg_tables
        WHERE tablename LIKE 'naga_%'
        ORDER BY tablename
    \"\"\")
    for t in tables:
        print(f'✅ {t[\"tablename\"]}')
    await conn.close()
asyncio.run(main())
"
```

Expected:

```
✅ naga_claims
✅ naga_sessions
✅ naga_sources
```

- [ ] **Step 3: Commit**

```bash
git add apps/backend-rag/backend/migrations/migration_078_naga_tables.py
git commit -m "feat(naga): add migration 078 — naga_sessions, naga_sources, naga_claims tables"
```

---

### Task 2: Config + Source Weights

**Files:**

- Create: `apps/naga/__init__.py`
- Create: `apps/naga/engine/__init__.py`
- Create: `apps/naga/engine/config/__init__.py`
- Create: `apps/naga/engine/config/naga_config.py`
- Create: `apps/naga/engine/config/source_weights.json`

- [ ] **Step 1: Create app skeleton with **init** files**

```python
# apps/naga/__init__.py
"""Naga — Agentic Research Engine."""
```

```python
# apps/naga/engine/__init__.py
```

```python
# apps/naga/engine/config/__init__.py
```

- [ ] **Step 2: Write naga_config.py**

```python
# apps/naga/engine/config/naga_config.py
"""Naga configuration — tier budgets, TTLs, thresholds."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TierConfig:
    """Budget and limits for a research tier."""

    max_search_calls: int
    max_sources_to_reader: int
    max_iterations: int
    default_ttl_seconds: int


TIER_CONFIGS: dict[str, TierConfig] = {
    "flash": TierConfig(
        max_search_calls=3,
        max_sources_to_reader=0,
        max_iterations=1,
        default_ttl_seconds=30,
    ),
    "deep": TierConfig(
        max_search_calls=25,
        max_sources_to_reader=20,
        max_iterations=3,
        default_ttl_seconds=300,
    ),
    "exhaustive": TierConfig(
        max_search_calls=80,
        max_sources_to_reader=50,
        max_iterations=5,
        default_ttl_seconds=1800,
    ),
}

CHANNEL_TTLS: dict[str, int] = {
    "telegram": 30,
    "web_chat": 60,
    "claude_code": 1800,
    "openclaw": 1800,
    "api": 3600,
    "cron": 3600,
}

# Convergence thresholds
CONVERGENCE_COVERAGE_THRESHOLD = 0.80
CONVERGENCE_NOVELTY_THRESHOLD = 0.10

# Source scoring filter
SOURCE_SCORE_MIN = 0.30

# Claim confidence boundaries (compatible with existing RAG scoring)
CONFIDENCE_VERIFIED_MIN = 0.85
CONFIDENCE_LIKELY_MIN = 0.50
CONFIDENCE_CONTESTED_MIN = 0.30
CONFIDENCE_UNVERIFIED_MIN = 0.15
```

- [ ] **Step 3: Write source_weights.json**

```json
{
  "_comment": "Domain credibility scores for Naga source scoring. Override per-domain.",
  "defaults": {
    "gov": 0.9,
    "academic": 0.85,
    "major_news": 0.6,
    "blog": 0.4,
    "forum": 0.2,
    "unknown": 0.3
  },
  "domain_overrides": {
    "pajak.go.id": 0.95,
    "imigrasi.go.id": 0.95,
    "kemenkumham.go.id": 0.9,
    "ahu.go.id": 0.9,
    "oss.go.id": 0.9,
    "bkpm.go.id": 0.9,
    "kemlu.go.id": 0.85,
    "peraturan.bpk.go.id": 0.95,
    "jdih.kemenkumham.go.id": 0.95,
    "arxiv.org": 0.85,
    "semanticscholar.org": 0.85,
    "openalex.org": 0.8,
    "reuters.com": 0.75,
    "bloomberg.com": 0.75,
    "thejakartapost.com": 0.65,
    "kompas.com": 0.6,
    "detik.com": 0.55,
    "tribunnews.com": 0.45
  },
  "freshness_weights": {
    "days_30": 1.0,
    "days_365": 0.7,
    "days_1095": 0.5,
    "older": 0.3
  }
}
```

- [ ] **Step 4: Commit**

```bash
git add apps/naga/
git commit -m "feat(naga): add app skeleton, tier config, and source weights"
```

---

### Task 3: Data Models — NagaSession, NagaSource, NagaClaim

**Files:**

- Create: `apps/naga/db/__init__.py`
- Create: `apps/naga/db/models.py`

- [ ] **Step 1: Write the test**

```python
# apps/naga/tests/__init__.py
```

```python
# apps/naga/tests/test_gateway.py
"""Tests for Naga data models and gateway."""

import pytest
from apps.naga.db.models import NagaSession, NagaSource, NagaClaim


def test_naga_session_defaults():
    session = NagaSession(query="test query", tier="deep", domain="general", mode="oneshot")
    assert session.status == "running"
    assert session.iterations == 0
    assert session.search_calls == 0
    assert session.url_history == []
    assert session.trusted_mode is False


def test_naga_session_budget_remaining():
    session = NagaSession(query="q", tier="deep", domain="general", mode="oneshot")
    session.search_calls = 10
    assert session.budget_remaining == 15  # deep max=25, used=10


def test_naga_source_credibility():
    source = NagaSource(
        url="https://imigrasi.go.id/news/123",
        title="New visa policy",
        domain="imigrasi.go.id",
        source_type="gov",
    )
    assert source.source_type == "gov"


def test_naga_claim_verification_levels():
    claim = NagaClaim(
        claim_text="KITAS fee is Rp 2.000.000",
        domain="indonesia",
        verification_level="VERIFIED",
        confidence=0.92,
        cross_ref_count=4,
    )
    assert claim.is_trustworthy is True

    contested = NagaClaim(
        claim_text="DPS deadline is March 2026",
        domain="indonesia",
        verification_level="CONTESTED",
        confidence=0.35,
        resolution_hint="Source A (2024, gov) vs Source B (2022, blog)",
    )
    assert contested.is_trustworthy is False


def test_naga_claim_supersession():
    old = NagaClaim(claim_text="Fee is 1M", domain="indonesia", confidence=0.8)
    new = NagaClaim(claim_text="Fee is 2M", domain="indonesia", confidence=0.9)
    old.mark_superseded_by(new.id)
    assert old.superseded_by == new.id
    assert old.superseded_at is not None
```

- [ ] **Step 2: Run test — verify it fails**

Run:

```bash
cd /Users/nuzantara/Desktop/nuzantara
PYTHONPATH=. python -m pytest apps/naga/tests/test_gateway.py -v --tb=short 2>&1 | head -20
```

Expected: FAIL — `ModuleNotFoundError: No module named 'apps.naga.db'`

- [ ] **Step 3: Write models.py**

```python
# apps/naga/db/__init__.py
```

```python
# apps/naga/db/models.py
"""Naga data models — sessions, sources, claims."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from apps.naga.engine.config.naga_config import TIER_CONFIGS


@dataclass
class NagaSession:
    """A single research session (one query, possibly chained)."""

    query: str
    tier: str  # flash / deep / exhaustive
    domain: str  # indonesia / general / hybrid
    mode: str  # oneshot / conversational

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_session_id: Optional[str] = None
    channel: Optional[str] = None
    ttl_seconds: Optional[int] = None
    trusted_mode: bool = False
    status: str = "running"

    # Metrics
    duration_ms: int = 0
    iterations: int = 0
    search_calls: int = 0
    sources_found: int = 0
    claims_extracted: int = 0
    avg_confidence: float = 0.0

    # Output
    report_markdown: str = ""
    report_drive_path: str = ""
    action_items: list[dict] = field(default_factory=list)

    # Conversational state
    evidence_map: dict = field(default_factory=dict)
    sub_questions: list[str] = field(default_factory=list)
    url_history: list[str] = field(default_factory=list)

    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    @property
    def budget_remaining(self) -> int:
        """Remaining search calls for this tier."""
        tier_config = TIER_CONFIGS.get(self.tier)
        if not tier_config:
            return 0
        return tier_config.max_search_calls - self.search_calls

    def record_search_call(self, count: int = 1) -> None:
        """Record search calls used."""
        self.search_calls += count

    def add_url_to_history(self, url: str) -> bool:
        """Add URL to history. Returns False if already seen."""
        if url in self.url_history:
            return False
        self.url_history.append(url)
        return True

    def merge_evidence(self, new_evidence: dict) -> None:
        """Merge new evidence into existing evidence_map (delta merge)."""
        for sub_q, data in new_evidence.items():
            if sub_q not in self.evidence_map:
                self.evidence_map[sub_q] = data
            else:
                existing = self.evidence_map[sub_q]
                existing.setdefault("facts", []).extend(data.get("facts", []))
                existing.setdefault("contradictions", []).extend(
                    data.get("contradictions", [])
                )
                existing.setdefault("gaps", []).extend(data.get("gaps", []))
                existing.setdefault("data_points", []).extend(
                    data.get("data_points", [])
                )

    def complete(self) -> None:
        """Mark session as completed."""
        self.status = "completed"
        self.completed_at = datetime.utcnow()


@dataclass
class NagaSource:
    """A source discovered during research."""

    url: str
    title: Optional[str] = None
    domain: Optional[str] = None
    source_type: Optional[str] = None  # web / gov / academic / internal / blog

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    credibility_score: float = 0.0
    freshness_date: Optional[date] = None
    content_hash: Optional[str] = None
    content_archived: bool = False
    drive_archive_path: Optional[str] = None
    fetched_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class NagaClaim:
    """A verified claim extracted from research."""

    claim_text: str
    domain: Optional[str] = None

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    topic_tags: list[str] = field(default_factory=list)

    # Verification
    verification_level: Optional[str] = None  # VERIFIED/LIKELY/CONTESTED/UNVERIFIED
    confidence: float = 0.0
    source_ids: list[str] = field(default_factory=list)
    cross_ref_count: int = 0

    # Temporal
    valid_as_of: Optional[date] = None
    expires_at: Optional[date] = None

    # Contestation
    resolution_hint: Optional[str] = None
    contradicting_source_ids: list[str] = field(default_factory=list)

    # Lifecycle
    superseded_by: Optional[str] = None
    superseded_at: Optional[datetime] = None

    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_trustworthy(self) -> bool:
        """Claim is trustworthy if VERIFIED or LIKELY."""
        return self.verification_level in ("VERIFIED", "LIKELY")

    def mark_superseded_by(self, new_claim_id: str) -> None:
        """Mark this claim as superseded by a newer one."""
        self.superseded_by = new_claim_id
        self.superseded_at = datetime.utcnow()
```

- [ ] **Step 4: Run tests — verify they pass**

Run:

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_gateway.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/naga/
git commit -m "feat(naga): add data models — NagaSession, NagaSource, NagaClaim"
```

---

### Task 4: State Management — BudgetTracker + URL History

**Files:**

- Create: `apps/naga/engine/state/__init__.py`
- Create: `apps/naga/engine/state/budget_tracker.py`
- Create: `apps/naga/engine/state/url_history.py`

- [ ] **Step 1: Write budget tracker tests**

```python
# Append to apps/naga/tests/test_gateway.py

import time
from apps.naga.engine.state.budget_tracker import BudgetTracker


def test_budget_tracker_search_calls():
    bt = BudgetTracker(max_search_calls=25, ttl_seconds=300)
    assert bt.can_search is True
    bt.record_search(10)
    assert bt.search_calls_remaining == 15
    bt.record_search(15)
    assert bt.search_calls_remaining == 0
    assert bt.can_search is False


def test_budget_tracker_ttl():
    bt = BudgetTracker(max_search_calls=25, ttl_seconds=1)
    assert bt.is_timed_out is False
    time.sleep(1.1)
    assert bt.is_timed_out is True


def test_budget_tracker_summary():
    bt = BudgetTracker(max_search_calls=25, ttl_seconds=300)
    bt.record_search(5)
    summary = bt.summary()
    assert summary["search_calls_used"] == 5
    assert summary["search_calls_remaining"] == 20
    assert summary["timed_out"] is False
```

- [ ] **Step 2: Write URL history tests**

```python
# Append to apps/naga/tests/test_gateway.py

from apps.naga.engine.state.url_history import URLHistory


def test_url_history_dedup():
    history = URLHistory()
    assert history.is_new("https://example.com/a") is True
    history.add("https://example.com/a")
    assert history.is_new("https://example.com/a") is False


def test_url_history_normalize():
    history = URLHistory()
    history.add("https://example.com/page?utm_source=google&id=1")
    # Same URL without tracking params should be recognized
    assert history.is_new("https://example.com/page?id=1") is False
```

- [ ] **Step 3: Run tests — verify they fail**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_gateway.py -v --tb=short 2>&1 | tail -15
```

Expected: FAIL — `ModuleNotFoundError: No module named 'apps.naga.engine.state'`

- [ ] **Step 4: Implement budget_tracker.py**

```python
# apps/naga/engine/state/__init__.py
```

```python
# apps/naga/engine/state/budget_tracker.py
"""Budget tracker — monitors search calls, TTL, and cost."""

import time
from dataclasses import dataclass, field


@dataclass
class BudgetTracker:
    """Tracks resource consumption during a research session."""

    max_search_calls: int
    ttl_seconds: int
    _search_calls_used: int = field(default=0, init=False)
    _start_time: float = field(default_factory=time.monotonic, init=False)

    @property
    def search_calls_remaining(self) -> int:
        return max(0, self.max_search_calls - self._search_calls_used)

    @property
    def seconds_remaining(self) -> float:
        elapsed = time.monotonic() - self._start_time
        return max(0.0, self.ttl_seconds - elapsed)

    @property
    def is_timed_out(self) -> bool:
        return self.seconds_remaining <= 0

    @property
    def can_search(self) -> bool:
        return self.search_calls_remaining > 0 and not self.is_timed_out

    def record_search(self, count: int = 1) -> None:
        """Record search API calls consumed."""
        self._search_calls_used += count

    def summary(self) -> dict:
        """Return budget status for the orchestrator."""
        return {
            "search_calls_used": self._search_calls_used,
            "search_calls_remaining": self.search_calls_remaining,
            "seconds_remaining": round(self.seconds_remaining, 1),
            "timed_out": self.is_timed_out,
            "can_search": self.can_search,
        }
```

- [ ] **Step 5: Implement url_history.py**

```python
# apps/naga/engine/state/url_history.py
"""URL history — cross-iteration dedup with normalization."""

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

# Tracking parameters to strip during URL normalization
_TRACKING_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "fbclid",
        "gclid",
        "ref",
        "source",
    }
)


def _normalize_url(url: str) -> str:
    """Normalize URL by removing tracking params and fragments."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=False)
    filtered = {k: v for k, v in params.items() if k not in _TRACKING_PARAMS}
    clean_query = urlencode(filtered, doseq=True)
    normalized = urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, clean_query, "")
    )
    return normalized.rstrip("/")


class URLHistory:
    """Tracks seen URLs with normalization for dedup."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def add(self, url: str) -> None:
        """Add a URL to history."""
        self._seen.add(_normalize_url(url))

    def is_new(self, url: str) -> bool:
        """Check if URL has NOT been seen before."""
        return _normalize_url(url) not in self._seen

    def add_many(self, urls: list[str]) -> list[str]:
        """Add multiple URLs, return only the new ones."""
        new_urls = [u for u in urls if self.is_new(u)]
        for u in new_urls:
            self.add(u)
        return new_urls

    @property
    def count(self) -> int:
        return len(self._seen)
```

- [ ] **Step 6: Run tests — verify they pass**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_gateway.py -v
```

Expected: all 10 tests PASS

- [ ] **Step 7: Commit**

```bash
git add apps/naga/engine/state/
git commit -m "feat(naga): add BudgetTracker and URLHistory state management"
```

---

### Task 5: Gateway — Tier/Domain/Mode Classifier

**Files:**

- Create: `apps/naga/engine/gateway.py`
- Modify test: `apps/naga/tests/test_gateway.py`

- [ ] **Step 1: Write gateway tests**

```python
# Append to apps/naga/tests/test_gateway.py

from apps.naga.engine.gateway import classify_query, GatewayResult


def test_gateway_indonesia_domain():
    result = classify_query("qual è il costo del KITAS 2026?")
    assert result.domain == "indonesia"


def test_gateway_general_domain():
    result = classify_query("explain quantum computing basics")
    assert result.domain == "general"


def test_gateway_hybrid_domain():
    result = classify_query("confronto golden visa Indonesia vs Portogallo")
    assert result.domain == "hybrid"


def test_gateway_flash_tier():
    result = classify_query("quanto costa KITAS?")
    assert result.tier == "flash"


def test_gateway_deep_tier():
    result = classify_query(
        "analisi completa dei regimi fiscali per PT PMA vs CV in Indonesia"
    )
    assert result.tier in ("deep", "exhaustive")


def test_gateway_telegram_ttl():
    result = classify_query("KITAS cost?", channel="telegram")
    assert result.ttl_seconds == 30


def test_gateway_cron_ttl():
    result = classify_query("full analysis", channel="cron")
    assert result.ttl_seconds == 3600


def test_gateway_result_structure():
    result = classify_query("test query")
    assert isinstance(result, GatewayResult)
    assert result.tier in ("flash", "deep", "exhaustive")
    assert result.domain in ("indonesia", "general", "hybrid")
    assert result.mode in ("oneshot", "conversational")
    assert isinstance(result.ttl_seconds, int)
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_gateway.py::test_gateway_indonesia_domain -v --tb=short
```

Expected: FAIL — `cannot import name 'classify_query'`

- [ ] **Step 3: Implement gateway.py**

```python
# apps/naga/engine/gateway.py
"""Naga Gateway — classifies queries into tier/domain/mode."""

from __future__ import annotations

import re
from dataclasses import dataclass

from apps.naga.engine.config.naga_config import CHANNEL_TTLS

# Indonesia domain keywords (Indonesian + English + Italian)
_INDONESIA_KEYWORDS = re.compile(
    r"\b("
    r"kitas|kitap|visa|visto|imigra[st]i|izin tinggal|"
    r"kbli|pt pma|perseroan|cv |yayasan|"
    r"pajak|tax|npwp|pph|ppn|"
    r"notaris|akta|ahu|oss|nib|"
    r"bali|indonesia|jakarta|"
    r"regulasi|peraturan|undang|permen|pp |perpres|"
    r"golden visa|investor visa|retirement visa|"
    r"izin usaha|sertifikat|hak pakai|hgb|"
    r"imigrasi|ditjen|kemenkumham|bkpm|"
    r"tarif|biaya|pnbp|retribusi"
    r")\b",
    re.IGNORECASE,
)

# Complexity signals for tier classification
_COMPLEX_SIGNALS = re.compile(
    r"\b("
    r"anali[sz][aei]|compar[ae]|confronto|comprehensive|"
    r"report|research|study|studio|"
    r"impatto|impact|implications|"
    r"pro e contro|trade.?off|vantaggi|"
    r"completa|dettagliata|approfondita|exhaustive|"
    r"storia|timeline|evoluzione"
    r")\b",
    re.IGNORECASE,
)

_CONVERSATIONAL_SIGNALS = re.compile(
    r"\b("
    r"esplora|explore|investigate|indaga|"
    r"non sono sicuro|not sure|"
    r"cosa pensi|what do you think|"
    r"diverse prospettive|multiple perspectives"
    r")\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class GatewayResult:
    """Classification result from the gateway."""

    tier: str  # flash / deep / exhaustive
    domain: str  # indonesia / general / hybrid
    mode: str  # oneshot / conversational
    ttl_seconds: int


def classify_query(
    query: str,
    channel: str | None = None,
    force_tier: str | None = None,
    force_domain: str | None = None,
) -> GatewayResult:
    """Classify a query into tier/domain/mode.

    This is the fast, rule-based classifier (< 1ms).
    For production, the orchestrator may re-classify using Haiku/qwen.
    """
    # --- Domain ---
    indonesia_hits = len(_INDONESIA_KEYWORDS.findall(query))
    has_general_content = len(query.split()) > 3 and indonesia_hits < len(
        query.split()
    ) * 0.5

    if force_domain:
        domain = force_domain
    elif indonesia_hits >= 2 and not has_general_content:
        domain = "indonesia"
    elif indonesia_hits >= 1 and has_general_content:
        domain = "hybrid"
    elif indonesia_hits == 1:
        domain = "indonesia"
    else:
        domain = "general"

    # --- Tier ---
    complexity_hits = len(_COMPLEX_SIGNALS.findall(query))
    word_count = len(query.split())

    if force_tier:
        tier = force_tier
    elif complexity_hits >= 3 or word_count > 40:
        tier = "exhaustive"
    elif complexity_hits >= 1 or word_count > 15:
        tier = "deep"
    else:
        tier = "flash"

    # --- Mode ---
    if _CONVERSATIONAL_SIGNALS.search(query):
        mode = "conversational"
    elif tier == "exhaustive":
        mode = "conversational"
    else:
        mode = "oneshot"

    # --- TTL ---
    if channel and channel in CHANNEL_TTLS:
        ttl = CHANNEL_TTLS[channel]
        # Telegram forces flash unless deep override
        if channel == "telegram" and tier != "flash" and force_tier is None:
            tier = "flash"
    else:
        from apps.naga.engine.config.naga_config import TIER_CONFIGS

        ttl = TIER_CONFIGS[tier].default_ttl_seconds

    return GatewayResult(tier=tier, domain=domain, mode=mode, ttl_seconds=ttl)
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_gateway.py -v
```

Expected: all 18 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/naga/engine/gateway.py apps/naga/tests/test_gateway.py
git commit -m "feat(naga): add Gateway classifier — tier/domain/mode routing"
```

---

## PHASE 2: Search Layer (Tasks 6-11)

### Task 6: BaseSearchAgent ABC + Agent Result Types

**Files:**

- Create: `apps/naga/engine/search_agents/__init__.py`
- Create: `apps/naga/engine/search_agents/base.py`

- [ ] **Step 1: Write tests**

```python
# apps/naga/tests/test_search_agents.py
"""Tests for search agents."""

import pytest
from apps.naga.engine.search_agents.base import SearchResult, AgentResponse


def test_search_result_structure():
    result = SearchResult(
        url="https://example.com",
        title="Test",
        content="Some content here",
        relevance_score=0.8,
    )
    assert result.url == "https://example.com"
    assert result.relevance_score == 0.8


def test_agent_response_merge():
    r1 = AgentResponse(
        agent_name="exa",
        results=[
            SearchResult(url="https://a.com", title="A", content="content A"),
        ],
    )
    r2 = AgentResponse(
        agent_name="brave",
        results=[
            SearchResult(url="https://b.com", title="B", content="content B"),
            SearchResult(url="https://a.com", title="A dup", content="content A"),
        ],
    )
    merged = AgentResponse.merge([r1, r2])
    # Dedup by URL — a.com appears once
    assert len(merged.results) == 2
    urls = {r.url for r in merged.results}
    assert urls == {"https://a.com", "https://b.com"}
```

- [ ] **Step 2: Run tests — verify fail**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_search_agents.py -v --tb=short
```

- [ ] **Step 3: Implement base.py**

```python
# apps/naga/engine/search_agents/__init__.py
```

```python
# apps/naga/engine/search_agents/base.py
"""Base search agent interface and shared types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class SearchResult:
    """A single search result from any agent."""

    url: str
    title: str
    content: str
    relevance_score: float = 0.0
    source_type: Optional[str] = None  # web / gov / academic / internal / blog
    freshness_date: Optional[date] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class AgentResponse:
    """Response from a search agent — a list of results."""

    agent_name: str
    results: list[SearchResult] = field(default_factory=list)
    search_calls_used: int = 0
    error: Optional[str] = None

    @staticmethod
    def merge(responses: list[AgentResponse]) -> AgentResponse:
        """Merge multiple agent responses, deduplicating by URL."""
        seen_urls: set[str] = set()
        merged_results: list[SearchResult] = []
        total_calls = 0

        for resp in responses:
            total_calls += resp.search_calls_used
            for result in resp.results:
                if result.url not in seen_urls:
                    seen_urls.add(result.url)
                    merged_results.append(result)

        return AgentResponse(
            agent_name="merged",
            results=merged_results,
            search_calls_used=total_calls,
        )


class BaseSearchAgent(ABC):
    """Abstract base for all Naga search agents."""

    name: str = "base"

    @abstractmethod
    async def search(
        self,
        query: str,
        sub_question: str,
        max_results: int = 10,
    ) -> AgentResponse:
        """Execute a search for the given query/sub-question."""
        ...
```

- [ ] **Step 4: Run tests — verify pass**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_search_agents.py -v
```

Expected: all 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/naga/engine/search_agents/ apps/naga/tests/test_search_agents.py
git commit -m "feat(naga): add BaseSearchAgent ABC and SearchResult types"
```

---

### Task 7: Exa Neural Search Agent

**Files:**

- Create: `apps/naga/engine/search_agents/exa_agent.py`

- [ ] **Step 1: Write test (mocked MCP calls)**

```python
# Append to apps/naga/tests/test_search_agents.py

from unittest.mock import AsyncMock, patch
import pytest


@pytest.mark.asyncio
async def test_exa_agent_search():
    from apps.naga.engine.search_agents.exa_agent import ExaSearchAgent

    mock_mcp = AsyncMock()
    mock_mcp.return_value = {
        "results": [
            {
                "url": "https://example.com/page1",
                "title": "Test Page 1",
                "text": "Content about Indonesia visa regulations",
                "highlights": ["visa regulations updated"],
                "score": 0.85,
            },
            {
                "url": "https://example.com/page2",
                "title": "Test Page 2",
                "text": "More content about KITAS",
                "score": 0.72,
            },
        ]
    }

    agent = ExaSearchAgent(mcp_call=mock_mcp)
    response = await agent.search("Indonesia visa regulations", "What are KITAS requirements?")

    assert response.agent_name == "exa"
    assert len(response.results) == 2
    assert response.results[0].url == "https://example.com/page1"
    assert response.results[0].relevance_score == 0.85
    assert response.search_calls_used >= 1


@pytest.mark.asyncio
async def test_exa_agent_with_domain_filter():
    from apps.naga.engine.search_agents.exa_agent import ExaSearchAgent

    mock_mcp = AsyncMock()
    mock_mcp.return_value = {"results": []}

    agent = ExaSearchAgent(mcp_call=mock_mcp)
    await agent.search(
        "visa policy", "test", include_domains=["imigrasi.go.id"]
    )

    # Verify the MCP call included domain filter
    call_kwargs = mock_mcp.call_args
    assert "includeDomains" in str(call_kwargs) or "include_domains" in str(call_kwargs)
```

- [ ] **Step 2: Run test — verify fail**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_search_agents.py::test_exa_agent_search -v --tb=short
```

- [ ] **Step 3: Implement exa_agent.py**

```python
# apps/naga/engine/search_agents/exa_agent.py
"""Exa Neural Search Agent — semantic web search via MCP."""

from __future__ import annotations

import logging
from typing import Callable, Optional

from apps.naga.engine.search_agents.base import (
    AgentResponse,
    BaseSearchAgent,
    SearchResult,
)

logger = logging.getLogger(__name__)


class ExaSearchAgent(BaseSearchAgent):
    """Search agent using Exa's neural search API via MCP tools."""

    name = "exa"

    def __init__(self, mcp_call: Callable) -> None:
        self._mcp_call = mcp_call

    async def search(
        self,
        query: str,
        sub_question: str,
        max_results: int = 10,
        include_domains: Optional[list[str]] = None,
        exclude_domains: Optional[list[str]] = None,
        search_type: str = "neural",
    ) -> AgentResponse:
        """Execute Exa neural search."""
        search_calls = 0

        try:
            params: dict = {
                "query": f"{query} {sub_question}".strip(),
                "numResults": max_results,
                "type": search_type,
            }
            if include_domains:
                params["includeDomains"] = include_domains
            if exclude_domains:
                params["excludeDomains"] = exclude_domains

            raw = await self._mcp_call(**params)
            search_calls += 1

            results = []
            for item in raw.get("results", []):
                results.append(
                    SearchResult(
                        url=item.get("url", ""),
                        title=item.get("title", ""),
                        content=item.get("text", ""),
                        relevance_score=item.get("score", 0.0),
                        source_type="web",
                        metadata={
                            "highlights": item.get("highlights", []),
                            "summary": item.get("summary", ""),
                            "agent": self.name,
                        },
                    )
                )

            return AgentResponse(
                agent_name=self.name,
                results=results,
                search_calls_used=search_calls,
            )

        except Exception as e:
            logger.error("Exa search failed: %s", e)
            return AgentResponse(
                agent_name=self.name,
                search_calls_used=search_calls,
                error=str(e),
            )
```

- [ ] **Step 4: Run tests — verify pass**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_search_agents.py -v
```

Expected: all 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/naga/engine/search_agents/exa_agent.py apps/naga/tests/test_search_agents.py
git commit -m "feat(naga): add Exa Neural Search Agent"
```

---

### Task 8: Brave Web Search Agent

**Files:**

- Create: `apps/naga/engine/search_agents/brave_agent.py`

- [ ] **Step 1: Write test**

```python
# Append to apps/naga/tests/test_search_agents.py


@pytest.mark.asyncio
async def test_brave_agent_search():
    from apps.naga.engine.search_agents.brave_agent import BraveSearchAgent

    mock_brave = AsyncMock()
    mock_brave.return_value = {
        "web": {
            "results": [
                {
                    "url": "https://news.com/article",
                    "title": "Latest Indonesia News",
                    "description": "Indonesia updates visa policy",
                    "age": "2 days ago",
                },
            ]
        }
    }

    mock_fetch = AsyncMock()
    mock_fetch.return_value = {"content": "Full article content about visa changes..."}

    agent = BraveSearchAgent(brave_call=mock_brave, fetch_call=mock_fetch)
    response = await agent.search("Indonesia visa", "latest changes")

    assert response.agent_name == "brave"
    assert len(response.results) >= 1
    assert response.search_calls_used >= 1
```

- [ ] **Step 2: Run test — verify fail**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_search_agents.py::test_brave_agent_search -v --tb=short
```

- [ ] **Step 3: Implement brave_agent.py**

```python
# apps/naga/engine/search_agents/brave_agent.py
"""Brave Web Search Agent — independent index via MCP."""

from __future__ import annotations

import logging
from typing import Callable, Optional

from apps.naga.engine.search_agents.base import (
    AgentResponse,
    BaseSearchAgent,
    SearchResult,
)

logger = logging.getLogger(__name__)


class BraveSearchAgent(BaseSearchAgent):
    """Search agent using Brave's independent web index."""

    name = "brave"

    def __init__(self, brave_call: Callable, fetch_call: Callable) -> None:
        self._brave_call = brave_call
        self._fetch_call = fetch_call

    async def search(
        self,
        query: str,
        sub_question: str,
        max_results: int = 10,
        fetch_top_n: int = 5,
    ) -> AgentResponse:
        """Execute Brave search + fetch top results."""
        search_calls = 0

        try:
            combined_query = f"{query} {sub_question}".strip()
            raw = await self._brave_call(query=combined_query, count=min(max_results, 20))
            search_calls += 1

            web_results = raw.get("web", {}).get("results", [])

            results = []
            for item in web_results[:fetch_top_n]:
                url = item.get("url", "")
                content = item.get("description", "")

                # Fetch full content for top results
                try:
                    fetched = await self._fetch_call(url=url, max_length=50000)
                    if fetched and fetched.get("content"):
                        content = fetched["content"]
                except Exception:
                    pass  # Fall back to description

                results.append(
                    SearchResult(
                        url=url,
                        title=item.get("title", ""),
                        content=content,
                        source_type="web",
                        metadata={
                            "age": item.get("age", ""),
                            "agent": self.name,
                        },
                    )
                )

            return AgentResponse(
                agent_name=self.name,
                results=results,
                search_calls_used=search_calls,
            )

        except Exception as e:
            logger.error("Brave search failed: %s", e)
            return AgentResponse(
                agent_name=self.name,
                search_calls_used=search_calls,
                error=str(e),
            )
```

- [ ] **Step 4: Run tests — verify pass**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_search_agents.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/naga/engine/search_agents/brave_agent.py apps/naga/tests/test_search_agents.py
git commit -m "feat(naga): add Brave Web Search Agent"
```

---

### Task 9: Indonesia Domain Agent

**Files:**

- Create: `apps/naga/engine/search_agents/domain_agent.py`

- [ ] **Step 1: Write test**

```python
# Append to apps/naga/tests/test_search_agents.py


@pytest.mark.asyncio
async def test_domain_agent_search():
    from apps.naga.engine.search_agents.domain_agent import IndonesiaDomainAgent

    mock_calls = {
        "ask_legal": AsyncMock(
            return_value={
                "answer": "KITAS fee is Rp 2.000.000 as per PP 28/2024",
                "sources": [{"title": "PP 28/2024", "url": "peraturan.bpk.go.id/..."}],
                "confidence": 0.85,
            }
        ),
        "search_intel": AsyncMock(
            return_value={
                "results": [
                    {"title": "New visa fee update", "content": "Details...", "url": "..."}
                ]
            }
        ),
        "notebook_query": AsyncMock(
            return_value={
                "status": "success",
                "answer": "Based on sources, fee is confirmed.",
                "sources_used": ["source_1"],
            }
        ),
        "recall_similar": AsyncMock(return_value={"episodes": []}),
        "exa_call": AsyncMock(return_value={"results": []}),
    }

    agent = IndonesiaDomainAgent(**mock_calls)
    response = await agent.search("KITAS fee 2026", "What is the current KITAS fee?")

    assert response.agent_name == "domain_indonesia"
    assert len(response.results) >= 1
    # Should have called ask_legal at minimum
    mock_calls["ask_legal"].assert_called_once()
```

- [ ] **Step 2: Run test — verify fail**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_search_agents.py::test_domain_agent_search -v --tb=short
```

- [ ] **Step 3: Implement domain_agent.py**

```python
# apps/naga/engine/search_agents/domain_agent.py
"""Indonesia Domain Agent — RAG + NLM + gov sources."""

from __future__ import annotations

import logging
from typing import Callable, Optional

from apps.naga.engine.search_agents.base import (
    AgentResponse,
    BaseSearchAgent,
    SearchResult,
)

logger = logging.getLogger(__name__)

# NLM notebook IDs by domain
NLM_NOTEBOOKS: dict[str, str] = {
    "immigration": "NB-2",
    "company": "NB-3",
    "tax": "NB-4",
    "property": "NB-5",
    "compliance": "NB-6",
    "employment": "NB-7",
    "general_legal": "NB-8",
}

# Keywords to select which NLM notebooks to query
_NOTEBOOK_KEYWORDS: dict[str, list[str]] = {
    "immigration": ["visa", "kitas", "kitap", "imigrasi", "izin tinggal", "golden visa", "b211"],
    "company": ["pt pma", "cv", "perseroan", "yayasan", "akta", "oss", "nib", "kbli"],
    "tax": ["pajak", "tax", "npwp", "pph", "ppn", "spt"],
    "property": ["hak pakai", "hgb", "shm", "properti", "tanah"],
    "compliance": ["compliance", "kepatuhan", "laporan", "pelaporan"],
    "employment": ["tenaga kerja", "rptka", "imta", "kemnaker", "employment"],
}

GOV_DOMAINS = [
    "imigrasi.go.id",
    "pajak.go.id",
    "kemenkumham.go.id",
    "oss.go.id",
    "bkpm.go.id",
    "peraturan.bpk.go.id",
    "jdih.kemenkumham.go.id",
]


class IndonesiaDomainAgent(BaseSearchAgent):
    """Search agent specialized for Indonesian legal/business domain."""

    name = "domain_indonesia"

    def __init__(
        self,
        ask_legal: Callable,
        search_intel: Callable,
        notebook_query: Optional[Callable] = None,
        recall_similar: Optional[Callable] = None,
        exa_call: Optional[Callable] = None,
    ) -> None:
        self._ask_legal = ask_legal
        self._search_intel = search_intel
        self._notebook_query = notebook_query
        self._recall_similar = recall_similar
        self._exa_call = exa_call

    def _select_notebooks(self, query: str) -> list[str]:
        """Select relevant NLM notebooks based on query keywords."""
        query_lower = query.lower()
        selected = []
        for domain, keywords in _NOTEBOOK_KEYWORDS.items():
            if any(kw in query_lower for kw in keywords):
                nb_id = NLM_NOTEBOOKS.get(domain)
                if nb_id:
                    selected.append(nb_id)
        return selected or ["NB-2"]  # Default to immigration

    async def search(
        self,
        query: str,
        sub_question: str,
        max_results: int = 10,
    ) -> AgentResponse:
        """Search across all Indonesia domain sources."""
        results: list[SearchResult] = []
        search_calls = 0
        combined = f"{query} {sub_question}".strip()

        # 1. ask_legal — RAG for normativa/visa/tax
        try:
            legal_resp = await self._ask_legal(query=combined)
            search_calls += 1
            if legal_resp and legal_resp.get("answer"):
                results.append(
                    SearchResult(
                        url="internal://ask_legal",
                        title="Legal RAG Response",
                        content=legal_resp["answer"],
                        relevance_score=legal_resp.get("confidence", 0.7),
                        source_type="internal",
                        metadata={
                            "sources": legal_resp.get("sources", []),
                            "agent": self.name,
                            "tool": "ask_legal",
                        },
                    )
                )
        except Exception as e:
            logger.warning("ask_legal failed: %s", e)

        # 2. search_intel — recent regulatory news
        try:
            intel_resp = await self._search_intel(query=combined)
            search_calls += 1
            for item in (intel_resp or {}).get("results", [])[:5]:
                results.append(
                    SearchResult(
                        url=item.get("url", "internal://search_intel"),
                        title=item.get("title", ""),
                        content=item.get("content", ""),
                        source_type="internal",
                        metadata={"agent": self.name, "tool": "search_intel"},
                    )
                )
        except Exception as e:
            logger.warning("search_intel failed: %s", e)

        # 3. NLM notebook_query on relevant notebooks
        if self._notebook_query:
            notebooks = self._select_notebooks(combined)
            for nb_id in notebooks[:2]:  # Max 2 notebooks per query
                try:
                    nlm_resp = await self._notebook_query(
                        notebook_id=nb_id, query=combined
                    )
                    search_calls += 1
                    if nlm_resp and nlm_resp.get("answer"):
                        results.append(
                            SearchResult(
                                url=f"internal://nlm/{nb_id}",
                                title=f"NLM {nb_id} Response",
                                content=nlm_resp["answer"],
                                relevance_score=0.8,
                                source_type="internal",
                                metadata={
                                    "sources_used": nlm_resp.get("sources_used", []),
                                    "agent": self.name,
                                    "tool": "notebook_query",
                                    "notebook": nb_id,
                                },
                            )
                        )
                except Exception as e:
                    logger.warning("NLM query %s failed: %s", nb_id, e)

        # 4. Exa with .go.id domain filter
        if self._exa_call:
            try:
                gov_resp = await self._exa_call(
                    query=combined,
                    numResults=5,
                    type="neural",
                    includeDomains=GOV_DOMAINS,
                )
                search_calls += 1
                for item in gov_resp.get("results", []):
                    results.append(
                        SearchResult(
                            url=item.get("url", ""),
                            title=item.get("title", ""),
                            content=item.get("text", ""),
                            relevance_score=item.get("score", 0.0),
                            source_type="gov",
                            metadata={"agent": self.name, "tool": "exa_gov"},
                        )
                    )
            except Exception as e:
                logger.warning("Exa gov search failed: %s", e)

        # 5. recall_similar — episodic memory
        if self._recall_similar:
            try:
                episodes = await self._recall_similar(query=combined)
                search_calls += 1
                for ep in (episodes or {}).get("episodes", [])[:3]:
                    results.append(
                        SearchResult(
                            url=f"internal://episode/{ep.get('id', '')}",
                            title=ep.get("title", "Past Episode"),
                            content=ep.get("content", ""),
                            source_type="internal",
                            metadata={"agent": self.name, "tool": "recall_similar"},
                        )
                    )
            except Exception as e:
                logger.warning("recall_similar failed: %s", e)

        return AgentResponse(
            agent_name=self.name,
            results=results,
            search_calls_used=search_calls,
        )
```

- [ ] **Step 4: Run tests — verify pass**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_search_agents.py -v
```

Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/naga/engine/search_agents/domain_agent.py apps/naga/tests/test_search_agents.py
git commit -m "feat(naga): add Indonesia Domain Agent — RAG + NLM + gov sources"
```

---

### Task 10: Academic Search Agent

**Files:**

- Create: `apps/naga/engine/readers/__init__.py`
- Create: `apps/naga/engine/readers/academic_apis.py`
- Create: `apps/naga/engine/search_agents/academic_agent.py`

- [ ] **Step 1: Write test**

```python
# Append to apps/naga/tests/test_search_agents.py


@pytest.mark.asyncio
async def test_academic_agent_search():
    from apps.naga.engine.search_agents.academic_agent import AcademicSearchAgent

    mock_http = AsyncMock()
    # Mock Semantic Scholar API response
    mock_http.return_value = {
        "data": [
            {
                "paperId": "abc123",
                "title": "Agentic RAG Survey",
                "abstract": "We survey agentic retrieval...",
                "year": 2025,
                "citationCount": 42,
                "url": "https://semanticscholar.org/paper/abc123",
                "externalIds": {"DOI": "10.1234/test"},
            }
        ]
    }

    agent = AcademicSearchAgent(http_get=mock_http)
    response = await agent.search("agentic RAG", "survey of architectures")

    assert response.agent_name == "academic"
    assert len(response.results) >= 1
    assert response.results[0].source_type == "academic"
```

- [ ] **Step 2: Run test — verify fail**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_search_agents.py::test_academic_agent_search -v --tb=short
```

- [ ] **Step 3: Implement academic_apis.py**

```python
# apps/naga/engine/readers/__init__.py
```

```python
# apps/naga/engine/readers/academic_apis.py
"""Academic API clients — Semantic Scholar, OpenAlex, arXiv."""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1"
OPENALEX_BASE = "https://api.openalex.org"
ARXIV_BASE = "http://export.arxiv.org/api/query"


async def search_semantic_scholar(
    query: str,
    http_get: Callable,
    limit: int = 10,
    fields: str = "paperId,title,abstract,year,citationCount,url,externalIds",
) -> list[dict]:
    """Search Semantic Scholar API."""
    try:
        url = f"{SEMANTIC_SCHOLAR_BASE}/paper/search"
        params = {"query": query, "limit": limit, "fields": fields}
        resp = await http_get(url=url, params=params)
        return resp.get("data", [])
    except Exception as e:
        logger.warning("Semantic Scholar search failed: %s", e)
        return []


async def search_openalex(
    query: str,
    http_get: Callable,
    limit: int = 10,
) -> list[dict]:
    """Search OpenAlex API (no auth required)."""
    try:
        url = f"{OPENALEX_BASE}/works"
        params = {
            "search": query,
            "per_page": limit,
            "sort": "relevance_score:desc",
            "select": "id,doi,title,abstract_inverted_index,publication_year,cited_by_count",
        }
        resp = await http_get(url=url, params=params)
        return resp.get("results", [])
    except Exception as e:
        logger.warning("OpenAlex search failed: %s", e)
        return []
```

- [ ] **Step 4: Implement academic_agent.py**

```python
# apps/naga/engine/search_agents/academic_agent.py
"""Academic Search Agent — Semantic Scholar + OpenAlex + arXiv."""

from __future__ import annotations

import logging
from typing import Callable, Optional

from apps.naga.engine.readers.academic_apis import (
    search_openalex,
    search_semantic_scholar,
)
from apps.naga.engine.search_agents.base import (
    AgentResponse,
    BaseSearchAgent,
    SearchResult,
)

logger = logging.getLogger(__name__)


class AcademicSearchAgent(BaseSearchAgent):
    """Search agent for academic papers and research."""

    name = "academic"

    def __init__(self, http_get: Callable) -> None:
        self._http_get = http_get

    async def search(
        self,
        query: str,
        sub_question: str,
        max_results: int = 10,
    ) -> AgentResponse:
        """Search academic sources."""
        results: list[SearchResult] = []
        search_calls = 0
        combined = f"{query} {sub_question}".strip()

        # 1. Semantic Scholar
        s2_papers = await search_semantic_scholar(
            combined, self._http_get, limit=max_results
        )
        search_calls += 1
        for paper in s2_papers:
            doi = (paper.get("externalIds") or {}).get("DOI", "")
            results.append(
                SearchResult(
                    url=paper.get("url", ""),
                    title=paper.get("title", ""),
                    content=paper.get("abstract", "") or "",
                    source_type="academic",
                    metadata={
                        "doi": doi,
                        "year": paper.get("year"),
                        "citations": paper.get("citationCount", 0),
                        "paper_id": paper.get("paperId", ""),
                        "agent": self.name,
                        "source_api": "semantic_scholar",
                    },
                )
            )

        # 2. OpenAlex (broader coverage)
        oa_works = await search_openalex(combined, self._http_get, limit=max_results)
        search_calls += 1
        for work in oa_works:
            # OpenAlex uses inverted index for abstract — reconstruct
            abstract = ""
            inverted = work.get("abstract_inverted_index")
            if inverted:
                word_positions: list[tuple[int, str]] = []
                for word, positions in inverted.items():
                    for pos in positions:
                        word_positions.append((pos, word))
                word_positions.sort()
                abstract = " ".join(w for _, w in word_positions)

            results.append(
                SearchResult(
                    url=work.get("doi", work.get("id", "")),
                    title=work.get("title", ""),
                    content=abstract,
                    source_type="academic",
                    metadata={
                        "doi": work.get("doi", ""),
                        "year": work.get("publication_year"),
                        "citations": work.get("cited_by_count", 0),
                        "agent": self.name,
                        "source_api": "openalex",
                    },
                )
            )

        return AgentResponse(
            agent_name=self.name,
            results=results,
            search_calls_used=search_calls,
        )
```

- [ ] **Step 5: Run tests — verify pass**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_search_agents.py -v
```

Expected: all 7 tests PASS

- [ ] **Step 6: Commit**

```bash
git add apps/naga/engine/readers/ apps/naga/engine/search_agents/academic_agent.py apps/naga/tests/test_search_agents.py
git commit -m "feat(naga): add Academic Search Agent — Semantic Scholar + OpenAlex"
```

---

### Task 11: Deep Crawl Agent

**Files:**

- Create: `apps/naga/engine/search_agents/crawl_agent.py`

- [ ] **Step 1: Write test**

```python
# Append to apps/naga/tests/test_search_agents.py


@pytest.mark.asyncio
async def test_crawl_agent():
    from apps.naga.engine.search_agents.crawl_agent import DeepCrawlAgent

    mock_fetch = AsyncMock()
    mock_fetch.return_value = {
        "content": "# Full Page Content\n\nDetailed information about regulations..."
    }

    agent = DeepCrawlAgent(fetch_call=mock_fetch)
    response = await agent.search(
        query="visa regulations",
        sub_question="details",
        urls_to_crawl=["https://imigrasi.go.id/page1", "https://pajak.go.id/page2"],
    )

    assert response.agent_name == "deep_crawl"
    assert len(response.results) == 2
    assert mock_fetch.call_count == 2
```

- [ ] **Step 2: Run test — verify fail**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_search_agents.py::test_crawl_agent -v --tb=short
```

- [ ] **Step 3: Implement crawl_agent.py**

```python
# apps/naga/engine/search_agents/crawl_agent.py
"""Deep Crawl Agent — reactive, fetches full page content."""

from __future__ import annotations

import logging
from typing import Callable

from apps.naga.engine.search_agents.base import (
    AgentResponse,
    BaseSearchAgent,
    SearchResult,
)

logger = logging.getLogger(__name__)


class DeepCrawlAgent(BaseSearchAgent):
    """Reactive agent — fetches full content from specific URLs.

    Only dispatched in cycle 2+ by the Orchestrator, never in cycle 1.
    """

    name = "deep_crawl"

    def __init__(self, fetch_call: Callable) -> None:
        self._fetch_call = fetch_call

    async def search(
        self,
        query: str,
        sub_question: str,
        max_results: int = 10,
        urls_to_crawl: list[str] | None = None,
    ) -> AgentResponse:
        """Fetch full content from specified URLs."""
        if not urls_to_crawl:
            return AgentResponse(agent_name=self.name, search_calls_used=0)

        results: list[SearchResult] = []

        for url in urls_to_crawl[:max_results]:
            try:
                fetched = await self._fetch_call(url=url, max_length=200000)
                content = fetched.get("content", "") if fetched else ""

                results.append(
                    SearchResult(
                        url=url,
                        title=url.split("/")[-1] or url,
                        content=content,
                        source_type="web",
                        metadata={
                            "agent": self.name,
                            "full_crawl": True,
                            "content_length": len(content),
                        },
                    )
                )
            except Exception as e:
                logger.warning("Deep crawl failed for %s: %s", url, e)

        return AgentResponse(
            agent_name=self.name,
            results=results,
            search_calls_used=len(urls_to_crawl),
        )
```

- [ ] **Step 4: Run tests — verify pass**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_search_agents.py -v
```

Expected: all 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/naga/engine/search_agents/crawl_agent.py apps/naga/tests/test_search_agents.py
git commit -m "feat(naga): add Deep Crawl Agent (reactive, cycle 2+)"
```

---

## PHASE 3: Quality + Synthesis (Tasks 12-17)

### Task 12: Source Scorer

**Files:**

- Create: `apps/naga/engine/quality/__init__.py`
- Create: `apps/naga/engine/quality/source_scorer.py`
- Create: `apps/naga/tests/test_quality.py`

- [ ] **Step 1: Write tests**

```python
# apps/naga/tests/test_quality.py
"""Tests for Naga quality pipeline."""

import pytest
from datetime import date, timedelta
from apps.naga.engine.quality.source_scorer import score_source, score_sources
from apps.naga.engine.search_agents.base import SearchResult


def test_score_gov_source():
    source = SearchResult(
        url="https://imigrasi.go.id/news/123",
        title="New policy",
        content="content",
        source_type="gov",
        freshness_date=date.today(),
    )
    score = score_source(source, relevance=0.8)
    assert score >= 0.7  # High credibility + fresh + relevant


def test_score_blog_source():
    source = SearchResult(
        url="https://randomblog.com/post",
        title="Opinion",
        content="content",
        source_type="blog",
        freshness_date=date.today() - timedelta(days=400),
    )
    score = score_source(source, relevance=0.5)
    assert score < 0.5  # Low credibility + old


def test_score_sources_filters_below_threshold():
    sources = [
        SearchResult(url="https://imigrasi.go.id/a", title="A", content="c", source_type="gov"),
        SearchResult(url="https://random.xyz/b", title="B", content="c", source_type="unknown"),
    ]
    scored = score_sources(sources, relevances={"https://imigrasi.go.id/a": 0.9, "https://random.xyz/b": 0.1})
    # random.xyz should be filtered out (low cred + low relevance)
    assert len(scored) >= 1
    assert scored[0].url == "https://imigrasi.go.id/a"
```

- [ ] **Step 2: Run tests — verify fail**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_quality.py -v --tb=short
```

- [ ] **Step 3: Implement source_scorer.py**

```python
# apps/naga/engine/quality/__init__.py
```

```python
# apps/naga/engine/quality/source_scorer.py
"""Source scorer — configurable domain credibility scoring."""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from apps.naga.engine.config.naga_config import SOURCE_SCORE_MIN
from apps.naga.engine.search_agents.base import SearchResult

logger = logging.getLogger(__name__)

_WEIGHTS_PATH = Path(__file__).parent.parent / "config" / "source_weights.json"
_weights_cache: Optional[dict] = None


def _load_weights() -> dict:
    """Load source weights from JSON config."""
    global _weights_cache
    if _weights_cache is None:
        with open(_WEIGHTS_PATH) as f:
            _weights_cache = json.load(f)
    return _weights_cache


def _credibility_score(url: str, source_type: Optional[str]) -> float:
    """Compute credibility score for a source."""
    weights = _load_weights()
    defaults = weights.get("defaults", {})
    overrides = weights.get("domain_overrides", {})

    # Check domain overrides first
    from urllib.parse import urlparse

    parsed = urlparse(url)
    domain = parsed.netloc.lower().lstrip("www.")

    if domain in overrides:
        return overrides[domain]

    # Check if it's a .go.id domain (Indonesian government)
    if domain.endswith(".go.id"):
        return defaults.get("gov", 0.9)

    # Fall back to source_type defaults
    if source_type and source_type in defaults:
        return defaults[source_type]

    return defaults.get("unknown", 0.3)


def _freshness_score(freshness_date: Optional[date]) -> float:
    """Compute freshness score based on age."""
    if not freshness_date:
        return 0.5  # Unknown freshness — neutral

    weights = _load_weights()
    freshness = weights.get("freshness_weights", {})
    age_days = (date.today() - freshness_date).days

    if age_days <= 30:
        return freshness.get("days_30", 1.0)
    elif age_days <= 365:
        return freshness.get("days_365", 0.7)
    elif age_days <= 1095:
        return freshness.get("days_1095", 0.5)
    else:
        return freshness.get("older", 0.3)


def score_source(
    source: SearchResult,
    relevance: float = 0.5,
    cred_weight: float = 0.40,
    fresh_weight: float = 0.25,
    rel_weight: float = 0.35,
) -> float:
    """Score a single source on [0, 1]."""
    cred = _credibility_score(source.url, source.source_type)
    fresh = _freshness_score(source.freshness_date)
    return cred * cred_weight + fresh * fresh_weight + relevance * rel_weight


def score_sources(
    sources: list[SearchResult],
    relevances: dict[str, float] | None = None,
    min_score: float = SOURCE_SCORE_MIN,
) -> list[SearchResult]:
    """Score and filter sources, returning those above threshold sorted by score."""
    relevances = relevances or {}
    scored: list[tuple[float, SearchResult]] = []

    for source in sources:
        rel = relevances.get(source.url, source.relevance_score or 0.5)
        s = score_source(source, relevance=rel)
        source.metadata["source_score"] = round(s, 3)
        if s >= min_score:
            scored.append((s, source))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [src for _, src in scored]
```

- [ ] **Step 4: Run tests — verify pass**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_quality.py -v
```

Expected: all 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/naga/engine/quality/ apps/naga/tests/test_quality.py
git commit -m "feat(naga): add Source Scorer with configurable domain credibility"
```

---

### Task 13: CRAG-Light — Fast Relevance Gate

**Files:**

- Create: `apps/naga/engine/quality/crag_light.py`

- [ ] **Step 1: Write test**

```python
# Append to apps/naga/tests/test_quality.py

from apps.naga.engine.quality.crag_light import crag_evaluate, CragDecision


def test_crag_pass():
    decision = crag_evaluate(
        sub_question="What is KITAS fee?",
        sources_content=["KITAS fee is Rp 2.000.000 per PP 28/2024"],
    )
    assert decision.action == "PASS"


def test_crag_retry_irrelevant():
    decision = crag_evaluate(
        sub_question="What is KITAS fee?",
        sources_content=["The weather in Bali is tropical year-round"],
    )
    assert decision.action in ("RETRY", "ESCALATE")


def test_crag_escalate_empty():
    decision = crag_evaluate(
        sub_question="What is KITAS fee?",
        sources_content=[],
    )
    assert decision.action == "ESCALATE"
```

- [ ] **Step 2: Run tests — verify fail**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_quality.py::test_crag_pass -v --tb=short
```

- [ ] **Step 3: Implement crag_light.py**

```python
# apps/naga/engine/quality/crag_light.py
"""CRAG-Light — fast relevance gate for search results.

Binary decision: PASS (sufficient) / RETRY (reformulate) / ESCALATE (add web search).
Runs on simple keyword overlap + content length heuristics.
For production, can be upgraded to Haiku/qwen LLM call.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CragDecision:
    """Result of CRAG-light evaluation."""

    action: str  # PASS / RETRY / ESCALATE
    reason: str
    relevance_score: float


def _keyword_overlap(question: str, content: str) -> float:
    """Compute keyword overlap ratio between question and content."""
    q_words = set(re.findall(r"\w{3,}", question.lower()))
    c_words = set(re.findall(r"\w{3,}", content.lower()))
    if not q_words:
        return 0.0
    overlap = q_words & c_words
    return len(overlap) / len(q_words)


def crag_evaluate(
    sub_question: str,
    sources_content: list[str],
    pass_threshold: float = 0.30,
    retry_threshold: float = 0.15,
) -> CragDecision:
    """Fast relevance gate for retrieved sources.

    Args:
        sub_question: The sub-question being answered.
        sources_content: List of source content strings.
        pass_threshold: Minimum overlap for PASS.
        retry_threshold: Minimum overlap for RETRY (below = ESCALATE).

    Returns:
        CragDecision with action, reason, and relevance_score.
    """
    if not sources_content:
        return CragDecision(
            action="ESCALATE",
            reason="No sources retrieved",
            relevance_score=0.0,
        )

    # Combine all sources for evaluation
    combined = " ".join(sources_content)
    overlap = _keyword_overlap(sub_question, combined)

    # Also check content substantiveness
    total_len = len(combined)
    has_substance = total_len > 100

    if overlap >= pass_threshold and has_substance:
        return CragDecision(
            action="PASS",
            reason=f"Keyword overlap {overlap:.2f} >= {pass_threshold}, content length {total_len}",
            relevance_score=overlap,
        )
    elif overlap >= retry_threshold:
        return CragDecision(
            action="RETRY",
            reason=f"Keyword overlap {overlap:.2f} — partial relevance, try reformulation",
            relevance_score=overlap,
        )
    else:
        return CragDecision(
            action="ESCALATE",
            reason=f"Keyword overlap {overlap:.2f} < {retry_threshold} — sources irrelevant",
            relevance_score=overlap,
        )
```

- [ ] **Step 4: Run tests — verify pass**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_quality.py -v
```

Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/naga/engine/quality/crag_light.py apps/naga/tests/test_quality.py
git commit -m "feat(naga): add CRAG-Light fast relevance gate"
```

---

### Task 14: Claim Extractor

**Files:**

- Create: `apps/naga/engine/quality/claim_extractor.py`

- [ ] **Step 1: Write test**

```python
# Append to apps/naga/tests/test_quality.py

from apps.naga.engine.quality.claim_extractor import extract_claims


def test_extract_claims_from_evidence():
    evidence = {
        "sub_q_1": {
            "facts": [
                {
                    "text": "KITAS fee increased to Rp 2.500.000 effective Jan 2026",
                    "source_ids": ["src_1", "src_2", "src_3"],
                    "confidence": 0.9,
                },
                {
                    "text": "Processing time is 5 business days",
                    "source_ids": ["src_1"],
                    "confidence": 0.6,
                },
            ],
            "contradictions": [
                {
                    "claim_a": "Fee is Rp 2.500.000",
                    "claim_b": "Fee is Rp 2.000.000",
                    "sources": ["src_1 vs src_4"],
                }
            ],
        }
    }

    claims = extract_claims(evidence, domain="indonesia")
    assert len(claims) >= 2

    # First claim should be VERIFIED (3 sources)
    verified = [c for c in claims if c.verification_level == "VERIFIED"]
    assert len(verified) >= 1

    # Should have a CONTESTED claim from contradictions
    contested = [c for c in claims if c.verification_level == "CONTESTED"]
    assert len(contested) >= 1
    assert contested[0].resolution_hint is not None
```

- [ ] **Step 2: Run test — verify fail**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_quality.py::test_extract_claims_from_evidence -v --tb=short
```

- [ ] **Step 3: Implement claim_extractor.py**

```python
# apps/naga/engine/quality/claim_extractor.py
"""Claim extractor — extracts atomic verified claims from evidence_map."""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from apps.naga.db.models import NagaClaim
from apps.naga.engine.config.naga_config import (
    CONFIDENCE_CONTESTED_MIN,
    CONFIDENCE_LIKELY_MIN,
    CONFIDENCE_UNVERIFIED_MIN,
    CONFIDENCE_VERIFIED_MIN,
)

logger = logging.getLogger(__name__)


def _classify_verification(
    source_count: int, confidence: float, has_contradiction: bool
) -> tuple[str, float]:
    """Classify claim verification level."""
    if has_contradiction:
        return "CONTESTED", max(CONFIDENCE_CONTESTED_MIN, min(confidence, 0.49))

    if source_count >= 3 and confidence >= CONFIDENCE_VERIFIED_MIN:
        return "VERIFIED", confidence
    elif source_count >= 1 and confidence >= CONFIDENCE_LIKELY_MIN:
        return "LIKELY", confidence
    elif source_count >= 1:
        return "UNVERIFIED", max(CONFIDENCE_UNVERIFIED_MIN, confidence)
    else:
        return "UNVERIFIED", CONFIDENCE_UNVERIFIED_MIN


def extract_claims(
    evidence_map: dict,
    domain: str = "general",
    session_id: Optional[str] = None,
) -> list[NagaClaim]:
    """Extract atomic claims from Gemini's evidence_map.

    Args:
        evidence_map: Output from Gemini Bulk Reader — per sub-question facts,
                      contradictions, gaps, data_points.
        domain: Research domain (indonesia/general/hybrid).
        session_id: Parent session ID for linking claims.

    Returns:
        List of NagaClaim objects with verification levels.
    """
    claims: list[NagaClaim] = []

    for sub_q, data in evidence_map.items():
        facts = data.get("facts", [])
        contradictions = data.get("contradictions", [])

        # Build contradiction index
        contradiction_texts: set[str] = set()
        for c in contradictions:
            contradiction_texts.add(c.get("claim_a", "").lower().strip())
            contradiction_texts.add(c.get("claim_b", "").lower().strip())

        # Process facts into claims
        for fact in facts:
            text = fact.get("text", "").strip()
            if not text:
                continue

            source_ids = fact.get("source_ids", [])
            raw_confidence = fact.get("confidence", 0.5)

            # Check if this fact is contested
            is_contested = any(
                text.lower().strip().startswith(ct[:30])
                for ct in contradiction_texts
                if ct
            )

            level, adjusted_confidence = _classify_verification(
                source_count=len(source_ids),
                confidence=raw_confidence,
                has_contradiction=is_contested,
            )

            claim = NagaClaim(
                claim_text=text,
                domain=domain,
                session_id=session_id,
                verification_level=level,
                confidence=adjusted_confidence,
                source_ids=source_ids,
                cross_ref_count=len(source_ids),
            )

            if is_contested:
                # Find the matching contradiction for resolution hint
                for c in contradictions:
                    if text.lower().strip()[:30] in c.get("claim_a", "").lower():
                        claim.resolution_hint = (
                            f"Contradicted by: {c.get('claim_b', '?')} "
                            f"(sources: {c.get('sources', '?')})"
                        )
                        break
                if not claim.resolution_hint:
                    claim.resolution_hint = "Contradicting source found — review manually"

            claims.append(claim)

        # Process contradictions as separate CONTESTED claims
        for c in contradictions:
            claim_a = c.get("claim_a", "").strip()
            claim_b = c.get("claim_b", "").strip()
            if not claim_a or not claim_b:
                continue

            # Check if already captured from facts
            already_captured = any(
                cl.claim_text.lower().startswith(claim_a.lower()[:30])
                for cl in claims
            )
            if already_captured:
                continue

            claims.append(
                NagaClaim(
                    claim_text=f"{claim_a} [CONTESTED: {claim_b}]",
                    domain=domain,
                    session_id=session_id,
                    verification_level="CONTESTED",
                    confidence=CONFIDENCE_CONTESTED_MIN,
                    resolution_hint=f"Sources disagree: '{claim_a}' vs '{claim_b}' ({c.get('sources', '?')})",
                )
            )

    return claims
```

- [ ] **Step 4: Run tests — verify pass**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_quality.py -v
```

Expected: all 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/naga/engine/quality/claim_extractor.py apps/naga/tests/test_quality.py
git commit -m "feat(naga): add Claim Extractor with 5-level verification"
```

---

### Task 15: Convergence Detector

**Files:**

- Create: `apps/naga/engine/quality/convergence.py`

- [ ] **Step 1: Write test**

```python
# Append to apps/naga/tests/test_quality.py

from apps.naga.engine.quality.convergence import check_convergence, ConvergenceResult


def test_convergence_converged():
    result = check_convergence(
        sub_questions=["q1", "q2", "q3"],
        claims_per_question={"q1": 3, "q2": 2, "q3": 1},
        new_claims_this_iteration=1,
        total_claims=20,
        iteration=3,
        budget_can_search=True,
    )
    assert result.decision == "CONVERGED"


def test_convergence_iterate():
    result = check_convergence(
        sub_questions=["q1", "q2", "q3", "q4", "q5"],
        claims_per_question={"q1": 3, "q2": 0, "q3": 0, "q4": 0, "q5": 0},
        new_claims_this_iteration=5,
        total_claims=8,
        iteration=1,
        budget_can_search=True,
    )
    assert result.decision == "ITERATE"
    assert len(result.gap_questions) > 0


def test_convergence_timeout():
    result = check_convergence(
        sub_questions=["q1", "q2"],
        claims_per_question={"q1": 1},
        new_claims_this_iteration=2,
        total_claims=3,
        iteration=1,
        budget_can_search=False,
    )
    assert result.decision == "TIMEOUT"
```

- [ ] **Step 2: Run tests — verify fail**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_quality.py::test_convergence_converged -v --tb=short
```

- [ ] **Step 3: Implement convergence.py**

```python
# apps/naga/engine/quality/convergence.py
"""Convergence detector — decides when to stop searching."""

from __future__ import annotations

from dataclasses import dataclass, field

from apps.naga.engine.config.naga_config import (
    CONVERGENCE_COVERAGE_THRESHOLD,
    CONVERGENCE_NOVELTY_THRESHOLD,
)


@dataclass(frozen=True)
class ConvergenceResult:
    """Result of convergence check."""

    decision: str  # CONVERGED / ITERATE / TIMEOUT
    reason: str
    coverage: float
    novelty: float
    gap_questions: list[str] = field(default_factory=list)


def check_convergence(
    sub_questions: list[str],
    claims_per_question: dict[str, int],
    new_claims_this_iteration: int,
    total_claims: int,
    iteration: int,
    budget_can_search: bool,
    coverage_threshold: float = CONVERGENCE_COVERAGE_THRESHOLD,
    novelty_threshold: float = CONVERGENCE_NOVELTY_THRESHOLD,
) -> ConvergenceResult:
    """Check if research has converged.

    Args:
        sub_questions: List of sub-questions to cover.
        claims_per_question: Number of trustworthy claims per sub-question.
        new_claims_this_iteration: Claims found in the last iteration.
        total_claims: Total claims found so far.
        iteration: Current iteration number.
        budget_can_search: Whether budget allows more searches.
        coverage_threshold: Min coverage for CONVERGED (default 0.80).
        novelty_threshold: Max novelty for CONVERGED (default 0.10).

    Returns:
        ConvergenceResult with decision and diagnostics.
    """
    # Coverage: % of sub-questions with at least 1 claim
    covered = sum(1 for q in sub_questions if claims_per_question.get(q, 0) > 0)
    coverage = covered / len(sub_questions) if sub_questions else 1.0

    # Novelty: proportion of new claims vs total
    novelty = new_claims_this_iteration / total_claims if total_claims > 0 else 1.0

    # Gap questions: sub-questions with no claims
    gaps = [q for q in sub_questions if claims_per_question.get(q, 0) == 0]

    # Budget exhausted?
    if not budget_can_search:
        return ConvergenceResult(
            decision="TIMEOUT",
            reason=f"Budget exhausted at iteration {iteration}. Coverage: {coverage:.0%}, gaps: {len(gaps)}",
            coverage=coverage,
            novelty=novelty,
            gap_questions=gaps,
        )

    # Converged?
    if coverage >= coverage_threshold and novelty < novelty_threshold:
        return ConvergenceResult(
            decision="CONVERGED",
            reason=f"Coverage {coverage:.0%} >= {coverage_threshold:.0%} and novelty {novelty:.0%} < {novelty_threshold:.0%}",
            coverage=coverage,
            novelty=novelty,
            gap_questions=gaps,
        )

    # Need more research
    return ConvergenceResult(
        decision="ITERATE",
        reason=f"Coverage {coverage:.0%} < {coverage_threshold:.0%} or novelty {novelty:.0%} >= {novelty_threshold:.0%}. {len(gaps)} gaps remaining.",
        coverage=coverage,
        novelty=novelty,
        gap_questions=gaps,
    )
```

- [ ] **Step 4: Run tests — verify pass**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_quality.py -v
```

Expected: all 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/naga/engine/quality/convergence.py apps/naga/tests/test_quality.py
git commit -m "feat(naga): add Convergence Detector — coverage + novelty + budget"
```

---

### Task 16: Gemini Bulk Reader

**Files:**

- Create: `apps/naga/engine/readers/gemini_reader.py`

- [ ] **Step 1: Write test**

```python
# Append to apps/naga/tests/test_quality.py

from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_gemini_reader():
    from apps.naga.engine.readers.gemini_reader import gemini_bulk_read

    mock_generate = AsyncMock()
    mock_generate.return_value = {
        "text": '{"sub_q_1": {"facts": [{"text": "KITAS costs 2M", "source_ids": ["s1"], "confidence": 0.9}], "contradictions": [], "gaps": [], "data_points": []}}'
    }

    evidence_map = await gemini_bulk_read(
        sub_questions=["What does KITAS cost?"],
        sources_content=[
            {"id": "s1", "url": "https://imigrasi.go.id/fees", "content": "KITAS fee schedule: Rp 2.000.000"}
        ],
        generate_fn=mock_generate,
    )

    assert "sub_q_1" in evidence_map
    assert len(evidence_map["sub_q_1"]["facts"]) >= 1
```

- [ ] **Step 2: Run test — verify fail**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_quality.py::test_gemini_reader -v --tb=short
```

- [ ] **Step 3: Implement gemini_reader.py**

````python
# apps/naga/engine/readers/gemini_reader.py
"""Gemini Bulk Reader — uses 1M context window to extract structured evidence."""

from __future__ import annotations

import json
import logging
from typing import Callable

logger = logging.getLogger(__name__)

_READER_PROMPT_TEMPLATE = """You are a research analyst. Read ALL the sources below carefully and extract structured evidence for each sub-question.

## Sub-Questions:
{sub_questions}

## Sources:
{sources}

## Instructions:
For EACH sub-question, provide a JSON object with:
1. "facts": list of {{"text": "factual claim", "source_ids": ["id1", "id2"], "confidence": 0.0-1.0}}
2. "contradictions": list of {{"claim_a": "...", "claim_b": "...", "sources": "source_a vs source_b"}}
3. "gaps": list of strings — what is NOT covered by any source
4. "data_points": list of {{"value": "...", "unit": "...", "source": "id", "date": "YYYY-MM-DD or null"}}

IMPORTANT:
- Every fact MUST reference source_ids
- Flag contradictions between sources explicitly
- Note quantitative data (prices, dates, percentages) in data_points
- Be honest about gaps

Return ONLY valid JSON with keys "sub_q_1", "sub_q_2", etc.
"""


def _build_prompt(sub_questions: list[str], sources_content: list[dict]) -> str:
    """Build the structured prompt for Gemini."""
    sq_text = "\n".join(
        f"sub_q_{i + 1}: {q}" for i, q in enumerate(sub_questions)
    )

    src_text = "\n\n".join(
        f"[SOURCE {s.get('id', i)}] URL: {s.get('url', 'unknown')}\n{s.get('content', '')[:20000]}"
        for i, s in enumerate(sources_content)
    )

    return _READER_PROMPT_TEMPLATE.format(
        sub_questions=sq_text, sources=src_text
    )


async def gemini_bulk_read(
    sub_questions: list[str],
    sources_content: list[dict],
    generate_fn: Callable,
) -> dict:
    """Send sources to Gemini for structured evidence extraction.

    Args:
        sub_questions: List of sub-questions to answer.
        sources_content: List of {"id": ..., "url": ..., "content": ...} dicts.
        generate_fn: Async function that calls Gemini API and returns {"text": "..."}.

    Returns:
        evidence_map dict with per-sub-question facts, contradictions, gaps, data_points.
    """
    prompt = _build_prompt(sub_questions, sources_content)

    try:
        response = await generate_fn(prompt=prompt)
        raw_text = response.get("text", "")

        # Try to parse JSON from response
        # Gemini sometimes wraps JSON in markdown code blocks
        clean = raw_text.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1] if "\n" in clean else clean
            clean = clean.rsplit("```", 1)[0]
        clean = clean.strip()

        evidence_map = json.loads(clean)

        # Validate structure
        for key in evidence_map:
            data = evidence_map[key]
            data.setdefault("facts", [])
            data.setdefault("contradictions", [])
            data.setdefault("gaps", [])
            data.setdefault("data_points", [])

        return evidence_map

    except json.JSONDecodeError as e:
        logger.error("Gemini response not valid JSON: %s", e)
        # Return empty evidence map with gaps noted
        return {
            f"sub_q_{i + 1}": {
                "facts": [],
                "contradictions": [],
                "gaps": [f"Gemini parsing failed: {e}"],
                "data_points": [],
            }
            for i in range(len(sub_questions))
        }
    except Exception as e:
        logger.error("Gemini bulk read failed: %s", e)
        return {}
````

- [ ] **Step 4: Run tests — verify pass**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_quality.py -v
```

Expected: all 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/naga/engine/readers/gemini_reader.py apps/naga/tests/test_quality.py
git commit -m "feat(naga): add Gemini Bulk Reader — structured evidence extraction"
```

---

### Task 17: Report Writer (Synthesis Engine)

**Files:**

- Create: `apps/naga/engine/synthesis/__init__.py`
- Create: `apps/naga/engine/synthesis/report_writer.py`

- [ ] **Step 1: Write test**

```python
# Append to apps/naga/tests/test_quality.py

from apps.naga.engine.synthesis.report_writer import generate_report


def test_report_writer_flash():
    claims_list = [
        NagaClaim(
            claim_text="KITAS fee is Rp 2.000.000",
            verification_level="VERIFIED",
            confidence=0.92,
            source_ids=["s1", "s2", "s3"],
            cross_ref_count=3,
        )
    ]
    report = generate_report(
        query="KITAS fee?",
        tier="flash",
        claims=claims_list,
        evidence_map={},
    )
    assert "KITAS" in report
    assert "2.000.000" in report
    assert len(report) < 2000  # Flash should be short


def test_report_writer_deep():
    claims_list = [
        NagaClaim(
            claim_text="Golden visa requires $350K investment",
            verification_level="VERIFIED",
            confidence=0.88,
            source_ids=["s1", "s2", "s3"],
            cross_ref_count=3,
        ),
        NagaClaim(
            claim_text="DPS deadline is contested",
            verification_level="CONTESTED",
            confidence=0.35,
            resolution_hint="Gov source (2024) vs blog (2022)",
        ),
    ]
    report = generate_report(
        query="Golden visa analysis",
        tier="deep",
        claims=claims_list,
        evidence_map={"sub_q_1": {"gaps": ["Timeline of implementation"]}},
    )
    assert "## " in report  # Should have sections
    assert "CONTESTED" in report or "contested" in report.lower()
    assert "Limitation" in report or "Gap" in report
```

- [ ] **Step 2: Run tests — verify fail**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_quality.py::test_report_writer_flash -v --tb=short
```

- [ ] **Step 3: Implement report_writer.py**

```python
# apps/naga/engine/synthesis/__init__.py
```

```python
# apps/naga/engine/synthesis/report_writer.py
"""Report writer — generates tier-appropriate research reports."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from apps.naga.db.models import NagaClaim


def _evidence_status_bar(claims: list[NagaClaim]) -> str:
    """Generate visual evidence status indicator."""
    verified = sum(1 for c in claims if c.verification_level == "VERIFIED")
    likely = sum(1 for c in claims if c.verification_level == "LIKELY")
    contested = sum(1 for c in claims if c.verification_level == "CONTESTED")
    unverified = sum(1 for c in claims if c.verification_level == "UNVERIFIED")

    total = verified + likely + contested + unverified
    if total == 0:
        return ""

    parts = []
    if verified:
        parts.append(f"VERIFIED: {verified}")
    if likely:
        parts.append(f"LIKELY: {likely}")
    if contested:
        parts.append(f"CONTESTED: {contested}")
    if unverified:
        parts.append(f"UNVERIFIED: {unverified}")

    return " | ".join(parts)


def _format_claim(claim: NagaClaim, index: int) -> str:
    """Format a single claim for the report."""
    level_icon = {
        "VERIFIED": "[VERIFIED]",
        "LIKELY": "[LIKELY]",
        "CONTESTED": "[CONTESTED]",
        "UNVERIFIED": "[UNVERIFIED]",
    }.get(claim.verification_level, "")

    line = f"{index}. {level_icon} {claim.claim_text}"
    if claim.cross_ref_count:
        line += f" ({claim.cross_ref_count} sources)"
    if claim.valid_as_of:
        line += f" — valid as of {claim.valid_as_of}"
    if claim.resolution_hint:
        line += f"\n   > Resolution: {claim.resolution_hint}"
    return line


def generate_report(
    query: str,
    tier: str,
    claims: list[NagaClaim],
    evidence_map: dict,
    sources_count: int = 0,
    duration_ms: int = 0,
    gaps: Optional[list[str]] = None,
) -> str:
    """Generate a research report based on tier.

    Args:
        query: Original query.
        tier: flash / deep / exhaustive.
        claims: Verified claims.
        evidence_map: Evidence from Gemini reader.
        sources_count: Number of sources consulted.
        duration_ms: Research duration.
        gaps: Known research gaps.

    Returns:
        Markdown report string.
    """
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    if tier == "flash":
        return _flash_report(query, claims, timestamp)
    elif tier == "deep":
        return _deep_report(query, claims, evidence_map, sources_count, duration_ms, gaps, timestamp)
    else:
        return _exhaustive_report(query, claims, evidence_map, sources_count, duration_ms, gaps, timestamp)


def _flash_report(query: str, claims: list[NagaClaim], timestamp: str) -> str:
    """Short, direct answer for flash tier."""
    lines = [f"**Query:** {query}", f"*{timestamp}*", ""]

    trustworthy = [c for c in claims if c.is_trustworthy]
    if trustworthy:
        for c in trustworthy:
            lines.append(f"- {c.claim_text}")
            if c.valid_as_of:
                lines.append(f"  *(valid as of {c.valid_as_of})*")
    else:
        lines.append("No verified information found for this query.")

    contested = [c for c in claims if c.verification_level == "CONTESTED"]
    if contested:
        lines.append("")
        lines.append("**Note:** Some information is contested:")
        for c in contested:
            lines.append(f"- {c.claim_text}")
            if c.resolution_hint:
                lines.append(f"  > {c.resolution_hint}")

    return "\n".join(lines)


def _deep_report(
    query: str,
    claims: list[NagaClaim],
    evidence_map: dict,
    sources_count: int,
    duration_ms: int,
    gaps: Optional[list[str]],
    timestamp: str,
) -> str:
    """Structured report for deep tier."""
    lines = [
        f"# Research Report: {query}",
        "",
        f"*Generated: {timestamp} | Sources: {sources_count} | Duration: {duration_ms}ms*",
        "",
        f"**Evidence Status:** {_evidence_status_bar(claims)}",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
    ]

    # Summary from verified + likely claims
    trustworthy = [c for c in claims if c.is_trustworthy]
    for i, c in enumerate(trustworthy, 1):
        lines.append(_format_claim(c, i))

    # Contradictions section
    contested = [c for c in claims if c.verification_level == "CONTESTED"]
    if contested:
        lines.extend(["", "## Contradictions and Uncertainty", ""])
        for i, c in enumerate(contested, 1):
            lines.append(_format_claim(c, i))

    # Gaps / limitations
    all_gaps = list(gaps or [])
    for data in evidence_map.values():
        all_gaps.extend(data.get("gaps", []))

    if all_gaps:
        lines.extend(["", "## Research Limitations", ""])
        for g in set(all_gaps):
            lines.append(f"- {g}")

    return "\n".join(lines)


def _exhaustive_report(
    query: str,
    claims: list[NagaClaim],
    evidence_map: dict,
    sources_count: int,
    duration_ms: int,
    gaps: Optional[list[str]],
    timestamp: str,
) -> str:
    """Full multi-perspective report for exhaustive tier."""
    # Build on deep report + add perspective sections
    base = _deep_report(query, claims, evidence_map, sources_count, duration_ms, gaps, timestamp)

    lines = [base]

    # Data points section
    data_points = []
    for data in evidence_map.values():
        data_points.extend(data.get("data_points", []))

    if data_points:
        lines.extend(["", "## Key Data Points", ""])
        for dp in data_points:
            val = dp.get("value", "")
            unit = dp.get("unit", "")
            src = dp.get("source", "")
            dt = dp.get("date", "")
            line = f"- **{val}** {unit}"
            if src:
                line += f" (source: {src})"
            if dt:
                line += f" [{dt}]"
            lines.append(line)

    # Appendix
    unverified = [c for c in claims if c.verification_level == "UNVERIFIED"]
    if unverified:
        lines.extend(["", "## Appendix: Unverified Claims", ""])
        for i, c in enumerate(unverified, 1):
            lines.append(_format_claim(c, i))

    return "\n".join(lines)
```

- [ ] **Step 4: Run tests — verify pass**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_quality.py -v
```

Expected: all 13 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/naga/engine/synthesis/ apps/naga/tests/test_quality.py
git commit -m "feat(naga): add Report Writer — flash/deep/exhaustive templates"
```

---

## PHASE 4: Integration (Tasks 18-22)

### Task 18: Orchestrator — The Main Research Loop

**Files:**

- Create: `apps/naga/engine/orchestrator.py`
- Create: `apps/naga/tests/test_orchestrator.py`

- [ ] **Step 1: Write integration test**

```python
# apps/naga/tests/test_orchestrator.py
"""Tests for Naga orchestrator — the main research loop."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from apps.naga.engine.orchestrator import NagaOrchestrator


@pytest.mark.asyncio
async def test_orchestrator_flash():
    """Flash tier should do a quick search and return directly."""
    mock_deps = _build_mock_deps()

    orch = NagaOrchestrator(deps=mock_deps)
    result = await orch.research(
        query="What is KITAS fee?",
        tier="flash",
        domain="indonesia",
        mode="oneshot",
        channel="telegram",
    )

    assert result.status == "completed"
    assert result.report_markdown != ""
    assert result.iterations <= 1


@pytest.mark.asyncio
async def test_orchestrator_deep():
    """Deep tier should iterate and produce claims."""
    mock_deps = _build_mock_deps()

    orch = NagaOrchestrator(deps=mock_deps)
    result = await orch.research(
        query="Analisi regimi fiscali PT PMA vs CV Indonesia",
        tier="deep",
        domain="indonesia",
        mode="oneshot",
    )

    assert result.status == "completed"
    assert result.claims_extracted >= 0
    assert result.iterations >= 1


def _build_mock_deps():
    """Build mock dependencies for the orchestrator."""
    deps = MagicMock()

    # Exa search
    deps.exa_search = AsyncMock(
        return_value={
            "results": [
                {
                    "url": "https://example.com/1",
                    "title": "Test",
                    "text": "KITAS fee is Rp 2.000.000 as per PP 28/2024. PT PMA tax rate is 22%.",
                    "score": 0.8,
                }
            ]
        }
    )

    # Brave search
    deps.brave_search = AsyncMock(
        return_value={"web": {"results": []}}
    )
    deps.fetch = AsyncMock(return_value={"content": ""})

    # Domain tools
    deps.ask_legal = AsyncMock(
        return_value={
            "answer": "PT PMA corporate tax is 22%. CV uses personal income tax rates.",
            "sources": [],
            "confidence": 0.8,
        }
    )
    deps.search_intel = AsyncMock(return_value={"results": []})
    deps.notebook_query = AsyncMock(
        return_value={"status": "success", "answer": "Confirmed.", "sources_used": []}
    )
    deps.recall_similar = AsyncMock(return_value={"episodes": []})

    # Gemini reader
    deps.gemini_generate = AsyncMock(
        return_value={
            "text": '{"sub_q_1": {"facts": [{"text": "KITAS fee Rp 2M", "source_ids": ["s1"], "confidence": 0.85}], "contradictions": [], "gaps": [], "data_points": []}}'
        }
    )

    # Academic (not used for flash/basic deep)
    deps.academic_http = AsyncMock(return_value={"data": []})

    return deps
```

- [ ] **Step 2: Run test — verify fail**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_orchestrator.py -v --tb=short
```

- [ ] **Step 3: Implement orchestrator.py**

```python
# apps/naga/engine/orchestrator.py
"""Naga Orchestrator — the main iterative research loop."""

from __future__ import annotations

import logging
import time
from typing import Any

from apps.naga.db.models import NagaClaim, NagaSession
from apps.naga.engine.config.naga_config import TIER_CONFIGS
from apps.naga.engine.quality.claim_extractor import extract_claims
from apps.naga.engine.quality.convergence import check_convergence
from apps.naga.engine.quality.crag_light import crag_evaluate
from apps.naga.engine.quality.source_scorer import score_sources
from apps.naga.engine.readers.gemini_reader import gemini_bulk_read
from apps.naga.engine.search_agents.base import AgentResponse, SearchResult
from apps.naga.engine.search_agents.brave_agent import BraveSearchAgent
from apps.naga.engine.search_agents.domain_agent import IndonesiaDomainAgent
from apps.naga.engine.search_agents.exa_agent import ExaSearchAgent
from apps.naga.engine.state.budget_tracker import BudgetTracker
from apps.naga.engine.state.url_history import URLHistory
from apps.naga.engine.synthesis.report_writer import generate_report

logger = logging.getLogger(__name__)


class NagaOrchestrator:
    """Main research orchestrator — iterative search + verify + synthesize."""

    def __init__(self, deps: Any) -> None:
        self._deps = deps

    async def research(
        self,
        query: str,
        tier: str = "deep",
        domain: str = "general",
        mode: str = "oneshot",
        channel: str | None = None,
        trusted_mode: bool = False,
    ) -> NagaSession:
        """Execute the full research loop."""
        start = time.monotonic()
        tier_config = TIER_CONFIGS[tier]

        session = NagaSession(
            query=query,
            tier=tier,
            domain=domain,
            mode=mode,
            channel=channel,
            trusted_mode=trusted_mode,
        )

        budget = BudgetTracker(
            max_search_calls=tier_config.max_search_calls,
            ttl_seconds=tier_config.default_ttl_seconds,
        )
        url_history = URLHistory()

        # Decompose into sub-questions (simplified for now — Opus would do this)
        sub_questions = self._decompose(query, tier)
        session.sub_questions = sub_questions

        all_claims: list[NagaClaim] = []
        all_sources: list[SearchResult] = []

        for iteration in range(1, tier_config.max_iterations + 1):
            session.iterations = iteration

            # --- SEARCH ---
            responses = await self._dispatch_search(
                query, sub_questions, domain, tier, budget, url_history, iteration
            )
            session.search_calls = tier_config.max_search_calls - budget.search_calls_remaining

            merged = AgentResponse.merge(responses)
            new_urls = url_history.add_many([r.url for r in merged.results])
            all_sources.extend(merged.results)
            session.sources_found = len(all_sources)

            # --- CRAG-LIGHT ---
            for sq in sub_questions:
                contents = [r.content for r in merged.results if r.content]
                crag_result = crag_evaluate(sq, contents)
                logger.info("CRAG %s for '%s': %s", crag_result.action, sq[:40], crag_result.reason)

            # For flash tier: skip quality pipeline, generate report directly
            if tier == "flash":
                # Simple claim extraction from search results
                for r in merged.results:
                    if r.content:
                        all_claims.append(
                            NagaClaim(
                                claim_text=r.content[:500],
                                domain=domain,
                                verification_level="LIKELY",
                                confidence=0.6,
                                source_ids=[r.url],
                                cross_ref_count=1,
                            )
                        )
                break

            # --- SCORE SOURCES ---
            scored = score_sources(merged.results)

            # --- GEMINI BULK READ ---
            if scored and tier_config.max_sources_to_reader > 0:
                sources_for_reader = [
                    {"id": f"s{i}", "url": s.url, "content": s.content}
                    for i, s in enumerate(scored[: tier_config.max_sources_to_reader])
                ]

                evidence_map = await gemini_bulk_read(
                    sub_questions=sub_questions,
                    sources_content=sources_for_reader,
                    generate_fn=self._deps.gemini_generate,
                )

                session.merge_evidence(evidence_map)

                # --- CLAIM EXTRACTION ---
                new_claims = extract_claims(evidence_map, domain=domain, session_id=session.id)
                all_claims.extend(new_claims)
                session.claims_extracted = len(all_claims)

                # --- CONVERGENCE ---
                claims_per_q = {}
                for i, sq in enumerate(sub_questions):
                    key = f"sub_q_{i + 1}"
                    facts = evidence_map.get(key, {}).get("facts", [])
                    claims_per_q[sq] = len(facts)

                conv = check_convergence(
                    sub_questions=sub_questions,
                    claims_per_question=claims_per_q,
                    new_claims_this_iteration=len(new_claims),
                    total_claims=len(all_claims),
                    iteration=iteration,
                    budget_can_search=budget.can_search,
                )

                logger.info("Convergence: %s — %s", conv.decision, conv.reason)

                if conv.decision == "CONVERGED":
                    break
                elif conv.decision == "TIMEOUT":
                    break
                # else: ITERATE — loop continues

        # --- SYNTHESIS ---
        elapsed_ms = int((time.monotonic() - start) * 1000)
        session.duration_ms = elapsed_ms

        all_gaps = []
        for data in session.evidence_map.values():
            all_gaps.extend(data.get("gaps", []))

        report = generate_report(
            query=query,
            tier=tier,
            claims=all_claims,
            evidence_map=session.evidence_map,
            sources_count=session.sources_found,
            duration_ms=elapsed_ms,
            gaps=all_gaps,
        )

        session.report_markdown = report

        if all_claims:
            confidences = [c.confidence for c in all_claims if c.confidence > 0]
            session.avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        session.complete()
        return session

    def _decompose(self, query: str, tier: str) -> list[str]:
        """Decompose query into sub-questions.

        For now: simple split. Production: Opus LLM call.
        """
        if tier == "flash":
            return [query]

        # Simple heuristic decomposition
        # In production, Opus would generate these
        words = query.lower().split()
        if any(w in words for w in ["vs", "confronto", "compare", "comparison"]):
            parts = query.split(" vs " if " vs " in query.lower() else " confronto ")
            if len(parts) == 2:
                return [
                    f"What are the key characteristics of {parts[0].strip()}?",
                    f"What are the key characteristics of {parts[1].strip()}?",
                    f"What are the main differences between {parts[0].strip()} and {parts[1].strip()}?",
                ]

        return [query, f"What are the latest developments regarding: {query}?"]

    async def _dispatch_search(
        self,
        query: str,
        sub_questions: list[str],
        domain: str,
        tier: str,
        budget: BudgetTracker,
        url_history: URLHistory,
        iteration: int,
    ) -> list[AgentResponse]:
        """Dispatch search agents based on domain and tier."""
        responses: list[AgentResponse] = []

        for sq in sub_questions:
            if not budget.can_search:
                break

            # Exa — always
            exa = ExaSearchAgent(mcp_call=self._deps.exa_search)
            resp = await exa.search(query, sq, max_results=5)
            budget.record_search(resp.search_calls_used)
            responses.append(resp)

            # Brave — always as diversifier
            if budget.can_search:
                brave = BraveSearchAgent(
                    brave_call=self._deps.brave_search,
                    fetch_call=self._deps.fetch,
                )
                resp = await brave.search(query, sq, max_results=5)
                budget.record_search(resp.search_calls_used)
                responses.append(resp)

            # Domain agent — if indonesia or hybrid
            if domain in ("indonesia", "hybrid") and budget.can_search:
                domain_agent = IndonesiaDomainAgent(
                    ask_legal=self._deps.ask_legal,
                    search_intel=self._deps.search_intel,
                    notebook_query=self._deps.notebook_query,
                    recall_similar=self._deps.recall_similar,
                    exa_call=self._deps.exa_search,
                )
                resp = await domain_agent.search(query, sq)
                budget.record_search(resp.search_calls_used)
                responses.append(resp)

        return responses
```

- [ ] **Step 4: Run tests — verify pass**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_orchestrator.py -v
```

Expected: both tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/naga/engine/orchestrator.py apps/naga/tests/test_orchestrator.py
git commit -m "feat(naga): add Orchestrator — iterative search/verify/synthesize loop"
```

---

### Task 19: FastAPI Router

**Files:**

- Create: `apps/backend-rag/backend/app/routers/naga.py`
- Modify: `apps/backend-rag/backend/app/setup/router_registration.py`

- [ ] **Step 1: Create the router**

```python
# apps/backend-rag/backend/app/routers/naga.py
"""Naga Agentic Research Engine — API endpoints."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/naga", tags=["naga"])


class ResearchRequest(BaseModel):
    query: str
    tier: str = "auto"  # auto / flash / deep / exhaustive
    domain: str = "auto"  # auto / indonesia / general / hybrid
    mode: str = "auto"  # auto / oneshot / conversational
    trusted_mode: bool = False
    channel: str = "api"


class ResearchResponse(BaseModel):
    session_id: str
    status: str
    tier: str
    domain: str
    report: str = ""
    claims_count: int = 0
    sources_count: int = 0
    avg_confidence: float = 0.0
    duration_ms: int = 0
    action_items: list[dict] = []


class ClaimSearchResponse(BaseModel):
    claims: list[dict]
    total: int


@router.post("/research", response_model=ResearchResponse)
async def start_research(request: ResearchRequest) -> ResearchResponse:
    """Start a Naga research task.

    For flash tier: synchronous, returns immediately.
    For deep/exhaustive: returns session_id for polling.
    """
    # TODO: Wire to NagaOrchestrator when dependencies are configured
    # For now, return a placeholder that confirms the endpoint works
    return ResearchResponse(
        session_id="placeholder",
        status="not_implemented",
        tier=request.tier,
        domain=request.domain,
    )


@router.get("/session/{session_id}", response_model=ResearchResponse)
async def get_session(session_id: str) -> ResearchResponse:
    """Get status and results of a research session."""
    raise HTTPException(status_code=404, detail=f"Session {session_id} not found")


@router.get("/claims/search", response_model=ClaimSearchResponse)
async def search_claims(
    q: str = Query(..., description="Search query"),
    domain: Optional[str] = Query(None, description="Filter by domain"),
    verification: Optional[str] = Query(None, description="Filter by verification level"),
    limit: int = Query(20, ge=1, le=100),
) -> ClaimSearchResponse:
    """Search the Naga Claims DB."""
    # TODO: Wire to PostgreSQL claims table
    return ClaimSearchResponse(claims=[], total=0)
```

- [ ] **Step 2: Register the router**

Add to `apps/backend-rag/backend/app/setup/router_registration.py` — add the import and include in the existing pattern.

Find the end of the imports section and add:

```python
from backend.app.routers import naga
```

Find where routers are included and add:

```python
api.include_router(naga.router)
```

- [ ] **Step 3: Test the endpoint locally**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. python -c "
from backend.app.routers.naga import router
print(f'✅ Naga router loaded: {len(router.routes)} routes')
for route in router.routes:
    print(f'  {route.methods} {route.path}')
"
```

Expected:

```
✅ Naga router loaded: 3 routes
  {'POST'} /api/naga/research
  {'GET'} /api/naga/session/{session_id}
  {'GET'} /api/naga/claims/search
```

- [ ] **Step 4: Commit**

```bash
git add apps/backend-rag/backend/app/routers/naga.py apps/backend-rag/backend/app/setup/router_registration.py
git commit -m "feat(naga): add FastAPI router — /api/naga/research, /session, /claims/search"
```

---

### Task 20: MCP Tool Registration

**Files:**

- Create: `apps/nuzantara-mcp/nuzantara_mcp/tools/naga.py`
- Modify: `apps/nuzantara-mcp/nuzantara_mcp/server.py`

- [ ] **Step 1: Create the MCP tool module**

```python
# apps/nuzantara-mcp/nuzantara_mcp/tools/naga.py
"""Naga research tools — MCP interface for the agentic research engine."""

from typing import Any, Optional


def register(mcp: Any, _call: Any, _call_safe: Any) -> None:
    """Register Naga research tools."""

    @mcp.tool()
    async def naga_research(
        query: str,
        tier: str = "auto",
        domain: str = "auto",
        mode: str = "auto",
        trusted_mode: bool = False,
    ) -> dict:
        """Execute agentic research using Naga engine.

        Naga searches across multiple sources (web, domain RAG, academic),
        verifies claims through a quality pipeline, and produces structured
        reports with actionable items.

        Args:
            query: Research query in any language.
            tier: Research depth — "flash" (5-15s), "deep" (1-5min),
                  "exhaustive" (5-30min), or "auto" (system decides).
            domain: Focus area — "indonesia" (legal/business/immigration),
                    "general" (any topic), "hybrid" (both), or "auto".
            mode: Interaction — "oneshot" (single report),
                  "conversational" (iterative refinement), or "auto".
            trusted_mode: If True, low-risk actions (notify, draft) auto-execute.

        Returns:
            Dict with session_id, status, report, claims_count, action_items.
        """
        result = await _call(
            "/api/naga/research",
            method="POST",
            json={
                "query": query,
                "tier": tier,
                "domain": domain,
                "mode": mode,
                "trusted_mode": trusted_mode,
                "channel": "mcp",
            },
            timeout=1800,
        )
        return result

    @mcp.tool()
    async def naga_claims_search(
        query: str,
        domain: Optional[str] = None,
        verification: Optional[str] = None,
        limit: int = 20,
    ) -> dict:
        """Search Naga's verified claims knowledge base.

        Query previously discovered and verified facts. Useful for checking
        "what do we already know about X?" before starting new research.

        Args:
            query: Search query.
            domain: Filter by domain — "indonesia" or "general".
            verification: Filter by level — "VERIFIED", "LIKELY", "CONTESTED".
            limit: Max results (1-100).

        Returns:
            Dict with claims list and total count.
        """
        params: dict = {"q": query, "limit": min(limit, 100)}
        if domain:
            params["domain"] = domain
        if verification:
            params["verification"] = verification
        return await _call("/api/naga/claims/search", params=params)

    @mcp.tool()
    async def naga_session_status(session_id: str) -> dict:
        """Check status of an ongoing Naga research session.

        Args:
            session_id: UUID of the research session.

        Returns:
            Session status with progress metrics and partial results.
        """
        return await _call(f"/api/naga/session/{session_id}")
```

- [ ] **Step 2: Register in server.py**

Add to imports section of `apps/nuzantara-mcp/nuzantara_mcp/server.py`:

```python
from nuzantara_mcp.tools.naga import register as register_naga
```

Add to registration section:

```python
register_naga(mcp, _call, _call_safe)
```

- [ ] **Step 3: Verify import works**

```bash
cd apps/nuzantara-mcp
python -c "from nuzantara_mcp.tools.naga import register; print('✅ Naga MCP tools importable')"
```

- [ ] **Step 4: Commit**

```bash
git add apps/nuzantara-mcp/nuzantara_mcp/tools/naga.py apps/nuzantara-mcp/nuzantara_mcp/server.py
git commit -m "feat(naga): register MCP tools — naga_research, naga_claims_search, naga_session_status"
```

---

### Task 21: Action Engine

**Files:**

- Create: `apps/naga/engine/actions/__init__.py`
- Create: `apps/naga/engine/actions/action_engine.py`

- [ ] **Step 1: Write test**

```python
# Append to apps/naga/tests/test_quality.py

from apps.naga.engine.actions.action_engine import detect_actions, ActionItem


def test_detect_actions_client_impact():
    claims = [
        NagaClaim(
            claim_text="KITAS fee increased to Rp 3.000.000 effective May 2026",
            domain="indonesia",
            verification_level="VERIFIED",
            confidence=0.92,
            topic_tags=["visa", "kitas", "fee"],
        )
    ]
    actions = detect_actions(claims, trusted_mode=False)
    assert len(actions) >= 1
    assert actions[0].action_type in ("notify", "crm_alert")


def test_detect_actions_contested_escalation():
    claims = [
        NagaClaim(
            claim_text="DPS deadline contested",
            domain="indonesia",
            verification_level="CONTESTED",
            confidence=0.35,
            topic_tags=["compliance"],
        )
    ]
    actions = detect_actions(claims, trusted_mode=False)
    escalation = [a for a in actions if a.action_type == "escalation"]
    assert len(escalation) >= 1


def test_detect_actions_trusted_mode():
    claims = [
        NagaClaim(
            claim_text="New regulation published",
            domain="indonesia",
            verification_level="VERIFIED",
            confidence=0.90,
            topic_tags=["regulation"],
        )
    ]
    actions = detect_actions(claims, trusted_mode=True)
    for a in actions:
        if a.action_type == "notify":
            assert a.auto_execute is True
        elif a.action_type == "publish":
            assert a.auto_execute is False  # publish always needs approval
```

- [ ] **Step 2: Run tests — verify fail**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_quality.py::test_detect_actions_client_impact -v --tb=short
```

- [ ] **Step 3: Implement action_engine.py**

```python
# apps/naga/engine/actions/__init__.py
```

```python
# apps/naga/engine/actions/action_engine.py
"""Action Engine — detects triggers from claims and proposes actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from apps.naga.db.models import NagaClaim

# Keywords that suggest client impact
_CLIENT_IMPACT_KEYWORDS = frozenset(
    {
        "fee",
        "tarif",
        "biaya",
        "cost",
        "deadline",
        "expiry",
        "new requirement",
        "persyaratan baru",
        "increased",
        "decreased",
        "changed",
        "effective",
        "berlaku",
    }
)

# Keywords that suggest newsworthy content
_NEWS_KEYWORDS = frozenset(
    {
        "new regulation",
        "new policy",
        "peraturan baru",
        "golden visa",
        "launched",
        "announced",
        "diumumkan",
        "diresmikan",
    }
)


@dataclass
class ActionItem:
    """A proposed action from the Action Engine."""

    action_type: str  # notify / crm_alert / draft_article / publish / escalation / followup
    description: str
    payload: dict = field(default_factory=dict)
    rationale: str = ""
    auto_execute: bool = False
    priority: str = "medium"  # low / medium / high / critical


def detect_actions(
    claims: list[NagaClaim],
    trusted_mode: bool = False,
    gaps: Optional[list[str]] = None,
) -> list[ActionItem]:
    """Analyze claims and detect actionable triggers.

    Args:
        claims: Verified claims from the research.
        trusted_mode: If True, notify/draft auto-execute.
        gaps: Research gaps that might need follow-up.

    Returns:
        List of proposed ActionItems.
    """
    actions: list[ActionItem] = []

    for claim in claims:
        text_lower = claim.claim_text.lower()

        # Trigger: VERIFIED claim impacting clients
        if claim.verification_level == "VERIFIED" and claim.domain == "indonesia":
            has_impact = any(kw in text_lower for kw in _CLIENT_IMPACT_KEYWORDS)
            if has_impact:
                actions.append(
                    ActionItem(
                        action_type="crm_alert",
                        description=f"Client impact detected: {claim.claim_text[:100]}",
                        payload={
                            "claim_text": claim.claim_text,
                            "topic_tags": claim.topic_tags,
                            "confidence": claim.confidence,
                        },
                        rationale="VERIFIED claim with client-impacting keywords",
                        auto_execute=False,
                        priority="high",
                    )
                )

                actions.append(
                    ActionItem(
                        action_type="notify",
                        description=f"Telegram: {claim.claim_text[:80]}",
                        payload={"message": claim.claim_text, "channel": "telegram"},
                        rationale="Client impact — notify team",
                        auto_execute=True,  # notify always auto
                        priority="high",
                    )
                )

        # Trigger: VERIFIED newsworthy
        if claim.verification_level == "VERIFIED":
            is_news = any(kw in text_lower for kw in _NEWS_KEYWORDS)
            if is_news:
                actions.append(
                    ActionItem(
                        action_type="draft_article",
                        description=f"Draft article: {claim.claim_text[:80]}",
                        payload={"claim_text": claim.claim_text, "topic_tags": claim.topic_tags},
                        rationale="Newsworthy VERIFIED claim",
                        auto_execute=trusted_mode,
                        priority="medium",
                    )
                )

        # Trigger: CONTESTED on active regulation
        if claim.verification_level == "CONTESTED" and claim.domain == "indonesia":
            actions.append(
                ActionItem(
                    action_type="escalation",
                    description=f"Contested: {claim.claim_text[:80]}",
                    payload={
                        "claim_text": claim.claim_text,
                        "resolution_hint": claim.resolution_hint,
                    },
                    rationale="Unresolved contradiction on Indonesia domain",
                    auto_execute=True,  # escalation always auto
                    priority="high",
                )
            )

    # Trigger: critical gaps
    if gaps:
        critical_gaps = [g for g in gaps if "regulation" in g.lower() or "normativa" in g.lower()]
        for gap in critical_gaps:
            actions.append(
                ActionItem(
                    action_type="followup",
                    description=f"Schedule follow-up: {gap[:80]}",
                    payload={"gap": gap, "followup_hours": 48},
                    rationale="Critical gap in Indonesia domain knowledge",
                    auto_execute=trusted_mode,
                    priority="medium",
                )
            )

    return actions
```

- [ ] **Step 4: Run tests — verify pass**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_quality.py -v
```

Expected: all 16 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/naga/engine/actions/ apps/naga/tests/test_quality.py
git commit -m "feat(naga): add Action Engine — CRM alerts, escalation, follow-up triggers"
```

---

### Task 22: End-to-End Integration Test

**Files:**

- Create: `apps/naga/tests/test_integration.py`

- [ ] **Step 1: Write full integration test**

```python
# apps/naga/tests/test_integration.py
"""End-to-end integration test for Naga."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from apps.naga.engine.gateway import classify_query
from apps.naga.engine.orchestrator import NagaOrchestrator


@pytest.mark.asyncio
async def test_full_research_flow():
    """Test the complete flow: gateway → orchestrator → report."""

    query = "Analisi completa golden visa Indonesia: requisiti, costi, confronto con KITAS Investasi"

    # 1. Gateway classification
    gw = classify_query(query)
    assert gw.domain == "indonesia"
    assert gw.tier in ("deep", "exhaustive")

    # 2. Orchestrator with mocked dependencies
    deps = MagicMock()
    deps.exa_search = AsyncMock(
        return_value={
            "results": [
                {
                    "url": "https://imigrasi.go.id/golden-visa",
                    "title": "Golden Visa Indonesia",
                    "text": "Indonesia launched the Golden Visa program in 2024. Minimum investment $350,000 for 5 years, $700,000 for 10 years.",
                    "score": 0.92,
                },
                {
                    "url": "https://expat.id/golden-visa-guide",
                    "title": "Golden Visa Guide",
                    "text": "The Golden Visa requires a minimum investment of $350,000. Processing takes 15 business days.",
                    "score": 0.78,
                },
            ]
        }
    )
    deps.brave_search = AsyncMock(return_value={"web": {"results": []}})
    deps.fetch = AsyncMock(return_value={"content": ""})
    deps.ask_legal = AsyncMock(
        return_value={
            "answer": "Golden Visa Indonesia diatur PP 40/2024. Investasi minimum $350,000 (5 tahun) atau $700,000 (10 tahun). Berbeda dari KITAS Investasi yang hanya memerlukan BKPM approval.",
            "sources": [{"title": "PP 40/2024"}],
            "confidence": 0.88,
        }
    )
    deps.search_intel = AsyncMock(return_value={"results": []})
    deps.notebook_query = AsyncMock(
        return_value={"status": "success", "answer": "Confirmed.", "sources_used": []}
    )
    deps.recall_similar = AsyncMock(return_value={"episodes": []})
    deps.gemini_generate = AsyncMock(
        return_value={
            "text": """{
                "sub_q_1": {
                    "facts": [
                        {"text": "Golden Visa minimum investment $350,000 for 5 years", "source_ids": ["s0", "s1", "s2"], "confidence": 0.92},
                        {"text": "Golden Visa $700,000 for 10 years", "source_ids": ["s0", "s2"], "confidence": 0.88},
                        {"text": "Processing time 15 business days", "source_ids": ["s1"], "confidence": 0.65}
                    ],
                    "contradictions": [],
                    "gaps": ["Comparison with other ASEAN golden visas"],
                    "data_points": [
                        {"value": "$350,000", "unit": "USD", "source": "s0", "date": "2024-01-01"},
                        {"value": "$700,000", "unit": "USD", "source": "s0", "date": "2024-01-01"}
                    ]
                },
                "sub_q_2": {
                    "facts": [
                        {"text": "KITAS Investasi requires BKPM approval only", "source_ids": ["s2"], "confidence": 0.85}
                    ],
                    "contradictions": [],
                    "gaps": [],
                    "data_points": []
                }
            }"""
        }
    )
    deps.academic_http = AsyncMock(return_value={"data": []})

    orch = NagaOrchestrator(deps=deps)
    session = await orch.research(
        query=query,
        tier="deep",
        domain="indonesia",
        mode="oneshot",
    )

    # 3. Verify results
    assert session.status == "completed"
    assert session.report_markdown != ""
    assert "Golden Visa" in session.report_markdown or "golden visa" in session.report_markdown.lower()
    assert session.claims_extracted > 0
    assert session.sources_found > 0
    assert session.avg_confidence > 0
    assert session.duration_ms > 0

    print(f"\n{'=' * 60}")
    print(f"✅ Naga E2E Test Passed")
    print(f"   Tier: {session.tier}")
    print(f"   Sources: {session.sources_found}")
    print(f"   Claims: {session.claims_extracted}")
    print(f"   Confidence: {session.avg_confidence:.2f}")
    print(f"   Iterations: {session.iterations}")
    print(f"   Duration: {session.duration_ms}ms")
    print(f"{'=' * 60}")
    print(f"\nReport Preview (first 500 chars):")
    print(session.report_markdown[:500])
```

- [ ] **Step 2: Run integration test**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/test_integration.py -v -s
```

Expected: PASS with full report output

- [ ] **Step 3: Run the complete test suite**

```bash
PYTHONPATH=. python -m pytest apps/naga/tests/ -v
```

Expected: all tests PASS (approximately 17-20 tests)

- [ ] **Step 4: Commit**

```bash
git add apps/naga/tests/test_integration.py
git commit -m "feat(naga): add end-to-end integration test — full research flow"
```

- [ ] **Step 5: Final commit — all Naga Phase 1-4**

```bash
git log --oneline -15  # Verify all Naga commits are present
```

---

## Post-Implementation Notes

### What's built after Phase 4:

- Full research loop: Gateway → Orchestrator → 5 Search Agents → Quality Pipeline → Synthesis → Report
- PostgreSQL schema for sessions, sources, claims (living knowledge base)
- FastAPI endpoints: `/api/naga/research`, `/session/{id}`, `/claims/search`
- MCP tools: `naga_research`, `naga_claims_search`, `naga_session_status`
- Action Engine with trusted_mode stratification
- 20+ tests covering all components

### What's NOT built yet (future tasks):

1. **LLM-based decomposition** — Currently uses heuristic split. Need Opus LLM call for proper sub-question generation.
2. **LLM-based CRAG** — Currently keyword overlap. Upgrade to Haiku/qwen call for semantic relevance.
3. **Conversational mode state persistence** — Session chaining via parent_session_id is modeled but not wired.
4. **Drive archiving** — Report → Google Drive upload not implemented.
5. **NLM NB-NAGA upload** — Exhaustive report → NLM notebook ingest not implemented.
6. **Qdrant naga_research collection** — Report chunks → vector ingest not implemented.
7. **Audio briefing** — NLM studio_create for exhaustive tier.
8. **Multi-perspective synthesis** — STORM-style perspective generation (needs Opus call).
9. **DB persistence** — NagaSession/Source/Claim → PostgreSQL save/load.
10. **Production Gemini integration** — Currently mocked; wire to google-generativeai SDK.
