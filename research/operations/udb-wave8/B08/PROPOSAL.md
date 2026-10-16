---
adversarial_review: codex
---

> Historical research retained for traceability. Superseded statements and commands are BLOCKED FOR IMPLEMENTATION. Current evidence is the synthesis addendum, pinned receipt and binding Dux rulings. No production/native action is authorized here.

# UDB Wave 8 — Block B08 Development & Evidence Closure Proposal

- **Mandate ID**: `universal-db-wave8-20261015`
- **Block**: `B08` — Cross-store operational guarantees (`dependencies`, `references`, `versions`, `time semantics`, `retention/erasure/security`, `recovery order`, `workload/cost`, `analytics/observability`)
- **Research Lines Mapped**: `D12`, `D14`, `D15`, `D16`, `D17` (cross-cutting `D00`, `D01`, `D11`, `D13`)
- **Mission Colour / Gear**: `BLUE` / `GEAR 3`
- **Block Lead Seat**: `Gemini 4 Argon (High)` — `EXTERNAL PREPARER, NO_DUX`
- **Appointed Dux**: `claude-opus-5-5` (`xhigh`) on `Pro`
- **Host / Worktree**: `Mini` / `/Users/nuzantara/nuzantara/.worktrees/db-udb-b08-crossstore`
- **Base Commit SHA**: `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`
- **Stage**: `ANALYSIS ONLY` (Stop after proposal; no production redesign before `S2`)

---

## 1. Desired Guarantees vs Current Facts (All 8 B08 Dimensions)

To prevent conflating current repository state with target architecture, the table below separates **Current Verified Facts** (proved in `ANALYSIS.md` §2–§3) from **Desired Operational Guarantees** and defines the **Scoped Wave 8 Verification Rule** (without proposing production redesign before `S2`).

