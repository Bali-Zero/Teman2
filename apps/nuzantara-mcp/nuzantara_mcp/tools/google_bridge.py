import logging
import json
import os
import httpx
from typing import Any, Optional

logger = logging.getLogger("nuzantara-mcp.google_bridge")

# Path to Google credentials
OAUTH_CREDS_PATH = os.path.expanduser("~/.gemini/oauth_creds.json")
BROWSER_PROFILE_PATH = os.path.expanduser("~/.gemini/antigravity-browser-profile/")

async def upload_to_notebooklm(file_path: str, title: Optional[str] = None) -> dict[str, Any]:
    """
    Upload a document to Google NotebookLM using the authenticated browser bridge.
    
    Args:
        file_path: Absolute path to the file to upload
        title: Optional title for the notebook
    """
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}

    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        try:
            # We must use a context to load the existing profile
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=BROWSER_PROFILE_PATH,
                headless=True
            )
            page = await browser.new_page()
            await page.goto("https://notebooklm.google/", wait_until="networkidle")

            # Check if we are logged in
            if await page.query_selector("text='Sign in'"):
                return {"error": "Not logged in to Google. Please log in manually in the browser first."}

            # Basic NotebookLM upload interaction (2026 UI)
            # Find the "New Notebook" button
            new_notebook_btn = await page.query_selector("text='New Notebook'")
            if not new_notebook_btn:
                # Fallback to selector
                new_notebook_btn = await page.query_selector("button:has-text('New Notebook')")

            if new_notebook_btn:
                await new_notebook_btn.click()
                await page.wait_for_timeout(2000)

                # Look for "Local files" or upload area
                async with page.expect_file_chooser() as fc_info:
                    await page.click("text='Local files'")
                file_chooser = await fc_info.value
                await file_chooser.set_files(file_path)

                await page.wait_for_timeout(8000) # Give more time for upload
                return {"success": True, "msg": f"Uploaded {os.path.basename(file_path)} to NotebookLM"}
            else:
                return {"error": "Could not find 'New Notebook' button"}
        except Exception as e:
            return {"error": f"NotebookLM bridge failed: {str(e)}"}
        finally:
            if 'browser' in locals():
                await browser.close()

def register(mcp, _call=None, _call_safe=None):
    """Register Google Bridge tools (Labs)"""
    # Wrap the top-level function as an MCP tool
    @mcp.tool()
    async def upload_to_notebooklm_tool(file_path: str, title: Optional[str] = None) -> dict[str, Any]:
        """
        Upload a document to Google NotebookLM using the authenticated browser bridge.
        
        Args:
            file_path: Absolute path to the file to upload
            title: Optional title for the notebook
        """
        return await upload_to_notebooklm(file_path, title)
