import os
import asyncio
import json
import hashlib
import httpx
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

# Base URLs
VISA_URL = "https://www.imigrasi.go.id/wna/permohonan-visa-republik-indonesia"
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "https://nuzantara-rag.fly.dev")

EMAILS = {
    "to": ["ari.firda@balizero.com", "sahira@balizero.com"],
    "cc": ["zero@balizero.com"],
    "sender": "intel-bot@balizero.com",
}

BASE_DIR = Path(__file__).parent.absolute()
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data" / "immigration"
OUTPUT_DIR = DATA_DIR  # Raw scraped visa files
STAGING_DIR = Path("data/staging")  # Staging for backend approval
MAP_FILE = CONFIG_DIR / "immigration_site_map.json"

CONFIG_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
STAGING_DIR.mkdir(parents=True, exist_ok=True)
(STAGING_DIR / "visa").mkdir(exist_ok=True)
(STAGING_DIR / "news").mkdir(exist_ok=True)


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


class BackendReporter:
    """Save discoveries to backend staging directory for human approval."""

    def __init__(self):
        self.visa_items = []
        self.news_items = []

    def add_visa_change(self, title, url, content, detection_type="NEW"):
        """Add a visa change for staging approval."""
        item_id = hashlib.md5(url.encode()).hexdigest()[:12]
        self.visa_items.append({
            "id": item_id,
            "type": "visa",
            "title": title,
            "url": url,
            "content": content,
            "status": "pending",
            "detected_at": datetime.now().isoformat(),
            "detection_type": detection_type,  # NEW or UPDATED
            "source": "intelligent_visa_agent"
        })

    def add_news_item(self, title, summary, is_critical=False):
        """Add a news item for staging approval."""
        item_id = hashlib.md5(f"{title}{datetime.now()}".encode()).hexdigest()[:12]
        self.news_items.append({
            "id": item_id,
            "type": "news",
            "title": title,
            "content": summary,
            "status": "pending",
            "detected_at": datetime.now().isoformat(),
            "detection_type": "NEW",
            "source": "imigrasi_news",
            "is_critical": is_critical
        })

    async def save_to_staging(self):
        """Save all items to staging directory (backend will pick them up)."""
        saved_count = 0

        # Save visa items
        for item in self.visa_items:
            staging_file = STAGING_DIR / "visa" / f"{item['id']}.json"
            try:
                with open(staging_file, "w", encoding="utf-8") as f:
                    json.dump(item, f, indent=2, ensure_ascii=False)
                logger.info(f"✅ Saved to staging: {item['title']}")
                saved_count += 1
            except Exception as e:
                logger.error(f"Failed to save {item['id']}: {e}")

        # Save news items
        for item in self.news_items:
            staging_file = STAGING_DIR / "news" / f"{item['id']}.json"
            try:
                with open(staging_file, "w", encoding="utf-8") as f:
                    json.dump(item, f, indent=2, ensure_ascii=False)
                logger.info(f"✅ Saved to staging: {item['title']}")
                saved_count += 1
            except Exception as e:
                logger.error(f"Failed to save {item['id']}: {e}")

        if saved_count > 0:
            logger.info(f"📦 Total items saved to staging: {saved_count}")
            logger.info("👁️ Review at: https://zantara.balizero.com/intelligence/visa-oracle")
        else:
            logger.info("ℹ️ No new changes detected.")

        return saved_count


class IntelligentVisaAgent:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.client = genai.Client(api_key=self.api_key)
        self.model_id = "gemini-2.0-flash"
        self.mapper = SiteMapper()
        self.reporter = BackendReporter()

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

            # Safe JSON parsing with error handling
            try:
                result = json.loads(text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from banner scan: {e}")
                logger.debug(f"Raw response: {text}")
                return False

            if result.get("found"):
                self.reporter.add_news_item(
                    title=f"[{site_name.upper()}] {result['title']}",
                    summary=result["summary"],
                    is_critical=True
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

            # Safe JSON parsing with error handling
            try:
                labels = json.loads(raw_text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from Gemini visa labels: {e}")
                logger.debug(f"Raw response: {raw_text}")
                return await self._fallback_link_extraction(page)

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

            # Safe JSON parsing with error handling
            try:
                news_items = json.loads(text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from news scan: {e}")
                logger.debug(f"Raw response: {text}")
                return

            for item in news_items:
                is_critical = item.get("is_critical", False)
                self.reporter.add_news_item(
                    title=item["title"],
                    summary=item["summary"],
                    is_critical=is_critical
                )
                if is_critical:
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

                        # Get content for staging
                        slug = link.split("/")[-1].split("?")[0]
                        content_file = OUTPUT_DIR / f"visa_{slug}.txt"
                        content = ""
                        if content_file.exists():
                            content = content_file.read_text(encoding="utf-8")

                        # Add to staging with proper detection type
                        self.reporter.add_visa_change(
                            title=f"{'🆕 NEW' if status == 'NEW' else '📝 UPDATED'} VISA: {title}",
                            url=link,
                            content=content,
                            detection_type=status
                        )

                        if status == "NEW":
                            new_items += 1
                        else:
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

        # Save all discoveries to staging directory
        await self.reporter.save_to_staging()
        logger.info("🏁 Daily Intel Run Complete.")


if __name__ == "__main__":
    agent = IntelligentVisaAgent()
    asyncio.run(agent.run())
