---
adversarial_review: codex
reviewed_source_sha256: "236f3745e7ddb421be06abd65dd4481356634cac3159775d35758e798e71b6ea"
review_disposition: HISTORICAL_OR_PENDING_PROPOSAL_NOT_ADMITTED
---

# B06 Business-Domain Paths — Development & Verification Proposal (`D04`–`D10`)

> **Dux addendum (2026-10-16, supersedes every conflicting statement below, including the 2026-10-15 correction).**
> Authoritative status and evidence: `RESULT.json`. `test_b06_domain_paths.py` runs 18 passed, 0 skipped, offline over committed
> files only (`fixtures/consumer-matrix-metadata.csv`, `fixtures/manifest.json`, `fixtures/receipts/`). Pinned receipts:
> `DUX-REQ-B06-01.out` sha256 `1551433483cb28444c7729aef228a351edc0a644880ec01d8b77546bb20f5cbb` and `DUX-REQ-B06-03.out` sha256 `e30e1c44d8e6ab797e20dc7722eb27854cc1e04a2feab325db2d0a1f3c9d10aa` (earlier text swapped them). The
> 683 B06-prefix rows are 504 `NOT_ENRICHED_THIS_PHASE` + 179 `MATCHED_SOURCE_PATH_ONLY; ACTOR_IDENTITY_UNRESOLVED`; the 527/155/1
> split, the 2,608-row business-label subset of `domain_hint` and a "parent run 3 passed / 8 failed" are withdrawn as
> unsupported. `dux-requests/` and `.agent-receipts/...` paths below are historical, untracked locations; the shipped copies
> live in `fixtures/`. Dispositions marked ACCEPTED for X10 (hash discipline), X12 (offline from committed files) and B06-F4
> (coverage counts) are met only as stated in this addendum. No runtime role, live aggregate or restore measurement is
> claimed; `block_closed` stays `false`.

- **Campaign**: `universal-db-wave8-20261015`
- **Block**: `B06` ("Business-domain paths")
- **Host / Seat**: `[Mini]` / Gemini block lead (`EXTERNAL PREPARER, NO_DUX`)
- **Worktree**: `~/nuzantara/.worktrees/db-udb-b06-domains`
- **Base Commit (`source_version`)**: `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`
- **Stage**: `ANALYSIS` (`PROPOSAL.md` deliverable)
- **Owned Write Perimeter**: `research/operations/udb-wave8/B06/**` and assigned evidence pack path (`BATTLE.md:10`)

---

## 1. Proposal Scope & Non-Goals

### 1.1 Scope (Inside B06 Perimeter)

In accordance with `BATTLE.md:10-29` and `ASTRA-ADVICE.md:1-12`, B06 does **not** redesign production business logic or mutate application routers during Wave 8 discovery/verification. Instead, B06 delivers a deterministic **Domain Operation Contract Extractor & Verification Suite** inside `research/operations/udb-wave8/B06/` that:

1. Emits machine-validated, `B05`-compatible operation-instance records for all 7 business-domain research lines (`D04`–`D10`), separating **contract-ready atomic subsystems** from **split-transaction / cross-store unfenced subsystems**.
2. Joins B06 source-level operation traces against `B03` runtime/scheduler reachability receipts and `B04` native PostgreSQL / Qdrant / Redis / restore-drill catalog proofs without fabricating any unmeasured runtime field (`UNKNOWN` / `BLOCKED` preserved fail-closed).
3. Provides hermetic, PII-zero verification harnesses and negative tests that prove both the positive contract invariants (e.g., `visa_engine`, `reconcile_service`, `garuda_orders`, `wa_outbox_worker`, `kbli_notebook`, `intake/writer`, `naga_persistence`) and the 7 counterexamples (`CE-B06-01` through `CE-B06-07` in `ANALYSIS.md`).

### 1.2 Explicit Non-Goals

- No edits to off-limits files (`zantara_core.py`, `fly.toml`, `.env*`, `apps/bali-intel-scraper/backend/db/migrations/env.py`, curated datasets, or WR2 queue JSONs).
- No speculative promotion of `BLOCKED_DISCOVERY` rows to `VERIFIED` where `B03` runtime principal identity or `B04` native store/restore verification is still `UNKNOWN`, `FAIL`, or `CANNOT-VERIFY`.
- Zero transcription of client PII, OSINT, or credentials into any contract record, fixture, or receipt.

