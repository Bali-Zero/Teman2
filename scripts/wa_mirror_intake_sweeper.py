#!/usr/bin/env python3
"""wa-mirror media → intake sweeper (Anello 1-bis, team lines, sovereign-local).

The official Bali Zero line (Anello 1) flows via Meta Cloud API. The TEAM
members' personal WhatsApp lines are mirrored by wa-mirror (Baileys/WhatsApp-Web)
which ALREADY downloads + decrypts + saves media blobs to disk at receive time
and records the path in ``whatsapp_message_context.media_stored_path`` (LOCAL
Postgres ``nuzantara_dev`` on the Pro). This sweeper is a READ-ONLY consumer of
that table: it never touches wa-mirror's code or writes back to its table.

Each tick it finds new inbound document/image blobs and ``enqueue()``s them into
the SAME local intake_queue the official line uses, so the existing intake worker
(OCR/classify/route → document_routing_proposal) processes them uniformly.

Law 2 / UU-PDP: everything is local — LOCAL DB read, LOCAL blob read, LOCAL
intake enqueue. No cloud, no Fly. Downstream OCR is local Ollama. Sender phones
and emails are PII — never logged at INFO with the value; only counts + row ids.

PRO-HALF cadence: the watermark is seeded to the CURRENT max id on first run, so
the Pro processes ONLY NEW arrivals. The historical backlog (id ≤ seed) is the
Mini's job (separate step). Override the seed with WA_MIRROR_SWEEP_START_ID.

Cron-tick shim (NOT a daemon), flock single-instance, atomic cursor — same shape
as scripts/wa_media_pull_worker.py.

Environment:
- INTAKE_DATABASE_URL / DATABASE_URL  (default postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev)
- WA_MIRROR_SWEEP_BATCH               (default 25 — rows enqueued per tick, rate-limit)
- WA_MIRROR_SWEEP_START_ID            (optional — seed watermark on first run;
                                       if unset, first run seeds to current max id = new-only)
- WA_MIRROR_MEDIA_TYPES              (default "document,image" — comma list)
"""
from __future__ import annotations

import asyncio
import fcntl
import logging
import os
import sys
from pathlib import Path

import asyncpg

# Reuse the shipped, tested enqueue core.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "backend-rag"))
from backend.services.intake.enqueue import enqueue  # noqa: E402

logger = logging.getLogger("wa_mirror_sweeper")

STATE_DIR = Path.home() / ".cell-bridge-state"
LAST_ID_FILE = STATE_DIR / "wa_mirror_sweep_last_id.txt"
LOCK_FILE = STATE_DIR / "wa_mirror_sweep.lock"

_SOURCE = "whatsapp"
_DEFAULT_BATCH = 25


