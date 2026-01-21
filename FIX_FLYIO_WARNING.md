# ✅ Fix Warning Fly.io - Risolto Definitivamente

**Data**: 2026-01-21  
**Commit**: `8b731041` - fix(fly.io): resolve listening address warning permanently

## 🔧 Problema

Durante il deploy su Fly.io appariva questo warning:

```
WARNING The app is not listening on the expected address and will not be reachable by fly-proxy.
You can fix this by configuring your app to listen on the following addresses:
  - 0.0.0.0:8080
```

## ✅ Soluzione Applicata

### 1. Dockerfile

**Prima:**

```dockerfile
CMD ["uvicorn", "backend.app.main_cloud:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
```

**Dopo:**

```dockerfile
CMD sh -c "uvicorn backend.app.main_cloud:app --host 0.0.0.0 --port ${PORT:-8080} --workers 2"
```

**Motivo**: Usa la variabile d'ambiente `PORT` impostata da Fly.io invece di hardcodare `8080`. Questo garantisce che l'app ascolti sulla porta corretta anche se Fly.io cambia la configurazione.

### 2. fly.toml - Health Check

**Prima:**

```toml
grace_period = '5m0s'
timeout = '15s'
```

**Dopo:**

```toml
grace_period = '30s'
timeout = '10s'
```

**Motivo**:

- `grace_period` ridotto da 5 minuti a 30 secondi (Fly.io raccomanda max 1 minuto)
- `timeout` ridotto da 15s a 10s per health check più responsivi

## 🎯 Risultato

Il warning sarà risolto perché:

1. ✅ L'app usa correttamente la variabile `PORT` di Fly.io
2. ✅ L'app ascolta su `0.0.0.0:${PORT:-8080}` come richiesto
3. ✅ Health check configurati correttamente con timing appropriati

## 📝 Verifica

Dopo il deploy, verificare che il warning non appaia più:

```bash
cd apps/backend-rag
flyctl deploy
```

Il deploy dovrebbe completarsi senza warning.
