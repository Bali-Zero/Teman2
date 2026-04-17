# GraphRAG 2.0 — Completion of residual gaps (2026-04-17)

> Session: Air-3 (strategic-8) · Branch: `graphrag/completion-gaps`
> Worktree: `.worktrees/graphrag-completion`
> Machine: Air (`antonellosiano@Nuzantara-9.local`)

## Context

GraphRAG 2.0 was deployed on 2026-04-07 in 5 phases: grading framework,
Louvain community detection (6,310 clusters), multi-hop, entity resolution,
trimodal RRF. Three residual gaps were open according to memory:
`graphrag-v2-deployed`:

1. populate entity linker full
2. activate trimodal RRF weight > 0
3. generate community summaries

## Subtask 1 — Entity linker full populate ✅

**Deliverable:** script `apps/backend-rag/scripts/run_entity_linker_full.py`
and populated `kg_entity_mentions` table.

**State before:**

| table | rows |
|---|---|
| `kg_nodes` | 113,854 |
| `kg_edges` | 251,522 |
| `kg_entity_mentions` | 58 |

**Run:**

- Collection: `legal_unified_hybrid_hybrid` (81,251 points in Qdrant Cloud)
- Batch: 256 points/scroll, fuzzy disabled (exact match only)
- Points processed: **80,979** (272 skipped: no `text` payload)
- Elapsed: **238.4s** (~340 points/s)
- Throughput: driven by in-memory `LOWER(kg_nodes.name) -> entity_id` index
  (85,175 unique-lowered keys) + `asyncpg.executemany` per batch.

**Resulting state:**

| metric | after |
|---|---|
| `kg_entity_mentions` total | **33,562** (+33,504) |
| distinct entities linked | 176 |
| points covered (with ≥1 mention) | 32,303 / 81,251 (39.8%) |
| match_type | 100% `exact` (fuzzy disabled for this run) |

**Design decisions:**

- **In-memory matcher**: `EntityLinker.link_text` originally called
  `self._pool.acquire()` once per mention per point (O(N·M) connections).
  The runner pre-loads all `kg_nodes.name` into a dict and matches in
  process, then flushes per-batch via `executemany`. This is the single
  biggest win (~100× speedup).
- **Variant expansion**: stored entity names use multiple forms
  (`UU 13/2003`, `UU NO. 11 TAHUN 2020`, `UU No 11 Tahun 2020`). The
  runner expands each detected mention into all known variants before
  index lookup.
- **CONTEXT prefix regex**: `legal_unified` payloads start with
  `[CONTEXT: PP - NO 6624 - TAHUN 2021 - TENTANG ...]`. The hyphen
  disrupts the default `PP\s*(?:No\.?\s*)?(\d+)\s*(?:Tahun\s*)?(\d{4})`
  pattern; an explicit CONTEXT pattern was added.
- **Resume-safe**: the `UNIQUE(entity_id, collection_name, point_id)`
  index on `kg_entity_mentions` makes inserts idempotent; the runner
  also pre-loads seen `point_id` set so it skips entire points on
  restart.
- **Fuzzy left off**: fuzzy trigram match would add ~50× overhead per
  miss. The 39.8% coverage from exact-match-only is already a >570×
  improvement vs baseline (58 mentions → 33,562). A follow-up fuzzy
  pass over the uncovered 48K points is a safe next step.

**Log:** `docs/superpowers/sessions/2026-04-17-strategic-8/logs/air-3-entity-linker.log`

## Subtask 2 — Trimodal RRF weight activation ✅ (decision made, no code change)

**Deliverable:** `docs/graphrag-rrf-weight-decision.md` + benchmark script
`scripts/benchmark_trimodal_rrf.py`.

**Finding:** `HybridSearchService.reciprocal_rank_fusion_trimodal` is
implemented with tests but **never called in production**. The only
production path is bimodal RRF via `search_hybrid`. Activating the
graph branch therefore requires (a) a call site and (b) a weight
choice. This task addresses (b) first; (a) is left to a follow-up PR.

**Benchmark (no gold labels):**

Three weight configs tested over 12 Indonesian/legal queries:

| config | coverage@10 | mentions/result | jaccard vs baseline |
|---|---|---|---|
| `(0.5, 0.5, 0.0)` baseline | 0.633 | 0.65 | 1.0 |
| `(0.4, 0.3, 0.3)` balanced | 0.617 | 0.68 | 0.431 |
| `(0.35, 0.15, 0.5)` graph-heavy | 0.65 | 0.73 | 0.335 |

**Decision:** keep `(0.5, 0.5, 0.0)` (do **not** activate graph weight
yet). The graph-heavy config gives +0.017 coverage (marginal) while the
Jaccard overlap vs baseline drops to 0.335 — the top-10 set changes
dramatically, which on a proxy metric is not justified. A gold-standard
relevance dataset (MRR/NDCG/Recall) is required before activation.

## Subtask 3 — Community summaries generation 🟡 (in progress)

**Deliverable:** script `scripts/generate_community_summaries.py` +
`scripts/fill_small_community_fallbacks.py` + populated
`kg_communities.summary` column.

**State before:** 6,310 Louvain communities, 0 with `summary`.

**Constraints:**

- Only `qwen3:4b` and `deepseek-r1:1.5b` installed on Air (memory
  referenced `qwen3.5:9b` which is not present). qwen3:4b ignores
  `think: false` and emits English reasoning preambles even when asked
  for Italian — output requires post-processing.
- Measured throughput: ~12s/call → 6310 × 12s / 2 concurrency ≈ 11 h
  (out of budget for this session). macOS system proxy on 127.0.0.1:8888
  intercepted localhost:11434 traffic until we passed `trust_env=False`.

**Strategy chosen:**

- **LLM path (qwen3:4b) for 898 communities with `member_count ≥ 10`**
  — the ones most likely to be retrieved. This takes ~3-4 hours at
  concurrency=2.
- **Deterministic fallback** for the 5,412 small communities
  (`member_count < 10`). They still get a non-NULL `summary` populated
  with "Cluster KG Louvain <id> (N membri) centrato su: <top_entities>.
  Raggruppamento automatico, riepilogo semantico non disponibile."
- Preamble stripping in `_strip_preamble`: drops `<think>...</think>`
  tags + paragraphs beginning with `Okay,` / `Let's tackle` / `First, I`.
  If nothing usable remains (<40 chars), we use the deterministic
  fallback for that community too.

**Current state:** see `logs/air-3-community-summaries.log` for live
counts. Sample output and final statistics appended at session end.

**Log:** `docs/superpowers/sessions/2026-04-17-strategic-8/logs/air-3-community-summaries.log`

## Files

| File | Purpose |
|---|---|
| `apps/backend-rag/scripts/run_entity_linker_full.py` | Subtask 1 runner |
| `apps/backend-rag/scripts/benchmark_trimodal_rrf.py` | Subtask 2 proxy benchmark |
| `docs/graphrag-rrf-weight-decision.md` | Subtask 2 decision report |
| `apps/backend-rag/scripts/generate_community_summaries.py` | Subtask 3 LLM runner |
| `apps/backend-rag/scripts/fill_small_community_fallbacks.py` | Subtask 3 deterministic filler |
| `docs/superpowers/sessions/2026-04-17-strategic-8/logs/air-3-entity-linker.log` | Subtask 1 run log |
| `docs/superpowers/sessions/2026-04-17-strategic-8/logs/air-3-community-summaries.log` | Subtask 3 run log |
| `docs/superpowers/sessions/2026-04-17-strategic-8/logs/air-3.log` | Unified session transcript |

## Next steps (for a future session)

1. **Entity linker fuzzy pass** on the 48,948 uncovered `legal_unified`
   points. Cost: ~50× exact-match time but recovers
   entities missed by exact.
2. **Trimodal RRF call site**: wire `reciprocal_rank_fusion_trimodal`
   into `search_hybrid` behind a setting
   (`settings.graphrag_trimodal_weights` default `(0.5, 0.5, 0.0)`),
   and ship a gold-standard query set (50-100 prod queries with
   user-clicked citations) to rerun the benchmark with real MRR/NDCG.
3. **Community summaries quality**: install `qwen3.5:9b` or
   `llama3.1:8b-instruct` and rerun the LLM path for communities 10+
   to replace the qwen3:4b/fallback mix.
4. **Extend linker to other collections**: tax_genius_hybrid,
   kbli_2025_final_hybrid, visa_oracle (same runner, different
   `--collection`).
