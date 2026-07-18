---
name: intake
description: "Intake corner — the live shared context for the document-intake organism (WhatsApp/Drive docs → OCR → classify → extract → route → attach-to-client). Load BEFORE touching the intake pipeline, the review_pending queue, the refinery pilot, the auto-attach gates, or the CRM writer — or when Zero says /intake, 'coda intake', 'review queue', 'auto-attach', 'refinery'. Holds: the north star (drain the queue with ZERO mis-attribution), the anatomy map (every table/file/gate/flag), the tier logic, LIVE STATE, and the blood-bought rules (2026-05-17 identity-hallucination scar)."
---

# INTAKE — the document-intake organism

> **North star:** every document that arrives (passport, KITAS, visa, KTP, akta, NIB, NPWP,
> bank statement…) lands attached to the RIGHT client, or is honestly quarantined — **never
> attached to the wrong person.** The backlog is finite (~35.8k `review_pending`); drain it by
> corroboration, not by guessing. **A wrong attach is worse than an unattached doc** (2026-05-17
> scar: name-frequency auto-attach → 12 mis-attributed summaries purged by hand).

---

## 0. The one rule that governs everything

**Auto-commit ONLY on strong-identifier corroboration** (passport / KITAS / NPWP / NIK **number equal**
between the document and the client record). **Name-only is NEVER an auto-commit** — it is the exact
failure mode of the 2026-05-17 identity-hallucination scar. Name-only, at most, pre-fills a decision;
it never writes autonomously without a second concordant signal. The refinery may **quarantine** (say
"not attachable") — that is a correct terminal state, not a failure. Forcing an attach on the ~25k
no-match mountain is forbidden.

---

## 1. Anatomy — where the organism lives

**DB (LOCAL, not Fly — scar W87):** `nuzantara_dev` on `127.0.0.1:5432`, user `nuzantara` (trust auth,
SELECT-only for inspection). The MCP `postgres-nuzantara` points at PROD and is the WRONG store for
intake — always use the local dev DB for intake work.

Core tables:

| Table                             | Key columns                                                                                                                                                                                                                      |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `document_routing_proposal` (`p`) | `id`, `queue_id`, `status` (**review_pending** / review_claimed / routed / **auto_routed**), `entity_resolution` (JSON: `candidates[]{table,id}`, `doc_type`, `decision`), `routing` (JSON: `fields`, `decision`), `commit_gate` |
| `intake_queue` (`q`)              | `id`, `stage_output` (JSON: `classify.ocr_text_per_page[]`, `extract.fields`, `ocr.pages[]`), `source`, `source_ref`, `blob_hash`, `pipeline_version`                                                                            |
| `intake_commit_audit`             | `proposal_id`, `client_id`, `outcome` (dry_run/blocked/committed/failed/rolled_back), `committed_by`, `dry_run` (bool) — every decision recorded, reversible                                                                     |
| `clients`                         | `id`, `full_name`, `phone_normalized`, `passport_number`, `kitas_number`, `nationality`, `deleted_at` (soft-delete)                                                                                                              |

**Extracted fields shape:** `routing.fields` (fallback `stage_output.extract.fields`); each value is
`{value, confidence, source_page}` or a scalar. Strong-id keys: `passport_no`, `kitas_no`.
**Strong-id normalization (canonical):** `re.sub(r"[^A-Za-z0-9]","",str(v)).upper()`, keep only `len>=6`.

**Pipeline (code, in `apps/backend-rag/backend/services/intake/`):**

- `routing.py:1290` → `_try_auto_attach_after_route()` runs the auto-attach gates right after a proposal is routed.
- `auto_attach.py` — the 3 **already-built, tested** gates (all default OFF):
  - `try_auto_attach` (LEVA-2): strong-id ⟂ **phone** concordance.
  - `try_direct_phone_auto_attach`: direct-chat phone-only.
  - `try_nameid_auto_attach` (LEVA-3): strong-id + document-subject-**name** concordance (no-phone sources).
