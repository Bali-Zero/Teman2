# 🌐 UNIFIED TEST SYSTEM - Documentazione Completa

## 🎯 OBIETTIVO

Sistema completo per testare **TUTTO** il sistema Nuzantara:

- Backend (Python/FastAPI)
- Frontend (TypeScript/React/Next.js)
- Integration (E2E, API)
- WhatsApp/Telegram

Calcola coverage complessivo e differenziale.  
Genera, salva ed esegue test automaticamente per aumentare la coverage.

---

## 🚀 COME FUNZIONA

### **Workflow Completo:**

1. **Step 1: Raccolta Coverage**
   - Raccoglie coverage da tutti i componenti
   - Backend: Python/pytest
   - Frontend: TypeScript/Vitest
   - Genera report unificato

2. **Step 2: Analisi Differenziale**
   - Confronta con baseline salvata
   - Identifica regressioni e miglioramenti
   - Calcola delta coverage

3. **Step 3: Identificazione Gap Critici**
   - Identifica file con coverage bassa
   - Priorità: coverage più bassa prima
   - Limita a top N gap per componente

4. **Step 4: Generazione Test** ⭐
   - Genera test con Qwen (Ollama)
   - **Salva test in file** (`apps/{component}/tests/unit/test_*.py`)
   - **Esegue test** per verificare che funzionino
   - Conta test passati/falliti

5. **Step 5: Ricalcolo Coverage** ⭐
   - Ricalcola coverage dopo i test generati
   - Mostra aumento coverage
   - Aggiorna report finale

---

## 📊 RISULTATI

### **Report JSON:**

```json
{
  "coverage_report": {
    "overall_coverage": 44.5,
    "components": {...}
  },
  "test_generation": {
    "tests_generated": 15,
    "tests_passed": 12,
    "tests_failed": 3,
    "tests_by_component": {...}
  },
  "coverage_after_tests": {
    "overall_coverage": 45.2,
    "components": {...}
  }
}
```

### **Log Output:**

```
✅ Test salvato: apps/bali-intel-scraper/tests/unit/test_article_deep_enricher.py
✅ Test passato: test_article_deep_enricher.py
📊 Step 5: Ricalcolo coverage dopo test generati...
✅ Coverage aggiornata: 45.2% (era 44.5%)
```

---

## 🔧 COME USARE

### **Esecuzione Completa:**

```bash
./scripts/unified_test_force.sh
```

### **Monitoraggio Live:**

```bash
tail -f logs/unified_test_force.log | grep --line-buffered -E "Step [1-5]|Generating test|salvato|passato|Coverage aggiornata"
```

### **Vedi Risultati:**

```bash
./scripts/show_unified_results.sh
```

---

## 📁 FILE GENERATI

### **Test Salvati:**

- Backend: `apps/{component}/tests/unit/test_{file}.py`
- Frontend: `apps/{component}/tests/{file}.test.ts`

### **Report:**

- `logs/unified_coverage_report.json` - Report completo JSON
- `logs/unified_test_force.log` - Log dettagliati

---

## ⚙️ CONFIGURAZIONE

### **System Prompts:**

- Backend: `apps/backend-rag/backend/agents/config/qwen_system_prompts.py`
- Frontend: `TEST_GENERATION_SYSTEM_PROMPT_FRONTEND`

### **Parametri:**

- `--max-tests=5` - Max test per componente
- `--generate-tests` - Abilita generazione test
- `--save-baseline` - Salva baseline per confronti futuri

---

## 🎯 FEATURES

### **✅ Implementato:**

- ✅ Raccolta coverage unificata (Backend + Frontend)
- ✅ Analisi differenziale vs baseline
- ✅ Generazione test con Qwen
- ✅ **Salvataggio test in file** ⭐
- ✅ **Esecuzione test automatica** ⭐
- ✅ **Ricalcolo coverage dopo test** ⭐
- ✅ Report JSON completo
- ✅ System prompts configurabili
- ✅ Circuit breaker e retry logic
- ✅ Fallback a mock se Qwen non disponibile

### **🔄 In Sviluppo:**

- 🔄 Integrazione Multi-AI (Claude Max per analisi)
- 🔄 Dashboard monitoring
- 🔄 Notifiche quando coverage aumenta

---

## 📊 COVERAGE TARGET

- **Backend:** 80%+ coverage
- **Frontend:** 70%+ coverage
- **Overall:** 75%+ coverage

---

## 🔍 TROUBLESHOOTING

### **Test non vengono salvati:**

- Verifica permessi scrittura in `apps/{component}/tests/`
- Controlla log per errori: `grep "salvato" logs/unified_test_force.log`

### **Test falliscono:**

- Verifica dipendenze installate
- Controlla import nel codice generato
- Vedi log dettagliati: `tail -100 logs/unified_test_force.log`

### **Coverage non aumenta:**

- Verifica che test vengano eseguiti: `grep "passato\|fallito" logs/unified_test_force.log`
- Controlla che test coprano codice mancante
- Verifica report: `cat logs/unified_coverage_report.json | python3 -m json.tool`

---

## 📚 DOCUMENTAZIONE CORRELATA

- `COMANDI_LIVE.md` - Comandi per monitoraggio live
- `VERIFICA_PIU_TARDI.md` - Comandi per verifica post-esecuzione
- `FIX_TEST_SALVATI_ESEGUITI.md` - Dettagli implementazione
- `CONFIGURAZIONE_CLAUDE_MAX.md` - Configurazione AI principale

---

**Sistema completo e funzionante!** 🚀
