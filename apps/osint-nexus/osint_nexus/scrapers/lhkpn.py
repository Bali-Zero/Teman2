"""LHKPN scraper — elhkpn.kpk.go.id asset declarations."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from bs4 import BeautifulSoup

from osint_nexus.scrapers.base import BaseScraper, ScrapedRecord
from osint_nexus.utils.http import get_client, random_delay

BASE_URL = "https://elhkpn.kpk.go.id/portal/user/pengumumanlhkpn"
SEARCH_URL = "https://elhkpn.kpk.go.id/portal/user/pengumumanlhkpn/index"


class LHKPNScraper(BaseScraper):
    """Scrapes LHKPN (harta kekayaan) declarations from KPK portal."""

    name = "lhkpn"

    async def scrape(self, query: str, **kwargs: Any) -> list[ScrapedRecord]:
        """Search by name, return asset declaration records."""
        records: list[ScrapedRecord] = []
        async with get_client() as client:
            # Search page to get session/token
            resp = await client.get(BASE_URL)
            resp.raise_for_status()

            # POST search
            await random_delay()
            search_resp = await client.post(
                SEARCH_URL,
                data={
                    "q": query,
                    "capilfilterset": "",
                },
                headers={"Referer": BASE_URL},
            )
            search_resp.raise_for_status()
            soup = BeautifulSoup(search_resp.text, "lxml")

            # Parse result rows
            rows = soup.select("table.table tbody tr")
            self.logger.info("LHKPN search '%s': %d results", query, len(rows))

            for row in rows:
                cells = row.select("td")
                if len(cells) < 5:
                    continue

                record_data = {
                    "nama": cells[1].get_text(strip=True),
                    "instansi": cells[2].get_text(strip=True),
                    "jabatan": cells[3].get_text(strip=True),
                    "tahun_pelaporan": cells[4].get_text(strip=True),
                }

                # Try to get detail link
                detail_link = row.select_one("a[href*='detailannounce']")
                detail_url = ""
                if detail_link:
                    detail_url = detail_link["href"]
                    if not detail_url.startswith("http"):
                        detail_url = f"https://elhkpn.kpk.go.id{detail_url}"

                    # Fetch detail page
                    await random_delay()
                    try:
                        detail_resp = await client.get(detail_url)
                        detail_resp.raise_for_status()
                        detail_soup = BeautifulSoup(detail_resp.text, "lxml")
                        record_data.update(self._parse_detail(detail_soup))
                    except Exception as e:
                        self.logger.warning("Failed detail fetch: %s", e)

                records.append(
                    ScrapedRecord(
                        source="lhkpn",
                        entity_type="asset_declaration",
                        url=detail_url or BASE_URL,
                        raw_data=record_data,
                    )
                )

        self.save_records(records)
        return records

    def _parse_detail(self, soup: BeautifulSoup) -> dict[str, Any]:
        """Extract structured data from LHKPN detail page."""
        data: dict[str, Any] = {}

        # NHK (registration number)
        nhk_el = soup.select_one("td:-soup-contains('NHK') + td")
        if nhk_el:
            data["nhk"] = nhk_el.get_text(strip=True)

        # Parse summary tables for totals
        for label_text in [
            "Harta Tidak Bergerak",
            "Harta Bergerak",
            "Surat Berharga",
            "Kas dan Setara Kas",
            "Harta Lainnya",
            "Total Harta",
            "Total Hutang",
            "Total Harta Kekayaan",
        ]:
            el = soup.find("td", string=lambda t: t and label_text in t if t else False)
            if el:
                val_el = el.find_next_sibling("td")
                if val_el:
                    data[label_text.lower().replace(" ", "_")] = val_el.get_text(strip=True)

        return data
