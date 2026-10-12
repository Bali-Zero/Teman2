"""Real-staff role guard on the wa_copilot team-identity signals (H2, H3).

Census 2026-10-06 (``research/operations/2026-10-06-team-members-identity-joins-census.md``):
``team_members`` mixes ~515 client-portal-login rows (``role='client'``) into the
same table as real staff. Both team signals in the sender-identity cascade
classified the sender as ``sender_role='team'`` with no role filter:

- ``resolve_team_email`` (H2): ``team_member_email`` → ``team_members.email``
  (confidence 1.00). A stale ``team_member_email`` carrying a client's address
  classified the client as staff — and team answers never touch the shared
  cache (2026-07-20 ruling), so the blast radius is wider than a bad label.
- ``resolve_team_name`` (H3): pg_trgm fuzzy match of the push name against
  ``team_members.full_name``. Client rows carry real full_names, so any
  inbound client message resembling a roster name classified as team. The
  ambiguity guard compares two candidates against each other, never staff vs
  client.

The fix mirrors ``backend/services/whatsapp_identity.py`` (fail-closed:
``role='client'`` AND NULL/blank role are both "not proven staff"). These tests
pin both sites with a guilt/innocence pair:

- GUILT: the lookup SQL must carry the real-staff guard — under the old
  predicate these assertions fail (neither query had a role filter).
- INNOCENCE: the matching substance (email equality / trgm match + active)
  survives, so a real staff row still resolves as team.

Synthetic fixtures only: no production data, no real addresses (the collision
scenario is exercised against the SQL text, which is where the defect lived).
"""

from __future__ import annotations

import re

import pytest

from backend.services.wa_copilot.identity_resolver import (
    resolve_team_email,
    resolve_team_name,
)

# Fail-closed form of the staff-role guard (whatsapp_identity.py model): a
# NULL/blank role is "not proven staff", exactly like role='client'.
STAFF_ROLE_GUARD = re.compile(
    r"lower\(btrim\(coalesce\((?:tm\.)?role,\s*''\)\)\)\s*<>\s*'client'",
    re.IGNORECASE,
)


class _RecordingConnection:
    """Captures the SQL the resolver sends; returns no row (idiom:
    tests/unit/services/crm/test_owner_role_guard.py)."""

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


# --- H2: resolve_team_email -------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_team_email_requires_a_real_staff_role_guilt() -> None:
    """A team_members row with role='client' and a colliding email must NOT
    classify the sender as 'team'. Under the old predicate (email + active
    only) this assertion fails."""
    conn = _RecordingConnection()

    result = await resolve_team_email(conn, {"team_member_email": "collider@example.com"})

    assert result is None
    sql = " ".join(conn.statements).lower()
    assert "team_members" in sql, "the staff directory is team_members"
    assert STAFF_ROLE_GUARD.search(sql), (
        "resolve_team_email matches team_members on email + active only — an "
        "active client-portal-login row (role='client') with a colliding email "
        "would classify the client as sender_role='team' (and team answers "
        "never touch the shared cache). Add the fail-closed staff-role guard "
        "(whatsapp_identity.py pattern) to the WHERE clause "
        "(census 2026-10-06, H2)."
    )


@pytest.mark.asyncio
async def test_resolve_team_email_still_credits_real_staff_innocence() -> None:
    """The staff-matching substance is untouched: the email equality and the
    active check survive, so a real staff row still resolves as team."""
    conn = _RecordingConnection()

    await resolve_team_email(conn, {"team_member_email": "staff.member@example.com"})

    sql = " ".join(conn.statements).lower()
    assert "lower(email) = lower($1)" in sql, (
        "the case-insensitive email match must survive the hardening — the "
        "role guard is added to the predicate, not substituted for it"
    )
    assert "active = true" in sql, "the active check must survive too"


# --- H3: resolve_team_name --------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_team_name_requires_a_real_staff_role_guilt() -> None:
    """A client row whose full_name trigram-matches the sender's push name must
    NOT classify the sender as 'team'. Under the old predicate (active +
    full_name trgm only) this assertion fails."""
    conn = _RecordingConnection()

    result = await resolve_team_name(conn, {"sender": "Synthetic Collider"})

    assert result is None
    sql = " ".join(conn.statements).lower()
    assert "team_members" in sql, "the staff directory is team_members"
    assert STAFF_ROLE_GUARD.search(sql), (
        "resolve_team_name fuzzy-matches team_members.full_name with no role "
        "filter — client rows carry real full_names, so an inbound client "
        "message resembling any roster name is classified as "
        "sender_role='team'. Add the fail-closed staff-role guard "
        "(whatsapp_identity.py pattern) to the WHERE clause "
        "(census 2026-10-06, H3)."
    )


@pytest.mark.asyncio
async def test_resolve_team_name_still_credits_real_staff_innocence() -> None:
    """The staff-matching substance is untouched: the trigram match, the NULL
    full_name exclusion, and the active check survive, so a real staff row
    still resolves as team."""
    conn = _RecordingConnection()

    await resolve_team_name(conn, {"sender": "Staff Member"})

    sql = " ".join(conn.statements).lower()
    assert "full_name % $1" in sql, (
        "the trigram match must survive the hardening — the role guard is "
        "added to the predicate, not substituted for it"
    )
    assert "full_name is not null" in sql
    assert "active = true" in sql, "the active check must survive too"
