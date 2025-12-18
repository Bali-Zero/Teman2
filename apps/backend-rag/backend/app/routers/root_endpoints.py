"""
Root Endpoints Router
Handles root-level endpoints like /, /api/csrf-token, /api/dashboard/stats
"""

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/")
async def root() -> dict[str, str]:
    """Root endpoint - health check"""
    return {"message": "ZANTARA RAG Backend Ready"}


@router.get("/api/csrf-token")
async def get_csrf_token() -> JSONResponse:
    """
    Generate CSRF token and session ID for frontend security.
    Returns token in both JSON body and response headers.
    """
    # Generate CSRF token (32 bytes = 64 hex chars)
    csrf_token = secrets.token_hex(32)

    # Generate session ID
    session_id = (
        f"session_{int(datetime.now(timezone.utc).timestamp() * 1000)}_{secrets.token_hex(16)}"
    )

    # Return in both JSON and headers
    response_data = {"csrfToken": csrf_token, "sessionId": session_id}

    # Create JSON response with headers
    json_response = JSONResponse(content=response_data)
    json_response.headers["X-CSRF-Token"] = csrf_token
    json_response.headers["X-Session-Id"] = session_id

    return json_response


@router.get("/api/dashboard/stats")
async def get_dashboard_stats() -> dict[str, str | dict[str, str]]:
    """
    Provide real-time stats for the Mission Control Dashboard.

    Note: Currently returns mock data. In production, this would query
    the database/orchestrator for real-time statistics.
    """
    return {
        "active_agents": "3",
        "system_health": "99.9%",
        "uptime_status": "ONLINE",
        "knowledge_base": {"vectors": "1.2M", "status": "Indexing..."},
    }
