"""
Health Monitor Service
Monitors system health and sends alerts on downtime or degradation.

Enhanced with:
- Resource monitoring (memory, CPU) for Fly.io 4GB VM
- Cold start tracking
- DB pool saturation alerts
- Restart counter
"""

import asyncio
import contextlib
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import psutil

from backend.services.monitoring.alert_service import AlertLevel, AlertService

logger = logging.getLogger(__name__)

# Track boot time for cold start and restart metrics
_BOOT_TIME = time.monotonic()
_BOOT_TIMESTAMP = datetime.now(timezone.utc)

# Fly.io VM memory limit (bytes). Default 4GB, override via FLY_VM_MEMORY_MB.
_VM_MEMORY_MB = int(os.getenv("FLY_VM_MEMORY_MB", "4096"))
_VM_MEMORY_BYTES = _VM_MEMORY_MB * 1024 * 1024


class HealthMonitor:
    """
    Monitors system health and sends alerts when services go down.

    Features:
    - Periodic health checks every 60 seconds
    - Alert on service downtime / recovery
    - Resource monitoring: memory RSS, CPU usage
    - DB pool saturation detection
    - Cold start duration tracking
    - Restart counter (increments per boot)
    """

    def __init__(self, alert_service: AlertService, check_interval: int = 60) -> None:
        self.alert_service = alert_service
        self.check_interval = check_interval
        self.last_status: dict[str, bool] = {}
        self.last_alert_time: dict[str, datetime] = {}
        self.alert_cooldown = timedelta(minutes=5)  # Don't spam alerts
        self.running = False
        self.task: asyncio.Task | None = None

        # Service injections
        self.memory_service: Any = None
        self.intelligent_router: Any = None
        self.tool_executor: Any = None
        self.app_state: Any = None

        # Resource monitoring state
        self._resource_alert_cooldown: dict[str, datetime] = {}
        self._cold_start_duration: float | None = None
        self._first_request_seen = False
        self._restart_count = self._read_restart_count()

        # Persistent HTTP client
        self._client: httpx.AsyncClient | None = None

        logger.info(f"✅ HealthMonitor initialized (check_interval={check_interval}s)")

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the shared async client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=10.0,
                limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
            )
        return self._client

    async def close(self) -> None:
        """Close the internal async client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
        logger.info("HealthMonitor HTTP client closed.")

    def record_first_request(self) -> None:
        """Call this when the first real request (non-health) is served."""
        if not self._first_request_seen:
            self._first_request_seen = True
            self._cold_start_duration = time.monotonic() - _BOOT_TIME
            logger.info(f"⏱️ Cold start duration: {self._cold_start_duration:.2f}s")

    async def start(self) -> None:
        """Start the health monitoring loop"""
        if self.running and self.task and not self.task.done():
            logger.warning("⚠️ HealthMonitor already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._monitoring_loop())
        logger.info("🔍 HealthMonitor started")

    async def stop(self) -> None:
        """Stop the health monitoring loop"""
        self.running = False
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
        logger.info("🛑 HealthMonitor stopped")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop with robust error handling"""
        logger.info("🔄 HealthMonitor loop entered")

        # Initial delay to allow services to fully initialize after startup
        try:
            await asyncio.sleep(15)
            logger.info("🔍 HealthMonitor starting checks after initial delay")
        except asyncio.CancelledError:
            logger.info("👋 HealthMonitor cancelled during initial delay")
            return

        while self.running:
            try:
                await self._check_health()
                await self._check_resources()
            except Exception as e:
                logger.error(f"❌ Critical error in health check loop: {e}", exc_info=True)

            try:
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
        app_state: Any = None,
    ) -> None:
        """Inject services after initialization"""
        self.memory_service = memory_service
        self.intelligent_router = intelligent_router
        self.tool_executor = tool_executor
        self.app_state = app_state
        logger.info("✅ HealthMonitor services injected")

    # =========================================================================
    # Service health checks
    # =========================================================================

    async def _check_health(self) -> None:
        """Perform health check and send alerts if needed"""
        from backend.app.dependencies import get_search_service

        try:
            search_service = get_search_service()
        except Exception:
            search_service = None

        memory_service = self.memory_service
        intelligent_router = self.intelligent_router
        tool_executor = self.tool_executor

        current_status = {
            "qdrant": await self._check_qdrant(search_service),
            "postgresql": await self._check_postgresql(memory_service),
            "ai_router": await self._check_ai_router(intelligent_router),
            "tools": tool_executor is not None,
        }

        for service_name, is_healthy in current_status.items():
            was_healthy = self.last_status.get(service_name, True)

            if was_healthy and not is_healthy:
                await self._send_downtime_alert(service_name)
            elif not was_healthy and is_healthy:
                await self._send_recovery_alert(service_name)

        self.last_status = current_status

        all_healthy = all(current_status.values())
        if not all_healthy:
            unhealthy_services = [k for k, v in current_status.items() if not v]
            logger.warning(f"⚠️ Unhealthy services: {', '.join(unhealthy_services)}")

    # =========================================================================
    # Resource monitoring (Fly.io specific)
    # =========================================================================

    async def _check_resources(self) -> None:
        """Check system resources and alert on thresholds."""
        from backend.app.core.config import settings

        try:
            process = psutil.Process()
            mem_info = process.memory_info()

            # Memory: RSS as percentage of VM limit
            rss_mb = mem_info.rss / (1024 * 1024)
            mem_percent = (mem_info.rss / _VM_MEMORY_BYTES) * 100

            if mem_percent > settings.memory_alert_threshold_percent:
                await self._send_resource_alert_throttled(
                    "memory",
                    mem_percent,
                    settings.memory_alert_threshold_percent,
                    unit=f"% ({rss_mb:.0f}MB / {_VM_MEMORY_MB}MB)",
                )

            # CPU: average over a non-blocking interval
            cpu_percent = process.cpu_percent(interval=None)  # Non-blocking
            if cpu_percent > settings.cpu_alert_threshold_percent:
                await self._send_resource_alert_throttled(
                    "cpu",
                    cpu_percent,
                    settings.cpu_alert_threshold_percent,
                )

            # DB pool saturation
            await self._check_db_pool_saturation()

            # Update Prometheus gauges
            self._update_resource_metrics(rss_mb, mem_percent, cpu_percent)

        except Exception as e:
            logger.debug(f"Resource check failed (non-critical): {e}")

    async def _check_db_pool_saturation(self) -> None:
        """Alert if DB connection pool is near exhaustion."""
        if not self.app_state:
            return

        db_pool = getattr(self.app_state, "db_pool", None)
        if not db_pool:
            return

        try:
            pool_size = db_pool.get_size()
            pool_max = db_pool.get_max_size()
            if pool_max > 0:
                saturation = (pool_size / pool_max) * 100
                if saturation > 85:
                    await self._send_resource_alert_throttled(
                        "db_pool",
                        saturation,
                        85.0,
                        unit=f"% ({pool_size}/{pool_max} connections)",
                    )
        except Exception as e:
            logger.debug(f"DB pool check failed: {e}")

    async def _send_resource_alert_throttled(
        self, resource: str, current: float, threshold: float, unit: str = "%"
    ) -> None:
        """Send resource alert with cooldown to avoid spam."""
        last = self._resource_alert_cooldown.get(resource)
        if last and datetime.now(tz=timezone.utc) - last < self.alert_cooldown:
            return

        await self.alert_service.send_resource_alert(
            resource=resource,
            current_value=current,
            threshold=threshold,
            unit=unit,
        )
        self._resource_alert_cooldown[resource] = datetime.now(tz=timezone.utc)

    def _update_resource_metrics(
        self, rss_mb: float, mem_percent: float, cpu_percent: float
    ) -> None:
        """Update Prometheus gauges for resources."""
        try:
            from backend.app.metrics import cpu_usage, memory_usage

            memory_usage.set(rss_mb)
            cpu_usage.set(cpu_percent)
        except Exception:
            pass  # Metrics module may not be imported yet

    # =========================================================================
    # Alert helpers
    # =========================================================================

    async def _send_downtime_alert(self, service_name: str) -> None:
        """Send alert when service goes down"""
        last_alert = self.last_alert_time.get(f"down_{service_name}")
        if last_alert and datetime.now(tz=timezone.utc) - last_alert < self.alert_cooldown:
            return

        await self.alert_service.send_alert(
            title=f"Service Down: {service_name}",
            message=f"The {service_name} service has gone offline and needs attention.",
            level=AlertLevel.CRITICAL,
            metadata={
                "service": service_name,
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "action": "immediate_investigation_required",
            },
        )

        self.last_alert_time[f"down_{service_name}"] = datetime.now(tz=timezone.utc)
        logger.error(f"🚨 ALERT SENT: {service_name} is DOWN")

    async def _send_recovery_alert(self, service_name: str) -> None:
        """Send alert when service recovers"""
        await self.alert_service.send_alert(
            title=f"Service Recovered: {service_name}",
            message=f"The {service_name} service has recovered and is now online.",
            level=AlertLevel.INFO,
            metadata={
                "service": service_name,
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "action": "monitoring_continue",
            },
        )

        logger.info(f"✅ ALERT SENT: {service_name} RECOVERED")

    # =========================================================================
    # Individual service checks
    # =========================================================================

    async def _check_qdrant(self, search_service: Any) -> bool:
        """Check if Qdrant is actually working via HTTP"""
        from backend.app.core.config import settings

        try:
            headers = {}
            if settings.qdrant_api_key:
                headers["api-key"] = settings.qdrant_api_key

            client = self._get_client()
            response = await client.get(
                f"{settings.qdrant_url}/collections",
                headers=headers,
                timeout=5.0,
            )
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Qdrant health check failed: {e}")
            return False

    async def _check_postgresql(self, memory_service: Any) -> bool:
        """Check if PostgreSQL is actually working by executing a real query"""
        import asyncpg

        from backend.app.core.config import settings

        # Strategy 1: Try to get memory_service dynamically from app_state
        service = memory_service
        if service is None and self.app_state:
            service = getattr(self.app_state, "memory_service", None)

        # Strategy 2: Try memory_service pool with actual query
        if service is not None:
            pool = getattr(service, "pool", None)
            if pool:
                try:
                    async with pool.acquire() as conn:
                        result = await conn.fetchval("SELECT 1")
                        if result == 1:
                            return True
                except Exception as e:
                    logger.warning(f"PostgreSQL (memory_service.pool) failed: {e}")

        # Strategy 3: Try db_pool from app_state
        if self.app_state:
            db_pool = getattr(self.app_state, "db_pool", None)
            if db_pool:
                try:
                    async with db_pool.acquire() as conn:
                        result = await conn.fetchval("SELECT 1")
                        if result == 1:
                            return True
                except Exception as e:
                    logger.warning(f"PostgreSQL (app_state.db_pool) failed: {e}")

        # Strategy 4: Direct connection test (fallback)
        try:
            if settings.database_url:
                conn = await asyncpg.connect(settings.database_url, timeout=5.0)
                result = await conn.fetchval("SELECT 1")
                await conn.close()
                if result == 1:
                    return True
            else:
                logger.warning("PostgreSQL: DATABASE_URL not set")
        except Exception as e:
            logger.warning(f"PostgreSQL (direct connect) failed: {e}")

        logger.warning(
            f"PostgreSQL health check failed: "
            f"memory_service={memory_service is not None}, "
            f"app_state={self.app_state is not None}"
        )
        return False

    async def _check_ai_router(self, intelligent_router: Any) -> bool:
        """Check if AI Router is actually working"""
        router = intelligent_router

        if router is None and self.app_state:
            router = getattr(self.app_state, "intelligent_router", None)

        if router is None:
            if not hasattr(self, "_ai_router_none_logged"):
                self._ai_router_none_logged = True
                logger.warning(
                    "AI Router health check: router is None. "
                    f"injected_router={intelligent_router is not None}, "
                    f"app_state={self.app_state is not None}"
                )
            return False

        try:
            has_orchestrator = (
                hasattr(router, "orchestrator")
                and getattr(router, "orchestrator", None) is not None
            )
            if has_orchestrator:
                return True

            has_llama = hasattr(router, "llama_client") and router.llama_client is not None
            if has_llama:
                return True

            if not hasattr(self, "_ai_router_debug_logged"):
                self._ai_router_debug_logged = True
                logger.warning(
                    f"AI Router health check failed: router_type={type(router).__name__}"
                )

            return False
        except Exception as e:
            logger.warning(f"AI Router health check exception: {e}")
            return False

    # =========================================================================
    # Restart tracking (persisted via Prometheus counter)
    # =========================================================================

    @staticmethod
    def _read_restart_count() -> int:
        """Increment restart counter. Uses Prometheus counter which resets per process."""
        try:
            from backend.app.metrics import safe_register_counter

            counter = safe_register_counter("zantara_restarts_total", "Total process restarts")
            counter.inc()
            return 1  # Prometheus handles accumulation
        except Exception:
            return 0

    # =========================================================================
    # Status reporting
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get current monitoring status with task liveness and resource info"""
        is_task_alive = self.task is not None and not self.task.done()

        # Resource snapshot
        resource_info: dict[str, Any] = {}
        try:
            process = psutil.Process()
            mem_info = process.memory_info()
            rss_mb = mem_info.rss / (1024 * 1024)
            resource_info = {
                "memory_rss_mb": round(rss_mb, 1),
                "memory_vm_limit_mb": _VM_MEMORY_MB,
                "memory_percent": round((mem_info.rss / _VM_MEMORY_BYTES) * 100, 1),
                "cpu_percent": process.cpu_percent(interval=None),
                "uptime_seconds": round(time.monotonic() - _BOOT_TIME, 0),
                "cold_start_seconds": round(self._cold_start_duration, 2)
                if self._cold_start_duration
                else None,
                "boot_time": _BOOT_TIMESTAMP.isoformat(),
            }
        except Exception:
            pass

        # DB pool info
        pool_info: dict[str, Any] = {}
        if self.app_state:
            db_pool = getattr(self.app_state, "db_pool", None)
            if db_pool:
                with contextlib.suppress(Exception):
                    pool_info = {
                        "size": db_pool.get_size(),
                        "min_size": db_pool.get_min_size(),
                        "max_size": db_pool.get_max_size(),
                        "idle": db_pool.get_idle_size(),
                    }

        return {
            "running": self.running and is_task_alive,
            "task_status": "alive" if is_task_alive else "dead/not_started",
            "check_interval": self.check_interval,
            "last_status": self.last_status,
            "resources": resource_info,
            "db_pool": pool_info,
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
