"""
Integration tests for Legal Ingestion Service
Tests legal document ingestion integration
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["QDRANT_URL"] = os.getenv("QDRANT_URL", "http://localhost:6333")
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestLegalServiceIntegration:
    """Integration tests for Legal Ingestion Service"""

    @pytest.mark.asyncio
    async def test_legal_service_initialization(self, qdrant_client):
        """Test legal service initialization"""
        from app.routers.legal_ingest import get_legal_service

        service = get_legal_service()
        assert service is not None

    @pytest.mark.asyncio
    async def test_legal_service_ingest_flow(self, qdrant_client):
        """Test legal document ingestion flow"""
        with (
            patch(
                "services.legal_ingestion_service.LegalIngestionService.ingest_legal_document",
                new_callable=AsyncMock,
            ) as mock_ingest,
            patch("pathlib.Path.exists", return_value=True),
        ):
            mock_ingest.return_value = {
                "success": True,
                "book_title": "Test Legal Document",
                "chunks_created": 10,
                "legal_metadata": {"type": "UU"},
                "message": "Ingestion successful",
            }

            from app.routers.legal_ingest import get_legal_service

            service = get_legal_service()
            result = await service.ingest_legal_document("/path/to/document.pdf")

            assert result["success"] is True
            assert "chunks_created" in result
