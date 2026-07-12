# T4 Social Media Monitor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a T4 tier social/web monitor that ingests Indonesian government immigration content (RSS feeds, website scraping, X/Twitter) into NLM NB-2 every 6 hours, with a hard budget cap of 11 slots and a 3-layer relevance filter.

**Architecture:** Two new files in `apps/evaluator/nlm_deep_research/` — `t4_monitor.py` (fetch → filter → SVS → ingest logic) and `t4_state.py` (JSON-backed state with dedup set, CB, PID lock). A cron shell script wraps the Python entrypoint. The module follows the same patterns as `circuit_breaker.py` and `source_management.py` already in the package.

**Tech Stack:** Python 3.11+, `httpx` (async HTTP), `feedparser` (RSS), `beautifulsoup4` (HTML scraping), `openai` (embeddings — text-embedding-3-small), `anthropic` (Haiku Layer-3 classifier), `asyncio` subprocess (nlm CLI ingest). All dependencies already present or listed below.

---

## File Map

| Path                                                         | Action     | Responsibility                                   |
| ------------------------------------------------------------ | ---------- | ------------------------------------------------ |
| `apps/evaluator/nlm_deep_research/t4_state.py`               | **Create** | T4State dataclass + JSON persistence + PID lock  |
| `apps/evaluator/nlm_deep_research/t4_monitor.py`             | **Create** | T4Monitor class: fetch/filter/SVS/ingest + CB_T4 |
| `apps/evaluator/nlm_deep_research/scripts/run_t4_monitor.sh` | **Create** | Cron wrapper with PID lock guard                 |
| `apps/evaluator/nlm_deep_research/__init__.py`               | **Modify** | Export `T4Monitor`, `T4State`                    |
| `tests/nlm_deep_research/test_t4_state.py`                   | **Create** | Unit tests for state persistence + PID lock      |
| `tests/nlm_deep_research/test_t4_filter.py`                  | **Create** | Unit tests for 3-layer relevance filter          |
| `tests/nlm_deep_research/test_t4_svs.py`                     | **Create** | Unit tests for SVS scoring                       |
| `tests/nlm_deep_research/test_t4_cb.py`                      | **Create** | Unit tests for CB_T4 FSM                         |
| `tests/nlm_deep_research/test_t4_monitor.py`                 | **Create** | Integration smoke test (dry-run, mocked NLM)     |

---

## Task 1: State dataclass and JSON persistence

**Files:**

- Create: `apps/evaluator/nlm_deep_research/t4_state.py`
- Create: `tests/nlm_deep_research/test_t4_state.py`

- [ ] **Step 1.1: Write the failing tests**

Create `tests/nlm_deep_research/test_t4_state.py`:

```python
"""Unit tests for T4State persistence and PID lock."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from apps.evaluator.nlm_deep_research.t4_state import T4State, T4StatePersistence


class TestT4StateDefaults:
    def test_fresh_state_has_empty_seen_ids(self):
        state = T4State()
        assert state.seen_ids == set()

    def test_fresh_state_cb_closed(self):
        state = T4State()
        assert state.cb_status == "CLOSED"
        assert state.cb_failure_count == 0

    def test_fresh_state_no_active_sources(self):
        state = T4State()
        assert state.active_t4_sources == []

    def test_fresh_state_x_enabled(self):
        state = T4State()
        assert state.x_enabled is True

    def test_fresh_state_no_pid(self):
        state = T4State()
        assert state.run_lock_pid is None


class TestT4StatePersistence:
    def test_save_and_load_roundtrip(self, tmp_path):
        state_path = tmp_path / "t4_state.json"
        persistence = T4StatePersistence(state_path)

        state = T4State(
            seen_ids={"abc123", "def456"},
            active_t4_sources=["src-1", "src-2"],
            cb_status="CLOSED",
            cb_failure_count=1,
        )
        persistence.save(state)

        loaded = persistence.load()
        assert loaded.seen_ids == {"abc123", "def456"}
        assert loaded.active_t4_sources == ["src-1", "src-2"]
        assert loaded.cb_failure_count == 1

    def test_load_missing_file_returns_fresh_state(self, tmp_path):
        state_path = tmp_path / "nonexistent.json"
        persistence = T4StatePersistence(state_path)
        state = persistence.load()
        assert state.seen_ids == set()

    def test_save_creates_parent_directory(self, tmp_path):
        state_path = tmp_path / "subdir" / "t4_state.json"
        persistence = T4StatePersistence(state_path)
        persistence.save(T4State())
        assert state_path.exists()


class TestT4StateBudget:
    def test_is_over_budget_when_full(self):
        state = T4State(active_t4_sources=["s"] * 11)
        assert state.is_over_budget(max_slots=11) is True

    def test_is_not_over_budget_when_below(self):
        state = T4State(active_t4_sources=["s"] * 10)
        assert state.is_over_budget(max_slots=11) is False

    def test_evict_oldest_removes_first_entry(self):
        state = T4State(active_t4_sources=["old", "mid", "new"])
        evicted = state.evict_oldest()
        assert evicted == "old"
        assert state.active_t4_sources == ["mid", "new"]

    def test_evict_oldest_on_empty_raises(self):
        state = T4State(active_t4_sources=[])
        with pytest.raises(IndexError):
            state.evict_oldest()
```

- [ ] **Step 1.2: Run tests — verify they fail**

```bash
cd /Users/nuzantara/Desktop/nuzantara
PYTHONPATH=. pytest tests/nlm_deep_research/test_t4_state.py -v 2>&1 | tail -20
```

Expected: `ModuleNotFoundError: No module named 'apps.evaluator.nlm_deep_research.t4_state'`

- [ ] **Step 1.3: Implement `t4_state.py`**

Create `apps/evaluator/nlm_deep_research/t4_state.py`:

```python
"""T4 Monitor state — persistence, PID lock, budget tracking.

State is stored as JSON at:
    apps/evaluator/nlm_deep_research/t4_state.json

PID lock prevents concurrent cron runs:
    apps/evaluator/nlm_deep_research/t4.lock
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

logger = logging.getLogger(__name__)

_DEFAULT_STATE_PATH: Path = Path(__file__).resolve().parent / "t4_state.json"
_DEFAULT_LOCK_PATH: Path = Path(__file__).resolve().parent / "t4.lock"

MAX_T4_SLOTS: int = 11
NEWS_HALF_LIFE_DAYS: int = 15


@dataclass
class T4State:
    """Mutable runtime state for the T4 monitor."""

    seen_ids: set[str] = field(default_factory=set)
    active_t4_sources: list[str] = field(default_factory=list)
    last_run_at: Optional[datetime] = None
    cb_status: Literal["CLOSED", "OPEN", "HALF_OPEN"] = "CLOSED"
    cb_failure_count: int = 0
    cb_last_failure: Optional[datetime] = None
    x_enabled: bool = True
    x_enabled_until: Optional[datetime] = None
    run_lock_pid: Optional[int] = None

    def is_over_budget(self, max_slots: int = MAX_T4_SLOTS) -> bool:
        return len(self.active_t4_sources) >= max_slots

    def evict_oldest(self) -> str:
        """Remove and return the oldest (first) active T4 source ID."""
        if not self.active_t4_sources:
            raise IndexError("No active T4 sources to evict")
        return self.active_t4_sources.pop(0)

    def mark_seen(self, article_id: str) -> None:
        self.seen_ids.add(article_id)

    def is_seen(self, article_id: str) -> bool:
        return article_id in self.seen_ids

    def add_source(self, nlm_source_id: str) -> None:
        self.active_t4_sources.append(nlm_source_id)


class T4StatePersistence:
    """Load/save T4State to/from JSON."""

    def __init__(self, path: Path = _DEFAULT_STATE_PATH) -> None:
        self.path = path

    def load(self) -> T4State:
        if not self.path.exists():
            logger.info("t4_state.json not found — returning fresh state")
            return T4State()
        try:
            data = json.loads(self.path.read_text())
            return T4State(
                seen_ids=set(data.get("seen_ids", [])),
                active_t4_sources=data.get("active_t4_sources", []),
                last_run_at=(
                    datetime.fromisoformat(data["last_run_at"])
                    if data.get("last_run_at")
                    else None
                ),
                cb_status=data.get("cb_status", "CLOSED"),
                cb_failure_count=data.get("cb_failure_count", 0),
                cb_last_failure=(
                    datetime.fromisoformat(data["cb_last_failure"])
                    if data.get("cb_last_failure")
                    else None
                ),
                x_enabled=data.get("x_enabled", True),
                x_enabled_until=(
                    datetime.fromisoformat(data["x_enabled_until"])
                    if data.get("x_enabled_until")
                    else None
                ),
                run_lock_pid=data.get("run_lock_pid"),
            )
        except Exception:
            logger.exception("Failed to load t4_state.json — returning fresh state")
            return T4State()

    def save(self, state: T4State) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "seen_ids": sorted(state.seen_ids),
            "active_t4_sources": state.active_t4_sources,
            "last_run_at": state.last_run_at.isoformat() if state.last_run_at else None,
            "cb_status": state.cb_status,
            "cb_failure_count": state.cb_failure_count,
            "cb_last_failure": (
                state.cb_last_failure.isoformat() if state.cb_last_failure else None
            ),
            "x_enabled": state.x_enabled,
            "x_enabled_until": (
                state.x_enabled_until.isoformat() if state.x_enabled_until else None
            ),
            "run_lock_pid": state.run_lock_pid,
        }
        self.path.write_text(json.dumps(data, indent=2))
        logger.debug("t4_state.json saved (%d seen_ids)", len(state.seen_ids))


class T4LockError(Exception):
    """Raised when the PID lock cannot be acquired."""


class T4PIDLock:
    """File-based PID lock preventing concurrent T4 monitor runs."""

    def __init__(self, lock_path: Path = _DEFAULT_LOCK_PATH) -> None:
        self.lock_path = lock_path

    def acquire(self) -> None:
        if self.lock_path.exists():
            pid_str = self.lock_path.read_text().strip()
            try:
                pid = int(pid_str)
                os.kill(pid, 0)  # signal 0 = check if process exists
                raise T4LockError(
                    f"T4 monitor already running (PID {pid}). Exiting."
                )
            except (ProcessLookupError, PermissionError):
                logger.warning("Stale lock (PID %s dead) — cleaning up", pid_str)
                self.lock_path.unlink(missing_ok=True)
        self.lock_path.write_text(str(os.getpid()))

    def release(self) -> None:
        self.lock_path.unlink(missing_ok=True)

    def __enter__(self) -> "T4PIDLock":
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()
```

