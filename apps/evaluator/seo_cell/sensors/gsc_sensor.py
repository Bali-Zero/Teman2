"""GSC Sensor — Google Search Console query performance (real fetch).

Uses the Search Console service-account credentials at
`.secrets/google-credentials.json` (already siteOwner of balizero.com,
verified by existing seo_guardian_core.py). Read-only scope only:
the cell never mutates GSC.

Returns a SensorReading carrying:
  value.query_count          — distinct query strings in the window
  value.clicks_total         — sum of clicks across all rows
  value.impressions_total    — sum of impressions
  value.top_queries          — top N rows sorted by impressions
                               (each row: query, clicks, impressions,
                                ctr, position)

`query_count` is the field the pre_natal gate reads to decide whether
the cell graduates (threshold: 80 distinct queries in 28d).

Failure policy:
  - missing credentials file → yellow with metadata.error
  - HttpError or other exception → red with metadata.error
  Sensor never raises; the pulse loop must never crash on I/O.

Dependencies: google-auth, google-api-python-client. These are already
installed (used by seo_guardian_core.py and gsc_resubmit_sitemap.py).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Any

from cell_core.types import SensorReading

from apps.evaluator.seo_cell.config import GOOGLE_CREDENTIALS_PATH, SITE_URL

logger = logging.getLogger("seo_cell.sensors.gsc")

_SCOPES = ("https://www.googleapis.com/auth/webmasters.readonly",)
_ROW_LIMIT = 1000  # GSC hard cap per request is 25_000; 1_000 is plenty for us
_TOP_N_KEEP = 50   # keep top-50 rows in the reading; thinker doesn't need more


class GSCSensor:
    name = "gsc"

    def __init__(self, window_days: int = 28, site_url: str = SITE_URL) -> None:
        self._window_days = window_days
        self._site_url = site_url

    async def read(self, **context) -> SensorReading:
        if not GOOGLE_CREDENTIALS_PATH.exists():
            return self._yellow(
                "credentials_missing",
                f"SA credentials not at {GOOGLE_CREDENTIALS_PATH}",
            )

        try:
            rows = await asyncio.to_thread(self._fetch_rows_blocking)
        except _GSCError as e:
            return self._red(e.code, str(e))
        except Exception as e:  # noqa: BLE001 — sensor must not raise
            logger.exception("[gsc] unexpected failure")
            return self._red("unexpected", repr(e))

        query_count = len(rows)
        clicks_total = sum(int(r.get("clicks", 0)) for r in rows)
        impressions_total = sum(int(r.get("impressions", 0)) for r in rows)
        top_rows = sorted(
            rows,
            key=lambda r: r.get("impressions", 0),
            reverse=True,
        )[:_TOP_N_KEEP]

        # Normalize row shape — GSC returns `keys: [query]` not `query: str`
        normalized_top = [
            {
                "query": (r.get("keys") or [""])[0],
                "clicks": int(r.get("clicks", 0)),
                "impressions": int(r.get("impressions", 0)),
                "ctr": float(r.get("ctr", 0.0)),
                "position": float(r.get("position", 0.0)),
            }
            for r in top_rows
        ]

        # Status heuristic: green if we have meaningful signal, yellow if the
        # account is new/empty, red is reserved for hard failures above.
        status = "green" if query_count >= 10 else "yellow"
        return SensorReading(
            sensor_name=self.name,
            status=status,
            value={
                "query_count": query_count,
                "clicks_total": clicks_total,
                "impressions_total": impressions_total,
                "top_queries": normalized_top,
            },
            metadata={
                "window_days": self._window_days,
                "site_url": self._site_url,
                "row_limit_requested": _ROW_LIMIT,
            },
        )

    # ── internal ──────────────────────────────────────────────────────────

    def _fetch_rows_blocking(self) -> list[dict[str, Any]]:
        """Runs inside a worker thread via asyncio.to_thread.

        googleapiclient is sync-only, so wrap the full auth+query in a
        thread to keep the pulse loop awaitable.
        """
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            from googleapiclient.errors import HttpError
        except ImportError as e:
            raise _GSCError("import_error", f"missing dep: {e}") from e

        creds = service_account.Credentials.from_service_account_file(
            str(GOOGLE_CREDENTIALS_PATH), scopes=list(_SCOPES)
        )
        service = build("webmasters", "v3", credentials=creds, cache_discovery=False)

        end = date.today()
        start = end - timedelta(days=self._window_days)
        body = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": ["query"],
            "rowLimit": _ROW_LIMIT,
        }
        try:
            response = (
                service.searchanalytics()
                .query(siteUrl=self._site_url, body=body)
                .execute()
            )
        except HttpError as e:
            raise _GSCError("http_error", f"GSC API {e.resp.status}: {e}") from e
        return list(response.get("rows", []))

    def _yellow(self, code: str, msg: str) -> SensorReading:
        return SensorReading(
            sensor_name=self.name,
            status="yellow",
            value={
                "query_count": 0,
                "clicks_total": 0,
                "impressions_total": 0,
                "top_queries": [],
            },
            metadata={
                "window_days": self._window_days,
                "site_url": self._site_url,
                "error_code": code,
                "error": msg,
            },
        )

    def _red(self, code: str, msg: str) -> SensorReading:
        logger.warning("[gsc] red: %s — %s", code, msg)
        return SensorReading(
            sensor_name=self.name,
            status="red",
            value={
                "query_count": 0,
                "clicks_total": 0,
                "impressions_total": 0,
                "top_queries": [],
            },
            metadata={
                "window_days": self._window_days,
                "site_url": self._site_url,
                "error_code": code,
                "error": msg,
            },
        )


class _GSCError(RuntimeError):
    """Internal signal from the blocking fetcher to the async wrapper."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
