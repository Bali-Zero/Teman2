---
date: 2026-08-26
domain: compliance
adversarial_review: kimi-k3
sources:
  - infra/launchagents/wrappers/regulatory-watcher-run.sh (== ~/scripts/regulatory-watcher-run.sh, sha256-identical, verified this session)
  - infra/eventbus/regulatory_ingest_runner.py
  - apps/backend-rag/backend/services/ingestion/legal_ingestion_service.py
  - apps/backend-rag/backend/core/legal/metadata_extractor.py
  - scripts/ci/ingest_target_lint.py
  - kb/inventory/legal_unified_2026.yaml (measured 2026-08-25 against production Qdrant)
  - research/regulatory/*.json (57 files, origin/main, read via `git show`)
  - live LegalMetadataExtractor / build_content_bound_legal_doc_id, run in-process on 12 real
    watcher-delta samples this session — read-only, zero writes to any store
---

# WIZ-1 — which route reconnects the regulatory watcher to the KB, and should either be armed now

Mandate: measure, do not build. Read-only on the world: nothing ingested, nothing written to
Qdrant, nothing deleted, no LaunchAgent touched. Worktree: `backend-rag-wiz1-route-0826`.

## The finding, up front

**Do not arm either route today.** Cost is not the blocker — it is a rounding error either way.
The blocker is identity, and it is a *different* shape of the identity problem than WIZ-2's own
framing suggested. It is not "dal nome del file" — that specific failure mode has already been
partly hardened (a fail-closed collision guard + a content-hash fallback landed 2026-08-25, the
day before this measurement). What remains, measured directly against the live extractor on 12
real watcher deltas: 7 of the 12 rows (58%) — equivalently 7 of the 11 distinct derived
identities (64%) — of the watcher's own short findings would land in the KB
**orphaned from citation lookup** — embedded and vector-searchable, but invisible to any
document_id/citation-exact query, KG entity-linking, or future de-dup pass. That is a quieter
failure than WIZ-2's "confidently wrong" case, but it is still not something to ship blind.

Recommended sequencing: **Route B's mechanics (below) are the right eventual shape — cheap to
build, reuses a pattern already live in the wrapper — but it should not be wired until the
ingest-time identity check WIZ-2 calls for exists for short-text sources specifically.** Today,
a delta with an unresolved identity would silently fall into a hash-suffixed bucket rather than
being flagged for re-citation. That is safe (no collision) but not correct (not retrievable by
citation), and it degrades quietly with no signal that anything needs attention.

---

## 1. What exists already — measured, not assumed

### 1.1 The watcher has never had an ingest path, confirmed independently

`infra/launchagents/wrappers/regulatory-watcher-run.sh` and the live `~/scripts/regulatory-watcher-run.sh`
are **byte-identical** (sha256 `af6715b6…`, verified this session) — this is not a HOME-fork drift
case, the tracked file IS the live one. `grep -inE "qdrant|upsert|ingest|embed"` against it: **zero
matches**. The script's actual output contract is a JSON delta file, a Telegram alert, an
`intel_lake_outbox` enqueue (a *different* pipeline, not Qdrant), and — since some point in its
history — a step that **commits the delta into the tracked repo tree itself** via an ephemeral
worktree + auto-merged PR (`promote_delta_via_pr()`, script lines 289–383). That last piece is why
delta files exist on `origin/main` at all: this is not a manual backlog, it is a working, if
narrow, promotion pipeline — it just stops at "the delta is a tracked file," never at "the delta is
a KB entry."

### 1.2 The backlog, measured in full (57 files, `git show origin/main:<path>` per file, zero parse errors)

- **57 delta files** tracked on `origin/main`, dated 2026-05-16 → 2026-08-25 (a 101-day span; only
  57 of those days produced a promoted file — the gap is not investigated here, but it means "57
  files" is not "57 incident-free days").
- **48 delta objects** total (`len(deltas[])` summed across all 57 files); **42 unique citations**
  — 6 are re-mentions of a regulation already seen on an earlier day (e.g. `PP 20/2026` appears
  across several deltas, each anchored to a different `Pasal`).
- `new_today_count` field sums to **45** against 48 actual `deltas[]` entries — a small,
  unexplained 3-count discrepancy between the two counters. Minor, but a naive consumer trusting
  `new_today_count` as "how many to ingest" would be off by a few.
- **12 of 57 files (21%) are `partial: true`** — the watcher's own admission that no tier completed
  a full scan that day. A consumer must honor this flag; a naive "read every file, ingest every
  delta" pass would treat a partial/degraded day's (possibly empty) findings as a clean "nothing
  new."
- **Schema drift is real but additive.** 23 distinct top-level key-shapes across 57 files (fields
  like `nb_query_notes`, `note`, `dedup_notes`, `web_sources_checked`, `confidence_note`,
  `sources_checked_no_delta` appear/disappear over time) and 12 distinct per-delta-object key
  shapes. None of this ever *drops* the 7 core fields a consumer would key on —
  `citation, title_id, title_en, service_line, source, summary, verbatim_excerpt` are present in
  every one of the 48 delta objects, in every shape observed. A consumer built against those 7
  fields is stable across the full history; one that also reads `new_today_count` or assumes a
  fixed top-level key set is not.
- **Text volume**: `verbatim_excerpt` sums to 11,298 chars, `summary` to 19,324 chars, and the full
  candidate "document text" per delta (citation + title_id + title_en + summary + verbatim_excerpt)
  sums to **43,440 chars** across all 48 deltas (~905 chars/delta average — a short digest, not a
  full instrument).

### 1.3 Which collection is actually live — this needed independent verification, and the naming is a trap

`ALLOWED_CANONICAL_COLLECTIONS = {LEGAL_CANONICAL_COLLECTION, "tax_genius"}` and
`LEGAL_CANONICAL_COLLECTION = "legal_unified"` (`legal_ingestion_service.py:60,68`). The obvious
misreading — given this work item's own name — is to assume `legal_unified_2026` is the live one.
It is not. `kb/inventory/legal_unified_2026.yaml` (measured 2026-08-25 by scrolling **both**
collections in full against production Qdrant, part of this same campaign) states plainly:
`legal_unified` (physical name `legal_unified_hybrid_hybrid`) is the collection **production
reads** — 84,283 points, 388 documents. `legal_unified_2026` is a **frozen, unrelated, 15,410-point
artifact from 2026-05-16** that this same work item's decision record retires as a target
(`decision.choice: retire_as_target`). `regulatory_ingest_runner.py:425` already targets
`"legal_unified"` literally — the correct one. `scripts/ci/ingest_target_lint.py`'s own docstring
(lines 6, 25-26) documents that this runner *did* once resolve to the wrong name via a string
concatenation (`"legal_unified" + "_2026"`) that a now-superseded regex scanner missed; an
AST-based lint replaced it and the runner is a `DECLARED_ENTRYPOINT` at the correct name today.
This is resolved, not open — noted here because getting it backwards would have wrecked the whole
analysis.

---

## 2. Route A — the watcher writes, an ingest runner consumes

`infra/eventbus/regulatory_ingest_runner.py` already exists and already targets the right
collection. It is an 8-step pipeline (verify JDIH URL → download PDF → Drive upload → Sheets
GAP_ANALYSIS → NotebookLM push → Qdrant embed via `LegalIngestionService` → KG extraction → finalize
report), invoked today by CLI args (`--reg`, `--domain`, `--jdih-url`, `--title`) supplied by a
human or another LLM session. Its own docstring already names this exact use case as a future
possibility: "From a future auto-watcher on bz:regulatory.delta.detected events" — that auto-watcher
does not exist.

**What connecting it would actually require:**

- **A citation → authoritative JDIH URL resolver, which does not exist anywhere in this codebase
  today.** `step1_verify()` needs a real, fetchable JDIH/government URL and does a `curl` HEAD-style
  check for HTTP 200 before anything else runs. The watcher's own `source` field is frequently a
  **secondary** source (DDTCNews, Hukumonline, IKPI — the sample delta read in full during this
  measurement cites `"DDTCNews | https://news.ddtc.co.id/"`, not a JDIH/peraturan.go.id URL). Of the
  12 citations sampled for the identity test below, several are Pasal-level (`"PP 20/2026, Pasal 56
  ayat (3) huruf a"`) or multi-citation (`"PP 20/2026; PP 55/2022; PP 23/2018"`) — neither maps
  cleanly onto "one regulation, one JDIH URL" without a resolution step that has to be built, not
  glued.
- **The bundled side effects.** `run()` unconditionally does Drive upload (step 3) and Sheets
  GAP_ANALYSIS update (step 4) and a NotebookLM push (step 5) before it ever reaches the Qdrant
  step. Running the 42-item backlog through this exactly as it stands means 42 Drive uploads, 42
  spreadsheet rows, and 42 NotebookLM source-adds — none of which the KB-ingestion goal needs. The
  orchestrator would need a mode that skips 3–5, which is not built today.
  Note: 1 confirmed, structural example, not enumerated exhaustively.
- **A recurring KG-extraction cost distinct from embedding.** `step7_kg_extract()` re-runs
  `kg_incremental_extraction.py --collection legal_unified --limit 200` (15-minute timeout) after
  *every* successful ingest. Across a 42-item backlog that is up to 42 KG passes over the same
  collection — a real wall-clock/compute cost the token-cost estimate below does not capture.

## 3. Route B — the watcher ingests directly

No such code exists, but the shape is small: the wrapper already has a working, proven pattern for
"take today's delta JSON and do a per-delta best-effort side-effect without blocking the main
run" — the `intel_lake_outbox` enqueue block (script lines 587-622) and the `modus_enqueue.py`
call at the very end. A Route-B implementation is one more block in that style: for each delta,
build a short synthetic document (title_id + citation + summary + verbatim_excerpt) and call
`LegalIngestionService.ingest_legal_document(collection_name="legal_unified", category=<mapped
from service_line>)`.

**What this would require:**

- A new call site added to `infra/launchagents/wrappers/regulatory-watcher-run.sh` **and its
  byte-identical HOME twin in the same gesture** (family #1 — this pair is already declared and
  lint-verified identical; a Route-B change that updates only one copy immediately creates the
  exact drift class the repo has a lint for).
- Registration of the new `LegalIngestionService(collection_name=...)` call site in
  `scripts/ci/ingest_target_lint.py`'s `DECLARED_ENTRYPOINTS`/AST-resolvable-literal requirement —
  this is a real gate, not a formality: the lint exists specifically because a prior version of
  this exact class of code (the regulatory ingest runner) once resolved to the wrong collection via
  an unresolvable string expression.
- A decision on collision semantics that today's code does not make for you (see §4).

## 4. Embedding cost — not the deciding factor, at any plausible multiplier

Model is frozen: `text-embedding-3-small`, 1536 dims — not proposed to change. Current published
price is **$0.02 per 1M input tokens** (standard API; $0.01/1M on the batch API), verified via web
search this session, sources below.

- **Route B backlog** (48 short deltas, the 43,440-char combined blob measured in §1.2): at a rough
  ~4 chars/token estimate for mixed Indonesian/English text, that is **~10,860 tokens ≈ $0.0002** —
  two-hundredths of a cent for the entire measured backlog to date.
- **Route A backlog** (42 unique regulations' *full* official text, not measured directly — no PDF
  was downloaded for this read-only mandate): even a generous estimate of 20,000–100,000 tokens per
  full Indonesian regulation puts the backlog at roughly 0.8M–4.2M tokens, i.e. **$0.017–$0.084** —
  still under ten cents.

Whichever route, or whatever backlog depth, the embedding bill is not a number anyone needs to
plan around. It is not why this should wait.

## 5. Identity risk — measured directly, not inferred

This is the part worth the most weight, because it is the part the mandate specifically asked to
have tested rather than assumed.

### 5.1 The mechanism, as it exists today (code dated 2026-08-25 — one day before this measurement)

`ingest_legal_document()` computes:

```
document_id = declared_storage_id or build_content_bound_legal_doc_id(metadata, source_sha256)
```

Neither route as sketched above passes `declared_storage_id` explicitly (the existing
`regulatory_ingest_runner.py` does not; a straightforward Route-B build would not either unless
deliberately designed to). So identity falls to `build_content_bound_legal_doc_id`, which needs
`metadata = LegalMetadataExtractor().extract(cleaned_text)` — a **content**-derived
`(type_abbrev, number, year)` triple, preferring one co-located match in a "title block" region and
falling back to three independent whole-document regex searches per field when that fails
(`metadata_extractor.py:76-160`). **Two antidotes landed the same day this file was authored,
change the risk profile from WIZ-2's worst case:**

1. Any field left `UNKNOWN`/`DOC`/`0`/`NONE` forces a 16-hex-char content-hash suffix onto the id
   (`legal_ingestion_service.py:215-228`) — this makes a failed extraction land under a unique,
   non-colliding id instead of a plausible-but-wrong one.
2. `_assert_identity_unclaimed()` (lines 298-374) is a fail-closed guard: a NEW source cannot
   silently overwrite an EXISTING different source holding the same `document_id` — it raises
   `LegalIngestIntegrityError` instead. (It was added after measuring the exact collision WIZ-2's
   class of defect produces: `Permen_1_2026` held 544 points shared between PMK 1/2026 and Permen
   Imipas 1/2026 — every ministry numbers its own regulations from 1 each year.)

### 5.2 What that mechanism actually does to the watcher's own text — measured, 12 real samples

To test "where would identity come from for this route" empirically rather than by inference, this
session ran the **live** `LegalMetadataExtractor` and `build_content_bound_legal_doc_id` in-process
(read-only — no network call, no Qdrant connection, no write to any store) against 12 randomly
sampled real delta objects pulled from the 48 measured in §1.2, building the document text the
obvious way a Route-B implementation would (`title_id + citation + summary + verbatim_excerpt`):

| citation (as the watcher wrote it) | extracted type/number/year | derived document_id |
|---|---|---|
| `SE-9/PJ/2026` | SE/UNKNOWN/UNKNOWN | `SE_UNKNOWN_UNKNOWN_83b4…` |
| `KEP-71/PJ/2026 (Keputusan Dirjen Pajak…)` | UNKNOWN/UNKNOWN/UNKNOWN | `UNKNOWN_UNKNOWN_UNKNOWN_e2da…` |
| `UU 2/2026` | UU/2/2026 | **`UU_2_2026`** (clean) |
| `KBLI 2025 (implementasi AHU Online…)` | UNKNOWN/UNKNOWN/UNKNOWN | `UNKNOWN_UNKNOWN_UNKNOWN_fcd2…` |
| `PP 20/2026, ketentuan peralihan (…SPT 2025…)` | UNKNOWN/UNKNOWN/**2025** | `UNKNOWN_UNKNOWN_2025_0231…` |
| `PP 20/2026 (DJP klarifikasi…)` | UNKNOWN/UNKNOWN/UNKNOWN | `UNKNOWN_UNKNOWN_UNKNOWN_a4f9…` |
| `PP 20/2026; PP 55/2022; PP 23/2018` | UNKNOWN/UNKNOWN/UNKNOWN | `UNKNOWN_UNKNOWN_UNKNOWN_9413…` |
| `PP 20/2026, Pasal 57 ayat (2) huruf e (Peraturan Pemerintah Nomor 20 Tahun 2026)` | PP/20/2026 | **`PP_20_2026`** (clean) |
| `KMK 29/MK/EF.2/2026` | **Kepmen**/29/UNKNOWN | `Kepmen_29_UNKNOWN_ab13…` |
| `PP 20/2026, Pasal 56 ayat (3) huruf a (Peraturan Pemerintah Nomor 20 Tahun 2026)` | PP/20/2026 | **`PP_20_2026`** (clean — correctly collapses onto the same id as the row above) |
| `PP 30/2026` | PP/30/2026 | **`PP_30_2026`** (clean) |
| `UU 4/2026` | UU/4/2026 | **`UU_4_2026`** (clean) |

