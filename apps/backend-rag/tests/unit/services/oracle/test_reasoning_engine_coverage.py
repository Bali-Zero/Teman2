"""
Test coverage for reasoning_engine.py - 100% coverage target.

This test module uses dynamic imports but coverage can still track the source file.
Run with: pytest --cov=services/oracle/reasoning_engine --cov-report=term-missing
"""
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


# Setup mock modules
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

# Import module dynamically - coverage will track the source file if run with --cov
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


# ========== __init__ Tests ==========
def test_init_with_both_parameters():
    """Test __init__ with both prompt_builder and response_validator"""
    builder = DummyPromptBuilder()
    validator = DummyValidator()
    service = ReasoningEngineService(prompt_builder=builder, response_validator=validator)
    assert service.prompt_builder is builder
    assert service.response_validator is validator


def test_init_without_prompt_builder():
    """Test __init__ without prompt_builder (should create default)"""
    validator = DummyValidator()
    service = ReasoningEngineService(response_validator=validator)
    assert service.prompt_builder is not None
    assert service.response_validator is validator


def test_init_without_validator():
    """Test __init__ without response_validator (should be None)"""
    builder = DummyPromptBuilder()
    service = ReasoningEngineService(prompt_builder=builder)
    assert service.prompt_builder is builder
    assert service.response_validator is None


def test_init_without_parameters():
    """Test __init__ without any parameters (should create default prompt_builder)"""
    service = ReasoningEngineService()
    assert service.prompt_builder is not None
    assert service.response_validator is None


# ========== build_context Tests - Documents Branch ==========
def test_build_context_full_docs_empty_documents():
    """Test build_context with use_full_docs=True but empty documents (line 61-64)"""
    service = ReasoningEngineService(prompt_builder=DummyPromptBuilder())
    context = service.build_context([], use_full_docs=True)
    # Should use excerpts branch when documents is empty (line 65)
    assert "RELEVANT DOCUMENT EXCERPTS" in context


def test_build_context_full_docs_no_documents():
    """Test build_context with use_full_docs=True but no documents"""
    service = ReasoningEngineService(prompt_builder=DummyPromptBuilder())
    context = service.build_context([], use_full_docs=True)
    assert "RELEVANT DOCUMENT EXCERPTS" in context


def test_build_context_excerpts_empty_documents():
    """Test build_context with use_full_docs=False and empty documents"""
    service = ReasoningEngineService(prompt_builder=DummyPromptBuilder())
    context = service.build_context([], use_full_docs=False)
    assert "RELEVANT DOCUMENT EXCERPTS" in context


# ========== build_context Tests - Memory Branch ==========
def test_build_context_without_memory():
    """Test build_context without user_memory_facts (line 73)"""
    service = ReasoningEngineService(prompt_builder=DummyPromptBuilder())
    context = service.build_context(["doc1"], user_memory_facts=None)
    assert "USER CONTEXT" not in context
    assert "RELEVANT DOCUMENT EXCERPTS" in context


def test_build_context_with_empty_memory():
    """Test build_context with empty user_memory_facts list"""
    service = ReasoningEngineService(prompt_builder=DummyPromptBuilder())
    context = service.build_context(["doc1"], user_memory_facts=[])
    # Empty list is falsy, so should not add memory context
    assert "USER CONTEXT" not in context


# ========== build_context Tests - Conversation History Branch ==========
def test_build_context_without_conversation_history():
    """Test build_context without conversation_history (line 80)"""
    service = ReasoningEngineService(prompt_builder=DummyPromptBuilder())
    context = service.build_context(["doc1"], conversation_history=None)
    assert "CONVERSATION HISTORY" not in context


def test_build_context_with_empty_conversation_history():
    """Test build_context with empty conversation_history list (line 80)"""
    service = ReasoningEngineService(prompt_builder=DummyPromptBuilder())
    context = service.build_context(["doc1"], conversation_history=[])
    assert "CONVERSATION HISTORY" not in context


def test_build_context_conversation_history_truncation():
    """Test build_context with >10 conversation history items (line 83)"""
    service = ReasoningEngineService(prompt_builder=DummyPromptBuilder())
    # Create 15 messages
    history = [{"role": "user", "content": f"msg{i}"} for i in range(15)]
    context = service.build_context(["doc1"], conversation_history=history)
    assert "CONVERSATION HISTORY" in context
    # Should only keep last 10
    assert "msg0" not in context  # First 5 should be removed
    assert "msg5" in context  # Last 10 should be present
    assert "msg14" in context  # Last message should be present


