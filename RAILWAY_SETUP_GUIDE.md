## 🚂 Railway Setup Guide - Complete Walkthrough

**For:** Nuzantara Migration from Fly.io
**Time:** ~2 hours
**Difficulty:** Beginner-friendly

---

## 📚 Table of Contents

1. [Account Setup](#account-setup)
2. [Backend Deployment](#backend-deployment)
3. [Frontend Deployment (Vercel)](#frontend-deployment)
4. [Database Migration](#database-migration)
5. [Environment Variables](#environment-variables)
6. [Custom Domains](#custom-domains)
7. [Monitoring & Logs](#monitoring--logs)

---

## 1. Account Setup

### Create Railway Account

1. Go to https://railway.app
2. Click "Start a New Project"
3. Sign up with GitHub
4. Verify email
5. Add payment method (gets $5 free credit)

### Install Railway CLI

```bash
npm install -g @railway/cli

# Verify installation
railway --version

# Login
railway login
```

---

## 2. Backend Deployment

### Step 2.1: Create Project

```bash
cd /Users/antonellosiano/Desktop/nuzantara/apps/backend-rag

# Initialize Railway project
railway init

# Name: nuzantara-backend
# When prompted, link to GitHub: Yes
```

### Step 2.2: Add PostgreSQL Database

```bash
# Add PostgreSQL plugin
railway add --plugin postgresql

# Wait ~2 minutes for provisioning
```

### Step 2.3: Configure Environment

Railway auto-detects:
- ✅ Python runtime
- ✅ `requirements.txt`
- ✅ Start command from `Procfile` or auto-detect

Create `railway.toml` (optional, for custom config):

```toml
[build]
builder = "NIXPACKS"

[deploy]
startCommand = "uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10
```

### Step 2.4: Set Environment Variables

```bash
# Set via CLI
railway variables set ENVIRONMENT=production
railway variables set PORT=8080
railway variables set LOG_LEVEL=INFO

# Or via dashboard (recommended for secrets)
railway open
# → Variables tab → Add variables
```

**Required variables:**
```env
ENVIRONMENT=production
PORT=8080
LOG_LEVEL=INFO
EMBEDDING_PROVIDER=openai
PYTHONUNBUFFERED=1
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=...
ANTHROPIC_API_KEY=...
QDRANT_URL=https://...
JWT_SECRET_KEY=...
```

### Step 2.5: Deploy

```bash
# Deploy
railway up

# Monitor deployment
railway logs

# Get service URL
railway status
```

**Expected output:**
```
✓ Build successful
✓ Deployment live
🔗 URL: https://nuzantara-backend.up.railway.app
```

### Step 2.6: Test

```bash
# Health check
curl https://nuzantara-backend.up.railway.app/health

# Should return:
# {"status": "healthy", "version": "..."}
```

---

## 3. Frontend Deployment (Vercel)

### Step 3.1: Create Vercel Account

1. Go to https://vercel.com
2. Sign up with GitHub
3. Verify email

### Step 3.2: Import Project

**Via Dashboard:**
1. Click "Add New" → "Project"
2. Import `nuzantara` repository
3. Select `apps/mouth` as root directory
4. Framework: Next.js (auto-detected)
5. Click "Deploy"

**Via CLI:**
```bash
cd /Users/antonellosiano/Desktop/nuzantara/apps/mouth

# Install Vercel CLI
npm install -g vercel

# Deploy
vercel

# Follow prompts:
# - Link to existing project? No
# - Project name: nuzantara-mouth
# - Directory: ./
# - Deploy: Yes
```

### Step 3.3: Environment Variables

**Dashboard:**
1. Go to project → Settings → Environment Variables
2. Add variables for all environments (Production, Preview, Development)

**Required:**
```env
NEXT_PUBLIC_API_URL=https://nuzantara-backend.up.railway.app
NEXT_PUBLIC_WS_URL=wss://nuzantara-backend.up.railway.app
NODE_ENV=production
```

**Via CLI:**
```bash
# Production
vercel env add NEXT_PUBLIC_API_URL production

# Enter value when prompted
```

### Step 3.4: Deploy to Production

```bash
# Deploy to production
vercel --prod

# Get URL
# https://nuzantara-mouth.vercel.app
```

---

## 4. Database Migration

### Step 4.1: Export from Fly.io

```bash
# From project root
./scripts/migration/01-export-flyio-data.sh

# Verify backup created
ls -lh backups/postgres/
```

### Step 4.2: Import to Railway

```bash
# Get Railway DATABASE_URL
railway variables get DATABASE_URL

# Import
./scripts/migration/02-import-railway-postgres.sh

# Verify
./scripts/migration/03-verify-database.sh
```

---

## 5. Environment Variables Reference

### Backend (Railway)

| Variable | Example | Required |
|----------|---------|----------|
| `DATABASE_URL` | Auto-injected by Railway | ✅ |
| `PORT` | `8080` | ✅ |
| `ENVIRONMENT` | `production` | ✅ |
| `OPENAI_API_KEY` | `sk-...` | ✅ |
| `GOOGLE_API_KEY` | `AIza...` | ✅ |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | ✅ |
| `QDRANT_URL` | `https://...` | ✅ |
| `QDRANT_API_KEY` | `...` | ⚠️ |
| `JWT_SECRET_KEY` | Random string | ✅ |
| `TELEGRAM_BOT_TOKEN` | `...` | ⚠️ |
| `SENTRY_DSN` | `https://...` | ⚠️ |

### Frontend (Vercel)

| Variable | Example | Required |
|----------|---------|----------|
| `NEXT_PUBLIC_API_URL` | `https://nuzantara-backend.up.railway.app` | ✅ |
| `NEXT_PUBLIC_WS_URL` | `wss://nuzantara-backend.up.railway.app` | ✅ |
| `NODE_ENV` | `production` | ✅ |

---

## 6. Custom Domains

### Railway Backend

**Dashboard:**
1. Railway dashboard → Project → Settings
2. Domains → Generate Domain
3. Or add custom domain: `api.nuzantara.com`

**DNS Setup:**
```
Type: CNAME
Name: api
Value: nuzantara-backend.up.railway.app
TTL: 300
```

### Vercel Frontend

**Dashboard:**
1. Vercel dashboard → Project → Settings → Domains
2. Add: `app.nuzantara.com`

**DNS Setup:**
```
Type: CNAME
Name: app
Value: cname.vercel-dns.com

# Or A record:
Type: A
Name: @
Value: 76.76.21.21
```

---

## 7. Monitoring & Logs

### Railway Logs

```bash
# Real-time logs
railway logs

# Filter by service
railway logs --service nuzantara-backend

# Follow mode
railway logs --follow
```

**Dashboard:**
- railway.app → Project → Deployments → Click deployment → Logs

### Vercel Logs

```bash
# CLI
vercel logs

# Production only
vercel logs --prod

# Follow mode
vercel logs --follow
```

**Dashboard:**
- vercel.com → Project → Deployments → Click deployment → Logs

### Metrics

**Railway:**
- Dashboard → Project → Metrics
- Shows: CPU, Memory, Network

**Vercel:**
- Dashboard → Project → Analytics
- Shows: Page views, Web Vitals, Top pages

---

## 🚨 Troubleshooting

### Build Fails

**Railway:**
```bash
# Check build logs
railway logs --deployment DEPLOYMENT_ID

# Common fixes:
# 1. Check requirements.txt
# 2. Verify Python version in runtime.txt
# 3. Check start command
```

**Vercel:**
```bash
# Check build output
vercel logs --deployment DEPLOYMENT_ID

# Common fixes:
# 1. Check package.json scripts
# 2. Verify Node version
# 3. Clear build cache
```

### Service Not Responding

```bash
# Railway: Check health
curl https://nuzantara-backend.up.railway.app/health

# If timeout:
# 1. Check Railway logs for errors
# 2. Verify PORT environment variable
# 3. Check healthcheck configuration
```

### Environment Variables Not Working

```bash
# Railway: List all variables
railway variables

# Vercel: Check via dashboard
# Settings → Environment Variables

# Common issues:
# - NEXT_PUBLIC_ prefix required for client-side vars
# - Redeploy after adding variables
```

---

## 📊 Cost Monitoring

### Railway

**Dashboard:**
- Project → Usage → Current billing cycle

**Set Budget Alerts:**
1. Settings → Usage Limits
2. Set monthly limit (e.g., $50)
3. Get email when 80% reached

### Vercel

**Dashboard:**
- Team Settings → Billing → Current usage

**Free tier limits:**
- 100 GB bandwidth/month
- Unlimited deployments
- Commercial use allowed

---

## ✅ Post-Deployment Checklist

- [ ] Health check passing on Railway backend
- [ ] Frontend loading on Vercel
- [ ] Database connected and migrations run
- [ ] Qdrant accessible from backend
- [ ] Environment variables all set
- [ ] Custom domains configured (if any)
- [ ] Monitoring/alerts setup
- [ ] Cost limits configured
- [ ] Team members invited (if applicable)

---

**Questions? Check:**
- Railway Docs: https://docs.railway.app
- Vercel Docs: https://vercel.com/docs
- Railway Discord: https://discord.gg/railway
- Vercel Support: https://vercel.com/support
