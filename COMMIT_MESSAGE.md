# 📝 COMMIT MESSAGE SUGGERITA

## 🎯 Titolo Commit

```
feat: Unified Test Force System with Qwen System Prompts

- Implement comprehensive unified test coverage system
- Add system prompts for Qwen test generation
- Support multi-component coverage (backend + frontend)
- Add differential coverage analysis vs baseline
- Improve circuit breaker and timeout handling
```

## 📋 Dettagli

### **Nuove Features:**
- ✅ Unified Coverage Collector (Backend + Frontend + Integration)
- ✅ Differential Coverage Analyzer (delta vs baseline)
- ✅ Unified Test Force Orchestrator (complete system testing)
- ✅ Qwen System Prompts configuration (362 lines detailed prompts)
- ✅ System prompt support in LLM Adapter

### **Miglioramenti:**
- ✅ Circuit breaker threshold: 5 → 10 failures
- ✅ Recovery timeout: 60s → 30s
- ✅ HTTP timeout: 3min → 10min
- ✅ Max tokens: 4000 → 2000
- ✅ Coverage collection timeouts increased
- ✅ Better error handling and partial results

### **File Creati:**
- `apps/backend-rag/backend/agents/services/unified_coverage_collector.py`
- `apps/backend-rag/backend/agents/services/differential_coverage_analyzer.py`
- `apps/backend-rag/backend/agents/agents/unified_test_force_orchestrator.py`
- `apps/backend-rag/backend/agents/config/qwen_system_prompts.py`
- `scripts/unified_test_force.sh`
- `scripts/show_unified_results.sh`

### **Documentazione:**
- `UNIFIED_TEST_SYSTEM.md`
- `COME_USARE_QWEN.md`
- `COME_MODIFICARE_SYSTEM_PROMPT.md`
- `CONSIGLI_PRATICI.md`
- `SYSTEM_PROMPT_PREPARATO.md`

---

## 🚀 Deploy Necessario?

**NO** - Il sistema è completamente locale:
- ✅ Ollama/Qwen locale
- ✅ Nessun servizio esterno
- ✅ Nessuna configurazione cloud
- ✅ Tutto funziona in locale

**Solo commit necessario per salvare il lavoro!**
