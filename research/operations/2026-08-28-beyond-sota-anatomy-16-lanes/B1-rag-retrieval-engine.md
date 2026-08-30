---
date: 2026-08-28
domain: operations
part: B1 rag-retrieval-engine
scope: "RAG retrieval / knowledge engine (services rag, search, knowledge_graph, kg_monitoring, memory, caching, oracle, ingestion; backend/kb; Qdrant collections; frozen embedding; abstain policy; retrieval routers) benchmarked against enterprise RAG SOTA"
sources:
  - https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/
  - https://www.anthropic.com/engineering/contextual-retrieval
  - https://qdrant.tech/articles/hybrid-search/
  - https://qdrant.tech/documentation/tutorials-search-engineering/reranking-hybrid-search/
  - https://www.zenml.io/llmops-database/building-robust-enterprise-search-with-llms-and-traditional-ir
  - https://research.perplexity.ai/articles/rethinking-search-as-code-generation
  - https://huggingface.co/vectara/hallucination_evaluation_model
  - https://arxiv.org/abs/2311.09476
  - https://arxiv.org/html/2402.03216v3
  - https://arxiv.org/pdf/2408.16672
  - https://cohere.com/blog/rerank-3pt5
  - https://redis.io/blog/what-is-semantic-caching/
  - https://arxiv.org/abs/2501.13956
  - https://www.researchgate.net/publication/386472016_Legal_Chunking_Evaluating_Methods_for_Effective_Legal_Text_Retrieval
status: DONE 2026-08-29
---

> ## ⚠️ Read this before acting on anything below
>
> **These findings are pinned to `11a3c89a2e` (2026-08-28). `origin/main` was 123 commits ahead
> when this file was published on 2026-08-30.** A verdict in here is a **LEAD, not a fact**: it
> was true of a tree that no longer exists. Re-measure before you build on it.
>
> **Defects presented below as current that were already CURED before publication** — each fix
> verified as a descendant of the pin with `git merge-base --is-ancestor 11a3c89a2e <sha>`:
>
> | Presented as a live defect | Actually cured by | Verified |
> |---|---|---|
> | R9 harness time-bomb dated 2026-09-02 (X1) | #5190 | ancestor check |
> | Phantom DeepSeek voter (B8) | #5211 / #5207 (`cc82ed62e4`, `0cccbbc925`) | ancestor check |
> | Auth split-brain across the portals (F3, F4) | #5181 (`d6556a75bf`) | ancestor check |
> | Magic-link `result_id` ownership — which F2 calls "replay-safe" (F2) | #5298 (`3861567e52`) | ancestor check |
> | Meta webhook signature unenforced in prod (B3) | fail-closed by default since 2026-08-26; `WHATSAPP_APP_SECRET` deployed | live probe: unsigned `POST /webhook/whatsapp` → **401 `Invalid signature`** (2026-08-30) |
>
> **Counts that were re-measured and found WRONG** (they were not corrected in the text, so that
> the reports stay the artefact the panel actually produced rather than a quietly-improved one):
> `X3:31` reads 10 directories + 6 symlinks, measured 11 + 5. `X3:45` reads 162 `@mcp.tool`,
> measured 153. Other counts flagged by the review but NOT settled either way are listed in this
> PR's evidence pack under `dissent`, marked PLAUSIBLE — treat every number in these files as
> unverified unless you have just re-run it.
>
> **Known internal contradiction, left standing:** `B4` states that OCR of identity documents
> never leaves the machine, and then, two paragraphs later, that OCR'd passport/NPWP/akta text is
> shipped to Gemini by CRM-Guardian. The second statement is the accurate one. It is ledgered.
>
> **Two things were withheld from this publication rather than edited quietly:** the panel's own
> mandate file (self-labelled `IN-PROGRESS` / `internal`), and the location of a live DNS-write
> credential named in `B5`. Both omissions are declared here because a silently-sanitised audit is
> worth less than an audit that says what it removed.
>
> The reports' own thesis is that a written artefact gets presumed to be in force. This header
> exists because that thesis applies, first, to the reports themselves.


# B1 — RAG Retrieval Engine: Beyond-SOTA Deep Research

## Anatomy (as measured)

**Scale.** The retrieval engine spans **168 Python files, ~70,600 LOC** across nine scoped directories (measured with `find -name '*.py' | xargs cat | wc -l` on the pinned worktree): `services/rag` 87 files / 41,250 LOC (of which the `agentic/` orchestrator package is 43 files), `services/search` 7 / 2,866, `services/knowledge_graph` 17 / 6,162, `services/kg_monitoring` 7 / 2,800, `services/memory` 10 / 4,544, `services/caching` 3 / 886, `services/oracle` 18 / 4,587, `services/ingestion` 12 / 5,841, `backend/kb` 7 / 1,636 (plus curated legal PDFs/MD under `kb/legal/`).

