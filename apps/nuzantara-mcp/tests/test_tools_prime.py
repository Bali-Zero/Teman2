"""Unit tests for Prime Nexus geospatial tools."""

import pytest

from nuzantara_mcp.tools.prime import register


def _register_tools(mock_mcp, mock_call, mock_call_safe):
    """Register prime tools and capture them."""
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
async def test_zone_lookup_basic(mock_mcp, mock_call, mock_call_safe) -> None:
    """prime_zone_lookup without analysis should POST to resolve."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"zone_code": "K-3", "name": "Komersial 3"}

    result = await tools["prime_zone_lookup"](lat=-8.648, lng=115.132)
    assert result["zone_code"] == "K-3"
    mock_call.assert_called_once_with(
        "/api/prime/v2/resolve",
        method="POST",
        json={"lat": -8.648, "lng": 115.132},
    )


@pytest.mark.asyncio
async def test_zone_lookup_with_analysis(mock_mcp, mock_call, mock_call_safe) -> None:
    """prime_zone_lookup with include_analysis should POST to analyze."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"verdict": "GREEN", "score": 85}

    result = await tools["prime_zone_lookup"](
        lat=-8.648, lng=115.132, include_analysis=True, kbli_code="56101"
    )
    assert result["verdict"] == "GREEN"
    payload = mock_call.call_args[1]["json"]
    assert payload["kbli_code"] == "56101"
    assert payload["is_pma"] is True
    assert mock_call.call_args[1]["method"] == "POST"


@pytest.mark.asyncio
async def test_competitor_density(mock_mcp, mock_call, mock_call_safe) -> None:
    """prime_competitor_density should GET density for zone."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"total_companies": 150, "saturation": "HIGH"}

    result = await tools["prime_competitor_density"](zone_code="K-3")
    assert result["saturation"] == "HIGH"
    mock_call.assert_called_once_with(
        "/api/prime/v2/density", method="GET", params={"zone_code": "K-3"}
    )


@pytest.mark.asyncio
async def test_predict_zone(mock_mcp, mock_call, mock_call_safe) -> None:
    """prime_predict_zone should GET prediction for zone."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"trend": "improving", "trend_score": 0.7}

    result = await tools["prime_predict_zone"](zone_code="W-1")
    assert result["trend"] == "improving"
    mock_call.assert_called_once_with(
        "/api/prime/v2/predict", method="GET", params={"zone_code": "W-1"}
    )


@pytest.mark.asyncio
async def test_temporal_analysis(mock_mcp, mock_call, mock_call_safe) -> None:
    """prime_temporal_analysis should pass zone and period."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"buckets": [], "trend": "stable"}

    await tools["prime_temporal_analysis"](zone_code="K-3", period="3m")
    params = mock_call.call_args[1]["params"]
    assert params["zone_code"] == "K-3"
    assert params["period"] == "3m"
    assert params["granularity"] == "weekly"


@pytest.mark.asyncio
async def test_regulation_feed(mock_mcp, mock_call, mock_call_safe) -> None:
    """prime_regulation_feed should GET regulations for zone."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"articles": []}

    await tools["prime_regulation_feed"](zone_code="W-1", limit=5)
    params = mock_call.call_args[1]["params"]
    assert params["zone_code"] == "W-1"
    assert params["limit"] == "5"


@pytest.mark.asyncio
async def test_create_proposal(mock_mcp, mock_call, mock_call_safe) -> None:
    """prime_create_proposal should POST proposal data."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"token": "tok-abc", "url": "https://prime.balizero.com/p/tok-abc"}

    result = await tools["prime_create_proposal"](
        lat=-8.648, lng=115.132, zone_code="K-3",
        kbli_code="56101", verdict_label="GREEN", verdict_score=85,
    )
    assert "token" in result
    payload = mock_call.call_args[1]["json"]
    assert payload["zone_code"] == "K-3"
    assert payload["verdict_score"] == 85


@pytest.mark.asyncio
async def test_portfolio_advisor(mock_mcp, mock_call, mock_call_safe) -> None:
    """prime_portfolio_advisor should GET portfolio for client."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"health_pct": 82, "entities": []}

    result = await tools["prime_portfolio_advisor"](client_id=123)
    assert result["health_pct"] == 82
    mock_call.assert_called_once_with(
        "/api/prime/v2/portfolio", method="GET", params={"client_id": "123"}
    )
