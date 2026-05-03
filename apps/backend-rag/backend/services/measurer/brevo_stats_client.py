"""Brevo (ex-Sendinblue) statistics client — list + campaign aggregates.

Bali Zero's primary sender: zantara@balizero.com (alias damar@balizero.com).
API key lives in ~/.nuzantara-secrets.env as SENDGRID_API_KEY (legacy var
name, actually Brevo xkeysib-) or BREVO_API_KEY on Pro local.

Known state (2026-04-22): Brevo account has 1 placeholder list with 0
subscribers and 0 sent campaigns. Bali Zero is NOT currently running
newsletters via Brevo. Day-1 baseline will show brevo.total_subscribers=0
and campaigns_analyzed=0 — this is honest reporting, not a bug. The SOTA
playbook (Task 20) is expected to recommend activating newsletter as an
action item.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

API_BASE = "https://api.brevo.com/v3"


# Golden Rule #10: module-level lazy singleton AsyncClient.
_module_client: httpx.AsyncClient | None = None


def _get_module_client(timeout: float) -> httpx.AsyncClient:
    global _module_client  # noqa: PLW0603 — singleton by design
    if _module_client is None or _module_client.is_closed:
        _module_client = httpx.AsyncClient(timeout=timeout)
    return _module_client


async def close_brevo_stats_client() -> None:
    """Release the module-level AsyncClient (lifespan shutdown hook)."""
    global _module_client  # noqa: PLW0603
    if _module_client is not None and not _module_client.is_closed:
        await _module_client.aclose()
    _module_client = None


class BrevoError(RuntimeError):
    """Raised on Brevo API failures."""


class BrevoStatsClient:
    def __init__(
        self,
        api_key: str,
        *,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = 15.0,
    ) -> None:
        if not api_key or not api_key.startswith("xkeysib-"):
            raise ValueError("BrevoStatsClient requires a Brevo key starting with xkeysib-")
        self.api_key = api_key
        self._client = http_client
        self.timeout = timeout

    async def fetch_list_totals(self) -> dict[str, Any]:
        payload = await self._get("/contacts/lists", params={"limit": 50, "offset": 0})
        lists = payload.get("lists", [])
        total = sum(item.get("totalSubscribers", 0) for item in lists)
        blacklisted = sum(item.get("totalBlacklisted", 0) for item in lists)
        return {
            "total_subscribers": total,
            "total_blacklisted": blacklisted,
            "list_count": len(lists),
        }

    async def fetch_campaign_aggregates(self, limit: int = 30) -> dict[str, Any]:
        payload = await self._get(
            "/emailCampaigns",
            params={"limit": limit, "status": "sent"},
        )
        campaigns = payload.get("campaigns", [])
        opens = clicks = sent = 0
        for c in campaigns:
            gs = c.get("statistics", {}).get("globalStats", {})
            sent += gs.get("sent", 0)
            opens += gs.get("uniqueViews", 0)
            clicks += gs.get("uniqueClicks", 0)
        if sent == 0:
            return {"campaigns_analyzed": len(campaigns), "avg_open_rate": 0.0, "avg_click_rate": 0.0}
        return {
            "campaigns_analyzed": len(campaigns),
            "avg_open_rate": opens / sent,
            "avg_click_rate": clicks / sent,
        }

    async def _get(self, path: str, *, params: dict | None = None) -> dict[str, Any]:
        url = f"{API_BASE}{path}"
        headers = {"api-key": self.api_key, "Accept": "application/json"}
        client = self._client or _get_module_client(self.timeout)
        close = self._client is None
        try:
            resp = await client.get(url, headers=headers, params=params or {})
            if resp.status_code >= 400:
                raise BrevoError(f"{resp.status_code} {resp.text[:200]}")
            return resp.json()
        finally:
            if close:
                await client.aclose()
