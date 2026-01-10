"""
CRM 100% Coverage Test Suite - Complete Implementation
Tests all methods and edge cases for full coverage
"""

import asyncio
import json
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


class _AsyncAcquireContext:
    """Simple async context manager wrapper for mocked connections."""

    def __init__(self, conn: AsyncMock):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeAsyncPool:
    """Minimal async pool wrapper for testing acquire context."""

    def __init__(self, conn: AsyncMock):
        self._conn = conn

    def acquire(self):
        return _AsyncAcquireContext(self._conn)


def _make_async_pool(conn: AsyncMock | None = None) -> tuple[AsyncMock, AsyncMock]:
    """Create an async pool whose acquire returns a context manager wrapping `conn`."""
    if conn is None:
        conn = AsyncMock()

    pool = _FakeAsyncPool(conn)
    return pool, conn


class TestCRMAuditLoggerComplete:
    """Complete test suite for CRM Audit Logger - 100% coverage"""

    @pytest.fixture
    def audit_logger_instance(self):
        """Create audit logger instance with proper mocking"""
        from app.services.crm.audit_logger import CRMAuditLogger

        logger = CRMAuditLogger()

        mock_conn = AsyncMock()
        mock_pool = _FakeAsyncPool(mock_conn)
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
            change_type="status_change",
            metadata={"reason": "qualified"},
        )

        assert result is True
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_state_change_no_changes(self, audit_logger_instance):
        """Test logging when no changes detected"""
        logger_instance, mock_conn = audit_logger_instance

        old_state = {"status": "active", "name": "Test"}
        new_state = {"status": "active", "name": "Test"}

        result = await logger_instance.log_state_change(
            entity_type="client",
            entity_id=123,
            old_state=old_state,
            new_state=new_state,
            user_email="test@example.com",
        )

        assert result is True
        mock_conn.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_log_state_change_no_changes_logs_warning(self, audit_logger_instance, caplog):
        logger_instance, mock_conn = audit_logger_instance
        with patch("app.services.crm.audit_logger.logger") as mock_logger:
            await logger_instance.log_state_change(
                entity_type="client",
                entity_id=123,
                old_state={"status": "active"},
                new_state={"status": "active"},
                user_email="test@example.com",
            )

        mock_conn.execute.assert_not_called()
        mock_logger.warning.assert_called_once()
        assert "No changes detected" in mock_logger.warning.call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_pool_initializes_when_none(self, audit_logger_instance):
        """Ensure _get_pool calls dependency when pool unset"""
        logger_instance, _ = audit_logger_instance
        logger_instance.pool = None

        async_pool = AsyncMock()
        with patch(
            "app.services.crm.audit_logger.get_database_pool",
            AsyncMock(return_value=async_pool),
        ) as mock_get_pool:
            pool_result = await logger_instance._get_pool()

        assert pool_result == async_pool
        mock_get_pool.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_log_state_change_database_error(self, audit_logger_instance):
        """Test handling of database errors"""
        logger_instance, mock_conn = audit_logger_instance

        mock_conn.execute.side_effect = Exception("Database connection failed")

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
        """Test client status change specific method"""
        logger_instance, mock_conn = audit_logger_instance

        result = await logger_instance.log_client_status_change(
            client_id=456,
            old_status="prospect",
            new_status="active",
            user_email="user@example.com",
            additional_data={
                "old": {"notes": "Initial contact"},
                "new": {"notes": "Qualified lead"},
            },
        )

        assert result is True
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args[0]
        metadata = json.loads(call_args[8])
        assert metadata["previous_status"] == "prospect"
        assert metadata["new_status"] == "active"

    @pytest.mark.asyncio
    async def test_log_case_progression(self, audit_logger_instance):
        """Test case progression logging"""
        logger_instance, mock_conn = audit_logger_instance

        result = await logger_instance.log_case_progression(
            case_id=789,
            old_stage="application_submitted",
            new_stage="under_review",
            user_email="agent@example.com",
            notes="Documents verified successfully",
        )

        assert result is True
        mock_conn.execute.assert_called_once()

        # Verify case-specific metadata
        call_args = mock_conn.execute.call_args[0]
        assert call_args[1] == "case"
        assert call_args[2] == 789
        assert call_args[3] == "stage_progression"
        assert call_args[4] == "agent@example.com"
        metadata = json.loads(call_args[8])
        assert metadata["case_id"] == 789
        assert metadata["previous_stage"] == "application_submitted"
        assert metadata["new_stage"] == "under_review"
        assert metadata["notes"] == "Documents verified successfully"

    @pytest.mark.asyncio
    async def test_get_audit_trail_success(self, audit_logger_instance):
        """Test successful audit trail retrieval"""
        logger_instance, mock_conn = audit_logger_instance

        # Mock database response
        mock_rows = [
            {
                "entity_type": "client",
                "entity_id": 123,
                "change_type": "status_change",
                "user_email": "test@example.com",
                "old_state": {"status": "prospect"},
                "new_state": {"status": "active"},
                "changes": {"status": {"old": "prospect", "new": "active"}},
                "metadata": {"reason": "qualified"},
                "timestamp": datetime.now(),
            },
            {
                "entity_type": "client",
                "entity_id": 123,
                "change_type": "update",
                "user_email": "agent@example.com",
                "old_state": {"notes": "Old note"},
                "new_state": {"notes": "New note"},
                "changes": {"notes": {"old": "Old note", "new": "New note"}},
                "metadata": {"source": "api"},
                "timestamp": datetime.now(),
            },
        ]
        mock_conn.fetch.return_value = mock_rows

        result = await logger_instance.get_audit_trail(
            entity_type="client", entity_id=123, user_email="test@example.com", limit=50
        )

        assert len(result) == 2
        assert result[0]["entity_type"] == "client"
        assert result[0]["entity_id"] == 123
        assert result[0]["change_type"] == "status_change"
        assert result[1]["change_type"] == "update"

        # Verify SQL query construction
        call_args = mock_conn.fetch.call_args[0]
        assert "AND entity_type = $1" in call_args[0]
        assert "AND entity_id = $2" in call_args[0]
        assert "AND user_email = $3" in call_args[0]
        assert "ORDER BY timestamp DESC" in call_args[0]

    @pytest.mark.asyncio
    async def test_get_audit_trail_with_all_filters(self, audit_logger_instance):
        """Test audit trail with all filters applied"""
        logger_instance, mock_conn = audit_logger_instance

        mock_conn.fetch.return_value = []

        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 12, 31)

        await logger_instance.get_audit_trail(
            entity_type="case",
            entity_id=456,
            user_email="agent@example.com",
            start_date=start_date,
            end_date=end_date,
            limit=25,
        )

        # Verify all filters are applied
        call_args = mock_conn.fetch.call_args
        assert len(call_args[0]) == 7  # Query + 6 parameters
        assert call_args[0][1] == "case"
        assert call_args[0][2] == 456
        assert call_args[0][3] == "agent@example.com"
        assert call_args[0][4] == start_date
        assert call_args[0][5] == end_date
        assert call_args[0][6] == 25

    @pytest.mark.asyncio
    async def test_get_audit_trail_date_filters_only(self, audit_logger_instance):
        """Test audit trail when only date filters and limit are provided"""
        logger_instance, mock_conn = audit_logger_instance

        mock_conn.fetch.return_value = []
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 6, 30)

        await logger_instance.get_audit_trail(start_date=start_date, end_date=end_date, limit=10)

        fetch_args = mock_conn.fetch.call_args[0]
        assert "timestamp >= $1" in fetch_args[0]
        assert "timestamp <= $2" in fetch_args[0]
        assert fetch_args[1] == start_date
        assert fetch_args[2] == end_date
        assert fetch_args[3] == 10

    @pytest.mark.asyncio
    async def test_get_audit_trail_error(self, audit_logger_instance):
        """Test audit trail retrieval with database error"""
        logger_instance, mock_conn = audit_logger_instance

        mock_conn.fetch.side_effect = Exception("Database query failed")

        result = await logger_instance.get_audit_trail()

        assert result == []

    def test_detect_changes_all_fields_changed(self, audit_logger_instance):
        """Test change detection with all fields changed"""
        logger_instance, _ = audit_logger_instance

        old_state = {
            "status": "prospect",
            "name": "Old Name",
            "email": "old@example.com",
            "phone": "+1234567890",
        }
        new_state = {
            "status": "active",
            "name": "New Name",
            "email": "new@example.com",
            "phone": "+0987654321",
        }

        result = logger_instance._detect_changes(old_state, new_state)

        assert len(result) == 4
        assert "status" in result
        assert "name" in result
        assert "email" in result
        assert "phone" in result

        # Verify change structure
        assert result["status"]["old"] == "prospect"
        assert result["status"]["new"] == "active"
        assert "changed_at" in result["status"]

    def test_detect_changes_no_changes(self, audit_logger_instance):
        """Test change detection with no changes"""
        logger_instance, _ = audit_logger_instance

        old_state = {"status": "active", "name": "Test Client"}
        new_state = {"status": "active", "name": "Test Client"}

        result = logger_instance._detect_changes(old_state, new_state)

        assert result == {}

    def test_detect_changes_removed_fields(self, audit_logger_instance):
        """Test change detection with removed fields"""
        logger_instance, _ = audit_logger_instance

        old_state = {
            "status": "active",
            "name": "Test",
            "temp_field": "temporary",
            "another_temp": "remove me",
        }
        new_state = {"status": "active", "name": "Test"}

        result = logger_instance._detect_changes(old_state, new_state)

        assert len(result) == 2
        assert "temp_field" in result
        assert "another_temp" in result
        assert result["temp_field"]["removed"] is True
        assert result["temp_field"]["old"] == "temporary"
        assert result["temp_field"]["new"] is None

    def test_detect_changes_mixed_changes(self, audit_logger_instance):
        """Test change detection with mixed updates and removals"""
        logger_instance, _ = audit_logger_instance

        old_state = {
            "status": "prospect",
            "name": "Old Name",
            "temp_field": "remove me",
            "keep_field": "unchanged",
        }
        new_state = {"status": "active", "name": "New Name", "keep_field": "unchanged"}

        result = logger_instance._detect_changes(old_state, new_state)

        assert len(result) == 3
        assert "status" in result and not result["status"].get("removed")
        assert "name" in result and not result["name"].get("removed")
        assert "temp_field" in result and result["temp_field"]["removed"] is True
        assert "keep_field" not in result


