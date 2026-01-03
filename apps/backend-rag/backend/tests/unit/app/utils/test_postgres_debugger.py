"""
Unit tests for app/utils/postgres_debugger.py
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.utils.postgres_debugger import (
    FORBIDDEN_KEYWORDS,
    MAX_ROWS_LIMIT,
    QUERY_TIMEOUT_SECONDS,
    _mask_sql_comments_and_literals,
    execute_safe_query,
    validate_query_safety,
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


class TestValidateQuerySafety:
    """Tests for validate_query_safety"""

    def test_safe_select_query(self):
        """Test validating safe SELECT query"""
        sql = "SELECT * FROM users"
        is_safe, reason = validate_query_safety(sql)
        assert is_safe is True
        assert reason is None

    def test_forbidden_drop(self):
        """Test detecting DROP statement"""
        sql = "DROP TABLE users"
        is_safe, reason = validate_query_safety(sql)
        assert is_safe is False
        assert "DROP" in reason.upper()

    def test_forbidden_delete(self):
        """Test detecting DELETE statement"""
        sql = "DELETE FROM users"
        is_safe, reason = validate_query_safety(sql)
        assert is_safe is False
        assert "DELETE" in reason.upper()

    def test_forbidden_update(self):
        """Test detecting UPDATE statement"""
        sql = "UPDATE users SET name = 'test'"
        is_safe, reason = validate_query_safety(sql)
        assert is_safe is False
        assert "UPDATE" in reason.upper()

    def test_forbidden_in_comment(self):
        """Test that forbidden keywords in comments are ignored"""
        sql = "SELECT * FROM users -- DROP TABLE test"
        is_safe, reason = validate_query_safety(sql)
        # Should be safe because DROP is in comment
        assert is_safe is True

    def test_forbidden_in_string(self):
        """Test that forbidden keywords in strings are ignored"""
        sql = "SELECT 'DROP TABLE test' FROM users"
        is_safe, reason = validate_query_safety(sql)
        # Should be safe because DROP is in string literal
        assert is_safe is True

    def test_multiple_statements(self):
        """Test detecting multiple statements"""
        sql = "SELECT * FROM users; DROP TABLE test;"
        is_safe, reason = validate_query_safety(sql)
        assert is_safe is False


class TestExecuteSafeQuery:
    """Tests for execute_safe_query"""

    @pytest.mark.asyncio
    async def test_execute_safe_query_success(self):
        """Test executing safe query successfully"""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[{"id": 1, "name": "test"}])

        result = await execute_safe_query(mock_conn, "SELECT * FROM users LIMIT 1")

        assert result["success"] is True
        assert len(result["rows"]) == 1

    @pytest.mark.asyncio
    async def test_execute_safe_query_forbidden(self):
        """Test executing forbidden query"""
        mock_conn = AsyncMock()

        result = await execute_safe_query(mock_conn, "DROP TABLE users")

        assert result["success"] is False
        assert "forbidden" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_execute_safe_query_timeout(self):
        """Test query timeout"""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(side_effect=TimeoutError("Query timeout"))

        result = await execute_safe_query(mock_conn, "SELECT * FROM users")

        assert result["success"] is False
        assert "timeout" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_execute_safe_query_error(self):
        """Test query execution error"""
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(side_effect=Exception("Database error"))

        result = await execute_safe_query(mock_conn, "SELECT * FROM nonexistent")

        assert result["success"] is False
        assert "error" in result

    def test_constants(self):
        """Test module constants"""
        assert QUERY_TIMEOUT_SECONDS == 30
        assert MAX_ROWS_LIMIT == 1000
        assert len(FORBIDDEN_KEYWORDS) > 0
        assert "DROP" in FORBIDDEN_KEYWORDS
        assert "DELETE" in FORBIDDEN_KEYWORDS




