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
| Table | Key columns |
|---|---|
| `document_routing_proposal` (`p`) | `id`, `queue_id`, `status` (**review_pending** / review_claimed / routed / **auto_routed**), `entity_resolution` (JSON: `candidates[]{table,id}`, `doc_type`, `decision`), `routing` (JSON: `fields`, `decision`), `commit_gate` |
| `intake_queue` (`q`) | `id`, `stage_output` (JSON: `classify.ocr_text_per_page[]`, `extract.fields`, `ocr.pages[]`), `source`, `source_ref`, `blob_hash`, `pipeline_version` |
| `intake_commit_audit` | `proposal_id`, `client_id`, `outcome` (dry_run/blocked/committed/failed/rolled_back), `committed_by`, `dry_run` (bool) — every decision recorded, reversible |
| `clients` | `id`, `full_name`, `phone_normalized`, `passport_number`, `kitas_number`, `nationality`, `deleted_at` (soft-delete) |

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

---

## 5. LIVE STATE (update on every material change)

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
