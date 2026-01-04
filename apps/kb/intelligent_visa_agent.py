import os
import asyncio
import json
import hashlib
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin
from google import genai
from google.genai import types
from playwright.async_api import async_playwright
from loguru import logger
from dotenv import load_dotenv

# --- CONFIGURATION ---
SITES = {
    "imigrasi_national": "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia",
    "imigrasi_news": "https://www.imigrasi.go.id/id/berita-utama-imigrasi",
    "imigrasi_ngurah_rai": "https://ngurahrai.imigrasi.go.id",
    "imigrasi_denpasar": "https://denpasar.imigrasi.go.id",
    "imigrasi_singaraja": "https://singaraja.imigrasi.go.id",
    "kemnaker_main": "https://kemnaker.go.id",
    "kemnaker_tka": "https://tka-online.kemnaker.go.id",
}

EMAILS = {
    "to": ["ari.firda@balizero.com", "sahira@balizero.com"],
    "cc": ["zero@balizero.com"],
    "sender": "intel-bot@balizero.com",
}

BASE_DIR = Path(__file__).parent.absolute()
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data" / "immigration"
MAP_FILE = CONFIG_DIR / "immigration_site_map.json"

CONFIG_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)


class SiteMapper:
    def __init__(self):
        self.map = self._load_map()

    def _load_map(self):
        if MAP_FILE.exists():
            try:
                return json.loads(MAP_FILE.read_text())
            except:
                return {}
        return {}

    def save_map(self):
        MAP_FILE.write_text(json.dumps(self.map, indent=2))

    def get_hash(self, site_key, url):
        return self.map.get(site_key, {}).get(url)

    def update_hash(self, site_key, url, content_hash):
        if site_key not in self.map:
            self.map[site_key] = {}

        # Check if hash changed
        old_hash = self.map[site_key].get(url)
        is_changed = old_hash != content_hash

        # Update
        self.map[site_key][url] = content_hash
        self.save_map()

        return is_changed, old_hash


class EmailReporter:
    def __init__(self):
        self.report_items = []

    def add_item(self, site, title, details, is_alert=False):
        icon = "🚨" if is_alert else "ℹ️"
        self.report_items.append(f"{icon} **[{site.upper()}]** {title}\n{details}\n")

    def send(self):
        if not self.report_items:
            logger.info("No report items to send.")
            return

        body = "<h2>Bali Zero Immigration & Labor Daily Intel</h2><hr>"
        body += "<br><br>".join([i.replace("\n", "<br>") for i in self.report_items])
        body += f"<br><hr><small>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</small>"

        logger.info(f"📧 EMAIL REPORT PREPARED for {EMAILS['to']} (CC: {EMAILS['cc']})")
        logger.info("--- CONTENT ---")
        logger.info(body)
        logger.info("--- END ---")
        # TODO: Implement actual SMTP sending here using os.getenv("SMTP_...")


