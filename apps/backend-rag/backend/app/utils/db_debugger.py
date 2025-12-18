"""
Database Query Debugger
Logs PostgreSQL queries with timing and identifies performance issues
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Global query tracking
_query_log: list[dict[str, Any]] = []
_slow_queries: list[dict[str, Any]] = []
_query_patterns: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)

# Configuration
SLOW_QUERY_THRESHOLD_MS = 1000  # 1 second
MAX_QUERIES_TO_TRACK = 1000


@dataclass
class QueryTrace:
    """Trace for a single database query"""

    query: str
    params: tuple | None = None
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    duration_ms: float | None = None
    rows_returned: int | None = None
    error: str | None = None
    connection_id: str | None = None
    transaction_id: str | None = None

    def finish(self, rows_returned: int | None = None, error: str | None = None) -> None:
        """Mark query as finished."""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.rows_returned = rows_returned
        self.error = error


class DatabaseQueryDebugger:
    """
    Debugger for database queries.

    Usage:
        debugger = DatabaseQueryDebugger()
        with debugger.trace_query(query, params):
            result = await conn.fetch(query, *params)
    """

    def __init__(self, slow_query_threshold_ms: float = SLOW_QUERY_THRESHOLD_MS):
        """
        Initialize database query debugger.

        Args:
            slow_query_threshold_ms: Threshold for slow queries in milliseconds
        """
        self.slow_query_threshold_ms = slow_query_threshold_ms

    def trace_query(
        self,
        query: str,
        params: tuple | None = None,
        connection_id: str | None = None,
        transaction_id: str | None = None,
    ):
        """
        Context manager for tracing a database query.

        Args:
            query: SQL query string
            params: Query parameters
            connection_id: Optional connection ID
            transaction_id: Optional transaction ID

        Returns:
            Context manager for the query
        """
        return QueryTraceContext(
            query=query,
            params=params,
            connection_id=connection_id,
            transaction_id=transaction_id,
            slow_threshold=self.slow_query_threshold_ms,
        )

    @staticmethod
    def get_slow_queries(limit: int = 50) -> list[dict[str, Any]]:
        """
        Get slow queries.

        Args:
            limit: Maximum number of queries to return

        Returns:
            List of slow query traces
        """
        return _slow_queries[-limit:]

    @staticmethod
    def get_recent_queries(limit: int = 100) -> list[dict[str, Any]]:
        """
        Get recent queries.

        Args:
            limit: Maximum number of queries to return

        Returns:
            List of recent query traces
        """
        return _query_log[-limit:]

    @staticmethod
    def analyze_query_patterns() -> dict[str, Any]:
        """
        Analyze query patterns to identify potential issues.

        Returns:
            Analysis results
        """
        analysis: dict[str, Any] = {
            "n_plus_one_patterns": [],
            "missing_indexes": [],
            "slow_patterns": [],
        }

        # Group queries by pattern (simplified - first 50 chars)
        pattern_stats: dict[str, list[float]] = defaultdict(list)

        for query_trace in _query_log:
            pattern = query_trace["query"][:50]
            if query_trace["duration_ms"]:
                pattern_stats[pattern].append(query_trace["duration_ms"])

        # Find slow patterns
        for pattern, durations in pattern_stats.items():
            avg_duration = sum(durations) / len(durations)
            if avg_duration > SLOW_QUERY_THRESHOLD_MS:
                analysis["slow_patterns"].append(
                    {
                        "pattern": pattern,
                        "avg_duration_ms": avg_duration,
                        "count": len(durations),
                    }
                )

        return analysis

    @staticmethod
    def clear_logs() -> int:
        """
        Clear all query logs.

        Returns:
            Number of queries cleared
        """
        global _query_log, _slow_queries, _query_patterns
        count = len(_query_log)
        _query_log.clear()
        _slow_queries.clear()
        _query_patterns.clear()
        return count


class QueryTraceContext:
    """Context manager for tracing a single database query"""

    def __init__(
        self,
        query: str,
        params: tuple | None = None,
        connection_id: str | None = None,
        transaction_id: str | None = None,
        slow_threshold: float = SLOW_QUERY_THRESHOLD_MS,
    ):
        """
        Initialize query trace context.

        Args:
            query: SQL query string
            params: Query parameters
            connection_id: Optional connection ID
            transaction_id: Optional transaction ID
            slow_threshold: Slow query threshold in milliseconds
        """
        self.trace = QueryTrace(
            query=query,
            params=params,
            connection_id=connection_id,
            transaction_id=transaction_id,
        )
        self.slow_threshold = slow_threshold

    def __enter__(self):
        """Enter query context."""
        return self.trace

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit query context and log query."""
        global _query_log, _slow_queries

        error = str(exc_val) if exc_val else None
        rows_returned = getattr(self.trace, "rows_returned", None)
        self.trace.finish(rows_returned=rows_returned, error=error)

        # Log query
        query_dict = {
            "query": self.trace.query,
            "params": self.trace.params,
            "duration_ms": self.trace.duration_ms,
            "rows_returned": self.trace.rows_returned,
            "error": self.trace.error,
            "connection_id": self.trace.connection_id,
            "transaction_id": self.trace.transaction_id,
        }

        # Add to log
        _query_log.append(query_dict)

        # Track slow queries
        if self.trace.duration_ms and self.trace.duration_ms > self.slow_threshold:
            _slow_queries.append(query_dict)
            logger.warning(
                f"🐌 Slow query detected: {self.trace.duration_ms:.2f}ms - "
                f"{self.trace.query[:100]}"
            )

        # Limit log size
        if len(_query_log) > MAX_QUERIES_TO_TRACK:
            _query_log.pop(0)

        if len(_slow_queries) > MAX_QUERIES_TO_TRACK:
            _slow_queries.pop(0)

        return False  # Don't suppress exceptions

