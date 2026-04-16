"""
Mata Garuda — Manual War Room → bridge:outbound publisher.

Reads War Room output files (canva_pending.json + claude_slides.json) and
publishes one `intel.article_ready` envelope to Redis stream
`bridge:outbound`, where the bridge push worker (nerve.py) reads it and
POSTs it to Fly's `/api/bridge/ingest/article` endpoint.

This is a **manual CLI tool** — run it once per War Room cycle after FASE 5
(delivery) completes.

Why manual: War Room is entirely file-based with a human-in-the-loop
(Canva application step requires Zero on Claude Desktop). There is no
automated "article published" signal. Wiring an auto-publisher would be
code that never fires. A manual tool that Zero invokes is honest.

Note on stream naming: the Phase 1 audit (PHASE1_SINAPSI_STATUS_2026-04-16.md)
called this stream `intel:articles`, but the bridge push consumer
(`nerve.py::push_once`) reads from `bridge:outbound` (the canonical name in
config.py). We publish to `bridge:outbound` so the envelope actually flows
to Fly. The audit's `intel:articles` is the same conceptual stream —
nomenclature drift, not architectural drift.

Usage:
    cd apps/mata-garuda
    PYTHONPATH=. .venv/bin/python -m mata_garuda.tools.intel_publisher

    # Explicit paths:
    PYTHONPATH=. .venv/bin/python -m mata_garuda.tools.intel_publisher \
        --canva ../war-room/output/canva/canva_pending.json \
        --slides ../war-room/output/strategy/claude_slides.json

    # Dry-run (shows envelope, no Redis write):
    PYTHONPATH=. .venv/bin/python -m mata_garuda.tools.intel_publisher --dry-run

Reference: docs/PHASE1_SINAPSI_STATUS_2026-04-16.md open item P0-3.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from mata_garuda.bridge.envelope import Envelope
from mata_garuda.config import STREAM_BRIDGE_OUTBOUND

logger = logging.getLogger("mata_garuda.tools.intel_publisher")

WAR_ROOM_ROOT = Path(os.environ.get(
    "WAR_ROOM_ROOT",
    os.path.expanduser("~/Desktop/nuzantara/apps/war-room"),
))
DEFAULT_CANVA = WAR_ROOM_ROOT / "output" / "canva" / "canva_pending.json"
DEFAULT_SLIDES = WAR_ROOM_ROOT / "output" / "strategy" / "claude_slides.json"


def _load_json(path: Path) -> Optional[dict[str, Any]]:
    if not path.exists():
        logger.error("File not found: %s", path)
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in %s: %s", path, e)
        return None


def _extract_tags(slides: list[dict[str, Any]], caption: str) -> list[str]:
    """Extract tags from instagram caption hashtags."""
    tags: list[str] = []
    for word in caption.split():
        if word.startswith("#") and len(word) > 1:
            tags.append(word.lstrip("#").lower())
    return tags[:10]


def _build_content_md(slides: list[dict[str, Any]]) -> str:
    """Assemble slides into a minimal markdown body."""
    parts: list[str] = []
    for s in slides:
        headline = s.get("headline", "")
        body = s.get("body") or s.get("subhead") or ""
        if s.get("is_cover"):
            parts.append(f"# {headline}\n\n{body}")
        else:
            parts.append(f"## {headline}\n\n{body}")
    return "\n\n---\n\n".join(parts)


def build_envelope(
    canva: dict[str, Any],
    slides_data: dict[str, Any],
) -> Envelope:
    """Build an intel.article_ready envelope from War Room output."""
    slides = slides_data.get("slides", [])
    caption = canva.get("instagram_caption") or slides_data.get("instagram_caption") or ""
    topic = canva.get("topic") or slides_data.get("topic") or "untitled"

    slug = topic.lower().replace(" ", "-").replace(":", "")[:80]
    tags = _extract_tags(slides, caption)
    content_md = _build_content_md(slides)

    return Envelope(
        type="intel.article_ready",
        source="war_room",
        priority=2,
        payload={
            "article_id": str(uuid4()),
            "title": topic,
            "slug": slug,
            "content_md": content_md,
            "tags": tags,
            "slides_count": canva.get("slides_count", len(slides)),
            "instagram_caption": caption,
            "canva_design_id": canva.get("design_id"),
            "canva_design_url": canva.get("design_url"),
            "tone": canva.get("tone") or slides_data.get("tone"),
            "source_ids": [],
        },
    )


def publish_to_redis(envelope: Envelope, stream: str = STREAM_BRIDGE_OUTBOUND) -> str:
    """XADD the envelope to the Redis stream. Returns the stream entry ID."""
    fields = envelope.to_redis_dict()
    args = ["redis-cli", "XADD", stream, "*"]
    for k, v in fields.items():
        args.extend([k, v])
    result = subprocess.run(args, capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        raise RuntimeError(f"redis-cli XADD failed: {result.stderr.strip()}")
    return result.stdout.strip()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Publish War Room article to intel:articles Redis stream",
    )
    parser.add_argument(
        "--canva", type=Path, default=DEFAULT_CANVA,
        help="Path to canva_pending.json",
    )
    parser.add_argument(
        "--slides", type=Path, default=DEFAULT_SLIDES,
        help="Path to claude_slides.json",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show envelope but don't publish to Redis",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    canva = _load_json(args.canva)
    slides_data = _load_json(args.slides)
    if canva is None or slides_data is None:
        return 1

    envelope = build_envelope(canva, slides_data)

    if args.dry_run:
        print(json.dumps(envelope.model_dump(), indent=2, ensure_ascii=False))
        logger.info("DRY RUN — not publishing to Redis")
        return 0

    entry_id = publish_to_redis(envelope)
    logger.info(
        "Published to %s: entry_id=%s article_id=%s title=%r",
        STREAM_BRIDGE_OUTBOUND,
        entry_id,
        envelope.payload["article_id"],
        envelope.payload["title"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
