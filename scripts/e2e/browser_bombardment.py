import os
import time
from playwright.sync_api import sync_playwright

# Configuration
BASE_URL = os.getenv("WEBAPP_URL", "http://localhost:3000")
EMAIL = os.getenv("ZANTARA_EMAIL", "zero@balizero.com")
PIN = os.getenv("ZANTARA_PIN", "123456")  # UPDATE THIS if needed

# 30 Questions
QUESTIONS = [
    # --- BUSINESS (20) ---
    "What are the requirements for a KITAS Investor?",
    "How much does a Working KITAS cost?",
    "Can I extend my VoA online?",
    "Tell me about the Second Home Visa.",
    "What is the difference between Offshore and Onshore B211A?",
    "What is the minimum capital for a PT PMA?",
    "Can a foreigner be a Director in a PT PMA?",
    "What does a Commissioner do in a PT PMA?",
    "Is a Virtual Office valid for a PT PMA?",
    "What are the KBLI codes for a restaurant?",
    "What is the corporate tax rate (PPh Badan)?",
    "What is the current VAT (PPN) rate?",
    "Do foreigners pay personal income tax?",
    "How do I register for an NPWP?",
    "How do I activate my EFIN?",
    "Is a nominee agreement safe?",
    "Explain Leasehold vs Freehold property.",
    "Can foreigners get Hak Pakai?",
    "Do I need a prenuptial agreement for a mixed marriage?",
    "What are the divorce laws in Indonesia?",
    # --- MEMORY & CONTEXT (10) ---
    "My name is Antonello. Please remember this.",
    "What is my name?",
    "I told you I like surfing. Where should I go in Bali?",
    "Write a short poem about the sunset in Uluwatu.",
    "Translate that poem into Indonesian.",
    "What was the very first question I asked you in this session?",
    "Summarize our conversation so far in 3 bullet points.",
    "You are very helpful, thank you!",
    "Can you explain the KITAS Investor again, but simpler this time?",
    "What documents do I need for THAT visa (the Investor one)?",
]


def run():
    print(f"🚀 Starting Browser Bombardment on {BASE_URL}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Headless=False to see the action
        context = browser.new_context()
        page = context.new_page()

        # 1. Navigate
        print(f"🌐 Navigating to {BASE_URL}...")
        page.goto(BASE_URL)

        # 2. Login (if needed)
        # Check if we are on login page
        if "login" in page.url or page.locator("input#email").count() > 0:
            print("🔑 Logging in...")
            page.fill("input#email", EMAIL)
            page.fill("input#password", PIN)
            page.click("button[type='submit']")

            # Wait for navigation to chat
            page.wait_for_url("**/chat", timeout=10000)
            print("✅ Login successful")

        # 3. Chat Loop
        print("💬 Starting Chat Loop...")

        # Wait for chat input to be ready
        page.wait_for_selector("textarea", state="visible", timeout=10000)

        for i, question in enumerate(QUESTIONS, 1):
            print(f"\n[{i}/{len(QUESTIONS)}] Asking: {question}")

            # Type question
            page.fill("textarea", question)

            # Click send (find button inside the form)
            # The send button usually has an icon or type='submit'
            # Based on code: button[type='submit'] inside the form
            page.click("button[type='submit']")

            # Wait for response
            # We assume a new message bubble appears.
            # A simple way is to wait for the "Assistant" or AI message count to increase
            # OR wait for the "typing" indicator to disappear and new text to appear.
            # For simplicity, we'll wait for a fixed time + check for text.

            # Better: Wait for the send button to be enabled again (it's disabled while loading)
            # Code: disabled={isLoading || !input.trim()}
            # So wait for it to be disabled (loading started) then enabled (loading finished)

            try:
                # Wait for loading state (button disabled)
                # page.wait_for_selector("button[type='submit'][disabled]", timeout=2000)
                pass
            except:
                pass  # Might be too fast

            # Wait for response completion (button enabled again)
            # And wait a bit for streaming to finish visually
            time.sleep(2)
            page.wait_for_selector(
                "button[type='submit']:not([disabled])", timeout=60000
            )

            # Capture last message
            # Assuming messages are in a list. We need a selector for the last message.
            # We'll just grab all text for now or wait.

            print("✅ Response received")
            time.sleep(1)  # Readability

        print("\n🏁 Test Complete!")
        # browser.close() # Keep open to inspect


if __name__ == "__main__":
    run()
