"""Tests for client_doc_indexer — CRM→Qdrant per-client document indexer.

Two units under test, both dependency-injected so tests use lightweight mocks
(no live Postgres, no live Qdrant, no live OpenAI):

- enqueue_index_job(conn, document_id, client_id, file_id, content_hash)
    Idempotent: ON CONFLICT (document_id, content_hash) DO NOTHING.

- index_pending_job(conn, qdrant, embedder, job)
    Reads OCR text already in documents.ocr_extracted_data, chunks it, embeds,
    upserts to the `client_documents` collection with a FLAT client_id payload,
    and transitions the job to indexed_active.

The PII isolation invariant (query for client A never returns client B chunks)
is enforced by putting client_id in every point's payload and is covered by
test_point_payload_carries_client_id_for_isolation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


# --------------------------------------------------------------------------
# enqueue_index_job
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enqueue_inserts_pending_job() -> None:
    from backend.services.crm.client_doc_indexer import enqueue_index_job

    conn = AsyncMock()
    await enqueue_index_job(
        conn,
        document_id=42,
        client_id=7,
        file_id="drive-abc",
        content_hash="hash123",
    )

    assert conn.execute.await_count == 1
    sql = conn.execute.await_args.args[0]
    assert "INSERT INTO document_index_jobs" in sql
    # Idempotency at the write site, matching the UNIQUE constraint.
    assert "ON CONFLICT (document_id, content_hash) DO NOTHING" in sql
    # Bound params carry the identifying tuple.
    assert conn.execute.await_args.args[1:] == (42, 7, "drive-abc", "hash123")


# --------------------------------------------------------------------------
# index_pending_job
# --------------------------------------------------------------------------

def _job(**over):
    base = {
        "id": 1,
        "document_id": 42,
        "client_id": 7,
        "file_id": "drive-abc",
        "content_hash": "hash123",
    }
    base.update(over)
    return base


@pytest.mark.asyncio
async def test_index_job_embeds_ocr_text_and_upserts_to_qdrant() -> None:
    from backend.services.crm.client_doc_indexer import index_pending_job

    conn = AsyncMock()
    # documents.ocr_extracted_data holds the already-extracted text.
    conn.fetchrow.return_value = {"ocr_extracted_data": {"text": "passport line one. line two."}}

    embedder = AsyncMock()
    embedder.generate_embeddings.return_value = [[0.1] * 1536]

    qdrant = AsyncMock()

    await index_pending_job(conn, qdrant, embedder, _job())

    # It embedded the OCR text (not a download).
    embedder.generate_embeddings.assert_awaited_once()
    # It upserted to Qdrant with flat payload.
    qdrant.upsert_documents.assert_awaited_once()
    kwargs = qdrant.upsert_documents.await_args.kwargs
    assert kwargs.get("flatten_payload") is True


@pytest.mark.asyncio
async def test_point_payload_carries_client_id_for_isolation() -> None:
    """PII isolation invariant: every point payload tags client_id + state."""
    from backend.services.crm.client_doc_indexer import index_pending_job

    conn = AsyncMock()
    conn.fetchrow.return_value = {"ocr_extracted_data": {"text": "some doc text"}}
    embedder = AsyncMock()
    embedder.generate_embeddings.return_value = [[0.2] * 1536]
    qdrant = AsyncMock()

    await index_pending_job(conn, qdrant, embedder, _job(client_id=7, document_id=42))

    metadatas = qdrant.upsert_documents.await_args.kwargs["metadatas"]
    assert all(m["client_id"] == 7 for m in metadatas)
    assert all(m["document_id"] == 42 for m in metadatas)
    assert all(m["state"] == "indexed_active" for m in metadatas)


@pytest.mark.asyncio
async def test_index_job_transitions_status_to_indexed_active() -> None:
    from backend.services.crm.client_doc_indexer import index_pending_job

    conn = AsyncMock()
    conn.fetchrow.return_value = {"ocr_extracted_data": {"text": "text"}}
    embedder = AsyncMock()
    embedder.generate_embeddings.return_value = [[0.3] * 1536]
    qdrant = AsyncMock()

    await index_pending_job(conn, qdrant, embedder, _job(id=99))

    # Final UPDATE flips the job to indexed_active.
    update_calls = [
        c for c in conn.execute.await_args_list
        if c.args and "UPDATE document_index_jobs" in c.args[0]
    ]
    assert update_calls, "expected an UPDATE on document_index_jobs"
    assert any("indexed_active" in c.args[0] for c in update_calls)


@pytest.mark.asyncio
async def test_index_job_with_empty_ocr_text_marks_failed_not_crash() -> None:
    from backend.services.crm.client_doc_indexer import index_pending_job

    conn = AsyncMock()
    conn.fetchrow.return_value = {"ocr_extracted_data": {"text": ""}}
    embedder = AsyncMock()
    qdrant = AsyncMock()

    await index_pending_job(conn, qdrant, embedder, _job())

    # No embedding / no upsert on empty text.
    embedder.generate_embeddings.assert_not_awaited()
    qdrant.upsert_documents.assert_not_awaited()
    # Job marked failed, not left dangling.
    assert any(
        c.args and "UPDATE document_index_jobs" in c.args[0] and "failed" in c.args[0]
        for c in conn.execute.await_args_list
    )
