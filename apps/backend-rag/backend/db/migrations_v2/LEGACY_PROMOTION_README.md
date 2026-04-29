# Legacy promotion plan — Strategy 01 Step 4

> Files: `129..130`, `132..137` (gap at `131` reserved for
> `131_unify_migration_tracking.sql` — Strategy 01 Step 3).
>
> Status: **draft / shipped behind a no-op** (this PR). The bootstrap
> step is still wired in `tests.yml` because removing it requires a
> coordinated cutover. See "Cutover" below.

## Why these files exist

Today CI bootstraps tables that prod created by hand or via the old
Python migration series (`backend/migrations/migration_NNN.py`, which
the v2 runner does not discover). The bootstrap script
[`apps/backend-rag/scripts/ci_bootstrap_schema.py`](../../scripts/ci_bootstrap_schema.py)
is the workaround. It uses `SQLModel.metadata.create_all()` on top of
raw DDL, which means the CI schema is built from a different recipe than
the prod schema — that gap is the root cause of several schema drifts
(see SCAR list in `apps/backend-rag/CLAUDE.md`).

The 8 files in this PR mirror, line-for-line, the DDL the bootstrap
script issues. They are intentionally **idempotent** (`CREATE TABLE IF
NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, `DROP NOT NULL`, `SET DEFAULT`)
so they can land in `migrations_v2/` without breaking either:

* **Prod**, where the tables and columns already exist (every statement
  becomes a no-op);
* **Bootstrap-built CI**, where the bootstrap script will create the
  same tables a few seconds before `python -m backend.db.migrate
  apply-all` runs — the migration finds them already in place and
  records itself as applied.

## Mapping bootstrap → SQL

| Bootstrap (`ci_bootstrap_schema.py`) | Migration |
|--------------------------------------|-----------|
| `CREATE TABLE IF NOT EXISTS user_profiles ...`  | `142_legacy_user_profiles.sql` (was `129_*` until P0-7 renumber on 2026-04-29) |
| `CREATE TABLE IF NOT EXISTS conversations ...`  | `143_legacy_conversations.sql` (was `130_*` until P0-7 renumber on 2026-04-29) |
| `CREATE TABLE IF NOT EXISTS lkpm_reports ...` + 18 ALTER + company_id | `132_legacy_lkpm_reports.sql` |
| `CREATE TABLE IF NOT EXISTS system_settings ...` | `133_legacy_system_settings.sql` |
| `CREATE TABLE IF NOT EXISTS notification_log ...` + index | `134_legacy_notification_log.sql` |
| `CREATE TABLE IF NOT EXISTS notification_prefs ...` | `135_legacy_notification_prefs.sql` |
| `clients` ADD COLUMN drive_* / deleted_at + timestamp defaults | `136_clients_drive_columns_and_defaults.sql` |
| `team_members` ADD COLUMN name + nullable + defaults | `137_team_members_legacy_columns_and_defaults.sql` |

The bootstrap script also imports the `class table=True` SQLModel
classes and calls `SQLModel.metadata.create_all()`; that mechanism
covers a separate set of tables (clients itself, practices,
practice_types, interactions, companies, client_company_links,
company_documents, tax_records, tax_documents, team_members,
user_sessions, user_facts, episodic_memories, collective_memory,
conversation_ratings, review_queue, openclaw_message_logs). Those tables
were created by hand in prod long ago, so a CREATE TABLE migration is
moot for them — they live as "promoted to v2" only on paper. A future
PR may add forward-only `CREATE TABLE IF NOT EXISTS` migrations for
them, but the value is small (idempotent no-op against prod) and the
risk surface is "what does the FK target look like in CI vs prod" —
which is precisely what `SCHEMA_AUDIT_REQUIRED_TABLES` is for (Step 6,
PR #253).

## Cutover (NOT in this PR)

Once these migrations are merged and applied:

1. Add `SCHEMA_AUDIT_REQUIRED_TABLES=clients,team_members,user_profiles,
   conversations,lkpm_reports,system_settings,notification_log,
   notification_prefs` to the CI env and run
   `python -m backend.db.schema_audit` after `apply-all` to verify the
   migrations actually produced the expected shape.
2. Drop the `Bootstrap SQLModel tables` step from
   `.github/workflows/tests.yml`.
3. Delete `apps/backend-rag/scripts/ci_bootstrap_schema.py` (or keep a
   stub that errors with "use migrations_v2 — see LEGACY_PROMOTION_README.md").
4. Run the schema audit on prod once to confirm there is no divergence
   in the post-cutover state.

Each of the steps above is a separate PR — that's the strangler-fig
sequencing strategy 01 Step 4 calls for.

## What these migrations do NOT do

* **No prod data migration.** Every table they touch already exists in
  prod; the migrations only record that fact. No `INSERT`, no `UPDATE`,
  no data movement.
* **No NOT NULL promotion.** Several lkpm_reports and team_members
  columns are nullable in prod by historical accident; the test suite
  (`test_legacy_promotion_migrations.py::test_alter_column_does_not_promote_to_not_null`)
  guards against re-introducing NOT NULL on columns that legitimately
  store NULL today. If we want to tighten any of these, that's a
  separate migration with a backfill.
* **No Alembic.** The backend uses the v2 SQL runner
  (`backend/db/migration_manager.py`); see `VADEMECUM.md §7`.

## Reference

- Strategy doc: `docs/reviews/2026-04-25-strategy-01-database-migrations.md` (Step 4)
- Schema audit (Step 6): PR #253
- Schema-change rules (Step 0): merged in PR #251
- Advisory lock fix (Step 1): merged in PR #250
