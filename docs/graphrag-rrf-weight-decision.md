# Trimodal RRF Weight Decision — GraphRAG 2.0

Generated: 2026-04-17 (Air-3 session)

## Method

- Collection: `legal_unified_hybrid_hybrid` (12 queries)
- Proxy metrics (no gold labels available in this collection):
    - **coverage@10** — fraction of top-10 docs with ≥1 `kg_entity_mentions` link
    - **mentions_per_result@10** — avg linked entities per top-10 doc
    - **jaccard_vs_baseline** — Jaccard similarity of top-10 id set vs w=(0.5,0.5,0.0)
- dense = Qdrant named-vector `dense` search on `text-embedding-3-small`
- sparse = payload full-text match proxy (BM25 index not queried directly here)
- graph = mentions count for query-detected entities in `kg_entity_mentions`

## Configurations

| name | dense | sparse | graph |
|------|-------|--------|-------|
| w=(0.5, 0.5, 0.0) | 0.5 | 0.5 | 0.0 |
| w=(0.4, 0.3, 0.3) | 0.4 | 0.3 | 0.3 |
| w=(0.35, 0.15, 0.5) | 0.35 | 0.15 | 0.5 |

## Aggregate results

| variant | coverage@10 | mentions/result | jaccard vs baseline | n |
|---|---|---|---|---|
| w=(0.5, 0.5, 0.0) | 0.633 | 0.65 | 1.0 | 12 |
| w=(0.4, 0.3, 0.3) | 0.617 | 0.68 | 0.431 | 12 |
| w=(0.35, 0.15, 0.5) | 0.65 | 0.73 | 0.335 | 12 |

## Per-query detail

### persyaratan KITAS untuk investor asing
- entities detected: `['kitas']`
- variants:
    - w=(0.5, 0.5, 0.0): cov=0.3 mpr=0.3 jac=1.0
    - w=(0.4, 0.3, 0.3): cov=0.4 mpr=0.5 jac=0.333
    - w=(0.35, 0.15, 0.5): cov=0.4 mpr=0.7 jac=0.333

### UU Cipta Kerja ketenagakerjaan
- entities detected: `[]`
- variants:
    - w=(0.5, 0.5, 0.0): cov=1.0 mpr=1.0 jac=1.0
    - w=(0.4, 0.3, 0.3): cov=0.9 mpr=0.9 jac=0.333
    - w=(0.35, 0.15, 0.5): cov=0.9 mpr=0.9 jac=0.333

### NIB untuk PT PMA di Bali
- entities detected: `['nib', 'pt pma']`
- variants:
    - w=(0.5, 0.5, 0.0): cov=0.9 mpr=0.9 jac=1.0
    - w=(0.4, 0.3, 0.3): cov=0.6 mpr=0.8 jac=0.333
    - w=(0.35, 0.15, 0.5): cov=1.0 mpr=1.1 jac=0.0

### KBLI konsultasi manajemen
- entities detected: `[]`
- variants:
    - w=(0.5, 0.5, 0.0): cov=0.4 mpr=0.4 jac=1.0
    - w=(0.4, 0.3, 0.3): cov=0.2 mpr=0.2 jac=0.333
    - w=(0.35, 0.15, 0.5): cov=0.2 mpr=0.2 jac=0.333

### PPh 21 karyawan expat
- entities detected: `['pph 21']`
- variants:
    - w=(0.5, 0.5, 0.0): cov=0.3 mpr=0.3 jac=1.0
    - w=(0.4, 0.3, 0.3): cov=0.3 mpr=0.3 jac=0.333
    - w=(0.35, 0.15, 0.5): cov=0.3 mpr=0.3 jac=0.333

### izin usaha restoran di Bali
- entities detected: `[]`
- variants:
    - w=(0.5, 0.5, 0.0): cov=0.7 mpr=0.7 jac=1.0
    - w=(0.4, 0.3, 0.3): cov=0.9 mpr=0.9 jac=0.333
    - w=(0.35, 0.15, 0.5): cov=0.9 mpr=0.9 jac=0.333

### Permen perlindungan data pribadi
- entities detected: `[]`
- variants:
    - w=(0.5, 0.5, 0.0): cov=0.4 mpr=0.4 jac=1.0
    - w=(0.4, 0.3, 0.3): cov=0.4 mpr=0.4 jac=0.333
    - w=(0.35, 0.15, 0.5): cov=0.4 mpr=0.4 jac=0.333

### BPJS Kesehatan pekerja asing
- entities detected: `['bpjs']`
- variants:
    - w=(0.5, 0.5, 0.0): cov=0.9 mpr=0.9 jac=1.0
    - w=(0.4, 0.3, 0.3): cov=0.9 mpr=0.9 jac=1.0
    - w=(0.35, 0.15, 0.5): cov=0.9 mpr=0.9 jac=1.0

### visa tinggal terbatas investor
- entities detected: `[]`
- variants:
    - w=(0.5, 0.5, 0.0): cov=0.4 mpr=0.4 jac=1.0
    - w=(0.4, 0.3, 0.3): cov=0.3 mpr=0.3 jac=0.538
    - w=(0.35, 0.15, 0.5): cov=0.3 mpr=0.3 jac=0.538

### persyaratan modal PMA minimum
- entities detected: `[]`
- variants:
    - w=(0.5, 0.5, 0.0): cov=0.3 mpr=0.3 jac=1.0
    - w=(0.4, 0.3, 0.3): cov=0.5 mpr=0.5 jac=0.429
    - w=(0.35, 0.15, 0.5): cov=0.5 mpr=0.5 jac=0.429

### Peraturan Pemerintah tentang OSS
- entities detected: `['oss']`
- variants:
    - w=(0.5, 0.5, 0.0): cov=1.0 mpr=1.1 jac=1.0
    - w=(0.4, 0.3, 0.3): cov=1.0 mpr=1.3 jac=0.333
    - w=(0.35, 0.15, 0.5): cov=1.0 mpr=1.3 jac=0.0

### imigrasi izin tinggal KITAP
- entities detected: `['kitap', 'imigrasi']`
- variants:
    - w=(0.5, 0.5, 0.0): cov=1.0 mpr=1.1 jac=1.0
    - w=(0.4, 0.3, 0.3): cov=1.0 mpr=1.2 jac=0.538
    - w=(0.35, 0.15, 0.5): cov=1.0 mpr=1.3 jac=0.053

## Decision

- **Picked:** `w=(0.5, 0.5, 0.0)`
- Baseline coverage@10 = 0.633, picked coverage@10 = 0.633
- Rationale: prefer highest coverage@10 (grounded in KG) provided the
  result set is not a radical departure from bimodal (jaccard ≥ 0.4),
  which would indicate graph signal is dominating rather than
  augmenting.

## Caveats

- Proxy metrics, not human-labelled relevance. MRR/NDCG/Recall require a
  gold-standard Q→relevant-doc dataset that does not yet exist for this
  collection.
- Sparse branch is a payload full-text proxy; native BM25 sparse vectors
  would yield slightly different rankings but similar deltas across
  weight configurations.
- Next step: collect 50-100 gold-labelled queries (e.g. from production
  Zantara logs with user-clicked citations) and rerun with MRR/NDCG/Recall.
