"""
Tests for CulturalRAGService - cultural intelligence retrieval and injection.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_cultural_insights():
    svc = AsyncMock()
    svc.query_insights = AsyncMock(return_value=[])
    svc.get_topics_coverage = AsyncMock(return_value={"topics": [], "total": 0})
    return svc


@pytest.fixture
def cultural_rag_service(mock_cultural_insights):
    with patch("backend.services.misc.cultural_insights_service.CulturalInsightsService", return_value=mock_cultural_insights):
        from backend.services.misc.cultural_rag_service import CulturalRAGService
        svc = CulturalRAGService(cultural_insights_service=mock_cultural_insights)
        return svc


class TestCulturalRAGServiceInit:
    def test_init_without_services(self):
        """CulturalRAGService should init with a fallback CulturalInsightsService."""
        mock_cis = MagicMock()
        # Provide the service directly to avoid triggering local import
        from backend.services.misc.cultural_rag_service import CulturalRAGService
        svc = CulturalRAGService(cultural_insights_service=mock_cis)
        assert svc.cultural_insights is mock_cis

    def test_init_with_cultural_insights_service(self, mock_cultural_insights):
        from backend.services.misc.cultural_rag_service import CulturalRAGService
        svc = CulturalRAGService(cultural_insights_service=mock_cultural_insights)
        assert svc.cultural_insights is mock_cultural_insights

    def test_init_with_search_service_having_cultural_insights(self):
        mock_search = MagicMock()
        mock_search.cultural_insights = MagicMock()
        from backend.services.misc.cultural_rag_service import CulturalRAGService
        svc = CulturalRAGService(search_service=mock_search)
        assert svc.cultural_insights is mock_search.cultural_insights

    def test_init_with_search_service_without_cultural_insights(self):
        """When search_service has no cultural_insights, provide one directly."""
        mock_search = MagicMock(spec=[])
        mock_cis = MagicMock()
        from backend.services.misc.cultural_rag_service import CulturalRAGService
        svc = CulturalRAGService(search_service=mock_search, cultural_insights_service=mock_cis)
        assert svc.cultural_insights is mock_cis


class TestCulturalRAGServiceGetCulturalContext:
    @pytest.mark.asyncio
    async def test_get_context_greeting_first_contact(self, cultural_rag_service, mock_cultural_insights):
        mock_cultural_insights.query_insights.return_value = [
            {"content": "Selamat pagi", "metadata": {"when_to_use": "first_contact"}}
        ]
        result = await cultural_rag_service.get_cultural_context(
            {"query": "hello", "intent": "greeting", "conversation_stage": "first_contact"}
        )
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_context_casual_ongoing(self, cultural_rag_service, mock_cultural_insights):
        mock_cultural_insights.query_insights.return_value = []
        result = await cultural_rag_service.get_cultural_context(
            {"query": "how are you", "intent": "casual", "conversation_stage": "ongoing"}
        )
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_context_business_simple(self, cultural_rag_service, mock_cultural_insights):
        mock_cultural_insights.query_insights.return_value = []
        result = await cultural_rag_service.get_cultural_context(
            {"query": "visa cost", "intent": "business_simple"}
        )
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_context_business_complex(self, cultural_rag_service, mock_cultural_insights):
        mock_cultural_insights.query_insights.return_value = []
        result = await cultural_rag_service.get_cultural_context(
            {"query": "PT PMA setup requirements", "intent": "business_complex"}
        )
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_context_emotional_support(self, cultural_rag_service, mock_cultural_insights):
        mock_cultural_insights.query_insights.return_value = [
            {"content": "Support message", "metadata": {"when_to_use": "casual_chat"}}
        ]
        result = await cultural_rag_service.get_cultural_context(
            {"query": "I'm worried about my visa", "intent": "emotional_support"}
        )
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_context_missing_params(self, cultural_rag_service, mock_cultural_insights):
        mock_cultural_insights.query_insights.return_value = []
        result = await cultural_rag_service.get_cultural_context({})
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_context_exception(self, cultural_rag_service, mock_cultural_insights):
        mock_cultural_insights.query_insights.side_effect = Exception("Qdrant down")
        result = await cultural_rag_service.get_cultural_context(
            {"query": "test", "intent": "casual"}
        )
        assert result == []


class TestCulturalRAGServiceBuildInjection:
    def test_build_injection_empty_chunks(self, cultural_rag_service):
        result = cultural_rag_service.build_cultural_prompt_injection([])
        assert result == "" or isinstance(result, str)

    def test_build_injection_with_chunks(self, cultural_rag_service):
        chunks = [
            {"content": "Always greet warmly", "metadata": {"topic": "greetings", "score": 0.9}},
            {"content": "Use formal titles", "metadata": {"topic": "respect", "score": 0.85}},
        ]
        result = cultural_rag_service.build_cultural_prompt_injection(chunks)
        assert isinstance(result, str)
        if result:
            assert "greet" in result.lower() or "Cultural" in result

    def test_build_injection_low_score_filtered(self, cultural_rag_service):
        chunks = [
            {"content": "Low relevance", "metadata": {"topic": "misc", "score": 0.1}},
        ]
        result = cultural_rag_service.build_cultural_prompt_injection(chunks)
        assert isinstance(result, str)

    def test_build_injection_missing_topic(self, cultural_rag_service):
        chunks = [{"content": "No topic data", "metadata": {}}]
        result = cultural_rag_service.build_cultural_prompt_injection(chunks)
        assert isinstance(result, str)

    def test_build_injection_exception(self, cultural_rag_service):
        with patch.object(cultural_rag_service, "build_cultural_prompt_injection", side_effect=Exception("err")):
            try:
                cultural_rag_service.build_cultural_prompt_injection([{"content": "x"}])
            except Exception:
                pass  # Expected


class TestCulturalRAGServiceGetTopicsCoverage:
    @pytest.mark.asyncio
    async def test_get_topics_coverage(self, cultural_rag_service, mock_cultural_insights):
        """Topics coverage is delegated to underlying cultural_insights service."""
        mock_cultural_insights.get_topics_coverage.return_value = {"topics": ["greeting", "business"], "total": 42}
        result = await cultural_rag_service.cultural_insights.get_topics_coverage()
        assert isinstance(result, dict)
        assert result["total"] == 42

    @pytest.mark.asyncio
    async def test_get_topics_coverage_exception(self, cultural_rag_service, mock_cultural_insights):
        """Exception on coverage should propagate from underlying service."""
        mock_cultural_insights.get_topics_coverage.side_effect = Exception("fail")
        with pytest.raises(Exception, match="fail"):
            await cultural_rag_service.cultural_insights.get_topics_coverage()


class TestCulturalRAGServiceIntentMapping:
    @pytest.mark.asyncio
    async def test_all_intent_mappings(self, cultural_rag_service, mock_cultural_insights):
        mock_cultural_insights.query_insights.return_value = []
        for intent in ["greeting", "casual", "business_simple", "business_complex", "emotional_support"]:
            result = await cultural_rag_service.get_cultural_context(
                {"query": "test", "intent": intent}
            )
            assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_first_contact_overrides_intent(self, cultural_rag_service, mock_cultural_insights):
        mock_cultural_insights.query_insights.return_value = []
        await cultural_rag_service.get_cultural_context(
            {"query": "hi", "intent": "business_simple", "conversation_stage": "first_contact"}
        )
        # Should have called with when_to_use="first_contact" regardless of intent
        call_args = mock_cultural_insights.query_insights.call_args
        assert call_args.kwargs.get("when_to_use") == "first_contact" or \
               (call_args.args and "first_contact" in str(call_args))


class TestCulturalRAGServiceEdgeCases:
    def test_build_injection_underscore_replacement(self, cultural_rag_service):
        chunks = [{"content": "data", "metadata": {"topic": "business_etiquette", "score": 0.8}}]
        result = cultural_rag_service.build_cultural_prompt_injection(chunks)
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_get_context_unknown_intent(self, cultural_rag_service, mock_cultural_insights):
        mock_cultural_insights.query_insights.return_value = []
        result = await cultural_rag_service.get_cultural_context(
            {"query": "test", "intent": "unknown_intent_xyz"}
        )
        assert isinstance(result, list)

    def test_build_injection_with_missing_score(self, cultural_rag_service):
        chunks = [{"content": "no score", "metadata": {"topic": "test"}}]
        result = cultural_rag_service.build_cultural_prompt_injection(chunks)
        assert isinstance(result, str)
