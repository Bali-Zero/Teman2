"""MetaGraphSampler — Instagram Business insights via Meta Graph API.

GET /{ig-media-id}/insights?metric=reach,impressions,saves,shares,likes,comments,video_views
    -> { data: [ {name: 'reach', values: [{value: N}]} ... ] }

Not all metrics apply to every media type. Carousel posts return at least
reach/impressions/saves/shares/likes/comments. Missing metrics are tolerated
— we emit only what we got, and flag ``partial=True`` if we expected more.

Auth: reuses the IG long-lived token (IG_LONG_LIVED_TOKEN) from Sprint 7.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from backend.services.measurer.base import (
    METRIC_COMMENTS,
    METRIC_IMPRESSIONS,
    METRIC_LIKES,
    METRIC_REACH,
    METRIC_SAVES,
    METRIC_SHARES,
    METRIC_VIDEO_VIEWS,
    MetricDatum,
    MetricSampler,
    SamplerError,
    SamplerResult,
)
from backend.services.war_room.models import MetricSource, Platform, WarRoomPost

logger = logging.getLogger(__name__)


DEFAULT_GRAPH_BASE = "https://graph.facebook.com/v20.0"
DEFAULT_TIMEOUT = 20.0

# Metric names as returned by the Graph API — mapped to our canonical names.
_API_TO_CANONICAL: dict[str, str] = {
    "reach": METRIC_REACH,
    "impressions": METRIC_IMPRESSIONS,
    "saved": METRIC_SAVES,       # Graph API uses 'saved'
    "saves": METRIC_SAVES,
    "shares": METRIC_SHARES,
    "likes": METRIC_LIKES,
    "comments": METRIC_COMMENTS,
    "video_views": METRIC_VIDEO_VIEWS,
}

_DEFAULT_CAROUSEL_METRICS: tuple[str, ...] = (
    "reach",
    "impressions",
    "saved",
    "shares",
    "likes",
    "comments",
)


class MetaGraphSampler(MetricSampler):
    name = "meta_graph"
    platforms = (Platform.INSTAGRAM,)
    source = MetricSource.META_GRAPH

    def __init__(
        self,
        *,
        access_token: str | None = None,
        metrics: tuple[str, ...] | None = None,
        graph_base: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        timeout: float | None = None,
    ) -> None:
        self.access_token = (
            access_token
            or os.environ.get("IG_LONG_LIVED_TOKEN")
            or os.environ.get("INSTAGRAM_ACCESS_TOKEN")
            or ""
        )
        if not self.access_token:
            raise SamplerError(
                "MetaGraphSampler requires IG_LONG_LIVED_TOKEN "
                "(or INSTAGRAM_ACCESS_TOKEN)",
            )
        self.metrics = metrics or _DEFAULT_CAROUSEL_METRICS
        self.graph_base = (graph_base or DEFAULT_GRAPH_BASE).rstrip("/")
        self._client = http_client
        self.timeout = timeout or DEFAULT_TIMEOUT

    async def sample(self, post: WarRoomPost) -> SamplerResult:
        if post.platform != Platform.INSTAGRAM or not post.post_external_id:
            return SamplerResult(
                sampler_name=self.name,
                post_id=post.id,
                ok=False,
                error="post has no IG external id",
            )

        start = time.perf_counter()
        client = self._client
        close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=self.timeout)
            close_client = True

        try:
            params = {
                "metric": ",".join(self.metrics),
                "access_token": self.access_token,
            }
            resp = await client.get(
                f"{self.graph_base}/{post.post_external_id}/insights",
                params=params,
                timeout=self.timeout,
            )
            duration_ms = (time.perf_counter() - start) * 1000

            if resp.status_code != 200:
                return SamplerResult(
                    sampler_name=self.name,
                    post_id=post.id,
                    ok=False,
                    error=f"HTTP {resp.status_code}: {resp.text[:300]}",
                    duration_ms=duration_ms,
                )

            body = resp.json()
            data = _parse_insights(body)
            partial = len(data) < len(self.metrics)
            return SamplerResult(
                sampler_name=self.name,
                post_id=post.id,
                ok=True,
                data=data,
                duration_ms=duration_ms,
                partial=partial,
            )
        except Exception as exc:  # noqa: BLE001
            return SamplerResult(
                sampler_name=self.name,
                post_id=post.id,
                ok=False,
                error=f"{type(exc).__name__}: {exc}",
                duration_ms=(time.perf_counter() - start) * 1000,
            )
        finally:
            if close_client:
                await client.aclose()


def _parse_insights(body: dict[str, Any]) -> list[MetricDatum]:
    data = body.get("data")
    if not isinstance(data, list):
        return []

    out: list[MetricDatum] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        api_name = entry.get("name", "")
        canonical = _API_TO_CANONICAL.get(api_name)
        if canonical is None:
            continue
        values = entry.get("values") or []
        if not isinstance(values, list) or not values:
            continue
        first = values[0]
        raw_value = first.get("value") if isinstance(first, dict) else None
        if raw_value is None:
            continue
        try:
            numeric = float(raw_value)
        except (TypeError, ValueError):
            continue
        out.append(
            MetricDatum(
                metric_name=canonical,
                value=numeric,
                source=MetricSource.META_GRAPH,
                meta={"api_name": api_name},
            )
        )
    return out
