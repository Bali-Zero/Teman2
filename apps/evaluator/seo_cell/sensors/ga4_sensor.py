"""GA4 Sensor — conversion funnel metrics per landing page (real fetch).

Uses the Analytics Data API v1beta via googleapiclient discovery (same
library as GSCSensor — no new dep). Read-only scope
(analytics.readonly). Property ID defaults to 505466833 (balizero.com)
per CLAUDE.md §7; overridable via GA4_PROPERTY_ID env or constructor.

Returns a SensorReading carrying:
  value.sessions_by_page   — {pagePath: session_count}
  value.conversions_by_page — {pagePath: conversion_count}
  value.page_count          — number of distinct landing pages
  value.sessions_total
  value.conversions_total

Dimensions chosen:
  `pagePath` (landing page without hostname) — matches the shape the
  thinker correlates with GSC landing_page in Sprint 3 when the
  Bayesian calibrator wires signals together.

Metrics chosen:
  `sessions` — top-of-funnel volume per page
  `conversions` — bottom-of-funnel (we use GA4 conversions, which
                  includes any event marked as conversion in the GA4
                  UI; currently `whatsapp_cta_click` + `form_submit`)

Failure policy mirrors GSCSensor: sensor never raises; yellow for
credential/config gaps, red for HttpError or unexpected exceptions.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import date, timedelta
from typing import Any

from cell_core.types import SensorReading

from apps.evaluator.seo_cell.config import GOOGLE_CREDENTIALS_PATH

logger = logging.getLogger("seo_cell.sensors.ga4")

_SCOPES = ("https://www.googleapis.com/auth/analytics.readonly",)
_DEFAULT_PROPERTY_ID = "505466833"  # CLAUDE.md §7 — BALI ZERO WEB stream
_ROW_LIMIT = 250  # GA4 default is 10_000; 250 is plenty for 28d of balizero.com
_TOP_N_KEEP = 50


class GA4Sensor:
    name = "ga4"

    def __init__(
        self,
        window_days: int = 28,
        property_id: str | None = None,
    ) -> None:
        self._window_days = window_days
        self._property_id = (
            property_id
            or os.environ.get("GA4_PROPERTY_ID")
            or _DEFAULT_PROPERTY_ID
        )

    async def read(self, **context) -> SensorReading:
        if not GOOGLE_CREDENTIALS_PATH.exists():
            return self._yellow(
                "credentials_missing",
                f"SA credentials not at {GOOGLE_CREDENTIALS_PATH}",
            )
        if not self._property_id:
            return self._yellow(
                "property_id_missing",
                "GA4 property ID not configured",
            )

        try:
            response = await asyncio.to_thread(self._fetch_report_blocking)
        except _GA4Error as e:
            return self._red(e.code, str(e))
        except Exception as e:  # noqa: BLE001 — sensor must not raise
            logger.exception("[ga4] unexpected failure")
            return self._red("unexpected", repr(e))

        rows = response.get("rows", []) or []
        sessions_by_page: dict[str, int] = {}
        conversions_by_page: dict[str, int] = {}

        # Rows shape: { "dimensionValues": [{"value": "/visa"}],
        #               "metricValues": [{"value": "42"}, {"value": "3"}] }
        # Metric order matches our request: sessions, conversions.
        for row in rows:
            dims = row.get("dimensionValues") or []
            metrics = row.get("metricValues") or []
            if not dims or len(metrics) < 2:
                continue
            page = dims[0].get("value", "") or "(unknown)"
            try:
                sessions = int(metrics[0].get("value", 0) or 0)
                conversions = int(metrics[1].get("value", 0) or 0)
            except (TypeError, ValueError):
                sessions = 0
                conversions = 0
            sessions_by_page[page] = sessions_by_page.get(page, 0) + sessions
            conversions_by_page[page] = (
                conversions_by_page.get(page, 0) + conversions
            )

        page_count = len(sessions_by_page)
        sessions_total = sum(sessions_by_page.values())
        conversions_total = sum(conversions_by_page.values())

        # Retain only top-N pages by sessions to keep the reading bounded
        top_pages = sorted(
            sessions_by_page.items(), key=lambda kv: kv[1], reverse=True
        )[:_TOP_N_KEEP]
        sessions_by_page_top = dict(top_pages)
        conversions_by_page_top = {
            p: conversions_by_page.get(p, 0) for p, _ in top_pages
        }

        # Same heuristic as GSC: green if signal is meaningful, else yellow
        status = "green" if page_count >= 5 else "yellow"

        return SensorReading(
            sensor_name=self.name,
            status=status,
            value={
                "page_count": page_count,
                "sessions_total": sessions_total,
                "conversions_total": conversions_total,
                "sessions_by_page": sessions_by_page_top,
                "conversions_by_page": conversions_by_page_top,
            },
            metadata={
                "window_days": self._window_days,
                "property_id": self._property_id,
                "row_limit_requested": _ROW_LIMIT,
            },
        )

    # ── internal ──────────────────────────────────────────────────────────

    def _fetch_report_blocking(self) -> dict[str, Any]:
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            from googleapiclient.errors import HttpError
        except ImportError as e:
            raise _GA4Error("import_error", f"missing dep: {e}") from e

        creds = service_account.Credentials.from_service_account_file(
            str(GOOGLE_CREDENTIALS_PATH), scopes=list(_SCOPES)
        )
        service = build(
            "analyticsdata", "v1beta", credentials=creds, cache_discovery=False
        )

        end = date.today()
        start = end - timedelta(days=self._window_days)
        body = {
            "dateRanges": [{"startDate": start.isoformat(), "endDate": end.isoformat()}],
            "metrics": [{"name": "sessions"}, {"name": "conversions"}],
            "dimensions": [{"name": "pagePath"}],
            "limit": _ROW_LIMIT,
        }
        try:
            response = (
                service.properties()
                .runReport(
                    property=f"properties/{self._property_id}",
                    body=body,
                )
                .execute()
            )
        except HttpError as e:
            status_code = getattr(getattr(e, "resp", None), "status", "?")
            raise _GA4Error(
                "http_error", f"GA4 API {status_code}: {e}"
            ) from e
        return response

    def _yellow(self, code: str, msg: str) -> SensorReading:
        return SensorReading(
            sensor_name=self.name,
            status="yellow",
            value={
                "page_count": 0,
                "sessions_total": 0,
                "conversions_total": 0,
                "sessions_by_page": {},
                "conversions_by_page": {},
            },
            metadata={
                "window_days": self._window_days,
                "property_id": self._property_id,
                "error_code": code,
                "error": msg,
            },
        )

    def _red(self, code: str, msg: str) -> SensorReading:
        logger.warning("[ga4] red: %s — %s", code, msg)
        return SensorReading(
            sensor_name=self.name,
            status="red",
            value={
                "page_count": 0,
                "sessions_total": 0,
                "conversions_total": 0,
                "sessions_by_page": {},
                "conversions_by_page": {},
            },
            metadata={
                "window_days": self._window_days,
                "property_id": self._property_id,
                "error_code": code,
                "error": msg,
            },
        )


class _GA4Error(RuntimeError):
    """Internal signal from the blocking fetcher to the async wrapper."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