class IntelligentVisaAgent:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.client = genai.Client(api_key=self.api_key)
        self.model_id = "gemini-2.0-flash"
        self.mapper = SiteMapper()
        self.reporter = EmailReporter()

    def _calculate_hash(self, text):
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    async def _fallback_link_extraction(self, page):
        """Simple DOM-based link extraction as fallback."""
        logger.info("🔄 Falling back to DOM-based link extraction...")
        links = await page.eval_on_selector_all(
            "a[href*='/permohonan-visa-republik-indonesia/']",
            "elements => elements.map(a => a.href)",
        )
        return list(set(links))

    async def scrape_page(self, page, url):
        """Scrape content from a specific visa page."""
        try:
            slug = url.split("/")[-1].split("?")[0]
            file_path = OUTPUT_DIR / f"visa_{slug}.txt"

            logger.info(f"📄 Scraping content from: {url}")
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            await asyncio.sleep(2)

            title = await page.title()
            content = await page.inner_text("body")

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"TITLE: {title}\n")
                f.write(f"SOURCE: {url}\n")
                f.write("=" * 50 + "\n\n")
                f.write(content)

            logger.info(f"   ✅ Saved {slug}")
        except Exception as e:
            logger.error(f"   ❌ Failed to scrape {url}: {e}")

    async def check_page_for_updates(self, page, url, site_key):
        """Check a specific page for content changes using hashing."""
        try:
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            await asyncio.sleep(2)

            content = await page.inner_text("body")
            current_hash = self._calculate_hash(content)

            is_changed, old_hash = self.mapper.update_hash(site_key, url, current_hash)

            if is_changed:
                if old_hash is None:
                    logger.info(f"🆕 New Page Found: {url}")
                    return "NEW"
                else:
                    logger.info(f"📝 Content Changed: {url}")
                    return "UPDATED"

            return "UNCHANGED"
        except Exception as e:
            logger.error(f"Failed to check page {url}: {e}")
            return "ERROR"

    async def scan_homepage_banners(self, page, site_name, url):
        """Scan homepage for visual announcements/banners."""
        logger.info(f"📸 Scanning {site_name} homepage for banners...")
        screenshot_path = BASE_DIR / f"banner_scan_{site_name}.png"
        await page.screenshot(path=str(screenshot_path), full_page=False)

        with open(screenshot_path, "rb") as f:
            img_data = f.read()

        prompt = f"""
        Analyze this homepage of {site_name} Immigration.
        Are there any IMPORTANT ANNOUNCEMENTS visible in banners or images?
        Look for:
        - Office closures / Holidays
        - System maintenance
        - New service launches (e.g. "Immigration Lounge")
        - Policy changes
        
        Ignore general promo or welcome messages.
        If found, return JSON: {{ "found": true, "title": "...", "summary": "..." }}
        If nothing critical, return {{ "found": false }}
        """

        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_bytes(data=img_data, mime_type="image/png"),
                            types.Part.from_text(text=prompt),
                        ],
                    )
                ],
            )
            text = response.text.replace("```json", "").replace("```", "").strip()
            result = json.loads(text)

            if result.get("found"):
                self.reporter.add_item(
                    site_name, result["title"], result["summary"], is_alert=True
                )
                return True
            return False
        except Exception as e:
            logger.error(f"Banner scan failed for {site_name}: {e}")
            return False

    async def get_visa_links(self, page):
        """Use Gemini to find visa link texts and resolve them to URLs."""
        logger.info("📸 Capturing page for visual analysis...")
        screenshot_path = BASE_DIR / "visa_page_analysis.png"
        await page.screenshot(path=str(screenshot_path), full_page=False)

        with open(screenshot_path, "rb") as f:
            img_data = f.read()

        prompt = """
        Analyze this screenshot of the Indonesian Immigration website. 
        Identify all the labels/texts of the links that lead to specific visa types or categories.
        Return ONLY a JSON list of strings representing the EXACT text shown on the buttons or links.
        Example format: ["A1 BEBAS VISA (WISATA)", "B1 VISA SAAT KEDATANGAN (WISATA)"]
        Ignore generic navigation like 'Home' or 'FAQ'.
        """

        logger.info("🧠 Asking Gemini to identify visa labels...")
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_bytes(data=img_data, mime_type="image/png"),
                            types.Part.from_text(text=prompt),
                        ],
                    )
                ],
            )

            raw_text = response.text.replace("```json", "").replace("```", "").strip()
            labels = json.loads(raw_text)
            logger.info(f"🔍 Gemini identified {len(labels)} visa labels.")

            urls = []
            for label in labels:
                try:
                    link_handle = page.get_by_role("link", name=label, exact=False)
                    if await link_handle.count() > 0:
                        url = await link_handle.first.get_attribute("href")
                        if url:
                            full_url = urljoin(VISA_URL, url)
                            urls.append(full_url)
                except:
                    pass

            return list(set(urls))
        except Exception as e:
            logger.error(f"❌ Gemini analysis failed: {e}")
            return await self._fallback_link_extraction(page)

    async def process_news(self, page):
        """Scan Immigration News for policy updates."""
        logger.info("📰 Scanning Immigration News...")
        url = SITES["imigrasi_news"]
        try:
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            await asyncio.sleep(3)

            screenshot_path = BASE_DIR / "news_scan.png"
            await page.screenshot(path=str(screenshot_path))

            with open(screenshot_path, "rb") as f:
                img_data = f.read()

            prompt = """
            Analyze these news headlines from Indonesian Immigration.
            Identify ANY news about:
            - New Visa Types
            - Policy Changes (Quota, Prices, Rules)
            - System Maintenance
            
            Return JSON list of relevant news: 
            [{"title": "...", "summary": "...", "is_critical": true}]
            Return [] if nothing relevant found.
            """

            response = self.client.models.generate_content(
                model=self.model_id,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_bytes(data=img_data, mime_type="image/png"),
                            types.Part.from_text(text=prompt),
                        ],
                    )
                ],
            )

            text = response.text.replace("```json", "").replace("```", "").strip()
            news_items = json.loads(text)

            for item in news_items:
                if item.get("is_critical"):
                    self.reporter.add_item(
                        "IMIGRASI NEWS", item["title"], item["summary"], is_alert=True
                    )
                    logger.info(f"🚨 Found critical news: {item['title']}")

        except Exception as e:
            logger.error(f"News scan error: {e}")

    async def process_kemnaker(self, page):
        """Special handling for Kemnaker (Labor)."""
        logger.info("👷 Processing Kemnaker...")
        url = SITES["kemnaker_tka"]
        await page.goto(url, timeout=60000, wait_until="domcontentloaded")
        await asyncio.sleep(3)
        await self.scan_homepage_banners(page, "kemnaker_tka", url)

    async def run(self):
        logger.info("🚀 Starting Daily Immigration & Labor Intel...")

        async with async_playwright() as p:
            browser = await p.webkit.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"
            )
            page = await context.new_page()

            # 1. Imigrasi National
            try:
                logger.info("--- Processing National Site ---")
                await page.goto(SITES["imigrasi_national"], timeout=60000)
                await asyncio.sleep(5)

                current_links = await self.get_visa_links(page)
                new_items = 0
                updated_items = 0

                for link in current_links:
                    if not link.startswith("http"):
                        continue

                    status = await self.check_page_for_updates(
                        page, link, "imigrasi_national"
                    )

                    if status in ["NEW", "UPDATED"]:
                        await self.scrape_page(page, link)
                        title = link.split("/")[-1].replace("-", " ").title()
                        if status == "NEW":
                            self.reporter.add_item(
                                "IMIGRASI",
                                f"🆕 NEW VISA: {title}",
                                f"Link: {link}",
                                is_alert=True,
                            )
                            new_items += 1
                        else:
                            self.reporter.add_item(
                                "IMIGRASI",
                                f"📝 UPDATED VISA: {title}",
                                f"Content changed.\nLink: {link}",
                                is_alert=False,
                            )
                            updated_items += 1
                        await asyncio.sleep(1)

                logger.info(
                    f"National Scan Result: {new_items} new, {updated_items} updated."
                )
            except Exception as e:
                logger.error(f"National scan error: {e}")

            # 1.5 Process News
            await self.process_news(page)

            # 2. Local Sites
            for site_key, url in SITES.items():
                if (
                    "imigrasi_" in site_key
                    and site_key != "imigrasi_national"
                    and site_key != "imigrasi_news"
                ):
                    try:
                        await page.goto(url, timeout=30000)
                        await asyncio.sleep(3)
                        await self.scan_homepage_banners(page, site_key, url)
                    except Exception as e:
                        logger.error(f"Local site {site_key} error: {e}")

            # 3. Kemnaker
            try:
                await self.process_kemnaker(page)
            except Exception as e:
                logger.error(f"Kemnaker error: {e}")

            await browser.close()

        self.reporter.send()
        logger.info("🏁 Daily Intel Run Complete.")


if __name__ == "__main__":
    agent = IntelligentVisaAgent()
    asyncio.run(agent.run())
