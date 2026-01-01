"""
Unit tests for CitationService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from services.search.citation_service import CitationService


@pytest.fixture
def citation_service():
    """Create CitationService instance"""
    return CitationService()


@pytest.fixture
def mock_search_results():
    """Mock search results"""
    return [
        {
            "id": "1",
            "metadata": {
                "title": "Test Document",
                "url": "https://example.com/doc1",
                "date": "2024-01-01"
            },
            "content": "Test content"
        },
        {
            "id": "2",
            "metadata": {
                "title": "Another Document",
                "url": "https://example.com/doc2"
            },
            "content": "More content"
        }
    ]


class TestCitationService:
    """Tests for CitationService"""

    def test_init(self):
        """Test initialization"""
        service = CitationService()
        assert service.search_service is None

    def test_init_with_search_service(self):
        """Test initialization with search service"""
        mock_search = MagicMock()
        service = CitationService(search_service=mock_search)
        assert service.search_service == mock_search

    def test_create_citation_instructions_with_sources(self, citation_service):
        """Test creating citation instructions with sources"""
        instructions = citation_service.create_citation_instructions(sources_available=True)
        assert "Citation Guidelines" in instructions
        assert "[1]" in instructions

    def test_create_citation_instructions_no_sources(self, citation_service):
        """Test creating citation instructions without sources"""
        instructions = citation_service.create_citation_instructions(sources_available=False)
        assert instructions == ""

    def test_extract_sources_from_rag(self, citation_service, mock_search_results):
        """Test extracting sources from RAG results"""
        citations = citation_service.extract_sources_from_rag(mock_search_results)
        assert len(citations) == 2
        assert citations[0]["id"] == 1
        assert citations[0]["title"] == "Test Document"

    def test_extract_sources_from_rag_empty(self, citation_service):
        """Test extracting sources from empty results"""
        citations = citation_service.extract_sources_from_rag([])
        assert citations == []

    def test_extract_sources_from_rag_no_metadata(self, citation_service):
        """Test extracting sources without metadata"""
        results = [{"id": "1", "content": "test"}]
        citations = citation_service.extract_sources_from_rag(results)
        assert len(citations) == 1
        assert citations[0]["title"] == "Document 1"

    def test_format_sources_section(self, citation_service):
        """Test formatting sources section"""
        citations = [
            {"id": 1, "title": "Doc 1", "url": "https://example.com/1"},
            {"id": 2, "title": "Doc 2"}
        ]
        formatted = citation_service.format_sources_section(citations)
        assert "[1]" in formatted
        assert "[2]" in formatted
        assert "Doc 1" in formatted

    def test_format_sources_section_empty(self, citation_service):
        """Test formatting empty sources"""
        formatted = citation_service.format_sources_section([])
        assert formatted == ""

    def test_inject_citation_context_into_prompt(self, citation_service):
        """Test injecting citation context into prompt"""
        prompt = "Original prompt"
        sources = [{"id": 1, "title": "Source 1"}]
        result = citation_service.inject_citation_context_into_prompt(prompt, sources)
        assert "Citation Guidelines" in result
        assert "Source 1" in result

    def test_validate_citations_in_response(self, citation_service):
        """Test validating citations in response"""
        response = "Statement [1] and another [2]."
        sources = [{"id": 1, "title": "Source 1"}, {"id": 2, "title": "Source 2"}]
        result = citation_service.validate_citations_in_response(response, sources)
        assert result["valid"] is True
        assert len(result["citations_found"]) == 2

    def test_append_sources_to_response(self, citation_service):
        """Test appending sources to response"""
        response = "Original response"
        sources = [{"id": 1, "title": "Source 1"}]
        result = citation_service.append_sources_to_response(response, sources)
        assert "Sources:" in result
        assert "Source 1" in result

    @pytest.mark.asyncio
    async def test_generate_citations(self, citation_service, mock_search_results):
        """Test async generate_citations"""
        citations = await citation_service.generate_citations(mock_search_results)
        assert len(citations) == 2
        assert citations[0]["id"] == 1

