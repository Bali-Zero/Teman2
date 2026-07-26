from __future__ import annotations

from backend.services.misc.result_formatter import format_search_results


def test_format_search_results_normalizes_scores_and_preserves_metadata_copy() -> None:
    metadata = {"type": "visa"}
    raw_results = {
        "ids": ["doc-1"],
        "documents": ["KITAS pricing"],
        "distances": [0.25],
        "metadatas": [metadata],
    }

    formatted = format_search_results(
        raw_results,
        "bali_zero_pricing_hybrid",
        primary_collection="visa_oracle",
    )

    assert formatted == [
        {
            "id": "doc-1",
            "text": "KITAS pricing",
            "metadata": {
                "type": "visa",
                "source_collection": "bali_zero_pricing_hybrid",
                "is_primary": False,
                "pricing_priority": "high",
            },
            "score": 0.95,
        }
    ]
    assert metadata == {"type": "visa"}


def test_format_search_results_applies_primary_collection_boost() -> None:
    formatted = format_search_results(
        {
            "ids": ["doc-1"],
            "documents": ["Primary result"],
            "distances": [1.0],
            "metadatas": [{}],
        },
        "visa_oracle",
        primary_collection="visa_oracle",
    )

    assert formatted[0]["score"] == 0.55
    assert formatted[0]["metadata"]["is_primary"] is True


def test_format_search_results_handles_missing_optional_arrays_and_negative_distance() -> None:
    formatted = format_search_results(
        {"documents": ["Fallback result"], "distances": [-0.2]},
        "general",
    )

    assert formatted == [
        {"id": None, "text": "Fallback result", "metadata": {}, "score": 1.0}
    ]


def test_format_search_results_returns_empty_for_no_documents() -> None:
    assert format_search_results({}, "general") == []


def _pricing_raw_results() -> dict:
    return {
        "ids": ["doc-1"],
        "documents": ["D12 remote work rules"],
        "distances": [1.0],
        "metadatas": [{}],
    }


def test_format_search_results_pricing_boost_skipped_without_price_intent() -> None:
    # Guilt: a non-price question hitting the pricing collection must NOT
    # get the +0.15 boost — this is the unsolicited-price-dump bug.
    formatted = format_search_results(
        _pricing_raw_results(),
        "bali_zero_pricing_hybrid",
        query="is remote work permitted on a D12 visa?",
    )
    assert formatted[0]["score"] == 0.5  # base score only, no boost


def test_format_search_results_pricing_boost_applied_with_price_intent() -> None:
    # Innocence: a genuine price question still gets the boost.
    formatted = format_search_results(
        _pricing_raw_results(),
        "bali_zero_pricing_hybrid",
        query="quanto costa un D12?",
    )
    assert formatted[0]["score"] == 0.65  # base 0.5 + PRICING_SCORE_BOOST 0.15


def test_format_search_results_pricing_boost_applied_when_query_omitted() -> None:
    # Backwards compat: query=None (caller can't tell us) keeps old
    # unconditional-boost behavior.
    formatted = format_search_results(_pricing_raw_results(), "bali_zero_pricing_hybrid")
    assert formatted[0]["score"] == 0.65


def test_format_search_results_team_boost_unaffected_by_query() -> None:
    # bali_zero_team boost is out of scope for the pricing-intent gate —
    # must stay unconditional regardless of query.
    formatted = format_search_results(
        _pricing_raw_results(),
        "bali_zero_team",
        query="is remote work permitted on a D12 visa?",
    )
    assert formatted[0]["score"] == 0.65
