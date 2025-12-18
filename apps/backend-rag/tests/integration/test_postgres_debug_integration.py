"""
Integration tests for PostgreSQL debug endpoints.
Tests end-to-end integration with database (if available) or mocked database pool.
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Set required environment variables BEFORE any imports
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")
os.environ.setdefault("API_KEYS", "test_api_key_1,test_api_key_2")
os.environ.setdefault("ADMIN_API_KEY", "test_admin_api_key")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("OPENAI_API_KEY", "sk-REDACTED")
os.environ.setdefault("GOOGLE_API_KEY", "test_google_api_key_for_testing")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test_whatsapp_verify_token")
os.environ.setdefault("INSTAGRAM_VERIFY_TOKEN", "test_instagram_verify_token")

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.fixture
def client():
    """Create test client with debug router only (no middleware)."""
    from fastapi import FastAPI
    from app.routers import debug
    
    # Create minimal app with only debug router (no middleware)
    app = FastAPI()
    app.include_router(debug.router)
    
    # Mock settings for debug router
    with patch("app.routers.debug.settings") as mock_settings:
        mock_settings.environment = "development"
        mock_settings.admin_api_key = os.getenv("ADMIN_API_KEY", "test_admin_api_key")
        # Also patch settings in postgres_debugger
        with patch("app.utils.postgres_debugger.settings") as mock_pg_settings:
            mock_pg_settings.database_url = os.getenv("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
            yield TestClient(app)


@pytest.fixture
def auth_headers():
    """Get authentication headers for debug endpoints."""
    return {"Authorization": f"Bearer {os.getenv('ADMIN_API_KEY')}"}


@pytest.fixture
def mock_db_pool():
    """Create mock database pool."""
    mock_pool = MagicMock()
    mock_pool.get_size = MagicMock(return_value=10)
    mock_pool.get_idle_size = MagicMock(return_value=5)
    mock_pool.acquire = MagicMock()

    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(side_effect=["PostgreSQL 14.0", "testdb", "testuser"])
    mock_conn.fetch = AsyncMock(return_value=[])
    mock_conn.close = AsyncMock()

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire.return_value = mock_cm

    return mock_pool, mock_conn


class TestPostgresDebugIntegration:
    """Integration tests for PostgreSQL debug functionality."""

    def test_connection_endpoint_with_pool_from_app_state(self, client, auth_headers, mock_db_pool):
        """Test connection endpoint uses pool from app.state if available."""
        mock_pool, mock_conn = mock_db_pool

        # Get app from client
        app = client.app

        # Set pool in app.state
        app.state.db_pool = mock_pool

        try:
            response = client.get("/api/debug/postgres/connection", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["connection"]["connected"] is True
            assert data["connection"]["pool_size"] == 10
            assert data["connection"]["pool_idle"] == 5
            assert data["connection"]["pool_active"] == 5
        finally:
            # Cleanup
            if hasattr(app.state, "db_pool"):
                delattr(app.state, "db_pool")

    def test_connection_endpoint_with_memory_service_pool(self, client, auth_headers, mock_db_pool):
        """Test connection endpoint uses pool from memory_service if available."""
        mock_pool, mock_conn = mock_db_pool

        # Get app from client
        app = client.app

        # Create mock memory_service with pool
        mock_memory_service = MagicMock()
        mock_memory_service.pool = mock_pool
        app.state.memory_service = mock_memory_service

        try:
            response = client.get("/api/debug/postgres/connection", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["connection"]["connected"] is True
        finally:
            # Cleanup
            if hasattr(app.state, "memory_service"):
                delattr(app.state, "memory_service")

    def test_query_endpoint_with_pool(self, client, auth_headers, mock_db_pool):
        """Test query endpoint uses pool from app.state if available."""
        mock_pool, mock_conn = mock_db_pool

        # Mock query results
        mock_desc_id = MagicMock()
        mock_desc_id.name = "id"
        mock_desc_name = MagicMock()
        mock_desc_name.name = "name"
        
        mock_row = MagicMock()
        mock_row._row_desc = [mock_desc_id, mock_desc_name]
        mock_row.__getitem__ = MagicMock(side_effect=lambda k: {"id": 1, "name": "test"}[k])
        mock_row.keys = MagicMock(return_value=["id", "name"])
        mock_conn.fetch = AsyncMock(return_value=[mock_row])

        # Get app from client
        app = client.app

        # Set pool in app.state
        app.state.db_pool = mock_pool

        try:
            response = client.post(
                "/api/debug/postgres/query",
                headers=auth_headers,
                json={"query": "SELECT * FROM users LIMIT 10", "limit": 10},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "rows" in data
            # Verify pool was used
            mock_pool.acquire.assert_called_once()
        finally:
            # Cleanup
            if hasattr(app.state, "db_pool"):
                delattr(app.state, "db_pool")

    def test_full_workflow_schema_inspection(self, client, auth_headers):
        """Test full workflow: get tables -> get table details -> get indexes."""
        with patch("app.utils.postgres_debugger.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.close = AsyncMock()

            # Mock tables list
            mock_table_row = MagicMock()
            mock_table_row.__getitem__ = MagicMock(side_effect=lambda k: {"table_name": "users", "table_type": "BASE TABLE"}[k])
            mock_table_row.keys = MagicMock(return_value=["table_name", "table_type"])

            # Mock table details
            mock_col = MagicMock()
            mock_col.__getitem__ = MagicMock(side_effect=lambda k: {"column_name": "id", "data_type": "integer", "is_nullable": "NO", "column_default": None, "character_maximum_length": None, "numeric_precision": None, "numeric_scale": None}[k])
            mock_col.keys = MagicMock(return_value=["column_name", "data_type"])

            # Mock indexes
            mock_idx_row = MagicMock()
            mock_idx_row.__getitem__ = MagicMock(side_effect=lambda k: {"schemaname": "public", "tablename": "users", "indexname": "idx_users_email", "indexdef": "CREATE INDEX..."}[k])
            mock_idx_row.keys = MagicMock(return_value=["schemaname", "tablename", "indexname", "indexdef"])

            mock_conn.fetch = AsyncMock(
                side_effect=[
                    [mock_table_row],  # get_tables
                    [mock_col],  # get_table_details - columns
                    [],  # get_table_details - indexes
                    [],  # get_table_details - foreign keys
                    [],  # get_table_details - constraints
                    [mock_idx_row],  # get_indexes
                ]
            )
            mock_connect.return_value = mock_conn

            # Step 1: Get tables
            response1 = client.get("/api/debug/postgres/schema/tables", headers=auth_headers)
            assert response1.status_code == 200
            tables_data = response1.json()
            assert len(tables_data["tables"]) > 0

            # Step 2: Get table details
            response2 = client.get("/api/debug/postgres/schema/table/users", headers=auth_headers)
            assert response2.status_code == 200
            table_data = response2.json()
            assert "columns" in table_data["table"]

            # Step 3: Get indexes
            response3 = client.get("/api/debug/postgres/schema/indexes?table_name=users", headers=auth_headers)
            assert response3.status_code == 200
            indexes_data = response3.json()
            assert "indexes" in indexes_data

    def test_full_workflow_stats(self, client, auth_headers):
        """Test full workflow: database stats -> table stats."""
        with patch("app.utils.postgres_debugger.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.close = AsyncMock()

            # Mock database stats
            mock_conn.fetchval = AsyncMock(side_effect=["100 MB", "PostgreSQL 14.0", 10, 5, 5, "testdb"])

            # Mock table stats
            mock_stat_row = MagicMock()
            mock_stat_row.__getitem__ = MagicMock(side_effect=lambda k: {"schemaname": "public", "tablename": "users", "total_size": "1 MB", "table_size": "800 kB", "indexes_size": "200 kB", "index_count": 2}[k])
            mock_stat_row.keys = MagicMock(return_value=["schemaname", "tablename", "total_size"])

            mock_conn.fetch = AsyncMock(return_value=[mock_stat_row])
            mock_conn.fetchval = AsyncMock(side_effect=["100 MB", "PostgreSQL 14.0", 10, 5, 5, "testdb", 100])  # db stats + row count

            mock_connect.return_value = mock_conn

            # Step 1: Get database stats
            response1 = client.get("/api/debug/postgres/stats/database", headers=auth_headers)
            assert response1.status_code == 200
            db_stats = response1.json()
            assert db_stats["stats"]["database"] == "testdb"

            # Step 2: Get table stats
            response2 = client.get("/api/debug/postgres/stats/tables", headers=auth_headers)
            assert response2.status_code == 200
            table_stats = response2.json()
            assert "stats" in table_stats

    def test_error_propagation(self, client, auth_headers):
        """Test that errors are properly propagated through the stack."""
        with patch("app.utils.postgres_debugger.asyncpg.connect", side_effect=Exception("Database connection failed")):
            response = client.get("/api/debug/postgres/schema/tables", headers=auth_headers)

            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
            assert "Database connection failed" in data["detail"]

    def test_query_validation_integration(self, client, auth_headers):
        """Test that query validation works end-to-end."""
        # Test various invalid queries
        invalid_queries = [
            "UPDATE users SET name = 'test'",
            "DELETE FROM users",
            "DROP TABLE users",
            "CREATE TABLE test (id INT)",
            "SELECT * FROM users; DROP TABLE users",
        ]

        for query in invalid_queries:
            response = client.post(
                "/api/debug/postgres/query",
                headers=auth_headers,
                json={"query": query, "limit": 10},
            )

            assert response.status_code == 400, f"Query should be rejected: {query}"
            data = response.json()
            assert "detail" in data

    def test_performance_endpoints_integration(self, client, auth_headers):
        """Test performance endpoints work together."""
        with patch("app.utils.postgres_debugger.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.close = AsyncMock()

            # Mock slow queries
            mock_conn.fetchval = AsyncMock(return_value=True)  # extension exists
            mock_slow_row = MagicMock()
            mock_slow_row.__getitem__ = MagicMock(side_effect=lambda k: {"query": "SELECT * FROM users", "calls": 100, "total_exec_time": 5000.0, "mean_exec_time": 50.0, "max_exec_time": 200.0, "min_exec_time": 10.0, "stddev_exec_time": 20.0}[k])
            mock_slow_row.keys = MagicMock(return_value=["query", "calls"])

            # Mock locks
            mock_lock_row = MagicMock()
            mock_lock_row.__getitem__ = MagicMock(side_effect=lambda k: {"locktype": "relation", "relation": "users", "mode": "AccessShareLock", "granted": True, "pid": 12345, "usename": "testuser", "application_name": "testapp", "state": "active", "query_start": None, "state_change": None}[k])
            mock_lock_row.keys = MagicMock(return_value=["locktype", "relation"])

            # Mock connection stats
            mock_state_row = MagicMock()
            mock_state_row.__getitem__ = MagicMock(side_effect=lambda k: {"state": "active", "count": 5}[k])
            mock_state_row.keys = MagicMock(return_value=["state", "count"])

            mock_conn.fetch = AsyncMock(
                side_effect=[
                    [mock_slow_row],  # slow queries
                    [mock_lock_row],  # locks
                    [mock_state_row],  # connection stats
                ]
            )
            mock_conn.fetchval = AsyncMock(side_effect=[True, 10, 2, 3])  # extension exists, total, long_running, idle_in_transaction
            mock_connect.return_value = mock_conn

            # Test slow queries
            response1 = client.get("/api/debug/postgres/performance/slow-queries", headers=auth_headers)
            assert response1.status_code == 200

            # Test locks
            response2 = client.get("/api/debug/postgres/performance/locks", headers=auth_headers)
            assert response2.status_code == 200

            # Test connection stats
            response3 = client.get("/api/debug/postgres/performance/connections", headers=auth_headers)
            assert response3.status_code == 200

