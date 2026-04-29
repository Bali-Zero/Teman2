# 06 — NotebookLM history: decisioni canoniche + cicatrici passate

**Data**: 2026-04-29 21:38-21:42 WITA
**Sorgenti**: NB-1 (`f6ecd115-...` "Nuzantara Codebase & Architecture") + NB-14 (`1e5f9b04-...` "Claude Code Session Memory")
**Trasporto**: 2 query separate via `nlm notebook query <id> "<question>"` (no batch cross-notebook nativo)

---

## 1. NB-1 — Decisioni architetturali canoniche (must NOT contradict)

### 1.1 Event Bus → PG LISTEN/NOTIFY + Outbox pattern (NON Redis Streams)

> "Nel file `apps/backend-rag/backend/services/events/event_bus.py`, l'architettura implementa esplicitamente un modello ibrido basato su PostgreSQL LISTEN/NOTIFY per il cross-process e pub/sub in-process per la latenza zero. Poiché `pg_notify` è volatile, l'architettura adotta l'Outbox Pattern implementato in `apps/backend-rag/backend/services/events/outbox.py` (migration 144)." [src: 5250c83e]

**Già coerente con stato attuale**: P0-2 fase 2 outbox è in cicatrici-scars come MITIGATED 2026-04-29 PR #357. Migration 146 ha refactored 6 trigger functions (`notify_practice_change`, `notify_client_change`, ecc.) per scrivere a `events_outbox` prima di `pg_notify`.

**Vincolo per innervation**: backend-rag interno usa **PG NOTIFY+Outbox**. **Organism `organism:events` resta su Redis Stream** — sono due bus paralleli per scope diversi:
- PG NOTIFY (backend internal): events business (CRM practice/client change, war room, intel, cognitive)
- Redis Stream `organism:events` (cross-flotta): heartbeat + recovery events

Non vanno fusi. NB-1 conferma la dualità.

### 1.2 ADR-2/3/7 Sentinel system

> "ADR-3 (No SQLite per shared state): I database SQLite locali sono esplicitamente banditi per lo storage condiviso cross-macchina a causa dei rischi di split-brain e corruzione binaria. Al loro posto si usano rigorosamente file JSONL separati (`shared/escalations_pro.jsonl` e `shared/escalations_air.jsonl`) uniti solo al momento della lettura." [src: a1ce1961]

**Implicazione per Genoma**: il design intent §4.2 (proposed `apps/organism/organism/genome.yaml`) è coerente — file YAML versionato in git, NON SQLite. Last-seen aggregato in JSONL+SQLite **locale** (per-machine, NOT shared) — coerente con ADR-3.

> "ADR-7 (Registry HALT): Una mancata corrispondenza della firma SHA256 sul file `job_registry.json` blocca l'intera esecuzione (HALT) e invia un alert CRITICAL su Telegram." [src: a1ce1961]

**Implicazione per Genoma**: il Genoma deve avere checksum/signature pattern simile a `job_registry.json`. Modifiche al Genoma vanno via PR review, non runtime mutation. Coerente con design intent §4.2 ("source-of-truth statico").

### 1.3 NIENTE PM2/Supervisor/Grafana locale (decisione cardinale Zero)

> "Nel file `INSTALL_CHECKLIST.md` sotto la sezione 'COSA NON INSTALLARE', due decisioni canoniche: (1) Niente PM2 o Supervisor — launchd è nativo su macOS ed è architetturalmente superiore. (2) Niente Grafana/Prometheus locale — le metriche Prometheus applicative vengono trasmesse a Grafana Cloud asincronamente via MetricsPusher." [src: 20a966e3 ?]

**Verifica chiave**: il "Supervisor" in NB-1 si riferisce a `supervisord` (Python tool ops di terze parti, non un python daemon nostro), non al Python daemon `apps/organism/organism/supervisor/daemon.py`. Conferma che la scelta canonica è:

