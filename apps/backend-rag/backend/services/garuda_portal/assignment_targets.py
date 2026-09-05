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

**This module does not restate the predicate — it CALLS it**, once per
candidate row. `listed ∩ refused = ∅` therefore holds by construction, and
keeps holding when the predicate changes under it (PR #5817 is turning
`service_accounts.is_human_team_member` from a denylist into a census
allow-list at the time of writing): an enumeration that copied the rule would
drift the day the rule moves, one that asks cannot. The same reasoning is why
`staff_auth._is_staff_role` delegates instead of keeping its own exclusion set.

Cost: one candidate query plus one point query per candidate row (~25 active
non-client rows against 525 active ``client`` rows, per the census above), on a
response the UI holds for 5 minutes. Cheap enough not to need a cache of its
own, and no cache means no second place to invalidate.

Known boundary, stated rather than left silent: candidates come from
`team_members`, so an email in `staff_auth._garuda_practice_admin_emails()`
that has NO active row there is accepted by the validator but not offered here.
The census shows every admin-class role (``founder``, ``ceo``, ``board member``)
holding an active row, so the set is empty today; widening the candidate query
to union the admin constant would mean either importing that private helper or
restating it — a second copy of a policy set, which is the exact drift this
module exists to avoid.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from backend.app.utils.service_accounts import non_human_roles_sql_array
from backend.services.garuda_portal.staff_auth import is_valid_garuda_assignment_target

__all__ = ["list_garuda_assignment_targets"]

#: PERFORMANCE PREFILTER, never the authority. `NON_HUMAN_ROLES`
#: ({``client``, ``monitoring``}) is a subset of everything
#: `is_valid_garuda_assignment_target` refuses — both roles are in
#: `NON_TEAM_ROLES` today, and neither is a team role under the census
#: allow-list PR #5817 introduces — so dropping them here cannot drop a row the
#: validator would accept. It exists because `team_members` holds 525 active
#: `client` rows next to ~25 staff rows, and asking the validator about a
#: client is a wasted query. The validator still sees every remaining row and
#: is still the only thing that decides.
_CANDIDATE_SQL = """
    SELECT email, name, full_name, role
      FROM team_members
     WHERE active = TRUE
       AND role <> ALL($1::text[])
     ORDER BY name ASC
"""


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
    rows = await conn.fetch(_CANDIDATE_SQL, non_human_roles_sql_array())

    accepted: list[tuple[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        raw_email = row["email"]
        email = raw_email.strip().lower() if isinstance(raw_email, str) else ""
        if not email or email in seen:
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
