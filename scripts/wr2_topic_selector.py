#!/usr/bin/env python3
"""WR2 Topic Selector — pick the best article from staging, create a draft.

Daily cron entry (05:00 WITA): fetches pending items from the News Room
staging area (on Fly), scores them with a deterministic heuristic
(freshness + Bali-Zero keyword relevance + tier), and if the top score
beats a threshold writes a new row into war_room_drafts (status=briefed).

Manual override (--topic-url): bypass the staging fetch + scoring entirely
and inject a draft from a single URL the operator picks. Fetches the page,
extracts <title> and the largest <article>/<main>/<p> text block, and
INSERTs a `briefed` row directly. Use when a news item matters more than
the cron's score sees (e.g. Pemkab announcements, BPD Bali notices).

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
# 2026-05-07: hard cutoff. Owner policy: news >3 days old is stale, never
# pickable. Previously the freshness_score decayed asymptotically but never
# zeroed out, so a 12-day-old article with strong tier+keywords could still
# beat a 1-day-old weaker one. Production failure: cron 05:10 picked an
# article from 24 April (12 days old) on 6 May. Override via
# WR2_MAX_ARTICLE_AGE_HOURS env if you ever need to relax for a backfill.
MAX_ARTICLE_AGE_HOURS: float = float(os.environ.get("WR2_MAX_ARTICLE_AGE_HOURS", "72"))
TIER_WEIGHT: dict[str, int] = {"T1": 30, "T2": 15, "T3": 5}
SCORE_THRESHOLD: float = 40.0
STAGING_FETCH_TIMEOUT: float = 30.0

# PR-1 §C: live news preference. The intel-scraper enricher (Section B) tags
# each staging item with live_news_score (0-100) and a derived liveness_tier
# (breaking >= 80, developing 40-79, evergreen <40). The selector turns those
# into a soft score adjustment so that — all else equal — a breaking-news
# item beats an evergreen guide.
#
# Bonus: live_news_score / 2 → up to +50 points for breaking, +40 max for
# upper-developing, 0 for evergreen. Defense-in-depth on top of the
# live-first hard filter (when WR2_PREFER_LIVE_NEWS=true).
#
# Penalty: -20 if the headline matches a routine/evergreen pattern. Even
# with a live_news_score from the enricher, a "How to apply for KITAS" or
# "The Complete Guide to PT PMA" should never beat an actual breaking item.
import re  # noqa: E402

LIVE_NEWS_BONUS_DIVISOR: float = 2.0  # score / 2 → 0..50 points
ROUTINE_TITLE_PENALTY: float = 20.0
ROUTINE_TITLE_PATTERN: re.Pattern[str] = re.compile(
    r"^\s*(?:how\s+to|guide\s+to|the\s+complete\s+guide|.+\s+explained|.+\s+decoded|step[-\s]by[-\s]step|everything\s+you\s+need)\b",
    re.IGNORECASE,
)
LIVENESS_TIER_VALID = {"breaking", "developing", "evergreen"}


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

    # Live news bonus (PR-1 §C). The intel-scraper enricher computes
    # live_news_score (0-100); we use it as a soft additive signal here.
    # Defaults to 0 when the field is missing (legacy items, evergreen).
    raw_live = item.get("live_news_score")
    try:
        live_news_score = int(round(float(raw_live))) if raw_live is not None else 0
    except (TypeError, ValueError):
        live_news_score = 0
    live_news_score = max(0, min(100, live_news_score))
    live_bonus = round(live_news_score / LIVE_NEWS_BONUS_DIVISOR, 1)
    detail["rules"]["live_news_score"] = live_news_score
    detail["rules"]["live_news_bonus"] = live_bonus

    liveness_tier = str(item.get("liveness_tier") or "").lower()
    if liveness_tier not in LIVENESS_TIER_VALID:
        liveness_tier = "evergreen"
    detail["rules"]["liveness_tier"] = liveness_tier

    # Routine/evergreen title penalty (PR-1 §C). Even when the enricher
    # mistakenly stamps a live_news_score on a routine guide, the headline
    # shape gives it away. Conservative: only fires on the title, not body.
    routine_penalty = 0.0
    if title and ROUTINE_TITLE_PATTERN.search(title):
        routine_penalty = ROUTINE_TITLE_PENALTY
    detail["rules"]["routine_penalty"] = routine_penalty

    total = fresh_score + kw_score + tier_score + live_bonus - routine_penalty
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


async def _seen_staging_ids(
    conn: asyncpg.Connection, staging_ids: list[str]
) -> set[str]:
    """Return the subset of staging_ids that already have a draft (bulk check)."""
    if not staging_ids:
        return set()
    rows = await conn.fetch(
        "SELECT brief_json->>'staging_id' AS sid FROM war_room_drafts "
        "WHERE brief_json->>'staging_id' = ANY($1::text[])",
        staging_ids,
    )
    return {r["sid"] for r in rows if r["sid"]}


MANUAL_FETCH_TIMEOUT: float = 30.0
MANUAL_USER_AGENT: str = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
)


async def _fetch_article(url: str) -> dict[str, str]:
    """Fetch a URL and extract a usable title + body for manual draft injection.

    Tries a cascade of selectors via stdlib HTMLParser — no BS4 dep on Pro.
    Returns dict with `title`, `body`, `source` (host). Raises RuntimeError on
    non-2xx / empty body.
    """
    from html.parser import HTMLParser
    from urllib.parse import urlparse

    async with httpx.AsyncClient(
        timeout=MANUAL_FETCH_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": MANUAL_USER_AGENT},
    ) as client:
        resp = await client.get(url)
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code} fetching {url}")
    html = resp.text
    if not html or len(html) < 200:
        raise RuntimeError(f"Empty/short body fetching {url} ({len(html)} bytes)")

    class _Extractor(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.title_buf: list[str] = []
            self.in_title = False
            self.skip_depth = 0  # script/style/nav nesting
            self.paragraphs: list[str] = []
            self.current: list[str] = []
            self.in_p = False

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag in {"script", "style", "noscript", "nav", "header", "footer", "aside"}:
                self.skip_depth += 1
                return
            if self.skip_depth:
                return
            if tag == "title":
                self.in_title = True
            elif tag == "p":
                self.in_p = True
                self.current = []

        def handle_endtag(self, tag: str) -> None:
            if tag in {"script", "style", "noscript", "nav", "header", "footer", "aside"}:
                if self.skip_depth:
                    self.skip_depth -= 1
                return
            if self.skip_depth:
                return
            if tag == "title":
                self.in_title = False
            elif tag == "p":
                if self.in_p:
                    text = " ".join(self.current).strip()
                    if len(text) > 30:
                        self.paragraphs.append(text)
                self.in_p = False

        def handle_data(self, data: str) -> None:
            if self.skip_depth:
                return
            if self.in_title:
                self.title_buf.append(data)
            elif self.in_p:
                self.current.append(data)

    parser = _Extractor()
    parser.feed(html)
    title = " ".join(parser.title_buf).strip() or url
    # Drop site-name suffix patterns ("Title - Site" / "Title | Site")
    for sep in (" | ", " - ", " — "):
        if sep in title:
            head, _, _ = title.partition(sep)
            if len(head) > 20:
                title = head
                break
    body_paragraphs = parser.paragraphs[:40]  # cap for sanity
    body = "\n\n".join(body_paragraphs).strip()
    if not body:
        raise RuntimeError(f"No <p> body extracted from {url}")
    host = urlparse(url).netloc or url
    return {"title": title[:500], "body": body[:8000], "source": host}


async def run_manual_topic(
    *,
    url: str,
    dry_run: bool = False,
    register: str | None = None,
) -> int:
    """Inject a manual draft from a single URL, bypassing staging+scoring.

    Bypasses: staging fetch, age filter, live-news preference, score
    threshold, dedup against staging_id (no staging_id exists). Marks the
    draft with `manual_override=True` so downstream tools can audit it.
    """
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL not set")
        return 2

    logger.info("Manual topic injection: fetching %s", url)
    try:
        article = await _fetch_article(url)
    except Exception as e:
        logger.exception("Manual fetch failed: %s", e)
        _send_telegram(f"WR2 manual topic fetch failed\n{url}\n{e}")
        return 2

    title = article["title"]
    body = article["body"]
    source = article["source"]
    logger.info(
        "Extracted: title=%r source=%s body_chars=%d",
        title[:100], source, len(body),
    )

    brief_json: dict[str, Any] = {
        "manual_override": True,
        "source_url": url,
        "source_host": source,
        "article_title": title,
        "article_summary": body[:2000],
        "article_body_full": body,
        "enrichment": {},
        "live_news_score": None,
        "liveness_tier": "manual",
        "live_news_reasons": [],
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "picked_at": datetime.now(timezone.utc).isoformat(),
        "score_detail": {"score": None, "rules": {"manual_override": True}},
    }

    if dry_run:
        logger.info("[DRY-RUN] Would create manual draft:\n%s", json.dumps({
            "topic": title[:120],
            "register": register,
            "brief_json_preview": {k: v for k, v in brief_json.items() if k != "article_body_full"},
        }, indent=2))
        return 0

    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2, command_timeout=30)
    try:
        async with pool.acquire() as conn:
            draft_id = await conn.fetchval(
                """
                INSERT INTO war_room_drafts (topic, register, status, brief_json)
                VALUES ($1, $2, 'briefed', $3::jsonb)
                RETURNING id
                """,
                title[:500],
                register,
                json.dumps(brief_json),
            )
    finally:
        await pool.close()

    logger.info("Created manual draft %s — topic=%r", draft_id, title[:80])
    _send_telegram(
        "WR2 manual topic injected\n"
        f"Topic: {title[:120]}\n"
        f"Source: {source}\n"
        f"URL: {url}\n"
        f"Draft: {draft_id}\n"
        "Draft Generator parte al prossimo run (05:15 WITA)",
    )
    return 0


async def run(*, dry_run: bool = False, force: bool = False) -> int:
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

    # 2026-05-07: hard age cutoff. Owner policy: never pick news >3 days old.
    # Drops items whose detected_at/published_at is older than
    # MAX_ARTICLE_AGE_HOURS (default 72). If the cutoff empties the pool,
    # the pipeline goes idle for the day rather than recycle stale topics.
    now_utc = datetime.now(timezone.utc)

    def _item_age_hours(it: dict[str, Any]) -> float:
        dt = _parse_dt(it.get("detected_at")) or _parse_dt(it.get("published_at"))
        if dt is None:
            return float("inf")  # missing timestamp → treat as stale
        return max(0.0, (now_utc - dt).total_seconds() / 3600.0)

    fresh_items = [i for i in items if _item_age_hours(i) <= MAX_ARTICLE_AGE_HOURS]
    dropped_stale = len(items) - len(fresh_items)
    if dropped_stale:
        logger.info(
            "Age filter: dropped %d items older than %.0fh (kept %d)",
            dropped_stale, MAX_ARTICLE_AGE_HOURS, len(fresh_items),
        )
    if not fresh_items:
        logger.warning(
            "Age filter emptied the pool (all %d items older than %.0fh) — "
            "pipeline idle for today. Override via WR2_MAX_ARTICLE_AGE_HOURS "
            "if backfill needed.",
            len(items), MAX_ARTICLE_AGE_HOURS,
        )
        return 0
    items = fresh_items

    # Live-first hard preference (PR-1 §C). When WR2_PREFER_LIVE_NEWS=true,
    # restrict the candidate pool to items the enricher tagged as breaking
    # or developing AND whose live_news_score crosses LIVE_NEWS_FILTER_MIN.
    # If that pool is empty, log explicitly and fall back to the full pool
    # (evergreen queue) so the pipeline never goes idle just because no
    # live news landed today. The score-bonus + routine-penalty in
    # score_item() apply on top regardless of this flag.
    prefer_live = os.environ.get("WR2_PREFER_LIVE_NEWS", "false").lower() == "true"
    live_filter_min = int(os.environ.get("WR2_LIVE_NEWS_FILTER_MIN", "40"))
    if prefer_live:
        live_pool = [
            i for i in items
            if str(i.get("liveness_tier") or "").lower() in {"breaking", "developing"}
            and (int(i.get("live_news_score") or 0) >= live_filter_min)
        ]
        if live_pool:
            logger.info(
                "WR2_PREFER_LIVE_NEWS=true: using live pool (%d items, score >= %d)",
                len(live_pool), live_filter_min,
            )
            items = live_pool
        else:
            logger.info(
                "WR2_PREFER_LIVE_NEWS=true: live pool empty (no items with "
                "liveness_tier∈{breaking,developing} AND live_news_score >= %d); "
                "falling back to evergreen pool (%d items)",
                live_filter_min, len(items),
            )

    scored = [(item, *score_item(item)) for item in items]
    scored.sort(key=lambda t: -t[1])

    for rank, (item, score, detail) in enumerate(scored[:5], start=1):
        logger.info(
            "#%d score=%.1f [%s/%s] kw=%d live=%d/%.1f routine=-%.0f title=%r",
            rank,
            score,
            detail["rules"]["tier"],
            detail["rules"].get("liveness_tier", "evergreen"),
            detail["rules"]["keywords_points"],
            detail["rules"].get("live_news_score", 0),
            detail["rules"].get("live_news_bonus", 0.0),
            detail["rules"].get("routine_penalty", 0.0),
            (item.get("title") or "")[:80],
        )

    threshold = 0.0 if force else SCORE_THRESHOLD

    # Bulk-check which of the top-N candidates already have a draft, then
    # pick the highest-scoring one that's NOT a duplicate. Without this,
    # the previous flow always picked scored[0] and bailed when it was
    # deduplicated, leaving the entire pipeline idle for the day even
    # though candidates #2..#N were untouched.
    DEDUP_LOOKAHEAD = int(os.environ.get("WR2_TOPIC_DEDUP_LOOKAHEAD", "20"))
    candidates = [t for t in scored[:DEDUP_LOOKAHEAD] if t[1] >= threshold]
    if not candidates:
        logger.info(
            "No candidates above threshold %.1f among top-%d — skip",
            threshold,
            DEDUP_LOOKAHEAD,
        )
        return 1

    candidate_ids = [
        (t[0].get("id") or "") for t in candidates if t[0].get("id")
    ]

    pool = await asyncpg.create_pool(
        dsn=dsn, min_size=1, max_size=2, command_timeout=30
    )
    try:
        async with pool.acquire() as conn:
            seen = await _seen_staging_ids(conn, candidate_ids)

        chosen: tuple[dict[str, Any], float, dict[str, Any]] | None = None
        for rank, (item, score, detail) in enumerate(candidates, start=1):
            sid = item.get("id") or ""
            if sid and sid in seen:
                logger.info(
                    "rank #%d %r (sid=%s) already has a draft — skip (dedup)",
                    rank,
                    (item.get("title") or "")[:80],
                    sid,
                )
                continue
            chosen = (item, score, detail)
            if rank > 1:
                logger.info(
                    "Picked rank #%d after %d dedup skip(s)", rank, rank - 1
                )
            break

        if chosen is None:
            logger.info(
                "All %d candidates already have a draft — nothing fresh to pick",
                len(candidates),
            )
            return 1

        top_item, top_score, top_detail = chosen
        staging_id = top_item.get("id") or ""
        title = top_item.get("title") or "(untitled)"

        if dry_run:
            logger.info("[DRY-RUN] Would create draft: %s (score=%.1f)", title, top_score)
            logger.info("[DRY-RUN] brief_json preview: %s", json.dumps(top_detail, indent=2))
            return 0

        # Enriched object pass-through (PR-1 §C bug fix). The intel-scraper
        # produces a full structured enrichment (1400-2000 words across
        # the_facts/bali_zero_take/in_practice/next_steps/faq) but the old
        # draft generator only saw `summary[:3500]` — i.e. ~25% of the
        # available material. We pass the entire enriched object through
        # brief_json so the draft generator can use the structured ground
        # truth instead of a truncated paragraph.
        enrichment_obj = top_item.get("enrichment") or {}
        brief_json: dict[str, Any] = {
            "staging_id": staging_id,
            "staging_type": top_item.get("type"),
            "source_url": top_item.get("source"),
            "article_title": title,
            "article_summary": (top_item.get("content") or "")[:2000],
            "enrichment": enrichment_obj,  # full structured object (PR-1 §C)
            "live_news_score": top_item.get("live_news_score"),
            "liveness_tier": top_item.get("liveness_tier"),
            "live_news_reasons": top_item.get("live_news_reasons") or [],
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
    parser.add_argument(
        "--topic-url",
        metavar="URL",
        help=(
            "Manual override: fetch this article URL, extract title+body, "
            "and INSERT a draft directly. Bypasses staging fetch, scoring, "
            "age filter, dedup. Use for ad-hoc topics the cron would miss."
        ),
    )
    parser.add_argument(
        "--register",
        metavar="REGISTER",
        default=None,
        help=(
            "Optional Council register hint for the draft (analitico, "
            "militante, pedagogico, ironico, rituale, poetico, tecnico). "
            "If omitted, draft_generator picks one."
        ),
    )
    args = parser.parse_args()

    _configure_logging()
    try:
        if args.topic_url:
            return asyncio.run(
                run_manual_topic(
                    url=args.topic_url,
                    dry_run=args.dry_run,
                    register=args.register,
                )
            )
        return asyncio.run(run(dry_run=args.dry_run, force=args.force))
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        logger.exception("Unhandled error: %s", e)
        _send_telegram(f"WR2 topic_selector crashed\n{str(e)[:400]}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
