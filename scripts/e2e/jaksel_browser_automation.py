import asyncio
import json
from playwright.async_api import async_playwright

# Configuration
URL = "https://nuzantara-webapp.fly.dev"
EMAIL = "anton@balizero.com"
PIN = "538147"
QUESTIONS_FILE = "apps/backend-rag/business_questions_id.json"
OUTPUT_FILE = "jaksel_test_results.json"


async def run():
    # Load questions
    with open(QUESTIONS_FILE, "r") as f:
        questions = json.load(f)

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        print(f"🚀 Navigating to {URL}...")
        await page.goto(URL)

        # Login
        print("🔑 Logging in...")
        await page.fill("input#email", EMAIL)
        await page.fill("input#pin", PIN)
        await page.click("button.group")  # Sign in button

        # Wait for chat interface
        try:
            # Wait for the textarea which indicates chat is ready
            await page.wait_for_selector("textarea", timeout=15000)
            print("✅ Login Successful!")
        except:
            print("❌ Login Failed or Chat not loaded.")
            await page.screenshot(path="login_failed.png")
            await browser.close()
            return

        # Iterate questions
        for i, question in enumerate(questions):
            print(f"❓ [{i + 1}/{len(questions)}] Asking: {question}")

            try:
                # Type and send
                await page.fill("textarea", question)
                await page.press("textarea", "Enter")

                # Wait for response
                # Given the 110s latency, we wait 2 minutes.
                print("⏳ Waiting for response (approx 2 mins)...")
                await page.wait_for_timeout(120000)

                # Capture screenshot
                screenshot_path = f"jaksel_answer_{i + 1}.png"
                await page.screenshot(path=screenshot_path)
                print(f"📸 Saved screenshot: {screenshot_path}")

                results.append(
                    {
                        "question": question,
                        "screenshot": screenshot_path,
                        "status": "captured",
                    }
                )

            except Exception as e:
                print(f"❌ Error asking question: {e}")
                results.append(
                    {"question": question, "error": str(e), "status": "failed"}
                )

        await browser.close()

    # Save summary
    with open(OUTPUT_FILE, "w") as f:
        json.dump(results, f, indent=2)
    print(f"✅ Test Complete. Results saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(run())
