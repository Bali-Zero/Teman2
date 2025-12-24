# Deploy Checklist - Sanatoria Profonda

Checklist per deploy controllato delle modifiche della sanatoria profonda.

## Pre-Deploy

### 1. Verifica Modifiche

- [x] Fix middleware auth (serializzazione Pool)
- [x] Miglioramenti diagnostica 503
- [x] Fallback query monthly_revenue_view
- [x] Health endpoint migliorato
- [x] Frontend: gestione 401 con redirect
- [x] Dashboard: cleanup mock + status degraded

### 2. Test Locali

```bash
# Backend tests
cd apps/backend-rag
pytest tests/api/test_crm_stats_503_regression.py -v

# Frontend tests (se disponibili)
cd apps/mouth
npm test
```

### 3. Verifica Secrets Fly.io

```bash
# Verifica DATABASE_URL configurato
flyctl secrets list -a nuzantara-rag | grep DATABASE_URL

# Verifica altri secrets necessari
flyctl secrets list -a nuzantara-rag
```

### 4. Backup Database

```bash
# Crea backup prima del deploy
flyctl postgres backups create -a nuzantara-postgres
```

---

## Deploy

### 1. Deploy Backend

```bash
cd apps/backend-rag
flyctl deploy -a nuzantara-rag
```

### 2. Monitor Logs

```bash
# Monitora logs durante deploy
flyctl logs -a nuzantara-rag --follow

# Cerca errori di inizializzazione
flyctl logs -a nuzantara-rag | grep -i "database\|db_pool\|error\|503"
```

### 3. Verifica Health

```bash
# Attendi che l'app sia pronta (circa 30-60 secondi)
sleep 60

# Verifica health endpoint
curl https://nuzantara-rag.fly.dev/api/health | jq .

# Verifica database status
curl https://nuzantara-rag.fly.dev/api/health/detailed | jq '.services.database'
```

---

## Post-Deploy Verification

### 1. Test Endpoint Stats

```bash
# Ottieni token JWT
TOKEN=$(curl -s -X POST https://nuzantara-rag.fly.dev/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"zero@balizero.com","pin":"010719"}' | jq -r '.data.token')

# Test practices stats
curl -H "Authorization: Bearer $TOKEN" \
  https://nuzantara-rag.fly.dev/api/crm/practices/stats/overview | jq .

# Test interactions stats
curl -H "Authorization: Bearer $TOKEN" \
  https://nuzantara-rag.fly.dev/api/crm/interactions/stats/overview | jq .
```

**Risultato atteso**: Status 200 con dati JSON validi

### 2. Test Frontend Dashboard

1. Accedi a `https://nuzantara-mouth.fly.dev/login`
2. Login come `zero@balizero.com`
3. Verifica dashboard carica correttamente
4. Verifica widget AI Pulse e Financial Reality visibili (solo per zero@balizero.com)
5. Verifica banner "System Partial Outage" se ci sono errori API

### 3. Test Error Handling

```bash
# Simula errore database (se possibile)
# Verifica che restituisca 503 con messaggio sicuro (no Pool serializzato)
```

### 4. Health Check Script

```bash
# Esegui health check completo
cd apps/backend-rag
python scripts/health_check.py
```

**Risultato atteso**: Tutti i servizi "healthy" o "degraded" (non "unavailable")

---

## Rollback Plan

Se qualcosa va storto:

### Rollback Rapido

```bash
# Rollback all'ultima versione funzionante
flyctl releases -a nuzantara-rag
flyctl releases rollback <release-id> -a nuzantara-rag
```

### Rollback Database (se necessario)

```bash
# Lista backup disponibili
flyctl postgres backups list -a nuzantara-postgres

# Restore backup (ATTENZIONE: distruttivo)
flyctl postgres backups restore <backup-id> -a nuzantara-postgres
```

---

## Monitoring Post-Deploy

### Primi 30 Minuti

Monitora attentamente:

```bash
# Logs errori
flyctl logs -a nuzantara-rag | grep -i "error\|503\|exception"

# Metriche performance
flyctl metrics -a nuzantara-rag

# Health endpoint
watch -n 5 'curl -s https://nuzantara-rag.fly.dev/api/health/detailed | jq ".services.database"'
```

### Primo Giorno

- [ ] Verifica che non ci siano picchi di errori 503
- [ ] Verifica che il database pool si inizializzi correttamente
- [ ] Verifica che gli endpoint stats rispondano correttamente
- [ ] Verifica che il frontend gestisca correttamente i 401

---

## Issue Noted

Se riscontri problemi:

1. **503 persistente**: Verifica logs startup per errori database
2. **Dashboard non carica**: Verifica frontend logs e proxy API
3. **401 loop**: Verifica gestione token nel frontend
4. **Dati mancanti**: Verifica che le migrazioni siano applicate

---

## Success Criteria

Deploy considerato riuscito se:

- ✅ Tutti gli endpoint stats restituiscono 200 (non 503)
- ✅ Health endpoint mostra database "healthy"
- ✅ Dashboard carica correttamente con dati reali
- ✅ Widget Zero-only visibili solo per zero@balizero.com
- ✅ Banner status degraded appare quando necessario
- ✅ Nessun errore critico nei logs

---

**Data Deploy**: _______________
**Deployato da**: _______________
**Status**: ☐ Success ☐ Failed ☐ Rollback

---

## Recent Deployments Log

### v857 - 2025-12-22 (google-genai SDK Migration + Exception Handlers Fix)

**Changes**:
- Migrated from `google-generativeai` to `google-genai` SDK
- Fixed OpenAI/httpx compatibility (`openai>=1.57.0`)
- Updated all GenAI mocking patterns in tests
- **Added global exception handlers** (`exception_handlers.py`) to prevent TypeError during HTTPException serialization
- **Fixed ImportError** in `nusantara_health.py` (changed relative import `...services` to absolute `services`)

**Final Dependencies**:
- `google-genai` 1.56.0
- `openai` 2.14.0
- `httpx` 0.28.1

**Status**: ✅ Success
**Health Check**: `{"status":"healthy","version":"v100-qdrant","database":{"collections":4,"total_documents":53757}}`
**Machine Status**: 1/1 passing ✅
**Fix Verification**:
- ✅ No TypeError in logs (exception handlers working)
- ✅ No ImportError in logs (nusantara_health.py fixed)
- ✅ Health checks passing
- ✅ Login functional