def test_build_context_conversation_history_exactly_10():
    """Test build_context with exactly 10 conversation history items (line 83)"""
    service = ReasoningEngineService(prompt_builder=DummyPromptBuilder())
    history = [{"role": "user", "content": f"msg{i}"} for i in range(10)]
    context = service.build_context(["doc1"], conversation_history=history)
    assert "CONVERSATION HISTORY" in context
    assert "msg0" in context  # All should be present
    assert "msg9" in context


def test_build_context_conversation_history_non_user_role():
    """Test build_context with non-user role (line 92 - should be Zantara)"""
    service = ReasoningEngineService(prompt_builder=DummyPromptBuilder())
    history = [{"role": "assistant", "content": "hello"}]
    context = service.build_context(["doc1"], conversation_history=history)
    assert "CONVERSATION HISTORY" in context
    assert "Zantara: hello" in context
    assert "User: hello" not in context


def test_build_context_conversation_history_missing_role():
    """Test build_context with message missing role key (line 88 - should default to 'user')"""
    service = ReasoningEngineService(prompt_builder=DummyPromptBuilder())
    history = [{"content": "hello"}]  # Missing role key
    context = service.build_context(["doc1"], conversation_history=history)
    assert "CONVERSATION HISTORY" in context
    assert "User: hello" in context


def test_build_context_conversation_history_missing_content():
    """Test build_context with message missing content key (line 89 - should default to '')"""
    service = ReasoningEngineService(prompt_builder=DummyPromptBuilder())
    history = [{"role": "user"}]  # Missing content key
    context = service.build_context(["doc1"], conversation_history=history)
    assert "CONVERSATION HISTORY" in context
    assert "User: " in context  # Should have empty content


def test_build_context_conversation_history_short_content():
    """Test build_context with content <= 500 chars (line 90 - should not truncate)"""
    service = ReasoningEngineService(prompt_builder=DummyPromptBuilder())
    short_content = "x" * 500  # Exactly 500 chars
    history = [{"role": "user", "content": short_content}]
    context = service.build_context(["doc1"], conversation_history=history)
    assert "CONVERSATION HISTORY" in context
    assert "..." not in context.split("User:")[1]  # Should not truncate 500 chars
    assert short_content in context


# ========== reason_with_gemini Tests - Mode/Temperature Branch ==========
@pytest.mark.asyncio
async def test_reason_with_gemini_procedure_guide_mode(monkeypatch):
    """Test reason_with_gemini with procedure_guide mode (temp 0.3, line 153)"""
    model = DummyModel(text="answer")
    monkeypatch.setattr(module.google_services, "get_gemini_model", lambda *_a, **_k: model)
    service = ReasoningEngineService(prompt_builder=DummyPromptBuilder())
    result = await service.reason_with_gemini(
        documents=["doc"],
        query="q",
        context=DummyPromptContext(mode="procedure_guide"),
    )
    assert result["success"] is True
    assert model.last_config["temperature"] == 0.3


@pytest.mark.asyncio
async def test_reason_with_gemini_default_mode(monkeypatch):
    """Test reason_with_gemini with default mode (temp 0.4, line 153)"""
    model = DummyModel(text="answer")
    monkeypatch.setattr(module.google_services, "get_gemini_model", lambda *_a, **_k: model)
    service = ReasoningEngineService(prompt_builder=DummyPromptBuilder())
    result = await service.reason_with_gemini(
        documents=["doc"],
        query="q",
        context=DummyPromptContext(mode="default"),
    )
    assert result["success"] is True
    assert model.last_config["temperature"] == 0.4


@pytest.mark.asyncio
async def test_reason_with_gemini_other_mode(monkeypatch):
    """Test reason_with_gemini with other mode (temp 0.4, line 153)"""
    model = DummyModel(text="answer")
    monkeypatch.setattr(module.google_services, "get_gemini_model", lambda *_a, **_k: model)
    service = ReasoningEngineService(prompt_builder=DummyPromptBuilder())
    result = await service.reason_with_gemini(
        documents=["doc"],
        query="q",
        context=DummyPromptContext(mode="other_mode"),
    )
    assert result["success"] is True
    assert model.last_config["temperature"] == 0.4


