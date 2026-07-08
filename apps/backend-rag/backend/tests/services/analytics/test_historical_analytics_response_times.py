"""
Regression test for /api/analytics/response-times 500 error.

LIVE BUG (prod, captured 2026-07-08):
    Failed to calculate response times: function round(double precision, integer) does not exist

Root cause: calculate_response_times() builds a raw SQL query with
    ROUND(AVG(EXTRACT(EPOCH FROM (...)) / 86400), 2)
and
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (...)) / 86400), 2)

EXTRACT(...)/86400 is double precision. AVG()/PERCENTILE_CONT() of a double
precision column is still double precision. Postgres only defines
round(numeric, integer) with a scale argument -- round(double precision, integer)
does not exist, so every call raises UndefinedFunctionError, which the router
(backend/app/routers/analytics.py::get_response_times) catches and re-raises
as HTTP 500 "Failed to calculate response times: ...".

Fix: cast the averaged/percentile expression to ::numeric before ROUND(x, 2).

This test does NOT require a live database. It captures the SQL string that
calculate_response_times() would send to asyncpg via an AsyncMock db_pool and
asserts every ROUND(..., 2) call in the query casts its argument to ::numeric
(guilt: fails against the pre-fix query; innocence: passes against the fixed
query and does not false-positive on the safe single-arg ROUND(...)::int
pattern used elsewhere in the codebase, e.g. guardian.py).
"""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.analytics.historical_analytics import calculate_response_times

# Matches ROUND( ... , 2) calls with a scale argument, capturing the inner expression.
_ROUND_WITH_SCALE_RE = re.compile(r"ROUND\(\s*(.*?)\s*,\s*2\s*\)", re.IGNORECASE | re.DOTALL)


@pytest.fixture
def mock_pool_and_conn():
    """
    Build an AsyncMock db_pool whose `acquire()` async-context-manager yields a
    connection whose `.fetch()` records the query text and returns an empty
    row list (function under test only needs to build+send the query; the
    500 in prod happens at the DB layer on `fetch`, which we don't need to
    simulate to catch the SQL-construction bug).
    """
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])

    acquire_cm = AsyncMock()
    acquire_cm.__aenter__.return_value = conn
    acquire_cm.__aexit__.return_value = False

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_cm)

    return pool, conn


@pytest.mark.asyncio
async def test_response_times_query_casts_round_args_to_numeric(mock_pool_and_conn):
    """
    Guilt: on the buggy source this test fails because at least one
    ROUND(..., 2) call wraps a bare double-precision expression
    (EXTRACT(...)/86400 via AVG/PERCENTILE_CONT) without a ::numeric cast --
    the exact call Postgres rejects with
    "function round(double precision, integer) does not exist".
    """
    pool, conn = mock_pool_and_conn

    await calculate_response_times(pool)

    assert conn.fetch.await_count == 1
    query = conn.fetch.await_args.args[0]

    round_calls = _ROUND_WITH_SCALE_RE.findall(query)
    assert round_calls, "expected at least one ROUND(..., 2) call in the response-times query"

    for expr in round_calls:
        assert "::numeric" in expr, (
            "ROUND(x, 2) with a scale argument requires x cast to ::numeric "
            f"(Postgres has no round(double precision, integer) overload). Offending expr: {expr!r}"
        )


@pytest.mark.asyncio
async def test_response_times_query_still_uses_epoch_extraction(mock_pool_and_conn):
    """
    Innocence guard: the fix must cast to ::numeric, not remove the
    EXTRACT(EPOCH FROM ...) day-conversion logic that the metric depends on.
    """
    pool, conn = mock_pool_and_conn

    await calculate_response_times(pool)

    query = conn.fetch.await_args.args[0]
    assert "EXTRACT(EPOCH FROM" in query
    assert "/ 86400" in query


def test_round_with_scale_regex_does_not_flag_safe_single_arg_round():
    """
    Innocence guard for the test's own regex: single-arg ROUND(x)::int
    (used e.g. in guardian.py) is a *different*, valid overload
    (round(double precision) -> double precision) and must NOT be flagged
    by this test's pattern, since it takes no scale argument.
    """
    safe_query = "SELECT ROUND(AVG(overall_score))::int as avg_overall FROM t"
    assert _ROUND_WITH_SCALE_RE.findall(safe_query) == []
