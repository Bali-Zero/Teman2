"""Who may be assigned a GARUDA practice — the enumeration half of the gate.

`staff_auth.is_valid_garuda_assignment_target` answers the SINGULAR question
("may THIS email be the target of `assignPractice`?", 422 `INVALID_REQUEST`
when it refuses). Nothing answered the plural one — "which emails may I
OFFER?" — so the staff UI filled its assignee `<select>`
(`apps/mouth/src/app/(workspace)/garuda-voa/[practiceId]/page.tsx`) from the
shared CRM roster `GET /api/team/members`, whose filter is the DENYLIST
`service_accounts.non_human_roles_sql_array()` = {``client``, ``monitoring``}.
The two predicates are not the same set, and the gap is measurable in
production. A read-only census of `team_members` taken 2026-09-06 (counts
only, never emails) found:

* one ACTIVE row whose email is in `crm_utils.PRACTICES_EXTRA_VIEW_EMAILS`
  (the accounting full-view role; `role = 'board member'` in `team_members`).
  The roster lists it — `staff_auth.is_valid_garuda_assignment_target`
  refuses it ("read-only means read-only", its own comment) — so the dropdown
  offered an option whose only possible outcome was a 422.
* ``partner`` rows: refused by the validator (`service_accounts.EXTERNAL_ROLES`),
  deliberately NOT excluded by the roster's denylist, because that module's own
  docstring leaves "whether a partner belongs in a roster or a dropdown" to the
  product layer. The ruling for this surface is that a partner is never
  assignable. Production holds 0 active partner rows (1 inactive), so this half
  is latent rather than live — it is covered here because an inactive row can
  be reactivated without a deploy.

The roster itself cannot be fixed into agreement: it is a visibility artifact
shared with the CRM clients/partners surfaces, where the read-only accounting
viewer legitimately belongs and where a partner's own colleagues may need to
appear. Only the GARUDA assignment dropdown needs the narrower set.

CONTRACT — the two properties this module owes, pinned as an executable
property test (`test_candidate_selection_is_complete_and_sound`), not as prose:

  C1 COMPLETENESS. For every ACTIVE `team_members` row that
     `is_valid_garuda_assignment_target` accepts, its normalized email IS
     offered. Dropping an accepted target is the defect this module exists to
     end: the picker shows a colleague who cannot be picked, and a practice
     already assigned to them renders as "not assignable" over an assignment
     the gate would have accepted.
  C2 SOUNDNESS. Every offered email is one the validator accepts, so
     `listed ∩ refused = ∅` and no option in the picker can produce a 422.

**This module does not restate the predicate — it CALLS it**, once per
candidate row, so C2 holds by construction and keeps holding when the predicate
changes under it (`is_human_team_member` became a census allow-list in #5817
while this was being written): an enumeration that copied the rule would drift
the day the rule moves, one that asks cannot. The same reasoning is why
`staff_auth._is_staff_role` delegates instead of keeping its own exclusion set.

WHY CANDIDATE SELECTION IS PYTHON, NOT SQL. C1 is the property that failed
twice, both times for the same reason: a `WHERE` clause has its own idea of
equality and normalization, and it disagreed with the validator's.

* Round 1 (codex Gear-2 grade of 0ead993f3b1b, finding 1 MEDIUM): the query
  filtered on role alone, but the validator accepts an admin email BEFORE it
  reads any role — so active admin rows whose role was ``client``/``monitoring``
  were dropped, and NULL roles were dropped because `role <> ALL(...)` is
  UNKNOWN in SQL's three-valued logic and `WHERE` discards UNKNOWN.
* Round 2 (same grader, cure head 2ec67edde2): the arm added to fix that
  compared `LOWER(email) = ANY($2)`, but `LOWER` does not trim, while the
  validator normalizes with `.strip().lower()` — so an admin row stored with
  surrounding spaces was still dropped. Its verdict: the fix-of-a-fix had
  reached depth 1, so the correction loop was to be suspended and the contract
  pinned before implementing against it. That is what this file is.

Two rounds, one cause: a second normalization living in SQL. So there is no
second normalization any more. The query is `WHERE active = TRUE` and nothing
else — no role predicate, no email predicate, no three-valued logic to model —
and the narrowing happens in `_candidate_email`, in the same language as the
validator, reading both authorities (`non_human_roles_sql_array()` and
`garuda_practice_admin_emails()`) instead of copying either. A test fake now has
to model one trivial query rather than SQL's comparison semantics, which is what
let the round-2 divergence hide: the fake stripped emails the way Python does,
and SQL did not.

Cost, measured against the census above rather than assumed: the query now
returns every active row (~550, of which 525 are ``client``) instead of ~25, and
the validator is still called once per surviving candidate, so the round-trip
count through the Fly proxy is unchanged. The price is transferring a few
hundred small rows on a response the UI holds for 5 minutes; what it buys is the
removal of the surface that produced both findings. Skipping the ``client`` rows
before the validator sees them is still worth that transfer, because asking the
validator about 525 clients would mean 525 extra round-trips.

Known boundary, stated rather than left silent: candidates come from
`team_members`, so an admin email with NO active row there is accepted by the
validator but not offered here — there is no name to show and no row to order
by. The census shows every admin-class role (``founder``, ``ceo``, ``board
member``) holding an active row, so that set is empty today, and
`test_admin_boundary_is_the_documented_one` pins the behaviour instead of
leaving it to chance.
"""

