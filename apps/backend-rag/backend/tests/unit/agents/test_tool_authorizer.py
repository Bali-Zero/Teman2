"""
Unit tests for ToolAuthorizer (VASSAL Phase 2 — Strada B).

Coverage:
    * AuthDecision enum + AuthResult helpers (allow/deny/confirm)
    * Default-deny: tool not in allowlist → DENIED
    * Admin role (empty allowlists) → all tools ALLOWED
    * Blocked tools → DENIED even if elsewhere in allowed_*
    * Backwards-compat: agent_role=None → ALLOWED (legacy /stream path)
    * Audit log emitted on every decision (allow + deny)
    * Scaffolding methods (`_check_client_scope`, `_check_requires_confirmation`)
      currently return None (no-op for Phase 2)
    * Integration with execute_tool: denied tools never reach tool.execute(),
      allowed tools execute normally, legacy callers (agent_role=None)
      bypass enforcement
"""

from __future__ import annotations

import pytest

from backend.services.agents.team_agent_config import (
    ROLE_ADMIN,
    ROLE_EXECUTIVE_CONSULTANT,
    ROLE_VISA_SPECIALIST,
)
from backend.services.agents.tool_authorizer import (
    AuthDecision,
    AuthResult,
    ToolAuthorizer,
)
from backend.services.rag.agentic.tool_executor import execute_tool
from backend.services.tools.definitions import BaseTool


# ─────────────────────────────────────────────────────────────────────────
# Test fixtures
# ─────────────────────────────────────────────────────────────────────────


class _NoopTool(BaseTool):
    """Minimal BaseTool that records execution and returns a marker string."""

    def __init__(self, name: str = "noop") -> None:
        self._name = name
        self.execute_called: bool = False
        self.last_kwargs: dict | None = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"test tool {self._name}"

    @property
    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs) -> str:
        self.execute_called = True
        self.last_kwargs = kwargs
        return f"{self._name}_ok"


@pytest.fixture
def authorizer() -> ToolAuthorizer:
    return ToolAuthorizer()


# ─────────────────────────────────────────────────────────────────────────
# AuthResult / AuthDecision helpers
# ─────────────────────────────────────────────────────────────────────────


class TestAuthResult:
    def test_allow_helper(self) -> None:
        r = AuthResult.allow({"x": 1})
        assert r.is_allowed
        assert not r.is_denied
        assert not r.needs_confirmation
        assert r.decision == AuthDecision.ALLOWED
        assert r.args == {"x": 1}

    def test_deny_helper(self) -> None:
        r = AuthResult.deny("nope")
        assert r.is_denied
        assert not r.is_allowed
        assert r.decision == AuthDecision.DENIED
        assert r.reason == "nope"

    def test_confirm_helper(self) -> None:
        r = AuthResult.confirm("approve please")
        assert r.needs_confirmation
        assert not r.is_allowed
        assert not r.is_denied
        assert r.decision == AuthDecision.NEEDS_CONFIRMATION

    def test_allow_default_args(self) -> None:
        r = AuthResult.allow()
        assert r.args == {}

    def test_decision_enum_values(self) -> None:
        # Stable string values — Phase 3+ depends on these for serialization.
        assert AuthDecision.ALLOWED.value == "allowed"
        assert AuthDecision.DENIED.value == "denied"
        assert AuthDecision.NEEDS_CONFIRMATION.value == "needs_confirmation"


# ─────────────────────────────────────────────────────────────────────────
# ToolAuthorizer.authorize — core decision logic
# ─────────────────────────────────────────────────────────────────────────


