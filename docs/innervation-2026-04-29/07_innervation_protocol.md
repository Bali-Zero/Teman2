# 07 — Innervation protocol: il contratto nervoso definitivo

**Data**: 2026-04-29
**Stato**: FASE 2 design — decisione approvata (proposta DeepSeek B con semplificazioni Codex)
**Riferimenti**: 03/04/05/06 da FASE 1, autonomic-organism-design 2026-04-22, NB-1 architecture decisions

---

## 1. Decisione finale

Tra le 3 proposte DeepSeek (`05_deepseek_minimum_contract.md`):

- ❌ Proposta C (Zero-Config Mesh, build-time decorator): **scartata**. Build-time scanning del genoma viola NB-1 ADR-7 (registry SHA256 firmato). Decorator decentralizzato è elegant ma fragile cross-platform Pro/Air/Fly/Vercel.
- 🟡 Proposta A (Minimal Heartbeat Bus): **base**. Simplicity vince per innervation di emergenza, ma graceful degradation Law 4 solo "Partial" (se Redis E JSONL down).
- 🟢 **Proposta B (Tiered Resilience Bus)**: **scelta**, ma **semplificata**.

### 1.1 Scelta = B − relay daemon + Codex bridge approach

DeepSeek raccomanda B con triple fallback: Redis → Unix socket relay daemon → JSONL → file mtime touch. **Rifiuto il relay daemon** per 2 motivi:

1. **NB-1 § "Niente PM2/Supervisor"**: Zero ha già rejected daemon ops aggiuntivi. Il relay sarebbe un nuovo daemon per macchina, ops overhead.
2. **Codex insight (`04_codex_existing_signals.md`) § "bridges, not edits to 50 jobs"**: gli organi **già scrivono state files** in `~/.agent/decisions/state/` e `~/.cron-agent-python/*.state.json`. Un **bridge consumer** (parte di Cell, NON un nuovo daemon) può leggere questi state files e ri-emit verso `organism:events`. Stesso effetto del relay daemon, MA come componente di Cell esistente.

**Architettura finale**:

```
Heartbeat path:
  Organ ──[1]──> Redis stream organism:events
              \──[2 fallback]──> JSONL ~/logs/organism/events.jsonl
              \──[3 emergency]──> ~/.organism/heartbeats/{source}.touch (mtime)

Bridge path (for organs that already write state files, no code change):
  Organ ──> ~/.agent/decisions/state/<job>.last.json (existing)
        ──> Cell sensor.bridge_state_files reads ──> emit_event()
        ──> organism:events
```

### 1.2 Heartbeat schema

**Frequency**: 60s (non 30s come DeepSeek B). 30s sarebbe ~5 events/s per 149 organi, eccessivo. 60s = ~2.5 events/s, manageable.

**Payload**:
```python
await emit_event(
    severity="info",
    source="<organ_id>",        # FQ id da Genoma
    kind="heartbeat",            # canonical kind
    payload={
        "uptime_s": <int>,       # seconds since organ started
        "last_action": <str>,    # most recent meaningful action OR "idle"
        "metrics": {<dict>},     # optional: organ-specific KPIs
    },
    correlation_id=<uuid>,       # auto-generated
    is_actuation=False,          # heartbeat is observation, not action
)
```

**Reuses existing `Event` Pydantic schema** (`apps/organism/organism/schemas.py`). NO nuovo envelope.

### 1.3 Detection thresholds

| Window | Stato organo |
|---|---|
| `last_seen < 90s` (1.5x interval) | **alive** (verde) |
| `90s ≤ last_seen < 180s` (3x interval) | **stale** (giallo) — emit `organism:events {kind: organ_stale}` |
| `last_seen ≥ 180s` (3x interval) | **dead** (rosso) — emit `organism:events {kind: organ_dead}` + dispatch recovery |

**Per-organ override**: il Genoma può specificare `expected_hb_seconds` custom (es. cron hourly = 3600s, frontend client beacon = 30min). Threshold = `2x expected_hb_seconds` per stale, `3x` per dead.

---

## 2. Genoma schema autoritativo

### 2.1 Locazione e formato

- **File**: `apps/organism/organism/genome.yaml` (single file, versionato in git)
- **Coesistenza**: complementare a `redundancies.yaml` (NON sostituisce). Genoma = registry "chi esiste"; redundancies = "chi è duplicato e come consolidare".
- **Persistenza**: YAML perché umano-leggibile + supporta commenti + multi-line. NO JSON (no commenti). NO SQLite (NB-1 ADR-3 ban shared SQLite).

### 2.2 Genome entry schema (definitivo)

