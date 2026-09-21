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

What this file judges, end to end:

  - no narrowing on any trigger (test_the_workflow_declares_no_paths_filter,
    test_no_branches_ignore_on_pull_request_or_merge_group,
    test_pull_request_branches_if_present_still_covers_main);
  - the structural shapes that make a context unreportable or falsely green
    WITHOUT narrowing a single path or branch: a step- or job-level `if:`,
    `continue-on-error` anywhere, a renamed job (the required context string
    IS the job name), a runner label outside the hosted list, and a
    concurrency group that stops varying per ref, at either scope;
  - the fail-closed judgment, by EXECUTION rather than by grepping text: every
    step whose executable lines name a repo tool is run for real, on a
    synthetic git repo, once with all its tools present and passing
    (calibration/innocence), once with each tool it actually called in that
    mode made absent, and once per call with that call's stub told to fail —
    a negated existence test, an `else` that echoes and falls through, or a
    swallowed `python3 T || true` are judged on whether the STEP exits
    non-zero, not on any one spelling of the skip;
  - the tool floor (test_every_guard_tool_is_still_run): every tool the
    workflow names today stays named by some step, hard-coded as a one-way
    set, so deleting a step wholesale (e.g. Law-5) reds here even though the
    execution harness above has nothing left to run against a step that no
    longer exists;
  - the two old bindings, kept verbatim from the PR #7000 version because
    they were never about the trigger: the push-time whole-tree scan
    enumerates the prose scanner's own suffixes, since that list is a third
    transcription of the same set; and the count the prose freezes must equal
    the count on disk.

The execution harness itself, plainly: it runs the workflow's own shell with
NO network sandbox — a step that calls the network does so for real, exactly
as it would in CI; `pip` is shimmed to a no-op so `python3 -m pip install`
never touches a registry; and no parent environment or secrets reach the
steps, git, or the xargs probe — every process gets an explicit, minimal env.
The prose step's no-base path writes the shared `/tmp/ban-prose-tree.txt`, so
concurrent local runs of this suite may collide on that one file. Each step
is bounded to 120s. The concurrency-group regex and the key allowlists below
are deliberately CLOSED lists: an equivalent-but-different spelling reds, and
this test must be updated in the same diff that adds the new spelling.

