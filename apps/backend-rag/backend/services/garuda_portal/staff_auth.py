"""GARUDA VOA — step 8 staff surface: staff session verification.

Two entry points, one underlying resolver.

1. `verify_staff_session(authorization) -> str | None` — wired onto
   `app.state.garuda_staff_session_verifier` and read by
   `garuda_orders_router.py::_require_staff_actor` (today inert — this PR
   is what arms it, per that function's own docstring warning about the
   un-awaited-coroutine landmine). Returns a bare actor STRING (the CRM
   email), matching `_require_staff_actor`'s existing contract exactly:
   `resolve_late_order`'s handler already passes that return value straight
   into `scoped_key_sha256(actor=actor, ...)`, which requires a string, not
   a dict — this function's signature is therefore load-bearing for
   `resolveLateOrder`, not just for this PR's new routes, and must not
   change shape.

2. `require_garuda_staff(request) -> dict | None` — the FastAPI dependency
   THIS PR's own `garuda_staff_router.py` uses, which needs more than a
   bare email (admin-vs-team-member visibility, STEP8-SPEC point 3). It
   resolves the SAME underlying actor via `_resolve_actor` and returns the
   full `{"email": str, "is_admin": bool}` shape. It ALSO accepts the
   browser path first: `request.state.user` (set by `HybridAuthMiddleware`
   from the `kita.balizero.com` cookie session — same attribute
   `deps/auth.py::get_current_user` reads as its own Priority 1) before
   falling back to the bearer verifier, so the SPA and a bare
   `Authorization: Bearer <jwt>` script caller resolve identically
   (STEP8-SPEC point 2: "both resolve to the same actor object").

**Decode duplication, not secret duplication.** `backend/app/deps/auth.py::
get_current_user` has no standalone decode helper to import — its JWT
validation is inline in that function's body, and that function is exercised
by a wide existing test surface this PR does not touch. `_decode_crm_jwt`
below duplicates the SAME validation steps (HS256, `verify_exp` +
`require_exp`, `type` claim check, revocation check) against the SAME
`settings.jwt_secret_key` `get_current_user` reads — it never re-derives or
hardcodes the secret, which is the invariant STEP8-SPEC point 2 actually
protects ("reuse its decode helper, do not copy the secret handling"). A
follow-up PR extracting a genuinely shared decode helper is a clean,
separate refactor of a function this PR's scope does not otherwise touch.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from jose import JWTError, jwt

from backend.app.utils.crm_utils import is_crm_admin
from backend.services.security.token_revocation import (
    RevocationStoreUnavailable,
    is_session_revoked_sync,
)

logger = logging.getLogger(__name__)

__all__ = ["require_garuda_staff", "verify_staff_session"]


def _decode_crm_jwt(token: str) -> dict[str, Any] | None:
    """Same validation steps as `deps/auth.py::get_current_user`'s
    Priority-2 branch, against the same secret. Returns the raw payload
    dict, or `None` for anything invalid/expired/wrong-type/revoked —
    never raises, so callers never need to catch a decode-specific
    exception on top of the auth-service-unavailable case below.
    """
    from backend.app.core.config import settings

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=["HS256"],
            options={"verify_exp": True, "require_exp": True},
        )
    except JWTError:
        return None

    token_type = payload.get("type")
    if token_type is not None and token_type != "access":
        return None
    user_email = payload.get("email") or payload.get("sub")
    if not user_email:
        return None

    try:
        if is_session_revoked_sync(payload):
            logger.warning("garuda_staff_auth.revoked_session_rejected")
            return None
    except RevocationStoreUnavailable:
        # Fail closed: an unverifiable revocation state must never be
        # treated as "not revoked" on a staff-write surface.
        logger.error("garuda_staff_auth.revocation_check_unavailable")
        return None

    return payload


def _actor_from_email_and_role(email: str, role: str) -> dict[str, Any] | None:
    """PR-13-shaped gate for STEP8-SPEC: only a CRM admin or CRM team-role
    holder is a staff actor — anyone else resolves to `None`, the same
    shape an unrecognized token gets, per `_require_staff_actor`'s own "no
    caller wired yet, never a silent bypass" contract.

    There is no third, unauthenticated CRM identity shape here: every valid
    CRM JWT / cookie session already carries `email` + `role`
    (`get_current_user`'s own return dict), and `crm_utils.is_crm_admin`
    is the SAME admin test `deps/crm_access.py::require_crm_admin` and
    `get_practices_user_filter` already use — a non-admin authenticated CRM
    identity is a plain team member, exactly the actor `assigned_to`
    filtering exists to scope.
    """
    email = (email or "").strip()
    if not email:
        return None
    return {"email": email.lower(), "is_admin": is_crm_admin({"email": email, "role": role})}


async def _resolve_actor(authorization: str) -> dict[str, Any] | None:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    payload = _decode_crm_jwt(token)
    if payload is None:
        return None
    return _actor_from_email_and_role(
        payload.get("email") or payload.get("sub") or "", payload.get("role", "user")
    )


async def verify_staff_session(authorization: str) -> str | None:
    """Bearer-token staff verifier — the `StaffSession` contract shape AND
    `_require_staff_actor`'s existing string-actor contract (see module
    docstring point 1). `authorization` is the raw header VALUE (e.g.
    `"Bearer <jwt>"`), matching `_require_staff_actor`'s own call site.
    """
    actor = await _resolve_actor(authorization)
    return actor["email"] if actor is not None else None


async def require_garuda_staff(request: Request) -> dict[str, Any] | None:
    """FastAPI dependency for `garuda_staff_router.py` — see module
    docstring point 2. Returns `None` rather than raising so the router's
    own `_ContractErrorRoute` (STEP8-SPEC: "reuse the L3 error-envelope
    helpers") stays the single place that turns "no actor" into the
    contract's `SESSION_REQUIRED` body; callers must check for `None`.
    """
    user = getattr(request.state, "user", None)
    if user:
        actor = _actor_from_email_and_role(user.get("email") or "", user.get("role", "user"))
        if actor is not None:
            return actor

    authorization = request.headers.get("authorization")
    if authorization:
        actor = await _resolve_actor(authorization)
        if actor is not None:
            return actor

    return None
