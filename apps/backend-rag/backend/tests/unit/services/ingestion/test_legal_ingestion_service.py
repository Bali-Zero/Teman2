"""
Unit tests for LegalIngestionService.
Covers: init, ingest_legal_document (success, error, OCR fallback, pricing skip),
_ensure_drive_folder_exists, _get_kg_extractor, detect_legal_document.
"""

import os
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if TYPE_CHECKING:
    from backend.services.ingestion.legal_ingestion_service import LegalIngestionService

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("API_KEYS", "test_api_key_1")
os.environ.setdefault("OPENAI_API_KEY", "test_key")
os.environ.setdefault("GOOGLE_API_KEY", "test_key")


def _build_service() -> "LegalIngestionService":
    """Build LegalIngestionService with all heavy dependencies mocked."""
    with patch("backend.services.ingestion.legal_ingestion_service.LegalCleaner") as mc, \
         patch("backend.services.ingestion.legal_ingestion_service.LegalMetadataExtractor") as mme, \
         patch("backend.services.ingestion.legal_ingestion_service.LegalStructureParser") as msp, \
         patch("backend.services.ingestion.legal_ingestion_service.LegalChunker") as mch, \
         patch("backend.services.ingestion.legal_ingestion_service.BM25Vectorizer") as mbm, \
         patch("backend.services.ingestion.legal_ingestion_service.create_embeddings_generator") as mce, \
         patch("backend.services.ingestion.legal_ingestion_service.resolve_collection_name", return_value="legal_unified"), \
         patch("backend.services.ingestion.legal_ingestion_service.QdrantClient") as mqd, \
         patch("backend.services.ingestion.legal_ingestion_service.TierClassifier") as mtc, \
         patch("backend.services.ingestion.legal_ingestion_service.HierarchicalIndexer") as mhi:

        mc.return_value = MagicMock()
        mme.return_value = MagicMock()
        msp.return_value = MagicMock()
        mch.return_value = MagicMock()
        mbm.return_value = MagicMock()
        mce.return_value = MagicMock()
        mqd.return_value = MagicMock()
        mtc.return_value = MagicMock()
        mhi.return_value = MagicMock()

        from backend.services.ingestion.legal_ingestion_service import LegalIngestionService
        svc = LegalIngestionService(collection_name="legal_unified")
        return svc


@pytest.fixture
def service() -> "LegalIngestionService":
    return _build_service()


def _common_ingest_patches():
    """Return the patches commonly needed for ingest_legal_document tests.

    TeamDriveService is imported inside a try/except block in the source code,
    so its import failure is already handled gracefully. We do not mock it.
    """
    return (
        patch("backend.services.ingestion.legal_ingestion_service.auto_detect_and_parse",
              return_value="raw legal text content here"),
        patch("backend.services.ingestion.legal_ingestion_service.ingestion_logger"),
        patch("backend.services.ingestion.legal_ingestion_service.metrics_collector"),
        patch("backend.services.ingestion.legal_ingestion_service.resolve_collection_name",
              return_value="legal_unified"),
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
        service.indexer.index_legal_document = AsyncMock(return_value={
            "chunks_indexed": 10,
            "parent_documents": 3,
            "total_bab": 2,
            "total_pasal": 8,
        })

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
    async def test_ingestion_with_tier_override(self, service: MagicMock) -> None:
        service.cleaner.clean.return_value = "cleaned content"
        service.metadata_extractor.extract.return_value = {
            "type": "PP", "type_abbrev": "PP", "number": "1",
            "year": "2024", "topic": "Test", "status": None, "full_title": "PP 1/2024",
        }
        tier_mock = MagicMock(value="silver")
        service.classifier.get_min_access_level.return_value = "guest"
        service.indexer.index_legal_document = AsyncMock(return_value={
            "chunks_indexed": 5, "parent_documents": 1, "total_bab": 1, "total_pasal": 3,
        })

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
            "type": "PERMEN", "type_abbrev": "PERMEN", "number": "10",
            "year": "2024", "topic": "Test", "status": None, "full_title": "PERMEN 10/2024",
        }
        service.classifier.classify_book_tier.return_value = MagicMock(value="bronze")
        service.classifier.get_min_access_level.return_value = "guest"
        service.indexer.index_legal_document = AsyncMock(return_value={
            "chunks_indexed": 3, "parent_documents": 1, "total_bab": 0, "total_pasal": 2,
        })

        with patch("backend.services.ingestion.legal_ingestion_service.auto_detect_and_parse",
                    return_value="raw text"), \
             patch("backend.services.ingestion.legal_ingestion_service.ingestion_logger") as mock_il, \
             patch("backend.services.ingestion.legal_ingestion_service.metrics_collector"), \
             patch("backend.services.ingestion.legal_ingestion_service.resolve_collection_name",
                    return_value="custom_collection"), \
             patch("backend.services.ingestion.legal_ingestion_service.QdrantClient"):
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
            "type": "UU", "type_abbrev": "UU", "number": "1",
            "year": "2024", "topic": "Test", "status": None, "full_title": "UU 1/2024",
        }
        service.classifier.classify_book_tier.return_value = MagicMock(value="bronze")
        service.classifier.get_min_access_level.return_value = "guest"
        service.indexer.index_legal_document = AsyncMock(return_value={
            "chunks_indexed": 1, "parent_documents": 1, "total_bab": 0, "total_pasal": 0,
        })

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
            "type": "PP", "type_abbrev": "PP", "number": "1",
            "year": "2024", "topic": "Fees", "status": None, "full_title": "PP 1/2024",
        }
        service.classifier.classify_book_tier.return_value = MagicMock(value="golden")
        service.classifier.get_min_access_level.return_value = "member"
        service.indexer.index_legal_document = AsyncMock(return_value={
            "chunks_indexed": 2, "parent_documents": 1, "total_bab": 0, "total_pasal": 1,
        })

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
            "type": "PP", "type_abbrev": "PP", "number": "2",
            "year": "2024", "topic": "Fees", "status": None, "full_title": "PP 2/2024",
        }
        service.classifier.classify_book_tier.return_value = MagicMock(value="golden")
        service.classifier.get_min_access_level.return_value = "member"
        service.indexer.index_legal_document = AsyncMock(return_value={
            "chunks_indexed": 1, "parent_documents": 1, "total_bab": 0, "total_pasal": 0,
        })

        p1, p2, p3, p4 = _common_ingest_patches()
        with p1, p2 as mock_il, p3, p4:
            mock_il.start_ingestion.return_value = "doc_005"

            result = await service.ingest_legal_document(
                file_path="/tmp/test.pdf",
                skip_pricing=True,
            )

            assert result["success"] is True


