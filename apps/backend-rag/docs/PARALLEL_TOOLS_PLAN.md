# Piano: Parallel Tool Execution per ReAct Loop

**Data**: 2026-01-27
**Obiettivo**: Ridurre latency da ~85s a ~30s eseguendo tool in parallelo

---

## Problema Attuale

```python
# reasoning.py - Loop SEQUENZIALE
while state.current_step < state.max_steps:  # max_steps = 3
    # Step 1: LLM decide quale tool usare (~15s)
    response = await llm.generate(prompt)

    # Step 2: Esegue UN tool alla volta (~10s)
    tool_result = await execute_tool(tool_name, args)

    # Step 3: Aggiunge observation al context
    state.steps.append(observation)
    state.current_step += 1

# Totale: 3 × (15s + 10s) = 75s + overhead = ~85s
```

---

## Soluzione Proposta: Parallel Tool Execution

### Strategia 1: Multi-Tool per Step (Recommended)

Permettere all'LLM di chiamare **multipli tool in un singolo step**, poi eseguirli in parallelo.

```python
# NUOVO: reasoning.py con parallel execution
async def run_react_step(state: AgentState, llm_gateway: LLMGateway):
    # Step 1: LLM decide TUTTI i tool necessari in un colpo
    response = await llm.generate(
        prompt,
        tool_choice="auto",  # Gemini può chiamare multipli tool
        parallel_tool_calls=True  # Abilita multi-tool response
    )

    # Step 2: Estrai TUTTE le tool calls dalla response
    tool_calls = extract_all_tool_calls(response)  # Lista di tool calls

    # Step 3: Esegui TUTTI i tool in PARALLELO
    if len(tool_calls) > 1:
        results = await asyncio.gather(*[
            execute_tool(tc.name, tc.args) for tc in tool_calls
        ])
    else:
        results = [await execute_tool(tool_calls[0].name, tool_calls[0].args)]

    # Step 4: Combina observations
    combined_observation = combine_observations(results)
    state.steps.append(combined_observation)
```

**Vantaggi**:

- Minimo refactoring (modifica solo il loop interno)
- Backward compatible
- LLM decide cosa parallelizzare

**Svantaggi**:

- Dipende dalla capacità dell'LLM di chiamare multipli tool
- Gemini 2.5 Flash supporta `parallel_tool_calls`? Da verificare.

---

### Strategia 2: Pre-fetch Parallel (Alternative)

Eseguire TUTTI i tool comuni in anticipo, prima del ReAct loop.

```python
# NUOVO: orchestrator.py con pre-fetch
async def run_query(query: str, ...):
    # FASE 1: Pre-fetch parallelo di TUTTI i contesti comuni
    search_task = search_service.search(query, limit=10)
    kg_task = kg_tool.search(query)
    pricing_task = pricing_tool.get_related_prices(query)

    search_results, kg_results, pricing_results = await asyncio.gather(
        search_task, kg_task, pricing_task,
        return_exceptions=True
    )

    # FASE 2: Costruisci context con TUTTI i risultati
    pre_fetched_context = build_context(search_results, kg_results, pricing_results)

    # FASE 3: ReAct loop con context già disponibile (max 1-2 steps)
    # L'LLM ha già tutto il context, deve solo ragionare
    state = AgentState(
        query=query,
        context_gathered=[pre_fetched_context],
        max_steps=1  # Ridotto perché context già disponibile
    )
```

**Vantaggi**:

- Garantito parallelo (non dipende dall'LLM)
- Riduce max_steps a 1
- Più prevedibile

**Svantaggi**:

- Spreca risorse se alcuni tool non servono
- Richiede più refactoring
- Meno flessibile per query che richiedono tool specifici

---

### Strategia 3: Hybrid (Best of Both)

Combina pre-fetch per tool comuni + ReAct per tool specifici.

```python
async def run_query(query: str, ...):
    # FASE 1: Classifica intent per determinare quali tool pre-fetchare
    intent = classify_intent(query)

    # FASE 2: Pre-fetch SOLO i tool probabilmente necessari
    prefetch_tasks = []
    if intent.needs_search:
        prefetch_tasks.append(("search", search_service.search(query)))
    if intent.needs_pricing:
        prefetch_tasks.append(("pricing", pricing_tool.get_prices(query)))
    if intent.needs_kg:
        prefetch_tasks.append(("kg", kg_tool.search(query)))

    # Esegui in parallelo
    prefetch_results = await asyncio.gather(*[t[1] for t in prefetch_tasks])
    prefetch_context = dict(zip([t[0] for t in prefetch_tasks], prefetch_results))

    # FASE 3: ReAct loop con pre-fetched context
    # Se LLM chiama un tool già pre-fetched → usa cache locale
    # Se LLM chiama un tool nuovo → esegui on-demand
    state = AgentState(
        query=query,
        prefetched_context=prefetch_context,
        max_steps=2  # Ridotto ma non a 1
    )
```

**Vantaggi**:

- Bilancia efficienza e flessibilità
- Non spreca risorse
- Mantiene capacità ReAct per casi edge

**Svantaggi**:

- Più complesso da implementare
- Richiede buon intent classifier

---

## File da Modificare

| File               | Modifiche                              | Effort |
| ------------------ | -------------------------------------- | ------ |
| `reasoning.py`     | Loop principale, multi-tool extraction | Alto   |
| `tool_executor.py` | Supporto batch execution               | Medio  |
| `orchestrator.py`  | Pre-fetch logic (se Strategia 2/3)     | Medio  |
| `definitions.py`   | `AgentState.prefetched_context`        | Basso  |
| `llm_gateway.py`   | `parallel_tool_calls` config           | Basso  |

---

## Stima Tempi

| Strategia              | Effort Dev | Rischio | Latency Attesa |
| ---------------------- | ---------- | ------- | -------------- |
| 1. Multi-Tool per Step | 2-3 giorni | Medio   | ~40-50s        |
| 2. Pre-fetch Parallel  | 3-4 giorni | Basso   | ~25-35s        |
| 3. Hybrid              | 4-5 giorni | Medio   | ~30-40s        |

---

## Raccomandazione

**Start con Strategia 1** (Multi-Tool per Step):

1. Minimo refactoring
2. Testabile incrementalmente
3. Se Gemini supporta `parallel_tool_calls`, beneficio immediato

**Se non funziona**, fallback a Strategia 2 (Pre-fetch).

---

## Test Plan

1. **Unit Test**: Mock LLM che ritorna multiple tool calls
2. **Integration Test**: Query reale con 3 tool calls parallele
3. **Latency Benchmark**: Prima/Dopo con stesso set di query
4. **Regression Test**: Verificare qualità risposte non degradata

---

## Metriche Successo

| Metrica              | Attuale       | Target        |
| -------------------- | ------------- | ------------- |
| Latency P50          | ~85s          | <35s          |
| Latency P95          | ~120s         | <50s          |
| Tool calls per query | 3 sequenziali | 1-3 parallele |
| LLM calls per query  | 3             | 1-2           |

---

## Rischi

1. **Gemini non supporta parallel_tool_calls** → Fallback a Strategia 2
2. **Qualità risposta degrada** → A/B test prima di deploy
3. **Race conditions** → Usare `asyncio.gather` con `return_exceptions=True`
4. **Costi aumentano** → Monitor token usage (dovrebbe essere uguale o minore)

---

## Next Steps

1. [ ] Verificare se Gemini 2.5/3 supporta `parallel_tool_calls`
2. [ ] Prototipo Strategia 1 in branch separato
3. [ ] Benchmark con 10 query di test
4. [ ] Se OK, merge e deploy graduale
