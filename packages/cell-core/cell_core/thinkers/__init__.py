"""Concrete Thinker implementations for cell-core PulseLoop.

A Thinker satisfies ``cell_core.protocols.Thinker``: given sensor readings,
homeostatic state, and a memory context, it proposes an action.

The two thinkers shipped here:

* :class:`RuleBasedThinker` — deterministic rule table. Zero LLM cost,
  zero latency, zero dependencies. Always available.
* :class:`OllamaAwareThinker` — wraps a delegate (typically a more
  expressive Ollama-backed thinker). Adds graceful degradation: if the
  delegate raises or times out, falls back to the rule-based thinker.

Per project Cost constraint and Symbiosis Law 4, Ollama is **never** in
the critical path. Rule-based output is the source of truth; Ollama
output, when available, only enriches it.
"""
from __future__ import annotations

from cell_core.thinkers.ollama_aware import OllamaAwareThinker
from cell_core.thinkers.rule_based import RuleBasedThinker

__all__ = ["RuleBasedThinker", "OllamaAwareThinker"]
