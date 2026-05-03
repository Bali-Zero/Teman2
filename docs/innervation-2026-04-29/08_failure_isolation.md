# 08 — Failure isolation: scenari di guasto + recovery path

**Data**: 2026-04-29
**Stato**: FASE 2 design — blast radius analysis per ogni componente del sistema nervoso
**Riferimenti**: 07_innervation_protocol, autonomic-organism-design 2026-04-22 §4 Safety rail, NB-14 cicatrici passate

---

## 1. Principio guida (SYMBIOSIS Legge 4)

> Graceful degradation: se un organo non risponde, gli altri procedono. L'organismo è resiliente per design, non per eccezione.

**Estensione per innervation**: introdurre Cell + Organism + Genoma **NON DEVE creare un SPOF nuovo**. Ogni componente nervoso deve avere un fallback locale che lo sostituisce se cade.

---

## 2. Scenari di guasto (matrice esaustiva)

### 2.1 Quando cade un organo della flotta

**Pre-innervation** (oggi):
- Drive_poll_service Air cron disabilitato per cicatrix → nessuno notice per 4h fino a sentinel scan
- backend-rag api restart loop (P0-0 cicatrix) → notato solo via login probe esterno
- claude-max-watcher silent fail → nessuno notice mai (no monitoring)

**Post-innervation** (target):
- Heartbeat fresh ≤90s → alive (verde). Stale 90-180s → emit `organ_stale` event. Dead ≥180s → emit `organ_dead` event + Decider triggers `restart_agent` actuator.
- Latency from organ death → human Telegram alert: ≤5min (3min stale window + 2min Telegram dispatch).

**Failure mode acceptable**: un organo morto **per cui non c'è recovery_action automatica** (es. `human_only` enum). In questo caso: emit organ_dead → Telegram alert solo, no recovery dispatch. Zero decide manualmente.

### 2.2 Quando cade Cell

**Causa probabile**: `cell.organism.plist` killed (P0-3 plist truncation), o Cell crash interno (sensor exception non catched), o Postgres `cell_pulses` write failure cascading.

**Effetti**:
- ✅ Organi continuano a emit_event() verso `organism:events` (NON dipendono da Cell).
- ✅ Supervisor continua a leggere bus + dispatcher recovery (NON dipende da Cell).
- ⚠️ Aggregation "chi è vivo" stops aggiornare. Dashboard locale mostra stato stale (>60s).
- ⚠️ I ~12 organi che Cell **proba via /health HTTP** (backend-rag, infra locali) perdono visibility. Mitigazione: backend-rag emit_event diretto (Wave 1).

**Recovery automatico**:
- LaunchAgent `com.cell.organism` ha `KeepAlive=true` → launchd riavvia subito.
- Se restart loop (3+ exits in 60s): Sentinel/zombie_hunter notica via `~/.agent/decisions/state/launchd_bad_exits.json` → emit `zombie_detected` event → Organism Decider rule `zombie_detected_restart` → quarantine + Telegram.

**Tempo recovery target**: <10s (single restart). >60s indica problema strutturale → Telegram → Zero.

### 2.3 Quando cade Organism Supervisor

**Causa probabile**: Supervisor LaunchAgent killed, daemon Python crash, Redis client connection esaurita, OOM (improbabile con stateless design).

**Effetti**:
- ✅ Organi continuano emit_event verso bus (Redis + JSONL).
- ✅ JSONL `~/logs/organism/events.jsonl` cresce con eventi non-consumati.
- ✅ Cell continua il pulse + sensor genome_aggregator legge SQLite last_seen direttamente (non dipende da Supervisor for read).
- ⚠️ Recovery actuator dispatch FERMO. Stale/dead organs non vengono restartati automatically.
- ⚠️ Heartbeat key Redis `organism:supervisor:heartbeat` non si refresh. Guardian che chiamano `supervisor_heartbeat_check()` → `should_enter_emergency_mode=True` → fallback a comportamento autonomo pre-organism.

**Recovery automatico**:
- LaunchAgent `com.nuzantara.organism.supervisor` ha `KeepAlive=true` (FASE 3 — non oggi). Launchd riavvia subito.
- Supervisor è **stateless by design** (state in Redis IncidentContext + JSONL backup): restart safe.
- Su restart, consume group `organism-supervisor` riprende da last unprocessed event (Redis Stream + XREADGROUP guarantee).
- JSONL backup permette replay completo se Redis Stream è troncato (MAXLEN cap).

