"""Owner-validity role guard on assigned_to ↔ team_members predicates.

PENDING-ARMS row opened 2026-08-21 (S7 orphan-client water-filling mandate):
``team_members`` mixes ~515 client-portal-login rows (``role='client'``) into
the same table as real staff, and every "is this a valid owner" predicate
matched on email + active only — never on role. A client whose ``assigned_to``
coincides with an active client-login email satisfied EXISTS(...) and was
silently misread as "has a valid owner" (excluded from the orphan pool, or
shown/routed to a client-login account as the owner).

The fix, per that row's missing arming step: every predicate that decides
ownership validity must also require a real-staff signal. This file pins the
three surviving Python call-sites with a guilt/innocence pair:

- GUILT: a client-role team_members row with a colliding email must NOT be
  read as a valid owner — under the old predicate each of these assertions
  fails (the SQL carried no role filter at all).
- INNOCENCE: the email/active matching that credits a REAL staff row is
  unchanged — a non-'client' role still resolves as owner.

Synthetic fixtures only: no production data, no real addresses (the collision
scenario is exercised against the SQL text, which is where the defect lived).
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from backend.app.modules.notifications.service import NotificationService

# NULL-safe form of the ledger's minimal ``tm.role <> 'client'``: identical on
# current data (every team_members row carries a role) and treats an unknown
# (NULL) role as "not proven staff" rather than silently crediting it.
STAFF_ROLE_GUARD = re.compile(r"\btm\.role\s+is\s+distinct\s+from\s+'client'", re.IGNORECASE)


def _repo_root() -> Path:
    p = Path(__file__).resolve()
    while p != p.parent:
        if (p / "apps").is_dir():
            return p
        p = p.parent
    raise AssertionError("repo root (dir containing apps/) not found from test file")


# The owner-resolution JOIN in each file: capture from `ON` up to the WHERE
# clause, whatever line layout the query uses.
_OWNER_JOIN = re.compile(
    r"JOIN\s+team_members\s+tm\s+ON\s+(.+?)(?=\n\s*WHERE\b)",
    re.DOTALL | re.IGNORECASE,
)

_OWNER_PREDICATE_SITES = {
    "portal profile read (owner name/avatar)": (
        "apps/backend-rag/backend/app/routers/portal.py"
    ),
    "portal profile update read (owner name/avatar)": (
        "apps/backend-rag/backend/services/portal/_mixins/billing.py"
    ),
}


def test_owner_resolution_joins_require_a_real_staff_role_guilt() -> None:
    """A client-login row (role='client') with a colliding email must not be
    read as the client's owner on the portal profile surfaces."""
    root = _repo_root()
    for label, rel in _OWNER_PREDICATE_SITES.items():
        src = (root / rel).read_text(encoding="utf-8")
        joins = [m for m in _OWNER_JOIN.finditer(src) if "assigned_to" in m.group(1)]
        assert joins, f"{label}: no assigned_to→team_members owner JOIN found in {rel}"
        for m in joins:
            assert STAFF_ROLE_GUARD.search(m.group(1)), (
                f"{label} ({rel}): the owner-resolution JOIN matches "
                "team_members on email without a real-staff signal — an active "
                "client-portal-login row (role='client') with a colliding email "
                "would be displayed as the client's owner. Add "
                "`AND tm.role IS DISTINCT FROM 'client'` to the JOIN "
                "(PENDING-ARMS 2026-08-21)."
            )


def test_owner_resolution_joins_still_credit_real_staff_innocence() -> None:
    """The staff-matching substance is untouched: email match on assigned_to
    survives, so a real staff row still resolves as owner."""
    root = _repo_root()
    for rel in _OWNER_PREDICATE_SITES.values():
        src = (root / rel).read_text(encoding="utf-8")
        joins = [m for m in _OWNER_JOIN.finditer(src) if "assigned_to" in m.group(1)]
        assert joins, f"no owner JOIN found in {rel}"
        for m in joins:
            assert re.search(
                r"(tm\.email\s*=\s*c\.assigned_to|c\.assigned_to\s*=\s*tm\.email)",
                m.group(1),
            ), (
                f"{rel}: the owner JOIN no longer matches tm.email against "
                "c.assigned_to — the role guard must be added to the predicate, "
                "not substituted for it."
            )


class _RecordingConnection:
    """Captures the SQL the service sends (idiom: tests/unit/app/modules/
    notifications/test_service_db_contracts.py)."""

    def __init__(self) -> None:
        self.statements: list[str] = []

    async def fetchrow(self, sql, *args):
        self.statements.append(sql)
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _service(conn: _RecordingConnection) -> NotificationService:
    pool = Mock()
    pool.acquire = Mock(return_value=conn)
    provider = Mock()
    provider.send_email = AsyncMock(return_value=True)
    return NotificationService(db_pool=pool, email_provider=provider)


@pytest.mark.asyncio
async def test_team_leader_lookup_requires_a_real_staff_role_guilt() -> None:
    """_get_team_leader_email resolves the client's owner for alert routing.
    Under the old predicate (email + active only) this assertion fails: the
    query would happily return a client-login account's email as 'team
    leader' for any client whose assigned_to collided with it."""
    conn = _RecordingConnection()
    service = _service(conn)

    await service._get_team_leader_email(42)

    sql = " ".join(conn.statements).lower()
    assert "team_members" in sql, "the staff directory is team_members"
    assert re.search(r"tm\.role\s+is\s+distinct\s+from\s+'client'", sql), (
        "_get_team_leader_email matches clients.assigned_to against "
        "team_members on email + active only — an active client-portal-login "
        "row (role='client') with a colliding email would be notified as the "
        "client's owner. Add `AND tm.role IS DISTINCT FROM 'client'` "
        "(PENDING-ARMS 2026-08-21)."
    )


@pytest.mark.asyncio
async def test_team_leader_lookup_still_credits_real_staff_innocence() -> None:
    """The lookup still matches on the assigned_to email and the active flag,
    so a real staff row (any of the 17 legitimate role strings) still
    resolves as owner."""
    conn = _RecordingConnection()
    service = _service(conn)

    await service._get_team_leader_email(42)

    sql = " ".join(conn.statements).lower()
    assert "lower(c.assigned_to) = lower(tm.email)" in sql, (
        "the email match against clients.assigned_to must survive the "
        "hardening — the role guard is added to the predicate, not "
        "substituted for it"
    )
    assert "tm.active is not false" in sql, "the active check must survive too"
