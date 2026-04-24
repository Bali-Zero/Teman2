"""Instagram Graph API v21 sensor — own account metrics for Bali Zero.

Pulls:
- Account summary (followers_count, media_count)
- Per-post insights (likes, comments, saved, reach, video_views). `impressions`
  was deprecated by Meta in Graph API v22+ for media insights; kept as
  dataclass field with default=0 for forward compatibility if Meta reinstates.

Scope: ONLY @balizero0 own account. Competitor posts are scraped manually
(see docs/runbooks/competitor-scrape-manual.md) because Graph API requires
Business Manager linkage to each target.

Token renewal: Meta long-lived tokens expire ~60 days. Watchdog TBD Task 30.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


class IGGraphError(RuntimeError):
    """Raised on Graph API error payloads."""


@dataclass(frozen=True)
class IGPostMetrics:
    post_id: str
    caption: str
    format: str  # IMAGE, VIDEO, CAROUSEL_ALBUM, REEL
    timestamp: str
    permalink: str
    likes: int
    comments: int
    saves: int
    reach: int
    impressions: int = 0
    video_views: int = 0


class IGGraphSensor:
    """Thin wrapper around Graph API GET calls for @balizero0 metrics."""

    def __init__(
        self,
        token: str,
        ig_user_id: str,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not token:
            raise ValueError("IGGraphSensor requires a Graph API token")
        if not ig_user_id:
            raise ValueError("IGGraphSensor requires the Instagram Business user id")
        self.token = token
        self.ig_user_id = ig_user_id
        self._client = http_client

    async def read_account_summary(self) -> dict[str, Any]:
        fields = "followers_count,media_count,biography,username"
        data = await self._get(f"/{self.ig_user_id}", fields=fields)
        if "error" in data:
            raise IGGraphError(data["error"].get("message", "unknown Graph error"))
        return data

    async def read_posts(self, limit: int = 25) -> list[IGPostMetrics]:
        fields = "id,caption,media_type,timestamp,permalink"
        page = await self._get(
            f"/{self.ig_user_id}/media",
            fields=fields,
            limit=limit,
        )
        if "error" in page:
            raise IGGraphError(page["error"].get("message", "media fetch failed"))
        out: list[IGPostMetrics] = []
        for media in page.get("data", []):
            metrics = await self._fetch_insights(media["id"], media.get("media_type", ""))
            out.append(
                IGPostMetrics(
                    post_id=media["id"],
                    caption=media.get("caption", ""),
                    format=media.get("media_type", ""),
                    timestamp=media.get("timestamp", ""),
                    permalink=media.get("permalink", ""),
                    **metrics,
                )
            )
        return out

    async def _fetch_insights(self, media_id: str, media_type: str) -> dict[str, int]:
        # Note: `impressions` was deprecated in Graph API v22+ for media insights.
        # Using only supported metrics to avoid OAuthException #100.
        metric_list = "likes,comments,saved,reach"
        if media_type in ("VIDEO", "REEL"):
            metric_list += ",video_views"
        response = await self._get(f"/{media_id}/insights", metric=metric_list)
        if "error" in response:
            logger.warning("insights error for %s: %s", media_id, response["error"])
            return {"likes": 0, "comments": 0, "saves": 0, "reach": 0}
        parsed: dict[str, int] = {
            "likes": 0, "comments": 0, "saves": 0,
            "reach": 0, "impressions": 0, "video_views": 0,
        }
        for entry in response.get("data", []):
            name = entry.get("name")
            if name == "saved":
                name = "saves"
            values = entry.get("values") or [{}]
            parsed[name] = int(values[0].get("value", 0))
        return parsed

    async def _get(self, path: str, **params: Any) -> dict[str, Any]:
        params["access_token"] = self.token
        url = f"{GRAPH_API_BASE}{path}"
        client = self._client or httpx.AsyncClient(timeout=20.0)
        close = self._client is None
        try:
            resp = await client.get(url, params=params)
            return resp.json()
        finally:
            if close:
                await client.aclose()
