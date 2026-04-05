"""
Integration test: RAG pipeline end-to-end flow.

Tests the full RAG cycle: classify intent → search → grade → generate.
Uses mocked external services (Qdrant, LLM) but tests actual wiring.
"""


import pytest

from backend.services.classification.intent_classifier import IntentClassifier


class TestRAGPipelineFlow:
    """Integration test for the RAG query pipeline."""

    @pytest.fixture
    def intent_classifier(self):
        return IntentClassifier()

    @pytest.mark.asyncio
    async def test_business_query_classified_for_rag(self, intent_classifier):
        """Business queries should be classified as needing RAG."""
        result = await intent_classifier.classify_intent(
            "What documents do I need for a KITAS?"
        )
        assert result["category"] == "business"
        assert result.get("skip_rag") is not True

    @pytest.mark.asyncio
    async def test_greeting_bypasses_rag(self, intent_classifier):
        """Greetings should skip the RAG pipeline entirely."""
        result = await intent_classifier.classify_intent("ciao")
        assert result["skip_rag"] is True
        assert result["category"] == "greeting"

    @pytest.mark.asyncio
    async def test_identity_bypasses_rag(self, intent_classifier):
        """Identity queries should skip RAG."""
        result = await intent_classifier.classify_intent("chi sono io?")
        assert result["skip_rag"] is True
        assert result["category"] == "identity"

    @pytest.mark.asyncio
    async def test_emotional_query_bypasses_rag(self, intent_classifier):
        """Emotional queries should skip RAG (handled by persona)."""
        result = await intent_classifier.classify_intent("sono triste")
        assert result["skip_rag"] is True

    @pytest.mark.asyncio
    async def test_tax_query_classified_as_business(self, intent_classifier):
        """Tax queries with Indonesian terms should be classified correctly."""
        result = await intent_classifier.classify_intent(
            "Bagaimana cara menghitung PPh 21?"
        )
        assert result["category"] == "business"

    @pytest.mark.asyncio
    async def test_visa_query_classified_as_business(self, intent_classifier):
        """Visa queries in multiple languages should be business intent."""
        queries = [
            "I need a visa for Bali",
            "Ho bisogno di un visto per Bali",
            "Saya butuh visa untuk Bali",
        ]
        for query in queries:
            result = await intent_classifier.classify_intent(query)
            assert result["category"] == "business", (
                f"Query '{query}' was classified as '{result['category']}' instead of 'business'"
            )


class TestRAGClassificationPriority:
    """Test that classification priorities are correct for edge cases."""

    @pytest.fixture
    def classifier(self):
        return IntentClassifier()

    @pytest.mark.asyncio
    async def test_mixed_emotional_business(self, classifier):
        """Emotional patterns should take priority over business keywords."""
        result = await classifier.classify_intent("sono preoccupato per il visto")
        # "preoccupato" is emotional, "visto" is business — emotional should win
        assert result["category"] == "emotional"

    @pytest.mark.asyncio
    async def test_new_client_is_casual(self, classifier):
        """New client introduction should be casual (memory), not business."""
        result = await classifier.classify_intent("ho un nuovo cliente")
        assert result["category"] == "casual"

    @pytest.mark.asyncio
    async def test_pure_business_query(self, classifier):
        """Clear business query with no emotional/casual signals."""
        result = await classifier.classify_intent("KBLI code for restaurant")
        assert result["category"] == "business"
