"""
Tests for memory_vector router - initialization and DB setup.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestInitializeMemoryVectorDB:
    @pytest.mark.asyncio
    async def test_initialize_failure(self):
        """initialize_memory_vector_db should raise on connection failure."""
        with patch("backend.app.routers.memory_vector.QdrantClient") as MockQC, \
             patch("backend.app.routers.memory_vector.settings") as mock_settings:
            mock_settings.qdrant_url = "https://qdrant.test.com"
            mock_instance = MagicMock()
            mock_instance.get_collection_stats = AsyncMock(side_effect=Exception("Connection refused"))
            MockQC.return_value = mock_instance

            from backend.app.routers.memory_vector import initialize_memory_vector_db
            with pytest.raises(Exception, match="Connection refused"):
                await initialize_memory_vector_db("https://qdrant.test.com")