**Collections and embedding invariant.** `core/collection_registry.py` (102 lines) is the canonical logical→physical map: 11 logical collections — `bali_zero_pricing_hybrid`, `visa_oracle`, `kbli_2025_final`, `tax_genius`, `legal_unified`, `training_conversations_hybrid`, `immigration_circulars`, `balizero_news`, `nlm_shadow_hybrid`, `curated_qa`, plus the skills mirror `bali_zero_skills_hybrid` (`collection_registry.py:7-31`). Alias chains are real and scar-bearing: `legal_architect` → physical `legal_unified_hybrid_hybrid` (`collection_registry.py:40` — a double-`_hybrid` suffix fossilized into the physical name). The embedding model is frozen at `text-embedding-3-small`, 1536 dims: `core/embeddings.py:256` hardcodes `self.dimensions = 1536`, `core/qdrant_db.py:74` sets `DEFAULT_OPENAI_DIMENSIONS = 1536`, and `fly.toml:37` pins `EMBEDDING_PROVIDER = 'openai'`. The "93K+ vectors" figure in `apps/backend-rag/CLAUDE.md` is (unverified) — live Qdrant counts are not inspectable from disk.

**The live query path** (`services/rag/agentic/orchestrator_core.py`, 2,330 LOC) is a staged pipeline: FAQ cache check (`:319`) → semantic cache check (`:465`) → curated-QA grounding injection (`:544`) → parallel entity extraction + KG context + LangGraph workflow fetch (`:741-792`) → KG fast path attempt (`:1028`) → ReAct loop (`:1106`, implemented in `agentic/reasoning.py`, 1,732 LOC) → grading gates (`:1897`) → finalization with an E33-claim guard (`:116`). Retrieval inside the loop goes through `VectorSearchTool` (`agentic/tools.py:78`), which routes across collections by LLM tool-argument choice (prompted collection descriptions at `tools.py:108-114`).

**Hybrid search and reranking exist but are dark in prod.** `services/rag/hybrid_search.py` (810 LOC) implements BM25 sparse vectors + dense + RRF (k=60, `hybrid_search.py:32`) over Qdrant native sparse support. `services/rag/reranker.py` (481 LOC) implements a local cross-encoder (`ms-marco-MiniLM-L-6-v2` default, `bge-reranker-v2-m3` recommended for multilingual, `reranker.py:10-13`), with a registry (`reranker_registry.py`) and an external ZeroEntropy backend option (`app/core/config.py:305-332`). But the flags say: `enable_reranker: bool = False  # DISABLED: Saves ~5GB Docker image size` (`app/core/config.py:310`), `enable_hybrid_search` default `False` (`config.py:347-351`), `enable_query_expansion` default `False` (`config.py:352-356`). `fly.toml [env]` sets none of them (checked lines 20-38), so unless overridden via Fly secrets (not inspectable on disk), **production retrieval is dense-only, un-reranked, single-query**. The gate in the tool is explicit: `use_hybrid = getattr(_settings, "enable_hybrid_search", False)` (`agentic/tools.py:177`).

**Abstain policy** — the 5 named gates hold as documented: `services/rag/agentic/_abstain_policy.py` (117 lines) centralizes GENERATION flat 0.15, LABEL per-domain (tax 0.10 / visa 0.12 / kbli 0.20), CONFIDENCE_LOW 0.15 / CONFIDENCE_HIGH 0.60, and `CONTEXT_QUALITY_MIN` (`_abstain_policy.py:53`), with `build_abstain_policy()` (`:103-117`) pulling from `EvidenceScoreConstants` + `get_abstain_threshold`. The intentional generation≠label divergence is documented in-file (`:19-29`) with the panel ruling. Evidence scoring lives in `reasoning.py` (trusted-tool flippers at `:634-699`).

**Grading** (`services/rag/grading/`, 10 files): retrieval, answer, hallucination, pricing, reasoning and self-RAG graders, wired into the live path via `orchestrator_core.py:1897` (`_run_grading_gates`). This is a real CRAG/Self-RAG-style implementation, not vapor.

