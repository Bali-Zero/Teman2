"""Unit tests for FastMCP server using in-memory Client pattern.

We patch make_browser_manager to return a MagicMock, then use
FastMCP's Client(mcp) to call tools through the real MCP protocol
in-memory. No real Chromium launch.

FastMCP 3.2.0 Client.call_tool returns a CallToolResult dataclass:
  - .data: structured output (parsed from structuredContent)
  - .content: list of ContentBlock (TextContent, etc.)
  - .structured_content: raw dict from MCP protocol
  - .is_error: bool
"""
from __future__ import annotations

import importlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp import Client


@pytest.fixture
def fake_page() -> MagicMock:
    page = MagicMock()
    page.title = AsyncMock(return_value="Mocked Title")
    page.content = AsyncMock(return_value="<html>hi</html>")

    locator = MagicMock()
    locator.inner_text = AsyncMock(return_value="located-text")
    locator.click = AsyncMock()
    locator.fill = AsyncMock()
    page.locator = MagicMock(return_value=locator)

    page.accessibility = MagicMock(
        snapshot=AsyncMock(
            return_value={"role": "WebArea", "name": "Mocked Title"}
        )
    )
    page.context = MagicMock()
    return page


@pytest.fixture
def fake_manager(fake_page: MagicMock) -> MagicMock:
    class _PageCtx:
        async def __aenter__(self):
            return fake_page

        async def __aexit__(self, *args):
            return None

    mgr = MagicMock()
    mgr.initialize = AsyncMock()
    mgr.close = AsyncMock()
    mgr.get_page = MagicMock(return_value=_PageCtx())
    mgr.get_page_content = AsyncMock(
        return_value={
            "url": "https://example.com",
            "title": "Mocked Title",
            "content": "<html>hi</html>",
            "status": 200,
        }
    )
    return mgr


def _extract_data(result: object) -> object:
    """Extract usable data from a FastMCP CallToolResult.

    FastMCP 3.2.0 call_tool returns a CallToolResult with:
      .data  — structured output (may be dict, str, or None)
      .content — list of ContentBlock (TextContent with .text attr)

    If .data is populated, use it directly. Otherwise fall back
    to parsing the first TextContent block from .content.
    """
    if hasattr(result, "data") and result.data is not None:
        return result.data

    # Fallback: parse from content blocks
    if hasattr(result, "content") and result.content:
        first = result.content[0]
        text = first.text if hasattr(first, "text") else str(first)
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text

    return result


@pytest.fixture
async def mcp_client(fake_manager: MagicMock):
    """In-memory FastMCP Client with the fake BrowserManager.

    Patches make_browser_manager before re-importing server so the
    module-scope browser_manager uses the fake.
    """
    with patch(
        "nuzantara_mcp_browser.manager_factory.make_browser_manager",
        return_value=fake_manager,
    ):
        import nuzantara_mcp_browser.server as srv

        importlib.reload(srv)

        async with Client(srv.mcp) as client:
            yield client


async def test_list_tools_returns_six(mcp_client: Client) -> None:
    tools = await mcp_client.list_tools()
    names = {t.name for t in tools}
    expected = {
        "browser_navigate",
        "browser_get_page_content",
        "browser_snapshot",
        "browser_click",
        "browser_type",
        "browser_extract_text",
    }
    assert names == expected, f"Tool mismatch: {names ^ expected}"


async def test_browser_navigate(mcp_client: Client) -> None:
    result = await mcp_client.call_tool(
        "browser_navigate", {"url": "https://example.com"}
    )
    data = _extract_data(result)
    assert isinstance(data, dict), f"Expected dict, got {type(data)}: {data}"
    assert data["title"] == "Mocked Title"
    assert data["url"] == "https://example.com"
    assert data["status"] == 200


async def test_browser_get_page_content(mcp_client: Client) -> None:
    result = await mcp_client.call_tool(
        "browser_get_page_content", {"url": "https://example.com"}
    )
    data = _extract_data(result)
    assert isinstance(data, dict), f"Expected dict, got {type(data)}: {data}"
    assert data["title"] == "Mocked Title"
    assert "<html>" in data["content"]
    assert data["status"] == 200


async def test_browser_snapshot(mcp_client: Client) -> None:
    result = await mcp_client.call_tool(
        "browser_snapshot", {"url": "https://example.com"}
    )
    data = _extract_data(result)
    assert isinstance(data, dict), f"Expected dict, got {type(data)}: {data}"
    assert data["role"] == "WebArea"
    assert data["name"] == "Mocked Title"


async def test_browser_click(
    mcp_client: Client, fake_page: MagicMock
) -> None:
    result = await mcp_client.call_tool(
        "browser_click",
        {"url": "https://example.com", "selector": "button#submit"},
    )
    data = _extract_data(result)
    assert isinstance(data, dict), f"Expected dict, got {type(data)}: {data}"
    assert data["clicked"] is True
    fake_page.locator.assert_called_with("button#submit")
    fake_page.locator.return_value.click.assert_awaited_once()


async def test_browser_type(
    mcp_client: Client, fake_page: MagicMock
) -> None:
    result = await mcp_client.call_tool(
        "browser_type",
        {
            "url": "https://example.com",
            "selector": "input#q",
            "text": "hello",
        },
    )
    data = _extract_data(result)
    assert isinstance(data, dict), f"Expected dict, got {type(data)}: {data}"
    assert data["typed"] == "hello"
    fake_page.locator.return_value.fill.assert_awaited_with("hello")


async def test_browser_extract_text(mcp_client: Client) -> None:
    result = await mcp_client.call_tool(
        "browser_extract_text",
        {"url": "https://example.com", "selector": "h1"},
    )
    data = _extract_data(result)
    assert data == "located-text", f"Expected 'located-text', got {data!r}"
