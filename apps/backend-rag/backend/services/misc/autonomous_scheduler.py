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
from datetime import datetime
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
        logger.debug(f"Failed to get Redis client: {e}")
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
        logger.debug(f"Lock acquisition error for {task_name}: {e}")
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
        logger.info(f"📋 Registered task: {name} (interval={interval_seconds}s, enabled={enabled})")

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
                            self._shutdown_event.wait(), timeout=task.interval_seconds
                        )
                        break
                    except asyncio.TimeoutError:
                        pass
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
                    self._run_task_loop(task), name=f"scheduler_{task.name}"
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
            logger.info(f"✅ Task enabled: {name}")
            return True
        return False

    def disable_task(self, name: str) -> bool:
        """Disable a task"""
        if name in self.tasks:
            self.tasks[name].enabled = False
            logger.info(f"⏸️ Task disabled: {name}")
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
    search_service,
    auto_ingestion_enabled: bool = False,  # Disabled - handled by bali-intel-scraper on Pro
    self_healing_enabled: bool = True,  # Active - health monitoring (5min, survives cold start)
    conversation_trainer_enabled: bool = False,  # DISABLED (audit 2026-03-16): git subprocess on Fly.io ephemeral container
    conversation_cleanup_enabled: bool = False,  # DISABLED (audit 2026-03-16): 24h > auto_stop uptime. Migrated to OpenClaw cron.
) -> AutonomousScheduler:
    """
    Create and start the autonomous scheduler with all agents.

    Args:
        db_pool: Database connection pool
        ai_client: ZantaraAIClient instance
        search_service: SearchService instance
        *_enabled: Enable/disable individual tasks

    Returns:
        Running AutonomousScheduler instance
    """
    scheduler = get_autonomous_scheduler()

    # ═══════════════════════════════════════════════════════════════════════════
    # 1. AUTO-INGESTION ORCHESTRATOR (every 24 hours)
    # ═══════════════════════════════════════════════════════════════════════════
    if auto_ingestion_enabled:
        try:
            from backend.services.ingestion.auto_ingestion_orchestrator import (
                AutoIngestionOrchestrator,
            )

            orchestrator = AutoIngestionOrchestrator(
                search_service=search_service,
                claude_service=ai_client,  # Parameter name is claude_service, not zantara_ai
            )

            async def run_auto_ingestion() -> None:
                await orchestrator.run_scheduled_ingestion()

            scheduler.register_task(
                name="auto_ingestion",
                task_func=run_auto_ingestion,
                interval_seconds=86400,  # 24 hours
                enabled=True,
            )
            logger.info("✅ Auto-Ingestion Orchestrator registered (24h interval)")
        except Exception as e:
            logger.error(f"❌ Failed to register Auto-Ingestion: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 2. BACKEND SELF-HEALING AGENT (every 5 minutes)
    # ═══════════════════════════════════════════════════════════════════════════
    if self_healing_enabled:
        try:
            from self_healing.backend_agent import BackendSelfHealingAgent

            healing_agent = BackendSelfHealingAgent(
                service_name="nuzantara-backend",
                check_interval=300,  # 5 minutes
                auto_fix_enabled=True,
            )

            async def run_self_healing() -> None:
                # Run a single health check cycle (not the infinite loop)
                await healing_agent.perform_health_check()
                issues = await healing_agent.detect_issues()
                if healing_agent.auto_fix_enabled and issues:
                    await healing_agent.attempt_auto_fix(issues)

            scheduler.register_task(
                name="self_healing",
                task_func=run_self_healing,
                interval_seconds=300,  # 5 minutes
                enabled=True,
            )
            logger.info("✅ Backend Self-Healing Agent registered (5min interval)")
        except Exception as e:
            logger.error(f"❌ Failed to register Self-Healing Agent: {e}")

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
                    f"🎓 Conversation Trainer found {len(analysis.get('patterns', []))} patterns"
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
                    logger.info(f"✅ Conversation Trainer: PR {pr_branch} created")

                except Exception as e:
                    logger.error(
                        f"Error in Conversation Trainer prompt generation/PR creation: {e}",
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
            logger.error(f"❌ Failed to register Conversation Trainer: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 5. GOLDEN ROUTES SEEDER (one-time at startup)
    # ═══════════════════════════════════════════════════════════════════════════
    if db_pool:
        try:

            async def seed_golden_routes_once() -> None:
                """Seed golden_routes with common query patterns (one-time)."""
                async with db_pool.acquire() as conn:
                    # Check if already seeded
                    count = await conn.fetchval("SELECT COUNT(*) FROM golden_routes")
                    if count > 0:
                        logger.debug(f"Golden Routes already seeded ({count} routes)")
                        return
                    logger.info("🌟 Seeding Golden Routes...")

                    # Common query patterns for Indonesian business/immigration
                    common_routes = [
                        {
                            "canonical_query": "What are the requirements for PT PMA company setup?",
                            "collections": ["legal_unified", "visa_kb"],
                            "hints": {"topic": "pt_pma", "intent": "requirements"},
                        },
                        {
                            "canonical_query": "How much does a KITAS work permit cost?",
                            "collections": ["visa_kb", "legal_unified"],
                            "hints": {"topic": "kitas", "intent": "pricing"},
                        },
                        {
                            "canonical_query": "What is the minimum capital for foreign investment?",
                            "collections": ["legal_unified"],
                            "hints": {"topic": "pt_pma", "intent": "capital"},
                        },
                        {
                            "canonical_query": "How long does KITAS processing take?",
                            "collections": ["visa_kb"],
                            "hints": {"topic": "kitas", "intent": "timeline"},
                        },
                        {
                            "canonical_query": "What documents are needed for company registration?",
                            "collections": ["legal_unified", "visa_kb"],
                            "hints": {"topic": "company", "intent": "documents"},
                        },
                        {
                            "canonical_query": "What are the tax obligations for foreign companies?",
                            "collections": ["tax_genius_hybrid", "legal_unified"],
                            "hints": {"topic": "tax", "intent": "obligations"},
                        },
                        {
                            "canonical_query": "How to extend KITAS work permit?",
                            "collections": ["visa_kb"],
                            "hints": {"topic": "kitas", "intent": "extension"},
                        },
                        {
                            "canonical_query": "What is the retirement visa age requirement?",
                            "collections": ["visa_kb"],
                            "hints": {"topic": "retirement", "intent": "eligibility"},
                        },
                    ]

                    import json
                    import uuid

                    for route in common_routes:
                        route_id = f"route_{uuid.uuid4().hex[:8]}"
                        await conn.execute(
                            """
                            INSERT INTO golden_routes (
                                route_id, canonical_query, document_ids, chapter_ids,
                                collections, routing_hints, usage_count
                            ) VALUES ($1, $2, $3, $4, $5, $6, 0)
                            """,
                            route_id,
                            route["canonical_query"],
                            [],  # document_ids - to be populated by search
                            [],  # chapter_ids
                            route["collections"],
                            json.dumps(route["hints"]),
                        )

                    logger.info(f"🌟 Seeded {len(common_routes)} Golden Routes!")

            scheduler.register_task(
                name="golden_routes_seeder",
                task_func=seed_golden_routes_once,
                interval_seconds=86400 * 365,  # Effectively one-time (1 year)
                enabled=True,
            )
        except Exception as e:
            logger.error(f"❌ Failed to register Golden Routes Seeder: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 6. RENEWAL ALERTS CHECKER (every 12 hours)
    # ═══════════════════════════════════════════════════════════════════════════
    if db_pool:
        try:

            async def run_renewal_alerts_checker() -> None:
                """Check for upcoming practice expirations and create alerts."""
                from datetime import datetime, timedelta

                logger.info("📅 Running Renewal Alerts Checker...")

                async with db_pool.acquire() as conn:
                    today = datetime.now(tz=timezone.utc).date()
                    alert_days = [90, 60, 30]  # Days before expiry to alert

                    for days in alert_days:
                        target_date = today + timedelta(days=days)

                        # Find practices expiring in exactly X days that don't have alerts yet
                        practices = await conn.fetch(
                            """
                            SELECT p.id, p.client_id, p.title, p.expiry_date, p.assigned_to,
                                   c.company_name, c.full_name
                            FROM practices p
                            JOIN clients c ON c.id = p.client_id
                            WHERE p.expiry_date = $1
                              AND p.status IN ('completed', 'active')
                              AND NOT EXISTS (
                                  SELECT 1 FROM renewal_alerts ra
                                  WHERE ra.practice_id = p.id
                                    AND ra.alert_type = $2
                              )
                            """,
                            target_date,
                            f"renewal_{days}d",
                        )

                        for p in practices:
                            client_name = p["company_name"] or p["full_name"] or "Cliente"
                            description = (
                                f"🔔 Pratica '{p['title']}' per {client_name} "
                                f"scade tra {days} giorni ({target_date})"
                            )

                            await conn.execute(
                                """
                                INSERT INTO renewal_alerts (
                                    practice_id, client_id, alert_type, description,
                                    target_date, alert_date, notify_team_member, status
                                ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending')
                                """,
                                p["id"],
                                p["client_id"],
                                f"renewal_{days}d",
                                description,
                                p["expiry_date"],
                                today,
                                p["assigned_to"],
                            )
                            logger.info(
                                f"   📌 Created {days}d alert for practice {p['id'][:8]}..."
                            )

                    # Count pending alerts
                    pending = await conn.fetchval(
                        "SELECT COUNT(*) FROM renewal_alerts WHERE status = 'pending'"
                    )
                    logger.info(f"✅ Renewal Alerts Checker done. {pending} alerts pending.")

            scheduler.register_task(
                name="renewal_alerts",
                task_func=run_renewal_alerts_checker,
                interval_seconds=43200,  # 12 hours
                enabled=False,  # DISABLED (audit 2026-03-16): 12h > auto_stop uptime. Covered by OpenClaw practice-lifecycle-check.
            )
            logger.info("⏸️ Renewal Alerts registered but DISABLED (migrated to OpenClaw)")
        except Exception as e:
            logger.error(f"❌ Failed to register Renewal Alerts: {e}")

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
                    logger.error(f"❌ Birthplace Enrichment error: {e}", exc_info=True)

            scheduler.register_task(
                name="birthplace_enrichment",
                task_func=run_birthplace_enrichment,
                interval_seconds=86400,  # 24 hours
                enabled=True,
            )
            logger.info("✅ Birthplace Enrichment registered (24h interval)")
        except Exception as e:
            logger.error(f"❌ Failed to register Birthplace Enrichment: {e}")

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
                logger.error(f"❌ Birthday Notifier error: {e}", exc_info=True)

        scheduler.register_task(
            name="birthday_notifier",
            task_func=run_birthday_notifier,
            interval_seconds=86400,  # 24 hours
            enabled=False,  # DISABLED (audit 2026-03-16): 24h > auto_stop uptime. Covered by OpenClaw client-health-monitor.
        )
        logger.info("⏸️ Birthday Notifier registered but DISABLED (migrated to OpenClaw)")
    except Exception as e:
        logger.error(f"❌ Failed to register Birthday Notifier: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # TASK 10: CONVERSATION CLEANUP (daily)
    # Cleans up old conversations (>30 days) and anonymizes user data (>7 days)
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
                            f"{result['anonymized_count']} anonymized"
                        )
                except Exception as e:
                    logger.error(f"❌ Conversation cleanup error: {e}", exc_info=True)

            scheduler.register_task(
                name="conversation_cleanup",
                task_func=run_conversation_cleanup,
                interval_seconds=86400,
                enabled=True,
            )
            logger.info("✅ Conversation Cleanup registered (24h interval)")
        except Exception as e:
            logger.error(f"❌ Failed to register Conversation Cleanup: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # TASK 11: DAILY OPS AUTOPILOT (daily at 08:00 WITA / 00:00 UTC)
    # Runs chain_daily_ops_autopilot MCP workflow:
    # 1. Check expiry alerts → send WhatsApp reminders (<30 days)
    # 2. Check autonomous agent health → restart stale agents
    # 3. Check critical intel alerts → auto-compose articles for high-impact items
    # 4. Gather team hours and completion rates
    # 5. Compile and email daily report
    # ═══════════════════════════════════════════════════════════════════════════
    try:

        async def run_daily_ops_autopilot() -> None:
            """Execute chain_daily_ops_autopilot via MCP server"""
            try:
                # Call MCP server endpoint to execute the chain
                mcp_base_url = os.getenv("MCP_SERVER_URL", "http://localhost:8000")
                client = _get_client(timeout=300.0)
                response = await client.post(
                    f"{mcp_base_url}/tools/chain_daily_ops_autopilot",
                    json={"send_report_to": "zero@balizero.com"},
                )
                response.raise_for_status()
                result = response.json()

                reminders = (
                    result.get("report", {}).get("expiry_alerts", {}).get("reminders_sent", 0)
                )
                articles = result.get("report", {}).get("intel", {}).get("articles_composed", 0)

                logger.info(
                    f"🤖 Daily Ops Autopilot completed: "
                    f"{reminders} reminders sent, {articles} articles composed"
                )
            except Exception as e:
                logger.error(f"❌ Daily Ops Autopilot error: {e}", exc_info=True)

        scheduler.register_task(
            name="daily_ops_autopilot",
            task_func=run_daily_ops_autopilot,
            interval_seconds=86400,  # 24 hours
            enabled=False,  # DISABLED (audit 2026-03-16): BUG (calls localhost:8000 = itself). OpenClaw daily-ops-autopilot handles correctly.
        )
        logger.info("⏸️ Daily Ops Autopilot registered but DISABLED (migrated to OpenClaw)")
    except Exception as e:
        logger.error(f"❌ Failed to register Daily Ops Autopilot: {e}")

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
                    logger.info(f"📂 Drive Poll: {processed} new files processed for OCR")
            except Exception as e:
                logger.error(f"Drive Poll error: {e}", exc_info=True)

        scheduler.register_task(
            name="drive_changes_poll",
            task_func=run_drive_poll,
            interval_seconds=300,  # 5 minutes
            enabled=False,  # DISABLED 2026-03-22: moved to Air cron (curl POST /api/admin/drive/poll every 5min). Fly.io auto_stop incompatible with internal polling.
        )
        logger.info("⏸️ Drive Changes Polling DISABLED (moved to Air cron)")
    except Exception as e:
        logger.error(f"Failed to register Drive Changes Polling: {e}")

    # Start the scheduler
    await scheduler.start()

    return scheduler
