"""Daily 09:00 WITA — if Loop day is 30/60/90, trigger formal checkpoint.

Invoked by `com.balizero.sota.m13-checkpoint.plist` through
`scripts/wr2-cron-wrapper.sh backend.services.sota_loop.m13_checkpoint`.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import date
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sota.m13.checkpoint")


def _repo_root() -> Path:
    env = os.environ.get("NUZANTARA_REPO_ROOT")
    if env:
        return Path(env)
    for parent in Path(__file__).resolve().parents:
        if (parent / "apps").is_dir() and (parent / "research").is_dir():
            return parent
    return Path(__file__).resolve().parents[5]


def _organism_heartbeat(status: str, note: str = "") -> None:
    try:
        scripts_dir = _repo_root() / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        from lib.heartbeat import organism_heartbeat

        organism_heartbeat("sota.m13_checkpoint", status, note)
    except Exception:
        pass


def main() -> int:
    repo = _repo_root()
    loop_start_file = repo / "research" / "sota-social-2026-v1" / ".loop_start_date"

    if not loop_start_file.is_file():
        logger.info("loop not started yet")
        return 0
    start_date = date.fromisoformat(loop_start_file.read_text().strip())
    days = (date.today() - start_date).days
    if days not in (30, 60, 90):
        return 0

    logger.info("Loop day %d — triggering checkpoint", days)
    report_path = repo / "research" / "sota-social-2026-v1" / f"checkpoint_day_{days}.md"
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
                        "chat_id": os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968"),
                        "text": text,
                    }
                ).encode(),
                timeout=10,
            )
        except Exception as e:
            logger.warning("telegram send failed: %s", e)
    return 0


if __name__ == "__main__":
    _organism_heartbeat("starting", "checkpoint run started")
    try:
        result = main()
    except KeyboardInterrupt:
        _organism_heartbeat("degraded", "keyboard interrupt")
        raise
    except Exception as exc:
        _organism_heartbeat("error", f"crashed: {exc}")
        raise
    _organism_heartbeat("ok" if result == 0 else "error", f"rc={result}")
    sys.exit(result)
