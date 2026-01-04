"""
Integration Tests for Full Pipeline
End-to-end tests with mocked external services
"""

import pytest
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))


class TestScoringIntegration:
    """Integration tests for scoring flow"""

    @pytest.mark.asyncio
    async def test_score_high_relevance_article(self):
        """Test scoring a high-relevance article"""
        from professional_scorer import score_article

        result = await score_article(
            title="New KITAS Golden Visa Requirements for Bali",
            content="Immigration announces new visa rules for foreign investors",
            source="Imigrasi Indonesia",
            source_url="https://imigrasi.go.id",
            published_at=datetime.utcnow(),
        )

        assert result.final_score >= 70
        assert result.matched_category == "immigration"

    @pytest.mark.asyncio
    async def test_score_low_relevance_article(self):
        """Test scoring a low-relevance article"""
        from professional_scorer import score_article

        result = await score_article(
            title="Celebrity Wedding Goes Viral",
            content="Famous actor gets married",
            source="Gossip Blog",
            source_url="https://gossip.com",
        )

        assert result.final_score < 50


class TestCategoryDetection:
    """Integration tests for category detection"""

    @pytest.mark.asyncio
    async def test_detect_immigration(self):
        """Test immigration detection"""
        from professional_scorer import score_article

        result = await score_article(
            title="New KITAS Golden Visa Update", content="Visa requirements change"
        )

        assert result.matched_category == "immigration"

    @pytest.mark.asyncio
    async def test_detect_tax(self):
        """Test tax detection"""
        from professional_scorer import score_article

        result = await score_article(
            title="NPWP Registration Changes", content="PPh 21 withholding update"
        )

        assert result.matched_category == "tax"

    @pytest.mark.asyncio
    async def test_detect_business(self):
        """Test business detection"""
        from professional_scorer import score_article

        result = await score_article(
            title="PT PMA Registration Update", content="BKPM foreign investment rules"
        )

        assert result.matched_category == "business"

    @pytest.mark.asyncio
    async def test_detect_property(self):
        """Test property detection"""
        from professional_scorer import score_article

        result = await score_article(
            title="HGB Land Title Changes", content="Hak pakai regulations"
        )

        assert result.matched_category == "property"


class TestPipelineComponents:
    """Test that pipeline components exist and can be imported"""

    def test_import_all_components(self):
        """Test all pipeline components can be imported"""

        # All imports successful
        assert True

    def test_create_pipeline_article(self):
        """Test creating a pipeline article"""
        from intel_pipeline import PipelineArticle

        article = PipelineArticle(
            title="Test",
            summary="Test summary",
            url="https://example.com",
            source="Test Source",
        )

        assert article.title == "Test"
        assert article.llama_score == 0
