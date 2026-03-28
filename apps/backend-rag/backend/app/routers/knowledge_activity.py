"""
Knowledge Activity Router
Track views and downloads of Knowledge Base content
"""

import logging
from typing import Literal

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app.dependencies import get_current_user, get_database_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge/activity", tags=["knowledge-activity"])


class KnowledgeActivityLog(BaseModel):
    """Request model for logging KB activity"""

    action_type: Literal["view", "download"]
    resource_type: str  # 'visa', 'article', 'document', 'blueprint', etc.
    resource_id: str | None = None
    resource_title: str | None = None
    resource_category: str | None = None


@router.post("/log")
async def log_knowledge_activity(
    activity: KnowledgeActivityLog,
    current_user: dict = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict:
    """Log a knowledge base view or download activity"""
    try:
        user_email = current_user.get("email", "unknown")

        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO knowledge_activity_log
                (user_email, action_type, resource_type, resource_id, resource_title, resource_category)
                VALUES ($1, $2, $3, $4, $5, $6)
            """,
                user_email,
                activity.action_type,
                activity.resource_type,
                activity.resource_id,
                activity.resource_title,
                activity.resource_category,
            )

        logger.info(
            f"KB activity logged: {user_email} {activity.action_type} {activity.resource_type}/{activity.resource_id}",
        )

        return {"success": True, "message": "Activity logged"}

    except Exception as e:
        logger.error(f"Failed to log KB activity: {e}")
        # Don't fail the request - logging is non-critical
        return {"success": False, "message": str(e)}
