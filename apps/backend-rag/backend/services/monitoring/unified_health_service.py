"""
NUZANTARA PRIME - Unified Health Check Service

Centralizes all health check functionality:
- Manual health checks (from scripts/health_check.py)
- Continuous monitoring (from self_healing/backend_agent.py)
- Service registry integration (from app.core.service_health)

This service provides a single source of truth for system health.
"""

import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import asyncpg
import httpx
import psutil
import redis

from app.core.config import settings
from app.core.service_health import ServiceStatus, service_registry

logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """Result of a single health check"""

    name: str
    status: str  # "ok", "warning", "error", "skipped"
    message: str
    latency_ms: float | None = None
    metadata: dict[str, Any] | None = None
    timestamp: float | None = None


@dataclass
class SystemMetrics:
    """System-level metrics"""

    cpu_usage: float
    memory_usage: float
    disk_usage: float
    uptime: float
    timestamp: float


class UnifiedHealthService:
    """
    Unified Health Check Service

    Provides:
    - Comprehensive health checks for all services
    - System metrics monitoring
    - Integration with ServiceRegistry
    - Continuous monitoring capabilities
    - Health check reporting
    """

    def __init__(self):
        self.service_registry = service_registry
        self.start_time = time.time()
        self.http_client: httpx.AsyncClient | None = None
        self.redis_client: redis.Redis | None = None
        self._check_cache: dict[str, tuple[float, HealthCheckResult]] = {}
        self._cache_ttl = 5.0  # Cache results for 5 seconds

    async def initialize(self):
        """Initialize HTTP and Redis clients"""
        self.http_client = httpx.AsyncClient(timeout=10.0)

        # Initialize Redis if available
        if settings.redis_url:
            try:
                self.redis_client = redis.from_url(settings.redis_url)
                self.redis_client.ping()
            except Exception as e:
                logger.warning(f"Redis not available for health checks: {e}")

    async def close(self):
        """Cleanup resources"""
        if self.http_client:
            await self.http_client.aclose()

    async def check_database(self) -> HealthCheckResult:
        """Check PostgreSQL database connection"""
        start = time.time()
        try:
            if not settings.database_url:
                return HealthCheckResult(
                    name="database",
                    status="skipped",
                    message="DATABASE_URL not set",
                    timestamp=time.time(),
                )

            conn = await asyncpg.connect(settings.database_url)
            await conn.execute("SELECT 1")
            await conn.close()

            latency = (time.time() - start) * 1000
            self.service_registry.register("database", ServiceStatus.HEALTHY)

            return HealthCheckResult(
                name="database",
                status="ok",
                message="Database connection successful",
                latency_ms=latency,
                timestamp=time.time(),
            )
        except Exception as e:
            self.service_registry.register("database", ServiceStatus.UNAVAILABLE, error=str(e))
            return HealthCheckResult(
                name="database",
                status="error",
                message=f"Database connection failed: {e}",
                latency_ms=(time.time() - start) * 1000,
                timestamp=time.time(),
            )

    async def check_qdrant(self) -> HealthCheckResult:
        """Check Qdrant vector database connection"""
        start = time.time()
        try:
            if not settings.qdrant_url:
                return HealthCheckResult(
                    name="qdrant",
                    status="skipped",
                    message="QDRANT_URL not set",
                    timestamp=time.time(),
                )

            from core.qdrant_db import QdrantClient

            client = QdrantClient(qdrant_url=settings.qdrant_url, collection_name="visa_oracle")
            if client.qdrant_url and client.collection_name:
                latency = (time.time() - start) * 1000
                self.service_registry.register("qdrant", ServiceStatus.HEALTHY)

                return HealthCheckResult(
                    name="qdrant",
                    status="ok",
                    message=f"Qdrant client initialized (URL: {client.qdrant_url})",
                    latency_ms=latency,
                    metadata={"collection": client.collection_name},
                    timestamp=time.time(),
                )
            else:
                raise Exception("Qdrant client missing required attributes")
        except Exception as e:
            self.service_registry.register("qdrant", ServiceStatus.UNAVAILABLE, error=str(e))
            return HealthCheckResult(
                name="qdrant",
                status="error",
                message=f"Qdrant connection failed: {e}",
                latency_ms=(time.time() - start) * 1000,
                timestamp=time.time(),
            )

    async def check_redis(self) -> HealthCheckResult:
        """Check Redis cache connection"""
        start = time.time()
        try:
            if not settings.redis_url:
                return HealthCheckResult(
                    name="redis",
                    status="skipped",
                    message="REDIS_URL not set",
                    timestamp=time.time(),
                )

            if not self.redis_client:
                self.redis_client = redis.from_url(settings.redis_url)

            self.redis_client.ping()
            latency = (time.time() - start) * 1000
            self.service_registry.register("redis", ServiceStatus.HEALTHY)

            return HealthCheckResult(
                name="redis",
                status="ok",
                message="Redis connection successful",
                latency_ms=latency,
                timestamp=time.time(),
            )
        except Exception as e:
            self.service_registry.register("redis", ServiceStatus.DEGRADED, error=str(e))
            return HealthCheckResult(
                name="redis",
                status="warning",
                message=f"Redis connection failed: {e}",
                latency_ms=(time.time() - start) * 1000,
                timestamp=time.time(),
            )

    async def check_api(self, url: str = "http://localhost:8000/health") -> HealthCheckResult:
        """Check API health endpoint"""
        start = time.time()
        try:
            if not self.http_client:
                await self.initialize()

            response = await self.http_client.get(url, timeout=5.0)
            latency = (time.time() - start) * 1000

            if response.status_code == 200:
                self.service_registry.register("api", ServiceStatus.HEALTHY)
                return HealthCheckResult(
                    name="api",
                    status="ok",
                    message=f"API responding (status: {response.status_code})",
                    latency_ms=latency,
                    timestamp=time.time(),
                )
            else:
                self.service_registry.register("api", ServiceStatus.DEGRADED)
                return HealthCheckResult(
                    name="api",
                    status="warning",
                    message=f"API returned status {response.status_code}",
                    latency_ms=latency,
                    timestamp=time.time(),
                )
        except Exception as e:
            self.service_registry.register("api", ServiceStatus.UNAVAILABLE, error=str(e))
            return HealthCheckResult(
                name="api",
                status="error",
                message=f"API health check failed: {e}",
                latency_ms=(time.time() - start) * 1000,
                timestamp=time.time(),
            )

    async def check_crm_models(self) -> HealthCheckResult:
        """Check CRM models are importable"""
        start = time.time()
        try:
            from app.modules.crm.models import Client, Interaction, Practice, PracticeType

            models = {
                "Client": Client,
                "Practice": Practice,
                "PracticeType": PracticeType,
                "Interaction": Interaction,
            }

            latency = (time.time() - start) * 1000
            return HealthCheckResult(
                name="crm_models",
                status="ok",
                message=f"CRM models imported successfully: {', '.join(models.keys())}",
                latency_ms=latency,
                metadata={"models": list(models.keys())},
                timestamp=time.time(),
            )
        except Exception as e:
            return HealthCheckResult(
                name="crm_models",
                status="error",
                message=f"CRM models import failed: {e}",
                latency_ms=(time.time() - start) * 1000,
                timestamp=time.time(),
            )

    async def check_collection_manager(self) -> HealthCheckResult:
        """Check CollectionManager initialization"""
        start = time.time()
        try:
            from services.collection_manager import CollectionManager

            manager = CollectionManager()
            collections = manager.list_collections()
            latency = (time.time() - start) * 1000

            return HealthCheckResult(
                name="collection_manager",
                status="ok",
                message=f"CollectionManager initialized ({len(collections)} collections)",
                latency_ms=latency,
                metadata={"collection_count": len(collections)},
                timestamp=time.time(),
            )
        except Exception as e:
            return HealthCheckResult(
                name="collection_manager",
                status="error",
                message=f"CollectionManager check failed: {e}",
                latency_ms=(time.time() - start) * 1000,
                timestamp=time.time(),
            )

    async def get_system_metrics(self) -> SystemMetrics:
        """Get system-level metrics"""
        return SystemMetrics(
            cpu_usage=psutil.cpu_percent(interval=1),
            memory_usage=psutil.virtual_memory().percent,
            disk_usage=psutil.disk_usage("/").percent,
            uptime=time.time() - self.start_time,
            timestamp=time.time(),
        )

    async def run_all_checks(self, use_cache: bool = True) -> dict[str, Any]:
        """
        Run all health checks and return comprehensive report

        Args:
            use_cache: Use cached results if available (default: True)

        Returns:
            Dictionary with all check results and system metrics
        """
        now = time.time()

        checks = [
            ("Database", self.check_database),
            ("Qdrant", self.check_qdrant),
            ("Redis", self.check_redis),
            ("API", self.check_api),
            ("CRM Models", self.check_crm_models),
            ("Collection Manager", self.check_collection_manager),
        ]

        results = []
        for name, check_func in checks:
            # Check cache
            if use_cache and name in self._check_cache:
                cached_time, cached_result = self._check_cache[name]
                if now - cached_time < self._cache_ttl:
                    results.append((name, cached_result))
                    continue

            # Run check
            try:
                result = await check_func()
                self._check_cache[name] = (now, result)
                results.append((name, result))
            except Exception as e:
                error_result = HealthCheckResult(
                    name=name.lower().replace(" ", "_"),
                    status="error",
                    message=f"Check failed: {e}",
                    timestamp=now,
                )
                results.append((name, error_result))

        # Get system metrics
        metrics = await self.get_system_metrics()

        # Get service registry status
        registry_status = self.service_registry.get_status()

        # Calculate overall health
        all_ok = all(r.status == "ok" for _, r in results)
        has_warnings = any(r.status == "warning" for _, r in results)
        has_errors = any(r.status == "error" for _, r in results)

        if has_errors:
            overall_status = "error"
        elif has_warnings:
            overall_status = "warning"
        elif all_ok:
            overall_status = "ok"
        else:
            overall_status = "unknown"

        return {
            "overall_status": overall_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {name: asdict(result) for name, result in results},
            "system_metrics": asdict(metrics),
            "service_registry": registry_status,
        }

    def format_report(self, report: dict[str, Any]) -> str:
        """Format health check report as human-readable string"""
        lines = []
        lines.append("=" * 60)
        lines.append("NUZANTARA HEALTH CHECK REPORT")
        lines.append("=" * 60)
        lines.append(f"Timestamp: {report['timestamp']}")
        lines.append(f"Overall Status: {report['overall_status'].upper()}")
        lines.append("")

        # System metrics
        metrics = report["system_metrics"]
        lines.append("System Metrics:")
        lines.append(f"  CPU: {metrics['cpu_usage']:.1f}%")
        lines.append(f"  Memory: {metrics['memory_usage']:.1f}%")
        lines.append(f"  Disk: {metrics['disk_usage']:.1f}%")
        lines.append(f"  Uptime: {metrics['uptime']:.0f}s")
        lines.append("")

        # Health checks
        lines.append("Health Checks:")
        for name, check in report["checks"].items():
            status = check["status"]
            if status == "ok":
                icon = "✅"
            elif status == "warning":
                icon = "⚠️"
            elif status == "skipped":
                icon = "⏭️"
            else:
                icon = "❌"

            latency = f" ({check['latency_ms']:.1f}ms)" if check.get("latency_ms") else ""
            lines.append(f"  {icon} {name}: {check['message']}{latency}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)


# Global singleton instance
_unified_health_service: UnifiedHealthService | None = None


def get_unified_health_service() -> UnifiedHealthService:
    """Get or create unified health service instance"""
    global _unified_health_service
    if _unified_health_service is None:
        _unified_health_service = UnifiedHealthService()
    return _unified_health_service
