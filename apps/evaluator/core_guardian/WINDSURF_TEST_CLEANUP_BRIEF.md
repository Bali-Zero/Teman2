# Test Suite Cleanup — Prompt per Windsurf

## Obiettivo

Porta la test suite del backend Python FastAPI a **0 failed, 0 errors**.

**Stato attuale:** 3853 passed, 48 failed, 17 errors, 956 skipped (7min 26s)
**Working directory:** `apps/backend-rag/`
**Python:** 3.11.11, virtualenv in `.venv/`

---

## Setup e Comandi

```bash
# SEMPRE prima di qualsiasi operazione
cd apps/backend-rag && source .venv/bin/activate

# Run singolo test file (per verificare ogni fix)
PYTHONPATH=. pytest backend/tests/path/to/test.py -v

# Run intera suite (verifica finale OBBLIGATORIA a fine lavoro)
PYTHONPATH=. pytest backend/tests/ --tb=short -q 2>&1 | tail -5
# TARGET FINALE: 0 failed, 0 errors
```

---

## Regole ASSOLUTE — Violarne una invalida tutto il lavoro

1. **MAI modificare codice di produzione** per far passare un test. I file in `backend/services/`, `backend/app/`, `backend/db/` sono SACRI. Unica eccezione: Gruppo 8 golden_rules (relative imports e type hints nel codice prod).
2. **Leggere SEMPRE il file sorgente di produzione** prima di toccare il test. La firma attuale del codice prod è LA VERITÀ. I test devono adattarsi al codice, mai il contrario.
3. **Se un test testa funzionalità che non esiste più → CANCELLARE il test intero**, non inventare mock per funzionalità fantasma.
4. **`AsyncMock` per ogni funzione async** — `MagicMock` non funziona con `await`. Il `return_value` deve essere il valore DIRETTO (es. `AsyncMock(return_value={"id": 1})`), MAI una coroutine.
5. **NON toccare questi test (passano già):** `test_kg_langgraph.py`, `test_kg_subgraphs.py`, `test_confidence.py`, `test_graph_tool_coverage.py`
6. **Import assoluti** obbligatori: `from backend.xyz import ...`, mai `from ..xyz import ...`
7. **Type hints** obbligatori su ogni funzione che scrivi.
8. **Verifica ogni gruppo** con `PYTHONPATH=. pytest <file> -v` prima di passare al successivo.

---

## TASK 1: AsyncMock non awaitable (14 test)

### 1A. `backend/tests/integration/conversation/test_e2e_conversation_flow.py` — 7 test falliti

**Errore:** `TypeError: object AsyncMock can't be used in 'await' expression`

**Causa root:** La fixture `mock_db_pool` a riga 30-39 crea il pool correttamente con `AsyncMock` per il context manager, MA il problema è nella riga 100:

```python
conn = await mock_db_pool.acquire()  # ← SBAGLIATO: acquire() ritorna un CM, non una conn
```

**File sorgente da leggere:** `backend/services/misc/conversation_service.py`
Il codice prod usa `async with self.db_pool.acquire() as conn:` (riga 55), quindi il mock deve supportare `async with`, non `await`.

**Coordinate dei 7 test (tutti nella classe `TestE2EConversationFlow`):**

- `test_save_conversation_with_auto_crm` (riga 82)
- `test_conversation_history_retrieval` (riga ~120)
- `test_conversation_history_fallback_to_memory_cache` (riga ~140)
- `test_multi_turn_conversation_context` (riga ~160)
- `test_conversation_with_episodic_memory_linking` (riga ~200)
- `test_conversation_metadata_persistence` (riga ~240)
- `test_conversation_error_handling` (riga ~280)

**Fix:** La fixture `mock_db_pool` (riga 30-39) è GIÀ corretta con il pattern CM:

```python
cm = AsyncMock()
cm.__aenter__.return_value = conn
pool.acquire.return_value = cm
```

Il problema è che nei test stessi (es. riga 100-101) fanno:

```python
conn = await mock_db_pool.acquire()  # SBAGLIATO
conn.fetchrow = AsyncMock(...)
```

Invece devono prendere la `conn` dalla fixture o dal CM. Fix: rimuovere le righe che fanno `await mock_db_pool.acquire()` nei test body e usare la `conn` dalla fixture tramite `mock_db_pool.acquire.return_value.__aenter__.return_value`.

