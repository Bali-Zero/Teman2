"""
Comprehensive pytest suite for QueryBuilder utility.
Tests: eq, neq, ilike, gte, lte, gt, lt, is_null, is_not_null,
       in_list, contains_jsonb, array_contains, raw, build,
       QueryResult, paginate

Target: 95%+ coverage (utility code should be rock-solid)
"""

from backend.utils.query_builder import QueryBuilder, QueryResult, paginate

# ============================================================================
# QueryBuilder TESTS
# ============================================================================


class TestQueryBuilder:
    """Tests for QueryBuilder fluent API."""

    def test_empty_build(self) -> None:
        """No conditions produces empty WHERE clause."""
        qb = QueryBuilder()
        result = qb.build()
        assert result.where_clause == ""
        assert result.params == []
        assert result.param_count == 0

    def test_single_eq(self) -> None:
        """Single equality condition."""
        qb = QueryBuilder()
        qb.eq("status", "active")
        result = qb.build()
        assert result.where_clause == "WHERE status = $1"
        assert result.params == ["active"]

    def test_eq_skips_none(self) -> None:
        """None values are skipped in eq."""
        qb = QueryBuilder()
        qb.eq("status", None)
        result = qb.build()
        assert result.where_clause == ""
        assert result.params == []

    def test_multiple_conditions(self) -> None:
        """Multiple conditions are AND-joined."""
        qb = QueryBuilder()
        qb.eq("status", "active")
        qb.eq("client_type", "individual")
        result = qb.build()
        assert result.where_clause == "WHERE status = $1 AND client_type = $2"
        assert result.params == ["active", "individual"]
        assert result.param_count == 2

    def test_neq(self) -> None:
        """Inequality condition."""
        qb = QueryBuilder()
        qb.neq("status", "deleted")
        result = qb.build()
        assert result.where_clause == "WHERE status != $1"
        assert result.params == ["deleted"]

    def test_ilike(self) -> None:
        """Case-insensitive LIKE with auto % wrapping."""
        qb = QueryBuilder()
        qb.ilike("full_name", "john")
        result = qb.build()
        assert result.where_clause == "WHERE full_name ILIKE $1"
        assert result.params == ["%john%"]

    def test_ilike_skips_none(self) -> None:
        """ILIKE skips None values."""
        qb = QueryBuilder()
        qb.ilike("name", None)
        result = qb.build()
        assert result.where_clause == ""

    def test_gte(self) -> None:
        """Greater than or equal."""
        qb = QueryBuilder()
        qb.gte("created_at", "2026-01-01")
        result = qb.build()
        assert result.where_clause == "WHERE created_at >= $1"

    def test_lte(self) -> None:
        """Less than or equal."""
        qb = QueryBuilder()
        qb.lte("created_at", "2026-12-31")
        result = qb.build()
        assert result.where_clause == "WHERE created_at <= $1"

    def test_gt(self) -> None:
        """Greater than."""
        qb = QueryBuilder()
        qb.gt("score", 0.5)
        result = qb.build()
        assert result.where_clause == "WHERE score > $1"

    def test_lt(self) -> None:
        """Less than."""
        qb = QueryBuilder()
        qb.lt("score", 0.9)
        result = qb.build()
        assert result.where_clause == "WHERE score < $1"

    def test_is_null(self) -> None:
        """IS NULL condition."""
        qb = QueryBuilder()
        qb.is_null("assigned_to")
        result = qb.build()
        assert result.where_clause == "WHERE assigned_to IS NULL"
        assert result.params == []

    def test_is_not_null(self) -> None:
        """IS NOT NULL condition."""
        qb = QueryBuilder()
        qb.is_not_null("email")
        result = qb.build()
        assert result.where_clause == "WHERE email IS NOT NULL"

    def test_in_list(self) -> None:
        """IN clause with multiple values."""
        qb = QueryBuilder()
        qb.in_list("status", ["active", "prospect", "lead"])
        result = qb.build()
        assert result.where_clause == "WHERE status IN ($1, $2, $3)"
        assert result.params == ["active", "prospect", "lead"]

    def test_in_list_empty(self) -> None:
        """IN clause skipped for empty list."""
        qb = QueryBuilder()
        qb.in_list("status", [])
        result = qb.build()
        assert result.where_clause == ""

    def test_in_list_none(self) -> None:
        """IN clause skipped for None."""
        qb = QueryBuilder()
        qb.in_list("status", None)
        result = qb.build()
        assert result.where_clause == ""

    def test_contains_jsonb(self) -> None:
        """JSONB containment condition."""
        qb = QueryBuilder()
        qb.contains_jsonb("permissions", '{"role": "admin"}')
        result = qb.build()
        assert result.where_clause == "WHERE permissions @> $1::jsonb"
        assert result.params == ['{"role": "admin"}']

    def test_array_contains(self) -> None:
        """Array containment condition."""
        qb = QueryBuilder()
        qb.array_contains("tags", "vip")
        result = qb.build()
        assert result.where_clause == "WHERE $1 = ANY(tags)"
        assert result.params == ["vip"]

    def test_raw_condition(self) -> None:
        """Raw SQL condition with parameters."""
        qb = QueryBuilder()
        qb.raw("LOWER(email) = $N", ["test@example.com"])
        result = qb.build()
        assert result.where_clause == "WHERE LOWER(email) = $1"
        assert result.params == ["test@example.com"]

    def test_raw_without_params(self) -> None:
        """Raw SQL condition without parameters."""
        qb = QueryBuilder()
        qb.raw("deleted_at IS NULL")
        result = qb.build()
        assert result.where_clause == "WHERE deleted_at IS NULL"
        assert result.params == []

    def test_fluent_chaining(self) -> None:
        """Methods return self for fluent chaining."""
        qb = QueryBuilder()
        result = (
            qb.eq("status", "active").ilike("name", "john").gte("created_at", "2026-01-01").build()
        )
        assert "status = $1" in result.where_clause
        assert "name ILIKE $2" in result.where_clause
        assert "created_at >= $3" in result.where_clause
        assert len(result.params) == 3

    def test_complex_query_like_crm_clients(self) -> None:
        """Simulate the dynamic WHERE from crm_clients.py."""
        qb = QueryBuilder()
        qb.eq("status", "active")
        qb.eq("client_type", "individual")
        qb.ilike("full_name", "John")
        qb.eq("assigned_to", "agent@balizero.com")
        qb.array_contains("tags", "vip")
        qb.gte("created_at", "2026-01-01")

        result = qb.build()

        assert result.param_count == 6
        assert "status = $1" in result.where_clause
        assert "client_type = $2" in result.where_clause
        assert "full_name ILIKE $3" in result.where_clause
        assert "assigned_to = $4" in result.where_clause
        assert "$5 = ANY(tags)" in result.where_clause
        assert "created_at >= $6" in result.where_clause