- [ ] **Step 1.4: Run tests — verify they pass**

```bash
cd /Users/nuzantara/Desktop/nuzantara
PYTHONPATH=. pytest tests/nlm_deep_research/test_t4_state.py -v 2>&1 | tail -25
```

Expected: all 11 tests PASS.

- [ ] **Step 1.5: Commit**

```bash
git add apps/evaluator/nlm_deep_research/t4_state.py tests/nlm_deep_research/test_t4_state.py
git commit -m "feat(t4): add T4State dataclass with JSON persistence and PID lock"
```

---

## Task 2: 3-layer relevance filter

**Files:**

- Create section in: `apps/evaluator/nlm_deep_research/t4_monitor.py` (filter functions only)
- Create: `tests/nlm_deep_research/test_t4_filter.py`

- [ ] **Step 2.1: Write the failing tests**

Create `tests/nlm_deep_research/test_t4_filter.py`:

```python
"""Unit tests for T4 3-layer relevance filter."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from apps.evaluator.nlm_deep_research.t4_monitor import (
    FilterResult,
    T4RelevanceFilter,
)


TIMPORA_TEXT = (
    "Timpora Kuta Selatan Tingkatkan Sinergitas dan Perkuat Pengawasan WNA. "
    "Imigrasi Ngurah Rai melakukan razia terhadap warga negara asing yang overstay."
)

DEPORTATION_TEXT = (
    "Imigrasi Ngurah Rai Deportasi WN Korea Selatan yang terbukti melanggar "
    "izin tinggal. Proses pendeportasian dilakukan sesuai prosedur imigrasi."
)

CEREMONY_TEXT = (
    "Selamat ulang tahun Direktorat Jenderal Imigrasi ke-73. "
    "Acara dihadiri oleh seluruh staf dan pegawai kantor imigrasi Denpasar."
)

GENERIC_SINGLE_HIGH_TEXT = (
    "Pengumuman jadwal libur nasional untuk kantor imigrasi seluruh Indonesia."
)


class TestLayer1KeywordFilter:
    """Layer 1: keyword recall pass/fail."""

    def test_critical_keyword_timpora_passes(self):
        f = T4RelevanceFilter()
        result = f.layer1_keywords(TIMPORA_TEXT)
        assert result is True

    def test_critical_keyword_deportasi_passes(self):
        f = T4RelevanceFilter()
        result = f.layer1_keywords(DEPORTATION_TEXT)
        assert result is True

    def test_two_high_keywords_pass(self):
        f = T4RelevanceFilter()
        text = "Peraturan imigrasi baru mengatur perpanjangan visa KITAS untuk TKA."
        result = f.layer1_keywords(text)
        assert result is True

    def test_single_high_keyword_fails(self):
        f = T4RelevanceFilter()
        result = f.layer1_keywords(GENERIC_SINGLE_HIGH_TEXT)
        assert result is False

    def test_ceremony_text_fails(self):
        f = T4RelevanceFilter()
        result = f.layer1_keywords(CEREMONY_TEXT)
        assert result is False

    def test_empty_text_fails(self):
        f = T4RelevanceFilter()
        result = f.layer1_keywords("")
        assert result is False

    def test_case_insensitive(self):
        f = T4RelevanceFilter()
        result = f.layer1_keywords("TIMPORA DAN DEPORTASI WNA")
        assert result is True


class TestLayer2EmbeddingFilter:
    """Layer 2: embedding cosine similarity (mocked)."""

    @pytest.mark.asyncio
    async def test_high_similarity_passes(self):
        f = T4RelevanceFilter()
        with patch.object(f, "_embed", new=AsyncMock(return_value=[0.9] * 1536)):
            # Mock: dot product of identical vectors = 1.0 (after normalization)
            result = await f.layer2_embedding(TIMPORA_TEXT, cached_ref=[0.9] * 1536)
        assert result >= 0.35

    @pytest.mark.asyncio
    async def test_low_similarity_fails(self):
        f = T4RelevanceFilter()
        # Ceremony text: orthogonal vector (all zeros except one dim)
        ref = [1.0] + [0.0] * 1535
        text_vec = [0.0] * 1535 + [1.0]
        with patch.object(f, "_embed", new=AsyncMock(return_value=text_vec)):
            result = await f.layer2_embedding(CEREMONY_TEXT, cached_ref=ref)
        assert result < 0.35

    @pytest.mark.asyncio
    async def test_borderline_returns_float(self):
        f = T4RelevanceFilter()
        vec = [0.5] * 1536
        with patch.object(f, "_embed", new=AsyncMock(return_value=vec)):
            result = await f.layer2_embedding("some text", cached_ref=vec)
        assert isinstance(result, float)


class TestLayer3HaikuFilter:
    """Layer 3: Haiku classifier for borderline cases."""

    @pytest.mark.asyncio
    async def test_enforcement_article_scores_high(self):
        f = T4RelevanceFilter()
        with patch.object(
            f, "_haiku_classify", new=AsyncMock(return_value=0.85)
        ):
            score = await f.layer3_haiku(DEPORTATION_TEXT)
        assert score >= 0.5

    @pytest.mark.asyncio
    async def test_ceremony_article_scores_low(self):
        f = T4RelevanceFilter()
        with patch.object(
            f, "_haiku_classify", new=AsyncMock(return_value=0.15)
        ):
            score = await f.layer3_haiku(CEREMONY_TEXT)
        assert score < 0.5


class TestFilterPipeline:
    """Full 3-layer pipeline integration."""

    @pytest.mark.asyncio
    async def test_critical_text_returns_admit_no_haiku(self):
        f = T4RelevanceFilter()
        high_sim = [0.9] * 1536
        with patch.object(f, "_embed", new=AsyncMock(return_value=high_sim)):
            result = await f.classify(TIMPORA_TEXT, ref_embedding=high_sim)
        assert result == FilterResult.ADMIT
        # Layer 3 should NOT be invoked (high L1+L2 → skip Haiku)

    @pytest.mark.asyncio
    async def test_ceremony_text_returns_reject(self):
        f = T4RelevanceFilter()
        orth_vec = [0.0] * 1536
        orth_vec[0] = 1.0
        ref_vec = [0.0] * 1536
        ref_vec[1] = 1.0
        with patch.object(f, "_embed", new=AsyncMock(return_value=orth_vec)):
            result = await f.classify(CEREMONY_TEXT, ref_embedding=ref_vec)
        assert result == FilterResult.REJECT
```

- [ ] **Step 2.2: Run tests — verify they fail**

