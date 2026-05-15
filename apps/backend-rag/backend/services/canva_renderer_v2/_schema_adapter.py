"""Legacy slides_json schema → v2 (Article 14 layout_family) adapter.

Detection: presence of `slide_type` field on first slide AND absence of
`layout_family` → legacy. Otherwise v2 passes through unchanged.

Used for drafts created before 2026-05-13 by storyboarder versions that
emitted slide_type strings. Storyboarder patched 2026-05-13 emits v2
schema directly; orchestrator handles both via this adapter inline.

Source material: /tmp/wr2_legacy_adapter.py (working draft 2026-05-13).
"""
from __future__ import annotations

import logging
import re
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

LEGACY_TO_LAYOUT = {
    "cover": "cover-photo",
    "take": "photo-headline-yellow-sub",
    "context": "photo-headline-yellow-sub",
    "shift": "evidence-carved",
    "mechanism": "swiss-grid-asymmetry",
    "stake": "photo-headline-yellow-sub",
    "law": "thin-red-rule-divider",
    "fiction-vs-substance": "dark-status-list",
    "numbers": "stat-card-hero",
    "signal": "photo-headline-yellow-sub",
    "cta": "elegant-close",
    "closing": "statement-bomb",
    "statement": "statement-bomb",
    "insight": "photo-headline-yellow-sub",
}

HERO_CACHE_DIR = Path("/tmp/wr2_hero_cache")


def is_legacy_schema(data: dict[str, Any]) -> bool:
    """Detect legacy schema by presence of `slide_type` on any slide.

    Fix 2026-05-15 [Codex find]: when this returns True, log a HIGH-VISIBILITY
    metric so we can detect storyboarder drift. Adapter accepting legacy
    schema can hide that storyboard still emits old format. Future cutoff
    (recommended 2026-06-15) should turn this into a hard fail via env
    var WR2_DISALLOW_LEGACY_SCHEMA=1.
    """
    slides = data.get("slides", [])
    if not slides:
        return False
    first = slides[0]
    is_legacy = "slide_type" in first and "layout_family" not in first
    if is_legacy:
        # Metric: log to stderr with structured prefix so log scrapers can
        # alert on it. Format mirrors Bali Zero cron-agent-python convention.
        import os as _os
        import sys as _sys
        draft_id = data.get("draft_id") or data.get("carousel_id") or "unknown"
        logger.warning(
            "[wr2-schema-adapter] legacy_schema_adapted=1 draft_id=%s — "
            "storyboarder emitted slide_type (pre-2026-05-13 format). "
            "If this persists past 2026-06-15 it is a structural bug.",
            draft_id,
        )
        print(f"[wr2-schema-adapter] METRIC legacy_schema_adapted=1 draft={draft_id}",
              file=_sys.stderr)
        # Optional hard-fail via env (recommended after cutoff)
        if _os.environ.get("WR2_DISALLOW_LEGACY_SCHEMA", "").lower() in {"1", "true", "yes"}:
            raise ValueError(
                f"Legacy slide_type schema rejected for draft {draft_id} "
                "(WR2_DISALLOW_LEGACY_SCHEMA=1). Storyboarder must emit "
                "layout_family (v2 schema). Update storyboarder skill or "
                "unset env var to bypass."
            )
    return is_legacy


def _download_hero(url: str, slide_n: int) -> str | None:
    """Download hero image to cache. Filename = SHA1(url)[:16] to prevent
    cross-draft cache collision.

    BUG FIX 2026-05-13: previous version used `hero_{slide_n:02d}.jpg` which
    caused multiple drafts to share the same cache file (slide 1 of draft A
    served from slide 1 of draft B). The orchestrator's first end-to-end
    run rendered Sam Altman with Marina Pinyaylova's heroes.
    """
    if not url:
        return None
    import hashlib
    HERO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    url_hash = hashlib.sha1(url.encode()).hexdigest()[:16]
    dest = HERO_CACHE_DIR / f"hero_{slide_n:02d}_{url_hash}.jpg"
    if dest.exists():
        return str(dest)
    try:
        urllib.request.urlretrieve(url, dest)  # noqa: S310
        return str(dest)
    except Exception as e:  # noqa: BLE001
        logger.warning("hero %d download failed: %s", slide_n, e)
        return None


def _map_swiss_grid_steps(body: str) -> list[dict]:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body) if s.strip()]
    steps: list[dict] = []
    for k, sent in enumerate(sentences[:3]):
        words = sent.split()
        head = " ".join(words[:4]).rstrip(",.;:")
        rest = " ".join(words[4:]).strip()
        steps.append({"num": f"{k + 1:02d}", "head": head, "body": rest[:90]})
    return steps


def adapt_legacy_schema(legacy: dict[str, Any], *, topic: str) -> dict[str, Any]:
    """Convert legacy slides_json → v2 Article 14 layout schema."""
    slides_in = legacy.get("slides", [])
    n = len(slides_in)
    adapted: list[dict] = []

    for i, ls in enumerate(slides_in):
        slide_type = ls.get("slide_type", "")
        layout = LEGACY_TO_LAYOUT.get(slide_type, "photo-headline-yellow-sub")
        if i == n - 1 and slide_type == "cta":
            layout = "statement-bomb"

        hero_path = None
        if ls.get("is_hero_image") and ls.get("image_url"):
            hero_path = _download_hero(ls["image_url"], ls.get("slide_number", i + 1))

        new: dict[str, Any] = {
            "index": ls.get("slide_number", i + 1),
            "layout_family": layout,
            "heading": ls.get("headline") or "",
            "subheading": ls.get("subhead") or "",
            "body": ls.get("body") or "",
        }
        if hero_path:
            new["hero_image_path"] = hero_path

        if layout == "statement-bomb":
            new["statement"] = ls.get("headline") or (ls.get("body", "") or "")[:120]
        elif layout == "stat-card-hero":
            text = (ls.get("body") or "") + " " + (ls.get("headline") or "")
            m = re.search(r"\b(\d+(?:,\d{3})*(?:\.\d+)?[KMB%]?)\b", text)
            new["stat"] = m.group(1) if m else "—"
            new["caption"] = (ls.get("body") or "")[:120]
            new["source"] = ls.get("subhead") or ""
        elif layout == "thin-red-rule-divider":
            new["body"] = ls.get("body") or ls.get("headline") or ""
            new["source"] = ls.get("subhead") or ""
        elif layout == "swiss-grid-asymmetry":
            new["yellow_accent"] = ls.get("subhead") or "MECHANISM"
            new["steps"] = _map_swiss_grid_steps(ls.get("body") or "")
        elif layout == "dark-status-list":
            new["list_items"] = [
                {"label": "FICTION", "value": "MYTH", "status": "critical"},
                {"label": "SUBSTANCE", "value": "FACT", "status": "positive"},
            ]
        elif layout == "elegant-close":
            new["heading"] = "Want to act on this?"
            new["body"] = ls.get("body") or ""
            new["email"] = "zantara@balizero.com"
            new["whatsapp"] = "wa.me/6285954680980"
        elif layout == "evidence-carved":
            new["evidence_code"] = ls.get("subhead") or ""

        adapted.append(new)

    out = {
        "carousel_id": legacy.get("carousel_id", topic.lower().replace(" ", "-")[:80]),
        "slide_count": len(adapted),
        "slides": adapted,
    }
    return out
