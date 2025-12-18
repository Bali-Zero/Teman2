"""
ZANTARA MEDIA - Content Orchestrator Tests
Tests for automated content generation pipeline
"""

import pytest
from unittest.mock import patch
from datetime import datetime

from app.services.content_orchestrator import ContentOrchestrator


@pytest.mark.asyncio
class TestContentOrchestrator:
    """Test content orchestration pipeline."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance."""
        return ContentOrchestrator()

    @pytest.fixture
    def mock_dependencies(
        self, mock_content_repository, mock_ai_engine, mock_image_service
    ):
        """Mock all dependencies."""
        with patch(
            "app.services.content_orchestrator.content_repository",
            mock_content_repository,
        ), patch("app.services.content_orchestrator.ai_engine", mock_ai_engine), patch(
            "app.services.content_orchestrator.google_ai_service", mock_image_service
        ):
            yield {
                "repository": mock_content_repository,
                "ai_engine": mock_ai_engine,
                "image_service": mock_image_service,
            }

    async def test_fetch_intel_signals_from_db(self, orchestrator, mock_dependencies):
        """Test fetching intel signals from database."""
        mock_signals = [
            {
                "id": "signal-1",
                "title": "New Visa Program",
                "summary": "Indonesia launches new visa",
                "category": "IMMIGRATION",
                "priority": 9,
            }
        ]

        mock_dependencies[
            "repository"
        ].get_pending_intel_signals.return_value = mock_signals

        signals = await orchestrator._fetch_intel_signals()

        assert len(signals) == 1
        assert signals[0]["title"] == "New Visa Program"
        mock_dependencies["repository"].get_pending_intel_signals.assert_called_once()

    async def test_generate_article_from_signal(
        self, orchestrator, mock_dependencies, mock_intel_signal
    ):
        """Test generating article from intel signal."""
        mock_dependencies["repository"].create_content.return_value = {
            "id": "article-123",
            "title": "Generated Article",
            "body": "Article content...",
            "status": "DRAFT",
        }

        article = await orchestrator._generate_article_from_signal(mock_intel_signal)

        assert article["id"] == "article-123"
        assert article["title"] == "Generated Article"
        mock_dependencies["ai_engine"].generate_with_fallback.assert_called_once()
        mock_dependencies["repository"].create_content.assert_called_once()

    async def test_generate_cover_image_success(self, orchestrator, mock_dependencies):
        """Test successful cover image generation."""
        article = {
            "id": "article-123",
            "title": "Test Article",
            "category": "IMMIGRATION",
        }

        image_url = await orchestrator._generate_cover_image(article)

        assert image_url is not None
        assert "https://" in image_url or "data:" in image_url
        mock_dependencies["image_service"].generate_image.assert_called_once()

    async def test_generate_cover_image_fallback(self, orchestrator, mock_dependencies):
        """Test cover image generation with fallback."""
        article = {
            "id": "article-123",
            "title": "Test Article",
            "category": "IMMIGRATION",
        }

        # Make primary service fail
        mock_dependencies["image_service"].generate_image.side_effect = Exception(
            "API Error"
        )

        image_url = await orchestrator._generate_cover_image(article)

        # Should return placeholder
        assert "placehold.co" in image_url

    async def test_build_article_prompt(self, orchestrator, mock_intel_signal):
        """Test article prompt generation."""
        prompt = orchestrator._build_article_prompt(mock_intel_signal)

        assert "New Digital Nomad Visa Announced" in prompt
        assert "IMMIGRATION" in prompt
        assert "600-800 words" in prompt
        assert "professional" in prompt.lower()

    async def test_parse_article_response(self, orchestrator):
        """Test parsing AI-generated article."""
        ai_response = """TITLE: New Visa Program for Digital Nomads

SUMMARY: Indonesia launches comprehensive visa program for remote workers.

BODY:
Indonesia has officially launched a new visa program designed specifically for digital nomads and remote workers.

## Key Features
- Extended stay duration
- Simplified application process
- Tax benefits

## Eligibility
Applicants must demonstrate stable remote income and health insurance coverage.
"""

        parsed = orchestrator._parse_article_response(ai_response)

        assert parsed["title"] == "New Visa Program for Digital Nomads"
        assert "Indonesia launches" in parsed["summary"]
        assert "digital nomads" in parsed["body"]

    async def test_generate_slug(self, orchestrator):
        """Test slug generation."""
        title = "New Visa Program for Digital Nomads in Bali!"
        slug = orchestrator._generate_slug(title)

        assert "new-visa-program" in slug
        assert "digital-nomads" in slug
        assert "!" not in slug
        assert len(slug) <= 100

    @patch("app.services.content_orchestrator.datetime")
    async def test_run_daily_pipeline_success(
        self, mock_datetime, orchestrator, mock_dependencies, mock_intel_signal
    ):
        """Test successful daily pipeline execution."""
        from uuid import uuid4

        # Mock datetime
        mock_datetime.utcnow.return_value = datetime(2025, 1, 10, 6, 0, 0)

        # Create proper UUIDs for signals
        signals = []
        for i in range(5):
            signal = {
                **mock_intel_signal,
                "id": str(uuid4()),  # Valid UUID string
                "title": f"Signal {i+1}",
            }
            signals.append(signal)

        # Mock signals
        mock_dependencies["repository"].get_pending_intel_signals.return_value = signals

        # Mock article creation - include 'category' which is used by the orchestrator
        article_id = str(uuid4())
        mock_dependencies["repository"].create_content.return_value = {
            "id": article_id,
            "title": "Generated Article",
            "body": "Content...",
            "category": "IMMIGRATION",  # Required by orchestrator
        }

        # Mock status updates
        mock_dependencies["repository"].update_content_status.return_value = {
            "id": article_id,
            "status": "PUBLISHED",
        }

        # Mock marking signal as processed
        mock_dependencies["repository"].mark_intel_signal_processed.return_value = {
            "id": signals[0]["id"],
            "processed": True,
        }

        # Run pipeline
        stats = await orchestrator.run_daily_pipeline()

        # Assertions
        assert stats["articles_generated"] == 5
        assert stats["images_generated"] == 5
        assert stats["articles_published"] == 5
        assert len(stats["articles_created"]) == 5
        assert "duration_seconds" in stats
        assert len(stats["errors"]) == 0

    async def test_run_daily_pipeline_no_signals(self, orchestrator, mock_dependencies):
        """Test pipeline with no intel signals."""
        mock_dependencies["repository"].get_pending_intel_signals.return_value = []

        stats = await orchestrator.run_daily_pipeline()

        assert stats["intel_signals_fetched"] == 0
        assert stats["articles_generated"] == 0
        # Pipeline completes with 0 signals

    async def test_run_daily_pipeline_partial_failure(
        self, orchestrator, mock_dependencies, mock_intel_signal
    ):
        """Test pipeline with some failures."""
        mock_dependencies["repository"].get_pending_intel_signals.return_value = [
            mock_intel_signal,
            {**mock_intel_signal, "id": "signal-2"},
        ]

        # Make second article fail
        call_count = 0

        async def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("Database error")
            return {"id": f"article-{call_count}", "title": "Article"}

        mock_dependencies["repository"].create_content.side_effect = mock_create

        stats = await orchestrator.run_daily_pipeline()

        assert stats["articles_generated"] == 1  # Only first succeeded
        assert len(stats["errors"]) > 0
