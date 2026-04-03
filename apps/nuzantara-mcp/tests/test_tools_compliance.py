"""Unit tests for Compliance tools."""

import pytest

from nuzantara_mcp.tools.compliance import register


def _register_tools(mock_mcp, mock_call, mock_call_safe):
    """Register compliance tools and capture them."""
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
async def test_track_compliance_required_fields(mock_mcp, mock_call, mock_call_safe) -> None:
    """track_compliance with required fields only."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"id": "comp-1", "alerts": [60, 30, 7]}

    result = await tools["track_compliance"](
        client_id="client-1",
        compliance_type="visa_expiry",
        title="KITAS Expiry",
        description="KITAS expires soon",
        deadline="2026-06-15",
    )
    assert result["id"] == "comp-1"
    mock_call.assert_called_once_with(
        "/api/agents/compliance/track",
        method="POST",
        json={
            "client_id": "client-1",
            "compliance_type": "visa_expiry",
            "title": "KITAS Expiry",
            "description": "KITAS expires soon",
            "deadline": "2026-06-15",
        },
    )


@pytest.mark.asyncio
async def test_track_compliance_with_cost_and_docs(mock_mcp, mock_call, mock_call_safe) -> None:
    """track_compliance with estimated_cost and required_documents."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"id": "comp-2"}

    await tools["track_compliance"](
        client_id="client-2",
        compliance_type="tax_filing",
        title="SPT Tahunan",
        description="Annual tax filing",
        deadline="2026-03-31",
        estimated_cost=5_000_000.0,
        required_documents=["NPWP", "Bukti Potong"],
    )
    call_json = mock_call.call_args[1]["json"]
    assert call_json["estimated_cost"] == 5_000_000.0
    assert call_json["required_documents"] == ["NPWP", "Bukti Potong"]


@pytest.mark.asyncio
async def test_track_compliance_omits_none_optionals(mock_mcp, mock_call, mock_call_safe) -> None:
    """track_compliance should not include optional fields when None."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"id": "comp-3"}

    await tools["track_compliance"](
        client_id="c", compliance_type="license_renewal",
        title="T", description="D", deadline="2026-12-01",
    )
    call_json = mock_call.call_args[1]["json"]
    assert "estimated_cost" not in call_json
    assert "required_documents" not in call_json


@pytest.mark.asyncio
async def test_track_compliance_zero_cost_included(mock_mcp, mock_call, mock_call_safe) -> None:
    """track_compliance with estimated_cost=0 should still include it."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"id": "comp-4"}

    await tools["track_compliance"](
        client_id="c", compliance_type="visa_expiry",
        title="T", description="D", deadline="2026-12-01",
        estimated_cost=0.0,
    )
    call_json = mock_call.call_args[1]["json"]
    assert call_json["estimated_cost"] == 0.0


@pytest.mark.asyncio
async def test_get_compliance_alerts_default(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_compliance_alerts with no filters."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"alerts": [{"severity": "CRITICAL"}]}

    result = await tools["get_compliance_alerts"]()
    assert len(result["alerts"]) == 1
    mock_call.assert_called_once_with(
        "/api/agents/compliance/alerts",
        params={"auto_notify": "false"},
    )


@pytest.mark.asyncio
async def test_get_compliance_alerts_with_filters(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_compliance_alerts with client_id and severity."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"alerts": []}

    await tools["get_compliance_alerts"](
        client_id="client-x", severity="URGENT", auto_notify=True
    )
    call_params = mock_call.call_args[1]["params"]
    assert call_params["client_id"] == "client-x"
    assert call_params["severity"] == "URGENT"
    assert call_params["auto_notify"] == "true"


@pytest.mark.asyncio
async def test_get_client_compliance(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_client_compliance should call correct endpoint."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"items": [{"type": "visa_expiry", "status": "active"}]}

    result = await tools["get_client_compliance"](client_id="client-99")
    assert result["items"][0]["type"] == "visa_expiry"
    mock_call.assert_called_once_with("/api/agents/compliance/client/client-99")


@pytest.mark.asyncio
async def test_get_compliance_summary(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_compliance_summary should call alerts with CRITICAL severity."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"total_items": 15, "by_severity": {"CRITICAL": 3}}

    result = await tools["get_compliance_summary"]()
    assert result["total_items"] == 15
    mock_call.assert_called_once_with(
        "/api/agents/compliance/alerts",
        params={"severity": "CRITICAL"},
    )


@pytest.mark.asyncio
async def test_get_compliance_alerts_error(mock_mcp, mock_call, mock_call_safe) -> None:
    """Error propagation from _call."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.side_effect = Exception("timeout")

    with pytest.raises(Exception, match="timeout"):
        await tools["get_compliance_alerts"]()
