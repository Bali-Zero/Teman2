"""W0 safety pre-arm — T-VIS: reasoning.py wires the per-request Gemini
tool-declaration filter into the two live ReAct-loop LLM turns.

Only two `llm_gateway.send_message()` call sites in reasoning.py actually
send tool declarations to Gemini (`enable_function_calling=True`): the main
turn in `execute_react_loop` (non-streaming) and the main turn in
`execute_react_loop_stream` (streaming). Every OTHER `send_message` call in
this file passes `enable_function_calling=False` (Tier-1 regen /
self-correction / final-answer generation), so the tools branch in
`llm_gateway._call_model._build_config` never fires for them regardless —
they are out of scope for this test and untouched by the fix.

Guilt/innocence:
- GUILT: a client/unresolved caller without a trusted workspace agent role
  must never see sensitive/internal declarations in the `gemini_tools` kwarg.
- GUILT: every WhatsApp profile, including team/creator, is L0 and cannot
  receive any internal declaration even if an AgentRole is also present.
- INNOCENCE: a server-derived workspace role (profile=None) receives only
  declarations allowed by canonical RBAC.

No real client data — fixture tool declarations are fabricated.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.agents.team_agent_config import ROLE_ADMIN, AgentRole
from backend.services.agents.tool_authorizer import SENSITIVE_TOOLS
from backend.services.rag.agentic.reasoning import ReasoningEngine
from backend.services.rag.agentic.team_crm_tools import TEAM_CRM_TOOL_NAMES
from backend.services.tools.definitions import AgentState

_FULL_GEMINI_TOOLS = [
    {"name": "vector_search", "description": "d"},
    {"name": "crm_query", "description": "d"},
    {"name": "timesheet", "description": "d"},
    {"name": "team_knowledge", "description": "d"},
    {"name": "get_pricing", "description": "d"},
    {"name": "team_my_clients", "description": "d"},
    {"name": "team_my_practices", "description": "d"},
    {"name": "team_my_deadlines", "description": "d"},
    {"name": "team_practice_detail", "description": "d"},
]

_INTERNAL_GEMINI_TOOL_NAMES = TEAM_CRM_TOOL_NAMES | SENSITIVE_TOOLS


def _make_llm_gateway(response_text: str = "Final Answer: done") -> AsyncMock:
    gw = AsyncMock()
    response_obj = MagicMock()
    response_obj.candidates = []
    token_usage = MagicMock(total_tokens=10)
    token_usage.__add__ = lambda self, other: self
    gw.send_message = AsyncMock(
        return_value=(response_text, "gemini-3-flash", response_obj, token_usage),
    )
    # `gemini_tools` is the shared, orchestrator-wide list — a real
    # LLMGateway exposes it as a read-only property backed by
    # `self._gemini_tools`; the AsyncMock double just needs the attribute.
    gw.gemini_tools = _FULL_GEMINI_TOOLS
    gw._gemini_tools = _FULL_GEMINI_TOOLS
    return gw


@pytest.fixture
def engine():
    return ReasoningEngine(tool_map={}, response_pipeline=None)


def _first_call_gemini_tool_names(gw: AsyncMock) -> set[str]:
    first_call_kwargs = gw.send_message.call_args_list[0].kwargs
    tools = first_call_kwargs["gemini_tools"]
    return {t["name"] for t in tools}


class TestExecuteReactLoopGeminiToolsScoping:
    @pytest.mark.asyncio
    async def test_guilt_client_caller_never_sees_team_tool_declarations(self, engine):
        gw = _make_llm_gateway()
        state = AgentState(query="hi", max_steps=1)
        state.caller_profile = None

        await engine.execute_react_loop(
            state=state,
            llm_gateway=gw,
            chat=MagicMock(),
            initial_prompt="hi",
            system_prompt="sys",
            query="hi",
            user_id="u",
            model_tier=0,
            tool_execution_counter={"count": 0},
        )

        sent_names = _first_call_gemini_tool_names(gw)
        assert sent_names.isdisjoint(_INTERNAL_GEMINI_TOOL_NAMES)
        assert sent_names == {"vector_search", "get_pricing"}

    @pytest.mark.asyncio
    async def test_guilt_wa_team_caller_never_sees_internal_declarations(self, engine):
        gw = _make_llm_gateway()
        state = AgentState(query="hi", max_steps=1)
        state.caller_profile = {"role": "team", "email": "member@balizero.com"}

        await engine.execute_react_loop(
            state=state,
            llm_gateway=gw,
            chat=MagicMock(),
            initial_prompt="hi",
            system_prompt="sys",
            query="hi",
            user_id="u",
            model_tier=0,
            tool_execution_counter={"count": 0},
        )

        sent_names = _first_call_gemini_tool_names(gw)
        assert sent_names.isdisjoint(_INTERNAL_GEMINI_TOOL_NAMES)

    @pytest.mark.asyncio
    async def test_innocence_workspace_agent_role_sees_full_tool_declarations(self, engine):
        gw = _make_llm_gateway()
        state = AgentState(query="hi", max_steps=1)
        state.caller_profile = None
        state.agent_role = ROLE_ADMIN

        await engine.execute_react_loop(
            state=state,
            llm_gateway=gw,
            chat=MagicMock(),
            initial_prompt="hi",
            system_prompt="sys",
            query="hi",
            user_id="u",
            model_tier=0,
            tool_execution_counter={"count": 0},
        )

        sent_names = _first_call_gemini_tool_names(gw)
        assert sent_names == {t["name"] for t in _FULL_GEMINI_TOOLS}

    @pytest.mark.asyncio
    async def test_guilt_wa_creator_with_admin_role_never_sees_internal_declarations(self, engine):
        gw = _make_llm_gateway()
        state = AgentState(query="hi", max_steps=1)
        state.caller_profile = {"role": "creator"}
        state.agent_role = ROLE_ADMIN

        await engine.execute_react_loop(
            state=state,
            llm_gateway=gw,
            chat=MagicMock(),
            initial_prompt="hi",
            system_prompt="sys",
            query="hi",
            user_id="u",
            model_tier=0,
            tool_execution_counter={"count": 0},
        )

        sent_names = _first_call_gemini_tool_names(gw)
        assert sent_names.isdisjoint(_INTERNAL_GEMINI_TOOL_NAMES)

    @pytest.mark.asyncio
    async def test_workspace_role_receives_only_canonical_allowlist(self, engine):
        gw = _make_llm_gateway()
        state = AgentState(query="hi", max_steps=1)
        state.caller_profile = None
        state.agent_role = AgentRole(
            role_id="synthetic_restricted",
            display_name="Synthetic",
            language="en",
            system_context="synthetic",
            allowed_read_tools=["vector_search", "team_knowledge"],
        )

        await engine.execute_react_loop(
            state=state,
            llm_gateway=gw,
            chat=MagicMock(),
            initial_prompt="hi",
            system_prompt="sys",
            query="hi",
            user_id="u",
            model_tier=0,
            tool_execution_counter={"count": 0},
        )

        assert _first_call_gemini_tool_names(gw) == {
            "vector_search",
            "team_knowledge",
        }

    @pytest.mark.asyncio
    async def test_no_caller_profile_attribute_defaults_to_client_scoping(self, engine):
        """A caller that never sets `state.caller_profile` at all (every
        non-WA caller today) must default to the SAME narrow scoping as an
        explicit client — `getattr(state, "caller_profile", None)` is `None`
        by the AgentState field default."""
        gw = _make_llm_gateway()
        state = AgentState(query="hi", max_steps=1)
        assert not hasattr(state, "caller_profile") or state.caller_profile is None

        await engine.execute_react_loop(
            state=state,
            llm_gateway=gw,
            chat=MagicMock(),
            initial_prompt="hi",
            system_prompt="sys",
            query="hi",
            user_id="u",
            model_tier=0,
            tool_execution_counter={"count": 0},
        )

        sent_names = _first_call_gemini_tool_names(gw)
        assert sent_names.isdisjoint(_INTERNAL_GEMINI_TOOL_NAMES)


class TestExecuteReactLoopStreamGeminiToolsScoping:
    @pytest.mark.asyncio
    async def test_guilt_client_caller_never_sees_team_tool_declarations(self, engine):
        gw = _make_llm_gateway()
        state = AgentState(query="hi", max_steps=1)
        state.caller_profile = None

        async for _event in engine.execute_react_loop_stream(
            state=state,
            llm_gateway=gw,
            chat=MagicMock(),
            initial_prompt="hi",
            system_prompt="sys",
            query="hi",
            user_id="u",
            model_tier=0,
            tool_execution_counter={"count": 0},
        ):
            pass

        sent_names = _first_call_gemini_tool_names(gw)
        assert sent_names.isdisjoint(_INTERNAL_GEMINI_TOOL_NAMES)

    @pytest.mark.asyncio
    async def test_guilt_wa_team_caller_never_sees_internal_declarations(self, engine):
        gw = _make_llm_gateway()
        state = AgentState(query="hi", max_steps=1)
        state.caller_profile = {"role": "team", "email": "member@balizero.com"}

        async for _event in engine.execute_react_loop_stream(
            state=state,
            llm_gateway=gw,
            chat=MagicMock(),
            initial_prompt="hi",
            system_prompt="sys",
            query="hi",
            user_id="u",
            model_tier=0,
            tool_execution_counter={"count": 0},
        ):
            pass

        sent_names = _first_call_gemini_tool_names(gw)
        assert sent_names.isdisjoint(_INTERNAL_GEMINI_TOOL_NAMES)

    @pytest.mark.asyncio
    async def test_innocence_workspace_agent_role_sees_full_tool_declarations(self, engine):
        gw = _make_llm_gateway()
        state = AgentState(query="hi", max_steps=1)
        state.caller_profile = None
        state.agent_role = ROLE_ADMIN

        async for _event in engine.execute_react_loop_stream(
            state=state,
            llm_gateway=gw,
            chat=MagicMock(),
            initial_prompt="hi",
            system_prompt="sys",
            query="hi",
            user_id="u",
            model_tier=0,
            tool_execution_counter={"count": 0},
        ):
            pass

        sent_names = _first_call_gemini_tool_names(gw)
        assert sent_names == {t["name"] for t in _FULL_GEMINI_TOOLS}


class TestFlagOffStillScopesGenericSensitiveTools:
    """The default-off flag removes the four team CRM tools only. Generic
    sensitive tools are always registered and must remain hidden from a
    client/unknown request."""

    @pytest.mark.asyncio
    async def test_client_cannot_see_generic_sensitive_tools(self, engine):
        gw = _make_llm_gateway()
        no_team_tools = [t for t in _FULL_GEMINI_TOOLS if t["name"] not in TEAM_CRM_TOOL_NAMES]
        gw.gemini_tools = no_team_tools
        gw._gemini_tools = no_team_tools
        state = AgentState(query="hi", max_steps=1)
        state.caller_profile = None

        await engine.execute_react_loop(
            state=state,
            llm_gateway=gw,
            chat=MagicMock(),
            initial_prompt="hi",
            system_prompt="sys",
            query="hi",
            user_id="u",
            model_tier=0,
            tool_execution_counter={"count": 0},
        )

        sent_names = _first_call_gemini_tool_names(gw)
        assert sent_names.isdisjoint(SENSITIVE_TOOLS)
        assert sent_names == {"vector_search", "get_pricing"}
