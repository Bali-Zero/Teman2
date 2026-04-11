# KB Politics — Hierarchical Retrieval

## Architecture

```
backend/kb/politics/hierarchical/
├── __init__.py       — public API
├── chunker.py        — JSONL → parent + child chunks
├── extractor.py      — rule-based claim extraction (no LLM, no spaCy)
├── embedder.py       — batched local embedding (sentence-transformers)
├── ingest.py         — idempotent upsert to Qdrant
├── retriever.py      — query → child search → parent aggregation → rerank
└── eval.py           — nDCG@5 + Recall@5 harness

backend/kb/politics/eval/
└── seed_queries.jsonl — 20 queries (16 hard, 4 weak labels)

scripts/
├── ingest_kb_politics_hier.py  — CLI entry for real Qdrant ingest
└── run_hier_eval.py            — self-contained in-memory eval
```

### Data flow

```
JSONL records (persons, parties, elections, jurisdictions)
    │
    ▼
HierarchicalChunker
    ├── Parent: full record text (~200-800 tokens)
    └── Children: claim-level sentences (~20-80 tokens each)
            each child → parent_id pointer
    │
    ▼
LocalEmbedder (paraphrase-multilingual-MiniLM-L12-v2, 384 dims)
    │
    ▼
Qdrant collection: kb_politics_hier_v1
    │
    ▼ (at query time)
HierarchicalRetriever
    1. Embed query
    2. Search children (top-20 nearest)
    3. Aggregate scores by parent_id (sum)
    4. Fetch parent texts
    5. Return parents sorted by aggregated child score
```

### Design decisions

| Decision | Choice | Alternative | Why |
|----------|--------|-------------|-----|
| Claim extraction | JSON field traversal | spaCy NLP | Data is structured JSONL, not free text. Avoids 30MB dep. Deterministic. |
| Embedding model | paraphrase-multilingual-MiniLM-L12-v2 | all-MiniLM-L6-v2 | Better Indonesian support. 384 dims same as fallback. |
| Collection | kb_politics_hier_v1 | Extend politics_id | Separate collection allows A/B comparison with flat baseline. |
| ID generation | MD5(source_path\|record_id\|chunk_type\|offset) | UUID | Deterministic → idempotent ingest. |
| Score aggregation | Sum of child scores | Max, mean | Sum rewards records with multiple matching claims. |

## Ingest

### CLI usage

```bash
cd apps/backend-rag

# Dry run (no Qdrant needed)
PYTHONPATH=. python scripts/ingest_kb_politics_hier.py --dry-run

# Real ingest (requires local Qdrant on :6333)
PYTHONPATH=. python scripts/ingest_kb_politics_hier.py

# Ingest + eval
PYTHONPATH=. python scripts/ingest_kb_politics_hier.py --eval

# Self-contained in-memory eval (no external Qdrant)
PYTHONPATH=. python scripts/run_hier_eval.py
```

### Ingest stats (real run, 2026-04-11)

| Metric | Value |
|--------|-------|
| Docs processed | 18 |
| Parents | 18 |
| Children | 68 |
| Total vectors | 86 |
| Embedding model | paraphrase-multilingual-MiniLM-L12-v2 |
| Embedding dims | 384 |
| Embedding time | 0.50s |
| Total runtime | 13.19s (includes model loading) |
| Peak RAM | 1,259 MB |

## Evaluation

### Methodology

- 20 seed queries derived from KB content (no real intel data)
- 16 hard labels (verified relevant_doc_ids), 4 weak labels
- Query types: factual, temporal, relation, event, comparison, list, compliance, mutation, schedule
- Metrics: nDCG@5 (normalized discounted cumulative gain at rank 5), Recall@5

### Results (2026-04-11)

| Metric | All (20) | Hard labels (16) |
|--------|----------|-------------------|
| Mean nDCG@5 | 0.6775 | **0.7555** |
| Mean Recall@5 | 0.7500 | **0.8125** |

### Per-query breakdown

| Query | nDCG@5 | Recall@5 | Label |
|-------|--------|----------|-------|
| Siapa presiden Indonesia saat ini? | 0.500 | 1.000 | HARD |
| Kapan Jokowi menjadi presiden? | 1.000 | 1.000 | HARD |
| Partai apa yang didirikan Prabowo? | 0.920 | 1.000 | HARD |
| Hasil pemilu presiden 2024 | 1.000 | 1.000 | HARD |
| Siapa yang memimpin PDI-P? | 0.387 | 0.500 | HARD |
| Megawati pernah menjabat apa? | 1.000 | 1.000 | HARD |
| Pemilu presiden Indonesia 2014 | 0.000 | 0.000 | HARD |
| SBY partai apa? | 0.920 | 1.000 | HARD |
| Gubernur DKI Jakarta sebelum Anies | 0.387 | 0.500 | HARD |
| Berapa persen suara Prabowo 2024? | 0.613 | 0.500 | HARD |
| Partai Golkar didirikan tahun berapa? | 1.000 | 1.000 | HARD |
| Who won the 2019 election? (EN) | 1.000 | 1.000 | HARD |
| Daftar presiden sejak 2001 | 0.442 | 0.500 | HARD |
| Jusuf Kalla menjabat sebagai apa? | 1.000 | 1.000 | HARD |
| Perbandingan suara 2004 vs 2009 | 0.920 | 1.000 | HARD |
| Ganjar Pranowo gubernur mana? | 1.000 | 1.000 | HARD |

**Caveat:** 4 weak-label queries (LHKPN, mutasi, jadwal, koalisi) have uncertain or empty ground truth. Their inclusion in "all" metrics drags down the average. Hard-label metrics are more reliable.

## Known gaps

1. **Pemilu 2014 query failure (nDCG=0.0):** The query "Pemilu presiden Indonesia 2014" retrieved persons (Jokowi, Prabowo) instead of the election record. This happens because child claims for persons mention "2014" in office dates, creating a stronger aggregate signal than the election's claim children. Fix: boost election record_type children when query contains "pemilu" keywords.

2. **Small corpus bias:** With only 21 records and 86 vectors, cosine similarity has limited discriminating power. Precision will improve as the corpus grows. The hierarchical structure is designed to scale — the parent-child ratio (1:3.8) should hold as data grows.

## Follow-up

1. **Cross-entity resolution:** Claims reference `party_id` and `person_id` as raw IDs (e.g., "party:id:pdip"). Resolving these to human names in claim text would improve semantic matching for queries that use party/person names.

2. **Hybrid search (BM25 + dense):** Adding BM25 sparse vectors would help with exact keyword matching (e.g., specific dates, KBLI codes). The Qdrant collection could be upgraded to named vectors (`dense` + `sparse`) following the `_hybrid` pattern used by other collections.

3. **Query-type routing:** Route queries containing "pemilu", "pilkada", "pilpres" keywords to election records with a filter boost, similar to how the RAG orchestrator handles intent classification.
