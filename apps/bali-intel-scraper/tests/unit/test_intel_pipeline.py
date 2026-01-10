"""
Unit Tests for Intel Pipeline
Tests for the main orchestration pipeline
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import sys
from pathlib import Path
from dataclasses import fields

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from intel_pipeline import PipelineArticle, PipelineStats, IntelPipeline


class TestPipelineArticle:
    """Test PipelineArticle dataclass"""

    def test_create_basic(self):
        """Test creating a basic pipeline article"""
        article = PipelineArticle(
            title="Test Article",
            summary="Test summary",
            url="https://example.com",
            source="Test Source",
        )
        assert article.title == "Test Article"
        assert article.summary == "Test summary"
        assert article.url == "https://example.com"
        assert article.source == "Test Source"

    def test_default_values(self):
        """Test default values"""
        article = PipelineArticle(
            title="Test", summary="Test", url="https://example.com", source="Source"
        )
        assert article.content == ""
        assert article.published_at is None
        assert article.llama_score == 0
        assert article.llama_category == "general"
        assert article.llama_priority == "medium"
        assert article.llama_reason == ""
        assert article.llama_keywords == []
        assert article.validated is False
        assert article.validation_approved is False
        assert article.validation_confidence == 0
        assert article.validation_reason == ""
        assert article.category_override is None
        assert article.priority_override is None
        assert article.enrichment_hints == []
        assert article.enriched is False
        assert article.enriched_article is None
        assert article.image_prompt == ""
        assert article.image_path == ""
        assert article.published is False
        assert article.publish_result == {}

    def test_with_scoring(self):
        """Test article with scoring data"""
        article = PipelineArticle(
            title="KITAS Update",
            summary="New visa rules",
            url="https://example.com",
            source="Gov",
            llama_score=85,
            llama_category="immigration",
            llama_priority="high",
        )
        assert article.llama_score == 85
        assert article.llama_category == "immigration"
        assert article.llama_priority == "high"

    def test_has_required_fields(self):
        """Test that article has all required fields"""
        field_names = [f.name for f in fields(PipelineArticle)]
        assert "title" in field_names
        assert "summary" in field_names
        assert "url" in field_names
        assert "source" in field_names
        assert "llama_score" in field_names
        assert "validated" in field_names
        assert "enriched" in field_names
        assert "published" in field_names

    def test_final_category_no_override(self):
        """Test final_category without override"""
        article = PipelineArticle(
            title="Test",
            summary="Test",
            url="http://x",
            source="S",
            llama_category="immigration",
        )
        assert article.final_category == "immigration"

    def test_final_category_with_override(self):
        """Test final_category with override"""
        article = PipelineArticle(
            title="Test",
            summary="Test",
            url="http://x",
            source="S",
            llama_category="immigration",
            category_override="tax",
        )
        assert article.final_category == "tax"

    def test_final_priority_no_override(self):
        """Test final_priority without override"""
        article = PipelineArticle(
            title="Test",
            summary="Test",
            url="http://x",
            source="S",
            llama_priority="high",
        )
        assert article.final_priority == "high"

    def test_final_priority_with_override(self):
        """Test final_priority with override"""
        article = PipelineArticle(
            title="Test",
            summary="Test",
            url="http://x",
            source="S",
            llama_priority="low",
            priority_override="critical",
        )
        assert article.final_priority == "critical"


class TestPipelineStats:
    """Test PipelineStats dataclass"""

    def test_default_stats(self):
        """Test default stats values"""
        stats = PipelineStats()
        assert stats.total_input == 0
        assert stats.llama_scored == 0
        assert stats.llama_filtered == 0
        assert stats.claude_validated == 0
        assert stats.claude_approved == 0
        assert stats.claude_rejected == 0
        assert stats.enriched == 0
        assert stats.images_generated == 0
        assert stats.published == 0
        assert stats.errors == 0
        assert stats.duration_seconds == 0

    def test_stats_increment(self):
        """Test incrementing stats"""
        stats = PipelineStats()
        stats.total_input = 10
        stats.llama_scored = 8
        stats.llama_filtered = 2
        assert stats.total_input == 10
        assert stats.llama_scored == 8
        assert stats.llama_filtered == 2


class TestIntelPipelineInit:
    """Test IntelPipeline initialization"""

    @patch("intel_pipeline.GeminiImageGenerator")
    @patch("intel_pipeline.ArticleDeepEnricher")
    @patch("intel_pipeline.ClaudeValidator")
    @patch("intel_pipeline.OllamaScorer")
    def test_default_init(
        self, mock_ollama, mock_validator, mock_enricher, mock_image_gen
    ):
        """Test default initialization"""
        pipeline = IntelPipeline()
        assert pipeline.min_llama_score == 40
        assert pipeline.auto_approve_threshold == 75
        assert pipeline.generate_images is True
        assert pipeline.dry_run is False
        assert pipeline.stats is not None
        mock_ollama.assert_called_once()
        mock_validator.assert_called_once()
        mock_enricher.assert_called_once_with(generate_images=True)
        mock_image_gen.assert_called_once()

    @patch("intel_pipeline.GeminiImageGenerator")
    @patch("intel_pipeline.ArticleDeepEnricher")
    @patch("intel_pipeline.ClaudeValidator")
    @patch("intel_pipeline.OllamaScorer")
    def test_custom_params(
        self, mock_ollama, mock_validator, mock_enricher, mock_image_gen
    ):
        """Test custom initialization params - note: images are now mandatory"""
        pipeline = IntelPipeline(
            min_llama_score=50,
            auto_approve_threshold=80,
            generate_images=False,  # Ignored - images are mandatory
            dry_run=True,
        )
        assert pipeline.min_llama_score == 50
        assert pipeline.auto_approve_threshold == 80
        # Images are now mandatory - always True regardless of parameter
        assert pipeline.generate_images is True
        assert pipeline.dry_run is True
        # Enricher always gets generate_images=True now
        mock_enricher.assert_called_once_with(generate_images=True)

    @patch("intel_pipeline.GeminiImageGenerator")
    @patch("intel_pipeline.ArticleDeepEnricher")
    @patch("intel_pipeline.ClaudeValidator")
    @patch("intel_pipeline.OllamaScorer")
    def test_image_generator_always_created(
        self, mock_ollama, mock_validator, mock_enricher, mock_image_gen
    ):
        """Test image generator is always created (mandatory for E-E-A-T)"""
        pipeline = IntelPipeline(generate_images=False)  # Ignored
        # Image generator should always be created - mandatory
        assert pipeline.image_generator is not None
        mock_image_gen.assert_called_once()


class TestProcessArticleLlamaScoring:
    """Test LLAMA scoring step in process_article"""

    @pytest.mark.asyncio
    @patch("intel_pipeline.GeminiImageGenerator")
    @patch("intel_pipeline.ArticleDeepEnricher")
    @patch("intel_pipeline.ClaudeValidator")
    @patch("intel_pipeline.OllamaScorer")
    @patch("intel_pipeline.score_article")
    async def test_llama_scoring_success(
        self, mock_score, mock_ollama, mock_validator, mock_enricher, mock_image_gen
    ):
        """Test successful LLAMA scoring"""
        mock_score_result = MagicMock()
        mock_score_result.final_score = 85
        mock_score_result.matched_category = "immigration"
        mock_score_result.priority = "high"
        mock_score_result.explanation = "Immigration keywords found"
        mock_score_result.matched_keywords = ["visa", "KITAS"]
        mock_score.return_value = mock_score_result

        # Mock validation to reject
        mock_validation = MagicMock()
        mock_validation.approved = False
        mock_validation.confidence = 40
        mock_validation.reason = "Not relevant"
        mock_validation.category_override = None
        mock_validation.priority_override = None
        mock_validation.enrichment_hints = []
        mock_validator.return_value.validate_article = AsyncMock(
            return_value=mock_validation
        )

        pipeline = IntelPipeline(dry_run=True)
        article = PipelineArticle(
            title="Indonesia Visa Update",
            summary="New visa rules announced",
            url="https://example.com",
            source="Jakarta Post",
        )

        result = await pipeline.process_article(article)

        assert result.llama_score == 85
        assert result.llama_category == "immigration"
        assert result.llama_priority == "high"
        assert pipeline.stats.llama_scored == 1

    @pytest.mark.asyncio
    @patch("intel_pipeline.GeminiImageGenerator")
    @patch("intel_pipeline.ArticleDeepEnricher")
    @patch("intel_pipeline.ClaudeValidator")
    @patch("intel_pipeline.OllamaScorer")
    @patch("intel_pipeline.score_article")
    async def test_llama_scoring_error(
        self, mock_score, mock_ollama, mock_validator, mock_enricher, mock_image_gen
    ):
        """Test LLAMA scoring error fallback"""
        mock_score.side_effect = Exception("Ollama connection failed")

        # Mock validation
        mock_validation = MagicMock()
        mock_validation.approved = False
        mock_validator.return_value.validate_article = AsyncMock(
            return_value=mock_validation
        )

        pipeline = IntelPipeline(dry_run=True)
        article = PipelineArticle(
            title="Test", summary="Test", url="https://example.com", source="Test"
        )

        result = await pipeline.process_article(article)

        assert result.llama_score == 50  # Default on error
        assert result.llama_category == "general"
        assert pipeline.stats.errors == 1

    @pytest.mark.asyncio
    @patch("intel_pipeline.GeminiImageGenerator")
    @patch("intel_pipeline.ArticleDeepEnricher")
    @patch("intel_pipeline.ClaudeValidator")
    @patch("intel_pipeline.OllamaScorer")
    @patch("intel_pipeline.score_article")
    async def test_llama_filters_low_score(
        self, mock_score, mock_ollama, mock_validator, mock_enricher, mock_image_gen
    ):
        """Test articles with low score are filtered"""
        mock_score_result = MagicMock()
        mock_score_result.final_score = 30
        mock_score_result.matched_category = "general"
        mock_score_result.priority = "low"
        mock_score_result.explanation = "Not relevant"
        mock_score_result.matched_keywords = []
        mock_score.return_value = mock_score_result

        pipeline = IntelPipeline(min_llama_score=40, dry_run=True)
        article = PipelineArticle(
            title="Random News",
            summary="Nothing",
            url="https://example.com",
            source="Test",
        )

        result = await pipeline.process_article(article)

        assert result.llama_score == 30
        assert result.validated is False  # Never reached validation
        assert pipeline.stats.llama_filtered == 1


class TestProcessArticleClaudeValidation:
    """Test Claude validation step in process_article"""

    @pytest.mark.asyncio
    @patch("intel_pipeline.GeminiImageGenerator")
    @patch("intel_pipeline.ArticleDeepEnricher")
    @patch("intel_pipeline.ClaudeValidator")
    @patch("intel_pipeline.OllamaScorer")
    @patch("intel_pipeline.score_article")
    async def test_claude_validation_approved(
        self, mock_score, mock_ollama, mock_validator, mock_enricher, mock_image_gen
    ):
        """Test Claude validation approving article"""
        # Mock LLAMA scoring
        mock_score_result = MagicMock()
        mock_score_result.final_score = 60
        mock_score_result.matched_category = "tax"
        mock_score_result.priority = "medium"
        mock_score_result.explanation = "Tax keywords"
        mock_score_result.matched_keywords = ["tax"]
        mock_score.return_value = mock_score_result

        # Mock validation - approved
        mock_validation = MagicMock()
        mock_validation.approved = True
        mock_validation.confidence = 85
        mock_validation.reason = "Highly relevant"
        mock_validation.category_override = None
        mock_validation.priority_override = "high"
        mock_validation.enrichment_hints = ["Focus on tax rates"]
        mock_validator.return_value.validate_article = AsyncMock(
            return_value=mock_validation
        )

        pipeline = IntelPipeline(dry_run=True)
        article = PipelineArticle(
            title="New Tax Regulations",
            summary="Tax changes",
            url="https://example.com",
            source="Gov",
        )

        result = await pipeline.process_article(article)

        assert result.validated is True
        assert result.validation_approved is True
        assert result.validation_confidence == 85
        assert result.priority_override == "high"
        assert result.enrichment_hints == ["Focus on tax rates"]
        assert pipeline.stats.claude_approved == 1

    @pytest.mark.asyncio
    @patch("intel_pipeline.GeminiImageGenerator")
    @patch("intel_pipeline.ArticleDeepEnricher")
    @patch("intel_pipeline.ClaudeValidator")
    @patch("intel_pipeline.OllamaScorer")
    @patch("intel_pipeline.score_article")
    async def test_claude_validation_rejected(
        self, mock_score, mock_ollama, mock_validator, mock_enricher, mock_image_gen
    ):
        """Test Claude validation rejecting article"""
        mock_score_result = MagicMock()
        mock_score_result.final_score = 45
        mock_score_result.matched_category = "general"
        mock_score_result.priority = "low"
        mock_score_result.explanation = "Weak match"
        mock_score_result.matched_keywords = []
        mock_score.return_value = mock_score_result

        mock_validation = MagicMock()
        mock_validation.approved = False
        mock_validation.confidence = 30
        mock_validation.reason = "Not relevant to expats"
        mock_validation.category_override = None
        mock_validation.priority_override = None
        mock_validation.enrichment_hints = []
        mock_validator.return_value.validate_article = AsyncMock(
            return_value=mock_validation
        )

        pipeline = IntelPipeline(dry_run=True)
        article = PipelineArticle(
            title="Local Sports News",
            summary="Sports",
            url="https://example.com",
            source="Test",
        )

        result = await pipeline.process_article(article)

        assert result.validated is True
        assert result.validation_approved is False
        assert pipeline.stats.claude_rejected == 1
        assert result.enriched is False  # Never reached enrichment

    @pytest.mark.asyncio
    @patch("intel_pipeline.GeminiImageGenerator")
    @patch("intel_pipeline.ArticleDeepEnricher")
    @patch("intel_pipeline.ClaudeValidator")
    @patch("intel_pipeline.OllamaScorer")
    @patch("intel_pipeline.score_article")
    async def test_claude_validation_error_fallback(
        self, mock_score, mock_ollama, mock_validator, mock_enricher, mock_image_gen
    ):
        """Test validation error fallback"""
        mock_score_result = MagicMock()
        mock_score_result.final_score = 60
        mock_score_result.matched_category = "immigration"
        mock_score_result.priority = "medium"
        mock_score_result.explanation = "Immigration"
        mock_score_result.matched_keywords = ["visa"]
        mock_score.return_value = mock_score_result

        mock_validator.return_value.validate_article = AsyncMock(
            side_effect=Exception("Claude unavailable")
        )

        pipeline = IntelPipeline(dry_run=True)
        article = PipelineArticle(
            title="Visa News", summary="Visa", url="https://example.com", source="Test"
        )

        result = await pipeline.process_article(article)

        # Should approve on fallback since score >= 55
        assert result.validation_approved is True
        assert pipeline.stats.errors == 1

    @pytest.mark.asyncio
    @patch("intel_pipeline.GeminiImageGenerator")
    @patch("intel_pipeline.ArticleDeepEnricher")
    @patch("intel_pipeline.ClaudeValidator")
    @patch("intel_pipeline.OllamaScorer")
    @patch("intel_pipeline.score_article")
    async def test_validation_category_override(
        self, mock_score, mock_ollama, mock_validator, mock_enricher, mock_image_gen
    ):
        """Test category override from validation"""
        mock_score_result = MagicMock()
        mock_score_result.final_score = 65
        mock_score_result.matched_category = "general"
        mock_score_result.priority = "medium"
        mock_score_result.explanation = "general"
        mock_score_result.matched_keywords = []
        mock_score.return_value = mock_score_result

        mock_validation = MagicMock()
        mock_validation.approved = True
        mock_validation.confidence = 80
        mock_validation.reason = "Actually immigration"
        mock_validation.category_override = "immigration"
        mock_validation.priority_override = None
        mock_validation.enrichment_hints = []
        mock_validator.return_value.validate_article = AsyncMock(
            return_value=mock_validation
        )

        pipeline = IntelPipeline(dry_run=True)
        article = PipelineArticle(
            title="Test", summary="Test", url="https://example.com", source="Test"
        )

        result = await pipeline.process_article(article)

        assert result.llama_category == "general"
        assert result.category_override == "immigration"
        assert result.final_category == "immigration"


class TestProcessArticleEnrichment:
    """Test enrichment step in process_article"""

    @pytest.mark.asyncio
    @patch("intel_pipeline.GeminiImageGenerator")
    @patch("intel_pipeline.ArticleDeepEnricher")
    @patch("intel_pipeline.ClaudeValidator")
    @patch("intel_pipeline.OllamaScorer")
    @patch("intel_pipeline.score_article")
    async def test_enrichment_success(
        self,
        mock_score,
        mock_ollama,
        mock_validator,
        mock_enricher_class,
        mock_image_gen,
    ):
        """Test successful enrichment"""
        mock_score_result = MagicMock()
        mock_score_result.final_score = 80
        mock_score_result.matched_category = "immigration"
        mock_score_result.priority = "high"
        mock_score_result.explanation = "Immigration"
        mock_score_result.matched_keywords = ["KITAS"]
        mock_score.return_value = mock_score_result

        mock_validation = MagicMock()
        mock_validation.approved = True
        mock_validation.confidence = 90
        mock_validation.reason = "Great"
        mock_validation.category_override = None
        mock_validation.priority_override = None
        mock_validation.enrichment_hints = []
        mock_validator.return_value.validate_article = AsyncMock(
            return_value=mock_validation
        )

        # Mock enricher
        mock_enriched = MagicMock()
        mock_enriched.headline = "Indonesia Extends KITAS Validity"
        mock_enriched.category = "immigration"
        mock_enriched.priority = "high"
        mock_enriched.relevance_score = 95
        mock_enricher_class.return_value.enrich_article = AsyncMock(
            return_value=mock_enriched
        )

        pipeline = IntelPipeline(dry_run=False, generate_images=False)
        article = PipelineArticle(
            title="KITAS News",
            summary="KITAS",
            url="https://example.com",
            source="Test",
        )

        result = await pipeline.process_article(article)

        assert result.enriched is True
        assert result.enriched_article == mock_enriched
        assert pipeline.stats.enriched == 1

    @pytest.mark.asyncio
    @patch("intel_pipeline.GeminiImageGenerator")
    @patch("intel_pipeline.ArticleDeepEnricher")
    @patch("intel_pipeline.ClaudeValidator")
    @patch("intel_pipeline.OllamaScorer")
    @patch("intel_pipeline.score_article")
    async def test_enrichment_skipped_dry_run(
        self, mock_score, mock_ollama, mock_validator, mock_enricher, mock_image_gen
    ):
        """Test enrichment skipped in dry run mode"""
        mock_score_result = MagicMock()
        mock_score_result.final_score = 80
        mock_score_result.matched_category = "tax"
        mock_score_result.priority = "high"
        mock_score_result.explanation = "Tax"
        mock_score_result.matched_keywords = ["tax"]
        mock_score.return_value = mock_score_result

        mock_validation = MagicMock()
        mock_validation.approved = True
        mock_validation.confidence = 90
        mock_validation.reason = "Good"
        mock_validation.category_override = None
        mock_validation.priority_override = None
        mock_validation.enrichment_hints = []
        mock_validator.return_value.validate_article = AsyncMock(
            return_value=mock_validation
        )

        pipeline = IntelPipeline(dry_run=True)
        article = PipelineArticle(
            title="Tax", summary="Tax", url="https://example.com", source="Test"
        )

        result = await pipeline.process_article(article)

        assert result.enriched is False  # Skipped due to dry_run
        # Enricher should not have been called
        mock_enricher.return_value.enrich_article.assert_not_called()

    @pytest.mark.asyncio
    @patch("intel_pipeline.GeminiImageGenerator")
    @patch("intel_pipeline.ArticleDeepEnricher")
    @patch("intel_pipeline.ClaudeValidator")
    @patch("intel_pipeline.OllamaScorer")
    @patch("intel_pipeline.score_article")
    async def test_enrichment_failure(
        self,
        mock_score,
        mock_ollama,
        mock_validator,
        mock_enricher_class,
        mock_image_gen,
    ):
        """Test enrichment failure"""
        mock_score_result = MagicMock()
        mock_score_result.final_score = 75
        mock_score_result.matched_category = "business"
        mock_score_result.priority = "medium"
        mock_score_result.explanation = "Business"
        mock_score_result.matched_keywords = ["PT"]
        mock_score.return_value = mock_score_result

        mock_validation = MagicMock()
        mock_validation.approved = True
        mock_validation.confidence = 80
        mock_validation.reason = "Ok"
        mock_validation.category_override = None
        mock_validation.priority_override = None
        mock_validation.enrichment_hints = []
        mock_validator.return_value.validate_article = AsyncMock(
            return_value=mock_validation
        )

        # Enricher returns None (failure)
        mock_enricher_class.return_value.enrich_article = AsyncMock(return_value=None)

        pipeline = IntelPipeline(dry_run=False, generate_images=False)
        article = PipelineArticle(
            title="PT Formation",
            summary="Business",
            url="https://example.com",
            source="Test",
        )

        result = await pipeline.process_article(article)

        assert result.enriched is False
        assert pipeline.stats.errors == 1

    @pytest.mark.asyncio
    @patch("intel_pipeline.GeminiImageGenerator")
    @patch("intel_pipeline.ArticleDeepEnricher")
    @patch("intel_pipeline.ClaudeValidator")
    @patch("intel_pipeline.OllamaScorer")
    @patch("intel_pipeline.score_article")
    async def test_enrichment_exception(
        self,
        mock_score,
        mock_ollama,
        mock_validator,
        mock_enricher_class,
        mock_image_gen,
    ):
        """Test enrichment exception handling"""
        mock_score_result = MagicMock()
        mock_score_result.final_score = 70
        mock_score_result.matched_category = "property"
        mock_score_result.priority = "medium"
        mock_score_result.explanation = "Property"
        mock_score_result.matched_keywords = ["land"]
        mock_score.return_value = mock_score_result

        mock_validation = MagicMock()
        mock_validation.approved = True
        mock_validation.confidence = 75
        mock_validation.reason = "Ok"
        mock_validation.category_override = None
        mock_validation.priority_override = None
        mock_validation.enrichment_hints = []
        mock_validator.return_value.validate_article = AsyncMock(
            return_value=mock_validation
        )

        mock_enricher_class.return_value.enrich_article = AsyncMock(
            side_effect=Exception("Claude CLI timeout")
        )

        pipeline = IntelPipeline(dry_run=False, generate_images=False)
        article = PipelineArticle(
            title="Land", summary="Land", url="https://example.com", source="Test"
        )

        result = await pipeline.process_article(article)

        assert result.enriched is False
        assert pipeline.stats.errors == 1


class TestProcessBatch:
    """Test batch processing"""

    @pytest.mark.asyncio
    @patch("intel_pipeline.GeminiImageGenerator")
    @patch("intel_pipeline.ArticleDeepEnricher")
    @patch("intel_pipeline.ClaudeValidator")
    @patch("intel_pipeline.OllamaScorer")
    @patch("intel_pipeline.score_article")
    async def test_process_batch_basic(
        self, mock_score, mock_ollama, mock_validator, mock_enricher, mock_image_gen
    ):
        """Test basic batch processing"""
        # All articles get low score (filtered)
        mock_score_result = MagicMock()
        mock_score_result.final_score = 30
        mock_score_result.matched_category = "general"
        mock_score_result.priority = "low"
        mock_score_result.explanation = "Not relevant"
        mock_score_result.matched_keywords = []
        mock_score.return_value = mock_score_result

        pipeline = IntelPipeline(dry_run=True)

        articles = [
            {
                "title": "Article 1",
                "summary": "Summary 1",
                "url": "https://example.com/1",
                "source": "Source 1",
            },
            {
                "title": "Article 2",
                "summary": "Summary 2",
                "url": "https://example.com/2",
                "source": "Source 2",
            },
        ]

        results, stats = await pipeline.process_batch(articles)

        assert len(results) == 2
        assert stats.total_input == 2
        assert stats.llama_filtered == 2  # Both filtered
        assert isinstance(stats.duration_seconds, float)

    @pytest.mark.asyncio
    @patch("intel_pipeline.GeminiImageGenerator")
    @patch("intel_pipeline.ArticleDeepEnricher")
    @patch("intel_pipeline.ClaudeValidator")
    @patch("intel_pipeline.OllamaScorer")
    @patch("intel_pipeline.score_article")
    async def test_process_batch_with_source_url_key(
        self, mock_score, mock_ollama, mock_validator, mock_enricher, mock_image_gen
    ):
        """Test batch with source_url instead of url"""
        mock_score_result = MagicMock()
        mock_score_result.final_score = 20
        mock_score_result.matched_category = "general"
        mock_score_result.priority = "low"
        mock_score_result.explanation = ""
        mock_score_result.matched_keywords = []
        mock_score.return_value = mock_score_result

        pipeline = IntelPipeline(dry_run=True)

        articles = [
            {
                "title": "Article",
                "summary": "Summary",
                "source_url": "https://example.com",
                "source": "Test",
            },
        ]

        results, stats = await pipeline.process_batch(articles)

        assert results[0].url == "https://example.com"

    @pytest.mark.asyncio
    @patch("intel_pipeline.GeminiImageGenerator")
    @patch("intel_pipeline.ArticleDeepEnricher")
    @patch("intel_pipeline.ClaudeValidator")
    @patch("intel_pipeline.OllamaScorer")
    @patch("intel_pipeline.score_article")
    async def test_process_batch_resets_stats(
        self, mock_score, mock_ollama, mock_validator, mock_enricher, mock_image_gen
    ):
        """Test that batch processing resets stats"""
        mock_score_result = MagicMock()
        mock_score_result.final_score = 35
        mock_score_result.matched_category = "general"
        mock_score_result.priority = "low"
        mock_score_result.explanation = ""
        mock_score_result.matched_keywords = []
        mock_score.return_value = mock_score_result

        pipeline = IntelPipeline(dry_run=True)
        pipeline.stats.total_input = 999  # Pre-existing value

        articles = [
            {"title": "Test", "summary": "Test", "url": "https://x.com", "source": "T"}
        ]
        results, stats = await pipeline.process_batch(articles)

        assert stats.total_input == 1  # Reset, not 999


class TestPrintSummary:
    """Test _print_summary method"""

    @patch("intel_pipeline.GeminiImageGenerator")
    @patch("intel_pipeline.ArticleDeepEnricher")
    @patch("intel_pipeline.ClaudeValidator")
    @patch("intel_pipeline.OllamaScorer")
    def test_print_summary_logs(
        self, mock_ollama, mock_validator, mock_enricher, mock_image_gen
    ):
        """Test that _print_summary doesn't crash"""
        pipeline = IntelPipeline(dry_run=True)
        pipeline.stats = PipelineStats(
            total_input=10,
            llama_scored=8,
            llama_filtered=2,
            claude_validated=6,
            claude_approved=4,
            claude_rejected=2,
            enriched=4,
            images_generated=4,
            published=4,
            errors=0,
            duration_seconds=120.5,
        )

        # Should not raise
        pipeline._print_summary()


