"""Putusan MA scraper — court decisions from putusan3.mahkamahagung.go.id.

Uses Playwright: the site serves JS-rendered content that plain HTTP clients
receive as stale edge-cache HTML. Full Chrome rendering returns 42+ entries.
From Bali IP: commit in 0.3s, .spost renders within 15s.
"""

from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from osint_nexus.scrapers.base import BaseScraper, ScrapedRecord
from osint_nexus.utils.http import random_delay

PUTUSAN_BASE = "https://putusan3.mahkamahagung.go.id"


class PutusanMAScraper(BaseScraper):
    """Scrapes court decisions from Mahkamah Agung directory."""

    name = "putusan_ma"

    async def scrape(self, query: str, **kwargs: Any) -> list[ScrapedRecord]:
        """Fetch court decisions, optionally filtered by query.

        Args:
            query: Keyword filter (client-side, applied after fetching)
            kwargs:
                max_pages: pages to fetch (default: 3)
        """
        max_pages = kwargs.get("max_pages", 3)
        records: list[ScrapedRecord] = []

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            self.logger.error("Playwright required. Run: playwright install chromium")
            return records

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                ctx = await browser.new_context(
                    ignore_https_errors=True,
                    locale="id-ID",
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"
                    ),
                )
                page = await ctx.new_page()

                for page_num in range(1, max_pages + 1):
                    await random_delay(1, 3)

                    url = (
                        f"{PUTUSAN_BASE}/direktori.html"
                        if page_num == 1
                        else f"{PUTUSAN_BASE}/direktori/page/{page_num}.html"
                    )

                    try:
                        resp = await page.goto(url, wait_until="commit", timeout=30000)
                        if not resp or resp.status != 200:
                            self.logger.warning("Page %d: HTTP %s", page_num, resp.status if resp else "none")
                            continue

                        # Wait for .spost to render (JS-dependent)
                        try:
                            await page.wait_for_selector(".spost", timeout=30000)
                        except Exception:
                            # Fallback: check if content loaded anyway
                            html_check = await page.content()
                            if ".spost" not in html_check and len(html_check) < 20000:
                                self.logger.warning("Page %d: .spost timeout", page_num)
                                continue

                    except Exception as e:
                        self.logger.warning("Page %d: %s", page_num, type(e).__name__)
                        continue

                    html = await page.content()
                    soup = BeautifulSoup(html, "lxml")
                    items = soup.select(".spost")

                    if not items:
                        break

                    self.logger.info("Putusan page %d: %d items", page_num, len(items))

                    query_lower = query.lower() if query else ""
                    for item in items:
                        record = self._parse_result(item)
                        if record:
                            if query_lower:
                                blob = " ".join(str(v).lower() for v in record.raw_data.values())
                                if query_lower not in blob:
                                    continue
                            records.append(record)
            finally:
                await browser.close()

        self.save_records(records)
        return records

    def _parse_result(self, item: Any) -> ScrapedRecord | None:
        """Parse a single .spost element."""
        try:
            title_el = item.select_one('a[href*="/direktori/putusan/"]')
            if not title_el:
                title_el = item.select_one("h3 a, .title a, a")
            if not title_el:
                return None

            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            url = href if href.startswith("http") else f"{PUTUSAN_BASE}{href}"

            meta: dict[str, str] = {"judul": title}

            # Extract nomor perkara from title
            if "/" in title:
                meta["nomor_perkara"] = title

            # Look for metadata in sibling/child elements
            for sel, key in [
                (".court, .pengadilan", "pengadilan"),
                (".date, .tanggal", "tanggal_putusan"),
                (".category, .kategori", "kategori"),
                ("p, .snippet", "ringkasan"),
            ]:
                el = item.select_one(sel)
                if el:
                    text = el.get_text(strip=True)
                    if text and text != title:
                        meta[key] = text[:500]

            return ScrapedRecord(
                source="putusan_ma",
                entity_type="court_decision",
                url=url,
                raw_data=meta,
            )
        except Exception as e:
            self.logger.warning("Parse error: %s", e)
            return None
