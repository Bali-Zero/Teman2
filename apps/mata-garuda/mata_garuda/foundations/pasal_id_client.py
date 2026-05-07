"""pasal.id API client wrapper.

Source: ilhamfp/pasal (https://pasal.id) — 40,143 Indonesian regulations indexed.
Discovered in R2 SOTA research 2026-05-08.

External-review fix (Codex GPT-5 + DeepSeek v4, 2026-05-08):
- Live API base is `/api/v1` (was `/api`)
- Bearer token auth required (was unauthenticated)
- Search response nests title/year/type under `work` (was top-level)

We accept missing token at construction time — `search_laws` raises
PasalIdAuthError if a request returns 401, instead of crashing on raise_for_status.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Optional

import httpx
from tenacity import (
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
)

PASAL_ID_BASE_URL = "https://pasal.id/api/v1"
DEFAULT_TIMEOUT_SECONDS = 30.0


class PasalIdAuthError(RuntimeError):
    """Raised when pasal.id returns 401/403 — bearer token missing or invalid."""


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

    def __init__(
        self,
        base_url: str = PASAL_ID_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        api_token: Optional[str] = None,
    ):
        self._base_url = base_url
        self._timeout = timeout
        self._api_token = api_token or os.environ.get("PASAL_ID_API_TOKEN")

    def _headers(self) -> dict:
        headers = {"Accept": "application/json"}
        if self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"
        return headers

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_not_exception_type(PasalIdAuthError),
    )
    async def search_laws(self, query: str, limit: int = 10) -> list[LawSearchResult]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(
                f"{self._base_url}/search",
                params={"q": query, "limit": limit},
                headers=self._headers(),
            )
            if response.status_code in (401, 403):
                raise PasalIdAuthError(
                    f"pasal.id auth failed ({response.status_code}). Set PASAL_ID_API_TOKEN env var."
                )
            response.raise_for_status()
            payload = response.json()
        results = []
        for item in payload.get("results", []):
            # Live API nests title/year/kind under `work`; tolerate both shapes.
            work = item.get("work", item)
            results.append(
                LawSearchResult(
                    id=item.get("id", work.get("id", "")),
                    title=work.get("title", item.get("title", "")),
                    year=int(work.get("year", item.get("year", 0))),
                    kind=work.get("type", work.get("kind", item.get("kind", "UNKNOWN"))),
                )
            )
        return results

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_not_exception_type(PasalIdAuthError),
    )
    async def get_law_status(self, law_id: str) -> LawStatus:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(
                f"{self._base_url}/laws/{law_id}/status",
                headers=self._headers(),
            )
            if response.status_code in (401, 403):
                raise PasalIdAuthError(
                    f"pasal.id auth failed ({response.status_code}). Set PASAL_ID_API_TOKEN env var."
                )
            response.raise_for_status()
            payload = response.json()
        return LawStatus(
            id=payload["id"],
            status=payload["status"],
            superseded_by=payload.get("superseded_by"),
        )
