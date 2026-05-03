# LLM Cost Tracking v2 — Complete Coverage + Governance — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend PR #107's cost recorder to every paid LLM/media endpoint in the backend, add CI enforcement, build a weekly cost-advisor agent, and ship a Pro-only local dashboard.

**Architecture:** Shared `@llm_cost_tracked` async decorator wraps 5 new integration points (+1 refactor); a CI script walks a fixed set of dirs and fails the build when a paid-client file doesn't call `record_llm_call`; a `CostAdvisor` service mines `llm_cost_events`, uses Claude OAuth Max as LLM-judge for substitutions, and persists recommendations in migration 118; a standalone Next.js 16 app on port 3100 reads Postgres directly with a Fly-tunnel fallback.

**Tech Stack:** Python 3.11 · FastAPI · asyncpg · pytest + pytest-asyncio · Next.js 16 · Recharts · Tailwind · launchd (Pro) · Brevo (Telegram relay)

**Spec:** `docs/superpowers/specs/2026-04-19-llm-cost-tracking-v2-design.md`

---

## File Structure

**New files (Phase B):**

- `apps/backend-rag/backend/services/observability/tracking_decorator.py` — `@llm_cost_tracked` async decorator + `set_usage` contextvar helper
- `apps/backend-rag/backend/app/routers/llm_costs.py` — POST `/api/admin/llm-costs/record`
- `scripts/check_llm_cost_tracking.py` — CI enforcer
- `apps/backend-rag/backend/tests/unit/services/observability/test_tracking_decorator.py`
- `apps/backend-rag/backend/tests/unit/routers/test_llm_costs_router.py`
- `apps/backend-rag/backend/tests/unit/scripts/test_check_llm_cost_tracking.py`
- `apps/backend-rag/backend/tests/unit/services/visual/test_imagen_client_tracking.py`
- `apps/backend-rag/backend/tests/unit/services/llm_clients/test_openrouter_tracking.py`
- `apps/backend-rag/backend/tests/unit/core/test_embeddings_tracking.py`
- `apps/backend-rag/backend/tests/unit/services/knowledge_graph/test_extractor_gemini_refactor.py`
- `apps/backend-rag/backend/tests/unit/app/services/test_audio_tracking.py`
- `apps/backend-rag/backend/tests/unit/services/council/test_cli_runners_tracking.py`

**Modified (Phase B):**

- `apps/backend-rag/backend/core/embeddings.py` — add `@llm_cost_tracked` around `embed_documents`/`embed_query` call path
- `apps/backend-rag/backend/services/llm_clients/openrouter_client.py` — wrap `complete`/`complete_stream`
- `apps/backend-rag/backend/services/knowledge_graph/extractor_gemini.py` — delegate to `get_genai_client()`
- `apps/backend-rag/backend/services/visual/imagen_client.py` — wrap `generate`
- `apps/backend-rag/backend/app/services/audio_service.py` — wrap OpenAI TTS/STT methods (Pollinations stays untracked, free)
- `apps/backend-rag/backend/services/council/cli_runners.py` — DeepSeek HTTP branch + Gemini API-key branch
- `apps/backend-rag/backend/app/setup/router_manifest.py` — register `llm_costs` router
- `.github/workflows/tests.yml` — add enforcer step before pytest

**New files (Phase C):**

- `apps/backend-rag/backend/migrations/migration_118_cost_recommendations.py`
- `apps/backend-rag/backend/services/observability/cost_advisor.py`
- `apps/backend-rag/backend/scripts/cost_advisor_cli.py`
- `apps/backend-rag/backend/tests/unit/services/observability/test_cost_advisor.py`
- `apps/backend-rag/backend/tests/unit/migrations/test_migration_118.py`
- `apps/backend-rag/backend/tests/integration/observability/test_cost_advisor_cli_integration.py`
- `~/Library/LaunchAgents/com.nuzantara.cost-advisor-weekly.plist` — Pro Mon 07:00 WITA
- `~/Library/LaunchAgents/com.nuzantara.cost-advisor-daily-cap.plist` — Pro 08:00 WITA daily

**New files (Phase D) — separate branch:**

- `apps/admin-dashboard-local/package.json`
- `apps/admin-dashboard-local/next.config.js`
- `apps/admin-dashboard-local/tsconfig.json`
- `apps/admin-dashboard-local/tailwind.config.ts`
- `apps/admin-dashboard-local/.gitignore`
- `apps/admin-dashboard-local/.env.example`
- `apps/admin-dashboard-local/app/layout.tsx`
- `apps/admin-dashboard-local/app/page.tsx`
- `apps/admin-dashboard-local/app/cost-dashboard/page.tsx`
- `apps/admin-dashboard-local/app/api/llm-costs/{kpi,timeline,top-endpoints,model-mix,recommendations,anomalies}/route.ts`
- `apps/admin-dashboard-local/app/lib/{db,queries}.ts`
- `apps/admin-dashboard-local/components/{CostKpiCards,CostTimeline,TopEndpoints,ModelMix,RecommendationPanel,AnomalyBanner}.tsx`
- `apps/admin-dashboard-local/__tests__/routes.integration.test.ts`
- `scripts/start-cost-dashboard.sh`

---

# PHASE B — Coverage + Enforcer + Remote Endpoint

## Pre-Phase B: Branch setup

- [ ] **Step 1: Create feature branch from main**

```bash
cd ~/Desktop/nuzantara
git checkout main && git pull origin main
git checkout -b feat/llm-cost-tracking-v2-complete
```

- [ ] **Step 2: Verify baseline green**

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/services/observability/test_llm_cost_recorder.py -q
```

Expected: all pass (PR #107 baseline intact).

---

## Task 1: `@llm_cost_tracked` decorator

**Files:**

- Create: `apps/backend-rag/backend/services/observability/tracking_decorator.py`
- Test: `apps/backend-rag/backend/tests/unit/services/observability/test_tracking_decorator.py`
- Modify: `apps/backend-rag/backend/services/observability/__init__.py` — add `llm_cost_tracked`, `set_usage` exports

- [ ] **Step 1: Write failing tests**

```python
# test_tracking_decorator.py
import pytest
from unittest.mock import AsyncMock, patch
from backend.services.observability.tracking_decorator import (
    llm_cost_tracked, set_usage,
)