- **launchd** (nativo macOS) per scheduling + restart policy daemon → **OK Organism Supervisor** lanciato come LaunchAgent
- **Grafana Cloud** (remoto, NON locale) per metriche aggregate → **OK admin-dashboard locale** è solo un read-only view per Pro, non sostituisce Grafana

**Vincolo per innervation FASE 3.4 (admin dashboard)**: il dashboard locale deve essere **read-only viewer**, NON scoreggia metriche/observability sopra Grafana. È un control plane per Pro Zero, non una piattaforma di osservabilità competitor.

### 1.4 Cell architecture (PulseLoop + Sensor + Thinker + Actor + Gate)

> "Una cellula viene istanziata tramite `apps/evaluator/seo_cell/cell.py` assemblando un PulseLoop (il battito cardiaco), un array di sensors per leggere dall'ambiente, un SEOThinker per ragionare e un SEOActor per eseguire Proposals. Prima che l'Organismo permetta l'apprendimento e l'azione, la cellula deve sbloccare il gate `pre_natal`." [src: c2a98b85 ?]

**Implicazione per innervation**: `apps/cell/cell/` segue lo stesso pattern di `apps/evaluator/seo_cell/`. **NON inventare una nuova architettura "cell-aggregator"** — estendere il pattern esistente con un nuovo sensor `genome_aggregator_sensor.py` che legge `organism:events` e produce stato "chi è vivo".

### 1.5 Heartbeat — pattern già esistenti

NB-1 elenca **3 heartbeat patterns già nel codice**:

1. `apps/evaluator/nlm_deep_research/heartbeat_monitor.py` (ARCH-9) — classifica stato in `OK/WARNING/CRITICAL/DEAD`. Per pipeline NLM specifically.
2. `apps/federation/launcher.py` `monitor_agents()` — ping HTTP ogni 30s, 3 fallimenti consecutivi → kill+restart agent.
3. `apps/backend-rag/backend/services/olympus/heartbeat.py` — DB metrics (connections, vacuum lag) periodicamente.

**Implicazione critica**: questi 3 heartbeat NON parlano tra loro né con `organism:events`. Sono silos con la stessa parola "heartbeat" ma scope differenti. **Mission innervation**: NON crearne un quarto silo — aggregare/bridge i 3 esistenti verso `organism:events`, ognuno mantiene il suo trasporto interno ma emit verso il bus comune.

---

## 2. NB-14 — Past Claude Code sessions (cicatrici da non ripetere)

### 2.1 Organism già "completed and merged" 2026-04-22 (13 PRs Wave 0-4)

> "The Nuzantara Autonomic Organism was completed and merged on 2026-04-22 across 13 PRs (Wave 0 to Wave 4). This architecture introduced a central event bus, heartbeat fallbacks, an emergency control panel, and a supervisor shadow mode. The final deployed organism features 9 actuators, 4 decision tiers (YAML, Ollama, Claude, and Consiglio), and a 6-layer safety rail." [src: 49ae6fa3]

**REVISIONE radicale del Design Intent §3.1**: avevo scritto "Organism W0+W1+W2+W3+W4 code complete a livello di codice ma NON deployato in produzione". NB-14 dice "completed and merged", quindi **TEORICAMENTE deployato** nel periodo 2026-04-22→04-25.

**Conflitto con stato osservato 2026-04-29**:
- Heartbeat key Redis EMPTY
- Supervisor LaunchAgent NON in `~/Library/LaunchAgents/`
- JSONL ultimo write 2026-04-25 (4gg fa)
- Stream `organism:events` 52 entry totali

**Ipotesi spiegazione**: Organism merged 2026-04-22 → deployato qualche giorno → spento manualmente o per cicatrix scar P0-3 plist mass corruption 2026-04-29 (51/54 plist truncated, possibile che organism plist sia stato tra i corrotti e mai ripristinato).