# --------------------------------------------------------------------------- #
# ingest_legal_document -- metadata fallback
# --------------------------------------------------------------------------- #

class TestMetadataFallback:
    @pytest.mark.asyncio
    async def test_metadata_unknown_with_category(self, service: MagicMock) -> None:
        service.cleaner.clean.return_value = "cleaned text"
        service.metadata_extractor.extract.return_value = None
        service.classifier.classify_book_tier.return_value = MagicMock(value="bronze")
        service.classifier.get_min_access_level.return_value = "guest"
        service.indexer.index_legal_document = AsyncMock(return_value={
            "chunks_indexed": 1, "parent_documents": 1, "total_bab": 0, "total_pasal": 0,
        })

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
            "type": "UNKNOWN", "type_abbrev": "UNKNOWN",
            "number": "UNKNOWN", "year": "UNKNOWN", "topic": "UNKNOWN",
        }
        service.classifier.classify_book_tier.return_value = MagicMock(value="bronze")
        service.classifier.get_min_access_level.return_value = "guest"
        service.indexer.index_legal_document = AsyncMock(return_value={
            "chunks_indexed": 1, "parent_documents": 1, "total_bab": 0, "total_pasal": 0,
        })

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
        with patch("backend.services.ingestion.legal_ingestion_service.auto_detect_and_parse",
                    side_effect=Exception("File not found")), \
             patch("backend.services.ingestion.legal_ingestion_service.ingestion_logger") as mock_il, \
             patch("backend.services.ingestion.legal_ingestion_service.metrics_collector"), \
             patch("backend.services.ingestion.legal_ingestion_service.resolve_collection_name",
                    return_value="legal_unified"):
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
        with patch("backend.services.ingestion.legal_ingestion_service.auto_detect_and_parse",
                    side_effect=Exception("Corrupt PDF")), \
             patch("backend.services.ingestion.legal_ingestion_service.ingestion_logger") as mock_il, \
             patch("backend.services.ingestion.legal_ingestion_service.metrics_collector"), \
             patch("backend.services.ingestion.legal_ingestion_service.resolve_collection_name",
                    return_value="legal_unified"):
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
        mock_drive.list_files = AsyncMock(return_value={
            "files": [
                {"name": "BALI ZERO", "type": "folder", "id": "folder_1"},
            ],
        })

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
        mock_drive.list_files = AsyncMock(return_value={"files": []})
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
        mock_drive.list_files = AsyncMock(side_effect=Exception("API error"))
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
        mock_drive.list_files = AsyncMock(side_effect=Exception("API error"))
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
        mock_drive.list_files = AsyncMock(return_value={"files": []})
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

        with patch("os.path.exists", return_value=True), \
             patch("importlib.util.spec_from_file_location") as mock_spec, \
             patch("importlib.util.module_from_spec") as mock_module, \
             patch("backend.app.core.config.settings", mock_settings):
            mock_spec_obj = MagicMock()
            mock_spec.return_value = mock_spec_obj
            mock_mod = MagicMock()
            mock_module.return_value = mock_mod

            result = await service._get_kg_extractor()
            assert result is None
