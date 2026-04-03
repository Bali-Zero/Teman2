"""Unit tests for Portal tools."""

import pytest

from nuzantara_mcp.tools.portal import register


def _register_tools(mock_mcp, mock_call, mock_call_safe):
    """Register portal tools and capture them."""
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
async def test_get_portal_dashboard(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_portal_dashboard should pass client_id as param."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {
        "active_practices": 2,
        "pending_documents": 1,
        "unread_messages": 3,
    }

    result = await tools["get_portal_dashboard"](client_id="client-abc")
    assert result["active_practices"] == 2
    mock_call.assert_called_once_with(
        "/api/portal/dashboard", params={"client_id": "client-abc"}
    )


@pytest.mark.asyncio
async def test_get_portal_visa_status(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_portal_visa_status should pass client_id as param."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {
        "type": "KITAS",
        "status": "processing",
        "expiry": "2027-01-15",
    }

    result = await tools["get_portal_visa_status"](client_id="client-xyz")
    assert result["type"] == "KITAS"
    mock_call.assert_called_once_with(
        "/api/portal/visa", params={"client_id": "client-xyz"}
    )


@pytest.mark.asyncio
async def test_list_portal_messages_default(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_portal_messages with defaults."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"messages": [{"subject": "Welcome"}]}

    result = await tools["list_portal_messages"](client_id="c-1")
    assert len(result["messages"]) == 1
    mock_call.assert_called_once_with(
        "/api/portal/messages",
        params={"client_id": "c-1", "limit": 20},
    )


@pytest.mark.asyncio
async def test_list_portal_messages_unread_only(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_portal_messages with unread_only=True should include the param."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"messages": []}

    await tools["list_portal_messages"](client_id="c-1", unread_only=True, limit=5)
    call_params = mock_call.call_args[1]["params"]
    assert call_params["unread_only"] is True
    assert call_params["limit"] == 5


@pytest.mark.asyncio
async def test_list_portal_messages_unread_false_omits(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_portal_messages with unread_only=False should not include it."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"messages": []}

    await tools["list_portal_messages"](client_id="c-1", unread_only=False)
    call_params = mock_call.call_args[1]["params"]
    assert "unread_only" not in call_params


@pytest.mark.asyncio
async def test_send_portal_message(mock_mcp, mock_call, mock_call_safe) -> None:
    """send_portal_message should POST with correct payload."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"id": "msg-1", "delivery_status": "sent"}

    result = await tools["send_portal_message"](
        client_id="c-2", subject="Update", body="Your visa is ready."
    )
    assert result["delivery_status"] == "sent"
    mock_call.assert_called_once_with(
        "/api/portal/messages",
        method="POST",
        json={
            "client_id": "c-2",
            "subject": "Update",
            "body": "Your visa is ready.",
        },
    )


@pytest.mark.asyncio
async def test_list_portal_documents_default(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_portal_documents without category filter."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"documents": [{"name": "passport.pdf"}]}

    result = await tools["list_portal_documents"](client_id="c-3")
    assert len(result["documents"]) == 1
    mock_call.assert_called_once_with(
        "/api/portal/documents", params={"client_id": "c-3"}
    )


@pytest.mark.asyncio
async def test_list_portal_documents_with_category(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_portal_documents with category filter."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"documents": []}

    await tools["list_portal_documents"](client_id="c-3", category="visa")
    call_params = mock_call.call_args[1]["params"]
    assert call_params["category"] == "visa"


@pytest.mark.asyncio
async def test_list_portal_documents_no_category_omits(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_portal_documents without category should not include it."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"documents": []}

    await tools["list_portal_documents"](client_id="c-3")
    call_params = mock_call.call_args[1]["params"]
    assert "category" not in call_params


@pytest.mark.asyncio
async def test_get_portal_timeline(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_portal_timeline should pass client_id."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {
        "timeline": [{"step": "Documents Submitted", "status": "completed"}]
    }

    result = await tools["get_portal_timeline"](client_id="c-4")
    assert result["timeline"][0]["status"] == "completed"
    mock_call.assert_called_once_with(
        "/api/portal/timeline", params={"client_id": "c-4"}
    )


@pytest.mark.asyncio
async def test_send_portal_message_error(mock_mcp, mock_call, mock_call_safe) -> None:
    """Error propagation from _call."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.side_effect = Exception("401 Unauthorized")

    with pytest.raises(Exception, match="401 Unauthorized"):
        await tools["send_portal_message"](
            client_id="c", subject="s", body="b"
        )
