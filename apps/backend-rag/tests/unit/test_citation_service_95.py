"""
Unit Tests for services/citation_service.py - 95% Coverage Target
Tests the CitationService class
"""

import os
import sys
from pathlib import Path

import pytest

# Set required environment variables BEFORE any imports
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_for_testing_only_min_32_chars"
os.environ["API_KEYS"] = "test_api_key_1,test_api_key_2"
os.environ["OPENAI_API_KEY"] = "test_openai_api_key_for_testing"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"

# Add backend directory to Python path
backend_path = Path(__file__).parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))


# ============================================================================
# Test CitationService initialization
# ============================================================================


class TestCitationServiceInit:
    """Test suite for CitationService initialization"""

    def test_init_without_search_service(self):
        """Test initialization without search service"""
        from services.citation_service import CitationService

        service = CitationService()

        assert service.search_service is None

    def test_init_with_search_service(self):
        """Test initialization with search service"""
        from unittest.mock import MagicMock

        from services.citation_service import CitationService

        mock_search = MagicMock()
        service = CitationService(search_service=mock_search)

        assert service.search_service == mock_search


# ============================================================================
# Test generate_citations
# ============================================================================


class TestGenerateCitations:
    """Test suite for generate_citations method"""

    @pytest.mark.asyncio
    async def test_generate_citations_empty_results(self):
        """Test generating citations from empty results"""
        from services.citation_service import CitationService

        service = CitationService()
        result = await service.generate_citations([])

        assert result == []

    @pytest.mark.asyncio
    async def test_generate_citations_with_results(self):
        """Test generating citations from results"""
        from services.citation_service import CitationService

        service = CitationService()
        results = [
            {"metadata": {"title": "Test Doc"}, "score": 0.8},
            {"metadata": {"title": "Another Doc"}, "score": 0.7},
        ]

        citations = await service.generate_citations(results)

        assert len(citations) == 2
        assert citations[0]["id"] == 1
        assert citations[0]["title"] == "Test Doc"


# ============================================================================
# Test create_citation_instructions
# ============================================================================


class TestCreateCitationInstructions:
    """Test suite for create_citation_instructions method"""

    def test_no_sources_returns_empty(self):
        """Test no sources returns empty string"""
        from services.citation_service import CitationService

        service = CitationService()
        result = service.create_citation_instructions(sources_available=False)

        assert result == ""

    def test_with_sources_returns_instructions(self):
        """Test with sources returns instructions"""
        from services.citation_service import CitationService

        service = CitationService()
        result = service.create_citation_instructions(sources_available=True)

        assert "Citation Guidelines" in result
        assert "[1]" in result
        assert "Sources:" in result


# ============================================================================
# Test extract_sources_from_rag
# ============================================================================


