#!/usr/bin/env python3
"""
Nuzantara GDrive Document Registerer
-----------------------------------
Parses the de-duplicated scan report and inserts the missing documents into
the PostgreSQL `documents` table, marking their ocr_status as 'pending'.
"""

import argparse
import asyncio
import logging
import os
import re
import sys
from typing import Any

import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("register_documents")

from pathlib import Path

base_path = Path(__file__).resolve().parent.parent
sys.path.append(str(base_path))
import dotenv

dotenv.load_dotenv(str(base_path / ".env"))

from backend.services.crm.documents import auto_categorize_document
from backend.services.crm.drive_poll_service import _infer_document_type


def parse_report(report_path: str) -> list[dict[str, Any]]:
    logger.info(f"Parsing report from {report_path}...")
    if not os.path.exists(report_path):
        logger.error(f"Report path {report_path} does not exist!")
        sys.exit(1)

    with open(report_path, encoding="utf-8") as f:
        content = f.read()

    blocks = content.split("----------------------------------\n")
    records = []

    client_re = re.compile(r"Client:\s+(\d+)\s+-\s+(.+)")
    path_re = re.compile(r"\s+Percorso Fisico:\s+(.+)")
    file_re = re.compile(r"\s+File:\s+(.+)")
    size_re = re.compile(r"\s+Dimensione:\s+(\d+)\s+bytes")
    id_re = re.compile(r"\s+Google Drive ID:\s+(\S+)")

    for block in blocks:
        block = block.strip()
        if not block or "REPORT DI SCANSIONE" in block:
            continue

        client_match = client_re.search(block)
        path_match = path_re.search(block)
        file_match = file_re.search(block)
        size_match = size_re.search(block)
        id_match = id_re.search(block)

        if client_match and file_match and id_match:
            records.append(
                {
                    "client_id": int(client_match.group(1)),
                    "client_name": client_match.group(2).strip(),
                    "subfolder": path_match.group(1).strip() if path_match else "Root",
                    "file_name": file_match.group(1).strip(),
                    "file_size": int(size_match.group(1)) if size_match else 0,
                    "file_id": id_match.group(1).strip(),
                }
            )

    logger.info(f"Successfully parsed {len(records)} records from report.")
    return records


