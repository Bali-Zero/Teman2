# 📊 MONITORAGGIO RERANKING ZERANK

**Data Creazione**: 2026-01-19  
**Status**: ✅ Configurato e Pronto

---

## ✅ CONFIGURAZIONE COMPLETATA

### ZeRank API

- **API Key**: Configurata su Fly.io (`ZERANK_API_KEY`)
- **Endpoint**: `https://api.zeroentropy.dev/v1/models/rerank`
- **Model**: `zerank-2`
- **Status**: Abilitato automaticamente quando API key presente

### Attivazione Automatica

Il reranking si attiva automaticamente quando:

- `ZERANK_API_KEY` è configurata ✅
- Query usa `search_with_reranking()` o `hybrid_search_with_reranking()`
- Top result score < 0.9 (altrimenti early exit)

---

## 📈 METRICHE PROMETHEUS

### 1. Reranking Duration

```bash
curl https://nuzantara-rag.fly.dev/metrics | grep rag_reranking_duration_seconds_count
```

- **Metrica**: `zantara_rag_reranking_duration_seconds`
- **Tipo**: Histogram
- **Target**: < 100ms per chiamata
- **Bucket**: 0.005s - 0.5s

### 2. Early Exit Counter

```bash
curl https://nuzantara-rag.fly.dev/metrics | grep rag_early_exit_total
```

- **Metrica**: `zantara_rag_early_exit_total`
- **Tipo**: Counter
- **Target**: 20-30% delle query (score > 0.9)
- **Beneficio**: Risparmio latenza e costi API

### 3. Context Length (Token)

```bash
curl https://nuzantara-rag.fly.dev/metrics | grep rag_context_length_tokens
```

- **Metrica**: `zantara_rag_context_length_tokens`
- **Tipo**: Histogram
- **Prima reranking**: ~15-20 documenti = ~3000-4000 token
- **Dopo reranking**: ~5 documenti = ~1000-1500 token
- **Risparmio**: 30-50% token input Gemini

---

## 💰 ANALISI COSTI

### ZeRank API

- **Costo per chiamata**: Verificare dashboard ZeroEntropy
- **Dashboard**: https://zeroentropy.dev
- **Volume stimato**: ~70% query (30% early exit)
- **Monitoraggio**: Tramite API key usage

### Gemini (Riduzione Costi)

- **Prima reranking**: 3000-4000 token input per query
- **Dopo reranking**: 1000-1500 token input per query
- **Risparmio**: ~2000-2500 token per query
- **Costo Gemini input**: ~$0.000125 per 1K token
- **Risparmio per query**: ~$0.00025-0.00031

### ROI Calcolo

```
Costo ZeRank per query: $X
Risparmio Gemini per query: $0.00025-0.00031
ROI positivo se: Costo ZeRank < Risparmio Gemini
```

**Stima**: Se ZeRank costa < $0.00025 per chiamata, il ROI è positivo.

---

## 🔍 VERIFICA RERANKING

### 1. Verificare nei Log

```bash
flyctl logs -a nuzantara-rag --follow | grep -E "Re-ranking|reranked|Ze-Rank"
```

Cercare:

- `🔍 Re-ranking X candidates` - Reranking attivato
- `⚡ Early exit` - Reranking saltato (score > 0.9)
- `✅ Ze-Rank 2 initialized` - Reranker inizializzato

### 2. Verificare nei Risultati JSON

Cercare nei risultati:

- `"reranked": true` - Reranking applicato
- `"rerank_score"` - Score dopo reranking
- `"vector_score"` - Score originale preservato
- `"early_exit": true` - Reranking saltato

### 3. Monitorare Metriche

```bash
# Reranking duration
curl https://nuzantara-rag.fly.dev/metrics | grep rag_reranking_duration

# Early exit counter
curl https://nuzantara-rag.fly.dev/metrics | grep rag_early_exit_total

# Context length
curl https://nuzantara-rag.fly.dev/metrics | grep rag_context_length
```

