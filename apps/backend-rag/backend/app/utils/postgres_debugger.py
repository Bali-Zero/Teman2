"""
PostgreSQL Debugger Utility
Provides comprehensive debugging capabilities for PostgreSQL database.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any

import asyncpg

from app.core.config import settings

logger = logging.getLogger(__name__)

# Security configuration
QUERY_TIMEOUT_SECONDS = 30
MAX_ROWS_LIMIT = 1000
FORBIDDEN_KEYWORDS = [
    "DROP",
    "DELETE",
    "UPDATE",
    "INSERT",
    "CREATE",
    "ALTER",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
    "EXECUTE",
    "CALL",
    "DO",
]


@dataclass
class ConnectionInfo:
    """PostgreSQL connection information"""

    connected: bool
    version: str | None = None
    database: str | None = None
    user: str | None = None
    pool_size: int | None = None
    pool_idle: int | None = None
    pool_active: int | None = None
    error: str | None = None


@dataclass
class TableInfo:
    """Table information"""

    schema: str
    name: str
    columns: list[dict[str, Any]]
    indexes: list[dict[str, Any]]
    foreign_keys: list[dict[str, Any]]
    constraints: list[dict[str, Any]]


class PostgreSQLDebugger:
    """
    Debugger for PostgreSQL database operations.

    Provides safe, read-only access to database inspection and debugging.
    """

    def __init__(self, database_url: str | None = None):
        """
        Initialize PostgreSQL debugger.

        Args:
            database_url: PostgreSQL connection string (defaults to settings.database_url)
        """
        self.database_url = database_url or settings.database_url

    async def _get_connection(self) -> asyncpg.Connection:
        """
        Get a database connection.

        Returns:
            asyncpg.Connection instance

        Raises:
            ValueError: If database_url is not configured
            asyncpg.PostgresError: If connection fails
        """
        if not self.database_url:
            raise ValueError("DATABASE_URL not configured")

        return await asyncpg.connect(self.database_url, timeout=QUERY_TIMEOUT_SECONDS)

    async def test_connection(self, pool: asyncpg.Pool | None = None) -> ConnectionInfo:
        """
        Test database connection and get connection info.

        Args:
            pool: Optional connection pool to check (from app.state)

        Returns:
            ConnectionInfo with connection status and details
        """
        if pool:
            try:
                # Get pool stats
                pool_size = pool.get_size()
                pool_idle = pool.get_idle_size()
                pool_active = pool_size - pool_idle

                # Test connection from pool
                async with pool.acquire() as conn:
                    version = await conn.fetchval("SELECT version()")
                    database = await conn.fetchval("SELECT current_database()")
                    user = await conn.fetchval("SELECT current_user")

                return ConnectionInfo(
                    connected=True,
                    version=version,
                    database=database,
                    user=user,
                    pool_size=pool_size,
                    pool_idle=pool_idle,
                    pool_active=pool_active,
                )
            except Exception as e:
                logger.error(f"Pool connection test failed: {e}", exc_info=True)
                return ConnectionInfo(connected=False, error=str(e))

        # Direct connection test
        try:
            conn = await self._get_connection()
            try:
                version = await conn.fetchval("SELECT version()")
                database = await conn.fetchval("SELECT current_database()")
                user = await conn.fetchval("SELECT current_user")
                return ConnectionInfo(
                    connected=True,
                    version=version,
                    database=database,
                    user=user,
                )
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"Direct connection test failed: {e}", exc_info=True)
            return ConnectionInfo(connected=False, error=str(e))

    def validate_query(self, query: str) -> tuple[bool, str | None]:
        """
        Validate that query is safe (read-only).

        Args:
            query: SQL query string

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not query or not query.strip():
            return False, "Query is empty"

        # Normalize query
        normalized = query.strip().upper()

        # Check whitelist: must start with SELECT
        if not normalized.startswith("SELECT"):
            return False, "Only SELECT queries are allowed"

        # Check blacklist: no forbidden keywords
        for keyword in FORBIDDEN_KEYWORDS:
            # Use word boundaries to avoid false positives
            pattern = rf"\b{keyword}\b"
            if re.search(pattern, normalized, re.IGNORECASE):
                return False, f"Forbidden keyword detected: {keyword}"

        # Check for semicolon-separated queries (potential SQL injection)
        # Count SELECT statements - if more than 1, it's multiple statements
        select_count = normalized.count("SELECT")
        if select_count > 1:
            return False, "Multiple statements not allowed"
        
        # Also check for multiple semicolons (even without multiple SELECT)
        if normalized.count(";") > 1:
            return False, "Multiple statements not allowed"

        return True, None

    async def execute_query(
        self, query: str, limit: int = 100, pool: asyncpg.Pool | None = None
    ) -> dict[str, Any]:
        """
        Execute a read-only query safely.

        Args:
            query: SQL SELECT query
            limit: Maximum number of rows to return (default 100, max 1000)
            pool: Optional connection pool to use

        Returns:
            Dictionary with query results and metadata

        Raises:
            ValueError: If query validation fails
            asyncpg.PostgresError: If query execution fails
        """
        # Validate query
        is_valid, error_msg = self.validate_query(query)
        if not is_valid:
            raise ValueError(error_msg or "Query validation failed")

        # Enforce row limit
        limit = min(limit, MAX_ROWS_LIMIT)

        # Add LIMIT if not present
        normalized_query = query.strip()
        if "LIMIT" not in normalized_query.upper():
            normalized_query = f"{normalized_query} LIMIT {limit}"

        try:
            if pool:
                async with pool.acquire() as conn:
                    rows = await conn.fetch(normalized_query, timeout=QUERY_TIMEOUT_SECONDS)
                    columns = [desc.name for desc in rows[0]._row_desc] if rows else []
            else:
                conn = await self._get_connection()
                try:
                    rows = await conn.fetch(normalized_query, timeout=QUERY_TIMEOUT_SECONDS)
                    columns = [desc.name for desc in rows[0]._row_desc] if rows else []
                finally:
                    await conn.close()

            # Convert rows to dictionaries
            results = [dict(row) for row in rows]

            return {
                "success": True,
                "rows": results,
                "row_count": len(results),
                "columns": columns,
                "query": normalized_query,
            }
        except asyncpg.PostgresError as e:
            logger.error(f"Query execution failed: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error during query execution: {e}", exc_info=True)
            raise

    async def get_tables(self, schema: str = "public") -> list[dict[str, Any]]:
        """
        Get list of all tables in a schema.

        Args:
            schema: Schema name (default: public)

        Returns:
            List of table information dictionaries
        """
        query = """
            SELECT 
                table_name,
                table_type
            FROM information_schema.tables
            WHERE table_schema = $1
            ORDER BY table_name
        """

        conn = await self._get_connection()
        try:
            rows = await conn.fetch(query, schema)
            return [{"name": row["table_name"], "type": row["table_type"]} for row in rows]
        finally:
            await conn.close()

    async def get_table_details(self, table_name: str, schema: str = "public") -> TableInfo:
        """
        Get detailed information about a table.

        Args:
            table_name: Table name
            schema: Schema name (default: public)

        Returns:
            TableInfo with columns, indexes, foreign keys, and constraints
        """
        conn = await self._get_connection()
        try:
            # Get columns
            columns_query = """
                SELECT 
                    column_name,
                    data_type,
                    is_nullable,
                    column_default,
                    character_maximum_length,
                    numeric_precision,
                    numeric_scale
                FROM information_schema.columns
                WHERE table_schema = $1 AND table_name = $2
                ORDER BY ordinal_position
            """
            columns_rows = await conn.fetch(columns_query, schema, table_name)
            columns = [
                {
                    "name": row["column_name"],
                    "type": row["data_type"],
                    "nullable": row["is_nullable"] == "YES",
                    "default": row["column_default"],
                    "max_length": row["character_maximum_length"],
                    "precision": row["numeric_precision"],
                    "scale": row["numeric_scale"],
                }
                for row in columns_rows
            ]

            # Get indexes
            indexes_query = """
                SELECT 
                    i.indexname,
                    i.indexdef,
                    a.attname as column_name
                FROM pg_indexes i
                LEFT JOIN pg_attribute a ON a.attrelid = (
                    SELECT oid FROM pg_class WHERE relname = i.tablename
                ) AND a.attnum = ANY(
                    SELECT unnest(ix.indkey) FROM pg_index ix 
                    WHERE ix.indexrelid = (
                        SELECT oid FROM pg_class WHERE relname = i.indexname
                    )
                )
                WHERE i.schemaname = $1 AND i.tablename = $2
                ORDER BY i.indexname, a.attnum
            """
            indexes_rows = await conn.fetch(indexes_query, schema, table_name)
            indexes_dict: dict[str, dict[str, Any]] = {}
            for row in indexes_rows:
                idx_name = row["indexname"]
                if idx_name not in indexes_dict:
                    indexes_dict[idx_name] = {
                        "name": idx_name,
                        "definition": row["indexdef"],
                        "columns": [],
                    }
                if row["column_name"]:
                    indexes_dict[idx_name]["columns"].append(row["column_name"])
            indexes = list(indexes_dict.values())

            # Get foreign keys
            fk_query = """
                SELECT
                    tc.constraint_name,
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                    AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                    AND tc.table_schema = $1
                    AND tc.table_name = $2
            """
            fk_rows = await conn.fetch(fk_query, schema, table_name)
            foreign_keys = [
                {
                    "constraint_name": row["constraint_name"],
                    "column": row["column_name"],
                    "references_table": row["foreign_table_name"],
                    "references_column": row["foreign_column_name"],
                }
                for row in fk_rows
            ]

            # Get constraints
            constraints_query = """
                SELECT
                    constraint_name,
                    constraint_type
                FROM information_schema.table_constraints
                WHERE table_schema = $1 AND table_name = $2
                ORDER BY constraint_name
            """
            constraints_rows = await conn.fetch(constraints_query, schema, table_name)
            constraints = [
                {
                    "name": row["constraint_name"],
                    "type": row["constraint_type"],
                }
                for row in constraints_rows
            ]

            return TableInfo(
                schema=schema,
                name=table_name,
                columns=columns,
                indexes=indexes,
                foreign_keys=foreign_keys,
                constraints=constraints,
            )
        finally:
            await conn.close()

    async def get_indexes(self, table_name: str | None = None) -> list[dict[str, Any]]:
        """
        Get list of all indexes.

        Args:
            table_name: Optional table name to filter indexes

        Returns:
            List of index information dictionaries
        """
        if table_name:
            query = """
                SELECT 
                    schemaname,
                    tablename,
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE tablename = $1
                ORDER BY schemaname, tablename, indexname
            """
            params = (table_name,)
        else:
            query = """
                SELECT 
                    schemaname,
                    tablename,
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                ORDER BY schemaname, tablename, indexname
            """
            params = ()

        conn = await self._get_connection()
        try:
            rows = await conn.fetch(query, *params)
            return [
                {
                    "schema": row["schemaname"],
                    "table": row["tablename"],
                    "name": row["indexname"],
                    "definition": row["indexdef"],
                }
                for row in rows
            ]
        finally:
            await conn.close()

    async def get_table_stats(self, table_name: str | None = None) -> list[dict[str, Any]]:
        """
        Get statistics for tables (row counts, sizes, indexes).

        Args:
            table_name: Optional table name to filter stats

        Returns:
            List of table statistics dictionaries
        """
        if table_name:
            query = """
                SELECT 
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
                    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - 
                                   pg_relation_size(schemaname||'.'||tablename)) as indexes_size,
                    (SELECT COUNT(*) FROM information_schema.statistics 
                     WHERE table_schema = schemaname AND table_name = tablename) as index_count
                FROM pg_tables
                WHERE tablename = $1 AND schemaname = 'public'
            """
            params = (table_name,)
        else:
            query = """
                SELECT 
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
                    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - 
                                   pg_relation_size(schemaname||'.'||tablename)) as indexes_size,
                    (SELECT COUNT(*) FROM information_schema.statistics 
                     WHERE table_schema = schemaname AND table_name = tablename) as index_count
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename
            """
            params = ()

        conn = await self._get_connection()
        try:
            rows = await conn.fetch(query, *params)
            stats = []
            for row in rows:
                # Get row count for each table
                count_query = f'SELECT COUNT(*) FROM "{row["schemaname"]}"."{row["tablename"]}"'
                try:
                    row_count = await conn.fetchval(count_query)
                except Exception:
                    row_count = None

                stats.append(
                    {
                        "schema": row["schemaname"],
                        "table": row["tablename"],
                        "row_count": row_count,
                        "total_size": row["total_size"],
                        "table_size": row["table_size"],
                        "indexes_size": row["indexes_size"],
                        "index_count": row["index_count"],
                    }
                )
            return stats
        finally:
            await conn.close()

    async def get_database_stats(self) -> dict[str, Any]:
        """
        Get global database statistics.

        Returns:
            Dictionary with database statistics
        """
        conn = await self._get_connection()
        try:
            # Database size
            db_size = await conn.fetchval(
                "SELECT pg_size_pretty(pg_database_size(current_database()))"
            )

            # Database version
            version = await conn.fetchval("SELECT version()")

            # Connection count
            conn_count = await conn.fetchval(
                "SELECT COUNT(*) FROM pg_stat_activity WHERE datname = current_database()"
            )

            # Active connections
            active_conn = await conn.fetchval(
                """
                SELECT COUNT(*) FROM pg_stat_activity 
                WHERE datname = current_database() AND state = 'active'
                """
            )

            # Idle connections
            idle_conn = await conn.fetchval(
                """
                SELECT COUNT(*) FROM pg_stat_activity 
                WHERE datname = current_database() AND state = 'idle'
                """
            )

            # Database name
            db_name = await conn.fetchval("SELECT current_database()")

            return {
                "database": db_name,
                "version": version,
                "size": db_size,
                "total_connections": conn_count,
                "active_connections": active_conn,
                "idle_connections": idle_conn,
            }
        finally:
            await conn.close()

    async def get_slow_queries(self, limit: int = 20) -> list[dict[str, Any]]:
        """
        Get slow queries from pg_stat_statements (if available).

        Args:
            limit: Maximum number of queries to return

        Returns:
            List of slow query information dictionaries
        """
        conn = await self._get_connection()
        try:
            # Check if pg_stat_statements extension is available
            extension_exists = await conn.fetchval(
                """
                SELECT EXISTS(
                    SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'
                )
                """
            )

            if not extension_exists:
                return []

            query = """
                SELECT 
                    query,
                    calls,
                    total_exec_time,
                    mean_exec_time,
                    max_exec_time,
                    min_exec_time,
                    stddev_exec_time
                FROM pg_stat_statements
                WHERE query NOT LIKE '%pg_stat_statements%'
                ORDER BY mean_exec_time DESC
                LIMIT $1
            """

            rows = await conn.fetch(query, limit)
            return [
                {
                    "query": row["query"][:500],  # Truncate long queries
                    "calls": row["calls"],
                    "total_time_ms": round(row["total_exec_time"], 2),
                    "mean_time_ms": round(row["mean_exec_time"], 2),
                    "max_time_ms": round(row["max_exec_time"], 2),
                    "min_time_ms": round(row["min_exec_time"], 2),
                    "stddev_time_ms": round(row["stddev_exec_time"] or 0, 2),
                }
                for row in rows
            ]
        finally:
            await conn.close()

    async def get_active_locks(self) -> list[dict[str, Any]]:
        """
        Get active locks in the database.

        Returns:
            List of lock information dictionaries
        """
        conn = await self._get_connection()
        try:
            query = """
                SELECT 
                    locktype,
                    database,
                    relation::regclass as relation,
                    mode,
                    granted,
                    pid,
                    usename,
                    application_name,
                    state,
                    query_start,
                    state_change
                FROM pg_locks l
                JOIN pg_stat_activity a ON l.pid = a.pid
                WHERE l.database = (SELECT oid FROM pg_database WHERE datname = current_database())
                ORDER BY query_start
            """

            rows = await conn.fetch(query)
            return [
                {
                    "lock_type": row["locktype"],
                    "relation": str(row["relation"]) if row["relation"] else None,
                    "mode": row["mode"],
                    "granted": row["granted"],
                    "pid": row["pid"],
                    "username": row["usename"],
                    "application": row["application_name"],
                    "state": row["state"],
                    "query_start": row["query_start"].isoformat() if row["query_start"] else None,
                }
                for row in rows
            ]
        finally:
            await conn.close()

    async def get_connection_stats(self) -> dict[str, Any]:
        """
        Get connection statistics.

        Returns:
            Dictionary with connection statistics
        """
        conn = await self._get_connection()
        try:
            # Total connections
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM pg_stat_activity WHERE datname = current_database()"
            )

            # By state
            states_query = """
                SELECT state, COUNT(*) as count
                FROM pg_stat_activity
                WHERE datname = current_database()
                GROUP BY state
            """
            states_rows = await conn.fetch(states_query)
            by_state = {row["state"]: row["count"] for row in states_rows}

            # Long-running queries
            long_running = await conn.fetchval(
                """
                SELECT COUNT(*) FROM pg_stat_activity
                WHERE datname = current_database()
                AND state = 'active'
                AND now() - query_start > interval '5 minutes'
                """
            )

            # Idle in transaction
            idle_in_transaction = await conn.fetchval(
                """
                SELECT COUNT(*) FROM pg_stat_activity
                WHERE datname = current_database()
                AND state = 'idle in transaction'
                """
            )

            return {
                "total": total,
                "by_state": by_state,
                "long_running_queries": long_running,
                "idle_in_transaction": idle_in_transaction,
            }
        finally:
            await conn.close()

