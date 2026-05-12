"""Phase 3 TICKET A.1 — CrmHGTBridge async tests.

Replaces the sync-stub tests previously in :mod:`test_stubs` (deleted per
the 4-panel review CORR-7).
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

_PACKAGE_PATH = Path(__file__).resolve().parents[1]
if str(_PACKAGE_PATH) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_PATH))

from cell_core.hgt.publisher import HGTPublisher  # noqa: E402
from crm_cell.hgt_publisher import CrmHGTBridge, StructuralPattern  # noqa: E402


def _make_pattern(
    *,
    pattern_id: str = "brevo_template_T123_bounce_rate",
    procedure: str = (
        "Brevo template T123 bounces above 80 percent for segment X over last 30 days"
    ),
    precondition: str = "segment X has at least 1000 active subscribers",
    success_criterion: str = "bounce rate stays above 80 percent in next 7-day window",
    confidence: float = 0.85,
    domain: str = "crm",
) -> StructuralPattern:
    return StructuralPattern(
        pattern_id=pattern_id,
        procedure=procedure,
        precondition=precondition,
        success_criterion=success_criterion,
        confidence=confidence,
        domain=domain,
    )


@pytest.fixture
def mock_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.xadd = AsyncMock(return_value=b"1-0")
    return redis


@pytest.fixture
def bridge(mock_redis: AsyncMock) -> CrmHGTBridge:
    return CrmHGTBridge.from_redis(redis_client=mock_redis)


@pytest.mark.asyncio
async def test_publish_below_confidence_floor_returns_false(
    bridge: CrmHGTBridge,
) -> None:
    """Confidence < 0.7 filtered locally before reaching HGTPublisher."""
    assert await bridge.publish(_make_pattern(confidence=0.5)) is False


@pytest.mark.asyncio
async def test_publish_confidence_exactly_1_returns_false(
    bridge: CrmHGTBridge,
) -> None:
    """Fixture pollution guard — confidence=1.0 is almost always a test value."""
    assert await bridge.publish(_make_pattern(confidence=1.0)) is False


@pytest.mark.asyncio
async def test_publish_pii_marker_in_procedure_blocked(
    bridge: CrmHGTBridge,
) -> None:
    """PII detection on ``procedure`` string (email substring)."""
    pattern = _make_pattern(procedure="user contact email leaked in template")
    assert await bridge.publish(pattern) is False


@pytest.mark.asyncio
async def test_publish_pii_marker_in_precondition_blocked(
    bridge: CrmHGTBridge,
) -> None:
    """PII detection on ``precondition`` (NPWP)."""
    pattern = _make_pattern(precondition="client npwp: 12.345.678.9-012.000")
    assert await bridge.publish(pattern) is False


@pytest.mark.asyncio
async def test_publish_calls_xadd_with_canonical_schema(
    bridge: CrmHGTBridge, mock_redis: AsyncMock
) -> None:
    """Verify the 9-field canonical skill dict reaches ``xadd``."""
    pattern = _make_pattern()
    result = await bridge.publish(pattern)
    assert result is True
    mock_redis.xadd.assert_called_once()
    call_args = mock_redis.xadd.call_args
    stream, fields = call_args[0]
    assert stream == "cell:skills"
    expected_keys = {
        "skill_id",
        "cell_origin",
        "procedure",
        "precondition",
        "success_criterion",
        "confidence",
        "type",
        "scope",
        "domain",
    }
    assert set(fields.keys()) == expected_keys, "xadd received wrong keys"
    assert fields["skill_id"] == "crm.pattern.brevo_template_T123_bounce_rate"
    assert fields["cell_origin"] == "crm-cell"
    assert fields["domain"] == "crm"
    assert fields["scope"] == "Project"
    assert fields["type"] == "skill"
    assert fields["confidence"] == "0.85"


@pytest.mark.asyncio
async def test_publish_skill_id_namespace(
    bridge: CrmHGTBridge, mock_redis: AsyncMock
) -> None:
    """``skill_id`` MUST be prefixed ``crm.pattern.<id>``."""
    await bridge.publish(_make_pattern(pattern_id="anything_here"))
    _stream, fields = mock_redis.xadd.call_args[0]
    assert fields["skill_id"].startswith("crm.pattern.")


@pytest.mark.asyncio
async def test_publish_redis_none_returns_false() -> None:
    """``from_redis(None)`` → HGTPublisher returns False on publish (no xadd)."""
    bridge = CrmHGTBridge.from_redis(redis_client=None)
    assert await bridge.publish(_make_pattern()) is False


@pytest.mark.asyncio
async def test_bridge_cell_origin_via_public_property(mock_redis: AsyncMock) -> None:
    """TICKET A.0 contract: bridge reads ``publisher.cell_name`` (public)."""
    bridge = CrmHGTBridge.from_redis(
        redis_client=mock_redis, cell_name="custom-name"
    )
    await bridge.publish(_make_pattern())
    _stream, fields = mock_redis.xadd.call_args[0]
    assert fields["cell_origin"] == "custom-name"


def test_confidence_floor_reads_from_hgt_publisher() -> None:
    """Phase 3 CORR-8: bridge uses ``HGTPublisher.CONFIDENCE_THRESHOLD`` SSOT."""
    assert HGTPublisher.CONFIDENCE_THRESHOLD == 0.7
