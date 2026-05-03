"""
Dynamic SQL Query Builder for asyncpg
Extracts the repeated WHERE clause + pagination pattern from routers.

Used by: crm_clients, crm_interactions, crm_practices, admin_logs,
         admin_team_activity, conversations, newsletter, news, whatsapp_conversations

Pattern replaced:
    conditions = []
    params = []
    param_count = 0
    if filter_value:
        param_count += 1
        conditions.append(f"field = ${param_count}")
        params.append(filter_value)
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class QueryResult:
    """Result of building a query with dynamic conditions."""

    where_clause: str
    params: list[Any]
    param_count: int

    def limit_offset_clause(self, limit: int, offset: int) -> str:
        """
        Append LIMIT/OFFSET to the query using the next param positions.

        Returns:
            SQL fragment like "LIMIT $3 OFFSET $4"
        """
        self.params.extend([limit, offset])
        limit_pos = self.param_count + 1
        offset_pos = self.param_count + 2
        self.param_count += 2
        return f"LIMIT ${limit_pos} OFFSET ${offset_pos}"

    def count_query(self, table: str, joins: str = "") -> str:
        """
        Build a SELECT COUNT(*) query for pagination totals.

        Args:
            table: Table name (e.g., "clients")
            joins: Optional JOIN clauses

        Returns:
            Full COUNT query string
        """
        parts = [f"SELECT COUNT(*) FROM {table}"]
        if joins:
            parts.append(joins)
        if self.where_clause:
            parts.append(self.where_clause)
        return " ".join(parts)


class QueryBuilder:
    """
    Fluent builder for dynamic SQL WHERE clauses with parameterized queries.

    Usage:
        qb = QueryBuilder()
        qb.eq("status", status)
        qb.ilike("full_name", search)
        qb.gte("created_at", start_date)
        qb.lte("created_at", end_date)
        qb.in_list("tags", tags)

        result = qb.build()
        # result.where_clause -> "WHERE status = $1 AND full_name ILIKE $2 AND ..."
        # result.params -> [status, f"%{search}%", start_date, end_date, ...]

        # For pagination:
        lo = result.limit_offset_clause(limit, offset)
        query = f"SELECT * FROM clients {result.where_clause} ORDER BY id {lo}"
        rows = await conn.fetch(query, *result.params)
    """

    def __init__(self) -> None:
        self._conditions: list[str] = []
        self._params: list[Any] = []
        self._param_count: int = 0

    def _next_param(self) -> int:
        """Get the next parameter position."""
        self._param_count += 1
        return self._param_count

    def eq(self, column: str, value: Any | None) -> QueryBuilder:
        """Add equality condition (column = $N). Skipped if value is None."""
        if value is not None:
            pos = self._next_param()
            self._conditions.append(f"{column} = ${pos}")
            self._params.append(value)
        return self

    def neq(self, column: str, value: Any | None) -> QueryBuilder:
        """Add inequality condition (column != $N). Skipped if value is None."""
        if value is not None:
            pos = self._next_param()
            self._conditions.append(f"{column} != ${pos}")
            self._params.append(value)
        return self

    def ilike(self, column: str, value: str | None) -> QueryBuilder:
        """Add case-insensitive LIKE condition. Auto-wraps with %. Skipped if value is None."""
        if value is not None:
            pos = self._next_param()
            self._conditions.append(f"{column} ILIKE ${pos}")
            self._params.append(f"%{value}%")
        return self

    def gte(self, column: str, value: Any | None) -> QueryBuilder:
        """Add >= condition. Skipped if value is None."""
        if value is not None:
            pos = self._next_param()
            self._conditions.append(f"{column} >= ${pos}")
            self._params.append(value)
        return self

    def lte(self, column: str, value: Any | None) -> QueryBuilder:
        """Add <= condition. Skipped if value is None."""
        if value is not None:
            pos = self._next_param()
            self._conditions.append(f"{column} <= ${pos}")
            self._params.append(value)
        return self

    def gt(self, column: str, value: Any | None) -> QueryBuilder:
        """Add > condition. Skipped if value is None."""
        if value is not None:
            pos = self._next_param()
            self._conditions.append(f"{column} > ${pos}")
            self._params.append(value)
        return self

    def lt(self, column: str, value: Any | None) -> QueryBuilder:
        """Add < condition. Skipped if value is None."""
        if value is not None:
            pos = self._next_param()
            self._conditions.append(f"{column} < ${pos}")
            self._params.append(value)
        return self

    def is_null(self, column: str) -> QueryBuilder:
        """Add IS NULL condition."""
        self._conditions.append(f"{column} IS NULL")
        return self

    def is_not_null(self, column: str) -> QueryBuilder:
        """Add IS NOT NULL condition."""
        self._conditions.append(f"{column} IS NOT NULL")
        return self

    def in_list(self, column: str, values: list[Any] | None) -> QueryBuilder:
        """Add IN (...) condition. Skipped if values is None or empty."""
        if values:
            placeholders = []
            for v in values:
                pos = self._next_param()
                placeholders.append(f"${pos}")
                self._params.append(v)
            self._conditions.append(f"{column} IN ({', '.join(placeholders)})")
        return self

    def contains_jsonb(self, column: str, value: Any | None) -> QueryBuilder:
        """Add JSONB containment condition (column @> $N::jsonb). Skipped if value is None."""
        if value is not None:
            pos = self._next_param()
            self._conditions.append(f"{column} @> ${pos}::jsonb")
            self._params.append(value)
        return self

    def array_contains(self, column: str, value: Any | None) -> QueryBuilder:
        """Add array containment (value = ANY(column)). Skipped if value is None."""
        if value is not None:
            pos = self._next_param()
            self._conditions.append(f"${pos} = ANY({column})")
            self._params.append(value)
        return self

    def raw(self, condition: str, params: list[Any] | None = None) -> QueryBuilder:
        """
        Add a raw SQL condition. Use $N placeholders starting from current count.

        Args:
            condition: Raw SQL condition string (e.g., "LOWER(email) = $N")
            params: Parameters for this condition
        """
        if params:
            # Replace $N placeholders sequentially
            for param in params:
                pos = self._next_param()
                condition = condition.replace("$N", f"${pos}", 1)
                self._params.append(param)
        self._conditions.append(condition)
        return self

    def build(self) -> QueryResult:
        """Build the WHERE clause and return a QueryResult."""
        where = "WHERE " + " AND ".join(self._conditions) if self._conditions else ""
        return QueryResult(
            where_clause=where,
            params=list(self._params),
            param_count=self._param_count,
        )


def paginate(
    limit: int, offset: int, max_limit: int = 200, default_limit: int = 50,
) -> tuple[int, int]:
    """
    Sanitize pagination parameters.

    Args:
        limit: Requested limit
        offset: Requested offset
        max_limit: Maximum allowed limit
        default_limit: Default limit when not specified

    Returns:
        Tuple of (sanitized_limit, sanitized_offset)
    """
    if limit <= 0:
        limit = default_limit
    limit = min(limit, max_limit)
    offset = max(0, offset)
    return limit, offset
