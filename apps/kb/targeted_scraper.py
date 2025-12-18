import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from loguru import logger
import aiohttp

# Configuration
BASE_URL = "https://peraturan.bpk.go.id"
SEARCH_URL = f"{BASE_URL}/Search"
DOWNLOAD_DIR = Path("data/immigration")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# List of regulations to find
TARGETS = [
    "Peraturan Menteri Hukum dan HAM Nomor 11 Tahun 2024",
    "Keputusan Menteri Hukum dan HAM Nomor M.HH-01.GR.01.01 Tahun 2024",
    "Surat Edaran IMI-0820.GR.01.01 Tahun 2022",
    "Peraturan Menteri Keuangan Nomor 81 Tahun 2024",
    "Peraturan Menteri Keuangan Nomor 66 Tahun 2023",
    "Peraturan Menteri Keuangan Nomor 68 Tahun 2022",
    "Peraturan Pemerintah Nomor 58 Tahun 2023",
    "Peraturan BKPM Nomor 5 Tahun 2021",
    "Peraturan Pemerintah Nomor 5 Tahun 2021",
    "Peraturan Pemerintah Nomor 18 Tahun 2021",
    "Peraturan Menteri ATR BPN Nomor 18 Tahun 2021",
]


async def download_pdf(url, filename):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                with open(DOWNLOAD_DIR / filename, "wb") as f:
                    f.write(await resp.read())
                logger.info(f"✅ Downloaded: {filename}")
                return True
            else:
                logger.error(f"❌ Failed to download {url}: {resp.status}")
                return False


async def search_and_download(page, query):
    logger.info(f"🔍 Searching for: {query}")

    # DUCKDUCKGO SEARCH STRATEGY (More scraper-friendly)
    # We use site:peraturan.bpk.go.id to target the specific site
    ddg_query = f"site:peraturan.bpk.go.id filetype:pdf {query}"
    ddg_url = f"https://duckduckgo.com/?q={ddg_query}&t=h_&ia=web"

    try:
        await page.goto(ddg_url, timeout=60000, wait_until="domcontentloaded")
        await asyncio.sleep(3)  # Wait for results

        # Find ANY link to the target domain
        # This is more robust than looking for specific .pdf endings immediately
        links = page.locator("a[href*='peraturan.bpk.go.id']")
        count = await links.count()
        logger.info(f"   Found {count} links to peraturan.bpk.go.id")

        found_pdf = False

        for i in range(count):
            try:
                link = links.nth(i)
                href = await link.get_attribute("href")
                if not href:
                    continue

                logger.info(f"   Checking link: {href}")

                # Case 1: Direct PDF link
                if ".pdf" in href.lower():
                    logger.info(f"   ✅ Found PDF link: {href}")
                    safe_name = query.replace(" ", "_").replace(".", "") + ".pdf"
                    await download_pdf(href, safe_name)
                    found_pdf = True
                    break

                # Case 2: Detail page (contains /Details/)
                if "/Details/" in href:
                    logger.info(f"   Found Detail Page: {href}")
                    await page.goto(href, timeout=60000)

                    # Try to find download link on BPK page
                    download_link = page.locator(
                        "a[href*='/Download/'], a[href$='.pdf']"
                    ).first
                    if await download_link.count() > 0:
                        pdf_url = await download_link.get_attribute("href")
                        if not pdf_url.startswith("http"):
                            pdf_url = (
                                BASE_URL + pdf_url
                                if pdf_url.startswith("/")
                                else BASE_URL + "/" + pdf_url
                            )

                        safe_name = query.replace(" ", "_").replace(".", "") + ".pdf"
                        logger.info(f"   ✅ Found PDF on Detail Page: {pdf_url}")
                        await download_pdf(pdf_url, safe_name)
                        found_pdf = True
                        break
            except Exception as e:
                logger.warning(f"   Error checking link {i}: {e}")
                continue

        if not found_pdf:
            logger.warning(
                f"   ⚠️ No PDF found for {query} after checking {count} links"
            )
            # Debug: Take screenshot and dump HTML
            try:
                slug = query[:10].replace(" ", "_")
                screenshot_path = f"debug_ddg_{slug}.png"
                html_path = f"debug_ddg_{slug}.html"

                await page.screenshot(path=screenshot_path)
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(await page.content())

                logger.info(f"   📸 Debug saved to {screenshot_path} and {html_path}")
            except:
                pass

    except Exception as e:
        logger.error(f"   ❌ Error processing {query}: {e}")
        try:
            screenshot_path = f"debug_error_{query[:10].replace(' ', '_')}.png"
            await page.screenshot(path=screenshot_path)
            logger.info(f"   📸 Screenshot saved to {screenshot_path}")
        except:
            pass


async def main():
    async with async_playwright() as p:
        # Launch with headless=True but set user agent to look like a real browser
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        for target in TARGETS:
            await search_and_download(page, target)
            await asyncio.sleep(5)  # Polite delay for Google

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
