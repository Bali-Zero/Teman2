"""
Tests for CitationService - citation formatting, extraction, validation.
"""

from unittest.mock import MagicMock

import pytest

from backend.services.search.citation_service import CitationService


@pytest.fixture
def citation_service():
    return CitationService()


@pytest.fixture
def sample_rag_results():
    return [
        {
            "score": 0.85,
            "metadata": {
                "title": "Immigration Regulations 2024",
                "url": "https://example.com/immigration",
                "date": "2024-01-15T10:00:00",
                "category": "immigration",
            },
        },
        {
            "score": 0.72,
            "metadata": {
                "title": "BKPM Investment Guidelines",
                "source_url": "https://example.com/bkpm",
                "scraped_at": "2024-02-20",
                "category": "investment",
            },
        },
    ]


class TestEdgeCasesAndErrorHandling:
    """Test edge cases in citation service."""

    def test_format_sources_date_exception_handling(self, citation_service):
        """format_sources_section should handle short date strings that skip formatting."""
        # Short date strings (< 10 chars) skip the date[:10] slicing but still get appended
        sources = [
            {
                "id": 1,
                "title": "Test Doc",
                "url": "https://example.com",
                "date": "2024",  # Short date string - less than 10 chars
            },
        ]
        result = citation_service.format_sources_section(sources)
        assert "[1] Test Doc" in result
        assert "Sources:" in result
        assert "2024" in result

    def test_format_sources_empty(self, citation_service):
        """format_sources_section should return empty string for no sources."""
        result = citation_service.format_sources_section([])
        assert result == ""

    def test_format_sources_no_url_no_date(self, citation_service):
        """format_sources_section should handle missing url and date."""
        sources = [{"id": 1, "title": "Minimal Doc"}]
        result = citation_service.format_sources_section(sources)
        assert "[1] Minimal Doc" in result

    def test_extract_sources_from_rag(self, citation_service, sample_rag_results):
        """extract_sources_from_rag should extract source metadata correctly."""
        sources = citation_service.extract_sources_from_rag(sample_rag_results)
        assert len(sources) == 2
        assert sources[0]["id"] == 1
        assert sources[0]["title"] == "Immigration Regulations 2024"
        assert sources[0]["url"] == "https://example.com/immigration"
        assert sources[0]["score"] == 0.85
        assert sources[1]["url"] == "https://example.com/bkpm"

    def test_extract_sources_empty(self, citation_service):
        """extract_sources_from_rag should return empty list for no results."""
        sources = citation_service.extract_sources_from_rag([])
        assert sources == []

    def test_create_citation_instructions_no_sources(self, citation_service):
        """create_citation_instructions should return empty string when no sources."""
        result = citation_service.create_citation_instructions(sources_available=False)
        assert result == ""

    def test_create_citation_instructions_with_sources(self, citation_service):
        """create_citation_instructions should return instructions when sources available."""
        result = citation_service.create_citation_instructions(sources_available=True)
        assert "Citation Guidelines" in result
        assert "[1]" in result

    def test_validate_citations_valid(self, citation_service):
        """validate_citations_in_response should validate correct citations."""
        sources = [{"id": 1, "title": "Doc A"}, {"id": 2, "title": "Doc B"}]
        response = "This is from source [1] and also [2]."
        result = citation_service.validate_citations_in_response(response, sources)
        assert result["valid"] is True
        assert 1 in result["citations_found"]
        assert 2 in result["citations_found"]
        assert result["invalid_citations"] == []

    def test_validate_citations_invalid(self, citation_service):
        """validate_citations_in_response should detect invalid citations."""
        sources = [{"id": 1, "title": "Doc A"}]
        response = "This references [1] and [5]."
        result = citation_service.validate_citations_in_response(response, sources)
        assert result["valid"] is False
        assert 5 in result["invalid_citations"]

    def test_validate_citations_unused_sources(self, citation_service):
        """validate_citations_in_response should detect unused sources."""
        sources = [{"id": 1, "title": "Doc A"}, {"id": 2, "title": "Doc B"}]
        response = "Only uses [1]."
        result = citation_service.validate_citations_in_response(response, sources)
        assert 2 in result["unused_sources"]

    def test_inject_citation_context_no_sources(self, citation_service):
        """inject_citation_context_into_prompt should return original when no sources."""
        prompt = "You are a helpful assistant."
        result = citation_service.inject_citation_context_into_prompt(prompt, [])
        assert result == prompt

    def test_inject_citation_context_with_sources(self, citation_service):
        """inject_citation_context_into_prompt should enhance prompt with source context."""
        prompt = "You are a helpful assistant."
        sources = [{"id": 1, "title": "Doc A", "category": "visa"}]
        result = citation_service.inject_citation_context_into_prompt(prompt, sources)
        assert "Available Sources" in result
        assert "[1] Doc A" in result
        assert "visa" in result

    def test_append_sources_to_response(self, citation_service):
        """append_sources_to_response should append sources section."""
        response = "This is the answer."
        sources = [{"id": 1, "title": "Doc A", "url": "https://example.com"}]
        result = citation_service.append_sources_to_response(response, sources)
        assert "Sources:" in result
        assert "Doc A" in result

    def test_append_sources_empty(self, citation_service):
        """append_sources_to_response should return original when no sources."""
        response = "This is the answer."
        result = citation_service.append_sources_to_response(response, [])
        assert result == response

    @pytest.mark.asyncio
    async def test_generate_citations(self, citation_service, sample_rag_results):
        """generate_citations should wrap extract_sources_from_rag."""
        citations = await citation_service.generate_citations(sample_rag_results)
        assert len(citations) == 2
        assert citations[0]["title"] == "Immigration Regulations 2024"