class TestExtractSourcesFromRag:
    """Test suite for extract_sources_from_rag method"""

    def test_extract_empty_list(self):
        """Test extracting from empty list"""
        from services.citation_service import CitationService

        service = CitationService()
        result = service.extract_sources_from_rag([])

        assert result == []

    def test_extract_single_document(self):
        """Test extracting from single document"""
        from services.citation_service import CitationService

        service = CitationService()
        docs = [
            {
                "metadata": {
                    "title": "Immigration Rules",
                    "url": "https://example.com/rules",
                    "date": "2024-01-15",
                    "category": "immigration",
                },
                "score": 0.85,
            }
        ]

        result = service.extract_sources_from_rag(docs)

        assert len(result) == 1
        assert result[0]["id"] == 1
        assert result[0]["title"] == "Immigration Rules"
        assert result[0]["url"] == "https://example.com/rules"
        assert result[0]["date"] == "2024-01-15"
        assert result[0]["type"] == "rag"
        assert result[0]["score"] == 0.85
        assert result[0]["category"] == "immigration"

    def test_extract_multiple_documents(self):
        """Test extracting from multiple documents"""
        from services.citation_service import CitationService

        service = CitationService()
        docs = [
            {"metadata": {"title": "Doc 1"}, "score": 0.9},
            {"metadata": {"title": "Doc 2"}, "score": 0.8},
            {"metadata": {"title": "Doc 3"}, "score": 0.7},
        ]

        result = service.extract_sources_from_rag(docs)

        assert len(result) == 3
        assert result[0]["id"] == 1
        assert result[1]["id"] == 2
        assert result[2]["id"] == 3

    def test_extract_missing_metadata(self):
        """Test extracting with missing metadata"""
        from services.citation_service import CitationService

        service = CitationService()
        docs = [{"score": 0.75}]

        result = service.extract_sources_from_rag(docs)

        assert len(result) == 1
        assert result[0]["title"] == "Document 1"
        assert result[0]["url"] == ""
        assert result[0]["date"] == ""
        assert result[0]["category"] == "general"

    def test_extract_source_url_fallback(self):
        """Test source_url fallback for url"""
        from services.citation_service import CitationService

        service = CitationService()
        docs = [{"metadata": {"source_url": "https://fallback.com"}}]

        result = service.extract_sources_from_rag(docs)

        assert result[0]["url"] == "https://fallback.com"

    def test_extract_scraped_at_fallback(self):
        """Test scraped_at fallback for date"""
        from services.citation_service import CitationService

        service = CitationService()
        docs = [{"metadata": {"scraped_at": "2024-03-15"}}]

        result = service.extract_sources_from_rag(docs)

        assert result[0]["date"] == "2024-03-15"


# ============================================================================
# Test format_sources_section
# ============================================================================


class TestFormatSourcesSection:
    """Test suite for format_sources_section method"""

    def test_format_empty_sources(self):
        """Test formatting empty sources"""
        from services.citation_service import CitationService

        service = CitationService()
        result = service.format_sources_section([])

        assert result == ""

    def test_format_single_source(self):
        """Test formatting single source"""
        from services.citation_service import CitationService

        service = CitationService()
        sources = [{"id": 1, "title": "Test Source", "url": "", "date": ""}]

        result = service.format_sources_section(sources)

        assert "Sources:" in result
        assert "[1] Test Source" in result

    def test_format_source_with_url(self):
        """Test formatting source with URL"""
        from services.citation_service import CitationService

        service = CitationService()
        sources = [{"id": 1, "title": "Test Source", "url": "https://example.com", "date": ""}]

        result = service.format_sources_section(sources)

        assert "https://example.com" in result

    def test_format_source_with_date(self):
        """Test formatting source with date"""
        from services.citation_service import CitationService

        service = CitationService()
        sources = [{"id": 1, "title": "Test Source", "url": "", "date": "2024-01-15T10:30:00"}]

        result = service.format_sources_section(sources)

        assert "2024-01-15" in result

    def test_format_source_with_all_fields(self):
        """Test formatting source with all fields"""
        from services.citation_service import CitationService

        service = CitationService()
        sources = [
            {
                "id": 1,
                "title": "Immigration Guide",
                "url": "https://gov.id/guide",
                "date": "2024-02-20",
            }
        ]

        result = service.format_sources_section(sources)

        assert "[1] Immigration Guide" in result
        assert "https://gov.id/guide" in result
        assert "2024-02-20" in result

    def test_format_multiple_sources(self):
        """Test formatting multiple sources"""
        from services.citation_service import CitationService

        service = CitationService()
        sources = [
            {"id": 1, "title": "Source A", "url": "", "date": ""},
            {"id": 2, "title": "Source B", "url": "", "date": ""},
        ]

        result = service.format_sources_section(sources)

        assert "[1] Source A" in result
        assert "[2] Source B" in result


# ============================================================================
# Test inject_citation_context_into_prompt
# ============================================================================