```bash
cd /Users/nuzantara/Desktop/nuzantara
PYTHONPATH=. pytest tests/nlm_deep_research/test_t4_filter.py -v 2>&1 | tail -10
```

Expected: `ModuleNotFoundError: No module named 'apps.evaluator.nlm_deep_research.t4_monitor'`

- [ ] **Step 2.3: Implement the filter module (stub of `t4_monitor.py`)**

Create `apps/evaluator/nlm_deep_research/t4_monitor.py`:

```python
"""T4 Social Media Monitor for NLM NB-2.

Fetches immigration-relevant content from:
  - RSS feeds (Layer 1 sources: ngurahrai, ditjenimigrasi)
  - Government websites (scraping /berita/ pages)
  - X/Twitter v2 API (time-boxed 30 days)

Applies a 3-layer relevance filter, computes SVS, and ingests
ADMIT articles into NLM NB-2 via the nlm CLI.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NB2_ID = "cff93ab0-813a-42f2-a8de-36987e724271"
MAX_T4_SLOTS = 11
CB_T4_FAILURE_THRESHOLD = 3
CB_T4_RECOVERY_MINUTES = 30

CRITICAL_KEYWORDS = [
    "timpora",
    "deportasi",
    "deportation",
    "overstay",
    "blacklist",
    "daftar cekal",
    "visa dicabut",
    "wna ditangkap",
    "razia",
    "pendeportasian",
    "izin tinggal dibatalkan",
    "cegah tangkal",
]

HIGH_KEYWORDS = [
    "kitas",
    "kitap",
    "visa",
    "izin tinggal",
    "paspor",
    "imigrasi",
    "wna",
    "warga negara asing",
    "tenaga kerja asing",
    "tka",
    "peraturan imigrasi",
    "kebijakan visa",
    "perpanjangan visa",
]

# Reference embedding query (pre-computed at runtime on first use)
REFERENCE_QUERY = (
    "Indonesian immigration enforcement TIMPORA deportation overstay "
    "WNA foreign nationals visa regulation Bali"
)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_SIMILARITY_THRESHOLD = 0.35
EMBEDDING_BORDERLINE_LOW = 0.30
EMBEDDING_BORDERLINE_HIGH = 0.40


# ---------------------------------------------------------------------------
# Enums / dataclasses
# ---------------------------------------------------------------------------


class FilterResult(str, Enum):
    ADMIT = "ADMIT"
    REJECT = "REJECT"
    BORDERLINE = "BORDERLINE"


# ---------------------------------------------------------------------------
# T4RelevanceFilter
# ---------------------------------------------------------------------------


class T4RelevanceFilter:
    """3-layer relevance filter for T4 immigration content.

    Layer 1 — keyword recall (~0ms, fast gate)
    Layer 2 — embedding cosine similarity (~50ms, precision gate)
    Layer 3 — Haiku LLM classifier (~500ms, borderline only)
    """

    def layer1_keywords(self, text: str) -> bool:
        """Return True if text passes keyword recall gate."""
        lower = text.lower()
        critical_hits = sum(1 for kw in CRITICAL_KEYWORDS if kw in lower)
        if critical_hits >= 1:
            return True
        high_hits = sum(1 for kw in HIGH_KEYWORDS if kw in lower)
        return high_hits >= 2

    async def _embed(self, text: str) -> list[float]:
        """Embed text using OpenAI text-embedding-3-small.

        Raises ImportError if openai package not installed.
        """
        import openai  # noqa: PLC0415 (import-outside-toplevel)

        client = openai.AsyncOpenAI()
        resp = await client.embeddings.create(model=EMBEDDING_MODEL, input=text)
        return resp.data[0].embedding

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    async def layer2_embedding(
        self, text: str, *, cached_ref: Optional[list[float]] = None
    ) -> float:
        """Return cosine similarity between text and reference query."""
        ref = cached_ref or await self._embed(REFERENCE_QUERY)
        text_vec = await self._embed(text)
        return self._cosine(text_vec, ref)

    async def _haiku_classify(self, text: str) -> float:
        """Call Haiku to score immigration relevance (0.0–1.0)."""
        import anthropic  # noqa: PLC0415

        client = anthropic.AsyncAnthropic()
        prompt = (
            "You are an immigration advisor for Bali, Indonesia. "
            "Score the following article's relevance to immigration enforcement "
            "(deportation, overstay, visa cancellation, arrests of foreign nationals). "
            "Respond with ONLY a decimal between 0.0 and 1.0. "
            "1.0 = highly relevant enforcement news. 0.0 = irrelevant.\n\n"
            f"Article: {text[:1500]}"
        )
        message = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        try:
            return float(raw)
        except ValueError:
            logger.warning("Haiku returned non-float: %r — defaulting to 0.0", raw)
            return 0.0

    async def layer3_haiku(self, text: str) -> float:
        """Return Haiku relevance score for text."""
        return await self._haiku_classify(text)

    async def classify(
        self,
        text: str,
        *,
        ref_embedding: Optional[list[float]] = None,
    ) -> FilterResult:
        """Run full 3-layer pipeline. Returns ADMIT, REJECT, or BORDERLINE."""
        if not self.layer1_keywords(text):
            return FilterResult.REJECT

        similarity = await self.layer2_embedding(text, cached_ref=ref_embedding)

        if similarity >= EMBEDDING_SIMILARITY_THRESHOLD:
            return FilterResult.ADMIT

        if EMBEDDING_BORDERLINE_LOW <= similarity < EMBEDDING_BORDERLINE_HIGH:
            score = await self.layer3_haiku(text)
            return FilterResult.ADMIT if score >= 0.5 else FilterResult.REJECT

        return FilterResult.REJECT
```

- [ ] **Step 2.4: Install missing dependencies if needed**

```bash
cd /Users/nuzantara/Desktop/nuzantara/apps/backend-rag
source .venv/bin/activate   # Pro uses .venv
pip show feedparser beautifulsoup4 2>&1 | grep -E "Name:|not found"
# If missing: pip install feedparser beautifulsoup4
```

- [ ] **Step 2.5: Run tests — verify they pass**

```bash
cd /Users/nuzantara/Desktop/nuzantara
PYTHONPATH=. pytest tests/nlm_deep_research/test_t4_filter.py -v 2>&1 | tail -25
```

Expected: all 12 tests PASS.

- [ ] **Step 2.6: Commit**

```bash
git add apps/evaluator/nlm_deep_research/t4_monitor.py \
        tests/nlm_deep_research/test_t4_filter.py
git commit -m "feat(t4): add T4RelevanceFilter with 3-layer keyword/embedding/haiku pipeline"
```

---

## Task 3: SVS scoring for T4 articles

**Files:**

- Modify: `apps/evaluator/nlm_deep_research/t4_monitor.py` (add `Article` dataclass + `T4SVSScorer`)
- Create: `tests/nlm_deep_research/test_t4_svs.py`

- [ ] **Step 3.1: Write the failing tests**

Create `tests/nlm_deep_research/test_t4_svs.py`:

```python
"""Unit tests for T4 SVS scoring."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from apps.evaluator.nlm_deep_research.t4_monitor import Article, T4SVSScorer


def make_article(**kwargs) -> Article:
    defaults = dict(
        source_handle="imngurahrai",
        article_id="abc123",
        url="https://ngurahrai.imigrasi.go.id/berita/1",
        title="Imigrasi Ngurah Rai Deportasi WN Korea",
        content="Timpora razia overstay WNA Korea daftar cekal.",
        scraped_at=datetime.now(timezone.utc),
        platform="rss",
    )
    defaults.update(kwargs)
    return Article(**defaults)


class TestT4SVSScorer:
    def test_enforcement_article_scores_above_threshold(self):
        scorer = T4SVSScorer()
        article = make_article(
            title="Imigrasi Deportasi 5 WNA Overstay",
            content="Timpora razia wna blacklist cegah tangkal deportasi."
        )
        score = scorer.score(article)
        assert score >= 0.35

    def test_ceremony_article_scores_below_threshold(self):
        scorer = T4SVSScorer()
        article = make_article(
            title="Selamat Ulang Tahun Imigrasi ke-73",
            content="Acara ulang tahun dihadiri seluruh pegawai kantor.",
            platform="website",
        )
        score = scorer.score(article)
        assert score < 0.35

    def test_fresh_article_scores_higher_than_old(self):
        scorer = T4SVSScorer()
        fresh = make_article(
            scraped_at=datetime.now(timezone.utc),
            content="Timpora deportasi WNA overstay",
        )
        old = make_article(
            scraped_at=datetime.now(timezone.utc) - timedelta(days=20),
            content="Timpora deportasi WNA overstay",
        )
        assert scorer.score(fresh) > scorer.score(old)

    def test_rss_source_scores_higher_than_website(self):
        scorer = T4SVSScorer()
        rss = make_article(platform="rss", content="Deportasi timpora WNA overstay")
        web = make_article(platform="website", content="Deportasi timpora WNA overstay")
        assert scorer.score(rss) >= scorer.score(web)

    def test_score_clamped_between_0_and_1(self):
        scorer = T4SVSScorer()
        article = make_article(content="timpora " * 100)
        score = scorer.score(article)
        assert 0.0 <= score <= 1.0

    def test_score_returns_float(self):
        scorer = T4SVSScorer()
        score = scorer.score(make_article())
        assert isinstance(score, float)
```

