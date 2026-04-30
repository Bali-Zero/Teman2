"""Lead Attribution Sensor — counts website-organic leads from CRM.

The pre_natal unlock gate (`phase.is_pre_natal`) ANDs three conditions;
the leads condition was previously hardcoded to 0 in the thinker (A3
anomaly), permanently locking the gate. This sensor closes the gap by
reading the `clients` table populated by migration 118
(`clients.referrer_url` / `landing_page` / `first_touch_at`).

A lead counts as "website-organic" when ALL of:

  - referrer_url IS NOT NULL — first-touch came through HTTP referer
  - referrer_url DOES NOT match a paid/social/internal pattern
  - first_touch_at is within the lookback window (default 28d to mirror
    the GSC query window used elsewhere in the v2.1 design)

Returns SensorReading.value:
  lead_count        — int, used by the thinker for the unlock gate
  by_landing_page   — {landing_page: count} for top N
  recent_leads      — [{first_touch_at, referrer_domain, landing_page}]

Failure policy mirrors the other PG-backed sensors (war_room_event,
gsc): never raises.
  - no DATABASE_URL                 → yellow, error_code=db_url_missing
  - asyncpg import failure          → red,    error_code=import_error
  - connection/query error          → red,    error_code=db_error
  - any other exception             → red,    error_code=unexpected
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from cell_core.types import SensorReading

logger = logging.getLogger("seo_cell.sensors.lead_attribution")

_DEFAULT_WINDOW_DAYS = 28
_TOP_N_KEEP = 50

# Domains we treat as paid/social/internal — NOT organic SEO traffic.
# Conservative: anything we can't classify positively as organic is
# excluded from the count, so the gate stays defensible.
_NON_ORGANIC_DOMAINS = frozenset({
    # Paid / ads
    "googleads.g.doubleclick.net",
    "ads.google.com",
    # Social — these are organic *social* traffic, not organic *search*.
    # The pre_natal gate is for SEO graduation specifically (decision
    # memo v2.1), so social leads don't qualify even when unpaid.
    "facebook.com", "m.facebook.com", "l.facebook.com",
    "instagram.com", "l.instagram.com",
    "tiktok.com",
    "linkedin.com", "lnkd.in",
    "twitter.com", "x.com", "t.co",
    "youtube.com", "youtu.be",
    "wa.me", "api.whatsapp.com",
    "t.me",
    # Internal — leads from our own subdomains aren't first-touch SEO.
    "balizero.com", "kita.balizero.com", "my.balizero.com",
    "prime.balizero.com", "knowledge.balizero.com", "zantara.balizero.com",
})

# Search engines whose referer DOES count as organic search.
_ORGANIC_SEARCH_DOMAINS = frozenset({
    "google.com", "www.google.com", "google.co.id", "google.com.au",
    "bing.com", "www.bing.com",
    "duckduckgo.com",
    "yahoo.com", "search.yahoo.com",
    "ecosia.org",
    "yandex.com", "yandex.ru",
    "baidu.com",
})


class LeadAttributionSensor:
    name = "lead_attribution"

    def __init__(
        self,
        window_days: int = _DEFAULT_WINDOW_DAYS,
        db_url: str | None = None,
    ) -> None:
        self._window_days = window_days
        self._db_url_override = db_url

    def _resolve_db_url(self) -> str | None:
        return self._db_url_override or os.environ.get("DATABASE_URL")

    async def read(self, **context) -> SensorReading:
        db_url = self._resolve_db_url()
        if not db_url:
            return self._yellow(
                "db_url_missing",
                "DATABASE_URL not set (and no override)",
            )

        try:
            rows = await self._fetch_leads(db_url)
        except _LeadAttributionError as e:
            return self._red(e.code, str(e))
        except Exception as e:  # noqa: BLE001 — sensor must not raise
            logger.exception("[lead_attribution] unexpected failure")
            return self._red("unexpected", repr(e))

        organic_rows = [r for r in rows if _is_organic_referrer(r.get("referrer_url"))]

        by_landing_page: dict[str, int] = {}
        recent: list[dict[str, Any]] = []
        for r in organic_rows:
            lp = r.get("landing_page") or "/"
            by_landing_page[lp] = by_landing_page.get(lp, 0) + 1
            recent.append({
                "first_touch_at": _isoformat_or_none(r.get("first_touch_at")),
                "referrer_domain": _domain_of(r.get("referrer_url")),
                "landing_page": lp,
            })

        recent.sort(key=lambda p: p.get("first_touch_at") or "", reverse=True)
        recent = recent[:_TOP_N_KEEP]

        lead_count = len(organic_rows)
        # green when at least one organic lead — same logic as
        # war_room_event_sensor: yellow when window is empty (no signal),
        # green when there's something to look at. The unlock gate is
        # evaluated by the thinker, not by colour here.
        status = "green" if lead_count > 0 else "yellow"

        return SensorReading(
            sensor_name=self.name,
            status=status,
            value={
                "lead_count": lead_count,
                "by_landing_page": by_landing_page,
                "recent_leads": recent,
            },
            metadata={
                "window_days": self._window_days,
                "table": "clients",
                "scanned_rows": len(rows),
            },
        )

    async def _fetch_leads(self, db_url: str) -> list[dict[str, Any]]:
        try:
            import asyncpg
        except ImportError as e:
            raise _LeadAttributionError("import_error", f"missing dep: {e}") from e

        cutoff = datetime.now(timezone.utc) - timedelta(days=self._window_days)
        try:
            conn = await asyncpg.connect(db_url, timeout=10)
        except Exception as e:
            raise _LeadAttributionError("db_error", f"connect failed: {e!r}") from e
        try:
            rows = await conn.fetch(
                """
                SELECT referrer_url, landing_page, first_touch_at
                FROM clients
                WHERE referrer_url IS NOT NULL
                  AND first_touch_at IS NOT NULL
                  AND first_touch_at >= $1
                ORDER BY first_touch_at DESC
                LIMIT 1000
                """,
                cutoff,
            )
        except Exception as e:
            raise _LeadAttributionError("db_error", f"query failed: {e!r}") from e
        finally:
            await conn.close()
        return [dict(r) for r in rows]

    def _yellow(self, code: str, msg: str) -> SensorReading:
        return SensorReading(
            sensor_name=self.name,
            status="yellow",
            value={
                "lead_count": 0,
                "by_landing_page": {},
                "recent_leads": [],
            },
            metadata={
                "window_days": self._window_days,
                "error_code": code,
                "error": msg,
            },
        )

    def _red(self, code: str, msg: str) -> SensorReading:
        logger.warning("[lead_attribution] red: %s — %s", code, msg)
        return SensorReading(
            sensor_name=self.name,
            status="red",
            value={
                "lead_count": 0,
                "by_landing_page": {},
                "recent_leads": [],
            },
            metadata={
                "window_days": self._window_days,
                "error_code": code,
                "error": msg,
            },
        )


class _LeadAttributionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _domain_of(url: str | None) -> str | None:
    if not url:
        return None
    try:
        host = urlparse(url).netloc.lower()
    except Exception:  # noqa: BLE001
        return None
    return host or None


def _is_organic_referrer(url: str | None) -> bool:
    """True iff referer is a known organic search domain.

    Conservative: an unknown referer (random other site, missing, weird
    scheme) does NOT count. The pre_natal unlock gate prefers a missed
    signal to a fake non-zero — see thinker.py:118-128.
    """
    domain = _domain_of(url)
    if domain is None:
        return False
    if domain in _NON_ORGANIC_DOMAINS:
        return False
    return domain in _ORGANIC_SEARCH_DOMAINS


def _isoformat_or_none(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)
