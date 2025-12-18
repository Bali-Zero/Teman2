# Piano per Raggiungere 100% Test Coverage

## Coverage Attuale: 87.20%

### File con Coverage < 90% (Priorità Alta)

#### Coverage 0%
1. **backend/services/team_analytics_service.py** - 0.00% (221 linee)
   - Test esistenti falliscono
   - Necessita fix test + nuovi test

2. **backend/services/vertex_ai_service.py** - 0.00% (43 linee)
   - Nessun test esistente
   - Creare test completi

#### Coverage < 30%
3. **backend/services/search_service.py** - 7.27% (284 linee non coperte)
   - Test esistenti falliscono
   - Necessita fix test + nuovi test

4. **backend/services/legal_ingestion_service.py** - 23.96% (55 linee)
   - Creare test per metodi non coperti

5. **backend/app/routers/health.py** - 26.52% (77 linee)
   - Creare test per endpoint non coperti

6. **backend/services/gemini_service.py** - 35.29% (28 linee)
   - Creare test per metodi non coperti

#### Coverage 50-90%
7. **backend/services/context/rag_manager.py** - 68.46% (28 linee)
8. **backend/services/context/context_builder.py** - 81.35% (19 linee)
9. **backend/core/qdrant_db.py** - 82.87% (22 linee)
10. **backend/services/emotional_attunement.py** - 87.98% (13 linee)
11. **backend/services/politics_ingestion.py** - 89.66% (11 linee)
12. **backend/services/session_service.py** - 90.08% (21 linee)
13. **backend/services/health_monitor.py** - 92.09% (8 linee)
14. **backend/services/notification_hub.py** - 91.98% (11 linee)
15. **backend/services/memory_service_postgres.py** - 91.81% (13 linee)
16. **backend/services/intelligent_router.py** - 85.19% (11 linee)

### File Esclusi in .coveragerc (da Includere)

Per raggiungere 100%, dobbiamo includere e testare:

1. **Routers** (attualmente esclusi):
   - `backend/app/routers/auth.py`
   - `backend/app/routers/crm_clients.py`
   - `backend/app/routers/ingest.py`
   - `backend/app/routers/instagram.py`
   - `backend/app/routers/intel.py`
   - `backend/app/routers/media.py`
   - `backend/app/routers/oracle_universal.py` ✅ (già testato)
   - `backend/app/routers/team_activity.py`
   - `backend/app/routers/websocket.py`
   - `backend/app/routers/whatsapp.py`
   - `backend/app/routers/productivity.py`
   - `backend/app/routers/conversations.py`
   - `backend/app/routers/agents.py`

2. **Services** (attualmente esclusi):
   - `backend/services/calendar_service.py`
   - `backend/services/gmail_service.py`
   - `backend/services/audit_service.py`

3. **Core Modules** (attualmente esclusi):
   - `backend/core/embeddings.py`
   - `backend/core/parsers.py`

4. **LLM Client** (attualmente escluso):
   - `backend/llm/zantara_ai_client.py`

5. **Middleware** (attualmente esclusi):
   - `backend/middleware/hybrid_auth.py`
   - `backend/middleware/rate_limiter.py`
   - `backend/middleware/error_monitoring.py`

6. **Identity Module** (attualmente escluso):
   - `backend/app/modules/identity/*.py` ✅ (già testato parzialmente)

## Strategia per Raggiungere 100%

### Fase 1: Fix Test Falliti (In Progress)
- ✅ test_api_key_auth.py (80 test passano)
- ✅ test_router_oracle_universal.py (tutti passano)
- ⏳ test_search_service.py (4 fallimenti)
- ⏳ test_team_analytics_service.py (1 fallimento)
- ⏳ test_parsers.py (1 fallimento)
- ⏳ test_rag_optimization.py (2 fallimenti)
- ⏳ test_router_conversations.py (1 fallimento)
- ⏳ test_llm_zantara_ai_client.py (2 fallimenti)
- ⏳ test_identity_service.py (2 fallimenti)

### Fase 2: Creare Test per File con Coverage Bassa

#### Priorità 1: Coverage 0%
1. **team_analytics_service.py** (0%)
   - Creare test per tutti i metodi
   - Fixare test esistenti che falliscono

2. **vertex_ai_service.py** (0%)
   - Creare test completi

#### Priorità 2: Coverage < 30%
3. **search_service.py** (7.27%)
   - Fixare test esistenti
   - Creare test per metodi non coperti

4. **legal_ingestion_service.py** (23.96%)
   - Creare test per metodi non coperti

5. **health.py router** (26.52%)
   - Creare test per endpoint non coperti

6. **gemini_service.py** (35.29%)
   - Creare test per metodi non coperti

#### Priorità 3: Coverage 50-90%
- Creare test per linee mancanti nei file elencati sopra

### Fase 3: Rimuovere Esclusioni e Creare Test

1. Rimuovere esclusioni da `.coveragerc` per file testabili
2. Creare test per ogni file rimosso
3. Verificare coverage dopo ogni rimozione

### Fase 4: Verifica Finale

1. Eseguire coverage completo
2. Verificare 100% coverage
3. Aggiornare `.coveragerc` con `fail_under=100`

## Stima Linee da Coprire

- **File con coverage 0%**: ~264 linee
- **File con coverage < 30%**: ~444 linee
- **File con coverage 50-90%**: ~200 linee
- **File esclusi**: ~2000+ linee (da valutare)

**Totale stimato**: ~2900+ linee da coprire

## Prossimi Passi Immediati

1. **Fixare test falliti rimanenti** (13 test)
2. **Creare test per team_analytics_service.py** (0% → 100%)
3. **Creare test per vertex_ai_service.py** (0% → 100%)
4. **Fixare e completare test per search_service.py** (7% → 100%)
5. **Creare test per legal_ingestion_service.py** (24% → 100%)
6. **Creare test per health.py router** (27% → 100%)
7. **Creare test per gemini_service.py** (35% → 100%)
8. **Completare coverage per file 50-90%**
9. **Rimuovere esclusioni e creare test**

## Note

- Alcuni file possono essere esclusi per motivi validi (entry points, script)
- Focus su business logic e API endpoints
- Usare mocking per dipendenze esterne
- Mantenere test veloci e isolati

