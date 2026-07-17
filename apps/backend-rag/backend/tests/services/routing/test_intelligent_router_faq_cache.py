"""P7 (SPEC v2 D3): IntelligentRouter must accept faq_cache and thread it into
create_agentic_rag() — mirrors the existing semantic_cache wiring.

Regression coverage for the FAQ-cache scope mismatch: IntelligentRouter is the
production entry point used by initialize_intelligent_router() (service_initializer.py)
and previously had no way to receive app.state.faq_cache at all.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from backend.services.routing import intelligent_router as intelligent_router_module


def test_intelligent_router_passes_faq_cache_to_create_agentic_rag() -> None:
    sentinel_faq_cache = object()
    captured: dict[str, Any] = {}

    def fake_create_agentic_rag(**kwargs: Any) -> MagicMock:
        captured.update(kwargs)
        return MagicMock()

    with (
        patch(
            "backend.services.rag.agentic.create_agentic_rag",
            side_effect=fake_create_agentic_rag,
        ),
        patch(
            "backend.core.redis_manager.RedisManager.get_instance",
            side_effect=RuntimeError("no redis in unit test"),
        ),
    ):
        intelligent_router_module.IntelligentRouter(
            search_service=None,
            db_pool=None,
            faq_cache=sentinel_faq_cache,
        )

    assert captured.get("faq_cache") is sentinel_faq_cache


def test_intelligent_router_defaults_faq_cache_to_none() -> None:
    captured: dict[str, Any] = {}

    def fake_create_agentic_rag(**kwargs: Any) -> MagicMock:
        captured.update(kwargs)
        return MagicMock()

    with (
        patch(
            "backend.services.rag.agentic.create_agentic_rag",
            side_effect=fake_create_agentic_rag,
        ),
        patch(
            "backend.core.redis_manager.RedisManager.get_instance",
            side_effect=RuntimeError("no redis in unit test"),
        ),
    ):
        intelligent_router_module.IntelligentRouter(search_service=None, db_pool=None)

    assert captured.get("faq_cache") is None
