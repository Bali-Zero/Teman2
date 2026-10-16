---
adversarial_review: codex
reviewed_source_sha256: "7c1bfb03d900c686ddb9c9f820ebdc23fa0eb868155fbd9a495f64b47c0e7fc9"
review_disposition: HISTORICAL_OR_PENDING_PROPOSAL_NOT_ADMITTED
---

# B01 Proposal — Real-Backup Recovery (`mini.restore_drill`)

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
- **Stage:** `ANALYSIS` (Proposal for `EXECUTION` gate approval)

---

## 1. Development Proposal

All proposed code changes stay strictly inside the `B01` recovery verification perimeter (`scripts/ci/restore_drill_verify.py`, `scripts/restore_drill/run_drill.sh`, `scripts/tests/test_restore_drill_verify.py`, and test fixtures) and obey **"Do not repair client rows"** (`BATTLE.md:4,13`) and **Builder Contract 4 (PII output boundary)**.

### 1.1 Change 1 — Make `_CONVERSATIONS_VIOLATIONS_SQL` Pure-SQL, DDL-Free, and Dual-Type (`JSONB` + `TEXT`)

- **Target:** `scripts/ci/restore_drill_verify.py:207-219`
- **Problem:** `_CONVERSATIONS_VIOLATIONS_SQL` currently defines `CREATE OR REPLACE FUNCTION pg_temp.try_jsonb_array(t text)` and calls `pg_temp.try_jsonb_array(messages)`. On real production backups where `conversations.messages` is `JSONB`, PostgreSQL 17 fails with `ERROR: function pg_temp.try_jsonb_array(jsonb) does not exist (SQLSTATE 42883)`, causing `conversations` to score `CANNOT-VERIFY` (`UNMEASURED_CHECK: 1`). Additionally, `CREATE FUNCTION pg_temp...` is DDL and fails on read-only connections (`REPORT.md:40-41`).
- **Proposed Fix:** Replace `_CONVERSATIONS_VIOLATIONS_SQL` with a single `SELECT` statement using PostgreSQL 17's polymorphic `to_jsonb(anyelement)`, `pg_typeof(any)`, and built-in `pg_input_is_valid(text, text)` (introduced in PostgreSQL 16, standard in `postgres:17-alpine` / `nuzantara/pg-drill:17-postgis` and Fly PG 17):
  ```sql
  SELECT json_build_object(
      'messages_not_json_array',
      (
          SELECT count(*)
          FROM conversations
          WHERE CASE
              WHEN messages IS NULL THEN true
              WHEN pg_typeof(messages) = 'jsonb'::regtype THEN jsonb_typeof(to_jsonb(messages)) <> 'array'
              WHEN pg_input_is_valid(messages::text, 'jsonb') THEN jsonb_typeof(messages::text::jsonb) <> 'array'
              ELSE true
          END
      )
  )::text;
  ```
- **Why this works across all environments:**
  1. **Production / Real Backup (`messages JSONB`):** `pg_typeof(messages) = 'jsonb'::regtype` evaluates to `true`; `to_jsonb(messages)` returns the `jsonb` value directly without text re-parsing; `jsonb_typeof(...) <> 'array'` counts any non-array JSONB value.
  2. **Synthetic CI / Migration 143 (`messages TEXT`):** `pg_typeof(messages) = 'jsonb'::regtype` evaluates to `false`; `pg_input_is_valid(messages::text, 'jsonb')` safely tests whether the text is valid JSONB without raising an exception; if valid, `jsonb_typeof(messages::text::jsonb) <> 'array'` checks the type; if malformed JSON text, the `ELSE true` branch counts the row as a violation without crashing the query.
  3. **Read-Only Connections (`nuzantara_readonly`):** Zero `CREATE FUNCTION` DDL; runs cleanly in `default_transaction_read_only = on`.

### 1.2 Change 2 — Preserve Sanitized `_VIOLATIONS_SQL` Failure Diagnostics in `fetch_live` and `_evaluate_one`

