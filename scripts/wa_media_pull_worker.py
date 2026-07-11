#!/usr/bin/env python3
"""WhatsApp media PULL worker — sovereign Pro side of Anello 1 (Law 2).

The Fly webhook publishes metadata-only rows to events_outbox
(channel ``whatsapp_media_pending``) — just a Meta ``media_id`` + provenance,
never a byte of the client document. This worker, running ONLY on the Pro:

1. Reads ``WHATSAPP_ACCESS_TOKEN`` from env (0600 env-file via wrapper) else Keychain (never plist,
   never logged).
2. HTTP GETs the Fly bridge for pending rows (metadata only).
3. For each: downloads the media FROM META ITSELF to the local sovereign blob
   root (``INTAKE_BLOB_ROOT``), then enqueues into the LOCAL nuzantara_dev
   intake_queue. PII therefore only ever exists on the Pro.
4. ACKs the Fly row only AFTER a successful local enqueue (at-least-once;
   enqueue is idempotent on intake_key, so a re-pull is harmless).
5. Staleness guard: Meta media_ids expire (~days). Any pending row older than
   ``WA_MEDIA_STALE_HOURS`` triggers a Telegram alert before it rots.

Cron-invoked shim (NOT a daemon — KeepAlive=false in the plist), modeled on
apps/cell/scripts/skills_bridge_consumer.py (Fly fetch + flock + cursor) and
backend/services/intake/worker.py (local DB + enqueue). Reuses the pure
``download_media`` + ``enqueue`` already shipped and tested.

Environment variables:
- FLY_BRIDGE_URL          (default https://nuzantara-rag.fly.dev)
- BRIDGE_API_KEY          (required; same key as GET /api/bridge/events)
- LOCAL_DATABASE_URL      (default postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev)
- INTAKE_BLOB_ROOT        (default ~/.nuzantara/intake-blobs — sovereign local)
- WA_MEDIA_KEYCHAIN_SERVICE (default balizero-whatsapp)
- WA_MEDIA_KEYCHAIN_ACCOUNT (default access-token)
- WA_MEDIA_API_VERSION    (default v18.0)
- WA_MEDIA_STALE_HOURS    (default 36 — alert if a pending row is older)
- TELEGRAM_BOT_TOKEN      (optional; alerts disabled if unset)
- TELEGRAM_OWNER_CHAT_ID  (optional; default 1125336968)
"""
from __future__ import annotations

import asyncio
import fcntl
import logging
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg
import httpx

# Reuse the shipped, tested pure helpers.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "backend-rag"))
from backend.channels.whatsapp.media_download import (
    MediaDownloadError,
    download_media,
)
from backend.services.intake.enqueue import enqueue

logger = logging.getLogger("wa_media_pull")

STATE_DIR = Path.home() / ".cell-bridge-state"
LAST_ID_FILE = STATE_DIR / "wa_media_last_id.txt"
LOCK_FILE = STATE_DIR / "wa_media_pull.lock"

_SOURCE = "whatsapp"


def _acquire_lock_or_exit() -> int:
    STATE_DIR.mkdir(exist_ok=True)
    fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BlockingIOError:
        logger.info("[wa_media_pull] another instance running, skipping this tick")
        os.close(fd)
        sys.exit(0)


def _load_since() -> int:
    if not LAST_ID_FILE.exists():
        return 0
    try:
        return int(LAST_ID_FILE.read_text().strip() or "0")
    except (ValueError, OSError) as exc:
        logger.warning("[wa_media_pull] cursor unreadable, reset to 0: %s", exc)
        return 0


def _save_since(last_id: int) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    tmp = LAST_ID_FILE.with_suffix(".tmp")
    tmp.write_text(str(int(last_id)))
    tmp.replace(LAST_ID_FILE)


def _read_keychain(service: str, account: str) -> str:
    """Read a generic-password secret from the macOS Keychain. Never logged.

    Returns "" (with a hint logged, never the value) if absent/unreadable.
    """
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.error("[wa_media_pull] Keychain read failed: %s", exc)
        return ""
    if out.returncode != 0:
        logger.error(
            "[wa_media_pull] Keychain item not found (service=%s account=%s) — "
            "store it with: security add-generic-password -s %s -a %s -w '<value>'",
            service, account, service, account,
        )
        return ""
    return out.stdout.strip()


def _read_access_token() -> str:
    """WHATSAPP_ACCESS_TOKEN from env if set, else the Pro Keychain. Never logged.

    Env-first mirrors _read_bridge_api_key: a 0600 env-file (sourced by the
    wrapper, like ~/.wa-mirror.env) is the durable delivery channel on the Pro,
    since the login Keychain is unreachable over SSH and a custom keychain gets
    quarantined by macOS Keychain Services under concurrent launchd access.
    """
    env_token = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    if env_token:
        return env_token
    service = os.getenv("WA_MEDIA_KEYCHAIN_SERVICE", "balizero-whatsapp")
    account = os.getenv("WA_MEDIA_KEYCHAIN_ACCOUNT", "access-token")
    return _read_keychain(service, account)


def _read_bridge_api_key() -> str:
    """BRIDGE_API_KEY from env if set, else the Pro Keychain (no secret in plist)."""
    env_key = os.getenv("BRIDGE_API_KEY", "")
    if env_key:
        return env_key
    service = os.getenv("WA_MEDIA_KEYCHAIN_SERVICE", "balizero-whatsapp")
    return _read_keychain(service, "bridge-api-key")


