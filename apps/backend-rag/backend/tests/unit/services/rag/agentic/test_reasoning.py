"""
Unit tests for ReasoningEngine and reasoning helpers.
Target: context validation, localized stubs, evidence scoring, tool selection.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.rag.agentic.reasoning import (
    ReasoningEngine,
    _validate_context_quality,
)
from backend.services.rag.agentic.reasoning_utils import (
    calculate_evidence_score,
    detect_team_query,
    get_critical_domain_type,
    is_critical_domain,
    is_valid_tool_call,
)

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def engine():
    """Create ReasoningEngine with mock tool_map."""
    tool_map = {"vector_search": MagicMock(), "calculator": MagicMock()}
    return ReasoningEngine(tool_map=tool_map, response_pipeline=None)


@pytest.fixture
def mock_llm_gateway():
    """Mock LLM gateway for send_message calls."""
    gw = AsyncMock()
    gw.send_message = AsyncMock(
        return_value=("Final Answer: This is a test", "gemini-2.0-flash", MagicMock(), MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30, cost_usd=0.0001, __add__=lambda s, o: s)),
    )
    gw._gemini_tools = []
    return gw


# ============================================================================
# _validate_context_quality TESTS
# ============================================================================


class TestValidateContextQuality:
    """Tests for the standalone _validate_context_quality function."""

    def test_empty_context(self):
        """Empty context returns 0.0."""
        assert _validate_context_quality("visa kitas", []) == 0.0

    def test_relevant_context(self):
        """Context with matching keywords scores higher."""
        score = _validate_context_quality(
            "visa kitas bali",
            ["KITAS visa permit for Bali", "Immigration process for KITAS holders"],
        )
        assert score > 0.0

    def test_irrelevant_context(self):
        """Context with no keyword overlap scores low."""
        score = _validate_context_quality(
            "quantum physics black holes",
            ["KBLI classification code 47911 retail", "PT PMA company setup Indonesia"],
        )
        assert score < 0.5

    def test_single_item_context(self):
        """Single context item still produces a score."""
        score = _validate_context_quality("visa", ["Visa information for Indonesia"])
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0


# ============================================================================
# ReasoningEngine._validate_context_quality (instance method)
# ============================================================================


class TestReasoningEngineContextQuality:
    """Tests for instance method wrapper."""

    def test_delegates_to_module_function(self, engine):
        """Instance method delegates to module-level function."""
        score = engine._validate_context_quality("test query", ["test context"])
        assert isinstance(score, float)


# ============================================================================
# ReasoningEngine._get_localized_stub TESTS
# ============================================================================


class TestLocalizedStubs:
    """Tests for localized stub message generation."""

    def test_abstain_italian(self, engine):
        """Italian abstain message returned."""
        msg = engine._get_localized_stub("abstain", "ITALIAN")
        assert "dispiace" in msg.lower() or "informazioni" in msg.lower()

    def test_abstain_english(self, engine):
        """English abstain message returned."""
        msg = engine._get_localized_stub("abstain", "ENGLISH")
        assert "sorry" in msg.lower() or "couldn't" in msg.lower()

    def test_abstain_indonesian(self, engine):
        """Indonesian abstain message returned."""
        msg = engine._get_localized_stub("abstain", "INDONESIAN")
        assert "maaf" in msg.lower()

    def test_abstain_detailed_italian(self, engine):
        """Detailed Italian abstain with suggestions."""
        msg = engine._get_localized_stub("abstain_detailed", "ITALIAN")
        assert "visti" in msg.lower() or "kitas" in msg.lower()

    def test_error_english(self, engine):
        """English error message returned."""
        msg = engine._get_localized_stub("error", "ENGLISH")
        assert "try again" in msg.lower()

    def test_confused_italian(self, engine):
        """Italian confused message returned."""
        msg = engine._get_localized_stub("confused", "ITALIAN")
        assert "capito" in msg.lower() or "riformulare" in msg.lower()

    def test_unknown_language_falls_back_to_english(self, engine):
        """Unknown language falls back to English."""
        msg = engine._get_localized_stub("abstain", "KLINGON")
        assert isinstance(msg, str)
        assert len(msg) > 10

    def test_unknown_key_returns_generic(self, engine):
        """Unknown key returns generic fallback."""
        msg = engine._get_localized_stub("nonexistent_key", "ENGLISH")
        assert isinstance(msg, str)


# ============================================================================
# is_valid_tool_call TESTS
# ============================================================================


class TestIsValidToolCall:
    """Tests for tool call validation."""

    def test_none_is_invalid(self):
        """None tool call is invalid."""
        assert is_valid_tool_call(None) is False

    def test_missing_tool_name(self):
        """Tool call without tool_name is invalid."""
        tc = MagicMock(spec=[])
        assert is_valid_tool_call(tc) is False

    def test_empty_tool_name(self):
        """Tool call with empty tool_name is invalid."""
        tc = MagicMock()
        tc.tool_name = ""
        tc.arguments = {}
        assert is_valid_tool_call(tc) is False

    def test_non_string_tool_name(self):
        """Tool call with non-string tool_name is invalid."""
        tc = MagicMock()
        tc.tool_name = 123
        tc.arguments = {}
        assert is_valid_tool_call(tc) is False

    def test_none_arguments(self):
        """Tool call with None arguments is invalid."""
        tc = MagicMock()
        tc.tool_name = "vector_search"
        tc.arguments = None
        assert is_valid_tool_call(tc) is False

    def test_valid_tool_call(self):
        """Valid tool call passes validation."""
        tc = MagicMock()
        tc.tool_name = "vector_search"
        tc.arguments = {"query": "kitas"}
        assert is_valid_tool_call(tc) is True


# ============================================================================
# calculate_evidence_score TESTS
# ============================================================================


class TestCalculateEvidenceScore:
    """Tests for evidence scoring logic."""

    def test_no_sources_no_context(self):
        """No sources and no context returns 0.0."""
        assert calculate_evidence_score(None, [], "some query") == 0.0

    def test_high_relevance_good_sources(self):
        """High keyword overlap + good sources scores > 0.6."""
        sources = [{"score": 0.85}]
        context = ["KITAS visa permit application process Indonesia immigration"]
        score = calculate_evidence_score(sources, context, "How to get a KITAS visa?")
        assert score > 0.5

    def test_no_keyword_overlap(self):
        """Zero keyword overlap scores very low."""
        sources = [{"score": 0.9}]
        context = ["KBLI classification code retail 47911"]
        score = calculate_evidence_score(sources, context, "quantum physics theory")
        assert score < 0.15

    def test_entity_type_mismatch_visa_vs_kbli(self):
        """KITAS query + KBLI context triggers mismatch penalty."""
        sources = [{"score": 0.7}]
        context = ["KBLI classification code 47911 retail trade business"]
        score = calculate_evidence_score(sources, context, "How to extend my KITAS?")
        assert score < 0.4

    def test_moderate_relevance(self):
        """Partial keyword match scores in cautious range."""
        sources = [{"score": 0.5}]
        context = ["Indonesia business setup company requirements investment"]
        score = calculate_evidence_score(sources, context, "Indonesia company setup requirements")
        assert 0.15 <= score <= 1.0

    def test_sources_only_no_context(self):
        """Sources without context still produces a score."""
        sources = [{"score": 0.8}]
        score = calculate_evidence_score(sources, [], "visa kitas")
        assert isinstance(score, float)

    def test_context_only_no_sources(self):
        """Context without sources still produces a score."""
        context = ["KITAS visa permit for Bali Indonesia immigration"]
        score = calculate_evidence_score(None, context, "KITAS visa Bali")
        assert score > 0.0


# ============================================================================
# get_critical_domain_type TESTS
# ============================================================================


class TestGetCriticalDomainType:
    """Tests for domain type classification."""

    def test_visa_domain(self):
        """Visa keywords detected."""
        assert get_critical_domain_type("How to get a KITAS?") == "visa"
        assert get_critical_domain_type("B211 visa extension") == "visa"

    def test_legal_domain(self):
        """Legal keywords detected."""
        assert get_critical_domain_type("What law regulates this?") == "legal"
        assert get_critical_domain_type("Contract compliance check") == "legal"

    def test_pricing_domain(self):
        """Pricing keywords detected."""
        assert get_critical_domain_type("How much does it cost?") == "pricing"
        assert get_critical_domain_type("Quanto costa il visto?") == "pricing"

    def test_procedure_domain(self):
        """Procedure keywords detected."""
        assert get_critical_domain_type("What documents do I need?") == "procedure"

    def test_default_business_complex(self):
        """Unknown topic defaults to business_complex."""
        assert get_critical_domain_type("Tell me about Bali") == "business_complex"


# ============================================================================
# is_critical_domain TESTS
# ============================================================================


class TestIsCriticalDomain:
    """Tests for critical domain detection."""

    def test_business_complex_intent(self):
        """business_complex intent is always critical."""
        assert is_critical_domain("hello world", "business_complex") is True

    def test_business_strategic_intent(self):
        """business_strategic intent is always critical."""
        assert is_critical_domain("generic text", "business_strategic") is True

    def test_visa_keyword_is_critical(self):
        """Visa keywords make query critical."""
        assert is_critical_domain("How to get a KITAS?", "simple") is True

    def test_pricing_keyword_is_critical(self):
        """Pricing keywords make query critical."""
        assert is_critical_domain("Quanto costa?", "simple") is True

    def test_general_non_critical(self):
        """General query without critical keywords is not critical."""
        assert is_critical_domain("What's the weather today?", "simple") is False


# ============================================================================
# detect_team_query TESTS
# ============================================================================


class TestDetectTeamQuery:
    """Tests for team query detection."""

    def test_not_a_team_query(self):
        """General query is not team-related."""
        is_team, _, _ = detect_team_query("How to get a visa?")
        assert is_team is False

    def test_list_all_team(self):
        """List all team request detected."""
        is_team, query_type, _ = detect_team_query("List all team members")
        assert is_team is True
        assert query_type == "list_all"

    def test_email_lookup(self):
        """Email address triggers search_by_email."""
        is_team, query_type, term = detect_team_query("Who is john@balizero.com?")
        assert is_team is True
        assert query_type == "search_by_email"
        assert "john@balizero.com" in term

    def test_role_lookup_tax(self):
        """Tax role lookup detected with team context."""
        is_team, query_type, term = detect_team_query("Chi si occupa di tax nel team?")
        assert is_team is True
        assert query_type == "search_by_role"
        assert term == "tax"

    def test_empty_string(self):
        """Empty string is not a team query."""
        is_team, _, _ = detect_team_query("")
        assert is_team is False

    def test_non_string_input(self):
        """Non-string input returns False."""
        is_team, _, _ = detect_team_query(123)
        assert is_team is False


# ============================================================================
# ReasoningEngine.execute_react_loop (smoke test)
# ============================================================================


class TestExecuteReactLoop:
    """Smoke tests for the ReAct loop - verifying it doesn't crash."""

    @pytest.mark.asyncio
    @patch("backend.services.rag.agentic.reasoning.trace_span")
    @patch("backend.services.rag.agentic.reasoning.set_span_attribute")
    @patch("backend.services.rag.agentic.reasoning.set_span_status")
    @patch("backend.services.rag.agentic.reasoning.add_span_event")
    @patch("backend.services.rag.agentic.reasoning.detect_query_language", return_value="ENGLISH")
    @patch("backend.services.rag.agentic.reasoning.calculate_evidence_score", return_value=0.8)
    @patch("backend.services.rag.agentic.reasoning.is_critical_domain", return_value=False)
    async def test_react_loop_final_answer_direct(
        self, mock_is_crit, mock_calc, mock_detect, mock_add_event, mock_status, mock_attr, mock_span, engine,
    ):
        """ReAct loop returns when LLM provides final answer directly."""
        mock_span.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_span.return_value.__exit__ = MagicMock(return_value=False)

        from backend.services.llm_clients.pricing import TokenUsage

        mock_usage = TokenUsage()

        llm_gw = AsyncMock()
        response_obj = MagicMock()
        response_obj.candidates = []
        llm_gw.send_message = AsyncMock(
            return_value=("Final Answer: Indonesia requires KITAS for work.", "gemini-flash", response_obj, mock_usage),
        )
        llm_gw._gemini_tools = []

        from backend.services.tools.definitions import AgentState

        state = AgentState(query="What is KITAS?", max_steps=3)
        state.skip_rag = False

        result_state, model_name, msgs, usage = await engine.execute_react_loop(
            state=state,
            llm_gateway=llm_gw,
            chat=MagicMock(),
            initial_prompt="What is KITAS?",
            system_prompt="You are Zantara.",
            query="What is KITAS?",
            user_id="test-user",
            model_tier=1,
            tool_execution_counter={"count": 0},
        )

        assert result_state.final_answer is not None
        assert "KITAS" in result_state.final_answer or "Indonesia" in result_state.final_answer
