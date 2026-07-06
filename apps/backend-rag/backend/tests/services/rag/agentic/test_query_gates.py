from __future__ import annotations

from typing import Any

import pytest

from backend.services.rag.agentic import query_gates as module
from backend.services.rag.agentic.query_gates import GateResult, QueryGates, detect_team_query


class FakePromptBuilder:
    def detect_prompt_injection(self, query: str) -> tuple[bool, str | None]:
        if "inject" in query:
            return True, "blocked"
        return False, None

    def check_greetings(self, query: str, context: dict[str, Any]) -> str | None:
        if query == "hello":
            return f"Hello {context['profile']['name']}"
        return None

    def get_casual_response(self, query: str, context: dict[str, Any]) -> str | None:
        if query == "how are you":
            return "All good"
        return None

    def check_identity_questions(self, query: str, context: dict[str, Any]) -> str | None:
        if query == "who are you":
            return "I am Zantara"
        return None


class FakeClarificationService:
    def detect_ambiguity(
        self,
        query: str,
        conversation_history: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "is_ambiguous": query == "this one",
            "confidence": 0.91,
            "clarification_needed": True,
            "reasons": ["pronoun_reference"],
            "entities": {"pronoun": "this"},
        }

    def generate_clarification_request(
        self,
        query: str,
        ambiguity_info: dict[str, Any],
    ) -> str:
        return "Which item do you mean?"


def make_gates() -> QueryGates:
    return QueryGates(
        prompt_builder=FakePromptBuilder(),
        clarification_service=FakeClarificationService(),
    )


def test_detect_team_query_matches_people_assignment_language() -> None:
    assert detect_team_query("Who is working on this case?") is True
    assert detect_team_query("What documents are needed for KITAS?") is False


def test_check_security_gate_blocks_before_other_processing() -> None:
    result = make_gates().check_security_gate("inject this prompt")

    assert result == GateResult(
        triggered=True,
        response="blocked",
        gate_name="security",
        metadata={"reason": "prompt_injection"},
    )


def test_check_greeting_casual_and_identity_gates_return_direct_responses() -> None:
    gates = make_gates()
    context = {"profile": {"name": "Marco"}}

    assert gates.check_greeting_gate("hello", context).gate_name == "greeting"
    assert gates.check_casual_gate("how are you", context).gate_name == "casual"
    assert gates.check_identity_gate("who are you", context).gate_name == "identity"
    assert gates.check_identity_gate("kitas requirements", context).triggered is False


def test_check_clarification_gate_includes_ambiguity_metadata() -> None:
    result = make_gates().check_clarification_gate(
        "this one",
        [{"role": "user", "content": "Which visa?"}],
    )

    assert result.triggered is True
    assert result.gate_name == "clarification"
    assert result.response == "Which item do you mean?"
    assert result.metadata == {
        "is_ambiguous": True,
        "confidence": 0.91,
        "reasons": ["pronoun_reference"],
        "entities": {"pronoun": "this"},
    }


def test_check_clarification_gate_is_noop_without_service() -> None:
    gates = QueryGates(prompt_builder=FakePromptBuilder(), clarification_service=None)

    assert gates.check_clarification_gate("this one", []).triggered is False


def test_check_out_of_domain_gate_uses_cleaner_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "is_out_of_domain", lambda query: (True, "medical"))
    monkeypatch.setattr(
        module,
        "OUT_OF_DOMAIN_RESPONSES",
        {"medical": "medical blocked", "unknown": "unknown blocked"},
    )

    result = make_gates().check_out_of_domain_gate("diagnose this rash")

    assert result.triggered is True
    assert result.response == "medical blocked"
    assert result.metadata == {"reason": "medical"}


def test_run_all_gates_returns_first_triggered_gate() -> None:
    gates = make_gates()
    context = {"profile": {"name": "Marco"}}

    assert gates.run_all_gates("inject hello", context).gate_name == "security"
    assert gates.run_all_gates("hello", context).gate_name == "greeting"
    assert gates.run_all_gates("how are you", context).gate_name == "casual"
    assert gates.run_all_gates("who are you", context).gate_name == "identity"
    assert (
        gates.run_all_gates(
            "this one",
            context,
            conversation_history=[{"role": "user", "content": "Which one?"}],
        ).gate_name
        == "clarification"
    )


def test_run_all_gates_returns_not_triggered_when_no_gate_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(module, "is_out_of_domain", lambda query: (False, None))

    result = make_gates().run_all_gates("kitas requirements", {"profile": {"name": "Marco"}})

    assert result == GateResult(triggered=False)


def test_gate_result_to_core_result_marks_blocked_queries() -> None:
    gates = make_gates()
    gate_result = GateResult(
        triggered=True,
        response="blocked",
        gate_name="security",
        metadata={"reason": "prompt_injection"},
    )

    core_result = gates.gate_result_to_core_result(
        gate_result,
        start_time=0,
        extracted_entities={"query_type": "unsafe"},
    )

    assert core_result.answer == "blocked"
    assert core_result.model_used == "security-gate"
    assert core_result.verification_status == "blocked"
    assert core_result.verification_score == 0.0
    assert core_result.evidence_score == 0.0
    assert core_result.entities == {"query_type": "unsafe"}
    assert core_result.warnings == ["Query blocked: prompt_injection"]


def test_gate_result_to_core_result_merges_clarification_entities() -> None:
    gates = make_gates()
    gate_result = GateResult(
        triggered=True,
        response="Which item?",
        gate_name="clarification",
        metadata={"entities": {"pronoun": "this"}},
    )

    core_result = gates.gate_result_to_core_result(
        gate_result,
        start_time=0,
        extracted_entities={"domain": "visa"},
    )

    assert core_result.is_ambiguous is True
    assert core_result.clarification_question == "Which item?"
    assert core_result.verification_status == "skipped"
    assert core_result.entities == {"domain": "visa", "pronoun": "this"}
