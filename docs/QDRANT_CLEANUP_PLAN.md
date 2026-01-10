# 🗑️ QDRANT CLEANUP PLAN - Rimozione Collezioni Obsolete

**Data:** 2026-01-10  
**Status:** ✅ Pronto per Esecuzione

---

## 📋 COLLEZIONI DA ELIMINARE

### 1. `collective_memories` - **0 documenti**

**Motivo:** Spostata completamente a PostgreSQL  
**Stato Attuale:** Vuota, mai popolata  
**Tabella PostgreSQL:** `collective_memories` (già esistente da migration_018)

**Azioni Richieste:**
- ✅ Eliminare collezione Qdrant
- ⚠️ Rimuovere codice Qdrant da `CollectiveMemoryService`
- ✅ Verificare che sistema usi solo PostgreSQL

**Note:**
- Il servizio `CollectiveMemoryService` ha già tabella PostgreSQL funzionante
- Qdrant era usato solo per semantic search (non necessario se vuota)
- Sistema può funzionare solo con PostgreSQL per ora

---

### 2. `tax_genius` - **332 documenti**

**Motivo:** Obsoleta - duplicato identico di `tax_genius_hybrid`  
**Stato Attuale:** 332 documenti identici a hybrid  
**Sostituto:** `tax_genius_hybrid` (332 documenti)

**Azioni Richieste:**
- ✅ Verificare che `tax_genius_hybrid` sia completa
- ✅ Eliminare `tax_genius` standard
- ✅ Aggiornare codice che fa riferimento a `tax_genius` → `tax_genius_hybrid`

**Note:**
- Formato hybrid è migliore (BM25 + Dense)
- Nessuna perdita di dati (identici)

---

### 3. `training_conversations` - **2,898 documenti**

**Motivo:** Obsoleta - sostituita da `training_conversations_hybrid`  
**Stato Attuale:** 2,898 documenti formato standard  
**Sostituto:** `training_conversations_hybrid` (3,525 documenti, più completa)

**Azioni Richieste:**
- ✅ Verificare che `training_conversations_hybrid` contenga tutti i dati necessari
- ✅ Eliminare `training_conversations` standard
- ✅ Aggiornare codice che fa riferimento a collezione standard

**Note:**
- Hybrid ha più documenti (3,525 vs 2,898)
- Formato hybrid è migliore (BM25 + Dense)
- Possibile perdita di 627 documenti se non migrati (verificare)

---

### 4. `bali_zero_pricing_hybrid` - **0 documenti**

**Motivo:** Obsoleta - vuota, mai popolata  
**Stato Attuale:** Vuota  
**Sostituto:** `bali_zero_pricing` (70 documenti, attiva)

**Azioni Richieste:**
- ✅ Eliminare collezione vuota
- ✅ Nessun aggiornamento codice necessario (non usata)

**Note:**
- Collezione mai utilizzata
- Nessun impatto sul sistema

---

## 🔧 MODIFICHE CODICE RICHIESTE

### 1. CollectiveMemoryService - Rimuovere Qdrant

**File:** `apps/backend-rag/backend/services/memory/collective_memory_service.py`

**Modifiche:**
- Rimuovere `QDRANT_COLLECTION` constant
- Rimuovere `_get_qdrant()` method
- Rimuovere `_sync_to_qdrant()` method
- Rimuovere chiamate a `_sync_to_qdrant()` in `add_contribution()`
- Rimuovere `qdrant_client` parameter da `__init__`

**Note:**
- Sistema funziona già solo con PostgreSQL
- Qdrant era usato solo per semantic search (non critico se vuota)

---

### 2. Query Router - Aggiornare Riferimenti

**File:** `apps/backend-rag/backend/services/routing/query_router.py`

**Verificare:**
- Nessun riferimento a `tax_genius` (solo `tax_genius_hybrid`)
- Nessun riferimento a `training_conversations` (solo `training_conversations_hybrid`)

**Status:** ✅ Già verificato - nessun riferimento trovato

---

## 📊 IMPATTO ANALISI

### Collezioni da Eliminare

| Collezione | Documenti | Impatto | Rischio |
|------------|-----------|---------|---------|
| `collective_memories` | 0 | Nessuno | ✅ Basso |
| `tax_genius` | 332 | Nessuno (duplicato) | ✅ Basso |
| `training_conversations` | 2,898 | Possibile perdita 627 docs | ⚠️ Medio |
| `bali_zero_pricing_hybrid` | 0 | Nessuno | ✅ Basso |

**Totale documenti da eliminare:** 3,230 documenti  
**Rischio complessivo:** ⚠️ Medio (verificare migrazione training_conversations)

---

## ✅ CHECKLIST PRE-ELIMINAZIONE

- [ ] Verificare che `tax_genius_hybrid` contenga tutti i 332 documenti
- [ ] Verificare che `training_conversations_hybrid` contenga tutti i documenti necessari
- [ ] Backup collezioni (opzionale ma consigliato)
- [ ] Rimuovere codice Qdrant da `CollectiveMemoryService`
- [ ] Testare sistema senza collezioni obsolete
- [ ] Eseguire cleanup script

---

## 🚀 ESECUZIONE

### Step 1: Rimuovere Codice Qdrant da CollectiveMemoryService

```python
# Rimuovere:
- QDRANT_COLLECTION constant
- _get_qdrant() method
- _sync_to_qdrant() method
- Chiamate a _sync_to_qdrant()
```

### Step 2: Eseguire Cleanup Script

```bash
python scripts/cleanup_qdrant_collections.py
```

### Step 3: Verificare

- Verificare che collezioni siano eliminate
- Verificare che sistema funzioni correttamente
- Aggiornare documentazione

---

## 📝 DOCUMENTAZIONE DA AGGIORNARE

1. `docs/QDRANT_11_COLLECTIONS_COMPLETE.md` - Rimuovere collezioni eliminate
2. `docs/AI_ONBOARDING.md` - Aggiornare lista collezioni
3. `docs/QDRANT_COLLECTIONS.md` - Aggiornare documentazione

---

**Prossimi Step:** Eseguire modifiche codice e cleanup
