"""Unit tests for backend/services/rag/query_expansion.py"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset module-level singleton between tests."""
    with patch("backend.services.rag.query_expansion.get_cache_service") as mock_cs:
        mock_cache = AsyncMock()
        mock_cache.get.return_value = None
        mock_cache.set.return_value = True
        mock_cache.delete.return_value = True
        mock_cache.clear_pattern.return_value = 0
        mock_cs.return_value = mock_cache
        yield mock_cache


@pytest.fixture
def expander(_reset_singleton):
    """Create a QueryExpander with mocked cache."""
    with patch("backend.services.rag.query_expansion.GENAI_AVAILABLE", False):
        from backend.services.rag.query_expansion import QueryExpander

        return QueryExpander(cache_service=_reset_singleton, max_variants=5)


# ---------------------------------------------------------------------------
# generate_synonyms
# ---------------------------------------------------------------------------


class TestGenerateSynonyms:
    def test_kitas_produces_synonyms(self, expander):
        variants = expander.generate_synonyms("How to apply for KITAS?")
        assert len(variants) > 0
        # Should contain at least one synonym for KITAS
        found = any(
            "residence permit" in v.lower() or "kartu izin tinggal" in v.lower()
            for v in variants
        )
        assert found, f"Expected synonym for KITAS, got: {variants}"

    def test_pt_pma_produces_synonyms(self, expander):
        variants = expander.generate_synonyms("How to establish PT PMA?")
        assert len(variants) > 0

    def test_no_match_returns_empty(self, expander):
        variants = expander.generate_synonyms("Hello world how are you?")
        assert variants == []

    def test_empty_query_returns_empty(self, expander):
        assert expander.generate_synonyms("") == []
        assert expander.generate_synonyms("   ") == []

    def test_nib_synonym(self, expander):
        variants = expander.generate_synonyms("What is NIB?")
        assert any("business identification number" in v.lower() for v in variants)

    def test_multiple_terms_in_query(self, expander):
        variants = expander.generate_synonyms("KITAS and NPWP requirements")
        assert len(variants) > 0

    def test_case_insensitive(self, expander):
        variants_upper = expander.generate_synonyms("KITAS application")
        variants_lower = expander.generate_synonyms("kitas application")
        # Both should produce synonyms
        assert len(variants_upper) > 0
        assert len(variants_lower) > 0


# ---------------------------------------------------------------------------
# _relax_filters
# ---------------------------------------------------------------------------


class TestRelaxFilters:
    def test_removes_only(self, expander):
        result = expander._relax_filters("I only want PT PMA companies")
        assert "only" not in result.lower()
        assert "PT PMA" in result

    def test_removes_specifically(self, expander):
        result = expander._relax_filters("I specifically need KITAS info")
        assert "specifically" not in result.lower()
        assert "KITAS" in result

    def test_removes_hanya(self, expander):
        result = expander._relax_filters("hanya untuk perusahaan besar")
        assert "hanya" not in result.lower()

    def test_removes_wajib(self, expander):
        result = expander._relax_filters("wajib menggunakan NIB baru")
        assert "wajib" not in result.lower()

    def test_no_filter_returns_same(self, expander):
        query = "How to get a visa?"
        result = expander._relax_filters(query)
        assert result == query

    def test_empty_input(self, expander):
        assert expander._relax_filters("") == ""

    def test_cleans_whitespace(self, expander):
        result = expander._relax_filters("I only want   just this")
        assert "  " not in result


# ---------------------------------------------------------------------------
# _dictionary_translate
# ---------------------------------------------------------------------------


class TestDictionaryTranslate:
    def test_translates_how_to(self, expander):
        variants = expander._dictionary_translate("how to get KITAS", ["id"])
        assert len(variants) > 0
        assert any("cara" in v.lower() for v in variants)

    def test_translates_requirements(self, expander):
        variants = expander._dictionary_translate("requirements for NIB", ["id"])
        assert any("persyaratan" in v.lower() for v in variants)

    def test_no_match_returns_empty(self, expander):
        variants = expander._dictionary_translate("xyz blah", ["id"])
        assert len(variants) == 0

    def test_empty_query_returns_empty(self, expander):
        variants = expander._dictionary_translate("", ["id", "en"])
        assert len(variants) == 0


# ---------------------------------------------------------------------------
# expand (async)
# ---------------------------------------------------------------------------


class TestExpand:
    @pytest.mark.asyncio
    async def test_expand_always_includes_original(self, expander):
        result = await expander.expand("How to get KITAS?")
        assert result[0] == "How to get KITAS?"

    @pytest.mark.asyncio
    async def test_expand_empty_query(self, expander):
        result = await expander.expand("")
        assert result == [""]

    @pytest.mark.asyncio
    async def test_expand_whitespace_only(self, expander):
        result = await expander.expand("   ")
        assert result == ["   "]

    @pytest.mark.asyncio
    async def test_expand_respects_max_variants(self, expander):
        expander.max_variants = 2
        result = await expander.expand("How to apply for KITAS visa?")
        assert len(result) <= 2

    @pytest.mark.asyncio
    async def test_expand_includes_synonyms(self, expander):
        result = await expander.expand("KITAS application")
        # Should have more than just the original
        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_expand_exception_returns_original(self, expander):
        """If expansion fails, return original query."""
        with patch.object(
            expander, "generate_synonyms", side_effect=RuntimeError("boom")
        ):
            result = await expander.expand("test query")
        assert result == ["test query"]


