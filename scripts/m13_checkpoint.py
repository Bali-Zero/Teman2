#!/usr/bin/env python3
"""Daily 09:00 WITA — if Loop day is 30/60/90, trigger formal checkpoint."""
from __future__ import annotations

import logging
import os
import sys
from datetime import date
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("sota.m13.checkpoint")

LOOP_START_FILE = (
    _REPO / "research" / "sota-social-2026-v1" / ".loop_start_date"
)


def main() -> int:
    if not LOOP_START_FILE.is_file():
        logger.info("loop not started yet")
        return 0
    start_date = date.fromisoformat(LOOP_START_FILE.read_text().strip())
    days = (date.today() - start_date).days
    if days not in (30, 60, 90):
        return 0

    logger.info("Loop day %d — triggering checkpoint", days)
    report_path = (
        _REPO / "research" / "sota-social-2026-v1" / f"checkpoint_day_{days}.md"
    )
    report_path.write_text(
        f"# SOTA Checkpoint — Loop Day {days}\n\n"
        f"Date: {date.today().isoformat()}\n\n"
        f"## Deliverables for this checkpoint\n"
        f"- Review of last {days} days deltas (see weekly reports)\n"
        f"- Go/Pivot/Kill decision per channel\n"
        f"- Update playbook version if needed\n\n"
        f"## Decision request (Telegram to Zero)\n"
        f"Reply with `/checkpoint day{days} decision=GO|PIVOT|KILL channel=<name>`\n",
        encoding="utf-8",
    )

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if token:
        # Plain text (no Markdown) per Fase 0 lesson #8.
        import urllib.parse
        import urllib.request

        text = (
            f"[SOTA Checkpoint Day {days}] formal review needed. "
            f"File: research/sota-social-2026-v1/checkpoint_day_{days}.md. "
            f"Reply GO/PIVOT/KILL per channel."
        )
        try:
            urllib.request.urlopen(
                f"https://api.telegram.org/bot{token}/sendMessage",
                urllib.parse.urlencode(
                    {
                        "chat_id": os.environ.get(
                            "TELEGRAM_OWNER_CHAT_ID", "1125336968"
                        ),
                        "text": text,
                    }
                ).encode(),
                timeout=10,
            )
        except Exception as e:
            logger.warning("telegram send failed: %s", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
