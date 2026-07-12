# NLM Knowledge Fabric Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire NotebookLM notebooks into the RAG pipeline as a parallel enrichment layer, giving clients a "team of specialists verified this" experience with expandable normative citations.

**Architecture:** Parallel speculative pattern — NLM query fires alongside ReAct loop, merges only if evidence_score lands in CAUTIOUS zone (0.15-0.60). Three independent subsystems: HTTP bridge on Pro Mac, backend pipeline integration, frontend UX components.

**Tech Stack:** Python/FastAPI (bridge), Python/asyncio (pipeline), TypeScript/React (frontend), Redis (cache), Tailscale (networking)

**Spec:** `docs/superpowers/specs/2026-03-25-nlm-knowledge-fabric-integration-design.md`

---

## File Structure

### New Files

| File                                                                            | Responsibility                                |
| ------------------------------------------------------------------------------- | --------------------------------------------- |
| `apps/nlm-bridge/main.py`                                                       | HTTP bridge wrapping notebooklm-tools library |
| `apps/nlm-bridge/com.balizero.nlm-bridge.plist`                                 | macOS LaunchAgent for auto-restart            |
| `apps/backend-rag/backend/services/oracle/nlm_notebook_registry.py`             | Domain→notebook_id mapping + keyword resolver |
| `apps/backend-rag/backend/services/oracle/nlm_enrichment_service.py`            | Async HTTP client for bridge + HMAC signing   |
| `apps/mouth/src/components/chat/NLMCitationPanel.tsx`                           | Collapsible citation panel below message      |
| `apps/backend-rag/backend/tests/unit/services/oracle/test_notebook_registry.py` | Registry tests                                |
| `apps/backend-rag/backend/tests/unit/services/oracle/test_nlm_enrichment.py`    | Enrichment service tests                      |

### Modified Files

| File                                                                           | What Changes                                  |
| ------------------------------------------------------------------------------ | --------------------------------------------- |
| `apps/backend-rag/backend/services/caching/notebooklm_cache_service.py`        | Add notebook_id to cache key hash             |
| `apps/backend-rag/backend/services/rag/agentic/reasoning.py`                   | Store `trusted_tools_used` on state (2 lines) |
| `apps/backend-rag/backend/services/rag/agentic/orchestrator_streaming_core.py` | Parallel NLM fire + late merge                |
| `apps/backend-rag/backend/services/rag/agentic/orchestrator_streaming.py`      | Extend `create_done_event` signature          |
| `apps/backend-rag/backend/services/rag/agentic/orchestrator_core.py`           | Non-streaming NLM enrichment path             |
| `apps/backend-rag/backend/app/setup/service_initializer.py`                    | Wire NLM service + feature flag               |
| `apps/mouth/src/lib/api/chat/chat.api.ts`                                      | Fix metadata overwrite + NLM event handlers   |
| `apps/mouth/src/hooks/useChatStreaming.ts`                                     | Pass through ALL metadata fields              |
| `apps/mouth/src/types/index.ts`                                                | Extend Message metadata type                  |
| `apps/mouth/src/components/chat/MessageBubble.tsx`                             | TeamVerificationBadge + NLM states            |

---

## Phase 1: Prerequisites — Fix Frontend Metadata Pipeline

These fixes are **mandatory before** NLM integration. They fix existing bugs that block metadata flow.

### Task 1: Fix metadata overwrite bug in chat.api.ts

**Files:**

- Modify: `apps/mouth/src/lib/api/chat/chat.api.ts:561`

- [ ] **Step 1: Read the current metadata handler**

Read `apps/mouth/src/lib/api/chat/chat.api.ts` around line 561 to confirm the overwrite pattern: `finalMetadata = data.data` (replace, not merge).

- [ ] **Step 2: Fix to merge instead of replace**

Change line 561 from:

```typescript
finalMetadata = isRecord(data.data) ? data.data : undefined;
```

to:

```typescript
finalMetadata = isRecord(data.data)
  ? { ...(finalMetadata ?? {}), ...data.data }
  : finalMetadata;
```

- [ ] **Step 3: Verify no regression**

Run: `cd apps/mouth && npm run build`
Expected: Build succeeds with no errors.

- [ ] **Step 4: Commit**

```bash
git add apps/mouth/src/lib/api/chat/chat.api.ts
git commit -m "fix(chat): merge metadata events instead of overwriting

Multiple metadata events (entities, persistence, NLM enrichment) now
accumulate instead of the last one winning."
```

### Task 2: Fix metadata field filtering in useChatStreaming.ts

**Files:**

- Modify: `apps/mouth/src/hooks/useChatStreaming.ts:107-111`

- [ ] **Step 1: Read the current metadata extraction**

Read `apps/mouth/src/hooks/useChatStreaming.ts` around lines 107-111 to confirm only `conversation_id`, `execution_time`, `persisted` are forwarded.

- [ ] **Step 2: Pass through all metadata fields**

Change the selective extraction to spread all fields:

```typescript
// Before: only 3 fields extracted
const metadata = {
  conversation_id: rawMeta.conversation_id,
  execution_time: rawMeta.execution_time,
  persisted: rawMeta.persisted,
};

// After: pass through everything
const metadata = { ...rawMeta };
```

- [ ] **Step 3: Verify build**

Run: `cd apps/mouth && npm run build`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add apps/mouth/src/hooks/useChatStreaming.ts
git commit -m "fix(chat): pass all metadata fields through streaming hook

Previously only conversation_id, execution_time, persisted survived.
Now all backend metadata reaches the Message object."
```

### Task 3: Extend Message type for NLM metadata

**Files:**

- Modify: `apps/mouth/src/types/index.ts`

- [ ] **Step 1: Read the current Message type**

Read `apps/mouth/src/types/index.ts` around line 53-78 to find the `Message` interface and its metadata fields.

- [ ] **Step 2: Add NLM-related optional fields**

Add to the Message interface (or its metadata sub-type):

```typescript
// NLM Knowledge Fabric enrichment (optional)
nlm_status?: 'consulting' | 'verified' | 'not_needed';
nlm_domain_label?: string;
nlm_citations?: Array<{
  source_file: string;
  section: string;
  excerpt: string;
  page?: number;
}>;
evidence_score?: number;
confidence_zone?: 'abstain' | 'cautious' | 'confident';
```

- [ ] **Step 3: Verify build**

Run: `cd apps/mouth && npm run build`
Expected: Build succeeds (new fields are optional, no breaking changes).

- [ ] **Step 4: Commit**

```bash
git add apps/mouth/src/types/index.ts
git commit -m "feat(types): add NLM enrichment fields to Message type

Optional fields for evidence_score, confidence_zone, nlm_status,
nlm_domain_label, and nlm_citations."
```

---

## Phase 2: NLM HTTP Bridge (Pro Mac)

Independent from backend/frontend. Can be tested with `curl`.

### Task 4: Notebook Registry + tests

**Files:**

- Create: `apps/backend-rag/backend/services/oracle/nlm_notebook_registry.py`
- Create: `apps/backend-rag/backend/tests/unit/services/oracle/test_notebook_registry.py`

- [ ] **Step 1: Write the failing tests**

```python
# test_notebook_registry.py
from backend.services.oracle.nlm_notebook_registry import resolve_notebook, NLM_NOTEBOOKS

def test_resolve_immigration_query():
    result = resolve_notebook("What are the KITAS requirements?")
    assert result is not None
    assert result["domain"] == "immigration"
    assert result["notebook_id"] == "84375bc3-12d0-4405-a774-9b89189d8c39"

def test_resolve_company_query():
    result = resolve_notebook("How to set up a PT PMA in Bali?")
    assert result is not None
    assert result["domain"] == "company"

def test_resolve_no_domain():
    result = resolve_notebook("Hello, how are you?")
    assert result is None

