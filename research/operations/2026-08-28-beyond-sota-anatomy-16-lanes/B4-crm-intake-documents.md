---
date: 2026-08-28
domain: operations
part: B4 crm-intake-documents
scope: document intake (WA/Drive/Dropbox → local OCR → classify → extract → route → attach), the review_pending/quarantine queue, the auto-attach gates and CRM writer, CRM-Guardian's Drive lane, CRM core services/routers, cache namespaces — measured on origin/main @ 11a3c89a2e, benchmarked against IDP + professional-services CRM state of the art
sources:
  - https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept/accuracy-confidence
  - https://docs.aws.amazon.com/textract/latest/dg/how-it-works-identity.html
  - https://knowledge-base.rossum.ai/docs/using-ai-confidence-thresholds-for-automation-in-rossum
  - https://help.hyperscience.ai/v41/docs/transcription-accuracy-and-automation
  - https://docs.cloud.google.com/document-ai/docs/hitl/quickstart
  - https://moj-analytical-services.github.io/splink/
  - https://ollama.com/blog/structured-outputs
  - https://ollama.com/library/qwen3-vl
  - https://github.com/icereed/paperless-gpt
  - https://github.com/docling-project/docling
  - https://github.com/opendatalab/OmniDocBench
  - https://python.useinstructor.com/
  - https://github.com/argilla-io/argilla
  - https://arxiv.org/abs/2107.07511
  - https://arxiv.org/abs/2606.24420
status: DONE 2026-08-28T12:40:00+08:00
adversarial_review: kimi-k3
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


# B4 — CRM / Intake / Documents — Beyond-SOTA lane

Method: static read-only (grep/wc/sed on the worktree, 15 fetched external sources, no test runs, no DB
queries). Every `file:line` below was read in this session; every population number is quoted from the
dated internal report that measured it and is marked with that date — none was re-measured here.
No client PII appears in this document (Law 2).

---

## 1. Anatomy (as measured)

### 1.1 Size

| Organ | Files | Lines | Largest members |
|---|---|---|---|
| `services/intake` | 24 | 13,182 | `extract.py` 2,243 · `routing.py` 1,613 · `writer.py` 1,454 · `auto_attach.py` 1,239 · `classify.py` 1,235 · `worker.py` 827 |
| `services/crm` | 47 | 16,196 | `client_core.py` 1,249 · `assignment.py` 836 · `drive_poll_service.py` 816 · `evidence_dossier.py` 664 · `enrichment.py` 529 |
| `services/crm_guardian` | 7 | 2,932 | `ocr.py` 797 · `consolidator.py` 601 · `schemas.py` 451 |
| `services/documents` | 3 | 711 | `ocr_dispatcher_service.py` 399 · `crm_drive_backfill_service.py` 312 |
| `services/multimodal` | 3 | 686 | `pdf_vision_service.py` 609 · `cloud_vision_gate.py` 77 |
| `services/{dossier_fanout,classification,pii,lead_capture,journey}` | 19 | 2,533 | — |
| 22 routers in scope | 22 | ~14,900 | `crm_practices.py` 2,597 · `crm_clients.py` 2,498 · `crm_enhanced.py` 1,565 · `intake_review.py` 1,368 |
| `apps/crm-cell` | 7 | 675 | thin cell wrapper (scar registry, HGT publisher, `cell.yaml`) |
| Tests | 182 files | — | intake 53 · crm 77 · documents 14 · crm_guardian 9 · pii 7 · journey 8 |
| Migrations touching the part | 20 of 175 | — | `212_intake_unified`, `214`, `217`, `218`, `219`, `224`, `225`, `227`, `232`, `240`, `246`; guardian `129/130/140/180/181/202` |
| Runtime organs | 9 launchd plists | — | `intake-worker`, `intake-blob-retention`, `intake-review-reader(+liveness)`, `intake-gate-count-pusher`, `intake-health-report`, `wa-mirror-intake-sweeper`, `drive-intake-drain`, `dropbox-intake` (`infra/launchagents/`) |

Two of the directories assigned to this lane are semantically elsewhere: `services/classification`
is the chat *intent* classifier (`intent_classifier.py:1-4`, pattern-based, no documents — B3
territory) and `services/dossier_fanout` distributes WR2 research dossiers to ten consumers
(`dossier_fanout/__init__.py:1-12` — B8 territory). Neither is benchmarked here.

### 1.2 The intake pipeline (data flow, as coded)

1. **Ingress** — three sweepers (WhatsApp mirror, Drive drain, Dropbox) call `enqueue.py`, which writes
   only `document_instances` + `intake_queue` ("ZERO CRM writes", `enqueue.py:3`). Dedup is structural:
   `document_instances` is an append-only registry keyed `UNIQUE(blob_hash, pipeline_version)` with
   `phash` (perceptual) and `normalized_text_hash` columns (`enqueue.py:9,120-136`).
2. **Worker** — `worker.py:1-50`: SKIP-LOCKED lease claim, heartbeat, retry/backoff, DLQ, v2 state machine
   `pending → ocr_done → extracted → validated → done`; `TransientStageError` (Ollama down) does not burn an
   attempt; a `dead` row is never re-claimable (W61 anti-storm); a review-claim reaper runs alongside.
