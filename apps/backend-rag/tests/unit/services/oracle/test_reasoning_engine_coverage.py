import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest


class DummyPromptContext:
    def __init__(self, mode="default"):
        self.mode = mode


class DummyPromptBuilder:
    def __init__(self, model_adapter=None):
        self.model_adapter = model_adapter

    def build(self, context):
        return f"SYSTEM:{context.mode}"


class DummyModel:
    def __init__(self, text="answer", error=None):
        self.text = text
        self._error = error
        self.last_contents = None
        self.last_config = None

    def generate_content(self, contents, generation_config):
        if self._error:
            raise self._error
        self.last_contents = contents
        self.last_config = generation_config
        return SimpleNamespace(text=self.text)


class DummyValidator:
    def __init__(self, validated="validated", violations=None):
        self.validated = validated
        self.violations = violations or []

    def validate(self, raw_answer, context):
        return SimpleNamespace(validated=self.validated, violations=self.violations)


services_pkg = types.ModuleType("services")
oracle_pkg = types.ModuleType("services.oracle")
oracle_pkg.__path__ = []
response_pkg = types.ModuleType("services.response")
response_pkg.__path__ = []
validator_module = types.ModuleType("services.response.validator")
validator_module.ZantaraResponseValidator = DummyValidator

google_services_module = types.ModuleType("services.oracle.oracle_google_services")
google_services_module.google_services = SimpleNamespace(get_gemini_model=lambda *_a, **_k: None)

llm_pkg = types.ModuleType("llm")
llm_adapters_pkg = types.ModuleType("llm.adapters")
llm_adapters_pkg.__path__ = []
gemini_module = types.ModuleType("llm.adapters.gemini")
gemini_module.GeminiAdapter = object

prompts_pkg = types.ModuleType("prompts")
prompt_builder_module = types.ModuleType("prompts.zantara_prompt_builder")
prompt_builder_module.PromptContext = DummyPromptContext
prompt_builder_module.ZantaraPromptBuilder = DummyPromptBuilder

sys.modules.update(
    {
        "services": services_pkg,
        "services.oracle": oracle_pkg,
        "services.response": response_pkg,
        "services.response.validator": validator_module,
        "services.oracle.oracle_google_services": google_services_module,
        "llm": llm_pkg,
        "llm.adapters": llm_adapters_pkg,
        "llm.adapters.gemini": gemini_module,
        "prompts": prompts_pkg,
        "prompts.zantara_prompt_builder": prompt_builder_module,
    }
)

module_path = (
    Path(__file__).resolve().parents[4] / "backend" / "services" / "oracle" / "reasoning_engine.py"
)
spec = importlib.util.spec_from_file_location("services.oracle.reasoning_engine", module_path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
ReasoningEngineService = module.ReasoningEngineService


def test_build_context_with_full_docs_and_memory():
    service = ReasoningEngineService(prompt_builder=DummyPromptBuilder())
    context = service.build_context(
        ["doc1", "doc2"],
        user_memory_facts=["fact1", "fact2"],
        conversation_history=[{"role": "user", "content": "hello"}],
        use_full_docs=True,
    )
    assert "FULL DOCUMENT CONTEXT" in context
    assert "fact1" in context
    assert "User: hello" in context


def test_build_context_with_excerpts():
    service = ReasoningEngineService(prompt_builder=DummyPromptBuilder())
    context = service.build_context(["doc1"], use_full_docs=False)
    assert "RELEVANT DOCUMENT EXCERPTS" in context
    assert "Document 1:" in context


@pytest.mark.asyncio
async def test_reason_with_gemini_success_with_validator(monkeypatch):
    model = DummyModel(text="raw")
    monkeypatch.setattr(module.google_services, "get_gemini_model", lambda *_a, **_k: model)
    validator = DummyValidator(validated="validated", violations=["v1"])
    service = ReasoningEngineService(
        prompt_builder=DummyPromptBuilder(), response_validator=validator
    )
    result = await service.reason_with_gemini(
        documents=["doc"],
        query="q",
        context=DummyPromptContext(mode="legal_brief"),
        use_full_docs=False,
    )
    assert result["answer"] == "validated"
    assert result["success"] is True
    assert model.last_config["temperature"] == 0.3


@pytest.mark.asyncio
async def test_reason_with_gemini_error(monkeypatch):
    model = DummyModel(error=RuntimeError("boom"))
    monkeypatch.setattr(module.google_services, "get_gemini_model", lambda *_a, **_k: model)
    service = ReasoningEngineService(prompt_builder=DummyPromptBuilder())
    result = await service.reason_with_gemini(
        documents=["doc"],
        query="q",
        context=DummyPromptContext(mode="default"),
    )
    assert result["success"] is False
    assert "boom" in result["error"]


def test_build_context_long_content_truncated():
    """Test build_context with conversation history content > 500 chars (line 91)"""
    service = ReasoningEngineService(prompt_builder=DummyPromptBuilder())
    long_content = "x" * 600  # Content longer than 500 chars
    context = service.build_context(
        ["doc1"],
        conversation_history=[{"role": "user", "content": long_content}],
        use_full_docs=False,
    )
    assert "..." in context  # Should be truncated
    assert len([line for line in context.split("\n") if "x" * 600 in line]) == 0  # Full content not present
    assert len([line for line in context.split("\n") if "x" * 500 in line]) > 0  # Truncated content present


@pytest.mark.asyncio
async def test_reason_with_gemini_no_validator(monkeypatch):
    """Test reason_with_gemini without validator (line 174)"""
    model = DummyModel(text="raw answer")
    monkeypatch.setattr(module.google_services, "get_gemini_model", lambda *_a, **_k: model)
    service = ReasoningEngineService(prompt_builder=DummyPromptBuilder())  # No validator
    result = await service.reason_with_gemini(
        documents=["doc"],
        query="q",
        context=DummyPromptContext(mode="default"),
    )
    assert result["success"] is True
    assert result["answer"] == "raw answer"  # Should use raw_answer directly (line 174)
