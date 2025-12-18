# Integration Tests - Comprehensive Suite

Questo documento descrive la suite completa di test di integrazione per il backend Nuzantara.

## Panoramica

La suite di test di integrazione copre tutti i componenti principali del sistema, testando interazioni reali con database PostgreSQL e Qdrant.

## Struttura dei Test

### 1. Test CRM (`test_crm_comprehensive_integration.py`)
- **Client Lifecycle**: Creazione, lettura, aggiornamento, eliminazione clienti
- **Practice Workflow**: Gestione pratiche complete
- **Interaction Tracking**: Logging e recupero interazioni
- **Shared Memory**: Operazioni CRUD su memoria condivisa
- **Analytics**: Query analitiche e reporting
- **Transaction Rollback**: Gestione errori e rollback transazioni

### 2. Test Oracle (`test_oracle_comprehensive_integration.py`)
- **Query Processing**: Elaborazione query con ricerca Qdrant
- **Analytics Storage**: Storage analytics query in PostgreSQL
- **Feedback System**: Storage e recupero feedback
- **Document Ingestion**: Inserimento documenti in Qdrant
- **Multi-Collection Routing**: Routing tra collezioni multiple
- **Session Tracking**: Tracciamento sessioni utente

### 3. Test Autenticazione (`test_authentication_integration.py`)
- **JWT Token**: Generazione e validazione token JWT
- **API Keys**: Validazione chiavi API
- **Middleware**: Integrazione middleware autenticazione
- **Rate Limiting**: Test limitazione rate
- **Error Monitoring**: Monitoraggio errori
- **Database Auth**: Autenticazione con database
- **Token Refresh**: Flusso refresh token

### 4. Test Agenti (`test_agents_comprehensive_integration.py`)
- **ClientJourneyOrchestrator**: Orchestrazione journey clienti
- **ProactiveComplianceMonitor**: Monitoraggio compliance proattivo
- **KnowledgeGraphBuilder**: Costruzione knowledge graph
- **AutonomousResearchService**: Ricerca autonoma
- **CrossOracleSynthesisService**: Sintesi cross-oracle

### 5. Test RAG Services (`test_rag_services_integration.py`)
- **AgenticRAGOrchestrator**: Orchestrazione RAG agentica
- **CulturalRAGService**: RAG culturale
- **Multi-Collection Retrieval**: Recupero multi-collezione
- **Reranking**: Servizio reranking
- **Context Building**: Costruzione contesto
- **Hybrid Search**: Ricerca ibrida

### 6. Test End-to-End (`test_end_to_end_flows.py`)
- **Complete Chat Flow**: Flusso chat completo (query -> search -> RAG -> response)
- **Complete CRM Flow**: Flusso CRM completo (client -> practice -> interaction -> memory)
- **Complete Oracle Flow**: Flusso Oracle completo (query -> routing -> search -> synthesis)
- **Complete Agent Flow**: Flusso agente completo (trigger -> research -> synthesis -> action)

### 7. Test Notifiche (`test_notification_system_integration.py`)
- **Notification Creation**: Creazione e storage notifiche
- **Template System**: Sistema template notifiche
- **Multi-Channel Delivery**: Delivery multi-canale
- **Delivery Tracking**: Tracciamento delivery
- **Error Handling**: Gestione errori e retry

### 8. Test Memoria e Sessioni (`test_memory_session_integration.py`)
- **Memory CRUD**: Operazioni CRUD memoria
- **Fact Extraction**: Estrazione fatti da conversazioni
- **Session Service**: Gestione sessioni
- **Work Session**: Sessioni di lavoro
- **Collective Memory**: Memoria collettiva
- **Deduplication**: Deduplicazione memoria
- **Memory Search**: Ricerca in memoria
- **Statistics**: Statistiche memoria

### 9. Test Router Endpoints (`test_router_endpoints_integration.py`)
- **Handlers Router**: Lista e ricerca handlers
- **Team Activity**: Tracking attività team
- **Productivity Router**: Gestione task produttività
- **Image Generation**: Generazione immagini
- **Legal Ingest**: Inserimento documenti legali
- **WhatsApp Router**: Webhook e messaggi WhatsApp
- **Instagram Router**: Webhook e messaggi Instagram
- **Media Router**: Upload e storage media

### 10. Test Edge Cases (`test_edge_cases_integration.py`)
- **Database Edge Cases**: Pool exhaustion, deadlock, rollback
- **Qdrant Edge Cases**: Collection not found, large payloads, empty results
- **Input Validation**: SQL injection, XSS prevention, large input
- **Concurrency**: Concurrent writes, race conditions
- **Timeouts**: Query timeouts, long transactions

### 11. Test Performance (`test_performance_integration.py`)
- **Database Performance**: Bulk insert, indexed queries, connection pool
- **Qdrant Performance**: Bulk insert, search performance
- **Caching Performance**: Cache hit performance
- **Concurrent Requests**: Concurrent database queries, concurrent searches

