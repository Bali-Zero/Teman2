"""Tests for CRM baseline extractor — leads_90d + source coverage.

Uses `lead_source` column (not `utm_source` — that doesn't exist in the
Bali Zero CRM schema as of 2026-04-22).
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock
from backend.services.research.crm_baseline import fetch_crm_baseline


class _FakeAcquire:
    def __init__(self, conn): self._conn = conn
    async def __aenter__(self): return self._conn
    async def __aexit__(self, *exc): return None


class _FakePool:
    def __init__(self, conn): self._conn = conn
    def acquire(self): return _FakeAcquire(self._conn)


@pytest.mark.asyncio
async def test_returns_leads_and_source_coverage():
    conn = AsyncMock()
    # Order: total_90d, social_90d, coverage_pct
    conn.fetchval = AsyncMock(side_effect=[324, 5, 0.981])
    pool = _FakePool(conn)
    result = await fetch_crm_baseline(pool)
    assert result == {
        "leads_total_90d": 324,
        "leads_social_90d": 5,
        "utm_coverage_pct": 0.981,
    }
    assert conn.fetchval.await_count == 3


@pytest.mark.asyncio
async def test_handles_null_returns_zeros():
    conn = AsyncMock()
    conn.fetchval = AsyncMock(side_effect=[None, None, None])
    pool = _FakePool(conn)
    result = await fetch_crm_baseline(pool)
    assert result == {
        "leads_total_90d": 0,
        "leads_social_90d": 0,
        "utm_coverage_pct": 0.0,
    }


@pytest.mark.asyncio
async def test_social_definition_excludes_whatsapp_referral_website():
    """`leads_social_90d` counts only social media channels, not WA/referral/web."""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(side_effect=[10, 0, 1.0])
    pool = _FakePool(conn)
    _ = await fetch_crm_baseline(pool)
    # Inspect the SQL that was used for social query (second call)
    social_sql = conn.fetchval.await_args_list[1].args[0]
    assert "instagram" in social_sql
    assert "linkedin" in social_sql
    assert "tiktok" in social_sql
    # Whatsapp is NOT a "social marketing" channel in this context — it's DM,
    # measured separately. Same for referral/website.
    assert "'whatsapp'" not in social_sql.lower()
    assert "'referral'" not in social_sql.lower()
    assert "'website'" not in social_sql.lower()
