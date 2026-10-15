# B05 ANALYSIS — Effective Operation Contracts

- **Campaign**: `universal-db-wave8-20261015`
- **Block**: `B05` — Effective operation contracts
- **Host / Worktree**: `[Mini]` · `<block worktree>`
- **Base Commit**: `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`
- **Stage**: `ANALYSIS` (read-only analysis + proposal; no code/test mutation outside `research/operations/udb-wave8/B05/**`)

---

## 1. Mandate & Scope Boundary

Per [`BATTLE.md`](/research/operations/udb-wave8/B05/BATTLE.md#L1-L31) and [`DUX-NOTE-ANALYSIS.md`](/research/operations/udb-wave8/B05/DUX-NOTE-ANALYSIS.md#L1-L31):

1. **Mission Objective**: Instantiate shared operation contracts against active operations covering `principal` / `role` / `tenant`, `policy` (`authorization`), `transaction`, `effects`, `retries` / `idempotency`, `failure`, `retention`, `recovery`, and `evidence` (`BATTLE.md:7`).
2. **Baseline Starting Point**: Currently `0` complete operation contracts exist (`STATE.json:11`, `REPORT.md:100`, `BATTLE.md:7`).
3. **Frozen Sibling Contract Schema (`BATTLE.md:9-10`, `ASTRA-ADVICE.md:5`)**:
   - **Frozen Base Fields (8)** — MUST be reused verbatim without redefining frozen IDs:
     `consumer_id`, `operation_id`, `store_id`, `source_version`, `evidence_timestamp`, `evidence_sha256`, `status`, `unknowns`
   - **B05 Operation-Instance Extension Fields (11)**:
     `principal`, `role`, `tenant`, `authorization`, `transaction`, `effects`, `retries`, `idempotency`, `failure`, `retention`, `recovery`
4. **Sibling Dependency Boundaries (`BATTLE.md:8`, `ASTRA-ADVICE.md:3-11`)**:
   - **`B03`**: Owns active consumer denominator, runtime consumer classification, and entry-point/pool bindings (`consumer_id`, active vs. dormant/non-consumer filtering).
   - **`B04`**: Owns store, catalog, schema, and migration lineage (`store_id`, relation/grant/trigger catalog truth).
   - **`B06`**: Owns domain writers, invariants, and state-machine transition rules (`garuda_orders`, `visa_decisions`, `clients`, `conversations`, etc.).
   - **`B07`**: Owns workflows, LaunchAgents, crons, background jobs, and event/outbox dispatch chains.
   - **`B05` (this block)**: Owns the operation-contract schema, validation semantics, failure-mode taxonomy, and concrete operation-contract instances joining `consumer_id × operation_id × store_id`, without mutating frozen sibling IDs.

---

## 2. Verified Facts (Pinned by Input SHA-256 and `file:line`)

### 2.1 Frozen Input Manifest & Baseline Metrics

All read-only inputs under `.agent-receipts/udb-wave8-inputs/` are pinned in [`INPUT-MANIFEST.json`](/.agent-receipts/udb-wave8-inputs/INPUT-MANIFEST.json#L1-L13):

| Input Artifact | Pinned SHA-256 (`INPUT-MANIFEST.json`) | Key Verified Facts |
| :--- | :--- | :--- |
| [`ASTRA-ADVICE.md`](/.agent-receipts/udb-wave8-inputs/ASTRA-ADVICE.md#L1-L12) | `72f349f285bc681013b67ad1d25cdad54d3d4478080dc1f5e7e0512dd9e1fdb8` | Mandates shared canonical JSON schema on `consumer_id`, `operation_id`, `store_id`; forbids peer-to-peer schema negotiation (`ASTRA-ADVICE.md:4-11`). |
| [`STATE.json`](/.agent-receipts/udb-wave8-inputs/STATE.json#L1-L134) | `caaebbbac9703bf5ebd5f7624b8a2dd6759a2e508703f311cecffebf1c0967d4` | `baseline_leads_preserved: 6029`, `additional_runtime_observations: 1`, `union_lead_rows: 6030`, `active_consumer_denominator: "UNKNOWN"`, `complete_operation_contracts: 0`, `complete_root_classes: 0` (`STATE.json:8-13`). |
| [`FINAL-BLUE-GATE.json`](/.agent-receipts/udb-wave8-inputs/FINAL-BLUE-GATE.json#L1-L128) | `b9d284e1dba9e87ad340cbd4076061e7a35a93fdf8bc1c910340e6099d711856` | Prior campaign `universal-db-wave7-20261015` received `FINAL_VERDICT: "PASS"` for honest fail-closed ledger preservation while explicitly recording `complete_operation_contracts: 0` and `overall_campaign_state: "PARTIAL_NO_COMPLETE_CELLS"` (`FINAL-BLUE-GATE.json:3, 25-32`). |
| [`REAL-RUN-RECEIPT.json`](/.agent-receipts/udb-wave8-inputs/REAL-RUN-RECEIPT.json#L1-L84) | `9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d` | Real PostgreSQL backup restore drill on `Mini` (`2026-10-15T06:24:09Z`, `elapsed_seconds: 87.337`) produced aggregate `status: "CANNOT-VERIFY"` (`REAL-RUN-RECEIPT.json:14, 24, 27`). |
| [`REPORT.md`](/.agent-receipts/udb-wave8-inputs/REPORT.md#L1-L146) | `d289fb8660a6bd634cb7785fef3a8c0b47ceefe82463d134c4bbf66dc0563e9a` | Summarizes 5-wave execution: 6,030 union rows, 0 complete operation contracts, 0 complete root classes (`D00`–`D17`), and synthetic vs. real restore divergence (`REPORT.md:90-132`). |
| [`research-lines.csv`](/.agent-receipts/udb-wave8-inputs/research-lines.csv#L1-L20) | `1b3d1f31df997500975311d3f49cbd3a50346c2fa7d27f49cbd3a50346c2fa7d` (manifest: `1b3d1f31df997500975311d3f49cbd3a50346c2fa7d27f45ff808c7203654c10`) | 18 root research lines (`D00`–`D17`); statuses are `PARTIAL` (`D00`–`D04`, `D07`, `D10`–`D11`, `D14`), `PARTIAL_SOURCE` (`D05`–`D06`, `D08`–`D09`, `D12`–`D13`, `D17`), and `OPEN_WITH_LEADS` (`D15`, `D16`) (`research-lines.csv:2-19`). |
| [`consumer-matrix.csv`](/.agent-receipts/udb-wave8-inputs/consumer-matrix.csv#L1-L50) | `c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118` | 6,031 lines total (1 header + 6,030 data rows) across 30 columns (`consumer-matrix.csv:1`). |

### 2.2 Observed Store, Catalog, and Runtime Facts in `STATE.json` and `consumer-matrix.csv`

1. **PostgreSQL Catalog Observer (`Pro` local read-only observer, `STATE.json:14-23`)**:
   - Observed `557` relations (`STATE.json:18`), `13` database actors/roles (`STATE.json:19`), `4,628` role-grant pairs (`STATE.json:20`), `112` triggers (`STATE.json:21`), `85` functions (`STATE.json:22`), and `240` foreign keys (`STATE.json:23`).
2. **Non-Relational & External Store Observations (`STATE.json:41-55`, `REPORT.md:41-49`)**:
   - **Qdrant (`Pro` local HTTP `:6333`)**: `2` collections observed with hashed names (`STATE.json:42`).
   - **Redis (`Pro` and `Mini`)**: Local TCP `:6379` reachable, but unauthenticated `INFO` returned `-NOAUTH Authentication required.` (`STATE.json:44-47`).
   - **Fly.io (`fly_pro`)**: `status: "CANNOT-VERIFY"`, `reason: "unauthorized_token"` (`STATE.json:48-51`).
   - **SQLite (`Pro` local)**: `82` candidates scanned; `70` accessible, `12` empty (`0` bytes) (`STATE.json:52-55`).
3. **Consumer Matrix Column Schema (`consumer-matrix.csv:1`)**:
   - Each row carries 30 columns: `row_id`, `lead_type`, `host_or_surface`, `source_path_or_unit`, `symbol_or_command`, `inferred_domain`, `store_kind`, `target_store_or_collection`, `object_or_table`, `operation_mode`, `principal`, `role`, `auth_mode`, `tenant_or_scope`, `entrypoint`, `runtime_registration`, `schedule_or_trigger`, `transaction_boundary`, `idempotency_or_retry`, `failure_mode`, `retention_or_ttl`, `recovery_dependency`, `latency_availability`, `evidence_class`, `verification_method`, `contract_coverage_status`, `disposition`, `unknown_reason`, `evidence_refs`, `notes`.
4. **Heterogeneous Row Classes in `consumer-matrix.csv`**:
   - Source code leads: `src_*` across `.github/workflows/*`, `apps/backend-rag/**`, `apps/mouth/**`, `scripts/**`, migrations, and tests (`consumer-matrix.csv:2-1050`).
   - Operational runtime leads: `job_pro_*`, `job_mini_*`, `job_M5_*`, `cron_pro_*`, `cron_mini_*`, `engine_pro_*`, `engine_mini_*`, `engine_M5_*`, plus `mini.restore_drill` (`consumer-matrix.csv:2500-2550, 5690-6031`).
   - Unmatched / non-consumer leads preserved for auditability: `SOURCE-PATH-UNMATCHED-PRO-*` (`consumer-matrix.csv:4000-4050`), `SOURCE-TRACE-UNMATCHED-PRO-*` (`consumer-matrix.csv:5550-5642`), `CI-REGISTRATION-UNMATCHED-GH-*` (`consumer-matrix.csv:5643-5689`), and `NOTEBOOK-CONTAINER-REFERENCE-NLM-*` (`consumer-matrix.csv:5963-5998`, explicitly marked `NOT_DATABASE_CONSUMER_IDENTITY`).

### 2.3 Source-Level Operation Mechanics on Current Worktree Branch (`8061c88e0c43dd42e735fd012f9ed072df3ef3d6`)

1. **Conversation Persistence & Retention (`apps/backend-rag/backend/db/repositories/conversation_repository.py` & `apps/backend-rag/backend/core/retention_policy.py`)**:
   - `ConversationRepository` inherits from `BaseRepository` with `table_name = "conversations"` (`conversation_repository.py:21-24`).
   - `save_messages` (`conversation_repository.py:32-136`) is decorated with `@cache_invalidating("zantara:conversations:*")` (`conversation_repository.py:26-31`). Inside `try:`, it acquires a connection from `self.db_pool` (`line 59`), enters `async with conn.transaction():` (`line 60`), runs `SELECT id, messages FROM conversations WHERE session_id = $1 ORDER BY created_at DESC LIMIT 1` (`lines 64-72`), merges messages with adjacent-element deduplication (`if not merged_messages or merged_messages[-1] != msg:`, `line 81`), and executes either `UPDATE conversations SET messages = $1, metadata = $2, updated_at = NOW() WHERE id = $3` (`lines 89-99`) or `INSERT INTO conversations (user_id, messages, created_at, updated_at, metadata, session_id) VALUES ($1, $2, NOW(), NOW(), $3, $4) RETURNING id` (`lines 108-120`). Any `Exception` is caught at `lines 134-136`, logged via `logger.error`, and returns `None`.
   - `cleanup_old_conversations` (`conversation_repository.py:183-236`) calls `enforce_retention_floor("delete_after_days", delete_after_days)` (`line 194`) and `enforce_retention_floor("anonymize_after_days", anonymize_after_days)` (`line 195`) **before** the `try:` block (`line 196`). Inside `try:`, it checks `clock_delete_allowed()` (`line 200`); only if `CONVERSATION_RETENTION_ALLOW_CLOCK_DELETE` is `"1"` or `"true"` (`retention_policy.py:50, 77-84`) does it run `DELETE FROM conversations WHERE created_at < $1` (`lines 204-209`). It then runs `UPDATE conversations SET user_id = 'anonymous_' || SUBSTRING(MD5(user_id), 1, 8), metadata = jsonb_set(...) WHERE created_at < $1 AND created_at >= $2 AND NOT (user_id LIKE 'anonymous_%')` (`lines 213-228`). Any runtime DB exception inside `try:` is caught at `lines 234-236` and returns `0`.
   - `anonymize_user_data` (`conversation_repository.py:243-290`) calls `enforce_retention_floor("older_than_days", older_than_days)` at `line 253` before `try:`, then updates rows in `conversations` without an explicit `conn.transaction()` block (`lines 259-277`), returning `0` on `Exception` (`lines 288-290`).
2. **Garuda Order State Machine, Idempotency, Inbox, Journal & Outbox (`apps/backend-rag/backend/db/migrations_v2/284_garuda_orders.sql`)**:
   - `public.garuda_orders` (`lines 36-114`) enforces a 13-state `CHECK` constraint (`lines 43-59`), invariant checks (`chk_garuda_orders_paid_requires_amount`, `chk_garuda_orders_quarantined_requires_reason`, `chk_garuda_orders_terminal_requires_timestamp`, `chk_garuda_orders_retention_anchor`, `lines 87-113`), and partial unique index `uq_garuda_orders_result_id_ref_live` on `(result_id_ref) WHERE state NOT IN ('CANCELLED', 'EXPIRED', 'REFUNDED', 'REJECTED')` (`lines 121-123`).
   - Trigger `trg_guard_garuda_order_state_transition` (`lines 128-171`) enforces monotonic `state_version = OLD.state_version + 1` (`lines 136-139`) and the closed state-transition matrix (`lines 142-160`), raising SQLSTATE `23514` on illegal transitions (`line 162`).
   - Function `public.active_garuda_order_policy_available(p_order_class, p_as_of)` (`lines 173-186`) checks `public.visa_decision_retention_policies` (`enabled = TRUE`, effective window).
   - `public.garuda_order_idempotency` (`lines 197-264`) keys customer commands by `(scope, idempotency_key_sha256, route_id, actor_key)` (`line 221`) with `ttl_expires_at` (`line 219`) and trigger `trg_guard_garuda_order_idempotency_mutation` (`lines 228-264`) rejecting `DELETE` and enforcing immutable digest/scope/ttl plus atomic completion (`response_body`, `response_status`, `completed_at`).
   - `public.garuda_payment_inbox` (`lines 272-284`) enforces `UNIQUE (provider, provider_event_id)` (`line 283`) and 4-state `outcome` (`received`, `committed`, `quarantined`, `rejected`).
   - `public.garuda_order_journal` (`lines 298-338`) enforces closed `transition_id` enum (`OP-00`..`PR-12`, `lines 305-310`), PII-free `detail` comment (`lines 314-316`), and append-only trigger raising SQLSTATE `23514` on `UPDATE OR DELETE` (`lines 325-338`).
   - `public.garuda_order_outbox` (`lines 347-365`) enforces `UNIQUE (journal_event_id, job_type)` (`line 356`) for exactly-once downstream job queueing per journal event.
3. **Research OS Contract Core (`apps/backend-rag/backend/db/migrations_v2/279_research_os_contract_core.sql`)**:
   - Defines `public.research_os_objects` (`lines 176-200`) with `tenant TEXT NOT NULL DEFAULT 'bali-zero'` (`line 196`), `contract_version TEXT NOT NULL` (`line 194`), `object_hash CHAR(64) NOT NULL` (`line 195`), and append-only trigger `research_os_reject_append_only_mutation` (`lines 120-134`) rejecting `UPDATE`/`DELETE` on `workflow_runs`, `evidence_Records`, `claim_ledger`, and `gate_verdicts`.
4. **Restore Drill Verifier & Real Restore Receipt (`scripts/ci/restore_drill_verify.py` & `REAL-RUN-RECEIPT.json`)**:
   - `restore_drill_verify.py` verifies 5 critical tables (`CRITICAL_TABLES = ("clients", "visa_decisions", "conversations", "events_outbox", "visa_decision_retention_policies")`, `lines 26-32`).
   - In `REAL-RUN-RECEIPT.json` (`lines 31-76`), the real restore run on `Mini` recorded:
     - `visa_decisions`: `PASS` (`row_count: 1`, `PASS: 5`, `REAL-RUN-RECEIPT.json:41-48`)
     - `events_outbox`: `PASS` (`row_count: 17`, `PASS: 4`, `REAL-RUN-RECEIPT.json:58-65`)
     - `visa_decision_retention_policies`: `PASS` (`row_count: 3`, `PASS: 5`, `REAL-RUN-RECEIPT.json:66-73`)
     - `clients`: `FAIL` (`row_count: 5539`, `PASS: 4`, `VIOLATION: 1`, `REAL-RUN-RECEIPT.json:32-39`)
     - `conversations`: `CANNOT-VERIFY` (`row_count: 966`, `PASS: 4`, `UNMEASURED_CHECK: 1`, `REAL-RUN-RECEIPT.json:49-56`)

---

## 3. Counterexamples & Discrepancies

### Counterexample 1 — Matrix Seam Claim vs. Actual HEAD Source (`consumer-matrix.csv:545` vs. `conversation_repository.py:32-136`)

- **Claim in Matrix**: Row `src_6ad3cb3fa4349521` (`consumer-matrix.csv:545`, `apps/backend-rag/backend/db/repositories/conversation_repository.py`, `ConversationRepository`) records:
  - `transaction_boundary = "One asyncpg transaction per save; two-int advisory session lock; row lock"`
  - `idempotency_or_retry = "Session lock serializes concurrent saves; duplicate messages still append"`
  - `latency_availability = "5 second lock timeout; failure returns None; product SLO UNKNOWN"`
  - `disposition = "ADAPTED_PARTIAL_VERIFIED"` (`SCOPED_ISOLATED_VERIFICATION_ONLY`).
- **Actual Code on Current Branch (`8061c88e0c43dd42e735fd012f9ed072df3ef3d6`)**:
  - In [`conversation_repository.py:59-136`](/apps/backend-rag/backend/db/repositories/conversation_repository.py#L59-L136), `save_messages` executes `async with self.db_pool.acquire() as conn:` and `async with conn.transaction():`, followed immediately by `SELECT id, messages FROM conversations WHERE session_id = $1 ORDER BY created_at DESC LIMIT 1` (`lines 64-72`).
  - There is **no** `pg_advisory_xact_lock` or session lock call, **no** `FOR UPDATE` row lock, and **no** `5 second lock timeout` in `conversation_repository.py`.
  - Conversely, `save_messages` **does** perform adjacent-message deduplication (`if not merged_messages or merged_messages[-1] != msg:`, `line 81`), contradicting `"duplicate messages still append"` for adjacent identical messages while remaining vulnerable to lost updates under concurrent transactions due to unserialized read-modify-write (`READ COMMITTED` `SELECT` followed by `UPDATE`).
- **Contract Implication**: Validates [`BATTLE.md:20`](/research/operations/udb-wave8/B05/BATTLE.md#L20) (*"Recheck changed source against the pinned current branch; do not blindly apply historical patches"*). Any operation contract that copies historical patch notes without verifying current-branch AST/source is invalid.

### Counterexample 2 — Silent Exception Masking + Non-Transactional Cache Side Effects (`conversation_repository.py:26-31, 134-136, 183-290`)

- **Observation**:
  - `save_messages` (`lines 26-31, 134-136`), `cleanup_old_conversations` (`lines 177-182, 234-236`), and `anonymize_user_data` (`lines 238-242, 288-290`) are all wrapped in `@cache_invalidating("zantara:conversations:*")`.
  - When a PostgreSQL query inside `try:` raises an `asyncpg` exception (e.g., deadlock, connection drop, or `InsufficientPrivilegeError`), the `except Exception:` block catches it, logs `logger.error`, and returns `None` (`save_messages`) or `0` (`cleanup_old_conversations`, `anonymize_user_data`) **without re-raising**.
  - Because the function returns normally instead of raising, callers cannot distinguish a failed DB write/delete from `"0 rows matched"`, and post-call decorator hooks execute outside the rolled-back database transaction.
- **Contract Implication**: An operation contract's `failure` and `effects` fields cannot simply state `"raises exception on DB error"`. They must explicitly model:
  1. Pre-transaction policy exceptions that propagate (`RetentionPolicyViolation` raised at `lines 194-195, 253` *above* `try:`),
  2. In-transaction DB errors that are swallowed into sentinel return values (`None` or `0`), and
  3. Cross-store side effects (`Redis` cache invalidation via `@cache_invalidating`) that execute outside the PostgreSQL transaction boundary.

### Counterexample 3 — Accidental Privilege Failure Mistaken for Retention Control (`retention_policy.py:28-36`)

- **Observation**: [`retention_policy.py:28-36`](/apps/backend-rag/backend/core/retention_policy.py#L28-L36) documents that the nightly cleanup job previously requested `delete_after_days=30, anonymize_after_days=7` while the HTTP router defaulted to `90/30`. The 7-day anonymization/deletion failed to destroy 5-year legal records **only** because the DB role `backend_rag_v2` lacked the `DELETE` privilege on `conversations`, causing the destructive SQL path to fail every night while dry-run returned `200`.
- **Contract Implication**: Proves that `role` / `authorization` (PostgreSQL table grants), `retention` (application floor `RETENTION_MIN_DAYS = 1826` + env switch `CONVERSATION_RETENTION_ALLOW_CLOCK_DELETE`), `failure` (swallowing privilege errors as `0`), and `consumer_id` (cron vs. HTTP admin router vs. per-subject JWT erasure) are tightly coupled dimensions of a single operation contract.

### Counterexample 4 — Strong SQL/DDL Invariants Without Bound Runtime Consumer or Verified Recovery (`284_garuda_orders.sql` & `REAL-RUN-RECEIPT.json`)

- **Observation**:
  - `284_garuda_orders.sql` defines complete relational state-machine, idempotency, webhook inbox, append-only journal, and transactional outbox invariants (`lines 36-365`).
  - However, in `consumer-matrix.csv:510` (`src_63bd7ca41f966a78`), this migration row has `principal = UNKNOWN`, `role = UNKNOWN`, `entrypoint = UNKNOWN`, `runtime_registration = UNKNOWN`, and `recovery_dependency = UNKNOWN`.
  - Simultaneously, on the `Mini` real-backup restore drill (`REAL-RUN-RECEIPT.json:27-56`), `clients` failed invariant checks (`VIOLATION: 1`, `status: "FAIL"`) and `conversations` could not be verified because `conversations.messages` is stored as `json` rather than `jsonb`, causing `jsonb_typeof(messages) = 'array'` to fail (`restore_drill_verify.py:130-137`, `REAL-RUN-RECEIPT.json:49-56`).
- **Contract Implication**: Neither a rich SQL schema (`284_garuda_orders.sql`) nor a passing synthetic PG17 test (`SYNTHETIC-PG-RESULT.json`, `REPORT.md:119`) is sufficient to mark an operation contract `COMPLETE`. Closure requires joining DDL invariants to an active runtime `consumer_id`, verified `principal`/`role`, and honest `recovery` status.

---

## 4. Separate Inferences (Structural Taxonomy of Contract Gaps)

*The following points are analytical inferences derived from the verified facts above, kept strictly separate from raw observations:*

1. **Why `complete_operation_contracts == 0` Across 6,030 Rows**:
   - Every row in `consumer-matrix.csv` currently represents a **single-seam observation** (either a static AST/regex file match `src_*`, a host launchd/cron registration `job_*`/`cron_*`, a local engine socket `engine_*`, or an unmatched trace).
   - An **Effective Operation Contract** is a **multi-seam join** across five layers:
     - **Layer A (Identity & Denominator — B03)**: Active runtime `consumer_id` + `entrypoint` + `runtime_registration`.
     - **Layer B (Store & Lineage — B04)**: Target `store_id` + schema/table/collection + migration lineage.
     - **Layer C (Security & Policy — B02/B05)**: Runtime `principal`, effective DB `role` (verified against the 4,628 grant pairs in `LIVE-DB-METADATA.json`), `tenant` isolation scope, and pre-execution `authorization` / policy gates.
     - **Layer D (Execution Mechanics — B05/B06/B07)**: `transaction` boundary (isolation, locking, multi-statement atomicity), `effects` (primary writes + outbox/journal/cache side effects), `retries` & `idempotency` (keys, digests, TTL, dedup scope), and `failure` semantics (raised vs. masked exceptions, quarantine, rollback).
     - **Layer E (Lifecycle & Survivability — B05/B08)**: `retention` floor/TTL/erasure path and `recovery` verification (synthetic vs. real backup restore status).
2. **Five Contract Archetypes Needed for B05 Instantiation**:
   To cover the repository's real operational patterns without inventing speculative behavior, B05 operation contracts naturally partition into five concrete archetypes:
   - **Archetype 1 — Guarded Transactional State-Machine + Idempotency + Outbox Write**: e.g., Garuda order command/transition (`garuda_orders` + `garuda_order_idempotency` + `garuda_payment_inbox` + `garuda_order_journal` + `garuda_order_outbox`, `284_garuda_orders.sql`).
   - **Archetype 2 — Append-Only Contract Ledger Write**: e.g., Research OS contract core (`research_os_objects`, `workflow_runs`, `evidence_records`, `claim_ledger`, `gate_verdicts`, `279_research_os_contract_core.sql`).
   - **Archetype 3 — Repository CRUD with Cross-Store Cache Invalidation & Masked Failure**: e.g., `ConversationRepository.save_messages` (`conversation_repository.py:32-136`).
   - **Archetype 4 — Policy-Gated Retention / Erasure Operation**: e.g., clock-driven `ConversationRepository.cleanup_old_conversations` (`conversation_repository.py:183-236` + `retention_policy.py:45-84`) vs. per-subject UU PDP Art. 43 erasure.
   - **Archetype 5 — Read-Only Verification / Audit Probe**: e.g., `restore_drill_verify.py` (`mini.restore_drill`, `consumer-matrix.csv:6031`, `REAL-RUN-RECEIPT.json`).

---

## 5. Open Unknowns & Missing Evidence

1. **Active Consumer Denominator (`B03` Dependency)**:
   - `active_consumer_denominator` is `UNKNOWN` (`STATE.json:10`). Without the exact partition of `consumer-matrix.csv` into active runtime consumers vs. dormant code, migrations, tests, and non-DB leads (`NOTEBOOK-CONTAINER-REFERENCE-NLM-*`), B05 cannot claim denominator-wide completion.
2. **Runtime Principal-to-Role Binding (`B02`/`B03`/`B04` Dependency)**:
   - While `STATE.json:19-20` confirms `13` DB actors and `4,628` grant pairs on `Pro`, the exact mapping from each active runtime service/job (`DATABASE_URL` / pool factory) to its effective PostgreSQL `role` (e.g., `backend_rag_v2`, `nuzantara_readonly`, migration owner) is not embedded in `consumer-matrix.csv` rows (where `principal` and `role` remain `UNKNOWN` on `src_*` rows).
3. **Unauthenticated Local Redis & Unauthorized Fly Probe (`Access Blockers`)**:
   - Redis on `Pro` and `Mini` rejected unauthenticated `INFO` with `NOAUTH` (`STATE.json:44-47`), leaving live TTL, eviction policy, and keyspace counts for `@cache_invalidating("zantara:conversations:*")` unverified at runtime.
   - Fly.io production inspection (`fly_pro`) is `CANNOT-VERIFY` (`unauthorized_token`, `STATE.json:48-51`).
4. **Real Backup Restore Failures on `Mini` (`Recovery Blocker`)**:
   - `REAL-RUN-RECEIPT.json:32-56` shows `clients` = `FAIL` (`VIOLATION: 1`) and `conversations` = `CANNOT-VERIFY` (`UNMEASURED_CHECK: 1` due to `json` vs. `jsonb` column type mismatch in `restore_drill_verify.py:130-137`). Until resolved, any operation contract touching `clients` or `conversations` must record `recovery.real_restore_status = "FAIL"` or `"CANNOT-VERIFY"`, never `"VERIFIED"`.
