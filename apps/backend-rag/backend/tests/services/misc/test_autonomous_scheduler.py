from __future__ import annotations

import pytest

from backend.services.misc import autonomous_scheduler as module
from backend.services.misc.autonomous_scheduler import (
    AutonomousScheduler,
    get_autonomous_scheduler,
)


async def _noop_task() -> None:
    return None


def test_get_autonomous_scheduler_returns_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "_scheduler", None)

    first = get_autonomous_scheduler()
    second = get_autonomous_scheduler()

    assert isinstance(first, AutonomousScheduler)
    assert first is second


def test_register_task_status_and_enable_disable() -> None:
    scheduler = AutonomousScheduler()
    scheduler.register_task("health", _noop_task, interval_seconds=300, enabled=False)

    status = scheduler.get_status()

    assert status["running"] is False
    assert status["task_count"] == 1
    assert status["tasks"]["health"]["enabled"] is False
    assert status["tasks"]["health"]["interval_seconds"] == 300
    assert scheduler.enable_task("health") is True
    assert scheduler.tasks["health"].enabled is True
    assert scheduler.disable_task("health") is True
    assert scheduler.tasks["health"].enabled is False
    assert scheduler.enable_task("missing") is False
    assert scheduler.disable_task("missing") is False


@pytest.mark.asyncio
async def test_start_and_stop_manage_enabled_task_without_running_body() -> None:
    scheduler = AutonomousScheduler()
    scheduler.register_task("health", _noop_task, interval_seconds=300, enabled=True)

    await scheduler.start()
    assert scheduler.get_status()["running"] is True
    assert scheduler.tasks["health"]._task is not None
    assert scheduler.tasks["health"]._task.done() is False

    await scheduler.stop()
    assert scheduler.get_status()["running"] is False


@pytest.mark.asyncio
async def test_create_and_start_scheduler_uses_global_scheduler_and_starts_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeScheduler:
        def __init__(self) -> None:
            self.registered: list[dict] = []
            self.started = False

        def register_task(self, **kwargs) -> None:
            self.registered.append(kwargs)

        async def start(self) -> None:
            self.started = True

    fake_scheduler = FakeScheduler()
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ENABLE_KG_INCREMENTAL", "false")
    monkeypatch.setattr(module, "get_autonomous_scheduler", lambda: fake_scheduler)

    result = await module.create_and_start_scheduler(
        db_pool=None,
        ai_client=object(),
        conversation_trainer_enabled=False,
        conversation_cleanup_enabled=False,
    )

    assert result is fake_scheduler
    assert fake_scheduler.started is True
    assert all("name" in task and "task_func" in task for task in fake_scheduler.registered)
