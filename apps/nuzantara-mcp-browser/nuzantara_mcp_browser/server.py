"""FastMCP server exposing stealth browser operations.

Uses FastMCP 3.2.0 API:
- @mcp.tool decorator (no parens)
- @lifespan decorator from fastmcp.server.lifespan
- lifespan= constructor param for startup/shutdown
"""
from __future__ import annotations

from typing import Any, AsyncIterator

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan

from nuzantara_mcp_browser.manager_factory import make_browser_manager

browser_manager = make_browser_manager()


@lifespan
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    """Initialize browser on startup, close on shutdown."""
    await browser_manager.initialize()
    try:
        yield {"browser_manager": browser_manager}
    finally:
        await browser_manager.close()


mcp = FastMCP(
    name="nuzantara-mcp-browser",
    instructions=(
        "Stealth Playwright browser tools. Use for headless automation "
        "where claude-in-chrome is not applicable. All contexts share "
        "five stealth patches (webdriver, chrome.runtime, navigator, "
        "permissions, canvas noise). Prefer browser_get_page_content for "
        "one-shot HTML fetch; use the finer-grained tools for multi-step "
        "interactions."
    ),
    lifespan=app_lifespan,
)


@mcp.tool
async def browser_navigate(url: str) -> dict[str, Any]:
    """Navigate to a URL and return {url, title, status}."""
    async with browser_manager.get_page(url) as page:
        title = await page.title()
        return {"url": url, "title": title, "status": 200}


@mcp.tool
async def browser_get_page_content(url: str) -> dict[str, Any]:
    """Fetch URL and return {url, title, content, status}."""
    return await browser_manager.get_page_content(url)


@mcp.tool
async def browser_snapshot(url: str) -> dict[str, Any]:
    """Return the accessibility tree snapshot of a URL."""
    async with browser_manager.get_page(url) as page:
        snap = await page.accessibility.snapshot()
        return snap or {}


@mcp.tool
async def browser_click(url: str, selector: str) -> dict[str, Any]:
    """Navigate and click the first element matching the selector."""
    async with browser_manager.get_page(url) as page:
        await page.locator(selector).click()
        return {"url": url, "selector": selector, "clicked": True}


@mcp.tool
async def browser_type(url: str, selector: str, text: str) -> dict[str, Any]:
    """Navigate and fill text into the first element matching the selector."""
    async with browser_manager.get_page(url) as page:
        await page.locator(selector).fill(text)
        return {"url": url, "selector": selector, "typed": text}


@mcp.tool
async def browser_extract_text(url: str, selector: str) -> str:
    """Navigate and return inner_text of the first matching element."""
    async with browser_manager.get_page(url) as page:
        try:
            return await page.locator(selector).inner_text()
        except Exception:
            return ""


def main() -> None:
    """CLI entry point - stdio transport."""
    mcp.run()


if __name__ == "__main__":
    main()
