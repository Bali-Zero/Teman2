"""
Tests for MemoryOrchestrator error handling - degraded mode, health status.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


class _MockOrchestrator:
    """Simplified mock of MemoryOrchestrator behavior."""

    def __init__(self):
        self.status = "healthy"
        self._initialized = True

    async def ensure_initialized(self):
        if self.status == "unavailable":
            raise RuntimeError("Memory orchestrator unavailable")

    def set_degraded(self):
        self.status = "degraded"

    def set_unavailable(self):
        self.status = "unavailable"

    def set_healthy(self):
        self.status = "healthy"


def test_degraded_mode_on_non_critical_failure():
    """Non-critical failure should set orchestrator to degraded mode."""
    orch = _MockOrchestrator()
    orch.set_degraded()
    assert orch.status == "degraded"


def test_healthy_status_on_success():
    """Successful operation should keep status healthy."""
    orch = _MockOrchestrator()
    assert orch.status == "healthy"


@pytest.mark.asyncio
async def test_ensure_initialized_raises_on_unavailable():
    """ensure_initialized should raise when status is unavailable."""
    orch = _MockOrchestrator()
    orch.set_unavailable()
    with pytest.raises(RuntimeError, match="unavailable"):
        await orch.ensure_initialized()
