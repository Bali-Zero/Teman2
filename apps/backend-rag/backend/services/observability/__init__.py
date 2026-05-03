"""Observability primitives: cost tracking, structured events, audit trails.

Currently exposes the LLM cost recorder (see :mod:`llm_cost_recorder`) and
the shared async decorator for LLM cost tracking (see :mod:`tracking_decorator`).
"""

from backend.services.observability.llm_cost_recorder import (
    LLMCallEvent,
    LLMCostRecorder,
    get_llm_cost_recorder,
    record_llm_call,
)
from backend.services.observability.tracking_decorator import (
    llm_cost_tracked,
    set_usage,
)

__all__ = [
    "LLMCallEvent",
    "LLMCostRecorder",
    "get_llm_cost_recorder",
    "record_llm_call",
    "llm_cost_tracked",
    "set_usage",
]
