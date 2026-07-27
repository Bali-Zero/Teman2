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

import os
import pathlib
import re
import subprocess
import sys
import tempfile

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
# BEHAVIOURAL: run the hook's real backend-suite region and READ WHAT IT PRINTS.
#
# WHY THIS SECTION EXISTS AND WHY IT COMES FIRST IN IMPORTANCE (round 2 of the
# adversarial review, 2026-07-27 — BLOCK, reproduced by hand before acting on
# it). Everything above and below judges the hook's SOURCE TEXT. Two one-line
# mutations reintroduce the original bug and keep all of it green:
#
#   1. append after the final `fi`:
#          echo "✅ All pre-push checks" "passed!"
#      Two arguments; `echo` joins them with a space and prints the identical
#      sentence. No contiguous literal exists in the source, so a substring
#      search finds nothing. 11/11 green, bug back.
#
#   2. inside the "no local PostgreSQL" skip branch:
#          export BACKEND_SUITE_RAN=1
#      The suite never runs; the verdict reads 1 and prints the pass. The
#      position/count regex below only recognised a BARE assignment, so
#      `export` (or `readonly`, or `eval`) slips past. 11/11 green, bug back.
#
# The defect is one defect, and it is the one this whole PR is about, turned on
# its author: a guard that matches the FORM instead of the ENTITY
# (cicatrix-superscar.md #3). The entity here is "what does a user SEE when the
# suite did not run", and the only way to assert on that is to run the thing.
#
# So: extract the hook's backend-suite region — from `if [ "$PREPUSH_RUN_BACKEND"
# = "1" ]; then` to end of file, which is self-contained (it defines its own
# PG_BIN/PG_ISREADY/PRE_PUSH_DB and reads only PREPUSH_RUN_BACKEND from above) —
# and execute it under a real `sh -e`, the same shell husky uses, with
# `pg_isready` stubbed to fail so the no-PG skip fires deterministically on any
# machine, CI included. Then assert on STDOUT.
#
# Both mutations die against this: (1) lands inside the extracted region and its
# rendered output contains the pass sentence; (2) is executed, so the verdict
# actually prints the pass. Neither can hide in a string literal.
# --------------------------------------------------------------------------

_REGION_ANCHOR = 'if [ "$PREPUSH_RUN_BACKEND" = "1" ]; then'


def _backend_region() -> str:
    """The hook from the backend-suite gate to EOF, verbatim."""
    text = _hook_text()
    hits = [i for i in range(len(text)) if text.startswith(_REGION_ANCHOR, i)]
    assert len(hits) == 1, (
        f"expected exactly one {_REGION_ANCHOR!r} in the hook, found {len(hits)} — "
        "re-anchor this harness rather than letting it execute the wrong region."
    )
    return text[hits[0]:]


def _run_region(run_backend: str, pg_ready: bool = False) -> str:
    """Execute the real region under `sh -e` and return everything it printed.

    `pg_ready=False` stubs pg_isready to exit 1, which is the "no local
    PostgreSQL" gate — the cheapest skip branch to reach, and the one that
    touches no database at all. Nothing below it runs, so this never creates,
    clones or drops anything.
    """
    with tempfile.TemporaryDirectory() as td:
        stub_dir = pathlib.Path(td) / "bin"
        stub_dir.mkdir()
        for name in ("pg_isready", "psql"):
            stub = stub_dir / name
            stub.write_text("#!/bin/sh\nexit %d\n" % (0 if pg_ready else 1))
            stub.chmod(0o755)
        script = f'PREPUSH_RUN_BACKEND="{run_backend}"\n' + _backend_region()
        env = dict(os.environ, PATH=f"{stub_dir}:{os.environ.get('PATH', '')}")
        proc = subprocess.run(
            ["sh", "-e", "-c", script],
            capture_output=True, text=True, env=env, cwd=str(REPO_ROOT), timeout=120,
        )
        return proc.stdout + proc.stderr


def test_behaviour_required_but_skipped_never_prints_a_pass() -> None:
    """THE test. The hook decided the suite was required, the environment
    skipped it, and what the user sees must not be a pass."""
    out = _run_region("1")
    assert UNVERIFIED_MARKER in out, (
        f"the hook did not warn that nothing was verified. It printed:\n{out}"
    )
    assert PASS_MARKER not in out, (
        "the hook printed a PASS while the backend suite never ran — this is the "
        f"original bug. Output:\n{out}"
    )


def test_behaviour_the_skip_reason_reaches_the_user() -> None:
    """A warning that cannot say why is a warning people learn to ignore."""
    out = _run_region("1")
    assert "reason not recorded" not in out, f"skip reason was lost:\n{out}"
    assert "no local PostgreSQL" in out, (
        f"the specific cause did not reach the verdict. Output:\n{out}"
    )


def test_behaviour_path_aware_skip_still_prints_a_pass() -> None:
    """INNOCENCE, behavioural: a diff that needed no backend suite is green, and
    stays green. Crying wolf on every docs push trains people past the warning."""
    out = _run_region("0")
    assert PASS_MARKER in out, f"a legitimate green stopped being green:\n{out}"
    assert UNVERIFIED_MARKER not in out, f"false alarm on a docs-only push:\n{out}"


