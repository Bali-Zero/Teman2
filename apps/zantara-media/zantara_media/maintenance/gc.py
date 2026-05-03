"""
Tombstone garbage collector.
Sweeps garuda_index for files deleted on Drive, marks them archived in Postgres + Qdrant.
"""
import logging
import os

import asyncpg

logger = logging.getLogger(__name__)


async def run_gc(dry_run: bool = False, batch_size: int = 100) -> dict:
    """
    Sweep garuda_index, check each active file against Drive, mark archived if 404.
    Returns: {"checked": n, "archived": n, "errors": n}
    """
    from zantara_media.indexer.drive_client import DriveClient
    from zantara_media.indexer.qdrant_writer import QdrantWriter
    from zantara_media.alerts import send_critical_alert

    pool = await asyncpg.create_pool(dsn=os.environ["DATABASE_URL"], min_size=2, max_size=5)
    drive = DriveClient()
    qdrant = QdrantWriter()

    stats: dict = {"checked": 0, "archived": 0, "errors": 0}

    try:
        offset = 0
        while True:
            rows = await pool.fetch(
                "SELECT file_id FROM garuda_index WHERE archived = FALSE LIMIT $1 OFFSET $2",
                batch_size,
                offset,
            )
            if not rows:
                break

            for row in rows:
                file_id = row["file_id"]
                stats["checked"] += 1

                try:
                    exists = await drive.file_exists(file_id)
                    if not exists:
                        logger.info("GC: archiving deleted file %s", file_id)
                        if not dry_run:
                            await pool.execute(
                                "UPDATE garuda_index SET archived = TRUE, modified_at = NOW()"
                                " WHERE file_id = $1",
                                file_id,
                            )
                            await qdrant.mark_archived(file_id)
                        stats["archived"] += 1
                except Exception as e:
                    logger.error("GC error for file %s: %s", file_id, e)
                    stats["errors"] += 1

            offset += batch_size

        msg = (
            f"🧹 GARUDA GC: {stats['archived']} files archived, {stats['checked']} checked"
        )
        if stats["errors"]:
            msg += f", {stats['errors']} errors"
        logger.info(msg)

        # Send Telegram summary only if something was archived
        if stats["archived"] > 0:
            await send_critical_alert(msg)

    finally:
        await qdrant.close()
        await pool.close()

    return stats
