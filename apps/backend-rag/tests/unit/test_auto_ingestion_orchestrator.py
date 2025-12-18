"""
Unit tests for Auto Ingestion Orchestrator
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure backend is in path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.auto_ingestion_orchestrator import (
    AutoIngestionOrchestrator,
    IngestionJob,
    IngestionStatus,
    MonitoredSource,
    ScrapedContent,
    SourceType,
    UpdateType,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_search_service():
    """Mock SearchService"""
    return MagicMock()


@pytest.fixture
def mock_claude_service():
    """Mock Claude/ZANTARA AI service"""
    mock = MagicMock()
    mock.conversational = AsyncMock(return_value={"text": "YES, this is a new regulation"})
    return mock


@pytest.fixture
def mock_scraper_service():
    """Mock scraper service"""
    mock = MagicMock()
    mock.scrape = AsyncMock(
        return_value=[
            {
                "title": "New Regulation",
                "content": "This is a new regulation update",
                "url": "https://example.com/regulation",
                "metadata": {},
            }
        ]
    )
    return mock


@pytest.fixture
def orchestrator(mock_search_service, mock_claude_service, mock_scraper_service):
    """Create AutoIngestionOrchestrator instance"""
    return AutoIngestionOrchestrator(
        search_service=mock_search_service,
        claude_service=mock_claude_service,
        scraper_service=mock_scraper_service,
    )


# ============================================================================
# Tests for Enums
# ============================================================================


def test_source_type_enum():
    """Test SourceType enum values"""
    assert SourceType.GOVERNMENT_WEBSITE == "government_website"
    assert SourceType.RSS_FEED == "rss_feed"
    assert SourceType.API_ENDPOINT == "api_endpoint"


def test_update_type_enum():
    """Test UpdateType enum values"""
    assert UpdateType.NEW_REGULATION == "new_regulation"
    assert UpdateType.AMENDED_REGULATION == "amended_regulation"
    assert UpdateType.POLICY_CHANGE == "policy_change"


def test_ingestion_status_enum():
    """Test IngestionStatus enum values"""
    assert IngestionStatus.PENDING == "pending"
    assert IngestionStatus.COMPLETED == "completed"
    assert IngestionStatus.FAILED == "failed"


# ============================================================================
# Tests for Dataclasses
# ============================================================================


def test_monitored_source_creation():
    """Test MonitoredSource dataclass creation"""
    source = MonitoredSource(
        source_id="test_source",
        source_type=SourceType.WEB_SCRAPER,
        name="Test Source",
        url="https://example.com",
        target_collection="test_collection",
    )
    assert source.source_id == "test_source"
    assert source.enabled is True
    assert source.scrape_frequency_hours == 24


def test_scraped_content_creation():
    """Test ScrapedContent dataclass creation"""
    content = ScrapedContent(
        content_id="content1",
        source_id="source1",
        title="Test Title",
        content="Test content",
        url="https://example.com",
        scraped_at=datetime.now().isoformat(),
    )
    assert content.content_id == "content1"
    assert content.relevance_score == 0.0


def test_ingestion_job_creation():
    """Test IngestionJob dataclass creation"""
    job = IngestionJob(
        job_id="job1",
        source_id="source1",
        status=IngestionStatus.PENDING,
        started_at=datetime.now().isoformat(),
    )
    assert job.job_id == "job1"
    assert job.items_scraped == 0
    assert job.items_ingested == 0


# ============================================================================
# Tests for AutoIngestionOrchestrator.__init__
# ============================================================================


def test_init(orchestrator):
    """Test AutoIngestionOrchestrator initialization"""
    assert orchestrator.search is not None
    assert orchestrator.zantara_ai is not None  # Updated: was claude, now zantara_ai
    assert orchestrator.scraper is not None
    assert len(orchestrator.sources) > 0
    assert orchestrator.orchestrator_stats["total_jobs"] == 0


def test_init_default_sources(orchestrator):
    """Test that default sources are initialized"""
    assert "oss_kbli" in orchestrator.sources
    assert "ditjen_imigrasi" in orchestrator.sources
    assert orchestrator.sources["oss_kbli"].target_collection == "kbli_comprehensive"


# ============================================================================
# Tests for add_source
# ============================================================================


def test_add_source(orchestrator):
    """Test adding a new source"""
    new_source = MonitoredSource(
        source_id="custom_source",
        source_type=SourceType.RSS_FEED,
        name="Custom RSS Feed",
        url="https://example.com/rss",
        target_collection="custom_collection",
    )

    orchestrator.add_source(new_source)

    assert "custom_source" in orchestrator.sources
    assert orchestrator.sources["custom_source"].name == "Custom RSS Feed"


# ============================================================================
# Tests for get_due_sources
# ============================================================================


def test_get_due_sources_no_last_scraped(orchestrator):
    """Test getting due sources when never scraped"""
    # Reset last_scraped for a source
    source = orchestrator.sources["oss_kbli"]
    source.last_scraped = None

    due_sources = orchestrator.get_due_sources()

    assert len(due_sources) > 0
    assert source in due_sources


def test_get_due_sources_due(orchestrator):
    """Test getting due sources when time has passed"""
    source = orchestrator.sources["oss_kbli"]
    # Set last_scraped to 200 hours ago (more than scrape_frequency_hours=168)
    source.last_scraped = (datetime.now() - timedelta(hours=200)).isoformat()

    due_sources = orchestrator.get_due_sources()

    assert source in due_sources


def test_get_due_sources_not_due(orchestrator):
    """Test getting due sources when not due yet"""
    source = orchestrator.sources["oss_kbli"]
    # Set last_scraped to 1 hour ago (less than scrape_frequency_hours=168)
    source.last_scraped = (datetime.now() - timedelta(hours=1)).isoformat()

    due_sources = orchestrator.get_due_sources()

    assert source not in due_sources


def test_get_due_sources_disabled(orchestrator):
    """Test that disabled sources are not returned"""
    source = orchestrator.sources["oss_kbli"]
    source.enabled = False
    source.last_scraped = None

    due_sources = orchestrator.get_due_sources()

    assert source not in due_sources


# ============================================================================
# Tests for scrape_source
# ============================================================================


@pytest.mark.asyncio
async def test_scrape_source_with_scraper(orchestrator, mock_scraper_service):
    """Test scraping source with scraper service"""
    source = orchestrator.sources["oss_kbli"]

    scraped_items = await orchestrator.scrape_source(source)

    assert len(scraped_items) > 0
    assert isinstance(scraped_items[0], ScrapedContent)
    assert scraped_items[0].source_id == source.source_id
    assert source.last_scraped is not None
    mock_scraper_service.scrape.assert_called_once()


@pytest.mark.asyncio
async def test_scrape_source_without_scraper(orchestrator):
    """Test scraping source without scraper service (demo mode)"""
    orchestrator.scraper = None
    source = orchestrator.sources["oss_kbli"]

    scraped_items = await orchestrator.scrape_source(source)

    assert len(scraped_items) > 0
    assert isinstance(scraped_items[0], ScrapedContent)
    assert "demo" in scraped_items[0].content_id.lower() or "demo" in scraped_items[0].title.lower()


@pytest.mark.asyncio
async def test_scrape_source_scraper_error(orchestrator, mock_scraper_service):
    """Test scraping source when scraper raises error"""
    mock_scraper_service.scrape.side_effect = Exception("Scraping failed")
    source = orchestrator.sources["oss_kbli"]

    scraped_items = await orchestrator.scrape_source(source)

    assert len(scraped_items) == 0


# ============================================================================
# Tests for filter_content
# ============================================================================


@pytest.mark.asyncio
async def test_filter_content_tier1_keyword_match(orchestrator):
    """Test filtering content with keyword match"""
    content_list = [
        ScrapedContent(
            content_id="content1",
            source_id="source1",
            title="New Regulation Update",
            content="This is about peraturan baru",
            url="https://example.com",
            scraped_at=datetime.now().isoformat(),
        ),
        ScrapedContent(
            content_id="content2",
            source_id="source1",
            title="Random News",
            content="This is just regular news",
            url="https://example.com",
            scraped_at=datetime.now().isoformat(),
        ),
    ]

    filtered = await orchestrator.filter_content(content_list)

    assert len(filtered) >= 1
    assert any(
        "regulation" in c.title.lower() or "peraturan" in c.content.lower() for c in filtered
    )


@pytest.mark.asyncio
async def test_filter_content_tier2_with_claude(orchestrator, mock_claude_service):
    """Test filtering content with Tier 2 AI filtering"""
    content_list = [
        ScrapedContent(
            content_id="content1",
            source_id="source1",
            title="New Regulation",
            content="This is a new regulation update",
            url="https://example.com",
            scraped_at=datetime.now().isoformat(),
        ),
    ]

    filtered = await orchestrator.filter_content(content_list)

    assert len(filtered) > 0
    assert mock_claude_service.conversational.called
    assert filtered[0].relevance_score > 0
    assert filtered[0].update_type is not None


@pytest.mark.asyncio
async def test_filter_content_no_zantara_service(orchestrator):
    """Test filtering content without ZANTARA AI service"""
    orchestrator.zantara_ai = None  # Updated: was claude, now zantara_ai
    content_list = [
        ScrapedContent(
            content_id="content1",
            source_id="source1",
            title="New Regulation",
            content="This is a new regulation",
            url="https://example.com",
            scraped_at=datetime.now().isoformat(),
        ),
    ]

    filtered = await orchestrator.filter_content(content_list)

    assert len(filtered) > 0
    # Should only use Tier 1 filtering


# ============================================================================
# Tests for ingest_content
# ============================================================================


@pytest.mark.asyncio
async def test_ingest_content_success(orchestrator):
    """Test ingesting content successfully"""
    source = orchestrator.sources["oss_kbli"]
    content_list = [
        ScrapedContent(
            content_id="content1",
            source_id="oss_kbli",
            title="Test Content",
            content="Test content",
            url="https://example.com",
            scraped_at=datetime.now().isoformat(),
        ),
    ]

    ingested_count = await orchestrator.ingest_content(content_list)

    assert ingested_count == 1
    assert "content1" in orchestrator.content_hashes
    assert orchestrator.orchestrator_stats["items_by_collection"]["kbli_comprehensive"] == 1


@pytest.mark.asyncio
async def test_ingest_content_duplicate(orchestrator):
    """Test ingesting duplicate content"""
    content = ScrapedContent(
        content_id="content1",
        source_id="oss_kbli",
        title="Test Content",
        content="Test content",
        url="https://example.com",
        scraped_at=datetime.now().isoformat(),
    )

    # Add to hashes first
    orchestrator.content_hashes.add("content1")

    ingested_count = await orchestrator.ingest_content([content])

    assert ingested_count == 0


@pytest.mark.asyncio
async def test_ingest_content_no_search_service(orchestrator):
    """Test ingesting content without search service"""
    orchestrator.search = None
    content_list = [
        ScrapedContent(
            content_id="content1",
            source_id="oss_kbli",
            title="Test Content",
            content="Test content",
            url="https://example.com",
            scraped_at=datetime.now().isoformat(),
        ),
    ]

    ingested_count = await orchestrator.ingest_content(content_list)

    assert ingested_count == 0


@pytest.mark.asyncio
async def test_ingest_content_unknown_source(orchestrator):
    """Test ingesting content with unknown source"""
    content_list = [
        ScrapedContent(
            content_id="content1",
            source_id="unknown_source",
            title="Test Content",
            content="Test content",
            url="https://example.com",
            scraped_at=datetime.now().isoformat(),
        ),
    ]

    ingested_count = await orchestrator.ingest_content(content_list)

    assert ingested_count == 0


# ============================================================================
# Tests for run_ingestion_job
# ============================================================================


@pytest.mark.asyncio
async def test_run_ingestion_job_success(orchestrator, mock_scraper_service, mock_claude_service):
    """Test running ingestion job successfully"""
    job = await orchestrator.run_ingestion_job("oss_kbli")

    assert isinstance(job, IngestionJob)
    assert job.status == IngestionStatus.COMPLETED
    assert job.items_scraped > 0
    assert job.completed_at is not None
    assert job.job_id in orchestrator.jobs
    assert orchestrator.orchestrator_stats["successful_jobs"] == 1


@pytest.mark.asyncio
async def test_run_ingestion_job_failure(orchestrator, mock_scraper_service):
    """Test running ingestion job with failure"""

    # Make filter_content raise an exception to trigger failure
    async def failing_filter(*args):
        raise Exception("Filtering failed")

    orchestrator.filter_content = failing_filter

    job = await orchestrator.run_ingestion_job("oss_kbli")

    assert job.status == IngestionStatus.FAILED
    assert job.error is not None
    assert orchestrator.orchestrator_stats["failed_jobs"] == 1


@pytest.mark.asyncio
async def test_run_ingestion_job_unknown_source(orchestrator):
    """Test running ingestion job for unknown source"""
    with pytest.raises(ValueError, match="Unknown source"):
        await orchestrator.run_ingestion_job("unknown_source")


@pytest.mark.asyncio
async def test_run_ingestion_job_updates_stats(
    orchestrator, mock_scraper_service, mock_claude_service
):
    """Test that running job updates statistics"""
    initial_total = orchestrator.orchestrator_stats["total_jobs"]

    await orchestrator.run_ingestion_job("oss_kbli")

    assert orchestrator.orchestrator_stats["total_jobs"] == initial_total + 1
    assert orchestrator.orchestrator_stats["last_run"] is not None


# ============================================================================
# Tests for run_scheduled_ingestion
# ============================================================================


@pytest.mark.asyncio
async def test_run_scheduled_ingestion_with_due_sources(
    orchestrator, mock_scraper_service, mock_claude_service
):
    """Test running scheduled ingestion with due sources"""
    # Make a source due
    source = orchestrator.sources["oss_kbli"]
    source.last_scraped = None

    jobs = await orchestrator.run_scheduled_ingestion()

    assert len(jobs) > 0
    assert all(isinstance(job, IngestionJob) for job in jobs)


@pytest.mark.asyncio
async def test_run_scheduled_ingestion_no_due_sources(orchestrator):
    """Test running scheduled ingestion with no due sources"""
    # Set all sources as recently scraped
    for source in orchestrator.sources.values():
        source.last_scraped = datetime.now().isoformat()

    jobs = await orchestrator.run_scheduled_ingestion()

    assert len(jobs) == 0


# ============================================================================
# Tests for get_job_status
# ============================================================================


def test_get_job_status_exists(orchestrator):
    """Test getting job status for existing job"""
    job = IngestionJob(
        job_id="test_job",
        source_id="oss_kbli",
        status=IngestionStatus.COMPLETED,
        started_at=datetime.now().isoformat(),
    )
    orchestrator.jobs["test_job"] = job

    retrieved_job = orchestrator.get_job_status("test_job")

    assert retrieved_job is not None
    assert retrieved_job.job_id == "test_job"


def test_get_job_status_not_exists(orchestrator):
    """Test getting job status for non-existent job"""
    job = orchestrator.get_job_status("nonexistent")

    assert job is None


# ============================================================================
# Tests for get_orchestrator_stats
# ============================================================================


def test_get_orchestrator_stats(orchestrator):
    """Test getting orchestrator statistics"""
    stats = orchestrator.get_orchestrator_stats()

    assert "total_jobs" in stats
    assert "successful_jobs" in stats
    assert "failed_jobs" in stats
    assert "success_rate" in stats
    assert "sources_monitored" in stats
    assert "sources_enabled" in stats


def test_get_orchestrator_stats_success_rate(orchestrator):
    """Test that success rate is calculated correctly"""
    # Add some jobs
    orchestrator.orchestrator_stats["total_jobs"] = 10
    orchestrator.orchestrator_stats["successful_jobs"] = 8

    stats = orchestrator.get_orchestrator_stats()

    assert stats["success_rate"] == "80.0%"


# ============================================================================
# Tests for _generate_content_id
# ============================================================================


def test_generate_content_id(orchestrator):
    """Test generating content ID from hash"""
    content = "Test content"
    content_id = orchestrator._generate_content_id(content)

    assert isinstance(content_id, str)
    assert len(content_id) == 32  # MD5 hash length
    # Same content should generate same ID
    assert orchestrator._generate_content_id(content) == content_id
