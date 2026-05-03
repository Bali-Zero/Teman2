# Operations Runbook — Nuzantara

**Last Updated:** 2026-02-26
**On-call:** Bali Zero AI Team
**Production URL:** https://nuzantara-rag.fly.dev
**Frontend URL:** https://kita.balizero.com

---

## Quick Reference Commands

```bash
# Health check
curl -s https://nuzantara-rag.fly.dev/health | python3 -m json.tool

# Detailed health
curl -s https://nuzantara-rag.fly.dev/health/detailed | python3 -m json.tool

# Logs (live tail)
fly logs -a nuzantara-rag

# App status
fly status -a nuzantara-rag

# SSH into machine
fly ssh console -a nuzantara-rag

# Secrets
fly secrets list -a nuzantara-rag

# Deploy (rolling, zero-downtime)
fly deploy -a nuzantara-rag --strategy rolling

# Emergency rollback
fly releases -a nuzantara-rag          # find previous release
fly deploy -a nuzantara-rag --image registry.fly.io/nuzantara-rag:deployment-<ID>
```

---

## Table of Contents

1. [Service Health States](#1-service-health-states)
2. [Incident: App Won't Start / Crash Loop](#2-incident-app-wont-start--crash-loop)
3. [Incident: High Latency / Slow Responses](#3-incident-high-latency--slow-responses)
4. [Incident: ABSTAIN on All Queries](#4-incident-abstain-on-all-queries)
5. [Incident: Qdrant Connection Failure](#5-incident-qdrant-connection-failure)
6. [Incident: Database Connection Failure](#6-incident-database-connection-failure)
7. [Incident: Google Drive 500 Errors](#7-incident-google-drive-500-errors)
8. [Incident: Rogue AI Code Changes](#8-incident-rogue-ai-code-changes)
9. [Incident: OOM Kill](#9-incident-oom-kill)
10. [Incident: Embedding Model Mismatch](#10-incident-embedding-model-mismatch)
11. [Incident: Channel Webhook Down](#11-incident-channel-webhook-down)
12. [Pre-Deploy Checklist](#12-pre-deploy-checklist)
13. [Scheduled Jobs Reference](#13-scheduled-jobs-reference)
14. [Monitoring Endpoints](#14-monitoring-endpoints)
15. [Secret Rotation Procedures](#15-secret-rotation-procedures)

---

## 1. Service Health States

`GET /health` returns one of these states:

| Status         | Meaning                                         | Action                            |
| -------------- | ----------------------------------------------- | --------------------------------- |
| `initializing` | Server started, services loading                | Wait 60s, then check again        |
| `healthy`      | All critical services operational               | None                              |
| `degraded`     | Non-critical service failed (DB, memory, cache) | Monitor, investigate non-critical |
| `critical`     | Search or AI service failed                     | **Immediate investigation**       |

**Critical services** (failure → `critical`): `search`, `ai`
**Non-critical services** (failure → `degraded`): `database`, `memory`, `router`, `health_monitor`, `query_cache`, `rate_limiter`, `kg_langgraph`

**Readiness probe** (`/health/ready`): Returns 503 until `search_service`, `ai_client`, and `services_initialized` are all set. Fly.io won't route traffic until this returns 200.

---

## 2. Incident: App Won't Start / Crash Loop

**Symptoms:** Fly.io shows machines restarting. Health check fails. Logs show Python tracebacks.

### Diagnosis

```bash
# Check recent logs for the crash
fly logs -a nuzantara-rag | head -100

# Check machine status
fly status -a nuzantara-rag
```

### Common Causes

**A. Missing import (most common)**

- **Cause:** A rogue AI refactor removed an import (e.g., `Any` from `typing`)
- **Indicator:** `ImportError` or `NameError` in logs
- **Fix:**

  ```bash
  # Identify the broken import
  cd apps/backend-rag && source venv/bin/activate
  python -c "from backend.app.dependencies import get_current_user; print('OK')"

  # If that fails, check what changed
  git diff HEAD~5 -- backend/app/dependencies.py
  git checkout HEAD~1 -- backend/app/dependencies.py  # restore from previous commit
  ```

**B. OOM Kill**

- **Indicator:** Machine restarts with no Python traceback in logs
- **Fix:** See [Incident: OOM Kill](#9-incident-oom-kill)

**C. Missing secret**

- **Indicator:** `KeyError` or `ValueError("... not set")` in logs
- **Fix:**
  ```bash
  fly secrets list -a nuzantara-rag
  # Compare with required: DATABASE_URL, QDRANT_URL, QDRANT_API_KEY, OPENAI_API_KEY, JWT_SECRET
  fly secrets set MISSING_SECRET="value" -a nuzantara-rag
  ```

**D. Database migration issue**

- **Indicator:** `UndefinedTable` or `column does not exist` errors
- **Fix:** Run migration manually via SSH
  ```bash
  fly ssh console -a nuzantara-rag
  python -m backend.db.migrate apply-all
  ```

### Recovery

If the above don't help, rollback:

```bash
fly releases -a nuzantara-rag
# Find the last working release number
fly deploy -a nuzantara-rag --image registry.fly.io/nuzantara-rag:deployment-<PREVIOUS_ID>
```

---

## 3. Incident: High Latency / Slow Responses

**Symptoms:** Chat responses take >10s. Users report timeouts.

### Diagnosis

```bash
# Check latency metrics
curl -s https://nuzantara-rag.fly.dev/api/monitoring/latency?days=1

# Check logs for slow queries
fly logs -a nuzantara-rag | grep "slow\|timeout\|latency"

# Check machine resource usage
fly status -a nuzantara-rag
```

### Common Causes

| Cause                        | Indicator                 | Fix                                            |
| ---------------------------- | ------------------------- | ---------------------------------------------- |
| Gemini API slow              | `LLMGateway` timeout logs | Wait (transient) or switch to Flash-Lite       |
| Qdrant overloaded            | `qdrant` timeout in logs  | Check Qdrant health, restart if needed         |
| PostgreSQL slow              | `asyncpg` timeout logs    | Check connection pool, run `VACUUM ANALYZE`    |
| Redis down                   | Cache miss rate spike     | Check Redis connection, fall back to no-cache  |
| Too many concurrent requests | 429 responses in logs     | Scale up: `fly scale count 2 -a nuzantara-rag` |

### Alert Thresholds

Default thresholds (configurable via `/api/monitoring/alert-threshold`):

- Max latency: 5000ms
- Max ABSTAIN rate: 20%
- Min cache hit rate: 50%
- Min retrieval quality: 0.3

---

## 4. Incident: ABSTAIN on All Queries

**Symptoms:** AI refuses to answer most queries. Users see "I don't have enough information" responses.

### Diagnosis

```bash
fly logs -a nuzantara-rag | grep -E "Evidence|ABSTAIN|evidence_score"
```

### Common Causes

**A. Qdrant connection failure**

- Evidence score = 0.0 because no documents retrieved
- Fix: Restart Qdrant or check `QDRANT_URL` secret

**B. Embedding model mismatch**

- Query embeddings don't match stored embeddings
- Fix: See [Incident: Embedding Model Mismatch](#10-incident-embedding-model-mismatch)

**C. Evidence scoring bug**

- The tools-available bypass was removed/broken
- Check: `reasoning.py` lines 867-883 must have the trusted tools check
- Fix: Restore from last known good commit

### Key Thresholds

- `< 0.15` → ABSTAIN (refuse to answer)
- `0.15 - 0.60` → CAUTIOUS (answer with disclaimer)
- `> 0.60` → NORMAL (confident answer)

Trusted tools that bypass evidence check: `calculator`, `get_pricing`, `team_knowledge`

---

## 5. Incident: Qdrant Connection Failure

**Symptoms:** Search returns empty results. Health check shows `search: critical`.

### Diagnosis

```bash
# Check Qdrant health
curl -s https://nuzantara-rag.fly.dev/health/metrics/qdrant

# Check from inside the machine
fly ssh console -a nuzantara-rag
curl -s $QDRANT_URL/collections | python3 -m json.tool
```

### Fix

```bash
# If Qdrant is a Fly.io app
fly status -a nuzantara-qdrant
fly restart -a nuzantara-qdrant

# If Qdrant secret changed
fly secrets set QDRANT_URL="new-url" QDRANT_API_KEY="new-key" -a nuzantara-rag
```

### Expected Collections

| Collection                 | Vectors  | Purpose                            |
| -------------------------- | -------- | ---------------------------------- |
| `bali_zero_kb`             | ~40,000  | Main knowledge base                |
| `kbli_2025_final`          | ~1,563   | KBLI business codes (FLAT payload) |
| `bali_zero_pricing_hybrid` | ~500     | Pricing data                       |
| `portal_documents`         | variable | Client documents                   |
| + 3 others                 | ~16,000  | Various domain collections         |

---

## 6. Incident: Database Connection Failure

**Symptoms:** CRM, conversations, analytics fail. Health shows `database: degraded`.

### Diagnosis

```bash
fly ssh console -a nuzantara-rag
python3 -c "
import asyncio, asyncpg, os
async def check():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])
    print(await conn.fetchval('SELECT 1'))
    await conn.close()
asyncio.run(check())
"
```

### Common Causes

| Cause                     | Fix                                    |
| ------------------------- | -------------------------------------- |
| Connection pool exhausted | Restart app (frees all connections)    |
| PostgreSQL down           | Check Fly.io Postgres app status       |
| `DATABASE_URL` rotated    | Update secret with new URL             |
| SSL certificate expired   | Regenerate Fly.io Postgres certificate |

---

## 7. Incident: Google Drive 500 Errors

**Symptoms:** Document upload fails. Portal documents page errors. Drive folder creation fails.

**Last occurrence:** 2026-01-23

### Diagnosis

```bash
fly logs -a nuzantara-rag | grep -i "drive\|google\|service.account"

# Check Drive health
curl -s https://nuzantara-rag.fly.dev/api/admin/drive/health
```

### Common Causes

| Cause                       | Fix                                         |
| --------------------------- | ------------------------------------------- |
| Service account disabled    | Re-enable in Google Cloud Console           |
| OAuth token expired         | POST `/api/admin/drive/refresh`             |
| Service account key rotated | Update `GOOGLE_SERVICE_ACCOUNT_JSON` secret |
| Quota exceeded              | Wait or request quota increase              |

### Fix Procedure

```bash
# 1. Check current status
curl -s https://nuzantara-rag.fly.dev/api/admin/drive/status

# 2. If token expired, refresh
curl -X POST https://nuzantara-rag.fly.dev/api/admin/drive/refresh

# 3. If service account key needs rotation
fly secrets set GOOGLE_SERVICE_ACCOUNT_JSON="$(cat new-credentials.json)" -a nuzantara-rag
```

Service account: `nuzantara-drive-bot@nuzantara.iam.gserviceaccount.com`

---

## 8. Incident: Rogue AI Code Changes

**Symptoms:** Unexpected changes in `git diff`. Import errors after another AI tool modified files. Production crash after deploy.

**Last occurrence:** 2026-02-16 (10 files had `Any` removed from typing imports)

### Prevention

```bash
# ALWAYS run before deploy
git diff --name-only HEAD -- apps/backend-rag/backend/

# Test critical import chain
cd apps/backend-rag && source venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('OK')"
```

### Recovery

```bash
# Option A: Restore entire backend directory
git checkout HEAD -- apps/backend-rag/backend/
# Then re-apply only your targeted changes

# Option B: Restore specific files
git checkout HEAD -- apps/backend-rag/backend/app/dependencies.py
git checkout HEAD -- apps/backend-rag/backend/services/__init__.py

# Option C: Revert to previous commit
git revert <bad-commit-hash>
```

### Known Rogue Patterns

| AI Tool  | Common Damage                                |
| -------- | -------------------------------------------- |
| Gemini   | Removes "unused" imports (`Any`, `Optional`) |
| Windsurf | Renames/deletes helper functions             |
| Cursor   | Deletes entire service modules               |

---

## 9. Incident: OOM Kill

**Symptoms:** Machine restarts with no Python traceback. Fly.io dashboard shows memory spike to 100%.

### Diagnosis

```bash
fly status -a nuzantara-rag
# Look for "OOM" in events

fly logs -a nuzantara-rag | grep -i "oom\|killed\|memory"
```

### Root Cause

Each uvicorn worker loads ~2GB of ML models. With a 2GB VM:

- 1 worker: ~1.8GB total (tight but stable with lazy loading)
- 2 workers: ~3.5GB total (OOM kill on 2GB VM)

### Fix

1. **Verify Dockerfile has `--workers 1`** (not 2)
2. **If memory grew over time** (memory leak):
   ```bash
   fly restart -a nuzantara-rag
   ```
3. **If needs more capacity**: Scale VM, not workers
   ```bash
   fly scale vm shared-cpu-4x -a nuzantara-rag  # upgrades to 8GB
   # Only THEN can you use --workers 2
   ```

---

## 10. Incident: Embedding Model Mismatch

**Symptoms:** Search returns irrelevant results. High ABSTAIN rate. Cosine similarity scores near 0.

### Diagnosis

```bash
# Check running model
curl -s https://nuzantara-rag.fly.dev/health | python3 -m json.tool | grep model

# Check Fly.io secret
fly secrets list -a nuzantara-rag | grep EMBEDDING
```

**Must be:** `text-embedding-3-small`

### Fix

```bash
fly secrets set EMBEDDING_MODEL=text-embedding-3-small -a nuzantara-rag
```

**WARNING:** If someone switched to a different model AND re-ingested data, you need to re-ingest with the correct model. This affects all 58,880 vectors across 7 collections.

---

## 11. Incident: Channel Webhook Down

**Symptoms:** Telegram/WhatsApp/Instagram bot not responding. Messages sent but no replies.

### Diagnosis

```bash
# Check webhook endpoints
curl -s https://nuzantara-rag.fly.dev/health

# Check specific channel logs
fly logs -a nuzantara-rag | grep -i "telegram\|whatsapp\|instagram"
```

### Channel-Specific Fixes

**Telegram:**

```bash
# Re-register webhook
curl "https://api.telegram.org/bot${TELEGRAM_TOKEN}/setWebhook?url=https://nuzantara-rag.fly.dev/api/telegram/webhook"
```

**WhatsApp:**

- Check Meta Business Manager webhook configuration
- Verify `WHATSAPP_VERIFY_TOKEN` matches Meta configuration

**Instagram:**

- Check Meta Developer Dashboard webhook subscription
- Verify app is in Live mode (not Development)

---

## 12. Pre-Deploy Checklist

```bash
# 1. Check for unexpected changes
git diff --name-only HEAD -- apps/backend-rag/backend/

# 2. Test critical import chain (MUST pass)
cd apps/backend-rag && source venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('OK')"

# 3. Run core tests (82 tests, <15s)
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_langgraph.py \
  backend/tests/services/rag/test_kg_subgraphs.py \
  backend/tests/services/rag/test_confidence.py -q

# 4. Deploy with rolling strategy
fly deploy -a nuzantara-rag --strategy rolling

# 5. Post-deploy health check (wait 60s for init)
sleep 60
curl -s https://nuzantara-rag.fly.dev/health | python3 -m json.tool
curl -s https://nuzantara-rag.fly.dev/health/ready

# 6. Smoke test (send a chat query)
curl -X POST https://nuzantara-rag.fly.dev/api/agentic-rag/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is a PT PMA?", "session_id": "deploy-test"}'
```

**Known test debt:** Cleaned 2026-03-20 (0 failures). Previously ~448 pre-existing failures from rogue AI refactors, resolved by Windsurf cleanup.

---

## 13. Scheduled Jobs Reference

| Job                        | Interval           | Timezone             | Description                      |
| -------------------------- | ------------------ | -------------------- | -------------------------------- |
| `self_healing`             | 5 min              | UTC                  | Backend self-diagnostics         |
| `conversation_trainer`     | 6 hours            | UTC                  | Train conversation models        |
| `golden_routes_seeder`     | One-time (startup) | —                    | Seed KG golden routes            |
| `renewal_alerts`           | 12 hours           | UTC                  | Check practice renewals          |
| `birthday_notifier`        | 24 hours           | UTC                  | Send birthday notifications      |
| `conversation_cleanup`     | 24 hours           | UTC                  | GDPR: anonymize >7d, delete >30d |
| `daily_notification_check` | 9:00 AM            | Asia/Makassar (WITA) | Check expiring practices         |
| `hourly_pending_send`      | Every hour         | Asia/Makassar        | Send pending notifications       |

**Leader election:** Redis `SET NX EX` ensures only one Fly.io machine runs each task. Falls back to all machines if Redis unavailable.

**Task timeout:** 30 minutes hard limit per task.

---

## 14. Monitoring Endpoints

| Endpoint                                | Auth   | Description                 |
| --------------------------------------- | ------ | --------------------------- |
| `GET /health`                           | Public | Basic health (Fly.io probe) |
| `GET /health/detailed`                  | Public | Per-service breakdown       |
| `GET /health/ready`                     | Public | Readiness probe             |
| `GET /health/live`                      | Public | Liveness probe              |
| `GET /health/metrics/qdrant`            | Public | Qdrant metrics              |
| `GET /health/kg-stats`                  | Public | KG node/edge counts         |
| `GET /metrics`                          | Public | Prometheus metrics          |
| `GET /api/monitoring/retrieval-quality` | Admin  | RAG quality scores          |
| `GET /api/monitoring/abstain-rate`      | Admin  | ABSTAIN rate                |
| `GET /api/monitoring/latency`           | Admin  | Latency percentiles         |

### Key Prometheus Metrics

| Metric                             | Type      | Description                             |
| ---------------------------------- | --------- | --------------------------------------- |
| `zantara_http_requests_total`      | Counter   | Total requests (method/endpoint/status) |
| `zantara_request_duration_seconds` | Histogram | Request latency                         |
| `zantara_ai_requests_total`        | Counter   | LLM calls (by model)                    |
| `zantara_ai_latency_seconds`       | Histogram | LLM latency                             |
| `zantara_llm_cost_usd_total`       | Counter   | LLM spend in USD                        |
| `zantara_cache_hits_total`         | Counter   | Cache hits                              |
| `zantara_cache_misses_total`       | Counter   | Cache misses                            |
| `zantara_db_connections_active`    | Gauge     | Active DB connections                   |

---

## 15. Secret Rotation Procedures

### OpenAI API Key

```bash
# 1. Generate new key in OpenAI dashboard
# 2. Set in Fly.io (zero-downtime — new requests use new key)
fly secrets set OPENAI_API_KEY="sk-new-key" -a nuzantara-rag
```

### Google Service Account

```bash
# 1. Create new key in Google Cloud Console
# 2. Update secret
fly secrets set GOOGLE_SERVICE_ACCOUNT_JSON="$(cat new-key.json)" -a nuzantara-rag
# 3. Verify Drive works
curl -s https://nuzantara-rag.fly.dev/api/admin/drive/health
```

### JWT Secret

```bash
# WARNING: Rotating JWT_SECRET invalidates ALL existing user sessions
fly secrets set JWT_SECRET="new-secret-value" -a nuzantara-rag
# Users will need to re-login
```

### Database URL

```bash
# If PostgreSQL credentials change
fly secrets set DATABASE_URL="postgres://user:pass@host:5432/db?sslmode=require" -a nuzantara-rag
```
