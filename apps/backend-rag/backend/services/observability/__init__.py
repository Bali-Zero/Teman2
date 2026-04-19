"""Observability primitives: cost tracking, structured events, audit trails.

Currently exposes the LLM cost recorder (see :mod:`llm_cost_recorder`).
"""

from backend.services.observability.llm_cost_recorder import (
    LLMCallEvent,
    LLMCostRecorder,
    get_llm_cost_recorder,
    record_llm_call,
)

__all__ = [
    "LLMCallEvent",
    "LLMCostRecorder",
    "get_llm_cost_recorder",
    "record_llm_call",
]
