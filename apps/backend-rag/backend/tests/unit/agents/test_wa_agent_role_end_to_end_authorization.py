"""T4 unified principal — end-to-end proof (spec `2026-07-24-zantara-bot-
consultant-assistant-spec.md` §5 item T4 — "two parallel auth systems").

The two halves of the fix are unit-tested separately elsewhere:
    * `_derive_wa_agent_role` (correct mapping) —
      `backend/tests/unit/app/routers/test_agentic_rag_router.py::TestDeriveWaAgentRole`
    * `ToolAuthorizer.authorize` accepting any `AgentRole` (pre-existing,
      untouched by T4) — `test_tool_authorizer.py`

This file composes BOTH halves for a concrete `SENSITIVE_TOOLS` entry, so
the actual defect T4 fixes — "a real Bali Zero team member messaging the
bot from their own phone cannot use crm_query/timesheet/team_knowledge,
because agent_role is always None on the WhatsApp path" — is disproven by
a single end-to-end test, not just inferred by the reader from two
separate files.
"""

from __future__ import annotations

import pytest

from backend.app.routers.agentic_rag import _derive_wa_agent_role
from backend.services.agents.team_agent_config import ROLE_ADMIN, ROLE_EXECUTIVE_CONSULTANT
from backend.services.agents.tool_authorizer import SENSITIVE_TOOLS, ToolAuthorizer


@pytest.fixture
def authorizer() -> ToolAuthorizer:
    return ToolAuthorizer()


class TestWaSenderSensitiveToolEndToEnd:
    """GUILT: the actual defect. Before T4 (`agent_role=None`, today's
    WhatsApp behavior), every SENSITIVE_TOOLS entry is hard-denied for
    everyone, including a genuine team member. After deriving `agent_role`
    from the server-resolved WA profile, that SAME team member's tool call
    is authorized — with THEIR OWN scope, not admin."""

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
        )
        assert result.is_denied

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tool_name", sorted(SENSITIVE_TOOLS))
    async def test_after_t4_registered_team_wa_sender_is_allowed_with_own_scope(
        self, authorizer: ToolAuthorizer, tool_name: str
    ) -> None:
        """T4 armed: a DB-resolved WA team sender with a registered VASSAL
        role now passes the SAME tourniquet a JWT-authenticated staff
        member already passes — using THEIR OWN role, not a fabricated
        admin one."""
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
        )
        assert result.is_allowed

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tool_name", sorted(SENSITIVE_TOOLS))
    async def test_after_t4_owner_wa_sender_is_allowed_as_admin(
        self, authorizer: ToolAuthorizer, tool_name: str
    ) -> None:
        """Owner persona maps to the exact admin principal — full access,
        same as the JWT-authenticated admin path."""
        derived_role = _derive_wa_agent_role({"role": "creator"})
        assert derived_role is ROLE_ADMIN

        result = await authorizer.authorize(
            user_email=None,
            agent_role=derived_role,
            tool_name=tool_name,
            args={},
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
            )
            assert result.is_denied
