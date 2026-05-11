"""Unit tests for backend.agents.agents.multi_ai_orchestrator."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from backend.agents.agents import multi_ai_orchestrator as module
from backend.agents.services.multi_ai_adapter import AIRequest, AIResponse, AITool, TaskType


class RecordingMultiAI:
    def __init__(self, response: AIResponse | Exception | None = None) -> None:
        self.response = response or AIResponse(text="generated", tool_used=AITool.CLAUDE)
        self.requests: list[AIRequest] = []
        self.available_tools_called = False

    def get_available_tools(self) -> list[AITool]:
        self.available_tools_called = True
        return [AITool.CLAUDE]

    async def generate(self, request: AIRequest) -> AIResponse:
        self.requests.append(request)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.fixture
def fake_multi_ai() -> RecordingMultiAI:
    return RecordingMultiAI(AIResponse(text="ok", tool_used=AITool.GEMINI))


@pytest.fixture
def orchestrator(fake_multi_ai: RecordingMultiAI) -> module.MultiAIOrchestrator:
    with patch.object(module, "get_multi_ai_adapter", return_value=fake_multi_ai):
        return module.MultiAIOrchestrator(Path("/tmp/project"))


def test_init_uses_adapter_factory(fake_multi_ai: RecordingMultiAI) -> None:
    with patch.object(module, "get_multi_ai_adapter", return_value=fake_multi_ai) as factory:
        orchestrator = module.MultiAIOrchestrator(Path("/tmp/project"))

    factory.assert_called_once_with()
    assert orchestrator.project_root == Path("/tmp/project")
    assert orchestrator.multi_ai is fake_multi_ai
    assert fake_multi_ai.available_tools_called is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "args", "task_type", "prompt_parts"),
    [
        ("generate_test", ("src/example.py", "def answer() -> int:\n    return 42"), TaskType.TEST_GENERATION, ["Generate comprehensive pytest test", "src/example.py", "99%+ coverage"]),
        ("refactor_code", ("src/example.py", "x=1", "improve readability"), TaskType.REFACTORING, ["Refactor this code to: improve readability", "src/example.py", "Return ONLY code"]),
        ("generate_documentation", ("src/example.py", "class Example:\n    pass"), TaskType.DOCUMENTATION, ["Generate comprehensive documentation", "Usage examples", "src/example.py"]),
    ],
)
async def test_text_methods_build_expected_ai_request(
    orchestrator: module.MultiAIOrchestrator,
    fake_multi_ai: RecordingMultiAI,
    method_name: str,
    args: tuple[str, ...],
    task_type: TaskType,
    prompt_parts: list[str],
) -> None:
    result = await getattr(orchestrator, method_name)(*args)

    assert result == "ok"
    assert len(fake_multi_ai.requests) == 1
    request = fake_multi_ai.requests[0]
    assert request.task_type is task_type
    assert request.context is None
    assert request.files is None
    assert request.preferred_tool is None
    for part in prompt_parts:
        assert part in request.prompt


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "args", "task_type", "response_key", "prompt_parts"),
    [
        ("analyze_code", ("src/example.py", "def bad(): pass"), TaskType.CODE_ANALYSIS, "analysis", ["Code quality assessment", "Security concerns", "src/example.py"]),
        ("design_architecture", ("Billing", "needs audit log"), TaskType.ARCHITECTURE, "architecture", ["Design architecture for: Billing", "needs audit log", "Implementation plan"]),
        ("review_code", ("src/example.py", "def risky(): pass"), TaskType.CODE_REVIEW, "review", ["Perform code review", "Security vulnerabilities", "src/example.py"]),
    ],
)
async def test_dict_methods_return_payload_with_tool_used(
    orchestrator: module.MultiAIOrchestrator,
    fake_multi_ai: RecordingMultiAI,
    method_name: str,
    args: tuple[str, ...],
    task_type: TaskType,
    response_key: str,
    prompt_parts: list[str],
) -> None:
    result = await getattr(orchestrator, method_name)(*args)

    assert result == {response_key: "ok", "tool_used": AITool.GEMINI.value}
    request = fake_multi_ai.requests[0]
    assert request.task_type is task_type
    for part in prompt_parts:
        assert part in request.prompt


@pytest.mark.asyncio
async def test_generate_error_propagates_after_building_request() -> None:
    fake_multi_ai = RecordingMultiAI(RuntimeError("provider down"))
    with patch.object(module, "get_multi_ai_adapter", return_value=fake_multi_ai):
        orchestrator = module.MultiAIOrchestrator(Path("/tmp/project"))

    with pytest.raises(RuntimeError, match="provider down"):
        await orchestrator.analyze_code("src/example.py", "broken")

    assert fake_multi_ai.requests[0].task_type is TaskType.CODE_ANALYSIS


class StubCLIOrchestrator:
    instances: list[StubCLIOrchestrator] = []

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.instances.append(self)

    def __getattr__(self, name: str) -> Any:
        async def _called(*args: Any) -> str:
            self.calls.append((name, args))
            return "unexpected call"

        return _called


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["prog", "--task", "test"], "--file and --code required for test generation"),
        (["prog", "--task", "analyze"], "--file and --code required for analysis"),
        (["prog", "--task", "architecture"], "--code (requirements) required"),
        (["prog", "--task", "refactor"], "--file and --code required"),
        (["prog", "--task", "docs"], "--file and --code required"),
        (["prog", "--task", "review"], "--file and --code required"),
    ],
)
async def test_main_returns_early_when_required_args_missing(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    argv: list[str],
    message: str,
) -> None:
    StubCLIOrchestrator.instances.clear()
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(module, "MultiAIOrchestrator", StubCLIOrchestrator)

    with caplog.at_level("INFO"):
        await module.main()

    assert message in caplog.text
    assert StubCLIOrchestrator.instances[0].calls == []


@pytest.mark.asyncio
async def test_main_catches_and_logs_orchestrator_errors(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class FailingOrchestrator(StubCLIOrchestrator):
        async def review_code(self, file_path: str, code: str) -> dict[str, Any]:
            raise RuntimeError("review exploded")

    monkeypatch.setattr(
        sys,
        "argv",
        ["prog", "--task", "review", "--file", "src/example.py", "--code", "code"],
    )
    monkeypatch.setattr(module, "MultiAIOrchestrator", FailingOrchestrator)

    with patch("traceback.print_exc", MagicMock()) as print_exc, caplog.at_level("ERROR"):
        await module.main()

    assert "review exploded" in caplog.text
    print_exc.assert_called_once_with()
