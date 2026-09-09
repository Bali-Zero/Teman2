"""Cross-language drift tripwire for NON_HUMAN_ROLES.

`apps/mouth/src/hooks/useTeamMembers.ts` hand-copies the Python SSOT
(`service_accounts.py::NON_HUMAN_ROLES`) into a TypeScript `Set` literal,
because the two languages cannot share a constant. That copy is a comment
promising sync, not a mechanism enforcing it — and it has exactly the shape
of the defect this whole module exists to close: two sides that must agree,
each internally consistent, with nothing making them agree. Add a third
service role to the Python side and forget the TS side, and every test on
BOTH sides stays green while a machine reappears in the human roster and
every assignment dropdown that reads it.

This test is the mechanism. It reads the TS source as plain text (no
bundler, no AST parser — a tripwire, not a build step), extracts the
`NON_HUMAN_ROLES` Set literal, and compares it against the Python SSOT as
sets, not as text, so formatting/ordering can never flip it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.app.utils.service_accounts import NON_HUMAN_ROLES, TEAM_ROLES

# Six levels up from this file (utils -> unit -> tests -> backend ->
# backend-rag -> apps) reaches the repo root, same convention as
# test_service_accounts.py's ROUTERS/DEPS (parents[3] -> backend) and
# test_router_manifest.py's ROUTERS_DIR (parents[2] -> backend), extended
# three more levels to cross out of apps/backend-rag entirely.
_TS_HOOK_PATH = (
    Path(__file__).resolve().parents[6] / "apps" / "mouth" / "src" / "hooks" / "useTeamMembers.ts"
)

_NON_HUMAN_ROLES_TS_RE = re.compile(
    r"const\s+NON_HUMAN_ROLES\s*=\s*new\s+Set\(\s*\[(?P<items>[^\]]*)\]\s*\)",
)

_TEAM_ROLES_TS_RE = re.compile(
    r"const\s+TEAM_ROLES\s*=\s*new\s+Set\(\s*\[(?P<items>[^\]]*)\]\s*\)",
)

_STRING_LITERAL_RE = re.compile(r"""["']([^"']+)["']""")


def _extract_ts_non_human_roles(source: str) -> set[str]:
    """Parse the `NON_HUMAN_ROLES` Set literal out of TS source as text.

    Raises if the declaration cannot be found at all, so a rename or a
    reformat past what this regex tolerates breaks this test LOUDLY instead
    of silently comparing against an empty extracted set and passing for the
    wrong reason — an empty-vs-empty comparison is a vacuous pass, and a
    vacuous pass is how a tripwire becomes decorative.
    """
    match = _NON_HUMAN_ROLES_TS_RE.search(source)
    if match is None:
        raise AssertionError(
            "Could not find `const NON_HUMAN_ROLES = new Set([...])` in "
            f"{_TS_HOOK_PATH} — the declaration was renamed, reformatted "
            "past what this regex tolerates, or removed. Update this "
            "test's extraction pattern to match the new shape; do not "
            "delete this test or weaken it to skip on a miss."
        )
    return set(_STRING_LITERAL_RE.findall(match.group("items")))


class TestNonHumanRolesStaysInSyncWithPython:
    """Guilt + innocence for the cross-language sync itself."""

    def test_ts_hook_declares_the_same_roles_as_the_python_ssot(self) -> None:
        """Guilt: a role present on only one side must fail this test.

        Compared as SETS, never as source text — element order in the TS
        array and whitespace/quote-style must never make this flaky.
        """
        assert _TS_HOOK_PATH.is_file(), f"expected TS hook file at {_TS_HOOK_PATH}"

        ts_roles = _extract_ts_non_human_roles(_TS_HOOK_PATH.read_text())

        # Non-vacuity: an empty extracted set would trivially equal an empty
        # Python set and pass for the wrong reason. NON_HUMAN_ROLES is a
        # frozenset with 'client' and 'monitoring' today and is asserted
        # non-empty by test_service_accounts.py already, so this guards the
        # EXTRACTION, not the SSOT.
        assert ts_roles, (
            "Extracted an EMPTY role set from the TS declaration in "
            f"{_TS_HOOK_PATH} — that is almost certainly a bug in this "
            "test's extraction regex, not a real empty set."
        )

        python_roles = set(NON_HUMAN_ROLES)
        assert ts_roles == python_roles, (
            f"Frontend NON_HUMAN_ROLES {sorted(ts_roles)} in "
            f"{_TS_HOOK_PATH} has drifted from the Python SSOT "
            f"{sorted(python_roles)} in service_accounts.py. A role present "
            "on only one side means either a service account leaks into a "
            "human-facing roster/dropdown (TS is missing a role Python has) "
            "or a real colleague is silently excluded from one (TS has a "
            "role Python doesn't)."
        )

    def test_extraction_raises_when_the_declaration_is_absent(self) -> None:
        """Innocence of the tripwire itself: prove the fail-loud path fires.

        Without this, a future edit to the regex could quietly go vacuous
        (always match, or always return an empty set) and nothing above
        would ever notice, because the guilt test only runs against the
        real, currently-matching file.
        """
        with pytest.raises(AssertionError, match="Could not find"):
            _extract_ts_non_human_roles("// NON_HUMAN_ROLES was removed here\n")

    def test_extraction_ignores_an_unrelated_set_literal(self) -> None:
        """Innocence: a same-shaped Set for something else must not match.

        Guards against a regex broad enough to grab the wrong declaration
        and report a false sync (or false drift) against unrelated code.
        """
        source = 'const SOME_OTHER_SET = new Set(["foo", "bar"]);\n'
        with pytest.raises(AssertionError, match="Could not find"):
            _extract_ts_non_human_roles(source)


class TestTeamRolesStaysInSyncWithPython:
    """The allow-list mirror (PENDING-ARMS row 88): same guilt as above, other set."""

    def test_ts_hook_declares_the_same_allow_list_as_the_python_ssot(self) -> None:
        source = _TS_HOOK_PATH.read_text()
        match = _TEAM_ROLES_TS_RE.search(source)
        assert match is not None, (
            f"Could not find `const TEAM_ROLES = new Set([...])` in {_TS_HOOK_PATH} — "
            "renamed, reformatted past this regex, or removed. Fix the pattern, never skip."
        )
        ts_roles = set(_STRING_LITERAL_RE.findall(match.group("items")))
        assert ts_roles, "extracted an EMPTY TEAM_ROLES set — extraction bug, not a real set"
        assert ts_roles == set(TEAM_ROLES), (
            f"Frontend TEAM_ROLES {sorted(ts_roles)} has drifted from the Python SSOT "
            f"{sorted(TEAM_ROLES)}: a colleague the backend admits would be unknown to "
            "the frontend, or the frontend would call someone a colleague the gate refuses."
        )

    def test_the_two_mirrors_never_overlap(self) -> None:
        source = _TS_HOOK_PATH.read_text()
        non_human = _extract_ts_non_human_roles(source)
        team = set(_STRING_LITERAL_RE.findall(_TEAM_ROLES_TS_RE.search(source).group("items")))
        assert not (non_human & team)
