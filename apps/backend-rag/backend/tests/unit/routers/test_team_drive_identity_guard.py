"""Real-staff role guard on the team_drive allow-list identity lookup (H1).

Census 2026-10-06 (``research/operations/2026-10-06-team-members-identity-joins-census.md``):
``team_members`` mixes ~515 client-portal-login rows (``role='client'``) into the
same table as real staff. ``get_user_allowed_folders`` matched the caller's
email (+ ``active``) only — never role — so a client-portal JWT whose row
collided classified the caller as ``role="team"`` for ``folder_access_rules``
resolution instead of falling to the safe not-found default (SHARED_FOLDERS
only). The drive endpoints accept any valid JWT, including client-portal ones.

The fix mirrors ``backend/services/whatsapp_identity.py`` (fail-closed:
``role='client'`` AND NULL/blank role are both "not proven staff"). These tests
pin the site with a guilt/innocence pair:

- GUILT: the identity lookup SQL must carry the real-staff guard — under the
  old predicate this assertion fails (the SQL had no role filter at all).
- INNOCENCE: the email match and the active check survive, so a real staff row
  still resolves with its department/role.

Synthetic fixtures only: no production data, no real addresses (the collision
scenario is exercised against the SQL text, which is where the defect lived).
"""

from __future__ import annotations

import re

import pytest

from backend.app.routers.team_drive import get_user_allowed_folders

# Fail-closed form of the staff-role guard (whatsapp_identity.py model): a
# NULL/blank role is "not proven staff", exactly like role='client'.
STAFF_ROLE_GUARD = re.compile(
    r"lower\(btrim\(coalesce\((?:tm\.)?role,\s*''\)\)\)\s*<>\s*'client'",
    re.IGNORECASE,
)


class _RecordingConnection:
    """Captures the SQL the router sends (idiom: tests/unit/services/crm/
    test_owner_role_guard.py). Returns no row → not-found default branch."""

    def __init__(self) -> None:
        self.statements: list[str] = []

    async def fetchrow(self, sql, *args):
        self.statements.append(sql)
        return None

    async def fetch(self, sql, *args):
        self.statements.append(sql)
        return []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _Pool:
    def __init__(self, conn: _RecordingConnection) -> None:
        self._conn = conn

    def acquire(self):
        return self._conn


@pytest.mark.asyncio
async def test_drive_identity_lookup_requires_a_real_staff_role_guilt() -> None:
    """An active client-portal row (role='client') with a colliding email must
    NOT feed the drive allow-list as a staff identity — it must fall to the
    not-found default. Under the old predicate (email + active only) this
    assertion fails."""
    conn = _RecordingConnection()

    await get_user_allowed_folders("collider@example.com", _Pool(conn))

    identity_sql = [s for s in conn.statements if "team_members" in s]
    assert identity_sql, "the identity lookup is the team_members query"
    sql = " ".join(identity_sql).lower()
    assert STAFF_ROLE_GUARD.search(sql), (
        "get_user_allowed_folders matches team_members on email + active only "
        "— an active client-portal-login row (role='client') with a colliding "
        "email would be authorised on the team drive as role='team'. Add the "
        "fail-closed staff-role guard (whatsapp_identity.py pattern) to the "
        "WHERE clause (census 2026-10-06, H1)."
    )


@pytest.mark.asyncio
async def test_drive_identity_lookup_still_credits_real_staff_innocence() -> None:
    """The staff-matching substance is untouched: the email match and the
    active check survive, so a real staff row still resolves with its
    department."""
    conn = _RecordingConnection()

    await get_user_allowed_folders("staff.member@example.com", _Pool(conn))

    identity_sql = [s for s in conn.statements if "team_members" in s]
    assert identity_sql, "no team_members identity lookup issued"
    sql = " ".join(identity_sql).lower()
    assert "tm.email = $1" in sql, (
        "the email match must survive the hardening — the role guard is added "
        "to the predicate, not substituted for it"
    )
    assert "tm.active = true" in sql, "the active check must survive too"
