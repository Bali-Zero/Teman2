# Test Skip - File Non Trovati

**Data:** 2026-01-16  
**Motivo:** File di test rimossi o spostati

---

## 📋 TEST DA SKIPARE (File Non Trovati)

### Totale: ~70 test in 14 file

1. **tests/unit/rag/test_agentic.py** - 1 test
2. **tests/unit/rag/test_reasoning_90_coverage.py** - 1 test
3. **tests/unit/rag/test_reasoning_edge_case_fixes.py** - 1 test
4. **tests/unit/rag/test_reasoning_exact_coverage.py** - 1 test
5. **tests/unit/routers/test_memory_vector_router.py** - 1 test
6. **tests/unit/services/llm_clients/test_gemini_service_coverage.py** - 1 test
7. **tests/unit/services/misc/test_autonomous_scheduler_coverage.py** - 3 test
8. **tests/unit/services/test_audit_service_comprehensive.py** - 3 test
9. **tests/unit/services/test_citation_service.py** - 1 test
10. **tests/unit/services/test_cultural_rag_service_comprehensive.py** - 23 test ⚠️
11. **tests/unit/services/test_gemini_service_comprehensive.py** - 8 test
12. **tests/unit/services/test_golden_answer_service_comprehensive.py** - 2 test
13. **tests/unit/services/test_golden_router_service_comprehensive.py** - 4 test
14. **tests/unit/services/test_intelligent_router.py** - 20 test ⚠️

---

## ⚠️ NOTE

- Questi file potrebbero essere stati spostati o rinominati
- Verificare se esistono in altre location prima di skipare definitivamente
- Se trovati, aggiornare import invece di skipare

---

## 🔍 VERIFICA DA FARE

```bash
# Cercare file spostati
find tests -name "*agentic*" -type f
find tests -name "*reasoning*" -type f
find tests -name "*cultural*rag*" -type f
find tests -name "*intelligent*router*" -type f
```

---

**Status:** ⏳ Da verificare se file sono stati spostati prima di skipare