- `writer.py` — the SINGLE safe commit path (reuse it, never raw SQL):
  - `plan_commit(proposal, conn, *, committed_by, override_client_id=None, …) -> CommitPlan` (`.blocked`, `.block_reasons`, `.ops`). READ-ONLY; validates against current DB (P0#3: e.g. **soft-deleted client → blocked**).
  - `execute_commit(plan, conn, *, dry_run=True, advance_from="review_claimed", advance_to="routed") -> CommitResult` (`.outcome`, `.audit_id`). System auto-attach uses `advance_from="review_pending", advance_to="auto_routed"`. `dry_run=False` **requires** `INTAKE_WRITER_ENABLED` truthy, else raises before any write.
  - `rollback_commit(conn, client_id=…, idempotency_key=…, committed_by=…)` — detaches + reopens the proposal.
- `extract.py` — field extraction; `client_enricher.py` — writes doc strong-id onto the client (backfill primitive), same TX as the doc write.

**Feature flags (env, read at call time, ALL default OFF; both the specific flag AND `INTAKE_WRITER_ENABLED` must be on for any autonomous write):**
`INTAKE_WRITER_ENABLED` · `INTAKE_AUTO_ATTACH_ENABLED` · `INTAKE_DIRECT_PHONE_AUTO_ATTACH_ENABLED` · `INTAKE_NAMEID_AUTO_ATTACH_ENABLED`.
**Arming pattern:** for a surgical batch, set the flags **in the batch process env only** (never flip the live routing daemon / never a Fly secret) → blast radius = exactly the proposals the batch iterates.

---

## 2. The tier logic (what may write, and how)

| Tier                                                           | Signal                                             | Precision (135 ground-truth)                                   | Headless?                                   |
| -------------------------------------------------------------- | -------------------------------------------------- | -------------------------------------------------------------- | ------------------------------------------- |
| **Deterministic strong-id**                                    | doc passport/kitas == candidate's, exactly 1 match | **61/61 = 100%**                                               | ✅ safe — arm it                            |
| Panel-unanimous name-only + 2nd signal (phone/nationality/DOB) | both LLMs MATCH same client + a corroborator       | ~100% in-sample (survivor bias)                                | ⚠️ only with the raised bar, measured first |
| Single-model name-only                                         | one LLM MATCH, dissent                             | **owns the only error** (prop 12923: picked 4037 vs truth 659) | ❌ quarantine, never auto                   |
| No match / 0-candidate                                         | —                                                  | —                                                              | quarantine (correct terminal state)         |

**Ambiguity even at strong-id level:** if a doc strong-id matches **>1** client → exclude (data-quality
lead, usually duplicate client records — see the 62130 case, 7 clients one passport).

---

## 3. The refinery pilot (the measuring instrument)

`scripts/intake_refinery_pilot.py` (worktree `backend-rag-intake-refinery`). Panel = `qwen3.5:9b` +
`aisingapore/Qwen-SEA-LION-v4-32B-IT:q4_k_m` (local Ollama, `think:false`, `format:json`) + DeepSeek
(dead, 402). Modes: `--mode groundtruth` (precision vs `intake_commit_audit` committed truth) /
`--mode sample-review` (dry triage of `review_pending`). Run: `cd apps/backend-rag && source .venv/bin/activate`
then `PYTHONPATH=. python scripts/intake_refinery_pilot.py --mode groundtruth --limit 135`.

**Proven findings (2026-07-18):**

- **Panel width / model strength is SECOND-ORDER.** SEA-LION-32B over qwen-9B added **0** auto-commits
  (rescued 1 NONE→triage-candidate). The auto-commit bottleneck is **structural** (CRM has ~2.6% passport,
  0% kitas) — no model can corroborate against absent data. A cloud seat (GLM etc.) is not the lever.
- Deterministic tier: **100% precision**. Name-only single-model owns the only observed error.

---

## 4. Sizing of the 35,796 `review_pending` (read-only scan, 2026-07-18)

- `HAS_DOC_STRONGID` = **5,147** (passport 3,783 / kitas 920 / visa 444).
- `DET_MATCH_NOW` ≈ **20-21** — doc strong-id already equals a candidate → auto-committable today.
- `N1_BACKFILL_FUEL` = **1,338** — single-candidate + doc strong-id the client LACKS → each confirmed
  attach writes that id onto the client (`client_enricher.py`), compounding future auto-corroboration.
- **~25,402 (71%) zero-candidate** — strong-id CORROBORATES, it does not FIND → needs Station 1+2
  (re-OCR + all-clients strong-id/name re-search). This is the volume; the panel does not touch it.

**The levers, in order of volume:** identity-backfill (1,338) + re-OCR/re-search (25k) ≫ deterministic
tier (20) ≫ panel width (0). Reviewers/LLMs drain the human tail; they do not replace the missing
structural signal.

**UPDATE 2026-07-18 — Station 1+2 rescue MEASURED, the 25k mountain is structurally stuck** (full-pop
scans, report `research/operations/2026-07-18-intake-station1-2-rescue-recall.md`):

- **Every one of the 25,400 carries `reason="no strong identifier, no fuzzy name >= 0.40"`** — fase4
  already ran strong-id + fuzzy≥0.40 and correctly found nothing. NOT a too-narrow bug.
- **Station 2 (re-search on already-extracted data, no re-OCR) recovers ~9 of 25,400 (0.04%)**:
  strong-id→client **2**, person-name→client(≥0.45) **7**, company-name→client **1**, transitive
  blob-inherit **0**. Root cause: the CRM has **313 passports / 1 kitas / 62 company_names** — it
  lacks the keys to match against. Strong-id CORROBORATES, it does not FIND.
- **Instrument validated (W65):** attached docs' names trigram-match their own client at avg 0.79,
  ≥0.45 in 90% (87/97). So the 7/5,661 is real — the subjects are genuinely not in the CRM
  (prospect / third-party on KTP-KK-akta / never-entered), ~88% genuine no-match.
- **Station 1 (re-OCR) structurally BLOCKED at scale:** of the 25,400 blobs only **594 (2.3%) still
  exist on disk** — `com.nuzantara.intake-blob-retention` (TTL=7d) unlinked the rest. **Of the 594
  present, 0 are stubs.** You cannot re-OCR files that are gone. Re-fetch from Drive is possible
  (`source_ref="drive:<file_id>"`, 24,276 IDs) but costs 24k downloads + 24k vision passes for a
  ~0.1% match ceiling — economically absurd, and does not fix the missing CRM keys.
- **Station 0 (dedup/junk) is the one real-volume lever left** (reads blob_hash, not the blob file):
  **2,152 removable exact-dup blobs** (1,090 groups) + **203 hard-junk non-docs** (.zip/.aae/.mp4/…)
  → 2,355 rows (9%) can reach a correct terminal state, zero mis-attribution risk. Queue hygiene,
  not recovery. Reproducible: `scripts/intake_station0_report.py` (dry-run).
- **The real levers (root cause):** (1) identity-backfill (fill CRM keys so future docs corroborate);
  (2) retention-TTL extension / cold blob-archive (so re-processing has raw material). NOT more
  re-OCR, NOT panel width, NOT a cloud reviewer seat.

---

## 5. LIVE STATE (update on every material change)

- **2026-07-18 late night — LOCAL SNAPSHOT REFRESHED (safe method — NOT the stock script):**
  `nuz_db_refresh.sh` does `dropdb nuzantara_dev` — on the Pro that would DESTROY the
  local-authoritative intake state (247k `intake_queue` rows whose `stage_output` is the ONLY OCR
  copy, 71.8k proposals, audit; prod intake tables verified EMPTY 0/0/0). Safe procedure executed
  instead: safety dump of dev (209M) → full prod dump (368M, readonly role via the MCP proxy
  :15432) → restore into the separate DB **`nuzantara_prod_snapshot`** (complete fresh prod
  mirror, use it for cross-checks; needed `brew install postgis` — prod `clients.geo_point`) →
  content-swap of ONLY `clients` in `nuzantara_dev` (DELETE+COPY under
  `session_replication_role=replica`). Dev schema gained prod's 10 new columns — **`npwp` (291
  alive), `nib`, `tax_id`, visa/kitas expiry** — previously-invisible strong-id substrate;
  POSSIBLE new lever: a re-route could gain strong-id matches IF routing consults npwp (verify
  before claiming). Verified after: dev.clients=1,757 alive / 1,665 with folder / client 3346
  intact; intake untouched (audit=885 unchanged). Known residue: 21 `documents` + 6 `practices`
  rows orphaned by prod hard-deletes (report-only).

