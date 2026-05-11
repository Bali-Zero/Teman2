"""GDELT DOC 2.0 API client.

Discovered in R6 SOTA 2026-05-08. Free, no auth, 65 languages translated to EN.
Indonesia FIPS-2 = ID. Update frequency: every 15 minutes.

API base: https://api.gdeltproject.org/api/v2/doc/doc
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"
DEFAULT_TIMEOUT = 30.0


@dataclass(frozen=True)
class GdeltArticle:
    url: str
    title: str
    seen_date: Optional[datetime]
    domain: str
    language: str
    source_country: str


class GdeltClient:
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def search_indonesia(self, query: str, max_results: int = 50) -> list[GdeltArticle]:
        params = {
            "query": f'{query} sourcecountry:ID',
            "mode": "ArtList",
            "format": "json",
            "maxrecords": str(max_results),
        }
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get(GDELT_DOC_API, params=params)
            response.raise_for_status()
            payload = response.json()
        return [
            GdeltArticle(
                url=item["url"],
                title=item.get("title", ""),
                seen_date=self._parse_seen_date(item.get("seendate")),
                domain=item.get("domain", ""),
                language=item.get("language", ""),
                source_country=item.get("sourcecountry", ""),
            )
            for item in payload.get("articles", [])
        ]

    @staticmethod
    def _parse_seen_date(raw: Optional[str]) -> Optional[datetime]:
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%Y%m%dT%H%M%SZ")
        except ValueError:
            return None