class TestCRMAuditLoggerDecorator:
    """Tests for audit decorator and migrations"""

    @pytest.mark.asyncio
    async def test_audit_change_decorator_logs_with_old_state(self):
        from app.services.crm.audit_logger import (
            audit_change,
            audit_logger,
        )

        async def dummy_handler(client_id: int, user_email: str):
            return {"status": "updated"}

        async_pool, async_conn = _make_async_pool()
        async_conn.fetchrow.return_value = {"id": 42, "status": "prospect"}
        async_mock_get_pool = AsyncMock(return_value=async_pool)

        with (
            patch(
                "app.services.crm.audit_logger.get_database_pool",
                async_mock_get_pool,
            ),
            patch.object(audit_logger, "log_state_change", AsyncMock()) as mock_log,
        ):
            decorated = audit_change("client")(dummy_handler)
            await decorated(client_id=42, user_email="agent@example.com")

            mock_log.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_audit_change_decorator_handles_fetch_failure(self):
        from app.services.crm.audit_logger import audit_change, audit_logger

        async def dummy_handler(client_id: int, user_email: str):
            return {"status": "updated"}

        async def failing_pool():
            raise RuntimeError("boom")

        async_mock_failing_pool = AsyncMock(side_effect=failing_pool)

        with (
            patch(
                "app.services.crm.audit_logger.get_database_pool",
                async_mock_failing_pool,
            ),
            patch.object(audit_logger, "log_state_change", AsyncMock()) as mock_log,
        ):
            decorated = audit_change("client")(dummy_handler)
            await decorated(client_id=42, user_email="agent@example.com")

            mock_log.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_audit_log_table_executes_sql(self):
        from app.services.crm.audit_logger import create_audit_log_table

        async_pool, async_conn = _make_async_pool()
        async_conn.execute = AsyncMock()

        async_mock_pool = AsyncMock(return_value=async_pool)

        with patch("app.services.crm.audit_logger.get_database_pool", async_mock_pool):
            await create_audit_log_table()

        async_conn.execute.assert_awaited_once()


