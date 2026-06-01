"""Unit tests for Guardian tools."""

import pytest

from nuzantara_mcp.tools.guardian import register


def _register_tools(mock_mcp, mock_call, mock_call_safe) -> dict:
    """Register Guardian tools and capture them."""
    tools: dict = {}

    def capture_tool():
        def decorator(fn):
            tools[fn.__name__] = fn
            return fn

        return decorator

    mock_mcp.tool = capture_tool
    register(mock_mcp, mock_call, mock_call_safe)
    return tools


@pytest.mark.asyncio
async def test_guardian_recent_decisions_uses_admin_auth(
    mock_mcp,
    mock_call,
    mock_call_safe,
) -> None:
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"decisions": [], "total": 0}

    result = await tools["guardian_recent_decisions"](
        last=12,
        component="rbac",
        severity="high",
        limit=25,
    )

    assert result == {"decisions": [], "total": 0}
    mock_call.assert_called_once_with(
        "/api/guardian/decisions",
        params={
            "last": 12,
            "limit": 25,
            "component": "rbac",
            "severity": "high",
        },
        admin=True,
    )


@pytest.mark.asyncio
async def test_guardian_risk_score_uses_admin_auth(
    mock_mcp,
    mock_call,
    mock_call_safe,
) -> None:
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"current": None, "trend": []}

    await tools["guardian_risk_score"]()

    mock_call.assert_called_once_with("/api/guardian/risk-score", admin=True)


@pytest.mark.asyncio
async def test_guardian_risk_score_history_uses_admin_auth(
    mock_mcp,
    mock_call,
    mock_call_safe,
) -> None:
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"days": 7, "scores": []}

    await tools["guardian_risk_score_history"](days=7)

    mock_call.assert_called_once_with(
        "/api/guardian/risk-score/history",
        params={"days": 7},
        admin=True,
    )
