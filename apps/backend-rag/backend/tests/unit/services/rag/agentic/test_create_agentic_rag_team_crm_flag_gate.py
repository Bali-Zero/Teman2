"""WA team-assistant Phase 2 (2026-07-20): flag-gated tool registration.

`create_agentic_rag()` must only append the 4 team_crm_tools.py tools to the
orchestrator's fixed tool list when WA_TEAM_CRM_TOOLS_ENABLED is truthy. This
is the "hard absence when flag is off" contract: since the orchestrator's
Gemini function-declaration schema is built ONCE from this list at
construction time (never re-filtered per request — see team_crm_tools.py
module docstring), the flag being off means the tools literally do not
exist in that schema for ANY caller, not just non-team senders.

Follows the exact monkeypatch pattern established by
test_create_agentic_rag_faq_cache.py (capture constructor kwargs on a fake
AgenticRAGOrchestrator, never a real DB/LLM).
"""

from __future__ import annotations

from typing import Any

import backend.services.rag.agentic as agentic_module
from backend.services.rag.agentic.team_crm_tools import TEAM_CRM_TOOL_NAMES


class _FakeAgenticRAGOrchestrator:
    last_kwargs: dict[str, Any] | None = None

    def __init__(self, **kwargs: Any) -> None:
        _FakeAgenticRAGOrchestrator.last_kwargs = kwargs


def _tool_names(kwargs: dict[str, Any]) -> set[str]:
    return {t.name for t in kwargs["tools"]}


def test_flag_off_team_crm_tools_are_absent(monkeypatch) -> None:
    monkeypatch.setenv("WA_TEAM_CRM_TOOLS_ENABLED", "false")
    monkeypatch.setattr(agentic_module, "AgenticRAGOrchestrator", _FakeAgenticRAGOrchestrator)

    agentic_module.create_agentic_rag(retriever=None, db_pool=None)

    names = _tool_names(_FakeAgenticRAGOrchestrator.last_kwargs)
    assert names.isdisjoint(TEAM_CRM_TOOL_NAMES), (
        "team_crm_tools must be completely absent from the tool list when "
        "the flag is off — found: " + str(names & TEAM_CRM_TOOL_NAMES)
    )


def test_flag_unset_defaults_to_absent(monkeypatch) -> None:
    monkeypatch.delenv("WA_TEAM_CRM_TOOLS_ENABLED", raising=False)
    monkeypatch.setattr(agentic_module, "AgenticRAGOrchestrator", _FakeAgenticRAGOrchestrator)

    agentic_module.create_agentic_rag(retriever=None, db_pool=None)

    names = _tool_names(_FakeAgenticRAGOrchestrator.last_kwargs)
    assert names.isdisjoint(TEAM_CRM_TOOL_NAMES)


def test_flag_on_team_crm_tools_are_present(monkeypatch) -> None:
    monkeypatch.setenv("WA_TEAM_CRM_TOOLS_ENABLED", "true")
    monkeypatch.setattr(agentic_module, "AgenticRAGOrchestrator", _FakeAgenticRAGOrchestrator)

    agentic_module.create_agentic_rag(retriever=None, db_pool=None)

    names = _tool_names(_FakeAgenticRAGOrchestrator.last_kwargs)
    assert TEAM_CRM_TOOL_NAMES.issubset(names)


def test_flag_on_does_not_remove_existing_tools(monkeypatch) -> None:
    """Innocence: arming the flag is purely additive — every pre-existing
    tool (vector_search, get_pricing, crm_query, ...) must still be present."""
    monkeypatch.setenv("WA_TEAM_CRM_TOOLS_ENABLED", "true")
    monkeypatch.setattr(agentic_module, "AgenticRAGOrchestrator", _FakeAgenticRAGOrchestrator)

    agentic_module.create_agentic_rag(retriever=None, db_pool=None)

    names = _tool_names(_FakeAgenticRAGOrchestrator.last_kwargs)
    assert "crm_query" in names
    assert "get_pricing" in names
    assert "vector_search" in names
