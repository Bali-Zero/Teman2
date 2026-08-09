"""WA team-assistant Phase 2 — guilt/innocence tests for team_crm_tools.py.

Design under test (`backend/services/rag/agentic/team_crm_tools.py`):
- 4 read-only tools, scope resolved server-side from `_caller_profile`
  (never an LLM-controllable arg).
- RBAC chain: `LOWER(assigned_to) = LOWER(email)` unless admin
  (`backend.app.utils.crm_utils.is_crm_admin` — the SAME allowlist the
  REST CRM routers use).
- Hard innocence: no profile / client / unresolved-team-identity / flag-off
  -> zero DB access, a static "not available" payload.
- No PII (client full_name) ever appears in a log record.

No real team/client data — all fixture names below are fabricated.
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from backend.services.agents.team_agent_config import ROLE_ADMIN, AgentRole
from backend.services.rag.agentic import team_crm_tools as tcm

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_pool(fetch_return: list[dict]) -> tuple[AsyncMock, AsyncMock]:
    """Minimal asyncpg-pool double — mirrors the pattern already used in
    backend/tests/unit/app/routers/test_crm_enhanced_alerts.py."""
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=fetch_return)

    pool = AsyncMock()

    @asynccontextmanager
    async def acquire():
        yield conn

    pool.acquire = acquire
    return pool, conn


ADMIN_PROFILE_CREATOR = {"role": "creator"}
TEAM_PROFILE_A = {"role": "team", "name": "Member A", "email": "membera@balizero.com"}
TEAM_PROFILE_B = {"role": "team", "name": "Member B", "email": "memberb@balizero.com"}
TEAM_PROFILE_NO_EMAIL = {"role": "team", "name": "Env Override Member"}
CLIENT_PROFILE = {"role": "client", "client_id": 1}
UNKNOWN_PROFILE = None


@pytest.fixture(autouse=True)
def _flag_on(monkeypatch):
    """Most tests exercise the ON path; the OFF path gets its own test."""
    monkeypatch.setenv("WA_TEAM_CRM_TOOLS_ENABLED", "true")
    yield


# ---------------------------------------------------------------------------
# is_team_crm_tools_enabled
# ---------------------------------------------------------------------------


def test_flag_default_is_off(monkeypatch):
    monkeypatch.delenv("WA_TEAM_CRM_TOOLS_ENABLED", raising=False)
    assert tcm.is_team_crm_tools_enabled() is False


@pytest.mark.parametrize("value", ["true", "1", "yes", "on", "TRUE", "  true  "])
def test_flag_truthy_values(monkeypatch, value):
    monkeypatch.setenv("WA_TEAM_CRM_TOOLS_ENABLED", value)
    assert tcm.is_team_crm_tools_enabled() is True


@pytest.mark.parametrize("value", ["false", "0", "no", "off", ""])
def test_flag_falsy_values(monkeypatch, value):
    monkeypatch.setenv("WA_TEAM_CRM_TOOLS_ENABLED", value)
    assert tcm.is_team_crm_tools_enabled() is False


# ---------------------------------------------------------------------------
# resolve_team_crm_scope — pure logic
# ---------------------------------------------------------------------------


class TestResolveTeamCrmScope:
    def test_creator_is_admin_scope(self):
        scope = tcm.resolve_team_crm_scope(ADMIN_PROFILE_CREATOR)
        assert scope is not None
        assert scope.is_admin is True

    def test_team_with_email_is_scoped_non_admin(self):
        scope = tcm.resolve_team_crm_scope(TEAM_PROFILE_A)
        assert scope is not None
        assert scope.is_admin is False
        assert scope.email == "membera@balizero.com"

    def test_team_email_lowercased(self):
        scope = tcm.resolve_team_crm_scope({"role": "team", "email": "MemberA@Balizero.COM"})
        assert scope.email == "membera@balizero.com"

    def test_team_admin_email_promotes_to_admin_scope(self, monkeypatch):
        # asya@balizero.com is a CRM_EXTRA_ADMIN_EMAILS entry — a "team"
        # role sender whose DB-resolved email happens to be an admin email
        # must get admin scope, not filtered scope.
        scope = tcm.resolve_team_crm_scope({"role": "team", "email": "asya@balizero.com"})
        assert scope is not None
        assert scope.is_admin is True

    def test_team_without_email_is_unresolved(self):
        scope = tcm.resolve_team_crm_scope(TEAM_PROFILE_NO_EMAIL)
        assert scope is not None
        assert scope.is_admin is False
        assert scope.email is None

    def test_client_role_returns_no_scope(self):
        assert tcm.resolve_team_crm_scope(CLIENT_PROFILE) is None

    def test_none_profile_returns_no_scope(self):
        assert tcm.resolve_team_crm_scope(None) is None

    def test_empty_profile_returns_no_scope(self):
        assert tcm.resolve_team_crm_scope({}) is None

    def test_unknown_role_returns_no_scope(self):
        assert tcm.resolve_team_crm_scope({"role": "unknown"}) is None


class TestIsTeamOrCreatorProfile:
    def test_team_is_true(self):
        assert tcm.is_team_or_creator_profile({"role": "team"}) is True

    def test_creator_is_true(self):
        assert tcm.is_team_or_creator_profile({"role": "creator"}) is True

    def test_client_is_false(self):
        assert tcm.is_team_or_creator_profile({"role": "client"}) is False

    def test_none_is_false(self):
        assert tcm.is_team_or_creator_profile(None) is False


# ---------------------------------------------------------------------------
# Shared guilt/innocence matrix — every tool must refuse identically for
# no-profile / client / flag-off / unresolved-team-identity.
# ---------------------------------------------------------------------------

ALL_TOOL_FACTORIES = [
    lambda pool: tcm.TeamMyClientsTool(pool),
    lambda pool: tcm.TeamMyPracticesTool(pool),
    lambda pool: tcm.TeamMyDeadlinesTool(pool),
    lambda pool: tcm.TeamPracticeDetailTool(pool),
]


def _required_kwargs(tool) -> dict:
    """team_practice_detail requires client_name; others need nothing extra."""
    if tool.name == "team_practice_detail":
        return {"client_name": "Any Name"}
    return {}


@pytest.mark.asyncio
@pytest.mark.parametrize("make_tool", ALL_TOOL_FACTORIES)
async def test_innocence_no_profile_never_touches_db(make_tool):
    pool, conn = _make_pool([])
    tool = make_tool(pool)
    result = await tool.execute(**_required_kwargs(tool))
    payload = json.loads(result)
    assert payload["available"] is False
    conn.fetch.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("make_tool", ALL_TOOL_FACTORIES)
async def test_innocence_client_profile_never_touches_db(make_tool):
    pool, conn = _make_pool([])
    tool = make_tool(pool)
    result = await tool.execute(_caller_profile=CLIENT_PROFILE, **_required_kwargs(tool))
    payload = json.loads(result)
    assert payload["available"] is False
    conn.fetch.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("make_tool", ALL_TOOL_FACTORIES)
async def test_innocence_flag_off_never_touches_db_even_for_team(make_tool, monkeypatch):
    monkeypatch.setenv("WA_TEAM_CRM_TOOLS_ENABLED", "false")
    pool, conn = _make_pool([])
    tool = make_tool(pool)
    result = await tool.execute(_caller_profile=TEAM_PROFILE_A, **_required_kwargs(tool))
    payload = json.loads(result)
    assert payload["available"] is False
    conn.fetch.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("make_tool", ALL_TOOL_FACTORIES)
async def test_innocence_team_without_email_never_touches_db(make_tool):
    pool, conn = _make_pool([])
    tool = make_tool(pool)
    result = await tool.execute(_caller_profile=TEAM_PROFILE_NO_EMAIL, **_required_kwargs(tool))
    payload = json.loads(result)
    assert payload["available"] is False
    conn.fetch.assert_not_called()


# ---------------------------------------------------------------------------
# team_my_clients
# ---------------------------------------------------------------------------


class TestTeamMyClientsTool:
    @pytest.mark.asyncio
    async def test_guilt_team_scope_filters_by_assigned_to(self):
        pool, conn = _make_pool([{"id": 1, "full_name": "Client Alpha", "practice_count": 2}])
        tool = tcm.TeamMyClientsTool(pool)
        result = await tool.execute(_caller_profile=TEAM_PROFILE_A)
        payload = json.loads(result)
        assert payload["available"] is True
        assert payload["clients"][0]["client_id"] == 1

        sql, params = conn.fetch.call_args.args[0], conn.fetch.call_args.args[1:]
        assert "LOWER(c.assigned_to)" in sql
        assert TEAM_PROFILE_A["email"] in params

    @pytest.mark.asyncio
    async def test_innocence_admin_scope_has_no_assigned_to_filter(self):
        pool, conn = _make_pool([])
        tool = tcm.TeamMyClientsTool(pool)
        await tool.execute(_caller_profile=ADMIN_PROFILE_CREATOR)

        sql = conn.fetch.call_args.args[0]
        assert "assigned_to" not in sql

    @pytest.mark.asyncio
    async def test_limit_is_clamped(self):
        pool, conn = _make_pool([])
        tool = tcm.TeamMyClientsTool(pool)
        await tool.execute(_caller_profile=TEAM_PROFILE_A, limit=99999)

        params = conn.fetch.call_args.args[1:]
        assert params[-1] == tcm.MAX_LIMIT


# ---------------------------------------------------------------------------
# team_my_practices
# ---------------------------------------------------------------------------


class TestTeamMyPracticesTool:
    @pytest.mark.asyncio
    async def test_guilt_team_scope_filters_by_assigned_to(self):
        pool, conn = _make_pool(
            [
                {
                    "id": 10,
                    "status": "on_process",
                    "expiry_date": None,
                    "created_at": None,
                    "practice_type": "KITAS",
                    "client_name": "Client Alpha",
                }
            ]
        )
        tool = tcm.TeamMyPracticesTool(pool)
        result = await tool.execute(_caller_profile=TEAM_PROFILE_A)
        payload = json.loads(result)
        assert payload["available"] is True
        assert payload["practices"][0]["practice_id"] == 10

        sql, params = conn.fetch.call_args.args[0], conn.fetch.call_args.args[1:]
        assert "LOWER(c.assigned_to)" in sql
        assert TEAM_PROFILE_A["email"] in params

    @pytest.mark.asyncio
    async def test_status_filter_is_parameterized(self):
        pool, conn = _make_pool([])
        tool = tcm.TeamMyPracticesTool(pool)
        await tool.execute(_caller_profile=TEAM_PROFILE_A, status="completed")

        sql, params = conn.fetch.call_args.args[0], conn.fetch.call_args.args[1:]
        assert "p.status = $" in sql
        assert "completed" in params


# ---------------------------------------------------------------------------
# team_my_deadlines
# ---------------------------------------------------------------------------


class TestTeamMyDeadlinesTool:
    @pytest.mark.asyncio
    async def test_guilt_team_scope_filters_both_queries(self):
        pool, conn = _make_pool([])  # same conn.fetch used for both queries
        tool = tcm.TeamMyDeadlinesTool(pool)
        result = await tool.execute(_caller_profile=TEAM_PROFILE_A)
        payload = json.loads(result)
        assert payload["available"] is True
        assert payload["deadlines"] == []

        assert conn.fetch.call_count == 2
        for call in conn.fetch.call_args_list:
            sql = call.args[0]
            params = call.args[1:]
            assert "assigned_to" in sql
            assert TEAM_PROFILE_A["email"] in params

    @pytest.mark.asyncio
    async def test_admin_scope_omits_assigned_to_filter(self):
        pool, conn = _make_pool([])
        tool = tcm.TeamMyDeadlinesTool(pool)
        await tool.execute(_caller_profile=ADMIN_PROFILE_CREATOR)

        for call in conn.fetch.call_args_list:
            sql = call.args[0]
            assert "assigned_to" not in sql

    @pytest.mark.asyncio
    async def test_days_ahead_is_clamped(self):
        pool, conn = _make_pool([])
        tool = tcm.TeamMyDeadlinesTool(pool)
        await tool.execute(_caller_profile=TEAM_PROFILE_A, days_ahead=99999)

        first_call_params = conn.fetch.call_args_list[0].args[1:]
        assert first_call_params[0] == tcm.MAX_DAYS_AHEAD


# ---------------------------------------------------------------------------
# team_practice_detail — the fuzzy-lookup scope-escape guilt fixture
# ---------------------------------------------------------------------------


class TestTeamPracticeDetailTool:
    @pytest.mark.asyncio
    async def test_guilt_own_client_found(self):
        pool, conn = _make_pool(
            [
                {
                    "id": 55,
                    "status": "waiting_documents",
                    "expiry_date": None,
                    "notes": None,
                    "created_at": None,
                    "updated_at": None,
                    "practice_type": "PT PMA",
                    "client_name": "Client Alpha",
                }
            ]
        )
        tool = tcm.TeamPracticeDetailTool(pool)
        result = await tool.execute(client_name="Alpha", _caller_profile=TEAM_PROFILE_A)
        payload = json.loads(result)
        assert payload["available"] is True
        assert len(payload["practices"]) == 1

    @pytest.mark.asyncio
    async def test_guilt_fuzzy_lookup_cannot_escape_scope(self):
        """Member A queries Member B's client by name — the SQL sent to the
        DB must carry BOTH the ILIKE pattern AND A's assigned_to filter in
        the SAME query, so a real Postgres would return zero rows no matter
        how loose the fuzzy match is. We assert the composed query (not a
        fake DB), which is the actual scope-escape-proof property."""
        pool, conn = _make_pool([])  # a real DB scoped to A would find nothing for B's client
        tool = tcm.TeamPracticeDetailTool(pool)
        result = await tool.execute(client_name="Client Beta", _caller_profile=TEAM_PROFILE_A)
        payload = json.loads(result)
        assert payload["available"] is True
        assert payload["practices"] == []

        sql, params = conn.fetch.call_args.args[0], conn.fetch.call_args.args[1:]
        assert "ILIKE" in sql
        assert "LOWER(c.assigned_to)" in sql
        assert "%Client Beta%" in params
        assert TEAM_PROFILE_A["email"] in params
        assert TEAM_PROFILE_B["email"] not in params

    @pytest.mark.asyncio
    async def test_admin_scope_has_no_assigned_to_filter(self):
        pool, conn = _make_pool([])
        tool = tcm.TeamPracticeDetailTool(pool)
        await tool.execute(client_name="Anyone", _caller_profile=ADMIN_PROFILE_CREATOR)

        sql = conn.fetch.call_args.args[0]
        assert "assigned_to" not in sql

    @pytest.mark.asyncio
    async def test_missing_client_name_is_handled_without_db_call(self):
        pool, conn = _make_pool([])
        tool = tcm.TeamPracticeDetailTool(pool)
        result = await tool.execute(client_name="   ", _caller_profile=TEAM_PROFILE_A)
        payload = json.loads(result)
        assert payload["available"] is True
        assert payload["practices"] == []
        conn.fetch.assert_not_called()


# ---------------------------------------------------------------------------
# PII discipline: no client full_name ever appears in a log record.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_client_name_in_log_records(caplog):
    caplog.set_level(logging.INFO, logger="backend.services.rag.agentic.team_crm_tools")
    pool, _conn = _make_pool(
        [{"id": 1, "full_name": "Very Distinctive Client Name", "practice_count": 1}]
    )
    tool = tcm.TeamMyClientsTool(pool)
    await tool.execute(_caller_profile=TEAM_PROFILE_A)

    for record in caplog.records:
        rendered = record.getMessage() + str(getattr(record, "__dict__", {}))
        assert "Very Distinctive Client Name" not in rendered


# ---------------------------------------------------------------------------
# create_team_crm_tools factory
# ---------------------------------------------------------------------------


def test_create_team_crm_tools_returns_four_tools():
    tools = tcm.create_team_crm_tools(db_pool=None)
    names = {t.name for t in tools}
    assert names == tcm.TEAM_CRM_TOOL_NAMES
    assert len(tools) == 4


# ---------------------------------------------------------------------------
# filter_gemini_tools_for_caller — T-VIS (W0 safety pre-arm, 2026-07-25).
#
# This function strips every sensitive/internal declaration from the
# per-request payload sent to Gemini for client/unknown callers. That includes
# the four flag-gated team CRM tools plus the always-registered crm_query,
# timesheet, and team_knowledge tools. Only the trusted ``is_whatsapp`` marker
# activates the exact WA L0 allowlist; a non-WA audience profile keeps ordinary
# tools. Authenticated workspace roles still use canonical RBAC.
# ---------------------------------------------------------------------------

_FULL_GEMINI_TOOLS = [
    {
        "name": "vector_search",
        "description": (
            "Search all collections, including training_conversations_hybrid "
            "and bali_zero_pricing_hybrid"
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "collection": {
                    "type": "STRING",
                    "enum": [
                        "visa_oracle",
                        "legal_unified",
                        "kbli_2025_final",
                        "tax_genius",
                        "bali_zero_pricing_hybrid",
                        "training_conversations_hybrid",
                        "immigration_circulars",
                        "balizero_news",
                    ],
                }
            },
        },
    },
    {"name": "crm_query", "description": "d"},
    {"name": "timesheet", "description": "d"},
    {"name": "team_knowledge", "description": "d"},
    {"name": "get_pricing", "description": "d"},
    {"name": "calculator", "description": "d"},
    {"name": "vision_analysis", "description": "d"},
    {"name": "generate_image", "description": "d"},
    {"name": "web_search", "description": "d"},
    {"name": "knowledge_graph_search", "description": "d"},
    {"name": "team_my_clients", "description": "d"},
    {"name": "team_my_practices", "description": "d"},
    {"name": "team_my_deadlines", "description": "d"},
    {"name": "team_practice_detail", "description": "d"},
]

_WA_L0_TOOL_NAMES = {"vector_search", "get_pricing", "calculator"}
_WA_L0_VECTOR_COLLECTIONS = {
    "visa_oracle",
    "legal_unified",
    "kbli_2025_final",
    "tax_genius",
    "immigration_circulars",
    "balizero_news",
}

_INTERNAL_GEMINI_TOOL_NAMES = tcm.TEAM_CRM_TOOL_NAMES | frozenset(
    {"crm_query", "timesheet", "team_knowledge"}
)


class TestFilterGeminiToolsForCaller:
    @pytest.mark.parametrize(
        ("profile", "agent_role"),
        [
            (None, None),
            (None, ROLE_ADMIN),
            (CLIENT_PROFILE, None),
            (TEAM_PROFILE_A, ROLE_ADMIN),
            (ADMIN_PROFILE_CREATOR, ROLE_ADMIN),
        ],
    )
    def test_trusted_whatsapp_surface_exposes_exact_l0_allowlist(
        self,
        profile,
        agent_role,
    ):
        filtered = tcm.filter_gemini_tools_for_caller(
            _FULL_GEMINI_TOOLS,
            profile,
            agent_role=agent_role,
            is_whatsapp=True,
        )
        assert {tool["name"] for tool in filtered} == _WA_L0_TOOL_NAMES

    def test_whatsapp_vector_schema_contains_only_public_low_pii_collections(self):
        filtered = tcm.filter_gemini_tools_for_caller(
            _FULL_GEMINI_TOOLS,
            None,
            agent_role=ROLE_ADMIN,
            is_whatsapp=True,
        )
        vector = next(tool for tool in filtered if tool["name"] == "vector_search")
        collection_schema = vector["parameters"]["properties"]["collection"]
        assert set(collection_schema["enum"]) == _WA_L0_VECTOR_COLLECTIONS
        rendered = json.dumps(vector)
        assert "training_conversations_hybrid" not in rendered
        assert "bali_zero_pricing_hybrid" not in rendered

        original = _FULL_GEMINI_TOOLS[0]
        assert "training_conversations_hybrid" in json.dumps(original)
        assert "bali_zero_pricing_hybrid" in json.dumps(original)

    # --- GUILT: internal declarations must be stripped for non-team callers ---

    def test_guilt_client_profile_strips_all_team_tool_names(self):
        filtered = tcm.filter_gemini_tools_for_caller(_FULL_GEMINI_TOOLS, CLIENT_PROFILE)
        names = {t["name"] for t in filtered}
        assert names.isdisjoint(_INTERNAL_GEMINI_TOOL_NAMES)

    def test_guilt_none_profile_strips_all_team_tool_names(self):
        filtered = tcm.filter_gemini_tools_for_caller(_FULL_GEMINI_TOOLS, UNKNOWN_PROFILE)
        names = {t["name"] for t in filtered}
        assert names.isdisjoint(_INTERNAL_GEMINI_TOOL_NAMES)

    def test_guilt_unknown_role_strips_all_team_tool_names(self):
        filtered = tcm.filter_gemini_tools_for_caller(_FULL_GEMINI_TOOLS, {"role": "unknown"})
        names = {t["name"] for t in filtered}
        assert names.isdisjoint(_INTERNAL_GEMINI_TOOL_NAMES)

    # --- GUILT: every non-None profile hides internal tools ---

    @pytest.mark.parametrize("profile", [ADMIN_PROFILE_CREATOR, TEAM_PROFILE_A])
    def test_guilt_wa_team_or_creator_profile_strips_internal_tools(self, profile):
        filtered = tcm.filter_gemini_tools_for_caller(
            _FULL_GEMINI_TOOLS,
            profile,
        )
        names = {tool["name"] for tool in filtered}
        assert names.isdisjoint(_INTERNAL_GEMINI_TOOL_NAMES)

    def test_innocence_workspace_agent_role_keeps_every_tool(self):
        filtered = tcm.filter_gemini_tools_for_caller(
            _FULL_GEMINI_TOOLS,
            None,
            agent_role=ROLE_ADMIN,
        )
        assert filtered == _FULL_GEMINI_TOOLS

    def test_workspace_role_sees_only_canonical_allowlist(self):
        restricted_role = AgentRole(
            role_id="synthetic_restricted",
            display_name="Synthetic",
            language="en",
            system_context="synthetic",
            allowed_read_tools=["vector_search", "team_knowledge"],
        )
        filtered = tcm.filter_gemini_tools_for_caller(
            _FULL_GEMINI_TOOLS,
            None,
            agent_role=restricted_role,
        )
        assert {tool["name"] for tool in filtered} == {
            "vector_search",
            "team_knowledge",
        }

    @pytest.mark.parametrize(
        "profile",
        [CLIENT_PROFILE, TEAM_PROFILE_A, ADMIN_PROFILE_CREATOR, {"role": "unknown"}],
    )
    def test_guilt_wa_profile_is_not_overridden_by_admin_role(self, profile):
        filtered = tcm.filter_gemini_tools_for_caller(
            _FULL_GEMINI_TOOLS,
            profile,
            agent_role=ROLE_ADMIN,
        )
        names = {t["name"] for t in filtered}
        assert names.isdisjoint(_INTERNAL_GEMINI_TOOL_NAMES)
        assert "web_search" in names

    # --- INNOCENCE: non-team tools are never collateral-dropped ---

    def test_innocence_non_team_tools_survive_client_filter(self):
        filtered = tcm.filter_gemini_tools_for_caller(_FULL_GEMINI_TOOLS, CLIENT_PROFILE)
        names = {t["name"] for t in filtered}
        assert names == {
            tool["name"]
            for tool in _FULL_GEMINI_TOOLS
            if tool["name"] not in _INTERNAL_GEMINI_TOOL_NAMES
        }
        assert next(tool for tool in filtered if tool["name"] == "web_search") == {
            "name": "web_search",
            "description": "d",
        }

    # --- Edge cases ---

    def test_empty_gemini_tools_list_returns_empty(self):
        assert tcm.filter_gemini_tools_for_caller([], CLIENT_PROFILE) == []

    def test_none_gemini_tools_returns_empty_list_not_none(self):
        """The flag-off case: create_agentic_rag() never appends the team
        tools, so `llm_gateway.gemini_tools` may legitimately be `[]`/None
        for every caller — the filter must return a list either way, never
        raise on None input."""
        assert tcm.filter_gemini_tools_for_caller(None, CLIENT_PROFILE) == []

    def test_flag_off_still_hides_always_registered_sensitive_tools(self):
        """The default-off flag removes the four team CRM tools, but generic
        sensitive tools remain in the shared registry and still need request
        scoping for a client."""
        no_team_tools = [t for t in _FULL_GEMINI_TOOLS if t["name"] not in tcm.TEAM_CRM_TOOL_NAMES]
        filtered = tcm.filter_gemini_tools_for_caller(no_team_tools, CLIENT_PROFILE)
        names = {t["name"] for t in filtered}
        assert names == {
            tool["name"]
            for tool in no_team_tools
            if tool["name"] not in _INTERNAL_GEMINI_TOOL_NAMES
        }