| # | B08 Dimension | Research Line(s) | Current Verified Fact (`8061c88e0c43dd42e735fd012f9ed072df3ef3d6`) | Desired Operational Guarantee | Wave 8 Contract Verification Rule |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | **End-to-End Dependencies** | `D16`, `D00`, `D01`, `D11` | `6030` rows in `consumer-matrix.csv` are `LEAD_ONLY`; `active_consumer_denominator = "UNKNOWN"` (`STATE.json:28`); static token matching inflates touch sets (e.g., `collective_memory_service.py:12` -> `postgresql;qdrant`). | Every active runtime consumer has a closed call/store DAG (`caller -> unit -> store_set -> downstream`) with proved active status and explicit timeout/retry/tx boundaries. | A row only transitions from `LEAD_ONLY` to `CONTRACT_VERIFIED` when (a) runtime registration is proved (`launchd`/`crontab`/Fly/GH workflow), and (b) every store in `store_id` has an AST/call-site-verified operation contract. |
| **2** | **Cross-Store References** | `D17` | `154_asset_provenance.sql:25-72` uses polymorphic `asset_id TEXT` across 12 kinds (8 non-PG) and `parent_provenance_ids UUID[]` with no FK; `cell.yaml` (`consumer-matrix.csv:2517`) vs `154_asset_provenance.sql` (`386`) split authority between SQLite and PG. | Every cross-store reference declares `(source_store, source_table, source_id) -> (target_store, target_collection_or_table, target_id)` with single authoritative ownership and deterministic orphan detection. | Any cross-store reference contract must name its target store resolver and orphan-check query; unresolved polymorphic or dual-authority targets remain `PARTIAL` / `OPEN`. |
| **3** | **Versions & Lineage** | `D00`, `D13`, `D17` | PG has dual migration tables (`_schema_versions` vs `schema_migrations`, reconciled in `165_reconcile_schema_migrations_duplicates.sql`); Qdrant model binding is unproved (`qdrant_model_binding_proved = false`, `STATE.json:43`). | Every derived vector/cache/event artifact binds to an immutable `(source_version, schema_version, model_id="text-embedding-3-small", dims=1536)` lineage tuple. | Cross-store version contracts fail closed (`CANNOT-VERIFY`) if `_schema_versions` digest or Qdrant collection vector config (`size=1536`) is unproved. |
| **4** | **Time Semantics** | `D17` | PG mixes `NOW()` (`144_events_outbox.sql:11`), `statement_timestamp()` (`264:129`), and `clock_timestamp()` (`264:152`); `pg-to-organism-bridge.py:176` overwrites `ts_utc` with host receipt clock; `outbox.py:144` uses `> 1e12` ms/s heuristic; `events_outbox` lacks DB `CHECK (consumed_at >= created_at)`. | Strict separation of `event_time`, `tx_commit_time`, and `ingest_time`; monotonic `consumed_at >= created_at` enforced in DDL and bridge contracts; explicit timestamp units. | Flag any contract where `consumed_at < created_at` is possible in DDL or where host wall-clock substitutes for commit timestamp in idempotency keys (`CE-03`). |
| **5** | **Retention, Erasure & Security** | `D14` | PG Visa Oracle (`264_visa_decision_retention_policy.sql`) has fail-closed policy binding, legal hold, and DSR erasure (`lines 982-1192`), but `outbox.py:334, 429` orphans unconsumed rows `>60m`, `llm_cost_recorder.py:58` has no 90d file pruner, and DSR erasure does not propagate to Qdrant/Redis/JSONL/Drive. | Policy-bound retention and UU PDP DSR erasure propagate across PG and all derived stores (`qdrant`, `redis`, `sqlite`, `file_state`, `external_container`) with legal-hold preflight and PII-free aggregate batch receipts. | A cross-store retention/erasure contract is only `COMPLETE` when every store in the data flow has an explicit TTL/purge primitive, legal-hold gate, and aggregate erasure receipt. |
| **6** | **Recovery Order & Cut Consistency** | `D14`, `D17` | `REAL-RUN-RECEIPT.json` is `FAILED_OR_CANNOT_VERIFY` (`conversations: CANNOT-VERIFY`, `clients: FAIL`); `restore_drill_verify.py` checks only 5 PG tables and 0 non-PG stores; 5 repo restore leads (`consumer-matrix.csv:25, 2948, 2962, 5762, 5919`) are unreconciled. | Deterministic multi-store recovery order with a shared cut epoch (`PG restore -> Outbox replay fence -> Qdrant/SQLite/Redis alignment -> External container check`) and green `PASS` on real backups. | Recovery status stays `FAILED_OR_CANNOT_VERIFY` until (a) real-backup `clients` and `conversations` pass without violations/errors, (b) all 5 repo restore leads are reconciled, and (c) cross-store cut divergence is fenced. |
| **7** | **Workload & Cost** | `D15` | `llm_cost_recorder.py:239-298` performs best-effort triple-write (Prometheus, PG `llm_cost_events`, Fly `/data/llm_cost_log.*.jsonl`) with no JSONL-to-PG backfill and no pricing validation. | Complete cost attribution with deterministic `request_id` deduplication and automated reconciliation between `/data/llm_cost_log.*.jsonl` and PG `llm_cost_events`. | Cost contracts must specify sink failure behavior and measure drift delta between `file_state` JSONL and PG `llm_cost_events`. |
| **8** | **Analytics & Observability** | `D12` | `war-room/metrics/costs/route.ts:84-89` masks PG `42P01` (`undefined_table`) as HTTP `200` with `grand_total_usd: 0`; `unified_health_service.py:129-156` (`check_qdrant`) performs zero network I/O and reports `status="ok"`. | Observability probes and analytics endpoints fail closed (`CANNOT_MEASURE` / `ERROR` != `0` / `HEALTHY`) and execute real bounded store I/O checks. | Any health or analytics surface that returns `ok` without I/O or `0` on `42P01`/connection failure is classified as a `COUNTEREXAMPLE_PROVED` contract defect. |

---

## 2. Stage `S1` (Execution) Scoped Development Proposal for `B08`

During Stage `S1` (after Dux synthesis of `ANALYSIS.md` and `PROPOSAL.md`), `B08` will **not** perform unapproved production redesigns or touch off-limits files. Instead, `B08` proposes to deliver a deterministic, self-contained **Cross-Store Contract & Invariant Verification Suite** inside `B08`'s owned perimeter:

### 2.1 Owned Artifact & Code Perimeter
1. **`research/operations/udb-wave8/B08/crossstore_contract_ledger.json`** (and `.csv` projection):
   - Machine-verifiable sibling contract rows (using the exact frozen schema from `BATTLE.md` §3: `consumer_id,operation_id,store_id,source_version,evidence_timestamp,evidence_sha256,status,unknowns` + `principal,role,tenant,authorization,transaction,effects,retries,idempotency,failure,retention,recovery`) for all multi-store operations (`store_touch_set` containing `;` or spanning `event_delivery`, `external_container`, recovery, observability, and cost attribution).
