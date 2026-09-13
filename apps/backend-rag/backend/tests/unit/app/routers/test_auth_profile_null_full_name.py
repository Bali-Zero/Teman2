"""GET /api/auth/profile must not 500 on a client whose full_name is NULL.

Portal audit finding F-03 (2026-09-11, live): the portal's Settings → Account
tab rendered "Unable to load profile." and the backing
`GET /api/auth/profile` answered HTTP 500.

Root cause: `get_current_user` selected `full_name as name`. `full_name` is
NULLABLE, `name` is NOT NULL, and the two portal write paths only ever fill
ONE of them — `ensure_portal_profile` inserts `name` and never `full_name`,
`complete_registration`'s existing-user branch updates neither. Measured on
production the same day: **455 of 540 `role='client'` rows carry
`full_name IS NULL`**, so `name` arrived as None and
`UserProfile(**current_user)`, where `name: str` is required, raised a
ValidationError that the route turned into a bare 500 — for 84% of clients.
"""

from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

from backend.app.models import UserProfile
from backend.app.routers import auth
from backend.services.portal import portal_profile_service


def _row(name: object) -> dict[str, object]:
    """The shape `get_current_user` returns to the route."""
    return {
        "id": "00000000-0000-0000-0000-000000000000",
        "email": "client@example.test",
        "name": name,
        "role": "client",
        "status": "active",
        "metadata": None,
        "language_preference": "en",
        "avatar": None,
    }


def test_user_profile_rejects_a_null_name_which_is_why_the_route_500d() -> None:
    """The failure mode, pinned: this is what a NULL full_name produced."""
    with pytest.raises(ValidationError):
        UserProfile(**_row(None))


def test_user_profile_accepts_a_real_name() -> None:
    profile = UserProfile(**_row("Client Name"))
    assert profile.name == "Client Name"
    assert profile.email == "client@example.test"


def test_get_current_user_query_coalesces_the_nullable_column() -> None:
    """Guilt-proof on the projection, which is where the 500 lives.

    A unit test cannot reach the live query without a database, so assert the
    SQL. Restoring `full_name as name` fails the first assertion; a COALESCE
    that puts `email` first — losing every real name — fails the second.
    """
    # Comment lines are stripped first: the cure's own comment QUOTES the
    # broken projection to explain it, and a substring test over raw source
    # would convict the explanation (superscar #3, guard-over-match). The
    # guard is about the CODE, so read the code.
    code = "\n".join(
        line
        for line in inspect.getsource(auth.get_current_user).splitlines()
        if not line.lstrip().startswith("#")
    )

    assert "full_name as name" not in code, (
        "full_name is nullable: projecting it straight into UserProfile.name "
        "(a required str) IS the 500"
    )
    assert "COALESCE(full_name, name, email) as name" in code
    assert "FROM team_members" in code


def test_ensure_portal_profile_writes_both_name_columns() -> None:
    """The divergence stops being created: new rows carry full_name too, and
    a re-provision never overwrites a full_name that is already set."""
    source = inspect.getsource(portal_profile_service.PortalProfileService)

    assert "name, full_name, email" in source
    assert "full_name = COALESCE(" in source
    assert "team_members.full_name" in source
