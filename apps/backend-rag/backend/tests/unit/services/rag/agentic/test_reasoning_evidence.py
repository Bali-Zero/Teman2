"""
Tests for `_reasoning_evidence.py`'s trusted-tool/final_answer relevance check.

Policy under test: `detect_trusted_tool_usage` gains an optional
`final_answer` keyword-only parameter. When supplied, a qualifying step on
one of the 4 "quotable" tools (get_pricing, crm_query, timesheet, calculator)
must also share a literal numeric token with `final_answer` before it grants
trust — this catches the LLM citing a trusted tool while writing a number the
tool never returned. Non-quotable structured/exact tools (team_knowledge and
successful exact kbli_lookup results) and the `final_answer=None` case preserve
unconditional trust.
Semantic vector search is intentionally absent from the production allowlist:
successful-but-irrelevant retrieval must take the relevance-score path.
"""

from typing import Any
from unittest.mock import MagicMock

import pytest

from backend.services.rag.agentic._reasoning_evidence import (
    _extract_literal_tokens,
    detect_quotable_relevance_veto,
    detect_trusted_tool_usage,
)

# ============================================================
# Fixtures / Helpers (mirrors test_abstain_bypass_policy.py)
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


_TRUSTED_TOOL_NAMES = frozenset(
    {"calculator", "crm_query", "get_pricing", "kbli_lookup", "team_knowledge", "timesheet"}
)


# ============================================================
# _extract_literal_tokens
# ============================================================


class TestExtractLiteralTokens:
    @pytest.mark.unit
    def test_plain_digit_run(self):
        assert _extract_literal_tokens("price is 5000000 rupiah") == frozenset({"5000000"})

    @pytest.mark.unit
    def test_comma_grouped(self):
        assert _extract_literal_tokens("Result: 5,000,000") == frozenset({"5000000"})

    @pytest.mark.unit
    def test_dot_grouped(self):
        assert _extract_literal_tokens("Rp 5.000.000") == frozenset({"5000000"})

    @pytest.mark.unit
    def test_all_three_formats_normalize_to_same_token(self):
        plain = _extract_literal_tokens("5000000")
        comma = _extract_literal_tokens("5,000,000")
        dot = _extract_literal_tokens("5.000.000")
        assert plain == comma == dot == frozenset({"5000000"})

    @pytest.mark.unit
    def test_short_number_dropped(self):
        assert _extract_literal_tokens("only 42 items") == frozenset()

    @pytest.mark.unit
    def test_empty_text_returns_empty(self):
        assert _extract_literal_tokens("") == frozenset()

    @pytest.mark.unit
    def test_none_text_returns_empty(self):
        assert _extract_literal_tokens(None) == frozenset()


# ============================================================
# detect_trusted_tool_usage — GUILT (mismatched numbers)
# ============================================================


class TestQuotableToolMismatchNotTrusted:
    @pytest.mark.unit
    def test_get_pricing_mismatched_number_not_trusted(self):
        obs = (
            '{"service": "PT PMA Setup", "price": 5000000, "notes": '
            '"includes notary and OSS registration fees for the full process"}'
        )
        assert len(obs) > 50
        step = _make_step("get_pricing", obs)
        result = detect_trusted_tool_usage(
            [step],
            _TRUSTED_TOOL_NAMES,
            final_answer="The setup will cost around 2000000 rupiah.",
        )
        assert result is False

    @pytest.mark.unit
    def test_crm_query_mismatched_number_not_trusted(self):
        obs = (
            '{"client": "Jane Doe", "outstanding_invoice_amount": 750000, '
            '"status": "active", "practice_count": 3}'
        )
        assert len(obs) > 50
        step = _make_step("crm_query", obs)
        result = detect_trusted_tool_usage(
            [step],
            _TRUSTED_TOOL_NAMES,
            final_answer="Your outstanding balance is 999000.",
        )
        assert result is False

    @pytest.mark.unit
    def test_calculator_mismatched_number_not_trusted(self):
        obs = "Result: 3,300,000 — this is the total after applying the discount rate requested"
        assert len(obs) > 50
        step = _make_step("calculator", obs)
        result = detect_trusted_tool_usage(
            [step],
            _TRUSTED_TOOL_NAMES,
            final_answer="The total comes to 4400000.",
        )
        assert result is False


