"""
GARUDA Indexer Orchestrator
Coordinates Drive changes polling, semaphore-bounded processing, and state management.
"""
import asyncio
import json
import logging
import os
import shutil
import subprocess
from contextlib import asynccontextmanager
from typing import Optional

import asyncpg

logger = logging.getLogger(__name__)

# --- Concurrency limits (from spec) ---
CONCURRENCY = {
    "drive_io": 4,
    "extract": 2,
    "vision": 1,     # qwen2.5vl is heavy
    "embed": 2,
}

BATCH_SIZE = int(os.getenv("CURATOR_BATCH_SIZE", "50"))
PREFLIGHT_MIN_DISK_GB = 5


async def preflight_checks() -> bool:
    """Returns True if safe to run, False if should abort."""
    # Check 1: core_guardian must NOT be running
    def _check_guardian() -> int:
        result = subprocess.run(
            ["pgrep", "-f", "core_guardian"],
            capture_output=True,
        )
        return result.returncode

    guardian_rc = await asyncio.to_thread(_check_guardian)
    if guardian_rc == 0:
        logger.warning("core_guardian is running — aborting preflight")
        return False

    # Check 2: disk free on /tmp >= 5 GB
    def _check_disk() -> int:
        usage = shutil.disk_usage("/tmp")
        return usage.free

    free_bytes = await asyncio.to_thread(_check_disk)
    min_bytes = PREFLIGHT_MIN_DISK_GB * 1024 ** 3
    if free_bytes < min_bytes:
        logger.warning(
            "Insufficient disk space on /tmp: %.1f GB free (need %d GB)",
            free_bytes / 1024 ** 3,
            PREFLIGHT_MIN_DISK_GB,
        )
        return False

    return True


@asynccontextmanager
async def pg_advisory_lock(conn: asyncpg.Connection, lock_key: str):
    """Acquire a Postgres advisory lock for the duration of the context."""
    lock_id = hash(lock_key) & 0x7FFFFFFF
    await conn.execute("SELECT pg_advisory_lock($1)", lock_id)
    try:
        yield
    finally:
        await conn.execute("SELECT pg_advisory_unlock($1)", lock_id)


async def load_state(worker_name: str, pool: asyncpg.Pool) -> dict:
    """Load worker state from garuda_indexer_state table."""
    row = await pool.fetchrow(
        "SELECT * FROM garuda_indexer_state WHERE worker_name = $1",
        worker_name,
    )
    return dict(row) if row else {}


async def save_state(worker_name: str, pool: asyncpg.Pool, updates: dict) -> None:
    """Persist worker state to garuda_indexer_state table."""
    await pool.execute(
        """
        UPDATE garuda_indexer_state
        SET last_change_page_token = $2,
            files_indexed_total = files_indexed_total + $3,
            files_indexed_last_run = $4,
            consecutive_failures = $5,
            last_run_completed_at = NOW(),
            last_error = $6::jsonb
        WHERE worker_name = $1
        """,
        worker_name,
        updates.get("last_change_page_token"),
        updates.get("files_delta", 0),
        updates.get("files_indexed_last_run", 0),
        updates.get("consecutive_failures", 0),
        json.dumps(updates.get("last_error")) if updates.get("last_error") else None,
    )


async def run_indexer(worker_name: str = "default") -> dict:
    """Main entry point for the GARUDA indexer.

    Returns a summary dict with keys:
        files_processed, files_indexed, files_skipped, errors
    """
    # 1. Pre-flight checks
    if not await preflight_checks():
        logger.info("Pre-flight failed, aborting run")
        return {"aborted": True, "reason": "preflight_failed"}

    # 2. Set up connections
    pg_pool = await asyncpg.create_pool(
        dsn=os.environ["DATABASE_URL"], min_size=2, max_size=10
    )

    # 3. Create semaphores
    semaphores = {
        "drive_io": asyncio.Semaphore(CONCURRENCY["drive_io"]),
        "extract": asyncio.Semaphore(CONCURRENCY["extract"]),
        "vision": asyncio.Semaphore(CONCURRENCY["vision"]),
        "embed": asyncio.Semaphore(CONCURRENCY["embed"]),
    }

    # 4. Init components
    from .drive_client import DriveClient
    from .embedder import Embedder
    from .qdrant_writer import QdrantWriter
    from .postgres_writer import PostgresWriter
    from .pipeline import Pipeline

    drive = DriveClient()
    embedder = Embedder()
    qdrant = QdrantWriter()
    pg_writer = PostgresWriter()
    pg_writer._pool = pg_pool  # reuse pool
    pipeline = Pipeline(embedder, qdrant, pg_writer, drive)

    stats = {
        "files_processed": 0,
        "files_indexed": 0,
        "files_skipped": 0,
        "errors": 0,
    }

    try:
        async with pg_pool.acquire() as conn:
            async with pg_advisory_lock(conn, f"garuda_indexer:{worker_name}"):
                # 5. Load state
                state = await load_state(worker_name, pg_pool)
                page_token = state.get("last_change_page_token")

                # 6. Catch-up mode: first run just bookmarks the current position
                if page_token is None:
                    logger.info("First run — bookmarking start page token")
                    token = await drive.get_start_page_token()
                    await pg_pool.execute(
                        "UPDATE garuda_indexer_state SET last_change_page_token = $2 WHERE worker_name = $1",
                        worker_name,
                        token,
                    )
                    return {"first_run": True, "token_saved": token}

                # 7. Stream changes and process
                next_token = page_token
                garuda_count = 0

                async for change in drive.list_changes(page_token):
                    if garuda_count >= BATCH_SIZE:
                        logger.info("Batch cap reached (%d files)", BATCH_SIZE)
                        break

                    # Update next_token from the change
                    if change.next_page_token:
                        next_token = change.next_page_token

                    # Only process GARUDA files
                    if change.file and not drive.is_under_garuda(change.file.parents):
                        continue

                    stats["files_processed"] += 1

                    # Handle tombstones
                    if change.is_tombstone:
                        logger.info("Tombstone: %s", change.file_id)
                        await qdrant.mark_archived(change.file_id)
                        await pg_writer.mark_archived(change.file_id)
                        stats["files_skipped"] += 1
                        continue

                    if change.file is None:
                        continue

                    # Check if already up-to-date by drive_version
                    stored_version = await pg_writer.get_drive_version(change.file.id)
                    if stored_version and stored_version >= change.file.version:
                        stats["files_skipped"] += 1
                        continue

                    # Process file through pipeline (bounded by drive_io semaphore)
                    async with semaphores["drive_io"]:
                        result = await pipeline.index_file_safe(change.file)

                    if result.status == "indexed":
                        stats["files_indexed"] += 1
                        garuda_count += 1
                    elif result.status == "error":
                        stats["errors"] += 1
                    else:
                        stats["files_skipped"] += 1

                    # Checkpoint: save state after each file
                    await save_state(
                        worker_name,
                        pg_pool,
                        {
                            "last_change_page_token": next_token,
                            "files_delta": 1 if result.status == "indexed" else 0,
                            "files_indexed_last_run": stats["files_indexed"],
                            "consecutive_failures": stats["errors"],
                        },
                    )

                # Final state save
                await save_state(
                    worker_name,
                    pg_pool,
                    {
                        "last_change_page_token": next_token,
                        "files_delta": stats["files_indexed"],
                        "files_indexed_last_run": stats["files_indexed"],
                        "consecutive_failures": stats["errors"],
                    },
                )

    finally:
        await embedder.close()
        await qdrant.close()
        await pg_writer.close()
        await pg_pool.close()

    return stats