- **Target:** `scripts/ci/restore_drill_verify.py:345-354, 404-418, 456-475`
- **Problem:** When `_run_psql(dsn, _VIOLATIONS_SQL[table])` fails (`rc != 0` or `JSONDecodeError`), `fetch_live` silently discards `rc` and `stderr`, leaving `measurement["violations"] = {}` and masking the SQL error as `check '<name>' could not be measured (missing from result)`.
- **Proposed Fix:**
  - In `fetch_live` (`lines 345-354`), when `rc != 0` or `out` is empty or `json.loads` fails, record a sanitized error summary in `measurement["violations_error"]` (extracting only `rc` and the SQLSTATE / first `ERROR:` line with any literal values redacted, never row contents).
  - In `_evaluate_one` (`lines 404-418`), if `measurement.get("violations_error")` is present while a check is missing from `violations`, include the sanitized error context in the `CANNOT-VERIFY` reason string (keeping `_classify_reason` mapping to `UNMEASURED_CHECK` so existing reason-class consumers remain compatible).

### 1.3 Change 3 — Calibrate `clients` Verification (`_CLIENTS_VIOLATIONS_SQL` & `required_columns`) Without Repairing Client Rows

- **Target:** `scripts/ci/restore_drill_verify.py:109-125, 221-229`
- **Schema Guard (retain Wave 7 improvement):** Keep `"lead_metadata"` in `clients.required_columns` (`["id", "full_name", "status", "client_type", "lead_metadata", "created_at", "updated_at"]`) and update `scripts/tests/test_restore_drill_verify.py` / `scripts/tests/fixtures/restore_drill/healthy.json` to match.
- **Invariant Calibration (governed by `DUX-REQUEST-1` aggregate diagnostic output, zero row mutations):**
  - **If `DUX-REQUEST-1` shows `lead_metadata_not_object > 0`:**
    - As established in `ANALYSIS.md` §1.4, `clients.lead_metadata` was omitted from Migration 243 (`243_jsonb_string_scalar_organism_wide_backfill.sql:402-420`) and has no `CHECK` constraint (`223_clients_lead_metadata.sql:10-11`).
    - Update `lead_metadata_not_object` in `_CLIENTS_VIOLATIONS_SQL` so it accepts the documented pre-existing production JSONB representations without modifying `clients` rows:
      - JSON `'null'::jsonb` (`jsonb_typeof(lead_metadata) = 'null'`, semantically equivalent to SQL `NULL`), and/or
      - Double-encoded JSON object strings (`jsonb_typeof(lead_metadata) = 'string'` where `pg_input_is_valid(lead_metadata #>> '{}', 'jsonb')` and `jsonb_typeof((lead_metadata #>> '{}')::jsonb) = 'object'`), while still flagging any non-object scalar/array corruption.
  - **If `DUX-REQUEST-1` shows `client_type_unknown > 0`:**
    - As established in `ANALYSIS.md` §1.4, `clients.client_type` has no database `CHECK` constraint (`restore_drill_verify.py:109-110`) and `ClientValidator` (`client_core.py:67`) permits arbitrary strings up to `VARCHAR(50)`.
    - Update `client_type_unknown` in `_CLIENTS_VIOLATIONS_SQL` to normalize case/whitespace (`lower(btrim(client_type))`) and allow the exact legacy non-PII enum token set verified in production by `DUX-REQUEST-1` (or non-empty bounded `btrim(client_type) <> ''` if legacy CRM rows use freeform type tags), while still failing on `NULL` or empty/corrupted values.
  - **If both subchecks are non-zero (ruled out for `REAL-RUN-RECEIPT.json` because `VIOLATION: 1`, not `2`, but guarded):** apply both predicate updates.

### 1.4 Change 4 — Emit Sanitized Check-Level Summary in `scripts/restore_drill/run_drill.sh`

