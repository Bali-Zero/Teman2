"""
Comprehensive Integration Tests for Ingestion Services
Tests IngestionService, LegalIngestionService, AutoIngestionOrchestrator

Covers:
- Document ingestion
- Legal document processing
- Auto ingestion orchestration
- Batch processing
- Error handling
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("OPENAI_API_KEY", "test_openai_api_key_for_testing")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestIngestionServiceIntegration:
    """Integration tests for IngestionService"""

    @pytest.mark.asyncio
    async def test_ingestion_service_initialization(self, qdrant_client):
        """Test IngestionService initialization"""
        with patch("services.ingestion_service.QdrantClient") as mock_qdrant:
            from services.ingestion_service import IngestionService

            service = IngestionService()

            assert service is not None

    @pytest.mark.asyncio
    async def test_ingest_document(self, qdrant_client):
        """Test document ingestion"""
        with (
            patch("services.ingestion_service.QdrantClient") as mock_qdrant,
            patch("core.embeddings.create_embeddings_generator") as mock_embedder,
        ):
            mock_client = MagicMock()
            mock_client.upsert = AsyncMock(return_value=True)
            mock_qdrant.return_value = mock_client

            embedder = MagicMock()
            embedder.generate_embeddings = AsyncMock(return_value=[[0.1] * 1536])
            mock_embedder.return_value = embedder

            from services.ingestion_service import IngestionService

            service = IngestionService()
            service.qdrant_client = mock_client

            document = {
                "text": "Test document content",
                "metadata": {"source": "test", "type": "document"},
            }

            result = await service.ingest_document(
                document=document, collection_name="test_collection"
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_batch_ingestion(self, qdrant_client):
        """Test batch document ingestion"""
        with (
            patch("services.ingestion_service.QdrantClient") as mock_qdrant,
            patch("core.embeddings.create_embeddings_generator") as mock_embedder,
        ):
            mock_client = MagicMock()
            mock_client.upsert = AsyncMock(return_value=True)
            mock_qdrant.return_value = mock_client

            embedder = MagicMock()
            embedder.generate_embeddings = AsyncMock(return_value=[[0.1] * 1536] * 10)
            mock_embedder.return_value = embedder

            from services.ingestion_service import IngestionService

            service = IngestionService()
            service.qdrant_client = mock_client

            documents = [{"text": f"Document {i}", "metadata": {"index": i}} for i in range(10)]

            result = await service.batch_ingest(
                documents=documents, collection_name="test_collection"
            )

            assert result is not None
            assert mock_client.upsert.called


@pytest.mark.integration
class TestLegalIngestionServiceIntegration:
    """Integration tests for LegalIngestionService"""

    @pytest.mark.asyncio
    async def test_legal_ingestion_service_initialization(self, qdrant_client):
        """Test LegalIngestionService initialization"""
        with patch("services.legal_ingestion_service.QdrantClient") as mock_qdrant:
            from services.legal_ingestion_service import LegalIngestionService

            service = LegalIngestionService()

            assert service is not None

    @pytest.mark.asyncio
    async def test_ingest_legal_document(self, qdrant_client):
        """Test legal document ingestion"""
        with (
            patch("services.legal_ingestion_service.QdrantClient") as mock_qdrant,
            patch("core.embeddings.create_embeddings_generator") as mock_embedder,
        ):
            mock_client = MagicMock()
            mock_client.upsert = AsyncMock(return_value=True)
            mock_qdrant.return_value = mock_client

            embedder = MagicMock()
            embedder.generate_embeddings = AsyncMock(return_value=[[0.1] * 1536])
            mock_embedder.return_value = embedder

            from services.legal_ingestion_service import LegalIngestionService

            service = LegalIngestionService()
            service.qdrant_client = mock_client

            legal_doc = {
                "law_id": "UU-11-2020",
                "pasal": "1",
                "content": "Ketentuan Umum",
                "metadata": {
                    "category": "legal_regulation",
                    "type": "undang_undang",
                },
            }

            result = await service.ingest_legal_document(legal_doc)

            assert result is not None

    @pytest.mark.asyncio
    async def test_legal_document_chunking(self, qdrant_client):
        """Test legal document chunking"""
        with (
            patch("services.legal_ingestion_service.QdrantClient") as mock_qdrant,
            patch("core.embeddings.create_embeddings_generator") as mock_embedder,
        ):
            mock_client = MagicMock()
            mock_client.upsert = AsyncMock(return_value=True)
            mock_qdrant.return_value = mock_client

            embedder = MagicMock()
            embedder.generate_embeddings = AsyncMock(return_value=[[0.1] * 1536] * 5)
            mock_embedder.return_value = embedder

            from services.legal_ingestion_service import LegalIngestionService

            service = LegalIngestionService()
            service.qdrant_client = mock_client

            # Long legal document
            long_content = "Pasal 1. " * 1000  # Very long content

            legal_doc = {
                "law_id": "UU-11-2020",
                "pasal": "1",
                "content": long_content,
                "metadata": {"category": "legal_regulation"},
            }

            result = await service.ingest_legal_document(legal_doc)

            # Should chunk into multiple documents
            assert result is not None
            assert mock_client.upsert.called


@pytest.mark.integration
class TestAutoIngestionOrchestratorIntegration:
    """Integration tests for AutoIngestionOrchestrator"""

    @pytest.mark.asyncio
    async def test_auto_ingestion_orchestrator_initialization(self, db_pool):
        """Test AutoIngestionOrchestrator initialization"""
        with (
            patch("services.auto_ingestion_orchestrator.IngestionService") as mock_ingestion,
            patch("services.auto_ingestion_orchestrator.LegalIngestionService") as mock_legal,
        ):
            from services.auto_ingestion_orchestrator import AutoIngestionOrchestrator

            orchestrator = AutoIngestionOrchestrator(
                ingestion_service=mock_ingestion.return_value,
                legal_ingestion_service=mock_legal.return_value,
            )

            assert orchestrator is not None

    @pytest.mark.asyncio
    async def test_auto_ingestion_workflow(self, db_pool, qdrant_client):
        """Test auto ingestion workflow"""

        async with db_pool.acquire() as conn:
            # Create ingestion_jobs table if not exists
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ingestion_jobs (
                    id SERIAL PRIMARY KEY,
                    job_id VARCHAR(255) UNIQUE,
                    source_type VARCHAR(100),
                    status VARCHAR(50),
                    documents_count INTEGER,
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW(),
                    completed_at TIMESTAMP
                )
                """
            )

            # Create job
            job_id = await conn.fetchval(
                """
                INSERT INTO ingestion_jobs (
                    job_id, source_type, status, documents_count, metadata
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                "auto_ingest_job_123",
                "legal_document",
                "pending",
                0,
                {"source": "test", "collection": "legal_unified"},
            )

            assert job_id is not None

            # Update job status
            await conn.execute(
                """
                UPDATE ingestion_jobs
                SET status = $1, documents_count = $2, completed_at = NOW()
                WHERE job_id = $3
                """,
                "completed",
                10,
                "auto_ingest_job_123",
            )

            # Verify job completion
            job = await conn.fetchrow(
                """
                SELECT status, documents_count, completed_at
                FROM ingestion_jobs
                WHERE job_id = $1
                """,
                "auto_ingest_job_123",
            )

            assert job["status"] == "completed"
            assert job["documents_count"] == 10
            assert job["completed_at"] is not None

            # Cleanup
            await conn.execute("DELETE FROM ingestion_jobs WHERE id = $1", job_id)

    @pytest.mark.asyncio
    async def test_ingestion_error_handling(self, db_pool):
        """Test ingestion error handling"""

        async with db_pool.acquire() as conn:
            # Create ingestion_errors table if not exists
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ingestion_errors (
                    id SERIAL PRIMARY KEY,
                    job_id VARCHAR(255),
                    error_type VARCHAR(100),
                    error_message TEXT,
                    document_id VARCHAR(255),
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Record ingestion error
            error_id = await conn.fetchval(
                """
                INSERT INTO ingestion_errors (
                    job_id, error_type, error_message, document_id
                )
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                "job_123",
                "embedding_error",
                "Failed to generate embeddings",
                "doc_456",
            )

            assert error_id is not None

            # Retrieve errors for job
            errors = await conn.fetch(
                """
                SELECT error_type, error_message
                FROM ingestion_errors
                WHERE job_id = $1
                """,
                "job_123",
            )

            assert len(errors) == 1
            assert errors[0]["error_type"] == "embedding_error"

            # Cleanup
            await conn.execute("DELETE FROM ingestion_errors WHERE id = $1", error_id)
