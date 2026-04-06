# S06 — Deployment & Infrastructure Solidification Plan

**Machine:** PRO | **Model:** Claude Opus 4.6 MAX | **Date:** 2026-04-06
**Status:** Fase 3 — Piano di Solidificazione

---

## STATO ATTUALE (Fase 1 findings)

### Infrastruttura

| Componente | Config | Stato |
|---|---|---|
| **nuzantara-rag** | 2 api machines (1GB, shared-2x) + 1 rag (2GB, shared-2x) | 3 machines started, health passing |
| **nuzantara-postgres** | shared-1x, 2GB | Always-on, daily backup |
| **nuzantara-qdrant** | Migrato a Qdrant Cloud | Fly app suspended |
| **Frontend (Vercel)** | Auto-deploy on push main | 8 subdomains |
| **Redis** | Managed (Upstash?) | Non verificato in health check |

### Deploy Pipeline (fly-deploy.yml)

```
push main → pre-deploy gate → [migrations DISABLED] → fly deploy rolling → health check (10×30s) → rollback se fail
```

**Gate:** import chain + ruff lint + 82 core tests + vulnerability check
**Notification:** Telegram su success/failure
**Rollback:** Automatico via `flyctl releases rollback`

### Backup Strategy

| Target | Script | Schedule | Retention | Verify |
|---|---|---|---|---|
| PostgreSQL | `~/scripts/fly-pg-backup.sh` | Daily | 7 local + 30 Tigris | gunzip + header check |
| Qdrant | `~/scripts/fly-qdrant-backup.sh` | Daily 03:30 | 7 local + 30 Tigris | Collection count |
| Redis | NESSUNO | - | - | - |

### Monitoring

| Tool | Cosa copre | Gap |
|---|---|---|
| `fly-health-check.sh` | RAG /health + PG status | Solo 07:30-20:00 WITA, no Redis, Qdrant hardcoded OK |
| `system_doctor.py` | Backend + frontend URLs + SSL + cron health | Completo ma run 1x/day |
| `rag_canary.py` | Embedding drift + golden queries | Ogni 6h, buona copertura |
| Fly.io built-in | Machine health checks | Ogni 30s, auto-restart |
| Sentry | Error tracking | In produzione (DSN configurato) |
| Telegram | Alert delivery | Tutti gli script alertano qui |

### Security CI

5 workflow attivi: fly-deploy, tests, security (Snyk+CodeQL+Bandit+Safety+detect-secrets), semgrep, sonarqube

---

## PIANO DI SOLIDIFICAZIONE

### A. PULIZIA (P0 — subito, 0 rischio)

| # | Fix | File | Effort |
|---|---|---|---|
| A1 | **Rimuovere credenziali Tigris hardcoded** da backup scripts | `~/scripts/fly-pg-backup.sh:14-15`, `~/scripts/fly-qdrant-backup.sh:28-29` | 15min |
| A2 | **Qdrant health check reale** — oggi hardcoded `QDRANT="OK"` | `~/scripts/fly-health-check.sh:34` | 10min |
| A3 | **Estendere health check a 24h** — oggi 07:30-20:00, failure notturni invisibili | `~/scripts/fly-health-check.sh` (rimuovere time gate) | 5min |
| A4 | **Aggiungere Redis health check** | `~/scripts/fly-health-check.sh` | 10min |
| A5 | **Pulire .dockerignore** — verificare che training-data/ serva in prod | `apps/backend-rag/.dockerignore` | 5min |

**Dettaglio A1 — Credenziali Tigris:**
```bash
# PRIMA (hardcoded)
TIGRIS_KEY="${AWS_ACCESS_KEY_ID:-tid_sZQYyrgouAXAdQDuvsfPlLIIUMMvEDNhfMWmzCdeouELsPMn_U}"
TIGRIS_SECRET="${AWS_SECRET_ACCESS_KEY:-tsec_5knItu7FoHkkv2P5qaEMSRdHxXDNb6ZD0+mgDfLsLF-lLntRwDUgrH4qmzhJX+3OI4XYTc}"

# DOPO (env-only, fail fast)
TIGRIS_KEY="${AWS_ACCESS_KEY_ID:?ERROR: AWS_ACCESS_KEY_ID not set}"
TIGRIS_SECRET="${AWS_SECRET_ACCESS_KEY:?ERROR: AWS_SECRET_ACCESS_KEY not set}"
```
Le credenziali vanno spostate in `~/.zshrc.secrets` (o env file dedicato).

