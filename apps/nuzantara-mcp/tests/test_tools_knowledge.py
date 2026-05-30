"""Unit tests for Knowledge tools."""

import pytest

from nuzantara_mcp.tools.knowledge import register


def _register_tools(mock_mcp, mock_call, mock_call_safe):
    """Register knowledge tools and capture them."""
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
async def test_search_kbli_default(mock_mcp, mock_call, mock_call_safe) -> None:
    """search_kbli with default limit."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {
        "results": [{"kode_kbli": "56101", "judul": "Restoran"}]
    }

    result = await tools["search_kbli"](query="restaurant business")
    assert result["results"][0]["kode_kbli"] == "56101"
    mock_call.assert_called_once_with(
        "/api/v1/kbli-notebook/search",
        params={"query": "restaurant business", "limit": 10},
    )


@pytest.mark.asyncio
async def test_search_kbli_wraps_list_response(mock_mcp, mock_call, mock_call_safe) -> None:
    """search_kbli should always return FastMCP-compatible structured content."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = [{"kode_kbli": "56303", "judul": "Bar"}]

    result = await tools["search_kbli"](query="bar business")

    assert result == {"results": [{"kode_kbli": "56303", "judul": "Bar"}]}


@pytest.mark.asyncio
async def test_search_kbli_limit_capped_at_20(mock_mcp, mock_call, mock_call_safe) -> None:
    """search_kbli should cap limit at 20."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"results": []}

    await tools["search_kbli"](query="test", limit=50)
    call_params = mock_call.call_args[1]["params"]
    assert call_params["limit"] == 20


@pytest.mark.asyncio
async def test_search_kbli_limit_under_20(mock_mcp, mock_call, mock_call_safe) -> None:
    """search_kbli with limit < 20 should pass as-is."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"results": []}

    await tools["search_kbli"](query="test", limit=5)
    call_params = mock_call.call_args[1]["params"]
    assert call_params["limit"] == 5


@pytest.mark.asyncio
async def test_inspect_kbli(mock_mcp, mock_call, mock_call_safe) -> None:
    """inspect_kbli should call endpoint with code."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {
        "kode_kbli": "62010",
        "judul": "Aktivitas Pemrograman",
        "pma_status": "open",
    }

    result = await tools["inspect_kbli"](code="62010")
    assert result["pma_status"] == "open"
    mock_call.assert_called_once_with("/api/v1/kbli-notebook/inspect/62010")


@pytest.mark.asyncio
async def test_chat_kbli(mock_mcp, mock_call, mock_call_safe) -> None:
    """chat_kbli should POST with query."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {
        "answer": "For a restaurant...",
        "detected_codes": ["56101"],
    }

    result = await tools["chat_kbli"](query="I want to open a restaurant in Bali")
    assert "56101" in result["detected_codes"]
    mock_call.assert_called_once_with(
        "/api/v1/kbli-notebook/chat",
        method="POST",
        json={"query": "I want to open a restaurant in Bali"},
    )


@pytest.mark.asyncio
async def test_ask_legal_minimal(mock_mcp, mock_call, mock_call_safe) -> None:
    """ask_legal with default user_id and no session_id."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call_safe.return_value = {
        "answer": "For KITAS investor...",
        "sources": ["PP 28/2025"],
    }

    result = await tools["ask_legal"](question="How to get KITAS investor?")
    assert "sources" in result
    mock_call_safe.assert_called_once_with(
        "/api/agentic-rag/query",
        method="POST",
        json={"query": "How to get KITAS investor?", "user_id": "mcp-agent"},
        timeout=60,
    )


@pytest.mark.asyncio
async def test_ask_legal_with_session(mock_mcp, mock_call, mock_call_safe) -> None:
    """ask_legal with custom user_id and session_id."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call_safe.return_value = {"answer": "..."}

    await tools["ask_legal"](
        question="Follow up", user_id="user-123", session_id="sess-abc"
    )
    call_json = mock_call_safe.call_args[1]["json"]
    assert call_json["user_id"] == "user-123"
    assert call_json["session_id"] == "sess-abc"


@pytest.mark.asyncio
async def test_ask_legal_no_session_omits(mock_mcp, mock_call, mock_call_safe) -> None:
    """ask_legal without session_id should not include it."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call_safe.return_value = {"answer": "..."}

    await tools["ask_legal"](question="test")
    call_json = mock_call_safe.call_args[1]["json"]
    assert "session_id" not in call_json


@pytest.mark.asyncio
async def test_list_visa_types(mock_mcp, mock_call, mock_call_safe) -> None:
    """list_visa_types should call the correct endpoint."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call_safe.return_value = {
        "visa_types": [{"code": "kitas_investor", "name": "KITAS Investor"}]
    }

    result = await tools["list_visa_types"]()
    assert result["visa_types"][0]["code"] == "kitas_investor"
    mock_call_safe.assert_called_once_with("/api/knowledge/visa/")


@pytest.mark.asyncio
async def test_company_setup_can_use_visa_tools(
    mock_mcp, mock_call, mock_call_safe, monkeypatch
) -> None:
    """WhatsApp company setup flows may need visa context for mixed client questions."""
    monkeypatch.setenv("AGENT_ROLE", "company_setup")
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call_safe.return_value = {"visa_types": []}

    assert await tools["list_visa_types"]() == {"visa_types": []}

    mock_call_safe.return_value = {"code": "b211a"}
    assert await tools["get_visa_details"](visa_code="b211a") == {"code": "b211a"}


@pytest.mark.asyncio
async def test_get_visa_details(mock_mcp, mock_call, mock_call_safe) -> None:
    """get_visa_details should pass visa_code in URL."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call_safe.return_value = {
        "code": "b211a",
        "name": "Business Visa",
        "requirements": ["Sponsor letter"],
    }

    result = await tools["get_visa_details"](visa_code="b211a")
    assert result["code"] == "b211a"
    mock_call_safe.assert_called_once_with("/api/knowledge/visa/code/b211a")


@pytest.mark.asyncio
async def test_visualize_langgraph_default(mock_mcp, mock_call, mock_call_safe) -> None:
    """visualize_langgraph without subgraph."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"mermaid": "graph TD; A-->B"}

    result = await tools["visualize_langgraph"]()
    assert "mermaid" in result
    mock_call.assert_called_once_with("/api/kg/visualize", params={})


@pytest.mark.asyncio
async def test_visualize_langgraph_with_subgraph(mock_mcp, mock_call, mock_call_safe) -> None:
    """visualize_langgraph with subgraph filter."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"mermaid": "graph TD; visa-->check"}

    await tools["visualize_langgraph"](subgraph="visa")
    call_params = mock_call.call_args[1]["params"]
    assert call_params["subgraph"] == "visa"


@pytest.mark.asyncio
async def test_search_kbli_error(mock_mcp, mock_call, mock_call_safe) -> None:
    """Error propagation from _call."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.side_effect = Exception("503 Service Unavailable")

    with pytest.raises(Exception, match="503"):
        await tools["search_kbli"](query="test")
