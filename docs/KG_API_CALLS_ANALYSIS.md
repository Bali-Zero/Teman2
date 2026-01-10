# 📊 KNOWLEDGE GRAPH - Analisi Chiamate API

**Data:** 2026-01-10  
**Obiettivo:** Calcolare chiamate API per run e verificare limiti Google AI Studio Free Tier

---

## 🔢 CALCOLO CHIAMATE API

### Formula Base

**1 chiamata API = 1 chunk processato**

Ogni chunk richiede:
- 1 chiamata a `gemini.models.generate_content()` per estrazione entità/relazioni
- Nessuna altra chiamata API aggiuntiva

**Quindi:** `Chiamate API = Numero Chunk Processati`

---

## 📊 SCENARI DI UTILIZZO

### Scenario 1: Primo Run (Full Build)

**Collezioni da Processare:**
- `legal_unified_hybrid`: 47,959 docs
- `kbli_unified`: 2,818 docs
- `tax_genius_hybrid`: 332 docs
- `visa_oracle`: 82 docs
- `balizero_news_history`: 6 docs

**Totale:** ~51,197 chunk

**Chiamate API Primo Run:** ~51,197 chiamate

⚠️ **SUPERA LIMITE FREE TIER** (1,500 RPD)

---

### Scenario 2: Run Incremental (Giornaliero)

**Assumendo 5-10% nuovi chunk/giorno:**

**5% nuovi:**
- Chunk nuovi: ~2,560
- **Chiamate API:** ~2,560

⚠️ **SUPERA LIMITE FREE TIER** (1,500 RPD)

**10% nuovi:**
- Chunk nuovi: ~5,120
- **Chiamate API:** ~5,120

❌ **SUPERA LIMITE FREE TIER** (1,500 RPD)

---

### Scenario 3: Run Incremental Realistico

**Assumendo crescita reale:**

**Prima settimana (molti nuovi):**
- Giorno 1: ~5,000 chunk nuovi → 5,000 chiamate
- Giorno 2: ~2,000 chunk nuovi → 2,000 chiamate
- Giorno 3: ~1,000 chunk nuovi → 1,000 chiamate
- Giorno 4: ~500 chunk nuovi → 500 chiamate
- Giorno 5: ~200 chunk nuovi → 200 chiamate
- Giorno 6: ~100 chunk nuovi → 100 chiamate
- Giorno 7: ~50 chunk nuovi → 50 chiamate

**Dopo prima settimana (stabile):**
- ~50-200 chunk nuovi/giorno
- **Chiamate API:** ~50-200/giorno

✅ **RIENTRA NEL LIMITE FREE TIER** (1,500 RPD)

---

## 🚨 LIMITI GOOGLE AI STUDIO FREE TIER

### Limiti Attuali

**Richieste per Minuto (RPM):**
- **15 RPM** (richieste al minuto)

**Richieste per Giorno (RPD):**
- **1,500 RPD** (richieste al giorno)

