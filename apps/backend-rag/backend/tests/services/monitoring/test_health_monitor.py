from types import SimpleNamespace

import pytest

from backend.services.monitoring import health_monitor as health_module
from backend.services.monitoring.alert_service import AlertLevel
from backend.services.monitoring.health_monitor import HealthMonitor


class FakeAlertService:
    def __init__(self) -> None:
        self.alerts: list[dict[str, object]] = []
        self.resource_alerts: list[dict[str, object]] = []

    async def send_alert(self, **kwargs: object) -> dict[str, bool]:
        self.alerts.append(kwargs)
        return {"logging": True}

    async def send_resource_alert(self, **kwargs: object) -> None:
        self.resource_alerts.append(kwargs)


class FakePool:
    def get_size(self) -> int:
        return 5

    def get_min_size(self) -> int:
        return 1

    def get_max_size(self) -> int:
        return 10

    def get_idle_size(self) -> int:
        return 3


@pytest.mark.asyncio
async def test_start_and_stop_manage_monitoring_task() -> None:
    monitor = HealthMonitor(FakeAlertService(), check_interval=1)

    await monitor.start()

    assert monitor.running is True
    assert monitor.task is not None

    await monitor.stop()

    assert monitor.running is False
    assert monitor.task.cancelled()


def test_set_services_and_get_status_include_pool_snapshot() -> None:
    monitor = HealthMonitor(FakeAlertService(), check_interval=7)
    app_state = SimpleNamespace(db_pool=FakePool())

    monitor.set_services(
        memory_service="memory",
        intelligent_router="router",
        tool_executor="tools",
        app_state=app_state,
    )
    monitor.last_status = {"qdrant": True}
    monitor._last_cpu_percent = 12.3

    status = monitor.get_status()

    assert monitor.memory_service == "memory"
    assert status["running"] is False
    assert status["check_interval"] == 7
    assert status["last_status"] == {"qdrant": True}
    assert status["db_pool"] == {"size": 5, "min_size": 1, "max_size": 10, "idle": 3}


def test_record_first_request_sets_cold_start_once() -> None:
    monitor = HealthMonitor(FakeAlertService())

    monitor.record_first_request()
    first = monitor._cold_start_duration
    monitor.record_first_request()

    assert first is not None
    assert monitor._cold_start_duration == first


@pytest.mark.asyncio
async def test_send_downtime_and_recovery_alerts() -> None:
    alerts = FakeAlertService()
    monitor = HealthMonitor(alerts)

    await monitor._send_downtime_alert("qdrant")
    await monitor._send_recovery_alert("qdrant")

    assert alerts.alerts[0]["title"] == "Service Down: qdrant"
    assert alerts.alerts[0]["level"] == AlertLevel.CRITICAL
    assert alerts.alerts[1]["title"] == "Service Recovered: qdrant"
    assert alerts.alerts[1]["level"] == AlertLevel.INFO


@pytest.mark.asyncio
async def test_send_resource_alert_throttles_repeated_resource() -> None:
    alerts = FakeAlertService()
    monitor = HealthMonitor(alerts)

    await monitor._send_resource_alert_throttled("memory", 90.0, 85.0)
    await monitor._send_resource_alert_throttled("memory", 91.0, 85.0)

    assert len(alerts.resource_alerts) == 1
    assert alerts.resource_alerts[0]["resource"] == "memory"


def test_init_health_monitor_sets_global_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(health_module, "_health_monitor", None)
    alert_service = FakeAlertService()

    monitor = health_module.init_health_monitor(alert_service, check_interval=5)

    assert health_module.get_health_monitor() is monitor
    assert monitor.check_interval == 5
