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


class TestBerapaIsNotAlwaysAboutMoney:
    """`berapa` is Indonesian for "how many/how much" — not for "what does it cost".

    GUILT, measured on production code and the production price list
    (2026-09-17): "Berapa lama proses pendirian PT PMA?" — a question about
    TIME — was classified as price intent, so the turn was handed the price
    list. That cost little while the list was payload only; since #6674 made
    it count as EVIDENCE, the same false positive gave a timing question a 0.3
    evidence score and a chunk carrying "20.000.000 IDR".

    Scar family #3 from the OVER-match side: the guard was judging a generic
    WORD instead of an entity.
    """

    @pytest.mark.parametrize(
        "query",
        [
            "Berapa lama proses pendirian PT PMA?",
            "berapa lama KITAS keluar",
            "Prosesnya berapa hari?",
            "berapa minggu untuk NPWP",
            "berapa bulan masa berlaku KITAS",
            "berapa tahun visa ini berlaku",
            "berapa orang yang dibutuhkan untuk PT PMA",
            "berapa kali harus lapor pajak",
        ],
    )
    def test_a_berapa_question_about_a_non_monetary_unit_is_not_price_intent(
        self, query: str
    ) -> None:
        assert has_pricing_intent(query) is False

    @pytest.mark.parametrize(
        "query",
        [
            # The neutralisation removes a PHRASE, never the rest of the
            # sentence: a question that asks both still matches on its own
            # price word.
            "Berapa lama dan berapa biayanya?",
            "berapa lama prosesnya, dan harga PT PMA berapa?",
            # Bare `berapa` keeps its old answer — nothing is narrowed beyond
            # the seven units named.
            "Berapa harga PT PMA?",
            "PT PMA berapa?",
            "berapa persen pajak penghasilan",
        ],
    )
    def test_innocence_a_real_price_question_still_matches(self, query: str) -> None:
        assert has_pricing_intent(query) is True
