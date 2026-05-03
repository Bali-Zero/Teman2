# Sistema Nervoso Centrale dell'Organismo Nuzantara — Design

> **Status:** Brainstorm completato 2026-04-14, in attesa di review utente prima del piano implementativo.
> **Filosofia:** SYMBIOSIS.md (8 leggi inviolabili). **Checklist:** VADEMECUM.md.
> **Obiettivo:** Connettere gli organi isolati di Nuzantara in un organismo che si auto-accresce, propone e (sotto supervisione) decide.

---

## 0. Sommario in lingua semplice

Oggi Nuzantara ha organi vivi ma scollegati: 552 gap nel grafo di intelligence non vengono mai consumati, gli articoli vengono pubblicati a mano, il CRM su Fly.io non comunica con Mata Garuda sul Pro, le query RAG con bassa confidence finiscono in un log e basta.

Costruiamo il sistema nervoso che li collega:

- Un **bridge bidirezionale** Pro↔Fly che fa il postino tra le due case.
- Un **gap consumer** che legge i 552 buchi nel grafo e dispatcha agenti per riempirli.
- Un **agente nuovo** (LHKPN harvester) che chiude 4 dei 8 tipi di gap.
- Un **linguaggio comune** (envelope standard a 5 campi) per tutti i messaggi tra organi.

Questa è la Fase 1 (Sinapsi). Le fasi successive aggiungono: riflessi (sleep-time consolidation), coscienza (Consiglio multi-modello), autonomia (curiosità LLM-driven + revenue tracing).

---

## 1. Stato attuale dell'organismo

### Organi vivi (mappa)

| Organo                             | Cosa fa                                                 | Stato     |
| ---------------------------------- | ------------------------------------------------------- | --------- |
| **Mata Garuda** (cervello)         | 11 agenti registrati, 3 workers, MetaChain + Lamarckian | Operativo |
| **OSINT Nexus** (memoria profonda) | Neo4j 1406 nodi, bridge consumer, 8 gap query Cypher    | Operativo |
| **Intel Scraper** (stomaco)        | 6 stadi, 630+ fonti, pubblica via POST API              | Operativo |
| **War Room** (fabbrica)            | A2A pipeline porte 8100-8108, Canva automation          | Operativo |
| **Cell-core** (DNA)                | PulseLoop, Genome FTS5, Memory 3-tier, 122 test         | Operativo |
| **EventBus** (nervi cloud)         | PG NOTIFY su 3 canali, 3 handler con dedup              | Operativo |
| **Backend RAG** (organo cloud)     | 90 router, 253 servizi, Fly.io                          | Operativo |

### Stream Redis attuali

| Stream            | Entries | Producer         | Consumer    |
| ----------------- | ------- | ---------------- | ----------- |
| `garuda:raw`      | 341     | 5 harvester      | Normalizer  |
| `garuda:enriched` | 106     | Normalizer       | Scorer      |
| `garuda:alerts`   | 0       | Scorer (score≥4) | **Nessuno** |
| `nexus:gaps`      | 552     | Gap Detector     | **Nessuno** |

### Buchi strutturali da colmare

1. `nexus:gaps` ha 552 entries — nessun consumer le legge.
2. Garuda→Backend (articoli): nessun bridge bidirezionale Pro↔Fly.
3. CRM events non arrivano a Mata Garuda — i due mondi sono isolati.
4. Nessuna metrica metabolica operativa.
5. Nessun sleep-time consolidation.
6. Nessun Consiglio multi-modello.
7. Sprint 5 (reflection engine + KB unificata) pianificato ma non implementato.

---

## 2. Architettura — Approccio C (ibrido bidirezionale)

L'organismo vive su due mondi separati da una frontiera di rete, connessi da un bridge bidirezionale.

```
┌─────────────────────────────────────┐     ┌──────────────────────────────┐
│           PRO (48GB, locale)         │     │      FLY.IO (cloud)          │
│                                      │     │                              │
│  Mata Garuda (cervello)              │     │  Backend RAG (FastAPI)       │
│  Intel Scraper (stomaco)             │     │  CRM (PG — 5000+ clienti)   │
│  War Room (fabbrica)                 │     │  EventBus (PG NOTIFY)        │
│  OSINT Nexus (Neo4j)                 │     │  Canali (WA/TG/IG/Web)      │
│  NLM Pipelines                       │     │  Qdrant (93K vectors)        │
│  Sentinel, Olympus                   │     │  Redis (cache + sessions)    │
│  OpenClaw (24 cron agentici)         │     │                              │
│  Ollama (4 modelli H24)             │     │                              │
│                                      │     │                              │
│  Bus interno: Redis Streams          │     │  Bus interno: PG NOTIFY      │
│  (7 stream, 34 type)                 │     │  + EventBus handlers         │
│                                      │     │                              │
│            ┌──────────┐              │     │                              │
│            │  BRIDGE   │◄────────────┼─────┼──── Pull: GET adattivo       │
│            │  (nervo   │─────────────┼─────┼───► Push: POST endpoint      │
│            │   vago)   │              │     │                              │
│            └──────────┘              │     │                              │
└─────────────────────────────────────┘     └──────────────────────────────┘
```

