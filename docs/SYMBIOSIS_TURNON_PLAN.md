# SYMBIOSIS — Turn-On Plan (2026-05-06)

**Owner**: Zero (Antonello Siano)  
**Branch**: feat/symbiosis-turnon-2026-05  
**Premise**: 70% del sistema simbiotico è già scritto in 6+ mesi di lavoro
(cell-core, organism, HGT, Innervation Genoma). Solo il 10% è acceso.
Questo piano accende il restante 60% in 3-4 settimane.

---

## Stato di partenza (verificato file:line, 2026-05-06)

### Già costruito e testato

- `packages/cell-core/cell_core/` — PulseLoop 6 fasi, Genome SQLite
  927 LOC, HGT publisher+consumer+coordinator (3 moduli), Observatory
  cross-machine via PG, Lifecycle 5 fasi maturazione, Homeostasis,
  Identity SelfModel.
- `apps/organism/organism/supervisor/` — daemon W1 shadow mode,
  claude_brain, consiglio_gate, 11 actuators (restart/quarantine/
  cleanup/notify), heartbeat Redis key `organism:supervisor:heartbeat`
- `apps/organism/organism/organs_registry.yaml` (Innervation Genoma —
  file renamed 2026-05-08 IG-3, legacy alias `genome.yaml` symlink works
  until 2026-06-08) — registry schema validato con SHA256 + pre-commit
  hook (NB-1 ADR-7 HALT-on-mismatch)

### Da accendere

1. Solo 26/163 organi reali registrati nel Innervation Genoma (16%)
2. HGT attivo solo su 3 celle (mata-garuda, crm-cell, bali-intel-scraper)
3. CELL_OBSERVATORY_EMIT=true settato su pochi LaunchAgent
4. Supervisor in W1 shadow (decide ma non agisce)
5. Consiglio v1 gate esiste, manca cron settimanale che lo attiva

---

## Le 4 fasi

### FASE 1 — Innervation Genoma activation (settimana 1)

**Obiettivo**: passare da 26 a 100+ organi registrati, abilitando
heartbeat + recovery automatico via Supervisor.

**Lavoro parallelizzabile su 4 sessioni Claude (worktree isolati)**:

| Sessione | Scope                                                 | Output                 |
| -------- | ----------------------------------------------------- | ---------------------- |
| W1-A     | Mata-garuda 30 agents + 13 workers                    | 43 entries organs_registry.yaml |
| W1-B     | WR2 14 unregistered LaunchAgents                      | 14 entries organs_registry.yaml |
| W1-C     | Pro background crons (intel/translate/sentinel/+ ~10) | ~10 entries            |
| W1-D     | Mini LaunchAgents (15 mata-garuda + others)           | ~20 entries            |

**Files**:

- `apps/organism/organism/organs_registry.yaml` (espandere da 26 a ~100 entries)
- `apps/organism/organism/tools/validate_organs_registry.py` (run --update-checksum)
- Pre-commit hook `validate-organs-registry` (già attivo; rename 2026-05-08 IG-3)

**Test**:

- `apps/organism/tests/test_genoma_activation.py::test_all_registered_organs_resolvable`
- Supervisor heartbeat compliance: ≥80% organi heartbeat in finestra 60s

**Metrica before/after** (Pilastro 7):

- Before: 26/163 organi visibili (16%)
- After: ≥100/163 organi visibili (60%+)

**Costo**: 5-7 giorni (parallelizzato 4 sessioni → 2 giorni wall-clock + 1
giorno review + 1 giorno canary su Mini)

---

### FASE 2 — Cell Observatory full coverage (settimana 1-2)

**Obiettivo**: ogni organo enrolled in organs_registry.yaml emette pulse a
events_outbox via observatory cross-machine.

**Lavoro**:

1. Patch tutti i LaunchAgent enrolled per aggiungere
   `CELL_OBSERVATORY_EMIT=true` + `EVENTBUS_DATABASE_URL=postgres://...flycast`
   in EnvironmentVariables (idempotente — usa plutil -insert come fatto
   per intel-bridge oggi).
