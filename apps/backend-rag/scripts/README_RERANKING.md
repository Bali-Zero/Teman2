# 🔄 Script Monitoraggio Reranking

Script automatizzati per monitorare, analizzare e valutare il reranking ZeRank.

## 📁 Script Disponibili

### 1. `monitor_reranking.sh`

Snapshot metriche e analisi costi/precisione.

**Utilizzo:**

```bash
bash scripts/monitor_reranking.sh
```

**Output:**

- `monitoring/reranking/snapshot_YYYYMMDD_HHMMSS.txt` - Metriche snapshot
- `monitoring/reranking/cost_analysis_YYYYMMDD_HHMMSS.md` - Analisi costi
- `monitoring/reranking/precision_YYYYMMDD_HHMMSS.md` - Valutazione precisione

---

### 2. `continuous_monitoring.sh`

Monitoraggio continuo ogni N ore per M ore.

**Utilizzo:**

```bash
# Monitoraggio ogni 24h per 48h (default)
bash scripts/continuous_monitoring.sh 48 24

# Monitoraggio ogni 12h per 72h
bash scripts/continuous_monitoring.sh 72 12
```

**Parametri:**

- `DURATION_HOURS` (default: 48) - Durata totale monitoraggio
- `INTERVAL_HOURS` (default: 24) - Intervallo tra snapshot

**Output:**

- Esegue `monitor_reranking.sh` ad ogni intervallo
- Genera file timestamped per ogni snapshot

---

### 3. `analyze_reranking_performance.py`

Analisi completa performance con report dettagliato.

**Utilizzo:**

```bash
python3 scripts/analyze_reranking_performance.py
```

**Output:**

- `monitoring/reranking/performance_report_YYYYMMDD_HHMMSS.md` - Report completo

**Requisiti:**

- Python 3.8+
- `httpx`: `pip install httpx`

---

## 🎯 Workflow Consigliato

### Monitoraggio 48h (ogni 24h)

```bash
# Avvia monitoraggio continuo
bash scripts/continuous_monitoring.sh 48 24

# In background (opzionale)
nohup bash scripts/continuous_monitoring.sh 48 24 > monitoring.log 2>&1 &
```

### Analisi Dopo 48h

```bash
# Genera report completo
python3 scripts/analyze_reranking_performance.py

# Analizza tutti i file generati
ls -lh monitoring/reranking/
```

---

## 📊 Metriche Tracciate

### Performance

- `rag_reranking_duration_seconds` - Latenza reranking
- `rag_early_exit_total` - Query che saltano rerank
- `rag_context_length_tokens` - Token nel contesto

### Costi

- Costo ZeRank API (per chiamata)
- Risparmio Gemini (per query)
- ROI netto

### Precisione

- Evidence Score
- Ranking quality
- User feedback (da raccogliere)

---

## 💰 Aggiornare Costi Reali

Modifica i valori in `analyze_reranking_performance.py`:

```python
ZERANK_COST_PER_CALL = 0.0001  # Aggiorna da ZeroEntropy dashboard
GEMINI_SAVINGS_PER_QUERY = 0.00028  # Calcola da Gemini usage
```

**Dashboard:**

- ZeroEntropy: https://zeroentropy.dev/dashboard
- Gemini: Google Cloud Console

---

## 🔍 Verifica Risultati

### Nei Log

```bash
flyctl logs -a nuzantara-rag | grep -E "Re-ranking|reranked|Ze-Rank"
```

### Nelle Metriche

```bash
curl https://nuzantara-rag.fly.dev/metrics | grep rag_reranking
```

### Nei Risultati JSON

Cercare:

- `"reranked": true`
- `"rerank_score"`
- `"early_exit": true`

---

## 📝 Note

- Gli script creano automaticamente la directory `monitoring/reranking/`
- I file sono timestamped per tracciare evoluzione nel tempo
- I costi sono stime iniziali, aggiornare con valori reali

---

**Ultimo Aggiornamento**: 2026-01-19
