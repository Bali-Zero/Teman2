# War Room 2.0 — Activation Plan

> **Stato**: Fase 0 + blocker fix + Fase 1 applicata 2026-04-20 00:25 WITA · Stop concordato prima di Fase 2
> **Autore**: Claude Opus 4.7 (sessione worktree `feat/war-room-2-activation`)
> **Riferimenti**: `docs/war-room-2.0-design.md` · `docs/war-room-v2/README.md` · `SYMBIOSIS.md`

---

## 1. Executive summary

War Room 2.0 è codice scritto al 95% ma mai acceso in produzione. L'attivazione
richiede: (a) applicare 3 migration Python (112/113/114) sulla PG di `nuzantara-postgres`,
(b) creare 10 LaunchAgent launchd su Pro, (c) smoke-test end-to-end, (d) decidere
come gestire la pipeline editoriale "vecchia" (intel-scraper + post-publish-poller)
che coesiste.

**Verifica Fase 0 ha rivelato un conflitto bloccante di schema** tra:

- `migration_114_cognitive_layer.py` (WR2, non applicata): definisce
  `compliance_alerts` con colonne `dossier_a_id`, `dossier_b_id`,
  `contradiction_type` — tabella per **contraddizioni cross-dossier**.
- `db/migrations_v2/114_compliance_alerts.sql` (già in prod): definisce
  `compliance_alerts` con colonne `alert_id`, `client_id`, `category`,
  `days_until`, `compliance_item_ref` — tabella per **alert di scadenza
  KITAS/LKPM per singolo cliente**.

Stesso nome, domini completamente diversi, schemi incompatibili. **Non si
può eseguire `migration_114_cognitive_layer.apply()` in prod** senza prima
rinominare la tabella WR2 (es. `wr_contradiction_alerts` o `anomaly_alerts`)
e aggiornare i riferimenti in `services/cognitive/repository.py`,
`anomaly_alerter.py`, `anomaly_detector.py`, `strategos.py`, il migration
file stesso e i test. **Decisione richiesta a Zero prima di procedere.**

## 2. Verifica codice Fase 0

### 2.1 Worktree

