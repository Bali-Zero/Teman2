# Runbook — M5 local PostgreSQL

Local PostgreSQL 17 on M5 (`balizero@Air-M5`) for: (1) a test DB matching CI so the
pre-push hook runs real tests instead of burning ~2min on `Connect ::1:5432` errors,
and (2) a pull-only data snapshot from Fly prod for dev/inspection.

> Design + rationale: `research/operations/2026-06-12-m5-postgres-architecture.md`
> Spec + acceptance: `research/operations/specs/2026-06-12-M5-postgres-local-spec.md`

## What's where

- **Engine**: Homebrew `postgresql@17` (keg-only, binaries at `/opt/homebrew/opt/postgresql@17/bin`).
  PATH added to `~/.zshenv`. Service: `brew services start postgresql@17`.
- **Databases** (on `localhost:5432`):
  - `test` — conftest default (`postgresql://test:test@localhost:5432/test`), role `test`/`test`.
  - `nuzantara_test` — CI-parity manual runs (matches `.github/workflows/tests.yml`).
  - `nuzantara_dev` — restored prod snapshot (refreshed on demand, see below).
- **Snapshots**: `~/.nuzantara-db-snapshots/` (700, files 600), last 3 kept.

## Daily use

**Run the test suite the way CI does** (the pre-push hook does this automatically when PG is up):

```bash
export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"
cd apps/backend-rag && source .venv/bin/activate
export DATABASE_URL="postgresql://test:test@localhost:5432/nuzantara_test"
export TEST_DATABASE_URL="$DATABASE_URL"
export JWT_SECRET_KEY="test_jwt_secret_key_for_testing_only_min_32_chars_long"
export API_KEYS="test_api_key_1,test_api_key_2"
# one-time bootstrap (re-run after new migrations):
PYTHONPATH=.:../crm-cell python scripts/ci_bootstrap_schema.py
PYTHONPATH=.:../crm-cell python -m backend.db.migrate apply-all   # NB: drop CI's `timeout` — macOS has none
# then:
PYTHONPATH=.:../crm-cell pytest backend/tests/ -q
```

**Refresh the dev snapshot from prod** (pull-only, never writes to Fly):

```bash
bash scripts/nuz_db_refresh.sh
# → fly proxy 15432 → pg_dump (role nuzantara_readonly, Keychain) → restore into nuzantara_dev
# requires: fly auth + Keychain entry nuzantara-postgres-readonly (see Setup below)
```

## Setup (one-time, already done 2026-06-12 — re-do only on a fresh M5)

1. `M5_HEAVY_BREW_GUARD=off brew install postgresql@17` then `brew services start postgresql@17`
   (the `m5_block_heavy_brew.py` hook no longer blocks postgresql — it was removed from HEAD on 2026-06-12).
2. PATH → `~/.zshenv`: `export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"`.
3. Roles + DBs:
   ```bash
   psql -d postgres -c "CREATE ROLE test LOGIN PASSWORD 'test' CREATEDB;"
   createdb -O test test; createdb -O test nuzantara_test; createdb nuzantara_dev
   ```
4. Keychain (for `nuz_db_refresh.sh` only) — value never echoed:
   ```bash
   RO=$(ssh pro "security find-generic-password -s nuzantara-postgres-readonly -w")
   security add-generic-password -U -s nuzantara-postgres-readonly -a nuzantara_readonly -w "$RO"; unset RO
   ```

## Gotchas

- **`localhost` resolves to `::1` (IPv6) first on macOS.** The 141 historical test errors were
  `Connect call failed ('::1', 5432)`. The local engine listens on both `::1` and `127.0.0.1`,
  so tests pass — BUT for the `fly proxy` path use `-h 127.0.0.1` explicitly (the proxy binds IPv4 only).
- **`timeout` does not exist on macOS** (GNU coreutils). The CI migrate step uses `timeout 120`; drop it locally.
- **Re-run bootstrap after pulling new migrations** — `ci_bootstrap_schema.py` creates SQLModel tables
  (`clients` etc. have no migration file); `migrate apply-all` then alters them. Some SQL migrations
  INSERT into tables created by the _Python_ migration runner (`backend/migrations/*.py`) — if a future
  migration trips "relation … does not exist", make it self-contained (`CREATE TABLE IF NOT EXISTS`),
  the pattern proven on PR #1111.
- **Pull-only**: `nuz_db_refresh.sh` never writes to Fly; if the readonly role hits a permission
  error mid-dump, the script STOPS — surface to Antonello, do NOT escalate the role (W38 spirit).
- **PII**: prod dumps contain client PII (UU PDP). They stay on M5 (Law 6), dir 700 / files 600,
  never synced out. The Pro's own local PG is never touched (Law 2).

## Rollback

```bash
brew services stop postgresql@17 && brew uninstall postgresql@17   # data dir removable after
git revert <the .husky/pre-push commit>                             # restore old hook
dropdb nuzantara_dev && rm -rf ~/.nuzantara-db-snapshots            # snapshot data
# re-add postgresql tokens to HEAVY in ~/.claude/hooks/m5_block_heavy_brew.py
```

Prod is untouched at every step by design.
