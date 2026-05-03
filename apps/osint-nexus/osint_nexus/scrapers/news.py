"""News aggregator scraper via Google News RSS.

Google News RSS is global, no geo-block, supports keyword search, returns
links to real news sites. Bypasses most .go.id restrictions because:
- RSS feed is served from Google global CDN
- Article URLs often point to CDN-backed news sites (Detik, Tempo, Kompas)
- We only need the title/snippet for NER; full article fetch is optional

Usage:
    scraper = NewsScraper()
    records = await scraper.scrape("kanim ngurah rai", max_items=30)
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET

from osint_nexus.scrapers.base import BaseScraper, ScrapedRecord
from osint_nexus.utils.http import get_client, random_delay

GNEWS_RSS = "https://news.google.com/rss/search"


class NewsScraper(BaseScraper):
    """Google News RSS scraper for Indonesian news."""

    name = "news"

    async def scrape(self, query: str, **kwargs: Any) -> list[ScrapedRecord]:
        """Fetch news items matching query.

        Args:
            query: Search keywords (will be URL-encoded)
            kwargs:
                max_items: max articles to return (default: 50)
                hl: language (default: 'id')
                gl: country (default: 'ID')
        """
        max_items = kwargs.get("max_items", 50)
        hl = kwargs.get("hl", "id")
        gl = kwargs.get("gl", "ID")

        records: list[ScrapedRecord] = []
        url = f"{GNEWS_RSS}?q={quote_plus(query)}&hl={hl}&gl={gl}&ceid={gl}:{hl}"

        async with get_client() as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
            except Exception as e:
                self.logger.warning("Google News fetch failed: %s", e)
                return records

            # Parse RSS XML
            try:
                root = ET.fromstring(resp.text)
            except ET.ParseError as e:
                self.logger.error("RSS parse error: %s", e)
                return records

            items = root.findall(".//item")
            self.logger.info("Google News: %d items for '%s'", len(items), query)

            for item in items[:max_items]:
                title = self._text(item, "title")
                link = self._text(item, "link")
                pub_date = self._text(item, "pubDate")
                description = self._text(item, "description")
                source_name = self._text(item, "source") or ""

                # Google News wraps description in HTML <a> etc.
                # Strip simple tags for NER friendliness.
                description = self._strip_html(description)

                # Separate publisher name from title (e.g. "Title - Detik")
                publisher = ""
                if " - " in title:
                    parts = title.rsplit(" - ", 1)
                    title, publisher = parts[0], parts[1]

                records.append(
                    ScrapedRecord(
                        source="google_news",
                        entity_type="article",
                        url=link,
                        raw_data={
                            "judul": title,
                            "ringkasan": description,
                            "tanggal_publikasi": pub_date,
                            "penerbit": publisher or source_name,
                            "bahasa": hl,
                        },
                    )
                )

            # Space out requests for follow-up queries
            await random_delay()

        self.save_records(records)
        return records

    @staticmethod
    def _text(element: ET.Element, tag: str) -> str:
        el = element.find(tag)
        return (el.text or "").strip() if el is not None and el.text else ""

    @staticmethod
    def _strip_html(text: str) -> str:
        """Remove basic HTML tags from RSS description."""
        import re
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
