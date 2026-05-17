"""Focused SearchService tests for SurfaceRouter activation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.search.search_service import SearchService


@pytest.mark.asyncio
async def test_prepare_search_context_uses_surface_router_when_available() -> None:
    """SearchService should honor the initialized SurfaceRouter in the primary path."""
    service = SearchService.__new__(SearchService)
    service.embedder = SimpleNamespace(
        generate_query_embedding=AsyncMock(return_value=[0.1] * 1536),
    )
    service._embedding_cache = {}
    service._embedding_cache_max = 256
    service.collection_manager = SimpleNamespace(
        get_collection=MagicMock(return_value=object()),
    )
    service.query_router = SimpleNamespace(
        route_query=MagicMock(return_value={"collection_name": "visa_oracle"}),
    )
    service.surface_router = SimpleNamespace(
        enabled=True,
        adecide=AsyncMock(
            return_value=SimpleNamespace(
                surface="qdrant_skills",
                primary_collection="bali_zero_skills_hybrid",
                collections=["bali_zero_skills_hybrid"],
                domain="skills",
                confidence=0.9,
                layer_used=1,
            ),
        ),
    )

    with patch(
        "backend.services.search.keyword_translator.get_keyword_translator",
        return_value=SimpleNamespace(translate=lambda query: query),
    ):
        _, collection_name, _, _, _ = await service._prepare_search_context(
            "internal ops workflow checklist",
            user_level=3,
            tier_filter=None,
            collection_override=None,
            apply_filters=None,
        )

    service.surface_router.adecide.assert_awaited_once()
    service.query_router.route_query.assert_not_called()
    service.collection_manager.get_collection.assert_called_once_with("bali_zero_skills_hybrid")
    assert collection_name == "bali_zero_skills_hybrid"


@pytest.mark.asyncio
async def test_route_search_query_falls_back_for_non_qdrant_surface() -> None:
    """Non-Qdrant SurfaceRouter decisions must not create empty collection searches."""
    service = SearchService.__new__(SearchService)
    service.query_router = SimpleNamespace(
        route_query=MagicMock(
            return_value={
                "collection_name": "legal_unified_hybrid_hybrid",
            },
        ),
    )
    service.surface_router = SimpleNamespace(
        enabled=True,
        adecide=AsyncMock(
            return_value=SimpleNamespace(
                surface="kg_agentic",
                primary_collection="",
                collections=[],
                domain="kg",
                confidence=0.82,
                layer_used=2,
            ),
        ),
    )

    routing_info = await service._route_search_query(
        "show company relationship graph",
        collection_override=None,
        enable_fallbacks=True,
    )

    service.surface_router.adecide.assert_awaited_once()
    service.query_router.route_query.assert_called_once()
    assert routing_info["collection_name"] == "legal_unified"
    assert routing_info["collections"] == ["legal_unified"]
    assert routing_info["confidence"] == 0.0


@pytest.mark.asyncio
async def test_route_search_query_canonicalizes_surface_collections() -> None:
    """SurfaceRouter physical collection names must map to CollectionManager keys."""
    service = SearchService.__new__(SearchService)
    service.query_router = SimpleNamespace(route_query=MagicMock())
    service.surface_router = SimpleNamespace(
        enabled=True,
        adecide=AsyncMock(
            return_value=SimpleNamespace(
                surface="qdrant_company",
                primary_collection="kbli_2025_final_hybrid",
                collections=[
                    "kbli_2025_final_hybrid",
                    "training_conversations_hybrid",
                    "legal_unified_hybrid_hybrid",
                ],
                domain="company",
                confidence=0.78,
                layer_used=1,
            ),
        ),
    )

    routing_info = await service._route_search_query(
        "PT PMA KBLI retail company setup",
        collection_override=None,
        enable_fallbacks=True,
    )

    service.query_router.route_query.assert_not_called()
    assert routing_info["collection_name"] == "kbli_2025_final"
    assert routing_info["collections"] == [
        "kbli_2025_final",
        "training_conversations_hybrid",
        "legal_unified",
    ]


@pytest.mark.asyncio
async def test_route_search_query_uses_legacy_router_when_surface_router_disabled() -> None:
    """SurfaceRouter must remain shadowed unless explicitly enabled."""
    service = SearchService.__new__(SearchService)
    service.query_router = SimpleNamespace(
        route_query=MagicMock(
            return_value={
                "collection_name": "visa_oracle",
            },
        ),
    )
    service.surface_router = SimpleNamespace(
        enabled=False,
        adecide=AsyncMock(),
    )

    routing_info = await service._route_search_query(
        "KITAS renewal documents",
        collection_override=None,
        enable_fallbacks=True,
    )

    service.surface_router.adecide.assert_not_called()
    service.query_router.route_query.assert_called_once()
    assert routing_info["collection_name"] == "visa_oracle"
    assert routing_info["collections"] == ["visa_oracle"]


@pytest.mark.asyncio
async def test_route_search_query_canonicalizes_legacy_router_collections() -> None:
    """Legacy routing must also return CollectionManager logical keys."""
    service = SearchService.__new__(SearchService)
    service.query_router = SimpleNamespace(
        route_query=MagicMock(
            return_value={
                "collection_name": "kbli_2025_final_hybrid",
                "collections": [
                    "kbli_2025_final_hybrid",
                    "legal_unified_hybrid_hybrid",
                ],
            },
        ),
    )
    service.surface_router = None

    routing_info = await service._route_search_query(
        "PT PMA KBLI company setup",
        collection_override=None,
        enable_fallbacks=True,
    )

    assert routing_info["collection_name"] == "kbli_2025_final"
    assert routing_info["collections"] == ["kbli_2025_final", "legal_unified"]
