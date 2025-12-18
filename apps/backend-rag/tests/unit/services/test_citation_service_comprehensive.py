"""
Comprehensive tests for services/citation_service.py
Target: 95%+ coverage
"""

import pytest

from services.citation_service import CitationService


class TestCitationService:
    """Comprehensive test suite for CitationService"""

    @pytest.fixture
    def service(self):
        """Create CitationService instance"""
        return CitationService()

    def test_init(self, service):
        """Test CitationService initialization"""
        assert service.search_service is None

    def test_create_citation_instructions_with_sources(self, service):
        """Test create_citation_instructions with sources"""
        instructions = service.create_citation_instructions(sources_available=True)
        assert len(instructions) > 0
        assert "Citation" in instructions

    def test_create_citation_instructions_no_sources(self, service):
        """Test create_citation_instructions without sources"""
        instructions = service.create_citation_instructions(sources_available=False)
        assert instructions == ""

    def test_extract_sources_from_rag(self, service):
        """Test extract_sources_from_rag"""
        rag_results = [
            {
                "metadata": {"title": "Doc 1", "url": "https://example.com", "date": "2024-01-01"},
                "score": 0.9,
            },
            {
                "metadata": {"title": "Doc 2"},
                "score": 0.8,
            },
        ]
        sources = service.extract_sources_from_rag(rag_results)
        assert len(sources) == 2
        assert sources[0]["id"] == 1
        assert sources[0]["title"] == "Doc 1"

    def test_extract_sources_from_rag_empty(self, service):
        """Test extract_sources_from_rag with empty results"""
        sources = service.extract_sources_from_rag([])
        assert sources == []

    def test_format_sources_section(self, service):
        """Test format_sources_section"""
        sources = [
            {"id": 1, "title": "Doc 1", "url": "https://example.com", "date": "2024-01-01"},
            {"id": 2, "title": "Doc 2"},
        ]
        section = service.format_sources_section(sources)
        assert "Sources:" in section
        assert "[1]" in section
        assert "[2]" in section

    def test_format_sources_section_empty(self, service):
        """Test format_sources_section with empty sources"""
        section = service.format_sources_section([])
        assert section == ""

    def test_inject_citation_context_into_prompt(self, service):
        """Test inject_citation_context_into_prompt"""
        prompt = "Original prompt"
        sources = [
            {"id": 1, "title": "Doc 1", "category": "immigration"},
        ]
        enhanced = service.inject_citation_context_into_prompt(prompt, sources)
        assert "Original prompt" in enhanced
        assert "[1]" in enhanced

    def test_inject_citation_context_no_sources(self, service):
        """Test inject_citation_context_into_prompt with no sources"""
        prompt = "Original prompt"
        enhanced = service.inject_citation_context_into_prompt(prompt, [])
        assert enhanced == prompt

    def test_validate_citations_in_response_valid(self, service):
        """Test validate_citations_in_response with valid citations"""
        response = "This is a fact [1]. Another fact [2]."
        sources = [
            {"id": 1, "title": "Doc 1"},
            {"id": 2, "title": "Doc 2"},
        ]
        validation = service.validate_citations_in_response(response, sources)
        assert validation["valid"] is True
        assert len(validation["citations_found"]) == 2

    def test_validate_citations_in_response_invalid(self, service):
        """Test validate_citations_in_response with invalid citations"""
        response = "This is a fact [5]."
        sources = [
            {"id": 1, "title": "Doc 1"},
        ]
        validation = service.validate_citations_in_response(response, sources)
        assert validation["valid"] is False
        assert len(validation["invalid_citations"]) > 0

    def test_validate_citations_no_citations(self, service):
        """Test validate_citations_in_response with no citations"""
        response = "This is a fact without citations."
        sources = [
            {"id": 1, "title": "Doc 1"},
        ]
        validation = service.validate_citations_in_response(response, sources)
        assert len(validation["citations_found"]) == 0

    def test_append_sources_to_response(self, service):
        """Test append_sources_to_response"""
        response = "This is a fact [1]."
        sources = [
            {"id": 1, "title": "Doc 1", "url": "https://example.com"},
        ]
        enhanced = service.append_sources_to_response(response, sources)
        assert "Sources:" in enhanced
        assert "[1]" in enhanced

    def test_append_sources_with_validation(self, service):
        """Test append_sources_to_response with validation"""
        response = "This is a fact [1]."
        sources = [
            {"id": 1, "title": "Doc 1"},
            {"id": 2, "title": "Doc 2"},
        ]
        validation = {"citations_found": [1]}
        enhanced = service.append_sources_to_response(response, sources, validation)
        assert "[1]" in enhanced
        assert "[2]" not in enhanced  # Should only include cited sources

    def test_process_response_with_citations(self, service):
        """Test process_response_with_citations"""
        response = "This is a fact [1]."
        rag_results = [
            {"metadata": {"title": "Doc 1"}, "score": 0.9},
        ]
        result = service.process_response_with_citations(response, rag_results)
        assert "response" in result
        assert "sources" in result
        assert "validation" in result
        assert result["has_citations"] is True

    def test_process_response_no_rag_results(self, service):
        """Test process_response_with_citations without RAG results"""
        response = "This is a fact."
        result = service.process_response_with_citations(response, None)
        assert result["has_citations"] is False

    def test_create_source_metadata_for_frontend(self, service):
        """Test create_source_metadata_for_frontend"""
        sources = [
            {
                "id": 1,
                "title": "Doc 1",
                "url": "https://example.com",
                "date": "2024-01-01",
                "type": "rag",
                "category": "immigration",
            },
        ]
        frontend_sources = service.create_source_metadata_for_frontend(sources)
        assert len(frontend_sources) == 1
        assert frontend_sources[0]["id"] == 1
        assert frontend_sources[0]["title"] == "Doc 1"

    @pytest.mark.asyncio
    async def test_generate_citations(self, service):
        """Test generate_citations"""
        rag_results = [
            {"metadata": {"title": "Doc 1"}, "score": 0.9},
        ]
        citations = await service.generate_citations(rag_results)
        assert len(citations) == 1

    @pytest.mark.asyncio
    async def test_health_check(self, service):
        """Test health_check"""
        health = await service.health_check()
        assert health["status"] == "healthy"
        assert "features" in health