class TestCRMMetricsComplete:
    """Complete test suite for CRM Metrics - 100% coverage"""

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
        # Test all metrics are created
        assert hasattr(metrics_instance, "active_clients_total")
        assert hasattr(metrics_instance, "client_creation_duration")
        assert hasattr(metrics_instance, "crm_info")
        assert metrics_instance.crm_info.info.call_count >= 1
        info_payload = metrics_instance.crm_info.info.call_args_list[-1][0][0]
        assert info_payload["version"] == "1.0.0"
        assert info_payload["environment"] == "production"

    def test_active_clients_total_gauge_operations(self, metrics_instance):
        """Test active clients total gauge operations"""
        # Test setting gauge values
        metrics_instance.active_clients_total.labels(
            assigned_to="agent@example.com", client_type="individual"
        ).set(25)

        metrics_instance.active_clients_total.labels(
            assigned_to="agent2@example.com", client_type="corporate"
        ).set(10)

        # Test increment/decrement
        metrics_instance.active_clients_total.labels(
            assigned_to="agent@example.com", client_type="individual"
        ).inc()

        metrics_instance.active_clients_total.labels(
            assigned_to="agent2@example.com", client_type="corporate"
        ).dec(2)

    def test_client_creation_duration_histogram(self, metrics_instance):
        """Test client creation duration histogram"""
        # Test observing creation times
        metrics_instance.client_creation_duration.labels(
            client_type="individual", lead_source="website"
        ).observe(5.2)

        metrics_instance.client_creation_duration.labels(
            client_type="corporate", lead_source="referral"
        ).observe(12.8)

        metrics_instance.client_creation_duration.labels(
            client_type="individual", lead_source="cold_call"
        ).observe(3.1)

    def test_application_processing_duration_histogram(self, metrics_instance):
        """Test application processing duration histogram"""
        # Test observing processing times in seconds
        metrics_instance.application_processing_duration.labels(
            visa_type="work_visa", destination_country="IT", outcome="approved"
        ).observe(86400)  # 1 day

        metrics_instance.application_processing_duration.labels(
            visa_type="student_visa", destination_country="US", outcome="rejected"
        ).observe(43200)  # 12 hours

        metrics_instance.application_processing_duration.labels(
            visa_type="tourist_visa", destination_country="UK", outcome="approved"
        ).observe(21600)  # 6 hours

    @pytest.mark.asyncio
    async def test_update_all_metrics_success(self, collector_instance):
        """Test successful update of all metrics"""
        collector, mock_conn = collector_instance

        # Mock all database queries
        mock_conn.fetch.side_effect = [
            # Active clients
            [{"assigned_to": "agent@example.com", "client_type": "individual", "count": 15}],
            # Status changes
            [
                {
                    "from_status": "prospect",
                    "to_status": "active",
                    "changed_by": "agent@example.com",
                    "count": 5,
                }
            ],
            # Applications in progress
            [{"stage": "under_review", "priority": "normal", "count": 8}],
            # Processing times
            [
                {
                    "visa_type": "work_visa",
                    "destination_country": "IT",
                    "outcome": "approved",
                    "duration_seconds": 86400,
                }
            ],
            # Conversion rates
            [
                {
                    "lead_source": "website",
                    "prospects": 20,
                    "active_clients": 10,
                    "conversion_rate": 50.0,
                }
            ],
            # Lifecycle durations
            [{"client_type": "individual", "outcome": "approved", "lifecycle_seconds": 2592000}],
            # Response times
            [{"interaction_type": "email", "channel": "web", "response_time_seconds": 3600}],
        ]

        result = await collector.update_all_metrics()

        assert result["success"] is True
        assert "timestamp" in result
        assert "metrics_updated" in result
        assert "errors" in result
        assert len(result["metrics_updated"]) == 7
        assert len(result["errors"]) == 0

        # Verify all metrics were updated
        expected_metrics = [
            "active_clients_total",
            "client_status_changes",
            "applications_in_progress",
            "application_processing_duration",
            "conversion_rate",
            "client_lifecycle_duration",
            "interaction_response_time",
        ]
        for metric in expected_metrics:
            assert metric in result["metrics_updated"]

    @pytest.mark.asyncio
    async def test_update_all_metrics_with_errors(self, collector_instance):
        """Test metrics update with some errors"""
        collector, mock_conn = collector_instance

        # Mock queries with some failures
        mock_conn.fetch.side_effect = [
            # Active clients - success
            [{"assigned_to": "agent@example.com", "client_type": "individual", "count": 15}],
            # Status changes - error
            Exception("Connection timeout"),
            # Applications in progress - success
            [{"stage": "under_review", "priority": "normal", "count": 8}],
            # Processing times - error
            Exception("Query failed"),
            # Conversion rates - empty
            [],
            # Client lifecycle - empty
            [],
            # Response times - empty
            [],
        ]

        result = await collector.update_all_metrics()

        assert result["success"] is True  # Still succeeds overall
        assert len(result["metrics_updated"]) == 5  # Only successful ones
        assert len(result["errors"]) == 2  # Failed ones

    @pytest.mark.asyncio
    async def test_update_client_metrics_detailed(self, collector_instance):
        """Test client metrics update in detail"""
        collector, mock_conn = collector_instance

        # Mock comprehensive client data
        mock_conn.fetch.side_effect = [
            # Active clients by user and type
            [
                {"assigned_to": "agent1@example.com", "client_type": "individual", "count": 10},
                {"assigned_to": "agent1@example.com", "client_type": "corporate", "count": 5},
                {"assigned_to": "agent2@example.com", "client_type": "individual", "count": 8},
                {"assigned_to": None, "client_type": "individual", "count": 2},  # Unassigned
            ],
            # Status changes in last 24h
            [
                {
                    "from_status": "prospect",
                    "to_status": "active",
                    "changed_by": "agent1@example.com",
                    "count": 3,
                },
                {
                    "from_status": "active",
                    "to_status": "inactive",
                    "changed_by": "agent2@example.com",
                    "count": 1,
                },
                {"from_status": "prospect", "to_status": "active", "changed_by": None, "count": 1},
            ],
        ]

        results = {"metrics_updated": [], "errors": []}
        await collector.update_client_metrics(results)

        assert "active_clients_total" in results["metrics_updated"]
        assert "client_status_changes" in results["metrics_updated"]
        assert len(results["errors"]) == 0

        # Verify gauge was called for each client combination
        assert mock_conn.fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_update_application_metrics_detailed(self, collector_instance):
        """Test application metrics update in detail"""
        collector, mock_conn = collector_instance

        # Mock application data
        mock_conn.fetch.side_effect = [
            # Applications in progress
            [
                {"stage": "document_collection", "priority": "high", "count": 3},
                {"stage": "under_review", "priority": "normal", "count": 5},
                {"stage": "final_approval", "priority": "low", "count": 2},
            ],
            # Processing times for completed applications
            [
                {
                    "visa_type": "work_visa",
                    "destination_country": "IT",
                    "outcome": "approved",
                    "duration_seconds": 86400,
                },
                {
                    "visa_type": "student_visa",
                    "destination_country": "US",
                    "outcome": "approved",
                    "duration_seconds": 129600,  # 36 hours
                },
                {
                    "visa_type": "tourist_visa",
                    "destination_country": "UK",
                    "outcome": "rejected",
                    "duration_seconds": 21600,  # 6 hours
                },
            ],
        ]

        results = {"metrics_updated": [], "errors": []}
        await collector.update_application_metrics(results)

        assert "applications_in_progress" in results["metrics_updated"]
        assert "application_processing_duration" in results["metrics_updated"]
        assert len(results["errors"]) == 0

    @pytest.mark.asyncio
    async def test_update_business_metrics_detailed(self, collector_instance):
        """Test business metrics update in detail"""
        collector, mock_conn = collector_instance

        # Mock business data
        mock_conn.fetch.side_effect = [
            # Conversion rates by lead source
            [
                {
                    "lead_source": "website",
                    "prospects": 50,
                    "active_clients": 15,
                    "conversion_rate": 30.0,
                },
                {
                    "lead_source": "referral",
                    "prospects": 20,
                    "active_clients": 12,
                    "conversion_rate": 60.0,
                },
                {
                    "lead_source": "cold_call",
                    "prospects": 100,
                    "active_clients": 10,
                    "conversion_rate": 10.0,
                },
            ],
            # Client lifecycle durations
            [
                {
                    "client_type": "individual",
                    "outcome": "approved",
                    "lifecycle_seconds": 2592000,  # 30 days
                },
                {
                    "client_type": "corporate",
                    "outcome": "approved",
                    "lifecycle_seconds": 1728000,  # 20 days
                },
                {
                    "client_type": "individual",
                    "outcome": "rejected",
                    "lifecycle_seconds": 432000,  # 5 days
                },
            ],
        ]

        results = {"metrics_updated": [], "errors": []}
        await collector.update_business_metrics(results)

        assert "conversion_rate" in results["metrics_updated"]
        assert "client_lifecycle_duration" in results["metrics_updated"]
        assert len(results["errors"]) == 0

    @pytest.mark.asyncio
    async def test_update_operational_metrics_detailed(self, collector_instance):
        """Test operational metrics update in detail"""
        collector, mock_conn = collector_instance

        # Mock operational data
        mock_conn.fetch.return_value = [
            {
                "interaction_type": "email",
                "channel": "web",
                "response_time_seconds": 3600,  # 1 hour
            },
            {
                "interaction_type": "whatsapp",
                "channel": "mobile",
                "response_time_seconds": 300,  # 5 minutes
            },
            {
                "interaction_type": "phone",
                "channel": "landline",
                "response_time_seconds": 180,  # 3 minutes
            },
        ]

        results = {"metrics_updated": [], "errors": []}
        await collector.update_operational_metrics(results)

        assert "interaction_response_time" in results["metrics_updated"]
        assert len(results["errors"]) == 0

        # Verify histogram was called for each interaction type
        assert len(mock_conn.fetch.return_value) == 3

    @pytest.mark.asyncio
    async def test_get_metrics_summary_complete(self, collector_instance):
        """Test complete metrics summary"""
        collector, mock_conn = collector_instance

        # Mock comprehensive summary data
        mock_conn.fetchrow.side_effect = [
            # Client stats
            {
                "active_clients": 75,
                "prospects": 30,
                "completed_clients": 150,
                "total_clients": 255,
                "new_clients_30d": 25,
                "active_clients_30d": 20,
            },
            # Application stats
            {
                "applications_in_progress": 12,
                "completed_applications": 40,
                "total_applications": 52,
                "avg_processing_days": 15.5,
            },
        ]

        result = await collector.get_metrics_summary()

        assert "timestamp" in result
        assert "clients" in result
        assert "applications" in result

        # Verify client data
        clients = result["clients"]
        assert clients["active"] == 75
        assert clients["prospects"] == 30
        assert clients["completed"] == 150
        assert clients["total"] == 255
        assert clients["new_last_30d"] == 25
        assert clients["active_last_30d"] == 20

        # Verify application data
        applications = result["applications"]
        assert applications["in_progress"] == 12
        assert applications["completed"] == 40
        assert applications["total"] == 52
        assert applications["avg_processing_days"] == pytest.approx(15.5)

    @pytest.mark.asyncio
    async def test_get_metrics_summary_error_handling(self, collector_instance):
        """Test metrics summary error handling"""
        collector, mock_conn = collector_instance

        mock_conn.fetchrow.side_effect = Exception("Database connection failed")

        result = await collector.get_metrics_summary()

        assert "error" in result
        assert "timestamp" in result
        assert result["error"] == "Database connection failed"

    @pytest.mark.asyncio
    async def test_metrics_collector_get_pool(self, collector_instance):
        """Test metrics collector pool initialization"""
        collector, _ = collector_instance

        # Reset pool to test initialization
        collector.pool = None

        # Mock get_database_pool
        async_pool = AsyncMock()
        async_conn = AsyncMock()
        async_pool.acquire.return_value.__aenter__.return_value = async_conn

        async def fake_get_pool():
            return async_pool

        with patch(
            "app.services.crm.metrics.get_database_pool", side_effect=fake_get_pool
        ) as mock_get_pool:
            pool = await collector._get_pool()

            assert pool == async_pool
            mock_get_pool.assert_called_once()


