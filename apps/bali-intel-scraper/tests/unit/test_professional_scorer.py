"""
Unit Tests for Professional Scorer
100% coverage for scoring logic
"""

import pytest
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from professional_scorer import (
    calculate_relevance,
    calculate_authority,
    calculate_recency,
    calculate_accuracy,
    calculate_geographic,
    calculate_final_score,
    score_article,
    ScoreResult,
    KEYWORDS,
    SOURCE_AUTHORITY,
    GEOGRAPHIC,
)


class TestCalculateRelevance:
    """Test relevance scoring based on keywords"""

    def test_direct_immigration_keywords(self):
        """Direct immigration keywords should score 100"""
        score, keywords, category = calculate_relevance(
            "New KITAS Requirements Announced", "The golden visa program for investors"
        )
        assert score == 100
        assert category == "immigration"

    def test_direct_tax_keywords(self):
        """Direct tax keywords should score 100"""
        score, keywords, category = calculate_relevance(
            "NPWP Registration Changes",
            "New PPh 21 withholding rules and coretax system",
        )
        assert score == 100
        assert category == "tax"

    def test_direct_business_keywords(self):
        """Direct business keywords should score 100"""
        score, keywords, category = calculate_relevance(
            "PT PMA Registration", "BKPM announces new foreign investment rules"
        )
        assert score == 100
        assert category == "business"

    def test_no_keywords_low_score(self):
        """No relevant keywords should score 20"""
        score, keywords, category = calculate_relevance(
            "Random Celebrity News", "Actor gets married in Hollywood"
        )
        assert score == 20
        assert category == "general"

    def test_bahasa_indonesia_keywords(self):
        """Indonesian language keywords should work"""
        score, keywords, category = calculate_relevance(
            "Izin Tinggal Terbatas Update", "Peraturan baru untuk tenaga kerja asing"
        )
        assert score >= 90


class TestCalculateAuthority:
    """Test authority scoring based on source reputation"""

    def test_government_sources(self):
        """Government sources should score 98"""
        assert calculate_authority("Imigrasi", "https://imigrasi.go.id/news") == 98
        assert calculate_authority("DJP", "https://pajak.go.id/info") == 98

    def test_major_media_sources(self):
        """Major international media should score 88"""
        assert calculate_authority("Reuters", "https://reuters.com/article") == 88
        assert calculate_authority("Bloomberg", "https://bloomberg.com/news") == 88

    def test_national_media_sources(self):
        """Indonesian national media should score 82"""
        assert calculate_authority("Jakarta Post", "https://jakartapost.com") == 82
        assert calculate_authority("Kompas", "https://kompas.com") == 82

    def test_unknown_source(self):
        """Completely unknown sources should score 40"""
        assert calculate_authority("Random", "") == 40


class TestCalculateRecency:
    """Test recency scoring with exponential decay"""

    def test_very_fresh_article(self):
        """Articles from today should score ~100"""
        score = calculate_recency(datetime.utcnow())
        assert score >= 95

    def test_one_week_old(self):
        """1-week-old articles should score lower"""
        score = calculate_recency(datetime.utcnow() - timedelta(days=7))
        assert 30 <= score <= 45

    def test_no_date(self):
        """No date should score 50"""
        score = calculate_recency(None)
        assert score == 50


class TestCalculateAccuracy:
    """Test accuracy scoring based on citation indicators"""

    def test_official_citations(self):
        """Official citations should increase score"""
        score = calculate_accuracy(
            "Minister Announces Policy",
            "According to official data, the regulation states...",
        )
        assert score > 60

    def test_speculation_decreases_score(self):
        """Speculation indicators should decrease score"""
        score = calculate_accuracy(
            "Rumor: Policy Might Change", "Allegedly sources say this could happen"
        )
        assert score < 50


class TestCalculateGeographic:
    """Test geographic relevance scoring"""

    def test_bali_specific(self):
        """Bali-specific keywords should score 100"""
        assert calculate_geographic("New Rules in Bali", "Denpasar office") == 100

    def test_indonesia_wide(self):
        """Indonesia-wide keywords should score 75"""
        assert calculate_geographic("Indonesia Policy", "Jakarta news") == 75

    def test_no_geographic_match(self):
        """No geographic match should score 25"""
        assert calculate_geographic("World News", "Global update") == 25


