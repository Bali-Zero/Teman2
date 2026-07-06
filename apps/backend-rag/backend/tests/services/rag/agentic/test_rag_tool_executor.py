from types import SimpleNamespace
from typing import Any

import pytest

from backend.services.rag.agentic import tool_executor


class FakeMetricsCollector:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def record_tool_call(self, tool_name: str, status: str) -> None:
        self.calls.append((tool_name, status))


class AllowAuthorizer:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def authorize(
        self,
        *,
        user_email: str | None,
        agent_role: Any,
        tool_name: str,
        args: dict[str, Any],
    ) -> SimpleNamespace:
        self.calls.append(
            {
                "user_email": user_email,
                "agent_role": agent_role,
                "tool_name": tool_name,
                "args": args.copy(),
            },
        )
        return SimpleNamespace(
            is_denied=False,
            needs_confirmation=False,
            reason=None,
            args=args.copy(),
        )


class DenyAuthorizer(AllowAuthorizer):
    async def authorize(self, **kwargs: Any) -> SimpleNamespace:
        await super().authorize(**kwargs)
        return SimpleNamespace(
            is_denied=True,
            needs_confirmation=False,
            reason="role not allowed",
            args=kwargs["args"],
        )


class ConfirmAuthorizer(AllowAuthorizer):
    async def authorize(self, **kwargs: Any) -> SimpleNamespace:
        await super().authorize(**kwargs)
        return SimpleNamespace(
            is_denied=False,
            needs_confirmation=True,
            reason="preview before action",
            args=kwargs["args"].copy(),
        )


class FakeTool:
    def __init__(self, result: str = "ok") -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    async def execute(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        return self.result


class FakeConfirmationService:
    def __init__(self, approved: bool) -> None:
        self.approved = approved
        self.calls: list[dict[str, Any]] = []

    async def request_and_wait(self, **kwargs: Any) -> bool:
        self.calls.append(kwargs)
        return self.approved


@pytest.fixture(autouse=True)
def reset_tool_executor(monkeypatch: pytest.MonkeyPatch) -> FakeMetricsCollector:
    metrics = FakeMetricsCollector()
    monkeypatch.setattr(tool_executor, "metrics_collector", metrics)
    tool_executor.configure_tool_executor(AllowAuthorizer(), confirmation_service=None)
    return metrics


def test_parse_native_function_call_returns_tool_call() -> None:
    part = SimpleNamespace(
        function_call=SimpleNamespace(
            name="vector_search",
            args={"query": "KITAS", "collection": "visa_oracle"},
        ),
    )

    call = tool_executor.parse_native_function_call(part)

    assert call is not None
    assert call.tool_name == "vector_search"
    assert call.arguments == {"query": "KITAS", "collection": "visa_oracle"}


def test_parse_tool_call_regex_handles_key_value_and_single_expression() -> None:
    search_call = tool_executor.parse_tool_call_regex(
        'ACTION: vector_search(query="visa requirements", collection="visa_oracle")',
    )
    calc_call = tool_executor.parse_tool_call_regex('ACTION: calculator("1000 * 0.22")')

    assert search_call is not None
    assert search_call.arguments == {
        "query": "visa requirements",
        "collection": "visa_oracle",
    }
    assert calc_call is not None
    assert calc_call.arguments == {"expression": "1000 * 0.22"}


@pytest.mark.asyncio
async def test_execute_tool_short_circuits_unknown_before_authorization(
    reset_tool_executor: FakeMetricsCollector,
) -> None:
    authorizer = AllowAuthorizer()
    tool_executor.configure_tool_executor(authorizer)

    result, _duration = await tool_executor.execute_tool(
        tool_map={},
        tool_name="missing",
        arguments={},
        user_id="owner@example.test",
    )

    assert result == "Error: Unknown tool 'missing'"
    assert authorizer.calls == []
    assert reset_tool_executor.calls == [("missing", "unknown")]


@pytest.mark.asyncio
async def test_execute_tool_authorizes_then_injects_user_id() -> None:
    authorizer = AllowAuthorizer()
    tool_executor.configure_tool_executor(authorizer)
    tool = FakeTool()

    result, duration = await tool_executor.execute_tool(
        tool_map={"safe_tool": tool},
        tool_name="safe_tool",
        arguments={"query": "hello"},
        user_id="owner@example.test",
    )

    assert result == "ok"
    assert duration >= 0
    assert authorizer.calls[0]["args"] == {"query": "hello"}
    assert tool.calls == [{"query": "hello", "_user_id": "owner@example.test"}]


@pytest.mark.asyncio
async def test_execute_tool_denies_without_running_tool(
    reset_tool_executor: FakeMetricsCollector,
) -> None:
    tool = FakeTool()
    tool_executor.configure_tool_executor(DenyAuthorizer())

    result, _duration = await tool_executor.execute_tool(
        tool_map={"admin_tool": tool},
        tool_name="admin_tool",
        arguments={"target": "client"},
    )

    assert result == "Tool execution denied: role not allowed"
    assert tool.calls == []
    assert reset_tool_executor.calls == [("admin_tool", "denied")]


@pytest.mark.asyncio
async def test_execute_tool_fails_closed_when_confirmation_service_missing(
    reset_tool_executor: FakeMetricsCollector,
) -> None:
    tool_executor.configure_tool_executor(ConfirmAuthorizer(), confirmation_service=None)

    result, _duration = await tool_executor.execute_tool(
        tool_map={"dangerous": FakeTool()},
        tool_name="dangerous",
        arguments={"target": "client"},
    )

    assert "confirmation service unavailable" in result
    assert reset_tool_executor.calls == [("dangerous", "denied")]


@pytest.mark.asyncio
async def test_execute_tool_runs_after_user_confirmation(
    reset_tool_executor: FakeMetricsCollector,
) -> None:
    confirmation = FakeConfirmationService(approved=True)
    tool = FakeTool(result="done")
    tool_executor.configure_tool_executor(
        ConfirmAuthorizer(),
        confirmation_service=confirmation,
    )

    result, _duration = await tool_executor.execute_tool(
        tool_map={"dangerous": tool},
        tool_name="dangerous",
        arguments={"target": "client"},
        user_id="owner@example.test",
    )

    assert result == "done"
    assert confirmation.calls[0]["preview"] == "preview before action"
    assert tool.calls == [{"target": "client", "_user_id": "owner@example.test"}]
    assert reset_tool_executor.calls == [("dangerous", "confirmed"), ("dangerous", "success")]


@pytest.mark.asyncio
async def test_execute_tool_enforces_per_query_limit(
    reset_tool_executor: FakeMetricsCollector,
) -> None:
    counter = {"count": 10}

    with pytest.raises(RuntimeError, match="Maximum tool executions exceeded"):
        await tool_executor.execute_tool(
            tool_map={"safe_tool": FakeTool()},
            tool_name="safe_tool",
            arguments={},
            tool_execution_counter=counter,
        )

    assert counter == {"count": 11}
    assert reset_tool_executor.calls == [("safe_tool", "rate_limited")]
