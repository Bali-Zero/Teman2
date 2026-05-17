"""
Pipeline trigger router.

Exposes endpoints to trigger the intel scraping pipeline remotely.
Used by the nuzantara-rag autonomous scheduler to wake up and run
the bali-intel-scraper daily.
"""

import logging
import os
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, status
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

# In-memory job tracker (reset on restart, but that's fine for this use case)
_jobs: dict[str, dict[str, Any]] = {}


class PipelineRunRequest(BaseModel):
    mode: str = "full"  # "full" | "rss_only"
    max_articles: int = 50
    min_score: int = 40
    auto_approve_threshold: int = 75
    require_approval: bool = False
    dry_run: bool = False


def _verify_trigger_key(x_api_key: str | None) -> None:
    """Verify the trigger API key. Accepts the same SCRAPER_API_KEY used for submit."""
    allowed = {
        k.strip()
        for k in os.getenv("SCRAPER_API_KEY", "internal-scraper-key").split(",")
        if k.strip()
    }
    if not x_api_key or x_api_key not in allowed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid X-API-Key required",
        )


async def _run_pipeline_job(job_id: str, req: PipelineRunRequest) -> None:
    """Run the full intel pipeline in background."""
    _jobs[job_id]["status"] = "running"
    _jobs[job_id]["started_at"] = datetime.utcnow().isoformat()

    try:
        import sys

        scripts_dir = os.path.join(os.path.dirname(__file__), "../../../../scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)

        from rss_fetcher import GoogleNewsRSSFetcher  # type: ignore
        from intel_pipeline import IntelPipeline  # type: ignore

        _jobs[job_id]["stage"] = "fetching_rss"
        logger.info(f"[{job_id}] Fetching Google News RSS...")
        fetcher = GoogleNewsRSSFetcher(max_age_days=7)
        raw_articles: list = []
        for query, category in fetcher.TOPICS:
            articles = await fetcher.fetch_topic(query, category)
            raw_articles.extend(articles)
        logger.info(f"[{job_id}] Fetched {len(raw_articles)} raw articles")

        _jobs[job_id]["stage"] = "processing"
        pipeline = IntelPipeline(
            min_llama_score=req.min_score,
            auto_approve_threshold=req.auto_approve_threshold,
            generate_images=False,  # Skip images for speed in automated runs
            require_approval=req.require_approval,
            dry_run=req.dry_run,
        )

        # Limit articles
        raw_articles = raw_articles[: req.max_articles]
        processed, stats = await pipeline.process_batch(raw_articles)

        _jobs[job_id].update(
            {
                "status": "completed",
                "completed_at": datetime.utcnow().isoformat(),
                "stage": "done",
                "results": {
                    "total_fetched": len(raw_articles),
                    "published": getattr(stats, "published", 0),
                    "enriched": getattr(stats, "enriched", 0),
                    "errors": getattr(stats, "errors", 0),
                },
            }
        )
        logger.info(
            f"[{job_id}] Pipeline done — published={getattr(stats, 'published', 0)}"
        )

    except Exception as e:
        logger.error(f"[{job_id}] Pipeline failed: {e}", exc_info=True)
        _jobs[job_id].update(
            {
                "status": "failed",
                "completed_at": datetime.utcnow().isoformat(),
                "error": str(e),
            }
        )


@router.post("/run")
async def trigger_pipeline(
    req: PipelineRunRequest,
    background_tasks: BackgroundTasks,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> dict[str, Any]:
    """
    Trigger the full intel scraping pipeline.

    Called daily by nuzantara-rag autonomous scheduler.
    Requires X-API-Key header matching SCRAPER_API_KEY env var.
    """
    _verify_trigger_key(x_api_key)

    job_id = f"pipeline_{uuid.uuid4().hex[:8]}"
    _jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "stage": "queued",
        "started_at": None,
        "completed_at": None,
        "results": None,
        "error": None,
        "created_at": datetime.utcnow().isoformat(),
    }

    background_tasks.add_task(_run_pipeline_job, job_id, req)
    logger.info(f"Pipeline job queued: {job_id}")

    return {
        "success": True,
        "job_id": job_id,
        "status": "pending",
        "status_url": f"/api/pipeline/jobs/{job_id}",
    }


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> dict[str, Any]:
    """Get the status of a pipeline job."""
    _verify_trigger_key(x_api_key)
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return _jobs[job_id]


@router.get("/status")
async def pipeline_status(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> dict[str, Any]:
    """Get status of all recent pipeline jobs."""
    _verify_trigger_key(x_api_key)
    recent = sorted(_jobs.values(), key=lambda j: j.get("created_at", ""), reverse=True)[:10]
    return {"jobs": recent, "total": len(_jobs)}
