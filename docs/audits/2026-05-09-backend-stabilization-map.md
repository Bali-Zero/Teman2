# Backend Stabilization Map - 2026-05-09

Scope: stop coverage expansion and map the real backend failures surfaced by the full `apps/backend-rag` run.

## Current Signal

Full backend run from `apps/backend-rag`:

- Command: `source .venv/bin/activate && PYTHONPATH=. coverage run -m pytest -q --tb=short --disable-warnings`
- Result: `13075 passed`, `806 skipped`, `9 failed`, `2 errors`
- Coverage after failed-but-complete collection: `68.57%`

The failing tests are not random coverage gaps. They cluster around live Postgres schema drift, migration bookkeeping drift, and cleanup/fixture isolation.

## Failure Clusters

### S1 - `clients` delete breaks because `crm_guardian_events` still has blocking rules

Symptoms:

- `backend/tests/app/routers/test_compliance_alerts_router.py`
- `backend/tests/integration/test_partners_e2e.py`
- `backend/tests/services/crm/partners/test_emails.py`

Representative error:

```text
asyncpg.exceptions.InternalServerError:
referential integrity query on "clients" from constraint
"crm_guardian_events_client_id_fkey" on "crm_guardian_events" gave unexpected result
HINT: This is most likely due to a rule having rewritten the query.
```

Direct DB evidence:

- `pg_rewrite` still contains:
  - `crm_guardian_events_no_delete`
  - `crm_guardian_events_no_update`
- `schema_migrations` contains migration `140_drop_crm_guardian_events_no_update_delete_rules`
- `_schema_versions` has no row for migration `140`

Root-cause hypothesis:

`140_drop_crm_guardian_events_no_update_delete_rules.sql` is the right physical migration, but the local DB ledger is split. `MigrationManager` discovers pending migrations from `_schema_versions`, while `BaseMigration.apply()` skips when `schema_migrations` says a migration is already applied. This lets migration `140` be recorded in the legacy ledger while its physical rule-drop effect is absent.

Impact:

Any test fixture that inserts into `clients` and later deletes the row can fail in teardown. That turns passing tests into errors and leaves test data behind.

### S2 - Migration `132_legacy_lkpm_reports` is not idempotent against a pre-existing partial `lkpm_reports`

Symptoms:

- `backend/tests/db/test_migration_114_115_116_roundtrip.py::test_apply_all_pending_creates_compliance_chain`

Representative error:

```text
SQL execution failed: column "cumulative_equipment_domestic" of relation "lkpm_reports" does not exist
```

Direct DB evidence:

- `lkpm_reports` currently has:
  - `company_id`
  - `realized_equipment_domestic`
- It does not have the `cumulative_*` columns that migration `132` tries to `ALTER ... DROP NOT NULL`.

Root-cause hypothesis:

Migration `132` uses `CREATE TABLE IF NOT EXISTS` with all desired columns, but on an already-existing partial table this does not add missing columns. The migration then runs `ALTER TABLE lkpm_reports ALTER COLUMN cumulative_* DROP NOT NULL`, which fails when those columns are absent.

Impact:

`apply_all_pending()` cannot complete reliably on drifted local/dev databases. This blocks using the full DB-backed suite as a stabilization gate.

### S3 - LKPM ready-pack tests fail on duplicate `clients.email`

Symptoms:

- `backend/tests/app/routers/test_compliance_lkpm_readypack.py`

Representative error:

```text
asyncpg.exceptions.UniqueViolationError:
duplicate key value violates unique constraint "clients_email_key"
DETAIL: Key (email)=(rp_router@example.com) already exists.
```

Direct DB evidence:

- `clients` contains one `rp_router@example.com` row.
- There are many leaked test rows:
  - `router_test_clients=525`
  - `partner_test_clients=267`

Root-cause hypothesis:

This is partly a fixture weakness and partly downstream of S1. The test uses the constant email `rp_router@example.com`; when cleanup fails because `DELETE FROM clients` is broken by guardian rules, reruns leave the row and future inserts violate the unique constraint.

Impact:

This cluster is noisy until S1 is fixed. After that, the fixture should still be hardened to use unique emails and deterministic cleanup.

## Stabilization Sessions

### Session A - Migration Ledger Reconciliation

Goal: make migration application state authoritative and prevent `schema_migrations` / `_schema_versions` split-brain.

Owned surfaces:

- `backend/db/migration_manager.py`
- `backend/db/migration_base.py`
- migration bookkeeping tests

Exit criteria:

- `apply_all_pending()` cannot skip physical SQL solely because `schema_migrations` has a row while `_schema_versions` does not.
- A regression test reproduces the current `140 recorded-but-rules-present` state.
- Dry-run output clearly reports drift instead of silently skipping.

### Session B - Migration 132 Idempotence

Goal: make `132_legacy_lkpm_reports.sql` safe for fresh, prod-shaped, and partial `lkpm_reports` schemas.

Owned surfaces:

- `backend/db/migrations_v2/132_legacy_lkpm_reports.sql`
- migration roundtrip tests

Exit criteria:

- Missing `cumulative_*` columns are added with `ADD COLUMN IF NOT EXISTS` before any `DROP NOT NULL`.
- The migration passes against a partial table containing only realized columns plus `company_id`.
- `test_apply_all_pending_creates_compliance_chain` no longer fails on migration `132`.