**Caching is layered but split-brained.** Two modules both named `semantic_cache.py`: `services/caching/semantic_cache.py` (426 LOC) is the wired one — L1 in-memory LRU (100 entries, 5-min TTL, `:94`) + L2 Redis with **domain-aware TTLs** (`DOMAIN_TTL`, `:39`), but despite its name it matches on **exact SHA-256 query hash** (`_query_hash`, `:103`), not embedding similarity. `services/search/semantic_cache.py` (290 LOC) does true cosine-similarity matching (threshold 0.95, `:44`) but scans all cached embeddings linearly in Redis (`_find_similar_query`, `:151-182`). A `notebooklm_cache_service.py` (455 LOC) caches NLM answers separately.

**Knowledge graph.** `services/knowledge_graph/` implements extraction (Gemini + local), coreference, entity/document linking, quality filtering, community detection, ontology, and an incremental builder persisting to Postgres `kg_nodes`/`kg_edges` (`incremental_builder.py:113-118`). Query-time KG traversal is a **LangGraph StateGraph** (`services/rag/kg_langgraph_orchestrator.py:18`, 722 LOC) with optional Postgres checkpointing (`:52-55`) and four compiled domain subgraphs (`kg_subgraph_visa/tax/company/property.py`). `kg_monitoring/` adds change detection + auto-ingestion + quality checks for source drift.

**Memory.** Four memory organs: `memory_service_postgres.py` (user facts, but retrieval is `ILIKE` substring — `:473`), `episodic_memory_service.py` (587 LOC; event/emotion detection is **regex + keyword lists**, `:214-235`), `collective_memory_service.py` (533 LOC; `search_similar` admits in its own docstring "simple text matching... For semantic search, would need vector embeddings", `:472-482`), and the `memory_vector` router which does use Qdrant (`zantara_memories` collection, `app/routers/memory_vector.py:34`). Routers measured: `agentic_rag.py` 1,899 LOC, `kg_agentic.py` 470, `memory_vector.py` 371, `legal_ingest.py` 727, `ingest.py` 292, `episodic_memory.py` 257, `lam_memory.py` 256, `collective_memory.py` 118.

**Ingestion & chunking.** `services/ingestion/` (12 files) has collection lifecycle, health, warmup, performance monitoring, and a 1,541-LOC legal ingestion service. Chunking is **naive fixed-size character chunking** — `core/chunker.py:56-57`: 1,000 chars, 100 overlap, defaults from settings. A more advanced **hierarchical pipeline exists only for the politics KB experiment** (`kb/politics/hierarchical/` — own chunker, embedder, retriever, eval harness with `eval/seed_queries.jsonl`).

**Evaluation.** `services/rag/evaluation/` implements a RAGAS-style evaluator — but it is a **self-implemented LLM-as-judge with Gemini prompts in Bahasa Indonesia** (`ragas_evaluator.py:1-60`), not the `ragas` library; `create_default_client()` raises `NotImplementedError` because `backend.llm.client` was removed (`:26-28`), so it only runs where a caller passes an LLM client explicitly. It is reachable via `app/routers/monitoring_rag.py` and `agentic_rag.py`, plus A/B testing and benchmark harnesses.

**Dead code measured** (zero non-test callers, checked by grepping imports across `app/`, `services/`, `channels/`): `hyde_expander.py` (203), `multi_hop.py` (379), `query_expansion.py` (708), `nlm_verifier.py` (316), `deep_research_dispatcher.py` (174), `personalized_workflow.py` (120) — **1,900 LOC of unwired retrieval features**, including exactly the techniques (HyDE, multi-hop, multi-query expansion) that SOTA systems run in production. Wired counterparts: `crag_router.py` and `multi_agent_coordinator.py` (via `orchestrator_core.py`), `vision_rag.py` (via `tools.py`), `query_expander.py` in `services/search` (via `search_service.py`).

**Oracle layer.** `services/oracle/` (18 files) bridges NotebookLM ground truth: notebook registry, orchestrator, enrichment, cross-notebook correlation, and `nlm_shadow_retrieval.py` — a nightly-extracted `nlm_shadow_hybrid` Qdrant collection read at runtime, opt-in via `NLM_SHADOW_RETRIEVAL_ENABLED` (`:1-13`), so NLM grounding serves sub-second without CLI calls in the hot path.

## Honest state vs. SOTA

