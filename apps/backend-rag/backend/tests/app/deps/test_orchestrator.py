"""P7 (SPEC v2 D3): get_orchestrator() must read request.app.state.faq_cache and
thread it into create_agentic_rag() when lazily constructing the singleton.

Regression coverage: the request-scoped dependency previously ignored
app.state.faq_cache entirely, so any router depending on get_orchestrator()
never benefited from the FAQ cache even when it was healthy.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from backend.app.deps import orchestrator as orchestrator_deps


@pytest.fixture(autouse=True)
def _reset_singleton():
    orchestrator_deps._agentic_rag_orchestrator = None
    yield
    orchestrator_deps._agentic_rag_orchestrator = None


@pytest.mark.asyncio
async def test_get_orchestrator_passes_app_state_faq_cache_to_factory() -> None:
    sentinel_faq_cache = object()
    captured: dict[str, Any] = {}

    def fake_create_agentic_rag(**kwargs: Any) -> MagicMock:
        captured.update(kwargs)
        return MagicMock(core=None)

    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                db_pool=None,
                search_service=None,
                specialized_router=None,
                surface_router=None,
                faq_cache=sentinel_faq_cache,
            ),
        ),
    )

    with patch(
        "backend.services.rag.agentic.create_agentic_rag",
        side_effect=fake_create_agentic_rag,
    ):
        await orchestrator_deps.get_orchestrator(request)

    assert captured.get("faq_cache") is sentinel_faq_cache


@pytest.mark.asyncio
async def test_get_orchestrator_defaults_faq_cache_to_none_when_absent() -> None:
    captured: dict[str, Any] = {}

    def fake_create_agentic_rag(**kwargs: Any) -> MagicMock:
        captured.update(kwargs)
        return MagicMock(core=None)

    # app.state without a faq_cache attribute at all (service not yet initialized)
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                db_pool=None,
                search_service=None,
                specialized_router=None,
                surface_router=None,
            ),
        ),
    )

    with patch(
        "backend.services.rag.agentic.create_agentic_rag",
        side_effect=fake_create_agentic_rag,
    ):
        await orchestrator_deps.get_orchestrator(request)

    assert captured.get("faq_cache") is None
