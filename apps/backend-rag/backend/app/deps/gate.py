"""`require_gate_cleared` — backend enforcement of the INTAKE login gate.

The frontend gate screen is convenience; THIS dependency is the actual gate
(spec §3.2). A worker who is `blocked` cannot act on workspace business routers
even by hitting the API directly.

Design (binding panel fixes):
- **F1 allowlist**: this guards only the workspace *business* routers it is
  explicitly attached to. The clearing endpoints (gate/status, intake
  claim/approve/reject/release, my-late-incident/resolve, compliance outcome,
  auth/profile, admin-rescue) MUST NOT carry this dependency — else a blocked
  user could never clear and would be locked forever. Enforcement is therefore
  OPT-IN per route (you add `Depends(require_gate_cleared)`), and a defensive
  path-allowlist below short-circuits if it is ever mis-attached to a clearing
  route.
- **F4 fail-OPEN**: the shared evaluator returns `degraded=True` and never
  raises on its own internal error → a probe/DB bug cannot 423-brick the company
  out of kita. Only a *clean* `blocked=True` result raises 423.
- **Q3 mutating-only**: attach this to mutating workspace endpoints
  (POST/PATCH/PUT/DELETE). Reads stay open (smaller blast radius, still prevents
  acting-while-blocked).

Usage on a business router:
    from backend.app.deps.gate import require_gate_cleared

    @router.post("/clients", dependencies=[Depends(require_gate_cleared)])
    async def create_client(...): ...

PII / Law 2: evaluates via the shared local-DB evaluator; raises a status code
only (no PII in the 423 body).
"""

from __future__ import annotations

import logging
from typing import Any

import asyncpg
from fastapi import Depends, HTTPException, Request, status

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.utils.crm_utils import is_crm_admin
from backend.services.intake.gate_evaluator import evaluate_gate_status

logger = logging.getLogger(__name__)

# F1 — path fragments that must NEVER be gated (the clearing endpoints + escapes).
# Defensive: even if a developer mis-attaches the dependency to one of these, it
# short-circuits so the gate can always be cleared.
_ALLOWLIST_FRAGMENTS: tuple[str, ...] = (
    "/api/intake/gate/status",
    "/api/intake/review",          # claim / approve / reject / release
    "/api/hr/my-late-incident",
    "/api/hr/late-reply",
    "/api/compliance/alerts",      # outcome=acknowledged is the clear action
    "/api/auth",
    "/api/profile",
    "/api/health",
)


def _is_allowlisted(path: str) -> bool:
    return any(frag in path for frag in _ALLOWLIST_FRAGMENTS)


async def require_gate_cleared(
    request: Request,
    user: dict[str, Any] = Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> None:
    """Raise HTTP 423 Locked if the user has unresolved gate obligations.

    Allowlisted clearing routes pass through unconditionally (F1). On evaluator
    error the result is degraded → fail-OPEN (F4): we log + allow, never 423 on a
    bug. Only a clean blocked=true raises.
    """
    path = request.url.path
    if _is_allowlisted(path):
        return

    email = (user.get("email") or "").strip()
    result = await evaluate_gate_status(
        pool,
        user_email=email,
        is_admin=is_crm_admin(user),
    )

    if result.get("degraded"):
        # Fail-OPEN: evaluator failed → let them through, ops already alerted by
        # the probe path; do not brick the workspace on a gate bug.
        logger.error(
            "require_gate_cleared: evaluator DEGRADED for user=%s path=%s — "
            "failing OPEN (allowing request)",
            email, path,
        )
        return

    if result.get("blocked"):
        sections = result.get("sections", {})
        counts = {k: v.get("count", 0) for k, v in sections.items()}
        logger.info(
            "require_gate_cleared: BLOCKED user=%s path=%s counts=%s",
            email, path, counts,
        )
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail={
                "error": "gate_blocked",
                "message": "Clear your INTAKE gate before acting in the workspace.",
                "sections": counts,
            },
        )
    # blocked=false → cleared, allow.
