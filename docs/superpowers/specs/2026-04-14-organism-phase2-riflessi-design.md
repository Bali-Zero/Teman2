# Organismo Nuzantara — Fase 2 (RIFLESSI) — Design

> **Status:** Brainstorm completato 2026-04-14, in attesa di review utente prima del piano implementativo.
> **Filosofia:** SYMBIOSIS.md (8 leggi inviolabili). **Checklist:** VADEMECUM.md.
> **Obiettivo Fase 2:** L'organismo connesso impara a reagire. Ogni esperienza diventa skill, ogni evento CRM cambia priorità, ogni notte il sistema dorme e consolida.

---

## 0. Sommario in lingua semplice

Fase 1 (Sinapsi) ha collegato Pro↔Fly via bridge bidirezionale e ha messo i 552 gap del Knowledge Graph nella coda di un consumer che dispatcha agenti. Funziona: 26 commit, 794 test backend, bridge LIVE in produzione (commit `5f1c9b460`).

Ma l'organismo non sta ancora imparando dalle proprie esecuzioni in produzione. L'audit del 2026-04-14 ha rivelato che lo Sprint 5 di Mata Garuda (reflection engine + KB unificata) era codice implementato ma INERTE — registry vuoto perché `mata_garuda.agents` non veniva mai importato dal `cell.runner`, e KB SQLite crashava sotto threading. Tre fix strutturali (commit `1520ce004`) hanno attivato il loop: il primo manual pulse ha prodotto la prima reflection, skill, insight reali in KB.

La Fase 2 costruisce sopra a queste fondamenta finalmente vive:

- **Priority Engine** — eventi CRM bumpano i topic degli harvester
- **LPSE Harvester** — chiude l'ultimo dei 8 gap types (procurement)
- **Sleep consolidation** — ogni notte il sistema dorme e promuove skill validate dalla riflessione
- **RAG Enricher** — query a bassa confidence diventano nuove entry KB Qdrant (con approval gate)
- **Sentinel health cell** — secondo cell-core dedicato al monitoraggio dell'organismo stesso

L'asse portante: il sistema reagisce agli eventi (CRM, gap, low-confidence, anomalie health) e impara dai propri cicli (reflection → consolidamento notturno → skill in Genome).

---

## 1. Stato attuale dell'organismo (post Fase 1)

### Cosa funziona

| Organo                       | Stato            | Evidenza                                                                          |
| ---------------------------- | ---------------- | --------------------------------------------------------------------------------- |
| Bridge bidirezionale Pro↔Fly | ✅ LIVE          | LaunchAgent `com.matagaruda.bridge.adaptive` attivo, ack rate sano                |
| Backend bridge router        | ✅ LIVE          | `/api/bridge/{events,ingest/article,ingest/enrichment}` in prod su nuzantara-rag  |
| EventBus → outbox            | ✅ LIVE          | 6 event types CRM/compliance scrivono in `bridge_outbox` PG                       |
| Gap consumer                 | ✅ ATTIVO        | `gap-consumer:consumer-1` legge `nexus:gaps`, dispatcha agenti                    |
| LHKPN harvester              | ✅ DEPLOYED      | Chiude 4 gap types (missing_nip, missing_lhkpn, missing_angkatan, stale_official) |
| Envelope standard 5-campi    | ✅ ADOPTED       | Tutti gli stream nuovi                                                            |
| Reflection loop MG           | ✅ ATTIVATO oggi | Manual pulse 14:53 ha prodotto insight+skill+reflection                           |
| KnowledgeBase SQLite + FTS5  | ✅ FUNZIONANTE   | 338 entries totali, threading-safe (fix di oggi)                                  |

### Baseline metrics 2026-04-14

