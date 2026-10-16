---
adversarial_review: codex
---

> Historical research retained for traceability. Superseded statements and commands are BLOCKED FOR IMPLEMENTATION. Current evidence is the synthesis addendum, pinned receipt and binding Dux rulings. No production/native action is authorized here.

# UDB Wave 8 — Block B08 Analysis: Cross-Store Operational Guarantees

- **Mandate ID**: `universal-db-wave8-20261015`
- **Block**: `B08` — Cross-store operational guarantees (`dependencies`, `references`, `versions`, `time semantics`, `retention/erasure/security`, `recovery order`, `workload/cost`, `analytics/observability`)
- **Research Lines Mapped**: Primary `D12`, `D14`, `D15`, `D16`, `D17`; Cross-cutting dependencies `D00`, `D01`, `D11`, `D13`
- **Mission Colour / Gear**: `BLUE` / `GEAR 3`
- **Block Lead Seat**: `Gemini 4 Argon (High)` — `EXTERNAL PREPARER, NO_DUX`
- **Appointed Dux**: `claude-opus-5-5` (`xhigh`) on `Pro`
- **Host / Worktree**: `Mini` / `/Users/nuzantara/nuzantara/.worktrees/db-udb-b08-crossstore`
- **Base Commit SHA**: `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`
- **Stage**: `ANALYSIS ONLY`

---

## 1. Scope & Boundary Matrix (`B08` vs `B01..B07`)

Block `B08` governs the invariants that span **two or more storage substrates** or **system-wide operational planes** across PostgreSQL (`nuzantara-postgres`), Qdrant (local Pro and Qdrant Cloud), Redis (Pro and Mini), SQLite (`mata-garuda`, local caches), append-only/queue `file_state` (JSONL/JSON on Pro, Mini, and Fly `/data`), `event_delivery` (`events_outbox` + `LISTEN/NOTIFY` + Redis Streams), and `external_container` (Google Drive, NotebookLM).

| B08 Guarantee Area | Primary Research Line(s) | Cross-Block Dependencies (`B01..B07`) | Current Baseline Status (`STATE.json`) |
| :--- | :--- | :--- | :--- |
| **1. End-to-End Dependencies** | `D16` (and `D00`, `D01`, `D11`) | `B01` (runtime inventory), `B02..B07` (store-specific writers/readers) | `D16: OPEN`, `D00: PARTIAL`, `D01: PARTIAL`, `D11: PARTIAL` (`active_consumer_denominator = "UNKNOWN"`) |
| **2. Cross-Store References** | `D17` | `B02` (PG relational FKs), `B04` (Qdrant points), `B06` (SQLite/file_state), `B07` (external containers) | `D17: OPEN` (no cross-store FK enforcement; polymorphic text pointers) |
| **3. Versions & Model/Schema Lineage** | `D00`, `D13`, `D17` | `B02`/`B03` (PG migrations), `B04` (Qdrant embedding model binding) | `D13: PARTIAL`, `D17: OPEN` (`qdrant_model_binding_proved = false`) |
| **4. Time Semantics** | `D17` | `B02` (PG timestamps/ranges), `B05` (event bus / Redis stream timestamps) | `D17: OPEN` (mixed `NOW()`, `statement_timestamp()`, `clock_timestamp()`, host `datetime.now()`, heuristic ms/s parsing) |
| **5. Retention, Erasure & Security** | `D14` | `B02`/`B03` (PG retention/DSR), `B04` (Qdrant point deletion), `B05` (Redis/outbox pruning), `B06` (JSONL rotation) | `D14: OPEN` (PG Visa Oracle primitives exist in `264`, but cross-store erasure propagation is unverified) |
| **6. Recovery Order & Cut Consistency** | `D14`, `D17` | `B01` (`mini.restore_drill`), `B02` (PG restore), `B04..B07` (non-PG stores) | `D14: OPEN`, `D17: OPEN` (`REAL-RUN-RECEIPT.json` = `FAILED_OR_CANNOT_VERIFY`; no multi-store cut epoch) |
| **7. Workload & Cost Attribution** | `D15` | `B02` (`llm_cost_events`, `war_room_costs`), `B06` (`/data/llm_cost_log.*.jsonl`), `B07` (external APIs) | `D15: OPEN` (triple-write best-effort; no automated PG-vs-JSONL reconciliation) |
| **8. Analytics & Observability** | `D12` | `B02` (analytics tables), `B04` (Qdrant health), `B05` (Redis health) | `D12: OPEN` (silent `42P01` zero-cost fallback; no-op Qdrant health check) |

---

## 2. Verified Facts (Current State vs Desired Guarantees)

All facts below cite either a frozen input file pinned in `.agent-receipts/udb-wave8-inputs/INPUT-MANIFEST.json:1-13` (with its verified SHA256) or an exact `file:line` in worktree commit `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`.

### 2.0 Frozen Baseline Pins (`INPUT-MANIFEST.json:1-13`)
- `scope`: `"FROZEN_DATED_TECHNICAL_BASELINE_NOT_NEW_LIVE_PROOF"` (`.agent-receipts/udb-wave8-inputs/INPUT-MANIFEST.json:2`).
- Pinned SHA256 digests (`.agent-receipts/udb-wave8-inputs/INPUT-MANIFEST.json:4-11`):
  - `REPORT.md`: `d289fb8660a6bd634cb7785fef3a8c0b47ceefe82463d134c4bbf66dc0563e9a`
  - `STATE.json`: `caaebbbac9703bf5ebd5f7624b8a2dd6759a2e508703f311cecffebf1c0967d4`
  - `FINAL-BLUE-GATE.json`: `b9d284e1dba9e87ad340cbd4076061e7a35a93fdf8bc1c910340e6099d711856`
  - `REAL-RUN-RECEIPT.json`: `9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d`
  - `research-lines.csv`: `1b3d1f31df997500975311d3f49cbd3a50346c2fa7d27f45ff808c7203654c10`
  - `ASTRA-ADVICE.md`: `72f349f285bc681013b67ad1d25cdad54d3d4478080dc1f5e7e0512dd9e1fdb8`
  - `consumer-matrix.csv`: `c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118`
