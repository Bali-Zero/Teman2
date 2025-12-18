# Debug Guide for Nuzantara Prime

This guide explains how to use the debug tools and endpoints available in Nuzantara Prime.

## Overview

Nuzantara Prime includes comprehensive debugging tools for troubleshooting and monitoring:

- **Request Tracing**: End-to-end request tracking with correlation IDs
- **RAG Pipeline Debugger**: Trace RAG pipeline execution
- **Database Query Debugger**: Monitor PostgreSQL queries and identify performance issues
- **PostgreSQL Debugger**: Comprehensive PostgreSQL database inspection (schema, statistics, performance)
- **Qdrant Debugger**: Analyze vector database collections and queries
- **Debug Endpoints**: REST API endpoints for accessing debug information

## Security

⚠️ **IMPORTANT**: All debug endpoints require authentication:

- Available in all environments (including production) when `ADMIN_API_KEY` is configured
- Require `ADMIN_API_KEY` (Bearer token or `X-Debug-Key` header)
- Rate limited to prevent abuse
- In production, endpoints are only accessible if `ADMIN_API_KEY` is set in environment variables

## Debug Endpoints

All debug endpoints are under `/api/debug/*`:

### Request Tracing

#### Get Request Trace
```bash
GET /api/debug/request/{request_id}
Authorization: Bearer {ADMIN_API_KEY}
```

Returns complete trace for a specific request, including:
- Correlation ID
- Request path and method
- Duration
- Steps executed
- Errors (if any)

#### Get Recent Traces
```bash
GET /api/debug/traces/recent?limit=50
Authorization: Bearer {ADMIN_API_KEY}
```

Returns recent request traces (up to 500).

#### Clear Traces
```bash
DELETE /api/debug/traces
Authorization: Bearer {ADMIN_API_KEY}
```

Clears all stored traces from memory.

### Application State

#### Get Application State
```bash
GET /api/debug/state
Authorization: Bearer {ADMIN_API_KEY}
```

Returns internal application state:
- Service availability
- Initialization status
- Current correlation ID

#### Get Services Status
```bash
GET /api/debug/services
Authorization: Bearer {ADMIN_API_KEY}
```

Returns status of all services:
- SearchService
- AI Client
- Database Pool
- Memory Service
- Intelligent Router
- Health Monitor

### Database Debugging

#### Get Slow Queries
```bash
GET /api/debug/db/queries/slow?limit=50
Authorization: Bearer {ADMIN_API_KEY}
```

Returns slow database queries (default threshold: 1000ms).

#### Get Recent Queries
```bash
GET /api/debug/db/queries/recent?limit=100
Authorization: Bearer {ADMIN_API_KEY}
```

Returns recent database queries with timing information.

#### Analyze Query Patterns
```bash
GET /api/debug/db/queries/analyze
Authorization: Bearer {ADMIN_API_KEY}
```

Analyzes query patterns to identify:
- N+1 query patterns
- Missing indexes
- Slow query patterns

### PostgreSQL Debugging (Advanced)

Comprehensive PostgreSQL database inspection and debugging endpoints:

#### Test Connection
```bash
GET /api/debug/postgres/connection
Authorization: Bearer {ADMIN_API_KEY}
```

Returns connection status, PostgreSQL version, database name, user, and pool statistics (if using connection pool).

#### Schema Inspection

**List Tables:**
```bash
GET /api/debug/postgres/schema/tables?schema=public
Authorization: Bearer {ADMIN_API_KEY}
```

**Get Table Details:**
```bash
GET /api/debug/postgres/schema/table/{table_name}?schema=public
Authorization: Bearer {ADMIN_API_KEY}
```

Returns detailed table information:
- Columns (name, type, nullable, default, constraints)
- Indexes (name, definition, columns)
- Foreign keys (constraints, references)
- Constraints (primary keys, unique, check)

