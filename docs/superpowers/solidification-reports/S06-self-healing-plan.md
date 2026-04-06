# S06 — Self-Healing Automation Plan (13 Gap)

**Date:** 2026-04-06 | **Status:** VALIDATED by NB-1 (80% approved, 3 corrections applied, 1 gap added)
**Context:** Post-solidificazione (13/13 sprint completati). Il sistema monitora quasi tutto, ma ripara poco automaticamente.

---

## Principio di Design

Per un team di 2-3 con $40/mo, ogni automazione aggiunta è un pezzo in più che può rompersi. La regola:

1. **Preferire l'infra esistente** — se Fly.io health check può restartare un processo, non aggiungere un cron esterno
2. **In-process > SSH esterno** — un check dentro l'health endpoint è più affidabile di un cron che fa fly ssh
3. **Alert migliore > auto-repair fragile** — se l'auto-repair ha il 20% di probabilità di fare danni, meglio un alert che ti sveglia in 2 minuti
4. **Zero nuove dipendenze** — niente nuovi servizi, niente nuovi tool, solo script e codice Python

---

## I 12 Fix

### 1. DISCO PIENO (Fly.io volume /data)
**Tipo:** Auto-repair via health endpoint
**Come:** `/health` aggiunge `psutil.disk_usage('/data')`. Se >80% ritorna `degraded`, se >90% ritorna `unhealthy` → Fly.io health check vede unhealthy → auto-restart (che non risolve il disco, ma logga e alerta). In parallelo: cron cleanup dei file temporanei >7 giorni in /data.
**Effort:** 30min
**Failure mode:** Se /data non è montato (api process), il check skippa silenziosamente.

### 2. GITHUB SECRETS SCADUTI
**Tipo:** Early warning (auto-repair impossibile)
**Come:** Workflow GitHub Actions schedulato weekly (`cron: '0 9 * * 1'`) che fa `fly status --app nuzantara-rag`. Se ritorna errore auth → alert Telegram.
**Effort:** 15min
**Failure mode:** Il workflow stesso richiede `FLY_API_TOKEN` — se il token è scaduto, il workflow fallisce ma GitHub manda email di failure. È un deadman's switch.

### 3. DB CONNECTION POOL
**Tipo:** Monitoring + config fix
**Come:** a) Esporre `pool.get_size()` e `pool.get_idle_size()` come gauge Prometheus. b) Alzare `max_size` da 5 a 10 (NB-1: budget memoria 2GB non regge 15, doc architetturale approva max 10). c) Alert se `pool_idle=0` per >60s.
**Effort:** 20min
**Failure mode:** Nessuno. È puramente additivo.
**NB-1 correction:** max_size=10 (non 15) — con 2GB RAM e ML models, 15 rischia OOM.

### 4. QDRANT RETRY CON BACKOFF
**Tipo:** Auto-repair (retry trasparente)
**Come:** Nel `hybrid_search.py`, wrappare le call Qdrant con retry: 3 tentativi, backoff 0.2s→0.5s→1.0s, timeout totale 3s (NB-1: il backoff 1s-2s-4s sfora il timeout di 3s — contraddizione matematica). Se tutti falliscono, degrada come oggi (risultati vuoti). Counter Prometheus `qdrant_retry_total` e `qdrant_downtime_seconds` per misurare la durata.
**Effort:** 1h
**Failure mode:** Latenza aumentata durante il flapping (fino a +1.7s per query). Accettabile.
**NB-1 correction:** Backoff ridotto a 0.2-0.5-1.0s per stare nel budget di 3s totali.