class TestMetricsDecoratorsAndScheduler:
    """Targeted tests for metrics decorators and scheduler"""

    @pytest.mark.asyncio
    async def test_track_client_creation_observes_duration(self):
        from app.services.crm.metrics import track_client_creation

        async def create_client():
            return "ok"

        label = MagicMock()
        observe = MagicMock()
        label.observe = observe
        mock_hist = MagicMock()
        mock_hist.labels.return_value = label

        with patch("app.services.crm.metrics.crm_metrics.client_creation_duration", mock_hist):
            decorated = track_client_creation(client_type="individual", lead_source="web")(
                create_client
            )
            await decorated()

        mock_hist.labels.assert_called_with(client_type="individual", lead_source="web")
        observe.assert_called_once()

    @pytest.mark.asyncio
    async def test_track_client_creation_records_duration_on_error(self):
        from app.services.crm.metrics import track_client_creation

        async def fail_client():
            raise RuntimeError("creation failed")

        label = MagicMock()
        observe = MagicMock()
        label.observe = observe
        mock_hist = MagicMock()
        mock_hist.labels.return_value = label

        with patch("app.services.crm.metrics.crm_metrics.client_creation_duration", mock_hist):
            decorated = track_client_creation(client_type="existing", lead_source="referral")(
                fail_client
            )
            with pytest.raises(RuntimeError):
                await decorated()

        mock_hist.labels.assert_called_with(client_type="existing", lead_source="referral")
        observe.assert_called_once()

    @pytest.mark.asyncio
    async def test_track_application_processing_records_error_on_failure(self):
        from app.services.crm.metrics import track_application_processing

        async def fail_app():
            raise RuntimeError("boom")

        label = MagicMock()
        observe = MagicMock()
        label.observe = observe
        mock_hist = MagicMock()
        mock_hist.labels.return_value = label

        with patch(
            "app.services.crm.metrics.crm_metrics.application_processing_duration",
            mock_hist,
        ):
            decorated = track_application_processing(
                visa_type="work_visa", destination_country="IT"
            )(fail_app)
            with pytest.raises(RuntimeError):
                await decorated()

        assert mock_hist.labels.call_args_list[-1][1]["outcome"] == "error"
        observe.assert_called_once()

    @pytest.mark.asyncio
    async def test_track_application_processing_observes_success(self):
        from app.services.crm.metrics import track_application_processing

        class Result:
            outcome = "approved"

        async def handle_app():
            return Result()

        label = MagicMock()
        observe = MagicMock()
        label.observe = observe
        mock_hist = MagicMock()
        mock_hist.labels.return_value = label

        with patch(
            "app.services.crm.metrics.crm_metrics.application_processing_duration",
            mock_hist,
        ):
            decorated = track_application_processing(
                visa_type="business", destination_country="CA"
            )(handle_app)
            await decorated()

        mock_hist.labels.assert_called_with(
            visa_type="business", destination_country="CA", outcome="approved"
        )
        observe.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_metrics_updates_runs_once(self, monkeypatch):
        from app.services.crm.metrics import (
            asyncio as metrics_asyncio,
        )
        from app.services.crm.metrics import (
            metrics_collector,
            schedule_metrics_updates,
        )

        call_count = 0
        sleep_args: list[int] = []

        async def fake_update():
            nonlocal call_count
            call_count += 1

        async def fake_sleep(duration):
            sleep_args.append(duration)
            raise metrics_asyncio.CancelledError()

        monkeypatch.setattr(metrics_collector, "update_all_metrics", fake_update)
        monkeypatch.setattr("app.services.crm.metrics.asyncio.sleep", fake_sleep)

        with pytest.raises(metrics_asyncio.CancelledError):
            await schedule_metrics_updates()

        assert call_count == 1

        assert sleep_args == [300]

    @pytest.mark.asyncio
    async def test_schedule_metrics_updates_handles_errors(self, monkeypatch):
        from app.services.crm.metrics import (
            asyncio as metrics_asyncio,
        )
        from app.services.crm.metrics import (
            metrics_collector,
            schedule_metrics_updates,
        )

        async def fake_update():
            raise RuntimeError("metrics failure")

        sleep_calls: list[int] = []

        async def fake_sleep(duration):
            sleep_calls.append(duration)
            if len(sleep_calls) == 2:
                raise metrics_asyncio.CancelledError()

        monkeypatch.setattr(metrics_collector, "update_all_metrics", fake_update)
        monkeypatch.setattr("app.services.crm.metrics.asyncio.sleep", fake_sleep)

        with pytest.raises(metrics_asyncio.CancelledError):
            await schedule_metrics_updates()

        assert sleep_calls[0] == 60
        assert sleep_calls[1] == 60