- [ ] **Step 3.2: Run tests — verify they fail**

```bash
cd /Users/nuzantara/Desktop/nuzantara
PYTHONPATH=. pytest tests/nlm_deep_research/test_t4_svs.py -v 2>&1 | tail -10
```

Expected: `ImportError: cannot import name 'Article' from 't4_monitor'`

- [ ] **Step 3.3: Add `Article` dataclass and `T4SVSScorer` to `t4_monitor.py`**

Add after the `FilterResult` class in `apps/evaluator/nlm_deep_research/t4_monitor.py`:

```python
@dataclass
class Article:
    """Normalized article from any T4 source."""

    source_handle: str
    article_id: str               # URL hash — PRIMARY dedup key
    url: str
    title: str
    content: str
    scraped_at: datetime
    platform: Literal["rss", "website", "twitter", "instagram"]
    published_at: Optional[datetime] = None  # UNRELIABLE — prefer scraped_at
    svs_score: float = 0.0
    filter_result: str = "PENDING"


@dataclass
class Post:
    """Normalized social media post (Twitter / Instagram)."""

    handle: str
    post_id: str                  # tweet_id or shortcode — PRIMARY dedup key
    url: str
    content: str
    scraped_at: datetime
    platform: Literal["twitter", "instagram"]
    timestamp: Optional[datetime] = None


# ---------------------------------------------------------------------------
# SVS Scorer
# ---------------------------------------------------------------------------

# Authority scores per source handle (higher = more authoritative)
SOURCE_AUTHORITY: dict[str, float] = {
    "ngurahrai.imigrasi.go.id": 1.0,
    "ditjenimigrasi.go.id": 1.0,
    "imigrasi.go.id": 0.95,
    "kanwilbali.kemenkumham.go.id": 0.90,
    "kemenkumham.go.id": 0.85,
    "ditjen_imigrasi": 0.90,   # Twitter
    "imngurahrai": 0.95,       # Twitter
    "kemenkumbali": 0.85,      # Twitter
}

PLATFORM_BOOST: dict[str, float] = {
    "rss": 0.10,
    "website": 0.05,
    "twitter": 0.08,
    "instagram": 0.03,
}


class T4SVSScorer:
    """Compute SVS for T4 articles.

    Weights:
        authority  0.30
        freshness  0.25
        uniqueness 0.20   (keyword density proxy)
        density    0.15   (CRITICAL keyword count)
        platform   0.10   (platform boost)
    """

    W_AUTHORITY = 0.30
    W_FRESHNESS = 0.25
    W_UNIQUENESS = 0.20
    W_DENSITY = 0.15
    W_PLATFORM = 0.10

    def score(self, article: Article) -> float:
        authority = self._authority(article)
        freshness = self._freshness(article)
        uniqueness = self._uniqueness(article)
        density = self._density(article)
        platform = PLATFORM_BOOST.get(article.platform, 0.0)

        raw = (
            self.W_AUTHORITY * authority
            + self.W_FRESHNESS * freshness
            + self.W_UNIQUENESS * uniqueness
            + self.W_DENSITY * density
            + self.W_PLATFORM * platform
        )
        return max(0.0, min(1.0, raw))

    def _authority(self, article: Article) -> float:
        from urllib.parse import urlparse  # noqa: PLC0415

        try:
            host = urlparse(article.url).hostname or ""
        except Exception:
            host = ""
        # Check handle match too
        return SOURCE_AUTHORITY.get(host, SOURCE_AUTHORITY.get(article.source_handle, 0.60))

    def _freshness(self, article: Article) -> float:
        """Exponential decay: half-life = NEWS_HALF_LIFE_DAYS (15 days)."""
        from apps.evaluator.nlm_deep_research.t4_state import NEWS_HALF_LIFE_DAYS  # noqa: PLC0415

        delta_days = (
            datetime.now(timezone.utc) - article.scraped_at
        ).total_seconds() / 86400
        return math.exp(-math.log(2) * delta_days / NEWS_HALF_LIFE_DAYS)

    def _uniqueness(self, article: Article) -> float:
        """Keyword density as uniqueness proxy (normalized)."""
        text = (article.title + " " + article.content).lower()
        all_keywords = CRITICAL_KEYWORDS + HIGH_KEYWORDS
        hits = sum(1 for kw in all_keywords if kw in text)
        return min(1.0, hits / 5.0)

    def _density(self, article: Article) -> float:
        """CRITICAL keyword density."""
        text = (article.title + " " + article.content).lower()
        hits = sum(1 for kw in CRITICAL_KEYWORDS if kw in text)
        return min(1.0, hits / 3.0)
```

- [ ] **Step 3.4: Run tests — verify they pass**

```bash
cd /Users/nuzantara/Desktop/nuzantara
PYTHONPATH=. pytest tests/nlm_deep_research/test_t4_svs.py -v 2>&1 | tail -20
```

Expected: all 6 tests PASS.

- [ ] **Step 3.5: Commit**

```bash
git add apps/evaluator/nlm_deep_research/t4_monitor.py \
        tests/nlm_deep_research/test_t4_svs.py
git commit -m "feat(t4): add Article dataclass and T4SVSScorer with freshness decay"
```

---

## Task 4: Circuit Breaker CB_T4

**Files:**

- Modify: `apps/evaluator/nlm_deep_research/t4_monitor.py` (add `T4CircuitBreaker`)
- Create: `tests/nlm_deep_research/test_t4_cb.py`

- [ ] **Step 4.1: Write the failing tests**

Create `tests/nlm_deep_research/test_t4_cb.py`:

```python
"""Unit tests for CB_T4 circuit breaker FSM."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from apps.evaluator.nlm_deep_research.t4_monitor import T4CircuitBreaker
from apps.evaluator.nlm_deep_research.t4_state import T4State


class TestT4CircuitBreaker:
    def _state(self, **kwargs) -> T4State:
        return T4State(**kwargs)

    def test_fresh_state_is_closed(self):
        cb = T4CircuitBreaker()
        state = self._state()
        assert cb.is_open(state) is False

    def test_three_failures_opens_cb(self):
        cb = T4CircuitBreaker()
        state = self._state()
        cb.record_failure(state)
        cb.record_failure(state)
        cb.record_failure(state)
        assert state.cb_status == "OPEN"

    def test_two_failures_stays_closed(self):
        cb = T4CircuitBreaker()
        state = self._state()
        cb.record_failure(state)
        cb.record_failure(state)
        assert state.cb_status == "CLOSED"

    def test_success_resets_failure_count(self):
        cb = T4CircuitBreaker()
        state = self._state(cb_failure_count=2)
        cb.record_success(state)
        assert state.cb_failure_count == 0
        assert state.cb_status == "CLOSED"

    def test_open_cb_stays_open_before_timeout(self):
        cb = T4CircuitBreaker()
        state = self._state(
            cb_status="OPEN",
            cb_last_failure=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        assert cb.is_open(state) is True

    def test_open_cb_transitions_to_half_open_after_timeout(self):
        cb = T4CircuitBreaker()
        state = self._state(
            cb_status="OPEN",
            cb_last_failure=datetime.now(timezone.utc) - timedelta(minutes=35),
        )
        cb.maybe_transition(state)
        assert state.cb_status == "HALF_OPEN"

    def test_half_open_success_closes_cb(self):
        cb = T4CircuitBreaker()
        state = self._state(cb_status="HALF_OPEN")
        cb.record_success(state)
        assert state.cb_status == "CLOSED"

    def test_half_open_failure_reopens_cb(self):
        cb = T4CircuitBreaker()
        state = self._state(cb_status="HALF_OPEN")
        cb.record_failure(state)
        assert state.cb_status == "OPEN"

    def test_dom_changed_opens_immediately(self):
        cb = T4CircuitBreaker()
        state = self._state(cb_failure_count=0)
        cb.open_immediately(state, reason="DOMChangedError")
        assert state.cb_status == "OPEN"
        assert state.cb_failure_count >= CB_T4_FAILURE_THRESHOLD

    def test_is_open_returns_false_when_closed(self):
        cb = T4CircuitBreaker()
        state = self._state(cb_status="CLOSED")
        assert cb.is_open(state) is False
```

