"""Guilt/innocence for the GARUDA assignee enumeration and its endpoint's auth.

The invariant, both halves (superscar #3 — OVER- and UNDER-match are symmetric):

* GUILT: nothing `is_valid_garuda_assignment_target` refuses is ever offered.
  This is the measured production defect the enumeration closes — the shared CRM
  roster (`GET /api/team/members`, denylist `{client, monitoring}`) offered an
  ACTIVE row whose email is in `PRACTICES_EXTRA_VIEW_EMAILS`, which
  `assignPractice` refuses with 422: a dropdown option whose only possible
  outcome was an error.
* INNOCENCE: every active candidate the validator accepts IS offered. A filter
  that quietly locks real staff out is the same defect wearing the other hat, so
  the roster SSOT `backend/data/team_members.json` drives the fixture: every
  role it names gets a row here and must come back out.

The expectation is DERIVED from the validator, never hand-written as a role
list. PR #5817 is replacing `service_accounts.is_human_team_member`'s denylist
with a census allow-list while this file is being written; a hardcoded list here
would either go stale or start asserting the superseded rule. Derived, this file
keeps telling the truth about whatever the predicate currently is — which is the
whole reason the enumeration calls the predicate instead of restating it.

`_FakeConn` emulates the two queries by honouring the bind parameter it is
handed rather than restating the SQL's intent. The SQL text itself is only
proven against a real database; what is proven here is the composition — which
rows get asked about, and what is done with the answers.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import get_database_pool
from backend.app.routers import garuda_assignment_targets
from backend.app.utils.crm_utils import PRACTICES_EXTRA_VIEW_EMAILS
from backend.services.garuda_portal import assignment_targets, staff_auth

_CENSUS_PATH = Path(__file__).resolve().parents[3] / "data" / "team_members.json"

_ADMIN_EMAIL = "admin@example.test"
#: In the admin set but with NO `team_members` row — the boundary the service
#: module docstring states instead of leaving silent.
_GHOST_ADMIN_EMAIL = "ghost-admin@example.test"

assert PRACTICES_EXTRA_VIEW_EMAILS, (
    "the read-only full-view set is empty; the guilt case below would pass vacuously"
)
_READONLY_VIEWER_EMAIL = sorted(PRACTICES_EXTRA_VIEW_EMAILS)[0]


def _census_roles() -> list[str]:
    """Distinct roles named by the roster SSOT. Anchor: an empty or moved census
    file must fail loudly, not shrink the innocence half to nothing."""
    rows = json.loads(_CENSUS_PATH.read_text())
    assert isinstance(rows, list) and rows, f"{_CENSUS_PATH} is not a non-empty list"
    roles = sorted(
        {
            str(row.get("role", "")).strip().lower()
            for row in rows
            if isinstance(row, dict) and row.get("role")
        }
    )
    assert roles, f"{_CENSUS_PATH} named no roles — innocence half would pass vacuously"
    return roles


_CENSUS_ROLES = _census_roles()


def _slug(role: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", role.lower()).strip("-") or "role"


def _row(email: str, role: str | None, *, active: bool = True, **names: Any) -> dict[str, Any]:
    return {
        "email": email,
        "name": names.get("name", _slug(email.split("@")[0])),
        "full_name": names.get("full_name"),
        "role": role,
        "active": active,
    }


def _roster() -> list[dict[str, Any]]:
    """One row per roster-SSOT role (the innocence half) plus every class the
    validator refuses (the guilt half). Emails are synthetic; the one real
    address in the fixture comes from `PRACTICES_EXTRA_VIEW_EMAILS` by import,
    never as a literal."""
    rows: list[dict[str, Any]] = [
        _row(f"{_slug(role)}@example.test", role, full_name=_slug(role).replace("-", " ").title())
        for role in _CENSUS_ROLES
    ]
    rows += [
        _row(_ADMIN_EMAIL, "founder", full_name="Admin Founder"),
        _row("partner-active@example.test", "partner"),
        _row("partner-inactive@example.test", "partner", active=False),
        _row("client-row@example.test", "client"),
        _row("monitoring-row@example.test", "monitoring"),
        # the middleware default role, and the shapes a denylist used to wave through
        _row("default-user@example.test", "user"),
        _row("empty-role@example.test", ""),
        _row("none-role@example.test", None),
        _row("spaced-partner@example.test", " Partner "),
        _row("invented-role@example.test", "space-cadet"),
        # refused by the read-only-viewer exclusion, NOT by its role: the role
        # here is one the census itself names
        _row(_READONLY_VIEWER_EMAIL, "board member", full_name="Read Only Viewer"),
    ]
    assert _READONLY_VIEWER_EMAIL not in {r["email"] for r in rows[: len(_CENSUS_ROLES) + 1]}
    return rows


class _FakeConn:
    """`fetch(_CANDIDATE_SQL, denylist)` and the validator's
    `fetchrow(... WHERE LOWER(email) = $1 AND active = TRUE)`, emulated from the
    parameter actually passed."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.fetch_calls = 0
        self.fetchrow_calls = 0

    async def fetch(self, _sql: str, *args: Any) -> list[dict[str, Any]]:
        self.fetch_calls += 1
        excluded = {str(role).strip().lower() for role in args[0]} if args else set()
        return [
            row
            for row in self._rows
            if row["active"] and str(row["role"] or "").strip().lower() not in excluded
        ]

    async def fetchrow(self, _sql: str, *args: Any) -> dict[str, Any] | None:
        self.fetchrow_calls += 1
        email = str(args[0]).strip().lower()
        for row in self._rows:
            if str(row["email"] or "").strip().lower() == email and row["active"]:
                return {"role": row["role"]}
        return None


