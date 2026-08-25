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
      currently return None for the current 9-tool registry (no tool
      carries an `assigned_to`/`client_id` argument) — but
      `_check_client_scope` is no longer a no-op stub: F5's real
      `assigned_to` staff-scope enforcement (see
      `TestClientScopeEnforcement`) is exercised via synthetic
      tool/args pairs that stand in for the not-yet-wired F5 registry
      (docs/plans/2026-08-25-due-bot-live/MANDATE.md F5/F7)
    * Integration with execute_tool: denied tools never reach tool.execute(),
      allowed tools execute normally, legacy callers (agent_role=None)
      bypass enforcement
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from backend.services.agents.team_agent_config import (
    ROLE_ADMIN,
    ROLE_EXECUTIVE_CONSULTANT,
    ROLE_TAX_SPECIALIST,
    ROLE_VISA_SPECIALIST,
)
from backend.services.agents.tool_authorizer import (
    CLIENT_SCOPE_FILTER_KEYS,
    SENSITIVE_TOOLS,
    AuthDecision,
    AuthResult,
    ToolAuthorizer,
)
from backend.services.pii.violation_store import hash_subject
from backend.services.rag.agentic import tool_executor
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


@pytest.fixture(autouse=True)
def _isolate_tool_executor_state() -> Iterator[None]:
    """Keep execute_tool integration assertions independent of prior test modules."""
    original_authorizer = tool_executor._authorizer
    original_confirmation_service = tool_executor._confirmation_service
    tool_executor.configure_tool_executor(ToolAuthorizer(), confirmation_service=None)
    yield
    tool_executor._authorizer = original_authorizer
    tool_executor._confirmation_service = original_confirmation_service


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
        self,
        authorizer: ToolAuthorizer,
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
        self,
        authorizer: ToolAuthorizer,
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
            assert r.is_allowed, f"visa specialist must allow runtime tool {tool} (Phase 2 v8)"

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
        self,
        authorizer: ToolAuthorizer,
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
        self,
        authorizer: ToolAuthorizer,
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
        self,
        authorizer: ToolAuthorizer,
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
        self,
        authorizer: ToolAuthorizer,
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
        self,
        authorizer: ToolAuthorizer,
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
        self,
        authorizer: ToolAuthorizer,
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
# TOURNIQUET (2026-07-21) — sensitive-tool deny for no-principal callers
# ─────────────────────────────────────────────────────────────────────────