Note: import `CB_T4_FAILURE_THRESHOLD` from `t4_monitor` in the test file header:

```python
from apps.evaluator.nlm_deep_research.t4_monitor import T4CircuitBreaker, CB_T4_FAILURE_THRESHOLD
```

- [ ] **Step 4.2: Run tests — verify they fail**

```bash
PYTHONPATH=. pytest tests/nlm_deep_research/test_t4_cb.py -v 2>&1 | tail -10
```

Expected: `ImportError: cannot import name 'T4CircuitBreaker' from 't4_monitor'`

- [ ] **Step 4.3: Add `T4CircuitBreaker` to `t4_monitor.py`**

Add after `T4SVSScorer` class:

```python
# ---------------------------------------------------------------------------
# Circuit Breaker CB_T4 (standalone — does NOT cascade to CB_NLM)
# ---------------------------------------------------------------------------


class T4CircuitBreaker:
    """Standalone circuit breaker for T4 monitor.

    Thresholds:
        failure_threshold = 3 consecutive failures → OPEN
        recovery_timeout  = 30 minutes → HALF_OPEN probe
        DOMChangedError   → immediate OPEN (no counter needed)

    Does NOT cascade to CB_NLM or CB_SOURCE (independent failure domain).
    """

    def is_open(self, state: "T4State") -> bool:  # noqa: F821
        from apps.evaluator.nlm_deep_research.t4_state import T4State  # noqa: PLC0415

        if state.cb_status == "OPEN":
            self.maybe_transition(state)
            return state.cb_status == "OPEN"
        return False

    def maybe_transition(self, state: "T4State") -> None:  # noqa: F821
        """Transition OPEN → HALF_OPEN if recovery timeout has elapsed."""
        if state.cb_status != "OPEN":
            return
        if state.cb_last_failure is None:
            state.cb_status = "HALF_OPEN"
            return
        elapsed = (
            datetime.now(timezone.utc) - state.cb_last_failure
        ).total_seconds() / 60
        if elapsed >= CB_T4_RECOVERY_MINUTES:
            state.cb_status = "HALF_OPEN"
            logger.info("CB_T4 → HALF_OPEN after %.0f min", elapsed)

    def record_failure(self, state: "T4State") -> None:  # noqa: F821
        """Increment failure counter; open CB after threshold."""
        state.cb_failure_count += 1
        state.cb_last_failure = datetime.now(timezone.utc)
        if state.cb_status == "HALF_OPEN":
            state.cb_status = "OPEN"
            logger.warning("CB_T4 HALF_OPEN probe failed → back to OPEN")
        elif state.cb_failure_count >= CB_T4_FAILURE_THRESHOLD:
            state.cb_status = "OPEN"
            logger.warning(
                "CB_T4 OPEN after %d failures", state.cb_failure_count
            )

    def record_success(self, state: "T4State") -> None:  # noqa: F821
        """Reset failure counter and close CB."""
        state.cb_failure_count = 0
        state.cb_status = "CLOSED"

    def open_immediately(self, state: "T4State", reason: str = "") -> None:  # noqa: F821
        """Force CB OPEN (e.g., DOMChangedError)."""
        state.cb_status = "OPEN"
        state.cb_failure_count = CB_T4_FAILURE_THRESHOLD
        state.cb_last_failure = datetime.now(timezone.utc)
        logger.error("CB_T4 forced OPEN: %s", reason)
```

Also update the test import line:

```python
from apps.evaluator.nlm_deep_research.t4_monitor import (
    T4CircuitBreaker,
    CB_T4_FAILURE_THRESHOLD,
)
```

- [ ] **Step 4.4: Run tests — verify they pass**

```bash
PYTHONPATH=. pytest tests/nlm_deep_research/test_t4_cb.py -v 2>&1 | tail -20
```

Expected: all 10 tests PASS.

- [ ] **Step 4.5: Commit**

```bash
git add apps/evaluator/nlm_deep_research/t4_monitor.py \
        tests/nlm_deep_research/test_t4_cb.py
git commit -m "feat(t4): add CB_T4 standalone circuit breaker FSM"
```

---

## Task 5: RSS and website fetching

**Files:**

- Modify: `apps/evaluator/nlm_deep_research/t4_monitor.py` (add `T4Fetcher`)
- Create: `tests/nlm_deep_research/test_t4_monitor.py` (fetch section)

- [ ] **Step 5.1: Write the failing tests**

Add to `tests/nlm_deep_research/test_t4_monitor.py`:

```python
"""Integration tests for T4Monitor fetch layer (mocked HTTP)."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.evaluator.nlm_deep_research.t4_monitor import T4Fetcher, Article


RSS_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Kantor Imigrasi Ngurah Rai</title>
    <link>https://ngurahrai.imigrasi.go.id</link>
    <item>
      <title>Imigrasi Ngurah Rai Deportasi WN Korea</title>
      <link>https://ngurahrai.imigrasi.go.id/berita/deportasi-korea</link>
      <description>WN Korea Selatan dideportasi akibat overstay 60 hari.</description>
      <pubDate>Thu, 26 Mar 2026 10:00:00 +0800</pubDate>
      <guid>https://ngurahrai.imigrasi.go.id/berita/deportasi-korea</guid>
    </item>
    <item>
      <title>Timpora Kuta Selatan Perkuat Pengawasan WNA</title>
      <link>https://ngurahrai.imigrasi.go.id/berita/timpora-kuta</link>
      <description>Operasi timpora dilakukan untuk menekan angka overstay.</description>
      <pubDate>Wed, 25 Mar 2026 08:00:00 +0800</pubDate>
      <guid>https://ngurahrai.imigrasi.go.id/berita/timpora-kuta</guid>
    </item>
  </channel>
</rss>"""


class TestT4FetcherRSS:
    @pytest.mark.asyncio
    async def test_fetch_rss_returns_articles(self):
        fetcher = T4Fetcher()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = RSS_SAMPLE
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            articles = await fetcher.fetch_rss(
                "https://ngurahrai.imigrasi.go.id/feed/",
                source_handle="imngurahrai",
            )

        assert len(articles) == 2
        assert all(isinstance(a, Article) for a in articles)
        assert articles[0].title == "Imigrasi Ngurah Rai Deportasi WN Korea"
        assert articles[0].platform == "rss"
        assert articles[0].article_id != ""   # URL-based hash

    @pytest.mark.asyncio
    async def test_fetch_rss_http_error_returns_empty(self):
        fetcher = T4Fetcher()
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))
            mock_client_cls.return_value = mock_client

            articles = await fetcher.fetch_rss(
                "https://bad-url.example.com/feed/",
                source_handle="bad",
            )

        assert articles == []

    @pytest.mark.asyncio
    async def test_article_id_is_url_hash(self):
        fetcher = T4Fetcher()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = RSS_SAMPLE
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            articles = await fetcher.fetch_rss(
                "https://ngurahrai.imigrasi.go.id/feed/",
                source_handle="imngurahrai",
            )

        import hashlib
        expected_id = hashlib.sha1(
            articles[0].url.encode()
        ).hexdigest()[:16]
        assert articles[0].article_id == expected_id
```

Add `import httpx` at top of test file.

- [ ] **Step 5.2: Run tests — verify they fail**

```bash
PYTHONPATH=. pytest tests/nlm_deep_research/test_t4_monitor.py -v 2>&1 | tail -10
```

Expected: `ImportError: cannot import name 'T4Fetcher'`

- [ ] **Step 5.3: Add `T4Fetcher` to `t4_monitor.py`**

Add after `T4CircuitBreaker` class:

```python
# ---------------------------------------------------------------------------
# Fetchers
# ---------------------------------------------------------------------------


class T4Fetcher:
    """Fetch articles from RSS feeds, government websites, and X/Twitter."""

    async def fetch_rss(
        self, url: str, *, source_handle: str
    ) -> list[Article]:
        """Fetch and parse an RSS feed. Returns [] on any error."""
        import feedparser  # noqa: PLC0415

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, follow_redirects=True)
                resp.raise_for_status()
                feed = feedparser.parse(resp.text)
        except Exception:
            logger.exception("RSS fetch failed for %s", url)
            return []

        articles: list[Article] = []
        for entry in feed.entries:
            link = getattr(entry, "link", "") or ""
            if not link:
                continue
            article_id = hashlib.sha1(link.encode()).hexdigest()[:16]
            title = getattr(entry, "title", link)
            summary = getattr(entry, "summary", "")
            content_detail = getattr(entry, "content", [])
            body = content_detail[0].value if content_detail else summary

            published_at: Optional[datetime] = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                from time import mktime  # noqa: PLC0415

                try:
                    published_at = datetime.fromtimestamp(
                        mktime(entry.published_parsed), tz=timezone.utc
                    )
                except Exception:
                    pass

            articles.append(
                Article(
                    source_handle=source_handle,
                    article_id=article_id,
                    url=link,
                    title=title,
                    content=f"{title}. {body}",
                    scraped_at=datetime.now(timezone.utc),
                    platform="rss",
                    published_at=published_at,
                )
            )
        return articles

    async def fetch_website(
        self,
        url: str,
        *,
        source_handle: str,
        article_selector: str = "article",
        title_selector: str = "h2",
        link_selector: str = "a",
    ) -> list[Article]:
        """Scrape a /berita/ listing page. Returns [] on any error."""
        from bs4 import BeautifulSoup  # noqa: PLC0415

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, follow_redirects=True)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
        except Exception:
            logger.exception("Website fetch failed for %s", url)
            return []

        articles: list[Article] = []
        for block in soup.select(article_selector)[:20]:
            title_el = block.select_one(title_selector)
            link_el = block.select_one(link_selector)
            if not title_el or not link_el:
                continue
            title = title_el.get_text(strip=True)
            link = link_el.get("href", "")
            if not link:
                continue
            if not link.startswith("http"):
                from urllib.parse import urljoin  # noqa: PLC0415

                link = urljoin(url, link)
            article_id = hashlib.sha1(link.encode()).hexdigest()[:16]
            text = block.get_text(separator=" ", strip=True)

            articles.append(
                Article(
                    source_handle=source_handle,
                    article_id=article_id,
                    url=link,
                    title=title,
                    content=text[:2000],
                    scraped_at=datetime.now(timezone.utc),
                    platform="website",
                )
            )
        return articles

    async def fetch_twitter(
        self,
        handle: str,
        *,
        bearer_token: str,
        max_results: int = 20,
    ) -> list[Post]:
        """Fetch recent tweets via Twitter API v2. Returns [] on any error."""
        try:
            # Step 1: resolve handle → user_id
            async with httpx.AsyncClient(timeout=30.0) as client:
                user_resp = await client.get(
                    f"https://api.twitter.com/2/users/by/username/{handle.lstrip('@')}",
                    headers={"Authorization": f"Bearer {bearer_token}"},
                )
                user_resp.raise_for_status()
                user_id = user_resp.json()["data"]["id"]

                # Step 2: fetch recent tweets
                tweet_resp = await client.get(
                    f"https://api.twitter.com/2/users/{user_id}/tweets",
                    headers={"Authorization": f"Bearer {bearer_token}"},
                    params={
                        "max_results": max_results,
                        "tweet.fields": "created_at,text",
                    },
                )
                tweet_resp.raise_for_status()
                tweets = tweet_resp.json().get("data", [])
        except Exception:
            logger.exception("Twitter fetch failed for @%s", handle)
            return []

        posts: list[Post] = []
        for tweet in tweets:
            tweet_id = tweet["id"]
            url = f"https://twitter.com/{handle.lstrip('@')}/status/{tweet_id}"
            created = None
            if tweet.get("created_at"):
                try:
                    created = datetime.fromisoformat(
                        tweet["created_at"].replace("Z", "+00:00")
                    )
                except ValueError:
                    pass
            posts.append(
                Post(
                    handle=handle,
                    post_id=tweet_id,
                    url=url,
                    content=tweet.get("text", ""),
                    scraped_at=datetime.now(timezone.utc),
                    platform="twitter",
                    timestamp=created,
                )
            )
        return posts
```

- [ ] **Step 5.4: Run fetch tests — verify they pass**

```bash
PYTHONPATH=. pytest tests/nlm_deep_research/test_t4_monitor.py -v 2>&1 | tail -20
```

Expected: all 3 fetch tests PASS.

- [ ] **Step 5.5: Commit**

```bash
git add apps/evaluator/nlm_deep_research/t4_monitor.py \
        tests/nlm_deep_research/test_t4_monitor.py
git commit -m "feat(t4): add T4Fetcher with RSS, website scraping, and Twitter API v2"
```

---

## Task 6: NLM ingest and T4Monitor orchestrator

**Files:**

- Modify: `apps/evaluator/nlm_deep_research/t4_monitor.py` (add `T4Monitor` class)
- Expand: `tests/nlm_deep_research/test_t4_monitor.py` (add orchestrator tests)

- [ ] **Step 6.1: Write orchestrator tests**

Append to `tests/nlm_deep_research/test_t4_monitor.py`:

```python
from apps.evaluator.nlm_deep_research.t4_monitor import T4Monitor
from apps.evaluator.nlm_deep_research.t4_state import T4State, T4StatePersistence


class TestT4MonitorIngest:
    @pytest.mark.asyncio
    async def test_already_seen_article_skipped(self, tmp_path):
        state = T4State(seen_ids={"abc123"})
        persistence = T4StatePersistence(tmp_path / "state.json")
        persistence.save(state)

        monitor = T4Monitor(state_path=tmp_path / "state.json", dry_run=True)
        ingested = await monitor._maybe_ingest(
            Article(
                source_handle="test",
                article_id="abc123",
                url="https://example.com/1",
                title="Test",
                content="timpora deportasi WNA",
                scraped_at=datetime.now(timezone.utc),
                platform="rss",
            )
        )
        assert ingested is False

    @pytest.mark.asyncio
    async def test_dry_run_does_not_call_nlm(self, tmp_path):
        monitor = T4Monitor(state_path=tmp_path / "state.json", dry_run=True)
        article = Article(
            source_handle="imngurahrai",
            article_id="new999",
            url="https://ngurahrai.imigrasi.go.id/berita/new",
            title="Deportasi Timpora WNA",
            content="Timpora deportasi WNA overstay visa dicabut.",
            scraped_at=datetime.now(timezone.utc),
            platform="rss",
        )
        with patch(
            "apps.evaluator.nlm_deep_research.t4_monitor.T4Monitor._call_nlm_cli",
            new=AsyncMock(return_value=True),
        ) as mock_nlm:
            await monitor._maybe_ingest(article)
        mock_nlm.assert_not_called()

    @pytest.mark.asyncio
    async def test_budget_exceeded_evicts_oldest(self, tmp_path):
        state = T4State(active_t4_sources=["s"] * 11)
        persistence = T4StatePersistence(tmp_path / "state.json")
        persistence.save(state)

        monitor = T4Monitor(state_path=tmp_path / "state.json", dry_run=True)
        loaded_state = monitor._persistence.load()
        assert loaded_state.is_over_budget()
        evicted = loaded_state.evict_oldest()
        assert evicted == "s"
        assert len(loaded_state.active_t4_sources) == 10

    @pytest.mark.asyncio
    async def test_nlm_ingest_builds_correct_content_format(self, tmp_path):
        monitor = T4Monitor(state_path=tmp_path / "state.json", dry_run=False)
        article = Article(
            source_handle="imngurahrai",
            article_id="x1",
            url="https://ngurahrai.imigrasi.go.id/berita/1",
            title="Deportasi WNA",
            content="Timpora razia overstay.",
            scraped_at=datetime(2026, 3, 28, 10, 0, 0, tzinfo=timezone.utc),
            platform="rss",
            svs_score=0.62,
        )
        formatted = monitor._format_for_nlm(article)
        assert "[TITLE]: Deportasi WNA" in formatted
        assert "[SOURCE]: imngurahrai" in formatted
        assert "[SVS]: 0.62" in formatted
        assert "Timpora razia overstay." in formatted
```

- [ ] **Step 6.2: Run new tests — verify they fail**

```bash
PYTHONPATH=. pytest tests/nlm_deep_research/test_t4_monitor.py::TestT4MonitorIngest -v 2>&1 | tail -10
```

Expected: `ImportError: cannot import name 'T4Monitor'`

- [ ] **Step 6.3: Add `T4Monitor` class to `t4_monitor.py`**

Add at the end of `apps/evaluator/nlm_deep_research/t4_monitor.py`:

```python
# ---------------------------------------------------------------------------
# T4Monitor — main orchestrator
# ---------------------------------------------------------------------------


@dataclass
class T4RunResult:
    fetched: int = 0
    filtered_admit: int = 0
    ingested: int = 0
    skipped_dedup: int = 0
    skipped_budget: int = 0
    rejected: int = 0
    errors: int = 0


class T4Monitor:
    """Main orchestrator: fetch → filter → SVS → ingest → persist."""

    RSS_SOURCES = [
        ("https://ngurahrai.imigrasi.go.id/feed/", "imngurahrai"),
        ("https://ditjenimigrasi.go.id/feed/", "ditjen_imigrasi"),
        ("https://www.imigrasi.go.id/feed/", "imigrasi_go_id"),
    ]

    WEBSITE_SOURCES = [
        (
            "https://ditjenimigrasi.go.id/kategori/berita/",
            "ditjen_imigrasi",
            {"article_selector": ".post", "title_selector": ".post-title", "link_selector": "a"},
        ),
        (
            "https://kanwilbali.kemenkumham.go.id/berita-utama",
            "kemenkumbali",
            {"article_selector": "article", "title_selector": "h2", "link_selector": "a"},
        ),
    ]

    TWITTER_HANDLES = [
        "@ditjen_imigrasi",
        "@imngurahrai",
        "@kemenkumbali",
    ]

    def __init__(
        self,
        *,
        state_path: Optional["Path"] = None,  # noqa: F821
        dry_run: bool = False,
        notebook_id: str = NB2_ID,
    ) -> None:
        from apps.evaluator.nlm_deep_research.t4_state import (  # noqa: PLC0415
            T4StatePersistence,
            _DEFAULT_STATE_PATH,
        )

        self._notebook_id = notebook_id
        self._dry_run = dry_run
        self._persistence = T4StatePersistence(
            state_path if state_path else _DEFAULT_STATE_PATH
        )
        self._fetcher = T4Fetcher()
        self._filter = T4RelevanceFilter()
        self._svs = T4SVSScorer()
        self._cb = T4CircuitBreaker()
        self._ref_embedding: Optional[list[float]] = None

    async def run(self) -> T4RunResult:
        """Main entry point: run full T4 monitor cycle."""
        result = T4RunResult()
        state = self._persistence.load()

        if self._cb.is_open(state):
            logger.warning("CB_T4 is OPEN — skipping T4 monitor run")
            self._persistence.save(state)
            return result

        articles: list[Article] = []

        # Fetch RSS
        for url, handle in self.RSS_SOURCES:
            fetched = await self._fetcher.fetch_rss(url, source_handle=handle)
            articles.extend(fetched)
            result.fetched += len(fetched)

        # Fetch websites
        for url, handle, selectors in self.WEBSITE_SOURCES:
            fetched = await self._fetcher.fetch_website(
                url, source_handle=handle, **selectors
            )
            articles.extend(fetched)
            result.fetched += len(fetched)

        # Fetch X/Twitter (if enabled and bearer available)
        bearer = self._get_bearer_token()
        if state.x_enabled and bearer:
            for handle in self.TWITTER_HANDLES:
                posts = await self._fetcher.fetch_twitter(handle, bearer_token=bearer)
                for post in posts:
                    # Convert Post → Article for uniform pipeline
                    a = Article(
                        source_handle=post.handle,
                        article_id=post.post_id,
                        url=post.url,
                        title=post.content[:100],
                        content=post.content,
                        scraped_at=post.scraped_at,
                        platform="twitter",
                    )
                    articles.append(a)
                    result.fetched += 1

        # Get reference embedding once
        if articles:
            try:
                self._ref_embedding = await self._filter._embed(REFERENCE_QUERY)
            except Exception:
                logger.warning("Could not get reference embedding — skipping L2/L3")

        # Filter, score, ingest
        for article in articles:
            ingested = await self._maybe_ingest(article)
            if ingested:
                result.ingested += 1
                state.mark_seen(article.article_id)
                state.add_source(article.article_id)
                result.filtered_admit += 1
            elif state.is_seen(article.article_id):
                result.skipped_dedup += 1
            else:
                result.rejected += 1

        state.last_run_at = datetime.now(timezone.utc)
        self._persistence.save(state)
        logger.info(
            "T4 run complete: fetched=%d admit=%d ingested=%d dedup=%d rejected=%d",
            result.fetched, result.filtered_admit, result.ingested,
            result.skipped_dedup, result.rejected,
        )
        return result

    async def _maybe_ingest(self, article: Article) -> bool:
        """Filter → SVS → budget check → ingest. Returns True if ingested."""
        state = self._persistence.load()

        # Dedup
        if state.is_seen(article.article_id):
            return False

        # Relevance filter
        filter_result = await self._filter.classify(
            article.content, ref_embedding=self._ref_embedding
        )
        article.filter_result = filter_result.value
        if filter_result == FilterResult.REJECT:
            return False

        # SVS scoring
        svs = self._svs.score(article)
        article.svs_score = svs
        if svs < 0.35:
            return False

        # Budget enforcement
        if state.is_over_budget():
            evicted = state.evict_oldest()
            logger.info("T4 budget full — evicted oldest source %s", evicted)

        # Ingest
        if self._dry_run:
            logger.info("[DRY-RUN] Would ingest: %s (SVS=%.2f)", article.title, svs)
            return False

        success = await self._call_nlm_cli(
            self._notebook_id,
            title=article.title,
            content=self._format_for_nlm(article),
        )
        if success:
            self._cb.record_success(state)
            self._persistence.save(state)
        else:
            self._cb.record_failure(state)
            self._persistence.save(state)
        return success

    def _format_for_nlm(self, article: Article) -> str:
        return (
            f"[TITLE]: {article.title}\n"
            f"[SOURCE]: {article.source_handle} | {article.url}\n"
            f"[DATE]: {article.scraped_at.isoformat()}\n"
            f"[PLATFORM]: {article.platform}\n"
            f"[SVS]: {article.svs_score:.2f}\n\n"
            f"{article.content}"
        )

    async def _call_nlm_cli(
        self, notebook_id: str, *, title: str, content: str, timeout_seconds: int = 60
    ) -> bool:
        nlm_bin = shutil.which("nlm") or "nlm"
        cmd = [
            nlm_bin, "source", "add", notebook_id,
            "--text", content,
            "--title", title,
            "--wait",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_seconds
            )
            if proc.returncode != 0:
                logger.error("nlm CLI error: %s", stderr.decode()[:200])
            return proc.returncode == 0
        except asyncio.TimeoutError:
            logger.error("nlm CLI timeout after %ds for title: %s", timeout_seconds, title)
            return False
        except Exception:
            logger.exception("nlm CLI unexpected error for title: %s", title)
            return False

    @staticmethod
    def _get_bearer_token() -> Optional[str]:
        import os  # noqa: PLC0415

        return (
            os.environ.get("TWITTER_BEARER_TOKEN")
            or os.environ.get("X_BEARER_TOKEN")
        )
```

- [ ] **Step 6.4: Run all T4 tests**

```bash
PYTHONPATH=. pytest tests/nlm_deep_research/test_t4_monitor.py -v 2>&1 | tail -25
```

Expected: all tests PASS (including new orchestrator tests).

- [ ] **Step 6.5: Commit**

```bash
git add apps/evaluator/nlm_deep_research/t4_monitor.py \
        tests/nlm_deep_research/test_t4_monitor.py
git commit -m "feat(t4): add T4Monitor orchestrator with dry-run mode and NLM CLI ingest"
```

---

## Task 7: Update `__init__.py` and run full test suite

**Files:**

- Modify: `apps/evaluator/nlm_deep_research/__init__.py`

- [ ] **Step 7.1: Export new classes**

Read current `apps/evaluator/nlm_deep_research/__init__.py` — it currently exports nothing from submodules. Append:

```python
from apps.evaluator.nlm_deep_research.t4_state import T4State, T4StatePersistence, T4PIDLock
from apps.evaluator.nlm_deep_research.t4_monitor import T4Monitor, T4Fetcher, T4RelevanceFilter, T4SVSScorer, T4CircuitBreaker, Article, FilterResult

__all__ = [
    # existing exports
    # new T4 exports
    "T4State",
    "T4StatePersistence",
    "T4PIDLock",
    "T4Monitor",
    "T4Fetcher",
    "T4RelevanceFilter",
    "T4SVSScorer",
    "T4CircuitBreaker",
    "Article",
    "FilterResult",
]
```

- [ ] **Step 7.2: Run full T4 test suite**

```bash
cd /Users/nuzantara/Desktop/nuzantara
PYTHONPATH=. pytest tests/nlm_deep_research/ -v 2>&1 | tail -40
```

Expected: all existing pipeline tests STILL PASS + all new T4 tests PASS.

