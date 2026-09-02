#!/usr/bin/env python3
r"""Guard: organ-conformance.yml must actually be wired to RUN
test_self_reporting_cron_own_plist_margin.py's guard — otherwise it sits in
the exact parking space its sibling
(test_organ_heartbeat_exceeds_poller_interval.py) sat in until 2026-09-01:
a corpus named by NO workflow executes only inside the continue-on-error
`scripts/tests/` sweep, which is green by construction and gates nothing
(cicatrix family #2, Esiste≠Armato).

This file is the sibling of test_organ_heartbeat_workflow_wiring.py, NOT an
extension of it -- deliberately independent (same reasoning that file's own
module docstring gives for keeping the bridge organ_id regex duplicated
rather than shared: a bug in one guard's parsing, or an import failure in
one guard's test module, must never silently take the other guard's wiring
proof down with it). The YAML/workflow-shape parsing helpers below are
therefore a second, independent implementation of the same small amount of
logic, not an import.

Read-set kept deliberately minimal (GUARD_READ_SET below): the new guard's
OTHER two inputs -- apps/organism/organism/organs_registry.yaml and every
tracked `*.plist` -- are already covered by organ-conformance.yml's
existing path lists (the registry is listed explicitly; every tracked
plist matches the existing bare `'*.plist'` / `'**/*.plist'` entries,
confirmed empirically: `git ls-files -- '*.plist'` matches plist files at
any depth, e.g. apps/organism/organism/launchd/*.plist and
docs/infra/launchagents/*.plist, both real, live install locations this
guard's own module docstring names). scripts/launchagent-state-bridge.py
is also already listed (shared with the sibling guard, which reads it for
the identical purpose: the set to EXCLUDE, here; the set to include, there).
The only member that needs a NEW literal path entry is this guard's own
test file -- nothing else in its read-set is un-covered.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github/workflows/organ-conformance.yml"

GUARD_READ_SET: frozenset[str] = frozenset(
    {
        "scripts/tests/test_self_reporting_cron_own_plist_margin.py",
        "scripts/tests/test_self_reporting_cron_workflow_wiring.py",
    }
)

_PATHSPEC_START_MARKER = 'git diff --name-only "$BASE" "$HEAD" -- \\'
_QUOTED_TOKEN_RE = re.compile(r"'([^']+)'")


def _load_workflow() -> dict:
    if not WORKFLOW_PATH.is_file():
        pytest.fail(f"cannot read {WORKFLOW_PATH} — missing")
    try:
        data = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        pytest.fail(f"cannot parse {WORKFLOW_PATH} as YAML: {exc}")
    if not isinstance(data, dict):
        pytest.fail(f"{WORKFLOW_PATH}: top level is not a mapping")
    return data


def _read_push_paths(data: dict) -> set[str]:
    # YAML 1.1: the bare key `on` parses as the boolean True, not "on".
    on_block = data[True] if True in data else data.get("on")
    if not isinstance(on_block, dict):
        pytest.fail(
            f"{WORKFLOW_PATH}: no usable 'on:' block (checked both the "
            "boolean True key and the string 'on' key)"
        )
    push = on_block.get("push")
    if not isinstance(push, dict):
        pytest.fail(f"{WORKFLOW_PATH}: 'on.push' is not a mapping — cannot read its paths")
    paths = push.get("paths")
    if not isinstance(paths, list) or not paths:
        pytest.fail(f"{WORKFLOW_PATH}: 'on.push.paths' is missing or empty")
    return set(paths)


def _read_conformance_steps(data: dict) -> list[dict]:
    try:
        steps = data["jobs"]["conformance"]["steps"]
    except (KeyError, TypeError) as exc:
        pytest.fail(f"{WORKFLOW_PATH}: cannot find jobs.conformance.steps ({exc})")
    if not isinstance(steps, list):
        pytest.fail(f"{WORKFLOW_PATH}: jobs.conformance.steps is not a list")
    return steps


def _read_relevant_step_run(data: dict) -> str:
    steps = _read_conformance_steps(data)
    matches = [s for s in steps if isinstance(s, dict) and s.get("id") == "relevant"]
    if len(matches) != 1:
        pytest.fail(
            f"{WORKFLOW_PATH}: expected exactly one step with id: relevant, "
            f"found {len(matches)} — the job was restructured, this test "
            "needs updating, not silently skipping"
        )
    run_text = matches[0].get("run")
    if not isinstance(run_text, str) or not run_text.strip():
        pytest.fail(f"{WORKFLOW_PATH}: the 'relevant' step has no usable 'run' text")
    return run_text


def _read_injob_pathspec(data: dict) -> set[str]:
    run_text = _read_relevant_step_run(data)
    occurrences = run_text.count(_PATHSPEC_START_MARKER)
    if occurrences != 1:
        pytest.fail(
            f"{WORKFLOW_PATH}: expected exactly one occurrence of the "
            f"pathspec start marker {_PATHSPEC_START_MARKER!r} in the "
            f"'relevant' step's run text, found {occurrences} — the step "
            "was restructured, this test needs updating, not silently "
            "skipping"
        )
    start = run_text.index(_PATHSPEC_START_MARKER) + len(_PATHSPEC_START_MARKER)
    tail = run_text[start:]
    if ")" not in tail:
        pytest.fail(
            f"{WORKFLOW_PATH}: no closing ')' found after the pathspec "
            "start marker — cannot bound the pathspec extraction"
        )
    pathspec_blob = tail[: tail.index(")")]
    tokens = set(_QUOTED_TOKEN_RE.findall(pathspec_blob))
    if not tokens:
        pytest.fail(
            f"{WORKFLOW_PATH}: parsed zero single-quoted path tokens out of "
            "the pathspec block — the regex or the source shape changed"
        )
    return tokens


def _read_conformance_job_run_texts(data: dict) -> list[str]:
    steps = _read_conformance_steps(data)
    return [
        s["run"]
        for s in steps
        if isinstance(s, dict) and isinstance(s.get("run"), str)
    ]


def test_push_paths_cover_the_guard_read_set():
    data = _load_workflow()
    push_paths = _read_push_paths(data)
    missing = GUARD_READ_SET - push_paths
    assert not missing, (
        f"{WORKFLOW_PATH.relative_to(REPO_ROOT)}'s on.push.paths is missing "
        f"{sorted(missing)} — a post-merge push touching only these files "
        "would never re-trigger this workflow at all (pull_request has no "
        "top-level path filter, so this list's only job is post-merge "
        "arming)"
    )


def test_injob_pathspec_covers_the_guard_read_set():
    data = _load_workflow()
    pathspec_tokens = _read_injob_pathspec(data)
    missing = GUARD_READ_SET - pathspec_tokens
    assert not missing, (
        f"{WORKFLOW_PATH.relative_to(REPO_ROOT)}'s in-job pathspec (inside "
        f"the 'Did organ surfaces change?' step) is missing {sorted(missing)} "
        "— a PR touching only these files would run the workflow "
        "(pull_request always triggers) but skip every gated step, "
        "including this guard's own test"
    )


def test_a_step_actually_executes_the_guard_file():
    """Mirrors the sibling guard's own council-round finding (codex-gpt-5.6-
    sol, 2026-08-31): path-list coverage alone does not prove a STEP invokes
    pytest against the guard file. Requiring the literal 'pytest' token in
    the SAME run text as the filename excludes a step that only MENTIONS the
    file (e.g. in a pathspec list or a comment) without ever running it.

    Requires BOTH guard files' names (not just the arithmetic guard's) in the
    same matching run text — codex-gpt-5.6-sol council finding, 2026-09-02:
    an earlier draft checked only for
    test_self_reporting_cron_own_plist_margin.py, so a step edit that dropped
    THIS file's own name from the pytest invocation line (while keeping its
    sibling's) would leave this very test — this file's sole proof that CI
    still runs it — silently passing while its own executor was gone."""
    data = _load_workflow()
    run_texts = _read_conformance_job_run_texts(data)
    matching = [
        t
        for t in run_texts
        if "pytest" in t
        and "test_self_reporting_cron_own_plist_margin.py" in t
        and "test_self_reporting_cron_workflow_wiring.py" in t
    ]
    assert matching, (
        f"{WORKFLOW_PATH.relative_to(REPO_ROOT)}: no step in "
        "jobs.conformance.steps has a 'run:' body invoking pytest against "
        "BOTH test_self_reporting_cron_own_plist_margin.py AND "
        "test_self_reporting_cron_workflow_wiring.py — the path lists can "
        "be perfectly wired while no step actually runs one or both guards "
        "(a mere MENTION of a filename, e.g. in a comment, does not count)"
    )
