import asyncio
import json
import os
import time
from typing import List, Dict
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Target URLs (as identified in our research)
TARGETS = [
    {"name": "Imigrasi_News", "url": "https://www.imigrasi.go.id/en/berita/"},
    {"name": "Imigrasi_Announcements", "url": "https://www.imigrasi.go.id/en/pengumuman/"},
    {"name": "OSS_Information", "url": "https://oss.go.id/informasi"},
    {"name": "BKPM_News", "url": "https://bkpm.go.id/en/publication/press-release"},
    {"name": "PUPR_Badung", "url": "https://dpupr.badungkab.go.id/"}
]

OUTPUT_DIR = os.path.expanduser("~/Desktop/nuzantara/data/scraping")

async def extract_text_from_page(page, url: str) -> str:
    """Extracts clean, readable text from a loaded page."""
    try:
        # Wait for the main content to load (adjust timeout for slow ID sites)
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        
        # Scroll to bottom to trigger lazy loading if any
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(2000)
        
        # Remove junk elements before extracting text to save context window later
        await page.evaluate("""
            document.querySelectorAll('script, style, nav, footer, header, noscript, iframe').forEach(el => el.remove());
        """)
        
        # Extract the visible inner text
        text = await page.evaluate("document.body.innerText")
        
        # Clean up whitespace
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        return "\n".join(lines)
        
    except PlaywrightTimeoutError:
        print(f"[-] Timeout while loading {url}")
        return ""
    except Exception as e:
        print(f"[-] Error extracting from {url}: {str(e)}")
        return ""

async def scrape_targets():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    results = []
    
    print("[*] Starting Bureaucracy Scraper (Playwright)...")
    
    async with async_playwright() as p:
        # Launch browser. Using chromium, headless. 
        # Adding some args to bypass basic anti-bot.
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        # Create a context with a standard user agent
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        
        page = await context.new_page()
        
        for target in TARGETS:
            print(f"\n[*] Scraping {target['name']}...")
            start_time = time.time()
            
            raw_text = await extract_text_from_page(page, target["url"])
            
            if raw_text:
                # Save individual text file for the AI filter to read later
                filename = f"{target['name']}_{int(time.time())}.txt"
                filepath = os.path.join(OUTPUT_DIR, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(f"SOURCE: {target['url']}\n")
                    f.write(f"SCRAPED_AT: {time.ctime()}\n")
                    f.write("-" * 50 + "\n")
                    f.write(raw_text)
                
                print(f"[+] Saved {len(raw_text)} chars to {filename} ({time.time() - start_time:.1f}s)")
                results.append({
                    "name": target["name"],
                    "url": target["url"],
                    "file": filepath,
                    "status": "success"
                })
            else:
                results.append({
                    "name": target["name"],
                    "url": target["url"],
                    "status": "failed"
                })
            
            # Gentle delay to avoid hammering servers and triggering IP bans
            await page.wait_for_timeout(3000)
            
        await browser.close()
    
    # Save a run manifest for Step 2 (The Qwen Filter) to process
    manifest_path = os.path.join(OUTPUT_DIR, "latest_run.json")
    with open(manifest_path, "w") as f:
        json.dump({"run_time": time.time(), "results": results}, f, indent=2)
    print(f"\n[*] Run complete. Manifest saved to {manifest_path}")

if __name__ == "__main__":
    asyncio.run(scrape_targets())
