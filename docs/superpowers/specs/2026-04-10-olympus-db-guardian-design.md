# OLIMPO — Il Custode Immortale del Database

> Data: 2026-04-10
> Fonti: Audit completo schema Fly (142 tabelle, 870K+ audit, 252K KG edges), 
>        codebase analysis (4 repository, 80+ service con SQL inline, 45 trigger, 19 view),
>        SOTA research (pg_cron, partitioning, materialized views, auto-healing),
>        Testo Sacro (SELF_EVOLVING_AGENT_RESEARCH.md — Reflexion, Voyager, DGM, EvoPrompt)
> Decisioni brainstorming: Anima A (integrato), Autonomia 2 (agisce+chiede), Multi-ritmo D, 
>                          Memoria PG, Crescita via Reflexion loop, Confronto inter-agente

---

## 1. IDENTITA

L'Olimpo non e' un cron job che fa VACUUM. E' un membro permanente dell'ecosistema Nuzantara
che **conosce** il database, **agisce** su di esso, **impara** dai risultati, **condivide** la
saggezza con gli altri agenti, e **si confronta** con loro per decisioni che superano il suo dominio.

### Principi fondamentali

| Principio | Meccanismo |
|-----------|-----------|
| **Ciclo Vitale Immortale** | Multi-ritmo: heartbeat 5min, pulse 6h, meta-cognizione settimanale |
| **Auto-Healing** | Ripara autonomamente cio' che sa riparare, propone per il resto |
| **Saggezza che si espande** | Non accumula log — estrae pattern, modifica il proprio comportamento |
| **Confronto** | Consiglio dell'Olimpo settimanale con tutti gli agenti del sistema |
| **Condivisione** | Le scoperte fluiscono verso chi ne ha bisogno, non restano in silos |

---

## 2. ARCHITETTURA

### Dove vive

Integrato in `apps/backend-rag/` come servizio Python. Usa il pool asyncpg esistente
(`app.state.db_pool`). Si avvia nel `service_initializer.py` come gli altri background task.

```
apps/backend-rag/backend/
  services/
    olympus/
      __init__.py
      guardian.py          # OlympusGuardian — classe principale, multi-ritmo
      heartbeat.py         # Ritmo veloce: metriche, alert, check vitali (ogni 5min)
      pulse.py             # Ritmo medio: manutenzione, cleanup, repair (ogni 6h)
      metacognition.py     # Ritmo lento: analisi trend, proposta regole (settimanale)
      rules_engine.py      # Legge olympus_rules, applica soglie dinamiche
      council.py           # Consiglio dell'Olimpo — raccoglie report, confronto inter-agente
      skills.py            # Skill library — procedure riusabili apprese dall'esperienza
      models.py            # Pydantic models per azioni, insight, regole
      alerts.py            # Integrazione Telegram per alert e proposte
```

### Separazione dalla macchina PG

L'Olimpo vive su `nuzantara-rag` (backend). PostgreSQL vive su `nuzantara-postgres` (macchina separata).
Tutto il lavoro dell'Olimpo avviene **via SQL** attraverso asyncpg. Non ha e non serve accesso
al filesystem della macchina PG.

Operazioni possibili via SQL:
- VACUUM ANALYZE, REINDEX CONCURRENTLY
- Query pg_stat_* (monitoring completo)
- CREATE/DROP INDEX, MATERIALIZED VIEW
- Funzioni PL/pgSQL, trigger
- pg_notify per eventi
- Advisory locks

Operazioni che richiedono intervento manuale (rare):
- Installare estensioni (pg_cron) → `fly ssh console -a nuzantara-postgres`
- Modificare postgresql.conf → idem

---

## 3. I TRE RITMI

### 3.1 Heartbeat (ogni 5 minuti) — Il battito cardiaco

Leggero, veloce, sempre attivo. Non modifica nulla. Osserva e allerta.

