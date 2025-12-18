# Phase 1 Execution Guide

**Date**: 2025-12-17  
**Purpose**: Step-by-step guide to execute Phase 1 fixes and benchmarks

## Prerequisites

1. **Backend Running**: Ensure backend is running on `http://localhost:8000` (or set `BACKEND_URL`)
2. **Database Access**: Ensure `DATABASE_URL` environment variable is set
3. **Dependencies**: All Python dependencies installed

## Step 1: Apply Migration 022

Migration 022 adds performance indexes. Check if already applied:

```bash
cd apps/backend-rag/backend
python migrations/migration_022.py
```

**Expected Output**:
```
Migration 022 completed and verified
```

**If migration already applied**:
```
Migration 022 already applied, skipping
```

**Verify indexes exist**:
```sql
-- Connect to PostgreSQL and run:
SELECT indexname FROM pg_indexes 
WHERE indexname IN (
    'idx_memory_facts_user_id',
    'idx_memory_facts_user_created',
    'idx_user_stats_user_id',
    'idx_conversations_user_id',
    'idx_conversations_user_updated'
);
```

---

## Step 2: Verify Fixes Are Deployed

Check that code changes are in place:

```bash
# Check GoldenAnswerService pool size
grep -A 2 "max_size=" apps/backend-rag/backend/services/golden_answer_service.py
# Should show: max_size=20

# Check early exit implementation
grep -A 5 "Early exit" apps/backend-rag/backend/services/search_service.py
# Should show early exit logic

# Check metrics are added
grep "zantara_rag_" apps/backend-rag/backend/app/metrics.py
# Should show new RAG metrics
```

---

## Step 3: Run Baseline Benchmark

**Before deploying fixes** (if you have a baseline version):

```bash
cd /Users/antonellosiano/Desktop/nuzantara
python scripts/benchmark_performance.py --baseline --base-url http://localhost:8000
```

**Expected Output**:
```
📊 Running BASELINE benchmark...
🔍 Benchmarking RAG search: 'What is a KITAS visa?' (5 iterations)
...
✅ Baseline benchmark complete: docs/debug/performance/benchmarks/benchmark_baseline_YYYYMMDD_HHMMSS.json
```

**Note**: If backend is not running, you'll see connection errors. Start backend first.

---

## Step 4: Deploy Fixes to Production

### Option A: Local Testing
```bash
# Restart backend to load new code
cd apps/backend-rag
# Restart your backend server (method depends on your setup)
```

### Option B: Production Deployment
```bash
# Deploy via Fly.io (example)
fly deploy --app nuzantara-rag

# Or via your CI/CD pipeline
git push origin main
```

**Verify deployment**:
```bash
# Check Prometheus metrics endpoint
curl http://localhost:8000/metrics | grep zantara_rag_
# Should show new metrics
```

---

## Step 5: Run Comparison Benchmark

**After deploying fixes**:

```bash
cd /Users/antonellosiano/Desktop/nuzantara
python scripts/benchmark_performance.py --compare --base-url http://localhost:8000
```

**Expected Output**:
```
📊 Running COMPARISON benchmark...
...
✅ Comparison benchmark complete: docs/debug/performance/benchmarks/benchmark_compare_YYYYMMDD_HHMMSS.json
```

**Compare both**:
```bash
python scripts/benchmark_performance.py --both --base-url http://localhost:8000
```

This will automatically compare baseline vs comparison and show improvements.

---

## Step 6: Monitor Prometheus Metrics

### Access Metrics Endpoint

```bash
# Get all metrics
curl http://localhost:8000/metrics

# Get specific RAG metrics
curl http://localhost:8000/metrics | grep zantara_rag_

# Get database metrics
curl http://localhost:8000/metrics | grep zantara_db_
```

### Key Metrics to Monitor

