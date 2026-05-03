"""
Tests for intent_classifier.py - Pattern-based intent classification.
"""

import pytest

from backend.services.classification.intent_classifier import IntentClassifier


@pytest.fixture
def classifier():
    return IntentClassifier()


class TestGreetingClassification:
    """Tests for greeting intent detection."""

    @pytest.mark.asyncio
    async def test_simple_greetings(self, classifier):
        for greeting in ["ciao", "hello", "hi", "hey", "salve", "buongiorno"]:
            result = await classifier.classify_intent(greeting)
            assert result["category"] == "greeting", f"Failed for '{greeting}'"
            assert result["confidence"] == 1.0
            assert result["suggested_ai"] == "fast"
            assert result["skip_rag"] is True

    @pytest.mark.asyncio
    async def test_greeting_case_insensitive(self, classifier):
        result = await classifier.classify_intent("CIAO")
        assert result["category"] == "greeting"

    @pytest.mark.asyncio
    async def test_greeting_with_whitespace(self, classifier):
        result = await classifier.classify_intent("  ciao  ")
        assert result["category"] == "greeting"


class TestIdentityClassification:
    """Tests for identity intent detection."""

    @pytest.mark.asyncio
    async def test_italian_identity(self, classifier):
        result = await classifier.classify_intent("chi sono io?")
        assert result["category"] == "identity"
        assert result["skip_rag"] is True

    @pytest.mark.asyncio
    async def test_english_identity(self, classifier):
        result = await classifier.classify_intent("who am i?")
        assert result["category"] == "identity"

    @pytest.mark.asyncio
    async def test_identity_has_team_context_flag(self, classifier):
        result = await classifier.classify_intent("mi conosci?")
        assert result["category"] == "identity"
        assert result.get("requires_team_context") is True


class TestTeamQueryClassification:
    """Tests for team query detection."""

    @pytest.mark.asyncio
    async def test_team_members_query(self, classifier):
        result = await classifier.classify_intent("who are the team members?")
        assert result["category"] == "team_query"
        assert result["skip_rag"] is True

    @pytest.mark.asyncio
    async def test_italian_team_query(self, classifier):
        # "chi sono" triggers identity before team, so use a query without it
        result = await classifier.classify_intent("parlami del team di bali zero")
        assert result["category"] == "team_query"


class TestSessionStateClassification:
    """Tests for session state detection."""

    @pytest.mark.asyncio
    async def test_login_intent(self, classifier):
        result = await classifier.classify_intent("login")
        assert result["category"] == "session_state"
        assert result["suggested_ai"] == "fast"

    @pytest.mark.asyncio
    async def test_logout_intent(self, classifier):
        result = await classifier.classify_intent("logout")
        assert result["category"] == "session_state"


class TestBusinessClassification:
    """Tests for business intent detection."""

    @pytest.mark.asyncio
    async def test_visa_question(self, classifier):
        result = await classifier.classify_intent("How do I get a KITAS visa for Indonesia?")
        # Should be classified as business (simple or complex)
        assert result["category"] in ("business_simple", "business_complex", "general_task")

    @pytest.mark.asyncio
    async def test_company_setup_question(self, classifier):
        result = await classifier.classify_intent("How to set up a PT PMA company?")
        assert result["category"] in ("business_simple", "business_complex", "general_task")


class TestCasualClassification:
    """Tests for casual intent detection."""

    @pytest.mark.asyncio
    async def test_how_are_you_italian(self, classifier):
        result = await classifier.classify_intent("come stai?")
        assert result["category"] == "casual"
        assert result["skip_rag"] is True

    @pytest.mark.asyncio
    async def test_how_are_you_english(self, classifier):
        result = await classifier.classify_intent("how are you?")
        assert result["category"] == "casual"


class TestModeDerivation:
    """Tests for mode derivation from categories."""

    @pytest.mark.asyncio
    async def test_greeting_has_mode(self, classifier):
        result = await classifier.classify_intent("ciao")
        assert "mode" in result

    @pytest.mark.asyncio
    async def test_identity_has_mode(self, classifier):
        result = await classifier.classify_intent("chi sono io?")
        assert "mode" in result
