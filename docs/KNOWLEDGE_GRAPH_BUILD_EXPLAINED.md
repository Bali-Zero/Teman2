# 🕸️ KNOWLEDGE GRAPH BUILD - Spiegazione Completa

**Data:** 2026-01-10  
**Domande:** 
1. Cosa significa "Build automatico ogni 4 ore"?
2. Il KB copre tutte le connessioni delle collections (58k docs)?

---

## 📋 RISPOSTA 1: Build Automatico Ogni 4 Ore

### Come Funziona

**Sistema:** `AutonomousScheduler`  
**File:** `apps/backend-rag/backend/services/misc/autonomous_scheduler.py`

**Configurazione:**
```python
# Linea 548-569
scheduler.register_task(
    name="knowledge_graph_builder",
    task_func=run_knowledge_graph_builder,
    interval_seconds=14400,  # 4 ore = 14400 secondi
    enabled=True,
)
```

### Cosa Fa il Build Automatico

**Agent:** `KnowledgeGraphBuilder` (da `backend/agents/agents/knowledge_graph_builder.py`)

**Processo:**
1. **Estrae entità e relazioni dalle conversazioni** (non dalle collezioni Qdrant!)
2. **Analizza conversazioni degli ultimi N giorni** (configurabile)
3. **Costruisce/aggiorna knowledge graph** in PostgreSQL
4. **Non processa collezioni Qdrant** - solo conversazioni utenti

**Metodo Chiamato:**
```python
# ATTENZIONE: Attualmente solo inizializza schema!
await graph_builder.init_graph_schema()
# TODO: build_graph_from_all_conversations() non chiamato automaticamente
```

**Nota Importante:** 
- ⚠️ Il build automatico attualmente **solo inizializza lo schema**
- ⚠️ **NON** processa conversazioni automaticamente (non implementato)
- ⚠️ **NON** processa le 58k documenti Qdrant
- ✅ Schema verificato ogni 4 ore

---

## 📊 RISPOSTA 2: Coverage Collezioni Qdrant (58k docs)

### Stato Attuale

**Collezioni Qdrant:** 54,792 documenti (dopo cleanup)

**Knowledge Graph Coverage:**
- ❓ **NON copre automaticamente** tutte le collezioni Qdrant
- ✅ **Copre conversazioni** utenti (fonte dinamica)
- ⚠️ **Processo manuale** necessario per collezioni Qdrant

### Due Approcci Diversi

#### 1. Build Automatico (ogni 4h) - Conversazioni

**Cosa fa:**
- Analizza conversazioni PostgreSQL (`conversations` table)
- Estrae entità/relazioni menzionate nelle chat
- Aggiorna knowledge graph

**Coverage:**
- ✅ Conversazioni utenti (dinamico)
- ❌ Collezioni Qdrant (non processate)

**Vantaggi:**
- Aggiornamento automatico
- Entità reali menzionate dagli utenti
- Relazioni validate dall'uso

**Limitazioni:**
- Non copre documenti Qdrant
- Dipende da conversazioni attive

---

#### 2. Build Manuale - Collezioni Qdrant

**Pipeline:** `KGPipeline`  
**File:** `apps/backend-rag/backend/services/knowledge_graph/pipeline.py`

**Metodo:**
```python
pipeline = KGPipeline(config=PipelineConfig())
stats = await pipeline.run_from_qdrant(
    collection_name="legal_unified_hybrid",
    limit=None,  # Tutti i documenti
    persist=True
)
```

**Cosa fa:**
- Processa chunk da collezione Qdrant
- Estrae entità/relazioni con LLM
- Persiste in PostgreSQL

**Coverage:**
- ✅ Collezioni Qdrant (tutte o selezionate)
- ❌ Non automatico (richiede trigger manuale)

**Endpoint Disponibile:**
```bash
POST /api/agents/knowledge-graph/extract-sample
GET /api/knowledge-graph/extract-sample?collection=legal_unified_hybrid&sample_size=50
```

---

## 🔍 ANALISI COVERAGE REALE

### Domanda: Quanti documenti Qdrant sono nel KG?

**Per rispondere, devo verificare:**
1. Quanti nodi/edge hanno `source_collection` da Qdrant?
2. Quali collezioni sono state processate?
3. Quanti chunk sono stati analizzati?

**Script per verificare:**
```bash
python scripts/analyze_knowledge_graph.py
# Richiede DATABASE_URL configurato
```