#### RAG Pipeline Metrics
- `zantara_rag_pipeline_duration_seconds` - Total pipeline time (histogram)
- `zantara_rag_embedding_duration_seconds` - Embedding generation time
- `zantara_rag_vector_search_duration_seconds` - Vector search time
- `zantara_rag_reranking_duration_seconds` - Reranking time
- `zantara_rag_early_exit_total` - Early exit counter (should increase)
- `zantara_rag_parallel_searches_total` - Parallel searches executed

#### Database Metrics
- `zantara_db_pool_size{service="golden_answer"}` - Pool size (should be 20)
- `zantara_db_pool_idle{service="golden_answer"}` - Idle connections
- `zantara_db_query_duration_seconds` - Query performance

### Example Queries

**Average pipeline duration**:
```promql
rate(zantara_rag_pipeline_duration_seconds_sum[5m]) / rate(zantara_rag_pipeline_duration_seconds_count[5m])
```

**Early exit rate**:
```promql
rate(zantara_rag_early_exit_total[5m])
```

**Database pool utilization**:
```promql
zantara_db_pool_size - zantara_db_pool_idle
```

---

## Step 7: Verify Expected Improvements

### Expected Results

| Metric | Baseline | Target | How to Verify |
|--------|----------|--------|---------------|
| RAG Pipeline Time | ~350ms | <280ms | Check `zantara_rag_pipeline_duration_seconds` p95 |
| Database Query Time | ~50ms | <35ms | Check `zantara_db_query_duration_seconds` p95 |
| Early Exit Rate | 0% | >30% | `rate(zantara_rag_early_exit_total[5m])` / total queries |
| Connection Pool Wait | Unknown | <10ms | Monitor pool idle connections |

### Benchmark Comparison

Compare benchmark JSON files:

```python
import json
from pathlib import Path

baseline = json.loads(Path("docs/debug/performance/benchmarks/benchmark_baseline_*.json").read_text())
compare = json.loads(Path("docs/debug/performance/benchmarks/benchmark_compare_*.json").read_text())

baseline_mean = baseline["summary"]["rag_pipeline"]["mean_time"]
compare_mean = compare["summary"]["rag_pipeline"]["mean_time"]

improvement = ((baseline_mean - compare_mean) / baseline_mean) * 100
print(f"Improvement: {improvement:.1f}%")
```

---

## Troubleshooting

### Backend Not Running

**Error**: `All connection attempts failed`

**Solution**:
```bash
# Start backend (method depends on your setup)
cd apps/backend-rag
# Option 1: Direct Python
python -m uvicorn app.main_cloud:app --host 0.0.0.0 --port 8000

# Option 2: Docker
docker-compose up backend

# Option 3: Fly.io
fly ssh console -a nuzantara-rag
```

### DATABASE_URL Not Set

**Error**: `ERROR: DATABASE_URL environment variable not set`

**Solution**:
```bash
# Set environment variable
export DATABASE_URL="postgresql://user:pass@host:port/dbname"

# Or use .env file
source .env
```

### Migration Already Applied

**Message**: `Migration 022 already applied, skipping`

**Status**: ✅ This is OK! Migration is idempotent and safe to run multiple times.

### Metrics Not Showing

**Issue**: New metrics not appearing in `/metrics` endpoint

**Solution**:
1. Verify code changes are deployed
2. Restart backend to load new code
3. Make some requests to trigger metric collection
4. Check Prometheus endpoint again

---

## Next Steps After Verification

1. **Document Results**: Update `PHASE1_IMPLEMENTATION.md` with actual improvements
2. **Create Grafana Dashboard**: Visualize metrics for ongoing monitoring
3. **Set Up Alerts**: Alert on performance degradation
4. **Plan Phase 2**: Proceed with LLM API optimizations (Phase 2)

---

## Quick Reference

```bash
# Apply migration
cd apps/backend-rag/backend && python migrations/migration_022.py

# Run baseline
python scripts/benchmark_performance.py --baseline

# Run comparison
python scripts/benchmark_performance.py --compare

# Run both and compare
python scripts/benchmark_performance.py --both

# Check metrics
curl http://localhost:8000/metrics | grep zantara_rag_
```

---

**Status**: Ready for execution when backend is available

