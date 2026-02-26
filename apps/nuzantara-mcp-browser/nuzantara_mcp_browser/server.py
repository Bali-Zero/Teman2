import base64
import logging
from typing import Optional

from fastmcp import FastMCP
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger("nuzantara-mcp-browser")

mcp = FastMCP(
    name="Nuzantara Browser",
    instructions="Headless browser sidecar for Nuzantara UI verification and data extraction",
)


from typing import Literal


@mcp.tool()
async def browse_url(
    url: str,
    wait_until: Literal[
        "load", "domcontentloaded", "networkidle", "commit"
    ] = "networkidle",
) -> dict:
    """
    Browse a URL and return basic page information.

    Args:
        url: The URL to browse
        wait_until: When to consider navigation finished ("load", "domcontentloaded", "networkidle", "commit")
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            response = await page.goto(url, wait_until=wait_until)
            title = await page.title()
            status = response.status if response else 0

            return {"url": url, "title": title, "status": status, "success": True}
        except Exception as e:
            return {"url": url, "success": False, "error": str(e)}
        finally:
            await browser.close()


@mcp.tool()
async def take_screenshot(
    url: str, selector: Optional[str] = None, full_page: bool = False
) -> dict:
    """
    Take a screenshot of a URL or a specific element.

    Returns a base64 encoded image string.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="networkidle")

            if selector:
                element = page.locator(selector)
                screenshot_bytes = await element.screenshot()
            else:
                screenshot_bytes = await page.screenshot(full_page=full_page)

            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

            return {
                "url": url,
                "screenshot_b64": screenshot_b64,
                "success": True,
                "mime_type": "image/png",
            }
        except Exception as e:
            return {"url": url, "success": False, "error": str(e)}
        finally:
            await browser.close()


@mcp.tool()
async def get_page_content(url: str, selector: str = "body") -> dict:
    """
    Extract text content from a URL.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="networkidle")
            content = await page.inner_text(selector)

            return {
                "url": url,
                "content": content[:10000],  # Limit content for LLM
                "success": True,
            }
        except Exception as e:
            return {"url": url, "success": False, "error": str(e)}
        finally:
            await browser.close()


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