# ---------------------------------------------------------------------------
# translate_variants (async)
# ---------------------------------------------------------------------------


class TestTranslateVariants:
    @pytest.mark.asyncio
    async def test_translate_with_cache_hit(self, expander, _reset_singleton):
        _reset_singleton.get.return_value = ["cached variant"]
        result = await expander.translate_variants("How to get KITAS?")
        assert result == ["cached variant"]

    @pytest.mark.asyncio
    async def test_translate_empty_query(self, expander):
        result = await expander.translate_variants("")
        assert result == []

    @pytest.mark.asyncio
    async def test_translate_caches_result(self, expander, _reset_singleton):
        _reset_singleton.get.return_value = None
        await expander.translate_variants("how to get visa")
        _reset_singleton.set.assert_called()


# ---------------------------------------------------------------------------
# _llm_rephrase (async)
# ---------------------------------------------------------------------------


class TestLlmRephrase:
    @pytest.mark.asyncio
    async def test_rephrase_with_cache_hit(self, expander, _reset_singleton):
        _reset_singleton.get.return_value = ["rephrased A", "rephrased B"]
        result = await expander._llm_rephrase("test query", num_variants=2)
        assert result == ["rephrased A", "rephrased B"]

    @pytest.mark.asyncio
    async def test_rephrase_no_client_returns_empty(self, expander, _reset_singleton):
        _reset_singleton.get.return_value = None
        result = await expander._llm_rephrase("test query")
        assert result == []


# ---------------------------------------------------------------------------
# _llm_translate (async)
# ---------------------------------------------------------------------------


class TestLlmTranslate:
    @pytest.mark.asyncio
    async def test_no_client_returns_empty(self, expander):
        result = await expander._llm_translate("test", ["id"])
        assert result == set()


# ---------------------------------------------------------------------------
# hybrid_expansion (async)
# ---------------------------------------------------------------------------


class TestHybridExpansion:
    @pytest.mark.asyncio
    async def test_hybrid_delegates_to_expand(self, expander):
        with patch.object(expander, "expand", new_callable=AsyncMock) as mock_expand:
            mock_expand.return_value = ["q1", "q2"]
            result = await expander.hybrid_expansion("test")
        mock_expand.assert_called_once_with("test", num_variants=5)
        assert result == ["q1", "q2"]


# ---------------------------------------------------------------------------
# get_expansion_details (async)
# ---------------------------------------------------------------------------


class TestGetExpansionDetails:
    @pytest.mark.asyncio
    async def test_returns_all_strategy_results(self, expander):
        result = await expander.get_expansion_details("How to get KITAS?")

        assert result["original"] == "How to get KITAS?"
        assert "final_variants" in result
        assert "synonym_variants" in result
        assert "translation_variants" in result
        assert "llm_variants" in result
        assert "total_variants" in result
        assert "elapsed_ms" in result
        assert isinstance(result["elapsed_ms"], float)

    @pytest.mark.asyncio
    async def test_details_relaxed_query_included(self, expander):
        result = await expander.get_expansion_details(
            "I only need KITAS info"
        )
        assert result["relaxed_query"] is not None
        assert "only" not in result["relaxed_query"].lower()


# ---------------------------------------------------------------------------
# clear_cache (async)
# ---------------------------------------------------------------------------


class TestClearCache:
    @pytest.mark.asyncio
    async def test_clear_specific_query(self, expander, _reset_singleton):
        _reset_singleton.delete.return_value = True
        count = await expander.clear_cache("test query")
        assert count == 2  # translate + rephrase keys

    @pytest.mark.asyncio
    async def test_clear_all(self, expander, _reset_singleton):
        _reset_singleton.clear_pattern.return_value = 5
        count = await expander.clear_cache()
        assert count == 5


# ---------------------------------------------------------------------------
# _generate_cache_key
# ---------------------------------------------------------------------------


class TestGenerateCacheKey:
    def test_deterministic(self, expander):
        key1 = expander._generate_cache_key("test", "rephrase")
        key2 = expander._generate_cache_key("test", "rephrase")
        assert key1 == key2

    def test_different_methods_differ(self, expander):
        key1 = expander._generate_cache_key("test", "rephrase")
        key2 = expander._generate_cache_key("test", "translate")
        assert key1 != key2

    def test_prefix(self, expander):
        key = expander._generate_cache_key("test", "rephrase")
        assert key.startswith("zantara:query_expand:")


# ---------------------------------------------------------------------------
# _get_genai_client
# ---------------------------------------------------------------------------


class TestGetGenaiClient:
    def test_returns_none_when_unavailable(self, expander):
        with patch("backend.services.rag.query_expansion.GENAI_AVAILABLE", False):
            client = expander._get_genai_client()
        assert client is None


# ---------------------------------------------------------------------------
# get_query_expander singleton
# ---------------------------------------------------------------------------


class TestGetQueryExpander:
    def test_singleton(self):
        with patch("backend.services.rag.query_expansion.get_cache_service"):
            with patch(
                "backend.services.rag.query_expansion.GENAI_AVAILABLE", False
            ):
                import backend.services.rag.query_expansion as mod

                mod._query_expander_instance = None
                e1 = mod.get_query_expander()
                e2 = mod.get_query_expander()
                assert e1 is e2
                mod._query_expander_instance = None  # cleanup
