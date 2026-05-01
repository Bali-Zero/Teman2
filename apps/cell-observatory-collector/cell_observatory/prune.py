import asyncio
import structlog
from datetime import datetime, timezone, timedelta

from cell_observatory.config import Config
from cell_observatory.storage import Storage

log = structlog.get_logger(__name__)


async def prune_old_events(storage: Storage, retention_days: int) -> int:
    """Delete pulse_events older than retention_days. Cascade deletes classifications via FK."""
    assert storage._conn is not None
    cutoff_ms = int((datetime.now(timezone.utc) - timedelta(days=retention_days)).timestamp() * 1000)

    cur = await storage._conn.execute(
        "DELETE FROM pulse_classifications WHERE outbox_id IN "
        "(SELECT outbox_id FROM pulse_events WHERE pulse_timestamp < ?)",
        (cutoff_ms,),
    )
    deleted_class = cur.rowcount

    cur = await storage._conn.execute(
        "DELETE FROM pulse_events WHERE pulse_timestamp < ?", (cutoff_ms,)
    )
    deleted_events = cur.rowcount
    await storage._conn.commit()

    log.info("pruned old events", deleted_events=deleted_events, deleted_classifications=deleted_class)
    return deleted_events


async def main():
    cfg = Config.from_env()
    s = Storage(db_path=cfg.db_path)
    await s.init()
    try:
        await prune_old_events(s, cfg.retention_days)
    finally:
        await s.close()


if __name__ == "__main__":
    asyncio.run(main())
