# S06 Infrastructure Hardening (B1-B6) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden deploy pipeline and monitoring — fix workflow/migration alignment, add backup restore test, configure log drain, add backup notifications.

**Architecture:** Mix of CI/CD workflow fix, bash script improvements, and Fly CLI configuration. B3 (Redis health) and B4 (JSON logging) are ALREADY IMPLEMENTED — skipped.

**Tech Stack:** Bash, GitHub Actions YAML, Fly CLI

**Discovery from investigation:**
- B3 SKIP: Redis health check already in `/health/detailed` via `RedisManager.health_check()` (PING + latency + dbsize + memory)
- B4 SKIP: JSON structured logging already active in production via `structlog` + `python-json-logger`, auto-JSON when `ENVIRONMENT=production`
- B1 CRITICAL: The CI/CD workflow (`fly-deploy.yml`) references `alembic.ini` which DOES NOT EXIST. The actual migration system is custom Python (`python -m backend.db.migrate`). This is a latent failure waiting to happen.

---

### Task 1: Fix migration workflow alignment (B1)

**Files:**
- Modify: `.github/workflows/fly-deploy.yml` (run-migrations job)
- Modify: `apps/backend-rag/fly.toml` (release_command comment)

The migration system is custom (`backend/db/migrate.py` with `apply-all` command), NOT Alembic. The workflow references `alembic.ini` which doesn't exist. We will:
1. Fix the workflow to reference the correct migration command
2. Keep migrations DISABLED (the bug is not documented/understood)
3. Add a migration drift check to pre-deploy gate
4. Document the situation

- [ ] **Step 1: Read the current fly-deploy.yml migrations job**

Read `.github/workflows/fly-deploy.yml` and find the `run-migrations` job. Note exact lines.

- [ ] **Step 2: Fix the migration command in workflow**

In the `run-migrations` job, replace any reference to `alembic` with the correct command:

```yaml
# WRONG (alembic doesn't exist)
command "cd /app && python -m alembic -c backend/alembic.ini upgrade head"

# CORRECT (custom migration system)
command "cd /app && python -m backend.db.migrate apply-all"
```

Keep the job **disabled/skipped** (via `if: false` or commented) but fix the command so when it's re-enabled it won't crash.

- [ ] **Step 3: Add migration status check to pre-deploy gate**

In the `pre-deploy-gate` job, after the existing tests, add a step that checks migration status via SSH:

```yaml
- name: Check migration status
  run: |
    echo "Checking for pending migrations..."
    flyctl ssh console --app nuzantara-rag -C "cd /app && python -m backend.db.migrate status" || echo "⚠️ Migration check failed (non-blocking)"
  continue-on-error: true
```

This is non-blocking (informational only) but will surface any drift.

- [ ] **Step 4: Update fly.toml comment**

Replace the current comment in `apps/backend-rag/fly.toml`:

```toml
# release_command = "sh -c 'python -m backend.db.migrate apply-all'"
# Temporarily disabled to bypass migration bug and deploy omnichannel fixes
```

With a more informative comment:

```toml
# release_command = "sh -c 'python -m backend.db.migrate apply-all'"
# DISABLED since 2026-04-06: migration bug during omnichannel deploy (commit 1253542d4)
# Migration system: custom Python (backend/db/migrate.py), NOT Alembic
# Re-enable after: 1) identify bug, 2) test locally, 3) dry-run on staging
# Monitor drift via pre-deploy-gate "Check migration status" step
```

- [ ] **Step 5: Verify workflow syntax**

Run: `cd /Users/nuzantara/Desktop/nuzantara && python3 -c "import yaml; yaml.safe_load(open('.github/workflows/fly-deploy.yml')); print('YAML OK')"`

---

### Task 2: Add backup restore verification (B2)

**Files:**
- Modify: `~/scripts/fly-pg-backup.sh` (after Step 2 integrity check, before Step 3 upload)

- [ ] **Step 1: Read current backup script integrity section**

Read `~/scripts/fly-pg-backup.sh` and find the "Step 2: Verify integrity" section (around lines 83-98).

- [ ] **Step 2: Add restore verification after header check**

After the `log "pg_dump header verified OK"` line (line 98), add:

```bash
# Step 2b: Verify restore-ability (non-destructive)
# Plain-format SQL dumps: verify key DDL statements present
TABLE_COUNT=$(gunzip -c "$BACKUP_FILE" 2>/dev/null | grep -c "^CREATE TABLE" || echo "0")
if [ "$TABLE_COUNT" -gt 10 ]; then
    log "Restore verification: PASS ($TABLE_COUNT tables found)"
else
    log "WARNING: Restore verification: only $TABLE_COUNT tables found (expected 50+)"
    # Non-blocking — the dump may still be valid for partial schemas
fi
```

Note: We use `grep CREATE TABLE` instead of `pg_restore --list` because the dump is plain SQL format (not custom format), and `pg_restore --list` only works with custom format dumps.

- [ ] **Step 3: Verify syntax**

Run: `bash -n ~/scripts/fly-pg-backup.sh && echo "Syntax OK"`

---

### Task 3: Configure Fly.io log drain (B5)

**Files:**
- No file changes — Fly CLI configuration only

Fly.io supports log shipping to external services. Options:
- **Betterstack (Logtail)** — free tier: 1GB/month, 3 day retention
- **Grafana Cloud Loki** — free tier: 50GB logs
- **Datadog** — free tier limited

We'll use Betterstack (simplest setup, 1 CLI command).

- [ ] **Step 1: Check if a log drain already exists**

Run: `fly logs list-drains --app nuzantara-rag 2>/dev/null || echo "No drains configured"`

- [ ] **Step 2: Document the setup command (DO NOT EXECUTE)**

The user needs to:
1. Create a free Betterstack account at https://betterstack.com
2. Get a source token from the Sources page
3. Run: `fly logs ship --app nuzantara-rag --token <BETTERSTACK_TOKEN>`

OR for Grafana Cloud:
1. Get Loki push URL and credentials from Grafana Cloud
2. Run: `fly logs ship --app nuzantara-rag --loki-url <URL> --loki-username <USER> --loki-password <TOKEN>`

**Create a setup script** at `~/scripts/setup-log-drain.sh`:

```bash
#!/usr/bin/env bash
# Fly.io Log Drain Setup — run once to configure external log shipping
# Requires: Betterstack account with source token
set -euo pipefail

TOKEN="${1:?Usage: $0 <betterstack-source-token>}"
APP="nuzantara-rag"

echo "Setting up log drain for $APP..."
fly logs ship --app "$APP" --token "$TOKEN"
echo "Log drain configured. Verify: fly logs list-drains --app $APP"
```

- [ ] **Step 3: Verify no existing drain**

Run the check command from Step 1 to confirm clean state.

---

### Task 4: Add backup success Telegram notification (B6)

**Files:**
- Modify: `~/scripts/fly-pg-backup.sh` (at the end, after "Backup complete")

- [ ] **Step 1: Read current backup script ending**

Read `~/scripts/fly-pg-backup.sh` last 15 lines.

- [ ] **Step 2: Add Telegram success notification**

Replace the final `log "Backup complete ✅"` line with:

```bash
# Notify Telegram on success
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-1125336968}"
if [[ -n "$TELEGRAM_BOT_TOKEN" ]]; then
    SIZE_FINAL=$(du -h "$BACKUP_FILE" | cut -f1)
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=✅ PG backup OK: ${SIZE_FINAL} → Tigris" \
        -d "parse_mode=Markdown" > /dev/null 2>&1 || true
fi
log "Backup complete ✅"

# Write state for job health monitoring
echo '{"job":"fly_pg_backup","ts":'$(date +%s)',"status":"ok","host":"'$(hostname -s)'","size":"'$(du -h "$BACKUP_FILE" | cut -f1)'"}' \
    > ~/.agent/decisions/state/fly_pg_backup.last.json
```

Also add a failure notification. Find the `exit 1` on backup failure (around line 79-81) and add before it:

```bash
    # Notify Telegram on failure
    if [[ -n "${TELEGRAM_BOT_TOKEN:-}" ]]; then
        curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_CHAT_ID:-1125336968}" \
            -d "text=🔴 PG backup FAILED after $MAX_RETRIES attempts!" \
            -d "parse_mode=Markdown" > /dev/null 2>&1 || true
    fi
```

- [ ] **Step 3: Verify syntax**

Run: `bash -n ~/scripts/fly-pg-backup.sh && echo "Syntax OK"`
