"""System-resource checks: CPU, memory, disk."""

from __future__ import annotations

import psutil

from backend.self_healing.checks.base import CheckResult


class CPUCheck:
    name = "cpu"

    def __init__(self, threshold_percent: float = 90.0) -> None:
        self.threshold_percent = threshold_percent

    async def run(self) -> CheckResult:
        try:
            cpu = psutil.cpu_percent(interval=1)
        except Exception as exc:  # noqa: BLE001
            return CheckResult(healthy=False, error=f"{type(exc).__name__}: {exc}")
        healthy = cpu < self.threshold_percent
        return CheckResult(
            healthy=healthy,
            detail={"cpu_percent": cpu, "threshold": self.threshold_percent},
            error=f"CPU at {cpu:.1f}%" if not healthy else None,
        )


class MemoryCheck:
    name = "memory"

    def __init__(self, threshold_percent: float = 90.0) -> None:
        self.threshold_percent = threshold_percent

    async def run(self) -> CheckResult:
        try:
            memory = psutil.virtual_memory().percent
        except Exception as exc:  # noqa: BLE001
            return CheckResult(healthy=False, error=f"{type(exc).__name__}: {exc}")
        healthy = memory < self.threshold_percent
        return CheckResult(
            healthy=healthy,
            detail={"memory_percent": memory, "threshold": self.threshold_percent},
            error=f"Memory at {memory:.1f}%" if not healthy else None,
        )


class DiskCheck:
    name = "disk"

    def __init__(self, threshold_percent: float = 90.0, path: str = "/") -> None:
        self.threshold_percent = threshold_percent
        self.path = path

    async def run(self) -> CheckResult:
        try:
            disk = psutil.disk_usage(self.path).percent
        except Exception as exc:  # noqa: BLE001
            return CheckResult(healthy=False, error=f"{type(exc).__name__}: {exc}")
        healthy = disk < self.threshold_percent
        return CheckResult(
            healthy=healthy,
            detail={"disk_percent": disk, "path": self.path, "threshold": self.threshold_percent},
            error=f"Disk at {disk:.1f}%" if not healthy else None,
        )