# ============================================================
# detect_trusted_tool_usage — INNOCENCE
# ============================================================


class TestQuotableToolMatchTrusted:
    @pytest.mark.unit
    def test_get_pricing_plain_digit_match(self):
        obs = (
            '{"service": "PT PMA Setup", "price": 5000000, "notes": '
            '"includes notary and OSS registration fees for the full process"}'
        )
        step = _make_step("get_pricing", obs)
        result = detect_trusted_tool_usage(
            [step],
            _TRUSTED_TOOL_NAMES,
            final_answer="The setup will cost 5000000 rupiah in total.",
        )
        assert result is True

    @pytest.mark.unit
    def test_get_pricing_comma_grouped_match(self):
        obs = (
            '{"service": "PT PMA Setup", "price": 5000000, "notes": '
            '"includes notary and OSS registration fees for the full process"}'
        )
        step = _make_step("get_pricing", obs)
        result = detect_trusted_tool_usage(
            [step],
            _TRUSTED_TOOL_NAMES,
            final_answer="The setup will cost Rp 5,000,000 in total.",
        )
        assert result is True

    @pytest.mark.unit
    def test_get_pricing_dot_grouped_match(self):
        obs = (
            '{"service": "PT PMA Setup", "price": 5000000, "notes": '
            '"includes notary and OSS registration fees for the full process"}'
        )
        step = _make_step("get_pricing", obs)
        result = detect_trusted_tool_usage(
            [step],
            _TRUSTED_TOOL_NAMES,
            final_answer="Biayanya adalah Rp 5.000.000 semua termasuk.",
        )
        assert result is True


class TestNonQuotableStructuredToolsUnconditionalTrust:
    @pytest.mark.unit
    def test_team_knowledge_no_overlap_still_trusted(self):
        obs = (
            "Damar is the Operations Manager, specializes in client onboarding "
            "and process design, department: Client Services."
        )
        assert len(obs) > 50
        step = _make_step("team_knowledge", obs)
        result = detect_trusted_tool_usage(
            [step],
            _TRUSTED_TOOL_NAMES,
            final_answer="You should ask about visas — no numbers here at all.",
        )
        assert result is True

    @pytest.mark.unit
    def test_exact_kbli_lookup_no_overlap_still_trusted(self):
        obs = (
            '{"found": true, "code": "51101", "pma": '
            '{"max_foreign_ownership_percent": 49, "condition": "single majority"}}'
        )
        assert len(obs) > 50
        step = _make_step("kbli_lookup", obs)
        result = detect_trusted_tool_usage(
            [step],
            _TRUSTED_TOOL_NAMES,
            final_answer="KBLI 51101 has a restricted foreign ownership regime.",
        )
        assert result is True

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "observation",
        (
            '{"found": false, "code": "68200", '
            '"reason": "CODE_NOT_IN_KBLI_2025_CANONICAL"}',
            '{"found": false, "code": "51101", "error": "DATASET_UNAVAILABLE"}',
            "not-json but long enough to cross the trusted observation threshold safely",
            '["valid", "json", "but", "not", "a", "canonical", "record"]',
        ),
    )
    def test_unsuccessful_kbli_lookup_never_grants_trust(self, observation):
        step = _make_step("kbli_lookup", observation)

        assert (
            detect_trusted_tool_usage(
                [step],
                _TRUSTED_TOOL_NAMES,
                final_answer="KBLI 68200 is fully open to foreign ownership.",
            )
            is False
        )

    @pytest.mark.unit
    def test_vector_search_is_not_on_the_trusted_allowlist(self):
        obs = (
            "Found a high-scoring but unrelated visa regulation with enough "
            "text to pass the old observation-length guard."
        )
        step = _make_step("vector_search", obs)
        result = detect_trusted_tool_usage(
            [step],
            _TRUSTED_TOOL_NAMES,
            final_answer="KBLI 51101 permits 100 percent foreign ownership.",
        )
        assert result is False


