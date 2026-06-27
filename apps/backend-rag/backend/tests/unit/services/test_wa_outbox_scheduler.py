"""Tests for the WA Meta Inbox outbox scheduler loop (main_api).

Covers the panel-2026-06-04 fixes:
  - cadence: sleep ~0.1s after 'sent' (drain fast), full interval after 'idle'.
  - resilience: a raised exception in a tick is logged and the loop continues.
  - cancellation: the loop exits cleanly on CancelledError (shutdown path).
  - bot generator (Option B): _make_wa_bot_generate returns a flag-gated
    closure that raises (RuntimeError) when WA_INBOX_BOT_AUTOREPLY is off —
    so the worker marks the row failed/retry, never a wrong send (default).

The loop is driven against a fake app whose state.db_pool is a sentinel, with
process_outbox_once monkeypatched to a scripted sequence of statuses. We cap
iterations by cancelling the task after the scripted statuses are consumed.
"""

from __future__ import annotations

import asyncio
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from backend.app import main_api


def test_wa_outbox_scheduler_enabled_defaults_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WA_OUTBOX_SCHEDULER_ENABLED", raising=False)

    assert main_api._wa_outbox_scheduler_enabled() is True


@pytest.mark.parametrize("value", ["0", "false", "False", " no ", "OFF"])
def test_wa_outbox_scheduler_enabled_false_values(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("WA_OUTBOX_SCHEDULER_ENABLED", value)

    assert main_api._wa_outbox_scheduler_enabled() is False


@pytest.mark.parametrize("value", ["1", "true", "yes", "enabled", ""])
def test_wa_outbox_scheduler_enabled_true_values(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("WA_OUTBOX_SCHEDULER_ENABLED", value)

    assert main_api._wa_outbox_scheduler_enabled() is True


@pytest.mark.asyncio
async def test_lifespan_light_disables_only_wa_outbox_scheduler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakePool:
        async def close(self) -> None:
            pass

    async def fake_initialize_services_light(app: Any) -> None:
        app.state.db_pool = FakePool()

    async def fake_init_scheduler(pool: Any) -> str:
        return "notification-scheduler"

    async def fake_close() -> None:
        pass

    def fail_run_wa_outbox_scheduler(app: Any) -> None:
        raise AssertionError("WA outbox scheduler should not start")

    initializer_mod = ModuleType("backend.app.setup.service_initializer")
    scheduler_mod = ModuleType("backend.app.modules.notifications.scheduler")
    rag_proxy_mod = ModuleType("backend.app.rag_proxy")
    wa_inbox_bot_mod = ModuleType("backend.services.integrations.wa_inbox_bot")
    setattr(initializer_mod, "initialize_services_light", fake_initialize_services_light)
    setattr(scheduler_mod, "init_scheduler", fake_init_scheduler)
    setattr(rag_proxy_mod, "close_proxy_client", fake_close)
    setattr(wa_inbox_bot_mod, "close_rag_client", fake_close)

    monkeypatch.delenv("DISABLE_BACKGROUND_WORKERS", raising=False)
    monkeypatch.setenv("WA_OUTBOX_SCHEDULER_ENABLED", "0")
    monkeypatch.setitem(
        sys.modules,
        "backend.app.setup.service_initializer",
        initializer_mod,
    )
    monkeypatch.setitem(
        sys.modules,
        "backend.app.modules.notifications.scheduler",
        scheduler_mod,
    )
    monkeypatch.setitem(sys.modules, "backend.app.rag_proxy", rag_proxy_mod)
    monkeypatch.setitem(
        sys.modules,
        "backend.services.integrations.wa_inbox_bot",
        wa_inbox_bot_mod,
    )
    monkeypatch.setattr(
        main_api,
        "_run_wa_outbox_scheduler",
        fail_run_wa_outbox_scheduler,
    )

    app = SimpleNamespace(state=SimpleNamespace())

    async with main_api.lifespan_light(app):
        await app.state._init_task
        assert app.state.notification_scheduler == "notification-scheduler"
        assert app.state._wa_outbox_scheduler_task is None


@pytest.mark.asyncio
async def test_bot_generator_flag_off_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    # Default (flag off) → the closure raises so the worker never sends a wrong
    # reply. Option B is opt-in via WA_INBOX_BOT_AUTOREPLY.
    monkeypatch.delenv("WA_INBOX_BOT_AUTOREPLY", raising=False)
    app = SimpleNamespace(state=SimpleNamespace(db_pool=object()))
    bot_fn = main_api._make_wa_bot_generate(app)
    thread = {"thread_id": 1, "counterpart_phone": "62811"}
    with pytest.raises(RuntimeError, match="disabled"):
        await bot_fn(thread)


@pytest.mark.asyncio
async def test_scheduler_cadence_sent_then_idle(monkeypatch: pytest.MonkeyPatch) -> None:
    statuses = ["sent", "sent", "idle"]
    calls: list[Any] = []
    sleeps: list[float] = []

    async def fake_process(pool, wa, botfn) -> str:
        calls.append((pool, wa, botfn))
        if statuses:
            return statuses.pop(0)
        raise asyncio.CancelledError  # stop the loop deterministically

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(main_api, "process_outbox_once", fake_process, raising=False)
    # patch the symbol the loop imports locally
    import backend.services.integrations.wa_outbox_worker as worker_mod

    monkeypatch.setattr(worker_mod, "process_outbox_once", fake_process)
    monkeypatch.setattr(main_api.asyncio, "sleep", fake_sleep)
    monkeypatch.setenv("WA_OUTBOX_POLL_SECONDS", "3")

    app = SimpleNamespace(state=SimpleNamespace(db_pool=object()))

    with pytest.raises(asyncio.CancelledError):
        await main_api._run_wa_outbox_scheduler(app)

    # 3 productive ticks happened (sent, sent, idle) before the cancel tick
    assert len(calls) == 4
    # cadence: 0.1 after each 'sent', full interval (3.0) after 'idle'
    assert sleeps[0] == pytest.approx(0.1)
    assert sleeps[1] == pytest.approx(0.1)
    assert sleeps[2] == pytest.approx(3.0)
    # the bot generator passed through is the Option-B closure (callable,
    # built once and reused for every tick of this scheduler run)
    assert callable(calls[0][2])
    assert calls[0][2] is calls[1][2]


@pytest.mark.asyncio
async def test_scheduler_survives_tick_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    seq = ["boom", "idle"]
    ticks = 0
    sleeps: list[float] = []

    async def fake_process(pool, wa, botfn) -> str:
        nonlocal ticks
        ticks += 1
        if not seq:
            raise asyncio.CancelledError
        item = seq.pop(0)
        if item == "boom":
            raise RuntimeError("transient tick failure")
        return item

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    import backend.services.integrations.wa_outbox_worker as worker_mod

    monkeypatch.setattr(worker_mod, "process_outbox_once", fake_process)
    monkeypatch.setattr(main_api.asyncio, "sleep", fake_sleep)

    app = SimpleNamespace(state=SimpleNamespace(db_pool=object()))

    with pytest.raises(asyncio.CancelledError):
        await main_api._run_wa_outbox_scheduler(app)

    # tick 1 raised RuntimeError (logged, backed off), tick 2 idle, tick 3 cancel
    assert ticks == 3
    # after the exception the loop backed off by the full interval (default 3.0)
    assert sleeps[0] == pytest.approx(3.0)


@pytest.mark.asyncio
async def test_scheduler_cancels_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_process(pool, wa, botfn) -> str:
        return "idle"

    _real_sleep = asyncio.sleep  # capture BEFORE patching to avoid recursion

    async def fast_sleep(seconds: float) -> None:
        await _real_sleep(0)  # yield so cancellation can be delivered

    import backend.services.integrations.wa_outbox_worker as worker_mod

    monkeypatch.setattr(worker_mod, "process_outbox_once", fake_process)
    monkeypatch.setattr(main_api.asyncio, "sleep", fast_sleep)

    app = SimpleNamespace(state=SimpleNamespace(db_pool=object()))
    task = asyncio.create_task(main_api._run_wa_outbox_scheduler(app))
    await asyncio.sleep(0)  # let it run a few ticks
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.cancelled()
