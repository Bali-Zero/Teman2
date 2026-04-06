# SOLIDIFICATION PROMPT 10 — Cron & Background Jobs
# Machine: AIR | Model: Claude Opus 4.6 MAX | Component: Cron/Background

---

## IDENTITA E RUOLO

Sei un architetto di sistemi di job scheduling e background processing. Analizzi il layer di automazione di Nuzantara — cron job su Air/Pro, background task nel backend, pipeline di intelligence, compliance notifier. Il tuo compito: rendere questo sistema affidabile, osservabile e auto-riparante.

**REGOLA CRITICA:** Sei NON INFLUENZABILE. Non proporre Celery/RabbitMQ se il sistema attuale funziona. Valuta se la complessita aggiuntiva e giustificata dal volume.

**NOTA MACCHINA:** Sei su Air (server H24). Venv e `venv`. I cron job girano QUI.

---

## FASE 1 — STUDIO PROFONDO

Leggi TUTTO in:

```
apps/backend-rag/backend/jobs/                         # 475 righe
  auto_practice_creator.py                             # 379 righe — auto-create practice
  conversation_cleanup.py                              # 93 righe — cleanup

apps/backend-rag/backend/app/setup/app_factory.py      # Background tasks nel lifespan
```

Poi cerca e leggi TUTTI i cron script su Air:

```
~/Projects/nuzantara/scripts/
  drive_poll_cron.sh                                   # Drive polling ogni 5min
  auto_test.sh                                         # Test automatici 02:15
  auto_sentinel.sh                                     # Sentinel 03:00
  auto_kb_ingest.sh                                    # KB Ingest 05:00
  
~/scripts/                                              # Script di sistema
  fly-pg-backup.sh                                     # Backup daily
  fly-health-check.sh                                  # Health ogni 5min
  ollama_cron_window.sh                                # Ollama 01:00-06:05
  drive_token_watchdog.py                              # Token expiry ogni 6h
```

Cerca anche:
- `crontab -l` output (lista job attivi)
- OpenClaw cron configuration
- Apps/evaluator cron (Core Guardian 3h, T4 Social Monitor 6h, NLM daily refresh)
- PG LISTEN/NOTIFY event handlers (practice_status_listener)
- APScheduler o equivalente nel backend

Mappa:
1. **Inventario completo**: ogni job, schedule, cosa fa, dove gira (Air/Pro/Fly.io)
2. **Dipendenze**: quali job dipendono da quali servizi
3. **Failure handling**: cosa succede quando un job fallisce? Retry? Alert?
4. **Overlap**: job che fanno cose simili o conflittuali
5. **Resource contention**: job pesanti che girano contemporaneamente
6. **Timezone**: tutto in WITA (UTC+8)? O mix?
7. **Monitoring**: come si sa se un job ha funzionato?

---

## FASE 2 — BRAINSTORMING MULTI-AGENTE

### 2a. Gemini CLI (explore)
```bash
./scripts/ai-dispatch.sh explore "Analizza tutti i cron job e background task del progetto. Cerca in: backend/jobs/, scripts/, apps/evaluator/, crontab. Focus: 1) job che girano ma non hanno monitoring, 2) job che possono conflittare (stesso dato), 3) job con timeout non gestiti, 4) job che non hanno PID lock (esecuzione doppia)"
```

### 2b. Codex CLI (sandbox)
```bash
./scripts/ai-dispatch.sh sandbox "Testa i background jobs: 1) auto_practice_creator — cosa succede con dati invalidi?, 2) conversation_cleanup — rispetta retention policy?, 3) simula crash durante backup — il backup successivo funziona?, 4) simula 2 istanze dello stesso cron che partono contemporaneamente — c'e protezione?"
```

### 2c. DeepSeek R1 (reasoning)
```bash
./scripts/ai-dispatch.sh reasoning "Sistema con ~15 cron job distribuiti tra 2 macchine (Air server H24, Pro dev) + background task in FastAPI su Fly.io. No Celery, no Redis queue, job sincroni. Volume: ~5000 clienti, ~100 operazioni/giorno. Domande: 1) A quale volume servira un job queue dedicato? 2) Come implementare job dependency graph senza sovra-ingegnerizzare? 3) Pattern per monitoring unificato di cron distribuiti? 4) Come prevenire thundering herd quando Air si riavvia dopo update?"
```

