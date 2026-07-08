from types import SimpleNamespace
from typing import Any

import pytest

from backend.prompts.zantara_prompt_builder import PromptContext
from backend.services.oracle import reasoning_engine as reasoning_module
from backend.services.oracle.reasoning_engine import ReasoningEngineService


class FakePromptBuilder:
    def build(self, context: PromptContext) -> str:
        return f"system:{context.mode}"


class FakeValidator:
    def validate(self, answer: str, context: PromptContext) -> SimpleNamespace:
        return SimpleNamespace(validated=f"validated:{answer}", violations=["trimmed"])


class FakeModel:
    def generate_content(self, **kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(text="raw answer")


def _context() -> PromptContext:
    return PromptContext(
        query="What is KITAS?",
        language="en",
        mode="legal_brief",
        emotional_state="neutral",
    )


def test_build_context_uses_excerpts_memory_and_recent_history() -> None:
    service = ReasoningEngineService(prompt_builder=FakePromptBuilder())
    long_doc = "A" * 1600
    history = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]

    context = service.build_context(
        documents=[long_doc],
        user_memory_facts=["prefers concise answers"],
        conversation_history=history,
    )

    assert "RELEVANT DOCUMENT EXCERPTS" in context
    assert "Document 1: " + ("A" * 1500) + "..." in context
    assert "USER CONTEXT" in context
    assert "- prefers concise answers" in context
    assert "User: hello" in context
    assert "Zantara: hi" in context


def test_build_context_can_include_full_documents() -> None:
    service = ReasoningEngineService(prompt_builder=FakePromptBuilder())

    context = service.build_context(["complete document"], use_full_docs=True)

    assert "FULL DOCUMENT CONTEXT" in context
    assert "complete document" in context
    assert "Document 1:" not in context


@pytest.mark.asyncio
async def test_reason_with_gemini_validates_successful_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ReasoningEngineService(
        prompt_builder=FakePromptBuilder(),
        response_validator=FakeValidator(),
    )
    monkeypatch.setattr(
        reasoning_module,
        "google_services",
        SimpleNamespace(get_gemini_model=lambda model_name: FakeModel()),
    )

    result = await service.reason_with_gemini(
        documents=["doc"],
        query="What is KITAS?",
        context=_context(),
    )

    assert result["success"] is True
    assert result["answer"] == "validated:raw answer"
    assert result["document_count"] == 1
    assert result["mode_used"] == "legal_brief"


@pytest.mark.asyncio
async def test_reason_with_gemini_returns_structured_error_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ReasoningEngineService(prompt_builder=FakePromptBuilder())
    monkeypatch.setattr(reasoning_module, "google_services", SimpleNamespace())

    result = await service.reason_with_gemini(
        documents=["doc"],
        query="What is KITAS?",
        context=_context(),
    )

    assert result["success"] is False
    assert result["document_count"] == 1
    assert "error" in result
