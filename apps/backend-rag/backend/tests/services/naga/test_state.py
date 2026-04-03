"""Tests for Naga state management: BudgetTracker + URLHistory."""

from __future__ import annotations

import time

import pytest

from backend.services.naga.state.budget_tracker import BudgetTracker
from backend.services.naga.state.url_history import URLHistory


# ---------------------------------------------------------------------------
# BudgetTracker
# ---------------------------------------------------------------------------


class TestBudgetTracker:
    """BudgetTracker tracks search calls and TTL for a research session."""

    def test_initial_state(self) -> None:
        bt = BudgetTracker(max_search_calls=10, ttl_seconds=300)
        assert bt.search_calls_remaining == 10
        assert bt.can_search is True
        assert bt.is_timed_out is False

    def test_record_search_decrements_remaining(self) -> None:
        bt = BudgetTracker(max_search_calls=5, ttl_seconds=300)
        bt.record_search()
        assert bt.search_calls_remaining == 4
        bt.record_search(count=3)
        assert bt.search_calls_remaining == 1

    def test_search_calls_remaining_floors_at_zero(self) -> None:
        bt = BudgetTracker(max_search_calls=2, ttl_seconds=300)
        bt.record_search(count=5)
        assert bt.search_calls_remaining == 0

    def test_can_search_false_when_exhausted(self) -> None:
        bt = BudgetTracker(max_search_calls=1, ttl_seconds=300)
        bt.record_search()
        assert bt.can_search is False

    def test_ttl_timeout(self) -> None:
        bt = BudgetTracker(max_search_calls=100, ttl_seconds=0)
        # ttl_seconds=0 means already expired
        assert bt.is_timed_out is True
        assert bt.can_search is False

    def test_seconds_remaining_decreases(self) -> None:
        bt = BudgetTracker(max_search_calls=10, ttl_seconds=60)
        s1 = bt.seconds_remaining
        assert s1 <= 60.0
        assert s1 > 0.0

    def test_can_search_requires_both_calls_and_time(self) -> None:
        # Out of calls but has time
        bt1 = BudgetTracker(max_search_calls=0, ttl_seconds=300)
        assert bt1.can_search is False

        # Has calls but out of time
        bt2 = BudgetTracker(max_search_calls=10, ttl_seconds=0)
        assert bt2.can_search is False

    def test_summary_dict(self) -> None:
        bt = BudgetTracker(max_search_calls=10, ttl_seconds=300)
        bt.record_search(count=3)
        s = bt.summary()

        assert s["max_search_calls"] == 10
        assert s["search_calls_used"] == 3
        assert s["search_calls_remaining"] == 7
        assert s["ttl_seconds"] == 300
        assert isinstance(s["seconds_remaining"], float)
        assert s["is_timed_out"] is False
        assert s["can_search"] is True

    def test_summary_keys_complete(self) -> None:
        bt = BudgetTracker(max_search_calls=5, ttl_seconds=60)
        expected_keys = {
            "max_search_calls",
            "search_calls_used",
            "search_calls_remaining",
            "ttl_seconds",
            "seconds_remaining",
            "is_timed_out",
            "can_search",
        }
        assert set(bt.summary().keys()) == expected_keys

    def test_record_search_default_count(self) -> None:
        bt = BudgetTracker(max_search_calls=10, ttl_seconds=300)
        bt.record_search()
        assert bt.search_calls_remaining == 9


# ---------------------------------------------------------------------------
# URLHistory
# ---------------------------------------------------------------------------


class TestURLHistory:
    """URLHistory deduplicates URLs across research iterations."""

    def test_add_and_is_new(self) -> None:
        uh = URLHistory()
        assert uh.is_new("https://example.com/page") is True
        uh.add("https://example.com/page")
        assert uh.is_new("https://example.com/page") is False

    def test_count(self) -> None:
        uh = URLHistory()
        assert uh.count == 0
        uh.add("https://a.com")
        uh.add("https://b.com")
        assert uh.count == 2

    def test_duplicate_add_does_not_increase_count(self) -> None:
        uh = URLHistory()
        uh.add("https://example.com")
        uh.add("https://example.com")
        assert uh.count == 1

    # --- URL normalization ---

    def test_strips_utm_params(self) -> None:
        uh = URLHistory()
        uh.add("https://example.com/page?utm_source=google&id=1")
        assert uh.is_new("https://example.com/page?id=1") is False

    def test_strips_fbclid(self) -> None:
        uh = URLHistory()
        uh.add("https://example.com/page?fbclid=abc123&q=test")
        assert uh.is_new("https://example.com/page?q=test") is False

    def test_strips_gclid(self) -> None:
        uh = URLHistory()
        uh.add("https://example.com/?gclid=xyz")
        assert uh.is_new("https://example.com/") is False

    def test_strips_ref_and_source(self) -> None:
        uh = URLHistory()
        uh.add("https://example.com/article?ref=twitter&source=feed")
        assert uh.is_new("https://example.com/article") is False

    def test_strips_fragments(self) -> None:
        uh = URLHistory()
        uh.add("https://example.com/page#section-2")
        assert uh.is_new("https://example.com/page") is False

    def test_strips_trailing_slash(self) -> None:
        uh = URLHistory()
        uh.add("https://example.com/page/")
        assert uh.is_new("https://example.com/page") is False

    def test_preserves_meaningful_params(self) -> None:
        uh = URLHistory()
        uh.add("https://example.com/search?q=test&page=2")
        # Different meaningful params -> different URL
        assert uh.is_new("https://example.com/search?q=other&page=2") is True

    def test_param_order_irrelevant(self) -> None:
        uh = URLHistory()
        uh.add("https://example.com/search?a=1&b=2")
        assert uh.is_new("https://example.com/search?b=2&a=1") is False

    def test_complex_normalization(self) -> None:
        """utm + fragment + trailing slash all at once."""
        uh = URLHistory()
        uh.add("https://example.com/page/?utm_source=google&utm_medium=cpc&id=1#top")
        assert uh.is_new("https://example.com/page?id=1") is False

    # --- add_many ---

    def test_add_many_returns_only_new(self) -> None:
        uh = URLHistory()
        uh.add("https://a.com")
        new = uh.add_many(["https://a.com", "https://b.com", "https://c.com"])
        assert new == ["https://b.com", "https://c.com"]
        assert uh.count == 3

    def test_add_many_empty_list(self) -> None:
        uh = URLHistory()
        assert uh.add_many([]) == []

    def test_add_many_all_duplicates(self) -> None:
        uh = URLHistory()
        uh.add("https://x.com")
        assert uh.add_many(["https://x.com"]) == []

    def test_add_many_deduplicates_within_batch(self) -> None:
        uh = URLHistory()
        new = uh.add_many(["https://a.com", "https://a.com", "https://b.com"])
        # Only first occurrence of a.com counts as new
        assert new == ["https://a.com", "https://b.com"]
        assert uh.count == 2

    def test_strips_multiple_utm_variants(self) -> None:
        uh = URLHistory()
        uh.add(
            "https://example.com/p?utm_source=x&utm_medium=y&utm_campaign=z&utm_term=t&utm_content=c&id=5"
        )
        assert uh.is_new("https://example.com/p?id=5") is False
