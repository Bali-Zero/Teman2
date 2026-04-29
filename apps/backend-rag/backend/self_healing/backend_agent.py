"""
🤖 ZANTARA Backend Self-Healing Agent (decomposed 2026-04-18)

Thin façade preserving the legacy API consumed by
`backend/services/misc/autonomous_scheduler.py`:
- perform_health_check()
- detect_issues()
- attempt_auto_fix(issues)

Internally delegates to:
- `checks/` — CPU / memory / disk / api / db / cache
- `actions/` — gc / reconnect_cache / restart_service
- `circuit_breaker.py` — per-check N-failure cooldown
- `orchestrator.py` — single `run_cycle()` that composes the above
- `reporter.py` — orchestrator HTTP reporting
- `metrics.py` — stats exposed via `/api/admin/self-healing/stats`

Run standalone for parity with the pre-decomposition entrypoint.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
import traceback
from dataclasses import asdict, dataclass
from typing import Any

import httpx
import psutil

from backend.self_healing.actions import (
    GCAction,
    ReconnectCacheAction,
    RestartServiceAction,
)
from backend.self_healing.checks import (
    CacheCheck,
    CPUCheck,
    DBCheck,
    DiskCheck,
    HTTPAPICheck,
    MemoryCheck,
)
from backend.self_healing.orchestrator import SelfHealingOrchestrator
from backend.self_healing.reporter import OrchestratorReporter

logging.basicConfig(
    level=logging.INFO, format="🤖 [Backend Agent] %(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class HealthMetrics:
    """Legacy dataclass preserved for autonomous_scheduler + snapshot parity."""

    timestamp: float
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    api_healthy: bool
    db_healthy: bool
    cache_healthy: bool
    error_count: int
    fix_count: int
    uptime: float


class BackendSelfHealingAgent:
    """Self-healing agent for backend services (decomposed internals)."""

    def __init__(
        self,
        service_name: str,
        orchestrator_url: str = "https://nuzantara-orchestrator.fly.dev",
        check_interval: int = 30,
        auto_fix_enabled: bool = False,
        *,
        failure_threshold: int = 3,
        cooldown_seconds: float = 60.0,
    ) -> None:
        self.service_name = service_name
        self.orchestrator_url = orchestrator_url
        self.check_interval = check_interval
        self.auto_fix_enabled = auto_fix_enabled

        self.start_time = time.time()
        self.error_count = 0
        self.fix_count = 0
        # Golden Rule #10: lazy-init via property; close() releases on
        # lifespan teardown.
        self._http_client: httpx.AsyncClient | None = None

        # Wire dependencies
        try:
            from backend.app.core.config import settings as _settings

            redis_url = _settings.redis_url
            hostname = _settings.hostname
            region = _settings.fly_region
        except Exception:  # noqa: BLE001
            redis_url, hostname, region = None, None, None

        self._reconnect_cache_action = ReconnectCacheAction(redis_url=redis_url)
        self._cache_check = CacheCheck(redis_client=self._reconnect_cache_action.redis_client)

        self.orchestrator = SelfHealingOrchestrator(
            checks=[
                CPUCheck(),
                MemoryCheck(),
                DiskCheck(),
                HTTPAPICheck("http://localhost:8080/health", client=self.http_client),
                DBCheck(),
                self._cache_check,
            ],
            actions=[
                GCAction(),
                self._reconnect_cache_action,
                RestartServiceAction(),
            ],
            failure_threshold=failure_threshold,
            cooldown_seconds=cooldown_seconds,
            reporter=OrchestratorReporter(
                orchestrator_url=orchestrator_url,
                http_client=self.http_client,
                service_name=service_name,
                hostname=hostname,
                region=region,
            ),
        )

        logger.info(f"Initializing agent for service: {service_name}")

    @property
    def http_client(self) -> httpx.AsyncClient:
        """Lazy-init persistent AsyncClient (Golden Rule #10).

        The orchestrator captures the reference once during ``__init__``
        (via ``HTTPAPICheck`` and ``OrchestratorReporter``) — subsequent
        access here returns the same client unless it was closed
        externally, in which case a fresh one is created.
        """
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=10.0)
        return self._http_client

    async def close(self) -> None:
        """Release the HTTP client (lifespan shutdown hook)."""
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()
        self._http_client = None

    # ── Legacy API preserved for autonomous_scheduler ──

    async def perform_health_check(self) -> HealthMetrics | None:
        """Run one cycle and project results into the legacy dataclass shape."""
        outcome = await self.orchestrator.run_cycle()

        def _healthy(name: str) -> bool:
            r = outcome.check_results.get(name)
            return r.healthy if r is not None else True  # Skipped → breaker open → treat as unchanged

        def _percent(name: str, field: str) -> float:
            r = outcome.check_results.get(name)
            if r is None or r.detail is None:
                return 0.0
            return float(r.detail.get(field, 0.0))

        try:
            return HealthMetrics(
                timestamp=time.time(),
                cpu_usage=_percent("cpu", "cpu_percent"),
                memory_usage=_percent("memory", "memory_percent"),
                disk_usage=_percent("disk", "disk_percent"),
                api_healthy=_healthy("api"),
                db_healthy=_healthy("db"),
                cache_healthy=_healthy("cache"),
                error_count=self.error_count,
                fix_count=self.fix_count,
                uptime=time.time() - self.start_time,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Health check projection failed: {exc}")
            return None

    async def detect_issues(self) -> list[dict]:
        """
        Legacy-shape issue list. The orchestrator already ran the checks on
        the most recent cycle, so we re-run them once here for a fresh view
        (the scheduler calls detect_issues → attempt_auto_fix as a pair).
        """
        issues: list[dict] = []
        # Snapshot breaker states + run checks once through the orchestrator
        outcome = await self.orchestrator.run_cycle()

        severity_map = {
            "cpu": "high",
            "memory": "critical",
            "disk": "high",
            "api": "critical",
            "db": "critical",
            "cache": "medium",
        }
        type_map = {
            "cpu": "high_cpu",
            "memory": "high_memory",
            "disk": "high_disk",
            "api": "api_down",
            "db": "db_down",
            "cache": "cache_down",
        }

        for name, result in outcome.check_results.items():
            if result.healthy:
                continue
            issues.append({
                "type": type_map.get(name, name),
                "severity": severity_map.get(name, "medium"),
                "message": result.error or f"{name} check failed",
                "detail": result.detail,
            })

        if issues:
            logger.warning(
                f"Detected {len(issues)} issue(s): {[i['type'] for i in issues]}",
            )
        return issues

    async def attempt_auto_fix(self, issues: list[dict]) -> None:
        """
        Legacy hook — the orchestrator already fired actions on the cycle
        that produced `issues`. We re-report here for parity with the old
        log line format used by the scheduler.
        """
        if not issues:
            return
        fix_snapshot = self.orchestrator.stats.snapshot().get("actions", {})
        for issue in issues:
            logger.info(f"🔧 Auto-fix cycle already handled: {issue['type']}")
            action_hits = [
                name for name, s in fix_snapshot.items() if s.get("last_run_at")
            ]
            if action_hits:
                self.fix_count += 1
            else:
                self.error_count += 1

    def get_status(self) -> dict:
        return {
            "service": self.service_name,
            "uptime": time.time() - self.start_time,
            "error_count": self.error_count,
            "fix_count": self.fix_count,
            "stats": self.orchestrator.get_stats(),
        }

    # ── Standalone loop (unchanged behavior) ──

    async def start(self) -> None:
        logger.info("🚀 Starting self-healing agent...")
        await self.monitoring_loop()

    async def monitoring_loop(self) -> None:
        while True:
            try:
                await self.orchestrator.run_cycle()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Error in monitoring loop: {exc}")
                logger.error(traceback.format_exc())
                await asyncio.sleep(5)


# ── Auto-start when run directly ──

if __name__ == "__main__":
    from backend.app.core.config import settings

    agent = BackendSelfHealingAgent(service_name=settings.service_name)
    try:
        asyncio.run(agent.start())
    except KeyboardInterrupt:
        logger.info("Agent stopped by user")
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Agent crashed: {exc}")
        logger.error(traceback.format_exc())
        sys.exit(1)


# Legacy symbols re-exported for any callers that imported from this module
__all__ = [
    "BackendSelfHealingAgent",
    "HealthMetrics",
    "SelfHealingOrchestrator",
    "asdict",  # kept for backward compat with any external re-export
    "psutil",
]
