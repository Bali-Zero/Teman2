"""
Unit tests for backend/app/routers/intel_scraper.py

Tests route handler functions and helpers directly (no TestClient) with mocked dependencies.
Covers:
- POST /api/intel/staging/register-notification -> register_notification
- POST /api/intel/scraper/submit               -> submit_from_scraper
- POST /api/intel/staging/publish/{type}/{id}   -> publish_staging_item
- convert_staging_to_enriched_article (helper)
- update_homepage_layout (helper)
- ingest_intel_to_qdrant (helper)
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helper: convert_staging_to_enriched_article
# ---------------------------------------------------------------------------


class TestConvertStagingToEnrichedArticle:
    def test_basic(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {
            "title": "New Visa Rule",
            "content": "## Summary\nNew rule.\n## Facts\nEffective Jan 2026.\n## Bali Zero Take\nImportant.\n## Next Steps\n- Step one",
            "category": "visa",
            "relevance_score": 80,
            "source_url": "https://example.com",
            "source_name": "Test Scraper",
        }
        result = convert_staging_to_enriched_article(data)

        assert result["title"] == "New Visa Rule"
        assert result["category"] == "visa"
        assert result["priority"] == "high"
        assert "tldr" in result
        assert "bali_zero_take" in result
        assert "next_steps" in result
        assert result["source"] == "Test Scraper"

    def test_low_relevance(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {
            "title": "Minor Update",
            "content": "Some minor content.",
            "category": "news",
            "relevance_score": 30,
        }
        result = convert_staging_to_enriched_article(data)
        assert result["priority"] == "low"
        assert result["tldr"]["risk_level"] == "Low"
        assert result["tldr"]["should_worry"] == "No"

    def test_medium_relevance(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {
            "title": "Medium Update",
            "content": "Some content here.",
            "category": "business",
            "relevance_score": 60,
        }
        result = convert_staging_to_enriched_article(data)
        assert result["priority"] == "medium"
        assert result["tldr"]["should_worry"] == "Depends"

    def test_no_sections(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {
            "title": "Plain Article",
            "content": "Just plain text without any markdown sections or structure.",
            "category": "news",
            "relevance_score": 50,
        }
        result = convert_staging_to_enriched_article(data)
        assert result["ai_summary"]
        assert result["facts"]

    def test_with_timeline_keywords(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {
            "title": "Timeline Article",
            "content": "## Summary\nNew timeline and date information.\n## Facts\nTimeline of events.",
            "category": "news",
            "relevance_score": 75,
        }
        result = convert_staging_to_enriched_article(data)
        assert "timeline" in result["suggested_components"]

    def test_with_comparison_keywords(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {
            "title": "Comparison Article",
            "content": "## Summary\nOld vs new regulations.\n## Facts\nComparison of approaches.",
            "category": "news",
            "relevance_score": 75,
        }
        result = convert_staging_to_enriched_article(data)
        assert "comparison-table" in result["suggested_components"]

    def test_with_expat_investor_steps(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {
            "title": "Steps Article",
            "content": (
                "## Summary\nSummary here.\n"
                "## Facts\nFacts here.\n"
                "## Bali Zero Take\nOur take.\n"
                "## Next Steps\n"
                "### For Expats\n"
                "- Check your visa status\n"
                "- Update documents\n"
                "### For Investors\n"
                "- Review investment plan\n"
                "- Consult advisor\n"
            ),
            "category": "visa",
            "relevance_score": 80,
        }
        result = convert_staging_to_enriched_article(data)
        assert len(result["next_steps"]["expat"]) >= 1
        assert len(result["next_steps"]["investor"]) >= 1

    def test_tags_generation(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {
            "title": "Important Regulation Update for Businesses",
            "content": "Content.",
            "category": "business",
            "relevance_score": 50,
        }
        result = convert_staging_to_enriched_article(data)
        assert "business" in result["ai_tags"]
        assert len(result["ai_tags"]) <= 5

    def test_defaults(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {}
        result = convert_staging_to_enriched_article(data)
        assert result["title"] == "Untitled"
        assert result["category"] == "news"
        assert result["source"] == "Bali Intel Scraper"

    def test_enriched_at_timestamp(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {"title": "T", "content": "C", "category": "news", "relevance_score": 50}
        result = convert_staging_to_enriched_article(data)
        assert "enriched_at" in result
        assert result["cover_image"] is None

    def test_bali_zero_take_subsections(self) -> None:
        from backend.app.routers.intel_scraper import convert_staging_to_enriched_article

        data = {
            "title": "Take Article",
            "content": (
                "## Summary\nSum.\n## Facts\nFacts.\n"
                "## Bali Zero Take\n"
                "### Hidden Insight\nHidden text here.\n"
                "### Our Analysis\nAnalysis text here.\n"
                "### Our Advice\nAdvice text here.\n"
                "## Next Steps\n- Step\n"
            ),
            "category": "news",
            "relevance_score": 75,
        }
        result = convert_staging_to_enriched_article(data)
        assert "Hidden text" in result["bali_zero_take"]["hidden_insight"]
        assert "Analysis text" in result["bali_zero_take"]["our_analysis"]
        assert "Advice text" in result["bali_zero_take"]["our_advice"]


# ---------------------------------------------------------------------------
# Helper: update_homepage_layout
# ---------------------------------------------------------------------------


class TestUpdateHomepageLayout:
    @pytest.mark.asyncio
    async def test_no_github_token(self) -> None:
        from backend.app.routers.intel_scraper import update_homepage_layout

        with patch.dict(os.environ, {}, clear=False):
            # Remove GITHUB_TOKEN if present
            env_copy = dict(os.environ)
            env_copy.pop("GITHUB_TOKEN", None)
            with patch.dict(os.environ, env_copy, clear=True):
                with pytest.raises(ValueError, match="GITHUB_TOKEN"):
                    await update_homepage_layout("slug", "hero_main")

    @pytest.mark.asyncio
    async def test_invalid_position(self) -> None:
        from backend.app.routers.intel_scraper import update_homepage_layout

        with patch.dict(os.environ, {"GITHUB_TOKEN": "test-token"}):
            with pytest.raises(ValueError, match="Invalid position"):
                await update_homepage_layout("slug", "invalid_position")


# ---------------------------------------------------------------------------
# Helper: ingest_intel_to_qdrant
# ---------------------------------------------------------------------------


class TestIngestIntelToQdrant:
    @pytest.mark.asyncio
    async def test_item_not_found(self) -> None:
        from backend.app.routers.intel_scraper import ingest_intel_to_qdrant

        with patch("backend.app.routers.intel_scraper.staging_service") as mock_svc:
            mock_svc.load_staging_item.return_value = None
            result = await ingest_intel_to_qdrant("item-1", "news")
        assert result is False

    @pytest.mark.asyncio
    async def test_no_collection(self) -> None:
        from backend.app.routers.intel_scraper import ingest_intel_to_qdrant

        with (
            patch("backend.app.routers.intel_scraper.staging_service") as mock_svc,
            patch("backend.app.routers.intel_scraper.INTEL_COLLECTIONS", {}),
        ):
            mock_svc.load_staging_item.return_value = {"title": "T", "content": "C"}
            result = await ingest_intel_to_qdrant("item-1", "unknown_type")
        assert result is False

    @pytest.mark.asyncio
    async def test_success(self) -> None:
        from backend.app.routers.intel_scraper import ingest_intel_to_qdrant

        mock_embedder = MagicMock()
        mock_embedder.generate_single_embedding = AsyncMock(return_value=[0.1] * 1536)

        mock_qdrant = MagicMock()
        mock_qdrant.upsert_documents = AsyncMock(return_value=None)

        with (
            patch("backend.app.routers.intel_scraper.staging_service") as mock_svc,
            patch("backend.app.routers.intel_scraper.INTEL_COLLECTIONS", {"news": "intel_news"}),
            patch("backend.app.routers.intel_scraper.get_embedder", return_value=mock_embedder),
            patch("backend.app.routers.intel_scraper.QdrantClient", return_value=mock_qdrant),
        ):
            mock_svc.load_staging_item.return_value = {
                "title": "Test Article",
                "content": "Some content",
                "source_url": "https://example.com",
                "category": "news",
                "source_name": "scraper",
                "relevance_score": 80,
            }
            result = await ingest_intel_to_qdrant("item-1", "news")
        assert result is True

    @pytest.mark.asyncio
    async def test_qdrant_exception(self) -> None:
        from backend.app.routers.intel_scraper import ingest_intel_to_qdrant

        mock_embedder = MagicMock()
        mock_embedder.generate_single_embedding = AsyncMock(return_value=[0.1] * 1536)

        with (
            patch("backend.app.routers.intel_scraper.staging_service") as mock_svc,
            patch("backend.app.routers.intel_scraper.INTEL_COLLECTIONS", {"news": "intel_news"}),
            patch("backend.app.routers.intel_scraper.get_embedder", return_value=mock_embedder),
            patch(
                "backend.app.routers.intel_scraper.QdrantClient",
                side_effect=Exception("Qdrant down"),
            ),
        ):
            mock_svc.load_staging_item.return_value = {"title": "T", "content": "C"}
            result = await ingest_intel_to_qdrant("item-1", "news")
        assert result is False


# ---------------------------------------------------------------------------
# Endpoint: register_notification
# ---------------------------------------------------------------------------


class TestRegisterNotification:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        from backend.app.routers.intel import RegisterNotificationRequest
        from backend.app.routers.intel_scraper import register_notification

        mock_handler = MagicMock()
        mock_handler.register_notification = MagicMock()

        with patch("backend.services.intel.intel_cover_handler.intel_cover_handler", mock_handler):
            req = RegisterNotificationRequest(
                telegram_message_id=123,
                chat_id=456,
                intel_type="news",
                item_id="news-2026-01",
                title="Test",
            )
            result = await register_notification(request=req, _api_key_verified=None)

        assert result["success"] is True
        assert result["message_id"] == 123
        mock_handler.register_notification.assert_called_once()


# ---------------------------------------------------------------------------
# Endpoint: submit_from_scraper
# ---------------------------------------------------------------------------


class TestSubmitFromScraper:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        from backend.app.routers.intel import ScraperSubmission
        from backend.app.routers.intel_scraper import submit_from_scraper

        with (
            patch("backend.app.routers.intel_scraper.classification_service") as mock_cls,
            patch("backend.app.routers.intel_scraper.staging_service") as mock_stg,
            patch("backend.app.routers.intel_scraper.intel_articles_submitted") as mock_metric,
            patch("backend.app.routers.intel_scraper.intel_scraper_latency") as mock_latency,
        ):
            mock_cls.classify_intel_type.return_value = "visa"
            mock_stg.generate_item_id.return_value = "visa-2026-test"
            mock_stg.check_duplicate.return_value = None
            mock_stg.save_staging_item.return_value = "/tmp/staging/visa/visa-2026-test.json"
            mock_stg.update_staging_queue_metrics = MagicMock()
            mock_metric.labels.return_value.inc = MagicMock()
            mock_latency.labels.return_value.observe = MagicMock()

            submission = ScraperSubmission(
                title="New visa rule",
                content="## Summary\nNew rule.\n## Facts\nEffective.",
                source_url="https://example.com",
                source_name="test-scraper",
                category="visa",
                relevance_score=80,
                extraction_method="auto",
                tier="tier1",
            )
            result = await submit_from_scraper(submission=submission, _api_key_verified=None)

        assert result["success"] is True
        assert result["intel_type"] == "visa"
        assert result["duplicate"] is False

    @pytest.mark.asyncio
    async def test_duplicate(self) -> None:
        from backend.app.routers.intel import ScraperSubmission
        from backend.app.routers.intel_scraper import submit_from_scraper

        with (
            patch("backend.app.routers.intel_scraper.classification_service") as mock_cls,
            patch("backend.app.routers.intel_scraper.staging_service") as mock_stg,
            patch("backend.app.routers.intel_scraper.intel_articles_duplicates") as mock_dup,
            patch("backend.app.routers.intel_scraper.intel_scraper_latency") as mock_latency,
        ):
            mock_cls.classify_intel_type.return_value = "news"
            mock_stg.generate_item_id.return_value = "news-2026-dup"
            mock_stg.check_duplicate.return_value = {"item_id": "news-2026-existing"}
            mock_dup.labels.return_value.inc = MagicMock()
            mock_latency.labels.return_value.observe = MagicMock()

            submission = ScraperSubmission(
                title="Duplicate",
                content="Content",
                source_url="https://example.com/dup",
                source_name="scraper",
                category="news",
                relevance_score=50,
                extraction_method="auto",
                tier="tier1",
            )
            result = await submit_from_scraper(submission=submission, _api_key_verified=None)

        assert result["duplicate"] is True
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_duplicate_backfills_enrichment_when_existing_item_lacks_it(self) -> None:
        """GUILT (round-2 red-team MUST-FIX #3, scar family #9): a
        duplicate hit against an existing staging item with no usable
        enrichment must be healed in place when the new submission carries
        one — the early-return dedup response happens BEFORE staging_data
        is built, so without this fix the existing item's future draft
        would stay stuck at {} forever (7-day dedup window)."""
        from backend.app.routers.intel import ScraperSubmission
        from backend.app.routers.intel_scraper import submit_from_scraper

        with (
            patch("backend.app.routers.intel_scraper.classification_service") as mock_cls,
            patch("backend.app.routers.intel_scraper.staging_service") as mock_stg,
            patch("backend.app.routers.intel_scraper.intel_articles_duplicates") as mock_dup,
            patch("backend.app.routers.intel_scraper.intel_scraper_latency") as mock_latency,
        ):
            mock_cls.classify_intel_type.return_value = "news"
            mock_stg.generate_item_id.return_value = "news-2026-dup"
            existing_item = {
                "item_id": "news-2026-existing",
                "title": "Existing",
                "source_url": "https://example.com/dup",
                "enrichment": {},
            }
            mock_stg.check_duplicate.return_value = existing_item
            mock_stg.load_staging_item.return_value = dict(existing_item)
            mock_dup.labels.return_value.inc = MagicMock()
            mock_latency.labels.return_value.observe = MagicMock()

            enrichment_obj = {
                "the_facts": "Fresh facts.",
                "bali_zero_take": "Fresh take.",
            }
            submission = ScraperSubmission(
                title="Duplicate with enrichment",
                content="Content",
                source_url="https://example.com/dup",
                source_name="scraper",
                category="news",
                relevance_score=50,
                extraction_method="auto",
                tier="tier1",
                enrichment=enrichment_obj,
            )
            result = await submit_from_scraper(submission=submission, _api_key_verified=None)

        assert result["duplicate"] is True
        assert result["success"] is True
        assert result["enrichment_backfilled"] is True
        mock_stg.load_staging_item.assert_called_once_with("news", "news-2026-existing")
        mock_stg.save_staging_item.assert_called_once()
        saved_type, saved_id, saved_data = mock_stg.save_staging_item.call_args[0]
        assert saved_type == "news"
        assert saved_id == "news-2026-existing"
        assert saved_data["enrichment"] == enrichment_obj

    @pytest.mark.asyncio
    async def test_duplicate_skips_backfill_when_existing_already_has_enrichment(
        self,
    ) -> None:
        """INNOCENCE: an existing duplicate that ALREADY carries a
        non-empty enrichment dict must not be touched — no load/save call,
        no `enrichment_backfilled` key in the response."""
        from backend.app.routers.intel import ScraperSubmission
        from backend.app.routers.intel_scraper import submit_from_scraper

        with (
            patch("backend.app.routers.intel_scraper.classification_service") as mock_cls,
            patch("backend.app.routers.intel_scraper.staging_service") as mock_stg,
            patch("backend.app.routers.intel_scraper.intel_articles_duplicates") as mock_dup,
            patch("backend.app.routers.intel_scraper.intel_scraper_latency") as mock_latency,
        ):
            mock_cls.classify_intel_type.return_value = "news"
            mock_stg.generate_item_id.return_value = "news-2026-dup2"
            mock_stg.check_duplicate.return_value = {
                "item_id": "news-2026-existing2",
                "enrichment": {"the_facts": "Already there."},
            }
            mock_dup.labels.return_value.inc = MagicMock()
            mock_latency.labels.return_value.observe = MagicMock()

            submission = ScraperSubmission(
                title="Duplicate again",
                content="Content",
                source_url="https://example.com/dup2",
                source_name="scraper",
                category="news",
                relevance_score=50,
                extraction_method="auto",
                tier="tier1",
                enrichment={"the_facts": "New but should not overwrite."},
            )
            result = await submit_from_scraper(submission=submission, _api_key_verified=None)

        assert result["duplicate"] is True
        assert "enrichment_backfilled" not in result
        mock_stg.load_staging_item.assert_not_called()
        mock_stg.save_staging_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_duplicate_skips_backfill_when_existing_is_published(self) -> None:
        """INNOCENCE (round-3 NICE fix, scar family #9): a duplicate hit
        against an existing staging item that is already `status: published`
        must NOT be healed even when it lacks enrichment and the new
        submission carries one. Published items still live in the staging
        root (the Telegram-quorum publish path never archives them), so an
        unconditional heal would write to a closed/live record. No
        downstream reader depends on this today (topic-selector filters
        status=="pending"), but the write itself must not happen."""
        from backend.app.routers.intel import ScraperSubmission
        from backend.app.routers.intel_scraper import submit_from_scraper

        with (
            patch("backend.app.routers.intel_scraper.classification_service") as mock_cls,
            patch("backend.app.routers.intel_scraper.staging_service") as mock_stg,
            patch("backend.app.routers.intel_scraper.intel_articles_duplicates") as mock_dup,
            patch("backend.app.routers.intel_scraper.intel_scraper_latency") as mock_latency,
        ):
            mock_cls.classify_intel_type.return_value = "news"
            mock_stg.generate_item_id.return_value = "news-2026-dup4"
            mock_stg.check_duplicate.return_value = {
                "item_id": "news-2026-existing4",
                "enrichment": {},
                "status": "published",
            }
            mock_dup.labels.return_value.inc = MagicMock()
            mock_latency.labels.return_value.observe = MagicMock()

            submission = ScraperSubmission(
                title="Duplicate against published item",
                content="Content",
                source_url="https://example.com/dup4",
                source_name="scraper",
                category="news",
                relevance_score=50,
                extraction_method="auto",
                tier="tier1",
                enrichment={"the_facts": "New but must not land on a published item."},
            )
            result = await submit_from_scraper(submission=submission, _api_key_verified=None)

        assert result["duplicate"] is True
        assert "enrichment_backfilled" not in result
        mock_stg.load_staging_item.assert_not_called()
        mock_stg.save_staging_item.assert_not_called()

    @pytest.mark.asyncio
    async def test_duplicate_backfill_failure_does_not_break_dedup_response(self) -> None:
        """Heal-attempt failures must never turn a successful dedup into a
        500 — log and fall through to the unchanged response shape."""
        from backend.app.routers.intel import ScraperSubmission
        from backend.app.routers.intel_scraper import submit_from_scraper

        with (
            patch("backend.app.routers.intel_scraper.classification_service") as mock_cls,
            patch("backend.app.routers.intel_scraper.staging_service") as mock_stg,
            patch("backend.app.routers.intel_scraper.intel_articles_duplicates") as mock_dup,
            patch("backend.app.routers.intel_scraper.intel_scraper_latency") as mock_latency,
        ):
            mock_cls.classify_intel_type.return_value = "news"
            mock_stg.generate_item_id.return_value = "news-2026-dup3"
            mock_stg.check_duplicate.return_value = {
                "item_id": "news-2026-existing3",
                "enrichment": {},
            }
            mock_stg.load_staging_item.side_effect = OSError("disk error")
            mock_dup.labels.return_value.inc = MagicMock()
            mock_latency.labels.return_value.observe = MagicMock()

            submission = ScraperSubmission(
                title="Duplicate heal failure",
                content="Content",
                source_url="https://example.com/dup3",
                source_name="scraper",
                category="news",
                relevance_score=50,
                extraction_method="auto",
                tier="tier1",
                enrichment={"the_facts": "New."},
            )
            result = await submit_from_scraper(submission=submission, _api_key_verified=None)

        assert result["success"] is True
        assert result["duplicate"] is True
        assert "enrichment_backfilled" not in result

    @pytest.mark.asyncio
    async def test_service_error(self) -> None:
        from fastapi import HTTPException

        from backend.app.routers.intel import ScraperSubmission
        from backend.app.routers.intel_scraper import submit_from_scraper

        with patch("backend.app.routers.intel_scraper.classification_service") as mock_cls:
            mock_cls.classify_intel_type.side_effect = Exception("Classification error")

            submission = ScraperSubmission(
                title="Err",
                content="Content",
                source_url="https://example.com/err",
                source_name="scraper",
                category="news",
                relevance_score=50,
                extraction_method="auto",
                tier="tier1",
            )
            with pytest.raises(HTTPException) as exc_info:
                await submit_from_scraper(submission=submission, _api_key_verified=None)
            assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_enrichment_persisted(self) -> None:
        """GUILT (WR2 enrichment passthrough, scar family #9): a
        ScraperSubmission carrying a full structured `enrichment` object
        must round-trip it verbatim into staging_data."""
        from backend.app.routers.intel import ScraperSubmission
        from backend.app.routers.intel_scraper import submit_from_scraper

        with (
            patch("backend.app.routers.intel_scraper.classification_service") as mock_cls,
            patch("backend.app.routers.intel_scraper.staging_service") as mock_stg,
            patch("backend.app.routers.intel_scraper.intel_articles_submitted") as mock_metric,
            patch("backend.app.routers.intel_scraper.intel_scraper_latency") as mock_latency,
        ):
            mock_cls.classify_intel_type.return_value = "news"
            mock_stg.generate_item_id.return_value = "news-2026-enriched"
            mock_stg.check_duplicate.return_value = None
            mock_stg.save_staging_item.return_value = "/tmp/staging/news/news-2026-enriched.json"
            mock_stg.update_staging_queue_metrics = MagicMock()
            mock_metric.labels.return_value.inc = MagicMock()
            mock_latency.labels.return_value.observe = MagicMock()

            enrichment_obj = {
                "the_facts": "Facts here.",
                "bali_zero_take": "Our take.",
                "thirty_second_brief": "Brief.",
                "faq": [{"q": "Q1", "a": "A1"}],
            }
            submission = ScraperSubmission(
                title="Enriched article",
                content="Content",
                source_url="https://example.com/enriched",
                source_name="test-scraper",
                category="news",
                relevance_score=70,
                extraction_method="auto",
                tier="tier1",
                enrichment=enrichment_obj,
            )
            result = await submit_from_scraper(submission=submission, _api_key_verified=None)

        assert result["success"] is True
        mock_stg.save_staging_item.assert_called_once()
        staging_data = mock_stg.save_staging_item.call_args[0][2]
        assert staging_data["enrichment"] == enrichment_obj

    @pytest.mark.asyncio
    async def test_enrichment_defaults_to_empty_dict_when_absent(self) -> None:
        """INNOCENCE: a legacy submission WITHOUT `enrichment` must still
        validate (backward-compat) and default to {} in staging_data — not
        crash, not omit the key entirely."""
        from backend.app.routers.intel import ScraperSubmission
        from backend.app.routers.intel_scraper import submit_from_scraper

        with (
            patch("backend.app.routers.intel_scraper.classification_service") as mock_cls,
            patch("backend.app.routers.intel_scraper.staging_service") as mock_stg,
            patch("backend.app.routers.intel_scraper.intel_articles_submitted") as mock_metric,
            patch("backend.app.routers.intel_scraper.intel_scraper_latency") as mock_latency,
        ):
            mock_cls.classify_intel_type.return_value = "news"
            mock_stg.generate_item_id.return_value = "news-2026-legacy"
            mock_stg.check_duplicate.return_value = None
            mock_stg.save_staging_item.return_value = "/tmp/staging/news/news-2026-legacy.json"
            mock_stg.update_staging_queue_metrics = MagicMock()
            mock_metric.labels.return_value.inc = MagicMock()
            mock_latency.labels.return_value.observe = MagicMock()

            submission = ScraperSubmission(
                title="Legacy article",
                content="Content",
                source_url="https://example.com/legacy",
                source_name="test-scraper",
                category="news",
                relevance_score=50,
                extraction_method="auto",
                tier="tier1",
            )
            result = await submit_from_scraper(submission=submission, _api_key_verified=None)

        assert result["success"] is True
        staging_data = mock_stg.save_staging_item.call_args[0][2]
        assert staging_data["enrichment"] == {}

    @pytest.mark.asyncio
    async def test_with_cover_image(self) -> None:
        from backend.app.routers.intel import ScraperSubmission
        from backend.app.routers.intel_scraper import submit_from_scraper

        with (
            patch("backend.app.routers.intel_scraper.classification_service") as mock_cls,
            patch("backend.app.routers.intel_scraper.staging_service") as mock_stg,
            patch("backend.app.routers.intel_scraper.intel_articles_submitted") as mock_metric,
            patch("backend.app.routers.intel_scraper.intel_scraper_latency") as mock_latency,
        ):
            mock_cls.classify_intel_type.return_value = "news"
            mock_stg.generate_item_id.return_value = "news-2026-img"
            mock_stg.check_duplicate.return_value = None
            mock_stg.save_staging_item.return_value = "/tmp/staging/news/news-2026-img.json"
            mock_stg.update_staging_queue_metrics = MagicMock()
            mock_metric.labels.return_value.inc = MagicMock()
            mock_latency.labels.return_value.observe = MagicMock()

            submission = ScraperSubmission(
                title="Image article",
                content="Content with image.",
                source_url="https://example.com/img",
                source_name="scraper",
                category="news",
                relevance_score=60,
                extraction_method="auto",
                tier="tier1",
                cover_image="https://example.com/cover.jpg",
            )
            result = await submit_from_scraper(submission=submission, _api_key_verified=None)

        assert result["success"] is True


# ---------------------------------------------------------------------------
# Endpoint: publish_staging_item
# ---------------------------------------------------------------------------


class TestPublishStagingItem:
    @pytest.mark.asyncio
    async def test_not_found(self) -> None:
        from fastapi import HTTPException

        from backend.app.routers.intel_scraper import publish_staging_item_internal

        with (
            patch("backend.app.routers.intel_scraper.staging_service") as mock_stg,
            patch("backend.app.routers.intel_scraper.intel_user_actions_total") as mock_metric,
        ):
            mock_stg.load_staging_item.return_value = None
            mock_metric.labels.return_value.inc = MagicMock()

            with pytest.raises(HTTPException) as exc_info:
                await publish_staging_item_internal("news", "nonexistent", actor="test")
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_qdrant_failure(self) -> None:
        from fastapi import HTTPException

        from backend.app.routers.intel_scraper import publish_staging_item_internal

        with (
            patch("backend.app.routers.intel_scraper.staging_service") as mock_stg,
            patch("backend.app.routers.intel_scraper.intel_user_actions_total") as mock_metric,
            patch(
                "backend.app.routers.intel_scraper.ingest_intel_to_qdrant",
                new=AsyncMock(return_value=False),
            ),
        ):
            mock_stg.load_staging_item.return_value = {
                "title": "T",
                "content": "C",
                "category": "news",
            }
            mock_metric.labels.return_value.inc = MagicMock()

            with pytest.raises(HTTPException) as exc_info:
                await publish_staging_item_internal("news", "item-1", actor="test")
            assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------


class TestModuleConstants:
    def test_router_exists(self) -> None:
        from backend.app.routers.intel_scraper import router

        assert router is not None
        assert router.tags == ["intel-scraper"]
