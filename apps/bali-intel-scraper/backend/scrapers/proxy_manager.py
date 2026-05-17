"""
Proxy rotation system for web scraping.

Manages a pool of proxies and rotates them to avoid IP blocking.
"""

import asyncio
import random
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse
from datetime import datetime

import aiohttp

from backend.core.logger import get_logger, LogAction
import contextlib

logger = get_logger(__name__, component="proxy_manager")


class ProxyStatus(Enum):
    """Proxy health status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    BANNED = "banned"
    CHECKING = "checking"


@dataclass
class Proxy:
    """Proxy configuration and status."""

    url: str
    username: str | None = None
    password: str | None = None
    country: str | None = None
    status: ProxyStatus = ProxyStatus.HEALTHY
    fail_count: int = 0
    success_count: int = 0
    last_used: datetime | None = None
    last_checked: datetime | None = None
    response_time_ms: float = 0.0
    banned_hosts: set[str] = None

    def __post_init__(self):
        if self.banned_hosts is None:
            self.banned_hosts = set()

    @property
    def is_available(self) -> bool:
        """Check if proxy is available for use."""
        return self.status in (ProxyStatus.HEALTHY, ProxyStatus.DEGRADED)

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate."""
        total = self.success_count + self.fail_count
        if total == 0:
            return 0.0
        return self.fail_count / total

    def to_playwright_format(self) -> dict[str, str]:
        """Convert to Playwright proxy format."""
        parsed = urlparse(self.url)
        proxy_dict = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}

        if self.username:
            proxy_dict["username"] = self.username
        if self.password:
            proxy_dict["password"] = self.password

        return proxy_dict

    def to_aiohttp_format(self) -> str:
        """Convert to aiohttp proxy format."""
        parsed = urlparse(self.url)

        if self.username and self.password:
            return f"{parsed.scheme}://{self.username}:{self.password}@{parsed.hostname}:{parsed.port}"

        return self.url


