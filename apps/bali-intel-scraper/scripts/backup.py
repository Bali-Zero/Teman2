"""
Database backup script.

Automated backups with compression and retention management.
"""

import asyncio
import gzip
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from backend.core.logger import get_logger, LogAction
from config.settings import settings

logger = get_logger(__name__, component="backup")


class DatabaseBackup:
    """Manage database backups."""

    def __init__(
        self,
        backup_dir: str = "./backups",
        retention_days: int = 30,
        compress: bool = True,
    ):
        self.backup_dir = Path(backup_dir)
        self.retention_days = retention_days
        self.compress = compress

        # Ensure backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    async def create_backup(self, backup_name: str | None = None) -> Path:
        """Create a database backup."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = backup_name or f"backup_{timestamp}"

        backup_path = self.backup_dir / f"{backup_name}.sql"

        logger.info(f"Creating database backup: {backup_name}", action=LogAction.START)

        # Build pg_dump command
        cmd = [
            "pg_dump",
            "-h",
            settings.database.host,
            "-p",
            str(settings.database.port),
            "-U",
            settings.database.user,
            "-d",
            settings.database.name,
            "-F",
            "p",  # Plain text format
            "-f",
            str(backup_path),
        ]

        # Set PGPASSWORD environment variable
        env = os.environ.copy()
        env["PGPASSWORD"] = settings.database.password

        try:
            # Run pg_dump
            process = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                raise Exception(f"pg_dump failed: {stderr.decode()}")

            # Compress if requested
            if self.compress:
                compressed_path = await self._compress_backup(backup_path)
                backup_path = compressed_path

            logger.info(
                f"Backup created: {backup_path}",
                action=LogAction.END,
                metadata={"size_mb": backup_path.stat().st_size / (1024 * 1024)},
            )

            return backup_path

        except Exception as e:
            logger.error(f"Backup failed: {e}", action=LogAction.ERROR)
            raise

    async def _compress_backup(self, backup_path: Path) -> Path:
        """Compress backup file."""
        compressed_path = backup_path.with_suffix(".sql.gz")

        with open(backup_path, "rb") as f_in, gzip.open(compressed_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

        # Remove uncompressed file
        backup_path.unlink()

        return compressed_path

    async def restore_backup(self, backup_path: Path) -> None:
        """Restore database from backup."""
        logger.info(f"Restoring backup: {backup_path}", action=LogAction.START)

        # Decompress if needed
        if backup_path.suffix == ".gz":
            decompressed_path = backup_path.with_suffix("")

            with gzip.open(backup_path, "rb") as f_in, open(decompressed_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

            backup_path = decompressed_path

        # Build psql command
        cmd = [
            "psql",
            "-h",
            settings.database.host,
            "-p",
            str(settings.database.port),
            "-U",
            settings.database.user,
            "-d",
            settings.database.name,
            "-f",
            str(backup_path),
        ]

        env = os.environ.copy()
        env["PGPASSWORD"] = settings.database.password

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                raise Exception(f"psql restore failed: {stderr.decode()}")

            logger.info("Backup restored successfully", action=LogAction.END)

        finally:
            # Cleanup decompressed file if created
            if backup_path.suffix == ".sql" and backup_path.name.endswith(
                "_decompressed.sql"
            ):
                backup_path.unlink()

    async def cleanup_old_backups(self) -> int:
        """Remove backups older than retention period."""
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        removed = 0

        for backup_file in self.backup_dir.glob("backup_*.sql*"):
            # Extract timestamp from filename
            try:
                timestamp_str = backup_file.stem.split("_")[1:3]
                timestamp = datetime.strptime("_".join(timestamp_str), "%Y%m%d_%H%M%S")

                if timestamp < cutoff:
                    backup_file.unlink()
                    removed += 1
                    logger.info(
                        f"Removed old backup: {backup_file.name}",
                        action=LogAction.DELETE,
                    )
            except (ValueError, IndexError):
                continue

        return removed

    def list_backups(self) -> list[dict]:
        """List available backups."""
        backups = []

        for backup_file in sorted(self.backup_dir.glob("backup_*.sql*"), reverse=True):
            stat = backup_file.stat()
            backups.append(
                {
                    "name": backup_file.name,
                    "path": str(backup_file),
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )

        return backups


async def run_daily_backup() -> None:
    """Run daily backup task."""
    backup = DatabaseBackup()

    try:
        # Create backup
        backup_path = await backup.create_backup()

        # Cleanup old backups
        removed = await backup.cleanup_old_backups()

        logger.info(
            "Daily backup completed",
            action=LogAction.END,
            metadata={"backup_path": str(backup_path), "removed_old": removed},
        )

    except Exception as e:
        logger.error(f"Daily backup failed: {e}", action=LogAction.ERROR)
        raise


if __name__ == "__main__":
    asyncio.run(run_daily_backup())
