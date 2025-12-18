"""
Comprehensive tests for CitationService - 100% coverage target
Tests citation formatting and source references for AI responses
"""

from unittest.mock import MagicMock

import pytest

from services.citation_service import CitationService


class TestCitationServiceInit:
    """Tests for CitationService initialization"""

    def test_init_default(self):
        """Test default initialization"""
        service = CitationService()
        assert service.search_service is None

    def test_init_with_search_service(self):
        """Test initialization with search service"""
        mock_search = MagicMock()
        service = CitationService(search_service=mock_search)
        assert service.search_service == mock_search


class TestGenerateCitations:
    """Tests for generate_citations method"""

    @pytest.fixture
    def service(self):
        return CitationService()

    @pytest.mark.asyncio
    async def test_generate_citations(self, service):
        """Test generating citations from search results"""
        search_results = [
            {"metadata": {"title": "Test Doc", "url": "http://test.com"}, "score": 0.9}
        ]

        result = await service.generate_citations(search_results)

        assert len(result) == 1
        assert result[0]["title"] == "Test Doc"
        assert result[0]["url"] == "http://test.com"


class TestCreateCitationInstructions:
    """Tests for create_citation_instructions method"""

    @pytest.fixture
    def service(self):
        return CitationService()

    def test_instructions_with_sources(self, service):
        """Test instructions when sources available"""
        result = service.create_citation_instructions(sources_available=True)

        assert "Citation Guidelines" in result
        assert "[1]" in result
        assert "[2]" in result

    def test_instructions_without_sources(self, service):
        """Test instructions when no sources"""
        result = service.create_citation_instructions(sources_available=False)

        assert result == ""


class TestExtractSourcesFromRAG:
    """Tests for extract_sources_from_rag method"""

    @pytest.fixture
    def service(self):
        return CitationService()

    def test_extract_sources_complete_metadata(self, service):
        """Test extracting sources with complete metadata"""
        rag_results = [
            {
                "metadata": {
                    "title": "Immigration Guide",
                    "url": "http://immigration.gov",
                    "date": "2024-01-15",
                    "category": "immigration",
                },
                "score": 0.95,
            },
            {
                "metadata": {
                    "title": "Tax Guide",
                    "source_url": "http://tax.gov",
                    "scraped_at": "2024-02-01",
                    "category": "tax",
                },
                "score": 0.85,
            },
        ]

        sources = service.extract_sources_from_rag(rag_results)

        assert len(sources) == 2
        assert sources[0]["id"] == 1
        assert sources[0]["title"] == "Immigration Guide"
        assert sources[0]["url"] == "http://immigration.gov"
        assert sources[0]["type"] == "rag"
        assert sources[1]["id"] == 2
        assert sources[1]["url"] == "http://tax.gov"

    def test_extract_sources_minimal_metadata(self, service):
        """Test extracting sources with minimal metadata"""
        rag_results = [{"metadata": {}, "score": 0.7}, {"metadata": None, "score": 0.6}]

        # Handle None metadata
        rag_results[1]["metadata"] = {}
        sources = service.extract_sources_from_rag(rag_results)

        assert len(sources) == 2
        assert sources[0]["title"] == "Document 1"
        assert sources[0]["url"] == ""

    def test_extract_sources_empty(self, service):
        """Test extracting from empty results"""
        sources = service.extract_sources_from_rag([])

        assert sources == []


