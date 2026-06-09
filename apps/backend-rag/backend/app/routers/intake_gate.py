"""INTAKE login-gate status probe — GET /api/intake/gate/status.

The workspace layout calls this on every mount (and on route change, F5) to learn
whether the logged-in worker must clear their 3 personal queues before entering
kita. Counts only — no PII rows (spec §3.1). Identity is server-side from the JWT
(`get_current_user`), never the spoofable frontend profile.

The actual count logic lives in the shared evaluator
(`backend.services.intake.gate_evaluator`) so the probe and the enforcement
dependency (`require_gate_cleared`) can never drift (panel fix F4).

PII / Law 2: local Postgres read, integer response only.
"""

from __future__ import annotations

import logging
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.utils.crm_utils import is_crm_admin
from backend.services.intake.gate_evaluator import evaluate_gate_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/intake/gate", tags=["intake", "gate"])


@router.get("/status")
async def get_gate_status(
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, Any]:
    """Per-user clearance state for the workspace login gate.

    Returns (spec §3.1):
        {
          "blocked": bool,
          "sections": {
            "documents": {"count": int, "blocking": true},
            "late_note": {"count": int, "blocking": true},
            "deadlines": {"count": int, "blocking": true}
          },
          "as_of": "<iso8601>",
          "degraded": bool   # true → evaluator failed, failed OPEN (F4)
        }

    Never 5xx on a count bug: the evaluator fails OPEN (blocked=false +
    degraded=true) so a probe error cannot lock the whole company out of kita.
    """
    user_email = (user.get("email") or "").strip()
    result = await evaluate_gate_status(
        pool,
        user_email=user_email,
        is_admin=is_crm_admin(user),
    )
    if result.get("degraded"):
        # Surface for ops; the response itself is non-blocking (fail-OPEN).
        logger.error(
            "gate/status DEGRADED for user=%s — failed OPEN (see evaluator log)",
            user_email,
        )
    return result
