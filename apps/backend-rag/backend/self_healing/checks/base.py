"""Protocol and result type for self-healing checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class CheckResult:
    healthy: bool
    detail: dict[str, Any] | None = None
    error: str | None = None


class HealthCheck(Protocol):
    name: str

    async def run(self) -> CheckResult: ...
