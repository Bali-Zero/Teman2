"""Small additive edge tests for ToolAuthorizer coverage branches."""

from __future__ import annotations

from typing import Any

import pytest

from backend.services.agents.team_agent_config import ROLE_VISA_SPECIALIST, AgentRole
from backend.services.agents.tool_authorizer import AuthResult, ToolAuthorizer


class _ScopedAuthorizer(ToolAuthorizer):
    def _check_client_scope(
        self,
        user_email: str | None,
        agent_role: AgentRole,
        tool_name: str,
        args: dict[str, Any],
    ) -> AuthResult | None:
        _ = (user_email, agent_role, tool_name)
        return AuthResult.deny("client scope denied", args)


@pytest.mark.asyncio
async def test_authorize_returns_client_scope_result_before_allowed_path() -> None:
    result = await _ScopedAuthorizer().authorize(
        user_email="agent@example.test",
        agent_role=ROLE_VISA_SPECIALIST,
        tool_name="vector_search",
        args={"client_id": 42},
    )

    assert result.is_denied
    assert result.reason == "client scope denied"
    assert result.args == {"client_id": 42}


def test_confirmation_preview_truncates_long_args_and_counts_extra_args() -> None:
    long_value = "x" * 80
    preview = ToolAuthorizer._build_confirmation_preview(
        ROLE_VISA_SPECIALIST,
        "image_generation",
        {
            "prompt": long_value,
            "style": "documentary",
            "width": 1024,
            "height": 1024,
            "seed": "fixed",
        },
    )

    assert long_value not in preview
    assert "prompt=" in preview
    assert "(+1 more)" in preview
    assert "image_generation" in preview
