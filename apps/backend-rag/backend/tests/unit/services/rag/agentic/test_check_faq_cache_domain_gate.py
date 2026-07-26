"""Phase-0 safety rail (FATAL 1, research/operations/2026-07-17-full-domain-
cache-design.md §8): OrchestratorCore.check_faq_cache() domain-scoped lookup
+ runtime domain-match check.

Three behaviors under test:
1. A concrete classified domain tries the domain-scoped key first.
2. MIGRATION BRIDGE: a domain-scoped miss falls back to the legacy unscoped
   key ONLY when the legacy hit's own stored domain matches the classified
   query domain — a mismatch is a MISS, never served cross-domain.
3. An unclassified/general domain skips the FAQ cache entirely (no key to
   safely scope by) rather than risk a cross-domain unscoped hit.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.services.caching.notebooklm_cache_service import domain_scope_id
from backend.services.rag.agentic.entity_extractor import EntityExtractionService
from backend.services.rag.agentic.orchestrator_core import OrchestratorCore


def make_core() -> OrchestratorCore:
    core = OrchestratorCore.__new__(OrchestratorCore)
    core.semantic_cache = None
    core.faq_cache = None
    core.retriever = None
    core.entity_extractor = None
    core.kg_retrieval = None
    core.kg_langgraph_orchestrator = None
    core.db_pool = None
    core.reasoning_engine = None
    core.llm_gateway = object()
    core.context_manager = None
    core.query_gates = None
    core.prompt_builder = None
    core.routing_manager = None
    core._surface_router = None
    core._specialized_router = None
    core._multi_agent_coordinator = None
    core._kg_auto_expansion = None
    return core


class FakeFaqCache:
    """In-memory stand-in keyed by (notebook_id, normalized question) —
    mirrors NotebookLMCacheService's real scoping semantics closely enough
    for this test without touching Redis."""

    def __init__(self) -> None:
        self.store: dict[tuple[str, str], dict] = {}

    def seed(self, question: str, answer: str, *, domain: str, notebook_id: str = "") -> None:
        self.store[(notebook_id, question)] = {
            "answer": answer,
            "metadata": {"domain": domain, "source": "team_qa"},
        }

    async def get(self, question: str, notebook_id: str = "") -> dict | None:
        return self.store.get((notebook_id, question))


@pytest.fixture
def faq_cache() -> FakeFaqCache:
    return FakeFaqCache()


# ── Domain-scoped hit (the common post-Phase-0 case) ────────────────────────


@pytest.mark.asyncio
async def test_domain_scoped_key_hit_is_served(faq_cache: FakeFaqCache) -> None:
    faq_cache.seed(
        "What is the E33 deposit amount?",
        "USD 130,000.",
        domain="visa",
        notebook_id=domain_scope_id("visa"),
    )
    core = make_core()
    core.faq_cache = faq_cache

    with patch("backend.app.metrics.faq_cache_hits_total") as mock_hits:
        result = await core.check_faq_cache(
            "What is the E33 deposit amount?",
            {"domain": "visa"},
            start_time=0.0,
        )

    assert result is not None
    assert result.answer == "USD 130,000."
    mock_hits.labels.assert_called_once_with(domain="visa")


# ── GUILT: cross-domain collision must never cross-serve ───────────────────


@pytest.mark.asyncio
async def test_same_question_two_domains_never_cross_serve(faq_cache: FakeFaqCache) -> None:
    faq_cache.seed(
        "What documents do I need?",
        "Visa answer.",
        domain="visa",
        notebook_id=domain_scope_id("visa"),
    )
    faq_cache.seed(
        "What documents do I need?",
        "Tax answer.",
        domain="tax",
        notebook_id=domain_scope_id("tax"),
    )
    core = make_core()
    core.faq_cache = faq_cache

    with patch("backend.app.metrics.faq_cache_hits_total"):
        visa_result = await core.check_faq_cache(
            "What documents do I need?",
            {"domain": "visa"},
            start_time=0.0,
        )
        tax_result = await core.check_faq_cache(
            "What documents do I need?",
            {"domain": "tax"},
            start_time=0.0,
        )

    assert visa_result.answer == "Visa answer."
    assert tax_result.answer == "Tax answer."


# ── Migration bridge: legacy unscoped key ───────────────────────────────────


@pytest.mark.asyncio
async def test_legacy_unscoped_hit_served_when_stored_domain_matches(
    faq_cache: FakeFaqCache,
) -> None:
    """The 216 pre-Phase-0 E33 rows live under the OLD unscoped key scheme —
    must still be reachable when the classified domain matches what's
    stored, without requiring a reload."""
    faq_cache.seed("What is the E33 deposit amount?", "USD 130,000.", domain="visa")
    core = make_core()
    core.faq_cache = faq_cache

    with patch("backend.app.metrics.faq_cache_hits_total"):
        result = await core.check_faq_cache(
            "What is the E33 deposit amount?",
            {"domain": "visa"},
            start_time=0.0,
        )

    assert result is not None
    assert result.answer == "USD 130,000."


@pytest.mark.asyncio
async def test_legacy_unscoped_hit_refused_on_domain_mismatch(faq_cache: FakeFaqCache) -> None:
    """GUILT — a legacy unscoped key whose stored domain does NOT match the
    classified query domain must be treated as a MISS, logged, and counted
    — never served cross-domain."""
    faq_cache.seed("What documents do I need?", "Tax answer.", domain="tax")
    core = make_core()
    core.faq_cache = faq_cache

    with (
        patch(
            "backend.app.metrics.faq_cache_domain_mismatch_averted_total",
        ) as mock_mismatch,
        patch("backend.app.metrics.faq_cache_misses_total") as mock_misses,
    ):
        result = await core.check_faq_cache(
            "What documents do I need?",
            {"domain": "visa"},
            start_time=0.0,
        )

    assert result is None
    mock_mismatch.labels.assert_called_once_with(classified_domain="visa", stored_domain="tax")
    mock_misses.inc.assert_called_once()


# ── Unclassified domain: FAQ cache skipped entirely ─────────────────────────


@pytest.mark.asyncio
async def test_missing_domain_skips_faq_cache_entirely(faq_cache: FakeFaqCache) -> None:
    """INNOCENCE — with no classified domain there is no safe key to check;
    the FAQ cache must be skipped rather than risk an unscoped cross-domain
    hit, even when a matching unscoped entry technically exists."""
    faq_cache.seed("some generic question", "some answer", domain="visa")
    core = make_core()
    core.faq_cache = faq_cache

    result = await core.check_faq_cache("some generic question", {}, start_time=0.0)

    assert result is None


@pytest.mark.asyncio
async def test_general_domain_skips_faq_cache_entirely(faq_cache: FakeFaqCache) -> None:
    """INNOCENCE — EntityExtractionService.DOMAIN_GENERAL is treated
    identically to a missing domain."""
    faq_cache.seed("some generic question", "some answer", domain="visa")
    core = make_core()
    core.faq_cache = faq_cache

    result = await core.check_faq_cache(
        "some generic question",
        {"domain": EntityExtractionService.DOMAIN_GENERAL},
        start_time=0.0,
    )

    assert result is None


@pytest.mark.asyncio
async def test_no_faq_cache_configured_returns_none() -> None:
    core = make_core()
    core.faq_cache = None

    result = await core.check_faq_cache("query", {"domain": "visa"}, start_time=0.0)

    assert result is None
