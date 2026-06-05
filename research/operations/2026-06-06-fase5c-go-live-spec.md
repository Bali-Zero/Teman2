---
date: 2026-06-06
domain: compliance
client_case: document-intake CRM writer (FASE 5C go-live)
sources:
  - apps/backend-rag/backend/services/intake/writer.py (origin/main @ a94a236b1)
  - apps/backend-rag/backend/app/routers/intake_review.py
  - apps/backend-rag/backend/app/setup/router_manifest.py:206
  - apps/backend-rag/backend/db/migrations_v2/217_intake_commit_audit.sql
  - apps/backend-rag/backend/tests/services/intake/test_intake_writer.py
  - backend-verifier empirical investigation 2026-06-06 (read-only, DB + code)
status: DRAFT — awaiting Antonello decision on the Fly-vs-local sovereignty fork + 4-LLM panel review
---

# FASE 5C — Document-Intake CRM Writer Go-Live — Spec

> **5C = activate the real CRM writer** so that approving an intake actually attaches
> the document to the client/practice in the CRM (today, 5B, an approve only logs a
> `dry_run=true` audit row and writes nothing).
>
> This spec is **NOT an implementation**. It documents the verified current state, the
> ONE load-bearing open decision (Fly-vs-local), the missing work, and the safe
> activation + rollback path. Nothing here is executed until Antonello picks the fork
> and the 4-LLM panel red-teams it.

---

## 0. TL;DR — why "flip the flag" is wrong

`INTAKE_WRITER_ENABLED=on` **alone does nothing**. The only caller of the writer
(`approve_review` in `intake_review.py`) passes `dry_run=True` **hardcoded**. The env
flag is a *second inner guard*, not the activation switch. 5C is **unshipped code**, not
a config toggle. Plus there is one architectural decision that must be made first.

---

## 1. The load-bearing decision: where does 5C write? (Fly vs local)

**The contradiction** (verified empirically):

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

## 2. Verified current state (origin/main @ a94a236b1)

### Control flow
- `approve_review()` → `execute_commit(plan, conn, dry_run=True)`  ← **hardcoded True**.
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
2. `UPDATE practices SET documents=$1, updated_at=NOW() WHERE id=$2` (append to JSONB
   `documents[]` after `SELECT ... FOR UPDATE` + dedup by `drive_file_id`).
3. `INSERT INTO intake_commit_audit (... dry_run=false, outcome='committed' ...)`.

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

## 3. What is MISSING before 5C (the actual work)

1. **[DECISION] Resolve §1 fork.** Blocks everything. Fork A → proceed below. Fork B →
   5C is deferred behind a CRM-domain re-architecture (separate spec).
2. **[CODE] Call-site activation.** Change `approve_review` to pass `dry_run=False` when
   the writer should commit — e.g. `dry_run=not writer_enabled()`, so the flag becomes the
   real switch and a missing flag still falls back to dry-run (fail-safe).
3. **[CODE] Implement deferred proposal/queue advancement + `intake_corrections` INSERT.**
   Currently a `# … happens here in 5C` placeholder. Without it, a committed doc leaves the
   proposal still `review_claimed` → it re-surfaces as claimable (double-attach risk
   bounded by idempotency UPSERT, but state is wrong). MUST advance proposal→terminal +
   release/close the queue row in the SAME transaction as the writes.
4. **[TEST] Real-write coverage (dry_run=False, flag ON).** Today ZERO tests exercise an
   actual INSERT/UPDATE. Need:
   - real `documents` INSERT + `practices` UPDATE assertions;
   - idempotent re-commit (2nd commit of same proposal = UPSERT no-op, no dup in
     `practices.documents[]`);
   - blocked-plan → zero write;
   - exception mid-TX → full rollback (nothing partially committed);
   - proposal advanced to terminal state exactly once.
5. **[OPS] Reversal runbook.** No automated un-commit exists. Document the manual SQL:
   from `intake_commit_audit WHERE outcome='committed'` → delete `documents` by
   `(client_id, intake_idempotency_key)` → strip from `practices.documents[]` → mark audit
   `rolled_back`. (Consider a `rollback_commit()` helper as a 5C+1 nice-to-have.)
6. **[OPS] Confirm migration 217 applied on the target DB** (Fork A: Fly — verified present).

---

## 4. Safe activation sequence (Fork A — DRAFT, pending panel)

> Mirrors the W38 staged-with-observation pattern. Nothing flips without a low-traffic
> window + immediate verification + ability to revert in one step.

- **Stage 0** — ship the CODE (items §3.2–3.4) as a normal reviewed PR, **flag still OFF**
  (default). Merging this changes nothing at runtime because `INTAKE_WRITER_ENABLED` unset
  → `dry_run=True` fallback. CI green + real-write tests passing is the gate.
- **Stage 1** — pick a **low-traffic window**. Set the Fly secret
  `INTAKE_WRITER_ENABLED=on` on `nuzantara-rag`. The next approve commits for real.
- **Stage 2** — **canary**: do ONE real approve on a known test/throwaway client, verify:
  `documents` row created, `practices.documents[]` updated, `intake_commit_audit
  outcome='committed'`, proposal advanced. Then verify a re-approve is a no-op (idempotent).
- **Stage 3** — observe N hours; watch `intake_commit_audit outcome IN ('failed','blocked')`
  rate. Any anomaly → **revert = unset the Fly secret** (`fly secrets unset
  INTAKE_WRITER_ENABLED`) → future commits raise `WriterDisabledError`, no new writes.
- **Rollback of DATA already written** (if needed): manual SQL per §3.5 runbook. The flag
  only stops future writes; it does not un-write.

---

## 5. Open questions for the 4-LLM panel (mandatory pre-impl, CLAUDE.md §6)

1. Is **Fork A** the right call, or is there a Law-2 reading that mandates Fork B? (Gemini
   + DeepSeek to argue both sides; NB-1 if a sovereignty doc exists.)
2. Is `dry_run = not writer_enabled()` the right fail-safe call-site wiring, or should
   activation be even more explicit (per-request opt-in, admin-only)?
3. Transaction boundary: are writes + proposal-advancement + audit all in ONE TX? Confirm
   no partial-commit window (the `_append_practice_document` lock + the documents UPSERT +
   the proposal UPDATE must be atomic).
4. Is the idempotency key truly collision-safe across a re-OCR of the same physical blob
   for the same client? (P0#1 says intake-instance, not content — confirm a re-upload
   doesn't silently dedup a genuinely new document.)
5. Reversal: is manual-SQL-via-audit acceptable for go-live, or is a `rollback_commit()`
   helper a hard prerequisite?

---

## 6. Recommendation (process, not action)

- **Do NOT set `INTAKE_WRITER_ENABLED=on` today.** It would do nothing useful (call-site
  still dry-run) and, once the call-site is wired, would write to Fly prod — which is
  exactly the §1 decision that must be made first.
- **Sequence**: Antonello picks the §1 fork → 4-LLM panel red-teams this spec → if Fork A,
  implement §3.2–3.4 behind the still-OFF flag as a reviewed PR → only then the staged §4
  activation. Every step reversible; the writer never touches real client data until the
  canary + observation pass.
