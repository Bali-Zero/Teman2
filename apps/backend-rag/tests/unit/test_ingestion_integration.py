"""
Integration Tests for Ingestion Logging and Metrics
Tests the complete integration of structured logging and metrics tracking
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.app.metrics import metrics_collector
from backend.services.ingestion.ingestion_logger import IngestionLogger, IngestionStage
from backend.services.ingestion.scraper_normalizer import NormalizationConfig, ScraperDataNormalizer


class TestIngestionLoggingIntegration:
    """Test integration of structured logging with ingestion services"""

    def test_logger_initialization(self):
        """Test logger initialization and configuration"""
        logger = IngestionLogger("test_service")

        assert logger.service_name == "test_service"
        assert logger.logger is not None
        assert logger.std_logger is not None

    def test_start_ingestion_logging(self):
        """Test ingestion start logging"""
        logger = IngestionLogger("test")

        document_id = logger.start_ingestion(
            file_path="/path/to/test.pdf",
            source="file_upload",
            trace_id="trace_123",
            user_id="user_456",
        )

        assert document_id is not None
        assert "doc_" in document_id

    def test_parsing_success_logging(self):
        """Test parsing success logging"""
        logger = IngestionLogger("test")

        logger.parsing_success(
            document_id="doc_123",
            file_path="/path/to/test.pdf",
            text_length=5000,
            duration_ms=150.5,
            source="file_upload",
            trace_id="trace_123",
        )
        # Should not raise any exceptions

    def test_parsing_error_logging(self):
        """Test parsing error logging"""
        logger = IngestionLogger("test")

        error = ValueError("PDF parsing failed")
        logger.parsing_error(
            document_id="doc_123",
            file_path="/path/to/test.pdf",
            error=error,
            source="file_upload",
            trace_id="trace_123",
        )
        # Should not raise any exceptions

    def test_ingestion_completion_logging(self):
        """Test ingestion completion logging"""
        logger = IngestionLogger("test")

        logger.ingestion_completed(
            document_id="doc_123",
            file_path="/path/to/test.pdf",
            chunks_created=10,
            collection_name="legal_unified",
            tier="A",
            total_duration_ms=5000.0,
            source="file_upload",
            trace_id="trace_123",
            user_id="user_456",
        )
        # Should not raise any exceptions

    def test_ingestion_failure_logging(self):
        """Test ingestion failure logging"""
        logger = IngestionLogger("test")

        error = Exception("Processing failed")
        logger.ingestion_failed(
            document_id="doc_123",
            file_path="/path/to/test.pdf",
            error=error,
            stage=IngestionStage.PARSING,
            duration_ms=2000.0,
            source="file_upload",
            trace_id="trace_123",
            user_id="user_456",
        )
        # Should not raise any exceptions

    def test_scraper_data_normalization_logging(self):
        """Test scraper data normalization logging"""
        logger = IngestionLogger("test")

        normalized_fields = {"title": "Test Article", "content": "Test content", "category": "news"}

        logger.scraper_data_normalized(
            document_id="news_123",
            source_url="https://example.com/article",
            normalized_fields=normalized_fields,
            duration_ms=100.5,
            trace_id="trace_123",
        )
        # Should not raise any exceptions


class TestMetricsIntegration:
    """Test integration of metrics with ingestion services"""

    def test_document_ingested_metrics(self):
        """Test document ingestion metrics recording"""
        metrics_collector.record_document_ingested(
            source="file_upload",
            file_type=".pdf",
            collection="legal_unified",
            status="success",
            chunks_created=15,
        )
        # Should not raise any exceptions

    def test_parsing_duration_metrics(self):
        """Test parsing duration metrics recording"""
        metrics_collector.record_parsing_duration(
            file_type=".pdf", source="file_upload", duration_seconds=2.5
        )
        # Should not raise any exceptions

    def test_parsing_error_metrics(self):
        """Test parsing error metrics recording"""
        metrics_collector.record_parsing_error(
            file_type=".pdf", error_type="CorruptFileError", source="file_upload"
        )
        # Should not raise any exceptions

    def test_document_processing_duration_metrics(self):
        """Test document processing duration metrics"""
        metrics_collector.record_document_processing_duration(
            source="file_upload", collection="legal_unified", duration_seconds=10.5
        )
        # Should not raise any exceptions

    def test_scraper_data_normalized_metrics(self):
        """Test scraper data normalization metrics"""
        metrics_collector.record_scraper_data_normalized(
            scraper_type="news", source="rss_feed", status="success", duration_seconds=0.5
        )
        # Should not raise any exceptions

    def test_scraper_normalization_error_metrics(self):
        """Test scraper normalization error metrics"""
        metrics_collector.record_scraper_normalization_error(
            scraper_type="visa", error_type="ValidationError"
        )
        # Should not raise any exceptions


class TestScraperNormalizerIntegration:
    """Test scraper normalizer with logging and metrics integration"""

    @pytest.mark.asyncio
    async def test_news_article_normalization_success(self):
        """Test successful news article normalization"""
        normalizer = ScraperDataNormalizer()

        raw_data = {
            "title": "Test News Article",
            "content": "This is a test news article with sufficient content to pass validation. "
            * 10,
            "url": "https://example.com/news/test",
            "published_date": "2024-01-15",
            "source": "Test News",
            "author": "Test Author",
            "tags": ["test", "news", "article"],
            "category": "technology",
            "language": "en",
            "confidence_score": 0.9,
        }

        result = await normalizer.normalize_news_article(
            raw_data, source="test_scraper", trace_id="test_trace"
        )

        # Verify normalized structure
        assert "id" in result
        assert result["data_type"] == "news_article"
        assert result["title"] == "Test News Article"
        assert len(result["content"]) > 100
        assert result["quality_score"] > 0.5
        assert "content_hash" in result
        assert "normalized_at" in result

        # Verify it was tracked
        assert len(normalizer.processed_items) == 1
        assert normalizer.processed_items[0] == result
        assert len(normalizer.errors) == 0

    @pytest.mark.asyncio
    async def test_visa_information_normalization_success(self):
        """Test successful visa information normalization"""
        normalizer = ScraperDataNormalizer()

        raw_data = {
            "visa_type": "Tourist Visa",
            "description": "For tourism purposes only",
            "requirements": ["Valid passport", "Proof of funds", "Return ticket"],
            "processing_time": "5-7 business days",
            "fees": "USD 50",
            "validity": "30 days",
            "source_url": "https://immigration.gov.id/tourist-visa",
            "country": "Indonesia",
            "scraper_type": "government_site",
        }

        result = await normalizer.normalize_visa_information(
            raw_data, source="gov_scraper", trace_id="visa_trace"
        )

        # Verify normalized structure
        assert "id" in result
        assert result["data_type"] == "visa_info"
        assert result["visa_type"] == "Tourist Visa"
        assert isinstance(result["requirements"], list)
        assert len(result["requirements"]) == 3
        assert result["fees"]["currency"] == "USD"
        assert result["fees"]["amount"] == 50
        assert result["processing_time"]["days_min"] == 5
        assert result["processing_time"]["days_max"] == 7

        # Verify it was tracked
        assert len(normalizer.processed_items) == 1
        assert len(normalizer.errors) == 0

    @pytest.mark.asyncio
    async def test_normalization_error_handling(self):
        """Test normalization error handling"""
        normalizer = ScraperDataNormalizer()

        # Missing required fields
        invalid_data = {
            "title": "",  # Empty title
            "content": "Too short",  # Too short content
        }

        with pytest.raises(ValueError, match="Missing required fields"):
            await normalizer.normalize_news_article(invalid_data)

        # Verify error was tracked
        assert len(normalizer.errors) == 1
        assert "Missing required fields" in normalizer.errors[0]["error"]

    def test_duplicate_detection(self):
        """Test duplicate detection functionality"""
        normalizer = ScraperDataNormalizer()

        # Create items with duplicates
        items = [
            {
                "id": "item1",
                "title": "Same Title",
                "content": "Same content",
                "url": "https://example.com/1",
                "content_hash": "abc123",
            },
            {
                "id": "item2",
                "title": "Same Title",
                "content": "Same content",
                "url": "https://example.com/2",
                "content_hash": "abc123",  # Same hash
            },
            {
                "id": "item3",
                "title": "Different Title",
                "content": "Different content",
                "url": "https://example.com/3",
                "content_hash": "def456",
            },
        ]

        duplicates = normalizer.detect_duplicates(items)

        # Should detect one duplicate
        assert len(duplicates) == 1
        assert duplicates[0]["id"] == "item2"
        assert len(normalizer.duplicates_detected) == 1

    def test_get_statistics(self):
        """Test statistics generation"""
        normalizer = ScraperDataNormalizer()

        # Add some processed items
        normalizer.processed_items = [
            {"data_type": "news_article", "quality_score": 0.8},
            {"data_type": "visa_info", "quality_score": 0.9},
            {"data_type": "news_article", "quality_score": 0.7},
        ]

        normalizer.duplicates_detected = [{"id": "dup1"}]
        normalizer.errors = [{"error": "test error"}]

        stats = normalizer.get_statistics()

        assert stats["total_processed"] == 3
        assert stats["duplicates_detected"] == 1
        assert stats["errors"] == 1
        assert stats["success_rate"] == 75.0  # 3/(3+1) * 100
        assert "news_article" in stats["data_types"]
        assert "visa_info" in stats["data_types"]
        assert stats["average_quality_score"] == 0.8  # (0.8+0.9+0.7)/3


class TestEndToEndIntegration:
    """Test end-to-end integration of logging and metrics"""

    @pytest.mark.asyncio
    async def test_complete_pipeline_integration(self):
        """Test complete pipeline with logging and metrics"""
        # Mock the metrics collector to avoid actual prometheus calls
        with patch.object(metrics_collector, "record_scraper_data_normalized") as mock_metrics:
            normalizer = ScraperDataNormalizer()

            raw_data = {
                "title": "Integration Test Article",
                "content": "This is a comprehensive test article for integration testing. " * 20,
                "url": "https://example.com/integration-test",
                "published_date": "2024-01-15",
                "source": "Integration Test Source",
                "author": "Test Author",
                "tags": ["integration", "test", "logging"],
                "category": "testing",
                "language": "en",
                "confidence_score": 0.95,
            }

            # Process the data
            result = await normalizer.normalize_news_article(
                raw_data, source="integration_test", trace_id="e2e_trace"
            )

            # Verify metrics were called
            mock_metrics.assert_called_once()
            call_args = mock_metrics.call_args
            assert call_args[1]["scraper_type"] == "news"
            assert call_args[1]["status"] == "success"
            assert call_args[1]["duration_seconds"] > 0

            # Verify result structure
            assert result["data_type"] == "news_article"
            assert result["quality_score"] > 0.8
            assert "content_hash" in result
            assert "normalized_at" in result

            # Verify tracking
            assert len(normalizer.processed_items) == 1
            assert len(normalizer.errors) == 0

    def test_error_pipeline_integration(self):
        """Test error handling in pipeline integration"""
        with patch.object(
            metrics_collector, "record_scraper_normalization_error"
        ) as mock_error_metrics:
            normalizer = ScraperDataNormalizer()

            # This should cause an error
            invalid_data = {"title": None, "content": ""}

            try:
                import asyncio

                asyncio.run(normalizer.normalize_news_article(invalid_data))
                assert False, "Should have raised an exception"
            except ValueError:
                pass  # Expected

            # Verify error metrics were called
            mock_error_metrics.assert_called_once()
            call_args = mock_error_metrics.call_args
            assert call_args[1]["scraper_type"] == "news"
            assert "ValueError" in call_args[1]["error_type"]

            # Verify error tracking
            assert len(normalizer.errors) == 1
            assert len(normalizer.processed_items) == 0


class TestConfigurationAndCustomization:
    """Test configuration and customization options"""

    def test_custom_configuration(self):
        """Test custom normalization configuration"""
        config = NormalizationConfig(
            enable_content_cleaning=False,
            min_content_length=100,
            required_fields=["title", "content", "author"],
        )

        normalizer = ScraperDataNormalizer(config)

        assert normalizer.config.enable_content_cleaning is False
        assert normalizer.config.min_content_length == 100
        assert "author" in normalizer.config.required_fields

    def test_content_cleaning_configuration(self):
        """Test content cleaning configuration"""
        config = NormalizationConfig(enable_content_cleaning=False)
        normalizer = ScraperDataNormalizer(config)

        dirty_text = "  <p>Dirty   text with   <b>HTML</b> tags!</p>  "
        cleaned = normalizer._clean_text(dirty_text)

        # With cleaning disabled, should be basic cleanup only
        assert "Dirty text with HTML tags!" == cleaned

    def test_duplicate_detection_configuration(self):
        """Test duplicate detection configuration"""
        config = NormalizationConfig(enable_duplicate_detection=False)
        normalizer = ScraperDataNormalizer(config)

        items = [{"content_hash": "same", "url": "url1"}, {"content_hash": "same", "url": "url2"}]

        duplicates = normalizer.detect_duplicates(items)
        assert len(duplicates) == 0  # Detection disabled


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