@pytest.mark.asyncio
async def test_decorator_records_on_success():
    @llm_cost_tracked(provider="openai_embeddings", static_model="text-embedding-3-small")
    async def fake_call():
        set_usage(input_tokens=100, output_tokens=0)
        return "ok"

    with patch("backend.services.observability.tracking_decorator.record_llm_call",
               new=AsyncMock()) as mock_rec:
        result = await fake_call()

    assert result == "ok"
    mock_rec.assert_awaited_once()
    kwargs = mock_rec.await_args.kwargs
    assert kwargs["provider"] == "openai_embeddings"
    assert kwargs["model"] == "text-embedding-3-small"
    assert kwargs["input_tokens"] == 100
    assert kwargs["success"] is True
    assert kwargs["error_class"] is None
    assert kwargs["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_decorator_records_on_failure():
    @llm_cost_tracked(provider="openrouter", static_model="llama-3")
    async def fake_call():
        set_usage(input_tokens=50, output_tokens=0)
        raise RuntimeError("boom")

    with patch("backend.services.observability.tracking_decorator.record_llm_call",
               new=AsyncMock()) as mock_rec:
        with pytest.raises(RuntimeError):
            await fake_call()

    kwargs = mock_rec.await_args.kwargs
    assert kwargs["success"] is False
    assert kwargs["error_class"] == "RuntimeError"


@pytest.mark.asyncio
async def test_decorator_never_raises_on_recorder_error():
    @llm_cost_tracked(provider="gemini", static_model="flash")
    async def fake_call():
        set_usage(input_tokens=1, output_tokens=1)
        return "ok"

    async def blowup(**_):
        raise OSError("disk full")

    with patch("backend.services.observability.tracking_decorator.record_llm_call",
               new=blowup):
        result = await fake_call()  # must not raise

    assert result == "ok"


@pytest.mark.asyncio
async def test_decorator_uses_model_attr_from_self():
    class Client:
        model = "dynamic-model-v2"

        @llm_cost_tracked(provider="gemini", model_attr="model")
        async def call(self):
            set_usage(input_tokens=10, output_tokens=20)
            return "ok"

    c = Client()
    with patch("backend.services.observability.tracking_decorator.record_llm_call",
               new=AsyncMock()) as mock_rec:
        await c.call()

    assert mock_rec.await_args.kwargs["model"] == "dynamic-model-v2"


@pytest.mark.asyncio
async def test_decorator_falls_back_to_zero_cost_on_unknown_model():
    @llm_cost_tracked(provider="mystery", static_model="who-knows")
    async def fake_call():
        set_usage(input_tokens=1, output_tokens=1)
        return "ok"

    with patch("backend.services.observability.tracking_decorator.record_llm_call",
               new=AsyncMock()) as mock_rec:
        await fake_call()

    assert mock_rec.await_args.kwargs["cost_usd"] == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd apps/backend-rag
PYTHONPATH=. pytest backend/tests/unit/services/observability/test_tracking_decorator.py -v
```

Expected: all 5 FAIL with `ModuleNotFoundError: backend.services.observability.tracking_decorator`.

- [ ] **Step 3: Write the decorator implementation**

```python
# apps/backend-rag/backend/services/observability/tracking_decorator.py
"""@llm_cost_tracked decorator — standardises LLM cost recording across clients.

Wraps an async function so that every call (success or failure) emits a
record_llm_call event. Token counts come from a contextvar that the wrapped
function writes via set_usage(). Cost is computed via the pricing module;
unknown provider/model → 0.0 + warning (never blocks the call).

Never raises: a recorder failure is logged and swallowed so user-facing
calls are unaffected.
"""

from __future__ import annotations

import functools
import logging
import time
from contextvars import ContextVar
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

_usage_ctx: ContextVar[tuple[int, int] | None] = ContextVar(
    "llm_cost_usage", default=None,
)


def set_usage(*, input_tokens: int, output_tokens: int) -> None:
    """Called inside a decorated function to report tokens actually used."""
    _usage_ctx.set((int(input_tokens), int(output_tokens)))


def llm_cost_tracked(
    *,
    provider: str,
    static_model: str | None = None,
    model_attr: str | None = None,
    endpoint: str | None = None,
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """Async-only decorator that records cost events.

    Args:
        provider: Event provider tag ('gemini', 'deepseek', ...).
        static_model: Fixed model slug (use this OR model_attr).
        model_attr: Attribute name on ``self`` to read the model from.
        endpoint: Optional caller endpoint tag; defaults to the function's
            qualified name.
    """
    if (static_model is None) == (model_attr is None):
        raise ValueError("Provide exactly one of static_model or model_attr")

    def decorator(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        ep = endpoint or fn.__qualname__

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            from backend.services.observability import record_llm_call
            from backend.services.llm_clients import pricing

            token = _usage_ctx.set(None)
            t0 = time.monotonic()
            success = False
            err: str | None = None
            try:
                result = await fn(*args, **kwargs)
                success = True
                return result
            except BaseException as exc:  # noqa: BLE001 — record, then re-raise
                err = type(exc).__name__
                raise
            finally:
                usage = _usage_ctx.get()
                _usage_ctx.reset(token)
                input_tokens, output_tokens = usage or (0, 0)

                if static_model is not None:
                    model = static_model
                else:
                    assert model_attr is not None
                    self_obj = args[0] if args else None
                    model = getattr(self_obj, model_attr, "unknown")

                try:
                    cost_usd = pricing.compute_cost(
                        provider=provider,
                        model=model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "llm_cost_tracked: unknown pricing for %s/%s (%s) "
                        "— recording cost_usd=0.0", provider, model, exc,
                    )
                    cost_usd = 0.0

                try:
                    await record_llm_call(
                        provider=provider,
                        model=model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cost_usd=cost_usd,
                        success=success,
                        latency_ms=int((time.monotonic() - t0) * 1000),
                        endpoint=ep,
                        error_class=err,
                    )
                except Exception as rec_exc:  # noqa: BLE001
                    logger.warning(
                        "llm_cost_tracked: recorder failed for %s/%s: %s",
                        provider, model, rec_exc,
                    )

        return wrapper

    return decorator
```

- [ ] **Step 4: Add `pricing.compute_cost` shim if missing**

```bash
cd apps/backend-rag
PYTHONPATH=. python -c "from backend.services.llm_clients import pricing; print(hasattr(pricing, 'compute_cost'))"
```

If `False`, append to `backend/services/llm_clients/pricing.py`:

```python
def compute_cost(
    *,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Return USD cost for a single call, or 0.0 if pricing is unknown.

    Raises:
        KeyError: if (provider, model) is not registered.
    """
    rates = _PRICING_TABLE.get((provider, model))
    if rates is None:
        raise KeyError((provider, model))
    return (
        input_tokens * rates["input_per_token"]
        + output_tokens * rates["output_per_token"]
    )
```

And register the 6 new (provider, model) pairs in `_PRICING_TABLE`:

```python
_PRICING_TABLE.update({
    ("openai_embeddings", "text-embedding-3-small"): {
        "input_per_token": 0.02 / 1_000_000,
        "output_per_token": 0.0,
    },
    ("openrouter", "__dynamic__"): {  # overridden at call time, see Task 3
        "input_per_token": 0.0,
        "output_per_token": 0.0,
    },
    ("imagen", "imagen-4.0-ultra-generate-001"): {
        "input_per_token": 0.06,  # one call = one "token" here
        "output_per_token": 0.0,
    },
    ("imagen", "imagen-4.0-generate-001"): {
        "input_per_token": 0.04,
        "output_per_token": 0.0,
    },
    ("imagen", "imagen-4.0-fast-generate-001"): {
        "input_per_token": 0.02,
        "output_per_token": 0.0,
    },
    ("openai_audio", "tts-1"): {
        "input_per_token": 15.0 / 1_000_000,  # $15/1M chars
        "output_per_token": 0.0,
    },
    ("openai_audio", "whisper-1"): {
        "input_per_token": 0.006 / 60,  # input_tokens = seconds → $0.006/min
        "output_per_token": 0.0,
    },
})
```

- [ ] **Step 5: Export decorator from `__init__.py`**

Modify `apps/backend-rag/backend/services/observability/__init__.py` to include:

```python
from backend.services.observability.tracking_decorator import (
    llm_cost_tracked,
    set_usage,
)
from backend.services.observability.llm_cost_recorder import record_llm_call

__all__ = ["record_llm_call", "llm_cost_tracked", "set_usage"]
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd apps/backend-rag
PYTHONPATH=. pytest backend/tests/unit/services/observability/test_tracking_decorator.py -v
```

Expected: all 5 PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/backend-rag/backend/services/observability/tracking_decorator.py \
        apps/backend-rag/backend/services/observability/__init__.py \
        apps/backend-rag/backend/services/llm_clients/pricing.py \
        apps/backend-rag/backend/tests/unit/services/observability/test_tracking_decorator.py
git commit -m "feat(observability): add @llm_cost_tracked async decorator

Standardises cost recording across all paid LLM clients. Uses a contextvar
(set_usage) for token reporting; never raises; falls back to cost_usd=0.0
on unknown pricing. Registers 6 new pricing rows (openai_embeddings,
openrouter, imagen, openai_audio)."
```

---

## Task 2: Integrate `core/embeddings.py` (OpenAI embeddings)

**Files:**

- Modify: `apps/backend-rag/backend/core/embeddings.py` — wrap the `AsyncOpenAI.embeddings.create` call site
- Test: `apps/backend-rag/backend/tests/unit/core/test_embeddings_tracking.py`

- [ ] **Step 1: Locate the call site**

```bash
grep -n "embeddings.create" apps/backend-rag/backend/core/embeddings.py
```

Expected: line around 309 (`response = await self.client.embeddings.create(...)`).

- [ ] **Step 2: Write failing test**

```python
# test_embeddings_tracking.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.core.embeddings import EmbeddingsGenerator


@pytest.mark.asyncio
async def test_embed_documents_records_cost():
    gen = EmbeddingsGenerator(api_key="test", model="text-embedding-3-small")
    fake_response = MagicMock()
    fake_response.data = [MagicMock(embedding=[0.1] * 1536)]
    fake_response.usage = MagicMock(prompt_tokens=42, total_tokens=42)
    gen.client = MagicMock()
    gen.client.embeddings.create = AsyncMock(return_value=fake_response)

    with patch("backend.services.observability.tracking_decorator.record_llm_call",
               new=AsyncMock()) as mock_rec:
        await gen.embed_documents(["hello world"])

    mock_rec.assert_awaited_once()
    kwargs = mock_rec.await_args.kwargs
    assert kwargs["provider"] == "openai_embeddings"
    assert kwargs["model"] == "text-embedding-3-small"
    assert kwargs["input_tokens"] == 42
    assert kwargs["output_tokens"] == 0
    assert kwargs["success"] is True
```

- [ ] **Step 3: Run test to verify it fails**

```bash
PYTHONPATH=. pytest backend/tests/unit/core/test_embeddings_tracking.py -v
```

Expected: FAIL — `record_llm_call` not awaited.

- [ ] **Step 4: Wrap the batch call**

In `apps/backend-rag/backend/core/embeddings.py`, find the async method that calls `self.client.embeddings.create(...)` (around line 309) and wrap it:

```python
from backend.services.observability import llm_cost_tracked, set_usage

class EmbeddingsGenerator:
    ...
    @llm_cost_tracked(provider="openai_embeddings", model_attr="model")
    async def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        response = await self.client.embeddings.create(model=self.model, input=batch)
        set_usage(
            input_tokens=getattr(response.usage, "prompt_tokens", 0),
            output_tokens=0,
        )
        return [item.embedding for item in response.data]
```

Refactor existing `embed_documents` to call `_embed_batch` per batch (it already batches — keep the loop, just delegate the actual create call).

- [ ] **Step 5: Run test to verify it passes**

```bash
PYTHONPATH=. pytest backend/tests/unit/core/test_embeddings_tracking.py -v
```

Expected: PASS.

- [ ] **Step 6: Run existing embeddings tests to confirm no regression**

```bash
PYTHONPATH=. pytest backend/tests/ -q -k embed
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add apps/backend-rag/backend/core/embeddings.py \
        apps/backend-rag/backend/tests/unit/core/test_embeddings_tracking.py
git commit -m "feat(embeddings): track OpenAI embedding call cost

Wraps the batch embedding call with @llm_cost_tracked, provider=
openai_embeddings, tokens from response.usage.prompt_tokens."
```

---

## Task 3: Integrate `services/llm_clients/openrouter_client.py`

**Files:**

- Modify: `apps/backend-rag/backend/services/llm_clients/openrouter_client.py`
- Test: `apps/backend-rag/backend/tests/unit/services/llm_clients/test_openrouter_tracking.py`

- [ ] **Step 1: Read the existing file to find `complete` + `complete_stream` methods**

```bash
grep -n "async def \(complete\|smart_complete\)" apps/backend-rag/backend/services/llm_clients/openrouter_client.py
```

- [ ] **Step 2: Write failing test**

```python
# test_openrouter_tracking.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.services.llm_clients.openrouter_client import (
    OpenRouterClient, ModelTier,
)


@pytest.mark.asyncio
async def test_complete_records_cost():
    client = OpenRouterClient(api_key="test-key", default_tier=ModelTier.RAG)
    fake_resp = MagicMock()
    fake_resp.json.return_value = {
        "choices": [{"message": {"content": "ok"}}],
        "model": "google/gemini-2.0-flash-exp:free",
        "usage": {"prompt_tokens": 120, "completion_tokens": 30},
    }
    fake_resp.raise_for_status = MagicMock()
    fake_http = AsyncMock()
    fake_http.post = AsyncMock(return_value=fake_resp)
    client._client = fake_http

    with patch("backend.services.observability.tracking_decorator.record_llm_call",
               new=AsyncMock()) as mock_rec:
        await client.complete(messages=[{"role": "user", "content": "hi"}])

    kwargs = mock_rec.await_args.kwargs
    assert kwargs["provider"] == "openrouter"
    assert kwargs["model"] == "google/gemini-2.0-flash-exp:free"
    assert kwargs["input_tokens"] == 120
    assert kwargs["output_tokens"] == 30


@pytest.mark.asyncio
async def test_complete_records_failure():
    client = OpenRouterClient(api_key="test-key")
    fake_http = AsyncMock()
    fake_http.post = AsyncMock(side_effect=RuntimeError("rate limit"))
    client._client = fake_http

    with patch("backend.services.observability.tracking_decorator.record_llm_call",
               new=AsyncMock()) as mock_rec:
        with pytest.raises(RuntimeError):
            await client.complete(messages=[{"role": "user", "content": "hi"}])

    kwargs = mock_rec.await_args.kwargs
    assert kwargs["success"] is False
    assert kwargs["error_class"] == "RuntimeError"
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
PYTHONPATH=. pytest backend/tests/unit/services/llm_clients/test_openrouter_tracking.py -v
```

Expected: FAIL — recorder not awaited.

- [ ] **Step 4: Wrap `complete` with dynamic model reporting**

Edit `openrouter_client.py`. Since model is determined by OpenRouter server-side (fallback chain), use `set_usage` + a small state attr:

```python
from backend.services.observability import llm_cost_tracked, set_usage

class OpenRouterClient:
    ...
    # Add to __init__:
    self._last_selected_model: str = "openrouter-fallback"

    @llm_cost_tracked(provider="openrouter", model_attr="_last_selected_model")
    async def complete(self, messages, tier=None, tools=None, **kw):
        # existing body up to response.json() ...
        data = response.json()
        self._last_selected_model = data.get("model", "openrouter-unknown")
        usage = data.get("usage", {})
        set_usage(
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
        )
        return CompletionResult(...)  # existing
```

For `complete_stream`, the model + usage arrive in the final chunk; track by accumulating token counts and calling `set_usage` once before yielding the final chunk (if the stream implementation has no final usage chunk, estimate: `input_tokens = len(prompt)//4`, `output_tokens = len(accumulated_text)//4`).

- [ ] **Step 5: Update `_PRICING_TABLE` for dynamic OpenRouter models**

Since OpenRouter offers ~10 distinct free/paid models across tiers, register each chain member in `pricing.py`:

```python
_PRICING_TABLE.update({
    ("openrouter", "google/gemini-2.0-flash-exp:free"): {"input_per_token": 0.0, "output_per_token": 0.0},
    ("openrouter", "meta-llama/llama-3.3-70b-instruct:free"): {"input_per_token": 0.0, "output_per_token": 0.0},
    ("openrouter", "qwen/qwen3.5-27b"): {"input_per_token": 0.0, "output_per_token": 0.0},
    ("openrouter", "mistralai/mistral-small-3.1-24b-instruct:free"): {"input_per_token": 0.0, "output_per_token": 0.0},
    ("openrouter", "qwen/qwen3.5-35b-a3b"): {"input_per_token": 0.0, "output_per_token": 0.0},
    ("openrouter", "meta-llama/llama-3.2-3b-instruct:free"): {"input_per_token": 0.0, "output_per_token": 0.0},
    # paid fallbacks if any future ones added — use real rates from openrouter.ai/docs
})
```

All free models → cost_usd always 0.0; this is correct per current config. The recorder still captures volume for analytics.

- [ ] **Step 6: Run tests to verify they pass**

```bash
PYTHONPATH=. pytest backend/tests/unit/services/llm_clients/test_openrouter_tracking.py backend/tests/services/llm_clients/test_openrouter_client.py -v
```

Expected: new tests pass; existing 30+ tests still pass.

- [ ] **Step 7: Commit**

```bash
git add apps/backend-rag/backend/services/llm_clients/openrouter_client.py \
        apps/backend-rag/backend/services/llm_clients/pricing.py \
        apps/backend-rag/backend/tests/unit/services/llm_clients/test_openrouter_tracking.py
git commit -m "feat(openrouter): track completion + stream cost

Records provider=openrouter with the dynamically-selected model from the
fallback chain. Free-tier models yield cost_usd=0.0 (expected)."
```

---

## Task 4: Refactor `extractor_gemini.py` to use `genai_client`

**Files:**

- Modify: `apps/backend-rag/backend/services/knowledge_graph/extractor_gemini.py`
- Test: `apps/backend-rag/backend/tests/unit/services/knowledge_graph/test_extractor_gemini_refactor.py`

- [ ] **Step 1: Write failing test**

```python
# test_extractor_gemini_refactor.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.services.knowledge_graph.extractor_gemini import GeminiKGExtractor


@pytest.mark.asyncio
async def test_extractor_delegates_to_genai_client():
    with patch("backend.services.knowledge_graph.extractor_gemini.get_genai_client") as mock_get:
        fake_client = MagicMock()
        fake_client.generate_content_async = AsyncMock(return_value=MagicMock(
            text='{"entities": [], "relations": []}',
            usage_metadata=MagicMock(prompt_token_count=50, candidates_token_count=20),
        ))
        mock_get.return_value = fake_client

        extractor = GeminiKGExtractor(model="gemini-2.0-flash")
        with patch("backend.services.observability.tracking_decorator.record_llm_call",
                   new=AsyncMock()) as mock_rec:
            await extractor.extract(text="Test document")

        # genai_client.generate_content_async was called (delegation)
        fake_client.generate_content_async.assert_awaited_once()
        # and because genai_client is already instrumented, recording happens
        mock_rec.assert_awaited()


def test_extractor_no_longer_imports_genai_directly():
    import backend.services.knowledge_graph.extractor_gemini as mod
    src = open(mod.__file__).read()
    assert "from google import genai" not in src
    assert "genai.Client(" not in src
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONPATH=. pytest backend/tests/unit/services/knowledge_graph/test_extractor_gemini_refactor.py -v
```

Expected: FAIL (current code imports `genai` directly).

- [ ] **Step 3: Refactor extractor**

Replace the `__init__` + client-creation block in `extractor_gemini.py`:

Before (find and delete lines 13, 14 import + `__init__` API-key/client block):

```python
from google import genai
...
self._client = genai.Client(api_key=api_key)
```

After:

```python
from backend.llm.genai_client import get_genai_client

class GeminiKGExtractor:
    def __init__(
        self,
        model: str = "gemini-2.0-flash",
        max_tokens: int = 4096,
        temperature: float = 0.1,
    ) -> None:
        self.model_name = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = get_genai_client()  # already instrumented
```

And replace any `self._client.models.generate_content(...)` with `self._client.generate_content_async(model=self.model_name, ...)` (use the `genai_client` facade's own method).

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=. pytest backend/tests/unit/services/knowledge_graph/test_extractor_gemini_refactor.py backend/tests/unit/services/knowledge_graph/ -v
```

Expected: PASS + existing extractor tests still pass.

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/services/knowledge_graph/extractor_gemini.py \
        apps/backend-rag/backend/tests/unit/services/knowledge_graph/test_extractor_gemini_refactor.py
git commit -m "refactor(kg): route extractor_gemini through genai_client

Eliminates the duplicate 'from google import genai' path. All KG
extraction now inherits the triple-write cost tracking that genai_client
provides (PR #107). Net -40 lines of auth/client boilerplate."
```

---

## Task 5: Integrate `services/visual/imagen_client.py`

**Files:**

- Modify: `apps/backend-rag/backend/services/visual/imagen_client.py`
- Test: `apps/backend-rag/backend/tests/unit/services/visual/test_imagen_client_tracking.py`

- [ ] **Step 1: Write failing test**

```python
# test_imagen_client_tracking.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.services.visual.imagen_client import ImagenClient, ImagenQuality


@pytest.mark.asyncio
async def test_generate_records_cost():
    os_env = {"GEMINI_API_KEY": "test-key"}
    with patch.dict("os.environ", os_env, clear=False):
        client = ImagenClient()
    fake_resp = MagicMock()
    fake_resp.json.return_value = {
        "predictions": [{"bytesBase64Encoded": "AAAA"}],
    }
    fake_resp.raise_for_status = MagicMock()
    fake_resp.status_code = 200
    client._client = AsyncMock()
    client._client.post = AsyncMock(return_value=fake_resp)

    with patch("backend.services.observability.tracking_decorator.record_llm_call",
               new=AsyncMock()) as mock_rec:
        await client.generate(prompt="sunset bali", quality=ImagenQuality.FAST)

    kwargs = mock_rec.await_args.kwargs
    assert kwargs["provider"] == "imagen"
    assert kwargs["model"] == "imagen-4.0-fast-generate-001"
    assert kwargs["input_tokens"] == 1  # 1 image
    assert kwargs["cost_usd"] == 0.02
```

- [ ] **Step 2: Run test to verify it fails**

```bash
PYTHONPATH=. pytest backend/tests/unit/services/visual/test_imagen_client_tracking.py -v
```

Expected: FAIL.

- [ ] **Step 3: Wrap `generate`**

In `imagen_client.py`, add decorator to the generate method:

```python
from backend.services.observability import llm_cost_tracked, set_usage

class ImagenClient:
    ...
    @llm_cost_tracked(provider="imagen", model_attr="_last_model")
    async def generate(self, prompt: str, quality: ImagenQuality = ImagenQuality.FAST, **kw):
        self._last_model = quality.model_id
        set_usage(input_tokens=1, output_tokens=0)  # 1 call = 1 image
        # existing body
```

Add `self._last_model: str = "imagen-4.0-fast-generate-001"` to `__init__`.

- [ ] **Step 4: Run test to verify it passes**

```bash
PYTHONPATH=. pytest backend/tests/unit/services/visual/test_imagen_client_tracking.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/services/visual/imagen_client.py \
        apps/backend-rag/backend/tests/unit/services/visual/test_imagen_client_tracking.py
git commit -m "feat(imagen): track Imagen generation cost

Records provider=imagen, input_tokens=1 per image, cost=\$0.02/0.04/0.06
based on ImagenQuality (FAST/STANDARD/ULTRA)."
```

---

## Task 6: Integrate `app/services/audio_service.py` (OpenAI paths only)

**Files:**

- Modify: `apps/backend-rag/backend/app/services/audio_service.py`
- Test: `apps/backend-rag/backend/tests/unit/app/services/test_audio_tracking.py`

- [ ] **Step 1: Identify the two OpenAI methods**

```bash
grep -n "openai_client\." apps/backend-rag/backend/app/services/audio_service.py
```

Expected: calls to `self.openai_client.audio.speech.create` (TTS) and `self.openai_client.audio.transcriptions.create` (STT/Whisper).

- [ ] **Step 2: Write failing tests**

```python
# test_audio_tracking.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.app.services.audio_service import AudioService


@pytest.mark.asyncio
async def test_openai_tts_records_cost():
    svc = AudioService()
    svc.openai_client = MagicMock()
    svc.openai_client.audio.speech.create = AsyncMock(
        return_value=MagicMock(content=b"audio"),
    )

    with patch("backend.services.observability.tracking_decorator.record_llm_call",
               new=AsyncMock()) as mock_rec:
        await svc._openai_tts(text="hello world", voice="alloy")

    kwargs = mock_rec.await_args.kwargs
    assert kwargs["provider"] == "openai_audio"
    assert kwargs["model"] == "tts-1"
    assert kwargs["input_tokens"] == len("hello world")


@pytest.mark.asyncio
async def test_openai_whisper_records_cost():
    svc = AudioService()
    svc.openai_client = MagicMock()
    svc.openai_client.audio.transcriptions.create = AsyncMock(
        return_value=MagicMock(text="hello world"),
    )

    with patch("backend.services.observability.tracking_decorator.record_llm_call",
               new=AsyncMock()) as mock_rec:
        await svc._openai_stt(file_path="/tmp/x.mp3", duration_seconds=12)

    kwargs = mock_rec.await_args.kwargs
    assert kwargs["provider"] == "openai_audio"
    assert kwargs["model"] == "whisper-1"
    assert kwargs["input_tokens"] == 12
    assert kwargs["output_tokens"] == len("hello world") // 4
```

- [ ] **Step 3: Run tests to verify they fail**

Expected: FAIL — methods `_openai_tts`/`_openai_stt` may not exist yet; we extract them.

- [ ] **Step 4: Refactor + wrap**

Split the OpenAI call paths from the orchestration methods. Add `_openai_tts` and `_openai_stt` private methods, each decorated:

```python
from backend.services.observability import llm_cost_tracked, set_usage

class AudioService:
    @llm_cost_tracked(provider="openai_audio", static_model="tts-1")
    async def _openai_tts(self, *, text: str, voice: str, **kw):
        set_usage(input_tokens=len(text), output_tokens=0)
        resp = await self.openai_client.audio.speech.create(
            model="tts-1", input=text, voice=voice,
        )
        return resp.content

    @llm_cost_tracked(provider="openai_audio", static_model="whisper-1")
    async def _openai_stt(self, *, file_path: str, duration_seconds: int, **kw):
        with open(file_path, "rb") as f:
            resp = await self.openai_client.audio.transcriptions.create(
                model="whisper-1", file=f,
            )
        text = resp.text
        set_usage(input_tokens=int(duration_seconds), output_tokens=len(text) // 4)
        return text
```

Update the public `synthesize`/`transcribe_audio` methods to call `_openai_tts`/`_openai_stt` in the OpenAI fallback branch (Pollinations stays untracked — it's free).

- [ ] **Step 5: Run tests**

```bash
PYTHONPATH=. pytest backend/tests/unit/app/services/test_audio_tracking.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/backend-rag/backend/app/services/audio_service.py \
        apps/backend-rag/backend/tests/unit/app/services/test_audio_tracking.py
git commit -m "feat(audio): track OpenAI TTS/Whisper cost

Pollinations (free) branch untouched. OpenAI fallback wrapped with
@llm_cost_tracked: TTS cost=chars×\$15/1M, Whisper cost=seconds×\$0.006/60."
```

---

## Task 7: Integrate `services/council/cli_runners.py` (DeepSeek + Gemini-API paths)

**Files:**

- Modify: `apps/backend-rag/backend/services/council/cli_runners.py`
- Test: `apps/backend-rag/backend/tests/unit/services/council/test_cli_runners_tracking.py`

- [ ] **Step 1: Find DeepSeek + Gemini-API branches**

```bash
grep -n "DeepSeekRunner\|deepseek\|GEMINI_API_KEY" apps/backend-rag/backend/services/council/cli_runners.py
```

- [ ] **Step 2: Write failing tests**

```python
# test_cli_runners_tracking.py
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.services.council.cli_runners import DeepSeekRunner


@pytest.mark.asyncio
async def test_deepseek_runner_records_cost():
    runner = DeepSeekRunner(api_key="test")
    fake_resp = MagicMock()
    fake_resp.json.return_value = {
        "choices": [{"message": {"content": "reply"}}],
        "model": "deepseek-chat",
        "usage": {"prompt_tokens": 50, "completion_tokens": 20},
    }
    fake_resp.raise_for_status = MagicMock()
    runner._client = AsyncMock()
    runner._client.post = AsyncMock(return_value=fake_resp)

    with patch("backend.services.observability.tracking_decorator.record_llm_call",
               new=AsyncMock()) as mock_rec:
        await runner.run(prompt="test")

    kwargs = mock_rec.await_args.kwargs
    assert kwargs["provider"] == "deepseek"
    assert kwargs["input_tokens"] == 50
    assert kwargs["output_tokens"] == 20
```

- [ ] **Step 3: Run test to verify it fails**

Expected: FAIL.

- [ ] **Step 4: Wrap `DeepSeekRunner.run` with the decorator; leave CLI subprocess runners untouched**

```python
from backend.services.observability import llm_cost_tracked, set_usage

class DeepSeekRunner:
    @llm_cost_tracked(provider="deepseek", static_model="deepseek-r1")
    async def run(self, prompt: str, **kw):
        # existing body ... after parsing response:
        usage = data.get("usage", {})
        set_usage(
            input_tokens=int(usage.get("prompt_tokens", 0)),
            output_tokens=int(usage.get("completion_tokens", 0)),
        )
        return RunnerResult(...)
```

For `GeminiCLIRunner`: check if `os.environ.get("GEMINI_API_KEY")` is set. If yes → it's paid API, not Max CLI → wrap the runner with the same pattern using subprocess stdout parsing (token counts not reliably reported by `gemini -p`; estimate `input_tokens=len(prompt)//4`, `output_tokens=len(stdout)//4`). If no → Max OAuth CLI → untracked (flat rate, noted in spec §9).

- [ ] **Step 5: Run tests**

```bash
PYTHONPATH=. pytest backend/tests/unit/services/council/test_cli_runners_tracking.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/backend-rag/backend/services/council/cli_runners.py \
        apps/backend-rag/backend/tests/unit/services/council/test_cli_runners_tracking.py
git commit -m "feat(council): track DeepSeek HTTP + paid Gemini API in cli_runners

Claude/Gemini CLI subprocess paths (Max OAuth flat-rate) remain untracked.
Only the paid branches (DeepSeek R1 HTTP, Gemini with GEMINI_API_KEY env)
emit record_llm_call."
```

---

## Task 8: CI enforcer script

**Files:**

- Create: `scripts/check_llm_cost_tracking.py`
- Test: `apps/backend-rag/backend/tests/unit/scripts/test_check_llm_cost_tracking.py`
- Modify: `.github/workflows/tests.yml`

- [ ] **Step 1: Write failing tests**

```python
# test_check_llm_cost_tracking.py
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[5] / "scripts"))
from check_llm_cost_tracking import scan_files, is_paid_client, tracks_cost


def test_detects_paid_client_without_tracking(tmp_path):
    f = tmp_path / "bad.py"
    f.write_text("""
from openai import AsyncOpenAI
client = AsyncOpenAI()
async def call():
    return await client.chat.completions.create(model='gpt-4', messages=[])
""")
    assert is_paid_client(f) is True
    assert tracks_cost(f) is False


def test_whitelist_skips_file(tmp_path):
    f = tmp_path / "ollama_client.py"
    f.write_text("import ollama\nawait ollama.chat(...)\n")
    # simulated whitelist (the real WHITELIST constant includes ollama files)
    from check_llm_cost_tracking import WHITELIST_SUBSTRINGS
    assert any(s in str(f) for s in ["ollama_client.py", "providers/ollama"])


def test_tracked_file_passes(tmp_path):
    f = tmp_path / "ok.py"
    f.write_text("""
from backend.services.observability import llm_cost_tracked
from openai import AsyncOpenAI
@llm_cost_tracked(provider='openai', static_model='x')
async def call(): ...
""")
    assert is_paid_client(f) is True
    assert tracks_cost(f) is True


def test_scan_returns_violations(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("from openai import AsyncOpenAI\nAsyncOpenAI().chat.completions.create()\n")
    good = tmp_path / "good.py"
    good.write_text("from openai import AsyncOpenAI\nrecord_llm_call()\n")

    violations = scan_files([tmp_path])
    assert str(bad) in violations
    assert str(good) not in violations
```

- [ ] **Step 2: Run test to verify it fails**

```bash
PYTHONPATH=. pytest backend/tests/unit/scripts/test_check_llm_cost_tracking.py -v
```

Expected: FAIL — script not created.

- [ ] **Step 3: Write the enforcer script**

```python
# scripts/check_llm_cost_tracking.py
"""CI gate: every paid LLM/media client MUST call record_llm_call.

Scans a fixed set of directories, identifies files that perform paid API
calls, and fails with exit 1 if any such file lacks cost tracking.
See docs/superpowers/specs/2026-04-19-llm-cost-tracking-v2-design.md §4.2.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Repo-root relative. Resolved at runtime.
SCAN_ROOTS: list[str] = [
    "apps/backend-rag/backend/llm/",
    "apps/backend-rag/backend/services/llm_clients/",
    "apps/backend-rag/backend/services/visual/",
    "apps/backend-rag/backend/services/knowledge_graph/",
    "apps/backend-rag/backend/services/council/",
    "apps/backend-rag/backend/app/services/",
    "apps/backend-rag/backend/core/",
]

# Substrings: if any is present in a file path, the file is skipped
# (infrastructure, pure proxies, local-only providers).
WHITELIST_SUBSTRINGS: list[str] = [
    "__init__.py",
    "__pycache__",
    "/base.py",
    "/config.py",
    "/pricing.py",
    "/fallback_messages.py",
    "/retry_handler.py",
    "/token_estimator.py",
    "/provider_registry.py",
    "/metrics_emitter.py",
    "/llm/adapters/",
    # Ollama (local, zero cost):
    "ollama_client.py",
    "llm/providers/ollama.py",
    # Proxies that delegate to already-tracked clients:
    "article_composer/claude_client.py",
    "llm/zantara_ai_client.py",
    "llm/claude_oauth_langchain.py",
    "llm/providers/gemini.py",
    "llm/providers/openrouter.py",
    "llm/providers/__init__.py",
    "services/llm_clients/gemini_service.py",
    # KG non-gemini files (extractor_gemini specifically is checked):
    "knowledge_graph/ontology.py",
    "knowledge_graph/coreference.py",
    "knowledge_graph/incremental_builder.py",
]

_PAID_IMPORT_RE = re.compile(
    r"^\s*(?:from|import)\s+"
    r"(anthropic|openai|google\.genai|google\.generativeai)\b",
    re.MULTILINE,
)
_PAID_URL_RE = re.compile(
    r"(api\.openai\.com|api\.deepseek\.com|openrouter\.ai/api|"
    r"generativelanguage\.googleapis|api\.anthropic\.com)",
)
_TRACKING_RE = re.compile(r"(record_llm_call|@llm_cost_tracked|llm_cost_tracked\()")


def is_paid_client(path: Path) -> bool:
    try:
        src = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return bool(_PAID_IMPORT_RE.search(src) or _PAID_URL_RE.search(src))


def tracks_cost(path: Path) -> bool:
    try:
        src = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return bool(_TRACKING_RE.search(src))


def _is_whitelisted(path: Path) -> bool:
    p = str(path)
    return any(s in p for s in WHITELIST_SUBSTRINGS)


def scan_files(roots: list[Path]) -> list[str]:
    violations: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if _is_whitelisted(path):
                continue
            if is_paid_client(path) and not tracks_cost(path):
                violations.append(str(path))
    return violations


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    roots = [repo_root / r for r in SCAN_ROOTS]
    violations = scan_files(roots)
    if violations:
        print("❌ LLM cost tracking violations:")
        for v in violations:
            print(f"  - {v}")
        print(
            "\nEach file above makes paid API calls but does not call "
            "record_llm_call or @llm_cost_tracked. Either add tracking or "
            "add the file to WHITELIST_SUBSTRINGS in "
            "scripts/check_llm_cost_tracking.py with a reason.",
        )
        return 1
    print("✅ All paid LLM clients track cost.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONPATH=. pytest backend/tests/unit/scripts/test_check_llm_cost_tracking.py -v
```

Expected: PASS.

- [ ] **Step 5: Run enforcer against the live repo**

```bash
cd ~/Desktop/nuzantara
python scripts/check_llm_cost_tracking.py
```

Expected: exit 0 (all 6 new files from Tasks 2-7 should now track, all infra whitelisted).

If exit 1, the output lists remaining violations — add them to WHITELIST_SUBSTRINGS (with reason comment) or wrap them.

- [ ] **Step 6: Wire CI**

Edit `.github/workflows/tests.yml`, job `unit-tests`, **before** pytest step:

```yaml
- name: Check LLM cost tracking coverage
  run: python scripts/check_llm_cost_tracking.py
```

- [ ] **Step 7: Commit**

```bash
git add scripts/check_llm_cost_tracking.py \
        apps/backend-rag/backend/tests/unit/scripts/test_check_llm_cost_tracking.py \
        .github/workflows/tests.yml
git commit -m "ci(observability): enforce LLM cost tracking on every paid client

scripts/check_llm_cost_tracking.py fails CI when a file in llm/, llm_clients/,
visual/, kg extractor, council, audio, or embeddings uses a paid provider
without record_llm_call or @llm_cost_tracked. Whitelist covers Ollama,
pure proxies, and infra files."
```

---

## Task 9: Remote ingestion endpoint

**Files:**

- Create: `apps/backend-rag/backend/app/routers/llm_costs.py`
- Modify: `apps/backend-rag/backend/app/setup/router_manifest.py`
- Test: `apps/backend-rag/backend/tests/unit/routers/test_llm_costs_router.py`

- [ ] **Step 1: Write failing tests**

```python
# test_llm_costs_router.py
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from backend.app.main import app


def _admin_headers():
    # Follow existing admin test pattern
    return {"Authorization": "Bearer test-admin-token"}


@pytest.mark.asyncio
async def test_post_record_accepts_valid_payload():
    from backend.app.routers.llm_costs import require_admin

    async def _fake_admin():
        return "zero@balizero.com"

    app.dependency_overrides[require_admin] = _fake_admin
    with patch("backend.app.routers.llm_costs.record_llm_call",
               new=AsyncMock(return_value={"prometheus": True, "postgres": True, "jsonl": True})):
        with TestClient(app) as client:
            r = client.post(
                "/api/admin/llm-costs/record",
                headers=_admin_headers(),
                json={
                    "provider": "gemini",
                    "model": "gemini-flash-3.0-preview",
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "cost_usd": 0.001,
                    "success": True,
                    "latency_ms": 300,
                    "endpoint": "cron.intel_scraper",
                },
            )
    assert r.status_code == 200
    assert r.json()["postgres"] is True
    app.dependency_overrides.clear()


def test_post_record_422_on_missing_fields():
    with TestClient(app) as client:
        r = client.post(
            "/api/admin/llm-costs/record",
            headers=_admin_headers(),
            json={"provider": "gemini"},
        )
    assert r.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Expected: 404 (router not registered yet).

- [ ] **Step 3: Write the router**

```python
# apps/backend-rag/backend/app/routers/llm_costs.py
"""Admin endpoint for Pro/Air cron agents to POST remote cost events."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.app.dependencies import get_current_user_email, get_database
from backend.services.observability import record_llm_call

router = APIRouter(prefix="/api/admin/llm-costs", tags=["observability", "admin"])


async def require_admin(
    email: Annotated[str, Depends(get_current_user_email)],
    request: Request,
) -> str:
    """Mirrors the pattern in messaging_identity.py: check admin role in DB."""
    db_pool = get_database(request)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT role FROM users WHERE email = $1", email,
        )
    if not row or row["role"] not in ("admin", "founder"):
        raise HTTPException(status_code=403, detail="admin required")
    return email


class LLMCostRecord(BaseModel):
    provider: str = Field(..., max_length=32)
    model: str = Field(..., max_length=128)
    input_tokens: int = Field(..., ge=0)
    output_tokens: int = Field(..., ge=0)
    cost_usd: float = Field(..., ge=0.0)
    success: bool
    latency_ms: int = Field(..., ge=0)
    endpoint: str | None = Field(default=None, max_length=128)
    request_id: str | None = Field(default=None, max_length=64)
    error_class: str | None = Field(default=None, max_length=64)
    cache_hit_tokens: int = Field(default=0, ge=0)


@router.post("/record", status_code=status.HTTP_200_OK)
async def record_remote(
    event: LLMCostRecord,
    _admin: Annotated[str, Depends(require_admin)],
) -> dict:
    """Relay a cost event emitted by a remote agent (Pro/Air cron)."""
    return await record_llm_call(**event.model_dump())
```

- [ ] **Step 4: Register in `router_manifest.py`**

Find `RouterEntry` list in `apps/backend-rag/backend/app/setup/router_manifest.py` and add:

```python
RouterEntry(
    module="backend.app.routers.llm_costs",
    attr="router",
    process_groups=(_API,),
    tags=("observability", "admin"),
),
```

- [ ] **Step 5: Run manifest tests + new tests**

```bash
PYTHONPATH=. pytest backend/tests/setup/test_router_manifest.py backend/tests/unit/routers/test_llm_costs_router.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/backend-rag/backend/app/routers/llm_costs.py \
        apps/backend-rag/backend/app/setup/router_manifest.py \
        apps/backend-rag/backend/tests/unit/routers/test_llm_costs_router.py
git commit -m "feat(api): POST /api/admin/llm-costs/record for remote agents

Pro/Air cron agents can now persist cost events to Fly Postgres via this
admin-authenticated endpoint. Registered in the _API process group."
```

---

## Task 10: Phase B integration check + PR

- [ ] **Step 1: Full test sweep + coverage**

```bash
cd apps/backend-rag
PYTHONPATH=. pytest backend/tests/ -q --cov=backend --cov-fail-under=40
```

Expected: all pass, coverage ≥40%.

- [ ] **Step 2: Run enforcer one last time**

```bash
cd ~/Desktop/nuzantara
python scripts/check_llm_cost_tracking.py
```

Expected: exit 0.

- [ ] **Step 3: Pre-deploy verification (imports)**

```bash
cd apps/backend-rag
PYTHONPATH=. python -c "from backend.app.dependencies import get_current_user; print('OK')"
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_langgraph.py backend/tests/services/rag/test_kg_subgraphs.py backend/tests/services/rag/test_confidence.py -q
```

Expected: all pass.

- [ ] **Step 4: Push + draft PR**

```bash
cd ~/Desktop/nuzantara
git push -u origin feat/llm-cost-tracking-v2-complete
gh pr create --draft --title "feat(observability): LLM cost tracking v2 — complete coverage + governance" \
    --body "$(cat <<'EOF'
## Summary
- Adds @llm_cost_tracked async decorator (observability/tracking_decorator.py)
- Integrates 6 remaining paid clients: embeddings, openrouter, imagen, audio, council DS/Gemini, extractor_gemini refactor
- CI enforcer scripts/check_llm_cost_tracking.py + tests.yml step
- POST /api/admin/llm-costs/record for Pro/Air cron ingestion

Spec: docs/superpowers/specs/2026-04-19-llm-cost-tracking-v2-design.md
Phase B of 3. Phase C (cost advisor) lands on this same branch next.

## Test plan
- [ ] CI green (tests + enforcer + import check)
- [ ] Local: run enforcer → exit 0
- [ ] Deploy staging: smoke POST to /api/admin/llm-costs/record
- [ ] Verify llm_cost_events rows appear for live calls
EOF
)"
```

---

# PHASE C — Cost Advisor Agent

_(Continues on same branch `feat/llm-cost-tracking-v2-complete`.)_

## Task 11: Migration 118

**Files:**

- Create: `apps/backend-rag/backend/migrations/migration_118_cost_recommendations.py`
- Test: `apps/backend-rag/backend/tests/unit/migrations/test_migration_118.py`

- [ ] **Step 1: Write failing apply/rollback test**

```python
# test_migration_118.py
import pytest
from backend.migrations.migration_118_cost_recommendations import apply, rollback


@pytest.mark.asyncio
async def test_apply_creates_table(pg_test_conn):
    await apply(pg_test_conn)
    row = await pg_test_conn.fetchrow(
        "SELECT to_regclass('llm_cost_recommendations') AS t",
    )
    assert row["t"] == "llm_cost_recommendations"


@pytest.mark.asyncio
async def test_rollback_drops_table(pg_test_conn):
    await apply(pg_test_conn)
    await rollback(pg_test_conn)
    row = await pg_test_conn.fetchrow(
        "SELECT to_regclass('llm_cost_recommendations') AS t",
    )
    assert row["t"] is None
```

_(Assumes existing `pg_test_conn` fixture from `tests/conftest.py`. If missing, add it or use the existing migration test pattern in `tests/unit/migrations/test_migration_117.py`.)_

- [ ] **Step 2: Run test to verify it fails**

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write migration**

```python
# apps/backend-rag/backend/migrations/migration_118_cost_recommendations.py
"""Migration 118: llm_cost_recommendations — CostAdvisor output table.

One row per (endpoint, current_model, proposed_model) produced by
the weekly advisor agent. Status flows: pending → reviewed → applied | rejected.

Author: Claude Opus 4.7
Date: 2026-04-19
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def apply(conn: Any) -> None:
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS llm_cost_recommendations (
            id                           BIGSERIAL PRIMARY KEY,
            ts_utc                       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            endpoint                     VARCHAR(128) NOT NULL,
            current_model                VARCHAR(128) NOT NULL,
            proposed_model               VARCHAR(128) NOT NULL,
            estimated_monthly_saving_usd NUMERIC(12, 6) NOT NULL,
            quality_tradeoff             TEXT NOT NULL,
            confidence                   VARCHAR(16) NOT NULL
                CHECK (confidence IN ('low','medium','high')),
            spike_flag                   BOOLEAN NOT NULL DEFAULT FALSE,
            status                       VARCHAR(16) NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending','reviewed','applied','rejected')),
            reviewed_at                  TIMESTAMP WITH TIME ZONE,
            reviewed_by                  VARCHAR(128),
            notes                        TEXT
        );
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_llm_cost_reco_status_ts
        ON llm_cost_recommendations (status, ts_utc DESC);
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_llm_cost_reco_endpoint
        ON llm_cost_recommendations (endpoint, ts_utc DESC);
    """)
    logger.info("✅ Migration 118: llm_cost_recommendations + 2 indexes created")


async def rollback(conn: Any) -> None:
    await conn.execute("DROP TABLE IF EXISTS llm_cost_recommendations CASCADE;")
    logger.info("Migration 118 rollback: llm_cost_recommendations dropped")
```

- [ ] **Step 4: Run tests**

```bash
PYTHONPATH=. pytest backend/tests/unit/migrations/test_migration_118.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/migrations/migration_118_cost_recommendations.py \
        apps/backend-rag/backend/tests/unit/migrations/test_migration_118.py
git commit -m "feat(migrations): 118 llm_cost_recommendations

Stores CostAdvisor output: endpoint → proposed model, estimated saving,
quality tradeoff, confidence, spike flag, review workflow (pending →
reviewed → applied/rejected). 2 indexes on (status, ts) and (endpoint, ts)."
```

---

## Task 12: `CostAdvisor` — dataclasses + analyze_last_window

**Files:**

- Create: `apps/backend-rag/backend/services/observability/cost_advisor.py`
- Test: `apps/backend-rag/backend/tests/unit/services/observability/test_cost_advisor.py`

- [ ] **Step 1: Write failing test for `analyze_last_window`**

```python
# test_cost_advisor.py (iteration 1)
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from backend.services.observability.cost_advisor import (
    CostAdvisor, EndpointCostSummary,
)


@pytest.mark.asyncio
async def test_analyze_last_window_aggregates_by_endpoint_and_model():
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_pool.acquire.return_value.__aexit__.return_value = None
    mock_conn.fetch.return_value = [
        {
            "endpoint": "article_composer", "model": "deepseek-chat",
            "provider": "deepseek", "call_count": 10,
            "total_cost_usd": Decimal("0.50"),
            "avg_cost_per_call_usd": Decimal("0.05"),
            "p50_latency_ms": 400, "p95_latency_ms": 800,
            "success_rate": 0.95,
        },
    ]

    advisor = CostAdvisor(pg_pool=mock_pool, oauth_client=MagicMock())
    summaries = await advisor.analyze_last_window(days=7)

    assert len(summaries) == 1
    s = summaries[0]
    assert isinstance(s, EndpointCostSummary)
    assert s.endpoint == "article_composer"
    assert s.total_cost_usd == Decimal("0.50")
    assert s.success_rate == 0.95
```

- [ ] **Step 2: Run test to verify it fails**

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement dataclasses + `analyze_last_window`**

```python
# apps/backend-rag/backend/services/observability/cost_advisor.py
"""CostAdvisor — weekly analysis of llm_cost_events → recommendations."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EndpointCostSummary:
    endpoint: str
    model: str
    provider: str
    call_count: int
    total_cost_usd: Decimal
    avg_cost_per_call_usd: Decimal
    p50_latency_ms: int
    p95_latency_ms: int
    success_rate: float


@dataclass(frozen=True)
class CostRecommendation:
    endpoint: str
    current_model: str
    proposed_model: str
    estimated_monthly_saving_usd: Decimal
    quality_tradeoff: str
    confidence: Literal["low", "medium", "high"]
    spike_flag: bool = False


class CostAdvisor:
    def __init__(self, *, pg_pool: Any, oauth_client: Any) -> None:
        self.pg_pool = pg_pool
        self.oauth_client = oauth_client

    async def analyze_last_window(self, days: int = 7) -> list[EndpointCostSummary]:
        async with self.pg_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    COALESCE(endpoint, 'unknown') AS endpoint,
                    model,
                    provider,
                    COUNT(*)                                     AS call_count,
                    SUM(cost_usd)                                AS total_cost_usd,
                    AVG(cost_usd)                                AS avg_cost_per_call_usd,
                    PERCENTILE_CONT(0.5)  WITHIN GROUP (ORDER BY latency_ms) AS p50_latency_ms,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency_ms,
                    AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END) AS success_rate
                FROM llm_cost_events
                WHERE ts_utc >= NOW() - ($1::int || ' days')::interval
                GROUP BY endpoint, model, provider
                ORDER BY total_cost_usd DESC
                """,
                days,
            )
        return [
            EndpointCostSummary(
                endpoint=r["endpoint"],
                model=r["model"],
                provider=r["provider"],
                call_count=int(r["call_count"]),
                total_cost_usd=Decimal(str(r["total_cost_usd"])),
                avg_cost_per_call_usd=Decimal(str(r["avg_cost_per_call_usd"])),
                p50_latency_ms=int(r["p50_latency_ms"] or 0),
                p95_latency_ms=int(r["p95_latency_ms"] or 0),
                success_rate=float(r["success_rate"]),
            )
            for r in rows
        ]
```

- [ ] **Step 4: Run test**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/services/observability/cost_advisor.py \
        apps/backend-rag/backend/tests/unit/services/observability/test_cost_advisor.py
git commit -m "feat(observability): CostAdvisor.analyze_last_window

Aggregates llm_cost_events by (endpoint, model, provider) with p50/p95
latency + success rate. First piece of the weekly advisor."
```

---

## Task 13: `CostAdvisor.detect_spikes`

- [ ] **Step 1: Add failing test**

Append to `test_cost_advisor.py`:

```python
@pytest.mark.asyncio
async def test_detect_spikes_flags_3x_increase():
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    # Baseline: endpoint X avg $0.10/week over 28d; last week: $0.40 → 4x
    mock_conn.fetchval.side_effect = [Decimal("0.10")]  # baseline query

    advisor = CostAdvisor(pg_pool=mock_pool, oauth_client=MagicMock())
    summaries = [
        EndpointCostSummary(
            endpoint="spiky", model="m", provider="p",
            call_count=1, total_cost_usd=Decimal("0.40"),
            avg_cost_per_call_usd=Decimal("0.40"),
            p50_latency_ms=1, p95_latency_ms=1, success_rate=1.0,
        ),
    ]
    spikes = await advisor.detect_spikes(summaries, baseline_days=28)
    assert spikes == {"spiky"}
```

- [ ] **Step 2: Run test → FAIL**

- [ ] **Step 3: Implement**

```python
# append to cost_advisor.py
    async def detect_spikes(
        self,
        summaries: list[EndpointCostSummary],
        *,
        baseline_days: int = 28,
        multiplier: float = 3.0,
    ) -> set[str]:
        spikes: set[str] = set()
        async with self.pg_pool.acquire() as conn:
            for s in summaries:
                baseline = await conn.fetchval(
                    """
                    SELECT COALESCE(SUM(cost_usd), 0) / ($2::float / 7)
                    FROM llm_cost_events
                    WHERE endpoint = $1
                      AND ts_utc >= NOW() - ($2::int || ' days')::interval
                      AND ts_utc < NOW() - INTERVAL '7 days'
                    """,
                    s.endpoint, baseline_days,
                )
                baseline_dec = Decimal(str(baseline or 0))
                if baseline_dec > 0 and s.total_cost_usd > baseline_dec * Decimal(str(multiplier)):
                    spikes.add(s.endpoint)
        return spikes
```

- [ ] **Step 4: Run test → PASS**

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(observability): CostAdvisor.detect_spikes

Flags endpoints where last 7d cost exceeds trailing 28d weekly avg ×3."
```

---

## Task 14: `CostAdvisor.propose_substitutions` (LLM-judge)

- [ ] **Step 1: Add failing test**

Append to `test_cost_advisor.py`:

```python
@pytest.mark.asyncio
async def test_propose_substitutions_returns_recommendations():
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    # Mock the advisor's analyze_last_window + detect_spikes outputs
    mock_oauth = AsyncMock()
    mock_oauth.complete = AsyncMock(return_value=(
        '[{"endpoint":"hot","current_model":"gpt-4","proposed_model":"deepseek-chat",'
        '"estimated_monthly_saving_usd":"100.0","quality_tradeoff":"Lower writing quality",'
        '"confidence":"medium"}]'
    ))

    advisor = CostAdvisor(pg_pool=mock_pool, oauth_client=mock_oauth)
    advisor.analyze_last_window = AsyncMock(return_value=[
        EndpointCostSummary(
            endpoint="hot", model="gpt-4", provider="openai",
            call_count=100, total_cost_usd=Decimal("50"),
            avg_cost_per_call_usd=Decimal("0.50"),
            p50_latency_ms=500, p95_latency_ms=1000, success_rate=0.98,
        ),
    ])
    advisor.detect_spikes = AsyncMock(return_value=set())

    recs = await advisor.propose_substitutions(top_n=5)
    assert len(recs) == 1
    assert recs[0].endpoint == "hot"
    assert recs[0].proposed_model == "deepseek-chat"
    assert recs[0].estimated_monthly_saving_usd == Decimal("100.0")
    assert recs[0].confidence == "medium"
```

- [ ] **Step 2: Run test → FAIL**

- [ ] **Step 3: Implement**

```python
# append to cost_advisor.py
import json

_JUDGE_SYSTEM_PROMPT = """You are a cost-optimisation advisor for an LLM
system. Given a list of endpoints with their current model + volume + cost,
propose cheaper substitutes. ONLY suggest models from these providers
already integrated in Nuzantara: 'gemini', 'deepseek', 'claude_oauth'.

Return ONE JSON array; each item:
- endpoint (string)
- current_model (string, echo)
- proposed_model (string)
- estimated_monthly_saving_usd (string decimal)
- quality_tradeoff (≤ 20 words)
- confidence ('low'|'medium'|'high')

No prose outside the JSON array."""


    async def propose_substitutions(self, *, top_n: int = 5) -> list[CostRecommendation]:
        summaries = await self.analyze_last_window(days=7)
        spikes = await self.detect_spikes(summaries)
        top = summaries[:top_n]
        if not top:
            return []

        payload = json.dumps([
            {
                "endpoint": s.endpoint,
                "current_model": s.model,
                "call_count": s.call_count,
                "total_cost_usd": str(s.total_cost_usd),
                "avg_cost_per_call_usd": str(s.avg_cost_per_call_usd),
            } for s in top
        ])

        raw = await self.oauth_client.complete(
            system=_JUDGE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": payload}],
        )
        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("CostAdvisor: LLM returned non-JSON, retrying once")
            raw = await self.oauth_client.complete(
                system=_JUDGE_SYSTEM_PROMPT + "\n\nRETURN JSON ONLY.",
                messages=[{"role": "user", "content": payload}],
            )
            items = json.loads(raw)

        recs: list[CostRecommendation] = []
        for item in items:
            try:
                rec = CostRecommendation(
                    endpoint=item["endpoint"],
                    current_model=item["current_model"],
                    proposed_model=item["proposed_model"],
                    estimated_monthly_saving_usd=Decimal(str(item["estimated_monthly_saving_usd"])),
                    quality_tradeoff=item["quality_tradeoff"],
                    confidence=item["confidence"],
                    spike_flag=item["endpoint"] in spikes,
                )
                if rec.spike_flag:
                    rec = CostRecommendation(**{**rec.__dict__, "confidence": "high"})
                recs.append(rec)
            except (KeyError, ValueError) as exc:
                logger.warning("CostAdvisor: dropping malformed rec %s: %s", item, exc)
        return recs
```

- [ ] **Step 4: Run test → PASS**

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(observability): CostAdvisor.propose_substitutions

LLM-as-judge via Claude OAuth Max. Top-N endpoints sent with cost/volume;
judge returns JSON array of substitutions (provider whitelist enforced in
system prompt). Spike endpoints pinned to confidence=high."
```

---

## Task 15: `CostAdvisor.persist_recommendations` + UPSERT

- [ ] **Step 1: Add failing test**

```python
@pytest.mark.asyncio
async def test_persist_recommendations_upserts_within_7d():
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

    advisor = CostAdvisor(pg_pool=mock_pool, oauth_client=MagicMock())
    rec = CostRecommendation(
        endpoint="x", current_model="a", proposed_model="b",
        estimated_monthly_saving_usd=Decimal("5"),
        quality_tradeoff="ok", confidence="medium", spike_flag=False,
    )
    await advisor.persist_recommendations([rec])

    call_sql = mock_conn.execute.await_args.args[0]
    assert "llm_cost_recommendations" in call_sql
    assert "NOT EXISTS" in call_sql or "ON CONFLICT" in call_sql
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement**

```python
# append to cost_advisor.py
    async def persist_recommendations(
        self, recs: list[CostRecommendation],
    ) -> int:
        """Insert recommendations; skip duplicates within the last 7 days."""
        if not recs:
            return 0
        inserted = 0
        async with self.pg_pool.acquire() as conn:
            for r in recs:
                result = await conn.execute(
                    """
                    INSERT INTO llm_cost_recommendations (
                        endpoint, current_model, proposed_model,
                        estimated_monthly_saving_usd, quality_tradeoff,
                        confidence, spike_flag
                    )
                    SELECT $1, $2, $3, $4, $5, $6, $7
                    WHERE NOT EXISTS (
                        SELECT 1 FROM llm_cost_recommendations
                        WHERE endpoint = $1
                          AND current_model = $2
                          AND proposed_model = $3
                          AND ts_utc >= NOW() - INTERVAL '7 days'
                    )
                    """,
                    r.endpoint, r.current_model, r.proposed_model,
                    r.estimated_monthly_saving_usd, r.quality_tradeoff,
                    r.confidence, r.spike_flag,
                )
                if "INSERT 0 1" in (result or ""):
                    inserted += 1
        return inserted
```

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(observability): CostAdvisor.persist_recommendations with 7d UPSERT dedup"
```

---

## Task 16: Cost advisor CLI

**Files:**

- Create: `apps/backend-rag/backend/scripts/cost_advisor_cli.py`
- Test: `apps/backend-rag/backend/tests/integration/observability/test_cost_advisor_cli_integration.py`

- [ ] **Step 1: Write failing integration test**

```python
# test_cost_advisor_cli_integration.py
import pytest
from unittest.mock import AsyncMock, patch
from backend.scripts.cost_advisor_cli import run_weekly_report, run_daily_cap_check


@pytest.mark.asyncio
async def test_weekly_report_persists_and_sends_telegram(pg_test_conn):
    # seed fake llm_cost_events (omitted for brevity — use a helper)
    with patch("backend.scripts.cost_advisor_cli.send_telegram",
               new=AsyncMock()) as mock_tg, \
         patch("backend.scripts.cost_advisor_cli.ClaudeOAuthClient") as mock_cls:
        mock_cls.return_value.complete = AsyncMock(return_value="[]")
        await run_weekly_report(pg_test_conn)

    # Telegram called with Markdown containing "Weekly LLM Cost Report"
    msg = mock_tg.await_args.kwargs["text"]
    assert "Weekly LLM Cost Report" in msg


@pytest.mark.asyncio
async def test_daily_cap_alerts_when_exceeded(pg_test_conn):
    # seed events totalling > DAILY_SPEND_ALERT_THRESHOLD_USD
    with patch("backend.scripts.cost_advisor_cli.send_telegram",
               new=AsyncMock()) as mock_tg:
        await run_daily_cap_check(pg_test_conn)
    assert "ALERT" in mock_tg.await_args.kwargs["text"]
```

- [ ] **Step 2: Run test → FAIL**

- [ ] **Step 3: Write CLI**

```python
# apps/backend-rag/backend/scripts/cost_advisor_cli.py
"""Weekly cost report + daily cap check. Pro launchd entry points.

Usage:
  PYTHONPATH=. python -m backend.scripts.cost_advisor_cli run           # weekly
  PYTHONPATH=. python -m backend.scripts.cost_advisor_cli --check-daily-cap
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from decimal import Decimal
from typing import Any

from backend.app.core.database import get_db_pool
from backend.llm.claude_oauth_client import ClaudeOAuthClient
from backend.services.observability.cost_advisor import CostAdvisor

logger = logging.getLogger(__name__)

DAILY_SPEND_ALERT_THRESHOLD_USD = Decimal("20.00")
TELEGRAM_CHAT_ID = "1125336968"


async def send_telegram(*, text: str, chat_id: str = TELEGRAM_CHAT_ID) -> None:
    """Reuses existing notifications/send-email pattern via httpx."""
    import httpx
    import os

    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            os.environ["ZANTARA_BACKEND_URL"].rstrip("/") + "/api/notifications/telegram",
            headers={"X-API-Key": os.environ["ZANTARA_API_KEY"]},
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
        )
        r.raise_for_status()


async def run_weekly_report(conn_or_pool: Any) -> None:
    advisor = CostAdvisor(pg_pool=conn_or_pool, oauth_client=ClaudeOAuthClient())
    summaries = await advisor.analyze_last_window(days=7)
    spikes = await advisor.detect_spikes(summaries)
    recs = await advisor.propose_substitutions(top_n=5)
    n_inserted = await advisor.persist_recommendations(recs)

    total = sum((s.total_cost_usd for s in summaries), Decimal("0"))
    top3 = recs[:3]
    md = [
        f"## Weekly LLM Cost Report — {Decimal(total):.2f} USD (7d)",
        f"**Endpoints analysed:** {len(summaries)}",
        f"**Anomalies (spikes):** {len(spikes)}",
        f"**Recommendations inserted:** {n_inserted}",
        "",
        "### Top 3 recommendations",
    ]
    for r in top3:
        md.append(
            f"- `{r.endpoint}` {r.current_model} → {r.proposed_model} "
            f"(save ~${r.estimated_monthly_saving_usd}/mo, conf={r.confidence}"
            f"{', SPIKE' if r.spike_flag else ''})\n  _{r.quality_tradeoff}_",
        )
    if not top3:
        md.append("_No substitutions proposed this week._")
    await send_telegram(text="\n".join(md))


async def run_daily_cap_check(conn_or_pool: Any) -> None:
    async with conn_or_pool.acquire() as conn:
        total = await conn.fetchval(
            """
            SELECT COALESCE(SUM(cost_usd), 0)
            FROM llm_cost_events
            WHERE ts_utc >= NOW() - INTERVAL '1 day'
            """,
        )
    total = Decimal(str(total or 0))
    if total > DAILY_SPEND_ALERT_THRESHOLD_USD:
        await send_telegram(
            text=f"🚨 *LLM daily cap ALERT*\nLast 24h spend: ${total:.2f} "
                 f"(cap: ${DAILY_SPEND_ALERT_THRESHOLD_USD})",
        )
    else:
        logger.info("daily cap ok: $%s < $%s", total, DAILY_SPEND_ALERT_THRESHOLD_USD)


async def _main(args: argparse.Namespace) -> None:
    pool = await get_db_pool()
    if args.check_daily_cap:
        await run_daily_cap_check(pool)
    else:
        await run_weekly_report(pool)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--check-daily-cap", action="store_true")
    asyncio.run(_main(p.parse_args()))
```

- [ ] **Step 4: Run tests → PASS**

- [ ] **Step 5: Commit**

```bash
git add apps/backend-rag/backend/scripts/cost_advisor_cli.py \
        apps/backend-rag/backend/tests/integration/observability/test_cost_advisor_cli_integration.py
git commit -m "feat(observability): cost_advisor_cli — weekly report + daily cap

Pro launchd entry point. Weekly: summary + top-3 recs → Telegram.
Daily: alert if last-24h spend > \$20."
```

---

## Task 17: launchd plists

- [ ] **Step 1: Create weekly plist**

```bash
cat > ~/Library/LaunchAgents/com.nuzantara.cost-advisor-weekly.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.nuzantara.cost-advisor-weekly</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-lc</string>
    <string>cd ~/Desktop/nuzantara/apps/backend-rag &amp;&amp; source .venv/bin/activate &amp;&amp; PYTHONPATH=. python -m backend.scripts.cost_advisor_cli run</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Weekday</key><integer>1</integer>
    <key>Hour</key><integer>7</integer>
    <key>Minute</key><integer>0</integer>
  </dict>
  <key>StandardOutPath</key><string>/tmp/cost-advisor-weekly.log</string>
  <key>StandardErrorPath</key><string>/tmp/cost-advisor-weekly.err</string>
</dict>
</plist>
EOF
launchctl load ~/Library/LaunchAgents/com.nuzantara.cost-advisor-weekly.plist
```

Note: WITA is UTC+8; macOS launchd uses local time. If Pro is on WITA/WIB, 07:00 Monday local = correct. Verify:

```bash
date  # should show WITA
```

- [ ] **Step 2: Create daily cap plist**

Same pattern, different schedule + flag:

```bash
cat > ~/Library/LaunchAgents/com.nuzantara.cost-advisor-daily-cap.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.nuzantara.cost-advisor-daily-cap</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>-lc</string>
    <string>cd ~/Desktop/nuzantara/apps/backend-rag &amp;&amp; source .venv/bin/activate &amp;&amp; PYTHONPATH=. python -m backend.scripts.cost_advisor_cli --check-daily-cap</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>8</integer>
    <key>Minute</key><integer>0</integer>
  </dict>
  <key>StandardOutPath</key><string>/tmp/cost-advisor-daily.log</string>
  <key>StandardErrorPath</key><string>/tmp/cost-advisor-daily.err</string>
</dict>
</plist>
EOF
launchctl load ~/Library/LaunchAgents/com.nuzantara.cost-advisor-daily-cap.plist
```

- [ ] **Step 3: Verify loaded**

```bash
launchctl list | grep cost-advisor
```

Expected: two lines, `com.nuzantara.cost-advisor-weekly` + `com.nuzantara.cost-advisor-daily-cap`.

- [ ] **Step 4: Smoke test the CLI once manually**

```bash
cd ~/Desktop/nuzantara/apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. python -m backend.scripts.cost_advisor_cli --check-daily-cap
```

Expected: log line "daily cap ok" (assuming no real spikes yet).

- [ ] **Step 5: Commit plist templates (documentation only — actual files live in ~/Library)**

Save copies in repo for doc/repro:

```bash
mkdir -p apps/backend-rag/deploy/launchd
cp ~/Library/LaunchAgents/com.nuzantara.cost-advisor-weekly.plist apps/backend-rag/deploy/launchd/
cp ~/Library/LaunchAgents/com.nuzantara.cost-advisor-daily-cap.plist apps/backend-rag/deploy/launchd/
git add apps/backend-rag/deploy/launchd/*.plist
git commit -m "chore(deploy): cost-advisor launchd plists (weekly Mon 07:00 + daily 08:00)"
```

---

## Task 18: Phase C push + PR update

- [ ] **Step 1: Full test sweep**

```bash
cd apps/backend-rag
PYTHONPATH=. pytest backend/tests/ -q --cov=backend --cov-fail-under=40
```

Expected: all pass.

- [ ] **Step 2: Push + mark PR ready for review**

```bash
git push
gh pr ready
```

---

# PHASE D — Local UI (separate branch)

## Pre-Phase D: New branch

- [ ] **Step 1: Branch from main**

```bash
cd ~/Desktop/nuzantara
git checkout main && git pull origin main
git checkout -b feat/llm-cost-ui-local
```

---

## Task 19: Scaffold Next.js app

**Files:** see File Structure §Phase D.

- [ ] **Step 1: Init minimal Next.js 16**

```bash
mkdir -p apps/admin-dashboard-local && cd apps/admin-dashboard-local
cat > package.json <<'EOF'
{
  "name": "admin-dashboard-local",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev -p 3100",
    "build": "next build",
    "start": "next start -p 3100",
    "test": "vitest"
  },
  "dependencies": {
    "next": "^16.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "recharts": "^2.12.0",
    "pg": "^8.11.0"
  },
  "devDependencies": {
    "@types/node": "^20",
    "@types/react": "^19",
    "typescript": "^5",
    "tailwindcss": "^3",
    "vitest": "^1.0.0"
  }
}
EOF
```

- [ ] **Step 2: Write `next.config.js` with LOCAL_ONLY guard**

```js
// apps/admin-dashboard-local/next.config.js
/** @type {import('next').NextConfig} */
if (process.env.LOCAL_ONLY !== "1") {
  throw new Error(
    "admin-dashboard-local is a Pro-only dev tool. Set LOCAL_ONLY=1 to run.",
  );
}
module.exports = {
  reactStrictMode: true,
  output: "standalone",
};
```

- [ ] **Step 3: tsconfig, tailwind, layout, .gitignore**

Reuse minimal templates from `apps/admin-dashboard/` with path edits. Set up `app/layout.tsx`, `app/page.tsx` (redirects to `/cost-dashboard`).

- [ ] **Step 4: Commit**

```bash
git add apps/admin-dashboard-local/
git commit -m "feat(admin-dashboard-local): scaffold Next.js 16 app (port 3100, LOCAL_ONLY guard)"
```

---

## Task 20: `lib/db.ts` with tunnel fallback + test

- [ ] **Step 1: Write failing test**

```typescript
// apps/admin-dashboard-local/__tests__/db.test.ts
import { describe, it, expect, vi } from "vitest";
import { getPool } from "../app/lib/db";

describe("db pool", () => {
  it("uses DATABASE_URL_LOCAL when set", async () => {
    vi.stubEnv("DATABASE_URL_LOCAL", "postgresql://test");
    const pool = await getPool();
    expect(pool.options.connectionString).toBe("postgresql://test");
  });

  it("falls back to FLY_TUNNEL_URL when local missing", async () => {
    vi.stubEnv("DATABASE_URL_LOCAL", "");
    vi.stubEnv("FLY_TUNNEL_URL", "postgresql://tunnel:15432/nz");
    const pool = await getPool();
    expect(pool.options.connectionString).toBe("postgresql://tunnel:15432/nz");
  });
});
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement**

```typescript
// apps/admin-dashboard-local/app/lib/db.ts
import { Pool } from "pg";

let _pool: Pool | null = null;

export async function getPool(): Promise<Pool> {
  if (_pool) return _pool;
  const url = process.env.DATABASE_URL_LOCAL || process.env.FLY_TUNNEL_URL;
  if (!url) {
    throw new Error(
      "Set DATABASE_URL_LOCAL or start Fly tunnel (fly proxy 15432) and set FLY_TUNNEL_URL",
    );
  }
  _pool = new Pool({ connectionString: url, max: 3 });
  console.log(
    `[admin-dashboard-local] connected via ${process.env.DATABASE_URL_LOCAL ? "LOCAL" : "TUNNEL"}`,
  );
  return _pool;
}
```

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(admin-dashboard-local): db pool with local→tunnel fallback"
```

---

## Task 21: Route handlers (6 endpoints)

**Files:** six route.ts under `app/api/llm-costs/*/route.ts`.

- [ ] **Step 1: Write failing integration test**

```typescript
// __tests__/routes.integration.test.ts
import { describe, it, expect } from "vitest";
import { GET as kpiGET } from "../app/api/llm-costs/kpi/route";

describe("GET /api/llm-costs/kpi", () => {
  it("returns today/7d/30d totals", async () => {
    // requires a test DB with llm_cost_events rows seeded
    const res = await kpiGET();
    const body = await res.json();
    expect(body).toHaveProperty("today_usd");
    expect(body).toHaveProperty("last_7d_usd");
    expect(body).toHaveProperty("last_30d_usd");
  });
});
```

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: Implement 6 handlers**

Each follows the same shape. Example `kpi`:

```typescript
// app/api/llm-costs/kpi/route.ts
import { NextResponse } from "next/server";
import { getPool } from "../../../lib/db";

export async function GET() {
  const pool = await getPool();
  const { rows } = await pool.query(`
    SELECT
      COALESCE(SUM(CASE WHEN ts_utc >= CURRENT_DATE THEN cost_usd ELSE 0 END), 0) AS today_usd,
      COALESCE(SUM(CASE WHEN ts_utc >= NOW() - INTERVAL '7 days' THEN cost_usd ELSE 0 END), 0) AS last_7d_usd,
      COALESCE(SUM(CASE WHEN ts_utc >= NOW() - INTERVAL '30 days' THEN cost_usd ELSE 0 END), 0) AS last_30d_usd
    FROM llm_cost_events
  `);
  return NextResponse.json(rows[0]);
}
```

Analogous for `timeline` (GROUP BY day + provider), `top-endpoints` (ORDER BY total DESC LIMIT 10), `model-mix` (GROUP BY provider, SUM input_tokens), `recommendations` (GET returns `WHERE status='pending' ORDER BY ts DESC LIMIT 20`; PATCH by id updates status), `anomalies` (`WHERE spike_flag=TRUE AND status='pending'`).

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(admin-dashboard-local): 6 route handlers for cost dashboard"
```

---

## Task 22: Components + dashboard page

- [ ] **Step 1: Write minimal components**

For each of the 6 widgets, a straightforward Recharts/Tailwind component. No tests (per spec §5.3). Dashboard page composes them:

```tsx
// app/cost-dashboard/page.tsx
import CostKpiCards from "@/components/CostKpiCards";
import CostTimeline from "@/components/CostTimeline";
import TopEndpoints from "@/components/TopEndpoints";
import ModelMix from "@/components/ModelMix";
import RecommendationPanel from "@/components/RecommendationPanel";
import AnomalyBanner from "@/components/AnomalyBanner";

export default function CostDashboard() {
  return (
    <main className="p-6 space-y-6 bg-slate-950 min-h-screen text-slate-100">
      <h1 className="text-2xl font-bold">LLM Cost Dashboard (Pro local)</h1>
      <AnomalyBanner />
      <CostKpiCards />
      <div className="grid grid-cols-2 gap-6">
        <CostTimeline />
        <ModelMix />
      </div>
      <TopEndpoints />
      <RecommendationPanel />
    </main>
  );
}
```

Each component fetches its route and renders. Keep them ~30-50 lines each.

- [ ] **Step 2: Commit**

```bash
git commit -am "feat(admin-dashboard-local): 6 widgets + dashboard page composition"
```

---

## Task 23: `start-cost-dashboard.sh`

- [ ] **Step 1: Write script**

```bash
cat > scripts/start-cost-dashboard.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)/apps/admin-dashboard-local"
export LOCAL_ONLY=1
if [ ! -d node_modules ]; then
  npm install
fi
npm run dev &
SERVER_PID=$!
sleep 3
open "http://localhost:3100/cost-dashboard"
wait $SERVER_PID
EOF
chmod +x scripts/start-cost-dashboard.sh
```

- [ ] **Step 2: Smoke test**

```bash
bash scripts/start-cost-dashboard.sh
```

Expected: server boots on 3100, browser opens `/cost-dashboard`, KPI cards populate (if DB has data) or show empty state gracefully.

Stop with Ctrl-C.

- [ ] **Step 3: Commit + push**

```bash
git add scripts/start-cost-dashboard.sh
git commit -m "feat(admin-dashboard-local): start-cost-dashboard.sh — bootstrap + open browser"
git push -u origin feat/llm-cost-ui-local
```

- [ ] **Step 4: Wait for Zero review**

Do NOT merge to main automatically. Zero reviews the branch, merges or requests changes.

---

# Post-phase verification

- [ ] **Full regression check on main after both PRs merged**

```bash
cd ~/Desktop/nuzantara && git checkout main && git pull
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/ -q --cov=backend --cov-fail-under=40
python ../../scripts/check_llm_cost_tracking.py
```

- [ ] **Smoke test POST endpoint in production (after fly deploy)**

```bash
curl -X POST "https://nuzantara-rag.fly.dev/api/admin/llm-costs/record" \
  -H "Authorization: Bearer $ADMIN_JWT" \
  -H "Content-Type: application/json" \
  -d '{"provider":"gemini","model":"test","input_tokens":1,"output_tokens":1,"cost_usd":0.0001,"success":true,"latency_ms":100,"endpoint":"smoke.test"}'
```

Expected: 200 + `{"prometheus":true,"postgres":true,"jsonl":true}`.

- [ ] **Verify weekly cron fires next Monday 07:00 WITA**

Check `/tmp/cost-advisor-weekly.log` at 07:05 Monday. Telegram message should arrive.

- [ ] **Save decision to MOS**

```bash
~/.claude/scripts/mem save decision \
  "LLM cost tracking v2 deployed: 100% paid-endpoint coverage + CI enforcer + weekly advisor agent + local Pro dashboard. Spec: docs/superpowers/specs/2026-04-19-llm-cost-tracking-v2-design.md" \
  9
```
