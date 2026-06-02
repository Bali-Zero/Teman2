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


async def _page_snapshot(page: Any) -> dict[str, Any]:
    """Return a useful page snapshot across Playwright versions."""
    accessibility = getattr(page, "accessibility", None)
    snapshot = getattr(accessibility, "snapshot", None)
    if callable(snapshot):
        snap = await snapshot()
        if isinstance(snap, dict):
            return snap

    return await page.evaluate(
        """() => {
            const clean = (value) => (value || "").replace(/\\s+/g, " ").trim();
            const title = clean(document.title);
            const text = clean(document.body ? document.body.innerText : "");
            const headings = Array.from(document.querySelectorAll("h1,h2,h3,h4,h5,h6"))
              .map((el) => ({
                role: "heading",
                level: Number(el.tagName.slice(1)),
                name: clean(el.innerText || el.textContent),
              }))
              .filter((item) => item.name)
              .slice(0, 50);
            const links = Array.from(document.querySelectorAll("a[href]"))
              .map((el) => ({
                role: "link",
                name: clean(el.innerText || el.textContent || el.getAttribute("aria-label")),
                href: el.href,
              }))
              .filter((item) => item.name || item.href)
              .slice(0, 50);
            return {
              role: "WebArea",
              name: title,
              url: window.location.href,
              text: text.slice(0, 5000),
              children: headings.concat(links),
            };
        }"""
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
        return await _page_snapshot(page)


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
