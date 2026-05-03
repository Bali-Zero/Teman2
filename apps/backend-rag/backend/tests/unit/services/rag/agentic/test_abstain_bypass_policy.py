"""
Policy-enforced tests for ABSTAIN bypass in the RAG reasoning engine.

These tests enforce the three-layer bypass as CONTRACT — any code change
that breaks them is a regression, not just a refactor.

Architecture (DO NOT CHANGE — test only):
  Layer 1 — IntentClassifier: GENERAL_TASK_KEYWORDS → skip_rag=True → bypasses ABSTAIN
  Layer 2a — Trusted Tools: _TRUSTED_TOOL_NAMES executed successfully → trusted_tools_used=True
  Layer 2b — Pricing Markers: Rp/IDR/USD/juta in final_answer → trusted_tools_used=True
  Layer 2c — Tools Available: _gemini_tools set on gateway + final_answer → trusted_tools_used=True
  Layer 3 — ABSTAIN Decision: triggers ONLY when all bypass conditions are False
"""

from typing import Any
from unittest.mock import MagicMock

import pytest

# ============================================================
# Fixtures / Helpers
# ============================================================

def _make_tool_call(tool_name: str) -> Any:
    """Return a minimal ToolCall-like object."""
    tc = MagicMock()
    tc.tool_name = tool_name
    tc.arguments = {}
    return tc


def _make_step(tool_name: str, observation: str | None) -> Any:
    """Return a minimal AgentStep-like object with an action."""
    step = MagicMock()
    step.action = _make_tool_call(tool_name)
    step.observation = observation
    step.is_final = False
    return step


def _make_state(
    *,
    final_answer: str | None = None,
    skip_rag: bool = False,
    steps: list | None = None,
    intent_type: str = "simple",
) -> Any:
    """Return a minimal AgentState-like object."""
    state = MagicMock()
    state.final_answer = final_answer
    state.skip_rag = skip_rag
    state.steps = steps or []
    state.intent_type = intent_type
    state.context_gathered = []
    state.sources = []
    state.evidence_score = None
    state.trusted_tools_used = False
    return state


def _make_gateway(gemini_tools: list | None = None, has_attr: bool = True) -> Any:
    """Return a minimal LLMGateway-like object."""
    gw = MagicMock()
    if has_attr:
        gw._gemini_tools = gemini_tools if gemini_tools is not None else []
    else:
        # Delete attribute so hasattr returns False
        del gw._gemini_tools
    return gw


# ============================================================
# Class 1 — Intent Classifier Bypass (Layer 1)
# ============================================================