def test_resolve_multi_domain_picks_best():
    result = resolve_notebook("I need a KITAS for my restaurant business")
    assert result is not None
    # "KITAS" matches immigration, "restaurant business" matches company
    # Should pick the domain with more keyword hits

def test_all_notebooks_have_required_fields():
    for domain, data in NLM_NOTEBOOKS.items():
        assert "notebook_id" in data
        assert "label" in data
        assert "keywords" in data
        assert len(data["keywords"]) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/oracle/test_notebook_registry.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement the registry**

Create `backend/services/oracle/nlm_notebook_registry.py` with `NLM_NOTEBOOKS` dict and `resolve_notebook(query: str) -> dict | None` function. Use keyword overlap scoring — count how many keywords from each domain appear in the lowercased query, return the highest-scoring domain or None if no matches.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/oracle/test_notebook_registry.py -v`
Expected: 5/5 PASS

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/services/oracle/nlm_notebook_registry.py
git add apps/backend-rag/backend/tests/unit/services/oracle/test_notebook_registry.py
git commit -m "feat(oracle): add NLM notebook registry with keyword-based domain resolver"
```

### Task 5: Fix cache key to include notebook_id

**Files:**

- Modify: `apps/backend-rag/backend/services/caching/notebooklm_cache_service.py`

- [ ] **Step 1: Read the current `_hash_question` method**

Read `apps/backend-rag/backend/services/caching/notebooklm_cache_service.py` around lines 70-91.

- [ ] **Step 2: Add notebook_id parameter**

Modify `_hash_question` to accept an optional `notebook_id` parameter and include it in the hash:

```python
def _hash_question(self, question: str, notebook_id: str = "") -> str:
    normalized = question.lower().strip()
    normalized = normalized.replace("?", "").replace("!", "").replace(".")
    key_input = f"{notebook_id}:{normalized}" if notebook_id else normalized
    return hashlib.md5(key_input.encode()).hexdigest()
```

Update `get()` and `set()` methods to accept and pass through `notebook_id`.

- [ ] **Step 3: Verify existing tests still pass**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/ -k "notebooklm" -v`
Expected: Existing tests pass (notebook_id defaults to "" → same hash as before).

- [ ] **Step 4: Commit**

```bash
git add apps/backend-rag/backend/services/caching/notebooklm_cache_service.py
git commit -m "fix(cache): include notebook_id in NLM cache key to prevent cross-domain collisions"
```

### Task 6: NLM HTTP Bridge service

**Files:**

- Create: `apps/nlm-bridge/main.py`
- Create: `apps/nlm-bridge/requirements.txt`

- [ ] **Step 1: Create the bridge directory**

```bash
mkdir -p apps/nlm-bridge
```

- [ ] **Step 2: Write requirements.txt**

```
fastapi>=0.115.0
uvicorn>=0.34.0
httpx>=0.28.0
pydantic>=2.10.0
```

- [ ] **Step 3: Implement the bridge**

Create `apps/nlm-bridge/main.py` with:

- `POST /nlm/query` endpoint accepting `{notebook_id, question, timeout}`
- `GET /nlm/health` endpoint returning auth status + uptime
- HMAC signature verification via `X-Bridge-Signature` header
- Rate limiting: 10 req/min via in-memory counter
- Import `notebooklm_tools` library for querying (not subprocess)
- Shell to `nlm_auth_bridge.ensure_nlm_auth()` for auth recovery
- Structured logging with `logging` module
- Lifespan handler for startup/shutdown

Reference: `apps/federation/nlm_auth_bridge.py` for auth patterns.

- [ ] **Step 4: Test with curl locally**

```bash
cd apps/nlm-bridge
pip install -r requirements.txt
uvicorn main:app --port 18790 &

# Health check
curl http://localhost:18790/nlm/health
# Expected: {"status":"healthy","mcp_alive":true,...}

