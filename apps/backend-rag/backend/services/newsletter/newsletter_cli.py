"""Newsletter cron entrypoint — weekly (Monday) or daily (--daily), on Pro.

Usage:
    cd ~/Desktop/nuzantara/apps/backend-rag
    source .venv/bin/activate
    PYTHONPATH=. python -m backend.services.newsletter.newsletter_cli            # weekly roundup
    PYTHONPATH=. python -m backend.services.newsletter.newsletter_cli --daily    # internal daily digest

Environment
-----------
NEWSLETTER_RECIPIENTS   comma-separated email list. Defaults to
                        ``zero@balizero.com`` when unset (2026-07-14 —
                        the newsletter was previously a permanent no-op,
                        "no_recipients", because this was never set).
NOTIFICATIONS_EMAIL_URL override internal endpoint (default localhost:8000).
NOTIFICATIONS_API_KEY   internal X-API-Key (required; no default — rotated key).
NEWSLETTER_SUBJECT_PREFIX  optional prefix prepended to the subject (e.g. "[TEST] ").

Exit codes:
    0  sent (even if 0 recipients — log-only)
    1  config / pool init error
    2  empty roundup/digest → nothing sent
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys

import asyncpg

from backend.services.cognitive.repository import CognitiveRepository
from backend.services.intel.dossier_repository import IntelRepository
from backend.services.newsletter.builder import DailyDigestBuilder, WeeklyRoundupBuilder
from backend.services.newsletter.publisher import NewsletterPublisher

logger = logging.getLogger("newsletter.cli")

DEFAULT_RECIPIENT = "zero@balizero.com"


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
    except Exception:
        pass


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )


def _recipients_from_env() -> list[str]:
    raw = os.environ.get("NEWSLETTER_RECIPIENTS", "")
    recipients = [r.strip() for r in raw.split(",") if r.strip()]
    if not recipients:
        # 2026-07-14: this was previously always empty in prod (env never
        # set) → send_roundup/send_daily_digest always skipped with
        # "no_recipients". Default to the internal owner so the cron is
        # never a silent no-op; NEWSLETTER_RECIPIENTS still overrides.
        recipients = [DEFAULT_RECIPIENT]
    return recipients


async def _run_weekly(pool: asyncpg.Pool, recipients: list[str], subject_prefix: str) -> int:
    intel_repo = IntelRepository(db_pool=pool)
    cognitive_repo = CognitiveRepository(db_pool=pool)

    builder = WeeklyRoundupBuilder(
        intel_repo=intel_repo,
        cognitive_repo=cognitive_repo,
    )
    content = await builder.build()

    publisher = NewsletterPublisher()
    result = await publisher.send_roundup(content, recipients, subject_prefix=subject_prefix)

    sys.stdout.write(
        json.dumps(
            {
                "mode": "weekly",
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
            },
            default=str,
        )
        + "\n"
    )

    if result.skipped and result.skip_reason == "empty_roundup":
        return 2
    return 0


async def _run_daily(pool: asyncpg.Pool, recipients: list[str], subject_prefix: str) -> int:
    intel_repo = IntelRepository(db_pool=pool)
    cognitive_repo = CognitiveRepository(db_pool=pool)

    builder = DailyDigestBuilder(
        intel_repo=intel_repo,
        cognitive_repo=cognitive_repo,
    )
    content = await builder.build_daily()

    publisher = NewsletterPublisher()
    result = await publisher.send_daily_digest(content, recipients, subject_prefix=subject_prefix)

    sys.stdout.write(
        json.dumps(
            {
                "mode": "daily",
                "day": result.day.isoformat(),
                "recipients_attempted": result.recipients_attempted,
                "recipients_sent": result.recipients_sent,
                "recipients_failed": result.recipients_failed,
                "subject": result.subject,
                "skipped": result.skipped,
                "skip_reason": result.skip_reason,
                "items_in_digest": len(content.items),
                "scarce": content.scarce,
            },
            default=str,
        )
        + "\n"
    )

    if result.skipped and result.skip_reason == "empty_digest":
        return 2
    return 0


async def run(*, daily: bool = False, subject_prefix: str = "") -> int:
    _configure_logging()
    _hb("starting")
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL not set")
        _hb("fail", "DATABASE_URL not set")
        return 1

    try:
        pool = await asyncpg.create_pool(
            dsn,
            min_size=1,
            max_size=2,
            command_timeout=60,
        )
    except Exception as exc:
        logger.error("pool init failed: %s", exc, exc_info=True)
        _hb("fail", f"pool init {type(exc).__name__}")
        return 1

    try:
        recipients = _recipients_from_env()
        if daily:
            rc = await _run_daily(pool, recipients, subject_prefix)
        else:
            rc = await _run_weekly(pool, recipients, subject_prefix)

        if rc == 2:
            _hb("warning", "empty")
        else:
            _hb("ok", f"mode={'daily' if daily else 'weekly'}")
        return rc
    except Exception as exc:
        _hb("fail", f"exc={type(exc).__name__}")
        raise
    finally:
        await pool.close()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--daily",
        action="store_true",
        help="Send the internal daily digest instead of the weekly roundup.",
    )
    parser.add_argument(
        "--subject-prefix",
        default=os.environ.get("NEWSLETTER_SUBJECT_PREFIX", ""),
        help='Prepended to the subject, e.g. "[TEST] " for a manual test send.',
    )
    return parser.parse_args(argv)


def main() -> None:
    args = _parse_args(sys.argv[1:])
    sys.exit(asyncio.run(run(daily=args.daily, subject_prefix=args.subject_prefix)))


if __name__ == "__main__":
    main()
