# Prompt 5/8: Audit Agenti Autonomi Backend

**Macchina:** Pro (codice locale) / Fly.io (runtime produzione)
**Scope:** 4 agenti Tier-1 + 12 scheduled task (AutonomousScheduler)
**Durata stimata:** 25-30 minuti
**Rischio:** BASSO (solo analisi codice, nessuna modifica produzione)

---

## MISSIONE

Verifica che gli agenti autonomi e lo scheduler siano realmente funzionanti e non solo "definiti nel codice". Per ognuno:

1. Il codice esiste e non ha errori di importazione
2. Lo scheduler lo lancia effettivamente (controlla log)
3. Produce risultati osservabili (DB entries, file, notifiche)
4. Non è ridondante con OpenClaw cron o LaunchAgents

## FILE DA ANALIZZARE

### AutonomousScheduler (il cuore)

```bash
cat apps/backend-rag/backend/services/misc/autonomous_scheduler.py
```

Cerca:

- Lista completa dei task registrati
- Intervalli configurati
- Meccanismo di leader election Redis
- Cosa succede se il backend è in cold start (auto_stop=true su Fly.io)?
- **CRITICO:** Se Fly.io spegne l'app dopo inattività, lo scheduler si ferma. Chi lo risveglia?

### Agenti Tier-1

1. **ConversationTrainer**

```bash
cat apps/backend-rag/backend/services/misc/conversation_trainer.py
```

- Analizza conversazioni → genera prompt migliorati → crea PR
- **Verifica:** Ha mai creato un PR? `cd ~/Desktop/nuzantara && git log --all --grep="conversation" --grep="trainer" --oneline | head -10`
- Dipendenze: serve accesso a GitHub API per creare PR?

2. **ClientValuePredictor**

```bash
cat apps/backend-rag/backend/services/misc/client_value_predictor.py
```

- Scoring LTV → identifica VIP/at-risk → WhatsApp nurturing
- **Verifica:** Manda davvero messaggi WhatsApp? O solo log?
- **Rischio:** Se manda messaggi automatici a clienti, serve controllo qualità

3. **KnowledgeGraphBuilder**

```bash
cat apps/backend-rag/backend/services/rag/kg_builder.py
```

- Ingestion documenti legali → entity extraction → KG
- **Stato noto:** 38% completato (11,490/30,065 documenti)
- **Verifica:** È ancora in esecuzione o si è fermato?

4. **SEO Guardian**

```bash
# Potrebbe essere in evaluator, non in backend
ls apps/evaluator/seo_guardian*.py
cat apps/evaluator/seo_guardian_agent.py | head -100
```

- Audit GEO/AEO, llms.txt, coverage AI SEO
- **Verifica:** Produce output in `~/.openclaw/workspace/autonomous/seo-guardian/`

### Scheduled Task individuali

Per ognuno dei 12 task dello scheduler, verifica:

| Task                   | Intervallo | Cosa Fa                       | Come Verificare                    |
| ---------------------- | ---------- | ----------------------------- | ---------------------------------- |
| auto_ingestion         | 24h        | Ingest nuovi doc in KG        | Check log, count KG nodes          |
| self_healing           | 5min       | Health check servizi          | Check log, recovery actions        |
| conversation_trainer   | 6h         | Analisi conversazioni         | Check PR creati                    |
| client_value_predictor | 12h        | Scoring clienti               | Check DB client scores             |
| renewal_alerts         | 12h        | Alert scadenze visa/licenze   | Check notifiche inviate            |
| birthplace_enrichment  | 24h        | Arricchimento dati nascita    | Check DB updates                   |
| birthday_notifier      | 24h        | Auguri compleanno             | Check notifiche                    |
| conversation_cleanup   | 24h        | Pulizia conversazioni vecchie | Check DB count prima/dopo          |
| daily_ops_autopilot    | 24h        | Daily ops chain               | Check → overlap con OpenClaw cron! |
| drive_changes_poll     | 5min       | Poll Google Drive changes     | Check log                          |
| weekly_report          | 7d         | Report settimanale            | Check → overlap con OpenClaw cron! |
| weekly_dep_audit       | 7d         | Audit dipendenze              | Check → overlap con OpenClaw cron! |

## OVERLAP CRITICO

Questi task dello scheduler hanno un OpenClaw cron equivalente:

| Scheduler Task      | OpenClaw Cron       | Chi vince?                    |
| ------------------- | ------------------- | ----------------------------- |
| daily_ops_autopilot | daily-ops-autopilot | Probabilmente ENTRAMBI girano |
| weekly_report       | weekly-report       | Probabilmente ENTRAMBI girano |
| weekly_dep_audit    | weekly-dep-audit    | OpenClaw non ha mai eseguito  |

**Domanda:** Se il backend Fly.io è in auto_stop e lo scheduler non gira, solo OpenClaw funziona. Ma se il backend è attivo, ENTRAMBI girano → duplicazione?

Proponi una strategia chiara: chi è il master per ogni task?

## ANALISI RUNTIME

Il backend Fly.io ha `auto_stop=true, min_machines=0`. Questo significa:

- Dopo ~5 min di inattività → app si spegne
- Lo scheduler si ferma
- Scheduled task NON girano finché qualcuno non chiama il backend

**Implicazione:** Lo scheduler è affidabile SOLO se il backend è sempre attivo. Con auto_stop, i task scheduled sono de facto MORTI tra una richiesta e l'altra.

**Verifica:** Quanto tempo il backend resta attivo mediamente? Controlla:

```bash
# Log Fly.io
fly logs --app nuzantara-rag --no-tail | grep -i "starting\|stopping\|shutdown" | tail -20
```

## OUTPUT RICHIESTO

### Tabella Agenti

| Agente                | Codice OK | Ultimo Run | Output Verificabile | Overlap       | Decisione |
| --------------------- | --------- | ---------- | ------------------- | ------------- | --------- |
| ConversationTrainer   | ?         | ?          | ? PR creati?        | —             | ?         |
| ClientValuePredictor  | ?         | ?          | ? msg inviati?      | —             | ?         |
| KnowledgeGraphBuilder | ?         | ?          | 38%?                | —             | ?         |
| SEO Guardian          | ?         | ?          | state.json?         | OpenClaw cron | ?         |

### Tabella Scheduled Tasks

| Task           | Gira su Fly.io? | Gira con auto_stop? | Overlap OpenClaw  | Decisione |
| -------------- | --------------- | ------------------- | ----------------- | --------- |
| auto_ingestion | ?               | NO (spento)         | —                 | ?         |
| self_healing   | ?               | NO (spento)         | health-check cron | ?         |
| ...            |                 |                     |                   |           |

### Raccomandazione Strategica

Rispondi a: **Lo AutonomousScheduler ha senso con auto_stop=true?**

- Se NO → tutti i task scheduled dovrebbero migrare a OpenClaw cron
- Se SÌ → come garantire che il backend resti attivo per lo scheduler?
