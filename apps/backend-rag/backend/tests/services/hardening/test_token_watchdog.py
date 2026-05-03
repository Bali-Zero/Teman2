"""Tests for TokenWatchdog — probe aggregation + alert thresholds."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from backend.services.hardening.token_watchdog import (
    TokenExpiryReport,
    TokenWatchdog,
)
from backend.services.review.telegram_adapter import SendResult


def _now() -> datetime:
    return datetime(2026, 4, 18, 12, 0, tzinfo=timezone.utc)


def _report(days_ahead: float, provider: str = "ig", ok: bool = True) -> TokenExpiryReport:
    return TokenExpiryReport(
        provider=provider,
        ok=ok,
        expires_at=_now() + timedelta(days=days_ahead),
    )


@pytest.fixture
def telegram():
    tg = AsyncMock()
    tg.send_message = AsyncMock(return_value=SendResult(ok=True, message_id=1))
    return tg


@pytest.mark.asyncio
async def test_no_alert_when_token_has_plenty_of_time(telegram):
    async def probe():
        return _report(days_ahead=30)

    watchdog = TokenWatchdog(
        probes=[("ig", probe)],
        telegram=telegram,
        owner_chat_id="999",
    )
    result = await watchdog.sweep_once(now=_now())
    assert result.warnings_sent == 0
    assert len(result.reports) == 1
    assert result.reports[0].days_remaining == pytest.approx(30.0)
    telegram.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_warn_alert_5_days_out(telegram):
    async def probe():
        return _report(days_ahead=5)

    watchdog = TokenWatchdog(
        probes=[("ig", probe)],
        telegram=telegram,
        owner_chat_id="999",
    )
    result = await watchdog.sweep_once(now=_now())
    assert result.warnings_sent == 1
    text = telegram.send_message.call_args.kwargs["text"]
    assert "scade fra 5" in text
    # not critical (>2d) → ⏰ not 🚨
    assert "⏰" in text


@pytest.mark.asyncio
async def test_critical_alert_1_day_out(telegram):
    async def probe():
        return _report(days_ahead=1)

    watchdog = TokenWatchdog(
        probes=[("ig", probe)],
        telegram=telegram,
        owner_chat_id="999",
    )
    result = await watchdog.sweep_once(now=_now())
    assert result.warnings_sent == 1
    text = telegram.send_message.call_args.kwargs["text"]
    assert "🚨" in text


@pytest.mark.asyncio
async def test_probe_returning_no_expiry_does_not_alert(telegram):
    async def probe():
        return TokenExpiryReport(
            provider="ig",
            ok=True,
            expires_at=None,
            note="no_expiration_reported",
        )

    watchdog = TokenWatchdog(
        probes=[("ig", probe)],
        telegram=telegram,
        owner_chat_id="999",
    )
    result = await watchdog.sweep_once(now=_now())
    assert result.warnings_sent == 0
    telegram.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_probe_with_ok_false_does_not_alert(telegram):
    async def probe():
        return TokenExpiryReport(
            provider="ig", ok=False, error="debug_token down",
        )

    watchdog = TokenWatchdog(
        probes=[("ig", probe)],
        telegram=telegram,
        owner_chat_id="999",
    )
    result = await watchdog.sweep_once(now=_now())
    assert result.warnings_sent == 0


@pytest.mark.asyncio
async def test_probe_exception_collected_as_error_no_crash(telegram):
    async def probe():
        raise RuntimeError("http down")

    watchdog = TokenWatchdog(
        probes=[("ig", probe)],
        telegram=telegram,
        owner_chat_id="999",
    )
    result = await watchdog.sweep_once(now=_now())
    assert result.warnings_sent == 0
    assert any("probe ig" in e for e in result.errors)


@pytest.mark.asyncio
async def test_multiple_probes_one_alerts(telegram):
    async def good():
        return _report(days_ahead=30, provider="ig")

    async def bad():
        return _report(days_ahead=2, provider="linkedin")

    watchdog = TokenWatchdog(
        probes=[("ig", good), ("linkedin", bad)],
        telegram=telegram,
        owner_chat_id="999",
    )
    result = await watchdog.sweep_once(now=_now())
    assert result.warnings_sent == 1
    assert len(result.reports) == 2
