"""
LKPM (Investment Activity Report) Router.

Endpoints for generating, validating, and managing quarterly LKPM reports.
All calculations are deterministic — no AI on numbers.
"""

import logging
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.models.lkpm import (
    LKPMClientConfig,
    LKPMClientSubmission,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/lkpm", tags=["lkpm"])


def _get_service(db_pool: asyncpg.Pool) -> Any:
    """Lazy import to avoid circular deps at startup."""
    from backend.services.compliance.lkpm_service import LKPMService

    return LKPMService(db_pool)


# ------------------------------------------------------------------
# Client Config
# ------------------------------------------------------------------


@router.post("/config", response_model=dict)
async def save_client_config(
    config: LKPMClientConfig,
    current_user: str = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Save or update LKPM client configuration (investment plan, Jurnal keys)."""
    service = _get_service(db_pool)
    try:
        config_id = await service.save_client_config(config)
        return {"success": True, "config_id": config_id}
    except Exception as e:
        logger.error(f"Failed to save client config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------
# Data Submission
# ------------------------------------------------------------------


@router.post("/submit-data", response_model=dict)
async def submit_data(
    submission: LKPMClientSubmission,
    current_user: str = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Submit LKPM data via manual form."""
    service = _get_service(db_pool)
    try:
        draft = await service.submit_form_data(submission)
        return {
            "success": True,
            "draft_id": draft.id,
            "quarter": draft.quarter,
            "year": draft.year,
            "realized_total": draft.realized.grand_total,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Form submission failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync-jurnal/{client_id}", response_model=dict)
async def sync_jurnal(
    client_id: int,
    quarter: str,
    year: int,
    current_user: str = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Pull data from Jurnal.id and create/update LKPM draft."""
    service = _get_service(db_pool)
    try:
        draft = await service.sync_jurnal(client_id, quarter, year)
        return {
            "success": True,
            "draft_id": draft.id,
            "realized_total": draft.realized.grand_total,
            "ai_categorized_count": draft.ai_categorized_count,
            "data_source": draft.data_source.value,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Jurnal sync failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------
# Draft Management
# ------------------------------------------------------------------


@router.get("/draft/{client_id}/{quarter}", response_model=dict)
async def get_draft(
    client_id: int,
    quarter: str,
    year: int,
    current_user: str = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Get LKPM draft for a client/quarter."""
    service = _get_service(db_pool)
    draft = await service.get_draft(client_id, quarter, year)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    return {"success": True, "draft": draft.model_dump()}


@router.post("/validate/{draft_id}", response_model=dict)
async def validate_draft(
    draft_id: int,
    current_user: str = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Validate an LKPM draft."""
    service = _get_service(db_pool)
    try:
        result = await service.validate_draft(draft_id)
        return {
            "success": True,
            "is_valid": result.is_valid,
            "red_count": result.red_count,
            "yellow_count": result.yellow_count,
            "green_count": result.green_count,
            "alerts": [a.model_dump() for a in result.alerts],
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Validation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------
# Ready Pack
# ------------------------------------------------------------------


@router.get("/ready-pack/{draft_id}", response_model=dict)
async def get_ready_pack(
    draft_id: int,
    current_user: str = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Generate Ready Pack for OSS copy-paste."""
    service = _get_service(db_pool)
    try:
        pack = await service.get_ready_pack(draft_id)

        # Generate HTML
        from backend.services.compliance.lkpm_ready_pack import generate_ready_pack_html

        html = generate_ready_pack_html(pack)
        pack.html_content = html

        return {
            "success": True,
            "ready_pack": pack.model_dump(),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Ready pack generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------
# Approval & Submission
# ------------------------------------------------------------------


@router.post("/approve/{draft_id}", response_model=dict)
async def approve_draft(
    draft_id: int,
    current_user: str = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Client approves LKPM draft."""
    service = _get_service(db_pool)
    try:
        return await service.approve_draft(draft_id)
    except Exception as e:
        logger.error(f"Approval failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mark-submitted/{draft_id}", response_model=dict)
async def mark_submitted(
    draft_id: int,
    submitted_by: str | None = None,
    current_user: str = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Team marks LKPM as submitted to OSS."""
    service = _get_service(db_pool)
    try:
        return await service.mark_submitted(draft_id, submitted_by or current_user)
    except Exception as e:
        logger.error(f"Mark submitted failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-receipt/{draft_id}", response_model=dict)
async def upload_receipt(
    draft_id: int,
    receipt_number: str,
    receipt_file_url: str | None = None,
    current_user: str = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Upload OSS receipt for a submitted LKPM."""
    service = _get_service(db_pool)
    try:
        return await service.upload_receipt(draft_id, receipt_number, receipt_file_url)
    except Exception as e:
        logger.error(f"Receipt upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------
# Portal: Shareholder History
# ------------------------------------------------------------------


@router.get("/history/me", response_model=dict)
async def get_my_history(
    request: Request,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Get LKPM reports for the authenticated portal client (all shareholder companies)."""
    from backend.app.routers.portal import get_current_client

    client = await get_current_client(request, db_pool)
    service = _get_service(db_pool)
    try:
        items = await service.get_history_for_portal_client(client["client_id"])
        return {
            "success": True,
            "client_id": client["client_id"],
            "count": len(items),
            "items": [item.model_dump() for item in items],
        }
    except Exception as e:
        logger.error(f"Failed to get LKPM history for portal client: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ------------------------------------------------------------------
# Batch & Queries
# ------------------------------------------------------------------


@router.get("/batch/{quarter}", response_model=dict)
async def get_batch(
    quarter: str,
    year: int,
    current_user: str = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Get all LKPM reports for a quarter (team batch view)."""
    service = _get_service(db_pool)
    items = await service.get_batch(quarter, year)
    return {
        "success": True,
        "quarter": quarter,
        "year": year,
        "count": len(items),
        "items": [item.model_dump() for item in items],
    }


@router.get("/alerts", response_model=dict)
async def get_alerts(
    current_user: str = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Get active validation alerts across all clients."""
    service = _get_service(db_pool)
    alerts = await service.get_alerts()
    return {"success": True, "alerts": alerts}


@router.get("/history/{client_id}", response_model=dict)
async def get_history(
    client_id: int,
    current_user: str = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Get LKPM report history for a client."""
    service = _get_service(db_pool)
    items = await service.get_history(client_id)
    return {
        "success": True,
        "client_id": client_id,
        "count": len(items),
        "items": [item.model_dump() for item in items],
    }


@router.get("/deadlines", response_model=dict)
async def get_deadlines(
    days_ahead: int = 30,
    current_user: str = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Get upcoming LKPM deadlines."""
    service = _get_service(db_pool)
    deadlines = service.get_deadlines(days_ahead)
    return {
        "success": True,
        "deadlines": [d.model_dump() for d in deadlines],
    }
