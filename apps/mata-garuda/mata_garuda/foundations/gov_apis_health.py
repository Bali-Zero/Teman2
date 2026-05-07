"""Indonesian gov-apis health monitor.

Forks the spirit of suryast/indonesia-gov-apis (50+ portal status tracker).
We probe a curated subset of 14+ portals relevant to Bali Zero monthly.

Discovery: R2 SOTA 2026-05-08 — "22 operational, 6 geo-blocked,
5 CF/bot-challenged, 16 DNS failures (28% infrastructure dead)".
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx

INVENTORY_PATH = Path(__file__).parent.parent.parent / "data" / "gov_apis_inventory.json"
PROBE_TIMEOUT_SECONDS = 15.0

PortalStatus = Literal[
    "operational",
    "dns_failure",
    "cf_challenge",
    "geo_blocked",
    "http_5xx",
    "http_4xx",
    "timeout",
    "unknown",
]


@dataclass(frozen=True)
class PortalHealth:
    id: str
    url: str
    status: PortalStatus
    http_code: int | None = None
    error: str | None = None


@dataclass(frozen=True)
class HealthReport:
    total: int
    operational: int
    results: list[PortalHealth]


def load_inventory() -> list[dict]:
    return json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))


async def probe_portal(entry: dict) -> PortalHealth:
    portal_id = entry["id"]
    url = entry["url"]
    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_SECONDS, follow_redirects=True) as client:
            response = await client.get(url)
        code = response.status_code
        if code == 200:
            return PortalHealth(id=portal_id, url=url, status="operational", http_code=code)
        if code == 403 and "cloudflare" in response.headers.get("server", "").lower():
            return PortalHealth(id=portal_id, url=url, status="cf_challenge", http_code=code)
        if code == 451 or code == 403:
            return PortalHealth(id=portal_id, url=url, status="geo_blocked", http_code=code)
        if code >= 500:
            return PortalHealth(id=portal_id, url=url, status="http_5xx", http_code=code)
        if code >= 400:
            return PortalHealth(id=portal_id, url=url, status="http_4xx", http_code=code)
        return PortalHealth(id=portal_id, url=url, status="unknown", http_code=code)
    except httpx.ConnectError as exc:
        return PortalHealth(id=portal_id, url=url, status="dns_failure", error=str(exc))
    except httpx.TimeoutException as exc:
        return PortalHealth(id=portal_id, url=url, status="timeout", error=str(exc))


async def probe_inventory(inventory: list[dict] | None = None) -> HealthReport:
    if inventory is None:
        inventory = load_inventory()
    results = []
    for entry in inventory:
        result = await probe_portal(entry)
        results.append(result)
    operational = sum(1 for r in results if r.status == "operational")
    return HealthReport(total=len(results), operational=operational, results=results)
