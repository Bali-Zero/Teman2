"""
Tests for notifications admin_router.require_admin using the canonical
role/email-based admin check (Bug #6, found via live prod E2E 2026-07-08).

SCAR CONTEXT:
`admin_router.require_admin` gated on `current_user.get("is_admin")` — a
boolean field the auth layer NEVER populates. `get_current_user`
(backend/app/deps/auth.py) returns only {email, user_id, role, permissions};
`is_admin` is absent, so `.get("is_admin")` is always None → EVERY caller
gets 403, including genuine Founders (zero@balizero.com). The notifications
admin tab reached the backend (double-prefix fix #2143 mounted the route)
but 403'd for the owner.

FIX: delegate to the canonical `is_crm_admin(current_user)` used across
crm_clients.py — email-in-admin-list OR role in {admin, board member, ceo,
founder}. This is the SAME check the working CRM tabs use, so a real admin's
role-based JWT reaches the notifications endpoints.

This test drives require_admin directly with representative user dicts (the
exact shape get_current_user emits), so it proves the gate by CONTENT, not by
the phantom flag.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException


def _require_admin():
    from backend.app.modules.notifications.admin_router import require_admin

    return require_admin


def test_founder_role_admin_passes() -> None:
    """GUILT: a genuine admin (role=founder) — the exact dict shape
    get_current_user emits — must NOT be rejected. This is the regression:
    the old `is_admin` flag was absent → 403 for the owner."""
    require_admin = _require_admin()
    founder = {
        "email": "someone@balizero.com",
        "user_id": "someone@balizero.com",
        "role": "founder",
        "permissions": [],
    }
    # Must not raise.
    require_admin(founder)


def test_admin_email_passes() -> None:
    """GUILT: an email in the admin allowlist (zero@balizero.com) passes even
    if its role were a plain 'user' — mirrors is_crm_admin's email branch."""
    require_admin = _require_admin()
    admin_by_email = {
        "email": "zero@balizero.com",
        "user_id": "zero@balizero.com",
        "role": "user",
        "permissions": [],
    }
    require_admin(admin_by_email)


def test_regular_user_still_403() -> None:
    """INNOCENCE: a non-admin team member (role=user, non-admin email) must
    still be rejected 403 — the fix must not open the endpoint to everyone."""
    require_admin = _require_admin()
    regular = {
        "email": "staffer@balizero.com",
        "user_id": "staffer@balizero.com",
        "role": "user",
        "permissions": [],
    }
    with pytest.raises(HTTPException) as exc:
        require_admin(regular)
    assert exc.value.status_code == 403


def test_client_role_403() -> None:
    """INNOCENCE: a portal client must never reach notifications admin."""
    require_admin = _require_admin()
    client = {
        "email": "client@example.com",
        "user_id": "client@example.com",
        "role": "client",
        "permissions": [],
    }
    with pytest.raises(HTTPException) as exc:
        require_admin(client)
    assert exc.value.status_code == 403


def test_does_not_gate_on_phantom_is_admin_flag() -> None:
    """INNOCENCE (source-level): require_admin must no longer GATE on the
    phantom `.get("is_admin")` key that the auth layer never sets — it must
    delegate to the canonical is_crm_admin helper instead.

    The check inspects the executable CODE (docstring stripped) so an
    explanatory docstring that names the old flag doesn't false-positive.
    """
    import ast
    import inspect

    from backend.app.modules.notifications import admin_router

    fn = ast.parse(inspect.getsource(admin_router.require_admin)).body[0]
    # Drop the docstring so we scan only real statements.
    body = fn.body
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(getattr(body[0], "value", None), ast.Constant)
    ):
        body = body[1:]
    code = "\n".join(ast.dump(stmt) for stmt in body)

    assert "is_admin" not in code, (
        "require_admin CODE still gates on the phantom `is_admin` flag — "
        "get_current_user never populates it, so this 403s real admins. "
        "Delegate to is_crm_admin(current_user) instead."
    )
    assert "is_crm_admin" in code, (
        "require_admin should delegate to the canonical is_crm_admin helper "
        "(email allowlist OR role in {admin, board member, ceo, founder})."
    )


def test_no_notifications_route_gates_on_phantom_is_admin_flag() -> None:
    """GUILT+class (W89): NO route in the notifications module may gate on the
    phantom `current_user.get("is_admin")` flag — the auth layer never sets it,
    so it 403s genuine admins. This scans the whole module (admin_router.py AND
    router.py) so the sibling that had the same bug can't creep back in, and a
    newly-added admin endpoint can't reintroduce it.
    """
    import ast
    from pathlib import Path

    module_dir = (
        Path(__file__).resolve().parents[6]
        / "backend"
        / "app"
        / "modules"
        / "notifications"
    )
    assert module_dir.is_dir(), f"notifications module not found at {module_dir}"

    def _phantom_gate_nodes(tree: ast.AST) -> list[ast.AST]:
        """Find real accesses of the 'is_admin' key on a mapping — either
        `x.get("is_admin")` or `x["is_admin"]`. AST-based, so string literals
        (docstrings, comments, explanatory prose) are structurally excluded."""
        hits: list[ast.AST] = []
        for node in ast.walk(tree):
            # x.get("is_admin")
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "is_admin"
            ):
                hits.append(node)
            # x["is_admin"]
            if (
                isinstance(node, ast.Subscript)
                and isinstance(node.slice, ast.Constant)
                and node.slice.value == "is_admin"
            ):
                hits.append(node)
        return hits

    offenders: list[str] = []
    for py in sorted(module_dir.glob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in _phantom_gate_nodes(tree):
            offenders.append(f"{py.name}:{getattr(node, 'lineno', '?')}")

    assert not offenders, (
        "These notifications routes still access the phantom `is_admin` flag "
        "that get_current_user never populates (403s real admins). Use "
        "is_crm_admin(current_user) instead:\n  " + "\n  ".join(offenders)
    )