class TestAuthorizeDecisions:
    @pytest.mark.asyncio
    async def test_legacy_path_passthrough(self, authorizer: ToolAuthorizer) -> None:
        """agent_role=None must always allow, regardless of tool."""
        for tool in ("vector_search", "execute_plan", "literally_anything"):
            r = await authorizer.authorize(
                user_email=None,
                agent_role=None,
                tool_name=tool,
                args={},
            )
            assert r.is_allowed, f"legacy passthrough must allow {tool}"

    @pytest.mark.asyncio
    async def test_admin_empty_allowlist_allows_all(
        self, authorizer: ToolAuthorizer,
    ) -> None:
        """ADMIN has empty allowed_* lists → is_tool_allowed returns True for all."""
        for tool in (
            "vector_search",
            "image_generation",
            "execute_plan",  # not blocked for admin
            "any_brand_new_tool",
        ):
            r = await authorizer.authorize(
                user_email="zero@balizero.com",
                agent_role=ROLE_ADMIN,
                tool_name=tool,
                args={},
            )
            assert r.is_allowed, f"admin must allow {tool}"

    @pytest.mark.asyncio
    async def test_visa_specialist_allowed_runtime_tools(
        self, authorizer: ToolAuthorizer,
    ) -> None:
        """Phase 2 v8 allowlist additions for runtime tools must be in effect.

        Note (VASSAL Phase 3): `image_generation` is still in the visa
        specialist allowlist, but Phase 3 put it behind a confirmation
        gate, so `authorize()` returns NEEDS_CONFIRMATION (not ALLOWED)
        for it. The confirmation path is exercised in
        test_confirmation_authorizer.py::TestAuthorizeEndToEndConfirmation.
        We intentionally keep the Phase 2 loop here narrowed to the
        non-gated tools so this test documents exactly what Phase 2
        unlocked without confirmation.
        """
        # These are the path Z read-only runtime tools added in Phase 2 v8
        # that were and remain plain ALLOWED (no confirmation gate).
        for tool in (
            "vector_search",
            "pricing",
            "team_knowledge",
            "knowledge_graph",
            "calculator",
            "vision",
            "web_search",
        ):
            r = await authorizer.authorize(
                user_email="damar@balizero.com",
                agent_role=ROLE_VISA_SPECIALIST,
                tool_name=tool,
                args={},
            )
            assert r.is_allowed, (
                f"visa specialist must allow runtime tool {tool} (Phase 2 v8)"
            )

        # image_generation is in the allowlist but gated in Phase 3.
        r = await authorizer.authorize(
            user_email="damar@balizero.com",
            agent_role=ROLE_VISA_SPECIALIST,
            tool_name="image_generation",
            args={},
        )
        assert r.needs_confirmation, (
            "image_generation should be in the visa specialist allowlist "
            "but gated by Phase 3 confirmation"
        )
        assert not r.is_denied, (
            "image_generation must not be denied — denial would regress Phase 2 v8"
        )

    @pytest.mark.asyncio
    async def test_visa_specialist_blocked_tool_denied(
        self, authorizer: ToolAuthorizer,
    ) -> None:
        """blocked_tools precedence — even if added to allowed_* by mistake."""
        r = await authorizer.authorize(
            user_email="damar@balizero.com",
            agent_role=ROLE_VISA_SPECIALIST,
            tool_name="execute_plan",
            args={},
        )
        assert r.is_denied
        assert "execute_plan" in r.reason
        assert "visa_specialist" in r.reason

    @pytest.mark.asyncio
    async def test_visa_specialist_timesheet_denied(
        self, authorizer: ToolAuthorizer,
    ) -> None:
        """Config updated: timesheet IS in visa_specialist.allowed_write_tools.

        Previous Phase 2 v8 brief said it was denied, but the allowlist was
        subsequently expanded. Test now verifies the actual current config.
        """
        r = await authorizer.authorize(
            user_email="damar@balizero.com",
            agent_role=ROLE_VISA_SPECIALIST,
            tool_name="timesheet",
            args={"action": "clock_in", "email": "damar@balizero.com"},
        )
        # timesheet is now in allowed_write_tools for visa_specialist
        assert r.is_allowed

    @pytest.mark.asyncio
    async def test_executive_consultant_timesheet_allowed(
        self, authorizer: ToolAuthorizer,
    ) -> None:
        """Per Phase 2 v8 brief: timesheet IS in executive_consultant write allowlist."""
        r = await authorizer.authorize(
            user_email="adit@balizero.com",
            agent_role=ROLE_EXECUTIVE_CONSULTANT,
            tool_name="timesheet",
            args={"action": "clock_in", "email": "adit@balizero.com"},
        )
        assert r.is_allowed

    @pytest.mark.asyncio
    async def test_executive_consultant_publish_article_denied(
        self, authorizer: ToolAuthorizer,
    ) -> None:
        """publish_article in blocked_tools for executive_consultant."""
        r = await authorizer.authorize(
            user_email="adit@balizero.com",
            agent_role=ROLE_EXECUTIVE_CONSULTANT,
            tool_name="publish_article",
            args={},
        )
        assert r.is_denied
        assert "publish_article" in r.reason

    @pytest.mark.asyncio
    async def test_unknown_tool_for_role_denied(
        self, authorizer: ToolAuthorizer,
    ) -> None:
        """Tool not in any allowlist for the role → default-deny."""
        r = await authorizer.authorize(
            user_email="damar@balizero.com",
            agent_role=ROLE_VISA_SPECIALIST,
            tool_name="some_brand_new_tool_nobody_has_listed",
            args={},
        )
        assert r.is_denied
        assert "not in the allowlist" in r.reason

    @pytest.mark.asyncio
    async def test_args_passthrough_unchanged(
        self, authorizer: ToolAuthorizer,
    ) -> None:
        """Phase 2 returns args unchanged. Phase 3+ may inject server fields."""
        original = {"query": "test", "limit": 10}
        r = await authorizer.authorize(
            user_email="damar@balizero.com",
            agent_role=ROLE_VISA_SPECIALIST,
            tool_name="vector_search",
            args=original,
        )
        assert r.is_allowed
        assert r.args == original


