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
