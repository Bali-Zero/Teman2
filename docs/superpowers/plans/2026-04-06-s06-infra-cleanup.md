# S06 Infrastructure Cleanup (A1-A5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 5 security and monitoring gaps in deploy infrastructure scripts

**Architecture:** Pure script fixes — no backend code changes, no deploys. All changes in `~/scripts/` (Pro machine) and crontab.

**Tech Stack:** Bash, crontab, curl

**Constraints:**
- Scripts are in `~/scripts/` (NOT in git repo) — no commits needed
- `fly-pg-backup.sh` already uses secrets file pattern — align `fly-qdrant-backup.sh` to match
- Health check runs on Pro crontab, not Air
- `~/.nuzantara-secrets.env` already exists (578 bytes, mode 600)

---

### Task 1: Remove hardcoded Tigris credentials from fly-qdrant-backup.sh

**Files:**
- Modify: `~/scripts/fly-qdrant-backup.sh:25-29`
- Verify: `~/.nuzantara-secrets.env` has AWS keys

- [ ] **Step 1: Verify secrets file has the needed keys**

Run: `grep -c "AWS_ACCESS_KEY_ID\|AWS_SECRET_ACCESS_KEY" ~/.nuzantara-secrets.env`
Expected: `2` (both keys present)

- [ ] **Step 2: Replace hardcoded Tigris credentials with secrets-file pattern**

Replace lines 25-29 of `~/scripts/fly-qdrant-backup.sh`:

```bash
# BEFORE (hardcoded fallback)
# Tigris credentials (same as pg backup)
TIGRIS_ENDPOINT="https://fly.storage.tigris.dev"
TIGRIS_BUCKET="nuzantara-backups"
TIGRIS_KEY="${AWS_ACCESS_KEY_ID:-tid_sZQYyrgouAXAdQDuvsfPlLIIUMMvEDNhfMWmzCdeouELsPMn_U}"
TIGRIS_SECRET="${AWS_SECRET_ACCESS_KEY:-tsec_5knItu7FoHkkv2P5qaEMSRdHxXDNb6ZD0+mgDfLsLF-lLntRwDUgrH4qmzhJX+3OI4XYTc}"
```

Replace with:

```bash
# Load secrets (same pattern as fly-pg-backup.sh)
SECRETS_FILE="$HOME/.nuzantara-secrets.env"
[ -f "$SECRETS_FILE" ] && { set -a; source "$SECRETS_FILE"; set +a; }

# Tigris credentials (from env — fail fast if missing)
TIGRIS_ENDPOINT="https://fly.storage.tigris.dev"
TIGRIS_BUCKET="nuzantara-backups"
TIGRIS_KEY="${AWS_ACCESS_KEY_ID:?Missing AWS_ACCESS_KEY_ID in $SECRETS_FILE}"
TIGRIS_SECRET="${AWS_SECRET_ACCESS_KEY:?Missing AWS_SECRET_ACCESS_KEY in $SECRETS_FILE}"
```

- [ ] **Step 3: Dry-run the script to verify secrets load**

Run: `bash -n ~/scripts/fly-qdrant-backup.sh && echo "Syntax OK"`
Expected: `Syntax OK`

Run: `source ~/.nuzantara-secrets.env && bash -c 'source ~/scripts/fly-qdrant-backup.sh' 2>&1 | head -5`
(Will fail at Qdrant API call, but should NOT fail at credential loading)

---

### Task 2: Add real Qdrant Cloud health check

**Files:**
- Modify: `~/scripts/fly-health-check.sh:32-34`

- [ ] **Step 1: Get Qdrant URL and API key location**