def _send_telegram_alert(msg: str) -> None:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    if not bot_token:
        return
    try:
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": msg}).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{bot_token}/sendMessage", data=data, timeout=5
        )
    except Exception as exc:
        logger.warning("[wa_media_pull] Telegram alert failed: %s", exc)


def _parse_iso(ts: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(ts)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


async def _fetch_pending(
    http: httpx.AsyncClient, base_url: str, api_key: str, since: int
) -> dict[str, Any] | None:
    try:
        resp = await http.get(
            f"{base_url}/api/bridge/wa-media/pending",
            params={"since": since, "limit": 50},
            headers={"X-Bridge-Auth": api_key},
        )
    except httpx.RequestError as exc:
        logger.warning("[wa_media_pull] pending GET failed: %s", exc)
        return None
    if resp.status_code == 401:
        logger.error("[wa_media_pull] auth failed (401) — check BRIDGE_API_KEY")
        return None
    if resp.status_code != 200:
        logger.error(
            "[wa_media_pull] pending unexpected status %d: %s",
            resp.status_code, resp.text[:200],
        )
        return None
    return resp.json()


async def _ack(http: httpx.AsyncClient, base_url: str, api_key: str, ids: list[int]) -> None:
    if not ids:
        return
    try:
        resp = await http.post(
            f"{base_url}/api/bridge/wa-media/ack",
            json={"outbox_ids": ids},
            headers={"X-Bridge-Auth": api_key},
        )
        if resp.status_code != 200:
            logger.warning(
                "[wa_media_pull] ack non-200 (%d) for ids=%s: %s",
                resp.status_code, ids, resp.text[:200],
            )
    except httpx.RequestError as exc:
        logger.warning("[wa_media_pull] ack POST failed for ids=%s: %s", ids, exc)


async def run_one_poll() -> int:
    base_url = os.getenv("FLY_BRIDGE_URL", "https://nuzantara-rag.fly.dev")
    api_key = _read_bridge_api_key()
    db_url = os.getenv(
        "LOCAL_DATABASE_URL", "postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev"
    )
    blob_root = os.path.expanduser(
        os.getenv("INTAKE_BLOB_ROOT", "~/.nuzantara/intake-blobs")
    )
    api_version = os.getenv("WA_MEDIA_API_VERSION", "v18.0")
    stale_hours = float(os.getenv("WA_MEDIA_STALE_HOURS", "36"))

    if not api_key:
        logger.error("[wa_media_pull] BRIDGE_API_KEY not in env or Keychain, aborting")
        return 1

    access_token = _read_access_token()
    if not access_token:
        logger.error("[wa_media_pull] no access token in Keychain, aborting")
        return 1

    since = _load_since()

    async with httpx.AsyncClient(timeout=60.0) as http:
        payload = await _fetch_pending(http, base_url, api_key, since)
        if payload is None:
            return 1

        items = payload.get("items", [])
        if not items:
            logger.info("[wa_media_pull] no pending media (since=%d)", since)
            return 0

        now = datetime.now(timezone.utc)
        oldest = None
        for it in items:
            dt = _parse_iso(it.get("created_at", ""))
            if dt and (oldest is None or dt < oldest):
                oldest = dt
        if oldest is not None:
            age_h = (now - oldest).total_seconds() / 3600.0
            if age_h > stale_hours:
                _send_telegram_alert(
                    f"⚠️ wa_media_pull: oldest pending WA media is {age_h:.1f}h old "
                    f"(>{stale_hours}h). Meta media_ids expire — the Pro may have been "
                    f"offline. {len(items)} item(s) pending. Run the worker now."
                )

        pool = await asyncpg.create_pool(dsn=db_url, min_size=1, max_size=3)
        acked: list[int] = []
        new_count = 0
        download_errors = 0
        try:
            for it in items:
                oid = int(it["outbox_id"])
                media_id = it.get("media_id") or ""
                wamid = it.get("wa_message_id") or media_id
                if not media_id:
                    logger.warning("[wa_media_pull] row %d has no media_id, skipping", oid)
                    continue
                try:
                    dl = await download_media(
                        http,
                        media_id=media_id,
                        access_token=access_token,
                        dest_dir=blob_root,
                        api_version=api_version,
                    )
                except MediaDownloadError as exc:
                    download_errors += 1
                    logger.error(
                        "[wa_media_pull] download failed for media_id=%s (row %d): %s",
                        media_id, oid, exc,
                    )
                    continue

                try:
                    result = await enqueue(
                        pool,
                        source=_SOURCE,
                        source_ref=f"whatsapp-live:{wamid}",
                        blob_path=dl.blob_path,
                        mime_type=dl.mime_type,
                        blob_hash=dl.sha256,
                        byte_size=dl.byte_size,
                        received_by=None,
                    )
                except Exception as exc:
                    logger.error(
                        "[wa_media_pull] enqueue failed for media_id=%s (row %d): %s",
                        media_id, oid, exc, exc_info=True,
                    )
                    continue

                if result.was_new:
                    new_count += 1
                acked.append(oid)
        finally:
            await pool.close()

        await _ack(http, base_url, api_key, acked)

    if acked:
        _save_since(max(acked))
    logger.info(
        "[wa_media_pull] done: pending=%d new=%d dl_err=%d acked=%d since=%d",
        len(items), new_count, download_errors, len(acked), _load_since(),
    )
    return 0


async def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    lock_fd = _acquire_lock_or_exit()
    try:
        return await run_one_poll()
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
        except Exception:
            pass


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