class TestSensitiveToolTourniquet:
    """
    Public CRM/PII exposure tourniquet: crm_query/timesheet/team_knowledge
    must be denied for agent_role=None (blog/ask, WA-unknown), even though
    every OTHER tool keeps the legacy passthrough. See memory
    `discovery_crm_pii_public_exposure_blog_ask_timesheet_2026_07_21`.
    `team_knowledge` was added in round 2 after the round-1 diff's Codex
    red-team caught it (empty search_term dumps all 19 staff records).
    """

    def test_sensitive_tools_frozenset_exact_values(self) -> None:
        """Guard the exact-match contract — no substring surprises later."""
        assert SENSITIVE_TOOLS == frozenset({"crm_query", "timesheet", "team_knowledge"})

    # ── GUILT: no-principal caller must be denied ──────────────────────

    @pytest.mark.asyncio
    async def test_crm_query_denied_for_no_principal(
        self,
        authorizer: ToolAuthorizer,
    ) -> None:
        """The verified blog/ask + WA-unknown vector: crm_query must be denied."""
        r = await authorizer.authorize(
            user_email=None,
            agent_role=None,
            tool_name="crm_query",
            args={"query_type": "client_stats"},
        )
        assert r.is_denied
        assert "authenticated" in r.reason.lower()

    @pytest.mark.asyncio
    async def test_timesheet_denied_for_no_principal(
        self,
        authorizer: ToolAuthorizer,
    ) -> None:
        """Same vector for the timesheet tool (clock in/out impersonation)."""
        r = await authorizer.authorize(
            user_email=None,
            agent_role=None,
            tool_name="timesheet",
            args={"action": "clock_in", "email": "anyone@balizero.com"},
        )
        assert r.is_denied
        assert "authenticated" in r.reason.lower()

    @pytest.mark.asyncio
    async def test_team_knowledge_denied_for_no_principal(
        self,
        authorizer: ToolAuthorizer,
    ) -> None:
        """Round 2: team_knowledge's search branch dumps whole records for an
        empty search_term — a no-principal caller must never reach it."""
        r = await authorizer.authorize(
            user_email=None,
            agent_role=None,
            tool_name="team_knowledge",
            args={"query_type": "search_by_name"},
        )
        assert r.is_denied
        assert "authenticated" in r.reason.lower()

    @pytest.mark.asyncio
    async def test_sensitive_deny_audited(self, authorizer: ToolAuthorizer, caplog) -> None:
        """The new deny path must still leave a trace in the audit log."""
        with caplog.at_level("WARNING", logger="backend.services.agents.tool_authorizer"):
            await authorizer.authorize(
                user_email=None,
                agent_role=None,
                tool_name="crm_query",
                args={},
            )
        records = [r for r in caplog.records if "tool_authz" in r.getMessage()]
        assert records, "tool_authz audit line missing for sensitive-tool deny"
        msg = records[-1].getMessage()
        assert "decision=deny" in msg
        assert "tool=crm_query" in msg
        assert "role=none" in msg

    # ── INNOCENCE: every OTHER tool keeps the legacy passthrough ────────

    @pytest.mark.asyncio
    async def test_non_sensitive_tools_still_passthrough_for_no_principal(
        self,
        authorizer: ToolAuthorizer,
    ) -> None:
        """Blog/marketing flows must not regress — only SENSITIVE_TOOLS are gated."""
        for tool in ("vector_search", "pricing", "knowledge_graph", "web_search"):
            r = await authorizer.authorize(
                user_email=None,
                agent_role=None,
                tool_name=tool,
                args={},
            )
            assert r.is_allowed, f"non-sensitive tool {tool} must keep legacy passthrough"

    # ── INNOCENCE: authenticated staff are unaffected ────────────────────

    @pytest.mark.asyncio
    async def test_crm_query_allowed_for_authenticated_staff(
        self,
        authorizer: ToolAuthorizer,
    ) -> None:
        """visa_specialist has crm_query in allowed_read_tools — must still work."""
        r = await authorizer.authorize(
            user_email="damar@balizero.com",
            agent_role=ROLE_VISA_SPECIALIST,
            tool_name="crm_query",
            args={"query_type": "client_stats"},
        )
        assert r.is_allowed

    @pytest.mark.asyncio
    async def test_timesheet_allowed_for_authenticated_staff(
        self,
        authorizer: ToolAuthorizer,
    ) -> None:
        """visa_specialist has timesheet in allowed_write_tools — must still work."""
        r = await authorizer.authorize(
            user_email="damar@balizero.com",
            agent_role=ROLE_VISA_SPECIALIST,
            tool_name="timesheet",
            args={"action": "clock_in", "email": "damar@balizero.com"},
        )
        assert r.is_allowed

    @pytest.mark.asyncio
    async def test_team_knowledge_allowed_for_authenticated_staff(
        self,
        authorizer: ToolAuthorizer,
    ) -> None:
        """visa_specialist has team_knowledge in allowed_read_tools — must still work."""
        r = await authorizer.authorize(
            user_email="damar@balizero.com",
            agent_role=ROLE_VISA_SPECIALIST,
            tool_name="team_knowledge",
            args={"query_type": "list_all"},
        )
        assert r.is_allowed

    @pytest.mark.asyncio
    async def test_crm_query_allowed_for_admin(
        self,
        authorizer: ToolAuthorizer,
    ) -> None:
        """Admin (empty allowlist precedence) must still reach crm_query."""
        r = await authorizer.authorize(
            user_email="zero@balizero.com",
            agent_role=ROLE_ADMIN,
            tool_name="crm_query",
            args={"query_type": "client_stats"},
        )
        assert r.is_allowed

    # ── Integration: execute_tool chokepoint ─────────────────────────────

    @pytest.mark.asyncio
    async def test_crm_query_denied_tool_never_executes_no_principal(self) -> None:
        """Denied sensitive tool must never reach tool.execute() (defense in depth).

        P0-DENY (2026-07-25): the denial observation itself must also stay
        neutral for a no-principal caller — the DATA not leaking (this
        assertion) is necessary but not sufficient; the fact that a CRM
        database and an authorization control exist must not leak either.
        See `discovery_p0deny_denial_narration_leak_2026_07_25` /
        `backend/services/rag/agentic/tool_executor.py::_denial_observation`.
        """
        tool = _NoopTool("crm_query")
        tool_map = {"crm_query": tool}

        result, _ = await execute_tool(
            tool_map=tool_map,
            tool_name="crm_query",
            arguments={"query_type": "client_stats"},
            user_id="anon@x",
            tool_execution_counter=None,
            agent_role=None,
        )
        assert tool.execute_called is False, "sensitive tool must not reach tool.execute()"
        lowered = result.lower()
        for forbidden in ("denied", "permission", "authoriz", "crm", "database"):
            assert forbidden not in lowered, f"leaked {forbidden!r} in anonymous denial: {result!r}"


