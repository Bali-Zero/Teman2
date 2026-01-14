# Safe Deploy Guide - Nuzantara Platform

**Version:** 1.0.0  
**Last Updated:** 2026-01-13  
**Author:** Nuzantara Team

---

## 📖 Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [How It Works](#how-it-works)
4. [Command Options](#command-options)
5. [Safety Mechanisms](#safety-mechanisms)
6. [Common Scenarios](#common-scenarios)
7. [Troubleshooting](#troubleshooting)
8. [Best Practices](#best-practices)
9. [Technical Details](#technical-details)

---

## Overview

The **Safe Deploy Script** (`safe-deploy.sh`) is a deployment automation tool that adds critical safety nets to manual deployments without sacrificing developer control. It provides:

- ✅ **Automated pre-deployment testing**
- ✅ **Automatic database backups**
- ✅ **Post-deployment health verification**
- ✅ **Automatic rollback on failure**
- ✅ **Comprehensive logging**
- ✅ **Full transparency and control**

### Philosophy

> **Manual deploy control + Automated safety nets = Best of both worlds**

You maintain full control over *when* to deploy, while the script ensures *how* it's done safely.

---

## Quick Start

### Basic Usage

```bash
# From project root
./scripts/safe-deploy.sh
```

That's it! The script will:
1. ✅ Run tests
2. ✅ Create database backup
3. ✅ Deploy to Fly.io
4. ✅ Verify health
5. ✅ Rollback automatically if anything fails

### First Time Setup

```bash
# 1. Ensure scripts are executable
chmod +x scripts/safe-deploy.sh
chmod +x scripts/backup-db.sh

# 2. Test with dry-run mode
./scripts/safe-deploy.sh --dry-run

# 3. Verify you're authenticated with Fly.io
flyctl auth whoami

# 4. Run your first safe deploy!
./scripts/safe-deploy.sh
```

---

## How It Works

### Deployment Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        SAFE DEPLOY FLOW                         │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
                     ┌─────────────────┐
                     │  Pre-Flight     │
                     │  Checks         │
                     │  • Git status   │
                     │  • Fly.io auth  │
                     │  • App exists   │
                     └────────┬────────┘
                              │
                              ▼
                     ┌─────────────────┐
                     │  Run Tests      │
                     │  • Unit tests   │
                     │  • Integration  │
                     └────────┬────────┘
                              │
                    ┌─────────┴─────────┐
                    │ Tests Pass?       │
                    └─────┬───────┬─────┘
                          │       │
                       NO │       │ YES
                          │       │
                    ┌─────▼────┐  │
                    │  ABORT   │  │
                    └──────────┘  │
                                  ▼
                         ┌─────────────────┐
                         │  Backup DB      │
                         │  • pg_dump      │
                         │  • Compress     │
                         │  • Store        │
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │  Deploy to      │
                         │  Fly.io         │
                         │  • Build        │
                         │  • Push         │
                         │  • Release      │
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │  Health Check   │
                         │  • Wait 30s     │
                         │  • Test /health │
                         │  • 6 retries    │
                         └────────┬────────┘
                                  │
                        ┌─────────┴─────────┐
                        │ Healthy?          │
                        └─────┬───────┬─────┘
                              │       │
                           NO │       │ YES
                              │       │
                     ┌────────▼────┐  │
                     │  ROLLBACK   │  │
                     │  • Revert   │  │
                     │  • Verify   │  │
                     └─────────────┘  │
                                      ▼
                             ┌─────────────────┐
                             │  SUCCESS!       │
                             │  • Version      │
                             │  • Duration     │
                             │  • Next steps   │
                             └─────────────────┘
```

### Time Breakdown

| Phase | Duration | Skippable |
|-------|----------|-----------|
| Pre-flight checks | ~5s | No |
| Test execution | ~30-60s | Yes (`--skip-tests`) |
| Database backup | ~10-20s | Yes (`--skip-backup`) |
| Deploy to Fly.io | ~2-3 min | No |
| Health check | ~30-60s | No |
| **Total** | **~4-5 min** | - |

---

## Command Options

### All Options

```bash
./scripts/safe-deploy.sh [OPTIONS]
```

| Option | Description | Use Case |
|--------|-------------|----------|
| `--skip-tests` | Skip test execution | Tests already run locally |
| `--skip-backup` | Skip database backup | No schema changes expected |
| `--no-rollback` | Disable auto-rollback | Manual recovery preferred |
| `--dry-run` | Simulate without executing | Test script changes |
| `-h, --help` | Show help message | Learn available options |

### Examples

```bash
# Standard deploy (recommended)
./scripts/safe-deploy.sh

# Quick deploy (tests already passed locally)
./scripts/safe-deploy.sh --skip-tests

# Emergency deploy (no time for backup)
./scripts/safe-deploy.sh --skip-backup --skip-tests

# Test the script without deploying
./scripts/safe-deploy.sh --dry-run

# Deploy without auto-rollback (manual control)
./scripts/safe-deploy.sh --no-rollback
```

---

## Safety Mechanisms

### 1. Pre-Flight Checks

**What it does:**
- Verifies you're in the project root
- Checks `flyctl` is installed and authenticated
- Confirms target app exists
- Shows git status and warns about uncommitted changes

**Why it matters:**
Prevents deployment from wrong directory or with wrong credentials.

**Example output:**
```
🔍 PRE-FLIGHT CHECKS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Pre-flight checks passed
ℹ️  Current branch: main
ℹ️  Last commit: feat: add pricing tool (a3f89d2)
⚠️  You have uncommitted changes!
M apps/backend-rag/backend/services/rag/tools.py
Continue anyway? (y/N)
```

---

### 2. Test Execution

**What it does:**
- Runs unit tests in `apps/backend-rag/tests/`
- Uses minimal output mode for speed
- Captures full output to `/tmp/test-output.txt`
- **Blocks deploy** if any tests fail

**Why it matters:**
Prevents deploying broken code to production.

**Example output:**
```
🧪 RUNNING TESTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Tests passed: 780 passed in 45.23s
```

**If tests fail:**
```
🧪 RUNNING TESTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ Tests failed!
ℹ️  Fix the failing tests before deploying
ℹ️  View full output: cat /tmp/test-output.txt

⛔ Deploy ABORTED
```

---

### 3. Database Backup

**What it does:**
- Creates timestamped PostgreSQL dump
- Compresses with gzip (saves ~70% space)
- Stores in `backups/postgres/`
- Keeps last 10 backups (configurable)
- Cleans up old backups automatically

**Why it matters:**
Safety net for schema changes or data migrations.

**Example output:**
```
💾 BACKING UP DATABASE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ℹ️  Creating database backup...
ℹ️  Using Fly Postgres proxy for backup...
✅ Backup created: backups/postgres/nuzantara-db-20260113-154523.sql.gz (45MB)
✅ Database backup created
```

**Backup structure:**
```
backups/postgres/
├── nuzantara-db-20260113-154523.sql.gz  (latest)
├── nuzantara-db-20260113-120145.sql.gz
├── nuzantara-db-20260112-183022.sql.gz
└── ... (up to 10 backups)
```

**Restore command:**
```bash
gunzip -c backups/postgres/nuzantara-db-20260113-154523.sql.gz | \
  psql $DATABASE_URL
```

---

### 4. Deploy to Fly.io

**What it does:**
- Changes to backend directory
- Runs `flyctl deploy -a nuzantara-rag`
- Captures full output to timestamped log file
- Extracts deployed version number
- Preserves logs for debugging

**Why it matters:**
Maintains audit trail of all deployments.

**Example output:**
```
🚀 DEPLOYING TO PRODUCTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ℹ️  Deploying to Fly.io...
ℹ️  Log file: deploy-logs/deploy-20260113-154545.log
==> Building image
==> Pushing image to fly
==> Deploying image
==> Monitoring health checks
✅ Deploy completed: v1480
```

**Log files:**
```
deploy-logs/
├── deploy-20260113-154545.log  (latest)
├── deploy-20260113-120200.log
└── deploy-20260112-183100.log
```

---

### 5. Health Check

**What it does:**
- Waits 30s for application startup
- Tests `https://nuzantara-rag.fly.dev/health`
- Retries up to 6 times (5s delay between)
- Parses JSON response for detailed status
- Verifies Qdrant and database connectivity

**Why it matters:**
Confirms the deployed version is actually working.

**Example output:**
```
🏥 HEALTH CHECK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ℹ️  Waiting 30s for application startup...
ℹ️  Checking health endpoint: https://nuzantara-rag.fly.dev/health
ℹ️  Attempt 1/6...
✅ Backend responding: HTTP 200
✅ Qdrant: 58,154 documents
✅ Database: connected
```

**If health check fails:**
```
🏥 HEALTH CHECK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ℹ️  Attempt 1/6...
⚠️  HTTP 503 - not healthy yet
ℹ️  Retrying in 5s...
ℹ️  Attempt 2/6...
⚠️  Connection failed or timeout
ℹ️  Retrying in 5s...
...
❌ Health check failed after 6 attempts!
```

---

### 6. Automatic Rollback

**What it does:**
- Triggers if health check fails
- Runs `flyctl releases rollback`
- Reverts to previous working version
- Re-verifies health after rollback
- Reports rollback status

**Why it matters:**
Minimizes downtime by automatically recovering from bad deploys.

**Example output:**
```
🔄 ROLLING BACK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  Health check failed - initiating automatic rollback...
==> Rolling back to v1479
✅ Rollback completed
ℹ️  Production should be stable on previous version
ℹ️  Verifying rollback...
✅ Rollback successful - production is healthy
```

**Downtime:** Typically < 60 seconds from failure detection to rollback completion.

---

## Common Scenarios

### Scenario 1: Standard Deploy (Everything Works)

```bash
$ ./scripts/safe-deploy.sh

╔════════════════════════════════════════════════════════╗
║          NUZANTARA SAFE DEPLOY SCRIPT v1.0.0          ║
╚════════════════════════════════════════════════════════╝

🔍 PRE-FLIGHT CHECKS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Pre-flight checks passed
ℹ️  Current branch: main
ℹ️  Last commit: feat: improve pricing tool (a3f89d2)

🧪 RUNNING TESTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Tests passed: 780 passed in 42.15s

💾 BACKING UP DATABASE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Backup created: backups/postgres/nuzantara-db-20260113-154523.sql.gz (45MB)
✅ Database backup created

🚀 DEPLOYING TO PRODUCTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ℹ️  Deploying to Fly.io...
✅ Deploy completed: v1480

🏥 HEALTH CHECK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ℹ️  Waiting 30s for application startup...
✅ Backend responding: HTTP 200
✅ Qdrant: 58,154 documents
✅ Database: connected

🎉 DEPLOY SUCCESSFUL!

✅ Version: v1480
✅ URL: https://nuzantara-rag.fly.dev
✅ Health: https://nuzantara-rag.fly.dev/health
ℹ️  Total time: 285s

ℹ️  Next steps:
  • Check logs: flyctl logs -a nuzantara-rag
  • Monitor: https://fly.io/apps/nuzantara-rag
  • Metrics: https://fly.io/apps/nuzantara-rag/metrics
```

**Duration:** ~5 minutes  
**Outcome:** ✅ Success

---

### Scenario 2: Test Failure (Deploy Blocked)

```bash
$ ./scripts/safe-deploy.sh

🧪 RUNNING TESTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FAILED tests/test_pricing.py::test_get_pricing - AssertionError
❌ Tests failed!
ℹ️  Fix the failing tests before deploying
ℹ️  View full output: cat /tmp/test-output.txt

⛔ Deploy ABORTED
```

**Duration:** ~1 minute  
**Outcome:** ⛔ Blocked (production safe)  
**Action:** Fix tests, then retry

---

### Scenario 3: Deploy OK but App Crashes (Auto-Rollback)

```bash
$ ./scripts/safe-deploy.sh

[... tests, backup, deploy all succeed ...]

🏥 HEALTH CHECK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ℹ️  Attempt 1/6...
⚠️  HTTP 503 - not healthy yet
ℹ️  Retrying in 5s...
ℹ️  Attempt 6/6...
⚠️  Connection failed or timeout
❌ Health check failed after 6 attempts!

🔄 ROLLING BACK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  Health check failed - initiating automatic rollback...
✅ Rollback completed
✅ Rollback successful - production is healthy
```

**Duration:** ~6 minutes  
**Outcome:** ✅ Rolled back (production stable on v1479)  
**Action:** Check logs, fix issue, retry

---

### Scenario 4: Quick Deploy (Skip Tests)

```bash
$ ./scripts/safe-deploy.sh --skip-tests

⚠️  Skipping tests (--skip-tests flag)

💾 BACKING UP DATABASE
...
✅ Deploy successful!
```

**Duration:** ~4 minutes  
**Use case:** Tests already passed locally, need quick hotfix

---

### Scenario 5: Dry Run (Testing Script)

```bash
$ ./scripts/safe-deploy.sh --dry-run

⚠️  DRY RUN MODE - No actual changes will be made

🔍 PRE-FLIGHT CHECKS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Pre-flight checks passed

🧪 RUNNING TESTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ℹ️  [DRY RUN] Would run: cd apps/backend-rag && pytest tests/ -q --tb=short
✅ [DRY RUN] Tests passed (simulated)

💾 BACKING UP DATABASE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ℹ️  [DRY RUN] Would run: ./scripts/backup-db.sh
✅ [DRY RUN] Backup created (simulated)

🚀 DEPLOYING TO PRODUCTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ℹ️  [DRY RUN] Would run: cd apps/backend-rag && flyctl deploy -a nuzantara-rag
✅ [DRY RUN] Deploy completed (simulated)

🏥 HEALTH CHECK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ℹ️  [DRY RUN] Would check: https://nuzantara-rag.fly.dev/health
✅ [DRY RUN] Health check passed (simulated)

🎉 DEPLOY SUCCESSFUL!
```

**Duration:** ~5 seconds  
**Use case:** Testing script modifications without deploying

---

## Troubleshooting

### Problem: "flyctl is not installed"

**Symptom:**
```
❌ flyctl is not installed!
ℹ️  Install it: https://fly.io/docs/hands-on/install-flyctl/
```

**Solution:**
```bash
# macOS
brew install flyctl

# Linux
curl -L https://fly.io/install.sh | sh

# Windows
powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
```

---

### Problem: "Not authenticated with Fly.io"

**Symptom:**
```
❌ Not authenticated with Fly.io!
ℹ️  Run: flyctl auth login
```

**Solution:**
```bash
flyctl auth login
# Opens browser for authentication
```

---

### Problem: "Tests failed"

**Symptom:**
```
❌ Tests failed!
ℹ️  Fix the failing tests before deploying
```

**Solution:**
```bash
# 1. View full test output
cat /tmp/test-output.txt

# 2. Run tests locally to debug
cd apps/backend-rag
PYTHONPATH=backend pytest tests/unit/test_failing.py -v

# 3. Fix the failing tests

# 4. Retry deploy
./scripts/safe-deploy.sh
```

**Workaround (use with caution):**
```bash
# Skip tests if you're confident they're false positives
./scripts/safe-deploy.sh --skip-tests
```

---

### Problem: "Health check failed after 6 attempts"

**Symptom:**
```
❌ Health check failed after 6 attempts!
⚠️  Health check failed - initiating automatic rollback...
```

**Diagnosis:**
```bash
# 1. Check application logs
flyctl logs -a nuzantara-rag

# 2. Check for common issues:
#    - Database connection errors
#    - Qdrant connection errors
#    - Import errors
#    - Configuration issues

# 3. Check health endpoint manually
curl https://nuzantara-rag.fly.dev/health
```

**Solution:**
- Fix the issue identified in logs
- Test locally if possible
- Retry deployment

---

### Problem: "Backup failed"

**Symptom:**
```
⚠️  Backup script failed, but continuing deploy
```

**Impact:** Deploy continues, but without database backup.

**Solution:**
```bash
# 1. Create manual backup
flyctl ssh console -a nuzantara-rag -C 'pg_dump $DATABASE_URL' > backup-manual.sql

# 2. Or skip backup for this deploy
./scripts/safe-deploy.sh --skip-backup

# 3. Fix backup script for future deploys
```

---

### Problem: "Rollback failed"

**Symptom:**
```
❌ Rollback failed!
⚠️  Manual intervention required!
```

**Solution:**
```bash
# 1. Manual rollback via Fly.io
flyctl releases list -a nuzantara-rag
flyctl releases rollback -a nuzantara-rag -y

# 2. Or rollback to specific version
flyctl releases rollback v1479 -a nuzantara-rag -y

# 3. Verify health
curl https://nuzantara-rag.fly.dev/health
```

---

### Problem: Script hangs during deploy

**Symptom:** Script appears frozen during deploy phase.

**Diagnosis:**
```bash
# Open another terminal and check Fly.io status
flyctl status -a nuzantara-rag
flyctl logs -a nuzantara-rag
```

**Solution:**
- Wait for timeout (usually 5-10 minutes)
- Or Ctrl+C and investigate logs
- May need to manually complete or rollback deploy

---

## Best Practices

### 1. Run Tests Locally First

```bash
# Before deploying, run tests locally
cd apps/backend-rag
PYTHONPATH=backend pytest tests/ -q

# If all pass, deploy with confidence
cd ../..
./scripts/safe-deploy.sh
```

**Benefit:** Catches issues faster, saves CI time.

---

### 2. Use Meaningful Commit Messages

```bash
# Good commit messages help debug failed deploys
git commit -m "feat: add pricing tool validation"
git commit -m "fix: resolve Qdrant timeout in vector search"
git commit -m "refactor: simplify reasoning loop state management"
```

**Benefit:** Easier to identify what changed when deploy fails.

---

### 3. Deploy During Low-Traffic Periods

```bash
# Check current traffic
flyctl metrics -a nuzantara-rag

# Deploy during known low-traffic windows
# (e.g., early morning, late evening)
./scripts/safe-deploy.sh
```

**Benefit:** Minimizes user impact if something goes wrong.

---

### 4. Monitor After Deploy

```bash
# Keep logs open for 5-10 minutes after deploy
flyctl logs -a nuzantara-rag

# Watch for:
# - Error spikes
# - Unusual patterns
# - User-reported issues
```

**Benefit:** Early detection of issues not caught by health check.

---

### 5. Keep Backups for 30 Days

```bash
# Modify backup retention in backup-db.sh
# Default: 10 backups
# Recommended: ~60 backups (2/day × 30 days)

# Edit scripts/backup-db.sh
KEEP_BACKUPS=60
```

**Benefit:** Recovery from issues discovered days later.

---

### 6. Test Rollback Process

```bash
# Periodically test rollback works
./scripts/safe-deploy.sh  # Deploy v1480
flyctl releases rollback -a nuzantara-rag -y  # Back to v1479
curl https://nuzantara-rag.fly.dev/health  # Verify
```

**Benefit:** Confidence that recovery mechanism works.

---

### 7. Document Risky Deploys

```bash
# For deploys with schema changes or major refactors
# Create a deploy note
echo "Deploy v1480 - Major DB migration (added collective_memories table)" \
  > deploy-logs/DEPLOY-v1480-NOTES.md

# Include:
# - What changed
# - Rollback plan
# - Known risks
# - Verification steps
```

**Benefit:** Context for debugging if issues arise later.

---

## Technical Details

### Script Architecture

```
safe-deploy.sh (main orchestrator)
├── Configuration (lines 1-50)
├── Utility Functions (lines 51-100)
├── Pre-flight Checks (lines 101-150)
├── Run Tests (lines 151-200)
├── Backup Database (lines 201-230)
│   └── calls backup-db.sh
├── Deploy to Fly.io (lines 231-280)
├── Health Check (lines 281-350)
├── Rollback (lines 351-400)
└── Main Execution (lines 401-450)
```

### Dependencies

| Tool | Required | Purpose |
|------|----------|---------|
| `bash` | Yes | Script execution |
| `flyctl` | Yes | Fly.io deployment |
| `curl` | Yes | Health checks |
| `jq` | No (recommended) | JSON parsing |
| `git` | Yes | Version control |
| `pytest` | Yes | Test execution |
| `pg_dump` | No | Database backup |

### Environment Variables

The script reads these from Fly.io secrets (no local env vars needed):

- `DATABASE_URL` - PostgreSQL connection string
- `QDRANT_URL` - Qdrant vector DB URL
- `GOOGLE_API_KEY` - Gemini API key
- All other app secrets

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error (tests failed, deploy failed, etc.) |
| 130 | User cancelled (Ctrl+C) |

### File Locations

```
nuzantara/
├── scripts/
│   ├── safe-deploy.sh          ← Main script
│   └── backup-db.sh            ← Backup helper
├── deploy-logs/
│   ├── deploy-20260113-154545.log
│   └── ...                     ← Deploy logs
├── backups/
│   └── postgres/
│       ├── nuzantara-db-20260113-154523.sql.gz
│       └── ...                 ← Database backups
└── /tmp/
    ├── test-output.txt         ← Test results
    └── health-response.json    ← Health check response
```

### Performance Metrics

Based on typical Nuzantara deploys:

| Metric | Typical Value |
|--------|---------------|
| Total deploy time | 4-5 minutes |
| Test execution | 30-60 seconds |
| Database backup | 10-20 seconds |
| Fly.io deploy | 2-3 minutes |
| Health check | 30-60 seconds |
| Rollback time | 30-60 seconds |

### Security Considerations

1. **No secrets in script** - All secrets come from Fly.io
2. **Read-only git operations** - Script never commits/pushes
3. **Explicit user confirmation** - For uncommitted changes
4. **Audit trail** - All actions logged
5. **Rollback capability** - Fast recovery from bad deploys

---

## Advanced Usage

### Customizing Test Command

Edit `safe-deploy.sh` line ~175:

```bash
# Default
if PYTHONPATH=backend pytest tests/unit/ -q --tb=short 2>&1

# Run all tests (slower but more comprehensive)
if PYTHONPATH=backend pytest tests/ -q --tb=short 2>&1

# Run only critical tests (faster)
if PYTHONPATH=backend pytest tests/unit/services/rag/ -q --tb=short 2>&1
```

### Customizing Health Check

Edit `safe-deploy.sh` lines 14-17:

```bash
# Default
HEALTH_CHECK_TIMEOUT=30
HEALTH_CHECK_RETRIES=6
RETRY_DELAY=5

# For slower startups
HEALTH_CHECK_TIMEOUT=60
HEALTH_CHECK_RETRIES=10
RETRY_DELAY=10
```

### Multiple Environments

Create environment-specific scripts:

```bash
# scripts/safe-deploy-staging.sh
APP_NAME="nuzantara-rag-staging"
HEALTH_URL="https://nuzantara-rag-staging.fly.dev/health"
# ... rest of safe-deploy.sh

# scripts/safe-deploy-production.sh
APP_NAME="nuzantara-rag"
HEALTH_URL="https://nuzantara-rag.fly.dev/health"
# ... rest of safe-deploy.sh
```

### Integration with CI/CD

```yaml
# .github/workflows/manual-deploy.yml
name: Manual Deploy (Safe)
on:
  workflow_dispatch:
    inputs:
      skip-tests:
        description: 'Skip tests'
        required: false
        default: 'false'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Fly.io
        uses: superfly/flyctl-actions/setup-flyctl@master
      - name: Safe Deploy
        run: |
          if [ "${{ inputs.skip-tests }}" == "true" ]; then
            ./scripts/safe-deploy.sh --skip-tests
          else
            ./scripts/safe-deploy.sh
          fi
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
```

---

## FAQ

**Q: Can I use this for frontend (mouth) deploys?**

A: Currently designed for backend only. For frontend, Vercel has built-in preview/rollback. You could adapt the script by changing `APP_NAME` and removing backend-specific checks.

**Q: What if I want to deploy without any safety checks?**

A: Use `flyctl deploy` directly. But we strongly recommend using safe-deploy.sh.

**Q: Can I skip the 30-second health check wait?**

A: Yes, edit `HEALTH_CHECK_TIMEOUT` in the script. But Fly.io needs time to start the new instance.

**Q: Does this work with multiple Fly.io apps?**

A: Yes, change `APP_NAME` variable or create separate scripts for each app.

**Q: What happens to old deploy logs?**

A: They accumulate indefinitely. Consider adding periodic cleanup (e.g., keep last 30 days).

**Q: Can I run this from CI/CD?**

A: Yes! Set `FLY_API_TOKEN` environment variable and the script will work non-interactively.

---

## Support

For issues or questions:

1. **Check logs:** `cat deploy-logs/deploy-latest.log`
2. **Check Fly.io status:** `flyctl status -a nuzantara-rag`
3. **Review this guide:** Especially [Troubleshooting](#troubleshooting)
4. **Contact team:** Nuzantara Slack #deployments channel

---

**Last Updated:** 2026-01-13  
**Script Version:** 1.0.0  
**Maintained by:** Nuzantara Team
