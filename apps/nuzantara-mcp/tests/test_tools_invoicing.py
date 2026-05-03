"""Unit tests for invoicing tools."""

import pytest

from nuzantara_mcp.tools.invoicing import register


def _register_tools(mock_mcp, mock_call, mock_call_safe):
    """Register invoicing tools and capture them."""
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
async def test_regenerate_invoice(mock_mcp, mock_call, mock_call_safe) -> None:
    """regenerate_invoice should POST to regenerate endpoint."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {
        "invoice_number": "INV-2026-001",
        "drive_link": "https://drive.google.com/file/abc",
    }

    result = await tools["regenerate_invoice"](practice_id=42)
    assert result["invoice_number"] == "INV-2026-001"
    mock_call.assert_called_once_with(
        "/api/crm/practices/42/regenerate-invoice", method="POST"
    )


@pytest.mark.asyncio
async def test_get_practice_invoice(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_practice_invoice should GET invoice details."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"number": "INV-001", "amount": 25_000_000, "status": "paid"}

    result = await tools["get_practice_invoice"](practice_id=42)
    assert result["status"] == "paid"
    mock_call.assert_called_once_with("/api/crm/practices/42/invoice")


@pytest.mark.asyncio
async def test_list_pending_invoices_default(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_pending_invoices should default to unpaid status."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"invoices": []}

    await tools["list_pending_invoices"]()
    mock_call.assert_called_once_with(
        "/api/crm/invoices", params={"status": "unpaid", "limit": 50}
    )


@pytest.mark.asyncio
async def test_list_pending_invoices_overdue(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_pending_invoices should support overdue filter."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"invoices": [{"id": 1, "status": "overdue"}]}

    result = await tools["list_pending_invoices"](status="overdue", limit=10)
    assert len(result["invoices"]) == 1
    params = mock_call.call_args[1]["params"]
    assert params["status"] == "overdue"
    assert params["limit"] == 10
