"""
Unit tests for ServiceRegistry and service health tracking.
"""

from datetime import datetime, timezone

from app.core.service_health import (
    ServiceHealth,
    ServiceRegistry,
    ServiceStatus,
)


class TestServiceStatus:
    """Tests for ServiceStatus enum."""

    def test_status_values(self):
        """Test that all expected status values exist."""
        assert ServiceStatus.HEALTHY.value == "healthy"
        assert ServiceStatus.DEGRADED.value == "degraded"
        assert ServiceStatus.UNAVAILABLE.value == "unavailable"


class TestServiceHealth:
    """Tests for ServiceHealth dataclass."""

    def test_create_healthy_service(self):
        """Test creating a healthy service entry."""
        service = ServiceHealth(
            name="test_service",
            status=ServiceStatus.HEALTHY,
            is_critical=True,
            initialized_at=datetime.now(timezone.utc),
        )
        assert service.name == "test_service"
        assert service.status == ServiceStatus.HEALTHY
        assert service.is_critical is True
        assert service.error is None

    def test_create_failed_service(self):
        """Test creating a failed service entry with error."""
        service = ServiceHealth(
            name="test_service",
            status=ServiceStatus.UNAVAILABLE,
            error="Connection refused",
            is_critical=True,
        )
        assert service.status == ServiceStatus.UNAVAILABLE
        assert service.error == "Connection refused"

    def test_to_dict(self):
        """Test converting service health to dictionary."""
        service = ServiceHealth(
            name="test_service",
            status=ServiceStatus.HEALTHY,
            is_critical=False,
        )
        result = service.to_dict()

        assert result["name"] == "test_service"
        assert result["status"] == "healthy"
        assert result["is_critical"] is False
        assert result["error"] is None


class TestServiceRegistry:
    """Tests for ServiceRegistry."""

    def test_register_healthy_service(self):
        """Test registering a healthy service."""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.HEALTHY)

        service = registry.get_service("search")
        assert service is not None
        assert service.status == ServiceStatus.HEALTHY
        assert service.is_critical is True  # search is in CRITICAL_SERVICES

    def test_register_failed_service(self):
        """Test registering a failed service with error."""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.UNAVAILABLE, error="Qdrant down")

        service = registry.get_service("search")
        assert service is not None
        assert service.status == ServiceStatus.UNAVAILABLE
        assert service.error == "Qdrant down"

    def test_critical_service_auto_detection(self):
        """Test that critical services are auto-detected."""
        registry = ServiceRegistry()

        # "search" and "ai" are in CRITICAL_SERVICES
        registry.register("search", ServiceStatus.HEALTHY)
        registry.register("ai", ServiceStatus.HEALTHY)
        registry.register("database", ServiceStatus.HEALTHY)

        assert registry.get_service("search").is_critical is True
        assert registry.get_service("ai").is_critical is True
        assert registry.get_service("database").is_critical is False

    def test_override_critical_flag(self):
        """Test that critical flag can be overridden."""
        registry = ServiceRegistry()

        # Override auto-detection
        registry.register("search", ServiceStatus.HEALTHY, critical=False)
        registry.register("custom", ServiceStatus.HEALTHY, critical=True)

        assert registry.get_service("search").is_critical is False
        assert registry.get_service("custom").is_critical is True

    def test_get_critical_failures_none(self):
        """Test getting critical failures when all healthy."""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.HEALTHY)
        registry.register("ai", ServiceStatus.HEALTHY)

        failures = registry.get_critical_failures()
        assert len(failures) == 0

    def test_get_critical_failures_with_failure(self):
        """Test getting critical failures when one fails."""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.UNAVAILABLE, error="Connection failed")
        registry.register("ai", ServiceStatus.HEALTHY)

        failures = registry.get_critical_failures()
        assert len(failures) == 1
        assert failures[0].name == "search"

    def test_has_critical_failures(self):
        """Test checking for critical failures."""
        registry = ServiceRegistry()

        # No failures initially
        registry.register("search", ServiceStatus.HEALTHY)
        registry.register("ai", ServiceStatus.HEALTHY)
        assert registry.has_critical_failures() is False

        # Add critical failure
        registry.register("search", ServiceStatus.UNAVAILABLE, error="Down")
        assert registry.has_critical_failures() is True

    def test_non_critical_failure_not_critical(self):
        """Test that non-critical failures don't trigger critical status."""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.HEALTHY)
        registry.register("ai", ServiceStatus.HEALTHY)
        registry.register("database", ServiceStatus.UNAVAILABLE, error="DB down")

        assert registry.has_critical_failures() is False

    def test_overall_status_healthy(self):
        """Test overall status when all healthy."""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.HEALTHY)
        registry.register("ai", ServiceStatus.HEALTHY)

        status = registry.get_status()
        assert status["overall"] == "healthy"

    def test_overall_status_critical(self):
        """Test overall status when critical service down."""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.UNAVAILABLE)
        registry.register("ai", ServiceStatus.HEALTHY)

        status = registry.get_status()
        assert status["overall"] == "critical"

    def test_overall_status_degraded(self):
        """Test overall status when non-critical service down."""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.HEALTHY)
        registry.register("ai", ServiceStatus.HEALTHY)
        registry.register("database", ServiceStatus.UNAVAILABLE)

        status = registry.get_status()
        assert status["overall"] == "degraded"

    def test_overall_status_unknown_when_empty(self):
        """Test overall status when no services registered."""
        registry = ServiceRegistry()
        status = registry.get_status()
        assert status["overall"] == "unknown"

    def test_get_status_includes_all_services(self):
        """Test that get_status includes all registered services."""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.HEALTHY)
        registry.register("ai", ServiceStatus.HEALTHY)
        registry.register("database", ServiceStatus.DEGRADED)

        status = registry.get_status()

        assert "services" in status
        assert "search" in status["services"]
        assert "ai" in status["services"]
        assert "database" in status["services"]
        assert "timestamp" in status
        assert "critical_services" in status

    def test_format_failures_message_empty(self):
        """Test formatting failures message when no failures."""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.HEALTHY)

        message = registry.format_failures_message()
        assert message == ""

    def test_format_failures_message_with_failures(self):
        """Test formatting failures message with failures."""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.UNAVAILABLE, error="Connection refused")
        registry.register("ai", ServiceStatus.UNAVAILABLE, error="API key invalid")

        message = registry.format_failures_message()

        assert "Critical services failed to initialize" in message
        assert "search" in message
        assert "Connection refused" in message
        assert "ai" in message
        assert "API key invalid" in message

    def test_update_existing_service(self):
        """Test updating an existing service status."""
        registry = ServiceRegistry()

        # Initially healthy
        registry.register("search", ServiceStatus.HEALTHY)
        assert registry.get_service("search").status == ServiceStatus.HEALTHY

        # Update to unavailable
        registry.register("search", ServiceStatus.UNAVAILABLE, error="Connection lost")
        assert registry.get_service("search").status == ServiceStatus.UNAVAILABLE
        assert registry.get_service("search").error == "Connection lost"