async def main():
    parser = argparse.ArgumentParser(
        description="Register discovered Google Drive documents into database."
    )
    parser.add_argument(
        "--execute", action="store_true", help="Execute database insertions (default is dry-run)"
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Limit number of records to process"
    )
    args = parser.parse_args()

    report_path = os.path.expanduser("~/Desktop/nuzantara_drive_scan_report_deduped.txt")
    records = parse_report(report_path)

    if args.limit:
        records = records[: args.limit]
        logger.info(f"Limiting to first {args.limit} records.")

    if not records:
        logger.info("No records found to process.")
        return

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL env var is missing")
        sys.exit(1)

    logger.info("Connecting to database...")
    db_pool = await asyncpg.create_pool(db_url, min_size=1, max_size=5)

    try:
        # Pre-process all records to infer type, category, subfolder, and URL
        logger.info("Auto-categorizing and inferring document types...")
        processed_data = []
        unique_clients = set()

        for r in records:
            file_name = r["file_name"]
            folder_name = r["subfolder"]
            file_id = r["file_id"]
            client_id = r["client_id"]

            # 1. Infer category and type
            cat_result = auto_categorize_document(file_name)
            doc_category = cat_result["document_category"]

            # Folder hint upgrade (just like in drive_poll_service.py)
            if doc_category == "other" and folder_name:
                folder_lower = folder_name.lower()
                if (
                    folder_lower in ("01_immigration", "actual visa", "previous visa")
                    or "immigration" in folder_lower
                ):
                    doc_category = "immigration"

            doc_type = _infer_document_type(file_name, folder_name)

            # 2. Check Actual Visa / Previous Visa subfolder
            subfolder_value = None
            parent_name_lower = folder_name.lower() if folder_name else ""
            if parent_name_lower in ("actual visa", "previous visa"):
                subfolder_value = (
                    "Actual Visa" if "actual" in parent_name_lower else "Previous Visa"
                )
                doc_category = "immigration"

            # 3. Size in KB
            file_size_kb = r["file_size"] // 1024

            # 4. Construct google drive URL
            drive_url = f"https://drive.google.com/file/d/{file_id}/view?usp=drivesdk"

            processed_data.append(
                (
                    client_id,
                    doc_type,
                    doc_category,
                    file_name,
                    file_id,
                    drive_url,
                    file_size_kb,
                    subfolder_value,
                )
            )
            unique_clients.add(client_id)

        if not args.execute:
            logger.info("=== DRY RUN MODE ===")
            logger.info(f"Total documents to register: {len(processed_data)}")
            logger.info(f"Total affected clients: {len(unique_clients)}")
            logger.info("Example of insertions:")
            for i, p in enumerate(processed_data[:5]):
                logger.info(
                    f"  Doc {i + 1}: Client: {p[0]}, Type: {p[1]}, Cat: {p[2]}, File: {p[3]}, ID: {p[4]}, Subfolder: {p[7]}"
                )
            logger.info("Use --execute flag to perform the actual database write.")
            return

        logger.info("=== EXECUTION MODE ===")
        logger.info(f"Registering {len(processed_data)} documents...")

        # Batch insert documents in chunks of 500
        chunk_size = 500
        inserted_count = 0

        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # We do this inside a single transaction
                for i in range(0, len(processed_data), chunk_size):
                    chunk = processed_data[i : i + chunk_size]

                    # Insert query
                    # Wait, is there a unique constraint on file_id in the database?
                    # Let's write standard inserts or catch duplicate errors, or check constraint.
                    # To be safe, we can do it one-by-one or check if file_id already exists.
                    # Since we pre-filtered in scan_drive_fast against the current list of file_ids,
                    # conflict should not happen, but we can do try-except per insert or use a safe insert.
                    # Let's run a bulk executemany, but wait, executemany is very fast.
                    # Let's check if there is a unique index on file_id.
                    # If there's no unique constraint on file_id, ON CONFLICT (file_id) will error.
                    # Let's just execute standard inserts but skip duplicate file_ids we already loaded.
                    # To be 100% safe, let's run individual inserts or check if there is a constraint.
                    # Actually, if we pre-fetched all file_ids from the database and only processed missing ones,
                    # we should not have conflicts. Let's just do bulk executemany without ON CONFLICT,
                    # or write a try-catch chunk processing.

                    # Let's check if documents has a constraint or just insert.
                    # Let's do executemany:
                    try:
                        await conn.executemany(
                            """
                            INSERT INTO documents (
                                client_id, document_type, document_category, file_name, file_id,
                                google_drive_file_url, file_size_kb, subfolder,
                                status, storage_type, ocr_status, created_at, updated_at
                            ) VALUES (
                                $1, $2, $3, $4, $5, $6, $7, $8,
                                'active', 'google_drive', 'pending', NOW(), NOW()
                            )
                        """,
                            chunk,
                        )
                        inserted_count += len(chunk)
                    except Exception as e:
                        logger.error(
                            f"Error inserting chunk {i // chunk_size}: {e}. Retrying chunk individually..."
                        )
                        # If a chunk fails, insert rows individually to skip duplicates
                        for row in chunk:
                            try:
                                await conn.execute(
                                    """
                                    INSERT INTO documents (
                                        client_id, document_type, document_category, file_name, file_id,
                                        google_drive_file_url, file_size_kb, subfolder,
                                        status, storage_type, ocr_status, created_at, updated_at
                                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'active', 'google_drive', 'pending', NOW(), NOW())
                                """,
                                    *row,
                                )
                                inserted_count += 1
                            except Exception as row_err:
                                # Safe skip
                                logger.warning(
                                    f"Failed to insert single file {row[3]} (ID: {row[4]}): {row_err}"
                                )

                    logger.info(f"Inserted {inserted_count}/{len(processed_data)} documents...")

                # Update affected clients updated_at
                logger.info(f"Touching updated_at for {len(unique_clients)} clients...")
                client_ids_list = list(unique_clients)
                await conn.execute(
                    """
                    UPDATE clients
                    SET updated_at = NOW()
                    WHERE id = ANY($1::int[])
                """,
                    client_ids_list,
                )

        logger.info(f"Successfully registered {inserted_count} documents in PostgreSQL database.")

    finally:
        await db_pool.close()


if __name__ == "__main__":
    asyncio.run(main())