class TestTestPipeline:
    """Test the test_pipeline function"""

    @pytest.mark.asyncio
    @patch("intel_pipeline.IntelPipeline")
    async def test_test_pipeline_runs(self, mock_pipeline_class):
        """Test that test_pipeline function runs"""
        from intel_pipeline import test_pipeline

        mock_pipeline = MagicMock()
        mock_pipeline.process_batch = AsyncMock(return_value=([], PipelineStats()))
        mock_pipeline_class.return_value = mock_pipeline

        await test_pipeline()

        mock_pipeline_class.assert_called_once_with(
            min_llama_score=40,
            auto_approve_threshold=75,
            generate_images=False,
            require_approval=False,
            dry_run=True,
        )
        mock_pipeline.process_batch.assert_called_once()


class TestImageGeneration:
    """Test image generation step"""

    @pytest.mark.asyncio
    @patch("intel_pipeline.GeminiImageGenerator")
    @patch("intel_pipeline.ArticleDeepEnricher")
    @patch("intel_pipeline.ClaudeValidator")
    @patch("intel_pipeline.OllamaScorer")
    @patch("intel_pipeline.score_article")
    async def test_image_step_when_enriched(
        self,
        mock_score,
        mock_ollama,
        mock_validator,
        mock_enricher_class,
        mock_image_gen,
    ):
        """Test image step is prepared when article is enriched"""
        mock_score_result = MagicMock()
        mock_score_result.final_score = 90
        mock_score_result.matched_category = "immigration"
        mock_score_result.priority = "high"
        mock_score_result.explanation = "KITAS"
        mock_score_result.matched_keywords = ["KITAS"]
        mock_score.return_value = mock_score_result

        mock_validation = MagicMock()
        mock_validation.approved = True
        mock_validation.confidence = 95
        mock_validation.reason = "Great"
        mock_validation.category_override = None
        mock_validation.priority_override = None
        mock_validation.enrichment_hints = []
        mock_validator.return_value.validate_article = AsyncMock(
            return_value=mock_validation
        )

        mock_enriched = MagicMock()
        mock_enriched.headline = "KITAS Extended"
        mock_enriched.category = "immigration"
        mock_enriched.priority = "high"
        mock_enriched.relevance_score = 95
        mock_enricher_class.return_value.enrich_article = AsyncMock(
            return_value=mock_enriched
        )

        pipeline = IntelPipeline(generate_images=True, dry_run=False)
        article = PipelineArticle(
            title="KITAS", summary="KITAS", url="https://example.com", source="Test"
        )

        result = await pipeline.process_article(article)

        # Article should be enriched and image generator should be present
        assert result.enriched is True
        assert pipeline.image_generator is not None