---

## 2. Proposed Artefacts & Architecture (Synthesis / Execution Stage)

During the subsequent authorised synthesis/execution stage, B06 proposes to materialise the following deterministic artefacts under `research/operations/udb-wave8/B06/`:

1. **`domain-operation-contracts.json` & `domain-operation-contracts.csv`**:
   - Schema locked to `BATTLE.md:14-18`:
     - **Frozen fields (8)**: `consumer_id`, `operation_id`, `store_id`, `source_version`, `evidence_timestamp`, `evidence_sha256`, `status`, `unknowns`
     - **Operation instance fields (11)**: `principal`, `role`, `tenant`, `authorization`, `transaction`, `effects`, `retries`, `idempotency`, `failure`, `retention`, `recovery`
     - **Domain & Lineage Metadata**: `research_line_id` (`D04`–`D10`), `entry_point`, `source_line_span`, `counterexample_id` (if applicable), `b03_reachability_ref`, `b04_catalog_ref`.
2. **`b06_contract_verifier.py` (Hermetic AST + Receipt Verifier)**:
   - Deterministically parses the pinned source files across `D04`–`D10` at `source_version = 8061c88e0c43dd42e735fd012f9ed072df3ef3d6` and cross-checks:
     - Every `consumer_id` exists in `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv` (`sha256: c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118`).
     - Transaction boundary markers (`conn.transaction()`, `FOR UPDATE`, `SKIP LOCKED`, `pg_try_advisory_lock`, `pg_advisory_xact_lock`, `lock_phone_cores`) match the declared `transaction` and `idempotency` fields in `domain-operation-contracts.json`.
     - Cross-checks `REAL-RUN-RECEIPT.json` (`sha256: 9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d`) so any operation touching `clients` (`FAIL`) or `conversations` (`CANNOT-VERIFY`) cannot be marked `COMPLETE_VERIFIED` until the underlying restore invariant is green.
3. **`test_b06_domain_contracts.py` (Unit, Negative & Integration Test Suite)**:
   - **Positive Contract Tests**:
     - Verify `D04` `visa_engine/evaluate_path.py`, `D05` `accounting/reconcile_service.py` & `garuda_orders/repository.py`, `D06` `wa_outbox_worker.py`, `D07` `kbli_notebook.py`, `D08` `intake/writer.py` & `intake/crm_delivery.py`, and `D10` `research_os/naga_persistence.py` satisfy all 19 `BATTLE.md` contract fields with explicit source line spans and SHA-256 hashes.
   - **Negative / Falsification Tests (Enforcing Fail-Closed Discipline)**:
     - **NT-01 (`CE-B06-01`)**: Rejects any attempt to score `clients` operations as restore-verified while `REAL-RUN-RECEIPT.json` records `clients.verdict == "FAIL"` (`VIOLATION: 1`), and flags out-of-transaction `CRMAuditor._flush_buffer` writes (`client_core.py:480-523,721`).
     - **NT-02 (`CE-B06-02`)**: Flags `InvoiceAutomationService.trigger_on_sending_invoice` (`invoice_service.py:62-286`) as `CROSS_STORE_UNFENCED` because external HTTP email and Google Drive writes precede `_update_practice_with_invoice` without an idempotency reservation key.
     - **NT-03 (`CE-B06-03`)**: Rejects promoting `D06` `conversations` consumers (`src_4c49b82438955ab7`, `src_5a7d24691f6be8c9`, `src_d88734f39509787b`) to `COMPLETE_VERIFIED` while `REAL-RUN-RECEIPT.json` records `conversations.verdict == "CANNOT-VERIFY"` (`UNMEASURED_CHECK: 1`).
     - **NT-04 (`CE-B06-04`)**: Rejects marking `D07` Qdrant-backed operations as model-binding proved while `STATE.json` records `qdrant_model_binding_proved == false`.
     - **NT-05 (`CE-B06-05`)**: Verifies `D08` `crm_delivery.py` fail-closed behavior (`identity_unresolved`) when `_PHONE_DUP_OWNERS_SQL` detects duplicate phone cores across `phone_normalized`, `phone`, or `whatsapp`.
     - **NT-06 (`CE-B06-06`)**: Flags `D09` `WarRoomRepository.create_draft`/`create_post` provenance tagging (`_tag_provenance_safe`, `war_room/repository.py:122-135`) and `news.py:_enqueue_post_publish` (`news.py:20-45`) as `BEST_EFFORT_OUT_OF_TX`.
     - **NT-07 (`CE-B06-07`)**: Flags `D10` `MemoryServicePostgres` (`memory_service_postgres.py:83-92,175-193`) as `VOLATILE_FALLBACK_RISK` due to its standalone connection pool and silent fallback to `self.memory_cache`.

