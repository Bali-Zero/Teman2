"""Unit tests for admin tools."""

import pytest

from nuzantara_mcp.tools.admin import register


def _register_tools(mock_mcp, mock_call, mock_call_safe):
    """Register admin tools and capture them."""
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
async def test_clock_in_default(mock_mcp, mock_call, mock_call_safe) -> None:
    """clock_in without member_id should POST empty body."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"timestamp": "2026-04-14T08:00:00Z"}

    result = await tools["clock_in"]()
    assert "timestamp" in result
    mock_call.assert_called_once_with(
        "/api/team-activity/clock-in", method="POST", json={}
    )


@pytest.mark.asyncio
async def test_clock_in_with_member(mock_mcp, mock_call, mock_call_safe) -> None:
    """clock_in with member_id should include it in payload."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"timestamp": "2026-04-14T08:00:00Z"}

    await tools["clock_in"](member_id="member-123")
    payload = mock_call.call_args[1]["json"]
    assert payload["member_id"] == "member-123"


@pytest.mark.asyncio
async def test_clock_out(mock_mcp, mock_call, mock_call_safe) -> None:
    """clock_out should POST to clock-out endpoint."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"hours_worked": 8.5}

    result = await tools["clock_out"]()
    assert result["hours_worked"] == 8.5
    mock_call.assert_called_once_with(
        "/api/team-activity/clock-out", method="POST", json={}
    )


@pytest.mark.asyncio
async def test_get_team_hours(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_team_hours should call correct period endpoint."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"members": []}

    await tools["get_team_hours"](period="monthly")
    mock_call.assert_called_once_with("/api/team-activity/hours/monthly")


@pytest.mark.asyncio
async def test_get_admin_logs(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_admin_logs should pass limit param."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"logs": []}

    await tools["get_admin_logs"](limit=25)
    mock_call.assert_called_once_with("/api/admin/logs", params={"limit": 25})
