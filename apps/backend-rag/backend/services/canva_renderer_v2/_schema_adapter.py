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
    """Detect legacy schema by presence of `slide_type` on any slide."""
    slides = data.get("slides", [])
    if not slides:
        return False
    first = slides[0]
    return "slide_type" in first and "layout_family" not in first


def _download_hero(url: str, slide_n: int) -> str | None:
    if not url:
        return None
    HERO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dest = HERO_CACHE_DIR / f"hero_{slide_n:02d}.jpg"
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
