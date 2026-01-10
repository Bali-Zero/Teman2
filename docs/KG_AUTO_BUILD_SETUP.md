# 🚀 KNOWLEDGE GRAPH AUTO-BUILD - Setup Guide

**Data:** 2026-01-10  
**Status:** ✅ Implementato - Pronto per Deploy

---

## 📋 QUICK START

### 1. Configurare API Key

**Su Fly.io (Produzione):**
```bash
fly secrets set GOOGLE_API_KEY=AIzaSyCr-wmXSDvRhAYqsV0XME227EX_uwXGWZI -a nuzantara-rag
```

**Localmente (.env):**
```bash
GOOGLE_API_KEY=AIzaSyCr-wmXSDvRhAYqsV0XME227EX_uwXGWZI
```

### 2. Verificare Configurazione

**Variabili Richieste:**
- ✅ `GOOGLE_API_KEY` - Google AI Studio API key
- ✅ `QDRANT_URL` - Qdrant instance URL
- ✅ `QDRANT_API_KEY` - Qdrant API key
- ✅ `DATABASE_URL` - PostgreSQL connection string

**Verifica:**
```bash
# Backend logs dovrebbero mostrare:
✅ Gemini client initialized with Google AI Studio
✅ Knowledge Graph Builder Agent registered (24h interval - incremental)
```

---

## 🔧 CONFIGURAZIONE

### Collezioni Processate

**Alta Priorità (ogni 24h):**
- `legal_unified_hybrid` (47,959 docs)
- `kbli_unified` (2,818 docs)
- `tax_genius_hybrid` (332 docs)
- `visa_oracle` (82 docs)
- `balizero_news_history` (6 docs)

**Modificabile in:**
`apps/backend-rag/backend/services/knowledge_graph/incremental_builder.py`
```python
HIGH_PRIORITY_COLLECTIONS = [
    "legal_unified_hybrid",
    "kbli_unified",
    # ... aggiungere/rimuovere collezioni
]
```

---

## 📊 MONITORING

### Logs da Monitorare

**Successo:**
```
🕸️ Processing collection: legal_unified_hybrid
Found 45,000 already processed chunks
  legal_unified_hybrid: 2,959 unprocessed / 47,959 total
✅ legal_unified_hybrid: 2,959 chunks, 1,234 entities, 567 relationships
🕸️ KG Incremental Extraction Complete: 5/5 collections, 5,000 chunks
```

**Errori:**
```
❌ Error processing legal_unified_hybrid (attempt 1/3): Connection timeout
⏳ Retrying legal_unified_hybrid in 2s...
```

### Statistiche

**Endpoint (se disponibile):**
```bash
GET /api/agents/knowledge-graph/stats
```

**Query Database:**
```sql
-- Totale nodi/edge
SELECT COUNT(*) FROM kg_nodes;
SELECT COUNT(*) FROM kg_edges;

-- Chunk processati
SELECT COUNT(DISTINCT unnest(source_chunk_ids)) 
FROM kg_nodes 
WHERE source_chunk_ids IS NOT NULL;

-- Ultimi nodi aggiunti
SELECT name, entity_type, created_at 
FROM kg_nodes 
ORDER BY created_at DESC 
LIMIT 10;
```

---

## ✅ VERIFICA FUNZIONAMENTO

### Test Manuale

**Eseguire build manuale:**
```python
from backend.services.knowledge_graph.incremental_builder import KGIncrementalBuilder

builder = KGIncrementalBuilder(db_pool=db_pool)
stats = await builder.run_incremental_extraction()
print(stats)
```

**Verificare risultati:**
- Controllare `kg_nodes` e `kg_edges` in PostgreSQL
- Verificare `source_chunk_ids` popolati
- Controllare logs per errori

---

## 🎯 CONCLUSIONE

**Setup Completato:** ✅

- ✅ Codice implementato
- ✅ Scheduler configurato (24h)
- ✅ Error handling robusto
- ✅ Google AI Studio supportato

**Prossimo Step:** Configurare `GOOGLE_API_KEY` e deployare

---

**Documentazione creata:** 2026-01-10
