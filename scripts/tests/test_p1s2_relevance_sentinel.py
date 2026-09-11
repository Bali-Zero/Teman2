#!/usr/bin/env python3
"""The p1s2 relevance sentinel resolves the right diff base for each event
shape, and fails OPEN when it cannot measure.

WHY THIS FILE EXISTS
--------------------
`p1s2-mutation-incremental.yml` gates every expensive step in its job on
`steps.relevant.outputs.run == 'true'`. That single output decides whether the
canary self-test and the incremental mutation pass run at all, so a defect in
the sentinel is invisible in exactly the direction that matters: a sentinel
that wrongly answers `run=false` makes the whole gate skip and report success,
which is a green that cannot fail (superscar #2).

Until 2026-08-31 the step answered `run=true` for EVERY non-`pull_request`
event. That was correct while `push:` was the only other trigger — push is
paths-filtered at the trigger, so a push run that exists is one that needs the
work. It stopped being correct when `merge_group:` was added to make this job
safe to require: without a per-event base, every entry in the merge queue
would have run a full `pip install mutmut` plus a mutation pass, fleet-wide,
for every lane. The workflow header had named that trap and named its fix
(compute against `github.event.merge_group.base_sha`) months before either
happened.

WHAT IS TESTED, AND HOW
-----------------------
The step's `run:` body is read out of the workflow with PyYAML, the three
`${{ }}` expressions are substituted, and the result is EXECUTED by bash
against a synthetic git repository built per test. Nothing here re-implements
the sentinel or asserts on its source text: a test that matched the shell
source would pass on a body that cannot run, which is the shape it exists to
catch. The repository is synthetic rather than this checkout so the test does
not depend on this repo's history — a shallow clone or a rewritten base would
otherwise turn it red for a reason unrelated to the sentinel.

`scripts/tests/test_hermetic_census.py` pins the grep alternation EQUAL to the
workflow's `push: paths:` list. That pin is about the two lists agreeing; this
file is about the surrounding logic doing the right thing with them. Neither
subsumes the other.
"""

from __future__ import annotations

import os
import pathlib
import re
import subprocess
import tempfile

import pytest
import yaml

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "p1s2-mutation-incremental.yml"

#: One trust path, taken from the alternation the workflow actually carries.
_TRUST_PATH = "scripts/mutation_incremental.py"
#: A path deliberately NOT in the alternation.
_IRRELEVANT_PATH = "docs/some-unrelated-note.md"


def _sentinel_body() -> str:
    """The `run:` script of the step whose id is `relevant`.

    PREMISE CHECK, not a convenience: if the step is renamed, re-ided, or the
    job is restructured, this must fail loudly rather than silently testing
    nothing (the failure mode a `next(..., None)` would have introduced).
    """
    doc = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    steps = doc["jobs"]["mutation-gate"]["steps"]
    matching = [s for s in steps if s.get("id") == "relevant"]
    assert len(matching) == 1, (
        "expected exactly one step with id 'relevant' in p1s2-mutation-incremental.yml, "
        f"found {len(matching)} — the sentinel moved or was renamed, so this corpus "
        "stopped testing it"
    )
    body = matching[0]["run"]
    assert "GITHUB_OUTPUT" in body, (
        "the 'relevant' step no longer writes to $GITHUB_OUTPUT — it cannot be a "
        "sentinel any more, and every downstream `if:` reads an empty output"
    )
    return body