# ========== reason_with_gemini Tests - Validator Branch ==========
@pytest.mark.asyncio
async def test_reason_with_gemini_validator_no_violations(monkeypatch):
    """Test reason_with_gemini with validator but no violations (line 171 - should not log)"""
    model = DummyModel(text="raw")
    monkeypatch.setattr(module.google_services, "get_gemini_model", lambda *_a, **_k: model)
    validator = DummyValidator(validated="validated", violations=[])  # No violations
    service = ReasoningEngineService(
        prompt_builder=DummyPromptBuilder(), response_validator=validator
    )
    result = await service.reason_with_gemini(
        documents=["doc"],
        query="q",
        context=DummyPromptContext(mode="default"),
    )
    assert result["success"] is True
    assert result["answer"] == "validated"


# ========== reason_with_gemini Tests - All Parameters ==========
@pytest.mark.asyncio
async def test_reason_with_gemini_all_parameters(monkeypatch):
    """Test reason_with_gemini with all optional parameters"""
    model = DummyModel(text="answer")
    monkeypatch.setattr(module.google_services, "get_gemini_model", lambda *_a, **_k: model)
    service = ReasoningEngineService(prompt_builder=DummyPromptBuilder())
    result = await service.reason_with_gemini(
        documents=["doc1", "doc2"],
        query="test query",
        context=DummyPromptContext(mode="legal_brief"),
        use_full_docs=True,
        user_memory_facts=["fact1", "fact2"],
        conversation_history=[{"role": "user", "content": "hello"}],
    )
    assert result["success"] is True
    assert result["full_analysis"] is True
    assert result["document_count"] == 2
    assert result["mode_used"] == "legal_brief"
    # Verify context was built with all parameters
    assert model.last_contents is not None
    assert len(model.last_contents) == 2  # system_prompt and user_message


# ========== reason_with_gemini Tests - Error Handling ==========
@pytest.mark.asyncio
async def test_reason_with_gemini_error_handling_time_tracking(monkeypatch):
    """Test reason_with_gemini error handling tracks time correctly"""
    model = DummyModel(error=ValueError("test error"))
    monkeypatch.setattr(module.google_services, "get_gemini_model", lambda *_a, **_k: model)
    service = ReasoningEngineService(prompt_builder=DummyPromptBuilder())
    result = await service.reason_with_gemini(
        documents=["doc"],
        query="q",
        context=DummyPromptContext(mode="default"),
    )
    assert result["success"] is False
    assert "test error" in result["error"]
    assert "reasoning_time_ms" in result
    assert result["reasoning_time_ms"] >= 0
    assert result["full_analysis"] is False
    assert result["document_count"] == 1


# ========== build_context Tests - Edge Cases ==========
def test_build_context_all_none():
    """Test build_context with all optional parameters None"""
    service = ReasoningEngineService(prompt_builder=DummyPromptBuilder())
    context = service.build_context(
        documents=[],
        user_memory_facts=None,
        conversation_history=None,
        use_full_docs=False,
    )
    assert "RELEVANT DOCUMENT EXCERPTS" in context
    assert "USER CONTEXT" not in context
    assert "CONVERSATION HISTORY" not in context


def test_build_context_document_truncation():
    """Test build_context truncates documents to 1500 chars in excerpts mode (line 68)"""
    service = ReasoningEngineService(prompt_builder=DummyPromptBuilder())
    long_doc = "x" * 2000  # Longer than 1500
    context = service.build_context([long_doc], use_full_docs=False)
    assert "RELEVANT DOCUMENT EXCERPTS" in context
    assert "Document 1:" in context
    # Check that it's truncated with "..."
    assert "..." in context.split("Document 1:")[1]


def test_build_context_all_components():
    """Test build_context with all components (full integration)"""
    service = ReasoningEngineService(prompt_builder=DummyPromptBuilder())
    context = service.build_context(
        documents=["doc1", "doc2"],
        user_memory_facts=["fact1", "fact2"],
        conversation_history=[
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ],
        use_full_docs=True,
    )
    assert "FULL DOCUMENT CONTEXT" in context
    assert "fact1" in context
    assert "fact2" in context
    assert "User: hello" in context
    assert "Zantara: hi" in context
