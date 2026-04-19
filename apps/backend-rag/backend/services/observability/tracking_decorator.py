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
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

from backend.services.observability.llm_cost_recorder import record_llm_call

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
            from backend.services.llm_clients import pricing

            token = _usage_ctx.set(None)
            t0 = time.monotonic()
            success = False
            err: str | None = None
            try:
                result = await fn(*args, **kwargs)
                success = True
                return result
            except BaseException as exc:
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
                except Exception as exc:
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
                except Exception as rec_exc:
                    logger.warning(
                        "llm_cost_tracked: recorder failed for %s/%s: %s",
                        provider, model, rec_exc,
                    )

        return wrapper

    return decorator