- **Target:** `scripts/restore_drill/run_drill.sh:250-264`
- **Problem:** `run_drill.sh` deletes `$WORK_DIR/verify.json` and `$WORK_DIR/verify.err` in `cleanup()` (`line 69`) and logs only `Restore drill verdict=$aggregate backup=$latest bytes=$dump_bytes` (`line 258`). When `aggregate != "PASS"`, operators and receipts cannot see which check key failed inside a relation without re-running a 98-second S3 download + restore.
- **Proposed Fix:** Before `cleanup()` runs, use `jq -c` on `$WORK_DIR/verify.json` to log a single compact, strictly non-PII diagnostic line to `$HOME/logs/mini-restore_drill/run.log` containing only non-`PASS` relation names, `status`, `missing_columns`, and `violations` check-key integer counts (never row data).

### 1.5 Change 5 — Synthetic PG & Unit Test Coverage

- **Target:** `scripts/tests/test_restore_drill_verify.py` and `scripts/tests/fixtures/restore_drill/healthy.json`
- **Proposed Tests:**
  1. Update `healthy.json` and column-list assertions for `clients.required_columns` including `"lead_metadata"`.
  2. Add unit tests for `fetch_live` / `_evaluate_one` when `_VIOLATIONS_SQL` returns `rc != 0` (verifying `UNMEASURED_CHECK` classification + sanitized `violations_error` surfacing).
  3. Add SQL/fixture regression tests covering both `conversations.messages` as `JSONB` (production type) and `conversations.messages` as `TEXT` (Migration 143 synthetic type), plus the calibrated `clients` check predicate.

---

## 2. Admission & Consent Plan for the Next Real-Backup Run

1. **Why a Real-Backup Run Cannot Be Executed Now:**
   - The Wave 7 one-run authorization (`APPROVED_ONE_EXISTING_JOB`) was a single-use consent consumed by the `2026-04-19T14:43:29Z` run (`REAL-RUN-RECEIPT.json:14-16`: `"consent_scope": "One execution of the existing restore/recovery job on Mini"`, `"consent_exhausted": true`).
   - Per `DUX-NOTE-ANALYSIS.md:18` and `BATTLE.md:12`, no new real-backup run may be triggered without explicit new owner consent.
2. **Pre-Run Admission Gate (Must All Be Green Before Requesting/Running Real-Backup Drill):**
   - **Step A (Diagnostic Attribution):** BLUE Dux executes `DUX-REQUEST-1` (read-only aggregate-only query on `nuzantara_readonly`, zero PII) to confirm the exact `clients` subcheck (`client_type_unknown` vs `lead_metadata_not_object`) and `conversations.messages` `udt_name`.
   - **Step B (Implementation & Unit Tests in `EXECUTION` stage):** Apply Changes 1–5 in `~/nuzantara/.worktrees/db-udb-b01-recovery` and pass `pytest -q scripts/tests/test_restore_drill_verify.py`.
   - **Step C (Synthetic PG Parity Proof in `EXECUTION` stage):** Run `restore_drill_verify.py` against a disposable synthetic PostgreSQL 17 instance testing **both** `conversations.messages` as `JSONB` and as `TEXT`, plus the real-world `clients` aggregate shapes from Step A, proving `12/12 PASS`.
   - **Step D (Owner Consent / Scheduled Cadence):** Present the `12/12 PASS` synthetic proof to Zero to authorize one verification run of `~/scripts/mini-restore-drill.sh` on Mini (or allow the next scheduled Sunday `05:30` WITA launchd run after merge to `main`), and capture the non-PII receipt into `~/.organism/last_seen/mini.restore_drill.json`.

---

## DUX-REQUESTS

To move from `ANALYSIS` to `EXECUTION` with zero guesswork on the `clients` `VIOLATION: 1` subcheck attribution, the BLUE Dux (`claude-opus-5-5` `xhigh` on `pro`) is requested to run the following **read-only, aggregate-only, zero-PII** diagnostic query against `nuzantara_readonly` (or against a local read-only schema check) and provide the output in the `EXECUTION` dispatch note:

### `DUX-REQUEST-1` — Read-Only Aggregate Attribution for `clients` and `conversations` (Zero PII)

```sql
SELECT json_build_object(
    'conversations_messages_udt', (
        SELECT udt_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'conversations'
          AND column_name = 'messages'
    ),
    'conversations_non_array_count', (
        SELECT count(*)
        FROM public.conversations
        WHERE CASE
            WHEN messages IS NULL THEN true
            WHEN pg_typeof(messages) = 'jsonb'::regtype THEN jsonb_typeof(to_jsonb(messages)) <> 'array'
            WHEN pg_input_is_valid(messages::text, 'jsonb') THEN jsonb_typeof(messages::text::jsonb) <> 'array'
            ELSE true
        END
    ),
    'clients_type_unknown_exact_count', (
        SELECT count(*)
        FROM public.clients
        WHERE client_type NOT IN ('individual', 'company')
    ),
    'clients_type_unknown_normalized_count', (
        SELECT count(*)
        FROM public.clients
        WHERE client_type IS NULL
           OR lower(btrim(client_type)) NOT IN ('individual', 'company')
    ),
    'clients_type_null_or_blank_count', (
        SELECT count(*)
        FROM public.clients
        WHERE client_type IS NULL
           OR btrim(client_type) = ''
    ),
    'clients_type_distinct_count', (
        SELECT count(DISTINCT lower(btrim(client_type)))
        FROM public.clients
    ),
    'clients_lead_metadata_not_object_count', (
        SELECT count(*)
        FROM public.clients
        WHERE lead_metadata IS NOT NULL
          AND jsonb_typeof(lead_metadata) <> 'object'
    ),
    'clients_lead_metadata_typeof_dist', (
        SELECT COALESCE(json_object_agg(t, c), '{}'::json)
        FROM (
            SELECT COALESCE(jsonb_typeof(lead_metadata), 'sql_null') AS t,
                   count(*) AS c
            FROM public.clients
            GROUP BY 1
        ) s
    ),
    'clients_lead_metadata_string_valid_object_count', (
        SELECT count(*)
        FROM public.clients
        WHERE lead_metadata IS NOT NULL
          AND jsonb_typeof(lead_metadata) = 'string'
          AND pg_input_is_valid(lead_metadata #>> '{}', 'jsonb')
          AND jsonb_typeof((lead_metadata #>> '{}')::jsonb) = 'object'
    )
)::text;
```

- **Why this query is strictly PII-safe:** Every field in the output JSON is either a PostgreSQL catalog type name (`udt_name`), a `jsonb_typeof` category (`object`, `string`, `array`, `null`, `boolean`, `number`, `sql_null`), or an integer `count(*)`. No row IDs, no client names, no emails, no phone numbers, and no free-text column values can ever be emitted.

### `DUX-REQUEST-2` — Stage Gate Authorization for `EXECUTION`

- Upon providing the `DUX-REQUEST-1` aggregate JSON, authorize `B01` to enter `EXECUTION` to apply Changes 1–5 in `~/nuzantara/.worktrees/db-udb-b01-recovery` and run `pytest -q scripts/tests/test_restore_drill_verify.py`.

## Adversarial review

Scoped Codex document review, parent receipt [`R1-DOCUMENT-REVIEW.json`](R1-DOCUMENT-REVIEW.json) (observed 2026-10-15T16:54:26Z): `HISTORICAL_OR_PENDING_PROPOSAL_NOT_ADMITTED` for this file's bytes with SHA256 `7c1bfb03d900c686ddb9c9f820ebdc23fa0eb868155fbd9a495f64b47c0e7fc9` at base `8061c88e0c43dd42e735fd012f9ed072df3ef3d6`. Bounded excerpts only: not a full document or code review, not implementation approval, not the final BLUE gate. Requested seat Astra 6/xhigh; effective runtime identity not observed. Edits after the reviewed bytes (addendum) apply its findings and were not re-reviewed.
