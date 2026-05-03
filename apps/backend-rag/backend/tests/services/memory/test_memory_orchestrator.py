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


# ═══════════════════════════════════════════════════════════════
# Bounded lock/semaphore LRU (S09)
# ═══════════════════════════════════════════════════════════════


class TestBoundedLockLRU:
    """Regression guard: per-user locks must not grow unbounded."""

    def test_write_lock_reuses_entry_for_same_user(self) -> None:
        orch = _make_orchestrator()
        first = orch._get_write_lock("alice@x.com")
        second = orch._get_write_lock("alice@x.com")
        assert first is second

    def test_write_lock_evicts_oldest_over_cap(self) -> None:
        orch = _make_orchestrator()
        orch._max_lock_entries = 3
        for i in range(5):
            orch._get_write_lock(f"user{i}@x.com")
        assert len(orch._write_locks) == 3
        assert "user0@x.com" not in orch._write_locks
        assert "user1@x.com" not in orch._write_locks
        assert "user4@x.com" in orch._write_locks

    def test_write_lock_lru_reorder(self) -> None:
        orch = _make_orchestrator()
        orch._max_lock_entries = 3
        for name in ("a", "b", "c"):
            orch._get_write_lock(name)
        # Touch "a" → it should survive the next insert
        orch._get_write_lock("a")
        orch._get_write_lock("d")
        assert set(orch._write_locks.keys()) == {"a", "c", "d"}

    def test_write_lock_skips_evicting_held_lock(self) -> None:
        """A locked entry must not be evicted — would strand the holder."""
        import asyncio

        async def _run() -> None:
            orch = _make_orchestrator()
            orch._max_lock_entries = 2
            held = orch._get_write_lock("holder@x.com")
            await held.acquire()
            try:
                orch._get_write_lock("a@x.com")
                orch._get_write_lock("b@x.com")  # would evict "holder" (oldest) but it's locked
                assert "holder@x.com" in orch._write_locks
            finally:
                held.release()

        asyncio.run(_run())

    def test_read_semaphore_reuses_entry(self) -> None:
        orch = _make_orchestrator()
        first = orch._get_read_semaphore("alice@x.com")
        second = orch._get_read_semaphore("alice@x.com")
        assert first is second

    def test_read_semaphore_evicts_over_cap(self) -> None:
        orch = _make_orchestrator()
        orch._max_lock_entries = 3
        for i in range(5):
            orch._get_read_semaphore(f"user{i}@x.com")
        assert len(orch._read_semaphores) == 3
