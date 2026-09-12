# B1.3 build spec — the evidence-sufficiency benchmark, frozen

Mandate B1 (BLUE), PR B1.3. Contract: `research/operations/2026-09-11-bot-staff-room/B1-design.md` §4 B1.3 and
README D2/D5. Paths relative to `apps/backend-rag/backend/`. Behaviour-preserving: no file under
`services/**`, `core/**`, `app/**` changes; `tests/unit/services/rag/agentic/test_evidence_cross_language.py`
stays byte-identical (its three wrong expectations are RECORDED here, activated in B2.1).

## Files

- `tests/benchmarks/evidence_sufficiency/manifest_mandatory.json` — the frozen mandatory set.
- `tests/benchmarks/evidence_sufficiency/manifest_supplement_b2.json` — `{"schema_version": 1, "cases": []}` (B2 only).
- `tests/benchmarks/evidence_sufficiency/validation_codex.json` — the independently drawn validation set; written
  LATER from the adversarial seat's output, verbatim. Create it now as `{"schema_version": 1, "drawn_by": null, "cases": []}`.
- `tests/benchmarks/evidence_sufficiency/harness.py` — pure functions + a `main()` CLI printing the JSON report.
- `tests/unit/services/rag/test_evidence_sufficiency_benchmark.py` — structural assertions only.
- `__init__.py` files as needed so `backend.tests.benchmarks.evidence_sufficiency.harness` imports.

## Manifest header

`schema_version: 1`, `frozen_for: "B1.3"`, `base_sha`, `bands` = the values READ at run time from the base and
written literally: generation threshold (`EvidenceScoreConstants.ABSTAIN_THRESHOLD`), label thresholds per domain
(from `_abstain_policy.build_abstain_policy` / `get_abstain_threshold` for default/tax/visa/kbli/pricing),
`CONFIDENCE_LOW/HIGH`, and the source-quality bands of `reasoning_utils.calculate_evidence_score` (0.7/0.5/0.3/0.15 —
verify on disk and write what the code says). `stratum_precedence` (below). `vocabulary` = `score_provenance.SCORE_KINDS`.

## Case schema (every field mandatory unless marked optional)

`case_id` (opaque: `bs-` + 8 lowercase hex, random, carries no meaning) · `query` · `query_lang` (`EN`|`ID`) ·
`context` (list of chunk strings — the ACTUAL text the scorer receives) · `context_lang` (`EN`|`ID`) ·
`provenance_fixture` = `{inventory_row: int, sources: [{score, score_kind, score_raw}], note}` ·
`requested_fact` (what the question needs, one sentence) · `supporting_span` (verbatim substring of one chunk; ONLY
when stratum = sufficient) or `missing_fact_explanation` (ONLY otherwise) · `stratum` · `generic_overlap` (bool) ·
`company_prefix` (bool) · `fee_policy` (bool: the context mentions a government fee/PNBP) ·
`expected_generation_gate` and `expected_label_gate` (`pass` for sufficient, `abstain` for every other stratum) ·
`synthetic: true` · `origin` (`golden:test_evidence_cross_language.py:<line>` | `constructed`) ·
optional: `spec_pair` (topic), `pair_id` (opaque, shared by the two members of a counterfactual pair),
`activates_in` (`B2.1`), `recorded_golden_expectation` (the checked-in boolean it corrects), `xfail_ref`
(test name), `constructed_counterpart: true`, `label_review` (free text for the reviewers).

**Stratum precedence** (first rule that holds wins): 1 `sufficient` — a chunk states the requested fact ·
2 `relevant_insufficient` — the chunks are about the requested topic/entity but do not state the fact ·
3 `irrelevant` — off-topic and neither nuisance property holds · 4 `generic_overlap` — off-topic, shares at least
one generic (non-identifier) query word · 5 `company_prefix_chunk` — off-topic, carries a company identifier prefix
(PT/PMA/NIB/OSS) the query also names. The nuisance booleans are recorded independently of the stratum.

## Provenance (from B1.1's measured table; never invent a rank)

- Golden originals: the file's literals `RETRIEVAL [{"score": 0.72}]` / `POOR_RETRIEVAL [{"score": 0.18}]` with
  `score_kind: "unknown"`, `score_raw: null`, `inventory_row: 5`, note "legacy literal, no writer (0.18 is below the
  measured formatted floor)".
- Constructed on-topic cases (both members of every pair): rank 0 in BOTH prefetch lists → fusion 1.0 → formatted
  1.0: `{score: 1.0, score_kind: "hybrid_rrf_formatted", score_raw: 1.0}`, `inventory_row: 1`.
- Constructed off-topic negatives: rank 0 in the dense list only → fusion 0.5 → formatted 0.6667:
  `{score: 0.6667, score_kind: "hybrid_rrf_formatted", score_raw: 0.5}`, `inventory_row: 1`.

## Cases (≈58; the Dux's design — draft the TEXT, keep the structure)

**A. The golden set, preserved (12)** — `test_evidence_cross_language.py:179-192`, each with the context the checked-in
test ACTUALLY feeds it (answerable rows are crossed: ID question → `EN_CONTEXT`, EN question → `ID_CONTEXT`;
unanswerable rows → `UNRELATED_CONTEXT` with `POOR_RETRIEVAL`). Copy the texts verbatim from `:47-65`.

- `:180`,`:181`,`:184` price rows → `sufficient` (span: the price sentence).
- `:182`,`:185` NIB/OSS rows → proposed `sufficient` with `label_review` explaining why it is contestable (the chunk
  lists deed, ministry approval, NPWP and NIB via OSS as setup components, not as NIB requirements). The reviewers
  decide; a split verdict is escalated, never coin-flipped.
