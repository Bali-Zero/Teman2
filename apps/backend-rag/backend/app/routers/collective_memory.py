"""
Collective Memory API Router
Endpoints for managing shared knowledge across users
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.dependencies import get_database_pool as get_db_pool
from app.routers.auth import get_current_user
from services.collective_memory_service import CollectiveMemoryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/collective-memory", tags=["Collective Memory"])


class ContributeRequest(BaseModel):
    """Request to contribute a fact to collective memory"""

    content: str
    category: str = "general"  # process, location, provider, regulation, tip, pricing


class RefuteRequest(BaseModel):
    """Request to refute a fact"""

    memory_id: int


@router.post("/contribute")
async def contribute_fact(
    request: ContributeRequest,
    current_user: dict = Depends(get_current_user),
    db_pool=Depends(get_db_pool),
):
    """
    Contribute a fact to collective memory.

    When 3+ different users contribute/confirm the same fact,
    it becomes "promoted" and is included in AI context for all users.
    """
    try:
        service = CollectiveMemoryService(pool=db_pool)
        result = await service.add_contribution(
            user_id=current_user["email"],
            content=request.content,
            category=request.category,
        )

        return {"success": True, "message": f"Fact {result['status']}", "data": result}
    except Exception as e:
        logger.error(f"Error contributing to collective memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refute")
async def refute_fact(
    request: RefuteRequest,
    current_user: dict = Depends(get_current_user),
    db_pool=Depends(get_db_pool),
):
    """
    Refute a collective memory fact.

    Decreases confidence. If confidence drops below 0.2, fact is removed.
    """
    try:
        service = CollectiveMemoryService(pool=db_pool)
        result = await service.refute_fact(
            user_id=current_user["email"],
            memory_id=request.memory_id,
        )

        return {"success": True, "message": f"Fact {result['status']}", "data": result}
    except Exception as e:
        logger.error(f"Error refuting fact: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/facts")
async def get_collective_facts(
    category: Optional[str] = None,
    db_pool=Depends(get_db_pool),
):
    """
    Get all promoted collective facts.

    Optional: filter by category.
    """
    try:
        service = CollectiveMemoryService(pool=db_pool)
        facts = await service.get_collective_context(category=category)

        return {"success": True, "facts": facts, "count": len(facts)}
    except Exception as e:
        logger.error(f"Error getting collective facts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_collective_stats(
    db_pool=Depends(get_db_pool),
):
    """
    Get collective memory statistics.
    """
    try:
        service = CollectiveMemoryService(pool=db_pool)
        stats = await service.get_stats()

        return {"success": True, "data": stats}
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