class ProxyManager:
    """Manages proxy pool and rotation."""

    def __init__(
        self,
        max_failures: int = 3,
        health_check_interval: int = 300,
        cooldown_period: int = 600,
    ):
        self.max_failures = max_failures
        self.health_check_interval = health_check_interval
        self.cooldown_period = cooldown_period

        self._proxies: list[Proxy] = []
        self._proxy_index: dict[str, Proxy] = {}
        self._lock = asyncio.Lock()
        self._health_check_task: asyncio.Task | None = None

    def add_proxy(
        self,
        url: str,
        username: str | None = None,
        password: str | None = None,
        country: str | None = None,
    ) -> Proxy:
        """Add a proxy to the pool."""
        proxy = Proxy(url=url, username=username, password=password, country=country)

        self._proxies.append(proxy)
        self._proxy_index[url] = proxy

        logger.info(
            f"Added proxy {url}", action=LogAction.UPDATE, metadata={"country": country}
        )

        return proxy

    def add_proxies_from_env(self) -> None:
        """Load proxies from environment variable."""
        from config.settings import settings

        for proxy_url in settings.scraping.proxy_list:
            if proxy_url.strip():
                self.add_proxy(proxy_url.strip())

    def remove_proxy(self, url: str) -> bool:
        """Remove a proxy from the pool."""
        if url in self._proxy_index:
            proxy = self._proxy_index.pop(url)
            self._proxies.remove(proxy)
            return True
        return False

    async def get_proxy(
        self,
        target_host: str | None = None,
        country: str | None = None,
        strategy: str = "round_robin",
    ) -> Proxy | None:
        """Get a proxy using specified strategy."""
        async with self._lock:
            available = [
                p
                for p in self._proxies
                if p.is_available
                and (target_host is None or target_host not in p.banned_hosts)
                and (country is None or p.country == country)
            ]

            if not available:
                return None

            if strategy == "round_robin":
                # Sort by last used time
                available.sort(key=lambda p: p.last_used or datetime.min)
                proxy = available[0]

            elif strategy == "random":
                proxy = random.choice(available)

            elif strategy == "best_performance":
                # Sort by response time and failure rate
                available.sort(
                    key=lambda p: (
                        p.failure_rate,
                        p.response_time_ms if p.response_time_ms > 0 else float("inf"),
                    )
                )
                proxy = available[0]

            elif strategy == "weighted":
                # Weight by success count
                weights = [max(1, p.success_count) for p in available]
                total = sum(weights)
                r = random.uniform(0, total)
                cumsum = 0
                proxy = available[0]
                for p, w in zip(available, weights):
                    cumsum += w
                    if r <= cumsum:
                        proxy = p
                        break
            else:
                proxy = available[0]

            proxy.last_used = datetime.now()
            return proxy

    async def report_success(self, proxy_url: str, response_time_ms: float) -> None:
        """Report successful proxy usage."""
        async with self._lock:
            proxy = self._proxy_index.get(proxy_url)
            if proxy:
                proxy.success_count += 1
                proxy.response_time_ms = (
                    (proxy.response_time_ms * 0.8 + response_time_ms * 0.2)
                    if proxy.response_time_ms > 0
                    else response_time_ms
                )

                # Recover from degraded state
                if proxy.status == ProxyStatus.DEGRADED and proxy.failure_rate < 0.3:
                    proxy.status = ProxyStatus.HEALTHY

    async def report_failure(
        self, proxy_url: str, error: str | None = None, host: str | None = None
    ) -> None:
        """Report failed proxy usage."""
        async with self._lock:
            proxy = self._proxy_index.get(proxy_url)
            if not proxy:
                return

            proxy.fail_count += 1

            # Check if banned by specific host
            if host and error and "blocked" in error.lower():
                proxy.banned_hosts.add(host)
                logger.warning(
                    f"Proxy {proxy_url} banned by {host}",
                    action=LogAction.UPDATE,
                    metadata={"host": host},
                )

            # Update status
            if proxy.fail_count >= self.max_failures:
                proxy.status = ProxyStatus.BANNED
                logger.warning(
                    f"Proxy {proxy_url} marked as banned",
                    action=LogAction.UPDATE,
                    metadata={
                        "fail_count": proxy.fail_count,
                        "failure_rate": proxy.failure_rate,
                    },
                )
            elif proxy.failure_rate > 0.5:
                proxy.status = ProxyStatus.DEGRADED

    async def start_health_checks(self) -> None:
        """Start periodic health check task."""
        if self._health_check_task is not None:
            return

        self._health_check_task = asyncio.create_task(self._health_check_loop())

    async def stop_health_checks(self) -> None:
        """Stop health check task."""
        if self._health_check_task:
            self._health_check_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._health_check_task
            self._health_check_task = None

    async def _health_check_loop(self) -> None:
        """Periodic health check loop."""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                await self._check_all_proxies()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "Health check loop error",
                    action=LogAction.ERROR,
                    metadata={"error": str(e)},
                )

    async def _check_all_proxies(self) -> None:
        """Check health of all proxies."""
        logger.info("Starting proxy health checks", action=LogAction.START)

        tasks = []
        for proxy in self._proxies:
            if proxy.status != ProxyStatus.CHECKING:
                tasks.append(self._check_proxy(proxy))

        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("Proxy health checks completed", action=LogAction.END)

    async def _check_proxy(self, proxy: Proxy) -> None:
        """Check health of a single proxy."""
        proxy.status = ProxyStatus.CHECKING
        proxy.last_checked = datetime.now()

        test_url = "http://httpbin.org/ip"

        try:
            start = asyncio.get_event_loop().time()

            async with aiohttp.ClientSession() as session, session.get(
                test_url,
                proxy=proxy.to_aiohttp_format(),
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                await response.text()

                response_time = (asyncio.get_event_loop().time() - start) * 1000

                # Mark as healthy
                proxy.status = ProxyStatus.HEALTHY
                proxy.response_time_ms = response_time

                # Reset fail count on successful check
                if proxy.fail_count > 0:
                    proxy.fail_count = max(0, proxy.fail_count - 1)

        except Exception as e:
            logger.warning(
                f"Proxy health check failed for {proxy.url}",
                action=LogAction.ERROR,
                metadata={"error": str(e)},
            )
            proxy.fail_count += 1

            if proxy.fail_count >= self.max_failures:
                proxy.status = ProxyStatus.BANNED
            else:
                proxy.status = ProxyStatus.DEGRADED

    def get_stats(self) -> dict:
        """Get proxy pool statistics."""
        status_counts = {}
        for proxy in self._proxies:
            status = proxy.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total": len(self._proxies),
            "by_status": status_counts,
            "avg_response_time_ms": sum(
                p.response_time_ms for p in self._proxies if p.response_time_ms > 0
            )
            / max(1, len([p for p in self._proxies if p.response_time_ms > 0])),
            "total_requests": sum(
                p.success_count + p.fail_count for p in self._proxies
            ),
            "total_success": sum(p.success_count for p in self._proxies),
            "total_failures": sum(p.fail_count for p in self._proxies),
        }


# Global proxy manager instance
proxy_manager = ProxyManager()


async def init_proxy_manager() -> None:
    """Initialize and load proxies."""
    proxy_manager.add_proxies_from_env()
    await proxy_manager.start_health_checks()


async def close_proxy_manager() -> None:
    """Stop proxy manager."""
    await proxy_manager.stop_health_checks()


__all__ = [
    "ProxyManager",
    "Proxy",
    "ProxyStatus",
    "proxy_manager",
    "init_proxy_manager",
    "close_proxy_manager",
]
