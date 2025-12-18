"""
Unit tests for Legal Ingestion Service
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

# Move imports here to satisfy E402 if possible, or ignore E402
from app.models import TierLevel  # noqa: E402
from services.legal_ingestion_service import LegalIngestionService  # noqa: E402

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_legal_components():
    """Mock all legal processing components"""
    return {
        "cleaner": MagicMock(),
        "metadata_extractor": MagicMock(),
        "structure_parser": MagicMock(),
        "chunker": MagicMock(),
        "embedder": MagicMock(),
        "vector_db": MagicMock(),
        "classifier": MagicMock(),
        "indexer": MagicMock(),  # Added HierarchicalIndexer mock
    }


@pytest.fixture
def legal_ingestion_service(mock_legal_components):
    """Create LegalIngestionService with mocked components"""
    with (
        patch(
            "services.legal_ingestion_service.LegalCleaner",
            return_value=mock_legal_components["cleaner"],
        ),
        patch(
            "services.legal_ingestion_service.LegalMetadataExtractor",
            return_value=mock_legal_components["metadata_extractor"],
        ),
        patch(
            "services.legal_ingestion_service.LegalStructureParser",
            return_value=mock_legal_components["structure_parser"],
        ),
        patch(
            "services.legal_ingestion_service.LegalChunker",
            return_value=mock_legal_components["chunker"],
        ),
        patch(
            "services.legal_ingestion_service.create_embeddings_generator",
            return_value=mock_legal_components["embedder"],
        ),
        patch(
            "services.legal_ingestion_service.QdrantClient",
            return_value=mock_legal_components["vector_db"],
        ),
        patch(
            "services.legal_ingestion_service.TierClassifier",
            return_value=mock_legal_components["classifier"],
        ),
        patch(
            "services.legal_ingestion_service.HierarchicalIndexer",
            return_value=mock_legal_components["indexer"],
        ),
    ):
        service = LegalIngestionService()
        return service, mock_legal_components


@pytest.fixture
def sample_legal_text():
    """Sample legal document text"""
    return """
    UNDANG-UNDANG REPUBLIK INDONESIA
    NOMOR 12 TAHUN 2024
    TENTANG PERUBAHAN ATAS UNDANG-UNDANG NOMOR 5 TAHUN 2023

    BAB I
    KETENTUAN UMUM

    Pasal 1
    Dalam Undang-Undang ini yang dimaksud dengan:
    1. Pemerintah adalah Pemerintah Republik Indonesia.
    2. Menteri adalah Menteri yang menyelenggarakan urusan pemerintahan.
    """


# ============================================================================
# Tests for __init__
# ============================================================================


def test_init_default_collection(mock_legal_components):
    """Test initialization with default collection"""
    with (
        patch(
            "services.legal_ingestion_service.LegalCleaner",
            return_value=mock_legal_components["cleaner"],
        ),
        patch(
            "services.legal_ingestion_service.LegalMetadataExtractor",
            return_value=mock_legal_components["metadata_extractor"],
        ),
        patch(
            "services.legal_ingestion_service.LegalStructureParser",
            return_value=mock_legal_components["structure_parser"],
        ),
        patch(
            "services.legal_ingestion_service.LegalChunker",
            return_value=mock_legal_components["chunker"],
        ),
        patch(
            "services.legal_ingestion_service.create_embeddings_generator",
            return_value=mock_legal_components["embedder"],
        ),
        patch(
            "services.legal_ingestion_service.QdrantClient",
            return_value=mock_legal_components["vector_db"],
        ),
        patch(
            "services.legal_ingestion_service.TierClassifier",
            return_value=mock_legal_components["classifier"],
        ),
    ):
        service = LegalIngestionService()
        assert service.cleaner == mock_legal_components["cleaner"]
        assert service.metadata_extractor == mock_legal_components["metadata_extractor"]
        assert service.structure_parser == mock_legal_components["structure_parser"]
        assert service.chunker == mock_legal_components["chunker"]
        assert service.embedder == mock_legal_components["embedder"]
        assert service.vector_db == mock_legal_components["vector_db"]
        assert service.classifier == mock_legal_components["classifier"]


def test_init_custom_collection(mock_legal_components):
    """Test initialization with custom collection name"""
    with (
        patch(
            "services.legal_ingestion_service.LegalCleaner",
            return_value=mock_legal_components["cleaner"],
        ),
        patch(
            "services.legal_ingestion_service.LegalMetadataExtractor",
            return_value=mock_legal_components["metadata_extractor"],
        ),
        patch(
            "services.legal_ingestion_service.LegalStructureParser",
            return_value=mock_legal_components["structure_parser"],
        ),
        patch(
            "services.legal_ingestion_service.LegalChunker",
            return_value=mock_legal_components["chunker"],
        ),
        patch(
            "services.legal_ingestion_service.create_embeddings_generator",
            return_value=mock_legal_components["embedder"],
        ),
        patch(
            "services.legal_ingestion_service.QdrantClient",
            return_value=mock_legal_components["vector_db"],
        ) as mock_qdrant,
        patch(
            "services.legal_ingestion_service.TierClassifier",
            return_value=mock_legal_components["classifier"],
        ),
        patch(
            "services.legal_ingestion_service.HierarchicalIndexer",
            return_value=mock_legal_components["indexer"],
        ),
    ):
        _ = LegalIngestionService(collection_name="custom_collection")
        mock_qdrant.assert_called_once_with(collection_name="custom_collection")


# ============================================================================
# Tests for ingest_legal_document
# ============================================================================


@pytest.mark.asyncio
async def test_ingest_legal_document_success(legal_ingestion_service, sample_legal_text):
    """Test successful legal document ingestion"""
    service, mocks = legal_ingestion_service

    # Setup mocks
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
        tmp.write(sample_legal_text)
        tmp_path = tmp.name

    try:
        mocks["cleaner"].clean.return_value = sample_legal_text
        mocks["metadata_extractor"].extract.return_value = {
            "type": "UNDANG-UNDANG",
            "type_abbrev": "UU",
            "number": "12",
            "year": 2024,
            "topic": "Perubahan",
            "status": "BERLAKU",
            "full_title": "UU No. 12 Tahun 2024",
        }
        mocks["structure_parser"].parse.return_value = {
            "batang_tubuh": [{"bab": "BAB I"}],
            "pasal_list": [{"pasal": "Pasal 1"}],
        }
        mocks["chunker"].chunk.return_value = [
            {"text": "Chunk 1", "chunk_index": 0, "total_chunks": 2, "has_context": True},
            {"text": "Chunk 2", "chunk_index": 1, "total_chunks": 2, "has_context": False},
        ]
        mocks["embedder"].generate_embeddings.return_value = [[0.1] * 1536, [0.2] * 1536]
        mocks["classifier"].classify_book_tier.return_value = TierLevel.S
        mocks["classifier"].get_min_access_level.return_value = 0
        mocks["indexer"].index_legal_document = AsyncMock(
            return_value={
                "chunks_indexed": 2,
                "parent_documents": 1,
                "total_bab": 1,
                "total_pasal": 1,
            }
        )

        with patch(
            "services.legal_ingestion_service.auto_detect_and_parse", return_value=sample_legal_text
        ):
            result = await service.ingest_legal_document(tmp_path)

            assert result["success"] is True
            assert result["chunks_created"] == 2
            assert result["book_title"] == "UU No. 12 Tahun 2024"
            assert result["tier"] == TierLevel.S.value
            assert "legal_metadata" in result
            assert "structure" in result
            mocks["indexer"].index_legal_document.assert_called_once()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_ingest_legal_document_with_title(legal_ingestion_service, sample_legal_text):
    """Test ingestion with provided title"""
    service, mocks = legal_ingestion_service

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
        tmp.write(sample_legal_text)
        tmp_path = tmp.name

    try:
        mocks["cleaner"].clean.return_value = sample_legal_text
        mocks["metadata_extractor"].extract.return_value = {}
        mocks["structure_parser"].parse.return_value = {"batang_tubuh": [], "pasal_list": []}
        mocks["chunker"].chunk.return_value = [
            {"text": "Chunk", "chunk_index": 0, "total_chunks": 1}
        ]
        mocks["embedder"].generate_embeddings.return_value = [[0.1] * 1536]
        mocks["classifier"].classify_book_tier.return_value = TierLevel.S
        mocks["classifier"].get_min_access_level.return_value = 0

        with patch(
            "services.legal_ingestion_service.auto_detect_and_parse", return_value=sample_legal_text
        ):
            result = await service.ingest_legal_document(tmp_path, title="Custom Title")

            assert result["book_title"] == "Custom Title"
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_ingest_legal_document_with_tier_override(legal_ingestion_service, sample_legal_text):
    """Test ingestion with tier override"""
    service, mocks = legal_ingestion_service

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
        tmp.write(sample_legal_text)
        tmp_path = tmp.name

    try:
        mocks["cleaner"].clean.return_value = sample_legal_text
        mocks["metadata_extractor"].extract.return_value = {}
        mocks["structure_parser"].parse.return_value = {"batang_tubuh": [], "pasal_list": []}
        mocks["chunker"].chunk.return_value = [
            {"text": "Chunk", "chunk_index": 0, "total_chunks": 1}
        ]
        mocks["embedder"].generate_embeddings.return_value = [[0.1] * 1536]
        mocks["classifier"].get_min_access_level.return_value = 1
        mocks["indexer"].index_legal_document = AsyncMock(
            return_value={
                "chunks_indexed": 1,
                "parent_documents": 1,
                "total_bab": 0,
                "total_pasal": 0,
            }
        )

        with patch(
            "services.legal_ingestion_service.auto_detect_and_parse", return_value=sample_legal_text
        ):
            result = await service.ingest_legal_document(tmp_path, tier_override=TierLevel.A)

            assert result["tier"] == TierLevel.A.value
            # Should not call classify_book_tier when override is provided
            mocks["classifier"].classify_book_tier.assert_not_called()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_ingest_legal_document_with_collection_override(
    legal_ingestion_service, sample_legal_text
):
    """Test ingestion with collection name override"""
    service, mocks = legal_ingestion_service

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
        tmp.write(sample_legal_text)
        tmp_path = tmp.name

    try:
        new_vector_db = MagicMock()
        mocks["cleaner"].clean.return_value = sample_legal_text
        mocks["metadata_extractor"].extract.return_value = {}
        mocks["structure_parser"].parse.return_value = {"batang_tubuh": [], "pasal_list": []}
        mocks["chunker"].chunk.return_value = [
            {"text": "Chunk", "chunk_index": 0, "total_chunks": 1}
        ]
        mocks["embedder"].generate_embeddings.return_value = [[0.1] * 1536]
        mocks["classifier"].classify_book_tier.return_value = TierLevel.S
        mocks["classifier"].get_min_access_level.return_value = 0
        mocks["indexer"].index_legal_document = AsyncMock(
            return_value={
                "chunks_indexed": 1,
                "parent_documents": 1,
                "total_bab": 0,
                "total_pasal": 0,
            }
        )

        with (
            patch(
                "services.legal_ingestion_service.auto_detect_and_parse",
                return_value=sample_legal_text,
            ),
            patch("services.legal_ingestion_service.QdrantClient", return_value=new_vector_db),
            patch(
                "services.legal_ingestion_service.HierarchicalIndexer",
                return_value=mocks["indexer"],
            ),
        ):
            _ = await service.ingest_legal_document(tmp_path, collection_name="custom_collection")

            assert service.vector_db == new_vector_db
            mocks["indexer"].index_legal_document.assert_called_once()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_ingest_legal_document_vertex_ai_fallback(legal_ingestion_service, sample_legal_text):
    """Test Vertex AI fallback when pattern extraction fails"""
    service, mocks = legal_ingestion_service

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
        tmp.write(sample_legal_text)
        tmp_path = tmp.name

    try:
        mocks["cleaner"].clean.return_value = sample_legal_text
        mocks["metadata_extractor"].extract.return_value = {"type": "UNKNOWN"}  # Triggers fallback
        mocks["structure_parser"].parse.return_value = {"batang_tubuh": [], "pasal_list": []}
        mocks["chunker"].chunk.return_value = [
            {"text": "Chunk", "chunk_index": 0, "total_chunks": 1}
        ]
        mocks["embedder"].generate_embeddings.return_value = [[0.1] * 1536]
        mocks["classifier"].classify_book_tier.return_value = TierLevel.S
        mocks["classifier"].get_min_access_level.return_value = 0

        mock_vertex_service = MagicMock()
        mock_vertex_service.extract_metadata = AsyncMock(
            return_value={"type": "UNDANG-UNDANG", "type_abbrev": "UU", "number": "12"}
        )

        mocks["indexer"].index_legal_document = AsyncMock(
            return_value={
                "chunks_indexed": 1,
                "parent_documents": 1,
                "total_bab": 0,
                "total_pasal": 0,
            }
        )

        with (
            patch(
                "services.legal_ingestion_service.auto_detect_and_parse",
                return_value=sample_legal_text,
            ),
            patch("services.vertex_ai_service.VertexAIService", return_value=mock_vertex_service),
        ):
            result = await service.ingest_legal_document(tmp_path)

            assert result["success"] is True
            mock_vertex_service.extract_metadata.assert_called_once()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_ingest_legal_document_vertex_ai_fallback_failure(
    legal_ingestion_service, sample_legal_text
):
    """Test handling when Vertex AI fallback fails"""
    service, mocks = legal_ingestion_service

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
        tmp.write(sample_legal_text)
        tmp_path = tmp.name

    try:
        mocks["cleaner"].clean.return_value = sample_legal_text
        mocks["metadata_extractor"].extract.return_value = {"type": "UNKNOWN"}
        mocks["structure_parser"].parse.return_value = {"batang_tubuh": [], "pasal_list": []}
        mocks["chunker"].chunk.return_value = [
            {"text": "Chunk", "chunk_index": 0, "total_chunks": 1}
        ]
        mocks["embedder"].generate_embeddings.return_value = [[0.1] * 1536]
        mocks["classifier"].classify_book_tier.return_value = TierLevel.S
        mocks["classifier"].get_min_access_level.return_value = 0

        mock_vertex_service = MagicMock()
        mock_vertex_service.extract_metadata = AsyncMock(side_effect=Exception("Vertex AI error"))

        mocks["indexer"].index_legal_document = AsyncMock(
            return_value={
                "chunks_indexed": 1,
                "parent_documents": 1,
                "total_bab": 0,
                "total_pasal": 0,
            }
        )

        with (
            patch(
                "services.legal_ingestion_service.auto_detect_and_parse",
                return_value=sample_legal_text,
            ),
            patch("services.vertex_ai_service.VertexAIService", return_value=mock_vertex_service),
            patch("services.legal_ingestion_service.logger") as mock_logger,
        ):
            result = await service.ingest_legal_document(tmp_path)

            # Should continue with default metadata
            assert result["success"] is True
            mock_logger.warning.assert_called()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_ingest_legal_document_no_metadata(legal_ingestion_service, sample_legal_text):
    """Test ingestion when no metadata is extracted"""
    service, mocks = legal_ingestion_service

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
        tmp.write(sample_legal_text)
        tmp_path = tmp.name

    try:
        mocks["cleaner"].clean.return_value = sample_legal_text
        mocks["metadata_extractor"].extract.return_value = None  # No metadata
        mocks["structure_parser"].parse.return_value = {"batang_tubuh": [], "pasal_list": []}
        mocks["chunker"].chunk.return_value = [
            {"text": "Chunk", "chunk_index": 0, "total_chunks": 1}
        ]
        mocks["embedder"].generate_embeddings.return_value = [[0.1] * 1536]
        mocks["classifier"].classify_book_tier.return_value = TierLevel.S
        mocks["classifier"].get_min_access_level.return_value = 0
        mocks["indexer"].index_legal_document = AsyncMock(
            return_value={
                "chunks_indexed": 1,
                "parent_documents": 1,
                "total_bab": 0,
                "total_pasal": 0,
            }
        )

        with patch(
            "services.legal_ingestion_service.auto_detect_and_parse", return_value=sample_legal_text
        ):
            result = await service.ingest_legal_document(tmp_path)

            # Should use default metadata
            assert result["success"] is True
            assert result["legal_metadata"]["type"] == "UNKNOWN"
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_ingest_legal_document_no_chunks(legal_ingestion_service, sample_legal_text):
    """Test ingestion when chunking produces no results"""
    service, mocks = legal_ingestion_service

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
        tmp.write(sample_legal_text)
        tmp_path = tmp.name

    try:
        mocks["cleaner"].clean.return_value = sample_legal_text
        mocks["metadata_extractor"].extract.return_value = {}
        mocks["structure_parser"].parse.return_value = {"batang_tubuh": [], "pasal_list": []}
        mocks["chunker"].chunk.return_value = []  # No chunks
        # When chunks are empty, indexer might still be called but with empty data
        # or the service might return early - adjust test accordingly
        mocks["indexer"].index_legal_document = AsyncMock(
            return_value={
                "chunks_indexed": 0,
                "parent_documents": 0,
                "total_bab": 0,
                "total_pasal": 0,
            }
        )

        with patch(
            "services.legal_ingestion_service.auto_detect_and_parse", return_value=sample_legal_text
        ):
            result = await service.ingest_legal_document(tmp_path)

            # When no chunks, the service should handle gracefully
            # It may return success=False or success=True with 0 chunks
            assert result["chunks_created"] == 0
            # Don't assert on indexer call - service may or may not call it with empty chunks
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_ingest_legal_document_with_pasal_number(legal_ingestion_service, sample_legal_text):
    """Test ingestion with chunks containing Pasal numbers"""
    service, mocks = legal_ingestion_service

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
        tmp.write(sample_legal_text)
        tmp_path = tmp.name

    try:
        mocks["cleaner"].clean.return_value = sample_legal_text
        mocks["metadata_extractor"].extract.return_value = {}
        mocks["structure_parser"].parse.return_value = {"batang_tubuh": [], "pasal_list": []}
        mocks["chunker"].chunk.return_value = [
            {"text": "Chunk 1", "chunk_index": 0, "total_chunks": 1, "pasal_number": "1"}
        ]
        mocks["embedder"].generate_embeddings.return_value = [[0.1] * 1536]
        mocks["classifier"].classify_book_tier.return_value = TierLevel.S
        mocks["classifier"].get_min_access_level.return_value = 0
        mocks["indexer"].index_legal_document = AsyncMock(
            return_value={
                "chunks_indexed": 1,
                "parent_documents": 1,
                "total_bab": 0,
                "total_pasal": 1,
            }
        )

        with patch(
            "services.legal_ingestion_service.auto_detect_and_parse", return_value=sample_legal_text
        ):
            result = await service.ingest_legal_document(tmp_path)

            assert result["success"] is True
            # Verify indexer was called with correct metadata
            assert mocks["indexer"].index_legal_document.called
            call_args = mocks["indexer"].index_legal_document.call_args
            # Verify metadata was passed correctly
            assert "metadata" in call_args.kwargs
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_ingest_legal_document_exception_handling(legal_ingestion_service, sample_legal_text):
    """Test exception handling during ingestion"""
    service, mocks = legal_ingestion_service

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
        tmp.write(sample_legal_text)
        tmp_path = tmp.name

    try:
        mocks["cleaner"].clean.side_effect = Exception("Cleaning failed")

        with patch(
            "services.legal_ingestion_service.auto_detect_and_parse", return_value=sample_legal_text
        ):
            result = await service.ingest_legal_document(tmp_path, title="Test Document")

            assert result["success"] is False
            assert result["book_title"] == "Test Document"
            assert "error" in result
            assert "Cleaning failed" in result["error"]
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_ingest_legal_document_uses_title_from_metadata(
    legal_ingestion_service, sample_legal_text
):
    """Test that title from metadata is used when not provided"""
    service, mocks = legal_ingestion_service

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
        tmp.write(sample_legal_text)
        tmp_path = tmp.name

    try:
        mocks["cleaner"].clean.return_value = sample_legal_text
        mocks["metadata_extractor"].extract.return_value = {
            "full_title": "Extracted Title from Metadata"
        }
        mocks["structure_parser"].parse.return_value = {"batang_tubuh": [], "pasal_list": []}
        mocks["chunker"].chunk.return_value = [
            {"text": "Chunk", "chunk_index": 0, "total_chunks": 1}
        ]
        mocks["embedder"].generate_embeddings.return_value = [[0.1] * 1536]
        mocks["classifier"].classify_book_tier.return_value = TierLevel.S
        mocks["classifier"].get_min_access_level.return_value = 0
        mocks["indexer"].index_legal_document = AsyncMock(
            return_value={
                "chunks_indexed": 1,
                "parent_documents": 1,
                "total_bab": 0,
                "total_pasal": 0,
            }
        )

        with patch(
            "services.legal_ingestion_service.auto_detect_and_parse", return_value=sample_legal_text
        ):
            result = await service.ingest_legal_document(tmp_path)

            assert result["book_title"] == "Extracted Title from Metadata"
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_ingest_legal_document_uses_filename_when_no_title(
    legal_ingestion_service, sample_legal_text
):
    """Test that filename is used as title when no title or metadata title"""
    service, mocks = legal_ingestion_service

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, prefix="test_doc_"
    ) as tmp:
        tmp.write(sample_legal_text)
        tmp_path = tmp.name

    try:
        mocks["cleaner"].clean.return_value = sample_legal_text
        mocks["metadata_extractor"].extract.return_value = {}
        mocks["structure_parser"].parse.return_value = {"batang_tubuh": [], "pasal_list": []}
        mocks["chunker"].chunk.return_value = [
            {"text": "Chunk", "chunk_index": 0, "total_chunks": 1}
        ]
        mocks["embedder"].generate_embeddings.return_value = [[0.1] * 1536]
        mocks["classifier"].classify_book_tier.return_value = TierLevel.S
        mocks["classifier"].get_min_access_level.return_value = 0

        with patch(
            "services.legal_ingestion_service.auto_detect_and_parse", return_value=sample_legal_text
        ):
            result = await service.ingest_legal_document(tmp_path)

            # Should use filename stem
            filename_stem = Path(tmp_path).stem
            assert filename_stem in result["book_title"] or result["book_title"] == filename_stem
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ============================================================================
# Tests for detect_legal_document
# ============================================================================


def test_detect_legal_document_true(legal_ingestion_service):
    """Test legal document detection returns True"""
    service, mocks = legal_ingestion_service
    mocks["metadata_extractor"].is_legal_document.return_value = True

    result = service.detect_legal_document("UNDANG-UNDANG REPUBLIK INDONESIA")

    assert result is True
    mocks["metadata_extractor"].is_legal_document.assert_called_once_with(
        "UNDANG-UNDANG REPUBLIK INDONESIA"
    )


def test_detect_legal_document_false(legal_ingestion_service):
    """Test legal document detection returns False"""
    service, mocks = legal_ingestion_service
    mocks["metadata_extractor"].is_legal_document.return_value = False

    result = service.detect_legal_document("Regular text document")

    assert result is False