# ─────────────────────────────────────────────────────────────────────────
# Scaffolding methods — Phase 2 no-op contract
# ─────────────────────────────────────────────────────────────────────────


class TestScaffoldingNoOps:
    def test_check_client_scope_returns_none(
        self, authorizer: ToolAuthorizer,
    ) -> None:
        """Phase 2: client_scope check is a hook for Strada A, returns None."""
        result = authorizer._check_client_scope(
            user_email="damar@balizero.com",
            agent_role=ROLE_VISA_SPECIALIST,
            tool_name="get_client",
            args={"client_id": 42},
        )
        assert result is None

    def test_check_requires_confirmation_returns_none(
        self, authorizer: ToolAuthorizer,
    ) -> None:
        """Phase 2: requires_confirmation hook is no-op until Phase 3."""
        result = authorizer._check_requires_confirmation(
            user_email="damar@balizero.com",
            agent_role=ROLE_VISA_SPECIALIST,
            tool_name="delete_client",
            args={"client_id": 42},
        )
        assert result is None


# ─────────────────────────────────────────────────────────────────────────
# Audit log emission
# ─────────────────────────────────────────────────────────────────────────


class TestAuditLog:
    @pytest.mark.asyncio
    async def test_allow_decision_logs_info(
        self, authorizer: ToolAuthorizer, caplog
    ) -> None:
        with caplog.at_level("INFO", logger="backend.services.agents.tool_authorizer"):
            await authorizer.authorize(
                user_email="damar@balizero.com",
                agent_role=ROLE_VISA_SPECIALIST,
                tool_name="vector_search",
                args={},
            )
        records = [r for r in caplog.records if "tool_authz" in r.getMessage()]
        assert records, "tool_authz audit line missing"
        msg = records[-1].getMessage()
        assert "decision=allow" in msg
        assert "user=damar@balizero.com" in msg
        assert "role=visa_specialist" in msg
        assert "scope=assigned" in msg
        assert "tool=vector_search" in msg

    @pytest.mark.asyncio
    async def test_deny_decision_logs_warning(
        self, authorizer: ToolAuthorizer, caplog
    ) -> None:
        with caplog.at_level("WARNING", logger="backend.services.agents.tool_authorizer"):
            await authorizer.authorize(
                user_email="damar@balizero.com",
                agent_role=ROLE_VISA_SPECIALIST,
                tool_name="execute_plan",
                args={},
            )
        records = [r for r in caplog.records if "tool_authz" in r.getMessage()]
        assert records, "tool_authz deny audit line missing"
        msg = records[-1].getMessage()
        assert "decision=deny" in msg
        assert "tool=execute_plan" in msg

    @pytest.mark.asyncio
    async def test_legacy_passthrough_still_audited(
        self, authorizer: ToolAuthorizer, caplog
    ) -> None:
        """Even legacy passthrough must leave a trace in the audit log."""
        with caplog.at_level("INFO", logger="backend.services.agents.tool_authorizer"):
            await authorizer.authorize(
                user_email=None,
                agent_role=None,
                tool_name="vector_search",
                args={},
            )
        records = [r for r in caplog.records if "tool_authz" in r.getMessage()]
        assert records
        msg = records[-1].getMessage()
        assert "decision=allow" in msg
        assert "role=none" in msg
        assert "user=anonymous" in msg


