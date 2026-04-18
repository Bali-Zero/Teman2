"""
Outbound event reporter for the self-healing agent.

Posts events to the central orchestrator over HTTP. Failures are swallowed
(logged at debug) — the reporter must never take down the agent itself.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class OrchestratorReporter:
    def __init__(
        self,
        orchestrator_url: str,
        http_client: httpx.AsyncClient,
        service_name: str,
        hostname: str | None = None,
        region: str | None = None,
    ) -> None:
        self.orchestrator_url = orchestrator_url
        self.http_client = http_client
        self.service_name = service_name
        self.hostname = hostname
        self.region = region

    async def report(self, event: dict[str, Any]) -> None:
        payload = {
            "agent": "backend",
            "service": self.service_name,
            "hostname": self.hostname or "unknown",
            "region": self.region or "unknown",
            "event": event,
            "timestamp": time.time(),
        }
        try:
            await self.http_client.post(
                f"{self.orchestrator_url}/api/report",
                json=payload,
                timeout=5.0,
            )
        except Exception as exc:  # noqa: BLE001 — never crash on reporting
            logger.debug(f"Failed to report to orchestrator: {exc}")