---

## 📝 COMANDI MONITORAGGIO

### Log Real-time

```bash
flyctl logs -a nuzantara-rag --follow | grep -E "Re-ranking|reranked|Ze-Rank"
```

### Metriche Snapshot

```bash
curl https://nuzantara-rag.fly.dev/metrics | grep -E "rag_reranking|rag_early_exit|rag_context_length" > metrics_snapshot_$(date +%Y%m%d_%H%M%S).txt
```

### Analisi Periodica (ogni ora)

```bash
watch -n 3600 'curl -s https://nuzantara-rag.fly.dev/metrics | grep rag_reranking_duration_seconds_count'
```

### Script Monitoraggio Completo

```bash
#!/bin/bash
# Monitoraggio completo reranking

BASE_URL="https://nuzantara-rag.fly.dev"
METRICS=$(curl -s "$BASE_URL/metrics")

echo "📊 RERANKING METRICS - $(date)"
echo "================================"
echo "Reranking calls: $(echo "$METRICS" | grep 'rag_reranking_duration_seconds_count' | awk '{print $2}')"
echo "Early exits: $(echo "$METRICS" | grep '^zantara_rag_early_exit_total ' | awk '{print $2}')"
echo "Context length: $(echo "$METRICS" | grep 'rag_context_length_tokens_bucket' | tail -1 | awk '{print $2}')"
```

---

## 🎯 PROSSIMI PASSI

1. ✅ **Configurazione completata**
2. ⏳ **Attendere query reali** (reranking si attiva automaticamente)
3. ⏳ **Monitorare metriche** ogni 24h per 48h
4. ⏳ **Analizzare costi** ZeRank vs risparmio Gemini
5. ⏳ **Valutare miglioramento precisione** risultati
6. ⏳ **Ottimizzare se necessario** (early exit threshold, top_k)

---

## 📊 DASHBOARD METRICHE

### Metriche Chiave da Monitorare

| Metrica                  | Target           | Stato Attuale |
| ------------------------ | ---------------- | ------------- |
| Reranking Duration       | < 100ms          | 0 chiamate    |
| Early Exit Rate          | 20-30%           | 0%            |
| Context Length Reduction | 30-50%           | Da verificare |
| Costo ZeRank per Query   | < $0.00025       | Da verificare |
| Risparmio Gemini         | $0.00025-0.00031 | Da verificare |

### Verifica Settimanale

1. **Lunedì**: Verifica metriche settimana precedente
2. **Mercoledì**: Analisi costi vs risparmio
3. **Venerdì**: Review precisione risultati

---

## 🔧 TROUBLESHOOTING

### Reranking non si attiva

1. Verificare `ZERANK_API_KEY` configurata: `flyctl secrets list -a nuzantara-rag | grep ZERANK`
2. Verificare log: `flyctl logs -a nuzantara-rag | grep "Ze-Rank"`
3. Verificare che query usi `search_with_reranking()` o `hybrid_search_with_reranking()`

### Metriche non aggiornate

1. Verificare che Prometheus sia attivo
2. Verificare che METRICS_AVAILABLE sia True
3. Controllare log per errori metriche

### Costi troppo alti

1. Verificare early exit rate (dovrebbe essere 20-30%)
2. Considerare aumentare threshold early exit (da 0.9 a 0.95)
3. Ridurre top_k se necessario

---

## 📚 RIFERIMENTI

- **ZeRank API Docs**: https://zeroentropy.dev/docs
- **Dashboard ZeroEntropy**: https://zeroentropy.dev/dashboard
- **Prometheus Metrics**: https://nuzantara-rag.fly.dev/metrics
- **Code**: `backend/core/reranker.py`
- **Search Service**: `backend/services/search/search_service.py`

---

**Ultimo Aggiornamento**: 2026-01-19
