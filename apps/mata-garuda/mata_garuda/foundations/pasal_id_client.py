"""pasal.id API client wrapper.

Source: ilhamfp/pasal (https://pasal.id) — 40,143 Indonesian regulations indexed.
Discovered in R2 SOTA research 2026-05-08.

This client uses the public REST surface; the FastMCP server upstream
exposes the same primitives. We use httpx async for parity with the rest of
the mata-garuda stack.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

PASAL_ID_BASE_URL = "https://pasal.id/api"
DEFAULT_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class LawSearchResult:
    id: str
    title: str
    year: int
    kind: str  # "UU" | "PP" | "Perpres" | "PMK" | "PER" | "KEP" | "SE" | etc.


@dataclass(frozen=True)
class LawStatus:
    id: str
    status: Literal["berlaku", "dicabut", "diubah", "tidak_berlaku"]
    superseded_by: Optional[str]


class PasalIdClient:
    """Async client for pasal.id regulation search + status lookup."""

    def __init__(self, base_url: str = PASAL_ID_BASE_URL, timeout: float = DEFAULT_TIMEOUT_SECONDS):
        self._base_url = base_url
        self._timeout = timeout

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def search_laws(self, query: str, limit: int = 10) -> list[LawSearchResult]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(
                f"{self._base_url}/laws/search",
                params={"q": query, "limit": limit},
            )
            response.raise_for_status()
            payload = response.json()
        return [
            LawSearchResult(
                id=item["id"],
                title=item["title"],
                year=int(item["year"]),
                kind=item.get("kind", "UNKNOWN"),
            )
            for item in payload.get("results", [])
        ]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def get_law_status(self, law_id: str) -> LawStatus:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(f"{self._base_url}/laws/{law_id}/status")
            response.raise_for_status()
            payload = response.json()
        return LawStatus(
            id=payload["id"],
            status=payload["status"],
            superseded_by=payload.get("superseded_by"),
        )
