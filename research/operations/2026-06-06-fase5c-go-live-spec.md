---
date: 2026-06-06
domain: compliance
client_case: document-intake CRM writer (FASE 5C go-live)
sources:
  - apps/backend-rag/backend/services/intake/writer.py (origin/main @ 12c67b38d — post #1145)
  - apps/backend-rag/backend/app/routers/intake_review.py
  - apps/backend-rag/backend/app/setup/router_manifest.py:206
  - apps/backend-rag/backend/db/migrations_v2/217_intake_commit_audit.sql
  - apps/backend-rag/backend/tests/services/intake/test_intake_writer.py
  - apps/backend-rag/backend/tests/routers/test_intake_review.py
  - backend-verifier empirical investigation 2026-06-06 (read-only, DB + code)
  - PR #1145 (writer real-commit path, MERGED 12c67b38d) + PR #1147 (/reject)
status: LIVE RUNBOOK — Fork A chosen (operator 2026-06-06); writer impl MERGED (#1145); /reject (#1147); awaiting operator Stage-1 secret activation
---

# FASE 5C — Document-Intake CRM Writer Go-Live — Spec

> **5C = activate the real CRM writer** so that approving an intake actually attaches
> the document to the client/practice in the CRM (today, 5B, an approve only logs a
> `dry_run=true` audit row and writes nothing).
>
> **POST-IMPLEMENTATION RUNBOOK (updated 2026-06-06).** The original draft was a
> research doc written BEFORE the code existed. The code is now shipped: the writer
> real-commit path merged in **PR #1145** and `/reject` in **PR #1147**. What remains is
> purely the **operator's Stage-1 secret activation** in a low-traffic window. Everything
> below the strikethrough/✅ marks describes what is now DONE; §4 is the live go-live
> sequence.

---

## 0. TL;DR — what changed, and what's left

**Then (draft):** `INTAKE_WRITER_ENABLED=on` alone did nothing — `approve_review` passed
`dry_run=True` **hardcoded**, so the flag was a dead inner guard and 5C was unshipped code.

**Now (#1145 merged):** the call-site is `dry_run = not writer_enabled()`. The flag IS the
switch. With it OFF (default) approve is dry-run (5B); with it ON, approve commits for real
inside one transaction (document UPSERT + practice link + proposal→`routed` + audit), and
`rollback_commit()` can undo a bad commit. 11/11 real-write tests pass on `nuzantara_dev`.

**Left:** ONE operator action — set the Fly secret in a low-traffic window (§4 Stage 1),
canary, observe. No code remains. The §1 fork decision (Fly vs local) is **DECIDED: Fork A**.

---

## 1. The load-bearing decision: where does 5C write? (Fly vs local)

> ✅ **DECIDED: Fork A (write to the Fly prod CRM). Operator confirmed 2026-06-06.**
> The real Bali Zero CRM (`clients`/`practices`/`documents`) lives on Fly; the intake
> writer attaches documents where the real clients are. The misleading "mai Fly" comment
> on migration 217 was corrected (PR #1143). The Fork A/B analysis below is kept for the
> record. **Fork B (local-only re-architecture) is NOT pursued.**

**The contradiction** (verified empirically — this is what the decision resolved):

- `217_intake_commit_audit.sql` header + `writer.py` docstring assert:
  *"PII 100% locale (Law 2 / UU-PDP): MAI applicare su Fly. Solo nuzantara_dev @127.0.0.1."*
- BUT the writer is reached **only** through the `intake_review` HTTP router, registered
  `process_groups=_RAG` (`router_manifest.py:206`) → ships on the **Fly `rag` machine** →
  its DB pool is the Fly secret `DATABASE_URL` = **Fly Postgres PROD CRM**.
- There is **no local-only execution path** for the writer today. The local intake worker
  (`com.nuzantara.intake-worker.plist`, Pro-only, `nuzantara_dev@127.0.0.1`) does NOT call
  the writer at all.

So as wired, enabling 5C writes PII to **Fly Postgres**, directly contradicting the
migration's "mai Fly" contract.

### The two forks

**Fork A — Fly is correct (the comment is a dev-time guard to remove).**
- Rationale: the *real* Bali Zero CRM (`clients`/`practices`/`documents`) that the team
  uses on `kita.balizero.com` LIVES on Fly. A document-intake whose whole job is "attach
  this doc to the real client" must write where the real clients are. A local-only writer
  would attach documents to an isolated `nuzantara_dev` that the team never sees —
  operationally pointless.
- PII perimeter: the entire CRM (incl. `documents`) is **already** on Fly. 5C does not
  widen the PII perimeter; it writes into a table class that is already there.
- Consequence: correct the misleading "mai Fly" comment (already partly done in PR #1143),
  treat 5C as a normal backend feature behind review.
- **Effort: MEDIUM.** Call-site change + proposal-advancement + tests.

**Fork B — local-only is correct (Law 2 radical sovereignty).**
- Rationale: PII documents must never leave the Pro; the Fly CRM should hold only
  metadata/pointers, and the actual document blobs + intake commits live on the Pro.
- Consequence: the writer CANNOT run on the Fly `_RAG` router. The whole approve→commit
  path must move to a **local process on the Pro** (extend the local intake worker, or a
  new local HITL service), talking only to `nuzantara_dev@127.0.0.1`. The Fly CRM would
  need a sync/pointer mechanism so the team still sees the attachment.
- **Effort: HIGH (architectural).** This is not a 5C task — it's a CRM data-domain
  re-architecture. 5C would be blocked behind it.

### Verifier's reading (to confirm, not assume)
The codebase strongly suggests **Fork A**: `documents`/`practices`/`clients` are already
Fly-prod tables the team reads from Fly; the "mai Fly" line reads like a guard written
during 5B local development, not the intended final architecture. **But this is a
sovereignty decision and belongs to Antonello, not inferred by the implementer.**

> ⚠️ **Side finding to resolve regardless of fork**: in 5B today, an `approve` call on
> prod already writes the `dry_run` audit row to **Fly** (router on Fly pool). Confirm
> migration 217 is applied on whichever DB the approve path actually hits (verifier saw
> 217 in Fly `_schema_versions` after #1137 — so the Fly table exists; good). If Fork B is
> chosen, those 5B audit rows are on the WRONG DB and need accounting.

---

## 2. Verified current state (origin/main @ 12c67b38d — post #1145)

### Control flow
- `approve_review()` → `execute_commit(plan, conn, dry_run=not writer_enabled())`
  ← ✅ **was hardcoded `True`; #1145 wired it to the flag.**
- `execute_commit`:
  - `plan.blocked` → audit `outcome="blocked"`, return (both modes).
  - `dry_run=True` → ONE `intake_commit_audit(dry_run=true, outcome="dry_run")`, return. No CRM write.
  - `dry_run=False` → `if not writer_enabled(): raise WriterDisabledError` (flag gate),
    then real writes.
- `writer_enabled()` reads env `INTAKE_WRITER_ENABLED` at **call time** (not import) →
  default OFF.

### What the real path writes (dry_run=False)
1. `INSERT INTO documents ... ON CONFLICT (client_id, intake_idempotency_key) DO UPDATE
   SET updated_at=now() RETURNING id` (UPSERT — `write_client_document`).
2. `UPDATE practices SET documents=$1::jsonb, updated_at=NOW() WHERE id=$2` (append to
   JSONB `documents[]` after `SELECT ... FOR UPDATE` + dedup by `drive_file_id`).
3. `advance_proposal()`: `UPDATE document_routing_proposal SET status='routed' + clear
   lease WHERE status='review_claimed'` (#1145 — proposal advanced exactly once, same TX).
4. `INSERT INTO intake_commit_audit (... dry_run=false, outcome='committed' ...)`.

All four are inside ONE `conn.transaction()` (the `approve_review` request TX). A failure
anywhere rolls back all of them (verified: `test_exception_mid_tx_rolls_back`).

### Guards already present (substantive — keep)
- Idempotency UNIQUE `uq_documents_intake_key (client_id, intake_idempotency_key)` +
  UPSERT `ON CONFLICT`. Intake-instance-scoped key (P0#1).
- Cross-client orphan guard: `practice.client_id != client_id` → `plan.blocked` (P0#3).
- Soft-delete guard: `clients.deleted_at is not None` → blocked.
- family_member ownership: `frow.client_id != client_id` → blocked.
- Practice row lock `SELECT ... FOR UPDATE` + membership dedup by `drive_file_id` (P0#6).
- UPSERT NULL-guard: `doc_id is None → raise` (P0#2).
- Claim/lease enforcement in `approve_review`: status `review_claimed`, lease unexpired,
  non-admin needs matching `claim_token` (P0#5).
- OCR preservation: never resets `ocr_status` completed→pending; no side-effects in TX (P0#8).

---

## 3. Work checklist (was "missing" — now mostly DONE)

1. **[DECISION] Resolve §1 fork.** ✅ **DONE** — Fork A (Fly prod CRM), operator 2026-06-06.
2. **[CODE] Call-site activation.** ✅ **DONE (#1145)** — `approve_review` passes
   `dry_run = not intake_writer.writer_enabled()`. Flag OFF (default) → dry-run fail-safe;
   flag ON → real commit. Startup `log_writer_status()` logs a WARNING when the flag is ON.
3. **[CODE] Proposal advancement in the commit TX.** ✅ **DONE (#1145)** — `advance_proposal()`
   moves the proposal `review_claimed → routed` (terminal) + clears the lease, inside the
   SAME transaction as the document/practice writes. Idempotent guard on
   `status='review_claimed'`.
4. **[TEST] Real-write coverage (dry_run=False, flag ON).** ✅ **DONE (#1145)** — 11/11 on
   `nuzantara_dev` (Pro): real `documents` INSERT + `practices` append + proposal `routed` +
   audit `committed`; idempotent re-commit (UPSERT no-op, no dup); blocked-plan zero write;
   exception mid-TX full rollback; proposal advanced exactly once.
5. **[OPS] Reversal.** ✅ **`rollback_commit()` shipped (#1145)** — deletes the document by
   `(client_id, intake_idempotency_key)`, detaches the practice link, re-opens the proposal
   (`routed → review_claimed`), writes a `rolled_back` audit row, idempotent. The manual-SQL
   fallback (delete `documents` → strip `practices.documents[]` → mark audit) stays
   documented for the case where the helper can't run.
6. **[OPS] Confirm migration 217 applied on the target DB** (Fork A: Fly). ✅ Verified
   present in Fly `_schema_versions` after #1137.
7. **[CODE] `/reject` terminal path.** ✅ **DONE (#1147)** — `review_claimed → rejected` +
   lease clear. **NOT flag-gated** (queue-management op, no CRM PII — works in 5B and 5C so
   reviewers can dispose of garbage proposals now). **No `intake_commit_audit` row** (a
   rejection is recorded by the proposal's own terminal status). No migration. 7 reject
   tests green on `nuzantara_dev`.

---

## 4. Safe activation sequence (Fork A — LIVE)

> Mirrors the W38 staged-with-observation pattern. Nothing flips without a low-traffic
> window + immediate verification + ability to revert in one step.

- **Stage 0 — ship the code, flag OFF.** ✅ **DONE.** Writer (#1145) + `/reject` (#1147)
  merged. Runtime unchanged: `INTAKE_WRITER_ENABLED` unset → `dry_run=True` fallback. CI
  green; 11/11 writer + 7 reject tests pass on `nuzantara_dev`.

- **Stage 1 — flip the secret (operator action, low-traffic window).** The next approve
  commits for real:
  ```bash
  fly secrets set INTAKE_WRITER_ENABLED=1 -a nuzantara-rag
  # ( =1 | =true | =yes | =on are all truthy per writer_enabled() )
  ```
  On the next request the rag machine restarts and logs at startup:
  `INTAKE WRITER ENABLED — real CRM commits are ACTIVE` (grep the Fly logs to confirm).

- **Stage 2 — canary.** Do ONE real approve on a known throwaway/test client (claim →
  approve with its token), then verify on the Fly DB (`:pid` = the proposal id):
  ```sql
  -- document written + linked to the right client/proposal
  SELECT id, client_id, intake_proposal_id, intake_idempotency_key, practice_id
    FROM documents WHERE intake_proposal_id = :pid;
  -- practice membership appended
  SELECT id, jsonb_array_length(documents) AS n_docs FROM practices WHERE id = :practice_id;
  -- audit committed (not dry_run)
  SELECT id, outcome, dry_run, doc_id, committed_at FROM intake_commit_audit
    WHERE proposal_id = :pid ORDER BY committed_at DESC LIMIT 3;
  -- proposal advanced to terminal
  SELECT id, status, lease_owner FROM document_routing_proposal WHERE id = :pid;  -- expect 'routed'
  ```
  Then re-approve the SAME intake instance and confirm idempotency: still ONE `documents`
  row, no duplicate entry in `practices.documents[]`, same `doc_id`.

- **Stage 3 — observe N hours.** Watch the audit outcome mix:
  ```sql
  SELECT outcome, count(*) FROM intake_commit_audit
   WHERE committed_at > now() - interval '6 hours'
   GROUP BY outcome ORDER BY 2 DESC;
  -- anomaly signal: outcome IN ('failed','blocked') climbing
  ```
  (Note: a healthy stream of human `/reject`s does NOT show here — reject writes no audit
  row by design, so the `failed`/`blocked` signal stays clean.)

- **Revert (one step).** Any anomaly → unset the secret; future commits raise
  `WriterDisabledError`, no new writes:
  ```bash
  fly secrets unset INTAKE_WRITER_ENABLED -a nuzantara-rag
  ```

- **Rollback of DATA already written** (if a bad commit landed): use `rollback_commit()`
  (writer.py — deletes the doc, detaches the practice link, re-opens the proposal,
  audits `rolled_back`) or the manual SQL in §3.5. The flag only stops *future* writes.

- **`/reject` is unaffected by all staging** — it is flag-independent and already live from
  the moment #1147 merges.

---

## 5. Panel questions — RESOLVED

The pre-impl 4-LLM panel ran (2026-06-06) and every question is now answered + shipped:

1. **Fork A vs Fork B?** → **Fork A** (operator decision). The CRM already lives on Fly;
   5C does not widen the PII perimeter.
2. **`dry_run = not writer_enabled()` the right wiring?** → **Yes**, shipped (#1145). The
   flag is the single switch; missing flag falls back to dry-run (fail-safe). A startup
   WARNING log makes the ON state loud.
3. **Writes + advancement + audit in ONE TX?** → **Yes** — `advance_proposal()` runs in the
   same `conn.transaction()` as the document UPSERT + practice append + audit. Verified by
   `test_exception_mid_tx_rolls_back` (a mid-TX failure rolls back all four). This was the
   panel's load-bearing failure-mode (no orphan doc, no routed-without-doc).
4. **Idempotency key collision-safe across re-OCR?** → **Yes** — intake-instance key
   `sha256(source|source_ref|blob_hash|doc_index|pipeline_version)`, UNIQUE per
   `(client_id, key)`. Verified by `test_real_commit_idempotent_recommit` (re-commit reuses
   the same `doc_id`, no dup).
5. **Manual-SQL reversal vs `rollback_commit()` helper?** → Panel elevated the helper to a
   HARD prerequisite. **`rollback_commit()` shipped (#1145)**, tested
   (`test_rollback_commit_undoes_document`). Manual SQL kept as fallback.

> The panel + running the tests on a real DB caught 4 latent bugs that the dry-run path
> never exercised (partial-index `ON CONFLICT`, JSONB double-encoding, NULL `practice_id`,
> `chk_ica_*` violations) — all fixed before merge. See PR #1145.

---

## 6. Recommendation — only Stage 1 remains

All code gates are passed. The single remaining action is the operator's:

- **When ready, in a low-traffic window, run §4 Stage 1** (`fly secrets set
  INTAKE_WRITER_ENABLED=1 -a nuzantara-rag`), then the §4 Stage 2 canary + Stage 3
  observation. Revert is one `fly secrets unset`. Already-written rows are reversible via
  `rollback_commit()`.
- Until then the flag stays OFF and the system is byte-identical to 5B (dry-run). `/reject`
  is already live and flag-independent.