# Query (needs valid HMAC — test without signature first)
curl -X POST http://localhost:18790/nlm/query \
  -H "Content-Type: application/json" \
  -d '{"notebook_id":"f6ecd115-dd89-4c9b-b3dd-071e0e2f1876","question":"What is the project structure?","timeout":15}'
# Expected: {"answer":"...","citations":[...],"confidence":0.8,"processing_time":4.2}
```

- [ ] **Step 5: Commit**

```bash
git add apps/nlm-bridge/
git commit -m "feat(nlm-bridge): HTTP bridge wrapping notebooklm-tools for Fly.io access"
```

### Task 7: LaunchAgent for bridge persistence

**Files:**

- Create: `apps/nlm-bridge/com.balizero.nlm-bridge.plist`

- [ ] **Step 1: Create the LaunchAgent plist**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.balizero.nlm-bridge</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/nuzantara/Desktop/nuzantara/apps/nlm-bridge/.venv/bin/uvicorn</string>
        <string>main:app</string>
        <string>--host</string>
        <string>0.0.0.0</string>
        <string>--port</string>
        <string>18790</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/nuzantara/Desktop/nuzantara/apps/nlm-bridge</string>
    <key>KeepAlive</key>
    <true/>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/nlm-bridge.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/nlm-bridge.err</string>
</dict>
</plist>
```

- [ ] **Step 2: Install and verify**

```bash
cp apps/nlm-bridge/com.balizero.nlm-bridge.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.balizero.nlm-bridge.plist
sleep 2
curl http://localhost:18790/nlm/health
# Expected: {"status":"healthy",...}
```

- [ ] **Step 3: Commit**

```bash
git add apps/nlm-bridge/com.balizero.nlm-bridge.plist
git commit -m "ops(nlm-bridge): add LaunchAgent for auto-restart on Pro Mac"
```

---

## Phase 3: Backend Pipeline Integration

Depends on Phase 2 (bridge must be running for integration tests).

### Task 8: NLM Enrichment Service + tests

**Files:**

- Create: `apps/backend-rag/backend/services/oracle/nlm_enrichment_service.py`
- Create: `apps/backend-rag/backend/tests/unit/services/oracle/test_nlm_enrichment.py`

- [ ] **Step 1: Write the failing tests**

```python
# test_nlm_enrichment.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.services.oracle.nlm_enrichment_service import NLMEnrichmentService

@pytest.fixture
def service():
    return NLMEnrichmentService(
        bridge_url="http://localhost:18790",
        bridge_secret="test-secret",
    )

@pytest.mark.asyncio
async def test_query_success(service):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "answer": "KITAS requires...",
        "citations": [{"source_file": "UU.pdf", "section": "Pasal 48", "excerpt": "...", "page": 23}],
        "confidence": 0.82,
        "processing_time": 4.2,
    }
    with patch.object(service._client, "post", new_callable=AsyncMock, return_value=mock_response):
        result = await service.query("nb-id-123", "What is KITAS?")
    assert result["answer"] == "KITAS requires..."
    assert len(result["citations"]) == 1

@pytest.mark.asyncio
async def test_query_timeout(service):
    import httpx
    with patch.object(service._client, "post", new_callable=AsyncMock, side_effect=httpx.TimeoutException("timeout")):
        result = await service.query("nb-id-123", "question")
    assert result is None

@pytest.mark.asyncio
async def test_query_bridge_down(service):
    import httpx
    with patch.object(service._client, "post", new_callable=AsyncMock, side_effect=httpx.ConnectError("refused")):
        result = await service.query("nb-id-123", "question")
    assert result is None

@pytest.mark.asyncio
async def test_hmac_signature_included(service):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"answer": "...", "citations": [], "confidence": 0.5, "processing_time": 1.0}
    with patch.object(service._client, "post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
        await service.query("nb-id", "question")
    call_kwargs = mock_post.call_args
    assert "X-Bridge-Signature" in call_kwargs.kwargs.get("headers", {})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/oracle/test_nlm_enrichment.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement the enrichment service**

Create `backend/services/oracle/nlm_enrichment_service.py`:

- Async `query(notebook_id, question, timeout=10)` → `dict | None`
- HMAC signing of request body
- `httpx.AsyncClient` with persistent connection (pattern: `_get_client`)
- Graceful error handling: timeout → None, connection error → None
- Structured logging

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/oracle/test_nlm_enrichment.py -v`
Expected: 4/4 PASS

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/services/oracle/nlm_enrichment_service.py
git add apps/backend-rag/backend/tests/unit/services/oracle/test_nlm_enrichment.py
git commit -m "feat(oracle): add NLM enrichment service with HMAC signing and graceful fallback"
```

### Task 9: Store trusted_tools_used on state in reasoning.py

**Files:**

- Modify: `apps/backend-rag/backend/services/rag/agentic/reasoning.py`

- [ ] **Step 1: Find the policy enforcement block in streaming path**

Read `reasoning.py` around line 1460-1470 — after the `has_tools` check where `trusted_tools_used` is finalized.

- [ ] **Step 2: Add 2 lines to store on state**

After the policy enforcement block in BOTH paths (streaming ~line 1465, non-streaming ~line 660):

```python
# Store for downstream NLM enrichment decision
state.trusted_tools_used = trusted_tools_used
```

- [ ] **Step 3: Run core tests**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/rag/agentic/test_orchestrator.py -v --tb=short`
Expected: All tests pass (new attribute is additive).

