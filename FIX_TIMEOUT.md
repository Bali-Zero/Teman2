# ⏱️ FIX TIMEOUT - Unified Coverage Collector

**Problema:** Timeout di 10 minuti troppo corto per backend-rag

**Fix Applicato:**

- ✅ Timeout aumentato a **30 minuti** per backend-rag
- ✅ Timeout aumentato a **20 minuti** per mouth-frontend
- ✅ Gestione migliorata: usa coverage esistenti se generazione va in timeout
- ✅ Logging migliorato per timeout

---

## 🔧 Modifiche

### **Backend Coverage:**

```python
# Timeout dinamico basato su componente
timeout = 1800.0 if component_name == "backend-rag" else 600.0
```

### **Frontend Coverage:**

```python
# Timeout dinamico per progetti grandi
timeout = 1200.0 if component_name == "mouth-frontend" else 600.0
```

### **Fallback su Coverage Esistenti:**

Se la generazione va in timeout, il sistema:

1. Cerca coverage.json esistente
2. Lo usa se disponibile
3. Logga warning ma continua

---

## 📊 Timeout per Componente

| Componente     | Timeout | Motivo                      |
| -------------- | ------- | --------------------------- |
| backend-rag    | 30 min  | Molti test, progetto grande |
| mouth-frontend | 20 min  | Progetto frontend grande    |
| Altri backend  | 10 min  | Progetti più piccoli        |
| Altri frontend | 10 min  | Progetti più piccoli        |

---

## ✅ Risultato

Il sistema ora:

- ✅ Non va in timeout su backend-rag
- ✅ Usa coverage esistenti se generazione fallisce
- ✅ Continua con altri componenti anche se uno fallisce
- ✅ Logging chiaro per debugging
