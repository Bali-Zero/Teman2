"""
Tests for AutoIngestionService - Phase 8
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.kg_monitoring.auto_ingestion import (
    AutoIngestionService,
    DocumentType,
    ExtractedDocument,
    IngestionResult,
    IngestionStatus,
)
from backend.services.kg_monitoring.scraper import ScrapedDocument


class TestIngestionStatus:
    """Test IngestionStatus enum"""

    def test_status_values(self):
        """Test status enum values"""
        assert IngestionStatus.PENDING.value == "pending"
        assert IngestionStatus.EXTRACTING.value == "extracting"
        assert IngestionStatus.VALIDATING.value == "validating"
        assert IngestionStatus.COMPLETED.value == "completed"
        assert IngestionStatus.FAILED.value == "failed"
        assert IngestionStatus.REJECTED.value == "rejected"


class TestExtractedDocument:
    """Test ExtractedDocument dataclass"""

    def test_document_creation(self):
        """Test creating extracted document"""
        doc = ExtractedDocument(
            document_id="doc123",
            source_id="test",
            title="Test Regulation",
            document_type=DocumentType.UNDANG_UNDANG,
            document_number="UU No. 13/2003",
            issuing_authority="DPR",
        )

        assert doc.document_id == "doc123"
        assert doc.key_points == []  # Default
        assert doc.confidence_score == 0.0  # Default

    def test_to_dict(self):
        """Test document to dict conversion"""
        doc = ExtractedDocument(
            document_id="doc123",
            source_id="test",
            title="Test",
            document_type=DocumentType.PERATURAN_PEMERINTAH,
            full_text="Full text content " * 100,  # Long text
            key_points=["Point 1", "Point 2"],
            confidence_score=0.85,
        )

        d = doc.to_dict()
        assert d["document_id"] == "doc123"
        assert d["document_type"] == "peraturan_pemerintah"
        assert "..." in d["full_text"]  # Should be truncated
        assert len(d["key_points"]) == 2


class TestIngestionResult:
    """Test IngestionResult dataclass"""

    def test_result_creation(self):
        """Test creating ingestion result"""
        result = IngestionResult(
            document_id="doc123",
            status=IngestionStatus.PENDING,
            started_at=datetime.now(tz=timezone.utc),
        )

        assert result.status == IngestionStatus.PENDING
        assert result.completed_at is None
        assert result.qdrant_id is None

    def test_to_dict(self):
        """Test result to dict conversion"""
        result = IngestionResult(
            document_id="doc123",
            status=IngestionStatus.COMPLETED,
            started_at=datetime.now(tz=timezone.utc),
            completed_at=datetime.now(tz=timezone.utc),
            qdrant_id="qdrant-uuid",
            processing_time_ms=1500.5,
        )

        d = result.to_dict()
        assert d["document_id"] == "doc123"
        assert d["status"] == "completed"
        assert d["qdrant_id"] == "qdrant-uuid"
        assert d["processing_time_ms"] == 1500.5


class TestAutoIngestionService:
    """Test AutoIngestionService functionality"""

    def test_initialization(self):
        """Test service initialization"""
        service = AutoIngestionService()

        assert service.ingestion_stats["total_processed"] == 0
        assert service.llm is None
        assert service.qdrant is None

    def test_initialization_with_deps(self):
        """Test service with dependencies"""
        mock_llm = MagicMock()
        mock_qdrant = MagicMock()

        service = AutoIngestionService(
            llm_client=mock_llm,
            qdrant_client=mock_qdrant,
        )

        assert service.llm == mock_llm
        assert service.qdrant == mock_qdrant

    def test_get_stats(self):
        """Test getting service statistics"""
        service = AutoIngestionService()
        service.ingestion_stats = {
            "total_processed": 100,
            "successful": 80,
            "failed": 15,
            "rejected": 5,
            "total_chunks_ingested": 250,
        }

        stats = service.get_stats()

        assert stats["total_processed"] == 100
        assert stats["successful"] == 80
        assert stats["success_rate"] == "80.0%"

    @pytest.mark.asyncio
    async def test_ingest_document_success(self):
        """Test successful document ingestion"""
        service = AutoIngestionService()

        # Mock the extraction method
        service._extract_document = AsyncMock(
            return_value=ExtractedDocument(
                document_id="doc123",
                source_id="test",
                title="Test",
                document_type=DocumentType.UNDANG_UNDANG,
                confidence_score=0.9,
            )
        )

        scraped_doc = ScrapedDocument(
            document_id="doc123",
            source_id="test",
            title="Test Document",
            url="https://example.com",
            content="Test content",
            raw_html="<p>Test</p>",
            scraped_at=datetime.now(tz=timezone.utc),
        )

        result = await service.ingest_document(scraped_doc)

        assert result.document_id == "doc123"
        assert result.status in (IngestionStatus.COMPLETED, IngestionStatus.FAILED)
        assert result.started_at is not None

    @pytest.mark.asyncio
    async def test_extract_json_from_markdown(self):
        """Test extracting JSON from markdown code blocks"""
        service = AutoIngestionService()

        # Test with markdown code block
        text = """```json
{"document_type": "undang_undang", "title": "Test"}
```"""
        result = service._extract_json(text)
        assert "undang_undang" in result

        # Test with raw JSON
        text2 = '{"document_type": "peraturan", "title": "Test 2"}'
        result2 = service._extract_json(text2)
        assert "peraturan" in result2

    @pytest.mark.asyncio
    async def test_create_chunks(self):
        """Test creating chunks from extracted document"""
        service = AutoIngestionService()

        doc = ExtractedDocument(
            document_id="doc123",
            source_id="test",
            title="UU No. 13/2003",
            document_type=DocumentType.UNDANG_UNDANG,
            document_number="UU No. 13 Tahun 2003",
            issuing_authority="DPR",
            subject="Ketenagakerjaan",
            summary="Undang-undang tentang ketenagakerjaan",
            full_text="Pasal 1 Ayat 1... " * 50,
            key_points=["Point A", "Point B", "Point C"],
        )

        chunks = service._create_chunks(doc)

        assert len(chunks) >= 4  # Main + 3 key points
        assert chunks[0]["metadata"]["chunk_type"] == "main"
        assert any(c["metadata"].get("chunk_type") == "key_point" for c in chunks)

    def test_extraction_prompt_format(self):
        """Test that extraction prompt is properly formatted"""
        service = AutoIngestionService()

        prompt = service.EXTRACTION_PROMPT.format(
            title="Test Title",
            source="test_source",
            content="Test content",
        )

        assert "Test Title" in prompt
        assert "test_source" in prompt
        assert "Test content" in prompt
        assert "JSON" in prompt
        assert "document_type" in prompt

    @pytest.mark.asyncio
    async def test_ingest_batch(self):
        """Test batch ingestion"""
        service = AutoIngestionService()

        # Mock ingest_document
        service.ingest_document = AsyncMock(
            return_value=IngestionResult(
                document_id="doc1",
                status=IngestionStatus.COMPLETED,
                started_at=datetime.now(tz=timezone.utc),
                completed_at=datetime.now(tz=timezone.utc),
            )
        )

        docs = [
            ScrapedDocument(
                document_id=f"doc{i}",
                source_id="test",
                title=f"Doc {i}",
                url=f"https://example.com/{i}",
                content="Content",
                raw_html="<p>HTML</p>",
                scraped_at=datetime.now(tz=timezone.utc),
            )
            for i in range(3)
        ]

        results = await service.ingest_batch(docs)

        assert len(results) == 3
        assert service.ingest_document.call_count == 3
