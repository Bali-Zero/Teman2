"""
🤖 AUTONOMOUS SCHEDULER SERVICE
Background tasks that run while the backend is active on Fly.io.

⚠️ AUDIT 2026-03-16: With auto_stop=true (min_machines=0), the backend shuts
down after ~5min of inattivity. Only short-interval tasks (<=5min) survive.
All long-interval tasks (>=6h) have been migrated to OpenClaw cron on Pro (H24).

Active Tasks (survive auto_stop):
- Backend Self-Healing Agent: health monitoring (every 5min)
- Golden Routes Seeder: seed query patterns (one-time at startup)

Disabled Tasks (migrated to OpenClaw cron):
- Conversation Trainer: git subprocess won't work on Fly.io
- Daily Ops Autopilot: BUG (localhost:8000 = self), OpenClaw handles correctly
- Renewal Alerts: 12h interval, covered by practice-lifecycle-check cron
- Birthday Notifier: 24h interval, covered by client-health-monitor cron
- Conversation Cleanup: 24h interval, migrated to OpenClaw cron
- Auto-Ingestion: handled by bali-intel-scraper on Pro
- Drive Changes Polling: migrated to OpenClaw cron

Leader Election:
- Uses Redis SET NX EX to ensure only one instance executes each task
- Safe across multiple Fly.io machines and uvicorn workers
- Falls back to normal execution if Redis is unavailable
"""

import asyncio
import contextlib
import logging
import os
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Module-level persistent HTTP client for background tasks
_client: httpx.AsyncClient | None = None


def _get_client(timeout: float = 30.0) -> httpx.AsyncClient:
    """Get or create the shared async client for scheduler tasks."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=timeout,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _client


async def close_scheduler_client() -> None:
    """Close the module-level async client."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
    logger.info("AutonomousScheduler module HTTP client closed.")


# Unique ID for this worker instance (machine + process)
_WORKER_ID = f"{os.getenv('FLY_MACHINE_ID', 'local')}:{os.getpid()}:{uuid.uuid4().hex[:8]}"

# Redis key prefix for task locks
_LOCK_PREFIX = "nuzantara:scheduler:lock:"


async def _get_redis() -> Any:
    """Get a Redis client for leader election via RedisManager. Returns None if unavailable."""
    try:
        from backend.core.redis_manager import RedisManager

        manager = RedisManager.get_instance()
        client = manager.get_async_client()
        if client is not None:
            manager.register_component("scheduler_locks", "active")
        return client
    except Exception as e:
        logger.debug("Failed to get Redis client: %s", e)
        return None


async def _acquire_task_lock(task_name: str, ttl_seconds: int) -> bool:
    """
    Try to acquire a distributed lock for a task.

    Uses Redis SET NX EX: only one worker wins per interval.
    Lock auto-expires after ttl_seconds (= task interval).

    Returns True if this worker acquired the lock (should run the task).
    Returns True if Redis is unavailable (fallback: run anyway, best effort).
    """
    client = await _get_redis()
    if client is None:
        return True  # No Redis = no coordination, run anyway

    lock_key = f"{_LOCK_PREFIX}{task_name}"
    try:
        acquired = await client.set(lock_key, _WORKER_ID, nx=True, ex=ttl_seconds)
        return bool(acquired)
    except Exception as e:
        logger.debug("Lock acquisition error for %s: %s", task_name, e)
        return True  # On error, run anyway


@dataclass
class ScheduledTask:
    """A scheduled autonomous task"""

    name: str
    interval_seconds: int
    task_func: Callable[[], Coroutine[Any, Any, Any]]
    enabled: bool = True
    last_run: datetime | None = None
    run_count: int = 0
    error_count: int = 0
    last_error: str | None = None
    _task: asyncio.Task | None = field(default=None, repr=False)


