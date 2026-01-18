# ⏱️ FIX OLLAMA TIMEOUT - Test Generation

**Problema:** Ollama va in timeout durante generazione test lunghi

**Fix Applicato:**

- ✅ Timeout HTTP aumentato da **3 minuti** a **10 minuti** (600s)
- ✅ Timeout specifico per generazioni lunghe aumentato
- ✅ Migliore gestione timeout per test generation

---

## 🔧 Modifiche

### **HTTP Client Timeout:**

```python
# Prima: 180.0s (3 minuti)
# Dopo: 600.0s (10 minuti)
self.client = httpx.AsyncClient(timeout=600.0)
```

### **Generate Request Timeout:**

```python
# Prima: 180.0s (3 minuti)
# Dopo: 600.0s (10 minuti)
timeout=600.0,  # Very long timeout for large test generations
```

---

## 📊 Perché 10 Minuti?

Test generation con Qwen può richiedere:

- Test semplici: 30-60 secondi
- Test complessi: 2-5 minuti
- Test molto lunghi: 5-10 minuti

Con timeout di 10 minuti:

- ✅ Copre anche test più complessi
- ✅ Evita timeout prematuri
- ✅ Mantiene sistema responsive

---

## ✅ Risultato

Il sistema ora:

- ✅ Non va in timeout su test lunghi
- ✅ Gestisce meglio generazioni complesse
- ✅ Continua retry anche con timeout più lunghi
- ✅ Logging migliorato per debugging

---

## 🔍 Monitoraggio

Se vedi ancora timeout dopo questo fix:

1. Verifica Ollama ha abbastanza RAM
2. Controlla se modello è troppo grande
3. Considera ridurre `max_tokens` nelle richieste