2. Verifica che ogni emit arrivi a `events_outbox` PG su Fly via
   Tailscale. Dashboard SQL: `SELECT channel, COUNT(*) FROM events_outbox
WHERE consumed_at IS NULL GROUP BY channel`
3. Estendere `events_outbox` triggers ai canali ancora volatili:
   `lkpm_ingest_completed`, `federation_alert`, `cell_pulse_observed`,
   `measurer_event`, `crm_welcome_completed`, `asset_provenance` (6
   migrations da scrivere, una per canale).

**Files**:

- `apps/backend-rag/backend/db/migrations_v2/{147..152}_*.sql` (6 nuove
  migration, una per canale)
- Bulk patcher Python `~/scripts/observatory-emit-enable-bulk.py` che
  legge genome.yaml + plutil -insert su ogni plist
- `apps/cell-observatory-collector/` (già esiste, verificare connection
  pool size adeguato a +60 organi)

**Test**:

- `backend/tests/services/events/test_outbox_full_coverage.py` —
  asserzione che ogni canale di PG_CHANNEL_MAP scrive in
  events_outbox prima di pg_notify
- E2E: kill un LaunchAgent, attendere 90s, verificare che Supervisor
  detect + restart + nuovo pulse arriva

**Metrica before/after**:

- Before: 6/12 canali durabili, ~5/100 organi emettono pulse
- After: 12/12 canali durabili, ≥90/100 organi emettono pulse ogni HB

**Costo**: 4-5 giorni (1 giorno bulk patcher + 2 giorni 6 migration +
1 giorno test E2E + 1 giorno canary)

---

### FASE 3 — HGT espansione (settimana 2-3)

**Obiettivo**: passare da 3 a 10+ celle che pubblicano e consumano
skill via Redis stream `cell:skills`.

**Lavoro**:

1. Identificare 7 nuove celle candidate (audit Fase 1 propone:
   nlm_feeder, scorer, kg_linker, classifier_worker, contradiction_worker,
   semantic_diff_worker, dedup_worker)
2. Ogni candidato: aggiungere `Genome` instance + `record_skill()` in
   loop principale + `HGTPublisher` + `HGTConsumer` con
   `interested_domains`
3. Configurare Redis su Mini (location single-node con accesso da
   Tailscale per organi cross-machine — già funzionante per
   mata-garuda)
4. Definire domini di interesse per ogni cella (es. nlm_feeder
   interessato a `nlm`, `bahasa`, `regulation`; scorer a `relevance`,
   `bali-zero-domain`)

**Files**:

- 7 worker patches (es. `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py`)
  che aggiungono Genome + HGT pub/sub
- `apps/mata-garuda/scripts/run_<worker>.py` aggiornati per istanziare
  HGT con redis_client connesso a Mini
- Doctrine update `apps/mata-garuda/CLAUDE.md` per documentare
  "Mata-garuda celle ora condividono skill via cell:skills, MAI dati
  OSINT — solo procedure operative astratte"

**Test**:

- `packages/cell-core/tests/test_hgt_e2e_multi_cell.py` —
  pubblica skill da cella A, verifica che cella B la riceve con
  decay 0.9× e la integra nel proprio Genome
- Misurare `XLEN cell:skills` su Mini (deve essere ~10-50/giorno
  steady-state con 10 celle attive)

**Metrica before/after**:

- Before: 3 celle attive HGT, ~0 skill scambiate/giorno
- After: 10 celle attive, ≥5 skill scambiate/giorno con confidence ≥0.7

**Costo**: 5-7 giorni (1 giorno per cella patch + test, 7 celle ÷ 2
sessioni parallele = 3.5 giorni + 1 giorno doctrine + 1 giorno E2E)

---

### FASE 4 — Consiglio v1 cron + Supervisor W2 (settimana 3-4)

**Obiettivo**: settimanalmente un LLM moderatore legge tutti i Genome
delle celle, identifica contraddizioni/correlazioni, propone azioni.
Supervisor passa da shadow a dispatch.

**Lavoro**:

1. **Consiglio cron**: nuovo LaunchAgent `com.nuzantara.consiglio.weekly`
   - Schedule: domenica 16:00 WITA (riprende lo schedule di Judgement
     Day documentato in CLAUDE.md cron Air)
   - Script: `scripts/consiglio_weekly.py` (~200 LOC) che:
     a. Legge ultimi 7 giorni di skill+scar+insight da tutti i Genome
     (cell-core SQLite + mata-garuda KB + apps/organism database)
     b. Invoca Claude Opus 4.7 (1M ctx) come moderatore con prompt
     che cita SYMBIOSIS.md §111-120
     c. Opzionalmente invoca Gemini 3.1 Pro o DeepSeek R1 come
     secondo parere su 1-2 punti specifici
     d. Salva minutes in `~/.agent/consiglio/minutes_YYYY-MM-DD.md`
     - crea entries `consiglio_decision` events_outbox
       e. Telegram notify a Zero con riassunto (3-5 righe)
2. **Supervisor W2**: cambiare flag in `daemon.py` da
   `SHADOW_MODE = True` → `False`. Test estensivo prima.
3. **Consiglio gate** già esiste in `consiglio_gate.py` — collegare
   il cron al gate per logging strutturato

**Files**:

- `~/Library/LaunchAgents/com.nuzantara.consiglio.weekly.plist`
- `scripts/consiglio_weekly.py` (nuovo)
- `apps/organism/organism/supervisor/daemon.py` (rimozione SHADOW_MODE)
- `apps/organism/tests/test_supervisor_dispatch_w2.py` (E2E con
  injected fault → recovery action verificata)

**Test**:

- 1 settimana di Supervisor W2 con monitoring intensivo (Telegram alert
  su ogni decisione dispatch)
- Consiglio dry-run su 7 giorni di dati storici prima di attivare cron

**Metrica before/after**:

- Before: 0 deliberazioni/settimana, Supervisor 0 dispatch
- After: 1 deliberazione/settimana con minutes pubblicate, Supervisor
  ≥1 dispatch al giorno (auto-restart, auto-quarantine, etc.)

**Costo**: 6-8 giorni (2 giorni Consiglio script + prompt design +
1 giorno LaunchAgent + 1 giorno dry-run + 1 giorno Supervisor W2 test

- 2 giorni canary)

---

## Workflow agentico parallelo

**Constraint**: max 3 sessioni Claude concorrent (3× MAX plans).

**Pattern proven (wave-orchestrator dal 2026-04-22)**:

- 1 sessione Claude Opus = orchestrator (questa, current)
- 3 sessioni Claude Opus su worktree isolati (FASE 1 W1-A/W1-B/W1-C/W1-D
  ruotando 3 alla volta)
- Codex CLI (sandbox r/w) per refactor mass-edit (es. bulk plist
  patcher in FASE 2)
- Gemini 3.1 Pro per esplorazione codebase + edge cases (FASE 1
  validation, FASE 4 prompt design)
- DeepSeek R1 per fact-check + reasoning su decisioni architetturali
  (FASE 4 prompt review, FASE 2 migration safety)
- NotebookLM bipolar verifier (NB-1 architettura + MATA GARUDA family)
  per ground-truth check su ogni fase

**Distribuzione fasi**:

- Settimana 1: 3 sessioni Claude (FASE 1 W1-A, W1-B, W1-C parallel) +
  Codex (W1-D batch tool)
- Settimana 2: 2 sessioni Claude (FASE 2 migration + bulk patcher) +
  Gemini (test coverage exploration)
- Settimana 3: 2 sessioni Claude (FASE 3 cell patches) + DeepSeek
  (HGT domain design review)
- Settimana 4: 1 sessione Claude (FASE 4 Consiglio + Supervisor W2) +
  Gemini + DeepSeek + NotebookLM (Consiglio dry-run multi-LLM)

**Sync points**:

- Ogni 90min: WIP commit + push (cicatrix antibody #2 da
  cicatrix-scars.md "branch hijack")
- EOD: SESSION_REPORT.md per ogni worktree
- EOW: tri-LLM review (Claude+Gemini+DeepSeek) prima di merge in main

