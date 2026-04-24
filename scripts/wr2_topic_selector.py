#!/usr/bin/env python3
"""WR2 Topic Selector — pick the best article from staging, create a draft.

Daily cron entry (05:00 WITA): fetches pending items from the News Room
staging area (on Fly), scores them with a deterministic heuristic
(freshness + Bali-Zero keyword relevance + tier), and if the top score
beats a threshold writes a new row into war_room_drafts (status=briefed).

Env:
    DATABASE_URL            — Fly postgres via localhost:15432 proxy
    NUZANTARA_BACKEND_URL   — default https://nuzantara-rag.fly.dev
    NUZANTARA_API_KEY       — default REDACTED-ROTATED-KEY
    TELEGRAM_BOT_TOKEN      — optional (best-effort notification)
    TELEGRAM_OWNER_CHAT_ID  — default 1125336968
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent

import asyncpg  # noqa: E402
import httpx  # noqa: E402

logger = logging.getLogger("wr2.topic_selector")

BZ_KEYWORDS: dict[str, int] = {
    # visa / immigration (highest priority)
    "investor kitas": 30,
    "golden visa": 25,
    "kitas": 25,
    "kitap": 25,
    "visa": 20,
    "imigrasi": 20,
    "immigration": 20,
    "overstay": 20,
    "nomad": 18,
    # tax / company
    "kbli": 25,
    "npwp": 20,
    "pma": 20,
    "nik": 15,
    "pajak": 15,
    "tax": 12,
    "bpjs": 10,
    # property
    "property": 15,
    "investor": 12,
    "real estate": 12,
    "villa": 10,
    # generic (low weight)
    "bali": 8,
    "indonesia": 5,
    "jakarta": 3,
}

FRESHNESS_MAX_POINTS: int = 30
FRESHNESS_HALF_LIFE_HOURS: float = 72.0
TIER_WEIGHT: dict[str, int] = {"T1": 30, "T2": 15, "T3": 5}
SCORE_THRESHOLD: float = 40.0
STAGING_FETCH_TIMEOUT: float = 30.0


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def score_item(item: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    """Return (total_score, breakdown) for a staging item."""
    now = datetime.now(timezone.utc)
    detail: dict[str, Any] = {"rules": {}}

    detected = _parse_dt(item.get("detected_at")) or _parse_dt(item.get("published_at"))
    age_h = max(0.0, (now - detected).total_seconds() / 3600.0) if detected else 24.0
    fresh_score = max(0.0, 1 - age_h / FRESHNESS_HALF_LIFE_HOURS) * FRESHNESS_MAX_POINTS
    detail["rules"]["freshness_points"] = round(fresh_score, 1)
    detail["rules"]["age_hours"] = round(age_h, 1)

    title = str(item.get("title") or "").lower()
    content = str(item.get("content") or item.get("summary") or "")[:1500].lower()
    text = f"{title} {content}"

    kw_hits: list[str] = []
    kw_score = 0
    for kw, w in BZ_KEYWORDS.items():
        if kw in text:
            kw_hits.append(kw)
            kw_score += w
    detail["rules"]["keywords_matched"] = kw_hits
    detail["rules"]["keywords_points"] = kw_score

    tier = str(item.get("tier") or item.get("qwen_tier") or "T3").upper()
    tier_score = TIER_WEIGHT.get(tier, 5)
    detail["rules"]["tier"] = tier
    detail["rules"]["tier_points"] = tier_score

    total = fresh_score + kw_score + tier_score
    detail["score"] = round(total, 1)
    return total, detail


async def fetch_staging(backend_url: str, api_key: str) -> list[dict[str, Any]]:
    url = f"{backend_url.rstrip('/')}/api/intel/staging/pending?type=all"
    async with httpx.AsyncClient(timeout=STAGING_FETCH_TIMEOUT) as client:
        resp = await client.get(url, headers={"X-API-Key": api_key})
    resp.raise_for_status()
    data = resp.json()
    items = data.get("items", [])
    return [i for i in items if (i.get("status") or "pending") == "pending"]


def _configure_logging() -> None:
    log_dir = Path.home() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "wr2_topic_selector.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),
        ],
    )


def _send_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    if not token:
        return
    try:
        import urllib.parse
        import urllib.request

        payload = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
        urllib.request.urlopen(  # noqa: S310
            f"https://api.telegram.org/bot{token}/sendMessage",
            payload,
            timeout=10,
        )
    except Exception as e:
        logger.warning("Telegram send failed: %s", e)


async def _already_seen(conn: asyncpg.Connection, staging_id: str) -> bool:
    row = await conn.fetchval(
        "SELECT 1 FROM war_room_drafts WHERE brief_json->>'staging_id' = $1 LIMIT 1",
        staging_id,
    )
    return bool(row)


async def run(*, dry_run: bool = False, force: bool = False, rank: int = 0) -> int:
    """rank=0 picks top-1, rank=1 picks #2 (useful for testing with a fresh topic)."""
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL not set")
        return 2

    backend_url = os.environ.get("NUZANTARA_BACKEND_URL", "https://nuzantara-rag.fly.dev")
    api_key = os.environ.get("NUZANTARA_API_KEY", "REDACTED-ROTATED-KEY")

    logger.info("Fetching staging from %s", backend_url)
    try:
        items = await fetch_staging(backend_url, api_key)
    except Exception as e:
        logger.exception("Staging fetch failed: %s", e)
        _send_telegram(f"WR2 topic_selector: staging fetch failed\n{e}")
        return 2

    logger.info("Fetched %d pending staging items", len(items))
    if not items:
        logger.info("No pending items — nothing to do today")
        return 1

    scored = [(item, *score_item(item)) for item in items]
    scored.sort(key=lambda t: -t[1])

    for rank, (item, score, detail) in enumerate(scored[:5], start=1):
        logger.info(
            "#%d score=%.1f [%s] kw=%d title=%r",
            rank,
            score,
            detail["rules"]["tier"],
            detail["rules"]["keywords_points"],
            (item.get("title") or "")[:80],
        )

    if rank >= len(scored):
        logger.error("rank=%d out of range (only %d items)", rank, len(scored))
        return 1
    top_item, top_score, top_detail = scored[rank]
    if rank > 0:
        logger.info("Using rank=%d (not top) for testing — picked #%d", rank, rank + 1)
    threshold = 0.0 if force else SCORE_THRESHOLD
    if top_score < threshold:
        logger.info("Top score %.1f below threshold %.1f — skip", top_score, threshold)
        return 1

    staging_id = top_item.get("id") or ""
    title = top_item.get("title") or "(untitled)"

    if dry_run:
        logger.info("[DRY-RUN] Would create draft: %s (score=%.1f)", title, top_score)
        logger.info("[DRY-RUN] brief_json preview: %s", json.dumps(top_detail, indent=2))
        return 0

    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2, command_timeout=30)
    try:
        async with pool.acquire() as conn:
            if staging_id and await _already_seen(conn, staging_id):
                logger.info("Staging item %s already has a draft — skip (dedup)", staging_id)
                return 1

        brief_json: dict[str, Any] = {
            "staging_id": staging_id,
            "staging_type": top_item.get("type"),
            "source_url": top_item.get("source"),
            "article_title": title,
            "article_summary": (top_item.get("content") or "")[:2000],
            "detected_at": top_item.get("detected_at"),
            "picked_at": datetime.now(timezone.utc).isoformat(),
            "score_detail": top_detail,
        }
        async with pool.acquire() as conn:
            draft_id = await conn.fetchval(
                """
                INSERT INTO war_room_drafts (topic, register, status, brief_json)
                VALUES ($1, NULL, 'briefed', $2::jsonb)
                RETURNING id
                """,
                title[:500],
                json.dumps(brief_json),
            )
        logger.info("Created draft %s — topic=%r score=%.1f", draft_id, title[:80], top_score)
    finally:
        await pool.close()

    kws = ", ".join(top_detail["rules"]["keywords_matched"][:8]) or "none"
    _send_telegram(
        "WR2 nuovo topic carosello\n"
        f"Topic: {title[:120]}\n"
        f"Score: {top_score:.0f} | Tier: {top_detail['rules']['tier']}\n"
        f"Keywords: {kws}\n"
        f"Draft: {draft_id}\n"
        "Draft Generator parte 05:15",
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="bypass score threshold")
    parser.add_argument("--rank", type=int, default=0, help="0=top, 1=#2, 2=#3... (testing)")
    args = parser.parse_args()

    _configure_logging()
    try:
        return asyncio.run(run(dry_run=args.dry_run, force=args.force, rank=args.rank))
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        logger.exception("Unhandled error: %s", e)
        _send_telegram(f"WR2 topic_selector crashed\n{str(e)[:400]}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
