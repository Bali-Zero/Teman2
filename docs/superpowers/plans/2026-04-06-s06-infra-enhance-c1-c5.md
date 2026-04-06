# S06 Infrastructure Enhancement (C1-C5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add observability, SLO definition, cost monitoring, dependency updates, and pre-deploy smoke tests.

**Architecture:** Mix of backend code (metrics endpoint), GitHub config (Dependabot), bash scripts (cost alert), CI/CD enhancement (smoke test), and documentation (SLO).

**Tech Stack:** Python/FastAPI, GitHub Actions, Bash, Fly CLI

**Discovery:**
- `prometheus_client` already installed, `generate_latest` imported in `backend/app/metrics.py`
- 20+ `zantara_*` metrics defined (counters, gauges, histograms) but NOT exposed via endpoint
- Local Prometheus+Grafana stack exists in `config/monitoring/` but not in production
- No `.github/dependabot.yml` exists
- Grafana Cloud free tier: 10K metrics series, 50GB logs, 14 day retention

---

### Task 1: Expose Prometheus /metrics endpoint (C1a)

**Files:**
- Modify: `apps/backend-rag/backend/app/routers/health.py`
- Reference: `apps/backend-rag/backend/app/metrics.py` (already has `generate_latest`)

- [ ] **Step 1: Read health.py to find the right insertion point**

Read `apps/backend-rag/backend/app/routers/health.py` — find the end of the file. The `/metrics` Prometheus endpoint should go after the existing `/health/metrics/summary` endpoint.

- [ ] **Step 2: Add Prometheus text format /metrics endpoint**

At the end of `health.py`, add:

```python
@router.get("/metrics/prometheus", include_in_schema=False)
async def prometheus_metrics():
    """Prometheus text format metrics for external scraping (Grafana Cloud, Prometheus)."""
    from backend.app.metrics import generate_latest
    from starlette.responses import Response

    return Response(
        content=generate_latest(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
```

Note: We use `/metrics/prometheus` (not `/metrics`) to avoid collision with existing `/metrics/summary` and `/metrics/qdrant` paths. The `/health` router prefix means the full path is `/health/metrics/prometheus`.

- [ ] **Step 3: Verify it works locally**

```bash
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.metrics import generate_latest; print(generate_latest()[:200])"
```

Expected: Prometheus text format output starting with `# HELP` and `# TYPE` lines.

- [ ] **Step 4: Verify the endpoint doesn't require auth**

Check that `/health/*` paths are excluded from auth middleware (they should be — health endpoints are always public).

---

### Task 2: Create Grafana Cloud setup script (C1b)

**Files:**
- Create: `~/scripts/setup-grafana-cloud.sh`

This is a setup guide/script — actual account creation is manual.

- [ ] **Step 1: Create the setup script**

```bash
#!/usr/bin/env bash
# Grafana Cloud Setup for Nuzantara
# Free tier: 10K metrics, 50GB logs, 14 day retention
#
# Prerequisites:
#   1. Create account: https://grafana.com/auth/sign-up/create-user
#   2. Get your Prometheus remote_write URL from Cloud Portal → Prometheus → Details
#   3. Get your username (numeric) and API key (grafana.com → My Account → API Keys)
#
# Usage: bash ~/scripts/setup-grafana-cloud.sh <prometheus-url> <username> <api-key>

set -euo pipefail

PROM_URL="${1:?Usage: $0 <prometheus-remote-write-url> <username> <api-key>}"
USERNAME="${2:?Missing Grafana Cloud username (numeric)}"
API_KEY="${3:?Missing Grafana Cloud API key}"
APP="nuzantara-rag"

echo "=== Grafana Cloud Setup for $APP ==="
echo ""
echo "Step 1: Configure Prometheus remote_write..."
echo ""
echo "Add to config/monitoring/prometheus/prometheus.yml:"
echo ""
cat <<YAML
remote_write:
  - url: ${PROM_URL}
    basic_auth:
      username: "${USERNAME}"
      password: "${API_KEY}"
YAML
echo ""
echo "Step 2: The backend exposes metrics at:"
echo "  https://nuzantara-rag.fly.dev/health/metrics/prometheus"
echo ""
echo "Step 3: Add this as a scrape target in Grafana Cloud:"
echo "  Go to Grafana Cloud → Connections → Add new connection → Prometheus"
echo "  Add scrape job for: https://nuzantara-rag.fly.dev/health/metrics/prometheus"
echo ""
echo "Step 4: Import dashboard"
echo "  Import ID 1860 (Node Exporter Full) for system metrics"
echo "  Or create custom dashboard with zantara_* metrics"
echo ""
echo "Done! Verify at your Grafana Cloud instance."
```

