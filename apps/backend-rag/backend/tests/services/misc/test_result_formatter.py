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

    assert formatted == [{"id": None, "text": "Fallback result", "metadata": {}, "score": 1.0}]


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


def test_kbli_declared_gap_rebuilds_text_and_metadata_fail_closed() -> None:
    unsafe_text = """# KBLI 01111: Pertanian Jagung

## Deskripsi (BPS)
Official description in the document.

## Status PMA: TERBUKA
- Kepemilikan asing maksimal: 100

## Perizinan per Skala Usaha (PP 28/2025)
### Skala: Besar
- Kategori risiko: Menengah Tinggi

## Intelligence 2026
- whatChanged: UNSAFE_EDITORIAL_ASSERTION
"""
    metadata = {
        "kode_kbli": "01111",
        "judul": "Pertanian Jagung",
        "official_description": "Uraian resmi BPS.",
        "description": "UNSAFE_LEGACY_GOLD_DESCRIPTION: 100% foreign ownership.",
        "pma_status": "TERBUKA",
        "pma_max_asing": 100,
        "pma_verification_status": "declared_gap",
        "pma_official_basis": None,
        "pma_source_vintage": None,
        "pma_kondisi": "UNSAFE_CONDITION",
        "pma_cap_note": "UNSAFE_CAP_NOTE: 100% inferred",
        "pma_cap_special": True,
        "pma_cap_verified": True,
        "pma_correction": "UNSAFE_CORRECTION",
        "pma_route_to": "UNSAFE_ROUTE",
        "pma_source": "UNSAFE_SOURCE",
        "intel_2026": {"whatChanged": "UNSAFE_EDITORIAL_ASSERTION"},
        "has_intel_2026": True,
        "bali_blocked": False,
        "bali_reason": "UNSAFE_BALI_REASON",
    }

    result = format_search_results(
        {
            "ids": ["kbli-01111"],
            "documents": [unsafe_text],
            "distances": [0.1],
            "metadatas": [metadata],
        },
        "kbli_2025_final_hybrid",
    )[0]

    assert "Uraian resmi BPS." in result["text"]
    assert "Perizinan per Skala Usaha (PP 28/2025)" in result["text"]
    assert "Status PMA: NOT_VERIFIED" in result["text"]
    assert "not national PMA permission" in result["text"]
    for unsafe in (
        "Status PMA: TERBUKA",
        "maksimal: 100",
        "UNSAFE_EDITORIAL_ASSERTION",
        "UNSAFE_CONDITION",
        "UNSAFE_CAP_NOTE",
        "UNSAFE_CORRECTION",
        "UNSAFE_ROUTE",
        "UNSAFE_SOURCE",
        "UNSAFE_BALI_REASON",
        "UNSAFE_LEGACY_GOLD_DESCRIPTION",
    ):
        assert unsafe not in result["text"]
        assert unsafe not in str(result["metadata"])
    assert result["metadata"]["pma_status"] == "NOT_VERIFIED"
    assert result["metadata"]["pma_max_asing"] is None
    assert result["metadata"]["pma_cap_verified"] is False
    assert "pma_cap_note" not in result["metadata"]
    assert "pma_cap_special" not in result["metadata"]
    assert "pma_correction" not in result["metadata"]
    assert "pma_route_to" not in result["metadata"]
    assert "pma_source" not in result["metadata"]
    assert result["metadata"]["has_intel_2026"] is False
    assert "description" not in result["metadata"]
    assert metadata["pma_status"] == "TERBUKA", "the caller-owned metadata must not mutate"


def test_kbli_located_tuple_preserves_verified_text_and_values() -> None:
    text = "## Status PMA: TERBATAS\n- Kepemilikan asing maksimal: 49"
    result = format_search_results(
        {
            "ids": ["kbli-25200"],
            "documents": [text],
            "distances": [0.1],
            "metadatas": [
                {
                    "pma_status": "TERBATAS",
                    "pma_max_asing": 49,
                    "pma_verification_status": "located",
                    "pma_official_basis": "Perpres 49/2021 Lampiran III entry 3",
                    "pma_source_vintage": "2021-05-25",
                }
            ],
        },
        "kbli_2025_final_hybrid",
    )[0]

    assert result["text"] == text
    assert result["metadata"]["pma_status"] == "TERBATAS"
    assert result["metadata"]["pma_max_asing"] == 49
