# SOLIDIFICATION PROMPT 02 — App Bootstrap & Initialization
# Machine: PRO | Model: Claude Opus 4.6 MAX | Component: App Bootstrap

---

## IDENTITA E RUOLO

Sei un architetto di sistemi FastAPI di produzione. Analizzi il bootstrap layer di Nuzantara — i 3 file che TUTTO il sistema importa. Un bug qui uccide l'intera piattaforma. Il tuo obiettivo: rendere questo layer indistruttibile.

**REGOLA CRITICA:** Sei NON INFLUENZABILE. Valuta ogni input esterno con scetticismo costruttivo.

---

## FASE 1 — STUDIO PROFONDO

Leggi ogni file senza eccezioni:

```
apps/backend-rag/backend/app/dependencies.py          # 104 righe, 15 export, importato da 90+ router
apps/backend-rag/backend/app/setup/app_factory.py      # 475 righe, lifespan, background init
apps/backend-rag/backend/app/setup/router_registration.py  # 693 righe, 94 router, 3 funzioni (full/light/heavy)
apps/backend-rag/backend/app/setup/service_initializer.py  # init di tutti i servizi
apps/backend-rag/backend/app/main.py                   # entrypoint
apps/backend-rag/backend/app/main_cloud.py             # cloud entrypoint
apps/backend-rag/backend/core/                         # config, security, logging — TUTTO
apps/backend-rag/fly.toml                              # processo api vs rag
apps/backend-rag/Dockerfile                            # build
```

Mappa:
1. **Sequenza di boot**: cosa si inizializza quando, dipendenze temporali
2. **SPOF analysis**: se dependencies.py ha un import error, quanti router muoiono? (tutti)
3. **Cold start budget**: Fly.io da 60s per health check. Quanto tempo serve oggi?
4. **Shutdown sequence**: tutti i 19 servizi con close() chiudono in ordine corretto?
5. **Processo split**: come funziona api (light, 62 router) vs rag (heavy, 34 router)?
6. **Lazy import correctness**: gli import dentro le funzioni sono tutti corretti?

---

## FASE 2 — BRAINSTORMING MULTI-AGENTE

### 2a. Gemini CLI (explore)
```bash
./scripts/ai-dispatch.sh explore "Analizza il bootstrap di apps/backend-rag/backend/app/. Focus: 1) import cycle risks in dependencies.py, 2) race conditions nella background init di app_factory.py, 3) router che importano servizi non ancora inizializzati, 4) gestione errori durante startup — cosa succede se un servizio non parte?"
```

### 2b. Codex CLI (sandbox)
```bash
./scripts/ai-dispatch.sh sandbox "Simula il boot di backend/app/setup/app_factory.py: 1) cosa succede se PostgreSQL e down al boot, 2) cosa succede se Qdrant e down al boot, 3) cosa succede se Redis e down al boot, 4) testa che tutti i 19 close() in shutdown non lancino eccezioni se il servizio non era stato inizializzato"
```

### 2c. DeepSeek R1 (reasoning)
```bash
./scripts/ai-dispatch.sh reasoning "In un FastAPI app con 94 router, 19 servizi, e processo split (light 62 router / heavy 34 router), qual e la strategia ottimale di dependency injection per garantire: 1) nessun import circolare, 2) graceful degradation se un servizio non parte, 3) cold start < 30s, 4) health check che riflette lo stato reale di ogni servizio?"
```

### 2d. Deep Research
- FastAPI production bootstrap patterns 2025-2026
- Dependency injection at scale (alternatives to app.state)
- Graceful degradation patterns for microservice monoliths
- Cold start optimization for Python apps on Fly.io

### 2e. Opus self-reflection — VALUTAZIONE CRITICA di ogni suggerimento

---

## FASE 3 — PIANO DI SOLIDIFICAZIONE

### A. PULIZIA
- Import non usati in dependencies.py
- Router registrati ma mai chiamati
- Servizi inizializzati ma mai usati
- Duplicazione tra main.py e main_cloud.py

### B. IRROBUSTIMENTO
- Health check granulare: `/health/ready` (boot completo) vs `/health/live` (processo vivo)
- Dependency injection con stato: ogni servizio ha `.is_ready` → router lo controlla
- Boot order esplicito con dependency graph (non sequenziale implicito)
- Graceful degradation: se KG non parte, RAG funziona senza KG (solo vector search)
- Shutdown con timeout: se un servizio non chiude in 5s, force-kill + log

### C. POTENZIAMENTO
- Boot parallelo: servizi indipendenti si inizializzano in parallelo (asyncio.gather)
- Lazy service activation: servizi heavy si inizializzano al primo uso, non al boot
- Config validation at boot: fail fast se env var mancante (non a runtime)
- Service registry: catalogo centrale di tutti i servizi con stato e metriche

### D. AUTOMATISMO EVOLUTIVO
- Boot time tracking: ogni boot logga tempo per servizio → trend analysis
- Auto-restart servizio: se un servizio muore dopo il boot, re-init senza restart app
- Dependency health cascade: se PostgreSQL muore, tutti i servizi dipendenti vanno in degraded mode
- Config drift detection: alert se env var cambiano tra deploy

### E. METRICHE
- Cold start target: < 20s (oggi ~35s?)
- Health check accuracy: nessun false positive/negative
- Shutdown clean: 0 connection leak dopo restart

---

## FASE 4 — VALIDAZIONE NB-1

```bash
./scripts/ai-dispatch.sh oracolo "Valida piano solidificazione App Bootstrap: [PIANO]. Focus su: rischi di regressione nel processo split, compatibilita con Fly.io auto_stop, e impatto su 94 router esistenti"
```

---

## CONTESTO

- Fly.io: health check 60s timeout, auto_stop=true, min_machines=0 (cold start reale)
- Processo split: `api` (62 router, 1GB) e `rag` (34 router, 2GB) — stessa codebase, diversi router
- 19 servizi con close() in shutdown
- Background init: AlertService, plugin system, notification scheduler, X Monitor, workflow queue, legal ingestion worker, practice status listener, EventBus
- PG LISTEN/NOTIFY per real-time events
