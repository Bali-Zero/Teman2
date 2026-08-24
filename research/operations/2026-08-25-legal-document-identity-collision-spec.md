# Legal document identity: a collision that destroyed data, and why the obvious fix is worse

> **Status:** SPEC. No code change is proposed for merge yet — the first attempt
> (PR #4864) was written, adversarially refuted, independently confirmed wrong,
> and reverted the same night. This document exists because the surface is
> under-specified, and the repo rule for that case is *write the spec, do not
> open the third PR*.

## 1. The defect, measured

On 2026-08-25 the production Qdrant collection `legal_unified_hybrid_hybrid`
held **544 points under a single `document_id`, `Permen_1_2026`, belonging to two
unrelated laws**:

| what | points |
|---|---|
| PMK 1/2026 — Ministry of **Finance**, Coretax tax administration | 494 |
| Permen Imipas 1/2026 — Ministry of **Immigration**, pencegahan/penangkalan | 50 |

The tax regulation had upserted **544 chunks of its own** (ingestion log line
127). 494 survive. The immigration regulation upserted 50 (log line 8393).
`494 + 50 = 544`: **50 chunks of the tax regulation were destroyed**, silently.
Nothing failed — an overwrite is a successful upsert.

A full scan of all **83,969 points / 28 distinct `document_id`s** found exactly
one such collision. Reproduce with a scroll over
`with_payload: ["document_id", "book_title"]`, grouping titles per id.

### Mechanism

- `build_content_bound_legal_doc_id()` composes identity from the extracted
  triple `(type_abbrev, number, year)`.
- **That triple does not identify an Indonesian instrument.** Every ministry
  numbers its regulations from 1 each year, so PMK 1/2026 and Permen Imipas
  1/2026 both reduce to `Permen_1_2026`.
- `hierarchical_indexer.py:234` builds `pasal_id = f"{document_id}_Pasal_{n}"`,
  and `:340` builds the Qdrant point id as `uuid5(NAMESPACE, chunk_id)`.
  Shared `document_id` + shared pasal number ⇒ **same point id** ⇒ overwrite.

The function already knew identity should be bound to the source bytes — it did
so **only when the extracted triple was visibly incomplete**
(`DOC`/`UNKNOWN`/`0`/`NONE`). That covers the case where the extractor *admits
it does not know*, and misses the case that actually cost data: a **confident,
complete, non-unique** answer. Confidence was never evidence of uniqueness.

## 2. Why the obvious fix is a net regression

PR #4864 made the source-hash suffix **unconditional**. It does remove the
collision — and breaks two invariants that were load-bearing. Both were raised
by a cross-family refuter and then **independently confirmed against the code**,
with file:line, by a second reader.

### 2a. It breaks historical replacement (CONFIRMED)

`legal_ingestion_service.py:746` computes
`current_doc_id = build_content_bound_legal_doc_id(metadata, source_sha256)`,
where `source_sha256` (`:443-444`) is the sha of **this call's own file bytes**.
When a law is superseded, the historical ingest uses that value to quarantine
(`:793`) and then `delete_by_filter(metadata_filter={"document_id":
current_doc_id})` (`:821-822`) the CURRENT version's points.

The trigger for that path is *a different document arriving* — hence different
bytes, hence a different sha, hence a `current_doc_id` that **cannot match** the
id the current version was stored under. `_convert_filter_to_qdrant_format`
(`qdrant_db.py:429-430`) builds a strict exact-value match, so the filter finds
**zero points**. Observable consequence: the superseded law stays live with
`retrieval_scope="current"` next to its replacement, and retrieval serves stale
law as current — silently.

The delete key only worked *because* the id was byte-independent when metadata
was complete. Removing that made the collision impossible and the supersession
impossible at the same time.

### 2b. It institutionalises duplication on re-download (CONFIRMED)

`source_sha256` is the hash of raw file bytes. A re-download of the *same* law
differing by one byte (regenerated PDF, new watermark, re-scan) yields a new id,
a new set of point ids, and a **full second copy** of the law. The only two
paths in the service that remove existing points are both hard-gated on
`retrieval_scope == HISTORICAL_RETRIEVAL_SCOPE` (`:793`, `:820-822`), so a
normal current-scope re-ingest removes nothing.

The PR's docstring claimed "same file re-ingested ⇒ same sha ⇒ same id ⇒
overwrite, not duplicate". True, and vacuous: it guarantees idempotence for the
one input that never needed protection (byte-identical re-ingest) and withdraws
it from the input that did.

### 2c. It left the suite red (CONFIRMED)

`pytest backend/tests/unit/services/ingestion/test_legal_ingestion_service.py`
⇒ **2 failed, 29 passed**. Both failures are pre-existing tests that pin the old
identity:

- `test_historical_source_is_namespaced_and_has_a_retrieval_guard` — expected
  `Perpres_43_2011__historical`, got `Perpres_43_2011_62a3c476c9c2771a__historical`
- `test_post_quarantine_failure_requires_human_review_without_rollback` —
  expected the quarantine filter on `Perpres_43_2011`, got it on
  `Perpres_43_2011_62a3c476c9c2771a`

**Process note, recorded deliberately.** The author ran the new tests with a
`-k` filter and reported them green. The filter selected exactly the tests that
could not contradict the change. The suite that would have caught it was one
command away. *A probe chosen after the change, that only covers the change, is
not evidence the change is safe.*

## 3. What a correct identity has to satisfy

Any accepted design must hold all four simultaneously. 2a and 2b exist because
the refuted attempt held only I1.

- **I1 — Unique per instrument.** PMK 1/2026 ≠ Permen Imipas 1/2026.
- **I2 — Stable across byte changes of the same instrument.** A re-download or
  re-scan must land on the same identity, or supersession and dedup both break.
- **I3 — Idempotent.** Re-ingesting a document refreshes its points; it never
  duplicates them.
- **I4 — Collisions must be loud.** Whatever residual classes remain, a second
  document arriving on an occupied identity must raise, not overwrite. This is
  the only invariant that protects against the classes nobody has enumerated —
  and it is the one whose absence turned this defect into data loss instead of
  an error message.

## 4. Candidate designs (none yet chosen)

**A. Add the issuing authority to the triple** → `PMK_1_2026` vs
`PermenImipas_1_2026`. Satisfies I1–I3, human-readable, stable. Cost: the
issuer must be extracted reliably, and today's extractor cannot even get the
*type* right (§5). Probably requires the ministry to be a declared field on the
ingestion entry rather than an extracted one.

**B. Derive identity from the curated source filename.** Our corpus filenames
already encode the instrument (`PMK_1_2026_Coretax_System.pdf`). Satisfies
I1–I3 for curated ingests; undefined for uploads through the router, where the
filename is caller-controlled and untrusted.

**C. Write-time uniqueness preflight (I4).** Before upsert, scroll for the
computed `document_id`; if points exist under it whose `file_path`/source sha
differ, refuse loudly. **This is orthogonal to A and B and should probably land
regardless of which is chosen** — it converts every future silent overwrite,
including from classes not yet imagined, into an observable failure.

Recommended shape: **C first** (it is additive, breaks no invariant, and is the
one change that would have turned this incident into an alert), then A or B as
a separate, migrated change.

## 5. The neighbouring defect (separate concern, not fixed here)

The metadata extractor assigns the **wrong legal type and number to 6 of the 19
documents** in the 2026-08-25 corpus. `LEGAL_TYPE_PATTERN`
(`backend/core/legal/constants.py:91`) carries no `KEPUTUSAN MENTERI` entry, and
`metadata_extractor.py` takes the **first match anywhere in the text** — so a
Kepmen's own heading is skipped and the first law cited in its `Mengingat`
preamble is adopted instead.

Live example, reproduced from the real file: the Kepmen on border-post work
arrangements (`M.IP-19.GR.01.01/2025`) is indexed as **`UU 28/2025`** — a
ministerial decision presented as an act of parliament, carrying a number
borrowed from *Undang-Undang Nomor 28 Tahun 1999* quoted in its preamble, and a
year taken from elsewhere in the text. The chunk's own injected
`[CONTEXT: UU - NO 28 - TAHUN 2025 - ...]` header carries the false citation into
the text an LLM reads.

Also mislabelled by the same mechanism: Perpres 157/2024 → `Perpres 39/2024`;
Pergub Bali 14/2023 → `UU 14/2023`; SE Gubernur Bali 09/2025 → `PP 18/2025`;
PP 9/2026 → `UU 17/2026`.

This is a citation-correctness defect on a client-facing surface and deserves
its own PR with its own guilt/innocence tests.

## 6. Repair still owed

The 50 destroyed Coretax chunks are restored by re-ingesting PMK 1/2026 — but
**only after** an identity fix lands, or the re-ingest simply re-runs the
collision in the other direction.
