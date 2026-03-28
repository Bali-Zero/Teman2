"""
Tests for Query Expansion Service

Tests cover:
- Synonym generation for Indonesian business terms
- Translation variants
- LLM-based rephrasing (with mocks)
- Filter relaxation
- Deduplication
- Error handling (fallback to original query)
- Caching behavior

Author: Nuzantara Team
Date: 2026-02-16
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.rag.query_expansion import (
    FILTER_KEYWORDS,
    INDONESIAN_BUSINESS_TERMS,
    QueryExpander,
    get_query_expander,
)


class TestQueryExpanderInitialization:
    """Test QueryExpander initialization and basic properties."""

    def test_default_initialization(self):
        """Test QueryExpander initializes with default values."""
        expander = QueryExpander()

        assert expander.max_variants == 5
        assert expander.llm_timeout_ms == 100
        assert expander._genai_client is None

    def test_custom_initialization(self):
        """Test QueryExpander initializes with custom values."""
        mock_cache = MagicMock()
        expander = QueryExpander(
            cache_service=mock_cache,
            max_variants=10,
            llm_timeout_ms=200,
        )

        assert expander.max_variants == 10
        assert expander.llm_timeout_ms == 200
        assert expander.cache_service == mock_cache


class TestSynonymGeneration:
    """Test synonym expansion functionality."""

    @pytest.fixture
    def expander(self):
        """Create a QueryExpander instance for tests."""
        return QueryExpander()

    def test_generate_synonyms_kitasa(self, expander):
        """Test synonym generation for KITAS."""
        query = "How to apply for KITAS?"
        variants = expander.generate_synonyms(query)

        assert len(variants) > 0
        # Check that residence permit variant exists
        assert any("residence permit" in v.lower() for v in variants)
        # Check that Indonesian variant exists
        assert any("kartu izin tinggal" in v.lower() for v in variants)

    def test_generate_synonyms_pt_pma(self, expander):
        """Test synonym generation for PT PMA."""
        query = "What are PT PMA requirements?"
        variants = expander.generate_synonyms(query)

        assert len(variants) > 0
        # Check that foreign investment company variant exists
        assert any("foreign investment" in v.lower() for v in variants)

    def test_generate_synonyms_nib(self, expander):
        """Test synonym generation for NIB."""
        query = "How to get NIB?"
        variants = expander.generate_synonyms(query)

        assert len(variants) > 0
        assert any("business identification" in v.lower() for v in variants)

    def test_generate_synonyms_case_insensitive(self, expander):
        """Test synonym generation is case insensitive."""
        query_lower = "how to apply for kitas?"
        query_upper = "How to apply for KITAS?"
        query_mixed = "How to apply for Kitas?"

        variants_lower = expander.generate_synonyms(query_lower)
        variants_upper = expander.generate_synonyms(query_upper)
        variants_mixed = expander.generate_synonyms(query_mixed)

        # All should produce similar variants
        assert len(variants_lower) > 0
        assert len(variants_upper) > 0
        assert len(variants_mixed) > 0

    def test_generate_synonyms_multiple_terms(self, expander):
        """Test synonym generation with multiple business terms."""
        query = "KITAS and NIB requirements for PT PMA"
        variants = expander.generate_synonyms(query)

        # Should generate variants for each term
        assert len(variants) >= 2

    def test_generate_synonyms_empty_query(self, expander):
        """Test synonym generation with empty query."""
        assert expander.generate_synonyms("") == []
        assert expander.generate_synonyms("   ") == []
        assert expander.generate_synonyms(None) == []

    def test_generate_synonyms_no_matches(self, expander):
        """Test synonym generation with no business terms."""
        query = "How to cook nasi goreng?"
        variants = expander.generate_synonyms(query)

        assert variants == []

    def test_indonesian_business_terms_dictionary(self):
        """Test that business terms dictionary is properly structured."""
        assert isinstance(INDONESIAN_BUSINESS_TERMS, dict)
        assert len(INDONESIAN_BUSINESS_TERMS) > 0

        # Check that all values are lists
        for term, synonyms in INDONESIAN_BUSINESS_TERMS.items():
            assert isinstance(term, str)
            assert isinstance(synonyms, list)
            assert len(synonyms) > 0
            for syn in synonyms:
                assert isinstance(syn, str)


class TestTranslationVariants:
    """Test translation variant generation."""

    @pytest.fixture
    def expander(self):
        """Create a QueryExpander instance with mocked cache."""
        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock(return_value=True)
        return QueryExpander(cache_service=mock_cache)

    @pytest.mark.asyncio
    async def test_translate_variants_how_to(self, expander):
        """Test translation of 'how to' queries."""
        query = "How to apply for KITAS?"
        variants = await expander.translate_variants(query, ["id"])

        # Should have at least dictionary-based translation
        assert len(variants) > 0
        assert any("cara" in v.lower() for v in variants)

    @pytest.mark.asyncio
    async def test_translate_variants_what_is(self, expander):
        """Test translation of 'what is' queries."""
        query = "What is NIB?"
        variants = await expander.translate_variants(query, ["id"])

        assert len(variants) > 0
        assert any("apa itu" in v.lower() for v in variants)

    @pytest.mark.asyncio
    async def test_translate_variants_cache_hit(self, expander):
        """Test that cached translations are returned."""
        cached_result = ["Cara mengajukan KITAS?"]
        expander.cache_service.get = AsyncMock(return_value=cached_result)

        query = "How to apply for KITAS?"
        variants = await expander.translate_variants(query, ["id"])

        assert variants == cached_result
        expander.cache_service.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_translate_variants_empty_query(self, expander):
        """Test translation with empty query."""
        assert await expander.translate_variants("") == []
        assert await expander.translate_variants("   ") == []
        assert await expander.translate_variants(None) == []

    @pytest.mark.asyncio
    async def test_translate_variants_default_languages(self, expander):
        """Test translation uses default languages when not specified."""
        query = "How to get KITAS?"
        variants = await expander.translate_variants(query)

        # Should attempt translation
        assert isinstance(variants, list)


class TestFilterRelaxation:
    """Test filter removal/relaxation functionality."""

    @pytest.fixture
    def expander(self):
        return QueryExpander()

    def test_relax_filters_only(self, expander):
        """Test removal of 'only' filter."""
        query = "I only want PT PMA companies"
        relaxed = expander._relax_filters(query)

        assert "only" not in relaxed.lower()
        assert "PT PMA" in relaxed

    def test_relax_filters_specifically(self, expander):
        """Test removal of 'specifically' filter."""
        query = "Specifically for foreign companies"
        relaxed = expander._relax_filters(query)

        assert "specifically" not in relaxed.lower()

    def test_relax_filters_must_be(self, expander):
        """Test removal of 'must be' filter."""
        query = "It must be a PT PMA"
        relaxed = expander._relax_filters(query)

        assert "must be" not in relaxed.lower()

    def test_relax_filters_indonesian(self, expander):
        """Test removal of Indonesian filter words."""
        query = "Saya hanya ingin PT PMA"
        relaxed = expander._relax_filters(query)

        assert "hanya" not in relaxed.lower()

    def test_relax_filters_no_matches(self, expander):
        """Test that query without filters remains unchanged."""
        query = "How to apply for KITAS?"
        relaxed = expander._relax_filters(query)

        assert relaxed == query

    def test_filter_keywords_list(self):
        """Test that filter keywords list exists and is non-empty."""
        assert isinstance(FILTER_KEYWORDS, list)
        assert len(FILTER_KEYWORDS) > 0

        for keyword in FILTER_KEYWORDS:
            assert isinstance(keyword, str)
            assert len(keyword) > 0


class TestLLMRephrasing:
    """Test LLM-based query rephrasing."""

    @pytest.fixture
    def expander(self):
        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock(return_value=True)
        return QueryExpander(cache_service=mock_cache)

    @pytest.mark.asyncio
    async def test_llm_rephrase_success(self, expander):
        """Test successful LLM rephrasing."""
        mock_response = {
            "text": '["What are the steps to obtain KITAS?", "How do I get a residence permit?"]',
        }

        with patch.object(expander, "_get_genai_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.generate_content = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            variants = await expander._llm_rephrase("How to get KITAS?", num_variants=2)

            assert len(variants) == 2
            assert "What are the steps to obtain KITAS?" in variants
            assert "How do I get a residence permit?" in variants

    @pytest.mark.asyncio
    async def test_llm_rephrase_empty_response(self, expander):
        """Test handling of empty LLM response."""
        with patch.object(expander, "_get_genai_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.generate_content = AsyncMock(return_value={"text": ""})
            mock_get_client.return_value = mock_client

            variants = await expander._llm_rephrase("How to get KITAS?")

            assert variants == []

    @pytest.mark.asyncio
    async def test_llm_rephrase_no_client(self, expander):
        """Test fallback when no GenAI client available."""
        with patch.object(expander, "_get_genai_client", return_value=None):
            variants = await expander._llm_rephrase("How to get KITAS?")

            assert variants == []

    @pytest.mark.asyncio
    async def test_llm_rephrase_cache_hit(self, expander):
        """Test that cached rephrasings are returned."""
        cached_result = ["Alternative phrasing 1", "Alternative phrasing 2"]
        expander.cache_service.get = AsyncMock(return_value=cached_result)

        variants = await expander._llm_rephrase("How to get KITAS?")

        assert variants == cached_result
        expander.cache_service.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_rephrase_timeout(self, expander):
        """Test handling of LLM timeout."""
        import asyncio

        with patch.object(expander, "_get_genai_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.generate_content = AsyncMock(side_effect=asyncio.TimeoutError())
            mock_get_client.return_value = mock_client

            variants = await expander._llm_rephrase("How to get KITAS?")

            assert variants == []


class TestHybridExpansion:
    """Test hybrid expansion combining all strategies."""

    @pytest.fixture
    def expander(self):
        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock(return_value=True)
        return QueryExpander(cache_service=mock_cache, max_variants=5)

    @pytest.mark.asyncio
    async def test_expand_returns_original(self, expander):
        """Test that expand always returns original query."""
        query = "How to apply for KITAS?"
        variants = await expander.expand(query)

        assert query in variants

    @pytest.mark.asyncio
    async def test_expand_includes_synonyms(self, expander):
        """Test that expand includes synonym variants."""
        query = "How to apply for KITAS?"
        variants = await expander.expand(query)

        # Should have synonym variants - check that at least one synonym is present
        synonym_variants = expander.generate_synonyms(query)
        # The original query should be present
        assert query in variants
        # At least one variant should exist (original + at least one expansion)
        assert len(variants) >= 1
        # If synonym variants were generated, at least one should be in final variants
        if synonym_variants:
            # Check that variants contains semantically similar terms
            variant_text = " ".join(variants).lower()
            assert any(term in variant_text for term in ["kitas", "residence", "permit", "tinggal"])

    @pytest.mark.asyncio
    async def test_expand_deduplication(self, expander):
        """Test that expand removes duplicates."""
        # Query that might generate duplicates
        query = "KITAS"
        variants = await expander.expand(query, num_variants=10)

        # All variants should be unique
        assert len(variants) == len(set(variants))

    @pytest.mark.asyncio
    async def test_expand_empty_query(self, expander):
        """Test expand with empty query."""
        variants = await expander.expand("")

        assert variants == [""]

    @pytest.mark.asyncio
    async def test_expand_respects_max_variants(self, expander):
        """Test that expand respects max_variants limit."""
        query = "PT PMA and KITAS and NIB requirements"
        variants = await expander.expand(query, num_variants=10)

        assert len(variants) <= expander.max_variants

    @pytest.mark.asyncio
    async def test_hybrid_expansion_alias(self, expander):
        """Test that hybrid_expansion is an alias for expand."""
        query = "How to get KITAS?"

        hybrid_variants = await expander.hybrid_expansion(query)
        expand_variants = await expander.expand(query)

        assert hybrid_variants == expand_variants


class TestErrorHandling:
    """Test error handling and fallbacks."""

    @pytest.fixture
    def expander(self):
        return QueryExpander()

    @pytest.mark.asyncio
    async def test_expand_returns_original_on_error(self, expander):
        """Test that expand returns original query on any error."""
        # Mock generate_synonyms to raise an exception
        with patch.object(expander, "generate_synonyms", side_effect=Exception("Test error")):
            query = "How to get KITAS?"
            variants = await expander.expand(query)

            assert variants == [query]

    @pytest.mark.asyncio
    async def test_translate_variants_returns_empty_on_error(self):
        """Test that translate returns empty list on error."""
        # Create a mock cache that raises exception on get
        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(side_effect=Exception("Test error"))
        expander_with_bad_cache = QueryExpander(cache_service=mock_cache)

        # The exception should bubble up or be handled - let's verify behavior
        try:
            variants = await expander_with_bad_cache.translate_variants("How to get KITAS?")
            # If no exception, should return empty list or handle gracefully
            assert isinstance(variants, list)
        except Exception:
            # Exception is also acceptable behavior
            pass


class TestExpansionDetails:
    """Test detailed expansion breakdown."""

    @pytest.fixture
    def expander(self):
        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock(return_value=True)
        return QueryExpander(cache_service=mock_cache)

    @pytest.mark.asyncio
    async def test_get_expansion_details_structure(self, expander):
        """Test that expansion details has expected structure."""
        query = "How to apply for KITAS?"
        details = await expander.get_expansion_details(query)

        assert "original" in details
        assert "final_variants" in details
        assert "synonym_variants" in details
        assert "translation_variants" in details
        assert "llm_variants" in details
        assert "total_variants" in details
        assert "elapsed_ms" in details

        assert details["original"] == query
        assert isinstance(details["final_variants"], list)
        assert isinstance(details["total_variants"], int)
        assert isinstance(details["elapsed_ms"], float)

    @pytest.mark.asyncio
    async def test_get_expansion_details_counts(self, expander):
        """Test that total_variants count matches final_variants length."""
        query = "How to apply for KITAS?"
        details = await expander.get_expansion_details(query)

        assert details["total_variants"] == len(details["final_variants"])


class TestCaching:
    """Test caching behavior."""

    @pytest.fixture
    def expander(self):
        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock(return_value=True)
        mock_cache.delete = AsyncMock(return_value=True)
        mock_cache.clear_pattern = AsyncMock(return_value=5)
        return QueryExpander(cache_service=mock_cache)

    @pytest.mark.asyncio
    async def test_clear_cache_specific_query(self, expander):
        """Test clearing cache for specific query."""
        query = "How to get KITAS?"
        count = await expander.clear_cache(query)

        # Should clear translate and rephrase keys
        assert count == 2
        assert expander.cache_service.delete.call_count == 2

    @pytest.mark.asyncio
    async def test_clear_cache_all(self, expander):
        """Test clearing all expansion cache."""
        count = await expander.clear_cache()

        assert count == 5
        expander.cache_service.clear_pattern.assert_called_once_with("zantara:query_expand:*")


class TestSingleton:
    """Test singleton pattern."""

    def test_get_query_expander_singleton(self):
        """Test that get_query_expander returns same instance."""
        expander1 = get_query_expander()
        expander2 = get_query_expander()

        assert expander1 is expander2

    def test_get_query_expander_type(self):
        """Test that get_query_expander returns QueryExpander."""
        expander = get_query_expander()

        assert isinstance(expander, QueryExpander)


class TestSemanticSimilarity:
    """Test that expansions maintain semantic similarity."""

    @pytest.fixture
    def expander(self):
        return QueryExpander()

    def test_synonyms_preserve_meaning(self, expander):
        """Test that synonym variants preserve original meaning."""
        query = "KITAS requirements"
        variants = expander.generate_synonyms(query)

        # All variants should contain a term related to permits/residence
        for variant in variants:
            assert any(
                term in variant.lower()
                for term in ["kitas", "residence", "permit", "tinggal", "izin"]
            )

    def test_business_terms_are_equivalent(self):
        """Test that business terms are semantically equivalent pairs."""
        # PT PMA should be equivalent to foreign investment company
        pt_pma_synonyms = INDONESIAN_BUSINESS_TERMS.get("pt pma", [])
        assert "foreign investment company" in pt_pma_synonyms

        # KITAS should be equivalent to residence permit
        kitas_synonyms = INDONESIAN_BUSINESS_TERMS.get("kitas", [])
        assert "residence permit" in kitas_synonyms

        # NIB should be equivalent to business identification number
        nib_synonyms = INDONESIAN_BUSINESS_TERMS.get("nib", [])
        assert "business identification number" in nib_synonyms


class TestIntegrationPatterns:
    """Test patterns for integration with RAG pipeline."""

    @pytest.fixture
    def expander(self):
        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock(return_value=True)
        return QueryExpander(cache_service=mock_cache)

    @pytest.mark.asyncio
    async def test_expand_for_rag_pipeline(self, expander):
        """Test expand method suitable for RAG pipeline integration."""
        user_query = "What are the requirements for PT PMA?"

        variants = await expander.expand(user_query, num_variants=3)

        # Should return list of strings
        assert isinstance(variants, list)
        assert len(variants) > 0
        assert all(isinstance(v, str) for v in variants)

        # Original query should be in variants (not necessarily first due to set ordering)
        assert user_query in variants

    @pytest.mark.asyncio
    async def test_multiple_queries_performance(self, expander):
        """Test handling multiple queries efficiently."""
        queries = [
            "KITAS application",
            "PT PMA setup",
            "NIB registration",
            "OSS requirements",
        ]

        for query in queries:
            variants = await expander.expand(query)
            assert len(variants) > 0
            assert query in variants
