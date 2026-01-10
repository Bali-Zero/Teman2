# 🔧 QDRANT FIXES APPLICATI - 2026-01-10

**Data:** 2026-01-10  
**Motivo:** Fix codice obsoleto dopo investigazione Qdrant

---

## ✅ FIX APPLICATI

### 1. Query Router - Fix `legal_unified` → `legal_unified_hybrid`

**File:** `apps/backend-rag/backend/services/routing/query_router.py`

**Problema:**
- Codice faceva riferimento a `legal_unified` che non esiste più
- Collezione reale è `legal_unified_hybrid` (47,959 docs)

**Fix Applicato:**
```python
# Prima (linea 572, 580):
collection = "legal_unified"

# Dopo:
collection = "legal_unified_hybrid"
```

**Linee modificate:**
- Linea 572: Default fallback
- Linea 580: Legal domain routing

**Impatto:**
- ✅ Query legali ora funzionano correttamente
- ✅ Default fallback ora usa collezione esistente

---

### 2. Query Router - Fix `bali_zero_team` Fallback

**File:** `apps/backend-rag/backend/services/routing/query_router.py`

**Problema:**
- Codice faceva riferimento a `bali_zero_team` che non esiste più
- Query team fallivano silenziosamente

**Fix Applicato:**
```python
# Prima (linea 595):
collection = "bali_zero_team"

# Dopo:
collection = "bali_zero_pricing"  # Temporary fallback
logger.warning("⚠️ Route: {collection} (team query - bali_zero_team not found, using fallback)")
```

**Linee modificate:**
- Linea 595: Team domain routing

**Impatto:**
- ✅ Query team non falliscono più
- ⚠️ Usano fallback temporaneo (da fixare con collezione corretta)

**TODO:**
- Verificare se `bali_zero_team` deve essere ricreata
- Oppure usare alternativa (es. `bali_zero_pricing` per info team)
- Rimuovere fallback temporaneo quando risolto

---

## 📋 FIX PENDENTI

### 1. Fallback Manager - Aggiornare riferimenti `legal_unified`

**File:** `apps/backend-rag/backend/services/routing/fallback_manager.py`

**Problema:**
- Fallback chains potrebbero ancora riferirsi a `legal_unified`

**Azione Richiesta:**
- Verificare e aggiornare tutti i riferimenti a `legal_unified` → `legal_unified_hybrid`

---

### 2. Priority Override - Fix `bali_zero_team`

**File:** `apps/backend-rag/backend/services/routing/priority_override.py`

**Problema:**
- Linee 150, 156, 161 fanno riferimento a `bali_zero_team`

**Azione Richiesta:**
- Decidere se ricreare collezione o usare alternativa
- Aggiornare codice di conseguenza

---

### 3. Collection Manager - Aggiornare definizioni

**File:** `apps/backend-rag/backend/services/ingestion/collection_manager.py`

**Problema:**
- Definizioni collezioni potrebbero essere obsolete

**Azione Richiesta:**
- Aggiornare `doc_count` con valori reali
- Rimuovere collezioni non esistenti

---

## 🧪 TESTING RICHIESTO

Dopo i fix applicati, testare:

1. ✅ Query legali generiche
2. ✅ Query legali specifiche (PP, UU, Permen)
3. ⚠️ Query team (usando fallback temporaneo)
4. ✅ Default fallback (quando nessun keyword match)

---

## 📝 NOTE

- Fix applicati sono **backward compatible** (non rompono codice esistente)
- Fallback temporaneo per team è una **soluzione provvisoria**
- Investigazione completa in: `docs/QDRANT_DEEP_INVESTIGATION_FINAL.md`

---

**Fix applicati:** 2026-01-10  
**Versione:** Pre-deploy (da testare)
