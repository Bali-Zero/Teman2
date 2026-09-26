"""Tests for visa_unified.bridge — facade between Visa Check and Oracle chat."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

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
        self.sql: str | None = None

    async def fetchrow(self, *args, **kwargs):
        self.sql = args[0]
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
                parent.last_conn = _FakeConn(parent._row)
                return parent.last_conn

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


def _clock_row(**overrides) -> dict:
    today = datetime.now(timezone.utc).date()
    row = {
        "hash": "clock11111111111",
        "branch": "clock",
        "visa_type": "VOA",
        "entry_date": today - timedelta(days=10),
        "expiry_date": today + timedelta(days=20),
        "extensions_possible": 1,
        "extension_days": 30,
        "created_at": datetime.now(timezone.utc),
    }
    row.update(overrides)
    return row


@pytest.mark.asyncio
async def test_get_funnel_context_returns_clock_context_for_clock_row():
    row = _clock_row()
    ctx = await get_funnel_context("clock11111111111", _FakePool(row=row))
    assert ctx is not None
    assert ctx.branch == "clock"
    assert ctx.referral_mode is False
    assert ctx.recommended_visa is None
    assert ctx.visa_type == "VOA"
    assert ctx.expiry_date == row["expiry_date"]
    assert (ctx.extensions_possible, ctx.extension_days) == (1, 30)


@pytest.mark.asyncio
async def test_get_funnel_context_clock_row_has_no_ttl():
    row = _clock_row(created_at=datetime.now(timezone.utc) - timedelta(days=60))
    ctx = await get_funnel_context("clock11111111111", _FakePool(row=row))
    assert ctx is not None and ctx.branch == "clock"


@pytest.mark.asyncio
async def test_get_funnel_context_clock_row_coerces_datetime_and_tolerates_nulls():
    stamp = datetime(2026, 9, 1, 12, 30)
    row = _clock_row(
        entry_date=stamp, expiry_date=None, extensions_possible=None, extension_days=None
    )
    ctx = await get_funnel_context("clock11111111111", _FakePool(row=row))
    assert ctx is not None
    assert ctx.entry_date == stamp.date() and type(ctx.entry_date).__name__ == "date"
    assert ctx.expiry_date is None and ctx.extensions_possible is None


@pytest.mark.asyncio
async def test_get_funnel_context_sql_is_not_restricted_to_match_branch():
    """The query must reach clock rows: no `branch = 'match'` filter, branch is selected."""
    pool = _FakePool(row=_clock_row())
    await get_funnel_context("clock11111111111", pool)
    sql = " ".join(pool.last_conn.sql.split())
    assert "branch = 'match'" not in sql
    assert "branch" in sql.split(" FROM ")[0]
    assert "WHERE hash = $1" in sql


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


def test_augment_for_clock_context_states_ground_truth_without_wizard_language():
    today = datetime.now(timezone.utc).date()
    expiry = today + timedelta(days=20)
    ctx = _ctx(
        branch="clock",
        recommended_visa=None,
        estimated_cost_idr=None,
        alternatives=[],
        nationality="",
        purpose="",
        duration_months=0,
        budget_band="",
        visa_type="VOA",
        entry_date=today - timedelta(days=10),
        expiry_date=expiry,
        extensions_possible=1,
        extension_days=30,
    )
    base = "You are the Visa Oracle."
    out = augment_chat_system_prompt(ctx, base)
    assert "VOA" in out
    assert expiry.isoformat() in out
    assert "20 days remaining" in out
    assert "1 extension(s) of 30 days" in out
    assert base in out
    assert "wizard" not in out.lower()
    assert "recommended visa:" not in out.lower()
    assert "None" not in out


def test_augment_for_clock_context_past_expiry_forbids_procedural_advice():
    today = datetime.now(timezone.utc).date()
    ctx = _ctx(
        branch="clock",
        visa_type="VOA",
        entry_date=today - timedelta(days=40),
        expiry_date=today - timedelta(days=3),
    )
    out = augment_chat_system_prompt(ctx, "base")
    assert "already ended 3 days ago" in out
    assert "no procedural advice" in out
