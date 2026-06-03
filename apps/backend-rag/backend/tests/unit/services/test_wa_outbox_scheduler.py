"""Tests for the WA Meta Inbox outbox scheduler loop (main_api).

Covers the panel-2026-06-04 fixes:
  - cadence: sleep ~0.1s after 'sent' (drain fast), full interval after 'idle'.
  - resilience: a raised exception in a tick is logged and the loop continues.
  - cancellation: the loop exits cleanly on CancelledError (shutdown path).
  - v1 sentinel bot generator raises NotImplementedError (human-send-only).

The loop is driven against a fake app whose state.db_pool is a sentinel, with
process_outbox_once monkeypatched to a scripted sequence of statuses. We cap
iterations by cancelling the task after the scripted statuses are consumed.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from backend.app import main_api


@pytest.mark.asyncio
async def test_v1_bot_generator_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        await main_api._wa_bot_generate_not_implemented(object())


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
    # the bot generator passed through is the v1 sentinel
    assert calls[0][2] is main_api._wa_bot_generate_not_implemented


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
