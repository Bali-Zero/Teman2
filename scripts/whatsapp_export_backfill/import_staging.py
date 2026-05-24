from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import asyncpg


@dataclass(frozen=True)
class ImportCounts:
    batches: int = 0
    messages: int = 0
    documents: int = 0
    contacts: int = 0


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _excerpt(value: str | None, limit: int = 240) -> str | None:
    if not value:
        return None
    collapsed = " ".join(str(value).split())
    return collapsed[:limit]


def _parse_iso_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


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


async def import_jsonl_to_staging(
    *,
    jsonl_path: Path,
    database_url: str,
    created_by: str | None,
    apply: bool,
) -> ImportCounts:
    records: list[dict[str, Any]] = []
    with jsonl_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))

    batch_records = [r for r in records if r.get("record_type") == "batch"]
    if not batch_records:
        return ImportCounts()

    batch = batch_records[0]
    source_root = str(batch.get("export_root") or "")
    chat_path = str(batch.get("chat_path") or "_chat.txt")
    batch_label = str(batch.get("batch_id") or batch.get("batch") or "export")
    source_hash = _sha256_text(f"{batch_label}\n{source_root}\n{chat_path}")

    if not apply:
        # dry-run only
        counts = summarize_jsonl(jsonl_path)
        return ImportCounts(
            batches=counts.get("batch", 0),
            messages=counts.get("message", 0),
            documents=counts.get("document", 0),
            contacts=counts.get("contact", 0),
        )

    conn = await asyncpg.connect(database_url)
    try:
        async with conn.transaction():
            batch_id = await conn.fetchval(
                """
                INSERT INTO whatsapp_export_batches
                    (source_root, source_label, source_hash, chat_title, canonical_chat_path, status, metadata, created_by)
                VALUES ($1, $2, $3, $4, $5, 'parsed', $6::jsonb, $7)
                ON CONFLICT (source_hash) DO UPDATE
                    SET source_root = EXCLUDED.source_root,
                        source_label = EXCLUDED.source_label,
                        canonical_chat_path = EXCLUDED.canonical_chat_path
                RETURNING id
                """,
                source_root,
                batch_label,
                source_hash,
                batch_label,
                chat_path,
                json.dumps({"message_count": batch.get("message_count")}),
                created_by,
            )

            message_count = 0
            document_count = 0
            contact_count = 0

            for record in records:
                rtype = record.get("record_type")
                if rtype == "message":
                    message_count += 1
                    attachments = record.get("attachments") or []
                    attachment_relpaths = [a.get("source_path") for a in attachments if a.get("source_path")]
                    await conn.execute(
                        """
                        INSERT INTO whatsapp_export_messages_staging
                            (batch_id, source_relpath, message_index, message_date, sender_display_name, body, body_excerpt,
                             has_attachments, attachment_relpaths, review_status)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, 'pending')
                        ON CONFLICT (batch_id, source_relpath, message_index) DO UPDATE
                            SET has_attachments = EXCLUDED.has_attachments,
                                attachment_relpaths = EXCLUDED.attachment_relpaths,
                                body = EXCLUDED.body,
                                body_excerpt = EXCLUDED.body_excerpt
                        """,
                        batch_id,
                        chat_path,
                        int(record.get("message_index") or 0),
                        _parse_iso_dt(record.get("timestamp")),
                        str(record.get("sender") or "")[:160] or None,
                        str(record.get("body") or "") if record.get("body") else None,
                        _excerpt(record.get("body")),
                        bool(attachment_relpaths),
                        json.dumps(attachment_relpaths),
                    )
                elif rtype == "document":
                    document_count += 1
                    source_path = str(record.get("source_path") or "")
                    filename = str(record.get("filename") or Path(source_path).name)
                    await conn.execute(
                        """
                        INSERT INTO whatsapp_export_documents_staging
                            (batch_id, source_relpath, file_name, file_ext, file_size_bytes, sha256,
                             document_category, match_reasons, contains_sensitive_data, review_status)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, '[]'::jsonb, TRUE, 'pending')
                        ON CONFLICT (batch_id, source_relpath) DO NOTHING
                        """,
                        batch_id,
                        source_path,
                        filename,
                        Path(filename).suffix.lstrip(".") or None,
                        record.get("size_bytes"),
                        record.get("sha256"),
                        record.get("category"),
                    )
                elif rtype == "contact":
                    contact_count += 1
                    source_path = str(record.get("source_path") or "")
                    phones = record.get("phones") or []
                    waids = record.get("waids") or []
                    phone_raw = str(phones[0]) if phones else None
                    phone_canonical = str(phones[0]) if phones else None
                    waid = str(waids[0]) if waids else None
                    await conn.execute(
                        """
                        INSERT INTO whatsapp_export_contacts_staging
                            (batch_id, source_relpath, display_name, phone_raw, phone_canonical, waid, match_reasons, review_status)
                        VALUES ($1, $2, $3, $4, $5, $6, '[]'::jsonb, 'pending')
                        ON CONFLICT (batch_id, source_relpath, COALESCE(phone_canonical, '')) DO NOTHING
                        """,
                        batch_id,
                        source_path,
                        str(record.get("display_name") or "")[:160] or None,
                        phone_raw,
                        phone_canonical,
                        waid,
                    )

            return ImportCounts(
                batches=1,
                messages=message_count,
                documents=document_count,
                contacts=contact_count,
            )
    finally:
        await conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import WhatsApp export JSONL into staging tables.")
    parser.add_argument("jsonl_path", type=Path)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--created-by", default=None)
    parser.add_argument("--apply", action="store_true", help="Write into DB (staging tables).")
    parser.add_argument("--dry-run", action="store_true", help="Print counts only (default).")
    args = parser.parse_args(argv)

    if not args.apply:
        counts = summarize_jsonl(args.jsonl_path)
        sysout = {"dry_run": True, "counts": counts}
        sys.stdout.write(json.dumps(sysout, sort_keys=True) + "\n")
        return 0

    if not args.database_url:
        raise SystemExit("Missing --database-url or DATABASE_URL env var.")

    counts = asyncio.run(
        import_jsonl_to_staging(
            jsonl_path=args.jsonl_path,
            database_url=args.database_url,
            created_by=args.created_by,
            apply=True,
        )
    )
    sys.stdout.write(
        json.dumps({"applied": True, "counts": counts.__dict__}, sort_keys=True) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
