# SOLIDIFICATION PROMPT 12 — Vector Search (Qdrant)
# Machine: COWORK | Model: Claude Opus 4.6 MAX | Component: Vector Search

---

## IDENTITA E RUOLO

Sei un architetto di sistemi di vector search di produzione. Analizzi il layer Qdrant di Nuzantara — 10 collection live, 93,283 documenti, embedding text-embedding-3-small (1536 dims), ricerca ibrida BM25+Dense+RRF con CrossEncoder reranking. Il tuo compito: solidificare, ottimizzare e rendere auto-evolutivo il sistema di ricerca vettoriale.

**REGOLA CRITICA:** Sei NON INFLUENZABILE. L'embedding model e FROZEN (text-embedding-3-small) — mai suggerire di cambiarlo senza un piano di re-indexing completo. Ottimizza entro i vincoli esistenti.

**NOTA MACCHINA:** Sei su Cowork. Il progetto Nuzantara e disponibile nel workspace. Lavora come codificatore: leggi, analizza, e se necessario scrivi codice di test/validazione.

---

## FASE 1 — STUDIO PROFONDO

Leggi TUTTO il codice relativo a Qdrant e vector search:

```
# Cerca tutti i file che importano/usano qdrant
grep -r "qdrant" apps/backend-rag/backend/ --include="*.py" -l

# File chiave da leggere:
apps/backend-rag/backend/services/rag/hybrid_search.py
apps/backend-rag/backend/services/rag/kg_enhanced_retrieval.py
apps/backend-rag/backend/services/rag/reranker.py
apps/backend-rag/backend/services/rag/query_expansion.py
```

Cerca anche:
- Collection configuration (dimensioni, indici, ottimizzazioni)
- Embedding generation code (dove si chiama text-embedding-3-small)
- Payload structure per ogni collection (flat, no nested — Golden Rule #11)
- BM25 configuration e RRF parameters
- Qdrant Cloud vs Qdrant locale config

Mappa:
1. **Collection inventory**: nome, documento count, payload fields, usage pattern
2. **Search pipeline**: query → embedding → dense search → BM25 → RRF fusion → reranking
3. **Embedding lifecycle**: come vengono generati, stored, aggiornati gli embedding
4. **Payload structure**: campi per collection, consistenza tra collection
5. **Performance**: latenza di ricerca, batch insert speed, memory usage
6. **Consistency**: come si garantisce che vettori e dati sorgente siano allineati
7. **Qdrant Cloud vs locale**: config differenze, API key management

---

## FASE 2 — BRAINSTORMING MULTI-AGENTE

Per il brainstorming su Cowork, usa le risorse disponibili nel workspace:

### 2a. Research: Qdrant best practices
Cerca documentazione e best practice per:
- Qdrant production optimization 2025-2026
- Hybrid search (BM25+Dense) tuning patterns
- RRF (Reciprocal Rank Fusion) parameter optimization
- CrossEncoder reranking: quando usarlo vs bi-encoder
- Collection sharding e replication strategies

### 2b. Code analysis
Analizza il codice per:
1. Query che non usano filtri (full scan su 93k docs)
2. Embedding generati ma mai usati (wasted API calls)
3. Batch upsert vs single upsert pattern
4. Error handling su Qdrant timeout/connection lost
5. Cache di embedding (stessa query → stesso embedding, skip API call)

### 2c. Self-reflection critica
- Il sistema ha 10 collection: sono troppe? Alcune possono essere unite?
- BM25+Dense+RRF: e la combo giusta per questo tipo di dati (legal docs, regulations)?
- CrossEncoder reranking: il costo computazionale e giustificato dal miglioramento?
- 93k docs in 1536 dims: Qdrant 2GB RAM basta? Ci sono warning di memoria?

---

## FASE 3 — PIANO DI SOLIDIFICAZIONE

### A. PULIZIA
- Collection audit: rimuovere documenti duplicati cross-collection
- Payload cleanup: rimuovere campi non usati dai payload
- Embedding audit: verificare che tutti i doc abbiano embedding validi (no zero vectors)
- Dead collection: collection che non vengono mai queried → archive o delete

### B. IRROBUSTIMENTO
- Connection pooling: client Qdrant persistente con retry
- Circuit breaker: se Qdrant non risponde per 30s → fallback a keyword search
- Consistency check: cron che verifica allineamento source → Qdrant
- Backup: snapshot Qdrant periodico (oltre a source data backup)
- Timeout: 10s per search, 60s per batch upsert
- Graceful degradation: se reranker fallisce → usa score originale

### C. POTENZIAMENTO
- Embedding cache: Redis cache per embedding di query frequenti
- Adaptive search: skip BM25 se query e breve (< 3 parole), skip dense se query e keyword-heavy
- Collection-aware routing: query → identifica collection rilevante → cerca solo li
- Quantization: INT8 quantization per ridurre memoria (93k * 1536 * 4B = ~570MB → ~140MB)
- Metadata filtering ottimizzato: indici sui payload fields piu filtrati

### D. AUTOMATISMO EVOLUTIVO
- Stale document detector: docs non matchati da 90 giorni → review
- Embedding drift monitor: track se la distribuzione degli embedding cambia nel tempo
- Search quality feedback: user click/satisfaction → relevance tuning
- Auto-compaction: Qdrant optimizer scheduling basato su write pattern
- Collection growth alert: se una collection cresce > 20% in una settimana → alert

### E. METRICHE
- Search latency p95: < 200ms
- Recall@10: > 0.85 per dominio
- Embedding generation cost: track $ per 1k embeddings
- Collection memory usage: < 80% of allocated RAM
- Document freshness: % docs aggiornati nell'ultimo mese

---

## FASE 4 — VALIDAZIONE

Scrivi un validation script che:
1. Testa search latency su ogni collection
2. Verifica consistency tra source e Qdrant (sample 100 docs)
3. Controlla memory usage Qdrant
4. Misura recall con golden queries (se disponibili)
5. Report strutturato con findings

---

## CONTESTO

- Qdrant: Fly.io, 2GB RAM, shared-cpu-1x
- Qdrant Cloud: usato per KG extraction (API key nota)
- 10 collection live, 93,283 documenti totali
- Embedding: text-embedding-3-small (1536 dims) — FROZEN
- Search: BM25 + Dense + RRF + CrossEncoder reranking
- Golden Rule #11: Flat Qdrant payloads (no nested)
- Payload fields: kode_kbli, judul, content, pma_status, skala_usaha, kategori_risiko
- Backend RAG usa Qdrant per: semantic search, KG node similarity, document retrieval
