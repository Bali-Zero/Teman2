"""
Test suite for confidence scoring in RAG system (Phase 2)

Tests confidence calculation, evidence scoring, and abstain decisions
for the agentic RAG orchestrator.

Author: Windsurf (QA Engineer)
Created: 2026-02-09
Updated: 2026-02-16 - Fixed to use correct reasoning_utils API
"""

import pytest

from backend.app.core.constants import EvidenceScoreConstants

# Import from the correct module
from backend.services.rag.agentic.reasoning_utils import (
    calculate_evidence_score,
    get_critical_domain_type,
    is_critical_domain,
)


class TestConfidenceScoring:
    """Test confidence scoring logic for RAG responses"""

    def test_calculate_evidence_score_high_confidence(self):
        """Test evidence score calculation with high confidence indicators"""
        # High quality sources with scores > HIGH_QUALITY_SOURCE_THRESHOLD (0.15)
        sources = [
            {"id": 1, "title": "Source 1", "score": 0.85},
            {"id": 2, "title": "Source 2", "score": 0.75},
            {"id": 3, "title": "Source 3", "score": 0.70},
            {"id": 4, "title": "Source 4", "score": 0.65},
        ]
        # Context with query keywords for relevance bonus
        context = [
            "Visa requirements for Bali: Tourist visa valid for 30 days",
            "Extension process: Apply at immigration office 7 days before expiry",
            "Required documents: Passport, return ticket, proof of accommodation",
        ]
        query = "What are visa requirements for Bali?"

        score = calculate_evidence_score(sources=sources, context_gathered=context, query=query)

        # Should have high score: +0.5 (high quality) + 0.2 (multiple sources) + 0.3 (keywords)
        # Score should be >= 0.7 to be considered high confidence
        assert score >= 0.7
        assert score <= 1.0

    def test_calculate_evidence_score_low_confidence(self):
        """Test evidence score calculation with low confidence indicators"""
        # No sources, minimal context
        sources = []
        context = ["Generic information not related to query"]
        query = "What are visa requirements for Bali?"

        score = calculate_evidence_score(sources=sources, context_gathered=context, query=query)

        # Low confidence is below ABSTAIN_THRESHOLD (0.3)
        assert score < 0.3

    def test_calculate_evidence_score_no_context(self):
        """Test evidence score with no context items"""
        score = calculate_evidence_score(sources=[], context_gathered=[], query="Test query")

        assert score == 0.0

    def test_calculate_evidence_score_with_sources(self):
        """Test that high-quality sources boost evidence score"""
        # Low quality sources (score <= HIGH_QUALITY_SOURCE_THRESHOLD=0.15)
        sources_low = [{"id": 1, "title": "Source 1", "score": 0.1}]
        context = ["Relevant information about visa"]
        query = "visa requirements"

        score_low_quality = calculate_evidence_score(
            sources=sources_low, context_gathered=context, query=query,
        )

        # High quality sources (score > 0.15)
        sources_high = [{"id": 1, "title": "Source 1", "score": 0.85}]

        score_high_quality = calculate_evidence_score(
            sources=sources_high, context_gathered=context, query=query,
        )

        # High quality source adds HIGH_QUALITY_SOURCE_BONUS (0.5)
        assert score_high_quality > score_low_quality

    def test_calculate_evidence_score_multiple_sources(self):
        """Test that multiple sources increase confidence"""
        context = ["Information from search"]
        query = "test query"

        # Single source
        sources_single = [{"id": 1, "title": "Source 1", "score": 0.85}]

        score_single_source = calculate_evidence_score(
            sources=sources_single, context_gathered=context, query=query,
        )

        # Multiple sources (> MIN_SOURCES_FOR_BONUS which is 3)
        sources_multiple = [
            {"id": 1, "title": "Source 1", "score": 0.85},
            {"id": 2, "title": "Source 2", "score": 0.80},
            {"id": 3, "title": "Source 3", "score": 0.75},
            {"id": 4, "title": "Source 4", "score": 0.70},
        ]

        score_multiple_sources = calculate_evidence_score(
            sources=sources_multiple, context_gathered=context, query=query,
        )

        # Multiple sources adds MULTIPLE_SOURCES_BONUS (0.2)
        assert score_multiple_sources >= score_single_source


