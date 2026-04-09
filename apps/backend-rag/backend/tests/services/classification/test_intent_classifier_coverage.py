"""
Extended tests for IntentClassifier — covering all intent categories
and multilingual pattern matching.

These tests complement the existing classification tests by ensuring
all intent categories and edge cases are properly classified.
"""

import pytest

from backend.services.classification.intent_classifier import (
    BUSINESS_KEYWORDS,
    EMOTIONAL_PATTERNS,
    IDENTITY_KEYWORDS,
    SESSION_PATTERNS,
    SIMPLE_GREETINGS,
    IntentClassifier,
)


@pytest.fixture
def classifier():
    """Create IntentClassifier instance."""
    return IntentClassifier()


# --- Greeting Tests ---


class TestGreetings:
    @pytest.mark.asyncio
    async def test_simple_greeting_ciao(self, classifier):
        result = await classifier.classify_intent("ciao")
        assert result["category"] == "greeting"
        assert result["confidence"] == 1.0
        assert result["skip_rag"] is True

    @pytest.mark.asyncio
    async def test_simple_greeting_hello(self, classifier):
        result = await classifier.classify_intent("hello")
        assert result["category"] == "greeting"
        assert result["skip_rag"] is True

    @pytest.mark.asyncio
    async def test_simple_greeting_halo(self, classifier):
        result = await classifier.classify_intent("halo")
        assert result["category"] == "greeting"
        assert result["skip_rag"] is True

    @pytest.mark.asyncio
    async def test_greeting_case_insensitive(self, classifier):
        result = await classifier.classify_intent("CIAO")
        assert result["category"] == "greeting"


# --- Identity Tests ---


class TestIdentity:
    @pytest.mark.asyncio
    async def test_identity_italian(self, classifier):
        result = await classifier.classify_intent("chi sono io?")
        assert result["category"] == "identity"
        assert result["skip_rag"] is True

    @pytest.mark.asyncio
    async def test_identity_english(self, classifier):
        result = await classifier.classify_intent("who am i")
        assert result["category"] == "identity"
        assert result["skip_rag"] is True

    @pytest.mark.asyncio
    async def test_identity_indonesian(self, classifier):
        result = await classifier.classify_intent("siapa saya?")
        assert result["category"] == "identity"
        assert result["skip_rag"] is True

    @pytest.mark.asyncio
    async def test_identity_recognition(self, classifier):
        result = await classifier.classify_intent("do you know me?")
        assert result["category"] == "identity"


# --- Team Query Tests ---


class TestTeamQuery:
    @pytest.mark.asyncio
    async def test_team_italian(self, classifier):
        result = await classifier.classify_intent("parlami del team")
        assert result["category"] == "team_query"
        assert result["skip_rag"] is True

    @pytest.mark.asyncio
    async def test_team_english(self, classifier):
        result = await classifier.classify_intent("tell me about the team members")
        assert result["category"] == "team_query"

    @pytest.mark.asyncio
    async def test_team_indonesian(self, classifier):
        result = await classifier.classify_intent("siapa anggota tim?")
        assert result["category"] == "team_query"


# --- Session Tests ---


class TestSession:
    @pytest.mark.asyncio
    async def test_login_intent(self, classifier):
        result = await classifier.classify_intent("login")
        assert result["category"] == "session_state"
        # session_state does not set skip_rag; it relies on memory/context routing
        assert result.get("require_memory") is True

    @pytest.mark.asyncio
    async def test_logout_intent(self, classifier):
        result = await classifier.classify_intent("logout")
        assert result["category"] == "session_state"
        assert result.get("require_memory") is True

    @pytest.mark.asyncio
    async def test_login_indonesian(self, classifier):
        result = await classifier.classify_intent("masuk ke sistem")
        assert result["category"] == "session_state"


# --- Casual Tests ---