- Baseline inventory counts (`STATE.json:25-33`, `REPORT.md:19-28`):
  - `baseline_leads_preserved`: `6029`
  - `additional_runtime_observations`: `1` (`mini.restore_drill` at `consumer-matrix.csv:6031`)
  - `union_lead_rows`: `6030` (lines `2..6031` of `consumer-matrix.csv`)
  - `active_consumer_denominator`: `"UNKNOWN"`
  - `complete_operation_contracts`: `0`
  - `complete_root_classes`: `0`

### 2.1 Area 1 — End-to-End Dependencies (`D16`, `D00`, `D01`, `D11`)
- **Current Facts**:
  1. `consumer-matrix.csv:1-6031` records `6030` static/runtime lead rows across `root_class` values including `ci_workflow`, `migration_sql`, `backend_service`, `backend_router`, `frontend_api`, `mcp_tool`, `cell_organ`, `script_job`, `systemd_unit`, `launchd_unit`, `cron_entry`, `ci_unmatched`, `notebook_ref`, and `runtime_restore_drill`.
  2. Multi-store rows in `consumer-matrix.csv` explicitly list composite `store_Touch_set` values separated by `;`, e.g.:
     - `apps/backend-rag/backend/db/migrations_v2/144_events_outbox.sql` -> `event_delivery;postgresql` (`consumer-matrix.csv:376`).
     - `apps/backend-rag/backend/db/migrations_v2/154_asset_provenance.sql` -> `event_delivery;postgresql;qdrant` (`consumer-matrix.csv:386`).
     - `apps/backend-rag/backend/services/observability/llm_cost_recorder.py` -> `file_state;postgresql` (`consumer-matrix.csv:1058`), plus Prometheus in-memory counters (`llm_cost_recorder.py:211-236`).
     - `scripts/pg-to-organism-bridge.py` -> touches PostgreSQL (`LISTEN/NOTIFY`), `file_state` (`~/.organism/events/pg-bridge.jsonl` and `~/.organism/heartbeats/pg-bridge.json`), and Redis (`XADD organism:events`) (`scripts/pg-to-organism-bridge.py:59-78, 189-222`).
  3. Every row in `consumer-matrix.csv:2-6030` carries `contract_status = LEAD_ONLY` with `UNKNOWN_DYNAMIC_OR_UNPROVED` for `principal_role`, `auth_gate`, `tx_boundary`, `idempotency_key`, `retry_policy`, `timeout_policy`, `retention_class`, and `pii_class`.
  4. Runtime daemon inventory (`STATE.json:36-41`, `REPORT.md:39-42`) proved `pro_launchd_loaded_count = 72`, `mini_launchd_loaded_count = 16`, `pro_crontab_line_count = 35`, `mini_crontab_line_count = 37`, while `30` GitHub workflow unmatched registrations (`CI-REGISTRATION-UNMATCHED-GH-1..30`, `consumer-matrix.csv:5970-5999`) have `active_status = UNKNOWN`.
- **Desired Guarantee**: Every active runtime consumer has a closed end-to-end dependency graph mapping caller -> service/daemon -> store(s) -> downstream side-effects, with an explicit active/inactive denominator and fail-closed timeout/retry/circuit-breaker contracts at every store boundary.

### 2.2 Area 2 — Cross-Store References (`D17`)
- **Current Facts**:
  1. `apps/backend-rag/backend/db/migrations_v2/154_asset_provenance.sql:25-30` defines `asset_provenance` with `asset_kind TEXT NOT NULL` and `asset_id TEXT NOT NULL`, explicitly documenting at line `29`: `-- Polymorphic: TEXT so UUID, INTEGER, kbli_code, point_id, composite all fit`.
  2. Of the 12 allowed `asset_kind` values in `154_asset_provenance.sql:47-60`:
     - Only 4 map to PostgreSQL tables (`article_draft`, `Shared_document`, `legal_chain_rule`, `tax_rate_row`), and even those have **no SQL `FOREIGN KEY`** because `asset_id` is polymorphic `TEXT` (`154_asset_provenance.sql:65-72`).
     - 8 kinds have **no PG target table** or reside in non-PG stores (`154_asset_provenance.sql:67-70`): `intel_finding` (Qdrant `point_id`), `kg_entity` (`kbli_code`/Qdrant), `visa_requirement` (in-code `VISA_TYPES_REFERENCE`), `kbli_synthesis` (cached synthesis), `generated_media` (filesystem/R2), `social_post_copy` (IG/X/TG/WA API), `crm_enrichment_lookup` (Google Places composite), `rag_answer_citation` (ephemeral turn).
  3. `apps/mata-garuda/cell.yaml` (`consumer-matrix.csv:2517`) declares `asset_provenance` under `sqlite`, whereas `154_asset_provenance.sql` (`consumer-matrix.csv:386`) declares `asset_provenance` in PostgreSQL (`event_delivery;postgresql;qdrant`).
  4. External container references (`clients.google_drive_folder_id` checked as a JSON/string shape in `scripts/ci/restore_drill_verify.py:114`, and 31 NotebookLM container references `NOTEBOOK-CONTAINER-REFERENCE-NLM-1..31` at `consumer-matrix.csv:6000-6030`) store external opaque identifiers without referential integrity or automated liveness verification.
- **Desired Guarantee**: Every cross-store pointer `(source_store, source_object, source_id) -> (target_store, target_object, target_id)` has a declared target store authority, a deterministic resolver, an explicit orphan-detection/reconciliation check, and a fail-closed behavior when the target object is missing or tombstoned.

