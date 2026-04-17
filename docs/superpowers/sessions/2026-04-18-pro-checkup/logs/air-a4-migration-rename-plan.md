# Air A4 — Migration Rename Plan
**Session:** 2026-04-18 · **Branch:** reliability/migration-drift-cleanup

## Discovery: Sistema di Loading Reale

Il loader attuale (`backend/db/migration_manager.py`) usa **`backend/db/migrations_v2/*.sql`** come fonte autoritativa.
I file in `backend/migrations/migration_*.py` sono **legacy** — non vengono scoperti automaticamente e devono essere applicati manualmente.
Il `BaseMigration` in `backend/db/migration_base.py` usa la sua `MIGRATIONS_DIR = Path(__file__).parent / "migrations_v2"`.

**Implicazione:** il rename dei `.py` in `backend/migrations/` non rompe alcun loader automatico — nessun import diretto trovato.

---

## Gruppo 021 — 2 file

| File attuale | Nuovo nome | Data commit | Motivo |
|---|---|---|---|
| `migration_021.py` | `migration_021a_baseline.py` | 2025-12-19 | Più vecchio (commit `86ee1b71c`) — refactoring base |
| `migration_021_add_bm25_sparse_vectors.py` | `migration_021b_add_bm25_sparse_vectors.py` | 2025-12-20 | Più recente (commit `911fb18e3`) — feature BM25 |

**Nota:** `021b` ha già description suffix nel nome, quindi è chiaro.

---

## Gruppo 080 — 3 file

| File attuale | Nuovo nome | Data commit | Area/tabella |
|---|---|---|---|
| `migration_080b_visa_oracle_sessions.py` | `migration_080a_visa_oracle_sessions.py` | 2026-04-04 | visa_oracle_sessions — ⚠️ già ha suffisso `b`, ma è il PIÙ VECCHIO |
| `migration_080_renewal_dedup.py` | `migration_080b_renewal_dedup.py` | 2026-04-06 | renewal dedup |
| `migration_080_hr_team_cleanup.py` | `migration_080c_hr_team_cleanup.py` | 2026-04-07 | hr team roster |

**Nota critica:** `080b_visa_oracle_sessions` esiste già con suffisso `b` ma è il file più antico.
Per coerenza cronologica: `080a` → visa_oracle (più vecchio), `080b` → renewal_dedup, `080c` → hr_team_cleanup.

---

## Gruppo 084 — 2 file

| File attuale | Nuovo nome | Data commit | Area/tabella |
|---|---|---|---|
| `migration_084_nlm_verification_log.py` | `migration_084a_nlm_verification_log.py` | 2026-04-06 11:30 | NLM verification log |
| `migration_084_client_perf_indexes.py` | `migration_084b_client_perf_indexes.py` | 2026-04-06 20:10 | Client composite indexes |

---

## Gruppo 085 — 2 file (1 untracked)

| File attuale | Nuovo nome | Data commit | Area/tabella |
|---|---|---|---|
| `migration_085_prime_proposals.py` | `migration_085a_prime_proposals.py` | 2026-04-06 13:01 | prime_proposals table |
| `migration_085_check_no_empty_strings.py` | `migration_085b_check_no_empty_strings.py` | untracked (18-apr) | CHECK constraints empty strings |

**Nota:** `migration_085_check_no_empty_strings.py` è un file **untracked** — probabilmente creato durante l'audit stamani (18 apr). Va committato insieme al rename. È un file separato con logica propria (cleaning + CHECK constraints).

---

## Gruppo 092 — 2 file (1 untracked)

| File attuale | Nuovo nome | Data commit | Area/tabella |
|---|---|---|---|
| `migration_092_attendance_late_incidents.py` | `migration_092a_attendance_late_incidents.py` | 2026-04-07 | HR attendance late incidents |
| `migration_092_coastline_distance.py` | `migration_092b_coastline_distance.py` | untracked (18-apr) | Prime Nexus coastline table |

**Nota:** `migration_092_attendance_late_incidents.py` contiene nel header: "⚠️ NOT WIRED INTO THE LOADER. Historical reference only." — da preservare questa nota nel rename.

---

## Gruppo 098 — 2 file (1 untracked)

| File attuale | Nuovo nome | Data commit | Area/tabella |
|---|---|---|---|
| `migration_098_owner_weekly_cashout.py` | `migration_098a_owner_weekly_cashout.py` | 2026-04-08 | owner_weekly_cashout_weeks |
| `migration_098_guardian_decisions.py` | `migration_098b_guardian_decisions.py` | untracked (18-apr) | guardian_decisions + guardian_risk_scores |

---

## Gruppo 100 — 3 file

| File attuale | Nuovo nome | Data commit | Area/tabella |
|---|---|---|---|
| `migration_100_lkpm_company_id.py` | `migration_100a_lkpm_company_id.py` | 2026-04-09 19:17 | lkpm company_id column |
| `migration_100_widen_gender_column.py` | `migration_100b_widen_gender_column.py` | 2026-04-09 21:34 | gender varchar(1)→varchar(20) |
| `migration_100_olympus_tables.py` | `migration_100c_olympus_tables.py` | 2026-04-10 02:59 | olympus_* tables |

---

## Riepilogo Rename

**Totale rename:** 16 file (tutti in `apps/backend-rag/backend/migrations/`)
**Import/referenze esterne da aggiornare:** 0 (nessun import diretto trovato)
**File untracked da aggiungere a git:** 3 (`085b`, `092b`, `098b`)

### Impatto su loader
- `migration_manager.py` usa `db/migrations_v2/*.sql` → **ZERO impatto**
- Nessun registry Python lista questi file per nome
- Nessun test import questi file per classname

### Convenzione finale adottata
```
migration_NNNa_descrizione.py  ← più vecchio del gruppo (by git commit date)
migration_NNNb_descrizione.py  ← secondo
migration_NNNc_descrizione.py  ← terzo (solo per 080 e 100)
```

---

## File .sql legacy non conformi (MED-7)

| File | Problema | Azione |
|---|---|---|
| `032_messaging_users.sql` | Manca prefisso `migration_` | Renaming non urgente — loader non la carica |
| `037_add_practice_required_docs.sql` | Manca prefisso `migration_` | Idem |
| `add_performance_indexes.sql` | Nessun numero progressivo | Idem |
| `migration_054_practice_required_documents.sql` | Conforme | OK |
| `migration_061_documents_ocr_status.sql` | Conforme | OK |
| `migration_062_client_drive_subfolders.sql` | Conforme | OK |

**File `apply_migration_*.py`** (16): legacy runner scripts. Non rinominati — la convenzione futura usa BaseMigration. Documentare in MIGRATIONS.md come "legacy runners, non aggiungerne di nuovi".

---

## Prossimi passi

1. ✅ **Subtask 1 completato** — questo documento
2. → **Subtask 2**: `git mv` per i 16 rename + `git add` per i 3 untracked
3. → **Subtask 3**: rollback enforcement in `migration_base.py` (ABC + `MigrationIrreversibleError`)
4. → **Subtask 4**: aggiornamento `MIGRATIONS.md` con convenzione
