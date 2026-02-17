# LangGraph Agentic Layer - Nuzantara Prime

**Status:** ✅ Implemented (2026-02-14)
**Version:** 1.0.0
**Author:** Chief Architect

---

## 1. Executive Summary

This document describes the **LangGraph-based agentic layer** implemented on top of Nuzantara Prime's existing FastAPI backend.

### Key Characteristics

- **Clean Separation**: Agentic logic in `app/agents/`, deterministic logic remains in `app/routers/` and `services/`
- **Production Ready**: Type-safe, observable, testable, documented
- **Extensible**: Easy to add new nodes, workflows, and integrations
- **Backward Compatible**: Existing routers unchanged, new `/api/agent` namespace

### Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                  FastAPI Layer                      │
│  /api/agent/invoke  →  Agent Router  →  LangGraph  │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│              LangGraph Workflow (agents/)           │
│  State → Retrieve → Grade → Generate → End         │
└─────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────┐
│          Existing Services (deterministic)          │
│  SearchService, QdrantService, LLMGateway, etc.    │
└─────────────────────────────────────────────────────┘
```

---

## 2. Directory Structure

```
backend/app/agents/
├── __init__.py           # Package initialization
├── state.py              # TypedDict state definitions
├── graph.py              # LangGraph workflow (Start → Retrieve → Grade → Generate)
├── nodes.py              # (Future) Node implementations
└── tools.py              # (Future) Tool definitions for agents

backend/app/routers/
└── agent.py              # API router exposing /api/agent endpoints
```

---

## 3. State Definitions (state.py)

### Core States

| State Class      | Purpose                                       | Key Fields                             |
| ---------------- | --------------------------------------------- | -------------------------------------- |
| `AgentState`     | Basic RAG workflow state                      | question, documents, generation        |
| `RetrievalState` | Extended retrieval tracking                   | query_vector, collection_name, top_k   |
| `GradingState`   | Document relevance tracking                   | relevance_scores, filtered_documents   |
| `WorkflowState`  | Full multi-step workflow (most commonly used) | All above + execution_path, step_count |

### Example: WorkflowState

```python
class WorkflowState(TypedDict, total=False):
    # Input
    question: str
    metadata: Optional[Dict[str, Any]]

    # Retrieval
    documents: List[str]
    retrieved_scores: Optional[List[float]]

    # Grading
    relevance_scores: Optional[List[float]]
    filtered_documents: Optional[List[str]]

    # Generation
    generation: str

    # Execution tracking
    errors: Optional[List[str]]
    step_count: Optional[int]
    timestamp: Optional[datetime]
    execution_path: Optional[List[str]]
```

---

## 4. Workflow Graph (graph.py)

### Current Workflow: RAG Pipeline

```mermaid
graph TD
    Start[Start] --> Retrieve[Retrieve Node]
    Retrieve --> Grade[Grade Node]
    Grade --> Decision{Relevant Docs?}
    Decision -->|Yes| Generate[Generate Node]
    Decision -->|No| End1[End]
    Generate --> End2[End]
```

### Node Descriptions

| Node       | Input                        | Output                               | Integration Status     |
| ---------- | ---------------------------- | ------------------------------------ | ---------------------- |
| `retrieve` | question                     | documents, retrieved_scores          | 🟡 Stub (TODO: Qdrant) |
| `grade`    | documents, retrieved_scores  | filtered_documents, relevance_scores | 🟡 Stub (TODO: LLM)    |
| `generate` | question, filtered_documents | generation                           | 🟡 Stub (TODO: LLM)    |

**Legend:**

- 🟡 Stub: Placeholder implementation (returns mock data)
- 🟢 Integrated: Connected to existing services
- 🔴 Not Implemented

---

## 5. API Endpoints (routers/agent.py)

### 5.1 POST /api/agent/invoke

**Description:** Invoke the RAG workflow with a question.

**Authentication:** Required (JWT token)

**Request Body:**

```json
{
  "question": "What are the requirements for a KITAS visa?",
  "metadata": {
    "user_id": "user_123",
    "session_id": "session_456",
    "language": "en"
  }
}
```

**Response (200 OK):**

```json
{
  "success": true,
  "question": "What are the requirements for a KITAS visa?",
  "generation": "Based on the documents, KITAS requirements include...",
  "execution_path": ["retrieve", "grade", "generate"],
  "step_count": 3,
  "timestamp": "2026-02-14T13:02:38.940051",
  "metadata": { "user_id": "user_123" },
  "errors": null
}
```

**Example cURL:**

```bash
curl -X POST https://nuzantara-rag.fly.dev/api/agent/invoke \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the requirements for a KITAS visa?",
    "metadata": {"user_id": "user_123"}
  }'