**Tempo recovery target**: <30s (launchd restart + supervisor reconnect to Redis + consumer group resume).

**Acceptable degradation during restart**: 30s di no-recovery-dispatch. Stale/dead organs aspettano il restart, poi stop-flow stale events vengono processati in batch.

### 2.4 Quando cade Redis (ORGANISM_REDIS_URL)

**Causa probabile**: `redis-server` crash (improbabile, è battle-tested), disk full, port conflict, manual `redis-cli FLUSHALL` (umano error).

**Effetti**:
- ✅ JSONL fallback in `~/logs/organism/events.jsonl` continua a ricevere eventi (Codex insight: organi scrivono local-first, Redis best-effort).
- ✅ Organi continuano emit_event con `redis emit failed, event persisted only to JSONL` log warning.
- ✅ Supervisor su reconnect riprende da consumer group (Redis ripristinato dal `dump.rdb` se persistence enabled).
- ⚠️ During Redis-down window: Cell aggregation degraded (no Redis HASH for last_seen — fallback to SQLite-only).
- ⚠️ Mutex lock per actuator concurrent execution non funziona → potential double-restart. Mitigazione: actuators sono idempotent by design.

**Recovery automatico**:
- Redis run as `homebrew.mxcl.redis.plist` (LaunchAgent system-managed). Brew autoload restart.
- Se Redis down >5min: Sentinel notica via `~/.agent/decisions/state/redis_health.json` (custom Sentinel rule, Wave 2). Emit `infra.redis_down` event. Telegram alert.

**Tempo recovery target**: <2min (brew restart + AOF replay if enabled).

**Critical mitigation**: la **terza linea di difesa** (file mtime touch in `~/.organism/heartbeats/`) garantisce che organi possano emit heartbeat anche con Redis E JSONL down (entrambi su disco). Questo è il "nuclear option" Law 4.

### 2.5 Quando cade Postgres (Fly nuzantara-postgres)

**Causa probabile**: Fly machine restart, planned maintenance, AOF corruption.

**Effetti**:
- ⚠️ backend-rag PG LISTEN/NOTIFY EventBus down → events_outbox accumula righe (good, durability).
- ⚠️ Cell `cell_pulses` write fails → logger.warning, pulse continues.
- ⚠️ Bridge sources di tipo `sql_table` (es. `cell_pulse_log`) non leggibili → bridge sensor reports `unknown` per organi affected.
- ✅ Organism Redis stream + JSONL **NON** dipendono da PG. Fully operational.

**Recovery automatico**:
- Fly auto-restart per PG machine (Fly orchestrator).
- Backend-rag PG pool reconnect via `expire_connections()` (esistente, vedi MEMORY 2026-03-22).

**Tempo recovery target**: <5min (Fly machine restart).

### 2.6 Quando cade JSONL disk (~/logs/organism/events.jsonl)

**Causa probabile**: disk full Pro, write permission revoked, FS corruption.

**Effetti**:
- ⚠️ emit_event locale fallisce → eccezione catched, logger.warning.
- ⚠️ Redis stream continua a ricevere events ma JSONL è la fonte di verità durable. Loss durante questo window.
- ✅ Cell + Supervisor continuano a operare (leggono Redis, non JSONL).

**Recovery automatico**:
- Disk full → cleanup_log actuator (esistente in Organism, non yet scheduled) può ruotare logs >30d.
- Permission → manual fix (rare).

**Tempo recovery target**: dipende. Disk cleanup automatico Wave 3 quando scheduled_tick attivo.

### 2.7 Quando cade Pro intera macchina

**Causa probabile**: power loss, hardware failure, manual reboot.

**Effetti**:
- 🔴 **Tutto Pro down**. Cell, Organism, 52 LaunchAgent, 46 home scripts, 30 cron-agent-python.
- ✅ Air continua per organi che ha (2 LaunchAgent + indexing-sweep).
- ✅ Fly continua (cloud, indipendente).
- ✅ Vercel continua (cloud, indipendente).

**Recovery**:
- Manual: power on Pro. LaunchAgent riavviano automaticamente al boot (RunAtLoad=true sui daemon critici).
- Cell + Organism Supervisor (KeepAlive=true) ripartono.
- Innervation events non emittati durante downtime sono persi per sempre per gli organi Pro-only. Air organi continuano emit (verso Redis-Pro è offline → fallback JSONL Air-side, sync on Pro recovery? no — Redis è su Pro, Air emit fallisce).