class TestFinalAnswerNoneBackwardCompatible:
    @pytest.mark.unit
    def test_final_answer_none_explicit_matches_omitted_call(self):
        obs = "PT PMA setup: Rp 45.000.000. Includes notary, OSS registration, and 6-month support."
        step = _make_step("get_pricing", obs)

        with_none = detect_trusted_tool_usage(
            [step], _TRUSTED_TOOL_NAMES, final_answer=None
        )
        without_param = detect_trusted_tool_usage([step], _TRUSTED_TOOL_NAMES)

        assert with_none is True
        assert without_param is True
        assert with_none == without_param


class TestQuotableToolNoCheckableLiteral:
    @pytest.mark.unit
    def test_crm_query_no_number_in_observation_still_trusted(self):
        obs = (
            "Found client: Jane Doe, status active, currently enrolled in the "
            "standard tax compliance retainer package with no open invoices"
        )
        assert len(obs) > 50
        assert _extract_literal_tokens(obs) == frozenset()
        step = _make_step("crm_query", obs)
        result = detect_trusted_tool_usage(
            [step],
            _TRUSTED_TOOL_NAMES,
            final_answer="Jane Doe's account is in good standing.",
        )
        assert result is True


class TestMultiStepOrSemantics:
    @pytest.mark.unit
    def test_one_failing_quotable_step_vector_retrieval_does_not_restore_trust(self):
        failing_obs = (
            '{"service": "PT PMA Setup", "price": 5000000, "notes": '
            '"includes notary and OSS registration fees for the full process"}'
        )
        passing_obs = (
            "Found 3 matching regulations: KITAS requires sponsor letter, "
            "health insurance, and valid passport with 18+ months validity."
        )
        failing_step = _make_step("get_pricing", failing_obs)
        passing_step = _make_step("vector_search", passing_obs)

        result = detect_trusted_tool_usage(
            [failing_step, passing_step],
            _TRUSTED_TOOL_NAMES,
            final_answer="The requirements are a sponsor letter and health insurance.",
        )
        assert result is False

    @pytest.mark.unit
    def test_one_failing_quotable_step_one_passing_quotable_step_trusted(self):
        failing_obs = (
            '{"service": "PT PMA Setup", "price": 5000000, "notes": '
            '"includes notary and OSS registration fees for the full process"}'
        )
        passing_obs = "Result: 3,300,000 — total after applying the discount rate requested"
        failing_step = _make_step("get_pricing", failing_obs)
        passing_step = _make_step("calculator", passing_obs)

        result = detect_trusted_tool_usage(
            [failing_step, passing_step],
            _TRUSTED_TOOL_NAMES,
            final_answer="The total comes to 3300000 after the discount.",
        )
        assert result is True

    @pytest.mark.unit
    def test_all_quotable_steps_fail_returns_false(self):
        obs1 = (
            '{"service": "PT PMA Setup", "price": 5000000, "notes": '
            '"includes notary and OSS registration fees for the full process"}'
        )
        obs2 = "Result: 3,300,000 — total after applying the discount rate requested"
        step1 = _make_step("get_pricing", obs1)
        step2 = _make_step("calculator", obs2)

        result = detect_trusted_tool_usage(
            [step1, step2],
            _TRUSTED_TOOL_NAMES,
            final_answer="Unrelated numbers here: 9999999 and 1234567.",
        )
        assert result is False


# ============================================================
# detect_quotable_relevance_veto — aggregate-trust mismatch guard
# ============================================================
#
# A separate qualifying step can grant aggregate trust even when a quotable
# tool's own output is contradicted. This veto forces trusted_tools_used back
# to False after trust inputs are combined, so the mismatch wins.