**Reading this straight:** 4 distinct regulations (5 of 12 rows, 2 of which correctly collapse onto
one id) land with a clean, citation-matching identity. The other 7 rows fall into the
hash-suffixed safety net — **safe from collision, but permanently unreachable by document_id or
citation lookup**, findable only via vector similarity. None of the 12 reproduced WIZ-2's worst
case (a clean-looking id that names the *wrong* instrument) — the 2026-08-25 hardening appears to
be doing its job on this sample. But two things in this small sample are still worth flagging
explicitly rather than washing out in an average:

- **`PP 20/2026, ketentuan peralihan…` extracted year `2025`**, not `2026` — pulled from an
  unrelated "SPT 2025" reference deep in the body text, not from the regulation's own citation. It
  landed safely (both type and number were UNKNOWN, so the hash suffix still applied) — but this is
  exactly the *mechanism* that produced WIZ-2's contradictory identities on full PDFs; it simply
  did not get unlucky enough here to slip past the safety net.
- **`KMK 29/MK/EF.2/2026` extracted type `Kepmen`**, not `KMK` — a real data-quality error that also
  happened to land in the safe bucket only because the year was separately lost. Had the extractor
  also (wrongly) found a year, this row would have produced a clean-looking-but-wrong id with
  nothing to catch it — the 2026-08-25 guard only fires on an EXACT id collision with a different
  existing source, not on "this triple is internally implausible."

