"""Unit tests for Analytics tools."""

import pytest

from nuzantara_mcp.tools.analytics import register


def _register_tools(mock_mcp, mock_call, mock_call_safe):
    """Register analytics tools and capture them."""
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
async def test_get_completion_rates_default(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_completion_rates with default period."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"avg_completion": 0.85, "by_type": {"visa": 0.90}}

    result = await tools["get_completion_rates"]()
    assert result["avg_completion"] == 0.85
    mock_call.assert_called_once_with(
        "/api/analytics/completion-rates", params={"period": "30d"}
    )


@pytest.mark.asyncio
async def test_get_completion_rates_custom_period(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_completion_rates with custom period."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"avg_completion": 0.78}

    await tools["get_completion_rates"](period="90d")
    call_params = mock_call.call_args[1]["params"]
    assert call_params["period"] == "90d"


@pytest.mark.asyncio
async def test_get_response_times_default(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_response_times with default period."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"avg_response_ms": 1200}

    result = await tools["get_response_times"]()
    mock_call.assert_called_once_with(
        "/api/analytics/response-times", params={"period": "30d"}
    )


@pytest.mark.asyncio
async def test_get_response_times_custom_period(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_response_times with custom period."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {}

    await tools["get_response_times"](period="7d")
    call_params = mock_call.call_args[1]["params"]
    assert call_params["period"] == "7d"


@pytest.mark.asyncio
async def test_get_sla_compliance_default(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_sla_compliance with default period."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"compliance_pct": 97.5, "breaches": 3}

    result = await tools["get_sla_compliance"]()
    assert result["compliance_pct"] == 97.5
    mock_call.assert_called_once_with(
        "/api/analytics/sla-compliance", params={"period": "30d"}
    )


@pytest.mark.asyncio
async def test_get_revenue_analytics_default(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_revenue_analytics with default period."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"total_revenue": 500_000_000, "currency": "IDR"}

    result = await tools["get_revenue_analytics"]()
    assert result["total_revenue"] == 500_000_000
    mock_call.assert_called_once_with(
        "/api/analytics/revenue", params={"period": "30d"}
    )


@pytest.mark.asyncio
async def test_get_revenue_analytics_yearly(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_revenue_analytics with 1y period."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"total_revenue": 6_000_000_000}

    await tools["get_revenue_analytics"](period="1y")
    call_params = mock_call.call_args[1]["params"]
    assert call_params["period"] == "1y"


@pytest.mark.asyncio
async def test_get_query_analytics_default(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_query_analytics default period is 7d."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"query_volume": 1500, "success_rate": 0.92}

    result = await tools["get_query_analytics"]()
    assert result["success_rate"] == 0.92
    mock_call.assert_called_once_with(
        "/api/query-analytics/volume", params={"period": "7d"}
    )


@pytest.mark.asyncio
async def test_get_failed_queries_default(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_failed_queries with default limit."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"queries": [{"query": "unknown topic", "confidence": 0.1}]}

    result = await tools["get_failed_queries"]()
    assert len(result["queries"]) == 1
    mock_call.assert_called_once_with(
        "/api/query-analytics/failed", params={"limit": 20}
    )


@pytest.mark.asyncio
async def test_get_failed_queries_custom_limit(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_failed_queries with custom limit."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"queries": []}

    await tools["get_failed_queries"](limit=5)
    call_params = mock_call.call_args[1]["params"]
    assert call_params["limit"] == 5


@pytest.mark.asyncio
async def test_get_team_productivity_default(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_team_productivity with default period."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"members": [{"name": "A", "practices": 15}]}

    result = await tools["get_team_productivity"]()
    mock_call.assert_called_once_with(
        "/api/team-analytics/productivity", params={"period": "7d"}
    )


@pytest.mark.asyncio
async def test_get_team_productivity_monthly(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_team_productivity with 30d period."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {}

    await tools["get_team_productivity"](period="30d")
    call_params = mock_call.call_args[1]["params"]
    assert call_params["period"] == "30d"


@pytest.mark.asyncio
async def test_get_burnout_indicators(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_burnout_indicators should call correct endpoint."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {
        "risk_scores": [{"member": "A", "risk": "low"}],
        "recommendations": ["Distribute workload more evenly"],
    }

    result = await tools["get_burnout_indicators"]()
    assert "recommendations" in result
    mock_call.assert_called_once_with("/api/team-analytics/burnout")


@pytest.mark.asyncio
async def test_get_completion_rates_error(mock_mcp, mock_call, mock_call_safe) -> None:
    """Error propagation from _call."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.side_effect = Exception("Database connection lost")

    with pytest.raises(Exception, match="Database connection lost"):
        await tools["get_completion_rates"]()