def test_behaviour_survives_a_split_string_echo() -> None:
    """Pin the exact bypass that motivated this section, so nobody re-derives a
    source-grep as 'equivalent'. The mutation is applied to a COPY: this proves
    the harness reads rendered output, not source characters."""
    injected = '\necho "✅ All pre-push checks" "passed!"\n'
    # The point of the mutation: the SENTENCE it prints exists nowhere in the
    # characters that produce it. (The region legitimately contains the marker in
    # its own else branch, so the claim is about the injected fragment alone.)
    assert PASS_MARKER not in injected, "mutation must be invisible to a substring search"
    mutated = _backend_region() + injected
    with tempfile.TemporaryDirectory() as td:
        stub_dir = pathlib.Path(td) / "bin"
        stub_dir.mkdir()
        for name in ("pg_isready", "psql"):
            (stub_dir / name).write_text("#!/bin/sh\nexit 1\n")
            (stub_dir / name).chmod(0o755)
        env = dict(os.environ, PATH=f"{stub_dir}:{os.environ.get('PATH', '')}")
        proc = subprocess.run(
            ["sh", "-e", "-c", 'PREPUSH_RUN_BACKEND="1"\n' + mutated],
            capture_output=True, text=True, env=env, cwd=str(REPO_ROOT), timeout=120,
        )
    assert PASS_MARKER in proc.stdout + proc.stderr, (
        "the harness failed to SEE a split-string pass — it is reading source, not "
        "output, and the bypass this section exists to kill is back."
    )


# --------------------------------------------------------------------------
# STRUCTURE: kept as a second line of defence. These are now redundant with the
# behavioural tests for the two known bypasses, and deliberately so — they fail
# FASTER and name the offending line, which the output-based tests cannot.
# --------------------------------------------------------------------------


def test_no_unconditional_pass_after_the_verdict() -> None:
    """An `echo 'All pre-push checks passed'` added AFTER the block would make
    every unverified push look green again — the original bug, restored.

    Source-level only: a split-string echo defeats this, which is exactly why
    test_behaviour_required_but_skipped_never_prints_a_pass exists above.
    """
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

    The pattern deliberately accepts every way shell can bind that name —
    bare, `export`, `readonly`, `declare`, `local`, `eval` — because the round-2
    bypass was `export BACKEND_SUITE_RAN=1` in a skip branch, invisible to a
    pattern that only knew the bare form. Matching the ENTITY (this variable
    acquires a truthy value here) rather than the FORM (this exact syntax).

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
    assign = re.compile(
        r'^\s*(?:export\s+|readonly\s+|declare\s+(?:-\w+\s+)*|local\s+|eval\s+)*'
        r'BACKEND_SUITE_RAN=(?:1|"1"|\'1\')\s*$',
        re.MULTILINE,
    )
    assert assign.search(m.group("body")), (
        "BACKEND_SUITE_RAN is not set inside the `TEST_RC -eq 0` branch — the "
        "only place that earned a pass."
    )
    found = assign.findall(text)
    assert len(found) == 1, (
        f"BACKEND_SUITE_RAN is bound to 1 in {len(found)} places; exactly one is "
        "allowed. A second binding — in any form, including `export` — is a way "
        "for a push to claim a verdict it did not earn."
    )


def test_the_failure_hint_does_not_send_anyone_at_the_shared_dev_db() -> None:
    """SCAR PIN, round 2. The hook exports three env vars at the isolated clone,
    but the reproduce command it PRINTS on failure omitted INTAKE_TEST_DSN. Those
    vars are command-scoped — nothing survives into the copier's shell — so the
    printed line sent whoever followed it straight onto the
    `postgresql://localhost:5432/nuzantara_dev` default, writing to the shared
    dev DB while debugging. The defect this diff cures, reintroduced in its own
    help text."""
    text = _hook_text()
    m = re.search(r'Reproduce \(against the persistent base db.*?pytest backend/tests/',
                  text, re.DOTALL)
    assert m, "reproduce hint not found — re-anchor this test"
    # Comment lines are stripped before judging: the block's own explanation
    # NAMES nuzantara_dev while saying never to send anyone there, and asserting
    # over raw text would fail on the warning instead of on the defect. Judging
    # the executable lines is the same correction this file already applies in
    # _hook_code() — and I made the mistake again here, in the very test written
    # to pin a round-2 finding.
    hint = "\n".join(l for l in m.group(0).splitlines() if not l.lstrip().startswith("#"))
    assert "INTAKE_TEST_DSN=" in hint, (
        "the printed reproduce command omits INTAKE_TEST_DSN, so copying it runs "
        f"the intake tests against the shared dev DB. Hint:\n{hint}"
    )
    assert "nuzantara_dev" not in hint, (
        f"the reproduce command names the shared dev database:\n{hint}"
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