### 2.3 Area 3 — Versions & Schema/Model Lineage (`D00`, `D13`, `D17`)
- **Current Facts**:
  1. PostgreSQL tracks schema migrations across two tables reconciled in `apps/backend-rag/backend/db/migrations_v2/165_reconcile_schema_migrations_duplicates.sql:4-9`: `schema_migrations` (which accumulated duplicate `migration_number` rows archived into `schema_migrations_reconciliation_archive` at lines `38-99`) and `_schema_versions` (the release runner ledger).
  2. In `apps/backend-rag/backend/db/migrations_v2/154_asset_provenance.sql:33-35`, `asset_provenance` records `source_Version TEXT NOT NULL` and `generator_model TEXT NOT NULL`, plus `parent_provenance_ids UUID[] NOT NULL DEFAULT '{}'` (`line 36`) without element-level foreign-key enforcement.
  3. In Qdrant, `STATE.json:42-43` and `REPORT.md:43-46` establish `qdrant_local_collection_count = 2` on Pro and `qdrant_model_binding_proved = false`. While project rules freeze `text-embedding-3-small` (`1536` dimensions, `apps/backend-rag/backend/core/qdrant_db.py:81`), live collection metadata and payload version tags binding Qdrant points to PG source row versions are not yet proved in `STATE.json`.
  4. `CollectiveMemoryService` (`apps/backend-rag/backend/services/memory/collective_memory_service.py:12, 77`) states `"PostgreSQL-based storage and retrieval (Qdrant removed 2026-01-10)"`, yet `consumer-matrix.csv:1006` still classifies `collective_memory_service.py` under `store_touch_set = postgresql;qdrant` because of static token matching (`LEAD_ONLY`).
- **Desired Guarantee**: Every derived artifact (Qdrant point, SQLite cache row, Redis stream event, JSONL record) carries an immutable `(source_store, source_object, source_version, schema_version, model_id, vector_dimensions)` tuple verifiable against the authoritative PG `_schema_versions` ledger and collection metadata.

### 2.4 Area 4 — Time Semantics (`D17`)
- **Current Facts**:
  1. PostgreSQL tables mix transaction-start time (`NOW()` / `CURRENT_TIMESTAMP`), statement-start time (`statement_timestamp()`), and wall-clock time (`clock_timestamp()`):
     - `events_outbox` (`apps/backend-rag/backend/db/migrations_v2/144_events_outbox.sql:11`) uses `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`, and `acknowledge()` (`apps/backend-rag/backend/services/events/outbox.py:261`) sets `consumed_at = NOW()`.
     - `visa_evaluate_idempotency` (`apps/backend-rag/backend/db/migrations_v2/264_visa_decision_retention_policy.sql:129-131`) strictly enforces `NEW.reserved_at IS DISTINCT FROM statement_timestamp() OR NEW.created_at IS DISTINCT FROM statement_timestamp()` (raising an exception otherwise), while `expected_expires_at <= clock_timestamp()` (`line 152`) and `purge_visa_decisions` (`line 1007`) compare against `clock_timestamp()`.
     - `visa_decision_retention_policies` (`264_visa_decision_retention_policy.sql:33, 39-42, 48`) enforces non-overlapping `[lower, upper)` `TSTZRANGE` (`effective_period`) per `environment` via `EXCLUDE USING gist`.
  2. Cross-process / cross-host clocks are uncoordinated:
     - `scripts/pg-to-organism-bridge.py:176-180` stamps `ts_utc` on bridged PG notifications using the local host clock (`datetime.now(timezone.utc).isoformat()`) at notification receipt time rather than the PG commit/outbox timestamp.
     - `apps/backend-rag/backend/services/events/outbox.py:115-145` (`_payload_timestamp_seconds`) uses a magnitude heuristic (`value / 1000.0 if value > 1e12 else value`) across 3 ad-hoc payload keys (`"pulse_timestamp"`, `"timestamp"`, `"ts"`) and compares against Python host `time.time()` (`line 161`).
- **Desired Guarantee**: Explicit separation and monotonic ordering between `event_time` (producer occurrence), `tx_commit_time` (authoritative store commit), and `ingest_time` (bridge/consumer receipt), using explicit unit-typed ISO-8601 UTC or epoch-ms fields and database-enforced `consumed_at >= created_at` constraints.

### 2.5 Area 5 — Retention, Erasure & Security (`D14`)
- **Current Facts**:
  1. **Visa Oracle PG substrate (`264_visa_decision_retention_policy.sql`)**:
     - Fails closed on new `SHADOW`/`ENFORCE` decision or idempotency inserts unless an active Zero-approved policy row exists in `visa_decision_retention_policies` (`264_visa_decision_retention_policy.sql:5-9, 137-149`).
     - Provides bounded `SECURITY DEFINER` primitives `purge_visa_decisions(p_limit, p_requested_by)` (`lines 982-1048`), `erase_visa_decision_for_dsr(p_decision_id, p_case_reference, p_requested_by)` (`lines 1050-1117`), and `set_visa_decision_legal_hold(...)` (`lines 1119-1192`), with `REVOKE ALL ... FROM PUBLIC` (`lines 1197-1201`).
     - `erase_visa_decision_for_dsr` deletes matching rows in `visa_evaluate_idempotency`, `visa_decision_payloads`, and `visa_decisions` inside one PG transaction and logs only aggregate counts into `visa_decision_dsr_erasure_batches` (`lines 1093-1115`).
  2. **Outbox & JSONL / Redis substrates**:
     - `scripts/outbox-prune.sh:2, 66-88` and `apps/backend-rag/backend/services/events/outbox.py:422-448` delete **consumed** `events_outbox` rows older than 30 days (`OUTBOX_PRUNE_DAYS:-30`), but explicitly **never delete unconsumed rows** (`outbox.py:429-431`).
     - `scripts/pg-to-organism-bridge.py:67, 189-221` appends PG notification payloads to `~/.organism/events/pg-bridge.jsonl` and Redis stream `organism:events` (`XADD ... *` with no `MAXLEN` trim in the command at `lines 208-211`).
     - `apps/backend-rag/backend/services/observability/llm_cost_recorder.py:58-60` defines `DEFAULT_RETENTION_DAYS = 90` in config (`LLM_COST_JSONL_RETENTION_DAYS`), but `LLMCostRecorder` (`lines 102-299`) contains **no pruning or rotation deletion method** that actually removes files older than 90 days.
  3. **Cross-Store DSR / Erasure Gap**: When a client or decision is erased in PostgreSQL, there is no automated cross-store erasure coordinator that tombstones or purges derived copies in Qdrant collections, `events_outbox` payloads, `~/.organism/events/pg-bridge.jsonl`, Redis `organism:events`, SQLite (`mata-garuda`), or Google Drive folders.
  4. **Redis Security Observation**: Both Pro and Mini Redis instances require authentication (`"pro": "AUTHORIZATION_REQUIRED"`, `"mini": "AUTHORIZATION_REQUIRED"`, `STATE.json:44-47`), and `scripts/pg-to-organism-bridge.py:202-206` passes `REDIS_PASSWORD` via `REDISCLI_AUTH` in environment variables.
