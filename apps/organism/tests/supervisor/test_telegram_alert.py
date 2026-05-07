"""Tests for telegram_alert.build_dispatch_alerter — best-effort Telegram side-effect."""
from __future__ import annotations

import pytest

from organism.schemas import ActionDecision
from organism.supervisor.telegram_alert import build_dispatch_alerter


class _FakeNotifyTelegram:
    """Test double matching the NotifyTelegram actuator surface."""

    name = "notify_telegram"

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def run(self, *, params, correlation_id, dry_run=False):
        self.calls.append({
            "params": dict(params),
            "correlation_id": correlation_id,
            "dry_run": dry_run,
        })
        return {"success": True}


def _decision(actuator="restart_agent"):
    return ActionDecision(
        actuator=actuator,
        params={"agent_ref": "core-guardian"},
        confidence=0.9,
        tier="L0_yaml",
        reasoning="test",
    )


@pytest.mark.asyncio
async def test_alerter_sends_message_on_success():
    notifier = _FakeNotifyTelegram()
    alerter = build_dispatch_alerter({"notify_telegram": notifier})
    await alerter(
        decision=_decision(),
        target="core-guardian",
        correlation_id="abc",
        result={"success": True, "label": "com.balizero.core-guardian"},
    )
    assert len(notifier.calls) == 1
    msg = notifier.calls[0]["params"]["message"]
    assert "restart_agent" in msg
    assert "core-guardian" in msg
    assert "✅" in msg or "ok" in msg.lower() or "success" in msg.lower()


@pytest.mark.asyncio
async def test_alerter_marks_failure_explicitly():
    notifier = _FakeNotifyTelegram()
    alerter = build_dispatch_alerter({"notify_telegram": notifier})
    await alerter(
        decision=_decision(),
        target="x",
        correlation_id="c",
        result={"success": False, "error": "kickstart returned 1"},
    )
    assert len(notifier.calls) == 1
    msg = notifier.calls[0]["params"]["message"]
    assert "fail" in msg.lower() or "❌" in msg or "error" in msg.lower()


@pytest.mark.asyncio
async def test_alerter_skips_self_alert_for_notify_telegram():
    """If the dispatched actuator IS notify_telegram, don't recurse."""
    notifier = _FakeNotifyTelegram()
    alerter = build_dispatch_alerter({"notify_telegram": notifier})
    await alerter(
        decision=_decision(actuator="notify_telegram"),
        target="x",
        correlation_id="c",
        result={"success": True},
    )
    assert notifier.calls == []


@pytest.mark.asyncio
async def test_alerter_no_op_when_notify_telegram_missing():
    """Registry without notify_telegram → silent no-op (best-effort)."""
    alerter = build_dispatch_alerter({})
    # Must not raise.
    await alerter(
        decision=_decision(),
        target="x",
        correlation_id="c",
        result={"success": True},
    )


@pytest.mark.asyncio
async def test_alerter_swallows_notifier_exceptions():
    """If NotifyTelegram raises, alerter must not propagate."""

    class _Boom:
        name = "notify_telegram"

        async def run(self, **_):
            raise RuntimeError("telegram api 500")

    alerter = build_dispatch_alerter({"notify_telegram": _Boom()})
    # Must not raise.
    await alerter(
        decision=_decision(),
        target="x",
        correlation_id="c",
        result={"success": True},
    )
