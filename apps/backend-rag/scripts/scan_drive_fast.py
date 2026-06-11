#!/usr/bin/env python3
"""
Nuzantara Fast Google Drive Scanner
----------------------------------
Performs a deep, recursive scan starting from the physical root folders
of all active clients in the database (1,408 clients) in parallel.

Uses independent connection pools per worker task to avoid SSL failures.
"""

import asyncio
import logging
import os
import sys
import time
from typing import Any

import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("scan_drive_fast")

from pathlib import Path

base_path = Path(__file__).resolve().parent.parent

# Dynamic environment bootstrapping
SECRETS_SA_PATH = str(base_path.parent / ".secrets/nuzantara-google-drive-sa.json")
if os.path.exists(SECRETS_SA_PATH):
    with open(SECRETS_SA_PATH) as f:
        os.environ["GOOGLE_CREDENTIALS_JSON"] = f.read()
else:
    logger.error(f"Credentials not found at {SECRETS_SA_PATH}")
    sys.exit(1)

os.environ["GDRIVE_INDIVIDUALS_FOLDER_ID"] = "1mNi2FkhZqP9inJH2Y1taXLCgS95UkYk4"
os.environ["GDRIVE_COMPANIES_FOLDER_ID"] = "1rLlr2G7TdNUmmvQ_xN9pZQLbPrDFjUsW"
os.environ["GOOGLE_DRIVE_ROOT_FOLDER_ID"] = "1mNi2FkhZqP9inJH2Y1taXLCgS95UkYk4"

sys.path.append(str(base_path))
import dotenv

dotenv.load_dotenv(str(base_path / ".env"))

from backend.services.integrations.service_account_drive_service import ServiceAccountDriveService


# Async-safe Rate Limiter
class AsyncRateLimiter:
    def __init__(self, rate: int, period: float = 1.0):
        self.rate = rate
        self.period = period
        self.allowance = float(rate)
        self.last_check = asyncio.get_event_loop().time()
        self.lock = asyncio.Lock()

    async def wait(self):
        async with self.lock:
            current = asyncio.get_event_loop().time()
            time_passed = current - self.last_check
            self.last_check = current
            self.allowance += time_passed * (self.rate / self.period)
            if self.allowance > self.rate:
                self.allowance = float(self.rate)

            if self.allowance < 1.0:
                sleep_time = (1.0 - self.allowance) * (self.period / self.rate)
                await asyncio.sleep(sleep_time)
                self.allowance = 0.0
            else:
                self.allowance -= 1.0


# 60 calls/sec is extremely fast and safe (Google allows up to 200/sec)
limiter = AsyncRateLimiter(rate=60, period=1.0)


