"""Tests for migration 125: document_index_jobs table.

Drives the CRM→Qdrant per-client document indexing queue. A row is enqueued
when a document's OCR completes; an indexer worker consumes it and upserts
the document chunks into the `client_documents` Qdrant collection.

Idempotency is enforced at the DB level by UNIQUE(document_id, content_hash):
the same document content can never be enqueued twice.
"""

from __future__ import annotations

import re
from unittest.mock import AsyncMock

import pytest


def _collect_sql(calls) -> str:
    return "\n".join(call.args[0] for call in calls if call.args)


@pytest.mark.asyncio
async def test_migration_125_creates_document_index_jobs_table() -> None:
    from backend.migrations.migration_125_document_index_jobs import apply

    conn = AsyncMock()
    await apply(conn)
    sql = _collect_sql(conn.execute.call_args_list)

    assert "CREATE TABLE IF NOT EXISTS document_index_jobs" in sql
    # core columns the indexer worker reads/writes
    assert "document_id" in sql
    assert "client_id" in sql
    assert "file_id" in sql
    assert "content_hash" in sql
    assert "status" in sql
    assert "attempts" in sql
    # FK to the documents table the OCR pipeline already populates
    assert "REFERENCES documents(id)" in sql


@pytest.mark.asyncio
async def test_migration_125_idempotency_unique_and_status_states() -> None:
    from backend.migrations.migration_125_document_index_jobs import apply

    conn = AsyncMock()
    await apply(conn)
    sql = _collect_sql(conn.execute.call_args_list)

    # Idempotency: same document content can never be enqueued twice.
    assert "UNIQUE (document_id, content_hash)" in sql
    # State machine the worker drives.
    assert "'pending'" in sql
    assert "'indexing'" in sql
    assert "'indexed_active'" in sql
    assert "'soft_deleted'" in sql


@pytest.mark.asyncio
async def test_migration_125_indexes_are_idempotent_and_claimable() -> None:
    from backend.migrations.migration_125_document_index_jobs import apply

    conn = AsyncMock()
    await apply(conn)
    sql = _collect_sql(conn.execute.call_args_list)

    # Worker claims pending jobs — needs an index to do it cheaply.
    assert "idx_document_index_jobs_claimable" in sql
    all_create_idx = re.findall(r"CREATE INDEX", sql)
    all_if_not_exists = re.findall(r"CREATE INDEX IF NOT EXISTS", sql)
    assert len(all_create_idx) > 0
    assert len(all_create_idx) == len(all_if_not_exists)


@pytest.mark.asyncio
async def test_migration_125_rollback_drops_table_and_indexes() -> None:
    from backend.migrations.migration_125_document_index_jobs import rollback

    conn = AsyncMock()
    await rollback(conn)
    sql = _collect_sql(conn.execute.call_args_list)

    assert "DROP TABLE IF EXISTS document_index_jobs" in sql
    assert "DROP INDEX IF EXISTS idx_document_index_jobs_claimable" in sql
