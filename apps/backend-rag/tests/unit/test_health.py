"""
Unit tests for health check endpoints.

Note: The detailed health endpoint (/health/detailed) requires integration testing
with the full application context due to complex import dependencies.
"""

from datetime import datetime, timezone

from app.core.service_health import ServiceRegistry, ServiceStatus


class TestHealthEndpointLogic:
    """Tests for health check logic (without HTTP testing)."""

    def test_service_registry_integration_healthy(self):
        """Test that service registry correctly reports healthy status."""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.HEALTHY)
        registry.register("ai", ServiceStatus.HEALTHY)

        status = registry.get_status()
        assert status["overall"] == "healthy"

    def test_service_registry_integration_critical(self):
        """Test that service registry correctly reports critical status."""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.UNAVAILABLE, error="Qdrant down")
        registry.register("ai", ServiceStatus.HEALTHY)

        status = registry.get_status()
        assert status["overall"] == "critical"

    def test_service_registry_integration_degraded(self):
        """Test that service registry correctly reports degraded status."""
        registry = ServiceRegistry()
        registry.register("search", ServiceStatus.HEALTHY)
        registry.register("ai", ServiceStatus.HEALTHY)
        registry.register("database", ServiceStatus.UNAVAILABLE, error="DB down")

        status = registry.get_status()
        assert status["overall"] == "degraded"


class TestHealthResponseStructure:
    """Tests for health response data structures."""

    def test_service_health_to_dict_structure(self):
        """Test ServiceHealth.to_dict returns expected structure."""
        from app.core.service_health import ServiceHealth

        service = ServiceHealth(
            name="test",
            status=ServiceStatus.HEALTHY,
            is_critical=True,
            initialized_at=datetime.now(timezone.utc),
        )
        result = service.to_dict()

        assert "name" in result
        assert "status" in result
        assert "is_critical" in result
        assert "error" in result
        assert "initialized_at" in result
        assert "last_check" in result

    def test_service_registry_get_status_structure(self):
        """Test ServiceRegistry.get_status returns expected structure."""
        registry = ServiceRegistry()
        registry.register("test", ServiceStatus.HEALTHY)

        status = registry.get_status()

        assert "overall" in status
        assert "services" in status
        assert "critical_services" in status
        assert "timestamp" in status

    def test_critical_services_list(self):
        """Test that critical services are correctly defined."""
        registry = ServiceRegistry()

        # Verify default critical services
        assert "search" in registry.CRITICAL_SERVICES
        assert "ai" in registry.CRITICAL_SERVICES


class TestHealthTimestamp:
    """Tests for timestamp handling in health responses."""

    def test_timestamp_format(self):
        """Test that timestamps are in ISO format."""
        registry = ServiceRegistry()
        registry.register("test", ServiceStatus.HEALTHY)

        status = registry.get_status()
        timestamp = status["timestamp"]

        # Should be parseable as ISO format
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        assert isinstance(parsed, datetime)

    def test_service_initialization_timestamp(self):
        """Test that service records initialization timestamp."""
        from app.core.service_health import ServiceHealth

        before = datetime.now(timezone.utc)
        service = ServiceHealth(
            name="test",
            status=ServiceStatus.HEALTHY,
            initialized_at=datetime.now(timezone.utc),
        )
        after = datetime.now(timezone.utc)

        assert service.initialized_at is not None
        assert before <= service.initialized_at <= after
