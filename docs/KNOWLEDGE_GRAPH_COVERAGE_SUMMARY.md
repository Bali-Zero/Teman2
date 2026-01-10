# 📊 KNOWLEDGE GRAPH COVERAGE - Summary

**Data:** 2026-01-10

---

## ❓ DOMANDE FREQUENTI

### Q1: Cosa significa "Build automatico ogni 4 ore"?

**Risposta:**
Il sistema esegue automaticamente ogni 4 ore, ma attualmente **solo verifica/inizializza lo schema database**. 

**NON estrae entità/relazioni automaticamente** - questa funzionalità non è implementata nel task schedulato.

**Codice attuale:**
```python
async def run_knowledge_graph_builder():
    await graph_builder.init_graph_schema()  # Solo questo!
    # build_graph_from_all_conversations() NON chiamato
```

---

### Q2: Il KB copre tutte le connessioni delle collections (58k docs)?

**Risposta:**
**NO** - Il knowledge graph **NON copre automaticamente** le 58k documenti Qdrant.

**Stato attuale:**
- ❌ Build automatico: Solo verifica schema (non estrae)
- ❌ Conversazioni: Non processate automaticamente
- ❌ Collezioni Qdrant: Non processate automaticamente
- ⚠️ **Richiede build manuale** per qualsiasi estrazione

**Per coprire le 58k docs serve:**
1. Eseguire build manuale con `KGPipeline.run_from_qdrant()`
2. Processare collezioni principali manualmente
3. Considerare costo LLM extraction

---

## 🔧 COME FUNZIONA REALMENTE

### Build Automatico (ogni 4h)

**Cosa fa:**
- ✅ Verifica/inizializza schema `kg_nodes` e `kg_edges`
- ❌ **NON** estrae entità/relazioni
- ❌ **NON** processa conversazioni
- ❌ **NON** processa Qdrant collections

**Perché:**
- Implementazione incompleta nel scheduler
- Estrazione richiede LLM (costo)
- Processo manuale più controllato

---

### Build Manuale Disponibile

**Due approcci:**

#### 1. Da Conversazioni
```python
builder = KnowledgeGraphBuilder(db_pool=db_pool, ai_client=ai_client)
await builder.build_graph_from_all_conversations(days_back=30)
```

#### 2. Da Collezioni Qdrant
```python
pipeline = KGPipeline()
await pipeline.run_from_qdrant(
    collection_name="legal_unified_hybrid",
    limit=None,  # Tutti i documenti
    persist=True
)
```

**Nota:** `build_graph_from_collection()` processa solo `limit=100` documenti per default, non tutti!

---

## 📊 COVERAGE STIMATA

### Se Build Manuale NON Eseguito
- **Nodi:** 0-100 (solo se schema inizializzato)
- **Edge:** 0-200
- **Source:** Nessuno

### Se Build Manuale Conversazioni Eseguito
- **Nodi:** ~100-1000 (da conversazioni)
- **Edge:** ~200-2000
- **Source:** `conversations` table

### Se Build Manuale Qdrant Eseguito
- **Nodi:** ~5000-50000 (da Qdrant)
- **Edge:** ~10000-100000
- **Source:** Collezioni Qdrant

**Per coprire tutte le 58k docs:**
- Processare tutte le collezioni principali
- Costo LLM: ~$50-500 (dipende da modello)
- Tempo: ~2-20 ore (dipende da batch size)

---

## ✅ RACCOMANDAZIONI

### Per Attivare Build Automatico Completo

**Modificare scheduler:**
```python
async def run_knowledge_graph_builder():
    await graph_builder.init_graph_schema()
    # AGGIUNGERE:
    await graph_builder.build_graph_from_all_conversations(days_back=7)
    # O processare Qdrant (più costoso)
```

### Per Coprire Tutte le 58k Docs

**Eseguire build manuale completo:**
```python
collections = [
    "legal_unified_hybrid",      # 47,959 docs
    "kbli_unified",              # 2,818 docs  
    "tax_genius_hybrid",         # 332 docs
    "visa_oracle",               # 82 docs
]

pipeline = KGPipeline()
for collection in collections:
    await pipeline.run_from_qdrant(
        collection_name=collection,
        limit=None,
        persist=True
    )
```

---

## 🎯 CONCLUSIONE

**Build automatico ogni 4 ore:**
- ✅ Esegue automaticamente
- ⚠️ Solo verifica schema (non estrae)
- ❌ Non copre KB automaticamente

**Coverage 58k docs:**
- ❌ **NON coperto automaticamente**
- ⚠️ **Richiede build manuale**
- 💰 **Costo LLM da considerare**

---

**Documentazione creata:** 2026-01-10