Inoltre, `_get_auto_crm` (riga 104) potrebbe essere un metodo async che ritorna il servizio — verificare se serve `AsyncMock`.

**Verifica:** `PYTHONPATH=. pytest backend/tests/integration/conversation/test_e2e_conversation_flow.py -v`

---

### 1B. `backend/tests/integration/multi_service/test_rag_memory_kg_integration.py` — 2 test falliti

**Errore:** `Expected 'get_user_context' to have been called once. Called 0 times.`

**File sorgente da leggere:** `backend/services/rag/agentic/orchestrator_context.py` — cercare dove `get_user_context` viene chiamato e qual è il path completo per il mock `patch`.

**Fix:** Il mock target è probabilmente `backend.services.rag.agentic.orchestrator_context.OrchestratorContextManager.get_basic_context` (il nome del metodo potrebbe essere cambiato da `get_user_context` a `get_basic_context`). Leggere il file e aggiornare il target del `patch`.

**Verifica:** `PYTHONPATH=. pytest backend/tests/integration/multi_service/test_rag_memory_kg_integration.py -v`

---

### 1C. `backend/tests/integration/multi_tool/test_multi_tool_execution_flow.py` — 1 test fallito

**Errore:** `Expected 'search' to have been called` + `coroutine 'AsyncMockMixin._execute_mock_call' was never awaited`

**Fix:** Il mock di `search` deve essere `AsyncMock`, non `MagicMock`. E il return_value deve essere un valore diretto.

**Verifica:** `PYTHONPATH=. pytest backend/tests/integration/multi_tool/test_multi_tool_execution_flow.py -v`

---

### 1D. `backend/tests/services/rag/evaluation/test_benchmark.py` — `test_save_results` (1 test)

**Errore:** `TypeError: object MagicMock can't be used in 'await' expression`

**Fix:** Il mock per `asyncpg` pool/connection deve usare `AsyncMock`.

---

### 1E. `backend/tests/services/rag/evaluation/test_ragas_evaluator.py` — `test_end_to_end_evaluation` (1 test)

**Errore:** `TypeError: object MagicMock can't be used in 'await' expression`

**Fix:** Come sopra.

---

### 1F. `backend/tests/integration/routing/test_e2e_routing_fallback.py` — 2 test falliti

**Errore:** `assert 0 >= 1` e `assert 0 == 3` — i mock non vengono chiamati

**Fix:** Verificare che i mock target siano corretti per il routing attuale. Leggere `backend/services/rag/agentic/orchestrator_routing.py`.

---

## TASK 2: PipelineConfig firma cambiata (6 errori di setup)

**File da fixare:** `backend/tests/integration/knowledge_graph/test_e2e_kg_flow.py`
**Errore:** `PipelineConfig.__init__() got an unexpected keyword argument 'enable_coreference'`

**Firma ATTUALE di PipelineConfig** (file: `backend/services/knowledge_graph/pipeline.py`, riga 33-59):

```python
@dataclass
class PipelineConfig:
    model: str = "claude-sonnet-4-20250514"
    api_key: str | None = None
    extractor_type: str = "claude"
    two_stage_extraction: bool = False
    use_coreference: bool = True        # ← ERA "enable_coreference", ORA È "use_coreference"
    min_confidence: float = 0.6
    use_quality_filter: bool = True
    min_entity_name_length: int = 4
    fuzzy_match_threshold: float = 0.85
    infer_relationships: bool = True
    batch_size: int = 10
    max_concurrent: int = 5
    database_url: str | None = None
```

**Fix alla riga 68 del test:**

```python
# PRIMA (rotto):
config = PipelineConfig(batch_size=10, enable_coreference=True, enable_entity_linking=True)
# DOPO (corretto):
config = PipelineConfig(batch_size=10, use_coreference=True)
```

Nota: `enable_entity_linking` NON ESISTE più in PipelineConfig. Rimuoverlo.

Anche il nome della classe pipeline potrebbe essere cambiato — cercare `class KGPipeline` nel file `pipeline.py`. Se non esiste, il test va riscritto o cancellato.

**Verifica:** `PYTHONPATH=. pytest backend/tests/integration/knowledge_graph/test_e2e_kg_flow.py -v`

---

## TASK 3: AgenticRAGOrchestrator firma cambiata (7 errori di setup)