**Fonte:** [Google AI Studio Pricing](https://ai.google.dev/pricing)

---

## ⚠️ PROBLEMA IDENTIFICATO

### Rate Limit (RPM)

**Configurazione Attuale:**
- Batch size: 5 chunk paralleli
- Sleep tra batch: 1 secondo
- **Throughput:** ~60 RPM (5 chunk × 12 batch/minuto)

**Limite Free Tier:** 15 RPM

❌ **SUPERA LIMITE RPM DI 4x**

### Daily Limit (RPD)

**Primo Run:**
- ~51,197 chiamate necessarie
- Limite: 1,500 RPD

❌ **SUPERA LIMITE RPD DI 34x**

**Run Incremental (5% nuovi):**
- ~2,560 chiamate necessarie
- Limite: 1,500 RPD

❌ **SUPERA LIMITE RPD DI 1.7x**

---

## ✅ SOLUZIONI

### Soluzione 1: Ridurre Rate Limit (RPM)

**Modificare batch size e sleep:**

```python
# Attuale (60 RPM)
batch_size = 5
sleep = 1.0  # 60 RPM

# Nuovo (15 RPM)
batch_size = 2  # Ridotto
sleep = 8.0  # 15 RPM (2 chunk ogni 8s = 15/minuto)
```

**Throughput:** ~15 RPM ✅

**Tempo per 1,500 chunk:** ~100 minuti (vs ~25 minuti)

---

### Soluzione 2: Limitare Chunk per Run

**Aggiungere limite giornaliero:**

```python
MAX_CHUNKS_PER_RUN = 1,500  # Limite free tier

# Nel codice:
chunks_to_process = chunks_to_process[:MAX_CHUNKS_PER_RUN]
```

**Vantaggi:**
- ✅ Rispetta limite giornaliero
- ✅ Processa sempre i chunk più recenti
- ✅ Nessun costo aggiuntivo

**Svantaggi:**
- ⚠️ Potrebbero rimanere chunk non processati
- ⚠️ Tempo per completare tutto aumenta

---

### Soluzione 3: Processare Solo Collezioni Piccole

**Limitare a collezioni piccole:**

```python
# Solo collezioni < 500 docs
SMALL_COLLECTIONS = [
    "visa_oracle",  # 82 docs
    "balizero_news_history",  # 6 docs
    "tax_genius_hybrid",  # 332 docs
]

# Totale: ~420 chunk
```

**Vantaggi:**
- ✅ Rientra nel limite free tier
- ✅ Nessun costo aggiuntivo
- ✅ Processa collezioni importanti

**Svantaggi:**
- ⚠️ Non processa collezioni grandi (`legal_unified_hybrid`, `kbli_unified`)

---

### Soluzione 4: Processare Collezioni Grandi Gradualmente

**Strategia multi-giorno:**

```python
# Giorno 1: legal_unified_hybrid (primi 1,500 chunk)
# Giorno 2: legal_unified_hybrid (chunk 1,501-3,000)
# Giorno 3: kbli_unified (primi 1,500 chunk)
# Giorno 4: kbli_unified (chunk 1,501-3,000)
# ...
```

**Vantaggi:**
- ✅ Rispetta limite giornaliero
- ✅ Processa tutte le collezioni gradualmente
- ✅ Nessun costo aggiuntivo

**Svantaggi:**
- ⚠️ Tempo per completare tutto aumenta (settimane)

---

## 🎯 RACCOMANDAZIONE

### Strategia Ibrida

**1. Rate Limit (RPM):**
- ✅ Ridurre batch size a 2
- ✅ Aumentare sleep a 8 secondi
- ✅ Throughput: 15 RPM (limite free tier)

**2. Daily Limit (RPD):**
- ✅ Limitare a 1,500 chunk per run
- ✅ Processare chunk più recenti prima
- ✅ Continuare giorno successivo

**3. Priorità Collezioni:**
- ✅ Processare collezioni piccole completamente
- ✅ Processare collezioni grandi gradualmente (1,500 chunk/giorno)

**Codice Modificato:**
```python
# Rate limit: 15 RPM
batch_size = 2  # Ridotto da 5
sleep = 8.0  # Aumentato da 1.0

# Daily limit: 1,500 chunk
MAX_CHUNKS_PER_RUN = 1,500
chunks_to_process = chunks_to_process[:MAX_CHUNKS_PER_RUN]
```

---

## 📊 CALCOLO TEMPI

### Con Rate Limit 15 RPM

**1,500 chunk:**
- Throughput: 15 chunk/minuto
- Tempo: ~100 minuti (~1.7 ore)

**2,560 chunk (5% nuovi):**
- Tempo: ~171 minuti (~2.8 ore)

**5,120 chunk (10% nuovi):**
- Tempo: ~341 minuti (~5.7 ore)

⚠️ **Supera limite giornaliero (1,500 RPD)**

---

## ✅ CONCLUSIONE

### Free Tier Limiti

**RPM:** 15 richieste/minuto  
**RPD:** 1,500 richieste/giorno

### Chiamate API per Run

**Primo Run:** ~51,197 chiamate ❌  
**Incremental (5%):** ~2,560 chiamate ❌  
**Incremental (realistico):** ~50-200 chiamate ✅

### Raccomandazione

**Per Free Tier:**
1. ✅ Limitare a 1,500 chunk per run
2. ✅ Ridurre rate limit a 15 RPM
3. ✅ Processare collezioni grandi gradualmente
4. ✅ Priorità a collezioni piccole

**Dopo prima settimana:**
- ✅ Incremental realistico (~50-200 chunk/giorno)
- ✅ Rientra nel limite free tier
- ✅ Nessun costo aggiuntivo

---

**Documentazione creata:** 2026-01-10