- [ ] **Step 2: Make executable and verify**

```bash
chmod +x ~/scripts/setup-grafana-cloud.sh
bash -n ~/scripts/setup-grafana-cloud.sh && echo "Syntax OK"
```

---

### Task 3: Write SLO definition document (C2)

**Files:**
- Create: `docs/SLO.md`

- [ ] **Step 1: Write the SLO document**

```markdown
# Nuzantara Service Level Objectives (SLO)

**Last Updated:** 2026-04-06
**Review Cadence:** Monthly

## Availability

| Service | Target | Measurement | Allowed Downtime/Year |
|---------|--------|-------------|----------------------|
| Backend API (nuzantara-rag) | 99.5% | Fly.io health checks (30s interval) | 43h 48min |
| Frontend (Vercel) | 99.9% | Vercel status page | 8h 46min |
| Database (PostgreSQL) | 99.5% | fly status checks | 43h 48min |
| Vector DB (Qdrant Cloud) | 99.5% | /healthz API check | 43h 48min |

## Latency

| Endpoint | p50 Target | p95 Target | p99 Target |
|----------|-----------|-----------|-----------|
| /health | <100ms | <500ms | <1s |
| /api/chat (RAG query) | <2s | <5s | <10s |
| /api/kbli/* | <500ms | <1s | <2s |
| Frontend page load | <2s | <4s | <8s |

## Recovery

| Metric | Target | Current |
|--------|--------|---------|
| MTTR (Mean Time To Recovery) | <15min | ~15-30min (auto-rollback helps) |
| Backup RTO (PostgreSQL) | <1h | Not tested (B2 adds verification) |
| Backup RTO (Qdrant) | <2h | Not tested |
| Backup RPO (data loss window) | <24h | 24h (daily backups) |

## Deploy

| Metric | Target |
|--------|--------|
| Deploy frequency | 1/day without fear |
| Deploy success rate | >95% |
| Rollback time | <5min (auto-rollback) |

## Error Budget

With 99.5% availability target:
- **Monthly budget:** 3h 39min downtime
- **Weekly budget:** ~50min downtime
- **If budget exhausted:** freeze non-critical deploys, focus on reliability

## Monitoring

| What | How | Alert |
|------|-----|-------|
| Backend health | fly-health-check.sh (*/30 cron) | Telegram |
| Deploy status | fly-deploy.yml post-deploy-health | Telegram |
| Backup status | fly-pg-backup.sh / fly-qdrant-backup.sh | Telegram |
| RAG quality | rag_canary.py (*/6h) | Telegram |
| SSL expiry | system_doctor.py (daily 08:00) | Telegram |
| Cost | cost-alert.sh (weekly) | Telegram |

## Budget Constraint

Infrastructure budget: $40-60/month. SLO targets are set for this budget level.
Multi-region, dedicated CPU, and higher availability targets require budget increase.
```

---

### Task 4: Create cost alerting script (C3)

**Files:**
- Create: `~/scripts/fly-cost-alert.sh`

- [ ] **Step 1: Create the cost alert script**

```bash
#!/usr/bin/env bash
# Fly.io Cost Alert — weekly check, alerts if cost exceeds threshold
# Run via cron: 0 9 * * 1 (Monday 09:00 WITA)
set -euo pipefail

THRESHOLD_CENTS=6000  # $60.00 — alert if monthly projection exceeds this
APP_LIST="nuzantara-rag nuzantara-postgres"
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-1125336968}"

# Load secrets
SECRETS_FILE="$HOME/.nuzantara-secrets.env"
[ -f "$SECRETS_FILE" ] && { set -a; source "$SECRETS_FILE"; set +a; }

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

send_alert() {
    if [[ -n "$TELEGRAM_BOT_TOKEN" ]]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_CHAT_ID}" \
            -d "text=$1" \
            -d "parse_mode=Markdown" > /dev/null 2>&1 || true
    fi
}

log "Checking Fly.io costs..."

# Get current month's invoice
INVOICE=$(fly bills view --json 2>/dev/null || echo '{}')

if [[ "$INVOICE" == '{}' ]]; then
    log "WARNING: Could not fetch billing info (fly bills may require org context)"
    # Fallback: check machine status for cost estimation
    TOTAL_MACHINES=0
    for app in $APP_LIST; do
        COUNT=$(fly status --app "$app" 2>/dev/null | grep -c "started" || echo "0")
        TOTAL_MACHINES=$((TOTAL_MACHINES + COUNT))
    done
    log "Active machines: $TOTAL_MACHINES (manual cost check recommended)"
    exit 0
fi

# Parse total from invoice (Fly.io returns cents)
TOTAL_CENTS=$(echo "$INVOICE" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('total_cents', d.get('amount', 0)))" 2>/dev/null || echo "0")
TOTAL_DOLLARS=$(echo "scale=2; $TOTAL_CENTS / 100" | bc)

log "Current month cost: \$$TOTAL_DOLLARS (threshold: \$$(echo "scale=2; $THRESHOLD_CENTS / 100" | bc))"

if [[ $TOTAL_CENTS -gt $THRESHOLD_CENTS ]]; then
    send_alert "💰 *Fly.io Cost Alert*%0A%0ACurrent: \$${TOTAL_DOLLARS}%0AThreshold: \$$(echo "scale=2; $THRESHOLD_CENTS / 100" | bc)%0A%0ACheck: fly bills view"
    log "ALERT: Cost exceeds threshold!"
else
    log "Cost within budget ✅"
fi

# Write state
mkdir -p ~/.agent/decisions/state
echo '{"job":"fly_cost_alert","ts":'$(date +%s)',"status":"ok","cost_cents":'$TOTAL_CENTS',"host":"'$(hostname -s)'"}' \
    > ~/.agent/decisions/state/fly_cost_alert.last.json
```

