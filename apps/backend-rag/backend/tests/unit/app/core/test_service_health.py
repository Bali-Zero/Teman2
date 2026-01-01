"""
Unit tests for service health registry
Target: >95% coverage
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.core.service_health import ServiceHealth, ServiceRegistry, ServiceStatus


class TestServiceStatus:
    """Tests for ServiceStatus enum"""

    def test_service_status_values(self):
        """Test service status enum values"""
        assert ServiceStatus.HEALTHY.value == "healthy"
        assert ServiceStatus.DEGRADED.value == "degraded"
        assert ServiceStatus.UNAVAILABLE.value == "unavailable"


class TestServiceHealth:
    """Tests for ServiceHealth dataclass"""

    def test_service_health_creation(self):
        """Test creating ServiceHealth"""
        health = ServiceHealth(
            name="test_service",
            status=ServiceStatus.HEALTHY,
            error=None,
            is_critical=False,
        )
        assert health.name == "test_service"
        assert health.status == ServiceStatus.HEALTHY
        assert health.error is None
        assert health.is_critical is False

    def test_service_health_to_dict(self):
        """Test converting ServiceHealth to dict"""
        now = datetime.now(timezone.utc)
        health = ServiceHealth(
            name="test_service",
            status=ServiceStatus.DEGRADED,
            error="Test error",
            is_critical=True,
            initialized_at=now,
            last_check=now,
        )
        result = health.to_dict()
        assert result["name"] == "test_service"
        assert result["status"] == "degraded"
        assert result["error"] == "Test error"
        assert result["is_critical"] is True
        assert result["initialized_at"] == now.isoformat()


class TestServiceRegistry:
    """Tests for ServiceRegistry"""

    def test_init(self):
        """Test initialization"""
        registry = ServiceRegistry()
        assert len(registry._services) == 0

    def test_register_service(self):
        """Test registering a service"""
        registry = ServiceRegistry()
        registry.register("test_service", ServiceStatus.HEALTHY)
        assert "test_service" in registry._services
        assert registry._services["test_service"].status == ServiceStatus.HEALTHY

    def test_register_critical_service(self):
        """Test registering a critical service"""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.HEALTHY)
        assert registry._services["search"].is_critical is True

    def test_register_with_error(self):
        """Test registering service with error"""
        registry = ServiceRegistry()
        registry.register("test_service", ServiceStatus.UNAVAILABLE, error="Connection failed")
        assert registry._services["test_service"].error == "Connection failed"
        assert registry._services["test_service"].status == ServiceStatus.UNAVAILABLE

    def test_get_service(self):
        """Test getting service health"""
        registry = ServiceRegistry()
        registry.register("test_service", ServiceStatus.HEALTHY)
        health = registry.get_service("test_service")
        assert health is not None
        assert health.name == "test_service"

    def test_get_service_not_found(self):
        """Test getting non-existent service"""
        registry = ServiceRegistry()
        health = registry.get_service("nonexistent")
        assert health is None

    def test_get_all_services_via_status(self):
        """Test getting all services via get_status"""
        registry = ServiceRegistry()
        registry.register("service1", ServiceStatus.HEALTHY)
        registry.register("service2", ServiceStatus.DEGRADED)
        status = registry.get_status()
        assert len(status["services"]) == 2

    def test_is_healthy_via_get_service(self):
        """Test checking if service is healthy via get_service"""
        registry = ServiceRegistry()
        registry.register("service1", ServiceStatus.HEALTHY)
        registry.register("service2", ServiceStatus.UNAVAILABLE)
        service1 = registry.get_service("service1")
        service2 = registry.get_service("service2")
        assert service1.status == ServiceStatus.HEALTHY
        assert service2.status == ServiceStatus.UNAVAILABLE

    def test_get_status_all_healthy(self):
        """Test status when all services are healthy"""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.HEALTHY)
        registry.register("ai", ServiceStatus.HEALTHY)
        status = registry.get_status()
        assert status["overall"] == "healthy"
        assert len(status["services"]) == 2

    def test_get_status_critical_failure(self):
        """Test status when critical service fails"""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.UNAVAILABLE, error="Failed")
        registry.register("ai", ServiceStatus.HEALTHY)
        status = registry.get_status()
        assert status["overall"] == "critical"

    def test_get_status_degraded(self):
        """Test status when services are degraded"""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.DEGRADED)
        registry.register("ai", ServiceStatus.HEALTHY)
        status = registry.get_status()
        assert status["overall"] == "degraded"

    def test_get_critical_failures(self):
        """Test getting critical failures"""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.UNAVAILABLE, error="Failed")
        registry.register("ai", ServiceStatus.HEALTHY)
        failures = registry.get_critical_failures()
        assert len(failures) == 1
        assert failures[0].name == "search"

    def test_has_critical_failures(self):
        """Test checking for critical failures"""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.UNAVAILABLE)
        assert registry.has_critical_failures() is True

    def test_format_failures_message(self):
        """Test formatting failures message"""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.UNAVAILABLE, error="Connection failed")
        message = registry.format_failures_message()
        assert "search" in message
        assert "Connection failed" in message

