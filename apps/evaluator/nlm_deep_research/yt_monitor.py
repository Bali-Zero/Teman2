"""YouTube Channel Monitor for NLM Notebooks.

Polls government YouTube channels via RSS, filters by keyword relevance,
and ingests high-value videos into the appropriate NLM notebook.

Extends the T4 Social Monitor pattern from t4_monitor.py.

Usage:
    python -m apps.evaluator.nlm_deep_research.yt_monitor [--dry-run] [--nb NB-2]

Cron (OpenClaw): every 6h, offset from T4 monitor
    30 */6 * * *  run_yt_monitor.sh
"""

from __future__ import annotations

import json
import hashlib
import logging
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHANNELS_FILE = Path(__file__).parent / "yt_channels.json"
STATE_FILE = Path(__file__).parent / "yt_state.json"
RSS_BASE = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
VIDEO_URL_BASE = "https://www.youtube.com/watch?v={video_id}"

NB_IDS = {
    "NB-2": "cff93ab0-813a-42f2-a8de-36987e724271",
    "NB-3": "933509f9-1561-403d-bd44-4a7a67a36df2",
    "NB-4": "d4b2eedb-9863-4a1a-81ff-a11b0b45d853",
    "NB-5": "d9438180-5e63-4e2a-a473-6061101f6a8d",
}


@dataclass
class YTVideo:
    """Normalized YouTube video from RSS feed."""

    channel_key: str
    video_id: str
    url: str
    title: str
    published_at: Optional[datetime] = None
    channel_name: str = ""
    tier: str = "YT-T0"
    target_notebooks: list[str] = field(default_factory=list)
    relevance_score: float = 0.0
    filter_result: str = "PENDING"


# ---------------------------------------------------------------------------
# RSS Fetching
# ---------------------------------------------------------------------------


def fetch_channel_rss(channel_id: str, max_entries: int = 15) -> list[dict]:
    """Fetch latest videos from YouTube RSS feed.

    Returns list of dicts with: video_id, title, published, link.
    """
    import feedparser  # noqa: PLC0415

    url = RSS_BASE.format(channel_id=channel_id)
    feed = feedparser.parse(url)

    if feed.bozo and not feed.entries:
        logger.warning("RSS feed error for %s: %s", channel_id, feed.bozo_exception)
        return []

    entries = []
    for entry in feed.entries[:max_entries]:
        video_id = entry.get("yt_videoid", "")
        if not video_id:
            # Extract from link
            link = entry.get("link", "")
            if "watch?v=" in link:
                video_id = link.split("watch?v=")[-1].split("&")[0]

        if not video_id:
            continue

        published = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            except Exception:
                pass

        entries.append({
            "video_id": video_id,
            "title": entry.get("title", ""),
            "published": published,
            "link": entry.get("link", VIDEO_URL_BASE.format(video_id=video_id)),
        })

    return entries


# ---------------------------------------------------------------------------
# Keyword Relevance Filter
# ---------------------------------------------------------------------------


def compute_relevance(
    title: str,
    keywords_critical: list[str],
    keywords_high: list[str],
) -> tuple[float, str]:
    """Score video title relevance. Returns (score, reason).

    Scoring:
      - CRITICAL keyword match: 0.8 base + 0.1 per additional
      - HIGH keyword match (≥2): 0.5 base + 0.1 per additional
      - HIGH keyword match (1): 0.3
      - No match: 0.0
    """
    text = title.lower()

    critical_hits = [kw for kw in keywords_critical if kw in text]
    high_hits = [kw for kw in keywords_high if kw in text]

    if critical_hits:
        score = min(1.0, 0.8 + 0.1 * (len(critical_hits) - 1))
        return score, f"CRITICAL: {', '.join(critical_hits)}"
    elif len(high_hits) >= 2:
        score = min(1.0, 0.5 + 0.1 * (len(high_hits) - 2))
        return score, f"HIGH(x{len(high_hits)}): {', '.join(high_hits)}"
    elif len(high_hits) == 1:
        return 0.3, f"HIGH(x1): {high_hits[0]}"
    else:
        return 0.0, "NO_MATCH"


# ---------------------------------------------------------------------------
# NB Routing
# ---------------------------------------------------------------------------


