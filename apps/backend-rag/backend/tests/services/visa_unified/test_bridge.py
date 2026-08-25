"""Tests for visa_unified.bridge — facade between Visa Check and Oracle chat."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

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
        self.last_query: str | None = None
        self.last_params: tuple = ()

    async def fetchrow(self, query, *params):
        self.last_query = query
        self.last_params = params
        return self._row


class _FakePool:
    def __init__(self, row: dict | None = None):
        self._row = row
        self.acquire_calls = 0
        self.last_conn: _FakeConn | None = None

    def acquire(self):
        self.acquire_calls += 1
        parent = self

        class _AcquireCtx:
            async def __aenter__(self_inner):
                conn = _FakeConn(parent._row)
                parent.last_conn = conn
                return conn

            async def __aexit__(self_inner, *exc):
                return None

        return _AcquireCtx()


# --- get_funnel_context ---------------------------------------------------


@pytest.mark.asyncio
async def test_get_funnel_context_returns_typed_dataclass():
    row = {
        "hash": "abc1234567890000",
        "branch": "match",
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
async def test_get_funnel_context_allows_null_created_at():
    """A row with NULL created_at bypasses TTL and is returned.

    Rationale: TTL is a safety net against replay attacks; authoritative
    freshness comes from the JWT's `exp` claim (see Task 2). If the DB
    row has no created_at (shouldn't happen in production but is
    permitted by the schema), we still return the context rather than
    discard it silently.
    """
    row = {
        "hash": "nullts1111111111",
        "branch": "match",
        "nationality": "USA",
        "purpose": "work_remote",
        "duration_months": 12,
        "budget_band": "50m_500m",
        "recommended_visa": "E33G",
        "recommendation_reason": "…",
        "alternatives": json.dumps(["E23-FREELANCE"]),
        "estimated_cost_idr": 13_000_000,
        "created_at": None,  # legitimate NULL
    }
    pool = _FakePool(row=row)
    ctx = await get_funnel_context("nullts1111111111", pool)
    assert ctx is not None, "NULL created_at must not be treated as expired"
    assert ctx.check_hash == "nullts1111111111"


@pytest.mark.asyncio
async def test_get_funnel_context_flags_referral_mode_when_visa_is_null():
    abstained_row = {
        "hash": "other11111111111",
        "branch": "match",
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


@pytest.mark.asyncio
async def test_get_funnel_context_query_has_no_hardcoded_branch_filter():
    """RED for the 410 defect (docs/plans/2026-08-24-visa-oracle-live): the
    SELECT used to hardcode ``AND branch = 'match'``, so every clock-branch
    hash (in-country visitors — the people who call Bali Zero most
    urgently) fetched no row at all and the chat endpoint 410'd. The query
    must discriminate on the row's own `branch` column in Python, not filter
    it out in SQL."""
    pool = _FakePool(row=None)
    await get_funnel_context("anyhash0000000000", pool)
    assert pool.last_conn is not None, "get_funnel_context must query via pool.acquire()"
    query_no_ws = " ".join(pool.last_conn.last_query.split())
    assert "branch = 'match'" not in query_no_ws, (
        f"query still hardcodes a branch filter, clock rows can never match: {query_no_ws!r}"
    )


@pytest.mark.asyncio
async def test_get_funnel_context_returns_clock_shaped_context():
    """A clock-branch visa_checks row (backend/services/visa_check/repository.py
    ::save_clock) carries visa_type/entry_date/expiry_date/extensions_*, NOT
    nationality/purpose/recommended_visa/estimated_cost_idr. The context
    returned for it must reflect that real shape — never fabricate empty
    strings/zeros for the match-only fields it does not have."""
    row = {
        "hash": "clockhash000000000",
        "branch": "clock",
        "visa_type": "B1",
        "entry_date": date(2026, 7, 1),
        "expiry_date": date(2026, 7, 31),
        "extensions_possible": 1,
        "extension_days": 30,
        "nationality": None,
        "purpose": None,
        "duration_months": None,
        "budget_band": None,
        "recommended_visa": None,
        "recommendation_reason": None,
        "alternatives": None,
        "estimated_cost_idr": None,
        "created_at": datetime.now(timezone.utc),
    }
    pool = _FakePool(row=row)
    ctx = await get_funnel_context("clockhash000000000", pool)
    assert ctx is not None
    assert ctx.branch == "clock"
    assert ctx.visa_type == "B1"
    assert ctx.entry_date == date(2026, 7, 1)
    assert ctx.expiry_date == date(2026, 7, 31)
    assert ctx.extensions_possible == 1
    assert ctx.extension_days == 30
    # Must not lie about facts a clock row does not carry.
    assert ctx.nationality is None
    assert ctx.purpose is None
    assert ctx.recommended_visa is None
    assert ctx.estimated_cost_idr is None


@pytest.mark.asyncio
async def test_get_funnel_context_clock_branch_respects_ttl():
    """The _CONTEXT_TTL freshness check must apply to the clock shape too,
    not just the match shape it was written against."""
    row = {
        "hash": "oldclock0000000000",
        "branch": "clock",
        "visa_type": "B1",
        "entry_date": date(2026, 1, 1),
        "expiry_date": date(2026, 1, 31),
        "extensions_possible": 0,
        "extension_days": 0,
        "nationality": None,
        "purpose": None,
        "duration_months": None,
        "budget_band": None,
        "recommended_visa": None,
        "recommendation_reason": None,
        "alternatives": None,
        "estimated_cost_idr": None,
        "created_at": datetime.now(timezone.utc) - timedelta(days=31),
    }
    pool = _FakePool(row=row)
    ctx = await get_funnel_context("oldclock0000000000", pool)
    assert ctx is None, "Clock rows older than 30 days should not be returned either"


# --- augment_chat_system_prompt -------------------------------------------


def _ctx(**overrides) -> FunnelContext:
    defaults = {
        "check_hash": "abc1234567890000",
        "nationality": "USA",
        "purpose": "work_remote",
        "duration_months": 12,
        "budget_band": "50m_500m",
        "recommended_visa": "E33G",
        "estimated_cost_idr": 13_000_000,
        "alternatives": ["E23-FREELANCE", "C1"],
        "referral_mode": False,
    }
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


def test_augment_match_context_with_no_cost_does_not_instruct_quoting_price():
    """Issue (3): with no cost present, the preamble used to still say
    'Always quote this recommended visa and cost' — inviting the model to
    invent a number it was never given. With no cost, it must say plainly
    that none is available and the team confirms."""
    base = "You are the Visa Oracle."
    ctx = _ctx(estimated_cost_idr=None)
    out = augment_chat_system_prompt(ctx, base)
    low = out.lower()
    assert "quote this recommended visa and cost" not in low
    assert "idr" not in low
    assert "no cost" in low or "no price" in low


def test_augment_chat_system_prompt_for_clock_branch_states_permit_facts():
    """Issue (1): a clock row has no cost at all — the preamble must name
    the visitor's own permit facts (type, entry, expiry, extensions) and
    must NOT invite the model to quote a price for it."""
    base = "You are the Visa Oracle."
    ctx = FunnelContext(
        check_hash="clockhash000000000",
        branch="clock",
        referral_mode=False,
        visa_type="B1",
        entry_date=date(2026, 7, 1),
        expiry_date=date(2026, 7, 31),
        extensions_possible=1,
        extension_days=30,
    )
    out = augment_chat_system_prompt(ctx, base)
    assert "B1" in out
    assert "2026-07-01" in out
    assert "2026-07-31" in out
    assert base in out
    low = out.lower()
    assert "idr" not in low
    assert "no cost" in low or "no price" in low
