"""Unit tests for federation tools."""

import pytest

from nuzantara_mcp.tools.federation import register


def _register_tools(mock_mcp, mock_call, mock_call_safe):
    """Register federation tools and capture them."""
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
async def test_federation_send_basic(mock_mcp, mock_call, mock_call_safe) -> None:
    """federation_send should POST message to target node."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"id": "msg-1", "status": "sent"}

    result = await tools["federation_send"](to_node="pro", body="Hello from Air")
    assert result["status"] == "sent"
    payload = mock_call.call_args[1]["json"]
    assert payload["to_node"] == "pro"
    assert payload["body"] == "Hello from Air"
    assert payload["message_type"] == "message"
    assert payload["priority"] == "normal"


@pytest.mark.asyncio
async def test_federation_send_escalation(mock_mcp, mock_call, mock_call_safe) -> None:
    """federation_send escalation should set correct type and priority."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"id": "msg-2"}

    await tools["federation_send"](
        to_node="pro",
        body="Critical issue",
        subject="Alert",
        message_type="escalation",
        priority="urgent",
    )
    payload = mock_call.call_args[1]["json"]
    assert payload["message_type"] == "escalation"
    assert payload["priority"] == "urgent"
    assert payload["subject"] == "Alert"


@pytest.mark.asyncio
async def test_federation_inbox(mock_mcp, mock_call, mock_call_safe) -> None:
    """federation_inbox should fetch messages."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call_safe.return_value = {"messages": [], "count": 0}

    result = await tools["federation_inbox"](unread_only=True, limit=10)
    assert result["count"] == 0
    mock_call_safe.assert_called_once_with(
        "/api/federation/inbox?unread_only=true&limit=10"
    )


@pytest.mark.asyncio
async def test_federation_mark_read(mock_mcp, mock_call, mock_call_safe) -> None:
    """federation_mark_read should POST to mark endpoint."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"status": "read"}

    result = await tools["federation_mark_read"](message_id="msg-1")
    assert result["status"] == "read"
    mock_call.assert_called_once_with(
        "/api/federation/inbox/read/msg-1", method="POST"
    )


@pytest.mark.asyncio
async def test_federation_status(mock_mcp, mock_call, mock_call_safe) -> None:
    """federation_status should return unread counts."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call_safe.return_value = {"pro": 2, "air": 0, "broadcast": 1}

    result = await tools["federation_status"]()
    assert result["pro"] == 2
    mock_call_safe.assert_called_once_with("/api/federation/status")
