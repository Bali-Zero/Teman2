# Testing Guide - Post Cleanup Refactoring

## Overview

This guide documents the testing procedures for verifying that all endpoints and services work correctly after the cleanup refactoring.

## Prerequisites

1. **Environment Setup**
   ```bash
   cd apps/backend-rag
   # Ensure all dependencies are installed
   pip install -r requirements.txt
   ```

2. **Start the Development Server**
   ```bash
   npm run dev
   # OR
   cd backend && uvicorn app.main_cloud:app --reload
   ```

3. **Verify Environment Variables**
   - `DATABASE_URL` - PostgreSQL connection string
   - `QDRANT_URL` - Qdrant vector database URL
   - `JWT_SECRET_KEY` - JWT secret (min 32 chars in production)
   - `API_KEYS` - Comma-separated API keys
   - Other required env vars (see `app/core/config.py`)

## Test Scripts

### 1. Endpoint Testing Script

**Location**: `scripts/test_endpoints.py`

**Usage**:
```bash
python scripts/test_endpoints.py [base_url] [api_key]
```

**Example**:
```bash
# Test against local server
python scripts/test_endpoints.py http://localhost:8000

# Test with API key
python scripts/test_endpoints.py http://localhost:8000 your_api_key
```

**What it tests**:
- ✅ Configuration validation
- ✅ Health endpoint (`/health`)
- ✅ Detailed health endpoint (`/health/detailed`)
- ✅ Readiness probe (`/health/ready`)
- ✅ Liveness probe (`/health/live`)
- ✅ Agent endpoints (if API key provided)

### 2. Health Check Script

**Location**: `scripts/health_check.py`

**Usage**:
```bash
python scripts/health_check.py
```

**What it tests**:
- Database connectivity
- Qdrant connectivity
- Service initialization
- Model availability

## Manual Testing Checklist

### Health Endpoints

1. **Basic Health Check**
   ```bash
   curl http://localhost:8000/health
   ```
   Expected: `200 OK` with `status: "healthy"` or `"initializing"`

2. **Detailed Health**
   ```bash
   curl http://localhost:8000/health/detailed
   ```
   Expected: `200 OK` with detailed service status

3. **Readiness Probe**
   ```bash
   curl http://localhost:8000/health/ready
   ```
   Expected: `200 OK` if ready, `503` if not ready

4. **Liveness Probe**
   ```bash
   curl http://localhost:8000/health/live
   ```
   Expected: `200 OK` always (if server is running)

### Agent Endpoints

1. **Conversation Trainer**
   ```bash
   curl -X POST http://localhost:8000/api/autonomous-agents/conversation-trainer/run \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -d '{"days_back": 7}'
   ```
   Expected: `200 OK` or `202 Accepted` with execution ID

2. **Knowledge Graph Builder**
   ```bash
   curl -X POST http://localhost:8000/api/autonomous-agents/knowledge-graph/run \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer YOUR_API_KEY" \
     -d '{"days_back": 30, "init_schema": false}'
   ```
   Expected: `200 OK` or `202 Accepted` with execution ID

## Performance Monitoring

### Key Metrics to Monitor

1. **Database Connection Pool**
   - Check pool size and usage
   - Monitor connection acquisition time
   - Verify no connection leaks

2. **Async Operations**
   - Verify all database operations are async
   - Check for blocking operations in event loop
   - Monitor response times

3. **Agent Performance**
   - Batch processing efficiency (N+1 query fixes)
   - Retry logic effectiveness
   - Timeout handling

### Monitoring Commands

```bash
# Check database pool status (via detailed health)
curl http://localhost:8000/health/detailed | jq '.services.database'

# Monitor logs for async operations
tail -f logs/app.log | grep -i "async\|await\|pool"
```

## Common Issues & Solutions

### Issue: Health endpoint returns "initializing"

**Cause**: Services not fully initialized yet

**Solution**: Wait for startup to complete (check logs)

### Issue: Agent endpoints return 401

**Cause**: Missing or invalid API key

**Solution**: Provide valid API key in Authorization header

### Issue: Database connection errors

**Cause**: 
- `DATABASE_URL` not set or incorrect
- Database not accessible
- Connection pool exhausted

**Solution**:
- Verify `DATABASE_URL` environment variable
- Check database connectivity
- Review connection pool configuration

### Issue: Import errors

**Cause**: Python path not configured correctly

**Solution**: 
- Ensure `PYTHONPATH` includes backend directory
- Run from project root or use `python -m` syntax

## Expected Performance Improvements

After the cleanup refactoring, you should see:

1. **Database Operations**
   - ✅ Faster query execution (asyncpg vs psycopg2)
   - ✅ Better connection pool utilization
   - ✅ Reduced N+1 query problems

2. **Agent Performance**
   - ✅ Batch processing reduces database load
   - ✅ Retry logic improves resilience
   - ✅ Timeouts prevent hanging operations

3. **Dependency Injection**
   - ✅ Cleaner code structure
   - ✅ Easier testing
   - ✅ Better service lifecycle management

## Next Steps

1. Run full test suite: `npm test`
2. Monitor production metrics
3. Review performance improvements
4. Consider refactoring God Objects (P1 task)

## References

- [Cleanup Implementation Summary](../CLEANUP_IMPLEMENTATION_SUMMARY.md)
- [Architecture Documentation](../ARCHITECTURE.md)
- [Config Documentation](../app/core/config.py)



























