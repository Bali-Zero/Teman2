# NUZANTARA FULL SYSTEM AUDIT

**Date:** 2026-02-08
**Scope:** Entire monorepo (`apps/backend-rag`, `apps/mouth`, satellites)
**Files Analyzed:** 500+ Python files, 70 routers, 230 services, 477 test files
**Method:** Automated exploration + deep code reading with line-by-line analysis

---

## EXECUTIVE SUMMARY

| Category          | Grade  | Critical Issues | High                 | Medium              | Low    |
| ----------------- | ------ | --------------- | -------------------- | ------------------- | ------ |
| **Security**      | B      | 3               | 3                    | 3                   | 0      |
| **RAG Pipeline**  | B-     | 4               | 6                    | 10                  | 10     |
| **Architecture**  | C+     | 2               | 3                    | 5                   | 3      |
| **Code Quality**  | C      | 43              | 1                    | 7                   | 2      |
| **Test Coverage** | C      | 0               | 65 untested services | 40 untested routers | 0      |
| **Dependencies**  | B+     | 1               | 0                    | 4                   | 3      |
| **TOTAL**         | **C+** | **53**          | **78**               | **69**              | **18** |

**Total findings: 218**

---

## SECTION 1: CRITICAL FINDINGS (Fix Immediately)

### CRIT-01: WhatsApp Conversation Endpoints Are Completely Unprotected

**Files:** `backend/app/routers/whatsapp_conversations.py`
**Risk:** HIGH -- unauthorized access to customer conversations

Three endpoints have **zero authentication**:

- `GET /api/whatsapp/conversations` -- exposes all conversation history
- `GET /api/whatsapp/messages/{phone}` -- exposes messages by phone number
- `POST /api/whatsapp/send` -- allows sending WhatsApp messages to any number

**Fix:** Add `Depends(get_current_user)` to all three endpoints. Verify user is team member.

---

### CRIT-02: VisionTool Has Path Traversal Vulnerability

**File:** `backend/services/rag/agentic/tools.py:288`
**Risk:** HIGH -- arbitrary file read via LLM prompt injection

`file_path` is user-controlled (via LLM tool call) and passed directly to `process_pdf()` with no validation. A prompt injection could make the LLM call `vision_analysis(file_path="/etc/shadow")`.

**Fix:** Add path allowlist (e.g., `/app/uploads/`, `/tmp/`), reject paths with `..`, validate file extensions.

---

### CRIT-03: Public Debug Endpoint Exposes Legal Documents

**File:** `backend/app/routers/debug.py:493`
**Risk:** MEDIUM -- legal document content accessible without auth

`GET /api/debug/parent-documents-public/{document_id}` is explicitly marked "PUBLIC endpoint for testing - NO AUTH REQUIRED".

**Fix:** Remove or add authentication.

---

### CRIT-04: Evidence Scoring Uses Deprecated Implementation

**File:** `backend/services/rag/agentic/reasoning.py:247-404`
**Risk:** HIGH -- scoring logic diverges from canonical version

The `from .reasoning_utils import calculate_evidence_score` at line 46 is **shadowed** by a local `def calculate_evidence_score()` at line 247. The local deprecated version (with different keyword matching logic and Italian-only stop words) is what actually runs. The canonical version in `reasoning_utils.py` is dead code.

The two versions produce different scores for the same input. A 10-word query with 2 keyword matches: canonical = YES (matches >= 2), deprecated = NO (2/10 = 0.2 < 0.3).

**Fix:** Delete the local definition at line 247-404. Let the import from `reasoning_utils` be the single source of truth.

---

### CRIT-05: `kg_orchestrator.py` Crashes at Runtime

**File:** `backend/services/rag/agentic/kg_orchestrator.py:551`
**Risk:** HIGH -- unhandled ValueError

```python
response, model_used, response_obj = await self.llm_gateway.send_message(...)
```

`send_message` returns 4 values `(str, str, Any, TokenUsage)`, but only 3 are unpacked. This raises `ValueError: too many values to unpack` at runtime.