```python
async def heartbeat(self) -> HeartbeatResult:
    """Pulse vitale ogni 5 minuti."""
    metrics = {}
    
    # Pool health
    metrics["pool_size"] = self.pool.get_size()
    metrics["pool_idle"] = self.pool.get_idle_size()
    metrics["pool_utilization"] = 1 - (metrics["pool_idle"] / max(metrics["pool_size"], 1))
    
    # Connection count (vs max_connections)
    metrics["connections"] = await conn.fetchval(
        "SELECT COUNT(*) FROM pg_stat_activity WHERE datname = current_database()"
    )
    metrics["max_connections"] = await conn.fetchval("SHOW max_connections")
    
    # Dead tuple hotspots (top 3)
    metrics["bloat_top3"] = await conn.fetch("""
        SELECT relname, n_dead_tup, n_live_tup,
               CASE WHEN n_live_tup > 0 
                    THEN round(100.0 * n_dead_tup / n_live_tup, 2) ELSE 0 END AS dead_pct
        FROM pg_stat_user_tables
        WHERE n_dead_tup > 1000
        ORDER BY n_dead_tup DESC LIMIT 3
    """)
    
    # Long-running queries (> 30s)
    metrics["long_queries"] = await conn.fetch("""
        SELECT pid, now() - query_start AS duration, query
        FROM pg_stat_activity
        WHERE state = 'active' AND query_start < now() - interval '30 seconds'
        AND query NOT LIKE '%pg_stat%'
    """)
    
    # DB size growth (compare with last heartbeat)
    metrics["db_size_bytes"] = await conn.fetchval(
        "SELECT pg_database_size(current_database())"
    )
    
    # Alert if thresholds exceeded
    if metrics["pool_utilization"] > 0.8:
        await self.alert("Pool saturation: {:.0%}".format(metrics["pool_utilization"]))
    if metrics["connections"] > int(metrics["max_connections"]) * 0.7:
        await self.alert(f"Connection count high: {metrics['connections']}/{metrics['max_connections']}")
    for row in metrics["long_queries"]:
        await self.alert(f"Long query ({row['duration']}): {row['query'][:100]}")
    
    # Persist snapshot
    await self._save_heartbeat(metrics)
    return HeartbeatResult(metrics=metrics, alerts_sent=self._alerts_count)
```

Metriche raccolte:
- Pool utilization (%, soglia alert 80%)
- Active connections vs max_connections (soglia 70%)
- Dead tuple hotspot top 3 (soglia 10% dead_pct)
- Long-running queries > 30s
- DB size (per calcolo growth rate)
- Lock waits
- Replication lag (se mai attivato)

### 3.2 Pulse (ogni 6 ore) — La manutenzione

Agisce autonomamente su operazioni sicure. Registra tutto.

**Azioni autonome (livello 2 — fa da solo):**

```python
async def pulse(self) -> PulseResult:
    """Manutenzione profonda ogni 6 ore."""
    actions = []
    
    # 1. VACUUM ANALYZE su tabelle con dead_pct > 10%
    bloated = await conn.fetch("""
        SELECT relname, n_dead_tup FROM pg_stat_user_tables
        WHERE n_dead_tup > 1000
        AND CASE WHEN n_live_tup > 0 
            THEN 100.0 * n_dead_tup / n_live_tup ELSE 0 END > 10
    """)
    for table in bloated:
        await conn.execute(f"VACUUM ANALYZE {table['relname']}")
        actions.append(Action(type="vacuum", target=table["relname"], 
                              detail=f"{table['n_dead_tup']} dead tuples"))
    
    # 2. Repair broken sequences
    broken_seqs = await self._find_broken_sequences()
    for seq in broken_seqs:
        await conn.execute(f"SELECT setval('{seq['seq']}', {seq['max_val']})")
        actions.append(Action(type="seq_repair", target=seq["table"]))
    
    # 3. Rebuild invalid indexes
    invalid = await conn.fetch(
        "SELECT indexrelid::regclass AS idx FROM pg_index WHERE NOT indisvalid"
    )
    for idx in invalid:
        await conn.execute(f"REINDEX INDEX CONCURRENTLY {idx['idx']}")
        actions.append(Action(type="reindex", target=str(idx["idx"])))
    
    # 4. Refresh materialized views
    for mv in self.materialized_views:
        await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {mv}")
        actions.append(Action(type="mv_refresh", target=mv))
    
    # 5. Cleanup audit trail > retention period (from rules)
    retention = await self._get_rule("audit_retention_days", default=90)
    deleted = await conn.execute(f"""
        DELETE FROM api_audit_trail 
        WHERE created_at < NOW() - INTERVAL '{retention} days'
    """)
    actions.append(Action(type="cleanup", target="api_audit_trail", detail=deleted))
    
    # 6. Cleanup expired sessions
    await conn.execute("""
        DELETE FROM persistent_sessions 
        WHERE updated_at < NOW() - INTERVAL '30 days'
    """)
    
    # 7. Find orphan records (diagnostic, no auto-delete)
    orphans = await self._find_orphans()
    if orphans:
        actions.append(Action(type="orphan_detected", detail=str(orphans)))
        # Non cancella — propone a Zero
        await self.propose("Orphan records found", orphans)
    
    # 8. Table size anomaly detection
    await self._check_growth_anomalies()
    
    # Persist all actions
    await self._save_pulse(actions)
    
    # Reflexion: cosa e' andato bene/male in questo pulse?
    await self._reflect_on_pulse(actions)
    
    return PulseResult(actions=actions)
```

**Azioni che richiedono conferma Zero (propone via TG):**
- Nuovi indici suggeriti (basati su query pattern da pg_stat_statements)
- Proposta di partitioning per tabelle > 500K righe
- Drop di indici unused (idx_scan = 0 per > 30 giorni)
- Cleanup di orphan records
- Qualsiasi DDL (CREATE/ALTER/DROP TABLE)

