"""
Tests for MemoryOrchestrator alerting (_alert_critical_failure, _alert_degraded_mode).

Tests mock AlertService to verify the correct alert level, title, and metadata
are sent without requiring actual Telegram connectivity.
"""

from unittest.mock import AsyncMock, patch

import pytest

from backend.services.memory.orchestrator import MemoryOrchestrator, MemoryServiceStatus


# ── Helpers ──────────────────────────────────────────────────────

def _make_orchestrator() -> MemoryOrchestrator:
    """Create a MemoryOrchestrator without connecting to any DB."""
    return MemoryOrchestrator(db_pool=None, database_url=None)


# ═══════════════════════════════════════════════════════════════
# _alert_critical_failure
# ═══════════════════════════════════════════════════════════════


class TestAlertCriticalFailure:
    @pytest.mark.asyncio
    async def test_sends_critical_alert(self) -> None:
        orch = _make_orchestrator()
        failures = [("memory_service", "Connection refused")]

        mock_alert = AsyncMock()
        mock_alert.send_alert = AsyncMock(return_value={"telegram": True})

        with patch(
            "backend.services.monitoring.alert_service.get_alert_service",
            return_value=mock_alert,
        ):
            await orch._alert_critical_failure(failures)

        mock_alert.send_alert.assert_called_once()
        call_kwargs = mock_alert.send_alert.call_args[1]
        assert call_kwargs["title"] == "Memory System CRITICAL Failure"
        assert "CRITICAL" in str(call_kwargs["level"])
        assert "memory_orchestrator" in str(call_kwargs["metadata"])
        assert "Connection refused" in call_kwargs["message"]

    @pytest.mark.asyncio
    async def test_handles_alert_failure_gracefully(self) -> None:
        orch = _make_orchestrator()

        with patch(
            "backend.services.monitoring.alert_service.get_alert_service",
            side_effect=Exception("Telegram unreachable"),
        ):
            # Should NOT raise
            await orch._alert_critical_failure([("test", "error")])

    @pytest.mark.asyncio
    async def test_multiple_failures_in_message(self) -> None:
        orch = _make_orchestrator()
        failures = [
            ("memory_service", "Pool timeout"),
            ("kg_repository", "Schema mismatch"),
        ]

        mock_alert = AsyncMock()
        mock_alert.send_alert = AsyncMock(return_value={"telegram": True})

        with patch(
            "backend.services.monitoring.alert_service.get_alert_service",
            return_value=mock_alert,
        ):
            await orch._alert_critical_failure(failures)

        msg = mock_alert.send_alert.call_args[1]["message"]
        assert "Pool timeout" in msg
        assert "Schema mismatch" in msg


# ═══════════════════════════════════════════════════════════════
# _alert_degraded_mode
# ═══════════════════════════════════════════════════════════════


class TestAlertDegradedMode:
    @pytest.mark.asyncio
    async def test_sends_warning_alert(self) -> None:
        orch = _make_orchestrator()
        failures = [("collective_memory", "Table missing")]

        mock_alert = AsyncMock()
        mock_alert.send_alert = AsyncMock(return_value={"telegram": True})

        with patch(
            "backend.services.monitoring.alert_service.get_alert_service",
            return_value=mock_alert,
        ):
            await orch._alert_degraded_mode(failures)

        mock_alert.send_alert.assert_called_once()
        call_kwargs = mock_alert.send_alert.call_args[1]
        assert call_kwargs["title"] == "Memory System DEGRADED"
        assert "WARNING" in str(call_kwargs["level"])
        assert "collective_memory" in call_kwargs["message"]

    @pytest.mark.asyncio
    async def test_lists_degraded_features(self) -> None:
        orch = _make_orchestrator()
        failures = [
            ("collective_memory", "err1"),
            ("episodic_memory", "err2"),
            ("kg_repository", "err3"),
        ]

        mock_alert = AsyncMock()
        mock_alert.send_alert = AsyncMock(return_value={"telegram": True})

        with patch(
            "backend.services.monitoring.alert_service.get_alert_service",
            return_value=mock_alert,
        ):
            await orch._alert_degraded_mode(failures)

        msg = mock_alert.send_alert.call_args[1]["message"]
        assert "collective_memory" in msg
        assert "episodic_memory" in msg
        assert "kg_repository" in msg

        metadata = mock_alert.send_alert.call_args[1]["metadata"]
        assert set(metadata["degraded_features"]) == {
            "collective_memory", "episodic_memory", "kg_repository",
        }

    @pytest.mark.asyncio
    async def test_handles_alert_failure_gracefully(self) -> None:
        orch = _make_orchestrator()

        with patch(
            "backend.services.monitoring.alert_service.get_alert_service",
            side_effect=Exception("Telegram down"),
        ):
            # Should NOT raise
            await orch._alert_degraded_mode([("test", "error")])


# ═══════════════════════════════════════════════════════════════
# MemoryOrchestrator basic properties
# ═══════════════════════════════════════════════════════════════


class TestMemoryOrchestratorProperties:
    def test_not_initialized_by_default(self) -> None:
        orch = _make_orchestrator()
        assert orch.is_initialized is False
        assert orch.db_pool is None

    def test_status_unavailable_by_default(self) -> None:
        orch = _make_orchestrator()
        assert orch._status == MemoryServiceStatus.UNAVAILABLE

    def test_ensure_initialized_raises(self) -> None:
        orch = _make_orchestrator()
        with pytest.raises(RuntimeError, match="not initialized"):
            orch._ensure_initialized()
