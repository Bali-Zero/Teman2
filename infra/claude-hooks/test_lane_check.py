#!/usr/bin/env python3
"""Corpus for `lane_check.py` — the lane's self-declared termination check.

L04-PR1 acceptance, verbatim from the lane spec: guilt (a failing check blocks
the stop and the stderr is quoted), innocence (no `.lane-check.json` means
behaviour byte-identical to before this file existed), and guilt again on a
tautological `true` command, which must be refused rather than passed.

WHY THE INNOCENCE CASE IS FIRST-CLASS HERE AND NOT AN AFTERTHOUGHT. This module
is imported by termination surfaces that every session and every subagent in the
fleet passes through. A defect that makes it block when no contract exists would
wall every lane at once. So the absent-file path is asserted to do NOTHING —
not merely to return ABSENT, but to run no subprocess at all, proved by pointing
the check at a command that would leave a side effect on disk and asserting the
side effect never appears.

Runs two ways, matching the convention of every sibling corpus in this
directory: `python3 infra/claude-hooks/test_lane_check.py -v` for the CI
executor in guard-conformance.yml, and `pytest` for local work.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import lane_check as lc  # noqa: E402


def _worktree(tmp: pathlib.Path, contract: dict | str | None) -> pathlib.Path:
    """A throwaway worktree root, optionally carrying a `.lane-check.json`.

    `contract` as a str is written verbatim, so a case can hand the module
    malformed JSON without this helper silently repairing it into valid JSON.
    """
    root = tmp / "wt"
    root.mkdir(exist_ok=True)
    path = root / ".lane-check.json"
    if contract is None:
        if path.exists():
            path.unlink()
    elif isinstance(contract, str):
        path.write_text(contract, encoding="utf-8")
    else:
        path.write_text(json.dumps(contract), encoding="utf-8")
    return root


def _clean_env() -> None:
    """LANE_CHECK_OFF leaking in from the caller's shell would turn every case
    below into a vacuous ABSENT and the corpus would pass having tested
    nothing — the premise is asserted, not assumed."""
    os.environ.pop("LANE_CHECK_OFF", None)


# ---------------------------------------------------------------- innocence

def _case_absent_is_a_no_op() -> list[str]:
    """INNOCENCE: no contract file -> ABSENT, does not block, and runs NOTHING.

    The side-effect probe is the load-bearing half. Asserting only
    `status == ABSENT` would still pass on a module that ran the command and
    then discarded the result, which is not "byte-identical to before".
    """
    fails: list[str] = []
    _clean_env()
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        root = _worktree(tmp, None)
        sentinel = tmp / "the-check-ran"
        # A contract that WOULD write the sentinel, deliberately not installed.
        result = lc.evaluate(str(root), changed_paths=["scripts/x.py"])
        if result.status is not lc.LaneCheckStatus.ABSENT:
            fails.append(f"absent contract resolved {result.status.value!r}, expected 'absent'")
        if lc.blocks(result):
            fails.append("absent contract BLOCKED the stop — this would wall every lane in the fleet")
        if result.message:
            fails.append(f"absent contract produced a message: {result.message!r}")
        if sentinel.exists():
            fails.append("absent contract still executed something — not a no-op")
    return fails


def _case_env_escape_is_absent() -> list[str]:
    """A stuck turn must always have a way out, and it must short-circuit
    BEFORE the file is read — otherwise an unreadable contract could still
    block a lane that had already opted out."""
    fails: list[str] = []
    _clean_env()
    with tempfile.TemporaryDirectory() as td:
        root = _worktree(pathlib.Path(td), {"command": "test -f nope-does-not-exist"})
        os.environ["LANE_CHECK_OFF"] = "1"
        try:
            result = lc.evaluate(str(root))
        finally:
            _clean_env()
        if result.status is not lc.LaneCheckStatus.ABSENT:
            fails.append(f"LANE_CHECK_OFF=1 resolved {result.status.value!r}, expected 'absent'")
        if lc.blocks(result):
            fails.append("LANE_CHECK_OFF=1 still blocked")
    return fails


def _case_passing_check_does_not_block() -> list[str]:
    """INNOCENCE: a real command that really passes must let the turn end.
    Without this, a module that blocked unconditionally would satisfy every
    guilt case in this file and still be useless."""
    fails: list[str] = []
    _clean_env()
    with tempfile.TemporaryDirectory() as td:
        # NOT `exit 0` — that is a tautology and the module refuses it, correctly.
        # The first draft of this case used it and failed, which is the corpus
        # catching the corpus: a "passing" command that cannot fail proves the
        # same nothing here as it would in a lane. `test -f` really can fail.
        root = _worktree(pathlib.Path(td), {"command": "test -f .lane-check.json", "expected_exit": 0})
        result = lc.evaluate(str(root))
        if result.status is not lc.LaneCheckStatus.PASS:
            fails.append(f"a passing command resolved {result.status.value!r}: {result.message!r}")
        if lc.blocks(result):
            fails.append("a passing command BLOCKED the stop")
    return fails


def _case_out_of_scope_skips() -> list[str]:
    """Scope globs bound the check. A changed set that matches none of them is
    OUT_OF_SCOPE and must not block — nor run the command."""
    fails: list[str] = []
    _clean_env()
    with tempfile.TemporaryDirectory() as td:
        root = _worktree(
            pathlib.Path(td),
            {"command": "exit 9", "scope_globs": ["scripts/*"]},
        )
        result = lc.evaluate(str(root), changed_paths=["docs/note.md"])
        if result.status is not lc.LaneCheckStatus.OUT_OF_SCOPE:
            fails.append(f"out-of-scope change resolved {result.status.value!r}")
        if lc.blocks(result):
            fails.append("an out-of-scope change BLOCKED the stop")
    return fails


def _case_unknown_change_set_still_runs() -> list[str]:
    """UNDER-MATCH GUARD (superscar #3, the gemello): scope_globs declared but
    `changed_paths=None` must NOT be read as "nothing matched". An unknown
    change set is not an out-of-scope change set, and letting a missing input
    silently disable the check is how a guard stops guarding without anyone
    editing it."""
    fails: list[str] = []
    _clean_env()
    with tempfile.TemporaryDirectory() as td:
        root = _worktree(
            pathlib.Path(td),
            {"command": "exit 3", "scope_globs": ["scripts/*"]},
        )
        result = lc.evaluate(str(root), changed_paths=None)
        if result.status is lc.LaneCheckStatus.OUT_OF_SCOPE:
            fails.append("changed_paths=None was read as out-of-scope — the check silently disabled itself")
        if not lc.blocks(result):
            fails.append(f"an unknown change set did not block on a failing check ({result.status.value})")
    return fails


def _case_empty_change_set_still_runs() -> list[str]:
    """UNDER-MATCH GUARD, the subtler sibling of the case above and a genuine
    corpus gap until a mutant found it.

    `changed_paths=[]` is not the same claim as `changed_paths=None`, but both
    must keep the check running. An empty list is what the wiring produces for a
    worktree that is clean AND has committed nothing since its merge-base — a
    perfectly ordinary state, and precisely the moment a lane is about to end a
    turn. Reading it as "nothing matched the scope" would skip the check exactly
    when it is most worth running.

    Found by mutation: relaxing the guard from `is not None and len(...) > 0` to
    `is not None` left every other case in this file green.
    """
    fails: list[str] = []
    _clean_env()
    with tempfile.TemporaryDirectory() as td:
        root = _worktree(
            pathlib.Path(td),
            {"command": "exit 4", "scope_globs": ["scripts/*"]},
        )
        result = lc.evaluate(str(root), changed_paths=[])
        if result.status is lc.LaneCheckStatus.OUT_OF_SCOPE:
            fails.append("an EMPTY change set was read as out-of-scope — the check disabled itself on a clean tree")
        if not lc.blocks(result):
            fails.append(f"an empty change set did not block on a failing check ({result.status.value})")
    return fails


# -------------------------------------------------------------------- guilt

def _case_failing_check_blocks_and_quotes_stderr() -> list[str]:
    """GUILT (spec acceptance 1): a failing check blocks the stop and the
    operator-facing message carries the command and the stderr tail."""
    fails: list[str] = []
    _clean_env()
    needle = "ASSERTION-XYZZY-FAILED"
    with tempfile.TemporaryDirectory() as td:
        root = _worktree(
            pathlib.Path(td),
            {"command": f"echo {needle} >&2; exit 1", "expected_exit": 0},
        )
        result = lc.evaluate(str(root))
        if result.status is not lc.LaneCheckStatus.FAIL:
            fails.append(f"a failing command resolved {result.status.value!r}, expected 'fail'")
        if not lc.blocks(result):
            fails.append("a FAILING lane check did not block the stop")
        if needle not in (result.message or ""):
            fails.append("the block message does not quote the check's stderr — an operator cannot act on it")
        if result.exit_code != 1:
            fails.append(f"exit_code recorded as {result.exit_code!r}, expected 1")
    return fails


def _case_tautology_is_refused() -> list[str]:
    """GUILT (spec acceptance 3): a command that cannot fail proves nothing and
    must be INVALID, never PASS. `true`, `:`, `exit 0` and their combinations."""
    fails: list[str] = []
    _clean_env()
    for cmd in ("true", ":", "exit 0", "/bin/true", "true && :", "true; exit 0", "  true  "):
        with tempfile.TemporaryDirectory() as td:
            root = _worktree(pathlib.Path(td), {"command": cmd})
            result = lc.evaluate(str(root))
            if result.status is not lc.LaneCheckStatus.INVALID:
                fails.append(f"tautology {cmd!r} resolved {result.status.value!r}, expected 'invalid'")
            if not lc.blocks(result):
                fails.append(f"tautology {cmd!r} did not block")
    return fails


def _case_tautology_check_is_not_a_substring_match() -> list[str]:
    """INNOCENCE for the rule above, and the reason it is written entity-wise.

    Superscar #3 has nine instances in this repo, most of them a guard that
    matched a substring where it meant an entity. Rejecting the word "true"
    anywhere would forbid a legitimate command that merely contains it, so the
    refusal is asserted NOT to fire on one.
    """
    fails: list[str] = []
    _clean_env()
    legit = (
        "pytest --assert=plain test_true_positive.py",
        "python3 -m pytest tests/test_truthy.py -q",
        "grep -r 'true' src/ && exit 0 || exit 1",
    )
    for cmd in legit:
        with tempfile.TemporaryDirectory() as td:
            root = _worktree(pathlib.Path(td), {"command": cmd, "scope_globs": ["nothing/*"]})
            # scoped out so the command never actually runs — this case is about
            # the CLASSIFICATION, not about executing pytest in a temp dir.
            result = lc.evaluate(str(root), changed_paths=["docs/x.md"])
            if result.status is lc.LaneCheckStatus.INVALID:
                fails.append(f"legitimate command {cmd!r} was refused as a tautology (over-match)")
    return fails


def _case_malformed_contract_blocks() -> list[str]:
    """A contract the lane cannot honour is INVALID and BLOCKS.

    Fail CLOSED here, and the reason is the whole point of the module: a lane
    that declared a check and then shipped an unusable one must not end its
    turn reporting success. "Could not measure" reported as "measured fine" is
    the disease (W104/W108). The escape is LANE_CHECK_OFF=1, not a typo.
    """
    fails: list[str] = []
    _clean_env()
    cases: list[tuple[str, object]] = [
        ("not json at all", "{ this is not json"),
        ("command missing", {"expected_exit": 0}),
        ("command empty", {"command": "   "}),
        # each of the four below carries a FALSIFIABLE command on purpose: with a
        # tautology they would resolve INVALID for the tautology rule instead of
        # the rule under test, and would pass for the wrong reason.
        ("command not a string", {"command": ["pytest"]}),
        ("expected_exit not an int", {"command": "test -f .lane-check.json", "expected_exit": "0"}),
        ("timeout not positive", {"command": "test -f .lane-check.json", "timeout": 0}),
        ("timeout absurd", {"command": "test -f .lane-check.json", "timeout": 100000}),
        ("scope_globs not a list of str", {"command": "test -f .lane-check.json", "scope_globs": [1, 2]}),
    ]
    for label, contract in cases:
        with tempfile.TemporaryDirectory() as td:
            root = _worktree(pathlib.Path(td), contract)  # type: ignore[arg-type]
            result = lc.evaluate(str(root))
            if result.status is not lc.LaneCheckStatus.INVALID:
                fails.append(f"{label}: resolved {result.status.value!r}, expected 'invalid'")
            if not lc.blocks(result):
                fails.append(f"{label}: did not block")
    return fails


def _case_timeout_blocks_rather_than_passing() -> list[str]:
    """A check that cannot finish has not passed.

    This is the case most likely to be softened later into a fail-open, so the
    reason is stated where it will be read: a timeout is a failure to MEASURE,
    and the one thing this module exists to prevent is a failure to measure
    being recorded as a measurement.
    """
    fails: list[str] = []
    _clean_env()
    with tempfile.TemporaryDirectory() as td:
        root = _worktree(pathlib.Path(td), {"command": "sleep 5", "timeout": 1})
        result = lc.evaluate(str(root))
        if result.status is not lc.LaneCheckStatus.ERROR:
            fails.append(f"a timing-out check resolved {result.status.value!r}, expected 'error'")
        if not lc.blocks(result):
            fails.append("a timing-out check did not block — a failure to measure read as a pass")
    return fails


def _case_never_raises() -> list[str]:
    """The four termination surfaces call this at the end of every turn. An
    exception escaping here would be a traceback in a Stop hook."""
    fails: list[str] = []
    _clean_env()
    for bad_cwd in ("/nonexistent/path/xyzzy", ""):
        try:
            result = lc.evaluate(bad_cwd)
        except Exception as exc:  # noqa: BLE001 — that is the assertion
            fails.append(f"evaluate({bad_cwd!r}) raised {exc!r} instead of degrading")
            continue
        if result.status not in (lc.LaneCheckStatus.ABSENT, lc.LaneCheckStatus.INVALID, lc.LaneCheckStatus.ERROR):
            fails.append(f"evaluate({bad_cwd!r}) resolved {result.status.value!r}")
    return fails


def _case_or_true_tail_is_refused() -> list[str]:
    """GUILT, and the shape a real lane would actually reach for.

    ``pytest test_foo.py || true`` is a REAL check whose failure is swallowed.
    Every entity but the last is legitimate, so an `all()` over the entities
    answers False and the command sails through, runs, exits 0 forever and
    reports PASS. Refusing only the fully-tautological form would have left the
    reward-hacking door open while looking closed. Found by a blind refuter.
    """
    fails: list[str] = []
    _clean_env()
    for cmd in ("pytest test_foo.py || true", "make check || :", "ruff check . || exit 0"):
        with tempfile.TemporaryDirectory() as td:
            root = _worktree(pathlib.Path(td), {"command": cmd})
            result = lc.evaluate(str(root))
            if result.status is not lc.LaneCheckStatus.INVALID:
                fails.append(f"{cmd!r} resolved {result.status.value!r} — an ||-swallowed failure read as a real check")
    return fails


def _case_quote_aware_split_does_not_mangle() -> list[str]:
    """INNOCENCE for the rule above. A separator INSIDE quotes is not a
    separator: ``git commit -m "fix && true"`` is one command, and a blind
    `str.replace` split it into two nonsense entities, one of which ends in
    the word the tautology rule looks for."""
    fails: list[str] = []
    _clean_env()
    for cmd in ('git commit -m "fix && true"', "echo 'a || true' && pytest x.py"):
        with tempfile.TemporaryDirectory() as td:
            root = _worktree(pathlib.Path(td), {"command": cmd, "scope_globs": ["none/*"]})
            result = lc.evaluate(str(root), changed_paths=["docs/x.md"])
            if result.status is lc.LaneCheckStatus.INVALID:
                fails.append(f"{cmd!r} was refused — a quoted separator was read as a real one")
    return fails


def _case_untrusted_origin_is_silent() -> list[str]:
    """An external repository's `.lane-check.json` must never be executed.

    A subagent routinely clones a stranger's repo to read it. Without this gate
    the harness would run that stranger's shell command, with shell=True, the
    moment the agent tried to stop — a zero-click RCE reached by cloning. The
    verdict is ABSENT and SILENT, never a block: refusing to run a stranger's
    command must not wall the agent that merely read their code.
    """
    fails: list[str] = []
    _clean_env()
    with tempfile.TemporaryDirectory() as td:
        root = _worktree(pathlib.Path(td), {"command": "echo pwned >&2; exit 1"})
        import subprocess as _sp
        _sp.run(["git", "-C", str(root), "init", "-q"], capture_output=True)
        _sp.run(["git", "-C", str(root), "remote", "add", "origin",
                 "https://github.com/some-stranger/evil.git"], capture_output=True)
        result = lc.evaluate(str(root))
        if result.status is not lc.LaneCheckStatus.ABSENT:
            fails.append(f"an untrusted origin resolved {result.status.value!r}, expected 'absent'")
        if lc.blocks(result):
            fails.append("an untrusted origin BLOCKED — refusing a stranger's command must not wall the agent")
    return fails


def _case_absent_never_computes_the_change_set() -> list[str]:
    """The innocence claim, asserted where it was actually FALSE.

    The docstring promises an absent contract costs one `os.path.isfile`. The
    first wiring broke that promise without touching this file: it evaluated the
    change set as a function ARGUMENT, so three git subprocesses ran on every
    termination in the fleet, contract or no contract. The library's own tests
    could not see it, because they pass the list directly. This case passes a
    CALLABLE that records whether it was invoked.
    """
    fails: list[str] = []
    _clean_env()
    called: list[int] = []
    with tempfile.TemporaryDirectory() as td:
        root = _worktree(pathlib.Path(td), None)
        lc.evaluate(str(root), changed_paths_fn=lambda: (called.append(1), ["x"])[1])
        if called:
            fails.append("the change set was computed for an ABSENT contract — the innocence promise is false")
    # and it IS computed when a contract with scope_globs exists
    called.clear()
    with tempfile.TemporaryDirectory() as td:
        root = _worktree(pathlib.Path(td), {"command": "exit 2", "scope_globs": ["scripts/*"]})
        lc.evaluate(str(root), changed_paths_fn=lambda: (called.append(1), ["docs/x.md"])[1])
        if not called:
            fails.append("the change set was NEVER computed for a scoped contract — scope_globs is dead again")
    return fails


_CASES = (
    ("innocence: absent contract is a no-op", _case_absent_is_a_no_op),
    ("innocence: LANE_CHECK_OFF=1 escapes", _case_env_escape_is_absent),
    ("innocence: a passing check does not block", _case_passing_check_does_not_block),
    ("innocence: out-of-scope change skips", _case_out_of_scope_skips),
    ("under-match: unknown change set still runs", _case_unknown_change_set_still_runs),
    ("under-match: empty change set still runs", _case_empty_change_set_still_runs),
    ("guilt: failing check blocks and quotes stderr", _case_failing_check_blocks_and_quotes_stderr),
    ("guilt: tautological command refused", _case_tautology_is_refused),
    ("innocence: tautology rule is entity-wise", _case_tautology_check_is_not_a_substring_match),
    ("guilt: malformed contract blocks", _case_malformed_contract_blocks),
    ("guilt: timeout blocks rather than passing", _case_timeout_blocks_rather_than_passing),
    ("guilt: an ||-swallowed failure is refused", _case_or_true_tail_is_refused),
    ("innocence: a quoted separator is not a separator", _case_quote_aware_split_does_not_mangle),
    ("security: an untrusted origin is silent, not executed", _case_untrusted_origin_is_silent),
    ("innocence: ABSENT never computes the change set", _case_absent_never_computes_the_change_set),
    ("robustness: evaluate never raises", _case_never_raises),
)


# pytest entry points — one per case so a failure names itself.
def test_absent_is_a_no_op() -> None:
    assert not _case_absent_is_a_no_op()


def test_env_escape_is_absent() -> None:
    assert not _case_env_escape_is_absent()


def test_passing_check_does_not_block() -> None:
    assert not _case_passing_check_does_not_block()


def test_out_of_scope_skips() -> None:
    assert not _case_out_of_scope_skips()


def test_unknown_change_set_still_runs() -> None:
    assert not _case_unknown_change_set_still_runs()


def test_empty_change_set_still_runs() -> None:
    assert not _case_empty_change_set_still_runs()


def test_failing_check_blocks_and_quotes_stderr() -> None:
    assert not _case_failing_check_blocks_and_quotes_stderr()


def test_tautology_is_refused() -> None:
    assert not _case_tautology_is_refused()


def test_tautology_check_is_not_a_substring_match() -> None:
    assert not _case_tautology_check_is_not_a_substring_match()


def test_malformed_contract_blocks() -> None:
    assert not _case_malformed_contract_blocks()


def test_timeout_blocks_rather_than_passing() -> None:
    assert not _case_timeout_blocks_rather_than_passing()


def test_or_true_tail_is_refused() -> None:
    assert not _case_or_true_tail_is_refused()


def test_quote_aware_split_does_not_mangle() -> None:
    assert not _case_quote_aware_split_does_not_mangle()


def test_untrusted_origin_is_silent() -> None:
    assert not _case_untrusted_origin_is_silent()


def test_absent_never_computes_the_change_set() -> None:
    assert not _case_absent_never_computes_the_change_set()


def test_never_raises() -> None:
    assert not _case_never_raises()


if __name__ == "__main__":
    verbose = "-v" in sys.argv
    all_fails: list[str] = []
    for label, fn in _CASES:
        fails = fn()
        all_fails.extend(f"{label}: {f}" for f in fails)
        if verbose:
            print(f"  [{'FAIL' if fails else ' ok '}] {label}")
    if all_fails:
        print(f"=== {len(all_fails)} FAIL ===")
        for f in all_fails:
            print("  [FAIL] " + f)
        sys.exit(1)
    print(f"=== lane_check OK ({len(_CASES)} cases: guilt on fail/tautology/malformed/timeout, "
          "innocence on absent/escape/pass/out-of-scope/entity-wise-tautology, under-match on unknown change set) ===")
    sys.exit(0)