Run: `grep "^QDRANT_URL=" ~/Desktop/nuzantara/apps/backend-rag/.env | head -1`
Run: `grep "^QDRANT_API_KEY=" ~/Desktop/nuzantara/apps/backend-rag/.env | head -c 30`
(Just verify they exist — don't print full key)

- [ ] **Step 2: Add secrets loading and real Qdrant check**

In `~/scripts/fly-health-check.sh`, after line 9 (`LOG_FILE=...`), add secrets + Qdrant env loading:

```bash
# Load secrets + Qdrant credentials
SECRETS_FILE="$HOME/.nuzantara-secrets.env"
[ -f "$SECRETS_FILE" ] && { set -a; source "$SECRETS_FILE"; set +a; }
QDRANT_ENV="$HOME/Desktop/nuzantara/apps/backend-rag/.env"
if [[ -f "$QDRANT_ENV" ]]; then
    QDRANT_URL=$(grep '^QDRANT_URL=' "$QDRANT_ENV" | cut -d= -f2-)
    QDRANT_API_KEY=$(grep '^QDRANT_API_KEY=' "$QDRANT_ENV" | cut -d= -f2-)
fi
```

Then replace lines 33-34:

```bash
# BEFORE
# Qdrant migrated off Fly.io (nuzantara-qdrant is suspended) — check via RAG /health instead
QDRANT="OK"  # Qdrant health checked indirectly via RAG backend health endpoint
```

With:

```bash
# Qdrant Cloud direct health check
if [[ -n "${QDRANT_URL:-}" && -n "${QDRANT_API_KEY:-}" ]]; then
    QDRANT_HTTP=$(curl -sf -o /dev/null -w "%{http_code}" -H "api-key: $QDRANT_API_KEY" "${QDRANT_URL}/healthz" --max-time 10 2>/dev/null || echo "000")
    if [[ "$QDRANT_HTTP" == "200" ]]; then
        QDRANT="OK"
    else
        QDRANT="FAIL:$QDRANT_HTTP"
    fi
else
    QDRANT="OK"  # credentials not available, trust RAG /health
fi
```

- [ ] **Step 3: Verify syntax**

Run: `bash -n ~/scripts/fly-health-check.sh && echo "Syntax OK"`
Expected: `Syntax OK`

---

### Task 3: Add Redis health check

**Files:**
- Modify: `~/scripts/fly-health-check.sh` (after Qdrant check, before FAILURES block)

- [ ] **Step 1: Find Redis URL**

Run: `grep "REDIS_URL\|UPSTASH" ~/Desktop/nuzantara/apps/backend-rag/.env | head -3`
(Need to know the Redis provider to pick the right health check method)

- [ ] **Step 2: Add Redis check**

After the Qdrant check block, before `FAILURES=""`, add:

```bash
# Redis health check
REDIS_URL_ENV=$(grep '^REDIS_URL=' "$QDRANT_ENV" 2>/dev/null | cut -d= -f2- || echo "")
if [[ -n "$REDIS_URL_ENV" ]]; then
    # Extract host:port from redis:// URL for a TCP check
    REDIS_HOST=$(echo "$REDIS_URL_ENV" | sed -E 's|^rediss?://([^:@]*:)?([^@]*@)?||; s|/.*||; s|:.*||')
    REDIS_PORT=$(echo "$REDIS_URL_ENV" | sed -E 's|.*:([0-9]+).*|\1|')
    REDIS_PORT="${REDIS_PORT:-6379}"
    if nc -z -w5 "$REDIS_HOST" "$REDIS_PORT" 2>/dev/null; then
        REDIS="OK"
    else
        REDIS="FAIL:unreachable"
    fi
else
    REDIS="SKIP"
fi
```

And add to the FAILURES block (after line 40 `[ "$PG" = "0" ]...`):

```bash
[ "$REDIS" = "FAIL:unreachable" ] && FAILURES="${FAILURES}Redis: unreachable\n"
```

- [ ] **Step 3: Verify syntax**

Run: `bash -n ~/scripts/fly-health-check.sh && echo "Syntax OK"`
Expected: `Syntax OK`

---

### Task 4: Extend health check to 24h

**Files:**
- Modify: Pro crontab

- [ ] **Step 1: Show current crontab entry**

Run: `crontab -l | grep fly-health`
Expected: `*/30 7-19 * * * /bin/bash /Users/nuzantara/scripts/fly-health-check.sh >> /tmp/cron-fly-health.log 2>&1`

- [ ] **Step 2: Update crontab to run 24h**

Run:
```bash
crontab -l | sed 's|^\*/30 7-19 \* \* \* /bin/bash .*/fly-health-check.sh|*/30 * * * * /bin/bash /Users/nuzantara/scripts/fly-health-check.sh|' | crontab -
```

- [ ] **Step 3: Verify new crontab**

Run: `crontab -l | grep fly-health`
Expected: `*/30 * * * * /bin/bash /Users/nuzantara/scripts/fly-health-check.sh >> /tmp/cron-fly-health.log 2>&1`

---

### Task 5: Verify .dockerignore (training-data)

**Files:**
- Verify: `apps/backend-rag/.dockerignore`
- Verify: `apps/backend-rag/training-data/`

- [ ] **Step 1: Check if training-data is referenced anywhere in backend code**

Run: `grep -rn "training.data\|training_data" apps/backend-rag/backend/ --include="*.py" | head -10`
Expected: No matches (already verified — training-data is NOT imported by any Python code)

- [ ] **Step 2: Check Docker image size impact**

`training-data/` is 1MB with 5 subdirs (business, customs, legal, licenses, realestate). At 1MB this is negligible — NOT worth removing from .dockerignore as it may be used for future fine-tuning data or loaded by scripts at runtime.

**Decision: NO CHANGE needed.** The 1MB cost is trivial. A5 is a non-issue.

---

### Task 6: End-to-end verification

- [ ] **Step 1: Run health check manually**

Run: `bash ~/scripts/fly-health-check.sh 2>&1`
Expected: `✅ All services healthy` (with Qdrant and Redis now checked)

- [ ] **Step 2: Verify qdrant backup script loads secrets correctly**

Run: `bash -x ~/scripts/fly-qdrant-backup.sh 2>&1 | head -20`
Expected: Should show `SECRETS_FILE` sourced, no hardcoded credentials in trace

- [ ] **Step 3: Check log output**

Run: `tail -5 /tmp/cron-fly-health.log`
Expected: Latest entry shows all checks passing
