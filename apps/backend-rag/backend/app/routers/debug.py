"""
Debug Router
Provides debug endpoints for troubleshooting and monitoring
"""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Query, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from app.core.config import settings
from app.dependencies import get_current_user
from middleware.request_tracing import (
    RequestTracingMiddleware,
    get_correlation_id,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/debug", tags=["debug"])

# Include v1 debug endpoints for backward compatibility
v1_router = APIRouter(prefix="/api/v1/debug", tags=["debug"])

# Security
security = HTTPBearer(auto_error=False)


def verify_debug_access(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    request: Request = None,
) -> bool:
    """
    Verify access to debug endpoints.

    Args:
        credentials: HTTP Bearer token
        request: FastAPI request

    Returns:
        True if access granted

    Raises:
        HTTPException: If access denied
    """
    # Allow in production only if ADMIN_API_KEY is configured (security check)
    if settings.environment.lower() == "production":
        if not settings.admin_api_key:
            raise HTTPException(
                status_code=403,
                detail="Debug endpoints are not available in production without ADMIN_API_KEY",
            )
        # In production, require ADMIN_API_KEY (checked below)

    # Check API key or JWT token
    if credentials:
        token = credentials.credentials

        # Check admin API key
        if settings.admin_api_key and token == settings.admin_api_key:
            return True

        # Check JWT token (if implemented)
        # For now, allow if admin_api_key matches
        if token == settings.admin_api_key:
            return True

    # Check X-Debug-Key header as fallback
    debug_key = request.headers.get("X-Debug-Key") if request else None
    if debug_key and settings.admin_api_key and debug_key == settings.admin_api_key:
        return True

    raise HTTPException(
        status_code=401,
        detail="Debug access requires valid API key or JWT token",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.get("/request/{request_id}")
async def get_request_trace(
    request_id: str,
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get trace for a specific request.

    Args:
        request_id: Request ID or correlation ID

    Returns:
        Trace data
    """
    trace = RequestTracingMiddleware.get_trace(request_id)

    if not trace:
        raise HTTPException(status_code=404, detail=f"Trace not found for request_id: {request_id}")

    return {
        "success": True,
        "trace": trace,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/logs")
async def get_logs(
    module: str | None = Query(None, description="Filter logs by module name"),
    level: str | None = Query(None, description="Filter by log level (DEBUG, INFO, WARNING, ERROR)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of logs to return"),
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get filtered logs.

    Note: This is a placeholder. In production, you would integrate with
    a logging service like CloudWatch, ELK, or similar.

    Args:
        module: Optional module name filter
        level: Optional log level filter
        limit: Maximum number of logs

    Returns:
        Logs data
    """
    # TODO: Integrate with actual logging service
    return {
        "success": True,
        "message": "Log retrieval not yet implemented. Integrate with logging service.",
        "filters": {
            "module": module,
            "level": level,
            "limit": limit,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/state")
async def get_app_state(
    request: Request,
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get internal application state.

    Args:
        request: FastAPI request

    Returns:
        Application state information
    """
    app_state = request.app.state

    state_info: dict[str, Any] = {
        "services": {},
        "initialized": getattr(app_state, "services_initialized", False),
        "correlation_id": get_correlation_id(request),
    }

    # Check key services
    service_checks = [
        "search_service",
        "ai_client",
        "db_pool",
        "memory_service",
        "intelligent_router",
        "tool_executor",
    ]

    for service_name in service_checks:
        service = getattr(app_state, service_name, None)
        state_info["services"][service_name] = {
            "present": service is not None,
            "type": type(service).__name__ if service else None,
        }

    return {
        "success": True,
        "state": state_info,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/services")
async def get_services_status(
    request: Request,
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get status of all services.

    Args:
        request: FastAPI request

    Returns:
        Services status
    """
    from app.core.service_health import service_registry

    services_status: dict[str, Any] = {}

    # Get service registry status if available
    try:
        registry_status = service_registry.get_status()
        services_status["registry"] = registry_status
    except Exception as e:
        logger.warning(f"Failed to get service registry status: {e}")
        services_status["registry"] = {"error": str(e)}

    # Check individual services
    app_state = request.app.state
    service_checks = [
        "search_service",
        "ai_client",
        "db_pool",
        "memory_service",
        "intelligent_router",
        "health_monitor",
    ]

    for service_name in service_checks:
        service = getattr(app_state, service_name, None)
        if service:
            try:
                # Try to get health status if available
                if hasattr(service, "health_check"):
                    health = await service.health_check()
                    services_status[service_name] = health
                else:
                    services_status[service_name] = {
                        "status": "available",
                        "type": type(service).__name__,
                    }
            except Exception as e:
                services_status[service_name] = {
                    "status": "error",
                    "error": str(e),
                }
        else:
            services_status[service_name] = {"status": "unavailable"}

    return {
        "success": True,
        "services": services_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/traces/recent")
async def get_recent_traces_endpoint(
    limit: int = Query(50, ge=1, le=500, description="Maximum number of traces"),
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get recent request traces.

    Args:
        limit: Maximum number of traces to return

    Returns:
        Recent traces
    """
    traces = RequestTracingMiddleware.get_recent_traces(limit=limit)

    return {
        "success": True,
        "traces": traces,
        "count": len(traces),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.delete("/traces")
async def clear_traces(
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Clear all stored traces.

    Returns:
        Confirmation message
    """
    from middleware.request_tracing import RequestTracingMiddleware

    count = RequestTracingMiddleware.clear_traces()

    return {
        "success": True,
        "message": f"Cleared {count} traces",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/rag/pipeline/{correlation_id}")
async def get_rag_pipeline_trace(
    correlation_id: str,
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get RAG pipeline trace for a correlation ID.

    Note: This requires RAG pipeline to use RAGPipelineDebugger.

    Args:
        correlation_id: Correlation ID

    Returns:
        RAG pipeline trace
    """
    # TODO: Implement RAG pipeline trace storage
    return {
        "success": False,
        "message": "RAG pipeline tracing not yet implemented. Use RAGPipelineDebugger in pipeline.",
        "correlation_id": correlation_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/db/queries/slow")
async def get_slow_queries(
    limit: int = Query(50, ge=1, le=500),
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get slow database queries.

    Args:
        limit: Maximum number of queries to return

    Returns:
        Slow queries list
    """
    from app.utils.db_debugger import DatabaseQueryDebugger

    slow_queries = DatabaseQueryDebugger.get_slow_queries(limit=limit)

    return {
        "success": True,
        "queries": slow_queries,
        "count": len(slow_queries),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/db/queries/recent")
async def get_recent_queries(
    limit: int = Query(100, ge=1, le=1000),
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get recent database queries.

    Args:
        limit: Maximum number of queries to return

    Returns:
        Recent queries list
    """
    from app.utils.db_debugger import DatabaseQueryDebugger

    recent_queries = DatabaseQueryDebugger.get_recent_queries(limit=limit)

    return {
        "success": True,
        "queries": recent_queries,
        "count": len(recent_queries),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/db/queries/analyze")
async def analyze_query_patterns(
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Analyze database query patterns.

    Returns:
        Query pattern analysis
    """
    from app.utils.db_debugger import DatabaseQueryDebugger

    analysis = DatabaseQueryDebugger.analyze_query_patterns()

    return {
        "success": True,
        "analysis": analysis,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/qdrant/collections/health")
async def get_qdrant_collections_health(
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get health status of all Qdrant collections.

    Returns:
        Collections health status
    """
    from app.utils.qdrant_debugger import QdrantDebugger

    debugger = QdrantDebugger()
    health_statuses = await debugger.get_all_collections_health()

    return {
        "success": True,
        "collections": [
            {
                "name": h.name,
                "points_count": h.points_count,
                "vectors_count": h.vectors_count,
                "indexed": h.indexed,
                "status": h.status,
                "error": h.error,
            }
            for h in health_statuses
        ],
        "count": len(health_statuses),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/qdrant/collection/{collection_name}/stats")
async def get_collection_stats(
    collection_name: str,
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get detailed statistics for a Qdrant collection.

    Args:
        collection_name: Collection name

    Returns:
        Collection statistics
    """
    from app.utils.qdrant_debugger import QdrantDebugger

    debugger = QdrantDebugger()
    stats = await debugger.get_collection_stats(collection_name)

    return {
        "success": True,
        "stats": stats,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/parent-documents-public/{document_id}")
async def get_parent_documents_public(
    document_id: str,
) -> dict[str, Any]:
    """
    Get parent documents (BAB) from PostgreSQL for a legal document.
    PUBLIC endpoint for testing - NO AUTH REQUIRED.

    Args:
        document_id: Document ID (e.g. "PP_31_2013")

    Returns:
        List of BAB (chapters) with metadata
    """
    import asyncpg

    try:
        conn = await asyncpg.connect(settings.database_url, timeout=10)

        # Query parent_documents table
        rows = await conn.fetch(
            """
            SELECT id, document_id, type, title,
                   char_count, pasal_count,
                   created_at
            FROM parent_documents
            WHERE document_id = $1
            ORDER BY id
            """,
            document_id
        )

        await conn.close()

        results = []
        for row in rows:
            results.append({
                "id": row["id"],
                "document_id": row["document_id"],
                "type": row["type"],
                "title": row["title"],
                "char_count": row["char_count"],
                "pasal_count": row["pasal_count"],
                "created_at": str(row["created_at"]),
            })

        return {
            "success": True,
            "document_id": document_id,
            "total_bab": len(results),
            "bab_list": results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to query parent_documents: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/parent-documents/{document_id}/{bab_id}/text")
async def get_bab_full_text(
    document_id: str,
    bab_id: str,
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get full text of a specific BAB from PostgreSQL.

    Args:
        document_id: Document ID
        bab_id: BAB ID (e.g. "PP_31_2013_BAB_III")

    Returns:
        Full text of the BAB
    """
    import asyncpg

    try:
        conn = await asyncpg.connect(settings.database_url, timeout=10)

        row = await conn.fetchrow(
            """
            SELECT id, title, full_text,
                   char_count, pasal_count
            FROM parent_documents
            WHERE document_id = $1 AND id = $2
            """,
            document_id, bab_id
        )

        await conn.close()

        if not row:
            return {
                "success": False,
                "error": "BAB not found",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        return {
            "success": True,
            "id": row["id"],
            "title": row["title"],
            "char_count": row["char_count"],
            "pasal_count": row["pasal_count"],
            "full_text": row["full_text"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to query BAB text: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.post("/profile")
async def run_performance_profiling(
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Run performance profiling analysis.

    Note: This integrates with the existing performance_profiler.py script.
    For full analysis, use the script directly: python scripts/performance_profiler.py

    Returns:
        Profiling results summary
    """
    import sys
    from pathlib import Path

    # Import the profiler class
    profiler_script_path = Path(__file__).parent.parent.parent.parent.parent / "scripts" / "performance_profiler.py"

    if not profiler_script_path.exists():
        return {
            "success": False,
            "message": "Performance profiler script not found",
            "path": str(profiler_script_path),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    try:
        # Import profiler class
        sys.path.insert(0, str(profiler_script_path.parent))
        from performance_profiler import PerformanceProfiler

        # Run profiling
        profiler = PerformanceProfiler(base_url=f"http://localhost:{settings.port}")
        results = await profiler.run_profiling()

        return {
            "success": True,
            "results": {
                "priority_areas": results.get("priorities", {}),
                "database_analysis": results.get("database", {}),
                "code_patterns": results.get("code_patterns", {}),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Performance profiling failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "message": "Performance profiling failed. Use script directly: python scripts/performance_profiler.py",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ========================================
# PostgreSQL Debug Endpoints
# ========================================


class QueryRequest(BaseModel):
    """Request model for custom query execution"""

    query: str
    limit: int = 100


@router.get("/postgres/connection")
async def get_postgres_connection(
    request: Request,
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Test PostgreSQL connection and get connection info.

    Args:
        request: FastAPI request (to access app.state for pool)

    Returns:
        Connection information and status
    """
    from app.utils.postgres_debugger import PostgreSQLDebugger

    debugger = PostgreSQLDebugger()

    # Try to get pool from app.state if available
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        # Try memory_service pool
        memory_service = getattr(request.app.state, "memory_service", None)
        if memory_service and hasattr(memory_service, "pool"):
            pool = memory_service.pool

    try:
        conn_info = await debugger.test_connection(pool=pool)
        return {
            "success": True,
            "connection": {
                "connected": conn_info.connected,
                "version": conn_info.version,
                "database": conn_info.database,
                "user": conn_info.user,
                "pool_size": conn_info.pool_size,
                "pool_idle": conn_info.pool_idle,
                "pool_active": conn_info.pool_active,
            },
            "error": conn_info.error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"PostgreSQL connection test failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/postgres/schema/tables")
async def get_postgres_tables(
    schema: str = Query("public", description="Schema name"),
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get list of all tables in a schema.

    Args:
        schema: Schema name (default: public)

    Returns:
        List of tables
    """
    from app.utils.postgres_debugger import PostgreSQLDebugger

    debugger = PostgreSQLDebugger()

    try:
        tables = await debugger.get_tables(schema=schema)
        return {
            "success": True,
            "schema": schema,
            "tables": tables,
            "count": len(tables),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get tables: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/postgres/schema/table/{table_name}")
async def get_postgres_table_details(
    table_name: str,
    schema: str = Query("public", description="Schema name"),
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get detailed information about a table.

    Args:
        table_name: Table name
        schema: Schema name (default: public)

    Returns:
        Table details including columns, indexes, foreign keys, constraints
    """
    from app.utils.postgres_debugger import PostgreSQLDebugger

    debugger = PostgreSQLDebugger()

    try:
        table_info = await debugger.get_table_details(table_name=table_name, schema=schema)
        return {
            "success": True,
            "table": {
                "schema": table_info.schema,
                "name": table_info.name,
                "columns": table_info.columns,
                "indexes": table_info.indexes,
                "foreign_keys": table_info.foreign_keys,
                "constraints": table_info.constraints,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get table details: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/postgres/schema/indexes")
async def get_postgres_indexes(
    table_name: str | None = Query(None, description="Optional table name filter"),
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get list of all indexes.

    Args:
        table_name: Optional table name to filter indexes

    Returns:
        List of indexes
    """
    from app.utils.postgres_debugger import PostgreSQLDebugger

    debugger = PostgreSQLDebugger()

    try:
        indexes = await debugger.get_indexes(table_name=table_name)
        return {
            "success": True,
            "indexes": indexes,
            "count": len(indexes),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get indexes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/postgres/stats/tables")
async def get_postgres_table_stats(
    table_name: str | None = Query(None, description="Optional table name filter"),
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get statistics for tables (row counts, sizes, indexes).

    Args:
        table_name: Optional table name to filter stats

    Returns:
        Table statistics
    """
    from app.utils.postgres_debugger import PostgreSQLDebugger

    debugger = PostgreSQLDebugger()

    try:
        stats = await debugger.get_table_stats(table_name=table_name)
        return {
            "success": True,
            "stats": stats,
            "count": len(stats),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get table stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/postgres/stats/database")
async def get_postgres_database_stats(
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get global database statistics.

    Returns:
        Database statistics
    """
    from app.utils.postgres_debugger import PostgreSQLDebugger

    debugger = PostgreSQLDebugger()

    try:
        stats = await debugger.get_database_stats()
        return {
            "success": True,
            "stats": stats,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get database stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/postgres/query")
async def execute_postgres_query(
    query_request: QueryRequest = Body(...),
    request: Request = None,
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Execute a read-only query safely.

    Args:
        query_request: Query request with SQL and limit
        request: FastAPI request (to access app.state for pool)

    Returns:
        Query results
    """
    from app.utils.postgres_debugger import PostgreSQLDebugger

    debugger = PostgreSQLDebugger()

    # Try to get pool from app.state if available
    pool = None
    if request:
        pool = getattr(request.app.state, "db_pool", None)
        if pool is None:
            memory_service = getattr(request.app.state, "memory_service", None)
            if memory_service and hasattr(memory_service, "pool"):
                pool = memory_service.pool

    try:
        results = await debugger.execute_query(
            query=query_request.query, limit=query_request.limit, pool=pool
        )
        return {
            "success": True,
            **results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except ValueError as e:
        # Query validation failed
        logger.warning(f"Query validation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Query execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/postgres/performance/slow-queries")
async def get_postgres_slow_queries(
    limit: int = Query(20, ge=1, le=100, description="Maximum number of queries"),
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get slow queries from pg_stat_statements (if available).

    Args:
        limit: Maximum number of queries to return

    Returns:
        Slow queries list
    """
    from app.utils.postgres_debugger import PostgreSQLDebugger

    debugger = PostgreSQLDebugger()

    try:
        queries = await debugger.get_slow_queries(limit=limit)
        return {
            "success": True,
            "queries": queries,
            "count": len(queries),
            "extension_available": len(queries) > 0 or True,  # Will be empty if extension not available
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get slow queries: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/postgres/performance/locks")
async def get_postgres_locks(
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get active locks in the database.

    Returns:
        Active locks list
    """
    from app.utils.postgres_debugger import PostgreSQLDebugger

    debugger = PostgreSQLDebugger()

    try:
        locks = await debugger.get_active_locks()
        return {
            "success": True,
            "locks": locks,
            "count": len(locks),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get locks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/postgres/performance/connections")
async def get_postgres_connection_stats(
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Get connection statistics.

    Returns:
        Connection statistics
    """
    from app.utils.postgres_debugger import PostgreSQLDebugger

    debugger = PostgreSQLDebugger()

    try:
        stats = await debugger.get_connection_stats()
        return {
            "success": True,
            "stats": stats,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get connection stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# --- Sentry Test Endpoint (v1 compatibility) ---
@v1_router.get("/sentry-test")
async def sentry_test_error(
    _current_user: dict = Depends(get_current_user),
):
    """
    Trigger a test error for Sentry monitoring verification.
    This endpoint intentionally raises an exception to test Sentry integration.

    SECURITY: Requires authentication to prevent abuse.
    """
    logger.warning("🧪 Sentry test endpoint triggered - about to raise exception")
    # This will be caught by Sentry
    raise ValueError(
        "🧪 TEST ERROR: This is a controlled test error for Sentry verification. If you see this in Sentry, the integration is working correctly!"
    )


