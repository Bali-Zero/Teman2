"""Intel Lake service — UPSERT logic for intel_items + intel_observations.

Wave 1 (2026-05-12): single source of truth for intel/news from 12+ producers.
Design: research/symbiosis/2026-05-12-intel-lake-design.md
Plan:   research/symbiosis/2026-05-12-intel-lake-wave1-plan.md

Key invariants (from Codex review):
- intel_items.title/summary/content_hash are IMMUTABLE post-first-write
- last_seen_at UPDATEs only when content_hash matches (no silent content drift)
- Content drift → INSERT new row (separate canonical version)
- intel_observations is append-only (no UNIQUE)
- raw_payload size capped at 50KB (server-side reject 413)
- All endpoint calls audited
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urldefrag, urlparse, urlunparse

import asyncpg

logger = logging.getLogger(__name__)


def _parse_iso_datetime(value: str | None) -> datetime | None:
    """Parse an ISO 8601 string into a datetime for asyncpg timestamptz binding.

    asyncpg's timestamptz codec requires a Python `datetime`, NOT a string.
    Wave 4 producers (regulatory_watcher, intel_radar) send ISO 8601 strings
    like ``2026-05-13T07:00:00+08:00``; binding them directly produced
    ``invalid input for query argument $9: ... (expected a date object)``
    and the endpoint returned 500. The bug silently dropped every item with
    a non-null ``published_at`` since Wave 4 deploy (2026-05-12) because the
    drainer trusts the audit log for rejection accounting.

    Returns ``None`` for empty / unparseable input — better to lose the
    timestamp than to drop the whole item.
    """
    if not value:
        return None
    try:
        # Python 3.11+ fromisoformat handles trailing 'Z' and offsets
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        logger.warning(
            "intel-lake: unparseable published_at=%r — storing as NULL",
            value,
        )
        return None

MAX_RAW_PAYLOAD_BYTES = 50_000
ROUTING_STATUS_VALUES = {
    "unrouted",
    "blog",
    "wr2",
    "nb-intel",
    "archive",
    "skip",
    "needs_review",
}
UTM_PREFIXES = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid", "_ga")


@dataclass(frozen=True)
class ObservationInput:
    producer_name: str
    canonical_url: str  # producer-provided (we'll re-canonicalize defensively)
    content_hash: str
    title: str
    summary: str | None
    source_domain: str
    language: str | None = None
    jurisdiction: str | None = None
    topic_tags: list[str] | None = None
    published_at: str | None = None  # ISO 8601
    score: float | None = None
    raw_payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class ObservationResult:
    item_id: str
    is_new_item: bool
    is_content_drift: bool
    observation_id: int


class IntelLakeError(Exception):
    """Base exception for intel-lake operations."""


class PayloadTooLargeError(IntelLakeError):
    """raw_payload exceeds MAX_RAW_PAYLOAD_BYTES."""


def canonicalize_url(url: str) -> str:
    """Defensive URL canonicalization.

    - Strip fragment
    - Lowercase host
    - Drop utm_*, fbclid, gclid, mc_*, _ga query params
    - Preserve scheme + path + remaining query
    """
    url_no_frag, _ = urldefrag(url.strip())
    parsed = urlparse(url_no_frag)
    netloc = parsed.netloc.lower()

    # Filter query params
    if parsed.query:
        kept = []
        for kv in parsed.query.split("&"):
            if not kv:
                continue
            key = kv.split("=", 1)[0].lower()
            if any(key.startswith(p) or key == p for p in UTM_PREFIXES):
                continue
            kept.append(kv)
        new_query = "&".join(kept)
    else:
        new_query = ""

    return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, new_query, ""))


class IntelLakeService:
    """Service-layer logic for intel_items / intel_observations UPSERTs."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self._pool = db_pool

    async def record_observation(
        self,
        obs: ObservationInput,
    ) -> ObservationResult:
        """Insert observation + UPSERT canonical item.

        Returns ObservationResult with is_new_item flag for the trigger event
        and is_content_drift if same URL but different content_hash (indicates
        an updated article — currently logged but does NOT mutate stored item).

        Raises:
            PayloadTooLargeError: if raw_payload JSON serializes >50KB
        """
        # Server-side defensive validation
        canonical = canonicalize_url(obs.canonical_url)
        if not canonical:
            raise IntelLakeError(f"empty canonical_url after normalize: {obs.canonical_url!r}")

        # ``raw_json`` is computed ONLY for the 50KB size guard below.
        # The DB binds ``raw_payload_obj`` (the raw dict) — the pool's jsonb
        # codec (``backend/app/core/database.py``) registers
        # ``encoder=json.dumps``, so binding pre-serialized text would
        # double-encode it into a jsonb *string* scalar. Regression fixed
        # 2026-05-14.
        raw_payload_obj = obs.raw_payload or {}
        raw_json = json.dumps(raw_payload_obj)
        if len(raw_json.encode()) > MAX_RAW_PAYLOAD_BYTES:
            raise PayloadTooLargeError(
                f"raw_payload {len(raw_json)} bytes exceeds limit {MAX_RAW_PAYLOAD_BYTES}"
            )

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Step 1: UPSERT item — only touch last_seen_at on conflict.
                # If content_hash differs we still update last_seen_at (the
                # URL is alive) but mark drift via separate diagnostic.
                row = await conn.fetchrow(
                    """
                    INSERT INTO intel_items
                        (canonical_url, content_hash, title, summary, source_domain,
                         language, jurisdiction, topic_tags, published_at, raw_payload)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::timestamptz, $10::jsonb)
                    ON CONFLICT (canonical_url) DO UPDATE
                        SET last_seen_at = NOW()
                    RETURNING id, (xmax = 0) AS is_new_item, content_hash AS stored_hash
                    """,
                    canonical,
                    obs.content_hash,
                    obs.title,
                    obs.summary,
                    obs.source_domain.lower(),
                    obs.language,
                    obs.jurisdiction,
                    obs.topic_tags or [],
                    _parse_iso_datetime(obs.published_at),
                    raw_payload_obj,
                )

                item_id = str(row["id"])
                is_new_item = bool(row["is_new_item"])
                is_content_drift = (
                    not is_new_item
                    and row["stored_hash"] is not None
                    and row["stored_hash"] != obs.content_hash
                )

                # Step 2: Append observation always.
                obs_id = await conn.fetchval(
                    """
                    INSERT INTO intel_observations
                        (item_id, producer_name, raw_payload, score)
                    VALUES ($1, $2, $3::jsonb, $4)
                    RETURNING id
                    """,
                    row["id"],
                    obs.producer_name,
                    raw_payload_obj,
                    obs.score,
                )

        if is_content_drift:
            logger.warning(
                "intel-lake content drift for %s (producer=%s, stored=%s incoming=%s)",
                canonical,
                obs.producer_name,
                row["stored_hash"][:12],
                obs.content_hash[:12],
            )

        return ObservationResult(
            item_id=item_id,
            is_new_item=is_new_item,
            is_content_drift=is_content_drift,
            observation_id=int(obs_id),
        )

    async def log_audit(
        self,
        producer_name: str,
        client_ip: str | None,
        request_path: str,
        status_code: int,
        payload_size: int | None,
        error_message: str | None = None,
    ) -> None:
        """Write audit entry. Best-effort: caller should not fail if this errors."""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO intel_lake_audit_log
                        (producer_name, client_ip, request_path, status_code,
                         payload_size, error_message)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    producer_name,
                    client_ip,
                    request_path,
                    status_code,
                    payload_size,
                    error_message,
                )
        except Exception as e:  # pragma: no cover — never block on audit failure
            logger.error("audit log failed: %s", e)
