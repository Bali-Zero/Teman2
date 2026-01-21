# 📋 Piano Risoluzione TODO/FIXME Critici

**Data:** 2026-01-21

---

## 🔴 TODO Critici Identificati

### 1. Pytest Configuration Issues

**File:** `apps/backend-rag/CLAUDE.md`
**Linee:** 166, 1376

**Problema:**

```
TODO: Fix pytest configuration in future session
TODO: Fix pytest configuration for pre-push hook
```

**Analisi:**

- ✅ `pytest.ini` presente in `apps/backend-rag/`
- ✅ `pytest.ini` presente in `apps/backend-rag/backend/`
- ✅ Pre-push hook configurato (`.husky/pre-push`)
- ⚠️ Possibile problema di path o PYTHONPATH

**Soluzione:**

1. Verificare che pytest trovi i test correttamente
2. Assicurarsi che PYTHONPATH sia configurato nel pre-push hook
3. Testare esecuzione manuale vs hook

**Status:** 🔄 In Analisi

---

### 2. TypeScript File Corrotto

**File:** `apps/backend-rag/CLAUDE.md:1359`
**Problema:**

```
TODO: Fix file TypeScript corrotto, poi run Sentinel
```

**Analisi:**

- File TypeScript corrotto non identificato nel report
- Potrebbe essere stato già risolto
- Sentinel è un tool di analisi statica

**Azione:**

1. Cercare file TypeScript con errori di sintassi
2. Verificare con TypeScript compiler
3. Eseguire Sentinel dopo fix

**Status:** 🔍 Da Verificare

---

## ✅ TODO Risolti

### Import Wildcard

- ✅ `apps/backend-rag/backend/app/main.py` - Sostituito con import espliciti
- ✅ `apps/backend-rag/backend/tests/unit/llm/test_base.py` - Sostituito
- ✅ `apps/backend-rag/backend/tests/unit/llm/test_provider_registry.py` - Sostituito

---

## 📝 TODO Non Critici (Da Gestire)

### Documentazione

- Migliorare documentazione struttura (✅ Creato `PROJECT_STRUCTURE.md`)
- Aggiornare README principali

### Testing

- Aumentare coverage backend (attuale ~0.67%, target 80%)
- Aggiungere test E2E per workflow critici

### Performance

- Ottimizzare query database lente
- Implementare caching per endpoint frequenti

---

## 🎯 Priorità

1. **Alta:** Risolvere pytest configuration
2. **Media:** Verificare file TypeScript corrotto
3. **Bassa:** Migliorare documentazione e coverage

---

**Prossimo Step:** Testare pytest configuration e risolvere problemi identificati.