- **Desired Guarantee**: Policy-bound retention and UU PDP DSR erasure propagate across all stores holding derived or bridged state (PG, Qdrant, Redis, SQLite, JSONL, external containers), with legal-hold preflight checks and PII-free aggregate erasure receipts across every store touched.

### 2.6 Area 6 — Recovery Order & Cut Consistency (`D14`, `D17`)
- **Current Facts**:
  1. `REAL-RUN-RECEIPT.json:1-84` records the single authorized real-backup restore run on Mini (`2026-10-15T03:00:43Z` to `2026-10-15T03:02:11Z`, duration `87.337s`):
     - `status`: `"FAILED_OR_CANNOT_VERIFY"` (`REAL-RUN-RECEIPT.json:11`).
     - Sidecar (`restore-drill-last.json`): `status = "error"`, `backup_age_hours = 0.02`, `rpo_ok = true`, `rto_ok = true`, `schema_migrations_count = 169` (`REAL-RUN-RECEIPT.json:28-38`).
     - Verifier (`restore-drill-verify.json`): `aggregate = "CANNOT-VERIFY"`, `exit_code = 2` (`REAL-RUN-RECEIPT.json:40-47`).
     - Per-domain status (`REAL-RUN-RECEIPT.json:48-74`):
       - `conversations`: `status = "CANNOT-VERIFY"`, `reason_counts = {"UNMEASURED_CHECK": 1}`
       - `clients`: `status = "FAIL"`, `reason_counts = {"VIOLATION": 1}`
       - `visa_decisions`: `status = "PASS"`
       - `events_outbox`: `status = "PASS"`
       - `visa_decision_retention_policies`: `status = "PASS"`
  2. `scripts/ci/restore_drill_verify.py:42-164` verifies **only 5 PostgreSQL tables** (`conversations`, `clients`, `visa_decisions`, `events_outbox`, `visa_decision_retention_policies`). It performs zero checks on Qdrant collections, Redis streams, SQLite databases, JSONL logs, or external containers.
  3. Five historical restore-drill source leads in `consumer-matrix.csv` (`rows 25, 2948, 2962, 5762, 5919`) remain unreconciled with the Mini runtime restore path (`REPORT.md:95-97`, `FINAL-BLUE-GATE.json:120`).
- **Desired Guarantee**: A documented, deterministic multi-store recovery order (`PostgreSQL authority -> Outbox replay fence -> Qdrant vector index alignment -> SQLite/Redis cache invalidation or rebuild -> External container reconciliation`) with a shared cut epoch and green `PASS` verification on real backups.

### 2.7 Area 7 — Workload & Cost Attribution (`D15`)
- **Current Facts**:
  1. `apps/backend-rag/backend/services/observability/llm_cost_recorder.py:239-298` implements a non-blocking, parallel triple-write (`_write_prometheus`, `_write_postgres` into `llm_cost_events`, and `_write_jsonl` into `/data/llm_cost_log.YYYY-MM-DD.jsonl`).
  2. Each sink fails independently without raising (`llm_cost_recorder.py:259-285`): if `postgres` fails while `jsonl` succeeds (or vice versa), `record()` returns `{"prometheus": ..., "postgres": False, "jsonl": True}` and logs a `WARNING`.
  3. There is **no automated replay or reconciliation job** in `llm_cost_recorder.py` that backfills missed `llm_cost_events` rows into PostgreSQL from `/data/llm_cost_log.YYYY-MM-DD.jsonl` after a DB outage.
  4. `LLMCallEvent` (`llm_cost_recorder.py:73-75`) explicitly does **not** validate pricing (`"The recorder does NOT validate pricing — callers are expected to compute cost_usd"`).
- **Desired Guarantee**: Every billable LLM/embedding/external API operation has a deterministic `request_id` / `correlation_id`, validated pricing version, and an automated reconciliation loop between durable fallback logs (`file_state`) and PostgreSQL (`llm_cost_events` / `war_room_costs`).

### 2.8 Area 8 — Analytics & Observability (`D12`)
- **Current Facts**:
  1. `apps/admin-dashboard/app/api/war-room/metrics/costs/route.ts:84-89` catches PostgreSQL error `42P01` (`undefined_table` when `war_room_costs` or `war_room_drafts` is absent) and returns HTTP `200` with `{ rows: [], by_day: [], grand_total_usd: 0, total_posts: 0, avg_cost_per_post_usd: 0 }`.
  2. `apps/backend-rag/backend/services/monitoring/unified_health_service.py:129-156` (`check_qdrant`) instantiates `QdrantClient(qdrant_url=settings.qdrant_url, collection_name="visa_oracle")` and checks `if client.qdrant_url and client.collection_name:`. Because `QdrantClient.__init__` (`apps/backend-rag/backend/core/qdrant_db.py:269-313`) is completely lazy (`self._http_client = None`) and performs zero network I/O, `check_qdrant()` marks Qdrant as `ServiceStatus.HEALTHY` / `status="ok"` without ever contacting the Qdrant server.
  3. Historical JSONB scalar double-encoding corrupted analytics and graph tables across PostgreSQL (`176_analytics_jsonb_double_encoding_repair.sql` at `consumer-matrix.csv:406` for `query_analytics`, `workflow_analytics`, `activity_log`, `ab_test_Metrics`, and `243_jsonb_string_scalar_organism_wide_backfill.sql` at `consumer-matrix.csv:471` for `conversations`, `events_outbox`, `kg_nodes`, `kg_edges`).
- **Desired Guarantee**: Observability and cost endpoints never conflate `CANNOT_MEASURE` / `UNDEFINED_TABLE` / `UNCONFIGURED_CLIENT` with `HEALTHY` or `0.00 USD`; every health check executes a real bounded I/O probe against the target store.

---

## 3. Concrete Counterexamples & Negative Proofs