class TestInjectCitationContextIntoPrompt:
    """Test suite for inject_citation_context_into_prompt method"""

    def test_inject_no_sources(self):
        """Test injecting with no sources"""
        from services.citation_service import CitationService

        service = CitationService()
        original = "You are a helpful assistant."

        result = service.inject_citation_context_into_prompt(original, [])

        assert result == original

    def test_inject_with_sources(self):
        """Test injecting with sources"""
        from services.citation_service import CitationService

        service = CitationService()
        original = "You are a helpful assistant."
        sources = [{"id": 1, "title": "Test Doc", "category": "immigration"}]

        result = service.inject_citation_context_into_prompt(original, sources)

        assert original in result
        assert "Citation Guidelines" in result
        assert "Available Sources" in result
        assert "[1] Test Doc" in result
        assert "immigration" in result

    def test_inject_multiple_sources(self):
        """Test injecting with multiple sources"""
        from services.citation_service import CitationService

        service = CitationService()
        original = "Base prompt"
        sources = [
            {"id": 1, "title": "Doc 1", "category": "tax"},
            {"id": 2, "title": "Doc 2", "category": None},
        ]

        result = service.inject_citation_context_into_prompt(original, sources)

        assert "[1] Doc 1" in result
        assert "[2] Doc 2" in result
        assert "tax" in result


# ============================================================================
# Test validate_citations_in_response
# ============================================================================


class TestValidateCitationsInResponse:
    """Test suite for validate_citations_in_response method"""

    def test_validate_no_citations(self):
        """Test validating response with no citations"""
        from services.citation_service import CitationService

        service = CitationService()
        sources = [{"id": 1}, {"id": 2}]

        result = service.validate_citations_in_response("This has no citations", sources)

        assert result["valid"] is True
        assert result["citations_found"] == []
        assert result["invalid_citations"] == []
        assert result["unused_sources"] == [1, 2]

    def test_validate_valid_citations(self):
        """Test validating valid citations"""
        from services.citation_service import CitationService

        service = CitationService()
        sources = [{"id": 1}, {"id": 2}]
        response = "According to [1] and [2], this is true."

        result = service.validate_citations_in_response(response, sources)

        assert result["valid"] is True
        assert sorted(result["citations_found"]) == [1, 2]
        assert result["invalid_citations"] == []
        assert result["unused_sources"] == []

    def test_validate_invalid_citations(self):
        """Test validating invalid citations"""
        from services.citation_service import CitationService

        service = CitationService()
        sources = [{"id": 1}]
        response = "According to [1] and [3], this is true."

        result = service.validate_citations_in_response(response, sources)

        assert result["valid"] is False
        assert 3 in result["invalid_citations"]

    def test_validate_duplicate_citations(self):
        """Test validating duplicate citations"""
        from services.citation_service import CitationService

        service = CitationService()
        sources = [{"id": 1}]
        response = "See [1] for details [1] and again [1]."

        result = service.validate_citations_in_response(response, sources)

        assert result["citations_found"] == [1]

    def test_validate_empty_sources(self):
        """Test validating with empty sources"""
        from services.citation_service import CitationService

        service = CitationService()

        result = service.validate_citations_in_response("Test response", [])

        assert result["stats"]["citation_rate"] == 0


# ============================================================================
# Test append_sources_to_response
# ============================================================================


class TestAppendSourcesToResponse:
    """Test suite for append_sources_to_response method"""

    def test_append_no_sources(self):
        """Test appending with no sources"""
        from services.citation_service import CitationService

        service = CitationService()
        original = "This is the response."

        result = service.append_sources_to_response(original, [])

        assert result == original

    def test_append_with_sources(self):
        """Test appending with sources"""
        from services.citation_service import CitationService

        service = CitationService()
        original = "This is the response."
        sources = [{"id": 1, "title": "Source Doc", "url": "", "date": ""}]

        result = service.append_sources_to_response(original, sources)

        assert original in result
        assert "Sources:" in result
        assert "[1] Source Doc" in result

    def test_append_filter_by_validation(self):
        """Test appending filters by validation result"""
        from services.citation_service import CitationService

        service = CitationService()
        original = "Response [1]"
        sources = [
            {"id": 1, "title": "Used", "url": "", "date": ""},
            {"id": 2, "title": "Unused", "url": "", "date": ""},
        ]
        validation = {"citations_found": [1]}

        result = service.append_sources_to_response(original, sources, validation)

        assert "[1] Used" in result
        assert "[2] Unused" not in result


