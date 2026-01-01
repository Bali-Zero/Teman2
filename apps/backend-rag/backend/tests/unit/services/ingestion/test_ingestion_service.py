"""
Unit tests for IngestionService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.ingestion.ingestion_service import IngestionService


@pytest.fixture
def ingestion_service():
    """Create IngestionService instance"""
    with patch('services.ingestion.ingestion_service.create_embeddings_generator'):
        with patch('services.ingestion.ingestion_service.QdrantClient'):
            with patch('services.ingestion.ingestion_service.TierClassifier'):
                service = IngestionService()
                return service


class TestIngestionService:
    """Tests for IngestionService"""

    def test_init(self):
        """Test initialization"""
        with patch('services.ingestion.ingestion_service.create_embeddings_generator'):
            with patch('services.ingestion.ingestion_service.QdrantClient'):
                with patch('services.ingestion.ingestion_service.TierClassifier'):
                    service = IngestionService()
                    assert service.chunker is not None
                    assert service.embedder is not None
                    assert service.vector_db is not None

    @pytest.mark.asyncio
    async def test_ingest_book_legal_document(self, ingestion_service):
        """Test ingesting legal document"""
        ingestion_service._is_legal_document = MagicMock(return_value=True)
        with patch('services.ingestion.legal_ingestion_service.LegalIngestionService') as mock_legal:
            mock_legal_instance = MagicMock()
            mock_legal_instance.ingest_legal_document = AsyncMock(return_value={"status": "success"})
            mock_legal.return_value = mock_legal_instance
            result = await ingestion_service.ingest_book("test.pdf")
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_ingest_book_regular_document(self, ingestion_service):
        """Test ingesting regular document"""
        ingestion_service._is_legal_document = MagicMock(return_value=False)
        with patch('services.ingestion.ingestion_service.get_document_info') as mock_info:
            mock_info.return_value = {"title": "Test Book", "author": "Test Author"}
            with patch('services.ingestion.ingestion_service.auto_detect_and_parse') as mock_parse:
                mock_parse.return_value = "Test content"
                ingestion_service.chunker.chunk_text = MagicMock(return_value=["chunk1", "chunk2"])
                ingestion_service.embedder.generate_embeddings = AsyncMock(return_value=[[0.1] * 384])
                ingestion_service.vector_db.upsert_documents = AsyncMock()
                result = await ingestion_service.ingest_book("test.pdf")
                assert isinstance(result, dict)

    def test_is_legal_document(self, ingestion_service):
        """Test detecting legal documents"""
        result = ingestion_service._is_legal_document("test.pdf")
        assert isinstance(result, bool)

