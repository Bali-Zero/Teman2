# 00 — Design intent: Cell, Organism, e l'innervazione mancante

**Data**: 2026-04-29
**Autore**: Claude Opus 4.7 max effort, sessione Track C3 Innervation
**Branch**: `feature/innervation-2026-04-29`
**Riferimenti autoritativi**:
- `SYMBIOSIS.md` (LE LEGGI 1-7)
- `VADEMECUM.md` (§11 LaunchAgent, §1 automation)
- `docs/superpowers/specs/2026-04-22-autonomic-organism-design.md` (design spec Organism approvato 2026-04-22, red-team da Gemini 3.1 + DeepSeek + Sonnet 4.6)
- `.claude/rules/cicatrix-scars.md` (8+ scar rilevanti, in particolare 2026-04-29 plist corruption + backend startup_failed)

> **Nota sulla ricostruzione**: questo file è stato perso al filesystem level durante un `git pull origin main` automatico arrivato da nuz-sync watchdog (vedi `02_dispatch_resilience_log.md` § Cosa è successo). È stato ricostruito identico dal context di sessione orchestrator. Lesson per future agent sessions: i file untracked vanno `git add` immediatamente; nuz-sync auto-pull può arrivare in qualsiasi momento. Vedi anche `13_known_gaps.md` per remediation policy.

---

## 1. Domanda di partenza

> "Completare il sistema nervoso e il DNA dell'organismo Nuzantara."

Cosa significa **innervazione** in concreto, oggi (2026-04-29)?

Due strati esistono in repo, in stadi di maturità diversi. Il task non è "costruire da zero un sistema nervoso" — è "**completare le sinapsi mancanti** tra ciò che già esiste, e darle un Genoma autoritativo".

---

## 2. Cell — cosa È oggi vs cosa DOVREBBE essere

### 2.1 Cosa È (osservato leggendo `apps/cell/cell/`)

**Cell è un singolo organo cognitivo "lifecycle-aware"**, non un sistema nervoso distribuito. Architettura:

| Modulo | Funzione |
|---|---|
| `core/pulse.py` | Loop sense→evaluate→think→act→remember ogni ~60s |
| `sensors/` (11) | `health` (backend-rag), `database`, `qdrant`, `ollama`, `error_rate`, `backup`, `cron`, `vercel`, `oauth_health`, `ai_intel`, `channel` (PR #360 appena merged) |
| `effectors/` (5) | `fly_effector` (restart Fly machines), `local_effector` (ollama_restart, run_backup), `logs_effector` (read fly logs), `nlm_effector` (push intel to NB), `telegram` (alert) |
| `cortex/` | `cortex` (skill library + curiosity), `critic`, `curiosity_engine`, `goal_generator`, `skill_library`, `strategy_mutator` |
| `memory/` | `short_term`, `long_term` (rules), `episodic` (significant events), `dreamer` (consolidation) |
| `metabolism/` | `tracker` (budget USD), `attention_allocator` |
| `lifecycle/` | `maturation` (5 fasi: embrione→neonato→giovane→adulto→anziano), `achievement_gate` |
| `identity/` | `self_model`, `journal` (3-day narrative) |
| `fast/` | reflexes <5ms (homeostatic, log_anomaly, trend, cost_guard, mutation_filter, health_triage) |
| `slow/` | `reasoner` (Ollama tier 0/1, ~5-30s) |

**Stato deploy**:
- `~/Library/LaunchAgents/com.cell.organism.plist` LIVE su Pro (cicatrix scar P0-3 plist corruption 2026-04-29 — protetta a 0400 ora che ha leaked secret).
- Cell scrive `cell_pulses` table su Postgres + `cell_alerts` per dashboard.
- 50+ sentinel reports già accumulati in `apps/cell/data/reports/sentinel_2026-04-*.md`.

**Limiti strutturali oggi**:
1. Cell **osserva un solo target esterno**: `nuzantara-rag.fly.dev/health`. Tutti gli altri "sensor" (db, qdrant, ollama, vercel, ai_intel, ecc.) leggono lo stesso `/health` body o servizi locali Pro. Cell **NON sa** se drive_poll_service Air è vivo, se i 7 channel ricevono webhook, se MCP server è up, se i 12 cron Air girano.
2. Cell **NON consuma `organism:events`**. Vive in isolamento dal bus eventi.
3. Cell **NON è registrata nel Genoma** (perché il Genoma non esiste come entità autoritativa).
4. Cell ha skill library locale (`cortex/skill_library.py`) ma **non condivide skill** con altri organi (no HGT cross-cell).

### 2.2 Cosa DOVREBBE essere (per SYMBIOSIS)

Per SYMBIOSIS Pilastro 6 (sovranità locale), Pilastro 4 (graceful degradation), Legge 3 (event-driven):

- Cell deve essere **uno dei tanti organi** dell'organismo, non l'unico. La sua maturità (cortex+lifecycle+memory) è un asset da preservare; la sua **vista limitata** è il bug.
- Cell deve **emettere `organism:events`** quando rileva anomalie nei suoi sensor (il `cron_sensor` rileva un cron rotto → emit `cron_agent_failure`).
- Cell deve **consumare il Genoma** (lista organi attesi) e includere nel pulse "tutti gli organi del Genoma sono vivi?".
- Cell deve continuare a vivere **anche se Organism Supervisor è down** (Legge 4). Supervisor heartbeat check `should_enter_emergency_mode` → modalità autonoma con effector locali.

---

## 3. Organism — cosa È oggi vs cosa DOVREBBE essere

### 3.1 Cosa È (osservato leggendo `apps/organism/organism/`)

**Organism ha tutto il codice scheletrico per la spec 2026-04-22, MA non è deployato attualmente.**

(Insight da NotebookLM NB-14 in `06_notebooklm_history.md`: l'Organism era stato "completed and merged 2026-04-22 across 13 PRs Wave 0-4". Quindi è stato deployato e poi degradato — possibile cause: scar P0-3 plist mass corruption 2026-04-29, oppure spegnimento manuale. Verifica obbligatoria PRIMA di ri-deployare.)

| Componente | Stato codice | Stato deploy 2026-04-29 |
|---|---|---|
| `emit.py` (event helper) | ✅ funzionale, sanitize+JSONL+Redis | ✅ usato da 4 caller: `system_doctor.py`, `sentinel_lib/zombie_hunter.py`, `post_commit_hook.py`, `scheduled_tick.py`, `actuators/base.py` |
| `redis_bus.py` (EventBus) | ✅ JSONL-first poi Redis | ✅ stream `organism:events` esiste, 52 entry totali |
| `heartbeat.py` (supervisor liveness check) | ✅ `supervisor_heartbeat_check()` | ❌ Heartbeat key VUOTO in Redis — **Supervisor non sta girando ora** |
| `schemas.py` (Event, ActionDecision, Severity) | ✅ Pydantic | — |
| `sanitize.py` (anti-prompt-injection) | ✅ deny-list + sanitize_payload | — |
| `blackout.py` + `control_panel.py` (HTTP :1819 /pause /resume) | ✅ token auth | ❌ LaunchAgent `com.nuzantara.organism.control-panel.plist` esiste in repo ma non installato in `~/Library/LaunchAgents/` |
| `supervisor/daemon.py` (consume loop, shadow mode, decisions.jsonl) | ✅ W1.A funzionale | ❌ LaunchAgent `com.nuzantara.organism.supervisor.plist` esiste in repo ma NON installato. Heartbeat empty conferma. |
| `supervisor/decider.py` + `yaml_rules.py` + `incident_context.py` | ✅ L0 YAML matching | — |
| `supervisor/circuit_breaker.py` + `mutex.py` | ✅ Redis-based | — |
| `supervisor/dispatch.py` (whitelist hardcoded) | ✅ shadow-mode + active path placeholder | — |
| `supervisor/ollama_classifier.py` (L1) | ✅ codice presente | — |
| `supervisor/claude_brain.py` (L2 Claude CLI) | ✅ codice presente | — |
| `supervisor/consiglio_gate.py` (L3) | ✅ codice presente | — |
| `actuators/` (11) | ✅ tutti idempotenti, dry-run, WAL, emit done | — |
| `tests/gauntlet/` (10/10 scenari) | ✅ tutti i 10 scenari del design spec | ❌ mai eseguiti contro Pro/Air reale |
| `rules/base.yaml` | ✅ 8 regole iniziali | — |
| `redundancies.yaml` (7 mappature consolidamento) | ✅ presente | ❌ consolidate_redundancy actuator mai invocato in produzione attiva |
| `post_commit_hook.py` | ✅ funzionale (emit `new_module` su nuovi `apps/`) | ✅ ATTIVO (3 entry recenti in JSONL: nuzantara-mcp-browser, drive, zantara-media — 2026-04-24) |
| `scheduled_tick.py` (cron tick produttivo) | ✅ funzionale | ❌ **non c'è LaunchAgent** che lo lanci ogni ora — quindi le 4 regole `scheduled_cleanup_*` non scattano |

**Stato sintetico**: Organism W0+W1+W2+W3+W4 **a livello di codice è completo**. **A livello di runtime è dormente** (no Supervisor, no scheduled_tick cron, no control panel HTTP, no heartbeat).

### 3.2 Cosa DOVREBBE essere (per SYMBIOSIS + spec 2026-04-22)

Per il design spec autoritativo (sezione 2 Architecture), Organism deve essere:
1. Supervisor daemon launchd su Pro (always-on, manual fallback Air).
2. Control panel HTTP :1819 sempre raggiungibile.
3. scheduled_tick cron ogni ora che emit eventi `scheduled_tick`.
4. Tutti i guardian (35 esistenti) wrappati con `emit_event()` → bus.
5. Whitelist actuator dispatchable senza approvazione.
6. Blackout flag e Telegram notifier per azioni HUMAN_ONLY.
7. Gauntlet test passati in staging Pro+Air prima del flip da shadow → active.

Il design spec è già stato red-team validato da Gemini+DeepSeek+Sonnet — non riapro la discussione architetturale. **Il gap è esecuzione, non design.**

---

## 4. Il Genoma autoritativo — cosa esiste, cosa manca

### 4.1 Mappe parziali esistenti

| Mappa | Tipo | Copertura |
|---|---|---|
| `apps/organism/organism/redundancies.yaml` | "Quali organi sono duplicati e come consolidarli" | 7 redundancies mappate (heartbeat, compliance pipeline, nb-batch, etc.) — solo organi *duplicati*, non l'inventario completo |
| `apps/cell/cell/sensors/*.py` | "Cosa Cell monitora" | 11 sensor — ma copre solo backend-rag /health, infra locale, e poco altro. NON è l'atlante della flotta. |
| `INDEX.md` | "Top of mind organi" | Lista narrativa di 21 apps + 5 packages. NON ha schedule, NON ha owner, NON ha recovery action. |
| `scripts/automation_catalog.json` | "Automazioni catalogate" (VADEMECUM §1.9) | Esiste? Da verificare. Probabilmente parziale. |
| `~/.agent/decisions/job_registry.json` | "Sentinel job registry" (VADEMECUM §11.8) | Esiste, Sentinel attivo, ADR-7 SHA256 signature (NB-1). |

**Nessuna di queste mappe è il Genoma**. Il Genoma deve essere:

> **Una sorgente autoritativa unificata che, per ogni organo della flotta, dichiara: ID stabile, runtime, owner, dipendenze, schedule, atteso heartbeat, recovery action, last-seen.**

### 4.2 Decisione architetturale (NON inventare un terzo schema concorrente)

Il design spec 2026-04-22 §2 definisce già il bus eventi e gli actuator. Il **Genoma come schema unificato** **non è esplicitato**, ma è implicito nel pattern "ogni organo emit evento + Supervisor decide". Costruire il Genoma significa:

1. **Estendere `redundancies.yaml`** in `genome.yaml` (o equivalente) come registry autoritativo della flotta — non solo le ridondanze ma TUTTI gli organi. **NON SQLite per shared state cross-machine** (NB-1 ADR-3).
2. **Cell sensor "genome_aggregator"** che legge il Genoma + last-seen di ogni organo dal bus + risponde "chi è vivo?". (NB-1 architettura: estende il pattern PulseLoop+Sensor+Thinker+Actor esistente.)
3. **Organism Supervisor + Genoma**: confronta Genoma vs eventi ricevuti → identifica organi silenti (registrati ma non heart-beat) e organi sconosciuti (che battono ma non sono nel Genoma).

**Vincolo SYMBIOSIS Legge 7 (numeri prima)**: il Genoma deve essere misurabile (n organi totali, n innervati, n silenti negli ultimi 5min) tramite `:1819 /stats`.

**Vincolo NB-1 ADR-7 (registry HALT)**: il Genoma deve avere checksum signature simile a `job_registry.json`. Modifiche via PR review, non runtime mutation.

---

## 5. La parola "innervazione" — cosa significa concretamente

Tre azioni riusabili in catena:

1. **Heartbeat**: ogni organo emit ogni X minuti `organism:events {kind: "heartbeat", source: "organ_id"}`. Cell+Organism osservano. Se un organo nel Genoma non batte da >2X, alert.
2. **Event emission strutturata**: ogni organo, quando rileva un fatto rilevante (file processato, errore, deploy, webhook ricevuto), emit evento tipizzato — non `print()` o `logger.info`. Decoupled da Cell/Organism: anche se entrambi cadono, l'organo continua.
3. **Genoma entry**: ogni organo è registrato con metadati. Se non è nel Genoma, Organism non lo sorveglia. Se cade un organo non nel Genoma, c'è un bug nel processo (post_commit_hook deve detect → adopt_module actuator).

L'innervazione **non è una libreria nuova**. È:
- 1 helper per emit_event/heartbeat (`organism.emit` esiste già).
- 1 file Genoma da costruire.
- N modifiche puntuali (1-3 righe) ad ogni organo per aggiungere `heartbeat` periodica e `emit_event` sui fatti rilevanti.
- Deploy del Supervisor + control panel + scheduled_tick.

**Insight chiave da Codex** (vedi `04_codex_existing_signals.md`): **molti organi già emettono signal** (state files `~/.agent/decisions/state/*.last.json`, cron-agent-python `*.state.json`, cell_pulse_log SQL, events_outbox PG, ecc.). L'innervazione può procedere **per BRIDGE** anziché modifica diretta a 50 organi: un bridge daemon legge state files e re-emit verso `organism:events`. Costo per organo: **0 LOC modifiche** (bridge fa il lavoro).

---

## 6. Cosa NON è il task (esclusioni esplicite)

Per evitare scope creep durante FASE 3:

| NON è il task | Perché |
|---|---|
| Riscrivere Cell o Organism | Sono buoni. Bug = vista limitata + non deployato, non architettura. |
| Sostituire i 35 guardian esistenti | Per design spec §1 "L'organismo augmenta, non prerequisita". |
| Implementare Pilastri SYMBIOSIS 1-8 | Quelli sono già live (Riflessione, Accumulazione, Curiosità v1). Innervazione è prerequisito a Confronto/Sogno/Misura cross-organ. |
| Scrivere un nuovo orchestrator centrale | Legge 3: event-driven, no polling centrale. |
| Aggiungere dipendenze cloud/SaaS | Legge 6: sovranità locale. JSONL+Redis bastano. |
| Migrare bus a Redis Streams (era PG LISTEN/NOTIFY) | Cicatrix STRUCTURAL 2026-04-29 P0-2 fase 2 — già risolto via outbox pattern. Backend-rag interno mantiene PG NOTIFY+Outbox. Organism `organism:events` resta su Redis Stream (separato, scope diverso). |
| Installare Grafana/Prometheus locale o supervisord | NB-1: Zero ha già rejected. Solo Grafana Cloud + launchd nativo. |

---

## 7. Output del Track C3 (sintesi)

Al termine, gli output osservabili sono:
1. Genoma file autoritativo, con N organi registrati (numero misurato).
2. Supervisor LaunchAgent attivo su Pro (heartbeat in Redis fresh ogni minuto).
3. Control panel HTTP :1819 raggiungibile.
4. scheduled_tick cron ogni ora.
5. Almeno **Wave 1** organi (4: backend api, drive_poll Air, claude-max-watcher Pro, login-healthcheck) wired con heartbeat — verificati in JSONL `~/logs/organism/events.jsonl`.
6. Cell estesa con un sensor "genome_aggregator" che reporta "chi è vivo".
7. Admin dashboard locale (Pro-only, **NON sostituisce Grafana Cloud**) che mostra Genoma + last-seen per ogni organo.
8. Chaos test 5/5 base scenari verde su Pro reale.
9. Numeri before/after pubblicati in `11_innervation_complete.md`.

**Il sistema risultante**: quando da domani in poi cade un organo, l'evento è in JSONL entro 60s, Cell+Organism lo vedono, Organism propone restart o quarantena, Telegram alert va a Zero. Niente più "5 minuti dopo che un cron lo scopre".

---

## 8. Prossimo step

→ `01_innervation_matrix.md`: inventario esaustivo organi della flotta + colonne nervose. Numeri prima.

→ `02_dispatch_resilience_log.md` + dispatch a 4 LLM (Gemini/Codex/DeepSeek/NLM) con focus distinti.

→ FASE 2 design (07/08/09): pick proposta DeepSeek (B Tiered Resilience), isolamento failure, migration plan in onde.
