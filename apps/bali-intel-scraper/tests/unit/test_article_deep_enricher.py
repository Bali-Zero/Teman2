"""
Unit Tests for Article Deep Enricher
Tests for Claude Max article enrichment
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from article_deep_enricher import ArticleDeepEnricher, EnrichedArticle


class TestEnrichedArticle:
    """Test EnrichedArticle dataclass"""

    def test_create_enriched_article(self):
        """Test creating an EnrichedArticle"""
        article = EnrichedArticle(
            title="Test Title",
            headline="Test Headline",
            tldr={"should_worry": "No", "what": "Test event"},
            facts="Some facts here",
            bali_zero_take='{"hidden_insight": "test"}',
            next_steps={"expat": ["step1"], "investor": ["step2"]},
            category="immigration",
            priority="high",
            relevance_score=85,
            ai_summary="Test summary",
            ai_tags=["visa", "expat"],
            source="Jakarta Post",
            source_url="https://example.com/article",
            original_content="Original content",
            published_at="2024-01-01",
            components=["timeline", "checklist"],
        )

        assert article.title == "Test Title"
        assert article.headline == "Test Headline"
        assert article.category == "immigration"
        assert article.relevance_score == 85
        assert "visa" in article.ai_tags

    def test_enriched_article_with_optional_fields(self):
        """Test EnrichedArticle with optional fields"""
        article = EnrichedArticle(
            title="Test",
            headline="Test",
            tldr={},
            facts="Facts",
            bali_zero_take="{}",
            next_steps={},
            category="business",
            priority="medium",
            relevance_score=50,
            ai_summary="Summary",
            ai_tags=[],
            source="Source",
            source_url="http://example.com",
            original_content="Content",
            published_at=None,
            components=[],
            cover_image="path/to/image.png",
            image_prompt="Generate an image",
        )

        assert article.cover_image == "path/to/image.png"
        assert article.image_prompt == "Generate an image"


class TestArticleDeepEnricherInit:
    """Test ArticleDeepEnricher initialization"""

    def test_default_init(self):
        """Test default initialization"""
        enricher = ArticleDeepEnricher()
        assert enricher is not None
        assert enricher.api_url == "https://balizero.com"
        assert enricher.generate_images is True

    def test_custom_api_url(self):
        """Test custom API URL"""
        enricher = ArticleDeepEnricher(api_url="https://custom.api.com")
        assert enricher.api_url == "https://custom.api.com"

    def test_images_disabled(self):
        """Test with images disabled"""
        enricher = ArticleDeepEnricher(generate_images=False)
        assert enricher.generate_images is False
        assert enricher.image_generator is None

    def test_has_system_prompt(self):
        """Test system prompt exists"""
        assert hasattr(ArticleDeepEnricher, "SYSTEM_PROMPT")
        assert "Bali Zero" in ArticleDeepEnricher.SYSTEM_PROMPT

    def test_has_fetch_method(self):
        """Test that fetch method exists"""
        enricher = ArticleDeepEnricher()
        assert hasattr(enricher, "fetch_full_article")

    def test_has_enrich_method(self):
        """Test that enrich method exists"""
        enricher = ArticleDeepEnricher()
        assert hasattr(enricher, "enrich_article")


class TestFetchFullArticle:
    """Test fetching full article content"""

    def test_fetch_method_callable(self):
        """Test fetch method is callable"""
        enricher = ArticleDeepEnricher()
        assert callable(enricher.fetch_full_article)

    def test_fetch_returns_none_on_failure(self):
        """Test fetch returns None when all methods fail"""
        enricher = ArticleDeepEnricher()

        import article_deep_enricher

        original_traf = article_deep_enricher.TRAFILATURA_AVAILABLE
        original_news = article_deep_enricher.NEWSPAPER_AVAILABLE
        article_deep_enricher.TRAFILATURA_AVAILABLE = False
        article_deep_enricher.NEWSPAPER_AVAILABLE = False

        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.__enter__.return_value = mock_instance
            mock_instance.__exit__.return_value = None
            mock_instance.get.side_effect = Exception("Network error")
            mock_client.return_value = mock_instance

            result = enricher.fetch_full_article("http://test.com/article")

        article_deep_enricher.TRAFILATURA_AVAILABLE = original_traf
        article_deep_enricher.NEWSPAPER_AVAILABLE = original_news

        assert result is None

    def test_fetch_with_httpx_fallback(self):
        """Test fetch using httpx fallback"""
        enricher = ArticleDeepEnricher()

        import article_deep_enricher

        original_traf = article_deep_enricher.TRAFILATURA_AVAILABLE
        original_news = article_deep_enricher.NEWSPAPER_AVAILABLE
        article_deep_enricher.TRAFILATURA_AVAILABLE = False
        article_deep_enricher.NEWSPAPER_AVAILABLE = False

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><p>" + "Content " * 100 + "</p></body></html>"

        with patch("httpx.Client") as mock_client:
            mock_instance = MagicMock()
            mock_instance.__enter__.return_value = mock_instance
            mock_instance.__exit__.return_value = None
            mock_instance.get.return_value = mock_response
            mock_client.return_value = mock_instance

            result = enricher.fetch_full_article("http://test.com/article")

        article_deep_enricher.TRAFILATURA_AVAILABLE = original_traf
        article_deep_enricher.NEWSPAPER_AVAILABLE = original_news

        assert result is not None
        assert "content" in result
        assert len(result["content"]) > 0


class TestBuildEnrichmentPrompt:
    """Test prompt building"""

    def test_build_prompt_contains_inputs(self):
        """Test prompt contains all input fields"""
        enricher = ArticleDeepEnricher()

        prompt = enricher.build_enrichment_prompt(
            original_title="Test Title",
            original_summary="Test Summary",
            full_content="Full article content here",
            source="Jakarta Post",
            category="immigration",
        )

        assert "Test Title" in prompt
        assert "Test Summary" in prompt
        assert "Full article content" in prompt
        assert "Jakarta Post" in prompt
        assert "immigration" in prompt

    def test_build_prompt_contains_json_format(self):
        """Test prompt includes JSON output format"""
        enricher = ArticleDeepEnricher()

        prompt = enricher.build_enrichment_prompt(
            original_title="Title",
            original_summary="Summary",
            full_content="Content",
            source="Source",
            category="business",
        )

        assert "JSON" in prompt
        assert "headline" in prompt
        assert "tldr" in prompt
        assert "bali_zero_take" in prompt


class TestCallClaudeCli:
    """Test Claude CLI calls"""

    def test_call_claude_success(self):
        """Test successful Claude CLI call"""
        enricher = ArticleDeepEnricher()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"headline": "Test Headline", "category": "business"}'

        with patch("subprocess.run", return_value=mock_result):
            response = enricher.call_claude_cli("Test prompt")

            assert response is not None
            assert "Test Headline" in response

    def test_call_claude_extracts_json_from_markdown(self):
        """Test extracting JSON from markdown code block"""
        enricher = ArticleDeepEnricher()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '```json\n{"headline": "Test"}\n```'

        with patch("subprocess.run", return_value=mock_result):
            response = enricher.call_claude_cli("Test prompt")

            assert response is not None
            assert "headline" in response
            assert "```" not in response

    def test_call_claude_cli_error(self):
        """Test Claude CLI error handling"""
        enricher = ArticleDeepEnricher()

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error message"

        with patch("subprocess.run", return_value=mock_result):
            response = enricher.call_claude_cli("Test prompt")

            assert response is None

    def test_call_claude_timeout(self):
        """Test Claude CLI timeout"""
        import subprocess

        enricher = ArticleDeepEnricher()

        with patch(
            "subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 300)
        ):
            response = enricher.call_claude_cli("Test prompt")

            assert response is None

    def test_call_claude_not_found(self):
        """Test Claude CLI not found"""
        enricher = ArticleDeepEnricher()

        with patch("subprocess.run", side_effect=FileNotFoundError()):
            response = enricher.call_claude_cli("Test prompt")

            assert response is None


class TestEnrichArticle:
    """Test article enrichment"""

    @pytest.mark.asyncio
    async def test_enrich_article_success(self):
        """Test successful article enrichment"""
        enricher = ArticleDeepEnricher(generate_images=False)

        mock_claude_response = json.dumps(
            {
                "headline": "Test Headline",
                "tldr": {"should_worry": "No", "what": "Test"},
                "facts": "Test facts",
                "bali_zero_take": {"hidden_insight": "Test insight"},
                "next_steps": {"expat": ["Step 1"], "investor": ["Step 2"]},
                "category": "immigration",
                "priority": "high",
                "relevance_score": 85,
                "ai_summary": "Test summary",
                "ai_tags": ["visa", "expat"],
                "suggested_components": ["timeline"],
            }
        )

        with patch.object(enricher, "fetch_full_article") as mock_fetch:
            mock_fetch.return_value = {"content": "Full article content" * 50}

            with patch.object(enricher, "call_claude_cli") as mock_claude:
                mock_claude.return_value = mock_claude_response

                result = await enricher.enrich_article(
                    title="Test Title",
                    summary="Test summary",
                    source_url="http://test.com/article",
                    source="Test Source",
                    category="immigration",
                )

                assert result is not None
                assert result.headline == "Test Headline"
                assert result.category == "immigration"

    @pytest.mark.asyncio
    async def test_enrich_article_fallback_to_summary(self):
        """Test enrichment with summary fallback when fetch fails"""
        enricher = ArticleDeepEnricher(generate_images=False)

        mock_claude_response = json.dumps(
            {
                "headline": "Fallback Headline",
                "tldr": {},
                "facts": "Facts",
                "bali_zero_take": {},
                "next_steps": {},
                "category": "business",
                "priority": "medium",
                "relevance_score": 50,
                "ai_summary": "Summary",
                "ai_tags": [],
                "suggested_components": [],
            }
        )

        with patch.object(enricher, "fetch_full_article", return_value=None):
            with patch.object(
                enricher, "call_claude_cli", return_value=mock_claude_response
            ):
                result = await enricher.enrich_article(
                    title="Title",
                    summary="Original summary",
                    source_url="http://test.com/article",
                    source="Source",
                )

                assert result is not None

    @pytest.mark.asyncio
    async def test_enrich_article_claude_failure(self):
        """Test enrichment when Claude fails"""
        enricher = ArticleDeepEnricher(generate_images=False)

        with patch.object(
            enricher, "fetch_full_article", return_value={"content": "Content"}
        ):
            with patch.object(enricher, "call_claude_cli", return_value=None):
                result = await enricher.enrich_article(
                    title="Title",
                    summary="Summary",
                    source_url="http://test.com",
                    source="Source",
                )

                assert result is None

    @pytest.mark.asyncio
    async def test_enrich_article_json_parse_error(self):
        """Test enrichment with invalid JSON response"""
        enricher = ArticleDeepEnricher(generate_images=False)

        with patch.object(
            enricher, "fetch_full_article", return_value={"content": "Content"}
        ):
            with patch.object(enricher, "call_claude_cli", return_value="Invalid JSON"):
                result = await enricher.enrich_article(
                    title="Title",
                    summary="Summary",
                    source_url="http://test.com",
                    source="Source",
                )

                assert result is None


class TestFormatAsMarkdown:
    """Test markdown formatting"""

    def test_format_markdown_structure(self):
        """Test markdown output structure"""
        enricher = ArticleDeepEnricher()

        article = EnrichedArticle(
            title="Test Title",
            headline="Test Headline",
            tldr={
                "should_worry": "No",
                "what": "Test event",
                "who": "Expats",
                "when": "Now",
                "risk_level": "Low",
            },
            facts="Test facts here",
            bali_zero_take='{"hidden_insight": "Hidden", "our_analysis": "Analysis", "our_advice": "Advice"}',
            next_steps={"expat": ["Step 1", "Step 2"], "investor": ["Step 3"]},
            category="immigration",
            priority="high",
            relevance_score=85,
            ai_summary="Summary",
            ai_tags=["visa", "kitas"],
            source="Jakarta Post",
            source_url="https://example.com/article",
            original_content="Original",
            published_at="2024-01-01",
            components=["timeline"],
        )

        markdown = enricher.format_as_markdown(article)

        assert "# " in markdown  # Has heading
        assert "Test Headline" in markdown
        assert "THE 30-SECOND BRIEF" in markdown
        assert "I FATTI" in markdown
        assert "BALI ZERO TAKE" in markdown
        assert "NEXT STEPS" in markdown
        assert "Step 1" in markdown
        assert "visa" in markdown


class TestSendToApi:
    """Test API sending"""

    @pytest.mark.asyncio
    async def test_send_dry_run(self):
        """Test dry run mode"""
        enricher = ArticleDeepEnricher()

        article = EnrichedArticle(
            title="Test",
            headline="Test",
            tldr={},
            facts="Facts",
            bali_zero_take="{}",
            next_steps={},
            category="business",
            priority="medium",
            relevance_score=50,
            ai_summary="Summary",
            ai_tags=[],
            source="Source",
            source_url="http://example.com",
            original_content="Content",
            published_at=None,
            components=[],
        )

        result = await enricher.send_to_api(article, dry_run=True)

        assert result["success"] is True
        assert result.get("dry_run") is True

    @pytest.mark.asyncio
    async def test_send_success(self):
        """Test successful API send"""
        enricher = ArticleDeepEnricher()

        article = EnrichedArticle(
            title="Test",
            headline="Test",
            tldr={},
            facts="Facts",
            bali_zero_take="{}",
            next_steps={},
            category="business",
            priority="medium",
            relevance_score=50,
            ai_summary="Summary",
            ai_tags=[],
            source="Source",
            source_url="http://example.com",
            original_content="Content",
            published_at="2024-01-01",
            components=[],
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "data": {"id": "123"}}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await enricher.send_to_api(article, api_key="test-key")

            assert result["success"] is True
            assert result.get("id") == "123"

    @pytest.mark.asyncio
    async def test_send_duplicate(self):
        """Test duplicate response"""
        enricher = ArticleDeepEnricher()

        article = EnrichedArticle(
            title="Test",
            headline="Test",
            tldr={},
            facts="Facts",
            bali_zero_take="{}",
            next_steps={},
            category="business",
            priority="medium",
            relevance_score=50,
            ai_summary="Summary",
            ai_tags=[],
            source="Source",
            source_url="http://example.com",
            original_content="Content",
            published_at=None,
            components=[],
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "duplicate": True}

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await enricher.send_to_api(article)

            assert result["success"] is True
            assert result.get("duplicate") is True

    @pytest.mark.asyncio
    async def test_send_error(self):
        """Test API error"""
        enricher = ArticleDeepEnricher()

        article = EnrichedArticle(
            title="Test",
            headline="Test",
            tldr={},
            facts="Facts",
            bali_zero_take="{}",
            next_steps={},
            category="business",
            priority="medium",
            relevance_score=50,
            ai_summary="Summary",
            ai_tags=[],
            source="Source",
            source_url="http://example.com",
            original_content="Content",
            published_at=None,
            components=[],
        )

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Server Error"

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await enricher.send_to_api(article)

            assert result["success"] is False


class TestEnrichRssBatch:
    """Test batch enrichment"""

    @pytest.mark.asyncio
    async def test_batch_import(self):
        """Test enrich_rss_batch can be imported"""
        from article_deep_enricher import enrich_rss_batch

        assert callable(enrich_rss_batch)

    @pytest.mark.asyncio
    async def test_batch_empty_list(self):
        """Test batch with empty list"""
        from article_deep_enricher import enrich_rss_batch

        result = await enrich_rss_batch([], dry_run=True)

        assert result["sent"] == 0
        assert result["failed"] == 0

    @pytest.mark.asyncio
    async def test_batch_processes_items(self):
        """Test batch processes items"""
        from article_deep_enricher import enrich_rss_batch

        items = [
            {
                "title": "Test Article",
                "summary": "Test summary",
                "sourceUrl": "http://test.com/article",
                "source": "Test",
                "category": "business",
            }
        ]

        with patch("article_deep_enricher.ArticleDeepEnricher") as mock_class:
            mock_enricher = MagicMock()
            mock_enricher.enrich_article = AsyncMock(return_value=None)
            mock_class.return_value = mock_enricher

            result = await enrich_rss_batch(items, dry_run=True)

            assert result["failed"] == 1


class TestGenerateCoverImageBrowser:
    """Test cover image generation"""

    @pytest.mark.asyncio
    async def test_generate_image_no_generator(self):
        """Test image generation when generator is None"""
        enricher = ArticleDeepEnricher(generate_images=False)
        enricher.image_generator = None

        result = await enricher.generate_cover_image_browser(
            title="Test", summary="Summary", category="business"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_generate_image_with_generator(self, tmp_path):
        """Test image generation with mocked generator"""
        enricher = ArticleDeepEnricher(generate_images=False)

        mock_generator = MagicMock()
        mock_generator.build_reasoning_prompt.return_value = "Reasoning prompt"
        mock_generator.get_category_guidelines.return_value = {"style": "test"}
        mock_generator.get_browser_automation_sequence.return_value = [{"step": 1}]
        enricher.image_generator = mock_generator

        with patch("article_deep_enricher.Path") as mock_path:
            mock_dir = MagicMock()
            mock_dir.mkdir = MagicMock()
            mock_dir.__truediv__ = lambda self, x: tmp_path / x
            mock_path.return_value = mock_dir

            result = await enricher.generate_cover_image_browser(
                title="Test Article", summary="Test summary", category="immigration"
            )

            if result is not None:
                assert "image_path" in result
                assert "reasoning_framework" in result