2. **`scripts/ci/crossstore_guarantees_verify.py`** (or scoped module under `research/operations/udb-wave8/B08/` per Dux placement ruling):
   - Pure-Python, offline-capable verifier (mirrors the fail-closed `PASS` / `FAIL` / `CANNOT-VERIFY` design of `scripts/ci/restore_drill_verify.py:217-268`) that evaluates the 8 cross-store guarantees against static AST/schema evidence and JSON runtime receipts:
     - **Check 1 (`dependencies`)**: Validates sibling contract completeness and flags static-token false positives (e.g., `collective_memory_service.py` Qdrant removal vs `consumer-matrix.csv` lead row).
     - **Check 2 (`references`)**: Validates cross-store reference declarations (`154_asset_provenance.sql` 12 `asset_kind` mappings, SQLite vs PG split authority, Drive/NotebookLM external containers) and scores unverified polymorphic pointers as `CANNOT-VERIFY` or `FAIL`.
     - **Check 3 (`versions`)**: Verifies `_schema_versions` vs `schema_migrations` reconciliation invariants (`165_reconcile_schema_migrations_duplicates.sql`) and checks Qdrant `1536`-dim model-binding receipt presence (`STATE.json:43`).
     - **Check 4 (`time_semantics`)**: Detects clock-source mixing (`NOW()` vs `statement_timestamp()` vs `clock_timestamp()` vs host wall-clock), missing `consumed_at >= created_at` constraints, and non-idempotent timestamp fallback correlation IDs (`pg-to-organism-bridge.py:174`).
     - **Check 5 (`retention_erasure_security`)**: Verifies presence of retention policy bindings (`264_visa_decision_retention_policy.sql`), detects unconsumed outbox orphan windows (`>60m` in `outbox.py:334, 429`), flags unimplemented retention configs (`llm_cost_recorder.py:58`), and checks cross-store DSR propagation completeness.
     - **Check 6 (`recovery_order`)**: Evaluates `REAL-RUN-RECEIPT.json` and multi-store cut consistency ($T_{\text{pg}}$ vs $T_{\text{redis}}, T_{\text{qdrant}}, T_{\text{jsonl}}, T_{\text{drive}}$), proving why `clients: FAIL` (`VIOLATION: 1`) is independent of `required_columns` and enforcing reconciliation of the 5 restore-drill repo leads.
     - **Check 7 (`workload_cost`)**: Evaluates triple-write cost ledger contracts (`llm_cost_recorder.py`) for JSONL-vs-PG drift detection and `request_id` idempotency.
     - **Check 8 (`analytics_observability`)**: Audits health and cost endpoints for silent error masking (`42P01 -> 0 USD` in `war-room/metrics/costs/route.ts:84-89`) and zero-I/O false-positive health checks (`unified_health_service.py:129-156`).
3. **`tests/ci/test_crossstore_guarantees_verify.py`**:
   - Deterministic `pytest` suite covering **positive cases** (well-formed multi-store contracts, valid restore cut epoch, atomic PG DSR erasure batch receipt, monotonic timestamps) and **meaningful negative cases** (`CE-01` through `CE-06`: real-backup `clients` violation vs missing column, polymorphic dangling `asset_id`, `pg-to-organism-bridge` 2KB truncation + clock fallback correlation ID, `check_qdrant` zero-I/O false positive, `42P01` silent zero-cost HTTP 200, and uncoordinated restore cut replay).

---

## 3. Concrete Proposals for Operator / Dux Authority Gates

Because `B08` operates under `EXTERNAL PREPARER, NO_DUX` with no shell execution or live production credentials, closing the remaining live runtime blockers requires explicit Dux/Operator action under the three bounded proposals below.

### Rejected Redis authority proposal

The former admin/app-secret mechanism and frozen-input writes were removed under the Dux ruling. B08 delegates observer admission to B02. No Redis command or credential access is admitted here.

### Proposal P-AUTH-02 — Mini `restore_drill` Disaggregation & Second-Run Gate (`GAP-B08-02`)
- **Problem**: `REAL-RUN-RECEIPT.json` (`2026-10-15T03:00:43Z`) failed verification (`aggregate: "CANNOT-VERIFY"`, `conversations: CANNOT-VERIFY` with `UNMEASURED_CHECK: 1`, `clients: FAIL` with `VIOLATION: 1`), and the prior one-run authorization is exhausted (`ASTRA-ADVICE.md:7`). Furthermore, as proved in `ANALYSIS.md` `CE-01` (`FINAL-BLUE-GATE.json:117`), `clients.lead_metadata` already existed in that restored snapshot; the failure was a data invariant violation (`client_type_unknown` or `lead_metadata_not_object`) plus a query execution failure on `conversations`.
- **Proposed Two-Step Gate**:
  - **Step 1 (Zero-Run Read-Only Artifact Inspection)**: Before requesting any new restore run, Dux inspects the existing `restore-drill-verify.json` file on Mini (from the `2026-10-15T03:00:43Z` run) to extract the non-PII `domains.conversations.reasons[]` (`code` + SQL error class) and `domains.clients.reasons[]` (`client_type_unknown=<int>, lead_metadata_not_object=<int>`). `scripts/ci/restore_drill_verify.py:346-354` already writes those exact integer breakdown strings into `Reason.detail` inside `restore-drill-verify.json`!
  - **Step 2 (Conditional Second-Run Authorization Request)**: Only if a verifier or backup-pipeline fix must be proved against a real snapshot after Step 1, Dux requests explicit operator (`Zero`) authorization for one bounded re-run of `mini.restore_drill`.

