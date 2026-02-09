# Phase 3b: Conditional Workflows - Implementation Brief

**Assigned to:** Available AI Agent
**Priority:** HIGH (fixes existing test failures)
**Estimated Effort:** 2-3 hours
**Dependencies:** Phase 1, Phase 2 (Confidence Scoring)

---

## Objective

Fix failing tests in `test_conditional_workflows.py` and complete conditional routing implementation.

---

## Current Status

**Test Results:** 12/20 passing, 8 failing, 2 skipped

**Root Causes:**
1. `detect_team_query()` API changed: returns `(bool, str, str)` tuple instead of `bool`
2. Workflow routing logic not implemented (`select_workflow()` always returns 'team_management')
3. Tool selection logic incomplete (`select_tools()` missing 'web_search')

---

## Tasks

### Task 1: Fix API Compatibility (30 min)

**File:** `backend/services/rag/agentic/query_gates.py`

**Option A - Revert to bool:**
```python
def detect_team_query(query: str) -> bool:
    """Returns True if query is about team/people."""
    patterns = [r'\bwho is\b', r'\bworking on\b', r'\bassigned to\b']
    return any(re.search(p, query.lower()) for p in patterns)
```

**Option B - Update tests to handle tuple:**
```python
# In test_conditional_workflows.py
def test_detect_team_query_positive():
    is_team, method, match = detect_team_query(query)
    assert is_team is True  # ← Change assertion
```

**Recommendation:** Option A (simpler, less breaking changes)

---

### Task 2: Implement Workflow Selection (60 min)

**File:** `backend/services/rag/agentic/query_gates.py`

```python
def select_workflow(query: str, user_context: dict) -> str:
    """
    Select workflow path based on query complexity and domain.

    Returns:
        - 'fast_path': Simple factual queries
        - 'full_reasoning': Complex multi-step queries
        - 'critical_verification': Tax/legal/compliance domains
        - 'team_management': Team/people queries
    """
    query_lower = query.lower()

    # Team queries
    if detect_team_query(query):
        return 'team_management'

    # Critical domains (tax, legal, compliance)
    critical_keywords = ['tax', 'pajak', 'legal', 'hukum', 'compliance', 'peraturan']
    if any(kw in query_lower for kw in critical_keywords):
        return 'critical_verification'

    # Simple queries (what, when, where with < 10 words)
    simple_patterns = [r'^\s*(what|apa|when|kapan|where|dimana)\s+\w+']
    if any(re.match(p, query_lower) for p in simple_patterns) and len(query.split()) < 10:
        return 'fast_path'

    # Default: full reasoning for complex queries
    return 'full_reasoning'
```

**Test Coverage:**
- `test_workflow_selection_simple_query` → 'fast_path'
- `test_workflow_selection_complex_query` → 'full_reasoning'
- `test_workflow_selection_critical_domain` → 'critical_verification'
- `test_workflow_selection_team_query` → 'team_management' ✅ (already passing)

---

### Task 3: Implement Tool Selection (45 min)

**File:** `backend/services/rag/agentic/query_gates.py`

```python
def select_tools(query: str, workflow: str) -> list[str]:
    """
    Select tools based on query and workflow path.

    Available tools:
        - knowledge_base_search: RAG retrieval
        - web_search: Real-time web search
        - kg_traversal: Knowledge graph traversal
        - pricing_tool: Bali Zero pricing
        - team_database: Team member search
        - task_tracker: Practice status
    """
    tools = ['knowledge_base_search']  # Always include KB search

    query_lower = query.lower()

    # Workflow-specific tools
    if workflow == 'team_management':
        tools.extend(['team_database', 'task_tracker'])

    # Domain-specific tools
    if any(kw in query_lower for kw in ['visa', 'kitas', 'kitap']):
        tools.append('kg_traversal')

    if any(kw in query_lower for kw in ['tax', 'pajak', 'pph', 'ppn']):
        tools.append('kg_traversal')

    if any(kw in query_lower for kw in ['price', 'cost', 'harga', 'biaya']):
        tools.append('pricing_tool')

    # Add web_search for general queries (not team/internal)
    if workflow not in ['team_management'] and 'web_search' not in tools:
        tools.append('web_search')

    return tools
```

**Test Coverage:**
- `test_tool_selection_for_visa_query` → includes 'kg_traversal' ✅
- `test_tool_selection_for_tax_query` → includes 'kg_traversal' ✅
- `test_tool_selection_for_general_query` → includes 'web_search' ❌ (currently failing)
- `test_tool_selection_for_team_query` → includes 'team_database' ✅

---

### Task 4: Fix QueryGates Initialization (15 min)

**File:** `backend/services/rag/agentic/query_gates.py`

**Current Issue:** Tests fail with `TypeError: QueryGates.__init__() missing 1 required positional argument: 'prompt_builder'`

**Fix:**
```python
class QueryGates:
    def __init__(self, prompt_builder=None):  # ← Make optional
        self.prompt_builder = prompt_builder
```

**Or update test fixture:**
```python
# In test_conditional_workflows.py
@pytest.fixture
def query_gates():
    from backend.services.rag.agentic.prompt_builder import PromptBuilder
    prompt_builder = PromptBuilder()
    return QueryGates(prompt_builder)
```

**Recommendation:** Make `prompt_builder` optional in `__init__`

---

## Test Execution

```bash
cd apps/backend-rag
python -m pytest backend/tests/services/rag/test_conditional_workflows.py -v
```

**Expected Result:** 20/20 passing (all green)

---

## Success Criteria

✅ All 20 tests passing
✅ No test skipped (run integration tests if possible)
✅ Workflow routing works for all 4 paths
✅ Tool selection includes web_search for general queries
✅ QueryGates can be initialized without prompt_builder

---

## Files to Modify

| File | Changes | Lines |
|------|---------|-------|
| `backend/services/rag/agentic/query_gates.py` | Implement workflow/tool selection | ~150 |
| `backend/tests/services/rag/test_conditional_workflows.py` | Fix assertions (if Option B chosen) | ~20 |

**Total Effort:** ~150-170 lines

---

## Notes

- **Don't over-engineer:** Keep logic simple, pattern-based
- **No LLM calls:** This is rules-based routing (fast!)
- **Backward compatible:** Existing code should not break
- **Document patterns:** Add comments for keyword lists

---

**Ready to implement?** Run tests first to confirm current state, then fix one task at a time.
