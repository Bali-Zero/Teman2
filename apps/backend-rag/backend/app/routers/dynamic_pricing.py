"""
Dynamic Scenario Pricing API

Calculates comprehensive investment costs for Indonesian business scenarios
by aggregating from multiple Oracle collections (KBLI, legal, tax, visa, property).

Example: "PT PMA Restaurant in Seminyak with 2 foreign directors"
→ Returns: setup cost breakdown + annual recurring costs + timeline
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from backend.app.dependencies import get_current_user
from backend.app.middleware.hybrid_auth import OptionalUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pricing", tags=["pricing"])


class ScenarioPricingRequest(BaseModel):
    scenario: str = Field(..., description="Business scenario, e.g. 'PT PMA restaurant Seminyak 2 directors'")
    user_level: int = Field(3, ge=1, le=5, description="User access level")


class ScenarioPricingResponse(BaseModel):
    scenario: str
    total_setup_cost: float
    total_recurring_cost: float
    currency: str
    breakdown_by_category: dict[str, float]
    timeline_estimate: str
    key_assumptions: list[str]
    confidence: float
    cost_items: list[dict[str, Any]]


@router.post("/scenario", response_model=ScenarioPricingResponse)
async def calculate_scenario_pricing(
    request: Request,
    body: ScenarioPricingRequest,
    current_user: OptionalUser = Depends(get_current_user),
) -> ScenarioPricingResponse:
    """
    Calculate comprehensive pricing for a business scenario.

    Aggregates costs from KBLI, legal, tax, visa, and property Oracle collections.
    Uses CrossOracleSynthesisService + bali_zero_pricing_hybrid collection.
    """
    try:
        from backend.services.pricing.dynamic_pricing_service import DynamicPricingService
    except ImportError as e:
        logger.error(f"DynamicPricingService import failed: {e}")
        raise HTTPException(status_code=503, detail="Dynamic pricing service unavailable")

    cross_oracle = getattr(request.app.state, "cross_oracle_synthesis_service", None)
    search_service = getattr(request.app.state, "search_service", None)

    if not cross_oracle or not search_service:
        raise HTTPException(
            status_code=503,
            detail="Pricing dependencies not initialized (CrossOracle or SearchService unavailable)",
        )

    try:
        service = DynamicPricingService(
            cross_oracle_synthesis_service=cross_oracle,
            search_service=search_service,
        )
        result = await service.calculate_pricing(
            scenario=body.scenario,
            user_level=body.user_level,
        )

        return ScenarioPricingResponse(
            scenario=result.scenario,
            total_setup_cost=result.total_setup_cost,
            total_recurring_cost=result.total_recurring_cost,
            currency=result.currency,
            breakdown_by_category=result.breakdown_by_category,
            timeline_estimate=result.timeline_estimate,
            key_assumptions=result.key_assumptions,
            confidence=result.confidence,
            cost_items=[
                {
                    "category": item.category,
                    "description": item.description,
                    "amount": item.amount,
                    "currency": item.currency,
                    "is_recurring": item.is_recurring,
                    "frequency": item.frequency,
                    "source_oracle": item.source_oracle,
                }
                for item in result.cost_items
            ],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Dynamic pricing calculation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Pricing calculation failed")
