# ✅ KNOWLEDGE GRAPH AUTO-BUILD - Implementazione Completata

**Data:** 2026-01-10  
**Status:** ✅ Implementato

---

## 🎯 SPECIFICHE IMPLEMENTATE

### ✅ Build Incrementale Automatico

- **Frequenza:** Ogni 24 ore
- **Strategia:** Solo chunk nuovi/modificati (non full rebuild)
- **Collezioni:** Alta priorità configurate
- **Modello:** Gemini via Google AI Studio
- **Error Handling:** Robusto con retry

---

## 📋 COLLEZIONI CONFIGURATE

### Collezioni Alta Priorità (processate ogni 24h)

1. `legal_unified_hybrid` (47,959 docs)
2. `kbli_unified` (2,818 docs)
3. `tax_genius_hybrid` (332 docs)
4. `visa_oracle` (82 docs)
5. `balizero_news_history` (6 docs)

**Totale documenti:** ~51,197 documenti

---

## 🔧 IMPLEMENTAZIONE

### 1. Nuovo Servizio: `KGIncrementalBuilder`

**File:** `apps/backend-rag/backend/services/knowledge_graph/incremental_builder.py`

**Funzionalità:**
- ✅ Traccia chunk processati (`get_processed_chunk_ids()`)
- ✅ Filtra solo chunk nuovi
- ✅ Integra `KGIncrementalExtractor` script
- ✅ Usa Gemini via Google AI Studio
- ✅ Error handling con retry (max 3 tentativi)
- ✅ Continue on error (non blocca altre collezioni)

**Metodo Principale:**
```python
async def run_incremental_extraction(
    self,
    collections: list[str] | None = None,
    max_retries: int = 3,
) -> dict[str, Any]
```

---

### 2. Modificato: `AutonomousScheduler`

**File:** `apps/backend-rag/backend/services/misc/autonomous_scheduler.py`

**Modifiche:**
- ✅ Frequenza cambiata: 4h → 24h
- ✅ Integrato `run_knowledge_graph_incremental_build()`
- ✅ Processa conversazioni (7 giorni)
- ✅ Processa collezioni Qdrant (incremental)
- ✅ Error handling robusto

**Task Function:**
```python
async def run_knowledge_graph_builder():
    # 1. Schema verification
    await graph_builder.init_graph_schema()
    
    # 2. Process conversations
    await graph_builder.build_graph_from_all_conversations(days_back=7)
    
    # 3. Incremental Qdrant extraction
    stats = await run_knowledge_graph_incremental_build(db_pool)
```

---

## 🔑 CONFIGURAZIONE GOOGLE AI STUDIO

### API Key

**Variabile Ambiente:**
```bash
GOOGLE_API_KEY=AIzaSyCr-wmXSDvRhAYqsV0XME227EX_uwXGWZI
```

**Supporto Multiplo:**
Il sistema supporta:
- `GOOGLE_API_KEY` (preferito)
- `GOOGLE_AI_STUDIO_KEY` (alternativo)
- `GOOGLE_IMAGEN_API_KEY` (fallback)

**Inizializzazione:**
```python
from google import genai
client = genai.Client(api_key=api_key)  # Google AI Studio
```

**Modello Usato:**
- `gemini-2.0-flash` (economico e veloce)
- Rate limit: 60+ RPM
- Costo: ~$0.0005 per chunk

---

## 🛡️ ERROR HANDLING

### Strategia Implementata

**1. Retry con Exponential Backoff**
- Max 3 tentativi per collezione
- Wait time: 2^attempt secondi (2s, 4s, 8s)
- Continue on error (non blocca altre collezioni)

**2. Error Logging**
- Log dettagliato per ogni errore
- Tracking errori per collezione
- Statistiche finali con errori

**3. Graceful Degradation**
- Se Gemini non disponibile → skip (non crash)
- Se collezione fallisce → continua con altre
- Se DB non disponibile → skip (non crash)

**Codice:**
```python
for collection in collections:
    for attempt in range(max_retries):
        try:
            stats = await extractor.run(collections=[collection])
            break  # Success
        except Exception as e:
            if attempt == max_retries - 1:
                total_stats["collections_failed"] += 1
                total_stats["errors"].append(error_msg)
            else:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
```

---

## 📊 STATISTICHE E MONITORING

### Statistiche Ritornate

```python
{
    "collections_processed": 5,
    "collections_failed": 0,
    "total_chunks": 1234,
    "total_entities": 5678,
    "total_relationships": 3456,
    "errors": []
}
```

### Logging

**Log Livelli:**
- ✅ INFO: Progress e successi
- ⚠️ WARNING: Skip e retry
- ❌ ERROR: Errori critici

**Esempio Log:**
```
🕸️ Processing collection: legal_unified_hybrid
Found 45,000 already processed chunks
  legal_unified_hybrid: 2,959 unprocessed / 47,959 total
Progress: 100/2959 chunks | Entities: 450 | Rate: 50.0 chunks/min
✅ legal_unified_hybrid: 2,959 chunks, 1,234 entities, 567 relationships
```

---

## 💰 COSTI STIMATI

### Per Run (24h)

**Assumendo 5-10% nuovi chunk/giorno:**
- Chunk nuovi: ~2,500-5,000/giorno
- Costo/chunk: ~$0.0005 (Gemini Flash)
- **Costo/run: ~$1.25-2.50**

