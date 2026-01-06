# 🚀 Nuzantara Migration Package - Complete Guide

**From:** Fly.io
**To:** Railway + Vercel
**Status:** Ready to Execute
**Created:** 2026-01-06

---

## 📦 What's Included

This migration package contains everything you need to migrate Nuzantara from Fly.io to Railway/Vercel with zero data loss and minimal downtime.

```
nuzantara/
├── MIGRATION_CHECKLIST.md           # Step-by-step checklist
├── RAILWAY_SETUP_GUIDE.md           # Detailed Railway/Vercel setup
├── MIGRATION_README.md              # This file
│
├── scripts/migration/
│   ├── 01-export-flyio-data.sh      # Export Postgres + secrets
│   ├── 02-import-railway-postgres.sh # Import to Railway
│   ├── 03-verify-database.sh        # Verify data integrity
│   ├── 04-export-qdrant.sh          # Export Qdrant snapshots
│   ├── 05-import-qdrant.sh          # Import to new Qdrant
│   ├── 06-setup-railway-backend.sh  # Deploy backend
│   ├── 07-integration-tests.sh      # Test everything
│   └── ROLLBACK.sh                  # Emergency rollback
│
└── backups/                          # Created during migration
    ├── postgres/                     # Database backups
    └── qdrant/                       # Vector DB snapshots
```

---

## 🎯 Quick Start

### Prerequisites

```bash
# Install required tools
npm install -g @railway/cli vercel
brew install postgresql@15

# Login to services
railway login
vercel login
```

### Migration in 3 Steps

**Step 1: Backup Everything**
```bash
cd /Users/antonellosiano/Desktop/nuzantara
./scripts/migration/01-export-flyio-data.sh
```

**Step 2: Setup New Infrastructure**
```bash
# Follow the Railway Setup Guide
open RAILWAY_SETUP_GUIDE.md
```

**Step 3: Migrate Data**
```bash
./scripts/migration/02-import-railway-postgres.sh
./scripts/migration/04-export-qdrant.sh
./scripts/migration/05-import-qdrant.sh
```

---

## 📋 Detailed Migration Process

### Phase 1: Preparation (30 minutes)

**What:** Create backups and setup accounts

**Steps:**
1. ✅ Create Railway account
2. ✅ Create Vercel account
3. ✅ Run backup script
4. ✅ Verify backups created

**Script:**
```bash
./scripts/migration/01-export-flyio-data.sh
```

**Output:**
- `backups/postgres/postgres_backup_TIMESTAMP.dump`
- `backups/secrets_backend_TIMESTAMP.txt`
- `backups/secrets_frontend_TIMESTAMP.txt`

---

### Phase 2: Infrastructure Setup (1-2 hours)

**What:** Setup Railway and Vercel projects

**Guide:** `RAILWAY_SETUP_GUIDE.md`

**Tasks:**
1. Create Railway projects (backend, scraper)
2. Add PostgreSQL plugin
3. Deploy frontend to Vercel
4. Configure environment variables
5. Get service URLs

**Expected URLs:**
- Backend: `https://nuzantara-backend.up.railway.app`
- Frontend: `https://nuzantara-mouth.vercel.app`

---

### Phase 3: Data Migration (2-4 hours)

**What:** Migrate PostgreSQL and Qdrant

**PostgreSQL:**
```bash
# Import database
./scripts/migration/02-import-railway-postgres.sh

# Verify
./scripts/migration/03-verify-database.sh
```

**Qdrant:**
```bash
# Export snapshots
./scripts/migration/04-export-qdrant.sh

# Import to new Qdrant
./scripts/migration/05-import-qdrant.sh
```

**Verification:**
- Row counts match between Fly.io and Railway
- Sample queries return same results
- Vector search works

---

### Phase 4: Testing (1-2 hours)

**What:** Comprehensive integration tests

**Script:**
```bash
./scripts/migration/07-integration-tests.sh
```

**Tests:**
- ✅ Health endpoints
- ✅ API functionality
- ✅ Database queries
- ✅ Vector search
- ✅ Authentication
- ✅ Response times

**Success Criteria:**
- All tests passing
- Response times < baseline
- No errors in logs

---

### Phase 5: Cutover (30 minutes)

**What:** Switch DNS to new infrastructure

**Checklist:**
```
MIGRATION_CHECKLIST.md → Day 5: Final Cutover
```

**Steps:**
1. Lower DNS TTL to 300s (5 min)
2. Wait 1 hour for propagation
3. Update DNS records
4. Monitor for issues
5. Verify new URLs working

**Downtime:** ~30 seconds (DNS switch only)

---

## 🔄 Rollback Plan

### If Anything Goes Wrong

```bash
# Emergency rollback (< 5 minutes)
./scripts/migration/ROLLBACK.sh
```

