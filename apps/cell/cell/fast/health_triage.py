"""Health Triage reflex — 5ms latency budget.
Pure threshold comparison. No LLM. No network calls."""
from enum import Enum


class HealthStatus(Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


def triage(cpu_percent: float, memory_percent: float, disk_io_wait: float) -> HealthStatus:
    """Classify system health from metrics."""
    if cpu_percent > 90 or memory_percent > 92:
        return HealthStatus.RED
    if cpu_percent > 75 or memory_percent > 80 or disk_io_wait > 50:
        return HealthStatus.YELLOW
    return HealthStatus.GREEN
