---
adversarial_review: codex
reviewed_source_sha256: "d0a1438f4b7118e64096547f6aeabea174ba9c6bc93ecc3d490513a06a387916"
review_disposition: PARTIAL_DOCUMENTATION_REQUIRES_RECONCILIATION
---

# B01 Analysis — Real-Backup Recovery (`mini.restore_drill`)

> **Dux addendum (2026-10-16, supersedes every conflicting statement below).** Authoritative status and evidence:
> `RESULT.json`. The only real-backup run of record is the 2026-10-15 run (started 03:00:43Z, terminal 03:02:11Z, 5 relations):
> aggregate CANNOT-VERIFY, `conversations` CANNOT-VERIFY (UNMEASURED_CHECK), `clients` FAIL (VIOLATION), `visa_decisions`,
> `events_outbox` and `visa_decision_retention_policies` PASS (raw-report sha256 `1d368c2d16d32a0834bb7d120d75005423227b77239107b1dc1873f8140b5744`;
> no rows, counts or raw errors exported). Any other run date, a 10/12 or 12/12 relation count, and any quoted consent field
> not in that receipt are withdrawn as unsupported. The five invariants and the strict `clients` predicate are unchanged;
> widening `clients` semantics is rejected. Option 2A (production backfill in S2+ before B01 closure) is a dependency cycle
> with S1 and is not adopted. Owner consent of 2026-10-16 ("continua") admits only boolean-only diagnostics, installation of
> the independently gated candidate with reviewed pins, and EXACTLY ONE isolated restore of an existing backup; it grants no
> client-row remediation, invariant change, repeat run or new backup. `block_closed` stays `false` until all five invariants
> are measured PASS on that run.

- **Campaign ID:** `universal-db-wave8-20261015`
- **Block ID:** `B01` — Real-backup recovery
- **Mission Colour & Gear:** `BLUE` · `GEAR3`
- **Host & Seat:** `[Mini]` · `gemini-4-argon` (`high`) — `EXTERNAL PREPARER, NO_DUX` (Appointed BLUE Dux: `claude-opus-5-5` `xhigh` on `pro`)
- **Worktree:** `~/nuzantara/.worktrees/db-udb-b01-recovery`
- **Base Commit:** `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`
- **Stage:** `ANALYSIS` (read-only analysis; no code mutations, no native probes, no real-backup execution)

---

## 0. Scoped Frozen Inputs Verification

All scoped inputs enumerated in `.agent-receipts/udb-wave8-inputs/INPUT-MANIFEST.json:1-47` and the block notes were read directly from disk:

| Input Artifact          | Path                                                          | Verified SHA-256 / Ref                                             | Role in B01                                                                     |
| :---------------------- | :------------------------------------------------------------ | :----------------------------------------------------------------- | :------------------------------------------------------------------------------ |
| `DUX-NOTE-ANALYSIS.md`  | `research/operations/udb-wave8/B01/DUX-NOTE-ANALYSIS.md:1-31` | Base `8061c88e`                                                    | Stage mandate, boundaries, `DUX-REQUESTS` protocol                              |
| `BATTLE.md`             | `research/operations/udb-wave8/B01/BATTLE.md:1-31`            | Base `8061c88e`                                                    | Campaign/block contract, sibling schema, stop rules                             |
| `REPORT.md`             | `.agent-receipts/udb-wave8-inputs/REPORT.md:1-146`            | `d289fb8660a6bd634cb7785fef3a8c0b47ceefe82463d134c4bbf66dc0563e9a` | Wave 7 executive report & Section 5 recovery state                              |
| `STATE.json`            | `.agent-receipts/udb-wave8-inputs/STATE.json:1-134`           | `caaebbbac9703bf5ebd5f7624b8a2dd6759a2e508703f311cecffebf1c0967d4` | Wave 7 organ inventory, synthetic PG vs real run state                          |
| `FINAL-BLUE-GATE.json`  | `.agent-receipts/udb-wave8-inputs/FINAL-BLUE-GATE.json:1-128` | `b9d284e1dba9e87ad340cbd4076061e7a35a93fdf8bc1c910340e6099d711856` | Wave 7 gate verdict (`HOLD`) & candidate patch assessment                       |
| `REAL-RUN-RECEIPT.json` | `.agent-receipts/udb-wave8-inputs/REAL-RUN-RECEIPT.json:1-84` | `9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d` | Authorized one-run real-backup receipt (`FAIL`)                                 |
| `research-lines.csv`    | `.agent-receipts/udb-wave8-inputs/research-lines.csv:1-20`    | `1b3d1f31df997500975311d3f49cbd3a50346c2fa7d27f45ff808c7203654c10` | `D14` Recovery, retention and security rubric                                   |
| `ASTRA-ADVICE.md`       | `.agent-receipts/udb-wave8-inputs/ASTRA-ADVICE.md:1-12`       | `72f349f285bc681013b67ad1d25cdad54d3d4478080dc1f5e7e0512dd9e1fdb8` | Strategic priorities (`B01` #4: `clients` FAIL + `conversations` CANNOT-VERIFY) |
| `consumer-matrix.csv`   | `.agent-receipts/udb-wave8-inputs/consumer-matrix.csv:1-120`  | `c09e14328f391d2615d320b6dc4218bf35a37e76fb847c46659a8db0f9326118` | Cross-consumer operation matrix for `clients` and `conversations`               |

---

## 1. Verified Facts

### 1.1 Anatomy of the `mini.restore_drill` Organ

1. **Organ Registry (`apps/organism/organism/organs_registry.yaml:2806-2827`):**
   - `id: mini.restore_drill`, `runtime: mini_launchd`, `label: com.nuzantara.restore-drill`, `cadence_seconds: 604800` (Sunday `05:30` WITA), `critical: false`, `recovery_action: human_only`.
   - `owner_module: infra/launchagents/wrappers/mini-restore-drill.sh`.
   - `bridge_source.path: ~/.organism/last_seen/mini.restore_drill.json` (`fresh_Multiplier: 1.5`).
2. **LaunchAgent Wrapper (`infra/launchagents/wrappers/mini-restore-drill.sh:1-156`):**
   - Mirrors `~/scripts/mini-restore-drill.sh` on Mini (`STATE.json:28-29`).
   - Resolves `REPO` via `git rev-parse --show-toplevel` or falls back to `$HOME/nuzantara` (`lines 15-18`) and executes `PAYLOAD="$REPO/scripts/restore_drill/run_drill.sh"` (`lines 19, 128`).
   - Writes structured receipt JSON to `~/.organism/last_seen/mini.restore_drill.json` (`lines 69-102`), telemetry JSONL to `~/.Ptah_telemetry/crontab_runs.jsonl` (`lines 55-67`), and alert queue entries on non-zero exit (`lines 104-126`).
3. **Payload Script (`scripts/restore_drill/run_drill.sh:1-305`):**
   - Selects the newest `nuzantara-fly-YYYYMMDD-HHMM.sql.gz` from `s3://nuzantara-backups/postgres/` (`lines 91-125`), enforcing `MAX_BACKUP_AGE_HOURS=72` (`lines 29, 144-156`) and `MIN_GZIP_BYTES=100000` (`lines 28, 165-171`).
   - Starts disposable container `nuzantara-pg-restore-drill` from `nuzantara/pg-drill:17-postgis` (`scripts/restore_drill/Dockerfile:1-12`) bound to `127.0.0.1:15499` (`lines 24-26, 179-211`).
   - Pre-creates stub roles parsed from the dump via `scripts/restore_drill/role_scanner.py:1-268` (`run_drill.sh:214-224`).
   - Restores the dump with `gunzip -c "$dump_path" | psql "$dsn" -v ON_ERROR_STOP=1 >"$restore_log" 2>&1` (`line 232`).
   - Invokes the semantic verifier:
     ```bash
     python3 "$REPO_ROOT/scripts/ci/restore_drill_verify.py" --dsn "$dsn" --json >"$WORK_DIR/verify.json" 2>"$WORK_DIR/verify.err"
     ```
     (`lines 251-252`).
   - Extracts only `.aggregate` (`PASS` / `FAIL` / `CANNOT-VERIFY`) via `jq -r '.aggregate // "CANNOT-VERIFY"' "$WORK_DIR/verify.json"` (`line 254`) and logs only `Restore drill verdict=$aggregate backup=$latest bytes=$dump_bytes` (`line 258`).
   - **Critical observability gap (`run_drill.sh:66-76`):** `trap cleanup EXIT INT TERM` runs `rm -rf "$WORK_DIR"`, which permanently deletes both `$WORK_DIR/verify.json` and `$WORK_DIR/verify.err` on exit without persisting sanitized check-level violation counts or error classes to `$HOME/logs/mini-restore_drill/run.log`.

### 1.2 What the Authorized Real-Backup Run Proved (`REAL-RUN-RECEIPT.json`)

1. **Execution provenance (`REAL-RUN-RECEIPT.json:1-31`):**
   - Executed once on `2026-04-19T14:43:29Z` → `2026-04-19T14:45:07Z` (`98s`) on Mini under one-time owner authorization `APPROVED_ONE_EXISTING_JOB` (`consent_exhausted: true`).
   - Restored real backup `nuzantara-fly-20260419-1801.sql.gz` (`85,848,479` bytes compressed) cleanly (`psql -v ON_ERROR_STOP=1` succeeded; post-run container cleanup confirmed, `lingering_containers: 0`).
2. **Per-relation outcomes (`REAL-RUN-RECEIPT.json:32-78`):**
   - **10 of 12 critical relations scored `PASS`:** `alembic_version`, `articles`, `Audit_log`, `collective_memories`, `documents`, `episodic_memories`, `kg_edges`, `kg_nodes`, `practices`, `users`.
   - **`clients` scored `FAIL`:** `reason_classes: {"VIOLATION": 1}` (`REAL-RUN-RECEIPT.json:33-39`).
   - **`conversations` scored `CANNOT-VERIFY`:** `reason_classes: {"UNMEASURED_CHECK": 1}` (`REAL-RUN-RECEIPT.json:41-47`).
   - **Aggregate verdict:** `FAIL` (exit code `1`), because `aggregate_verdict` returns `FAIL` whenever any relation has `status == "FAIL"` (`scripts/ci/restore_drill_verify.py:430-436`).

### 1.3 Verified Codebase Facts on `conversations` (`UNMEASURED_CHECK: 1`)

1. **Migration vs. Production Schema Divergence:**
   - `apps/backend-rag/backend/db/migrations_v2/143_legacy_conversations.sql:11-26` defines:
     ```sql
     -- Idempotent: CREATE TABLE IF NOT EXISTS — no-op on prod (table predates the
     -- v2 runner, was created by hand).
     CREATE TABLE IF NOT EXISTS conversations (
         id SERIAL PRIMARY KEY,
         user_id VARCHAR(255) NOT NULL,
         messages TEXT NOT NULL DEFAULT '[]',
         ...
     ```
   - Because `conversations` pre-existed on production (`nuzantara-postgres`), migration `143` was a no-op on production (`143_legacy_conversations.sql:12-13`).
   - On production (`nuzantara-postgres`), `public.conversations.messages` is `JSONB`, not `TEXT`. This is independently verified across four codebase locations:
     1. `apps/backend-rag/backend/app/routers/conversations.py:258`: `INSERT INTO conversations (user_id, session_id, messages, metadata, created_at) VALUES ($1, $2, $3::text::jsonb, $4::text::jsonb, $5)`.
     2. `apps/backend-rag/backend/app/routers/conversations.py:531`: `SUM(jsonb_array_length(messages)) as total_messages` — `jsonb_array_length(jsonb)` has no `text` overload in PostgreSQL and would fail at runtime if `messages` were `TEXT`.
     3. `apps/backend-rag/backend/db/migrations_v2/243_jsonb_string_scalar_organism_wide_backfill.sql:375-384`: targets `table_name = 'conversations' AND column_name = 'messages' AND udt_name = 'jsonb'`.
     4. `apps/backend-rag/backend/tests/db/test_jsonb_double_encoding_class_guard.py:83`: lists `"conversations": ("messages", "metadata")` under `PROTECTED_JSONB_COLUMNS`.
2. **Verifier Implementation (`scripts/ci/restore_drill_verify.py:99-108, 207-219`):**
   - Comment at `lines 99-101` states: `Migration 143 declares messages as TEXT NOT NULL DEFAULT '[]' (not JSONB), so jsonb_typeof(messages) fails when any row holds malformed JSON. Wrap the cast in a pg_temp helper so bad rows count as violations instead of crashing the query.`
   - `_CONVERSATIONS_VIOLATIONS_SQL` (`lines 207-218`) executes:
     ```sql
     CREATE OR REPLACE FUNCTION pg_temp.try_jsonb_array(t text) RETURNS boolean
     LANGUAGE plpgsql IMMUTABLE AS $$
     BEGIN
         RETURN jsonb_typeof(t::jsonb) = 'array';
     EXCEPTION WHEN others THEN
         RETURN false;
     END $$;
     SELECT json_build_object(
         'messages_not_json_array',
         (SELECT count(*) FROM conversations WHERE NOT pg_temp.try_jsonb_array(messages))
     )::text;
     ```

### 1.4 Verified Codebase Facts on `clients` (`VIOLATION: 1`)

1. **Verifier Specification (`scripts/ci/restore_drill_verify.py:109-125, 221-229`):**
   - `clients` checks two violation keys in `_CLIENTS_VIOLATIONS_SQL` (`lines 221-229`):
     - `'client_type_unknown'`: `(SELECT count(*) FROM clients WHERE client_type NOT IN ('individual','company'))`
     - `'lead_metadata_not_object'`: `(SELECT count(*) FROM clients WHERE lead_metadata IS NOT NULL AND jsonb_typeof(lead_metadata) <> 'object')`
2. **Schema & Writer Surface for `clients.lead_metadata`:**
   - Added by `apps/backend-rag/backend/db/migrations_v2/223_clients_lead_metadata.sql:10-11`: `ADD COLUMN IF NOT EXISTS lead_metadata JSONB DEFAULT NULL` (no `CHECK (jsonb_typeof(lead_metadata) = 'object')` constraint).
   - Written by `scripts/lead_intent_matcher.py:424-441`: `SET lead_metadata = COALESCE(lead_metadata, '{}'::jsonb) || $1::jsonb` where `json.dumps(metadata_patch)` is bound as `$1`.
   - **Omission in Migration 243 (`apps/backend-rag/backend/db/migrations_v2/243_jsonb_string_scalar_organism_wide_backfill.sql:402-420`):** Migration 243 repaired double-encoded JSONB string scalars (`jsonb_typeof(col) = 'string'`) across 27 tables, and on `clients` (`lines 403-419`) it repaired `passport_ocr_data` and `custom_fields`, **but omitted `clients.lead_metadata`** (and `test_jsonb_double_encoding_class_guard.py:84` also only lists `"clients": ("custom_fields", "passport_ocr_data")`). Additionally, any row where `lead_metadata` holds JSON `'null'::jsonb` (`lead_metadata IS NOT NULL AND jsonb_typeof(lead_metadata) = 'null'`) fails `jsonb_typeof(lead_metadata) <> 'object'`.
3. **Schema & Writer Surface for `clients.client_type`:**
   - As documented in `restore_drill_verify.py:109-110`, `clients.client_type` has no database `CHECK` constraint (`VARCHAR(50) DEFAULT 'individual'`).
   - While router `CreateClientRequest` (`apps/backend-rag/backend/app/routers/crm_clients.py:280-286`) validates `v not in ("individual", "company")`, `ClientValidator` in `apps/backend-rag/backend/services/crm/client_core.py:67` declares `client_type: str = "individual"` with **no `@field_validator("client_type")`** (`lines 60-136`), and `ClientBase` in `apps/backend-rag/backend/app/modules/crm/models.py:55` declares `client_type: str = Field(default="individual", max_length=50)` with no enum restriction.

---

## 2. Counterexamples

### Counterexample 1 — Why the Wave 7 Candidate Patch (`lead_metadata` in `required_columns`) Cannot Resolve `clients: FAIL`

- **Hypothesis tested:** The dirty worktree candidate patch described in `FINAL-BLUE-GATE.json:116-117` (adding `"lead_metadata"` to `clients.required_columns` in `scripts/ci/restore_drill_verify.py:113-120`) resolves the `clients` failure.
- **Refutation from `restore_drill_verify.py` & `REAL-RUN-RECEIPT.json`:**
  1. In `fetch_live` (`scripts/ci/restore_drill_verify.py:338-347`), `missing_cols = [c for c in spec["required_columns"] if c not in present_cols]`. If `missing_cols` is non-empty, `_VIOLATIONS_SQL` is skipped (`if not missing_cols and spec["checks"]:`) and `_evaluate_one` (`lines 391-403`) returns `status = "CANNOT-VERIFY"` with reason class `MISSING_COLUMN` (`_classify_reason`, `line 465`).
  2. In `REAL-RUN-RECEIPT.json:33-39`, `clients` did **not** score `CANNOT-VERIFY` (`MISSING_COLUMN` or `UNMEASURED_CHECK`); it scored `status: "FAIL"` with `reason_classes: {"VIOLATION": 1}`.
  3. By `_evaluate_one` (`lines 404-427`), a `VIOLATION` reason is emitted if and only if `_CLIENTS_VIOLATIONS_SQL` executed with `rc == 0`, returned valid JSON containing both `'client_type_unknown'` and `'lead_metadata_not_object'`, and exactly one of those two integer counts was `> 0` while the other was `0`.
  4. Therefore, `lead_metadata` already existed on the restored `clients` table in `nuzantara-fly-20260419-1801.sql.gz`. Adding `"lead_metadata"` to `required_columns` is a sound schema guard when `lead_metadata` is absent, but on the real backup it changes nothing about the `FAIL` (`VIOLATION: 1`) outcome.

### Counterexample 2 — Why Synthetic PG Passed `conversations` (`STATE.json:61`) While Real Backup Scored `CANNOT-VERIFY` (`UNMEASURED_CHECK: 1`)

- **Hypothesis tested:** Passing `restore_drill_verify.py` against a synthetic PostgreSQL 17 instance seeded from `migrations_v2` (`STATE.json:61`) proves `_CONVERSATIONS_VIOLATIONS_SQL` works on real production backups.
- **Refutation:**
  1. Synthetic PG builds `conversations` from `143_legacy_conversations.sql:18`, where `messages` has type `TEXT`. Calling `pg_temp.try_jsonb_array(messages)` invokes `pg_temp.try_jsonb_array(text)` (`restore_drill_verify.py:208`) with an exact type match.
  2. In the real production backup (`nuzantara-fly-20260419-1801.sql.gz`), `conversations.messages` has type `JSONB` (proven by `conversations.py:258,531` and `243_jsonb_string_scalar_organism_wide_backfill.sql:381`).
  3. In PostgreSQL 17's `pg_cast` catalog, the cast from `jsonb` to `text` has `castcontext = 'a'` (assignment only), **not** `castcontext = 'i'` (implicit). PostgreSQL function call resolution does not apply assignment casts to match `pg_temp.try_jsonb_array(t text)` when passed a `jsonb` argument.
  4. Consequently, `SELECT count(*) FROM conversations WHERE NOT pg_temp.try_jsonb_array(messages)` fails immediately in PostgreSQL with:
     `ERROR: function pg_temp.try_jsonb_array(jsonb) does not exist (SQLSTATE 42883)`.
  5. Additionally, because `_CONVERSATIONS_VIOLATIONS_SQL` executes `CREATE OR REPLACE FUNCTION pg_temp.try_jsonb_array(...)` (DDL), it cannot run on read-only sessions (`default_transaction_read_only = on`) and had to be skipped during the Wave 7 live read-only check (`REPORT.md:40-41`).

### Counterexample 3 — Why `fetch_live` Masks Query Errors as `UNMEASURED_CHECK`

- **Hypothesis tested:** `restore_drill_verify.py` distinguishes between a missing JSON key and a failed/timed-out SQL query.
- **Refutation (`scripts/ci/restore_drill_verify.py:345-354, 404-418`):**
  ```python
  if not missing_cols and spec["checks"]:
      rc, out, _ = _run_psql(dsn, _VIOLATIONS_SQL[table])
      if rc == 0 and out:
          try:
              measurement["violations"] = json.loads(out.splitlines()[-1])
          except json.JSONDecodeError:
              measurement["violations"] = {}
  ```
  - When `_run_psql` returns `rc != 0` (such as `SQLSTATE 42883` on `conversations` or `rc == 124` on `subprocess.TimeoutExpired` at `line 263`), `stderr` (`_`) and `rc` are discarded, `measurement["violations"]` is left empty, and `_evaluate_one` (`lines 406-409`) emits `"check 'messages_not_json_array' could not be measured (missing from result)"` (`UNMEASURED_CHECK`).
  - Furthermore, `run_drill.sh:69` deletes `$WORK_DIR/verify.json` and `$WORK_DIR/verify.err` on exit, leaving only reason-class tallies in `REAL-RUN-RECEIPT.json`.

### Counterexample 4 — Why `_CLIENTS_VIOLATIONS_SQL` Fires on Production Data Without Restore Corruption

- **Hypothesis tested:** Any non-zero count in `_CLIENTS_VIOLATIONS_SQL` indicates backup/restore corruption of `clients`.
- **Refutation:**
  - `REAL-RUN-RECEIPT.json:37` shows `reason_classes: {"VIOLATION": 1}` across the 2 checks on `clients`, meaning **strictly one** check returned `> 0` and the other returned `0`:
    - **Case A (`lead_metadata_not_object > 0`, `client_type_unknown == 0`):** `clients.lead_metadata` has no `CHECK` constraint (`223_clients_lead_metadata.sql:10-11`) and was excluded from Migration 243's JSONB string-scalar backfill (`243_jsonb_string_scalar_organism_wide_backfill.sql:402-420`). Any pre-existing row in production where `lead_metadata` is `'null'::jsonb` (`jsonb_typeof = 'null'`) or a double-encoded JSON object string (`jsonb_typeof = 'string'`) causes `lead_metadata IS NOT NULL AND jsonb_typeof(lead_metadata) <> 'object'` to fire in the restored dump even though the restore is bit-for-bit faithful to production.
    - **Case B (`client_type_unknown > 0`, `lead_metadata_not_object == 0`):** `clients.client_type` has no database `CHECK` constraint (`restore_drill_verify.py:109-110`) and `ClientValidator` (`client_core.py:67`) does not restrict `client_type` to `('individual', 'company')`. Any legacy/imported/system row in production with casing or token variance (e.g., `'corporate'`, `'business'`, `'Individual'`, `''`) causes `client_type NOT IN ('individual','company')` to fire on a faithful restore.
  - Under the hard mandate constraint **"Do not repair client rows"** (`BATTLE.md:4,13`), `restore_drill_verify.py` must validate the actual production invariant rather than rejecting pre-existing un-constrained production shapes.

---

## 3. Sibling Contract & Operation Instance Mapping (`B01`, Dependencies `B04`, `B07`)

Per `BATTLE.md` §3, `B01` reuses the frozen sibling schema without modification:

### 3.1 Frozen Record Fields

| consumer_id                                                                                                                                                | operation_id            | store_id                                                                                     | source_version                             | evidence_timestamp     | evidence_sha256                                                    | status                                                                                           | unknowns                                                                                                                                               |
| :--------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------------- | :------------------------------------------------------------------------------------------- | :----------------------------------------- | :--------------------- | :----------------------------------------------------------------- | :----------------------------------------------------------------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `mini.restore_drill` (`infra/launchagents/wrappers/mini-restore-drill.sh` -> `scripts/restore_drill/run_drill.sh` -> `scripts/ci/restore_drill_verify.py`) | `OP-B01-RESTORE-VERIFY` | `pg.nuzantara_backups_s3_to_pg_drill_17_postgis` (`127.0.0.1:15499/nuzantara_Restore_drill`) | `8061c88e0c43dd42e735fd012f9ed072df3ef3d6` | `2026-04-19T14:45:07Z` | `9851ae0521ada6d52b2391f906543300ab6111cd9e3a11ca42797a86ed248d0d` | `FAIL` (`10 PASS`, `clients=FAIL/VIOLATION:1`, `conversations=CANNOT-VERIFY/UNMEASURED_CHECK:1`) | Which of the 2 `clients` subchecks (`client_type_unknown` vs `lead_metadata_not_object`) produced the single `VIOLATION: 1` in `REAL-RUN-RECEIPT.json` |

### 3.2 Operation Instance Fields (`OP-B01-RESTORE-VERIFY`)

| Field           | Verified Value (`file:line`)                                                                                                                                                                                                                                                                                                                                                               |
| :-------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `principal`     | Local macOS user `nuzantara` on `Mini` via launchd agent `com.nuzantara.restore-drill` (`apps/organism/organism/organs_registry.yaml:2806-2820`)                                                                                                                                                                                                                                           |
| `role`          | Ephemeral PostgreSQL superuser `postgres` inside disposable container `nuzantara-pg-restore-drill` (`127.0.0.1:15499`), plus stub roles scanned via `scripts/restore_drill/role_scanner.py:1-268` (`scripts/restore_drill/run_drill.sh:25,214-224`)                                                                                                                                        |
| `tenant`        | System-wide backup verification across all 12 critical relations; connects to sibling `B04` (`clients` schema/legacy writers) and `B07` (`conversations` / `lead_metadata` JSONB contract)                                                                                                                                                                                                 |
| `authorization` | Scheduled weekly cron (`604800s`) under launchd; manual out-of-cadence real-backup execution requires explicit owner consent (`APPROVED_ONE_EXISTING_JOB` exhausted on `2026-04-19T14:45:07Z`, `REAL-RUN-RECEIPT.json:7-16`)                                                                                                                                                               |
| `transaction`   | Restore phase: single stream `gunzip -c "$dump_path" \| psql "$dsn" -v ON_ERROR_STOP=1` (`run_drill.sh:232`). Verify phase: per-query autocommit `psql -X -A -t -v ON_ERROR_STOP=1` (`restore_drill_verify.py:249-266`)                                                                                                                                                                    |
| `effects`       | Downloads newest `s3://nuzantara-backups/postgres/nuzantara-fly-*.sql.gz` to `mktemp -d`, starts ephemeral container `nuzantara-pg-restore-drill`, restores dump, runs `restore_drill_verify.py`, writes `~/.organism/last_seen/mini.restore_drill.json` and `~/.Ptah_telemetry/crontab_runs.jsonl`, removes temp dir and container (`run_drill.sh:66-76`, `mini-restore-drill.sh:55-102`) |
| `retries`       | `recovery_action: human_only` (`organs_registry.yaml:2813`); no automatic retry on failure; Pg readiness loop polls `pg_isready` up to 30 iterations × 1s (`run_drill.sh:198-211`)                                                                                                                                                                                                         |
| `idempotency`   | Pre-run `docker rm -f "$CONTAINER_NAME"` (`run_drill.sh:180`) + fresh `mktemp -d` (`line 64`) + `trap cleanup EXIT INT TERM` (`line 76`); receipt overwrites `~/.organism/last_seen/mini.restore_drill.json` atomically via `.tmp.$$` (`mini-restore-drill.sh:100-101`)                                                                                                                    |
| `failure`       | Fail-closed: exit code `1` on `FAIL`, `2` on `CANNOT-VERIFY` (`restore_drill_verify.py:495-501`, `run_drill.sh:260-269`); wrapper queues critical alert to `~/.organism/alert_queue.jsonl` (`mini-restore-drill.sh:104-126`)                                                                                                                                                               |
| `retention`     | Ephemeral container and `$WORK_DIR` (`dump.sql.gz`, `restore.log`, `verify.json`, `verify.err`) are deleted immediately on exit (`run_drill.sh:66-74`); S3 backup retention enforced at `<= 72h` freshness (`run_drill.sh:29,144-156`); local receipt retained at `~/.organism/last_seen/mini.restore_drill.json`                                                                          |
| `recovery`      | `human_only` (`organs_registry.yaml:2813`); requires code fix in `scripts/ci/restore_drill_verify.py` + `scripts/restore_drill/run_drill.sh`, synthetic PG verification (`B01`), and owner-consented or scheduled weekly Sunday `05:30` WITA real-backup run                                                                                                                               |

---

## 4. Missing Evidence & Unknowns

1. **Exact attribution of `clients` `VIOLATION: 1` between the two subchecks (`client_type_unknown` vs `lead_metadata_not_object`):**
   - Because `run_drill.sh:69` deleted `$WORK_DIR/verify.json` on exit and `REAL-RUN-RECEIPT.json:33-39` preserved only `reason_classes: {"VIOLATION": 1}`, the frozen inputs do not record whether the single violated check in `clients` is `client_type_unknown` or `lead_metadata_not_object`.
   - Resolving this requires **one read-only aggregate shape query** (zero PII, returning only integer counts, `jsonb_typeof(lead_metadata)` distribution, and known/non-PII `client_type` token characteristics) executed by the BLUE Dux against `nuzantara_readonly` (or against a local non-PII diagnostic check), as specified in `PROPOSAL.md` (`## DUX-REQUESTS`).
2. **Owner consent for a second out-of-cadence real-backup run:**
   - The Wave 7 one-run authorization (`APPROVED_ONE_EXISTING_JOB`) was consumed by the `2026-04-19T14:43:29Z` run (`REAL-RUN-RECEIPT.json:14-16`). A second manual real-backup execution of `mini.restore_drill` requires fresh owner consent (or waiting for the scheduled Sunday `05:30` WITA launchd run after the verifier fix is merged to `main`).

## Adversarial review

Scoped Codex document review, parent receipt [`R1-DOCUMENT-REVIEW.json`](R1-DOCUMENT-REVIEW.json) (observed 2026-10-15T16:54:26Z): `PARTIAL_DOCUMENTATION_REQUIRES_RECONCILIATION` for this file's bytes with SHA256 `d0a1438f4b7118e64096547f6aeabea174ba9c6bc93ecc3d490513a06a387916` at base `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`. Bounded excerpts only: not a full document or code review, not implementation approval, not the final BLUE gate. Requested seat Astra 6/xhigh; effective runtime identity not observed. Edits after the reviewed bytes (addendum) apply its findings and were not re-reviewed.
