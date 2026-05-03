# SOLIDIFICATION 04 — LLM Integration Layer Audit & Plan

**Date:** 2026-04-06
**Component:** LLM Integration (`backend/llm/`, `backend/services/llm_clients/`)

## Findings: 3 HIGH, 5 MEDIUM, 4 LOW

## Code Fixes Applied

| Fix | Severity | What |
|-----|----------|------|
| F-01 | HIGH | OllamaProvider: replaced per-request httpx.AsyncClient with persistent _get_async_client() + aclose() |
| F-02 | MEDIUM | Added OpenRouter client close() to app_factory.py lifespan shutdown |
| F-09 | MEDIUM | Removed sync HTTP health check from OllamaProvider constructor (blocks event loop) |

## Deferred (architecture debt, not urgent)

- F-05: ZantaraAIClient circuit breaker (HIGH — needs shared CB registry with LLMGateway)
- F-06: Unify three independent Gemini stacks (MEDIUM — architecture refactor)
- F-07: Cost tracking in ZantaraAIClient (MEDIUM — use pricing.py)
- F-03: Clean dead provider .pyc and test stubs (MEDIUM — cleanup)
- F-10: Verify gemini-3-flash model availability (HIGH — operational)
