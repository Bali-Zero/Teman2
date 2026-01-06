# 🚀 Migration Quick Reference Card

**Print this out and keep it handy during migration**

---

## 📞 Emergency Contacts

| Service | Support | Response |
|---------|---------|----------|
| Railway | Discord: discord.gg/railway | <1 hour |
| Vercel | vercel.com/support | <2 hours |
| Fly.io | fly.io/docs/about/support | Varies |

---

## 🔧 Essential Commands

### Railway

```bash
# Login
railway login

# Create project
railway init

# Deploy
railway up

# Logs
railway logs --follow

# Variables
railway variables
railway variables set KEY=value

# Status
railway status

# Open dashboard
railway open
```

### Vercel

```bash
# Login
vercel login

# Deploy
vercel

# Deploy to production
vercel --prod

# Logs
vercel logs --follow

# Environment vars
vercel env add KEY production
vercel env ls

# Open dashboard
vercel --prod
```

### PostgreSQL

```bash
# Dump database
pg_dump -Fc $DATABASE_URL > backup.dump

# Restore database
pg_restore -d $DATABASE_URL backup.dump

# Connect to database
psql $DATABASE_URL

# Row count
psql $DATABASE_URL -c "SELECT COUNT(*) FROM table_name;"
```

---

## 📋 Migration Scripts (In Order)

```bash
cd /Users/antonellosiano/Desktop/nuzantara

# 1. Export Fly.io data
./scripts/migration/01-export-flyio-data.sh

# 2. Import to Railway Postgres
./scripts/migration/02-import-railway-postgres.sh

# 3. Verify database
./scripts/migration/03-verify-database.sh

# 4. Export Qdrant
python3 ./scripts/migration/04-export-qdrant.sh

# 5. Import Qdrant
python3 ./scripts/migration/05-import-qdrant.sh

# 6. Setup Railway backend
./scripts/migration/06-setup-railway-backend.sh

# 7. Integration tests
./scripts/migration/07-integration-tests.sh

# 🚨 EMERGENCY: Rollback
./scripts/migration/ROLLBACK.sh
```

---

## 🔗 Service URLs

### Development

| Service | URL |
|---------|-----|
| Railway Backend | `railway open` |
| Vercel Frontend | `vercel` |

### Production

| Service | URL Pattern |
|---------|-------------|
| Railway Backend | `https://PROJECT.up.railway.app` |
| Vercel Frontend | `https://PROJECT.vercel.app` |

---

## 🧪 Health Checks

```bash
# Railway backend
curl https://nuzantara-backend.up.railway.app/health

# Vercel frontend
curl https://nuzantara-mouth.vercel.app

# Local backend (dev)
curl http://localhost:8080/health
```

---

## 📊 Monitoring

### Railway

```bash
# Real-time logs
railway logs --follow

# Specific deployment
railway logs --deployment DEPLOYMENT_ID

# Metrics
railway open  # → Metrics tab
```

### Vercel

```bash
# Real-time logs
vercel logs --follow

# Production only
vercel logs --prod

# Analytics
# Dashboard → Analytics
```

---

## 🔐 Environment Variables

### Required for Backend

```env
DATABASE_URL        # Auto-injected by Railway
PORT=8080
ENVIRONMENT=production
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...
ANTHROPIC_API_KEY=sk-ant-...
QDRANT_URL=https://...
JWT_SECRET_KEY=...
```

### Required for Frontend

```env
NEXT_PUBLIC_API_URL=https://nuzantara-backend.up.railway.app
NEXT_PUBLIC_WS_URL=wss://nuzantara-backend.up.railway.app
NODE_ENV=production
```

---

## 🚨 Troubleshooting

### Build Fails

```bash
# Railway
railway logs --deployment LAST_ID
# Check: Python version, requirements.txt, start command

# Vercel
vercel logs --deployment LAST_ID
# Check: Node version, package.json, build command
```

### Service Not Responding

```bash
# Check health
curl https://SERVICE_URL/health

# Check logs
railway logs --follow
vercel logs --follow

# Check env vars
railway variables
vercel env ls
```

### Database Connection Fails

```bash
# Test connection
psql $RAILWAY_DATABASE_URL -c "SELECT version();"

# Check variable
railway variables get DATABASE_URL

# Restart service
railway up
```

---

## 📈 Cost Monitoring

### Railway

```bash
# View usage
railway open
# → Usage tab

# Set budget
# Settings → Usage Limits → Set monthly cap
```

### Vercel

```bash
# View usage
vercel --prod
# Dashboard → Team Settings → Billing
```

---

## 🔄 Rollback Procedure

### Quick Rollback (<5 min)

```bash
# Run emergency script
./scripts/migration/ROLLBACK.sh

# Revert DNS manually
# CNAME: api.nuzantara.com → nuzantara-rag.fly.dev
# CNAME: app.nuzantara.com → nuzantara-mouth.fly.dev

# Verify Fly.io
curl https://nuzantara-rag.fly.dev/health
```

---

## 📝 Verification Checklist

### After Each Phase

**Backend:**
- [ ] Health check passing
- [ ] Database connected
- [ ] Qdrant accessible
- [ ] API endpoints working
- [ ] Logs showing no errors

**Frontend:**
- [ ] Site loads
- [ ] API calls working
- [ ] No console errors
- [ ] Images loading

**Performance:**
- [ ] Response times acceptable
- [ ] No timeout errors
- [ ] Memory usage normal

---

## 🎯 Success Metrics

| Metric | Target |
|--------|--------|
| Uptime | >99.9% |
| Health check response | <500ms |
| API response | <2s |
| Build time | <5min |
| Zero data loss | ✅ |

---

## 📞 Quick Help

**Stuck?** Check:
1. `MIGRATION_README.md` - Overview
2. `MIGRATION_CHECKLIST.md` - Detailed steps
3. `RAILWAY_SETUP_GUIDE.md` - Platform guides
4. Railway Discord - Live support
5. Vercel Support - Ticket system

---

**Print Date:** 2026-01-06
**Keep this card during migration!**
