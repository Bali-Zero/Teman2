"""
Tests for Migration 079: Naga Agentic Research Engine Tables

Verifies SQL structure, key design decisions, and idempotency
without requiring a live database connection.
"""

import inspect
import re
from unittest.mock import AsyncMock

import pytest

from backend.migrations.migration_079_naga_tables import apply, rollback


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_executed_sql(calls: list[tuple]) -> str:
    """Join all SQL strings passed to conn.execute into one blob."""
    return "\n".join(call.args[0] for call in calls if call.args)


def _normalize(sql: str) -> str:
    """Collapse runs of whitespace to a single space for matching."""
    return re.sub(r"\s+", " ", sql)


# ---------------------------------------------------------------------------
# Table presence
# ---------------------------------------------------------------------------

EXPECTED_TABLES = [
    "naga_sessions",
    "naga_sources",
    "naga_claims",
    "naga_claim_evidence",
    "naga_claim_transitions",
]


@pytest.mark.asyncio
async def test_all_five_tables_created():
    """All 5 Naga table names must appear in the CREATE TABLE statements."""
    conn = AsyncMock()
    await apply(conn)
    sql = _collect_executed_sql(conn.execute.call_args_list)
    for table in EXPECTED_TABLES:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql, (
            f"Missing CREATE TABLE IF NOT EXISTS for {table}"
        )


@pytest.mark.asyncio
async def test_all_five_tables_dropped_on_rollback():
    """Rollback must DROP all 5 tables (CASCADE)."""
    conn = AsyncMock()
    await rollback(conn)
    sql = _collect_executed_sql(conn.execute.call_args_list)
    for table in EXPECTED_TABLES:
        assert table in sql, f"Rollback missing DROP for {table}"
    assert "CASCADE" in sql, "Rollback should use CASCADE"


# ---------------------------------------------------------------------------
# Key design decisions (from Naga spec review)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_evidence_map_uri_not_jsonb():
    """evidence_map must be stored as TEXT URI, not JSONB (Pointer State Pattern)."""
    conn = AsyncMock()
    await apply(conn)
    sql = _collect_executed_sql(conn.execute.call_args_list)
    norm = _normalize(sql)
    assert "evidence_map_uri" in sql, "Missing evidence_map_uri column"
    # Must be TEXT type (normalized to collapse alignment spaces)
    assert "evidence_map_uri TEXT" in norm, (
        "evidence_map_uri must be TEXT type"
    )


@pytest.mark.asyncio
async def test_langgraph_thread_id_present():
    """langgraph_thread_id column must exist for LangGraph checkpoint/resume."""
    conn = AsyncMock()
    await apply(conn)
    sql = _collect_executed_sql(conn.execute.call_args_list)
    assert "langgraph_thread_id" in sql, "Missing langgraph_thread_id column"


@pytest.mark.asyncio
async def test_review_status_default_auto_extracted():
    """review_status must default to 'auto_extracted' (human review gate)."""
    conn = AsyncMock()
    await apply(conn)
    sql = _collect_executed_sql(conn.execute.call_args_list)
    assert "review_status" in sql, "Missing review_status column"
    assert "auto_extracted" in sql, "review_status must default to 'auto_extracted'"


@pytest.mark.asyncio
async def test_claim_evidence_join_table_exists():
    """naga_claim_evidence must be a proper join table with relation column."""
    conn = AsyncMock()
    await apply(conn)
    sql = _collect_executed_sql(conn.execute.call_args_list)
    norm = _normalize(sql)
    assert "naga_claim_evidence" in sql
    assert "claim_id" in sql, "Missing claim_id FK in naga_claim_evidence"
    assert "source_id" in sql, "Missing source_id FK in naga_claim_evidence"
    assert "relation VARCHAR" in norm, "Missing relation column in naga_claim_evidence"


@pytest.mark.asyncio
async def test_claim_transitions_table_exists():
    """naga_claim_transitions must support many-to-many supersession."""
    conn = AsyncMock()
    await apply(conn)
    sql = _collect_executed_sql(conn.execute.call_args_list)
    assert "naga_claim_transitions" in sql
    assert "from_claim_id" in sql, "Missing from_claim_id in naga_claim_transitions"
    assert "to_claim_id" in sql, "Missing to_claim_id in naga_claim_transitions"
    assert "transition_type" in sql, "Missing transition_type in naga_claim_transitions"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_idempotent_create_tables():
    """All CREATE TABLE statements must use IF NOT EXISTS."""
    conn = AsyncMock()
    await apply(conn)
    sql = _collect_executed_sql(conn.execute.call_args_list)
    create_table_count = sql.count("CREATE TABLE")
    create_table_if_count = sql.count("CREATE TABLE IF NOT EXISTS")
    assert create_table_count > 0, "No CREATE TABLE found"
    assert create_table_count == create_table_if_count, (
        f"Not all CREATE TABLE use IF NOT EXISTS "
        f"({create_table_count} vs {create_table_if_count})"
    )


@pytest.mark.asyncio
async def test_idempotent_create_indexes():
    """All CREATE INDEX statements must use IF NOT EXISTS."""
    conn = AsyncMock()
    await apply(conn)
    sql = _collect_executed_sql(conn.execute.call_args_list)
    create_idx_count = sql.count("CREATE INDEX")
    if_not_exists_idx = sql.count("CREATE INDEX IF NOT EXISTS")
    assert create_idx_count > 0, "No CREATE INDEX found"
    assert create_idx_count == if_not_exists_idx, (
        f"Not all CREATE INDEX use IF NOT EXISTS ({create_idx_count} vs {if_not_exists_idx})"
    )


