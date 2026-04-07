"""AHU scraper — uses shared stealth BrowserManager from browser-core.

Lazy-initialized per-process BrowserManager. No module-level singleton
at import time — first use creates it. `atexit` ensures cleanup on
process shutdown (prevents leaked Chromium processes).
"""
from __future__ import annotations

import asyncio
import atexit
from typing import Any, Optional

from browser_core import BrowserConfig, BrowserManager

from osint_nexus.scrapers.base import BaseScraper, ScrapedRecord
from osint_nexus.utils.http import random_delay
from osint_nexus.utils.logging import get_logger

AHU_BASE = "https://ahu.go.id"

logger = get_logger("scraper.ahu")

_browser_instance: Optional[BrowserManager] = None


def _get_browser() -> BrowserManager:
    """Lazy BrowserManager getter. Called from inside async contexts."""
    global _browser_instance
    if _browser_instance is None:
        _browser_instance = BrowserManager(
            BrowserConfig(
                headless=True,
                locale="id-ID",
                timezone="Asia/Makassar",
                max_contexts=2,
                page_load_timeout_ms=30000,
            )
        )
    return _browser_instance


def _shutdown_browser() -> None:
    """Best-effort atexit hook: closes the lazy browser if it was ever initialized.

    WARNING (Codex GPT-5.4 review N3): this creates a new event loop to close
    Playwright objects that were created on the original loop. This is a known
    footgun — it may fail silently if the original loop is still alive or if
    Playwright objects hold references to it. The PRIMARY shutdown path should
    be the runtime owner (dossier CLI, pipeline runner) calling:
        await _get_browser().close()
    explicitly in its own `finally` block. This atexit hook is a safety net
    for cases where the caller forgets.
    """
    global _browser_instance
    if _browser_instance is None:
        return
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_browser_instance.close())
        loop.close()
    except Exception as exc:
        logger.warning("AHU browser atexit shutdown failed (best-effort): %s", exc)
    finally:
        _browser_instance = None


atexit.register(_shutdown_browser)


class AHUScraper(BaseScraper):
    """Scrapes AHU (Administrasi Hukum Umum) — PT and Yayasan registries."""

    name = "ahu"

    async def scrape(self, query: str, **kwargs: Any) -> list[ScrapedRecord]:
        search_type = kwargs.get("search_type", "pt")
        records: list[ScrapedRecord] = []
        search_url = f"{AHU_BASE}/pencarian/profil-{search_type}"

        browser = _get_browser()

        async with browser.get_page(search_url) as page:
            try:
                await random_delay(1, 3)

                # AHU uses input[name='nama'] — no submit button, Enter key triggers search
                search_input = page.locator("input[name='nama']")
                await search_input.fill(query)
                await random_delay(0.5, 1.5)
                await search_input.press("Enter")

                await page.wait_for_load_state("networkidle", timeout=15000)
                await random_delay(1, 2)

                # AHU renders results as div cards inside section#hasil_cari,
                # NOT as table rows. Each card is div.cl0 or div.cl1.
                cards = await page.locator("section#hasil_cari div[class^='cl']").all()
                self.logger.info("AHU search '%s': %d results", query, len(cards))

                for card in cards:
                    # Company name in strong.judul with data-id attribute
                    nama_el = card.locator("strong.judul")
                    nama = (await nama_el.inner_text()).strip() if await nama_el.count() else ""
                    data_id = await nama_el.get_attribute("data-id") if await nama_el.count() else ""

                    # Address in div.alamat
                    alamat_el = card.locator("div.alamat")
                    alamat = (await alamat_el.inner_text()).strip() if await alamat_el.count() else ""

                    # City/province in div.kabpro
                    kabpro_el = card.locator("div.kabpro")
                    kabpro = (await kabpro_el.inner_text()).strip() if await kabpro_el.count() else ""

                    if not nama:
                        continue

                    record_data: dict[str, Any] = {
                        "nama": nama,
                        "data_id": data_id,
                        "alamat": alamat,
                        "kabpro": kabpro,
                        "tipe": search_type,
                    }

                    records.append(
                        ScrapedRecord(
                            source="ahu",
                            entity_type="company",
                            url=f"{AHU_BASE}/pencarian/profil-{search_type}?id={data_id}" if data_id else search_url,
                            raw_data=record_data,
                        )
                    )

            except Exception as e:
                self.logger.error("AHU scrape failed: %s", e)

        self.save_records(records)
        return records

    async def _fetch_detail(self, context: Any, url: str) -> dict[str, Any]:
        """Open throwaway tab from shared context — preserves row iteration."""
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=20000)
            data: dict[str, Any] = {}
            pairs = await page.locator("table tr").all()
            for pair in pairs:
                cells = await pair.locator("td, th").all()
                if len(cells) >= 2:
                    key = (
                        (await cells[0].inner_text())
                        .strip()
                        .lower()
                        .replace(" ", "_")
                    )
                    val = (await cells[1].inner_text()).strip()
                    if key and val:
                        data[key] = val
            return data
        finally:
            await page.close()
