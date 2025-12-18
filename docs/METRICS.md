# 📊 Zantara Phase 1 Metrics Reference

Metriche Prometheus esposte su `https://nuzantara-rag.fly.dev/metrics`.

## 🚀 RAG Performance Metrics (Phase 1)

Queste metriche tracciano le prestazioni del `SearchService`.

| Metric Name | Type | Description | Target |
| :--- | :--- | :--- | :--- |
| **`zantara_rag_pipeline_duration_seconds`** | Histogram | Durata totale della pipeline RAG (Embedding + Search + Rerank). | `< 2.0s` (p95) |
| **`zantara_rag_embedding_duration_seconds`** | Histogram | Tempo speso per generare l'embedding della query (OpenAI/Local). | `< 0.5s` |
| **`zantara_rag_vector_search_duration_seconds`** | Histogram | Tempo di risposta puro di Qdrant. | `< 0.2s` |
| **`zantara_rag_reranking_duration_seconds`** | Histogram | Tempo speso per il reranking (se attivo). | `< 1.0s` |
| **`zantara_rag_early_exit_total`** | Counter | Numero di query che hanno saltato il reranking (Score > 0.9). | Alto è meglio |
| **`zantara_db_pool_size`** | Gauge | Dimensione attuale del pool Postgres (Golden Answers). | `< 20` |

## 🕵️ How to Verify

1. **Genera traffico**:
   Esegui qualche richiesta su `/api/chat/stream` (vedi `ENDPOINTS.md`).

2. **Controlla le metriche**:
   ```bash
   curl -s https://nuzantara-rag.fly.dev/metrics | grep zantara_rag_
   ```

3. **Interpreta**:
   - Se `zantara_rag_early_exit_total` sale, l'ottimizzazione "Early Exit" funziona.
   - Se `zantara_rag_vector_search_duration_seconds` è basso, Qdrant risponde bene.

---
**Nota**: Le metriche appaiono solo DOPO la prima richiesta valida all'endpoint corretto.