- [ ] **Step 4: Commit**

```bash
git add apps/backend-rag/backend/services/rag/agentic/reasoning.py
git commit -m "feat(reasoning): expose trusted_tools_used on state for NLM enrichment"
```

### Task 10: Extend create_done_event signature

**Files:**

- Modify: `apps/backend-rag/backend/services/rag/agentic/orchestrator_streaming.py`

- [ ] **Step 1: Read create_done_event at line 221-242**

Read the current signature and payload construction.

- [ ] **Step 2: Add evidence_score and confidence_zone parameters**

```python
def create_done_event(
    self,
    execution_time: float,
    route_used: str,
    evidence_score: float | None = None,
    confidence_zone: str | None = None,
) -> dict:
    data = {
        "execution_time": round(execution_time, 2),
        "route_used": route_used,
    }
    if evidence_score is not None:
        data["evidence_score"] = round(evidence_score, 3)
    if confidence_zone is not None:
        data["confidence_zone"] = confidence_zone
    return {"type": "done", "data": data}
```

- [ ] **Step 3: Verify existing callers still work (default params)**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/rag/agentic/ -v --tb=short -q`
Expected: All tests pass (new params are optional with defaults).

- [ ] **Step 4: Commit**

```bash
git add apps/backend-rag/backend/services/rag/agentic/orchestrator_streaming.py
git commit -m "feat(streaming): extend done event with evidence_score and confidence_zone"
```

### Task 11: Wire NLM service in service_initializer + feature flag

**Files:**

- Modify: `apps/backend-rag/backend/app/setup/service_initializer.py`

- [ ] **Step 1: Read service_initializer.py to find the pattern**

Find where other services are initialized (around line 540+) and follow the same pattern.

- [ ] **Step 2: Add NLM enrichment service initialization**

```python
# NLM Enrichment Service (feature-flagged)
nlm_enrichment_enabled = os.getenv("ENABLE_NLM_ENRICHMENT", "false").lower() in ("true", "1")
if nlm_enrichment_enabled:
    from backend.services.oracle.nlm_enrichment_service import NLMEnrichmentService
    nlm_service = NLMEnrichmentService(
        bridge_url=os.getenv("NLM_BRIDGE_URL", "http://100.107.22.111:18790"),
        bridge_secret=os.getenv("NLM_BRIDGE_SECRET", ""),
    )
    app.state.nlm_enrichment_service = nlm_service
    logger.info("✅ NLM Enrichment Service initialized (ENABLE_NLM_ENRICHMENT=true)")
