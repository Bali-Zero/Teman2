"""Pricing grader — extra-strict check for pricing accuracy.

Pricing is the most dangerous area for hallucinations. This grader
has the highest pass threshold (0.9) and checks specifically for
price-related claims against source documents.
"""

from __future__ import annotations

import logging
import re

from backend.services.rag.grading.base import BaseGrader
from backend.services.rag.grading.context import GradingContext

logger = logging.getLogger(__name__)

# Patterns that indicate pricing content
PRICE_PATTERNS = [
    r"\$[\d,]+",                          # $1,200,000
    r"USD\s*[\d,]+",                       # USD 1200000
    r"IDR\s*[\d,.]+",                      # IDR 10,000,000
    r"Rp\.?\s*[\d,.]+",                    # Rp. 10.000.000
    r"[\d,]+\s*(?:juta|miliar|ribu)",      # 10 juta, 1 miliar
]


def contains_pricing(text: str) -> bool:
    """Check if text contains any pricing patterns."""
    return any(
        re.search(p, text, re.IGNORECASE)
        for p in PRICE_PATTERNS
    )


class PricingGrader(BaseGrader):
    grader_name = "pricing"
    pass_threshold = 0.9  # very strict for pricing
    fail_fast_threshold = 0.2

    def _evaluate(self, ctx: GradingContext) -> tuple[float, str, str]:
        answer = ctx.answer

        if not answer:
            return 1.0, "No answer to check for pricing", ""

        # Check if answer contains pricing
        if not contains_pricing(answer):
            return 1.0, "No pricing content in answer, grader N/A", ""

        # Check if prices can be traced to source documents
        source_text = " ".join(d.content for d in ctx.retrieved_documents)

        # Extract all price mentions from answer
        answer_prices: set[str] = set()
        for pattern in PRICE_PATTERNS:
            matches = re.findall(pattern, answer, re.IGNORECASE)
            answer_prices.update(matches)

        if not answer_prices:
            return 1.0, "No extractable prices found", ""

        # Check how many prices appear in source docs
        grounded = sum(1 for p in answer_prices if p in source_text)
        ratio = grounded / len(answer_prices)

        # Also check KG entities for pricing data
        kg_text = " ".join(str(e) for e in ctx.kg_entities)
        kg_grounded = sum(1 for p in answer_prices if p in kg_text)
        kg_ratio = kg_grounded / len(answer_prices) if answer_prices else 0

        combined = max(ratio, kg_ratio)  # either source is fine

        if combined < self.fail_fast_threshold:
            return combined, f"Pricing appears fabricated ({len(answer_prices)} prices, {grounded} grounded)", ""

        if combined < self.pass_threshold:
            hint = "Verify all prices against official pricing data before including them"
            return combined, f"Some prices unverified (ratio={combined:.2f})", hint

        return combined, f"All prices verified (ratio={combined:.2f})", ""