# ─────────────────────────────────────────────────────────────────────────
# Scaffolding methods — Phase 2 no-op contract
# ─────────────────────────────────────────────────────────────────────────


class TestScaffoldingNoOps:
    def test_check_client_scope_returns_none(
        self,
        authorizer: ToolAuthorizer,
    ) -> None:
        """A bare `client_id` (a record REFERENCE, not a staff-scope filter)
        is deliberately excluded from `_check_client_scope`'s recognised
        keys (`CLIENT_SCOPE_FILTER_KEYS` — see that method's docstring):
        verifying whether client 42 belongs to `damar` would need a DB
        read this stateless authorizer intentionally does not perform, so
        this stays `None` even after F5's `assigned_to` enforcement landed
        (see `TestClientScopeEnforcement` for the part that IS enforced
        now)."""
        result = authorizer._check_client_scope(
            user_email="damar@balizero.com",
            agent_role=ROLE_VISA_SPECIALIST,
            tool_name="get_client",
            args={"client_id": 42},
        )
        assert result is None

    def test_check_requires_confirmation_returns_none(
        self,
        authorizer: ToolAuthorizer,
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
# F5 client-scope enforcement — the `assigned_to` staff-scope filter
# ─────────────────────────────────────────────────────────────────────────
#
# `list_practices`, `create_reminder`, `open_practice` (F5's ten-tool
# registry, apps/team-bot/team_bot/registry/tools.py) declare an OPTIONAL
# `assigned_to` argument (a staff-scope filter/target). None of those
# tools are wired into THIS authorizer's registry yet (team-bot is a
# standalone app with no executor today), so every scenario below uses a
# synthetic `tool_name`/`args` pair that stands in for that future shape
# — exactly the scaffold-completion F5 asks for ("complete... before any
# mutation arms").


class TestClientScopeEnforcement:
    NON_ADMIN_EMAIL = "damar@balizero.com"  # ROLE_VISA_SPECIALIST, client_scope="assigned"

    def test_recognised_key_is_assigned_to_only(self) -> None:
        """Pin the recognised-key set so a future edit that widens it
        (e.g. adding `client_id`) is a deliberate, reviewed change, not a
        silent one — see `_check_client_scope`'s docstring for why a bare
        record reference stays excluded."""
        assert CLIENT_SCOPE_FILTER_KEYS == frozenset({"assigned_to"})

    # ── Guilt: a non-admin actor referencing SOMEONE ELSE'S book ────────

    @pytest.mark.asyncio
    async def test_assigned_to_someone_else_denied(
        self,
        authorizer: ToolAuthorizer,
    ) -> None:
        result = await authorizer.authorize(
            user_email=self.NON_ADMIN_EMAIL,
            agent_role=ROLE_VISA_SPECIALIST,
            tool_name="list_practices",  # in ROLE_VISA_SPECIALIST.allowed_read_tools
            args={"assigned_to": "krisna@balizero.com"},
        )
        assert result.is_denied
        assert "assigned_to" in result.reason
        assert "list_practices" in result.reason

    @pytest.mark.asyncio
    async def test_deny_is_audited(
        self,
        authorizer: ToolAuthorizer,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """The scope-violation deny goes through `self._audit(...)`, same
        as every other denial — the guilt case must be traceable, not a
        silent refusal."""
        with caplog.at_level("WARNING", logger="backend.services.agents.tool_authorizer"):
            result = await authorizer.authorize(
                user_email=self.NON_ADMIN_EMAIL,
                agent_role=ROLE_VISA_SPECIALIST,
                tool_name="list_practices",
                args={"assigned_to": "krisna@balizero.com"},
            )
        assert result.is_denied
        assert any(
            "tool_authz decision=deny" in r.message and "tool=list_practices" in r.message
            for r in caplog.records
        )
        # PII boundary: neither raw email appears in the log line.
        joined = "\n".join(r.message for r in caplog.records)
        assert "damar@balizero.com" not in joined
        assert "krisna@balizero.com" not in joined

    # ── Innocence: own scope, admin scope, and untouched tools ──────────

    @pytest.mark.asyncio
    async def test_assigned_to_own_email_allowed(
        self,
        authorizer: ToolAuthorizer,
    ) -> None:
        """The half that matters most: a non-admin actor referencing
        THEIR OWN book must pass exactly as before."""
        result = await authorizer.authorize(
            user_email=self.NON_ADMIN_EMAIL,
            agent_role=ROLE_VISA_SPECIALIST,
            tool_name="list_practices",
            args={"assigned_to": self.NON_ADMIN_EMAIL},
        )
        assert result.is_allowed

    @pytest.mark.asyncio
    async def test_assigned_to_own_email_case_and_whitespace_insensitive(
        self,
        authorizer: ToolAuthorizer,
    ) -> None:
        result = await authorizer.authorize(
            user_email=self.NON_ADMIN_EMAIL,
            agent_role=ROLE_VISA_SPECIALIST,
            tool_name="list_practices",
            args={"assigned_to": "  DAMAR@BaliZero.com  "},
        )
        assert result.is_allowed

    @pytest.mark.asyncio
    async def test_admin_role_client_scope_all_unaffected(
        self,
        authorizer: ToolAuthorizer,
    ) -> None:
        """`agent_role.client_scope == "all"` bypasses the scope check
        entirely — an admin referencing someone else's book is fine."""
        result = await authorizer.authorize(
            user_email="zero@balizero.com",
            agent_role=ROLE_ADMIN,
            tool_name="list_practices",
            args={"assigned_to": "krisna@balizero.com"},
        )
        assert result.is_allowed

    @pytest.mark.asyncio
    async def test_tax_specialist_client_scope_all_unaffected_even_though_crm_access_disagrees(
        self,
        authorizer: ToolAuthorizer,
    ) -> None:
        """Empirically verified: `tax@balizero.com` is NOT recognised as a
        CRM admin by `crm_access.get_crm_user_filter` (it is absent from
        `crm_utils`'s admin allowlists), yet `ROLE_TAX_SPECIALIST.client_scope
        == "all"`. `agent_role.client_scope` must be consulted FIRST — if
        this authorizer relied on `get_crm_user_filter` alone, the tax team
        would be wrongly scope-restricted."""
        assert ROLE_TAX_SPECIALIST.client_scope == "all"
        result = await authorizer.authorize(
            user_email="tax@balizero.com",
            agent_role=ROLE_TAX_SPECIALIST,
            tool_name="list_practices",
            args={"assigned_to": "someone-else@balizero.com"},
        )
        assert result.is_allowed

    @pytest.mark.asyncio
    async def test_no_client_identifier_untouched(
        self,
        authorizer: ToolAuthorizer,
    ) -> None:
        """A tool call with no `assigned_to` (every one of the 9
        pre-existing tools) must not start failing."""
        result = await authorizer.authorize(
            user_email=self.NON_ADMIN_EMAIL,
            agent_role=ROLE_VISA_SPECIALIST,
            tool_name="vector_search",  # existing tool, no scope-carrying arg
            args={"query": "visa requirements"},
        )
        assert result.is_allowed

    def test_existing_nine_tools_all_pass_through_unaffected(
        self,
        authorizer: ToolAuthorizer,
    ) -> None:
        """Direct, synchronous sweep of `_check_client_scope` over the
        exact 9-tool registry named in the module docstring — none of
        them carry `assigned_to`, so every one must still resolve to
        `None` (untouched)."""
        existing_tools_and_args = {
            "vector_search": {"query": "x"},
            "pricing": {"service": "kitas"},
            "team_knowledge": {"search_term": ""},
            "knowledge_graph": {"entity": "x"},
            "calculator": {"expression": "1+1"},
            "vision": {"image_url": "https://example.com/x.png"},
            "image_generation": {"prompt": "x"},
            "web_search": {"query": "x"},
            "timesheet": {"action": "clock_in"},
        }
        for tool_name, args in existing_tools_and_args.items():
            result = authorizer._check_client_scope(
                user_email=self.NON_ADMIN_EMAIL,
                agent_role=ROLE_VISA_SPECIALIST,
                tool_name=tool_name,
                args=args,
            )
            assert result is None, f"{tool_name} unexpectedly scope-restricted"

    # ── WhatsApp-channel identity guard ──────────────────────────────────

    def test_whatsapp_pseudo_id_defers_rather_than_false_denies(self) -> None:
        """`user_email` on the WA channel is `whatsapp_<phone>`
        (`wa_inbox_bot.generate_bot_reply`), not a real email, even when
        `agent_role` was correctly resolved via a separately-trusted
        email upstream (`agentic_rag.py::_derive_wa_agent_role`). Without
        the `get_agent_role(user_email) == agent_role` guard, a WA-channel
        caller referencing their OWN book (by real email, since that is
        what CRM data stores) would be wrongly denied because the phone
        pseudo-id can never equal a real email. Confirm the guard fires:
        no deny, even though the argument names a DIFFERENT person, because
        this authorizer cannot confirm the caller's identity at all."""
        authorizer = ToolAuthorizer()
        result = authorizer._check_client_scope(
            user_email="whatsapp_+628123456789",
            agent_role=ROLE_VISA_SPECIALIST,
            tool_name="list_practices",
            args={"assigned_to": "krisna@balizero.com"},
        )
        assert result is None


# ─────────────────────────────────────────────────────────────────────────
# Audit log emission
# ─────────────────────────────────────────────────────────────────────────


class TestAuditLog:
    @pytest.mark.asyncio
    async def test_allow_decision_logs_info(self, authorizer: ToolAuthorizer, caplog) -> None:
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
        assert f"user=h:{hash_subject('damar@balizero.com')}" in msg
        assert "damar@balizero.com" not in msg, "raw staff email must never reach the audit log"
        assert "role=visa_specialist" in msg
        assert "scope=assigned" in msg
        assert "tool=vector_search" in msg

    @pytest.mark.asyncio
    async def test_deny_decision_logs_warning(self, authorizer: ToolAuthorizer, caplog) -> None:
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
        assert "damar@balizero.com" not in msg

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
# Principal pseudonymisation — P0 PII leak fix (2026-07-25)
#
# `tool_authorizer._audit` used to log `user_email` in the clear. The
# WhatsApp channel passes `f"whatsapp_{phone}"` as `user_email`
# (`wa_inbox_bot.generate_bot_reply`), so a client's phone number was
# written to production logs on EVERY tool call — allow included, the
# highest-volume path. Fix: `_principal_token` hashes every non-empty
# principal uniformly, regardless of its shape (cicatrix-superscar #3 —
# a `.startswith("whatsapp_")` branch would just move the disease to the
# next channel id shape that doesn't match).
# ─────────────────────────────────────────────────────────────────────────


class TestPrincipalPseudonymisation:
    WA_USER = "whatsapp_620000000000"
    WA_PHONE = "620000000000"

    @pytest.mark.asyncio
    async def test_wa_phone_not_in_log_on_allow(self, authorizer: ToolAuthorizer, caplog) -> None:
        """GUILT (allow path — the high-volume one, easiest to forget)."""
        with caplog.at_level("INFO", logger="backend.services.agents.tool_authorizer"):
            await authorizer.authorize(
                user_email=self.WA_USER,
                agent_role=ROLE_VISA_SPECIALIST,
                tool_name="vector_search",
                args={},
            )
        records = [r for r in caplog.records if "tool_authz" in r.getMessage()]
        assert records
        msg = records[-1].getMessage()
        assert "decision=allow" in msg
        assert self.WA_PHONE not in msg, "raw phone leaked into an ALLOW audit line"
        assert self.WA_USER not in msg, "raw whatsapp_<phone> identifier leaked"
        assert f"user=h:{hash_subject(self.WA_USER)}" in msg

    @pytest.mark.asyncio
    async def test_wa_phone_not_in_log_on_deny(self, authorizer: ToolAuthorizer, caplog) -> None:
        """GUILT (deny path — SENSITIVE_TOOLS tourniquet, agent_role=None)."""
        with caplog.at_level("WARNING", logger="backend.services.agents.tool_authorizer"):
            await authorizer.authorize(
                user_email=self.WA_USER,
                agent_role=None,
                tool_name="crm_query",
                args={},
            )
        records = [r for r in caplog.records if "tool_authz" in r.getMessage()]
        assert records
        msg = records[-1].getMessage()
        assert "decision=deny" in msg
        assert self.WA_PHONE not in msg, "raw phone leaked into a DENY audit line"
        assert self.WA_USER not in msg
        assert f"user=h:{hash_subject(self.WA_USER)}" in msg

    @pytest.mark.asyncio
    async def test_no_shape_branch_every_principal_shape_redacted(
        self, authorizer: ToolAuthorizer, caplog
    ) -> None:
        """
        INNOCENCE-of-the-antidote / anti-family-#3: redaction must not be a
        `whatsapp_`-prefix special case. A staff email, a WA id, and some
        made-up future channel id must ALL come out hashed, uniformly.
        """
        principals = [
            "damar@balizero.com",
            "whatsapp_620000000000",
            "telegram_987654321",  # hypothetical future channel — no branch for it
        ]
        with caplog.at_level("INFO", logger="backend.services.agents.tool_authorizer"):
            for p in principals:
                caplog.clear()
                await authorizer.authorize(
                    user_email=p,
                    agent_role=ROLE_VISA_SPECIALIST,
                    tool_name="vector_search",
                    args={},
                )
                records = [r for r in caplog.records if "tool_authz" in r.getMessage()]
                msg = records[-1].getMessage()
                assert p not in msg, f"principal {p!r} leaked raw into the audit log"
                assert f"user=h:{hash_subject(p)}" in msg

    @pytest.mark.asyncio
    async def test_anonymous_stays_anonymous(self, authorizer: ToolAuthorizer, caplog) -> None:
        """A genuinely absent principal must stay the literal 'anonymous' —
        never hashed, so it's still visibly distinct from a redacted one."""
        with caplog.at_level("INFO", logger="backend.services.agents.tool_authorizer"):
            await authorizer.authorize(
                user_email=None,
                agent_role=None,
                tool_name="vector_search",
                args={},
            )
        records = [r for r in caplog.records if "tool_authz" in r.getMessage()]
        msg = records[-1].getMessage()
        assert "user=anonymous" in msg

    @pytest.mark.asyncio
    async def test_stable_and_distinct_tokens(self, authorizer: ToolAuthorizer, caplog) -> None:
        """STABILITY: same principal -> same token twice; different
        principals -> different tokens. An operator holding a known
        identifier reproduces the token via hash_subject(identifier)."""
        with caplog.at_level("INFO", logger="backend.services.agents.tool_authorizer"):
            await authorizer.authorize(
                user_email=self.WA_USER,
                agent_role=ROLE_VISA_SPECIALIST,
                tool_name="vector_search",
                args={},
            )
            first_msg = [r for r in caplog.records if "tool_authz" in r.getMessage()][
                -1
            ].getMessage()
            caplog.clear()
            await authorizer.authorize(
                user_email=self.WA_USER,
                agent_role=ROLE_VISA_SPECIALIST,
                tool_name="pricing",
                args={},
            )
            second_msg = [r for r in caplog.records if "tool_authz" in r.getMessage()][
                -1
            ].getMessage()
            caplog.clear()
            await authorizer.authorize(
                user_email="whatsapp_610000000001",
                agent_role=ROLE_VISA_SPECIALIST,
                tool_name="vector_search",
                args={},
            )
            third_msg = [r for r in caplog.records if "tool_authz" in r.getMessage()][
                -1
            ].getMessage()

        token_first = f"user=h:{hash_subject(self.WA_USER)}"
        assert token_first in first_msg
        assert token_first in second_msg, "same principal must yield the same token"
        assert token_first not in third_msg, "different principal must yield a different token"

    @pytest.mark.asyncio
    async def test_decision_unchanged_by_redaction(self, authorizer: ToolAuthorizer) -> None:
        """Redaction changes only what is LOGGED, never what is DECIDED."""
        allow = await authorizer.authorize(
            user_email=self.WA_USER,
            agent_role=ROLE_VISA_SPECIALIST,
            tool_name="vector_search",
            args={},
        )
        assert allow.is_allowed

        deny = await authorizer.authorize(
            user_email=self.WA_USER,
            agent_role=None,
            tool_name="crm_query",
            args={},
        )
        assert deny.is_denied


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
        assert tool.execute_called is False, "denied tool must not reach tool.execute()"

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
