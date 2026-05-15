"""Unit tests for QueryAnalyticsRepository.

Focused on the jsonb-binding contract of `log_query` — see the
2026-05-14 double-encoding regression.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


def _mock_pool() -> tuple[MagicMock, AsyncMock]:
    """Mock asyncpg pool whose acquire() yields a shared AsyncMock conn."""
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire.return_value = ctx
    return pool, conn


class TestLogQueryJsonbBind:
    """Regression 2026-05-14 — jsonb double-encoding of `metadata`.

    The app/runtime asyncpg pool registers a jsonb codec with
    ``encoder=json.dumps`` (service_initializer.py / database.py). If
    ``log_query`` ALSO calls ``json.dumps(...)`` on ``metadata`` before
    binding, the value is serialized twice and lands in PG as a jsonb
    *string* scalar (``"{}"``) instead of a jsonb *object*. The
    ``metadata ? 'user_email'`` operator then silently returns nothing.

    The fix binds the raw dict; the pool codec serializes it once.
    """

    @pytest.mark.asyncio
    async def test_metadata_bound_as_dict_not_str_with_user(self) -> None:
        from backend.db.repositories.query_analytics_repository import (
            QueryAnalyticsRepository,
        )

        pool, conn = _mock_pool()
        conn.fetchrow = AsyncMock(
            return_value={"id": "00000000-0000-0000-0000-000000000001"}
        )
        repo = QueryAnalyticsRepository(pool)

        await repo.log_query(query_text="how to set up PT PMA?", user_id="u@example.com")

        # log_query args after query: query_text, query_hash, session_id, metadata, ...
        bound_metadata = conn.fetchrow.call_args[0][4]
        assert isinstance(bound_metadata, dict), (
            f"metadata bound as {type(bound_metadata).__name__} — json.dumps "
            f"+ pool codec = double-encoding into a jsonb string scalar"
        )
        assert bound_metadata == {"user_email": "u@example.com"}

    @pytest.mark.asyncio
    async def test_metadata_bound_as_empty_dict_without_user(self) -> None:
        from backend.db.repositories.query_analytics_repository import (
            QueryAnalyticsRepository,
        )

        pool, conn = _mock_pool()
        conn.fetchrow = AsyncMock(
            return_value={"id": "00000000-0000-0000-0000-000000000002"}
        )
        repo = QueryAnalyticsRepository(pool)

        await repo.log_query(query_text="anon query", user_id=None)

        bound_metadata = conn.fetchrow.call_args[0][4]
        assert isinstance(bound_metadata, dict), (
            f"empty metadata bound as {type(bound_metadata).__name__}, expected dict"
        )
        assert bound_metadata == {}

    @pytest.mark.asyncio
    async def test_log_query_sql_targets_query_analytics(self) -> None:
        # Anchor: confirm we are asserting against the right INSERT.
        from backend.db.repositories.query_analytics_repository import (
            QueryAnalyticsRepository,
        )

        pool, conn = _mock_pool()
        conn.fetchrow = AsyncMock(
            return_value={"id": "00000000-0000-0000-0000-000000000003"}
        )
        repo = QueryAnalyticsRepository(pool)

        await repo.log_query(query_text="q", user_id="x@y.z")

        assert "INSERT INTO query_analytics" in conn.fetchrow.call_args[0][0]
