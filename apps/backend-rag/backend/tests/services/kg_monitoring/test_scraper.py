"""
Tests for LegalScraper - Phase 8
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.kg_monitoring.scraper import (
    LegalScraper,
    ScrapedDocument,
    SourceConfig,
    SourceType,
)


class TestScrapedDocument:
    """Test ScrapedDocument dataclass"""

    def test_document_creation(self):
        """Test creating a scraped document"""
        doc = ScrapedDocument(
            document_id="test123",
            source_id="jdih_kemenkumham",
            title="Test Regulation",
            url="https://example.com/doc",
            content="Test content",
            raw_html="<html>Test</html>",
            scraped_at=datetime.now(tz=timezone.utc),
        )

        assert doc.document_id == "test123"
        assert doc.source_id == "jdih_kemenkumham"
        assert doc.title == "Test Regulation"
        assert doc.document_hash != ""  # Auto-generated

    def test_document_hash_generation(self):
        """Test that document hash is generated from content"""
        doc1 = ScrapedDocument(
            document_id="doc1",
            source_id="test",
            title="Same Title",
            url="https://example.com/1",
            content="Same content",
            raw_html="<p>Same</p>",
            scraped_at=datetime.now(tz=timezone.utc),
        )

        doc2 = ScrapedDocument(
            document_id="doc2",
            source_id="test",
            title="Same Title",
            url="https://example.com/2",
            content="Same content",
            raw_html="<p>Same</p>",
            scraped_at=datetime.now(tz=timezone.utc),
        )

        # Same title and content should produce same hash
        assert doc1.document_hash == doc2.document_hash

    def test_different_content_different_hash(self):
        """Test that different content produces different hashes"""
        doc1 = ScrapedDocument(
            document_id="doc1",
            source_id="test",
            title="Title A",
            url="https://example.com/1",
            content="Content A",
            raw_html="<p>A</p>",
            scraped_at=datetime.now(tz=timezone.utc),
        )

        doc2 = ScrapedDocument(
            document_id="doc2",
            source_id="test",
            title="Title B",
            url="https://example.com/2",
            content="Content B",
            raw_html="<p>B</p>",
            scraped_at=datetime.now(tz=timezone.utc),
        )

        assert doc1.document_hash != doc2.document_hash


class TestSourceConfig:
    """Test SourceConfig dataclass"""

    def test_default_values(self):
        """Test default configuration values"""
        config = SourceConfig(
            source_id="test_source",
            name="Test Source",
            base_url="https://example.com",
            source_type=SourceType.LEGAL_DATABASE,
        )

        assert config.rate_limit_delay == 1.0
        assert config.timeout == 30
        assert config.max_retries == 3
        assert config.enabled is True
        assert "User-Agent" in config.headers


class TestLegalScraper:
    """Test LegalScraper functionality"""

    def test_initialization(self):
        """Test scraper initialization"""
        scraper = LegalScraper()

        assert len(scraper.sources) == 2
        assert "jdih_kemenkumham" in scraper.sources
        assert "peraturan_bpk" in scraper.sources

    def test_custom_sources(self):
        """Test scraper with custom sources"""
        custom = {
            "custom_source": SourceConfig(
                source_id="custom_source",
                name="Custom",
                base_url="https://custom.com",
                source_type=SourceType.GOVERNMENT_SITE,
            ),
        }
        scraper = LegalScraper(custom_sources=custom)

        assert len(scraper.sources) == 1
        assert "custom_source" in scraper.sources

    def test_add_source(self):
        """Test adding a source"""
        scraper = LegalScraper()
        new_source = SourceConfig(
            source_id="new_source",
            name="New Source",
            base_url="https://new.com",
            source_type=SourceType.GOVERNMENT_SITE,
        )

        scraper.add_source(new_source)

        assert "new_source" in scraper.sources
        assert scraper.sources["new_source"].name == "New Source"

    def test_disable_enable_source(self):
        """Test disabling and enabling sources"""
        scraper = LegalScraper()

        scraper.disable_source("jdih_kemenkumham")
        assert scraper.sources["jdih_kemenkumham"].enabled is False

        scraper.enable_source("jdih_kemenkumham")
        assert scraper.sources["jdih_kemenkumham"].enabled is True

    def test_get_stats(self):
        """Test getting scraper statistics"""
        scraper = LegalScraper()
        stats = scraper.get_stats()

        assert "total_requests" in stats
        assert "successful_requests" in stats
        assert "documents_found" in stats
        assert stats["sources_configured"] == 2
        assert stats["sources_enabled"] == 2

    @pytest.mark.asyncio
    async def test_scrape_source_disabled(self):
        """Test scraping a disabled source returns empty"""
        scraper = LegalScraper()
        scraper.disable_source("jdih_kemenkumham")

        result = await scraper.scrape_source("jdih_kemenkumham")
        assert result == []

    @pytest.mark.asyncio
    async def test_scrape_source_unknown(self):
        """Test scraping unknown source raises error"""
        scraper = LegalScraper()

        with pytest.raises(ValueError, match="Unknown source"):
            await scraper.scrape_source("unknown_source")

    def test_build_search_url(self):
        """Test URL building with pagination"""
        scraper = LegalScraper()
        source = scraper.sources["jdih_kemenkumham"]

        url = scraper._build_search_url(source, "/arsip/cari", 1, 10)
        assert "page=1" in url
        assert "per_page=10" in url

    def test_generate_document_id(self):
        """Test document ID generation"""
        scraper = LegalScraper()

        id1 = scraper._generate_document_id("test content")
        id2 = scraper._generate_document_id("test content")
        id3 = scraper._generate_document_id("different content")

        assert id1 == id2  # Same content = same ID
        assert id1 != id3  # Different content = different ID
        assert len(id1) == 16  # MD5 hex, truncated to 16 chars

    @pytest.mark.asyncio
    async def test_fetch_with_retry_success(self):
        """Test successful fetch with retry"""
        scraper = LegalScraper()
        source = scraper.sources["jdih_kemenkumham"]

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.text = "<html>Test</html>"

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        result = await scraper._fetch_with_retry(mock_client, "https://test.com", source)

        assert result == mock_response
        assert scraper.scrape_stats["successful_requests"] == 1

    @pytest.mark.asyncio
    async def test_fetch_with_retry_failure(self):
        """Test fetch that fails after retries"""
        scraper = LegalScraper()
        source = scraper.sources["jdih_kemenkumham"]
        source.max_retries = 2

        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection failed")

        result = await scraper._fetch_with_retry(mock_client, "https://test.com", source)

        assert result is None
        assert scraper.scrape_stats["failed_requests"] == 2