### Counterexample CE-01 — Real-Backup Restore `clients` FAIL Is Non-Causal to the Candidate `required_columns` Patch (`D14` / `B01` / `B08`)
- **Evidence**: `REAL-RUN-RECEIPT.json:53-57`, `FINAL-BLUE-GATE.json:115-118`, `scripts/ci/restore_drill_verify.py:72-95, 110-120, 319-354`.
- **Proof**:
  1. In `scripts/ci/restore_drill_verify.py:319-336`, `verify_domain()` first checks whether all `spec.required_columns` exist in `information_schema.columns`. If any required column is missing, it appends `ReasonCode.MISSING_COLUMN`, skips `_VIOLATIONS_SQL[name]` (`lines 342-343`: `if not any(r.code in (ReasonCode.MISSING_TABLE, ReasonCode.MISSING_COLUMN) ...)`), and scores the domain as `CANNOT-VERIFY` (`lines 257-263`).
  2. A domain only receives `status = "FAIL"` with `ReasonCode.VIOLATION` (`restore_drill_verify.py:254-255, 349-354`) when `_VIOLATIONS_SQL[name]` **executes without SQL error** and returns a sum of violation columns `> 0`.
  3. `_VIOLATIONS_SQL["clients"]` (`restore_drill_verify.py:110-120`) directly references `lead_metadata`:
     ```sql
     COUNT(*) FILTER (
         WHERE lead_metadata IS NOT NULL
           AND jsonb_typeof(lead_metadata) <> 'object'
     ) AS lead_metadata_not_object
     ```
  4. Had `clients.lead_metadata` been missing in the restored backup, PostgreSQL would have raised `UndefinedColumn` during `_run_check` (`lines 285-296`), producing `ReasonCode.UNMEASURED_CHECK` (`status = "CANNOT-VERIFY"`), **not** `ReasonCode.VIOLATION` (`status = "FAIL"`).
  5. Therefore, `clients.lead_metadata` was **present** in the restored backup on Mini, and the real backup failed because at least one row violated `client_type_unknown` or `lead_metadata_not_object`. Furthermore, `conversations` returned `CANNOT-VERIFY` with `UNMEASURED_CHECK: 1` (`REAL-RUN-RECEIPT.json:49-52`), meaning `_VIOLATIONS_SQL["conversations"]` (`restore_drill_verify.py:100-109`) raised an exception during execution.

### Counterexample CE-02 — Polymorphic Cross-Store References Without Integrity or Single Store Authority (`D17`)
- **Evidence**: `apps/backend-rag/backend/db/migrations_v2/154_asset_provenance.sql:25-36, 47-72`, `consumer-matrix.csv:386, 2517`.
- **Proof**:
  1. `asset_provenance.asset_id` (`TEXT`) points across 12 `asset_kind` values spanning PostgreSQL, Qdrant (`intel_finding`, `kg_entity`), filesystem/R2 (`generated_media`), external APIs (`social_post_copy`, `crm_enrichment_lookup`), and ephemeral turns (`rag_answer_citation`).
  2. `parent_provenance_ids UUID[]` (`line 36`) is an array column, which PostgreSQL cannot bind to a foreign key constraint; orphan cleanup is deferred in comments (`line 38`) to a `"weekly orphan-GC cron (W2 backlog)"`.
  3. Simultaneously, `apps/mata-garuda/cell.yaml` (`consumer-matrix.csv:2517`) claims `asset_provenance` as a `sqlite` object while `154_asset_provenance.sql` (`consumer-matrix.csv:386`) defines it in PostgreSQL.

### Counterexample CE-03 — Event Bridge Truncation, Host-Clock Idempotency Drift, and Best-Effort Stream Loss (`D16` / `D17`)
- **Evidence**: `scripts/pg-to-organism-bridge.py:59-78, 138-222`, `apps/backend-rag/backend/db/migrations_v2/144_events_outbox.sql:5-17`.
- **Proof**:
  1. **Silent Payload Truncation**: `scripts/pg-to-organism-bridge.py:138-153` (`_truncate_payload`) truncates any JSON payload exceeding `2000` bytes by replacing every nested `dict` or `list` with the literal string `"(nested-truncated)"` and setting `_truncated = True`. Downstream consumers reading `~/.organism/events/pg-bridge.jsonl` or Redis `organism:events` receive structurally mutated payloads compared to `events_outbox.payload` in PostgreSQL.
  2. **Wall-Clock Fallback Correlation ID Breaks Idempotency**: In `_build_event` (`scripts/pg-to-organism-bridge.py:172-174`), if `correlation_id` and `_outbox_id` are absent from the notification payload, the bridge synthesizes `corr = f"pg-{channel}-{datetime.now(timezone.utc).timestamp()}"`. Any replay or duplicate notification generates a distinct `correlation_id`.
  3. **Non-Atomic Dual Sink**: `_emit_event` (`scripts/pg-to-organism-bridge.py:189-221`) writes to `~/.organism/events/pg-bridge.jsonl` first and then invokes `redis-cli XADD organism:events *` with a 2-second timeout (`line 212`). If Redis returns `NOAUTH`, `ERR`, or times out (`lines 215-221`), the error is logged as a non-fatal warning; the event exists in `pg-bridge.jsonl` and PG but is permanently absent from Redis `organism:events`.
  4. **Missing DB Temporal Constraint**: `144_events_outbox.sql:5-17` has no `CHECK (consumed_at IS NULL OR consumed_at >= created_at)` constraint in DDL; the invariant is only checked ex-post during restore drills (`scripts/ci/restore_drill_verify.py:152-153`).

### Counterexample CE-04 — False-Positive Qdrant Health Check in `UnifiedHealthService` (`D12` / `D16`)
- **Evidence**: `apps/backend-rag/backend/services/monitoring/unified_health_service.py:129-156`, `apps/backend-rag/backend/core/qdrant_db.py:269-313`.
- **Proof**: `UnifiedHealthService.check_qdrant()` creates `QdrantClient(qdrant_url=settings.qdrant_url, collection_name="visa_oracle")` (`line 143`) and immediately returns `HealthCheckResult(name="qdrant", status="ok", ...)` if `client.qdrant_url and client.collection_name` are truthy (`lines 144-155`). Because `QdrantClient.__init__` (`qdrant_db.py:306`) sets `self._http_client = None` and makes zero network requests, `check_qdrant()` reports `ServiceStatus.HEALTHY` even when the Qdrant process or cloud endpoint is completely unreachable.

