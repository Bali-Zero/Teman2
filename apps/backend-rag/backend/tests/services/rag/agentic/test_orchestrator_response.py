from types import SimpleNamespace

import pytest

from backend.services.llm_clients.pricing import TokenUsage
from backend.services.rag.agentic.orchestrator_response import OrchestratorResponseBuilder
from backend.services.tools.definitions import AgentState


def test_build_core_result_maps_state_metadata_and_abstain_reason() -> None:
    state = AgentState(query="random unsupported topic")
    state.final_answer = "I do not have enough evidence."
    state.verification_score = 0.5
    state.evidence_score = 0.01
    usage = TokenUsage(prompt_tokens=10, completion_tokens=4, cost_usd=0.0001)

    result = OrchestratorResponseBuilder().build_core_result(
        state=state,
        sources=[{"title": "source"}],
        extracted_entities={"visa_types": ["KITAS"]},
        model_used="gemini-test",
        token_usage=usage,
        timings={"total": 0.5},
        start_time=0.0,
        workflow={"steps": []},
        reasoning="reasoned",
    )

    assert result.answer == "I do not have enough evidence."
    assert result.sources == [{"title": "source"}]
    assert result.entities == {"visa_types": ["KITAS"]}
    assert result.model_used == "gemini-test"
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 4
    assert result.total_tokens == 14
    assert result.document_count == 1
    assert result.verification_status == "unchecked"
    assert result.abstain is True
    assert result.abstain_reason == "no_relevant_context"
    assert result.workflow == {"steps": []}
    assert result.reasoning == "reasoned"


def test_build_gate_response_uses_trusted_defaults(monkeypatch) -> None:
    monkeypatch.setattr("time.time", lambda: 101.5)

    result = OrchestratorResponseBuilder().build_gate_response(
        answer="Hello",
        model_used="greeting-gate",
        entities={"intent": "greeting"},
        start_time=100.0,
    )

    assert result.answer == "Hello"
    assert result.model_used == "greeting-gate"
    assert result.verification_score == 1.0
    assert result.evidence_score == 1.0
    assert result.verification_status == "passed"
    assert result.timings == {"total": 1.5}
    assert result.sources == []


def test_build_clarification_response_preserves_entities(monkeypatch) -> None:
    monkeypatch.setattr("time.time", lambda: 15.0)

    result = OrchestratorResponseBuilder().build_clarification_response(
        clarification_msg="Do you mean investor KITAS or spouse KITAS?",
        ambiguity_info={"entities": {"visa_type": ["KITAS"]}},
        start_time=10.0,
    )

    assert result.is_ambiguous is True
    assert result.clarification_question == "Do you mean investor KITAS or spouse KITAS?"
    assert result.entities == {"visa_type": ["KITAS"]}
    assert result.model_used == "clarification-gate"
    assert result.verification_status == "skipped"
    assert result.timings == {"total": 5.0}


@pytest.mark.parametrize(
    ("reason", "expected_model"),
    [("medical", "out-of-domain-medical"), ("politics", "out-of-domain-politics")],
)
def test_build_out_of_domain_response_blocks_with_warning(monkeypatch, reason, expected_model) -> None:
    monkeypatch.setattr("time.time", lambda: 4.0)

    result = OrchestratorResponseBuilder().build_out_of_domain_response(
        answer_text="I cannot help with that topic.",
        reason=reason,
        start_time=1.0,
    )

    assert result.answer == "I cannot help with that topic."
    assert result.model_used == expected_model
    assert result.verification_status == "blocked"
    assert result.warnings == [f"Query blocked: {reason}"]
    assert result.document_count == 0
    assert result.timings == {"total": 3.0}


def test_builder_accepts_optional_entity_extractor() -> None:
    extractor = SimpleNamespace(name="extractor")

    assert OrchestratorResponseBuilder(entity_extractor=extractor).entity_extractor is extractor
