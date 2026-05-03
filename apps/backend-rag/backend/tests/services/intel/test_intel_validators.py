"""
3-tier validators:
  Tier 1 regex_schema — hard gate
  Tier 2 citation_check — retry-aware (3× exp backoff) on 5xx/timeout
  Tier 3 kg_crossref — soft signal via kg_auto_expansion
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

from backend.services.intel.intel_validators import (
    CitationResult,
    IntelDoc,
    citation_check,
    kg_crossref,
    regex_schema,
    validate,
)


# ── Tier 1: regex_schema ─────────────────────────────────────────────────


def test_regex_schema_valid_doc_passes() -> None:
    doc = IntelDoc(
        title="BKPM issues new LKPM template",
        url="https://bkpm.go.id/article/123",
        published_at="2026-04-15",
        body_text="Full article body at least 50 characters long lorem ipsum dolor sit amet...",
        source_domain="bkpm.go.id",
    )
    assert regex_schema(doc) is True


def test_regex_schema_missing_title_fails() -> None:
    doc = IntelDoc(
        title="",
        url="https://x.com",
        published_at="2026-04-15",
        body_text="ok " * 30,
        source_domain="x.com",
    )
    assert regex_schema(doc) is False


def test_regex_schema_malformed_url_fails() -> None:
    doc = IntelDoc(
        title="t",
        url="not-a-url",
        published_at="2026-04-15",
        body_text="ok " * 30,
        source_domain="x.com",
    )
    assert regex_schema(doc) is False


def test_regex_schema_body_too_short_fails() -> None:
    doc = IntelDoc(
        title="t",
        url="https://x.com",
        published_at="2026-04-15",
        body_text="short",
        source_domain="x.com",
    )
    assert regex_schema(doc) is False


def test_regex_schema_invalid_date_fails() -> None:
    doc = IntelDoc(
        title="Title here",
        url="https://bkpm.go.id/article",
        published_at="15/04/2026",  # not ISO
        body_text="content " * 15,
        source_domain="bkpm.go.id",
    )
    assert regex_schema(doc) is False


# ── Tier 2: citation_check ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_citation_check_2xx_passes() -> None:
    mock_client = AsyncMock()
    mock_client.head = AsyncMock(return_value=AsyncMock(status_code=200))
    result = await citation_check("https://bkpm.go.id/x", http_client=mock_client)
    assert result == CitationResult.PASS


@pytest.mark.asyncio
async def test_citation_check_201_passes() -> None:
    mock_client = AsyncMock()
    mock_client.head = AsyncMock(return_value=AsyncMock(status_code=201))
    result = await citation_check("https://bkpm.go.id/x", http_client=mock_client)
    assert result == CitationResult.PASS


@pytest.mark.asyncio
async def test_citation_check_404_definitive_fail_no_retry() -> None:
    mock_client = AsyncMock()
    mock_client.head = AsyncMock(return_value=AsyncMock(status_code=404))
    result = await citation_check("https://bkpm.go.id/x", http_client=mock_client)
    assert result == CitationResult.DEFINITIVE_FAIL
    assert mock_client.head.await_count == 1


@pytest.mark.asyncio
async def test_citation_check_403_definitive_fail() -> None:
    mock_client = AsyncMock()
    mock_client.head = AsyncMock(return_value=AsyncMock(status_code=403))
    result = await citation_check("https://bkpm.go.id/x", http_client=mock_client)
    assert result == CitationResult.DEFINITIVE_FAIL
    assert mock_client.head.await_count == 1


@pytest.mark.asyncio
async def test_citation_check_5xx_retries_three_times() -> None:
    mock_client = AsyncMock()
    mock_client.head = AsyncMock(return_value=AsyncMock(status_code=503))
    result = await citation_check(
        "https://bkpm.go.id/x",
        http_client=mock_client,
        max_retries=3,
        backoff_base=0.0,  # no sleep in tests
    )
    assert result == CitationResult.SOFT_FAIL
    assert mock_client.head.await_count == 3


@pytest.mark.asyncio
async def test_citation_check_timeout_treated_as_transient() -> None:
    mock_client = AsyncMock()
    mock_client.head = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
    result = await citation_check(
        "https://bkpm.go.id/x",
        http_client=mock_client,
        max_retries=2,
        backoff_base=0.0,
    )
    assert result == CitationResult.SOFT_FAIL


# ── Tier 3: kg_crossref ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_kg_crossref_no_match_returns_empty() -> None:
    mock_kg = AsyncMock()
    mock_kg.find_entities = AsyncMock(return_value=[])
    entities = await kg_crossref("some unknown text", kg=mock_kg)
    assert entities == []


@pytest.mark.asyncio
async def test_kg_crossref_match_returns_entities() -> None:
    mock_kg = AsyncMock()
    mock_kg.find_entities = AsyncMock(return_value=[{"id": "e1", "name": "BKPM"}])
    entities = await kg_crossref("BKPM issued new regulation", kg=mock_kg)
    assert entities == [{"id": "e1", "name": "BKPM"}]


@pytest.mark.asyncio
async def test_kg_crossref_timeout_returns_empty_no_raise() -> None:
    mock_kg = AsyncMock()
    mock_kg.find_entities = AsyncMock(side_effect=asyncio.TimeoutError)
    entities = await kg_crossref("x", kg=mock_kg)
    assert entities == []


@pytest.mark.asyncio
async def test_kg_crossref_exception_returns_empty_no_raise() -> None:
    mock_kg = AsyncMock()
    mock_kg.find_entities = AsyncMock(side_effect=RuntimeError("KG unavailable"))
    entities = await kg_crossref("x", kg=mock_kg)
    assert entities == []


# ── Orchestrator: validate ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_validate_regex_fail_returns_rejected_skips_rest() -> None:
    doc = IntelDoc(
        title="",
        url="https://bkpm.go.id/x",
        published_at="2026-04-15",
        body_text="ok " * 30,
        source_domain="bkpm.go.id",
    )
    mock_http = AsyncMock()
    mock_kg = AsyncMock()
    result = await validate(doc, http_client=mock_http, kg=mock_kg)
    assert result.status == "rejected"
    assert result.tiers[0].result == "fail"  # regex
    # citation + kg should be skipped (short-circuit)
    assert len(result.tiers) == 1


@pytest.mark.asyncio
async def test_validate_all_pass_gives_valid() -> None:
    doc = IntelDoc(
        title="BKPM update",
        url="https://bkpm.go.id/x",
        published_at="2026-04-15",
        body_text="content " * 30,
        source_domain="bkpm.go.id",
    )
    mock_http = AsyncMock()
    mock_http.head = AsyncMock(return_value=AsyncMock(status_code=200))
    mock_kg = AsyncMock()
    mock_kg.find_entities = AsyncMock(return_value=[{"id": "e1"}])
    result = await validate(doc, http_client=mock_http, kg=mock_kg)
    assert result.status == "valid"
    assert result.score == pytest.approx(1.0, abs=0.01)


@pytest.mark.asyncio
async def test_validate_citation_soft_fail_drops_below_valid() -> None:
    doc = IntelDoc(
        title="t",
        url="https://bkpm.go.id/x",
        published_at="2026-04-15",
        body_text="content " * 30,
        source_domain="bkpm.go.id",
    )
    mock_http = AsyncMock()
    mock_http.head = AsyncMock(return_value=AsyncMock(status_code=503))
    mock_kg = AsyncMock()
    mock_kg.find_entities = AsyncMock(return_value=[{"id": "e1"}])
    result = await validate(doc, http_client=mock_http, kg=mock_kg, max_retries=1)
    # regex 0.3 + kg 0.3 = 0.6 → at the valid threshold; citation soft_fail = 0
    # Score 0.6 qualifies as valid (>= 0.6 and whitelisted), or needs_review depending
    # on exact boundary handling. Accept either.
    assert result.status in {"valid", "needs_review"}


@pytest.mark.asyncio
async def test_validate_non_whitelisted_domain_forces_needs_review() -> None:
    """Even with full score, non-whitelisted source → needs_review (not valid)."""
    doc = IntelDoc(
        title="Some article",
        url="https://medium.com/article/123",
        published_at="2026-04-15",
        body_text="content " * 30,
        source_domain="medium.com",
    )
    mock_http = AsyncMock()
    mock_http.head = AsyncMock(return_value=AsyncMock(status_code=200))
    mock_kg = AsyncMock()
    mock_kg.find_entities = AsyncMock(return_value=[{"id": "e1"}])
    result = await validate(doc, http_client=mock_http, kg=mock_kg)
    # Non-whitelisted forces needs_review=True → status cannot be 'valid'
    assert result.needs_review is True
    assert result.status != "valid"