class TestFormatSourcesSection:
    """Tests for format_sources_section method"""

    @pytest.fixture
    def service(self):
        return CitationService()

    def test_format_complete_sources(self, service):
        """Test formatting sources with all info"""
        sources = [
            {"id": 1, "title": "Immigration Guide", "url": "http://test.com", "date": "2024-01-15"},
            {"id": 2, "title": "Tax Guide", "url": "http://tax.com", "date": "2024-02-01"},
        ]

        result = service.format_sources_section(sources)

        assert "**Sources:**" in result
        assert "[1] Immigration Guide" in result
        assert "[2] Tax Guide" in result
        assert "http://test.com" in result
        assert "2024-01-15" in result

    def test_format_sources_minimal_info(self, service):
        """Test formatting sources with minimal info"""
        sources = [{"id": 1, "title": "Document 1"}, {"id": 2, "title": "Document 2", "url": ""}]

        result = service.format_sources_section(sources)

        assert "[1] Document 1" in result
        assert "[2] Document 2" in result

    def test_format_sources_empty(self, service):
        """Test formatting empty sources"""
        result = service.format_sources_section([])

        assert result == ""

    def test_format_sources_long_date(self, service):
        """Test formatting with ISO date string"""
        sources = [{"id": 1, "title": "Doc", "url": "", "date": "2024-01-15T10:30:00Z"}]

        result = service.format_sources_section(sources)

        assert "2024-01-15" in result


class TestInjectCitationContextIntoPrompt:
    """Tests for inject_citation_context_into_prompt method"""

    @pytest.fixture
    def service(self):
        return CitationService()

    def test_inject_with_sources(self, service):
        """Test injecting citation context"""
        system_prompt = "You are a helpful assistant."
        sources = [
            {"id": 1, "title": "Guide 1", "category": "immigration"},
            {"id": 2, "title": "Guide 2", "category": "tax"},
        ]

        result = service.inject_citation_context_into_prompt(system_prompt, sources)

        assert "You are a helpful assistant." in result
        assert "Citation Guidelines" in result
        assert "Available Sources" in result
        assert "[1] Guide 1" in result
        assert "(Category: immigration)" in result

    def test_inject_without_category(self, service):
        """Test injecting without category"""
        system_prompt = "Base prompt"
        sources = [{"id": 1, "title": "Doc"}]

        result = service.inject_citation_context_into_prompt(system_prompt, sources)

        assert "[1] Doc" in result

    def test_inject_empty_sources(self, service):
        """Test injecting with no sources"""
        system_prompt = "Base prompt"

        result = service.inject_citation_context_into_prompt(system_prompt, [])

        assert result == system_prompt


class TestValidateCitationsInResponse:
    """Tests for validate_citations_in_response method"""

    @pytest.fixture
    def service(self):
        return CitationService()

    def test_validate_valid_citations(self, service):
        """Test validating correct citations"""
        response = "Indonesia requires KITAS [1]. The tax rate is 10% [2]."
        sources = [{"id": 1}, {"id": 2}]

        result = service.validate_citations_in_response(response, sources)

        assert result["valid"] is True
        assert result["citations_found"] == [1, 2]
        assert result["invalid_citations"] == []
        assert result["unused_sources"] == []

    def test_validate_invalid_citations(self, service):
        """Test validating with invalid citations"""
        response = "Statement [1]. Another [5]."
        sources = [{"id": 1}, {"id": 2}]

        result = service.validate_citations_in_response(response, sources)

        assert result["valid"] is False
        assert 5 in result["invalid_citations"]

    def test_validate_unused_sources(self, service):
        """Test validating with unused sources"""
        response = "Statement [1]."
        sources = [{"id": 1}, {"id": 2}, {"id": 3}]

        result = service.validate_citations_in_response(response, sources)

        assert result["valid"] is True
        assert 2 in result["unused_sources"]
        assert 3 in result["unused_sources"]

    def test_validate_duplicate_citations(self, service):
        """Test validating with duplicate citations"""
        response = "Statement [1]. More [1]. And [2]. Again [1]."
        sources = [{"id": 1}, {"id": 2}]

        result = service.validate_citations_in_response(response, sources)

        assert result["citations_found"] == [1, 2]

    def test_validate_no_citations(self, service):
        """Test validating response without citations"""
        response = "A response without any citations."
        sources = [{"id": 1}]

        result = service.validate_citations_in_response(response, sources)

        assert result["citations_found"] == []
        assert result["stats"]["citation_rate"] == 0

    def test_validate_empty_sources(self, service):
        """Test validating with no sources"""
        response = "Response [1]."
        sources = []

        result = service.validate_citations_in_response(response, sources)

        assert result["invalid_citations"] == [1]
        assert result["stats"]["citation_rate"] == 0


