"""Brevo (ex-Sendinblue) statistics client — list + campaign aggregates.

Bali Zero's primary sender: zantara@balizero.com (alias damar@balizero.com).
API key lives in ~/.nuzantara-secrets.env as SENDGRID_API_KEY (legacy var
name, actually Brevo xkeysib-).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

API_BASE = "https://api.brevo.com/v3"


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
        client = self._client or httpx.AsyncClient(timeout=self.timeout)
        close = self._client is None
        try:
            resp = await client.get(url, headers=headers, params=params or {})
            if resp.status_code >= 400:
                raise BrevoError(f"{resp.status_code} {resp.text[:200]}")
            return resp.json()
        finally:
            if close:
                await client.aclose()