# ============================================================================
# QueryResult TESTS
# ============================================================================


class TestQueryResult:
    """Tests for QueryResult dataclass."""

    def test_limit_offset_clause(self) -> None:
        """LIMIT/OFFSET uses correct param positions."""
        qr = QueryResult(
            where_clause="WHERE status = $1",
            params=["active"],
            param_count=1,
        )

        lo = qr.limit_offset_clause(50, 0)

        assert lo == "LIMIT $2 OFFSET $3"
        assert qr.params == ["active", 50, 0]
        assert qr.param_count == 3

    def test_limit_offset_no_where(self) -> None:
        """LIMIT/OFFSET works without WHERE clause."""
        qr = QueryResult(where_clause="", params=[], param_count=0)

        lo = qr.limit_offset_clause(10, 20)

        assert lo == "LIMIT $1 OFFSET $2"
        assert qr.params == [10, 20]

    def test_count_query(self) -> None:
        """COUNT query uses WHERE clause."""
        qr = QueryResult(
            where_clause="WHERE status = $1",
            params=["active"],
            param_count=1,
        )

        query = qr.count_query("clients")
        assert query == "SELECT COUNT(*) FROM clients WHERE status = $1"

    def test_count_query_with_joins(self) -> None:
        """COUNT query includes JOIN clauses."""
        qr = QueryResult(
            where_clause="WHERE c.status = $1",
            params=["active"],
            param_count=1,
        )

        query = qr.count_query("clients c", joins="JOIN practices p ON p.client_id = c.id")
        assert "JOIN practices p ON p.client_id = c.id" in query
        assert "WHERE c.status = $1" in query

    def test_count_query_no_where(self) -> None:
        """COUNT query without WHERE clause."""
        qr = QueryResult(where_clause="", params=[], param_count=0)

        query = qr.count_query("clients")
        assert query == "SELECT COUNT(*) FROM clients"