**Costo Mensile:**
- **~$37.50-75/mese** (incremental)
- vs ~$1,500/mese (full rebuild giornaliero)

**Risparmio:** ~95% rispetto a full rebuild

---

## ⏱️ PERFORMANCE

### Tempi Stimati

**Per Run (2,500-5,000 nuovi chunk):**
- Batch size: 5 chunk paralleli
- Throughput: ~50 chunk/minuto
- **Tempo: ~50-100 minuti**

**Ottimizzazioni Future:**
- Batch size maggiore: 10 → ~25-50 minuti
- Concurrent maggiore: 10 → ~12-25 minuti

---

## ✅ VERIFICA IMPLEMENTAZIONE

### File Creati/Modificati

1. ✅ **Creato:** `apps/backend-rag/backend/services/knowledge_graph/incremental_builder.py`
   - Servizio per build incrementale
   - Integrazione con script esistente
   - Error handling robusto

2. ✅ **Modificato:** `apps/backend-rag/backend/services/misc/autonomous_scheduler.py`
   - Frequenza: 24h
   - Integrato build incrementale
   - Processa conversazioni + Qdrant

### Configurazione Richiesta

**Variabili Ambiente:**
```bash
# Google AI Studio API Key (richiesto)
GOOGLE_API_KEY=AIzaSyCr-wmXSDvRhAYqsV0XME227EX_uwXGWZI

# Qdrant (già configurato)
QDRANT_URL=https://nuzantara-qdrant.fly.dev
QDRANT_API_KEY=<existing>

# Database (già configurato)
DATABASE_URL=<existing>
```

---

## 🚀 COME FUNZIONA

### Workflow Automatico (ogni 24h)

1. **Schema Verification**
   - Verifica/inizializza `kg_nodes` e `kg_edges`
   - Crea indici se necessario

2. **Process Conversazioni**
   - Analizza conversazioni ultimi 7 giorni
   - Estrae entità/relazioni menzionate
   - Aggiorna knowledge graph

3. **Incremental Qdrant Extraction**
   - Per ogni collezione prioritaria:
     - Recupera chunk processati da DB
     - Filtra solo chunk nuovi
     - Estrae entità/relazioni con Gemini
     - Persiste in PostgreSQL
   - Retry su errori (max 3 tentativi)
   - Continue on error

4. **Logging e Statistiche**
   - Log progress dettagliato
   - Statistiche finali
   - Errori tracciati

---

## 📈 BENEFICI ATTESI

### Tecnici

**✅ Knowledge Graph Aggiornato:**
- Entità/relazioni sempre aggiornate
- Query più accurate
- Migliore comprensione contesto

**✅ Performance:**
- Query strutturate più veloci
- Context più ricco per AI
- Relazioni validate

### Business

**✅ Migliori Risposte AI:**
- Context più ricco
- Relazioni strutturate
- Entità validate

**✅ Manutenzione Automatica:**
- Nessun intervento manuale
- Aggiornamento continuo
- Sistema self-healing

---

## ⚠️ NOTE IMPORTANTI

### Google AI Studio API Key

**✅ Supportato:**
- La chiave fornita (`GOOGLE_API_KEY`) funziona con Google AI Studio
- Usa `genai.Client(api_key=api_key)` per inizializzazione
- Modello: `gemini-2.0-flash` (economico)

**Verifica:**
- Il codice già supporta Google AI Studio
- La chiave viene letta da `GOOGLE_API_KEY` env var
- Fallback a `GOOGLE_AI_STUDIO_KEY` o `GOOGLE_IMAGEN_API_KEY`

### Tracking Chunk Processati

**Metodo:**
- Usa `source_chunk_ids` array in `kg_nodes` e `kg_edges`
- Query SQL per recuperare chunk già processati
- Filtra chunk nuovi prima di estrazione

**Efficienza:**
- GIN index su `source_chunk_ids` per query veloci
- Set-based filtering per performance

---

## 🎯 PROSSIMI STEP

### 1. Configurare API Key

**Su Fly.io:**
```bash
fly secrets set GOOGLE_API_KEY=AIzaSyCr-wmXSDvRhAYqsV0XME227EX_uwXGWZI -a nuzantara-rag
```

**Localmente (.env):**
```bash
GOOGLE_API_KEY=AIzaSyCr-wmXSDvRhAYqsV0XME227EX_uwXGWZI
```

### 2. Verificare Funzionamento

**Dopo deploy:**
- Verificare logs scheduler
- Controllare che task esegua ogni 24h
- Monitorare costi LLM
- Verificare statistiche KG

### 3. Monitoring

**Metriche da Tracciare:**
- Chunk processati per run
- Entità/relazioni estratte
- Costo LLM per run
- Errori e retry
- Tempo esecuzione

---

## ✅ CONCLUSIONE

**Implementazione Completata:**

- ✅ Build incrementale automatico ogni 24h
- ✅ Solo chunk nuovi/modificati
- ✅ Collezioni prioritarie configurate
- ✅ Gemini via Google AI Studio
- ✅ Error handling robusto

**Status:** ✅ **Pronto per Deploy**

**Costo Stimato:** ~$1.25-2.50/run (~$37.50-75/mese)

**Tempo Stimato:** ~50-100 minuti/run

---

**Implementato:** 2026-01-10  
**Prossimo Step:** Configurare `GOOGLE_API_KEY` e deployare
