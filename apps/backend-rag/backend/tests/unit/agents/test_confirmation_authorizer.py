"""
Unit tests for VASSAL Phase 3 — Confirmation Gates in ToolAuthorizer.

Coverage (additive to test_tool_authorizer.py, which stays at 24/24 green):
    * AgentRole gains a `requires_confirmation: list[str]` field (default [])
    * ROLE_VISA_SPECIALIST and ROLE_EXECUTIVE_CONSULTANT both list
      'image_generation' in requires_confirmation (the real candidate tool
      from VASSAL_PLAN_V8 §5.1)
    * ROLE_ADMIN has no requires_confirmation (admins don't confirm their
      own actions)
    * ToolAuthorizer._check_requires_confirmation stops being a no-op:
      when a tool is in the role's requires_confirmation list, it returns
      AuthResult.confirm() with a non-empty preview reason
    * authorize() end-to-end returns NEEDS_CONFIRMATION for those tools
    * Tools NOT in the list still return None from the internal check
      (preserving the Phase 2 no-op contract for unlisted tools —
      test_check_requires_confirmation_returns_none in
      test_tool_authorizer.py MUST still pass)
    * Audit log format extended with `decision=needs_confirmation`

These tests run WITHOUT a real ConfirmationService — the authorizer's
confirmation check is a pure function over AgentRole.requires_confirmation.
The ConfirmationService (Redis + asyncio.Future) is tested separately in
test_confirmation_service.py.
"""

from __future__ import annotations

import pytest

from backend.services.agents.team_agent_config import (
    ROLE_ADMIN,
    ROLE_EXECUTIVE_CONSULTANT,
    ROLE_VISA_SPECIALIST,
    AgentRole,
)
from backend.services.agents.tool_authorizer import (
    AuthDecision,
    AuthResult,
    ToolAuthorizer,
)


# ─────────────────────────────────────────────────────────────────────────
# AgentRole — new requires_confirmation field
# ─────────────────────────────────────────────────────────────────────────


class TestAgentRoleRequiresConfirmation:
    def test_agent_role_default_requires_confirmation_is_empty_list(self) -> None:
        """New AgentRole instances default to no tools requiring confirmation."""
        role = AgentRole(
            role_id="test",
            display_name="Test",
            language="en",
            system_context="",
        )
        assert role.requires_confirmation == []

    def test_visa_specialist_requires_confirmation_image_generation(self) -> None:
        """Phase 3: ROLE_VISA_SPECIALIST must require confirmation for image_generation."""
        assert "image_generation" in ROLE_VISA_SPECIALIST.requires_confirmation

    def test_executive_consultant_requires_confirmation_image_generation(self) -> None:
        """Phase 3: ROLE_EXECUTIVE_CONSULTANT must require confirmation for image_generation."""
        assert "image_generation" in ROLE_EXECUTIVE_CONSULTANT.requires_confirmation

    def test_admin_has_no_requires_confirmation(self) -> None:
        """Admins bypass confirmation — they don't confirm their own actions."""
        assert ROLE_ADMIN.requires_confirmation == []

    def test_visa_specialist_timesheet_not_in_requires_confirmation(self) -> None:
        """
        Per VASSAL_PLAN_V8 §5.1: timesheet is 'Deferred pending verification'.
        Phase 3 scope is image_generation only. Timesheet must NOT be in the
        requires_confirmation list for any role.
        """
        assert "timesheet" not in ROLE_VISA_SPECIALIST.requires_confirmation
        assert "timesheet" not in ROLE_EXECUTIVE_CONSULTANT.requires_confirmation


# ─────────────────────────────────────────────────────────────────────────
# ToolAuthorizer._check_requires_confirmation — was no-op, now active
# ─────────────────────────────────────────────────────────────────────────


class TestCheckRequiresConfirmation:
    @pytest.fixture
    def authorizer(self) -> ToolAuthorizer:
        return ToolAuthorizer()

    def test_returns_confirm_for_listed_tool(
        self, authorizer: ToolAuthorizer,
    ) -> None:
        """image_generation is in ROLE_VISA_SPECIALIST.requires_confirmation."""
        result = authorizer._check_requires_confirmation(
            user_email="damar@balizero.com",
            agent_role=ROLE_VISA_SPECIALIST,
            tool_name="image_generation",
            args={"prompt": "a KITAS card"},
        )
        assert result is not None
        assert result.decision == AuthDecision.NEEDS_CONFIRMATION
        assert result.reason  # non-empty preview text
        assert "image_generation" in result.reason

    def test_returns_confirm_for_executive_consultant_image_generation(
        self, authorizer: ToolAuthorizer,
    ) -> None:
        result = authorizer._check_requires_confirmation(
            user_email="adit@balizero.com",
            agent_role=ROLE_EXECUTIVE_CONSULTANT,
            tool_name="image_generation",
            args={"prompt": "a marketing banner"},
        )
        assert result is not None
        assert result.decision == AuthDecision.NEEDS_CONFIRMATION

    def test_returns_none_for_unlisted_tool(
        self, authorizer: ToolAuthorizer,
    ) -> None:
        """
        Tools NOT in requires_confirmation return None (preserving the
        Phase 2 contract). This is the same invariant as
        test_tool_authorizer.py::test_check_requires_confirmation_returns_none
        — that test stays green because delete_client is not listed either.
        """
        result = authorizer._check_requires_confirmation(
            user_email="damar@balizero.com",
            agent_role=ROLE_VISA_SPECIALIST,
            tool_name="vector_search",
            args={"query": "visa"},
        )
        assert result is None

    def test_returns_none_for_admin_even_on_image_generation(
        self, authorizer: ToolAuthorizer,
    ) -> None:
        """Admins never need confirmation — their requires_confirmation is []."""
        result = authorizer._check_requires_confirmation(
            user_email="zero@balizero.com",
            agent_role=ROLE_ADMIN,
            tool_name="image_generation",
            args={"prompt": "anything"},
        )
        assert result is None

    def test_args_echoed_back_in_authresult(
        self, authorizer: ToolAuthorizer,
    ) -> None:
        """Args pass through unchanged — downstream tool_executor uses them."""
        original = {"prompt": "test", "style": "watercolor"}
        result = authorizer._check_requires_confirmation(
            user_email="damar@balizero.com",
            agent_role=ROLE_VISA_SPECIALIST,
            tool_name="image_generation",
            args=original,
        )
        assert result is not None
        assert result.args == original


