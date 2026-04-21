"""EmailHealthMonitor — retries, stale detection, escalation, daily report.

Runs on a cron schedule via the ``/api/cron/notifiers/email-health``
endpoint (every 30 minutes from Air). Reads ``email_send_log`` written by
``email_audit.py`` and:

1. :meth:`check_and_retry_failed_emails` — re-attempts rows with
   ``status='failed'`` and ``retry_after<NOW()`` and ``attempt_number<3``.
   Uses ``SELECT ... FOR UPDATE SKIP LOCKED`` so two concurrent cron
   passes don't both try to retry the same row.
2. :meth:`check_stale_sendings` — flips rows stuck at ``status='sending'``
   for more than 10 minutes to ``failed`` so the retry path picks them up.
   Guards against a worker crashing mid-send.
3. :meth:`escalate_unrecoverable` — any row with ``status='failed'``
   and ``attempt_number>=3`` is marked ``escalated`` and the full list
   is paged to the owner via Telegram.
4. :meth:`generate_daily_report` — once per 24h sends a summary of counts
   per ``email_type`` × ``status`` to Telegram.

The monitor does NOT itself send emails in the critical path — it calls
back into the original service's send path via a minimal retry helper
scoped to brevo-only for now (retrying through the full Brevo→Zoho chain
would be re-entrant with the service that just recorded the failure).
"""

from __future__ import annotations

import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from backend.services.notifications.email_http import get_email_client

if TYPE_CHECKING:
    import asyncpg

logger = logging.getLogger(__name__)

_OWNER_CHAT_ID: str = os.getenv("TELEGRAM_OWNER_CHAT_ID", "1125336968")
_EMAIL_API_URL = os.getenv(
    "INTERNAL_EMAIL_API_URL",
    "https://nuzantara-rag.fly.dev/api/notifications/send-email",
)
_EMAIL_API_KEY = os.getenv("NUZANTARA_API_KEY", "")

STALE_SENDING_THRESHOLD = timedelta(minutes=10)
MAX_ATTEMPTS = 3
_DAILY_REPORT_STATE_KEY = "email_health_monitor_last_report_utc"


