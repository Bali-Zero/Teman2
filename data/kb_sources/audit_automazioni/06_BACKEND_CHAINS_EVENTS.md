# Prompt 6/8: Audit Workflow Chains, Event Handlers, Pipelines

**Macchina:** Pro (codice) / Fly.io (runtime)
**Scope:** 8 chains + 5 event handlers + 7 pipelines + 4 LangGraph agents
**Durata stimata:** 25-30 minuti
**Rischio:** BASSO (solo analisi)

---

## MISSIONE

Verifica che tutti i componenti "reactive" del backend funzionino. Questi NON sono scheduled — si attivano su evento o su chiamata. L'obiettivo è capire cosa funziona, cosa è morto, e cosa è ridondante.

## 1. WORKFLOW CHAINS (8)

Tutti definiti in `apps/nuzantara-mcp/`. Cerca i file:

```bash
# Trova tutti i file chain
find apps/nuzantara-mcp/ -name "*.py" | xargs grep -l "def chain_" 2>/dev/null
```

Per ogni chain, verifica:

| Chain                          | File | Chiamante            | Test                                                                              |
| ------------------------------ | ---- | -------------------- | --------------------------------------------------------------------------------- |
| chain_daily_ops_autopilot      | ?    | OpenClaw cron        | `mcporter call nuzantara-mcp.chain_daily_ops_autopilot --dry-run` (se supportato) |
| chain_new_client_onboarding    | ?    | DB trigger / manuale | Quando è stata l'ultima onboarding?                                               |
| chain_practice_lifecycle_check | ?    | OpenClaw cron        | OK (gira ogni 6h)                                                                 |
| chain_intel_pipeline           | ?    | Manuale / cron       | Ultimo articolo prodotto?                                                         |
| chain_weekly_report            | ?    | OpenClaw cron        | OK (gira lunedì)                                                                  |
| chain_client_health_monitor    | ?    | OpenClaw cron        | OK (gira 14:00)                                                                   |
| chain_compliance_autopilot     | ?    | OpenClaw cron        | OK (gira ogni 6h)                                                                 |
| chain_journey_accelerator      | ?    | Manuale solo         | Mai usata in produzione?                                                          |

**Domande chiave:**

- `chain_new_client_onboarding`: si attiva automaticamente quando un client viene creato? O serve trigger manuale?
- `chain_intel_pipeline`: è il SOLO pipeline per articoli? O c'è anche il LaunchAgent `intel.nightly` su Pro?
- `chain_journey_accelerator`: qualcuno l'ha mai invocata? O è solo definita?

## 2. EVENT HANDLERS (5)

### Webhook Handlers

```bash
cat apps/backend-rag/backend/app/routers/telegram.py | head -50
cat apps/backend-rag/backend/app/routers/instagram.py | head -50
cat apps/backend-rag/backend/app/routers/twitter.py | head -50
```

| Handler   | Endpoint                 | Verifiche                                       |
| --------- | ------------------------ | ----------------------------------------------- |
| Telegram  | POST /webhooks/telegram  | Funziona? Controlla log recenti su Fly.io       |
| Instagram | POST /webhooks/instagram | Meta webhook attivo? Ultimo messaggio ricevuto? |
| Twitter/X | POST /webhooks/twitter   | Twitter webhook attivo? O è legacy?             |

**Per Instagram e Twitter:**

- Sono REALMENTE configurati con i rispettivi webhook di Meta/X?
- O sono solo endpoint nel codice senza webhook registrato?
- Se non c'è webhook registrato → sono codice morto

### DB Triggers

```bash
cat apps/backend-rag/backend/db/triggers.py 2>/dev/null || echo "File non trovato"
# Se non esiste, cerca altrove:
find apps/backend-rag/ -name "triggers*" -o -name "*trigger*" | head -10
```

Verifica:

- I trigger sono registrati nel DB PostgreSQL? O sono solo Python code?
- `on_client_created` → crea davvero cartella Drive? Controlla con un client recente
- `on_practice_created` → genera davvero fattura? Controlla
- `on_document_uploaded` → indicizza in Qdrant? Controlla

### Google Drive Poll

```bash
grep -r "drive_changes_poll\|changes_poll\|drive.*poll" apps/backend-rag/backend/ --include="*.py" -l
```

- Ogni 5 min controlla nuovi file → auto-index
- **Ma con auto_stop su Fly.io, NON gira.** È morto in produzione?

## 3. PIPELINE PROCESSORS (7)

| Pipeline              | File                                          | Stato        | Verifica                         |
| --------------------- | --------------------------------------------- | ------------ | -------------------------------- |
| Bali Intel Scraper    | apps/bali-intel-scraper/                      | Pro locale   | LaunchAgent 01:00                |
| Article Composer      | backend/services/content/article_composer.py  | Fly.io       | Ultimo articolo composto?        |
| GEO/SEO Optimizer     | In scraper pipeline                           | Pro locale   | Integrato nel scraper            |
| Search Index Pipeline | backend/services/search/indexing.py           | Fly.io       | Ultimo batch indicizzato?        |
| Conversation Cleanup  | backend/services/misc/conversation_cleanup.py | Fly.io       | Scheduled (morto con auto_stop?) |
| Drive Changes Poll    | backend/services/integrations/google_drive.py | Fly.io       | Scheduled (morto con auto_stop?) |
| KG Legal Extraction   | Pro locale                                    | Parziale 38% | `sync_legal_hybrid_only.sh`      |

Per ogni pipeline, controlla:

```bash
# File esiste?
ls -la apps/backend-rag/backend/services/content/article_composer.py 2>/dev/null
ls -la apps/backend-rag/backend/services/search/indexing.py 2>/dev/null
ls -la apps/backend-rag/backend/services/misc/conversation_cleanup.py 2>/dev/null
```

## 4. LANGGRAPH REASONING AGENTS (4)

```bash
cat apps/backend-rag/backend/services/rag/kg_langgraph.py | head -80
```

Verifica:

- I 4 subgraph sono tutti importati e usati?
- Chi li invoca? (Il RAG query engine? Un router specifico?)
- Confidence scoring funziona? (ABSTAIN < 0.15, CAUTIOUS 0.15-0.60, NORMAL > 0.60)
- Quante query usano i subgraph al giorno?

## OUTPUT RICHIESTO

### Tabella Riassuntiva

| Componente        | Tipo     | Dove Gira | Attivo? | Morto con auto_stop? | Overlap        | Decisione |
| ----------------- | -------- | --------- | ------- | -------------------- | -------------- | --------- |
| chain_daily_ops   | Chain    | MCP       | ✅      | N/A (OpenClaw)       | Scheduler task | ?         |
| chain_new_client  | Chain    | MCP       | ?       | N/A (evento)         | —              | ?         |
| Telegram webhook  | Event    | Fly.io    | ✅      | ✅ (sveglia app)     | —              | KEEP      |
| Instagram webhook | Event    | Fly.io    | ?       | ?                    | —              | ?         |
| Twitter webhook   | Event    | Fly.io    | ?       | ?                    | —              | ?         |
| DB triggers       | Event    | Fly.io    | ?       | —                    | —              | ?         |
| Drive poll        | Pipeline | Fly.io    | ❌      | ❌ (morto)           | —              | ?         |
| Article Composer  | Pipeline | Fly.io    | ?       | —                    | —              | ?         |
| ...               |          |           |         |                      |                |           |

### Raccomandazione

Rispondi a: **Quanti di questi componenti sono effettivamente morti a causa di auto_stop?**
E proponi: migrare a OpenClaw cron vs. disabilitare auto_stop vs. keep-alive ping.
