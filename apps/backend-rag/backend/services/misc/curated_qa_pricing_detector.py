"""
Deterministic pricing-content detector for the curated_qa harvester
(Phase-0 safety rail, FATAL 13 — research/operations/2026-07-17-full-domain-cache-design.md §8).

Pure, dependency-free helper: no class instantiation, no I/O. Decides whether
an ANSWER TEXT actually states a price/cost figure, so
`scripts/curated_qa_harvest.py` can refuse to write price-bearing rows to the
exact-match FAQ (Redis) sink — a cached verbatim price is a stale price
waiting to happen, and prices must come from `PricingTool` only
(apps/backend-rag/CLAUDE.md §Pricing Rules).

This is a DIFFERENT detector than `pricing_intent.has_pricing_intent()`:
that one asks "is the USER'S QUERY asking about price" (query-side, price
INTENT keywords like "fee"/"cost"/"rate"). This one asks "does the ANSWER
TEXT actually CONTAIN a price figure" (answer-side, currency MARKERS and
numeric patterns) — deliberately NOT reusing bare price-intent keywords
("fee", "cost", "price", "rate") because those are exactly the substrings
that trap on "coffee", "Costa Rica", "corporate" (scar family #3,
.claude/rules/cicatrix-superscar.md). A currency SYMBOL or a spelled-out
money amount is a much narrower, safer signal for "this text states a
figure" than a bare price-intent word.
"""

from __future__ import annotations

import re

# Currency-marker + digit adjacency: "Rp 5.000.000", "USD 130,000", "$50",
# "€ 200", "IDR15000000". Requires a digit immediately (optionally after
# whitespace/punctuation) after the currency token — a bare "USD" or "Rp"
# mention with no number attached is not itself a price figure.
_CURRENCY_WITH_DIGIT_RE = re.compile(
    r"""
    (?:
        \bRp\.?\s?\d               # Rp 5.000.000 / Rp.5jt
      | \bIDR\s?\d                 # IDR 5000000
      | \bUSD\s?\d                 # USD 130,000
      | \$\s?\d                    # $50 / $ 50
      | €\s?\d                     # € 200
      | \d[\d.,]*\s?(?:IDR|USD|Rp)\b  # 5.000.000 IDR / 130,000 USD
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# "Starting from" / "mulai dari" / "a partire da" style open-ended price
# framing — these phrases signal a price statement even before any digit is
# reached, and are exactly the pattern the design doc's §8 FATAL 13 calls out.
_STARTING_FROM_RE = re.compile(
    r"\b(starting from|starts at|from only|mulai dari|a partire da)\b",
    re.IGNORECASE,
)

# Spelled-out amounts in money context: "15 juta", "2.5 million", "1 milyar",
# "500 ribu". "M" (as in "Rp 5M") is intentionally scoped to a currency-
# prefixed numeric context via _CURRENCY_RANGE_RE below, not matched bare
# here — a bare "\d+\s?M" is far too easy to false-positive (shirt size,
# section numbers, etc).
_SPELLED_AMOUNT_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s?(?:juta|million|milyar|billion|ribu|thousand)\b",
    re.IGNORECASE,
)

# A numeric range with an explicit currency marker on at least one side, or a
# currency-prefixed amount using the "M" (million) shorthand — e.g.
# "Rp 5-10 juta" is already caught above, but "USD 2,000-5,000" and
# "Rp 5M" need their own pattern since the dash isn't itself the price
# signal — the currency token is.
_CURRENCY_RANGE_OR_SHORTHAND_RE = re.compile(
    r"(?:Rp\.?|USD|IDR|\$|€)\s?[\d.,]+\s?M\b"  # Rp 5M / USD2M
    r"|(?:Rp\.?|USD|IDR|\$|€)\s?[\d.,]+\s?(?:-|to|–|—)\s?(?:Rp\.?|USD|IDR|\$|€)?\s?[\d.,]+",
    re.IGNORECASE,
)

_ALL_PATTERNS = (
    _CURRENCY_WITH_DIGIT_RE,
    _STARTING_FROM_RE,
    _SPELLED_AMOUNT_RE,
    _CURRENCY_RANGE_OR_SHORTHAND_RE,
)


def has_price_content(text: str | None) -> bool:
    """Return True if `text` states a price/cost figure.

    Pure function — no side effects, no service dependency. Deliberately
    narrower than `pricing_intent.has_pricing_intent()`: matches currency
    markers + digits, "starting from"-style framing, spelled-out amounts,
    and currency-prefixed ranges/shorthand — never bare words like
    "fee"/"cost"/"price"/"rate" (scar family #3: those trap on
    "coffee"/"Costa Rica"/"corporate").

    Used by `scripts/curated_qa_harvest.py` to refuse price-bearing rows
    for the FAQ (Redis) verbatim sink — prices must come from `PricingTool`
    only and change independently of any curated_qa row's `source_date`.
    """
    if not text:
        return False
    return any(pattern.search(text) for pattern in _ALL_PATTERNS)