- **Redis Streams** = bus locale Pro (Garuda, Sentinel, OpenClaw, NLM)
- **PG NOTIFY + EventBus** = bus Fly.io (CRM, canali, RAG)
- **Bridge bidirezionale** = nervo vago — singolo componente, NON orchestratore
  - Pull: GET polling adattivo (30s 08-18 WITA, 5min notte)
  - Push: POST su endpoint backend
  - Graceful degradation: se uno dei due è giù, l'altro continua

**OSINT blindato (Legge 2):** il bridge trasporta solo dati business (articoli, eventi CRM, enrichment KB). I dati OSINT/Nexus NON attraversano mai la frontiera.

---

## 3. Stream design — 7 stream, 34 type, 1 envelope

### Envelope standard

Tutti gli stream usano lo stesso envelope a 5 campi obbligatori:

```json
{
  "id": "uuid-v4",
  "type": "crm.client_created",
  "source": "bridge",
  "timestamp": "2026-04-14T08:30:00+08:00",
  "priority": 3,
  "payload": {}
}
```

- `id`: UUID v4, univoco per messaggio
- `type`: dot notation gerarchica, consumer filtra per prefisso (`crm.*`)
- `source`: organo produttore
- `timestamp`: ISO 8601 con timezone WITA
- `priority`: 1 (urgente) → 5 (bassa)
- `payload`: contenuto libero, specifico per type

Puro JSON, zero dipendenze (pydantic only). Leggibile con `redis-cli XREAD`. Loggabile e replayabile.

**Migrazione stream esistenti:** `garuda:raw` e `nexus:gaps` verranno migrati a questo formato quando i consumer vengono riscritti — non urgente rompere quello che funziona.

### Catalogo type completo

| Stream               | Type                        | Producer                  | Fase |
| -------------------- | --------------------------- | ------------------------- | ---- |
| **garuda:raw**       | `harvest.regulation`        | Regulation Watcher        | 1    |
|                      | `harvest.arxiv`             | ArXiv Harvester           | 1    |
|                      | `harvest.github`            | GitHub Harvester          | 1    |
|                      | `harvest.youtube`           | YouTube Harvester         | 1    |
|                      | `harvest.newsletter`        | Newsletter Harvester      | 1    |
|                      | `harvest.lhkpn`             | LHKPN Harvester (nuovo)   | 1    |
|                      | `harvest.lpse`              | LPSE Harvester (nuovo)    | 2    |
| **garuda:enriched**  | `enriched.normalized`       | Normalizer worker         | 1    |
|                      | `enriched.scored`           | Scorer worker             | 1    |
| **garuda:alerts**    | `alert.high_score`          | Scorer (score≥4)          | 1    |
|                      | `alert.gap_urgent`          | Gap consumer (priority=1) | 2    |
| **nexus:gaps**       | `gap.missing_nip`           | Gap Detector              | 1    |
|                      | `gap.missing_lhkpn`         | Gap Detector              | 1    |
|                      | `gap.stale_official`        | Gap Detector              | 1    |
|                      | `gap.orphan_org`            | Gap Detector              | 1    |
|                      | `gap.missing_procurement`   | Gap Detector              | 1    |
|                      | `gap.missing_office`        | Gap Detector              | 1    |
|                      | `gap.missing_angkatan`      | Gap Detector              | 1    |
|                      | `gap.kanim_struktur`        | Gap Detector              | 1    |
| **bridge:outbound**  | `intel.article_ready`       | Intel Scraper/War Room    | 1    |
|                      | `intel.article_published`   | Bridge (conferma)         | 1    |
|                      | `enrichment.kb_entry`       | MG enrichment agents      | 2    |
| **bridge:inbound**   | `crm.client_created`        | Bridge poll               | 1    |
|                      | `crm.client_sector_changed` | Bridge poll               | 1    |
|                      | `crm.practice_completed`    | Bridge poll               | 1    |
|                      | `crm.practice_created`      | Bridge poll               | 1    |
|                      | `compliance.critical_alert` | Bridge poll               | 2    |
|                      | `rag.low_confidence`        | Bridge poll               | 2    |
| **organism:metrics** | `metric.ttr`                | TTR calculator            | 3    |
|                      | `metric.ontology_density`   | Neo4j query               | 3    |
|                      | `metric.autonomy_index`     | Task origin counter       | 3    |
|                      | `metric.escalation_rate`    | TG message counter        | 3    |

