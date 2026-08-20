---
date: 2026-08-21
domain: compliance
client_case: null
sources:
  - "live read-only SQL run against prod Postgres (nuzantara-postgres) via scripts/pg.sh, synthetic VALUES/generate_series data only — no real clients/team_members rows touched"
---

# Water-filling SQL robustness test (requested by team-lead, PR #4468 review)

Companion to `2026-08-21-orphan-client-reassignment-plan.md` and the staged draft migration
`2026-08-21-migration-276-DRAFT-pending-guardrails-bypass.sql.txt`. Team-lead asked, before
promoting the draft: does the dynamic (run-time-computed) water-filling logic hold if the
orphan pool **grows** past 324 before the migration executes, and does the **zero-orphan**
case degrade cleanly (no-op, not a division-by-zero)? Answered empirically, not by
reasoning about the SQL — same CTE chain as the draft migration, with `current_loads` and
the orphan pool swapped for synthetic literals (`VALUES` + `generate_series`), run
read-only against prod via `nuzantara_readonly` (zero write risk, no real table read
either — the query never joins `clients`/`team_members` in this test).

## Test 1 — pool grows to N=400 (was 324 at measurement time)

Current loads held fixed at the real snapshot (Damar 78, Surya 200, Vino 250, Adit 258,
Ari 316, Krisna 352). Result:

| Person | Current | +New | Final |
|---|---:|---:|---:|
| Damar | 78 | +219 | 297 |
| Surya | 200 | +97 | 297 |
| Vino | 250 | +46 | 296 |
| Adit | 258 | +38 | 296 |
| Ari | 316 | +0 | 316 |
| Krisna | 352 | +0 | 352 |

`SUM(final_alloc) = 400` exactly, `MIN(final_alloc) = 0` (no negative allocations). Ari and
Krisna still receive zero — the level only reaches 296.5, still below their 316/352. (For
the record: the level would need to clear 316 for Ari to join the pool, which needs
`N > 4×316 − 786 = 478` orphans — well past any plausible drift in the hours between this
plan and its execution.)

Ran the **full chain** including the id-bucketing (`orphans_ranked` + `allocation_buckets`
+ `assignment`, with `synthetic_orphans` = `generate_series(1,400)` standing in for real
orphan client ids): 400 assignment rows, contiguous non-overlapping id ranges matching the
counts above exactly (Damar 1–219, Surya 220–316, Vino 317–362, Adit 363–400) — no gaps, no
overlaps, no double-assignment.

## Test 2 — pool empties to N=0

Same current loads, `orphan_count.n = 0`. Result: every `final_alloc = 0`,
`SUM(final_alloc) = 0`, `MAX(final_alloc) = 0`. Full chain (bucketing +
`generate_series(1,0)`, which Postgres correctly returns as an empty set): `assignment_rows
= 0`. Clean no-op — no error, no division-by-zero. (Structurally this was never at risk:
every division in the algorithm is `.../k` where `k` ranges 1–6, never `.../n`; the orphan
count only ever appears in a numerator. Verified empirically anyway per the anti-hallucination
discipline — reasoning about a query is not the same as running it.)

## Conclusion

The dynamic water-filling clause in the draft migration is robust to both directions of
drift (pool grows, pool empties) without any code change. This does not change the FASE 2
plan or the CSV mapping (both computed at N=324, the measured value at plan time) — it
confirms that if the *migration* itself is delayed and the real orphan count has moved by
the time it runs, its own live recomputation will produce a correct new split rather than
silently reusing the stale 324-based numbers or erroring out.

## Post-execution proof (for whoever runs the migration once the guardrails bypass is granted)

**1. Zero-orphans check** — must return `0` after the migration commits:

```sql
SELECT COUNT(*) FROM clients c
WHERE c.deleted_at IS NULL
  AND NOT EXISTS (
    SELECT 1 FROM team_members tm
    WHERE lower(tm.email) = lower(BTRIM(c.assigned_to)) AND tm.active = true
  );
-- expected: 0
```

**2. Per-person final load** — sanity check against the FASE 2 table (numbers there were
computed at N=324; if the real orphan count drifted, expect the migration's own live
recomputation to have produced different final totals — that is correct, not a bug; only
re-derive by hand if this looks obviously wrong, e.g. someone getting negative growth):

```sql
SELECT assigned_to, COUNT(*) FROM clients
WHERE deleted_at IS NULL
  AND assigned_to IN (
    'damar@balizero.com','surya@balizero.com','vino@balizero.com',
    'adit@balizero.com','ari.firda@balizero.com','krisna@balizero.com'
  )
GROUP BY assigned_to ORDER BY 2 DESC;
```

**3. Cache invalidation — do NOT skip, and do NOT run it from a bare local/ssh script.**
`backend.core.cache.invalidate_cache` is importable from any standalone Python process, but
`CacheService._try_connect_redis()` reaches Redis via `RedisManager.get_instance()` **without**
ever calling `RedisManager.initialize()` — that call only happens inside the FastAPI app's
own `lifespan`. A bare script (local, or `ssh pro`/`ssh mini` + a one-off `python -c`) that
never calls `.initialize()` gets a `None` async client and silently falls back to an
in-memory cache local to that one throwaway process — the invalidation call returns
cleanly and invalidates **nothing** the live API actually reads (an "Esiste ≠ Armato" trap,
documented independently in `scripts/intake_identity_backfill.py`'s own
`_invalidate_identity_backfill_cache()` — same finding, different mutation). Concretely:

```bash
fly ssh console -a nuzantara-rag -C "python3 -c '
import asyncio
from backend.core.redis_manager import RedisManager
from backend.core.cache import invalidate_cache, get_cache_service

async def main():
    RedisManager.get_instance().initialize()
    await invalidate_cache(\"zantara:crm_clients_stats:*\")
    await invalidate_cache(\"zantara:crm_practices:*\")
    print(\"backend:\", get_cache_service().get_stats().get(\"backend\"))

asyncio.run(main())
'"
```

Check the printed `backend:` value is `redis`, not the in-memory fallback name — that is
the actual proof the invalidation reached the live cache, not just that the call returned
without error. `CACHE_TTL_STATS_SECONDS = 300` (5 min) means a skipped invalidation
self-heals within 5 minutes regardless, but CLAUDE.md §9's cache-invalidation rule is
unconditional ("after EVERY mutation") — don't rely on the TTL as a substitute.

Related: `2026-08-21-orphan-client-reassignment-plan.md` (FASE 1/2 + criterion),
`2026-08-21-migration-276-DRAFT-pending-guardrails-bypass.sql.txt` (the migration itself,
staged pending the operator's guardrails bypass — PR #4468).
