# Test Coverage Status - Backend RAG

## Obiettivo: 100% Test Coverage

## Stato Attuale

### ✅ Completato

1. **Configurazione Test Base**
   - ✅ Fixato `conftest.py` per impostare variabili d'ambiente richieste
   - ✅ Aggiunte variabili: `JWT_SECRET_KEY`, `API_KEYS`, `WHATSAPP_VERIFY_TOKEN`, `INSTAGRAM_VERIFY_TOKEN`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`

2. **Test Identity Router**
   - ⚠️ Parzialmente fixato: alcuni test commentati per endpoint rimossi
   - ⚠️ Problemi di sintassi rimanenti che devono essere risolti

### ⚠️ In Progress

1. **Fix Test Identity Router**
   - File: `apps/backend-rag/tests/unit/test_identity_router.py`
   - Problema: Alcuni test hanno ancora problemi di sintassi dopo il commento degli endpoint rimossi
   - Endpoint rimossi che necessitano test commentati:
     - `seed_team_endpoint`
     - `run_migration_010`
     - `debug_auth`
     - `reset_admin_user`

### 📋 Da Fare

1. **Fix Completo Test Identity Router**
   ```bash
   # Verificare e correggere manualmente il file
   python -m py_compile apps/backend-rag/tests/unit/test_identity_router.py
   ```

2. **Eseguire Coverage Analysis**
   ```bash
   cd apps/backend-rag
   python -m coverage run --source=backend -m pytest tests/unit -v
   python -m coverage report --show-missing
   ```

3. **Identificare File Non Coperti**
   - Analizzare il report di coverage
   - Creare test per file/moduli non coperti

4. **Rimuovere Esclusioni Non Necessarie da .coveragerc**
   - Verificare quali file esclusi possono essere testati
   - Creare test appropriati

5. **Verificare 100% Coverage**
   ```bash
   python -m coverage report --fail-under=100
   ```

## File Esclusi da Coverage (da .coveragerc)

I seguenti file sono attualmente esclusi dalla coverage. Per raggiungere il 100%, alcuni di questi devono essere inclusi e testati:

### Entry Points (giustificati)
- `backend/app/main_cloud.py` - Entry point principale
- `backend/app/main.py` - Entry point alternativo
- `backend/populate_inline.py` - Script di popolazione

### Agent Runners (giustificati)
- `backend/agents/run_*.py`
- `backend/agents/agents/*.py`

### Moduli con Problemi (da testare)
- `backend/app/feature_flags.py`
- `backend/app/metrics.py`
- `backend/app/modules/identity/*.py` - ⚠️ Da includere e testare

### Router con Low Coverage (da testare)
- `backend/app/routers/auth.py`
- `backend/app/routers/crm_clients.py`
- `backend/app/routers/ingest.py`
- `backend/app/routers/instagram.py`
- `backend/app/routers/intel.py`
- `backend/app/routers/media.py`
- `backend/app/routers/oracle_universal.py`
- `backend/app/routers/team_activity.py`
- `backend/app/routers/websocket.py`
- `backend/app/routers/whatsapp.py`
- `backend/app/routers/productivity.py`
- `backend/app/routers/conversations.py`
- `backend/app/routers/agents.py`

### Services con Problemi (da testare)
- `backend/services/calendar_service.py`
- `backend/services/gmail_service.py`
- `backend/services/audit_service.py`

### Core Modules (da testare)
- `backend/core/embeddings.py` - ⚠️ Critico
- `backend/core/parsers.py`

### LLM Client (da testare con mock)
- `backend/llm/zantara_ai_client.py` - ⚠️ Critico

### Middleware (da testare)
- `backend/middleware/hybrid_auth.py`
- `backend/middleware/rate_limiter.py`
- `backend/middleware/error_monitoring.py`

## Strategia per Raggiungere 100%

### Fase 1: Fix Test Esistenti ✅ (Parzialmente Completato)
- [x] Fix conftest.py
- [ ] Fix completo test_identity_router.py
- [ ] Verificare tutti i test passano

### Fase 2: Coverage Analysis
- [ ] Eseguire coverage su tutti i test
- [ ] Identificare file/moduli con coverage < 100%
- [ ] Creare lista prioritaria

### Fase 3: Creare Test Mancanti
- [ ] Test per router esclusi
- [ ] Test per services esclusi
- [ ] Test per core modules esclusi
- [ ] Test per middleware esclusi

### Fase 4: Rimuovere Esclusioni
- [ ] Rimuovere esclusioni non giustificate da .coveragerc
- [ ] Verificare coverage dopo rimozione
- [ ] Aggiungere test se necessario

### Fase 5: Verifica Finale
- [ ] Eseguire coverage completo
- [ ] Verificare 100% coverage
- [ ] Aggiornare .coveragerc con fail_under=100

## Comandi Utili

```bash
# Eseguire tutti i test
cd apps/backend-rag
python -m pytest tests/unit -v

# Eseguire coverage
python -m coverage run --source=backend -m pytest tests/unit
python -m coverage report --show-missing
python -m coverage html  # Genera report HTML

# Verificare sintassi file Python
python -m py_compile path/to/file.py

# Verificare import
python -c "import app.core.config; print('OK')"
```

## Note

- Alcuni file possono essere esclusi per motivi validi (entry points, script)
- Focus su file di business logic e API endpoints
- Usare mocking per dipendenze esterne (API keys, database, etc.)
- Mantenere test veloci e isolati