**Limite riconosciuto**: Sovranità locale Legge 6 dice "vive su Pro+Air offline" ma Redis è solo su Pro. **Open question per Wave 5+**: Redis replica Pro→Air (NB-14 federation pattern + design spec 2026-04-22 §2 "Redis Sentinel quorum=2"). Non in scope FASE 1-4 di questo Track.

---

## 3. SPOF analysis

### 3.1 SPOF presenti PRE-innervation (oggi)

| SPOF | Impatto | Mitigazione attuale |
|---|---|---|
| Pro `nuzantara` LaunchAgent | 132 organi giù se Pro down | None — accept residual risk |
| Fly `nuzantara-rag` api machine | Backend down → 7 channel + 8 subdomain frontend tutti broken | Fly auto-restart, P0-0 fix incoming |
| Postgres `nuzantara-postgres` | Backend EventBus + cell_pulses + KG + CRM tutti compromessi | Daily pg_dump → Tigris, auto-restore drill manuale |
| Telegram bot @Balizerobot | Tutti gli alert silent | None — accept residual risk |

### 3.2 SPOF introdotti da innervation? **Nessuno**, by design

| Componente nuovo | È SPOF? | Perché no |
|---|---|---|
| Genoma YAML | ❌ | Statico, versionato in git, replicato su Pro+Air automaticamente |
| Cell sensor genome_aggregator | ❌ | Cell death → organi continuano emit + Supervisor reads bus directly |
| Organism Supervisor (Wave 3 deploy) | ❌ | Supervisor death → guardians fallback to local_emergency_mode (esistente) |
| SQLite ~/.organism/last_seen.db | ❌ | Per-machine, ricostruibile dal JSONL replay |
| Bridge sensor (state file reader) | ❌ | Read-only, cell-internal, Cell death lo include |
| Control panel HTTP :1819 | ❌ | Operator console only, niente lo legge in critical path |

**Verdetto**: l'innervation **migliora la resilienza** della flotta complessiva, **senza** introdurre nuovi SPOFs. La `~/.organism/heartbeats/{source}.touch` file mtime fallback è il "nuclear safety" — anche con Redis E JSONL E Cell E Supervisor tutti down, organi continuano a touchare file.

---

## 4. Test scenarios per FASE 4 chaos test (mapping)

I 5 test concordati con Zero (Q3-A) corrispondono a:

| # | Action | Scenario sezione 2 | Expected detection | Expected recovery |
|---|---|---|---|---|
| 1 | Stop drive_poll cron Air | §2.1 organ death (Air cron) | Cell sensor genome_aggregator notice in 5min (300s expected_hb) | Wave 1 supervised: emit `organ_stale` event, no auto-restart yet (cron disabled by cicatrix) |
| 2 | Kill claude-max-usage-watcher Pro | §2.1 organ death (Pro LaunchAgent) | Cell sensor notice in 60min (3600s expected_hb) — slow! | Decider rule fires `restart_agent` → `launchctl kickstart com.nuzantara.claude-max-usage-watcher` |
| 3 | Kill Cell process | §2.2 Cell down | Sentinel/zombie_hunter notice in 60s | LaunchAgent restart Cell, organi continuano |
| 4 | Kill Organism Supervisor | §2.3 Supervisor down | Heartbeat key Redis stale → `supervisor_heartbeat_check()` returns alive=False | Guardian local_emergency_mode + LaunchAgent restart Supervisor |
| 5 | Kill nuzantara-rag api machine via fly machines stop | §2.5 Fly machine down (extension: §2.1 backend.api organ) | Cell sensor http_health probe sees timeout, classify RED. Login probe also fires alert. | Fly auto-restart machine (existing) + Decider rule `restart_agent backend.api` (placebo if Fly handles it first) |

**Abort criteria** (concordato Q3-A): se test 3 (Cell) fallisce a essere rilevato in 90s → STOP, non procedere a 4 e 5.

---

## 5. Output FASE 2

→ Fault tolerance verified. Nessun SPOF nuovo. Recovery time targets: 10s Cell, 30s Supervisor, 2min Redis, 5min PG, manual Pro hardware.

→ `09_migration_plan.md`: ondata-by-ondata implementation order con sequenziamento Q2-B + chaos test alignment.
