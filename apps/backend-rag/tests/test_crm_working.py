"""
CRM Test Suite - Working Version with Proper Mocking
"""

from unittest.mock import AsyncMock, MagicMock, patch

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


class TestCRMAuditLogger:
    """Test for CRM Audit Logger"""

    @pytest.fixture
    def audit_logger_instance(self):
        """Create audit logger instance with mocked dependencies"""
        from app.services.crm.audit_logger import CRMAuditLogger

        logger = CRMAuditLogger()

        # Create proper mock for pool
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        logger.pool = mock_pool

        return logger, mock_conn

    @pytest.mark.asyncio
    async def test_log_state_change_success(self, audit_logger_instance):
        """Test successful state change logging"""
        logger_instance, mock_conn = audit_logger_instance

        old_state = {"status": "prospect"}
        new_state = {"status": "active"}

        # Execute
        result = await logger_instance.log_state_change(
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
        logger_instance, _ = audit_logger_instance

        old_state = {"status": "prospect", "name": "Old Name"}
        new_state = {"status": "active", "name": "New Name"}

        result = logger_instance._detect_changes(old_state, new_state)

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

        # Create instance with proper mocking
        audit_logger = CRMAuditLogger()
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        audit_logger.pool = mock_pool

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