**Fix:** Change to `response, model_used, response_obj, _usage = ...`

---

### CRIT-06: Streaming vs Non-Streaming Trusted Tools Mismatch

**Files:** `reasoning.py:871-878` (non-streaming) vs `reasoning.py:1590-1596` (streaming)

Non-streaming path includes `"timesheet"` in trusted tools; streaming does not. Additionally, both paths include `"search_team_member"` and `"get_team_members_list"` which don't exist as actual tools -- the tool registry only has `"team_knowledge"`.

**Fix:** Synchronize both sets. Add `"timesheet"`, remove phantom tool names.

---

### CRIT-07: CacheService Uses Synchronous Redis (Blocks Event Loop)

**File:** `backend/core/cache.py:164`
**Risk:** HIGH -- every cached endpoint call blocks the asyncio event loop

The main `CacheService` uses `redis.from_url()` (synchronous), while `SemanticCache` and `ArticleComposerCache` correctly use `redis.asyncio`. Every `@cached` decorator call (CRM stats, RAG search, etc.) blocks the event loop during Redis I/O.

**Fix:** Migrate `CacheService` to `redis.asyncio`.

---

### CRIT-08: No Cache Invalidation on CRM Mutations

**File:** `backend/core/cache.py:407` (function exists but never called)
**Risk:** MEDIUM -- users see stale dashboard data for up to 5 minutes

`invalidate_cache()` exists but is never called from any CRM create/update/delete operation. After creating a client, stats dashboards show stale data until TTL expires (300s).

**Fix:** Add `invalidate_cache("zantara:crm_clients_stats:*")` after create/update/delete in all CRM routers.

---

### CRIT-09: 43 Silent Exception Swallows Across the Codebase

**Files:** Multiple (see Section 4 for full list)
**Risk:** HIGH -- production errors invisible, debugging impossible

43 instances where exceptions are caught with `except Exception:` but either silently `pass`ed or `return None` without logging. Critical paths affected:

- `whatsapp_chat.py:274` -- context building silently fails
- `whatsapp_chat.py:457` -- database pool errors hidden
- `hybrid_auth.py:383` -- authentication failures hidden
- `memory/orchestrator.py:406` -- user memory context lost silently

**Fix:** Add `logger.error(f"...: {e}", exc_info=True)` to all silent catches.

---

## SECTION 2: SECURITY FINDINGS

### SEC-01: Hardcoded Admin Email Lists

**File:** `backend/app/routers/crm_utils.py:11-22`

Admin emails hardcoded in source code (4 CRM admins + 2 super admins). Requires code deployment to change admin access.

**Recommendation:** Move to `team_members` table with role column.

### SEC-02: Missing Rate Limits on Expensive Public Endpoints

| Endpoint                  | File                        | Issue                               |
| ------------------------- | --------------------------- | ----------------------------------- |
| `/api/blog/ask`           | `blog_ask.py`               | LLM-powered, no specific rate limit |
| `/api/kbli-notebook/chat` | `kbli_notebook.py`          | LLM-powered, no specific rate limit |
| `/api/whatsapp/send`      | `whatsapp_conversations.py` | Message sending, no rate limit      |

Default is 200/min which is too high for LLM-powered endpoints.

### SEC-03: Fail-Open Rate Limiting

**File:** `backend/middleware/rate_limiter.py:118`

On Redis error, rate limiter allows the request (`return True`). If Redis goes down, all rate limiting is disabled.

### SEC-04: ElevenLabs Webhook Missing Signature Verification

**File:** `backend/middleware/hybrid_auth.py:121`

The comment says "should add signature verification" but none is implemented.

### SEC-05: `/metrics` Endpoint Publicly Accessible

**File:** `backend/middleware/hybrid_auth.py:106`

Prometheus metrics endpoint is public. Comment says "should be IP-restricted in production".

### SEC-06: Inconsistent RBAC Role Naming

`analytics.py` checks for role `"Founder"` (capital F), while `crm_utils.py` checks for `"admin"` (lowercase). Role name inconsistency may lead to bypass.