### 3.3 Meta-cognizione (settimanale) — La saggezza

Questo ritmo NON gira dentro il backend. Gira sul Pro via OpenClaw cron (domenica ore 16:00 WITA),
usando `claude --print` per analizzare i dati raccolti durante la settimana.

```
Input al LLM:
  - Ultimi 7 giorni di olympus_actions (heartbeat + pulse)
  - Trend metriche: growth rate tabelle, dead tuple patterns, query latency
  - Regole attuali (olympus_rules) e quante volte sono state applicate
  - Skill library: quali skill sono state usate e quanto hanno funzionato
  - Report degli altri agenti (Mata Garuda fitness, RAG Canary quality, System Doctor)

Output dal LLM:
  - Nuove regole o soglie modificate → INSERT/UPDATE olympus_rules
  - Nuove skill estratte dai successi → INSERT olympus_skills  
  - Pattern riconosciuti cross-sistema → INSERT olympus_insights
  - Proposte strutturali per Zero → TG con dettaglio e motivazione
  - Auto-valutazione: "questa settimana ho fatto X bene, Y male, dovrei cambiare Z"
```

Questo e' il Reflexion loop del testo sacro applicato al DB custodian.

---

## 4. SCHEMA DATABASE (tabelle olympus_*)

### 4.1 olympus_heartbeats — Snapshot ogni 5 minuti

```sql
CREATE TABLE olympus_heartbeats (
    id BIGSERIAL PRIMARY KEY,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    pool_size INTEGER,
    pool_idle INTEGER,
    pool_utilization NUMERIC(4,2),
    active_connections INTEGER,
    max_connections INTEGER,
    db_size_bytes BIGINT,
    bloat_top3 JSONB,           -- [{table, dead_tup, dead_pct}, ...]
    long_queries INTEGER,        -- count of queries > 30s
    lock_waits INTEGER,
    alerts_sent INTEGER DEFAULT 0
) PARTITION BY RANGE (recorded_at);

-- Partizioni mensili (l'Olimpo crea automaticamente la prossima)
CREATE TABLE olympus_heartbeats_2026_04 PARTITION OF olympus_heartbeats
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE olympus_heartbeats_default PARTITION OF olympus_heartbeats DEFAULT;

-- BRIN perche' i dati sono naturalmente ordinati per tempo
CREATE INDEX idx_olympus_heartbeats_time ON olympus_heartbeats USING BRIN (recorded_at);

-- Retention: l'Olimpo droppa partizioni > 90 giorni nel pulse
```

### 4.2 olympus_actions — Ogni azione del pulse

```sql
CREATE TABLE olympus_actions (
    id BIGSERIAL PRIMARY KEY,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    rhythm TEXT NOT NULL CHECK (rhythm IN ('heartbeat', 'pulse', 'metacognition')),
    action_type TEXT NOT NULL,   -- vacuum, reindex, cleanup, seq_repair, mv_refresh, propose, alert
    target TEXT,                 -- nome tabella/indice/vista
    detail JSONB,               -- contesto specifico dell'azione
    outcome TEXT CHECK (outcome IN ('success', 'failure', 'skipped', 'proposed')),
    duration_ms INTEGER,
    rule_applied TEXT,           -- quale regola ha triggerato questa azione (FK logica a olympus_rules)
    reflection TEXT              -- auto-riflessione post-azione (Reflexion pattern)
);

CREATE INDEX idx_olympus_actions_type_time ON olympus_actions (action_type, executed_at DESC);
CREATE INDEX idx_olympus_actions_target ON olympus_actions (target, executed_at DESC);
```

### 4.3 olympus_rules — Regole operative evolvibili

```sql
CREATE TABLE olympus_rules (
    id SERIAL PRIMARY KEY,
    rule_name TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL,       -- threshold, schedule, policy, skill
    config JSONB NOT NULL,        -- la regola vera e propria
    source TEXT NOT NULL,         -- 'initial', 'metacognition_2026-04-13', 'zero_manual'
    confidence NUMERIC(3,2) DEFAULT 1.0,  -- quanto l'Olimpo si fida di questa regola
    applied_count INTEGER DEFAULT 0,
    last_applied TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    superseded_by INTEGER REFERENCES olympus_rules(id)  -- per tracciare evoluzione
);

-- Seed iniziale delle regole
INSERT INTO olympus_rules (rule_name, category, config, source) VALUES
('vacuum_dead_pct_threshold', 'threshold', '{"value": 10, "unit": "percent"}', 'initial'),
('audit_retention_days', 'policy', '{"value": 90}', 'initial'),
('heartbeat_interval_seconds', 'schedule', '{"value": 300}', 'initial'),
('pulse_interval_hours', 'schedule', '{"value": 6}', 'initial'),
('connection_alert_pct', 'threshold', '{"value": 70, "unit": "percent"}', 'initial'),
('pool_alert_pct', 'threshold', '{"value": 80, "unit": "percent"}', 'initial'),
('long_query_threshold_seconds', 'threshold', '{"value": 30}', 'initial'),
('growth_anomaly_pct', 'threshold', '{"value": 20, "unit": "percent_weekly"}', 'initial'),
('orphan_auto_cleanup', 'policy', '{"enabled": false, "tables": []}', 'initial'),
('partition_suggest_threshold', 'threshold', '{"value": 500000, "unit": "rows"}', 'initial');
```

