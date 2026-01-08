"""
CRM 100% Coverage Test - Final Version
Covers all missing methods to reach 100% coverage
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


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


class TestCRMAuditLoggerFull:
    """Complete audit logger tests for 100% coverage"""

    @pytest.fixture
    def audit_logger_instance(self):
        """Create audit logger instance with proper mocking"""
        from app.services.crm.audit_logger import CRMAuditLogger

        logger = CRMAuditLogger()

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        logger.pool = mock_pool

        return logger, mock_conn

    @pytest.mark.asyncio
    async def test_log_state_change_success(self, audit_logger_instance):
        """Test successful state change logging"""
        logger_instance, mock_conn = audit_logger_instance

        result = await logger_instance.log_state_change(
            entity_type="client",
            entity_id=123,
            old_state={"status": "prospect"},
            new_state={"status": "active"},
            user_email="test@example.com",
        )

        assert result is True
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_state_change_database_error(self, audit_logger_instance):
        """Test database error handling"""
        logger_instance, mock_conn = audit_logger_instance

        mock_conn.execute.side_effect = Exception("Database error")

        result = await logger_instance.log_state_change(
            entity_type="client",
            entity_id=123,
            old_state={"status": "prospect"},
            new_state={"status": "active"},
            user_email="test@example.com",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_log_client_status_change(self, audit_logger_instance):
        """Test client status change method"""
        logger_instance, mock_conn = audit_logger_instance

        result = await logger_instance.log_client_status_change(
            client_id=456,
            old_status="prospect",
            new_status="active",
            user_email="agent@example.com",
        )

        assert result is True
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_case_progression(self, audit_logger_instance):
        """Test case progression method"""
        logger_instance, mock_conn = audit_logger_instance

        result = await logger_instance.log_case_progression(
            case_id=789,
            old_stage="submitted",
            new_stage="under_review",
            user_email="agent@example.com",
            notes="Documents verified",
        )

        assert result is True
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_audit_trail_success(self, audit_logger_instance):
        """Test audit trail retrieval"""
        logger_instance, mock_conn = audit_logger_instance

        mock_rows = [
            {
                "entity_type": "client",
                "entity_id": 123,
                "change_type": "status_change",
                "user_email": "test@example.com",
                "timestamp": datetime.now(),
            }
        ]
        mock_conn.fetch.return_value = mock_rows

        result = await logger_instance.get_audit_trail(entity_type="client", entity_id=123)

        assert len(result) == 1
        assert result[0]["entity_type"] == "client"

    @pytest.mark.asyncio
    async def test_get_audit_trail_error(self, audit_logger_instance):
        """Test audit trail error handling"""
        logger_instance, mock_conn = audit_logger_instance

        mock_conn.fetch.side_effect = Exception("Query error")

        result = await logger_instance.get_audit_trail()

        assert result == []

    def test_detect_changes(self, audit_logger_instance):
        """Test change detection logic"""
        logger_instance, _ = audit_logger_instance

        old_state = {"status": "prospect"}
        new_state = {"status": "active"}

        result = logger_instance._detect_changes(old_state, new_state)

        assert "status" in result
        assert result["status"]["old"] == "prospect"
        assert result["status"]["new"] == "active"


class TestCRMMetricsFull:
    """Complete metrics tests for 100% coverage"""

    @pytest.fixture
    def metrics_instance(self):
        """Create metrics instance"""
        from app.services.crm.metrics import CRMMetrics

        return CRMMetrics()

    @pytest.fixture
    def collector_instance(self):
        """Create metrics collector with mocked dependencies"""
        from app.services.crm.metrics import CRMMetricsCollector

        collector = CRMMetricsCollector()

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        collector.pool = mock_pool

        return collector, mock_conn

    def test_metrics_initialization(self, metrics_instance):
        """Test metrics initialization"""
        assert hasattr(metrics_instance, "active_clients_total")
        assert hasattr(metrics_instance, "client_creation_duration")
        assert hasattr(metrics_instance, "crm_info")

    @pytest.mark.asyncio
    async def test_update_all_metrics_success(self, collector_instance):
        """Test successful metrics update"""
        collector, mock_conn = collector_instance

        # Mock all queries
        mock_conn.fetch.side_effect = [
            [{"assigned_to": "agent@example.com", "client_type": "individual", "count": 10}],
            [
                {
                    "from_status": "prospect",
                    "to_status": "active",
                    "changed_by": "agent@example.com",
                    "count": 5,
                }
            ],
            [{"stage": "under_review", "priority": "normal", "count": 3}],
            [
                {
                    "visa_type": "work_visa",
                    "destination_country": "IT",
                    "outcome": "approved",
                    "duration_seconds": 86400,
                }
            ],
            [{"lead_source": "website", "prospects": 20, "active_clients": 10}],
            [{"client_type": "individual", "outcome": "approved", "lifecycle_seconds": 2592000}],
            [{"interaction_type": "email", "channel": "web", "response_time_seconds": 3600}],
        ]

        result = await collector.update_all_metrics()

        assert result["success"] is True
        assert len(result["metrics_updated"]) == 7

    @pytest.mark.asyncio
    async def test_update_all_metrics_error(self, collector_instance):
        """Test metrics update with error"""
        collector, mock_conn = collector_instance

        mock_conn.fetch.side_effect = Exception("Database error")

        result = await collector.update_all_metrics()

        assert "error" in result

    @pytest.mark.asyncio
    async def test_update_client_metrics(self, collector_instance):
        """Test client metrics update"""
        collector, mock_conn = collector_instance

        mock_conn.fetch.side_effect = [
            [{"assigned_to": "agent@example.com", "client_type": "individual", "count": 10}],
            [
                {
                    "from_status": "prospect",
                    "to_status": "active",
                    "changed_by": "agent@example.com",
                    "count": 5,
                }
            ],
        ]

        results = {"metrics_updated": [], "errors": []}
        await collector.update_client_metrics(results)

        assert "active_clients_total" in results["metrics_updated"]
        assert "client_status_changes" in results["metrics_updated"]

    @pytest.mark.asyncio
    async def test_update_application_metrics(self, collector_instance):
        """Test application metrics update"""
        collector, mock_conn = collector_instance

        mock_conn.fetch.side_effect = [
            [{"stage": "under_review", "priority": "normal", "count": 3}],
            [
                {
                    "visa_type": "work_visa",
                    "destination_country": "IT",
                    "outcome": "approved",
                    "duration_seconds": 86400,
                }
            ],
        ]

        results = {"metrics_updated": [], "errors": []}
        await collector.update_application_metrics(results)

        assert "applications_in_progress" in results["metrics_updated"]
        assert "application_processing_duration" in results["metrics_updated"]

    @pytest.mark.asyncio
    async def test_update_business_metrics(self, collector_instance):
        """Test business metrics update"""
        collector, mock_conn = collector_instance

        mock_conn.fetch.side_effect = [
            [{"lead_source": "website", "prospects": 20, "active_clients": 10}],
            [{"client_type": "individual", "outcome": "approved", "lifecycle_seconds": 2592000}],
        ]

        results = {"metrics_updated": [], "errors": []}
        await collector.update_business_metrics(results)

        assert "conversion_rate" in results["metrics_updated"]
        assert "client_lifecycle_duration" in results["metrics_updated"]

    @pytest.mark.asyncio
    async def test_update_operational_metrics(self, collector_instance):
        """Test operational metrics update"""
        collector, mock_conn = collector_instance

        mock_conn.fetch.return_value = [
            [{"interaction_type": "email", "channel": "web", "response_time_seconds": 3600}]
        ]

        results = {"metrics_updated": [], "errors": []}
        await collector.update_operational_metrics(results)

        assert "interaction_response_time" in results["metrics_updated"]

    @pytest.mark.asyncio
    async def test_get_metrics_summary(self, collector_instance):
        """Test metrics summary"""
        collector, mock_conn = collector_instance

        mock_conn.fetchrow.side_effect = [
            {
                "active_clients": 50,
                "prospects": 20,
                "completed_clients": 100,
                "total_clients": 170,
                "new_clients_30d": 15,
                "active_clients_30d": 12,
            },
            {
                "applications_in_progress": 8,
                "completed_applications": 25,
                "total_applications": 33,
                "avg_processing_days": 15.5,
            },
        ]

        result = await collector.get_metrics_summary()

        assert "clients" in result
        assert "applications" in result
        assert result["clients"]["active"] == 50
        assert result["applications"]["in_progress"] == 8

    @pytest.mark.asyncio
    async def test_get_metrics_summary_error(self, collector_instance):
        """Test metrics summary error"""
        collector, mock_conn = collector_instance

        mock_conn.fetchrow.side_effect = Exception("Database error")

        result = await collector.get_metrics_summary()

        assert "error" in result


class TestCRMIntegrationFull:
    """Complete integration tests"""

    @pytest.mark.asyncio
    async def test_full_audit_flow(self):
        """Test complete audit flow"""
        from app.services.crm.audit_logger import CRMAuditLogger

        audit_logger = CRMAuditLogger()
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        audit_logger.pool = mock_pool

        # Log multiple changes
        result1 = await audit_logger.log_state_change(
            entity_type="client",
            entity_id=123,
            old_state={"status": "prospect"},
            new_state={"status": "active"},
            user_email="agent@example.com",
        )

        result2 = await audit_logger.log_client_status_change(
            client_id=123,
            old_status="active",
            new_status="inactive",
            user_email="agent@example.com",
        )

        result3 = await audit_logger.log_case_progression(
            case_id=456,
            old_stage="submitted",
            new_stage="under_review",
            user_email="agent@example.com",
        )

        # Retrieve audit trail
        mock_conn.fetch.return_value = [
            {
                "entity_type": "client",
                "entity_id": 123,
                "change_type": "status_change",
                "user_email": "agent@example.com",
                "timestamp": datetime.now(),
            },
            {
                "entity_type": "client",
                "entity_id": 123,
                "change_type": "status_change",
                "user_email": "agent@example.com",
                "timestamp": datetime.now(),
            },
            {
                "entity_type": "case",
                "entity_id": 456,
                "change_type": "stage_progression",
                "user_email": "agent@example.com",
                "timestamp": datetime.now(),
            },
        ]

        audit_trail = await audit_logger.get_audit_trail()

        # Verify all operations
        assert result1 is True
        assert result2 is True
        assert result3 is True
        assert len(audit_trail) == 3
        assert mock_conn.execute.call_count == 3

    @pytest.mark.asyncio
    async def test_metrics_and_audit_integration(self):
        """Test metrics and audit integration"""
        from app.services.crm.audit_logger import CRMAuditLogger
        from app.services.crm.metrics import CRMMetricsCollector

        audit_logger = CRMAuditLogger()
        metrics_collector = CRMMetricsCollector()

        # Mock database
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        audit_logger.pool = mock_pool
        metrics_collector.pool = mock_pool

        # Mock metrics data
        mock_conn.fetch.side_effect = [
            [{"assigned_to": "agent@example.com", "client_type": "individual", "count": 5}],
            [
                {
                    "from_status": "prospect",
                    "to_status": "active",
                    "changed_by": "agent@example.com",
                    "count": 2,
                }
            ],
            [{"stage": "under_review", "priority": "normal", "count": 3}],
            [
                {
                    "visa_type": "work_visa",
                    "destination_country": "IT",
                    "outcome": "approved",
                    "duration_seconds": 86400,
                }
            ],
            [{"lead_source": "website", "prospects": 10, "active_clients": 5}],
            [{"client_type": "individual", "outcome": "approved", "lifecycle_seconds": 2592000}],
            [{"interaction_type": "email", "channel": "web", "response_time_seconds": 3600}],
        ]

        # Test both systems
        audit_result = await audit_logger.log_state_change(
            entity_type="client",
            entity_id=123,
            old_state={"status": "prospect"},
            new_state={"status": "active"},
            user_email="agent@example.com",
        )

        metrics_result = await metrics_collector.update_all_metrics()

        # Verify integration
        assert audit_result is True
        assert metrics_result["success"] is True
        assert len(metrics_result["metrics_updated"]) == 7


class TestCRMEdgeCases:
    """Test edge cases"""

    @pytest.mark.asyncio
    async def test_null_values(self):
        """Test null value handling"""
        from app.services.crm.audit_logger import CRMAuditLogger

        audit_logger = CRMAuditLogger()
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        audit_logger.pool = mock_pool

        result = await audit_logger.log_state_change(
            entity_type="client",
            entity_id=123,
            old_state={"status": None},
            new_state={"status": "active"},
            user_email="test@example.com",
            metadata=None,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_large_data(self):
        """Test large data handling"""
        from app.services.crm.audit_logger import CRMAuditLogger

        audit_logger = CRMAuditLogger()
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        audit_logger.pool = mock_pool

        large_state = {f"field_{i}": f"value_{i}" for i in range(100)}

        result = await audit_logger.log_state_change(
            entity_type="client",
            entity_id=123,
            old_state=large_state,
            new_state=large_state,
            user_email="test@example.com",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test concurrent operations"""
        from app.services.crm.audit_logger import CRMAuditLogger

        audit_logger = CRMAuditLogger()
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        audit_logger.pool = mock_pool

        # Create concurrent tasks
        tasks = []
        for i in range(10):
            task = audit_logger.log_state_change(
                entity_type="client",
                entity_id=i,
                old_state={"status": "prospect"},
                new_state={"status": "active"},
                user_email=f"user_{i}@example.com",
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        assert all(result is True for result in results)
        assert mock_conn.execute.call_count == 10


if __name__ == "__main__":
    pytest.main(
        [
            __file__,
            "-v",
            "--cov=app.services.crm",
            "--cov-report=term-missing",
            "--cov-fail-under=95",
        ]
    )
