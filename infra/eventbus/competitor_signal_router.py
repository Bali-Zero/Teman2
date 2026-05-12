#!/usr/bin/env python3
"""W3.5 — Competitor signal router.

Reads latest monthly competitor-monitor digest (markdown file) and emits structured
intel.collected events tagged source='competitor-monitor', so wr2-topic-selector
can score them as topic candidates (via the event-driven path post-W1).

Triggered weekly by cron (Mon 06:30 WITA, after Reflexion Sun 02:30).
NO ongoing daemon — single-shot script.
"""
from __future__ import annotations
import os
import sys
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from eventbus import publish

DIGEST_DIR = Path.home() / "Desktop/nuzantara/research/competitive"
LOG_PATH = Path.home() / "logs" / "competitor-signal-router.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()],
)
log = logging.getLogger("competitor-signal-router")


def find_latest_digest() -> Path | None:
    if not DIGEST_DIR.exists():
        return None
    candidates = sorted(DIGEST_DIR.glob("*-digest.md"))
    return candidates[-1] if candidates else None


def parse_action_items(md: str) -> list[dict]:
    """Extract '## Action items' bullets as actionable signals."""
    m = re.search(r"##\s+Action items.*?\n(.+?)(?=\n##|\Z)", md, re.DOTALL | re.IGNORECASE)
    if not m:
        return []
    block = m.group(1)
    items = []
    for line in block.split("\n"):
        line = line.strip()
        if line.startswith("- [ ]") or line.startswith("- ["):
            text = re.sub(r"^- \[.\]\s*", "", line).strip()
            if text:
                items.append({"text": text, "raw": line})
    return items


def main() -> int:
    digest = find_latest_digest()
    if not digest:
        log.warning("no competitor digest found in %s", DIGEST_DIR)
        return 0

    log.info("processing digest: %s", digest)
    md = digest.read_text(errors="replace")
    actions = parse_action_items(md)
    log.info("found %d action items", len(actions))

    if not actions:
        return 0

    n_emit = 0
    digest_date = digest.stem.split("-")[0:2]
    digest_tag = "-".join(digest_date) if digest_date else "unknown"

    for idx, action in enumerate(actions):
        try:
            eid = publish(
                "intel.collected",
                {
                    "source": "competitor-monitor",
                    "citation_or_url": f"competitor-digest:{digest.name}#action-{idx}",
                    "raw_payload": {
                        "title": action["text"][:200],
                        "entity": "competitor-monitor",
                        "date": digest_tag,
                        "jurisdiction": "competitive",
                        "kind": "competitor_action_item",
                        "raw_line": action["raw"],
                    },
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "agent_name": "competitor-signal-router",
                },
                emitted_by="competitor-signal-router",
            )
            n_emit += 1
            log.info("emitted %s: %s", eid, action["text"][:80])
        except Exception as e:
            log.exception("emit failed for action %d: %s", idx, e)

    log.info("done. emitted=%d", n_emit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
