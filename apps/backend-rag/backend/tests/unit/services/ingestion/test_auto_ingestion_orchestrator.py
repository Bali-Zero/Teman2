"""
Unit tests for AutoIngestionOrchestrator
Target: >99% coverage
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.services.ingestion.auto_ingestion_orchestrator import (
    AutoIngestionOrchestrator,
    IngestionStatus,
    MonitoredSource,
    ScrapedContent,
    SourceType,
    UpdateType,
)


@pytest.fixture
def auto_ingestion_orchestrator():
    """Create AutoIngestionOrchestrator instance"""
    return AutoIngestionOrchestrator()


class TestAutoIngestionOrchestrator:
    """Tests for AutoIngestionOrchestrator"""

    def test_init(self, auto_ingestion_orchestrator):
        """Test initialization"""
        assert auto_ingestion_orchestrator is not None
        assert isinstance(auto_ingestion_orchestrator.sources, dict)
        assert len(auto_ingestion_orchestrator.sources) > 0  # Default sources
        assert isinstance(auto_ingestion_orchestrator.jobs, dict)
        assert isinstance(auto_ingestion_orchestrator.content_hashes, set)

    def test_init_with_services(self):
        """Test initialization with services"""
        mock_search = MagicMock()
        mock_zantara = MagicMock()
        mock_scraper = MagicMock()

        orchestrator = AutoIngestionOrchestrator(
            search_service=mock_search,
            claude_service=mock_zantara,
            scraper_service=mock_scraper,
        )
        assert orchestrator.search == mock_search
        assert orchestrator.zantara_ai == mock_zantara
        assert orchestrator.scraper == mock_scraper

    def test_add_source(self, auto_ingestion_orchestrator):
        """Test adding monitored source"""
        source = MonitoredSource(
            source_id="test_source",
            source_type=SourceType.GOVERNMENT_WEBSITE,
            name="Test Source",
            url="https://test.com",
            target_collection="visa_oracle",
        )
        auto_ingestion_orchestrator.add_source(source)
        assert "test_source" in auto_ingestion_orchestrator.sources

    def test_get_due_sources_all_due(self, auto_ingestion_orchestrator):
        """Test getting sources due for scraping (never scraped)"""
        sources = auto_ingestion_orchestrator.get_due_sources()
        assert isinstance(sources, list)
        # All default sources should be due (never scraped)
        assert len(sources) > 0

    def test_get_due_sources_enabled_only(self, auto_ingestion_orchestrator):
        """Test getting only enabled sources"""
        # Disable a source
        for source in auto_ingestion_orchestrator.sources.values():
            source.enabled = False
            break

        sources = auto_ingestion_orchestrator.get_due_sources()
        assert len(sources) == 0  # All disabled

    def test_get_due_sources_with_last_scraped(self, auto_ingestion_orchestrator):
        """Test getting sources due based on last_scraped"""
        # Set last_scraped to past (more than frequency hours ago)
        for source in auto_ingestion_orchestrator.sources.values():
            source.last_scraped = (datetime.now() - timedelta(hours=25)).isoformat()
            source.scrape_frequency_hours = 24
            break

        sources = auto_ingestion_orchestrator.get_due_sources()
        assert len(sources) > 0

    def test_get_due_sources_not_due(self, auto_ingestion_orchestrator):
        """Test getting sources not due yet"""
        # Set last_scraped to recent (less than frequency hours ago)
        for source in auto_ingestion_orchestrator.sources.values():
            source.last_scraped = (datetime.now() - timedelta(hours=1)).isoformat()
            source.scrape_frequency_hours = 24
            break

        # Count due sources before
        all_due = len([s for s in auto_ingestion_orchestrator.sources.values() if s.enabled])
        sources = auto_ingestion_orchestrator.get_due_sources()
        # Should have fewer due sources now
        assert len(sources) < all_due

    @pytest.mark.asyncio
    async def test_scrape_source_no_scraper(self, auto_ingestion_orchestrator):
        """Test scraping without scraper service"""
        source = MonitoredSource(
            source_id="test_source",
            source_type=SourceType.GOVERNMENT_WEBSITE,
            name="Test Source",
            url="https://test.com",
            target_collection="visa_oracle",
        )

        with pytest.raises(ValueError, match="Scraper service not configured"):
            await auto_ingestion_orchestrator.scrape_source(source)

    @pytest.mark.asyncio
    async def test_scrape_source_with_scraper(self, auto_ingestion_orchestrator):
        """Test scraping with scraper service"""
        mock_scraper = AsyncMock()
        mock_scraper.scrape.return_value = [
            {
                "title": "Test Article",
                "content": "Test content",
                "url": "https://test.com/article",
                "metadata": {},
            }
        ]

        orchestrator = AutoIngestionOrchestrator(scraper_service=mock_scraper)
        source = MonitoredSource(
            source_id="test_source",
            source_type=SourceType.GOVERNMENT_WEBSITE,
            name="Test Source",
            url="https://test.com",
            target_collection="visa_oracle",
        )

        results = await orchestrator.scrape_source(source)
        assert len(results) == 1
        assert isinstance(results[0], ScrapedContent)
        assert results[0].title == "Test Article"
        assert source.last_scraped is not None

    @pytest.mark.asyncio
    async def test_scrape_source_error(self, auto_ingestion_orchestrator):
        """Test scraping with scraper error"""
        mock_scraper = AsyncMock()
        mock_scraper.scrape.side_effect = Exception("Scraping failed")

        orchestrator = AutoIngestionOrchestrator(scraper_service=mock_scraper)
        source = MonitoredSource(
            source_id="test_source",
            source_type=SourceType.GOVERNMENT_WEBSITE,
            name="Test Source",
            url="https://test.com",
            target_collection="visa_oracle",
        )

        with pytest.raises(Exception, match="Scraping failed"):
            await orchestrator.scrape_source(source)

    @pytest.mark.asyncio
    async def test_filter_content_tier1_only(self, auto_ingestion_orchestrator):
        """Test filtering content with tier 1 only (no zantara_ai)"""
        content = ScrapedContent(
            content_id="test1",
            source_id="test_source",
            title="New Regulation",
            content="This is a new regulation about taxes",
            url="https://test.com",
            scraped_at=datetime.now().isoformat(),
        )

        results = await auto_ingestion_orchestrator.filter_content([content])
        assert len(results) == 1  # Should pass keyword filter

    @pytest.mark.asyncio
    async def test_filter_content_no_keywords(self, auto_ingestion_orchestrator):
        """Test filtering content with no keywords"""
        content = ScrapedContent(
            content_id="test1",
            source_id="test_source",
            title="Random Article",
            content="This is a random article about nothing",
            url="https://test.com",
            scraped_at=datetime.now().isoformat(),
        )

        results = await auto_ingestion_orchestrator.filter_content([content])
        assert len(results) == 0  # Should not pass keyword filter

    @pytest.mark.asyncio
    async def test_filter_content_with_zantara_ai(self):
        """Test filtering content with zantara_ai"""
        mock_zantara = AsyncMock()
        mock_zantara.conversational.return_value = {
            "text": "YES, this is a new regulation about taxes.",
        }

        orchestrator = AutoIngestionOrchestrator(claude_service=mock_zantara)
        content = ScrapedContent(
            content_id="test1",
            source_id="test_source",
            title="New Regulation",
            content="This is a new regulation about taxes",
            url="https://test.com",
            scraped_at=datetime.now().isoformat(),
        )

        results = await orchestrator.filter_content([content])
        assert len(results) == 1
        assert results[0].update_type == UpdateType.NEW_REGULATION
        assert results[0].relevance_score > 0

    @pytest.mark.asyncio
    async def test_filter_content_zantara_ai_no(self):
        """Test filtering content with zantara_ai saying NO"""
        mock_zantara = AsyncMock()
        mock_zantara.conversational.return_value = {
            "text": "NO, this is not relevant.",
        }

        orchestrator = AutoIngestionOrchestrator(claude_service=mock_zantara)
        content = ScrapedContent(
            content_id="test1",
            source_id="test_source",
            title="New Regulation",
            content="This is a new regulation about taxes",
            url="https://test.com",
            scraped_at=datetime.now().isoformat(),
        )

        results = await orchestrator.filter_content([content])
        assert len(results) == 0  # Should be filtered out

    @pytest.mark.asyncio
    async def test_filter_content_zantara_ai_error(self):
        """Test filtering content with zantara_ai error"""
        mock_zantara = AsyncMock()
        mock_zantara.conversational.side_effect = Exception("AI error")

        orchestrator = AutoIngestionOrchestrator(claude_service=mock_zantara)
        content = ScrapedContent(
            content_id="test1",
            source_id="test_source",
            title="New Regulation",
            content="This is a new regulation about taxes",
            url="https://test.com",
            scraped_at=datetime.now().isoformat(),
        )

        # Should include by default if error
        results = await orchestrator.filter_content([content])
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_ingest_content_no_search(self, auto_ingestion_orchestrator):
        """Test ingesting content without search service"""
        content = ScrapedContent(
            content_id="test1",
            source_id="oss_kbli",
            title="Test",
            content="Test content",
            url="https://test.com",
            scraped_at=datetime.now().isoformat(),
        )

        count = await auto_ingestion_orchestrator.ingest_content([content])
        assert count == 0

    @pytest.mark.asyncio
    async def test_ingest_content_with_duplicates(self, auto_ingestion_orchestrator):
        """Test ingesting content with duplicates"""
        mock_search = MagicMock()
        orchestrator = AutoIngestionOrchestrator(search_service=mock_search)

        content = ScrapedContent(
            content_id="test1",
            source_id="oss_kbli",
            title="Test",
            content="Test content",
            url="https://test.com",
            scraped_at=datetime.now().isoformat(),
        )

        # Add to hash set (simulate duplicate)
        orchestrator.content_hashes.add("test1")

        count = await orchestrator.ingest_content([content])
        assert count == 0  # Duplicate should be skipped

    @pytest.mark.asyncio
    async def test_ingest_content_unknown_source(self, auto_ingestion_orchestrator):
        """Test ingesting content with unknown source"""
        mock_search = MagicMock()
        orchestrator = AutoIngestionOrchestrator(search_service=mock_search)

        content = ScrapedContent(
            content_id="test1",
            source_id="unknown_source",
            title="Test",
            content="Test content",
            url="https://test.com",
            scraped_at=datetime.now().isoformat(),
        )

        count = await orchestrator.ingest_content([content])
        assert count == 0  # Unknown source should be skipped

    @pytest.mark.asyncio
    async def test_run_ingestion_job_unknown_source(self, auto_ingestion_orchestrator):
        """Test running ingestion job with unknown source"""
        with pytest.raises(ValueError, match="Unknown source"):
            await auto_ingestion_orchestrator.run_ingestion_job("unknown_source")

    @pytest.mark.asyncio
    async def test_run_ingestion_job_success(self):
        """Test running successful ingestion job"""
        mock_scraper = AsyncMock()
        mock_scraper.scrape.return_value = [
            {
                "title": "New Regulation",
                "content": "This is a new regulation",
                "url": "https://test.com",
                "metadata": {},
            }
        ]

        mock_search = MagicMock()
        orchestrator = AutoIngestionOrchestrator(
            scraper_service=mock_scraper, search_service=mock_search
        )

        # Use a default source
        source_id = list(orchestrator.sources.keys())[0]
        job = await orchestrator.run_ingestion_job(source_id)

        assert job.status == IngestionStatus.COMPLETED
        assert job.items_scraped > 0
        assert job.job_id in orchestrator.jobs

    @pytest.mark.asyncio
    async def test_run_ingestion_job_failure(self):
        """Test running ingestion job with failure"""
        mock_scraper = AsyncMock()
        mock_scraper.scrape.side_effect = Exception("Scraping failed")

        orchestrator = AutoIngestionOrchestrator(scraper_service=mock_scraper)

        source_id = list(orchestrator.sources.keys())[0]
        job = await orchestrator.run_ingestion_job(source_id)

        assert job.status == IngestionStatus.FAILED
        assert job.error is not None
        assert orchestrator.orchestrator_stats["failed_jobs"] > 0

    @pytest.mark.asyncio
    async def test_run_scheduled_ingestion(self, auto_ingestion_orchestrator):
        """Test running scheduled ingestion"""
        # All sources should be due (never scraped)
        jobs = await auto_ingestion_orchestrator.run_scheduled_ingestion()
        # Should return empty list (no scraper configured, so all fail)
        assert isinstance(jobs, list)

    @pytest.mark.asyncio
    async def test_run_scheduled_ingestion_no_due(self, auto_ingestion_orchestrator):
        """Test running scheduled ingestion with no due sources"""
        # Disable all sources
        for source in auto_ingestion_orchestrator.sources.values():
            source.enabled = False

        jobs = await auto_ingestion_orchestrator.run_scheduled_ingestion()
        assert jobs == []

    def test_generate_content_id(self, auto_ingestion_orchestrator):
        """Test generating content ID"""
        content = "Test content"
        content_id = auto_ingestion_orchestrator._generate_content_id(content)
        assert isinstance(content_id, str)
        assert len(content_id) == 32  # MD5 hash length

    def test_get_job_status(self, auto_ingestion_orchestrator):
        """Test getting job status"""
        from backend.services.ingestion.auto_ingestion_orchestrator import IngestionJob

        job = IngestionJob(
            job_id="test_job",
            source_id="test_source",
            status=IngestionStatus.PENDING,
            started_at=datetime.now().isoformat(),
        )
        auto_ingestion_orchestrator.jobs["test_job"] = job

        result = auto_ingestion_orchestrator.get_job_status("test_job")
        assert result == job

    def test_get_job_status_not_found(self, auto_ingestion_orchestrator):
        """Test getting job status for non-existent job"""
        result = auto_ingestion_orchestrator.get_job_status("nonexistent")
        assert result is None

    def test_get_orchestrator_stats(self, auto_ingestion_orchestrator):
        """Test getting orchestrator statistics"""
        stats = auto_ingestion_orchestrator.get_orchestrator_stats()
        assert isinstance(stats, dict)
        assert "total_jobs" in stats
        assert "success_rate" in stats
        assert "sources_monitored" in stats
        assert "sources_enabled" in stats
