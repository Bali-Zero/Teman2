# Memory Orchestrator Error Scenario - Test Report

**Data:** 2026-01-19  
**Obiettivo:** Verificare che i test esistenti passino ancora, controllare i log per timing metrics, e testare lo scenario di errore quando memory_orchestrator non è disponibile.

---

## 📋 Test Esistenti da Verificare

### Test Memory Orchestrator Error Handling

**File:** `tests/unit/services/memory/test_memory_orchestrator_error_handling.py`

**Test inclusi:**
1. `test_degraded_mode_on_non_critical_failure` - Verifica degraded mode su errori non critici
2. `test_unavailable_on_critical_failure` - Verifica unavailable status su errori critici
3. `test_healthy_status_on_success` - Verifica healthy status quando tutto funziona
4. `test_error_classification_for_failures` - Verifica classificazione errori
5. `test_degraded_mode_returns_limited_context` - Verifica context limitato in degraded mode
6. `test_ensure_initialized_raises_on_unavailable` - Verifica raise su unavailable
7. `test_ensure_initialized_raises_when_not_initialized` - Verifica raise quando non inizializzato

**Status:** ⚠️ **Bloccato da dipendenza `langgraph`** - Richiede installazione nel virtualenv

**Nota:** I test sono ben strutturati e coprono gli scenari di errore. Una volta risolta la dipendenza, dovrebbero passare.

---

## 🔍 Timing Metrics nei Log

### Metriche Disponibili

Il sistema registra diverse metriche di timing per memory orchestrator:

#### Prometheus Metrics (`backend/app/metrics.py`)

```python
memory_orchestrator_degraded_total = Counter(
    "zantara_memory_orchestrator_degraded_total",
    "Number of times memory orchestrator entered degraded mode",
)

memory_orchestrator_unavailable_total = Counter(
    "zantara_memory_orchestrator_unavailable_total",
    "Number of times memory orchestrator initialization failed",
)

memory_context_degraded_total = Counter(
    "zantara_memory_context_degraded_total",
    "Number of times context was returned in degraded mode",
)

memory_context_failed_total = Counter(
    "zantara_memory_context_failed_total",
    "Number of times context retrieval failed",
)
```

#### Timing Logs (`backend/services/rag/agentic/memory_handler.py`)

Il `MemoryHandler` registra timing per:
- **Lock contention**: Tempo di attesa per acquisire lock per-user
- **Processing time**: Tempo di elaborazione dei fatti (ms)
- **Lock timeout**: Quando il lock non viene acquisito entro il timeout

**Pattern di log:**
```python
logger.info(
    f"Saved {result.facts_saved}/{result.facts_extracted} "
    f"facts for {user_id} ({result.processing_time_ms:.1f}ms)"
)
```

**Lock contention metric:**
```python
lock_wait_time = time.time() - lock_start_time
if lock_wait_time > 0.01 and metrics_collector:  # Only record if waited > 10ms
    metrics_collector.record_memory_lock_contention(
        operation="save_memory", wait_time_seconds=lock_wait_time
    )
```

---

## 🧪 Scenario di Errore: Memory Orchestrator Non Disponibile

### Comportamento Atteso

Quando `memory_orchestrator` non è disponibile, il sistema deve:

1. **Non bloccare il flusso principale** - Il RAG orchestrator continua a funzionare
2. **Ritornare None** - `get_memory_orchestrator()` ritorna `None` invece di sollevare eccezione
3. **Logging appropriato** - Warning log senza stack trace fatale
4. **Graceful degradation** - Le funzionalità che non richiedono memory continuano a funzionare

### Implementazione (`memory_handler.py`)

```python
async def get_memory_orchestrator(self) -> "MemoryOrchestrator | None":
    """Lazy load and initialize memory orchestrator."""
    if self._memory_orchestrator is None:
        try:
            from backend.services.memory import MemoryOrchestrator
            self._memory_orchestrator = MemoryOrchestrator(db_pool=self.db_pool)
            await self._memory_orchestrator.initialize()
            logger.info("MemoryOrchestrator initialized for AgenticRAG")
        except (asyncpg.PostgresError, asyncpg.InterfaceError, ValueError, RuntimeError) as e:
            logger.warning(f"Failed to initialize MemoryOrchestrator: {e}", exc_info=True)
            return None  # ✅ Non-fatal: ritorna None invece di sollevare eccezione
    return self._memory_orchestrator
```

