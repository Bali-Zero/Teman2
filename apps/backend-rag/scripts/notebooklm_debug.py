import os
import time
from playwright.sync_api import sync_playwright

USER_DATA_DIR = "apps/backend-rag/data/chrome_profile"

def run_debug_mode():
    print("🛠️ DEBUG MODE: Launching Chrome...")
    print("👉 I will keep the browser open for 5 minutes.")
    print("👉 Please manually test if you can upload the PDF.")
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"] # Anti-detection
        )
        
        page = browser.new_page()
        page.goto("https://notebooklm.google.com/")
        
        print("✅ Browser Open. Go ahead and test NotebookLM.")
        print("⏱️  Closing in 300 seconds...")
        time.sleep(300)
        browser.close()

if __name__ == "__main__":
    run_debug_mode()
