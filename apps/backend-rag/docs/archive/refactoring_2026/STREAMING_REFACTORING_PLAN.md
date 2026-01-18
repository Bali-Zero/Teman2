# Streaming Refactoring Plan (Fase 2)

**Data:** 2026-01-15  
**Obiettivo:** Refactorizzare completamente `stream_query()` per eliminare duplicazione

---

## 📊 ANALISI ATTUALE

### Duplicazione Identificata

`stream_query()` duplica ~70% della logica di `process_query()`:

1. **Context Loading** - Duplicato (righe 337-383 vs orchestrator_context.py)
2. **Query Gates** - Duplicato (righe 389-469 vs query_gates.py)
3. **Entity Extraction** - Duplicato (righe 595-604 vs orchestrator_core.py)
4. **Cache Check** - Duplicato (righe 606-636 vs orchestrator_core.py)
5. **Intent Classification** - Duplicato (righe 638-657 vs orchestrator_routing.py)
6. **KG Retrieval** - Duplicato (righe 670-680 vs orchestrator_core.py)
7. **System Prompt Building** - Duplicato (righe 682-689 vs orchestrator_core.py)

**Totale duplicazione:** ~450 righe su 600 righe di stream_query()

---

## 🎯 PIANO REFACTORING

### Step 1: Creare `orchestrator_streaming_core.py`

**Responsabilità:**

- Coordina streaming logic usando moduli specializzati
- Gestisce event generation e validation
- Coordina ReAct loop streaming
- Gestisce follow-up questions generation
- Memory persistence dopo stream

**Target:** ~300-400 righe

### Step 2: Estrarre Logica Comune

**Metodi da creare in OrchestratorCore:**

```python
async def prepare_query_context(
    self, query, user_id, conversation_history, session_id
) -> tuple[dict, list, dict]:
    """Common context preparation for both streaming and non-streaming"""
    # Usa OrchestratorContextManager
    # Ritorna (user_context, optimized_history, extracted_entities)

async def check_gates_and_cache(
    self, query, user_context, history, extracted_entities, start_time
) -> CoreResult | None:
    """Common gate checking and cache lookup"""
    # Usa QueryGates
    # Usa SemanticCache
    # Ritorna CoreResult se gate triggered o cache hit, None altrimenti

async def prepare_react_execution(
    self, query, user_context, history, extracted_entities
) -> tuple[str, bool, AgentState, str]:
    """Common ReAct loop preparation"""
    # Usa OrchestratorRoutingManager
    # Usa EntityExtractionService
    # Usa KGEnhancedRetrieval
    # Ritorna (model_tier, deep_think_mode, state, system_prompt)
```

### Step 3: Refactorizzare `stream_query()`

**Nuova struttura:**

```python
async def stream_query(...) -> AsyncGenerator[dict, None]:
    # 1. Preparazione comune (usa prepare_query_context)
    # 2. Gate checking comune (usa check_gates_and_cache)
    # 3. Se gate/cache hit: stream response usando OrchestratorStreamingManager
    # 4. Altrimenti: prepara ReAct (usa prepare_react_execution)
    # 5. Esegui ReAct loop streaming
    # 6. Processa eventi con OrchestratorStreamingManager
    # 7. Genera follow-up questions
    # 8. Salva memory
```

**Target:** ~200-250 righe (da 600 attuali)

---

## 📋 CHECKLIST REFACTORING

- [ ] Creare `orchestrator_streaming_core.py`
- [ ] Estrarre metodi comuni in `OrchestratorCore`
- [ ] Refactorizzare `stream_query()` per usare moduli
- [ ] Creare test per streaming core
- [ ] Verificare backward compatibility
- [ ] Rimuovere codice duplicato
- [ ] Aggiungere logging appropriato

---

## 🎯 BENEFICI ATTESI

| Metrica                  | Prima | Dopo | Miglioramento |
| ------------------------ | ----- | ---- | ------------- |
| Duplicazione codice      | ~70%  | <5%  | -93%          |
| Righe stream_query       | 600   | ~250 | -58%          |
| Complessità stream_query | 73    | <20  | -73%          |
| Testabilità streaming    | Bassa | Alta | +100%         |

---

**Status:** 📋 Piano definito, pronto per implementazione