### Session C - Guardian Rule Physical State

Goal: ensure migration `140` physically removes the two PostgreSQL rules and that deleting a test client works.

Owned surfaces:

- `backend/db/migrations_v2/140_drop_crm_guardian_events_no_update_delete_rules.sql`
- DB sanity test around `crm_guardian_events`
- local/dev remediation script or runbook, if needed

Exit criteria:

- DB check returns zero `crm_guardian_events_no_%` rules after migration application.
- `DELETE FROM clients WHERE id = <test client>` succeeds.
- `test_compliance_alerts_router.py::test_post_outcome_creates_row` passes cleanly, including teardown.

### Session D - Fixture Isolation And Test DB Hygiene

Goal: prevent one failed run from poisoning later runs.

Owned surfaces:

- `backend/tests/app/routers/test_compliance_lkpm_readypack.py`
- `backend/tests/app/routers/test_compliance_alerts_router.py`
- `backend/tests/services/crm/partners/conftest.py`

Exit criteria:

- Fixed emails like `rp_router@example.com` are replaced with unique test emails.
- Cleanup handles dependent rows explicitly where safe.
- A preflight or cleanup helper reports leaked test rows without deleting production-like data.

### Session E - Backend Stabilization Gate

Goal: define a smaller reliable gate before returning to coverage expansion.

Owned surfaces:

- pytest markers/config
- backend DB test runbook
- CI/local command documentation

Exit criteria:

- A DB-stabilization subset runs green before full backend.
- Full backend run failures are reduced to known skips or separately tracked issues.
- Coverage work resumes only after DB-backed fixture and migration state are stable.

## Recommended Order

1. Session A: ledger reconciliation.
2. Session B: migration `132` idempotence.
3. Session C: guardian rule physical-state verification/remediation.
4. Session D: fixture isolation.
5. Session E: stable gate definition.

Do not start new coverage work until Sessions A-C are green. Session D can run in parallel only after S1 client-delete behavior is fixed, otherwise fixture failures remain misleading.

## Stabilization Result - 2026-05-09

Implemented in `codex/coverage-integration-20260509020838`:

- Session A: `MigrationManager.apply_all_pending()` now reconciles both ledgers in both directions:
  - `schema_migrations` -> `_schema_versions` for canonical rows, including historical rows whose SQL files are no longer in `migrations_v2`.
  - `_schema_versions` -> `schema_migrations` for discovered legacy-only rows.
  - Known physical drift checks force idempotent SQL re-run for migrations `132` and `140` instead of trusting a ledger row.
- Session B: migration `132_legacy_lkpm_reports.sql` now converges partial `lkpm_reports` tables by adding all promoted columns with `ADD COLUMN IF NOT EXISTS` before relaxing `realized_*` / `cumulative_*` nullability.
- Session C: local DB remediation re-ran migrations `132` and `140`; `pg_rewrite` now has zero `crm_guardian_events_no_update` / `crm_guardian_events_no_delete` rules.
- Session D: LKPM ready-pack router fixture now generates unique client emails instead of reusing `rp_router@example.com`.
- Session E: stable backend gate below is the required pre-coverage gate.

Final local DB evidence:

```text
guardian_rules=[]
ledger_counts={'legacy': 87, 'canonical': 87}
canonical_only=[]
legacy_only=[]
lkpm_checked_columns=19
lkpm_realization_nullable=True
schema_audit.ok=True
```

## Backend Stabilization Gate

Run from `apps/backend-rag` with the project virtualenv active.

1. Reconcile/apply migrations:

```bash
JWT_SECRET_KEY=test_jwt_secret_key_for_testing_only_min_32_chars_long \
API_KEYS=test_api_key_1,test_api_key_2 \
DATABASE_URL=postgresql://nuzantara@localhost:5432/nuzantara_dev \
PYTHONPATH=. python -m backend.db.migrate apply-all
```

2. Audit migration state:

```bash
JWT_SECRET_KEY=test_jwt_secret_key_for_testing_only_min_32_chars_long \
API_KEYS=test_api_key_1,test_api_key_2 \
DATABASE_URL=postgresql://nuzantara@localhost:5432/nuzantara_dev \
PYTHONPATH=. python -m backend.db.schema_audit --json
```

Expected: `"ok": true`, no findings.

3. Run the stabilization subset:

```bash
PYTHONPATH=. pytest \
  backend/tests/db/test_migration_114_115_116_roundtrip.py::test_apply_all_pending_creates_compliance_chain \
  backend/tests/db/test_migration_132_lkpm_idempotence.py \
  backend/tests/db/test_migration_ledger_reconciliation.py \
  backend/tests/app/routers/test_compliance_lkpm_readypack.py::test_happy_path_admin_dry_run \
  backend/tests/app/routers/test_compliance_alerts_router.py::test_post_outcome_creates_row \
  backend/tests/services/crm/partners/test_emails.py::test_send_commission_earned_sterilizes_client_name \
  backend/tests/db/test_migration_advisory_lock.py \
  backend/tests/db/test_legacy_promotion_migrations.py \
  backend/tests/db/test_schema_audit.py
```

Current result: `34 passed` across the listed stabilization targets.

Broader DB check: `PYTHONPATH=. pytest backend/tests/db -q` currently returns
`194 passed, 9 skipped`, and a post-run `backend.db.schema_audit --json`
returns `"ok": true`.