### 5.3 What this means for the decision

The identity mechanism as it stands is **not** the unguarded "trust the filename" pattern WIZ-2's
title implies — that specific hole has a fresh, real patch. What it still does not have, and what
WIZ-2's own stated cure (a title-block extractor with guilt-AND-innocence tests, "plus an
ingest-time check that refuses a document_id its own title block contradicts") would add, is any
check that an extracted triple is *plausible* rather than merely non-colliding. On short,
watcher-shaped text specifically, that gap manifests as a large orphaned fraction (7 of 12
rows, 58%, in this sample) rather than as silent corruption — which is a materially different, and
more tolerable, failure mode than what was measured on full-PDF ingests in the legal_unified_2026
experiment (11 of 18, ~61%, carrying a *confidently wrong* identity). But "more tolerable" is not
"acceptable to ship": well over half of a compliance-relevant regulatory KB effectively invisible to
exact lookup, silently, with no alarm, is still a defect a paying client's tax or visa question
could walk straight into.

## 6. Recommendation

1. **Do not arm Route A or Route B today.** Neither is cost-blocked; both are identity-blocked, in
   different ways and to different degrees.
2. **Route B is the right eventual shape** — small build, reuses the wrapper's existing
   best-effort-enqueue pattern, backlog cost is a fraction of a cent. Route A requires building a
   citation→JDIH-URL resolver that does not exist, accepting or refactoring around three bundled
   side effects (Drive/Sheets/NLM) the KB goal does not need, and pays a real per-item KG-extraction
   compute cost — meaningfully more engineering for the same destination collection.
