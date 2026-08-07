"""Newsletter cron entrypoint — weekly (Monday) or daily (--daily).

Runs INSIDE the Fly `api` process (dispatched remotely from the Pro
scheduler via ``scripts/wr2-cron-wrapper.sh``, ``fly ssh console -g api``):
DATABASE_URL, NOTIFICATIONS_API_KEY, and the notifications endpoint only
exist there. For a manual/local run against a machine that already has all
three set, the usage below still applies.

Usage:
    cd ~/nuzantara/apps/backend-rag
    source .venv/bin/activate
    PYTHONPATH=. python -m backend.services.newsletter.newsletter_cli            # weekly roundup
    PYTHONPATH=. python -m backend.services.newsletter.newsletter_cli --daily    # internal daily digest

Environment
-----------
NEWSLETTER_RECIPIENTS   comma-separated email list. Defaults to
                        ``zero@balizero.com`` when unset (2026-07-14 —
                        the newsletter was previously a permanent no-op,
                        "no_recipients", because this was never set).
NOTIFICATIONS_EMAIL_URL override internal endpoint (default 127.0.0.1:8080 —
                        matches fly.toml's `internal_port`/uvicorn `--port`;
                        127.0.0.1:8000 was a stale default that made every
                        send fail with connection-refused, fixed 2026-07-14).
NOTIFICATIONS_API_KEY   internal X-API-Key (required; no default — rotated key).
NEWSLETTER_SUBJECT_PREFIX  optional prefix prepended to the subject (e.g. "[TEST] ").

Exit codes:
    0  sent (even if 0 recipients — log-only)
    1  config / pool init error
    2  empty roundup/digest → nothing sent (includes "already sent today")

Idempotency (daily digest only, added 2026-08-07)
--------------------------------------------------
Two independent schedulers can call ``_run_daily`` for the same UTC calendar
day: the legacy Pro LaunchAgent (``com.balizero.wr2.newsletter``, disarmed
2026-08-07 but this guard survives it deliberately — HOME-fork drift, scar
family #1, can silently reload a plist) via this CLI's ``--daily`` path, and
the in-process ``daily_task.py`` loop (``_run_once`` calls ``_run_daily``
directly). Neither ``send_daily_digest`` nor ``build_daily`` de-duplicates —
confirmed live 2026-08-07: the old cron fired 00:00 UTC and the in-process
loop fired 18:30 UTC the same UTC day, ~5.5h apart, both against a 48h
lookback window with no "already included" filter, so the two runs' item
sets overlap almost entirely. ``_already_sent_today``/``_mark_sent_today``
close that gap using the SAME state mechanism ``daily_task.py`` already uses
for its own receipt (``system_settings``, key/value/updated_at) — no new
lock/queue invented. The claim is written BEFORE the send attempt (not
after) so a slow first sender still wins the race against a second
invocation that starts moments later; a caller that finds the day already
claimed skips without touching the network.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import date, datetime, timezone

import asyncpg

from backend.services.cognitive.repository import CognitiveRepository
from backend.services.intel.dossier_repository import IntelRepository
from backend.services.newsletter.builder import DailyDigestBuilder, WeeklyRoundupBuilder
from backend.services.newsletter.publisher import NewsletterPublisher

logger = logging.getLogger("newsletter.cli")

DEFAULT_RECIPIENT = "zero@balizero.com"

# system_settings key recording the last UTC calendar day the daily digest
# was actually claimed for sending. Distinct from daily_task.py's
# "newsletter_daily_task_last" (that one records ITS OWN last cycle outcome,
# written by only one caller); this key is the cross-caller dedup guard both
# the CLI path and the in-process loop consult and update.
_DAILY_SENT_KEY = "newsletter_daily_digest_last_sent_day"


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


async def _already_sent_today(pool: asyncpg.Pool, day: date) -> bool:
    """True if the daily digest for ``day`` was already claimed by some caller.

    Read-only probe — never raises past the caller. On any DB error, returns
    False (fail-open to "not yet sent"): a transient read failure must not
    silently swallow a legitimate send (scar family #8 — never crash/starve
    a task over a flaky connection). The real backstop against a genuine
    duplicate under a DB outage is that BOTH schedulers would need to be
    invoked within the outage window, same as before this guard existed.
    """
    try:
        row = await pool.fetchrow("SELECT value FROM system_settings WHERE key = $1", _DAILY_SENT_KEY)
    except Exception as exc:
        logger.warning("[newsletter] idempotency check failed (%s) — proceeding as not-sent", exc)
        return False
    if row is None or row["value"] is None:
        return False
    try:
        return json.loads(row["value"]).get("day") == day.isoformat()
    except (TypeError, ValueError, AttributeError):
        return False


async def _mark_sent_today(pool: asyncpg.Pool, day: date) -> bool:
    """Atomically claim ``day`` for sending. Returns True iff THIS call won.

    Uses the same INSERT ... ON CONFLICT DO UPDATE upsert shape as
    ``daily_task._persist_state`` (system_settings key/value/updated_at) but
    adds a WHERE guard so a second caller racing shortly after does not
    silently re-claim (and thus re-permit) an already-claimed day: the
    UPDATE only fires — and RETURNING only yields a row — when the stored
    value actually differs from what we're about to write.
    """
    try:
        row = await pool.fetchrow(
            """
            INSERT INTO system_settings (key, value, updated_at)
            VALUES ($1, $2, now())
            ON CONFLICT (key) DO UPDATE
                SET value = EXCLUDED.value, updated_at = now()
                WHERE system_settings.value IS DISTINCT FROM EXCLUDED.value
            RETURNING value
            """,
            _DAILY_SENT_KEY,
            json.dumps({"day": day.isoformat()}),
        )
    except Exception as exc:
        logger.warning("[newsletter] idempotency claim failed (%s) — sending unguarded", exc)
        return True  # never block a real send over a persistence hiccup
    return row is not None


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


def _write_daily_skip(day: date, *, items_in_digest: int, scarce: bool, skip_reason: str) -> None:
    """Emit the same JSON line shape as a real send, for a pre-send skip."""
    sys.stdout.write(
        json.dumps(
            {
                "mode": "daily",
                "day": day.isoformat(),
                "recipients_attempted": 0,
                "recipients_sent": 0,
                "recipients_failed": 0,
                "subject": "",
                "skipped": True,
                "skip_reason": skip_reason,
                "items_in_digest": items_in_digest,
                "scarce": scarce,
            },
            default=str,
        )
        + "\n"
    )


async def _run_daily(pool: asyncpg.Pool, recipients: list[str], subject_prefix: str) -> int:
    today = datetime.now(timezone.utc).date()
    if await _already_sent_today(pool, today):
        logger.warning(
            "[newsletter] daily digest for %s already sent by another invocation "
            "— skipping (idempotency guard)",
            today.isoformat(),
        )
        _write_daily_skip(today, items_in_digest=0, scarce=False, skip_reason="already_sent_today")
        return 2

    intel_repo = IntelRepository(db_pool=pool)
    cognitive_repo = CognitiveRepository(db_pool=pool)

    builder = DailyDigestBuilder(
        intel_repo=intel_repo,
        cognitive_repo=cognitive_repo,
    )
    content = await builder.build_daily()

    # Claim the day BEFORE sending, not after: a second invocation starting
    # while the first is still mid-flight on its per-recipient HTTP loop
    # must see the day already taken. Only claim when there is something to
    # actually send — an empty-digest or no-recipients run must not burn
    # the day for a later, real attempt (both are already no-ops for the
    # recipient, so there's nothing to duplicate).
    if not content.is_empty and recipients:
        if not await _mark_sent_today(pool, content.day):
            logger.warning(
                "[newsletter] daily digest for %s claimed by a concurrent invocation "
                "— skipping",
                content.day.isoformat(),
            )
            _write_daily_skip(
                content.day,
                items_in_digest=len(content.items),
                scarce=content.scarce,
                skip_reason="already_sent_today",
            )
            return 2

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
