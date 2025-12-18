#!/usr/bin/env python3
import logging
import random
import time
from pathlib import Path
from bs4 import BeautifulSoup

# Selenium Imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Setup Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

BASE_URL = "https://putusan3.mahkamahagung.go.id"

# Categories to scrape (Targeted)
CATEGORIES = {
    "niaga": "niaga",  # Commercial
    "pajak": "pajak",  # Tax
    "phi": "pengadilan-hubungan-industrial",  # Labor
    "tun": "tata-usaha-negara",  # Administrative
    "pidana_khusus": "pidana-khusus",  # Special Crimes
}

# Targeted Keywords (Filter: Only download if title contains one of these)
KEYWORDS = [
    "Pailit",
    "PKPU",
    "Merek",
    "Paten",
    "Hak Cipta",
    "Desain Industri",  # Commercial
    "Pajak",
    "Sengketa Pajak",
    "Banding",
    "Gugatan",
    "PPN",
    "PPh",  # Tax
    "PHK",
    "Pesangon",
    "Tenaga Kerja Asing",
    "Outsourcing",  # Labor
    "Sengketa Tanah",
    "Hak Milik",
    "Hak Guna Bangunan",
    "Nominee",  # Land
    "Wanprestasi",
    "Perbuatan Melawan Hukum",  # Contracts
    "Imigrasi",
    "Deportasi",
    "Cekal",
    "Izin Tinggal",
    "KITAS",
    "KITAP",  # Immigration (Admin)
    "Pasal 122",
    "Penyalahgunaan Izin Tinggal",  # Immigration (Criminal)
]

DATA_DIR = Path("apps/scraper/data/raw_putusan")
DATA_DIR.mkdir(parents=True, exist_ok=True)


def setup_driver():
    """Setup Headless Chrome Driver"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run headless
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    # Anti-detection
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


def download_pdf(url, filename):
    """Download PDF using requests (Selenium is for navigation)"""
    import requests

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, stream=True, timeout=30)
        if resp.status_code == 200:
            filepath = DATA_DIR / filename
            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            logger.info(f"✅ Downloaded: {filename}")
            return True
        else:
            logger.error(f"❌ Failed to download PDF {url}: {resp.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Error downloading PDF: {e}")
        return False


def scrape_category(driver, category_name, category_code, limit=5):
    logger.info(f"🔍 Scraping Category: {category_name} (Limit: {limit})")

    # List of URL patterns to try
    patterns = [
        f"{BASE_URL}/direktori/kategori/{category_code}.html",
        f"{BASE_URL}/direktori/index/kategori/{category_code}.html",
        f"{BASE_URL}/direktori/index/pengadilan/mahkamah-agung/kategori/{category_code}.html",
        f"{BASE_URL}/direktori/kategori/jenis/{category_code}.html",
        # Some categories might have -1 or -2 suffix
        f"{BASE_URL}/direktori/index/kategori/{category_code}-1.html",
        f"{BASE_URL}/direktori/index/kategori/{category_code}-2.html",
    ]

    target_url = None

    for url in patterns:
        logger.info(f"   Testing URL: {url}")
        try:
            driver.get(url)
            # Increased timeout to 60s as requested ("togli il timeout")
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.CLASS_NAME, "spost"))
            )
            target_url = url
            logger.info(f"   ✅ Found valid URL: {target_url}")
            break
        except:
            logger.warning(f"   ❌ Failed to load (timeout): {url}")
            continue

    if not target_url:
        logger.error(f"❌ Could not find ANY valid URL for {category_name}")
        return

    count = 0
    page = 1

    while count < limit:
        logger.info(f"   📄 Processing Page {page}")

        # Parse current page content
        soup = BeautifulSoup(driver.page_source, "html.parser")
        items = soup.find_all("div", class_="spost")

        if not items:
            logger.warning("No items found on this page.")
            break

        for item in items:
            if count >= limit:
                break

            title_tag = item.find("strong")
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)

            # --- TARGETING FILTER ---
            if not any(k.lower() in title.lower() for k in KEYWORDS):
                continue
            # ------------------------

            # Find PDF Link
            pdf_link = None
            for a in item.find_all("a", href=True):
                if a["href"].endswith(".pdf"):
                    pdf_link = a["href"]
                    break

            if pdf_link:
                safe_title = "".join([c if c.isalnum() else "_" for c in title])[:100]
                filename = f"{category_name}_{safe_title}.pdf"

                logger.info(f"   🎯 Found Target: {title[:60]}...")
                download_pdf(pdf_link, filename)
                count += 1
                time.sleep(random.uniform(1.0, 3.0))  # Be nice

        # Pagination: Click "Next" or construct URL
        # Constructing URL is safer than clicking "Next" which might be JS
        page += 1

        # Fix pagination: strip .html if present
        base_page_url = target_url.replace(".html", "")
        next_page_url = f"{base_page_url}/page/{page}"

        if count < limit:
            logger.info(f"   ➡️ Going to next page: {next_page_url}")
            driver.get(next_page_url)
            try:
                # Increased timeout for pagination too
                WebDriverWait(driver, 60).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "spost"))
                )
            except:
                logger.warning("End of pagination or timeout.")
                break


def main():
    driver = setup_driver()
    try:
        # Targeted Run
        scrape_category(driver, "niaga", "niaga", limit=5)
        scrape_category(driver, "pajak", "pajak", limit=5)
        scrape_category(driver, "phi", "pengadilan-hubungan-industrial", limit=5)
        scrape_category(driver, "tun", "tata-usaha-negara", limit=5)
        scrape_category(driver, "pidana_khusus", "pidana-khusus", limit=5)
    finally:
        driver.quit()
        logger.info("🎉 Selenium Scraping Complete!")


if __name__ == "__main__":
    main()