**Verifica next**: `git log --all --grep="organism" --since="2026-04-22"` per ricostruire timeline merge → deploy → degrado.

### 2.2 Cicatrice WR2: PG NOTIFY fire-and-forget → 5min reconciliation loop

> "A critical discovery revealed that Postgres NOTIFY is 'fire-and-forget,' meaning if the supervisor crashes or the Mac sleeps, status transitions are permanently lost. To fix this, a periodic 5-minute reconciliation loop was mandated to catch stalled drafts." [src: 08a57399]

**Implicazione per innervation**: già risolto via Outbox pattern (migration 144) — PR #342 fase 1 + #357 fase 2. Il principio "5min reconciliation" è fondamentale: anche dopo Outbox, il **Supervisor deve** ri-leggere lo stato persistente ogni N minuti per recuperare da crash/sleep. Questo è già nel Wave 1.A daemon.

### 2.3 Cell osserva solo `/health` per design

> "Cell currently observes only the backend-rag /health endpoint because the Prometheus Blackbox exporter is explicitly configured to probe HTTP health endpoints. Other organs, such as the Mata Garuda agents, operate as background LaunchAgents or CLI runners. Since these background organs do not expose dedicated HTTP web servers, standard HTTP-based observability tools cannot probe them directly." [src: c4126c89]

**Conferma chiave**: il "Cell vede solo 1 organo" NON è bug architetturale, è **una scelta storica imposta da Prometheus Blackbox**. Le LaunchAgent non hanno HTTP endpoint → NON possono essere probate via Blackbox.

**Soluzione innervation (coerente con NB-14)**: invertire il pattern. **Sono gli organi che pingano** (Legge 3 SYMBIOSIS event-driven, no central polling), non Cell che li probe. Cell consuma `organism:events` invece di probarlo. Coerente con "Pattern Sentinel" (`scripts/nuzantara-sentinel.py` osserva `~/.agent/decisions/state/` files writes).

### 2.4 Cicatrici "I tried X but Y happened" (must NOT repeat)

> 1. **Heartbeat & Fast Restarts (2026-04-07)**: `fly secrets set` triggered fast restart that silently failed to reboot background asyncio scheduler in `service_initializer.py`. Fix: heartbeat log every tick + mandate `fly deploy --strategy rolling`. [src: 5324be89]
> 2. **Sentry APM Exhaustion (2026-04-21)**: Enabled `traces_sample_rate>0` → burned 5K events/month free tier in <24h → all subsequent critical errors silently dropped → reverted to 0.0 prod. [src: c4126c89]
> 3. **Silent EventBus Invalidation (2026-04-18)**: Cache invalidation via EventBus failing because `handlers.py` imports non-existent `cache_service` module. `except Exception` swallowed ImportError → `logger.debug` only. [src: c4126c89]
> 4. **Health Check False Positives (2026-04-06)**: `fly.toml` health check returning HTTP 200 even when system unhealthy → no auto-restart. `system_doctor` `model=unknown` false alarm because API light process doesn't include embedding model in /health. [src: 5324be89]

**Implicazione per innervation FASE 2 design (07_innervation_protocol.md)**:

- **Lesson 1**: heartbeat **in ogni tick** (non solo on success). I miei organi devono emit heartbeat anche se la run è failed — solo così il "silenzio" è interpretabile.
- **Lesson 2**: **NO Sentry-style sampling**. JSONL + Redis sono full-fidelity. Sample-rate è una trappola sottile.
- **Lesson 3**: **NO `except Exception: pass`**. Ogni errore di emit deve essere `logger.warning` minimum, mai swallowed.
- **Lesson 4**: heartbeat **deve includere semantica oltre il codice HTTP**. Cell ha già fix questo (P0-0 cicatrix `pulse.py` classify `body.status` semantica). Genoma entry deve avere `health_check_method` e parsing del body.

---

