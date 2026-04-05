"""
Tests for citation_service.py - Citation formatting and validation.
"""

import pytest

from backend.services.search.citation_service import CitationService


@pytest.fixture
def service():
    return CitationService()


@pytest.fixture
def sample_rag_results():
    return [
        {
            "score": 0.95,
            "metadata": {
                "title": "Immigration Regulations 2024",
                "url": "https://example.com/imm",
                "date": "2024-01-15",
                "category": "immigration",
            },
        },
        {
            "score": 0.85,
            "metadata": {
                "title": "Tax Guidelines",
                "url": "https://example.com/tax",
                "date": "2024-02-20",
                "category": "tax",
            },
        },
        {
            "score": 0.70,
            "metadata": {
                "title": "KBLI Reference",
                "category": "kbli",
            },
        },
    ]


class TestExtractSourcesFromRag:
    """Tests for extract_sources_from_rag method."""

    def test_extracts_correct_count(self, service, sample_rag_results):
        sources = service.extract_sources_from_rag(sample_rag_results)
        assert len(sources) == 3

    def test_sequential_ids(self, service, sample_rag_results):
        sources = service.extract_sources_from_rag(sample_rag_results)
        assert sources[0]["id"] == 1
        assert sources[1]["id"] == 2
        assert sources[2]["id"] == 3

    def test_metadata_extracted(self, service, sample_rag_results):
        sources = service.extract_sources_from_rag(sample_rag_results)
        assert sources[0]["title"] == "Immigration Regulations 2024"
        assert sources[0]["url"] == "https://example.com/imm"
        assert sources[0]["score"] == 0.95

    def test_missing_metadata_defaults(self, service):
        results = [{"score": 0.5, "metadata": {}}]
        sources = service.extract_sources_from_rag(results)
        assert sources[0]["title"] == "Document 1"
        assert sources[0]["url"] == ""

    def test_empty_results(self, service):
        sources = service.extract_sources_from_rag([])
        assert sources == []


class TestCreateCitationInstructions:
    """Tests for create_citation_instructions method."""

    def test_no_sources_returns_empty(self, service):
        result = service.create_citation_instructions(sources_available=False)
        assert result == ""

    def test_with_sources_returns_instructions(self, service):
        result = service.create_citation_instructions(sources_available=True)
        assert "Citation Guidelines" in result
        assert "[1]" in result
        assert "Sources:" in result


class TestFormatSourcesSection:
    """Tests for format_sources_section method."""

    def test_formats_sources(self, service, sample_rag_results):
        sources = service.extract_sources_from_rag(sample_rag_results)
        section = service.format_sources_section(sources)
        assert "Sources:" in section
        assert "[1] Immigration Regulations 2024" in section
        assert "https://example.com/imm" in section

    def test_empty_sources(self, service):
        section = service.format_sources_section([])
        assert section == ""

    def test_source_without_url(self, service):
        sources = [{"id": 1, "title": "Test", "date": "2024-01-01"}]
        section = service.format_sources_section(sources)
        assert "[1] Test" in section


class TestValidateCitationsInResponse:
    """Tests for validate_citations_in_response method."""

    def test_valid_citations(self, service, sample_rag_results):
        sources = service.extract_sources_from_rag(sample_rag_results)
        response = "According to [1], immigration requires KITAS. Also see [2] for tax info."
        result = service.validate_citations_in_response(response, sources)
        assert result["valid"] is True
        assert 1 in result["citations_found"]
        assert 2 in result["citations_found"]

    def test_invalid_citation_detected(self, service, sample_rag_results):
        sources = service.extract_sources_from_rag(sample_rag_results)
        response = "According to [1] and [99], these are the rules."
        result = service.validate_citations_in_response(response, sources)
        assert result["valid"] is False
        assert 99 in result["invalid_citations"]

    def test_unused_sources_detected(self, service, sample_rag_results):
        sources = service.extract_sources_from_rag(sample_rag_results)
        response = "According to [1], immigration is important."
        result = service.validate_citations_in_response(response, sources)
        assert 2 in result["unused_sources"]
        assert 3 in result["unused_sources"]

    def test_no_citations_in_response(self, service, sample_rag_results):
        sources = service.extract_sources_from_rag(sample_rag_results)
        response = "Immigration is important for business in Indonesia."
        result = service.validate_citations_in_response(response, sources)
        assert result["citations_found"] == []
        assert result["stats"]["total_citations"] == 0

    def test_duplicate_citations_deduplicated(self, service, sample_rag_results):
        sources = service.extract_sources_from_rag(sample_rag_results)
        response = "See [1] for info. Also [1] mentions this. And [1] again."
        result = service.validate_citations_in_response(response, sources)
        assert result["citations_found"].count(1) == 1


class TestProcessResponseWithCitations:
    """Tests for process_response_with_citations method."""

    def test_full_workflow(self, service, sample_rag_results):
        response = "Immigration requires KITAS [1] and tax compliance [2]."
        result = service.process_response_with_citations(
            response_text=response,
            rag_results=sample_rag_results,
            auto_append=True,
        )
        assert result["has_citations"] is True
        assert "Sources:" in result["response"]
        assert len(result["sources"]) == 3

    def test_no_rag_results(self, service):
        result = service.process_response_with_citations(
            response_text="Hello world",
            rag_results=None,
        )
        assert result["has_citations"] is False
        assert result["sources"] == []

    def test_auto_append_false(self, service, sample_rag_results):
        response = "See [1] for details."
        result = service.process_response_with_citations(
            response_text=response,
            rag_results=sample_rag_results,
            auto_append=False,
        )
        assert result["response"] == response  # Unchanged


class TestAppendSourcesToResponse:
    """Tests for append_sources_to_response method."""

    def test_appends_sources(self, service, sample_rag_results):
        sources = service.extract_sources_from_rag(sample_rag_results)
        result = service.append_sources_to_response("Answer text.", sources)
        assert "Answer text." in result
        assert "Sources:" in result

    def test_no_sources_returns_original(self, service):
        result = service.append_sources_to_response("Answer text.", [])
        assert result == "Answer text."

    def test_filters_by_validation_result(self, service, sample_rag_results):
        sources = service.extract_sources_from_rag(sample_rag_results)
        validation = {"citations_found": [1]}
        result = service.append_sources_to_response("Text [1].", sources, validation)
        assert "[1] Immigration" in result
        # Source 2 and 3 should not appear since they weren't cited
        assert "Tax Guidelines" not in result


class TestHealthCheck:
    """Tests for health_check method."""

    @pytest.mark.asyncio
    async def test_returns_healthy(self, service):
        result = await service.health_check()
        assert result["status"] == "healthy"
        assert result["features"]["inline_citations"] is True
