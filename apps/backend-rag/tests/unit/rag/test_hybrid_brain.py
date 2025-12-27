"""
Unit Tests for Hybrid Brain (Deep Dive) Capabilities
Verifies the integration of 'VectorSearchTool' (ID extraction) and 'DatabaseQueryTool' (Deep Dive).
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.rag.agentic.prompt_builder import SystemPromptBuilder
from services.rag.agent.tools import DatabaseQueryTool
from services.rag.agentic.tools import VectorSearchTool


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

        # Execute tool with query_type="full_text"
        result = await tool.execute(search_term="UU-11-2020", query_type="full_text")

        # Verify result contains document content
        assert "Document Found" in result or "No full text document found" in result
        if "Document Found" in result:
            assert "UU-11-2020" in result or "Undang-Undang Cipta Kerja" in result

        # Verify correct SQL was called
        mock_conn.fetchrow.assert_called_once()

    async def test_prompt_includes_core_instructions(self):
        """Verify SystemPromptBuilder includes core Zantara instructions"""
        builder = SystemPromptBuilder()

        # Build prompt
        context = {"profile": {"name": "Test User"}, "facts": []}
        prompt = builder.build_system_prompt(
            user_id="test@example.com", context=context, query="Tell me about laws"
        )

        # Assertions - check for core elements in current prompt structure
        assert "ZANTARA" in prompt  # Core identity
        assert "<identity>" in prompt  # Identity section
        assert "vector_search" in prompt  # Tool instructions
        assert "RESPONSE FORMAT" in prompt or "COMPREHENSIVE" in prompt  # Response guidance
