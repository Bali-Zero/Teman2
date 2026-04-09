"""Wikipedia (ID/EN) + Wikidata scraper.

Both APIs are global, no geo-block, no rate-limiting for reasonable usage.
Good for:
- Biographies of high-profile pejabat
- Organization histories (ministries, kanim structure)
- Locations (kabupaten, kecamatan)
- Dates (established, renamed, transferred)
"""

from __future__ import annotations

from typing import Any

from osint_nexus.scrapers.base import BaseScraper, ScrapedRecord
from osint_nexus.utils.http import get_client, random_delay

WIKI_ID_API = "https://id.wikipedia.org/w/api.php"
WIKI_EN_API = "https://en.wikipedia.org/w/api.php"

# MediaWiki policy requires identifying UA with contact info.
# https://meta.wikimedia.org/wiki/User-Agent_policy
WIKI_UA = "OSINT-Nexus/0.2 (research; contact: zero@balizero.com)"


class WikiScraper(BaseScraper):
    """Wikipedia ID + EN search + page extract."""

    name = "wiki"

    async def scrape(self, query: str, **kwargs: Any) -> list[ScrapedRecord]:
        """Search Wikipedia for query, fetch full extract of top results.

        Args:
            query: Search term
            kwargs:
                limit: max results per language (default: 5)
                lang: 'id' (default), 'en', or 'both'
        """
        limit = kwargs.get("limit", 5)
        lang = kwargs.get("lang", "both")

        records: list[ScrapedRecord] = []

        # Override default UA with MediaWiki-compliant identifier
        async with get_client(headers={"User-Agent": WIKI_UA}) as client:
            langs_to_query = ["id", "en"] if lang == "both" else [lang]
            for lang_code in langs_to_query:
                api = WIKI_ID_API if lang_code == "id" else WIKI_EN_API
                records.extend(await self._search_and_fetch(client, api, query, limit, lang_code))
                await random_delay(0.5, 1.5)

        self.save_records(records)
        return records

    async def _search_and_fetch(
        self, client: Any, api: str, query: str, limit: int, lang_code: str
    ) -> list[ScrapedRecord]:
        """Search → get page IDs → fetch extracts in one batch."""
        records: list[ScrapedRecord] = []

        # Step 1: search
        try:
            search_resp = await client.get(
                api,
                params={
                    "action": "query",
                    "format": "json",
                    "list": "search",
                    "srsearch": query,
                    "srlimit": limit,
                },
            )
            search_resp.raise_for_status()
            search_data = search_resp.json()
        except Exception as e:
            self.logger.warning("Wiki search failed (%s): %s", lang_code, e)
            return records

        hits = search_data.get("query", {}).get("search", [])
        if not hits:
            return records

        self.logger.info("Wiki %s: %d hits for '%s'", lang_code, len(hits), query)

        page_ids = [str(h["pageid"]) for h in hits]
        titles_map = {h["pageid"]: h["title"] for h in hits}

        # Step 2: batch fetch extracts + categories + links
        await random_delay(0.3, 0.8)
        try:
            extract_resp = await client.get(
                api,
                params={
                    "action": "query",
                    "format": "json",
                    "pageids": "|".join(page_ids),
                    "prop": "extracts|info|categories",
                    "exintro": 1,  # Only intro paragraph(s)
                    "explaintext": 1,  # Plain text, not HTML
                    "inprop": "url",
                    "cllimit": 20,
                },
            )
            extract_resp.raise_for_status()
            extract_data = extract_resp.json()
        except Exception as e:
            self.logger.warning("Wiki extract failed (%s): %s", lang_code, e)
            return records

        pages = extract_data.get("query", {}).get("pages", {})
        for pid_str, page in pages.items():
            extract = page.get("extract", "")
            if not extract:
                continue

            categories = [
                c.get("title", "").replace("Kategori:", "").replace("Category:", "")
                for c in page.get("categories", [])
            ]

            records.append(
                ScrapedRecord(
                    source=f"wikipedia_{lang_code}",
                    entity_type="wiki_article",
                    url=page.get("fullurl", f"https://{lang_code}.wikipedia.org/?curid={pid_str}"),
                    raw_data={
                        "judul": page.get("title", titles_map.get(int(pid_str), "")),
                        "ringkasan": extract[:3000],  # Cap intro
                        "bahasa": lang_code,
                        "kategori": ", ".join(categories[:10]),
                        "pageid": pid_str,
                    },
                )
            )

        return records
