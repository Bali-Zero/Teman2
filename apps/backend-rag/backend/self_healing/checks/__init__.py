"""
Diagnostic checks used by the self-healing orchestrator.

Each check implements the `HealthCheck` protocol:
- `name` — human-readable identifier
- `async def run() -> CheckResult` — executes and returns healthy/unhealthy

Checks never mutate state; remediation is the responsibility of the
corresponding `actions/` module.
"""

from backend.self_healing.checks.base import CheckResult, HealthCheck
from backend.self_healing.checks.cache import CacheCheck
from backend.self_healing.checks.db import DBCheck
from backend.self_healing.checks.http_api import HTTPAPICheck
from backend.self_healing.checks.system import CPUCheck, DiskCheck, MemoryCheck

__all__ = [
    "CPUCheck",
    "CacheCheck",
    "CheckResult",
    "DBCheck",
    "DiskCheck",
    "HTTPAPICheck",
    "HealthCheck",
    "MemoryCheck",
]
