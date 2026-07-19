# Curated Q&A corpus (SPEC v2 D3 — F1b)

This directory holds **normalized, pre-vetted Q&A JSONL files** consumed by
`scripts/curated_qa_harvest.py`. Each file is one JSON object per line
(`.jsonl`), one row per question.

Files are produced by the converters in `scripts/curated_qa_convert_e33.py`
(or hand-authored following the same schema) and are meant to be
**repo-reviewable** — this is the audit trail behind the safety invariant:

> NO verbatim serving from any similarity-based layer; verbatim only from
> exact-match FAQ cache with pre-vetted provenance.

## Schema (one JSON object per line)

```json
{
  "question": "string — the exact question text",
  "answer": "string | null — the vetted, client-facing answer. null means this row is a QUESTION-ONLY seed (see below) and MUST be skipped by the FAQ sink.",
  "domain": "string — visa | tax | kbli | property | default | ...",
  "lang": "string — ISO-ish language tag, e.g. 'en', 'id'",
  "source_ref": "string — stable reference to the source document/anchor, e.g. 'E33-DEFINITIVE-CHATKB-2026-07-15.md#Q1'",
  "source_date": "string — ISO date (YYYY-MM-DD) the source content was authored/reconciled",
  "confidence_class": "string — the source's own confidence label (e.g. BERSYARAT, JELAS, BELUM_DIATUR_PUBLIK, KEBIJAKAN_PENYEDIA, DINAMIS) or 'UNSCORED' for question-only seeds",
  "law_refs": ["array of strings — verbatim law/citation references, [] if none"],
  "source_priority": "int — collision-policy rank for the FAQ cache; higher wins, never silently overwritten by a lower-priority write. Callers of curated_qa_harvest.py choose this per corpus/batch.",
  "verbatim_eligible": "bool — Phase-0 safety rail (FATAL 3). BEST-EFFORT ONLY as written by a converter/author — curated_qa_harvest.py NEVER trusts this stored value; it independently RE-DERIVES eligibility at harvest time (confidence_class == 'JELAS' AND non-price AND non-client_specific) and uses ONLY that recomputed value to gate the FAQ (Redis) sink write. A stored value that disagrees with the derived one is logged as drift, not honored.",
  "client_specific": "bool — Phase-0 safety rail (FATAL 3). Converter/author-set (default false) — requires domain judgment no detector can supply, so the harvester TRUSTS this field (unlike verbatim_eligible). true means the answer is specific to one client's situation and must never be served verbatim."
}
```

All fields are **required** on every row — `curated_qa_harvest.py` validates
the shape before writing to either sink. This is a flat schema (no nested
metadata dict) so it maps directly onto the FAQ cache's `metadata` argument
and onto a **flat Qdrant payload** for the `curated_qa` collection (data
invariant: Qdrant payloads are never nested).

### FAQ-sink eligibility (verbatim_eligible)

Only `JELAS`-classed, non-price, non-`client_specific` rows may ever reach
the exact-match FAQ (Redis) sink — that sink bypasses the abstain gate on
every hit, so a conditional ("depends on your case") answer served verbatim
with zero reasoning is a wrong answer waiting for the wrong client.
`BERSYARAT` / `BELUM_DIATUR_PUBLIK` / `KEBIJAKAN_PENYEDIA` / `DINAMIS` rows
are grounding-only (Qdrant `curated_qa` collection) forever — see
`curated_qa_harvest.py::_derive_verbatim_eligible`.

## Question-only seeds (`answer: null`)

Some source corpora (NLM prewarm question banks, golden-answer canonical
question lists) only have questions — the actual answer lives elsewhere
(a live NLM query, a Postgres `golden_answers` table) and is **not**
reproduced here. Those rows are written with `"answer": null`.

`curated_qa_harvest.py --faq` **silently skips** answer-less rows for the
FAQ sink (an FAQ cache entry with no answer is meaningless and would violate
the provenance contract in `notebooklm_cache_service.py`, which requires a
non-empty string answer). They are still counted and reported, and remain
useful later for **coverage analysis** (e.g. "which prewarm/golden questions
still have no curated answer yet").

## Sinks

- `--faq`: writes to the Redis FAQ cache (`NotebookLMCacheService`),
  **domain-scoped keys** (`notebook_id=domain_scope_id(domain)`, Phase-0
  safety rail FATAL 1) — this is what `orchestrator_core.check_faq_cache()`
  reads via `faq_cache.get(query, notebook_id=domain_scope_id(classified_domain))`,
  with a dual-read fallback to the legacy unscoped key for pre-Phase-0
  entries (only served when the stored domain matches).
- `--qdrant`: writes to the `curated_qa` Qdrant collection (logical name
  registered in `backend/core/collection_registry.py`), embedding the
  **question** with the frozen `text-embedding-3-small` model. Used by the
  D3-L2 grounding-injection step in `orchestrator_core.py`.

## Corpora landed here so far

| File | Rows | Source | Converter mode |
|---|---|---|---|
| (none committed by this build — see PENDING-ARMS for the E33/golden/prewarm conversion runs) | | | |

Corpus growth follows the same JSONL schema per domain
(`apps/backend-rag/data/curated_qa/<domain-or-batch>.jsonl`), reviewed in the
PR that adds them.