### 4.4 olympus_insights — Saggezza accumulata (condivisa con altri agenti)

```sql
CREATE TABLE olympus_insights (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    insight_type TEXT NOT NULL,    -- pattern, correlation, anomaly, recommendation, skill
    title TEXT NOT NULL,
    content TEXT NOT NULL,          -- la saggezza in linguaggio naturale
    evidence JSONB,                 -- dati che supportano l'insight
    source TEXT NOT NULL,           -- 'pulse_2026-04-10', 'metacognition_2026-04-13', 'council_2026-04-13'
    confidence NUMERIC(3,2),
    applicable_to TEXT[],           -- ['olympus', 'rag_canary', 'mata_garuda', 'system_doctor']
    accessed_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMPTZ,
    superseded_by INTEGER REFERENCES olympus_insights(id)
);

CREATE INDEX idx_olympus_insights_type ON olympus_insights (insight_type);
CREATE INDEX idx_olympus_insights_applicable ON olympus_insights USING GIN (applicable_to);
```

### 4.5 olympus_skills — Procedure riusabili (Voyager pattern)

```sql
CREATE TABLE olympus_skills (
    id SERIAL PRIMARY KEY,
    skill_name TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL,
    sql_template TEXT NOT NULL,     -- il SQL parametrizzato da eseguire
    parameters JSONB,               -- parametri attesi con default
    preconditions TEXT[],           -- condizioni che devono essere vere prima di eseguire
    success_criteria TEXT,          -- come verificare che la skill ha funzionato
    times_used INTEGER DEFAULT 0,
    times_succeeded INTEGER DEFAULT 0,
    last_used TIMESTAMPTZ,
    learned_from TEXT,              -- 'pulse_2026-04-10_action_42' — traccia l'origine
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.6 Riuso guardian_* esistenti

Le tabelle `guardian_decisions` (717 righe) e `guardian_risk_scores` (4 righe) restano.
L'Olimpo le legge come fonte storica durante la meta-cognizione ma non ci scrive.
La migrazione verso le tabelle `olympus_*` e' un'evoluzione, non una sostituzione.

---

## 5. CRESCITA REALE — Il Reflexion Loop

Il cuore dell'Olimpo non e' il codice — e' il **loop di apprendimento** che chiude il cerchio
tra azione, osservazione, riflessione, e cambiamento di comportamento.

### 5.1 Riflessione post-azione (dopo ogni pulse)

Dopo ogni pulse, l'Olimpo non salva solo "ho fatto VACUUM su X". Salva anche:

```python
async def _reflect_on_pulse(self, actions: list[Action]) -> None:
    """Reflexion pattern: auto-riflessione dopo ogni pulse."""
    # Costruisci contesto per la riflessione
    context = {
        "actions": [a.dict() for a in actions],
        "rules_applied": [a.rule_applied for a in actions if a.rule_applied],
        "failures": [a for a in actions if a.outcome == "failure"],
        "anomalies": [a for a in actions if a.action_type == "anomaly_detected"],
    }
    
    # Riflessione locale (senza LLM, pattern-based)
    for action in actions:
        if action.outcome == "failure":
            # Incrementa contatore fallimenti per questa regola
            await self._record_rule_failure(action.rule_applied)
            # Se una regola fallisce 3 volte di fila, abbassa confidence
            if await self._consecutive_failures(action.rule_applied) >= 3:
                await self._lower_rule_confidence(action.rule_applied, delta=-0.1)
                await self.alert(
                    f"Rule '{action.rule_applied}' failed 3x consecutively. "
                    f"Confidence lowered. Review recommended."
                )
    
    # Salva riflessione come action
    await self._save_action(Action(
        rhythm="pulse",
        action_type="reflection",
        detail=context,
        outcome="success",
        reflection=f"Pulse completed: {len(actions)} actions, "
                   f"{sum(1 for a in actions if a.outcome == 'failure')} failures"
    ))
```

### 5.2 Meta-cognizione settimanale (LLM-powered)

Script eseguito via OpenClaw cron sul Pro:

```python
# scripts/olympus_metacognition.py
# Eseguito: domenica 16:00 WITA via OpenClaw cron

