#!/usr/bin/env python3
"""wa-mirror media → CRM lead + intake sweeper (Anello 1-bis, sovereign-local).

The official Bali Zero line (Anello 1) flows via Meta Cloud API. The TEAM
members' personal WhatsApp lines are mirrored by wa-mirror (Baileys/WhatsApp-Web)
which ALREADY downloads + decrypts + saves media blobs to disk at receive time
and records the path in ``whatsapp_message_context.media_stored_path`` (LOCAL
Postgres ``nuzantara_dev`` on the Pro). This sweeper never touches wa-mirror's
code or writes back to its table. It does write to the local CRM ``clients``
table in one narrow, phone-keyed path: when a direct inbound WA message/media
arrives, resolve an existing live client by normalized phone or create a
placeholder ``Lead +<phone>`` row. The passport document later matches that
same phone through the normal intake routing path.

Group media is intentionally still enqueued for OCR/HITL review, but group
participant phone numbers are NOT used as client identity hints. Internal Bali
Zero groups often carry documents and team-member sender phones; using those
phones as CRM identity would create false leads or false routes.

Each tick it finds new inbound document/image blobs and ``enqueue()``s them into
the SAME local intake_queue the official line uses, so the existing intake worker
(OCR/classify/route → document_routing_proposal) processes them uniformly.

Law 2 / UU-PDP: everything is local — LOCAL DB read/write, LOCAL blob read,
LOCAL intake enqueue. No cloud, no Fly. Downstream OCR is local Ollama. Sender
phones, names, and emails are PII — never logged at INFO with the value; only
counts + row ids.

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
- WA_MIRROR_TEXT_SWEEP_BATCH          (default 100 — direct text rows promoted per tick)
- WA_MIRROR_TEXT_START_ID             (optional — same seed semantics for text rows)
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
from backend.services.intake.enqueue import enqueue
from backend.services.intake.routing import normalize_sender_phone

logger = logging.getLogger("wa_mirror_sweeper")

STATE_DIR = Path.home() / ".cell-bridge-state"
LAST_ID_FILE = STATE_DIR / "wa_mirror_sweep_last_id.txt"
TEXT_LAST_ID_FILE = STATE_DIR / "wa_mirror_text_sweep_last_id.txt"
LOCK_FILE = STATE_DIR / "wa_mirror_sweep.lock"

_SOURCE = "whatsapp"
_DEFAULT_BATCH = 25
_DEFAULT_TEXT_BATCH = 100
_CRM_ACTOR = "wa-mirror-crm-writer@balizero.com"
_LEAD_SOURCE = "whatsapp_auto"


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


def _load_int(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        return int(path.read_text().strip() or "0")
    except (ValueError, OSError) as exc:
        logger.warning("[wa_mirror_sweep] cursor unreadable, treating as unseeded: %s", exc)
        return None


def _save_int(path: Path, value: int) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(str(int(value)))
    tmp.replace(path)


def _clean_push_name(value: object) -> str | None:
    if value is None:
        return None
    name = " ".join(str(value).split()).strip()
    if len(name) < 2 or len(name) > 160:
        return None
    lowered = name.lower()
    if lowered in {"unknown", "null", "none"}:
        return None
    if "@s.whatsapp.net" in lowered or "@lid" in lowered:
        return None
    if normalize_sender_phone(name):
        return None
    return name


def _lead_name(push_name: object, normalized_phone: str) -> str:
    return _clean_push_name(push_name) or f"Lead +{normalized_phone}"


def _name_is_junk(value: object) -> bool:
    if value is None:
        return True
    name = " ".join(str(value).split()).strip().lower()
    if not name:
        return True
    if name == "unknown" or name.startswith("lead +") or name.startswith("lead+"):
        return True
    return name.replace("+", "").replace(" ", "").replace("-", "").isdigit()


def _record_get(row: asyncpg.Record | dict, key: str) -> object:
    if isinstance(row, dict):
        return row.get(key)
    try:
        return row[key]
    except KeyError:
        return None


def _is_direct_chat(row: asyncpg.Record | dict) -> bool:
    """True when a wa-mirror row is a 1:1 chat, not a multi-party group."""
    chat_type = str(_record_get(row, "chat_type") or "").strip().lower()
    group_jid = _record_get(row, "group_jid")
    if chat_type == "group" or group_jid:
        return False
    if chat_type == "direct":
        return True
    # Older synthetic/export rows predate chat_type/group_jid; treat them as
    # direct to preserve the original one-to-one behavior.
    return True


def _candidate_phone(row: asyncpg.Record | dict) -> str | None:
    """Phone candidate for direct-chat CRM identity only."""
    for key in ("sender_phone", "counterpart_phone", "phone_number"):
        value = _record_get(row, key)
        if value and normalize_sender_phone(value):
            return str(value)
    return None


def _client_identity_phone(row: asyncpg.Record | dict) -> str | None:
    """Return a CRM identity phone only for direct chats.

    Group rows are intentionally review/OCR-only at this layer. A later group
    classifier may promote known client groups, but this first sovereign intake
    ring must not infer a client from a group participant phone.
    """
    if not _is_direct_chat(row):
        return None
    return _candidate_phone(row)


def _queue_sender_phone(row: asyncpg.Record | dict) -> str | None:
    """Sender phone passed to intake routing.

    Routing uses sender_phone as a client-match signal. Suppress it for group
    rows because group sender can be a Bali Zero teammate forwarding a document.
    """
    if not _is_direct_chat(row):
        return None
    value = _record_get(row, "sender_phone")
    return str(value) if value else None


async def _upsert_client_by_phone(
    conn: asyncpg.Connection,
    *,
    raw_phone: str | None,
    push_name: object = None,
    assigned_to: str | None = None,
    note_kind: str = "message",
) -> int | None:
    """Resolve/create a local CRM client from a WA sender phone.

    The CRM identity key is the normalized phone. Existing live clients win. If
    none exists, create a minimal lead with a placeholder name that later
    passport enrichment may improve. Never stores raw message text.
    """
    phone = normalize_sender_phone(raw_phone)
    if not phone:
        return None
    name = _lead_name(push_name, phone)

    await conn.execute("SELECT pg_advisory_xact_lock(hashtext($1))", phone)
    rows = await conn.fetch(
        """
        SELECT id, full_name
          FROM clients
         WHERE deleted_at IS NULL
           AND (
                phone_normalized IN ($1, $2)
             OR REGEXP_REPLACE(COALESCE(whatsapp, ''), '\\D', '', 'g') = $1
             OR REGEXP_REPLACE(COALESCE(phone, ''), '\\D', '', 'g') = $1
           )
         ORDER BY updated_at DESC NULLS LAST, id
         LIMIT 3
         FOR UPDATE
        """,
        phone,
        "+" + phone,
    )
    if rows:
        first = rows[0]
        current_name = first["full_name"]
        if _name_is_junk(current_name) and not _name_is_junk(name):
            await conn.execute(
                """
                UPDATE clients
                   SET full_name = $1, updated_at = NOW(), updated_by = $2
                 WHERE id = $3
                """,
                name,
                _CRM_ACTOR,
                first["id"],
            )
        return int(first["id"])

    note = (
        "WA mirror auto-intake: phone-keyed lead created from inbound "
        f"{note_kind}; raw message content not stored."
    )
    new_id = await conn.fetchval(
        """
        INSERT INTO clients (
          full_name, phone, whatsapp, phone_normalized,
          status, client_type, lead_source, assigned_to,
          created_by, updated_by, notes
        ) VALUES (
          $1, '+' || $2, '+' || $2, $2,
          'lead', 'individual', $3, $4,
          $5, $5, $6
        )
        RETURNING id
        """,
        name,
        phone,
        _LEAD_SOURCE,
        assigned_to,
        _CRM_ACTOR,
        note,
    )
    return int(new_id) if new_id is not None else None


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
    return _load_int(LAST_ID_FILE)


def _save_watermark(last_id: int) -> None:
    _save_int(LAST_ID_FILE, last_id)


async def _resolve_text_seed(conn: asyncpg.Connection) -> int:
    env = os.getenv("WA_MIRROR_TEXT_START_ID", "").strip()
    if env:
        try:
            return int(env)
        except ValueError:
            logger.warning("[wa_mirror_sweep] bad WA_MIRROR_TEXT_START_ID=%r, ignoring", env)
    cur_max = await conn.fetchval(
        """
        SELECT COALESCE(max(id), 0) FROM whatsapp_message_context
         WHERE direction = 'inbound'
           AND (chat_type = 'direct' OR (chat_type IS NULL AND group_jid IS NULL))
           AND COALESCE(NULLIF(body, ''), NULLIF(message_text, '')) IS NOT NULL
        """
    )
    return int(cur_max or 0)


async def _sweep_text_clients(pool: asyncpg.Pool, batch: int) -> dict[str, int]:
    counters = {"scanned": 0, "resolved": 0, "skipped": 0}
    async with pool.acquire() as conn:
        watermark = _load_int(TEXT_LAST_ID_FILE)
        if watermark is None:
            watermark = await _resolve_text_seed(conn)
            _save_int(TEXT_LAST_ID_FILE, watermark)
            logger.info("[wa_mirror_sweep] first text run, watermark seeded to %d", watermark)

        rows = await conn.fetch(
            """
            SELECT id, team_member_email, sender_phone, counterpart_phone, phone_number,
                   sender_push_name_snapshot
              FROM whatsapp_message_context
             WHERE direction = 'inbound'
               AND (chat_type = 'direct' OR (chat_type IS NULL AND group_jid IS NULL))
               AND COALESCE(NULLIF(body, ''), NULLIF(message_text, '')) IS NOT NULL
               AND id > $1
             ORDER BY id ASC
             LIMIT $2
            """,
            int(watermark),
            int(batch),
        )

        max_done = watermark
        for row in rows:
            rid = int(row["id"])
            counters["scanned"] += 1
            try:
                async with conn.transaction():
                    client_id = await _upsert_client_by_phone(
                        conn,
                        raw_phone=_candidate_phone(row),
                        push_name=row["sender_push_name_snapshot"],
                        assigned_to=row["team_member_email"],
                        note_kind="direct message",
                    )
            except Exception as exc:
                logger.error(
                    "[wa_mirror_sweep] CRM phone upsert failed for text row %d: %s",
                    rid, exc, exc_info=True,
                )
                break
            if client_id is None:
                counters["skipped"] += 1
            else:
                counters["resolved"] += 1
            max_done = max(max_done, rid)

        if max_done > watermark:
            _save_int(TEXT_LAST_ID_FILE, max_done)
    return counters


async def run_one_tick() -> int:
    db_url = os.getenv(
        "INTAKE_DATABASE_URL",
        os.getenv("DATABASE_URL", "postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev"),
    )
    batch = int(os.getenv("WA_MIRROR_SWEEP_BATCH", str(_DEFAULT_BATCH)))
    text_batch = int(os.getenv("WA_MIRROR_TEXT_SWEEP_BATCH", str(_DEFAULT_TEXT_BATCH)))
    media_types = _media_types()

    pool = await asyncpg.create_pool(dsn=db_url, min_size=1, max_size=3)
    try:
        text_counts = await _sweep_text_clients(pool, text_batch)
        if text_counts["scanned"]:
            logger.info(
                "[wa_mirror_sweep] text CRM pass: scanned=%d resolved=%d skipped=%d",
                text_counts["scanned"],
                text_counts["resolved"],
                text_counts["skipped"],
            )

        async with pool.acquire() as conn:
            watermark = _load_watermark()
            if watermark is None:
                watermark = await _resolve_seed(conn, media_types)
                _save_watermark(watermark)
                logger.info("[wa_mirror_sweep] first run, watermark seeded to %d", watermark)

            rows = await conn.fetch(
                """
                SELECT id, baileys_message_id, media_stored_path, media_mime,
                       media_type, team_member_email, sender_phone, counterpart_phone,
                       phone_number, sender_push_name_snapshot, chat_type, group_jid
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
        direct_media = 0
        group_media = 0
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
            client_id_hint = None
            if _is_direct_chat(r):
                direct_media += 1
                try:
                    async with pool.acquire() as conn, conn.transaction():
                        client_id_hint = await _upsert_client_by_phone(
                            conn,
                            raw_phone=_client_identity_phone(r),
                            push_name=r["sender_push_name_snapshot"],
                            assigned_to=r["team_member_email"],
                            note_kind="media",
                        )
                except Exception as exc:
                    logger.error(
                        "[wa_mirror_sweep] CRM phone upsert failed for media row %d: %s",
                        rid,
                        exc,
                        exc_info=True,
                    )
                    break
            else:
                group_media += 1
            try:
                result = await enqueue(
                    pool,
                    source=_SOURCE,
                    source_ref=f"wa-mirror:{bmid}",
                    blob_path=blob_path,
                    client_id_hint=client_id_hint,
                    mime_type=r["media_mime"],
                    received_by=r["team_member_email"],
                    sender_phone=_queue_sender_phone(r),
                )
            except Exception as exc:
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
            "[wa_mirror_sweep] done: scanned=%d direct=%d group=%d new=%d dup=%d "
            "blob_missing=%d watermark=%d",
            len(rows), direct_media, group_media, enqueued_new, already, blob_missing, max_done,
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
        except Exception:
            pass


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
