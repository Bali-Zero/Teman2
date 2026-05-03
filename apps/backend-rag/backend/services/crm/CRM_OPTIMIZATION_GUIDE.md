# CRM Optimization Guide

## Overview

Il modulo CRM è stato ottimizzato per produzione con validazione robusta, caching intelligente, audit trail completo e query ottimizzate.

## New Modules

### 1. validators.py

Validazione Pydantic per dati CRM:

- `ClientValidator` - Validazione clienti
- `PracticeValidator` - Validazione pratiche
- `InteractionValidator` - Validazione interazioni
- `normalize_phone_e164()` - Normalizzazione telefoni
- `extract_entities_from_text()` - Estrazione entità da testo

### 2. cache_manager.py

Sistema di caching livello applicazione:

- `crm_cache` - Cache generica con TTL
- `query_cache` - Cache query specifiche (email, phone, practice_types)
- `cache_crm_result()` - Decorator per caching automatico
- `invalidate_client_cache()` - Invalidazione selettiva

### 3. query_optimizer.py

Query ottimizzate e batch operations:

- `CRMQueryOptimizer` - Query builder ottimizzato
- `batch_insert_clients()` - Insert batch clienti
- `get_clients_with_practices()` - Single query con join
- `search_clients_optimized()` - Ricerca con ranking
- `health_check_crm_tables()` - Verifica integrità

### 4. audit_trail.py

Audit logging completo:

- `CRMAuditor` - Sistema audit
- `AuditAction` - Enum azioni tracciabili
- `init_audit_table()` - Setup tabella audit
- Auto-flushing buffer (100 entries)

### 5. enhanced_crm_service.py

Servizio unificato production-ready:

- Validazione automatica
- Caching integrato
- Audit trail automatico
- Error handling robusto
- Batch operations

## Usage Examples

### Basic Client Creation

```python
from backend.services.crm import get_enhanced_crm_service

service = await get_enhanced_crm_service(db_pool)

client = await service.create_client(
    client_data={
        "full_name": "John Doe",
        "email": "john@example.com",
        "phone": "+628123456789",
        "nationality": "US"
    },
    user_id="admin@example.com",
    metadata={"ip_address": "1.2.3.4"}
)
```

### Validazione Manuale

```python
from backend.services.crm import ClientValidator, normalize_phone_e164

# Validazione
try:
    validated = ClientValidator(
        full_name="John Doe",
        email="john@example.com",
        phone="0812-3456-7890"
    )
    print(validated.phone)  # Normalizzato
except ValueError as e:
    print(f"Invalid: {e}")

# Normalizzazione telefono
normalized = normalize_phone_e164("0812-3456-7890")
# Result: "+6281234567890"
```

### Caching

```python
from backend.services.crm import crm_cache, invalidate_client_cache

# Salva in cache
await crm_cache.set("key", value, ttl=300)

# Recupera
cached = await crm_cache.get("key")

# Invalida per cliente
invalidate_client_cache(client_id=123)
```

### Audit Trail

```python
from backend.services.crm import CRMAuditor, AuditAction

auditor = CRMAuditor(db_pool)

# Log manuale
await auditor.log(
    action=AuditAction.CLIENT_UPDATED,
    entity_type="client",
    entity_id=123,
    user_id="admin@example.com",
    old_values={"status": "inactive"},
    new_values={"status": "active"}
)

# Recupero audit trail
logs, total = await auditor.get_audit_trail(
    entity_type="client",
    entity_id=123,
    limit=50
)
```

### Batch Operations

```python
# Batch insert
client_ids = await service.batch_create_clients([
    {"full_name": "Client 1", "email": "c1@test.com"},
    {"full_name": "Client 2", "email": "c2@test.com"},
])

# Batch update
updated = await optimizer.batch_update_practices([
    {"id": 1, "status": "completed"},
    {"id": 2, "status": "in_progress"},
])
```

## Performance Improvements

1. **Query Optimization**
   - Single query con JOIN per clienti + pratiche
   - Batch insert/update riduce round-trip DB
   - Indici per email, phone, status

2. **Caching Strategy**
   - Practice types: 1 ora TTL (raramente cambiano)
   - Client by email/phone: 10 min TTL
   - Query results: 5 min TTL
   - Invalidazione selettiva su update

3. **Audit Optimization**
   - Buffer 100 entries prima di flush
   - Batch insert audit logs
   - JSONB per flessibilità

## Database Schema

### Audit Table

```sql
CREATE TABLE crm_audit_log (
    id SERIAL PRIMARY KEY,
    action VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(100) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    changes JSONB,
    old_values JSONB,
    new_values JSONB,
    metadata JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_audit_action ON crm_audit_log(action);
CREATE INDEX idx_audit_user ON crm_audit_log(user_id);
CREATE INDEX idx_audit_created ON crm_audit_log(created_at);
```

## Error Handling

Tutte le operazioni usano custom exceptions:

- `ValidationError` - Input non valido
- `ResourceNotFoundError` - Risorsa non trovata
- `DatabaseError` - Errore database

Errori sono sanitizzati per non leakare info sensibili.

## Migration from Old Service

```python
# Old way
from backend.services.crm import AutoCRMService
service = AutoCRMService(db_pool=pool)

# New way (enhanced)
from backend.services.crm import get_enhanced_crm_service
service = await get_enhanced_crm_service(db_pool)

# API compatible
client = await service.create_client(data, user_id="admin")
```

## Testing

```python
# Test validazione
from backend.services.crm.validators import ClientValidator

validator = ClientValidator(full_name="Test", email="invalid")
# Raises: ValidationError

# Test cache
from backend.services.crm.cache_manager import crm_cache
await crm_cache.set("test", {"data": 123})
assert await crm_cache.get("test") == {"data": 123}
```

## Monitoring

```python
# Health check
health = await service.health_check()
print(health)
# {
#     "clients": {"count": 150},
#     "practices": {"count": 320},
#     "orphan_clients": 0,
#     "orphan_practices": 0
# }

# Statistics
stats = await service.get_statistics()
print(stats)
# {
#     "by_status": {"in_progress": 50, "completed": 100},
#     "by_priority": {"high": 20, "normal": 80},
#     "financials": {"total_quoted": 5000000, "total_paid": 3000000}
# }
```

## Best Practices

1. **Usa sempre EnhancedCRMService** per nuovo codice
2. **Valida input** prima di chiamare servizi
3. **Sfrutta il caching** per query frequenti
4. **Logga metadati** (IP, user agent) per audit
5. **Gestisci errori** con try/except specifici
6. **Invalida cache** dopo update/delete
7. **Usa batch operations** per operazioni massive
