"""Which `team_members` rows are people, and which are machines.

Several call sites partition "team" from "client" by testing the role against
the literal string ``client``. That test answers *"is this not a client"*,
which is not the same question as *"is this a person"*. A service account — an
unattended probe, a bot — is neither. The two questions returned the same
answer only for as long as no service account carried a non-client role.

Anything that produces a human-facing artifact must exclude
:data:`SERVICE_ROLES` as well as clients:

* an attendance record (``team_timesheet``) — a probe must never clock in;
* a headcount — a probe is not a colleague;
* an assignment dropdown — a client must never be assignable to a machine.

Checks that merely gate *access* are deliberately left alone: they ask "is this
caller allowed here", and for those a service account genuinely is a
non-client. See the module-level note in ``services/whatsapp_identity.py`` for
one such case that is correct as written.

External partners are the third class. A partner is a person — reached through
the partner portal (``/portal/partner``, see ``routers/auth.py::_redirect_for_role``
and ``routers/partners.py::_is_partner_role``) — who is not on the team. The
platform copies ``team_members.role`` verbatim into the JWT, so a ``partner``
token reaches every gate a colleague's does. :func:`is_human_team_member`
refuses it; :data:`NON_HUMAN_ROLES` and its SQL renderings deliberately do
NOT list it, because whether a partner belongs in a roster or a dropdown is a
product decision, not an authentication one.

This module imports nothing itself, and the package it lives in
(``backend.app.utils``) is kept free of import-time settings access, so
importing this module never requires production secrets to be configured.
"""

from __future__ import annotations

#: Roles whose holder is an end customer, reached through the client portal.
CLIENT_ROLES = frozenset({"client"})

#: Roles held by unattended machines that authenticate like team members.
#: ``monitoring`` is the login-healthcheck probe, which authenticates against
#: kita every 5 minutes to prove the operator door is open.
SERVICE_ROLES = frozenset({"monitoring"})

#: Everything that must be excluded from people-shaped artifacts.
NON_HUMAN_ROLES = CLIENT_ROLES | SERVICE_ROLES

#: Roles held by people who are not on the team: external partners, who log in
#: through the same door as staff and land on ``/portal/partner``.
EXTERNAL_ROLES = frozenset({"partner"})

#: Everything an "is this caller a colleague" gate must refuse.
NON_TEAM_ROLES = NON_HUMAN_ROLES | EXTERNAL_ROLES


def normalize_role(role: str | None) -> str:
    """Return a role in the canonical form the comparisons below expect."""
    return (role or "").strip().lower()


def is_human_team_member(role: str | None) -> bool:
    """True when the role belongs to a person on the team.

    Neither clients, service accounts nor external partners qualify.
    """
    return normalize_role(role) not in NON_TEAM_ROLES


def non_human_roles_sql_array() -> list[str]:
    """The exclusion set as a sorted list, for ``role <> ALL($n::text[])``.

    Sorted so a query plan and a test assertion both see a stable order.
    """
    return sorted(NON_HUMAN_ROLES)


def _sql_literal_list(roles: frozenset[str]) -> str:
    """Render roles as a SQL ``IN`` list, refusing anything not a bare token.

    These roles are compile-time constants declared in this module, never user
    input, so interpolating them carries no injection risk — but a future
    contributor could add a role with a quote in it, so the guard is asserted
    rather than assumed.

    Two mechanisms exist because the call sites differ: this literal serves the
    queries that take no positional parameters, while
    :func:`non_human_roles_sql_array` serves the ones that already do, where a
    bind parameter is both idiomatic and avoids turning a multi-CTE query
    containing braces into an f-string.
    """
    for role in roles:
        if not role or not all(ch.isalpha() or ch == "_" for ch in role):
            raise ValueError(
                f"role {role!r} is not a bare token and cannot be inlined into SQL; "
                "use a bind parameter for it instead"
            )
    return ", ".join(f"'{role}'" for role in sorted(roles))


#: Ready-to-interpolate SQL fragment: ``WHERE role NOT IN (NON_HUMAN_ROLES_SQL)``.
NON_HUMAN_ROLES_SQL = _sql_literal_list(NON_HUMAN_ROLES)
