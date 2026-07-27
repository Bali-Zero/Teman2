#!/usr/bin/env python3
"""Guilt + innocence for the `.husky/pre-push` final-verdict branch.

WHY (measured live on Mini, 2026-07-27 — cicatrix-superscar.md family #2,
"esiste ≠ armato"): the path-aware gate can decide the backend suite is
REQUIRED, four environment gates can then skip it entirely (no local PG /
unprovisioned test DB / no venv / DB clone failed), and before this fix all
four fell through to the same closing line:

    🧭 6/6 changed file(s) are NOT on the innocent allowlist — running FULL suite
    🐍 Running Python tests...
    ⏭️  SKIP Python tests — local PG up but 'nuzantara_test' not provisioned
    ✅ All pre-push checks passed!

Mini's local PG had no `test` role at all, so EVERY push ever made from that
machine met a gate that ran zero tests and announced a pass. The skip is
legitimate (a machine without a test DB must still be able to push); the CLAIM
was not.

WHAT THIS FILE LEARNED FROM ITS OWN REVIEW: the first draft extracted only the
`if` PREDICATE and then evaluated its OWN `echo UNVERIFIED/PASSED` branches. It
would have passed with the hook's two messages swapped, or with an
unconditional "All pre-push checks passed" added after the block — i.e. it
tested a truth table, not a verdict. It now asserts the REAL branch bodies, and
the structural checks below accept legitimate refactors (quoted assignment,
printf instead of echo) instead of pinning today's exact characters.

Run:  python3 scripts/tests/test_prepush_honest_verdict.py
      pytest scripts/tests/test_prepush_honest_verdict.py -q
Wired into CI by .github/workflows/prepush-guards.yml.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
HOOK_FILE = REPO_ROOT / ".husky" / "pre-push"

UNVERIFIED_MARKER = "PUSH NOT VERIFIED LOCALLY"
PASS_MARKER = "All pre-push checks passed"


def _hook_text() -> str:
    return HOOK_FILE.read_text(encoding="utf-8")


def _hook_code() -> str:
    """The hook with comment-only lines removed.

    Needed because this file's own first run failed on the hook's EXPLANATORY
    COMMENTS: the comment block quotes Mini's log verbatim (which contains "All
    pre-push checks passed") and names `nuzantara_dev` while explaining why it
    must never be connected to. Asserting over raw text judged the FORM (a
    string appears) instead of the ENTITY (the hook does the thing) — the same
    error family (#3) these assertions exist to catch. Comments are evidence;
    only executable lines are behaviour.
    """
    return "\n".join(
        l for l in _hook_text().splitlines() if not l.lstrip().startswith("#")
    )


# --------------------------------------------------------------------------
# The real block, split into its two real branches.
# --------------------------------------------------------------------------


def _verdict_block() -> tuple[str, str, str]:
    """(predicate, then-branch body, else-branch body) from the actual hook."""
    m = re.search(
        r"^if (?P<cond>\[ \"\$PREPUSH_RUN_BACKEND\" = \"1\" \] && \[ \"\$\{BACKEND_SUITE_RAN:-0\}\" != \"1\" \]); then\n"
        r"(?P<then>.*?)\nelse\n(?P<els>.*?)\nfi\b",
        _hook_text(),
        re.MULTILINE | re.DOTALL,
    )
    assert m, (
        f"final-verdict if/else not found in {HOOK_FILE}. It must stay a single "
        "`if <cond>; then ... else ... fi` so this test can read the REAL branches."
    )
    return m.group("cond"), m.group("then"), m.group("els")


def _evaluate(run_backend: str, suite_ran: str | None) -> str:
    """Run the REAL predicate under a real `sh -e`, exactly as the hook does.

    `suite_ran=None` models the variable being UNSET — the path-aware-skip path
    never enters the block that initialises it.
    """
    cond, _, _ = _verdict_block()
    assign = "" if suite_ran is None else f'BACKEND_SUITE_RAN="{suite_ran}"\n'
    script = (
        "set -e\n"
        f'PREPUSH_RUN_BACKEND="{run_backend}"\n'
        f"{assign}"
        f"if {cond}; then echo TOOK_THEN; else echo TOOK_ELSE; fi\n"
    )
    r = subprocess.run(["sh", "-c", script], capture_output=True, text=True)
    assert r.returncode == 0, f"predicate aborted the shell: {r.stderr!r}"
    return r.stdout.strip()


def _verdict(run_backend: str, suite_ran: str | None) -> str:
    """Which REAL message this state produces: 'UNVERIFIED' or 'PASS'."""
    _, then_body, else_body = _verdict_block()
    body = then_body if _evaluate(run_backend, suite_ran) == "TOOK_THEN" else else_body
    has_unverified = UNVERIFIED_MARKER in body
    has_pass = PASS_MARKER in body
    assert has_unverified != has_pass, (
        f"a verdict branch must say exactly one of the two things; got "
        f"unverified={has_unverified} pass={has_pass} in:\n{body}"
    )
    return "UNVERIFIED" if has_unverified else "PASS"


# --------------------------------------------------------------------------
# GUILT: the exact Mini shape must not produce a passing message.
# --------------------------------------------------------------------------


def test_required_but_never_ran_says_unverified() -> None:
    assert _verdict("1", "0") == "UNVERIFIED"


def test_required_but_variable_unset_says_unverified() -> None:
    """Fail-safe direction: a future skip path that forgets the bookkeeping
    entirely must still not claim a pass."""
    assert _verdict("1", None) == "UNVERIFIED"


def test_branches_are_not_swapped() -> None:
    """Kills the mutation the first draft of this file could not see."""
    _, then_body, else_body = _verdict_block()
    assert UNVERIFIED_MARKER in then_body and PASS_MARKER not in then_body
    assert PASS_MARKER in else_body and UNVERIFIED_MARKER not in else_body


# --------------------------------------------------------------------------
# INNOCENCE: the two legitimate greens stay green.
# --------------------------------------------------------------------------


def test_suite_actually_passed_says_pass() -> None:
    assert _verdict("1", "1") == "PASS"


def test_path_aware_skip_says_pass() -> None:
    """A diff with no backend-relevant paths never needed the suite. Reporting
    it unverified would cry wolf on every docs/frontend push and train people
    to ignore the warning."""
    assert _verdict("0", None) == "PASS"


# --------------------------------------------------------------------------
# STRUCTURE: written to survive legitimate refactors, and to check POSITION
# rather than mere count.
# --------------------------------------------------------------------------


def test_no_unconditional_pass_after_the_verdict() -> None:
    """An `echo 'All pre-push checks passed'` added AFTER the block would make
    every unverified push look green again — the original bug, restored."""
    text = _hook_text()
    _, _, else_body = _verdict_block()
    tail = text[text.rindex(else_body) + len(else_body):]
    assert PASS_MARKER not in tail, (
        f"{PASS_MARKER!r} appears after the verdict block — it must only ever be "
        f"reachable through the else branch. Trailing text:\n{tail}"
    )


def test_the_pass_claim_exists_only_inside_the_verdict_block() -> None:
    _, _, else_body = _verdict_block()
    assert _hook_code().count(PASS_MARKER) == else_body.count(PASS_MARKER) == 1


def test_suite_ran_is_set_only_where_pytest_succeeded() -> None:
    """POSITION, not count. Counting one assignment does not prove it sits in
    the success branch — it could be moved into a skip path and still count 1.

    Note on the name: BACKEND_SUITE_RAN means "the suite completed and passed",
    not "execution began" — a suite that starts and fails exits 1 before the
    verdict, so the distinction never reaches a message today.
    """
    text = _hook_text()
    m = re.search(
        r'if \[ "\$TEST_RC" -eq 0 \]; then\n(?P<body>.*?)\n\s*elif ',
        text,
        re.DOTALL,
    )
    assert m, "pytest-success branch not found — re-anchor this test"
    assign = re.compile(r'^\s*BACKEND_SUITE_RAN=(?:1|"1"|\'1\')\s*$', re.MULTILINE)
    assert assign.search(m.group("body")), (
        "BACKEND_SUITE_RAN is not set inside the `TEST_RC -eq 0` branch — the "
        "only place that earned a pass."
    )
    assert len(assign.findall(text)) == 1, (
        "BACKEND_SUITE_RAN=1 must appear exactly once; a second assignment is a "
        "way for a push to claim a verdict it did not earn."
    )


def test_every_suite_skip_branch_records_a_reason() -> None:
    """Accepts echo or printf, and any helper that assigns the reason — what
    matters is that each skip leaves one, so the verdict can name the cause
    instead of saying 'reason not recorded'."""
    text = _hook_text()
    skips = len(re.findall(r'(?:echo|printf)\s+"⏭️\s+SKIP Python tests', text))
    reasons = len(re.findall(r"^\s*BACKEND_SUITE_SKIP_REASON=", text, re.MULTILINE))
    assert skips > 0, "no 'SKIP Python tests' branches found — re-anchor this test"
    assert reasons == skips + 1, (
        f"{skips} skip branches but {reasons} BACKEND_SUITE_SKIP_REASON "
        "assignments (expected skips + 1 initialiser)."
    )


def test_signal_death_cannot_reach_a_pass() -> None:
    """A SIGTERM'd suite (TEST_RC >= 128 — the contention failure this fleet
    hits) must exit before the verdict, never fall through to it."""
    m = re.search(
        r"TERMINATED by signal \$TEST_SIGNAL.*?\n(.*?)\n\s*else", _hook_text(), re.DOTALL
    )
    assert m, "signal-classification branch not found — re-anchor this test"
    assert "exit 1" in m.group(1)


def test_intake_dsn_is_isolated_to_the_per_push_clone() -> None:
    """SCAR PIN (2026-07-27). test_intake_writer.py defaults INTAKE_TEST_DSN to
    the machine's SHARED nuzantara_dev (12,408 client rows on Pro): a default
    that fails OPEN onto real data instead of skipping. CI has exported the
    disposable DB since the var existed; this hook must too, or the local suite
    both writes to that DB and goes red on writes it did not cause."""
    text = _hook_text()
    assert re.search(r'INTAKE_TEST_DSN="postgresql://[^"]*\$CLONE_DB"', text), (
        "the hook must export INTAKE_TEST_DSN pointing at the per-push clone "
        "($CLONE_DB), mirroring .github/workflows/tests.yml"
    )
    assert "nuzantara_dev" not in _hook_code(), (
        "no EXECUTABLE line may name the shared dev DB (the comment that explains "
        "why is not only allowed, it is the evidence)"
    )


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {name}: {exc}")
    sys.exit(1 if failures else 0)
