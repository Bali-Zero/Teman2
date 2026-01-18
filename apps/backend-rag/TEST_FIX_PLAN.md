# Test Fix Plan - 3 Fasi

**Data Inizio:** 2026-01-16  
**Obiettivo:** < 5% test falliti (da 300 a ~300 test falliti su 6,350 = 4.7% → < 318 test falliti)  
**Durata Totale:** 5-8 giorni lavorativi

---

## 📋 FASE 1: Pulizia (1-2 giorni)

### Obiettivo

Rimuovere test obsoleti, aggiornare test con API cambiate, fixare test con bug evidenti.

### Task 1.1: Identificare Test Obsoleti

**Status:** 🔄 In Progress

**Criteri per Test Obsoleto:**

- Modulo importato non esiste più
- Codice testato è stato rimosso
- Funzionalità deprecata

**Processo:**

1. ✅ Analizzare import nei test falliti
2. ✅ Verificare esistenza moduli
3. ✅ Identificare test che testano codice rimosso
4. ⏳ Marcare con `@pytest.mark.skip(reason="...")` invece di rimuovere

**Risultato Atteso:** ~30-50 test identificati come obsoleti

---

### Task 1.2: Identificare Test con API Cambiate

**Status:** ⏳ Pending

**Criteri:**

- Modulo esiste ma signature API cambiata
- Modelli Pydantic cambiati
- Endpoint modificati

**Processo:**

1. ⏳ Confrontare signature attuali con quelle nei test
2. ⏳ Identificare modelli Pydantic cambiati
3. ⏳ Verificare endpoint modificati

**Risultato Atteso:** ~100-150 test identificati con API cambiate

---

### Task 1.3: Identificare Test con Bug Evidenti

**Status:** ⏳ Pending

**Criteri:**

- Assertion errate
- Setup incompleto
- Mock mal configurati

**Processo:**

1. ⏳ Analizzare assertion nei test
2. ⏳ Verificare setup delle fixture
3. ⏳ Controllare configurazione mock

**Risultato Atteso:** ~20-30 test identificati con bug evidenti

---

### Task 1.4: Rimuovere/Skip Test Obsoleti

**Status:** ⏳ Pending

**Processo:**

1. ⏳ Per ogni test obsoleto identificato:
   - Verificare che codice sia davvero rimosso
   - Aggiungere `@pytest.mark.skip(reason="Module removed: ...")`
   - Documentare in commento quando è stato rimosso

**Esempio:**

```python
@pytest.mark.skip(reason="Module removed: backend.core.plugins was refactored in 2026-01")
def test_plugins_init_exports():
    """Test removed - module no longer exists"""
    pass
```

**Risultato Atteso:** ~30-50 test skipped

---

### Task 1.5: Aggiornare Test con API Cambiate

**Status:** ⏳ Pending

**Processo:**

1. ⏳ Per ogni test con API cambiata:
   - Verificare nuova signature API
   - Aggiornare import se necessario
   - Aggiornare chiamate API
   - Aggiornare modelli Pydantic
   - Aggiornare assertion se necessario
   - Documentare cambiamento: `# Updated 2026-01-16: API changed`

**Risultato Atteso:** ~100-150 test aggiornati

---

### Task 1.6: Fixare Test con Bug Evidenti

**Status:** ⏳ Pending

**Processo:**

1. ⏳ Per ogni test con bug evidente:
   - Fixare assertion errate
   - Completare setup fixture
   - Fixare configurazione mock
   - Documentare fix: `# Fixed 2026-01-16: assertion corrected`

**Risultato Atteso:** ~20-30 test fixati

---

## 📋 FASE 2: Fix Critici (3-5 giorni)

### Obiettivo

Identificare e fixare test critici che testano funzionalità core e rivelano bug reali.

### Task 2.1: Identificare Test Critici

**Status:** ⏳ Pending

**Criteri per Test Critico:**

- Testa funzionalità core (autenticazione, database, LLM gateway)
- Testa API pubbliche (router endpoints)
- Testa error handling critico
- Testa sicurezza

**Moduli Critici Identificati:**

1. 🔴 **LLM Gateway** (38 test) - Core functionality
2. 🔴 **CRM Clients Router** (54 test) - Public API
3. 🔴 **Identity Service** (12 test) - Authentication
4. 🔴 **Error Handling** (32 test) - Resilience
5. 🔴 **Team Activity Router** (41 test) - Public API

**Risultato Atteso:** ~150-200 test critici identificati

---

### Task 2.2: Fixare Test che Rivelano Bug Reali

**Status:** ⏳ Pending

**Processo:**

