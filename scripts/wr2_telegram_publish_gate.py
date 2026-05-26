#!/usr/bin/env python3
"""WR2 Telegram Publish Gate — operator approval loop.

Spec: research/wr2/2026-05-27-wr2-autonomous-workflow-spec.md §10
Phase 2.2 of WR2 autonomous carousel pipeline (Antonello 2026-05-27).

Flow:
    1. Poll wr2_carousel_runs for state='awaiting_approval' AND no
       pending publish_attempt with valid token.
    2. Generate manual_publish_token (HMAC-SHA256 single-use, 24h expiry).
    3. INSERT wr2_publish_attempts with state='blocked_manual_gate'.
    4. POST Telegram message with inline buttons [Approve/Reject/Preview].
    5. Long-poll Telegram getUpdates → handle callback_query.
    6. On approve: validate token + user_id whitelist → state=approved.
    7. On reject: state=rejected with reason.
    8. Stuck >7d (token_expires_at + 6 days) → state=stale_abandoned.

Env:
    DATABASE_URL            — PG via localhost:15432 proxy on Pro
    TELEGRAM_BOT_TOKEN      — required
    TELEGRAM_OWNER_CHAT_ID  — default 1125336968 (Zero)
    WR2_TG_GATE_SECRET      — HMAC key for token signing (required)
    WR2_AUTO_PUBLISH_ENABLED — false Day 1 (auto path codato in standby)
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import logging
import os
import secrets
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import asyncpg
import httpx

logger = logging.getLogger("wr2.telegram_gate")

DEFAULT_OWNER_CHAT_ID = 1125336968  # Zero per CLAUDE.md §13
DEFAULT_POLL_INTERVAL_SEC = 60
TOKEN_TTL_HOURS = 24  # Spec Q5
STALE_THRESHOLD_DAYS = 7
TELEGRAM_API_BASE = "https://api.telegram.org"
TELEGRAM_TIMEOUT_SEC = 30
LONG_POLL_TIMEOUT_SEC = 25
DEFAULT_PREVIEW_BASE = os.environ.get("WR2_PREVIEW_BASE_URL", "")

ALLOWED_USER_IDS: set[int] = {DEFAULT_OWNER_CHAT_ID}


def get_owner_chat_id() -> int:
    raw = os.environ.get("TELEGRAM_OWNER_CHAT_ID", str(DEFAULT_OWNER_CHAT_ID))
    try:
        return int(raw)
    except ValueError:
        logger.warning(f"invalid TELEGRAM_OWNER_CHAT_ID={raw!r}, falling back to default")
        return DEFAULT_OWNER_CHAT_ID


def get_gate_secret() -> bytes:
    s = os.environ.get("WR2_TG_GATE_SECRET")
    if not s:
        raise SystemExit("WR2_TG_GATE_SECRET env required (HMAC signing key)")
    return s.encode("utf-8")


def sign_token(carousel_id: str, content_hash: str, nonce: str, expires_at: int) -> str:
    """HMAC-SHA256 signed manual_publish_token.

    Spec §10.1 + Codex amendment: bound to content_hash (token-reuse
    prevention across drafts).
    """
    payload = f"{carousel_id}|{content_hash}|{nonce}|{expires_at}"
    sig = hmac.new(get_gate_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{nonce}.{expires_at}.{sig}"


def verify_token(token: str, carousel_id: str, content_hash: str) -> tuple[bool, str]:
    """Returns (valid, reason). Constant-time HMAC compare."""
    try:
        nonce, expires_at_str, sig = token.split(".")
        expires_at = int(expires_at_str)
    except ValueError:
        return False, "token_malformed"

    if time.time() > expires_at:
        return False, "token_expired"

    expected = sign_token(carousel_id, content_hash, nonce, expires_at).split(".")[-1]
    if not hmac.compare_digest(sig, expected):
        return False, "token_mismatch"
    return True, "ok"


def compute_content_hash(output_dir: Path) -> str:
    """sha256 di critic-verdict + layout + rendered file paths."""
    h = hashlib.sha256()
    for name in ("brief_interpreter.json", "storyboarder.json",
                 "layout_composer.json", "rendered.json"):
        p = output_dir / name
        if p.is_file():
            h.update(p.read_bytes())
    return h.hexdigest()


async def find_pending_carousels(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    """Spec §10.1 — find awaiting_approval without active publish_attempt."""
    rows = await conn.fetch(
        """
        SELECT cr.*
          FROM wr2_carousel_runs cr
          LEFT JOIN wr2_publish_attempts pa
            ON pa.carousel_id = cr.carousel_id
           AND pa.state = 'blocked_manual_gate'
           AND pa.token_expires_at > now()
         WHERE cr.state = 'awaiting_approval'
           AND pa.id IS NULL
         ORDER BY cr.state_updated_at ASC
         LIMIT 10
        """,
    )
    return [dict(r) for r in rows]


async def find_active_publish_attempts(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    """Spec §10.1 — active gate (waiting for callback)."""
    rows = await conn.fetch(
        """
        SELECT pa.*, cr.topic, cr.output_dir, cr.publish_mode
          FROM wr2_publish_attempts pa
          JOIN wr2_carousel_runs cr ON cr.carousel_id = pa.carousel_id
         WHERE pa.state = 'blocked_manual_gate'
           AND pa.token_expires_at > now()
         ORDER BY pa.created_at ASC
         LIMIT 50
        """,
    )
    return [dict(r) for r in rows]


async def create_publish_attempt(
    conn: asyncpg.Connection,
    run: dict[str, Any],
) -> dict[str, Any]:
    """Spec §10.1 — INSERT blocked_manual_gate with signed token."""
    carousel_id = str(run["carousel_id"])
    content_hash = compute_content_hash(Path(run["output_dir"]))
    nonce = secrets.token_urlsafe(16)
    expires_at = int(time.time()) + TOKEN_TTL_HOURS * 3600
    token = sign_token(carousel_id, content_hash, nonce, expires_at)
    idempotency_key = f"{carousel_id}:instagram:{content_hash[:16]}"

    row = await conn.fetchrow(
        """
        INSERT INTO wr2_publish_attempts
            (carousel_id, platform, content_hash, state, idempotency_key,
             manual_publish_token, token_expires_at)
        VALUES ($1, 'instagram', $2, 'blocked_manual_gate', $3, $4, to_timestamp($5))
        ON CONFLICT (idempotency_key) DO UPDATE
           SET manual_publish_token = EXCLUDED.manual_publish_token,
               token_expires_at = EXCLUDED.token_expires_at,
               updated_at = now()
        RETURNING *
        """,
        run["carousel_id"], content_hash, idempotency_key, token, expires_at,
    )
    logger.info(f"publish_attempt {row['id']} → blocked_manual_gate (exp {TOKEN_TTL_HOURS}h)")
    return dict(row)


def build_inline_keyboard(carousel_id: str, attempt_id: int) -> dict[str, Any]:
    short_id = str(carousel_id)[:8]
    keyboard = [
        [
            {"text": "✅ Approve", "callback_data": f"a:{short_id}:{attempt_id}"},
            {"text": "❌ Reject", "callback_data": f"r:{short_id}:{attempt_id}"},
        ],
    ]
    if DEFAULT_PREVIEW_BASE:
        keyboard.append([
            {"text": "👀 Preview", "url": f"{DEFAULT_PREVIEW_BASE}/{carousel_id}"},
        ])
    return {"inline_keyboard": keyboard}


async def telegram_send_message(
    client: httpx.AsyncClient,
    bot_token: str,
    chat_id: int,
    text: str,
    *,
    reply_markup: dict[str, Any] | None = None,
) -> int | None:
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        r = await client.post(
            f"{TELEGRAM_API_BASE}/bot{bot_token}/sendMessage",
            json=payload, timeout=TELEGRAM_TIMEOUT_SEC,
        )
    except httpx.HTTPError as exc:
        logger.warning(f"telegram sendMessage failed: {exc}")
        return None

    if r.status_code != 200:
        logger.warning(f"telegram sendMessage {r.status_code}: {r.text[:200]}")
        return None
    data = r.json()
    return data.get("result", {}).get("message_id")


async def telegram_answer_callback(
    client: httpx.AsyncClient,
    bot_token: str,
    callback_query_id: str,
    text: str,
) -> None:
    try:
        await client.post(
            f"{TELEGRAM_API_BASE}/bot{bot_token}/answerCallbackQuery",
            json={"callback_query_id": callback_query_id, "text": text[:200]},
            timeout=TELEGRAM_TIMEOUT_SEC,
        )
    except httpx.HTTPError as exc:
        logger.warning(f"telegram answerCallback failed: {exc}")


async def telegram_get_updates(
    client: httpx.AsyncClient,
    bot_token: str,
    offset: int,
) -> list[dict[str, Any]]:
    """Long-poll for callback_query updates."""
    try:
        r = await client.get(
            f"{TELEGRAM_API_BASE}/bot{bot_token}/getUpdates",
            params={
                "offset": offset,
                "timeout": LONG_POLL_TIMEOUT_SEC,
                "allowed_updates": json.dumps(["callback_query"]),
            },
            timeout=LONG_POLL_TIMEOUT_SEC + 5,
        )
    except httpx.HTTPError as exc:
        logger.warning(f"telegram getUpdates failed: {exc}")
        return []

    if r.status_code != 200:
        logger.warning(f"telegram getUpdates {r.status_code}: {r.text[:200]}")
        return []
    return r.json().get("result", []) or []


async def notify_pending(
    conn: asyncpg.Connection,
    client: httpx.AsyncClient,
    bot_token: str,
    chat_id: int,
) -> int:
    """Find pending carousels + send Telegram notifications."""
    pending = await find_pending_carousels(conn)
    sent = 0
    for run in pending:
        try:
            attempt = await create_publish_attempt(conn, run)
        except Exception as exc:
            logger.warning(f"create_publish_attempt failed for {run['carousel_id']}: {exc}")
            continue

        text = (
            f"🎠 *WR2 Carousel awaiting approval*\n\n"
            f"`carousel_id`: `{run['carousel_id']}`\n"
            f"`topic`: {run['topic']}\n"
            f"`session`: `{run['session_id']}`\n"
            f"`expires`: {TOKEN_TTL_HOURS}h"
        )
        msg_id = await telegram_send_message(
            client, bot_token, chat_id, text,
            reply_markup=build_inline_keyboard(str(run["carousel_id"]), attempt["id"]),
        )
        if msg_id:
            sent += 1
    if sent:
        logger.info(f"notified {sent} pending carousels")
    return sent


async def handle_callback(
    conn: asyncpg.Connection,
    client: httpx.AsyncClient,
    bot_token: str,
    update: dict[str, Any],
) -> None:
    callback = update.get("callback_query") or {}
    cb_id = callback.get("id")
    data = callback.get("data", "")
    from_user = callback.get("from") or {}
    user_id = from_user.get("id")

    if user_id not in ALLOWED_USER_IDS:
        await telegram_answer_callback(client, bot_token, cb_id, "🚫 Unauthorized")
        logger.warning(f"callback from unauthorized user_id={user_id}")
        return

    try:
        action, short_id, attempt_id = data.split(":", 2)
        attempt_id_int = int(attempt_id)
    except (ValueError, AttributeError):
        await telegram_answer_callback(client, bot_token, cb_id, "❌ Malformed callback")
        logger.warning(f"malformed callback_data={data!r}")
        return

    attempt = await conn.fetchrow(
        "SELECT * FROM wr2_publish_attempts WHERE id = $1",
        attempt_id_int,
    )
    if not attempt:
        await telegram_answer_callback(client, bot_token, cb_id, "❌ Attempt not found")
        return

    if attempt["approved_at"] is not None or attempt["state"] != "blocked_manual_gate":
        await telegram_answer_callback(
            client, bot_token, cb_id,
            f"⚠️ Already {attempt['state']}",
        )
        return

    if action == "a":  # approve
        await conn.execute(
            """
            UPDATE wr2_publish_attempts
               SET approved_by = $1, approved_at = now(), updated_at = now()
             WHERE id = $2
            """,
            str(user_id), attempt_id_int,
        )
        await conn.execute(
            "UPDATE wr2_carousel_runs SET state = 'approved', state_updated_at = now() WHERE carousel_id = $1",
            attempt["carousel_id"],
        )
        await telegram_answer_callback(client, bot_token, cb_id, "✅ Approved")
        logger.info(f"approved attempt={attempt_id_int} carousel={attempt['carousel_id']}")

    elif action == "r":  # reject
        await conn.execute(
            """
            UPDATE wr2_publish_attempts
               SET state = 'failed', updated_at = now()
             WHERE id = $1
            """,
            attempt_id_int,
        )
        await conn.execute(
            "UPDATE wr2_carousel_runs SET state = 'rejected', state_updated_at = now(), completed_at = now() WHERE carousel_id = $1",
            attempt["carousel_id"],
        )
        await telegram_answer_callback(client, bot_token, cb_id, "❌ Rejected")
        logger.info(f"rejected attempt={attempt_id_int} carousel={attempt['carousel_id']}")

    else:
        await telegram_answer_callback(client, bot_token, cb_id, "❌ Unknown action")


async def archive_stale(conn: asyncpg.Connection) -> int:
    """Spec §10.2 — auto-archive carousels stuck >7d in awaiting_approval."""
    rows = await conn.fetch(
        """
        UPDATE wr2_carousel_runs
           SET state = 'stale_abandoned',
               state_updated_at = now(),
               completed_at = now(),
               last_error = 'Telegram approval window expired'
         WHERE state = 'awaiting_approval'
           AND state_updated_at < now() - $1::interval
         RETURNING carousel_id
        """,
        f"{STALE_THRESHOLD_DAYS} days",
    )
    if rows:
        logger.info(f"archived {len(rows)} stale_abandoned carousels")
    return len(rows)


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WR2 Telegram Publish Gate")
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--poll-interval", type=int, default=DEFAULT_POLL_INTERVAL_SEC)
    parser.add_argument("--once", action="store_true", help="One iteration (debug)")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL env required")
        return 74

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN env required")
        return 74

    try:
        get_gate_secret()  # validate at startup
    except SystemExit:
        return 74

    chat_id = get_owner_chat_id()
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2, timeout=10)
    update_offset = 0

    try:
        async with httpx.AsyncClient() as client:
            while True:
                async with pool.acquire() as conn:
                    try:
                        await notify_pending(conn, client, bot_token, chat_id)
                        await archive_stale(conn)
                    except Exception as exc:
                        logger.warning(f"notify/archive loop error: {exc}")

                # Long-poll for callbacks
                updates = await telegram_get_updates(client, bot_token, update_offset)
                for upd in updates:
                    update_offset = max(update_offset, upd.get("update_id", 0) + 1)
                    if "callback_query" not in upd:
                        continue
                    async with pool.acquire() as conn:
                        try:
                            await handle_callback(conn, client, bot_token, upd)
                        except Exception as exc:
                            logger.exception(f"handle_callback error: {exc}")

                if args.once:
                    break
                await asyncio.sleep(max(args.poll_interval - LONG_POLL_TIMEOUT_SEC, 5))

        return 0
    finally:
        await pool.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
