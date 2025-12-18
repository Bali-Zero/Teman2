"""
Unit tests for PostgreSQLDebugger utility.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.utils.postgres_debugger import (
    PostgreSQLDebugger,
    FORBIDDEN_KEYWORDS,
    MAX_ROWS_LIMIT,
    QUERY_TIMEOUT_SECONDS,
)


class TestPostgreSQLDebugger:
    """Test PostgreSQLDebugger class."""

    def test_init_with_database_url(self):
        """Test initialization with custom database URL."""
        debugger = PostgreSQLDebugger(database_url="postgresql://test:test@localhost/test")
        assert debugger.database_url == "postgresql://test:test@localhost/test"

    def test_init_without_database_url(self):
        """Test initialization uses settings.database_url by default."""
        with patch("app.utils.postgres_debugger.settings") as mock_settings:
            mock_settings.database_url = "postgresql://default:default@localhost/default"
            debugger = PostgreSQLDebugger()
            assert debugger.database_url == "postgresql://default:default@localhost/default"

    @pytest.mark.asyncio
    async def test_test_connection_success(self):
        """Test successful connection test."""
        debugger = PostgreSQLDebugger(database_url="postgresql://test:test@localhost/test")

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=["PostgreSQL 14.0", "testdb", "testuser"])
        mock_conn.close = AsyncMock()

        with patch("app.utils.postgres_debugger.asyncpg.connect", return_value=mock_conn):
            conn_info = await debugger.test_connection()

        assert conn_info.connected is True
        assert conn_info.version == "PostgreSQL 14.0"
        assert conn_info.database == "testdb"
        assert conn_info.user == "testuser"
        assert conn_info.error is None
        mock_conn.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_test_connection_failure(self):
        """Test connection test with failure."""
        debugger = PostgreSQLDebugger(database_url="postgresql://test:test@localhost/test")

        with patch(
            "app.utils.postgres_debugger.asyncpg.connect", side_effect=Exception("Connection failed")
        ):
            conn_info = await debugger.test_connection()

        assert conn_info.connected is False
        assert conn_info.error == "Connection failed"

    @pytest.mark.asyncio
    async def test_test_connection_with_pool(self):
        """Test connection test with pool."""
        debugger = PostgreSQLDebugger(database_url="postgresql://test:test@localhost/test")

        mock_pool = MagicMock()
        mock_pool.get_size = MagicMock(return_value=10)
        mock_pool.get_idle_size = MagicMock(return_value=5)
        mock_pool.acquire = MagicMock()

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=["PostgreSQL 14.0", "testdb", "testuser"])

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire.return_value = mock_cm

        conn_info = await debugger.test_connection(pool=mock_pool)

        assert conn_info.connected is True
        assert conn_info.pool_size == 10
        assert conn_info.pool_idle == 5
        assert conn_info.pool_active == 5

    def test_validate_query_select_allowed(self):
        """Test that SELECT queries are allowed."""
        debugger = PostgreSQLDebugger()
        is_valid, error = debugger.validate_query("SELECT * FROM users")
        assert is_valid is True
        assert error is None

    def test_validate_query_select_case_insensitive(self):
        """Test that SELECT queries are case-insensitive."""
        debugger = PostgreSQLDebugger()
        is_valid, error = debugger.validate_query("select * from users")
        assert is_valid is True
        assert error is None

    def test_validate_query_select_with_whitespace(self):
        """Test that SELECT queries with leading whitespace are allowed."""
        debugger = PostgreSQLDebugger()
        is_valid, error = debugger.validate_query("  SELECT * FROM users")
        assert is_valid is True
        assert error is None

    def test_validate_query_empty(self):
        """Test that empty queries are rejected."""
        debugger = PostgreSQLDebugger()
        is_valid, error = debugger.validate_query("")
        assert is_valid is False
        assert error == "Query is empty"

    def test_validate_query_whitespace_only(self):
        """Test that whitespace-only queries are rejected."""
        debugger = PostgreSQLDebugger()
        is_valid, error = debugger.validate_query("   ")
        assert is_valid is False
        assert error == "Query is empty"  # After strip(), whitespace-only becomes empty

    def test_validate_query_non_select_rejected(self):
        """Test that non-SELECT queries are rejected."""
        debugger = PostgreSQLDebugger()
        is_valid, error = debugger.validate_query("UPDATE users SET name = 'test'")
        assert is_valid is False
        assert error == "Only SELECT queries are allowed"

    def test_validate_query_forbidden_keywords(self):
        """Test that queries with forbidden keywords are rejected."""
        debugger = PostgreSQLDebugger()

        for keyword in FORBIDDEN_KEYWORDS:
            query = f"SELECT * FROM users; {keyword} TABLE users"
            is_valid, error = debugger.validate_query(query)
            assert is_valid is False, f"Keyword {keyword} should be rejected"
            assert keyword in error.upper() or "forbidden" in error.lower()

    def test_validate_query_multiple_statements_rejected(self):
        """Test that queries with multiple statements are rejected."""
        debugger = PostgreSQLDebugger()
        # Use a query that has multiple semicolons (more than 1)
        is_valid, error = debugger.validate_query("SELECT * FROM users; SELECT * FROM posts; SELECT * FROM comments")
        assert is_valid is False
        assert "Multiple statements" in error or "forbidden" in error.lower()

    def test_validate_query_select_with_semicolon_allowed(self):
        """Test that SELECT queries ending with semicolon are allowed."""
        debugger = PostgreSQLDebugger()
        is_valid, error = debugger.validate_query("SELECT * FROM users;")
        assert is_valid is True
        assert error is None

    @pytest.mark.asyncio
    async def test_execute_query_success(self):
        """Test successful query execution."""
        debugger = PostgreSQLDebugger(database_url="postgresql://test:test@localhost/test")

        # Create proper mock descriptors with name attribute
        mock_desc_id = MagicMock()
        mock_desc_id.name = "id"
        mock_desc_name = MagicMock()
        mock_desc_name.name = "name"

        mock_row1 = MagicMock()
        mock_row1._row_desc = [mock_desc_id, mock_desc_name]
        mock_row1.__getitem__ = MagicMock(side_effect=lambda k: {"id": 1, "name": "test"}[k])
        mock_row1.keys = MagicMock(return_value=["id", "name"])

        mock_row2 = MagicMock()
        mock_row2._row_desc = [mock_desc_id, mock_desc_name]
        mock_row2.__getitem__ = MagicMock(side_effect=lambda k: {"id": 2, "name": "test2"}[k])
        mock_row2.keys = MagicMock(return_value=["id", "name"])

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[mock_row1, mock_row2])
        mock_conn.close = AsyncMock()

        with patch("app.utils.postgres_debugger.asyncpg.connect", return_value=mock_conn):
            result = await debugger.execute_query("SELECT * FROM users", limit=10)

        assert result["success"] is True
        assert result["row_count"] == 2
        assert len(result["rows"]) == 2
        assert result["columns"] == ["id", "name"]
        mock_conn.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_query_with_limit(self):
        """Test query execution respects limit."""
        debugger = PostgreSQLDebugger(database_url="postgresql://test:test@localhost/test")

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.close = AsyncMock()

        with patch("app.utils.postgres_debugger.asyncpg.connect", return_value=mock_conn):
            await debugger.execute_query("SELECT * FROM users", limit=50)

        # Verify LIMIT was added to query
        call_args = mock_conn.fetch.call_args
        assert "LIMIT 50" in call_args[0][0].upper()

    @pytest.mark.asyncio
    async def test_execute_query_limit_enforced(self):
        """Test that limit is enforced to MAX_ROWS_LIMIT."""
        debugger = PostgreSQLDebugger(database_url="postgresql://test:test@localhost/test")

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.close = AsyncMock()

        with patch("app.utils.postgres_debugger.asyncpg.connect", return_value=mock_conn):
            await debugger.execute_query("SELECT * FROM users", limit=5000)

        # Verify LIMIT was capped at MAX_ROWS_LIMIT
        call_args = mock_conn.fetch.call_args
        assert f"LIMIT {MAX_ROWS_LIMIT}" in call_args[0][0].upper()

    @pytest.mark.asyncio
    async def test_execute_query_invalid_query(self):
        """Test that invalid queries raise ValueError."""
        debugger = PostgreSQLDebugger(database_url="postgresql://test:test@localhost/test")

        with pytest.raises(ValueError, match="Only SELECT queries are allowed"):
            await debugger.execute_query("UPDATE users SET name = 'test'")

    @pytest.mark.asyncio
    async def test_execute_query_with_pool(self):
        """Test query execution using pool."""
        debugger = PostgreSQLDebugger(database_url="postgresql://test:test@localhost/test")

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire.return_value = mock_cm

        result = await debugger.execute_query("SELECT * FROM users", pool=mock_pool)

        assert result["success"] is True
        mock_pool.acquire.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_tables(self):
        """Test getting list of tables."""
        debugger = PostgreSQLDebugger(database_url="postgresql://test:test@localhost/test")

        mock_row1 = MagicMock()
        mock_row1.__getitem__ = MagicMock(side_effect=lambda k: {"table_name": "users", "table_type": "BASE TABLE"}[k])
        mock_row1.keys = MagicMock(return_value=["table_name", "table_type"])

        mock_row2 = MagicMock()
        mock_row2.__getitem__ = MagicMock(side_effect=lambda k: {"table_name": "posts", "table_type": "BASE TABLE"}[k])
        mock_row2.keys = MagicMock(return_value=["table_name", "table_type"])

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[mock_row1, mock_row2])
        mock_conn.close = AsyncMock()

        with patch("app.utils.postgres_debugger.asyncpg.connect", return_value=mock_conn):
            tables = await debugger.get_tables(schema="public")

        assert len(tables) == 2
        assert tables[0]["name"] == "users"
        assert tables[1]["name"] == "posts"
        mock_conn.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_table_details(self):
        """Test getting table details."""
        debugger = PostgreSQLDebugger(database_url="postgresql://test:test@localhost/test")

        # Mock columns
        mock_col_row = MagicMock()
        mock_col_row.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "column_name": "id",
                "data_type": "integer",
                "is_nullable": "NO",
                "column_default": None,
                "character_maximum_length": None,
                "numeric_precision": None,
                "numeric_scale": None,
            }[k]
        )
        mock_col_row.keys = MagicMock(return_value=["column_name", "data_type", "is_nullable", "column_default"])

        # Mock indexes (empty)
        mock_idx_row = MagicMock()
        mock_idx_row.__getitem__ = MagicMock(side_effect=lambda k: {"indexname": None, "indexdef": None, "column_name": None}[k])
        mock_idx_row.keys = MagicMock(return_value=["indexname", "indexdef", "column_name"])

        # Mock foreign keys (empty)
        mock_fk_row = MagicMock()
        mock_fk_row.__getitem__ = MagicMock(side_effect=lambda k: {"constraint_name": None, "column_name": None, "foreign_table_name": None, "foreign_column_name": None}[k])
        mock_fk_row.keys = MagicMock(return_value=["constraint_name", "column_name", "foreign_table_name", "foreign_column_name"])

        # Mock constraints (empty)
        mock_constraint_row = MagicMock()
        mock_constraint_row.__getitem__ = MagicMock(side_effect=lambda k: {"constraint_name": None, "constraint_type": None}[k])
        mock_constraint_row.keys = MagicMock(return_value=["constraint_name", "constraint_type"])

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(
            side_effect=[
                [mock_col_row],  # columns
                [],  # indexes
                [],  # foreign keys
                [],  # constraints
            ]
        )
        mock_conn.close = AsyncMock()

        with patch("app.utils.postgres_debugger.asyncpg.connect", return_value=mock_conn):
            table_info = await debugger.get_table_details(table_name="users", schema="public")

        assert table_info.schema == "public"
        assert table_info.name == "users"
        assert len(table_info.columns) == 1
        assert table_info.columns[0]["name"] == "id"
        mock_conn.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_indexes(self):
        """Test getting indexes."""
        debugger = PostgreSQLDebugger(database_url="postgresql://test:test@localhost/test")

        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "schemaname": "public",
                "tablename": "users",
                "indexname": "idx_users_email",
                "indexdef": "CREATE INDEX idx_users_email ON users(email)",
            }[k]
        )
        mock_row.keys = MagicMock(return_value=["schemaname", "tablename", "indexname", "indexdef"])

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[mock_row])
        mock_conn.close = AsyncMock()

        with patch("app.utils.postgres_debugger.asyncpg.connect", return_value=mock_conn):
            indexes = await debugger.get_indexes()

        assert len(indexes) == 1
        assert indexes[0]["name"] == "idx_users_email"
        mock_conn.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_table_stats(self):
        """Test getting table statistics."""
        debugger = PostgreSQLDebugger(database_url="postgresql://test:test@localhost/test")

        mock_stat_row = MagicMock()
        mock_stat_row.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "schemaname": "public",
                "tablename": "users",
                "total_size": "1 MB",
                "table_size": "800 kB",
                "indexes_size": "200 kB",
                "index_count": 2,
            }[k]
        )
        mock_stat_row.keys = MagicMock(return_value=["schemaname", "tablename", "total_size", "table_size", "indexes_size", "index_count"])

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[mock_stat_row])
        mock_conn.fetchval = AsyncMock(return_value=100)  # row count
        mock_conn.close = AsyncMock()

        with patch("app.utils.postgres_debugger.asyncpg.connect", return_value=mock_conn):
            stats = await debugger.get_table_stats()

        assert len(stats) == 1
        assert stats[0]["table"] == "users"
        assert stats[0]["row_count"] == 100
        mock_conn.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_database_stats(self):
        """Test getting database statistics."""
        debugger = PostgreSQLDebugger(database_url="postgresql://test:test@localhost/test")

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(
            side_effect=[
                "100 MB",  # db_size
                "PostgreSQL 14.0",  # version
                10,  # conn_count
                5,  # active_conn
                5,  # idle_conn
                "testdb",  # db_name
            ]
        )
        mock_conn.close = AsyncMock()

        with patch("app.utils.postgres_debugger.asyncpg.connect", return_value=mock_conn):
            stats = await debugger.get_database_stats()

        assert stats["database"] == "testdb"
        assert stats["version"] == "PostgreSQL 14.0"
        assert stats["size"] == "100 MB"
        assert stats["total_connections"] == 10
        assert stats["active_connections"] == 5
        assert stats["idle_connections"] == 5
        mock_conn.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_slow_queries_no_extension(self):
        """Test getting slow queries when extension is not available."""
        debugger = PostgreSQLDebugger(database_url="postgresql://test:test@localhost/test")

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=False)  # extension not exists
        mock_conn.close = AsyncMock()

        with patch("app.utils.postgres_debugger.asyncpg.connect", return_value=mock_conn):
            queries = await debugger.get_slow_queries()

        assert queries == []
        mock_conn.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_slow_queries_with_extension(self):
        """Test getting slow queries when extension is available."""
        debugger = PostgreSQLDebugger(database_url="postgresql://test:test@localhost/test")

        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "query": "SELECT * FROM users",
                "calls": 100,
                "total_exec_time": 5000.0,
                "mean_exec_time": 50.0,
                "max_exec_time": 200.0,
                "min_exec_time": 10.0,
                "stddev_exec_time": 20.0,
            }[k]
        )
        mock_row.keys = MagicMock(return_value=["query", "calls", "total_exec_time", "mean_exec_time", "max_exec_time", "min_exec_time", "stddev_exec_time"])

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=True)  # extension exists
        mock_conn.fetch = AsyncMock(return_value=[mock_row])
        mock_conn.close = AsyncMock()

        with patch("app.utils.postgres_debugger.asyncpg.connect", return_value=mock_conn):
            queries = await debugger.get_slow_queries(limit=10)

        assert len(queries) == 1
        assert queries[0]["query"] == "SELECT * FROM users"
        assert queries[0]["calls"] == 100
        mock_conn.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_active_locks(self):
        """Test getting active locks."""
        debugger = PostgreSQLDebugger(database_url="postgresql://test:test@localhost/test")

        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(
            side_effect=lambda k: {
                "locktype": "relation",
                "relation": "users",
                "mode": "AccessShareLock",
                "granted": True,
                "pid": 12345,
                "usename": "testuser",
                "application_name": "testapp",
                "state": "active",
                "query_start": None,
                "state_change": None,
            }[k]
        )
        mock_row.keys = MagicMock(return_value=["locktype", "relation", "mode", "granted", "pid", "usename", "application_name", "state", "query_start", "state_change"])

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[mock_row])
        mock_conn.close = AsyncMock()

        with patch("app.utils.postgres_debugger.asyncpg.connect", return_value=mock_conn):
            locks = await debugger.get_active_locks()

        assert len(locks) == 1
        assert locks[0]["lock_type"] == "relation"
        assert locks[0]["relation"] == "users"
        mock_conn.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_connection_stats(self):
        """Test getting connection statistics."""
        debugger = PostgreSQLDebugger(database_url="postgresql://test:test@localhost/test")

        mock_state_row = MagicMock()
        mock_state_row.__getitem__ = MagicMock(side_effect=lambda k: {"state": "active", "count": 5}[k])
        mock_state_row.keys = MagicMock(return_value=["state", "count"])

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=[10, 2, 3])  # total, long_running, idle_in_transaction
        mock_conn.fetch = AsyncMock(return_value=[mock_state_row])
        mock_conn.close = AsyncMock()

        with patch("app.utils.postgres_debugger.asyncpg.connect", return_value=mock_conn):
            stats = await debugger.get_connection_stats()

        assert stats["total"] == 10
        assert stats["long_running_queries"] == 2
        assert stats["idle_in_transaction"] == 3
        assert "by_state" in stats
        mock_conn.close.assert_called_once()