def route_to_notebooks(
    title: str,
    channel_notebooks: list[str],
    channel_key: str,
) -> list[str]:
    """Route a video to specific notebooks based on title keywords.

    For multi-NB channels (e.g., Sekretariat Presiden), filter by
    minister/topic keywords.
    """
    if len(channel_notebooks) == 1:
        return channel_notebooks

    text = title.lower()
    routed = []

    nb_keywords = {
        "NB-2": ["imigrasi", "visa", "kitas", "kitap", "paspor", "wna", "tka", "migran"],
        "NB-3": ["investasi", "pma", "bkpm", "perizinan", "oss", "nib", "perusahaan"],
        "NB-4": ["pajak", "fiskal", "keuangan", "coretax", "spt", "ppn", "pph"],
        "NB-5": ["tanah", "pertanahan", "bpn", "atr", "properti", "sertifikat"],
    }

    for nb in channel_notebooks:
        keywords = nb_keywords.get(nb, [])
        if any(kw in text for kw in keywords):
            routed.append(nb)

    return routed if routed else channel_notebooks[:1]


# ---------------------------------------------------------------------------
# State Management
# ---------------------------------------------------------------------------


def load_state() -> dict:
    """Load ingested video IDs from state file."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"ingested": {}, "last_poll": None, "stats": {"total_polled": 0, "total_ingested": 0}}


def save_state(state: dict) -> None:
    """Save state to disk."""
    state["last_poll"] = datetime.now(timezone.utc).isoformat()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# NLM Ingestion
# ---------------------------------------------------------------------------


def _enqueue_to_intel_lake(video_url: str, notebook_id: str, source_handle: str | None = None) -> None:
    """Wave 2 (2026-05-12): mirror this YT ingestion into the Intel Lake outbox.

    Best-effort — failure must not break the existing yt_monitor flow.
    """
    try:
        import hashlib  # noqa: PLC0415
        import sys  # noqa: PLC0415
        sys.path.insert(0, "/Users/nuzantara/scripts")
        from intel_lake_outbox import enqueue as _lake_enqueue  # type: ignore

        content_hash = hashlib.sha256(video_url.encode()).hexdigest()[:32]
        _lake_enqueue(
            "yt_monitor",
            {
                "producer_name": "yt_monitor",
                "canonical_url": video_url,
                "content_hash": content_hash,
                "title": video_url,  # full title unknown at this layer
                "summary": None,
                "source_domain": "youtube.com",
                "language": None,
                "jurisdiction": None,
                "topic_tags": ["youtube", "video"],
                "published_at": None,
                "score": None,
                "raw_payload": {
                    "notebook_id": notebook_id,
                    "source_handle": source_handle,
                },
            },
        )
    except Exception as exc:
        logger.warning("intel-lake enqueue failed for %s: %s", video_url[:80], exc)


def ingest_video(notebook_id: str, video_url: str, dry_run: bool = False) -> bool:
    """Ingest a YouTube video into NLM notebook via nlm CLI."""
    if dry_run:
        logger.info("[DRY-RUN] Would ingest %s into %s", video_url, notebook_id)
        return True

    try:
        # PR-E1 (2026-04-30): nlm CLI dropped --notebook flag — NOTEBOOK_ID
        # is now a positional, --youtube replaces --url for YT video ingestion.
        result = subprocess.run(
            ["nlm", "source", "add", notebook_id, "--youtube", video_url],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            logger.info("Ingested %s into %s", video_url, notebook_id)
            _enqueue_to_intel_lake(video_url, notebook_id)
            return True
        else:
            logger.error("nlm ingest failed: %s", result.stderr[:200])
            return False
    except subprocess.TimeoutExpired:
        logger.error("nlm ingest timeout for %s", video_url)
        return False
    except FileNotFoundError:
        logger.error("nlm CLI not found — install with: pip install nlm-cli")
        return False


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------


def _is_denied_title(title: str, denylist: list[str]) -> bool:
    """Check if title matches any denylist pattern (ceremonial, greetings, bumpers)."""
    text = title.lower()
    return any(pattern in text for pattern in denylist)


def _is_youtube_short(url: str) -> bool:
    """Check if URL is a YouTube Short."""
    return "/shorts/" in url


def run_monitor(
    dry_run: bool = False,
    target_nb: str | None = None,
    max_age_days: int = 30,
    svs_threshold: float = 0.35,
) -> dict:
    """Run the YouTube monitor pipeline.

    Returns summary dict with stats.
    """
    # Load config
    with open(CHANNELS_FILE) as f:
        config = json.load(f)

    channels = config["channels"]
    rules = config.get("monitoring_rules", {})
    title_denylist = config.get("title_denylist", [])
    t1_min_matches = rules.get("t1_min_keyword_matches", 2)
    skip_shorts = rules.get("shorts_policy", "skip") == "skip"

    state = load_state()
    ingested_ids = state.get("ingested", {})

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    stats = {
        "channels_polled": 0,
        "videos_found": 0,
        "videos_relevant": 0,
        "videos_ingested": 0,
        "videos_skipped_dedup": 0,
        "videos_skipped_old": 0,
        "videos_skipped_irrelevant": 0,
        "videos_skipped_denied": 0,
        "videos_skipped_shorts": 0,
        "errors": [],
    }

    for key, ch in channels.items():
        channel_id = ch.get("channel_id")
        if not channel_id:
            logger.debug("Skipping %s — no channel_id", key)
            continue

        # Allow channels even without rss_verified — try and log errors
        # Filter by target NB if specified
        if target_nb and target_nb not in ch.get("notebooks", []):
            continue

        logger.info("Polling %s (%s) [%s]", ch["name"], key, ch.get("tier", "?"))
        stats["channels_polled"] += 1

        try:
            entries = fetch_channel_rss(channel_id)
        except Exception as e:
            logger.error("RSS fetch failed for %s: %s", key, e)
            stats["errors"].append(f"{key}: {e}")
            continue

        tier = ch.get("tier", "YT-T4")

        for entry in entries:
            video_id = entry["video_id"]
            stats["videos_found"] += 1

            # Skip Shorts
            if skip_shorts and _is_youtube_short(entry["link"]):
                stats["videos_skipped_shorts"] += 1
                continue

            # Dedup
            url_hash = hashlib.sha256(entry["link"].encode()).hexdigest()[:16]
            if url_hash in ingested_ids:
                stats["videos_skipped_dedup"] += 1
                continue

            # Age filter
            if entry["published"] and entry["published"] < cutoff:
                stats["videos_skipped_old"] += 1
                continue

            # Title denylist (ceremonial, greetings, bumpers)
            if _is_denied_title(entry["title"], title_denylist):
                stats["videos_skipped_denied"] += 1
                logger.debug("DENY %s (denylist)", entry["title"][:60])
                continue

            # Keyword relevance
            score, reason = compute_relevance(
                entry["title"],
                ch.get("keywords_critical", []),
                ch.get("keywords_high", []),
            )

            # T1 channels (press/media) require ≥2 keyword matches to avoid noise
            if tier == "YT-T1" and "HIGH(x1)" in reason:
                stats["videos_skipped_irrelevant"] += 1
                logger.debug("SKIP T1 single-match: %s", entry["title"][:60])
                continue

            if score < svs_threshold:
                stats["videos_skipped_irrelevant"] += 1
                logger.debug("SKIP %s (%.2f): %s", entry["title"][:60], score, reason)
                continue

            stats["videos_relevant"] += 1
            logger.info("ADMIT %.2f [%s] [%s] %s", score, tier, reason, entry["title"][:80])

            # Route to notebooks
            target_nbs = route_to_notebooks(entry["title"], ch["notebooks"], key)

            for nb in target_nbs:
                nb_id = NB_IDS.get(nb)
                if not nb_id:
                    continue

                success = ingest_video(nb_id, entry["link"], dry_run=dry_run)
                if success:
                    stats["videos_ingested"] += 1
                    ingested_ids[url_hash] = {
                        "video_id": video_id,
                        "title": entry["title"],
                        "channel": key,
                        "notebook": nb,
                        "score": score,
                        "reason": reason,
                        "ingested_at": datetime.now(timezone.utc).isoformat(),
                    }

    # Save state
    state["ingested"] = ingested_ids
    state["stats"]["total_polled"] += stats["videos_found"]
    state["stats"]["total_ingested"] += stats["videos_ingested"]
    save_state(state)

    logger.info(
        "YT Monitor complete: %d polled, %d relevant, %d ingested, %d dedup, %d old, %d irrelevant",
        stats["videos_found"],
        stats["videos_relevant"],
        stats["videos_ingested"],
        stats["videos_skipped_dedup"],
        stats["videos_skipped_old"],
        stats["videos_skipped_irrelevant"],
    )

    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="YouTube Channel Monitor for NLM")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually ingest")
    parser.add_argument("--nb", type=str, default=None, help="Filter to specific NB (e.g., NB-2)")
    parser.add_argument("--max-age", type=int, default=30, help="Max video age in days")
    parser.add_argument("--threshold", type=float, default=0.35, help="SVS threshold")
    args = parser.parse_args()

    stats = run_monitor(
        dry_run=args.dry_run,
        target_nb=args.nb,
        max_age_days=args.max_age,
        svs_threshold=args.threshold,
    )

    print(json.dumps(stats, indent=2))
