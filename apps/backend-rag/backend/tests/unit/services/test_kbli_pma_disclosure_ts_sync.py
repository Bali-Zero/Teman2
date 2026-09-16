"""Cross-language drift tripwire for BALI_ALLOWED_STATUSES.

`apps/mouth/src/lib/kbli-pma-disclosure.ts` hand-copies this module's
`BALI_ALLOWED_STATUSES` frozenset into a TypeScript `Set` literal
(`ALLOWED_BALI_STATUSES`), because the two languages cannot share a constant.
That copy is a comment promising sync, not a mechanism enforcing it, and it
has exactly the shape of the defect this module's own docstring warns about:
two sides that must agree, each internally consistent, with nothing making
them agree. Add a new Bali status on one side and forget the other, and every
test on BOTH sides stays green while the frontend silently drops a whole
`l4_bali` verdict (`discloseBaliL4` returns `undefined` for anything not in
its set) or the backend admits a status the frontend has never heard of.

Same pattern as `test_service_accounts_ts_sync.py::TestNonHumanRolesStaysInSyncWithPython`
(NON_HUMAN_ROLES / TEAM_ROLES): read the TS source as plain text (no bundler,
no AST parser — a tripwire, not a build step), extract the Set literal, and
compare as SETS, never as text, so formatting/ordering can never flip it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.services.kbli_pma_disclosure import BALI_ALLOWED_STATUSES

# Six levels up from this file (services -> unit -> tests -> backend ->
# backend-rag -> apps) reaches the repo root — same convention and same depth
# as test_service_accounts_ts_sync.py's _TS_HOOK_PATH (utils -> unit -> tests
# -> backend -> backend-rag -> apps).
_TS_MODULE_PATH = (
    Path(__file__).resolve().parents[6]
    / "apps"
    / "mouth"
    / "src"
    / "lib"
    / "kbli-pma-disclosure.ts"
)

_ALLOWED_BALI_STATUSES_TS_RE = re.compile(
    r"const\s+ALLOWED_BALI_STATUSES\s*=\s*new\s+Set\(\s*\[(?P<items>[^\]]*)\]\s*\)",
)

_STRING_LITERAL_RE = re.compile(r"""["']([^"']+)["']""")


def _extract_ts_allowed_bali_statuses(source: str) -> set[str]:
    """Parse the `ALLOWED_BALI_STATUSES` Set literal out of TS source as text.

    Raises if the declaration cannot be found at all, so a rename or a
    reformat past what this regex tolerates breaks this test LOUDLY instead
    of silently comparing against an empty extracted set and passing for the
    wrong reason — an empty-vs-empty comparison is a vacuous pass, and a
    vacuous pass is how a tripwire becomes decorative.
    """
    match = _ALLOWED_BALI_STATUSES_TS_RE.search(source)
    if match is None:
        raise AssertionError(
            "Could not find `const ALLOWED_BALI_STATUSES = new Set([...])` in "
            f"{_TS_MODULE_PATH} — the declaration was renamed, reformatted "
            "past what this regex tolerates, or removed. Update this test's "
            "extraction pattern to match the new shape; do not delete this "
            "test or weaken it to skip on a miss."
        )
    return set(_STRING_LITERAL_RE.findall(match.group("items")))


class TestBaliAllowedStatusesStaysInSyncWithTypeScript:
    """Guilt + innocence for the cross-language sync itself."""

    def test_python_and_ts_allow_the_same_bali_status_vocabulary(self) -> None:
        """Guilt: a status present on only one side must fail this test.

        Compared as SETS, never as source text — element order in the TS
        array literal and whitespace/quote-style must never make this flaky.
        """
        assert _TS_MODULE_PATH.is_file(), f"expected TS module at {_TS_MODULE_PATH}"

        ts_statuses = _extract_ts_allowed_bali_statuses(_TS_MODULE_PATH.read_text())

        # Non-vacuity: an empty extracted set would trivially equal an empty
        # Python set and pass for the wrong reason.
        assert ts_statuses, (
            "Extracted an EMPTY status set from the TS declaration in "
            f"{_TS_MODULE_PATH} — that is almost certainly a bug in this "
            "test's extraction regex, not a real empty set."
        )

        python_statuses = set(BALI_ALLOWED_STATUSES)
        assert ts_statuses == python_statuses, (
            f"Frontend ALLOWED_BALI_STATUSES {sorted(ts_statuses)} in "
            f"{_TS_MODULE_PATH} has drifted from the Python SSOT "
            f"BALI_ALLOWED_STATUSES {sorted(python_statuses)} in "
            "kbli_pma_disclosure.py. A status present on only one side means "
            "either the frontend silently drops a whole l4_bali verdict "
            "(discloseBaliL4 returns undefined for anything not in its set) "
            "or the backend admits a status the frontend has never heard of."
        )

    def test_extraction_raises_when_the_declaration_is_absent(self) -> None:
        """Innocence of the tripwire itself: prove the fail-loud path fires.

        Without this, a future edit to the regex could quietly go vacuous
        (always match, or always return an empty set) and nothing above
        would ever notice, because the guilt test only runs against the
        real, currently-matching file.
        """
        with pytest.raises(AssertionError, match="Could not find"):
            _extract_ts_allowed_bali_statuses(
                "// ALLOWED_BALI_STATUSES was removed here\n"
            )

    def test_extraction_ignores_an_unrelated_set_literal(self) -> None:
        """Innocence: a same-shaped Set for something else must not match.

        Guards against a regex broad enough to grab the wrong declaration
        and report a false sync (or false drift) against unrelated code.
        """
        source = 'const SOME_OTHER_SET = new Set(["foo", "bar"]);\n'
        with pytest.raises(AssertionError, match="Could not find"):
            _extract_ts_allowed_bali_statuses(source)