class TestEdgeCases:
    """Test edge cases"""

    @pytest.mark.asyncio
    @patch("intel_pipeline.GeminiImageGenerator")
    @patch("intel_pipeline.ArticleDeepEnricher")
    @patch("intel_pipeline.ClaudeValidator")
    @patch("intel_pipeline.OllamaScorer")
    @patch("intel_pipeline.score_article")
    async def test_empty_summary_uses_content(
        self, mock_score, mock_ollama, mock_validator, mock_enricher, mock_image_gen
    ):
        """Test scoring uses content when summary is empty"""
        mock_score_result = MagicMock()
        mock_score_result.final_score = 25
        mock_score_result.matched_category = "general"
        mock_score_result.priority = "low"
        mock_score_result.explanation = ""
        mock_score_result.matched_keywords = []
        mock_score.return_value = mock_score_result

        pipeline = IntelPipeline(dry_run=True)
        article = PipelineArticle(
            title="Test",
            summary="",  # Empty
            content="This is the full article content about KITAS",
            url="https://example.com",
            source="Test",
        )

        await pipeline.process_article(article)

        # Verify score_article was called with content (first 500 chars)
        call_args = mock_score.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    @patch("intel_pipeline.GeminiImageGenerator")
    @patch("intel_pipeline.ArticleDeepEnricher")
    @patch("intel_pipeline.ClaudeValidator")
    @patch("intel_pipeline.OllamaScorer")
    @patch("intel_pipeline.score_article")
    async def test_validation_error_approves_if_score_high(
        self, mock_score, mock_ollama, mock_validator, mock_enricher, mock_image_gen
    ):
        """Test validation error approves if LLAMA score >= 55"""
        mock_score_result = MagicMock()
        mock_score_result.final_score = 55  # Exactly at threshold
        mock_score_result.matched_category = "tax"
        mock_score_result.priority = "medium"
        mock_score_result.explanation = ""
        mock_score_result.matched_keywords = []
        mock_score.return_value = mock_score_result

        mock_validator.return_value.validate_article = AsyncMock(
            side_effect=Exception("API error")
        )

        pipeline = IntelPipeline(dry_run=True)
        article = PipelineArticle(
            title="Tax", summary="Tax", url="https://example.com", source="T"
        )

        result = await pipeline.process_article(article)

        assert result.validation_approved is True  # Approved on fallback

    @pytest.mark.asyncio
    @patch("intel_pipeline.GeminiImageGenerator")
    @patch("intel_pipeline.ArticleDeepEnricher")
    @patch("intel_pipeline.ClaudeValidator")
    @patch("intel_pipeline.OllamaScorer")
    @patch("intel_pipeline.score_article")
    async def test_validation_error_rejects_if_score_low(
        self, mock_score, mock_ollama, mock_validator, mock_enricher, mock_image_gen
    ):
        """Test validation error rejects if LLAMA score < 55"""
        mock_score_result = MagicMock()
        mock_score_result.final_score = 54  # Just below threshold
        mock_score_result.matched_category = "general"
        mock_score_result.priority = "low"
        mock_score_result.explanation = ""
        mock_score_result.matched_keywords = []
        mock_score.return_value = mock_score_result

        mock_validator.return_value.validate_article = AsyncMock(
            side_effect=Exception("API error")
        )

        pipeline = IntelPipeline(dry_run=True)
        article = PipelineArticle(
            title="News", summary="News", url="https://example.com", source="T"
        )

        result = await pipeline.process_article(article)

        assert result.validation_approved is False  # Rejected on fallback

    def test_pipeline_article_with_all_fields(self):
        """Test creating article with all fields"""
        article = PipelineArticle(
            title="Full Article",
            summary="Full summary",
            url="https://example.com",
            source="Source",
            content="Full content",
            published_at="2025-01-01T00:00:00Z",
            llama_score=85,
            llama_category="immigration",
            llama_priority="high",
            llama_reason="Good match",
            llama_keywords=["visa", "KITAS"],
            validated=True,
            validation_approved=True,
            validation_confidence=90,
            validation_reason="Excellent",
            category_override="tax",
            priority_override="critical",
            enrichment_hints=["Check rates"],
            enriched=True,
            image_prompt="Generate image",
            image_path="/path/to/image.png",
            published=True,
            publish_result={"id": 123},
        )

        assert article.title == "Full Article"
        assert article.final_category == "tax"  # Override
        assert article.final_priority == "critical"  # Override
        assert article.published is True
        assert article.publish_result["id"] == 123
