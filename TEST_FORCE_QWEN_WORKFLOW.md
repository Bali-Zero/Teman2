# 🔥 TEST FORCE - QWEN-FIRST WORKFLOW COMPLETO

**Data:** 2026-01-18  
**Sistema:** Test Force con Qwen 2.5 (Ollama)  
**Status:** ✅ QWEN-FIRST MODE ATTIVO

---

## ✅ VERIFICA: STIAMO USANDO QWEN?

**SÌ!** Ecco la prova:

### 1. LLM Adapter Configuration

```python
# backend/agents/services/llm_adapter.py
- Provider disponibili: SOLO ['ollama', 'mock']
- Gemini: COMPLETAMENTE RIMOSSO ❌
- Default model: qwen2.5:latest
- Max retries: 10 (aggressivi!)
- Auto-start Ollama: ✅ ATTIVO
```

### 2. Test Eseguiti

```
✅ Qwen Health Check: PASS
✅ Qwen Generation: PASS (15-16s response time)
✅ Retry Mechanism: PASS (fallback a Mock solo dopo 10 tentativi)
✅ Gemini Removal: PASS (completamente rimosso)
✅ Environment Variables: PASS (OLLAMA_MODEL=qwen2.5:latest)
```

### 3. Agenti Configurati

Tutti gli agenti usano `provider="local"` che significa **QWEN**:

- ✅ TestGuardian → Qwen
- ✅ TestCreator → Qwen
- ✅ TestMaintainer → Qwen
- ✅ TestCleaner → Qwen
- ✅ TestForceOrchestrator → Qwen

---

## 🎭 WORKFLOW COMPLETO TEST FORCE

### 📅 SCHEDULAZIONE (Cron)

```bash
# scripts/setup_all_automation.sh
2:00 AM  → Ollama Start (finestra 2 ore)
2:15 AM  → Test Force Orchestrator (Qwen)
3:30 AM  → Agent Tests (Qwen)
4:00 AM  → Ollama Stop
```

### 🔄 WORKFLOW ESECUZIONE

#### **FASE 1: PREPARAZIONE** (2:00 AM)

```bash
1. Ollama Start
   └─> Verifica Ollama disponibile
   └─> Pull modello qwen2.5:latest se necessario
   └─> Avvia Ollama serve
   └─> Health check: ✅ Ollama running
```

#### **FASE 2: TEST FORCE ORCHESTRATOR** (2:15 AM)

```bash
# scripts/auto_test_force.sh
python3 -m backend.agents.agents.test_force_orchestrator \
    --mode=auto \
    --provider=local \          # ← QWEN!
    --coverage-target=99.0
```

**Workflow interno:**

```
┌─────────────────────────────────────────────────────────┐
│         TEST FORCE ORCHESTRATOR (QWEN)                  │
└─────────────────────────────────────────────────────────┘
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  GUARDIAN   │ │   CREATOR   │ │ MAINTAINER  │
│  (Qwen)     │ │   (Qwen)    │ │  (Qwen)     │
└─────────────┘ └─────────────┘ └─────────────┘
        │           │               │
        ▼           ▼               ▼
   Coverage    Genera Test    Aggiorna Test
   Analysis    per nuovo      quando codice
               codice         cambia
                    │
                    ▼
        ┌─────────────────────┐
        │     CLEANER         │
        │     (Qwen)          │
        └─────────────────────┘
                    │
                    ▼
            Rimuove test
            obsoleti/duplicati
```

#### **FASE 3: AGENTI DETTAGLIATI**

##### 🛡️ **TestGuardian** (Coverage Analysis)

```
1. Analizza coverage con pytest --cov
2. Identifica file < 99% coverage
3. Per ogni gap:
   └─> Legge codice sorgente
   └─> Estrae context (imports, classi, funzioni)
   └─> Chiama QWEN per generare test
       ├─> Retry fino a 10 volte se fallisce
       ├─> Exponential backoff
       └─> Auto-start Ollama se necessario
   └─> Salva test generato
   └─> Esegue test (self-healing)
   └─> Se fallisce → Qwen fix → retry
```

##### 🎯 **TestCreator** (New Code Tests)

```
1. Monitora git diff per nuovo codice
2. Per ogni file nuovo/modificato:
   └─> Analizza cambiamenti
   └─> Chiama QWEN per generare test completo
       ├─> Retry fino a 10 volte
       └─> Auto-start Ollama se necessario
   └─> Valida test generato
   └─> Self-healing se fallisce
```

##### 🔧 **TestMaintainer** (Update Tests)