**List Indexes:**
```bash
GET /api/debug/postgres/schema/indexes?table_name={table_name}
Authorization: Bearer {ADMIN_API_KEY}
```

#### Database Statistics

**Table Statistics:**
```bash
GET /api/debug/postgres/stats/tables?table_name={table_name}
Authorization: Bearer {ADMIN_API_KEY}
```

Returns:
- Row counts
- Table size
- Indexes size
- Total size
- Index count

**Database Statistics:**
```bash
GET /api/debug/postgres/stats/database
Authorization: Bearer {ADMIN_API_KEY}
```

Returns global database statistics:
- Database name and version
- Total database size
- Connection counts (total, active, idle)

#### Query Execution (Read-Only)

Execute custom SELECT queries safely:

```bash
POST /api/debug/postgres/query
Authorization: Bearer {ADMIN_API_KEY}
Content-Type: application/json

{
  "query": "SELECT * FROM users LIMIT 10",
  "limit": 100
}
```

**Security Features:**
- Only SELECT queries allowed
- Forbidden keywords blocked (DROP, DELETE, UPDATE, INSERT, CREATE, ALTER, etc.)
- Maximum timeout: 30 seconds
- Maximum rows: 1000 (enforced automatically)

#### Performance Metrics

**Slow Queries (from pg_stat_statements):**
```bash
GET /api/debug/postgres/performance/slow-queries?limit=20
Authorization: Bearer {ADMIN_API_KEY}
```

Returns slow queries from `pg_stat_statements` extension (if available):
- Query text
- Execution count
- Total, mean, max, min execution time
- Standard deviation

**Active Locks:**
```bash
GET /api/debug/postgres/performance/locks
Authorization: Bearer {ADMIN_API_KEY}
```

Returns active database locks:
- Lock type and mode
- Relation (table) name
- Process ID
- Username and application
- Lock state

**Connection Statistics:**
```bash
GET /api/debug/postgres/performance/connections
Authorization: Bearer {ADMIN_API_KEY}
```

Returns connection statistics:
- Total connections
- Connections by state (active, idle, idle in transaction)
- Long-running queries count
- Idle in transaction count

### Qdrant Debugging

#### Get Collections Health
```bash
GET /api/debug/qdrant/collections/health
Authorization: Bearer {ADMIN_API_KEY}
```

Returns health status of all Qdrant collections:
- Points count
- Vectors count
- Index status
- Collection status

#### Get Collection Stats
```bash
GET /api/debug/qdrant/collection/{collection_name}/stats
Authorization: Bearer {ADMIN_API_KEY}
```

Returns detailed statistics for a specific collection.

## Using Debug Utilities in Code

### Request Tracing

The `RequestTracingMiddleware` automatically adds correlation IDs to all requests. Access it in your code:

```python
from middleware.request_tracing import get_correlation_id

# In your endpoint
correlation_id = get_correlation_id(request)
```

### RAG Pipeline Debugger

Trace RAG pipeline execution:

```python
from app.utils.rag_debugger import RAGPipelineDebugger

debugger = RAGPipelineDebugger(query="...", correlation_id="...")

with debugger.step("embedding"):
    embedding = embed_query(query)

with debugger.step("search"):
    results = search_service.search(query, embedding)

debugger.add_documents(results, stage="retrieved")
trace = debugger.finish(response)
```

### Database Query Debugger

Trace database queries:

```python
from app.utils.db_debugger import DatabaseQueryDebugger

debugger = DatabaseQueryDebugger()

with debugger.trace_query(query, params):
    result = await conn.fetch(query, *params)
```

### Qdrant Debugger

Debug Qdrant collections:

```python
from app.utils.qdrant_debugger import QdrantDebugger

debugger = QdrantDebugger()
health = await debugger.get_collection_health("legal_unified")
stats = await debugger.get_collection_stats("legal_unified")
```

### PostgreSQL Debugger

Debug PostgreSQL database programmatically:

```python
from app.utils.postgres_debugger import PostgreSQLDebugger

debugger = PostgreSQLDebugger()

# Test connection
conn_info = await debugger.test_connection()
print(f"Connected: {conn_info.connected}, Version: {conn_info.version}")

# Get tables
tables = await debugger.get_tables(schema="public")

# Get table details
table_info = await debugger.get_table_details(table_name="users", schema="public")
print(f"Columns: {len(table_info.columns)}, Indexes: {len(table_info.indexes)}")

# Get database statistics
db_stats = await debugger.get_database_stats()
print(f"Database: {db_stats['database']}, Size: {db_stats['size']}")

# Execute read-only query (validated for safety)
results = await debugger.execute_query("SELECT COUNT(*) FROM users", limit=10)
print(f"Rows returned: {results['row_count']}")

# Get slow queries (if pg_stat_statements is enabled)
slow_queries = await debugger.get_slow_queries(limit=20)

# Get active locks
locks = await debugger.get_active_locks()
```

### OpenTelemetry Tracing

Use OpenTelemetry spans for distributed tracing:

```python
from app.utils.tracing import trace_span, set_span_attribute

with trace_span("rag_search", attributes={"query": query}):
    results = search_service.search(query)
    set_span_attribute("results_count", len(results))
```

## Debug Context Manager

Enable debug mode for specific operations:

```python
from app.utils.debug_context import debug_mode

with debug_mode(request_id="abc123", enable_verbose_logging=True):
    # All operations here will have enhanced logging
    result = some_operation()
```

## Troubleshooting Common Issues

### Request Not Found

If a request trace is not found:
- Check that the request was made after the server started
- Traces are stored in memory (max 1000 traces)
- Use `/api/debug/traces/recent` to see available traces

### Slow Queries

To identify slow queries:
1. Use `/api/debug/db/queries/slow` to see slow queries
2. Use `/api/debug/db/queries/analyze` to identify patterns
3. Check for N+1 patterns or missing indexes

### Qdrant Issues

To debug Qdrant:
1. Check collection health: `/api/debug/qdrant/collections/health`
2. Inspect specific collection: `/api/debug/qdrant/collection/{name}/stats`
3. Verify Qdrant URL and API key in configuration

### Missing Traces

If traces are missing:
- Ensure `RequestTracingMiddleware` is registered in `main_cloud.py`
- Check that correlation IDs are being passed between services
- Verify OpenTelemetry is configured (optional)

## Performance Considerations

- Debug endpoints are rate limited
- Traces are stored in memory (limited to 1000)
- Query logging may impact performance (use selectively)
- Debug mode increases logging verbosity

## Examples

### Example: Debugging a Slow Request

```bash
# 1. Get request ID from response headers
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
  https://api.example.com/api/oracle/query

# Response includes: X-Request-ID: abc-123-def

# 2. Get trace for that request
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
  https://api.example.com/api/debug/request/abc-123-def

# 3. Check slow queries
curl -H "Authorization: Bearer $ADMIN_API_KEY" \
  https://api.example.com/api/debug/db/queries/slow
```

### Example: Debugging RAG Pipeline

```python
from app.utils.rag_debugger import RAGPipelineDebugger

async def search_with_debug(query: str, correlation_id: str):
    debugger = RAGPipelineDebugger(query=query, correlation_id=correlation_id)
    
    with debugger.step("embedding"):
        embedding = await embed_query(query)
    
    with debugger.step("search"):
        results = await search_service.search(query, embedding)
        debugger.add_documents(results.get("results", []), stage="retrieved")
    
    with debugger.step("rerank"):
        reranked = await rerank_service.rerank(results)
        debugger.add_documents(reranked, stage="reranked")
    
    trace = debugger.finish()
    return trace
```

## Additional Resources

- [Architecture Documentation](./ARCHITECTURE.md)
- [Health Check Endpoints](./HEALTH_CHECKS.md)
- [Performance Profiling](./PERFORMANCE.md)

