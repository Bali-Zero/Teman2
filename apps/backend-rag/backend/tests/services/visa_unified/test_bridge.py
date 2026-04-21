"""Tests for visa_unified.bridge — facade between Visa Check and Oracle chat."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from backend.services.visa_unified.bridge import (
    FunnelContext,
    augment_chat_system_prompt,
    get_funnel_context,
)


# --- Fake asyncpg.Pool that returns canned rows ---------------------------

class _FakeConn:
    def __init__(self, row: dict | None):
        self._row = row

    async def fetchrow(self, *args, **kwargs):
        return self._row


class _FakePool:
    def __init__(self, row: dict | None = None):
        self._row = row
        self.acquire_calls = 0

    def acquire(self):
        self.acquire_calls += 1
        parent = self

        class _AcquireCtx:
            async def __aenter__(self_inner):
                return _FakeConn(parent._row)

            async def __aexit__(self_inner, *exc):
                return None

        return _AcquireCtx()


# --- get_funnel_context ---------------------------------------------------

@pytest.mark.asyncio
async def test_get_funnel_context_returns_typed_dataclass():
    row = {
        "hash": "abc1234567890000",
        "nationality": "USA",
        "purpose": "work_remote",
        "duration_months": 12,
        "budget_band": "50m_500m",
        "recommended_visa": "E33G",
        "recommendation_reason": "Digital Nomad KITAS",
        "alternatives": json.dumps(["E23-FREELANCE", "C1"]),
        "estimated_cost_idr": 13_000_000,
        "created_at": datetime.now(timezone.utc),
    }
    pool = _FakePool(row=row)
    ctx = await get_funnel_context("abc1234567890000", pool)
    assert isinstance(ctx, FunnelContext)
    assert ctx.check_hash == "abc1234567890000"
    assert ctx.recommended_visa == "E33G"
    assert ctx.estimated_cost_idr == 13_000_000
    assert ctx.alternatives == ["E23-FREELANCE", "C1"]
    assert ctx.referral_mode is False  # recommended_visa present ⇒ wizard did NOT abstain


@pytest.mark.asyncio
async def test_get_funnel_context_returns_none_when_hash_absent():
    pool = _FakePool(row=None)
    ctx = await get_funnel_context("missinghash000000", pool)
    assert ctx is None


@pytest.mark.asyncio
async def test_get_funnel_context_returns_none_for_expired_row():
    old_row = {
        "hash": "old111111111111",
        "nationality": "USA",
        "purpose": "work_remote",
        "duration_months": 12,
        "budget_band": "50m_500m",
        "recommended_visa": "E33G",
        "recommendation_reason": "...",
        "alternatives": json.dumps([]),
        "estimated_cost_idr": None,
        "created_at": datetime.now(timezone.utc) - timedelta(days=31),
    }
    pool = _FakePool(row=old_row)
    ctx = await get_funnel_context("old111111111111", pool)
    assert ctx is None, "Rows older than 30 days should not be returned"


@pytest.mark.asyncio
async def test_get_funnel_context_flags_referral_mode_when_visa_is_null():
    abstained_row = {
        "hash": "other11111111111",
        "nationality": "ITA",
        "purpose": "other",
        "duration_months": 12,
        "budget_band": "50m_500m",
        "recommended_visa": None,
        "recommendation_reason": "Let's review on WhatsApp",
        "alternatives": json.dumps([]),
        "estimated_cost_idr": None,
        "created_at": datetime.now(timezone.utc),
    }
    pool = _FakePool(row=abstained_row)
    ctx = await get_funnel_context("other11111111111", pool)
    assert ctx is not None
    assert ctx.referral_mode is True
    assert ctx.recommended_visa is None


# --- augment_chat_system_prompt -------------------------------------------

def _ctx(**overrides) -> FunnelContext:
    defaults = dict(
        check_hash="abc1234567890000",
        nationality="USA",
        purpose="work_remote",
        duration_months=12,
        budget_band="50m_500m",
        recommended_visa="E33G",
        estimated_cost_idr=13_000_000,
        alternatives=["E23-FREELANCE", "C1"],
        referral_mode=False,
    )
    defaults.update(overrides)
    return FunnelContext(**defaults)


def test_augment_chat_system_prompt_includes_visa_code():
    base = "You are the Visa Oracle."
    out = augment_chat_system_prompt(_ctx(), base)
    assert "E33G" in out
    assert base in out


def test_augment_chat_system_prompt_includes_cost_and_alternatives():
    base = "You are the Visa Oracle."
    out = augment_chat_system_prompt(_ctx(), base)
    assert "13,000,000" in out or "13000000" in out
    assert "E23-FREELANCE" in out
    assert "C1" in out


def test_augment_for_wizard_abstained_shifts_tone_to_handoff():
    base = "You are the Visa Oracle."
    ctx = _ctx(recommended_visa=None, estimated_cost_idr=None, alternatives=[], referral_mode=True)
    out = augment_chat_system_prompt(ctx, base)
    # When the wizard abstained, the augmentation tells the LLM to gather
    # details for WhatsApp handoff rather than invent a visa recommendation.
    low = out.lower()
    assert "whatsapp" in low or "human" in low or "handoff" in low
    assert "recommended visa:" not in low  # no fake recommendation to quote
    assert base in out


def test_augment_never_quotes_pricing_when_cost_is_null():
    base = "You are the Visa Oracle."
    ctx = _ctx(estimated_cost_idr=None)
    out = augment_chat_system_prompt(ctx, base)
    # Should not claim "IDR 0" or "IDR None"
    assert "IDR 0" not in out
    assert "None" not in out
