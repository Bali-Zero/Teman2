---
date: 2026-06-12
domain: operations
client_case: internal-infra
status: DESIGN ONLY — approved-pending-GO, NOT implemented (Antonello: "simulala, poi fermati")
author: Claude (Fable 5 session, M5) — handoff to Opus implementation session
sources:
  - apps/backend-rag/backend/tests/conftest.py:22 (DATABASE_URL default test:test@localhost:5432/test)
  - .github/workflows/tests.yml:25-26,129 (CI = postgres:15, nuzantara_test)
  - fly image show -a nuzantara-postgres (postgres-flex 17.2, repmgr — NOT Stolon, docs drift)
  - cicatrix W67c / mata_garuda active-active / W70 fly_pg_backup 0-byte
  - session 2026-06-12: 141 test errors "Connect ::1:5432" on M5 → repeated --no-verify
---

# M5 PostgreSQL — architecture design (pre-implementation)

## Verdict on "totalmente sync"

Full sync (streaming replica / multi-master M5⟷Pro⟷Fly) REJECTED, 4 reasons:

1. **WAL-slot trap**: physical replication slot on Fly primary + laptop replica offline
   → primary retains WAL → prod disk fill → laptop can cause prod outage.
2. **Active-active scar family**: W67c, 12+1 mata_garuda — organism bitten 3× already.
   Test writes on M5 syncing back to prod CRM = phantom clients.
3. **Coupling**: streaming needs identical PG major (prod 17.2 vs CI 15 vs hook @18);
   logical replication breaks on DDL (every migration).
4. **Law 2**: Pro's local PG (wa-mirror/intel) NEVER syncs out. Pro stays island.

What IS "totally sync": **schema** (migrations in repo — same code applied by M5/CI/Fly)
+ **read-only data snapshot on demand** (pull, never push).

## Architecture

```
Fly nuzantara-postgres (postgres-flex 17.2, repmgr) = SOURCE OF TRUTH
        │ PULL one-way: fly proxy 15432 → pg_dump -Fc (role nuzantara_readonly, Keychain T3.2)
        ▼
M5 postgresql@17 (brew, NATIVE install — never copy venv/datadir cross-machine, cf. M5 path-drift scar)
  ├── nuzantara_test  — ephemeral, migrations-only, CI parity (test:test@localhost:5432)
  └── nuzantara_dev   — restored snapshot (pg_restore --clean --no-owner),
                        --exclude-table-data on churn tables (events_outbox, olympus_heartbeats*)
Pro local PG — NOT synced (Law 2). M5 dashboard dev uses synthetic fixtures.
```

## Key simulations run (design-time)

- Laptop closed 3d + streaming → WAL retention → prod risk ⇒ kills streaming. Snapshot: no-op. ✓
- Test write flowing back (multi-master) → phantom CRM rows ⇒ one-way only. ✓
- Pre-push hook on M5 with local PG → 141 ::1:5432 errors disappear → no more --no-verify. ✓
- New migration: snapshot picks up at refresh; test-DB from repo. GOTCHA (learned 2026-06-12
  on PR #1111): test-DB bootstrap MUST run BOTH runners — migrations_v2/*.sql AND
  backend/migrations/*.py (migration_100c creates olympus_* tables; the SQL runner alone
  hit "relation olympus_rules does not exist").
- PII: prod dump = client PII (UU PDP). M5 is Zero's machine (Law 6), FileVault, dumps
  chmod 600 outside repo (~/.nuzantara-db-snapshots/). Fly→M5 does not violate Law 2.
- Versions: dump/restore is major-agnostic ⇒ @17 on M5 = prod parity. CI 15 is the outlier.
- W70 synergy: fly_pg_backup produces 0-byte dumps (open scar). A working M5 refresh =
  verified extra backup layer (successful restore proves dump integrity).

## Implementation plan (NOT executed)

1. **Phase 1 — test DB** (fixes today's pain, standalone value):
   `brew install postgresql@17` + `brew services start`; create role test/test;
   bootstrap script creates nuzantara_test + runs BOTH migration runners.
2. **Phase 2 — dev snapshot**: `scripts/nuz_db_refresh.sh` — fly proxy → pg_dump -Fc
   (nuzantara_readonly from Keychain `nuzantara-postgres-readonly`) → pg_restore into
   nuzantara_dev. Idempotent, pull-only, no replication slots.
3. **Phase 3 — pre-push hook**: PG present → run DB tests; absent → declared SKIP
   (not silent failure). Ends the --no-verify era on M5.
4. **Phase 4 (opt) — LaunchAgent** daily refresh, AC+network gated, NO KeepAlive
   (it's a cron — 2026-04-29 daemon-vs-cron scar).

## Open decisions for Antonello

- (a) Phase 1 only first, or 1+2 together?
- (b) SessionStart hook checks postgresql@18 — update hook to @17 (prod parity) or install 18?
- (c) Bump CI postgres:15 → 17 to match prod?

## Doc drift found (incidental)

CLAUDE.md §11 says "nuzantara-postgres (Stolon HA)" — live image is **postgres-flex 17.2
with repmgr** (`fly.pg-manager=repmgr`). Update docs when convenient.
