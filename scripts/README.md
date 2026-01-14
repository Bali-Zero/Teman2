# Deployment Scripts

This directory contains deployment automation scripts for the Nuzantara platform.

---

## 🚀 Quick Start

### Standard Deploy (Recommended)

```bash
./scripts/safe-deploy.sh
```

**What it does:**
- ✅ Runs tests
- ✅ Backs up database
- ✅ Deploys to Fly.io
- ✅ Verifies health
- ✅ Auto-rollback if failure

**Time:** ~4-5 minutes

---

## 📜 Available Scripts

### Deployment

#### `safe-deploy.sh` ⭐ **PRIMARY**
Complete deployment workflow with safety checks.

```bash
# Standard deploy
./scripts/safe-deploy.sh

# Skip tests (if already run)
./scripts/safe-deploy.sh --skip-tests

# Test without deploying
./scripts/safe-deploy.sh --dry-run

# Emergency deploy
./scripts/safe-deploy.sh --skip-tests --skip-backup

# Help
./scripts/safe-deploy.sh --help
```

**Documentation:** `docs/SAFE_DEPLOY_GUIDE.md`

#### `fly-backend.sh`
Legacy helper for direct Fly.io commands.

```bash
./scripts/fly-backend.sh status
./scripts/fly-backend.sh logs
./scripts/fly-backend.sh deploy  # Not recommended, use safe-deploy.sh
```

---

### Database

#### `backup-db.sh`
Database backup via Fly.io SSH.

```bash
# Create backup (manual)
./scripts/backup-db.sh

# Custom output directory
./scripts/backup-db.sh --output-dir /path/to/backups

# Keep 20 backups instead of 10
./scripts/backup-db.sh --keep 20
```

**Output:** `backups/postgres/nuzantara-db-TIMESTAMP.sql.gz`

**Restore:**
```bash
gunzip -c backups/postgres/nuzantara-db-20260113-154523.sql.gz | \
  psql $DATABASE_URL
```

---

### Monitoring & Health

#### `verify_online_status.sh`
Check if services are online.

```bash
./scripts/verification/verify_online_status.sh
```

#### `deploy_monitoring.sh`
Deploy monitoring stack (Prometheus, Grafana, Jaeger).

```bash
./scripts/deploy_monitoring.sh
```

---

## 🔒 Best Practices

### Do's
- ✅ **Always use `safe-deploy.sh`** for production deploys
- ✅ Commit your changes before deploying
- ✅ Monitor logs after deploy for 5-10 minutes
- ✅ Test in dry-run mode if script modified
- ✅ Keep backups for 30+ days

### Don'ts
- ❌ **Don't run `flyctl deploy` directly** (no safety checks)
- ❌ Don't deploy with uncommitted changes (unless intentional)
- ❌ Don't skip tests without good reason
- ❌ Don't panic if deploy fails (auto-rollback will recover)

---

## 📊 Deploy Flow

```
Standard Deploy (./scripts/safe-deploy.sh)
│
├─1─ Pre-flight Checks (~5s)
│    ├─ Git status
│    ├─ Fly.io auth
│    └─ App exists
│
├─2─ Run Tests (~30-60s)
│    └─ pytest tests/ -q
│
├─3─ Backup Database (~10-20s)
│    └─ pg_dump via Fly.io SSH
│
├─4─ Deploy to Fly.io (~2-3 min)
│    └─ flyctl deploy -a nuzantara-rag
│
├─5─ Health Check (~30-60s)
│    ├─ Wait 30s for startup
│    ├─ Test /health endpoint
│    └─ Retry 6 times if needed
│
└─6─ Success or Rollback
     ├─ ✅ Success → Done
     └─ ❌ Failure → Auto-rollback (<60s)

Total: ~4-5 minutes
```

---

## 🚨 Troubleshooting

### "Tests failed"
```bash
# View test output
cat /tmp/test-output.txt

# Run tests manually
cd apps/backend-rag
PYTHONPATH=backend pytest tests/ -v
```

### "Health check failed"
```bash
# Check logs
flyctl logs -a nuzantara-rag

# Check health manually
curl https://nuzantara-rag.fly.dev/health

# Manual rollback if needed
flyctl releases rollback -a nuzantara-rag -y
```

### "Backup failed"
```bash
# Create manual backup
flyctl ssh console -a nuzantara-rag -C 'pg_dump $DATABASE_URL' > backup.sql

# Or skip backup for this deploy
./scripts/safe-deploy.sh --skip-backup
```

---

## 📖 Documentation

| Script | Documentation |
|--------|---------------|
| `safe-deploy.sh` | `docs/SAFE_DEPLOY_GUIDE.md` (900+ lines) |
| `backup-db.sh` | Inline help (`--help`) |
| All scripts | `docs/SAFE_DEPLOY_IMPLEMENTATION.md` |

---

## 🔧 Script Options

### safe-deploy.sh

| Option | Description |
|--------|-------------|
| `--skip-tests` | Skip test execution (use with caution) |
| `--skip-backup` | Skip database backup |
| `--no-rollback` | Disable auto-rollback |
| `--dry-run` | Simulate without executing |
| `-h, --help` | Show help message |

### backup-db.sh

| Option | Description |
|--------|-------------|
| `--output-dir DIR` | Custom backup directory |
| `--app-name NAME` | Fly.io app name |
| `--keep N` | Keep last N backups |
| `-h, --help` | Show help message |

---

## 📁 File Locations

```
nuzantara/
├── scripts/
│   ├── safe-deploy.sh          ← Main deploy script
│   ├── backup-db.sh            ← DB backup helper
│   ├── fly-backend.sh          ← Legacy Fly.io helper
│   └── ...
├── deploy-logs/                ← Deploy logs (auto-created)
│   └── deploy-TIMESTAMP.log
├── backups/
│   └── postgres/               ← Database backups (auto-created)
│       └── nuzantara-db-TIMESTAMP.sql.gz
└── docs/
    ├── SAFE_DEPLOY_GUIDE.md    ← Complete documentation
    └── SAFE_DEPLOY_IMPLEMENTATION.md
```

---

## 🎯 Quick Commands

```bash
# Deploy
./scripts/safe-deploy.sh

# Deploy (skip tests)
./scripts/safe-deploy.sh --skip-tests

# Test script
./scripts/safe-deploy.sh --dry-run

# Backup DB
./scripts/backup-db.sh

# Check status
./scripts/fly-backend.sh status

# View logs
flyctl logs -a nuzantara-rag

# Rollback
flyctl releases rollback -a nuzantara-rag -y
```

---

## 🆘 Support

**Issues?**
1. Check `docs/SAFE_DEPLOY_GUIDE.md` → Troubleshooting section
2. Run `./scripts/safe-deploy.sh --dry-run` to test
3. Check logs: `cat deploy-logs/deploy-latest.log`
4. Review health: `curl https://nuzantara-rag.fly.dev/health`

**Emergency Rollback:**
```bash
flyctl releases list -a nuzantara-rag
flyctl releases rollback -a nuzantara-rag -y
```

---

**Last Updated:** 2026-01-13  
**Maintained by:** Nuzantara Team