# ─────────────────────────────────────────────────────────────────────────
# End-to-end authorize() returns NEEDS_CONFIRMATION
# ─────────────────────────────────────────────────────────────────────────


class TestAuthorizeEndToEndConfirmation:
    @pytest.fixture
    def authorizer(self) -> ToolAuthorizer:
        return ToolAuthorizer()

    @pytest.mark.asyncio
    async def test_visa_specialist_image_generation_returns_needs_confirmation(
        self, authorizer: ToolAuthorizer,
    ) -> None:
        result = await authorizer.authorize(
            user_email="damar@balizero.com",
            agent_role=ROLE_VISA_SPECIALIST,
            tool_name="image_generation",
            args={"prompt": "a KITAS card"},
        )
        assert result.needs_confirmation
        assert not result.is_allowed
        assert not result.is_denied
        assert result.reason

    @pytest.mark.asyncio
    async def test_executive_consultant_image_generation_returns_needs_confirmation(
        self, authorizer: ToolAuthorizer,
    ) -> None:
        result = await authorizer.authorize(
            user_email="adit@balizero.com",
            agent_role=ROLE_EXECUTIVE_CONSULTANT,
            tool_name="image_generation",
            args={"prompt": "banner"},
        )
        assert result.needs_confirmation

    @pytest.mark.asyncio
    async def test_admin_image_generation_is_allowed_without_confirmation(
        self, authorizer: ToolAuthorizer,
    ) -> None:
        """Admins bypass confirmation — they get plain ALLOWED."""
        result = await authorizer.authorize(
            user_email="zero@balizero.com",
            agent_role=ROLE_ADMIN,
            tool_name="image_generation",
            args={"prompt": "anything"},
        )
        assert result.is_allowed
        assert not result.needs_confirmation

    @pytest.mark.asyncio
    async def test_legacy_none_role_image_generation_is_allowed(
        self, authorizer: ToolAuthorizer,
    ) -> None:
        """
        Backward compat: agent_role=None (legacy /stream path) never asks
        for confirmation. Phase 2 contract preserved.
        """
        result = await authorizer.authorize(
            user_email=None,
            agent_role=None,
            tool_name="image_generation",
            args={"prompt": "anything"},
        )
        assert result.is_allowed
        assert not result.needs_confirmation

    @pytest.mark.asyncio
    async def test_visa_specialist_vector_search_still_allowed(
        self, authorizer: ToolAuthorizer,
    ) -> None:
        """Regression: read-only tools are not affected by Phase 3."""
        result = await authorizer.authorize(
            user_email="damar@balizero.com",
            agent_role=ROLE_VISA_SPECIALIST,
            tool_name="vector_search",
            args={"query": "visa"},
        )
        assert result.is_allowed
        assert not result.needs_confirmation


# ─────────────────────────────────────────────────────────────────────────
# Audit log — new decision value `needs_confirmation`
# ─────────────────────────────────────────────────────────────────────────


class TestAuditLogConfirmation:
    @pytest.fixture
    def authorizer(self) -> ToolAuthorizer:
        return ToolAuthorizer()

    @pytest.mark.asyncio
    async def test_needs_confirmation_logs_decision_line(
        self, authorizer: ToolAuthorizer, caplog,
    ) -> None:
        """Audit log must carry `decision=needs_confirmation` for grep-ability."""
        with caplog.at_level(
            "INFO", logger="backend.services.agents.tool_authorizer",
        ):
            await authorizer.authorize(
                user_email="damar@balizero.com",
                agent_role=ROLE_VISA_SPECIALIST,
                tool_name="image_generation",
                args={"prompt": "test"},
            )
        records = [r for r in caplog.records if "tool_authz" in r.getMessage()]
        assert records, "tool_authz audit line missing for needs_confirmation"
        msg = records[-1].getMessage()
        assert "decision=needs_confirmation" in msg
        assert "tool=image_generation" in msg
        assert "user=damar@balizero.com" in msg
        assert "role=visa_specialist" in msg
