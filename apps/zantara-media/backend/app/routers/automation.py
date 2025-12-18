"""
ZANTARA MEDIA - Automation Endpoints
API endpoints for managing automated content generation
"""

import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any

from app.services.scheduler import scheduler_service

logger = logging.getLogger(__name__)

router = APIRouter()


class AutomationStatus(BaseModel):
    """Automation status response."""

    running: bool
    jobs: list


class ManualTriggerResponse(BaseModel):
    """Manual trigger response."""

    success: bool
    message: str
    stats: Dict[str, Any] = {}


@router.get("/status", response_model=AutomationStatus)
async def get_automation_status():
    """
    Get automation scheduler status.

    Returns information about scheduled jobs and their next run times.
    """
    status = scheduler_service.get_status()
    return AutomationStatus(**status)


@router.post("/trigger", response_model=ManualTriggerResponse)
async def trigger_manual_run(background_tasks: BackgroundTasks):
    """
    Manually trigger the daily content generation pipeline.

    This is useful for:
    - Testing the pipeline
    - Generating content on-demand
    - Running missed scheduled jobs

    The pipeline runs in the background and this endpoint returns immediately.
    """
    logger.info("Manual pipeline trigger requested via API")

    # Run in background to avoid timeout
    background_tasks.add_task(_run_pipeline_background)

    return ManualTriggerResponse(
        success=True,
        message="Pipeline triggered successfully. Check logs for progress.",
        stats={},
    )


@router.post("/trigger-sync")
async def trigger_manual_run_sync():
    """
    Manually trigger the pipeline and wait for completion.

    Warning: This can take several minutes. Use the /trigger endpoint
    for long-running operations.
    """
    logger.info("Synchronous manual pipeline trigger requested via API")

    result = await scheduler_service.trigger_manual_run()

    if not result["success"]:
        raise HTTPException(
            status_code=500, detail=result.get("error", "Pipeline failed")
        )

    return {
        "success": True,
        "message": "Pipeline completed successfully",
        "stats": result["stats"],
    }


async def _run_pipeline_background():
    """Run pipeline in background."""
    try:
        result = await scheduler_service.trigger_manual_run()
        if result["success"]:
            logger.info("Background pipeline completed successfully")
        else:
            logger.error(f"Background pipeline failed: {result.get('error')}")
    except Exception as e:
        logger.error(f"Background pipeline exception: {e}", exc_info=True)


@router.post("/start")
async def start_scheduler():
    """
    Start the automation scheduler.

    This is typically called automatically on application startup,
    but can be triggered manually if needed.
    """
    try:
        await scheduler_service.start()
        return {
            "success": True,
            "message": "Scheduler started successfully",
        }
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_scheduler():
    """
    Stop the automation scheduler.

    Useful for maintenance or testing.
    """
    try:
        await scheduler_service.stop()
        return {
            "success": True,
            "message": "Scheduler stopped successfully",
        }
    except Exception as e:
        logger.error(f"Failed to stop scheduler: {e}")
        raise HTTPException(status_code=500, detail=str(e))
