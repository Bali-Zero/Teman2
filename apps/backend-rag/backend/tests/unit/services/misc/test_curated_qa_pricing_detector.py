"""Phase-0 safety rail (FATAL 13): deterministic pricing-content detector.

Guilt: answers that actually state a price/cost figure must be caught.
Innocence: prose that merely CONTAINS price-intent substrings ("coffee",
"Costa Rica", "corporate") — or generic non-price numbers — must NOT trip
the detector (scar family #3 discipline).
"""

from __future__ import annotations

import pytest

from backend.services.misc.curated_qa_pricing_detector import has_price_content

# ── Guilt: real price-bearing text ──────────────────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        "The E33 deposit is USD 130,000 in a state-owned bank.",
        "The service fee is Rp 5.000.000 for standard processing.",
        "Prices start from $50 per month.",
        "Starting from Rp 2 juta for a single extension.",
        "Costs range Rp 5.000.000-10.000.000 depending on complexity.",
        "Biaya sekitar IDR 15 juta untuk paket lengkap.",
        "Il deposito richiesto è di € 200 per la pratica.",
        "Package price is Rp 5M for the fast-track option.",
        "mulai dari Rp 1.500.000 per bulan.",
        "a partire da € 300 per il servizio base.",
        "The annual retainer is 2.5 million IDR.",
    ],
)
def test_detects_price_bearing_text(text: str) -> None:
    assert has_price_content(text) is True


# ── Innocence: substring traps + generic non-price text ────────────────────


@pytest.mark.parametrize(
    "text",
    [
        "We can meet over coffee to discuss your case.",
        "Costa Rica is not a market Bali Zero currently serves.",
        "This is handled by our corporate services division.",
        "The process typically takes 5 to 10 business days.",
        "You will need your passport, a photo, and proof of address.",
        "Section M of the form covers dependents.",
        "The deposit must be held for a minimum of 2 years.",
        "",
        None,
    ],
)
def test_does_not_flag_innocent_text(text) -> None:
    assert has_price_content(text) is False


def test_bare_currency_code_without_digit_is_not_flagged() -> None:
    """A bare mention of USD/IDR/Rp with no attached figure is not itself a
    price STATEMENT — e.g. 'fees are quoted in USD' names a currency, it
    doesn't state an amount."""
    assert has_price_content("All our fees are quoted in USD for clarity.") is False


def test_number_without_currency_marker_is_not_flagged() -> None:
    assert has_price_content("The application has 3 stages and takes 10 days.") is False