| Metrica                    | Valore                                     |
| -------------------------- | ------------------------------------------ |
| Redis `garuda:raw`         | 351 entries                                |
| Redis `garuda:enriched`    | 106 entries                                |
| Redis `nexus:gaps`         | 621 entries (consumer lag=551, da drenare) |
| Redis `bridge:outbound`    | 1 entry (lag=0)                            |
| Redis `bridge:inbound`     | 0 entries (mai eventi reali)               |
| KB SQLite `reflection`     | 1                                          |
| KB SQLite `skill`          | 1                                          |
| KB SQLite `insight`        | 1                                          |
| KB SQLite `harvested_item` | 101                                        |
| Genome cell-core skills    | 7                                          |
| Test backend               | 794 pass                                   |
| Test mata-garuda           | 280 pass                                   |

### Cosa manca

1. **Gap.missing_procurement** — l'unico tipo non coperto dagli harvester esistenti
2. **CRM → Intelligence priority** — bridge:inbound non ha consumer, nessuno reagisce agli eventi CRM
3. **Sleep consolidation** — reflection accumulano ma non vengono mai promosse a skill validate cross-agent
4. **RAG low_confidence eventi** — il code path emit esiste ma `db_pool` non è mai wired su `ReasoningEngine`
5. **Health monitoring agentico** — Core Guardian V3 esiste ma non impara dalle azioni di recovery
6. **Integration test** — il ciclo end-to-end reflect→store→inject non è coperto da test

---

## 2. Pre-work — Task 0 (sblocca il resto)

Prima di costruire i 5 nuovi deliverable, si chiudono 4 task pre-requisito:

| #      | Task                                                                  | Files                                                                                                           | Test                               |
| ------ | --------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ---------------------------------- |
| 0.1 ✅ | Fix registry import + SQLite threading                                | DONE: `cell/runner.py`, `cell/actor.py`, `workers/gap_consumer.py`, `runtime/knowledge.py` (commit `1520ce004`) | 280/280 pass                       |
| 0.2    | Wire `db_pool` su `ReasoningEngine` (Phase 1 Task 17)                 | `apps/backend-rag/backend/services/rag/agentic/reasoning.py` + `app_factory.py`                                 | `test_low_confidence_emit_real.py` |
| 0.3    | Integration test reflect→store→inject (Sprint 5 Task 6)               | `apps/mata-garuda/tests/test_organism_integration.py`                                                           | end-to-end pulse + KB assertion    |
| 0.4    | Aggiorna SYMBIOSIS.md sezione "DOVE SIAMO" — Pilastro 1+2 → Operativo | `SYMBIOSIS.md`                                                                                                  | manual review                      |

Stima: 4 task, 1-2 ore di lavoro complessive, sblocca tutto downstream.

---

## 3. Deliverable 1 — Priority Engine

### Scelta architetturale (Q4)