@pytest.fixture(autouse=True)
def _fixed_admin_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the admin constant so these tests do not depend on the machine's
    `ADMIN_EMAILS` env (the helper already tolerates a MagicMock `settings`, but
    "tolerates" is not "asserts something known")."""
    monkeypatch.setattr(
        staff_auth,
        "_garuda_practice_admin_emails",
        lambda: frozenset({_ADMIN_EMAIL, _GHOST_ADMIN_EMAIL}),
    )


async def _validator_verdicts(rows: list[dict[str, Any]]) -> tuple[set[str], set[str]]:
    """(accepted, refused) over the ACTIVE rows, asked of the validator itself."""
    conn = _FakeConn(rows)
    accepted: set[str] = set()
    refused: set[str] = set()
    for row in rows:
        email = str(row["email"] or "").strip().lower()
        if not email or not row["active"]:
            continue
        if await staff_auth.is_valid_garuda_assignment_target(conn, email):
            accepted.add(email)
        else:
            refused.add(email)
    return accepted, refused


async def test_listed_is_exactly_the_active_rows_the_validator_accepts() -> None:
    """THE invariant, both halves at once: listed ∩ refused = ∅ (never offer a
    422) and listed == accepted (never omit a valid target)."""
    rows = _roster()
    listed = await assignment_targets.list_garuda_assignment_targets(_FakeConn(rows))
    emails = [item["email"] for item in listed]

    accepted, refused = await _validator_verdicts(rows)
    # anchors: neither half may pass vacuously
    assert accepted, "no candidate is accepted — the innocence half would prove nothing"
    assert refused, "no candidate is refused — the guilt half would prove nothing"

    assert len(emails) == len(set(emails)), f"offered a duplicate email: {emails}"
    assert not (set(emails) & refused), (
        f"offered rows the validator refuses: {sorted(set(emails) & refused)}"
    )
    assert set(emails) == accepted, (
        f"enumeration disagrees with the validator — "
        f"missing {sorted(accepted - set(emails))}, extra {sorted(set(emails) - accepted)}"
    )


@pytest.mark.parametrize(
    "role",
    ["partner", "client", "monitoring", "", None, " Partner "],
    ids=["partner", "client", "monitoring", "empty", "none", "spaced-partner"],
)
async def test_refused_role_is_never_offered(role: str | None) -> None:
    """Only the classes the predicate refuses TODAY are named here. An unknown
    role (``user``, the middleware default; anything invented) is accepted by
    the current denylist and refused by the allow-list PR #5817 introduces — the
    enumeration must follow the predicate either way, never anticipate it, so
    those two are covered by the DERIVED invariant above (its fixture roster
    carries both rows) and deliberately not asserted twice as a hardcoded rule
    this file does not own."""
    rows = [_row("candidate@example.test", role)]
    conn = _FakeConn(rows)
    assert await assignment_targets.list_garuda_assignment_targets(conn) == []
    # anchor: the validator refuses this row too, so the enumeration is not
    # dropping it for an unrelated reason (a prefilter that quietly dropped a
    # row the validator would accept is the UNDER-match half of superscar #3)
    assert not await staff_auth.is_valid_garuda_assignment_target(conn, "candidate@example.test")


async def test_enumeration_decides_by_asking_not_by_copying(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The executable form of "calls the predicate, never restates it": replace
    the predicate the enumeration asks and the list follows. A second copy of
    the rule — the drift this module exists to avoid, and the one
    `staff_auth._is_staff_role`'s own docstring already records having paid for
    — would keep answering from the roles instead."""
    rows = _roster()
    only = "invented-role@example.test"

    async def _stub(_conn: Any, email: str) -> bool:
        return email == only

    monkeypatch.setattr(assignment_targets, "is_valid_garuda_assignment_target", _stub)
    listed = await assignment_targets.list_garuda_assignment_targets(_FakeConn(rows))
    assert [item["email"] for item in listed] == [only]


@pytest.mark.parametrize("role", _CENSUS_ROLES)
async def test_every_roster_ssot_role_is_offered(role: str) -> None:
    rows = [_row("candidate@example.test", role)]
    listed = await assignment_targets.list_garuda_assignment_targets(_FakeConn(rows))
    assert [item["email"] for item in listed] == ["candidate@example.test"], (
        f"role {role!r} is named by {_CENSUS_PATH.name} but was not offered"
    )