async def weekly_metacognition():
    """L'Oracolo pensa."""
    
    # 1. Raccogli dati della settimana
    actions = await fetch_week_actions()       # olympus_actions ultimi 7 giorni
    heartbeats = await fetch_week_heartbeats() # trend metriche
    rules = await fetch_current_rules()        # olympus_rules attuali
    skills = await fetch_skills_usage()        # quali skill usate e con che successo
    
    # 2. Raccogli dati degli altri agenti
    garuda_fitness = read_file("feedback/fitness.jsonl")  # Mata Garuda
    canary_report = await fetch_canary_metrics()           # RAG Canary (da Redis o DB)
    doctor_report = read_latest("~/logs/system-doctor.log") # System Doctor
    
    # 3. Chiedi al LLM di riflettere
    prompt = f"""
    Sei l'Oracolo dell'Olimpo. Analizzi lo stato del database Nuzantara e del sistema.
    
    AZIONI OLIMPO (ultimi 7 giorni): {json.dumps(actions_summary)}
    TREND METRICHE: {json.dumps(heartbeat_trends)}
    REGOLE ATTUALI: {json.dumps(rules)}
    SKILL USATE: {json.dumps(skills)}
    MATA GARUDA FITNESS: {garuda_fitness[-20:]}
    RAG CANARY: {canary_summary}
    SYSTEM DOCTOR: {doctor_summary}
    
    Rispondi in JSON con:
    1. "rule_updates": regole da modificare (soglie, policy) con motivazione
    2. "new_skills": nuove procedure apprese dai successi della settimana
    3. "cross_insights": correlazioni tra Olimpo e gli altri agenti
    4. "proposals_for_zero": azioni strutturali che richiedono conferma umana
    5. "self_evaluation": cosa ha funzionato, cosa no, cosa cambiare
    """
    
    result = subprocess.run(
        ["claude", "--print", "-p", prompt],
        capture_output=True, text=True
    )
    
    response = json.loads(result.stdout)
    
    # 4. Applica rule_updates
    for update in response["rule_updates"]:
        await apply_rule_update(update)
    
    # 5. Salva new_skills
    for skill in response["new_skills"]:
        await save_skill(skill)
    
    # 6. Salva cross_insights (accessibili a tutti gli agenti)
    for insight in response["cross_insights"]:
        await save_insight(insight)
    
    # 7. Manda proposte a Zero via TG
    if response["proposals_for_zero"]:
        await send_tg(format_proposals(response["proposals_for_zero"]))
    
    # 8. Salva auto-valutazione
    await save_action(Action(
        rhythm="metacognition",
        action_type="self_evaluation",
        detail=response["self_evaluation"]
    ))
```

### 5.3 Come cresce concretamente

Settimana 1: L'Olimpo fa VACUUM su `api_audit_trail` ogni 6h perche' la regola dice
`vacuum_dead_pct_threshold = 10%`. Funziona.

Settimana 2: Stesso pattern. Sempre VACUUM ogni 6h.

Settimana 3: La meta-cognizione nota: "api_audit_trail richiede VACUUM ad OGNI pulse.
La tabella cresce di 30K righe/giorno. VACUUM non basta — serve partitioning."
→ Propone a Zero: "Partitioning mensile per api_audit_trail. Attuale: 870K righe, 240MB.
Con partitioning: cleanup via DROP PARTITION invece di DELETE."
→ Salva insight: "Tabelle con growth > 5K righe/giorno beneficiano di partitioning, non solo VACUUM."
→ Salva skill: "partition_table_monthly" con il SQL template parametrizzato.

Settimana 4: Zero approva. L'Olimpo applica la skill. Da ora in poi il pulse fa
DROP PARTITION per cleanup invece di DELETE.

Settimana 5: La meta-cognizione nota: "Da quando api_audit_trail e' partizionata,
il VACUUM su quella tabella non serve piu'. Disabilito la regola per quella tabella."
→ Aggiorna regola: `vacuum_exclusions: ["api_audit_trail"]`

**Questo e' crescita.** Non accumulo di righe — cambiamento di comportamento.

---

## 6. CONDIVISIONE E CONFRONTO

### 6.1 Redis come bus nervoso

```python
# Pubblica insight in real-time quando l'Olimpo scopre qualcosa di significativo
await redis.xadd("olympus:insights", {
    "type": "anomaly",
    "title": "kg_edges growth 40% in 7 days",
    "detail": "252K -> 353K edges. Correlate with Mata Garuda harvest?",
    "confidence": "0.8",
    "timestamp": datetime.utcnow().isoformat()
})
```

Stream Redis:
- `olympus:insights` — l'Olimpo pubblica scoperte, pattern, anomalie
- `olympus:proposals` — proposte strutturali in attesa di conferma Zero
- `olympus:heartbeat` — ultimo heartbeat (consumabile da /health endpoint)

Chi consuma:
- RAG Canary puo' leggere `olympus:insights` per correlare latenze query con stato DB
- System Doctor puo' leggere per correlare salute infra con salute DB
- `/health/db` endpoint legge `olympus:heartbeat` per dashboard

### 6.2 olympus_insights come memoria condivisa

Qualsiasi agente o servizio puo' query-are:

```sql
-- Cosa sa l'Olimpo su kg_edges?
SELECT title, content, confidence, created_at 
FROM olympus_insights 
WHERE 'mata_garuda' = ANY(applicable_to)
AND content ILIKE '%kg_edges%'
ORDER BY created_at DESC LIMIT 5;
```

### 6.3 Consiglio dell'Olimpo (settimanale)

Script eseguito via OpenClaw cron sul Pro, subito DOPO la meta-cognizione:

```python
# scripts/olympus_council.py
# Eseguito: domenica 17:00 WITA (1h dopo la meta-cognizione)

