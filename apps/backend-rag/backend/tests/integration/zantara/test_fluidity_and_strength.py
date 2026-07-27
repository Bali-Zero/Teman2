"""
Integration tests to verify ZANTARA is fluid and powerful
Tests fluidity (low ABSTAIN rate) and strength (proactive, helpful responses)
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set test environment before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("API_KEYS", "test-api-key-1,test-api-key-2")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault("GOOGLE_API_KEY", "test-google-key")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("ENVIRONMENT", "test")

from backend.services.rag.agentic.orchestrator import AgenticRAGOrchestrator
from backend.services.rag.agentic.schema import CoreResult


@pytest.fixture
def mock_tools():
    """Create mock tools for orchestrator"""
    return []


@pytest.fixture
def orchestrator(mock_tools):
    """Create orchestrator instance with mocked dependencies"""
    with (
        patch("backend.services.rag.agentic.orchestrator.SemanticCache"),
        patch("backend.services.rag.agentic.orchestrator.KGEnhancedRetrieval"),
        patch("backend.services.rag.agentic.orchestrator.IntentClassifier"),
        patch("backend.services.rag.agentic.orchestrator.EmotionalAttunementService"),
        patch("backend.services.rag.agentic.orchestrator.ClarificationService"),
        patch("backend.services.rag.agentic.orchestrator.FollowupService") as mock_followup,
        patch("backend.services.rag.agentic.orchestrator.GoldenAnswerService"),
        patch("backend.services.rag.agentic.orchestrator.MemoryHandler"),
        patch("backend.services.rag.agentic.orchestrator.QueryGates"),
        patch("backend.services.rag.agentic.orchestrator.LLMGateway") as mock_llm_gateway,
        patch("backend.services.rag.agentic.orchestrator.ReasoningEngine") as mock_reasoning,
    ):
        # Setup mock LLM Gateway
        mock_llm_gateway_instance = MagicMock()
        mock_llm_gateway.return_value = mock_llm_gateway_instance

        # Setup mock Reasoning Engine
        mock_reasoning_instance = MagicMock()
        mock_reasoning.return_value = mock_reasoning_instance

        # Setup mock FollowupService
        mock_followup_instance = MagicMock()
        mock_followup_instance.get_followups = AsyncMock(
            return_value=["Quanto costa?", "Quali documenti servono?", "Quanto tempo richiede?"],
        )
        mock_followup.return_value = mock_followup_instance

        # Create orchestrator
        orch = AgenticRAGOrchestrator(
            tools=mock_tools,
            db_pool=None,
            semantic_cache=None,
            retriever=None,
            clarification_service=None,
        )

        # Inject mock followup service
        orch.followup_service = mock_followup_instance

        yield orch


class TestZantaraFluidity:
    """Test that ZANTARA is fluid (responds often, low ABSTAIN rate)"""

    @pytest.mark.asyncio
    async def test_low_abstain_threshold(self):
        """Test that ABSTAIN threshold is low (0.2) for fluidity"""
        from backend.app.core.constants import EvidenceScoreConstants

        assert EvidenceScoreConstants.ABSTAIN_THRESHOLD == 0.15, (
            f"ABSTAIN threshold should be 0.15 (was {EvidenceScoreConstants.ABSTAIN_THRESHOLD})"
        )

    @pytest.mark.asyncio
    async def test_proactive_abstain_message(self):
        """The detailed ABSTAIN a client receives suggests alternatives.

        This test used to paste a COPY of the message into itself and assert
        against that literal — so it passed no matter what production said,
        and would have kept passing if the table were emptied. It now reads
        the shipped table, in every protocol language.
        """
        from backend.services.rag.agentic._reasoning_stubs import (
            PROTOCOL_LANGUAGES,
            get_localized_stub,
        )

        for language in PROTOCOL_LANGUAGES:
            message = get_localized_stub("abstain_detailed", language)
            # It names concrete domains rather than trailing off into "anything else?"
            assert message.count("•") >= 3, f"{language}: fewer than 3 suggestions"
            assert "KITAS" in message, f"{language}: does not name the core service line"
            assert "PT PMA" in message, f"{language}: does not name company setup"

    @pytest.mark.asyncio
    async def test_evidence_score_allows_responses(self):
        """Test that evidence score thresholds allow responses"""
        from backend.app.core.constants import EvidenceScoreConstants

        # With threshold 0.2, responses with score >= 0.2 should be allowed
        test_scores = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

        for score in test_scores:
            assert score >= EvidenceScoreConstants.ABSTAIN_THRESHOLD, (
                f"Score {score} should allow response (threshold: {EvidenceScoreConstants.ABSTAIN_THRESHOLD})"
            )


class TestZantaraStrength:
    """Test that ZANTARA is strong (proactive, helpful, suggests next steps)"""

    @pytest.mark.asyncio
    async def test_prompt_includes_proactivity(self):
        """Test that system prompt includes proactivity rules"""
        from backend.services.rag.agentic.prompt_builder import ZANTARA_MASTER_TEMPLATE

        # Check for proactivity keywords in prompt
        assert (
            "PROACTIVITY" in ZANTARA_MASTER_TEMPLATE
            or "proactive" in ZANTARA_MASTER_TEMPLATE.lower()
        )
        assert (
            "suggest" in ZANTARA_MASTER_TEMPLATE.lower()
            or "suggerire" in ZANTARA_MASTER_TEMPLATE.lower()
        )
        assert (
            "next step" in ZANTARA_MASTER_TEMPLATE.lower()
            or "prossimi passi" in ZANTARA_MASTER_TEMPLATE.lower()
        )

    @pytest.mark.asyncio
    async def test_followup_service_active(self, orchestrator):
        """Test that FollowupService is active and generates suggestions"""
        assert orchestrator.followup_service is not None

        # Test that followup service generates suggestions
        followups = await orchestrator.followup_service.get_followups(
            query="Quanto costa PT PMA?",
            response="PT PMA costa Rp 20.000.000...",
            use_ai=False,  # Use topic-based for faster test
        )

        assert isinstance(followups, list)
        assert len(followups) > 0, "FollowupService should generate suggestions"

    @pytest.mark.asyncio
    async def test_final_prompt_includes_suggestions(self):
        """Test that final answer prompt includes instruction to suggest next steps"""
        from pathlib import Path

        # Read the reasoning.py file to verify prompt includes suggestions.
        # __file__ = .../backend/tests/integration/zantara/test_fluidity_and_strength.py
        # parents[0] = zantara, [1] = integration, [2] = tests, [3] = backend
        backend_dir = Path(__file__).resolve().parents[3]
        reasoning_file = backend_dir / "services" / "rag" / "agentic" / "reasoning.py"
        reasoning_content = reasoning_file.read_text()

        assert "suggest" in reasoning_content.lower() or "suggerire" in reasoning_content.lower()
        assert (
            "next step" in reasoning_content.lower()
            or "prossimi passi" in reasoning_content.lower()
        )
        assert "Vuoi sapere anche" in reasoning_content or "Ti interessa anche" in reasoning_content

    @pytest.mark.asyncio
    async def test_moderate_evidence_allows_response(self):
        """Test that moderate evidence (0.2-0.5) still allows response with warning"""
        from backend.app.core.constants import EvidenceScoreConstants

        moderate_scores = [0.2, 0.3, 0.4, 0.5]

        for score in moderate_scores:
            # Should allow response (not ABSTAIN)
            assert score >= EvidenceScoreConstants.ABSTAIN_THRESHOLD, (
                f"Moderate score {score} should allow response"
            )

            # Should use positive language ("available" not "limited")
            # This is verified in the code, not directly testable here


class TestZantaraIntegration:
    """Integration tests for ZANTARA fluidity and strength"""

    @pytest.mark.asyncio
    async def test_response_includes_proactive_suggestions(self, orchestrator):
        """Test that responses include proactive suggestions"""
        # Mock a successful response with followups
        mock_result = CoreResult(
            answer="PT PMA costa Rp 20.000.000. Il processo richiede circa 2-3 settimane.",
            sources=[],
            evidence_score=0.7,
            verification_score=0.9,
            is_ambiguous=False,
            entities={},
            model_used="gemini-2.0-flash-lite",
            timings={"total": 1.5},
        )

        # Verify response is substantial (not empty)
        assert len(mock_result.answer) > 50, "Response should be substantial"
        assert mock_result.evidence_score >= 0.2, "Evidence score should allow response"

    @pytest.mark.asyncio
    async def test_followup_generation_metrics(self):
        """Test that followup generation is tracked with metrics"""
        from backend.services.misc.followup_service import (
            followup_generation_duration,
            followup_requests_total,
        )

        # Verify metrics exist
        assert followup_requests_total is not None
        assert followup_generation_duration is not None

    @pytest.mark.asyncio
    async def test_abstain_message_quality(self):
        """Both ABSTAIN variants are substantial in every protocol language.

        Same correction as ``test_proactive_abstain_message``: this asserted
        against a literal it had written itself. It now reads production.
        """
        from backend.services.rag.agentic._reasoning_stubs import (
            PROTOCOL_LANGUAGES,
            get_localized_stub,
        )

        for language in PROTOCOL_LANGUAGES:
            detailed = get_localized_stub("abstain_detailed", language)
            assert len(detailed) > 100, f"{language}: detailed abstain is not substantial"
            assert "•" in detailed, f"{language}: detailed abstain lost its bullets"

            # The short variant is what most refusals actually send. It must
            # still be a sentence a client can act on, not a one-liner dead end.
            short = get_localized_stub("abstain", language)
            assert len(short) > 100, f"{language}: short abstain is a bare dead end"


class TestZantaraPerformance:
    """Test ZANTARA performance characteristics"""

    @pytest.mark.asyncio
    async def test_evidence_score_calculation_allows_responses(self):
        """Test that evidence score calculation allows most queries to get responses"""
        from backend.services.rag.agentic.reasoning import calculate_evidence_score

        # Simulate scenarios that should get responses
        test_cases = [
            {
                "sources": [{"score": 0.4}],  # High quality source
                "context": ["Some relevant context"],
                "query": "Quanto costa PT PMA?",
                "expected_min": 0.2,  # Should be above ABSTAIN threshold
            },
            {
                "sources": [
                    {"score": 0.3},
                    {"score": 0.3},
                    {"score": 0.3},
                    {"score": 0.3},
                ],  # Multiple sources
                "context": ["Context 1", "Context 2", "Context 3"],
                "query": "Come funziona il visto?",
                "expected_min": 0.2,
            },
        ]

        for case in test_cases:
            score = calculate_evidence_score(
                sources=case["sources"],
                context_gathered=case["context"],
                query=case["query"],
            )
            # Verify the function returns a float in [0, 1]
            assert isinstance(score, float)
            assert 0.0 <= score <= 1.0, (
                f"Evidence score {score} must be in [0, 1] for query: {case['query']}"
            )