```yaml
# apps/organism/organism/genome.yaml
version: 1                       # schema version, incrementare on breaking changes
checksum_algo: sha256            # ADR-7 signature method
checksum: "<sha256 of canonical entries>"  # rebuilt by tooling, HALT on mismatch

organs:
  - id: backend.api               # FQ ID, format: <runtime>.<domain>.<name>
    runtime: fly_machine          # enum: pro_launchd, air_launchd, air_cron, fly_machine, vercel_function, github_actions, mcp_session, backend_internal
    type: webhook                 # enum: daemon, cron, webhook, agent, channel, evaluator
    expected_hb_seconds: 60       # 0 = no heartbeat required (use event emission instead)
    owner_module: apps/backend-rag/backend/app/main.py  # path repo (or external if homedir script)
    dependencies:                 # list of organ IDs this depends on
      - infra.postgres
      - infra.redis
      - infra.qdrant
    recovery_action: fly_machines_start
    recovery_params:
      app: nuzantara-rag
      process_group: api
    severity_on_silence: critical # enum: info, warning, error, critical
    cicatrix_refs:                # related cicatrices in .claude/rules/cicatrix-scars.md
      - 2026-04-29-startup-failed-mask
      - 2026-04-29-drive-poll-attribute-error
    bridge_source:                # OPTIONAL: existing signal file Cell bridge can read instead
      type: state_file            # state_file | sql_table | redis_stream | logger
      path: ~/.agent/decisions/state/backend_api.last.json
      timestamp_field: ts
      status_field: status

  # ... 148 more organs
```

### 2.3 Genoma lifecycle

- **Modifications**: only via PR review. **NEVER** runtime mutation. Adopt-module actuator can PROPOSE additions via PR (auto-PR L2 path), but apply requires human merge.
- **Validation**: pre-commit hook runs `python -m organism.tools.validate_genome` — checks: unique IDs, valid runtime/type/recovery_action enums, all dependencies are valid IDs, checksum matches.
- **Deploy**: copying `genome.yaml` is part of normal git deploy. No special pipeline.
- **Local cache**: Cell + Supervisor load Genoma at startup, hash-check, in-memory map. Re-load only on SIGHUP (manual re-config). No auto-reload (NB-1 ADR-7 HALT philosophy).

### 2.4 Bridge sources (Codex insight)

Per la maggior parte degli organi esistenti, NON serve modifica del codice. Il Genoma dichiara `bridge_source` con:
- **state_file**: filesystem JSON file with timestamp+status (Pattern A from Codex)
- **sql_table**: PG table with last-row timestamp (Pattern B: events_outbox, cell_pulse_log)
- **redis_stream**: existing stream beyond organism:events (Pattern C: cron:reports, llm:metrics)
- **logger**: requires bridge to parse logs (Pattern D — last resort, fragile)

Cell new sensor `genome_bridge_sensor.py` reads bridge_source per organ + computes virtual heartbeat → emit_event verso `organism:events`. **Result: 0 LOC modifications to bridged organs**.

---

## 3. Cell aggregation (no new SPOF)

### 3.1 New sensor: `cell.sensors.genome_aggregator_sensor`

```python
# apps/cell/cell/sensors/genome_aggregator_sensor.py (NUOVO)
class GenomeAggregatorSensor:
    """Reads organism:events stream + Genoma + bridge sources.
    Produces SensorReading with aggregate state of all 149 organs."""

    async def read(self) -> SensorReading:
        genome = self._load_genome()  # cached, refreshed on SIGHUP
        last_seen = await self._read_last_seen()  # SQLite ~/.organism/last_seen.db (per-machine)
        bridge_states = await self._read_bridge_sources()  # state files / SQL / Redis
        merged = self._merge(genome, last_seen, bridge_states)

        return SensorReading(
            status=self._classify(merged),  # green if all alive, yellow if any stale, red if any dead
            metadata={
                "total_organs": len(genome.organs),
                "alive": len([o for o in merged if o.state == "alive"]),
                "stale": len([o for o in merged if o.state == "stale"]),
                "dead": len([o for o in merged if o.state == "dead"]),
                "dead_organs": [o.id for o in merged if o.state == "dead"],
            },
        )
```

### 3.2 Failure isolation (Cell death scenarios)

| Scenario | Risultato |
|---|---|
| Cell process dies | Organi continuano heartbeating verso Redis+JSONL. Cell aggregation stops. **Supervisor reads bus directly** — no cascade. Nuzantara-sentinel notica Cell silent → restart via `launchctl kickstart`. |
| Cell sensor genome_aggregator throws exception | Pulse continues con altri 11 sensor. Sensor returns `status=yellow` con metadata `{"error": "..."}`. Reasoner lo vede in metadata. |
| Cell DB (Postgres `cell_pulses`) down | Cell pulse fails to log (graceful, logger.warning), but emit_event ancora funziona. Recovery: PG restart o tunnel SSH Pro→Air→Fly fix. |
| Bridge source state file deleted | Sensor reports organ as `dead` (correct behavior). Bridge sensor logs warning. |

### 3.3 Read API: "chi è vivo?" in <100ms

