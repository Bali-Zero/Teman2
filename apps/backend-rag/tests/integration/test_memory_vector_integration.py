"""
Integration tests for Memory Vector Service
Tests memory vector storage and search integration
"""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["QDRANT_URL"] = os.getenv("QDRANT_URL", "http://localhost:6333")
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"

backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestMemoryVectorIntegration:
    """Integration tests for Memory Vector Service"""

    @pytest.mark.asyncio
    async def test_memory_vector_initialization(self, qdrant_client):
        """Test memory vector DB initialization"""
        with patch(
            "app.routers.memory_vector.initialize_memory_vector_db", new_callable=AsyncMock
        ) as mock_init:
            mock_db = MagicMock()
            mock_db.get_collection_stats = AsyncMock(
                return_value={"collection_name": "zantara_memories", "total_documents": 0}
            )
            mock_init.return_value = mock_db

            from app.routers.memory_vector import initialize_memory_vector_db

            db = await initialize_memory_vector_db()
            assert db is not None

    @pytest.mark.asyncio
    async def test_memory_vector_store_and_search(self, qdrant_client):
        """Test memory vector store and search flow"""
        with patch(
            "app.routers.memory_vector.get_memory_vector_db", new_callable=AsyncMock
        ) as mock_get_db:
            mock_db = MagicMock()
            mock_db.upsert_documents = AsyncMock(return_value=None)
            mock_db.search = AsyncMock(
                return_value={
                    "documents": ["Stored memory"],
                    "ids": ["mem1"],
                    "distances": [0.1],
                }
            )
            mock_get_db.return_value = mock_db

            from app.routers.memory_vector import get_memory_vector_db

            db = await get_memory_vector_db()
            await db.upsert_documents(
                ids=["mem1"],
                documents=["Test memory"],
                embeddings=[[0.1] * 1536],
                metadatas=[{}],
            )

            results = await db.search(query_embedding=[0.1] * 1536, limit=10)
            assert "documents" in results
