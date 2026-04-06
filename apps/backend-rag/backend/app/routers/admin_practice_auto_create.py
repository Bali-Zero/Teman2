"""
Admin Auto-Practice Creation Router

POST /api/admin/practice/auto-create

Triggers auto-creation of visa renewal practices for visas expiring in ~60 days.
Access: Requires X-API-Key (REDACTED-ROTATED-KEY) or ADMIN_API_KEY.
"""

from fastapi import APIRouter, Depends, Header, HTTPException

from backend.app.core.config import settings
from backend.app.dependencies import get_database_pool
from backend.app.utils.logging_utils import get_logger
from backend.jobs.auto_practice_creator import run_auto_practice_creator

logger = get_logger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin-practice"])


def verify_api_key(
    x_api_key: str | None = Header(default=None, alias="x-api-key", convert_underscores=False),
    x_debug_key: str | None = Header(default=None, alias="x-debug-key", convert_underscores=False),
) -> bool:
    """Verify via X-API-Key or X-Debug-Key."""
    if x_api_key == "REDACTED-ROTATED-KEY":
        return True
    if settings.admin_api_key and x_debug_key == settings.admin_api_key:
        return True
    raise HTTPException(status_code=401, detail="Invalid API key")


@router.post("/practice/auto-create")
async def trigger_auto_practice_creation(
    _: bool = Depends(verify_api_key),
    db_pool=Depends(get_database_pool),
):
    """Trigger auto-creation of renewal practices for expiring visas."""
    logger.info("admin_auto_practice_creation_triggered")
    stats = await run_auto_practice_creator(db_pool)
    return stats
