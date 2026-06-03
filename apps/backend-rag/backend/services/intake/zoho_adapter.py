"""Zoho mail intake adapter (FASE 1B) — NEW source.

Lists new mail attachments via the Zoho Mail API using the OAuth token already
managed by `admin_zoho_auth.py` (table `zoho_email_tokens`) and enqueues each
attachment blob. ZERO CRM writes.

Cursor: `system_settings` key `zoho_intake_cursor` (seeded '{}' by migration 210).
We store `{"last_message_time": <epoch_ms>}` and only fetch messages newer than
that watermark.

Graceful degradation (Law 4): if no Zoho token is configured, or the API is
unreachable, the adapter logs WARN and returns 0 WITHOUT crashing. PII stays
local — attachment bytes are written under INTAKE_BLOB_ROOT on the Pro and never
shipped to cloud LLMs here.

Zoho Mail API surface (verified against zoho_email_tokens schema, not live):
- api_domain stored per token (default https://mail.zoho.com).
- List messages:    GET {api_domain}/api/accounts/{account_id}/messages/view
- List attachments: GET {api_domain}/api/accounts/{account_id}/folders/{folderId}/messages/{messageId}/attachmentinfo
- Download:         GET {api_domain}/api/accounts/{account_id}/folders/{folderId}/messages/{messageId}/attachments/{attachmentId}
- Auth header:      "Authorization: Zoho-oauthtoken {access_token}"
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import asyncpg
import httpx

from backend.services.intake.enqueue import enqueue

logger = logging.getLogger(__name__)

_SOURCE = "zoho"
_CURSOR_KEY = "zoho_intake_cursor"

_BLOB_ROOT = Path(
    os.environ.get("INTAKE_BLOB_ROOT", os.path.expanduser("~/.nuzantara/intake-blobs"))
) / "zoho"

_HTTP_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


async def _load_token(pool: asyncpg.Pool) -> dict[str, Any] | None:
    """Return the most-recently-updated Zoho token row, or None if none exists."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT account_id, access_token, api_domain
            FROM zoho_email_tokens
            ORDER BY updated_at DESC NULLS LAST
            LIMIT 1
            """
        )
    if row is None:
        return None
    return dict(row)


async def _load_cursor(pool: asyncpg.Pool) -> int:
    async with pool.acquire() as conn:
        raw = await conn.fetchval(
            "SELECT value FROM system_settings WHERE key = $1", _CURSOR_KEY
        )
    if isinstance(raw, str) and raw not in ("", "{}"):
        try:
            parsed = json.loads(raw)
            return int(parsed.get("last_message_time", 0))
        except (ValueError, TypeError):
            return 0
    return 0


async def _save_cursor(pool: asyncpg.Pool, last_message_time: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO system_settings (key, value, updated_at)
            VALUES ($1, $2, now())
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()
            """,
            _CURSOR_KEY,
            json.dumps({"last_message_time": last_message_time}),
        )


async def drain_zoho(
    pool: asyncpg.Pool,
    *,
    client: httpx.AsyncClient | None = None,
    limit: int = 200,
) -> dict[str, int]:
    """Fetch new Zoho mail attachments since the cursor and enqueue each blob.

    `client` lets callers inject a persistent AsyncClient (Golden Rule #10). If
    None, a single client is created for the whole drain and closed at the end
    (NOT per-iteration).

    Returns counters: {messages, attachments, enqueued_new, already_present, errors}.
    """
    counters = {
        "messages": 0,
        "attachments": 0,
        "enqueued_new": 0,
        "already_present": 0,
        "errors": 0,
    }

    token = await _load_token(pool)
    if not token or not token.get("access_token"):
        logger.warning("drain_zoho: no Zoho token configured — skipping (graceful, Law 4)")
        return counters

    account_id = token["account_id"]
    api_domain = (token.get("api_domain") or "https://mail.zoho.com").rstrip("/")
    headers = {"Authorization": f"Zoho-oauthtoken {token['access_token']}"}
    cursor = await _load_cursor(pool)

    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=_HTTP_TIMEOUT)

    new_watermark = cursor
    try:
        try:
            resp = await client.get(
                f"{api_domain}/api/accounts/{account_id}/messages/view",
                headers=headers,
                params={"limit": limit, "sortBy": "date", "sortorder": "false"},
            )
            resp.raise_for_status()
            messages = resp.json().get("data", [])
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("drain_zoho: message list failed — skipping (%s)", exc)
            return counters

        for msg in messages:
            msg_time = int(msg.get("receivedTime", 0) or 0)
            if msg_time <= cursor:
                continue
            new_watermark = max(new_watermark, msg_time)
            msg_id = str(msg.get("messageId", ""))
            folder_id = str(msg.get("folderId", ""))
            if not msg_id or not folder_id:
                continue
            counters["messages"] += 1

            try:
                ainfo = await client.get(
                    f"{api_domain}/api/accounts/{account_id}/folders/{folder_id}"
                    f"/messages/{msg_id}/attachmentinfo",
                    headers=headers,
                )
                ainfo.raise_for_status()
                attachments = ainfo.json().get("data", {}).get("attachments", [])
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning("drain_zoho: attachmentinfo failed msg=%s (%s)", msg_id, exc)
                counters["errors"] += 1
                continue

            for att in attachments:
                att_id = str(att.get("attachmentId") or att.get("attachId") or "")
                att_name = att.get("attachmentName") or att.get("fileName") or att_id
                if not att_id:
                    continue
                counters["attachments"] += 1
                try:
                    dl = await client.get(
                        f"{api_domain}/api/accounts/{account_id}/folders/{folder_id}"
                        f"/messages/{msg_id}/attachments/{att_id}",
                        headers=headers,
                    )
                    dl.raise_for_status()
                    dest = _BLOB_ROOT / msg_id[:2] / f"{msg_id}__{att_id}__{att_name}".replace("/", "_")
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(dl.content)
                    res = await enqueue(
                        pool,
                        source=_SOURCE,
                        source_ref=f"zoho:{msg_id}:{att_id}",
                        blob_path=dest,
                        mime_type=att.get("contentType") or None,
                        byte_size=len(dl.content),
                    )
                except Exception:  # noqa: BLE001 — adapter must not crash the drain loop
                    logger.exception("drain_zoho enqueue failed msg=%s att=%s", msg_id, att_id)
                    counters["errors"] += 1
                    continue
                if res.was_new:
                    counters["enqueued_new"] += 1
                else:
                    counters["already_present"] += 1

        if new_watermark > cursor:
            await _save_cursor(pool, new_watermark)
    finally:
        if owns_client:
            await client.aclose()

    logger.info("drain_zoho done: %s", counters)
    return counters