class EmailHealthMonitor:
    """Retry + escalate + report health of outbound email delivery."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool

    # ------------------------------------------------------------------
    # 1. Retry failed rows
    # ------------------------------------------------------------------

    async def check_and_retry_failed_emails(self) -> dict[str, int]:
        """Retry rows with status='failed' whose retry_after has elapsed.

        Uses SKIP LOCKED so concurrent cron passes don't collide.
        Returns stats: {"considered": N, "retried": N, "succeeded": N,
        "failed_again": N}.
        """
        stats = {"considered": 0, "retried": 0, "succeeded": 0, "failed_again": 0}

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, email_type, to_email, subject, practice_id,
                       client_id, attempt_number
                  FROM email_send_log
                 WHERE status = 'failed'
                   AND retry_after IS NOT NULL
                   AND retry_after <= NOW()
                   AND attempt_number < $1
                 ORDER BY retry_after ASC
                 LIMIT 50
                 FOR UPDATE SKIP LOCKED
                """,
                MAX_ATTEMPTS,
            )

            # Claim each row by flipping status away from 'failed' so a
            # parallel cron pass won't pick it up even after this tx commits.
            for row in rows:
                await conn.execute(
                    """
                    UPDATE email_send_log
                       SET status = 'retry_scheduled'
                     WHERE id = $1
                    """,
                    row["id"],
                )
                stats["considered"] += 1

        # Retry outside the claim transaction so we don't hold locks across
        # network I/O.
        for row in rows:
            stats["retried"] += 1
            succeeded = await self._retry_single(row)
            if succeeded:
                stats["succeeded"] += 1
            else:
                stats["failed_again"] += 1

        return stats

    async def _retry_single(self, row: Any) -> bool:
        """Re-attempt delivery for one email_send_log row.

        Inserts a new audit row for the retry attempt (attempt_number+1)
        so the timeline is preserved. The ORIGINAL row (previously
        claimed to ``status='retry_scheduled'``) is closed to the same
        terminal status as the new row so it doesn't accumulate as an
        orphan invisible to the dashboard. Returns True on success.
        """
        original_id = row["id"]
        attempt_n = row["attempt_number"] + 1

        async with self.db_pool.acquire() as conn:
            new_id = await conn.fetchval(
                """
                INSERT INTO email_send_log
                    (email_type, practice_id, client_id, to_email,
                     subject, status, attempt_number)
                VALUES ($1, $2, $3, $4, $5, 'sending', $6)
                RETURNING id
                """,
                row["email_type"],
                row["practice_id"],
                row["client_id"],
                row["to_email"],
                (row["subject"] or "")[:500],
                attempt_n,
            )

        # Retry using the same Brevo internal endpoint — we don't have
        # the original body cached (payload_cache is reserved for future
        # retention but not yet populated), so this is a best-effort
        # "synthesize a minimal retry notification" path.
        # The body simply explains this is an automated retry and points
        # to the original subject so the recipient has context.
        retry_body = (
            f"<p>This is an automated retry of a previously-failed email.</p>"
            f"<p><strong>Original subject:</strong> {(row['subject'] or '')[:200]}</p>"
            f"<p>If you did not expect this message or the original email arrived, "
            f"please disregard.</p>"
            f"<p><em>Retry attempt #{attempt_n} of {MAX_ATTEMPTS}</em></p>"
        )

        err_msg: str | None = None
        try:
            client = await get_email_client()
            resp = await client.post(
                _EMAIL_API_URL,
                headers={"X-API-Key": _EMAIL_API_KEY},
                json={
                    "to": row["to_email"],
                    "subject": f"[RETRY] {(row['subject'] or 'Bali Zero notification')[:480]}",
                    "body": retry_body,
                },
            )
            resp.raise_for_status()
        except Exception as e:
            err_msg = str(e)

        async with self.db_pool.acquire() as conn:
            if err_msg is None:
                # Close both the new retry row AND the original claim row
                # to 'sent' — the original row was sitting at
                # 'retry_scheduled' and would otherwise never reach a
                # terminal state, becoming dashboard-invisible bloat.
                await conn.execute(
                    """
                    UPDATE email_send_log
                       SET status = 'sent', provider = 'brevo',
                           sent_at = NOW(), retry_after = NULL
                     WHERE id = ANY($1::bigint[])
                    """,
                    [new_id, original_id],
                )
                return True

            # Failed again — compute next retry_after or None to escalate.
            from backend.services.notifications.email_audit import _RETRY_BACKOFF

            next_retry: datetime | None = None
            if attempt_n < len(_RETRY_BACKOFF) + 1 and attempt_n < MAX_ATTEMPTS:
                next_retry = datetime.now(tz=timezone.utc) + _RETRY_BACKOFF[attempt_n - 1]
            # Close the new retry row as 'failed' (it carries the new
            # attempt_number and next retry_after), AND close the original
            # claim row as 'failed' with NULL retry_after so it's treated
            # as already-escalated-to-successor — the new row is the one
            # the retry worker / escalator will now act on.
            await conn.execute(
                """
                UPDATE email_send_log
                   SET status = 'failed', provider = 'brevo',
                       error_message = $2, retry_after = $3
                 WHERE id = $1
                """,
                new_id,
                err_msg[:4000],
                next_retry,
            )
            await conn.execute(
                """
                UPDATE email_send_log
                   SET status = 'superseded',
                       error_message = 'superseded_by_retry',
                       retry_after = NULL
                 WHERE id = $1
                """,
                original_id,
            )
            return False

    # ------------------------------------------------------------------
    # 2. Stale-sending detection
    # ------------------------------------------------------------------

    async def check_stale_sendings(self) -> dict[str, int]:
        """Flip rows stuck at 'sending' for >10 min to 'failed'.

        Symptom of: worker crash, httpx connection timeout not raising,
        pod eviction during send. The retry worker will then re-attempt.
        """
        cutoff = datetime.now(tz=timezone.utc) - STALE_SENDING_THRESHOLD

        async with self.db_pool.acquire() as conn:
            updated = await conn.fetch(
                """
                UPDATE email_send_log
                   SET status = 'failed',
                       provider = 'unknown',
                       error_message = 'stale_sending: worker_crash_or_timeout',
                       retry_after = NOW() + INTERVAL '1 hour'
                 WHERE status = 'sending'
                   AND created_at < $1
                 RETURNING id
                """,
                cutoff,
            )

        count = len(updated)
        if count:
            logger.warning("EmailHealthMonitor: unstuck %d stale 'sending' rows", count)
        return {"unstuck": count}

    # ------------------------------------------------------------------
    # 3. Escalate unrecoverable
    # ------------------------------------------------------------------

    async def escalate_unrecoverable(self) -> dict[str, int]:
        """Escalate rows that can't recover via retry.

        Two categories, both marked ``escalated`` so they're paged once:

        - ``status='failed'`` AND ``attempt_number>=3`` — exhausted retry
          budget for retryable types.
        - ``status='failed'`` AND ``retry_after IS NULL`` AND
          ``attempt_number<3`` — non-resurrectable types (client-facing
          emails with personalized HTML / attachments). These never
          entered the retry queue because retrying with a stub body
          would be worse than alerting the owner for manual recovery.
        """
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, email_type, to_email, subject, practice_id,
                       client_id, attempt_number, error_message, created_at
                  FROM email_send_log
                 WHERE status = 'failed'
                   AND (
                         attempt_number >= $1
                      OR retry_after IS NULL
                   )
                 ORDER BY created_at ASC
                 LIMIT 50
                """,
                MAX_ATTEMPTS,
            )

            if not rows:
                return {"escalated": 0}

            ids = [r["id"] for r in rows]
            await conn.execute(
                """
                UPDATE email_send_log
                   SET status = 'escalated'
                 WHERE id = ANY($1::bigint[])
                """,
                ids,
            )

        # Build consolidated Telegram message
        lines = [
            f"⚠️ *Email escalation* — {len(rows)} unrecoverable message(s)",
            "",
        ]
        for r in rows[:15]:  # hard cap to avoid oversized Telegram message
            subj = (r["subject"] or "").strip()[:60]
            err = (r["error_message"] or "").strip()[:80]
            lines.append(
                f"• `{r['email_type']}` → `{r['to_email']}`\n"
                f"  _{subj}_\n"
                f"  error: `{err}`"
            )
        if len(rows) > 15:
            lines.append(f"\n_...and {len(rows) - 15} more (see email_send_log)_")
        lines.append(
            "\nAll flagged `escalated` — manual recovery required via the "
            "`/api/admin/email-health` dashboard."
        )
        _post_telegram("\n".join(lines))

        return {"escalated": len(rows)}

    # ------------------------------------------------------------------
    # 4. Daily report (fires at most once per 24h)
    # ------------------------------------------------------------------

    async def generate_daily_report(self) -> dict[str, Any]:
        """Send a 24h summary to Telegram, but at most once per 24h.

        Uses ``system_settings[email_health_monitor_last_report_utc]`` as
        a lock so the monitor can run every 30 min but only emit one
        daily digest.
        """
        async with self.db_pool.acquire() as conn:
            last_ts_raw = await conn.fetchval(
                "SELECT value FROM system_settings WHERE key = $1",
                _DAILY_REPORT_STATE_KEY,
            )

        now = datetime.now(tz=timezone.utc)
        if last_ts_raw:
            try:
                last_ts = datetime.fromisoformat(last_ts_raw)
                if last_ts.tzinfo is None:
                    last_ts = last_ts.replace(tzinfo=timezone.utc)
                if now - last_ts < timedelta(hours=23):
                    return {"report": "skipped", "reason": "fired_within_24h"}
            except (ValueError, TypeError):
                pass  # corrupt value → run the report and overwrite

        async with self.db_pool.acquire() as conn:
            counts = await conn.fetch(
                """
                SELECT email_type, status, COUNT(*) AS n
                  FROM email_send_log
                 WHERE created_at >= NOW() - INTERVAL '24 hours'
                 GROUP BY email_type, status
                 ORDER BY email_type, status
                """,
            )

        if not counts:
            # Still mark state so we don't re-query immediately.
            await self._mark_report_fired(now)
            return {"report": "empty_window"}

        # Build per-type rollup
        by_type: dict[str, dict[str, int]] = {}
        for row in counts:
            by_type.setdefault(row["email_type"], {})[row["status"]] = row["n"]

        lines = [
            "📊 *Email health — last 24h*",
            "",
        ]
        for et in sorted(by_type.keys()):
            sent = by_type[et].get("sent", 0)
            failed = by_type[et].get("failed", 0)
            esc = by_type[et].get("escalated", 0)
            skipped = by_type[et].get("skipped_idempotent", 0)
            flag = "🚨" if (failed + esc) else "✅"
            lines.append(
                f"{flag} `{et}`: sent={sent} failed={failed} escalated={esc}"
                + (f" skipped={skipped}" if skipped else "")
            )

        _post_telegram("\n".join(lines))
        await self._mark_report_fired(now)
        return {"report": "sent", "lines": len(lines) - 2}

    async def _mark_report_fired(self, ts: datetime) -> None:
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO system_settings (key, value, updated_at)
                VALUES ($1, $2, NOW())
                ON CONFLICT (key) DO UPDATE
                  SET value = EXCLUDED.value, updated_at = NOW()
                """,
                _DAILY_REPORT_STATE_KEY,
                ts.isoformat(),
            )

    # ------------------------------------------------------------------
    # Dashboard query helpers (used by /api/admin/email-health)
    # ------------------------------------------------------------------

    async def dashboard_rollup_7d(self) -> list[dict[str, Any]]:
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT email_type, status, COUNT(*) AS n
                  FROM email_send_log
                 WHERE created_at >= NOW() - INTERVAL '7 days'
                 GROUP BY email_type, status
                 ORDER BY email_type, status
                """,
            )
        return [dict(r) for r in rows]

    async def dashboard_pending_failures(self) -> list[dict[str, Any]]:
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, email_type, to_email, subject, attempt_number,
                       error_message, retry_after, created_at, status
                  FROM email_send_log
                 WHERE status IN ('failed', 'escalated')
                 ORDER BY created_at DESC
                 LIMIT 100
                """,
            )
        return [dict(r) for r in rows]

    async def dashboard_provider_failure_rate_7d(self) -> dict[str, float]:
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT provider,
                       SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) AS ok,
                       SUM(CASE WHEN status IN ('failed','escalated') THEN 1 ELSE 0 END) AS ko,
                       COUNT(*) AS total
                  FROM email_send_log
                 WHERE created_at >= NOW() - INTERVAL '7 days'
                   AND provider IS NOT NULL
                 GROUP BY provider
                """,
            )
        result: dict[str, float] = {}
        for r in rows:
            total = r["total"] or 1
            result[r["provider"]] = float(r["ko"]) / float(total)
        return result


# ----------------------------------------------------------------------
# Telegram helper (sync, same pattern as email_audit)
# ----------------------------------------------------------------------


def _post_telegram(text: str) -> None:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        logger.warning(
            "EmailHealthMonitor: TELEGRAM_BOT_TOKEN not set; skipping: %s",
            text[:200],
        )
        return
    try:
        data = urllib.parse.urlencode(
            {"chat_id": _OWNER_CHAT_ID, "text": text, "parse_mode": "Markdown"},
        ).encode()
        urllib.request.urlopen(  # noqa: S310 — api.telegram.org is a known URL
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data,
            timeout=10,
        )
    except (urllib.error.URLError, OSError, ValueError) as exc:
        logger.warning("EmailHealthMonitor: Telegram post failed: %s", exc)
