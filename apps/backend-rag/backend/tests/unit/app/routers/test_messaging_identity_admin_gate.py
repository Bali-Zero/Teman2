"""
Tests for messaging_identity.require_admin using the canonical role/email-based
admin check (live prod 500, found 2026-07-08).

SCAR CONTEXT:
`require_admin` had two bugs:

1. It queried a separate `team_access` table and restricted the pass condition
   to the literal role strings "admin"/"founder" only, disagreeing with the
   canonical `is_crm_admin` gate used across the rest of the CRM (which also
   accepts an admin-allowlisted email, or role in {board member, ceo}) — a
   genuine Founder authorized elsewhere in the CRM could be rejected here.
2. The whole check was wrapped in `try/except Exception`, which caught the
   deliberately-raised `HTTPException(403)` and re-raised it as a 500 —
   masking the real 403 reason in prod logs and breaking the HTTP contract
   (a client-error became a server-error).

Fix: `require_admin` now takes the JWT-derived `current_user` dict directly
(no DB round-trip) and delegates to the canonical `is_crm_admin(current_user)`
— the SAME gate `crm_clients.py`, `team_activity.py`, and the notifications
module (Bug #6, W89) use. No try/except around the guard, so a 403 stays 403.

This test drives `require_admin` directly with representative user dicts (the
exact shape `get_current_user` emits), so it proves the gate by CONTENT, not
by re-running the whole FastAPI dependency graph.
"""

from __future__ import annotations

import ast
import inspect

import pytest
from fastapi import HTTPException


def _require_admin():
    from backend.app.routers.messaging_identity import require_admin

    return require_admin


@pytest.mark.asyncio
async def test_founder_role_admin_passes() -> None:
    """GUILT: a genuine admin (role=founder) — the exact dict shape
    get_current_user emits — must NOT be rejected. This is the regression:
    the old query only accepted role in ("admin", "founder") verbatim from a
    DB table that could easily disagree with the JWT role, and the outer
    try/except would have turned the resulting 403 into a 500 anyway."""
    require_admin = _require_admin()
    founder = {
        "email": "zero@balizero.com",
        "user_id": "zero@balizero.com",
        "role": "founder",
        "permissions": [],
    }
    result = await require_admin(founder)
    assert result == "zero@balizero.com"


@pytest.mark.asyncio
async def test_admin_email_passes() -> None:
    """GUILT: an email in the admin allowlist passes even if role is a plain
    'user' — mirrors is_crm_admin's email branch."""
    require_admin = _require_admin()
    admin_by_email = {
        "email": "asya@balizero.com",
        "user_id": "asya@balizero.com",
        "role": "user",
        "permissions": [],
    }
    result = await require_admin(admin_by_email)
    assert result == "asya@balizero.com"


@pytest.mark.asyncio
async def test_board_member_role_passes() -> None:
    """GUILT: is_crm_admin also accepts role in {board member, ceo} — a
    stricter admin/founder-only string check would have rejected these."""
    require_admin = _require_admin()
    board_member = {
        "email": "someone@balizero.com",
        "user_id": "someone@balizero.com",
        "role": "board member",
        "permissions": [],
    }
    result = await require_admin(board_member)
    assert result == "someone@balizero.com"


@pytest.mark.asyncio
async def test_regular_user_gets_403_not_500() -> None:
    """INNOCENCE + the core bug: a non-admin team member must be rejected
    with 403 (the deliberate, correct status), NOT masked into a 500 by an
    overly-broad try/except around the guard."""
    require_admin = _require_admin()
    regular = {
        "email": "staffer@balizero.com",
        "user_id": "staffer@balizero.com",
        "role": "user",
        "permissions": [],
    }
    with pytest.raises(HTTPException) as exc:
        await require_admin(regular)
    assert exc.value.status_code == 403
    assert "admin" in exc.value.detail.lower() or "founder" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_client_role_403() -> None:
    """INNOCENCE: a portal client must never reach messaging-identity admin
    endpoints."""
    require_admin = _require_admin()
    client = {
        "email": "client@example.com",
        "user_id": "client@example.com",
        "role": "client",
        "permissions": [],
    }
    with pytest.raises(HTTPException) as exc:
        await require_admin(client)
    assert exc.value.status_code == 403


def test_require_admin_does_not_wrap_guard_in_broad_except() -> None:
    """INNOCENCE (source-level): require_admin's CODE must not contain a
    bare `except Exception` (or similarly broad) block around the admin
    check — that pattern is exactly what turned a deliberate 403 into a 500
    in prod. The AST is scanned so an explanatory docstring/comment
    mentioning "except" doesn't false-positive.
    """
    from backend.app.routers import messaging_identity

    fn = ast.parse(inspect.getsource(messaging_identity.require_admin)).body[0]
    assert isinstance(fn, ast.AsyncFunctionDef | ast.FunctionDef)

    try_nodes = [node for node in ast.walk(fn) if isinstance(node, ast.Try)]
    assert not try_nodes, (
        "require_admin must not wrap the admin guard in a try/except — the "
        "previous implementation caught the deliberate HTTPException(403) "
        "with `except Exception` and re-raised it as a 500, hiding the real "
        "403 reason from prod logs and breaking the HTTP contract."
    )


def test_require_admin_delegates_to_canonical_is_crm_admin() -> None:
    """GUILT (source-level): require_admin must delegate to the canonical
    is_crm_admin helper (the SAME gate crm_clients.py/team_activity.py/the
    notifications module use), not a bespoke DB query restricted to literal
    role strings.
    """
    from backend.app.routers import messaging_identity

    source = inspect.getsource(messaging_identity.require_admin)
    assert "is_crm_admin" in source, (
        "require_admin should delegate to the canonical is_crm_admin(current_user) "
        "helper (email allowlist OR role in {admin, board member, ceo, founder})."
    )