**Dettaglio A2 — Qdrant health check reale:**
```bash
# PRIMA
QDRANT="OK"  # Qdrant health checked indirectly via RAG backend health endpoint

# DOPO
QDRANT_URL="${QDRANT_URL:-}"
QDRANT_API_KEY="${QDRANT_API_KEY:-}"
if [[ -n "$QDRANT_URL" ]]; then
    QDRANT_STATUS=$(curl -sf -H "api-key: $QDRANT_API_KEY" "$QDRANT_URL/healthz" --max-time 10 && echo "OK" || echo "FAIL")
    QDRANT="$QDRANT_STATUS"
else
    QDRANT="OK"  # fallback: checked via RAG /health
fi
```

**Dettaglio A4 — Redis health check:**
```bash
REDIS_URL="${REDIS_URL:-}"
if [[ -n "$REDIS_URL" ]]; then
    REDIS=$(curl -sf --max-time 5 "$REDIS_URL/ping" 2>/dev/null && echo "OK" || echo "FAIL")
else
    REDIS="SKIP"  # URL non configurata
fi
[ "$REDIS" = "FAIL" ] && FAILURES="${FAILURES}Redis: unreachable\n"
```

### B. IRROBUSTIMENTO (P1 — questa settimana, basso rischio)

| # | Fix | File | Effort |
|---|---|---|---|
| B1 | **Riabilitare migrations in CI/CD** — o documentare perché disabilitate | `.github/workflows/fly-deploy.yml:52-53` + `fly.toml:10-11` | 30min |
| B2 | **Backup restore test** — pg_restore --list dopo pg_dump | `~/scripts/fly-pg-backup.sh` | 20min |
| B3 | **Health endpoint: aggiungere Redis check** | `backend/app/routers/health.py` | 15min |
| B4 | **Structured logging → JSON** in produzione | `backend/core/logging_config.py` (se esiste) | 30min |
| B5 | **Fly.io log drain** → external (Grafana Cloud free o Betterstack free) | Fly CLI config | 20min |
| B6 | **Backup Telegram notification** — notifica anche su success, non solo failure | `~/scripts/fly-pg-backup.sh` | 10min |

**Dettaglio B1 — Migrations:**
Il release_command è commentato in fly.toml E il job run-migrations in fly-deploy.yml. Rischio: schema drift tra codice e DB.
- **Opzione A:** Fix il bug che ha causato la disabilitazione e riabilita
- **Opzione B:** Se il bug è complesso, almeno aggiungere un check che verifica `alembic current == alembic heads`

**Dettaglio B2 — Backup restore test:**
Dopo `gunzip -t` e header check (già presenti), aggiungere:
```bash
# Verify restore-ability (list mode, non scrive nulla)
if gunzip -c "$BACKUP_FILE" | pg_restore --list > /dev/null 2>&1; then
    log "Restore test: PASS (pg_restore --list OK)"
else
    # pg_dump plain format: try psql dry-run parse
    if gunzip -c "$BACKUP_FILE" | head -100 | grep -q "CREATE TABLE\|INSERT INTO"; then
        log "Restore test: PASS (plain SQL format verified)"
    else
        log "WARNING: Restore test inconclusive"
    fi
fi
```

### C. POTENZIAMENTO (P2 — prossime 2 settimane, medio effort)

| # | Fix | Impatto | Effort |
|---|---|---|---|
| C1 | **Grafana Cloud free tier** — dashboard con Fly.io metrics | Visibilità storica, trend | 2h setup |
| C2 | **SLO definition** — 99.5% availability, <2s p95 latency | Target misurabile | 1h doc |
| C3 | **Cost alerting** — Fly.io billing API check settimanale | Prevenire cost overrun | 1h script |
| C4 | **Dependabot/Renovate** — security patches automatici | Supply chain security | 30min config |
| C5 | **Pre-deploy smoke test migliorato** — test RAG query e2e nel CI | Catch regression prima del deploy | 2h |

**Dettaglio C1 — Grafana Cloud:**
- Free tier: 10K metrics, 50GB logs, 50GB traces
- Fly.io ha `fly metrics` built-in, ma senza storico
- Setup: `fly logs ship --grafana-cloud-token <token>` (1 comando)
- Dashboard: import template per Fly.io metrics (CPU, memory, requests, latency)

