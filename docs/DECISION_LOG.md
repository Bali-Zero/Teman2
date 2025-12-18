# 🪵 Decision Log & Technical Discoveries

Questo file traccia le decisioni tecniche chiave e le scoperte fatte durante lo sviluppo per evitare regressioni o dubbi futuri.

## 2025-12-18: Phase 1 Metrics Instrumentation

### Context
Durante la verifica del deploy della Phase 1, è emersa una discrepanza nella generazione delle metriche tra i vari endpoint.

### Discovery
- **Problema**: Le chiamate a `POST /api/oracle/query` non generavano le metriche `zantara_rag_*`.
- **Causa**: `OracleService.process_query` istanzia manualmente `EmbeddingsGenerator` e chiama direttamente `vector_db.search`, bypassando il metodo `SearchService.search()` che contiene l'instrumentazione Prometheus.
- **Conferma**: L'endpoint `POST /api/chat/stream` (utilizzando `IntelligentRouter` -> `AgenticRAG` -> `VectorSearchTool`) chiama correttamente `SearchService` e genera le metriche.

### Decision
1.  **Verification Path**: Utilizzare esclusivamente `/api/chat/stream` per validare le performance RAG della Phase 1.
2.  **Documentation**: Aggiornare `ENDPOINTS.md` per riflettere esplicitamente quali endpoint sono strumentati.
3.  **Future Debt**: Pianificare il refactoring di `OracleService` per utilizzare `SearchService` centralizzato (unificazione logica di ricerca).

---

## 2025-12-18: Fly.io Startup Latency

### Context
Il deploy falliva sistematicamente per timeout durante l'avvio del container.

### Decision
- **Fix**: Aumentato `grace_period` nel `fly.toml` da `1m` a `5m`.
- **Reason**: Il download dei modelli ML all'avvio (lazy loading parziale o init) richiede più tempo delle risorse CPU condivise disponibili su Fly.io.