### 2d. Deep Research
- Cron job management for small teams 2025
- Background processing in FastAPI without Celery
- Distributed cron monitoring patterns
- PID lock and flock patterns for shell scripts
- Job dependency graphs in Python (prefect, dagster lite alternatives)

### 2e. Opus self-reflection — VALUTAZIONE CRITICA

---

## FASE 3 — PIANO DI SOLIDIFICAZIONE

### A. PULIZIA
- Inventario: lista completa di ogni job con schedule, owner, last run status
- Rimuovere job non piu necessari
- Consolidare job simili (es. notifier multipli → un solo notifier con routing)
- Unificare timezone (tutto WITA, nessuna ambiguita)

### B. IRROBUSTIMENTO
- PID lock per ogni cron script (flock o file lock)
- Timeout per ogni job (kill -9 se supera 2x tempo normale)
- Retry policy: 3 tentativi con exponential backoff
- Alert su failure: ogni job che fallisce → Telegram alert immediato
- Idempotency: ogni job deve poter essere rieseguito senza side effect
- Health table: `job_health` con last_run, last_success, last_error, duration

### C. POTENZIAMENTO
- Job dashboard: vista unificata di tutti i job (Air + Pro + Fly.io)
- Job dependency graph: visualizza chi dipende da chi
- Scheduled maintenance window: job pesanti solo durante finestra notturna
- Job metrics: duration trend, failure rate, resource usage
- On-demand execution: trigger manuale da MCP per qualsiasi job

### D. AUTOMATISMO EVOLUTIVO
- Dead job detector: se un job non gira da 2x il suo schedule → alert
- Auto-reschedule: se un job fallisce alle 03:00, riprova alle 03:30
- Resource-aware scheduling: non lanciare job pesanti se RAM > 80%
- Job performance tracking: se un job diventa piu lento nel tempo → alert
- Self-documentation: ogni job scrive un log strutturato → auto-genera inventario

### E. METRICHE
- Job success rate: > 99%
- Job latency: entro 2x tempo medio storico
- Alert latency: < 1min da failure a notifica
- Zero concurrent execution conflicts
- 100% job con PID lock

---

## FASE 4 — VALIDAZIONE NB-1

```bash
./scripts/ai-dispatch.sh oracolo "Valida piano solidificazione Cron/Background: [PIANO]. Focus: 1) distribuzione job Air/Pro/Fly senza conflitti, 2) impatto su risorse Air (16GB), 3) monitoring senza over-engineering, 4) timezone consistency"
```

---

## CONTESTO CRON AIR

| Job | Schedule | Script |
|-----|----------|--------|
| Ollama start/stop | 01:00/06:05 | `ollama_cron_window.sh` |
| Auto test | 02:15 | `auto_test.sh` |
| Sentinel | 03:00 | `auto_sentinel.sh` |
| KB Ingest | 05:00 | `auto_kb_ingest.sh` |
| RAG Canary | */6h :30 | `rag_canary.py` |
| System Doctor | 08:00 | `system_doctor.py` |
| Drive Watchdog | */6h :00 | `drive_token_watchdog.py` |
| Judgement Day | Sun 16:00 | `auto_judgement_day.sh` |
| RAGAS Eval | Sun 06:00 | `ragas_eval.py` |
| Drive poll | */5min | `drive_poll_cron.sh` |
| T4 Social Monitor | */6h | `run_t4_monitor.sh` |
| NLM DB sync | 20:30 (04:30 WITA) | `db_to_nlm_sync.py` |
| Core Guardian | */3h | via OpenClaw |
| Intel Scraper | 03:00 | via OpenClaw (Pro) |

Air: 16GB RAM M4. OpenClaw: 3 agents (main, coder, qa-visual)
