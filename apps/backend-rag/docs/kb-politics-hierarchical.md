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
| ID generation | MD5(record_id\|chunk_type\|index) | UUID | Deterministic, path-independent → idempotent ingest even if files move. |
| Score aggregation | Sum of child scores | Max, mean | Sum rewards records with multiple matching claims. |
| Hybrid search | Dense + BM25 sparse + RRF | Dense only | BM25 fixes exact keyword matching for dates, abbreviations, names. |
| Sparse encoder | BM25 (pure Python, no deps) | SPLADE, learned sparse | Zero dependency, deterministic, tiny vocab (165 terms for seed corpus). |

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

| Metric | Dense only | **Hybrid (Dense+BM25)** |
|--------|:----------:|:-----------------------:|
| Mean nDCG@5 (hard) | 0.7555 | **0.9410** |
| Mean Recall@5 (hard) | 0.8125 | **0.9844** |
| Mean nDCG@5 (all) | 0.6775 | **0.8353** |
| Mean Recall@5 (all) | 0.7500 | **0.8875** |

### Per-query breakdown (hybrid)

| Query | nDCG@5 | Recall@5 | Dense nDCG | Delta |
|-------|--------|----------|:----------:|:-----:|
| Siapa presiden Indonesia saat ini? | 0.631 | 1.000 | 0.500 | +0.13 |
| Kapan Jokowi menjadi presiden? | 1.000 | 1.000 | 1.000 | = |
| Partai apa yang didirikan Prabowo? | 1.000 | 1.000 | 0.920 | +0.08 |
| Hasil pemilu presiden 2024 | 1.000 | 1.000 | 1.000 | = |
| Siapa yang memimpin PDI-P? | 0.850 | 1.000 | 0.387 | **+0.46** |
| Megawati pernah menjabat apa? | 1.000 | 1.000 | 1.000 | = |
| Pemilu presiden Indonesia 2014 | 1.000 | 1.000 | 0.000 | **+1.00** |
| SBY partai apa? | 1.000 | 1.000 | 0.920 | +0.08 |
| Gubernur DKI Jakarta sebelum Anies | 0.920 | 1.000 | 0.387 | **+0.53** |
| Berapa persen suara Prabowo 2024? | 0.850 | 1.000 | 0.613 | +0.24 |
| Partai Golkar didirikan tahun berapa? | 1.000 | 1.000 | 1.000 | = |
| Who won the 2019 election? (EN) | 1.000 | 1.000 | 1.000 | = |
| Jusuf Kalla menjabat sebagai apa? | 1.000 | 1.000 | 1.000 | = |
| Perbandingan suara 2004 vs 2009 | 1.000 | 1.000 | 0.920 | +0.08 |
| Ganjar Pranowo gubernur mana? | 1.000 | 1.000 | 1.000 | = |
| Daftar presiden sejak 2001 | 0.805 | 0.750 | 0.442 | +0.36 |

**Key wins from hybrid:** Pemilu 2014 (0.0→1.0), PDI-P leadership (0.39→0.85), DKI governor (0.39→0.92). BM25 fixes exact keyword matching for dates and names that dense embeddings miss.

**Caveat:** 4 weak-label queries (LHKPN, mutasi, jadwal, koalisi) have uncertain or empty ground truth. Hard-label metrics are more reliable.

## Known gaps

1. **List queries degrade gracefully:** "Daftar presiden sejak 2001" retrieves 3/4 presidents (Recall=0.75). The fourth scores lower in aggregate because fewer claims match the broad query. Resolves naturally as corpus grows.

2. **Small corpus:** 21 records, 86 vectors. The parent-child ratio (1:3.8) and BM25 vocab (165 terms) will scale, but IDF weights become more meaningful with more documents.

## Follow-up

1. **Cross-entity resolution:** Claims reference `party_id` and `person_id` as raw IDs (e.g., "party:id:pdip"). Resolving to human names would improve semantic matching.
