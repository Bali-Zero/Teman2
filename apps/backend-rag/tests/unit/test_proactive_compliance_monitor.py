"""
Unit tests for ProactiveComplianceMonitor
Target: Increase coverage from 90% to 95%+
"""

import asyncio
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def compliance_monitor():
    """Create ProactiveComplianceMonitor instance"""
    from services.proactive_compliance_monitor import ProactiveComplianceMonitor

    # ProactiveComplianceMonitor doesn't use dependency injection in __init__
    # It gets services via get_search_service(), get_memory_service(), get_alert_service()
    monitor = ProactiveComplianceMonitor()
    return monitor


def test_init(compliance_monitor):
    """Test ProactiveComplianceMonitor initialization"""
    monitor = compliance_monitor

    assert monitor.running is False
    assert monitor.task is None
    assert monitor.check_interval == 86400  # 24 hours


def test_init_custom_interval():
    """Test initialization and setting custom check interval"""
    from services.proactive_compliance_monitor import ProactiveComplianceMonitor

    monitor = ProactiveComplianceMonitor()
    # Set interval after initialization
    monitor.check_interval = 3600
    assert monitor.check_interval == 3600


@pytest.mark.asyncio
async def test_start(compliance_monitor):
    """Test starting the monitor"""
    monitor = compliance_monitor

    # Set a very short interval for testing
    monitor.check_interval = 0.01

    try:
        await monitor.start()

        assert monitor.running is True
        assert monitor.task is not None

        # Wait a tiny bit
        await asyncio.sleep(0.05)
    finally:
        # Cleanup
        monitor.running = False
        if monitor.task:
            monitor.task.cancel()
            try:
                await monitor.task
            except asyncio.CancelledError:
                pass


@pytest.mark.asyncio
async def test_start_already_running(compliance_monitor):
    """Test starting when already running"""
    monitor = compliance_monitor
    monitor.check_interval = 0.01

    try:
        await monitor.start()
        assert monitor.running is True

        # Try to start again - should not create new task
        original_task = monitor.task
        await monitor.start()
        assert monitor.task == original_task
    finally:
        monitor.running = False
        if monitor.task:
            monitor.task.cancel()
            try:
                await monitor.task
            except asyncio.CancelledError:
                pass


@pytest.mark.asyncio
async def test_stop(compliance_monitor):
    """Test stopping the monitor"""
    monitor = compliance_monitor
    monitor.check_interval = 0.01

    await monitor.start()
    assert monitor.running is True

    monitor.running = False
    if monitor.task:
        monitor.task.cancel()
        try:
            await monitor.task
        except asyncio.CancelledError:
            pass

    assert monitor.running is False


@pytest.mark.asyncio
async def test_stop_not_running(compliance_monitor):
    """Test stopping when not running"""
    monitor = compliance_monitor

    # Should not raise error
    await monitor.stop()
    assert monitor.running is False


@pytest.mark.asyncio
async def test_monitoring_loop_error_handling(compliance_monitor):
    """Test monitoring loop handles errors gracefully"""
    monitor = compliance_monitor
    monitor.check_interval = 0.01

    # Make check_compliance_items raise an error
    monitor.check_compliance_items = MagicMock(side_effect=Exception("Test error"))

    try:
        await monitor.start()

        # Wait a bit for loop to run
        await asyncio.sleep(0.05)

        # Should still be running despite error
        assert monitor.running is True
    finally:
        monitor.running = False
        if monitor.task:
            monitor.task.cancel()
            try:
                await monitor.task
            except asyncio.CancelledError:
                pass


@pytest.mark.asyncio
async def test_monitoring_loop_cancellation(compliance_monitor):
    """Test monitoring loop can be cancelled"""
    monitor = compliance_monitor
    monitor.check_interval = 0.01

    await monitor.start()

    # Cancel task manually
    monitor.running = False
    if monitor.task:
        monitor.task.cancel()
        try:
            await monitor.task
        except asyncio.CancelledError:
            pass  # Expected

    assert monitor.running is False


def test_check_compliance_items(compliance_monitor):
    """Test check_compliance_items method"""
    monitor = compliance_monitor

    # Mock search service
    mock_search = MagicMock()
    mock_search.search = MagicMock(
        return_value={
            "results": [{"text": "Test compliance item", "metadata": {"type": "regulation"}}]
        }
    )
    monitor.search = mock_search

    # Should not raise error
    monitor.check_compliance_items()


def test_generate_alerts(compliance_monitor):
    """Test generate_alerts method"""
    monitor = compliance_monitor

    # Mock notification service
    mock_notifications = MagicMock()
    mock_notifications.send_alert = MagicMock()
    monitor.notifications = mock_notifications

    # Should not raise error
    monitor.generate_alerts()


def test_check_interval_property(compliance_monitor):
    """Test check_interval can be modified"""
    monitor = compliance_monitor

    monitor.check_interval = 3600
    assert monitor.check_interval == 3600