class AutonomousScheduler:
    """
    Centralized scheduler for all autonomous agents.

    Features:
    - Configurable intervals per task
    - Error tracking and recovery
    - Graceful shutdown
    - Task status monitoring
    """

    def __init__(self) -> None:
        self.tasks: dict[str, ScheduledTask] = {}
        self._running = False
        self._shutdown_event = asyncio.Event()

        logger.info("🤖 AutonomousScheduler initialized")

    def register_task(
        self,
        name: str,
        task_func: Callable[[], Coroutine[Any, Any, Any]],
        interval_seconds: int,
        enabled: bool = True,
    ) -> None:
        """
        Register a new scheduled task.

        Args:
            name: Unique task name
            task_func: Async function to execute
            interval_seconds: Interval between runs
            enabled: Whether task is enabled
        """
        self.tasks[name] = ScheduledTask(
            name=name,
            interval_seconds=interval_seconds,
            task_func=task_func,
            enabled=enabled,
        )
        logger.info(
            "📋 Registered task: %s (interval=%ss, enabled=%s)", name, interval_seconds, enabled
        )

    async def _run_task_loop(self, task: ScheduledTask) -> None:
        """Run a single task in a loop"""
        logger.info(f"🚀 Starting task loop: {task.name}")

        # Initial delay to stagger task starts (avoid thundering herd)
        initial_delay = hash(task.name) % 60  # 0-60 seconds
        await asyncio.sleep(initial_delay)

        while not self._shutdown_event.is_set():
            if not task.enabled:
                await asyncio.sleep(60)  # Check again in 1 minute
                continue

            try:
                # Leader election: only one worker runs each task
                lock_ttl = max(task.interval_seconds, 30)  # Lock for at least 30s
                if not await _acquire_task_lock(task.name, lock_ttl):
                    logger.debug(f"⏭️ Task {task.name} locked by another worker, skipping")
                    # Still wait the full interval before trying again
                    try:
                        await asyncio.wait_for(
                            self._shutdown_event.wait(),
                            timeout=task.interval_seconds,
                        )
                        break
                    except asyncio.TimeoutError:
                        pass  # timeout elapsed — retry task
                    continue

                logger.info(f"⏰ Running scheduled task: {task.name}")
                task.last_run = datetime.now(tz=timezone.utc)

                # Run with timeout (max 30 minutes per task)
                await asyncio.wait_for(task.task_func(), timeout=1800)

                task.run_count += 1
                logger.info(f"✅ Task completed: {task.name} (run #{task.run_count})")

            except asyncio.TimeoutError:
                task.error_count += 1
                task.last_error = "Task timed out after 30 minutes"
                logger.error(f"⏱️ Task timeout: {task.name}")

            except asyncio.CancelledError:
                logger.info(f"🛑 Task cancelled: {task.name}")
                break

            except Exception as e:
                task.error_count += 1
                task.last_error = str(e)
                logger.error(f"❌ Task error: {task.name} - {e}")

            # Wait for next interval or shutdown
            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=task.interval_seconds)
                # If we get here, shutdown was signaled
                break
            except asyncio.TimeoutError:
                # Normal timeout, continue loop
                pass

    async def start(self) -> None:
        """Start all enabled scheduled tasks"""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True
        self._shutdown_event.clear()

        logger.info(f"🚀 Starting AutonomousScheduler with {len(self.tasks)} tasks")

        for task in self.tasks.values():
            if task.enabled:
                task._task = asyncio.create_task(
                    self._run_task_loop(task),
                    name=f"scheduler_{task.name}",
                )
                logger.info(f"   ✅ Started: {task.name}")
            else:
                logger.info(f"   ⏸️ Skipped (disabled): {task.name}")

    async def stop(self) -> None:
        """Stop all scheduled tasks gracefully"""
        if not self._running:
            return

        logger.info("🛑 Stopping AutonomousScheduler...")
        self._shutdown_event.set()

        # Cancel all running tasks
        for task in self.tasks.values():
            if task._task and not task._task.done():
                task._task.cancel()
                with contextlib.suppress(asyncio.CancelledError, asyncio.TimeoutError):
                    await asyncio.wait_for(task._task, timeout=5)

        self._running = False
        logger.info("✅ AutonomousScheduler stopped")

    def get_status(self) -> dict[str, Any]:
        """Get scheduler status and task statistics"""
        return {
            "running": self._running,
            "task_count": len(self.tasks),
            "tasks": {
                name: {
                    "enabled": task.enabled,
                    "interval_seconds": task.interval_seconds,
                    "last_run": task.last_run.isoformat() if task.last_run else None,
                    "run_count": task.run_count,
                    "error_count": task.error_count,
                    "last_error": task.last_error,
                    "status": "running" if task._task and not task._task.done() else "stopped",
                }
                for name, task in self.tasks.items()
            },
        }

    def enable_task(self, name: str) -> bool:
        """Enable a task"""
        if name in self.tasks:
            self.tasks[name].enabled = True
            logger.info("✅ Task enabled: %s", name)
            return True
        return False

    def disable_task(self, name: str) -> bool:
        """Disable a task"""
        if name in self.tasks:
            self.tasks[name].enabled = False
            logger.info("⏸️ Task disabled: %s", name)
            return True
        return False


