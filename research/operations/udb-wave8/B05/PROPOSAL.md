---
adversarial_review: codex
reviewed_source_sha256: "945cbf17ea05efd8914b1e650c6ab82548011c0eae3cfbe28976f34e0b83e508"
review_disposition: REVIEWED_PARTIAL_HISTORICAL_DESIGN
---

> HISTORICAL PROPOSAL: dotted store IDs and PARTIAL_VERIFIED examples below are superseded. Use the delivered colon-delimited grammar, current status vocabulary and corrected23-contract ledger. This document grants no execution or closure authority.

# B05 PROPOSAL — Effective Operation Contracts Schema, Validator & Instantiation Plan

- **Campaign**: `universal-db-wave8-20261015`
- **Block**: `B05` — Effective operation contracts
- **Host / Worktree**: `[Mini]` · `<block worktree>`
- **Base Commit**: `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`
- **Stage**: `ANALYSIS` (Proposal for Dux review; stops before code mutation)

---

## 1. Canonical Operation-Contract Schema (`B05` Specification)

To satisfy [`BATTLE.md:9-10`](/research/operations/udb-wave8/B05/BATTLE.md#L9-L10) and [`ASTRA-ADVICE.md:4-11`](/.agent-receipts/udb-wave8-inputs/ASTRA-ADVICE.md#L4-L11), every operation contract instance is serialized as a deterministic JSON object with **19 top-level keys**: the **8 frozen sibling base fields** (unchanged) plus the **11 B05 operation-instance extension fields**.

### 1.1 Top-Level Contract Shape

```json
{
  "consumer_id": "src_6ad3cb3fa4349521",
  "operation_id": "op.pg.conversations.save_messages",
  "store_id": "pg.primary.public.conversations",
  "source_version": "8061c88e0c43dd42e735fd012f9ed072df3ef3d6",
  "evidence_timestamp": "2026-10-15T06:24:09Z",
  "evidence_sha256": "<sha256-of-pinned-evidence-bundle>",
  "status": "PARTIAL_VERIFIED",
  "unknowns": [
    "runtime_principal_to_db_role_binding",
    "redis_cache_invalidation_live_auth_blocked",
    "real_restore_conversations_json_vs_jsonb_unmeasured"
  ],
  "principal": {
    "service_identity": "apps/backend-rag",
    "entrypoint": "backend.db.repositories.conversation_repository:ConversationRepository.save_messages",
    "runtime_surface": "UNKNOWN",
    "verification_status": "PARTIAL_SOURCE"
  },
  "role": {
    "db_role": "UNKNOWN",
    "candidate_roles": ["backend_rag_v2"],
    "required_privileges": ["SELECT", "INSERT", "UPDATE"],
    "grant_verified": false
  },
  "tenant": {
    "isolation_mode": "USER_AND_SESSION_SCOPED",
    "scope_keys": ["user_id", "session_id"],
    "rls_enforced": false,
    "default_tenant": null
  },
  "authorization": {
    "pre_execution_gates": ["caller_jwt_or_internal_service_context"],
    "db_policy_functions": [],
    "fail_closed_on_violation": false
  },
  "transaction": {
    "boundary": "EXPLICIT_CONN_TRANSACTION",
    "isolation_level": "READ_COMMITTED_DEFAULT",
    "locking_mode": "NONE",
    "lock_timeout_ms": null,
    "atomicity_scope": "SINGLE_STORE_PG_ONLY"
  },
  "effects": {
    "primary_writes": [
      {"table": "public.conversations", "ops": ["SELECT", "INSERT", "UPDATE"]}
    ],
    "transactional_outbox_or_journal": [],
    "non_transactional_side_effects": [
      {
        "store_id": "redis.local.zantara_cache",
        "mechanism": "@cache_invalidating('zantara:conversations:*')",
        "fires_on_masked_error": true
      }
    ]
  },
  "retries": {
    "caller_retry_policy": "NONE_IN_REPOSITORY",
    "db_retry_on_serialization_or_deadlock": false,
    "max_attempts": 1
  },
  "idempotency": {
    "mechanism": "ADJACENT_MESSAGE_EQUALITY_DEDUP",
    "key_fields": ["session_id", "messages[-1]"],
    "concurrency_safe": false,
    "notes": "No advisory lock or SELECT FOR UPDATE in current branch conversation_repository.py:59-136; concurrent saves on same session_id can race."
  },
  "failure": {
    "db_exception_behavior": "SWALLOWED_RETURNS_SENTINEL",
    "sentinel_return_value": null,
    "policy_exception_behavior": "NONE",
    "quarantine_or_dead_letter": null
  },
  "retention": {
    "floor_days": 1826,
    "policy_module": "apps/backend-rag/backend/core/retention_policy.py:45",
    "clock_delete_env_gate": "CONVERSATION_RETENTION_ALLOW_CLOCK_DELETE",
    "clock_delete_default_enabled": false,
    "subject_erasure_exempt": true
  },
  "recovery": {
    "synthetic_pg17_status": "PASS",
    "real_restore_status": "CANNOT-VERIFY",
    "real_restore_receipt_sha256": "9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d",
    "real_restore_blocker": "UNMEASURED_CHECK: conversations.messages is json, verifier called jsonb_typeof(messages)"
  }
}
```

### 1.2 Frozen ID Non-Negotiation Rule (`ASTRA-ADVICE.md:5-11`)

- `consumer_id` MUST match an existing `row_id` in `consumer-matrix.csv` (e.g., `src_6ad3cb3fa4349521`, `src_63bd7ca41f966a78`, `src_5ebca16bb2011dc6`, `mini.restore_drill`) or a canonical `B03`-minted consumer ID.
- `operation_id` follows the deterministic naming convention `op.<store_kind>.<object_or_table>.<verb_or_method>` and is mapped 1-to-N against `consumer_id` without altering `consumer_id`.
- `store_id` binds directly to `B04` store identifiers (`pg.primary.public.<table>`, `redis.local.<namespace>`, `qdrant.local.<collection>`, `sqlite.local.<file>`).

---

## 2. Fail-Closed Closure & Validation Rules

The B05 validator enforces five strict invariants so that partial or drifted contracts can never inflate `complete_operation_contracts`:

1. **Rule V1 — Exact 19-Key Schema Parity**:
   - Missing any of the 8 frozen base fields or 11 B05 extension fields raises `ContractSchemaError`.
2. **Rule V2 — Fail-Closed `COMPLETE` Gate**:
   - A contract instance may have `status == "COMPLETE"` **if and only if**:
     - `unknowns == []` (empty list),
     - `principal.verification_status == "VERIFIED_RUNTIME"`,
     - `role.grant_verified is True` (privilege set confirmed against `B04` catalog grant pairs for `role.db_role`),
     - `recovery.real_restore_status == "PASS"` (or store is explicitly non-persistent/ephemeral with documented rebuild proof), and
     - `evidence_sha256` and `source_version` are non-empty and match pinned current-branch artifacts.
   - If `status == "COMPLETE"` while `len(unknowns) > 0` or any sub-gate above is false, the validator rejects the contract (`ContractClosureViolation`).
3. **Rule V3 — Counterexample Detection Gate (`INVALID_COUNTEREXAMPLE`)**:
   - If a contract claim contradicts pinned current-branch source or live catalog/restore evidence (such as claiming `advisory_lock` or `FOR UPDATE` on `ConversationRepository.save_messages` where `conversation_repository.py:59-136` has neither, or claiming `real_restore_status == "PASS"` on `clients` where `REAL-RUN-RECEIPT.json:34` is `"FAIL"`), the validator classifies the claim as `INVALID_COUNTEREXAMPLE` and blocks promotion.
4. **Rule V4 — Masked-Failure & Non-Transactional Effect Disclosure**:
   - Whenever a repository method catches `Exception` and returns a sentinel (`None`, `0`, `False`) while decorated with `@cache_invalidating`, the contract MUST set `failure.db_exception_behavior = "SWALLOWED_RETURNS_SENTINEL"` and `effects.non_transactional_side_effects[*].fires_on_masked_error = True`.
5. **Rule V5 — Retention Policy Dual-Door Rule**:
   - Operations on retention-governed tables (`conversations`, `visa_decisions`, `garuda_orders`) MUST distinguish clock-driven retention (`floor_days = 1826` or `visa_decision_retention_policies` check) from data-subject erasure (`UU PDP Art. 43`).

---

## 3. Proposed Deliverable Scope for Execution Stage (Post-Dux Approval)

Once the Dux reviews this proposal and provides the Definitive Synthesis / Execution go-ahead, B05 will implement a tight, self-contained verification package within the B05 perimeter:

### 3.1 Proposed Files to Create / Update in Execution Stage

1. **`research/operations/udb-wave8/B05/contracts_schema.py`** (or under `scripts/udb_wave8/b05_contracts.py` per Dux placement instruction):
   - Pure-Python (stdlib `dataclasses`, `json`, `hashlib`, `pathlib`, `ast`) schema & fail-closed validator implementing the 8 frozen + 11 B05 fields and Rules `V1`–`V5`.
   - AST/source verifier that inspects current-branch Python/SQL files (e.g., `conversation_repository.py`, `retention_policy.py`, `284_garuda_orders.sql`, `279_research_os_contract_core.sql`, `restore_drill_verify.py`) to verify locking, transaction boundaries, exception handling, and triggers directly from disk.
2. **`research/operations/udb-wave8/B05/operation-contracts.json`**:
   - Canonical machine-readable ledger of instantiated operation contracts across the 5 verified archetypes:
     1. `op.pg.conversations.save_messages` (`consumer_id: "src_6ad3cb3fa4349521"`) — `PARTIAL_VERIFIED` + explicit counterexample refuting the stale advisory-lock claim in `consumer-matrix.csv:545`.
     2. `op.pg.conversations.cleanup_old_conversations` (`consumer_id: "src_6ad3cb3fa4349521"`) — `PARTIAL_VERIFIED` with `RETENTION_MIN_DAYS = 1826`, `CONVERSATION_RETENTION_ALLOW_CLOCK_DELETE`, pre-try `RetentionPolicyViolation`, and in-try masked `0` return.
     3. `op.pg.conversations.anonymize_user_data` (`consumer_id: "src_6ad3cb3fa4349521"`) — `PARTIAL_VERIFIED` with `RETENTION_MIN_DAYS = 1826`, no explicit `conn.transaction()`, and masked `0` return.
     4. `op.pg.garuda_orders.transition_and_outbox` (`consumer_id: "src_63bd7ca41f966a78"`) — `PARTIAL_VERIFIED` binding `garuda_orders` state transition trigger (`trg_guard_garuda_order_state_transition`), `active_garuda_order_policy_available`, `garuda_order_idempotency`, `garuda_payment_inbox`, `garuda_order_journal`, and `garuda_order_outbox`.
     5. `op.pg.research_os_objects.append_contract_record` (`consumer_id: "src_5ebca16bb2011dc6"`) — `PARTIAL_VERIFIED` binding `tenant = 'bali-zero'`, `object_hash CHAR(64)`, and `research_os_reject_append_only_mutation`.
     6. `op.pg.restore_drill.verify_critical_tables` (`consumer_id: "mini.restore_drill"`) — `PARTIAL_VERIFIED` binding the read-only verifier contract to `REAL-RUN-RECEIPT.json` (`visa_decisions`/`events_outbox`/`visa_decision_retention_policies` = `PASS`, `clients` = `FAIL`, `conversations` = `CANNOT-VERIFY`).
3. **`research/operations/udb-wave8/B05/test_b05_operation_contracts.py`**:
   - Deterministic `pytest` suite covering:
     - **Positive tests**: Schema validation of all 19 fields, deterministic SHA-256 evidence pinning, AST verification of `conversation_repository.py` and `retention_policy.py`.
     - **Negative / Counterexample tests**:
       - Rejecting `status = "COMPLETE"` when `unknowns` is non-empty (`Rule V2`).
       - Rejecting `status = "COMPLETE"` when `recovery.real_restore_status` is `"FAIL"` (`clients`) or `"CANNOT-VERIFY"` (`conversations`) (`Rule V2`).
       - Rejecting the stale `consumer-matrix.csv:545` claim (`two-int advisory session lock; row lock`) against current-branch `conversation_repository.py:59-136` (`Rule V3`).
       - Rejecting any contract that mutates or omits a frozen sibling base field (`Rule V1`).

---

## 4. Sibling Integration Checkpoints (`B03`, `B04`, `B06`, `B07`)

| Sibling Block | Input Consumed by B05 | Output Provided by B05 | Frozen Join Key |
| :--- | :--- | :--- | :--- |
| **`B03`** (Active Consumer Denominator) | Active vs. dormant/non-consumer disposition for each `consumer_id` + runtime pool/entrypoint binding | Operation-level contract coverage status per active `consumer_id` | `consumer_id` |
| **`B04`** (Store / Catalog / Lineage) | Canonical `store_id`, live PostgreSQL role-grant pairs (`4,628`), trigger/function catalog (`112`/`85`) | Required privilege set (`role.required_privileges`) & trigger invariant bindings per operation | `store_id` |
| **`B06`** (Domain Writers / State Machines) | Writer inventory and state-transition invariants for domain tables (`garuda_orders`, `clients`, `visa_decisions`, `conversations`) | Bound `transaction`, `effects`, `idempotency`, `failure`, and `retention` sub-contracts | `operation_id`, `store_id` |
| **`B07`** (Workflows / Cron / Jobs / Events) | Scheduled caller registrations (`job_*`, `cron_*`) and outbox/inbox dispatch chains | End-to-end caller-to-operation `retries`, `idempotency`, and dead-letter/quarantine contracts | `consumer_id`, `operation_id` |

---

## DUX-REQUESTS

Because `run_command` is disabled in this non-interactive `ANALYSIS` session (`DUX-NOTE-ANALYSIS.md:18-26`), B05 requests the BLUE Dux to execute or provide the following read-only computations before Definitive Synthesis:

1. **`DUX-B05-01` — Full Aggregate Breakdown of `consumer-matrix.csv` (6,030 rows)**:
   - Run a read-only aggregation over `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv` grouped by `(lead_type, store_kind, contract_coverage_status, disposition)` and return the exact counts so B05 can cite the full 6,030-row distribution without sampling error.
2. **`DUX-B05-02` — SHA-256 Hash Pins of Target Source Files on Base Commit `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`**:
   - Compute `shasum -a 256` for:
     - `apps/backend-rag/backend/db/repositories/conversation_repository.py`
     - `apps/backend-rag/backend/core/retention_policy.py`
     - `apps/backend-rag/backend/db/migrations_v2/279_research_os_contract_core.sql`
     - `apps/backend-rag/backend/db/migrations_v2/284_garuda_orders.sql`
     - `scripts/ci/restore_drill_verify.py`
   - So each contract instance in `operation-contracts.json` can populate `evidence_sha256` with an exact, verifiable hash pin.
3. **`DUX-B05-03` — Read-Only Extract of Catalog Grants & Pool Factory Bindings for Core Tables**:
   - If the Wave 7 raw evidence artifacts referenced in `consumer-matrix.csv` (`LIVE-DB-METADATA.json`, `POOL-FACTORY-SOURCE.json`, `SOURCE-REEXPORT-JOIN.json`, `SYNTHETIC-PG-RESULT.json`) exist in the parent campaign store or sibling worktrees (`B03`/`B04`), provide the read-only slice of PostgreSQL `role_grants` for `conversations`, `clients`, `visa_decisions`, `events_outbox`, `visa_decision_retention_policies`, `garuda_orders`, and `research_os_objects` (confirming whether `backend_rag_v2` currently holds `SELECT/INSERT/UPDATE/DELETE` on each).
4. **`DUX-B05-04` — Active Writer Consumer IDs from `B06` / `B07` for `garuda_orders` and `research_os_objects`**:
   - Confirm whether active Python/TypeScript runtime writer `consumer_id` rows exist in `consumer-matrix.csv` for `garuda_orders` (beyond migration `src_63bd7ca41f966a78`) and `research_os_objects` (beyond migration `src_5ebca16bb2011dc6`), or if they remain DDL-only (`PARTIAL_SOURCE`) on commit `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`.
5. **`DUX-B05-05` — Execution-Stage Pytest & Receipt Runner**:
   - In the subsequent execution stage, run `pytest research/operations/udb-wave8/B05/test_b05_operation_contracts.py -q` and capture the test receipt SHA-256 for the B05 Evidence Pack.


## Adversarial review

Independent Codex document review: `REVIEWED_PARTIAL_HISTORICAL_DESIGN`. The reviewed original bytes have SHA256 `945cbf17ea05efd8914b1e650c6ab82548011c0eae3cfbe28976f34e0b83e508` at candidate `3cd10ccec8f6c47ab19629bf9c48cc0e5eb9ed7e`. See [the source-pinned review receipt](R1-DOCUMENT-REVIEW.json) for findings and limitations. The requested reviewer seat was Astra6/xhigh; its effective runtime identity was not separately echoed. This attribution records review with the stated blockers; it does not approve implementation of historical proposals, prove live role bindings, close B05, or replace the fresh BLUE exact-head Opus gate.