else:
    app.state.nlm_enrichment_service = None
    logger.info("⚠️ NLM Enrichment Service DISABLED")
```

Pass `nlm_enrichment_service` to `OrchestratorCore` and `OrchestratorStreamingCore` constructors.

- [ ] **Step 3: Verify startup with flag OFF**

Run: `cd apps/backend-rag && PYTHONPATH=. python -c "from backend.app.dependencies import get_current_user; print('OK')"`
Expected: OK (import chain unbroken).

- [ ] **Step 4: Commit**

```bash
git add apps/backend-rag/backend/app/setup/service_initializer.py
git commit -m "feat(init): wire NLM enrichment service with ENABLE_NLM_ENRICHMENT feature flag"
```

### Task 12: Pipeline insertion — parallel speculative NLM in streaming core

**Files:**

- Modify: `apps/backend-rag/backend/services/rag/agentic/orchestrator_streaming_core.py`

- [ ] **Step 1: Read orchestrator_streaming_core.py to map insertion points**

Read the full file. Identify:

- Line ~214: where ReAct loop starts
- Line ~269: where `create_done_event` is called
- Where `state.evidence_score` and `state.trusted_tools_used` are accessible

- [ ] **Step 2: Add NLM parallel fire (Point 1, before ReAct loop)**

After domain detection, before the ReAct loop call:

```python
# NLM Speculative Fire (parallel with ReAct loop)
nlm_task = None
nlm_cached_result = None
nlm_domain = None
if self.core.nlm_enrichment_service:
    from backend.services.oracle.nlm_notebook_registry import resolve_notebook
    nlm_match = resolve_notebook(query)
    if nlm_match:
        nlm_domain = nlm_match
        # Check cache first
        if self.core.faq_cache:
            nlm_cached_result = await self.core.faq_cache.get(
                query, notebook_id=nlm_match["notebook_id"]
            )
        if not nlm_cached_result:
            nlm_task = asyncio.create_task(
                self.core.nlm_enrichment_service.query(
                    nlm_match["notebook_id"], query
                )
            )
        # Emit consulting status
        yield {"type": "nlm_status", "data": {
            "status": "consulting",
            "domain_label": nlm_match["label"],
        }}
```

- [ ] **Step 3: Add NLM late merge (Point 2, before done event)**

Before `create_done_event`:

```python
# NLM Late Merge
nlm_result = None
evidence_score = getattr(state, "evidence_score", None)
trusted = getattr(state, "trusted_tools_used", True)
cautious = (evidence_score is not None
            and 0.15 <= evidence_score <= 0.60
            and not trusted)

if cautious and (nlm_cached_result or nlm_task):
    try:
        nlm_result = nlm_cached_result or await asyncio.wait_for(nlm_task, timeout=3.0)
    except (asyncio.TimeoutError, asyncio.CancelledError, Exception) as e:
        logger.warning(f"NLM enrichment skipped: {e}")
elif nlm_task and not nlm_task.done():
    nlm_task.cancel()

if nlm_result and nlm_domain:
    yield {"type": "nlm_enrichment", "data": {
        "domain": nlm_domain["domain"] if isinstance(nlm_domain, dict) else nlm_domain,
        "domain_label": nlm_domain.get("label", ""),
        "citations": nlm_result.get("citations", []),
        "summary": nlm_result.get("answer", ""),
    }}
    # Cache for next time
    if self.core.faq_cache and not nlm_cached_result:
        await self.core.faq_cache.set(
            query, nlm_result.get("answer", ""),
            metadata=nlm_result,
            notebook_id=nlm_domain.get("notebook_id", ""),
        )

# Compute confidence zone for done event
confidence_zone = "confident"
if evidence_score is not None:
    if evidence_score < 0.15:
        confidence_zone = "abstain"
    elif evidence_score <= 0.60 and not trusted:
        confidence_zone = "cautious"
