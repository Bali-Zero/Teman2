"""Unit tests for LAM memory tools."""

import pytest

from nuzantara_mcp.tools.memory import register


def _register_tools(mock_mcp, mock_call, mock_call_safe):
    """Register memory tools and capture them."""
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
async def test_save_episode_defaults(mock_mcp, mock_call, mock_call_safe) -> None:
    """save_episode should POST with defaults (empty tags and metadata)."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call_safe.return_value = {"id": "ep-1", "status": "saved"}

    result = await tools["save_episode"](content="Fixed a bug in KG")
    assert result["status"] == "saved"
    payload = mock_call_safe.call_args[1]["json"]
    assert payload["content"] == "Fixed a bug in KG"
    assert payload["agent"] == "main"
    assert payload["tags"] == []
    assert payload["metadata"] == {}


@pytest.mark.asyncio
async def test_save_episode_with_tags(mock_mcp, mock_call, mock_call_safe) -> None:
    """save_episode should include tags and metadata when provided."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call_safe.return_value = {"id": "ep-2", "status": "saved"}

    await tools["save_episode"](
        content="Onboarded client",
        agent="visa_specialist",
        tags=["onboarding", "kitas"],
        outcome="success",
        metadata={"client_id": "c-123"},
    )
    payload = mock_call_safe.call_args[1]["json"]
    assert payload["tags"] == ["onboarding", "kitas"]
    assert payload["metadata"] == {"client_id": "c-123"}
    assert payload["outcome"] == "success"


@pytest.mark.asyncio
async def test_recall_similar(mock_mcp, mock_call, mock_call_safe) -> None:
    """recall_similar should POST query for semantic search."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call_safe.return_value = {"results": [], "query": "visa issue"}

    result = await tools["recall_similar"](query="visa issue", limit=3)
    assert result["query"] == "visa issue"
    payload = mock_call_safe.call_args[1]["json"]
    assert payload["query"] == "visa issue"
    assert payload["limit"] == 3
    assert payload["agent"] is None


@pytest.mark.asyncio
async def test_recall_similar_with_agent(mock_mcp, mock_call, mock_call_safe) -> None:
    """recall_similar should filter by agent when specified."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call_safe.return_value = {"results": []}

    await tools["recall_similar"](query="test", agent="coder")
    payload = mock_call_safe.call_args[1]["json"]
    assert payload["agent"] == "coder"


@pytest.mark.asyncio
async def test_list_recent_episodes(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_recent_episodes should GET with limit."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call_safe.return_value = {"episodes": [], "total": 0}

    result = await tools["list_recent_episodes"](limit=5)
    assert result["total"] == 0
    mock_call_safe.assert_called_once_with(
        "/api/memory/lam/episodes", params={"limit": 5}
    )


@pytest.mark.asyncio
async def test_delete_episode(mock_mcp, mock_call, mock_call_safe) -> None:
    """delete_episode should DELETE by ID."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call_safe.return_value = {"status": "deleted", "id": "ep-99"}

    result = await tools["delete_episode"](episode_id="ep-99")
    assert result["status"] == "deleted"
    mock_call_safe.assert_called_once_with(
        "/api/memory/lam/episodes/ep-99", method="DELETE"
    )
