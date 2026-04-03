"""Unit tests for Drive tools."""

import pytest

from nuzantara_mcp.tools.drive import register


def _register_tools(mock_mcp, mock_call, mock_call_safe):
    """Register drive tools and capture them."""
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
async def test_list_drive_files_default(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_drive_files with defaults should pass limit=30."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = [{"name": "doc.pdf", "type": "file"}]

    result = await tools["list_drive_files"]()
    mock_call.assert_called_once_with("/api/drive/files", params={"limit": 30})


@pytest.mark.asyncio
async def test_list_drive_files_with_folder(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_drive_files with folder_id should include it in params."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = []

    await tools["list_drive_files"](folder_id="folder-abc", limit=5)
    mock_call.assert_called_once_with(
        "/api/drive/files", params={"limit": 5, "folder_id": "folder-abc"}
    )


@pytest.mark.asyncio
async def test_list_drive_files_no_folder_omits_param(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_drive_files without folder_id should not include it in params."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = []

    await tools["list_drive_files"]()
    call_params = mock_call.call_args[1]["params"]
    assert "folder_id" not in call_params


@pytest.mark.asyncio
async def test_search_drive(mock_mcp, mock_call, mock_call_safe) -> None:
    """search_drive should pass query and limit."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"results": [{"name": "contract.pdf"}]}

    result = await tools["search_drive"](query="contract", limit=5)
    assert result["results"][0]["name"] == "contract.pdf"
    mock_call.assert_called_once_with(
        "/api/drive/search", params={"q": "contract", "limit": 5}
    )


@pytest.mark.asyncio
async def test_search_drive_default_limit(mock_mcp, mock_call, mock_call_safe) -> None:
    """search_drive default limit should be 10."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"results": []}

    await tools["search_drive"](query="test")
    call_params = mock_call.call_args[1]["params"]
    assert call_params["limit"] == 10


@pytest.mark.asyncio
async def test_create_drive_folder_minimal(mock_mcp, mock_call, mock_call_safe) -> None:
    """create_drive_folder with name only."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"id": "new-folder-id", "url": "https://drive.google.com/..."}

    result = await tools["create_drive_folder"](name="My Folder")
    assert result["id"] == "new-folder-id"
    mock_call.assert_called_once_with(
        "/api/drive/folders", method="POST", json={"name": "My Folder"}
    )


@pytest.mark.asyncio
async def test_create_drive_folder_with_parent(mock_mcp, mock_call, mock_call_safe) -> None:
    """create_drive_folder with parent_id."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"id": "child-id"}

    await tools["create_drive_folder"](name="Sub", parent_id="parent-123")
    call_json = mock_call.call_args[1]["json"]
    assert call_json["parent_id"] == "parent-123"
    assert call_json["name"] == "Sub"


@pytest.mark.asyncio
async def test_create_drive_folder_no_parent_omits_key(mock_mcp, mock_call, mock_call_safe) -> None:
    """create_drive_folder without parent_id should not include it in payload."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"id": "x"}

    await tools["create_drive_folder"](name="Root Folder")
    call_json = mock_call.call_args[1]["json"]
    assert "parent_id" not in call_json


@pytest.mark.asyncio
async def test_get_drive_storage_stats(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_drive_storage_stats should call /api/drive/stats."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"total_gb": 12.5, "files_count": 342}

    result = await tools["get_drive_storage_stats"]()
    assert result["total_gb"] == 12.5
    mock_call.assert_called_once_with("/api/drive/stats")


@pytest.mark.asyncio
async def test_create_client_drive_folder(mock_mcp, mock_call, mock_call_safe) -> None:
    """create_client_drive_folder should POST with client_id in URL."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"folder_id": "cf-1", "subfolders": ["Passport", "Visa"]}

    result = await tools["create_client_drive_folder"](client_id="client-uuid-abc")
    assert "subfolders" in result
    mock_call.assert_called_once_with(
        "/api/crm/drive-folders/client-uuid-abc", method="POST"
    )


@pytest.mark.asyncio
async def test_list_drive_files_error_propagates(mock_mcp, mock_call, mock_call_safe) -> None:
    """Errors from _call should propagate."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.side_effect = Exception("Connection refused")

    with pytest.raises(Exception, match="Connection refused"):
        await tools["list_drive_files"]()