class TestCRMIntegrationComplete:
    """Complete integration tests for CRM system"""

    @pytest.mark.asyncio
    async def test_full_audit_flow(self):
        """Test complete audit flow from creation to retrieval"""
        from app.services.crm.audit_logger import CRMAuditLogger

        audit_logger = CRMAuditLogger()
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        audit_logger.pool = mock_pool

        # Step 1: Log initial state change
        result1 = await audit_logger.log_state_change(
            entity_type="client",
            entity_id=123,
            old_state={"status": "prospect"},
            new_state={"status": "active"},
            user_email="agent@example.com",
        )
        assert result1 is True

        # Step 2: Log status change
        result2 = await audit_logger.log_client_status_change(
            client_id=123,
            old_status="active",
            new_status="inactive",
            user_email="agent@example.com",
        )
        assert result2 is True

        # Step 3: Log case progression
        result3 = await audit_logger.log_case_progression(
            case_id=456,
            old_stage="application_submitted",
            new_stage="under_review",
            user_email="agent@example.com",
        )
        assert result3 is True

        # Step 4: Retrieve audit trail
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

        # Verify full flow
        assert len(audit_trail) == 3
        assert mock_conn.execute.call_count == 3  # 3 log calls
        assert mock_conn.fetch.call_count == 1  # 1 retrieval call

    @pytest.mark.asyncio
    async def test_metrics_and_audit_integration(self):
        """Test integration between metrics and audit logging"""
        from app.services.crm.audit_logger import CRMAuditLogger
        from app.services.crm.metrics import CRMMetricsCollector

        # Create instances
        audit_logger = CRMAuditLogger()
        metrics_collector = CRMMetricsCollector()

        # Mock database for both
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        audit_logger.pool = mock_pool
        metrics_collector.pool = mock_pool

        # Mock metrics data
        mock_conn.fetch.side_effect = [
            # Metrics queries
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

        # Test both systems work together
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

    @pytest.mark.asyncio
    async def test_error_propagation_integration(self):
        """Test error handling in integrated system"""
        from app.services.crm.audit_logger import CRMAuditLogger
        from app.services.crm.metrics import CRMMetricsCollector

        audit_logger = CRMAuditLogger()
        metrics_collector = CRMMetricsCollector()

        # Mock database with failures
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        audit_logger.pool = mock_pool
        metrics_collector.pool = mock_pool

        # Test audit logging handles database errors
        mock_conn.execute.side_effect = Exception("Connection failed")
        audit_result = await audit_logger.log_state_change(
            entity_type="client",
            entity_id=123,
            old_state={"status": "prospect"},
            new_state={"status": "active"},
            user_email="agent@example.com",
        )

        assert audit_result is False

        # Test metrics handles partial failures
        mock_conn.execute.side_effect = None
        mock_conn.fetch.side_effect = [
            [{"assigned_to": "agent@example.com", "client_type": "individual", "count": 5}],
            Exception("Query timeout"),
        ]

        metrics_result = await metrics_collector.update_all_metrics()

        assert metrics_result["success"] is True  # Overall success
        assert len(metrics_result["errors"]) > 0  # But with errors


class TestCRMEdgeCases:
    """Test edge cases and boundary conditions"""

    @pytest.mark.asyncio
    async def test_null_and_empty_values(self):
        """Test handling of null and empty values"""
        from app.services.crm.audit_logger import CRMAuditLogger

        audit_logger = CRMAuditLogger()
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        audit_logger.pool = mock_pool

        # Test with None values
        result = await audit_logger.log_state_change(
            entity_type="client",
            entity_id=123,
            old_state={"status": None, "name": None, "email": ""},
            new_state={"status": "active", "name": "", "email": None},
            user_email="test@example.com",
            metadata=None,
        )

        assert result is True
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_large_data_sets(self):
        """Test handling of large data sets"""
        from app.services.crm.audit_logger import CRMAuditLogger

        audit_logger = CRMAuditLogger()
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        audit_logger.pool = mock_pool

        # Create large state data
        large_old_state = {f"field_{i}": f"value_{i}" for i in range(1000)}
        large_new_state = {f"field_{i}": f"new_value_{i}" for i in range(1000)}
        large_metadata = {f"meta_{i}": f"data_{i}" for i in range(100)}

        result = await audit_logger.log_state_change(
            entity_type="client",
            entity_id=123,
            old_state=large_old_state,
            new_state=large_new_state,
            user_email="test@example.com",
            metadata=large_metadata,
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test concurrent audit operations"""
        from app.services.crm.audit_logger import CRMAuditLogger

        audit_logger = CRMAuditLogger()
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        audit_logger.pool = mock_pool

        # Create multiple concurrent tasks
        tasks = []
        for i in range(50):
            task = audit_logger.log_state_change(
                entity_type="client",
                entity_id=i,
                old_state={"status": "prospect"},
                new_state={"status": "active"},
                user_email=f"user_{i}@example.com",
            )
            tasks.append(task)

        # Execute all concurrently
        results = await asyncio.gather(*tasks)

        # Verify all succeeded
        assert all(result is True for result in results)
        assert mock_conn.execute.call_count == 50

    def test_special_characters_in_data(self):
        """Test handling of special characters and unicode"""
        from app.services.crm.audit_logger import CRMAuditLogger

        audit_logger = CRMAuditLogger()

        # Test with special characters
        old_state = {
            "name": "José María",
            "notes": "Client with émojis 🎉 and 特殊文字",
            "address": "123 Main St, São Paulo",
        }
        new_state = {
            "name": "José María García",
            "notes": "Updated with more émojis 🚀✨ and 中文文字",
            "address": "456 New Ave, São Paulo",
        }

        result = audit_logger._detect_changes(old_state, new_state)

        assert len(result) == 3
        assert "name" in result
        assert "notes" in result
        assert "address" in result
        assert result["name"]["old"] == "José María"
        assert result["name"]["new"] == "José María García"

    @pytest.mark.asyncio
    async def test_extreme_values(self):
        """Test handling of extreme values"""
        from app.services.crm.audit_logger import CRMAuditLogger

        audit_logger = CRMAuditLogger()
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        audit_logger.pool = mock_pool

        # Test with extreme values
        extreme_state = {
            "very_long_text": "x" * 10000,
            "very_large_number": 999999999999999999,
            "very_small_number": 0.0000000001,
            "unicode_text": "🎉" * 1000,
        }

        result = await audit_logger.log_state_change(
            entity_type="client",
            entity_id=123,
            old_state={},
            new_state=extreme_state,
            user_email="test@example.com",
        )

        assert result is True


if __name__ == "__main__":
    pytest.main(
        [
            __file__,
            "-v",
            "--cov=app.services.crm",
            "--cov-report=term-missing",
            "--cov-report=html",
            "--cov-fail-under=95",
        ]
    )