### Counterexample CE-05 — Silent Zero-Cost Masking on Missing Schema (`42P01`) in Admin Dashboard (`D12` / `D15`)
- **Evidence**: `apps/admin-dashboard/app/api/war-room/metrics/costs/route.ts:84-89`.
- **Proof**: When PostgreSQL raises code `42P01` (`undefined_table` on `war_room_costs` or `war_room_drafts`), the route handler catches the error and returns HTTP `200` with `grand_total_usd: 0, total_posts: 0, avg_cost_per_post_usd: 0` instead of a structured `CANNOT_MEASURE` / `SCHEMA_MISSING` status. This directly violates the repository's measurement invariant (`cannot-measure != measured-zero`).

### Counterexample CE-06 — Unbounded Outbox Unconsumed Backlog vs Stale-Skip Acking (`D14` / `D17`)
- **Evidence**: `apps/backend-rag/backend/services/events/outbox.py:283, 332-335, 383-393, 422-448`.
- **Proof**:
  1. `replay_unconsumed()` only selects rows where `consumed_at IS NULL AND created_at > NOW() - INTERVAL '{max_age_minutes} minutes'` (default `60` minutes, `lines 283, 333-335`).
  2. Any row that remains unconsumed for `> 60` minutes is permanently ignored by `replay_unconsumed()`, **and** is never deleted by `prune_consumed()` (`lines 429-441`, which only deletes `WHERE consumed_at IS NOT NULL`). Thus, unconsumed rows older than 60 minutes become immortal orphan rows in `events_outbox`.
  3. Conversely, for rows `< 60` minutes old whose inner payload timestamp exceeds `payload_ttl_minutes`, `replay_unconsumed()` skips dispatch (`line 383`) but marks `consumed_at = NOW()` with `consumer_id = "outbox_replay_stale_skip"` (`line 391`) and increments the returned `acked` counter (`line 392`)—conflating dropped stale events with successfully delivered events unless callers filter on `consumer_id`.

---

## 4. Inferences (Derived from Verified Facts)

1. **Cross-Store Restore Cut Vulnerability (from §2.5, §2.6, CE-03)**: Because PostgreSQL backups, Qdrant collections, Redis streams, `~/.organism/events/pg-bridge.jsonl`, and Google Drive folders have no shared checkpoint or epoch counter, restoring PostgreSQL to an earlier point $T_{\text{pg}}$ while leaving non-PG stores at $T_{\text{now}}$ will cause `replay_unconsumed()` (`outbox.py:278`) to re-emit events from $(T_{\text{pg}} - 60\text{m}, T_{\text{pg}}]$ that were unacked at $T_{\text{pg}}$ and will leave Qdrant points / Drive folders created in $(T_{\text{pg}}, T_{\text{now}}]$ orphaned from PG rows.
2. **Static Lead Inflation in Cross-Store Touch Sets (from §2.1, §2.3)**: `consumer-matrix.csv` static token scanning over-attributes cross-store dependencies where comments or legacy docstrings mention a store (e.g., `collective_memory_service.py:12` mentioning `"Qdrant removed 2026-01-10"` causes `consumer-matrix.csv:1006` to record `postgresql;qdrant`). Therefore, static `store_touch_set` strings in `consumer-matrix.csv` must be filtered by AST/call-site verification before promoting any `LEAD_ONLY` row to a verified cross-store contract.
3. **Triple-Write Cost Ledger Drift Risk (from §2.7, `llm_cost_recorder.py:239-298`)**: During any PostgreSQL maintenance window or connection pool exhaustion, `LLMCostRecorder` continues writing events to `/data/llm_cost_log.YYYY-MM-DD.jsonl` on the Fly volume while `llm_cost_events` in PG drops those events. Without a deterministic reconciliation job keyed on `request_id` + `ts_utc`, PostgreSQL cost queries under-report actual spend.

---

## 5. Unknowns & Concrete Evidence Blockers

| Gap ID | Research Line(s) | Blocker / Unknown Description | Required Authority / Action to Close |
| :--- | :--- | :--- | :--- |
| **GAP-B08-01** | `D01`, `D12`, `D14`, `D16` | **Redis Runtime State Unobserved on Pro & Mini**: Both hosts return `AUTHORIZATION_REQUIRED` to unauthenticated `INFO` (`STATE.json:44-47`, `REPORT.md:47-50`). Stream length of `organism:events`, memory eviction policy (`maxmemory-policy`), persistence mode (`AOF`/`RDB`), and key TTL distributions are `UNKNOWN`. | Operator/Dux approval of a read-only observer route (`INFO`, `XLEN organism:events`, `CONFIG GET maxmemory*`) using existing host secrets without echoing credentials. |
| **GAP-B08-02** | `D14`, `D17`, `B01` | **Mini Real-Backup Restore Failure & Exhausted Run Authorization**: `REAL-RUN-RECEIPT.json:48-74` ended in `conversations: CANNOT-VERIFY` (`UNMEASURED_CHECK: 1`) and `clients: FAIL` (`VIOLATION: 1`). Prior one-run authorization is exhausted (`ASTRA-ADVICE.md:7`). Exact SQL exception on `conversations` and which sub-check failed on `clients` (`client_type_unknown` vs `lead_metadata_not_object`) are not broken out in the aggregate receipt. | (1) Read-only inspection of the existing Mini restore log/artifacts if retained, or (2) explicit fresh operator/Dux authorization for a second bounded diagnostic run on Mini. |
| **GAP-B08-03** | `D01`, `D07`, `D13`, `D17` | **Qdrant Production Cloud & Model Binding Unproved**: `STATE.json:42-43` proved only `2` local Pro collections (hashed names) and `qdrant_model_binding_proved = false`. Live vector dimensions, distance metrics, payload schema, and PG-to-Qdrant point parity are `UNKNOWN`. | Coordinated with `B04`: read-only collection metadata probe proving `1536`-dim binding and payload version fields. |
| **GAP-B08-04** | `D00`, `D11`, `D16` | **Active Consumer Denominator Unknown**: `active_consumer_denominator = "UNKNOWN"` across `6030` rows (`STATE.json:28`), including `30` unmatched GitHub workflows (`CI-REGISTRATION-UNMATCHED-GH-1..30`) and `31` NotebookLM container refs (`NOTEBOOK-CONTAINER-REFERENCE-NLM-1..31`). | Coordinated with `B01`: join `consumer-matrix.csv` against live `launchd`, `crontab`, Fly process, and GitHub Actions workflow inventories. |
| **GAP-B08-05** | `D14`, `D17` | **Historical Restore Drill Source Drift**: `5` repo leads (`consumer-matrix.csv:25, 2948, 2962, 5762, 5919`) reference restore-drill workflows/scripts not reconciled with the Mini runtime restore job (`REPORT.md:95-97`, `FINAL-BLUE-GATE.json:120`). | Coordinated with `B01`: reconcile all 5 repo leads with the canonical Mini restore runner and `scripts/ci/restore_drill_verify.py`. |