**JSON flat snapshot + JSONL audit append-only** (consultazione NLM + Codex + Gemini, NLM rivela pattern Voyager/AgentSpawn/CtxVault: file flat = diffable/versionable/debuggable; SQLite o stream confondono "configurazione calda" con "conoscenza accumulata" e degradano l'agente).

### Componenti

```
~/.agent/decisions/
├── topic_priorities.json          # snapshot atomico (1 writer, N reader)
└── topic_priority_bumps.jsonl     # append-only audit (rotation >5000 righe o >90gg)
```

### Schema `topic_priorities.json`

```json
{
  "version": 1,
  "updated_at": "2026-04-14T15:30:00+08:00",
  "topics": {
    "tax": {
      "priority": 2.3,
      "last_bump_at": "2026-04-14T15:30:00+08:00",
      "decay_half_life_days": 30
    },
    "immigration": {
      "priority": 1.5,
      "last_bump_at": "2026-04-13T08:15:00+08:00",
      "decay_half_life_days": 30
    }
  }
}
```

Decay calcolato lazy al retrieval:

```python
current_priority = stored_priority * 2 ** (-days_since_bump / half_life_days)
```

### Schema `topic_priority_bumps.jsonl`

```json
{
  "ts": "2026-04-14T15:30:00+08:00",
  "event": "crm.client_created",
  "client_id": "...",
  "sector": "PMA-Tax",
  "topic": "tax",
  "delta": +1.0,
  "new_priority": 2.3
}
```

### Mapping eventi → topic bump

| Evento CRM                                | Topic bumped   | Delta       |
| ----------------------------------------- | -------------- | ----------- |
| `crm.client_created` con sector=PMA-Tax   | tax            | +1.0        |
| `crm.client_created` con sector=PMA-Other | property       | +0.5        |
| `crm.practice_completed` type=VISA-E33    | immigration    | +0.8        |
| `crm.practice_completed` type=VISA-B211   | immigration    | +0.5        |
| `crm.client_sector_changed`               | both old + new | -0.3 / +1.0 |

### Componente

`apps/mata-garuda/mata_garuda/workers/priority_engine.py`

- Consumer Redis stream `bridge:inbound` via consumer group `priority-engine`
- Filter `type` prefix `crm.*`
- Per ogni evento: lookup mapping → bump → write JSON atomico (write+rename) → append JSONL
- Schedule: cron 5 minuti (LaunchAgent `com.matagaruda.priority-engine`)
- Rotation JSONL: se >5000 righe o >90gg, archivia in `~/.agent/decisions/archive/topic_priority_bumps_YYYYMM.jsonl`

### Harvester reading

Ogni harvester (regulation_watcher, lhkpn, lpse, arxiv, github, youtube) carica `topic_priorities.json` al boot del pulse, applica il fattore al ranking dei propri job. Esempio Regulation Watcher: keyword "pajak"/"PMK"/"PPh" pesate × `priorities['tax']` corrente.

### Graceful degradation

- File non esiste → harvester usa default uniforme (tutte priorità = 1.0)
- File malformato → log warning, default
- JSONL non scrivibile → log warning, JSON snapshot continua a funzionare

### Metriche

- Counter eventi processati
- Counter bump per topic
- Età max di un topic senza bump (deve restare <30gg per topic attivi)

### Test

- `test_priority_engine.py`: bump unico, decay temporale, rotation JSONL, atomic write, consumer group ack
- `test_priority_integration.py`: evento CRM nel stream → bump → harvester legge nuova priorità

---

## 4. Deliverable 2 — LPSE Harvester

### Scelta architetturale (Q5)

**INAproc + 5 LPSE chiave via SPSE 4.5 JSON endpoint** (consultazione NLM + Codex + Gemini; Gemini rivela dato tecnico chiave: SPSE 4.5 è la piattaforma standard LKPP che sta sotto la maggior parte dei LPSE regionali, espone endpoint JSON `/dt/tender` — niente parser HTML per-portale).

### Strategia

```
Pulse → check INAproc /dt/tender (primary)
     → if empty/error: per ogni LPSE high-priority {Bali, Jakarta, Kemenkumham, Kemenkeu, BKPM}:
         scrape SPSE 4.5 /dt/tender JSON
         break alla prima risposta valida
     → publish a garuda:raw type=harvest.lpse
```

### Files

| File                                                           | Responsabilità                                                 |
| -------------------------------------------------------------- | -------------------------------------------------------------- |
| `apps/mata-garuda/mata_garuda/agents/lpse_harvester.py`        | Agent registrato (factory function)                            |
| `apps/mata-garuda/mata_garuda/agents/lpse_harvester_GENOME.md` | Constraints (rate limit, UA rotation, fallback chain)          |
| `apps/mata-garuda/mata_garuda/tools/lpse_tools.py`             | `scrape_spse_tender(url)`, `parse_spse_json(payload)`, helpers |

### GAP_DISPATCH update

```python
# apps/mata-garuda/mata_garuda/workers/gap_consumer.py
GAP_DISPATCH["gap.missing_procurement"] = "lpse_harvester"  # era None
```

### Output `garuda:raw` payload

```json
{
  "type": "harvest.lpse",
  "tender_id": "...",
  "tender_name": "...",
  "agency": "Pemprov Bali",
  "category": "Konstruksi",
  "value_idr": 5000000000,
  "deadline": "2026-05-01",
  "sector_tags": ["construction", "infrastructure"],
  "source_url": "https://lpse.baliprov.go.id/eproc4/lelang/...",
  "scraped_at": "2026-04-14T..."
}
```

### Constraints (GENOME.md)

- Rate limit: max 5 req/min per dominio
- User-Agent rotation: 3 varianti
- Cookie session se WAF richiede (Gemini Q5 risk)
- Fallback chain: INAproc → 5 regional in ordine di Priority Engine
- Escalation: 3 fallimenti consecutivi su tutto il fallback chain → meta-agent review

### Test

- `test_lpse_tools.py`: parser JSON SPSE 4.5, mock fixture, error handling
- `test_lpse_harvester.py`: case_resolved con tender publish, case_not_resolved se all fallback fail
- `test_gap_consumer_lpse.py`: gap.missing_procurement → lpse_harvester dispatched

### Out of scope per ora (Fase 4 future)

- Voyager skill library dinamica (parser auto-generati per portale)
- MAR multi-agent reflexion per debug parsing failure

---

## 5. Deliverable 3 — Sleep-time consolidation

### Scelta architetturale (Q3)

**Hybrid 2-pass** (pass 1 per-agent compression + pass 2 meta-claude per cross-agent + contraddizioni). Combina isolation di B (errore in un agente non inquina altri) con cross-agent insight di A (correlazioni profonde).

### Cron

LaunchAgent `com.matagaruda.dream.nightly`, finestra 01:00-05:00 WITA, esecuzione singola alle 01:00.

### Script

`apps/mata-garuda/scripts/dream_consolidation.py`

### Pass 1 — Per-agent compression

Per ogni agente con reflection ultimi 7gg:

```python
prompt = f"""
Sei il sistema di consolidamento per agente {agent_name}.
Reflection ultimi 7 giorni (n={count}):
{json.dumps(reflections, indent=2)}

Skill esistenti per questo agente nel Genome (confidence>0.7):
{json.dumps(existing_skills, indent=2)}

Estrai skill consolidate. Output JSON STRICT (validato con pydantic):
{{
  "consolidated_skills": [
    {{
      "skill_id": "string snake_case",
      "procedure": "step-by-step procedure",
      "precondition": "when this skill applies",
      "success_criterion": "how to verify it worked",
      "category": "scraping|reasoning|recovery|publishing",
      "derived_from": ["reflection_id1", "reflection_id2"]
    }}
  ],
  "prunable_entries": ["reflection_id_too_noisy"]
}}
"""
result = subprocess.run(["claude", "--print", prompt], ...)
candidates = pydantic_validate(result.stdout, AgentConsolidationOutput)
```

### Pass 2 — Meta-claude su candidates (NON entries raw)

```python
prompt = f"""
Sei il consolidatore meta-cognitivo dell'organismo Nuzantara.
Skill candidate proposte stanotte da N agenti:
{json.dumps(all_candidates, indent=2)}

Genoma globale attuale (confidence>0.7, scope=Project):
{json.dumps(global_genome, indent=2)}

Trova:
1. contraddizioni: skill candidate che contraddicono genoma esistente (stessa precondition, procedure diverse)
2. duplicati: skill candidate equivalenti tra agenti diversi (consolidare in 1 con scope='Project')
3. cross_agent_patterns: skill di un agente che dovrebbero essere applicabili anche ad altri

Output JSON STRICT:
{{
  "approved_skills": [...],         # promuovere a Genome con confidence=0.3
  "contradictions": [...],          # log + TG, NON inserire
  "cross_agent_promotions": [...],  # skill da promuovere con scope=Project
  "summary": "1 frase"
}}
"""
```

### Apply with safety

- `approved_skills` → `genome.record_skill()` con `confidence=0.3`, `scope='Project'`
- `cross_agent_promotions` → `genome.record_skill()` con `confidence=0.3`, scope='Project', `derived_from=[agent_a, agent_b]`
- `contradictions` → log in `data/contradictions.jsonl` + TG a Zero per review, NON inserire
- Reflection originali marcate `consolidated=true` in KB (NON cancellate — Genome è non-distruttivo)

### Safety gate (revert automatico)

Misura `success_rate` 10 run successive degli agenti con skill consolidate vs media 10 run pre-consolidamento.

```python
if post_mean < (pre_mean - pre_stddev):
    for skill_id in consolidated_tonight:
        genome.silence_skill(skill_id)  # epigenetic, valid_to=now()
    send_tg("Sleep consolidation reverted: success rate dropped from X% to Y%")
```

### Entries necessarie per attivare

Sleep consolidation NON gira finché non ci sono almeno 20 reflection in KB ultimi 7gg. Quindi: scrittura del codice subito, attivazione cron solo da settimana 3 di Fase 2.

### Test

- `test_dream_consolidation.py`: pass 1 con fixture reflection, pass 2 con candidate fittizi, contraddizioni, safety gate revert
- `test_dream_safety.py`: simula calo success_rate post-consolidamento → verifica silence_skill chiamato

---

## 6. Deliverable 4 — RAG Enricher

### Scelta architetturale (Q6)

**Semi-auto con pending collection** (consultazione NLM + Codex + Gemini convergenti su semi-auto; Codex propone collection separata `enrichment_pending`; Gemini cross-check pre-TG contro reference files).

### Trigger

- Threshold: `evidence_score < 0.15` (ABSTAIN range, "veri buchi")
- Budget: 5/giorno hard cap, 2/settimana per topic
- Scoping: KBLI + Visa + Tax + Immigration (Property escluso — dati troppo dinamici)

### Flusso

```
Backend RAG (Fly) emette rag.low_confidence → bridge_outbox PG
  → Bridge pull → bridge:inbound Redis stream (Pro)
  → Consumer rag_enricher (Pro):
      1. Filtro type=rag.low_confidence
      2. Verifica budget (day + topic week)
      3. Cross-notebook query NLM su NB-2..8 (visa, tax, kbli, immigration)
      4. Se trovata risposta NLM con confidence forte:
         a. Cross-check pre-TG: confronta contro PRICING_REFERENCE.md + VISA_TYPES_REFERENCE.md
         b. Se conflict → marca CONFLICT nel msg TG
         c. Pubblica enrichment.kb_entry su bridge:outbound
      5. Bridge push → POST /api/bridge/ingest/enrichment
  → Backend (Fly) inserisce in collection enrichment_pending Qdrant (NON live)
  → Notification TG a Zero: "/approve_kb {id}" o "/reject_kb {id}"
  → Se /approve: backend handler promuove pending → live
  → Se /reject o TTL 7gg: vector decade
```

### Files

| File                                                             | Responsabilità                                   |
| ---------------------------------------------------------------- | ------------------------------------------------ |
| `apps/mata-garuda/mata_garuda/agents/rag_enricher.py`            | Consumer + agent loop                            |
| `apps/mata-garuda/mata_garuda/agents/rag_enricher_GENOME.md`     | Constraints                                      |
| `apps/mata-garuda/mata_garuda/tools/rag_enricher_tools.py`       | NLM cross-notebook query, cross-check validators |
| `apps/backend-rag/backend/app/routers/enrichment_approval.py`    | Endpoint `/api/enrichment/approve` + `/reject`   |
| `apps/backend-rag/backend/services/qdrant/enrichment_pending.py` | Collection management                            |

### Cross-check validation

Prima di pubblicare su `bridge:outbound`, l'enricher legge in locale:

- `PRICING_REFERENCE.md` — se la risposta NLM contiene importi che differiscono dai prezzi ufficiali → CONFLICT
- `VISA_TYPES_REFERENCE.md` — se la risposta NLM contiene visa codes/requirements diversi → CONFLICT

Il messaggio TG a Zero include tag `[CONFLICT]` se trovato; Zero decide se approvare comunque (override) o rifiutare.

### Approval gate via TG

```
TG msg: "📚 Enrichment proposto

Topic: tax
Query originale: 'KITAS investor minimum 2 anni stage'
Risposta NLM (NB-3): 'KITAS investor 2 anni: ...'
Confidence NLM: 0.82

[NESSUN CONFLICT con PRICING/VISA]

/approve_kb 42
/reject_kb 42"
```

### Weekly batch decay

Cron lunedì 09:00 WITA: `enrichment_decay.py` rimuove entry pending non approvate >7gg dalla collection `enrichment_pending` Qdrant.

### Metriche

- Counter eventi pulled
- Counter enrichment proposed
- Counter approved / rejected / decayed
- Drift uplift: confidence media RAG sui topic post-approval (target: +5%)

### Test

- `test_rag_enricher.py`: budget, scoping, NLM query mock
- `test_cross_check.py`: conflict detection con fixture PRICING/VISA
- `test_enrichment_approval_router.py`: backend endpoint approval flow

---

## 7. Deliverable 5 — Sentinel health cell

### Scelta architetturale (Q7)

**Due cellule separate + modulo comune** (consensus 3/3 NLM+Codex+Gemini; NLM pattern Voyager `action_agent` + `critic_agent` separati; Gemini pulse isolation 5min vs 24h; Codex incompatibilità requisiti).

### Refactor

```
Rinomina:
  apps/mata-garuda/mata_garuda/cells/sentinel_cell.py
  → apps/mata-garuda/mata_garuda/cells/intel_sentinel_cell.py

Nuovo:
  apps/mata-garuda/mata_garuda/cells/health_sentinel_cell.py

Modulo condiviso:
  apps/mata-garuda/mata_garuda/cells/common/
  ├── __init__.py
  ├── envelope.py          # alias di mata_garuda/bridge/envelope.py
  └── recovery_policy.py   # whitelist actions
```

### Health sensors

| Sensor                   | Cosa misura                                                                       | Threshold red                            |
| ------------------------ | --------------------------------------------------------------------------------- | ---------------------------------------- |
| `FlyStatusSensor`        | `fly status` per nuzantara-rag/postgres/qdrant                                    | qualsiasi machine non running            |
| `LaunchdSensor`          | `launchctl list` per 22 cron registrati in `~/.agent/decisions/job_registry.json` | LastExitStatus≠0 da >2 esecuzioni        |
| `RedisStreamDepthSensor` | XLEN su 7 stream organismo                                                        | depth crescente >2x baseline per 3 pulse |
| `DiskRAMCPUSensor`       | macOS sysctl + df                                                                 | disk>90%, ram>85%, load>8                |
| `BridgeThroughputSensor` | bridge:outbound lag, last bridge run                                              | lag>50 o no-run >15min                   |

### Recovery actor

`HealthRecoveryActor` con whitelist di azioni autorizzate:

```python
ALLOWED_RECOVERY_ACTIONS = {
    "launchctl_kickstart": lambda label: ["launchctl", "kickstart", "-k", f"gui/{uid}/{label}"],
    "redis_xtrim": lambda stream, maxlen: ["redis-cli", "XTRIM", stream, "MAXLEN", str(maxlen)],
    "fly_machine_restart": lambda app, machine_id: ["fly", "machine", "restart", "-a", app, machine_id],
}
# Esplicitamente VIETATI: rm, kill, DROP, DELETE, fly machine destroy
```

### Stream nuovi

- `sentinel:alerts` — alert strutturati con envelope (type: `alert.fly_down`, `alert.cron_failed`, `alert.stream_overflow`, ...)
- `sentinel:recovery` — log azioni recovery eseguite (type: `recovery.kickstart`, `recovery.xtrim`, `recovery.restart`)

### Genome learning

Ogni recovery success → `genome.record_skill()` con `scope='recovery'`, `confidence=0.6`. Esempi di skill emergenti:

- "Quando `cron_failed` è regulation_watcher → kickstart com.matagaruda.watcher.daily ha success_rate=0.95"
- "Quando `stream_overflow` è garuda:raw e depth>500 → xtrim a 200 ha success_rate=0.88"

Su pulse successivi, l'health cell cerca prima nel Genome (`genome.search('cron_failed regulation')`) prima di chiamare claude --print.

### Fast path / slow path

NLM raccomandazione (pattern AgentSpawn): monitor programmatico veloce → trigger LLM solo se anomalia persistente.

```python
# Fast path (programmatico, <30s):
readings = await asyncio.gather(*[s.read() for s in sensors])
proposal = thinker.fast_decide(readings)  # rule-based
if proposal.action != "claude_diagnose":
    await actor.act(proposal)  # esegui recovery whitelist diretto
else:
    # Slow path (LLM-based, anomalia persistente):
    proposal = await thinker.slow_diagnose(readings)  # claude --print
    await actor.act(proposal)
```

### LaunchAgent

- `com.nuzantara.health-sentinel.plist` — pulse ogni 5 minuti, finestra 24/7
- `com.matagaruda.intel-sentinel.plist` — pulse giornaliero (esistente, da rinominare)

### Test

- `test_health_sensors.py`: ogni sensor con mock subprocess
- `test_health_recovery_actor.py`: whitelist enforcement, blocked actions raise
- `test_health_sentinel_cell.py`: pulse end-to-end con sensor red → recovery → log → genome update
- `test_recovery_policy.py`: whitelist + denylist coverage

---

## 8. Ordine implementativo

```
Pre-work (Task 0): 0.1 ✅ → 0.2 → 0.3 → 0.4
   ↓
D1 Priority Engine (indipendente)
   ↓
D2 LPSE Harvester (usa D1)
   ↓
D4 RAG Enricher (richiede 0.2)
   ↓
D3 Sleep consolidation (richiede 7gg di reflection — codice pronto, attivazione cron settimana 3)
   ↓
D5 Sentinel health cell (5-7 task TDD, ultimo, ha più isolamento)
```

Stima: ~30-35 task TDD totali, 4-6 sessioni di lavoro, ~1500-2000 LOC nuove.

---

## 9. Metriche before/after

| Metrica                                | Baseline 2026-04-14 | Target post-Fase 2                       |
| -------------------------------------- | ------------------- | ---------------------------------------- |
| Reflection entries KB                  | 1                   | ≥100 (7gg di pulse reali)                |
| Skill entries KB                       | 1                   | ≥50 (con conf >0.7)                      |
| Genome cell-core skills                | 7                   | ≥30                                      |
| `nexus:gaps` depth                     | 621 (lag 551)       | trend calante (drained dal gap consumer) |
| `garuda:raw` type=`harvest.lpse`       | 0                   | ≥1                                       |
| `bridge:inbound` eventi pulled         | 0                   | ≥1 (conferma `rag.low_confidence` reale) |
| Sleep consolidation cycles successful  | 0                   | ≥5 (1/notte × 5 notti)                   |
| RAG enrichment approved → live         | 0                   | ≥3                                       |
| Sentinel `recovery_*` skills in genome | 0                   | ≥5                                       |
| Topic priorities adattive              | static              | bump in ≤24h da nuovo cliente CRM        |
| Test mata-garuda                       | 280 pass            | ≥320 pass                                |
| Test backend                           | 794 pass            | ≥800 pass                                |

---

## 10. Vincoli architetturali (Le 8 Leggi)

Tutto il design rispetta SYMBIOSIS.md:

1. **CLI-only per LLM** — `claude --print` per reflection, sleep consolidation, RAG enricher, sentinel slow path. Nessuna API HTTP a Anthropic/Google/OpenAI.
2. **OSINT blindato** — il bridge trasporta solo dati business (CRM events, articoli, enrichment KB). I dati Garuda/Nexus restano sul Pro. La RAG enrichment scrive in collection Qdrant business, non OSINT.
3. **Event-driven** — Redis Streams per tutti i canali (bridge:inbound/outbound, nexus:gaps, sentinel:alerts, sentinel:recovery). Priority Engine è l'unico file flat (config calda).
4. **Graceful degradation** — Priority Engine senza file → harvester usano default. Sleep consolidation senza KB entries → skip silenzioso. RAG enricher senza NLM → log warning, no crash. Sentinel senza recovery whitelist match → escalation TG, no random action.
5. **Zero come ultima istanza** — RAG enricher richiede `/approve_kb` per ogni entry. Sleep consolidation invia TG solo per contraddizioni. Sentinel recovery limitato a whitelist; altre azioni → escalation TG.
6. **Sovranità locale** — tutto vive su Pro. Bridge è l'unico componente cross-frontiera.
7. **Numeri prima** — ogni deliverable ha metriche before/after misurabili nella tabella §9. Sleep consolidation ha safety gate basato su success_rate misurato.
8. **Legge 8 (5 domande universali)** — ogni componente nuovo risponde: dove sono nell'organismo, cosa produco, cosa consumo, fallisce silenzioso?, è misurabile?.

---

## 11. Cosa NON è in scope (Fase 3+)

- **Consiglio multi-modello** (Fase 3) — sleep consolidation è single-claude per ora, non MAR
- **Curiosity LLM-driven** (Fase 4) — il sistema reagisce, non propone task nuovi
- **Voyager skill library dinamica** per LPSE — parser standard SPSE 4.5 basta per la prima implementazione
- **GA4 → Revenue tracing** (Fase 4)
- **Metriche metaboliche complete** (Fase 3) — TTR, ontology density, autonomy index
- **Auto-mutation GENOME tecniche** (Fase 4) — solo manual review per ora
- **Distribuzione cellule cross-machine** (Fase 4) — tutto su Pro

---

## 12. Riferimenti

- **Spec organismo (4 fasi):** `docs/superpowers/specs/2026-04-14-organism-nervous-system-design.md`
- **Plan Fase 1 completato:** `docs/superpowers/plans/2026-04-14-organism-phase1-sinapsi.md`
- **Sprint 5 MG (assorbito):** `apps/mata-garuda/docs/superpowers/plans/2026-04-09-self-evolving-organism.md`
- **Research patterns (Voyager, Reflexion, MAR, AgentSpawn, CtxVault):** `apps/mata-garuda/docs/SELF_EVOLVING_AGENT_RESEARCH.md` + NLM notebook `305f5f2e-d2f4-4f77-a771-c2b7aa0867e4`
- **Cell-core DNA:** `packages/cell-core/cell_core/`
- **SYMBIOSIS:** `SYMBIOSIS.md`
- **VADEMECUM:** `VADEMECUM.md`
- **Mata Garuda CLAUDE:** `apps/mata-garuda/CLAUDE.md`
- **Decisioni di brainstorm:** `mem query "Phase 2"`

---

## 13. Decisioni di design — riassunto consultazione esterna

Ogni deliverable è stato validato consultando NLM (ground truth NB self-evolving agents) + Codex CLI + Gemini CLI in parallelo. Le risposte sono in `mem` con tag `Phase 2`.

| Deliverable        | NLM              | Codex             | Gemini                            | Scelta finale                                                             |
| ------------------ | ---------------- | ----------------- | --------------------------------- | ------------------------------------------------------------------------- |
| D1 Priority Engine | A flat           | D (A+JSONL)       | B SQLite                          | **D — A+JSONL** (NLM ground truth: file flat, Codex enhancement)          |
| D2 LPSE            | D+C+Voyager      | C stretto         | B targeted (rivela SPSE 4.5 JSON) | **C pragmatico + SPSE JSON** (combina insight Gemini + pragmatismo Codex) |
| D3 Sleep           | (proposto da me) | —                 | —                                 | **C Hybrid 2-pass**                                                       |
| D4 RAG Enricher    | semi-auto MAR    | semi-auto pending | semi-auto cross-check             | **convergenza: semi-auto + pending collection + cross-check pre-TG**      |
| D5 Sentinel        | A+C ibrido       | A 2-cellule       | A 2-cellule                       | **A — 2 cellule + modulo comune** (consensus 3/3)                         |

---

**Last Updated:** 2026-04-14 15:35 WITA
**Stato:** Brainstorm completato, in attesa review utente
**Next:** `superpowers:writing-plans` per piano TDD dettagliato (~30-35 task)
