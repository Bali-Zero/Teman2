"""
Dynamic Scenario Pricer - Phase 3 (Core Agent #2)

Calculates comprehensive pricing for business scenarios by aggregating
costs from multiple Oracle collections.

Example: "PT PMA Restaurant in Seminyak, 3 foreign directors"
→ Aggregates costs from:
  - KBLI setup (kbli_eye)
  - Legal incorporation (legal_architect)
  - Tax registration (tax_genius)
  - Visa costs (visa_oracle) x3
  - Location requirements (property_knowledge)
  - Service fees (bali_zero_pricing)

→ Output: Detailed breakdown + total investment + timeline
"""

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CostItem:
    """Single cost item"""

    category: str  # e.g., "Legal", "Visa", "Tax"
    description: str
    amount: float  # In IDR
    currency: str = "IDR"
    source_oracle: str = ""
    is_recurring: bool = False
    frequency: str | None = None  # "monthly", "annually", etc.


@dataclass
class PricingResult:
    """Result of dynamic pricing calculation"""

    scenario: str
    total_setup_cost: float  # One-time costs
    total_recurring_cost: float  # Recurring costs (annual)
    currency: str
    cost_items: list[CostItem]
    timeline_estimate: str
    breakdown_by_category: dict[str, float]
    key_assumptions: list[str]
    confidence: float  # 0.0-1.0


