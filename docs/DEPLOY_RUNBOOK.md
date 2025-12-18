# 🚀 Zantara Deployment Runbook

**Last Verified**: 2025-12-18 (Phase 1)

Procedura standard per il deploy sicuro delle modifiche backend su Fly.io.

## ⚡ Quick Deploy (Recommended)

Usare sempre lo script automatizzato se possibile. Gestisce git add, commit standardizzato e fly deploy.

```bash
bash deploy_now.sh
```

---

## 🛠 Manual Deployment Steps

Se lo script fallisce o serve controllo granulare.

### 1. Verify Environment
Assicurarsi di essere nella root del progetto.
```bash
pwd
# output: .../nuzantara
```

### 2. Prepare & Commit
```bash
# Check status
git status

# Stage files (esempio)
git add apps/backend-rag/backend/modified_file.py

# Commit (seguire conventional commits)
git commit -m "fix(rag): description of changes"
```

### 3. Push Changes
```bash
git push origin main
```

### 4. Deploy to Fly.io
```bash
cd apps/backend-rag
fly deploy --app nuzantara-rag
```

### 5. Verify Deployment
```bash
# Check logs for startup errors
fly logs --app nuzantara-rag

# Check endpoint health
curl https://nuzantara-rag.fly.dev/health
```

---

## 🚨 Troubleshooting Common Issues

### "Timeout waiting for health checks"
- **Causa**: L'app ci mette troppo ad avviarsi (download modelli, init DB).
- **Fix**: Modifica `apps/backend-rag/fly.toml`:
  ```toml
  [[http_service.checks]]
    grace_period = "5m0s"  # Aumentare questo valore
  ```

### "Migration Lock / Schema Drift"
- **Fix**: Eseguire migrazioni manuali (la release_command è disabilitata per bug wireguard).
  ```bash
  # Via MCP o script locale connesso al DB Fly via proxy
  python -m backend.db.migrate apply-all
  ```