**Totale: 34 type su 7 stream.** I consumer filtrano per prefisso.

---

## 4. Bridge bidirezionale (il nervo vago)

### Componente singolo

`apps/mata-garuda/mata_garuda/bridge/nerve.py`

Vive nel monorepo come parte di Mata Garuda. NON è un daemon — è un worker invocato da cron (LaunchAgent `com.matagaruda.bridge.adaptive`).

**Schedule adattivo:**

- 08:00-18:00 WITA: ogni 30 secondi (orario lavoro)
- 18:00-08:00 WITA: ogni 5 minuti (notte)

Implementato come due `StartCalendarInterval` separati nel plist, oppure come singolo daemon con sleep adattivo (preferito: meno overhead di launch).

### Pull (Fly→Pro)

```python
GET https://nuzantara-rag.fly.dev/api/bridge/events?after_id={cursor}&limit=50
Headers:
  X-Bridge-Auth: {BRIDGE_API_KEY from ~/.nuzantara-secrets.env}

Response:
{
  "events": [
    {"id": 1234, "type": "crm.client_created", "payload": {...}, "created_at": "..."},
    ...
  ],
  "last_id": 1287
}
```

Per ogni evento:

1. Wrap in envelope standard con `source="bridge"`
2. `XADD bridge:inbound * data <json>`
3. Dopo XADD di tutti, salva cursor in `~/.agent/decisions/bridge_cursor.json` (atomic write-then-rename)

Se Fly unreachable → log warning, retry al prossimo ciclo, nessun crash.

### Push (Pro→Fly)

```python
# Consumer group: bridge-push:nerve-1
XREADGROUP GROUP bridge-push nerve-1 COUNT 10 BLOCK 1000 STREAMS bridge:outbound >
```

Per ogni messaggio:

- `type == "intel.article_ready"` → `POST /api/bridge/ingest/article`
- `type == "enrichment.kb_entry"` → `POST /api/bridge/ingest/enrichment`

Se POST 200:

- `XACK bridge:outbound bridge-push <id>`
- Pubblica conferma `intel.article_published` su `bridge:outbound` (per tracking interno)

Se POST fallisce:

- NON XACK (at-least-once delivery)
- Log error, retry al prossimo ciclo
- Dopo 5 fallimenti consecutivi sullo stesso messaggio: skip + log + TG a Zero

### Backend side (Fly.io)

**Migrazione Alembic 061:** `bridge_outbox` table

```sql
CREATE TABLE bridge_outbox (
    id BIGSERIAL PRIMARY KEY,
    type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_outbox_id ON bridge_outbox(id);
CREATE INDEX idx_outbox_type ON bridge_outbox(type);
```

**Retention:** cron `DELETE FROM bridge_outbox WHERE created_at < NOW() - INTERVAL '30 days'`. Schedulato giornalmente alle 04:00 UTC.

**Router `backend/app/routers/bridge.py`:** 3 endpoint:

1. `GET /api/bridge/events?after_id=&limit=` — legge outbox, auth via `X-Bridge-Auth` header, response con `last_id`
2. `POST /api/bridge/ingest/article` — riceve articolo, lo inserisce nel CMS, response `{"article_id": "...", "status": "published"}`
3. `POST /api/bridge/ingest/enrichment` — riceve KB entry, la inserisce in Qdrant, response `{"vector_id": "...", "status": "indexed"}`

**Triggers EventBus → outbox:** modifiche ai handler esistenti in `backend/services/events/handlers.py`:

- `on_client_changed` aggiunge `INSERT INTO bridge_outbox` per tipi: `crm.client_created`, `crm.client_sector_changed`
- `on_practice_status_changed` aggiunge INSERT per: `crm.practice_completed`, `crm.practice_created`
- `on_compliance_alert` aggiunge INSERT per: `compliance.critical_alert` (solo severity=critical AND days_until_expiry≤7)

