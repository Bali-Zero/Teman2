"""WhatsApp intake adapter (FASE 1B).

Drains WhatsApp export documents that are still pending review and enqueues each
blob for unified intake. ZERO CRM writes — only reads the WA staging tables and
calls enqueue() (which writes only document_instances / intake_queue).

Source-of-truth (verified against nuzantara_dev migration schema, 2026-06-04):
- `whatsapp_export_documents_staging`: one row per exported file.
  Pending column is `review_status` (CHECK in pending/approved/rejected/ignored),
  NOT `ocr_status`. The blob lives at
  `whatsapp_export_batches.source_root` + '/' + `source_relpath`.
  `matched_client_id` is the non-authoritative client hint.

NOTE (spec correction): the FASE 1B brief said WA files carry `ocr_status='pending'`.
In this schema the WA-export staging table uses `review_status='pending'`; the
`ocr_status` column lives on the separate CRM `documents` table. This adapter
drains the WA-export staging table (the actual on-disk WA blobs).
"""

from __future__ import annotations

import logging
import os

import asyncpg

from backend.services.intake.enqueue import EnqueueResult, enqueue

logger = logging.getLogger(__name__)

_SOURCE = "whatsapp"


async def drain_whatsapp(
    pool: asyncpg.Pool,
    *,
    limit: int = 500,
) -> dict[str, int]:
    """Enqueue WhatsApp-export blobs still pending review.

    Reads `whatsapp_export_documents_staging` joined to `whatsapp_export_batches`
    for the on-disk path, enqueues each existing file. Idempotent: re-running
    skips already-queued blobs (intake_key UNIQUE).

    Returns counters: {found, enqueued_new, already_present, missing_file, errors}.
    """
    counters = {
        "found": 0,
        "enqueued_new": 0,
        "already_present": 0,
        "missing_file": 0,
        "errors": 0,
    }

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                s.id              AS staging_id,
                b.source_root     AS source_root,
                s.source_relpath  AS source_relpath,
                s.sha256          AS sha256,
                s.matched_client_id AS matched_client_id,
                s.file_size_bytes AS file_size_bytes
            FROM whatsapp_export_documents_staging s
            JOIN whatsapp_export_batches b ON b.id = s.batch_id
            WHERE s.review_status = 'pending'
            ORDER BY s.id
            LIMIT $1
            """,
            limit,
        )

    counters["found"] = len(rows)
    for row in rows:
        blob_path = os.path.join(row["source_root"], row["source_relpath"])
        if not os.path.isfile(blob_path):
            logger.warning("whatsapp blob missing on disk: %s (staging_id=%s)", blob_path, row["staging_id"])
            counters["missing_file"] += 1
            continue
        source_ref = f"whatsapp:{row['staging_id']}"
        client_hint = row["matched_client_id"]
        try:
            res: EnqueueResult = await enqueue(
                pool,
                source=_SOURCE,
                source_ref=source_ref,
                blob_path=blob_path,
                client_id_hint=client_hint,
                # Reuse the precomputed export sha256 as blob_hash if present
                # (it is sha256 of the same bytes); else enqueue() recomputes.
                blob_hash=row["sha256"] or None,
                byte_size=row["file_size_bytes"],
            )
        except Exception:  # noqa: BLE001 — adapter must not crash the drain loop
            logger.exception("whatsapp enqueue failed for staging_id=%s", row["staging_id"])
            counters["errors"] += 1
            continue
        if res.was_new:
            counters["enqueued_new"] += 1
        else:
            counters["already_present"] += 1

    logger.info("drain_whatsapp done: %s", counters)
    return counters
