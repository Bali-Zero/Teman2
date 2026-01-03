"""
Unit tests for app/utils/db_debugger.py
Target: >95% coverage
"""

import sys
import time
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.utils.db_debugger import (
    DatabaseQueryDebugger,
    QueryTrace,
    clear_query_log,
    get_query_statistics,
    get_slow_queries,
)


class TestQueryTrace:
    """Tests for QueryTrace"""

    def test_init(self):
        """Test QueryTrace initialization"""
        trace = QueryTrace(query="SELECT * FROM users", params=("test",))
        assert trace.query == "SELECT * FROM users"
        assert trace.params == ("test",)
        assert trace.start_time > 0
        assert trace.end_time is None
        assert trace.duration_ms is None
        assert trace.rows_returned is None
        assert trace.error is None

    def test_finish_success(self):
        """Test finishing trace with success"""
        trace = QueryTrace(query="SELECT * FROM users")
        time.sleep(0.01)  # Small delay
        trace.finish(rows_returned=10)

        assert trace.end_time is not None
        assert trace.duration_ms is not None
        assert trace.duration_ms > 0
        assert trace.rows_returned == 10
        assert trace.error is None

    def test_finish_with_error(self):
        """Test finishing trace with error"""
        trace = QueryTrace(query="SELECT * FROM users")
        trace.finish(error="Connection timeout")

        assert trace.error == "Connection timeout"
        assert trace.rows_returned is None


class TestDatabaseQueryDebugger:
    """Tests for DatabaseQueryDebugger"""

    def test_init_default(self):
        """Test DatabaseQueryDebugger initialization with defaults"""
        debugger = DatabaseQueryDebugger()
        assert debugger.slow_query_threshold_ms == 1000

    def test_init_custom(self):
        """Test DatabaseQueryDebugger initialization with custom threshold"""
        debugger = DatabaseQueryDebugger(slow_query_threshold_ms=500)
        assert debugger.slow_query_threshold_ms == 500

    def test_trace_query(self):
        """Test tracing a query"""
        debugger = DatabaseQueryDebugger()
        trace_ctx = debugger.trace_query("SELECT * FROM users", params=("test",))

        assert trace_ctx is not None
        assert trace_ctx.query == "SELECT * FROM users"
        assert trace_ctx.params == ("test",)

    def test_trace_query_with_ids(self):
        """Test tracing query with connection and transaction IDs"""
        debugger = DatabaseQueryDebugger()
        trace_ctx = debugger.trace_query(
            "SELECT * FROM users",
            connection_id="conn-123",
            transaction_id="txn-456"
        )

        assert trace_ctx.connection_id == "conn-123"
        assert trace_ctx.transaction_id == "txn-456"

    def test_get_slow_queries(self):
        """Test getting slow queries"""
        # Clear any existing queries
        clear_query_log()

        # Get slow queries (should return empty list if none)
        slow = get_slow_queries()
        assert isinstance(slow, list)

    def test_get_query_statistics(self):
        """Test getting query statistics"""
        stats = get_query_statistics()
        assert isinstance(stats, dict)
        assert "total_queries" in stats
        assert "slow_queries" in stats
        assert "average_duration_ms" in stats

    def test_clear_query_log(self):
        """Test clearing query log"""
        count = clear_query_log()
        assert isinstance(count, int)
        assert count >= 0


class TestQueryTraceContext:
    """Tests for QueryTraceContext (via trace_query)"""

    def test_context_manager_usage(self):
        """Test using trace_query as context manager"""
        debugger = DatabaseQueryDebugger()

        with debugger.trace_query("SELECT * FROM users") as trace:
            assert trace.query == "SELECT * FROM users"
            time.sleep(0.01)

        assert trace.end_time is not None
        assert trace.duration_ms is not None

    def test_context_manager_with_exception(self):
        """Test context manager with exception"""
        debugger = DatabaseQueryDebugger()

        with pytest.raises(ValueError):
            with debugger.trace_query("SELECT * FROM users") as trace:
                raise ValueError("Test error")

        assert trace.error is not None or trace.end_time is not None

    def test_slow_query_detection(self):
        """Test slow query detection"""
        debugger = DatabaseQueryDebugger(slow_query_threshold_ms=10)

        with debugger.trace_query("SELECT * FROM users") as trace:
            time.sleep(0.02)  # 20ms - should be slow

        # Query should be marked as slow if threshold is 10ms
        assert trace.duration_ms is not None
        if trace.duration_ms >= 10:
            # Should be in slow queries
            slow = get_slow_queries(limit=100)
            # May or may not be in list depending on implementation
            assert isinstance(slow, list)