class TestCriticalDomainDetection:
    """Test critical domain detection for abstain decisions"""

    def test_is_critical_domain_visa(self):
        """Test visa queries are detected as critical"""
        visa_queries = [
            "How do I apply for a visa?",
            "What are visa requirements?",
            "Can I extend my visa in Bali?",
            "Visa application process",
        ]

        for query in visa_queries:
            assert is_critical_domain(query, "business_simple") is True

    def test_is_critical_domain_pricing(self):
        """Test pricing queries are detected as critical"""
        pricing_queries = [
            "What is the price?",
            "How much does it cost?",
            "Quanto costa?",
            "What are the fees?",
        ]

        for query in pricing_queries:
            assert is_critical_domain(query, "business_simple") is True

    def test_is_critical_domain_legal(self):
        """Test legal queries are detected as critical"""
        legal_queries = [
            "What are my legal rights?",
            "Contract law in Indonesia",
            "Legal requirements for business",
            "Immigration law",
        ]

        for query in legal_queries:
            assert is_critical_domain(query, "business_simple") is True

    def test_is_not_critical_domain(self):
        """Test non-critical queries are not flagged"""
        non_critical_queries = [
            "What's the weather like?",
            "Best restaurants in Bali",
            "How to get to the beach?",
            "General information about Bali",
        ]

        for query in non_critical_queries:
            assert is_critical_domain(query, "casual") is False

    def test_is_critical_domain_complex_intent(self):
        """Test that business_complex intent is always critical"""
        assert is_critical_domain("Tell me about Bali", "business_complex") is True
        assert is_critical_domain("Random query", "business_strategic") is True

    def test_get_critical_domain_type_visa(self):
        """Test critical domain type detection for visa"""
        domain = get_critical_domain_type("How do I apply for a visa?")
        assert domain == "visa"

    def test_get_critical_domain_type_pricing(self):
        """Test critical domain type detection for pricing"""
        domain = get_critical_domain_type("How much does it cost?")
        assert domain == "pricing"

    def test_get_critical_domain_type_legal(self):
        """Test critical domain type detection for legal"""
        domain = get_critical_domain_type("What are my legal rights?")
        assert domain == "legal"

    def test_get_critical_domain_type_procedure(self):
        """Test critical domain type detection for procedure"""
        domain = get_critical_domain_type("What documents do I need?")
        assert domain == "procedure"

    def test_get_critical_domain_type_default(self):
        """Test non-critical queries return 'business_complex' as default"""
        domain = get_critical_domain_type("Best restaurants in Bali")
        assert domain == "business_complex"


class TestAbstainDecision:
    """Test abstain decision logic based on confidence scores"""

    def test_should_abstain_critical_low_confidence(self):
        """Test abstain decision for critical domain with low confidence"""
        # Critical domain query
        query = "What are visa requirements for Bali?"
        is_crit = is_critical_domain(query, "business_simple")

        # Low evidence score (below ABSTAIN_THRESHOLD = 0.10)
        evidence_score = 0.05

        # Should abstain if critical and low confidence
        should_abstain = is_crit and evidence_score < EvidenceScoreConstants.ABSTAIN_THRESHOLD

        assert should_abstain is True

    def test_should_not_abstain_critical_high_confidence(self):
        """Test no abstain for critical domain with high confidence"""
        query = "What are visa requirements for Bali?"
        is_crit = is_critical_domain(query, "business_simple")

        # High evidence score (above ABSTAIN_THRESHOLD = 0.10)
        evidence_score = 0.85

        should_abstain = is_crit and evidence_score < EvidenceScoreConstants.ABSTAIN_THRESHOLD

        assert should_abstain is False

    def test_should_not_abstain_non_critical_low_confidence(self):
        """Test no abstain for non-critical domain even with low confidence"""
        query = "Best restaurants in Bali"
        is_crit = is_critical_domain(query, "casual")

        # Low evidence score
        evidence_score = 0.2

        should_abstain = is_crit and evidence_score < EvidenceScoreConstants.ABSTAIN_THRESHOLD

        assert should_abstain is False


class TestConfidenceThresholds:
    """Test confidence threshold constants"""

    def test_abstain_threshold(self):
        """Test that ABSTAIN_THRESHOLD is within valid range"""
        assert 0.0 <= EvidenceScoreConstants.ABSTAIN_THRESHOLD <= 1.0
        # ABSTAIN_THRESHOLD should be low (0.3 or less)
        assert EvidenceScoreConstants.ABSTAIN_THRESHOLD <= 0.3

    def test_high_quality_source_threshold(self):
        """Test that HIGH_QUALITY_SOURCE_THRESHOLD is within valid range"""
        assert 0.0 <= EvidenceScoreConstants.HIGH_QUALITY_SOURCE_THRESHOLD <= 1.0

    def test_threshold_values(self):
        """Test that all threshold values are reasonable"""
        assert EvidenceScoreConstants.ABSTAIN_THRESHOLD >= 0.0
        assert EvidenceScoreConstants.HIGH_QUALITY_SOURCE_THRESHOLD >= 0.0
        assert EvidenceScoreConstants.MAX_SCORE == 1.0


@pytest.mark.integration
class TestConfidenceScoringIntegration:
    """Integration tests for confidence scoring in full RAG pipeline"""

    @pytest.mark.asyncio
    async def test_confidence_scoring_in_reasoning_engine(self):
        """Test confidence scoring integration with reasoning engine"""
        # This will be implemented after reasoning engine is available
        pytest.skip("Requires full reasoning engine setup")

    @pytest.mark.asyncio
    async def test_abstain_decision_in_orchestrator(self):
        """Test abstain decision integration with orchestrator"""
        # This will be implemented after orchestrator is available
        pytest.skip("Requires full orchestrator setup")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