1. ⏳ Eseguire test critici per vedere errori reali
2. ⏳ Categorizzare: bug reale vs test obsoleto
3. ⏳ Per bug reali:
   - Creare issue/ticket
   - Fixare bug nel codice
   - Verificare test passa
   - Documentare: `# Fixed bug #XXX: ...`

**Risultato Atteso:** ~30-50 bug reali identificati e fixati

---

### Task 2.3: Aggiornare Test per Nuove Signature API

**Status:** ⏳ Pending

**Processo:**

1. ⏳ Per ogni test critico con API cambiata:
   - Verificare nuova signature
   - Aggiornare test
   - Verificare test passa
   - Documentare: `# Updated 2026-01-16: API signature changed`

**Risultato Atteso:** ~100-150 test critici aggiornati

---

## 📋 FASE 3: Automazione (1 giorno)

### Obiettivo

Aggiungere test failure tracking in CI, bloccare merge se test critici falliscono, generare report automatico.

### Task 3.1: Aggiungere Test Failure Tracking in CI

**Status:** ⏳ Pending

**Processo:**

1. ⏳ Verificare configurazione CI esistente
2. ⏳ Aggiungere step per eseguire test suite
3. ⏳ Aggiungere step per generare report test falliti
4. ⏳ Salvare report come artifact

**File da Creare/Modificare:**

- `.github/workflows/test.yml` (se GitHub Actions)
- `ci/test.sh` (script per eseguire test)

**Risultato Atteso:** CI esegue test e genera report

---

### Task 3.2: Bloccare Merge se Test Critici Falliscono

**Status:** ⏳ Pending

**Processo:**

1. ⏳ Identificare test critici (da Fase 2)
2. ⏳ Creare marker pytest per test critici: `@pytest.mark.critical`
3. ⏳ Configurare CI per eseguire solo test critici su PR
4. ⏳ Bloccare merge se test critici falliscono

**Esempio:**

```python
@pytest.mark.critical
def test_create_client_success():
    """Critical test - blocks merge if fails"""
    pass
```

**Risultato Atteso:** Merge bloccato se test critici falliscono

---

### Task 3.3: Generare Report Automatico Test Falliti

**Status:** ⏳ Pending

**Processo:**

1. ⏳ Creare script per generare report: `scripts/generate_test_report.py`
2. ⏳ Report deve includere:
   - Numero totale test
   - Numero test falliti
   - Lista test falliti con categoria
   - Trend (miglioramento/peggioramento)
3. ⏳ Eseguire script in CI dopo test suite
4. ⏳ Salvare report come artifact

**Risultato Atteso:** Report automatico generato ad ogni run CI

---

## 📊 METRICHE DI SUCCESSO

### Obiettivi FASE 1

- ✅ ~30-50 test obsoleti identificati e skipped
- ✅ ~100-150 test con API cambiate identificati
- ✅ ~20-30 test con bug evidenti identificati
- ✅ ~150-230 test fixati/aggiornati

**Risultato:** ~70-120 test falliti rimanenti (da 300)

---

### Obiettivi FASE 2

- ✅ ~150-200 test critici identificati
- ✅ ~30-50 bug reali identificati e fixati
- ✅ ~100-150 test critici aggiornati
- ✅ ~130-200 test critici fixati

**Risultato:** ~50-100 test falliti rimanenti (non critici)

---

### Obiettivo Finale

- ✅ < 5% test falliti (< 318 test su 6,350)
- ✅ 0 test critici falliti
- ✅ CI blocca merge su test critici falliti
- ✅ Report automatico generato

**Risultato:** Test suite stabile e mantenibile

---

## 📝 DOCUMENTAZIONE

### Template per Documentare Fix

```python
# Fixed 2026-01-16: Issue #XXX - Description
# Updated 2026-01-16: API signature changed from X to Y
# Skipped 2026-01-16: Module removed - backend.core.plugins refactored
```

### Template per Issue/Ticket

```
Title: Test Failure: [module]::[test_name]

Description:
- Test: [path]
- Error: [error message]
- Category: [obsolete/api_changed/bug_real/test_bug]
- Priority: [high/medium/low]

Fix:
- [description of fix]
- [link to PR/commit]
```

---

## 🚀 PROSSIMI PASSI IMMEDIATI

1. ✅ Completare Task 1.1: Identificare test obsoleti
2. ⏳ Iniziare Task 1.2: Identificare test con API cambiate
3. ⏳ Iniziare Task 1.4: Skip test obsoleti verificati
4. ⏳ Iniziare Task 1.5: Aggiornare test con API cambiate

---

**Status:** 🔄 FASE 1 In Progress  
**Prossimo Task:** Completare identificazione test obsoleti e iniziare skip
