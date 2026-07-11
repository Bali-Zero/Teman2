"""Regression test for the streaming CRM pre-call tool_map access.

Bug (2026-06-21): `orchestrator_streaming_core.py` read `self.core.tool_map`,
but OrchestratorCore has NO `tool_map` attribute — the {name: tool} dict lives
on `OrchestratorCore.reasoning_engine.tool_map`. Any query containing a CRM
keyword (e.g. Bahasa "berapa", "how many", "breakdown") entered the CRM pre-call
branch and raised AttributeError, crashing the whole streaming path → the channel
bot (Instagram/WhatsApp/Telegram) replied with a generic error. The non-streaming
path was unaffected (it never reads tool_map).

This test pins the correct access path so the regression cannot silently return.
"""

from __future__ import annotations

import inspect

from backend.services.rag.agentic import orchestrator_streaming_core


def test_streaming_crm_precall_reads_toolmap_via_reasoning_engine():
    """The CRM pre-call must read tool_map through reasoning_engine, not core."""
    src = inspect.getsource(orchestrator_streaming_core)
    # The broken access must be gone …
    assert "self.core.tool_map.get" not in src, (
        "Regression: streaming CRM pre-call reads self.core.tool_map, which "
        "AttributeErrors (OrchestratorCore has no tool_map). Use "
        "self.core.reasoning_engine.tool_map instead."
    )
    # … and the correct access must be present.
    assert "self.core.reasoning_engine.tool_map.get(" in src


def test_orchestrator_core_has_no_tool_map_but_reasoning_engine_does():
    """Pin the structural fact the fix relies on: tool_map lives on
    reasoning_engine, never directly on OrchestratorCore."""
    from backend.services.rag.agentic.orchestrator_core import OrchestratorCore
    from backend.services.rag.agentic.reasoning import ReasoningEngine

    # OrchestratorCore.__init__ does not assign self.tool_map
    core_src = inspect.getsource(OrchestratorCore.__init__)
    assert "self.tool_map" not in core_src, (
        "OrchestratorCore now sets self.tool_map — update the fix/test: the CRM "
        "pre-call could read it directly again."
    )
    # ReasoningEngine.__init__ does assign self.tool_map
    re_src = inspect.getsource(ReasoningEngine.__init__)
    assert "self.tool_map" in re_src