**What it does:**
1. Restarts Fly.io machines
2. Provides DNS rollback instructions
3. Pauses Railway services
4. Creates rollback log

**Manual Steps:**
1. Revert DNS CNAME records
2. Wait for propagation (~5-10 min)
3. Verify Fly.io working

---

## 📊 Cost Comparison

### Current (Fly.io)

```
Backend (2 machines):     ~$25-30/mese
Frontend (2 machines):    ~$15-20/mese
PostgreSQL:               ~$10/mese
Qdrant (self-hosted):     $0
───────────────────────────────────
TOTALE:                   ~$50-60/mese
```

### New (Railway + Vercel)

```
Backend (Railway):        ~$30-40/mese
Frontend (Vercel):        $0 (free tier)
PostgreSQL (Railway):     ~$10/mese
Qdrant Cloud:             ~$95/mese
Scraper (Railway):        ~$15/mese
───────────────────────────────────
TOTALE:                   ~$150-160/mese
```

**OR with Qdrant self-hosted:**
```
Qdrant (Hetzner):         €4.49/mese
───────────────────────────────────
TOTALE:                   ~$60-70/mese
```

---

## ⚡ Performance Expectations

### Response Times

| Endpoint | Fly.io | Railway | Target |
|----------|--------|---------|--------|
| Health check | 200-300ms | 150-250ms | <500ms |
| Chat API | 800-1200ms | 600-1000ms | <2s |
| Search | 400-600ms | 300-500ms | <1s |

### Uptime

| Service | Fly.io | Railway |
|---------|--------|---------|
| Backend | 98-99% | 99.9% |
| Frontend | 98-99% | 99.99% (Vercel) |

---

## 🆘 Support & Resources

### Documentation

- **Migration Checklist:** `MIGRATION_CHECKLIST.md`
- **Railway Guide:** `RAILWAY_SETUP_GUIDE.md`
- **Scripts:** `scripts/migration/`

### External Resources

- Railway Docs: https://docs.railway.app
- Vercel Docs: https://vercel.com/docs
- Railway Discord: https://discord.gg/railway
- Vercel Support: https://vercel.com/support

### Get Help

**Railway:**
- Discord (fastest): https://discord.gg/railway
- Email: team@railway.app
- Response time: <1 hour

**Vercel:**
- Support: https://vercel.com/support
- Response time: <2 hours

---

## ✅ Migration Checklist Summary

Use `MIGRATION_CHECKLIST.md` for detailed steps.

### Pre-Migration
- [ ] Accounts created (Railway, Vercel)
- [ ] Tools installed (CLI, psql)
- [ ] Backups completed
- [ ] Team notified

### Day 1: Setup
- [ ] Railway projects created
- [ ] Vercel project imported
- [ ] PostgreSQL provisioned
- [ ] Environment variables set

### Day 2: Database
- [ ] PostgreSQL exported
- [ ] PostgreSQL imported to Railway
- [ ] Data verified

### Day 3: Qdrant
- [ ] Qdrant snapshots created
- [ ] Qdrant imported to new instance
- [ ] Vector search tested

### Day 4: Deployment
- [ ] Backend deployed to Railway
- [ ] Frontend deployed to Vercel
- [ ] Integration tests passing

### Day 5: Cutover
- [ ] DNS TTL lowered
- [ ] Final testing complete
- [ ] DNS switched
- [ ] Monitoring active

### Post-Migration
- [ ] 24h monitoring
- [ ] Performance validated
- [ ] Costs reviewed
- [ ] Fly.io decommissioned (after 30 days)

---

## 📝 Notes

### Important Decisions

**Qdrant Hosting:**
- Option A: Qdrant Cloud ($95/mese) - Zero maintenance
- Option B: Self-hosted ($5/mese) - Manual management

**Frontend:**
- Vercel is non-negotiable for Next.js (best DX + performance)

**Backend:**
- Railway chosen for reliability + DX
- Alternative: Google Cloud Run (cheaper but complex)

### Lessons Learned

*Add notes here during migration*

---

## 🎓 What You'll Learn

This migration will teach you:
- ✅ Database migration with zero data loss
- ✅ Vector database snapshot/restore
- ✅ Zero-downtime deployments
- ✅ DNS cutover strategies
- ✅ Rollback procedures
- ✅ Infrastructure as Code basics

---

## 🚀 Ready to Migrate?

1. **Read:** `MIGRATION_CHECKLIST.md`
2. **Setup:** `RAILWAY_SETUP_GUIDE.md`
3. **Execute:** Run scripts in order
4. **Test:** `./scripts/migration/07-integration-tests.sh`
5. **Cutover:** Update DNS
6. **Monitor:** Watch for 24-48 hours

**Estimated Total Time:** 11-15 hours over 4-5 days

**Questions?** Check the guides or contact support.

---

**Last Updated:** 2026-01-06
**Version:** 1.0.0
**Status:** ✅ Ready for Production
