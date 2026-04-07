"""End-to-end smoke -- real Chromium, real example.com.

Opt-in: pytest -m integration tests/test_integration_smoke.py
"""
from __future__ import annotations

import importlib
import json

import pytest
from fastmcp import Client

pytestmark = pytest.mark.integration


def _extract_data(result: object) -> object:
    """Extract usable data from a FastMCP CallToolResult.

    Mirrors the helper in test_server_tools.py for consistency.
    """
    if hasattr(result, "data") and result.data is not None:
        return result.data

    if hasattr(result, "content") and result.content:
        first = result.content[0]
        text = first.text if hasattr(first, "text") else str(first)
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text

    return result


@pytest.fixture
async def real_mcp_client():
    """Real BrowserManager, real Chromium, in-memory MCP Client."""
    import nuzantara_mcp_browser.server as srv

    importlib.reload(srv)

    async with Client(srv.mcp) as client:
        yield client


async def test_real_navigate_example_com(real_mcp_client: Client) -> None:
    result = await real_mcp_client.call_tool(
        "browser_navigate", {"url": "https://example.com"}
    )
    data = _extract_data(result)
    assert isinstance(data, dict), f"Expected dict, got {type(data)}: {data}"
    assert data["title"] == "Example Domain"
    assert data["url"] == "https://example.com"
    assert data["status"] == 200


async def test_real_get_page_content_example_com(
    real_mcp_client: Client,
) -> None:
    result = await real_mcp_client.call_tool(
        "browser_get_page_content", {"url": "https://example.com"}
    )
    data = _extract_data(result)
    assert isinstance(data, dict), f"Expected dict, got {type(data)}: {data}"
    assert data["title"] == "Example Domain"
    assert "Example Domain" in data["content"]
    assert data["status"] == 200
