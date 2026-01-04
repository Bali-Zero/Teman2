"""
Unit tests for CitationService
Target: >95% coverage
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

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
                "date": "2024-01-01",
            },
            "content": "Test content",
        },
        {
            "id": "2",
            "metadata": {"title": "Another Document", "url": "https://example.com/doc2"},
            "content": "More content",
        },
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
            {"id": 2, "title": "Doc 2"},
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

    def test_format_sources_section_with_date(self, citation_service):
        """Test formatting sources with date - covers line 162-167"""
        sources = [
            {
                "id": 1,
                "title": "Doc 1",
                "url": "https://example.com",
                "date": "2024-01-15T10:30:00Z",
            }
        ]
        formatted = citation_service.format_sources_section(sources)
        assert "[1]" in formatted
        assert "2024-01-15" in formatted  # Date truncated to YYYY-MM-DD

    def test_format_sources_section_date_short(self, citation_service):
        """Test formatting sources with short date string - covers line 163"""
        sources = [
            {"id": 1, "title": "Doc 1", "date": "2024"}  # Less than 10 chars
        ]
        formatted = citation_service.format_sources_section(sources)
        assert "[1]" in formatted
        assert "2024" in formatted

    def test_format_sources_section_date_exception(self, citation_service):
        """Test formatting sources with problematic date - covers line 166-167"""
        sources = [
            {"id": 1, "title": "Doc 1", "date": None}  # None date
        ]
        formatted = citation_service.format_sources_section(sources)
        assert "[1]" in formatted
        assert "Doc 1" in formatted

    def test_inject_citation_context_empty_sources(self, citation_service):
        """Test injecting citation context with empty sources - covers line 188"""
        prompt = "Original prompt"
        result = citation_service.inject_citation_context_into_prompt(prompt, [])
        assert result == prompt

    def test_inject_citation_context_with_category(self, citation_service):
        """Test injecting citation context with source category - covers line 198"""
        prompt = "Original prompt"
        sources = [{"id": 1, "title": "Source 1", "category": "immigration"}]
        result = citation_service.inject_citation_context_into_prompt(prompt, sources)
        assert "Category: immigration" in result

    def test_inject_citation_context_without_category(self, citation_service):
        """Test injecting citation context without category"""
        prompt = "Original prompt"
        sources = [{"id": 1, "title": "Source 1"}]  # No category
        result = citation_service.inject_citation_context_into_prompt(prompt, sources)
        assert "Source 1" in result
        assert "Category:" not in result

    def test_validate_citations_invalid_citation(self, citation_service):
        """Test validating citations with invalid citation - covers line 256"""
        response = "Statement [1] and invalid [5]."
        sources = [{"id": 1, "title": "Source 1"}]  # Only source 1
        result = citation_service.validate_citations_in_response(response, sources)
        assert result["valid"] is False
        assert 5 in result["invalid_citations"]

    def test_validate_citations_unused_sources(self, citation_service):
        """Test validating citations with unused sources"""
        response = "Statement [1]."
        sources = [
            {"id": 1, "title": "Source 1"},
            {"id": 2, "title": "Source 2"},  # Unused
        ]
        result = citation_service.validate_citations_in_response(response, sources)
        assert result["valid"] is True
        assert 2 in result["unused_sources"]

    def test_validate_citations_empty_sources(self, citation_service):
        """Test validating citations with empty sources"""
        response = "Statement with no citations."
        sources = []
        result = citation_service.validate_citations_in_response(response, sources)
        assert result["valid"] is True
        assert result["stats"]["citation_rate"] == 0

    def test_validate_citations_duplicates(self, citation_service):
        """Test validating citations with duplicate references"""
        response = "Statement [1] and again [1] and [1]."
        sources = [{"id": 1, "title": "Source 1"}]
        result = citation_service.validate_citations_in_response(response, sources)
        assert result["valid"] is True
        assert result["citations_found"] == [1]  # Deduplicated

    def test_append_sources_empty(self, citation_service):
        """Test appending sources with empty sources - covers line 283"""
        response = "Original response"
        result = citation_service.append_sources_to_response(response, [])
        assert result == response

    def test_append_sources_with_validation_filter(self, citation_service):
        """Test appending sources filtered by validation - covers line 287-288"""
        response = "Original response"
        sources = [
            {"id": 1, "title": "Source 1"},
            {"id": 2, "title": "Source 2"},  # Won't be cited
        ]
        validation_result = {"citations_found": [1]}  # Only source 1 cited
        result = citation_service.append_sources_to_response(response, sources, validation_result)
        assert "Source 1" in result
        assert "Source 2" not in result

    def test_append_sources_validation_empty_citations(self, citation_service):
        """Test appending sources with empty citations_found in validation"""
        response = "Original response"
        sources = [{"id": 1, "title": "Source 1"}]
        validation_result = {"citations_found": []}  # Empty
        result = citation_service.append_sources_to_response(response, sources, validation_result)
        # When citations_found is empty, should include all sources
        assert "Source 1" in result

    def test_process_response_with_citations_full(self, citation_service):
        """Test full citation processing workflow - covers line 319-331"""
        response = "Statement [1] with citation."
        rag_results = [{"metadata": {"title": "Doc 1", "url": "https://example.com"}, "score": 0.9}]
        result = citation_service.process_response_with_citations(response, rag_results)
        assert "response" in result
        assert "sources" in result
        assert "validation" in result
        assert "has_citations" in result
        assert result["has_citations"] is True

    def test_process_response_with_citations_no_rag(self, citation_service):
        """Test processing without RAG results - covers line 319-320"""
        response = "Statement without citations."
        result = citation_service.process_response_with_citations(response, None)
        assert result["sources"] == []
        assert result["has_citations"] is False

    def test_process_response_with_citations_empty_rag(self, citation_service):
        """Test processing with empty RAG results"""
        response = "Statement without citations."
        result = citation_service.process_response_with_citations(response, [])
        assert result["sources"] == []
        assert result["has_citations"] is False

    def test_process_response_auto_append_true(self, citation_service):
        """Test auto append sources - covers line 328-329"""
        response = "Statement [1]."
        rag_results = [{"metadata": {"title": "Doc 1"}, "score": 0.9}]
        result = citation_service.process_response_with_citations(
            response, rag_results, auto_append=True
        )
        assert "Sources:" in result["response"]

    def test_process_response_auto_append_false(self, citation_service):
        """Test auto append disabled"""
        response = "Statement [1]."
        rag_results = [{"metadata": {"title": "Doc 1"}, "score": 0.9}]
        result = citation_service.process_response_with_citations(
            response, rag_results, auto_append=False
        )
        assert result["response"] == response  # Unchanged

    def test_create_source_metadata_for_frontend(self, citation_service):
        """Test creating frontend metadata - covers line 359-373"""
        sources = [
            {
                "id": 1,
                "title": "Doc 1",
                "url": "https://example.com",
                "date": "2024-01-01",
                "type": "rag",
                "category": "immigration",
            },
            {
                "id": 2,
                "title": "Doc 2",
                # Missing fields - should use defaults
            },
        ]
        result = citation_service.create_source_metadata_for_frontend(sources)
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[0]["title"] == "Doc 1"
        assert result[0]["url"] == "https://example.com"
        assert result[0]["category"] == "immigration"
        # Default values for missing fields
        assert result[1]["url"] == ""
        assert result[1]["type"] == "rag"
        assert result[1]["category"] == "general"

    def test_create_source_metadata_empty(self, citation_service):
        """Test creating frontend metadata with empty sources"""
        result = citation_service.create_source_metadata_for_frontend([])
        assert result == []

    def test_create_source_metadata_unknown_source(self, citation_service):
        """Test creating frontend metadata with missing title"""
        sources = [{"id": 1}]  # No title
        result = citation_service.create_source_metadata_for_frontend(sources)
        assert result[0]["title"] == "Unknown Source"

    @pytest.mark.asyncio
    async def test_health_check(self, citation_service):
        """Test health check - covers line 385"""
        result = await citation_service.health_check()
        assert result["status"] == "healthy"
        assert result["features"]["inline_citations"] is True
        assert result["features"]["source_formatting"] is True
        assert result["features"]["citation_validation"] is True
        assert result["features"]["rag_integration"] is True
        assert result["features"]["frontend_metadata"] is True

    def test_extract_sources_source_url_fallback(self, citation_service):
        """Test extracting sources using source_url fallback"""
        results = [
            {
                "metadata": {
                    "title": "Doc 1",
                    "source_url": "https://alt.example.com",  # Fallback URL
                }
            }
        ]
        citations = citation_service.extract_sources_from_rag(results)
        assert citations[0]["url"] == "https://alt.example.com"

    def test_extract_sources_scraped_at_fallback(self, citation_service):
        """Test extracting sources using scraped_at fallback"""
        results = [
            {
                "metadata": {
                    "title": "Doc 1",
                    "scraped_at": "2024-06-15",  # Fallback date
                }
            }
        ]
        citations = citation_service.extract_sources_from_rag(results)
        assert citations[0]["date"] == "2024-06-15"

    def test_extract_sources_with_score(self, citation_service):
        """Test extracting sources with score"""
        results = [{"metadata": {"title": "Doc 1"}, "score": 0.85}]
        citations = citation_service.extract_sources_from_rag(results)
        assert citations[0]["score"] == 0.85

    def test_extract_sources_default_score(self, citation_service):
        """Test extracting sources with default score"""
        results = [{"metadata": {"title": "Doc 1"}}]
        citations = citation_service.extract_sources_from_rag(results)
        assert citations[0]["score"] == 0.0

    def test_extract_sources_default_category(self, citation_service):
        """Test extracting sources with default category"""
        results = [{"metadata": {"title": "Doc 1"}}]
        citations = citation_service.extract_sources_from_rag(results)
        assert citations[0]["category"] == "general"

    def test_extract_sources_with_category(self, citation_service):
        """Test extracting sources with explicit category"""
        results = [{"metadata": {"title": "Doc 1", "category": "tax"}}]
        citations = citation_service.extract_sources_from_rag(results)
        assert citations[0]["category"] == "tax"
