"""
ZANTARA RAG - Service Health Registry

Provides centralized tracking of service health status for fail-fast behavior
and health-based degradation in production environments.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class ServiceStatus(Enum):
    """Service health status levels."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass
class ServiceHealth:
    """Health information for a single service."""

    name: str
    status: ServiceStatus
    error: str | None = None
    is_critical: bool = False
    initialized_at: datetime | None = None
    last_check: datetime | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "status": self.status.value,
            "error": self.error,
            "is_critical": self.is_critical,
            "initialized_at": self.initialized_at.isoformat() if self.initialized_at else None,
            "last_check": self.last_check.isoformat() if self.last_check else None,
        }


class ServiceRegistry:
    """
    Registry for tracking service health status.

    Provides:
    - Service registration with health status
    - Overall system health assessment
    - Critical service failure detection
    - Health reporting for monitoring endpoints
    """

    # Define which services are critical for system operation
    CRITICAL_SERVICES = {"search", "ai"}

    def __init__(self):
        self._services: dict[str, ServiceHealth] = {}

    def register(
        self,
        name: str,
        status: ServiceStatus,
        error: str | None = None,
        critical: bool | None = None,
    ) -> None:
        """
        Register or update a service's health status.

        Args:
            name: Service identifier
            status: Current health status
            error: Error message if status is not HEALTHY
            critical: Whether service is critical (auto-detected if None)
        """
        is_critical = critical if critical is not None else (name in self.CRITICAL_SERVICES)

        self._services[name] = ServiceHealth(
            name=name,
            status=status,
            error=error,
            is_critical=is_critical,
            initialized_at=datetime.now(timezone.utc) if status == ServiceStatus.HEALTHY else None,
            last_check=datetime.now(timezone.utc),
        )

    def get_service(self, name: str) -> ServiceHealth | None:
        """Get health info for a specific service."""
        return self._services.get(name)

    def get_critical_failures(self) -> list[ServiceHealth]:
        """Get list of critical services that are unavailable."""
        return [
            s
            for s in self._services.values()
            if s.is_critical and s.status == ServiceStatus.UNAVAILABLE
        ]

    def has_critical_failures(self) -> bool:
        """Check if any critical services have failed."""
        return len(self.get_critical_failures()) > 0

    def _overall_status(self) -> str:
        """
        Calculate overall system health status.

        Returns:
            "critical" - if any critical service is unavailable
            "degraded" - if any service is not healthy
            "healthy" - if all services are healthy
        """
        if not self._services:
            return "unknown"

        # Check for critical failures first
        critical_down = any(
            s.status == ServiceStatus.UNAVAILABLE and s.is_critical for s in self._services.values()
        )
        if critical_down:
            return "critical"

        # Check for any degradation
        any_degraded = any(s.status != ServiceStatus.HEALTHY for s in self._services.values())
        return "degraded" if any_degraded else "healthy"

    def get_status(self) -> dict:
        """
        Get complete health status report.

        Returns:
            Dictionary with overall status and per-service breakdown
        """
        return {
            "overall": self._overall_status(),
            "services": {k: v.to_dict() for k, v in self._services.items()},
            "critical_services": list(self.CRITICAL_SERVICES),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def format_failures_message(self) -> str:
        """Format critical failures as human-readable message."""
        failures = self.get_critical_failures()
        if not failures:
            return ""

        lines = ["Critical services failed to initialize:"]
        for service in failures:
            error_info = f": {service.error}" if service.error else ""
            lines.append(f"  - {service.name}{error_info}")

        return "\n".join(lines)


# Global singleton instance
service_registry = ServiceRegistry()
