"""P7 (SPEC v2 D3): create_agentic_rag() must thread faq_cache into AgenticRAGOrchestrator.

Regression coverage for the FAQ-cache scope mismatch found by the adversarial panel:
the factory function silently dropped faq_cache, so every orchestrator built via
create_agentic_rag() (IntelligentRouter's production path included) never saw the
FAQ cache even when app.state.faq_cache was healthy.
"""

from __future__ import annotations

from typing import Any

import backend.services.rag.agentic as agentic_module


class _FakeAgenticRAGOrchestrator:
    """Captures constructor kwargs without doing any real initialization work."""

    last_kwargs: dict[str, Any] | None = None

    def __init__(self, **kwargs: Any) -> None:
        _FakeAgenticRAGOrchestrator.last_kwargs = kwargs


def test_create_agentic_rag_passes_faq_cache_through(monkeypatch) -> None:
    monkeypatch.setattr(agentic_module, "AgenticRAGOrchestrator", _FakeAgenticRAGOrchestrator)

    sentinel_faq_cache = object()

    agentic_module.create_agentic_rag(
        retriever=None,
        db_pool=None,
        faq_cache=sentinel_faq_cache,
    )

    assert _FakeAgenticRAGOrchestrator.last_kwargs is not None
    assert _FakeAgenticRAGOrchestrator.last_kwargs["faq_cache"] is sentinel_faq_cache


def test_create_agentic_rag_defaults_faq_cache_to_none(monkeypatch) -> None:
    monkeypatch.setattr(agentic_module, "AgenticRAGOrchestrator", _FakeAgenticRAGOrchestrator)

    agentic_module.create_agentic_rag(retriever=None, db_pool=None)

    assert _FakeAgenticRAGOrchestrator.last_kwargs is not None
    assert _FakeAgenticRAGOrchestrator.last_kwargs["faq_cache"] is None
