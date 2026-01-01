import os
import time
from playwright.sync_api import sync_playwright

# Directory to store browser profile (cookies, login session)
USER_DATA_DIR = "apps/backend-rag/data/chrome_profile"

def setup_session():
    print("🚀 Launching Browser for Setup...")
    print("👉 Please log in to NotebookLM manually in the window that opens.")
    print("👉 Once logged in, simply close the browser window to save the session.")

    with sync_playwright() as p:
        # Launch Chrome in headful mode (visible) with persistent context
        browser = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False,  # Visible
            channel="chrome", # Use installed Chrome
            args=["--no-sandbox"]
        )
        
        page = browser.new_page()
        page.goto("https://notebooklm.google.com/")
        
        # Keep script running until user closes browser
        try:
            print("⏳ Waiting for you to close the browser...")
            page.wait_for_timeout(9999999) # Wait indefinitely (or until close)
        except Exception:
            print("✅ Browser closed. Session saved!")
        
        browser.close()

if __name__ == "__main__":
    # Ensure dir exists
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    setup_session()
