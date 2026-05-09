"""Weekly newsletter cron entrypoint — Monday 06:00 WITA on Pro.

Usage:
    cd ~/Desktop/nuzantara/apps/backend-rag
    source .venv/bin/activate
    PYTHONPATH=. python -m backend.services.newsletter.newsletter_cli

Environment
-----------
NEWSLETTER_RECIPIENTS   comma-separated email list (fallback if no recipients_fn
                        wire-up is available; primarily for bootstrap / dev).
NOTIFICATIONS_EMAIL_URL override internal endpoint (default localhost:8000).
NOTIFICATIONS_API_KEY   override internal X-API-Key (default REDACTED-ROTATED-KEY).

Exit codes:
    0  sent (even if 0 recipients — log-only)
    1  config / pool init error
    2  empty roundup → nothing sent
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

import asyncpg

from backend.services.cognitive.repository import CognitiveRepository
from backend.services.intel.dossier_repository import IntelRepository
from backend.services.newsletter.builder import WeeklyRoundupBuilder
from backend.services.newsletter.publisher import NewsletterPublisher

logger = logging.getLogger("newsletter.cli")


def _hb(status: str, note: str = "") -> None:
    """Best-effort heartbeat for the Innervation Genoma sentinel.

    Writes ~/.organism/last_seen/wr2.newsletter.json. Never raises.
    """
    try:
        from datetime import datetime, timezone
        from pathlib import Path

        directory = Path.home() / ".organism" / "last_seen"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "wr2.newsletter.json"
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        payload = {"ts": ts, "status": status, "note": str(note)[:500]}
        tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
        tmp.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except Exception:  # noqa: BLE001
        pass


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )


def _recipients_from_env() -> list[str]:
    raw = os.environ.get("NEWSLETTER_RECIPIENTS", "")
    return [r.strip() for r in raw.split(",") if r.strip()]


async def run() -> int:
    _configure_logging()
    _hb("starting")
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL not set")
        _hb("fail", "DATABASE_URL not set")
        return 1

    try:
        pool = await asyncpg.create_pool(
            dsn, min_size=1, max_size=2, command_timeout=60,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("pool init failed: %s", exc, exc_info=True)
        _hb("fail", f"pool init {type(exc).__name__}")
        return 1

    try:
        intel_repo = IntelRepository(db_pool=pool)
        cognitive_repo = CognitiveRepository(db_pool=pool)

        builder = WeeklyRoundupBuilder(
            intel_repo=intel_repo, cognitive_repo=cognitive_repo,
        )
        content = await builder.build()

        recipients = _recipients_from_env()
        publisher = NewsletterPublisher()
        result = await publisher.send_roundup(content, recipients)

        sys.stdout.write(json.dumps({
            "week_of": result.week_of.isoformat(),
            "recipients_attempted": result.recipients_attempted,
            "recipients_sent": result.recipients_sent,
            "recipients_failed": result.recipients_failed,
            "subject": result.subject,
            "skipped": result.skipped,
            "skip_reason": result.skip_reason,
            "dossiers_in_roundup": len(content.dossiers),
            "theses_in_roundup": len(content.theses),
            "brief_included": content.brief is not None,
        }, default=str) + "\n")

        if result.skipped and result.skip_reason == "empty_roundup":
            _hb("warning", "empty_roundup")
            return 2
        _hb("ok", f"sent={result.recipients_sent}")
        return 0
    except Exception as exc:  # noqa: BLE001
        _hb("fail", f"exc={type(exc).__name__}")
        raise
    finally:
        await pool.close()


def main() -> None:
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