**Trigger nuovo per RAG low confidence:** in `backend/services/rag/answer.py`, dopo ogni query con `confidence < 0.3`, INSERT in `bridge_outbox` con dedup 24h (key: hash della query). Type: `rag.low_confidence`.

### Graceful degradation (Legge 4)

| Scenario    | Comportamento                                                                 |
| ----------- | ----------------------------------------------------------------------------- |
| Fly down    | Pro continua, eventi si accumulano in outbox, al ripristino Pro riceve tutto  |
| Pro down    | Outbox cresce (max 30gg retention), nessuna perdita                           |
| Redis down  | Bridge non parte, organi funzionano in isolamento                             |
| Bridge down | Outbox accumula (cursor non avanza), articoli accumulano in `bridge:outbound` |

---

## 5. Gap consumer e LHKPN harvester

### Gap consumer

`apps/mata-garuda/mata_garuda/workers/gap_consumer.py`

Worker che legge `nexus:gaps` via consumer group `gap-consumer:consumer-1`.

**Mapping gap type → agente:**

```python
GAP_DISPATCH = {
    "gap.missing_nip":          "lhkpn_harvester",
    "gap.missing_lhkpn":        "lhkpn_harvester",
    "gap.missing_angkatan":     "lhkpn_harvester",
    "gap.stale_official":        "regulation_watcher",
    "gap.orphan_org":            "regulation_watcher",
    "gap.missing_office":        "regulation_watcher",
    "gap.kanim_struktur":        "regulation_watcher",
    "gap.missing_procurement":   None,  # Fase 2 — skip con log
}
```

**Flusso per ogni gap:**

1. Lookup mapping
2. Se `None` → XACK + log "skipped (Fase 2)"
3. Se agent → `MetaChain.run(agent_name, gap.payload)`
4. Se successo (`case_resolved`) → XACK + pubblica risultato su `garuda:raw`
5. Se fallimento (`case_not_resolved`) → 2 retry con backoff esponenziale (10s, 60s)
6. Dopo 2 retry falliti → XACK + log + non blocca la coda

**Rate limit:** max 5 dispatch/ciclo per evitare di saturare le CLI LLM (claude/gemini hanno limiti). Sleep tra dispatch: 2 secondi.

**Schedule:** LaunchAgent `com.matagaruda.gap.consumer`, ogni 10 minuti durante 06:00-22:00 WITA.

### LHKPN harvester

`apps/mata-garuda/mata_garuda/agents/lhkpn_harvester.py` + `lhkpn_harvester_GENOME.md`

**Scopo:** scrape antv.kpk.go.id/elhkpn/ (portale dichiarazioni patrimoniali) per riempire 4 dei 8 gap types: `missing_nip`, `missing_lhkpn`, `missing_angkatan`, `stale_official`.

**Layer:** 1 (harvester)

**Tools:** `scraper_tools.py` esteso con:

- `scrape_lhkpn_search(name)` → cerca per nome
- `scrape_lhkpn_profile(nip)` → estrae dichiarazione completa per NIP
- `parse_lhkpn_assets(html)` → struttura JSON: properties[], vehicles[], accounts[], total_harta

**Output:** `XADD garuda:raw` con type `harvest.lhkpn`, payload:

```json
{
  "person_name": "...",
  "person_nip": "...",
  "report_year": 2025,
  "total_harta": 12500000000,
  "delta_yoy": 850000000,
  "properties_count": 7,
  "vehicles_count": 3,
  "accounts_count": 12,
  "angkatan": "1995",
  "source_url": "https://antv.kpk.go.id/...",
  "scraped_at": "2026-04-14T..."
}
```

**GENOME.md:**

- Vincoli: max 10 req/min (rate limit antv.kpk.go.id)
- User-Agent rotation (3 varianti)
- Fallback se 403: switch User-Agent + retry
- Escalation: 3 fallimenti consecutivi → meta-agent review

---

## 6. Sleep-time consolidation (Fase 2)

### Cron e script

LaunchAgent `com.matagaruda.dream.nightly`, finestra 01:00-05:00 WITA (esecuzione singola alle 01:00).

Script: `apps/mata-garuda/scripts/dream_consolidation.py`

### Flusso

1. **Read recent KB:** query SQLite Genome per entries ultimi 7 giorni (reflections, insights, skills) di tutti gli agenti.

2. **Read existing genome:** SELECT skill esistenti con `confidence > 0.7` — il "genoma attuale".

