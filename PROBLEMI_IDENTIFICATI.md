# 🚨 PROBLEMI IDENTIFICATI - Unified Test Force

## ❌ PROBLEMI CRITICI

### **1. Circuit Breaker Troppo Aggressivo**

- **Problema:** Si apre dopo solo 5 failures
- **Causa:** Ollama è lento ma funzionante, non down
- **Impatto:** 7 test generati con Mock invece di Qwen (inutili)
- **Fix:** Aumentato threshold a 10 failures

### **2. Timeout Troppo Corti**

- **Problema:** Timeout di 3 minuti troppo corti per test lunghi
- **Causa:** Test complessi richiedono più tempo
- **Impatto:** Timeout frequenti anche se Ollama funziona
- **Fix:** Aumentato a 10 minuti (già fatto, ma processo corrente usa vecchio codice)

### **3. Ollama Potrebbe Essere Sovraccarico**

- **Problema:** Ollama risponde ma va in timeout su richieste lunghe
- **Possibili cause:**
  - Modello troppo grande per RAM disponibile
  - CPU sovraccarica
  - Richieste troppo grandi (4000 tokens)
- **Fix:** Ridotto max_tokens a 2000 (già fatto)

### **4. Circuit Breaker Non Si Resetta**

- **Problema:** Una volta aperto, rimane aperto per tutti i test successivi
- **Causa:** Timeout di 60s prima di tentare half-open
- **Impatto:** Tutti i test dopo il 5° fallimento usano Mock
- **Fix:** Migliorare logica di recovery

---

## ✅ FIX APPLICATI

### **1. Circuit Breaker Threshold**

```python
# Prima: 5 failures → OPEN
# Dopo: 10 failures → OPEN
circuit_breaker_failure_threshold: int = 10
```

### **2. Timeout HTTP**

```python
# Prima: 180s (3 minuti)
# Dopo: 600s (10 minuti)
timeout=600.0
```

### **3. Max Tokens**

```python
# Prima: 4000 tokens
# Dopo: 2000 tokens
max_tokens=2000
```

---

## 🔍 DIAGNOSTICA NECESSARIA

### **Verificare Ollama:**

```bash
# Verifica Ollama risponde
curl http://localhost:11434/api/tags

# Test generazione semplice
curl -X POST http://localhost:11434/api/generate \
  -d '{"model":"qwen2.5:latest","prompt":"test","stream":false}'

# Verifica risorse
ps aux | grep ollama
```

### **Possibili Problemi:**

1. **RAM insufficiente** → Modello troppo grande
2. **CPU sovraccarica** → Troppe richieste simultanee
3. **Modello corrotto** → Reinstallare modello
4. **Configurazione Ollama** → Verificare settings

---

## 🎯 PROSSIMI PASSI

1. ✅ Fix circuit breaker threshold (10 invece di 5)
2. ✅ Fix timeout (10 min invece di 3)
3. ✅ Fix max tokens (2000 invece di 4000)
4. 🔍 Investigare perché Ollama va in timeout
5. 🔧 Migliorare recovery del circuit breaker
6. 📊 Monitorare prossimo run

---

## 💡 RACCOMANDAZIONI

### **Se Ollama Continua ad Andare in Timeout:**

1. **Ridurre dimensione modello:**

   ```bash
   ollama pull qwen2.5:3b  # Più piccolo, più veloce
   ```

2. **Aumentare RAM disponibile:**
   - Chiudere altre applicazioni
   - Aumentare swap se necessario

3. **Ridurre parallelismo:**
   - Generare un test alla volta invece di batch

4. **Usare modello più piccolo:**
   - `qwen2.5:3b` invece di `qwen2.5:latest`

---

## ✅ RISULTATO ATTESO

Con i fix applicati:

- ✅ Circuit breaker più tollerante (10 failures)
- ✅ Timeout più lunghi (10 minuti)
- ✅ Richieste più piccole (2000 tokens)
- ✅ Meno fallimenti
- ✅ Più test generati con Qwen
