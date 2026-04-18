"""End-to-end integration test for the RAG trace ledger.

Requires a live Postgres reachable via ``RAG_TRACE_TEST_DSN`` (falls back
to ``postgresql://localhost/postgres`` on Pro). The test:

* applies migration 112 (rag_traces) into a throwaway schema;
* runs a nested :func:`rag_span` pipeline;
* awaits the fire-and-forget flush;
* verifies the row via :func:`aggregate_rag_stats`.

Per durable team feedback "integration tests must hit a real database, not
mocks" the DB path is exercised directly. The test is skipped when no
Postgres is reachable so CI without infra remains green.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from decimal import Decimal
from pathlib import Path

import asyncpg
import pytest

from backend.db.migration_base import _split_rollback_marker
from backend.services.observability import rag_trace
from backend.services.observability.rag_trace import rag_span
from backend.services.observability.stats_aggregator import (
    StatsRequest,
    aggregate_rag_stats,
)

pytestmark = pytest.mark.integration

DEFAULT_DSN = os.environ.get(
    "RAG_TRACE_TEST_DSN", "postgresql://localhost/postgres",
)
MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "db"
    / "migrations_v2"
    / "112_rag_traces.sql"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


async def _can_connect() -> bool:
    try:
        conn = await asyncpg.connect(DEFAULT_DSN, timeout=2)
    except Exception:
        return False
    await conn.close()
    return True


@pytest.fixture
async def _connectivity():
    if not await _can_connect():
        pytest.skip(f"Postgres not reachable at {DEFAULT_DSN}")


@pytest.fixture
async def pg_pool(_connectivity):  # noqa: ARG001 — fixture chain
    """Ephemeral schema + asyncpg pool. Creates rag_traces, yields pool, drops."""
    schema = f"rag_trace_it_{uuid.uuid4().hex[:8]}"
    admin = await asyncpg.connect(DEFAULT_DSN)
    await admin.execute(f'CREATE SCHEMA "{schema}"')
    await admin.close()

    pool = await asyncpg.create_pool(
        DEFAULT_DSN,
        min_size=1, max_size=2,
        server_settings={"search_path": schema},
    )
    sql = MIGRATION_PATH.read_text(encoding="utf-8")
    forward, _rollback = _split_rollback_marker(sql)
    async with pool.acquire() as conn:
        await conn.execute(forward)

    try:
        yield pool
    finally:
        await pool.close()
        admin = await asyncpg.connect(DEFAULT_DSN)
        await admin.execute(f'DROP SCHEMA "{schema}" CASCADE')
        await admin.close()


# ---------------------------------------------------------------------------
# End-to-end roundtrip
# ---------------------------------------------------------------------------


async def test_nested_spans_persist_and_aggregate(pg_pool, monkeypatch):
    monkeypatch.setenv("RAG_TRACE_ENABLED", "true")
    monkeypatch.setenv("RAG_TRACE_SAMPLE_RATE", "1.0")
    rag_trace.configure_pool(pg_pool)

    try:
        async with rag_span("retrieval", domain="visa") as r:
            r.set(cache_hit=False, metadata={"docs": 5})
            async with rag_span("rerank") as rr:
                rr.set(metadata={"top_k": 5})
            async with rag_span("reasoning") as reasoning:
                reasoning.set(
                    tokens_in=400, tokens_out=120,
                    cost_usd=Decimal("0.0195"),
                )

        # Fire-and-forget flush: wait generously for the task to drain.
        for _ in range(20):
            await asyncio.sleep(0.05)
            async with pg_pool.acquire() as conn:
                count = await conn.fetchval("SELECT COUNT(*) FROM rag_traces")
            if count >= 1:
                break
        assert count == 1

        async with pg_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM rag_traces")
        assert row["total_tokens_in"] == 400
        assert row["total_tokens_out"] == 120
        assert Decimal(row["total_cost_usd"]) == Decimal("0.019500")
        assert row["domain"] == "visa"
        assert row["total_duration_ms"] >= 0

        spans = row["root_span"]
        if isinstance(spans, str):
            import json
            spans = json.loads(spans)
        stages = {s["stage"] for s in spans["spans"]}
        assert stages == {"retrieval", "rerank", "reasoning"}

        payload = await aggregate_rag_stats(pg_pool, StatsRequest(window_hours=1))
        assert payload["total_queries"] == 1
        assert "retrieval" in payload["stages"]
        assert "reasoning" in payload["stages"]
        assert payload["top_domains_by_cost"][0]["domain"] == "visa"
    finally:
        rag_trace.configure_pool(None)


async def test_feature_flag_off_writes_nothing(pg_pool, monkeypatch):
    monkeypatch.setenv("RAG_TRACE_ENABLED", "false")
    rag_trace.configure_pool(pg_pool)
    try:
        async with rag_span("retrieval"):
            pass
        await asyncio.sleep(0.1)
        async with pg_pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM rag_traces")
        assert count == 0
    finally:
        rag_trace.configure_pool(None)
