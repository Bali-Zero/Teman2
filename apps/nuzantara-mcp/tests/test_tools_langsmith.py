"""Unit tests for LangSmith observability tools."""

from unittest.mock import AsyncMock, patch

import pytest

from nuzantara_mcp.tools.langsmith import register


def _register_tools(mock_mcp, mock_call, mock_call_safe):
    """Register langsmith tools and capture them."""
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
async def test_langsmith_recent_runs(mock_mcp, mock_call, mock_call_safe) -> None:
    """langsmith_recent_runs should return formatted run list."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)

    mock_runs = [
        {
            "id": "run-1",
            "name": "query",
            "status": "success",
            "error": None,
            "total_time": 1.5,
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "start_time": "2026-04-14T10:00:00Z",
        }
    ]

    with patch("nuzantara_mcp.tools.langsmith._ls_get", new_callable=AsyncMock) as mock_ls:
        mock_ls.return_value = mock_runs
        result = await tools["langsmith_recent_runs"](limit=5)

    assert result["count"] == 1
    assert result["runs"][0]["id"] == "run-1"
    assert result["runs"][0]["latency_ms"] == 1500


@pytest.mark.asyncio
async def test_langsmith_recent_runs_error_only(mock_mcp, mock_call, mock_call_safe) -> None:
    """langsmith_recent_runs with error_only should set error param."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)

    with patch("nuzantara_mcp.tools.langsmith._ls_get", new_callable=AsyncMock) as mock_ls:
        mock_ls.return_value = []
        await tools["langsmith_recent_runs"](error_only=True)

    params = mock_ls.call_args[1]["params"]
    assert params["error"] is True


@pytest.mark.asyncio
async def test_langsmith_recent_runs_caps_limit(mock_mcp, mock_call, mock_call_safe) -> None:
    """langsmith_recent_runs should cap limit at 50."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)

    with patch("nuzantara_mcp.tools.langsmith._ls_get", new_callable=AsyncMock) as mock_ls:
        mock_ls.return_value = []
        await tools["langsmith_recent_runs"](limit=999)

    params = mock_ls.call_args[1]["params"]
    assert params["limit"] == 50


@pytest.mark.asyncio
async def test_langsmith_run_detail(mock_mcp, mock_call, mock_call_safe) -> None:
    """langsmith_run_detail should fetch run and children."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)

    with patch("nuzantara_mcp.tools.langsmith._ls_get", new_callable=AsyncMock) as mock_ls:
        mock_ls.side_effect = [
            # First call: run detail
            {
                "id": "run-1", "name": "query", "status": "success",
                "error": None, "inputs": {"q": "test"}, "outputs": {"a": "result"},
                "total_time": 2.0, "prompt_tokens": 200, "completion_tokens": 100,
                "start_time": "2026-04-14T10:00:00Z",
            },
            # Second call: children
            [{"name": "retriever", "status": "success", "error": None, "total_time": 0.5}],
        ]
        result = await tools["langsmith_run_detail"](run_id="run-1")

    assert result["id"] == "run-1"
    assert result["latency_ms"] == 2000
    assert len(result["nodes"]) == 1
    assert result["nodes"][0]["name"] == "retriever"


@pytest.mark.asyncio
async def test_langsmith_project_stats(mock_mcp, mock_call, mock_call_safe) -> None:
    """langsmith_project_stats should compute aggregate metrics."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)

    runs = [
        {"status": "success", "total_time": 1.0, "prompt_tokens": 100, "completion_tokens": 50},
        {"status": "error", "total_time": 0.5, "prompt_tokens": 80, "completion_tokens": 0},
        {"status": "success", "total_time": 2.0, "prompt_tokens": 150, "completion_tokens": 75},
    ]

    with patch("nuzantara_mcp.tools.langsmith._ls_get", new_callable=AsyncMock) as mock_ls:
        mock_ls.return_value = runs
        result = await tools["langsmith_project_stats"]()

    assert result["total_runs"] == 3
    assert result["error_count"] == 1
    assert result["error_rate_pct"] == pytest.approx(33.3, abs=0.1)
    assert result["total_tokens"] == 455  # 100+50+80+0+150+75


@pytest.mark.asyncio
async def test_langsmith_project_stats_no_runs(mock_mcp, mock_call, mock_call_safe) -> None:
    """langsmith_project_stats should handle empty project."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)

    with patch("nuzantara_mcp.tools.langsmith._ls_get", new_callable=AsyncMock) as mock_ls:
        mock_ls.return_value = []
        result = await tools["langsmith_project_stats"]()

    assert result["total_runs"] == 0
    assert "message" in result


@pytest.mark.asyncio
async def test_langsmith_handles_api_error(mock_mcp, mock_call, mock_call_safe) -> None:
    """langsmith tools should return error dict on API failure."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)

    with patch("nuzantara_mcp.tools.langsmith._ls_get", new_callable=AsyncMock) as mock_ls:
        mock_ls.side_effect = Exception("API key invalid")
        result = await tools["langsmith_recent_runs"]()

    assert "error" in result
    assert "API key invalid" in result["error"]
