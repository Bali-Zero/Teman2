"""Process-local admission control for Intake Ollama inference.

The Intake worker deliberately runs more than one queue slot so cheap database,
validation, and routing work can overlap.  Ollama on the Pro is a different
resource: concurrent OCR/extraction generations compete for the same GPU and can
turn a few-second request into a five-minute timeout.  This module keeps queue
concurrency while serialising only the local model calls.

The gate is per asyncio event loop.  That makes it safe for the long-lived worker
and avoids binding a module-level semaphore to the first pytest event loop.
"""

from __future__ import annotations

import asyncio
import logging
import os
import weakref
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

logger = logging.getLogger("zantara.intake.inference_runtime")

DEFAULT_OLLAMA_MAX_INFLIGHT = 1
# Intake alternates qwen2.5vl OCR with qwen3.5 text extraction. Pro currently
# admits one loaded Ollama model at a time; a long residency hint therefore
# makes the next model wait behind an idle predecessor until that hint expires.
# A short grace keeps adjacent same-model page calls warm without converting a
# model switch into repeated HTTP timeouts.
DEFAULT_OLLAMA_KEEP_ALIVE = "5s"
_MAX_CONFIGURED_INFLIGHT = 8


@dataclass(frozen=True)
class OllamaInferenceLease:
    """Metadata about one acquired inference slot."""

    capacity: int
    wait_ms: int


_gates: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, tuple[int, asyncio.Semaphore]] = (
    weakref.WeakKeyDictionary()
)


def ollama_max_inflight() -> int:
    """Return the bounded process-local Ollama concurrency."""
    raw = os.getenv("INTAKE_OLLAMA_MAX_INFLIGHT", str(DEFAULT_OLLAMA_MAX_INFLIGHT))
    try:
        configured = int(raw)
    except ValueError:
        logger.warning(
            "invalid INTAKE_OLLAMA_MAX_INFLIGHT=%r; using %d",
            raw,
            DEFAULT_OLLAMA_MAX_INFLIGHT,
        )
        configured = DEFAULT_OLLAMA_MAX_INFLIGHT
    return min(max(configured, 1), _MAX_CONFIGURED_INFLIGHT)


def ollama_keep_alive() -> str:
    """Return the Ollama residency hint shared by OCR/classify/extract."""
    return os.getenv("INTAKE_OLLAMA_KEEP_ALIVE", DEFAULT_OLLAMA_KEEP_ALIVE).strip() or (
        DEFAULT_OLLAMA_KEEP_ALIVE
    )


def clear_ollama_inference_gates() -> None:
    """Clear idle gates after configuration changes in tests.

    Production configuration is immutable for the lifetime of the worker.  This
    helper exists so tests that use a fresh event loop or a different capacity do
    not inherit state from another case.
    """
    _gates.clear()


def _gate_for_running_loop() -> tuple[int, asyncio.Semaphore]:
    loop = asyncio.get_running_loop()
    existing = _gates.get(loop)
    if existing is not None:
        return existing
    capacity = ollama_max_inflight()
    created = (capacity, asyncio.Semaphore(capacity))
    _gates[loop] = created
    return created


@asynccontextmanager
async def ollama_inference_slot(
    *,
    operation: str,
    model: str,
) -> AsyncIterator[OllamaInferenceLease]:
    """Acquire the shared Ollama slot around exactly one HTTP generation call."""
    capacity, gate = _gate_for_running_loop()
    loop = asyncio.get_running_loop()
    started = loop.time()
    await gate.acquire()
    wait_ms = int((loop.time() - started) * 1000)
    if wait_ms >= 100:
        logger.info(
            "intake Ollama admission operation=%s model=%s waited_ms=%d capacity=%d",
            operation,
            model,
            wait_ms,
            capacity,
        )
    try:
        yield OllamaInferenceLease(capacity=capacity, wait_ms=wait_ms)
    finally:
        gate.release()