class TestQuotableRelevanceVetoGuilt:
    @pytest.mark.unit
    def test_mismatched_pricing_number_vetoes_even_with_pricing_marker_in_answer(self):
        """A monetary claim must still match the executed pricing tool."""
        obs = (
            '{"service": "PT PMA Setup", "price": 5000000, "notes": '
            '"includes notary and OSS registration fees for the full process"}'
        )
        step = _make_step("get_pricing", obs)
        result = detect_quotable_relevance_veto(
            [step], final_answer="The setup will cost Rp 2.000.000 in total."
        )
        assert result is True

    @pytest.mark.unit
    def test_crm_query_mismatch_vetoes(self):
        obs = (
            '{"client": "Jane Doe", "outstanding_invoice_amount": 750000, '
            '"status": "active", "practice_count": 3}'
        )
        step = _make_step("crm_query", obs)
        result = detect_quotable_relevance_veto(
            [step], final_answer="Your outstanding balance is 999000."
        )
        assert result is True

    @pytest.mark.unit
    def test_veto_fires_even_when_another_step_independently_qualifies(self):
        """Vector retrieval cannot restore trust, and the independent veto
        still reports the confirmed pricing mismatch."""
        mismatched_pricing_obs = (
            '{"service": "PT PMA Setup", "price": 5000000, "notes": '
            '"includes notary and OSS registration fees for the full process"}'
        )
        vector_obs = (
            "Found 3 matching regulations: KITAS requires sponsor letter, "
            "health insurance, and valid passport with 18+ months validity."
        )
        pricing_step = _make_step("get_pricing", mismatched_pricing_obs)
        vector_step = _make_step("vector_search", vector_obs)

        base_trust = detect_trusted_tool_usage(
            [pricing_step, vector_step],
            _TRUSTED_TOOL_NAMES,
            final_answer="The requirements are a sponsor letter and health insurance.",
        )
        veto = detect_quotable_relevance_veto(
            [pricing_step, vector_step],
            final_answer="The requirements are a sponsor letter and health insurance.",
        )
        assert base_trust is False
        assert veto is True


class TestQuotableRelevanceVetoInnocence:
    @pytest.mark.unit
    def test_matching_number_does_not_veto(self):
        obs = (
            '{"service": "PT PMA Setup", "price": 5000000, "notes": '
            '"includes notary and OSS registration fees for the full process"}'
        )
        step = _make_step("get_pricing", obs)
        result = detect_quotable_relevance_veto(
            [step], final_answer="The setup will cost Rp 5.000.000 in total."
        )
        assert result is False

    @pytest.mark.unit
    def test_non_quotable_tool_never_vetoes(self):
        """team_knowledge/vector_search are excluded from the quotable set —
        their content never triggers this veto regardless of overlap."""
        obs = (
            "Damar is the Operations Manager, specializes in client onboarding "
            "and process design, department: Client Services."
        )
        step = _make_step("team_knowledge", obs)
        result = detect_quotable_relevance_veto(
            [step], final_answer="You should ask about visas — no numbers here at all."
        )
        assert result is False

    @pytest.mark.unit
    def test_no_checkable_literal_does_not_veto(self):
        obs = (
            "Found client: Jane Doe, status active, currently enrolled in the "
            "standard tax compliance retainer package with no open invoices"
        )
        step = _make_step("crm_query", obs)
        result = detect_quotable_relevance_veto(
            [step], final_answer="Jane Doe's account is in good standing."
        )
        assert result is False

    @pytest.mark.unit
    def test_final_answer_none_does_not_veto(self):
        """Mirrors detect_trusted_tool_usage's own safe default for the
        streaming crm_query early-exit caller (final_answer doesn't exist yet)."""
        obs = "PT PMA setup: Rp 45.000.000. Includes notary, OSS registration, and 6-month support."
        step = _make_step("get_pricing", obs)
        result = detect_quotable_relevance_veto([step], final_answer=None)
        assert result is False

    @pytest.mark.unit
    def test_no_steps_does_not_veto(self):
        assert detect_quotable_relevance_veto([], final_answer="anything") is False
