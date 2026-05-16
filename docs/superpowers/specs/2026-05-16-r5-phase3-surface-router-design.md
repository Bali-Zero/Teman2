# SurfaceRouter Design — R5 Phase 3

**Date:** 2026-05-16  
**Branch:** feat/r5-phase3-surface-router-2026-05-16  
**Status:** Implementation-ready

---

## Problem

`QueryRouterIntegration` (production) uses keyword-only Layer 1 routing. This handles 80%+ of
Bali Zero queries correctly (visa, tax, kbli are high-signal domains). However:

1. No surface differentiation: all queries route to Qdrant collections; KG, NB, SQLite-skills are
   never consulted by the router decision layer.
2. Ambiguous queries (property law + tax, or skills/ops questions) get routed by whichever domain
   has slightly more keyword hits — unpredictable.
3. `bali_zero_skills_local` (R5 Phase 1: 379 skills/reflections/insights) is local-only Qdrant;
   no production code routes there yet.

---

## Design Goals

| Goal                                            | Target                           |
| ----------------------------------------------- | -------------------------------- |
| p95 latency (keyword path, 80% of queries)      | ≤ 10 ms                          |
| p95 latency (LLM fallback path, 20% of queries) | ≤ 3 000 ms                       |
| Accuracy on 50-query benchmark                  | ≥ 88 %                           |
| Zero breaking changes to existing routing       | Required                         |
| No `ANTHROPIC_API_KEY` / SDK                    | Required (Claude CLI OAuth only) |

---

## Architecture: 2-Layer Router

```
query
  │
  ├─► Layer 1: Keyword scoring (< 1 ms)
  │     QueryRouterIntegration.route_query()  ← existing SSOT
  │     confidence >= 0.60  ─────────────────► SurfaceDecision  (FAST PATH)
  │     confidence < 0.60   ─────────────────► Layer 2
  │
  └─► Layer 2: Claude Haiku-4.5 classifier (800–2500 ms)
        claude -p "<system>" --model claude-haiku-4-5-20251001
        Returns JSON: {surface, collection, domain, confidence}
        ─────────────────────────────────────────────────────► SurfaceDecision
```

**Surfaces (7):**

| Surface           | Collection/Target                                          | Domain trigger        |
| ----------------- | ---------------------------------------------------------- | --------------------- |
| `qdrant_visa`     | `visa_oracle` + `immigration_circulars`                    | visa, immigration     |
| `qdrant_tax`      | `tax_genius_hybrid`                                        | tax, pajak            |
| `qdrant_company`  | `kbli_2025_final_hybrid` + `training_conversations_hybrid` | kbli, company, legal  |
| `qdrant_property` | `legal_unified_hybrid_hybrid`                              | property              |
| `qdrant_pricing`  | `bali_zero_pricing_hybrid`                                 | pricing               |
| `qdrant_news`     | `balizero_news`                                            | news, intel           |
| `qdrant_skills`   | `bali_zero_skills_local` (local, via `QDRANT_LOCAL_URL`)   | ops, skills, workflow |

**Out of scope (Phase 3):** KG surface, NB surface. These are Phase 4+ (blocked on AIL gates).

---

## Key Implementation Decisions

### Decision 1: Consume QueryRouterIntegration as SSOT

`SurfaceRouter` does NOT re-implement keyword logic. It delegates to `QueryRouterIntegration`
(already wired in production) and reads `confidence` from the result. This means:

- Zero duplication of keyword lists
- Future improvements to `QueryRouter` automatically benefit `SurfaceRouter`
- Surface mapping is a thin translation layer only

### Decision 2: Haiku via Claude CLI OAuth (no SDK)

Following project rule: `claude -p "<prompt>" --model claude-haiku-4-5-20251001 --output-format json`

- Uses `ClaudeOAuthClient` (already exists at `backend/llm/claude_oauth_client.py`)
- Timeout: 3s hard limit; on timeout → fallback to keyword result
- Haiku triggered only when confidence < 0.60 (expected: ~20% of queries)

### Decision 3: Skills surface is local-only for now

`bali_zero_skills_local` exists in Qdrant Docker on Pro (`http://127.0.0.1:6333`).
Fly.io backend cannot reach it. So:

- `qdrant_skills` surface is returned in the `SurfaceDecision` but the caller is responsible
  for using `QDRANT_LOCAL_URL` for that surface.
- A `is_local_only: bool` flag on `SurfaceDecision` communicates this constraint.
- TODO (Phase 4 AIL #1): re-index to Qdrant Cloud once decision confirmed.

### Decision 4: Shadow mode default (feature flag)

`SURFACE_ROUTER_ENABLED` env var (default: `"false"` in prod). When disabled, `SurfaceRouter`
returns a decision but callers continue to use `QueryRouterIntegration` output directly.
This matches the pattern of `USE_QUERY_PLANNER` in `query_planner.py`.

---

## Data Structures

```python
@dataclass
class SurfaceDecision:
    surface: str                    # e.g. "qdrant_visa"
    primary_collection: str         # e.g. "visa_oracle"
    collections: list[str]          # ordered list including fallbacks
    domain: str                     # e.g. "visa"
    confidence: float               # 0.0–1.0
    layer_used: int                 # 1 = keyword, 2 = haiku
    is_local_only: bool             # True only for qdrant_skills
    latency_ms: float               # routing decision latency
```

---

## Files

| File                                                    | Action                                     |
| ------------------------------------------------------- | ------------------------------------------ |
| `backend/services/routing/surface_router.py`            | CREATE — main implementation               |
| `backend/tests/services/routing/test_surface_router.py` | CREATE — 50-query TDD benchmark            |
| `backend/app/setup/service_initializer.py`              | EDIT — register `app.state.surface_router` |

---

## Test Strategy

50 canonical queries covering all 7 surfaces + edge cases:

- 10 visa queries (Italian/EN/ID mix)
- 8 tax queries
- 8 company/KBLI queries
- 6 property queries
- 5 pricing queries
- 5 news queries
- 4 ops/skills queries (ops procedures, internal workflows)
- 4 ambiguous multi-domain queries (→ validates Haiku fallback path)

Each test asserts: correct `surface`, `domain`, `confidence ≥ 0.5`, `latency_ms < 10`
(keyword path — Haiku path is mocked in unit tests).