class TestAppendSourcesToResponse:
    """Tests for append_sources_to_response method"""

    @pytest.fixture
    def service(self):
        return CitationService()

    def test_append_sources(self, service):
        """Test appending sources to response"""
        response = "Here is the information [1] [2]."
        sources = [
            {"id": 1, "title": "Source 1", "url": "http://s1.com"},
            {"id": 2, "title": "Source 2", "url": "http://s2.com"},
        ]

        result = service.append_sources_to_response(response, sources)

        assert "**Sources:**" in result
        assert "[1] Source 1" in result
        assert "[2] Source 2" in result

    def test_append_with_validation_filter(self, service):
        """Test appending with validation result filtering"""
        response = "Info [1]."
        sources = [{"id": 1, "title": "Used Source"}, {"id": 2, "title": "Unused Source"}]
        validation = {"citations_found": [1]}

        result = service.append_sources_to_response(response, sources, validation)

        assert "[1] Used Source" in result
        assert "Unused Source" not in result

    def test_append_empty_sources(self, service):
        """Test appending with no sources"""
        response = "Response text."

        result = service.append_sources_to_response(response, [])

        assert result == response


class TestProcessResponseWithCitations:
    """Tests for process_response_with_citations method"""

    @pytest.fixture
    def service(self):
        return CitationService()

    def test_process_with_rag_results(self, service):
        """Test complete processing with RAG results"""
        response = "Information from source [1]."
        rag_results = [{"metadata": {"title": "Doc 1", "url": "http://test.com"}, "score": 0.9}]

        result = service.process_response_with_citations(response, rag_results)

        assert "has_citations" in result
        assert result["has_citations"] is True
        assert len(result["sources"]) == 1
        assert "**Sources:**" in result["response"]

    def test_process_without_citations(self, service):
        """Test processing response without citations"""
        response = "Response without any citations."
        rag_results = [{"metadata": {"title": "Doc"}, "score": 0.8}]

        result = service.process_response_with_citations(response, rag_results)

        assert result["has_citations"] is False
        assert result["response"] == response  # No sources appended

    def test_process_no_auto_append(self, service):
        """Test processing without auto append"""
        response = "Info [1]."
        rag_results = [{"metadata": {"title": "Doc"}, "score": 0.8}]

        result = service.process_response_with_citations(response, rag_results, auto_append=False)

        assert "**Sources:**" not in result["response"]

    def test_process_no_rag_results(self, service):
        """Test processing without RAG results"""
        response = "Response text."

        result = service.process_response_with_citations(response, None)

        assert result["sources"] == []
        assert result["has_citations"] is False


class TestCreateSourceMetadataForFrontend:
    """Tests for create_source_metadata_for_frontend method"""

    @pytest.fixture
    def service(self):
        return CitationService()

    def test_create_frontend_metadata(self, service):
        """Test creating frontend metadata"""
        sources = [
            {
                "id": 1,
                "title": "Doc",
                "url": "http://test.com",
                "date": "2024-01-01",
                "type": "rag",
                "category": "tax",
            },
            {"id": 2},  # Minimal source
        ]

        result = service.create_source_metadata_for_frontend(sources)

        assert len(result) == 2
        assert result[0]["title"] == "Doc"
        assert result[0]["category"] == "tax"
        assert result[1]["title"] == "Unknown Source"
        assert result[1]["type"] == "rag"


class TestHealthCheck:
    """Tests for health_check method"""

    @pytest.fixture
    def service(self):
        return CitationService()

    @pytest.mark.asyncio
    async def test_health_check(self, service):
        """Test health check returns healthy"""
        result = await service.health_check()

        assert result["status"] == "healthy"
        assert result["features"]["inline_citations"] is True
        assert result["features"]["citation_validation"] is True