**Query SQL per verificare:**
```sql
-- Nodi da collezioni Qdrant
SELECT source_collection, COUNT(*) 
FROM kg_nodes 
WHERE source_collection IS NOT NULL 
GROUP BY source_collection;

-- Edge da collezioni Qdrant
SELECT source_collection, COUNT(*) 
FROM kg_edges 
WHERE source_collection IS NOT NULL 
GROUP BY source_collection;

-- Totale nodi/edge
SELECT COUNT(*) FROM kg_nodes;
SELECT COUNT(*) FROM kg_edges;
```

---

## ⚠️ LIMITAZIONI ATTUALI

### Build Automatico

**Cosa copre:**
- ✅ Conversazioni utenti (dinamico)
- ✅ Entità menzionate nelle chat
- ✅ Relazioni validate dall'uso

**Cosa NON copre:**
- ❌ Documenti Qdrant (58k docs)
- ❌ Collezioni knowledge base
- ❌ Documenti legali/fiscali/visa

### Build Manuale (Qdrant)

**Cosa copre:**
- ✅ Collezioni Qdrant (se eseguito)
- ✅ Documenti legali/fiscali/visa
- ✅ Knowledge base completa

**Cosa NON copre:**
- ❌ Non automatico
- ❌ Richiede trigger manuale
- ❌ Costoso (LLM extraction)

---

## 🎯 RACCOMANDAZIONI

### Per Coprire Tutte le 58k Docs

**Opzione 1: Build Manuale Completo**
```python
# Processare tutte le collezioni principali
collections = [
    "legal_unified_hybrid",      # 47,959 docs
    "kbli_unified",              # 2,818 docs
    "tax_genius_hybrid",         # 332 docs
    "visa_oracle",               # 82 docs
    "training_conversations_hybrid",  # 3,525 docs
]

pipeline = KGPipeline()
for collection in collections:
    await pipeline.run_from_qdrant(
        collection_name=collection,
        limit=None,  # Tutti i documenti
        persist=True
    )
```

**Opzione 2: Build Incrementale**
- Processare solo documenti nuovi/aggiornati
- Usare `source_chunk_ids` per tracking
- Evitare duplicati

**Opzione 3: Build Automatico Esteso**
- Modificare `AutonomousScheduler` per includere Qdrant
- Processare collezioni Qdrant ogni 4h (o più raramente)
- Costo LLM da considerare

---

## 📊 STATO ATTUALE STIMATO

### Build Automatico (ogni 4h) - STATO ATTUALE

**Coverage:**
- Conversazioni: ⚠️ **NON processate** (non implementato nel scheduler)
- Qdrant Collections: ❌ Non processate automaticamente
- Schema: ✅ Verificato/inizializzato

**Stima:**
- Nodi: ~0-100 (solo se build manuale eseguito)
- Edge: ~0-200 (solo se build manuale eseguito)
- Source: Build manuale o conversazioni (se processate manualmente)

**Nota:** Il task automatico attualmente **solo verifica lo schema**, non estrae entità/relazioni!

### Build Manuale (se eseguito)

**Coverage:**
- Qdrant Collections: ✅ Se eseguito manualmente
- Documenti processati: Dipende da esecuzione

**Stima (se eseguito):**
- Nodi: ~5000-50000 (da Qdrant)
- Edge: ~10000-100000 (da Qdrant)
- Source: Collezioni Qdrant

---

## ✅ CONCLUSIONE

### Build Automatico Ogni 4 Ore - REALTÀ

**Significa:**
- ✅ Sistema esegue automaticamente ogni 4 ore
- ✅ **Solo verifica/inizializza schema** database
- ⚠️ **NON estrae entità/relazioni** automaticamente (non implementato)

**Non significa:**
- ❌ Non analizza conversazioni automaticamente
- ❌ Non processa collezioni Qdrant automaticamente
- ❌ Non copre tutti i 58k documenti
- ❌ Non è un build completo del KB

**Codice Attuale:**
```python
async def run_knowledge_graph_builder():
    await graph_builder.init_graph_schema()  # Solo schema!
    # TODO: build_graph_from_all_conversations() non chiamato
```

### Coverage Collezioni (58k docs)

**Risposta:**
- ❌ **NON copre automaticamente** tutte le collezioni Qdrant
- ❌ **NON copre conversazioni** automaticamente (non implementato)
- ⚠️ **Richiede build manuale** per qualsiasi estrazione
- ⚠️ **Build automatico** attualmente solo verifica schema

**Per coprire tutto serve:**
1. **Build manuale conversazioni** (se necessario)
2. **Build manuale Qdrant** (per 58k docs)
3. **Modificare scheduler** per includere estrazione automatica

**Per coprire tutto:**
1. Eseguire build manuale con `KGPipeline.run_from_qdrant()`
2. Processare collezioni principali
3. Considerare costo LLM extraction

---

**Documentazione creata:** 2026-01-10  
**Prossimo step:** Verificare coverage reale con script analisi