**Worktree isolation**:

- Ogni sessione su `~/Desktop/nuzantara/.worktrees/<name>` separato
- Branch dedicato `feat/symbiosis-W<N>-<scope>`
- Symlinked venv `apps/backend-rag/.venv` shared

**Costo arsenale**:

- Claude MAX: $0 (3 plan attivi, OAuth)
- Codex: $0 incrementale ($200/yr già pagato)
- Gemini: $0 (free tier 100q/day, basta)
- DeepSeek: ~$2 totali (200 query × $0.01)
- NotebookLM: $0 (free)
- **Totale: $2 per 4 settimane**

---

## Rischi noti

1. **Branch hijack** (cicatrix-scars STRUCTURAL). Mitigazione: worktree
   isolati + commit/push entro 30s di ogni edit.
2. **Supervisor W2 prematuro**: se attivato senza dry-run sufficiente
   può fare restart loop. Mitigazione: 1 settimana monitoring
   intensivo + kill switch via Telegram.
3. **HGT skill explosion**: troppe skill di bassa confidence inquinano
   i Genome consumer. Mitigazione: confidence threshold 0.7 (già
   hardcoded in HGTPublisher), decay automatic in HGTConsumer.
4. **Consiglio LLM cost**: se Opus 4.7 1M ctx legge tutti i Genome,
   prompt può superare cache TTL. Mitigazione: pre-aggregare in
   sintesi 7-day prima di passare a Claude.
5. **Mini single-point Redis**: `cell:skills` stream vive solo su
   Mini Redis. Se Mini down, HGT pause. Accettabile (graceful
   degradation per SYMBIOSIS Legge 4) — ogni cella usa Genome locale
   intanto.

---

## Decision points — Zero approval ratified 2026-05-06 14:55 WITA

1. ✅ **Mata-garuda enrollment**: enrolled in Innervation Genoma
   exposing OPERATIONAL metadata only (heartbeat ts, last_activity,
   error_count, items_processed). NO OSINT content exposed via
   observatory. Documented in W1-A enrollment PR.
2. ✅ **Supervisor W2 dispatch**: activated at week 4 with intensive
   Telegram monitoring + kill switch. Shadow logs preserved as
   audit trail.
3. ✅ **Consiglio cron schedule**: Sunday 16:00 WITA (alongside
   existing Judgement Day cadence). LaunchAgent
   `com.nuzantara.consiglio.weekly`.
4. ✅ **Air decommissioning**: `shared/escalations_air.jsonl`,
   `shared/escalations_pro.jsonl`, and any `peer=air` references in
   genome.yaml / scripts marked DEPRECATED. Air symbol kept for
   archaeological grep but no path is active. Topology officially
   2-node: Pro + Mini-Pro2 + Fly.

---

## Metriche di successo finale (4-week)

| Indicatore                          | Before           | Target                  | Pilastro SYMBIOSIS         |
| ----------------------------------- | ---------------- | ----------------------- | -------------------------- |
| Organi in genome.yaml               | 26               | ≥100                    | Pilastro 7 (Misura)        |
| Canali events_outbox durabili       | 6/12             | 12/12                   | Legge 4 (event-driven)     |
| Celle HGT attive                    | 3                | 10+                     | Pilastro 2 (Accumulazione) |
| Skill scambiate/giorno              | ~0               | ≥5                      | Pilastro 3 (Condivisione)  |
| Supervisor dispatch/giorno          | 0 (shadow)       | ≥1                      | Pilastro 1 (Riflessione)   |
| Consiglio deliberazioni             | 0                | 1/settimana             | Pilastro 4 (Confronto)     |
| Tempo recovery organo morto         | manual ∞         | <90s auto               | Pilastro 7 (Misura)        |
| Densità ontologica KG (mata-garuda) | 0 entities/0 rel | ≥500 entities ≥1500 rel | Pilastro 7                 |

---

**Last updated**: 2026-05-06 14:50 WITA
**Status**: Awaiting Zero approval on 4 decision points above
