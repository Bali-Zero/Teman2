"""
Unit tests for LegalIngestionService.
Covers: init, ingest_legal_document (success, error, OCR fallback, pricing skip),
_ensure_drive_folder_exists, _get_kg_extractor, detect_legal_document.
"""

from __future__ import annotations

import hashlib
import os
from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

if TYPE_CHECKING:
    from backend.services.ingestion.legal_ingestion_service import LegalIngestionService

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("API_KEYS", "test_api_key_1")
os.environ.setdefault("OPENAI_API_KEY", "test_key")
os.environ.setdefault("GOOGLE_API_KEY", "test_key")


def _build_service() -> LegalIngestionService:
    """Build LegalIngestionService with all heavy dependencies mocked."""
    with (
        patch("backend.services.ingestion.legal_ingestion_service.LegalCleaner") as mc,
        patch("backend.services.ingestion.legal_ingestion_service.LegalMetadataExtractor") as mme,
        patch("backend.services.ingestion.legal_ingestion_service.LegalStructureParser") as msp,
        patch("backend.services.ingestion.legal_ingestion_service.LegalChunker") as mch,
        patch("backend.services.ingestion.legal_ingestion_service.BM25Vectorizer") as mbm,
        patch(
            "backend.services.ingestion.legal_ingestion_service.create_embeddings_generator"
        ) as mce,
        patch(
            "backend.services.ingestion.legal_ingestion_service.resolve_collection_name",
            return_value="legal_unified",
        ),
        patch("backend.services.ingestion.legal_ingestion_service.QdrantClient") as mqd,
        patch("backend.services.ingestion.legal_ingestion_service.TierClassifier") as mtc,
        patch("backend.services.ingestion.legal_ingestion_service.HierarchicalIndexer") as mhi,
    ):
        mc.return_value = MagicMock()
        mme.return_value = MagicMock()
        msp.return_value = MagicMock()
        mch.return_value = MagicMock()
        mbm.return_value = MagicMock()
        mce.return_value = MagicMock()
        # The identity-collision guard scrolls for points already holding the
        # computed document_id before anything is written. The default world for
        # these tests is "nothing there yet"; tests that need a pre-existing
        # document override scroll_strict themselves.
        _vector_db = MagicMock()
        _vector_db.scroll_strict = AsyncMock(return_value=[])
        mqd.return_value = _vector_db
        mtc.return_value = MagicMock()
        mhi.return_value = MagicMock()

        from backend.services.ingestion.legal_ingestion_service import LegalIngestionService

        svc = LegalIngestionService(collection_name="legal_unified")
        return svc


@pytest.fixture
def service():
    return _build_service()


@pytest.fixture(autouse=True)
def _source_file_bytes():
    """Parser mocks still need stable source bytes for content-bound identities."""
    with patch(
        "backend.services.ingestion.legal_ingestion_service.Path.read_bytes",
        return_value=b"unit-test-legal-source",
    ):
        yield


def _common_ingest_patches():
    """Return the patches commonly needed for ingest_legal_document tests."""
    return (
        patch(
            "backend.services.ingestion.legal_ingestion_service.auto_detect_and_parse",
            return_value="raw legal text content here",
        ),
        patch("backend.services.ingestion.legal_ingestion_service.ingestion_logger"),
        patch("backend.services.ingestion.legal_ingestion_service.metrics_collector"),
        patch(
            "backend.services.ingestion.legal_ingestion_service.resolve_collection_name",
            return_value="legal_unified",
        ),
    )


# --------------------------------------------------------------------------- #
# Initialization
# --------------------------------------------------------------------------- #


class TestInit:
    def test_init_creates_components(self, service: MagicMock) -> None:
        assert service.cleaner is not None
        assert service.metadata_extractor is not None
        assert service.structure_parser is not None
        assert service.chunker is not None
        assert service.sparse_vectorizer is not None
        assert service.embedder is not None
        assert service.vector_db is not None
        assert service.classifier is not None
        assert service.indexer is not None
        assert service.kg_enabled is False


# --------------------------------------------------------------------------- #
# detect_legal_document
# --------------------------------------------------------------------------- #


class TestDetectLegalDocument:
    def test_delegates_to_metadata_extractor(self, service: MagicMock) -> None:
        service.metadata_extractor.is_legal_document.return_value = True
        assert service.detect_legal_document("UNDANG-UNDANG NOMOR 6 TAHUN 2023") is True
        service.metadata_extractor.is_legal_document.assert_called_once()

    def test_not_legal(self, service: MagicMock) -> None:
        service.metadata_extractor.is_legal_document.return_value = False
        assert service.detect_legal_document("random text") is False


# --------------------------------------------------------------------------- #
# ingest_legal_document -- success path
# --------------------------------------------------------------------------- #


