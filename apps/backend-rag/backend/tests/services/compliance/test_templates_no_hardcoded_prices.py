"""
Regression: ANNUAL_DEADLINES must not embed government prices.
Prices come from PricingTool only (Golden Rule #12, CLAUDE.md §4).
"""
from __future__ import annotations

from backend.services.compliance.templates import ComplianceTemplatesService


def test_annual_deadlines_have_no_estimated_cost_key() -> None:
    svc = ComplianceTemplatesService()
    for key, tpl in svc.ANNUAL_DEADLINES.items():
        assert "estimated_cost" not in tpl, (
            f"Template {key} has hardcoded 'estimated_cost' — violates PricingTool rule"
        )


def test_annual_deadlines_have_pricing_key_reference() -> None:
    svc = ComplianceTemplatesService()
    for key, tpl in svc.ANNUAL_DEADLINES.items():
        assert "pricing_key" in tpl, (
            f"Template {key} must declare a pricing_key string (for PricingTool lookup) "
            "instead of hardcoded IDR amount"
        )