---

## 6. Representative Cross-Store Sibling Contract Table (Frozen Schema)

Per `BATTLE.md` §3, all sibling blocks share the frozen contract fields (`consumer_id,operation_id,store_id,source_version,evidence_timestamp,evidence_sha256,status,unknowns`) and operation instance fields (`principal,role,tenant,authorization,transaction,effects,retries,idempotency,failure,retention,recovery`). Below is the baseline contract mapping for the primary cross-store operations analyzed in `B08`:

| `consumer_id` | `operation_id` | `store_id` | `source_version` | `evidence_timestamp` | `evidence_sha256` | `status` | `unknowns` | `principal` / `role` / `tenant` / `authorization` | `transaction` / `effects` / `retries` / `idempotency` | `failure` / `retention` / `recovery` |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `scripts/pg-to-organism-bridge.py` (`LEAD-5880` / organism bridge) | `op.bridge.pg_notify_to_jsonl_and_redis` | `postgresql;file_state;redis` | `8061c88e0c43dd42e735fd012f9ed072df3ef3d6` (`scripts/pg-to-organism-bridge.py:1-351`) | `2026-10-15T03:02:11Z` | `c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118` | `PARTIAL_COUNTEREXAMPLE_PROVED` | Live Redis stream length & eviction policy (`GAP-B08-01`) | `principal`: local daemon (`DATABASE_URL_LOCAL`/`pg-proxy:15432`, `REDIS_PASSWORD`); `role`: bridge listener; `tenant`: system-wide; `authorization`: env secret file `~/.nuzantara-secrets.env` | `transaction`: non-transactional across stores (`LISTEN` -> JSONL append -> `redis-cli XADD`); `effects`: truncates payloads `>2000B` (`lines 138-153`); `retries`: PG reconnect exponential backoff `5s..60s` (`lines 69-70, 278`), Redis `XADD` `0` retries (`2s` timeout, `line 212`); `idempotency`: `_outbox_id` or fallback host timestamp (`line 174`, non-idempotent fallback) | `failure`: Redis `XADD` failure logged as warning (`lines 215-221`); `retention`: JSONL & Redis stream retention unproved; `recovery`: no replay from `pg-bridge.jsonl` into Redis on outage |
| `apps/backend-rag/backend/services/events/outbox.py` (`LEAD-0376` / `144_events_outbox.sql`) | `op.events_outbox.publish_replay_prune` | `postgresql;event_delivery` | `8061c88e0c43dd42e735fd012f9ed072df3ef3d6` (`outbox.py:1-482`, `144_events_outbox.sql:1-51`) | `2026-10-15T03:02:11Z` | `9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d` | `PARTIAL_COUNTEREXAMPLE_PROVED` | Unconsumed rows older than 60m in prod PG | `principal`: backend app DB pool & `pro.outbox_prune_daily` launchd; `role`: app runtime; `tenant`: global; `authorization`: PG role + `_CHANNEL_RE` guard (`outbox.py:52`) | `transaction`: `publish()` atomic with caller PG tx (`outbox.py:188-229`); `replay_unconsumed()` per-row dispatch + `acknowledge()` (`lines 356-410`); `retries`: at-least-once within `60m` window (`line 283`); `idempotency`: `_outbox_id` (`BIGSERIAL`) + `WHERE consumed_at IS NULL` (`line 264`) | `failure`: handler raise leaves row unconsumed up to `60m`, after `60m` orphaned forever (`lines 334, 429`); stale payload (`>60m` inner ts) skipped & acked as `*_stale_skip` (`line 391`); `retention`: consumed rows pruned at `30d` (`scripts/outbox-prune.sh:66`); `recovery`: verified `PASS` in `REAL-RUN-RECEIPT.json:63-67` |
| `apps/backend-rag/backend/db/migrations_v2/154_asset_provenance.sql` (`LEAD-0386` / `LEAD-2517`) | `op.provenance.record_and_resolve` | `postgresql;qdrant;sqlite;event_delivery` | `8061c88e0c43dd42e735fd012f9ed072df3ef3d6` (`154_asset_provenance.sql:1-120`) | `2026-10-15T03:02:11Z` | `c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118` | `PARTIAL_COUNTEREXAMPLE_PROVED` | Orphan rate across 12 `asset_kind` values; SQLite vs PG split authority | `principal`: backend/cell writers; `role`: app runtime; `tenant`: global; `authorization`: PG table grants (`154_asset_provenance.sql`) | `transaction`: single-table PG insert + `pg_notify` trigger; `effects`: writes polymorphic `asset_id TEXT` and `parent_provenance_ids UUID[]`; `retries`: caller-dependent; `idempotency`: none on `(asset_kind, asset_id, operation)` | `failure`: dangling cross-store refs undetected at write time; `retention`: weekly orphan-GC cron noted as W2 backlog (`line 38`), unproved; `recovery`: unverified in `restore_drill_verify.py` |
| `apps/backend-rag/backend/db/migrations_v2/264_visa_decision_retention_policy.sql` (`LEAD-0492`) | `op.visa_decision.retain_purge_dsr_hold` | `postgresql` (with cross-store DSR gap to `qdrant;file_state`) | `8061c88e0c43dd42e735fd012f9ed072df3ef3d6` (`264_visa_decision_retention_policy.sql:1-1340`) | `2026-10-15T03:02:11Z` | `9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d` | `PARTIAL_PG_PROVED_CROSSSTORE_OPEN` | Production policy seed status & scheduler cadence (`lines 5-15`) | `principal`: separated policy-writer / privacy operator roles (`lines 51-52, 1194-1210`); `role`: `SECURITY DEFINER` functions with `REVOKE ALL FROM PUBLIC`; `tenant`: `environment IN ('TEST','STAGING','PRODUCTION')`; `authorization`: GUC capability checks (`visa.retention_requested_by`, `visa.dsr_requested_by`, `visa.legal_hold_*`) | `transaction`: strict single-tx atomic delete across `visa_evaluate_idempotency`, `visa_decision_payloads`, `visa_decisions` (`lines 1093-1106`); `effects`: writes aggregate batch receipts (`visa_decision_retention_batches`, `visa_decision_dsr_erasure_batches`); `idempotency`: `FOR UPDATE SKIP LOCKED` / `decision_id` lookup | `failure`: fails closed if no active policy (`lines 145-146`) or if `legal_hold = TRUE` (`line 1087`); `retention`: governed by `visa_decision_retention_policies.retention_interval`; `recovery`: `visa_decisions` and `visa_decision_retention_policies` verified `PASS` in `REAL-RUN-RECEIPT.json:58-73` |
| `apps/backend-rag/backend/services/observability/llm_cost_recorder.py` (`LEAD-1058`) | `op.observability.record_llm_call` | `postgresql;file_state` (+ Prometheus) | `8061c88e0c43dd42e735fd012f9ed072df3ef3d6` (`llm_cost_recorder.py:1-365`) | `2026-10-15T03:02:11Z` | `c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118` | `PARTIAL_COUNTEREXAMPLE_PROVED` | Drift delta between `/data/llm_cost_log.*.jsonl` and PG `llm_cost_events` | `principal`: `nuzantara-rag` process; `role`: app runtime; `tenant`: global; `authorization`: local `/data` volume + PG pool | `transaction`: independent parallel tasks (`asyncio.create_task`, `lines 256-257`); `effects`: `O_APPEND` + `fsync` to JSONL (`lines 166-176`) + `INSERT INTO llm_cost_events` (`lines 191-196`); `retries`: `0`; `idempotency`: none (`request_id` optional, no unique constraint conflict handler in `INSERT`) | `failure`: catches all exceptions, logs warning/critical (`lines 259-297`); `retention`: `DEFAULT_RETENTION_DAYS = 90` declared (`line 58`) but no pruning code exists; `recovery`: no JSONL-to-PG backfill runner |
| `apps/admin-dashboard/app/api/war-room/metrics/costs/route.ts` (`LEAD-0068`) | `op.observability.war_room_costs_read` | `postgresql` | `8061c88e0c43dd42e735fd012f9ed072df3ef3d6` (`route.ts:1-98`) | `2026-10-15T03:02:11Z` | `c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118` | `COUNTEREXAMPLE_PROVED` | Live table presence in all environments | `principal`: admin dashboard server route; `role`: reader; `tenant`: internal admin; `authorization`: admin session | `transaction`: read-only `SELECT` over `war_room_costs` and `war_room_drafts` (`lines 42-68`); `effects`: none; `retries`: `0`; `idempotency`: read-only | `failure`: catches `42P01` (`undefined_table`) and returns HTTP `200` with `grand_total_usd: 0` (`lines 84-89`, false-zero); `retention`: N/A; `recovery`: N/A |
| `apps/backend-rag/backend/services/monitoring/unified_health_service.py` (`LEAD-1042`) | `op.monitoring.unified_health_check` | `postgresql;qdrant;redis` | `8061c88e0c43dd42e735fd012f9ed072df3ef3d6` (`unified_health_service.py:1-250`) | `2026-10-15T03:02:11Z` | `c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118` | `COUNTEREXAMPLE_PROVED` | Live Redis health status when `RedisManager` returns `None` (`status="skipped"`) | `principal`: backend health monitor; `role`: observer; `tenant`: global; `authorization`: `settings.database_url`, `settings.qdrant_url`, `RedisManager` | `transaction`: read-only probes (`SELECT 1` on PG, `ping()` on Redis, lazy init only on Qdrant); `effects`: updates `service_registry` (`lines 110, 146, 187`); `retries`: `5s` in-memory result cache (`line 69`); `idempotency`: read-only | `failure`: `check_qdrant()` (`lines 129-156`) performs zero network I/O and reports `status="ok"` on unreachable Qdrant; `check_redis()` returns `"skipped"` when `RedisManager` client is `None` (`lines 176-182`); `retention`: in-memory only; `recovery`: N/A |
| `scripts/ci/restore_drill_verify.py` (`LEAD-6031` / `mini.restore_drill`) | `op.recovery.restore_drill_verify` | `postgresql` (5 tables only) | `8061c88e0c43dd42e735fd012f9ed072df3ef3d6` (`restore_drill_verify.py:1-506`) | `2026-10-15T03:02:11Z` | `9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d` | `FAILED_OR_CANNOT_VERIFY` | Exact row violation in `clients` and SQL error in `conversations` (`GAP-B08-02`) | `principal`: Mini restore drill runner; `role`: verifier; `tenant`: backup restore DB; `authorization`: local restore PG DSN | `transaction`: read-only verification queries with `statement_timeout = 15000ms` (`line 272`); `effects`: writes JSON report + sidecar (`lines 422-498`); `retries`: `0` (one-run authority exhausted); `idempotency`: deterministic per restored snapshot | `failure`: fail-closed (`exit_code = 2` on `CANNOT-VERIFY`, `exit_code = 1` on `FAIL`, `lines 266-267`); `retention`: ephemeral restore DB + JSON receipt; `recovery`: `REAL-RUN-RECEIPT.json` is `CANNOT-VERIFY` overall (`clients: FAIL`, `conversations: CANNOT-VERIFY`) |

## Adversarial review

A real scoped Codex document review examined source SHA-256 cd9f51be9e6a59e2f545d83d06639274a000d3d02209ff52b9ce9ca3080a388b. R1-DOCUMENT-REVIEW.json records scope, findings and limitations: REVIEWED_PARTIAL_WITH_BLOCKERS, no full-document or implementation approval. Historical wrong counts/paths/authority proposals do not become executable through attribution. The addendum reconciles actual receipts; this is not an independent code grade. Requested supporting seat: Astra 6 / xhigh; effective runtime identity UNOBSERVED. A fresh independent Opus 5.5 / xhigh exact-head BLUE gate remains required.