3. **LLM consolidation:** `claude --print` con prompt:

   ```
   Sei il sistema di consolidamento notturno di Mata Garuda.
   Genoma attuale (skill validate): {genome_json}
   Esperienze ultimi 7 giorni: {recent_entries_json}

   Output JSON con:
   - consolidated_skills[]: nuove skill estratte (procedure riusabili)
   - contradictions[]: skill nuove che contraddicono genoma attuale
   - prunable_entries[]: entry rumorose o duplicate da potare
   - summary: 1 frase

   Una skill contraddice se: stessa category + stessa precondition ma procedure diversa.
   ```

4. **Output JSON format:**

   ```json
   {
     "consolidated_skills": [
       {
         "skill_id": "harvest_403_bypass",
         "procedure": "Use User-Agent 'Mozilla/5.0...' with Accept-Language 'id-ID'",
         "precondition": "Target returns HTTP 403 on default headers",
         "success_criterion": "HTTP 200 with content length > 1000",
         "confidence": 0.3,
         "derived_from": ["reflection_42", "reflection_67"],
         "category": "scraping"
       }
     ],
     "contradictions": [
       {
         "existing_skill_id": "always_use_curl",
         "new_claim": "httpx async is faster for batch",
         "conflict_type": "method_disagreement"
       }
     ],
     "prunable_entries": ["reflection_12", "reflection_15"],
     "summary": "3 skills extracted, 1 contradiction, 2 prunable"
   }
   ```

5. **Apply with safety:**
   - Skill non contraddittorie → INSERT in Genome con `confidence=0.3`, `scope='Project'`
   - Contraddizioni → log in `data/contradictions.jsonl`, TG a Zero per review, NON inserire
   - Entry originali marcate `consolidated=true` (NON cancellate — Genome è non-distruttivo)

### Safety gate (revert automatico)

Misura `success_rate` delle 10 run successive degli agenti che usano le skill consolidate (via `fitness.py`). Confronta con media 10 run pre-consolidamento.

Se `post_mean < pre_mean - pre_stddev` (più di 1σ in calo):

- `genome.silence_skill(skill_id)` per ogni skill consolidata in quella notte
- TG a Zero: "Sleep consolidation reverted: success rate dropped from X% to Y%"
- Le skill restano in Genome ma con `valid_to=now()` (epigenetic silencing, non cancellate)

---

## 7. Metriche metaboliche (Fase 3)

### 4 metriche

| Metrica                      | Calcolo                                                                                                          | Baseline 2026-04-14  | Target        |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------- | -------------------- | ------------- |
| **TTR** (Time-to-Resolution) | `gap.created_at` → `garuda:raw resolved_at` (correlato via `gap_id` nel payload), media mobile 30 giorni         | ∞ (0 gap consumati)  | Calante       |
| **Densità ontologica**       | Neo4j: `MATCH ()-[r]-() RETURN count(r)` / `MATCH (n) RETURN count(n)`                                           | 2121/1406 = **1.51** | Crescente     |
| **Indice autonomia**         | KB query: `SELECT origin, count(*) FROM tasks WHERE created_at > now-30d GROUP BY origin`, ratio endogeno/totale | ~0%                  | >30% a Fase 4 |
| **Frequenza escalation**     | Conta messaggi TG con tag `[escalation]` per settimana                                                           | Da misurare          | Calante       |

### Collector

`apps/mata-garuda/scripts/metrics_collector.py`

LaunchAgent `com.matagaruda.metrics.weekly`, ogni domenica 18:00 WITA.

**Per ogni metrica:**

1. Calcola valore corrente
2. Pubblica su `organism:metrics` con envelope (type: `metric.ttr`, etc.)
3. INSERT in SQLite locale `~/.agent/decisions/organism_metrics.db`:
   ```sql
   CREATE TABLE metrics_history (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       metric_type TEXT NOT NULL,
       value REAL NOT NULL,
       calculated_at TEXT NOT NULL,
       metadata JSON
   );
   ```

**Trend visualization:** non in scope per Fase 3. Query SQL ad-hoc per Zero che vuole vedere il trend.

---

## 8. Consiglio multi-modello (Fase 3)

### 4 modelli architettonicamente diversi

1. **Claude (cli)** — `claude --print`
2. **Gemini (cli)** — `gemini --prompt`
3. **DeepSeek (API)** — unica API ammessa (Legge 1)
4. **Ollama locale** — `gemma4:26b` o `deepseek-r1:32b`

NO roleplay sullo stesso modello. La diversità deve essere architettonica per evitare groupthink.

### Script e flusso

`apps/mata-garuda/scripts/council.py`

