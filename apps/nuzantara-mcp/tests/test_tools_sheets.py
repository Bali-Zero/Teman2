"""Unit tests for sheets tools."""

import pytest

from nuzantara_mcp.tools.sheets import register


def _register_tools(mock_mcp, mock_call, mock_call_safe):
    """Register sheets tools and capture them."""
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
async def test_read_sheet_uses_post(mock_mcp, mock_call, mock_call_safe) -> None:
    """read_sheet should use POST (not GET) to avoid A1 notation escaping issues."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"values": [["A", "B"], ["1", "2"]]}

    result = await tools["read_sheet"](
        spreadsheet_id="abc123", range="Company!A1:Z100"
    )
    assert "values" in result
    mock_call.assert_called_once_with(
        "/api/sheets/read",
        method="POST",
        json={"spreadsheet_id": "abc123", "range": "Company!A1:Z100"},
    )


@pytest.mark.asyncio
async def test_write_sheet(mock_mcp, mock_call, mock_call_safe) -> None:
    """write_sheet should POST with spreadsheet_id, range, and values."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"updated_cells": 6}

    result = await tools["write_sheet"](
        spreadsheet_id="abc123",
        range="Sheet1!A1:C2",
        values=[["a", "b", "c"], ["1", "2", "3"]],
    )
    assert result["updated_cells"] == 6
    payload = mock_call.call_args[1]["json"]
    assert payload["spreadsheet_id"] == "abc123"
    assert len(payload["values"]) == 2


@pytest.mark.asyncio
async def test_update_sheet_row(mock_mcp, mock_call, mock_call_safe) -> None:
    """update_sheet_row should POST with row details."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"updated_range": "Company!D5:F5"}

    await tools["update_sheet_row"](
        spreadsheet_id="abc123",
        sheet_name="Company",
        row_number=5,
        column_start="D",
        values=["val1", "val2", "val3"],
    )
    payload = mock_call.call_args[1]["json"]
    assert payload["sheet_name"] == "Company"
    assert payload["row_number"] == 5
    assert payload["column_start"] == "D"


@pytest.mark.asyncio
async def test_find_sheet_row(mock_mcp, mock_call, mock_call_safe) -> None:
    """find_sheet_row should POST search criteria."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"row_number": 7}

    result = await tools["find_sheet_row"](
        spreadsheet_id="abc123",
        range="Company!A:C",
        search_value="Bali Zero",
        search_column=1,
    )
    assert result["row_number"] == 7
    payload = mock_call.call_args[1]["json"]
    assert payload["search_value"] == "Bali Zero"
    assert payload["search_column"] == 1