- `:183`,`:186`,`:187` (minimum capital ×2, duration) → `relevant_insufficient`, `recorded_golden_expectation: true`,
  `activates_in: "B2.1"`.
- `:188`–`:191` → `irrelevant` (check the nuisance flags honestly: "asdkjhasd"/"xyzabc123" share nothing).
  **A2. The two strict xfails (2)** — `test_a_question_naming_no_identifier_is_still_language_blind` ("What is the price
  of new company setup?" × `ID_CONTEXT` × `RETRIEVAL` → `sufficient`) and `test_one_generic_word_should_not_be_evidence`
  ("Berapa harga sewa motor di Canggu?" × `ID_CONTEXT` × `POOR_RETRIEVAL` → `generic_overlap`), each with `xfail_ref`.

**B. The four spec pairs (32)** — topics `all_in_price`, `nib_oss_requirements`, `minimum_paid_up_capital`,
`registration_duration`; for each topic: 2 queries (EN, ID) × 2 context languages (EN, ID) × 2 members (sufficient,
relevant_insufficient) sharing a `pair_id`. Queries: price EN "How much is a PT PMA company, all in?" / ID "Harga PT
PMA berapa all in?"; NIB EN "What are the NIB and OSS requirements?" / ID "Apa saja syarat NIB dan OSS?"; capital EN
"What is the minimum paid-up capital for a PT PMA?" / ID "Berapa modal disetor minimum PT PMA?"; duration EN "How long
does PT PMA registration take?" / ID **constructed** "Berapa lama proses pendirian PT PMA?" (`constructed_counterpart:
true`, `label_review` asking for the independent language check). Within a pair the two contexts are the SAME PT PMA
chunk in the same language and about the same length; the sufficient member states the fact, the insufficient member
replaces that sentence with one that names the topic without the fact ("the minimum paid-up capital depends on the
approved investment plan and is not stated in this summary"). Facts to state, and only these: price "IDR 20,000,000
all inclusive" (one price, no government-fee split); NIB/OSS "the NIB is issued through OSS once the notarial deed,
the Ministry of Law approval and the company NPWP are in place, together with the KBLI codes and the business address";
capital "minimum paid-up capital of IDR 2.5 billion (BKPM Regulation 5/2025)"; duration "about 3 to 4 weeks from the
signed deed to the NIB" (synthetic example; note it in `requested_fact`). Indonesian texts natural, not word-for-word.
Nuisance on sufficient cases, at least once each across B: one `generic_overlap: true`, one `company_prefix: true`,
one `fee_policy: true` (e.g. "IDR 20,000,000 all inclusive, government fees included" — still one price).

**C. Off-topic negatives (12)** — per (query_lang × context_lang) cell one each of `irrelevant`, `generic_overlap`,
`company_prefix_chunk`, off-topic provenance. generic_overlap: a non-company question sharing one generic word with a
company chunk (the xfail's shape, new wording). company_prefix_chunk: a PT PMA fact question against a chunk that
carries "PT PMA"/"NIB" as a prefix but is about something else (e.g. a scooter-rental business listing). fee_policy
negatives may reuse the SHAPE of `tests/unit/services/test_curated_qa_government_fee_gate.py:26-112` (read-only, no copy
of client text — those fixtures are synthetic too; say so in `origin`).

Balance to verify: per cell ≥3 `sufficient` and ≥1 of each of the four negative strata. No PII, no real person or
client, every case `synthetic: true`.

## Harness (`harness.py`)

- `load(path) -> dict`; `validate(manifest) -> list[str]` (schema, precedence consistency: span iff sufficient,
  expected gates consistent with stratum, `score_kind` in vocabulary, unique opaque ids, each `pair_id` has exactly one
  sufficient + one relevant_insufficient with IDENTICAL query, query_lang, context_lang and provenance).
- `decide(case) -> dict`: `score = calculate_evidence_score(sources, context, query)`, `policy =
build_abstain_policy(query)`, `generation = "abstain" if policy.generation_abstains(score) else "pass"`, same for
  label. It reads ONLY query, context, sources — never a label field.
- `report(manifest) -> dict`: per set, per cell (`EN>EN`, `EN>ID`, `ID>EN`, `ID>ID`), per gate
  (`generation`, `label`): `false_abstention: {count, denominator}` (denominator = cases expected `pass`) and
  `false_acceptance: {count, denominator}` (expected `abstain`); the same broken down by stratum; a `fee_policy` column;
  a `spec_pairs` view (per pair: both decisions and `distinguished = sufficient passes AND insufficient abstains`).
- `main()`: `python -m backend.tests.benchmarks.evidence_sufficiency.harness [--manifest P] [--json]` prints the report.

## Test module (structural only — nothing new about the scorer)

`validate()` returns no error on the mandatory manifest; balance per cell; every cell × gate × metric denominator > 0
on the mandatory set; every topic in `spec_pair` covers all four cells; the three golden corrections carry
`activates_in: "B2.1"`; the two `xfail_ref` names exist in `test_evidence_cross_language.py` (AST);
**labels never select inputs**: flip every `stratum`/`expected_*`/span field in a deep copy → every `decide()` output
identical; `MANDATORY_MANIFEST_SHA256` pinned (the file's bytes), so an edit after the freeze goes red; the supplement
file exists and is empty. Run from `apps/backend-rag`: `PYTHONPATH=. SKIP_SENTRY_INIT=1 .venv/bin/python -m pytest
backend/tests/unit/services/rag/test_evidence_sufficiency_benchmark.py`, then the CLI once, JSON to stdout.