---

## 3. Sibling Block Interfaces (`B03`, `B04`, `B05`, `B07`)

| Sibling Block                       | Interface Direction | Concrete Handshake                                                                                                                                                                                                                                                                                              |
| :---------------------------------- | :------------------ | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`B03` (Runtime / Daemons)**       | `B03 -> B06`        | Supplies verified `principal`, process registration (`router_registration.py`, `main_api.py` schedulers, `launchd` plists such as `com.balizero.post-publish-poller`, `com.matagaruda.invalidation-sweep`, `com.nuzantara.kbli-oss-refresh.weekly`), and active consumer denominator filtering for `D04`–`D10`. |
| **`B04` (Native Stores & Restore)** | `B04 -> B06`        | Supplies PostgreSQL role/grant bindings (`POOL-FACTORY-SOURCE.json` -> `role`), exact sub-check breakdown for `clients` (`VIOLATION: 1`) and `conversations` (`UNMEASURED_CHECK: 1`) in `restore_drill_verify.py`, and read-only Qdrant Cloud / Redis metadata.                                                 |
| **`B05` (Consumer Contracts)**      | `B05 <-> B06`       | B06 emits operation rows conforming 1:1 to `B05`'s 8 frozen fields + 11 operation instance fields (`BATTLE.md:14-18`).                                                                                                                                                                                          |
| **`B07` (Reconciliation & Gate)**   | `B06 -> B07`        | B06 hands off `domain-operation-contracts.json`, the 7 counterexamples (`CE-B06-01`..`07`), and cross-store drift vectors (PG↔Drive, PG↔Qdrant, Pro-PG↔Fly-PG, PG↔MemoryCache) for Wave 8 gate synthesis.                                                                                                       |

---

## 4. DUX-REQUESTS (Read-Only Computations Needed Before Synthesis)

Because `run_command` is disabled in this analysis window (`DUX-NOTE-ANALYSIS.md:13-22`), the following read-only, aggregate/hashed computations are requested from the BLUE Dux to pin missing evidence before B06 synthesis:

### `DUX-REQ-B06-01`: Exact Domain Row & Disposition Breakdown in `consumer-matrix.csv` for `D04`–`D10`

- **id**: `DUX-REQ-B06-01`
- **Command / Script**:
  ```bash
  python3 -c '
  import csv, collections, hashlib, json, pathlib
  p = pathlib.Path(".agent-receipts/udb-wave8-inputs/consumer-matrix.csv")
  counts = collections.Counter()
  by_domain_disp = collections.defaultdict(collections.Counter)
  with p.open() as f:
      for r in csv.DictReader(f):
          dom = r.get("domain_heuristic", "UNKNOWN")
          disp = r.get("disposition", "UNKNOWN")
          status = r.get("contract_coverage_status", "UNKNOWN")
          counts[dom] += 1
          by_domain_disp[dom][f"{disp}|{status}"] += 1
  print(json.dumps({"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "domain_counts": dict(counts), "by_domain_disposition": {k: dict(v) for k, v in by_domain_disp.items()}}, indent=2, sort_keys=True))
  '
  ```