class TestIngestSuccess:
    @pytest.mark.asyncio
    async def test_basic_ingestion(self, service: MagicMock) -> None:
        service.cleaner.clean.return_value = "cleaned text with enough content for testing"
        service.metadata_extractor.extract.return_value = {
            "type": "Undang-Undang",
            "type_abbrev": "UU",
            "number": "6",
            "year": "2023",
            "topic": "Immigration",
            "status": "active",
            "full_title": "UU 6/2023 tentang Imigrasi",
        }
        service.classifier.classify_book_tier.return_value = MagicMock(value="golden")
        service.classifier.get_min_access_level.return_value = "member"
        service.indexer.index_legal_document = AsyncMock(
            return_value={
                "chunks_indexed": 10,
                "parent_documents": 3,
                "total_bab": 2,
                "total_pasal": 8,
            }
        )

        p1, p2, p3, p4 = _common_ingest_patches()
        with p1, p2 as mock_logger, p3, p4:
            mock_logger.start_ingestion.return_value = "doc_001"

            result = await service.ingest_legal_document(
                file_path="/tmp/test.pdf",
                title="UU 6/2023",
                category="01_immigrazione",
            )

            assert result["success"] is True
            assert result["chunks_created"] == 10
            assert result["tier"] == "golden"
            assert result["legal_metadata"]["type_abbrev"] == "UU"

    @pytest.mark.asyncio
    async def test_archives_in_dedicated_legal_root_idempotently(
        self, service: MagicMock
    ) -> None:
        service.cleaner.clean.return_value = "cleaned legal text"
        service.metadata_extractor.extract.return_value = {
            "type": "Peraturan Presiden",
            "type_abbrev": "Perpres",
            "number": "43",
            "year": "2011",
            "topic": "Test",
            "status": None,
            "full_title": "Perpres 43/2011",
        }
        service.classifier.classify_book_tier.return_value = MagicMock(value="golden")
        service.classifier.get_min_access_level.return_value = "member"
        service.indexer.index_legal_document = AsyncMock(
            return_value={
                "chunks_indexed": 2,
                "chunks_upserted": 2,
                "parent_documents": 1,
                "total_bab": 0,
                "total_pasal": 2,
            }
        )
        drive = MagicMock()
        drive.archive_file_idempotent = AsyncMock(
            return_value=(
                {
                "id": "drive_file_43",
                "webViewLink": "https://drive.example/43",
                "md5Checksum": hashlib.md5(b"archive source").hexdigest(),
                },
                "reused",
            )
        )
        archive_pool = MagicMock()
        service.indexer._get_db_pool = AsyncMock(return_value=archive_pool)
        legal_settings = SimpleNamespace(
            legal_drive_root_folder_id="legal_root",
            legal_drive_impersonate_user="legal-archive@example.com",
            google_drive_root_folder_id="generic_root",
        )
        p1, p2, p3, p4 = _common_ingest_patches()
        with (
            p1,
            p2 as mock_logger,
            p3,
            p4,
            patch(
                "backend.services.ingestion.legal_ingestion_service.ServiceAccountDriveService",
                return_value=drive,
            ) as service_account_cls,
            patch("backend.app.core.config.settings", legal_settings),
            patch(
                "backend.services.ingestion.legal_ingestion_service.Path.read_bytes",
                return_value=b"archive source",
            ),
        ):
            mock_logger.start_ingestion.return_value = "doc_legal_root"
            result = await service.ingest_legal_document(file_path="/tmp/perpres_43_2011.pdf")

        assert result["success"] is True
        assert result["drive_archive"]["status"] == "reused"
        service_account_cls.assert_called_once_with(
            root_folder_id="legal_root",
            delegated_user="legal-archive@example.com",
        )
        drive.archive_file_idempotent.assert_awaited_once_with(
            folder_id="legal_root",
            file_content=b"archive source",
            file_name="perpres_43_2011.pdf",
            mime_type="application/pdf",
            db_pool=archive_pool,
            require_distributed_lock=False,
        )
        metadata = service.indexer.index_legal_document.await_args.kwargs["metadata"]
        assert metadata["drive_file_id"] == "drive_file_43"

    @pytest.mark.asyncio
    async def test_historical_source_is_namespaced_and_has_a_retrieval_guard(
        self, service: MagicMock
    ) -> None:
        service.cleaner.clean.return_value = "cleaned legal text"
        service.metadata_extractor.extract.return_value = {
            "type": "Peraturan Presiden",
            "type_abbrev": "Perpres",
            "number": "43",
            "year": "2011",
            "topic": "Test",
            "status": None,
            "full_title": "Perpres 43/2011",
        }
        service.classifier.classify_book_tier.return_value = MagicMock(value="golden")
        service.classifier.get_min_access_level.return_value = "member"
        service.indexer.index_legal_document = AsyncMock(
            return_value={
                "chunks_indexed": 2,
                "chunks_upserted": 2,
                "parent_documents": 1,
                "total_bab": 0,
                "total_pasal": 2,
            }
        )
        service.vector_db.ensure_keyword_payload_index = AsyncMock()
        service.vector_db.scroll_strict = AsyncMock(
            return_value=[
                {
                    "id": "old-current-point",
                    "payload": {"document_id": "Perpres_43_2011"},
                }
            ]
        )
        service.vector_db.set_payload_by_filter = AsyncMock()
        service.vector_db.delete_by_filter = AsyncMock(
            return_value={"success": True}
        )
        archive_pool = MagicMock()
        service.indexer._get_db_pool = AsyncMock(return_value=archive_pool)
        drive = MagicMock()
        drive.archive_file_idempotent = AsyncMock(
            return_value=(
                {
                    "id": "drive_file_43",
                    "webViewLink": "https://drive.example/43",
                    "md5Checksum": hashlib.md5(b"unit-test-legal-source").hexdigest(),
                },
                "reused",
            )
        )
        legal_settings = SimpleNamespace(
            legal_drive_root_folder_id="legal_root",
            legal_drive_impersonate_user="legal-archive@example.com",
            google_drive_root_folder_id="generic_root",
        )
        p1, p2, p3, p4 = _common_ingest_patches()
        with (
            p1,
            p2 as mock_logger,
            p3,
            p4,
            patch(
                "backend.services.ingestion.legal_ingestion_service.ServiceAccountDriveService",
                return_value=drive,
            ),
            patch("backend.app.core.config.settings", legal_settings),
        ):
            mock_logger.start_ingestion.return_value = "doc_historical"
            result = await service.ingest_legal_document(
                file_path="/tmp/perpres_43_2011.pdf",
                retrieval_scope="historical_only",
                source_url="https://www.peraturan.go.id/id/perpres-no-43-tahun-2011",
                effective_date=date(2011, 7, 18),
                observed_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
            )

        assert result["success"] is True
        index_call = service.indexer.index_legal_document.await_args
        assert index_call.kwargs["document_id"] == "Perpres_43_2011__historical"
        assert index_call.kwargs["metadata"]["retrieval_scope"] == "historical_only"
        assert index_call.kwargs["metadata"]["source_url"].endswith("perpres-no-43-tahun-2011")
        service.vector_db.ensure_keyword_payload_index.assert_has_awaits(
            [call("retrieval_scope"), call("metadata.retrieval_scope")],
        )
        drive.archive_file_idempotent.assert_awaited_once()
        assert drive.archive_file_idempotent.await_args.kwargs["db_pool"] is archive_pool
        assert drive.archive_file_idempotent.await_args.kwargs["require_distributed_lock"] is True
        service.vector_db.set_payload_by_filter.assert_awaited_once_with(
            metadata_filter={"document_id": "Perpres_43_2011"},
            payload={"retrieval_scope": "historical_only"},
        )
        service.vector_db.delete_by_filter.assert_awaited_once_with(
            metadata_filter={"document_id": "Perpres_43_2011"},
        )

    @pytest.mark.asyncio
    async def test_historical_reclassification_quarantines_previous_current_points(
        self, service: MagicMock
    ) -> None:
        vector_db = MagicMock()
        vector_db.scroll_strict = AsyncMock(
            return_value=[
                {"id": "flat", "payload": {"document_id": "PP_1_2024"}},
                {
                    "id": "nested",
                    "payload": {
                        "metadata": {
                            "document_id": "PP_1_2024",
                            "source_url": "https://example.test/source",
                        }
                    },
                },
            ]
        )
        vector_db.set_payload_by_filter = AsyncMock()

        quarantined = await service._quarantine_current_points(vector_db, "PP_1_2024")

        assert quarantined == ["flat", "nested"]
        vector_db.set_payload_by_filter.assert_awaited_once_with(
            metadata_filter={"document_id": "PP_1_2024"},
            payload={"retrieval_scope": "historical_only"},
        )

    @pytest.mark.asyncio
    async def test_collection_override_uses_request_local_qdrant_client(
        self, service: MagicMock
    ) -> None:
        base_vector_db = service.vector_db
        base_indexer_qdrant = service.indexer.qdrant
        request_vector_db = MagicMock(collection_name="tax_genius")
        # Same as the shared fixture: the identity guard scrolls the
        # REQUEST-local client, so it needs an empty world too.
        request_vector_db.scroll_strict = AsyncMock(return_value=[])
        service.cleaner.clean.return_value = "cleaned tax regulation"
        service.metadata_extractor.extract.return_value = {
            "type": "Peraturan Menteri Keuangan",
            "type_abbrev": "PMK",
            "number": "1",
            "year": "2024",
            "topic": "Tax",
            "status": "active",
            "full_title": "PMK 1/2024",
        }
        service.classifier.classify_book_tier.return_value = MagicMock(value="golden")
        service.classifier.get_min_access_level.return_value = "member"
        service.indexer.index_legal_document = AsyncMock(
            return_value={
                "chunks_indexed": 1,
                "chunks_upserted": 1,
                "parent_documents": 0,
                "total_bab": 0,
                "total_pasal": 1,
            }
        )

        with (
            patch(
                "backend.services.ingestion.legal_ingestion_service.auto_detect_and_parse",
                return_value="raw tax regulation",
            ),
            patch(
                "backend.services.ingestion.legal_ingestion_service.ingestion_logger"
            ) as mock_logger,
            patch("backend.services.ingestion.legal_ingestion_service.metrics_collector"),
            patch(
                "backend.services.ingestion.legal_ingestion_service.resolve_collection_name",
                return_value="tax_genius",
            ),
            patch(
                "backend.services.ingestion.legal_ingestion_service.QdrantClient",
                return_value=request_vector_db,
            ),
        ):
            mock_logger.start_ingestion.return_value = "tax_request"
            result = await service.ingest_legal_document(
                file_path="/tmp/pmk.pdf",
                collection_name="tax_genius",
            )

        assert result["success"] is True
        assert service.vector_db is base_vector_db
        assert service.indexer.qdrant is base_indexer_qdrant
        assert (
            service.indexer.index_legal_document.await_args.kwargs["qdrant_client"]
            is request_vector_db
        )

    @pytest.mark.asyncio
    async def test_historical_ingestion_fails_when_archive_integrity_fails(
        self, service: MagicMock
    ) -> None:
        from backend.services.integrations.service_account_drive_service import (
            DriveArchiveIntegrityError,
        )

        service.vector_db.ensure_keyword_payload_index = AsyncMock()
        service.indexer._get_db_pool = AsyncMock(return_value=MagicMock())
        service.indexer.index_legal_document = AsyncMock()
        drive = MagicMock()
        drive.archive_file_idempotent = AsyncMock(
            side_effect=DriveArchiveIntegrityError("checksum mismatch")
        )
        legal_settings = SimpleNamespace(
            legal_drive_root_folder_id="legal_root",
            legal_drive_impersonate_user="legal-archive@example.com",
            google_drive_root_folder_id="generic_root",
        )
        p1, p2, p3, p4 = _common_ingest_patches()
        with (
            p1,
            p2 as mock_logger,
            p3,
            p4,
            patch(
                "backend.services.ingestion.legal_ingestion_service.ServiceAccountDriveService",
                return_value=drive,
            ),
            patch("backend.app.core.config.settings", legal_settings),
        ):
            mock_logger.start_ingestion.return_value = "bad_archive"
            result = await service.ingest_legal_document(
                file_path="/tmp/collision.pdf",
                retrieval_scope="historical_only",
            )

        assert result["success"] is False
        assert "archive integrity" in result["error"]
        service.indexer.index_legal_document.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_current_ingestion_reports_archive_collision_but_continues(
        self, service: MagicMock
    ) -> None:
        from backend.services.integrations.service_account_drive_service import (
            DriveArchiveIntegrityError,
        )

        service.cleaner.clean.return_value = "corrected current law"
        service.metadata_extractor.extract.return_value = {
            "type": "Peraturan Pemerintah",
            "type_abbrev": "PP",
            "number": "5",
            "year": "2024",
            "topic": "Correction",
            "status": "active",
            "full_title": "PP 5/2024",
        }
        service.classifier.classify_book_tier.return_value = MagicMock(value="golden")
        service.classifier.get_min_access_level.return_value = "member"
        service.indexer._get_db_pool = AsyncMock(return_value=MagicMock())
        service.indexer.index_legal_document = AsyncMock(
            return_value={
                "chunks_indexed": 1,
                "chunks_upserted": 1,
                "parent_documents": 0,
                "total_bab": 0,
                "total_pasal": 1,
            }
        )
        drive = MagicMock()
        drive.archive_file_idempotent = AsyncMock(
            side_effect=DriveArchiveIntegrityError("checksum mismatch")
        )
        legal_settings = SimpleNamespace(
            legal_drive_root_folder_id="legal_root",
            legal_drive_impersonate_user="legal-archive@example.com",
            google_drive_root_folder_id="generic_root",
        )
        p1, p2, p3, p4 = _common_ingest_patches()
        with (
            p1,
            p2 as mock_logger,
            p3,
            p4,
            patch(
                "backend.services.ingestion.legal_ingestion_service.ServiceAccountDriveService",
                return_value=drive,
            ),
            patch("backend.app.core.config.settings", legal_settings),
        ):
            mock_logger.start_ingestion.return_value = "current_correction"
            result = await service.ingest_legal_document(file_path="/tmp/PP_5_2024.pdf")

        assert result["success"] is True
        assert result["drive_archive"] == {
            "status": "failed",
            "reason": "archive_integrity",
        }
        service.indexer.index_legal_document.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_post_quarantine_failure_requires_human_review_without_rollback(
        self, service: MagicMock
    ) -> None:
        service.cleaner.clean.return_value = "historical source text"
        service.metadata_extractor.extract.return_value = {
            "type": "Peraturan Presiden",
            "type_abbrev": "Perpres",
            "number": "43",
            "year": "2011",
            "topic": "Historical source",
            "status": None,
            "full_title": "Perpres 43/2011",
        }
        service.classifier.classify_book_tier.return_value = MagicMock(value="golden")
        service.classifier.get_min_access_level.return_value = "member"
        service.indexer._get_db_pool = AsyncMock(return_value=MagicMock())
        service.indexer.index_legal_document = AsyncMock(
            side_effect=RuntimeError("embedding unavailable")
        )
        service.vector_db.ensure_keyword_payload_index = AsyncMock()
        service.vector_db.scroll_strict = AsyncMock(
            return_value=[{"id": "old-current", "payload": {}}]
        )
        service.vector_db.set_payload_by_filter = AsyncMock()
        service.vector_db.delete_by_filter = AsyncMock()
        drive = MagicMock()
        drive.archive_file_idempotent = AsyncMock(
            return_value=(
                {
                    "id": "archive-43",
                    "md5Checksum": hashlib.md5(b"unit-test-legal-source").hexdigest(),
                },
                "reused",
            )
        )
        legal_settings = SimpleNamespace(
            legal_drive_root_folder_id="legal_root",
            legal_drive_impersonate_user="legal-archive@example.com",
            google_drive_root_folder_id="generic_root",
        )
        p1, p2, p3, p4 = _common_ingest_patches()
        with (
            p1,
            p2 as mock_logger,
            p3,
            p4,
            patch(
                "backend.services.ingestion.legal_ingestion_service.ServiceAccountDriveService",
                return_value=drive,
            ),
            patch("backend.app.core.config.settings", legal_settings),
        ):
            mock_logger.start_ingestion.return_value = "failed_reconciliation"
            result = await service.ingest_legal_document(
                file_path="/tmp/perpres_43_2011.pdf",
                retrieval_scope="historical_only",
            )

        assert result["success"] is False
        assert result["reconciliation_status"] == "HUMAN_REVIEW_REQUIRED"
        assert result["current_scope_state"] == "QUARANTINED_OR_UNKNOWN"
        service.vector_db.set_payload_by_filter.assert_awaited_once_with(
            metadata_filter={"document_id": "Perpres_43_2011"},
            payload={"retrieval_scope": "historical_only"},
        )
        service.vector_db.delete_by_filter.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_ingestion_with_tier_override(self, service: MagicMock) -> None:
        service.cleaner.clean.return_value = "cleaned content"
        service.metadata_extractor.extract.return_value = {
            "type": "PP",
            "type_abbrev": "PP",
            "number": "1",
            "year": "2024",
            "topic": "Test",
            "status": None,
            "full_title": "PP 1/2024",
        }
        tier_mock = MagicMock(value="silver")
        service.classifier.get_min_access_level.return_value = "guest"
        service.indexer.index_legal_document = AsyncMock(
            return_value={
                "chunks_indexed": 5,
                "parent_documents": 1,
                "total_bab": 1,
                "total_pasal": 3,
            }
        )

        p1, p2, p3, p4 = _common_ingest_patches()
        with p1, p2 as mock_il, p3, p4:
            mock_il.start_ingestion.return_value = "doc_002"

            result = await service.ingest_legal_document(
                file_path="/tmp/test2.pdf",
                tier_override=tier_mock,
            )

            assert result["success"] is True
            assert result["tier"] == "silver"
            service.classifier.classify_book_tier.assert_not_called()

    @pytest.mark.asyncio
    async def test_ingestion_with_wrong_collection_override_fails(self, service: MagicMock) -> None:
        service.cleaner.clean.return_value = "cleaned"
        service.metadata_extractor.extract.return_value = {
            "type": "PERMEN",
            "type_abbrev": "PERMEN",
            "number": "10",
            "year": "2024",
            "topic": "Test",
            "status": None,
            "full_title": "PERMEN 10/2024",
        }
        service.classifier.classify_book_tier.return_value = MagicMock(value="bronze")
        service.classifier.get_min_access_level.return_value = "guest"
        service.indexer.index_legal_document = AsyncMock(
            return_value={
                "chunks_indexed": 3,
                "parent_documents": 1,
                "total_bab": 0,
                "total_pasal": 2,
            }
        )

        with (
            patch(
                "backend.services.ingestion.legal_ingestion_service.auto_detect_and_parse",
                return_value="raw text",
            ),
            patch("backend.services.ingestion.legal_ingestion_service.ingestion_logger") as mock_il,
            patch("backend.services.ingestion.legal_ingestion_service.metrics_collector"),
            patch(
                "backend.services.ingestion.legal_ingestion_service.resolve_collection_name",
                return_value="custom_collection",
            ),
            patch("backend.services.ingestion.legal_ingestion_service.QdrantClient"),
        ):
            mock_il.start_ingestion.return_value = "doc_003"

            result = await service.ingest_legal_document(
                file_path="/tmp/test3.pdf",
                collection_name="custom_collection",
            )

            assert result["success"] is False
            assert "target collection" in result["error"]

    @pytest.mark.asyncio
    async def test_ingestion_generates_document_id(self, service: MagicMock) -> None:
        """Test that document_id is auto-generated when not provided."""
        service.cleaner.clean.return_value = "text"
        service.metadata_extractor.extract.return_value = {
            "type": "UU",
            "type_abbrev": "UU",
            "number": "1",
            "year": "2024",
            "topic": "Test",
            "status": None,
            "full_title": "UU 1/2024",
        }
        service.classifier.classify_book_tier.return_value = MagicMock(value="bronze")
        service.classifier.get_min_access_level.return_value = "guest"
        service.indexer.index_legal_document = AsyncMock(
            return_value={
                "chunks_indexed": 1,
                "parent_documents": 1,
                "total_bab": 0,
                "total_pasal": 0,
            }
        )

        p1, p2, p3, p4 = _common_ingest_patches()
        with p1, p2 as mock_il, p3, p4:
            mock_il.start_ingestion.return_value = "auto_doc"

            result = await service.ingest_legal_document(file_path="/tmp/auto.pdf")
            assert result["success"] is True
            assert result["document_id"] == "auto_doc"


