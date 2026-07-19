"""
🤖 AUTONOMOUS SCHEDULER SERVICE
Background tasks that run while the backend is active on Fly.io.

⚠️ AUDIT 2026-03-16: With auto_stop=true (min_machines=0), the backend shuts
down after ~5min of inattivity. Only short-interval tasks (<=5min) survive.
All long-interval tasks (>=6h) have been migrated to OpenClaw cron on Pro (H24).

⚰️ NECROPSY 2026-07-14: the engine itself has been DEAD in prod since
2026-02-11 (service_initializer §10 commented out), so nothing registered here
runs. Surviving live coverage moved to the live init path: self-healing (§10e),
WhatsApp guardian (§10d), KG incremental builder (§10f). Retired blocks carry
tombstone comments below; full report in
research/operations/2026-07-14-autonomous-scheduler-necropsy.md.

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


# Atomic compare-and-delete: only remove the lock if it still holds THIS
# worker's identity. A plain DEL would let a worker whose lock already
# expired (e.g. it overran ttl_seconds) delete a *different* worker's lock
# that has since acquired the same key.
_RELEASE_LOCK_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


async def _release_task_lock(task_name: str) -> bool:
    """
    Release a distributed task lock, but ONLY if this worker still holds it.

    Pairs with `_acquire_task_lock`. Callers should acquire a short-TTL lock
    for the duration of a task and release it in a `finally` block so a
    crashed/killed task does not hold the lock for its full TTL (still a
    safety net, just no longer the only exit).

    Returns True if this worker's lock was released, False otherwise
    (already expired, held by another worker, or Redis unavailable).
    """
    client = await _get_redis()
    if client is None:
        return False  # No Redis = nothing to release

    lock_key = f"{_LOCK_PREFIX}{task_name}"
    try:
        released = await client.eval(_RELEASE_LOCK_LUA, 1, lock_key, _WORKER_ID)
        return bool(released)
    except Exception as e:
        logger.debug("Lock release error for %s: %s", task_name, e)
        return False


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
    conversation_cleanup_enabled: bool = False,  # DISABLED (audit 2026-03-16): 24h > auto_stop uptime. Migrated to OpenClaw cron.
) -> AutonomousScheduler:
    """
    Create and start the autonomous scheduler with the surviving agents.

    Necropsy 2026-07-14: params for retired tasks (search_service,
    auto_ingestion_enabled, self_healing_enabled, conversation_trainer_enabled,
    ai_client) were removed with their blocks — the sole caller (_init_background_services, §10) is commented out.

    Args:
        db_pool: Database connection pool
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

    # 3. CONVERSATION TRAINER — RETIRED 2026-07-14 (necropsy follow-up, decision
    # delegated by Zero "agisci con saggezza"): total_runs=0 in its whole life,
    # registered-but-disabled since the 2026-03-16 audit (git subprocess cannot
    # work on a Fly ephemeral container). The on-demand surface survives intact:
    # POST /api/autonomous-agents/conversation-trainer/run + MCP
    # run_conversation_trainer. Re-arming autonomously would be a NEW build
    # (artifact store instead of git), not a resurrection.

    # 5. GOLDEN ROUTES SEEDER — RETIRED 2026-07-14 (scheduler-necropsy): it
    # would have seeded rows nobody reads — GoldenRouterService was never
    # instantiated in the app and document_ids were never populated. The orphan
    # service was DELETED same day (wire-or-delete resolved: the live golden
    # routes are KGEnhancedRetrieval.GOLDEN_ROUTES). The stale golden_routes
    # DB table (8 rows, last write 2026-01-10) remains; dropping it is a
    # migration decision tracked in modus PENDING-ARMS.

    # 6. RENEWAL ALERTS — RETIRED 2026-07-14 (scheduler-necropsy): the old
    # comment claimed coverage by 'OpenClaw practice-lifecycle-check' (false);
    # the REAL live coverage is crm_automation_engine.py module 'renewals'
    # (Pro crontab 23:00 UTC). This dead block duplicated that logic.

    # 8. BIRTHPLACE ENRICHMENT — RETIRED 2026-07-14 (necropsy follow-up,
    # decision delegated by Zero "agisci con saggezza"): 945 candidates, 0
    # enriched EVER; prod always skipped it (no Ollama on Fly); the consumer
    # (birthday email) degrades to "" without it. LLM-fabricated "cultural
    # context" on client birthplaces is also a UU PDP liability, not a feature.
    # The service module stays for deliberate local runs.

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

    # KG INCREMENTAL BUILDER — MOVED to the live init path 2026-07-14
    # (service_initializer §10f, necropsy follow-up): it was doubly unarmed
    # here — dead engine AND an ENABLE_KG_INCREMENTAL env never set on Fly.
    # The "run via Air/Pro cron" claim above it was false (no cron/plist
    # anywhere; Air is decommissioned). Daily loop now lives next to the
    # WhatsApp guardian, same Redis lock key for dedupe.

    # WHATSAPP WABA SUBSCRIPTION GUARDIAN — registration RETIRED 2026-07-14
    # (scheduler-necropsy): the guardian lives on the LIVE init path
    # (service_initializer §10d, PR #2423). Registering its dormant twin here
    # was pure readability debt — the Redis leader lock already dedupes, but a
    # dead engine should not advertise live organs.

    # Start the scheduler
    await scheduler.start()

    return scheduler
