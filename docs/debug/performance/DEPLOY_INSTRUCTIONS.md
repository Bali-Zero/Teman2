# Deploy Instructions - Phase 1 Performance Optimizations

**Status**: ✅ Code Ready, Backend Running Well  
**Date**: 2025-12-17

## Quick Deploy Commands

### 1. Commit Changes

```bash
cd /Users/antonellosiano/Desktop/nuzantara

# Stage all performance-related changes
git add apps/backend-rag/backend/services/golden_answer_service.py
git add apps/backend-rag/backend/services/search_service.py
git add apps/backend-rag/backend/app/metrics.py
git add scripts/benchmark_performance.py
git add scripts/performance_profiler.py
git add docs/debug/performance/

# Commit
git commit -m "perf: Phase 1 performance optimizations - Database & RAG Pipeline

- Increase GoldenAnswerService connection pool (min=5, max=20)
- Add early exit for reranking when score > 0.9
- Add Prometheus metrics for RAG pipeline performance tracking
- Implement performance monitoring for embedding, search, reranking
- Add benchmark script for before/after comparison
- Add comprehensive performance debugging documentation

Expected improvements:
- RAG Pipeline: -20% total time
- Database Query: -30% query time  
- Early Exit Rate: >30% of queries
- Connection Pool: no wait time

See docs/debug/performance/ for details"
```

### 2. Push to Remote

```bash
# Push to current branch (usually main or master)
git push origin $(git rev-parse --abbrev-ref HEAD)

# Or push to main explicitly
git push origin main
```

### 3. Deploy to Fly.io

```bash
# Navigate to backend directory
cd apps/backend-rag

# Deploy to Fly.io
fly deploy --app nuzantara-rag

# Or if fly.toml is in root
cd /Users/antonellosiano/Desktop/nuzantara
fly deploy --app nuzantara-rag
```

### 4. Monitor Deployment

```bash
# Check deployment status
fly status --app nuzantara-rag

# View logs
fly logs --app nuzantara-rag

# Monitor metrics endpoint
curl https://nuzantara-rag.fly.dev/metrics | grep zantara_rag_
```

## Alternative: Use Deploy Script

```bash
# Run automated deploy script
bash scripts/deploy_phase1_performance.sh
```

## Post-Deployment Verification

### 1. Check Metrics Endpoint

```bash
# Get all metrics
curl https://nuzantara-rag.fly.dev/metrics

# Check specific RAG metrics
curl https://nuzantara-rag.fly.dev/metrics | grep zantara_rag_pipeline_duration
curl https://nuzantara-rag.fly.dev/metrics | grep zantara_rag_early_exit
curl https://nuzantara-rag.fly.dev/metrics | grep zantara_db_pool_size
```

### 2. Run Benchmark Comparison

```bash
python scripts/benchmark_performance.py --compare --base-url https://nuzantara-rag.fly.dev
```

### 3. Verify Improvements

Monitor these metrics:
- `zantara_rag_pipeline_duration_seconds` - Should decrease by ~20%
- `zantara_rag_early_exit_total` - Should increase (early exits happening)
- `zantara_db_pool_size` - Should show max=20 for golden_answer service
- `zantara_db_query_duration_seconds` - Should decrease by ~30%

## Expected Results

After deployment, you should see:

✅ **RAG Pipeline**: 20-30% faster  
✅ **Database Queries**: 30-50% faster  
✅ **Early Exits**: >30% of queries skip reranking  
✅ **Connection Pool**: No wait times, better concurrency  

## Troubleshooting

### If deployment fails:

1. **Check Fly.io status**:
   ```bash
   fly status --app nuzantara-rag
   ```

2. **Check logs**:
   ```bash
   fly logs --app nuzantara-rag
   ```

3. **Verify migration 022**:
   ```bash
   fly ssh console -a nuzantara-rag
   python -m migrations.migration_022
   ```

### If metrics not showing:

1. Restart backend to load new code
2. Make some API requests to trigger metric collection
3. Wait a few minutes for Prometheus to scrape metrics

---

**Ready to Deploy**: ✅ Yes  
**Backend Status**: 🚂 Running like a train!


