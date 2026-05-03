# Intel Router Deployment Guide

**Last Updated:** 2026-01-17

---

## 🚀 Deployment Process

### Overview

Intel Router deployment is done **manually from local machine** directly to Fly.io. The CI/CD pipeline runs tests only, not deployment.

---

## 📋 Pre-Deploy Checklist

- [ ] Code committed and pushed to GitHub
- [ ] All tests pass locally (if possible)
- [ ] Code syntax verified
- [ ] Fly CLI installed and authenticated
- [ ] Backup current deployment (optional)

---

## 🔧 Deployment Methods

### Method 1: Automated Script (Recommended)

Use the automated deployment script that includes pre-deploy checks, deployment, and post-deploy verification:

```bash
./scripts/deployment/deploy_intel_router.sh
```

**What it does:**

1. ✅ Pre-deploy code syntax checks
2. 🚀 Deploys to Fly.io
3. ⏳ Waits for deployment stabilization
4. 🏥 Runs health check
5. 🧪 Runs production tests
6. 📊 Runs monitoring checks

### Method 2: Manual Deployment

**Step 1: Navigate to backend directory**

```bash
cd apps/backend-rag
```

**Step 2: Deploy to Fly.io**

```bash
fly deploy -a nuzantara-rag --remote-only
```

**Step 3: Wait for deployment**

```bash
# Wait ~30 seconds for deployment to stabilize
sleep 30
```

**Step 4: Verify deployment**

```bash
# Health check
curl https://nuzantara-rag.fly.dev/health

# Run production tests
cd ../..
python3 scripts/testing/test_intel_production.py
```

---

## ✅ Post-Deploy Verification

### 1. Health Check

```bash
curl https://nuzantara-rag.fly.dev/health
```

Expected: `{"status":"healthy",...}`

### 2. Production Tests

```bash
python3 scripts/testing/test_intel_production.py
```

Expected: All tests pass or show expected authentication requirements

### 3. Monitor Metrics

```bash
python3 scripts/monitoring/monitor_intel_metrics.py
```

Expected: Metrics within normal range

### 4. Check Performance

```bash
python3 scripts/monitoring/monitor_intel_performance.py 5
```

Expected: Response times < 500ms

### 5. Monitor Logs

```bash
fly logs -a nuzantara-rag --limit 50
```

Look for:

- ✅ No errors
- ✅ Service initialization successful
- ✅ Intel services loaded correctly

---

## 🔄 Rollback Procedure

If deployment causes issues, rollback to previous version:

**Step 1: List releases**

```bash
fly releases -a nuzantara-rag
```

**Step 2: Rollback to previous release**

```bash
fly releases rollback <release-id> -a nuzantara-rag
```

**Step 3: Verify rollback**

```bash
fly status -a nuzantara-rag
curl https://nuzantara-rag.fly.dev/health
```

---

## 📊 Monitoring After Deployment

### Immediate Monitoring (First 5 minutes)

- Check health endpoint
- Monitor logs for errors
- Verify metrics collection
- Test key endpoints

### Short-term Monitoring (First hour)

- Monitor error rates
- Check response times
- Verify staging operations
- Check approval workflow

### Long-term Monitoring (Daily)

- Review daily monitoring reports
- Check performance trends
- Analyze error patterns
- Review metrics

---

## 🚨 Troubleshooting

### Deployment Fails

**Check:**

1. Fly CLI authentication: `fly auth whoami`
2. App exists: `fly apps list`
3. Code syntax: `python3 -m py_compile backend/services/intel/*.py`
4. Network connectivity

**Common Issues:**

- **Build timeout:** Increase timeout or check build logs
- **Dockerfile not found:** Ensure you're in `apps/backend-rag` directory
- **Authentication error:** Run `fly auth login`

### Health Check Fails

**Check:**

1. Deployment status: `fly status -a nuzantara-rag`
2. Machine logs: `fly logs -a nuzantara-rag`
3. Machine health: `fly status -a nuzantara-rag`

**Common Issues:**

- **Port not listening:** Check app configuration
- **Database connection:** Verify Qdrant connection
- **Service initialization:** Check startup logs

### Tests Fail After Deployment

**Check:**

1. Endpoint accessibility
2. Authentication requirements
3. Service availability
4. Network connectivity

**Common Issues:**

- **401 Unauthorized:** Expected for protected endpoints
- **Timeout:** Service may still be starting
- **Connection refused:** Service not ready yet

---

## 📝 Deployment Log Template

Keep a deployment log:

```
Date: YYYY-MM-DD HH:MM
Deployed by: [name]
Commit: [hash]
Version: [version]

Pre-deploy checks: ✅
Deployment: ✅
Health check: ✅
Production tests: ✅
Monitoring: ✅

Notes: [any issues or observations]
```

---

## 🔗 Related Documentation

- [Intel Router Refactoring Summary](../INTEL_ROUTER_REFACTORING_SUMMARY.md)
- [Monitoring & CI/CD Setup](./INTEL_MONITORING_CI_CD_SETUP.md)
- [Deploy Verification Report](./INTEL_ROUTER_DEPLOY_VERIFICATION.md)

---

**Deployment guide complete!** ✅