### Test Creati

**File:** `tests/unit/services/rag/agentic/test_memory_handler_error_scenario.py`

**Test inclusi:**
1. ✅ `test_memory_orchestrator_unavailable_returns_none` - Verifica che ritorna None
2. ✅ `test_save_memory_gracefully_handles_unavailable_orchestrator` - Verifica graceful handling
3. ✅ `test_save_memory_timing_metrics_recorded` - Verifica timing metrics
4. ✅ `test_save_memory_lock_timeout_handled` - Verifica lock timeout
5. ✅ `test_save_memory_database_error_handled` - Verifica gestione errori DB
6. ✅ `test_save_memory_anonymous_user_skipped` - Verifica skip utenti anonymous
7. ✅ `test_create_save_task_returns_none_for_invalid_input` - Verifica input validation
8. ✅ `test_create_save_task_creates_background_task` - Verifica creazione task
9. ✅ `test_multiple_concurrent_saves_same_user` - Verifica serializzazione concorrente

**Status:** ⚠️ **Bloccato da dipendenza `langgraph`** - L'import di `MemoryHandler` causa import di tutto `backend.services`

---

## 🔧 Script di Verifica Log

**File:** `scripts/check_memory_timing_logs.py`

### Funzionalità

Lo script analizza i log per:
- Timing metrics (valori in ms)
- Errori di memory orchestrator
- Lock contention
- Performance metrics

### Utilizzo

```bash
# Analizza log locale
python scripts/check_memory_timing_logs.py --log-file logs/app.log

# Analizza log da Fly.io
python scripts/check_memory_timing_logs.py --fly-logs --app-name nuzantara-rag
```

### Output Atteso

```
================================================================================
MEMORY ORCHESTRATOR TIMING & ERROR ANALYSIS
================================================================================

📊 Statistics:
  Total lines analyzed: 1234
  Memory-related lines: 45
  Error lines: 2
  Timing lines: 38
  Lock-related lines: 5

⏱️  Timing Metrics:
  Count: 38
  Min: 12.50ms
  Max: 245.30ms
  Avg: 87.65ms
  Median: 82.10ms

❌ Errors Found: 2
  Recent errors:
    - WARNING: Failed to initialize MemoryOrchestrator: Database connection failed...

💾 Memory Operations: 45
  Recent operations:
    - Saved 2/2 facts for user@example.com (150.5ms)...
```

---

## ✅ Checklist Verifica

- [x] **Test creati** per scenario di errore
- [x] **Script di analisi log** creato
- [x] **Documentazione** degli scenari di errore
- [ ] **Test eseguiti** (bloccati da dipendenza `langgraph`)
- [ ] **Log analizzati** (richiede log file o accesso Fly.io)

---

## 🚀 Prossimi Passi

1. **Installare dipendenze mancanti:**
   ```bash
   cd apps/backend-rag
   source .venv/bin/activate
   pip install langgraph asyncpg
   ```

2. **Eseguire i test:**
   ```bash
   pytest tests/unit/services/memory/test_memory_orchestrator_error_handling.py -v
   pytest tests/unit/services/rag/agentic/test_memory_handler_error_scenario.py -v
   ```

3. **Verificare log:**
   ```bash
   python scripts/check_memory_timing_logs.py --fly-logs
   ```

4. **Monitorare metriche Prometheus:**
   - `zantara_memory_orchestrator_degraded_total`
   - `zantara_memory_orchestrator_unavailable_total`
   - `zantara_memory_context_degraded_total`
   - `zantara_memory_context_failed_total`

---

## 📝 Note

- Il sistema è progettato per **graceful degradation** quando memory orchestrator non è disponibile
- I timing metrics vengono registrati solo quando rilevanti (>10ms per lock contention)
- Gli errori vengono loggati come WARNING, non ERROR, per evitare allarmi non necessari
- Il flusso principale RAG continua a funzionare anche senza memory orchestrator

---

**Ultimo aggiornamento:** 2026-01-19
