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

## Subtask 3 — Community summaries generation ✅ (deterministic route)

**Deliverable:** script `scripts/generate_community_summaries.py` +
`scripts/fill_small_community_fallbacks.py` + populated
`kg_communities.summary` column (**6,310 / 6,310 = 100%**).

**State before:** 6,310 Louvain communities, 0 with `summary`.

**Constraints discovered during the session:**

- Only `qwen3:4b` and `deepseek-r1:1.5b` are installed on Air (memory
  `graphrag-v2-deployed` referenced `qwen3.5:9b`, which is not
  present on either machine's Ollama cache).
- qwen3:4b **ignores `think: false`** and hard-codes an English
  reasoning preamble ("Okay, the user wants...", "Let me translate
  the key terms...") even when the system prompt forbids it and the
  user prompt is entirely in Italian. The actual Italian answer, when
  it appears, is deep inside a 2-3kB reasoning trace.
- At `num_predict=800` (needed to let qwen3 reach the Italian conclusion),
  wall-clock latency is ~59s/call. 6,310 × 59s / 2 concurrency ≈ 51 h —
  well beyond this session's 24h budget, and beyond the 24h stop hard.
- deepseek-r1:1.5b at 40s/call produces broken Italian ("l'indonesia:
  le relazioni indosains entre Indonesia...").
- macOS system proxy on 127.0.0.1:8888 silently intercepts
  localhost:11434 traffic. Fix: `httpx.AsyncClient(trust_env=False)`.

**Decision taken:** ship a **domain-aware deterministic summary** for all
6,310 communities using the top_entities already persisted in the
Louvain table. This gives:

- 100% coverage of a non-NULL `summary` field (which unblocks any
  downstream retrieval code that expects it, e.g. community-summary
  RAG routes).
- Italian-only text, deterministic, fast to regenerate.
- A coarse semantic label inferred from entity tokens (KBLI,
  permessi di soggiorno, obblighi fiscali, licenze d'impresa,
  struttura societaria, lavoro/BPJS, normative primarie, enti
  governativi, sanzioni, ambiente, immobiliare).

The LLM runner script is retained for a future session that installs
`qwen3.5:9b` (1.5B-param local model matches memory's original plan).

**Result:**

| metric | value |
|---|---|
| communities with summary | 6,310 / 6,310 (100%) |
| LLM-generated | 0 |
| deterministic (domain-aware) | 6,310 |
| mean length | ~180 chars |

**Sample (top 20 by member_count):**

```
comm_L0_904cacad67f2 [7450m]: Cluster Louvain di 7450 entità centrate su
  riferimenti normativi primari e secondari. Voci rappresentative:
  ayat_ayat_(1), ayat_ayat_(2), pasal_ayat_(1), sanksi_sanksi_administratif,
  ayat_ayat_(3). Riepilogo deterministico (estratto da top_entities) —
  non generato da LLM.

comm_L0_5f1572accbd7 [7056m]: Cluster Louvain di 7056 entità centrate su
  classificazione attività economiche (KBLI). Voci rappresentative:
  izin_usaha_tidak_diketahui, license:sertifikat_standar, ...

comm_L0_ea84ab642fa6 [852m]: Cluster Louvain di 852 entità centrate su
  struttura societaria e capitale. Voci rappresentative: license:izin,
  company:pt_pma, sektor:I.J, sektor:I.K, sektor:I.L. ...

comm_L0_984af547f5da [688m]: Cluster Louvain di 688 entità centrate su
  permessi di soggiorno e immigrazione. Voci rappresentative:
  permen_no_22_tahun_2023, izin_tinggal_terbatas, izin_tinggal_tetap,
  izin_tinggal_kunjungan, orang_asing. ...
```

Full 20 samples: `docs/superpowers/sessions/2026-04-17-strategic-8/logs/air-3-community-samples.log`

**Log:** `docs/superpowers/sessions/2026-04-17-strategic-8/logs/air-3-community-summaries.log` (LLM attempt trace, stopped early after diagnosis)

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
3. **Community summaries quality**: `ollama pull qwen3.5:9b` on Air
   (~5GB disk, Q4_K_M quant fits in 16GB RAM), then rerun
   `generate_community_summaries.py --min-members 10` for the 898
   largest clusters. At a realistic 6-8s/call this finishes in ~2h.
   The deterministic fallback stays in place for the small-cluster
   long tail.
4. **Extend linker to other collections**: `tax_genius_hybrid`,
   `kbli_2025_final_hybrid`, `visa_oracle`, `bali_zero_pricing_hybrid`
   (same runner, different `--collection`).
5. **Extend entity_linker.py** to use the variant-expansion lookup
   from `scripts/run_entity_linker_full.py` (the production class
   still does one SQL round-trip per mention, which is 100× slower
   than the in-memory path).