async def weekly_council():
    """Il Consiglio dell'Olimpo: confronto inter-agente."""
    
    # Raccogli i report di tutti gli agenti
    olympus_report = await fetch_metacognition_report()  # appena generato
    garuda_report = await fetch_garuda_weekly()           # fitness + mutazioni
    canary_report = await fetch_canary_weekly()           # qualita' RAG
    doctor_report = await fetch_doctor_weekly()           # salute infra
    
    prompt = f"""
    Sei il Moderatore del Consiglio dell'Olimpo. Hai davanti i report settimanali
    di 4 custodi del sistema Nuzantara. Il tuo compito e':
    
    1. Identificare CONTRADDIZIONI tra i report
       (es. Olimpo dice "DB sano" ma RAG Canary dice "query lente")
    2. Identificare CORRELAZIONI che nessun singolo agente vede
       (es. harvest Garuda -> crescita KG -> degrado RAG)
    3. Produrre DECISIONI CONSENSUALI
       (es. "prima del prossimo harvest, Olimpo faccia VACUUM preventivo")
    4. Assegnare COMPITI incrociati
       (es. "Garuda notifichi Olimpo 1h prima di ogni harvest massiccio")
    
    OLIMPO (DB Guardian): {olympus_report}
    MATA GARUDA (Intel): {garuda_report}
    RAG CANARY (Quality): {canary_report}
    SYSTEM DOCTOR (Infra): {doctor_report}
    
    Rispondi in JSON:
    - contradictions: [...]
    - correlations: [...]
    - decisions: [...]
    - cross_tasks: [{{from: "agent", to: "agent", task: "..."}}]
    - escalations_to_zero: [...]  (solo se serve decisione umana)
    """
    
    result = subprocess.run(
        ["claude", "--print", "-p", prompt], capture_output=True, text=True
    )
    council_output = json.loads(result.stdout)
    
    # Salva decisioni come insight condivisi
    for decision in council_output["decisions"]:
        await save_insight(decision, source="council", applicable_to=["all"])
    
    # Pubblica cross-tasks su Redis per gli agenti destinatari
    for task in council_output["cross_tasks"]:
        await redis.xadd(f"{task['to']}:tasks", task)
    
    # Report a Zero via TG
    await send_tg(format_council_summary(council_output))
```

---

## 7. AZIONI PRIORITARIE DEL PRIMO PULSE

Dall'audit emergono problemi reali da risolvere subito. L'Olimpo al primo avvio:

### 7.1 Allineamento locale <-> Fly (55 tabelle mancanti)

L'Olimpo non allinea il DB locale — quello e' compito delle migration.
Ma l'Olimpo **monitora** la divergenza e allerta se il locale non e' in sync.

### 7.2 Indici mancanti critici

```sql
-- conversations.session_id: chiave lookup primaria, NESSUN INDICE
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conversations_session_id 
    ON conversations (session_id);

-- practices.assigned_to: filtro RBAC su ogni query
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_practices_assigned_to 
    ON practices (assigned_to) WHERE assigned_to IS NOT NULL;

-- practices.client_id: join frequentissimo
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_practices_client_id 
    ON practices (client_id);
```

### 7.3 Materialized views per dashboard

```sql
CREATE MATERIALIZED VIEW mv_api_usage_daily AS
SELECT endpoint, method, COUNT(*) as requests,
       AVG(response_time_ms)::INTEGER as avg_ms,
       PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms)::INTEGER as p95_ms,
       COUNT(CASE WHEN response_status >= 500 THEN 1 END) as errors,
       DATE(created_at) as date
FROM api_audit_trail
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY endpoint, method, DATE(created_at);

CREATE UNIQUE INDEX ON mv_api_usage_daily (endpoint, method, date);

CREATE MATERIALIZED VIEW mv_kg_stats AS
SELECT 'nodes' as category, entity_type as type, COUNT(*) as count,
       AVG(confidence)::NUMERIC(4,2) as avg_confidence
FROM kg_nodes GROUP BY entity_type
UNION ALL
SELECT 'edges', relationship_type, COUNT(*), AVG(confidence)::NUMERIC(4,2)
FROM kg_edges GROUP BY relationship_type;