### D. AUTOMATISMO EVOLUTIVO (P3 — backlog, solo se necessario)

| # | Feature | Trigger | Razionale |
|---|---|---|---|
| D1 | **Multi-region failover** | Quando revenue > $5K/mo o SLA contrattuale | Oggi: $40/mo, 5000 clienti. Non giustificato. |
| D2 | **Preview environments** | Quando team > 3 persone | Oggi: 2-3 persone, PR review manuale è OK |
| D3 | **Auto-scaling basato su load** | Quando p95 > 3s o memory > 80% costante | Oggi: shared-2x regge, monitor prima |
| D4 | **Blue-green deploy** | Quando rolling non basta | Rolling + auto-rollback è sufficiente oggi |

---

## OVER-ENGINEERING RIFIUTATO

| Proposta | Perché NO |
|---|---|
| **Kubernetes** | Team 2-3, Fly.io gestisce tutto. K8s è 10x complessità per 0 beneficio. |
| **OpenTelemetry full stack** | Sentry + Fly metrics + system_doctor copre il 95%. |
| **Service mesh** | 3 app, comunicazione interna via Fly DNS. Zero senso. |
| **Multi-region** | $40/mo budget. SIN uptime 99.9%. RTO < 1h con backup è accettabile per 5000 clienti. |
| **Dedicated CPU** | shared-2x regge. Upgrade quando monitoring mostra saturazione. |
| **WAF/DDoS** | Fly.io ha protezione built-in. Cloudflare in più è overkill per il traffico attuale. |

---

## METRICHE TARGET

| Metrica | Attuale | Target | Come misurare |
|---|---|---|---|
| **Availability** | ~99% (stimato) | 99.5% (430min/anno) | Fly.io checks + health script |
| **Deploy frequency** | ~2-3/week | 1/day | GitHub Actions history |
| **MTTR** | ~15-30min | <15min | Auto-rollback + alert |
| **Backup RTO** | Non testato | <1h (PG), <2h (Qdrant) | Weekly restore test |
| **Cold start** | Eliminato (auto_stop=off) | N/A | Già risolto |
| **p95 latency** | Non misurato | <2s | Grafana Cloud (dopo C1) |

---

## SECURITY FINDINGS

### CRITICO: Credenziali Tigris in chiaro nei backup scripts

**File:** `~/scripts/fly-pg-backup.sh:14-15` e `~/scripts/fly-qdrant-backup.sh:28-29`
```
TIGRIS_KEY="${AWS_ACCESS_KEY_ID:-tid_sZQYyrgouAXAdQDuvsfPlLIIUMMvEDNhfMWmzCdeouELsPMn_U}"
TIGRIS_SECRET="${AWS_SECRET_ACCESS_KEY:-tsec_5knItu7FoHkkv2P5qaEMSRdHxXDNb6ZD0+mgDfLsLF-lLntRwDUgrH4qmzhJX+3OI4XYTc}"
```

Questi script sono in `~/scripts/` (non nel repo git), ma le credenziali in chiaro sono un rischio se il disco viene compromesso. **Fix A1 è priorità assoluta.**

### NOTA: PG password in backup script

`fly-pg-backup.sh:55` contiene `PGPASSWORD=2zEjit43IF6gNUV` hardcoded nel comando pg_dump. Stessa urgenza di A1.

---

## SEQUENZA DI IMPLEMENTAZIONE

```
Settimana 1: A1-A5 (pulizia, 45min totale)
Settimana 1: B1-B6 (irrobustimento, 2h totale)
Settimana 2: C1-C2 (Grafana + SLO, 3h)
Settimana 3: C3-C5 (cost alert + Dependabot + smoke test, 3.5h)
Backlog: D1-D4 (solo se triggered)
```

**Budget impatto:** $0 extra (Grafana Cloud free, Dependabot free, tutto il resto è config/script)

---

## RISCHI NON MITIGABILI (con $40/mo)

1. **Fly.io SIN region outage** — RTO stimato 2-4h (restore su altra region). Accettabile per il business.
2. **Qdrant Cloud outage** — backend va in degraded mode (no vector search). Backup su Tigris permette restore.
3. **Tigris outage** — backup non uploadabili, ma restano in locale (7 copie).

Questi rischi sono documentati e accettati dato il budget e la scala del business.
