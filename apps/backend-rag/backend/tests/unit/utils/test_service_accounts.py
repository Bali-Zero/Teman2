"""A service account is not a colleague — and every people-shaped query knows it.

Guilt and innocence for `backend/app/utils/service_accounts.py`, plus a
class-audit test: the point of the module is that the exclusion set lives in ONE
place, so a test that only checked the helper would pass while a call site
quietly kept its own hand-written `NOT IN ('client')`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.app.utils.service_accounts import (
    CLIENT_ROLES,
    NON_HUMAN_ROLES,
    NON_HUMAN_ROLES_SQL,
    SERVICE_ROLES,
    _sql_literal_list,
    is_human_team_member,
    non_human_roles_sql_array,
)

ROUTERS = Path(__file__).resolve().parents[3] / "app" / "routers"
DEPS = Path(__file__).resolve().parents[3] / "app" / "deps"


class TestIsHumanTeamMember:
    @pytest.mark.parametrize("role", sorted(NON_HUMAN_ROLES))
    def test_clients_and_service_accounts_are_not_people(self, role: str) -> None:
        assert is_human_team_member(role) is False

    @pytest.mark.parametrize(
        "role",
        ["Tax Lead", "admin", "Founder", "Reception", "member", "Specialist Advisor"],
    )
    def test_real_roles_still_count_as_people(self, role: str) -> None:
        """Innocence: this must not degenerate into 'exclude anything unfamiliar'.

        Every role here is held by a real person in the live team_members table.
        """
        assert is_human_team_member(role) is True

    def test_role_matching_ignores_case_and_padding(self) -> None:
        assert is_human_team_member("  MONITORING  ") is False
        assert is_human_team_member("Client") is False

    def test_the_two_sets_are_disjoint(self) -> None:
        assert not (CLIENT_ROLES & SERVICE_ROLES)
        assert NON_HUMAN_ROLES == CLIENT_ROLES | SERVICE_ROLES


class TestSqlRendering:
    def test_literal_is_sorted_and_quoted(self) -> None:
        assert NON_HUMAN_ROLES_SQL == "'client', 'monitoring'"

    def test_array_is_sorted(self) -> None:
        assert non_human_roles_sql_array() == sorted(NON_HUMAN_ROLES)

    def test_a_role_that_cannot_be_inlined_is_refused_not_escaped(self) -> None:
        """The guard must raise rather than silently produce injectable SQL."""
        with pytest.raises(ValueError, match="bare token"):
            _sql_literal_list(frozenset({"we're not a token"}))

    def test_rejects_a_role_carrying_a_sql_comment(self) -> None:
        with pytest.raises(ValueError, match="bare token"):
            _sql_literal_list(frozenset({"client'--"}))


class TestNoCallSiteKeepsItsOwnCopy:
    """Class-audit: the exclusion set must not be re-hardcoded anywhere.

    This is the test that would have failed BEFORE the fix, when four routers
    each carried their own `role NOT IN ('client')`. It is here so the fifth
    call site cannot be added by hand.
    """

    HARDCODED = re.compile(
        r"""role\s*(?:!=|<>)\s*'client'|role\s+NOT\s+IN\s*\(\s*'client'\s*\)""",
        re.IGNORECASE,
    )

    def test_no_router_hardcodes_the_client_only_exclusion(self) -> None:
        offenders: list[str] = []
        for path in sorted(ROUTERS.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            for match in self.HARDCODED.finditer(text):
                line_no = text.count("\n", 0, match.start()) + 1
                offenders.append(f"{path.name}:{line_no}: {match.group(0)}")

        assert not offenders, (
            "these queries partition team-vs-client by hand instead of using "
            "service_accounts.NON_HUMAN_ROLES, so a service account would be "
            "counted as a colleague:\n  " + "\n  ".join(offenders)
        )

    def test_the_probe_finds_the_pattern_it_is_looking_for(self) -> None:
        """Innocence for the probe itself: a regex that matches nothing proves nothing.

        Without this, deleting the routers directory would make the test above
        pass (W107 — the probe that measures its own poverty).
        """
        assert self.HARDCODED.search("WHERE role != 'client'")
        assert self.HARDCODED.search("WHERE tm.role NOT IN ('client')")
        assert not self.HARDCODED.search("WHERE role <> ALL($2::text[])")

    def test_the_routers_directory_was_actually_scanned(self) -> None:
        assert len(list(ROUTERS.glob("*.py"))) > 10, (
            f"expected the routers package at {ROUTERS}, found almost nothing — "
            "the audit above would pass vacuously"
        )


class TestNoCallSiteUsesClientAsAProxyForStaff:
    """Class-audit, generalized (2026-08-19 audit, Defect 2): the SQL-level
    audit above (``role NOT IN ('client')``) is blind to the Python-level
    equivalent — ``current_user.get("role") == "client"`` — which is exactly
    the form four LIVE dependency/guard functions used to grant team-level
    authority (require_team_member, require_team_auth, and inline checks in
    portal_invite.py + agentic_rag.py). "Not a client" is not the same
    question as "is a colleague"; a service account passes the old check.

    This is the test that would have failed BEFORE the fix. It scans both
    routers/ and deps/ — the earlier audit missed deps/auth.py entirely
    because it only ever looked at routers/.
    """

    HARDCODED = re.compile(
        r"""\.get\(\s*['"]role['"][^)]*\)\s*(?:==|!=)\s*['"]client['"]"""
        r"""|\[\s*['"]role['"]\s*\]\s*(?:==|!=)\s*['"]client['"]""",
        re.IGNORECASE,
    )

    #: Files that compare role to the literal "client" for a purpose OTHER
    #: than "is this not a client, therefore staff" (Defect 2's bug shape).
    #: auth.py asks "IS this a client" to populate client-only JWT/profile
    #: fields and drive login-redirect logic — the opposite direction, and
    #: explicitly verified correct (login 403 + the auto-clockin guard are
    #: out of scope for this audit). portal.py's endpoints are client-portal
    #: -only by design (module docstring: "All endpoints require client
    #: authentication"), so denying non-clients there is the intended
    #: admission gate, not a staff-authority proxy a service account could
    #: exploit. Both were carved out deliberately, not overlooked — same
    #: spirit as NON_ROUTER_FILES in test_router_manifest.py.
    ACCESS_GATE_ALLOWLIST = frozenset({"auth.py", "portal.py"})

    def _scan(self, root: Path) -> list[str]:
        offenders: list[str] = []
        for path in sorted(root.glob("*.py")):
            if path.name in self.ACCESS_GATE_ALLOWLIST:
                continue
            text = path.read_text(encoding="utf-8")
            for match in self.HARDCODED.finditer(text):
                line_no = text.count("\n", 0, match.start()) + 1
                offenders.append(f"{path.name}:{line_no}: {match.group(0)}")
        return offenders

    def test_no_router_or_dep_hardcodes_the_client_only_exclusion(self) -> None:
        offenders = self._scan(ROUTERS) + self._scan(DEPS)
        assert not offenders, (
            "these checks partition team-vs-client by hand instead of using "
            "service_accounts.is_human_team_member, so a service account would pass "
            "a guard meant to gate team-level authority:\n  " + "\n  ".join(offenders)
        )

    def test_the_probe_finds_the_pattern_it_is_looking_for(self) -> None:
        assert self.HARDCODED.search('if user.get("role") == "client":')
        assert self.HARDCODED.search("if current_user.get('role') == 'client':")
        assert self.HARDCODED.search('current_user["role"] == "client" and x != y')
        assert not self.HARDCODED.search("is_human_team_member(current_user.get(\"role\"))")
        assert not self.HARDCODED.search('user.get("role") == "admin"')

    def test_the_deps_directory_was_actually_scanned(self) -> None:
        assert len(list(DEPS.glob("*.py"))) >= 3, (
            f"expected the deps package at {DEPS}, found almost nothing — "
            "the audit above would pass vacuously"
        )

    def test_allowlist_entries_still_exist_and_still_need_the_exemption(self) -> None:
        """An exemption is an assertion about the file, not a formality
        (W109): if auth.py/portal.py are ever rewritten to no longer contain
        this pattern, the allowlist entry becomes a silent, unneeded blind
        spot in the audit and must be removed."""
        for name in self.ACCESS_GATE_ALLOWLIST:
            path = ROUTERS / name
            assert path.is_file(), f"{name} is allowlisted but no longer exists — remove it"
            text = path.read_text(encoding="utf-8")
            assert self.HARDCODED.search(text), (
                f"{name} is allowlisted as a deliberate exception, but no longer contains "
                "the pattern — remove the now-unnecessary exemption"
            )
