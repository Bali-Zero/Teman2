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

# `berapa` alone is the weak link in the list above, and the only term there
# that is not about money in its own language: in Indonesian it is the bare
# interrogative "how many / how much", so "berapa lama" is "how LONG" and
# "berapa orang" is "how MANY PEOPLE". Scar family #3 again, from the OVER-match
# side — the guard was judging a generic word instead of an entity.
#
# MEASURED, not theorised (2026-09-17, prod code + prod price list):
# "Berapa lama proses pendirian PT PMA?" — a question about TIME — classified as
# price intent, so the turn got the price list attached. That was nearly free
# while the price list was payload only; since B2.5-3 (#6674) made the list count
# as EVIDENCE, the same false positive now hands a timing question a 0.3 evidence
# score and a chunk carrying "20.000.000 IDR". The cure belongs here, at the
# classifier, not at the consumer.
#
# Deliberately NARROW: only the units that cannot denominate money. Anything the
# list does not name keeps its old answer, and a query that asks BOTH
# ("berapa lama dan berapa biayanya?") still matches on its own price word — the
# neutralisation removes the phrase, never the rest of the sentence.
_NON_PRICE_BERAPA_UNITS = (
    "lama",  # how long (duration)
    "hari",  # days
    "minggu",  # weeks
    "bulan",  # months
    "tahun",  # years
    "orang",  # people
    "kali",  # times (occurrences)
)

_NON_PRICE_BERAPA_RE = re.compile(
    r"\bberapa\s+(?:" + "|".join(_NON_PRICE_BERAPA_UNITS) + r")\b",
    re.IGNORECASE,
)


def has_pricing_intent(query: str) -> bool:
    """Return True if `query` is actually asking about a price/cost/fee.

    Pure function — no side effects, no service dependency. Word-boundary
    matched (scar #3): "coffee"/"corporate"/"Costa Rica" do NOT trigger a
    false positive just because they contain "fee"/"rate"/"cost". The same
    scar from the other side: bare `berapa` is Indonesian for "how many",
    so "berapa lama" (how long) is a question about TIME and must not match.
    """
    if not query:
        return False
    # Strip the non-monetary `berapa <unit>` phrases BEFORE the search, so what
    # remains is judged normally: this removes a phrase, never a sentence.
    return bool(_PRICE_INTENT_RE.search(_NON_PRICE_BERAPA_RE.sub(" ", query)))
