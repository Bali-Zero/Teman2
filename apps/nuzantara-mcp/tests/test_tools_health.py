"""Unit tests for health tools."""

import pytest

from nuzantara_mcp.tools.health import register


@pytest.fixture
def health_tools(mock_mcp, mock_call, mock_call_safe):
    """Register health tools and return the mock _call for assertions."""
    register(mock_mcp, mock_call, mock_call_safe)
    return mock_call


@pytest.mark.asyncio
async def test_check_health(mock_mcp, mock_call, mock_call_safe) -> None:
    """check_health should call /health endpoint."""
    tools: dict = {}

    def capture_tool():
        def decorator(fn):
            tools[fn.__name__] = fn
            return fn
        return decorator

    mock_mcp.tool = capture_tool
    register(mock_mcp, mock_call, mock_call_safe)

    mock_call.return_value = {"status": "healthy", "version": "v100"}
    result = await tools["check_health"]()
    assert result == {"status": "healthy", "version": "v100"}
    mock_call.assert_called_once_with("/health")


@pytest.mark.asyncio
async def test_check_health_detailed(mock_mcp, mock_call, mock_call_safe) -> None:
    """check_health_detailed should call /health/detailed."""
    tools: dict = {}

    def capture_tool():
        def decorator(fn):
            tools[fn.__name__] = fn
            return fn
        return decorator

    mock_mcp.tool = capture_tool
    register(mock_mcp, mock_call, mock_call_safe)

    mock_call.return_value = {"services": {"search": "ok", "ai_client": "ok"}}
    result = await tools["check_health_detailed"]()
    assert "services" in result
    mock_call.assert_called_once_with("/health/detailed")


@pytest.mark.asyncio
async def test_get_qdrant_metrics(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_qdrant_metrics should call /health/metrics/qdrant."""
    tools: dict = {}

    def capture_tool():
        def decorator(fn):
            tools[fn.__name__] = fn
            return fn
        return decorator

    mock_mcp.tool = capture_tool
    register(mock_mcp, mock_call, mock_call_safe)

    mock_call.return_value = {"search_count": 100, "avg_latency_ms": 12.5}
    result = await tools["get_qdrant_metrics"]()
    assert result["search_count"] == 100
    mock_call.assert_called_once_with("/health/metrics/qdrant")
