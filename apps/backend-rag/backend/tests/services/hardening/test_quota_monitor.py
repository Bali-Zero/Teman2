"""Tests for QuotaMonitor — soft cap + daily spike detection."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.services.hardening.quota_monitor import (
    DEFAULT_SOFT_CAPS_USD,
    QuotaMonitor,
)
from backend.services.review.telegram_adapter import SendResult


@pytest.fixture
def repo_tg():
    repo = AsyncMock()
    tg = AsyncMock()
    tg.send_message = AsyncMock(return_value=SendResult(ok=True, message_id=1))
    return repo, tg


def _monitor(repo, tg) -> QuotaMonitor:
    return QuotaMonitor(repo=repo, telegram=tg, owner_chat_id="999")


async def _stub_fetches(
    repo,
    *,
    totals_30d: dict[str, float],
    today: dict[str, float],
    prior_7d_rows: list[dict],
):
    """Return totals_30d, then today_by_type, then per-type 7-day series."""
    _call_index = {"i": 0}  # noqa: F841 (preserved for debug/introspection)

    async def side_effect(query, *args):
        q = query.strip()
        if "GROUP BY cost_type;" in q and "make_interval(days => $1)" in q and "DATE(" not in q:
            # _cost_totals_by_type
            return [{"cost_type": k, "total": v} for k, v in totals_30d.items()]
        if "DATE(occurred_at" in q and "= $1" in q:
            return [{"cost_type": k, "total": v} for k, v in today.items()]
        if "GROUP BY cost_type, day" in q:
            return prior_7d_rows
        return []

    repo.fetch_safe = AsyncMock(side_effect=side_effect)


# ── No alerts ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_alert_when_under_cap_and_no_spike(repo_tg):
    repo, tg = repo_tg
    await _stub_fetches(
        repo,
        totals_30d={"imagen_fast": 2.0},
        today={"imagen_fast": 0.05},
        prior_7d_rows=[
            {"cost_type": "imagen_fast", "day": None, "total": 0.08},
            {"cost_type": "imagen_fast", "day": None, "total": 0.07},
        ],
    )
    monitor = _monitor(repo, tg)
    result = await monitor.sweep_once()
    assert result.alerts_sent == 0
    tg.send_message.assert_not_called()


# ── Soft-cap breach ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_alert_when_soft_cap_exceeded(repo_tg):
    repo, tg = repo_tg
    await _stub_fetches(
        repo,
        totals_30d={"imagen_fast": 15.0},  # cap default 10
        today={"imagen_fast": 0.10},
        prior_7d_rows=[
            {"cost_type": "imagen_fast", "day": None, "total": 0.5},
        ],
    )
    monitor = _monitor(repo, tg)
    result = await monitor.sweep_once()
    assert result.alerts_sent == 1
    text = tg.send_message.call_args.kwargs["text"]
    assert "soft cap" in text
    assert "15.00" in text


@pytest.mark.asyncio
async def test_zero_cap_costs_never_alert(repo_tg):
    """claude_cli soft_cap is 0 (flat-rate) — shouldn't trigger."""
    repo, tg = repo_tg
    await _stub_fetches(
        repo,
        totals_30d={"claude_cli": 999.0},  # absurd
        today={},
        prior_7d_rows=[],
    )
    monitor = _monitor(repo, tg)
    result = await monitor.sweep_once()
    assert result.alerts_sent == 0


# ── Daily spike ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_alert_on_daily_spike_above_3x_avg(repo_tg):
    repo, tg = repo_tg
    await _stub_fetches(
        repo,
        totals_30d={"imagen_fast": 3.0},
        today={"imagen_fast": 4.0},
        prior_7d_rows=[
            {"cost_type": "imagen_fast", "day": None, "total": 1.0},
            {"cost_type": "imagen_fast", "day": None, "total": 1.0},
            {"cost_type": "imagen_fast", "day": None, "total": 1.0},
        ],
    )
    monitor = _monitor(repo, tg)
    result = await monitor.sweep_once()
    assert result.alerts_sent == 1
    text = tg.send_message.call_args.kwargs["text"]
    assert "Spike oggi" in text


@pytest.mark.asyncio
async def test_spike_below_min_absolute_ignored(repo_tg):
    """Today's $0.10 on cost_type with avg $0.02 is 5× but abs too low to bother."""
    repo, tg = repo_tg
    await _stub_fetches(
        repo,
        totals_30d={"imagen_fast": 0.5},
        today={"imagen_fast": 0.10},  # < spike_min_abs_usd = 0.5
        prior_7d_rows=[
            {"cost_type": "imagen_fast", "day": None, "total": 0.02},
        ],
    )
    monitor = _monitor(repo, tg)
    result = await monitor.sweep_once()
    assert result.alerts_sent == 0


@pytest.mark.asyncio
async def test_spike_without_prior_history_ignored(repo_tg):
    repo, tg = repo_tg
    await _stub_fetches(
        repo,
        totals_30d={"imagen_fast": 2.0},
        today={"imagen_fast": 2.0},
        prior_7d_rows=[],   # no history
    )
    monitor = _monitor(repo, tg)
    result = await monitor.sweep_once()
    # no prior history → rolling_avg=0 → no spike detection
    # cap not exceeded → no alert
    assert result.alerts_sent == 0


# ── Error handling ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_failure_no_crash(repo_tg):
    repo, tg = repo_tg
    repo.fetch_safe = AsyncMock(side_effect=RuntimeError("pg"))
    monitor = _monitor(repo, tg)
    result = await monitor.sweep_once()
    assert any("fetch" in e for e in result.errors)
    assert result.alerts_sent == 0


# ── Default caps sanity ────────────────────────────────────────


def test_default_caps_cover_all_cost_types():
    """Every CostType enum value should have a soft cap entry (0 = not monitored)."""
    from backend.services.war_room.models import CostType

    for ct in CostType:
        assert ct.value in DEFAULT_SOFT_CAPS_USD
