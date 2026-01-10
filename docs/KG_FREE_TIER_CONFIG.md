# 🔧 KNOWLEDGE GRAPH - Configurazione Free Tier

**Data:** 2026-01-10  
**Obiettivo:** Configurare build incrementale per rispettare limiti Google AI Studio Free Tier

---

## 🚨 LIMITI FREE TIER

### Google AI Studio Free Tier

**Richieste per Minuto (RPM):**
- **15 RPM** (richieste al minuto)

**Richieste per Giorno (RPD):**
- **1,500 RPD** (richieste al giorno)

**Fonte:** [Google AI Studio Pricing](https://ai.google.dev/pricing)

---

## ⚠️ PROBLEMA ATTUALE

### Rate Limit (RPM)

**Configurazione Attuale:**
```python
batch_size = 5  # 5 chunk paralleli
sleep = 1.0     # 1 secondo tra batch
# Throughput: ~60 RPM
```

**Limite Free Tier:** 15 RPM

❌ **SUPERA LIMITE RPM DI 4x**

### Daily Limit (RPD)

**Primo Run Incremental:**
- ~2,560 chunk nuovi (5% di 51,197)
- **Chiamate API:** ~2,560

**Limite Free Tier:** 1,500 RPD

❌ **SUPERA LIMITE RPD DI 1.7x**

---

## ✅ SOLUZIONE IMPLEMENTATA

### 1. Rate Limit (RPM) - Modificare Script

**File:** `apps/backend-rag/scripts/kg_incremental_extraction.py`

**Modifiche Necessarie:**
```python
# Attuale (60 RPM)
batch_size = 5
sleep = 1.0

# Nuovo (15 RPM - Free Tier)
batch_size = 2  # Ridotto da 5
sleep = 8.0     # Aumentato da 1.0
# Throughput: 2 chunk ogni 8s = 15/minuto ✅
```

### 2. Daily Limit (RPD) - Già Implementato

**File:** `apps/backend-rag/backend/services/knowledge_graph/incremental_builder.py`

**Implementato:**
```python
MAX_CHUNKS_PER_RUN = 1,500  # Daily limit
```

**Comportamento:**
- Limita a 1,500 chunk per run
- Processa collezioni in ordine di priorità
- Si ferma quando raggiunge limite giornaliero
- Continua giorno successivo

---

## 🔧 MODIFICHE NECESSARIE

### Modifica 1: Rate Limit nello Script

**File:** `apps/backend-rag/scripts/kg_incremental_extraction.py`

**Linea ~420:**
```python
# PRIMA
batch_size = 5  # Process 5 chunks in parallel (gemini-1.5-flash: 60+ RPM)

# DOPO
batch_size = 2  # Process 2 chunks in parallel (Free Tier: 15 RPM)
```

**Linea ~440:**
```python
# PRIMA
await asyncio.sleep(1.0)  # Rate limit between batches (1s with 5 parallel = ~60 RPM)

# DOPO
await asyncio.sleep(8.0)  # Rate limit: 2 chunk ogni 8s = 15 RPM (Free Tier limit)
```

---

## 📊 IMPATTO MODIFICHE

### Tempi di Esecuzione

**Prima (60 RPM):**
- 1,500 chunk: ~25 minuti
- 2,560 chunk: ~43 minuti

**Dopo (15 RPM):**
- 1,500 chunk: ~100 minuti (~1.7 ore)
- 2,560 chunk: ⚠️ Supera limite giornaliero (limitato a 1,500)

### Throughput

**Prima:**
- ~60 chunk/minuto
- ~3,600 chunk/ora

**Dopo:**
- ~15 chunk/minuto
- ~900 chunk/ora

**Riduzione:** 4x più lento, ma rispetta limiti free tier

---

## ✅ VERIFICA CONFIGURAZIONE

### Test Rate Limit

**Verificare logs:**
```
Progress: 30/1500 chunks | Entities: 120 | Rate: 15.0 chunks/min
```

**Se rate > 15 chunks/min:** ⚠️ Supera limite RPM

### Test Daily Limit

**Verificare logs:**
```
⚠️ Daily limit reached (1,500 chunks). Skipping remaining collections.
```

**Se processa > 1,500 chunk:** ⚠️ Supera limite RPD

---

## 🎯 STRATEGIA CONSIGLIATA

### Per Primo Run

**Opzione A: Processare Gradualmente**
- Giorno 1: Primi 1,500 chunk di `legal_unified_hybrid`
- Giorno 2: Chunk 1,501-3,000 di `legal_unified_hybrid`
- Giorno 3: Primi 1,500 chunk di `kbli_unified`
- ...

**Opzione B: Processare Solo Collezioni Piccole**
- `visa_oracle`: 82 chunk ✅
- `balizero_news_history`: 6 chunk ✅
- `tax_genius_hybrid`: 332 chunk ✅
- Totale: ~420 chunk ✅ (rientra nel limite)

### Per Run Incremental

**Dopo prima settimana:**
- ~50-200 chunk nuovi/giorno
- ✅ Rientra nel limite free tier
- ✅ Nessun problema

---

## 📝 CHECKLIST IMPLEMENTAZIONE

- [ ] Modificare `batch_size` a 2 nello script
- [ ] Modificare `sleep` a 8.0 nello script
- [ ] Verificare `MAX_CHUNKS_PER_RUN` nel builder
- [ ] Testare rate limit (verificare logs)
- [ ] Testare daily limit (verificare logs)
- [ ] Monitorare costi (dovrebbe essere $0 con free tier)

---

## ✅ CONCLUSIONE

**Modifiche Necessarie:**
1. ✅ Rate limit: batch_size=2, sleep=8.0 (già documentato)
2. ✅ Daily limit: MAX_CHUNKS_PER_RUN=1,500 (già implementato)

**Risultato:**
- ✅ Rispetta limiti free tier
- ✅ Nessun costo aggiuntivo
- ⚠️ Tempi più lunghi (4x)

**Prossimo Step:** Applicare modifiche allo script

---

**Documentazione creata:** 2026-01-10