# ============================================================================
# paginate TESTS
# ============================================================================


class TestPaginate:
    """Tests for paginate helper function."""

    def test_normal_values(self) -> None:
        """Normal limit and offset pass through."""
        limit, offset = paginate(50, 10)
        assert limit == 50
        assert offset == 10

    def test_limit_capped_at_max(self) -> None:
        """Limit is capped at max_limit."""
        limit, offset = paginate(500, 0, max_limit=200)
        assert limit == 200

    def test_negative_limit_uses_default(self) -> None:
        """Negative limit uses default."""
        limit, offset = paginate(-1, 0)
        assert limit == 50

    def test_zero_limit_uses_default(self) -> None:
        """Zero limit uses default."""
        limit, offset = paginate(0, 0)
        assert limit == 50

    def test_negative_offset_clamped_to_zero(self) -> None:
        """Negative offset is clamped to 0."""
        limit, offset = paginate(50, -10)
        assert offset == 0

    def test_custom_defaults(self) -> None:
        """Custom max_limit and default_limit."""
        limit, offset = paginate(0, 0, max_limit=100, default_limit=25)
        assert limit == 25


# ============================================================================
# INTEGRATION-STYLE TESTS
# ============================================================================


class TestQueryBuilderIntegration:
    """Tests simulating real-world query building patterns."""

    def test_crm_list_query(self) -> None:
        """Simulate building a CRM client list query."""
        # Parameters from endpoint
        status = "active"
        search = "Marco"
        assigned_to = "agent@balizero.com"
        limit_val, offset_val = paginate(50, 0)

        qb = QueryBuilder()
        qb.eq("status", status)
        qb.ilike("full_name", search)
        qb.eq("assigned_to", assigned_to)

        result = qb.build()

        # Build count query
        count_sql = result.count_query("clients")
        assert "SELECT COUNT(*)" in count_sql

        # Build data query
        list(result.params)  # Save for count query
        lo = result.limit_offset_clause(limit_val, offset_val)
        data_sql = f"SELECT * FROM clients {result.where_clause} ORDER BY created_at DESC {lo}"

        assert "LIMIT" in data_sql
        assert "OFFSET" in data_sql
        assert len(result.params) == 5  # 3 conditions + limit + offset

    def test_admin_logs_query(self) -> None:
        """Simulate building an admin logs query with date range."""
        from datetime import datetime, timezone

        qb = QueryBuilder()
        qb.eq("user_email", "admin@balizero.com")
        qb.eq("action_type", "create")
        qb.gte("created_at", datetime(2026, 1, 1, tzinfo=timezone.utc))
        qb.lte("created_at", datetime(2026, 1, 31, tzinfo=timezone.utc))

        result = qb.build()

        assert result.param_count == 4
        assert "user_email = $1" in result.where_clause
        assert "action_type = $2" in result.where_clause
        assert "created_at >= $3" in result.where_clause
        assert "created_at <= $4" in result.where_clause
