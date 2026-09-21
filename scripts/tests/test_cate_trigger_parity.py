"""A guard must start on everything it scans — and this one has no filter.

catE-sovereignty-lint.yml is the only consumer of the ban-family lints in this
tree. It shipped with a path filter narrower than their scanners: nine suffixes
read, five started on, identically on both events, so a PR whose changed set
fell entirely inside the gap never started the workflow and the blocking step
never ran. PR #7000 closed that by widening the filter and pinning the two sets
to each other here.

This file is what that test became once the filter was REMOVED (2026-09-21).
The parity question disappears when there is nothing to keep in parity: with no
`paths:` on any event the workflow starts on every change, so every suffix a
scanner reads and every data file a step reads is covered by construction. What
survives is the thing construction cannot guarantee — that the absence STAYS.

Why the absence and not a wider filter: a path-filtered check cannot be made
REQUIRED without a skip-to-success sentinel, because a PR matching no path
never reports the context and pends forever (W69 BUCO #1). The filter was the
obstacle between this guard and branch protection, and a sentinel is a second
thing to keep honest. Removing the filter costs some fan-out on merges that
would not otherwise have started it; the measured cost is recorded in this
change's evidence pack, not frozen here.

Two bindings that the filter's removal does NOT satisfy, kept verbatim from the
PR #7000 version because they were never about the trigger:

  1. the push-time whole-tree scan enumerates the prose scanner's own suffixes,
     since that list is a third transcription of the same set;
  2. the count the prose freezes must equal the count on disk. It was written
     16 against a list of 11 — a sentence contradicted by the file beside it,
     inside the lane whose entire subject is sentences that lie about code.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "catE-sovereignty-lint.yml"
GRANDFATHERED = REPO / "infra" / "ban-prose" / "grandfathered.json"

# Data a step READS, as opposed to source it scans. Listed by hand because the
# reading happens in shell inside the workflow, where no import can find it.
#
# merge_group is in this tuple too, not only pull_request/push: the narrowing
# check below must cover it, because a `paths:`/`paths-ignore:` planted under
# merge_group is the same pending-forever shape (W69 BUCO #1) on the one event
# a REQUIRED context cannot afford to miss.
EVENTS = ("pull_request", "push", "merge_group")


def _module(name: str, relative: str):
    path = REPO / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"cannot load {relative}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_prose = _module("lint_ban_prose", "scripts/lint/lint_ban_prose.py")


def _triggers() -> dict:
    document = yaml.safe_load(WORKFLOW.read_text())
    # YAML 1.1 reads a bare `on` as the boolean true, which is why this is not
    # simply document["on"].
    triggers = document.get("on", document.get(True))
    assert isinstance(triggers, dict), "the workflow header did not parse"
    return triggers


def _jobs() -> dict:
    document = yaml.safe_load(WORKFLOW.read_text())
    jobs = document.get("jobs")
    assert isinstance(jobs, dict) and jobs, "the workflow declares no jobs"
    return jobs


@pytest.mark.parametrize("event", EVENTS)
def test_the_workflow_declares_no_paths_filter(event: str) -> None:
    """The whole cure, and the only thing that can regress.

    A `paths:` here is not wrong in itself — it was reasonable on 2026-06-12
    and it will look just as reasonable the next time fan-out is trimmed. It is
    wrong for THIS workflow while the goal is branch protection, and it is the
    single edit that silently un-arms it. So the guard is on the absence, and
    the failure message says what to do instead rather than just refusing.
    """
    block = _triggers()[event]
    # Both keys, not one: `paths-ignore` makes the same PR never report the
    # context, from the other side, and a guard that only knew `paths` would
    # stay green under it — the gap check_required_workflow_conformance.py
    # closed for its rule 4 on 2026-08-29, found in this test by its author
    # before the council saw it.
    narrowing = [k for k in ("paths", "paths-ignore") if block and k in block]
    assert not narrowing, (
        f"{event} carries {narrowing} again: {[block.get(k) for k in narrowing]!r}. This "
        "workflow runs unconditionally on purpose — a path-filtered check "
        "cannot be REQUIRED without a skip-to-success sentinel, because a PR "
        "matching no path never reports the context and pends forever. If the "
        "fan-out cost has genuinely become a problem, add the sentinel job in "
        "the same diff and rewrite this test to bind the filter to the "
        "scanners, the way PR #7000 did."
    )


def test_the_workflow_triggers_on_merge_group() -> None:
    """A required context must be reportable by a merge-queue run.

    test_advisory_workflows_no_merge_group.py enforces this for every workflow
    that infra/required.d/contexts.json lists — but that snapshot is
    regenerated AFTER branch protection changes, so between the flip that makes
    this context required and the regen that records it, nothing else would
    notice the trigger going missing. This closes that window for the one
    workflow whose whole purpose in this file is to become required.
    """
    triggers = _triggers()
    assert "merge_group" in triggers, (
        "catE has no merge_group trigger. Once this context is required, a "
        "merge-queue run can never report it, and every queue entry waits for "
        "it until the 90-minute timeout — a fleet-wide stall with nothing red "
        "to fix."
    )


def test_the_push_event_is_still_scoped_to_main() -> None:
    """Removing `paths:` must not remove the branch scope with it.

    `branches: [main]` is not a path filter and is not what W69 bites on — it
    selects which pushes matter, not which files. Deleting it would run the
    whole-tree scan on every branch push, which is noise rather than coverage.
    """
    push = _triggers()["push"]
    assert isinstance(push, dict) and push.get("branches") == ["main"], (
        f"the push event is no longer scoped to main: {push!r}"
    )


def test_pull_request_types_include_the_full_default_set() -> None:
    """A `types:` list on pull_request REPLACES GitHub's default set (opened,
    synchronize, reopened) rather than adding to it — one of the platform's
    own footguns. Dropping `synchronize` off a required guard would let it
    stop re-running when new commits land on an already-open PR, silently, so
    any `types:` added here must still carry all three defaults.
    """
    block = _triggers()["pull_request"]
    if not block or "types" not in block:
        return
    types = set(block["types"])
    required = {"opened", "synchronize", "reopened"}
    missing = required - types
    assert not missing, (
        f"pull_request.types is missing {sorted(missing)}: {block['types']!r}. "
        "A `types:` list REPLACES GitHub's default set rather than adding to "
        "it, so this must include opened, synchronize AND reopened, or the "
        "workflow silently stops re-running on new commits or on reopen. "
        "Either drop `types:` entirely (keeping the default set) or list all "
        "three."
    )


@pytest.mark.parametrize("event", ("pull_request", "merge_group"))
def test_no_branches_ignore_on_pull_request_or_merge_group(event: str) -> None:
    """`branches-ignore` narrows exactly the way `paths-ignore` narrows: a
    PR/queue entry whose branch is ignored never reports this context — the
    same pending-forever shape (W69 BUCO #1) the rest of this file exists to
    keep out, just spelled on branches instead of paths.
    """
    block = _triggers().get(event)
    assert not (block and "branches-ignore" in block), (
        f"{event} carries branches-ignore: {block.get('branches-ignore')!r}. "
        "That is the same pending-forever narrowing as paths-ignore (W69 BUCO "
        "#1) — a matching branch never reports this context. Remove it; a "
        "branch that genuinely must be excluded is a branch-protection "
        "decision, not a trigger-level one."
    )


def test_pull_request_branches_if_present_still_covers_main() -> None:
    """pull_request carries no `branches:` today, meaning "any base branch".
    Adding one that omits main would stop this guard firing on exactly the
    PRs it exists to cover, while reading like a narrower, cheaper version of
    the same trigger.
    """
    block = _triggers()["pull_request"]
    if not block or "branches" not in block:
        return
    branches = block["branches"] or []
    assert "main" in branches, (
        f"pull_request.branches is {branches!r} and does not contain 'main'. "
        "That stops this guard running on PRs targeting main, the branch it "
        "exists to protect. Drop `branches:` (any base branch) or include "
        "'main' in the list."
    )


def test_no_job_level_if_on_any_job() -> None:
    """A job-level `if:` that evaluates false SKIPS the job, and GitHub
    reports a skipped job as a successful check — a false green on a context
    this workflow exists to make REQUIRED. Put a condition inside a step, not
    on the job.
    """
    offenders = sorted(
        name
        for name, job in _jobs().items()
        if isinstance(job, dict) and "if" in job
    )
    assert not offenders, (
        f"job(s) {offenders} carry a job-level `if:`. A false condition SKIPS "
        "the whole job, and GitHub reports a skipped job as success — a false "
        "green on a context meant to be REQUIRED. Move the condition into a "
        "step's `if:` instead, so the job itself always reports."
    )


def test_concurrency_group_is_scoped_per_ref() -> None:
    """A constant concurrency group serializes every run of this workflow
    across the whole repo: `cancel-in-progress` would then cancel one PR's
    in-flight run because an unrelated PR started, reporting a false red on
    the innocent one. The group string must keep varying per ref.
    """
    document = yaml.safe_load(WORKFLOW.read_text())
    group = document.get("concurrency", {}).get("group", "")
    assert "github.ref" in group, (
        f"concurrency.group is {group!r} and no longer contains github.ref. "
        "A constant group serializes runs across every PR/branch, and "
        "cancel-in-progress would cancel one PR's run because an unrelated "
        "PR started — restore the per-ref group, e.g. "
        "'catE-sovereignty-lint-${{ github.ref }}'."
    )


def test_no_step_warns_and_skips_when_its_own_tool_is_absent() -> None:
    """A step that warns and continues when the file it runs is missing turns
    'the linter was deleted' into a green run instead of a red one — the exact
    shape the #43 Law-5 step used to have. Read via yaml (a step's `run:`
    body), not by grepping comments, so the shape is caught wherever it lives
    in the script, not only where a comment happens to describe it.

    Judged on the shape, not on one spelling of the skip message: any step
    that tests for a file's existence must exit non-zero and must not emit a
    ::warning:: — the message could be reworded, the fall-through could not.
    """
    existence_test = re.compile(r"\[\s+-[ef]\s|\btest\s+-[ef]\s")
    for job_name, job in _jobs().items():
        steps = job.get("steps", []) if isinstance(job, dict) else []
        for step in steps:
            run = step.get("run", "") if isinstance(step, dict) else ""
            if not existence_test.search(run):
                continue
            assert "exit 1" in run and "::warning::" not in run, (
                f"job {job_name!r} step {step.get('name')!r} tests for a file "
                "and warns or falls through when it is absent. A required "
                "guard must fail closed when its tool is missing: print an "
                "::error:: naming the file and exit 1 instead."
            )


def _executable_lines() -> str:
    # Comments only: a reader that accepts them can be satisfied by a STALE
    # comment while the live command drifts — measured by a council seat, which
    # removed a glob from the command, left the old line commented above it, and
    # watched the suite pass anyway (finding 4). This reader is the cure the
    # finding bought, so that same mutation reds here now.
    return "\n".join(
        ln for ln in WORKFLOW.read_text().splitlines() if not ln.strip().startswith("#")
    )


def test_the_push_time_tree_scan_enumerates_the_prose_suffixes() -> None:
    line = re.search(r"git ls-files -- (.+?)\\\n", _executable_lines() + "\n")
    assert line, "the push-time whole-tree scan is no longer where this test reads it"
    globs = re.findall(r"'\*(\.[a-z]+)'", line.group(1))
    assert set(globs) == set(_prose.ALL_PROSE_SUFFIXES), (
        f"the push-time tree scan enumerates {sorted(set(globs))} while the "
        f"scanner reads {sorted(_prose.ALL_PROSE_SUFFIXES)}"
    )


def test_the_frozen_count_in_prose_equals_the_list_on_disk() -> None:
    on_disk = len(json.loads(GRANDFATHERED.read_text())["files"])
    pattern = re.compile(r"(\d+)\s*\n?#?\s*files (?:that )?already\s*\n?#?\s*carried")
    for path in (WORKFLOW, REPO / "scripts" / "lint" / "lint_ban_prose.py"):
        stated = [int(n) for n in pattern.findall(path.read_text())]
        assert stated, f"{path.name} no longer states the frozen count where this test reads it"
        assert all(n == on_disk for n in stated), (
            f"{path.name} freezes {stated} files, the list on disk carries {on_disk}"
        )
