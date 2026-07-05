# Qdrant estate reconciliation — defined vs live (TAC-2 A6)

date: 2026-07-05 · source of truth: live probe `GET /health/collections` on
`nuzantara-rag.fly.dev` at 2026-07-05T09:4x UTC (14 collections · 113,818 documents)
crossed with `collection_definitions` in
`apps/backend-rag/backend/services/ingestion/collection_manager.py:48` (20 entries).

TAC-1 (2026-07-02) reported "20 defined vs 12 live, 8 to reconcile". The live probe shows
the divergence is structurally worse: **only 6 of 20 definitions match a live collection**;
14 definitions point at nothing; 8 live collections (including the two biggest) have no
definition at all. The manager describes the pre-hybrid-migration generation of the estate.

## Defined ∧ Live (6)

| Collection | defined doc_count | live points | note |
|---|---|---|---|
| bali_zero_pricing_hybrid | 29 | 70 | annotation stale |
| balizero_news | — | 3,513 | |
| immigration_circulars | — | 1,979 | |
| tax_genius_hybrid | — | 340 | |
| training_conversations_hybrid | — | 3,638 | |
| visa_oracle | 1,612 | **90** | 94% shrink vs annotation — worth its own look |

## Defined, NOT live (14) — the dead definitions

`collective_memories`¹ · `bali_zero_team` · `kbli_2025_final`² · `tax_genius`² ·
`legal_architect` · `legal_unified`² · `legal_unified_hybrid`² · `zantara_books` ·
`cultural_insights` · `tax_updates` · `tax_knowledge` · `property_listings` ·
`property_knowledge` · `legal_updates`

¹ Collective memories live in the **Postgres table** `collective_memories` today
(`services/memory/collective_memory_service.py` — pure SQL). The Qdrant definition is
pre-migration archaeology.
² Superseded by a live successor generation: `kbli_2025_final` → `kbli_2025_final_hybrid`
+ `kbli_2025_final_oss`; `tax_genius` → `tax_genius_hybrid`; `legal_unified` →
`legal_unified_2026`; `legal_unified_hybrid` → `legal_unified_hybrid_hybrid`.

## Live, NOT defined (8) — the undocumented estate

| Collection | live points | note |
|---|---|---|
| legal_unified_hybrid_hybrid | 81,411 | the BIGGEST collection — zero definition |
| legal_unified_2026 | 15,410 | second biggest — zero definition |
| kbli_2025_final_oss | 4,424 | |
| kbli_2025_final_hybrid | 1,559 | |
| bali_zero_skills_hybrid | 613 | |
| intel_authoritative_sources | 525 | |
| kbli_tka_hybrid | 246 | |
| garuda_assets | **0** | live but empty — create-and-abandon? |

## The second registry (why "20 defined" meant two different things)

There are **two parallel, never-reconciled registries** — this duplication, not the raw
20-vs-live gap, is the structural disease:

1. `backend/core/collection_registry.py` — `CANONICAL_COLLECTION_ALIASES` has ~20 keys
   (the most plausible source of TAC-1's "20"), but they are **aliases** folding onto ~10
   canonical logical/physical names (`CANONICAL_LOGICAL_COLLECTIONS` +
   `LOGICAL_TO_PHYSICAL_COLLECTIONS`; two entries are constant-named, so naive string-key
   counts under-count). Two aliases are dead code — `legal_intelligence` and
   `intel_authoritative_sources` have zero references outside their own definition
   (note: an `intel_authoritative_sources` COLLECTION nonetheless exists live with 525
   points — fed by a producer that bypasses this registry).
2. `services/ingestion/collection_manager.py` — `collection_definitions` (20 entries,
   §above) with **6 names the registry has never seen**: `collective_memories`,
   `bali_zero_team`, `zantara_books`, `cultural_insights`, `property_listings`,
   `property_knowledge`. Of these, `property_listings`/`property_knowledge` carry an
   identical copy-paste-looking `doc_count: 29` and no SurfaceRouter wiring, and
   `cultural_insights` declares `doc_count: 0` in its own definition.

Orphan tooling on top: `kb_politics_hier_v1` (one-off ingest script), `kbli_tka`
generation/verify scripts (while the LIVE collection is named `kbli_tka_hybrid`, 246
points), `bali_zero_skills_local` (explicitly superseded per registry comment).

The regeneration PR (§Decision proposal) should therefore also PICK ONE canonical source
(registry.py is the better skeleton) and fold or retire the manager's 6 orphans — not
just sync counts.

## Collateral findings

- **DOCSYNC Qdrant numbers are a frozen cache.** The green block says "12 collections ·
  104,154 vectors"; live is 14 · 113,818. `scripts/docs_sync.py::get_qdrant_stats` refreshes
  only when `QDRANT_URL`+`QDRANT_API_KEY` are exported — probed 2026-07-05: **unset on Mini
  AND Pro** (`~/.nuzantara-secrets.env`), so the cache can never refresh on either machine.
  The "machine-verified" label on these two numbers is Esiste≠Armato.
- `CollectionManager` feeds `search_service`, `hybrid_search`, `query_router_integration`
  and `collection_warmup_service` — a warmup/routing pass over the 14 dead names is wasted
  work at best, silent empty-result routing at worst. Not traced end-to-end in this pass.

## Decision proposal (operator)

1. **Document-as-intentional now** (this PR): dated note in `collection_manager.py`
   pointing here — done, zero runtime risk.
2. **Next PR (needs a maintainer run with Qdrant env):** regenerate `collection_definitions`
   from the live estate (14 entries), delete the 14 dead ones, and mark
   `garuda_assets` (0 points) + `visa_oracle` (90 vs 1,612) for content review.
3. Export `QDRANT_URL`/`QDRANT_API_KEY` (0600 secrets file) on ONE canonical machine so the
   DOCSYNC Qdrant cache can actually refresh, or drop those two numbers from the green block.
