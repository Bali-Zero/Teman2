"""OpenSanctions Indonesia datasets client.

Discovered in R7 SOTA 2026-05-08. Free non-commercial.
Datasets:
  - id_dttot (Indonesian Suspected Terrorists, daily)
  - id_regional_2018 (2018 Regional Head Election Results)

Used for KYC/PEP screening of Bali Zero clients (B6 sink).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

OPENSANCTIONS_BASE = "https://data.opensanctions.org/datasets"
DEFAULT_TIMEOUT = 60.0


@dataclass(frozen=True)
class SanctionEntity:
    id: str
    schema: str  # "Person" | "Organization" | "Address" etc.
    caption: str
    properties: dict


class OpenSanctionsClient:
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def fetch_dttot(self) -> list[SanctionEntity]:
        url = f"{OPENSANCTIONS_BASE}/latest/id_dttot/entities.ftm.json"
        return await self._fetch_jsonlines(url)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    async def fetch_regional_2018(self) -> list[SanctionEntity]:
        url = f"{OPENSANCTIONS_BASE}/latest/id_regional_2018/entities.ftm.json"
        return await self._fetch_jsonlines(url)

    async def match_name(self, name_substring: str) -> list[SanctionEntity]:
        entities = await self.fetch_dttot()
        needle = name_substring.lower()
        return [e for e in entities if needle in e.caption.lower()]

    @staticmethod
    async def _fetch_jsonlines(url: str) -> list[SanctionEntity]:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get(url)
            response.raise_for_status()
            text = response.text
        entities = []
        for line in text.strip().split("\n"):
            if not line.strip():
                continue
            payload = json.loads(line)
            entities.append(
                SanctionEntity(
                    id=payload["id"],
                    schema=payload["schema"],
                    caption=payload.get("caption", ""),
                    properties=payload.get("properties", {}),
                )
            )
        return entities