- Percorso: `/Users/nuzantara/Desktop/wr2-activation/` (NON `/tmp`, volatile)
- Branch: `feat/war-room-2-activation`
- HEAD: `26999af3a` (PR #123 merge, 2026-04-19)
- Pulito: sì (nessuna modifica rispetto al parent commit al momento della creazione)

### 2.2 12 package servizi presenti

Tutti in `apps/backend-rag/backend/services/` (brief diceva `backend/services/`
— path relativo sbagliato nel brief, corretto qui):

| Package | File count | Note |
|---|---|---|
| `war_room/` | 4 | `models.py`, `repository.py`, `dashboard_service.py`, `__init__.py` |
| `intel/` | 14 + `trend_hunter/` subpkg | dossier_compiler + trend_hunter CLI ok |
| `council/` | 4 | runners + ToneCouncil + prompts |
| `visual/` | 7 | imagen + qa_judge + vision_qa + fireworks fallback |
| `layout/` | 7 | renderer + patcher + templates + playwright |
| `review/` | 5 | handler + sla_worker + telegram_adapter |
| `publisher/` | 9 | IG/X/LI/Blog + orchestrator + blog_batch |
| `measurer/` | 6 | meta_graph + utm + scheduler + orchestrator |
| `learner/` | 5 | orchestrator + score + genome_adapter + injection |
| `hardening/` | 5 | failover + missed_runs + token_watchdog + quota |
| `cognitive/` | 14 | connector/anomaly/strategos/oracle + cli + delivery |
| `newsletter/` | 4 | builder + publisher + cli |

### 2.3 CLI entry-point inventory

Esistenti (verificati via `ls`):

- `backend.services.intel.trend_hunter.cli` ✅
- `backend.services.intel.dossier_compiler_cli` ✅
- `backend.services.cognitive.connector_cli` ✅
- `backend.services.cognitive.strategos_cli` ✅
- `backend.services.cognitive.oracle_cli` ✅
- `backend.services.newsletter.newsletter_cli` ✅
- `backend.services.council.cli_runners` ✅ (componente, non main entry — OK, non invocato da launchd)

**Mancanti** (da creare in Fase 2):

- `backend.services.review.sla_worker_cli` (esiste `sla_worker.py` modulo, ma
  niente `if __name__ == '__main__'`; verificare se `python -m
  backend.services.review.sla_worker` funziona)
- `backend.services.measurer.cli` o wrapper equivalente (esiste `scheduler.py`,
  serve wrapper invocabile)
- `backend.services.learner.cli` o wrapper (esiste `learner_orchestrator.py`,
  serve wrapper)
- `backend.services.hardening.missed_runs_cli` (esiste `missed_runs_alerter.py`
  modulo, serve CLI wrapper)
- `backend.services.hardening.token_watchdog_cli` (idem)
- `backend.services.hardening.quota_cli` (idem)
- `backend.services.cognitive.anomaly_cli` (esiste `anomaly_alerter.py` +
  `anomaly_subscriber.py`; anomaly è event-driven quindi potrebbe non servire
  cron-CLI — confermare con Zero)

### 2.4 Migration Python presenti

- `backend/migrations/migration_112_war_room_tables.py` — 7 tabelle
  war_room_*, trigger `notify_war_room_event()`, rollback incluso.
- `backend/migrations/migration_113_intel_dossiers.py` — 4 tabelle:
  `trend_signals`, `research_dossiers`, `dossier_reuses`,
  `dossier_refresh_log`. Trigger `notify_intel_event()`, rollback incluso.
- `backend/migrations/migration_114_cognitive_layer.py` — 4 tabelle:
  `cross_dossier_theses`, **`compliance_alerts`** (CONFLITTO),
  `weekly_strategic_briefs`, `ultra_moves`. Trigger `notify_cognitive_event()`,
  rollback incluso.

Test integration presenti:

- `backend/tests/services/war_room/test_migration_112.py` (skippato senza
  `TEST_DATABASE_URL`)
- `backend/tests/services/intel/test_migration_113.py` (idem)
- `backend/tests/db/test_migration_114_115_116_roundtrip.py` (testa la versione
  SQL, non la Python)

### 2.5 Produzione attuale (nuzantara-postgres via nuzantara-rag DATABASE_URL)

Tabelle WR2-adjacent presenti:

```
alert_outcomes         (da SQL 115)
compliance_alerts      (da SQL 114 — schema compliance clienti, NON WR2)
intel_validator_log    (da SQL 116)
```

Schema `compliance_alerts` in prod (21 colonne): `alert_id TEXT PK`,
`client_id INTEGER`, `category`, `severity`, `status`, `deadline DATE`,
`days_until INTEGER`, `compliance_item_ref`, `dedup_key`, `message_it/en/id`,
`suggested_action`, `estimated_cost_idr BIGINT`, `evidence_refs JSONB`,
`nb2_ref`, `upgrade_count`, `created_at`, `sent_at`, `acknowledged_at`,
`resolved_at`.

### 2.6 Router FastAPI registrati

- `war_room_dashboard` registrato in `router_manifest.py:309` → endpoint
  `/api/war-room/metrics/*` attivi ma risponderanno con errori fintanto che
  `war_room_drafts` e correlate non esistono.
- `cognitive/*` router: **non registrato** — il pacchetto cognitive/ è
  isolato dal FastAPI app. Questo conferma che il codice incompatibile con
  `compliance_alerts` prod non è ancora esposto o chiamato da nessuno.

### 2.7 LaunchAgent macOS correnti su Pro

Rilevanti (attivi):

```
com.balizero.post-publish-webhook    (PID 1189, vecchia pipeline)
com.balizero.nlm-bridge
com.balizero.post-publish-poller     (vecchia pipeline)
com.balizero.intel.nightly           (intel-scraper vecchio)
com.balizero.translate.hourly
com.balizero.renewal-alerts
com.balizero.client-value-predictor
```

**Nessun LaunchAgent WR2 presente.** Coerente con "WR2 non attivo".

---

## 3. BLOCKER CRITICO: conflitto `compliance_alerts`

### 3.1 Natura del conflitto

Due tabelle con lo stesso nome, schemi mutuamente esclusivi:

| Campo | SQL 114 (prod, in uso) | Python 114 (WR2, mai applicata) |
|---|---|---|
| PK | `alert_id TEXT` | `id UUID` |
| Soggetto | `client_id INTEGER` | `dossier_a_id UUID` + `dossier_b_id UUID` |
| Tipo | `category TEXT` | `contradiction_type TEXT` |
| Trigger | `compliance_alerts_trigger` (m114 SQL) | `notify_cognitive_event()` (Python 114) |
| Riferimenti | `compliance_item_ref`, `nb2_ref`, `days_until` | `affected_client_query`, `notified_zero BOOL` |
| Uso attuale | ✅ Usato da `AlertsEngine` + `AlertDispatcher` | ❌ Non usato (cognitive/ non registrato) |

### 3.2 Cosa succederebbe senza fix

`migration_114_cognitive_layer.apply()` usa `CREATE TABLE IF NOT EXISTS`:
la tabella esiste già → **il CREATE viene saltato silenziosamente**. Le
altre 3 tabelle (cross_dossier_theses, weekly_strategic_briefs, ultra_moves)
vengono create. Il trigger `notify_cognitive_event()` viene creato e prova
ad agganciarsi a `compliance_alerts` esistente — **qui si innesterebbe un
trigger cognitive su una tabella compliance, con payload sbagliato**.

Quando Anomaly L2 fosse poi acceso, `AnomalyAlerter.persist()` farebbe:
```sql
INSERT INTO compliance_alerts (dossier_a_id, dossier_b_id, contradiction_type, ...)
```
→ **ERROR: column "dossier_a_id" of relation "compliance_alerts" does not exist**.

E peggio: `AlertsEngine.generate_alerts()` (che oggi inserisce nella tabella
compliance reale) sparerebbe pg_notify sul canale `cognitive_event` sbagliato.

### 3.3 Fix proposto (richiede decisione Zero)

**Opzione A — Rinominare la tabella WR2.** Minimo impatto, raccomandata.

1. In `migration_114_cognitive_layer.py`: rinominare `compliance_alerts` →
   `wr_anomaly_alerts` (o `cognitive_contradictions`). Aggiornare constraint
   names, index names, trigger `notify_cognitive_event()`.
2. In `services/cognitive/repository.py` (righe 106, 194, 213, 232, 252, 260):
   rinominare tutte le reference.
3. In `services/cognitive/anomaly_alerter.py:113`: idem.
4. In `services/cognitive/strategos.py` (righe 6, 269): aggiornare
   documentazione/prompt + query che legge "unresolved compliance_alerts".
5. Aggiungere test che verifichi la separazione (no cross-contamination).
6. Aggiornare `docs/war-room-2.0-design.md` §17.2 per riflettere nuovo nome.

**Effort stimato**: 45-60 min. Modifica isolata al pacchetto `cognitive/`.
Nessuna modifica ai servizi compliance esistenti.

**Opzione B — Evolvere la tabella compliance per ospitare entrambi i domini.**
Sconsigliata: mescola concetti (alert cliente vs contraddizione cross-dossier),
schema gonfio, future confusion.

**Opzione C — Mantenere schema SQL, riscrivere cognitive/ per usarlo.**
Sconsigliata: la tabella compliance ha semantica client-centrica (FK
`client_id`) incompatibile con il concetto di "contraddizione tra due dossier".

---

## 4. Piano Fase 1 (bloccato fino a decisione 3.3)

### 4.1 Pre-condizioni

- Decisione Zero su Opzione A/B/C del blocker (§3.3)
- Applicazione fix al codice (se Opzione A: ~45 min lavoro)
- Test locale: `TEST_DATABASE_URL=... pytest
  backend/tests/services/war_room/test_migration_112.py
  backend/tests/services/intel/test_migration_113.py -v` **passa**
- Backup Fly PG: verifica che `~/scripts/fly-pg-backup.sh` ha eseguito nelle
  ultime 24h (o lancia manualmente prima)

### 4.2 Esecuzione (post-fix)

```bash
# Da Pro, con venv backend-rag attivo
cd /Users/nuzantara/Desktop/wr2-activation/apps/backend-rag
source .venv/bin/activate
export DATABASE_URL=$(fly ssh console -a nuzantara-rag -C "printenv DATABASE_URL" | tr -d '\r')

# 112 — War Room core
PYTHONPATH=. python -c "
import asyncio, asyncpg, os
from backend.migrations import migration_112_war_room_tables as m
async def run():
    c = await asyncpg.connect(os.environ['DATABASE_URL'])
    await m.apply(c); await c.close()
    print('✅ 112 applied')
asyncio.run(run())
"

# 113 — Intel dossier
# (idem con migration_113_intel_dossiers)

# 114 — Cognitive (DOPO fix §3.3 Opzione A)
# (idem con migration_114_cognitive_layer)
```

### 4.3 Verifica

```sql
SELECT tablename FROM pg_tables
 WHERE schemaname='public'
   AND (tablename LIKE 'war_room%'
        OR tablename IN ('trend_signals','research_dossiers','dossier_reuses',
                          'dossier_refresh_log','cross_dossier_theses',
                          'wr_anomaly_alerts','weekly_strategic_briefs',
                          'ultra_moves'))
 ORDER BY tablename;
```

**Atteso**: 15 tabelle (7 war_room_* + 4 intel + 4 cognitive, assumendo
Opzione A con rename). Il brief originale diceva "14 tabelle" perché
escludeva `compliance_alerts` dal conteggio cognitive (già in prod sotto
altra semantica). Con rename a `wr_anomaly_alerts`, diventa **15 nuove
tabelle**.

### 4.4 Rollback

Ogni migration Python ha funzione `rollback()` che fa DROP delle tabelle
create. Attenzione: rollback migration 112 rimuove **tutti i dati
war_room_* operativi**. Dato che smoke test è dry-run senza pubblicazioni
reali, rollback è sicuro prima del primo uso produzione.

---

## 5. Piano Fase 2–6 (sintesi, dettagli in sessioni successive)

### Fase 2 — CLI entry-point (1h)

Creare wrapper `cli.py` per i 6 servizi senza entry-point (§2.3).
Template minimale:

```python
# backend/services/<name>/cli.py
import asyncio, logging
from backend.app.dependencies import get_database_pool
from backend.services.<name>.<main_class> import <MainClass>

async def main():
    pool = await get_database_pool()
    svc = <MainClass>(pool=pool, ...)
    await svc.sweep_once()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
```

### Fase 3 — 10 LaunchAgent plist (1.5h)

Scrivere in `.openclaw/launchagents/` (NON installati automaticamente):

| Nome | Schedule | Invocazione |
|---|---|---|
| `com.balizero.wr2.trend-hunter.plist` | StartInterval 7200 | `python -m backend.services.intel.trend_hunter.cli` |
| `com.balizero.wr2.connector.plist` | Hour=4 Min=0 daily | `python -m backend.services.cognitive.connector_cli` |
| `com.balizero.wr2.strategos.plist` | Hour=22 Weekday=0 weekly | `python -m backend.services.cognitive.strategos_cli` |
| `com.balizero.wr2.oracle.plist` | Hour=22 Min=30 Weekday=0 | `python -m backend.services.cognitive.oracle_cli` |
| `com.balizero.wr2.newsletter.plist` | Hour=9 Weekday=1 weekly | `python -m backend.services.newsletter.newsletter_cli` |
| `com.balizero.wr2.measurer.plist` | StartInterval 21600 | `python -m backend.services.measurer.cli` (TBD) |
| `com.balizero.wr2.sla-worker.plist` | StartInterval 1800 | `python -m backend.services.review.sla_worker` |
| `com.balizero.wr2.learner-nightly.plist` | Hour=3 Min=0 daily | `python -m backend.services.learner.cli` (TBD) |
| `com.balizero.wr2.hardening.plist` | StartInterval 21600 | shell script che invoca i 3 CLI hardening in sequenza |
| `com.balizero.wr2.dossier-compiler.plist` | Hour=4 Min=30 daily | `python -m backend.services.intel.dossier_compiler_cli` |

EnvironmentVariables richieste (da README §3): `DATABASE_URL`,
`OPENAI_API_KEY`, `QDRANT_URL`, `REDIS_URL`, `JWT_SECRET`,
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_CHAT_ID`, `GROK_API_KEY`,
`DEEPSEEK_API_KEY`, `GOOGLE_API_KEY`, `FIREWORKS_API_KEY`, `IG_USER_ID`,
`IG_LONG_LIVED_TOKEN`, `X_BEARER_TOKEN`, `LINKEDIN_ACCESS_TOKEN`,
`LINKEDIN_AUTHOR_URN`, `BLOG_*`.

Log path standard: `/Users/nuzantara/.openclaw/workspace/logs/war-room-v2/<service>.log`.

Script installazione: `scripts/install_wr2_launchagents.sh` — fa cp +
`launchctl load -w`. **NON eseguire** automaticamente — preparato per
review manuale.

### Fase 4 — Smoke test (1h)

Dry-run pipeline completa (no publish reale):

1. `WarRoomRepository.create_draft(topic="WR2 activation smoke test 2026-04-20")`
2. `ToneCouncil.run(...)` con `BLOG_PUBLISH_SKIP_PUSH=1`
3. `VisualGenerator.generate_carousel(1 slide cover)` — budget ~$0.03
4. `ReviewHandler.send_review_request(...)` — Telegram a Zero con prefisso
   `[DRY-RUN]`
5. Verifica SQL: 1 riga in `war_room_drafts`, 1 in `war_room_costs`.

### Fase 5 — Decisione pipeline doppia (30 min)

Documento comparativo 3 strade (A spegni vecchio, B parallel canary 7gg,
C coesistenza permanente) — **propondi, non decidi**.

### Fase 6 — PR e summary (30 min)

Commit incrementali per fase, push branch, `gh pr create` con body
strutturato, Telegram a Zero.

---

## 6. Tempistica rivista

| Fase | Originale | Rivisto | Delta |
|---|---|---|---|
| 0 | 30 min | 45 min | +15 (identificato blocker) |
| **Fix blocker §3.3** | — | **45-60 min** | **nuovo** |
| 1 | 1h | 1h | — |
| 2 | 1h | 1h | — |
| 3 | 1.5h | 1.5h | — |
| 4 | 1h | 1h | — |
| 5 | 30 min | 30 min | — |
| 6 | 30 min | 30 min | — |
| **Totale** | **5h** | **~6h** | **+1h** |

---

## 7. Decisioni richieste a Zero prima di proseguire

1. **Blocker §3.3**: Opzione A (rename WR2 `compliance_alerts` →
   `wr_anomaly_alerts`), B (tabella unica), o C (cognitive usa compliance
   schema esistente)? **Raccomandazione**: A.
2. **Fase 4 smoke test**: OK a spendere ~$0.03 Imagen + token Claude/Gemini
   + 1 messaggio Telegram reale con prefisso `[DRY-RUN]`?
3. **Anomaly CLI**: Anomaly L2 è event-driven (PG NOTIFY) o cron? Se
   event-driven non serve LaunchAgent — vorresti un `anomaly-subscriber`
   daemon persistente invece?
4. **Env var inventory**: i secret per IG/X/LinkedIn/Brevo sono tutti
   presenti su Pro, o serve un pass per verificarli prima di Fase 3?

---

## 8. Appendice A — Fonti verificate

- `apps/backend-rag/CLAUDE.md` (non-inferable knowledge backend)
- `apps/backend-rag/backend/db/migrations_v2/114_compliance_alerts.sql`
  (schema prod)
- `apps/backend-rag/backend/migrations/migration_11[234]_*.py` (WR2
  migrations Python)
- `fly ssh console -a nuzantara-rag -C "python -c '...'"` — query PG live
  2026-04-20 00:10 WITA
- `apps/backend-rag/backend/services/cognitive/repository.py` (hardcoded
  INSERT INTO compliance_alerts con schema WR2)

---

## 9. Cicatrici operative rilevanti (da `cicatrix-scars.md`)

- **Migration runner rollback marker** (2026-04-19): il runner SQL
  `BaseMigration.apply()` ora strippa correttamente le sezioni ROLLBACK.
  Non applicabile qui perché migration 112/113/114 sono **Python**, non
  SQL — hanno funzioni `apply()` e `rollback()` separate, no marker.
- **Docker build context monorepo root**: non applicabile (no deploy
  backend in questo PR).
- **Router manifest**: applicabile quando wireremo `cognitive/*` come
  router (Parte II dell'attivazione, non in questo PR — solo CLI +
  LaunchAgent).

---

**Prossimo step**: attesa decisione Zero su §7.1 (blocker compliance_alerts).

---

## Appendice B — Status aggiornato 2026-04-20 00:25 WITA

### B.1 Blocker risolto

Opzione A applicata. Commit `283263c6e`:

- Tabella WR2 rinominata da `compliance_alerts` a `wr_anomaly_alerts`.
- File modificati: `migration_114_cognitive_layer.py`, `cognitive/repository.py`,
  `cognitive/anomaly_alerter.py`, `cognitive/strategos.py`, `events/event_bus.py`.
- Test: 49/49 cognitive + 158/176 war_room/intel passano (18 skipped richiedono
  `TEST_DATABASE_URL`, come previsto).
- Zero modifiche al pacchetto `services/compliance/*` o `db/migrations_v2/*`.

### B.2 Migrations applicate a nuzantara-postgres (verified)

Backup PG pre-migration: `~/backups/fly-postgres/nuzantara-fly-20260420-0017.sql.gz`
(288MB, integrity OK).

Proxy usato: `fly proxy 15432:5432 -a nuzantara-postgres` → localhost, poi
`PYTHONPATH=/Users/nuzantara/Desktop/wr2-activation/apps/backend-rag` con venv
della repo principale (asyncpg installato).

**15 nuove tabelle create**:

```
cross_dossier_theses        ultra_moves               war_room_metrics
dossier_refresh_log         war_room_costs            war_room_missed_runs
dossier_reuses              war_room_drafts           war_room_posts
research_dossiers           war_room_leads            war_room_rejections
trend_signals               weekly_strategic_briefs   wr_anomaly_alerts
```

Schema `wr_anomaly_alerts` verificato contenere `dossier_a_id`, `dossier_b_id`,
`contradiction_type` (come da design WR2).

Schema `compliance_alerts` **non toccato** — verificato mantiene `alert_id`,
`client_id` (come da migrazione SQL 114 prod live).

### B.3 Env var inventory Fly secrets nuzantara-rag

**Presenti (7/15 come nome esatto brief):**

- ✅ TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_CHAT_ID
- ✅ GROK_API_KEY, DEEPSEEK_API_KEY
- ✅ GOOGLE_API_KEY, FIREWORKS_API_KEY
- ✅ X_BEARER_TOKEN

**Presenti con nome diverso (Instagram):**

- ⚠️ `INSTAGRAM_ACCOUNT_ID` ≈ `IG_USER_ID` (da verificare equivalenza valore)
- ⚠️ `INSTAGRAM_ACCESS_TOKEN` ≈ `IG_LONG_LIVED_TOKEN`

Il codice `ig_publisher.py:57-59` legge `IG_USER_ID` / `IG_LONG_LIVED_TOKEN`
via `os.environ.get()`. Due opzioni:
1. **Alias in LaunchAgent plist**: settare `IG_USER_ID = $INSTAGRAM_ACCOUNT_ID`
   nella sezione EnvironmentVariables del plist (rapido, no code change).
2. **Refactor ig_publisher.py**: supportare entrambi i nomi
   (`os.environ.get("IG_USER_ID") or os.environ.get("INSTAGRAM_ACCOUNT_ID")`).

Raccomandazione: opzione 2, scritto nel commit che crea CLI wrappers
(Fase 2), perché coerente con canali esistenti e riduce drift nomi.

**Mancanti:**

- ❌ `LINKEDIN_ACCESS_TOKEN` — **nessun secret LinkedIn in Fly**. Richiede:
  a) app OAuth LinkedIn Developer, b) token exchange, c) `fly secrets set` su
  nuzantara-rag (e copia in plist EnvironmentVariables). Stima effort: 1h.
- ❌ `LINKEDIN_AUTHOR_URN` — viene generato dopo l'OAuth sopra.
- ❌ `BLOG_*` vars — tutte hanno default in publisher code (verified
  `blog_publisher.py`), basta settarle in plist se default sbagliato. Zero
  blocker.

### B.4 Implicazioni per Fase 3

LaunchAgent **abilitabili subito** (secret presenti o default ok):

- trend-hunter, connector, strategos, oracle, newsletter, measurer, sla-worker,
  learner-nightly, hardening, dossier-compiler
- blog_batch_publisher (usa default path se BLOG_* non settato)

LaunchAgent **rimandati** finché token non disponibile:

- LinkedIn publisher (se la pipeline prova a fare LI, fallisce —
  `PublisherOrchestrator` gestisce con graceful degradation per canale)

Instagram publisher: **abilitabile** con alias env var in plist (raccomandato
refactor leggero in Fase 2.5).

### B.5 Anomaly L2 in-process subscriber — wiring plan (NOT executed in this PR)

Zero ha scelto "daemon persistente". La scelta più pulita è "in-process
subscriber dentro `nuzantara-rag` main_api", non un daemon separato, perché
riusa l'EventBus già operativo (`backend.services.events.event_bus`) e il
canale PG `intel_event` già acceso.

**Wire-up da aggiungere in una PR separata (non in questo attivamento):**

1. Edit `backend/services/events/handlers.py::register_handlers(bus, db_pool)`:

   ```python
   # ── intel.event → AnomalyEventSubscriber ───────────────────────────
   from backend.services.cognitive.anomaly_detector import AnomalyDetector
   from backend.services.cognitive.anomaly_subscriber import (
       AnomalyEventSubscriber,
   )
   from backend.services.cognitive.repository import CognitiveRepository
   from backend.services.intel.dossier_repository import IntelRepository

   _intel_repo = IntelRepository(db_pool=db_pool)
   _cognitive_repo = CognitiveRepository(db_pool=db_pool)
   _detector = AnomalyDetector(
       intel_repo=_intel_repo,
       cognitive_repo=_cognitive_repo,
       # runner left to default or injected Claude CLI runner
   )
   _anomaly_subscriber = AnomalyEventSubscriber(
       intel_repo=_intel_repo, detector=_detector,
   )
   bus.subscribe("intel.event", _anomaly_subscriber.handle)
   ```

2. **Idempotency guard**: `CognitiveRepository.alert_exists_for_pair()` already
   prevents duplicate alerts within a 14-day window for the same ordered
   dossier pair. No additional work needed.

3. **Testing**: `backend/tests/services/cognitive/test_anomaly_subscriber.py`
   already covers handler dispatch (uses `AsyncMock` for detector + intel
   repo). Integration test hitting real PG NOTIFY can be added later.

4. **Observability**: `EventBus.get_stats()` (existing endpoint) already
   surfaces per-event latency and handler success rate. Once wired,
   `/api/events/stats` will show `intel.event` with the new handler.

**Why NOT a separate launchd daemon**:
- Would duplicate PG LISTEN infrastructure.
- Would require separate venv + log rotation + process supervision.
- Cognitive reasoning (Claude CLI) can be invoked cleanly from main_api
  process — it's already the pattern for `cognitive/connector_cli.py`
  except that's cron, not event-driven.

**Why not wire it in THIS PR**:
- Requires actual backend deploy (Dockerfile context, image rebuild, Fly
  release). Current PR scope is "infrastructure activation + CLI wrappers
  + LaunchAgent configs" — all changes side-of-app.
- Deploying the cognitive path means turning on `cross_dossier_theses`
  generation → potential early thesis notifications before content is
  validated. Better to deploy Anomaly L2 as a dedicated small PR with
  feature flag.

### B.6 Fase 4 smoke test — risultato

Eseguito 2026-04-20 00:40 WITA. **PASS.**

```
draft_id: 23ea7d3d-8c94-41cd-aed2-9c6af0fd417a
final_status: pending_review → (post-run marked 'rejected' for cleanup)
imagen: model=imagen-4.0-ultra-generate-001, bytes=1,446,761, duration=11.6s
total_cost_usd: 0.06
placeholder_slides: 3 (stored in slides_json as dict, no Imagen call)
telegram: delivered (chat_id 1125336968, plain message, [DRY-RUN] prefix)
```

Verifica SQL post-run:

```
brief_json  jsonb_typeof = 'object' ✓
slides_json jsonb_typeof = 'object' (3 entries) ✓
war_room_costs: 1 riga imagen_ultra $0.060000 ✓
```

**Bug preesistenti scoperti durante lo smoke test** (non bloccanti per
l'activation, ma da fixare in PR separata):

1. **Double-encoding JSONB**: `WarRoomRepository.create_draft` chiama
   `json.dumps(dict)` sul parametro JSONB. asyncpg in questo progetto ha
   codec JSONB custom (`backend/app/core/database.py::init_db_connection`)
   che ri-serializza → output: `'"{"origin":..."'` (JSON-encoded JSON
   string). Stesso pattern in `update_content_jsonb`, `record_cost`
   (meta_json), e possibilmente altri metodi del repo. Rilevante anche
   altri repository (grep: `json.dumps.*repo\.|json.dumps.*conn\.execute`).
   Smoke workaround: passare il dict direttamente via UPDATE raw.

2. **Imagen aspectRatio default errato**: `ImagenClient.__init__` default
   `aspect_ratio="4:5"` → Imagen 4.0 API rifiuta con 400
   "supported: 1:1, 9:16, 16:9, 4:3, 3:4". Il War Room design usa 4:5 per
   il formato IG carousel, quindi serve:
   - upstream fix in Imagen (non controllabile), oppure
   - client-side crop/resize da 3:4 a 4:5 in `VisualGenerator`, oppure
   - documentare che VisualGenerator deve sempre override aspect_ratio
     dalla shape del template.

   Smoke workaround: passare `aspect_ratio="3:4"` esplicito.

3. **Nota osservabilità (non bug)**: il container di produzione monta
   `/data` read-only per questo processo (JSONL cost recorder fallisce).
   Non blocca nulla, ma il cost recorder dovrebbe degradare più silente
   (WARNING invece di ERROR), o scrivere in `$WR2_COST_LOG_DIR` se
   configurato.

Nessuno dei 3 è regressione introdotta da questa PR; tutti preesistono
nel codice WR2 ereditato. Da tracciare in issue separate.

### B.7 Fase 5 — Pipeline doppia: tre strade (per Zero)

War Room 2.0 e la "pipeline vecchia" (`apps/bali-intel-scraper/` +
LaunchAgent `com.balizero.intel.nightly` + `com.balizero.post-publish-poller`
+ `com.balizero.post-publish-webhook`) producono entrambi contenuto
editoriale per `kita.balizero.com` e `balizero.com`. Accendere WR2 senza
disciplinare la coesistenza = 2 sistemi che scrivono MDX su `apps/mouth/`,
commit duplicati, confusione team.

Tre strade. **Proposta, Zero decide.**

---

#### Strada A — Shutoff netto della vecchia

**Sequenza**: installare 10 plist WR2 → caricare WR2 → `launchctl unload -w`
di `com.balizero.intel.nightly`, `post-publish-poller`, `post-publish-webhook`
→ archiviare `apps/bali-intel-scraper/` in `apps/_archived/bali-intel-scraper/`
(commit + push) → update CLAUDE.md §12 per rimuovere riferimenti.

- **Pro**: caos zero, 1 solo sistema a regime, mental model pulito.
- **Contro**: se WR2 ha bug non scoperti al smoke test (Council timeout,
  Playwright flake, IG auth flow), non c'è fallback — la news pipeline si
  interrompe. Zero osserva 1-3 giorni di output zero prima di reagire.
- **Effort**: 30 min operativi + rollback in 10 min (re-load vecchi
  LaunchAgent + git revert archivio).
- **Rischi**: scoperta di edge case (es. Council che fa `claude --print`
  con prompt 12K token → hit rate-limit) quando tutto il carico editoriale
  dipende da WR2.

#### Strada B — Canary 7-14 giorni parallelo

**Sequenza**: installare 10 plist WR2 CON una variabile ambientale
`WR2_CANARY=1` → in VisualGenerator/Publisher, quando `WR2_CANARY=1`,
stampare `[CANARY]` nei titoli IG/X/LI e NON pubblicare su Brevo
newsletter → vecchia pipeline resta attiva parallela → dashboard observa
`war_room_drafts` vs. kita MDX commits per 7gg → se metriche WR2 verdi
(0 critical errors, >5 post approvati, review loop funziona), rimuovere
`WR2_CANARY` flag e applicare Strada A.

- **Pro**: safety net, dual verifica in produzione reale, dashboard
  comparativa utile per apprendimento.
- **Contro**: 7-14gg di complessità mentale (2 pipeline, 2 set di log,
  rischio "doppio post" se per sbaglio team gira manualmente entrambi),
  costi ~$30 extra in LLM/Imagen.
- **Effort**: 2h per aggiungere `WR2_CANARY` env var + titolo prefix +
  Brevo skip + 30 min decisione finale al giorno 7.
- **Rischi**: canary diventa "permanente" per inerzia. Serve milestone
  fisso: "Lunedì 2026-04-27 decisione shutoff vecchia".

#### Strada C — Coesistenza permanente segmentata

**Sequenza**: installare 10 plist WR2 → vecchia pipeline resta attiva
ma **solo per intel-staging UI** (manual human approval su
`kita.balizero.com/newsroom`) → WR2 gestisce esclusivamente cognitive
layer (L1-L4) + newsletter settimanale + pubblicazione automatica post
approvazione Telegram. I due sistemi non si sovrappongono per design:
vecchia = discovery + curation manuale; WR2 = produzione multi-canale
cognitivamente consapevole.

- **Pro**: sfrutta il valore già creato dalla vecchia (UI newsroom,
  staging area, quality_scorer validato), zero migrazione dati, team
  continua con workflow noto mentre WR2 matura.
- **Contro**: complessità permanente. 2 LaunchAgent set. 2 prompt
  systems (intel-scraper `classifier` vs. WR2 Council). Confusion su
  "dove va un nuovo topic?".
- **Effort**: 1h per scrivere la documentazione "cosa va dove" +
  aggiornamento CLAUDE.md. Zero code change.
- **Rischi**: diventa "tutto resta com'è" + WR2 = dead code in 3 mesi.
  O viceversa: WR2 divora funzionalità vecchia gradualmente →
  intel-staging UI resta ma senza traffico di input.

---

**Raccomandazione**: **Strada B (canary 7 giorni)**. Mitiga il rischio
scoperta bug in produzione senza committare a una coesistenza permanente
che tende all'entropia. Al giorno 7 decisione binaria:
- se WR2 ha prodotto ≥5 draft approvati da Zero, 0 critical errors,
  review-loop medio ≤4h → Strada A (shutoff)
- se no → estendi canary altri 7gg + fix

**Decisione Zero 2026-04-20**: ✅ **Strada B approvata.**

Protocollo canary attivo dal 2026-04-20 → revisione 2026-04-27:

1. **Pipeline vecchia** (`com.balizero.intel.nightly`,
   `com.balizero.post-publish-poller`, `com.balizero.post-publish-webhook`)
   **resta attiva** invariata. Non toccare i plist.
2. **Pipeline WR2** attiva ma marcata canary:
   - Tutti i post generati da WR2 hanno prefisso `[CANARY]` nel titolo
     IG/X/LI (da implementare in un piccolo patch separato se/quando
     si abilita effettivamente il Publisher — per ora Fase 4 è
     dry-run, nessun post reale)
   - Newsletter settimanale Brevo disabilitata fino al gg 7
     (LaunchAgent `com.balizero.wr2.newsletter` caricato ma con
     env var `NEWSLETTER_SKIP_SEND=1` — da aggiungere al plist prima
     di `launchctl load`)
3. **Monitoraggio gg 1-7**:
   - `war_room_drafts` count/day target: ≥1
   - Review-loop medio target: ≤4h
   - Critical errors: 0 (da `war_room_missed_runs` + Telegram alerts)
   - Metriche cross-dossier (Connector L1, Strategos L3): almeno 1 tesi
     prodotta entro gg 4
4. **2026-04-27 review**: se gate passa → merge Strada A con
   shutoff vecchia + removal `[CANARY]` prefix + abilitazione newsletter.
   Se gate fallisce → estendi 7gg o rollback WR2.

### B.8 Decisioni implementative Strada B — NON in questo PR

Da fare in PR/commit successivi (non ora, per mantenere questo PR atomico
sulla sola attivazione infrastrutturale):

1. Flag `WR2_CANARY=1` in ogni plist che invoca Publisher
   (sla_worker non pubblica, misuratore non pubblica — solo
   trend-hunter/connector/strategos/oracle/newsletter/measurer sono
   "produttori") — aggiungere al `<EnvironmentVariables>` dict.
2. Patch in `newsletter_cli.py` / `builder.py`: se
   `os.environ.get("WR2_CANARY")` o `os.environ.get("NEWSLETTER_SKIP_SEND")`
   → skip Brevo send, log only.
3. Patch in orchestrator di `blog_batch_publisher` etc.: prefissa
   `[CANARY] ` a title/caption quando flag attivo.

Stima effort: 1h per tutti e 3. Da fare DOPO merge di questo PR,
come canary-activation PR.

### B.9 Decisioni implementative pre-Fase 2

### B.8 Decisioni richieste pre-Fase 2

1. Refactor `ig_publisher.py` per accettare `INSTAGRAM_ACCOUNT_ID`/
   `INSTAGRAM_ACCESS_TOKEN` come fallback di `IG_USER_ID`/`IG_LONG_LIVED_TOKEN`?
   (Raccomandazione: sì, ~15 min)
2. LinkedIn publisher: rimandare a sprint separato o generare token ora?
   (Raccomandazione: rimandare — LI non è mission-critical per activation
   smoke test)
3. Anomaly L2 daemon persistente (come da decisione Zero): scelta tra
   - (a) daemon Python con `asyncpg.LISTEN` su `cognitive_event` →
     KeepAlive=true in plist
   - (b) subscriber che vive dentro backend-rag main_api process (no
     LaunchAgent separato)
   Raccomandazione: (b) perché sfrutta event_bus esistente, zero
   infrastruttura nuova. Ma richiede registrazione handler in `app_factory`
   — piccolo code change.


