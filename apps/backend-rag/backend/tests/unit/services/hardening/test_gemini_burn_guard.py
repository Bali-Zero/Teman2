"""Guilt, innocence, and cannot-verify for the Gemini burn-rate guard.

Mirrors ``test_llm_credit_sentinel.py``'s doctrine: the guilt case is easy;
the innocence cases are the point. A guard that fires on ordinary variance,
on cold-start (no baseline yet), or on noise-floor amounts gets muted by its
audience within a week — and a guard that reports NORMAL when it could not
even read the ledger is worse than no guard, because it manufactures a false
all-clear (cicatrix-superscar family #9, W106b doctrine).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.services.hardening.gemini_burn_guard import (
    BurnState,
    BurnWindowStats,
    GeminiBurnGuard,
)


def _guard(fetch, sent: list, **kwargs):
    async def notify(text: str) -> bool:
        sent.append(text)
        return True

    return GeminiBurnGuard(fetch, {"test": notify}, **kwargs)


def _stats(total: str, calls: int = 10, top_model: str | None = None, top_model_usd: str = "0"):
    return BurnWindowStats(
        total_usd=Decimal(total),
        call_count=calls,
        top_model=top_model,
        top_model_usd=Decimal(top_model_usd),
    )


# --------------------------------------------------------------- guilt


@pytest.mark.asyncio
async def test_burn_far_above_baseline_alerts_and_names_the_model():
    async def fetch():
        return (
            _stats("12.00", top_model="gemini-2.5-flash", top_model_usd="11.50"),
            _stats("2.00"),  # baseline already normalised to the same window
        )

    sent: list = []
    guard = _guard(fetch, sent)
    verdict = await guard.check()
    assert verdict.state is BurnState.ACCELERATING
    assert verdict.ratio == pytest.approx(6.0)
    assert len(sent) == 1
    assert "gemini-2.5-flash" in sent[0]
    assert "non conosco" in sent[0].lower() or "residuo" in sent[0].lower()


@pytest.mark.asyncio
async def test_alert_names_unattributed_model_honestly():
    async def fetch():
        return (_stats("10.00", top_model=None), _stats("1.00"))

    sent: list = []
    guard = _guard(fetch, sent)
    verdict = await guard.check()
    assert verdict.state is BurnState.ACCELERATING
    assert "non attribuibile" in verdict.detail


# ----------------------------------------------------------------- innocence


@pytest.mark.asyncio
async def test_ordinary_variance_under_threshold_stays_silent():
    async def fetch():
        return (_stats("2.50"), _stats("1.00"))  # 2.5x < default 3.0x threshold

    sent: list = []
    guard = _guard(fetch, sent)
    verdict = await guard.check()
    assert (verdict.state, sent) == (BurnState.NORMAL, [])


@pytest.mark.asyncio
async def test_flat_burn_matching_the_real_2026_08_11_outage_shape_stays_silent():
    """The exact regression this module must never produce: the four real
    historical depletions showed FLAT spend right up to the wall, never a
    preceding spike. A guard that alerts on steady-state burn would be
    noise, not signal."""

    async def fetch():
        return (_stats("3.62"), _stats("3.40"))  # ~1.06x — normal day-to-day noise

    sent: list = []
    guard = _guard(fetch, sent)
    verdict = await guard.check()
    assert (verdict.state, sent) == (BurnState.NORMAL, [])


@pytest.mark.asyncio
async def test_no_baseline_history_does_not_read_as_infinite_ratio():
    async def fetch():
        return (_stats("5.00"), _stats("0"))

    sent: list = []
    guard = _guard(fetch, sent)
    verdict = await guard.check()
    assert (verdict.state, sent) == (BurnState.NORMAL, [])
    assert verdict.ratio is None


@pytest.mark.asyncio
async def test_trivial_amount_below_floor_ignored_despite_high_ratio():
    """$0.01 vs $0.001 baseline is technically 10x and means nothing."""

    async def fetch():
        return (_stats("0.01"), _stats("0.001"))

    sent: list = []
    guard = _guard(fetch, sent, min_recent_usd=Decimal("1.00"))
    verdict = await guard.check()
    assert (verdict.state, sent) == (BurnState.NORMAL, [])


@pytest.mark.asyncio
async def test_threshold_is_configurable():
    async def fetch():
        return (_stats("4.00"), _stats("2.00"))  # 2.0x

    sent: list = []
    guard = _guard(fetch, sent, ratio_threshold=1.5)
    verdict = await guard.check()
    assert verdict.state is BurnState.ACCELERATING


# ------------------------------------------------------------ cannot-verify


@pytest.mark.asyncio
async def test_fetch_failure_is_cannot_verify_not_normal_not_accelerating():
    async def fetch():
        raise RuntimeError("connection to postgres refused")

    sent: list = []
    guard = _guard(fetch, sent)
    verdict = await guard.check()
    assert verdict.state is BurnState.CANNOT_VERIFY
    assert sent == []  # a read failure must never alert AND never claim "fine"
    assert verdict.should_alert is False


@pytest.mark.asyncio
async def test_cannot_verify_never_claims_a_ratio():
    async def fetch():
        raise TimeoutError("db unreachable")

    guard = _guard(fetch, [])
    verdict = await guard.check()
    assert verdict.ratio is None


# ---------------------------------------------------------- fan-out doctrine


@pytest.mark.asyncio
async def test_one_dead_channel_does_not_mute_the_others():
    async def fetch():
        return (_stats("10.00", top_model="gemini-3.5-flash", top_model_usd="9.0"), _stats("1.00"))

    delivered: list = []

    async def broken(text: str) -> bool:
        raise ConnectionError("telegram down")

    async def working(text: str) -> bool:
        delivered.append(text)
        return True

    guard = GeminiBurnGuard(fetch, {"broken": broken, "working": working})
    verdict = await guard.check()
    assert verdict.state is BurnState.ACCELERATING
    assert len(delivered) == 1
