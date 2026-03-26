import asyncio
from playwright.async_api import async_playwright
import os

BROWSER_PROFILE_PATH = os.path.expanduser("~/.gemini/antigravity-browser-profile/")

async def debug_notebooklm():
    async with async_playwright() as p:
        print(f"Launching with profile: {BROWSER_PROFILE_PATH}")
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=BROWSER_PROFILE_PATH,
            headless=True
        )
        page = await browser.new_page()
        await page.goto("https://notebooklm.google.com/", wait_until="networkidle")
        
        # Wait a bit
        await page.wait_for_timeout(3000)
        
        # Check login
        if await page.query_selector("text='Sign in'"):
            print("ERROR: Not logged in. Page wants 'Sign in'.")
        elif await page.query_selector("text='Accedi'"):
            print("ERROR: Not logged in (Italian). Page wants 'Accedi'.")
        else:
            print("SUCCESS: Logged in.")
            
        # Dump all button texts
        buttons = await page.query_selector_all("button")
        print(f"Found {len(buttons)} buttons.")
        for btn in buttons:
            text = await btn.inner_text()
            print(f"Button: '{text}'")
            
        # Dump role=button as well
        div_buttons = await page.query_selector_all("[role='button']")
        print(f"Found {len(div_buttons)} div[role=button].")
        for btn in div_buttons:
            text = await btn.inner_text()
            print(f"Role-Button: '{text}'")

        # Save HTML for inspection
        html = await page.content()
        with open("/Users/nuzantara/Desktop/nuzantara/tmp_notebooklm/debug.html", "w") as f:
            f.write(html)
        print("HTML saved to debug.html")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_notebooklm())