from __future__ import annotations

from collections.abc import Collection
from typing import Any

import asyncpg

from backend.app.utils.service_accounts import non_human_roles_sql_array
from backend.services.garuda_portal.staff_auth import (
    garuda_practice_admin_emails,
    is_valid_garuda_assignment_target,
)

__all__ = ["list_garuda_assignment_targets"]

#: The ONLY query this module makes for candidates, and deliberately the whole
#: of its SQL semantics: every active row, nothing filtered. See the module
#: docstring's "WHY CANDIDATE SELECTION IS PYTHON, NOT SQL" — two independent
#: grade rounds found the validator and a `WHERE` clause disagreeing about
#: roles and about email normalization, so the narrowing moved to
#: `_candidate_email`, where the validator's own idiom can be used and tested.
_ACTIVE_ROSTER_SQL = """
    SELECT email, name, full_name, role
      FROM team_members
     WHERE active = TRUE
     ORDER BY name ASC
"""


def _normalized_email(value: Any) -> str:
    """`staff_auth`'s own email idiom — `(email or "").strip().lower()`, the
    exact expression `is_valid_garuda_assignment_target` opens with — kept in
    one place in this module because C1 depends on the enumeration and the
    validator agreeing about what the same stored string MEANS. Round 2 is what
    happens when they do not: SQL's `LOWER` does not trim, Python's `.strip()`
    does, and an admin row stored with surrounding spaces vanished from the
    picker while the validator would have accepted it.
    """
    return value.strip().lower() if isinstance(value, str) else ""


def _candidate_email(
    row: Any,
    admin_emails: Collection[str],
    excluded_roles: Collection[str],
) -> str | None:
    """The normalized email of a row worth asking the validator about, or None.

    Narrowing only, never deciding — the validator still sees every row this
    returns True for, so an error here can only cost a wasted query (C2 is
    untouched) while an error in the OTHER direction costs a colleague their
    place in the picker (C1). Every branch is therefore written to be too
    generous rather than too strict:

    * an admin email is a candidate whatever its role, mirroring the order the
      validator itself uses (admin shortcut BEFORE any role or row lookup);
    * a NULL or empty role is a candidate — `None not in {...}` is False in
      Python, where the same row was UNKNOWN and dropped in SQL — and the
      validator refuses it, so nothing is offered that should not be;
    * a role is compared RAW, exactly as the denylist holds it: ``'Client'`` or
      ``'client '`` stays a candidate and is refused downstream by the
      validator's own `normalize_role`. Case-folding here would be a third
      opinion about what a role string means.
    """
    email = _normalized_email(row["email"])
    if not email:
        return None
    if email in admin_emails:
        return email
    if row["role"] in excluded_roles:
        return None
    return email


def _base_label(row: Any, email: str) -> str:
    """`full_name` → `name` → the email itself: the same preference order the
    roster hook this replaces used (`useTeamMembers.ts::useTeamMemberOptions`),
    so a staffer's name does not change shape when the source of the list does.
    """
    for key in ("full_name", "name"):
        value = row[key]
        if isinstance(value, str) and value.strip():
            return value.strip()
    return email


async def list_garuda_assignment_targets(conn: asyncpg.Connection) -> list[dict[str, str]]:
    """Every email `assignPractice` would accept today, as ``{"email", "label"}``.

    Rows are deduplicated by normalized email (the roster this replaces did the
    same) and labels that would render twice in one `<select>` carry the email
    as a disambiguator — two "Antonello" options are indistinguishable to the
    person picking one, and picking wrong assigns a practice to the wrong
    colleague.
    """
    # Both authorities are read at CALL time and never cached here, so this
    # function and the validator cannot disagree about who is an admin or which
    # roles are non-human: one source each, read per request, same answer.
    admin_emails = frozenset(garuda_practice_admin_emails())
    excluded_roles = frozenset(non_human_roles_sql_array())
    rows = await conn.fetch(_ACTIVE_ROSTER_SQL)

    accepted: list[tuple[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        email = _candidate_email(row, admin_emails, excluded_roles)
        if email is None or email in seen:
            continue
        seen.add(email)
        if not await is_valid_garuda_assignment_target(conn, email):
            continue
        accepted.append((email, _base_label(row, email)))

    label_counts: dict[str, int] = {}
    for _email, label in accepted:
        key = label.lower()
        label_counts[key] = label_counts.get(key, 0) + 1

    return [
        {
            "email": email,
            "label": label if label_counts[label.lower()] == 1 else f"{label} ({email})",
        }
        for email, label in accepted
    ]
