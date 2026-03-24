# NLM Knowledge Fabric Integration — Design Spec

**Date:** 2026-03-25
**Status:** Draft v2 — Post-Review, Parallel Architecture
**Authors:** Claude Opus 4.6 (synthesis), Gemini 3.1 Pro, DeepSeek R1 671b
**Reviewers:** Gemini 3.1 Pro (critical), DeepSeek R1 (red team), Claude Opus (code architect)

---

## 1. Problem

Zantara's RAG pipeline answers ~85% of queries with high confidence (evidence score > 0.60). But ~15% of queries land in the **CAUTIOUS zone** (score 0.15-0.60) — the system has some relevant context but not enough to be confident. These queries currently get a weaker answer with no external validation.

Meanwhile, 8 NotebookLM notebooks sit unused in production, each loaded with verified domain documents (immigration law, tax codes, company regulations, property rules, etc.) that could validate and enrich these uncertain answers.

**Goal:** When the RAG pipeline is uncertain, consult the relevant NLM notebook to validate the answer and surface official source citations — making the client feel that a **team of domain specialists** reviewed the response.

---

## 2. Architecture Overview — Parallel "Specialist Team" Pattern

### Core Concept

Zantara answers immediately (RAG, ~4.5s). In **parallel**, the relevant NLM notebook is already being consulted. If the answer turns out to need reinforcement (CAUTIOUS zone), the NLM citations arrive moments later as a **supplementary enrichment** — giving the client the impression that a team of domain specialists verified the response.

If the answer is confident (NORMAL zone), the speculative NLM call is silently discarded. If the bridge is unreachable, nothing changes — the answer stands on its own. **Zero regression risk.**

### Timing Diagram

```
t=0s    Query arrives
        ├── Domain detection (keywords, instant)
        ├── START NLM speculative query ──────────────────────┐
        │   (asyncio.Task, fire-and-forget)                   │
        │                                                     │
        ├── IntentClassifier → tier selection                 │
        ├── ReAct Loop begins                                 │
        │   ├── tool calls, Qdrant search                     │  NLM query
        │   ├── stream answer tokens to user ─── USER SEES    │  running in
        │   │   ANSWER HERE (no delay)                        │  background
        │   └── evidence_score calculated                     │  (3-8s)
        │                                                     │
t=4.5s  ReAct Loop complete                                   │
        │                                                     │
        ├── if CONFIDENT: cancel NLM task, emit done          │
        │                                                     │
        ├── if CAUTIOUS: await NLM task ◄─────────────────────┘
        │   (likely already finished — NLM took 3-8s,
        │    ReAct took 4.5s → overlap = ~4.5s hidden)
        │
        │   SSE: nlm_enrichment event (citations)
        │   SSE: done event
        │
t=5-6s  Frontend: badge transitions from "Consulting..." → "Verified"
```

**Net latency for CAUTIOUS queries: ~0-3s extra** (hidden behind ReAct loop)
**Waste for NORMAL queries: one free NLM call discarded** (~$0, rate limit allows ~600/day)

### System Diagram

```
┌─────────────────────────────────────────────────┐
│ Fly.io RAG Pipeline (Singapore)                 │
│                                                 │
│  1. Domain detection (keywords)                 │
│  2. Fire NLM speculative task (asyncio.Task)    │
│  3. QueryGates → IntentClassifier               │
│  4. ReAct Loop → stream answer tokens           │
│  5. Evidence Score calculated                   │
│     ├── CONFIDENT: cancel NLM task → done       │
│     └── CAUTIOUS: await NLM task                │
│         ├── if ready: emit nlm_enrichment       │
│         ├── if timeout (3s grace): skip         │
│         └── emit done                           │
└──────────────────┬──────────────────────────────┘
                   │ (Tailscale VPN)
                   ▼
┌─────────────────────────────────────────────────┐
│ Pro Mac — NLM HTTP Bridge (port 18790)          │
│                                                 │
│  POST /nlm/query                                │
│  → Redis cache check (30-day TTL)               │
│  → nlm_auth_bridge (auth check)                 │
│  → notebooklm-tools library (query)             │
│  → return {answer, citations, confidence}       │
│                                                 │
│  GET /nlm/health → auth + connectivity status   │
└─────────────────────────────────────────────────┘
                   │
                   ▼
           Google NLM (batchexecute RPC)
           3-8s per query, cookie auth
```