# Global scheduler instance
_scheduler: AutonomousScheduler | None = None


def get_autonomous_scheduler() -> AutonomousScheduler:
    """Get or create the global scheduler instance"""
    global _scheduler
    if _scheduler is None:
        _scheduler = AutonomousScheduler()
    return _scheduler


async def create_and_start_scheduler(
    db_pool,
    ai_client,
    conversation_trainer_enabled: bool = False,  # DISABLED (audit 2026-03-16): git subprocess on Fly.io ephemeral container
    conversation_cleanup_enabled: bool = False,  # DISABLED (audit 2026-03-16): 24h > auto_stop uptime. Migrated to OpenClaw cron.
) -> AutonomousScheduler:
    """
    Create and start the autonomous scheduler with the surviving agents.

    Necropsy 2026-07-14: params for retired tasks (search_service,
    auto_ingestion_enabled, self_healing_enabled) were removed with their
    blocks — the sole caller (_init_background_services, §10) is commented out.

    Args:
        db_pool: Database connection pool
        ai_client: ZantaraAIClient instance
        *_enabled: Enable/disable individual tasks

    Returns:
        Running AutonomousScheduler instance
    """
    scheduler = get_autonomous_scheduler()

    # 1. AUTO-INGESTION — RETIRED 2026-07-14 (scheduler-necropsy): never worked
    # (scrape_source crashed, ingest_content was a fake-success stub) and wrote to
    # intel_articles, NOT the RAG collections. The real RAG-freshness gap is a
    # product decision tracked in modus PENDING-ARMS. AutoIngestionOrchestrator
    # class stays importable (routers/agents.py imports it at module level).

    # 2. BACKEND SELF-HEALING — MOVED to the live init path 2026-07-14
    # (service_initializer §10e, scheduler-necropsy): this engine has been dead
    # since 2026-02-11, so the 'Active' claim above it was a lie for 5 months.
    # The reduced agent (GCAction + stats visibility) now runs per-machine.

    # ═══════════════════════════════════════════════════════════════════════════
    # 3. CONVERSATION TRAINER AGENT (every 6 hours)
    # ═══════════════════════════════════════════════════════════════════════════
    if conversation_trainer_enabled and db_pool:
        try:
            from backend.agents.agents.conversation_trainer import ConversationTrainer

            trainer = ConversationTrainer(
                db_pool=db_pool,
                zantara_client=ai_client,
            )

            async def run_conversation_trainer() -> None:
                # 1. Analyze last 7 days of high-rated conversations
                analysis = await trainer.analyze_winning_patterns(days_back=7)
                if not analysis:
                    logger.info("No high-rated conversations found in last 7 days")
                    return

                logger.info(
                    f"🎓 Conversation Trainer found {len(analysis.get('patterns', []))} patterns",
                )

                # 2. Generate improved prompt based on analysis
                try:
                    improved_prompt = await trainer.generate_prompt_update(analysis)
                    if not improved_prompt:
                        logger.warning("Failed to generate improved prompt")
                        return

                    logger.info("✅ Generated improved prompt from conversation analysis")

                    # 3. Create PR with improvements
                    pr_branch = await trainer.create_improvement_pr(improved_prompt, analysis)
                    logger.info("✅ Conversation Trainer: PR %s created", pr_branch)

                except Exception as e:
                    logger.error(
                        "Error in Conversation Trainer prompt generation/PR creation: %s",
                        e,
                        exc_info=True,
                    )

            scheduler.register_task(
                name="conversation_trainer",
                task_func=run_conversation_trainer,
                interval_seconds=21600,  # 6 hours
                enabled=False,  # DISABLED (audit 2026-03-16): git subprocess on Fly.io ephemeral container
            )
            logger.info("⏸️ Conversation Trainer registered but DISABLED (migrated to OpenClaw)")
        except Exception as e:
            logger.error("❌ Failed to register Conversation Trainer: %s", e)

    # 5. GOLDEN ROUTES SEEDER — RETIRED 2026-07-14 (scheduler-necropsy): it
    # would have seeded rows nobody reads — GoldenRouterService is never
    # instantiated in the app and document_ids were never populated. The orphan
    # service+table (wire-or-delete) is tracked in modus PENDING-ARMS.

    # 6. RENEWAL ALERTS — RETIRED 2026-07-14 (scheduler-necropsy): the old
    # comment claimed coverage by 'OpenClaw practice-lifecycle-check' (false);
    # the REAL live coverage is crm_automation_engine.py module 'renewals'
    # (Pro crontab 23:00 UTC). This dead block duplicated that logic.

    # ═══════════════════════════════════════════════════════════════════════════
    # TASK 8: BIRTHPLACE ENRICHMENT (Ollama)
    # Enriches client birthplace with cultural context for personalized conversations
    # Runs daily at ~22:00 Bali time (after work hours, when Ollama has capacity)
    # ═══════════════════════════════════════════════════════════════════════════
    # Skip in production (Ollama not available on Fly.io)
    _is_production = os.getenv("ENVIRONMENT", "").lower() == "production"
    if _is_production:
        logger.debug("Birthplace Enrichment disabled in production (no Ollama)")
    else:
        try:
            from backend.services.crm.birthplace_enrichment_service import (
                run_birthplace_enrichment_task,
            )

            async def run_birthplace_enrichment() -> None:
                try:
                    stats = await run_birthplace_enrichment_task(db_pool)
                    logger.info(f"🎭 Birthplace Enrichment: {stats.get('successful', 0)} enriched")
                except Exception as e:
                    logger.error("❌ Birthplace Enrichment error: %s", e, exc_info=True)

            scheduler.register_task(
                name="birthplace_enrichment",
                task_func=run_birthplace_enrichment,
                interval_seconds=86400,  # 24 hours
                enabled=True,
            )
            logger.info("✅ Birthplace Enrichment registered (24h interval)")
        except Exception as e:
            logger.error("❌ Failed to register Birthplace Enrichment: %s", e)

    # ═══════════════════════════════════════════════════════════════════════════
    # TASK 9: BIRTHDAY EMAIL SERVICE
    # Sends personalized birthday emails to clients in their language
    # Runs daily at ~08:00 Bali time (morning greeting)
    # ═══════════════════════════════════════════════════════════════════════════
    try:
        from backend.services.crm.birthday_notifier_service import (
            run_birthday_notifier_task,
        )

        async def run_birthday_notifier() -> None:
            try:
                stats = await run_birthday_notifier_task(db_pool)
                logger.info(f"🎂 Birthday Notifier: {stats.get('sent', 0)} emails sent")
            except Exception as e:
                logger.error("❌ Birthday Notifier error: %s", e, exc_info=True)

        scheduler.register_task(
            name="birthday_notifier",
            task_func=run_birthday_notifier,
            interval_seconds=86400,  # 24 hours
            enabled=False,  # DISABLED (audit 2026-03-16): 24h > auto_stop uptime. Covered by OpenClaw client-health-monitor.
        )
        logger.info("⏸️ Birthday Notifier registered but DISABLED (migrated to OpenClaw)")
    except Exception as e:
        logger.error("❌ Failed to register Birthday Notifier: %s", e)

    # ═══════════════════════════════════════════════════════════════════════════
    # TASK 10: CONVERSATION CLEANUP (daily)
    # NOTE (scheduler-necropsy 2026-07-14): this dead block's 30d/7d values are
    # STALE — the LIVE coverage is POST /api/admin/conversation-cleanup
    # (admin_conversation_cleanup.py: delete >90d, anonymize >30d, OpenClaw cron).
    # Do not cite these numbers in UU PDP retention reviews.
    # ═══════════════════════════════════════════════════════════════════════════
    if conversation_cleanup_enabled and db_pool:
        try:
            from backend.jobs.conversation_cleanup import cleanup_conversations

            async def run_conversation_cleanup() -> None:
                try:
                    result = await cleanup_conversations(
                        retention_days=30,
                        anonymize_days=7,
                    )
                    if result["success"]:
                        logger.info(
                            f"🧹 Conversation cleanup: {result['deleted_count']} deleted, "
                            f"{result['anonymized_count']} anonymized",
                        )
                except Exception as e:
                    logger.error("❌ Conversation cleanup error: %s", e, exc_info=True)

            scheduler.register_task(
                name="conversation_cleanup",
                task_func=run_conversation_cleanup,
                interval_seconds=86400,
                enabled=True,
            )
            logger.info("✅ Conversation Cleanup registered (24h interval)")
        except Exception as e:
            logger.error("❌ Failed to register Conversation Cleanup: %s", e)

    # TASK 11 DAILY OPS AUTOPILOT — RETIRED 2026-07-14 (scheduler-necropsy):
    # it POSTed to an HTTP route the MCP server (stdio-only) never exposed, the
    # OpenClaw cron that replaced it was frozen 2026-04-30 (zombie heartbeat
    # archived 05-19). Expiry reminders live in scripts/expiry_alerter.py.
    # Residual gaps (auto-compose intel articles, daily ops digest) are a
    # business decision tracked in modus PENDING-ARMS.

    # ═══════════════════════════════════════════════════════════════════════════
    # TASK 12: DRIVE CHANGES POLLING (every 5 minutes)
    # Detects files added directly to Google Drive client folders
    # and dispatches OCR extraction automatically
    # ═══════════════════════════════════════════════════════════════════════════
    try:
        from backend.services.crm.drive_poll_service import poll_drive_changes

        async def run_drive_poll() -> None:
            try:
                result = await poll_drive_changes()
                processed = result.get("processed", 0)
                if processed > 0:
                    logger.info("📂 Drive Poll: %s new files processed for OCR", processed)
            except Exception as e:
                logger.error("Drive Poll error: %s", e, exc_info=True)

        scheduler.register_task(
            name="drive_changes_poll",
            task_func=run_drive_poll,
            interval_seconds=300,  # 5 minutes
            enabled=False,  # DISABLED 2026-03-22; since re-homed to the dedicated Fly process group drive_poll_worker (fly.toml) — the old 'Air cron' note was stale, Air is decommissioned 2026-05-05.
        )
        logger.info("⏸️ Drive Changes Polling DISABLED (lives in the drive_poll_worker Fly process group)")
    except Exception as e:
        logger.error("Failed to register Drive Changes Polling: %s", e)

    # ═══════════════════════════════════════════════════════════════════════════
    # KG INCREMENTAL BUILDER (daily — disabled on Fly.io, run via Air/Pro cron)
    # ENABLE_KG_INCREMENTAL=true to activate. Uses Gemini Free Tier (15 RPM, 1500/day).
    # ═══════════════════════════════════════════════════════════════════════════
    kg_incremental_enabled = os.getenv("ENABLE_KG_INCREMENTAL", "false").lower() in (
        "true",
        "1",
        "yes",
    )
    if kg_incremental_enabled and db_pool:
        try:
            from backend.services.knowledge_graph.incremental_builder import KGIncrementalBuilder

            kg_builder = KGIncrementalBuilder(db_pool=db_pool)

            async def run_kg_incremental() -> None:
                await kg_builder.run_incremental_extraction()

            scheduler.register_task(
                name="kg_incremental_builder",
                task_func=run_kg_incremental,
                interval_seconds=86400,  # 24 hours
                enabled=True,
            )
            logger.info("✅ KGIncrementalBuilder registered (24h, Gemini Free Tier)")
        except Exception as e:
            logger.error("❌ Failed to register KGIncrementalBuilder: %s", e)

    # WHATSAPP WABA SUBSCRIPTION GUARDIAN — registration RETIRED 2026-07-14
    # (scheduler-necropsy): the guardian lives on the LIVE init path
    # (service_initializer §10d, PR #2423). Registering its dormant twin here
    # was pure readability debt — the Redis leader lock already dedupes, but a
    # dead engine should not advertise live organs.

    # Start the scheduler
    await scheduler.start()

    return scheduler