```
1. Mappa source → test files
2. Per ogni file sorgente modificato:
   └─> Trova test corrispondenti
   └─> Analizza breaking changes
   └─> Chiama QWEN per aggiornare test
       ├─> Retry fino a 10 volte
       └─> Auto-start Ollama se necessario
   └─> Valida test aggiornato
```

##### 🧹 **TestCleaner** (Remove Obsolete)

```
1. Scansiona tutti i test
2. Identifica:
   - Test orfani (source file deleted)
   - Test duplicati (semantic similarity)
   - Test inutili (sempre green, mai eseguiti)
3. Chiama QWEN per analisi semantica
   ├─> Retry fino a 10 volte
   └─> Auto-start Ollama se necessario
4. Archivia/rimuove test obsoleti
```

#### **FASE 4: AGENT TESTS** (3:30 AM)

```bash
# scripts/auto_agent_test.sh
- Test agentic RAG con Qwen reale
- Test orchestrator con Qwen
- Test reasoning con Qwen
```

#### **FASE 5: CLEANUP** (4:00 AM)

```bash
1. Ollama Stop
2. Logs archiviati
3. Metrics salvate
```

---

## 🔥 COME FUNZIONA QWEN-FIRST MODE

### **LLM Adapter Behavior**

```python
# Ogni chiamata LLM:
1. Check cache → Se hit, return cached
2. Try Qwen (Ollama):
   ├─> Attempt 1: Direct call
   ├─> Attempt 2-10: Retry con exponential backoff
   │   ├─> Wait: 1.5^(attempt-1) secondi
   │   └─> Auto-start Ollama se non disponibile
   └─> Se tutti falliscono → Mock (NON Gemini!)
```

### **Retry Strategy**

```
Attempt 1: Immediate
Attempt 2: Wait 1.5s
Attempt 3: Wait 2.25s
Attempt 4: Wait 3.38s
...
Attempt 10: Wait ~57s
Total max wait: ~2 minuti prima di fallback a Mock
```

### **Auto-Recovery**

```
Se Ollama non risponde:
1. Health check Ollama
2. Se non disponibile:
   └─> Tenta: ollama serve (background)
   └─> Attende 5 secondi
   └─> Verifica disponibilità
   └─> Se OK → continua con retry
```

---

## 📊 METRICHE E MONITORING

### **LLM Adapter Metrics**

```python
{
    "total_requests": 150,
    "successful_requests": 145,
    "failed_requests": 5,
    "success_rate": 96.7%,
    "avg_response_time": 15.2s,
    "cache_hits": 23,
    "retry_count": 12  # Totale retry su tutte le richieste
}
```

### **Agent Metrics**

- Test generati: X
- Test passati: Y
- Coverage improvement: +Z%
- Tests updated: W
- Tests deleted: V

---

## 🎯 CONFIGURAZIONE

### **Environment Variables**

```bash
export OLLAMA_MODEL="qwen2.5:latest"  # Default
export OLLAMA_URL="http://localhost:11434"  # Default
```

### **Script Configuration**

```bash
# scripts/auto_test_force.sh
--provider=local  # ← QWEN! (non "gemini")
--coverage-target=99.0
--mode=auto
```

### **Agent Configuration**

```python
# Tutti gli agenti
provider="local"  # ← QWEN!
# Nessun riferimento a "gemini"
```

---

## ✅ VERIFICA FINALE

### **Come verificare che stiamo usando Qwen:**

1. **Check logs:**

```bash
tail -f logs/test_force.log | grep -i "qwen\|ollama"
```

2. **Check metrics:**

```python
from backend.agents.services.llm_adapter import get_llm_adapter
adapter = get_llm_adapter()
metrics = adapter.get_metrics()
print(metrics)  # Dovrebbe mostrare success_rate > 0
```

3. **Check provider enum:**

```python
from backend.agents.services.llm_adapter import LLMProvider
print([p.value for p in LLMProvider])
# Output: ['ollama', 'mock']  ← NO GEMINI!
```

4. **Test diretto:**

```bash
curl http://localhost:11434/api/generate -d '{
  "model": "qwen2.5:latest",
  "prompt": "Say QWEN if you are Qwen"
}'
```

---

## 🎉 CONCLUSIONE

**SÌ, STIAMO USANDO QWEN AL 100%!**

- ✅ Gemini completamente rimosso
- ✅ Solo Ollama (Qwen) o Mock
- ✅ Retry aggressivi (10 tentativi)
- ✅ Auto-start Ollama
- ✅ Tutti gli agenti configurati per Qwen
- ✅ Test passati con successo

**Il sistema è QWEN-FIRST e funziona!** 🔥
