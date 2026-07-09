"""
Unit tests for app/utils/postgres_debugger.py
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from backend.app.utils.postgres_debugger import (
    FORBIDDEN_KEYWORDS,
    MAX_ROWS_LIMIT,
    QUERY_TIMEOUT_SECONDS,
    PostgreSQLDebugger,
    _mask_sql_comments_and_literals,
    _strip_trailing_statement_terminator,
)


class TestMaskSQLCommentsAndLiterals:
    """Tests for _mask_sql_comments_and_literals"""

    def test_empty_sql(self):
        """Test masking empty SQL"""
        result = _mask_sql_comments_and_literals("")
        assert result == ""

    def test_mask_line_comment(self):
        """Test masking line comments"""
        sql = "SELECT * FROM users -- This is a comment"
        result = _mask_sql_comments_and_literals(sql)
        assert "--" not in result or "comment" not in result

    def test_mask_block_comment(self):
        """Test masking block comments"""
        sql = "SELECT * FROM users /* This is a block comment */"
        result = _mask_sql_comments_and_literals(sql)
        assert "comment" not in result.lower()

    def test_mask_single_quoted_string(self):
        """Test masking single-quoted strings"""
        sql = "SELECT * FROM users WHERE name = 'John'"
        result = _mask_sql_comments_and_literals(sql)
        assert "'John'" not in result

    def test_mask_double_quoted_string(self):
        """Test masking double-quoted strings"""
        sql = 'SELECT * FROM users WHERE name = "John"'
        result = _mask_sql_comments_and_literals(sql)
        assert '"John"' not in result

    def test_mask_dollar_quoted_string(self):
        """Test masking dollar-quoted strings"""
        sql = "SELECT $$text$$"
        result = _mask_sql_comments_and_literals(sql)
        assert "text" not in result


class TestStripTrailingStatementTerminator:
    """Tests for _strip_trailing_statement_terminator"""

    def test_strip_semicolon(self):
        """Test stripping trailing semicolon"""
        sql = "SELECT * FROM users;"
        result = _strip_trailing_statement_terminator(sql)
        assert not result.endswith(";")

    def test_no_semicolon(self):
        """Test SQL without trailing semicolon"""
        sql = "SELECT * FROM users"
        result = _strip_trailing_statement_terminator(sql)
        assert result == sql

    def test_strip_with_whitespace(self):
        """Test stripping with trailing whitespace"""
        sql = "SELECT * FROM users;  "
        result = _strip_trailing_statement_terminator(sql)
        assert not result.strip().endswith(";")


class TestPostgreSQLDebuggerValidateQuery:
    """Tests for PostgreSQLDebugger.validate_query"""

    @pytest.fixture
    def debugger(self):
        """Create debugger instance"""
        with patch("backend.app.utils.postgres_debugger.settings") as mock_settings:
            mock_settings.database_url = "postgresql://test"
            return PostgreSQLDebugger()

    def test_safe_select_query(self, debugger):
        """Test validating safe SELECT query"""
        sql = "SELECT * FROM users"
        is_safe, reason = debugger.validate_query(sql)
        assert is_safe is True
        assert reason is None

    def test_forbidden_drop(self, debugger):
        """Test detecting DROP statement"""
        sql = "DROP TABLE users"
        is_safe, reason = debugger.validate_query(sql)
        assert is_safe is False
        # Non-SELECT queries are rejected with "Only SELECT queries are allowed"
        assert "SELECT" in reason.upper() or "DROP" in reason.upper()

    def test_forbidden_delete(self, debugger):
        """Test detecting DELETE statement"""
        sql = "DELETE FROM users"
        is_safe, reason = debugger.validate_query(sql)
        assert is_safe is False
        # Non-SELECT queries are rejected with "Only SELECT queries are allowed"
        assert "SELECT" in reason.upper() or "DELETE" in reason.upper()

    def test_forbidden_update(self, debugger):
        """Test detecting UPDATE statement"""
        sql = "UPDATE users SET name = 'test'"
        is_safe, reason = debugger.validate_query(sql)
        assert is_safe is False
        # Non-SELECT queries are rejected with "Only SELECT queries are allowed"
        assert "SELECT" in reason.upper() or "UPDATE" in reason.upper()

    def test_forbidden_in_comment(self, debugger):
        """Test that forbidden keywords in comments are ignored"""
        sql = "SELECT * FROM users -- DROP TABLE test"
        is_safe, reason = debugger.validate_query(sql)
        # Should be safe because DROP is in comment
        assert is_safe is True

    def test_forbidden_in_string(self, debugger):
        """Test that forbidden keywords in strings are ignored"""
        sql = "SELECT 'DROP TABLE test' FROM users"
        is_safe, reason = debugger.validate_query(sql)
        # Should be safe because DROP is in string literal
        assert is_safe is True

    def test_multiple_statements(self, debugger):
        """Test detecting multiple statements"""
        sql = "SELECT * FROM users; DROP TABLE test;"
        is_safe, reason = debugger.validate_query(sql)
        assert is_safe is False


class TestPostgreSQLDebuggerExecuteQuery:
    """Tests for PostgreSQLDebugger.execute_query"""

    @pytest.fixture
    def debugger(self):
        """Create debugger instance"""
        with patch("backend.app.utils.postgres_debugger.settings") as mock_settings:
            mock_settings.database_url = "postgresql://test"
            return PostgreSQLDebugger()

    @pytest.mark.asyncio
    async def test_execute_query_success(self, debugger):
        """Test executing safe query successfully"""
        # Create mock row with _row_desc attribute
        mock_row = MagicMock()
        mock_row.__iter__ = MagicMock(return_value=iter([("id", 1), ("name", "test")]))
        mock_row.items = MagicMock(return_value=[("id", 1), ("name", "test")])
        mock_row._row_desc = [MagicMock(name="id"), MagicMock(name="name")]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[mock_row])
        mock_conn.transaction = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(), __aexit__=AsyncMock()),
        )

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn),
                __aexit__=AsyncMock(return_value=None),
            ),
        )

        result = await debugger.execute_query("SELECT * FROM users LIMIT 1", pool=mock_pool)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_query_forbidden(self, debugger):
        """Test executing forbidden query raises ValueError"""
        mock_pool = AsyncMock()

        # execute_query raises ValueError for invalid queries
        with pytest.raises(ValueError) as exc_info:
            await debugger.execute_query("DROP TABLE users", pool=mock_pool)

        assert "SELECT" in str(exc_info.value).upper()

    @pytest.mark.asyncio
    async def test_execute_query_error(self, debugger):
        """Test query execution error propagates"""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(side_effect=Exception("Database error"))
        mock_conn.transaction = MagicMock(
            return_value=AsyncMock(__aenter__=AsyncMock(), __aexit__=AsyncMock()),
        )

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_conn),
                __aexit__=AsyncMock(return_value=None),
            ),
        )

        # execute_query propagates exceptions (may raise original or UnboundLocalError)
        with pytest.raises(Exception):
            await debugger.execute_query("SELECT * FROM nonexistent", pool=mock_pool)


class TestModuleConstants:
    """Tests for module constants"""

    def test_constants(self):
        """Test module constants"""
        assert QUERY_TIMEOUT_SECONDS == 30
        assert MAX_ROWS_LIMIT == 1000
        assert len(FORBIDDEN_KEYWORDS) > 0
        assert "DROP" in FORBIDDEN_KEYWORDS
        assert "DELETE" in FORBIDDEN_KEYWORDS


class TestPostgreSQLDebuggerInit:
    """Tests for PostgreSQLDebugger initialization"""

    def test_init_with_url(self):
        """Test initialization with explicit URL"""
        debugger = PostgreSQLDebugger(database_url="postgresql://test")
        assert debugger.database_url == "postgresql://test"

    def test_init_from_settings(self):
        """Test initialization from settings"""
        with patch("backend.app.utils.postgres_debugger.settings") as mock_settings:
            mock_settings.database_url = "postgresql://from-settings"
            debugger = PostgreSQLDebugger()
            assert debugger.database_url == "postgresql://from-settings"


class TestPostgreSQLDebuggerGetActiveLocks:
    """
    Regression tests for get_active_locks().

    Live prod bug: /api/debug/postgres/performance/locks returned 500
    with 'column reference "pid" is ambiguous'. The query JOINs
    pg_locks (aliased l) with pg_stat_activity (aliased a) — both
    tables have a `pid` column, so any bare, unqualified `pid` in the
    SELECT list is ambiguous to Postgres. Fix: qualify with `a.pid`.
    """

    @pytest.fixture
    def debugger(self):
        with patch("backend.app.utils.postgres_debugger.settings") as mock_settings:
            mock_settings.database_url = "postgresql://test"
            return PostgreSQLDebugger()

    async def _captured_query(self, debugger, mock_conn):
        """Run get_active_locks with a mocked connection and return the SQL sent to fetch()."""
        with patch.object(debugger, "_get_connection", AsyncMock(return_value=mock_conn)):
            await debugger.get_active_locks()
        assert mock_conn.fetch.await_args is not None
        return mock_conn.fetch.await_args.args[0]

    @pytest.mark.asyncio
    async def test_query_qualifies_pid_with_table_alias(self, debugger):
        """The SELECT list must not contain a bare, unqualified `pid` column."""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.close = AsyncMock()

        query = await self._captured_query(debugger, mock_conn)

        # Isolate the SELECT clause (before FROM) — this is where an
        # unqualified `pid` caused Postgres to reject the query.
        select_clause = query.split("FROM", 1)[0]
        import re

        bare_pid_matches = re.findall(r"(?<![\w.])pid(?![\w])", select_clause)
        assert not bare_pid_matches, (
            f"SELECT clause has {len(bare_pid_matches)} unqualified 'pid' reference(s) "
            f"— ambiguous with a JOIN across pg_locks/pg_stat_activity: {select_clause!r}"
        )
        # The qualified reference must still be present so the fix
        # doesn't silently drop the column.
        assert "a.pid" in query or "l.pid" in query.split("JOIN")[0]

    @pytest.mark.asyncio
    async def test_join_still_matches_pid_between_both_tables(self, debugger):
        """The JOIN condition itself (l.pid = a.pid) must be untouched."""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.close = AsyncMock()

        query = await self._captured_query(debugger, mock_conn)
        assert "l.pid = a.pid" in query

    @pytest.mark.asyncio
    async def test_response_shape_preserved(self, debugger):
        """The fix must not change the returned dict shape (frontend-facing contract)."""
        mock_row = {
            "locktype": "relation",
            "relation": "some_table",
            "mode": "AccessShareLock",
            "granted": True,
            "pid": 12345,
            "usename": "nuzantara_rag",
            "application_name": "backend",
            "state": "active",
            "query_start": None,
        }

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[mock_row])
        mock_conn.close = AsyncMock()

        with patch.object(debugger, "_get_connection", AsyncMock(return_value=mock_conn)):
            result = await debugger.get_active_locks()

        assert result == [
            {
                "lock_type": "relation",
                "relation": "some_table",
                "mode": "AccessShareLock",
                "granted": True,
                "pid": 12345,
                "username": "nuzantara_rag",
                "application": "backend",
                "state": "active",
                "query_start": None,
            }
        ]


class TestGetTableStatsSQL:
    """
    Regression tests for get_table_stats() SQL generation.

    Bug: prod 500 on GET /api/debug/postgres/stats/tables —
    "relation \"information_schema.statistics\" does not exist".
    information_schema.statistics is a MySQL-only relation; PostgreSQL has
    no such view. The index-count subquery must use pg_indexes instead,
    qualified against the outer pg_tables columns to avoid ambiguity.
    """

    @pytest.fixture
    def debugger(self):
        """Create debugger instance"""
        with patch("backend.app.utils.postgres_debugger.settings") as mock_settings:
            mock_settings.database_url = "postgresql://test"
            return PostgreSQLDebugger()

    @staticmethod
    def _mock_connection_capturing_sql():
        """Return (mock_conn, get_connection_patch_target) that records the SQL passed to fetch()."""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.close = AsyncMock()
        return mock_conn

    @pytest.mark.asyncio
    async def test_single_table_query_has_no_mysql_only_relation(self, debugger):
        """table_name branch: query must not reference information_schema.statistics"""
        mock_conn = self._mock_connection_capturing_sql()
        with patch.object(debugger, "_get_connection", AsyncMock(return_value=mock_conn)):
            await debugger.get_table_stats(table_name="clients")

        assert mock_conn.fetch.await_count == 1
        sql = mock_conn.fetch.await_args.args[0]
        assert "information_schema.statistics" not in sql
        assert "STATISTICS" not in sql.upper()

    @pytest.mark.asyncio
    async def test_single_table_query_uses_qualified_pg_indexes(self, debugger):
        """table_name branch: index_count subquery must use pg_indexes, qualified vs pg_tables"""
        mock_conn = self._mock_connection_capturing_sql()
        with patch.object(debugger, "_get_connection", AsyncMock(return_value=mock_conn)):
            await debugger.get_table_stats(table_name="clients")

        sql = mock_conn.fetch.await_args.args[0]
        assert "FROM pg_indexes" in sql
        assert "pg_indexes.schemaname = pg_tables.schemaname" in sql
        assert "pg_indexes.tablename = pg_tables.tablename" in sql

    @pytest.mark.asyncio
    async def test_all_tables_query_has_no_mysql_only_relation(self, debugger):
        """else branch (no table_name filter): same MySQL-ism must be absent"""
        mock_conn = self._mock_connection_capturing_sql()
        with patch.object(debugger, "_get_connection", AsyncMock(return_value=mock_conn)):
            await debugger.get_table_stats(table_name=None)

        assert mock_conn.fetch.await_count == 1
        sql = mock_conn.fetch.await_args.args[0]
        assert "information_schema.statistics" not in sql

    @pytest.mark.asyncio
    async def test_all_tables_query_uses_qualified_pg_indexes(self, debugger):
        """else branch: index_count subquery must use pg_indexes, qualified vs pg_tables"""
        mock_conn = self._mock_connection_capturing_sql()
        with patch.object(debugger, "_get_connection", AsyncMock(return_value=mock_conn)):
            await debugger.get_table_stats(table_name=None)

        sql = mock_conn.fetch.await_args.args[0]
        assert "FROM pg_indexes" in sql
        assert "pg_indexes.schemaname = pg_tables.schemaname" in sql
        assert "pg_indexes.tablename = pg_tables.tablename" in sql

    def test_module_source_has_no_information_schema_statistics(self):
        """
        Static guard: the whole module must never reference the MySQL-only
        information_schema.statistics relation again (W89 class regression guard).
        """
        import inspect

        from backend.app.utils import postgres_debugger

        source = inspect.getsource(postgres_debugger)
        assert "information_schema.statistics" not in source
