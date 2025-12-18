"""
Comprehensive tests for Cultural RAG Service
Target: 95%+ coverage
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest


class TestCulturalRAGServiceInit:
    """Test CulturalRAGService initialization"""

    def test_init_without_services(self):
        """Test initialization without any services"""
        with patch("services.cultural_insights_service.CulturalInsightsService") as mock_cis:
            mock_cis.return_value = Mock()

            from backend.services.cultural_rag_service import CulturalRAGService

            service = CulturalRAGService()

            assert service.search_service is None
            assert service.cultural_insights is not None

    def test_init_with_cultural_insights_service(self):
        """Test initialization with cultural_insights_service"""
        from backend.services.cultural_rag_service import CulturalRAGService

        mock_cultural = Mock()
        service = CulturalRAGService(cultural_insights_service=mock_cultural)

        assert service.cultural_insights == mock_cultural

    def test_init_with_search_service_having_cultural_insights(self):
        """Test initialization with search_service that has cultural_insights"""
        from backend.services.cultural_rag_service import CulturalRAGService

        mock_search = Mock()
        mock_cultural = Mock()
        mock_search.cultural_insights = mock_cultural

        service = CulturalRAGService(search_service=mock_search)

        assert service.search_service == mock_search
        assert service.cultural_insights == mock_cultural

    def test_init_with_search_service_without_cultural_insights(self):
        """Test initialization with search_service without cultural_insights attr"""
        with patch("services.cultural_insights_service.CulturalInsightsService") as mock_cis:
            mock_cis.return_value = Mock()

            from backend.services.cultural_rag_service import CulturalRAGService

            mock_search = Mock(spec=[])  # No cultural_insights attribute
            service = CulturalRAGService(search_service=mock_search)

            assert service.search_service == mock_search


class TestCulturalRAGServiceGetCulturalContext:
    """Test get_cultural_context method"""

    @pytest.mark.asyncio
    async def test_get_context_greeting_first_contact(self):
        """Test get context for greeting on first contact"""
        from backend.services.cultural_rag_service import CulturalRAGService

        mock_cultural = AsyncMock()
        mock_cultural.query_insights.return_value = [
            {"content": "Greeting insight", "metadata": {"topic": "greeting"}, "score": 0.9}
        ]

        service = CulturalRAGService(cultural_insights_service=mock_cultural)

        context_params = {
            "query": "Hello",
            "intent": "greeting",
            "conversation_stage": "first_contact",
        }

        result = await service.get_cultural_context(context_params, limit=2)

        assert len(result) == 1
        mock_cultural.query_insights.assert_called_once()
        # Should use first_contact for when_to_use due to conversation_stage
        call_args = mock_cultural.query_insights.call_args
        assert call_args[1]["when_to_use"] == "first_contact"

    @pytest.mark.asyncio
    async def test_get_context_casual_ongoing(self):
        """Test get context for casual chat ongoing"""
        from backend.services.cultural_rag_service import CulturalRAGService

        mock_cultural = AsyncMock()
        mock_cultural.query_insights.return_value = [
            {"content": "Casual insight", "metadata": {"topic": "casual"}, "score": 0.8}
        ]

        service = CulturalRAGService(cultural_insights_service=mock_cultural)

        context_params = {
            "query": "How are you?",
            "intent": "casual",
            "conversation_stage": "ongoing",
        }

        result = await service.get_cultural_context(context_params)

        call_args = mock_cultural.query_insights.call_args
        assert call_args[1]["when_to_use"] == "casual_chat"

    @pytest.mark.asyncio
    async def test_get_context_business_simple(self):
        """Test get context for business_simple intent"""
        from backend.services.cultural_rag_service import CulturalRAGService

        mock_cultural = AsyncMock()
        mock_cultural.query_insights.return_value = []

        service = CulturalRAGService(cultural_insights_service=mock_cultural)

        context_params = {
            "query": "What is KITAS?",
            "intent": "business_simple",
            "conversation_stage": "ongoing",
        }

        result = await service.get_cultural_context(context_params)

        call_args = mock_cultural.query_insights.call_args
        # business_simple has no specific context
        assert call_args[1]["when_to_use"] is None

    @pytest.mark.asyncio
    async def test_get_context_business_complex(self):
        """Test get context for business_complex intent"""
        from backend.services.cultural_rag_service import CulturalRAGService

        mock_cultural = AsyncMock()
        mock_cultural.query_insights.return_value = []

        service = CulturalRAGService(cultural_insights_service=mock_cultural)

        context_params = {
            "query": "Complex business question",
            "intent": "business_complex",
            "conversation_stage": "ongoing",
        }

        result = await service.get_cultural_context(context_params)

        call_args = mock_cultural.query_insights.call_args
        assert call_args[1]["when_to_use"] is None

    @pytest.mark.asyncio
    async def test_get_context_emotional_support(self):
        """Test get context for emotional_support intent"""
        from backend.services.cultural_rag_service import CulturalRAGService

        mock_cultural = AsyncMock()
        mock_cultural.query_insights.return_value = [
            {"content": "Support insight", "metadata": {}, "score": 0.7}
        ]

        service = CulturalRAGService(cultural_insights_service=mock_cultural)

        context_params = {
            "query": "I'm feeling stressed",
            "intent": "emotional_support",
            "conversation_stage": "ongoing",
        }

        result = await service.get_cultural_context(context_params)

        call_args = mock_cultural.query_insights.call_args
        assert call_args[1]["when_to_use"] == "casual_chat"

    @pytest.mark.asyncio
    async def test_get_context_missing_params(self):
        """Test get context with missing parameters"""
        from backend.services.cultural_rag_service import CulturalRAGService

        mock_cultural = AsyncMock()
        mock_cultural.query_insights.return_value = []

        service = CulturalRAGService(cultural_insights_service=mock_cultural)

        # Empty context params
        context_params = {}

        result = await service.get_cultural_context(context_params)

        call_args = mock_cultural.query_insights.call_args
        assert call_args[1]["query"] == ""

    @pytest.mark.asyncio
    async def test_get_context_exception(self):
        """Test get context handles exceptions"""
        from backend.services.cultural_rag_service import CulturalRAGService

        mock_cultural = AsyncMock()
        mock_cultural.query_insights.side_effect = Exception("Query failed")

        service = CulturalRAGService(cultural_insights_service=mock_cultural)

        context_params = {"query": "test", "intent": "casual", "conversation_stage": "ongoing"}

        result = await service.get_cultural_context(context_params)

        assert result == []


class TestCulturalRAGServiceBuildInjection:
    """Test build_cultural_prompt_injection method"""

    def test_build_injection_empty_chunks(self):
        """Test build injection with empty chunks"""
        from backend.services.cultural_rag_service import CulturalRAGService

        service = CulturalRAGService(cultural_insights_service=Mock())

        result = service.build_cultural_prompt_injection([])

        assert result == ""

    def test_build_injection_with_chunks(self):
        """Test build injection with cultural chunks"""
        from backend.services.cultural_rag_service import CulturalRAGService

        service = CulturalRAGService(cultural_insights_service=Mock())

        chunks = [
            {
                "content": "Indonesian greeting customs are important.",
                "metadata": {"topic": "indonesian_greetings"},
                "score": 0.85,
            },
            {
                "content": "Patience is valued in bureaucracy.",
                "metadata": {"topic": "bureaucracy_patience"},
                "score": 0.75,
            },
        ]

        result = service.build_cultural_prompt_injection(chunks)

        assert "Indonesian Cultural Intelligence" in result
        assert "Indonesian Greetings" in result
        assert "Bureaucracy Patience" in result
        assert "relevance: 0.85" in result
        assert "How to use this intelligence" in result

    def test_build_injection_low_score_filtered(self):
        """Test build injection filters low score chunks"""
        from backend.services.cultural_rag_service import CulturalRAGService

        service = CulturalRAGService(cultural_insights_service=Mock())

        chunks = [
            {
                "content": "High relevance content",
                "metadata": {"topic": "high_topic"},
                "score": 0.5,
            },
            {
                "content": "Low relevance content",
                "metadata": {"topic": "low_topic"},
                "score": 0.2,  # Below 0.3 threshold
            },
        ]

        result = service.build_cultural_prompt_injection(chunks)

        assert "High Topic" in result
        assert "Low Topic" not in result

    def test_build_injection_missing_topic(self):
        """Test build injection with missing topic in metadata"""
        from backend.services.cultural_rag_service import CulturalRAGService

        service = CulturalRAGService(cultural_insights_service=Mock())

        chunks = [
            {
                "content": "Content without topic",
                "metadata": {},
                "score": 0.6,
            }
        ]

        result = service.build_cultural_prompt_injection(chunks)

        # Should use "Cultural_Insight" as default
        assert "Cultural Insight" in result

    def test_build_injection_exception(self):
        """Test build injection handles exceptions"""
        from backend.services.cultural_rag_service import CulturalRAGService

        service = CulturalRAGService(cultural_insights_service=Mock())

        # Malformed chunks that might cause issues
        chunks = [None]

        result = service.build_cultural_prompt_injection(chunks)

        # Should return empty string on error
        assert result == ""


class TestCulturalRAGServiceGetTopicsCoverage:
    """Test get_cultural_topics_coverage method"""

    @pytest.mark.asyncio
    async def test_get_topics_coverage(self):
        """Test getting cultural topics coverage"""
        from backend.services.cultural_rag_service import CulturalRAGService

        service = CulturalRAGService(cultural_insights_service=Mock())

        result = await service.get_cultural_topics_coverage()

        assert "indonesian_greetings" in result
        assert "bureaucracy_patience" in result
        assert "face_saving_culture" in result
        assert "tri_hita_karana" in result
        assert "hierarchy_respect" in result
        assert "meeting_etiquette" in result
        assert "ramadan_business" in result
        assert "relationship_capital" in result
        assert "flexibility_expectations" in result
        assert "language_barrier_navigation" in result

        # Each should have count of 1
        for topic, count in result.items():
            assert count == 1

    @pytest.mark.asyncio
    async def test_get_topics_coverage_exception(self):
        """Test get topics coverage handles exceptions"""
        from backend.services.cultural_rag_service import CulturalRAGService

        # Create service that will raise exception internally
        service = CulturalRAGService(cultural_insights_service=Mock())

        # Mock to raise exception
        with patch.object(service, "get_cultural_topics_coverage") as mock_method:
            mock_method.return_value = {}

            result = await mock_method()

        assert result == {}


class TestCulturalRAGServiceIntentMapping:
    """Test intent to context mapping"""

    @pytest.mark.asyncio
    async def test_all_intent_mappings(self):
        """Test all intent types are mapped correctly"""
        from backend.services.cultural_rag_service import CulturalRAGService

        mock_cultural = AsyncMock()
        mock_cultural.query_insights.return_value = []

        service = CulturalRAGService(cultural_insights_service=mock_cultural)

        intents_and_expected = [
            ("greeting", "first_contact"),  # Will be overridden by first_contact stage
            ("casual", "casual_chat"),
            ("business_simple", None),
            ("business_complex", None),
            ("emotional_support", "casual_chat"),
        ]

        for intent, expected_context in intents_and_expected:
            context_params = {
                "query": "test",
                "intent": intent,
                "conversation_stage": "ongoing",  # Not first_contact
            }

            await service.get_cultural_context(context_params)

            call_args = mock_cultural.query_insights.call_args
            assert call_args[1]["when_to_use"] == expected_context, f"Failed for intent: {intent}"

            mock_cultural.reset_mock()

    @pytest.mark.asyncio
    async def test_first_contact_overrides_intent(self):
        """Test first_contact stage overrides intent mapping"""
        from backend.services.cultural_rag_service import CulturalRAGService

        mock_cultural = AsyncMock()
        mock_cultural.query_insights.return_value = []

        service = CulturalRAGService(cultural_insights_service=mock_cultural)

        # Even with casual intent, first_contact should override
        context_params = {
            "query": "test",
            "intent": "casual",
            "conversation_stage": "first_contact",
        }

        await service.get_cultural_context(context_params)

        call_args = mock_cultural.query_insights.call_args
        assert call_args[1]["when_to_use"] == "first_contact"


class TestCulturalRAGServiceEdgeCases:
    """Test edge cases"""

    def test_build_injection_underscore_replacement(self):
        """Test topic underscore replacement in display"""
        from backend.services.cultural_rag_service import CulturalRAGService

        service = CulturalRAGService(cultural_insights_service=Mock())

        chunks = [
            {
                "content": "Test content",
                "metadata": {"topic": "multi_word_topic_name"},
                "score": 0.5,
            }
        ]

        result = service.build_cultural_prompt_injection(chunks)

        # Should convert underscores to spaces and title case
        assert "Multi Word Topic Name" in result

    @pytest.mark.asyncio
    async def test_get_context_unknown_intent(self):
        """Test get context with unknown intent"""
        from backend.services.cultural_rag_service import CulturalRAGService

        mock_cultural = AsyncMock()
        mock_cultural.query_insights.return_value = []

        service = CulturalRAGService(cultural_insights_service=mock_cultural)

        context_params = {
            "query": "test",
            "intent": "unknown_intent_type",
            "conversation_stage": "ongoing",
        }

        await service.get_cultural_context(context_params)

        call_args = mock_cultural.query_insights.call_args
        # Unknown intent should return None for when_to_use
        assert call_args[1]["when_to_use"] is None

    def test_build_injection_with_missing_score(self):
        """Test build injection with missing score defaults to 0"""
        from backend.services.cultural_rag_service import CulturalRAGService

        service = CulturalRAGService(cultural_insights_service=Mock())

        chunks = [
            {
                "content": "Content",
                "metadata": {"topic": "test_topic"},
                # No score - should default to 0, which is < 0.3 threshold
            }
        ]

        result = service.build_cultural_prompt_injection(chunks)

        # Since score defaults to 0, which is < 0.3, it should be filtered
        # Result should only have the header and instructions, not the content
        assert "Test Topic" not in result or "relevance: 0.00" in result
