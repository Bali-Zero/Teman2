"""
Unit tests for Intent Classifier
Target: 100% coverage
Composer: 5
"""

import sys
from pathlib import Path
import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.classification.intent_classifier import IntentClassifier


@pytest.fixture
def intent_classifier():
    """Create IntentClassifier instance"""
    return IntentClassifier()


class TestIntentClassifier:
    """Tests for Intent Classifier"""

    @pytest.mark.asyncio
    async def test_classify_greeting(self, intent_classifier):
        """Test classifying greeting"""
        result = await intent_classifier.classify_intent("ciao")
        assert result["category"] == "greeting"
        assert result["suggested_ai"] == "fast"
        assert result["skip_rag"] is True

    @pytest.mark.asyncio
    async def test_classify_identity(self, intent_classifier):
        """Test classifying identity query"""
        result = await intent_classifier.classify_intent("chi sono io")
        assert result["category"] == "identity"
        assert result["suggested_ai"] == "fast"

    @pytest.mark.asyncio
    async def test_classify_team_query(self, intent_classifier):
        """Test classifying team query"""
        result = await intent_classifier.classify_intent("chi lavora nel team")
        assert result["category"] == "team_query"
        assert result["suggested_ai"] == "fast"

    @pytest.mark.asyncio
    async def test_classify_session_state_login(self, intent_classifier):
        """Test classifying login intent"""
        result = await intent_classifier.classify_intent("login")
        assert result["category"] == "session_state"
        assert result["suggested_ai"] == "fast"

    @pytest.mark.asyncio
    async def test_classify_general_task_translation(self, intent_classifier):
        """Test classifying translation task"""
        result = await intent_classifier.classify_intent("traduci questo in inglese")
        assert result["category"] == "general_task"
        assert result["skip_rag"] is True

    @pytest.mark.asyncio
    async def test_classify_casual(self, intent_classifier):
        """Test classifying casual question"""
        result = await intent_classifier.classify_intent("come stai")
        assert result["category"] == "casual"
        assert result["skip_rag"] is True

    @pytest.mark.asyncio
    async def test_classify_emotional(self, intent_classifier):
        """Test classifying emotional pattern"""
        result = await intent_classifier.classify_intent("sono triste")
        assert result["category"] == "casual"
        assert result["skip_rag"] is True

    @pytest.mark.asyncio
    async def test_classify_business_simple(self, intent_classifier):
        """Test classifying simple business question"""
        result = await intent_classifier.classify_intent("what is visa")
        assert result["category"] == "business_simple"
        assert result["suggested_ai"] in ["fast", "pro"]

    @pytest.mark.asyncio
    async def test_classify_business_complex(self, intent_classifier):
        """Test classifying complex business question"""
        result = await intent_classifier.classify_intent("how to setup PT PMA company with investment requirements")
        assert result["category"] == "business_complex"
        assert result["suggested_ai"] == "pro"

    @pytest.mark.asyncio
    async def test_classify_business_strategic(self, intent_classifier):
        """Test classifying strategic business question"""
        result = await intent_classifier.classify_intent("what is the best strategy for investment")
        assert result["category"] == "business_strategic"
        assert result["suggested_ai"] == "deep_think"

    @pytest.mark.asyncio
    async def test_classify_devai_code(self, intent_classifier):
        """Test classifying DevAI code query"""
        result = await intent_classifier.classify_intent("how to debug this python code")
        assert result["category"] == "devai_code"
        assert result["suggested_ai"] == "devai"

    @pytest.mark.asyncio
    async def test_classify_unknown_fallback(self, intent_classifier):
        """Test fallback classification"""
        result = await intent_classifier.classify_intent("xyz123")
        assert result["category"] in ["casual", "business_simple"]
        assert "suggested_ai" in result

    @pytest.mark.asyncio
    async def test_classify_error_handling(self, intent_classifier):
        """Test error handling"""
        # Force an error by passing None
        result = await intent_classifier.classify_intent(None)
        assert result["category"] == "unknown"
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_derive_mode_greeting(self, intent_classifier):
        """Test deriving mode for greeting"""
        result = await intent_classifier.classify_intent("ciao")
        assert result["mode"] == "greeting"

    @pytest.mark.asyncio
    async def test_derive_mode_procedure_guide(self, intent_classifier):
        """Test deriving mode for procedure guide"""
        result = await intent_classifier.classify_intent("how to get visa")
        assert result["mode"] == "procedure_guide"

    @pytest.mark.asyncio
    async def test_derive_mode_risk_explainer(self, intent_classifier):
        """Test deriving mode for risk explainer"""
        result = await intent_classifier.classify_intent("what is the risk of illegal visa")
        assert result["mode"] == "risk_explainer"

