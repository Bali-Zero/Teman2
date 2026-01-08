"""
CRM Test Suite - Final Working Version
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest


# Mock the configuration to avoid Pydantic issues
@pytest.fixture(autouse=True)
def mock_config():
    """Mock all configuration dependencies"""
    with (
        patch("app.dependencies.get_database_pool"),
        patch("app.utils.logging_utils.get_logger"),
        patch("prometheus_client.Counter"),
        patch("prometheus_client.Histogram"),
        patch("prometheus_client.Gauge"),
        patch("prometheus_client.Info"),
    ):
        yield


@pytest.fixture
def mock_logger():
    """Mock logger for tests"""
    return Mock()


class TestCRMAuditLogger:
    """Test for CRM Audit Logger"""

    @pytest.fixture
    def audit_logger_instance(self):
        """Create audit logger instance with mocked dependencies"""
        from app.services.crm.audit_logger import CRMAuditLogger

        logger = CRMAuditLogger()
        logger.pool = AsyncMock()
        return logger

    @pytest.mark.asyncio
    async def test_log_state_change_success(self, audit_logger_instance):
        """Test successful state change logging"""
        # Setup
        mock_conn = AsyncMock()
        audit_logger_instance.pool.acquire.return_value.__aenter__.return_value = mock_conn

        old_state = {"status": "prospect"}
        new_state = {"status": "active"}

        # Execute
        result = await audit_logger_instance.log_state_change(
            entity_type="client",
            entity_id=123,
            old_state=old_state,
            new_state=new_state,
            user_email="test@example.com",
        )

        # Assert
        assert result is True
        mock_conn.execute.assert_called_once()

    def test_detect_changes(self, audit_logger_instance):
        """Test change detection logic"""
        old_state = {"status": "prospect", "name": "Old Name"}
        new_state = {"status": "active", "name": "New Name"}

        result = audit_logger_instance._detect_changes(old_state, new_state)

        assert "status" in result
        assert "name" in result
        assert result["status"]["old"] == "prospect"
        assert result["status"]["new"] == "active"


class TestCRMMetrics:
    """Test for CRM Metrics"""

    def test_metrics_initialization(self):
        """Test metrics initialization"""
        from app.services.crm.metrics import CRMMetrics

        metrics = CRMMetrics()

        assert hasattr(metrics, "active_clients_total")
        assert hasattr(metrics, "client_creation_duration")
        assert hasattr(metrics, "application_processing_duration")


class TestCRMIntegration:
    """Integration tests"""

    @pytest.mark.asyncio
    async def test_basic_integration(self):
        """Test basic integration"""
        from app.services.crm.audit_logger import CRMAuditLogger

        # Create instance
        audit_logger = CRMAuditLogger()
        audit_logger.pool = AsyncMock()

        # Setup mock connection
        mock_conn = AsyncMock()
        audit_logger.pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Test audit logging
        result = await audit_logger.log_state_change(
            entity_type="client",
            entity_id=123,
            old_state={"status": "prospect"},
            new_state={"status": "active"},
            user_email="test@example.com",
        )

        # Assert
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