class DynamicPricingService:
    """
    Calculates scenario-based pricing by aggregating Oracle knowledge.

    Works with CrossOracleSynthesisService to extract cost information.
    """

    # Cost extraction patterns (regex)
    COST_PATTERNS = [
        # IDR formats
        r"Rp\s*([0-9.,]+)\s*(juta|million|ribu|thousand)?",
        r"([0-9.,]+)\s*IDR",
        # USD formats
        r"\$\s*([0-9.,]+)",
        r"USD\s*([0-9.,]+)",
        # Generic number + currency
        r"([0-9.,]+)\s*(rupiah|dollar)",
    ]

    # Known cost categories
    COST_CATEGORIES = {
        "legal": ["notary", "deed", "akta", "incorporation", "pt pma", "bkpm"],
        "licensing": ["nib", "oss", "business license", "izin", "kbli"],
        "tax": ["npwp", "pkp", "tax registration", "pajak"],
        "visa": ["kitas", "kitap", "imta", "visa", "work permit", "rptka"],
        "property": ["rent", "lease", "sewa", "property", "location"],
        "service_fees": ["bali zero", "consultation", "service", "professional fee"],
    }

    def __init__(self, cross_oracle_synthesis_service, search_service):
        """
        Initialize Dynamic Pricing Service.

        Args:
            cross_oracle_synthesis_service: For Oracle orchestration
            search_service: For direct pricing queries
        """
        self.synthesis = cross_oracle_synthesis_service
        self.search = search_service

        self.pricing_stats = {
            "total_calculations": 0,
            "avg_total_cost": 0.0,
            "scenarios_priced": {},
        }

        logger.info("✅ DynamicPricingService initialized")

    def extract_costs_from_text(self, text: str, source_oracle: str = "") -> list[CostItem]:
        """
        Extract cost information from Oracle result text.

        Args:
            text: Text from Oracle result
            source_oracle: Which Oracle provided this text

        Returns:
            List of extracted CostItems
        """
        costs = []

        # Try each pattern
        for pattern in self.COST_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)

            for match in matches:
                try:
                    # Extract amount
                    amount_str = match.group(1).replace(",", "").replace(".", "")
                    amount = float(amount_str)

                    # Handle multipliers (juta, ribu, etc.)
                    if len(match.groups()) > 1 and match.group(2):
                        multiplier_text = match.group(2).lower()
                        if "juta" in multiplier_text or "million" in multiplier_text:
                            amount *= 1_000_000
                        elif "ribu" in multiplier_text or "thousand" in multiplier_text:
                            amount *= 1_000

                    # Determine currency
                    if "$" in match.group(0) or "USD" in match.group(0):
                        amount *= 15_000  # Convert to IDR (rough estimate)

                    # Extract context (description)
                    # Get ~50 chars before and after match
                    start = max(0, match.start() - 50)
                    end = min(len(text), match.end() + 50)
                    context = text[start:end].strip()

                    # Categorize
                    category = self._categorize_cost(context)

                    # Check if recurring
                    is_recurring = any(
                        keyword in text.lower()
                        for keyword in [
                            "annual",
                            "yearly",
                            "monthly",
                            "recurring",
                            "per year",
                            "per month",
                        ]
                    )

                    costs.append(
                        CostItem(
                            category=category,
                            description=context,
                            amount=amount,
                            currency="IDR",
                            source_oracle=source_oracle,
                            is_recurring=is_recurring,
                        )
                    )

                except (ValueError, IndexError) as e:
                    logger.debug(f"Could not parse cost: {match.group(0)} - {e}")
                    continue

        return costs

    def _categorize_cost(self, text: str) -> str:
        """Categorize a cost based on keywords in description"""
        text_lower = text.lower()

        for category, keywords in self.COST_CATEGORIES.items():
            if any(kw in text_lower for kw in keywords):
                return category.title()

        return "Other"

    async def calculate_pricing(self, scenario: str, user_level: int = 3) -> PricingResult:
        """
        Calculate comprehensive pricing for a scenario.

        Args:
            scenario: Business scenario (e.g., "PT PMA Restaurant in Seminyak")
            user_level: User access level

        Returns:
            PricingResult with detailed cost breakdown
        """
        self.pricing_stats["total_calculations"] += 1

        logger.info(f"💰 Calculating pricing for scenario: '{scenario}'")

        # Step 1: Use Cross-Oracle Synthesis to get all relevant info
        synthesis_result = await self.synthesis.synthesize(
            query=scenario,
            user_level=user_level,
            use_cache=False,  # Don't use cache for pricing (need fresh data)
        )

        # Step 2: Extract costs from all Oracle results
        all_costs = []

        for oracle_name, oracle_data in synthesis_result.sources.items():
            if not oracle_data.get("success"):
                continue

            for result in oracle_data.get("results", []):
                text = result.get("text", "")
                extracted_costs = self.extract_costs_from_text(text, oracle_name)
                all_costs.extend(extracted_costs)

        # Step 3: Also query bali_zero_pricing directly
        pricing_results = await self.search.search(
            query=scenario, user_level=user_level, limit=5, collection_override="bali_zero_pricing"
        )

        for result in pricing_results.get("results", []):
            text = result.get("text", "")
            extracted_costs = self.extract_costs_from_text(text, "bali_zero_pricing")
            all_costs.extend(extracted_costs)

        logger.info(f"   Extracted {len(all_costs)} cost items from Oracles")

        # Step 4: Deduplicate and aggregate
        setup_costs = [c for c in all_costs if not c.is_recurring]
        recurring_costs = [c for c in all_costs if c.is_recurring]

        total_setup = sum(c.amount for c in setup_costs)
        total_recurring = sum(c.amount for c in recurring_costs)

        # Step 5: Calculate breakdown by category
        breakdown = {}
        for cost in all_costs:
            breakdown[cost.category] = breakdown.get(cost.category, 0.0) + cost.amount

        # Step 6: Extract timeline from synthesis
        timeline = synthesis_result.timeline or "4-6 months (estimated)"

        # Step 7: Generate key assumptions
        assumptions = [
            f"Consulted {len(synthesis_result.oracles_consulted)} Oracle collections",
            f"Based on {len(all_costs)} cost data points",
            "Costs are estimates and subject to change",
            "Exchange rate: 1 USD = 15,000 IDR (if applicable)",
        ]

        if synthesis_result.risks:
            assumptions.append(f"Identified {len(synthesis_result.risks)} potential risks")

        # Step 8: Calculate confidence
        # Base on: number of cost items, Oracle coverage, synthesis confidence
        confidence = min(
            synthesis_result.confidence * 0.4  # Scenario classification
            + (len(all_costs) / 10) * 0.3  # Cost item coverage
            + (len(synthesis_result.oracles_consulted) / 6) * 0.3,  # Oracle coverage
            1.0,
        )

        result = PricingResult(
            scenario=scenario,
            total_setup_cost=total_setup,
            total_recurring_cost=total_recurring,
            currency="IDR",
            cost_items=all_costs,
            timeline_estimate=timeline,
            breakdown_by_category=breakdown,
            key_assumptions=assumptions,
            confidence=confidence,
        )

        # Update stats
        self.pricing_stats["avg_total_cost"] = (
            self.pricing_stats["avg_total_cost"] * (self.pricing_stats["total_calculations"] - 1)
            + total_setup
        ) / self.pricing_stats["total_calculations"]

        scenario_type = synthesis_result.scenario_type
        self.pricing_stats["scenarios_priced"][scenario_type] = (
            self.pricing_stats["scenarios_priced"].get(scenario_type, 0) + 1
        )

        logger.info(
            f"✅ Pricing calculated: Setup=Rp {total_setup:,.0f}, "
            f"Recurring=Rp {total_recurring:,.0f}/year, "
            f"Confidence={confidence:.2f}"
        )

        return result

    def format_pricing_report(self, pricing_result: PricingResult, format: str = "text") -> str:
        """
        Generate formatted pricing report.

        Args:
            pricing_result: PricingResult to format
            format: "text" or "markdown"

        Returns:
            Formatted report string
        """
        if format == "markdown":
            return self._format_markdown_report(pricing_result)
        else:
            return self._format_text_report(pricing_result)

    def _format_text_report(self, pr: PricingResult) -> str:
        """Generate plain text pricing report"""
        lines = []
        lines.append("=" * 80)
        lines.append("DYNAMIC PRICING REPORT")
        lines.append("=" * 80)
        lines.append(f"Scenario: {pr.scenario}")
        lines.append(f"Timeline: {pr.timeline_estimate}")
        lines.append(f"Confidence: {pr.confidence * 100:.0f}%")
        lines.append("")

        lines.append("TOTAL INVESTMENT")
        lines.append("-" * 80)
        lines.append(f"Setup Costs (One-time): Rp {pr.total_setup_cost:,.0f}")
        if pr.total_recurring_cost > 0:
            lines.append(f"Recurring Costs (Annual): Rp {pr.total_recurring_cost:,.0f}")
        lines.append("")

        lines.append("BREAKDOWN BY CATEGORY")
        lines.append("-" * 80)
        for category in sorted(pr.breakdown_by_category.keys()):
            amount = pr.breakdown_by_category[category]
            percentage = (amount / pr.total_setup_cost * 100) if pr.total_setup_cost > 0 else 0
            lines.append(f"  {category:20} Rp {amount:>15,.0f}  ({percentage:>5.1f}%)")
        lines.append("")

        lines.append("DETAILED COST ITEMS")
        lines.append("-" * 80)
        for category in sorted({c.category for c in pr.cost_items}):
            cat_costs = [c for c in pr.cost_items if c.category == category]
            lines.append(f"\n{category}:")
            for cost in cat_costs:
                recur_tag = " [RECURRING]" if cost.is_recurring else ""
                lines.append(f"  • Rp {cost.amount:>12,.0f}{recur_tag} - {cost.description[:80]}")
        lines.append("")

        lines.append("KEY ASSUMPTIONS")
        lines.append("-" * 80)
        for assumption in pr.key_assumptions:
            lines.append(f"  • {assumption}")
        lines.append("")

        lines.append("=" * 80)

        return "\n".join(lines)

    def _format_markdown_report(self, pr: PricingResult) -> str:
        """Generate markdown pricing report"""
        # Similar to text but with markdown formatting
        return self._format_text_report(pr)  # Simplified for now

    def get_pricing_stats(self) -> dict:
        """Get pricing calculation statistics"""
        return {
            **self.pricing_stats,
            "avg_total_cost_formatted": f"Rp {self.pricing_stats['avg_total_cost']:,.0f}",
        }