Cron settimanale: domenica 16:00 WITA (LaunchAgent `com.matagaruda.council.weekly`).

**Flusso:**

1. **Dossier preparation:** moderatore Python prepara JSON con:
   - Ultime 4 metriche metaboliche
   - Top 10 gaps irrisolti (`nexus:gaps` non consumati >7gg)
   - Skill consolidate ultima settimana
   - Proposte pendenti (curiosity_proposals.json se Fase 4)
   - Eventi notevoli ultima settimana (escalation, contradictions)

2. **Parallel query:** invia stessa domanda strutturata a tutti e 4 via subprocess (parallelo). Domanda template:

   ```
   Dato il dossier dell'organismo Nuzantara, cosa raccomandi
   per la prossima settimana? Massimo 3 azioni con motivazione.
   Output JSON: {"actions": [{"action": "...", "rationale": "...", "priority": 1-5}]}
   ```

3. **Synthesis:** raccoglie le 4 risposte JSON, le ripresenta a un 5° LLM (claude --print) come moderatore:

   ```
   4 modelli hanno risposto al dossier. Trova:
   - Consenso (azioni proposte da ≥3 modelli)
   - Dissenso (azioni proposte solo da 1 modello)
   - Falle (se tutti concordano troppo, cerca cosa hanno mancato)
   Output JSON con: agreement_level (0-1), consensus_actions[], dissent_positions[], blind_spots[]
   ```

4. **Routing:**
   - Se `agreement_level < 0.6` → escalation TG a Zero con dossier completo + 4 risposte
   - Se `agreement_level >= 0.6` → salva decisione in Genome:
     ```python
     genome.record_skill(
       cell="council",
       skill_id="council_decision_{date}",
       procedure=consensus_actions,
       confidence=0.6,
       scope="Project"
     )
     ```
     TG informativo a Zero.

---

## 9. Curiosità a 2 stadi (Fase 1 + Fase 4)

### Stadio 1 — Gap-driven (Fase 1)

Curiosità reattiva, già quasi implementata:

```
Gap Detector → nexus:gaps → Gap Consumer → dispatcha agente → garuda:raw
→ Bridge consumer aggiorna grafo → Gap Detector trova nuovi gap → loop
```

L'organismo vede un buco, lo riempie. Non scopre cose nuove — riempie cose note.

### Stadio 2 — LLM-driven (Fase 4)

Curiosità generativa:

`apps/mata-garuda/scripts/curiosity_engine.py`

Cron settimanale (domenica 09:00 WITA, prima del Consiglio).

**Flusso:**

1. Legge archivio task ultime 4 settimane (completati + falliti) da KB
2. Legge stato grafo (top entities, gap pattern)
3. Legge skill accumulate (genoma attuale)
4. `claude --print` con prompt:

   ```
   Sei l'engine di curiosità di Mata Garuda.
   Archivio task: {recent_tasks}
   Stato grafo: {graph_summary}
   Skill: {skills}

   Cosa è la cosa più interessante da esplorare alla frontiera
   delle capacità dell'organismo? Proponi 1-3 task nuovi che:
   - Non sono già stati fatti
   - Riempiono un buco non rilevato dal gap detector
   - Estendono le capacità dell'organismo

   Output JSON: [{"task": "...", "rationale": "...", "expected_outcome": "..."}]
   ```

5. Output → `~/.agent/decisions/curiosity_proposals.json`
6. TG a Zero per approvazione: "Curiosity propone N task. Approvi?"
7. Se Zero approva → task entrano in coda esecuzione con `origin=endogeno` (alimenta indice di autonomia)

---

## 10. Produzione→Revenue tracing (Fase 4)

### Chiave di correlazione

`article_id` (UUID v4 generato da Intel Scraper al momento della creazione, prima della pubblicazione).

### Catena end-to-end

```
1. Intel Scraper genera article_id durante la composizione
2. War Room finalizza articolo (Canva slides + body MDX), include article_id in frontmatter
3. Pubblicazione: bridge:outbound (type: intel.article_ready, payload.article_id)
4. Bridge push: POST /api/bridge/ingest/article
5. Backend pubblica su frontend (MDX viene processato, article_id finisce nei meta)
6. GA4 (property 505466833) traccia per URL: pageviews, tempo, conversioni
7. Cron giornaliero su Pro: pull GA4 metrics → wrap in event → INSERT bridge_outbox
   type: analytics.article_performance
   payload: {article_id, pageviews_24h, avg_time_seconds, conversions_count}
8. Bridge pull → bridge:inbound → MG analytics worker
9. MG correla: article_id → topic → settore → clienti CRM con quel settore
10. Catena tracciata in SQLite locale: revenue_correlation table
```

