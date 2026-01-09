# 🔍 Analisi Codebase - Aree Poco Chiare e Sporche

**Data Analisi:** 2026-01-09  
**Scope:** Backend (Python) + Frontend (TypeScript/React)

---

## 📊 Executive Summary

Questa analisi identifica aree della codebase che necessitano di refactoring, pulizia o miglioramento strutturale. Le problematiche sono categorizzate per priorità e impatto.

**Metriche Chiave:**
- **File Python > 1000 righe:** 19 file
- **File TypeScript/TSX > 1000 righe:** 8 file
- **TODO/FIXME:** ~1600+ occorrenze
- **Print statements:** 395 occorrenze (dovrebbero essere logging)
- **Exception handlers generici:** 943 occorrenze
- **TypeScript `any`/`@ts-ignore`:** 972 occorrenze

---

## 🔴 PRIORITÀ ALTA - Problemi Critici

### 1. File Troppo Grandi (Code Smell Principale)

#### Backend Python

| File | Righe | Problema | Priorità |
|------|-------|----------|----------|
| `test_orchestrator.py` | 2744 | Test file gigante, difficile da mantenere | 🔴 CRITICA |
| `orchestrator.py` | 1560 | Logica complessa, molte responsabilità | 🔴 CRITICA |
| `intel.py` | 1474 | Router con troppi endpoint, logica mista | 🔴 CRITICA |
| `team_drive_service.py` | 1444 | Servizio con troppe responsabilità | 🔴 CRITICA |
| `reasoning.py` | 1418 | Logica ReAct complessa, difficile da testare | 🔴 CRITICA |
| `prompt_builder.py` | 1314 | Builder pattern troppo complesso | 🟡 ALTA |
| `telegram.py` | 1260 | Router con logica business mista | 🟡 ALTA |
| `metrics.py` | 1224 | Troppe metriche in un file | 🟡 ALTA |
| `qdrant_db.py` | 1180 | Database layer troppo grande | 🟡 ALTA |
| `search_service.py` | 1128 | Servizio con troppe funzionalità | 🟡 ALTA |

**Raccomandazioni:**
- **orchestrator.py**: Dividere in `orchestrator_core.py`, `orchestrator_tools.py`, `orchestrator_react.py`
- **intel.py**: Separare in `intel_router.py`, `intel_service.py`, `intel_models.py`
- **team_drive_service.py**: Estrarre `drive_auth.py`, `drive_operations.py`, `drive_audit.py`
- **reasoning.py**: Separare logica ReAct in moduli più piccoli

#### Frontend TypeScript/React

| File | Righe | Problema | Priorità |
|------|-------|----------|----------|
| `chat/page.tsx` | 1938 | Componente monolitico, troppi stati | 🔴 CRITICA |
| `blueprints/page.tsx` | 1925 | Pagina complessa, logica mista | 🔴 CRITICA |
| `clients/[id]/page.tsx` | 1728 | Dettaglio cliente troppo complesso | 🔴 CRITICA |
| `analytics/page.tsx` | 1363 | Dashboard con troppa logica | 🟡 ALTA |
| `services/[slug]/page.tsx` | 1314 | Pagina servizio troppo grande | 🟡 ALTA |

**Raccomandazioni:**
- **chat/page.tsx**: Estrarre hooks (`useChatState`, `useChatActions`), componenti (`ChatSidebar`, `ChatInput`, `ChatMessages`)
- **blueprints/page.tsx**: Dividere in `BlueprintsList`, `BlueprintEditor`, `BlueprintUploader`
- **clients/[id]/page.tsx**: Separare in `ClientHeader`, `ClientDetails`, `ClientInteractions`, `ClientPractices`

---

### 2. Exception Handling Generico (943 occorrenze)

**Problema:** Troppi `except:` o `except Exception:` che nascondono errori specifici.

**Esempi trovati:**
```python
# ❌ CATTIVO
try:
    result = some_operation()
except:  # Troppo generico
    pass

# ✅ BUONO
try:
    result = some_operation()
except SpecificError as e:
    logger.error(f"Specific error: {e}")
    raise
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise
```

**File con più problemi:**
- `team_drive_service.py`: 24 exception handlers generici
- `intel.py`: 32 exception handlers generici
- `crm_clients.py`: 11 exception handlers generici
- `orchestrator.py`: 13 exception handlers generici

**Raccomandazione:** Refactoring graduale per specificare exception types.

---

### 3. Print Statements invece di Logging (395 occorrenze)

**Problema:** Uso di `print()` invece di logging strutturato.

**File con più print:**
- Migrations: ~100+ print statements
- Scripts: ~200+ print statements
- Test files: ~50+ print statements

**Raccomandazione:**
```python
# ❌ CATTIVO
print(f"Processing {item}")

# ✅ BUONO
logger.info(f"Processing {item}", extra={"item_id": item.id})
```

**Azione:** Usare script `cleanup_prints.py` esistente per conversione automatica.

---

### 4. TypeScript Type Safety Debole (972 occorrenze)

**Problema:** Uso eccessivo di `any`, `@ts-ignore`, `eslint-disable`.

**Distribuzione:**
- `any`: ~800+ occorrenze
- `@ts-ignore`: ~100+ occorrenze
- `eslint-disable`: ~70+ occorrenze

**File problematici:**
- `api.test.ts`: 15 occorrenze
- `cases/__tests__/page.test.tsx`: 19 occorrenze
- `chat.api.test.ts`: 21 occorrenze
- Content articles: ~200+ occorrenze (accettabile per MDX)

