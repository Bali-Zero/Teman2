#!/usr/bin/env python3
r"""Guard: organ-conformance.yml must actually be wired to RUN
test_organ_heartbeat_exceeds_poller_interval.py's guard on any change to its
declared read-set (GUARD_READ_SET) — otherwise that guard sits in the exact
parking space organ-conformance.yml's own comment documents for a prior,
structurally identical, real defect: a corpus named by NO workflow executes
only inside the continue-on-error `scripts/tests/` sweep, which is green by
construction and gates nothing (cicatrix family #2, Esiste≠Armato — the
same defect class this repo's own W108 fixed for a different corpus).

Found live 2026-08-31 (independent review, team-lead + spalla, on the PR
that added the guard): `grep -rl test_organ_heartbeat_exceeds_poller_interval
.github/` returned zero hits — the guard existed, ran clean locally, and
gated nothing in CI.

Parses the workflow's own two path lists — never a second, hand-maintained
copy of "what should be there" — and asserts each is a superset of
GUARD_READ_SET (imported from the guard's own test file, the single place
that set is declared):
  1. `on.push.paths` — arms the workflow to trigger at all on a post-merge
     push to main. `pull_request` always triggers this workflow with no
     top-level path filter (the "sentinel pattern" the workflow's own
     header comment names), so this list's ONLY job is post-merge arming.
  2. the in-job `git diff --name-only "$BASE" "$HEAD" -- <pathspec>` inside
     the "Did organ surfaces change?" step (id: relevant) — decides whether
     the job's gated steps do any work on a given PR.
A path listed in one but not the other is armed for one event type and
silently skipped for the other — the workflow's own comment (near its
`scripts/lib/heartbeat.sh` entry) names this exact trap.

CORRECTED 2026-08-31 (codex-gpt-5.6-sol, this PR's own council round): a
prior draft of this docstring claimed a step invoking the two guard files
did NOT need its own check, reasoning that CI running this file at all
already proved the step's presence — an "accidentally-removed step would
take this file's collection down with it." That reasoning was WRONG: this
file's own collection does not depend on the required-workflow step at
all — remove that step and this file simply falls back to running inside
the continue-on-error `scripts/tests/` sweep, which gates nothing (the
exact defect class this whole file exists to catch, one level up). Fixed
below: test_a_step_actually_executes_both_guard_files() parses the job's
`run:` bodies directly and asserts one of them names both guard files,
closing the "step edited/typo'd/one file dropped" gap. It does NOT (and
structurally cannot) prove survival of the step's OUTRIGHT deletion — see
that test's own docstring for why, and for the residual risk this repo's
Gear-3 hot-zone gate covers instead.

YAML gotcha handled explicitly, because it bit the first draft of this
test: PyYAML's `safe_load` follows YAML 1.1 rules, under which the bare key
`on:` in a GitHub Actions workflow parses as the boolean `True`, not the
string `"on"` — read `data[True]` (falling back to `data["on"]` only for a
YAML-1.2-compliant loader, never assumed).

Bash-parsing gotcha ALSO handled explicitly, because it bit the first draft
too: the "relevant" step's `run:` text is one long string containing both
the real pathspec AND ordinary English prose comments with apostrophes
("...the G2 gene's implementation...") ahead of it. A naive "grab every
'...'-quoted token in the whole run block" regex mis-pairs on that
apostrophe and returns comment prose as fake path tokens (verified live
while writing this test — the very first version printed a "path" that was
three lines of code comment). Anchoring on the literal
`git diff --name-only "$BASE" "$HEAD" -- \` marker and stopping at the
subshell's closing `)` scopes the regex to ONLY the real pathspec.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest
import yaml

# Explicit, not relied-on-by-accident: scripts/tests/__init__.py exists but
# scripts/__init__.py does not, so under pytest's default "prepend" import
# mode this file is imported as `tests.test_organ_heartbeat_workflow_wiring`
# (scripts/ goes on sys.path, not scripts/tests/) — a bare
# `from test_organ_heartbeat_exceeds_poller_interval import ...` is NOT
# guaranteed to resolve under that scheme. Force this file's own directory
# onto sys.path first, same defensive pattern already used by
# scripts/tests/test_organism_stale_detector.py for its cross-directory
# import. Verified empirically before relying on it: both the plain
# `from test_organ_heartbeat_exceeds_poller_interval import GUARD_READ_SET`
# AND this explicit form were tried; only the explicit form is kept.
sys.path.insert(0, os.path.dirname(__file__))

from test_organ_heartbeat_exceeds_poller_interval import (  # noqa: E402
    GUARD_READ_SET,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github/workflows/organ-conformance.yml"

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


def _read_relevant_step_run(data: dict) -> str:
    try:
        steps = data["jobs"]["conformance"]["steps"]
    except (KeyError, TypeError) as exc:
        pytest.fail(f"{WORKFLOW_PATH}: cannot find jobs.conformance.steps ({exc})")
    if not isinstance(steps, list):
        pytest.fail(f"{WORKFLOW_PATH}: jobs.conformance.steps is not a list")
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
    try:
        steps = data["jobs"]["conformance"]["steps"]
    except (KeyError, TypeError) as exc:
        pytest.fail(f"{WORKFLOW_PATH}: cannot find jobs.conformance.steps ({exc})")
    if not isinstance(steps, list):
        pytest.fail(f"{WORKFLOW_PATH}: jobs.conformance.steps is not a list")
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
        "arming; missing an entry here means the guard is armed for PRs "
        "but silently disarmed after merge for the exact same change)"
    )


def test_injob_pathspec_covers_the_guard_read_set():
    data = _load_workflow()
    pathspec_tokens = _read_injob_pathspec(data)
    # Two tokens in the real pathspec are globs (`*.plist`, `**/*.plist`),
    # not literal paths — real git pathspec matching would honour them, but
    # this guard's fixture is deliberately named `*.plist.fixture` (see
    # scripts/tests/fixtures/organ_heartbeat_cadence/README.md) precisely
    # so it does NOT match those globs — it must not look like a launchd
    # organ to check_organ_conformance.py, which uses the identical glob.
    # So coverage here is checked as exact literal-string membership, the
    # same way GUARD_READ_SET's members are actually added to this list —
    # never credited via glob coverage that would defeat the fixture's own
    # naming fix.
    missing = GUARD_READ_SET - pathspec_tokens
    assert not missing, (
        f"{WORKFLOW_PATH.relative_to(REPO_ROOT)}'s in-job pathspec (inside "
        f"the 'Did organ surfaces change?' step) is missing {sorted(missing)} "
        "— a PR touching only these files would run the workflow "
        "(pull_request always triggers) but skip every gated step, "
        "including this guard's own test"
    )


def test_a_step_actually_executes_both_guard_files():
    """Codex-gpt-5.6-sol review finding, 2026-08-31 (this PR's own council
    round): the two superset assertions above prove the PATH LISTS are
    wired, but neither checks that a STEP actually invokes pytest against
    the two guard files — a step whose body is edited (wrong path, a typo,
    accidentally dropping one of the two files while "cleaning up") would
    sail through both superset checks untouched while silently running less
    than it claims to.

    Does NOT, and cannot, prove the step survives being deleted OUTRIGHT: if
    the whole step disappears, this test's own only required-workflow
    executor is gone with it, and it falls back to running inside the
    continue-on-error `scripts/tests/` sweep, which gates nothing — the same
    residual risk every OTHER named step in every required workflow in this
    repo carries (no step can prove its own non-deletion from inside
    itself). That broader class is covered by this repo's Gear-3 hot-zone
    gate on any `.github/workflows/*` edit, which this very diff went
    through — not by a test file trying to out-recurse it.
    """
    data = _load_workflow()
    run_texts = _read_conformance_job_run_texts(data)
    # Substring presence ALONE is not enough — caught live while verifying
    # this very test: "Did organ surfaces change?" (id: relevant) mentions
    # both filenames too, in its own explanatory comment and its pathspec
    # list, without ever invoking pytest on either. Requiring the literal
    # "pytest" token in the SAME run text excludes that step and anchors on
    # an actual test invocation, not a passing mention (cicatrix family #3,
    # guard-over-match on substring instead of intent).
    matching = [
        t
        for t in run_texts
        if "pytest" in t
        and "test_organ_heartbeat_exceeds_poller_interval.py" in t
        and "test_organ_heartbeat_workflow_wiring.py" in t
    ]
    assert matching, (
        f"{WORKFLOW_PATH.relative_to(REPO_ROOT)}: no step in "
        "jobs.conformance.steps has a 'run:' body invoking pytest against "
        "both test_organ_heartbeat_exceeds_poller_interval.py AND "
        "test_organ_heartbeat_workflow_wiring.py — the path lists can be "
        "perfectly wired while no step actually runs these guards (a mere "
        "MENTION of both filenames, e.g. in a comment, does not count)"
    )
