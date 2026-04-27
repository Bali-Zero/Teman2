"""Unit tests for compliance_handlers.py EventBus handlers.

All tests are pure unit tests — no DB, no Redis, no network.
`invalidate_cache` is patched at its home module so deferred imports inside
each handler resolve to the mock.
"""
from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, call, patch

import pytest

from backend.services.events.handlers.compliance_handlers import (
    HANDLERS,
    on_compliance_alert_created,
    on_compliance_alert_outcome,
    on_intel_validation_complete,
    on_lkpm_readypack_generated,
)

pytestmark = pytest.mark.unit

_CACHE_PATCH = "backend.core.cache.invalidate_cache"


# ---------------------------------------------------------------------------
# on_compliance_alert_created
# ---------------------------------------------------------------------------


class TestOnComplianceAlertCreated:
    async def test_happy_path_calls_cache_twice(self) -> None:
        """Valid client_id triggers two invalidate_cache calls with correct keys."""
        with patch(_CACHE_PATCH, new=AsyncMock(return_value=3)) as mock_inv:
            await on_compliance_alert_created({"client_id": 42})

        assert mock_inv.call_count == 2
        assert mock_inv.call_args_list[0] == call("zantara:compliance_alerts:42:*")
        assert mock_inv.call_args_list[1] == call("zantara:compliance_metrics:*")

    async def test_missing_client_id_key_returns_early(self) -> None:
        """Empty payload — no client_id — must skip all cache calls."""
        with patch(_CACHE_PATCH, new=AsyncMock(return_value=0)) as mock_inv:
            result = await on_compliance_alert_created({})

        assert result is None
        assert mock_inv.call_count == 0

    async def test_explicit_none_client_id_returns_early(self) -> None:
        """Explicit client_id=None must skip all cache calls."""
        with patch(_CACHE_PATCH, new=AsyncMock(return_value=0)) as mock_inv:
            await on_compliance_alert_created({"client_id": None})

        assert mock_inv.call_count == 0

    async def test_cache_exception_is_swallowed(self) -> None:
        """RuntimeError from invalidate_cache must not propagate."""
        with patch(_CACHE_PATCH, new=AsyncMock(side_effect=RuntimeError("redis down"))):
            # Should not raise
            await on_compliance_alert_created({"client_id": 7})

    async def test_cache_key_uses_client_id_verbatim_int(self) -> None:
        """Integer client_id is interpolated as-is into the cache key."""
        with patch(_CACHE_PATCH, new=AsyncMock(return_value=1)) as mock_inv:
            await on_compliance_alert_created({"client_id": 99})

        assert mock_inv.call_args_list[0] == call("zantara:compliance_alerts:99:*")

    async def test_cache_key_uses_client_id_verbatim_str(self) -> None:
        """String client_id is interpolated as-is into the cache key."""
        with patch(_CACHE_PATCH, new=AsyncMock(return_value=1)) as mock_inv:
            await on_compliance_alert_created({"client_id": "abc"})

        assert mock_inv.call_args_list[0] == call("zantara:compliance_alerts:abc:*")


# ---------------------------------------------------------------------------
# on_compliance_alert_outcome
# ---------------------------------------------------------------------------