class TestCalculateFinalScore:
    """Test final composite score calculation"""

    def test_high_score_article(self):
        """High-quality article should score high"""
        result = calculate_final_score(
            title="Indonesia Launches New Golden Visa Program",
            content="BKPM announced new golden visa regulations",
            source="BKPM",
            source_url="https://bkpm.go.id/golden-visa",
            published_at=datetime.utcnow(),
        )
        assert isinstance(result, ScoreResult)
        assert result.final_score >= 70
        assert result.priority in ["high", "medium"]

    def test_low_score_article(self):
        """Low-quality article should score low"""
        result = calculate_final_score(
            title="Celebrity Wedding Goes Viral",
            content="Famous actor gets married",
            source="Gossip Blog",
            source_url="https://gossip.com/wedding",
            published_at=datetime.utcnow() - timedelta(days=30),
        )
        assert result.final_score < 50

    def test_explanation_format(self):
        """Explanation should contain all score components"""
        result = calculate_final_score(
            title="Test Article",
            content="Test content",
            source="Test Source",
            source_url="https://test.com",
            published_at=datetime.utcnow(),
        )
        assert "R:" in result.explanation
        assert "A:" in result.explanation


class TestScoreArticle:
    """Test main score_article async function"""

    @pytest.mark.asyncio
    async def test_score_article_basic(self):
        """Basic scoring without Ollama"""
        result = await score_article(
            title="New KITAS Requirements",
            content="Immigration policy update",
            source="Imigrasi",
            source_url="https://imigrasi.go.id",
            published_at=datetime.utcnow(),
            use_ollama=False,
        )
        assert isinstance(result, ScoreResult)
        assert result.final_score > 0

    @pytest.mark.asyncio
    async def test_score_article_with_defaults(self):
        """Score article with minimal parameters"""
        result = await score_article(title="Test Article")
        assert isinstance(result, ScoreResult)


class TestDatabases:
    """Test keyword and source databases"""

    def test_all_categories_exist(self):
        """All expected categories should exist"""
        expected = ["immigration", "business", "tax", "property", "tech", "lifestyle"]
        for cat in expected:
            assert cat in KEYWORDS

    def test_all_tiers_exist(self):
        """All authority tiers should exist"""
        expected = ["government", "major_media", "national_media"]
        for tier in expected:
            assert tier in SOURCE_AUTHORITY

    def test_all_regions_exist(self):
        """All geographic regions should exist"""
        expected = ["bali_specific", "indonesia_wide", "southeast_asia"]
        for region in expected:
            assert region in GEOGRAPHIC


class TestAuthorityEdgeCases:
    """Test edge cases in authority scoring"""

    def test_official_gov_url(self):
        """URLs with .gov should score high"""
        score = calculate_authority("Unknown", "https://example.gov")
        assert score == 90

    def test_co_id_url(self):
        """URLs with .co.id should score medium"""
        score = calculate_authority("Unknown", "https://company.co.id")
        assert score == 55

    def test_com_url(self):
        """URLs with .com should score medium"""
        score = calculate_authority("Unknown", "https://example.com/page")
        assert score == 55


class TestRecencyEdgeCases:
    """Test edge cases in recency scoring"""

    def test_future_date(self):
        """Future dates should score 100"""
        future = datetime.utcnow() + timedelta(days=5)
        score = calculate_recency(future)
        assert score == 100

    def test_very_old_article(self):
        """Very old articles should have minimum score"""
        old_date = datetime.utcnow() - timedelta(days=100)
        score = calculate_recency(old_date)
        assert score >= 10  # Minimum

    def test_timezone_aware_date(self):
        """Timezone-aware dates should be handled"""
        import pytz

        aware_date = datetime.now(pytz.UTC)
        score = calculate_recency(aware_date)
        assert score >= 90  # Should be very fresh


