from __future__ import annotations

import pytest

from backend.services.misc.pricing_intent import has_pricing_intent


@pytest.mark.parametrize(
    "query",
    [
        "is remote work permitted on a D12 visa?",
        # Scar #3 word-boundary trap: "fee" is a substring of "coffee", "rate"
        # is a substring of "corporate" — neither is a real price-intent word
        # here, so this must NOT match.
        "what a nice coffee shop and corporate strategy discussion",
        "what documents do I need for a KITAS?",
        "",
    ],
)
def test_has_pricing_intent_guilt_false_on_non_price_questions(query: str) -> None:
    assert has_pricing_intent(query) is False


@pytest.mark.parametrize(
    "query",
    [
        "quanto costa un D12?",
        "how much is the E33G",
        "berapa harga KITAS",
        "what's the price for a PT PMA setup?",
        "quanto viene una KITAP?",
        "biaya tarif untuk NPWP",
    ],
)
def test_has_pricing_intent_innocence_true_on_price_questions(query: str) -> None:
    assert has_pricing_intent(query) is True


def test_has_pricing_intent_is_case_insensitive() -> None:
    assert has_pricing_intent("HOW MUCH does a D12 cost?") is True


def test_has_pricing_intent_none_query_is_false() -> None:
    assert has_pricing_intent(None) is False  # type: ignore[arg-type]