Il sensor pulse target è 60s, but read API dev essere <100ms per dashboard. Implementation:
- Cell mantiene **in-memory cache** del merge result, refreshed every pulse cycle (60s).
- Backend-rag endpoint `/api/cell/innervation` legge SQLite `~/.organism/last_seen.db` (Cell exposes via local tunnel) + Genoma → merged JSON in <50ms.
- Dashboard locale (FASE 3.4) consuma quell'endpoint.

---

## 4. Organism observation (no central polling)

### 4.1 Supervisor reads bus, NOT Genoma

Il Supervisor daemon (`apps/organism/organism/supervisor/daemon.py`) **continua il pattern attuale**: consume `organism:events` via XREADGROUP. **Genoma è consultato lazy**: solo quando un evento arriva, lookup `event.source` in Genoma.

Workflow:
1. Event `kind=heartbeat source=backend.api` arriva.
2. Supervisor lookup `genome.organs["backend.api"]` → trova entry.
3. Supervisor aggiorna SQLite `~/.organism/last_seen.db` con `source → ts`.
4. Supervisor **NON polla Genoma periodicamente**. Stale detection è fatta da Cell (sensor genome_aggregator) o da background task low-frequency.

### 4.2 Background task: stale detector (1 task in Supervisor)

Ogni 30s (background asyncio task in Supervisor):
- Read SQLite `~/.organism/last_seen.db`.
- Compute diff `expected (Genoma) - observed (last_seen)`.
- For each stale organ: emit `organism:events {kind: organ_stale, source: "<silent>"}` + dispatch recovery action via Decider (L0 YAML rules).

Questo è **event-driven** Law 3: la stale detection produce eventi che fanno partire il recovery dispatcher esistente. Non è polling: è un timer interno al Supervisor che genera eventi sintetici.

### 4.3 New YAML rules (additions to `apps/organism/organism/rules/base.yaml`)

```yaml
- id: organ_stale_alert
  match: {kind: organ_stale, severity: [warning]}
  action: {actuator: notify_telegram, params: {message: "Organ {payload.source} stale {payload.lag_seconds}s"}}
  confidence: 0.85

- id: organ_dead_recovery
  match: {kind: organ_dead, severity: [error, critical]}
  action: {actuator: restart_agent, params: {agent_ref: "{payload.source}"}}
  confidence: 0.90
```

**Hook con `restart_agent` actuator esistente**: actuator legge `genome.recovery_action` per organo source → esegue (`launchctl kickstart`, `fly machines start`, ecc.). Dry-run mandatory (esistente). Idempotent (esistente).

---

## 5. Existing emit_event() callers — preservazione

I 4 caller esistenti (`post_commit_hook`, `scheduled_tick`, `system_doctor`, `zombie_hunter`) **NON vengono modificati**. Continuano a emit eventi di tipo `new_module`, `scheduled_tick`, `cron_agent_failure`, `zombie_detected` come prima. Il nuovo lavoro è:

1. **Aggiungere heartbeat** (kind="heartbeat") parallelo agli eventi business esistenti per gli stessi 4 caller (1-2 LOC ciascuno).
2. **Bridge sources** per i ~140+ organi NON-emit_event() (0 LOC each, lavoro di Cell sensor).
3. **Genoma entries** per tutti i 149 organi (lavoro di file YAML).

---

## 6. Costo per organo (recap)

| Categoria organo | Cost LOC | Esempio |
|---|---:|---|
| Existing emit_event callers | 1-2 | system_doctor.py adds `await emit_event(kind="heartbeat", source="pro.system_doctor")` at end of cycle |
| Bridge-able (state file / SQL / Redis stream) | 0 | drive_poll_service writes state file naturally → bridge reads |
| Frontend (Vercel client beacon) | 5-10 | New API endpoint + JS beacon on page load |
| MCP servers (session-bound) | 3-5 | On-startup emit + on-shutdown emit (no continuous heartbeat — they're sporadic) |
| Organi totalmente nuovi (rare) | 5-10 | New cron emits heartbeat + business event |

**Totale stimato 149 organi**:
- ~10 organs need 1-2 LOC = ~15 LOC
- ~120 organs bridge-able = 0 LOC
- ~8 frontend organs = ~50 LOC (1 helper + 8 invocations)
- ~3 MCP servers = ~10 LOC
- ~8 nuovi/edge cases = ~50 LOC

**Sum: ~125 LOC modifications across 149 organs** + ~200 LOC new code (bridge sensor, stale detector, dashboard endpoint). **Total ~325 LOC**.

DeepSeek B-original stimava 5-10 LOC × 149 = ~1500 LOC. **78% riduzione effort** grazie a Codex bridge insight.

---

## 7. Output FASE 2

→ Protocol decided. Heartbeat 60s, transport Redis→JSONL fallback, Genoma YAML at `apps/organism/organism/genome.yaml`, bridge sources for existing state-file emitters, no relay daemon.

→ `08_failure_isolation.md`: scenario-by-scenario blast radius + recovery path.

→ `09_migration_plan.md`: ordine onde 1-4 con sequenziamento Q2-B (parallel solo file/repo, serial Air/Fly/Vercel).
