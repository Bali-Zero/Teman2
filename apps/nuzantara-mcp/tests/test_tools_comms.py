"""Unit tests for communication tools."""

import pytest

from nuzantara_mcp.tools.comms import register


def _register_tools(mock_mcp, mock_call, mock_call_safe):
    """Register comms tools and capture them."""
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
async def test_send_email_basic(mock_mcp, mock_call, mock_call_safe) -> None:
    """send_email should POST to notifications endpoint."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"success": True, "message": "sent"}

    result = await tools["send_email"](
        to="test@example.com", subject="Hello", body="Test body"
    )
    assert result["success"] is True
    mock_call.assert_called_once_with(
        "/api/notifications/send-email",
        method="POST",
        json={"to": "test@example.com", "subject": "Hello", "body": "Test body"},
    )


@pytest.mark.asyncio
async def test_send_email_with_cc(mock_mcp, mock_call, mock_call_safe) -> None:
    """send_email with CC should include cc in payload."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"success": True}

    await tools["send_email"](
        to="a@b.com", subject="Sub", body="Body", cc="cc@b.com"
    )
    payload = mock_call.call_args[1]["json"]
    assert payload["cc"] == "cc@b.com"


@pytest.mark.asyncio
async def test_list_emails_default(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_emails should default to inbox folder."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"emails": []}

    await tools["list_emails"]()
    mock_call.assert_called_once_with(
        "/api/zoho/emails", params={"folder": "inbox", "limit": 20}
    )


@pytest.mark.asyncio
async def test_list_emails_unread(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_emails with unread_only should include param."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"emails": []}

    await tools["list_emails"](unread_only=True)
    params = mock_call.call_args[1]["params"]
    assert params["unread_only"] is True


@pytest.mark.asyncio
async def test_search_emails(mock_mcp, mock_call, mock_call_safe) -> None:
    """search_emails should pass query and limit."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"results": []}

    await tools["search_emails"](query="invoice", limit=5)
    mock_call.assert_called_once_with(
        "/api/zoho/emails/search", params={"query": "invoice", "limit": 5}
    )


@pytest.mark.asyncio
async def test_send_whatsapp(mock_mcp, mock_call, mock_call_safe) -> None:
    """send_whatsapp should POST phone and message."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"status": "delivered"}

    result = await tools["send_whatsapp"](phone="+62812345678", message="Hello")
    assert result["status"] == "delivered"
    mock_call.assert_called_once_with(
        "/api/whatsapp/send",
        method="POST",
        json={"phone": "+62812345678", "message": "Hello"},
    )


@pytest.mark.asyncio
async def test_list_whatsapp_conversations(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_whatsapp_conversations should pass limit."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"conversations": []}

    await tools["list_whatsapp_conversations"](limit=10)
    mock_call.assert_called_once_with(
        "/api/whatsapp/conversations", params={"limit": 10}
    )


@pytest.mark.asyncio
async def test_list_telegram_conversations(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_telegram_conversations should pass limit."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"conversations": []}

    await tools["list_telegram_conversations"](limit=5)
    mock_call.assert_called_once_with(
        "/api/telegram/conversations", params={"limit": 5}
    )