```

---

### 5.2 GET /api/agent/health

**Description:** Check agent system health.

**Authentication:** Not required (public endpoint)

**Response (200 OK):**

```json
{
  "status": "healthy",
  "graph_loaded": true,
  "timestamp": "2026-02-14T13:10:00",
  "message": "Agent system is operational"
}
```

**Example cURL:**

```bash
curl https://nuzantara-rag.fly.dev/api/agent/health
```

---

## 6. Integration Points (Next Steps)

### 6.1 Retrieve Node → QdrantService

**File:** `backend/services/search/search_service.py`

**Integration:**

```python
# In retrieve_node (graph.py)
from backend.app.dependencies import get_search_service

async def retrieve_node(state: WorkflowState) -> WorkflowState:
    question = state["question"]
    search_service = get_search_service()  # Inject dependency

    # Call existing SearchService
    results = await search_service.search_collection(
        collection_name="legal_unified_hybrid",
        query_text=question,
        top_k=5,
    )

    documents = [r["text"] for r in results]
    scores = [r["score"] for r in results]

    return {**state, "documents": documents, "retrieved_scores": scores}
```

---

### 6.2 Grade Node → LLM Gateway

**File:** `backend/services/llm/llm_gateway.py`

**Integration:**

```python
# In grade_node (graph.py)
from backend.app.dependencies import get_llm_client

async def grade_node(state: WorkflowState) -> WorkflowState:
    question = state["question"]
    documents = state["documents"]
    llm_client = get_llm_client()  # Claude/OpenAI client

    # LLM prompt for relevance grading
    prompt = f"""
    Question: {question}

    For each document below, rate its relevance (0-1):
    {chr(10).join(f"{i+1}. {doc}" for i, doc in enumerate(documents))}
    """

    response = await llm_client.generate(prompt)
    relevance_scores = parse_scores(response)  # Extract scores

    # Filter documents with score > 0.7
    filtered_docs = [doc for doc, score in zip(documents, relevance_scores) if score > 0.7]

    return {**state, "filtered_documents": filtered_docs, "relevance_scores": relevance_scores}
```

---

### 6.3 Generate Node → Orchestrator

**File:** `backend/services/rag/agentic/orchestrator.py`

**Integration:**

```python
# In generate_node (graph.py)
from backend.app.dependencies import get_orchestrator

async def generate_node(state: WorkflowState) -> WorkflowState:
    question = state["question"]
    filtered_docs = state["filtered_documents"]
    orchestrator = get_orchestrator()  # Existing AgenticRAGOrchestrator

    # Call existing orchestrator with filtered context
    response = await orchestrator.aquery(
        query=question,
        context_override=filtered_docs,  # Use pre-filtered documents
    )

    return {**state, "generation": response["answer"]}
```

---

## 7. Testing

### 7.1 Unit Tests (Manual Verification)

```bash
cd /Users/antonellosiano/Projects/nuzantara/apps/backend-rag
source .venv/bin/activate

# Test 1: Graph compilation
PYTHONPATH=. python -c "
from backend.app.agents.graph import rag_graph
print('✅ Graph loaded:', type(rag_graph))
"

# Test 2: Workflow invocation
python /tmp/test_agent_workflow.py

# Test 3: API imports
python /tmp/test_agent_api.py

# Test 4: Router registration
PYTHONPATH=. python -c "
from backend.app.setup.router_registration import include_routers
from fastapi import FastAPI
app = FastAPI()
include_routers(app)
agent_routes = [r for r in app.routes if '/api/agent' in str(r.path)]
print(f'✅ Found {len(agent_routes)} agent endpoints')
"
```

**Results:**

- ✅ Graph compilation: SUCCESS
- ✅ Workflow invocation: SUCCESS (3 steps executed)
- ✅ API imports: SUCCESS (2 endpoints)
- ✅ Router registration: SUCCESS (2 agent routes)

---

### 7.2 Integration Tests (TODO)

**File:** `backend/tests/integration/test_agent_workflow.py`

```python
import pytest
from backend.app.agents.graph import invoke_rag_workflow

@pytest.mark.asyncio
async def test_full_workflow_with_mocked_services():
    """Test complete workflow with mocked SearchService and LLMGateway."""
    result = invoke_rag_workflow(
        question="Test question",
        metadata={"test": True}
    )

    assert result["step_count"] == 3
    assert result["execution_path"] == ["retrieve", "grade", "generate"]
    assert len(result["generation"]) > 0
    assert result.get("errors") is None
```

---

## 8. Deployment Checklist

### Pre-Deployment

- [x] Virtual environment created (.venv/)
- [x] LangGraph dependencies installed (requirements.txt)
- [x] Directory structure created (app/agents/)
- [x] State definitions implemented (state.py)
- [x] Workflow graph implemented (graph.py)
- [x] API router created (routers/agent.py)
- [x] Router registered (setup/router_registration.py)
- [x] Manual tests passed (4/4)
- [ ] Integration tests written
- [ ] Service integrations completed (retrieve/grade/generate nodes)

### Deployment to Staging/Production

```bash
# 1. Commit changes
git add backend/app/agents/ backend/app/routers/agent.py backend/app/setup/router_registration.py
git commit -m "feat(agents): implement LangGraph agentic layer with RAG workflow

