"""
Unit tests for ServiceHealth and ServiceRegistry
Target: >95% coverage
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.core.service_health import ServiceHealth, ServiceRegistry, ServiceStatus, service_registry


class TestServiceHealth:
    """Tests for ServiceHealth"""

    def test_init(self):
        """Test initialization"""
        health = ServiceHealth(name="test_service", status=ServiceStatus.HEALTHY)
        assert health.name == "test_service"
        assert health.status == ServiceStatus.HEALTHY
        assert health.error is None
        assert health.is_critical is False

    def test_init_with_all_fields(self):
        """Test initialization with all fields"""
        now = datetime.now(timezone.utc)
        health = ServiceHealth(
            name="test_service",
            status=ServiceStatus.DEGRADED,
            error="Test error",
            is_critical=True,
            initialized_at=now,
            last_check=now,
        )
        assert health.name == "test_service"
        assert health.status == ServiceStatus.DEGRADED
        assert health.error == "Test error"
        assert health.is_critical is True
        assert health.initialized_at == now

    def test_to_dict(self):
        """Test converting to dictionary"""
        now = datetime.now(timezone.utc)
        health = ServiceHealth(
            name="test_service", status=ServiceStatus.HEALTHY, initialized_at=now, last_check=now
        )
        result = health.to_dict()
        assert result["name"] == "test_service"
        assert result["status"] == "healthy"
        assert result["initialized_at"] == now.isoformat()
        assert result["last_check"] == now.isoformat()

    def test_to_dict_with_error(self):
        """Test converting to dictionary with error"""
        health = ServiceHealth(
            name="test_service", status=ServiceStatus.UNAVAILABLE, error="Service error"
        )
        result = health.to_dict()
        assert result["error"] == "Service error"
        assert result["status"] == "unavailable"


class TestServiceRegistry:
    """Tests for ServiceRegistry"""

    def test_init(self):
        """Test initialization"""
        registry = ServiceRegistry()
        assert len(registry._services) == 0
        assert "search" in registry.CRITICAL_SERVICES
        assert "ai" in registry.CRITICAL_SERVICES

    def test_register_service(self):
        """Test registering a service"""
        registry = ServiceRegistry()
        registry.register("test_service", ServiceStatus.HEALTHY)

        service = registry.get_service("test_service")
        assert service is not None
        assert service.name == "test_service"
        assert service.status == ServiceStatus.HEALTHY
        assert service.is_critical is False

    def test_register_critical_service(self):
        """Test registering a critical service"""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.HEALTHY)

        service = registry.get_service("search")
        assert service is not None
        assert service.is_critical is True

    def test_register_with_error(self):
        """Test registering service with error"""
        registry = ServiceRegistry()
        registry.register("test_service", ServiceStatus.UNAVAILABLE, error="Connection failed")

        service = registry.get_service("test_service")
        assert service.error == "Connection failed"
        assert service.status == ServiceStatus.UNAVAILABLE

    def test_register_with_explicit_critical(self):
        """Test registering service with explicit critical flag"""
        registry = ServiceRegistry()
        registry.register("test_service", ServiceStatus.HEALTHY, critical=True)

        service = registry.get_service("test_service")
        assert service.is_critical is True

    def test_register_updates_existing(self):
        """Test registering updates existing service"""
        registry = ServiceRegistry()
        registry.register("test_service", ServiceStatus.HEALTHY)
        registry.register("test_service", ServiceStatus.DEGRADED, error="Degraded")

        service = registry.get_service("test_service")
        assert service.status == ServiceStatus.DEGRADED
        assert service.error == "Degraded"

    def test_get_service_not_found(self):
        """Test getting non-existent service"""
        registry = ServiceRegistry()
        service = registry.get_service("nonexistent")
        assert service is None

    def test_get_critical_failures(self):
        """Test getting critical failures"""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.UNAVAILABLE, error="Failed")
        registry.register("ai", ServiceStatus.HEALTHY)
        registry.register("test_service", ServiceStatus.UNAVAILABLE)  # Not critical

        failures = registry.get_critical_failures()
        assert len(failures) == 1
        assert failures[0].name == "search"

    def test_get_critical_failures_none(self):
        """Test getting critical failures when none exist"""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.HEALTHY)

        failures = registry.get_critical_failures()
        assert len(failures) == 0

    def test_has_critical_failures_true(self):
        """Test has_critical_failures returns True"""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.UNAVAILABLE)

        assert registry.has_critical_failures() is True

    def test_has_critical_failures_false(self):
        """Test has_critical_failures returns False"""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.HEALTHY)

        assert registry.has_critical_failures() is False

    def test_overall_status_healthy(self):
        """Test overall status when all healthy"""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.HEALTHY)
        registry.register("ai", ServiceStatus.HEALTHY)

        status = registry._overall_status()
        assert status == "healthy"

    def test_overall_status_degraded(self):
        """Test overall status when some degraded"""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.HEALTHY)
        registry.register("ai", ServiceStatus.DEGRADED)

        status = registry._overall_status()
        assert status == "degraded"

    def test_overall_status_critical(self):
        """Test overall status when critical service unavailable"""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.UNAVAILABLE)
        registry.register("ai", ServiceStatus.HEALTHY)

        status = registry._overall_status()
        assert status == "critical"

    def test_overall_status_unknown(self):
        """Test overall status when no services registered"""
        registry = ServiceRegistry()
        status = registry._overall_status()
        assert status == "unknown"

    def test_get_status(self):
        """Test getting complete status"""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.HEALTHY)

        status = registry.get_status()
        assert "overall" in status
        assert "services" in status
        assert "critical_services" in status
        assert "timestamp" in status
        assert status["overall"] == "healthy"
        assert "search" in status["services"]

    def test_format_failures_message(self):
        """Test formatting failures message"""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.UNAVAILABLE, error="Connection failed")

        message = registry.format_failures_message()
        assert "Critical services failed" in message
        assert "search" in message
        assert "Connection failed" in message

    def test_format_failures_message_empty(self):
        """Test formatting failures message when no failures"""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.HEALTHY)

        message = registry.format_failures_message()
        assert message == ""

    def test_service_registry_singleton(self):
        """Test that service_registry is a singleton"""
        assert service_registry is not None
        assert isinstance(service_registry, ServiceRegistry)