- **2026-07-18 night — `google_drive_folder_id` backfill CLOSED + PROD-DEDUP DISCOVERY:** the
  "173/11,744 populated" premise was STALE-SNAPSHOT math. Prod truth (verified twice: Fly API GET +
  readonly MCP SELECT): the CRM book was **mass-deduped on prod — 1,755 alive clients** (local
  snapshot still holds ~11.7k pre-dedup rows, 128/128 probed "alive" locally were dead/absent on
  prod), and **1,664/1,755 (94.8%) already have `google_drive_folder_id`** via the server-side
  ensure-folder flow. Session-as-reviewer backfill (`scripts/intake_drive_folder_id_backfill.py`,
  Tier-A bar: exact-name OR sim≥0.85 + Drive ancestor-walk ground truth + live-screen-BEFORE-
  bijectivity + TOCTOU re-check + never-overwrite): **234 candidates → 1 applied:verified (client 3346)**, 61 already served live, 128 dead on prod, 44 Drive-unresolved (folders renamed/moved
  post-enqueue — correct terminal skips). **The gdrive-backfill lever is exhausted; every local-book
  analysis (incl. the 88.5% ceiling below) needs recompute after `nuz_db_refresh.sh`.** Drive access
  gotcha: the SA alone sees NOTHING (404) — DWD impersonation `zero@balizero.com` is mandatory.

