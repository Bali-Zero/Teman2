"""LPSE scraper — government procurement data from SPSE/INAPROC."""

from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from osint_nexus.scrapers.base import BaseScraper, ScrapedRecord
from osint_nexus.utils.http import get_client, random_delay
from osint_nexus.utils.logging import get_logger

# Kemenkumham LPSE instance
LPSE_BASE = "https://lpse.kemenkumham.go.id"
# Alternative: INAPROC aggregator
INAPROC_API = "https://isb.lkpp.go.id/isb-2/api"

logger = get_logger("scraper.lpse")


class LPSEScraper(BaseScraper):
    """Scrapes tender/procurement data from LPSE portals."""

    name = "lpse"

    async def scrape(self, query: str, **kwargs: Any) -> list[ScrapedRecord]:
        """Search tenders by keyword or satker name.

        Args:
            query: Search term (e.g. 'Kantor Imigrasi Ngurah Rai')
            kwargs:
                tahun: year filter (default: current)
                max_pages: max result pages to fetch (default: 5)
        """
        max_pages = kwargs.get("max_pages", 5)
        records: list[ScrapedRecord] = []

        async with get_client() as client:
            for page in range(max_pages):
                await random_delay()
                url = f"{LPSE_BASE}/eproc4/dt/lelang"
                try:
                    resp = await client.get(
                        url,
                        params={
                            "draw": page + 1,
                            "start": page * 10,
                            "length": 10,
                            "search[value]": query,
                            "columns[0][data]": "0",
                        },
                        headers={
                            "X-Requested-With": "XMLHttpRequest",
                            "Referer": f"{LPSE_BASE}/eproc4/lelang",
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    self.logger.warning("LPSE page %d failed: %s", page, e)
                    # Try HTML fallback
                    records.extend(await self._scrape_html(client, query, page))
                    continue

                items = data.get("data", [])
                if not items:
                    break

                for item in items:
                    record = self._parse_lpse_item(item)
                    if record:
                        records.append(record)

                self.logger.info("LPSE page %d: %d items", page, len(items))

        self.save_records(records)
        return records

    async def _scrape_html(
        self, client: Any, query: str, page: int
    ) -> list[ScrapedRecord]:
        """Fallback HTML scraping when AJAX endpoint isn't available."""
        records: list[ScrapedRecord] = []
        try:
            resp = await client.get(
                f"{LPSE_BASE}/eproc4/lelang",
                params={"page": page + 1},
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            for row in soup.select("table tbody tr"):
                cells = row.select("td")
                if len(cells) < 5:
                    continue

                detail_link = row.select_one("a[href]")
                detail_url = ""
                if detail_link:
                    href = detail_link.get("href", "")
                    detail_url = href if href.startswith("http") else f"{LPSE_BASE}{href}"

                records.append(
                    ScrapedRecord(
                        source="lpse",
                        entity_type="tender",
                        url=detail_url or LPSE_BASE,
                        raw_data={
                            "nama_paket": cells[1].get_text(strip=True) if len(cells) > 1 else "",
                            "instansi": cells[2].get_text(strip=True) if len(cells) > 2 else "",
                            "hps": cells[3].get_text(strip=True) if len(cells) > 3 else "",
                            "tahap": cells[4].get_text(strip=True) if len(cells) > 4 else "",
                        },
                    )
                )
        except Exception as e:
            self.logger.warning("LPSE HTML fallback failed: %s", e)

        return records

    def _parse_lpse_item(self, item: list | dict) -> ScrapedRecord | None:
        """Parse a single LPSE DataTables row."""
        try:
            if isinstance(item, list):
                # DataTables array format
                kode = item[0] if len(item) > 0 else ""
                nama_html = item[1] if len(item) > 1 else ""
                instansi = item[2] if len(item) > 2 else ""
                hps = item[3] if len(item) > 3 else ""
                tahap = item[4] if len(item) > 4 else ""

                # Extract link from HTML in nama field
                soup = BeautifulSoup(str(nama_html), "lxml")
                link = soup.select_one("a")
                nama = link.get_text(strip=True) if link else str(nama_html)
                url = link.get("href", "") if link else ""
                if url and not url.startswith("http"):
                    url = f"{LPSE_BASE}{url}"

                return ScrapedRecord(
                    source="lpse",
                    entity_type="tender",
                    url=url or LPSE_BASE,
                    raw_data={
                        "kode_tender": str(kode),
                        "nama_paket": nama,
                        "instansi": str(instansi),
                        "hps": str(hps),
                        "tahap": str(tahap),
                    },
                )
            elif isinstance(item, dict):
                return ScrapedRecord(
                    source="lpse",
                    entity_type="tender",
                    url=item.get("url", LPSE_BASE),
                    raw_data=item,
                )
        except Exception as e:
            self.logger.warning("Failed to parse LPSE item: %s", e)
        return None

    async def scrape_detail(self, tender_url: str) -> dict[str, Any]:
        """Fetch tender detail page for winner info."""
        async with get_client() as client:
            await random_delay()
            resp = await client.get(tender_url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            detail: dict[str, Any] = {}

            # Winner info
            winner_section = soup.find("th", string=lambda t: t and "Pemenang" in t if t else False)
            if winner_section:
                row = winner_section.find_parent("tr")
                if row:
                    tds = row.find_all("td")
                    if tds:
                        detail["pemenang"] = tds[-1].get_text(strip=True)

            # Contract value
            value_section = soup.find("th", string=lambda t: t and "Nilai Kontrak" in t if t else False)
            if value_section:
                row = value_section.find_parent("tr")
                if row:
                    tds = row.find_all("td")
                    if tds:
                        detail["nilai_kontrak"] = tds[-1].get_text(strip=True)

            return detail
