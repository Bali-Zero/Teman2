"""
Session Management API Router
Exposes SessionService functionality via REST API endpoints
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from services.session_service import SessionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

# Global service instance
_session_service: Optional[SessionService] = None


def get_session_service() -> SessionService:
    """Get or create SessionService instance"""
    global _session_service
    if _session_service is None:
        redis_url = getattr(settings, "redis_url", "redis://localhost:6379")
        _session_service = SessionService(redis_url)
    return _session_service


class SessionHistoryRequest(BaseModel):
    """Request model for updating session history"""

    history: list[dict] = Field(..., description="Conversation history")


class SessionUpdateRequest(BaseModel):
    """Request model for updating session with custom TTL"""

    history: list[dict] = Field(..., description="Conversation history")
    ttl_hours: Optional[int] = Field(None, description="Custom TTL in hours")


class SessionTTLRequest(BaseModel):
    """Request model for extending session TTL"""

    ttl_hours: int = Field(..., description="New TTL in hours")


@router.post("/create")
async def create_session(service: SessionService = Depends(get_session_service)):
    """Create a new conversation session"""
    try:
        session_id = await service.create_session()
        return {"success": True, "session_id": session_id}
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}")
async def get_session(session_id: str, service: SessionService = Depends(get_session_service)):
    """Get conversation history for a session"""
    try:
        history = await service.get_history(session_id)
        if history is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"success": True, "session_id": session_id, "history": history}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{session_id}")
async def update_session(
    session_id: str,
    request: SessionHistoryRequest,
    service: SessionService = Depends(get_session_service),
):
    """Update conversation history for a session"""
    try:
        success = await service.update_history(session_id, request.history)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to update session")
        return {"success": True, "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{session_id}/ttl")
async def update_session_with_ttl(
    session_id: str,
    request: SessionUpdateRequest,
    service: SessionService = Depends(get_session_service),
):
    """Update session with custom TTL"""
    try:
        success = await service.update_history_with_ttl(
            session_id, request.history, request.ttl_hours
        )
        if not success:
            raise HTTPException(status_code=400, detail="Failed to update session")
        return {"success": True, "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{session_id}")
async def delete_session(session_id: str, service: SessionService = Depends(get_session_service)):
    """Delete a session"""
    try:
        success = await service.delete_session(session_id)
        return {"success": success, "session_id": session_id}
    except Exception as e:
        logger.error(f"Failed to delete session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/extend")
async def extend_session_ttl(
    session_id: str,
    service: SessionService = Depends(get_session_service),
):
    """Extend session TTL"""
    try:
        success = await service.extend_ttl(session_id)
        return {"success": success, "session_id": session_id}
    except Exception as e:
        logger.error(f"Failed to extend TTL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/extend-custom")
async def extend_session_ttl_custom(
    session_id: str,
    request: SessionTTLRequest,
    service: SessionService = Depends(get_session_service),
):
    """Extend session TTL to custom duration"""
    try:
        success = await service.extend_ttl_custom(session_id, request.ttl_hours)
        return {"success": success, "session_id": session_id}
    except Exception as e:
        logger.error(f"Failed to extend TTL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/info")
async def get_session_info(session_id: str, service: SessionService = Depends(get_session_service)):
    """Get session metadata"""
    try:
        info = await service.get_session_info(session_id)
        if info is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"success": True, "info": info}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/export")
async def export_session(
    session_id: str,
    format: str = "json",
    service: SessionService = Depends(get_session_service),
):
    """Export session conversation"""
    try:
        exported = await service.export_session(session_id, format)
        if exported is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"success": True, "session_id": session_id, "format": format, "data": exported}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/overview")
async def get_analytics(service: SessionService = Depends(get_session_service)):
    """Get analytics about all sessions"""
    try:
        analytics = await service.get_analytics()
        return {"success": True, "analytics": analytics}
    except Exception as e:
        logger.error(f"Failed to get analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup")
async def cleanup_sessions(service: SessionService = Depends(get_session_service)):
    """Cleanup expired sessions (no-op, Redis handles automatically)"""
    try:
        cleaned = await service.cleanup_expired_sessions()
        return {"success": True, "cleaned": cleaned}
    except Exception as e:
        logger.error(f"Failed to cleanup sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check(service: SessionService = Depends(get_session_service)):
    """Health check for session service"""
    try:
        healthy = await service.health_check()
        return {"success": healthy, "service": "session"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"success": False, "service": "session", "error": str(e)}
