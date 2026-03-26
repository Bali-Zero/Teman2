# Audit 05: Backend Agents — Risultati e Azioni

**Data:** 2026-03-16
**Eseguito da:** Claude Opus 4.6
**Rischio:** BASSO (solo disabilitazione task, nessun codice rimosso)

## Verdetto

**L'AutonomousScheduler è inutile con `auto_stop=true`.** Il backend si spegne dopo ~5min — nessun task >=6h esegue mai.

## Azioni Eseguite

### 1. Disabilitati 5 task nello scheduler backend

| Task                   | Motivo                                      | Coperto da                          |
| ---------------------- | ------------------------------------------- | ----------------------------------- |
| `conversation_trainer` | git subprocess su container effimero Fly.io | Nessuno (funzionalità morta)        |
| `daily_ops_autopilot`  | BUG: chiama localhost:8000 (se stesso)      | OpenClaw `daily-ops-autopilot`      |
| `renewal_alerts`       | 12h > uptime auto_stop                      | OpenClaw `practice-lifecycle-check` |
| `birthday_notifier`    | 24h > uptime auto_stop                      | OpenClaw `client-health-monitor`    |
| `conversation_cleanup` | 24h > uptime auto_stop                      | Nuovo cron OpenClaw (aggiunto)      |

### 2. Aggiunto cron OpenClaw

- `conversation-cleanup` — 02:00 WITA daily, chiama backend API per cleanup conversazioni

### 3. Task rimasti attivi (funzionano con auto_stop)

| Task                   | Intervallo | Perché funziona                              |
| ---------------------- | ---------- | -------------------------------------------- |
| `self_healing`         | 5min       | Si riarma ad ogni cold start                 |
| `golden_routes_seeder` | one-shot   | Controlla COUNT(\*) e skippa se già popolato |

### 4. Codice orfano identificato (NON toccato)

- `ClientValuePredictor`: file esiste ma mai registrato nello scheduler. Twilio non configurato.
- `ConversationTrainer`: codice funzionale ma inutile su Fly.io (git subprocess).

## File Modificati

| File                                                             | Modifica                                  |
| ---------------------------------------------------------------- | ----------------------------------------- |
| `apps/backend-rag/backend/services/misc/autonomous_scheduler.py` | Disabilitati 5 task, aggiornato docstring |
| `~/.openclaw/cron/jobs.json`                                     | Aggiunto `conversation-cleanup` cron      |

## Prossimi Passi (opzionali)

1. **Deploy backend** per applicare le disabilitazioni su Fly.io
2. **Verificare** che OpenClaw esegue `conversation-cleanup` nella prossima finestra (02:00 WITA)
3. **Considerare** rimozione completa del codice morto (ConversationTrainer, ClientValuePredictor) in futuro
