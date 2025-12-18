# Performance Profiling Report
Generated: 2025-12-17T19:43:00.878258

## Executive Summary

This report identifies performance bottlenecks in the Nuzantara codebase, organized by priority (critical → warning → info).

## Priority Areas

### 🔴 CRITICAL Priority

#### Rag Pipeline
- **Score**: 100/100
- **Reason**: Core functionality, high frequency, CPU/IO intensive
- **Impact**: Blocks entire system if slow

#### Database
- **Score**: 100/100
- **Reason**: Connection pool issues, N+1 queries
- **Impact**: Can cause timeouts and connection exhaustion

#### Llm Api
- **Score**: 85/100
- **Reason**: External API calls, rate limiting, timeouts
- **Impact**: Blocks user requests, high latency

### 🟡 WARNING Priority

#### Memory
- **Score**: 60/100
- **Reason**: Cache hit rate, query optimization
- **Impact**: Affects UX but doesn't block

#### Agentic
- **Score**: 55/100
- **Reason**: Multi-step reasoning overhead
- **Impact**: Slower responses but functional

### 🟢 INFO Priority

#### Code Quality
- **Score**: 35/100
- **Reason**: Found 5 code quality issues
- **Impact**: Minor optimizations

## Detailed Findings

### Database Analysis

#### Connection Pools
- **services/memory_service_postgres.py**: min=5, max=50
  - Utilization risk: medium
- **services/golden_answer_service.py**: min=2, max=10
  - Utilization risk: high

#### Potential N+1 Query Patterns
- **backend-rag/backend/migrations/migration_019.py**:92
- **backend-rag/backend/migrations/migration_018.py**:72
- **backend-rag/backend/migrations/migration_013.py**:31
- **backend-rag/backend/migrations/migration_022.py**:93
- **backend-rag/backend/migrations/migration_021.py**:101
- **backend-rag/backend/migrations/migration_014.py**:31

### Code Pattern Analysis

#### Blocking Calls
- **backend-rag/backend/verify_chat.py**:11 - blocking HTTP call
- **backend-rag/backend/verify_chat.py**:25 - blocking HTTP call
- **backend-rag/backend/verify_streaming.py**:19 - blocking HTTP call
- **backend-rag/backend/verify_route.py**:15 - blocking HTTP call
- **backend-rag/backend/app/routers/oracle_ingest.py**:95 - blocking HTTP call

## Next Steps

1. Review critical priority areas first
2. Create task files for each Composer
3. Run parallel debugging sessions
4. Measure improvements with benchmarks
