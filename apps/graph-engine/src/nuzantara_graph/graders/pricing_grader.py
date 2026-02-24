"""Pricing grader — extra-strict check for pricing accuracy.

Pricing is the most dangerous area for hallucinations. This grader
has the highest pass threshold (0.9) and checks specifically for
price-related claims against source documents.
"""

from __future__ import annotations

import re
from typing import Any

import structlog

from nuzantara_graph.graders.base import BaseGrader
from nuzantara_graph.services import Services
from nuzantara_schemas.state import GraphState

logger = structlog.get_logger()

# Patterns that indicate pricing content
PRICE_PATTERNS = [
    r"\$[\d,]+",           # $1,200,000
    r"USD\s*[\d,]+",       # USD 1200000
    r"IDR\s*[\d,.]+",      # IDR 10,000,000
    r"Rp\.?\s*[\d,.]+",    # Rp. 10.000.000
    r"[\d,]+\s*(?:juta|miliar|ribu)",  # 10 juta, 1 miliar
]


class PricingGrader(BaseGrader):
    grader_name = "pricing"
    pass_threshold = 0.9  # very strict for pricing
    fail_fast_threshold = 0.2

    def _evaluate(self, state: GraphState) -> tuple[float, str, str]:
        answer = state.answer

        # Check if answer contains pricing
        has_prices = any(
            re.search(p, answer, re.IGNORECASE)
            for p in PRICE_PATTERNS
        )

        if not has_prices:
            # No pricing in answer — this grader is not applicable
            return 1.0, "No pricing content in answer, grader N/A", ""

        # Check if prices can be traced to source documents
        docs = state.retrieved_documents
        source_text = " ".join(d.content for d in docs)

        # Extract all price mentions from answer
        answer_prices = set()
        for pattern in PRICE_PATTERNS:
            matches = re.findall(pattern, answer, re.IGNORECASE)
            answer_prices.update(matches)

        if not answer_prices:
            return 1.0, "No extractable prices found", ""

        # Check how many prices appear in source docs
        grounded = sum(1 for p in answer_prices if p in source_text)
        ratio = grounded / len(answer_prices)

        # Also check KG entities for pricing data
        kg_text = " ".join(str(e) for e in state.kg_entities)
        kg_grounded = sum(1 for p in answer_prices if p in kg_text)
        kg_ratio = kg_grounded / len(answer_prices) if answer_prices else 0

        combined = max(ratio, kg_ratio)  # either source is fine

        if combined < self.fail_fast_threshold:
            return combined, f"Pricing appears fabricated ({len(answer_prices)} prices, {grounded} grounded)", ""

        if combined < self.pass_threshold:
            hint = "Verify all prices against official pricing data before including them"
            return combined, f"Some prices unverified (ratio={combined:.2f})", hint

        return combined, f"All prices verified (ratio={combined:.2f})", ""


def make_pricing_grader(services: Services | None = None):
    """Factory that creates a pricing grader node."""
    grader = PricingGrader()

    async def pricing_grader_node(state: GraphState) -> dict[str, Any]:
        result = grader.grade(state)
        grades = list(state.grades) + [result]

        updates: dict[str, Any] = {
            "grades": grades,
            "current_node": "grade_pricing",
        }

        if result.decision.value == "retry":
            updates["correction_count"] = min(state.correction_count + 1, state.max_corrections)

        return updates

    return pricing_grader_node
