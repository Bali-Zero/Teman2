"""Tests for nlm_shadow_retrieval — runtime read of Sprint 2 collection."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.oracle import nlm_shadow_retrieval as nsr


def _hit(payload: dict, score: float = 0.8) -> SimpleNamespace:
    return SimpleNamespace(payload=payload, score=score)


def _fresh_payload(**overrides) -> dict:
    base = {
        "claim_text": "PT PMA minimum capital is IDR 10 billion under PP 28/2025.",
        "source": "nlm_shadow",
        "nb_id": "nb-uuid",
        "nb_label": "company",
        "extraction_run_id": "r1",
        "extracted_at": datetime.now(tz=timezone.utc).isoformat(),
        "deepseek_confidence": 0.85,
        "ttl_hours": 72,
    }
    base.update(overrides)
    return base


# ── activation flag ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_disabled_returns_empty(monkeypatch):
    monkeypatch.delenv("NLM_SHADOW_RETRIEVAL_ENABLED", raising=False)
    assert await nsr.search_nlm_shadow_claims([0.0] * 1536) == []


@pytest.mark.asyncio
async def test_enabled_with_no_client_returns_empty(monkeypatch):
    monkeypatch.setenv("NLM_SHADOW_RETRIEVAL_ENABLED", "1")
    out = await nsr.search_nlm_shadow_claims([0.0] * 1536, qdrant_client=None)
    assert out == []


# ── happy path ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_returns_top_k_filtered_by_confidence(monkeypatch):
    monkeypatch.setenv("NLM_SHADOW_RETRIEVAL_ENABLED", "1")
    fake_hits = [
        _hit(_fresh_payload(claim_text="A", deepseek_confidence=0.9), score=0.95),
        _hit(_fresh_payload(claim_text="B", deepseek_confidence=0.4), score=0.92),  # below min_conf
        _hit(_fresh_payload(claim_text="C", deepseek_confidence=0.7), score=0.88),
        _hit(_fresh_payload(claim_text="D", deepseek_confidence=0.65), score=0.85),
    ]
    client = MagicMock()
    client.search = MagicMock(return_value=fake_hits)

    out = await nsr.search_nlm_shadow_claims(
        [0.0] * 1536, qdrant_client=client, top_k=5, min_confidence=0.6
    )
    assert [c["claim_text"] for c in out] == ["A", "C", "D"]
    assert all(c["score"] > 0 for c in out)


@pytest.mark.asyncio
async def test_domain_filter_passed_to_qdrant(monkeypatch):
    monkeypatch.setenv("NLM_SHADOW_RETRIEVAL_ENABLED", "1")
    client = MagicMock()
    client.search = MagicMock(return_value=[_hit(_fresh_payload(nb_label="tax"))])

    await nsr.search_nlm_shadow_claims(
        [0.0] * 1536, domain="tax", qdrant_client=client
    )

    # Verify the Qdrant filter included nb_label=tax
    call_kwargs = client.search.call_args.kwargs
    qfilter = call_kwargs["query_filter"]
    nb_conditions = [
        c for c in qfilter.must if getattr(c, "key", None) == "nb_label"
    ]
    assert len(nb_conditions) == 1
    assert nb_conditions[0].match.value == "tax"


@pytest.mark.asyncio
async def test_unknown_domain_dropped(monkeypatch):
    monkeypatch.setenv("NLM_SHADOW_RETRIEVAL_ENABLED", "1")
    client = MagicMock()
    client.search = MagicMock(return_value=[])

    await nsr.search_nlm_shadow_claims(
        [0.0] * 1536, domain="not-a-domain", qdrant_client=client
    )

    # Filter must NOT include nb_label since the domain was rejected
    qfilter = client.search.call_args.kwargs["query_filter"]
    nb_conditions = [c for c in qfilter.must if getattr(c, "key", None) == "nb_label"]
    assert nb_conditions == []


# ── expiration ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_expired_claims_are_dropped(monkeypatch):
    monkeypatch.setenv("NLM_SHADOW_RETRIEVAL_ENABLED", "1")
    old_ts = (datetime.now(tz=timezone.utc) - timedelta(hours=200)).isoformat()
    fake = [
        _hit(_fresh_payload(claim_text="OLD", extracted_at=old_ts, ttl_hours=72)),
        _hit(_fresh_payload(claim_text="FRESH")),
    ]
    client = MagicMock()
    client.search = MagicMock(return_value=fake)

    out = await nsr.search_nlm_shadow_claims([0.0] * 1536, qdrant_client=client)
    texts = [c["claim_text"] for c in out]
    assert "FRESH" in texts
    assert "OLD" not in texts


@pytest.mark.asyncio
async def test_expired_kept_when_skip_expired_false(monkeypatch):
    monkeypatch.setenv("NLM_SHADOW_RETRIEVAL_ENABLED", "1")
    old_ts = (datetime.now(tz=timezone.utc) - timedelta(hours=200)).isoformat()
    fake = [_hit(_fresh_payload(claim_text="OLD", extracted_at=old_ts, ttl_hours=72))]
    client = MagicMock()
    client.search = MagicMock(return_value=fake)

    out = await nsr.search_nlm_shadow_claims(
        [0.0] * 1536, qdrant_client=client, skip_expired=False
    )
    assert len(out) == 1
    assert out[0]["claim_text"] == "OLD"


# ── error handling ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_qdrant_search_exception_returns_empty(monkeypatch):
    monkeypatch.setenv("NLM_SHADOW_RETRIEVAL_ENABLED", "1")
    client = MagicMock()
    client.search = MagicMock(side_effect=Exception("connection refused"))
    assert await nsr.search_nlm_shadow_claims([0.0] * 1536, qdrant_client=client) == []


@pytest.mark.asyncio
async def test_async_qdrant_client_supported(monkeypatch):
    monkeypatch.setenv("NLM_SHADOW_RETRIEVAL_ENABLED", "1")
    client = MagicMock()
    client.search = AsyncMock(return_value=[_hit(_fresh_payload(claim_text="ASYNC"))])
    out = await nsr.search_nlm_shadow_claims([0.0] * 1536, qdrant_client=client)
    assert len(out) == 1
    assert out[0]["claim_text"] == "ASYNC"
