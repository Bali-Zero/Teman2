"""Unit tests for CRM tools."""

import pytest


def _register_tools(mock_mcp, mock_call, mock_call_safe):
    """Register CRM tools and capture them for testing."""
    from nuzantara_mcp.tools.crm import register

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
async def test_list_clients_default(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_clients with no filters should pass default params."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = [
        {"id": "1", "name": "John Doe", "status": "active"},
        {"id": "2", "name": "Jane Smith", "status": "prospect"},
    ]

    result = await tools["list_clients"]()
    assert result["count"] == 2
    assert len(result["clients"]) == 2
    mock_call.assert_called_once_with(
        "/api/crm/clients/", params={"limit": 50, "offset": 0}
    )


@pytest.mark.asyncio
async def test_list_clients_with_filters(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_clients should pass status and search filters."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = [{"id": "1", "name": "John", "status": "active"}]

    result = await tools["list_clients"](status="active", search="John")
    assert result["count"] == 1
    mock_call.assert_called_once_with(
        "/api/crm/clients/",
        params={"limit": 50, "offset": 0, "status": "active", "search": "John"},
    )


@pytest.mark.asyncio
async def test_list_clients_limit_capped(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_clients should cap limit at 200."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = []

    await tools["list_clients"](limit=500)
    call_args = mock_call.call_args
    assert call_args[1]["params"]["limit"] == 200


@pytest.mark.asyncio
async def test_list_clients_dict_response(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_clients should return dict responses as-is."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"clients": [], "count": 0, "total": 0}

    result = await tools["list_clients"]()
    assert result == {"clients": [], "count": 0, "total": 0}


@pytest.mark.asyncio
async def test_get_client(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_client should call correct endpoint with client_id."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"id": "abc-123", "name": "John Doe"}

    result = await tools["get_client"](client_id="abc-123")
    assert result["id"] == "abc-123"
    mock_call.assert_called_once_with("/api/crm/clients/abc-123")


@pytest.mark.asyncio
async def test_create_client_minimal(mock_mcp, mock_call, mock_call_safe) -> None:
    """create_client with required fields only."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"id": "new-1", "name": "John", "email": "john@test.com"}

    result = await tools["create_client"](
        name="John", email="john@test.com", nationality="Italian"
    )
    assert result["id"] == "new-1"
    mock_call.assert_called_once_with(
        "/api/crm/clients/",
        method="POST",
        json={"name": "John", "email": "john@test.com", "nationality": "Italian"},
    )


@pytest.mark.asyncio
async def test_create_client_full(mock_mcp, mock_call, mock_call_safe) -> None:
    """create_client with all optional fields."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"id": "new-2"}

    await tools["create_client"](
        name="Jane",
        email="jane@test.com",
        nationality="Australian",
        phone="+62812345678",
        notes="VIP client",
    )
    call_json = mock_call.call_args[1]["json"]
    assert call_json["phone"] == "+62812345678"
    assert call_json["notes"] == "VIP client"