CREATE UNIQUE INDEX ON mv_kg_stats (category, type);

CREATE MATERIALIZED VIEW mv_client_activity AS
SELECT c.id, c.name, c.status,
       COUNT(DISTINCT p.id) as practices,
       COUNT(DISTINCT i.id) as interactions,
       MAX(i.created_at) as last_interaction
FROM clients c
LEFT JOIN practices p ON p.client_id = c.id
LEFT JOIN interactions i ON i.client_id = c.id
GROUP BY c.id, c.name, c.status;

CREATE UNIQUE INDEX ON mv_client_activity (id);
```

### 7.4 Pool consolidation (proposta)

Eliminare i pool indipendenti in `audit_service.py`, `golden_router_service.py`, 
`legal_ingestion_service.py`, `pipeline.py`. Tutti devono usare `app.state.db_pool`.
Questo e' un refactor multi-file — l'Olimpo lo propone, non lo esegue.

### 7.5 Partitioning api_audit_trail (proposta)

870K righe, 240MB, cresce ~30K/giorno. Partitioning mensile con auto-creation.
L'Olimpo propone il piano, Zero approva, l'Olimpo esegue.

---

## 8. INTEGRAZIONE CON L'ECOSISTEMA

### 8.1 Nel backend (service_initializer.py)

```python
# In initialize_database_services()
from backend.services.olympus.guardian import OlympusGuardian

olympus = OlympusGuardian(db_pool=app.state.db_pool, redis=app.state.redis)
await olympus.initialize()  # Crea tabelle se non esistono, carica regole
app.state.olympus = olympus

# Background task
asyncio.create_task(olympus.run_forever())  # Multi-ritmo loop
```

### 8.2 Endpoint /health/db

```python
@router.get("/health/db")
async def db_health(olympus: OlympusGuardian = Depends(get_olympus)):
    return await olympus.get_health_summary()
    # Ritorna: ultimo heartbeat, azioni recenti, regole attive, alert aperti
```

### 8.3 Endpoint /internal/olympus/propose (per conferma azioni)

```python
@router.post("/internal/olympus/propose/{action_id}/approve")
async def approve_proposal(action_id: int, olympus = Depends(get_olympus)):
    """Zero approva una proposta dell'Olimpo via TG deeplink."""
    return await olympus.execute_approved_proposal(action_id)