3. **OCR + classify** (`classify.py`) — local only by construction: `_OCR_PRIMARY_DEFAULT = "qwen2.5vl:7b"`
   and `_OCR_FALLBACK = "qwen2.5vl:7b"` (`classify.py:89,93`), `OCR_PAGE_TIMEOUT_SECONDS = 120.0`
   (`:111`), OCR runs on **all pages** (`:1189`, `:1016`) while vision classification looks at the first
   `VISION_CLASSIFY_MAX_PAGES = 3` (`:840`) — which is exactly why the "directors on page 2-3 of an akta"
   rule holds: extraction sees every page, only the *type* decision is capped. A Gemini OCR path exists
   as env opt-in (`_GEMINI_OCR_MODEL`, `:97`) and is the subject of an open owner decision (§1.7).
   `preprocess.py:304-317` guards the documented qwen2.5vl SmartResize panic on sub-28px images.
4. **Extract** (`extract.py:1-14`) — schema-driven, local Ollama, the *Maybe pattern*: a field is either a
   value with `source_page` evidence or an explicit `null` with confidence 0.0. Confidence is **constant,
   not measured**: `_PRESENT_CONFIDENCE = 0.85`, `_MRZ_CONFIDENCE = 0.95`, `_LABEL_CONFIDENCE = 0.90`,
   with the comment "the extractor is deterministic (temperature 0) and does not emit calibrated
   probabilities" (`extract.py:72-80`). Passport MRZ is parsed deterministically with ICAO 9303 check
   digits (`extract.py:631-692`); NIB and NPWP (15 legacy / 16 NIK-based) are format-checked in
   `validate_rules.py:136-150`. The Ollama call uses JSON *mode* (`"format": "json"`, `extract.py:2012`),
   not a JSON-schema constraint.
5. **Route** (`routing.py:36-52`) — four verdicts: `AUTO_ATTACH` (exactly one candidate via a strong id),
   `LINK_CANDIDATE`, `AMBIGUOUS` (≥2 plausible, or a strong id owned by >1 client), `NO_MATCH`. Matching
   is exact strong-id lookup plus in-DB `pg_trgm` fuzzy name with `FUZZY_APPLY_THRESHOLD = 0.70`,
   `FUZZY_REVIEW_LOW = 0.40`, `AMBIGUITY_MARGIN = 0.15` (`:108-110`, `:727-739`), sender phone, and
   every folder segment of the source path (`:659-684`). GATE-11: a backfilled identifier born
   `verified:false` degrades a strong match to `LINK_CANDIDATE` (`:389,419`). The module explains why
   Splink was rejected for this problem: the keys are quasi-unique, an exact lookup resolves them, and a
   DuckDB engine would add weight for "zero marginal precision" — "if a future FASE needs many-field
   probabilistic linkage (e.g. dedup across noisy CRM rows), revisit splink then" (`routing.py:23-33`).
6. **Gates** (`auto_attach.py:1-40`) — three killswitches, all default OFF (`:130-170`): strong-id ⟂ phone
   double concordance, direct-phone, strong-id ⟂ document-subject-name. `AUTO_ATTACH_SUPPRESSED_PIPELINE_VERSIONS`
   (`routing.py:84`) lets batch programs disable auto-attach per pipeline tag.