```

Pass `evidence_score` and `confidence_zone` to `create_done_event()`.

- [ ] **Step 4: Run orchestrator tests**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/rag/agentic/test_orchestrator.py -v --tb=short`
Expected: All existing tests pass (NLM service is None → all NLM code paths skip).

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/services/rag/agentic/orchestrator_streaming_core.py
git commit -m "feat(pipeline): add parallel speculative NLM enrichment in streaming path"
```

### Task 13: Non-streaming path in orchestrator_core.py

**Files:**

- Modify: `apps/backend-rag/backend/services/rag/agentic/orchestrator_core.py`

- [ ] **Step 1: Read orchestrator_core.py to find the non-streaming query path**

Find `process_query_core()` and where `CoreResult` is constructed.

- [ ] **Step 2: Add NLM enrichment before returning CoreResult**

Same pattern as streaming: fire NLM at start, merge at end if CAUTIOUS. Add NLM citations to `CoreResult.sources` and enrichment metadata to the result.

- [ ] **Step 3: Run tests**

Run: `cd apps/backend-rag && PYTHONPATH=. pytest backend/tests/unit/services/rag/agentic/ -v --tb=short -q`
Expected: All pass.

- [ ] **Step 4: Commit**

```bash
git add apps/backend-rag/backend/services/rag/agentic/orchestrator_core.py
git commit -m "feat(pipeline): add NLM enrichment to non-streaming query path"
```

---

## Phase 4: Frontend UX — "Team of Specialists"

### Task 14: SSE event handlers for nlm_status and nlm_enrichment

**Files:**

- Modify: `apps/mouth/src/lib/api/chat/chat.api.ts`

- [ ] **Step 1: Read the SSE parser if/else chain**

Read `chat.api.ts` around lines 380-584 to understand the event dispatch pattern.

- [ ] **Step 2: Add handlers for new event types**

Add after the existing handlers (before the final else):

```typescript
} else if (data.type === "nlm_status") {
  // NLM consulting status — show "team is verifying" indicator
  if (callbacks?.onStep) {
    callbacks.onStep({ type: "nlm_status", data: data.data });
  }
  // Store in metadata for Message
  finalMetadata = { ...(finalMetadata ?? {}), nlm_status: data.data.status, nlm_domain_label: data.data.domain_label };
} else if (data.type === "nlm_enrichment") {
  // NLM citations arrived — store for Message
  finalMetadata = {
    ...(finalMetadata ?? {}),
    nlm_status: "verified",
    nlm_citations: data.data.citations,
    nlm_domain_label: data.data.domain_label,
  };
  if (callbacks?.onStep) {
    callbacks.onStep({ type: "nlm_enrichment", data: data.data });
  }
} else if (data.type === "evidence_score") {
  // Evidence score from backend — store for verification badge
  finalMetadata = { ...(finalMetadata ?? {}), evidence_score: data.data.score };
```

- [ ] **Step 3: Verify build**

Run: `cd apps/mouth && npm run build`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add apps/mouth/src/lib/api/chat/chat.api.ts
git commit -m "feat(chat): add SSE handlers for nlm_status, nlm_enrichment, evidence_score events"
```

### Task 15: TeamVerificationBadge in MessageBubble

**Files:**

- Modify: `apps/mouth/src/components/chat/MessageBubble.tsx`

- [ ] **Step 1: Read existing VerificationBadge (lines 44-76)**

Understand the current 3-tier badge (green/yellow/red based on numeric score).

- [ ] **Step 2: Extend with NLM team states**

Replace or extend `VerificationBadge` to accept `nlm_status`, `nlm_domain_label`, `confidence_zone` from message metadata. Implement 3 visual states:

1. **Consulting** (pulsing): `👥 I nostri specialisti {domain} stanno verificando...`
2. **Verified** (gold): `👥 Verificato dal team {domain}` — clickable, expands citations
3. **Fade** (on done without enrichment): opacity transition to 0

Use CSS animation for pulse:

```css
@keyframes pulse-soft {
  0%,
  100% {
    opacity: 0.6;
  }
  50% {
    opacity: 1;
  }
}
```

Color: `var(--bz-accent, #d4845a)` for verified state.
Icon: `Users` from `lucide-react`.

- [ ] **Step 3: Wire badge rendering in MessageBubble**

After the existing VerificationBadge render (around line 507-509), add the NLM team badge:

```typescript
{message.metadata?.nlm_status && (
  <TeamVerificationBadge
    status={message.metadata.nlm_status}
    domainLabel={message.metadata.nlm_domain_label}
    onExpand={() => setShowCitations(prev => !prev)}
  />
)}
```

- [ ] **Step 4: Verify build**

Run: `cd apps/mouth && npm run build`
Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add apps/mouth/src/components/chat/MessageBubble.tsx
git commit -m "feat(chat): add TeamVerificationBadge with consulting/verified/fade states"
```

### Task 16: NLMCitationPanel component

**Files:**

- Create: `apps/mouth/src/components/chat/NLMCitationPanel.tsx`

- [ ] **Step 1: Create the citation panel component**

Collapsible panel with gold accent border (`--bz-accent`). Shows citations from NLM with source file, section, excerpt. Collapsed by default.

```typescript
interface NLMCitationPanelProps {
  citations: Array<{
    source_file: string;
    section: string;
    excerpt: string;
    page?: number;
  }>;
  domainLabel: string;
  expanded: boolean;
  onToggle: () => void;
}
```

Use existing Tailwind classes + `--bz-accent` for the gold border. Follow `CitationCard.tsx` visual language but with NLM-specific fields.

- [ ] **Step 2: Wire into MessageBubble**

Import and render below the answer text, conditionally when `nlm_citations` exist:

```typescript
{showCitations && message.metadata?.nlm_citations?.length > 0 && (
  <NLMCitationPanel
    citations={message.metadata.nlm_citations}
    domainLabel={message.metadata.nlm_domain_label ?? ""}
    expanded={showCitations}
    onToggle={() => setShowCitations(false)}
  />
)}
```

- [ ] **Step 3: Verify build**

Run: `cd apps/mouth && npm run build`
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add apps/mouth/src/components/chat/NLMCitationPanel.tsx
git add apps/mouth/src/components/chat/MessageBubble.tsx
git commit -m "feat(chat): add NLMCitationPanel with expandable normative citations"
```

---

## Phase 5: Integration Test + Deploy

### Task 17: End-to-end verification

- [ ] **Step 1: Verify bridge is running on Pro**

```bash
curl http://localhost:18790/nlm/health
# Expected: {"status":"healthy","mcp_alive":true}
```

- [ ] **Step 2: Deploy backend with feature flag OFF**

```bash
cd apps/backend-rag && fly deploy --strategy rolling
# Verify: ENABLE_NLM_ENRICHMENT is NOT set → NLM disabled
```

- [ ] **Step 3: Run import chain check**

```bash
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('OK')"
```

- [ ] **Step 4: Deploy frontend**

```bash
git push origin main
# Vercel auto-deploys. Verify kita.balizero.com loads.
```

- [ ] **Step 5: Enable NLM on Fly.io**

```bash
fly secrets set ENABLE_NLM_ENRICHMENT=true NLM_BRIDGE_URL=http://100.107.22.111:18790 NLM_BRIDGE_SECRET=<secret> -a nuzantara-rag
```

- [ ] **Step 6: Test with a CAUTIOUS-zone query**

Open `https://kita.balizero.com` chat, ask a borderline question that would trigger CAUTIOUS. Watch for:

- Consulting indicator appears during streaming
- If NLM returns: citations panel appears with gold badge
- If NLM doesn't return: indicator fades silently

- [ ] **Step 7: Commit any fixes**

```bash
git add -A && git commit -m "fix: integration adjustments from E2E testing"
```
