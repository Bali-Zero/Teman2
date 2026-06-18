"""Tests for search_client_documents — the PII-isolated retrieval entrypoint.

The whole per-client design hinges on ONE invariant:

    A query scoped to client A can NEVER return client B's chunks.

This is enforced by always injecting `client_id` (and active state) into the
Qdrant metadata filter. These tests are the falsifiable proof of that
invariant — if the filter ever drops client_id, test_filter_always_scopes_to_
client fails.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_search_embeds_query_and_filters_by_client() -> None:
    from backend.services.crm.client_doc_indexer import search_client_documents

    embedder = AsyncMock()
    embedder.generate_single_embedding.return_value = [0.1] * 1536
    qdrant = AsyncMock()
    qdrant.search.return_value = {"results": []}

    await search_client_documents(qdrant, embedder, client_id=7, query="quando scade il kitas?")

    embedder.generate_single_embedding.assert_awaited_once()
    qdrant.search.assert_awaited_once()
    filt = qdrant.search.await_args.kwargs["filter"]
    assert filt["client_id"] == 7
    assert filt["state"] == "indexed_active"


@pytest.mark.asyncio
async def test_filter_always_scopes_to_client_isolation_invariant() -> None:
    """PII isolation: every search MUST carry the caller's client_id in the filter."""
    from backend.services.crm.client_doc_indexer import search_client_documents

    embedder = AsyncMock()
    embedder.generate_single_embedding.return_value = [0.2] * 1536
    qdrant = AsyncMock()
    qdrant.search.return_value = {"results": []}

    for cid in (7, 42, 999):
        qdrant.search.reset_mock()
        await search_client_documents(qdrant, embedder, client_id=cid, query="x")
        filt = qdrant.search.await_args.kwargs["filter"]
        # The filter is the ONLY thing standing between client A and client B.
        assert filt["client_id"] == cid


@pytest.mark.asyncio
async def test_search_empty_query_returns_empty_no_qdrant_call() -> None:
    from backend.services.crm.client_doc_indexer import search_client_documents

    embedder = AsyncMock()
    qdrant = AsyncMock()

    result = await search_client_documents(qdrant, embedder, client_id=7, query="   ")

    assert result == []
    qdrant.search.assert_not_awaited()
    embedder.generate_single_embedding.assert_not_awaited()
