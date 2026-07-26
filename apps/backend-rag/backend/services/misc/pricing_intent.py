"""
Pricing-intent classifier for the RAG search boost gate.

Pure, dependency-free helper: no class instantiation, no I/O. Decides whether
a raw user query is actually ASKING about price, so the unconditional
`PRICING_SCORE_BOOST` in result_formatter.py doesn't fire on every
visa/company/tax question that merely happens to touch a domain the
`bali_zero_pricing_hybrid` collection also covers.

Scar family #3 (guard-over-match, .claude/rules/cicatrix-superscar.md)
discipline: matching must be on ENTITY/INTENT, never bare substring.
"fee" is a substring of "coffee", "rate" is a substring of "corporate",
"cost" is a substring of "Costa Rica" — single-word keywords are matched
on \\b word boundaries. Multi-word phrases ("how much", "quanto costa")
are naturally self-delimiting and may match as substrings.
"""

from __future__ import annotations

import re

# EN + IT + ID price-intent terms. Alternation order does not affect
# re.search() correctness (boolean any-match) — longest-phrase-first
# only for readability.
_PRICE_INTENT_TERMS = (
    "how much",
    "quanto costa",
    "quanto viene",
    "pricing",
    "price",
    "costs",
    "cost",
    "fees",
    "fee",
    "charge",
    "rates",
    "rate",
    "prezzi",
    "prezzo",
    "costi",
    "costo",
    "tariffa",
    "berapa",
    "harga",
    "biaya",
    "tarif",
)

_PRICE_INTENT_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(term) for term in _PRICE_INTENT_TERMS) + r")\b",
    re.IGNORECASE,
)


def has_pricing_intent(query: str) -> bool:
    """Return True if `query` is actually asking about a price/cost/fee.

    Pure function — no side effects, no service dependency. Word-boundary
    matched (scar #3): "coffee"/"corporate"/"Costa Rica" do NOT trigger a
    false positive just because they contain "fee"/"rate"/"cost".
    """
    if not query:
        return False
    return bool(_PRICE_INTENT_RE.search(query))