3. **Sequence Route B behind a scoped piece of WIZ-2**, specifically: before any delta is ever
   ingested, add an explicit check that treats "extracted identity fell to the hash-suffix fallback"
   (or "type_abbrev/number/year individually implausible" — e.g. an unrecognized `type_abbrev`) as a
   signal to **flag for re-citation, not silently ingest**. This is a narrower ask than WIZ-2's full
   title-block guilt/innocence extractor rebuild — it can reuse the fallback signal the code already
   computes (`build_content_bound_legal_doc_id` already knows when it used the hash suffix; that
   boolean currently gets thrown away) — but it is a real, separate piece of work, not a rename.
4. Whichever route eventually ships, the proof-of-armed already stated in the WIZ-1 ledger entry is
   the right bar: a regulation present in a `research/regulatory/<date>-delta.json` retrievable from
   `legal_unified` by a probe question that fails before the change and passes after — never a delta
   file's existence or a runner's exit code.

Sources for the pricing figure in §4:
[CloudZero — OpenAI API pricing in 2026](https://www.cloudzero.com/blog/openai-pricing/),
[EmbeddingCost.com — OpenAI Embedding Pricing 2026](https://embeddingcost.com/openai),
[TokenMix — OpenAI Embedding Pricing 2026](https://tokenmix.ai/blog/openai-embedding-pricing).

## Adversarial review

Refuted by **Kimi K3** (cross-family seat, not this document's author), 2026-08-26, on a fresh
context with the repository in front of it, instructed to verify every citation with a command
rather than by reading and to default to skepticism.

**Verdict: SURVIVES_WITH_LIMITS.** One SUBSTANTIVE finding and four MINOR ones. Every number below
was RE-MEASURED independently before being accepted — a refuter hallucinates too — and the
independent measurement agreed with the seat on all five.

| # | severity | finding | disposition |
|---|---|---|---|
| C1 | **SUBSTANTIVE** | The headline statistic was wrong, and the document's own table refutes it. §5.2 lists **12** rows of which **5** are clean, which leaves **7** — but the text said "the other **8** rows" (`5 + 8 = 13 != 12`) and generalised it to "roughly **two-thirds**", stated three separate times. The true fraction is **7/12 = 58%** by row, or **7/11 = 64%** counting distinct derived identities (two rows correctly collapse onto one `PP_20_2026`). Neither reading is two-thirds, and the 64% one — the closest — is a denominator the document never stated. | **Corrected in all four places**, and, more importantly, **outside this document too**: the false fraction had already been copied into PRODUCTION CODE. `legal_ingestion_service.py:223` and a test docstring in `test_legal_ingestion_service.py` both said "roughly two-thirds" and both cited this document's §5.2 as their source. Both now carry the measured number and a note naming the correction. A wrong statistic in a code comment is worse than in a research file: nobody re-reads it, and it outlives the document. |
| C2 | MINOR | "57 delta files tracked on `origin/main`" — there are now **58**; `2026-08-26-delta.json` landed after the measurement. | **Recorded, not rewritten.** 57 is what was true when measured. Re-measured over all 58 files, every substantive §1.2 number still reproduces exactly: 48 delta objects, 42 unique citations, 45 `new_today`, 12 `partial: true`. The 58th file contributes zero deltas, which is why nothing moved. |
| C3 | MINOR | "23 distinct top-level key-shapes" is not reproducible by either obvious method. | **Corrected to a measured range.** Independently recomputed over the tracked files: **21** distinct shapes treating a shape as the sorted key set, **24** treating it as the ordered key tuple. Neither is 23, for either the 57- or 58-file population, so the document's counting method was unstated and is now unrecoverable. The qualitative claim it supports — drift is additive, the 7 core fields are always present, `core_missing = 0` — verified and unaffected. |
| C4 | MINOR | "43,440 chars across all 48 deltas" — the true sum is **43,248**. | **Corrected.** The difference is exactly **192 = 48 x 4**, i.e. four one-character separators per delta between the five concatenated fields — an artefact of joining rather than summing. Average is 901 chars/delta, not 905. The embedding-cost conclusion is unaffected at any plausible multiplier, which is why this is MINOR and not SUBSTANTIVE. |
| C5 | MINOR | Line citations into `legal_ingestion_service.py` have drifted: the hash-suffix mechanism is cited at `215-228` but `source_sha256[:16]` is at **288**; `_assert_identity_unclaimed` is cited at `298-374` but its `def` is at **360**. | **Corrected.** Both mechanisms exist exactly as described — only the coordinates moved. The cause is self-inflicted and worth naming: the WIZ-1 comment block that now occupies `215-228` was inserted *because of* this document, and it cites this document, so the act of recording the finding is what invalidated the finding's own line numbers. |

**Not findings, recorded so they are not mistaken for verified.** The two extraction quirks the
document flags — the year `2025` extracted from an `SPT 2025` reference, and `KMK -> Kepmen` — are
the author's readings of a table produced by its own in-process run; re-deriving them would mean
re-running the live extractor, which the seat did not do. The document hedges both appropriately.
Everything else the repository could answer was checked and reconciled: the sha256-identical
wrapper pair, the zero `qdrant|upsert|ingest|embed` matches in the watcher (rc=1, empty), the
`promote_delta_via_pr` line range, the runner's `collection_name="legal_unified"`, the
`ingest_target_lint` declared entrypoints, `legal_unified_2026.yaml`'s 15,410 points / 18 documents
against `legal_unified`'s 84,283 / 388, the "11 of 18, ~61%" cross-reference, both route token
estimates, the 101-day span, and `48 - 42 = 6` re-mentions.

**The recommendation is unchanged by all of this** — arm neither route; identity is the blocker.
It holds under the corrected 58% just as it did under the wrong two-thirds, which is the one
reassuring thing about a headline number being wrong: here it was decorative, not load-bearing.
