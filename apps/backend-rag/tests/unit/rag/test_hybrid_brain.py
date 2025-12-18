"""
Unit Tests for Hybrid Brain (Deep Dive) Capabilities
Verifies the integration of 'VectorSearchTool' (ID extraction) and 'DatabaseQueryTool' (Deep Dive).
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.rag.agentic.prompt_builder import SystemPromptBuilder
from services.rag.agentic.tools import DatabaseQueryTool, VectorSearchTool


@pytest.mark.asyncio
class TestHybridBrainTools:
    """Test suite for Hybrid Brain tools and logic"""

    async def test_vector_search_includes_document_id(self):
        """Verify VectorSearchTool includes document ID in output for agent visibility"""
        # Mock retriever
        mock_retriever = AsyncMock()

        # Mock search results with metadata containing chapter_id/document_id
        mock_results = {
            "results": [
                {
                    "text": "Snippet of Omnibus Law...",
                    "metadata": {
                        "title": "UU Cipta Kerja",
                        "chapter_id": "UU-11-2020-BAB-3",  # Primary ID source
                        "source_url": "http://law.go.id/uu11",
                    },
                    "score": 0.95,
                },
                {
                    "text": "Another snippet...",
                    "metadata": {
                        "title": "Tax Regulation",
                        "document_id": "PP-55-2022",  # Fallback ID source
                        "id": "chunk-123",
                    },
                    "score": 0.88,
                },
            ]
        }

        # Setup mock behavior
        mock_retriever.search_with_reranking.return_value = mock_results

        # Initialize tool
        tool = VectorSearchTool(retriever=mock_retriever)

        # Execute tool
        result_json = await tool.execute(query="Omnibus Law", collection="legal_unified")
        result = json.loads(result_json)
        content = result["content"]

        # Assertions
        assert "ID: UU-11-2020-BAB-3" in content
        assert "ID: PP-55-2022" in content
        assert "Snippet of Omnibus Law..." in content

    async def test_database_query_by_id(self):
        """Verify DatabaseQueryTool handles 'by_id' queries correctly"""
        # Mock DB pool and connection
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        # Mock DB result for full document
        mock_row = {
            "document_id": "UU-11-2020",
            "title": "Undang-Undang Cipta Kerja",
            "full_text": "PASAL 1... [Full 50 page text] ... PASAL 99",
        }
        mock_conn.fetchrow.return_value = mock_row

        # Initialize tool
        tool = DatabaseQueryTool(db_pool=mock_pool)

        # Execute tool with query_type="by_id"
        result = await tool.execute(search_term="UU-11-2020", query_type="by_id")

        # Verify SQL query structure
        # We can't check the exact string easily due to asyncpg args, but we check flow
        assert "=== FULL DOCUMENT (Deep Dive) ===" in result
        assert "ID: UU-11-2020" in result
        assert "PASAL 1..." in result

        # Verify correct SQL was called (conceptually)
        mock_conn.fetchrow.assert_called_once()
        call_args = mock_conn.fetchrow.call_args
        assert call_args is not None
        sql_query = call_args[0][0]
        assert "WHERE document_id = $1 OR id = $1" in sql_query

    async def test_prompt_includes_deep_dive_instructions(self):
        """Verify SystemPromptBuilder includes instructions for Deep Dive"""
        builder = SystemPromptBuilder()

        # Build prompt
        context = {"profile": {"name": "Test User"}, "facts": []}
        prompt = builder.build_system_prompt(
            user_id="test@example.com", context=context, query="Tell me about laws"
        )

        # Assertions
        assert "DEEP DIVE / FULL DOCUMENT READING" in prompt
        assert 'Call database_query(search_term="UU-11-2020", query_type="by_id")' in prompt
        assert "retrieve the COMPLETE text" in prompt
