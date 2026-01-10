import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from scripts.intel_pipeline import IntelPipeline


@pytest.fixture
def mock_scorer():
    with patch("scripts.intel_pipeline.score_article") as mock:
        result = MagicMock()
        result.final_score = 80
        result.matched_category = "visa"
        result.priority = "high"
        result.explanation = "Strong match"
        result.matched_keywords = ["visa", "indonesia"]
        mock.return_value = result
        yield mock


@pytest.fixture
def mock_validator():
    with patch("scripts.intel_pipeline.ClaudeValidator") as mock_class:
        instance = mock_class.return_value
        validation = MagicMock()
        validation.approved = True
        validation.confidence = 90
        validation.reason = "Very relevant"
        validation.category_override = None
        validation.priority_override = None
        validation.enrichment_hints = ["Highlight E33G"]
        instance.validate_article = AsyncMock(return_value=validation)
        yield instance


@pytest.fixture
def mock_enricher():
    with patch("scripts.intel_pipeline.ArticleDeepEnricher") as mock_class:
        instance = mock_class.return_value
        enriched = MagicMock()
        enriched.headline = "Enriched Title"
        enriched.executive_brief = "Short summary"
        enriched.facts = """Fact 1
Fact 2"""
        enriched.bali_zero_take = "Our view"
        enriched.category = "visa"
        enriched.priority = "high"
        enriched.relevance_score = 85
        instance.enrich_article = AsyncMock(return_value=enriched)
        yield instance


@pytest.mark.asyncio
async def test_intel_pipeline_full_flow(mock_scorer, mock_validator, mock_enricher):
    """Test full pipeline flow with mocked components"""

    pipeline = IntelPipeline(
        min_llama_score=40,
        auto_approve_threshold=75,
        generate_images=False,
        require_approval=False,
        dry_run=False,
    )

    test_articles = [
        {
            "title": "New Visa Policy",
            "summary": "Indonesia changes visa rules.",
            "url": "http://example.com",
            "source": "News",
        }
    ]

    # Mock SEO optimizer to avoid errors
    with patch("scripts.intel_pipeline.seo_optimize") as mock_seo:
        mock_seo.return_value = {"seo": {"title": "SEO Title", "keywords": ["visa"]}}

        results, stats = await pipeline.process_batch(test_articles)

    # Verify stages
    assert stats.total_input == 1
    assert stats.llama_scored == 1
    assert stats.claude_approved == 1
    assert stats.enriched == 1
    assert stats.seo_optimized == 1

    # Verify article state
    article = results[0]
    assert article.enriched is True
    assert article.seo_optimized is True
    assert article.enriched_article.headline == "Enriched Title"


@pytest.mark.asyncio
async def test_intel_pipeline_filtering(mock_scorer):
    """Test that low score articles are filtered out"""

    # Setup low score
    mock_scorer.return_value.final_score = 20

    pipeline = IntelPipeline(min_llama_score=40)

    test_articles = [
        {"title": "Irrelevant", "summary": "...", "url": "http://x.com", "source": "X"}
    ]

    results, stats = await pipeline.process_batch(test_articles)

    assert stats.llama_filtered == 1
    assert results[0].enriched is False
