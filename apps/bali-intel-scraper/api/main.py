"""
BALI INTEL SCRAPER - REST API Server
FastAPI server that wraps the scraping orchestrator
"""

import logging
import os
import sys
from datetime import datetime
from typing import Optional, List
from pathlib import Path

from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add scripts directory to path
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from orchestrator import (
    run_stage1_scraping,
    run_stage2_generation,
    run_stage3_upload,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Bali Intel Scraper API",
    description="REST API for 630+ Indonesian source scraping and AI article generation",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job tracking (replace with database in production)
jobs = {}
job_counter = 0


# ============================================================================
# MODELS
# ============================================================================


class ScrapeRequest(BaseModel):
    """Request to trigger scraping."""

    categories: Optional[List[str]] = None
    limit: int = 10
    generate_articles: bool = True
    upload_to_vector_db: bool = False
    max_articles: int = 100


class JobStatus(BaseModel):
    """Job status response."""

    job_id: str
    status: str  # pending, running, completed, failed
    stage: str  # scraping, generating, uploading
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    results: Optional[dict] = None
    error: Optional[str] = None


class Signal(BaseModel):
    """Intelligence signal."""

    id: str
    title: str
    summary: str
    category: str
    source_name: str
    source_url: Optional[str] = None
    source_tier: str
    priority: int
    confidence_score: float
    tags: List[str]
    created_at: str
    processed: bool = False


# ============================================================================
# HEALTH CHECK
# ============================================================================


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Bali Intel Scraper API",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


# ============================================================================
# SCRAPING ENDPOINTS
# ============================================================================


@app.post("/api/v1/scrape/trigger")
async def trigger_scrape(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """
    Trigger a scraping job.

    This runs the 3-stage pipeline:
    1. Scrape sources (630+ sources)
    2. Generate articles with AI (optional)
    3. Upload to vector DB (optional)

    Returns a job ID that can be used to check status.
    """
    global job_counter, jobs

    job_counter += 1
    job_id = f"job_{job_counter}"

    jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "stage": "scraping",
        "started_at": None,
        "completed_at": None,
        "results": None,
        "error": None,
    }

    # Run in background
    background_tasks.add_task(
        _run_scrape_job,
        job_id,
        request.categories,
        request.limit,
        request.generate_articles,
        request.upload_to_vector_db,
        request.max_articles,
    )

    logger.info(f"Scraping job triggered: {job_id}")

    return {
        "success": True,
        "job_id": job_id,
        "message": "Scraping job started",
        "status_url": f"/api/v1/scrape/jobs/{job_id}",
    }


@app.get("/api/v1/scrape/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get status of a scraping job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatus(**jobs[job_id])


@app.get("/api/v1/scrape/jobs")
async def list_jobs(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100),
):
    """List recent scraping jobs."""
    job_list = list(jobs.values())

    if status:
        job_list = [j for j in job_list if j["status"] == status]

    # Sort by started_at descending
    job_list.sort(key=lambda x: x.get("started_at") or "", reverse=True)

    return {"total": len(job_list), "jobs": job_list[:limit]}


async def _run_scrape_job(
    job_id: str,
    categories: Optional[List[str]],
    limit: int,
    generate_articles: bool,
    upload_to_vector_db: bool,
    max_articles: int,
):
    """Run the scraping job in background."""
    try:
        jobs[job_id]["status"] = "running"
        jobs[job_id]["started_at"] = datetime.utcnow().isoformat()

        results = {}

        # Stage 1: Scraping
        logger.info(f"[{job_id}] Starting Stage 1: Scraping")
        jobs[job_id]["stage"] = "scraping"

        scrape_results = run_stage1_scraping(categories=categories, limit=limit)
        results["scraping"] = scrape_results
        logger.info(
            f"[{job_id}] Stage 1 complete: {scrape_results.get('total_scraped', 0)} items"
        )

        # Stage 2: AI Generation
        if generate_articles:
            logger.info(f"[{job_id}] Starting Stage 2: AI Generation")
            jobs[job_id]["stage"] = "generating"

            gen_results = run_stage2_generation(
                categories=categories, max_articles=max_articles
            )
            results["generation"] = gen_results
            logger.info(
                f"[{job_id}] Stage 2 complete: {gen_results.get('processed', 0)} articles"
            )

        # Stage 3: Vector DB Upload
        if upload_to_vector_db:
            logger.info(f"[{job_id}] Starting Stage 3: Vector DB Upload")
            jobs[job_id]["stage"] = "uploading"

            upload_results = run_stage3_upload(categories=categories)
            results["upload"] = upload_results
            logger.info(
                f"[{job_id}] Stage 3 complete: {upload_results.get('uploaded', 0)} documents"
            )

        # Success
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()
        jobs[job_id]["results"] = results
        logger.info(f"[{job_id}] Job completed successfully")

    except Exception as e:
        logger.error(f"[{job_id}] Job failed: {e}", exc_info=True)
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()
        jobs[job_id]["error"] = str(e)


# ============================================================================
# SIGNALS ENDPOINTS
# ============================================================================


@app.get("/api/v1/signals")
async def get_signals(
    category: Optional[str] = Query(None, description="Filter by category"),
    priority_min: int = Query(1, ge=1, le=10, description="Minimum priority"),
    processed: Optional[bool] = Query(None, description="Filter by processed status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    Get intelligence signals from scraped data.

    NOTE: This requires database backend to be implemented.
    For now, returns empty list with instructions.
    """
    # TODO: Implement database query
    # This should query from intel_signals table once database is set up

    return {
        "total": 0,
        "signals": [],
        "message": "Database backend not yet implemented. Run scraping job to generate signals.",
        "note": "Implement PostgreSQL connection to store and retrieve signals persistently.",
    }


@app.post("/api/v1/signals/{signal_id}/process")
async def mark_signal_processed(
    signal_id: str,
    action: str = Query(
        ..., description="Action: content_created, dismissed, archived"
    ),
    content_id: Optional[str] = Query(None, description="Created content ID"),
):
    """
    Mark a signal as processed.

    NOTE: Requires database backend.
    """
    # TODO: Implement database update

    return {
        "success": False,
        "message": "Database backend not yet implemented",
        "note": "This endpoint requires PostgreSQL connection for persistent signal tracking",
    }


# ============================================================================
# SOURCES ENDPOINTS
# ============================================================================


@app.get("/api/v1/sources")
async def list_sources(
    category: Optional[str] = Query(None, description="Filter by category"),
    tier: Optional[str] = Query(None, description="Filter by tier (T1, T2, T3)"),
):
    """
    List configured sources.

    Returns the 630+ sources from configuration.
    """
    # Load from config
    import json
    from pathlib import Path

    config_path = Path(__file__).parent.parent / "config" / "categories.json"

    if not config_path.exists():
        raise HTTPException(status_code=500, detail="Configuration file not found")

    with open(config_path) as f:
        config = json.load(f)

    sources = []
    for cat_key, cat_data in config.get("categories", {}).items():
        if category and cat_key != category:
            continue

        for source in cat_data.get("sources", []):
            if tier and source.get("tier") != tier:
                continue

            sources.append(
                {
                    "name": source.get("name"),
                    "url": source.get("url"),
                    "tier": source.get("tier"),
                    "category": cat_key,
                }
            )

    return {"total": len(sources), "sources": sources}


@app.get("/api/v1/sources/stats")
async def get_source_stats():
    """Get statistics about configured sources."""
    import json
    from pathlib import Path

    config_path = Path(__file__).parent.parent / "config" / "categories.json"

    with open(config_path) as f:
        config = json.load(f)

    total = 0
    by_category = {}
    by_tier = {"T1": 0, "T2": 0, "T3": 0}

    for cat_key, cat_data in config.get("categories", {}).items():
        count = len(cat_data.get("sources", []))
        total += count
        by_category[cat_key] = count

        for source in cat_data.get("sources", []):
            tier = source.get("tier", "unknown")
            if tier in by_tier:
                by_tier[tier] += 1

    return {
        "total_sources": total,
        "by_category": by_category,
        "by_tier": by_tier,
        "categories": len(config.get("categories", {})),
    }


# ============================================================================
# ROOT
# ============================================================================


@app.get("/")
async def root():
    """API information."""
    return {
        "service": "Bali Intel Scraper API",
        "version": "1.0.0",
        "description": "REST API for 630+ Indonesian source scraping",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "scraping": {
                "trigger": "POST /api/v1/scrape/trigger",
                "jobs": "GET /api/v1/scrape/jobs",
                "job_status": "GET /api/v1/scrape/jobs/{job_id}",
            },
            "sources": {
                "list": "GET /api/v1/sources",
                "stats": "GET /api/v1/sources/stats",
            },
            "signals": {
                "list": "GET /api/v1/signals",
                "process": "POST /api/v1/signals/{signal_id}/process",
            },
        },
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8002"))

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
    )
