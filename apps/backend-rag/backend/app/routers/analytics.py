"""
Analytics API Router
Exposes historical analytics endpoints for dashboard consumption.

Endpoints:
- GET /api/analytics/completion-rates
- GET /api/analytics/response-times
- GET /api/analytics/sla-compliance
- GET /api/analytics/revenue
- GET /api/analytics/monthly-report/{year}/{month}
"""

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.dependencies import get_current_user, get_database_pool
from backend.services.analytics.historical_analytics import (
    calculate_completion_rate,
    calculate_response_times,
    calculate_revenue_metrics,
    calculate_sla_compliance,
    generate_monthly_report,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def verify_founder_access(current_user: Any = Depends(get_current_user)) -> Any:
    """
    Verify that the user has founder or admin level access.
    """
    if current_user.get("role") not in ["Founder", "admin"]:
        raise HTTPException(
            status_code=403, detail="Access denied. This dashboard is for founders only."
        )
    return current_user


@router.get("/completion-rates")
async def get_completion_rates(
    practice_type: str | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    db_pool=Depends(get_database_pool),
    current_user=Depends(verify_founder_access),
) -> Any:
    """
    Get practice completion rates.

    - **practice_type**: Filter by practice type code (optional)
    - **start_date**: Start date for analysis period (optional)
    - **end_date**: End date for analysis period (optional)
    """
    try:
        return await calculate_completion_rate(db_pool, practice_type, start_date, end_date)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to calculate completion rates: {str(e)}"
        )


@router.get("/response-times")
async def get_response_times(
    practice_type: str | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    db_pool=Depends(get_database_pool),
    current_user=Depends(verify_founder_access),
) -> Any:
    """
    Get average response times (inquiry to start, start to completion).

    - **practice_type**: Filter by practice type code (optional)
    - **start_date**: Start date for analysis period (optional)
    - **end_date**: End date for analysis period (optional)
    """
    try:
        return await calculate_response_times(db_pool, practice_type, start_date, end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate response times: {str(e)}") from e


@router.get("/sla-compliance")
async def get_sla_compliance(
    practice_type: str | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    db_pool=Depends(get_database_pool),
    current_user=Depends(verify_founder_access),
) -> Any:
    """
    Get SLA compliance rates (practices completed within expected duration).

    - **practice_type**: Filter by practice type code (optional)
    - **start_date**: Start date for analysis period (optional)
    - **end_date**: End date for analysis period (optional)
    """
    try:
        return await calculate_sla_compliance(db_pool, practice_type, start_date, end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate SLA compliance: {str(e)}") from e


@router.get("/revenue")
async def get_revenue_metrics(
    practice_type: str | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    db_pool=Depends(get_database_pool),
    current_user=Depends(verify_founder_access),
) -> Any:
    """
    Get revenue metrics by practice type.

    - **practice_type**: Filter by practice type code (optional)
    - **start_date**: Start date for analysis period (optional)
    - **end_date**: End date for analysis period (optional)
    """
    try:
        return await calculate_revenue_metrics(db_pool, practice_type, start_date, end_date)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to calculate revenue metrics: {str(e)}"
        )


@router.get("/monthly-report/{year}/{month}")
async def get_monthly_report(
    year: int,
    month: int,
    db_pool=Depends(get_database_pool),
    current_user=Depends(verify_founder_access),
) -> Any:
    """
    Generate comprehensive monthly analytics report.

    - **year**: Year (e.g., 2026)
    - **month**: Month (1-12)
    """
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Month must be between 1 and 12")

    if year < 2020 or year > 2100:
        raise HTTPException(status_code=400, detail="Invalid year")

    try:
        return await generate_monthly_report(db_pool, year, month)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate monthly report: {str(e)}") from e