7. **Writer** (`writer.py:1-45`) — the single commit path: `plan_commit` (read-only, in-TX revalidation of
   client/practice/soft-delete, P0#3) → `execute_commit` (dry-run unless `INTAKE_WRITER_ENABLED`) →
   `rollback_commit`; idempotency key is intake-instance based, never content based (P0#1); every
   decision lands in `intake_commit_audit`. A real write also records `intake_corrections` rows
   (`_record_commit_corrections`, `writer.py:661,680,952`) — the learning table exists and *is* wired.
8. **Delivery** — `crm_delivery.py` / `crm_push.py` push the attach Pro → Fly through the scoped
   `X-CRM-Write-Key` bridge; `crm_push.py` calls `upsert-by-phone` with `reject_ambiguous=True` and
   `restore_if_archived=False` (advisory of 2026-08-19, §1.7).
9. **Human surface** — `intake_review.py` (`/queue`, `/claim`, `/release`, `/recover`, `/approve`,
   `/reject`, lines 363-1222; RBAC axis is "own chat", `:14-27`) and the login gate probe
   `intake_gate.py` (counts only, fail-open on evaluator error).

### 1.3 CRM-Guardian — the second, older document lane

`services/crm_guardian/ocr.py:1-30` implements a cost-ordered cascade: pdfminer text layer →
pypdfium2 + tesseract `ind+eng` → `qwen2.5vl:7b` when tesseract confidence < 0.4, with a 120 s per-page
cap (`:56-60`). Its cache table lives on Fly Postgres next to `clients.ai_summary` (`:24-26`). The worker
`scripts/crm_guardian_gemini_cli_worker.py` then renders `<FILE_CONTENT_SNIPPETS>` — "passport MRZ, akta
capital section, NPWP number" (`:895-905`) — into a prompt passed as an `agy` argv value to Gemini
(`:109`, `:1100-1112`). The docstring itself flags, unresolved: the prompt is `ps`-visible to every
local user while running, and "is CRM/client document content by construction". This lane was born
from the 2026-05-17 identity-hallucination scar (Phase 1 sent filenames only; Phase 1.5 added content,
an OCR budget of 30 fresh files per client and ~19 clients/hour — `cicatrix-scars-archive.md:666-741`).

### 1.4 CRM core, caches, neighbours

`client_core.py:1-10` consolidates validators, audit trail and `EnhancedCRMService`; `assignment.py:353-358`
holds the only duplicate check (`check_duplicates`, on assignment). Cache invalidation on the two
namespaces this lane owns is called at 44 sites — e.g. `crm_practices.py:664-665`, `crm_clients.py:716`
— and also by neighbours (`portal.py:1256`, `accounting.py:166`), so the namespace contract is shared
with B5. `pii/violation_store.py:27-38` grades scanner hits (KTP/NPWP/passport high, phone/email medium,
PERSON low). `lead_capture/source.py:12-30` enumerates the funnel apps that emit leads; `journey/*`
builds client journeys from templates. `apps/crm-cell/README.md` declares the cell uses Gemini 3 Flash for
CRM automations and records a standing rejection: no DB-backed workflow registry ("C2 — REJECTED, NEVER").

### 1.5 Where the data lives

Intake state is **local to the Pro** (`nuzantara_dev`), never on Fly: the prod MCP sees zero of the
proposals (intake `SKILL.md:29-31`; producer/consumer split proven in
`research/operations/2026-06-09-intake-review-pro-reader-spec.md`). The review reader therefore runs on the
Pro. All OCR/vision is local; the only cloud chokepoints are gated by `cloud_vision_gate.cloud_vision_allowed()`
which reads `settings.ocr_allow_cloud_vision`, default False, failing closed on any error
(`cloud_vision_gate.py:28-40`), and alerts per degraded surface (`:43-77`). Callers: `pdf_vision_service.py:113-122`
(Ollama-first, `gemini-2.0-flash-lite` fallback), `crm_enhanced.py:100,158-163` (`_gemini_ocr`, gated),
`crm_clients_documents.py:280-285`, `ocr_dispatcher_service.py:300-306` (its content classifier is
`crm_enhanced._auto_classify_content`, `crm_enhanced.py:839`).

### 1.6 Constraints (SYMBIOSIS §LE LEGGI, as they bind this part)

Law 1 (CLI-only LLM); Law 2 (no PII transcribed in any output; `cloud_vision_gate` governs only
OCR/vision of documents, not chat text; the Art. 56 cascade is per transfer; consent is collected by
contract — Zero 2026-08-09 — but clause, proof, revocation and enforcement are not armed); Law 4
(degrade, never hard-fail); Law 6 (the organism lives on Zero's machines; offline is natural); Law 7
(no metric → no improvement). Scar families that bite here: #2 *exists ≠ armed* (the auto-attach flag
was computed for months before `auto_attach.py` consumed it), #5 sibling race (work lost mid-Phase-1.5),
#6 anti-hallucination (2026-05-17), #9 proxy-vs-state (the fifteen-round drive-autocreate gate,
`2026-07-19-drive-contact-autocreate-design.md`).

### 1.7 Prior decisions — cited, not re-opened

- **Human review loop retired** (Zero, 2026-07-12): 34,680 `review_pending` + 9,535 quarantine vs ~91
  ever routed; "NO, retire the human-review loop … no drain plan" (`PENDING-ARMS.md:450`).
- **Gemini cloud-OCR opt-in in `classify.py`**: an owner compliance call, open since 2026-07-07
  (`PENDING-ARMS.md:294`).
- **Stay on `qwen2.5vl:7b`; bake off Qwen3-VL-8B and GLM-OCR on 50 real docs**
  (`2026-06-27-local-ocr-model-bakeoff-indonesian-id-docs.md`); Surya/Marker are NO-GO on revenue-capped
  licences (`2026-06-27-39k-drive-ocr-backlog-sovereign-pipeline.md`). Tooling exists
  (`scripts/ocr_bakeoff.py`, `intake_ocr_quality_eval.py`, `intake_reocr_sample.py`); whether the bake-off
  was executed is not recorded in the files read — *(unverified)*.
- **Fine-tuning is not essential anywhere yet**; the ladder is constrained decoding, few-shot retrieval,
  off-the-shelf calibration (`2026-07-18-slm-finetuning-essentiality-audit.md`, both red-teams).
- **Panel width is second-order; the bottleneck is the CRM key-book** — the deterministic tier scored
  61/61, name-only single-model owned the only error (intake `SKILL.md:67-93`, measured 2026-07-18).
- **Re-OCR of the 25.4k zero-candidate mountain is a dead end** (0.04% recovery; 97.7% of blobs already
  unlinked by the 7-day TTL); Station 0 dedup/junk is the only volume lever
  (`2026-07-18-intake-station1-2-rescue-recall.md`).
- **Drive contact auto-create** shipped through 15 adversarial rounds; waves 1-3 created 198 + 94 + 1
  contacts with 0 auto-attach (intake `SKILL.md:155-244`).

---

## 2. Honest state vs. SOTA

Where this part is already at or beyond the commercial state of the art:

- **Identity-matching safety.** No vendor fetched (Azure, AWS, Rossum, Hyperscience) models the
  *sender ≠ subject* problem or forbids name-only attachment; Nuzantara does both by construction
  (double concordance, GATE-11 unverified-key demotion, AMBIGUOUS on shared keys, quarantine as a
  correct terminal). The deterministic tier's measured 100% precision (61/61) is the kind of number
  Hyperscience sells as an "accuracy target".
- **Sovereignty.** OCR of identity documents never leaves the machine, with a fail-closed gate and a
  per-surface alert — stronger than any cloud IDP's default posture.
- **Dedup-before-OCR and lease-correct queueing** (`document_instances`, SKIP-LOCKED worker, DLQ) match
  what paperless-ngx/pgqueuer offer, in Postgres, already in production.

Where it is behind:

- **Confidence is asserted, never measured.** Rossum calibrates scores to the probability of
  correctness and defaults its queue threshold to 0.975; Hyperscience derives thresholds from accuracy
  targets over ≥2,000-5,000 QA-verified fields; Azure returns word, field and document-type confidence.
  Nuzantara's extractor emits four constants (§1.2 step 4) and its routing thresholds (0.70/0.40/0.15)
  were lifted from the WhatsApp identity resolver, not fitted to intake data.
- **The learning table is wired but starved.** `intake_corrections` fills only on real commits; with the
  review loop retired and ~91 documents ever routed, there is no calibration set. Every automation
  gain to date came from a *structural* discovery made by hand (folder segments, npwp, backfill),
  none from data.
- **OCR engine.** `qwen2.5vl:7b` (7B, 10-language OCR) sits where 0.9B specialised parsers now score
  95-96 on OmniDocBench v1.6 and Qwen3-VL covers 32 OCR languages; the bake-off decided in June has no
  recorded outcome.
- **CRM-level dedup.** The only check runs at assignment; measured locally 622 phone-dup groups and 17
  passport-dup groups (2026-07-18), and one passport shared by 7 client rows. Splink was correctly
  rejected for *attach*, and its own note reserves it for exactly this.
- **One lane contradicts the sovereignty invariant.** CRM-Guardian ships OCR'd passport/NPWP/akta text
  to Gemini via `agy` and exposes the prompt in the process table — flagged in code, unresolved.
- **Observability.** The nine intake runtime organs have no rows in the organism registry or the
  automation catalog (F1 in `2026-07-19-product-corners-strategic-coherence.md`); a stale worker was
  caught only by a manual restart.

---

## 3. Deep research: the world's best

**Azure AI Document Intelligence** — confidence is a per-field probability ("0.95 … correct 19 out of 20
times"), with word-level and, since API 2024-11-30, table/row/cell confidence; the doc recommends
composing field confidence with the underlying OCR confidence, targeting ≥80% model accuracy and "close
to 100%" for sensitive records, and adding human review for critical automation. Accuracy scores are
estimated by cross-validation over the training set; low document-type confidence signals template
drift. [S1]

**AWS Textract AnalyzeID** — identity documents return `IdentityDocumentFields` with a *normalised* type
and a raw key, each with its own confidence, so heterogeneous IDs map to one schema; two-sided documents
are passed as separate images in one request. The A2I human-loop pages returned no content in this
session — *(A2I activation conditions unverified)*. [S2]

**Rossum** — the queue-level threshold defaults to 0.975 and "expresses a requirement for 97.5%
accuracy"; per-field thresholds override it; a document auto-exports only when *every* configured
field clears its threshold; thresholds are chosen by experiments on the customer's own data, and the
scores are admitted to be "a little pessimistic". [S3]

**Hyperscience** — the operator sets an *accuracy target* per document type and per field; the platform
derives the confidence threshold from the target and QA feedback ("you indicate how accurate you want
the transcription to be… Hyperscience adjusts all the other metrics"); targets only activate after a
minimum QA sample (5,000 fields structured, 2,000 semi-structured, 2,000 cells) inside a lookback
window; higher targets lower automation until the QA loop learns. [S4]

**Google Document AI** — the HITL quickstart URL now resolves to a deprecation notice ("Human in the Loop
(HITL) January 16, 2024"): Google retired its built-in review console; review is expected to be built by
the customer on top of per-entity confidence. [S5]

**ExtractConf (arXiv 2606.24420, June 2026)** — a multi-signal confidence engine for LLM field
extraction: cross-call disagreement between two asymmetric readings (field-guided vs holistic), LLM
uncertainty, OCR confidence, image quality and layout, fused by a classifier with "no domain-specific
rules or retraining". On DocILE (55 fields, 26% base failure) it reaches 0.928 AUROC, 70% risk
reduction over log-prob mean, and 99.1% accuracy at 80% coverage; on CORD zero-shot, 0.858 AUROC with an
89% calibration-error reduction after Lasso recalibration. [S15]

**Conformal / selective prediction (Angelopoulos & Bates)** — prediction sets "guaranteed to contain the
ground truth with a user-specified probability" from a held-out calibration set, distribution-free,
usable "with any pre-trained model", including models that abstain. This is the statistical basis for
turning "auto-attach precision ≥ 99.5%" into an enforceable guarantee rather than a hope. [S14]

**Splink** — Fellegi-Sunter probabilistic linkage with unsupervised EM training, blocking rules, term-
frequency adjustments and clustering; DuckDB/Postgres/Spark backends; "a million records on a laptop in
approximately one minute"; explicitly not for single bag-of-words columns; no guidance on choosing a
match-probability cutoff (that remains a human calibration step). [S6]

**Ollama structured outputs + Instructor** — Ollama constrains decoding to a JSON schema via the
`format` parameter on `/api/chat`, with a vision example (image + schema) and a "temperature 0"
recommendation; Instructor wraps this in Pydantic models with validators and an automatic re-ask loop
(`max_retries`) across 15+ providers including Ollama and llama-cpp. [S7][S12]

**Local OCR/VLM landscape** — OmniDocBench v1.6 (April 2026, 1,651 pages, 10 doc types): PaddleOCR-VL-1.6
(0.9B) 96.34, MinerU2.5-Pro (1.2B) 95.75, GLM-OCR (0.9B) 95.22, dots.ocr (3B) 90.77, DeepSeek-OCR-2 (3B)
90.25, Qwen3-VL-235B 89.78 — specialised sub-1B parsers beat general VLMs 200× their size on parsing.
Qwen3-VL ships on Ollama in 2b/4b/8b/30b/32b/235b with OCR in 32 languages and a 256K context (Ollama
≥ 0.12.7). Caveat carried from the June bake-off: none of these benchmarks contain Indonesian identity
documents; only a local golden set decides. [S11][S8]

**Docling / paperless-gpt** — Docling (MIT, arm64, air-gapped OK) parses layout, reading order, tables
and runs a 258M Granite-Docling VLM; paperless-gpt (MIT, Go) adds vision-LLM OCR and an explicit
suggestion-then-approve loop over paperless-ngx with a fail-tag for retries, and "doesn't expose
explicit confidence scores" — the OSS ceiling is *review everything*, not selective automation.
[S10][S9]

**Argilla** — self-hosted (Apache-2.0) review tool whose data model separates model *suggestions* from
human *responses* per question, with filters and semantic search; the fetched page does not document
suggestion-score display or annotator-overlap policy. [S13]

**Professional-services CRMs** — Clio Grow's help pages (found via search; the article fetch returned
403, so *not fetched*) describe intake forms feeding document templates via merge fields and bundled
e-signature; HubSpot's duplicate-management page returned 404. No fetched CRM source documents anything
like a strong-identifier ledger or a provenance-gated attach — the professional-services CRM market
competes on intake *forms*, not on document *truth*.

---

## 4. Gap table

| Capability | Nuzantara today (measured) | World best (fetched) | Gap |
|---|---|---|---|
| Field confidence | 4 constants (`extract.py:72-80`), no calibration | Rossum probability-calibrated, Azure per-word/field, ExtractConf 0.93 AUROC | **Large** |
| Automation threshold selection | Hand-set 0.70/0.40/0.15 + killswitches | Thresholds from accuracy target over ≥2k QA fields (Hyperscience), per-field (Rossum) | **Large** |
| Selective automation guarantee | Deterministic tier 100% (61/61, 2026-07-18) | Conformal coverage guarantee, distribution-free | Medium (strong base, no guarantee) |
| Feedback loop | `intake_corrections` wired on commit, starved (loop retired) | QA sampling in background, minimum sample sizes | **Large** |
| Constrained extraction | JSON mode (`extract.py:2012`) + Maybe pattern + validators | JSON-schema constrained decoding + validator re-ask (Ollama/Instructor) | Small-Medium |
| Deterministic parsers | MRZ 9303 check digits, NIB/NPWP format | AnalyzeID normalised keys + per-key confidence | Small (ahead on MRZ) |
| OCR engine | `qwen2.5vl:7b`, 120 s/page, all pages | 0.9B parsers at 95-96 OmniDocBench; Qwen3-VL 32-lang | Medium (bake-off decided, outcome unrecorded) |
| Identity-matching safety | Never name-only, sender≠subject, GATE-11, AMBIGUOUS-on-shared-key | Not modelled by any vendor fetched | **Ahead** |
| CRM dedup | `check_duplicates` at assignment only | Splink FS/EM clustering, 1M rows/min | Medium |
| PII sovereignty | Fail-closed vision gate, local intake | Cloud vendors: DPA-based | Ahead — except CRM-Guardian egress |
| Review tooling | Custom `/review` (claim/lease/approve/reject) | Argilla suggestions vs responses; paperless-gpt approve loop | Small (loop retired anyway) |
| Runtime observability | 9 organs unregistered (F1) | Accuracy harness dashboards | Medium |
| Blob retention | 7-day TTL; 97.7% of backlog blobs gone | Archive-forever (paperless) | Medium |
| Intake forms / e-sign | `lead_capture` sources; portal owned by B5 | Clio Grow forms→templates→e-sign | Out of lane (B5/F2) |

---

## 5. Recommendations — reach SOTA

**R1 — P0 — Bring CRM-Guardian's extraction home (close the one egress that contradicts Law 2).**
*What:* stop sending OCR snippets to Gemini; run the L1 identity/compliance extraction locally with a
JSON-schema-constrained call (qwen3.5:9b, or deepseek-r1:32b on the Mini for the akta reasoning),
keeping the pdfminer→tesseract→qwen2.5vl cascade untouched. If Zero keeps a cloud seat for
*non-PII* summarisation, pass the prompt through a file or stdin, never argv. *Why:* the worker's own
docstring records the exposure (`crm_guardian_gemini_cli_worker.py:1107-1112`); the SLM audit's E1 named
it the "genuine compliance finding" and prescribed exactly this (local constrained decoding,
deterministic parsers first). *How:* new `services/crm_guardian/local_extractor.py` reusing
`intake/extract.py`'s Maybe-pattern prompt + `validate_rules.py`; a `cloud_text_gate` twin of
`cloud_vision_gate` consulted at `call_gemini_cli`; guilt/innocence tests in `tests/unit/services/crm_guardian/`.
*Effort:* M. *Risk:* summary quality drop on long akta — mitigate with the 32B on the Mini. *Deps:* Zero's
call on the agy seat (§8). *Acceptance:* one full 706-client cycle with zero `agy` invocations carrying
`<FILE_CONTENT_SNIPPETS>` (grep of the worker log) and L1 field agreement ≥ 95% against 50 prior
Gemini summaries on the identity fields.

**R2 — P0 — Measured confidence instead of constants (the calibration harness).**
*What:* a nightly, local `scripts/intake_calibration_report.py` that joins `intake_corrections` +
`intake_commit_audit` + the ground-truth 135 set and emits, per `doc_type × field`, precision at each
confidence bucket, a reliability diagram, and — via split conformal on the held-out slice — the
threshold that guarantees a chosen error rate (e.g. ≤ 0.5% on strong ids, ≤ 5% on names). Replace
`_PRESENT_CONFIDENCE`/`FUZZY_APPLY_THRESHOLD` reads with values loaded from a versioned
`intake_calibration.json` (fallback to today's constants when the sample is below a Hyperscience-style
floor — propose 500 fields per doc_type, since 2,000 is unreachable soon). *Why:* every fetched leader
(Rossum, Hyperscience, Azure) automates on *measured* probability; the extractor comment admits it has
none. *How:* add ExtractConf-style signals cheaply — the second reading is free (`classify` vision text
vs `extract` output disagreement), MRZ check-digit pass, `validate_rules` outcome, OCR char-density from
`ocr_quality.py`. *Effort:* M. *Risk:* tiny samples → wide intervals; the harness must print the interval,
never a point. *Deps:* R3 for the sample source. *Acceptance:* the report exists for ≥ 3 doc types; the
auto-tier threshold it selects reproduces ≥ 99.5% precision on the 135 ground-truth set; a CI test fails
if code reads a threshold constant the harness also emits (single source).

**R3 — P1 — Feed the corrections table without resurrecting the retired queue.**
*What:* record a correction row for *every* human-confirmed attach on any surface that already exists —
`intake_review` approve/reject (writer real path already does it, `writer.py:952`), Kita document
uploads that are later re-typed, drive-autocreate wave verifications, and a 2%-random QA sample of
`auto_routed` commits shown to the receiving employee as a one-tap "correct / wrong" in their own chat
(RBAC axis already "own chat", `intake_review.py:14-27`). *Why:* Hyperscience's targets only activate
after a QA floor; Google removed its HITL console and expects the customer to own this loop; Zero
retired *mass* review, not *sampling*. *How:* extend `_record_commit_corrections` callers; a
`review_sample` flag on `document_routing_proposal`. *Effort:* S-M. *Risk:* scope creep back into the
retired loop — cap the sample at 2% and 5 items/day/employee. *Deps:* Zero's OK on the sampling (§8).
*Acceptance:* ≥ 50 corrections/week measured over 4 weeks; 0 rows with cleartext outside the local DB.

**R4 — P1 — Schema-constrained decoding with validator re-ask.**
*What:* switch `extract.py:2012` from `"format": "json"` to the Pydantic-derived JSON schema per
doc_type (Ollama `format=<schema>`), and wrap with an Instructor-style re-ask (max 2) whose validators
are `validate_rules.py`. *Why:* the SLM audit's first rung; Ollama documents it natively, including for
vision models. *How:* one schema module per doc_type in `services/intake/schemas/` shared with
`crm_guardian/schemas.py`. *Effort:* S. *Risk:* schema too strict hides partial reads — keep the Maybe
pattern (`null` allowed everywhere). *Acceptance:* JSON-parse failures → 0 on the 50-doc golden set;
field-exact-match not lower than today (`intake_ocr_quality_eval.py`).

**R5 — P1 — Run the decided bake-off, and a tiered router.**
*What:* execute `scripts/ocr_bakeoff.py` on the 50-doc set for `qwen2.5vl:7b` vs Qwen3-VL-8B vs
GLM-OCR vs PaddleOCR-VL-1.6 (all Apache/MIT; Surya/Marker stay NO-GO), then route: text-layer PDFs →
pdfminer (already in guardian, not in intake), printed scans → the fastest parser that passes,
identity docs → the winner of field-exact-match. *Why:* 0.9B parsers now lead OmniDocBench; the June
decision is unexecuted as far as the files show. *How:* `model_roles.py` role `ocr_vision` per
doc-class; keep `INTAKE_OLLAMA_MAX_INFLIGHT=1` and never co-load a 32B translator on the same host
(orphan-leak root cause, 2026-06-28). *Effort:* M. *Risk:* Ollama runner crashes on new model classes —
the SmartResize guard shows the pattern. *Acceptance:* field-exact-match ≥ incumbent AND p95 page
latency < 60 s on the Pro; zero DLQ growth over a 24 h soak.

**R6 — P2 — CRM dedup as a review-only Splink lane.**
*What:* a DuckDB Splink model on `clients` (phone core, normalised name, passport, email, DOB, folder id)
run on the Mini, writing *clusters* to a `crm_merge_candidates` table; never auto-merge. *Why:*
`routing.py:31-33` reserves Splink for exactly this; 622 phone-dup and 17 passport-dup groups were
measured (2026-07-18) and one passport with 7 rows blocks deterministic attach. *Effort:* M. *Risk:*
merge is irreversible in the CRM — keep it a proposal. *Acceptance:* 100% of known multi-row strong-id
groups appear as clusters; ≤ 5% false clusters on a 100-pair adjudicated sample.

**R7 — P2 — Register the nine intake organs and lengthen retention.** Add registry/catalog rows plus a
heartbeat that reads the worker's *output* (last `done` timestamp), not its PID (superscar #2); raise
`intake-blob-retention` TTL to 90 days on the Mini's disk with dedup by `blob_hash` and a disk budget
alarm (the orphan sweep freed 24.5 GB on 2026-06-28). *Acceptance:* a stopped worker alarms within 15
min; 100% of documents < 90 days old are re-processable.

---

## 6. Recommendations — beyond SOTA

**B1 — P0 — The Sovereign Accuracy Harness: precision packs, signed like visa rule packs.**
Hyperscience sells "accuracy targets" as a cloud service on 5,000-field QA floors. Nuzantara can do the
same thing at $0, offline, and *publish the proof*: R2's calibration output becomes a signed
`intake_precision_pack` (doc_type → field → threshold → measured precision interval → sample size →
code SHA), versioned in the repo like the visa rule packs, loaded by `routing.py`/`extract.py` at boot,
and re-issued nightly by a session on the Mini. Nobody in the fetched field signs their thresholds; a
firm that can show a client *"passports auto-attach at a measured ≥ 99.5% [98.9, 99.9], n = 412"* has a
trust artefact no SaaS has. *How:* `services/intake/precision_pack.py` + `scripts/tests/test_precision_pack_signature.py`;
the pack is the single source of every threshold (R2's CI test). *Effort:* M after R2. *Risk:* signing a
pack with n < floor — the pack must refuse to sign and fall back to today's constants. *Acceptance:*
`routing.py` and `extract.py` contain zero literal thresholds; a tampered pack fails boot.

**B2 — P1 — Cross-family, image-grounded grader for every autonomous attach.**
The 3-Mac fleet makes generator ≠ grader possible *without* a cloud seat: the Pro extracts with the
incumbent VLM, the Mini re-reads the same page blind with a different family (GLM-OCR or PaddleOCR-VL
from R5), and `auto_attach` requires agreement on the strong id *and* the subject name before an
autonomous commit; disagreement → quarantine with both readings stored. This is ExtractConf's
strongest signal (cross-call disagreement) plus the repo's own KBLI lane scar (same-family agreement is
a false friend; cross-family image-grounded refutation is mandatory). *How:* `auto_attach.py` gate 6
"second-family concordance", fed by a `grader_stage` in `stages.py` that runs only on `AUTO_ATTACH`
candidates (a few per day, so latency is irrelevant). *Effort:* M. *Risk:* both families share OCR
blind spots on degraded scans — measured, not assumed, via R2. *Acceptance:* on the 135 ground-truth
set, dual-family agreement ≥ deterministic-tier precision; every disagreement is a real error or a
real ambiguity in a 30-case audit.

**B3 — P1 — Consent-backed identity key-book (turn UU PDP into the matching key).**
The measured bottleneck is not model power but missing keys (2.9% passport coverage locally, 74.5%
prod, 2026-07-18). The lawful way to fill them is the client: a self-service "verify my identity"
step — client uploads the passport, local MRZ parse + check digits, the client *confirms* the read, the
key is written `verified:true` with a consent record (basis, timestamp, revocation hook) in
`custom_fields.identity_backfill` next to GATE-11's provenance. Consent collection is already Zero's
decision (2026-08-09); this makes it *produce* the strong identifier every future document corroborates
against, and gives the Art. 56 proof-per-client that SYMBIOSIS says is missing. Intake owns the
primitive (`client_enricher.py` write path + consent columns); the portal surface is B5's. *Effort:* M.
*Risk:* a client confirming a wrong read — the check digits and R2's threshold gate the write.
*Acceptance:* key coverage on active clients rises from measured baseline by ≥ 20 points in 90 days;
0 keys written without a consent row.

**B4 — P2 — Evidence bundles per attach, erasure-ready by construction.**
Every autonomous attach already stores `source_page`, audit and idempotency key. Extend to a per-document
evidence bundle (page hashes, MRZ check-digit results, model + pack version, both family readings
from B2, consent reference from B3) stored locally and hash-referenced from the CRM row. It answers a
client's UU PDP access/erasure request for documents in one query and makes every past decision
re-adjudicable when a pack version is later found wrong — the reversibility the writer promises,
extended to *why*. *Effort:* S-M. *Acceptance:* `SELECT` by client_id returns every bundle; erasure
removes bundles and blobs in one transaction with an audit row.

Deliberately not proposed: fine-tuning (ruled out until corrections reach thousands), a cloud
reviewer seat (measured zero lift), re-OCR of the backlog (measured dead end), a DB workflow registry
(rejected), reviving the mass review loop (retired by Zero).

---

## 7. §Meta-pattern

**Safety was engineered by construction, so measurement was never needed — and the automation
frontier froze exactly where the rules stop.** The organism guarantees zero mis-attribution with
exact-key equality, killswitches, GATE-11 and quarantine-as-success; that discipline is world-class,
and it made calibrated confidence unnecessary for *safety*. But every threshold in the pipeline is a
constant asserted by a session (0.85, 0.95, 0.70, 0.40, 0.15), the corrections table fills only on
real commits, and the human loop that would have produced samples was retired. So the system cannot
learn where its own precision ends: 71% of the queue is "structurally unreachable" by rules, and every
gain since May came from a hand-found structural bug, not from data. The belief generating most
findings here is *precision comes from rules, not from measurement* — Law 7 applied to the product
but not to the decision engine. R2/B1 are the cure class: keep the rules, add the ruler.

---

## 8. §Solo-operatore

Only Zero can decide or do:

1. **Business (Legge 5):** whether the `agy` seat may keep receiving client-document text at all (R1 —
   the E1 finding), and the 2026-07-07 call on the Gemini opt-in OCR path in `classify.py`
   (`PENDING-ARMS.md:294`); whether a 2%/5-per-day correction sample is acceptable after retiring the
   review loop (R3); whether clients are asked to self-verify identity as a service condition (B3).
2. **Consents/credentials:** the Workspace DPA status and per-client consent proof that SYMBIOSIS lists
   as unregistered; Drive domain-wide delegation stays the only working Drive access.
3. **GUI/physical:** nothing in this lane; launchd plist installs on the Pro/Mini are session work.
4. **Spend:** none — every recommendation runs on local Ollama, flat-subscription seats, or Postgres
   already in place. Disk on the Mini for R7 is the only resource decision.

---

## 9. Sources

Fetched with content (access date 2026-08-28):

- [S1] Microsoft Learn — Interpret and improve model accuracy and confidence scores (Azure AI Document Intelligence, page dated 2026-04-08). https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept/accuracy-confidence
- [S2] AWS — Amazon Textract, Analyzing Identity Documents (AnalyzeID). https://docs.aws.amazon.com/textract/latest/dg/how-it-works-identity.html
- [S3] Rossum Knowledge Base — Using AI confidence thresholds for automation in Rossum. https://knowledge-base.rossum.ai/docs/using-ai-confidence-thresholds-for-automation-in-rossum
- [S4] Hyperscience Help — Transcription Accuracy and Automation (v41). https://help.hyperscience.ai/v41/docs/transcription-accuracy-and-automation
- [S5] Google Cloud — Document AI HITL quickstart (resolves to the deprecation notice, HITL deprecated 2024-01-16). https://docs.cloud.google.com/document-ai/docs/hitl/quickstart
- [S6] Splink documentation. https://moj-analytical-services.github.io/splink/
- [S7] Ollama blog — Structured outputs. https://ollama.com/blog/structured-outputs
- [S8] Ollama library — qwen3-vl. https://ollama.com/library/qwen3-vl
- [S9] paperless-gpt (GitHub, MIT). https://github.com/icereed/paperless-gpt
- [S10] Docling (GitHub, MIT). https://github.com/docling-project/docling
- [S11] OmniDocBench v1.6 leaderboard (GitHub). https://github.com/opendatalab/OmniDocBench
- [S12] Instructor documentation. https://python.useinstructor.com/
- [S13] Argilla (GitHub, Apache-2.0). https://github.com/argilla-io/argilla
- [S14] Angelopoulos & Bates, A Gentle Introduction to Conformal Prediction (arXiv 2107.07511, abstract page). https://arxiv.org/abs/2107.07511
- [S15] Kumar, Beyond Logprobs: A Multi-Signal Confidence Engine for LLM-Based Document Field Extraction (arXiv 2606.24420, June 2026). https://arxiv.org/abs/2606.24420

Consulted via search-result summaries only (page not fetched — claims marked as such above): Hyperscience "What is HITL", Google Document AI custom-extractor overview, Clio Grow document/intake help articles (fetch returned 403), HubSpot deduplicate-records (404), AWS A2I Textract task type (empty response).

Internal (read this session): `.claude/skills/intake/SKILL.md`; `SYMBIOSIS.md` §LE LEGGI; `.claude/rules/cicatrix-scars-archive.md:666-741`; `.claude/skills/modus/PENDING-ARMS.md:294,450,660`; `research/operations/` 2026-06-09 pro-reader spec · 2026-06-14 mythos-m4 intake · 2026-06-21 review-time reduction · 2026-06-27 39k backlog · 2026-06-27 OCR bake-off · 2026-06-28 orphan leak · 2026-07-18 identity-backfill · 2026-07-18 station 1-2 rescue · 2026-07-18 SLM audit · 2026-07-19 drive-autocreate design · 2026-07-19 product-corners coherence · 2026-08-19 upsert-by-phone advisory; code files cited inline.

## Adversarial review

**Reviewer: `kimi-k3` (Moonshot K3) and `codex` (OpenAI gpt-5.6-sol at xhigh effort), 2026-08-30 — cross-family, generator ≠ grader.** Neither seat wrote any part of this panel. Both read all 18 files of the set in full and were asked the *publication* question rather than a proof-reading one: what in this diff creates real incremental risk beyond what the repository already discloses, whether "it is already public elsewhere" is a sound argument or a rationalisation, whether the sequencing is wrong, and what is simply FALSE. Every concrete file claim either seat made was then re-derived independently with `grep`/`git` before being recorded, and objections that measurement falsified are kept as RETRACTED rather than quietly dropped. The full journal and the complete objection list, with per-objection status, are in this PR's evidence pack (`council-journal.jsonl` and the pack's `dissent` block).

**Limits of this review, stated so it is not read as more than it was.** It happened at PUBLICATION time, not at authoring time: no seat re-derived this lane's technical findings against the codebase, so it is not a correctness review of the analysis. Nine numeric objections across the set were recorded PLAUSIBLE because the fact-checking pass ran out of time, not because they were investigated and cleared — an open list, not an all-clear.

**Finding for this file:** Two confirmed findings, both re-derived against `origin/main`. **(a)** This file contradicts itself: it states that OCR of identity documents never leaves the machine, and then, two paragraphs later, that OCR'd passport/NPWP/akta text is shipped to a cloud model by CRM-Guardian. The second statement is the true one; a reader who stops at the first gets a false assurance about client PII. **(b)** The defect that second statement describes is real and armed — the worker passes that text as a process argument, visible to any local user, and the organ is loaded on the machine holding the PII. Ledgered, not fixed by publishing this file.