class TestOnComplianceAlertOutcome:
    async def test_happy_path_calls_metrics_cache(self) -> None:
        """Valid payload triggers exactly one invalidate_cache call on the metrics key."""
        with patch(_CACHE_PATCH, new=AsyncMock(return_value=1)) as mock_inv:
            await on_compliance_alert_outcome({"alert_id": 101, "outcome": "acted"})

        assert mock_inv.call_count == 1
        assert mock_inv.call_args_list[0] == call("zantara:compliance_metrics:*")

    async def test_happy_path_logs_alert_id_and_outcome(self, caplog: pytest.LogCaptureFixture) -> None:
        """INFO log must mention alert_id and outcome."""
        with patch(_CACHE_PATCH, new=AsyncMock(return_value=1)):
            with caplog.at_level(logging.INFO, logger="backend.services.events.handlers.compliance_handlers"):
                await on_compliance_alert_outcome({"alert_id": 101, "outcome": "acted"})

        assert any("101" in r.message and "acted" in r.message for r in caplog.records)

    async def test_empty_payload_still_calls_cache(self) -> None:
        """No early-return guard — cache is always invalidated even without fields."""
        with patch(_CACHE_PATCH, new=AsyncMock(return_value=0)) as mock_inv:
            await on_compliance_alert_outcome({})

        assert mock_inv.call_count == 1

    async def test_cache_exception_is_swallowed(self, caplog: pytest.LogCaptureFixture) -> None:
        """ConnectionError from invalidate_cache must not propagate."""
        with patch(_CACHE_PATCH, new=AsyncMock(side_effect=ConnectionError("redis timeout"))):
            with caplog.at_level(logging.DEBUG, logger="backend.services.events.handlers.compliance_handlers"):
                await on_compliance_alert_outcome({"alert_id": 5, "outcome": "dismissed"})

        assert any("compliance outcome cache invalidation skipped" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# on_intel_validation_complete
# ---------------------------------------------------------------------------


class TestOnIntelValidationComplete:
    async def test_happy_path_calls_staging_cache_key(self) -> None:
        """staging_id present → invalidate with scoped key."""
        with patch(_CACHE_PATCH, new=AsyncMock(return_value=2)) as mock_inv:
            await on_intel_validation_complete({"staging_id": "stg-abc-123"})

        assert mock_inv.call_count == 1
        assert mock_inv.call_args_list[0] == call("zantara:intel_validation:stg-abc-123:*")

    async def test_missing_staging_id_returns_early(self) -> None:
        """Empty payload must not call invalidate_cache."""
        with patch(_CACHE_PATCH, new=AsyncMock(return_value=0)) as mock_inv:
            await on_intel_validation_complete({})

        assert mock_inv.call_count == 0

    async def test_explicit_none_staging_id_returns_early(self) -> None:
        """staging_id=None must not call invalidate_cache."""
        with patch(_CACHE_PATCH, new=AsyncMock(return_value=0)) as mock_inv:
            await on_intel_validation_complete({"staging_id": None})

        assert mock_inv.call_count == 0

    async def test_cache_exception_is_swallowed(self, caplog: pytest.LogCaptureFixture) -> None:
        """OSError from invalidate_cache must not propagate."""
        with patch(_CACHE_PATCH, new=AsyncMock(side_effect=OSError("unreachable"))):
            with caplog.at_level(logging.DEBUG, logger="backend.services.events.handlers.compliance_handlers"):
                await on_intel_validation_complete({"staging_id": "s1"})

        assert any("intel validation cache invalidation skipped" in r.message for r in caplog.records)

    async def test_cache_key_uses_staging_id_verbatim_str(self) -> None:
        """String staging_id is interpolated verbatim."""
        with patch(_CACHE_PATCH, new=AsyncMock(return_value=1)) as mock_inv:
            await on_intel_validation_complete({"staging_id": "uuid-xyz"})

        assert mock_inv.call_args_list[0] == call("zantara:intel_validation:uuid-xyz:*")

    async def test_cache_key_uses_staging_id_verbatim_int(self) -> None:
        """Integer staging_id is interpolated verbatim."""
        with patch(_CACHE_PATCH, new=AsyncMock(return_value=1)) as mock_inv:
            await on_intel_validation_complete({"staging_id": 77})

        assert mock_inv.call_args_list[0] == call("zantara:intel_validation:77:*")


# ---------------------------------------------------------------------------
# on_lkpm_readypack_generated
# ---------------------------------------------------------------------------


class TestOnLkpmReadypackGenerated:
    async def test_logs_all_fields(self, caplog: pytest.LogCaptureFixture) -> None:
        """Handler logs client_id, period, and drive_url at INFO level."""
        payload = {"client_id": 55, "period": "2026-Q1", "drive_url": "https://drive.google.com/xyz"}
        with caplog.at_level(logging.INFO, logger="backend.services.events.handlers.compliance_handlers"):
            result = await on_lkpm_readypack_generated(payload)

        assert result is None
        assert any(
            "55" in r.message and "2026-Q1" in r.message and "https://drive.google.com/xyz" in r.message
            for r in caplog.records
        )

    async def test_empty_payload_does_not_raise(self, caplog: pytest.LogCaptureFixture) -> None:
        """All .get() return None — handler must not raise."""
        with caplog.at_level(logging.INFO, logger="backend.services.events.handlers.compliance_handlers"):
            await on_lkpm_readypack_generated({})

        assert any(r.levelno == logging.INFO for r in caplog.records)

    async def test_no_cache_calls(self) -> None:
        """This handler never calls invalidate_cache."""
        with patch(_CACHE_PATCH, new=AsyncMock(return_value=0)) as mock_inv:
            await on_lkpm_readypack_generated({"client_id": 1, "period": "2026-Q1", "drive_url": "https://x"})

        assert mock_inv.call_count == 0


# ---------------------------------------------------------------------------
# HANDLERS dict
# ---------------------------------------------------------------------------


class TestHandlersDict:
    def test_maps_all_expected_event_types(self) -> None:
        """All four event-type keys must be present with correct handler references."""
        assert set(HANDLERS.keys()) == {
            "compliance.alert",
            "compliance.alert_outcome",
            "intel.event",
            "lkpm.ingest_completed",
        }
        assert HANDLERS["compliance.alert"] is on_compliance_alert_created
        assert HANDLERS["compliance.alert_outcome"] is on_compliance_alert_outcome
        assert HANDLERS["intel.event"] is on_intel_validation_complete
        assert HANDLERS["lkpm.ingest_completed"] is on_lkpm_readypack_generated

    def test_all_handlers_are_coroutine_functions(self) -> None:
        """Every value in HANDLERS must be awaitable."""
        for key, handler in HANDLERS.items():
            assert asyncio.iscoroutinefunction(handler), f"HANDLERS[{key!r}] is not a coroutine function"

    def test_length_is_exactly_four(self) -> None:
        """Guard against silent additions or deletions — update test if HANDLERS grows."""
        assert len(HANDLERS) == 4