---

## SECTION 3: RAG PIPELINE FINDINGS

### RAG-01: `reasoning.py` is 2,151 Lines with ~1,400 Duplicated

The file contains two near-complete ReAct loop implementations (non-streaming: lines 498-1358, streaming: lines 1359-1998), plus deprecated functions, duplicate evidence scoring, and three copies of `detect_team_query`. Every bug fix must be applied twice (and they aren't -- see CRIT-06).

**Recommendation:** Refactor into shared private methods. Target: 800 lines.

### RAG-02: Sequential Federated Vector Search (Biggest Latency Bottleneck)

**File:** `tools.py:130-158`

When no collection is specified, all 6 collections are searched **one after another** in a `for` loop. Each search: 150-300ms. Total: 900-1800ms.

The KG orchestrator (`kg_orchestrator.py:367`) correctly uses `asyncio.gather()` for the same pattern.

**Fix:** Replace with `asyncio.gather()` + per-collection `asyncio.wait_for(timeout=10)`.

### RAG-03: Fake Streaming (20-char Chunks, Not Real Token Streaming)

**File:** `reasoning.py:1989-1993`

The entire answer is generated first, then chunked into 20-character pieces. Users see nothing until the full answer is ready.

### RAG-04: ABSTAIN Messages Hardcoded in Italian Only

6 locations in `reasoning.py` have Italian refusal messages. English/Indonesian/other users get Italian error messages.

### RAG-05: TIER_PRO and TIER_FLASH Use Identical Model

**File:** `llm_gateway.py:120-122`

Both resolve to `gemini-2.0-flash-001`. Code that sets `tier=TIER_PRO` for complex queries gets no actual upgrade.

### RAG-06: TIER_LITE Skips Primary Model Entirely

**File:** `llm_gateway.py:374-382`

`TIER_LITE (1)` condition `1 <= TIER_FLASH (0)` is `False`, so the primary model is never tried. TIER_LITE is actually worse than TIER_FLASH.

### RAG-07: No Timeout on LLM `generate_content()` Call

**File:** `llm_gateway.py:857`

No explicit timeout. If Gemini hangs (network partition), this `await` blocks indefinitely.

### RAG-08: OpenRouter Token Usage Not Tracked

**File:** `llm_gateway.py:699-704`

When OpenRouter handles a query, `prompt_tokens=0` and `completion_tokens=0` are recorded. Cost tracking is lost.

### RAG-09: Verification Service Creates Its Own LLM Client

**File:** `verification_service.py:74`

Bypasses the main `LLMGateway`'s circuit breaker, fallback cascade, and cost limiter.

### RAG-10: Emotional Acknowledgment Always Assumes Frustration

**File:** `response_processor.py:140-144`

"I understand the frustration..." prepended even for positive emotional queries like "I'm so excited about my new visa!"

### RAG-11: Prompt Builder Cache Key Uses Length Not Hash

**File:** `prompt_builder.py:651`

Cache key includes `len(facts)` not `hash(facts)`. If a fact is updated but count stays same, stale prompt served for 5 minutes.

### RAG-12: Streaming Path Has Zero OpenTelemetry Tracing

**File:** `reasoning.py` (streaming section, lines 1359-1998)

Non-streaming path has full tracing spans. Streaming path (majority of production traffic) has none.

### RAG-13: Health Check Tests Same Model Twice, Never Tests Fallback

**File:** `llm_gateway.py:1043-1080`

Tests `model_name_flash` twice. `model_name_fallback` is never tested.

### RAG-14: `_build_multimodal_content` and `_send_with_fallback` Defined Twice

**File:** `llm_gateway.py:384/535, 488/727`

First definitions are dead code. Python uses the second definition.

---

## SECTION 4: CODE QUALITY FINDINGS

### 43 Silent Exception Swallows (Full List)

**Critical Paths:**
| File | Line | Context |
|------|------|---------|
| `whatsapp_chat.py` | 274 | `except Exception: pass` -- context building |
| `whatsapp_chat.py` | 457 | `except Exception: return None` -- DB pool |
| `hybrid_auth.py` | 383 | `except Exception:` -- auth errors |
| `memory/orchestrator.py` | 406 | `except Exception:` -- user context |
| `reasoning.py` | 722 | `except Exception:` -- reasoning error |

**Services (28 instances):**

- `intel.py` -- 5 silent catches
- `zoho_email_service.py` -- 3 silent catches
- `vision_rag.py` -- 2 silent catches
- `intel_analytics_service.py` -- 5 silent catches
- 13 more across various services

**Agents (10 instances):**

- `multi_ai_adapter.py` -- 3 silent catches
- `test_maintainer.py` -- 3 silent catches
- 4 more across agent services

### 3 print() Statements in Production Code

| File                  | Count |
| --------------------- | ----- |
| `verify_streaming.py` | 8     |
| `verify_route.py`     | 7     |
| `verify_chat.py`      | 12    |

### 1 Bare Except Clause

`migrations/scripts/seed_visa_types_complete_2026.py:1628` -- `except: pass`

### 4 console.log in Frontend Production Code

| File                       | Line |
| -------------------------- | ---- |
| `hooks/useCrmPractices.ts` | 46   |
| `hooks/useCrmClients.ts`   | 29   |
| `lib/ai-insights.tsx`      | 521  |

### 2 Logging Patterns (Inconsistent)

~90% use `import logging; logger = logging.getLogger(__name__)`
~10% use `from backend.app.utils.logging_utils import get_logger`

---

## SECTION 5: ARCHITECTURE FINDINGS

### ARCH-01: 5 Circular Dependency Chains (46 Deferred Imports)

1. `memory/` <-> `rag/agentic/` (via MemoryOrchestrator)
2. `misc/` <-> `llm/` (7 services)
3. `rag/agentic/` internal cycle (orchestrator -> sub-modules)
4. `misc/conversation_service` <-> `crm/`
5. `misc/tool_executor` <-> `misc/` siblings

**Root cause:** `backend.app.metrics` is the #1 hotspot (14 deferred imports in `llm_gateway.py`, `reasoning.py`, `memory/orchestrator.py`).

**Fix:** Create Protocol interfaces and a metrics facade.

### ARCH-02: 20+ Direct `os.environ` Bypasses of `settings`

20 services read env vars directly instead of using the centralized `Settings` class. 8 env vars (`ANTHROPIC_API_KEY`, `GOOGLE_CLOUD_PROJECT`, etc.) have no corresponding settings field at all.

### ARCH-03: config.py Has Duplicate Field Definitions

- `whatsapp_verify_token` defined twice (lines 537, 599)
- `whatsapp_phone_number_id` defined twice (lines 569, 595)
- `google_credentials_json` defined twice (lines 37, 738) -- second overwrites first, making the validator dead code
- `@field_validator("whatsapp_verify_token")` defined twice (lines 545, 616)

### ARCH-04: 4 Independent Redis Connections Instead of Shared Pool

`CacheService` (sync), `SemanticCache` (async), `ArticleComposerCache` (async), `UnifiedHealthService` (sync) each create their own Redis connection.

### ARCH-05: Database Init Retry Can Block Startup for 62 Seconds

**File:** `service_initializer.py:296`

5 retries with exponential backoff (2+4+8+16+32+~2.5 jitter = ~64.5s). Fly.io health check may kill the instance before retries complete.

### ARCH-06: Background Tasks Have No Supervision/Restart

`asyncio.create_task()` calls are fire-and-forget. If a background task crashes, the functionality silently stops.

### ARCH-07: CulturalRAGService and CollaboratorService Created Twice

**File:** `service_initializer.py:196-202, 786-792` (CulturalRAGService)
**File:** `service_initializer.py:809-815, 627-634` (CollaboratorService)

First instance is discarded; second is used.

---

## SECTION 6: TEST COVERAGE FINDINGS

### Coverage Summary

| Category     | Total | Tested | Untested | Coverage |
| ------------ | ----- | ------ | -------- | -------- |
| **Services** | ~150  | ~85    | ~65      | **57%**  |
| **Routers**  | 70    | ~30    | ~40      | **43%**  |
| **Overall**  | ~220  | ~115   | ~105     | **52%**  |

### Highest-Priority Untested Modules

| Module               | Untested Files | Business Criticality    |
| -------------------- | -------------- | ----------------------- |
| **Knowledge Graph**  | 8/8            | Core RAG functionality  |
| **Memory Services**  | 8/8            | User memory and context |
| **Analytics**        | 12/13          | Team productivity       |
| **Intel Services**   | 4/4            | News pipeline           |
| **Journey Services** | 5/5            | Client journey          |
| **LLM Clients**      | 5/5            | Provider integrations   |
| **Compliance**       | 5/5            | Compliance monitoring   |

### Untested Critical Routers

- `whatsapp_conversations.py` -- WhatsApp API
- `telegram.py` -- Telegram bot
- `intel.py` -- Intel/news pipeline
- `crm_practices.py` -- CRM practices
- `portal.py`, `portal_taxes.py`, `portal_visa.py` -- Portal

---

## SECTION 7: ROUTER REGISTRATION FINDINGS

### 5 Unregistered Router Files

| File                     | Purpose                                        | Recommendation                                                |
| ------------------------ | ---------------------------------------------- | ------------------------------------------------------------- |
| `article_composer_v2.py` | Article Composer v2 with retry/circuit breaker | Register if active, remove if obsolete                        |
| `crm_drive_folders.py`   | Google Drive folder management                 | Register if needed                                            |
| `crm_migration.py`       | Migration status tracking                      | Register if needed                                            |
| `kg_agentic.py`          | KG-Agentic RAG API                             | Register if needed (has crash bug, see CRIT-05)               |
| `memory_vector.py`       | Semantic memory via Qdrant                     | Register if needed (may conflict with existing `/api/memory`) |

### 1 Duplicate Registration

`analytics.py` registered twice in `router_registration.py` (lines 126 and 199).

### 1 Dead Service File

`services/rag/graph_pathfinder.py` -- never imported anywhere. Safe to delete.

---

## SECTION 8: DEPENDENCY FINDINGS

### Missing Critical Dependency

**`Pillow`** is imported as `PIL` in 2 files (`pdf_vision_service.py`, `vision_rag.py`) but is NOT in `requirements.txt`. Docker builds may fail.

### Duplicate Dependency

`redis` appears twice in `requirements.txt` (lines 68 and 125).

### Potentially Unused Dependencies (~10 packages)

`playwright`, `selenium`, `fake-useragent`, `webdriver-manager`, `sendgrid`, `twilio`, `datasets`, `pandas`, `sse-starlette`, `tiktoken`

### Missing Environment Variable Documentation

8 env vars used directly via `os.getenv()` have no corresponding field in `config.py Settings` class and no documentation.

---

## SECTION 9: PRIORITIZED ACTION PLAN

### Week 1: Security & Correctness (Critical)

| #   | Action                                       | Effort | Impact | Files                       |
| --- | -------------------------------------------- | ------ | ------ | --------------------------- |
| 1   | Protect WhatsApp endpoints                   | 30m    | HIGH   | `whatsapp_conversations.py` |
| 2   | Fix VisionTool path traversal                | 30m    | HIGH   | `tools.py:288`              |
| 3   | Remove public debug endpoint                 | 5m     | MEDIUM | `debug.py:493`              |
| 4   | Fix trusted tools mismatch (streaming)       | 15m    | HIGH   | `reasoning.py:1590-1596`    |
| 5   | Fix kg_orchestrator unpacking crash          | 5m     | HIGH   | `kg_orchestrator.py:551`    |
| 6   | Delete deprecated `calculate_evidence_score` | 30m    | HIGH   | `reasoning.py:247-404`      |
| 7   | Add cache invalidation on CRM mutations      | 1h     | MEDIUM | CRM routers (7 endpoints)   |

### Week 2: Performance & Reliability

| #   | Action                                        | Effort | Impact | Files                    |
| --- | --------------------------------------------- | ------ | ------ | ------------------------ |
| 8   | Parallelize federated vector search           | 1h     | HIGH   | `tools.py:130-158`       |
| 9   | Migrate CacheService to async Redis           | 4h     | HIGH   | `core/cache.py`          |
| 10  | Fix LLM Gateway tier logic                    | 1h     | MEDIUM | `llm_gateway.py:374-382` |
| 11  | Add timeout to LLM generate_content           | 30m    | HIGH   | `llm_gateway.py:857`     |
| 12  | Add Pillow to requirements.txt                | 5m     | HIGH   | `requirements.txt`       |
| 13  | Remove duplicate redis entry                  | 5m     | LOW    | `requirements.txt`       |
| 14  | Add rate limits to expensive public endpoints | 1h     | MEDIUM | `rate_limiter.py`        |

### Week 3: Code Quality

| #   | Action                                  | Effort | Impact | Files                              |
| --- | --------------------------------------- | ------ | ------ | ---------------------------------- |
| 15  | Fix 43 silent exception swallows        | 3h     | HIGH   | Multiple (see Section 4)           |
| 16  | Internationalize ABSTAIN messages       | 1h     | MEDIUM | `reasoning.py` (6 locations)       |
| 17  | Fix config.py duplicate fields          | 30m    | LOW    | `config.py`                        |
| 18  | Consolidate os.environ to settings      | 3h     | MEDIUM | 20 service files                   |
| 19  | Remove duplicate analytics registration | 5m     | LOW    | `router_registration.py`           |
| 20  | Delete dead `graph_pathfinder.py`       | 5m     | LOW    | `services/rag/graph_pathfinder.py` |

### Month 2: Architecture Refactoring

| #   | Action                                          | Effort | Impact | Files                     |
| --- | ----------------------------------------------- | ------ | ------ | ------------------------- |
| 21  | Refactor reasoning.py (deduplicate ReAct loops) | 8h     | HIGH   | `reasoning.py`            |
| 22  | Break circular dependencies with Protocols      | 16h    | HIGH   | 46 deferred imports       |
| 23  | Consolidate Redis connections into shared pool  | 4h     | MEDIUM | 4 files                   |
| 24  | Add background task supervision                 | 3h     | MEDIUM | `service_initializer.py`  |
| 25  | Inject LLMGateway into VerificationService      | 2h     | MEDIUM | `verification_service.py` |

### Month 3: Test Coverage

| #   | Action                                              | Effort | Impact | Files                       |
| --- | --------------------------------------------------- | ------ | ------ | --------------------------- |
| 26  | Write tests for Knowledge Graph services (8)        | 16h    | HIGH   | `services/knowledge_graph/` |
| 27  | Write tests for Memory services (8)                 | 12h    | HIGH   | `services/memory/`          |
| 28  | Write tests for untested CRM routers (4)            | 8h     | HIGH   | CRM routers                 |
| 29  | Write tests for Intel services (4)                  | 8h     | MEDIUM | `services/intel/`           |
| 30  | Build RAG quality benchmark (50-100 gold questions) | 16h    | HIGH   | `apps/evaluator/`           |

---

## APPENDIX A: RAG PIPELINE ARCHITECTURE (Actual From Code)

```
stream_query() [orchestrator.py:329]
│
├─ Gate 1: Security (prompt injection, 25 regex patterns)
├─ Gate 2: Context Loading (profile + history)
├─ Gate 3: Greeting (11 patterns, 8 languages)
├─ Gate 4: Casual (80 biz keywords, 12 casual patterns)
├─ Gate 5: Identity ("chi sei" / "who am I" fast paths)
├─ Gate 6: Clarification (ambiguity detection, threshold 0.6)
├─ Gate 7: Team Query (direct tool execution, bypasses RAG)
├─ Gate 8: Conversation Recall (23 trigger phrases)
├─ Gate 9: Out-of-Domain
│
└─ ReAct Loop (max 3 steps)
    │
    ├─ LLM Call → Gemini 2.0 Flash → Gemini 2.5 Flash → OpenRouter
    ├─ Parse Tool Calls (native function_call OR regex "ACTION: tool(args)")
    ├─ Execute Tool (rate limit: 10/query)
    │   └─ vector_search | calculator | get_pricing | team_knowledge |
    │     generate_image | web_search | timesheet | vision_analysis
    ├─ Early Exit (>500 chars from vector_search + simple query → break)
    │
    ├─ Evidence Score (0.0 - 1.0)
    │   ├─ High-quality sources (score > 0.15) → +0.5
    │   ├─ Multiple sources (> 3) → +0.2
    │   ├─ Substantial context (> 500 chars) → +0.35
    │   └─ Keyword matches → +0.35
    │
    ├─ Policy Enforcement
    │   ├─ < 0.10 + critical domain → STRICT ABSTAIN (Italian only!)
    │   ├─ < 0.10 + general → Tier-1 Fallback w/ transparency
    │   └─ ≥ 0.10 → Answer (warning if < 0.5)
    │
    └─ Response Pipeline
        ├─ VerificationStage (extra LLM call, threshold ≥ 0.7)
        ├─ PostProcessingStage (clean reasoning patterns)
        ├─ CitationStage (dedup, max 10, sort by relevance)
        └─ FormatStage
            └─ Fake streaming: 20-char chunks after full generation
```

---

## APPENDIX B: COMPLETE EVIDENCE SCORING MATRIX

| Scenario              | Sources | Score > 0.15? | Context     | Keywords        | Evidence | Decision       |
| --------------------- | ------- | ------------- | ----------- | --------------- | -------- | -------------- |
| Perfect retrieval     | 5 docs  | Yes           | Yes         | 3+              | **1.0**  | Normal         |
| Good retrieval        | 2 docs  | Yes           | Yes         | 2               | **0.85** | Normal         |
| Moderate retrieval    | 2 docs  | Yes           | Yes         | 0               | **0.5**  | Warning        |
| Low score sources     | 4 docs  | No            | Yes         | 2               | **0.55** | Warning        |
| No sources, good ctx  | 0       | N/A           | >500ch      | 2               | **0.70** | Normal         |
| No sources, short ctx | 0       | N/A           | <500ch      | 1 (short query) | **0.35** | Normal         |
| Empty retrieval       | 0       | N/A           | None        | N/A             | **0.0**  | ABSTAIN/Tier-1 |
| Trusted tools         | 0       | N/A           | Tool output | N/A             | Bypassed | Normal         |

---

## APPENDIX C: FULL PUBLIC ENDPOINTS LIST (29)

### Infrastructure (8)

`/health`, `/health/`, `/docs`, `/docs/`, `/openapi.json`, `/api/v1/openapi.json`, `/redoc`, `/metrics`

### Auth (3)

`/api/auth/team/login`, `/api/auth/login`, `/api/auth/csrf-token`

### Webhooks (5)

`/webhook/whatsapp`, `/api/whatsapp/webhook`, `/webhook/instagram`, `/api/telegram/webhook`, `/api/voice/elevenlabs`

### OAuth (3)

`/api/integrations/zoho/callback`, `/api/integrations/google-drive/callback`, `/api/integrations/google-drive/system/status`

### Portal (2)

`/api/portal/invite/validate/`, `/api/portal/invite/complete`

### Knowledge (3)

`/api/knowledge/visa`, `/api/oracle/health`, `/api/v1/kbli-notebook/`

### Blog (4)

`/api/blog/newsletter/subscribe`, `/api/blog/newsletter/confirm`, `/api/blog/newsletter/unsubscribe`, `/api/blog/ask`

### Preview (1)

`/preview/`

---

_Report generated by ZANTARA full-spectrum system audit. 500+ files analyzed across 7 parallel exploration agents._
_Total audit duration: ~15 minutes._