# ============================================================================
# Test process_response_with_citations
# ============================================================================


class TestProcessResponseWithCitations:
    """Test suite for process_response_with_citations method"""

    def test_process_no_rag_results(self):
        """Test processing without RAG results"""
        from services.citation_service import CitationService

        service = CitationService()

        result = service.process_response_with_citations("Response text")

        assert result["response"] == "Response text"
        assert result["sources"] == []
        assert result["has_citations"] is False

    def test_process_with_rag_results_no_citations(self):
        """Test processing with RAG results but no citations in response"""
        from services.citation_service import CitationService

        service = CitationService()
        rag_results = [{"metadata": {"title": "Doc"}, "score": 0.8}]

        result = service.process_response_with_citations(
            "Response without citations", rag_results=rag_results
        )

        assert len(result["sources"]) == 1
        assert result["has_citations"] is False
        assert result["response"] == "Response without citations"

    def test_process_with_citations_auto_append(self):
        """Test processing with citations and auto append"""
        from services.citation_service import CitationService

        service = CitationService()
        rag_results = [{"metadata": {"title": "Immigration Doc"}, "score": 0.9}]

        result = service.process_response_with_citations(
            "According to [1], KITAS is required.", rag_results=rag_results
        )

        assert result["has_citations"] is True
        assert "Sources:" in result["response"]
        assert "[1] Immigration Doc" in result["response"]

    def test_process_with_auto_append_disabled(self):
        """Test processing with auto append disabled"""
        from services.citation_service import CitationService

        service = CitationService()
        rag_results = [{"metadata": {"title": "Doc"}, "score": 0.8}]

        result = service.process_response_with_citations(
            "According to [1].", rag_results=rag_results, auto_append=False
        )

        assert result["has_citations"] is True
        assert "Sources:" not in result["response"]


# ============================================================================
# Test create_source_metadata_for_frontend
# ============================================================================


class TestCreateSourceMetadataForFrontend:
    """Test suite for create_source_metadata_for_frontend method"""

    def test_create_empty_sources(self):
        """Test creating metadata from empty sources"""
        from services.citation_service import CitationService

        service = CitationService()
        result = service.create_source_metadata_for_frontend([])

        assert result == []

    def test_create_single_source(self):
        """Test creating metadata from single source"""
        from services.citation_service import CitationService

        service = CitationService()
        sources = [
            {
                "id": 1,
                "title": "Test Doc",
                "url": "https://example.com",
                "date": "2024-01-15",
                "type": "rag",
                "category": "immigration",
            }
        ]

        result = service.create_source_metadata_for_frontend(sources)

        assert len(result) == 1
        assert result[0]["id"] == 1
        assert result[0]["title"] == "Test Doc"
        assert result[0]["url"] == "https://example.com"
        assert result[0]["type"] == "rag"
        assert result[0]["category"] == "immigration"

    def test_create_with_missing_fields(self):
        """Test creating metadata with missing fields"""
        from services.citation_service import CitationService

        service = CitationService()
        sources = [{"id": 1}]

        result = service.create_source_metadata_for_frontend(sources)

        assert result[0]["title"] == "Unknown Source"
        assert result[0]["url"] == ""
        assert result[0]["type"] == "rag"
        assert result[0]["category"] == "general"


# ============================================================================
# Test health_check
# ============================================================================


class TestHealthCheck:
    """Test suite for health_check method"""

    @pytest.mark.asyncio
    async def test_health_check_returns_healthy(self):
        """Test health check returns healthy status"""
        from services.citation_service import CitationService

        service = CitationService()
        result = await service.health_check()

        assert result["status"] == "healthy"
        assert result["features"]["inline_citations"] is True
        assert result["features"]["source_formatting"] is True
        assert result["features"]["citation_validation"] is True
        assert result["features"]["rag_integration"] is True
        assert result["features"]["frontend_metadata"] is True