---

## 3. Component Design

### 3.1 NLM HTTP Bridge (Pro Mac)

**What:** Lightweight FastAPI service on Pro Mac that wraps `notebooklm-tools` library over HTTP.

**Where:** New directory `apps/nlm-bridge/` in monorepo, runs on Pro via LaunchAgent.

**Port:** 18790 (next to OpenClaw's 18789).

**Endpoints:**

| Method | Path          | Purpose              |
| ------ | ------------- | -------------------- |
| `POST` | `/nlm/query`  | Query a notebook     |
| `GET`  | `/nlm/health` | Health + auth status |

**POST /nlm/query request:**

```json
{
  "notebook_id": "84375bc3-12d0-4405-a774-9b89189d8c39",
  "question": "What are the KITAS requirements for 2026?",
  "timeout": 10
}
```

**POST /nlm/query response:**

```json
{
  "answer": "Based on UU No. 1/2026, KITAS requirements include...",
  "citations": [
    {
      "source_file": "UU_Nomor_1_Tahun_2026.pdf",
      "section": "Pasal 48, Ayat 2",
      "excerpt": "Izin tinggal terbatas diberikan kepada...",
      "page": 23
    }
  ],
  "confidence": 0.82,
  "processing_time": 4.2
}
```

**Key design decisions:**

- Import `notebooklm-tools` library directly (no subprocess shelling to `nlm` CLI)
- Call `nlm_auth_bridge.ensure_nlm_auth()` before each query (existing auth recovery)
- Rate limit: 10 req/min (respect Google's undocumented NLM quota)
- API key header: `X-Bridge-Key` shared secret between Fly.io and Pro
- Timeout: configurable per-request, default 10s, max 30s
- No CORS needed (server-to-server only via Tailscale)

**Failure modes:**
| Failure | Detection | Recovery |
|---------|-----------|----------|
| Pro asleep | 2s connection timeout | Fly.io falls back to Qdrant-only answer |
| NLM auth expired | `nlm_auth_bridge` detects | Auto-relogin via Chrome; if locked, Telegram alert |
| Google changes API | NLM library throws exception | Log error, fall back, wait for `nlm` update |
| Tailscale down | Connection refused | Same as Pro asleep — graceful fallback |

### 3.2 Notebook Registry (Backend)

**What:** Static Python dict mapping domains to NLM notebook IDs. Single source of truth replacing the bash `case` in `ai-dispatch.sh`.

**Where:** New file `backend/services/oracle/nlm_notebook_registry.py`

```python
NLM_NOTEBOOKS = {
    "immigration": {
        "notebook_id": "84375bc3-12d0-4405-a774-9b89189d8c39",
        "label": "Immigration & Visa",
        "keywords": {"visa", "kitas", "kitap", "tka", "immigration", "imigrasi",
                     "work permit", "stay permit", "foreigner", "expat"},
    },
    "company": {
        "notebook_id": "2e84b9b9-3b99-4bc5-8ec5-351a43c52df4",
        "label": "Company & Licensing",
        "keywords": {"company", "kbli", "pma", "oss", "licensing", "nib",
                     "investment", "business", "pt ", "perseroan"},
    },
    "tax": {
        "notebook_id": "837b620b-2aca-43ab-812e-97ca92bdad1d",
        "label": "Tax & Compliance",
        "keywords": {"tax", "compliance", "lkpm", "npwp", "pph", "ppn",
                     "coretax", "bpjs", "fiscal", "pajak"},
    },
    "property": {
        "notebook_id": "568ec624-ceb8-47d1-a2a2-5b2f793ea7ed",
        "label": "Property & Zoning",
        "keywords": {"property", "zoning", "land", "hgb", "hak pakai",
                     "building", "villa", "real estate", "leasehold"},
    },
    "operations": {
        "notebook_id": "3e1baa5f-680f-4499-9430-23a901576bcc",
        "label": "Operations",
        "keywords": {"sop", "team", "pricing", "crm", "workflow", "competitor"},
    },
    "editorial": {
        "notebook_id": "dd464d8f-6b8e-4543-8647-f62c498589b1",
        "label": "Editorial & Market",
        "keywords": {"seo", "content", "market", "intel", "trends", "news",
                     "article", "editorial"},
    },
    "lifestyle": {
        "notebook_id": "1143b525-dd3f-40d7-a34d-2e9263b44460",
        "label": "Expat Life",
        "keywords": {"lifestyle", "expat", "healthcare", "cost of living",
                     "culture", "digital nomad", "education", "school"},
    },
}
```

**`resolve_notebook(query: str) -> dict | None`** — matches query keywords against the registry, returns the best-matching notebook or `None` if no match.

**Multi-domain queries** (e.g., "open a restaurant and get a KITAS"): query the primary notebook only (highest keyword overlap). Querying multiple notebooks doubles latency for marginal benefit. If needed later, use `cross_notebook_query` MCP tool.

**Fallback:** If no domain detected AND score is CAUTIOUS → skip NLM enrichment entirely. Better no enrichment than querying the wrong notebook.

### 3.3 Pipeline Insertion — Parallel Speculative Pattern (Backend)

**Two insertion points in `orchestrator_streaming_core.py`:**

**Point 1 — Early fire (BEFORE ReAct loop):**
After domain detection (keywords, instant), fire `asyncio.create_task()` to call NLM Bridge speculatively. Runs in background during entire ReAct loop.

**Point 2 — Late merge (AFTER ReAct, BEFORE `done` event at line 269):**
After evidence_score is on `state`, decide:

- CAUTIOUS + NLM done → yield `nlm_enrichment` event + "Verified" badge data
- CAUTIOUS + NLM still running → `await asyncio.wait_for(nlm_task, timeout=3.0)`
- CONFIDENT or ABSTAIN → `nlm_task.cancel()`, proceed normally
- NLM failed/unreachable → skip enrichment, no regression

**Flow in the streaming path:**

```
1. Domain detection → resolve_notebook(query)
2. if domain found:
   a. Check Redis cache first (NotebookLMCacheService, 30-day TTL)
   b. if cache hit: store result, skip bridge call
   c. if cache miss: nlm_task = asyncio.create_task(query_nlm_bridge(...))
3. SSE: emit {"type": "nlm_status", "data": {"status": "consulting", "domain_label": "Immigration & Visa"}}
   → Frontend shows "I nostri specialisti Immigration stanno verificando..."
4. ReAct loop runs → streams answer tokens → calculates evidence_score
5. Store trusted_tools_used on state (2 lines in reasoning.py)
6. if CAUTIOUS AND not trusted_tools_used AND nlm_task/cached_result exists:
   a. result = cached_result or await asyncio.wait_for(nlm_task, timeout=3.0)
   b. yield SSE {"type": "nlm_enrichment", ...}
   c. Cache result in NotebookLMCacheService (key = notebook_id + question_hash)
   else: nlm_task.cancel() if exists
7. yield done event (with evidence_score + confidence_zone)
```

**Why parallel is safe:**

- NLM is read-only — no side effects from speculative calls
- NLM is free ($0, Google AI Ultra) — wasted calls cost nothing
- Rate limit: ~600/day budget vs ~100 queries/day = ample headroom
- `asyncio.Task` is lightweight — no threads, no processes
- Cancel is clean — `task.cancel()` + `try/except asyncio.CancelledError`

**For the non-streaming path** (`orchestrator_core.py`): same pattern — fire NLM task at start, await at end if CAUTIOUS.

**Changes to `reasoning.py`:** Store `trusted_tools_used` on `state` (2 lines):

```python
state.trusted_tools_used = trusted_tools_used  # after policy enforcement
```

**Changes to `orchestrator_streaming.py`:** Extend `create_done_event()` signature to accept `evidence_score` and `confidence_zone`. Update all callers.

**Review fix — Cache key:** Include `notebook_id` in cache key hash (current `NotebookLMCacheService._hash_question` hashes only the question — same question to different notebooks would collide).

### 3.4 SSE Protocol Changes

**Extended `done` event:**

```json
{
  "type": "done",
  "data": {
    "execution_time": 3.42,
    "route_used": "agentic",
    "evidence_score": 0.38,
    "confidence_zone": "cautious"
  }
}
```

**New `nlm_enrichment` event** (emitted BEFORE done, only for CAUTIOUS + NLM success):

```json
{
  "type": "nlm_enrichment",
  "data": {
    "domain": "immigration",
    "domain_label": "Immigration & Visa",
    "citations": [
      {
        "source_file": "UU_Nomor_1_Tahun_2026.pdf",
        "section": "Pasal 48, Ayat 2",
        "excerpt": "Izin tinggal terbatas diberikan kepada...",
        "page": 23
      }
    ],
    "summary": "Confirmed by official immigration law sources."
  }
}
```

**Backward compatibility:** Both events are additive. Old clients that don't handle `nlm_enrichment` ignore it. The `done` event still signals completion. The frontend's SSE parser already handles arbitrary event types via if/else chain fallthrough.

**Discovery:** `reasoning.py:1363` already emits `{"type": "evidence_score", "data": {"score": ...}}` but the frontend ignores it. This confirms the SSE protocol already supports arbitrary metadata events.

### 3.5 Frontend UX — "Zantara Risponde, il Team Conferma"

**Core narrative:** Zantara is the first responder — she answers immediately, with authority. But she has a team of domain specialists behind her. When they've finished reviewing, their confirmation appears seamlessly. The client sees a professional firm at work, not a chatbot hedging.

**Design principle:** No numbers, no scores, no technical jargon. The perception is human expertise, not algorithmic confidence. Like getting an email from a lawyer who says "I've checked with our immigration team and they confirm..."

#### The User Experience (Timeline)

```
┌──────────────────────────────────────────────────────────────┐
│ t=0s  User asks: "What are the KITAS requirements?"         │
│                                                              │
│ t=1s  Zantara starts streaming answer...                     │
│       "Per il KITAS 2026 servono: passaporto valido          │
│        18 mesi, sponsor letter, RPTKA approvato..."          │
│                                                              │
│       👥 I nostri specialisti Immigration stanno              │
│          verificando i riferimenti normativi                  │
│          ░░░░░░░░░░                                          │
│                                                              │
│ t=4.5s Answer complete. NLM result arrives.                  │
│                                                              │
│       👥 Verificato dal team Immigration              [▼]    │
│       ┌────────────────────────────────────────────────┐     │
│       │ 📖 Fonti ufficiali                             │     │
│       │ UU No. 1/2026 — Pasal 48, Ayat 2              │     │
│       │ Permenkumham 22/2023 — Bab III, Pasal 15       │     │
│       └────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
```

#### States:

| Phase                          | SSE Event                 | UI Treatment                                                                                                                |
| ------------------------------ | ------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Answer streaming + NLM working | `nlm_status: consulting`  | **"I nostri specialisti {Domain} stanno verificando i riferimenti normativi"** — subtle pulsing, below the streaming answer |
| Answer done + NLM success      | `nlm_enrichment` + `done` | Badge transitions to **"Verificato dal team {Domain}"** — gold accent, expandable citations panel                           |
| Answer done + NLM timeout/fail | `done` (no enrichment)    | Consulting indicator fades out silently — answer stands on its own, no alarm                                                |
| CONFIDENT answer (>0.60)       | `done` only               | No badge, no consulting indicator — the answer speaks for itself                                                            |
| ABSTAIN (<0.15)                | N/A                       | System refuses to answer (existing behavior)                                                                                |

#### Component: `TeamVerificationBadge`

Replaces/extends existing `VerificationBadge` in `MessageBubble.tsx:44-76`.

**Consulting state** (appears during answer streaming when NLM is working):

```
👥 I nostri specialisti Immigration stanno verificando i riferimenti normativi
```

- Icon: `Users` (Lucide) — suggests a team of people, not a machine
- Color: muted zinc text, subtle
- Pulsing animation on icon (CSS `@keyframes pulse-soft`, no Framer Motion)
- Language: follows user's detected language (Italian/English/Indonesian)

**Verified state** (replaces consulting state when NLM enrichment arrives):

```
👥 Verificato dal team Immigration                              [▼]
```

- Icon: `Users` (Lucide) with check overlay
- Color: warm gold (`--bz-accent: #d4845a`) — matches Warm Depth design system
- Clickable: expands `NLMCitationPanel` below
- Transition: smooth fade from consulting → verified

**Graceful fade** (NLM timed out or failed):
The consulting indicator fades out with `opacity: 0` transition over 500ms. No error message, no badge change. The answer was already good — the team just didn't get back in time. No alarm.

#### Component: `NLMCitationPanel`

Collapsible panel below the message bubble. **Collapsed by default**, expanded on badge click.

#### Component: `NLMCitationPanel`

Collapsible panel below the message bubble. Collapsed by default, expanded on badge click.

```
┌─────────────────────────────────────────────┐
│ 📖 Fonti ufficiali — Immigration & Visa     │
│                                         [▼] │
├─────────────────────────────────────────────┤
│ UU_Nomor_1_Tahun_2026.pdf                   │
│ Pasal 48, Ayat 2                            │
│ "Izin tinggal terbatas diberikan kepada..." │
│                                             │
│ Permenkumham_22_2023.pdf                    │
│ Bab III, Pasal 15                           │
│ "Persyaratan perpanjangan KITAS meliputi..."│
└─────────────────────────────────────────────┘
```

- Uses `--bz-accent` gold border to match the badge
- Each citation shows: filename, section reference, relevant excerpt
- Follows existing `CitationCard` component visual language (already in `MessageBubble.tsx:27`)
- Language: follows user's detected language (Italian for admin, English/Indonesian for clients)

---

## 4. Data Flow Summary

```
                     QUERY: "What are KITAS requirements for 2026?"
                                        │
                                        ▼
                             ┌─ ReAct Loop (4.5s avg) ─┐
                             │ Qdrant search            │
                             │ KG traversal             │
                             │ Tool calls               │
                             │ → streams answer tokens   │
                             └──────────┬───────────────┘
                                        │
                                   evidence_score = 0.38
                                   confidence_zone = CAUTIOUS
                                        │
                              ┌─────────┴─────────┐
                              │ resolve_notebook() │
                              │ → "immigration"    │
                              │ → NB-2 (84375bc3)  │
                              └─────────┬─────────┘
                                        │
                              ┌─────────┴─────────┐
                              │ Redis cache check  │
                              │ (30-day TTL)       │
                              └────┬────────┬──────┘
                                   │        │
                              MISS │        │ HIT → use cached
                                   │        │
                              ┌────┴────────┘
                              │
                    POST http://100.x.x.x:18790/nlm/query
                    (Tailscale, 8s timeout)
                              │
                         NLM responds (4.2s)
                              │
                    SSE: nlm_enrichment event
                    SSE: done event
                              │
                    Frontend: show TeamVerificationBadge
                              + expandable NLMCitationPanel
```

---

## 5. Existing Infrastructure to Reuse

| Component                  | Location                                                 | Reuse                                                   |
| -------------------------- | -------------------------------------------------------- | ------------------------------------------------------- |
| `NotebookLMCacheService`   | `backend/services/caching/notebooklm_cache_service.py`   | Redis cache with 30-day TTL, MD5 hashing — use directly |
| `nlm_auth_bridge.py`       | `apps/federation/nlm_auth_bridge.py`                     | Auth check + auto-relogin — import in bridge            |
| `VerificationBadge`        | `apps/mouth/src/components/chat/MessageBubble.tsx:44-76` | Extend with team specialist states                      |
| `CitationCard`             | `apps/mouth/src/components/search/CitationCard.tsx`      | Visual reference for NLMCitationPanel                   |
| `EvidenceScoreConstants`   | `backend/app/core/constants.py:85-105`                   | CAUTIOUS zone thresholds                                |
| Tailscale VPN              | Both Pro and Fly.io machines                             | Encrypted tunnel, no port exposure                      |
| `evidence_score` SSE event | `reasoning.py:1363`                                      | Already emitted, frontend ignores it — activate         |

---

## 6. Change Surface Estimate (Updated post-review)

| File                                                           | Type   | Lines          | Risk                                             |
| -------------------------------------------------------------- | ------ | -------------- | ------------------------------------------------ |
| `apps/nlm-bridge/main.py`                                      | NEW    | ~120           | Low (isolated service)                           |
| `apps/nlm-bridge/com.balizero.nlm-bridge.plist`                | NEW    | ~20            | Low (LaunchAgent)                                |
| `backend/services/oracle/nlm_notebook_registry.py`             | NEW    | ~60            | Low (static config)                              |
| `backend/services/oracle/nlm_enrichment_service.py`            | NEW    | ~80            | Low (thin HTTP client + HMAC signing)            |
| `backend/services/rag/agentic/reasoning.py`                    | MODIFY | +2             | Low (store flag on state)                        |
| `backend/services/rag/agentic/orchestrator_streaming_core.py`  | MODIFY | +45            | Medium (parallel fire + late merge)              |
| `backend/services/rag/agentic/orchestrator_streaming.py`       | MODIFY | +10            | Low (extend `create_done_event` signature)       |
| `backend/services/rag/agentic/orchestrator_core.py`            | MODIFY | +25            | Medium (non-streaming path)                      |
| `backend/services/caching/notebooklm_cache_service.py`         | MODIFY | +5             | Low (add notebook_id to cache key)               |
| `backend/app/setup/service_initializer.py`                     | MODIFY | +15            | Low (wire service + feature flag)                |
| `apps/mouth/src/lib/api/chat/chat.api.ts`                      | MODIFY | +35            | **High** (fix metadata overwrite + NLM handlers) |
| `apps/mouth/src/hooks/useChatStreaming.ts`                     | MODIFY | +10            | Medium (pass ALL metadata fields, not just 3)    |
| `apps/mouth/src/types/index.ts`                                | MODIFY | +15            | Low (extend Message metadata type)               |
| `apps/mouth/src/components/chat/MessageBubble.tsx`             | MODIFY | +50            | Medium (TeamVerificationBadge + states)          |
| `apps/mouth/src/components/chat/NLMCitationPanel.tsx`          | NEW    | ~60            | Low (display only)                               |
| `backend/tests/unit/services/oracle/test_nlm_enrichment.py`    | NEW    | ~120           | Low (tests)                                      |
| `backend/tests/unit/services/oracle/test_notebook_registry.py` | NEW    | ~40            | Low (tests)                                      |
| **Total**                                                      |        | **~750 lines** |                                                  |

### Simulation-Discovered Critical Fixes

These issues were found during end-to-end flow simulation and are **mandatory prerequisites**:

**Fix 1 — Metadata overwrite bug (CRITICAL):**
`chat.api.ts:561` does `finalMetadata = data.data` which REPLACES previous metadata. Multiple metadata events (entities, NLM enrichment, persistence) overwrite each other — only the last one survives to `onDone`. Must change to **MERGE**: `finalMetadata = {...finalMetadata, ...data.data}`.

**Fix 2 — Metadata field filtering (HIGH):**
`useChatStreaming.ts:107-111` extracts ONLY `conversation_id`, `execution_time`, `persisted` from metadata. All other fields (route_used, emotional_state, NLM data) are silently dropped before reaching `useChatPage.ts`. Must pass through ALL fields.

**Fix 3 — CAUTIOUS zone rarely fires (DESIGN):**
`reasoning.py` has 5+ bypass mechanisms that push evidence_score to 0.85 or force `trusted_tools_used=True`:

- `vector_search` is in `trusted_tool_names` (line 1325)
- Any context >200 chars → `trusted_tools_used=True` (line 1414-1421)
- `has_tools` check → if LLM had tools, trust its answer (line 1458-1464)
- Pricing data markers → bypass (line 1423-1449)

This means CAUTIOUS zone fires for <5% of queries. The parallel speculative pattern makes this acceptable (zero latency cost for discarded NLM calls), but the speculative `nlm_status: consulting` indicator will show for ALL domain-detected queries, not just CAUTIOUS ones. **The frontend must handle the indicator appearing then fading without the "Verified" badge for the majority of queries.** This is the graceful fade pattern.

---

## 7. Rollout Plan

**Phase 1 — Bridge + Tests (Day 1):**
Deploy NLM HTTP Bridge on Pro (port 18790). Add LaunchAgent. Add HMAC request signing. Test with `curl`. Verify Tailscale connectivity from Fly.io. Write bridge health check.

**Phase 2 — Backend wiring (Day 2):**
Add notebook registry, enrichment service, parallel pipeline insertion. Write unit tests. Feature-flagged via `ENABLE_NLM_ENRICHMENT` env var in `service_initializer.py` (default: `false`). Deploy to Fly.io with flag OFF. Test in staging.

**Phase 3 — Frontend (Day 3):**
Add `TeamVerificationBadge` (consulting/verified/fade states), `NLMCitationPanel`, SSE event handlers for `nlm_status` and `nlm_enrichment`. Extend `Message` type. Deploy to Vercel.

**Phase 4 — Enable + Monitor (Day 4):**
Set `ENABLE_NLM_ENRICHMENT=true` on Fly.io. Monitor: NLM call volume, latency, cache hit rate, bridge health. Add Telegram alert if bridge unreachable for >5 min.

**Phase 5 — Populate notebooks (Day 5+):**
Populate NB-2 through NB-8 with domain documents. Each notebook activation expands the coverage.

---

## 8. Review Fixes (from Gemini, DeepSeek R1, Claude Architect)

| Issue                                                                  | Severity | Fix Applied                                                                                                                                                                                                                       |
| ---------------------------------------------------------------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cache key missing `notebook_id`                                        | High     | Added to §3.3: cache key = `notebook_id + question_hash`                                                                                                                                                                          |
| `Message` type not in change surface                                   | High     | Added `types/index.ts` to §6                                                                                                                                                                                                      |
| Tests absent                                                           | High     | Added 2 test files to §6 (~160 lines)                                                                                                                                                                                             |
| `create_done_event` signature change missing                           | Medium   | Added `orchestrator_streaming.py` to §6                                                                                                                                                                                           |
| Feature flag wiring unspecified                                        | Medium   | Specified in §7 Phase 2                                                                                                                                                                                                           |
| Tailscale failure detection = 8-12s not 2s                             | Medium   | Changed to 3s grace timeout in §3.3 after parallel overlap                                                                                                                                                                        |
| HMAC request signing for bridge security                               | Medium   | Added to enrichment service + bridge                                                                                                                                                                                              |
| NLM auth uses subprocess for `nlm login`, not library import           | Low      | Clarified: bridge imports library for queries, shells for auth                                                                                                                                                                    |
| `NLMCitationPanel` can't reuse `CitationCard` props (different schema) | Low      | New component, follows same visual language only                                                                                                                                                                                  |
| CAUTIOUS zone likely <5% in practice                                   | Info     | Acknowledged — parallel pattern makes this acceptable (zero latency cost for NORMAL queries)                                                                                                                                      |
| DeepSeek R1 recommends REJECT                                          | Dissent  | Noted. Parallel pattern + graceful fade eliminates the ROI concern — zero regression, zero latency cost. Bridge fragility is mitigated by graceful degradation. Human-in-the-loop is a valid Phase 2 addition, not a replacement. |

---

## 9. Constraints and Non-Goals

**Constraints:**

- NLM has no public REST API — uses reverse-engineered `batchexecute` protocol (fragile)
- NLM auth is cookie-based, requires Chrome on Pro — watchdog + auto-relogin mitigate
- NLM is a validator (9/10 reliability), not an explorer — confirms, doesn't discover
- Parallel pattern hides NLM latency behind ReAct loop — net add ~0-3s for CAUTIOUS only

**Non-goals:**

- Not replacing Qdrant/KG pipeline — NLM is supplementary enrichment only
- Not building a general NLM API — this bridge serves only the RAG pipeline
- Not exposing technical metrics to clients — they see "team verified", not "score 0.38"
- Not supporting multi-notebook queries in v1 — primary domain only
- Not blocking answers for NLM — Zantara always responds first, team confirms after