class TestCasual:
    @pytest.mark.asyncio
    async def test_casual_italian(self, classifier):
        result = await classifier.classify_intent("come stai?")
        assert result["category"] == "casual"
        assert result["skip_rag"] is True

    @pytest.mark.asyncio
    async def test_casual_english(self, classifier):
        result = await classifier.classify_intent("how are you?")
        assert result["category"] == "casual"

    @pytest.mark.asyncio
    async def test_casual_indonesian(self, classifier):
        result = await classifier.classify_intent("apa kabar?")
        assert result["category"] == "casual"

    @pytest.mark.asyncio
    async def test_memory_query(self, classifier):
        result = await classifier.classify_intent("what do you remember about me?")
        assert result["category"] == "casual"
        assert result["skip_rag"] is True


# --- Emotional Tests ---


class TestEmotional:
    @pytest.mark.asyncio
    async def test_emotional_sadness(self, classifier):
        # Emotional patterns are classified as 'casual' in current implementation
        result = await classifier.classify_intent("i'm sad today")
        assert result["category"] == "casual"
        assert result["skip_rag"] is True

    @pytest.mark.asyncio
    async def test_emotional_worry_italian(self, classifier):
        result = await classifier.classify_intent("sono preoccupato per il visto")
        assert result["category"] == "casual"

    @pytest.mark.asyncio
    async def test_emotional_happy_indonesian(self, classifier):
        result = await classifier.classify_intent("aku senang sekali!")
        assert result["category"] == "casual"


# --- Business Intent Tests ---


class TestBusinessIntent:
    @pytest.mark.asyncio
    async def test_visa_query(self, classifier):
        # Business queries are classified as business_simple or business_complex (not 'business')
        result = await classifier.classify_intent("I need a visa for Bali")
        assert result["category"].startswith("business")
        assert result.get("skip_rag") is not True

    @pytest.mark.asyncio
    async def test_kitas_query(self, classifier):
        # "How do I get" triggers complex_indicator → business_complex
        result = await classifier.classify_intent("How do I get a KITAS?")
        assert result["category"] == "business_complex"

    @pytest.mark.asyncio
    async def test_company_setup(self, classifier):
        result = await classifier.classify_intent("I want to open a PT PMA in Bali")
        assert result["category"].startswith("business")

    @pytest.mark.asyncio
    async def test_tax_query(self, classifier):
        result = await classifier.classify_intent("What about PPh 21 withholding?")
        assert result["category"].startswith("business")


# --- Priority Tests ---


class TestClassificationPriority:
    @pytest.mark.asyncio
    async def test_identity_takes_priority_over_casual(self, classifier):
        """Identity patterns should match before casual (both contain 'do you know me')."""
        result = await classifier.classify_intent("do you know me?")
        assert result["category"] == "identity"

    @pytest.mark.asyncio
    async def test_greeting_exact_match_priority(self, classifier):
        """Exact greeting should be classified as greeting, not business."""
        result = await classifier.classify_intent("ciao")
        assert result["category"] == "greeting"


# --- Keyword Constants Tests ---


class TestKeywordConstants:
    def test_simple_greetings_not_empty(self):
        assert len(SIMPLE_GREETINGS) > 0

    def test_identity_keywords_multilingual(self):
        """Identity keywords should cover Italian, English, and Indonesian."""
        all_keywords = " ".join(IDENTITY_KEYWORDS)
        assert "chi sono" in all_keywords  # Italian
        assert "who am i" in all_keywords  # English
        assert "siapa saya" in all_keywords  # Indonesian

    def test_business_keywords_cover_core_services(self):
        """Business keywords should include core service types."""
        assert "visa" in BUSINESS_KEYWORDS
        assert "kitas" in BUSINESS_KEYWORDS
        assert "pma" in BUSINESS_KEYWORDS
        assert "tax" in BUSINESS_KEYWORDS
        assert "kbli" in BUSINESS_KEYWORDS

    def test_session_patterns_cover_login_logout(self):
        assert "login" in SESSION_PATTERNS
        assert "logout" in SESSION_PATTERNS
        assert "masuk" in SESSION_PATTERNS  # Indonesian
        assert "accedi" in SESSION_PATTERNS  # Italian

    def test_emotional_patterns_not_empty(self):
        assert len(EMOTIONAL_PATTERNS) > 5