### Proposal P-AUTH-03 — Cross-Block Checkpoint Alignment (`B01..B07`)
- **`B01` (Runtime & CI Inventory)**: Reconcile the 5 restore-drill repo leads (`consumer-matrix.csv:25, 2948, 2962, 5762, 5919`) against Mini runtime `mini.restore_drill` (`row 6031`), and supply the active/inactive disposition for `CI-REGISTRATION-UNMATCHED-GH-1..30`.
- **`B02` / `B03` (PostgreSQL Schema & Policies)**: Confirm whether `visa_decision_retention_policies` (`264_visa_decision_retention_policy.sql:20`) has any seeded policy row in production or remains fail-closed empty, and confirm whether `144_events_outbox.sql` will gain a `CHECK (consumed_at IS NULL OR consumed_at >= created_at)` constraint in `S2`.
- **`B04` (Qdrant)**: Provide the read-only collection metadata receipt proving `size = 1536`, distance metric, and payload schema across local Pro and Qdrant Cloud collections (`GAP-B08-03`).
- **`B06` (SQLite & File State)**: Resolve the split authority for `asset_provenance` between `apps/mata-garuda/cell.yaml` (`sqlite`, `consumer-matrix.csv:2517`) and `154_asset_provenance.sql` (`postgresql`, `consumer-matrix.csv:386`).
- **`B07` (External Containers)**: Provide the disposition of `NOTEBOOK-CONTAINER-REFERENCE-NLM-1..31` (`consumer-matrix.csv:6000-6030`) and `clients.google_drive_folder_id` orphan checking.

---

## DUX-REQUESTS

Per `DUX-NOTE-ANALYSIS.md`, shell execution (`run_command`) is disabled in this session. The following read-only computations over existing repository files and receipts are requested from the BLUE Dux before Synthesis / `S1`:

1. **`id`: `DUX-REQ-B08-01`**
   - **Exact read-only command or script path**:
     ```bash
     python3 -c '
     import csv, collections, json
     with open(".agent-receipts/udb-wave8-inputs/consumer-matrix.csv", newline="", encoding="utf-8") as f:
         rows = list(csv.DictReader(f))
     multi = [r for r in rows if ";" in r["store_touch_set"] or r["store_touch_set"] in ("event_delivery", "external_container")]
     by_touch = collections.Counter(r["store_touch_set"] for r in multi)
     by_class = collections.Counter(r["root_class"] for r in multi)
     print(json.dumps({"total_rows": len(rows), "cross_store_or_boundary_rows": len(multi), "by_store_touch_set": dict(by_touch.most_common()), "by_root_class": dict(by_class.most_common())}, indent=2))
     '
     ```
   - **Inputs**: `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv` (SHA256 `c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118`)
   - **Expected output shape**: Aggregate JSON object with `total_rows` (`6030`), `cross_store_or_boundary_rows` (`<int>`), `by_store_touch_set` (`{ "<store_set>": <int> }`), and `by_root_class` (`{ "<root_class>": <int> }`).
   - **Why it matters for the block's contract**: Establishes the exact, deterministic denominator of multi-store / cross-boundary rows in `consumer-matrix.csv` owned or co-owned by `B08` (`D16`, `D17`).

2. **`id`: `DUX-REQ-B08-02`**
   - **Exact read-only command or script path**:
     ```bash
     python3 -c '
     import csv, json
     targets = {"25", "376", "386", "406", "471", "492", "1006", "1042", "1058", "2517", "2948", "2962", "5762", "5880", "5919", "6030"}
     with open(".agent-receipts/udb-wave8-inputs/consumer-matrix.csv", newline="", encoding="utf-8") as f:
         out = [r for i, r in enumerate(csv.DictReader(f), start=1) if str(i) in targets or "restore" in r["source_path"].lower() or "outbox" in r["source_path"].lower() or "provenance" in r["source_path"].lower() or "cost" in r["source_path"].lower()]
     print(json.dumps({"matched_count": len(out), "rows": [{"lead_id": r["lead_id"], "root_class": r["root_class"], "source_path": r["source_path"], "store_touch_set": r["store_touch_set"], "object_names": r["object_names"], "contract_status": r["contract_status"]} for r in out]}, indent=2))
     '
     ```
   - **Inputs**: `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv`
   - **Expected output shape**: JSON object containing `matched_count` and the exact slice of `lead_id`, `root_class`, `source_path`, `store_touch_set`, `object_names`, and `contract_status` for all restore-drill, outbox, provenance, and cost-recorder leads.
   - **Why it matters for the block's contract**: Pins every `lead_id` in `consumer-matrix.csv` corresponding to `D12`, `D14`, `D15`, `D16`, and `D17` so `B08`'s `crossstore_contract_ledger.json` maps 1-to-1 to the canonical `LEAD-*` identifiers (`REPORT.md:95-97`, `FINAL-BLUE-GATE.json:120`).

