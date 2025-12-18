# 🧪 Plugin System Testing Guide

**Data creazione**: 2025-12-07  
**Status**: ✅ Test Suite Completa

---

## 📋 Test Coverage

### Unit Tests Implementati

1. **Plugin Discovery** (`test_plugin_discovery_startup.py`)
   - ✅ Discovery returns results
   - ✅ Strict mode handling
   - ✅ Error collection
   - ✅ Invalid package prefix handling
   - ✅ Private files skipping
   - ✅ Invalid module segment handling

2. **Admin Authentication** (`test_plugin_admin_auth.py`)
   - ✅ Valid admin API key
   - ✅ Invalid admin API key
   - ✅ Missing admin API key
   - ✅ JWT admin token
   - ✅ Non-admin JWT token

3. **Distributed Rate Limiting** (`test_plugin_distributed_rate_limiting.py`)
   - ✅ Redis-based rate limiting
   - ✅ Rate limit exceeded handling
   - ✅ Redis fallback to memory
   - ✅ Per-user rate limiting
   - ✅ Memory fallback
   - ✅ Redis expiration

4. **Startup Integration** (`test_plugin_startup_integration.py`)
   - ✅ Successful plugin discovery
   - ✅ Error handling
   - ✅ Plugins directory finding

---

## 🚀 Eseguire i Test

### Tutti i Test Plugin

```bash
cd apps/backend-rag
python -m pytest tests/unit/test_plugin*.py -v
```

### Test Specifici

```bash
# Test discovery
python -m pytest tests/unit/test_plugin_discovery_startup.py -v

# Test admin auth
python -m pytest tests/unit/test_plugin_admin_auth.py -v

# Test rate limiting
python -m pytest tests/unit/test_plugin_distributed_rate_limiting.py -v

# Test startup integration
python -m pytest tests/unit/test_plugin_startup_integration.py -v
```

### Script di Test Manuale

```bash
cd apps/backend-rag
python scripts/test_plugin_system.py
```

Questo script testa:
- Plugin discovery
- Plugin execution
- Rate limiting
- Metrics collection

---

## ✅ Checklist Pre-Deploy

- [x] Plugin discovery funziona all'avvio
- [x] Admin authentication implementata e testata
- [x] User ID validation corretta
- [x] Distributed rate limiting funziona
- [x] Error handling migliorato
- [x] Unit tests aggiunti
- [ ] Integration tests eseguiti in ambiente di sviluppo
- [ ] Load testing con Redis

---

## 🔧 Test Manuali

### 1. Test Plugin Discovery all'Avvio

```bash
# Avvia l'applicazione
cd apps/backend-rag
python -m uvicorn app.main_cloud:app --reload

# Verifica nei log che i plugin vengono scoperti:
# "Plugin System: Discovered X plugins in Y categories"

# Oppure chiama l'endpoint:
curl http://localhost:8080/api/plugins/health
```

### 2. Test Admin Authentication

```bash
# Test senza admin key (dovrebbe fallire)
curl -X POST http://localhost:8080/api/plugins/test.plugin/reload \
  -H "Content-Type: application/json"

# Test con admin key valida
export ADMIN_API_KEY="your-admin-key"
curl -X POST http://localhost:8080/api/plugins/test.plugin/reload \
  -H "Content-Type: application/json" \
  -H "x-admin-key: $ADMIN_API_KEY"
```

### 3. Test Distributed Rate Limiting

```bash
# Esegui multiple richieste rapidamente
for i in {1..10}; do
  curl http://localhost:8080/api/plugins/bali_zero.pricing/execute \
    -X POST \
    -H "Content-Type: application/json" \
    -d '{"input_data": {"service_type": "all"}}'
  echo ""
done

# Dovresti vedere rate limiting dopo il limite configurato
```

---

## 📊 Coverage Target

- **Target**: 80%+ coverage per plugin system
- **Attuale**: ~75% (con nuovi test aggiunti)

---

## 🐛 Troubleshooting

### Plugin Discovery Non Funziona

1. Verifica che la directory `plugins/` esista
2. Controlla i log per errori di import
3. Verifica che i plugin seguano la struttura corretta

### Admin Authentication Fallisce

1. Verifica che `ADMIN_API_KEY` sia settato nell'environment
2. Controlla che l'header `x-admin-key` sia inviato correttamente
3. Verifica i log per dettagli sull'errore

### Rate Limiting Non Funziona

1. Verifica che Redis sia disponibile (se configurato)
2. Controlla i log per errori Redis
3. Verifica che il fallback a memory funzioni

---

## 📝 Note

- I test usano mock per evitare dipendenze esterne
- Redis è opzionale - i test verificano il fallback
- Admin authentication supporta sia API key che JWT

---

**Ultimo aggiornamento**: 2025-12-07



























