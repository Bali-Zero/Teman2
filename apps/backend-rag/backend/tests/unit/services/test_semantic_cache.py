"""Tests for Semantic Cache."""
from backend.services.caching.semantic_cache import (
    _L1_CACHE,
    cache_response,
    get_cache_stats,
    get_cached_response,
    invalidate_cache,
)


class TestSemanticCache:
    def setup_method(self):
        _L1_CACHE.clear()

    def test_cache_miss_returns_none(self):
        assert get_cached_response("unknown query") is None

    def test_cache_hit_after_store(self):
        cache_response("test query", {"answer": "test"})
        result = get_cached_response("test query")
        assert result is not None
        assert result["answer"] == "test"

    def test_case_insensitive(self):
        cache_response("Test Query", {"answer": "ok"})
        assert get_cached_response("test query") is not None

    def test_invalidate_all(self):
        cache_response("q1", {"a": 1})
        cache_response("q2", {"a": 2})
        count = invalidate_cache()
        assert count == 2
        assert get_cached_response("q1") is None

    def test_invalidate_pattern(self):
        cache_response("visa question", {"a": 1})
        cache_response("tax question", {"a": 2})
        count = invalidate_cache("visa")
        assert count == 1
        assert get_cached_response("tax question") is not None

    def test_lru_eviction(self):
        from backend.services.caching.semantic_cache import _L1_MAX_SIZE
        for i in range(_L1_MAX_SIZE + 10):
            cache_response(f"query {i}", {"i": i})
        stats = get_cache_stats()
        assert stats["l1_size"] <= _L1_MAX_SIZE

    def test_stats(self):
        stats = get_cache_stats()
        assert "l1_size" in stats
        assert "l1_max" in stats
        assert "l1_ttl" in stats