async def test_read_only_full_view_row_is_not_offered_despite_a_staff_role() -> None:
    """The live production case: an active row with a census role that the
    validator refuses on the read-only-viewer exclusion."""
    rows = [_row(_READONLY_VIEWER_EMAIL, "board member")]
    conn = _FakeConn(rows)
    assert await assignment_targets.list_garuda_assignment_targets(conn) == []
    assert not await staff_auth.is_valid_garuda_assignment_target(conn, _READONLY_VIEWER_EMAIL)


async def test_admin_boundary_is_the_documented_one() -> None:
    """An admin WITH an active row is offered; an admin email with NO row is
    accepted by the validator but not offered — the boundary the service module
    docstring names, pinned so it stays a decision rather than a surprise."""
    rows = _roster()
    listed = {
        item["email"]
        for item in await assignment_targets.list_garuda_assignment_targets(_FakeConn(rows))
    }
    conn = _FakeConn(rows)

    assert _ADMIN_EMAIL in listed
    assert _GHOST_ADMIN_EMAIL not in listed
    assert await staff_auth.is_valid_garuda_assignment_target(conn, _GHOST_ADMIN_EMAIL)


async def test_label_prefers_full_name_then_name_then_email() -> None:
    rows = [
        _row("full@example.test", "founder", name="Full Name", full_name="Full Name"),
        _row("name-only@example.test", "founder", name="Name Only", full_name="   "),
        _row("bare@example.test", "founder", name="", full_name=None),
    ]
    listed = await assignment_targets.list_garuda_assignment_targets(_FakeConn(rows))
    assert {item["email"]: item["label"] for item in listed} == {
        "full@example.test": "Full Name",
        "name-only@example.test": "Name Only",
        "bare@example.test": "bare@example.test",
    }


async def test_duplicate_labels_carry_the_email_and_duplicate_rows_collapse() -> None:
    """Two options rendering the same text are indistinguishable to the person
    picking one; two rows for one email must not become two options."""
    rows = [
        _row("twin-a@example.test", "founder", name="twin", full_name="Twin"),
        _row("twin-b@example.test", "ceo", name="twin", full_name="Twin"),
        _row("Solo Example", "founder"),
        _row("DUPLICATE@EXAMPLE.TEST", "ceo", name="Dup", full_name="Dup"),
        _row("duplicate@example.test", "ceo", name="Dup", full_name="Dup"),
    ]
    listed = await assignment_targets.list_garuda_assignment_targets(_FakeConn(rows))
    by_email = {item["email"]: item["label"] for item in listed}

    assert by_email["twin-a@example.test"] == "Twin (twin-a@example.test)"
    assert by_email["twin-b@example.test"] == "Twin (twin-b@example.test)"
    assert "duplicate@example.test" in by_email
    assert len([email for email in by_email if email == "duplicate@example.test"]) == 1


# ---------------------------------------------------------------------------
# The endpoint's own posture: who may read the list, and what it hands back.
# ---------------------------------------------------------------------------

_DB_TOUCHED = "the gate must refuse before the database is touched"


class _UntouchablePool:
    """Any attribute access is a test failure (same idiom as
    `test_crm_intelligence_partner_gate.py`): a 401/403 proves the gate fired
    before any roster row could be read."""

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"{_DB_TOUCHED} (accessed .{name})")


class _Acquire:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    async def __aenter__(self) -> _FakeConn:
        return self._conn

    async def __aexit__(self, *_exc: object) -> bool:
        return False


class _FakePool:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    def acquire(self) -> _Acquire:
        return _Acquire(self._conn)


def _client(pool: Any, actor: dict[str, Any] | None, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    async def _resolve(_request: Any) -> dict[str, Any] | None:
        return actor

    monkeypatch.setattr(garuda_assignment_targets, "require_garuda_staff", _resolve)
    app = FastAPI()
    app.include_router(garuda_assignment_targets.router)
    app.dependency_overrides[get_database_pool] = lambda: pool
    return TestClient(app)


_URL = "/api/crm/garuda/assignment-targets"


def test_endpoint_refuses_a_caller_that_is_not_a_staff_principal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _client(_UntouchablePool(), None, monkeypatch)
    response = client.get(_URL)
    assert response.status_code == 401


def test_endpoint_refuses_a_non_admin_staff_member(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`assignPractice` is admin-only, so a non-admin is not handed the list of
    people to assign to."""
    actor = {"email": "staff@example.test", "is_admin": False}
    client = _client(_UntouchablePool(), actor, monkeypatch)
    response = client.get(_URL)
    assert response.status_code == 403


async def test_endpoint_serves_the_enumeration_to_an_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = _roster()
    client = _client(
        _FakePool(_FakeConn(rows)), {"email": _ADMIN_EMAIL, "is_admin": True}, monkeypatch
    )
    response = client.get(_URL)

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store, private"
    items = response.json()["items"]
    assert items, "an admin got an empty picker over a roster full of staff rows"
    assert all(set(item) == {"email", "label"} for item in items)
    # the body is the service's own answer, not a second rendering of it
    accepted, refused = await _validator_verdicts(rows)
    assert {item["email"] for item in items} == accepted
    assert not ({item["email"] for item in items} & refused)
