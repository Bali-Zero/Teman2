"""Tests for the OCR-completed → client_doc_indexer enqueue hook.

The hook lives in ocr_dispatcher_service alongside the existing KG-link hook.
It is best-effort and total-swallow: indexing is a derived view and must NEVER
make an OCR caller think the upload failed (same contract as kg_link).

L2 critical-path guard: the second test proves a crash in enqueue does not
propagate out of the hook.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _pool_with_conn(conn: AsyncMock) -> MagicMock:
    """Build a db_pool whose `async with pool.acquire() as conn` yields `conn`.

    `acquire()` is sync-returns an async context manager (asyncpg semantics),
    so it must be a MagicMock returning an object with async __aenter__/__aexit__.
    """
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=cm)
    return pool


@pytest.mark.asyncio
async def test_hook_enqueues_index_job_after_ocr_with_doc_id() -> None:
    from backend.services.documents.ocr_dispatcher_service import (
        _enqueue_client_doc_index_after_ocr,
    )

    conn = AsyncMock()
    # documents row carries the content_hash already computed by DrivePoll.
    conn.fetchrow.return_value = {"content_hash": "md5abc"}
    db_pool = _pool_with_conn(conn)

    with patch(
        "backend.services.crm.client_doc_indexer.enqueue_index_job",
        new=AsyncMock(),
    ) as mock_enqueue:
        await _enqueue_client_doc_index_after_ocr(
            db_pool,
            file_id="drive-xyz",
            client_id=7,
            doc_id=42,
        )

    mock_enqueue.assert_awaited_once()
    kwargs = mock_enqueue.await_args.kwargs
    assert kwargs["document_id"] == 42
    assert kwargs["client_id"] == 7
    assert kwargs["file_id"] == "drive-xyz"
    assert kwargs["content_hash"] == "md5abc"


@pytest.mark.asyncio
async def test_hook_swallows_enqueue_failure_never_propagates() -> None:
    """L2 guard: a crash in enqueue must NOT escape the hook (OCR stays green)."""
    from backend.services.documents.ocr_dispatcher_service import (
        _enqueue_client_doc_index_after_ocr,
    )

    conn = AsyncMock()
    conn.fetchrow.return_value = {"content_hash": "md5abc"}
    db_pool = _pool_with_conn(conn)

    with patch(
        "backend.services.crm.client_doc_indexer.enqueue_index_job",
        new=AsyncMock(side_effect=RuntimeError("qdrant down")),
    ):
        # Must not raise.
        await _enqueue_client_doc_index_after_ocr(
            db_pool,
            file_id="drive-xyz",
            client_id=7,
            doc_id=42,
        )


@pytest.mark.asyncio
async def test_hook_noop_when_doc_id_missing() -> None:
    """No doc_id → nothing to index (can't map to a documents row)."""
    from backend.services.documents.ocr_dispatcher_service import (
        _enqueue_client_doc_index_after_ocr,
    )

    db_pool = AsyncMock()

    with patch(
        "backend.services.crm.client_doc_indexer.enqueue_index_job",
        new=AsyncMock(),
    ) as mock_enqueue:
        await _enqueue_client_doc_index_after_ocr(
            db_pool,
            file_id="drive-xyz",
            client_id=7,
            doc_id=None,
        )

    mock_enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_kg_link_hook_triggers_index_enqueue() -> None:
    """Wiring: _kg_link_after_ocr fires the index enqueue for every OCR branch."""
    from backend.services.documents import ocr_dispatcher_service as svc

    conn = AsyncMock()
    conn.fetchrow.return_value = {"content_hash": "md5abc"}
    db_pool = _pool_with_conn(conn)

    with patch.object(
        svc, "_enqueue_client_doc_index_after_ocr", new=AsyncMock()
    ) as mock_enqueue, patch.object(svc, "_kg_enabled", return_value=False):
        await svc._kg_link_after_ocr(
            db_pool,
            file_id="drive-xyz",
            client_id=7,
            doc_type="passport",
            handler_result={"success": True, "extracted": {}},
            doc_id=42,
            filename="passport.pdf",
        )

    mock_enqueue.assert_awaited_once()
    assert mock_enqueue.await_args.kwargs["doc_id"] == 42
    assert mock_enqueue.await_args.kwargs["client_id"] == 7
