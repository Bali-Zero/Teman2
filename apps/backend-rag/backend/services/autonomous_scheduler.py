"""
🤖 AUTONOMOUS SCHEDULER SERVICE
Centralizes scheduling of all autonomous agents and background tasks.

Managed Services:
1. Auto-Ingestion Orchestrator - Daily regulatory updates (every 24h)
2. Backend Self-Healing Agent - Continuous health monitoring (every 30s)
3. Conversation Trainer Agent - Learn from successful conversations (every 6h)
4. Client Value Predictor Agent - Nurture high-value clients (every 12h)
5. Knowledge Graph Builder Agent - Build knowledge graphs (every 4h)
"""

import asyncio
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


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

    def __init__(self):
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
                logger.info(f"⏰ Running scheduled task: {task.name}")
                task.last_run = datetime.now()

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
                try:
                    await asyncio.wait_for(task._task, timeout=5)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass

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
    auto_ingestion_enabled: bool = True,
    self_healing_enabled: bool = True,
    conversation_trainer_enabled: bool = True,
    client_value_predictor_enabled: bool = True,
    knowledge_graph_enabled: bool = True,
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
            from services.auto_ingestion_orchestrator import AutoIngestionOrchestrator

            orchestrator = AutoIngestionOrchestrator(
                search_service=search_service,
                claude_service=ai_client,  # Parameter name is claude_service, not zantara_ai
            )

            async def run_auto_ingestion():
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
    # 2. BACKEND SELF-HEALING AGENT (every 30 seconds)
    # ═══════════════════════════════════════════════════════════════════════════
    if self_healing_enabled:
        try:
            from self_healing.backend_agent import BackendSelfHealingAgent

            healing_agent = BackendSelfHealingAgent(
                service_name="nuzantara-backend",
                check_interval=30,
                auto_fix_enabled=True,
            )

            async def run_self_healing():
                # Run a single health check cycle (not the infinite loop)
                await healing_agent.perform_health_check()
                issues = await healing_agent.detect_issues()
                if healing_agent.auto_fix_enabled and issues:
                    await healing_agent.attempt_auto_fix(issues)

            scheduler.register_task(
                name="self_healing",
                task_func=run_self_healing,
                interval_seconds=30,  # 30 seconds
                enabled=True,
            )
            logger.info("✅ Backend Self-Healing Agent registered (30s interval)")
        except Exception as e:
            logger.error(f"❌ Failed to register Self-Healing Agent: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 3. CONVERSATION TRAINER AGENT (every 6 hours)
    # ═══════════════════════════════════════════════════════════════════════════
    if conversation_trainer_enabled and db_pool:
        try:
            from agents.agents.conversation_trainer import ConversationTrainer

            trainer = ConversationTrainer(
                db_pool=db_pool,
                zantara_client=ai_client,
            )

            async def run_conversation_trainer():
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
                    logger.error(f"Error in Conversation Trainer prompt generation/PR creation: {e}", exc_info=True)

            scheduler.register_task(
                name="conversation_trainer",
                task_func=run_conversation_trainer,
                interval_seconds=21600,  # 6 hours
                enabled=True,
            )
            logger.info("✅ Conversation Trainer Agent registered (6h interval)")
        except Exception as e:
            logger.error(f"❌ Failed to register Conversation Trainer: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 4. CLIENT VALUE PREDICTOR AGENT (every 12 hours)
    # ═══════════════════════════════════════════════════════════════════════════
    if client_value_predictor_enabled and db_pool:
        try:
            from agents.agents.client_value_predictor import ClientValuePredictor

            predictor = ClientValuePredictor(
                db_pool=db_pool,
                ai_client=ai_client,
            )

            async def run_client_value_predictor():
                # This would typically:
                # 1. Score all clients
                # 2. Identify VIP/high-value inactive clients
                # 3. Send nurturing messages
                logger.info("💰 Running Client Value Predictor...")
                # Full implementation would call predictor methods
                # await predictor.run_full_analysis()

            scheduler.register_task(
                name="client_value_predictor",
                task_func=run_client_value_predictor,
                interval_seconds=43200,  # 12 hours
                enabled=True,
            )
            logger.info("✅ Client Value Predictor Agent registered (12h interval)")
        except Exception as e:
            logger.error(f"❌ Failed to register Client Value Predictor: {e}")

    # ═══════════════════════════════════════════════════════════════════════════
    # 5. KNOWLEDGE GRAPH BUILDER AGENT (every 4 hours)
    # ═══════════════════════════════════════════════════════════════════════════
    if knowledge_graph_enabled and db_pool:
        try:
            from agents.agents.knowledge_graph_builder import KnowledgeGraphBuilder

            graph_builder = KnowledgeGraphBuilder(
                db_pool=db_pool,
                ai_client=ai_client,
            )

            async def run_knowledge_graph_builder():
                # Initialize schema if needed
                await graph_builder.init_graph_schema()
                logger.info("🕸️ Knowledge Graph schema verified")
                # Full implementation would process new documents
                # and extract entities/relationships

            scheduler.register_task(
                name="knowledge_graph_builder",
                task_func=run_knowledge_graph_builder,
                interval_seconds=14400,  # 4 hours
                enabled=True,
            )
            logger.info("✅ Knowledge Graph Builder Agent registered (4h interval)")
        except Exception as e:
            logger.error(f"❌ Failed to register Knowledge Graph Builder: {e}")

    # Start the scheduler
    await scheduler.start()

    return scheduler
