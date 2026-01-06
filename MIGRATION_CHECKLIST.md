# 🚀 Nuzantara Migration: Fly.io → Railway/Vercel

**Status:** Ready to Execute
**Estimated Time:** 11-15 hours over 4 days
**Downtime:** ~30 seconds (DNS switch only)
**Rollback Time:** <5 minutes

---

## 📋 PRE-MIGRATION CHECKLIST

### ✅ Phase 0: Preparation (Day 0)

- [ ] **Create accounts**
  - [ ] Railway account (https://railway.app)
  - [ ] Vercel account (https://vercel.com)
  - [ ] Qdrant Cloud account (https://cloud.qdrant.io) - Optional

- [ ] **Backup everything**
  - [ ] PostgreSQL full dump
  - [ ] Qdrant snapshots (all collections)
  - [ ] Environment variables export
  - [ ] File storage backup (if any volumes)
  - [ ] Git commit all changes

- [ ] **Audit current Fly.io setup**
  - [ ] Document all running services
  - [ ] List all secrets/env vars
  - [ ] Check DNS records
  - [ ] Document external integrations

- [ ] **Install tools**
  ```bash
  # Railway CLI
  npm i -g @railway/cli

  # Vercel CLI
  npm i -g vercel

  # PostgreSQL client
  brew install postgresql@15
  ```

---

## 🎯 MIGRATION TIMELINE

### 📅 DAY 1: Infrastructure Setup (2-3 hours)

#### Step 1.1: Railway Account Setup
- [ ] Sign up at https://railway.app
- [ ] Connect GitHub account
- [ ] Verify email
- [ ] Add payment method (gets $5 free credit)

#### Step 1.2: Create Railway Projects
```bash
cd /Users/antonellosiano/Desktop/nuzantara

# Login
railway login

# Create projects
railway init --name nuzantara-backend
railway init --name nuzantara-scraper
```

- [ ] Project: `nuzantara-backend` created
- [ ] Project: `nuzantara-scraper` created

#### Step 1.3: Vercel Account Setup
- [ ] Sign up at https://vercel.com
- [ ] Connect GitHub account
- [ ] Import repository: `nuzantara` (mouth app)

#### Step 1.4: Setup PostgreSQL on Railway
- [ ] Railway dashboard → Add PostgreSQL plugin
- [ ] Wait for provisioning (~2 minutes)
- [ ] Copy `DATABASE_URL` connection string
- [ ] Test connection:
  ```bash
  psql $RAILWAY_DATABASE_URL -c "SELECT version();"
  ```

---

### 📅 DAY 2: Database Migration (3-4 hours)

#### Step 2.1: Export Fly.io PostgreSQL

```bash
# Run the script
./scripts/migration/01-export-flyio-data.sh

# Verify backup files
ls -lh backups/
# Should see:
# - postgres_backup_YYYYMMDD.sql.gz
# - postgres_backup_YYYYMMDD.dump
```

- [ ] PostgreSQL backup created
- [ ] Backup file size verified (>0 bytes)
- [ ] Backup integrity checked

#### Step 2.2: Import to Railway PostgreSQL

```bash
# Run the script
./scripts/migration/02-import-railway-postgres.sh

# Expected output: "Database restored successfully"
```

- [ ] Database imported to Railway
- [ ] Table counts match Fly.io
- [ ] Sample queries tested

#### Step 2.3: Verify Data Integrity

```bash
# Run verification script
./scripts/migration/03-verify-database.sh
```

- [ ] Row counts match
- [ ] Key tables verified:
  - [ ] `users`
  - [ ] `clients`
  - [ ] `conversations`
  - [ ] `rag_documents`
  - [ ] `kg_nodes`
  - [ ] `kg_edges`

---

### 📅 DAY 3: Qdrant Migration (4-6 hours)

#### Step 3.1: Setup Qdrant Cloud (Recommended)

- [ ] Sign up at https://cloud.qdrant.io
- [ ] Create cluster (Starter plan)
- [ ] Copy API key and cluster URL

**OR** Self-hosted on Railway:

```bash
# Deploy Qdrant container
railway up --service qdrant
```

#### Step 3.2: Export Qdrant Data from Fly.io

```bash
# Run snapshot script
./scripts/migration/04-export-qdrant.sh

# Verify snapshots
ls -lh backups/qdrant/
```

- [ ] Snapshots created for all collections:
  - [ ] `legal_unified`
  - [ ] `tax_genius`
  - [ ] `immigration_docs`
  - [ ] `training_conversations`
  - [ ] `business_intelligence`
  - [ ] `company_knowledge`

#### Step 3.3: Import to New Qdrant

```bash
# Run import script
./scripts/migration/05-import-qdrant.sh
```

- [ ] All collections restored
- [ ] Point counts verified
- [ ] Sample searches tested

---

### 📅 DAY 4: Application Deployment (2-3 hours)

#### Step 4.1: Deploy Backend to Railway

```bash
cd apps/backend-rag

# Set environment variables (script prompts)
./scripts/migration/06-setup-railway-backend.sh

# Deploy
railway up
```

- [ ] Backend deployed successfully
- [ ] Health check passing: `https://nuzantara-backend.up.railway.app/health`
- [ ] API test successful

#### Step 4.2: Deploy Frontend to Vercel

```bash
cd apps/mouth

# Login and deploy
vercel login
vercel --prod
```

- [ ] Frontend deployed
- [ ] Preview URL working
- [ ] Production domain assigned

#### Step 4.3: Deploy Scraper to Railway

```bash
cd apps/bali-intel-scraper
railway up
```

- [ ] Scraper deployed
- [ ] Cron jobs configured
- [ ] Test scrape successful

---

### 📅 DAY 5: Final Cutover (1-2 hours)

#### Step 5.1: Final Testing on New Infrastructure

```bash
# Run full integration tests
./scripts/migration/07-integration-tests.sh
```

**Test Checklist:**
- [ ] User login works
- [ ] Chat query returns results
- [ ] Sources are cited correctly
- [ ] Knowledge graph search works
- [ ] Email integration works
- [ ] Telegram bot responds
- [ ] Dashboard loads

#### Step 5.2: DNS Cutover

**Current DNS (Fly.io):**
```
nuzantara-rag.fly.dev → Backend
nuzantara-mouth.fly.dev → Frontend
```

**New DNS (Railway/Vercel):**
```
# Backend
CNAME: api.nuzantara.com → nuzantara-backend.up.railway.app

# Frontend
CNAME: app.nuzantara.com → cname.vercel-dns.com
A: nuzantara.com → 76.76.21.21 (Vercel)
```

- [ ] DNS records updated
- [ ] TTL reduced to 300s (5 min) before switch
- [ ] Waited for propagation (~5-10 min)
- [ ] Verified new URLs working

#### Step 5.3: Monitor for Issues

**First 24 hours:**
- [ ] Check Railway logs every 2 hours
- [ ] Monitor error rates
- [ ] Check user reports
- [ ] Verify billing estimates

---

## 🔄 ROLLBACK PLAN

### If Migration Fails: Rollback in <5 Minutes

```bash
# Emergency rollback script
./scripts/migration/ROLLBACK.sh
```

**What it does:**
1. Reverts DNS to Fly.io
2. Stops Railway/Vercel services
3. Restores Fly.io if any machines were stopped
4. Sends alert notification

**Manual Rollback Steps:**

1. **DNS Rollback** (30 seconds)
   - Revert CNAME records to `*.fly.dev`
   - Wait for propagation

2. **Restart Fly.io machines** (if stopped)
   ```bash
   fly machine start --app nuzantara-rag --all
   ```

3. **Verify Fly.io working**
   ```bash
   curl https://nuzantara-rag.fly.dev/health
   ```

---

## ✅ POST-MIGRATION TASKS

### Week 1 After Migration

- [ ] **Day 1-3:** Monitor closely
  - Check logs hourly
  - Respond to user issues
  - Performance testing

- [ ] **Day 4-7:** Fine-tune
  - Optimize Railway resources
  - Adjust autoscaling
  - Review costs

### Week 2-4: Optimization

- [ ] Setup monitoring (Better Stack / Datadog)
- [ ] Configure alerts
- [ ] Review and optimize costs
- [ ] Document new architecture

### Month 2: Decommission Fly.io

- [ ] Verify Railway stable for 30 days
- [ ] Export final Fly.io backups
- [ ] Cancel Fly.io subscription
- [ ] Request credit for outage (if applicable)

---

## 📊 SUCCESS METRICS

**Migration is successful when:**

- ✅ All services healthy for 48 hours
- ✅ Response times < Fly.io baseline
- ✅ Zero data loss verified
- ✅ User complaints = 0
- ✅ Costs within budget
- ✅ Team comfortable with new platform

---

## 🆘 EMERGENCY CONTACTS

**Railway Support:**
- Discord: https://discord.gg/railway
- Email: team@railway.app
- Response: <1 hour (usually)

**Vercel Support:**
- Support: https://vercel.com/support
- Response: <2 hours

**Internal:**
- Migration lead: [Your Name]
- On-call: [Phone Number]

---

## 📝 NOTES & LESSONS LEARNED

*Add notes here during migration*

---

**Last Updated:** 2026-01-06
**Version:** 1.0
**Author:** Claude Code Assistant