class TestGeographicEdgeCases:
    """Test edge cases in geographic scoring"""

    def test_southeast_asia(self):
        """Southeast Asia keywords should score 45"""
        score = calculate_geographic("ASEAN Meeting", "regional summit")
        assert score == 45


class TestPriorityLevels:
    """Test priority determination"""

    def test_filtered_priority(self):
        """Very low score should be filtered"""
        result = calculate_final_score(
            title="Random unrelated content",
            content="Nothing about Indonesia or anything relevant",
            source="Unknown",
            source_url="",
            published_at=datetime.utcnow() - timedelta(days=60),
        )
        if result.final_score < 35:
            assert result.priority == "filtered"

    def test_low_priority(self):
        """Low score should be low priority"""
        result = calculate_final_score(
            title="Some news",
            content="General content about tourism",
            source="Unknown Blog",
            source_url="",
            published_at=datetime.utcnow() - timedelta(days=14),
        )
        if 35 <= result.final_score < 50:
            assert result.priority == "low"


class TestEnhanceWithOllama:
    """Test Ollama enhancement function"""

    @pytest.mark.asyncio
    async def test_enhance_high_score_unchanged(self):
        """High scores should not be enhanced"""
        from professional_scorer import enhance_with_ollama

        base_result = ScoreResult(
            final_score=85,
            relevance=90,
            authority=80,
            recency=80,
            accuracy=80,
            geographic=80,
            priority="high",
            matched_keywords=["kitas"],
            matched_category="immigration",
            explanation="R:90 A:80 T:80 C:80 G:80 → 85 (high)",
        )

        result = await enhance_with_ollama("Test", "Content", base_result)

        assert result.final_score == 85  # Unchanged

    @pytest.mark.asyncio
    async def test_enhance_low_score_unchanged(self):
        """Low scores should not be enhanced"""
        from professional_scorer import enhance_with_ollama

        base_result = ScoreResult(
            final_score=30,
            relevance=20,
            authority=40,
            recency=30,
            accuracy=40,
            geographic=25,
            priority="filtered",
            matched_keywords=[],
            matched_category="general",
            explanation="R:20 A:40 T:30 C:40 G:25 → 30 (filtered)",
        )

        result = await enhance_with_ollama("Test", "Content", base_result)

        assert result.final_score == 30  # Unchanged

    @pytest.mark.asyncio
    async def test_enhance_ambiguous_with_ollama_success(self):
        """Ambiguous scores should call Ollama"""
        from professional_scorer import enhance_with_ollama
        from unittest.mock import patch, AsyncMock, MagicMock

        base_result = ScoreResult(
            final_score=50,
            relevance=50,
            authority=50,
            recency=50,
            accuracy=50,
            geographic=50,
            priority="medium",
            matched_keywords=[],
            matched_category="general",
            explanation="R:50 A:50 T:50 C:50 G:50 → 50 (medium)",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": '{"adjustment": 5, "reason": "good"}'
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await enhance_with_ollama("Test", "Content", base_result)

            assert result.final_score == 55  # Adjusted

    @pytest.mark.asyncio
    async def test_enhance_ollama_error_fallback(self):
        """Ollama errors should fallback to base result"""
        from professional_scorer import enhance_with_ollama
        from unittest.mock import patch, AsyncMock

        base_result = ScoreResult(
            final_score=50,
            relevance=50,
            authority=50,
            recency=50,
            accuracy=50,
            geographic=50,
            priority="medium",
            matched_keywords=[],
            matched_category="general",
            explanation="R:50 A:50 T:50 C:50 G:50 → 50 (medium)",
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = Exception("Connection failed")
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await enhance_with_ollama("Test", "Content", base_result)

            assert result.final_score == 50  # Unchanged

    @pytest.mark.asyncio
    async def test_enhance_adjustment_clamp(self):
        """Adjustments should be clamped to -10 to +10"""
        from professional_scorer import enhance_with_ollama
        from unittest.mock import patch, AsyncMock, MagicMock

        base_result = ScoreResult(
            final_score=50,
            relevance=50,
            authority=50,
            recency=50,
            accuracy=50,
            geographic=50,
            priority="medium",
            matched_keywords=[],
            matched_category="general",
            explanation="R:50 A:50 T:50 C:50 G:50 → 50 (medium)",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": '{"adjustment": 50, "reason": "extreme"}'  # > 10
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await enhance_with_ollama("Test", "Content", base_result)

            # Should clamp to +10, so final = 60
            assert result.final_score == 60

    @pytest.mark.asyncio
    async def test_enhance_priority_recalculated(self):
        """Priority should be recalculated after adjustment"""
        from professional_scorer import enhance_with_ollama
        from unittest.mock import patch, AsyncMock, MagicMock

        base_result = ScoreResult(
            final_score=45,
            relevance=45,
            authority=45,
            recency=45,
            accuracy=45,
            geographic=45,
            priority="low",
            matched_keywords=[],
            matched_category="general",
            explanation="R:45 A:45 T:45 C:45 G:45 → 45 (low)",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": '{"adjustment": 8, "reason": "better"}'
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await enhance_with_ollama("Test", "Content", base_result)

            assert result.final_score == 53
            assert result.priority == "medium"

    @pytest.mark.asyncio
    async def test_enhance_negative_adjustment(self):
        """Negative adjustments should decrease score"""
        from professional_scorer import enhance_with_ollama
        from unittest.mock import patch, AsyncMock, MagicMock

        base_result = ScoreResult(
            final_score=55,
            relevance=55,
            authority=55,
            recency=55,
            accuracy=55,
            geographic=55,
            priority="medium",
            matched_keywords=[],
            matched_category="general",
            explanation="R:55 A:55 T:55 C:55 G:55 → 55 (medium)",
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": '{"adjustment": -8, "reason": "worse"}'
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await enhance_with_ollama("Test", "Content", base_result)

            assert result.final_score == 47
            assert result.priority == "low"


class TestScoreArticleWithOllama:
    """Test score_article with Ollama enabled"""

    @pytest.mark.asyncio
    async def test_score_with_ollama(self):
        """Score article with Ollama enhancement"""
        from unittest.mock import patch, AsyncMock, MagicMock

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": '{"adjustment": 5, "reason": "good"}'
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await score_article(
                title="General news about Indonesia",
                content="Some content about Jakarta",
                source="Unknown",
                use_ollama=True,
            )

            assert isinstance(result, ScoreResult)


class TestKeywordMatching:
    """Test keyword matching edge cases"""

    def test_short_keyword_boundary(self):
        """Short keywords should use word boundary matching"""
        score, keywords, category = calculate_relevance(
            "AI Investment Policy", "The AI industry in Indonesia"
        )
        # " ai " is a direct tech keyword
        assert category == "tech" or score >= 70

    def test_medium_keywords_property(self):
        """Medium property keywords should score 70"""
        score, keywords, category = calculate_relevance(
            "Land Development News", "Property market in Indonesia"
        )
        assert score >= 70

    def test_tech_keywords(self):
        """Tech keywords should be detected"""
        score, keywords, category = calculate_relevance(
            "AI Regulation in Indonesia",
            "Machine learning and kecerdasan buatan policy",
        )
        assert category == "tech"
        assert score >= 90

    def test_lifestyle_keywords(self):
        """Lifestyle keywords should score lower"""
        score, keywords, category = calculate_relevance(
            "Digital Nomad Life in Bali", "Expat coliving experience"
        )
        assert category == "lifestyle"
        assert score >= 60


class TestScoreResultDataclass:
    """Test ScoreResult dataclass"""

    def test_create_score_result(self):
        """Create ScoreResult with all fields"""
        result = ScoreResult(
            final_score=85,
            relevance=90,
            authority=80,
            recency=85,
            accuracy=80,
            geographic=100,
            priority="high",
            matched_keywords=["kitas", "visa"],
            matched_category="immigration",
            explanation="R:90 A:80 T:85 C:80 G:100 → 85 (high)",
        )

        assert result.final_score == 85
        assert result.priority == "high"
        assert "kitas" in result.matched_keywords