# --------------------------------------------------------------------------- #
# ingest_legal_document -- skip pricing
# --------------------------------------------------------------------------- #


class TestSkipPricing:
    @pytest.mark.asyncio
    async def test_skip_pricing_removes_lines(self, service: MagicMock) -> None:
        service.cleaner.clean.return_value = "Line 1\nBiaya Rp 500.000\nLine 3\nIDR 100\nLine 5"
        service.metadata_extractor.extract.return_value = {
            "type": "PP",
            "type_abbrev": "PP",
            "number": "1",
            "year": "2024",
            "topic": "Fees",
            "status": None,
            "full_title": "PP 1/2024",
        }
        service.classifier.classify_book_tier.return_value = MagicMock(value="golden")
        service.classifier.get_min_access_level.return_value = "member"
        service.indexer.index_legal_document = AsyncMock(
            return_value={
                "chunks_indexed": 2,
                "parent_documents": 1,
                "total_bab": 0,
                "total_pasal": 1,
            }
        )

        p1, p2, p3, p4 = _common_ingest_patches()
        with p1, p2 as mock_il, p3, p4:
            mock_il.start_ingestion.return_value = "doc_004"

            result = await service.ingest_legal_document(
                file_path="/tmp/test.pdf",
                skip_pricing=True,
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_skip_pricing_single_block(self, service: MagicMock) -> None:
        """Test skip pricing with text that has few newlines but lots of content."""
        long_block = "First sentence. Biaya IDR 500000 second. Third sentence." + "x" * 1000
        service.cleaner.clean.return_value = long_block
        service.metadata_extractor.extract.return_value = {
            "type": "PP",
            "type_abbrev": "PP",
            "number": "2",
            "year": "2024",
            "topic": "Fees",
            "status": None,
            "full_title": "PP 2/2024",
        }
        service.classifier.classify_book_tier.return_value = MagicMock(value="golden")
        service.classifier.get_min_access_level.return_value = "member"
        service.indexer.index_legal_document = AsyncMock(
            return_value={
                "chunks_indexed": 1,
                "parent_documents": 1,
                "total_bab": 0,
                "total_pasal": 0,
            }
        )

        p1, p2, p3, p4 = _common_ingest_patches()
        with p1, p2 as mock_il, p3, p4:
            mock_il.start_ingestion.return_value = "doc_005"

            result = await service.ingest_legal_document(
                file_path="/tmp/test.pdf",
                skip_pricing=True,
            )

            assert result["success"] is True


# --------------------------------------------------------------------------- #
# ingest_legal_document -- identity collision guard
# --------------------------------------------------------------------------- #


class TestIdentityCollisionGuard:
    """The incident of 2026-08-25, encoded.

    In production, `Permen_1_2026` held 544 points belonging to TWO unrelated
    laws: PMK 1/2026 (Ministry of Finance, Coretax) and Permen Imipas 1/2026
    (Ministry of Immigration). Every Indonesian ministry numbers its regulations
    from 1 each year, so the extracted (type, number, year) triple collapsed
    them onto one identity. Chunk ids are `{document_id}_Pasal_{n}` and point
    ids are `uuid5(chunk_id)`, so the second ingest OVERWROTE 50 chunks of the
    first. Qdrant reported a successful upsert, because it was one.

    A guard that only proves guilt is half a guard: the refresh case (the SAME
    document re-ingested) must still pass, or the corpus can never be updated.
    Both halves are asserted here.
    """

    @staticmethod
    def _coretax_metadata() -> dict:
        return {
            "type": "Peraturan Menteri",
            "type_abbrev": "Permen",
            "number": "1",
            "year": "2026",
            "topic": "Coretax",
            "status": None,
            "full_title": "PMK 1/2026",
        }

    def _prime(self, service: MagicMock, existing: list) -> None:
        service.cleaner.clean.return_value = "cleaned legal text"
        service.metadata_extractor.extract.return_value = self._coretax_metadata()
        service.classifier.classify_book_tier.return_value = MagicMock(value="golden")
        service.classifier.get_min_access_level.return_value = "member"
        service.indexer.index_legal_document = AsyncMock(
            return_value={
                "chunks_indexed": 4,
                "chunks_upserted": 4,
                "parent_documents": 1,
                "total_bab": 0,
                "total_pasal": 4,
            }
        )
        service.vector_db.scroll_strict = AsyncMock(return_value=existing)
        service.vector_db.set_payload_by_filter = AsyncMock()
        service.vector_db.delete_by_filter = AsyncMock()
        service.vector_db.ensure_keyword_payload_index = AsyncMock()

    @pytest.mark.asyncio
    async def test_guilt_a_second_document_on_a_held_identity_is_refused(
        self, service: MagicMock
    ) -> None:
        """The real collision: a DIFFERENT source file on an occupied identity."""
        self._prime(
            service,
            existing=[
                {
                    "id": "coretax-point",
                    "payload": {
                        "document_id": "Permen_1_2026",
                        "source_basename": "PMK_1_2026_Coretax_System.pdf",
                    },
                }
            ],
        )

        p1, p2, p3, p4 = _common_ingest_patches()
        with p1, p2 as mock_logger, p3, p4:
            mock_logger.start_ingestion.return_value = "trace_id"
            result = await service.ingest_legal_document(
                file_path="/tmp/PermenImipas_1_2026_Perubahan.pdf",
                title="Permen Imipas 1/2026",
                category="01_immigrazione",
            )

        assert result["success"] is False
        assert "identity collision" in str(result.get("error", "")).lower()
        # Nothing may be written, and nothing may be mutated: the guard runs
        # before the quarantine, which already rewrites payloads.
        service.indexer.index_legal_document.assert_not_awaited()
        service.vector_db.set_payload_by_filter.assert_not_awaited()
        service.vector_db.delete_by_filter.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_innocence_the_same_document_may_be_re_ingested(
        self, service: MagicMock
    ) -> None:
        """Refreshing a document is not a collision. It is the point of a corpus."""
        self._prime(
            service,
            existing=[
                {
                    "id": "coretax-point",
                    "payload": {
                        "document_id": "Permen_1_2026",
                        "source_basename": "PMK_1_2026_Coretax_System.pdf",
                    },
                }
            ],
        )

        p1, p2, p3, p4 = _common_ingest_patches()
        with p1, p2 as mock_logger, p3, p4:
            mock_logger.start_ingestion.return_value = "trace_id"
            result = await service.ingest_legal_document(
                file_path="/somewhere/else/PMK_1_2026_Coretax_System.pdf",
                title="PMK 1/2026",
                category="04_fiscale",
            )

        assert result["success"] is True
        service.indexer.index_legal_document.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_innocence_an_unclaimed_identity_passes(
        self, service: MagicMock
    ) -> None:
        self._prime(service, existing=[])

        p1, p2, p3, p4 = _common_ingest_patches()
        with p1, p2 as mock_logger, p3, p4:
            mock_logger.start_ingestion.return_value = "trace_id"
            result = await service.ingest_legal_document(
                file_path="/tmp/PMK_1_2026_Coretax_System.pdf",
                title="PMK 1/2026",
                category="04_fiscale",
            )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_absolute_path_alone_does_not_read_as_a_foreign_document(
        self, service: MagicMock
    ) -> None:
        """Legacy points carry an absolute `file_path`, which is machine-specific.

        The same file ingested from a worktree and from the checkout has two
        different absolute paths. Comparing those would refuse every legitimate
        re-ingest from a different machine, so the guard compares BASENAMES.
        """
        self._prime(
            service,
            existing=[
                {
                    "id": "legacy-point",
                    "payload": {
                        "document_id": "Permen_1_2026",
                        "file_path": "/Users/someone/else/PMK_1_2026_Coretax_System.pdf",
                    },
                }
            ],
        )

        p1, p2, p3, p4 = _common_ingest_patches()
        with p1, p2 as mock_logger, p3, p4:
            mock_logger.start_ingestion.return_value = "trace_id"
            result = await service.ingest_legal_document(
                file_path="/tmp/laws/PMK_1_2026_Coretax_System.pdf",
                title="PMK 1/2026",
                category="04_fiscale",
            )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_guilt_a_historical_ingest_may_not_delete_a_foreign_document(
        self, service: MagicMock
    ) -> None:
        """The historical path DELETES, so it must be guarded on what it deletes.

        A historical ingest writes to `X__historical` but quarantines and then
        deletes every point under `X`. Guarding only the write target leaves `X`
        uninspected: a historical ingest whose derived identity happens to match
        a different ministry's current-law document would pass the guard and
        then remove that document in full. That is strictly worse than the
        incident the guard was written for — 50 chunks overwritten there, an
        entire law deleted here, with the guard's blessing.
        """
        self._prime(service, existing=[])

        # The write target `Permen_1_2026__historical` is free; the identity the
        # delete will actually hit, `Permen_1_2026`, belongs to someone else.
        def _scroll(metadata_filter: dict, **_kwargs: object) -> list:
            if metadata_filter.get("document_id") == "Permen_1_2026":
                return [
                    {
                        "id": "foreign-current-point",
                        "payload": {
                            "document_id": "Permen_1_2026",
                            "source_basename": "PMK_1_2026_Coretax_System.pdf",
                        },
                    }
                ]
            return []

        service.vector_db.scroll_strict = AsyncMock(side_effect=_scroll)
        service.indexer._get_db_pool = AsyncMock(return_value=MagicMock())

        # Historical ingestion demands a verified Drive archive BEFORE the
        # identity is even known (STAGE 1.5 runs ahead of metadata extraction),
        # so the archive has to succeed for this test to reach the guard at all.
        drive = MagicMock()
        drive.archive_file_idempotent = AsyncMock(
            return_value=(
                {
                    "id": "drive_file_x",
                    "webViewLink": "https://drive.example/x",
                    "md5Checksum": hashlib.md5(b"unit-test-legal-source").hexdigest(),
                },
                "reused",
            )
        )
        legal_settings = SimpleNamespace(
            legal_drive_root_folder_id="legal_root",
            legal_drive_impersonate_user="legal-archive@example.com",
            google_drive_root_folder_id="generic_root",
        )

        p1, p2, p3, p4 = _common_ingest_patches()
        with (
            p1,
            p2 as mock_logger,
            p3,
            p4,
            patch(
                "backend.services.ingestion.legal_ingestion_service.ServiceAccountDriveService",
                return_value=drive,
            ),
            patch("backend.app.core.config.settings", legal_settings),
        ):
            mock_logger.start_ingestion.return_value = "trace_id"
            result = await service.ingest_legal_document(
                file_path="/tmp/SomeOtherMinistry_1_2026.pdf",
                title="Some other ministry 1/2026",
                category="01_immigrazione",
                retrieval_scope="historical_only",
            )

        assert result["success"] is False
        assert "identity collision" in str(result.get("error", "")).lower()
        # The foreign document must be neither quarantined nor deleted.
        service.vector_db.set_payload_by_filter.assert_not_awaited()
        service.vector_db.delete_by_filter.assert_not_awaited()
        service.indexer.index_legal_document.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_declared_identity_is_what_gets_stored(
        self, service: MagicMock
    ) -> None:
        """`document_id` must mean the storage key, not a log correlation id.

        Until 2026-08-25 the caller's `document_id` reached only the ingestion
        logger, while the id written to Qdrant was always the derived triple —
        so a caller who declared an identity got a trace id and believed they
        had set the storage key. Declaring it is what lets a curated corpus say
        which instrument a file is, when the extractor cannot tell PMK 1/2026
        from Permen Imipas 1/2026.
        """
        self._prime(service, existing=[])

        p1, p2, p3, p4 = _common_ingest_patches()
        with p1, p2 as mock_logger, p3, p4:
            mock_logger.start_ingestion.return_value = "trace_id_not_the_storage_key"
            result = await service.ingest_legal_document(
                file_path="/tmp/PMK_1_2026_Coretax_System.pdf",
                title="PMK 1/2026",
                category="04_fiscale",
                document_id="PMK_1_2026",
            )

        assert result["success"] is True
        stored = service.indexer.index_legal_document.await_args.kwargs["document_id"]
        assert stored == "PMK_1_2026"
        assert stored != "Permen_1_2026", (
            "the derived triple is exactly the value that collided; declaring "
            "an identity must override it"
        )

    @pytest.mark.asyncio
    async def test_without_a_declaration_the_derived_identity_is_unchanged(
        self, service: MagicMock
    ) -> None:
        """No declaration ⇒ the pre-existing derivation, byte for byte.

        This pins the blast radius: nothing already in the collection changes
        identity, so no migration is owed and the historical-replacement key
        keeps matching.
        """
        self._prime(service, existing=[])

        p1, p2, p3, p4 = _common_ingest_patches()
        with p1, p2 as mock_logger, p3, p4:
            mock_logger.start_ingestion.return_value = "trace_id"
            await service.ingest_legal_document(
                file_path="/tmp/PMK_1_2026_Coretax_System.pdf",
                title="PMK 1/2026",
                category="04_fiscale",
            )

        stored = service.indexer.index_legal_document.await_args.kwargs["document_id"]
        assert stored == "Permen_1_2026"


# --------------------------------------------------------------------------- #
# ingest_legal_document -- metadata fallback
# --------------------------------------------------------------------------- #


class TestMetadataFallback:
    def test_incomplete_metadata_identity_is_bound_to_source_content(self) -> None:
        from backend.services.ingestion.legal_ingestion_service import (
            build_content_bound_legal_doc_id,
        )

        metadata = {
            "type_abbrev": "DOC",
            "number": "UNKNOWN",
            "year": "UNKNOWN",
        }
        first = build_content_bound_legal_doc_id(metadata, "a" * 64)
        second = build_content_bound_legal_doc_id(metadata, "b" * 64)

        assert first == "DOC_UNKNOWN_UNKNOWN_aaaaaaaaaaaaaaaa"
        assert second == "DOC_UNKNOWN_UNKNOWN_bbbbbbbbbbbbbbbb"
        assert first != second

        type_unknown = {"type_abbrev": "DOC", "number": "43", "year": "2011"}
        assert build_content_bound_legal_doc_id(type_unknown, "c" * 64) == (
            "DOC_43_2011_cccccccccccccccc"
        )

    @pytest.mark.asyncio
    async def test_metadata_unknown_with_category(self, service: MagicMock) -> None:
        service.cleaner.clean.return_value = "cleaned text"
        service.metadata_extractor.extract.return_value = None
        service.classifier.classify_book_tier.return_value = MagicMock(value="bronze")
        service.classifier.get_min_access_level.return_value = "guest"
        service.indexer.index_legal_document = AsyncMock(
            return_value={
                "chunks_indexed": 1,
                "parent_documents": 1,
                "total_bab": 0,
                "total_pasal": 0,
            }
        )

        p1, p2, p3, p4 = _common_ingest_patches()
        with p1, p2 as mock_il, p3, p4:
            mock_il.start_ingestion.return_value = "doc_006"

            result = await service.ingest_legal_document(
                file_path="/tmp/test.pdf",
                category="01_immigrazione",
            )

            assert result["success"] is True
            assert result["legal_metadata"]["type_abbrev"] == "IMMIGRAZIONE"

    @pytest.mark.asyncio
    async def test_metadata_unknown_type_with_partial_metadata(self, service: MagicMock) -> None:
        service.cleaner.clean.return_value = "cleaned text"
        service.metadata_extractor.extract.return_value = {
            "type": "UNKNOWN",
            "type_abbrev": "UNKNOWN",
            "number": "UNKNOWN",
            "year": "UNKNOWN",
            "topic": "UNKNOWN",
        }
        service.classifier.classify_book_tier.return_value = MagicMock(value="bronze")
        service.classifier.get_min_access_level.return_value = "guest"
        service.indexer.index_legal_document = AsyncMock(
            return_value={
                "chunks_indexed": 1,
                "parent_documents": 1,
                "total_bab": 0,
                "total_pasal": 0,
            }
        )

        p1, p2, p3, p4 = _common_ingest_patches()
        with p1, p2 as mock_il, p3, p4:
            mock_il.start_ingestion.return_value = "doc_007"

            result = await service.ingest_legal_document(
                file_path="/tmp/test.pdf",
                title="Custom Title",
                category="02_tax",
            )

            assert result["success"] is True
            assert result["legal_metadata"]["type_abbrev"] == "TAX"


# --------------------------------------------------------------------------- #
# ingest_legal_document -- error path
# --------------------------------------------------------------------------- #


class TestIngestError:
    @pytest.mark.asyncio
    async def test_parse_error(self, service: MagicMock) -> None:
        with (
            patch(
                "backend.services.ingestion.legal_ingestion_service.auto_detect_and_parse",
                side_effect=Exception("File not found"),
            ),
            patch("backend.services.ingestion.legal_ingestion_service.ingestion_logger") as mock_il,
            patch("backend.services.ingestion.legal_ingestion_service.metrics_collector"),
            patch(
                "backend.services.ingestion.legal_ingestion_service.resolve_collection_name",
                return_value="legal_unified",
            ),
        ):
            mock_il.start_ingestion.return_value = "doc_err"

            result = await service.ingest_legal_document(
                file_path="/tmp/nonexistent.pdf",
            )

            assert result["success"] is False
            assert "File not found" in result["error"]
            assert result["chunks_created"] == 0

    @pytest.mark.asyncio
    async def test_error_with_no_document_id(self, service: MagicMock) -> None:
        """Test error path when document_id was not yet generated."""
        with (
            patch(
                "backend.services.ingestion.legal_ingestion_service.auto_detect_and_parse",
                side_effect=Exception("Corrupt PDF"),
            ),
            patch("backend.services.ingestion.legal_ingestion_service.ingestion_logger") as mock_il,
            patch("backend.services.ingestion.legal_ingestion_service.metrics_collector"),
            patch(
                "backend.services.ingestion.legal_ingestion_service.resolve_collection_name",
                return_value="legal_unified",
            ),
        ):
            mock_il.start_ingestion.side_effect = Exception("logger init fail")

            result = await service.ingest_legal_document(
                file_path="/tmp/corrupt.pdf",
            )

            assert result["success"] is False


# --------------------------------------------------------------------------- #
# _ensure_drive_folder_exists
# --------------------------------------------------------------------------- #


class TestEnsureDriveFolder:
    @pytest.mark.asyncio
    async def test_finds_existing_folder(self, service: MagicMock) -> None:
        mock_drive = AsyncMock()
        mock_drive.find_folder = AsyncMock(return_value={"id": "folder_1"})

        mock_settings = MagicMock()
        mock_settings.google_drive_root_folder_id = "root_123"

        with patch("backend.app.core.config.settings", mock_settings):
            result = await service._ensure_drive_folder_exists(
                drive_service=mock_drive,
                folder_path="BALI ZERO",
            )
            assert result == "folder_1"

    @pytest.mark.asyncio
    async def test_creates_missing_folder(self, service: MagicMock) -> None:
        mock_drive = AsyncMock()
        mock_drive.find_folder = AsyncMock(return_value=None)
        mock_drive.create_folder = AsyncMock(return_value={"id": "new_folder_id"})

        mock_settings = MagicMock()
        mock_settings.google_drive_root_folder_id = "root_123"

        with patch("backend.app.core.config.settings", mock_settings):
            result = await service._ensure_drive_folder_exists(
                drive_service=mock_drive,
                folder_path="BALI ZERO/PERATURAN",
            )
            assert result == "new_folder_id"

    @pytest.mark.asyncio
    async def test_list_fails_creates_directly(self, service: MagicMock) -> None:
        mock_drive = AsyncMock()
        mock_drive.find_folder = AsyncMock(side_effect=Exception("API error"))
        mock_drive.create_folder = AsyncMock(return_value={"id": "fallback_id"})

        mock_settings = MagicMock()
        mock_settings.google_drive_root_folder_id = None

        with patch("backend.app.core.config.settings", mock_settings):
            result = await service._ensure_drive_folder_exists(
                drive_service=mock_drive,
                folder_path="TEST",
            )
            assert result == "fallback_id"

    @pytest.mark.asyncio
    async def test_list_and_create_both_fail(self, service: MagicMock) -> None:
        mock_drive = AsyncMock()
        mock_drive.find_folder = AsyncMock(side_effect=Exception("API error"))
        mock_drive.create_folder = AsyncMock(side_effect=Exception("Create also failed"))

        mock_settings = MagicMock()
        mock_settings.google_drive_root_folder_id = None

        with patch("backend.app.core.config.settings", mock_settings):
            with pytest.raises(Exception, match="Create also failed"):
                await service._ensure_drive_folder_exists(
                    drive_service=mock_drive,
                    folder_path="FAIL",
                )

    @pytest.mark.asyncio
    async def test_multi_level_path(self, service: MagicMock) -> None:
        """Test creating nested folder structure."""
        mock_drive = AsyncMock()
        mock_drive.find_folder = AsyncMock(return_value=None)
        mock_drive.create_folder = AsyncMock(
            side_effect=[{"id": "lvl1"}, {"id": "lvl2"}, {"id": "lvl3"}]
        )

        mock_settings = MagicMock()
        mock_settings.google_drive_root_folder_id = "root"

        with patch("backend.app.core.config.settings", mock_settings):
            result = await service._ensure_drive_folder_exists(
                drive_service=mock_drive,
                folder_path="A/B/C",
            )
            assert result == "lvl3"
            assert mock_drive.create_folder.await_count == 3


# --------------------------------------------------------------------------- #
# _get_kg_extractor
# --------------------------------------------------------------------------- #


class TestKGExtractor:
    @pytest.mark.asyncio
    async def test_returns_existing_extractor(self, service: MagicMock) -> None:
        service.kg_extractor = MagicMock()
        result = await service._get_kg_extractor()
        assert result is service.kg_extractor

    @pytest.mark.asyncio
    async def test_returns_none_if_script_missing(self, service: MagicMock) -> None:
        service.kg_extractor = None
        with patch("os.path.exists", return_value=False):
            result = await service._get_kg_extractor()
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_if_no_database_url(self, service: MagicMock) -> None:
        service.kg_extractor = None
        mock_settings = MagicMock()
        mock_settings.database_url = None

        with (
            patch("os.path.exists", return_value=True),
            patch("importlib.util.spec_from_file_location") as mock_spec,
            patch("importlib.util.module_from_spec") as mock_module,
            patch("backend.app.core.config.settings", mock_settings),
        ):
            mock_spec_obj = MagicMock()
            mock_spec.return_value = mock_spec_obj
            mock_mod = MagicMock()
            mock_module.return_value = mock_mod

            result = await service._get_kg_extractor()
            assert result is None
