# Deep Research: Performance & Scaling — FastAPI on 2GB Fly.io

You are researching for Nuzantara/Bali Zero — a FastAPI backend running on Fly.io with severe resource constraints.

## Current Constraints

- Fly.io: shared-cpu-2x, 2GB RAM, 1 worker (OOM with 2), auto_stop=true, min=0
- Cold start: ~35s (lazy loading + background init)
- PostgreSQL: 2GB RAM (Fly.io managed)
- Qdrant: 2GB RAM (Fly.io)
- Redis: Upstash (serverless)
- ~500 requests/day, bursty (most during WITA business hours)

## Research Questions

1. **Cold start elimination**: Strategies to reduce 35s cold start on auto_stop Fly.io machines. Keep-alive pings, pre-warming, lazy loading optimization, import profiling. What do production FastAPI apps on Fly.io do?

2. **Memory optimization for Python ML apps**: We load sentence-transformers, LangGraph, 70+ routers. How to reduce resident memory? `gc.collect()` strategies, import deferral, model quantization, shared memory.

3. **Connection pooling**: asyncpg pool sizing for 2GB PostgreSQL with bursty traffic. Best practices for pool_size, max_overflow, connection recycling on constrained VMs.

4. **Qdrant optimization on 2GB**: Our 9 collections use 66K vectors at 1536 dims. Quantization (scalar, product, binary), HNSW tuning (m, ef_construct), memory-mapped storage. What fits in 2GB?

5. **Edge computing opportunity**: Should we move any workloads to Cloudflare Workers, Vercel Edge Functions, or Fly.io Machines GPU? Specifically: embedding generation, intent classification, response caching.

6. **Cost optimization**: We spend ~$40/mo on Fly.io. Is there a cheaper alternative at equivalent performance? Railway, Render, Koyeb, self-hosted on Hetzner ARM?

## Output Format

Concrete benchmarks and configurations, not theory. Include actual Fly.io fly.toml settings, Python code snippets, and Qdrant config where applicable.

Save your research to `docs/research/2026-03-15-performance-scaling.md`