### Tabella revenue_correlation

```sql
CREATE TABLE revenue_correlation (
    article_id TEXT PRIMARY KEY,
    topic TEXT,
    sector TEXT,
    published_at TEXT,
    pageviews_total INTEGER,
    conversions_total INTEGER,
    estimated_revenue_eur REAL,
    last_updated TEXT
);
```

Aggiornata settimanalmente. Permette query: "Quanto fatturato ha generato la nostra intelligence sul settore PMA negli ultimi 90 giorni?"

---

## 11. Le 4 fasi con deliverable concreti

### Fase 1 — SINAPSI (connettere)

| #    | Task                         | File da creare/modificare                                               | Test                             |
| ---- | ---------------------------- | ----------------------------------------------------------------------- | -------------------------------- |
| 1.1  | Envelope model Pydantic      | `apps/mata-garuda/mata_garuda/bridge/envelope.py`                       | `test_envelope.py`               |
| 1.2  | Bridge nerve (pull+push)     | `apps/mata-garuda/mata_garuda/bridge/nerve.py`                          | `test_nerve.py`                  |
| 1.3  | Backend outbox migration     | `apps/backend-rag/backend/migrations/versions/061_bridge_outbox.py`     | up/down test                     |
| 1.4  | Backend bridge router        | `apps/backend-rag/backend/app/routers/bridge.py`                        | `test_bridge_router.py`          |
| 1.5  | EventBus→outbox triggers     | `apps/backend-rag/backend/services/events/handlers.py` (modify)         | `test_handlers_outbox.py`        |
| 1.6  | RAG low confidence trigger   | `apps/backend-rag/backend/services/rag/answer.py` (modify)              | `test_low_confidence_trigger.py` |
| 1.7  | Gap consumer worker          | `apps/mata-garuda/mata_garuda/workers/gap_consumer.py`                  | `test_gap_consumer.py`           |
| 1.8  | LHKPN harvester agent        | `apps/mata-garuda/mata_garuda/agents/lhkpn_harvester.py` + `_GENOME.md` | `test_lhkpn.py`                  |
| 1.9  | LHKPN scraper tools          | `apps/mata-garuda/mata_garuda/tools/scraper_tools.py` (extend)          | `test_scraper_tools.py`          |
| 1.10 | LaunchAgent bridge           | `~/Library/LaunchAgents/com.matagaruda.bridge.adaptive.plist`           | manual verify                    |
| 1.11 | LaunchAgent gap consumer     | `~/Library/LaunchAgents/com.matagaruda.gap.consumer.plist`              | manual verify                    |
| 1.12 | Automation catalog update    | `scripts/automation_catalog.json` (3 entries)                           | —                                |
| 1.13 | Sentinel job_registry update | `~/.agent/decisions/job_registry.json` (3 entries)                      | —                                |
| 1.14 | Bridge API key in secrets    | `~/.nuzantara-secrets.env` (BRIDGE_API_KEY)                             | manual verify                    |

**Metriche Fase 1 (before/after):**

| Metrica                        | Before | After                                                              |
| ------------------------------ | ------ | ------------------------------------------------------------------ |
| Cicli chiusi end-to-end        | 0      | 4 (CRM→MG, MG→backend, gap→harvest, RAG→enrichment)                |
| Gap consumati                  | 0/552  | 552/552 entro 7gg                                                  |
| Articoli pubblicati via bridge | 0      | ≥1 articolo end-to-end (test)                                      |
| Bridge uptime                  | N/A    | >95% (calcolato come `(periodi successo)/(periodi totali)` su 7gg) |

### Fase 2 — RIFLESSI (reagire)

| #   | Task                                                                                                                                                     |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2.1 | Sprint 5 Mata Garuda (7 task dal piano esistente: RunOutcome, KB unificata, reflection engine, knowledge tools, hook reflection, integration test, docs) |
| 2.2 | Sleep-time consolidation script + cron                                                                                                                   |
| 2.3 | CRM→Intelligence priority engine (consumer `bridge:inbound` → topic priorities JSON)                                                                     |
| 2.4 | LPSE harvester (chiude `gap.missing_procurement`)                                                                                                        |
| 2.5 | Sentinel migrazione a cell-core (sentinel:alerts stream nasce qui)                                                                                       |
| 2.6 | RAG enrichment agent (consuma `rag.low_confidence`, arricchisce KB)                                                                                      |

