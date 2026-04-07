"""AHU scraper — company/foundation registry from ahu.go.id (JS-heavy, needs Playwright)."""

from __future__ import annotations

import asyncio
from typing import Any

from osint_nexus.scrapers.base import BaseScraper, ScrapedRecord
from osint_nexus.utils.http import random_delay
from osint_nexus.utils.logging import get_logger

AHU_BASE = "https://ahu.go.id"
AHU_PT_SEARCH = "https://ahu.go.id/pencarian/profil-pt"

logger = get_logger("scraper.ahu")


class AHUScraper(BaseScraper):
    """Scrapes AHU (Administrasi Hukum Umum) — PT and Yayasan registries.

    Uses Playwright because AHU is heavily JS-rendered.
    """

    name = "ahu"

    async def scrape(self, query: str, **kwargs: Any) -> list[ScrapedRecord]:
        """Search AHU by company name or person name.

        Args:
            query: Company or person name
            kwargs:
                search_type: 'pt' (default), 'yayasan', 'perkumpulan'
        """
        search_type = kwargs.get("search_type", "pt")
        records: list[ScrapedRecord] = []

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            self.logger.error("Playwright not installed. Run: playwright install chromium")
            return records

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                locale="id-ID",
                timezone_id="Asia/Makassar",
            )
            page = await context.new_page()

            try:
                url = f"{AHU_BASE}/pencarian/profil-{search_type}"
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await random_delay(1, 3)

                # Fill search field
                search_input = page.locator("input[type='text']").first
                await search_input.fill(query)
                await random_delay(0.5, 1.5)

                # Submit
                submit_btn = page.locator("button[type='submit'], input[type='submit']").first
                await submit_btn.click()

                # Wait for results
                await page.wait_for_load_state("networkidle", timeout=15000)
                await random_delay(1, 2)

                # Parse result table
                rows = await page.locator("table tbody tr").all()
                self.logger.info("AHU search '%s': %d results", query, len(rows))

                for row in rows:
                    cells = await row.locator("td").all()
                    if len(cells) < 3:
                        continue

                    nama = await cells[0].inner_text()
                    nomor_sk = await cells[1].inner_text() if len(cells) > 1 else ""
                    status = await cells[2].inner_text() if len(cells) > 2 else ""

                    record_data: dict[str, Any] = {
                        "nama": nama.strip(),
                        "nomor_sk": nomor_sk.strip(),
                        "status": status.strip(),
                        "tipe": search_type,
                    }

                    # Try detail page
                    detail_link = await row.locator("a").first.get_attribute("href")
                    if detail_link:
                        detail_url = detail_link if detail_link.startswith("http") else f"{AHU_BASE}{detail_link}"
                        await random_delay(2, 4)
                        try:
                            detail_data = await self._fetch_detail(page, detail_url)
                            record_data.update(detail_data)
                        except Exception as e:
                            self.logger.warning("AHU detail failed: %s", e)

                    records.append(
                        ScrapedRecord(
                            source="ahu",
                            entity_type="company",
                            url=detail_link or url,
                            raw_data=record_data,
                        )
                    )

            except Exception as e:
                self.logger.error("AHU scrape failed: %s", e)
            finally:
                await browser.close()

        self.save_records(records)
        return records

    async def _fetch_detail(self, page: Any, url: str) -> dict[str, Any]:
        """Navigate to detail page and extract company info."""
        await page.goto(url, wait_until="networkidle", timeout=20000)
        data: dict[str, Any] = {}

        # Extract key-value pairs from detail tables
        pairs = await page.locator("table tr").all()
        for pair in pairs:
            cells = await pair.locator("td, th").all()
            if len(cells) >= 2:
                key = (await cells[0].inner_text()).strip().lower().replace(" ", "_")
                val = (await cells[1].inner_text()).strip()
                if key and val:
                    data[key] = val

        return data