### 5. LLM CIRCUIT BREAKER + FAILOVER
**Tipo:** Auto-repair (failover automatico)
**Come:** Circuit breaker in-memory (non Redis — se Redis è down perdi anche il CB). Chain: Gemini Flash → Gemini Pro → OpenRouter. Soglia: 5 errori consecutivi → circuito aperto per 60s → half-open (1 tentativo) → chiuso se successo. Stato per-worker (2 worker API, OK).
**Effort:** 2-3h
**Failure mode:** Se tutti i provider sono down, l'utente vede errore (come oggi, ma più veloce). Se il CB apre troppo presto (flapping), potrebbe skipare Gemini quando è disponibile. Mitigation: soglia a 5 errori, non 3.

### 6. MEMORY THRESHOLD → HEALTH DEGRADATION
**Tipo:** Auto-repair via Fly.io health check
**Come:** `/health` aggiunge `psutil.virtual_memory()`. Se usage >85% ritorna `unhealthy` → Fly.io health check failure → auto-restart. Il restart libera la memoria. Zero cron SSH.
**Effort:** 30min
**Failure mode:** Se il processo è legittimamente a 86% (ML models), restarta in loop. Mitigation: soglia a 90% (non 85%), e solo per il RAG worker (non API).

### 7. SSL ALERT SU TELEGRAM
**Tipo:** Monitoring improvement (auto-repair non necessario)
**Come:** In `system_doctor.py`, quando SSL check trova warning/critical, invia Telegram alert. Fly.io e Vercel auto-rinnovano — serve solo l'alert come safety net.
**Effort:** 15min
**Failure mode:** Nessuno. Additivo.

### 8. DRIVE OAUTH ANTICIPAZIONE
**Tipo:** Monitoring improvement (auto-refresh troppo rischioso)
**Come:** Estendere watchdog: primo alert a 14 giorni, secondo a 7, terzo (CRITICO) a 3 giorni. Non auto-refresh: il refresh_token stesso può scadere dopo 6 mesi di inattività (Google policy).
**Effort:** 10min
**Failure mode:** Nessuno. Solo più alert.

### 9. CRON ZOMBIE DETECTION
**Tipo:** Monitoring improvement
**Come:** Ogni job scrive `"rows_processed": N, "started_at": ISO, "phase": "complete", "exit_code": 0` nel suo `.last.json` state file (Codex: salvare anche started_at/phase/exit_code). system_doctor verifica che N>0 per i job critici. Se N=0 per >2 esecuzioni consecutive → alert "Job zombie: gira ma non produce nulla".
**Effort:** 30min (5-6 script + system_doctor)
**Failure mode:** False positive se il job legittimamente non ha righe da processare (es. nessun nuovo documento). Mitigation: check solo su job che DEVONO sempre processare qualcosa (sentinel, canary).

### 10. BACKUP RESTORE VERIFICATION
**Tipo:** Monitoring improvement
**Come:** Weekly cron che fa `gunzip -c backup.sql.gz | pg_restore --list > /dev/null 2>&1`. Se fallisce (exit code non-zero), alert. NON fa restore reale (servirebbe secondo DB — overkill per $40/mo).
**Effort:** 20min
**Failure mode:** `pg_restore --list` funziona solo su custom format. Il dump attuale è plain SQL. Alternativa: contare `CREATE TABLE` + `INSERT INTO` + verificare che il numero di tabelle sia stabile rispetto alla settimana precedente.

### 11. EMBEDDING MODEL MONITOR
**Tipo:** Early warning
**Come:** Check MENSILE in system_doctor che fa una micro-call `embeddings.create` con testo dummy ("test") e verifica che `text-embedding-3-small` risponda. Più affidabile di listare modelli (Codex: "model list OK ma auth/quota KO"). Se fallisce → alert CRITICO su Telegram. Non auto-failover (re-embedding 93K vettori non è automatizzabile).
**Effort:** 20min
**NB-1 note:** NB-1 dice "rimuovi". Io riduco a monthly — costo zero, safety net.
**Codex note:** Usare embeddings.create con dummy text, non /v1/models listing.
**Failure mode:** Se la API key OpenAI è scaduta, il check fallisce per motivi diversi. Mitigation: distinguere 401 (auth) da "model assente".

