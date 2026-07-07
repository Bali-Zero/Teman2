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