**Raccomandazione:** Refactoring graduale per tipizzare correttamente.

---

## 🟡 PRIORITÀ MEDIA - Problemi Strutturali

### 5. Configurazioni Sparse

**Problema:** Variabili d'ambiente accedute direttamente invece di usare `config.py`.

**Esempi:**
```python
# ❌ CATTIVO (trovato in vari file)
api_key = os.getenv("OPENAI_API_KEY")

# ✅ BUONO
from app.core.config import settings
api_key = settings.openai_api_key
```

**File con configurazioni sparse:**
- `intel.py`: `os.getenv("OPENAI_API_KEY")` diretto
- `scripts/`: Molti script con configurazioni hardcoded
- `zoho_oauth_service.py`: Debug logging con configurazioni sparse

**Raccomandazione:** Centralizzare tutte le configurazioni in `config.py`.

---

### 6. File Deprecati Non Rimossi

**File trovati:**
- `apps/mouth/src/app/(workspace)/dashboard/page-old.tsx` (352 righe)
- `apps/backend-rag/backend/app/modules/knowledge/service.py` (marcato DEPRECATED ma ancora presente)

**Raccomandazione:** Rimuovere file deprecati o completare migrazione.

---

### 7. TODO/FIXME Non Risolti (~1600+ occorrenze)

**Categorie:**
- **Implementazione mancante:** ~400+ TODO
- **Debug/Test:** ~600+ DEBUG/TODO
- **Bug noti:** ~50+ BUG/FIXME
- **Ottimizzazioni:** ~200+ TODO

**TODO Critici da risolvere:**
```python
# apps/backend-rag/backend/app/routers/intel.py:929
"agent_status": "active",  # TODO: Implement agent health check

# apps/backend-rag/backend/app/routers/intel.py:1185
# TODO: Implement Qdrant filter support for better performance

# apps/mouth/src/app/(workspace)/intelligence/system-pulse/page.tsx:39
// TODO: Replace with real API call when backend endpoint is ready
```

**Raccomandazione:** Creare issue tracking per TODO critici.

---

### 8. Duplicazioni di Codice

**Aree identificate:**
- **KBLI extraction:** Logica duplicata in `extract_kbli.py`, `verify_kbli.py`, `compare_kbli_pdf_qdrant.py`
- **Error handling:** Pattern simili ripetuti in molti router
- **API client patterns:** Logica simile in vari file API del frontend

**Raccomandazione:** Estrarre utility functions comuni.

---

## 🟢 PRIORITÀ BASSA - Miglioramenti

### 9. Import Non Utilizzati

**Problema:** Import che potrebbero essere rimossi dopo refactoring.

**Raccomandazione:** Usare `ruff check --select F401` per identificare import non utilizzati.

---

### 10. Commenti Obsoleti

**Problema:** Commenti che non riflettono più il codice corrente.

**Esempio trovato:**
```python
# apps/kb/scripts/extract_kbli.py:192-209
# Merge or Skip?
# PP 28 might have same code for different Risk Levels?
# Usually KBLI is unique per row, but in regulation tables,
# one KBLI can have multiple rows for different scales...
# [20+ righe di commenti confusi]
```

**Raccomandazione:** Pulizia periodica dei commenti obsoleti.

---

## 📋 Piano di Azione Prioritizzato

### Fase 1: Criticità Alta (1-2 settimane)
1. ✅ Refactoring `chat/page.tsx` - Dividere in componenti più piccoli
2. ✅ Refactoring `orchestrator.py` - Separare responsabilità
3. ✅ Refactoring `intel.py` - Separare router/service/models
4. ✅ Convertire print() in logging strutturato (script automatico)

### Fase 2: Criticità Media (2-4 settimane)
5. ✅ Specificare exception types invece di generici
6. ✅ Rimuovere file deprecati (`page-old.tsx`, `service.py` se non usato)
7. ✅ Centralizzare configurazioni sparse
8. ✅ Risolvere TODO critici

### Fase 3: Miglioramenti (4-8 settimane)
9. ✅ Migliorare type safety TypeScript (ridurre `any`)
10. ✅ Estrarre duplicazioni di codice
11. ✅ Pulizia commenti obsoleti
12. ✅ Rimuovere import non utilizzati

---

## 🛠️ Strumenti Disponibili

Il progetto ha già strumenti per aiutare:

1. **`scripts/cleanup_prints.py`** - Converte print() in logging
2. **`scripts/auto_fix.py`** - Auto-fix per import organization
3. **`scripts/watchdog.py`** - Code quality monitoring
4. **`ruff`** - Linting Python (già configurato)
5. **`eslint`** - Linting TypeScript (già configurato)

---

## 📈 Metriche di Successo

**Obiettivi:**
- Ridurre file > 1000 righe del 50% (da 19 a ~10)
- Ridurre exception handlers generici del 70% (da 943 a ~280)
- Eliminare tutti i print() statements (da 395 a 0)
- Ridurre `any` TypeScript del 60% (da 800 a ~320)
- Risolvere 80% dei TODO critici

---

## 🔗 File Correlati

- `docs/operations/CODE_QUALITY_STATUS.md` - Status linting
- `docs/AI_ONBOARDING.md` - Standard di codice
- `docs/LIVING_ARCHITECTURE.md` - Architettura sistema

---

**Ultimo aggiornamento:** 2026-01-09
