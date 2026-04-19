"""Integration tests for cost_advisor_cli entry points.

Uses mocked db pool + Telegram + Claude OAuth so no external services are
hit; exercises the real run_weekly_report / run_daily_cap_check paths.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.scripts.cost_advisor_cli import (
    DAILY_SPEND_ALERT_THRESHOLD_USD,
    run_daily_cap_check,
    run_weekly_report,
)


def _make_pool_with_fetchval(value):
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=value)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    pool = MagicMock()
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=acquire_cm)
    return pool, conn


@pytest.mark.asyncio
async def test_daily_cap_sends_telegram_when_exceeded():
    pool, _ = _make_pool_with_fetchval(DAILY_SPEND_ALERT_THRESHOLD_USD + Decimal("5"))
    with patch(
        "backend.scripts.cost_advisor_cli.send_telegram",
    ) as mock_tg:
        await run_daily_cap_check(pool)
    mock_tg.assert_called_once()
    msg = mock_tg.call_args.kwargs["text"]
    assert "ALERT" in msg
    assert "25" in msg or "$25" in msg  # Decimal("25")


@pytest.mark.asyncio
async def test_daily_cap_silent_when_under_threshold():
    pool, _ = _make_pool_with_fetchval(Decimal("1.00"))
    with patch("backend.scripts.cost_advisor_cli.send_telegram") as mock_tg:
        await run_daily_cap_check(pool)
    mock_tg.assert_not_called()


@pytest.mark.asyncio
async def test_weekly_report_sends_telegram_with_header():
    pool, _ = _make_pool_with_fetchval(Decimal("0"))
    with patch(
        "backend.scripts.cost_advisor_cli.send_telegram",
    ) as mock_tg, patch(
        "backend.scripts.cost_advisor_cli.CostAdvisor",
    ) as mock_cls:
        instance = mock_cls.return_value
        instance.analyze_last_window = AsyncMock(return_value=[])
        instance.detect_spikes = AsyncMock(return_value=set())
        instance.propose_substitutions = AsyncMock(return_value=[])
        instance.persist_recommendations = AsyncMock(return_value=0)

        await run_weekly_report(pool)

    mock_tg.assert_called_once()
    msg = mock_tg.call_args.kwargs["text"]
    assert "Weekly LLM Cost Report" in msg
    assert "Endpoints analysed" in msg
    assert "No substitutions proposed" in msg
