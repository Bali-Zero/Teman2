# Air A4 — Checkpoint Final
**Session:** 2026-04-18 · **Branch:** `reliability/migration-drift-cleanup`

## Stop criteria — verifica

| Criterio | Status |
|---|---|
| `air-a4-migration-rename-plan.md` completo in docs/ | ✅ |
| Git diff mostra ~16 rename + 3 untracked aggiunti | ✅ 16R + 3A |
| `pytest test_migration_base_rollback.py test_migration_contract.py -v` verde | ✅ 13 passed, 1 skipped |
| `MIGRATIONS.md` aggiornato con convenzione | ✅ |
| Import chain (`from backend.db.migration_base import ...`) non regressiona | ✅ |
| Nessun tocco a `alembic/env.py`, `fly.toml`, `.env*`, `zantara_core.py` | ✅ |

## Subtask completati

### Subtask 1 — Audit e mapping duplicati ✅
- Discovery: loader usa `db/migrations_v2/*.sql`, i `migrations/*.py` sono legacy/manual
- 7 gruppi duplicati identificati: 021×2, 080×3, 084×2, 085×2, 092×2, 098×2, 100×3
- 3 file untracked trovati (085b, 092b, 098b — creati il 18-apr, probabilmente durante audit)
- Piano rename scritto con ordine cronologico git-verified
- **File**: `docs/superpowers/sessions/2026-04-18-pro-checkup/logs/air-a4-migration-rename-plan.md`

### Subtask 2 — Rename + untracked ✅
- 16 `git mv` eseguiti (tutti staged come R)
- 3 file untracked aggiunti con `git add`
- 0 import/referenze esterne da aggiornare (nessun import diretto trovato)
- Loader V2 non impattato (usa `migrations_v2/*.sql`)

### Subtask 3 — Rollback enforcement ✅
- **`MigrationIrreversibleError`**: nuova eccezione che estende `MigrationError`
- **`LEGACY_NO_ROLLBACK_WHITELIST`**: frozenset di 104 stems pre-cutoff
- **`BaseMigration.__init__`**: raise `ValueError` se migration > 111 senza `rollback_sql`
- **`verify_apply` / `verify_rollback`**: metodi async con default `return True`
- **`_sql_dir` param**: dependency injection per test senza filesystem prod
- **Test TDD verde**: `test_migration_base_rollback.py` (9 test), `test_migration_contract.py` (5 test)

### Subtask 4 — MIGRATIONS.md aggiornato ✅
- Two-tier system documentato (V2 loader vs legacy manual)
- Naming convention con letter suffix ordinato per data commit
- Rollback policy: pre-cutoff grandfathered, post-cutoff obbligatorio
- Template nuovo con rollback_sql + verify_apply/verify_rollback
- Legacy file types documentati come "non aggiungerne di nuovi"

## File modificati / creati

```
M  apps/backend-rag/backend/db/migration_base.py          # MigrationIrreversibleError + whitelist + enforcement
A  apps/backend-rag/backend/tests/db/__init__.py
A  apps/backend-rag/backend/tests/db/test_migration_base_rollback.py
A  apps/backend-rag/backend/tests/db/test_migration_contract.py
M  apps/backend-rag/backend/migrations/MIGRATIONS.md      # Convenzione aggiornata

# 16 rename (R):
R  migration_021.py                      → migration_021a_baseline.py
R  migration_021_add_bm25_sparse_vectors → migration_021b_add_bm25_sparse_vectors.py
R  migration_080b_visa_oracle_sessions   → migration_080a_visa_oracle_sessions.py
R  migration_080_renewal_dedup           → migration_080b_renewal_dedup.py
R  migration_080_hr_team_cleanup         → migration_080c_hr_team_cleanup.py
R  migration_084_nlm_verification_log    → migration_084a_nlm_verification_log.py
R  migration_084_client_perf_indexes     → migration_084b_client_perf_indexes.py
R  migration_085_prime_proposals         → migration_085a_prime_proposals.py
R  migration_085_check_no_empty_strings  → migration_085b_check_no_empty_strings.py
R  migration_092_attendance_late_incidents → migration_092a_attendance_late_incidents.py
R  migration_092_coastline_distance      → migration_092b_coastline_distance.py
R  migration_098_owner_weekly_cashout    → migration_098a_owner_weekly_cashout.py
R  migration_098_guardian_decisions      → migration_098b_guardian_decisions.py
R  migration_100_lkpm_company_id         → migration_100a_lkpm_company_id.py
R  migration_100_widen_gender_column     → migration_100b_widen_gender_column.py
R  migration_100_olympus_tables          → migration_100c_olympus_tables.py

# 3 nuovi (A):
A  migration_085b_check_no_empty_strings.py   (era untracked)
A  migration_092b_coastline_distance.py        (era untracked)
A  migration_098b_guardian_decisions.py        (era untracked)

# Session docs:
A  docs/superpowers/sessions/2026-04-18-pro-checkup/logs/air-a4-migration-rename-plan.md
A  docs/superpowers/sessions/2026-04-18-pro-checkup/logs/air-a4-checkpoint-final.md
```

## Rischi residui per Zero

1. **`migration_080b_visa_oracle_sessions`** era già nel repo con suffisso `b` — ora rinominato in `080a`. Se qualcuno aveva salvato il vecchio nome in documentazione esterna, va aggiornato. File non usato da alcun loader automatico.
2. I 3 file untracked (085b/092b/098b) potrebbero sovrascrivere logica già in `migrations_v2/` — vanno valutati se applicare o solo tenere come reference.
3. Il test `test_post_cutoff_migration_has_rollback_sql` attualmente è SKIPPED (nessun file > 111 con BaseMigration). Quando il primo post-cutoff viene creato, sarà PARAMETRIZED e verde solo se rollback_sql è presente.

## Note per Zero (reviewer)

- PR richiede review prima di merge — nessuna migration su DB reale applicata
- Il PR non tocca `alembic/env.py`, `fly.toml`, `.env*`
- Il test suite è standalone (no DB connection): `PYTHONPATH=. pytest backend/tests/db/ -v`
