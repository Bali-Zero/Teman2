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
NOTIFICATIONS_API_KEY   override internal X-API-Key (default zantara-secret-2024).

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
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL not set")
        return 1

    try:
        pool = await asyncpg.create_pool(
            dsn, min_size=1, max_size=2, command_timeout=60,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("pool init failed: %s", exc, exc_info=True)
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
            return 2
        return 0
    finally:
        await pool.close()


def main() -> None:
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