**Metriche Fase 2:**

- Skill in KB con confidence >0.7 (target: >50)
- Consolidamento notturno operativo (cron success rate >90%)
- Priorità harvesting adattive (verificabile: settore di nuovo cliente PMA → priorità harvester aumenta entro 24h)

### Fase 3 — COSCIENZA (deliberare)

| #   | Task                                               |
| --- | -------------------------------------------------- |
| 3.1 | Metrics collector + SQLite trend                   |
| 3.2 | Consiglio v1 (4 modelli + moderatore)              |
| 3.3 | Meta-cognizione settimanale (analisi cross-organo) |

**Metriche Fase 3:**

- 4 metriche tracciate con trend visibile in SQLite
- N decisioni proposte dal Consiglio (target: 1/settimana)
- Densità ontologica >1.7 (da 1.51 baseline)

### Fase 4 — AUTONOMIA (anticipare)

| #   | Task                                                   |
| --- | ------------------------------------------------------ |
| 4.1 | Curiosità LLM-driven (stadio 2)                        |
| 4.2 | GA4→outbox integration per article performance         |
| 4.3 | Revenue tracing end-to-end (revenue_correlation table) |
| 4.4 | Production guidance: CRM+SEO drive content production  |

**Metriche Fase 4:**

- X% task endogeni (target: >30%)
- Revenue tracciabile a intelligence (almeno 1 articolo con catena completa documentata)
- Indice autonomia >30%

---

## 12. Vincoli architetturali (Le 8 Leggi)

Tutto il design rispetta SYMBIOSIS.md:

1. **CLI-only per LLM:** subprocess `claude --print`, `gemini --prompt`. Solo DeepSeek API ammessa nel Consiglio (Fase 3).
2. **OSINT blindato:** bridge trasporta solo dati business. `garuda:raw` e `nexus:gaps` NON attraversano la frontiera.
3. **Event-driven:** Redis Streams + PG NOTIFY. Nessun polling interno (solo bridge fa polling esterno per necessità di rete).
4. **Graceful degradation:** ogni organo continua se gli altri sono down. Documentato in §4.
5. **Zero come ultima istanza:** Consiglio propone, Zero approva via TG. Curiosità propone, Zero approva.
6. **Sovranità locale:** tutto vive su Pro 48GB. Bridge è l'unico componente che parla con cloud.
7. **Numeri prima:** ogni fase ha metriche before/after. 4 metriche metaboliche operative in Fase 3.
8. **Legge 8 (5 domande):** ogni componente nuovo risponde a "dove sono nell'organismo, cosa produco, cosa consumo, fallisce silenzioso?, è misurabile?".

---

## 13. Cosa NON è in scope

- **Non orchestratore centrale:** il bridge è un postino, non un decisore. Nessun componente fa orchestrazione globale.
- **Non riscrittura:** Sprint 5 esistente viene assorbito in Fase 2, non riscritto.
- **Non nuovo framework:** zero dipendenze nuove (pydantic+pytest already in scope).
- **Non vector DB nuovo:** Qdrant esistente per RAG, SQLite Genome per skill — basta.
- **Non breaking changes:** stream esistenti continuano a funzionare. Migrazione a envelope è opzionale e graduale.
- **Non auto-deploy:** ogni fase richiede approvazione Zero prima di andare in produzione.

---

## 14. Riferimenti

- **SYMBIOSIS.md** — 8 leggi inviolabili
- **VADEMECUM.md** — checklist per ogni elemento creato
- **apps/mata-garuda/CLAUDE.md** — vincoli specifici Mata Garuda
- **apps/mata-garuda/docs/SELF_EVOLVING_AGENT_RESEARCH.md** — 6 pattern (Reflexion, Voyager, DGM, EvoPrompt, Hybrid Memory, Sandbox)
- **apps/mata-garuda/docs/superpowers/plans/2026-04-09-self-evolving-organism.md** — Sprint 5 (assorbito in Fase 2)
- **~/Desktop/OSINT-Nexus/docs/SYMBIOSIS_ARCHITECTURE.md** — architettura Garuda↔Nexus
- **scripts/automation_catalog.json** — catalogo 266 automazioni
- **docs/AUTOMATION_MODEL_MAP.md** — mappa modelli LLM x automazioni

---

**Last Updated:** 2026-04-14
**Stato:** Brainstorm completato, in attesa review utente
**Next:** Invocare `superpowers:writing-plans` per piano implementativo dettagliato
