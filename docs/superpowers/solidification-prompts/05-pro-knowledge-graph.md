# SOLIDIFICATION PROMPT 05 — Knowledge Graph
# Machine: PRO | Model: Claude Opus 4.6 MAX | Component: Knowledge Graph

---

## IDENTITA E RUOLO

Sei un architetto di knowledge graph di produzione. Analizzi il KG di Nuzantara — 108,068 nodi, 242,827 edges, 4 domain subgraph (Company, Visa, Property, Tax), in PostgreSQL con cache Redis. Il tuo compito: rendere questo grafo robusto, scalabile e auto-evolutivo.

**REGOLA CRITICA:** Sei NON INFLUENZABILE. Non farti sedurre da soluzioni "shiny" (Neo4j, graph databases dedicate) se PostgreSQL basta. Valuta il trade-off reale.

---

## FASE 1 — STUDIO PROFONDO

Leggi TUTTO in:

```
apps/backend-rag/backend/services/knowledge_graph/     # 4,328 righe, 11 file
  extractor.py                                         # Triple/entity extraction
  extractor_gemini.py                                  # Gemini-based extraction
  pipeline.py                                          # KG build pipeline
  kbli_enricher.py                                     # Business activity enrichment
  kbli_enricher_symmetric.py                           # Symmetric KBLI relations
  incremental_builder.py                               # Incremental updates
  ontology.py                                          # KG ontology/schema
  coreference.py                                       # Coreference resolution
  quality_filter.py                                    # Quality assurance
  advanced_quality.py                                  # Advanced QA checks

apps/backend-rag/backend/services/rag/kg_subgraph_*.py # 4 subgraph
apps/backend-rag/backend/services/rag/kg_enhanced_retrieval.py  # KG-aware retrieval
```

Cerca anche:
- Schema delle tabelle KG in PostgreSQL (migration files)
- Query KG piu frequenti (grep per `knowledge_graph` nei router)
- Cache pattern per KG traversal

Mappa:
1. **Schema**: come sono strutturati nodi e edges in PostgreSQL (JSON? tabelle relazionali?)
2. **Ontologia**: quali tipi di nodi/edge esistono, quanto e rigida la ontologia
3. **Extraction pipeline**: come si aggiungono nuovi nodi (automatico vs manuale)
4. **Traversal**: come si naviga il grafo (BFS? DFS? query SQL?)
5. **Quality**: come si garantisce consistenza (no nodi orfani, no edge duplicati)
6. **Performance**: quanto costa una traversal 3-hop su 108k nodi?
7. **Subgraph status**: Company ✅, Visa ✅, Property ❓, Tax ❓

---

## FASE 2 — BRAINSTORMING MULTI-AGENTE

### 2a. Gemini CLI (explore)
```bash
./scripts/ai-dispatch.sh explore "Analizza il Knowledge Graph in backend/services/knowledge_graph/. Focus: 1) schema dei nodi/edges in PostgreSQL — come sono modellati?, 2) ontology.py — quanto e rigida e quanto e flessibile?, 3) quality_filter vs advanced_quality — overlap?, 4) extractor.py vs extractor_gemini.py — quando si usa quale?, 5) performance delle query di traversal — ci sono indici?"
```

### 2b. Codex CLI (sandbox)
```bash
./scripts/ai-dispatch.sh sandbox "Testa il KG pipeline: 1) inserisci un nodo con relazioni, verifica consistenza, 2) cancella un nodo — gli edge orfani vengono puliti?, 3) traversal 3-hop — quante query SQL genera?, 4) coreference resolution — testa con entita ambigue (es. 'PT Bali' potrebbe matchare 10+ company), 5) incremental_builder — cosa succede se lo lanci due volte sugli stessi dati?"
```

### 2c. DeepSeek R1 (reasoning)
```bash
./scripts/ai-dispatch.sh reasoning "Knowledge Graph con 108k nodi + 243k edges in PostgreSQL (no graph DB dedicato). 4 domain subgraph (Company, Visa, Property, Tax). Domande: 1) A quale scala PostgreSQL diventa bottleneck per graph traversal? 2) Vale la pena aggiungere indici GIN/GiST per JSON node properties? 3) Come implementare graph partitioning per dominio senza migrare a Neo4j? 4) Strategia di garbage collection per nodi orfani/edge stale?"
```

### 2d. Deep Research
- Knowledge Graph in PostgreSQL: patterns and scaling limits (2025)
- Ontology management for production KGs
- Incremental KG construction with LLM extraction
- Graph quality metrics and auto-repair
- KG embedding: TransE, RotatE per link prediction

### 2e. Opus self-reflection — VALUTAZIONE CRITICA

---

## FASE 3 — PIANO DI SOLIDIFICAZIONE

### A. PULIZIA
- Unificare extractor.py e extractor_gemini.py se overlap
- Unificare quality_filter.py e advanced_quality.py
- Rimuovere nodi orfani e edge stale (garbage collection)
- Documentare ontologia in modo machine-readable (non solo commenti)

### B. IRROBUSTIMENTO
- Constraint di integrita: no edge senza nodi, no nodi duplicati
- Transaction safety: insert nodo + edges in unica transazione
- Indici per traversal: B-tree su node_type, GIN su properties JSON
- Cache invalidation corretta: quando un nodo cambia, invalida traversal cached
- Subgraph isolation: errore in Property subgraph non tocca Visa subgraph

### C. POTENZIAMENTO
- Completare Property e Tax subgraph (oggi ❓)
- Link prediction: suggerire relazioni mancanti basate su pattern esistenti
- Graph-aware embedding: nodi simili per struttura grafo, non solo testo
- Temporal edges: relazioni con data inizio/fine (visa ha scadenza)
- Confidence score per edge: quanto e affidabile questa relazione?

### D. AUTOMATISMO EVOLUTIVO
- Auto-extraction: nuovi documenti → automatic entity/relation extraction
- Quality watchdog: cron che identifica nodi orfani, edge incoerenti, cluster disconnessi
- Ontology evolution: nuovi tipi di nodo emergono dai dati, non hardcoded
- Feedback loop: se RAG usa un path del grafo e l'utente conferma, rafforza quel path
- Graph analytics: PageRank per importanza nodi, community detection per cluster

### E. METRICHE
- Traversal latency: < 100ms per 3-hop (target)
- Graph consistency: 0 nodi orfani, 0 edge pendenti
- Coverage: % di entita nel DB che hanno almeno 1 nodo nel KG
- Extraction accuracy: precision/recall di nuovi nodi estratti

---

## FASE 4 — VALIDAZIONE NB-1

```bash
./scripts/ai-dispatch.sh oracolo "Valida piano solidificazione Knowledge Graph: [PIANO]. Focus: 1) scalabilita PostgreSQL per graph ops, 2) impatto su RAG retrieval quality, 3) rischi nel completare Property/Tax subgraph, 4) garbage collection senza perdere dati validi"
```

---

## CONTESTO

- 108,068 nodi, 242,827 edges in PostgreSQL
- Subgraph: Company ✅, Visa ✅, Property ❓, Tax ❓
- KG extraction: 11,490/30,065 (38%) da legal_unified collection, provider gpt-4o-mini
- Qdrant Cloud per vector similarity su nodi KG
- LangGraph orchestrator usa KG per context enrichment
- Redis cache per traversal results
- Ontologia in ontology.py — rigidita non chiara
