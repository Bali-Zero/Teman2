"""
Integration Tests for CitationService
Tests citation formatting and source references
"""

import os
import sys
from pathlib import Path

import pytest

# Set environment variables before imports
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing_only_min_32_chars")

backend_path = Path(__file__).parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


@pytest.mark.integration
class TestCitationServiceIntegration:
    """Comprehensive integration tests for CitationService"""

    @pytest.fixture
    def service(self):
        """Create CitationService instance"""
        from services.citation_service import CitationService

        return CitationService()

    def test_initialization(self, service):
        """Test service initialization"""
        assert service is not None

    @pytest.mark.asyncio
    async def test_generate_citations(self, service):
        """Test generating citations from search results"""
        search_results = [
            {
                "text": "Document 1",
                "metadata": {"title": "Test Document 1", "url": "http://example.com/doc1"},
                "score": 0.9,
            },
            {
                "text": "Document 2",
                "metadata": {"title": "Test Document 2"},
                "score": 0.8,
            },
        ]

        citations = await service.generate_citations(search_results)

        assert citations is not None
        assert len(citations) == 2
        assert citations[0]["id"] == 1
        assert citations[1]["id"] == 2

    def test_create_citation_instructions_with_sources(self, service):
        """Test creating citation instructions with sources"""
        instructions = service.create_citation_instructions(sources_available=True)

        assert instructions is not None
        assert "Citation" in instructions or "citation" in instructions.lower()

    def test_create_citation_instructions_without_sources(self, service):
        """Test creating citation instructions without sources"""
        instructions = service.create_citation_instructions(sources_available=False)

        assert instructions == ""

    def test_extract_sources_from_rag(self, service):
        """Test extracting sources from RAG results"""
        rag_results = [
            {
                "text": "Test document",
                "metadata": {
                    "title": "Test Title",
                    "url": "http://example.com",
                    "date": "2024-01-01",
                    "category": "legal",
                },
                "score": 0.85,
            }
        ]

        sources = service.extract_sources_from_rag(rag_results)

        assert len(sources) == 1
        assert sources[0]["id"] == 1
        assert sources[0]["title"] == "Test Title"
        assert sources[0]["type"] == "rag"

    def test_format_sources_section(self, service):
        """Test formatting sources section"""
        sources = [
            {
                "id": 1,
                "title": "Test Document",
                "url": "http://example.com",
                "date": "2024-01-01",
            }
        ]

        formatted = service.format_sources_section(sources)

        assert formatted is not None
        assert "Sources:" in formatted
        assert "[1]" in formatted

    def test_format_sources_section_empty(self, service):
        """Test formatting empty sources section"""
        formatted = service.format_sources_section([])

        assert formatted == ""

    def test_inject_citation_context_into_prompt(self, service):
        """Test injecting citation context into prompt"""
        system_prompt = "You are a helpful assistant."
        sources = [
            {"id": 1, "title": "Test Document", "category": "legal"},
        ]

        enhanced = service.inject_citation_context_into_prompt(system_prompt, sources)

        assert enhanced is not None
        assert "Citation" in enhanced or "citation" in enhanced.lower()
        assert "Available Sources" in enhanced or "sources" in enhanced.lower()