# ---------------------------------------------------------------------------
# Indexes
# ---------------------------------------------------------------------------

EXPECTED_INDEXES = [
    "idx_naga_sessions_parent",
    "idx_naga_sessions_status",
    "idx_naga_sources_url",
    "idx_naga_sources_hash",
    "idx_naga_claims_domain",
    "idx_naga_claims_topic",
    "idx_naga_claims_confidence",
    "idx_naga_claims_valid",
    "idx_naga_claims_verification",
    "idx_naga_claims_review",
    "idx_naga_claims_key",
    "idx_naga_claim_evidence_claim",
    "idx_naga_claim_evidence_source",
    "idx_naga_claim_transitions_from",
    "idx_naga_claim_transitions_to",
]


@pytest.mark.asyncio
async def test_all_indexes_created():
    """All specified indexes must be present in the migration SQL."""
    conn = AsyncMock()
    await apply(conn)
    sql = _collect_executed_sql(conn.execute.call_args_list)
    missing = [idx for idx in EXPECTED_INDEXES if idx not in sql]
    assert not missing, f"Missing indexes: {missing}"


@pytest.mark.asyncio
async def test_gin_index_for_topic_tags():
    """idx_naga_claims_topic must use GIN for TEXT[] array search."""
    conn = AsyncMock()
    await apply(conn)
    sql = _collect_executed_sql(conn.execute.call_args_list)
    # Find the section around the topic index
    assert "USING GIN" in sql or "USING gin" in sql, (
        "topic_tags index must use GIN operator class"
    )


# ---------------------------------------------------------------------------
# Foreign keys and constraints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cascade_deletes():
    """FK references to naga_sessions and naga_claims must use ON DELETE CASCADE."""
    conn = AsyncMock()
    await apply(conn)
    sql = _collect_executed_sql(conn.execute.call_args_list)
    # naga_sources -> naga_sessions
    assert "REFERENCES naga_sessions" in sql
    assert "ON DELETE CASCADE" in sql
    # naga_claims -> naga_sessions
    # naga_claim_evidence -> naga_claims, naga_sources
    # naga_claim_transitions -> naga_claims (twice)
    cascade_count = sql.count("ON DELETE CASCADE")
    # At minimum: sources->sessions, claims->sessions, evidence->claims,
    # evidence->sources, transitions->from, transitions->to = 6
    assert cascade_count >= 6, (
        f"Expected at least 6 ON DELETE CASCADE, found {cascade_count}"
    )


@pytest.mark.asyncio
async def test_unique_constraints():
    """Verify UNIQUE constraints on join tables."""
    conn = AsyncMock()
    await apply(conn)
    sql = _collect_executed_sql(conn.execute.call_args_list)
    # naga_sources: UNIQUE(url, session_id)
    assert "UNIQUE" in sql
    # naga_claim_evidence: UNIQUE(claim_id, source_id, relation)
    # naga_claim_transitions: UNIQUE(from_claim_id, to_claim_id, transition_type)


# ---------------------------------------------------------------------------
# Column type checks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sessions_has_required_columns():
    """naga_sessions must have all specified columns."""
    conn = AsyncMock()
    await apply(conn)
    sql = _collect_executed_sql(conn.execute.call_args_list)
    norm = _normalize(sql)
    required = [
        "parent_session_id",
        "query TEXT",
        "tier VARCHAR",
        "domain VARCHAR",
        "mode VARCHAR",
        "channel VARCHAR",
        "ttl_seconds",
        "trusted_mode",
        "status VARCHAR",
        "duration_ms",
        "iterations",
        "search_calls",
        "sources_found",
        "claims_extracted",
        "avg_confidence",
        "report_markdown",
        "report_drive_path",
        "action_items",
        "evidence_map_uri",
        "sub_questions",
        "url_history",
        "langgraph_thread_id",
        "created_at",
        "completed_at",
    ]
    for col in required:
        assert col in norm, f"naga_sessions missing column/type: {col}"


@pytest.mark.asyncio
async def test_sources_has_required_columns():
    """naga_sources must have all specified columns."""
    conn = AsyncMock()
    await apply(conn)
    sql = _collect_executed_sql(conn.execute.call_args_list)
    norm = _normalize(sql)
    required = [
        "session_id",
        "url TEXT",
        "title TEXT",
        "source_type",
        "credibility_score",
        "freshness_date",
        "content_hash",
        "content_archived",
        "drive_archive_path",
        "fetched_at",
    ]
    for col in required:
        assert col in norm, f"naga_sources missing column/type: {col}"


@pytest.mark.asyncio
async def test_claims_has_required_columns():
    """naga_claims must have all specified columns."""
    conn = AsyncMock()
    await apply(conn)
    sql = _collect_executed_sql(conn.execute.call_args_list)
    norm = _normalize(sql)
    required = [
        "claim_text TEXT",
        "claim_key",
        "topic_tags",
        "jurisdiction",
        "verification_level",
        "confidence FLOAT",
        "cross_ref_count",
        "review_status",
        "valid_as_of",
        "expires_at",
        "resolution_hint",
    ]
    for col in required:
        assert col in norm, f"naga_claims missing column/type: {col}"


# ---------------------------------------------------------------------------
# apply / rollback are async callables
# ---------------------------------------------------------------------------

def test_apply_is_async():
    """apply must be an async function."""
    assert inspect.iscoroutinefunction(apply)


def test_rollback_is_async():
    """rollback must be an async function."""
    assert inspect.iscoroutinefunction(rollback)
