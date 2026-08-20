---
date: 2026-08-21
domain: compliance
client_case: null
sources:
  - "live read-only SQL run against prod Postgres (nuzantara-postgres) via scripts/pg.sh, synthetic VALUES/generate_series data only — no real clients/team_members rows touched"
adversarial_review: kimi-k3
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

**Caveat on this pair of tests** (raised in adversarial review, see section below): both N=400
and N=0 stay on the *same* branch of the k-selection loop as the real N=324 case (k=4, or the
k=1 degenerate case for N=0) — neither exercises the one piece of logic that can actually
produce a wrong allocation, the point where the smallest-valid-k search moves from one k to
the next. "Robust to drift" was true only for drift that doesn't cross that boundary. Closed
by the six tests below.

## Test 3 — the k-transition boundary (N=478 vs N=479)

At k=4, the level `L` reaches Ari's load (316) exactly at `N = 4×316 − 786 = 478`. Below that,
k=4 stays valid; at N=479, k=4 would push Ari's allocation negative and the smallest-valid-k
search must move to k=5. Ran both:

- **N=478**: k=4, L=316.0, Ari allocation exactly 0 (boundary, not negative) — k=4 still valid.
- **N=479**: k=5, L=316.2 — Ari now receives **+0.2 → rounds to a real client**, alongside
  Damar/Surya/Vino/Adit; Krisna (352) still excluded. `SUM(final_alloc) = 479` exactly.

This is the first test in either document that actually forces the k-selection loop to pick a
different k than the real run did — the boundary the original two tests never touched.

## Test 4 — N=500 (past the transition, confirms k=5 stays valid and stable)

k=5, L=317.2, allocations sum to 500 exactly, Krisna still the sole exclusion, no negative
allocations. Confirms the transition isn't a one-off fluke at the exact boundary.

## Test 5 — duplicate row in the `team` CTE (confirmed real defect mode)

Simulated the six-person `team` CTE with `damar@balizero.com` appearing **twice** (the kind of
duplication a join-fan-out or a copy-paste in the CTE's `VALUES` list could produce). Result:
`SUM(current_loads)` double-counts Damar's 78, and the per-person `k` in the level equation no
longer matches the number of distinct people — the computed `L` and every allocation downstream
is wrong, silently (no error, no constraint violated, just a wrong number). **Confirmed as a
real, un-defended-against corruption mode**, not a hypothetical. Addressed in the migration
draft: the `team` CTE now uses `SELECT DISTINCT` on the email, so a duplicate literal row can no
longer double-count (see `2026-08-21-migration-276-DRAFT-pending-guardrails-bypass.sql.txt`).

## Test 6 — empty team (k=0)

Simulated a `team` CTE with zero rows (e.g. all six flagged `active=false` simultaneously, or a
join that returns nothing). The level-search loop never finds a valid k (there's nothing to
search over) and the query returns zero assignment rows rather than dividing by zero — no
`division by zero` error, no crash, no bogus allocation. Confirmed safe. This is the dual case
to N=0 (division by n never at risk vs. division by k when k=0) and neither the original
document nor this one had pinned it until now.

## Test 7 — all six tied at the same current load

All six set to 254 (an arbitrary tie value), N=324. Result: k=6 (everyone is in the smallest
valid prefix — no one is excluded), L = 254 + 324/6 = 308, every person +54, sum=324 exactly.
Matches hand arithmetic (a tie forces the flat-split case, which is what "divide by 6" would
have given anyway — correctly so, since with no spread to level, max-min fairness degenerates
to an even split).

## Test 8 — N=1 (smallest nonzero pool)

k=1 (only the lowest-loaded person, Damar), L = 78+1 = 79, Damar +1, everyone else +0, sum=1.
Confirmed correct — the single client goes to whoever has the least, which is the intended
behavior of leveling from the bottom up.

## Conclusion

The dynamic water-filling clause in the draft migration is robust to both directions of pool
drift (grows, empties) **and** to the boundary that actually matters — the k-transition — which
the original two tests (N=400, N=0) did not exercise; that gap is closed by Tests 3-8 above.
One real defect mode was found and fixed in the process: a duplicate row in the `team` CTE
silently corrupts the allocation (Test 5) — hardened against with `SELECT DISTINCT`. This does
not change the FASE 2 plan or the CSV mapping (both computed at N=324, the measured value at
plan time) — it confirms that if the *migration* itself is delayed and the real orphan count has
moved by the time it runs, its own live recomputation will produce a correct new split across
the boundary conditions actually tested, rather than silently reusing the stale 324-based
numbers, erroring out, or (per Test 5) silently double-counting a duplicated team-member row.

## Adversarial review

Reviewed by Kimi K3 (`kimi-code/k3`, cross-family, non-PII input). Full review covered six
claims across both this document and the sibling plan document; this section covers the finding
specific to this file (see `2026-08-21-orphan-client-reassignment-plan.md`'s own Adversarial
review section for the rest).

**ISSUE FOUND, closed above**: both original tests (N=400, N=0) stayed on the same branch of
the k-selection loop as the real N=324 run and never exercised the k-transition boundary
(k=4→k=5 at N≈478/479) — the one piece of logic that can actually produce a wrong allocation.
Also untested: duplicate emails in the team CTE (a realistic corruption mode for anything built
from a join), an empty team (the k=0 dual of the N=0 test), all-six-tied, and N=1. Kimi's exact
words: *"the claimed 'structurally safe, verified empirically as an invariant-pin for future
rewrites' overclaims — two boundary tests on one branch do not pin the invariant."* That
critique is accepted at face value — the original framing was too strong for what had actually
been tested. Tests 3-8 above close every one of the five gaps named; Test 5 (duplicate row)
turned up a real, previously-undefended corruption mode and the migration draft was hardened
for it (`SELECT DISTINCT` on the team CTE). With that coverage in place, "invariant-pin for
future rewrites" is now a claim this document has actually earned, not one it merely asserted.

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
