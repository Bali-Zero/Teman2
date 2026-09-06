"""GET /api/crm/garuda/assignment-targets — the GARUDA assignee picker's source.

The enumeration half of `assignPractice`'s own target gate; see
`services/garuda_portal/assignment_targets.py` for the measured divergence this
closes (the shared CRM roster offers rows the validator refuses, so the staff
dropdown could offer an option whose only outcome was a 422).

**Why this lives under `/api/crm/garuda`, not `/api/visa/voa/staff`.**
`products/garuda-voa/contracts/README.md` freezes that prefix: "A lane never
edits the contract to fit its code. Contract changes go through the
orchestrator." The assignee dropdown has never been part of the frozen surface
— it was fed by the CRM roster (`GET /api/team/members`) — so the GARUDA-filtered
replacement stays on the same side of that boundary and `openapi.yaml` v1.0.0 is
untouched. `test_garuda_voa_openapi_parity.py` keeps pinning the four contract
operations exactly as before.

**Why there is no `GARUDA_PUBLIC_ENABLED` check.** That flag gates the GARUDA
product surface (eligibility funnel, checkout, magic-link auth, staff
practices), and `test_garuda_public_enabled_readers_agree.py` pins its three
readers byte-identical — a fourth local copy here would be a fourth place for
it to drift. Nothing is gained by one: when the flag is off the staff UI that
renders this picker 404s, and the data itself (which colleagues are assignable)
is already visible to the same admin caller through `GET /api/team/members`,
which is not flag-gated either.

Auth is the staff surface's own: `require_garuda_staff` resolves the SAME actor
object from either the `kita.balizero.com` cookie session or a bearer CRM JWT
(never a customer magic-link session), and `is_admin` is the same test
`assign_practice` applies before it accepts an assignment — a non-admin staff
member cannot assign, so a non-admin is not sent the list of people to assign
to. `HybridAuthMiddleware` still rejects a credential-less caller first (this
prefix is not in `public_endpoints.py`); the 401 below is the second line for a
credential that authenticates but is not a GARUDA staff principal (a client or
partner token).

Deliberately NOT the contract error envelope (`{"code","retryable",
"message_key"}` is `garuda_staff_router._error()`'s shape, owned by the frozen
`errors.yaml` catalog): this route is outside that contract, so it uses
FastAPI's plain `detail`, the shape `routers/team.py` — the endpoint this
replaces for this picker — already returns.
"""

from __future__ import annotations

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from backend.app.dependencies import get_database_pool
from backend.services.garuda_portal.assignment_targets import list_garuda_assignment_targets
from backend.services.garuda_portal.staff_auth import require_garuda_staff

router = APIRouter(prefix="/api/crm/garuda", tags=["garuda-assignment"])


def _privacy_headers(response: Response) -> None:
    """Same three headers `garuda_staff_router._privacy_headers` sets: a staff
    roster is a per-caller artifact, never a shared-cache one. A local copy
    rather than an import of that router's private helper (LANES.md
    file-ownership discipline, and importing a `_`-prefixed helper across
    routers is the kind of coupling that breaks silently on a rename)."""
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"


@router.get("/assignment-targets")
async def get_assignment_targets(
    request: Request,
    response: Response,
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> dict[str, list[dict[str, str]]]:
    """`{"items": [{"email", "label"}]}` — every email `assignPractice` accepts.

    Sorted by the roster's own `ORDER BY name`, deduplicated, with ambiguous
    labels disambiguated by the service (see its docstring).
    """
    _privacy_headers(response)

    actor: dict[str, Any] | None = await require_garuda_staff(request)
    if actor is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not actor.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin role required")

    async with pool.acquire() as conn:
        items = await list_garuda_assignment_targets(conn)
    return {"items": items}


__all__ = ["router"]
