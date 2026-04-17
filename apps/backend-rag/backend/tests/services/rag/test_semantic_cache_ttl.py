"""Tests for semantic cache domain-aware TTL and invalidate_by_domain (HIGH-12).

Covers:
- classify_query_domain returns correct domain for each keyword class
- ttl_for_domain resolves per-domain seconds (1h / 4h / 2h / 6h)
- cache_response_async uses domain-derived TTL via Redis.setex
- cache_response_async accepts explicit ``domain=`` override
- L1 LRU expires after _L1_TTL seconds (time-based, monkeypatched clock)
- invalidate_by_domain wipes only L1 entries tagged with that domain
- invalidate_by_domain wipes only L2 Redis keys under the domain prefix
"""
from __future__ import annotations

import importlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.caching import semantic_cache as sc


@pytest.fixture(autouse=True)
def _reset_semantic_cache() -> None:
    """Ensure every test starts with a clean in-memory L1 and a fresh module state."""
    sc._L1_CACHE.clear()
    sc._redis_checked = False
    sc._redis_client = None
    yield
    sc._L1_CACHE.clear()
    sc._redis_checked = False
    sc._redis_client = None


# ── Domain classifier ──────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("How much does a KITAS cost?", sc.DOMAIN_PRICING),
        ("what is the price of a company setup", sc.DOMAIN_PRICING),
        ("berapa biaya C7A?", sc.DOMAIN_PRICING),
        ("Is KITAS valid for 2 years?", sc.DOMAIN_VISA),
        ("Can I convert C1 visa to KITAS", sc.DOMAIN_VISA),
        ("what does UU PDP require for DPO?", sc.DOMAIN_LEGAL),
        ("latest immigration regulation 2026", sc.DOMAIN_LEGAL),
        ("Hello, who are you?", sc.DOMAIN_GENERAL),
    ],
)
def test_classify_query_domain(query: str, expected: str) -> None:
    assert sc.classify_query_domain(query) == expected


def test_ttl_for_domain_table() -> None:
    assert sc.ttl_for_domain(sc.DOMAIN_PRICING) == 3600
    assert sc.ttl_for_domain(sc.DOMAIN_LEGAL) == 14400
    assert sc.ttl_for_domain(sc.DOMAIN_VISA) == 7200
    assert sc.ttl_for_domain(sc.DOMAIN_GENERAL) == 21600
    # Unknown domain falls back to general
    assert sc.ttl_for_domain("unknown-xyz") == 21600


# ── Domain-aware put uses the right TTL ────────────────────────────────────

@pytest.mark.asyncio
async def test_cache_response_async_uses_domain_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_redis = MagicMock()
    fake_redis.setex = AsyncMock()
    monkeypatch.setattr(sc, "_get_redis_client", lambda: fake_redis)

    # Pricing query → 3600s
    await sc.cache_response_async("What's the cost of KITAS?", {"ok": True})
    (key, ttl, _payload) = fake_redis.setex.call_args.args
    assert ttl == 3600
    assert key.startswith(f"{sc._L2_PREFIX}:{sc.DOMAIN_PRICING}:")

    fake_redis.setex.reset_mock()
    # Legal query → 14400s
    await sc.cache_response_async("Immigration regulation 2026", {"ok": True})
    (key, ttl, _payload) = fake_redis.setex.call_args.args
    assert ttl == 14400
    assert key.startswith(f"{sc._L2_PREFIX}:{sc.DOMAIN_LEGAL}:")

    fake_redis.setex.reset_mock()
    # Visa query → 7200s
    await sc.cache_response_async("Can I extend my KITAS in Bali?", {"ok": True})
    (key, ttl, _payload) = fake_redis.setex.call_args.args
    assert ttl == 7200
    assert key.startswith(f"{sc._L2_PREFIX}:{sc.DOMAIN_VISA}:")

    fake_redis.setex.reset_mock()
    # General query → 21600s
    await sc.cache_response_async("Hello Zantara!", {"ok": True})
    (key, ttl, _payload) = fake_redis.setex.call_args.args
    assert ttl == 21600
    assert key.startswith(f"{sc._L2_PREFIX}:{sc.DOMAIN_GENERAL}:")