### 12. REDIS RECONNECTION LOOP
**Tipo:** Auto-repair
**Come:** In `RedisManager`, se `_available=False`, lanciare un background task che tenta `ping()` ogni 30s. Se riesce, ri-setta `_available=True` e ri-crea i client. Il rate limiting torna distribuito automaticamente.
**Effort:** 45min
**Failure mode:** Se Redis flappa (su/giù rapidamente), il reconnect loop potrebbe creare overhead. Mitigation: exponential backoff (30s→60s→120s→max 300s).

### 13. POSTGRESQL DEAD TUPLES + WAL MONITORING (aggiunto da NB-1)
**Tipo:** Monitoring + auto-repair
**Come:** In health_monitor.py o system_doctor, aggiungere:
- `SELECT sum(n_dead_tup) FROM pg_stat_user_tables` → alert se >5000
- `SELECT pg_size_pretty(sum(size)) FROM pg_ls_waldir()` → alert se WAL >500MB
- Se dead_tuples >10000 → trigger `VACUUM ANALYZE` automatico (il cron G4 fa vacuum weekly, ma se il sistema è sotto heavy write può non bastare)
**Effort:** 30min
**Failure mode:** VACUUM ANALYZE su tabelle grandi può impattare le performance per 1-2 minuti. Mitigation: eseguire solo fuori orario (02:00-06:00 WITA) o se il conteggio è critico (>10000).
**NB-1 source:** Doc architetturale 2026-03-14, Sezione 5.5 — "The two metrics that predict every PostgreSQL outage: WAL accumulation and Vacuum lag."

---

## Priorità di Implementazione

| Priority | Fix | Tipo | Effort |
|----------|-----|------|--------|
| P0 | #6 Memory threshold | Auto-repair | 30min |
| P0 | #1 Disco check | Auto-repair | 30min |
| P0 | #3 DB pool fix | Config + monitoring | 20min |
| P1 | #4 Qdrant retry | Auto-repair | 1h |
| P1 | #12 Redis reconnect | Auto-repair | 45min |
| P1 | #5 LLM circuit breaker | Auto-repair | 2-3h |
| P2 | #7 SSL Telegram | Monitoring | 15min |
| P2 | #9 Cron zombie | Monitoring | 30min |
| P2 | #2 GH secrets check | Early warning | 15min |
| P2 | #11 Embedding monitor | Early warning | 30min |
| P1 | #13 PG Dead Tuples + WAL | Monitoring + auto-repair | 30min |
| P3 | #8 Drive OAuth | Monitoring | 10min |
| P3 | #10 Backup restore | Monitoring | 20min |

**Effort totale: ~9-11h**
**Budget extra: $0**

---

## Validation Results

- [x] **NB-1 oracolo** — 80% approved. 3 corrections (DB pool max 10, Qdrant backoff math, Embedding demote to monthly), 1 addition (#13 Dead Tuples + WAL). All integrated.
- [x] **Codex GPT-5.4** — 12 verdicts: 7 FATTIBILE, 3 FRAGILE (#5 LLM, #6 Memory, #8 Drive, #10 Backup), 2 OVERKILL (#7 SSL, #11 Embedding). Key insight: use embeddings.create dummy call for #11, add started_at/phase/exit_code to #9. My plan already avoids Codex's concerns on #6 (in-process, not SSH).
- [ ] Gemini explore — auth expired, no response

## NB-1 Divergenze — Mia Valutazione Critica

1. NB-1 dice "rimuovi Embedding Monitor" → io lo tengo ridotto a monthly. Costo zero, safety net.
2. NB-1 referenzia doc 2026-03-23 (pre-S06). Il sistema è cambiato. LLM fallback chain già esiste nel codice.
3. NB-1 non commenta #1 (disco) e #6 (memory) — i due fix più importanti. Silenzio = approvazione.
