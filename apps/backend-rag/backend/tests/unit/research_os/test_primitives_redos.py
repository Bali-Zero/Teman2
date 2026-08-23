"""Guard the two canonical-name regexes against catastrophic backtracking.

CodeQL raised two high-severity `py/redos` alerts against
`packages/research-os-core/research_os/primitives.py` (lines 29-30 as merged in
PR #4586, which merged with that check red). The alerts were real: the separator
character class overlapped the body class beside it, so `_` and `-` belonged to
both and a run of them could be split between the two roles in exponentially many
ways. Measured on the pre-cure patterns before writing this file: a 46-character
non-match took 1.0s, and every further 2 characters doubled it — so an ~80
character input stalls for minutes. Both patterns back `Field(pattern=...)`
validators (`RegisteredName`, `Identifier`), so the input is attacker-controlled
by construction.

Three independent properties, deliberately not the same claim:

* STRUCTURE  — the separator and body classes must stay disjoint. This is the
               root cause, and it fails INSTANTLY on a reintroduced pattern.
* TIMING     — the exponential blowup must be gone, measured rather than argued.
               Sized so a reintroduced pattern fails in about a second: `re.match`
               runs in C and cannot be interrupted by a signal, so a guard aimed
               at a longer input would hang the CI job instead of failing it.
               (Learned the hard way — an earlier draft of this file used
               `repeats=48` and ran past 600s against the vulnerable pattern
               without ever reporting.)
* LANGUAGE   — the cure must not have quietly narrowed what the canonical grammar
               accepts. Proven exhaustively, not by example.
"""

from __future__ import annotations

import itertools
import re
import time

import pytest
from research_os.primitives import _IDENTIFIER_RE, _REGISTERED_NAME_RE

# The exact patterns as they stood on main before the cure. Used ONLY as the
# reference for the equivalence proof, and ONLY against the short generated
# strings below — never against adversarial input.
PRE_CURE_REGISTERED_NAME = r"^[a-z][a-z0-9]*(?:[._-][a-z0-9][a-z0-9_-]*)+$"
PRE_CURE_IDENTIFIER = r"^[a-z][a-z0-9_-]*(?:[.-][a-z0-9_-]+)*$"

PATTERNS = [
    (_REGISTERED_NAME_RE, PRE_CURE_REGISTERED_NAME, "_REGISTERED_NAME_RE"),
    (_IDENTIFIER_RE, PRE_CURE_IDENTIFIER, "_IDENTIFIER_RE"),
]

# Every character class in play: a letter, a digit, and all three characters that
# appear in some separator class (`.`, `_`, `-`). The wider alphabet catches
# anything needing two distinct letters or digits; shorter strings keep it cheap.
ALPHABET = "a0_-."
WIDE_ALPHABET = "ab01_-."


def _all_strings(alphabet: str, max_len: int):
    for n in range(1, max_len + 1):
        for tup in itertools.product(alphabet, repeat=n):
            yield "".join(tup)


@pytest.mark.parametrize(("pattern", "_pre_cure", "name"), PATTERNS)
def test_separator_and_body_classes_stay_disjoint(pattern, _pre_cure, name):
    """STRUCTURE: the root cause, asserted directly so it fails instantly.

    A repeated group whose separator class shares a character with the body class
    beside it is the ReDoS condition. `-` and `_` live in the body class already,
    so neither ever needed to be a separator; only `.` adds expressive power.
    """
    source = pattern.pattern
    assert "[.-]" not in source, (
        f"{name} uses separator class [.-], which shares '-' with its body class "
        f"[a-z0-9_-] — that overlap is the py/redos condition"
    )
    # `[._-]` is permitted at most once: in _REGISTERED_NAME_RE it is the single
    # mandatory first separator, preceded by [a-z0-9], which is disjoint from it.
    # Inside a REPEATED group it would reintroduce the blowup.
    assert source.count("[._-]") <= 1, (
        f"{name} uses [._-] more than once; every repeated separator must be the "
        f"disjoint literal '\\.'"
    )


@pytest.mark.parametrize(("pattern", "_pre_cure", "name"), PATTERNS)
@pytest.mark.parametrize("repeats", [10, 16, 22])
def test_no_catastrophic_backtracking(pattern, _pre_cure, name, repeats):
    """TIMING: the CodeQL witness shape stays cheap, measured.

    `a-0-0-0...!` is exactly what the alert annotation described: an accepted
    prefix, a long run of characters belonging to both classes, and a final
    character that cannot match — forcing every partition of the run to be tried
    before failure can be reported.

    22 repeats costs ~1.0s on the vulnerable pattern and ~0s on the cured one, so
    a 0.3s budget separates them by a wide margin while staying far too short to
    flake on a loaded runner. Larger inputs are deliberately NOT used: they would
    hang rather than fail.
    """
    subject = "a" + "-0" * repeats + "!"
    start = time.perf_counter()
    assert pattern.match(subject) is None
    elapsed = time.perf_counter() - start
    assert elapsed < 0.3, (
        f"{name} took {elapsed:.3f}s on a {len(subject)}-character non-match "
        f"({repeats} repeats) — the exponential-backtracking signature CodeQL "
        f"py/redos flags, not a slow machine. Check whether a separator class "
        f"again overlaps its body class."
    )


# NOTE — there is deliberately NO test here that feeds a very long adversarial
# string (e.g. 800 characters). It would pass on the cured patterns in
# microseconds and is tempting to add as a flourish, but on a REINTRODUCED
# vulnerable pattern it does not fail: it diverges. Measured while writing this
# file, such a test ran past 600s twice and had to be killed, leaving a mutated
# source tree behind both times. A guard whose failure mode is "hang the runner"
# is worse than no guard, because CI reports a timeout instead of a red
# assertion and the cause is not named anywhere. The 22-repeat case above
# separates cured (~0s) from vulnerable (~1.0s) by a factor of thousands, which
# is all the signal needed; linearity at length 800 is recorded in the PR body,
# where a number cannot hang anything.

@pytest.mark.parametrize(("pattern", "pre_cure", "name"), PATTERNS)
@pytest.mark.parametrize(("alphabet", "max_len"), [(ALPHABET, 6), (WIDE_ALPHABET, 5)])
def test_cure_accepts_exactly_the_same_language(pattern, pre_cure, name, alphabet, max_len):
    """LANGUAGE: the cure is a rewrite, not a restriction.

    Exhaustive over the alphabet. If the cured pattern rejected even one string
    the original accepted, the canonical grammar would have silently narrowed and
    records that used to validate would start failing — a worse outcome than the
    ReDoS for anything already in flight.
    """
    reference = re.compile(pre_cure)
    divergent = [
        s
        for s in _all_strings(alphabet, max_len)
        if bool(reference.match(s)) != bool(pattern.match(s))
    ]
    assert not divergent, (
        f"{name} changed the accepted language for {len(divergent)} string(s); "
        f"first few: {divergent[:8]!r}"
    )
