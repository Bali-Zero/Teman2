"""Background task primitives — fire-and-forget with strong-ref + error surfacing.

Problem solved
--------------
Bare ``asyncio.create_task(coro)`` without capturing the return value is a
latent bug: CPython holds only a *weak* reference to the task internally, so
if the caller drops the reference the task can be garbage-collected mid-flight,
silently dropping the work. Additionally, exceptions raised inside such tasks
never surface — they are swallowed by the destructor.

``spawn()`` fixes both:

1. The created task is added to a module-level set (``_inflight``) so it is
   retained until it completes.
2. A done-callback removes the task from the set and, if the task raised
   (and was not cancelled), logs the exception at ERROR level with full
   traceback.

Use this instead of ``asyncio.create_task`` for any background/fire-and-forget
work where you do not need to await the result from the caller.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Coroutine

logger = logging.getLogger(__name__)

_inflight: set[asyncio.Task[Any]] = set()


def spawn(
    coro: Coroutine[Any, Any, Any],
    *,
    name: str | None = None,
) -> asyncio.Task[Any]:
    """Schedule ``coro`` as a background task with strong-ref + error surfacing.

    Returns the ``asyncio.Task`` so callers may still store / cancel / await
    it if desired. The task is retained by this module until completion, so
    dropping the return value is safe.
    """
    task = asyncio.create_task(coro, name=name)
    _inflight.add(task)
    task.add_done_callback(_on_done)
    return task


def _on_done(task: asyncio.Task[Any]) -> None:
    _inflight.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error(
            "background task %r failed: %s",
            task.get_name(),
            exc,
            exc_info=exc,
        )


__all__ = ["spawn"]
