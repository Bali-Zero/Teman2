"""
Advanced Monitoring and Observability Integration Tests
Tests monitoring, metrics, logging, and observability

Covers:
- Metrics collection
- Performance monitoring
- Log aggregation
- Alert generation
- Health dashboards
"""

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
@pytest.mark.slow
class TestMonitoringObservabilityAdvanced:
    """Advanced monitoring and observability integration tests"""

    @pytest.mark.asyncio
    async def test_metrics_collection(self, db_pool):
        """Test metrics collection"""

        async with db_pool.acquire() as conn:
            # Create metrics table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS metrics (
                    id SERIAL PRIMARY KEY,
                    metric_name VARCHAR(255),
                    metric_value DECIMAL(10,2),
                    metric_type VARCHAR(50),
                    tags JSONB DEFAULT '{}',
                    collected_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Collect metrics
            metrics = [
                ("request_count", 1000, "counter"),
                ("response_time_ms", 150.5, "gauge"),
                ("error_rate", 0.02, "gauge"),
                ("active_connections", 25, "gauge"),
            ]

            for metric_name, metric_value, metric_type in metrics:
                await conn.execute(
                    """
                    INSERT INTO metrics (
                        metric_name, metric_value, metric_type, tags
                    )
                    VALUES ($1, $2, $3, $4)
                    """,
                    metric_name,
                    metric_value,
                    metric_type,
                    {"service": "backend", "environment": "test"},
                )

            # Aggregate metrics
            aggregated = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total_metrics,
                    AVG(metric_value) as avg_value,
                    MAX(metric_value) as max_value
                FROM metrics
                WHERE metric_type = $1
                """,
                "gauge",
            )

            assert aggregated is not None
            assert aggregated["total_metrics"] == 3

            # Cleanup
            await conn.execute("DELETE FROM metrics")

    @pytest.mark.asyncio
    async def test_performance_monitoring(self, db_pool):
        """Test performance monitoring"""

        async with db_pool.acquire() as conn:
            # Create performance_metrics table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id SERIAL PRIMARY KEY,
                    endpoint VARCHAR(255),
                    method VARCHAR(10),
                    response_time_ms INTEGER,
                    status_code INTEGER,
                    request_size_bytes INTEGER,
                    response_size_bytes INTEGER,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Track performance
            endpoints = [
                ("/api/clients", "GET", 50, 200, 100, 5000),
                ("/api/practices", "POST", 150, 201, 500, 2000),
                ("/api/oracle/query", "POST", 300, 200, 200, 8000),
            ]

            for endpoint, method, response_time, status, req_size, resp_size in endpoints:
                await conn.execute(
                    """
                    INSERT INTO performance_metrics (
                        endpoint, method, response_time_ms, status_code,
                        request_size_bytes, response_size_bytes
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    endpoint,
                    method,
                    response_time,
                    status,
                    req_size,
                    resp_size,
                )

            # Analyze performance
            performance = await conn.fetchrow(
                """
                SELECT
                    AVG(response_time_ms) as avg_response_time,
                    MAX(response_time_ms) as max_response_time,
                    COUNT(*) as total_requests,
                    SUM(request_size_bytes + response_size_bytes) as total_bytes
                FROM performance_metrics
                """
            )

            assert performance is not None
            assert performance["total_requests"] == len(endpoints)
            assert performance["avg_response_time"] > 0

            # Cleanup
            await conn.execute("DELETE FROM performance_metrics")

    @pytest.mark.asyncio
    async def test_log_aggregation(self, db_pool):
        """Test log aggregation"""

        async with db_pool.acquire() as conn:
            # Create logs table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS aggregated_logs (
                    id SERIAL PRIMARY KEY,
                    log_level VARCHAR(50),
                    log_message TEXT,
                    component VARCHAR(255),
                    user_id VARCHAR(255),
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Aggregate logs
            log_entries = [
                ("INFO", "Request processed", "api", "user_1"),
                ("ERROR", "Database connection failed", "database", None),
                ("WARNING", "Rate limit approaching", "middleware", None),
                ("INFO", "Cache hit", "cache", None),
            ]

            for level, message, component, user_id in log_entries:
                await conn.execute(
                    """
                    INSERT INTO aggregated_logs (
                        log_level, log_message, component, user_id
                    )
                    VALUES ($1, $2, $3, $4)
                    """,
                    level,
                    message,
                    component,
                    user_id,
                )

            # Aggregate by level
            log_summary = await conn.fetchrow(
                """
                SELECT
                    log_level,
                    COUNT(*) as count
                FROM aggregated_logs
                GROUP BY log_level
                ORDER BY count DESC
                LIMIT 1
                """
            )

            assert log_summary is not None
            assert log_summary["count"] >= 1

            # Cleanup
            await conn.execute("DELETE FROM aggregated_logs")

    @pytest.mark.asyncio
    async def test_alert_generation(self, db_pool):
        """Test alert generation"""

        async with db_pool.acquire() as conn:
            # Create alerts table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS system_alerts (
                    id SERIAL PRIMARY KEY,
                    alert_type VARCHAR(100),
                    severity VARCHAR(50),
                    message TEXT,
                    component VARCHAR(255),
                    resolved BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Generate alerts
            alerts = [
                ("high_error_rate", "critical", "Error rate exceeded 5%", "api"),
                ("slow_response", "warning", "Response time > 1s", "database"),
                ("resource_exhaustion", "critical", "Memory usage > 90%", "system"),
            ]

            for alert_type, severity, message, component in alerts:
                await conn.execute(
                    """
                    INSERT INTO system_alerts (
                        alert_type, severity, message, component
                    )
                    VALUES ($1, $2, $3, $4)
                    """,
                    alert_type,
                    severity,
                    message,
                    component,
                )

            # Get critical alerts
            critical_alerts = await conn.fetch(
                """
                SELECT alert_type, message
                FROM system_alerts
                WHERE severity = $1 AND resolved = FALSE
                ORDER BY created_at DESC
                """,
                "critical",
            )

            assert len(critical_alerts) == 2

            # Cleanup
            await conn.execute("DELETE FROM system_alerts")

    @pytest.mark.asyncio
    async def test_health_dashboard_data(self, db_pool):
        """Test health dashboard data"""

        async with db_pool.acquire() as conn:
            # Create health_dashboard table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS health_dashboard (
                    id SERIAL PRIMARY KEY,
                    service_name VARCHAR(255),
                    health_status VARCHAR(50),
                    uptime_percentage DECIMAL(5,2),
                    last_check TIMESTAMP DEFAULT NOW()
                )
                """
            )

            # Store health data
            services = [
                ("database", "healthy", 99.9),
                ("qdrant", "healthy", 99.8),
                ("ai_service", "degraded", 95.5),
            ]

            for service_name, status, uptime in services:
                await conn.execute(
                    """
                    INSERT INTO health_dashboard (
                        service_name, health_status, uptime_percentage
                    )
                    VALUES ($1, $2, $3)
                    ON CONFLICT (service_name) DO UPDATE
                    SET health_status = EXCLUDED.health_status,
                        uptime_percentage = EXCLUDED.uptime_percentage,
                        last_check = NOW()
                    """,
                    service_name,
                    status,
                    uptime,
                )

            # Get dashboard data
            dashboard = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total_services,
                    COUNT(CASE WHEN health_status = 'healthy' THEN 1 END) as healthy_count,
                    AVG(uptime_percentage) as avg_uptime
                FROM health_dashboard
                """
            )

            assert dashboard is not None
            assert dashboard["total_services"] == len(services)
            assert dashboard["healthy_count"] == 2

            # Cleanup
            await conn.execute("DELETE FROM health_dashboard")










