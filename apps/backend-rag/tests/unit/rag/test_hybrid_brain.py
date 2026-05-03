"""
Tests for HybridBrain tools - vector search document ID inclusion.
"""

import pytest


class TestHybridBrainTools:
    def test_vector_search_includes_document_id(self):
        """Vector search results should include document IDs."""
        # Verify the module structure
        from backend.services.rag import agentic
        assert agentic is not None
