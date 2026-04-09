"""OpenTender.net API scraper — Indonesian procurement data via ICW/LKPP mirror.

opentender.net aggregates all LPSE instances and exposes them via REST API
with ODbL license. Works from any IP (global CDN). Bypasses broken TLS on
individual LPSE sites like lpse.kemenkumham.go.id.

Returns: package_name, winner_name, winner_tax_id, contract_final, fiscal_year,
         announcement_date, lpse_name, klpd_name, etc.
"""

from __future__ import annotations

from typing import Any

from osint_nexus.scrapers.base import BaseScraper, ScrapedRecord
from osint_nexus.utils.http import get_client, random_delay

OPENTENDER_API = "https://opentender.net/api/tender/"


class OpenTenderScraper(BaseScraper):
    """Scrapes procurement data from opentender.net API."""

    name = "opentender"

    async def scrape(self, query: str, **kwargs: Any) -> list[ScrapedRecord]:
        """Search tenders by keyword.

        Args:
            query: Search term (e.g. 'imigrasi kelas I khusus')
            kwargs:
                max_pages: max API pages (default: 5, 20 results/page)
                page_size: results per page (default: 20)
        """
        max_pages = kwargs.get("max_pages", 5)
        page_size = kwargs.get("page_size", 20)
        records: list[ScrapedRecord] = []

        async with get_client() as client:
            page = 1
            while page <= max_pages:
                await random_delay(0.5, 1.5)
                try:
                    resp = await client.get(
                        OPENTENDER_API,
                        params={
                            "q": query,
                            "format": "json",
                            "page": page,
                            "page_size": page_size,
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    self.logger.warning("OpenTender page %d failed: %s", page, e)
                    break

                results = data.get("results", [])
                total = data.get("count", 0)
                self.logger.info(
                    "OpenTender page %d: %d results (total: %d)",
                    page, len(results), total,
                )

                if not results:
                    break

                for item in results:
                    records.append(self._parse_item(item))

                # Check if more pages
                if not data.get("links", {}).get("next"):
                    break
                page += 1

        self.save_records(records)
        return records

    def _parse_item(self, item: dict[str, Any]) -> ScrapedRecord:
        """Convert an opentender API result to ScrapedRecord."""
        return ScrapedRecord(
            source="opentender",
            entity_type="tender",
            url=f"https://opentender.net/tender/{item.get('id', '')}",
            raw_data={
                "nama_paket": item.get("package_name", ""),
                "pemenang": item.get("winner_name", ""),
                "npwp_pemenang": item.get("winner_tax_id", ""),
                "nilai_kontrak": str(item.get("contract_final", "")),
                "tahun_anggaran": item.get("fiscal_year", ""),
                "tanggal_pengumuman": item.get("announcement_date", ""),
                "lpse": item.get("lpse_name", ""),
                "instansi": item.get("klpd_name", ""),
                "kode_rup": item.get("rup_code", ""),
                "kode_lelang": item.get("auction_code", ""),
                "skor": str(item.get("total_score", "")),
                "kategori": item.get("category_label", ""),
                "sub_kategori": item.get("sub_category_label", ""),
            },
        )