**File da fixare:** `backend/tests/integration/rag_agentic/test_e2e_rag_flow.py`
**Errore:** `AgenticRAGOrchestrator.__init__() missing 1 required positional argument: 'tools'`

**Firma ATTUALE** (file: `backend/services/rag/agentic/orchestrator.py`, riga 101-112):

```python
def __init__(
    self,
    tools: list[BaseTool],           # ← REQUIRED, primo arg
    db_pool: Any = None,
    model_name: str = "gemini-3-flash-preview",
    semantic_cache: SemanticCache = None,
    faq_cache: Any = None,
    retriever: Any = None,
    clarification_service: ClarificationService = None,
    entity_extractor: EntityExtractionService = None,
    llm_gateway: LLMGateway = None,
):
```

**Import necessario per il tipo:** `from backend.services.tools.definitions import BaseTool`

**Fix:** Nella fixture che crea l'orchestratore, aggiungere `tools=[]` come primo argomento:

```python
orch = AgenticRAGOrchestrator(tools=[], db_pool=mock_db_pool, ...)
```

**Verifica:** `PYTHONPATH=. pytest backend/tests/integration/rag_agentic/test_e2e_rag_flow.py -v`

---

## TASK 4: test_conversation_persistence con DB reale (3 errori)

**File:** `backend/tests/test_conversation_persistence.py`
**Errore:** `socket.gaierror` — tenta connessione a DB reale

**File sorgente:** `backend/db/repositories/conversation_repository.py`
La classe `ConversationRepository.__init__` accetta `db_pool: asyncpg.Pool` e usa `self.db_pool.acquire()` come async context manager.

**Fix consigliato:** Convertire a test con mock. Sostituire il contenuto del file con:

```python
"""Test conversation persistence with mocked DB pool"""
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
import pytest
from backend.db.repositories.conversation_repository import ConversationRepository

@pytest.fixture
def mock_db_pool():
    pool = MagicMock()
    conn = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire.return_value = cm
    return pool, conn

@pytest.mark.asyncio
async def test_conversation_repository_save_and_retrieve(mock_db_pool):
    pool, conn = mock_db_pool
    repo = ConversationRepository(pool)
    # Mock SELECT returning None (new conversation)
    conn.fetchrow.side_effect = [None, {"id": 1}]
    result = await repo.save_messages(
        session_id="test-session", user_id="test@example.com",
        messages=[{"role": "user", "content": "Hello"}], metadata={"test": True}
    )
    assert result == 1

@pytest.mark.asyncio
async def test_conversation_repository_limit(mock_db_pool):
    pool, conn = mock_db_pool
    repo = ConversationRepository(pool)
    msgs = [{"role": "user", "content": f"Msg {i}"} for i in range(10)]
    conn.fetchrow.return_value = {"messages": msgs}
    result = await repo.get_messages(session_id="test", limit=5)
    assert len(result) == 5

@pytest.mark.asyncio
async def test_conversation_cleanup(mock_db_pool):
    pool, conn = mock_db_pool
    repo = ConversationRepository(pool)
    conn.execute.return_value = "DELETE 3"
    result = await repo.cleanup_old_conversations(days=30)
    assert result == 3
```

**ATTENZIONE:** La funzione `save_messages` del repo usa `to_jsonb()` — il mock di `fetchrow` e `execute` non deve preoccuparsene perché `to_jsonb` opera sul valore passato, non sulla connessione.

**Verifica:** `PYTHONPATH=. pytest backend/tests/test_conversation_persistence.py -v`

---

## TASK 5: ABSTAIN/fluidity thresholds obsoleti (8 test)

**Valore ATTUALE di ABSTAIN_THRESHOLD:** `0.15` (file: `backend/app/core/constants.py`, riga 96)

```python
class EvidenceScoreConstants:
    ABSTAIN_THRESHOLD: float = 0.15
    CONFIDENCE_LOW: float = 0.15
    CONFIDENCE_CAUTIOUS: float = 0.6
    CONFIDENCE_HIGH: float = 0.6
```

La costante è in `backend.app.core.constants.EvidenceScoreConstants.ABSTAIN_THRESHOLD`.

### 5A. `backend/tests/integration/zantara/test_fluidity_and_strength.py` — 2 test

**Problemi aggiuntivi:** Riga 30 fa `from services.rag.agentic.orchestrator import ...` (import relativo via `os.chdir`). Questo è fragile ma funziona. NON cambiare il pattern di import se non causa errori.