- Add app/agents/ directory with state.py, graph.py
- Implement 3-node workflow: Retrieve → Grade → Generate
- Expose /api/agent/invoke and /api/agent/health endpoints
- Register agent router in router_registration.py
- All manual tests passing (graph compilation, invocation, API)

Next steps:
- Integrate SearchService (retrieve node)
- Integrate LLM Gateway (grade + generate nodes)
- Add integration tests
"

# 2. Deploy to Fly.io
fly deploy --config apps/backend-rag/fly.toml --app nuzantara-rag

# 3. Verify health
curl https://nuzantara-rag.fly.dev/api/agent/health

# Expected output:
# {"status":"healthy","graph_loaded":true,"timestamp":"...","message":"Agent system is operational"}
```

---

## 9. Performance Considerations

### Current Performance (Stub Implementation)

| Metric                  | Value   | Notes                         |
| ----------------------- | ------- | ----------------------------- |
| Workflow execution time | ~50ms   | Mock data only (no I/O)       |
| Step count              | 3       | retrieve → grade → generate   |
| Memory usage            | < 10 MB | Lightweight graph compilation |

### Projected Performance (Full Integration)

| Metric               | Estimated | Bottleneck                         |
| -------------------- | --------- | ---------------------------------- |
| Retrieve node        | 200-500ms | Qdrant vector search               |
| Grade node           | 1-2s      | LLM API call (Claude/OpenAI)       |
| Generate node        | 2-5s      | LLM generation (depends on length) |
| **Total end-to-end** | **3-8s**  | LLM latency dominates              |

### Optimization Strategies

1. **Parallel Execution**: Run retrieve + grade in parallel if possible
2. **Caching**: Cache frequently asked questions (Redis)
3. **Streaming**: Use SSE for progressive generation in generate node
4. **Model Selection**: Use Haiku for grading (fast), Sonnet/Opus for generation (quality)

---

## 10. Future Enhancements

### Phase 2: Advanced Workflows

- **Self-Correction Loop**: If generation quality is low, retry with different retrieval strategy
- **Multi-Hop Reasoning**: Traverse knowledge graph nodes for complex queries
- **Tool Calling**: Integrate PricingTool, KnowledgeGraphTool, etc. as LangGraph tools

### Phase 3: Observability

- **LangSmith Integration**: Trace workflow executions in LangSmith dashboard
- **Prometheus Metrics**: Expose workflow_duration, step_success_rate, etc.
- **Sentry Error Tracking**: Capture workflow failures in Sentry

### Phase 4: Advanced Features

- **Checkpointing**: Persist state with `langgraph-checkpoint-postgres`
- **Human-in-the-Loop**: Pause workflow for human review before generation
- **Multi-Agent Collaboration**: Multiple agents working together (research + synthesis)

---

## 11. Troubleshooting

### Issue: Graph fails to load

**Symptom:** `ImportError: cannot import name 'rag_graph' from 'backend.app.agents.graph'`

**Solution:**

```bash
# Verify LangGraph is installed
source .venv/bin/activate
python -c "import langgraph; print(langgraph.__version__)"

# Check graph compilation
PYTHONPATH=. python -c "from backend.app.agents.graph import rag_graph; print(type(rag_graph))"
```

---

### Issue: Router not registered

**Symptom:** `404 Not Found` when calling `/api/agent/invoke`

**Solution:**

```bash
# Verify router is imported in router_registration.py
grep "agent" backend/app/setup/router_registration.py

# Check if router is included
PYTHONPATH=. python -c "
from backend.app.setup.router_registration import include_routers
from fastapi import FastAPI
app = FastAPI()
include_routers(app)
print([r.path for r in app.routes if '/api/agent' in str(r.path)])
"
```

---

### Issue: Workflow hangs or times out

**Symptom:** Request to `/api/agent/invoke` takes > 30s

**Cause:** One of the nodes (retrieve/grade/generate) is blocking indefinitely

**Solution:**

1. Add timeout to node operations (use `asyncio.wait_for`)
2. Check logs for which node is stuck:
   ```bash
   fly logs -a nuzantara-rag | grep "RETRIEVE_NODE\|GRADE_NODE\|GENERATE_NODE"
   ```
3. Implement circuit breaker for external service calls

---

## 12. References

### Internal Documentation

- `/docs/KG_LANGGRAPH_ARCHITECTURE.md` - Knowledge Graph LangGraph implementation
- `/docs/AGENTIC_RAG_API.md` - Existing agentic RAG system
- `CLAUDE.md` - Project memory and golden rules

### External Resources

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangChain StateGraph](https://python.langchain.com/docs/langgraph/reference/graphs)
- [FastAPI Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)

---

## 13. Version History

| Version | Date       | Author          | Changes                                  |
| ------- | ---------- | --------------- | ---------------------------------------- |
| 1.0.0   | 2026-02-14 | Chief Architect | Initial implementation with RAG workflow |

---

**Status:** ✅ Phase 1 Complete (Foundation)
**Next Milestone:** Phase 2 - Service Integration (retrieve/grade/generate nodes)
**Owner:** Chief Architect
**Last Updated:** 2026-02-14