def _acquire_lock_or_exit() -> int:
    STATE_DIR.mkdir(exist_ok=True)
    fd = os.open(str(LOCK_FILE), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BlockingIOError:
        logger.info("[wa_mirror_sweep] another instance running, skipping this tick")
        os.close(fd)
        sys.exit(0)


def _media_types() -> tuple[str, ...]:
    raw = os.getenv("WA_MIRROR_MEDIA_TYPES", "document,image")
    return tuple(t.strip() for t in raw.split(",") if t.strip())


async def _resolve_seed(conn: asyncpg.Connection, media_types: tuple[str, ...]) -> int:
    """First-run watermark seed.

    Explicit WA_MIRROR_SWEEP_START_ID wins. Otherwise seed to the CURRENT max id
    of eligible rows so the Pro half processes ONLY new arrivals (backlog is the
    Mini's job). If the table is empty, seed 0.
    """
    env = os.getenv("WA_MIRROR_SWEEP_START_ID", "").strip()
    if env:
        try:
            return int(env)
        except ValueError:
            logger.warning("[wa_mirror_sweep] bad WA_MIRROR_SWEEP_START_ID=%r, ignoring", env)
    cur_max = await conn.fetchval(
        """
        SELECT COALESCE(max(id), 0) FROM whatsapp_message_context
         WHERE media_stored_path IS NOT NULL
           AND media_type = ANY($1::text[])
           AND direction = 'inbound'
        """,
        list(media_types),
    )
    return int(cur_max or 0)


def _load_watermark() -> int | None:
    if not LAST_ID_FILE.exists():
        return None
    try:
        return int(LAST_ID_FILE.read_text().strip() or "0")
    except (ValueError, OSError) as exc:
        logger.warning("[wa_mirror_sweep] watermark unreadable, treating as unseeded: %s", exc)
        return None


def _save_watermark(last_id: int) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    tmp = LAST_ID_FILE.with_suffix(".tmp")
    tmp.write_text(str(int(last_id)))
    tmp.replace(LAST_ID_FILE)


async def run_one_tick() -> int:
    db_url = os.getenv(
        "INTAKE_DATABASE_URL",
        os.getenv("DATABASE_URL", "postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev"),
    )
    batch = int(os.getenv("WA_MIRROR_SWEEP_BATCH", str(_DEFAULT_BATCH)))
    media_types = _media_types()

    pool = await asyncpg.create_pool(dsn=db_url, min_size=1, max_size=3)
    try:
        async with pool.acquire() as conn:
            watermark = _load_watermark()
            if watermark is None:
                watermark = await _resolve_seed(conn, media_types)
                _save_watermark(watermark)
                logger.info("[wa_mirror_sweep] first run, watermark seeded to %d", watermark)

            rows = await conn.fetch(
                """
                SELECT id, baileys_message_id, media_stored_path, media_mime,
                       media_type, team_member_email, sender_phone
                  FROM whatsapp_message_context
                 WHERE media_stored_path IS NOT NULL
                   AND media_type = ANY($1::text[])
                   AND direction = 'inbound'
                   AND id > $2
                 ORDER BY id ASC
                 LIMIT $3
                """,
                list(media_types),
                int(watermark),
                int(batch),
            )

        if not rows:
            logger.info("[wa_mirror_sweep] no new media (watermark=%d)", watermark)
            return 0

        enqueued_new = 0
        already = 0
        blob_missing = 0
        max_done = watermark

        for r in rows:
            rid = int(r["id"])
            bmid = r["baileys_message_id"]
            blob_path = r["media_stored_path"]
            if not bmid or not blob_path:
                logger.warning("[wa_mirror_sweep] row %d missing id/path, skipping", rid)
                max_done = max(max_done, rid)  # don't re-scan a structurally-bad row
                continue
            if not os.path.exists(blob_path):
                blob_missing += 1
                logger.warning("[wa_mirror_sweep] row %d blob missing on disk, skipping", rid)
                max_done = max(max_done, rid)  # blob gone; never coming back, advance past it
                continue
            try:
                result = await enqueue(
                    pool,
                    source=_SOURCE,
                    source_ref=f"wa-mirror:{bmid}",
                    blob_path=blob_path,
                    mime_type=r["media_mime"],
                    received_by=r["team_member_email"],
                    sender_phone=r["sender_phone"],
                )
            except Exception as exc:  # noqa: BLE001 — isolate per-row failure
                logger.error(
                    "[wa_mirror_sweep] enqueue failed for row %d: %s", rid, exc, exc_info=True
                )
                # Do NOT advance past a transient failure — retry next tick.
                break
            if result.was_new:
                enqueued_new += 1
            else:
                already += 1
            max_done = max(max_done, rid)

        if max_done > watermark:
            _save_watermark(max_done)
        logger.info(
            "[wa_mirror_sweep] done: scanned=%d new=%d dup=%d blob_missing=%d watermark=%d",
            len(rows), enqueued_new, already, blob_missing, max_done,
        )
        return 0
    finally:
        await pool.close()


async def main() -> int:
    logging.basicConfig(
        level=os.getenv("WA_MIRROR_SWEEP_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    lock_fd = _acquire_lock_or_exit()
    try:
        return await run_one_tick()
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