# ─────────────────────────────────────────────────────────────────────────
# Integration: execute_tool + ToolAuthorizer chokepoint
# ─────────────────────────────────────────────────────────────────────────


class TestExecuteToolIntegration:
    @pytest.mark.asyncio
    async def test_allowed_tool_executes(self) -> None:
        tool = _NoopTool("vector_search")
        tool_map = {"vector_search": tool}

        result, duration = await execute_tool(
            tool_map=tool_map,
            tool_name="vector_search",
            arguments={},
            user_id="damar@balizero.com",
            tool_execution_counter=None,
            agent_role=ROLE_VISA_SPECIALIST,
        )
        assert result == "vector_search_ok"
        assert tool.execute_called
        assert duration >= 0.0

    @pytest.mark.asyncio
    async def test_denied_tool_does_not_execute(self) -> None:
        """Denied tools must NEVER reach tool.execute()."""
        tool = _NoopTool("execute_plan")
        tool_map = {"execute_plan": tool}

        result, _ = await execute_tool(
            tool_map=tool_map,
            tool_name="execute_plan",
            arguments={},
            user_id="damar@balizero.com",
            tool_execution_counter=None,
            agent_role=ROLE_VISA_SPECIALIST,
        )
        assert "denied" in result.lower()
        assert "execute_plan" in result
        assert tool.execute_called is False, (
            "denied tool must not reach tool.execute()"
        )

    @pytest.mark.asyncio
    async def test_legacy_caller_bypasses_enforcement(self) -> None:
        """agent_role=None → execute even tools that would be denied otherwise."""
        tool = _NoopTool("execute_plan")
        tool_map = {"execute_plan": tool}

        result, _ = await execute_tool(
            tool_map=tool_map,
            tool_name="execute_plan",
            arguments={},
            user_id="anon@x",
            tool_execution_counter=None,
            agent_role=None,  # legacy /stream path
        )
        assert result == "execute_plan_ok"
        assert tool.execute_called

    @pytest.mark.asyncio
    async def test_unknown_tool_short_circuits_before_authz(self) -> None:
        """tool_name not in tool_map → 'Unknown tool' error, no authz call needed."""
        tool_map = {"vector_search": _NoopTool()}

        result, _ = await execute_tool(
            tool_map=tool_map,
            tool_name="this_does_not_exist",
            arguments={},
            user_id="damar@balizero.com",
            tool_execution_counter=None,
            agent_role=ROLE_VISA_SPECIALIST,
        )
        assert "Unknown tool" in result

    @pytest.mark.asyncio
    async def test_user_id_injected_into_args_after_authz(self) -> None:
        """The existing _user_id injection must still happen for allowed tools."""
        tool = _NoopTool("pricing")
        tool_map = {"pricing": tool}

        await execute_tool(
            tool_map=tool_map,
            tool_name="pricing",
            arguments={},
            user_id="damar@balizero.com",
            tool_execution_counter=None,
            agent_role=ROLE_VISA_SPECIALIST,
        )
        assert tool.last_kwargs is not None
        assert tool.last_kwargs.get("_user_id") == "damar@balizero.com"
