#!/usr/bin/env python3
"""Pro→Fly INTAKE gate document-count pusher (anti-Surya gate-1 on Fly).

Gate-1 document PII lives ONLY on the Pro nuzantara_dev (Law 2). The Fly gate
evaluator therefore cannot see how many documents a worker has pending. This Pro
cron worker computes a per-user pending-document COUNT (a non-PII integer) from
the local intake tables and pushes a full snapshot to Fly via
POST /api/bridge/intake-gate/doc-counts. Counts are not PII — no document
content, no client identity, just integers keyed by the worker's own email.

The Fly bridge upserts each count and zeroes any user absent from the snapshot,
so a cleared worker's gate-1 actually clears on Fly.

Mirrors scripts/wa_media_pull_worker.py: flock single-instance, Keychain-only
secret (BRIDGE_API_KEY), single persistent httpx client, structured logging.

Environment:
- INTAKE_DATABASE_URL / LOCAL_DATABASE_URL  (default local nuzantara_dev)
- FLY_BRIDGE_URL                            (default https://nuzantara-rag.fly.dev)
- BRIDGE_API_KEY                            (env else Keychain balizero-whatsapp/bridge-api-key)
"""
from __future__ import annotations

import asyncio
import fcntl
import logging
import os
import subprocess
import sys
from pathlib import Path

import asyncpg
import httpx

logger = logging.getLogger("intake_gate_count_pusher")

STATE_DIR = Path.home() / ".cell-bridge-state"
LOCK_FILE = STATE_DIR / "intake_gate_count_pusher.lock"

_DOC_PENDING_STATUSES = ("review_pending", "review_claimed")
_KEYCHAIN_SERVICE = "balizero-whatsapp"
_KEYCHAIN_BRIDGE_ACCOUNT = "bridge-api-key"


def _acquire_lock_or_exit() -> int:
    STATE_DIR.mkdir(exist_ok=True)
    fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BlockingIOError:
        logger.info("[gate_count_pusher] another instance running, skipping")
        os.close(fd)
        sys.exit(0)


def _read_keychain(account: str) -> str:
    try:
        out = subprocess.run(
            ["security", "find-generic-password", "-s", _KEYCHAIN_SERVICE, "-a", account, "-w"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("[gate_count_pusher] keychain read failed for %s: %s", account, exc)
    return ""


def _read_bridge_api_key() -> str:
    return os.getenv("BRIDGE_API_KEY", "").strip() or _read_keychain(_KEYCHAIN_BRIDGE_ACCOUNT)


async def _compute_counts(pool: asyncpg.Pool) -> list[dict[str, object]]:
    """Per-user pending-document count, by-receiver, matching the gate evaluator.

    One aggregate query with the SAME blocking predicate as
    gate_evaluator._count_documents: a doc blocks its receiver if it is
    review_pending, OR claimed by the receiver themselves (own active claim), OR
    its lease has expired (reclaimable, F7). A live claim by SOMEONE ELSE is
    excluded (F3). Grouped by intake_queue.received_by.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT lower(q.received_by) AS user_email, count(*) AS pending_count
              FROM document_routing_proposal p
              JOIN intake_queue q ON q.id = p.queue_id
             WHERE q.received_by IS NOT NULL
               AND p.status = ANY($1::text[])
               AND (
                     p.status = 'review_pending'
                  OR p.lease_expires_at < now()
                  OR lower(p.lease_owner) = lower(q.received_by)
               )
             GROUP BY lower(q.received_by)
            """,
            list(_DOC_PENDING_STATUSES),
        )
    return [
        {"user_email": r["user_email"], "pending_count": int(r["pending_count"])}
        for r in rows
    ]


async def run_one_push() -> int:
    db_url = os.getenv(
        "INTAKE_DATABASE_URL",
        os.getenv("LOCAL_DATABASE_URL", "postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev"),
    )
    base_url = os.getenv("FLY_BRIDGE_URL", "https://nuzantara-rag.fly.dev").rstrip("/")
    api_key = _read_bridge_api_key()
    if not api_key:
        logger.error("[gate_count_pusher] no BRIDGE_API_KEY (env or Keychain) — abort")
        return 1

    pool = await asyncpg.create_pool(dsn=db_url, min_size=1, max_size=3)
    try:
        counts = await _compute_counts(pool)
    finally:
        await pool.close()

    payload = {"counts": counts}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{base_url}/api/bridge/intake-gate/doc-counts",
            json=payload,
            headers={"X-Bridge-Auth": api_key},
        )
    if resp.status_code != 200:
        logger.error(
            "[gate_count_pusher] push failed: HTTP %s %s", resp.status_code, resp.text[:200]
        )
        return 1
    body = resp.json()
    logger.info(
        "[gate_count_pusher] pushed %d user-counts (upserted=%s zeroed=%s)",
        len(counts), body.get("upserted"), body.get("zeroed"),
    )
    return 0


async def main() -> int:
    logging.basicConfig(
        level=os.getenv("GATE_COUNT_PUSHER_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    lock_fd = _acquire_lock_or_exit()
    try:
        return await run_one_push()
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