- **2026-07-18 evening — BACKLOG REROUTED through the m227 fix (EXECUTED, measured):**
  `scripts/intake_reprocess_backlog.py --reroute-drive-folder --apply` resumed **24,256** Drive
  0-candidate rows at route-only (stage_output PRESERVED — the blobs are retention-evicted, the saved
  fields are the only copy; the generic `--reprocess` would have WIPED them, locked by test). Worker
  restarted first (launchagent `com.nuzantara.intake-worker` runs from `~/nuzantara-deploy`, had
  pre-merge code in memory). Drained in ~5 min. **Outcome: 1,588 docs (6.5%) gained ≥1 candidate —
  1,285 LINK_CANDIDATE + 300 AMBIGUOUS** (676 LINK + 172 AMBIG live in review_pending; 588+128 in
  quarantine via the LEVA-1 noise filter, consultable). Methods: folder_name 1,665, fuzzy_full_name
  195, strong-id 3 (2 passport + 1 kitas — enricher backfill from prior attaches already compounding).
  **never-auto held: 0 auto_routed.** Side-win: 14,859 noise NO_MATCH moved review_pending→quarantine
  (review feed −~15k). Pipeline tag: `pipeline_version='v2.2-m227-folder'`.

- **2026-07-18 (m227 FOLDER FIX — the structural lever for the 24k drive backlog):** `routing.py::
_match_folder_name` was **root-segment-only** (`source_path.split('/')[0]`) — correct for Dropbox
  (client folder at root) but BLIND to Drive, whose 16 roots are staff/category folders
  (`PEMEGANG KITAS`, `EXTEND VISA`, `NOVI`…) and whose client folder sits at depth 2–3. So the folder
  signal (a NEVER-auto transport hint) structurally never fired on Drive → all 24,277 drive docs land
  0-candidate despite the logic existing (#2 exists≠armed). **Fix (new `_folder_segments`): scan EVERY
  segment, dedup by (table,id), keep FUZZY_APPLY_THRESHOLD=0.70 + ambiguity margin.** Recall
  (prod semantics): **1,231 docs (5.1%) gain a folder candidate, 1,005 unique → LINK_CANDIDATE**, ~95%
  precision (attached ground truth 19/20). 466 intake tests pass + 10 new (`test_intake_routing_folder.py`).
  Dual value: fixes ingress (future docs resolve at enqueue) + backlog (via `intake_reprocess_backlog.py`,
  operator-armed apply). Report: `research/operations/2026-07-18-intake-station1-2-rescue-recall.md`.
  **NOTE:** `client_id_hint` is NOT consumed by fase4 (only written) — the fix is in the matcher, not the hint.
- **Ceiling stays structural:** 88.5% of client-folders (3,591/4,057) name entities absent from the CRM
  (313 passports / 1 kitas / 62 company_names / 173 google_drive_folder_id of 11,748 clients). Folder
  recovers the ~5% catalogued; the rest are uncatalogued prospects (data gap). Root-cause levers:
  backfill `google_drive_folder_id`, extend blob-retention TTL, enter the ~1,215 uncatalogued folders.
- **2026-07-18:** deterministic tier proven (61/61) + **18 documents auto-attached** via `plan_commit`/
  `execute_commit` (tag `committed_by='system:refinery-deterministic'`, `review_pending`→`auto_routed`,
  reversible). Pilot v2 committed (`a4914660b`, adds SEA-LION panel + N-model gate).
- **OPEN — 3 soft-deleted-client proposals** (82041/82021/82034 → client 10236, `deleted_at` set):
  correctly refused by the writer, still `review_pending`. Decision: restore client vs re-route vs human.
- **OPEN — dedup anomaly 62130:** 7 clients share one normalized passport → likely duplicate client
  records; a direct lead into the CRM dedup problem.
- **NOT DONE — entry leak** (~3,084 wa-mirror rows never enqueued, ~80/day) + **1,345 rows frozen
  mid-pipeline since 2026-06-20** — separate upstream levers; the refinery drains, the leak bleeds.

---

## 6. Blood-bought rules (scars)

- **2026-05-17 identity-hallucination:** name-frequency auto-attach mis-attributed 12 → **never
  name-only auto**. Strong-id corroboration or quarantine.
- **W65 generator≠grader:** the model that proposes a match never grades it. The refinery uses a
  separate panel; any "confirmed" verdict is re-checked, not trusted.
- **W87 postgres access-wall:** intake lives on LOCAL `nuzantara_dev`, NOT the Fly-prod MCP. `✔ Connected`
  ≠ auth+query.
- **W96 test-writes-prod:** intake tests must redirect output/DB to fixtures, never touch the real queue.
- **Law 2 (UU PDP):** the refinery's _output_ is an attach decision (doc_id→client_id) INSIDE the system.
  Reports / memories / logs / skills **never** transcribe client PII (names, passport/kitas VALUES,
  phones) in clear — integers, `client_id`, field-name-matched only. Processing may use context; output may not.
- **Reversibility:** dry_run → measured precision → real write in batches, with `intake_commit_audit`
  - `rollback_commit` + a kill-switch (the flags). Never a blind mass write.

---

## 7. Design spec + references

- Full station design (Station 0 dedup/junk → 1 re-extract → 2 candidate-regen → 3 panel → 4 gate →
  5 commit): scratchpad `intake-refinery-design.md`.
- Memory: `discovery_refinery_panel_width_is_second_order_2026_07_18` (findings + sizing + precision).
- Writer/gate code is the ground truth — re-read `writer.py` / `auto_attach.py` in-turn before any mutation
  (anti-hallucination: never build on a remembered signature).