### 12. Test Scenari Completi (`test_comprehensive_scenarios.py`)
- **Client Onboarding**: Flusso completo onboarding clienti
- **Practice Lifecycle**: Gestione lifecycle pratica completa
- **Complex Query**: Query complesse multi-collezione
- **Team Collaboration**: Collaborazione team su clienti
- **Compliance Monitoring**: Workflow monitoraggio compliance

## Setup e Configurazione

### Prerequisiti

1. **PostgreSQL**: Database PostgreSQL disponibile (via Docker o locale)
2. **Qdrant**: Istanza Qdrant disponibile (via Docker o locale)
3. **Python Dependencies**: Tutte le dipendenze installate

### Variabili d'Ambiente

```bash
export DATABASE_URL="postgresql://test:test@localhost:5432/test"
export QDRANT_URL="http://localhost:6333"
export JWT_SECRET_KEY="test_jwt_secret_key_for_testing_only_min_32_chars"
export API_KEYS="test_api_key_1,test_api_key_2"
export OPENAI_API_KEY="test_openai_api_key_for_testing"
export GOOGLE_API_KEY="test_google_api_key_for_testing"
```

### Esecuzione Test

#### Eseguire tutti i test di integrazione:
```bash
pytest tests/integration/ -v -m integration
```

#### Eseguire un file specifico:
```bash
pytest tests/integration/test_crm_comprehensive_integration.py -v
```

#### Eseguire test con database:
```bash
pytest tests/integration/ -v -m "integration and database"
```

#### Eseguire test end-to-end (lenti):
```bash
pytest tests/integration/test_end_to_end_flows.py -v -m slow
```

## Fixtures Disponibili

### Database Fixtures
- `postgres_container`: Container PostgreSQL per test
- `db_pool`: Pool connessioni asyncpg
- `memory_service`: Istanza MemoryServicePostgres

### Qdrant Fixtures
- `qdrant_container`: Container Qdrant per test
- `qdrant_client`: Client Qdrant

### Service Fixtures
- `search_service`: SearchService con Qdrant test
- `cleanup_test_data`: Cleanup automatico dati test

## Copertura Test

### Servizi Testati
- ✅ CRM Services (AutoCRM, ClientJourney, ProactiveCompliance)
- ✅ Oracle Services (Query, Ingestion, Analytics)
- ✅ RAG Services (AgenticRAG, CulturalRAG, CrossOracle)
- ✅ Memory Services (MemoryService, SessionService, WorkSession)
- ✅ Notification Services (NotificationHub, Templates, Delivery)
- ✅ Authentication (JWT, API Keys, Middleware)
- ✅ Agent Services (All 10 agents)
- ✅ Productivity Services (Task management)
- ✅ Image Generation Services
- ✅ Legal Ingestion Services

### Router Testati
- ✅ CRM Routers (Clients, Practices, Interactions, Shared Memory)
- ✅ Oracle Routers (Universal, Ingest)
- ✅ Agent Routers (All agent endpoints)
- ✅ Authentication Routers
- ✅ Memory Routers
- ✅ Handlers Router
- ✅ Team Activity Router
- ✅ Productivity Router
- ✅ Media Router
- ✅ Image Generation Router
- ✅ Legal Ingest Router
- ✅ WhatsApp Router
- ✅ Instagram Router

### Flussi End-to-End
- ✅ Complete Chat Flow
- ✅ Complete CRM Flow
- ✅ Complete Oracle Flow
- ✅ Complete Agent Flow
- ✅ Client Onboarding Flow
- ✅ Practice Lifecycle Flow
- ✅ Team Collaboration Flow
- ✅ Compliance Monitoring Flow

### Edge Cases e Performance
- ✅ Database Edge Cases (Pool exhaustion, deadlock, rollback)
- ✅ Qdrant Edge Cases (Large payloads, empty results)
- ✅ Input Validation (SQL injection, XSS prevention)
- ✅ Concurrency Tests (Race conditions, concurrent writes)
- ✅ Performance Tests (Bulk operations, caching, concurrent requests)
- ✅ Timeout Scenarios

## Best Practices

1. **Isolamento**: Ogni test è isolato e pulisce i propri dati
2. **Realistic Data**: Usa dati realistici per test più significativi
3. **Error Handling**: Testa sia successi che fallimenti
4. **Performance**: Test end-to-end sono marcati come `slow`
5. **Documentation**: Ogni test ha docstring descrittiva

## Troubleshooting

### Database Connection Errors
- Verifica che PostgreSQL sia in esecuzione
- Controlla `DATABASE_URL` nelle variabili d'ambiente
- Verifica permessi database

### Qdrant Connection Errors
- Verifica che Qdrant sia in esecuzione
- Controlla `QDRANT_URL` nelle variabili d'ambiente
- Verifica accesso alla rete

### Test Failures
- Controlla log per dettagli errori
- Verifica che tutti i servizi siano disponibili
- Assicurati che i dati di test siano puliti

## Contribuire

Quando aggiungi nuovi test:
1. Segui la struttura esistente
2. Usa fixtures appropriate
3. Pulisci dati dopo ogni test
4. Aggiungi docstring descrittive
5. Marca test lenti con `@pytest.mark.slow`

