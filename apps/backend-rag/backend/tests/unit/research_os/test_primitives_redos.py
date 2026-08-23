"""Regression guard for the CodeQL py/redos findings on PR #4586.

`_IDENTIFIER_RE` and `_REGISTERED_NAME_RE` in `research_os.primitives` used to
have `*`/`+` quantifiers whose body character class overlapped the separator
character class that follows them (hyphen in both, and for
`_REGISTERED_NAME_RE` underscore too). That overlap let the backtracking
engine parse the same run of hyphens/underscores as "body" or as
"separator + next repetition" in exponentially many ways, so a pathological
input took seconds on a ~30-50 character string.

Measured on this machine BEFORE the fix (plain `*`/`+`, alarm-timed,
`re.Pattern.fullmatch`):

    _IDENTIFIER_RE       "a" + "-"*n + "!"    n=26 ->    8.71 ms
                                                n=32 ->  154.77 ms
    _REGISTERED_NAME_RE  "a" + "-0"*n + "!"   n=26 -> 1760.59 ms
                                                n=28 -> 7024.26 ms

The fix is a restructuring to disjoint character classes -- NOT possessive
quantifiers (`*+`/`++`). An earlier version of this fix used possessives,
which resolve the ambiguity for Python's `re` but do not exist in ECMA-262
(the dialect JSON Schema's "pattern" keyword is specified against, since
these same compiled patterns' `.pattern` text is reused verbatim as
`Field(pattern=...)` and flows into the checked-in cross-language
schemas/*.schema.json). `_IDENTIFIER_RE` drops the redundant `-` from its
separator class (`-` was already accepted by the body class, so the
separator reduces to a bare `\\.`, leaving body and separator strictly
disjoint). `_REGISTERED_NAME_RE` needed real restructuring: a mandatory
`[._-][a-z0-9]` opening followed by a tail loop offering two
first-character-disjoint alternatives (`[a-z0-9_-]` or `\\.[a-z0-9]`), so
the engine never has two ways to consume the same character. See
`test_every_schema_pattern_compiles_under_ecma_262` in test_schemas.py for
the guard that a possessive (or any other ECMA-incompatible) variant would
trip.

AFTER the fix, both patterns resolve the same pathological inputs in well
under a millisecond -- these tests pin that with a threshold that the
pre-fix regex would have blown through by 1-3 orders of magnitude, so a
regression (someone reintroducing a plain, ambiguous `*`/`+` here) fails
loudly instead of silently degrading back into a ReDoS.
"""

from __future__ import annotations

import time

from research_os.primitives import _IDENTIFIER_RE, _REGISTERED_NAME_RE

# Generous relative to the <1ms the fixed regex actually takes, but far
# below the 154ms / 1760ms the vulnerable regex took on the same inputs.
_FAST_THRESHOLD_SECONDS = 0.1


def test_identifier_re_resolves_pathological_hyphen_run_fast() -> None:
    pathological = "a" + "-" * 32 + "!"

    start = time.perf_counter()
    result = _IDENTIFIER_RE.fullmatch(pathological)
    elapsed = time.perf_counter() - start

    assert result is None  # trailing "!" is never valid -- must still reject
    assert elapsed < _FAST_THRESHOLD_SECONDS, (
        f"_IDENTIFIER_RE took {elapsed * 1000:.2f} ms on a pathological input "
        f"(threshold {_FAST_THRESHOLD_SECONDS * 1000:.0f} ms) -- possible ReDoS regression"
    )


def test_registered_name_re_resolves_pathological_hyphen_digit_run_fast() -> None:
    pathological = "a" + "-0" * 26 + "!"

    start = time.perf_counter()
    result = _REGISTERED_NAME_RE.fullmatch(pathological)
    elapsed = time.perf_counter() - start

    assert result is None  # trailing "!" is never valid -- must still reject
    assert elapsed < _FAST_THRESHOLD_SECONDS, (
        f"_REGISTERED_NAME_RE took {elapsed * 1000:.2f} ms on a pathological input "
        f"(threshold {_FAST_THRESHOLD_SECONDS * 1000:.0f} ms) -- possible ReDoS regression"
    )


def test_identifier_re_still_accepts_representative_valid_identifiers() -> None:
    for value in ("a", "a-b", "a.b-c", "a_b.c-d", "a" + "-" * 20, "a" + "." + "0" * 5):
        assert _IDENTIFIER_RE.fullmatch(value) is not None, value


def test_identifier_re_still_rejects_representative_invalid_identifiers() -> None:
    for value in ("", "A", "1abc", "a.", "a..b", "-a", "a b"):
        assert _IDENTIFIER_RE.fullmatch(value) is None, value


def test_registered_name_re_still_accepts_representative_valid_names() -> None:
    for value in ("a.b", "a-b0", "a_b", "com.balizero.example", "a0.b_c-d9"):
        assert _REGISTERED_NAME_RE.fullmatch(value) is not None, value


def test_registered_name_re_still_rejects_representative_invalid_names() -> None:
    for value in ("", "a", "abc", "a.", "a..b", "a-", "a__", "A.b", ".ab"):
        assert _REGISTERED_NAME_RE.fullmatch(value) is None, value
