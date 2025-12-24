# Qdrant Stats - Statistiche Collezioni

Mostra statistiche dettagliate delle collezioni Qdrant.

## Istruzioni

1. **Connessione a Qdrant**:
   - Usa l'endpoint API del backend: `https://nuzantara-rag.fly.dev/api/debug/qdrant/collections/health`
   - Oppure query diretta Qdrant Cloud (se disponibile)

2. **Recupera statistiche**:
   ```bash
   curl -s https://nuzantara-rag.fly.dev/api/debug/qdrant/collections/health \
     -H "X-API-Key: $ADMIN_API_KEY" | jq
   ```

3. **Per ogni collezione**:
   ```bash
   curl -s "https://nuzantara-rag.fly.dev/api/debug/qdrant/collection/{collection_name}/stats" \
     -H "X-API-Key: $ADMIN_API_KEY" | jq
   ```

4. **Analisi**:
   - Confronta con valori attesi (da SYSTEM_MAP_4D.md)
   - Segnala anomalie (documenti mancanti, collezioni vuote)

## Collezioni attese

| Collezione | Documenti attesi | Scopo |
|------------|------------------|-------|
| kbli_unified | ~8,886 | Business classification codes |
| legal_unified | ~5,041 | Laws & regulations |
| visa_oracle | ~1,612 | Immigration documents |
| tax_genius | ~895 | Tax regulations |
| bali_zero_pricing | ~29 | Service pricing |
| bali_zero_team | ~22 | Team profiles |
| knowledge_base | ~37,272 | General KB |

**Totale atteso: ~53,757 documenti**

## Output atteso

```
## Qdrant Collections Status

### Overview
- Total collections: 7
- Total documents: 53,757
- Status: healthy

### Collections Detail

| Collection | Documents | Status | Last Updated |
|------------|-----------|--------|--------------|
| kbli_unified | 8,886 | OK | 2025-12-20 |
| legal_unified | 5,041 | OK | 2025-12-22 |
| visa_oracle | 1,612 | OK | 2025-12-21 |
| tax_genius | 895 | OK | 2025-12-19 |
| bali_zero_pricing | 29 | OK | 2025-12-15 |
| bali_zero_team | 22 | OK | 2025-12-10 |
| knowledge_base | 37,272 | OK | 2025-12-23 |

### Vector Config
- Dimensions: 1536
- Distance: Cosine
- Provider: OpenAI text-embedding-3-small

### BM25 Sparse
- Enabled: Yes
- Vocab size: 30,000
- Hybrid weights: Dense=0.7, Sparse=0.3

### Health
- [x] All collections accessible
- [x] No orphaned vectors
- [x] Indexes optimized
```
