# Deploy Backend RAG

Deploy del backend FastAPI su Fly.io con health check automatico.

## Istruzioni

1. **Pre-deploy checks**:
   - Verifica che non ci siano errori di sintassi: `cd apps/backend-rag && python -m py_compile backend/app/main_cloud.py`
   - Verifica che i test critici passino: `pytest tests/unit/test_health_router.py -v`

2. **Deploy su Fly.io**:
   ```bash
   cd apps/backend-rag && fly deploy --remote-only
   ```

3. **Post-deploy verification**:
   - Attendi 30 secondi per il warmup
   - Verifica health: `curl -s https://nuzantara-rag.fly.dev/health | jq`
   - Verifica readiness: `curl -s https://nuzantara-rag.fly.dev/health/ready | jq`
   - Se fallisce, mostra logs: `fly logs -a nuzantara-rag -n 50`

4. **Rollback automatico**:
   - Se health check fallisce dopo 3 tentativi, suggerisci rollback
   - Comando rollback: `fly releases -a nuzantara-rag` poi `fly deploy -a nuzantara-rag --image <previous-image>`

## Output atteso

```
## Deploy Backend RAG

### Pre-checks
- [x] Syntax check: OK
- [x] Health tests: OK (2 passed)

### Deploy
- [x] Build: OK (2m 30s)
- [x] Deploy: OK (machine started)

### Health Check
- [x] /health: OK (status: healthy)
- [x] /health/ready: OK (qdrant: connected, postgres: connected)

### Summary
Deploy completato con successo!
URL: https://nuzantara-rag.fly.dev
```
