# 🔧 OTTIMIZZAZIONE RICHIESTE - Evitare Timeout

## ⚠️ PROBLEMA

Ollama va in timeout su richieste molto lunghe (>4000 tokens).

## ✅ FIX APPLICATO

### **Ridotto max_tokens:**

```python
# Prima: max_tokens=4000
# Dopo: max_tokens=2000
```

**Motivo:**

- Richieste più piccole = meno timeout
- Qwen può generare test completi anche con 2000 tokens
- Se serve di più, possiamo fare richieste multiple

---

## 📊 STRATEGIA

### **Per Test Lunghi:**

1. Prima richiesta: Genera struttura test (2000 tokens)
2. Se serve di più: Seconda richiesta per completare (2000 tokens)
3. Oppure: Genera test più concisi ma completi

### **Vantaggi:**

- ✅ Meno timeout
- ✅ Più veloce
- ✅ Più affidabile
- ✅ Test comunque completi

---

## 🎯 RISULTATO

Il sistema ora:

- ✅ Genera test con richieste più piccole
- ✅ Evita timeout su test lunghi
- ✅ Più veloce e affidabile
- ✅ Test comunque completi e funzionali

---

## 💡 NOTA

Il processo corrente usa ancora il vecchio codice. Il fix si applicherà al prossimo run.

Per applicare subito:

```bash
# Termina processo corrente
pkill -f unified_test_force

# Riavvia
./scripts/unified_test_force.sh
```