- [ ] **Step 7.3: Commit**

```bash
git add apps/evaluator/nlm_deep_research/__init__.py
git commit -m "feat(t4): export T4Monitor classes from nlm_deep_research package"
```

---

## Task 8: Cron shell script

**Files:**

- Create dir: `apps/evaluator/nlm_deep_research/scripts/`
- Create: `apps/evaluator/nlm_deep_research/scripts/run_t4_monitor.sh`

- [ ] **Step 8.1: Create the cron wrapper**

```bash
mkdir -p /Users/nuzantara/Desktop/nuzantara/apps/evaluator/nlm_deep_research/scripts
```

Create `apps/evaluator/nlm_deep_research/scripts/run_t4_monitor.sh`:

```bash
#!/usr/bin/env bash
# T4 Social Media Monitor — cron wrapper
# Schedule: 0 */6 * * *  (every 6 hours)
# Machine:  Air (antonellosiano@Nuzantara-9)
# Log:      ~/.openclaw/logs/t4_monitor.log
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../../.." && pwd)"

# Air uses venv (not .venv). Pro uses .venv — detect at runtime.
if [ -d "$PROJECT_ROOT/apps/backend-rag/venv" ]; then
    PYTHON="$PROJECT_ROOT/apps/backend-rag/venv/bin/python"
else
    PYTHON="$PROJECT_ROOT/apps/backend-rag/.venv/bin/python"
fi

LOCK_FILE="$SCRIPT_DIR/../t4.lock"
LOG_FILE="${HOME}/.openclaw/logs/t4_monitor.log"
mkdir -p "$(dirname "$LOG_FILE")"

# PID lock — prevent concurrent runs
if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [SKIP] T4 monitor already running (PID $PID)" >> "$LOG_FILE"
        exit 0
    fi
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [WARN] Stale lock (PID $PID) — cleaning up" >> "$LOG_FILE"
    rm -f "$LOCK_FILE"
fi
echo $$ > "$LOCK_FILE"
trap "rm -f '$LOCK_FILE'" EXIT

cd "$PROJECT_ROOT"
echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [START] T4 monitor (PID $$)" >> "$LOG_FILE"

PYTHONPATH=. "$PYTHON" -m apps.evaluator.nlm_deep_research.t4_monitor \
    --notebook-id "cff93ab0-813a-42f2-a8de-36987e724271" \
    --log-level INFO \
    2>&1 | tee -a "$LOG_FILE"

echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [DONE] T4 monitor completed" >> "$LOG_FILE"
```

- [ ] **Step 8.2: Add `__main__` entrypoint to `t4_monitor.py`**

Append at the bottom of `apps/evaluator/nlm_deep_research/t4_monitor.py`:

```python
# ---------------------------------------------------------------------------
# CLI entrypoint (python -m apps.evaluator.nlm_deep_research.t4_monitor)
# ---------------------------------------------------------------------------


def _parse_args() -> "argparse.Namespace":  # noqa: F821
    import argparse  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="T4 Social Media Monitor")
    parser.add_argument(
        "--notebook-id", default=NB2_ID, help="NLM notebook UUID"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Fetch + filter but do not ingest"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args()


if __name__ == "__main__":
    import sys

    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    monitor = T4Monitor(notebook_id=args.notebook_id, dry_run=args.dry_run)
    result = asyncio.run(monitor.run())
    print(
        f"T4 run complete: fetched={result.fetched} "
        f"ingested={result.ingested} rejected={result.rejected} "
        f"errors={result.errors}"
    )
    sys.exit(0 if result.errors == 0 else 1)
```

- [ ] **Step 8.3: Make script executable and smoke-test**

```bash
chmod +x apps/evaluator/nlm_deep_research/scripts/run_t4_monitor.sh

# Dry run — should print articles but not ingest
cd /Users/nuzantara/Desktop/nuzantara
PYTHONPATH=. apps/backend-rag/.venv/bin/python \
    -m apps.evaluator.nlm_deep_research.t4_monitor \
    --dry-run --log-level DEBUG 2>&1 | head -40
```

Expected output includes lines like:

```
INFO t4_monitor Fetching RSS: https://ngurahrai.imigrasi.go.id/feed/
INFO t4_monitor [DRY-RUN] Would ingest: Imigrasi Ngurah Rai Deportasi WN Korea (SVS=0.58)
T4 run complete: fetched=12 ingested=0 rejected=8 errors=0
```

- [ ] **Step 8.4: Commit**

```bash
git add apps/evaluator/nlm_deep_research/scripts/run_t4_monitor.sh \
        apps/evaluator/nlm_deep_research/t4_monitor.py
git commit -m "feat(t4): add cron shell wrapper and __main__ CLI entrypoint"
```

---

## Task 9: Final integration test and OpenClaw cron registration

**Files:**

- No code changes — verify, register cron on Air

- [ ] **Step 9.1: Run complete test suite**

```bash
cd /Users/nuzantara/Desktop/nuzantara
PYTHONPATH=. pytest tests/nlm_deep_research/ -q 2>&1 | tail -10
```

Expected: `X passed, 0 failed, 0 errors` (X = all existing + new T4 tests).

- [ ] **Step 9.2: Live dry-run against Ngurah Rai RSS (confirm live feed)**

```bash
PYTHONPATH=. apps/backend-rag/.venv/bin/python \
    -m apps.evaluator.nlm_deep_research.t4_monitor \
    --dry-run 2>&1 | grep -E "ADMIT|REJECT|Would ingest|fetched"
```

Expected: ≥2 articles from `ngurahrai.imigrasi.go.id/feed/` reaching ADMIT.

- [ ] **Step 9.3: Register cron on Air via OpenClaw**

SSH to Air and add the cron entry:

```bash
ssh air 'crontab -l 2>/dev/null | grep -v t4_monitor | { cat; echo "0 */6 * * * /bin/bash /Users/antonellosiano/Projects/nuzantara/apps/evaluator/nlm_deep_research/scripts/run_t4_monitor.sh >> /Users/antonellosiano/.openclaw/logs/t4_monitor.log 2>&1"; } | crontab -'
# Verify:
ssh air 'crontab -l | grep t4'
```

Expected output: `0 */6 * * * /bin/bash .../run_t4_monitor.sh ...`

- [ ] **Step 9.4: Final commit**

```bash
git add -A
git commit -m "feat(t4): T4 Social Media Monitor complete — RSS/web/X, 3-layer filter, CB_T4, cron"
```

---

## Self-Review

**Spec coverage check:**

| Spec section                  | Covered by                                                    |
| ----------------------------- | ------------------------------------------------------------- |
| Website-first RSS (Layer 1)   | Task 5 `T4Fetcher.fetch_rss`                                  |
| Website scraping (Layer 2)    | Task 5 `T4Fetcher.fetch_website`                              |
| X/Twitter time-boxed          | Task 5 `T4Fetcher.fetch_twitter` + Task 6 `_get_bearer_token` |
| Instagram deferred v2         | Not implemented (correct per spec)                            |
| 3-layer relevance filter      | Task 2 `T4RelevanceFilter`                                    |
| SVS admission gate ≥0.35      | Task 3 `T4SVSScorer` + Task 6 `_maybe_ingest`                 |
| Hard T4 budget cap (11 slots) | Task 1 `T4State.is_over_budget` + Task 6 budget check         |
| FIFO rotation on budget full  | Task 1 `T4State.evict_oldest`                                 |
| CB_T4 standalone FSM          | Task 4 `T4CircuitBreaker`                                     |
| nlm CLI subprocess pattern    | Task 6 `T4Monitor._call_nlm_cli`                              |
| PID lock                      | Task 1 `T4PIDLock` + Task 8 shell script                      |
| dedup by article_id           | Task 1 `T4State.seen_ids` + Task 5 URL hash                   |
| NLM content format            | Task 6 `T4Monitor._format_for_nlm`                            |
| Cron every 6h                 | Task 8 shell script                                           |
| NB-2 notebook ID              | Task 6 constant `NB2_ID`                                      |
| X time-box 30 days            | `T4State.x_enabled_until` field (enforcement deferred to ops) |
| `__init__.py` exports         | Task 7                                                        |

**Placeholder scan:** None found.

**Type consistency:**

- `Article` defined Task 3, used consistently in Tasks 5, 6
- `T4State` defined Task 1, used in Tasks 4, 6
- `FilterResult` defined Task 2, used in Task 6 `_maybe_ingest`
- `T4Fetcher`, `T4RelevanceFilter`, `T4SVSScorer`, `T4CircuitBreaker` all defined before `T4Monitor` references them ✓