- `test_low_abstain_threshold`: aspetta `0.2`, cambiare a `0.15`
- `test_evidence_score_calculation_allows_responses`: il calcolo produce `0.04` che è sotto `0.15`, quindi l'ABSTAIN scatta correttamente. Il test è sbagliato — deve aspettarsi che `0.04` venga trattato come ABSTAIN, oppure il mock del contesto deve produrre un score più alto.

**Verifica:** `PYTHONPATH=. pytest backend/tests/integration/zantara/test_fluidity_and_strength.py -v`

### 5B. `backend/tests/integration/zantara/test_fluidity_and_strength_simple.py` — 4 test

Cercano stringhe esatte nei file sorgente:

- `ABSTAIN_THRESHOLD = 0.2` → non esiste più (è `0.15` e in un'altra posizione)
- `MULTIPLE_SOURCES_BONUS` → cercare il nome attuale in `reasoning.py`

**Fix:** Leggere `reasoning.py` con grep per trovare i nomi attuali delle costanti e aggiornare le assertion dei test.

### 5C. `backend/tests/integration/zantara/test_tier1_fallback.py` — 3 test

Cercano `Transparency Protocol` nel prompt. La stringa è probabilmente cambiata.

**File sorgente:** `backend/services/rag/agentic/prompt_builder.py` — cercare il testo attuale relativo al fallback/tier1.

Se il concetto "Tier1 fallback" non esiste più nel codice → CANCELLARE i 3 test.

**Verifica:** `PYTHONPATH=. pytest backend/tests/integration/zantara/ -v`

---

## TASK 6: Benchmark/evaluation test obsoleti (10 test)

### 6A. `backend/tests/services/rag/evaluation/test_benchmark.py` — 6 test

**File sorgente:** `backend/services/rag/evaluation/benchmark.py`

Il search method si chiama ora `hybrid_rrf` (non `hybrid`). Aggiornare tutte le assertion che fanno `== 'hybrid'` a `== 'hybrid_rrf'`.

Per `test_init_lazy_reranker` e `test_init_reranker_failure`: verificare come il reranker viene inizializzato nella classe `BenchmarkRunner` (o come si chiama ora).

Per `test_evaluate_sample_dense`: la query di default è cambiata da `'test query'` a `'Apa itu KITAS?'` — aggiornare.

### 6B. `backend/tests/services/rag/evaluation/test_dataset_builder.py` — 4 test

**File sorgente:** `backend/services/rag/evaluation/dataset_builder.py`

- Dataset size è 18 non 20 → aggiornare assertion
- Ratios producono 5 non 6 → aggiornare
- `invalid_ratios` non lancia più → rimuovere `pytest.raises`, testare il return value
- Template con `{business_term}` non risolto → verificare la lista di template nel builder

**Verifica:** `PYTHONPATH=. pytest backend/tests/services/rag/evaluation/ -v`

---

## TASK 7: GraphTraversalTool — test_agentic_init.py (1 errore)

**File:** `backend/tests/services/rag/agentic/test_agentic_init.py`

**Il file attuale (14 righe) fa:**

```python
from backend.services.rag.agentic.__init__ import *
```

Il problema: `__init__.py` dichiara `GraphTraversalTool` in `__all__` (riga 94) ma lo carica lazy via `_get_graph_traversal_tool()`. L'errore è che `from ... import *` tenta di risolvere `GraphTraversalTool` direttamente come attributo del modulo, ma è accessibile solo tramite la funzione `_get_graph_traversal_tool()`.

**Fix:** Il test è un skeleton auto-generato con `@pytest.mark.skip`. Dato che è skippato E rotto:

- **Opzione A (consigliata):** Cancellare il file intero — è un skeleton vuoto che non testa niente
- **Opzione B:** Cambiare l'import a `from backend.services.rag.agentic import AgenticRAGOrchestrator` (import esplicito, non `*`)

**Verifica:** `PYTHONPATH=. pytest backend/tests/services/rag/agentic/test_agentic_init.py -v`

---

## TASK 8: Vari singoli (11 test)

### 8A. `backend/tests/compliance/test_golden_rules.py` — 2 test — QUI SI FIXA IL CODICE PROD

**ECCEZIONE alla regola 1:** Questi test verificano regole di qualità del codice di produzione. Qui devi fixare il codice prod.

**test_golden_rule_3_no_relative_imports (17 relative imports):**

I relative imports nel codice prod sono:

```
backend/services/misc/__init__.py:  from ..autonomous_agents.knowledge_graph_builder import ...
backend/agents/agents/knowledge_graph_builder.py:  from ..services.kg_extractors import EntityExtractor, ...
backend/agents/agents/knowledge_graph_builder.py:  from ..services.kg_repository import KnowledgeGraphRepository
backend/agents/agents/knowledge_graph_builder.py:  from ..services.kg_schema import KnowledgeGraphSchema
```

Convertire ogni `from ..xyz import` a `from backend.xyz import`. Verificare che gli import assoluti funzionino.

**test_golden_rule_5_type_hints (5 missing):**
Eseguire il test singolo con `-v` per vedere QUALI funzioni mancano di type hints. Poi aggiungerle.

```bash
PYTHONPATH=. pytest backend/tests/compliance/test_golden_rules.py::test_golden_rule_5_type_hints -v --tb=long
```

**Verifica:** `PYTHONPATH=. pytest backend/tests/compliance/test_golden_rules.py -v`

---

### 8B. `backend/tests/integration/article_composer/test_article_composer_integration.py` — 4 test

**Errore:** Status code 422 (validation error) su tutti i test. L'endpoint `/api/articles/compose` restituisce 422 perché il payload non passa la validazione Pydantic.

**File sorgente:** `backend/app/routers/article_composer.py` — leggere il modello `ComposeRequest` (o come si chiama) per vedere i campi REQUIRED attuali.

**Fix:** Aggiornare il payload JSON nei test per includere tutti i campi required. Il mock di TestClient potrebbe anche non includere i middleware/auth corretti — in quel caso il router potrebbe richiedere dipendenze aggiuntive da mockare.

**Verifica:** `PYTHONPATH=. pytest backend/tests/integration/article_composer/ -v`

---

### 8C. `backend/tests/unit/app/test_config.py` — 1 test

**Errore:** `DATABASE_URL` override aspetta una stringa specifica che non corrisponde.

**File sorgente:** `backend/app/core/config.py` — leggere la logica di override di `DATABASE_URL`.

**Fix:** Aggiornare la stringa attesa nel test.

---

### 8D. `backend/tests/unit/core/test_embeddings.py` — 1 test

**Errore:** `DID NOT RAISE Exception` — il codice gestisce l'errore gracefully.

**Fix:** Cambiare il test da `pytest.raises(Exception)` a verificare che il return value sia vuoto/None/empty.

---

### 8E. `backend/tests/services/rag/test_reranker.py` — 1 test

**Errore:** `assert 3 == 4`

**Fix:** Leggere il reranker service per capire il filtraggio attuale. Aggiornare il conteggio.

---

### 8F. `backend/tests/integration/knowledge/test_knowledge_service_integration.py` — 3 test

- `test_query_router_integration`: `visa_oracle` vs `kbli_unified` — il routing è cambiato
- `test_hybrid_collection_vector_name`: `dense` vs `None` — la naming convention è cambiata
- `test_error_handling_integration`: non lancia più eccezione

**File sorgente:** `backend/app/modules/knowledge/service.py` — leggere il routing e le configurazioni collection.

---

### 8G. `backend/tests/integration/specialized_services/test_autonomous_research_integration.py` — 1 test

**Errore:** `Expected 'get' to have been called` — mock della cache non configurato.

**Fix:** Verificare dove il caching viene usato nel codice prod e aggiornare il target del `patch`.

---

## Ordine di esecuzione OBBLIGATORIO

```
TASK 7  →  1 file da cancellare, 30 secondi
TASK 4  →  1 file da riscrivere, 5 minuti
TASK 2  →  1 fix a riga 68, 2 minuti
TASK 3  →  1 parametro da aggiungere, 5 minuti
TASK 1  →  14 test, il più grosso — 30 minuti
TASK 5  →  8 test thresholds, 15 minuti
TASK 6  →  10 test benchmark, 15 minuti
TASK 8  →  11 test vari, 20 minuti
```

## Verifica FINALE — NON SALTARE

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/ --tb=short -q 2>&1 | tail -5
```

**DEVE mostrare:**

- `0 failed`
- `0 errors`
- `passed >= 3853` (il numero di passed non deve scendere — se scende, hai cancellato test che passavano)
- `skipped` può cambiare
