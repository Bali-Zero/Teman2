"""WhatsApp export staging importer.

Reads JSONL produced by parse_exports.py and INSERTs records into:
- whatsapp_export_batches
- whatsapp_export_documents_staging
- whatsapp_export_messages_staging

Idempotent: ON CONFLICT DO NOTHING via UNIQUE constraints.
NEVER writes to clients/practices — staging only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import Json

logger = logging.getLogger("whatsapp_export_backfill.import_staging")

_MSG_INDEX_RE = re.compile(r":(\d+)$")


def summarize_jsonl(path: str | Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record: dict[str, Any] = json.loads(line)
            record_type = str(record.get("record_type") or "unknown")
            counts[record_type] = counts.get(record_type, 0) + 1
    return counts


def _compute_source_hash(batch: dict[str, Any]) -> str:
    payload = f"{batch.get('export_root', '')}|{batch.get('chat_path', '')}|{batch.get('batch_id', '')}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _msg_index(message_id: str | None) -> int | None:
    if not message_id:
        return None
    match = _MSG_INDEX_RE.search(message_id)
    return int(match.group(1)) if match else None


def _excerpt(body: str | None, limit: int = 240) -> str | None:
    if not body:
        return None
    body = body.strip()
    return body[:limit] + ("…" if len(body) > limit else "")


def import_jsonl(
    jsonl_path: Path,
    conn: Any,
    *,
    created_by: str = "import_staging.py",
) -> dict[str, int]:
    """Idempotent import. Returns counts of inserted rows."""
    records: list[dict[str, Any]] = []
    with jsonl_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            records.append(json.loads(line))

    batch_records = [r for r in records if r.get("record_type") == "batch"]
    if len(batch_records) != 1:
        raise ValueError(f"expected exactly 1 batch record, found {len(batch_records)}")
    batch = batch_records[0]

    documents = [r for r in records if r.get("record_type") == "document"]
    messages = [r for r in records if r.get("record_type") == "message"]

    source_hash = _compute_source_hash(batch)
    inserted = {"batch": 0, "document": 0, "message": 0}

    with conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO whatsapp_export_batches
                    (source_root, source_label, source_hash, chat_title,
                     canonical_chat_path, status, metadata, created_by)
                VALUES (%s, %s, %s, %s, %s, 'parsed', %s, %s)
                ON CONFLICT (source_hash) DO NOTHING
                RETURNING id
                """,
                (
                    batch.get("export_root"),
                    batch.get("batch_id"),
                    source_hash,
                    batch.get("batch_id"),
                    batch.get("chat_path"),
                    Json(
                        {
                            "message_count": batch.get("message_count"),
                            "parser_record_count": len(records),
                        }
                    ),
                    created_by,
                ),
            )
            row = cur.fetchone()
            if row is not None:
                batch_pk = row[0]
                inserted["batch"] = 1
            else:
                cur.execute(
                    "SELECT id FROM whatsapp_export_batches WHERE source_hash = %s",
                    (source_hash,),
                )
                batch_pk = cur.fetchone()[0]

            for doc in documents:
                source_relpath = doc.get("source_path")
                if not source_relpath:
                    logger.warning("doc missing source_path, skipped: %s", doc.get("filename"))
                    continue
                cur.execute(
                    """
                    INSERT INTO whatsapp_export_documents_staging
                        (batch_id, source_relpath, file_name, file_ext,
                         file_size_bytes, sha256, document_category,
                         match_reasons, contains_sensitive_data, review_status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, '[]'::jsonb, true, 'pending')
                    ON CONFLICT (batch_id, source_relpath) DO NOTHING
                    """,
                    (
                        batch_pk,
                        source_relpath,
                        doc.get("filename_nfc") or doc.get("filename"),
                        Path(doc.get("filename") or "").suffix.lstrip(".").lower() or None,
                        doc.get("size_bytes"),
                        doc.get("sha256"),
                        doc.get("category") or "unknown",
                    ),
                )
                if cur.rowcount == 1:
                    inserted["document"] += 1

            for msg in messages:
                idx = _msg_index(msg.get("message_id"))
                if idx is None:
                    logger.warning("msg missing index, skipped: %s", msg.get("message_id"))
                    continue
                attachments = msg.get("attachments") or []
                cur.execute(
                    """
                    INSERT INTO whatsapp_export_messages_staging
                        (batch_id, source_relpath, message_index, message_date,
                         sender_display_name, body, body_excerpt,
                         has_attachments, attachment_relpaths, review_status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
                    ON CONFLICT (batch_id, source_relpath, message_index) DO NOTHING
                    """,
                    (
                        batch_pk,
                        batch.get("chat_path") or "_chat.txt",
                        idx,
                        msg.get("timestamp"),
                        msg.get("sender"),
                        msg.get("body"),
                        _excerpt(msg.get("body")),
                        bool(attachments),
                        Json(attachments),
                    ),
                )
                if cur.rowcount == 1:
                    inserted["message"] += 1

    return inserted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import parsed WhatsApp export JSONL into staging tables (idempotent)."
    )
    parser.add_argument("jsonl_path", type=Path)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print summary only, no DB writes (default behavior preserved).",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="Postgres DSN (defaults to $DATABASE_URL).",
    )
    parser.add_argument("--created-by", default="import_staging.py")
    args = parser.parse_args(argv)

    counts = summarize_jsonl(args.jsonl_path)

    if args.dry_run or not args.database_url:
        sys.stdout.write(
            json.dumps(
                {
                    "dry_run": True,
                    "counts": counts,
                    "reason": "no_database_url" if not args.database_url else "explicit_dry_run",
                },
                sort_keys=True,
            )
            + "\n"
        )
        return 0

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    conn = psycopg2.connect(args.database_url)
    try:
        inserted = import_jsonl(args.jsonl_path, conn, created_by=args.created_by)
    finally:
        conn.close()

    sys.stdout.write(
        json.dumps(
            {"dry_run": False, "counts": counts, "inserted": inserted},
            sort_keys=True,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
