# Optimization Monitoring Guide - Phase 1.1 & 1.2

## Quick Start

### Monitor Phase 1.1 (Parallel Context Loading)

```bash
# Quick check
flyctl logs -a nuzantara-rag | grep "PARALLEL LOADING" | tail -10

# Detailed metrics
flyctl logs -a nuzantara-rag | grep -E "Profile fetch|Memory fetch|speedup:" | tail -20
```

### Monitor Phase 1.2 (Parallel Entity + KG)

```bash
# Quick check
flyctl logs -a nuzantara-rag | grep "PARALLEL Entity" | tail -10

# Detailed metrics
flyctl logs -a nuzantara-rag | grep -E "Entity extraction|KG retrieval|PARALLEL Entity" | tail -20
```

## Expected Log Patterns

### Phase 1.1 Success Pattern

```
⏱️  [ContextManager] Profile fetch: 0.234s
⏱️  [ContextManager] Memory fetch: 0.312s
⚡ [ContextManager] PARALLEL LOADING completed in 0.315s (DB: 0.234s, Memory: 0.312s, speedup: ~0.231s vs sequential ~0.546s)
```

**Interpretation:**

- Profile: 234ms
- Memory: 312ms
- Parallel total: 315ms (max of the two)
- Sequential would be: 546ms
- **Speedup: 231ms** ✅

### Phase 1.2 Success Pattern

```
⏱️  [Orchestrator] Entity extraction: 0.085s
⏱️  [Orchestrator] KG retrieval: 0.142s
⚡ [Orchestrator] PARALLEL Entity+KG completed in 0.145s (Entity: 0.085s, KG: 0.142s, speedup: ~0.082s vs sequential ~0.227s)
```

**Interpretation:**

- Entity: 85ms
- KG: 142ms
- Parallel total: 145ms (max of the two)
- Sequential would be: 227ms
- **Speedup: 82ms** ✅

## Combined Improvement

**Total Pre-ReAct Latency Reduction:**

- Phase 1.1: ~231ms
- Phase 1.2: ~82ms
- **Combined: ~313ms reduction** 🚀

## Monitoring Scripts

### Automated Monitoring

```bash
# Run monitoring script (if available)
./scripts/monitoring/monitor_phase_1_1.sh

# Or manually extract metrics
flyctl logs -a nuzantara-rag | grep "speedup:" | awk -F'speedup:' '{print $2}' | awk '{print $1}'
```

### Extract Average Speedup

```bash
# Phase 1.1 average speedup
flyctl logs -a nuzantara-rag | grep "PARALLEL LOADING" | grep -oP 'speedup: ~\K[\d.]+' | awk '{sum+=$1; count++} END {if(count>0) print "Average:", sum/count, "s"}'

# Phase 1.2 average speedup
flyctl logs -a nuzantara-rag | grep "PARALLEL Entity" | grep -oP 'speedup: ~\K[\d.]+' | awk '{sum+=$1; count++} END {if(count>0) print "Average:", sum/count, "s"}'
```

## TTFT Measurement

### Before Optimization

```
TTFT Baseline:
├── Context Loading: ~700ms (sequential)
├── Entity + KG: ~250ms (sequential)
├── Gates + Cache: ~100ms
└── Total: ~1050ms
```

### After Optimization (Phase 1.1 + 1.2)

```
TTFT Optimized:
├── Context Loading: ~400ms (parallel, Phase 1.1)
├── Entity + KG: ~150ms (parallel, Phase 1.2)
├── Gates + Cache: ~100ms
└── Total: ~650ms
```

**Improvement: ~400ms reduction (38% faster)** 🎯

## Error Monitoring

### Check for Failures

```bash
# Phase 1.1 errors
flyctl logs -a nuzantara-rag | grep -E "Profile fetch failed|Memory fetch failed"

# Phase 1.2 errors
flyctl logs -a nuzantara-rag | grep -E "Entity extraction failed|KG retrieval failed"
```

### Expected Behavior

- **Phase 1.1:** If Profile fails, Memory continues (and vice versa)
- **Phase 1.2:** If Entity fails, KG continues (and vice versa)
- System should continue functioning even with partial failures

## Success Criteria

### Phase 1.1 ✅

- [x] Average speedup > 200ms
- [x] No increase in error rate
- [x] Timing metrics visible in logs

### Phase 1.2 ✅

- [ ] Average speedup > 50ms
- [ ] No increase in error rate
- [ ] Entity extraction still fast (<100ms)

### Combined ✅

- [ ] Total TTFT reduction > 300ms
- [ ] No regressions in functionality
- [ ] All tests passing

## Troubleshooting

### No Metrics in Logs

**Possible causes:**

1. No queries processed yet → Make a test query
2. Log level too high → Check LOG_LEVEL setting
3. Metrics not being logged → Verify code deployed correctly

**Solution:**

```bash
# Trigger a query to generate metrics
curl -X POST https://nuzantara-rag.fly.dev/api/agentic-rag/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "What is KITAS?", "user_id": "test@example.com"}'

# Then check logs
flyctl logs -a nuzantara-rag | grep "PARALLEL"
```

### Low Speedup

**Possible causes:**

1. Network latency dominates (DB/Memory are fast)
2. One operation is much faster than the other
3. Overhead from parallelization

**Analysis:**

- Check individual timings (Profile vs Memory, Entity vs KG)
- If one is much faster, speedup will be limited
- This is expected behavior - parallelization helps when operations are similar in duration

## Next Steps

1. **Monitor Phase 1.1** for 24 hours
2. **Deploy Phase 1.2** (in progress)
3. **Verify combined improvement**
4. **Proceed to Phase 1.3** (Parallel Tool Execution) if successful

## References

- **Phase 1.1 Docs:** `docs/PHASE_1_1_PARALLEL_CONTEXT_LOADING.md`
- **Phase 1.2 Docs:** `docs/PHASE_1_2_PARALLEL_ENTITY_KG.md`
- **Deploy Status:** `DEPLOY_PHASE_1_1_COMPLETE.md`
- **Phase 1.2 Status:** `PHASE_1_2_READY.md`