async def list_folder_contents_async(
    drive: ServiceAccountDriveService, folder_id: str
) -> list[dict[str, Any]]:
    """List files and folders inside a folder sequentially with retries."""
    items = []
    page_token = None
    query = f"'{folder_id}' in parents and trashed=false"
    max_retries = 3

    while True:
        success = False
        for attempt in range(max_retries):
            try:
                await limiter.wait()
                request = drive.service.files().list(
                    q=query,
                    fields="nextPageToken, files(id, name, mimeType, size)",
                    pageSize=1000,
                    pageToken=page_token,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                result = await asyncio.to_thread(request.execute)
                items.extend(result.get("files", []))
                page_token = result.get("nextPageToken")
                success = True
                break
            except Exception as e:
                backoff = (attempt + 1) * 2.0
                logger.warning(
                    f"Error listing folder {folder_id} (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {backoff}s..."
                )
                await asyncio.sleep(backoff)

        if not success:
            logger.error(f"Failed to list folder {folder_id} after {max_retries} attempts.")
            break

        if not page_token:
            break

    return items


async def scan_folder_recursive(
    drive: ServiceAccountDriveService,
    folder_id: str,
    client_id: int,
    client_name: str,
    path: str,
    existing_file_ids: set[str],
    orphans: list[dict[str, Any]],
):
    """Recursively scan a GDrive folder and add missing files to orphans."""
    contents = await list_folder_contents_async(drive, folder_id)

    for item in contents:
        item_id = item["id"]
        item_name = item["name"]
        mime_type = item.get("mimeType", "")

        if mime_type == "application/vnd.google-apps.folder":
            sub_path = f"{path}/{item_name}" if path else item_name
            await scan_folder_recursive(
                drive, item_id, client_id, client_name, sub_path, existing_file_ids, orphans
            )
        else:
            if mime_type.startswith("video/") or mime_type.startswith("audio/"):
                continue

            file_size = int(item.get("size", 0))
            if item_id not in existing_file_ids:
                orphans.append(
                    {
                        "client_id": client_id,
                        "client_name": client_name,
                        "subfolder": path or "Root",
                        "file_name": item_name,
                        "file_id": item_id,
                        "file_size": file_size,
                        "mime_type": mime_type,
                    }
                )


async def worker(
    worker_id: int,
    queue: asyncio.Queue,
    existing_file_ids: set[str],
    all_discovered_files: list[dict[str, Any]],
    progress: dict[str, int],
):
    """Worker task that processes clients from the queue using its own Drive service instance."""
    # Instantiate service specific to this worker to avoid shared connection SSL errors!
    drive = ServiceAccountDriveService()

    while True:
        try:
            client = queue.get_nowait()
        except asyncio.QueueEmpty:
            break

        client_id = client["id"]
        client_name = client["full_name"]
        root_folder_id = client["google_drive_folder_id"]

        progress["scanned"] += 1
        curr_scanned = progress["scanned"]
        curr_total = progress["total"]

        if curr_scanned % 20 == 0 or curr_scanned == curr_total:
            logger.info(f"Progress: [{curr_scanned}/{curr_total}] clients processed...")

        try:
            client_orphans = []
            await scan_folder_recursive(
                drive=drive,
                folder_id=root_folder_id,
                client_id=client_id,
                client_name=client_name,
                path="",
                existing_file_ids=existing_file_ids,
                orphans=client_orphans,
            )
            if client_orphans:
                all_discovered_files.extend(client_orphans)
                logger.info(
                    f"  Worker {worker_id}: Client {client_id} ({client_name}) - Found {len(client_orphans)} new files!"
                )
        except Exception as e:
            logger.error(
                f"  Worker {worker_id}: Failed to scan client {client_id} ({client_name}) root folder {root_folder_id}: {e}"
            )
        finally:
            queue.task_done()


async def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL env var is missing")
        sys.exit(1)

    db_pool = await asyncpg.create_pool(db_url, min_size=1, max_size=2)

    try:
        async with db_pool.acquire() as conn:
            # 1. Pre-fetch all existing file IDs from DB (O(1) matching)
            logger.info("Pre-fetching existing file IDs from database...")
            rows = await conn.fetch("SELECT file_id FROM documents WHERE file_id IS NOT NULL")
            existing_file_ids = {r["file_id"] for r in rows}
            logger.info(f"Loaded {len(existing_file_ids)} file IDs from DB")

            # 2. Fetch all active clients with non-null folder IDs
            logger.info("Fetching active clients with folders...")
            clients_query = """
                SELECT id, full_name, google_drive_folder_id
                FROM clients
                WHERE google_drive_folder_id IS NOT NULL AND deleted_at IS NULL
                ORDER BY id
            """
            active_clients = await conn.fetch(clients_query)
            logger.info(
                f"Found {len(active_clients)} active clients with Google Drive folders to scan"
            )

            # 3. Queue setup
            queue = asyncio.Queue()
            for c in active_clients:
                queue.put_nowait(dict(c))

            progress = {"scanned": 0, "total": len(active_clients)}
            all_discovered_files = []

            # 4. Launch concurrent workers
            num_workers = 25
            logger.info(f"Launching {num_workers} concurrent workers for deep scan...")

            workers = [
                asyncio.create_task(
                    worker(i, queue, existing_file_ids, all_discovered_files, progress)
                )
                for i in range(num_workers)
            ]

            await asyncio.gather(*workers)
            await queue.join()

            # 5. Write Report to Desktop
            report_path = "/Users/nuzantara/Desktop/nuzantara_drive_scan_report.txt"
            logger.info(f"Writing report to {report_path}...")

            # Sort files by client_id and subfolder path for readability
            all_discovered_files.sort(
                key=lambda x: (x["client_id"], x["subfolder"], x["file_name"])
            )

            with open(report_path, "w") as rf:
                rf.write("=================================================================\n")
                rf.write(
                    " REPORT DI SCANSIONE GOOGLE DRIVE PROFONDO - FILE NON ANCORA TRASCRITTI \n"
                )
                rf.write("=================================================================\n\n")
                rf.write(f"Data Scansione: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                rf.write(f"Clienti attivi scansionati ricorsivamente: {len(active_clients)}\n")
                rf.write(
                    f"File totali scoperti non presenti nel database: {len(all_discovered_files)}\n\n"
                )

                if all_discovered_files:
                    rf.write("Dettaglio dei file orfani trovati:\n")
                    rf.write("----------------------------------\n")
                    for file in all_discovered_files:
                        rf.write(f"Client: {file['client_id']} - {file['client_name']}\n")
                        rf.write(f"  Percorso Fisico: {file['subfolder']}\n")
                        rf.write(f"  File: {file['file_name']}\n")
                        rf.write(f"  Dimensione: {file['file_size']} bytes\n")
                        rf.write(f"  Google Drive ID: {file['file_id']}\n")
                        rf.write("  Stato nel DB: MANCANTE\n")
                        rf.write("----------------------------------\n")
                else:
                    rf.write(
                        "Ottimo! Tutti i file presenti ricorsivamente su Google Drive sono già registrati e indicizzati nel database.\n"
                    )

            logger.info(f"Report written successfully to {report_path}. Done!")
    finally:
        await db_pool.close()


if __name__ == "__main__":
    asyncio.run(main())
