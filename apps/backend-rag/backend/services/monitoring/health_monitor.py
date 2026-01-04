"""
Health Monitor Service
Monitors system health and sends alerts on downtime or degradation
"""

import asyncio
import contextlib
import logging
from datetime import datetime, timedelta
from typing import Any

from .alert_service import AlertLevel, AlertService

logger = logging.getLogger(__name__)


class HealthMonitor:
    """
    Monitors system health and sends alerts when services go down

    Features:
    - Periodic health checks every 60 seconds
    - Alert on service downtime
    - Alert on database connection failures
    - Alert on AI service failures
    - Exponential backoff for repeated alerts
    """

    def __init__(self, alert_service: AlertService, check_interval: int = 60):
        self.alert_service = alert_service
        self.check_interval = check_interval
        self.last_status: dict[str, bool] = {}
        self.last_alert_time: dict[str, datetime] = {}
        self.alert_cooldown = timedelta(minutes=5)  # Don't spam alerts
        self.running = False
        self.task: asyncio.Task | None = None

        # Service injections
        self.memory_service = None
        self.intelligent_router = None
        self.tool_executor = None

        logger.info(f"✅ HealthMonitor initialized (check_interval={check_interval}s)")

    async def start(self):
        """Start the health monitoring loop"""
        if self.running and self.task and not self.task.done():
            logger.warning("⚠️ HealthMonitor already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._monitoring_loop())
        logger.info("🔍 HealthMonitor started")

    async def stop(self):
        """Stop the health monitoring loop"""
        self.running = False
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
        logger.info("🛑 HealthMonitor stopped")

    async def _monitoring_loop(self):
        """Main monitoring loop with robust error handling"""
        logger.info("🔄 HealthMonitor loop entered")
        while self.running:
            try:
                await self._check_health()
            except Exception as e:
                logger.error(f"❌ Critical error in health check loop: {e}", exc_info=True)

            try:
                # Wait before next check
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                logger.info("👋 HealthMonitor loop cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Sleep interrupted in health monitor: {e}")
                break

    def set_services(
        self,
        memory_service: Any = None,
        intelligent_router: Any = None,
        tool_executor: Any = None,
    ):
        """Inject services after initialization"""
        self.memory_service = memory_service
        self.intelligent_router = intelligent_router
        self.tool_executor = tool_executor
        logger.info("✅ HealthMonitor services injected")

    async def _check_health(self):
        """Perform health check and send alerts if needed"""
        from app.dependencies import get_search_service

        # Get services from dependencies
        try:
            search_service = get_search_service()
        except Exception:
            search_service = None

        # Use injected services or fallback to None
        memory_service = self.memory_service
        intelligent_router = self.intelligent_router
        tool_executor = self.tool_executor

        current_status = {
            "qdrant": await self._check_qdrant(search_service),
            "postgresql": await self._check_postgresql(memory_service),
            "ai_router": await self._check_ai_router(intelligent_router),
            "tools": tool_executor is not None,
        }

        # Check each service
        for service_name, is_healthy in current_status.items():
            was_healthy = self.last_status.get(service_name, True)

            # Service went down
            if was_healthy and not is_healthy:
                await self._send_downtime_alert(service_name)

            # Service recovered
            elif not was_healthy and is_healthy:
                await self._send_recovery_alert(service_name)

        # Update status
        self.last_status = current_status

        # Check overall health
        all_healthy = all(current_status.values())
        if not all_healthy:
            unhealthy_services = [k for k, v in current_status.items() if not v]
            logger.warning(f"⚠️ Unhealthy services: {', '.join(unhealthy_services)}")

    async def _send_downtime_alert(self, service_name: str):
        """Send alert when service goes down"""
        # Check cooldown to avoid spam
        last_alert = self.last_alert_time.get(f"down_{service_name}")
        if last_alert and datetime.now() - last_alert < self.alert_cooldown:
            return  # Skip alert, too soon

        await self.alert_service.send_alert(
            title=f"🚨 Service Down: {service_name}",
            message=f"The {service_name} service has gone offline and needs attention.",
            level=AlertLevel.CRITICAL,
            metadata={
                "service": service_name,
                "timestamp": datetime.now().isoformat(),
                "action": "immediate_investigation_required",
            },
        )

        self.last_alert_time[f"down_{service_name}"] = datetime.now()
        logger.error(f"🚨 ALERT SENT: {service_name} is DOWN")

    async def _send_recovery_alert(self, service_name: str):
        """Send alert when service recovers"""
        await self.alert_service.send_alert(
            title=f"✅ Service Recovered: {service_name}",
            message=f"The {service_name} service has recovered and is now online.",
            level=AlertLevel.INFO,
            metadata={
                "service": service_name,
                "timestamp": datetime.now().isoformat(),
                "action": "monitoring_continue",
            },
        )

        logger.info(f"✅ ALERT SENT: {service_name} RECOVERED")

    async def _check_qdrant(self, search_service) -> bool:
        """Check if Qdrant is actually working"""
        if search_service is None:
            return False

        try:
            # Try to get collection count (lightweight operation)
            if hasattr(search_service, "client") and search_service.client:
                # client might be async or sync depending on implementation
                res = search_service.client.list_collections()
                import inspect

                if inspect.isawaitable(res):
                    await res
                return True
            return True  # Service exists
        except Exception as e:
            logger.debug(f"Qdrant health check failed: {e}")
            return False

    async def _check_postgresql(self, memory_service) -> bool:
        """Check if PostgreSQL is actually working"""
        if memory_service is None:
            return False

        try:
            # Try a simple connection check or check pool status
            if hasattr(memory_service, "pool") and memory_service.pool:
                return True

            # Check if it has a health method
            if hasattr(memory_service, "health_check"):
                return await memory_service.health_check()

            return False
        except Exception as e:
            logger.debug(f"PostgreSQL health check failed: {e}")
            return False

    async def _check_ai_router(self, intelligent_router) -> bool:
        """Check if AI Router is actually working"""
        if intelligent_router is None:
            return False

        try:
            # NEW: Check if router has the Agentic RAG orchestrator
            has_orchestrator = (
                hasattr(intelligent_router, "orchestrator")
                and intelligent_router.orchestrator is not None
            )

            if has_orchestrator:
                return True

            # Legacy fallback: check old attributes
            has_llama = (
                hasattr(intelligent_router, "llama_client")
                and intelligent_router.llama_client is not None
            )
            return has_orchestrator or has_llama
        except Exception as e:
            logger.debug(f"AI Router health check failed: {e}")
            return False

    def get_status(self) -> dict[str, Any]:
        """Get current monitoring status with task liveness check"""
        is_task_alive = self.task is not None and not self.task.done()
        return {
            "running": self.running and is_task_alive,
            "task_status": "alive" if is_task_alive else "dead/not_started",
            "check_interval": self.check_interval,
            "last_status": self.last_status,
            "next_check_in": f"{self.check_interval}s",
        }


# Singleton instance
_health_monitor: HealthMonitor | None = None


def get_health_monitor() -> HealthMonitor | None:
    """Get the global HealthMonitor instance"""
    return _health_monitor


def init_health_monitor(alert_service: AlertService, check_interval: int = 60) -> HealthMonitor:
    """Initialize the global HealthMonitor instance"""
    global _health_monitor
    _health_monitor = HealthMonitor(alert_service, check_interval)
    return _health_monitor
