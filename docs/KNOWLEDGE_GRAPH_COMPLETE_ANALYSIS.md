# 🕸️ KNOWLEDGE GRAPH - Analisi Completa

**Data Analisi:** 2026-01-10  
**Sistema:** Conscious GraphRAG v6.5  
**Database:** PostgreSQL (kg_nodes, kg_edges)

---

## 📊 OVERVIEW

Il Knowledge Graph è un sistema di rappresentazione strutturata delle relazioni tra entità business estratte dalle collezioni Qdrant. Utilizza PostgreSQL per la persistenza e fornisce query strutturate per trovare connessioni tra entità.

---

## 🏗️ ARCHITETTURA

### Database Schema

**Tabelle:**
- `kg_nodes` - Entità del grafo
- `kg_edges` - Relazioni tra entità

**Migration:** `migration_028_knowledge_graph_schema.py` (2025-12-29)

### Struttura kg_nodes

```sql
CREATE TABLE kg_nodes (
    entity_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    properties JSONB DEFAULT '{}'::jsonb,
    confidence FLOAT DEFAULT 1.0,
    source_collection TEXT,
    source_chunk_ids TEXT[] DEFAULT '{}',  -- Aggiunto in migration_029
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Indici:**
- `idx_kg_nodes_type` - Per query per tipo
- `idx_kg_nodes_name` - Per ricerca per nome
- `idx_kg_nodes_chunks` - GIN index per source_chunk_ids

### Struttura kg_edges

```sql
CREATE TABLE kg_edges (
    relationship_id TEXT PRIMARY KEY,
    source_entity_id TEXT NOT NULL REFERENCES kg_nodes(entity_id) ON DELETE CASCADE,
    target_entity_id TEXT NOT NULL REFERENCES kg_nodes(entity_id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,
    properties JSONB DEFAULT '{}'::jsonb,
    confidence FLOAT DEFAULT 1.0,
    source_collection TEXT,
    source_chunk_ids TEXT[] DEFAULT '{}',  -- Aggiunto in migration_029
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**Indici:**
- `idx_kg_edges_source` - Per query da source
- `idx_kg_edges_target` - Per query da target
- `idx_kg_edges_type` - Per query per tipo relazione
- `idx_kg_edges_chunks` - GIN index per source_chunk_ids

---

## 📋 TIPI DI ENTITÀ

### EntityType Enum

| Tipo | Descrizione | Esempi |
|------|-------------|--------|
| `kbli_code` | Codici KBLI | KBLI 56101, KBLI 47111 |
| `legal_entity` | Entità legali | PT PMA, CV, PT Lokal |
| `visa_type` | Tipi di visto | C22B, Investor KITAS, Work Permit |
| `tax_type` | Tipi fiscali | PPh 21, PPN/VAT, NPWP |
| `permit` | Permessi | NIB, SIUP, IMB |
| `document` | Documenti | Akta Pendirian, SK Kemenkumham |
| `process` | Processi | Company Setup, Visa Application |
| `regulation` | Regolamenti | PP 28/2025, UU Cipta Kerja |
| `location` | Località | Bali, Jakarta, Indonesia |
| `service` | Servizi | Legal Consultation, Tax Filing |

---

## 🔗 TIPI DI RELAZIONI

### RelationType Enum

| Tipo | Descrizione | Esempi |
|------|-------------|--------|
| `requires` | Prerequisito | PT PMA requires NIB |
| `related_to` | Relazione generica | KITAS related_to Work Permit |
| `part_of` | Parte di | NIB part_of Company Setup |
| `provides` | Fornisce | PT PMA provides Limited Liability |
| `costs` | Costo | Visa Application costs 2,500,000 IDR |
| `duration` | Durata | Process takes 30 days |
| `prerequisite` | Prerequisito | NIB prerequisite for NPWP |
| `tax_obligation` | Obbligo fiscale | Restaurant tax_obligation PPh 23 |
| `legal_requirement` | Requisito legale | PT PMA legal_requirement Akta |
| `location_restriction` | Restrizione geografica | Business location_restriction Zoning |

---

## 🔧 COMPONENTI PRINCIPALI

### 1. KnowledgeGraphBuilder

**File:** `apps/backend-rag/backend/services/autonomous_agents/knowledge_graph_builder.py`

**Responsabilità:**
- Estrazione entità da documenti Qdrant
- Inferenza relazioni usando pattern regex + LLM
- Persistenza in PostgreSQL
- Query del grafo (traversal, subgraph extraction)

**Pattern di Estrazione:**
- Regex patterns per entità comuni (KBLI, Visa, Tax)
- LLM semantic extraction per entità complesse
- Hybrid approach (regex + LLM)

**Metodi Principali:**
- `add_entity()` - Aggiunge entità al grafo
- `add_relationship()` - Aggiunge relazione
- `build_graph_from_collection()` - Costruisce grafo da collezione Qdrant
- `query_graph()` - Query del grafo (BFS traversal)
- `_refresh_from_db()` - Sincronizza memoria con DB

---

### 2. KGPipeline

**File:** `apps/backend-rag/backend/services/knowledge_graph/pipeline.py`

**Responsabilità:**
- Pipeline end-to-end per estrazione KG
- Orchestrazione: chunk retrieval → extraction → coreference → persistence
- Batch processing con controllo concorrenza

**Configurazione:**
- Model: Claude Sonnet 4 (default) o Gemini
- Two-stage extraction: opzionale (più accurato ma più lento)
- Coreference resolution: LLM-based o heuristics
- Batch size: 10 chunks per batch
- Max concurrent: 5 batch paralleli

**Metodi Principali:**
- `run_from_qdrant()` - Esegue pipeline da collezione Qdrant
- `extract_from_chunks()` - Estrae entità/relazioni da chunk
- `persist_results()` - Persiste risultati in PostgreSQL
- `get_stats()` - Statistiche pipeline

---

### 3. KnowledgeGraphTool

**File:** `apps/backend-rag/backend/services/tools/knowledge_graph_tool.py`

**Responsabilità:**
- Tool per Agentic RAG per query del knowledge graph
- Formatta risultati per consumo LLM
- Integrazione con sistema ReAct

**Parametri:**
- `entity` - Nome entità da cercare (required)
- `depth` - Profondità traversal (1-2, default 1)
- `relationship_type` - Filtro tipo relazione (optional)

**Esempio Uso:**
```python
# Query: "What is required for PT PMA?"
result = await kg_tool.execute(
    entity="PT PMA",
    depth=1,
    relationship_type="requires"
)
```

---

### 4. CoreferenceResolver

**File:** `apps/backend-rag/backend/services/knowledge_graph/coreference.py`

**Responsabilità:**
- Risoluzione coreferenze (es. "PT PMA" = "Perseroan Terbatas Penanaman Modal Asing")
- Deduplicazione entità cross-chunk
- Cache per performance

**Strategie:**
- LLM-based coreference (Claude)
- Heuristics (fuzzy matching, acronyms)
- Hybrid (LLM + heuristics)

---

## 📊 STATISTICHE E METRICHE

### Metriche Disponibili

**Per Nodi:**
- Totale nodi
- Distribuzione per tipo
- Distribuzione per collezione sorgente
- Confidence scores (avg, min, max)
- Numero connessioni per nodo

**Per Edge:**
- Totale edge
- Distribuzione per tipo relazione
- Distribuzione per collezione sorgente
- Confidence scores
- Densità grafo (edge/nodo)

**Per Source Chunks:**
- Nodi con chunk IDs
- Edge con chunk IDs
- Media chunk per nodo/edge
- Provenance tracking completo

---

## 🔍 QUERY E UTILIZZO

### Query Graph (BFS Traversal)

```python
result = await kg_builder.query_graph(
    entity_name="PT PMA",
    max_depth=2  # 1 = direct, 2 = extended
)
```

**Risultato:**
```json
{
    "found": true,
    "query": "PT PMA",
    "start_entity": {
        "entity_id": "pt_pma",
        "name": "PT PMA",
        "entity_type": "legal_entity",
        "description": "..."
    },
    "entities": [...],
    "relationships": [...],
    "total_entities": 15,
    "total_relationships": 23
}
```

### Esempio Output KnowledgeGraphTool

```
Found subgraph for 'PT PMA' (15 nodes, 23 edges):

[FOCUS] PT PMA (legal_entity)
  Description: Perseroan Terbatas Penanaman Modal Asing...

Connections:
  - [This] --REQUIRES--> NIB
  - [This] --REQUIRES--> NPWP
  - [This] --TAX_OBLIGATION--> PPh 23
  - [This] --TAX_OBLIGATION--> PPN
  - [This] --LEGAL_REQUIREMENT--> Akta Pendirian
  ...
```

---

## 🚀 PIPELINE DI ESTRAZIONE

### Workflow Completo

1. **Chunk Retrieval**
   - Recupera chunk da Qdrant collection
   - Batch processing (10 chunk per batch)
   - Max concurrent: 5 batch

2. **Entity/Relation Extraction**
   - LLM-based extraction (Claude/Gemini)
   - Pattern matching (regex) per entità comuni
   - Two-stage extraction (opzionale)

3. **Coreference Resolution**
   - Risoluzione coreferenze cross-chunk
   - Deduplicazione entità
   - Cache per performance

4. **Persistence**
   - Upsert nodi in `kg_nodes`
   - Upsert edge in `kg_edges`
   - Merge properties e source_chunk_ids
   - Update confidence scores

---

## 📚 INTEGRAZIONE CON SISTEMA

### Agentic RAG Integration

**Tool Disponibile:**
- `KnowledgeGraphTool` - Query strutturate del grafo
- Usato dopo `VectorSearchTool` per approfondire relazioni

**Workflow Tipico:**
1. User query → VectorSearchTool (trova documenti rilevanti)
2. KnowledgeGraphTool (trova relazioni tra entità menzionate)
3. LLM synthesis (combina informazioni)

### Memory Orchestrator Integration

**File:** `apps/backend-rag/backend/services/memory/orchestrator.py`

**Utilizzo:**
- `KnowledgeGraphRepository` per query entità correlate
- Aggiunge contesto KG al context utente
- Non-critico (fallback se non disponibile)

---

## 🔄 MANUTENZIONE E AGGIORNAMENTO

### Build Automatico

**Agent:** `KnowledgeGraphBuilderAgent`
- Esegue ogni 4 ore (configurabile)
- Analizza collezioni Qdrant aggiornate
- Estrae nuove entità/relazioni

### Build Manuale

**Endpoint:** `/api/agents/knowledge-graph/build`
- Trigger manuale build
- Parametri: `days_back`, `init_schema`
- Background task execution

---

## 📈 BEST PRACTICES

### Estrazione

1. **Usa Two-Stage Extraction** per documenti complessi
2. **Coreference Resolution** per qualità migliore
3. **Batch Size** ottimale: 10-20 chunk
4. **Confidence Threshold**: 0.6+ per produzione

### Query

1. **Depth Limit**: Max 2 per performance
2. **Filter by Type**: Usa `relationship_type` quando possibile
3. **Cache Results**: Cache query frequenti
4. **Combine with Vector Search**: KG dopo vector search

### Manutenzione

1. **Regular Builds**: Esegui build ogni 4-6 ore
2. **Monitor Confidence**: Rimuovi nodi/edge con confidence < 0.3
3. **Verify Source Chunks**: Mantieni provenance tracking
4. **Cleanup Duplicates**: Deduplica entità periodicamente

---

## ⚠️ LIMITAZIONI E NOTE

### Limitazioni Attuali

1. **Depth Limit**: Max 2 hop per performance
2. **LLM Cost**: Estrazione LLM può essere costosa
3. **Coreference**: Non perfetta per nomi complessi
4. **Scalability**: Query complesse possono essere lente

### Miglioramenti Futuri

1. **Graph Embeddings**: Usa embeddings per similarity search
2. **Incremental Updates**: Update incrementali invece di rebuild completo
3. **Graph Analytics**: Metriche avanzate (centrality, communities)
4. **Visualization**: UI per visualizzare grafo

---

## 📝 ESEMPI D'USO

### Esempio 1: Query Prerequisiti

```python
# Query: "What is required for opening a restaurant?"
result = await kg_tool.execute(
    entity="Restaurant",
    depth=1,
    relationship_type="requires"
)
```

**Output:**
```
Found subgraph for 'Restaurant' (8 nodes, 12 edges):

[FOCUS] Restaurant (process)
Connections:
  - [This] --REQUIRES--> KBLI 56101
  - [This] --REQUIRES--> NIB
  - [This] --REQUIRES--> NPWP
  - [This] --REQUIRES--> IMB
  ...
```

### Esempio 2: Query Obblighi Fiscali

```python
# Query: "What taxes apply to PT PMA?"
result = await kg_tool.execute(
    entity="PT PMA",
    depth=1,
    relationship_type="tax_obligation"
)
```

### Esempio 3: Query Processo Completo

```python
# Query: "What are the steps to open a company?"
result = await kg_tool.execute(
    entity="Company Setup",
    depth=2  # Extended network
)
```

---

## ✅ CONCLUSIONE

Il Knowledge Graph fornisce:

- ✅ **Rappresentazione Strutturata** delle relazioni business
- ✅ **Query Strutturate** per trovare connessioni
- ✅ **Provenance Tracking** completo (source_chunk_ids)
- ✅ **Integrazione** con Agentic RAG
- ✅ **Scalabilità** PostgreSQL-backed

**Status:** ✅ Attivo e funzionante  
**Uso:** Query strutturate dopo vector search  
**Manutenzione:** Build automatico ogni 4 ore

---

**Documentazione creata:** 2026-01-10  
**Basata su:** Analisi codice e schema database
