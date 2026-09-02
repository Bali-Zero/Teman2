"""GARUDA VOA — step 8 staff surface: staff session verification.

Two entry points, one shared validator underneath both.

1. `verify_staff_session(authorization) -> str | None` — wired onto
   `app.state.garuda_staff_session_verifier` and read by
   `garuda_orders_router.py::_require_staff_actor` (armed by this PR, per
   that function's own docstring warning about the un-awaited-coroutine
   landmine). Returns a bare actor STRING (the CRM email), matching
   `_require_staff_actor`'s existing contract exactly: `resolve_late_order`'s
   handler already passes that return value straight into
   `scoped_key_sha256(actor=actor, ...)`, which requires a string, not a
   dict — this function's signature is therefore load-bearing for
   `resolveLateOrder`, not just for this PR's new routes, and must not
   change shape.

2. `require_garuda_staff(request) -> dict | None` — the FastAPI dependency
   `garuda_staff_router.py` uses, which needs more than a bare email
   (admin-vs-team-member visibility, STEP8-SPEC point 3). It resolves the
   SAME underlying actor via the shared validator and returns the full
   `{"email": str, "is_admin": bool}` shape. It accepts the browser path
   first: `request.state.user` (set by `HybridAuthMiddleware` from the
   `kita.balizero.com` cookie session — same attribute `deps/auth.py::
   get_current_user` reads as its own Priority 1) before falling back to
   the bearer verifier, so the SPA and a bare `Authorization: Bearer <jwt>`
   script caller resolve identically (STEP8-SPEC point 2: "both resolve to
   the same actor object") — through the SAME `_staff_principal_from_role`
   eligibility check either way (cross-family refuter finding #4:
   previously the cookie path skipped straight to
   `_actor_from_email_and_role` with no `type=access` re-check, since the
   cookie's own JWT was already decoded by the middleware; the eligibility
   half of that check -- role must be a real staff role, never `client` or
   a service account, never missing -- is now identical on both paths, the
   `type=access` half is inherently Bearer-only because a cookie session
   has already been decoded upstream by the time it reaches this module).

**Decode duplication, not secret duplication.** `backend/app/deps/auth.py::
get_current_user` has no standalone decode helper to import — its JWT
validation is inline in that function's body, and that function is exercised
by a wide existing test surface this PR does not touch. `_decode_staff_jwt`
below is the ONE staff-specific JWT validator (cross-family refuter finding
#5): same steps as `get_current_user` (HS256, `verify_exp` + `require_exp`,
revocation check) against the SAME `settings.jwt_secret_key` it reads — it
never re-derives or hardcodes the secret — but STRICTER on the `type` claim:
`get_current_user` treats a missing `type` claim as backward-compatible
"access" (pre-S03 tokens); this staff validator requires `type == "access"`
literally, rejecting a missing claim too. A staff-write surface is a poor
place to keep a backward-compatibility allowance a customer-read surface
still needs, and this module owns no legacy token population that would
break. A follow-up PR extracting a genuinely shared decode helper (with an
explicit `require_exact_type: bool` parameter) is a clean, separate refactor
of a function this PR's scope does not otherwise touch.

**Garuda magic-link sessions cannot reach this validator at all** (refuter
finding #4's "reject a garuda magic session" clause, verified structurally
rather than by a runtime marker check): `garuda_portal_auth.py`'s customer
session is an opaque bearer secret stored via `magic_link_store.py`, never a
signed JWT, and travels in the separate `garuda_session` cookie — a
different cookie name than `cookie_auth.JWT_COOKIE_NAME`, so
`HybridAuthMiddleware` never decodes it into `request.state.user`. If that
opaque secret is ever presented here as `Authorization: Bearer <secret>`,
`_decode_staff_jwt` raises/returns `None` on the first `jwt.decode` call
(it is not a JWT), before any role check runs — there is no code path by
which a magic-link identity produces a non-`None` return from this module.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from jose import JWTError, jwt

from backend.app.utils.service_accounts import NON_HUMAN_ROLES, normalize_role
from backend.services.security.token_revocation import (
    RevocationStoreUnavailable,
    is_session_revoked_sync,
)

logger = logging.getLogger(__name__)

__all__ = [
    "can_manage_garuda_practices",
    "require_garuda_staff",
    "verify_staff_session",
]

# Admin set for GARUDA practice management specifically (cross-family
# refuter disposition, item 4+5+6): the global admin allowlist plus Asya,
# deliberately NARROWER than `crm_utils.is_crm_admin` -- that helper also
# treats `PRACTICES_EXTRA_VIEW_EMAILS` (the accounting full-view role,
# `ruslana@balizero.com`) as admin, which is correct for READ visibility
# but wrong for WRITE authority: an accounting reconciliation viewer must
# never be able to assign a practice or force a transition. Kept as a
# frozenset literal (not a re-export of `crm_utils.CRM_EXTRA_ADMIN_EMAILS`,
# which also includes `admin@balizero.com`/`admin@zantara.io` -- a wider
# set the disposition did not name) so this module's admin boundary is
# readable in one place without cross-referencing crm_utils's own unrelated
# admin unions.
_GARUDA_PRACTICE_ADMIN_EXTRA_EMAILS: frozenset[str] = frozenset({"asya@balizero.com"})


def _garuda_practice_admin_emails() -> frozenset[str]:
    """Global admin allowlist (tolerating a MagicMock `settings` in legacy
    tests, same defensive pattern as `crm_utils._settings_admin_emails`)
    plus this module's own narrower extra-admin set.
    """
    from backend.app.core.config import settings

    raw = getattr(settings, "admin_emails_set", frozenset())
    if isinstance(raw, frozenset):
        base = raw
    elif isinstance(raw, set | list | tuple):
        base = frozenset(str(email).lower().strip() for email in raw)
    else:
        base = frozenset()
    return base | _GARUDA_PRACTICE_ADMIN_EXTRA_EMAILS


def _is_staff_role(role: str | None) -> bool:
    """True iff `role` names a real person on the team -- never a client,
    never a service account (`monitoring`), never empty/missing. Reuses
    `service_accounts.NON_HUMAN_ROLES` (the same exclusion set
    `deps/auth.py::require_team_member` already gates access with) rather
    than inventing a second definition of "staff role" that could drift
    from it.
    """
    role = normalize_role(role)
    if not role:
        return False
    return role not in NON_HUMAN_ROLES


def can_manage_garuda_practices(user: dict[str, Any] | None) -> bool:
    """True iff `user` (the `{"email","is_admin"}`-or-richer shape this
    module and `deps/auth.py::get_current_user` both produce) may assign or
    transition a GARUDA practice. NOT the same test as
    `crm_utils.is_crm_admin`/`can_view_all_practices` -- see
    `_garuda_practice_admin_emails` docstring above for why the accounting
    full-view role is deliberately excluded from this one.
    """
    if not user:
        return False
    email = (user.get("email") or "").lower().strip()
    if not email:
        return False
    if email in _garuda_practice_admin_emails():
        return True
    return _is_staff_role(user.get("role"))


def _staff_principal_from_role(email: str, role: str | None) -> dict[str, Any] | None:
    """The ONE eligibility check both the cookie path and the Bearer path
    in `require_garuda_staff` run through (cross-family refuter finding
    #4): `email` must be non-empty and `role` must pass `_is_staff_role`.
    Returns the `{"email","is_admin"}` actor shape, or `None` for anything
    that fails eligibility -- the same shape an unrecognized/absent
    credential gets, per `_require_staff_actor`'s own "no caller wired yet,
    never a silent bypass" contract.
    """
    email = (email or "").strip().lower()
    if not email or not can_manage_garuda_practices({"email": email, "role": role}):
        return None
    return {"email": email, "is_admin": email in _garuda_practice_admin_emails()}


def _decode_staff_jwt(token: str) -> dict[str, Any] | None:
    """The ONE staff-specific JWT validator (module docstring point on
    finding #5). Same steps as `deps/auth.py::get_current_user`'s
    Priority-2 branch, against the same secret, but STRICTLY requires
    `type == "access"` (see module docstring) and never raises -- callers
    never need a decode-specific exception on top of the
    auth-service-unavailable case below.
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

    if payload.get("type") != "access":
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


async def _resolve_bearer_actor(authorization: str) -> dict[str, Any] | None:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    payload = _decode_staff_jwt(token)
    if payload is None:
        return None
    return _staff_principal_from_role(
        payload.get("email") or payload.get("sub") or "", payload.get("role")
    )


async def verify_staff_session(authorization: str) -> str | None:
    """Bearer-token staff verifier — the `StaffSession` contract shape AND
    `_require_staff_actor`'s existing string-actor contract (see module
    docstring point 1). `authorization` is the raw header VALUE (e.g.
    `"Bearer <jwt>"`), matching `_require_staff_actor`'s own call site.
    """
    actor = await _resolve_bearer_actor(authorization)
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
        actor = _staff_principal_from_role(user.get("email") or "", user.get("role"))
        if actor is not None:
            return actor

    authorization = request.headers.get("authorization")
    if authorization:
        actor = await _resolve_bearer_actor(authorization)
        if actor is not None:
            return actor

    return None
