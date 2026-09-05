"""``_is_staff_role`` must agree with ``require_team_member`` about who is staff.

``staff_auth.py`` promises to reuse the team gate's exclusion set rather than
keep a second definition that could drift. It had drifted once already: when
``partner`` stopped passing ``is_human_team_member`` the local copy still
admitted it. It now delegates, and this file pins the agreement.
"""

from __future__ import annotations

import pytest

from backend.services.garuda_portal import staff_auth
from backend.services.garuda_portal.staff_auth import (
    _is_staff_role,
    _staff_principal_from_role,
)


@pytest.mark.parametrize("role", ["partner", "Partner", "  PARTNER  ", "client", "monitoring"])
def test_non_team_roles_are_not_staff(role: str) -> None:
    assert _is_staff_role(role) is False


@pytest.mark.parametrize("role", ["Accounting", "Tax Lead", "admin", "Specialist Advisor"])
def test_real_staff_roles_still_qualify(role: str) -> None:
    assert _is_staff_role(role) is True


@pytest.mark.parametrize("role", [None, "", "   "])
def test_empty_role_is_still_refused_here(role: str | None) -> None:
    """The one thing this predicate adds on top of the shared one."""
    assert _is_staff_role(role) is False


def test_partner_never_becomes_a_garuda_staff_principal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(staff_auth, "_garuda_practice_admin_emails", lambda: frozenset())
    assert _staff_principal_from_role("partner@example.com", "partner") is None
    assert _staff_principal_from_role("staff@balizero.com", "Reception") == {
        "email": "staff@balizero.com",
        "is_admin": False,
    }
