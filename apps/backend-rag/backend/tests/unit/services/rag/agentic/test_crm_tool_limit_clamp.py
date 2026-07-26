"""W0 safety pre-arm — S1: CRMTool `limit`/`days_ahead` clamp (PII blast-radius).

`CRMTool.execute()` (backend/services/rag/agentic/tools.py) passes the raw,
LLM-supplied `limit` kwarg straight into `LIMIT $N` SQL across 4 branches
(search_clients, expiring_documents, practice_stats, recent_clients). An LLM
can be induced (or can simply hallucinate) into passing an unbounded value —
`limit=1000000` would return the entire `clients`/`practices` table in one
tool call, a PII blast-radius bug. `days_ahead` gets the same defensive
clamp for the same class of caller-supplied-int risk (CLAUDE.md §13 CRM RBAC
is about WHO can see rows; this is about HOW MANY rows a single call can
exfiltrate once authorized).

Guilt/innocence pairs (cicatrix-superscar.md family #3 discipline — every
guard needs both):
- GUILT: an oversized/negative/garbage `limit` must never reach the SQL
  driver unclamped.
- INNOCENCE: a legitimate in-range `limit` must pass through UNCHANGED — the
  clamp must not silently override a caller's reasonable request.

No real client data — all fixture rows below are fabricated.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from backend.services.rag.agentic.tools import CRMTool

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_pool(fetch_return: list[dict] | None = None, fetchrow_return: dict | None = None):
    """Minimal asyncpg-pool double, mirrors test_team_crm_tools.py's `_make_pool`."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=fetch_return or [])
    conn.fetchrow = AsyncMock(return_value=fetchrow_return or {})

    pool = AsyncMock()

    @asynccontextmanager
    async def acquire():
        yield conn

    pool.acquire = acquire
    return pool, conn


# ---------------------------------------------------------------------------
# GUILT — an oversized/negative/non-numeric `limit` must never reach SQL raw
# ---------------------------------------------------------------------------


class TestCRMToolLimitClampGuilt:
    @pytest.mark.asyncio
    async def test_search_clients_oversized_limit_is_clamped(self):
        pool, conn = _make_pool(fetch_return=[])
        tool = CRMTool(db_pool=pool)

        await tool.execute(query_type="search_clients", search_term="x", limit=1_000_000)

        called_limit = conn.fetch.call_args.args[-1]
        assert called_limit <= 50

    @pytest.mark.asyncio
    async def test_recent_clients_negative_limit_is_clamped_to_floor(self):
        pool, conn = _make_pool(fetch_return=[])
        tool = CRMTool(db_pool=pool)

        await tool.execute(query_type="recent_clients", limit=-5)

        called_limit = conn.fetch.call_args.args[-1]
        assert called_limit >= 1

    @pytest.mark.asyncio
    async def test_expiring_documents_zero_limit_is_clamped_to_floor(self):
        pool, conn = _make_pool(fetch_return=[])
        tool = CRMTool(db_pool=pool)

        await tool.execute(query_type="expiring_documents", limit=0)

        called_limit = conn.fetch.call_args.args[-1]
        assert called_limit >= 1

    @pytest.mark.asyncio
    async def test_practice_stats_non_integer_limit_falls_back_to_default(self):
        pool, conn = _make_pool(fetch_return=[])
        tool = CRMTool(db_pool=pool)

        # An LLM can pass a garbage string instead of an int — must never
        # raise, must degrade to the documented default (20), never crash
        # the tool call.
        await tool.execute(query_type="practice_stats", limit="not-a-number")

        called_limit = conn.fetch.call_args.args[-1]
        assert called_limit == 20

    @pytest.mark.asyncio
    async def test_search_clients_none_limit_falls_back_to_default(self):
        pool, conn = _make_pool(fetch_return=[])
        tool = CRMTool(db_pool=pool)

        await tool.execute(query_type="search_clients", search_term="x", limit=None)

        called_limit = conn.fetch.call_args.args[-1]
        assert called_limit == 20

    @pytest.mark.asyncio
    async def test_search_clients_list_limit_falls_back_to_default(self):
        """A structurally wrong type (list, not scalar) must degrade, not crash."""
        pool, conn = _make_pool(fetch_return=[])
        tool = CRMTool(db_pool=pool)

        await tool.execute(query_type="search_clients", search_term="x", limit=[1, 2, 3])

        called_limit = conn.fetch.call_args.args[-1]
        assert called_limit == 20


# ---------------------------------------------------------------------------
# INNOCENCE — a legitimate in-range limit must pass through unchanged
# ---------------------------------------------------------------------------


class TestCRMToolLimitClampInnocence:
    @pytest.mark.asyncio
    async def test_search_clients_in_range_limit_is_unchanged(self):
        pool, conn = _make_pool(fetch_return=[])
        tool = CRMTool(db_pool=pool)

        await tool.execute(query_type="search_clients", search_term="x", limit=10)

        called_limit = conn.fetch.call_args.args[-1]
        assert called_limit == 10

    @pytest.mark.asyncio
    async def test_recent_clients_max_boundary_limit_is_unchanged(self):
        """Exactly the ceiling (50) must not be treated as over-limit."""
        pool, conn = _make_pool(fetch_return=[])
        tool = CRMTool(db_pool=pool)

        await tool.execute(query_type="recent_clients", limit=50)

        called_limit = conn.fetch.call_args.args[-1]
        assert called_limit == 50

    @pytest.mark.asyncio
    async def test_practice_stats_default_limit_is_20(self):
        pool, conn = _make_pool(fetch_return=[])
        tool = CRMTool(db_pool=pool)

        await tool.execute(query_type="practice_stats")

        called_limit = conn.fetch.call_args.args[-1]
        assert called_limit == 20


# ---------------------------------------------------------------------------
# days_ahead — same clamp class, exercised via the public execute() surface.
# The `expiring_documents` branch does not currently thread `days_ahead`
# into its SQL (pre-existing, out of scope to change here — see PR body),
# so this asserts the clamp never raises / never crashes the call for any
# input shape rather than a SQL-bound value.
# ---------------------------------------------------------------------------


class TestCRMToolDaysAheadClamp:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("days_ahead", [10_000, -30, 0, "garbage", None, [1, 2]])
    async def test_expiring_documents_never_crashes_on_any_days_ahead_shape(self, days_ahead):
        pool, _conn = _make_pool(fetch_return=[])
        tool = CRMTool(db_pool=pool)

        result = await tool.execute(query_type="expiring_documents", days_ahead=days_ahead)

        parsed = json.loads(result)
        assert "error" not in parsed


# ---------------------------------------------------------------------------
# No db_pool — untouched behaviour (regression guard)
# ---------------------------------------------------------------------------


class TestCRMToolNoDbPool:
    @pytest.mark.asyncio
    async def test_no_db_pool_returns_error_without_touching_clamp_logic(self):
        tool = CRMTool(db_pool=None)
        result = await tool.execute(query_type="client_stats", limit=999999999)
        parsed = json.loads(result)
        assert parsed == {"error": "CRM database not available"}
