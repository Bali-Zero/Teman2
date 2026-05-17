"""Integrity gates for legal/regulatory ingestion."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_preflight_rejects_process_env_shadowing_env_file() -> None:
    """Local shell QDRANT_URL must not silently override a different .env target."""
    from backend.services.ingestion.legal_ingestion_service import (
        LegalIngestIntegrityError,
        LegalIngestPreflight,
        validate_legal_ingest_preflight,
    )

    preflight = LegalIngestPreflight(
        configured_qdrant_url="https://shell-qdrant.example",
        process_qdrant_url="https://shell-qdrant.example",
        env_file_qdrant_url="https://dotenv-qdrant.example",
        requested_collection="legal_unified",
        resolved_collection="legal_unified_hybrid_hybrid",
        allow_process_env_override=False,
        environment="development",
    )

    with pytest.raises(LegalIngestIntegrityError, match="QDRANT_URL source conflict"):
        validate_legal_ingest_preflight(preflight)


def test_preflight_allows_explicit_process_env_override() -> None:
    """Canary/Fly-style explicit env override is source-based, not host allowlisted."""
    from backend.services.ingestion.legal_ingestion_service import (
        LegalIngestPreflight,
        validate_legal_ingest_preflight,
    )

    preflight = LegalIngestPreflight(
        configured_qdrant_url="https://canary-qdrant.example",
        process_qdrant_url="https://canary-qdrant.example",
        env_file_qdrant_url="https://dotenv-qdrant.example",
        requested_collection="legal_unified",
        resolved_collection="legal_unified_hybrid_hybrid",
        allow_process_env_override=True,
        environment="development",
    )

    validate_legal_ingest_preflight(preflight)


def test_preflight_rejects_wrong_target_collection() -> None:
    """Legal/regulatory ingestion must only target the legal collection family."""
    from backend.services.ingestion.legal_ingestion_service import (
        LegalIngestIntegrityError,
        LegalIngestPreflight,
        validate_legal_ingest_preflight,
    )

    preflight = LegalIngestPreflight(
        configured_qdrant_url="http://localhost:6333",
        process_qdrant_url="http://localhost:6333",
        env_file_qdrant_url="http://localhost:6333",
        requested_collection="visa_oracle",
        resolved_collection="visa_oracle",
        allow_process_env_override=False,
        environment="development",
    )

    with pytest.raises(LegalIngestIntegrityError, match="target collection"):
        validate_legal_ingest_preflight(preflight)


def test_validate_legal_ingest_result_rejects_failed_service_result() -> None:
    from backend.services.ingestion.legal_ingestion_service import (
        LegalIngestIntegrityError,
        validate_legal_ingest_result,
    )

    with pytest.raises(LegalIngestIntegrityError, match="failed"):
        validate_legal_ingest_result(
            {"success": False, "chunks_created": 0, "error": "parse failed"}
        )


def test_validate_legal_ingest_result_rejects_zero_chunks() -> None:
    from backend.services.ingestion.legal_ingestion_service import (
        LegalIngestIntegrityError,
        validate_legal_ingest_result,
    )

    with pytest.raises(LegalIngestIntegrityError, match="zero chunks"):
        validate_legal_ingest_result({"success": True, "chunks_created": 0})


def test_validate_legal_ingest_result_rejects_zero_upserts() -> None:
    from backend.services.ingestion.legal_ingestion_service import (
        LegalIngestIntegrityError,
        validate_legal_ingest_result,
    )

    with pytest.raises(LegalIngestIntegrityError, match="zero upserts"):
        validate_legal_ingest_result(
            {"success": True, "chunks_created": 3, "chunks_upserted": 0}
        )


@pytest.mark.asyncio
async def test_hierarchical_indexer_rejects_zero_qdrant_upserts() -> None:
    from backend.core.legal.hierarchical_indexer import HierarchicalChunk, HierarchicalIndexer

    qdrant = MagicMock()
    qdrant.upsert_documents = AsyncMock(
        return_value={"success": True, "documents_added": 0, "collection": "legal_unified"}
    )
    indexer = HierarchicalIndexer(
        structure_parser=MagicMock(),
        qdrant_client=qdrant,
        embeddings=MagicMock(),
    )
    chunk = HierarchicalChunk(
        chunk_id="PP_123_2024_Pasal_1",
        text="Pasal 1 text",
        document_id="PP_123_2024",
        chapter_id=None,
        section_id=None,
        article_id="PP_123_2024_Pasal_1",
        hierarchy_path="PP_123_2024/Pasal_1",
        hierarchy_level=3,
        parent_chunk_ids=["PP_123_2024"],
        sibling_chunk_ids=[],
        bab_title=None,
        bab_full_text=None,
        metadata={"legal_type": "PP"},
    )

    with pytest.raises(RuntimeError, match="zero upserts"):
        await indexer._upsert_hierarchical_chunks([chunk], [[0.1] * 1536])

    qdrant.upsert_documents.assert_awaited_once()
    assert qdrant.upsert_documents.await_args.kwargs["flatten_payload"] is True


@pytest.mark.asyncio
async def test_worker_fails_job_when_ingest_result_has_zero_chunks() -> None:
    """Worker must not advance zero-chunk jobs to qdrant_done/Drive."""
    from backend.services.ingestion import legal_full_ingestion_worker as worker

    job = {
        "id": "job-zero",
        "tipo": "PP",
        "nomor": "123",
        "anno": "2024",
        "source_url": "https://example.test/doc.pdf",
        "nb_target": "NB-3",
        "titolo": "PP 123/2024",
        "status": "pending",
    }

    class _AsyncTx:
        async def __aenter__(self) -> None:
            return None

        async def __aexit__(self, *_exc: object) -> bool:
            return False

    class _Acquire:
        def __init__(self, conn: AsyncMock) -> None:
            self._conn = conn

        async def __aenter__(self) -> AsyncMock:
            return self._conn

        async def __aexit__(self, *_exc: object) -> bool:
            return False

    conn = AsyncMock()
    conn.transaction = MagicMock(return_value=_AsyncTx())
    db_pool = MagicMock()
    db_pool.acquire.return_value = _Acquire(conn)

    service = MagicMock()
    service.ingest_legal_document = AsyncMock(
        return_value={"success": True, "chunks_created": 0}
    )

    with patch.object(worker, "_claim_job", new=AsyncMock(return_value=job)), \
         patch.object(worker, "_download_pdf", new=AsyncMock(return_value=MagicMock())), \
         patch(
             "backend.services.ingestion.legal_ingestion_service.LegalIngestionService",
             return_value=service,
         ), \
         patch.object(worker, "_build_drive_service") as build_drive:
        await worker._process_one_job(db_pool, MagicMock())

    build_drive.assert_not_called()
    execute_calls = conn.execute.call_args_list
    assert any("status = $2" in call.args[0] and "failed" in call.args for call in execute_calls)
    assert not any("qdrant_done" in call.args for call in execute_calls)
