"""LHKPN scraper — elhkpn.kpk.go.id asset declarations.

As of 2026-04, KPK moved from a simple GET endpoint to a SPA with
reCAPTCHA v3 (invisible). This scraper uses browser-core to:
1. Navigate to the homepage
2. Remove the modal overlay
3. Fill the search form
4. Generate and inject a reCAPTCHA v3 token
5. Submit and parse the results table
6. Download PDF detail for each declaration (via setid → timer → auto-download)

PDF download flow (reverse-engineered 2026-04-08):
- Each row has a `data-id` in the Aksi column (base64 encoded)
- POST to /portal/user/setid/ with {id: data-id} sets the server session
- Navigate to /portal/user/timer/ which auto-downloads the PDF after 3 sec
- Playwright catches the download via expect_download()
- Files are saved as LHKPN_{NHK}_{nama}_{tahun}.pdf
"""
from __future__ import annotations

import asyncio
import atexit
import re
from pathlib import Path
from typing import Any, Optional

from browser_core import BrowserConfig, BrowserManager

from osint_nexus.config import RAW_DIR
from osint_nexus.scrapers.base import BaseScraper, ScrapedRecord
from osint_nexus.utils.http import random_delay
from osint_nexus.utils.logging import get_logger

BASE_URL = "https://elhkpn.kpk.go.id"
TIMER_URL = "https://elhkpn.kpk.go.id/portal/user/timer/"
SETID_URL = "https://elhkpn.kpk.go.id/portal/user/setid/"
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
        """Search by name/NIK, return asset declaration records + download PDFs.

        Args:
            query: Name or NIK to search
            kwargs:
                tahun: Optional year filter
                download_pdf: Download full PDF declarations (default True)
                pdf_dir: Directory for PDFs (default: RAW_DIR / "lhkpn" / "pdfs")
        """
        download_pdf = kwargs.get("download_pdf", True)
        pdf_dir = Path(kwargs.get("pdf_dir", self._output_dir / "pdfs"))
        pdf_dir.mkdir(parents=True, exist_ok=True)

        records: list[ScrapedRecord] = []
        browser = _get_browser()

        async with browser.get_context() as ctx:
            page = await ctx.new_page()
            try:
                await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(3000)

                # Remove modal overlay
                await page.evaluate("""() => {
                    document.querySelectorAll('.remodal-wrapper, .remodal-overlay, .remodal')
                        .forEach(el => el.remove());
                }""")
                await random_delay(0.5, 1)

                # Fill search form
                await page.fill("#CARI_NAMA", query)
                await random_delay(0.5, 1)

                tahun = kwargs.get("tahun")
                if tahun:
                    await page.fill("#CARI_TAHUN", str(tahun))

                # reCAPTCHA v3 token
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

                # Submit
                async with page.expect_navigation(wait_until="load", timeout=30000):
                    await page.click("#announ button[type=submit]")
                await page.wait_for_timeout(3000)
                await random_delay(1, 2)

                # Parse total
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
                    "LHKPN search '%s': %d rows, %d total",
                    query,
                    len(rows),
                    total_entries,
                )

                for row in rows:
                    cells = await row.locator("td").all()
                    if len(cells) < 14:
                        continue

                    # [0]=hash [1]=id [2]=_ [3]=tahun [4]=type [5]=no
                    # [6]=nama [7]=lembaga [8]=unit_kerja [9]=jabatan
                    # [10]=tanggal [11]=jenis [12]=total_harta [13]=aksi
                    tahun_data = (await cells[3].inner_text()).strip()
                    nama = (await cells[6].inner_text()).strip()
                    lembaga = (await cells[7].inner_text()).strip()
                    unit_kerja = (await cells[8].inner_text()).strip()
                    jabatan = (await cells[9].inner_text()).strip()
                    tanggal_lapor = (await cells[10].inner_text()).strip()
                    jenis_laporan = (await cells[11].inner_text()).strip()
                    total_harta_raw = (await cells[12].inner_text()).strip()
                    total_harta = self._parse_rupiah(total_harta_raw)

                    # Get data-id for PDF download
                    dl_btn = cells[13].locator("a.yesdownl")
                    data_id = (
                        await dl_btn.get_attribute("data-id")
                        if await dl_btn.count()
                        else None
                    )

                    # Download PDF if requested
                    pdf_path: str = ""
                    if download_pdf and data_id:
                        try:
                            pdf_path = await self._download_pdf(
                                ctx, page, data_id, nama, tahun_data, pdf_dir
                            )
                        except Exception as exc:
                            self.logger.warning(
                                "PDF download failed for %s/%s: %s",
                                nama,
                                tahun_data,
                                exc,
                            )

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
                        "data_id": data_id or "",
                        "pdf_path": pdf_path,
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
            finally:
                await page.close()

        self.save_records(records)
        return records

    async def _download_pdf(
        self,
        ctx: Any,
        search_page: Any,
        data_id: str,
        nama: str,
        tahun: str,
        pdf_dir: Path,
    ) -> str:
        """Download a single LHKPN PDF declaration.

        Flow: POST setid → navigate to /timer/ → catch auto-download.
        Returns the saved file path as string.
        """
        # Step 1: Set server session with the target declaration ID
        await search_page.evaluate(
            """(args) => new Promise((resolve, reject) => {
                $.post(args.url, {id: args.id}, () => resolve())
                 .fail((xhr) => reject('setid failed: ' + xhr.status));
            })""",
            {"url": SETID_URL, "id": data_id},
        )

        # Step 2: Open timer page in new tab and catch auto-download
        timer_page = await ctx.new_page()
        try:
            async with timer_page.expect_download(timeout=30000) as dl_info:
                await timer_page.goto(TIMER_URL, wait_until="load", timeout=30000)

            download = await dl_info.value

            # Step 3: Save with descriptive filename
            safe_nama = re.sub(r"[^\w\s-]", "", nama).strip().replace(" ", "_")[:50]
            filename = f"LHKPN_{safe_nama}_{tahun}.pdf"
            save_path = pdf_dir / filename
            await download.save_as(str(save_path))

            size = save_path.stat().st_size
            self.logger.info("PDF saved: %s (%d bytes)", filename, size)
            await random_delay(1, 2)

            return str(save_path)
        finally:
            await timer_page.close()

    @staticmethod
    def _parse_rupiah(text: str) -> int:
        """Parse 'Rp.34.983.828.731' → 34983828731."""
        digits = re.sub(r"[^\d]", "", text)
        return int(digits) if digits else 0