3. **`id`: `DUX-REQ-B08-03`**
   - **Exact read-only command or script path**:
     ```bash
     python3 -c '
     import hashlib, json, pathlib
     files = [
         "scripts/ci/restore_drill_verify.py",
         "scripts/pg-to-organism-bridge.py",
         "scripts/outbox-prune.sh",
         "apps/backend-rag/backend/services/events/outbox.py",
         "apps/backend-rag/backend/services/observability/llm_cost_recorder.py",
         "apps/backend-rag/backend/services/monitoring/unified_health_service.py",
         "apps/backend-rag/backend/core/qdrant_db.py",
         "apps/admin-dashboard/app/api/war-room/metrics/costs/route.ts",
         "apps/backend-rag/backend/db/migrations_v2/144_events_outbox.sql",
         "apps/backend-rag/backend/db/migrations_v2/154_asset_provenance.sql",
         "apps/backend-rag/backend/db/migrations_v2/165_reconcile_schema_migrations_duplicates.sql",
         "apps/backend-rag/backend/db/migrations_v2/264_visa_decision_retention_policy.sql",
     ]
     print(json.dumps({p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() for p in files}, indent=2))
     '
     ```
   - **Inputs**: The 12 repository source files analyzed in `ANALYSIS.md`.
   - **Expected output shape**: JSON dictionary `{ "<repo_relative_path>": "<64-hex-sha256>" }`.
   - **Why it matters for the block's contract**: Supplies the exact per-file `evidence_sha256` values required by the frozen sibling contract schema (`BATTLE.md` §3) for each `B08` operation contract row.

4. **`id`: `DUX-REQ-B08-04`**
   - **Exact read-only command or script path**:
     - Inspect the existing Mini restore verifier output file (from the `2026-10-15T03:00:43Z` run referenced in `REAL-RUN-RECEIPT.json:19`) if still present on Mini:
       ```bash
       python3 -c '
       import json, pathlib
       for candidate in sorted(pathlib.Path("/tmp").glob("*restore*verify*.json")) + [pathlib.Path.home() / ".organism" / "restore-drill-verify.json"]:
           if candidate.is_file():
               data = json.loads(candidate.read_text(encoding="utf-8"))
               print(json.dumps({
                   "path": str(candidate),
                   "aggregate": data.get("aggregate"),
                   "conversations_reasons": data.get("domains", {}).get("conversations", {}).get("reasons", []),
                   "clients_reasons": data.get("domains", {}).get("clients", {}).get("reasons", []),
               }, indent=2))
       '
       ```
   - **Inputs**: Existing local `restore-drill-verify.json` artifact on Mini (read-only; does **not** run a new restore drill).
   - **Expected output shape**: Aggregate reason code list (`code` + integer count `detail` from `scripts/ci/restore_drill_verify.py:346-354`, e.g., `client_type_unknown=<int>, lead_metadata_not_object=<int>` and the SQL error class for `conversations`), with zero row values or PII.
   - **Why it matters for the block's contract**: Disaggregates `GAP-B08-02` (`conversations: UNMEASURED_CHECK` and `clients: VIOLATION`) without consuming a new restore-drill authorization.

## Adversarial review

A real scoped Codex document review examined source SHA-256 293372971df2e4bb736ea2c226322aaa3c30de059d02a46a138a9504d03a7d91. R1-DOCUMENT-REVIEW.json records scope, findings and limitations: REVIEWED_PARTIAL_WITH_BLOCKERS, no full-document or implementation approval. Historical wrong counts/paths/authority proposals do not become executable through attribution. The addendum reconciles actual receipts; this is not an independent code grade. Requested supporting seat: Astra 6 / xhigh; effective runtime identity UNOBSERVED. A fresh independent Opus 5.5 / xhigh exact-head BLUE gate remains required.
