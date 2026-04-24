#!/usr/bin/env python3
"""Fase 0 Day 2 driver — classify 25 @balizero0 posts + persist corpus.

Produces `research/sota-social-2026-v1/01_balizero_corpus.json`.

Gate 2 (EOD day 2): no tone register >60% of sample.
  - script exits 1 if skew detected

Per-post output record:
    post_id, caption, format, hook_type, tone_register, topic,
    posted_hour_wita, likes, comments, saves, reach, engagement_rate
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "apps" / "backend-rag"))

# Backend Settings validation placeholders (same trick as sota_build_baseline.py)
os.environ.setdefault("JWT_SECRET_KEY", "sota-research-local-dev-placeholder-32chars-min-ok")
os.environ.setdefault("API_KEYS", "sota-research-local-placeholder-key")

from backend.services.measurer.ig_graph_sensor import IGGraphSensor  # noqa: E402
from backend.services.research.empirical_ig_analyzer import (  # noqa: E402
    EmpiricalIGAnalyzer,
    ClassifiedPost,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sota.day2")

OUTPUT = _REPO_ROOT / "research" / "sota-social-2026-v1" / "01_balizero_corpus.json"


def _infer_topic(caption: str) -> str:
    """Heuristic topic bucket from caption content.

    5 buckets chosen to match Bali Zero's core service lines. Posts that
    don't match any bucket get "general".
    """
    c = (caption or "").lower()
    if any(w in c for w in ["kitas", "visa", "e33", "b211", "kitap"]):
        return "visa"
    if any(w in c for w in ["pt pma", "pma", "kbli", "nib", "oss", "company"]):
        return "company"
    if any(w in c for w in ["tax", "npwp", "dta", "aire", "tassazione", "pajak"]):
        return "tax"
    if any(w in c for w in ["villa", "imb", "pbg", "hak pakai", "property", "real estate"]):
        return "property"
    return "general"


def _hour_wita(timestamp_iso: str) -> int:
    """Convert Meta's ISO timestamp (UTC+0) → hour in WITA (UTC+8).

    Returns -1 if parse fails. Meta returns e.g. "2026-04-21T10:23:12+0000".
    """
    try:
        # Python 3.11 doesn't accept "+0000" without ":" — normalize.
        normalized = timestamp_iso.replace("Z", "+00:00")
        if "+" in normalized and ":" not in normalized.split("+")[-1]:
            tz_part = normalized.split("+")[-1]
            normalized = normalized[: -len(tz_part)] + f"{tz_part[:2]}:{tz_part[2:]}"
        dt = datetime.fromisoformat(normalized)
        return (dt.hour + 8) % 24
    except Exception:
        return -1


async def main() -> int:
    token = os.environ.get("IG_GRAPH_API_TOKEN")
    ig_id = os.environ.get("IG_BUSINESS_ACCOUNT_ID")
    if not (token and ig_id):
        logger.error("IG secrets missing (IG_GRAPH_API_TOKEN + IG_BUSINESS_ACCOUNT_ID)")
        return 2

    sensor = IGGraphSensor(token=token, ig_user_id=ig_id)
    analyzer = EmpiricalIGAnalyzer(ig_sensor=sensor)

    # IGGraphSensor.read_posts returns IGPostMetrics dataclass instances;
    # but load_posts_for_analysis just slices what sensor.read_posts returns.
    # Adapt: IGGraphSensor's read_posts yields IGPostMetrics objects.
    raw_posts = await analyzer.load_posts_for_analysis()
    logger.info("loaded %d posts for analysis (expected 25)", len(raw_posts))

    # Normalize to dicts for classifier (IGPostMetrics has same field names)
    posts_dicts: list[dict] = []
    for p in raw_posts:
        if hasattr(p, "post_id"):  # IGPostMetrics dataclass
            posts_dicts.append(asdict(p))
        else:
            posts_dicts.append(dict(p))

    logger.info("classifying hooks via claude -p...")
    hooks = analyzer.classify_hooks_batch(posts_dicts)
    logger.info("hooks classified: %d/%d", len(hooks), len(posts_dicts))

    logger.info("classifying tones via gemini 3.1 pro...")
    tones = analyzer.classify_tones_batch(posts_dicts)
    logger.info("tones classified: %d/%d", len(tones), len(posts_dicts))

    classified: list[ClassifiedPost] = []
    for p in posts_dicts:
        cp = ClassifiedPost(
            post_id=p["post_id"],
            caption=p.get("caption", ""),
            format=p.get("format", "IMAGE"),
            hook_type=hooks.get(p["post_id"], "unknown"),
            tone_register=tones.get(p["post_id"], "unknown"),
            topic=_infer_topic(p.get("caption", "")),
            posted_hour_wita=_hour_wita(p.get("timestamp", "")),
            likes=int(p.get("likes", 0) or 0),
            comments=int(p.get("comments", 0) or 0),
            saves=int(p.get("saves", 0) or 0),
            reach=int(p.get("reach", 0) or 0),
        )
        classified.append(cp)

    # Gate 2 skew check on tone distribution
    tone_dist = Counter(c.tone_register for c in classified)
    ok, dominant, pct = EmpiricalIGAnalyzer.check_skew(dict(tone_dist), threshold=0.6)

    # Persist
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps({
            "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "source_account": os.environ.get("IG_BUSINESS_HANDLE", "balizero0"),
            "sample_size": len(classified),
            "tone_distribution": dict(tone_dist),
            "hook_distribution": dict(Counter(c.hook_type for c in classified)),
            "topic_distribution": dict(Counter(c.topic for c in classified)),
            "format_distribution": dict(Counter(c.format for c in classified)),
            "dominant_tone_pct": round(pct, 3),
            "gate_2_skew_ok": ok,
            "posts": [
                {**asdict(c), "engagement_rate": c.engagement_rate}
                for c in classified
            ],
        }, indent=2),
        encoding="utf-8",
    )
    logger.info("wrote %s (%d posts)", OUTPUT, len(classified))

    if not ok:
        logger.error(
            "Gate 2 FAIL: tone %r = %.1f%% (>60%%)",
            dominant, pct * 100,
        )
        return 1
    logger.info("Gate 2 OK: dominant tone %r = %.1f%%", dominant, pct * 100)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
