"""Phase 3 TICKET A.2 EXECUTION — crm_hgt_handlers async tests.

12 unit tests covering 2 handlers × 6 scenarios:
- happy path (event → window ZADD → threshold met → bridge.publish called)
- below threshold (no publish)
- missing required payload fields (early return)
- bridge None (graceful degradation)
- Redis window error (returns 0 count → no publish)
- canonical schema (verify pattern_id/domain/confidence after publish)

Plus 1 registration test asserting HANDLERS dict + register_crm_hgt_handlers
subscribes to expected event types.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import backend.services.events.handlers.crm_hgt_handlers as mod
from backend.services.events.handlers.crm_hgt_handlers import (
    HANDLERS,
    _ingest_event,
    on_lkpm_ingest_completed,
    on_practice_status_changed,
    register_crm_hgt_handlers,
)


@pytest.fixture(autouse=True)
def _reset_bridge_singleton():
    """Reset the module-level lazy bridge between tests."""
    mod._bridge = None
    yield
    mod._bridge = None


@pytest.fixture
def mock_bridge() -> AsyncMock:
    """Mock CrmHGTBridge with mock publisher + redis."""
    bridge = AsyncMock()
    bridge.publish = AsyncMock(return_value=True)
    # Bridge wraps publisher which wraps redis client
    redis_pipeline = AsyncMock()
    redis_pipeline.execute = AsyncMock(return_value=[None, None, 25, None])
    redis_pipeline.zadd = MagicMock()
    redis_pipeline.zremrangebyscore = MagicMock()
    redis_pipeline.zcard = MagicMock()
    redis_pipeline.expire = MagicMock()

    pipeline_cm = MagicMock()
    pipeline_cm.__aenter__ = AsyncMock(return_value=redis_pipeline)
    pipeline_cm.__aexit__ = AsyncMock(return_value=None)

    redis_client = MagicMock()
    redis_client.pipeline = MagicMock(return_value=pipeline_cm)

    bridge._publisher = MagicMock()
    bridge._publisher._redis = redis_client
    return bridge


# ---------------------------------------------------------------------------
# _ingest_event — sliding-window helper
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_event_returns_zcard_result() -> None:
    """Happy path: pipeline returns the ZCARD result (item index 2)."""
    redis = MagicMock()
    pipe = AsyncMock()
    pipe.execute = AsyncMock(return_value=[None, None, 42, None])
    pipe.zadd = MagicMock()
    pipe.zremrangebyscore = MagicMock()
    pipe.zcard = MagicMock()
    pipe.expire = MagicMock()

    pcm = MagicMock()
    pcm.__aenter__ = AsyncMock(return_value=pipe)
    pcm.__aexit__ = AsyncMock(return_value=None)
    redis.pipeline = MagicMock(return_value=pcm)

    count = await _ingest_event(
        redis, "test.window", "evt-1", 1000.0, 3600
    )
    assert count == 42


@pytest.mark.asyncio
async def test_ingest_event_returns_zero_on_redis_error() -> None:
    """Redis error → returns 0 (handler treats as below threshold)."""
    redis = MagicMock()
    redis.pipeline = MagicMock(side_effect=RuntimeError("redis down"))
    count = await _ingest_event(redis, "test", "evt", 1000.0, 3600)
    assert count == 0


# ---------------------------------------------------------------------------
# on_practice_status_changed — 6 scenarios
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_practice_happy_path_above_threshold_publishes(mock_bridge) -> None:
    """ZCARD returns 25 (≥20 threshold) → bridge.publish called with canonical pattern."""
    with patch.object(mod, "_get_bridge", return_value=mock_bridge):
        await on_practice_status_changed(
            {"practice_id": 42, "new_status": "on_process", "event_id": "evt-1"}
        )
    mock_bridge.publish.assert_called_once()
    pattern = mock_bridge.publish.call_args[0][0]
    assert pattern.pattern_id == "practice_transition_on_process"
    assert pattern.domain == "crm"
    assert pattern.confidence == 0.8


@pytest.mark.asyncio
async def test_practice_below_threshold_does_not_publish(mock_bridge) -> None:
    """ZCARD returns 5 (<20 threshold) → no publish."""
    mock_bridge._publisher._redis.pipeline.return_value.__aenter__.return_value.execute = AsyncMock(
        return_value=[None, None, 5, None]
    )
    with patch.object(mod, "_get_bridge", return_value=mock_bridge):
        await on_practice_status_changed(
            {"practice_id": 1, "new_status": "submitted", "event_id": "evt-2"}
        )
    mock_bridge.publish.assert_not_called()


@pytest.mark.asyncio
async def test_practice_missing_fields_early_return(mock_bridge) -> None:
    """Missing practice_id → early return, no Redis call, no publish."""
    with patch.object(mod, "_get_bridge", return_value=mock_bridge):
        await on_practice_status_changed({"new_status": "on_process"})
    mock_bridge._publisher._redis.pipeline.assert_not_called()
    mock_bridge.publish.assert_not_called()


@pytest.mark.asyncio
async def test_practice_bridge_none_graceful_degradation() -> None:
    """Bridge init failed (None) → early return, no exception."""
    with patch.object(mod, "_get_bridge", return_value=None):
        # Should NOT raise
        await on_practice_status_changed(
            {"practice_id": 1, "new_status": "on_process"}
        )


@pytest.mark.asyncio
async def test_practice_redis_window_error_no_publish(mock_bridge) -> None:
    """Redis pipeline raises → _ingest_event returns 0 → no publish."""
    mock_bridge._publisher._redis.pipeline = MagicMock(
        side_effect=RuntimeError("redis down")
    )
    with patch.object(mod, "_get_bridge", return_value=mock_bridge):
        await on_practice_status_changed(
            {"practice_id": 1, "new_status": "on_process"}
        )
    mock_bridge.publish.assert_not_called()


@pytest.mark.asyncio
async def test_practice_pattern_canonical_schema(mock_bridge) -> None:
    """Verify all 6 StructuralPattern fields populated correctly."""
    with patch.object(mod, "_get_bridge", return_value=mock_bridge):
        await on_practice_status_changed(
            {"practice_id": 99, "new_status": "completed"}
        )
    pattern = mock_bridge.publish.call_args[0][0]
    assert pattern.pattern_id == "practice_transition_completed"
    assert "completed" in pattern.procedure
    assert "7d rolling window" in pattern.procedure
    assert "practice pipeline" in pattern.precondition
    assert pattern.success_criterion.startswith("practice_transition_completed")
    assert pattern.confidence == 0.8
    assert pattern.domain == "crm"


# ---------------------------------------------------------------------------
# on_lkpm_ingest_completed — 5 scenarios (1 shared with practice via bridge_none)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lkpm_happy_path_above_threshold_publishes(mock_bridge) -> None:
    """ZCARD returns 25 (≥10 threshold) → bridge.publish called."""
    with patch.object(mod, "_get_bridge", return_value=mock_bridge):
        await on_lkpm_ingest_completed(
            {"pt_count": 5, "receipt_count": 12, "event_id": "lkpm-1"}
        )
    mock_bridge.publish.assert_called_once()
    pattern = mock_bridge.publish.call_args[0][0]
    assert pattern.pattern_id == "lkpm_ingestion_success_rate"
    assert pattern.domain == "crm"


@pytest.mark.asyncio
async def test_lkpm_below_threshold_does_not_publish(mock_bridge) -> None:
    """ZCARD returns 3 (<10 threshold) → no publish."""
    mock_bridge._publisher._redis.pipeline.return_value.__aenter__.return_value.execute = AsyncMock(
        return_value=[None, None, 3, None]
    )
    with patch.object(mod, "_get_bridge", return_value=mock_bridge):
        await on_lkpm_ingest_completed(
            {"pt_count": 5, "receipt_count": 12}
        )
    mock_bridge.publish.assert_not_called()


@pytest.mark.asyncio
async def test_lkpm_missing_structural_signal_early_return(mock_bridge) -> None:
    """Payload missing pt_count AND receipt_count → early return."""
    with patch.object(mod, "_get_bridge", return_value=mock_bridge):
        await on_lkpm_ingest_completed({"quarter": "Q1"})
    mock_bridge._publisher._redis.pipeline.assert_not_called()
    mock_bridge.publish.assert_not_called()


@pytest.mark.asyncio
async def test_lkpm_bridge_none_graceful_degradation() -> None:
    """Bridge None → early return, no exception."""
    with patch.object(mod, "_get_bridge", return_value=None):
        await on_lkpm_ingest_completed({"pt_count": 5, "receipt_count": 12})


@pytest.mark.asyncio
async def test_lkpm_pattern_canonical_schema(mock_bridge) -> None:
    """Verify LKPM pattern fields."""
    with patch.object(mod, "_get_bridge", return_value=mock_bridge):
        await on_lkpm_ingest_completed({"pt_count": 8, "receipt_count": 20})
    pattern = mock_bridge.publish.call_args[0][0]
    assert pattern.pattern_id == "lkpm_ingestion_success_rate"
    assert "LKPM bulk ingest" in pattern.procedure
    assert "90d rolling window" in pattern.procedure
    assert "PT segment" in pattern.precondition
    assert pattern.confidence == 0.8
    assert pattern.domain == "crm"


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_handlers_dict_contains_expected_event_types() -> None:
    """HANDLERS maps the 2 v1-scope event types per spec v2 CAV-3."""
    assert set(HANDLERS.keys()) == {
        "practice.status_changed",
        "lkpm.ingest_completed",
    }
    assert HANDLERS["practice.status_changed"] is on_practice_status_changed
    assert HANDLERS["lkpm.ingest_completed"] is on_lkpm_ingest_completed


def test_register_crm_hgt_handlers_subscribes_to_bus() -> None:
    """register_crm_hgt_handlers(bus) calls bus.subscribe for each HANDLER entry."""
    bus = MagicMock()
    register_crm_hgt_handlers(bus)
    assert bus.subscribe.call_count == len(HANDLERS)
    subscribed_events = {call.args[0] for call in bus.subscribe.call_args_list}
    assert subscribed_events == set(HANDLERS.keys())
