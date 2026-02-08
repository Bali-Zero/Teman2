"""
Database partitioning for large tables.

Implements time-based partitioning for tables with high volume:
- Articles
- Scraping logs
- Analytics data
"""

from datetime import datetime, timedelta
from typing import List

from backend.db.connection import db
from backend.core.logger import get_logger, LogAction

logger = get_logger(__name__, component="partitioning")


class TablePartitioner:
    """Manage table partitioning."""

    PARTITION_INTERVALS = {"monthly": "MONTH", "daily": "DAY", "weekly": "WEEK"}

    def __init__(self):
        self.partitioned_tables = ["articles", "scraping_logs", "analytics"]

    async def setup_partitioning(
        self,
        table_name: str,
        partition_column: str = "created_at",
        interval: str = "monthly",
    ) -> None:
        """
        Setup range partitioning for a table.

        Args:
            table_name: Table to partition
            partition_column: Column to partition by
            interval: Partition interval (monthly, daily, weekly)
        """
        interval_sql = self.PARTITION_INTERVALS.get(interval, "MONTH")

        # Convert existing table to partitioned
        # Note: This requires creating a new table and migrating data

        logger.info(
            f"Setting up partitioning for {table_name}",
            action=LogAction.START,
            metadata={
                "table": table_name,
                "column": partition_column,
                "interval": interval,
            },
        )

        # Create partitioned table structure
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name}_partitioned (
            LIKE {table_name} INCLUDING ALL
        ) PARTITION BY RANGE ({partition_column});
        """

        await db.execute(create_sql)

        # Create initial partitions
        await self.create_partitions(
            table_name, partition_column, interval, months_ahead=3
        )

        logger.info(
            f"Partitioning setup complete for {table_name}", action=LogAction.END
        )

    async def create_partitions(
        self,
        table_name: str,
        partition_column: str,
        interval: str,
        months_ahead: int = 3,
    ) -> None:
        """Create partitions for upcoming months."""
        now = datetime.now()

        for i in range(months_ahead):
            start_date = (now.replace(day=1) + timedelta(days=32 * i)).replace(day=1)

            if interval == "monthly":
                end_date = (start_date + timedelta(days=32)).replace(day=1)
                partition_name = (
                    f"{table_name}_{start_date.year}_{start_date.month:02d}"
                )
            else:
                # Daily partitioning
                end_date = start_date + timedelta(days=1)
                partition_name = f"{table_name}_{start_date.year}_{start_date.month:02d}_{start_date.day:02d}"

            # Create partition
            partition_sql = f"""
            CREATE TABLE IF NOT EXISTS {partition_name}
            PARTITION OF {table_name}_partitioned
            FOR VALUES FROM ('{start_date.isoformat()}') 
            TO ('{end_date.isoformat()}');
            """

            try:
                await db.execute(partition_sql)
                logger.debug(
                    f"Created partition {partition_name}",
                    metadata={"table": table_name},
                )
            except Exception as e:
                logger.warning(
                    f"Failed to create partition {partition_name}: {e}",
                    action=LogAction.ERROR,
                )

    async def drop_old_partitions(
        self, table_name: str, retention_months: int = 12
    ) -> int:
        """Drop partitions older than retention period."""
        cutoff_date = datetime.now() - timedelta(days=30 * retention_months)

        # Get list of partitions
        partitions_sql = f"""
        SELECT tablename FROM pg_tables 
        WHERE tablename LIKE '{table_name}_%' 
        AND schemaname = 'public';
        """

        partitions = await db.fetch(partitions_sql)
        dropped = 0

        for partition in partitions:
            partition_name = partition["tablename"]

            # Extract date from partition name
            try:
                parts = partition_name.split("_")
                if len(parts) >= 3:
                    year = int(parts[-2])
                    month = int(parts[-1])
                    partition_date = datetime(year, month, 1)

                    if partition_date < cutoff_date:
                        drop_sql = f"DROP TABLE IF EXISTS {partition_name};"
                        await db.execute(drop_sql)
                        dropped += 1

                        logger.info(
                            f"Dropped old partition {partition_name}",
                            action=LogAction.DELETE,
                        )
            except (ValueError, IndexError):
                continue

        return dropped

    async def get_partition_stats(self, table_name: str) -> List[dict]:
        """Get statistics for table partitions."""
        stats_sql = f"""
        SELECT 
            schemaname,
            tablename,
            pg_size_pretty(pg_total_relation_size(tablename)) as size,
            pg_total_relation_size(tablename) as size_bytes
        FROM pg_tables
        WHERE tablename LIKE '{table_name}_%'
        ORDER BY tablename;
        """

        return await db.fetch(stats_sql)

    async def maintain_partitions(self) -> dict:
        """Run partition maintenance tasks."""
        results = {}

        for table in self.partitioned_tables:
            try:
                # Create new partitions
                await self.create_partitions(table, "created_at", "monthly")

                # Drop old partitions
                dropped = await self.drop_old_partitions(table, retention_months=24)

                # Get stats
                stats = await self.get_partition_stats(table)

                results[table] = {
                    "partitions": len(stats),
                    "dropped": dropped,
                    "total_size": sum(s["size_bytes"] for s in stats),
                }

            except Exception as e:
                logger.error(
                    f"Partition maintenance failed for {table}: {e}",
                    action=LogAction.ERROR,
                )
                results[table] = {"error": str(e)}

        return results


partitioner = TablePartitioner()


async def setup_partitioning(
    table_name: str, partition_column: str = "created_at", interval: str = "monthly"
) -> None:
    """Setup partitioning for a table."""
    await partitioner.setup_partitioning(table_name, partition_column, interval)


__all__ = [
    "TablePartitioner",
    "partitioner",
    "setup_partitioning",
]