- **Inputs**: `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv` (`sha256: c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118`)
- **Expected Output Shape**: JSON object with `sha256`, `domain_counts` (`dict[str, int]`), and `by_domain_disposition` (`dict[str, dict[str, int]]`). Zero row content or PII.
- **Why It Matters**: Pins the exact deterministic denominator of `consumer-matrix.csv` rows per `domain_heuristic` (`crm_cases`, `visa_company_tax_property`, `pricing_payments_accounting`, `conversations_channels`, `knowledge_rag`, `document_ingestion`, `editorial`, `research_intelligence`, `agent_workflows`) so B06 synthesis can account for 100% of domain rows without estimation.

### `DUX-REQ-B06-02`: Sub-Check Disaggregation of `clients` (`FAIL`) and `conversations` (`CANNOT-VERIFY`) from Mini Restore Drill

- **id**: `DUX-REQ-B06-02`
- **Command / Script**:
  ```bash
  python3 scripts/ci/restore_drill_verify.py --fixture scripts/tests/fixtures/restore_drill/healthy.json --json
  ```
  _(Plus read-only inspection of the Mini restore drill raw JSON output or re-running the two aggregate `SELECT jsonb_build_object(...)` queries from `scripts/ci/restore_drill_verify.py:207-229` against the isolated Mini restore target database, emitting only boolean/integer check counts.)_
- **Inputs**: `scripts/ci/restore_drill_verify.py:207-229` and the isolated Mini restore drill database referenced in `.agent-receipts/udb-wave8-inputs/REAL-RUN-RECEIPT.json:15-74`.
- **Expected Output Shape**: Aggregate JSON counts only: `{"clients": {"client_type_unknown": <int>, "lead_metadata_not_object": <int>}, "conversations": {"messages_not_json_array": <int_or_error_class>}}`. Zero client rows, zero PII.
- **Why It Matters**: Resolves Unknown #2 and Unknown #3 in `ANALYSIS.md` by identifying whether `clients` failed on `client_type_unknown` or `lead_metadata_not_object`, and why `_CONVERSATIONS_VIOLATIONS_SQL` returned `UNMEASURED_CHECK: 1` on Mini restore.

### `DUX-REQ-B06-03`: Pool-Factory Actor & Grant Join for B06 Backend Routers/Services

- **id**: `DUX-REQ-B06-03`
- **Command / Script**:
  ```bash
  python3 -c '
  import csv, collections, json, pathlib
  p = pathlib.Path(".agent-receipts/udb-wave8-inputs/consumer-matrix.csv")
  b06_prefixes = (
      "apps/backend-rag/backend/app/routers/",
      "apps/backend-rag/backend/services/",
      "apps/bali-intel-scraper/",
      "apps/cell/",
      "packages/cell-core/",
      "packages/research-os-core/",
  )
  summary = collections.Counter()
  with p.open() as f:
      for r in csv.DictReader(f):
          ep = r.get("entry_point", "")
          if ep.startswith(b06_prefixes):
              key = f"{r.get(\"join_source\",\"NONE\")}|{r.get(\"join_status\",\"NONE\")}"
              summary[key] += 1
  print(json.dumps(dict(summary), indent=2, sort_keys=True))
  '
  ```
- **Inputs**: `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv`
- **Expected Output Shape**: Aggregate JSON map of `join_source|join_status -> integer count` across B06 source prefixes.
- **Why It Matters**: Quantifies the exact number of B06 source files that already have `POOL-FACTORY-SOURCE.json` or `SOURCE-REEXPORT-JOIN.json` bindings vs. `NOT_ENRICHED_THIS_PHASE`, enabling a clean join with `B04` and `B05`.

## Adversarial review

Scoped Codex document review, parent receipt [`R1-DOCUMENT-REVIEW.json`](R1-DOCUMENT-REVIEW.json) (observed 2026-10-15T16:54:26Z): `HISTORICAL_OR_PENDING_PROPOSAL_NOT_ADMITTED` for this file's bytes with SHA256 `236f3745e7ddb421be06abd65dd4481356634cac3159775d35758e798e71b6ea` at base `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`. Bounded excerpts only: not a full document or code review, not implementation approval, not the final BLUE gate. Requested seat Astra 6/xhigh; effective runtime identity not observed. Edits after the reviewed bytes (corrections, addendum) apply its findings and were not re-reviewed.
