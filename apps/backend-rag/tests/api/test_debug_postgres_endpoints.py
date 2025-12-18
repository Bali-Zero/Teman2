"""
API Tests for PostgreSQL Debug Endpoints
Tests all PostgreSQL debug endpoints with authentication, security, and error handling.
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
    admin_key = os.getenv("ADMIN_API_KEY", "test_admin_api_key")
    return {"Authorization": f"Bearer {admin_key}"}


class TestPostgresConnectionEndpoint:
    """Test /api/debug/postgres/connection endpoint."""

    def test_connection_endpoint_success(self, client, auth_headers):
        """Test connection endpoint with successful connection."""
        with patch("app.utils.postgres_debugger.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.fetchval = AsyncMock(side_effect=["PostgreSQL 14.0", "testdb", "testuser"])
            mock_conn.close = AsyncMock()
            mock_connect.return_value = mock_conn

            response = client.get("/api/debug/postgres/connection", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["connection"]["connected"] is True
            assert data["connection"]["version"] == "PostgreSQL 14.0"

    def test_connection_endpoint_failure(self, client, auth_headers):
        """Test connection endpoint with connection failure."""
        with patch(
            "app.utils.postgres_debugger.asyncpg.connect", side_effect=Exception("Connection failed")
        ):
            response = client.get("/api/debug/postgres/connection", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["connection"]["connected"] is False
            # Error can be in connection dict or at root level
            assert "error" in data["connection"] or "error" in data

    def test_connection_endpoint_unauthorized(self, client):
        """Test connection endpoint without authentication."""
        response = client.get("/api/debug/postgres/connection")

        assert response.status_code == 401


class TestPostgresSchemaEndpoints:
    """Test PostgreSQL schema inspection endpoints."""

    def test_get_tables_endpoint(self, client, auth_headers):
        """Test /api/debug/postgres/schema/tables endpoint."""
        with patch("app.utils.postgres_debugger.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_row = MagicMock()
            mock_row.__getitem__ = MagicMock(side_effect=lambda k: {"table_name": "users", "table_type": "BASE TABLE"}[k])
            mock_row.keys = MagicMock(return_value=["table_name", "table_type"])
            mock_conn.fetch = AsyncMock(return_value=[mock_row])
            mock_conn.close = AsyncMock()
            mock_connect.return_value = mock_conn

            response = client.get("/api/debug/postgres/schema/tables", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["tables"]) > 0

    def test_get_table_details_endpoint(self, client, auth_headers):
        """Test /api/debug/postgres/schema/table/{name} endpoint."""
        with patch("app.utils.postgres_debugger.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            # Mock columns
            mock_col = MagicMock()
            mock_col.__getitem__ = MagicMock(side_effect=lambda k: {"column_name": "id", "data_type": "integer", "is_nullable": "NO", "column_default": None, "character_maximum_length": None, "numeric_precision": None, "numeric_scale": None}[k])
            mock_col.keys = MagicMock(return_value=["column_name", "data_type", "is_nullable"])
            mock_conn.fetch = AsyncMock(side_effect=[[mock_col], [], [], []])  # columns, indexes, fks, constraints
            mock_conn.close = AsyncMock()
            mock_connect.return_value = mock_conn

            response = client.get("/api/debug/postgres/schema/table/users", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "table" in data
            assert "columns" in data["table"]

    def test_get_indexes_endpoint(self, client, auth_headers):
        """Test /api/debug/postgres/schema/indexes endpoint."""
        with patch("app.utils.postgres_debugger.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_row = MagicMock()
            mock_row.__getitem__ = MagicMock(side_effect=lambda k: {"schemaname": "public", "tablename": "users", "indexname": "idx_users_email", "indexdef": "CREATE INDEX..."}[k])
            mock_row.keys = MagicMock(return_value=["schemaname", "tablename", "indexname", "indexdef"])
            mock_conn.fetch = AsyncMock(return_value=[mock_row])
            mock_conn.close = AsyncMock()
            mock_connect.return_value = mock_conn

            response = client.get("/api/debug/postgres/schema/indexes", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "indexes" in data


class TestPostgresStatsEndpoints:
    """Test PostgreSQL statistics endpoints."""

    def test_get_table_stats_endpoint(self, client, auth_headers):
        """Test /api/debug/postgres/stats/tables endpoint."""
        with patch("app.utils.postgres_debugger.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_stat_row = MagicMock()
            mock_stat_row.__getitem__ = MagicMock(side_effect=lambda k: {"schemaname": "public", "tablename": "users", "total_size": "1 MB", "table_size": "800 kB", "indexes_size": "200 kB", "index_count": 2}[k])
            mock_stat_row.keys = MagicMock(return_value=["schemaname", "tablename", "total_size"])
            mock_conn.fetch = AsyncMock(return_value=[mock_stat_row])
            mock_conn.fetchval = AsyncMock(return_value=100)
            mock_conn.close = AsyncMock()
            mock_connect.return_value = mock_conn

            response = client.get("/api/debug/postgres/stats/tables", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "stats" in data

    def test_get_database_stats_endpoint(self, client, auth_headers):
        """Test /api/debug/postgres/stats/database endpoint."""
        with patch("app.utils.postgres_debugger.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.fetchval = AsyncMock(side_effect=["100 MB", "PostgreSQL 14.0", 10, 5, 5, "testdb"])
            mock_conn.close = AsyncMock()
            mock_connect.return_value = mock_conn

            response = client.get("/api/debug/postgres/stats/database", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "stats" in data
            assert data["stats"]["database"] == "testdb"


class TestPostgresQueryEndpoint:
    """Test /api/debug/postgres/query endpoint."""

    def test_execute_query_success(self, client, auth_headers):
        """Test successful query execution."""
        with patch("app.utils.postgres_debugger.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_row = MagicMock()
            mock_row._row_desc = [MagicMock(name="id"), MagicMock(name="name")]
            mock_row.__getitem__ = MagicMock(side_effect=lambda k: {"id": 1, "name": "test"}[k])
            mock_row.keys = MagicMock(return_value=["id", "name"])
            mock_conn.fetch = AsyncMock(return_value=[mock_row])
            mock_conn.close = AsyncMock()
            mock_connect.return_value = mock_conn

            response = client.post(
                "/api/debug/postgres/query",
                headers=auth_headers,
                json={"query": "SELECT * FROM users", "limit": 10},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "rows" in data
            assert "row_count" in data

    def test_execute_query_invalid_non_select(self, client, auth_headers):
        """Test that non-SELECT queries are rejected."""
        response = client.post(
            "/api/debug/postgres/query",
            headers=auth_headers,
            json={"query": "UPDATE users SET name = 'test'", "limit": 10},
        )

        assert response.status_code == 400
        data = response.json()
        assert "Only SELECT queries are allowed" in data["detail"]

    def test_execute_query_forbidden_keyword(self, client, auth_headers):
        """Test that queries with forbidden keywords are rejected."""
        response = client.post(
            "/api/debug/postgres/query",
            headers=auth_headers,
            json={"query": "SELECT * FROM users; DROP TABLE users", "limit": 10},
        )

        assert response.status_code == 400
        data = response.json()
        assert "forbidden" in data["detail"].lower() or "DROP" in data["detail"]

    def test_execute_query_limit_enforced(self, client, auth_headers):
        """Test that query limit is enforced."""
        with patch("app.utils.postgres_debugger.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_conn.close = AsyncMock()
            mock_connect.return_value = mock_conn

            response = client.post(
                "/api/debug/postgres/query",
                headers=auth_headers,
                json={"query": "SELECT * FROM users", "limit": 5000},
            )

            assert response.status_code == 200
            # Verify LIMIT was capped
            call_args = mock_conn.fetch.call_args
            assert "LIMIT 1000" in call_args[0][0].upper()

    def test_execute_query_database_error(self, client, auth_headers):
        """Test error handling when database query fails."""
        with patch("app.utils.postgres_debugger.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.fetch = AsyncMock(side_effect=Exception("Database error"))
            mock_conn.close = AsyncMock()
            mock_connect.return_value = mock_conn

            response = client.post(
                "/api/debug/postgres/query",
                headers=auth_headers,
                json={"query": "SELECT * FROM users", "limit": 10},
            )

            assert response.status_code == 500
            data = response.json()
            assert "detail" in data


class TestPostgresPerformanceEndpoints:
    """Test PostgreSQL performance endpoints."""

    def test_get_slow_queries_endpoint(self, client, auth_headers):
        """Test /api/debug/postgres/performance/slow-queries endpoint."""
        with patch("app.utils.postgres_debugger.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_conn.fetchval = AsyncMock(return_value=True)  # extension exists
            mock_row = MagicMock()
            mock_row.__getitem__ = MagicMock(side_effect=lambda k: {"query": "SELECT * FROM users", "calls": 100, "total_exec_time": 5000.0, "mean_exec_time": 50.0, "max_exec_time": 200.0, "min_exec_time": 10.0, "stddev_exec_time": 20.0}[k])
            mock_row.keys = MagicMock(return_value=["query", "calls", "total_exec_time"])
            mock_conn.fetch = AsyncMock(return_value=[mock_row])
            mock_conn.close = AsyncMock()
            mock_connect.return_value = mock_conn

            response = client.get("/api/debug/postgres/performance/slow-queries?limit=10", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "queries" in data

    def test_get_locks_endpoint(self, client, auth_headers):
        """Test /api/debug/postgres/performance/locks endpoint."""
        with patch("app.utils.postgres_debugger.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_row = MagicMock()
            mock_row.__getitem__ = MagicMock(side_effect=lambda k: {"locktype": "relation", "relation": "users", "mode": "AccessShareLock", "granted": True, "pid": 12345, "usename": "testuser", "application_name": "testapp", "state": "active", "query_start": None, "state_change": None}[k])
            mock_row.keys = MagicMock(return_value=["locktype", "relation", "mode"])
            mock_conn.fetch = AsyncMock(return_value=[mock_row])
            mock_conn.close = AsyncMock()
            mock_connect.return_value = mock_conn

            response = client.get("/api/debug/postgres/performance/locks", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "locks" in data

    def test_get_connection_stats_endpoint(self, client, auth_headers):
        """Test /api/debug/postgres/performance/connections endpoint."""
        with patch("app.utils.postgres_debugger.asyncpg.connect") as mock_connect:
            mock_conn = AsyncMock()
            mock_state_row = MagicMock()
            mock_state_row.__getitem__ = MagicMock(side_effect=lambda k: {"state": "active", "count": 5}[k])
            mock_state_row.keys = MagicMock(return_value=["state", "count"])
            mock_conn.fetchval = AsyncMock(side_effect=[10, 2, 3])
            mock_conn.fetch = AsyncMock(return_value=[mock_state_row])
            mock_conn.close = AsyncMock()
            mock_connect.return_value = mock_conn

            response = client.get("/api/debug/postgres/performance/connections", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "stats" in data


class TestPostgresSecurity:
    """Test security features of PostgreSQL debug endpoints."""

    def test_all_endpoints_require_auth(self, client):
        """Test that all endpoints require authentication."""
        endpoints = [
            "/api/debug/postgres/connection",
            "/api/debug/postgres/schema/tables",
            "/api/debug/postgres/schema/table/users",
            "/api/debug/postgres/schema/indexes",
            "/api/debug/postgres/stats/tables",
            "/api/debug/postgres/stats/database",
            "/api/debug/postgres/performance/slow-queries",
            "/api/debug/postgres/performance/locks",
            "/api/debug/postgres/performance/connections",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 401, f"Endpoint {endpoint} should require auth"

    def test_query_endpoint_blocks_dml(self, client, auth_headers):
        """Test that query endpoint blocks DML operations."""
        dml_queries = [
            "INSERT INTO users VALUES (1, 'test')",
            "UPDATE users SET name = 'test'",
            "DELETE FROM users WHERE id = 1",
        ]

        for query in dml_queries:
            response = client.post(
                "/api/debug/postgres/query",
                headers=auth_headers,
                json={"query": query, "limit": 10},
            )
            assert response.status_code == 400, f"Query should be blocked: {query}"

    def test_query_endpoint_blocks_ddl(self, client, auth_headers):
        """Test that query endpoint blocks DDL operations."""
        ddl_queries = [
            "CREATE TABLE test (id INT)",
            "ALTER TABLE users ADD COLUMN test VARCHAR",
            "DROP TABLE users",
        ]

        for query in ddl_queries:
            response = client.post(
                "/api/debug/postgres/query",
                headers=auth_headers,
                json={"query": query, "limit": 10},
            )
            assert response.status_code == 400, f"Query should be blocked: {query}"

