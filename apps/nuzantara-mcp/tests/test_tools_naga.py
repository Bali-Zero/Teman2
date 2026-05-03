"""Unit tests for Naga research engine tools."""

import pytest

from nuzantara_mcp.tools.naga import register


def _register_tools(mock_mcp, mock_call, mock_call_safe):
    """Register naga tools and capture them."""
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
async def test_naga_research_defaults(mock_mcp, mock_call, mock_call_safe) -> None:
    """naga_research should POST with auto defaults."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"findings": [], "confidence": 0.8}

    result = await tools["naga_research"](query="KITAS processing time 2026")
    assert result["confidence"] == 0.8
    payload = mock_call.call_args[1]["json"]
    assert payload["query"] == "KITAS processing time 2026"
    assert payload["tier"] == "auto"
    assert payload["domain"] == "auto"
    assert payload["mode"] == "auto"
    assert payload["trusted_mode"] is False
    # Should use long timeout
    assert mock_call.call_args[1]["timeout"] == 1800


@pytest.mark.asyncio
async def test_naga_research_deep(mock_mcp, mock_call, mock_call_safe) -> None:
    """naga_research with tier=t3 should pass deep config."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"findings": []}

    await tools["naga_research"](
        query="PMK 28/2025 impact analysis",
        tier="t3",
        domain="tax",
        mode="verify",
        trusted_mode=True,
    )
    payload = mock_call.call_args[1]["json"]
    assert payload["tier"] == "t3"
    assert payload["domain"] == "tax"
    assert payload["mode"] == "verify"
    assert payload["trusted_mode"] is True


@pytest.mark.asyncio
async def test_naga_claims_search(mock_mcp, mock_call, mock_call_safe) -> None:
    """naga_claims_search should pass query and filters."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"claims": [{"text": "KITAS valid 2y", "verified": True}]}

    result = await tools["naga_claims_search"](
        query="KITAS validity", domain="visa", verification="verified", limit=5
    )
    assert len(result["claims"]) == 1
    params = mock_call.call_args[1]["params"]
    assert params["query"] == "KITAS validity"
    assert params["domain"] == "visa"
    assert params["verification"] == "verified"
    assert params["limit"] == 5


@pytest.mark.asyncio
async def test_naga_claims_search_minimal(mock_mcp, mock_call, mock_call_safe) -> None:
    """naga_claims_search with only query should omit optional params."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"claims": []}

    await tools["naga_claims_search"](query="tax filing")
    params = mock_call.call_args[1]["params"]
    assert "domain" not in params
    assert "verification" not in params


@pytest.mark.asyncio
async def test_naga_session_status(mock_mcp, mock_call, mock_call_safe) -> None:
    """naga_session_status should GET session by ID."""
    tools = _register_tools(mock_mcp, mock_call, mock_call_safe)
    mock_call.return_value = {"session_id": "s-1", "progress": 60, "step": "triangulation"}

    result = await tools["naga_session_status"](session_id="s-1")
    assert result["progress"] == 60
    mock_call.assert_called_once_with("/api/naga/session/s-1")
