from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.services.ingestion.auto_ingestion_orchestrator import (
    AutoIngestionOrchestrator,
    IngestionStatus,
    MonitoredSource,
    ScrapedContent,
    SourceType,
    UpdateType,
)


def build_source(
    source_id: str = "src",
    *,
    last_scraped: str | None = None,
    enabled: bool = True,
) -> MonitoredSource:
    return MonitoredSource(
        source_id=source_id,
        source_type=SourceType.WEB_SCRAPER,
        name="Source",
        url="https://example.test",
        target_collection="legal_updates",
        scrape_frequency_hours=24,
        last_scraped=last_scraped,
        enabled=enabled,
    )


def build_content(content_id: str = "c1", source_id: str = "src") -> ScrapedContent:
    return ScrapedContent(
        content_id=content_id,
        source_id=source_id,
        title="New regulation",
        content="A regulation update was published",
        url="https://example.test/item",
        scraped_at="2026-01-01T00:00:00+00:00",
    )


def test_add_source_and_due_sources_respect_disabled_and_recent_sources() -> None:
    now = datetime.now(tz=timezone.utc)
    due = build_source("due", last_scraped=(now - timedelta(hours=25)).isoformat())
    recent = build_source("recent", last_scraped=(now - timedelta(hours=1)).isoformat())
    disabled = build_source("disabled", enabled=False)
    orchestrator = AutoIngestionOrchestrator()
    orchestrator.sources = {"recent": recent, "disabled": disabled}

    orchestrator.add_source(due)

    assert orchestrator.sources["due"] is due
    assert orchestrator.get_due_sources() == [due]


async def test_scrape_source_requires_scraper_service() -> None:
    orchestrator = AutoIngestionOrchestrator(scraper_service=None)

    with pytest.raises(ValueError, match="Scraper service not configured"):
        await orchestrator.scrape_source(build_source())


async def test_scrape_source_maps_items_and_updates_last_scraped() -> None:
    class FakeScraper:
        async def scrape(self, url: str) -> list[dict[str, object]]:
            assert url == "https://example.test"
            return [
                {
                    "title": "Policy",
                    "content": "Regulation text",
                    "url": "https://example.test/policy",
                    "metadata": {"kind": "policy"},
                }
            ]

    source = build_source()
    orchestrator = AutoIngestionOrchestrator(scraper_service=FakeScraper())

    scraped = await orchestrator.scrape_source(source)

    assert len(scraped) == 1
    assert scraped[0].title == "Policy"
    assert scraped[0].content_id == orchestrator._generate_content_id("Regulation text")
    assert scraped[0].metadata == {"kind": "policy"}
    assert source.last_scraped is not None


async def test_filter_content_applies_keyword_and_ai_classification() -> None:
    class FakeAI:
        async def conversational(self, **kwargs) -> dict[str, str]:
            assert kwargs["user_id"] == "auto_ingestion"
            return {"text": "YES, new regulation"}

    relevant = build_content()
    irrelevant = build_content("c2")
    irrelevant.title = "Travel story"
    irrelevant.content = "A lifestyle article about travel"
    orchestrator = AutoIngestionOrchestrator(claude_service=FakeAI())

    filtered = await orchestrator.filter_content([relevant, irrelevant])

    assert filtered == [relevant]
    assert relevant.relevance_score == 0.8
    assert relevant.update_type is UpdateType.NEW_REGULATION


async def test_ingest_content_deduplicates_and_updates_collection_stats() -> None:
    source = build_source()
    orchestrator = AutoIngestionOrchestrator(search_service=object())
    orchestrator.sources = {source.source_id: source}
    content = build_content()

    assert await orchestrator.ingest_content([content, content]) == 1
    assert orchestrator.content_hashes == {"c1"}
    assert orchestrator.orchestrator_stats["items_by_collection"] == {"legal_updates": 1}


async def test_run_ingestion_job_records_successful_job() -> None:
    class FakeScraper:
        async def scrape(self, _url: str) -> list[dict[str, object]]:
            return [{"title": "Policy", "content": "regulation update"}]

    source = build_source()
    orchestrator = AutoIngestionOrchestrator(
        search_service=object(),
        scraper_service=FakeScraper(),
    )
    orchestrator.sources = {source.source_id: source}

    job = await orchestrator.run_ingestion_job(source.source_id)

    assert job.status is IngestionStatus.COMPLETED
    assert job.items_scraped == 1
    assert job.items_filtered == 1
    assert job.items_ingested == 1
    assert orchestrator.get_job_status(job.job_id) is job
    assert orchestrator.get_orchestrator_stats()["success_rate"] == "100.0%"


async def test_run_scheduled_ingestion_runs_only_due_sources(monkeypatch) -> None:
    now = datetime.now(tz=timezone.utc)
    due = build_source("due", last_scraped=(now - timedelta(hours=25)).isoformat())
    recent = build_source("recent", last_scraped=(now - timedelta(hours=1)).isoformat())
    orchestrator = AutoIngestionOrchestrator()
    orchestrator.sources = {"due": due, "recent": recent}

    async def fake_run(source_id: str):
        return {"source_id": source_id}

    monkeypatch.setattr(orchestrator, "run_ingestion_job", fake_run)

    assert await orchestrator.run_scheduled_ingestion() == [{"source_id": "due"}]