@pytest.mark.asyncio
async def test_cache_response_async_honours_explicit_domain(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_redis = MagicMock()
    fake_redis.setex = AsyncMock()
    monkeypatch.setattr(sc, "_get_redis_client", lambda: fake_redis)

    # Query with no domain-matching keywords, but caller knows it's legal.
    await sc.cache_response_async("mostra l'articolo 12", {"ok": True}, domain=sc.DOMAIN_LEGAL)
    (key, ttl, _payload) = fake_redis.setex.call_args.args
    assert ttl == 14400
    assert key.startswith(f"{sc._L2_PREFIX}:{sc.DOMAIN_LEGAL}:")


@pytest.mark.asyncio
async def test_cache_response_async_ttl_override_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_redis = MagicMock()
    fake_redis.setex = AsyncMock()
    monkeypatch.setattr(sc, "_get_redis_client", lambda: fake_redis)

    await sc.cache_response_async("What's the price?", {"ok": True}, ttl=42)
    (_key, ttl, _payload) = fake_redis.setex.call_args.args
    assert ttl == 42


# ── L1 TTL expiry ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_l1_entry_expires_after_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    # Redis absent → L1-only mode.
    monkeypatch.setattr(sc, "_get_redis_client", lambda: None)

    now_slot = [1_700_000_000.0]
    monkeypatch.setattr(sc.time, "time", lambda: now_slot[0])

    await sc.cache_response_async("pricing question", {"answer": "v1"})
    assert sc.get_cached_response("pricing question") == {"answer": "v1"}

    # Advance beyond _L1_TTL
    now_slot[0] += sc._L1_TTL + 1
    assert sc.get_cached_response("pricing question") is None
    assert "pricing question" not in (e.get("query") for e in sc._L1_CACHE.values())


# ── invalidate_by_domain ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_invalidate_by_domain_clears_only_target_l1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sc, "_get_redis_client", lambda: None)

    await sc.cache_response_async("price list", {"r": 1})           # pricing
    await sc.cache_response_async("new UU PDP article", {"r": 2})   # legal
    await sc.cache_response_async("hello there", {"r": 3})          # general

    assert len(sc._L1_CACHE) == 3
    cleared = await sc.invalidate_by_domain(sc.DOMAIN_LEGAL)
    assert cleared == 1
    # pricing + general must survive
    remaining_domains = [e["domain"] for e in sc._L1_CACHE.values()]
    assert sc.DOMAIN_LEGAL not in remaining_domains
    assert sc.DOMAIN_PRICING in remaining_domains
    assert sc.DOMAIN_GENERAL in remaining_domains


@pytest.mark.asyncio
async def test_invalidate_by_domain_scans_only_domain_redis_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_redis = MagicMock()
    fake_redis.setex = AsyncMock()
    # keys() returns only the keys matching the pattern — we record it.
    observed_patterns: list[str] = []

    async def fake_keys(pattern: str) -> list[bytes]:
        observed_patterns.append(pattern)
        # Respond with 2 fake matches for legal only.
        if sc.DOMAIN_LEGAL in pattern:
            return [b"semantic_cache:legal:aaaa", b"semantic_cache:legal:bbbb"]
        return []

    fake_redis.keys = fake_keys
    fake_redis.delete = AsyncMock(return_value=2)
    monkeypatch.setattr(sc, "_get_redis_client", lambda: fake_redis)

    cleared = await sc.invalidate_by_domain(sc.DOMAIN_LEGAL)

    assert observed_patterns == [f"{sc._L2_PREFIX}:{sc.DOMAIN_LEGAL}:*"]
    assert cleared == 2
    fake_redis.delete.assert_awaited_once()
