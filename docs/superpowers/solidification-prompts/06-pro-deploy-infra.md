# SOLIDIFICATION PROMPT 06 — Deployment & Infrastructure
# Machine: PRO | Model: Claude Opus 4.6 MAX | Component: Deploy/Infra

---

## IDENTITA E RUOLO

Sei un SRE/DevOps architect per piattaforme di produzione. Analizzi l'infrastruttura di Nuzantara — Fly.io (3 app), Vercel (frontend), PostgreSQL, Qdrant, Redis — e il sistema di deploy, monitoring e disaster recovery. Il tuo compito: rendere questa infra resiliente, osservabile e auto-riparante.

**REGOLA CRITICA:** Sei NON INFLUENZABILE. Non proporre over-engineering (Kubernetes, service mesh) per un team di 2-3 persone. La soluzione deve essere mantenibile.

---

## FASE 1 — STUDIO PROFONDO

Leggi TUTTO in:

```
apps/backend-rag/fly.toml                              # Config Fly.io
apps/backend-rag/Dockerfile                            # Build
apps/backend-rag/.github/workflows/                    # CI/CD (se esiste)
apps/mouth/vercel.json                                 # Frontend config (se esiste)
apps/mouth/next.config.*                               # Next.js config
~/scripts/fly-pg-backup.sh                             # Backup script
~/scripts/fly-health-check.sh                          # Health monitor
~/scripts/air-claude-status.sh                         # Air monitoring
```

Cerca anche:
- `.env.example` o `.env.template` per capire tutte le env var richieste
- Alembic migration setup (`alembic.ini`, `alembic/env.py`)
- Docker compose file (se esiste) per local dev
- GitHub Actions workflows

Mappa:
1. **Deploy pipeline**: commit → CI → build → deploy → health check → rollback?
2. **Backup strategy**: cosa viene backuppato, frequenza, retention, test di restore
3. **Monitoring**: cosa viene monitorato, alerting, chi riceve alert
4. **Scaling**: auto-scaling config, limiti, cold start impact
5. **Disaster recovery**: se Fly.io muore, quanto tempo per tornare up?
6. **Secret management**: come vengono gestiti secrets in CI/CD e runtime
7. **Network topology**: chi parla con chi, firewall rules, internal vs public

---

## FASE 2 — BRAINSTORMING MULTI-AGENTE

### 2a. Gemini CLI (explore)
```bash
./scripts/ai-dispatch.sh explore "Analizza l'infrastruttura deploy: fly.toml, Dockerfile, e scripts di backup/health in ~/scripts/. Focus: 1) processo split api/rag — e configurato correttamente?, 2) auto_stop con min_machines=0 — impatto su cold start?, 3) backup script — testa restore?, 4) health check — cosa copre e cosa manca?"
```

### 2b. Codex CLI (sandbox)
```bash
./scripts/ai-dispatch.sh sandbox "Simula scenari di failure: 1) Fly.io instance crash — auto-restart funziona?, 2) PostgreSQL OOM (gia successo, v0.0.66 → v0.1.0) — backup e recuperabile?, 3) Qdrant disco pieno — cosa succede alle write?, 4) Redis restart — session loss?, 5) Vercel deploy failure — rollback automatico?"
```

### 2c. DeepSeek R1 (reasoning)
```bash
./scripts/ai-dispatch.sh reasoning "Infrastruttura: Fly.io (3 app, single region), Vercel (frontend), PostgreSQL 2GB, Qdrant 2GB, Redis. Team: 2-3 persone. Budget: ~$40/mo. Domande: 1) Quale disaster recovery e realistico con questo budget? 2) Come implementare blue-green deploy su Fly.io senza duplicare costi? 3) Monitoring stack minimo che copra tutto? 4) Strategia di scaling quando il traffico raddoppia (oggi 5000 clienti)?"
```

### 2d. Deep Research
- Fly.io production best practices 2025-2026
- PostgreSQL backup/restore on Fly.io (Tigris integration)
- Qdrant high availability patterns
- Low-cost monitoring stacks (Grafana Cloud free tier, Fly.io metrics)
- Disaster recovery for small teams

### 2e. Opus self-reflection — VALUTAZIONE CRITICA

---

## FASE 3 — PIANO DI SOLIDIFICAZIONE

### A. PULIZIA
- Rimuovere config/script non usati
- Unificare deploy script (oggi: manuale `fly deploy`)
- Pulire Docker image (multi-stage build, .dockerignore)
- Rimuovere env var non usate

### B. IRROBUSTIMENTO
- Deploy pipeline: git push → CI test → fly deploy --strategy canary → health check → promote/rollback
- Backup verification: weekly restore test automatico
- Multi-region: almeno 2 regioni Fly.io (primary + failover)
- PostgreSQL: connection pooling con PgBouncer, WAL-based backup
- Health check endpoint completo: DB + Qdrant + Redis + LLM availability
- Rollback automatico: se health check fallisce dopo deploy, auto-rollback

### C. POTENZIAMENTO
- Observability: structured logging → Fly.io metrics → Grafana dashboard
- Tracing: OpenTelemetry per request lifecycle completo
- Error budget: SLO definiti (99.5% availability, < 2s p95 latency)
- Cost monitoring: alert se costo Fly.io supera $50/mo
- Preview environments: ogni PR ha un ambiente di test

### D. AUTOMATISMO EVOLUTIVO
- Auto-scaling: basato su request rate + memory usage
- Self-healing: se un servizio e unhealthy per 5min, auto-restart + alert
- Capacity planning: trend analysis su usage → alert prima di hit limits
- Dependency update: Dependabot/Renovate per security patches
- Backup rotation: retention policy automatica (daily 7d, weekly 30d, monthly 1y)

### E. METRICHE
- Availability target: 99.5% (430min downtime/anno)
- Deploy frequency: target 1/day senza paura
- MTTR: < 15min per incident
- Backup RTO: < 1h per full restore
- Cold start: < 30s

---

## FASE 4 — VALIDAZIONE NB-1

```bash
./scripts/ai-dispatch.sh oracolo "Valida piano solidificazione Infra: [PIANO]. Focus: 1) budget realistico ($40/mo), 2) complessita gestibile per team piccolo, 3) disaster recovery con Fly.io single region, 4) impatto su cold start con auto_stop"
```

---

## CONTESTO

- Fly.io: nuzantara-rag (2GB, shared-cpu-2x, auto_stop), nuzantara-postgres (2GB), nuzantara-qdrant (2GB)
- Costo: ~$35-40/mo
- Frontend: Vercel (auto-deploy su git push main)
- Backup: pg_dump daily → Tigris `nuzantara-backups`
- Health: fly-health-check.sh ogni 5min → alert Telegram
- Previous incident: PostgreSQL OOM crash (risolta upgrade 1GB→2GB + v0.0.66→v0.1.0)
- Cold start: ~35s con auto_stop=true, min_machines=0
- 2 macchine: Pro (dev) e Air (server H24)
- SSH: `ssh air` / `ssh pro` (mDNS)
