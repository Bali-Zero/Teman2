"""In-process daily trigger for the internal newsletter digest.

Born 2026-07-15 to replace the Pro-side LaunchAgent
(``com.balizero.wr2.newsletter``, ``StartCalendarInterval`` 08:00 WITA):
that cron dispatches into Fly via ``fly ssh console -a nuzantara-rag -g api``
(see ``scripts/wr2-cron-wrapper.sh`` §1.5), and the ``FLY_API_TOKEN`` living
on Pro is an app-scoped deploy token — it can ``fly status`` but not
``fly ssh console`` (that needs org-level access), so the cron has been
armed-but-unable-to-fire (scar family #2, Esiste≠Armato) whenever Pro's
token doesn't happen to have the right scope. ``newsletter_cli.py`` already
documents that the whole run only ever executes *inside* the Fly ``api``
process — DATABASE_URL, NOTIFICATIONS_API_KEY, and the notifications
endpoint only exist there. Since that's already true, the natural fix is to
fire the trigger from *inside* that same process instead of ssh-ing into it
from outside: zero new secrets, zero cross-machine dependency, zero
`fly ssh` token-scope problem.

``nuzantara-rag`` is not the auto_stop-to-zero app the old AutonomousScheduler
comments warn about — ``fly.toml`` sets ``auto_stop_machines = 'off'`` /
``min_machines_running = 1`` (always-on), so a long-sleeping in-process task
is safe here in a way it would not be on a scale-to-zero app.

Design, mirroring the ``whatsapp_subscription_guardian`` live-path pattern
(service_initializer §10d) since the generic ``AutonomousScheduler`` engine
is dead in prod (necropsy 2026-07-14, ``autonomous_scheduler.py`` module
docstring):

- Standalone ``asyncio`` loop started directly from ``service_initializer``
  (the live init path), NOT registered on the dead scheduler.
- Sleeps to the next wall-clock UTC target (default 00:00 UTC = 08:00 WITA)
  rather than a fixed interval-since-boot: a fixed 24h interval (the
  ``kg_incremental_builder`` convention) would drift away from "08:00 WITA"
  every time the process restarts (deploys happen several times a day on
  this repo). Wall-clock alignment recomputed after every run stays pinned
  to the target time regardless of restarts.
- Reuses the scheduler's Redis leader-lock helper for cross-machine dedupe
  (``min_machines_running=1`` makes a genuine split-brain unlikely, but a
  rolling deploy can briefly run two machines — cheap insurance, same
  reasoning as the WA guardian).
- Reuses ``newsletter_cli._run_daily`` / ``_recipients_from_env`` verbatim
  instead of re-implementing the send path (this is the exact path verified
  live via ``fly ssh console -C "python -m ...newsletter_cli --daily"``,
  2026-07-15, ``recipients_sent:1``).
- Persists the verdict to ``system_settings`` (key
  ``newsletter_daily_task_last``), the same durable-receptor pattern the WA
  guardian uses — Telegram/log output is a view nobody may be reading; the
  disk-state row is queryable from any session with one SELECT.

Kill switch: ``NEWSLETTER_DAILY_TASK_ENABLED=false``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TARGET_HOUR_UTC = 0  # 00:00 UTC == 08:00 WITA
DEFAULT_TARGET_MINUTE_UTC = 0
_LOCK_TASK_NAME = "newsletter_daily_task"
_SETTINGS_KEY = "newsletter_daily_task_last"


def _seconds_until_next_utc_target(
    hour: int,
    minute: int,
    now: datetime | None = None,
) -> float:
    """Seconds from ``now`` (UTC) until the next occurrence of ``hour:minute`` UTC.

    Pure function — no I/O, no sleeping — so it is unit-testable without an
    event loop. If ``now`` is already past today's target, rolls to tomorrow.
    """
    now = now or datetime.now(tz=timezone.utc)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def _persist_state(db_pool: Any, result: dict[str, Any]) -> None:
    if db_pool is None:
        return
    try:
        await db_pool.execute(
            """
            INSERT INTO system_settings (key, value, updated_at)
            VALUES ($1, $2, now())
            ON CONFLICT (key) DO UPDATE
                SET value = EXCLUDED.value, updated_at = now()
            """,
            _SETTINGS_KEY,
            json.dumps(result, default=str),
        )
    except Exception as e:  # persistence must never kill the loop
        logger.warning("[newsletter-daily-task] state persist failed: %s", e)


async def _run_once(db_pool: Any, subject_prefix: str) -> dict[str, Any]:
    """One digest send, reusing newsletter_cli's own send path verbatim."""
    from backend.services.newsletter.newsletter_cli import (
        _recipients_from_env,
        _run_daily,
    )

    now = datetime.now(tz=timezone.utc)
    recipients = _recipients_from_env()
    try:
        rc = await _run_daily(db_pool, recipients, subject_prefix)
        result = {"ran_at": now.isoformat(), "exit_code": rc, "ok": rc in (0, 2)}
    except Exception as e:  # the loop must survive anything (scar family #8)
        logger.error("[newsletter-daily-task] send crashed: %s", e)
        result = {"ran_at": now.isoformat(), "exit_code": None, "ok": False, "error": str(e)}
    logger.info("[newsletter-daily-task] cycle done: %s", json.dumps(result))
    return result


async def _daily_loop(
    db_pool: Any,
    target_hour_utc: int,
    target_minute_utc: int,
    subject_prefix: str,
) -> None:
    from backend.services.misc.autonomous_scheduler import _acquire_task_lock

    await asyncio.sleep(30)  # let the app finish booting
    while True:
        try:
            sleep_seconds = _seconds_until_next_utc_target(target_hour_utc, target_minute_utc)
            logger.info(
                "[newsletter-daily-task] next send in %.0fs (target %02d:%02d UTC)",
                sleep_seconds,
                target_hour_utc,
                target_minute_utc,
            )
            await asyncio.sleep(sleep_seconds)

            # Lock TTL covers the target window (23h) so a rolling-deploy
            # overlap of two machines cannot double-send the same day.
            if await _acquire_task_lock(_LOCK_TASK_NAME, ttl_seconds=23 * 3600):
                result = await _run_once(db_pool, subject_prefix)
                await _persist_state(db_pool, result)
            else:
                logger.debug("[newsletter-daily-task] another worker holds the lock")
        except asyncio.CancelledError:
            raise
        except Exception as e:  # the loop must survive anything
            logger.error("[newsletter-daily-task] loop iteration crashed: %s", e)
            # Avoid a tight crash loop if something upstream is persistently broken.
            await asyncio.sleep(60)


def start_newsletter_daily_task(
    db_pool: Any = None,
    target_hour_utc: int = DEFAULT_TARGET_HOUR_UTC,
    target_minute_utc: int = DEFAULT_TARGET_MINUTE_UTC,
    subject_prefix: str = "",
) -> asyncio.Task | None:
    """Spawn the daily-digest loop on the running event loop (kill-switch aware)."""
    if os.environ.get("NEWSLETTER_DAILY_TASK_ENABLED", "true").lower() in {
        "false",
        "0",
        "no",
    }:
        logger.info("[newsletter-daily-task] disabled via NEWSLETTER_DAILY_TASK_ENABLED")
        return None
    task = asyncio.get_event_loop().create_task(
        _daily_loop(db_pool, target_hour_utc, target_minute_utc, subject_prefix),
        name="newsletter_daily_task",
    )
    logger.info(
        "✅ Newsletter daily-digest task started (target %02d:%02d UTC)",
        target_hour_utc,
        target_minute_utc,
    )
    return task