def _git(repo: pathlib.Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


@pytest.fixture()
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """A synthetic repo with a known base commit, then one commit touching a
    trust path and one touching only an irrelevant file."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.invalid")
    _git(r, "config", "user.name", "t")
    (r / "seed.txt").write_text("seed\n")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "seed")
    return r


def _commit(repo: pathlib.Path, relpath: str, msg: str) -> str:
    target = repo / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", msg)
    return _git(repo, "rev-parse", "HEAD")


def _run_sentinel(
    repo: pathlib.Path,
    event: str,
    *,
    pr_base: str = "",
    mg_base: str = "",
    shim_dir: pathlib.Path | None = None,
) -> tuple[int, str, str]:
    """Execute the real sentinel body. Returns (rc, GITHUB_OUTPUT, stdout)."""
    body = _sentinel_body()
    body = body.replace("${{ github.event_name }}", event)
    body = body.replace("${{ github.event.pull_request.base.sha }}", pr_base)
    body = body.replace("${{ github.event.merge_group.base_sha }}", mg_base)
    leftover = re.findall(r"\$\{\{[^}]*\}\}", body)
    assert not leftover, (
        "an unsubstituted ${{ }} expression remains in the sentinel body — this "
        "test would be executing a script GitHub would have expanded differently, "
        "so its verdict would be meaningless. Remaining: " + repr(leftover)
    )

    out_file = repo / "_github_output"
    out_file.write_text("")
    runner_temp = repo / "_runner_temp"
    runner_temp.mkdir(exist_ok=True)
    script = repo / "_sentinel.sh"
    script.write_text(body)

    # The flags GitHub Actions itself uses for a `run:` step on Linux:
    # `bash --noprofile --norc -e -o pipefail {0}`. Matched exactly rather than
    # invoking a plain `bash`, which would source the caller's profile and rc
    # files and so test a contaminated shell instead of the isolated one the
    # runner provides. Raised by a blind refuter of this change.
    env = {
        **os.environ,
        "GITHUB_OUTPUT": str(out_file),
        "RUNNER_TEMP": str(runner_temp),
    }
    if shim_dir is not None:
        env["PATH"] = f"{shim_dir}{os.pathsep}{env['PATH']}"
    proc = subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", str(script)],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.returncode, out_file.read_text().strip(), proc.stdout


# --------------------------------------------------------------- relevance

def test_pull_request_touching_a_trust_path_runs_the_gate(repo: pathlib.Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, _TRUST_PATH, "touch a trust path")
    rc, out, _ = _run_sentinel(repo, "pull_request", pr_base=base)
    assert rc == 0
    assert out == "run=true"


def test_merge_group_touching_a_trust_path_runs_the_gate(repo: pathlib.Path) -> None:
    """The queue must not be a hole in the gate: an entry that changes a trust
    path has to run the canary, or the queue's synthetic merge SHA is the one
    commit shape nothing ever mutation-tests."""
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, _TRUST_PATH, "touch a trust path")
    rc, out, _ = _run_sentinel(repo, "merge_group", mg_base=base)
    assert rc == 0
    assert out == "run=true"


def test_pull_request_touching_nothing_relevant_skips(repo: pathlib.Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, _IRRELEVANT_PATH, "touch nothing relevant")
    rc, out, _ = _run_sentinel(repo, "pull_request", pr_base=base)
    assert rc == 0
    assert out == "run=false"


def test_merge_group_touching_nothing_relevant_skips(repo: pathlib.Path) -> None:
    """THE reason the merge_group trigger was safe to add at all.

    Before the per-event base existed, every non-pull_request event resolved
    `run=true`, so this case would have bought a pip install of mutmut and a
    full mutation pass on EVERY entry in the merge queue, fleet-wide. If this
    test ever goes red the trigger is costing the fleet exactly what the
    workflow header says it must not.
    """
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, _IRRELEVANT_PATH, "touch nothing relevant")
    rc, out, _ = _run_sentinel(repo, "merge_group", mg_base=base)
    assert rc == 0
    assert out == "run=false"


def test_merge_group_does_not_read_the_pull_request_base(repo: pathlib.Path) -> None:
    """Guilt for the specific confusion this change exists to remove: on a
    merge_group event the pull_request payload is absent, so a body that still
    read `pull_request.base.sha` would receive an empty string. It must resolve
    the merge_group key instead — proved by giving the two keys DIFFERENT
    values and checking which one the answer reflects."""
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, _IRRELEVANT_PATH, "touch nothing relevant")
    head = _git(repo, "rev-parse", "HEAD")
    # merge_group base is the older commit (an irrelevant file changed since);
    # the pull_request base is HEAD (nothing changed since). If the sentinel
    # read the wrong key it would still answer run=false here, so the
    # discriminating case is the reverse pairing below.
    rc, out, _ = _run_sentinel(repo, "merge_group", pr_base=head, mg_base=base)
    assert rc == 0
    assert out == "run=false"

    # Now make the two keys disagree in the direction that CAN be told apart:
    # a trust path changed since `base`, nothing changed since `head2`.
    _commit(repo, _TRUST_PATH, "touch a trust path")
    head2 = _git(repo, "rev-parse", "HEAD")
    rc, out, _ = _run_sentinel(repo, "merge_group", pr_base=head2, mg_base=base)
    assert rc == 0
    assert out == "run=true", (
        "the sentinel answered as if it had read pull_request.base.sha (which "
        "points at HEAD, so nothing changed) instead of merge_group.base_sha"
    )


# ------------------------------------------------------------- fail open

def test_empty_base_fails_open_and_says_so(repo: pathlib.Path) -> None:
    """A sentinel that cannot measure must run the work, not skip it. Skipping
    on a measurement failure is a false green on a correctness gate — the one
    direction this job must never fail in."""
    rc, out, stdout = _run_sentinel(repo, "merge_group", mg_base="")
    assert rc == 0
    assert out == "run=true"
    assert "::warning::" in stdout, (
        "the sentinel fell back to running the gate but did so SILENTLY — a "
        "degradation with no channel is indistinguishable from health (W108)"
    )


def test_unresolvable_base_fails_open_and_says_so(repo: pathlib.Path) -> None:
    """`git diff` against a SHA that does not exist must not abort the step
    under `set -e` and leave the fallback as unreachable code on the only path
    it exists for."""
    rc, out, stdout = _run_sentinel(repo, "merge_group", mg_base="0" * 40)
    assert rc == 0
    assert out == "run=true"
    assert "::warning::" in stdout


def test_push_and_other_events_still_run_unconditionally(repo: pathlib.Path) -> None:
    """`push:` is paths-filtered at the trigger, so a push run that exists is a
    push run that needs the work. Unchanged behaviour, pinned so a later
    refactor of the event branching cannot quietly drop it."""
    _commit(repo, _IRRELEVANT_PATH, "touch nothing relevant")
    for event in ("push", "workflow_dispatch", "schedule"):
        rc, out, _ = _run_sentinel(repo, event)
        assert rc == 0, f"event {event} aborted the sentinel"
        assert out == "run=true", f"event {event} resolved {out!r}, expected run=true"


# ------------------------------------------------------- trigger presence

def test_workflow_declares_both_pull_request_and_merge_group() -> None:
    """The sentinel's merge_group branch is dead code unless the trigger exists;
    the trigger is a cost bomb unless the branch exists. They ship together or
    not at all, so both are asserted here rather than trusting one to imply the
    other."""
    doc = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    # PyYAML 1.1 reads a bare `on:` key as the boolean True.
    on_block = doc.get("on", doc.get(True))
    assert isinstance(on_block, dict), "the workflow's `on:` block did not parse as a mapping"
    assert "merge_group" in on_block, (
        "no merge_group trigger — a required status check with no merge_group "
        "trigger cannot be satisfied by a merge-queue run at all (conformance rule 2)"
    )
    assert "pull_request" in on_block, (
        "no pull_request trigger — a required context that fires only on the queue "
        "reports 'Expected — waiting for status' on every ordinary PR (conformance rule 3)"
    )
    assert on_block["pull_request"] is None or "paths" not in (on_block["pull_request"] or {}), (
        "a top-level paths: filter reappeared under on.pull_request — a path-miss PR "
        "would never start a run, so this context would hang 'Expected — waiting' "
        "forever (conformance rule 4, W69)"
    )


def test_checkout_keeps_full_history_or_the_sentinel_silently_stops_saving() -> None:
    """`fetch-depth: 0` is what makes the sentinel's diff resolvable at all.

    A blind refuter of the change that added the merge_group trigger argued the
    sentinel would fail on a shallow clone, because `actions/checkout` defaults
    to `fetch-depth: 1` and the base commit would not be present. The premise was
    wrong — this workflow sets `fetch-depth: 0` explicitly, and the refuter had
    not been shown the checkout step — but the FAILURE MODE it describes is real
    and worth pinning, because of how quietly it would arrive.

    If someone later "optimises" this checkout to a shallow one, `git diff` fails
    against every base, the sentinel correctly fails OPEN, and the job runs the
    full mutation gate on every PR and every queue entry forever. Nothing goes
    red. The only symptom is the saving disappearing and the queue getting
    slower — a degradation whose sole channel is a `::warning::` nobody reads.
    """
    doc = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    steps = doc["jobs"]["mutation-gate"]["steps"]
    checkouts = [s for s in steps if str(s.get("uses", "")).startswith("actions/checkout")]
    assert len(checkouts) == 1, (
        f"expected exactly one actions/checkout step, found {len(checkouts)} — the "
        "job was restructured and this pin no longer knows which checkout feeds the sentinel"
    )
    depth = (checkouts[0].get("with") or {}).get("fetch-depth")
    assert depth == 0, (
        f"actions/checkout fetch-depth is {depth!r}, not 0. The sentinel diffs against a "
        "base commit that a shallow clone does not fetch, so it would fail open on every "
        "run: the gate would still be correct and would silently stop saving anything, "
        "running a full mutation pass on every PR and every merge-queue entry."
    )


def test_a_grep_that_cannot_read_is_not_read_as_no_match(repo: pathlib.Path) -> None:
    """grep's exit code is THREE-valued and the difference decides the gate.

    0 = matched, 1 = did not match, >1 = an ERROR (unreadable file, exhausted
    file descriptors, a broken locale). An `if grep ...; then A; else B; fi`
    collapses 1 and >1 into the same branch, so a grep that could not READ the
    changed-file list would be recorded as "nothing relevant changed" and skip
    the mutation gate — a failure to measure reported as a measurement.

    Proved by executing the real body with a `grep` shim ahead of it on PATH
    that exits 2, rather than by reading the shell source. Found by a blind
    cross-family refuter of the change that added the merge_group trigger.
    """
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, _IRRELEVANT_PATH, "touch nothing relevant")

    shim = repo / "_shim"
    shim.mkdir()
    fake_grep = shim / "grep"
    fake_grep.write_text("#!/bin/sh\nexit 2\n")
    fake_grep.chmod(0o755)

    rc, out, stdout = _run_sentinel(repo, "merge_group", mg_base=base, shim_dir=shim)
    assert rc == 0, "the sentinel aborted instead of falling back"
    assert out == "run=true", (
        "a grep ERROR (rc=2) was read as 'no relevant paths changed' and skipped the "
        "gate — the false green this sentinel exists to make impossible"
    )
    assert "::warning::" in stdout, (
        "the sentinel fell back but said nothing — a degradation with no channel is "
        "indistinguishable from health"
    )


def test_a_grep_that_finds_nothing_is_still_a_skip(repo: pathlib.Path) -> None:
    """Innocence for the rule above: rc=1 must still mean skip, or the cure for
    the error case would have turned the sentinel into an always-run and quietly
    deleted the saving it exists to provide."""
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, _IRRELEVANT_PATH, "touch nothing relevant")

    shim = repo / "_shim1"
    shim.mkdir()
    fake_grep = shim / "grep"
    fake_grep.write_text("#!/bin/sh\nexit 1\n")
    fake_grep.chmod(0o755)

    rc, out, _ = _run_sentinel(repo, "merge_group", mg_base=base, shim_dir=shim)
    assert rc == 0
    assert out == "run=false"