Not covered — stated plainly rather than claimed as "every shape":

  - steps whose executable lines name no repo tool are never executed here —
    today that is the two Anthropic-ban grep steps (#40, #40b) and the #44
    apps/*/.env permission step;
  - a tool's own semantics are not judged, only whether the step propagates
    its exit code — a linter that is simply wrong but still exits 0 stays
    invisible to this file;
  - the whole-tree scan's warn-and-pass on an unreadable file, and the #44
    step's vacuity on hosted checkouts (`.env*` is gitignored, so
    actions/checkout never materialises one to judge), are tracked as their
    own row in .claude/skills/modus/PENDING-ARMS.md
    ("catE-passes-without-examining"), not cured by this file;
  - any `runs-on` outside HOSTED_RUNNERS reds even when a self-hosted label
    exists elsewhere in the fleet — deliberate, not an oversight.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "catE-sovereignty-lint.yml"
GRANDFATHERED = REPO / "infra" / "ban-prose" / "grandfathered.json"

CONTEXT = "catE-sovereignty-lint"
HOSTED_RUNNERS = frozenset({"ubuntu-latest", "ubuntu-24.04", "ubuntu-22.04"})

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


@pytest.mark.parametrize("event", ("pull_request", "merge_group"))
def test_pull_request_branches_if_present_still_covers_main(event: str) -> None:
    """Neither event carries a `branches:` today, meaning "any base branch"
    for pull_request and "any queued target" for merge_group. Adding one that
    omits main, or that excludes it again through a negation, would stop this
    guard firing on exactly the runs it exists to cover, while reading like a
    narrower, cheaper version of the same trigger.
    """
    block = _triggers().get(event)
    if not block or "branches" not in block:
        return
    branches = block["branches"] or []
    assert "main" in branches, (
        f"{event}.branches is {branches!r} and does not contain 'main'. That "
        f"stops this guard running on {event} runs targeting main, the branch "
        "it exists to protect. Drop `branches:` (any base branch) or include "
        "'main' in the list."
    )
    negated = [b for b in branches if isinstance(b, str) and b.startswith("!")]
    assert not negated, (
        f"{event}.branches carries a negation {negated!r} inside {branches!r}. "
        "A negated entry can exclude main again even while the literal "
        "'main' is also present in the same list — drop the negation."
    )


def test_no_step_carries_an_if_and_nothing_continues_on_error() -> None:
    """A false step-level `if:` skips the step and the job still reports
    success; `continue-on-error` turns a red step green whichever level it
    sits at. Neither belongs on a context meant to be REQUIRED — put any
    condition inside the step's own shell, where it can only choose the
    step's exit code, never whether the step (or the job) is judged to have
    run at all.
    """
    offenders = []
    for job_name, job in _jobs().items():
        if not isinstance(job, dict):
            continue
        if "continue-on-error" in job:
            offenders.append(f"job {job_name!r} carries continue-on-error")
        for step in job.get("steps", []):
            if not isinstance(step, dict):
                continue
            step_name = step.get("name", "<unnamed>")
            if "if" in step:
                offenders.append(f"job {job_name!r} step {step_name!r} carries if:")
            if "continue-on-error" in step:
                offenders.append(
                    f"job {job_name!r} step {step_name!r} carries continue-on-error"
                )
    assert not offenders, (
        f"{offenders}. A false step-level `if:` skips the step and the job "
        "still reports success; continue-on-error turns a red step green. "
        "Put the condition inside the step's shell instead — never on the "
        "step or the job."
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
        "green on a context meant to be REQUIRED. Move the condition into "
        "the step's shell instead, so the job itself always reports."
    )


def test_the_job_reports_the_context_that_will_be_required() -> None:
    """The required-context string that branch protection will store IS the
    job name — not the workflow name, not the step name. A rename here means
    the context this file exists to arm is never reported again, and every
    queue entry waits it out to the timeout instead of merging.
    """
    jobs = _jobs()
    assert list(jobs) == [CONTEXT], (
        f"the workflow declares job keys {list(jobs)}, expected exactly "
        f"[{CONTEXT!r}]. The required context string is the job name, so a "
        "rename means the context is never reported and the queue waits out "
        "its timeout."
    )
    job = jobs[CONTEXT]
    assert job.get("name") == CONTEXT, (
        f"job {CONTEXT!r}'s name: is {job.get('name')!r}, not {CONTEXT!r}. "
        "The required context string is the job name, so a rename means the "
        "context is never reported and the queue waits out its timeout."
    )


def test_the_job_runs_on_a_github_hosted_label() -> None:
    """A `runs-on` outside the hosted fleet queues forever the moment this
    context is required, with nothing red to explain why — the queue simply
    never finds a runner. Reds even if a self-hosted label exists somewhere
    on the fleet: this workflow is not wired to one, and pretending it could
    be is exactly the kind of plausible-looking edit this file exists to
    catch before it lands.
    """
    offenders = {
        name: job.get("runs-on")
        for name, job in _jobs().items()
        if isinstance(job, dict) and job.get("runs-on") not in HOSTED_RUNNERS
    }
    assert not offenders, (
        f"job(s) {offenders} do not run on a plain GitHub-hosted label "
        f"{sorted(HOSTED_RUNNERS)}. A runs-on outside the hosted list queues "
        "forever even if a self-hosted label exists elsewhere on the fleet — "
        "deliberate, not an oversight."
    )


_CONCURRENCY_PREFIX = r"(?:[A-Za-z0-9_.-]+|\$\{\{\s*github\.workflow\s*\}\}-)"
_CONCURRENCY_PER_REF = (
    r"(?:\$\{\{\s*github\.ref\s*\}\}"
    r"|\$\{\{\s*github\.head_ref\s*\|\|\s*github\.run_id\s*\}\})"
)
_CONCURRENCY_GROUP_RE = re.compile(_CONCURRENCY_PREFIX + _CONCURRENCY_PER_REF)


def test_concurrency_group_is_scoped_per_ref() -> None:
    """A constant concurrency group serializes every run of this workflow
    across the whole repo: `cancel-in-progress` would then cancel one PR's
    in-flight run because an unrelated PR started, reporting a false red on
    the innocent one. The group string must FULLMATCH a literal-prefix (or
    `${{ github.workflow }}-`) followed by exactly one per-ref expression
    (cicatrix #3: substring is not enough — a constant string that merely
    CONTAINS the text `github.ref` inside a dead branch of a ternary is not
    scoped by it).

    Also: no job may carry a job-level `concurrency`, which can serialize or
    cancel independently of the workflow-level group on however constant a
    string the job author chose.
    """
    document = yaml.safe_load(WORKFLOW.read_text())
    group = document.get("concurrency", {}).get("group", "")
    assert _CONCURRENCY_GROUP_RE.fullmatch(str(group).strip()), (
        f"concurrency.group is {group!r} and does not fullmatch "
        "<literal-prefix-or-${{ github.workflow }}->-<github.ref OR "
        "github.head_ref-or-run_id>. A constant group serializes runs across "
        "every PR/branch, and cancel-in-progress would cancel one PR's run "
        "because an unrelated PR started; a group that merely CONTAINS the "
        "substring github.ref inside otherwise-constant expression text is "
        "not scoped by it either. Restore a per-ref group, e.g. "
        "'catE-sovereignty-lint-${{ github.ref }}'."
    )
    job_level = {
        name: job["concurrency"]
        for name, job in _jobs().items()
        if isinstance(job, dict) and "concurrency" in job
    }
    assert not job_level, (
        f"job(s) carry a job-level concurrency: {job_level}. That can "
        "serialize or cancel runs independently of the workflow-level "
        "group — scoping belongs only at the workflow level."
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


# ─────────────────────────────────────────────────────────────────────────
# The tool floor: every repo tool the workflow's EXECUTABLE lines name today.
# One-way, hard-coded: it only ever SHRINKS by a step genuinely dropping a
# tool it named. Recomputed by hand from the file (2026-09-21) with:
#   re.findall(r"scripts/[\w./-]+\.(?:py|sh)\b", <non-comment run: text>)
# A step deleted wholesale (e.g. Law-5) takes its tool's only mention with
# it, so test_every_guard_tool_is_still_run reds instead of REQUIRED_TOOLS
# quietly following the deletion down.
# ─────────────────────────────────────────────────────────────────────────
REQUIRED_TOOLS = frozenset(
    {
        "scripts/ci/hotzone_changed_files.sh",
        "scripts/lint/lint_ban_prose.py",
        "scripts/lint/wr3_lint_autonomous_publish.py",
        "scripts/lint_paid_llm_entity.py",
        "scripts/test_lint_paid_llm_entity.py",
        "scripts/tests/test_ban_predicates.py",
        "scripts/tests/test_cate_paid_budget.sh",
        "scripts/tests/test_cate_trigger_parity.py",
        "scripts/tests/test_lint_ban_prose.py",
        "scripts/tests/test_typesafe_client_pin.py",
        "scripts/tests/test_vendor_authorization_fence.py",
    }
)

_TOOL_RE = re.compile(r"scripts/[\w./-]+\.(?:py|sh)\b")


def _step_executable_lines(run: str) -> str:
    return "\n".join(ln for ln in run.splitlines() if not ln.strip().startswith("#"))


def _steps_with_tools() -> list[tuple[str, dict, dict, frozenset]]:
    """Every step across every job whose executable `run:` lines name at
    least one repo tool, paired with its job and the tool set named. Read
    fresh from the live workflow file at call time (collection time, for the
    parametrize list below), so a mutated copy of the file yields a
    different set.
    """
    found = []
    for job in _jobs().values():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps", []):
            if not isinstance(step, dict):
                continue
            run = step.get("run", "")
            tools = frozenset(_TOOL_RE.findall(_step_executable_lines(run)))
            if tools:
                found.append((step.get("name", "<unnamed>"), job, step, tools))
    return found


_ALLOWED_SHELL = "bash -e {0}"


def test_no_step_overrides_the_shell() -> None:
    """The execution harness below runs every step under `bash -e`, which is
    what GitHub uses for a `run:` block with no `shell:`. A step that sets
    its own `shell:` (e.g. `bash {0}`, which drops `-e`) would run in CI
    under rules the harness does not reproduce, so its verdict there would
    be about a different program. Keeping `-e` in force does NOT make a
    failing tool abort the step wherever it is called: bash suppresses `-e`
    inside an `if`/`while`/`until` CONDITION and for any command that is
    part of an `&&` or `||` list — it only aborts on a failure in top-level,
    unconditional command position. An explicit `shell: bash -e {0}` is
    allowed below, since it spells out that same default rather than
    overriding it.
    """
    offenders = sorted(
        f"{name!r}: {step.get('name') or step.get('uses')!r}"
        for name, job in _jobs().items()
        if isinstance(job, dict)
        for step in job.get("steps", [])
        if isinstance(step, dict) and step.get("shell") not in (None, _ALLOWED_SHELL)
    )
    offenders += sorted(
        f"{name!r}: defaults.run.shell"
        for name, job in _jobs().items()
        if isinstance(job, dict)
        and (job.get("defaults") or {}).get("run", {}).get("shell") not in (None, _ALLOWED_SHELL)
    )
    document = yaml.safe_load(WORKFLOW.read_text())
    workflow_shell = ((document.get("defaults") or {}).get("run") or {}).get("shell")
    if workflow_shell not in (None, _ALLOWED_SHELL):
        offenders.append("workflow: defaults.run.shell")
    assert not offenders, (
        f"shell overridden at {offenders}. GitHub's default for `run:` is "
        f"`{_ALLOWED_SHELL}`, the only shell test_step_fails_closed "
        f"reproduces; an explicit `shell: {_ALLOWED_SHELL}` is allowed "
        "since it spells out that same default, but any other override "
        "(e.g. `bash {0}`, which drops -e) lets a failing tool fall through "
        "unjudged. Remove the override and keep the default shell."
    )


def test_every_guard_tool_is_still_run() -> None:
    """Every tool in REQUIRED_TOOLS must still be named by some step's
    executable lines. Deleting a step (e.g. the Law-5 guard) takes its only
    mention with it and reds here — the execution harness below cannot catch
    this shape, because there is nothing left for it to run.
    """
    named: set[str] = set()
    for _, _, _, tools in _steps_with_tools():
        named |= tools
    missing = REQUIRED_TOOLS - named
    assert not missing, (
        f"tool(s) {sorted(missing)} are in REQUIRED_TOOLS but no step names "
        "them any more. REQUIRED_TOOLS is a one-way floor: either the tool "
        "is still meant to run (restore the step that named it) or it is "
        "genuinely retired (drop it from REQUIRED_TOOLS in the same diff "
        "that removes the step)."
    )


# ─────────────────────────────────────────────────────────────────────────
# Structural allowlists: a key outside these is either inert or dangerous,
# and the only way to tell which is to look — so it reds instead of passing
# silently. Each set below is EXACTLY the keys the current file uses,
# printed and verified against the live document before being hard-coded
# here (`python3 -c "import yaml; d=yaml.safe_load(open('.github/workflows/
# catE-sovereignty-lint.yml')); ..."`, run 2026-09-21), with one deliberate
# exception noted at STEP_KEYS. A new key must be added here in the SAME
# diff that adds it to the workflow — that is the point of a closed list.
# ─────────────────────────────────────────────────────────────────────────
WORKFLOW_TOP_LEVEL_KEYS = frozenset({"name", "on", "permissions", "concurrency", "jobs"})
JOB_KEYS = frozenset({"name", "runs-on", "timeout-minutes", "steps"})
# `shell` is NOT used by any step today, yet it is allowed here on purpose:
# test_no_step_overrides_the_shell already vets its one legitimate value
# (`bash -e {0}`, GitHub's own default spelled out) and reds any other, so
# the allowlist's job — catching a key nobody has vetted — is already done
# for this one by a dedicated test.
STEP_KEYS = frozenset({"uses", "with", "name", "run", "env", "shell"})

# Job keys that would each be a way this job's required context stops
# reporting, fans out under a matrix suffix (so the exact string branch
# protection expects never reports), runs on an unreviewed image, or turns
# a red into a green.
_BANNED_JOB_KEYS = (
    "needs",
    "strategy",
    "container",
    "services",
    "defaults",
    "environment",
    "if",
    "continue-on-error",
    "concurrency",
)
# Step keys that would each let one step skip, swallow its own exit code, or
# run somewhere other than the checkout this harness reproduces.
_BANNED_STEP_KEYS = ("if", "continue-on-error", "working-directory", "timeout-minutes")


def _normalized_top_level_keys(document: dict) -> set:
    # YAML 1.1 reads a bare `on` as the boolean True — normalize it back to
    # the string "on" so offender messages read like the file, same reason
    # _triggers() does not simply index document["on"].
    keys = set(document)
    if True in keys:
        keys.discard(True)
        keys.add("on")
    return keys


def test_the_workflow_job_and_steps_use_only_known_keys() -> None:
    """`test_no_job_level_if_on_any_job` and
    `test_no_step_carries_an_if_and_nothing_continues_on_error` already
    catch `if`/`continue-on-error` specifically; this is the general case —
    `needs`, `strategy` (a matrix suffixes the required-context name, so the
    exact string branch protection expects never reports), `container`,
    `working-directory`, a step-level `timeout-minutes`, and any future key
    nobody has reviewed against what this workflow is trying to guarantee.
    """
    document = yaml.safe_load(WORKFLOW.read_text())
    top_offenders = sorted(_normalized_top_level_keys(document) - WORKFLOW_TOP_LEVEL_KEYS)
    assert not top_offenders, (
        f"workflow top level carries unknown key(s) {top_offenders}. Add "
        "them to WORKFLOW_TOP_LEVEL_KEYS in this test, in the same diff, if "
        "they are deliberate."
    )
    assert "defaults" not in document, (
        "workflow carries a top-level `defaults:` — a workflow-level "
        "defaults.run.shell/working-directory would apply to every job "
        "without a single grep hit naming it at the job or step. Put the "
        "setting explicitly where it applies, or extend this test "
        "deliberately."
    )
    for job_name, job in _jobs().items():
        if not isinstance(job, dict):
            continue
        job_offenders = sorted(set(job) - JOB_KEYS)
        assert not job_offenders, (
            f"job {job_name!r} carries unknown key(s) {job_offenders}. Add "
            "them to JOB_KEYS in this test, in the same diff, if they are "
            "deliberate."
        )
        for banned in _BANNED_JOB_KEYS:
            assert banned not in job, (
                f"job {job_name!r} carries {banned!r}. needs/strategy/"
                "container/services/defaults/environment/if/"
                "continue-on-error/concurrency are each a way this job's "
                "required context could stop reporting, fan out under a "
                "matrix suffix, run on an unreviewed image, or turn a red "
                "into a green — deliberately not allowed here."
            )
        for step in job.get("steps", []):
            if not isinstance(step, dict):
                continue
            step_name = step.get("name") or step.get("uses") or "<unnamed>"
            step_offenders = sorted(set(step) - STEP_KEYS)
            assert not step_offenders, (
                f"job {job_name!r} step {step_name!r} carries unknown "
                f"key(s) {step_offenders}. Add them to STEP_KEYS in this "
                "test, in the same diff, if they are deliberate."
            )
            for banned in _BANNED_STEP_KEYS:
                assert banned not in step, (
                    f"job {job_name!r} step {step_name!r} carries "
                    f"{banned!r}. if/continue-on-error/working-directory/"
                    "timeout-minutes on a step are each a way that one "
                    "step could skip, swallow its own exit code, or run "
                    "somewhere other than the checkout this harness "
                    "reproduces — deliberately not allowed here."
                )


def test_job_timeout_minutes_is_at_least_the_recorded_floor() -> None:
    """One-way floor at today's value. A required check's timeout blocks an
    INNOCENT PR rather than merely re-running a flaky job — unlike a normal
    workflow, it has no headroom — and 20 is the value set for the recorded
    599s worst-case checkout (see the comment above `timeout-minutes:` in
    the workflow, #3649). Lowering it again reintroduces the ~1s margin
    that prompted raising it from 10.
    """
    for job_name, job in _jobs().items():
        if not isinstance(job, dict):
            continue
        timeout = job.get("timeout-minutes")
        assert isinstance(timeout, int) and not isinstance(timeout, bool), (
            f"job {job_name!r} timeout-minutes is {timeout!r}, not a plain "
            "int."
        )
        assert timeout >= 20, (
            f"job {job_name!r} timeout-minutes is {timeout}, below the "
            "recorded floor of 20. A required check's timeout blocks an "
            "innocent PR, and 20 is the value set for the recorded 599s "
            "worst-case checkout (#3649) — do not lower it without a fresh "
            "measurement."
        )


# ─────────────────────────────────────────────────────────────────────────
# The fail-closed judgment, by EXECUTION, per real trigger EVENT.
#
# Every step found above is run for real, under `bash -e` (GitHub's actual
# default shell for `run:` — not plain `bash script`), against a synthetic
# git repo holding stub tools, once per event in EVENTS (pull_request, push,
# merge_group) with that event's own context rendered into the step's env
# and `run:` text. Shapes like `if [ ! -f T ]; then exit 0; fi`,
# `[ -s T ] || ...`, `[ -e T ] || exit 0`, an `else` that echoes and falls
# through, `python3 T || true`, and a skip keyed on `github.event_name` or
# `$GITHUB_EVENT_NAME` (for only one event) are all control flow and cannot
# be judged by grepping text — they can only be judged by running the
# script, with the right event's context in place, and reading its own exit
# code.
# ─────────────────────────────────────────────────────────────────────────

# Fixed, fake, 40-hex-char SHAs — one per role, so a bug that mixes up
# base/head/merge shows up in a failure message instead of silently
# matching by coincidence.
_FAKE_PR_MERGE_SHA = "a1" * 20
_FAKE_PR_BASE_SHA = "b2" * 20
_FAKE_PR_HEAD_SHA = "c3" * 20
_FAKE_PUSH_SHA = "d4" * 20
_FAKE_MERGE_GROUP_BASE_SHA = "e5" * 20
_FAKE_MERGE_GROUP_HEAD_SHA = "f6" * 20

# The per-event context the expression renderer below resolves a
# `github.`/`secrets.` path against — one entry per event in EVENTS. GitHub
# renders any property of an event that did not fire as an empty string,
# which is why `event.pull_request.*` is "" on push and merge_group, and
# `event.merge_group.*` is "" everywhere except merge_group. `secrets.*` is
# handled separately in _resolve_context_path (any key renders ""), so it is
# not listed per-event here.
GITHUB_CONTEXTS: dict[str, dict] = {
    "pull_request": {
        "event_name": "pull_request",
        "ref": "refs/pull/1/merge",
        "sha": _FAKE_PR_MERGE_SHA,
        "run_id": "100000001",
        "workflow": "catE-sovereignty-lint",
        "repository": "bali-zero/nuzantara",
        "head_ref": "feature",
        "base_ref": "main",
        "token": "fake-github-token",
        "event": {
            "pull_request": {
                "base": {"sha": _FAKE_PR_BASE_SHA},
                "head": {"sha": _FAKE_PR_HEAD_SHA},
                "number": "1",
            },
        },
    },
    "push": {
        "event_name": "push",
        "ref": "refs/heads/main",
        "sha": _FAKE_PUSH_SHA,
        "run_id": "100000002",
        "workflow": "catE-sovereignty-lint",
        "repository": "bali-zero/nuzantara",
        "head_ref": "",
        "base_ref": "",
        "token": "fake-github-token",
        "event": {
            "pull_request": {
                "base": {"sha": ""},
                "head": {"sha": ""},
                "number": "",
            },
        },
    },
    "merge_group": {
        "event_name": "merge_group",
        "ref": f"refs/heads/gh-readonly-queue/main/pr-1-{_FAKE_MERGE_GROUP_BASE_SHA}",
        "sha": _FAKE_MERGE_GROUP_HEAD_SHA,
        "run_id": "100000003",
        "workflow": "catE-sovereignty-lint",
        "repository": "bali-zero/nuzantara",
        "head_ref": "",
        "base_ref": "",
        "token": "fake-github-token",
        "event": {
            "pull_request": {
                "base": {"sha": ""},
                "head": {"sha": ""},
                "number": "",
            },
            "merge_group": {
                "head_sha": _FAKE_MERGE_GROUP_HEAD_SHA,
                "base_sha": _FAKE_MERGE_GROUP_BASE_SHA,
            },
        },
    },
}

# Tools whose OUTPUT a step merely consumes (the changed-file list). Their
# stub always prints "x.py" and succeeds unless told to fail — a step is
# never required to call one of these on a push or merge_group run (no PR
# base to enumerate against).
HELPERS = frozenset({"scripts/ci/hotzone_changed_files.sh"})

# A step may legitimately never call one of these on a push or merge_group
# run: the tool judges a PR's diff against its base, and only a
# pull_request run has one. On pull_request itself there is no exemption —
# see the coverage check in test_step_fails_closed.
PR_TIME_ONLY = frozenset({"scripts/lint_paid_llm_entity.py"})


def _resolve_context_path(path: str, event: str, original: str):
    """Resolve a `${{ }}` context path (e.g. `github.event.pull_request.base
    .sha`) against GITHUB_CONTEXTS[event], or fail closed.

    `secrets.<anything>` always renders "" — this harness never has a real
    secret to render. Any other root context, or any path
    GITHUB_CONTEXTS[event] does not carry all the way down, fails the test
    instead of silently rendering an empty string: an unrepresented shape
    must be loud, not invisible.
    """
    parts = path.split(".")
    if parts[0] == "secrets":
        return ""
    if parts[0] != "github":
        pytest.fail(
            f"expression {original!r} on event {event!r} uses context "
            f"{parts[0]!r}, which this harness does not model — extend the "
            "harness's context table."
        )
    node: object = GITHUB_CONTEXTS[event]
    seen = ["github"]
    for key in parts[1:]:
        seen.append(key)
        if isinstance(node, dict) and key in node:
            node = node[key]
        else:
            pytest.fail(
                f"expression {original!r} on event {event!r}: "
                f"{'.'.join(seen)!r} is not in the context table — extend "
                "the harness's context table."
            )
    return node


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    return value != ""


def _render_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


_EXPR_TOKEN_RE = re.compile(r"==|!=|&&|\|\||!|\(|\)|'(?:[^']|'')*'|[A-Za-z_][A-Za-z0-9_.]*")


def _tokenize_expr(expr: str, event: str, original: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    pos = 0
    n = len(expr)
    while pos < n:
        if expr[pos].isspace():
            pos += 1
            continue
        m = _EXPR_TOKEN_RE.match(expr, pos)
        if not m:
            pytest.fail(
                f"cannot parse expression {original!r} on event {event!r} "
                f"at {expr[pos:pos + 20]!r} — extend the harness's context "
                "table."
            )
        text = m.group(0)
        if text[0] == "'":
            tokens.append(("string", text[1:-1].replace("''", "'")))
        elif text in ("==", "!=", "&&", "||", "!", "(", ")"):
            tokens.append(("op", text))
        else:
            tokens.append(("path", text))
        pos = m.end()
    return tokens


class _ExprParser:
    """Recursive-descent parser for the subset of GitHub Actions expression
    syntax this workflow uses: context paths, single-quoted string literals,
    `==`/`!=`, `&&`, `||`, parentheses, and unary `!`. Precedence, high to
    low: `!` > `==`/`!=` > `&&` > `||` — GitHub's own documented order, not
    Python's.
    """

    def __init__(self, tokens: list[tuple[str, str]], event: str, original: str):
        self.tokens = tokens
        self.pos = 0
        self.event = event
        self.original = original

    def _peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _fail(self, msg: str):
        pytest.fail(
            f"cannot parse expression {self.original!r} on event "
            f"{self.event!r}: {msg} — extend the harness's context table."
        )

    def parse(self):
        value = self._or_expr()
        if self.pos != len(self.tokens):
            self._fail(f"unexpected trailing token {self.tokens[self.pos]!r}")
        return value

    def _or_expr(self):
        left = self._and_expr()
        while self._peek() == ("op", "||"):
            self._advance()
            right = self._and_expr()
            left = left if _truthy(left) else right
        return left

    def _and_expr(self):
        left = self._eq_expr()
        while self._peek() == ("op", "&&"):
            self._advance()
            right = self._eq_expr()
            left = right if _truthy(left) else left
        return left

    def _eq_expr(self):
        left = self._unary()
        while self._peek() in (("op", "=="), ("op", "!=")):
            op = self._advance()[1]
            right = self._unary()
            equal = _render_value(left) == _render_value(right)
            left = equal if op == "==" else not equal
        return left

    def _unary(self):
        if self._peek() == ("op", "!"):
            self._advance()
            return not _truthy(self._unary())
        return self._primary()

    def _primary(self):
        tok = self._peek()
        if tok is None:
            self._fail("unexpected end of expression")
        kind, text = tok
        if kind == "string":
            self._advance()
            return text
        if kind == "path":
            self._advance()
            return _resolve_context_path(text, self.event, self.original)
        if tok == ("op", "("):
            self._advance()
            value = self._or_expr()
            if self._peek() != ("op", ")"):
                self._fail("missing closing parenthesis")
            self._advance()
            return value
        self._fail(f"unexpected token {tok!r}")


_EXPR_BLOCK_RE = re.compile(r"\$\{\{(.*?)\}\}", re.DOTALL)


def _render_expr(expr_text: str, event: str) -> str:
    original = expr_text.strip()
    tokens = _tokenize_expr(original, event, original)
    if not tokens:
        pytest.fail(
            f"empty '${{{{ }}}}' expression on event {event!r} — extend "
            "the harness's context table."
        )
    value = _ExprParser(tokens, event, original).parse()
    return _render_value(value)


def _render_text(text: str, event: str) -> str:
    """Substitute every `${{ expr }}` in `text` with its rendered value for
    `event` — GitHub does this to both `env:` values and `run:` bodies
    before the shell ever sees either.
    """
    return _EXPR_BLOCK_RE.sub(lambda m: _render_expr(m.group(1), event), text)


def _env_block(mapping) -> dict:
    return {str(k): str(v) for k, v in (mapping or {}).items()}


def _rendered_step_env(step: dict, job: dict, document: dict, event: str) -> dict:
    """Workflow env, then job env, then the step's own env — later
    overrides earlier, same precedence as GitHub — each value rendered
    through `${{ }}` for `event` before it ever reaches the step's process.
    """
    combined: dict[str, str] = {}
    combined.update(_env_block(document.get("env")))
    combined.update(_env_block(job.get("env")))
    combined.update(_env_block(step.get("env")))
    return {k: _render_text(v, event) for k, v in combined.items()}


def _probe_xargs_needs_shim() -> bool:
    # Probed ONCE, at collection time, with a minimal env (PATH only — never
    # the parent environment, the same rule every step below is run under):
    # GNU xargs (CI, most Linux) supports -r/-d natively; BSD xargs
    # implements -r but not -d. Only shim it where it fails.
    try:
        probe = subprocess.run(
            ["xargs", "-r", "-d", "\\n", "true"],
            input="",
            text=True,
            capture_output=True,
            timeout=10,
            env={"PATH": os.environ.get("PATH", "")},
        )
    except (OSError, subprocess.TimeoutExpired):
        return True
    return probe.returncode != 0


NEEDS_XARGS_SHIM = _probe_xargs_needs_shim()


_PYTHON_SHIM = r"""#!/bin/sh
# no network: `python3 -m pip install ...` (step "ban-predicates") always
# succeeds without touching a registry.
if [ "$1" = "-m" ] && [ "$2" = "pip" ]; then
  exit 0
fi
exec "__EXECUTABLE__" "$@"
"""

_XARGS_SHIM = r"""#!/bin/sh
# Minimal GNU-xargs-compatible shim for `-r` and `-d '<delim>'` (BSD xargs
# implements -r but not -d natively). This repo's workflow only ever calls
# it as `xargs -r -d '\n' <cmd> ...`, so splitting on newline is the whole
# of the decoded delimiter this shim supports.
r_flag=0
while [ $# -gt 0 ]; do
  case "$1" in
    -r) r_flag=1; shift ;;
    -d) shift 2 ;;
    *) break ;;
  esac
done

had_input=0
while IFS= read -r line || [ -n "$line" ]; do
  had_input=1
  set -- "$@" "$line"
done

if [ "$had_input" = 0 ] && [ "$r_flag" = 1 ]; then
  exit 0
fi

"$@"
rc=$?
if [ "$rc" -ge 1 ] && [ "$rc" -le 125 ]; then
  exit 123
fi
exit "$rc"
"""

_PY_STUB = r"""import os
import sys

SELF = "__SELF__"
_LOG = os.environ.get("CATE_STUB_LOG")
_FAIL_SPEC = os.environ.get("CATE_STUB_FAIL", "")


def _record_call():
    n = 1
    if _LOG and os.path.exists(_LOG):
        with open(_LOG) as f:
            n = sum(1 for line in f if line.strip() == SELF) + 1
    if _LOG:
        with open(_LOG, "a") as f:
            f.write(SELF + "\n")
    return n


_CALL_N = _record_call()
_FAILING = _FAIL_SPEC == (SELF + ":" + str(_CALL_N))

if __name__ == "__main__":
    print("x.py")
    sys.exit(1 if _FAILING else 0)


def test_stub():
    assert not _FAILING
"""

_SH_STUB = r"""#!/bin/sh
SELF="__SELF__"
LOG="$CATE_STUB_LOG"
N=1
if [ -n "$LOG" ] && [ -f "$LOG" ]; then
  COUNT=$(grep -c -F -x "$SELF" "$LOG")
  N=$((COUNT + 1))
fi
if [ -n "$LOG" ]; then
  printf '%s\n' "$SELF" >> "$LOG"
fi
echo x.py
if [ "$CATE_STUB_FAIL" = "$SELF:$N" ]; then
  exit 1
fi
exit 0
"""


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _write_stub(repo: Path, tool: str) -> None:
    path = repo / tool
    path.parent.mkdir(parents=True, exist_ok=True)
    if tool.endswith(".py"):
        path.write_text(_PY_STUB.replace("__SELF__", tool))
    else:
        path.write_text(_SH_STUB.replace("__SELF__", tool))
    path.chmod(0o755)


def _write_shims(shim_dir: Path) -> None:
    for name in ("python3", "python"):
        path = shim_dir / name
        path.write_text(_PYTHON_SHIM.replace("__EXECUTABLE__", sys.executable))
        path.chmod(0o755)
    if NEEDS_XARGS_SHIM:
        path = shim_dir / "xargs"
        path.write_text(_XARGS_SHIM)
        path.chmod(0o755)


def _git_env(home: Path) -> dict:
    # Minimal, like the step env: nothing from the parent environment but PATH.
    return {
        "PATH": os.environ.get("PATH", ""),
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "HOME": str(home),
    }


def _make_repo(base: Path, tools: frozenset, home: Path) -> Path:
    repo = Path(tempfile.mkdtemp(dir=base, prefix="repo-"))
    genv = _git_env(home)
    subprocess.run(["git", "init", "-q", "--template="], cwd=repo, env=genv, check=True)
    (repo / "x.py").write_text("pass\n")
    for tool in tools:
        _write_stub(repo, tool)
    subprocess.run(["git", "add", "-A"], cwd=repo, env=genv, check=True)
    return repo


def _default_env(
    shim_dir: Path,
    home: Path,
    runner_temp: Path,
    stub_log: Path,
    repo: Path,
    event: str,
    gh_files: dict,
) -> dict:
    """GitHub's own default variables for `event`, plus this harness's
    minimal shim/stub plumbing. Never the parent environment — every key
    here is explicit; BASE_SHA/HEAD_SHA/PR_NUMBER are NOT injected here —
    they come only from rendering the step's own `env:` (see
    _rendered_step_env), the same as on a real runner.
    """
    ctx = GITHUB_CONTEXTS[event]
    return {
        "PATH": f"{shim_dir}:{os.environ.get('PATH', '')}",
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "RUNNER_TEMP": str(runner_temp),
        "RUNNER_OS": "Linux",
        "CI": "true",
        "GITHUB_ACTIONS": "true",
        "CATE_STUB_LOG": str(stub_log),
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GITHUB_EVENT_NAME": ctx["event_name"],
        "GITHUB_REF": ctx["ref"],
        "GITHUB_SHA": ctx["sha"],
        "GITHUB_HEAD_REF": ctx["head_ref"],
        "GITHUB_BASE_REF": ctx["base_ref"],
        "GITHUB_REPOSITORY": ctx["repository"],
        "GITHUB_WORKFLOW": ctx["workflow"],
        "GITHUB_RUN_ID": ctx["run_id"],
        "GITHUB_WORKSPACE": str(repo),
        "GITHUB_STEP_SUMMARY": str(gh_files["summary"]),
        "GITHUB_OUTPUT": str(gh_files["output"]),
        "GITHUB_ENV": str(gh_files["env"]),
        "GITHUB_PATH": str(gh_files["path"]),
    }


def _run_step(step_path: Path, repo: Path, env: dict) -> subprocess.CompletedProcess:
    # `bash -e {0}` is GitHub's default shell for a `run:` block — not plain
    # `bash script`. Without -e a step's own `set -uo pipefail` (no `-e`)
    # would let an unchecked command's failure fall through silently.
    return subprocess.run(
        ["bash", "-e", str(step_path)],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _call_counts(stub_log: Path) -> dict:
    counts: dict = {}
    if stub_log.exists():
        for line in stub_log.read_text().splitlines():
            line = line.strip()
            if line:
                counts[line] = counts.get(line, 0) + 1
    return counts


def _fail_closed_cases():
    cases = []
    for name, job, step, tools in _steps_with_tools():
        for event in EVENTS:
            cases.append(pytest.param(job, step, tools, event, id=f"{_slug(name)}/{event}"))
    return cases


_FAIL_CLOSED_CASES = _fail_closed_cases()


@pytest.mark.parametrize("job,step,tools,event", _FAIL_CLOSED_CASES)
def test_step_fails_closed(
    tmp_path: Path, job: dict, step: dict, tools: frozenset, event: str
) -> None:
    """Runs one step's own `run:` script, for real, against a synthetic
    repo, under the rendered context of one real trigger event.

    CALIBRATION proves the harness can say yes (all tools present, passing,
    with that event's `env:`/`${{ }}` rendered exactly as GitHub would).
    Then, coverage is judged per event: on pull_request every named tool
    must be called, no exemption — there IS a PR base, so nothing legitimately
    skips; on push and merge_group a tool never called reds unless it is a
    HELPER or PR_TIME_ONLY exemption (there is no PR base to run a PR-time
    tool against). Every CALLED tool made ABSENT must fail the step, and
    every call that tool made, told to FAIL, must fail the step too — which
    is what catches `|| true` on one of several invocations, or a skip keyed
    on `github.event_name`/`$GITHUB_EVENT_NAME`/an inline `${{ }}` for only
    one event. Failure messages say: fail closed with an `::error::` naming
    the file and `exit 1`; never swallow the tool's exit.
    """
    step_name = step.get("name", "<unnamed>")
    run_script = step.get("run", "")
    assert run_script, f"step {step_name!r} has no run: block to execute"

    document = yaml.safe_load(WORKFLOW.read_text())
    rendered_step_env = _rendered_step_env(step, job, document, event)
    rendered_script = _render_text(run_script, event)

    home = tmp_path
    shim_dir = tmp_path / "shim"
    shim_dir.mkdir()
    _write_shims(shim_dir)
    runner_temp = tmp_path / "runner_temp"
    runner_temp.mkdir()
    stub_log = tmp_path / "stub.log"
    step_path = tmp_path / "step.sh"
    step_path.write_text(rendered_script)
    gh_files = {
        "summary": tmp_path / "github_step_summary.txt",
        "output": tmp_path / "github_output.txt",
        "env": tmp_path / "github_env.txt",
        "path": tmp_path / "github_path.txt",
    }
    for gh_file in gh_files.values():
        gh_file.write_text("")

    def env_for(repo: Path, extra: dict | None = None) -> dict:
        if stub_log.exists():
            stub_log.unlink()
        env = _default_env(shim_dir, home, runner_temp, stub_log, repo, event, gh_files)
        env.update(rendered_step_env)
        if extra:
            env.update(extra)
        return env

    # --- CALIBRATION / innocence: all named tools present and passing ---
    repo = _make_repo(tmp_path, tools, home)
    result = _run_step(step_path, repo, env_for(repo))
    assert result.returncode == 0, (
        f"CALIBRATION: step {step_name!r} ({event}) exited {result.returncode} "
        "with every named tool present and passing — the harness cannot say "
        f"yes.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    called = _call_counts(stub_log)

    # --- coverage: a tool this step names but never calls on this event ---
    for tool in sorted(tools):
        if called.get(tool, 0) > 0:
            continue
        if event in ("push", "merge_group") and (tool in HELPERS or tool in PR_TIME_ONLY):
            # legitimately exempt: no PR base to run a PR-time tool
            # against, judged separately for push and merge_group.
            continue
        pytest.fail(
            f"step {step_name!r}: on a {event} run this step never runs "
            f"{tool}, so it would pass unexamined. On pull_request there is "
            "no exemption; on push/merge_group only a HELPERS or "
            "PR_TIME_ONLY tool may legitimately go uncalled."
        )

    called_tools = sorted(t for t, n in called.items() if n > 0)

    # --- ABSENT: the tool this step called is missing entirely ---
    for tool in called_tools:
        repo_absent = _make_repo(tmp_path, tools - {tool}, home)
        result = _run_step(step_path, repo_absent, env_for(repo_absent))
        assert result.returncode != 0, (
            f"step {step_name!r} ({event}): with {tool} ABSENT the step "
            "still exits 0. Fail closed with an ::error:: naming the file "
            f"and exit 1; never swallow the tool's exit.\nstdout:\n"
            f"{result.stdout}\nstderr:\n{result.stderr}"
        )

    # --- FAIL-ON-CALL-k: each call this step made to a tool, told to fail ---
    for tool in called_tools:
        for k in range(1, called[tool] + 1):
            repo_fail = _make_repo(tmp_path, tools, home)
            result = _run_step(
                step_path,
                repo_fail,
                env_for(repo_fail, {"CATE_STUB_FAIL": f"{tool}:{k}"}),
            )
            assert result.returncode != 0, (
                f"step {step_name!r} ({event}): call {k} of {tool} failing "
                "did not fail the step (exit 0). Fail closed with an "
                "::error:: naming the file and exit 1; never swallow the "
                f"tool's exit.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
