"""WA Copilot Telegram notifier (S1.11).

Sends per-owner Telegram DM for ``action_queue`` items that are open and due
within the next 4 hours (configurable). Strictly opt-in via ``team_members``:

    SELECT a.*, tm.telegram_chat_id, tm.notify_telegram
    FROM action_queue a
    JOIN team_members tm ON tm.email = a.owner
    WHERE a.status = 'open'
      AND a.due_at < NOW() + INTERVAL '4 hours'
      AND tm.telegram_chat_id IS NOT NULL
      AND tm.notify_telegram = true
      AND tm.active = true
    ORDER BY a.priority DESC, a.due_at ASC NULLS LAST
    LIMIT N;

CLI:
    python -m backend.services.wa_copilot.telegram_notifier \\
      (--apply | --dry-run) \\
      [--limit N] \\
      [--window-hours H]            (default 4) \\
      [--dedup-key-prefix wa_actions:]  (default wa_actions:) \\
      [--dedup-ttl-sec 86400]       (default 86400 = 24h) \\
      [--metrics-json /tmp/notif.json]

Constraints (CLAUDE.md + cicatrix):
  - httpx async (NEVER requests).
  - PgBouncer-safe asyncpg (statement_cache_size=0).
  - Reuses W55 cicatrix retry pattern: 3 attempts, backoff 1s/3s/7s,
    HTTP 4xx no-retry, 5xx+OSError/timeout retry.
  - Dedup via Redis SET ``wa_actions:notified:<action_id>``, TTL 24h.
    If Redis unreachable, the notifier falls back to "skip-on-no-cache"
    posture (treat as duplicate) — safer than fan-out duplicates.
  - Per-owner DM only — no group chat fanout.
  - Markdown-safe body with deep link to /actions?id=<id>.

References:
  - S1.9 action_queue rules: ``action_queue_rules.py``
  - W55 retry pattern: ``scripts/sentinel_lib/alerter.py`` (3-attempt
    progressive backoff for transient network errors).
  - Migration 200: ``team_members.{telegram_chat_id, notify_telegram}``.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import json
import logging
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Any

import asyncpg
import httpx

logger = logging.getLogger(__name__)

NOTIFIER_VERSION = "v1-2026-05-25"
DEFAULT_DEDUP_PREFIX = "wa_actions:"
DEFAULT_DEDUP_TTL_SEC = 86400  # 24h
DEFAULT_WINDOW_HOURS = 4
DEFAULT_LIMIT = 100
TELEGRAM_API = "https://api.telegram.org"
HTTP_TIMEOUT_SEC = 10
RETRY_BACKOFFS_SEC = (1, 3, 7)  # W55 pattern: 3 attempts total
MAX_ATTEMPTS = 3


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class NotifierMetrics:
    notif_candidates: int = 0
    notif_sent: int = 0
    notif_skipped_dedup: int = 0
    notif_failed_no_owner: int = 0
    notif_failed_no_telegram: int = 0
    notif_failed_http: int = 0
    notif_skipped_dry_run: int = 0
    wall_ms: int = 0
    samples: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Markdown helpers
# ---------------------------------------------------------------------------

# Telegram Markdown V1 (parse_mode='Markdown') reserves: _ * ` [
# We escape sparingly — body is meant to be human-readable.
_MARKDOWN_ESCAPE_RE = re.compile(r"([_*`\[])")


def _md_escape(text: str | None) -> str:
    """Escape Telegram Markdown reserved characters in a free-text field."""
    if not text:
        return "—"
    return _MARKDOWN_ESCAPE_RE.sub(r"\\\1", str(text))


def _format_due(due_at: _dt.datetime | None) -> str:
    """Human-friendly due_at formatting (relative to now)."""
    if due_at is None:
        return "no deadline"
    now = _dt.datetime.now(_dt.timezone.utc)
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=_dt.timezone.utc)
    delta = due_at - now
    minutes = int(delta.total_seconds() // 60)
    if minutes < -60:
        hours = abs(minutes) // 60
        return f"OVERDUE by {hours}h ({due_at:%Y-%m-%d %H:%M UTC})"
    if minutes < 0:
        return f"OVERDUE by {abs(minutes)}min ({due_at:%H:%M UTC})"
    if minutes < 60:
        return f"in {minutes}min ({due_at:%H:%M UTC})"
    hours = minutes // 60
    return f"in {hours}h{minutes % 60:02d}m ({due_at:%Y-%m-%d %H:%M UTC})"


def build_message_body(row: dict[str, Any]) -> str:
    """Build Telegram Markdown body for one action_queue row.

    Row must contain: action_id, priority, client_full_name (nullable),
    action_type, due_at (nullable), reason, recommended_action.
    """
    action_id = row["action_id"]
    priority = row.get("priority", 5)
    client_name = _md_escape(row.get("client_full_name") or "unknown client")
    action_type = _md_escape(row.get("action_type") or "—")
    due_str = _format_due(row.get("due_at"))
    reason = _md_escape(row.get("reason") or "—")
    recommended = _md_escape(row.get("recommended_action") or "—")

    return (
        f"🚨 *Action #{action_id}* (priority {priority})\n"
        f"\n"
        f"Client: {client_name}\n"
        f"Type: {action_type}\n"
        f"Due: {due_str}\n"
        f"\n"
        f"*Reason:* {reason}\n"
        f"*Action:* {recommended}\n"
        f"\n"
        f"👉 https://kita.balizero.com/actions?id={action_id}"
    )


# ---------------------------------------------------------------------------
# Telegram client (W55 retry pattern)
# ---------------------------------------------------------------------------


async def send_telegram_message(
    client: httpx.AsyncClient,
    bot_token: str,
    chat_id: str,
    text: str,
) -> tuple[bool, str | None]:
    """POST /sendMessage with W55 retry-with-backoff.

    Returns (success, error_message).

    Retry semantics (mirrors ``scripts/sentinel_lib/alerter.py``):
      - 3 attempts total, backoffs 1s/3s/7s between.
      - HTTP 4xx (payload/auth/rate) → no retry, return failure.
      - HTTP 5xx → retry as transient.
      - Network errors (timeout, connect error, OSError) → retry.
      - HTTP 200 → success.
    """
    url = f"{TELEGRAM_API}/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    last_err: str | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = await client.post(url, data=payload, timeout=HTTP_TIMEOUT_SEC)
            if resp.status_code == 200:
                return True, None
            if 400 <= resp.status_code < 500:
                # 4xx: payload/auth/rate-limit; do NOT retry.
                body_excerpt = resp.text[:200]
                last_err = f"HTTP {resp.status_code} non-retryable: {body_excerpt}"
                logger.warning(
                    "telegram send action_id=? HTTP %d (non-retryable): %s",
                    resp.status_code,
                    body_excerpt,
                )
                return False, last_err
            # 5xx: transient, retry.
            last_err = f"HTTP {resp.status_code} (retryable)"
            logger.info(
                "telegram send retry %d/%d: HTTP %d",
                attempt,
                MAX_ATTEMPTS,
                resp.status_code,
            )
        except (httpx.TimeoutException, httpx.NetworkError, OSError) as e:
            last_err = f"{type(e).__name__}: {e}"
            logger.info(
                "telegram send retry %d/%d: %s",
                attempt,
                MAX_ATTEMPTS,
                last_err,
            )
        except Exception as e:  # pragma: no cover - safety net
            last_err = f"unexpected {type(e).__name__}: {e}"
            logger.warning(
                "telegram send retry %d/%d: unexpected %s",
                attempt,
                MAX_ATTEMPTS,
                last_err,
            )
        if attempt < MAX_ATTEMPTS:
            await asyncio.sleep(RETRY_BACKOFFS_SEC[attempt - 1])

    logger.warning(
        "telegram send exhausted %d retries (last error: %s)",
        MAX_ATTEMPTS,
        last_err,
    )
    return False, last_err or "exhausted retries"


# ---------------------------------------------------------------------------
# Redis dedup
# ---------------------------------------------------------------------------


async def _get_redis_client() -> Any | None:
    """Return an aioredis client, or None if Redis is unreachable.

    Uses REDIS_URL env (falls back to localhost:6379/0). Failure to connect
    is non-fatal: caller treats unreachable Redis as "skip-all" to avoid
    duplicate fanout (safer posture than send-and-pray).
    """
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    try:
        import redis.asyncio as aioredis  # type: ignore

        client = aioredis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        await client.ping()
        return client
    except Exception as e:
        logger.warning(
            "Redis unreachable (%s) — dedup disabled; notifier will SKIP all "
            "candidates rather than risk duplicate fanout",
            e,
        )
        return None


async def _dedup_key_exists(
    redis_client: Any | None,
    prefix: str,
    action_id: int,
) -> bool:
    if redis_client is None:
        return True  # fail-closed: skip everything when Redis is down
    key = f"{prefix}notified:{action_id}"
    try:
        return bool(await redis_client.exists(key))
    except Exception as e:
        logger.warning("redis EXISTS failed for %s: %s — treating as duplicate", key, e)
        return True


async def _dedup_mark_sent(
    redis_client: Any | None,
    prefix: str,
    action_id: int,
    ttl_sec: int,
) -> None:
    if redis_client is None:
        return
    key = f"{prefix}notified:{action_id}"
    try:
        await redis_client.set(key, str(int(time.time())), ex=ttl_sec)
    except Exception as e:
        logger.warning("redis SET failed for %s: %s", key, e)


# ---------------------------------------------------------------------------
# DB query
# ---------------------------------------------------------------------------


_FETCH_CANDIDATES_SQL = """
SELECT
    a.action_id,
    a.client_id,
    a.action_type,
    a.reason,
    a.recommended_action,
    a.due_at,
    a.priority,
    a.owner,
    c.full_name AS client_full_name,
    tm.telegram_chat_id,
    tm.notify_telegram,
    tm.active AS tm_active
