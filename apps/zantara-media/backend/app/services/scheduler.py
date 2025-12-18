"""
ZANTARA MEDIA - Scheduler Service
Daily automation using APScheduler
"""

import logging
from datetime import datetime
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.services.content_orchestrator import content_orchestrator

logger = logging.getLogger(__name__)


class SchedulerService:
    """
    Manages scheduled tasks for automated content generation.

    Default Schedule:
    - Daily content generation: 6:00 AM Asia/Makassar (Bali time)
    """

    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.is_running = False

    async def start(self):
        """Start the scheduler."""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return

        logger.info("Starting scheduler...")

        self.scheduler = AsyncIOScheduler(timezone="Asia/Makassar")

        # Daily content generation at 6:00 AM Bali time
        self.scheduler.add_job(
            self._run_daily_pipeline,
            trigger=CronTrigger(hour=6, minute=0),
            id="daily_content_generation",
            name="Daily Content Generation Pipeline",
            replace_existing=True,
        )

        # Optional: Weekly cleanup at Sunday 2:00 AM
        self.scheduler.add_job(
            self._weekly_cleanup,
            trigger=CronTrigger(day_of_week="sun", hour=2, minute=0),
            id="weekly_cleanup",
            name="Weekly Database Cleanup",
            replace_existing=True,
        )

        self.scheduler.start()
        self.is_running = True

        logger.info("✓ Scheduler started successfully")
        logger.info("  → Daily content generation: 6:00 AM Bali time")
        logger.info("  → Weekly cleanup: Sunday 2:00 AM Bali time")

    async def stop(self):
        """Stop the scheduler."""
        if not self.is_running or not self.scheduler:
            return

        logger.info("Stopping scheduler...")
        self.scheduler.shutdown(wait=False)
        self.is_running = False
        logger.info("✓ Scheduler stopped")

    async def _run_daily_pipeline(self):
        """
        Run the daily content generation pipeline.

        This is the main scheduled task that runs every day.
        """
        logger.info("=" * 80)
        logger.info("SCHEDULED TASK: Daily Content Generation")
        logger.info(f"Triggered at: {datetime.now()}")
        logger.info("=" * 80)

        try:
            stats = await content_orchestrator.run_daily_pipeline()

            logger.info("\nScheduled task completed successfully")
            logger.info(f"  Articles generated: {stats['articles_generated']}")
            logger.info(f"  Articles published: {stats['articles_published']}")
            logger.info(f"  Duration: {stats['duration_seconds']:.2f}s")

            # Log errors if any
            if stats["errors"]:
                logger.error(f"  Errors occurred: {len(stats['errors'])}")
                for error in stats["errors"]:
                    logger.error(f"    - {error}")

        except Exception as e:
            logger.error(f"Scheduled task failed: {e}", exc_info=True)

    async def _weekly_cleanup(self):
        """
        Weekly database cleanup task.

        Cleans up old data to keep database healthy.
        """
        logger.info("=" * 80)
        logger.info("SCHEDULED TASK: Weekly Cleanup")
        logger.info(f"Triggered at: {datetime.now()}")
        logger.info("=" * 80)

        cleanup_stats = {
            "archived_content": 0,
            "failed_distributions_cleaned": 0,
            "old_logs_removed": 0,
            "errors": [],
        }

        try:
            # 1. Archive old published content (older than 90 days)
            archived = await self._archive_old_content(days=90)
            cleanup_stats["archived_content"] = archived
            logger.info(f"  Archived {archived} old content items")

            # 2. Clean up failed distributions (older than 7 days)
            cleaned = await self._cleanup_failed_distributions(days=7)
            cleanup_stats["failed_distributions_cleaned"] = cleaned
            logger.info(f"  Cleaned {cleaned} failed distributions")

            # 3. Remove old automation logs (older than 30 days)
            removed = await self._remove_old_logs(days=30)
            cleanup_stats["old_logs_removed"] = removed
            logger.info(f"  Removed {removed} old log entries")

            logger.info("Cleanup task completed successfully")
            logger.info(f"  Stats: {cleanup_stats}")

        except Exception as e:
            cleanup_stats["errors"].append(str(e))
            logger.error(f"Cleanup task failed: {e}", exc_info=True)

        return cleanup_stats

    async def _archive_old_content(self, days: int = 90) -> int:
        """
        Archive content older than specified days.

        In a full implementation, this would:
        - Move old published content to an archive table
        - Update content status to ARCHIVED
        - Optionally compress/store in cold storage
        """
        try:
            from app.db.connection import get_db_pool

            pool = await get_db_pool()
            async with pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE zantara_content
                    SET status = 'archived'
                    WHERE status = 'published'
                      AND published_at < NOW() - INTERVAL '%s days'
                    """,
                    days,
                )
                # Parse "UPDATE N" to get count
                if result and result.startswith("UPDATE "):
                    return int(result.split()[1])
        except Exception as e:
            logger.warning(f"Archive old content skipped: {e}")
        return 0

    async def _cleanup_failed_distributions(self, days: int = 7) -> int:
        """
        Clean up failed distribution records.

        Removes distribution records that failed more than N days ago,
        freeing up database space and keeping the queue clean.
        """
        try:
            from app.db.connection import get_db_pool

            pool = await get_db_pool()
            async with pool.acquire() as conn:
                result = await conn.execute(
                    """
                    DELETE FROM distributions
                    WHERE status = 'failed'
                      AND created_at < NOW() - INTERVAL '%s days'
                    """,
                    days,
                )
                if result and result.startswith("DELETE "):
                    return int(result.split()[1])
        except Exception as e:
            logger.warning(f"Cleanup failed distributions skipped: {e}")
        return 0

    async def _remove_old_logs(self, days: int = 30) -> int:
        """
        Remove old automation/scheduler logs.

        Cleans up log entries older than specified days to prevent
        unbounded log table growth.
        """
        try:
            from app.db.connection import get_db_pool

            pool = await get_db_pool()
            async with pool.acquire() as conn:
                result = await conn.execute(
                    """
                    DELETE FROM automation_logs
                    WHERE created_at < NOW() - INTERVAL '%s days'
                    """,
                    days,
                )
                if result and result.startswith("DELETE "):
                    return int(result.split()[1])
        except Exception as e:
            logger.warning(f"Remove old logs skipped: {e}")
        return 0

    async def trigger_manual_run(self) -> dict:
        """
        Trigger a manual run of the daily pipeline.

        This can be called via API endpoint for testing or manual generation.
        """
        logger.info("Manual pipeline trigger requested")

        try:
            stats = await content_orchestrator.run_daily_pipeline()
            return {
                "success": True,
                "stats": stats,
            }
        except Exception as e:
            logger.error(f"Manual pipeline run failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    def get_status(self) -> dict:
        """Get scheduler status."""
        if not self.scheduler:
            return {
                "running": False,
                "jobs": [],
            }

        jobs = []
        for job in self.scheduler.get_jobs():
            next_run = job.next_run_time
            jobs.append(
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run": next_run.isoformat() if next_run else None,
                    "trigger": str(job.trigger),
                }
            )

        return {
            "running": self.is_running,
            "jobs": jobs,
        }


# Singleton instance
scheduler_service = SchedulerService()
