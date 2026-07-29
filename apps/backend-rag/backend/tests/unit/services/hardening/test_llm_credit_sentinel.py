"""Guilt and innocence for the LLM credit sentinel.

The guilt case is easy; the innocence cases are the point. A sentinel that
fires on every 429 gets muted by its audience within a week, and then it is
worth less than no sentinel at all — so a plain rate limit, a network error and
a healthy reply must all stay silent.
"""

from __future__ import annotations

import pytest

from backend.services.hardening.llm_credit_sentinel import (
    CreditState,
    LLMCreditSentinel,
    classify_probe_error,
)

DEPLETED_MSG = (
    "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'Your prepayment "
    "credits are depleted. Please go to AI Studio at https://ai.studio/projects "
    "to manage your project and billing.'}}"
)
RATE_LIMIT_MSG = (
    "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'Quota exceeded "
    "for quota metric generate_requests_per_model_per_minute'}}"
)


def _sentinel(probe, sent: list):
    async def notify(text: str) -> bool:
        sent.append(text)
        return True

    return LLMCreditSentinel(probe, {"test": notify}), sent


# --------------------------------------------------------------- classifier


def test_depletion_wording_is_classified_as_depleted():
    v = classify_probe_error(RuntimeError(DEPLETED_MSG))
    assert (v.state, v.should_alert) == (CreditState.DEPLETED, True)


def test_plain_rate_limit_429_is_not_depletion():
    """The exact regression that would make this alarm untrustworthy."""
    v = classify_probe_error(RuntimeError(RATE_LIMIT_MSG))
    assert (v.state, v.should_alert) == (CreditState.RATE_LIMITED, False)


def test_network_error_is_unknown_not_depletion():
    v = classify_probe_error(TimeoutError("connection timed out"))
    assert (v.state, v.should_alert) == (CreditState.UNKNOWN, False)


def test_depletion_is_detected_even_without_the_429_token():
    v = classify_probe_error(RuntimeError("billing account has been depleted"))
    assert v.state is CreditState.DEPLETED


# ----------------------------------------------------------------- sentinel


@pytest.mark.asyncio
async def test_depleted_probe_alerts_every_channel():
    async def probe() -> str:
        raise RuntimeError(DEPLETED_MSG)

    sent: list = []
    sentinel, _ = _sentinel(probe, sent)
    verdict = await sentinel.check()
    assert verdict.state is CreditState.DEPLETED
    assert len(sent) == 1
    assert "AI Studio" in sent[0] and "Nuzantara" in sent[0]


@pytest.mark.asyncio
async def test_healthy_probe_stays_silent():
    async def probe() -> str:
        return "PONG"

    sent: list = []
    sentinel, _ = _sentinel(probe, sent)
    verdict = await sentinel.check()
    assert (verdict.state, sent) == (CreditState.OK, [])


@pytest.mark.asyncio
async def test_rate_limited_probe_stays_silent():
    async def probe() -> str:
        raise RuntimeError(RATE_LIMIT_MSG)

    sent: list = []
    sentinel, _ = _sentinel(probe, sent)
    verdict = await sentinel.check()
    assert (verdict.state, sent) == (CreditState.RATE_LIMITED, [])


@pytest.mark.asyncio
async def test_one_dead_channel_does_not_mute_the_others():
    """WhatsApp refuses outside Meta's 24h window — Telegram must still fire."""

    async def probe() -> str:
        raise RuntimeError(DEPLETED_MSG)

    delivered: list = []

    async def broken(text: str) -> bool:
        raise ConnectionError("24h window closed")

    async def working(text: str) -> bool:
        delivered.append(text)
        return True

    sentinel = LLMCreditSentinel(probe, {"wa": broken, "tg": working})
    verdict = await sentinel.check()
    assert verdict.state is CreditState.DEPLETED
    assert len(delivered) == 1