FROM action_queue a
LEFT JOIN clients c ON c.id = a.client_id
JOIN team_members tm ON LOWER(tm.email) = LOWER(a.owner)
WHERE a.status = 'open'
  AND a.due_at IS NOT NULL
  AND a.due_at < NOW() + ($1::int * INTERVAL '1 hour')
  AND tm.telegram_chat_id IS NOT NULL
  AND tm.notify_telegram = true
  AND tm.active = true
ORDER BY a.priority DESC NULLS LAST, a.due_at ASC NULLS LAST
LIMIT $2;
"""


async def fetch_candidates(
    pool: asyncpg.Pool,
    window_hours: int,
    limit: int,
) -> list[dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(_FETCH_CANDIDATES_SQL, window_hours, limit)
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


async def run_notifier(
    pool: asyncpg.Pool,
    *,
    apply: bool,
    limit: int,
    window_hours: int,
    dedup_prefix: str,
    dedup_ttl_sec: int,
    bot_token: str | None,
    keep_samples: int = 5,
) -> NotifierMetrics:
    metrics = NotifierMetrics()
    t0 = time.monotonic()

    candidates = await fetch_candidates(pool, window_hours=window_hours, limit=limit)
    metrics.notif_candidates = len(candidates)
    logger.info(
        "notifier: %d candidate(s) within %dh window (limit=%d)",
        metrics.notif_candidates,
        window_hours,
        limit,
    )

    if not candidates:
        metrics.wall_ms = int((time.monotonic() - t0) * 1000)
        return metrics

    redis_client = await _get_redis_client()

    async with httpx.AsyncClient() as http_client:
        for row in candidates:
            action_id = row["action_id"]
            chat_id = row.get("telegram_chat_id")
            owner = row.get("owner")
            body = build_message_body(row)

            if not owner:
                metrics.notif_failed_no_owner += 1
                continue
            if not chat_id:
                metrics.notif_failed_no_telegram += 1
                continue

            if await _dedup_key_exists(redis_client, dedup_prefix, action_id):
                metrics.notif_skipped_dedup += 1
                logger.debug(
                    "notifier: action_id=%d skipped (dedup hit)", action_id
                )
                continue

            if len(metrics.samples) < keep_samples:
                metrics.samples.append(
                    {
                        "action_id": action_id,
                        "owner": owner,
                        "chat_id": str(chat_id),
                        "body_preview": body[:200],
                    }
                )

            if not apply:
                metrics.notif_skipped_dry_run += 1
                logger.info(
                    "notifier (dry-run): action_id=%d → owner=%s chat=%s",
                    action_id,
                    owner,
                    chat_id,
                )
                continue

            if not bot_token:
                metrics.notif_failed_http += 1
                logger.error(
                    "notifier: TELEGRAM_BOT_TOKEN unset, cannot send "
                    "action_id=%d",
                    action_id,
                )
                continue

            ok, err = await send_telegram_message(
                http_client, bot_token, str(chat_id), body
            )
            if ok:
                metrics.notif_sent += 1
                await _dedup_mark_sent(
                    redis_client, dedup_prefix, action_id, dedup_ttl_sec
                )
                logger.info(
                    "notifier: SENT action_id=%d owner=%s chat=%s",
                    action_id,
                    owner,
                    chat_id,
                )
            else:
                metrics.notif_failed_http += 1
                logger.warning(
                    "notifier: FAILED action_id=%d owner=%s err=%s",
                    action_id,
                    owner,
                    err,
                )

    if redis_client is not None:
        try:
            await redis_client.aclose()
        except Exception:  # pragma: no cover
            pass

    metrics.wall_ms = int((time.monotonic() - t0) * 1000)
    return metrics


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_dsn_local() -> str:
    """Build asyncpg DSN pointing at fly-pg-proxy localhost:15432
    (matches the action_queue_rules / team_promises pattern)."""
    db_url = os.environ.get("DATABASE_URL", "")
    if "127.0.0.1:15432" in db_url or "localhost:15432" in db_url:
        return db_url
    fly_url = os.environ.get("DATABASE_URL_FLY", "")
    m = re.match(r"postgres(?:ql)?://([^:]+):([^@]+)@", fly_url)
    if not m:
        return db_url
    user, pwd = m.group(1), m.group(2)
    return f"postgresql://{user}:{pwd}@127.0.0.1:15432/nuzantara_rag"


async def cli_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="telegram_notifier")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--apply", action="store_true", help="POST to Telegram")
    g.add_argument(
        "--dry-run",
        action="store_true",
        help="Select candidates but skip HTTP and dedup write",
    )
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--window-hours", type=int, default=DEFAULT_WINDOW_HOURS)
    parser.add_argument(
        "--dedup-key-prefix",
        default=DEFAULT_DEDUP_PREFIX,
        help=f"Redis key prefix (default {DEFAULT_DEDUP_PREFIX!r})",
    )
    parser.add_argument("--dedup-ttl-sec", type=int, default=DEFAULT_DEDUP_TTL_SEC)
    parser.add_argument("--metrics-json", default=None)
    parser.add_argument("--log-level", default="INFO")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )

    dsn = _build_dsn_local()
    if not dsn:
        logger.error("DATABASE_URL or DATABASE_URL_FLY required")
        return 2

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip() or None
    if args.apply and not bot_token:
        logger.error(
            "--apply requires TELEGRAM_BOT_TOKEN; set it via env or "
            "~/.wa-mirror.env"
        )
        return 2

    pool = await asyncpg.create_pool(
        dsn,
        min_size=1,
        max_size=3,
        statement_cache_size=0,
        command_timeout=60,
    )
    try:
        nm = await run_notifier(
            pool,
            apply=args.apply,
            limit=args.limit,
            window_hours=args.window_hours,
            dedup_prefix=args.dedup_key_prefix,
            dedup_ttl_sec=args.dedup_ttl_sec,
            bot_token=bot_token,
        )
        combined: dict[str, Any] = {
            "version": NOTIFIER_VERSION,
            "apply": args.apply,
            "limit": args.limit,
            "window_hours": args.window_hours,
            "dedup_prefix": args.dedup_key_prefix,
            "dedup_ttl_sec": args.dedup_ttl_sec,
            "started_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "metrics": asdict(nm),
        }
        logger.info(
            "NOTIFIER done: candidates=%d sent=%d dedup=%d no_owner=%d "
            "no_tg=%d http_fail=%d dry=%d wall=%dms",
            nm.notif_candidates,
            nm.notif_sent,
            nm.notif_skipped_dedup,
            nm.notif_failed_no_owner,
            nm.notif_failed_no_telegram,
            nm.notif_failed_http,
            nm.notif_skipped_dry_run,
            nm.wall_ms,
        )
        if args.metrics_json:
            with open(args.metrics_json, "w", encoding="utf-8") as f:
                json.dump(combined, f, indent=2, default=str)
            logger.info("metrics written to %s", args.metrics_json)
        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(cli_main()))
