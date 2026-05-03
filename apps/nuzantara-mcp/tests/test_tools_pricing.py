"""Unit tests for pricing tools."""

import pytest

from nuzantara_mcp.tools.pricing import register


def _register_tools(mock_mcp, mock_call, mock_call_safe):
    """Register pricing tools and capture them."""
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
async def test_calculate_pricing_default(mock_mcp, mock_call, mock_call_safe) -> None:
    """calculate_pricing should POST with defaults."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call_safe.return_value = {
        "base_price": 20_000_000,
        "surcharges": 0,
        "total": 20_000_000,
        "currency": "IDR",
    }

    result = await tools["calculate_pricing"](service_type="kitas")
    assert result["total"] == 20_000_000
    mock_call_safe.assert_called_once_with(
        "/api/agents/pricing/calculate",
        method="POST",
        json={
            "service_type": "kitas",
            "complexity": "standard",
            "urgency": "normal",
        },
    )


@pytest.mark.asyncio
async def test_calculate_pricing_urgent(mock_mcp, mock_call, mock_call_safe) -> None:
    """calculate_pricing with urgency surcharge."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call_safe.return_value = {"total": 30_000_000, "surcharges": 10_000_000}

    result = await tools["calculate_pricing"](
        service_type="pt_pma", complexity="complex", urgency="express"
    )
    assert result["surcharges"] == 10_000_000
    call_json = mock_call_safe.call_args[1]["json"]
    assert call_json["urgency"] == "express"
    assert call_json["complexity"] == "complex"


@pytest.mark.asyncio
async def test_get_all_prices(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_all_prices should call /pricing/all."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call_safe.return_value = {"services": {"visa": [], "company": []}}

    result = await tools["get_all_prices"]()
    assert "services" in result
    mock_call_safe.assert_called_once_with("/api/pricing/all")


@pytest.mark.asyncio
async def test_search_service_pricing(mock_mcp, mock_call, mock_call_safe) -> None:
    """search_service_pricing should pass query param."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call_safe.return_value = {
        "results": [{"service": "KITAS", "price_idr": 2_500_000}]
    }

    result = await tools["search_service_pricing"](query="work permit investor")
    assert len(result["results"]) == 1
    mock_call_safe.assert_called_once_with(
        "/api/pricing/search", params={"q": "work permit investor"}
    )
