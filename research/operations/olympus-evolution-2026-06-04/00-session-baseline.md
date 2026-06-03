---
date: 2026-06-04
domain: operations
client_case: none (internal infra)
component: Olympus DB Guardian
sources:
  - apps/backend-rag/backend/services/olympus/*.py (source read in-session)
  - apps/backend-rag/backend/migrations/migration_100c_olympus_tables.py
  - apps/backend-rag/backend/migrations/migration_104_olympus_v3_columns.py
  - apps/backend-rag/backend/tests/services/olympus/*.py (49 tests run)
  - live production query nuzantara-rag Fly Postgres (2026-06-04, via fly ssh + asyncpg)
  - real e2e test against throwaway PG18 on Pro
author: Claude Opus 4.8 (M5 session)
status: STEP 0 of 5 — baseline established
---

# 00 — Olympus Baseline: studio + test reali (sessione 2026-06-04)

> Primo dei 5 report della pipeline "olympus-evolution".
> Pipeline: **00 baseline** → 01 deep-research → 02 gap-analysis → 03 panel-4LLM → 04 spec.
> Scopo: congelare TUTTO ciò che è stato osservato empiricamente in questa sessione, così
> i passi successivi (e sessioni future) non ri-derivano da zero né allucinano numeri.
> Ogni numero qui è stato letto da un tool in-session, non ricordato.

---

## 1. Cos'è Olympus (architettura osservata)

Self-monitoring DB guardian per il Postgres di produzione (Fly app `nuzantara-rag`).
Vive in `apps/backend-rag/backend/services/olympus/`. Modellato come "organismo" con due
ritmi (heartbeat veloce + pulse lento), regole evolvibili, raccolta insight.

### 1.1 Moduli (LOC reali)

| File                     | LOC | Ruolo                                                                                        |
| ------------------------ | --- | -------------------------------------------------------------------------------------------- |
| `guardian.py`            | 210 | Orchestratore. Wires heartbeat+pulse+rules+alerts+insights. Feedback loop. Loop asyncio.     |
| `heartbeat.py`           | 230 | Raccolta metriche (5min), check_alerts, persist snapshot, compute health_score               |
| `pulse.py`               | 493 | Manutenzione (6h): vacuum/cleanup/seq-repair/reindex/MV-refresh/partition/autovacuum-advisor |
| `rules_engine.py`        | 95  | Load rules da DB, get_threshold, record_applied (++), lower_confidence (-0.1)                |
| `insights.py`            | 240 | Query intelligence (pg_stat_statements) + bloat intelligence (unused/missing index)          |
| `models.py`              | 131 | Pydantic: HeartbeatSnapshot (+compute_health_score), PulseAction, OlympusRule, InsightRecord |
| `alerts.py`              | 41  | OlympusAlerts — Telegram via AlertService, nullable-safe (None su API machine)               |
| `app/routers/olympus.py` | 35  | `/internal/olympus/pulse` (POST trigger), `/internal/olympus/rules` (GET)                    |

Totale ~1476 LOC.

### 1.2 Schema DB (migrations)

`migration_100c_olympus_tables.py` — 5 tabelle:

- `olympus_heartbeats` — **partizionata RANGE(recorded_at)**, partizioni mensili
  (2026_04/05/06 + default), indice BRIN, PK composta (id, recorded_at).
- `olympus_actions` — audit trail. CHECK rhythm IN (heartbeat,pulse,metacognition,council),
  CHECK outcome IN (success,failure,skipped,proposed).
- `olympus_rules` — regole evolvibili. UNIQUE rule_name, CHECK category IN
  (threshold,schedule,policy,skill), confidence NUMERIC(3,2) default 1.00, superseded_by self-FK.
- `olympus_insights` — wisdom. CHECK insight_type IN (pattern,correlation,anomaly,
  recommendation,skill), evidence JSONB, applicable_to TEXT[] GIN, superseded_by self-FK.
- `olympus_skills` — **Voyager-pattern, MAI usato** (sql_template, preconditions). Scaffold v4.
- Seed 10 regole iniziali.

`migration_104_olympus_v3_columns.py` — ALTER heartbeats ADD cache_hit_ratio,
top_tables_by_size, idx_scan_ratio, health_score. Seed 2 regole v3.

### 1.3 health_score (models.py:42-77)

Composito 0-100: cache_hit 25pt(>=95%) · pool_util 20pt(<=50%) · dead_tuple 20pt(<2%) ·
idx_scan 15pt(>80%) · long_queries 10pt(-2/q) · lock_waits 10pt(-5/lock). None→assume healthy.
**Verificato a mano**: snapshot degradato → calcolo manuale 41 = codice 41. Match esatto.

### 1.4 Wiring produzione (service_initializer.py)

- 2 path init: full (~1422, con alert_service) e light (~1617, alert_service=None).
- **Kill-switch** `DISABLE_BACKGROUND_WORKERS=1` → skip. Motivo (incident 2026-04-12):
  loop corrompono pool asyncpg su errori PG transitori → ConnectionDoesNotExistError storm.
- register critical=False. Router manifest:251 group \_API tag admin.
- `_heartbeat_loop` usa `get_bg_pool_semaphore()` (cicatrix god-test S12/FIX-1 2026-05-24).
  `_pulse_loop` parte dopo 60s poi ogni N ore.

### 1.5 Safety: \_SAFE_VACUUM_TABLES (pulse.py:25-50)

Allowlist **24 tabelle** hard-coded. VACUUM solo su queste; altre bloated → `skipped`
"Not in safe-list". Le 24: api_audit_trail, auth_audit_log, kg_edges, kg_nodes,
company_documents, memory_facts, team_timesheet, whatsapp_message_context, cell_pulse_log,
user_stats, clients, ab_test_metrics, whatsapp_contacts, documents, query_analytics,
activity_log, workflow_analytics, cell_episodes, conversations, episodic_memories,
olympus_heartbeats, olympus_actions, news_items, conversation_messages.

Altre azioni NON allowlist ma intrinsecamente safe: cleanup_audit_trail (solo api_audit_trail),
cleanup_expired_sessions (solo persistent_sessions >30gg), repair_sequences (setval su desync),
rebuild_invalid_indexes (REINDEX solo NOT indisvalid), refresh_materialized_views (CONCURRENTLY

- fallback), ensure_next_partition (CREATE mese+1), autovacuum_advisor (solo proposed).

---

## 2. Test eseguiti in-session (3 livelli)

### 2.1 Unit suite (mock pools)

`PYTHONPATH=. .venv/bin/python -m pytest backend/tests/services/olympus/ -q` → **49 passed in 0.11s**.
LIMITE: mock pool → NON valida che la SQL sia eseguibile su PG reale.

### 2.2 Logica pura (verifica indipendente)

health_score (100/41/100/0.0), OlympusRule JSON parse, PulseAction defaults — tutto coerente.

### 2.3 End-to-end su Postgres 18 reale (Pro, DB usa-e-getta `olympus_test`)

- migrazioni → 12 regole, 16 colonne ✓
- heartbeat persistito, health=100, db_size 9.0MB ✓
- **repair_sequence**: clients_id_seq → 99999 ✓ (side-effect reale)
- **cleanup_expired_sessions**: 40gg purgata ✓; **cleanup_audit_trail**: 200gg purgata ✓
- actions persistite=4, applied_count audit_retention_days→1 (feedback) ✓
- **vacuum gating** (test dedicato): clients/api_audit_trail in lista → success;
  persistent_sessions fuori → **skipped "Not in safe-list"** ✓
- **confidence loop**: pool_alert_pct 1.0→0.9→0.8 (mem+DB coerenti) ✓
  DB droppato a fine test. Nessun residuo.

---

## 3. STATO PRODUZIONE REALE (Fly nuzantara-rag, 2026-06-04 via fly ssh + asyncpg)

> Query dentro container Fly con `os.environ["DATABASE_URL"]`. Script via fly ssh sftp, poi rimosso.

### 3.1 Heartbeat

- **hb_total = 17.715** · window 2026-04-09 → 2026-06-03 = **~55 giorni** · ~322/g ≈ ogni 4.5 min
- last hb: health **98**, pool 1/1, active 2/300, cache 99.27%, idx_scan 79.43%, long 1, lock 0

### 3.2 Azioni (act_total = 20.504)

| action_type              | outcome     | count     |
| ------------------------ | ----------- | --------- |
| vacuum                   | skipped     | **7.782** |
| unused_index             | proposed    | 6.970     |
| refresh_matview          | success     | 2.257     |
| missing_index            | proposed    | 1.272     |
| query_intelligence       | **skipped** | 704       |
| cleanup_audit_trail      | success     | 704       |
| cleanup_expired_sessions | success     | 704       |
| refresh_matview          | **failure** | 68        |
| vacuum                   | success     | 42        |
| ensure_partition         | success     | 1         |

### 3.3 Insights & Rules

- **insights_total = 8.242** (accumulati, mai consumati)
- applied_count>0: audit_retention_days=704, vacuum_dead_pct_threshold=36. Altre=0. **Tutte confidence=1.0**.
- Regole extra non nelle migration lette: v4_insights_threshold, growth_anomaly_pct,
  partition_suggest_threshold, mv_refresh_interval_seconds → seeded altrove (verificare in 02).

### 3.4 Coverage

- **total_public_tables = 265** · allowlist VACUUM 24 → **9.1%**

---

## 4. Semi di gap (da approfondire in 02)

1. **pg_stat_statements ASSENTE in prod** → query_intelligence sempre skipped (704×). Ramo
   "regressione query +30%" dormiente. Confermato da test e2e (warning) + 704 skipped prod.
2. **8.242 insights mai consumati**. Nessun consumer legge olympus_insights. `_check_v4_readiness`
   logga solo se >=500 (superato 16×) ma non attiva nulla. olympus_skills resta scaffold vuoto.
3. **6.970 unused_index + 1.272 missing_index proposed** — mai attuati né sorvegliati. Rumore o valore?
4. **refresh_matview 68 failure** su 2.325 (~2.9%). Quali MV? perché fallisce anche non-concurrent?
5. **vacuum skipped 7.782 vs success 42** — allowlist 9%. Le 241 tabelle fuori potrebbero avere bloat reale.
6. **health 98 stabile** ma output quasi tutto in `proposed` non azionato → Olympus oggi più
   **osservatore** che **attuatore autonomo**.
7. **Kill-switch storia**: pool corruption su errori PG transitori (2026-04-12). Robustezza loop = tema.
8. **W38 cicatrix**: backend_rag_v2 ha rolsuper=t. Olympus gira come quel ruolo. Demotion NOSUPERUSER
   pianificata ma non eseguita — impatta capacità future (CREATE EXTENSION pg_stat_statements).

---

## 5. Metodo & ambiente (riproducibilità)

- Sessione su **Air-M5** (`balizero@Air-M5`), thin-client: no PG/Docker locale.
- Venv reale: `~/Desktop/nuzantara/apps/backend-rag/.venv` (268 pkg). SessionStart hook
  "Backend venv MISSING" = **falso negativo** (path sbagliato `~/apps/...`).
- PG reale e2e: via `ssh pro` (PG18 Homebrew :5432).
- PG prod: via `fly` (funzione shell M5 → proxy Pro) → `fly ssh console -a nuzantara-rag`.
  psql assente nel container → Python+asyncpg con DATABASE_URL.
- Keychain readonly NON leggibile via SSH headless (login keychain locked) → usato path interno.
- **Worktree isolation**: report scritti in `.worktrees/docs-olympus-evo-2026-06-04`
  (branch `agent/air-m5/docs/olympus-evo-2026-06-04`) per cicatrix sibling-race.

---

## 6. Next steps

- [ ] 01 — deep research SOTA autonomous DB agents (Exa + NLM + WebSearch)
- [ ] 02 — gap analysis dettagliata (consumare semi §4)
- [ ] 03 — panel 4-LLM
- [ ] 04 — spec di piano