**Genuinely good — above typical mid-market RAG:**
1. **The abstain policy is best-in-class engineering.** Five named gates, one SSOT, intentional divergence documented in-file with the panel ruling that forbids "tidying" it, tripwire-tested. Most commercial RAG stacks have *no* calibrated abstain at all; the evaluation literature (RAGAS/ARES line, Vectara's faithfulness work) treats abstention as frontier. This is real safety engineering.
2. **Grading gates in the hot path** (retrieval/answer/hallucination/pricing graders) implement the CRAG/Self-RAG pattern that enterprise vendors describe as production practice — actually wired, not aspirational.
3. **Layered caching with domain TTLs** and an FAQ fast path is legitimate cost engineering for a solo-operator budget.
4. **The KG with LangGraph domain subgraphs** plus Postgres persistence is a serious structural investment few small shops make; kg_monitoring's change-detection loop mirrors what large vendors describe for KG freshness.
5. **Curated-QA grounding injection** and the NLM shadow collection are a clean "authority tier" design — precomputed ground truth served from vector storage instead of live oracle calls.

**Theater / dark machinery:**
1. **Hybrid search, cross-encoder reranking, and query expansion are all built, tested, documented — and OFF in prod** (`config.py:310,347-356`; nothing in `fly.toml [env]` turns them on). The engine the docs describe ("BM25+dense+RRF+reranking") is not the engine that runs. This is the repo's own scar family #2 ("Esiste ≠ Armato") expressed in the retrieval core.
2. **1,900 LOC of dead advanced-RAG modules** (HyDE, multi-hop, multi-query, NLM verifier, deep-research dispatcher) — capability inventory that inflates any architecture review that doesn't grep callers.
3. **"Semantic" caches that aren't**: the wired cache is exact-hash; the true semantic one (cosine 0.95) is unwired and linear-scan.
4. **Memory retrieval is substring matching** in three of four organs (`ILIKE` in postgres memory and collective memory; regex emotion detection in episodic). The names promise vector memory; only `zantara_memories` delivers it.
5. **Evaluation exists but cannot self-run** (`create_default_client` raises), and no CI/cron invokes the RAGAS harness against a golden set — no retrieval-quality regression gate protects the frozen index.

**Broken/fragile by design:**
- Collection routing depends on the LLM choosing a collection name from a prompt string (`tools.py:108-114`) — no learned or rule-based router in the hot path (the `QueryPlanner` runs only in shadow mode, `orchestrator_core.py:1855`).
- Fixed 1,000-char chunking for Indonesian legal text discards document structure (pasal/ayat hierarchy) that the corpus itself preserves in `kb/legal/` markdown.
- The frozen embedding (`text-embedding-3-small`) is a 2024-era model; the invariant is correct as a *process* rule (never change without a re-indexing plan) but the model itself now trails multilingual leaders for Indonesian retrieval (see research below).

## Deep research: the world's best

**1. Glean — hybrid retrieval as non-negotiable baseline.** Glean's production enterprise search runs every query through two concurrent first-stage retrievers — dense embeddings for semantic match and BM25-family lexical for exact terms — fused with Reciprocal Rank Fusion on ranks (never raw scores), layered under a knowledge graph with PageRank-inspired authority signals and per-user personalization ([ZenML LLMOps case study](https://www.zenml.io/llmops-database/building-robust-enterprise-search-with-llms-and-traditional-ir), [Glean blog](https://www.glean.com/blog/how-to-build-an-ai-assistant-for-the-enterprise)). The lesson for Nuzantara is uncomfortable: what Glean calls the baseline is exactly what Nuzantara built and left off.

**2. Anthropic Contextual Retrieval — the highest-leverage ingestion trick measured anywhere.** Prepending 50-100 tokens of LLM-generated document context to each chunk before embedding + BM25-indexing cut top-20 retrieval failure by 35% alone, 49% combined with contextual BM25, and **67% with reranking added** (5.7% → 1.9%) ([Anthropic engineering](https://www.anthropic.com/engineering/contextual-retrieval)). It is a pure ingestion-time cost (one cheap LLM call per chunk, cacheable), which suits a flat-subscription LLM arsenal perfectly.

**3. Qdrant's own engineering guidance — the pipeline mental model.** Qdrant's hybrid-search articles formalize what failed implementations get wrong: BM25/sparse and dense are *complementary first-stage retrievers*, RRF fuses ranks, and cross-encoder or late-interaction reranking is a *second-stage precision layer over a shortlist* — never a single blended score formula ([Hybrid Search with Query API](https://qdrant.tech/articles/hybrid-search/), [Reranking tutorial](https://qdrant.tech/documentation/tutorials-search-engineering/reranking-hybrid-search/)). Qdrant now ships miniCOIL — BM25 reweighted by term context — as a drop-in sparse upgrade. Nuzantara is on Qdrant already; the vendor's own reference architecture is the unarmed code path.

**4. Late interaction and multilingual models — the Indonesian axis.** BGE-M3 unifies dense + sparse + ColBERT-style multi-vector retrieval in one model, 100+ languages, 8,192-token inputs ([BGE-M3 paper](https://arxiv.org/html/2402.03216v3)); Jina-ColBERT-v2 gives general-purpose multilingual late interaction ([paper](https://arxiv.org/pdf/2408.16672)). Cohere Rerank 3.5 measured **+26.4% cross-lingual improvement** and +23.4% over hybrid search alone on enterprise data ([Cohere blog](https://cohere.com/blog/rerank-3pt5)). For a corpus that is largely Bahasa Indonesia queried in Italian/English/Indonesian, cross-lingual reranking is where the biggest measured wins live. Notably `bge-m3` already runs on the fleet's Ollama arsenal for other purposes.

**5. Microsoft LazyGraphRAG — graph quality at vector-RAG cost.** LazyGraphRAG defers all LLM summarization to query time: indexing cost identical to vector RAG (0.1% of full GraphRAG), global-query quality comparable to GraphRAG global search at ~700× lower query cost, and it beat all competing methods across query classes in Microsoft's BenchmarkQED ([Microsoft Research blog](https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/)). The pattern — lightweight graph at index time, lazy expansion at query time — matches Nuzantara's existing KG + community-detection assets almost exactly.

**6. Perplexity — Search as Code.** Perplexity's 2026 reference architecture exposes retrieval primitives (retrieve, filter, dedupe, rerank) as SDK building blocks that *agents compose per query* inside a sandbox, instead of one static search endpoint ([Rethinking Search as Code Generation](https://research.perplexity.ai/articles/rethinking-search-as-code-generation)). This is the frontier version of what Nuzantara's `VectorSearchTool` gestures at with prompt-chosen collection names.

**7. Vectara HHEM — faithfulness as a cheap classifier, not an LLM call.** Vectara's open HHEM model scores factual consistency of an answer against retrieved context with probabilistic output, is small enough to run locally, and is attached to *every query* in Vectara's platform ([HHEM on Hugging Face](https://huggingface.co/vectara/hallucination_evaluation_model)). ARES similarly showed fine-tuned lightweight judges beat prompted LLM judges for statistically confident RAG scoring ([ARES paper](https://arxiv.org/abs/2311.09476)).

**8. Evaluation practice — golden sets in CI.** The converged industry practice: a versioned golden set (question, reference context, ideal answer) built early, per-metric thresholds (e.g. faithfulness ≥ 0.9), evaluated on every pipeline change in CI — otherwise "quality remains unmeasurable and regressions only surface in production" (RAGAS/TruLens/ARES comparisons; Microsoft's golden-dataset methodology). Nuzantara has the harness code and zero golden sets wired to CI.

**9. Semantic caching in production.** Redis LangCache-style semantic caches report 60-85% hit rates on FAQ-shaped workloads and 50-90% LLM cost reduction, with tuned similarity thresholds (0.65-0.95 depending on wrong-hit tolerance) and embeddings indexed in a vector store — not linearly scanned ([Redis semantic caching guide](https://redis.io/blog/what-is-semantic-caching/)). A visa/tax/pricing agency chat workload is exactly FAQ-shaped.

**10. Agent memory — temporal knowledge graphs.** Zep's Graphiti builds a temporal KG with explicit fact-validity intervals and outperforms MemGPT-style recursive summarization on deep memory retrieval (94.8% vs 93.4% DMR; up to 15-point gaps on temporal queries) ([Zep paper](https://arxiv.org/abs/2501.13956)). Fact-validity intervals map one-to-one onto Indonesian regulatory life-cycles (`status_vigensi`, repealed-law exclusion) — a domain where "when was this true" is the product.

**11. Structure-aware chunking for legal text.** Multiple 2025-26 studies (Legal Chunking; oil-and-gas enterprise chunking evaluation; hierarchical indexing lines) converge: structure-aware chunking that respects headings/sections/articles consistently wins top-K retrieval metrics in specialized domains over fixed-size windows, and hierarchical chunk trees give provenance for free ([Legal Chunking study](https://www.researchgate.net/publication/386472016_Legal_Chunking_Evaluating_Methods_for_Effective_Legal_Text_Retrieval)). Indonesian law's pasal/ayat/butir hierarchy is the canonical case.

## Gap table

| Dimension | Nuzantara (measured) | SOTA (sourced) | Gap |
|---|---|---|---|
| First-stage retrieval | Dense-only in prod (`config.py:347`, flag off) | Hybrid dense+sparse everywhere (Glean, Qdrant, Anthropic) | **Severe — code exists, unarmed** |
| Fusion | RRF k=60 implemented (`hybrid_search.py:32`), dark | RRF is the standard (Glean, Qdrant) | Flag-flip away |
| Reranking | Cross-encoder built, `enable_reranker=False` (`config.py:310`) | 2nd-stage rerank is table stakes; +26% cross-lingual (Cohere 3.5) | **Severe — worst for cross-lingual queries** |
| Chunking | Fixed 1,000 chars / 100 overlap (`core/chunker.py:56`) | Structure-aware / hierarchical wins in legal domains | Severe for `legal_unified` |
| Ingestion-time context | None (raw chunks embedded) | Contextual retrieval: −49% to −67% retrieval failures (Anthropic) | Large, cheap to close |
| Embedding | Frozen `text-embedding-3-small` (2024) | BGE-M3 / multilingual multi-vector; late interaction | Medium; migration = governed re-index |
| Query routing | LLM picks collection from prompt text (`tools.py:108`); planner shadow-only | Learned/rule routers; Perplexity composes pipelines per query | Medium |
| Abstain / faithfulness | 5 named calibrated gates (SSOT, tested) | Mostly absent in industry; HHEM-style classifiers at frontier | **Nuzantara ahead** on policy; behind on classifier-based scoring |
| Eval / regression | Harness exists, no golden set, not in CI, default client raises | Golden set + thresholds in CI is converged practice | **Severe — the index is unprotected** |
| Caching | Exact-hash L1/L2 with domain TTLs; true semantic cache unwired | Semantic cache, 60-85% hit rates, vector-indexed | Medium |
| Knowledge graph | Real KG + community detection + LangGraph subgraphs | LazyGraphRAG: lazy query-time summarization at vector-RAG cost | Nuzantara has the assets; missing the lazy query pattern |
| Memory | ILIKE substring in 3 of 4 organs (`:473`, `:482`) | Temporal KG memory with validity intervals (Zep) | Severe on retrieval; temporal model absent |
| Freshness | kg_monitoring change detection + nightly NLM shadow | Continuous ingestion + temporal validity | Ahead of small-shop norm, behind temporal SOTA |

## Recommendations — reach SOTA

**R1 (P0). Build the golden set and put retrieval eval in CI — before touching retrieval.** Any retrieval change without a measuring stick is doctrine, not engineering (and flipping flags changes behavior for live clients). Assemble 100-150 QA triples per core domain (visa/kbli/tax/pricing) from `curated_qa`, real anonymized query logs, and team review; fix `ragas_evaluator.create_default_client` (pass the Gemini client explicitly); add a CI job that computes recall@10, context precision, faithfulness on the golden set against the live Qdrant snapshot. *Acceptance (falsifiable): a PR that degrades recall@10 by >3 points on the golden set goes red; the job runs on every PR touching `services/rag|search|ingestion`.* Solo-op sizing: 2-3 sessions + one team review pass for the gold answers.

**R2 (P0). Arm hybrid search + reranking behind a measured, staged rollout.** The code is written; the risk is the flag-flip without measurement (R1 first). Reranker without +5GB Docker: use the ONNX-quantized `bge-reranker-v2-m3` via fastembed (~300MB, CPU) or route reranking to the Mini's Ollama/bge-m3 as an internal service; alternatively start rerank-free with BM25+RRF only. Stage: `ENABLE_HYBRID_SEARCH=1` on one collection (`bali_zero_pricing_hybrid`, lowest risk, already `_hybrid`-formatted) → measure on golden set → widen. *Acceptance: recall@10 on golden set improves ≥10% over dense-only baseline on ≥2 domains; p95 retrieval latency stays <2× baseline; rollback is a single env unset.*

**R3 (P1). Contextual retrieval at ingestion.** Add an LLM chunk-contextualization pass (50-100 tokens of "where this chunk sits") to `ingestion_service`/`legal_ingestion_service` before embedding, per Anthropic's recipe; run it via the flat-sub CLI arsenal (Gemini/Sonnet), cache per chunk-hash. Applies at next re-index of each collection — no invariant violation (same embedding model, enriched input text). *Acceptance: retrieval-failure rate (golden-set queries whose gold context is absent from top-20) drops ≥30% on the re-indexed collection.*

**R4 (P1). Structure-aware chunking for the legal corpus.** Replace fixed 1,000-char chunking for `legal_unified` with pasal/ayat-boundary chunking (the corpus already has structured MD in `kb/legal/`; the in-repo `kb/politics/hierarchical/` pipeline is a working template — promote it, don't rewrite it). Attach hierarchy metadata (uu number, pasal, ayat) to payloads for filterable citation. *Acceptance: zero chunks in the re-indexed legal collection split a pasal mid-article (scriptable check); legal golden-set recall@5 improves; every legal answer can cite pasal-level provenance.*

**R5 (P1). One semantic cache, vector-indexed.** Merge the two `semantic_cache.py` modules: keep the wired L1/L2 + domain-TTL shell, add the cosine layer, and store cache-entry embeddings in a small Qdrant collection instead of the linear Redis scan (`services/search/semantic_cache.py:151`). Threshold per domain (start 0.92 for pricing/tax where wrong-hit is costly, 0.85 for chit-chat). *Acceptance: measured cache hit-rate ≥25% on live traffic within 2 weeks with zero wrong-hits on a 50-paraphrase probe set (probe pairs that MUST hit, and near-miss pairs that MUST NOT).*

**R6 (P2). Kill or arm the dead 1,900 LOC.** For each of `hyde_expander`, `multi_hop`, `query_expansion`, `nlm_verifier`, `deep_research_dispatcher`, `personalized_workflow`: either wire it behind a flag with a golden-set A/B, or delete it (git preserves it). Add a CI lint: any module in `services/rag/` with zero non-test importers fails. *Acceptance: the lint exists and passes; `services/rag` sheds ≥1,500 LOC or gains ≥2 armed features with measured deltas.*

**R7 (P2). Vector-grade memory retrieval.** Route `memory_service_postgres.search` and `collective_memory_service.search_similar` through the existing `zantara_memories` Qdrant collection (embed on write, search by cosine) instead of `ILIKE`. *Acceptance: a probe set of 20 paraphrased memory queries retrieves the right fact ≥90% vs the measured ILIKE baseline.*

## Recommendations — beyond SOTA

**B1. Lazy graph-summarization over the existing KG (LazyGraphRAG pattern).** Nuzantara already pays for KG extraction, community detection, and domain subgraphs — the missing piece is deferring summarization to query time: on KG fast-path hits, expand the matched community lazily (breadth-limited claim extraction over member chunks) instead of static context blocks. This delivers GraphRAG-class global answers ("what changed across immigration circulars this quarter?") at vector-RAG cost — a query class no Bali competitor can serve. *Priority P1 (after R1/R2). Acceptance: on a 20-question "global/thematic" golden subset that dense retrieval fails today, lazy-KG answers reach ≥70% judge-scored completeness at <3× median query cost.*

**B2. Calibration loop on the abstain gates — from constants to measured curves.** The 5-gate SSOT is ahead of industry; its values are still hand-set constants. Log every `(evidence_score, gate decision, domain, user feedback/correction)` tuple (the `is_divergent` property at `_abstain_policy.py:77` is already designed for this observability); quarterly, fit per-domain false-abstain vs false-answer curves and re-derive thresholds with the panel ruling as constraint (generation stays ≥ flat 0.15 in penalty domains). Nobody in the enterprise-RAG market ships *measured, domain-calibrated* abstention. *Priority P2. Acceptance: a dashboard/report showing per-domain abstain precision/recall from ≥4 weeks of logged tuples; one threshold change justified by the curve, ratified by Zero, with tripwire tests updated.*

**B3. Local HHEM-style faithfulness scorer in the confidence zone.** Run Vectara's open HHEM (small, CPU-viable, local — PII never leaves) over (answer, retrieved context) as a second opinion feeding the CONFIDENCE zone and the hallucination grader — classifier-grade faithfulness on every answer at ~zero marginal cost, where the industry pays an LLM-judge call. *Priority P2. Acceptance: HHEM score logged on 100% of answers; disagreement between HHEM and the LLM hallucination grader (>0.3 delta) flagged on <10% of golden-set answers, with disagreements triaged once.*

**B4. Retrieval-as-code for the agent fleet (Perplexity SaC pattern).** Replace the single `VectorSearchTool` prompt-menu with composable primitives exposed to the orchestrator: `retrieve(collection, query, k)`, `fuse(rrf)`, `filter(payload)`, `rerank(model)`, `dedupe()`. The ReAct agent composes per-query pipelines; the deterministic defaults stay for simple queries. This also makes every A/B a config, not a code change. *Priority P2 — architecture step, gated on R2 evidence. Acceptance: ≥3 distinct pipeline shapes observed in production traces; complex-query golden subset improves without regressing the simple-query set.*

**B5. Temporal validity on KG edges — regulation-native memory (Zep pattern).** Add `valid_from`/`valid_until`/`superseded_by` to `kg_edges` and populate from the legal corpus's status metadata; retrieval filters by as-of date. This kills the `exclude_repealed`-empty-key disease class at the root (temporal truth lives in the graph, not in a payload key someone forgot to fill) and enables "what was the rule when the client filed in 2025-03?" — beyond anything in the sector. *Priority P2. Acceptance: 10 golden temporal queries ("rule as of date X") answered correctly; repealed-law leakage on the legal golden set measured at zero.*

**B6. An Indonesian regulatory retrieval benchmark.** From the golden sets (R1) distill a 300-500 query public benchmark (immigration/company/tax, ID/EN/IT queries, pasal-level relevance judgments, no client data). Nothing comparable exists; it makes "Bali Zero has the best Indonesian regulatory retrieval" a *measurable* claim and every future model/embedding decision one command. *Priority P2, business upside for Zero. Acceptance: benchmark runs against ≥3 configurations (dense-only, hybrid, hybrid+rerank) producing a ranked table.*

## §Meta-pattern

The engine's disease is not missing capability — it is **built ≠ armed**, the repo's own scar family #2 measured in its most valuable organ. Hybrid search, reranking, query expansion, RAGAS evaluation, a true semantic cache, HyDE, multi-hop: all written, most tested, none running. The documentation then describes the *built* system, so every downstream reader (including audits and this program's own briefs) inherits an inflated picture of the running engine. The secondary pattern is **naming inflation**: a "semantic" cache that hashes, "vector" memory that ILIKEs, a "RAGAS" evaluator that cannot construct its own client. Both patterns have the same antidote, and it is the same one the fleet already uses for cron theater: *a measured gate per capability* — a golden-set eval in CI is to retrieval what the heartbeat probe is to a daemon. R1 is therefore not one recommendation among ten; it is the precondition that turns the other nine from doctrine into engineering.

## §Solo-operatore

Decisions only Zero can take:

1. **Prod flag-flips on live client traffic** (R2): enabling hybrid/rerank changes answer behavior on WhatsApp/web clients. Recommend staged rollout per collection; Zero owns the go and the rollback ruling.
2. **Spend — reranker/runtime resources**: local ONNX rerank fits the current Fly shared-2x 2GB only if measured; if it needs a bigger VM (~$/mo) or the Cohere Rerank API (per-token paid, requires explicit authorization under the 2026-06-04 cost rule; PII boundary applies to queries sent to it), that is Zero's call. Free path exists (BM25+RRF only, no rerank) — worth arming regardless.
3. **Embedding migration ruling** (gap table row "Embedding"): moving off frozen `text-embedding-3-small` to a multilingual model (bge-m3 local = $0 + sovereignty win) requires the full re-index plan the invariant demands, plus accepting temporary dual-collection serving. Not urgent; R3 (contextual retrieval) captures most of the win without touching the invariant. Defer until R1 metrics exist to judge it.
4. **Team time for golden answers** (R1): ~2-3 hours of domain-expert review (Ari/Surya lanes) to bless gold answers; only Zero can allocate team hours.
5. **Benchmark publication** (B6): whether the Indonesian regulatory benchmark is published (marketing asset) or kept internal (competitive moat) is a business decision.

## Sources

1. Microsoft Research — LazyGraphRAG: https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/
2. Anthropic Engineering — Contextual Retrieval: https://www.anthropic.com/engineering/contextual-retrieval
3. Qdrant — Hybrid Search with the Query API: https://qdrant.tech/articles/hybrid-search/
4. Qdrant — Reranking in Hybrid Search tutorial: https://qdrant.tech/documentation/tutorials-search-engineering/reranking-hybrid-search/
5. ZenML LLMOps Database — Glean: Building Robust Enterprise Search with LLMs and Traditional IR: https://www.zenml.io/llmops-database/building-robust-enterprise-search-with-llms-and-traditional-ir
6. Glean — Learning lessons from building an enterprise AI assistant: https://www.glean.com/blog/how-to-build-an-ai-assistant-for-the-enterprise
7. Perplexity Research — Rethinking Search as Code Generation: https://research.perplexity.ai/articles/rethinking-search-as-code-generation
8. Vectara — HHEM hallucination evaluation model: https://huggingface.co/vectara/hallucination_evaluation_model
9. ARES: An Automated Evaluation Framework for RAG (arXiv): https://arxiv.org/abs/2311.09476
10. BGE-M3 paper (arXiv): https://arxiv.org/html/2402.03216v3
11. Jina-ColBERT-v2 (arXiv): https://arxiv.org/pdf/2408.16672
12. Cohere — Introducing Rerank 3.5: https://cohere.com/blog/rerank-3pt5
13. Redis — What is semantic caching: https://redis.io/blog/what-is-semantic-caching/
14. Zep: A Temporal Knowledge Graph Architecture for Agent Memory (arXiv): https://arxiv.org/abs/2501.13956
15. Legal Chunking: Evaluating Methods for Effective Legal Text Retrieval: https://www.researchgate.net/publication/386472016_Legal_Chunking_Evaluating_Methods_for_Effective_Legal_Text_Retrieval
