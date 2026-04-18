"""Tests for the safety middleware stack."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import pytest

from backend.jobs.context import CostMeter, JobContext
from backend.jobs.middleware import (
    CostCap,
    OAuthGuard,
    detect_claude_cli_available,
)
from backend.jobs.retry import CostExceeded, OAuthViolation


def _ctx(meter: CostMeter | None = None) -> JobContext:
    return JobContext(
        job_name="t",
        scheduled_tick=datetime(2026, 4, 18, tzinfo=timezone.utc),
        attempt=1,
        run_id=1,
        db_pool=None,
        logger=logging.getLogger("t"),
        meter=meter or CostMeter(),
        claude_cli_available=True,
        source="scheduled",
    )


async def test_oauth_guard_raises_when_key_set(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-bad")
    guard = OAuthGuard()
    with pytest.raises(OAuthViolation):
        await guard.check(_ctx())


async def test_oauth_guard_passes_when_key_absent(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    guard = OAuthGuard()
    await guard.check(_ctx())  # no raise


async def test_cost_cap_allows_under_budget():
    cap = CostCap(limit_cents=100)
    ctx = _ctx()
    ctx.meter.charge(50, "a")
    cap.check(ctx)  # no raise
    ctx.meter.charge(40, "b")
    cap.check(ctx)


async def test_cost_cap_raises_on_overflow():
    cap = CostCap(limit_cents=100)
    ctx = _ctx()
    ctx.meter.charge(60, "a")
    ctx.meter.charge(50, "b")
    with pytest.raises(CostExceeded):
        cap.check(ctx)


def test_detect_claude_cli_available_on_macos_tty(monkeypatch):
    """Macos + TTY -> True."""
    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    assert detect_claude_cli_available() is True


def test_detect_claude_cli_available_on_linux_non_tty(monkeypatch):
    """Linux + non-TTY -> False (Fly.io container case)."""
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    assert detect_claude_cli_available() is False
