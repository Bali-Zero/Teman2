"""Admin endpoint: Pro/Air cron agents POST LLM cost events.

Relays to backend.services.observability.record_llm_call, which performs
the triple-write (Prometheus + Postgres + JSONL). See the LLM Cost Tracking
v2 design for the recorder architecture.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.app.dependencies import get_current_user_email, get_database
from backend.services.observability import record_llm_call

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin/llm-costs",
    tags=["observability", "admin"],
)


async def require_admin(
    email: Annotated[str, Depends(get_current_user_email)],
    request: Request,
) -> str:
    """Verify the current user is an admin or founder.

    Mirrors the pattern used in messaging_identity.py — queries team_access
    joined to user_profiles to get the role.

    Args:
        email: User email from JWT.
        request: FastAPI request (carries DB pool).

    Returns:
        User email if authorized.

    Raises:
        HTTPException 403: If user is not an admin or founder.
        HTTPException 500: On unexpected DB error.
    """
    db_pool = get_database(request)

    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT ta.role
                FROM team_access ta
                JOIN user_profiles up ON up.id = ta.user_id
                WHERE up.email = $1
                """,
                email,
            )

        if not row or row["role"] not in ("admin", "founder"):
            raise HTTPException(
                status_code=403,
                detail="Only admins and founders can record LLM cost events",
            )

        return email

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error checking admin role for llm-costs: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error") from exc


class LLMCostRecord(BaseModel):
    """Payload for a single LLM call cost event."""

    provider: str = Field(..., max_length=32)
    model: str = Field(..., max_length=128)
    input_tokens: int = Field(..., ge=0)
    output_tokens: int = Field(..., ge=0)
    cost_usd: float = Field(..., ge=0.0)
    success: bool
    latency_ms: int = Field(..., ge=0)
    endpoint: str | None = Field(default=None, max_length=128)
    request_id: str | None = Field(default=None, max_length=64)
    error_class: str | None = Field(default=None, max_length=64)
    cache_hit_tokens: int = Field(default=0, ge=0)


@router.post("/record", status_code=status.HTTP_200_OK)
async def record_remote(
    event: LLMCostRecord,
    _admin: Annotated[str, Depends(require_admin)],
) -> dict:
    """Relay a cost event emitted by a remote agent (Pro/Air cron).

    Accepts the full LLMCostRecord payload and delegates to the singleton
    recorder's triple-write path (Prometheus counter, Postgres insert, JSONL
    append). Returns the write-result dict from record_llm_call.
    """
    return await record_llm_call(**event.model_dump())
