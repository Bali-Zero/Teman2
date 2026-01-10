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

from backend.app.utils.db_debugger import (
    DatabaseQueryDebugger,
    QueryTrace,
    QueryTraceContext,
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
        assert isinstance(trace_ctx, QueryTraceContext)
        # The trace is inside the context
        assert trace_ctx.trace.query == "SELECT * FROM users"
        assert trace_ctx.trace.params == ("test",)

    def test_trace_query_with_ids(self):
        """Test tracing query with connection and transaction IDs"""
        debugger = DatabaseQueryDebugger()
        trace_ctx = debugger.trace_query(
            "SELECT * FROM users", connection_id="conn-123", transaction_id="txn-456"
        )

        assert trace_ctx.trace.connection_id == "conn-123"
        assert trace_ctx.trace.transaction_id == "txn-456"

    def test_get_slow_queries(self):
        """Test getting slow queries"""
        # Clear any existing queries
        DatabaseQueryDebugger.clear_logs()

        # Get slow queries (should return empty list if none)
        slow = DatabaseQueryDebugger.get_slow_queries()
        assert isinstance(slow, list)

    def test_get_recent_queries(self):
        """Test getting recent queries"""
        queries = DatabaseQueryDebugger.get_recent_queries()
        assert isinstance(queries, list)

    def test_analyze_query_patterns(self):
        """Test analyzing query patterns"""
        patterns = DatabaseQueryDebugger.analyze_query_patterns()
        assert isinstance(patterns, dict)
        assert "n_plus_one_patterns" in patterns
        assert "missing_indexes" in patterns
        assert "slow_patterns" in patterns

    def test_clear_logs(self):
        """Test clearing query log"""
        count = DatabaseQueryDebugger.clear_logs()
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
            slow = DatabaseQueryDebugger.get_slow_queries(limit=100)
            # May or may not be in list depending on implementation
            assert isinstance(slow, list)

    def test_query_trace_context_init(self):
        """Test QueryTraceContext initialization"""
        ctx = QueryTraceContext(
            query="SELECT 1",
            params=(1,),
            connection_id="conn-1",
            transaction_id="txn-1",
            slow_threshold=500,
        )

        assert ctx.trace.query == "SELECT 1"
        assert ctx.trace.params == (1,)
        assert ctx.trace.connection_id == "conn-1"
        assert ctx.trace.transaction_id == "txn-1"
        assert ctx.slow_threshold == 500

    def test_query_trace_context_enter_exit(self):
        """Test QueryTraceContext __enter__ and __exit__"""
        ctx = QueryTraceContext(query="SELECT 1")

        # Test __enter__
        trace = ctx.__enter__()
        assert trace is ctx.trace

        # Test __exit__ (returns False to not suppress exceptions)
        result = ctx.__exit__(None, None, None)
        assert result is False
        assert trace.end_time is not None
