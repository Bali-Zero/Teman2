# Graph Design

## Flow

```
understand ──> route ──┬──> retrieve ──> GRADE_RETRIEVAL ──┬──> reason ──> GRADE_REASONING ──┬──> synthesize ──> GRADE_ANSWER ──┬──> GRADE_HALLUC ──> END
                       │                   │ retry          │                 │ retry          │                  │ retry         │
                       │                   └───< retrieve   │                 └───< reason     │                  └───< synth     │
                       │                                    │                                  │                                  │
                       ├──> subgraph_company ───────────────┘                                  │                                  │
                       ├──> subgraph_visa ─────────────────────────────────────────────────────┘                                  │
                       ├──> subgraph_property                                                                                     │
                       ├──> subgraph_tax                                                                                          │
                       ├──> tools ──> reason                                                                                      │
                       └──> synthesize_direct (greeting/cache) ───────────────────────────────────────────────────────────────────┘
```

## Node Specifications

### understand

- **Input:** raw `query`, `conversation_history` (from session memory)
- **Output:** `intent`, `domain`, `extracted_entities`, `detected_language`, `is_followup`
- **LLM call:** Yes (intent classification + entity extraction, uses history for follow-up detection)

### route (conditional edges)

- **Logic:** Maps `IntentType` enum to `RouteDecision` enum
- **No LLM call** — purely deterministic

### retrieve

- **Input:** `query`, `extracted_entities`
- **Output:** `retrieved_documents`, `kg_entities`, `kg_relationships`
- **Services:** Qdrant vector search + PostgreSQL KG traversal

### reason

- **Input:** `retrieved_documents`, `kg_entities`, `extracted_entities`
- **Output:** `reasoning_steps`, `tool_calls`
- **LLM call:** Yes (CoT reasoning with optional tool use)

### synthesize

- **Input:** `reasoning_steps`, `retrieved_documents`
- **Output:** `answer`, `sources`, `confidence`
- **LLM call:** Yes (answer generation)

### tools

- **Input:** tool call request from reason node
- **Output:** `tool_calls` with results
- **No LLM call** — executes tool functions

## Grader Specifications

Each grader follows the same pattern:

```python
class BaseGrader(ABC):
    @abstractmethod
    def grade(self, state: GraphState) -> GradeResult:
        """Returns PASS (≥0.7), RETRY (0.4-0.7), or FAIL (<0.4)"""
```

| Grader        | Checks                          | Threshold | LLM verification         |
| ------------- | ------------------------------- | --------- | ------------------------ |
| retrieval     | Document relevance to query     | 0.7       | No                       |
| reasoning     | CoT coherence and completeness  | 0.7       | No                       |
| answer        | Answer quality and completeness | 0.7       | No                       |
| hallucination | Factual grounding in sources    | 0.8       | Yes (borderline 0.5–0.8) |
| pricing       | Price accuracy vs official data | 0.9       | No                       |

### Hallucination Grader — Two-Phase Verification

1. **Fast heuristic:** keyword overlap ratio (always, zero LLM cost)
2. **LLM verification:** called only when heuristic score is 0.50–0.80
   - Blend: 70% LLM score + 30% heuristic
   - Model: `gemini-2.0-flash` (fast + cheap for grading)

## Correction Cycle

1. Grader returns `RETRY` with `retry_hint`
2. Router checks `correction_count < max_corrections`
3. If yes: increment `correction_count`, loop back to previous node
4. If no: continue forward with warning (degraded answer)

Max corrections: 2 (configurable via `GraphState.max_corrections`)

## Subgraphs

Each domain subgraph is a compiled `StateGraph` that:

1. Receives the main `GraphState`
2. Performs domain-specific retrieval and reasoning
3. Updates `retrieved_documents`, `kg_entities`, `reasoning_steps`
4. Returns to the main graph's `reason` node

Subgraphs: company (PT PMA/CV), visa (KITAS/KITAP), property (Hak Pakai/HGB), tax (PPh/PPN)

## Semantic Cache Integration

Cache check happens **before** graph invocation in `/api/query`:

1. Exact SHA-256 hash lookup (O(1), no embedding)
2. Qdrant cosine similarity search on `v6_cache_vectors` (threshold 0.92)
3. On miss: run full graph, store result in both Redis + Qdrant

## Conversation Memory Integration

`session_id` flows through the entire pipeline:

- Loaded into `GraphState.conversation_history` before graph starts
- `understand` node has access to previous turns for follow-up detection
- After graph completes: user query + assistant answer appended to Redis session
- Session TTL: 24h, max 10 turns (sliding window)
