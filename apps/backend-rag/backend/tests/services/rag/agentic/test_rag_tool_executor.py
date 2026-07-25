from types import SimpleNamespace
from typing import Any

import pytest

from backend.services.agents.confirmation_service import (
    ConfirmationRedisDown,
    ConfirmationTimeout,
)
from backend.services.agents.tool_authorizer import SENSITIVE_TOOLS
from backend.services.rag.agentic import tool_executor

# Deny-narration fix (P0-DENY, 2026-07-25): a sentinel standing in for "a
# real, authenticated AgentRole" wherever a test needs to simulate the
# *with-principal* audience. The fakes below don't consult its attributes —
# only its identity (`is None` vs not) — so any non-None object does the job.
A_PRINCIPAL = SimpleNamespace(role_id="visa_specialist")


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
    def __init__(self, deny_reason: str = "role not allowed") -> None:
        super().__init__()
        self.deny_reason = deny_reason

    async def authorize(self, **kwargs: Any) -> SimpleNamespace:
        await super().authorize(**kwargs)
        return SimpleNamespace(
            is_denied=True,
            needs_confirmation=False,
            reason=self.deny_reason,
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


class RaisingConfirmationService:
    """Fake confirmation service that raises instead of resolving —
    exercises the ConfirmationRedisDown / ConfirmationTimeout denial paths."""

    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.calls: list[dict[str, Any]] = []

    async def request_and_wait(self, **kwargs: Any) -> bool:
        self.calls.append(kwargs)
        raise self.exc


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
    """INNOCENCE 1 (P0-DENY): a real `agent_role` (authenticated/team
    caller) still gets today's informative reason, byte-identical. In the
    real ToolAuthorizer this "role not allowed" verdict is only reachable
    once `agent_role is not None` (the legacy-passthrough branch returns
    ALLOWED before ever reaching the allowlist check) — so this test now
    passes a principal to match reality."""
    tool = FakeTool()
    tool_executor.configure_tool_executor(DenyAuthorizer())

    result, _duration = await tool_executor.execute_tool(
        tool_map={"admin_tool": tool},
        tool_name="admin_tool",
        arguments={"target": "client"},
        agent_role=A_PRINCIPAL,
    )

    assert result == "Tool execution denied: role not allowed"
    assert tool.calls == []
    assert reset_tool_executor.calls == [("admin_tool", "denied")]


@pytest.mark.asyncio
async def test_execute_tool_denies_anonymous_caller_with_neutral_observation(
    reset_tool_executor: FakeMetricsCollector,
) -> None:
    """GUILT (P0-DENY): a no-principal caller (`agent_role=None` — client,
    unknown WA sender, public /stream) asking for a SENSITIVE_TOOLS-style
    tool gets a neutral, non-diagnostic observation. It must not name the
    tool's internal semantics, and must not contain any of the words that
    would let the LLM narrate "there's a CRM/database and a permission
    control blocked you" back to an untrusted stranger — this is the exact
    live-production leak this fix closes."""
    tool = FakeTool()
    tool_executor.configure_tool_executor(
        DenyAuthorizer(deny_reason="This action needs an authenticated Bali Zero staff account."),
    )

    result, _duration = await tool_executor.execute_tool(
        tool_map={"crm_query": tool},
        tool_name="crm_query",
        arguments={"query": "quanti clienti attivi abbiamo adesso?"},
        agent_role=None,
    )

    lowered = result.lower()
    for forbidden in ("crm_query", "denied", "permission", "authoriz", "crm", "database"):
        assert forbidden not in lowered, f"leaked {forbidden!r} in anonymous denial: {result!r}"
    assert tool.calls == []
    assert reset_tool_executor.calls == [("crm_query", "denied")]


@pytest.mark.asyncio
async def test_execute_tool_denies_anonymous_caller_logs_full_reason_pii_free(
    reset_tool_executor: FakeMetricsCollector,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """P0-DENY audit restore: the client-facing observation for a
    no-principal caller is neutral (see the GUILT test above), but the
    denial reason must still be recoverable server-side for security
    review — this is the audit trail the fix must not remove along with
    the narration leak. GUILT: the reason text IS present in the log.
    INNOCENCE: the WhatsApp-shaped `user_id` (`whatsapp_<phone>`, PII under
    UU PDP / SYMBIOSIS Law 2) never reaches the log line, mirroring the
    `no @ / no phone` contract already enforced for the team-principal
    lane's degrade logs."""
    tool = FakeTool()
    tool_executor.configure_tool_executor(
        DenyAuthorizer(deny_reason="This action needs an authenticated Bali Zero staff account."),
    )

    with caplog.at_level("WARNING", logger="backend.services.rag.agentic.tool_executor"):
        result, _duration = await tool_executor.execute_tool(
            tool_map={"crm_query": tool},
            tool_name="crm_query",
            arguments={"query": "quanti clienti attivi abbiamo adesso?"},
            user_id="whatsapp_+6281234567890",
            agent_role=None,
        )

    # Client-facing string stays neutral (unchanged by this test's scope).
    assert "authenticated Bali Zero staff account" not in result

    records = [r for r in caplog.records if "tool_authz" in r.getMessage()]
    assert records, "expected a tool_authz audit line for the denied call"
    msg = records[-1].getMessage()
    assert "This action needs an authenticated Bali Zero staff account." in msg
    assert "crm_query" in msg
    assert "principal_present=False" in msg
    assert "@" not in msg
    assert "6281234567890" not in msg
    assert "whatsapp_" not in msg


@pytest.mark.asyncio
async def test_execute_tool_fails_closed_when_confirmation_service_missing(
    reset_tool_executor: FakeMetricsCollector,
) -> None:
    """With a real principal, the confirmation-unavailable reason stays
    exactly as informative as before (INNOCENCE-adjacent — this path is
    only reachable with `agent_role is not None` in the real authorizer,
    since NEEDS_CONFIRMATION requires a resolved AgentRole)."""
    tool_executor.configure_tool_executor(ConfirmAuthorizer(), confirmation_service=None)

    result, _duration = await tool_executor.execute_tool(
        tool_map={"dangerous": FakeTool()},
        tool_name="dangerous",
        arguments={"target": "client"},
        agent_role=A_PRINCIPAL,
    )

    assert "confirmation service unavailable" in result
    assert reset_tool_executor.calls == [("dangerous", "denied")]


@pytest.mark.asyncio
async def test_execute_tool_confirmation_unavailable_anonymous_caller_is_neutral(
    reset_tool_executor: FakeMetricsCollector,
) -> None:
    """COVERAGE (P0-DENY): the confirmation-service-unavailable fallback is
    itself audience-aware, defense-in-depth, even though the real
    ToolAuthorizer never produces NEEDS_CONFIRMATION for `agent_role=None`
    today — a future code path must not silently regain the leak."""
    tool_executor.configure_tool_executor(ConfirmAuthorizer(), confirmation_service=None)

    result, _duration = await tool_executor.execute_tool(
        tool_map={"dangerous": FakeTool()},
        tool_name="dangerous",
        arguments={"target": "client"},
        agent_role=None,
    )

    assert "confirmation service unavailable" not in result
    assert "denied" not in result.lower()
    assert reset_tool_executor.calls == [("dangerous", "denied")]


@pytest.mark.asyncio
async def test_execute_tool_confirmation_redis_down_audience_aware(
    reset_tool_executor: FakeMetricsCollector,
) -> None:
    """COVERAGE: ConfirmationRedisDown denial — principal gets the
    informative message, anonymous gets the neutral one."""
    tool_executor.configure_tool_executor(
        ConfirmAuthorizer(),
        confirmation_service=RaisingConfirmationService(ConfirmationRedisDown("down")),
    )

    result_principal, _ = await tool_executor.execute_tool(
        tool_map={"dangerous": FakeTool()},
        tool_name="dangerous",
        arguments={"target": "client"},
        agent_role=A_PRINCIPAL,
    )
    assert "confirmation system unavailable" in result_principal
    assert "Redis down" in result_principal

    result_anonymous, _ = await tool_executor.execute_tool(
        tool_map={"dangerous": FakeTool()},
        tool_name="dangerous",
        arguments={"target": "client"},
        agent_role=None,
    )
    assert "redis" not in result_anonymous.lower()
    assert "denied" not in result_anonymous.lower()

    assert reset_tool_executor.calls == [
        ("dangerous", "denied"),
        ("dangerous", "denied"),
    ]


@pytest.mark.asyncio
async def test_execute_tool_confirmation_timeout_audience_aware(
    reset_tool_executor: FakeMetricsCollector,
) -> None:
    """COVERAGE: ConfirmationTimeout denial — principal gets the
    informative message, anonymous gets the neutral one."""
    tool_executor.configure_tool_executor(
        ConfirmAuthorizer(),
        confirmation_service=RaisingConfirmationService(ConfirmationTimeout("timed out")),
    )

    result_principal, _ = await tool_executor.execute_tool(
        tool_map={"dangerous": FakeTool()},
        tool_name="dangerous",
        arguments={"target": "client"},
        agent_role=A_PRINCIPAL,
    )
    assert "did not confirm" in result_principal

    result_anonymous, _ = await tool_executor.execute_tool(
        tool_map={"dangerous": FakeTool()},
        tool_name="dangerous",
        arguments={"target": "client"},
        agent_role=None,
    )
    assert "confirm" not in result_anonymous.lower()
    assert "denied" not in result_anonymous.lower()

    assert reset_tool_executor.calls == [
        ("dangerous", "timeout"),
        ("dangerous", "timeout"),
    ]


@pytest.mark.asyncio
async def test_execute_tool_confirmation_rejected_audience_aware(
    reset_tool_executor: FakeMetricsCollector,
) -> None:
    """COVERAGE: user-rejected-confirmation denial — principal gets the
    informative message, anonymous gets the neutral one."""
    tool_executor.configure_tool_executor(
        ConfirmAuthorizer(),
        confirmation_service=FakeConfirmationService(approved=False),
    )

    result_principal, _ = await tool_executor.execute_tool(
        tool_map={"dangerous": FakeTool()},
        tool_name="dangerous",
        arguments={"target": "client"},
        agent_role=A_PRINCIPAL,
    )
    assert "user rejected" in result_principal

    result_anonymous, _ = await tool_executor.execute_tool(
        tool_map={"dangerous": FakeTool()},
        tool_name="dangerous",
        arguments={"target": "client"},
        agent_role=None,
    )
    assert "rejected" not in result_anonymous.lower()
    assert "denied" not in result_anonymous.lower()

    assert reset_tool_executor.calls == [
        ("dangerous", "rejected"),
        ("dangerous", "rejected"),
    ]


@pytest.mark.asyncio
async def test_execute_tool_allowed_path_unaffected_by_agent_role(
    reset_tool_executor: FakeMetricsCollector,
) -> None:
    """INNOCENCE 2 (P0-DENY): the allow/deny decision set is untouched by
    this fix — only the DENIAL string changes. Parameterised over
    SENSITIVE_TOOLS names plus a normal tool: for an ALLOWED verdict (the
    authorizer's call, unaffected by this change), execution proceeds and
    returns the tool's real result regardless of `agent_role`."""
    for tool_name in (*sorted(SENSITIVE_TOOLS), "vector_search"):
        for agent_role in (None, A_PRINCIPAL):
            authorizer = AllowAuthorizer()
            tool_executor.configure_tool_executor(authorizer)
            tool = FakeTool(result=f"ok:{tool_name}")

            result, _duration = await tool_executor.execute_tool(
                tool_map={tool_name: tool},
                tool_name=tool_name,
                arguments={"query": "hello"},
                agent_role=agent_role,
            )

            assert result == f"ok:{tool_name}"
            assert tool.calls == [{"query": "hello"}]
            assert authorizer.calls[0]["agent_role"] is agent_role


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