- [ ] **Step 2: Make executable and add to crontab**

```bash
chmod +x ~/scripts/fly-cost-alert.sh
# Add weekly Monday 09:00 WITA cron
(crontab -l 2>/dev/null; echo "0 9 * * 1 /bin/bash /Users/nuzantara/scripts/fly-cost-alert.sh >> /tmp/cron-fly-cost.log 2>&1") | crontab -
```

- [ ] **Step 3: Verify syntax**

```bash
bash -n ~/scripts/fly-cost-alert.sh && echo "Syntax OK"
```

---

### Task 5: Configure Dependabot (C4)

**Files:**
- Create: `.github/dependabot.yml`

- [ ] **Step 1: Create Dependabot configuration**

```yaml
# Dependabot security updates — weekly, grouped, auto-merge patch
version: 2
updates:
  # Python backend
  - package-ecosystem: "pip"
    directory: "/apps/backend-rag"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 5
    labels:
      - "dependencies"
      - "security"
    groups:
      minor-and-patch:
        update-types:
          - "minor"
          - "patch"

  # Node.js frontend
  - package-ecosystem: "npm"
    directory: "/apps/mouth"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 5
    labels:
      - "dependencies"
      - "security"
    groups:
      minor-and-patch:
        update-types:
          - "minor"
          - "patch"

  # GitHub Actions
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 3
    labels:
      - "dependencies"
      - "ci"
```

- [ ] **Step 2: Verify YAML syntax**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/dependabot.yml')); print('YAML OK')"
```

---

### Task 6: Add pre-deploy RAG smoke test (C5)

**Files:**
- Modify: `.github/workflows/fly-deploy.yml` (post-deploy-health job)

The current post-deploy-health job only checks `/health` returns "healthy". We'll add a RAG query smoke test.

- [ ] **Step 1: Read the post-deploy-health job**

Read `.github/workflows/fly-deploy.yml` and find the `post-deploy-health` job.

- [ ] **Step 2: Add RAG smoke test after health check passes**

After the existing health check loop succeeds, add a step:

```yaml
      - name: RAG smoke test
        if: success()
        run: |
          echo "Running RAG smoke test..."
          # Test a simple query against the live API
          RESPONSE=$(curl -sf --max-time 30 \
            -X POST "https://nuzantara-rag.fly.dev/api/chat/query" \
            -H "Content-Type: application/json" \
            -H "X-API-Key: ${{ secrets.SMOKE_TEST_API_KEY }}" \
            -d '{"query": "what is a PT PMA?", "channel": "smoke-test"}' \
            2>/dev/null || echo '{"error": "timeout"}')
          
          # Check response is not an error
          if echo "$RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'error' not in d or d.get('answer',''), 'No answer'" 2>/dev/null; then
            echo "✅ RAG smoke test passed"
          else
            echo "⚠️ RAG smoke test failed (non-blocking)"
            echo "Response: $RESPONSE"
          fi
        continue-on-error: true
```

Note: `continue-on-error: true` makes this non-blocking — a failed smoke test won't trigger rollback. It's informational.

- [ ] **Step 3: Verify YAML syntax**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/fly-deploy.yml')); print('YAML OK')"
```
