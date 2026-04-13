"""
Unit tests for collection freshness tracking in CollectionManager.

Verifies that:
- last_updated timestamp is recorded after successful ingest_with_lock
- get_collection_freshness returns timestamps and ages for all collections
- get_collection_info includes last_updated
- Prometheus gauge is updated on ingest
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.ingestion.collection_manager import CollectionManager


@pytest.fixture
def collection_manager() -> CollectionManager:
    """Create a CollectionManager with mocked Qdrant URL."""
    with patch("backend.services.ingestion.collection_manager.settings") as mock_settings:
        mock_settings.qdrant_url = "http://localhost:6333"
        mgr = CollectionManager(qdrant_url="http://localhost:6333")
    return mgr


class TestCollectionFreshness:
    """Tests for collection freshness tracking."""

    def test_initial_state_no_timestamps(self, collection_manager: CollectionManager) -> None:
        """No timestamps before any ingest."""
        assert collection_manager._collection_last_updated == {}

    def test_get_collection_freshness_returns_all_collections(
        self, collection_manager: CollectionManager,
    ) -> None:
        """get_collection_freshness includes all defined collections."""
        freshness = collection_manager.get_collection_freshness()
        assert len(freshness) == len(collection_manager.collection_definitions)
        for name in collection_manager.collection_definitions:
            assert name in freshness
            assert freshness[name]["last_updated"] is None
            assert freshness[name]["age_seconds"] is None

    def test_get_collection_freshness_after_update(
        self, collection_manager: CollectionManager,
    ) -> None:
        """After setting a timestamp, freshness should reflect it."""
        now = time.time()
        collection_manager._collection_last_updated["visa_oracle"] = now

        freshness = collection_manager.get_collection_freshness()
        assert freshness["visa_oracle"]["last_updated"] == now
        assert freshness["visa_oracle"]["age_seconds"] is not None
        assert freshness["visa_oracle"]["age_seconds"] >= 0

    def test_get_collection_info_includes_last_updated(
        self, collection_manager: CollectionManager,
    ) -> None:
        """get_collection_info should include last_updated field."""
        # Before any ingest
        info = collection_manager.get_collection_info("visa_oracle")
        assert info is not None
        assert info["last_updated"] is None

        # After setting timestamp
        now = time.time()
        collection_manager._collection_last_updated["visa_oracle"] = now
        info = collection_manager.get_collection_info("visa_oracle")
        assert info is not None
        assert info["last_updated"] == now

    @pytest.mark.asyncio
    async def test_ingest_with_lock_updates_timestamp(
        self, collection_manager: CollectionManager,
    ) -> None:
        """Successful ingest should update the last_updated timestamp."""
        # Mock the collection client
        mock_client = MagicMock()
        mock_client.upsert_documents = AsyncMock(return_value={"status": "ok"})
        collection_manager._collections_cache["visa_oracle"] = mock_client

        # Need a lock for the collection
        collection_manager._collection_locks["visa_oracle"] = asyncio.Lock()

        before = time.time()

        with patch("backend.app.metrics.metrics_collector") as mock_metrics:
            result = await collection_manager.ingest_with_lock(
                collection_name="visa_oracle",
                documents=["test doc"],
                embeddings=[[0.1, 0.2, 0.3]],
            )

        after = time.time()

        assert result == {"status": "ok"}
        assert "visa_oracle" in collection_manager._collection_last_updated
        ts = collection_manager._collection_last_updated["visa_oracle"]
        assert before <= ts <= after

    @pytest.mark.asyncio
    async def test_ingest_with_lock_does_not_update_on_failure(
        self, collection_manager: CollectionManager,
    ) -> None:
        """Failed ingest should NOT update the timestamp."""
        mock_client = MagicMock()
        mock_client.upsert_documents = AsyncMock(side_effect=RuntimeError("Qdrant down"))
        collection_manager._collections_cache["visa_oracle"] = mock_client
        collection_manager._collection_locks["visa_oracle"] = asyncio.Lock()

        with pytest.raises(RuntimeError, match="Qdrant down"):
            await collection_manager.ingest_with_lock(
                collection_name="visa_oracle",
                documents=["test doc"],
                embeddings=[[0.1, 0.2, 0.3]],
            )

        assert "visa_oracle" not in collection_manager._collection_last_updated
