"""Putusan MA scraper — court decisions from putusan3.mahkamahagung.go.id."""

from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from osint_nexus.scrapers.base import BaseScraper, ScrapedRecord
from osint_nexus.utils.http import get_client, random_delay

PUTUSAN_BASE = "https://putusan3.mahkamahagung.go.id"
SEARCH_URL = f"{PUTUSAN_BASE}/search.html"


class PutusanMAScraper(BaseScraper):
    """Scrapes court decisions from Mahkamah Agung directory."""

    name = "putusan_ma"

    async def scrape(self, query: str, **kwargs: Any) -> list[ScrapedRecord]:
        """Search court decisions by name or keyword.

        Args:
            query: Person name or case keyword
            kwargs:
                kategori: 'pidana', 'perdata', 'tun', etc.
                max_pages: max pages to fetch (default: 3)
        """
        kategori = kwargs.get("kategori", "")
        max_pages = kwargs.get("max_pages", 3)
        records: list[ScrapedRecord] = []

        async with get_client() as client:
            for page_num in range(1, max_pages + 1):
                await random_delay()

                params: dict[str, Any] = {
                    "q": f'"{query}"',
                    "page": page_num,
                }
                if kategori:
                    params["cat"] = kategori

                try:
                    resp = await client.get(SEARCH_URL, params=params)
                    resp.raise_for_status()
                except Exception as e:
                    self.logger.warning("Putusan MA page %d failed: %s", page_num, e)
                    continue

                soup = BeautifulSoup(resp.text, "lxml")
                result_items = soup.select(".result-item, .search-result-item, .entry")

                if not result_items:
                    # Try alternative selectors
                    result_items = soup.select("table tbody tr")

                if not result_items:
                    self.logger.info("No more results at page %d", page_num)
                    break

                self.logger.info("Putusan MA page %d: %d items", page_num, len(result_items))

                for item in result_items:
                    record = self._parse_result(item)
                    if record:
                        records.append(record)

        self.save_records(records)
        return records

    def _parse_result(self, item: Any) -> ScrapedRecord | None:
        """Parse a single search result."""
        try:
            # Try structured result format
            title_el = item.select_one("h3 a, .title a, a.result-title")
            if not title_el:
                title_el = item.select_one("a")

            if not title_el:
                return None

            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            url = href if href.startswith("http") else f"{PUTUSAN_BASE}{href}"

            # Extract metadata
            meta: dict[str, str] = {"judul": title}

            # Court name
            court_el = item.select_one(".court, .pengadilan")
            if court_el:
                meta["pengadilan"] = court_el.get_text(strip=True)

            # Case number
            number_el = item.select_one(".nomor, .case-number")
            if number_el:
                meta["nomor_perkara"] = number_el.get_text(strip=True)
            elif "/" in title:
                meta["nomor_perkara"] = title

            # Date
            date_el = item.select_one(".date, .tanggal")
            if date_el:
                meta["tanggal_putusan"] = date_el.get_text(strip=True)

            # Category
            cat_el = item.select_one(".category, .kategori")
            if cat_el:
                meta["kategori"] = cat_el.get_text(strip=True)

            # Snippet/summary
            snippet_el = item.select_one(".snippet, .summary, p")
            if snippet_el:
                meta["ringkasan"] = snippet_el.get_text(strip=True)[:500]

            return ScrapedRecord(
                source="putusan_ma",
                entity_type="court_decision",
                url=url,
                raw_data=meta,
            )
        except Exception as e:
            self.logger.warning("Parse error: %s", e)
            return None

    async def fetch_full_decision(self, url: str) -> dict[str, Any]:
        """Fetch and parse full court decision text."""
        async with get_client() as client:
            await random_delay()
            resp = await client.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")

            data: dict[str, Any] = {}

            # Decision text
            content = soup.select_one("#putusan-content, .putusan-body, .content-putusan")
            if content:
                data["full_text"] = content.get_text(separator="\n", strip=True)[:10000]

            # Parties
            for label in ["Penggugat", "Tergugat", "Terdakwa", "Penuntut"]:
                el = soup.find(string=lambda t: t and label in t if t else False)
                if el and el.parent:
                    sibling = el.parent.find_next_sibling()
                    if sibling:
                        data[label.lower()] = sibling.get_text(strip=True)

            # Amar putusan
            amar = soup.find(string=lambda t: t and "MENGADILI" in t.upper() if t else False)
            if amar and amar.parent:
                data["amar"] = amar.parent.get_text(separator="\n", strip=True)[:2000]

            return data