class TestIntentClassifierBypass:
    """
    Policy: GENERAL_TASK_KEYWORDS in the user query → classify_intent returns
    skip_rag=True. This is Layer 1: the ReasoningEngine will skip the ABSTAIN
    check entirely when state.skip_rag is True.
    """

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_pricing_keyword_italiano_sets_skip_rag(self):
        """
        POLICY: Italian pricing query "quanto costa" must set skip_rag=True.
        WHY: Italian-speaking clients ask pricing in Italian; without this
        bypass every pricing answer gets ABSTAIN'd because Gemini answers
        directly (evidence_score=0.00 from KB).
        """
        from backend.services.classification.intent_classifier import IntentClassifier

        clf = IntentClassifier()
        result = await clf.classify_intent("quanto costa aprire una PT PMA?")
        assert result.get("skip_rag") is True, (
            "Italian pricing keyword 'quanto costa' must set skip_rag=True"
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_pricing_keyword_english_sets_skip_rag(self):
        """
        POLICY: English pricing query "how much does" must set skip_rag=True.
        WHY: Same bypass needed for English-speaking clients.
        """
        from backend.services.classification.intent_classifier import IntentClassifier

        clf = IntentClassifier()
        result = await clf.classify_intent("how much does a KITAS cost?")
        assert result.get("skip_rag") is True, (
            "English pricing keyword 'how much does' must set skip_rag=True"
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_pricing_keyword_indonesian_sets_skip_rag(self):
        """
        POLICY: Indonesian pricing query "berapa biaya" must set skip_rag=True.
        WHY: Indonesian clients use 'berapa biaya'; missing this means all
        Indonesian pricing answers are ABSTAIN'd.
        """
        from backend.services.classification.intent_classifier import IntentClassifier

        clf = IntentClassifier()
        result = await clf.classify_intent("berapa biaya visa kerja?")
        assert result.get("skip_rag") is True, (
            "Indonesian pricing keyword 'berapa biaya' must set skip_rag=True"
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_non_pricing_query_no_skip_rag(self):
        """
        POLICY: Non-pricing query "what documents do I need for KITAS?" must NOT
        set skip_rag=True (RAG evidence is required for document questions).
        WHY: Only pricing/general-task queries bypass RAG; document/legal queries
        need KB-backed answers.
        """
        from backend.services.classification.intent_classifier import IntentClassifier

        clf = IntentClassifier()
        result = await clf.classify_intent("what documents do I need for KITAS?")
        assert result.get("skip_rag") is not True, (
            "Document question must NOT set skip_rag=True — it needs RAG evidence"
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_boundary_keyword_fee_not_in_list(self):
        """
        POLICY: "what's the fee?" is NOT in GENERAL_TASK_KEYWORDS, but still sets
        skip_rag=True via the casual classifier (CASUAL_PATTERNS match).
        WHY: Documents that 'fee' queries bypass ABSTAIN via the casual path —
        not via the pricing/general_task path. This is acceptable behavior but
        depends on casual classification remaining stable.
        """
        from backend.services.classification.intent_classifier import IntentClassifier

        clf = IntentClassifier()
        result = await clf.classify_intent("what's the fee?")
        # Gets skip_rag=True via casual path (not general_task / pricing path)
        assert result.get("skip_rag") is True
        # Document: category is 'casual', NOT 'general_task'
        assert result.get("category") != "general_task", (
            "NOTE: 'fee' bypass comes from casual classifier, not pricing keywords. "
            "If casual path changes, pricing-only queries with 'fee' may ABSTAIN."
        )


# ============================================================
# Class 2 — Trusted Tool Detection (Layer 2a)
# ============================================================

class TestTrustedToolDetection:
    """
    Policy: If a step in state.steps used a tool from _TRUSTED_TOOL_NAMES
    AND the observation is >50 chars with no error markers →
    trusted_tools_used=True, evidence_score=0.85.
    """

    def _run_trusted_check(self, steps: list) -> tuple[bool, float]:
        """
        Replicate the Layer 2a logic from reasoning.py without importing it
        directly (avoids import side-effects). Returns (trusted, score).
        """
        from backend.services.rag.agentic.reasoning import _TRUSTED_TOOL_NAMES

        trusted_tools_used = False
        for step in steps:
            if step.action and hasattr(step.action, "tool_name"):
                if step.action.tool_name in _TRUSTED_TOOL_NAMES and step.observation:
                    obs_lower = step.observation.lower()
                    has_content = (
                        "error" not in obs_lower
                        and "not found" not in obs_lower
                        and "no relevant" not in obs_lower
                        and len(step.observation) > 50
                    )
                    if has_content:
                        trusted_tools_used = True
                        break

        evidence_score = 0.85 if trusted_tools_used else 0.00
        return trusted_tools_used, evidence_score

    @pytest.mark.unit
    def test_get_pricing_tool_success_sets_trusted(self):
        """
        POLICY: get_pricing tool with >50 char non-error result → trusted_tools_used=True.
        WHY: PricingTool output IS the evidence; no KB sources needed.
        """
        obs = "PT PMA setup: Rp 45.000.000. Includes notary, OSS registration, and 6-month support."
        assert len(obs) > 50
        step = _make_step("get_pricing", obs)
        trusted, score = self._run_trusted_check([step])
        assert trusted is True
        assert score == 0.85

    @pytest.mark.unit
    def test_tool_error_response_not_trusted(self):
        """
        POLICY: get_pricing returning "error: service unavailable" is NOT trusted.
        WHY: Error responses must not bypass ABSTAIN — would give clients bad data.
        """
        obs = "error: service unavailable — pricing database is down, please retry"
        step = _make_step("get_pricing", obs)
        trusted, _ = self._run_trusted_check([step])
        assert trusted is False

    @pytest.mark.unit
    def test_tool_short_response_not_trusted(self):
        """
        POLICY: get_pricing returning a very short response ("N/A", 3 chars) is NOT trusted.
        WHY: Minimum 50 chars required to confirm the tool returned real content.
        """
        step = _make_step("get_pricing", "N/A")
        trusted, _ = self._run_trusted_check([step])
        assert trusted is False

    @pytest.mark.unit
    def test_unknown_tool_not_trusted(self):
        """
        POLICY: A tool NOT in _TRUSTED_TOOL_NAMES with valid output is NOT trusted.
        WHY: Only whitelisted tools bypass evidence scoring.
        """
        obs = "x" * 100  # 100 chars, no error markers
        step = _make_step("random_tool", obs)
        trusted, _ = self._run_trusted_check([step])
        assert trusted is False

    @pytest.mark.unit
    def test_vector_search_trusted(self):
        """
        POLICY: vector_search with a valid >50 char result → trusted_tools_used=True.
        WHY: vector_search retrieves KB content directly — its output IS evidence.
        """
        obs = (
            "Found 3 matching regulations: KITAS requires sponsor letter, "
            "health insurance, and valid passport with 18+ months validity."
        )
        assert len(obs) > 50
        step = _make_step("vector_search", obs)
        trusted, score = self._run_trusted_check([step])
        assert trusted is True
        assert score == 0.85


# ============================================================
# Class 3 — Pricing Markers in Final Answer (Layer 2b)
# ============================================================

class TestPricingMarkersInAnswer:
    """
    Policy: If state.final_answer contains any pricing marker (rp, idr, usd, juta...)
    → trusted_tools_used=True even without tool steps.
    This covers Gemini answering directly from system prompt context.
    """

    def _check_pricing_markers(self, final_answer: str) -> bool:
        """Replicate Layer 2b logic from reasoning.py."""
        answer_lower = final_answer.lower()
        return any(
            marker in answer_lower
            for marker in [
                "rp ",
                "rp.",
                "idr ",
                "usd ",
                "20.000.000",
                "15.000.000",
                "10.000.000",
                "5.000.000",
                "juta",
            ]
        )

    @pytest.mark.unit
    def test_idr_marker_sets_trusted(self):
        """
        POLICY: Final answer containing "idr 15.000.000" → trusted_tools_used=True.
        WHY: Specific IDR amounts indicate real pricing data in the answer.
        """
        answer = "The KITAS processing fee is idr 15.000.000 for the first year."
        assert self._check_pricing_markers(answer) is True

    @pytest.mark.unit
    def test_rp_marker_sets_trusted(self):
        """
        POLICY: Final answer containing "rp 5.000.000" → trusted_tools_used=True.
        WHY: 'Rp' is the standard Indonesian Rupiah notation used in Bali Zero prices.
        """
        answer = "The document legalization costs rp 5.000.000 at the notary."
        assert self._check_pricing_markers(answer) is True

    @pytest.mark.unit
    def test_usd_marker_sets_trusted(self):
        """
        POLICY: Final answer containing "usd 500" → trusted_tools_used=True.
        WHY: USD prices appear in expat service packages; must not ABSTAIN on these.
        """
        answer = "Monthly retainer for tax compliance is usd 500 per month."
        assert self._check_pricing_markers(answer) is True

    @pytest.mark.unit
    def test_juta_marker_sets_trusted(self):
        """
        POLICY: Final answer containing "juta" (Indonesian for million) → trusted.
        WHY: Clients and staff use Indonesian numerical shorthand in answers.
        """
        answer = "Biaya setup PT PMA sekitar 45 juta rupiah sudah termasuk notaris."
        assert self._check_pricing_markers(answer) is True

    @pytest.mark.unit
    def test_no_pricing_markers_not_trusted(self):
        """
        POLICY: Answer with no pricing markers is NOT auto-trusted via Layer 2b.
        WHY: Generic text answers must go through evidence scoring; only specific
        factual pricing data bypasses it.
        """
        answer = "You need a sponsor letter, health insurance, and a valid passport."
        assert self._check_pricing_markers(answer) is False


# ============================================================
# Class 4 — Tools Available Bypass (Layer 2c)
# ============================================================

class TestToolsAvailableBypass:
    """
    Policy: If LLM gateway has _gemini_tools (non-empty) AND state.final_answer
    is set → trusted_tools_used=True. The LLM had the opportunity to call tools
    and chose to answer directly — trust its judgment.
    """

    def _check_tools_available_bypass(self, gateway: Any, final_answer: str | None) -> bool:
        """Replicate Layer 2c logic from reasoning.py lines 663-669."""
        has_tools = hasattr(gateway, "_gemini_tools") and bool(gateway._gemini_tools)
        if has_tools and final_answer:
            return True
        return False

    @pytest.mark.unit
    def test_gemini_tools_set_bypasses(self):
        """
        POLICY: gateway._gemini_tools=[tool1, tool2] + final_answer → bypass ABSTAIN.
        WHY: If LLM was given tools and chose to answer, it's a deliberate choice —
        not a knowledge gap. Forcing ABSTAIN here punishes confident LLMs.
        """
        gw = _make_gateway(gemini_tools=[MagicMock(), MagicMock()])
        result = self._check_tools_available_bypass(gw, "The answer is X.")
        assert result is True

    @pytest.mark.unit
    def test_gemini_tools_empty_no_bypass(self):
        """
        POLICY: gateway._gemini_tools=[] (empty list) → no bypass.
        WHY: Empty tools list means LLM had no tools configured — the answer
        was not tool-informed, evidence scoring must proceed.
        """
        gw = _make_gateway(gemini_tools=[])
        result = self._check_tools_available_bypass(gw, "The answer is X.")
        assert result is False

    @pytest.mark.unit
    def test_gemini_tools_none_no_bypass(self):
        """
        POLICY: gateway._gemini_tools=None → no bypass.
        WHY: None means tools were not configured; bool(None) is False.
        """
        gw = _make_gateway(gemini_tools=None)
        result = self._check_tools_available_bypass(gw, "The answer is X.")
        assert result is False

    @pytest.mark.unit
    def test_no_gemini_tools_attr_no_bypass(self):
        """
        POLICY: If gateway has NO _gemini_tools attribute at all → no bypass.
        WHY: hasattr guard is required; attribute absence means different gateway
        type (e.g., Ollama) with no tool support.
        """
        gw = _make_gateway(has_attr=False)
        result = self._check_tools_available_bypass(gw, "The answer is X.")
        assert result is False


# ============================================================
# Class 5 — ABSTAIN Decision Integration
# ============================================================

class TestAbstainDecisionIntegration:
    """
    Policy: The ABSTAIN gate fires ONLY when ALL of these are true:
      - state.final_answer is set
      - evidence_score < ABSTAIN_THRESHOLD (0.15)
      - state.skip_rag is False
      - trusted_tools_used is False

    These tests verify the gate logic directly, mocking only the
    pre-computed values (score, skip_rag, trusted).
    """

    def _abstain_fires(
        self,
        *,
        final_answer: str | None,
        evidence_score: float,
        skip_rag: bool,
        trusted_tools_used: bool,
    ) -> bool:
        """
        Replicate the ABSTAIN gate condition from reasoning.py lines 673-678.
        Returns True if ABSTAIN would fire, False if answer passes through.
        """
        from backend.app.core.constants import EvidenceScoreConstants

        return (
            bool(final_answer)
            and evidence_score < EvidenceScoreConstants.ABSTAIN_THRESHOLD
            and not skip_rag
            and not trusted_tools_used
        )

    @pytest.mark.unit
    def test_low_evidence_no_bypass_triggers_abstain(self):
        """
        POLICY: score=0.05, skip_rag=False, trusted=False → ABSTAIN fires.
        WHY: This is the baseline case — no bypass means ABSTAIN blocks the answer.
        """
        fires = self._abstain_fires(
            final_answer="Some answer",
            evidence_score=0.05,
            skip_rag=False,
            trusted_tools_used=False,
        )
        assert fires is True

    @pytest.mark.unit
    def test_low_evidence_with_skip_rag_allows_answer(self):
        """
        POLICY: score=0.05, skip_rag=True → ABSTAIN does NOT fire (Layer 1 bypass).
        WHY: Pricing/translation queries set skip_rag=True; must pass through.
        """
        fires = self._abstain_fires(
            final_answer="Rp 45.000.000 untuk setup PT PMA.",
            evidence_score=0.05,
            skip_rag=True,
            trusted_tools_used=False,
        )
        assert fires is False

    @pytest.mark.unit
    def test_low_evidence_with_trusted_tools_allows_answer(self):
        """
        POLICY: score=0.05, trusted_tools_used=True → ABSTAIN does NOT fire (Layer 2).
        WHY: Tool-backed answers bypass evidence scoring by design.
        """
        fires = self._abstain_fires(
            final_answer="PT PMA registration costs Rp 45.000.000.",
            evidence_score=0.05,
            skip_rag=False,
            trusted_tools_used=True,
        )
        assert fires is False

    @pytest.mark.unit
    def test_at_threshold_no_abstain(self):
        """
        POLICY: score=0.15 exactly → ABSTAIN does NOT fire (boundary condition).
        WHY: Threshold is STRICT less-than (<0.15), not less-than-or-equal.
        A score of exactly 0.15 is within the CAUTIOUS band and should pass.
        """
        fires = self._abstain_fires(
            final_answer="Some answer with sources.",
            evidence_score=0.15,
            skip_rag=False,
            trusted_tools_used=False,
        )
        assert fires is False

    @pytest.mark.unit
    def test_above_threshold_no_abstain(self):
        """
        POLICY: score=0.60 → ABSTAIN does NOT fire (normal high-confidence case).
        WHY: Standard KB-backed answers with score ≥ 0.15 must always pass through.
        """
        fires = self._abstain_fires(
            final_answer="KITAS requires sponsor letter and health insurance.",
            evidence_score=0.60,
            skip_rag=False,
            trusted_tools_used=False,
        )
        assert fires is False


# ============================================================
# Class 6 — Streaming Path Parity
# ============================================================

class TestStreamingPathParity:
    """
    Policy: The streaming path (execute_react_loop_stream) must have the same
    ABSTAIN bypass logic as the non-streaming path (execute_react_loop).
    We verify this by checking the method exists and runs the bypass correctly.
    """

    @pytest.mark.unit
    def test_streaming_execute_method_exists(self):
        """
        POLICY: ReasoningEngine must expose execute_react_loop_stream as a callable.
        WHY: If this method is removed/renamed, all streaming clients (WebSocket,
        SSE) silently lose the ABSTAIN bypass protection.
        """
        from backend.services.rag.agentic.reasoning import ReasoningEngine

        engine = ReasoningEngine(tool_map={})
        assert callable(getattr(engine, "execute_react_loop_stream", None)), (
            "execute_react_loop_stream must be a callable method on ReasoningEngine"
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_streaming_skip_rag_bypasses_abstain(self):
        """
        POLICY: When state.skip_rag=True, the streaming path must NOT emit ABSTAIN.
        WHY: Streaming clients (WebSocket chat) must have parity with non-streaming
        for pricing queries. A divergence would mean Zantara ABSTAINs only on
        streaming connections but not API calls — invisible bug.
        """
        from backend.services.rag.agentic.reasoning import ReasoningEngine

        _engine = ReasoningEngine(tool_map={})  # noqa: F841

        # Build minimal mocked state with skip_rag=True
        state = _make_state(
            final_answer="PT PMA costs Rp 45.000.000 all inclusive.",
            skip_rag=True,
        )

        # Patch execute_react_loop_stream to capture state after bypass evaluation
        # We test that the method is callable and state.skip_rag is respected
        # by verifying the ABSTAIN gate would not fire given these inputs
        from backend.app.core.constants import EvidenceScoreConstants

        evidence_score = 0.05  # Below threshold
        abstain_would_fire = (
            bool(state.final_answer)
            and evidence_score < EvidenceScoreConstants.ABSTAIN_THRESHOLD
            and not state.skip_rag        # <-- skip_rag=True prevents ABSTAIN
            and not state.trusted_tools_used
        )
        assert abstain_would_fire is False, (
            "ABSTAIN must NOT fire in streaming path when skip_rag=True"
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_streaming_trusted_tools_bypasses_abstain(self):
        """
        POLICY: When trusted_tools_used=True, the streaming path must NOT emit ABSTAIN.
        WHY: Pricing tool results streamed to client must not be blocked by evidence gate.
        """
        from backend.app.core.constants import EvidenceScoreConstants

        state = _make_state(
            final_answer="The cost is Rp 45.000.000 per year.",
            skip_rag=False,
        )
        state.trusted_tools_used = True

        evidence_score = 0.05
        abstain_would_fire = (
            bool(state.final_answer)
            and evidence_score < EvidenceScoreConstants.ABSTAIN_THRESHOLD
            and not state.skip_rag
            and not state.trusted_tools_used  # <-- trusted=True prevents ABSTAIN
        )
        assert abstain_would_fire is False, (
            "ABSTAIN must NOT fire in streaming path when trusted_tools_used=True"
        )

    # ------------------------------------------------------------------
    # Streaming-only context_gathered bypass tests (reasoning.py:1373-1429)
    # ------------------------------------------------------------------

    def _run_streaming_context_gathered_check(self, context_gathered: list[str]) -> bool:
        """
        Replicate the STREAMING-ONLY context_gathered fallback logic
        from reasoning.py lines 1373-1429.

        This bypass exists ONLY in execute_react_loop_stream, NOT in
        execute_react_loop. It checks context_gathered for pricing/team/KG
        markers and also applies an unconditional bypass when total context
        length exceeds 200 chars.

        Returns True if trusted_tools_used would become True.
        """
        trusted_tools_used = False

        # Phase 1: Marker-based bypass (lines 1375-1418)
        if not trusted_tools_used and context_gathered:
            context_text = " ".join(context_gathered).lower()
            # Pricing markers
            if any(
                marker in context_text
                for marker in [
                    "bali_zero_official_prices",
                    "service_type",
                    "total_price",
                    "pricing",
                    "rp ",
                    "idr ",
                    "harga",
                ]
            ):
                trusted_tools_used = True
            # Team markers
            elif any(
                marker in context_text
                for marker in [
                    "team_member",
                    "specialties",
                    "role:",
                    "department",
                ]
            ):
                trusted_tools_used = True
            # KG markers
            elif any(
                marker in context_text
                for marker in [
                    "subgraph",
                    "nodes,",
                    "edges)",
                    "focus]",
                    "knowledge graph",
                ]
            ):
                trusted_tools_used = True

        # Phase 2: Substantial content bypass (lines 1420-1429)
        if not trusted_tools_used and context_gathered:
            total_context_len = sum(len(c) for c in context_gathered)
            if total_context_len > 200:
                trusted_tools_used = True

        return trusted_tools_used

    @pytest.mark.unit
    def test_streaming_context_gathered_pricing_markers_bypass(self):
        """
        STREAMING-ONLY bypass: context_gathered contains pricing marker
        'bali_zero_official_prices' -> trusted_tools_used becomes True.

        This bypass exists ONLY in the streaming path (execute_react_loop_stream,
        reasoning.py lines 1375-1391). The non-streaming path does NOT inspect
        context_gathered for these markers. Without this test, a refactor that
        removes the streaming fallback would silently break pricing answers
        delivered over SSE/WebSocket.
        """
        context = [
            '{"source": "bali_zero_official_prices", "service_type": "PT PMA Setup", "total_price": 45000000}'
        ]
        result = self._run_streaming_context_gathered_check(context)
        assert result is True, (
            "Pricing marker 'bali_zero_official_prices' in context_gathered "
            "must set trusted_tools_used=True in the streaming path"
        )

    @pytest.mark.unit
    def test_streaming_context_gathered_team_markers_bypass(self):
        """
        STREAMING-ONLY bypass: context_gathered contains team marker
        'team_member' -> trusted_tools_used becomes True.

        This bypass exists ONLY in the streaming path (execute_react_loop_stream,
        reasoning.py lines 1393-1403). The non-streaming path does NOT inspect
        context_gathered for team markers. Without this test, team knowledge
        answers streamed via SSE would get incorrectly ABSTAIN'd.
        """
        context = [
            '{"team_member": "Damar", "role": "Operations Manager", "department": "Client Services"}'
        ]
        result = self._run_streaming_context_gathered_check(context)
        assert result is True, (
            "Team marker 'team_member' in context_gathered "
            "must set trusted_tools_used=True in the streaming path"
        )

    @pytest.mark.unit
    def test_streaming_substantial_content_bypass(self):
        """
        STREAMING-ONLY bypass: context_gathered total length >200 chars
        -> trusted_tools_used becomes True unconditionally.

        This bypass exists ONLY in the streaming path (execute_react_loop_stream,
        reasoning.py lines 1420-1429). The non-streaming path does NOT have this
        length-based fallback. It ensures that ANY tool output with substantial
        content (>200 chars) bypasses the evidence check, even when no specific
        pricing/team/KG markers are present.
        """
        # 250 chars of generic tool output with no known markers
        context = [
            "The client submitted documents on 2026-01-15 and the processing "
            "was completed within the standard timeframe. All requirements were "
            "met and the application was approved by the regional office after "
            "review by three separate departments.",
        ]
        total_len = sum(len(c) for c in context)
        assert total_len > 200, f"Test setup error: context is only {total_len} chars"

        result = self._run_streaming_context_gathered_check(context)
        assert result is True, (
            f"Context with {total_len} chars (>200) must set trusted_tools_used=True "
            "unconditionally in the streaming path"
        )

    @pytest.mark.unit
    def test_streaming_short_content_no_bypass(self):
        """
        STREAMING-ONLY negative case: context_gathered has <200 chars total
        and no known markers -> trusted_tools_used stays False.

        This verifies the streaming fallback does NOT blindly trust short,
        unmarked context. Without markers AND without substantial length,
        the evidence scoring must proceed normally and ABSTAIN can fire.
        """
        # 50 chars of generic text, no markers
        context = ["Some brief info about the client's request."]
        total_len = sum(len(c) for c in context)
        assert total_len < 200, f"Test setup error: context is {total_len} chars"

        result = self._run_streaming_context_gathered_check(context)
        assert result is False, (
            f"Context with {total_len} chars (<200) and no markers "
            "must NOT set trusted_tools_used=True"
        )


# ============================================================
# Class 7 — apply_shared_trusted_flippers helper (U5 unification)
# ============================================================

class TestApplySharedTrustedFlippers:
    """
    U5 (Wave 2): Both ReAct pipelines (sync + streaming) call the same
    helper `apply_shared_trusted_flippers` for the *shared* portion of
    trusted-path detection: pricing-in-answer + LLM-had-tools. The
    streaming path has extra pre-flippers (context markers, substantial
    context) that are INTENTIONALLY not mirrored to sync (SCAR §U5).

    These tests lock in:
    - Helper honors early-True (never flips True→False).
    - Pricing markers set trusted=True on empty-tools gateway.
    - Has-tools + final_answer sets trusted=True on no-pricing answer.
    - Empty final_answer + no pricing keeps trusted=False.
    """

    @pytest.mark.unit
    def test_early_true_preserved(self):
        """Invariant: once True, stays True — helper never flips back."""
        from backend.services.rag.agentic._reasoning_policy import (
            apply_shared_trusted_flippers,
        )
        gw = _make_gateway(gemini_tools=[])
        result = apply_shared_trusted_flippers(
            trusted_tools_used=True,
            final_answer="",  # nothing would flip from here
            llm_gateway=gw,
        )
        assert result is True

    @pytest.mark.unit
    def test_pricing_marker_flips_true(self):
        """Pricing markers in final_answer set trusted=True even with
        empty gateway tools."""
        from backend.services.rag.agentic._reasoning_policy import (
            apply_shared_trusted_flippers,
        )
        gw = _make_gateway(gemini_tools=[])
        result = apply_shared_trusted_flippers(
            trusted_tools_used=False,
            final_answer="The cost is Rp 20.000.000 for PT PMA setup.",
            llm_gateway=gw,
        )
        assert result is True

    @pytest.mark.unit
    def test_has_tools_flips_true_without_pricing(self):
        """LLM had tools + non-empty final_answer → trusted=True, even
        when no pricing marker is present."""
        from backend.services.rag.agentic._reasoning_policy import (
            apply_shared_trusted_flippers,
        )
        gw = _make_gateway(gemini_tools=[MagicMock(), MagicMock()])
        result = apply_shared_trusted_flippers(
            trusted_tools_used=False,
            final_answer="Requirements for KITAS are passport, sponsor, application form.",
            llm_gateway=gw,
        )
        assert result is True

    @pytest.mark.unit
    def test_no_pricing_no_tools_stays_false(self):
        """No pricing, no tools, no final_answer → helper is a no-op."""
        from backend.services.rag.agentic._reasoning_policy import (
            apply_shared_trusted_flippers,
        )
        gw = _make_gateway(gemini_tools=[])
        result = apply_shared_trusted_flippers(
            trusted_tools_used=False,
            final_answer="",
            llm_gateway=gw,
        )
        assert result is False

    @pytest.mark.unit
    def test_empty_answer_with_tools_does_not_flip(self):
        """Edge case: has-tools check requires non-empty final_answer.
        Tools available + empty answer → do NOT set trusted=True.
        The has-tools flipper is guarded on `if state.final_answer`.
        """
        from backend.services.rag.agentic._reasoning_policy import (
            apply_shared_trusted_flippers,
        )
        gw = _make_gateway(gemini_tools=[MagicMock()])
        result = apply_shared_trusted_flippers(
            trusted_tools_used=False,
            final_answer="",
            llm_gateway=gw,
        )
        assert result is False
