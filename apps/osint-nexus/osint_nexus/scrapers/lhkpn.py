"""LHKPN scraper — elhkpn.kpk.go.id asset declarations.

As of 2026-04, KPK moved from a simple GET endpoint to a SPA with
reCAPTCHA v3 (invisible). This scraper uses browser-core to:
1. Navigate to the homepage
2. Remove the modal overlay
3. Fill the search form
4. Generate and inject a reCAPTCHA v3 token
5. Submit and parse the results table
"""
from __future__ import annotations

import asyncio
import atexit
import re
from typing import Any, Optional

from browser_core import BrowserConfig, BrowserManager

from osint_nexus.scrapers.base import BaseScraper, ScrapedRecord
from osint_nexus.utils.http import random_delay
from osint_nexus.utils.logging import get_logger

BASE_URL = "https://elhkpn.kpk.go.id"
RECAPTCHA_SITE_KEY = "6LfANPQrAAAAAFAKhYMdri6OAuMOPZZorjsCqUGk"

logger = get_logger("scraper.lhkpn")

# --- Lazy per-process BrowserManager (same pattern as ahu.py) ---
_browser_instance: Optional[BrowserManager] = None


def _get_browser() -> BrowserManager:
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
    """Best-effort atexit cleanup."""
    global _browser_instance
    if _browser_instance is None:
        return
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_browser_instance.close())
        loop.close()
    except Exception as exc:
        logger.warning("LHKPN browser atexit shutdown failed: %s", exc)
    finally:
        _browser_instance = None


atexit.register(_shutdown_browser)


class LHKPNScraper(BaseScraper):
    """Scrapes LHKPN (harta kekayaan) declarations from KPK e-Announcement."""

    name = "lhkpn"

    async def scrape(self, query: str, **kwargs: Any) -> list[ScrapedRecord]:
        """Search by name/NIK, return asset declaration records."""
        records: list[ScrapedRecord] = []
        browser = _get_browser()

        async with browser.get_page(BASE_URL) as page:
            try:
                await page.wait_for_load_state("networkidle")

                # Remove modal overlay that blocks interaction
                await page.evaluate("""() => {
                    document.querySelectorAll('.remodal-wrapper, .remodal-overlay, .remodal')
                        .forEach(el => el.remove());
                }""")
                await random_delay(0.5, 1)

                # Fill search form
                await page.fill("#CARI_NAMA", query)
                await random_delay(0.5, 1)

                # Optional: fill tahun if provided
                tahun = kwargs.get("tahun")
                if tahun:
                    await page.fill("#CARI_TAHUN", str(tahun))

                # Generate reCAPTCHA v3 token and inject it
                await page.evaluate(
                    """(siteKey) => {
                    return new Promise((resolve, reject) => {
                        if (typeof grecaptcha === 'undefined') {
                            reject('grecaptcha not loaded');
                            return;
                        }
                        grecaptcha.ready(() => {
                            grecaptcha.execute(siteKey, {action: 'search'})
                                .then(token => {
                                    const field = document.querySelector(
                                        '[name=g-recaptcha-response-announ]'
                                    );
                                    if (field) field.value = token;
                                    resolve(token);
                                })
                                .catch(err => reject(err.toString()));
                        });
                    });
                }""",
                    RECAPTCHA_SITE_KEY,
                )
                self.logger.info("reCAPTCHA v3 token generated for '%s'", query)

                # Submit — form POSTs to a new URL, wait for navigation
                async with page.expect_navigation(
                    wait_until="networkidle", timeout=30000
                ):
                    await page.click("#announ button[type=submit]")
                await page.wait_for_timeout(3000)
                await random_delay(1, 2)

                # Parse results table (we're now on /check_search_announ)
                # Get total from "Showing 1 to 10 of N entries"
                info_el = page.locator(".dataTables_info")
                info_text = (
                    await info_el.inner_text() if await info_el.count() else ""
                )
                total_match = re.search(r"of\s+([\d,]+)\s+entries", info_text)
                total_entries = (
                    int(total_match.group(1).replace(",", ""))
                    if total_match
                    else 0
                )

                rows = await page.locator("table tbody tr").all()
                self.logger.info(
                    "LHKPN search '%s': %d rows on page, %d total entries",
                    query,
                    len(rows),
                    total_entries,
                )

                for row in rows:
                    cells = await row.locator("td").all()
                    if len(cells) < 13:
                        continue

                    # Real column layout (14 cells):
                    # [0]=hash [1]=id [2]=empty [3]=tahun [4]=type [5]=no
                    # [6]=NAMA [7]=lembaga [8]=unit_kerja [9]=jabatan
                    # [10]=tanggal_lapor [11]=jenis_laporan [12]=total_harta [13]=aksi
                    tahun_data = (await cells[3].inner_text()).strip()
                    nama = (await cells[6].inner_text()).strip()
                    lembaga = (await cells[7].inner_text()).strip()
                    unit_kerja = (await cells[8].inner_text()).strip()
                    jabatan = (await cells[9].inner_text()).strip()
                    tanggal_lapor = (await cells[10].inner_text()).strip()
                    jenis_laporan = (await cells[11].inner_text()).strip()
                    total_harta_raw = (await cells[12].inner_text()).strip()

                    # Parse total harta (e.g., "Rp.34.983.828.731")
                    total_harta = self._parse_rupiah(total_harta_raw)

                    record_data: dict[str, Any] = {
                        "nama": nama,
                        "tahun_data": tahun_data,
                        "lembaga": lembaga,
                        "unit_kerja": unit_kerja,
                        "jabatan": jabatan,
                        "tanggal_lapor": tanggal_lapor,
                        "jenis_laporan": jenis_laporan,
                        "total_harta_raw": total_harta_raw,
                        "total_harta": total_harta,
                    }

                    records.append(
                        ScrapedRecord(
                            source="lhkpn",
                            entity_type="asset_declaration",
                            url=BASE_URL,
                            raw_data=record_data,
                        )
                    )

            except Exception as e:
                self.logger.error("LHKPN scrape failed: %s", e)

        self.save_records(records)
        return records

    @staticmethod
    def _parse_rupiah(text: str) -> int:
        """Parse 'Rp.34.983.828.731' → 34983828731."""
        digits = re.sub(r"[^\d]", "", text)
        return int(digits) if digits else 0
