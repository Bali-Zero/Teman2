"""
Funnel session tracking — cross-funnel lead capture before auth.

Endpoints:
- POST /api/funnel/session/touch   upsert session + update last_touched_at
- POST /api/funnel/session/convert  set converted_to_client_id at SSO login
"""

from __future__ import annotations

import hashlib
import json
import logging
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from backend.app.deps.database import get_database_pool

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/funnel", tags=["funnel"])


class FunnelType(str, Enum):
    VISA = "visa"
    KBLI = "kbli"
    TAX = "tax"
    PROPERTY = "property"
    HOME = "home"


class TouchRequest(BaseModel):
    session_id: str = Field(min_length=32, max_length=64)
    funnel: FunnelType
    step_state: dict[str, Any] = Field(default_factory=dict)
    lead_profile: dict[str, Any] = Field(default_factory=dict)


def _ip_hash(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for") or ""
    client_host = request.client.host if request.client else ""
    ip = (xff.split(",")[0].strip() or client_host).strip()
    return hashlib.sha256(ip.encode()).hexdigest()[:64] if ip else ""


@router.post("/session/touch")
async def touch_session(
    req: TouchRequest,
    request: Request,
    pool=Depends(get_database_pool),
) -> dict[str, bool]:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO funnel_sessions (session_id, funnel, step_state, lead_profile, ip_hash)
            VALUES ($1, $2, $3::jsonb, $4::jsonb, $5)
            ON CONFLICT (session_id) DO UPDATE SET
                funnel = EXCLUDED.funnel,
                step_state = funnel_sessions.step_state || EXCLUDED.step_state,
                lead_profile = funnel_sessions.lead_profile || EXCLUDED.lead_profile,
                last_touched_at = NOW()
            """,
            req.session_id,
            req.funnel.value,
            json.dumps(req.step_state),
            json.dumps(req.lead_profile),
            _ip_hash(request),
        )
    return {"ok": True}


class ConvertRequest(BaseModel):
    session_id: str = Field(min_length=32, max_length=64)
    client_id: str


@router.post("/session/convert")
async def convert_session(
    req: ConvertRequest,
    pool=Depends(get_database_pool),
) -> dict[str, bool]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE funnel_sessions
            SET converted_to_client_id = $2
            WHERE session_id = $1
            RETURNING funnel, first_touched_at
            """,
            req.session_id,
            req.client_id,
        )
        if row:
            await conn.execute(
                """
                INSERT INTO funnel_attributions (client_id, session_id, first_funnel, first_touch_at)
                VALUES ($1, $2, $3, $4)
                """,
                req.client_id,
                req.session_id,
                row["funnel"],
                row["first_touched_at"],
            )
    return {"ok": True}
