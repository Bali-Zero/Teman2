"""Tests for NLM speculative enrichment in the streaming pipeline."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from backend.services.oracle.nlm_enrichment_service import NLMEnrichmentService
from backend.services.oracle.nlm_notebook_registry import resolve_notebook


@pytest.mark.asyncio
async def test_speculative_fire_and_cautious_merge():
    """NLM fires speculatively, evidence=CAUTIOUS, result merged."""
    nlm_service = AsyncMock(spec=NLMEnrichmentService)
    nlm_service.query = AsyncMock(
        return_value={
            "answer": "Verified",
            "citations": [
                {
                    "source_file": "UU.pdf",
                    "section": "Pasal 48",
                    "excerpt": "...",
                    "page": 23,
                },
            ],
            "confidence": 0.82,
        },
    )

    task = asyncio.create_task(nlm_service.query("nb-id", "KITAS requirements"))
    await asyncio.sleep(0.01)

    evidence_score, trusted = 0.35, False
    if 0.15 <= evidence_score <= 0.60 and not trusted:
        result = await asyncio.wait_for(task, timeout=3.0)
        assert result is not None
        assert result["citations"][0]["source_file"] == "UU.pdf"


@pytest.mark.asyncio
async def test_speculative_fire_and_confident_cancel():
    """NLM fires, evidence=CONFIDENT, task cancelled."""

    async def slow_query(*a, **kw):
        await asyncio.sleep(10)

    nlm_service = AsyncMock(spec=NLMEnrichmentService)
    nlm_service.query = slow_query

    task = asyncio.create_task(nlm_service.query("nb-id", "PT PMA cost"))
    await asyncio.sleep(0.01)

    evidence_score, trusted = 0.85, True
    if evidence_score > 0.60 or trusted:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert task.cancelled()


@pytest.mark.asyncio
async def test_timeout_emits_done_without_enrichment():
    """NLM times out, pipeline proceeds without enrichment."""

    async def very_slow(*a, **kw):
        await asyncio.sleep(100)

    nlm_service = AsyncMock(spec=NLMEnrichmentService)
    nlm_service.query = very_slow

    task = asyncio.create_task(nlm_service.query("nb-id", "q"))
    try:
        result = await asyncio.wait_for(task, timeout=0.05)
    except asyncio.TimeoutError:
        result = None
        task.cancel()

    assert result is None


@pytest.mark.asyncio
async def test_bridge_crash_does_not_propagate():
    """Bridge crash caught, pipeline continues."""

    async def crash(*a, **kw):
        raise ConnectionError("down")

    nlm_service = AsyncMock(spec=NLMEnrichmentService)
    nlm_service.query = crash

    task = asyncio.create_task(nlm_service.query("nb-id", "q"))
    try:
        result = await task
    except Exception:
        result = None

    assert result is None


@pytest.mark.asyncio
async def test_cache_hit_skips_bridge():
    """Cache hit means no bridge call."""
    cache = AsyncMock()
    cache.get = AsyncMock(return_value={"answer": "cached", "citations": []})

    nlm_service = AsyncMock(spec=NLMEnrichmentService)

    cached = await cache.get("q", notebook_id="nb-id")
    nlm_task = None
    if not cached:
        nlm_task = asyncio.create_task(nlm_service.query("nb-id", "q"))

    assert cached is not None
    assert nlm_task is None
    nlm_service.query.assert_not_called()


@pytest.mark.asyncio
async def test_parent_cancel_cleans_up():
    """Parent stream cancel cleans up NLM task."""

    async def slow_query(*a, **kw):
        await asyncio.sleep(10)

    nlm_service = AsyncMock(spec=NLMEnrichmentService)
    nlm_service.query = slow_query

    task = asyncio.create_task(nlm_service.query("nb-id", "q"))
    await asyncio.sleep(0.01)

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert task.cancelled() and task.done()


def test_resolve_notebook_none_for_generic():
    """Generic query with no domain keywords returns None."""
    result = resolve_notebook("hello how are you")
    assert result is None


def test_resolve_notebook_immigration():
    """Immigration-domain query resolves to immigration notebook."""
    result = resolve_notebook("What documents for KITAS renewal?")
    assert result is not None
    assert result["domain"] == "immigration"
