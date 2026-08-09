"""T4 unified principal — end-to-end proof (spec `2026-07-24-zantara-bot-
consultant-assistant-spec.md` §5 item T4 — "two parallel auth systems").

The two halves of the fix are unit-tested separately elsewhere:
    * `_derive_wa_agent_role` (correct mapping) —
      `backend/tests/unit/app/routers/test_agentic_rag_router.py::TestDeriveWaAgentRole`
    * `ToolAuthorizer.authorize` accepting any `AgentRole` (pre-existing,
      untouched by T4) — `test_tool_authorizer.py`

This file composes sender-role derivation with the execution authorizer.
WhatsApp is deliberately L0: a non-None trusted caller_profile always wins
over any derived or conflicting AgentRole and denies all seven internal tools.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.app.routers.agentic_rag import _derive_wa_agent_role
from backend.services.agents.team_agent_config import ROLE_ADMIN, ROLE_EXECUTIVE_CONSULTANT
from backend.services.agents.tool_authorizer import SENSITIVE_TOOLS, ToolAuthorizer
from backend.services.rag.agentic import tool_executor

_WA_INTERNAL_TOOL_NAMES = frozenset(
    {
        "crm_query",
        "timesheet",
        "team_knowledge",
        "team_my_clients",
        "team_my_practices",
        "team_my_deadlines",
        "team_practice_detail",
    }
)

_WA_NON_L0_TOOL_NAMES = _WA_INTERNAL_TOOL_NAMES | frozenset(
    {
        "vision_analysis",
        "generate_image",
        "web_search",
        "knowledge_graph_search",
    }
)


@pytest.fixture
def authorizer() -> ToolAuthorizer:
    return ToolAuthorizer()


class TestWaSenderSensitiveToolEndToEnd:
    """Execution-side tripwire for the WhatsApp L0 capability ceiling."""

    def test_canonical_sensitive_set_contains_all_seven_internal_tools(self) -> None:
        assert SENSITIVE_TOOLS == _WA_INTERNAL_TOOL_NAMES

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tool_name", sorted(SENSITIVE_TOOLS))
    async def test_before_t4_wa_sender_is_denied(
        self, authorizer: ToolAuthorizer, tool_name: str
    ) -> None:
        """Today's behavior (T4 flag off, or before this PR): a WA sender's
        `agent_role` is always None -> every SENSITIVE_TOOLS entry denied."""
        result = await authorizer.authorize(
            user_email=None,
            agent_role=None,
            tool_name=tool_name,
            args={},
            caller_profile=None,
        )
        assert result.is_denied

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tool_name", sorted(SENSITIVE_TOOLS))
    async def test_registered_team_wa_sender_is_denied_even_with_own_role(
        self, authorizer: ToolAuthorizer, tool_name: str
    ) -> None:
        trusted_profile = {
            "role": "team",
            "name": "Adit",
            "email": "adit@balizero.com",
        }
        derived_role = _derive_wa_agent_role(trusted_profile)
        assert derived_role is ROLE_EXECUTIVE_CONSULTANT  # sanity: real scope, not admin

        result = await authorizer.authorize(
            user_email=trusted_profile["email"],
            agent_role=derived_role,
            tool_name=tool_name,
            args={},
            caller_profile=trusted_profile,
        )
        assert result.is_denied

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tool_name", sorted(SENSITIVE_TOOLS))
    async def test_owner_wa_sender_is_denied_even_as_admin(
        self, authorizer: ToolAuthorizer, tool_name: str
    ) -> None:
        profile = {"role": "creator"}
        derived_role = _derive_wa_agent_role(profile)
        assert derived_role is ROLE_ADMIN

        result = await authorizer.authorize(
            user_email=None,
            agent_role=derived_role,
            tool_name=tool_name,
            args={},
            caller_profile=profile,
        )
        assert result.is_denied

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tool_name", sorted(SENSITIVE_TOOLS))
    async def test_workspace_admin_without_wa_profile_remains_rbac_authorized(
        self, authorizer: ToolAuthorizer, tool_name: str
    ) -> None:
        result = await authorizer.authorize(
            user_email="synthetic-admin@example.test",
            agent_role=ROLE_ADMIN,
            tool_name=tool_name,
            args={},
            caller_profile=None,
        )
        assert result.is_allowed

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tool_name", sorted(SENSITIVE_TOOLS))
    async def test_innocence_client_or_unregistered_wa_sender_still_denied(
        self, authorizer: ToolAuthorizer, tool_name: str
    ) -> None:
        """INNOCENCE (the tourniquet must be provably intact): a client
        phone AND a DB-resolved team row with no registered VASSAL role
        both still derive `agent_role=None` -> still hard-denied. This is
        the exact regression PR #2962/#3062 fixed after real PII exposure —
        proof it did not come back."""
        for trusted_profile in (
            {"role": "client", "client_id": 1},
            {"role": "unknown"},
            {"role": "team", "name": "Ghost", "email": "ghost@balizero.com"},
            None,
        ):
            derived_role = _derive_wa_agent_role(trusted_profile)
            assert derived_role is None

            result = await authorizer.authorize(
                user_email=None,
                agent_role=derived_role,
                tool_name=tool_name,
                args={},
                caller_profile=trusted_profile,
            )
            assert result.is_denied


class _NeverExecuteTool:
    def __init__(self) -> None:
        self.called = False

    async def execute(self, **_kwargs) -> str:
        self.called = True
        return "should never run"


class TestWaNativeAndRegexExecutionTripwire:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("tool_name", sorted(_WA_NON_L0_TOOL_NAMES))
    @pytest.mark.parametrize("parse_mode", ["native", "regex"])
    async def test_wa_admin_profile_cannot_execute_internal_tool_from_any_parser(
        self,
        authorizer: ToolAuthorizer,
        tool_name: str,
        parse_mode: str,
    ) -> None:
        if parse_mode == "native":
            parsed = tool_executor.parse_native_function_call(
                SimpleNamespace(
                    function_call=SimpleNamespace(
                        name=tool_name,
                        args={"query": "PII_CANARY_TOOL_ARG_81c9"},
                    )
                )
            )
        else:
            parsed = tool_executor.parse_tool_call_regex(f"ACTION: {tool_name}()")
        assert parsed is not None

        tool = _NeverExecuteTool()
        tool_executor.configure_tool_executor(authorizer, confirmation_service=None)
        result, _duration = await tool_executor.execute_tool(
            tool_map={tool_name: tool},
            tool_name=parsed.tool_name,
            arguments=parsed.arguments,
            user_id="whatsapp_PII_CANARY_PHONE_628000000000",
            agent_role=ROLE_ADMIN,
            caller_profile=None,
            is_whatsapp=True,
        )

        assert not tool.called
        assert result == "This capability is not available in this conversation."