```

### 8.4 Cron sul Pro (OpenClaw)

```
Domenica 16:00 WITA → scripts/olympus_metacognition.py   (meta-cognizione)
Domenica 17:00 WITA → scripts/olympus_council.py         (Consiglio dell'Olimpo)
```

---

## 9. SYMBIOSIS ARCHITECTURE UPDATE

La SYMBIOSIS_ARCHITECTURE.md (Mata Garuda <-> Nexus) va aggiornata per includere l'Olimpo.

### Nuovo stream Redis

| Stream | Direzione | Contenuto |
|---|---|---|
| `olympus:insights` | Olimpo → tutti | Pattern, anomalie, correlazioni DB |
| `olympus:proposals` | Olimpo → Zero TG | Proposte strutturali |
| `olympus:heartbeat` | Olimpo → /health | Ultimo snapshot metriche |

### Nuovo nodo nell'architettura

```
                    ┌──────────────┐
                    │    OLIMPO    │ ← dentro nuzantara-rag
                    │  (DB Guard)  │
                    └──────┬───────┘
                           │ olympus:insights
          ┌────────────────┼────────────────────┐
          ↓                ↓                     ↓
   ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐
   │ MATA GARUDA  │ │  RAG CANARY  │ │  SYSTEM DOCTOR   │
   └──────┬───────┘ └──────────────┘ └──────────────────┘
          │ garuda:raw
          ↓
   ┌──────────────┐
   │  NEXUS/Neo4j │ ← OSINT graph
   └──────────────┘
```

### Interazione Olimpo <-> Mata Garuda

Quando Mata Garuda sta per lanciare un harvest massiccio (es. 50K regolazioni JDIH),
pubblica un avviso su `garuda:pre_harvest`. L'Olimpo:
1. Fa VACUUM preventivo su kg_nodes e kg_edges
2. Alza temporaneamente la soglia di growth anomaly per quelle tabelle
3. Dopo il harvest, verifica integrita' e ripristina soglie normali

### Interazione Olimpo <-> RAG Canary

Se il RAG Canary rileva degrado qualita' (confidence drop), query-a `olympus_insights`:
"c'e' stato un problema DB questa settimana?" L'Olimpo potrebbe rispondere:
"si, dead tuple spike su query_analytics giovedi'" — correlazione trovata.

---

## 10. COSA NON FARE

1. **NON installare pg_cron** — richiede custom Dockerfile Fly. L'app-level scheduling basta.
2. **NON aggiungere pgvector** — 2GB non regge 93K vettori. Qdrant e' gia' in produzione.
3. **NON usare PgBouncer** — asyncpg pool basta. Consolidare i pool esistenti e' sufficiente.
4. **NON dare all'Olimpo accesso DDL autonomo** — solo DML autonomo, DDL via proposta.
5. **NON partire con la meta-cognizione** — prima il heartbeat e il pulse devono funzionare.
6. **NON duplicare health_monitor.py** — l'Olimpo lo assorbe e lo estende.
7. **NON fare l'Olimpo stateless** — le tabelle olympus_* sono il suo cervello.
8. **NON ignorare guardian_decisions** — 717 righe di storia. Leggere, non sovrascrivere.

---

## 11. FASI DI IMPLEMENTAZIONE

### Fase 1: Fondamenta (2-3 giorni)
- Migration: crea tabelle olympus_* + materialized views + indici mancanti
- `guardian.py` + `heartbeat.py`: multi-ritmo loop base
- `rules_engine.py`: lettura regole da DB
- Integrazione in `service_initializer.py`
- `/health/db` endpoint
- Test: heartbeat gira, metriche raccolte, alert TG funziona

### Fase 2: Manutenzione autonoma (2 giorni)
- `pulse.py`: VACUUM, cleanup, seq repair, mv refresh, orphan detection
- `alerts.py`: integrazione TG per proposte
- `models.py`: Pydantic models
- Assorbi logica di `health_monitor.py` (evita duplicazione)
- Test: pulse esegue azioni, registra in olympus_actions

### Fase 3: Reflexion loop (1-2 giorni)
- Riflessione post-pulse (pattern-based, senza LLM)
- Rule confidence decay su fallimenti ripetuti
- Skill extraction: quando un'azione funziona, salva come skill riusabile
- Test: regole evolvono, skill library cresce

### Fase 4: Meta-cognizione (1-2 giorni)
- `scripts/olympus_metacognition.py` (Pro, claude --print)
- Cron OpenClaw domenica 16:00 WITA
- Rule updates automatici, insight cross-sistema
- Test: meta-cognizione produce output, regole aggiornate

### Fase 5: Consiglio dell'Olimpo (1 giorno)
- `scripts/olympus_council.py` (Pro, claude --print)
- Raccolta report multi-agente
- Sintesi cross-sistema, cross-tasks
- Test: council produce decisioni, cross-tasks pubblicati

### Fase 6: Azioni strutturali (ongoing)
- Partitioning api_audit_trail
- Pool consolidation
- Indici suggeriti dalla meta-cognizione
- Evoluzione guidata dai dati

**Totale: ~8-10 giorni per organismo funzionante. Poi cresce da solo.**

---

## APPENDICE A: AUDIT FINDINGS (da risolvere)

### Tabelle mancanti su locale (55)

```
ab_test_metrics, ab_test_summaries, analytics_map_lookups, api_audit_trail,
attendance_late_incidents, bali_coastline, bali_zoning_layers,
cell_critic_expectations, cell_critiques, cell_curiosity_findings, cell_goals,
cell_mutations, cell_skill_audit, cell_skills, client_drive_subfolders,
clients_archive, conversation_messages, conversation_threads, failed_messages,
federation_messages, geocoding_jobs, guardian_decisions, guardian_risk_scores,
hr_bonus_ledger, hr_bonus_rates, hr_deductions, hr_employees, hr_leave_balances,
hr_leave_requests, hr_leave_types, hr_payroll_periods, hr_payslips, invoices,
kg_communities, kg_edges_staging, kg_entity_mentions, kg_node_community,
kg_nodes_staging, legal_instruments, lkpm_client_config, lkpm_reports,
master_building_codes, migration_history, naga_claim_evidence,
naga_claim_transitions, naga_claims, naga_sessions, naga_sources,
notification_alerts, post_publish_queue, prime_proposals, spatial_ref_sys,
system_settings, welcome_email_queue, workflow_jobs
```

### Tabelle locali obsolete (3)
`generals_activity`, `generals_memory`, `generals_tasks` — non su Fly, nessun codice le referenzia.

### Dual-writer conflict
`query_analytics`: asyncpg (QueryAnalyticsRepository, user_id=NULL) vs SQLAlchemy (oracle_database.py, user_id=UUID).

### Missing FK
- `lkpm_client_config.client_id` → no FK to clients
- `conversation_messages.client_id` → no FK to clients
- `knowledge_activity_log.user_email` → no FK

### Migration system duplicato
3 tracking tables: `schema_migrations`, `_schema_versions`, `migration_history`.
`migrations_v2/` directory vuota — il loader automatico non ha nulla da applicare.

### Pool proliferation
Pools indipendenti in: audit_service.py, golden_router_service.py, legal_ingestion_service.py, pipeline.py.
Rischio: superamento max_connections con 2 worker API + 1 worker RAG + pool multipli.
