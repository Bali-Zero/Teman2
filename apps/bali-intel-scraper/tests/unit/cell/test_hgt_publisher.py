"""Unit tests for intel-scraper-cell hgt_publisher.

Mocks redis.asyncio.Redis with AsyncMock — no real Redis. Cf.
``packages/cell-core/tests/hgt/`` for the underlying HGTPublisher tests.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.cell.hgt_publisher import (
    IntelScraperHGTBridge,
    StructuralPattern,
)


def _make_pattern(
    *,
    confidence: float = 0.85,
    procedure: str = "Site exposes RSS at /api/v2/news with stable schema",
    precondition: str = "scraper hits djp.go.id homepage",
    success_criterion: str = "feed parses and yields ≥1 item",
    domain: str = "news",
    pattern_id: str = "djp_rss_v2",
) -> StructuralPattern:
    return StructuralPattern(
        pattern_id=pattern_id,
        source="djp.go.id",
        procedure=procedure,
        precondition=precondition,
        success_criterion=success_criterion,
        confidence=confidence,
        domain=domain,
    )


@pytest.mark.asyncio
async def test_publish_high_confidence_pattern_broadcasts() -> None:
    fake_redis = MagicMock()
    fake_redis.xadd = AsyncMock(return_value=b"1-0")
    bridge = IntelScraperHGTBridge.from_redis(fake_redis,
                                              cell_name="intel-scraper-cell")

    ok = await bridge.publish(_make_pattern(confidence=0.85))
    assert ok is True
    fake_redis.xadd.assert_awaited_once()
    args, kwargs = fake_redis.xadd.await_args
    assert args[0] == "cell:skills"
    fields = args[1]
    assert fields["skill_id"] == "intel.scraper.pattern.djp_rss_v2"
    assert fields["cell_origin"] == "intel-scraper-cell"
    assert fields["confidence"] == "0.85"
    assert fields["scope"] == "Project"
    assert fields["domain"] == "news"


@pytest.mark.asyncio
async def test_publish_below_threshold_filtered_by_publisher() -> None:
    fake_redis = MagicMock()
    fake_redis.xadd = AsyncMock()
    bridge = IntelScraperHGTBridge.from_redis(fake_redis,
                                              cell_name="intel-scraper-cell")

    ok = await bridge.publish(_make_pattern(confidence=0.5))
    assert ok is False
    fake_redis.xadd.assert_not_called()


@pytest.mark.asyncio
async def test_publish_exact_one_confidence_filtered_locally() -> None:
    """Cell-level rule: confidence == 1.0 is almost always a fixture/test
    sentinel, NOT an empirical confidence. Filter before HGTPublisher."""
    fake_redis = MagicMock()
    fake_redis.xadd = AsyncMock()
    bridge = IntelScraperHGTBridge.from_redis(fake_redis,
                                              cell_name="intel-scraper-cell")

    ok = await bridge.publish(_make_pattern(confidence=1.0))
    assert ok is False
    fake_redis.xadd.assert_not_called()


@pytest.mark.asyncio
async def test_publish_pii_marker_blocks_broadcast() -> None:
    """Defense-in-depth: a procedure containing PII markers (email, +62,
    NPWP, passport) is filtered before HGT — content stays in local
    genome, never on the cell:skills stream."""
    fake_redis = MagicMock()
    fake_redis.xadd = AsyncMock()
    bridge = IntelScraperHGTBridge.from_redis(fake_redis,
                                              cell_name="intel-scraper-cell")

    pattern_with_email = _make_pattern(
        procedure="ping admin@djp.go.id when feed breaks",
    )
    ok = await bridge.publish(pattern_with_email)
    assert ok is False
    fake_redis.xadd.assert_not_called()

    pattern_with_phone = _make_pattern(
        precondition="contact +62 812-3456 if scrape blocked",
    )
    ok2 = await bridge.publish(pattern_with_phone)
    assert ok2 is False

    pattern_with_npwp = _make_pattern(
        success_criterion="payload contains npwp: 12.345.678.9-012.000",
    )
    ok3 = await bridge.publish(pattern_with_npwp)
    assert ok3 is False


@pytest.mark.asyncio
async def test_publish_redis_none_returns_false_silently() -> None:
    """Redis unavailable: publish returns False, no exception."""
    bridge = IntelScraperHGTBridge.from_redis(None,
                                              cell_name="intel-scraper-cell")
    ok = await bridge.publish(_make_pattern(confidence=0.9))
    assert ok is False


@pytest.mark.asyncio
async def test_publish_redis_xadd_failure_returns_false() -> None:
    """Redis xadd raising: HGTPublisher catches; bridge surfaces False."""
    fake_redis = MagicMock()
    fake_redis.xadd = AsyncMock(side_effect=ConnectionError("redis down"))
    bridge = IntelScraperHGTBridge.from_redis(fake_redis,
                                              cell_name="intel-scraper-cell")
    ok = await bridge.publish(_make_pattern(confidence=0.9))
    assert ok is False


@pytest.mark.asyncio
async def test_publish_unknown_domain_normalized_to_generic() -> None:
    """Unknown domain falls through validate_domain → 'generic'."""
    fake_redis = MagicMock()
    fake_redis.xadd = AsyncMock(return_value=b"1-0")
    bridge = IntelScraperHGTBridge.from_redis(fake_redis,
                                              cell_name="intel-scraper-cell")

    ok = await bridge.publish(_make_pattern(domain="some_brand_new_domain"))
    assert ok is True
    args, _ = fake_redis.xadd.await_args
    assert args[1]["domain"] == "generic"


def test_to_skill_dict_shape() -> None:
    pattern = _make_pattern(confidence=0.8)
    skill = pattern.to_skill_dict(cell_origin="intel-scraper-cell")
    assert skill["id"] == "intel.scraper.pattern.djp_rss_v2"
    assert skill["scope"] == "Project"
    assert skill["type"] == "skill"
    assert skill["confidence"] == 0.8
    assert skill["domain"] == "news"
    assert skill["cell_origin"] == "intel-scraper-cell"