## 3. Constraints da NON ritestare (settled by Zero)

| Constraint | Cita | Status |
|---|---|---|
| Niente Redis Streams come bus principale interno backend | NB-1 §1 | Settled (Outbox PG NOTIFY) |
| Niente PM2/supervisord ops tool, usa launchd | NB-1 §3 | Settled |
| Niente Grafana/Prometheus locale stack | NB-1 §3 | Settled (Grafana Cloud + MetricsPusher) |
| Niente SQLite per shared state cross-machine | NB-1 ADR-3 | Settled (JSONL split + merge-on-read) |
| Cell osserva solo `/health` perché Blackbox probe HTTP | NB-14 §2.3 | Settled — innervation lo INVERTE: organi push, non Cell pull |
| Sentry sample-rate > 0 in prod → burns quota | NB-14 §2.4.2 | Settled — JSONL full-fidelity sempre |
| `fly secrets set` non rebbota uvicorn asyncio scheduler | NB-14 §2.4.1 | Settled — usa `fly deploy --strategy rolling` |

---

## 4. Open questions only NLM caught (matrix/00 missed)

1. **Organism W0-W4 era stato deployato (NB-14 §2.1)** ma non lo è ora. Cosa è successo tra 2026-04-25 e 2026-04-29? Possibili: (a) plist truncation P0-3, (b) volontaria disattivazione, (c) crash silente. **Verifica obbligatoria PRIMA di ri-deployare**: leggere `git log --grep="organism" --since="2026-04-22"` + `JSONL ~/logs/organism/events.jsonl` per evidenze.

2. **3 heartbeat silos già esistenti** (`nlm_deep_research/heartbeat_monitor.py`, `federation/launcher.py monitor_agents`, `olympus/heartbeat.py`) — innervation deve **bridge questi 3 senza romperli**. Costo aggiuntivo per ognuno: ~10 LOC `await emit_event(kind="heartbeat", source="<silo>", payload={...})`.

3. **`com.cell.organism` plist failed launch storicamente** (CELL_DATABASE_URL → Fly tunnel 15432 manualmente). Implica che Cell oggi tunnel ssh Pro→Air→Fly. Se Air è offline, Cell perde DB. **Cell entry nel Genoma deve dichiarare dipendenza esplicita: `infra.fly_tunnel_15432`**.

4. **Federation `launcher.py monitor_agents`** ha già il pattern "ping HTTP every 30s, 3 fail → kill+restart". Questo è **già un Supervisor di nicchia** per agenti federation. Innervation deve decidere: (a) federation continua autonomo, emit-only verso bus per visibility; (b) Organism Supervisor reclama responsabilità anche federation. Default: **(a) emit-only**, evita conflict mutex/circuit-breaker tra due Supervisor.

5. **`apps/evaluator/seo_cell/`** è un'altra Cell esistente, non solo `apps/cell/`. La query NB-1 lo cita come riferimento Cell architecture. Implica almeno 2 Cell istanze nel sistema. **Inventory matrix § 2.7 sottostimato** — devo verificare se ci sono altre Cell-pattern instances (mata-garuda probabilmente).

---

## 5. Verdetto

**Output NLM è solido**: 5 ground truth confermate da NB-1 + 4 cicatrici prevenute da NB-14 + 5 open questions da risolvere in FASE 2. Coerenza con design intent 00: ALTA con un'eccezione (deploy storia 2026-04-22→25 da chiarire prima di ri-deploy).

**Costo dispatch**: 2 query a 180s timeout = ~3 minuti totali. Free tier OAuth (zero cost).

→ FASE 2 può procedere anche con 3/4 LLM (Gemini 429 + DeepSeek+Codex pending). Storia + signals + contract sono i 3 pilastri minimi; senza dependency graph Gemini, costruisco manualmente. NLM è il pilastro che NESSUN altro LLM avrebbe potuto dare (memoria conversazionale).
