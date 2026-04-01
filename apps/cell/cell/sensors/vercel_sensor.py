"""VercelSensor — monitors the 6 Vercel-deployed subdomains.

Sends a HEAD request to each subdomain and checks for HTTP 200/307.
A 307 redirect (e.g. auth redirect) is considered alive (yellow),
while a connection error or 5xx is red.

Runs once per pulse (60s). Uses a single shared httpx.AsyncClient
passed in from main.py to avoid creating per-pulse connections.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger("cell.sensors.vercel")

_DEFAULT_SUBDOMAINS = [
    "https://kita.balizero.com",
    "https://my.balizero.com",
    "https://mail.balizero.com",
    "https://calendar.balizero.com",
    "https://drive.balizero.com",
    "https://zantara.balizero.com",
]


@dataclass
class SubdomainStatus:
    url: str
    status: str  # "green", "yellow", "red"
    status_code: int = 0
    response_time_ms: float = 0.0
    error: str = ""


@dataclass
class VercelReading:
    status: str  # worst across all subdomains
    subdomains: list[SubdomainStatus] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class VercelSensor:
    """HEAD-checks all Vercel subdomains concurrently.

    green  — 200
    yellow — 301/302/307/308 redirect (alive but auth-gated)
    red    — 4xx/5xx or connection error
    """

    def __init__(
        self,
        client: Any,
        urls: list[str] | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._client = client
        self._urls = urls or _DEFAULT_SUBDOMAINS
        self._timeout = timeout

    async def read(self) -> VercelReading:
        tasks = [self._check(url) for url in self._urls]
        results: list[SubdomainStatus] = await asyncio.gather(*tasks)

        _severity = {"green": 0, "yellow": 1, "red": 2}
        worst = max(results, key=lambda r: _severity.get(r.status, 0))
        down = [r.url for r in results if r.status == "red"]

        return VercelReading(
            status=worst.status,
            subdomains=results,
            metadata={"down": down, "total": len(results)},
        )

    async def _check(self, url: str) -> SubdomainStatus:
        import time
        t0 = time.monotonic()
        try:
            response = await self._client.head(
                url,
                timeout=self._timeout,
                follow_redirects=False,
            )
            elapsed_ms = (time.monotonic() - t0) * 1000
            code = response.status_code

            if code == 200:
                status = "green"
            elif 300 <= code < 400:
                status = "yellow"
            else:
                status = "red"

            return SubdomainStatus(
                url=url,
                status=status,
                status_code=code,
                response_time_ms=round(elapsed_ms, 1),
            )
        except httpx.TimeoutException:
            return SubdomainStatus(url=url, status="red", error="timeout")
        except Exception as e:
            return SubdomainStatus(url=url, status="red", error=str(e)[:120])
