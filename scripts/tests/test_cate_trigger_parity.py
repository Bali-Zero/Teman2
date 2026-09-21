"""A guard must start on everything it scans — and this one has no filter.

catE-sovereignty-lint.yml is the only consumer of the ban-family lints in this
tree. It shipped with a path filter narrower than their scanners: nine suffixes
read, five started on, identically on both events, so a PR whose changed set
fell entirely inside the gap never started the workflow and the blocking step
never ran. PR #7000 closed that by widening the filter and pinning the two sets
to each other here.

This file is what that test became once the filter was REMOVED (2026-09-21).
The parity question disappears when there is nothing to keep in parity: with no
`paths:` on either event the workflow starts on every change, so every suffix a
scanner reads and every data file a step reads is covered by construction. What
survives is the thing construction cannot guarantee — that the absence STAYS.

Why the absence and not a wider filter: a path-filtered check cannot be made
REQUIRED without a skip-to-success sentinel, because a PR matching no path
never reports the context and pends forever (W69 BUCO #1). The filter was the
obstacle between this guard and branch protection, and a sentinel is a second
thing to keep honest. Removing the filter costs ~48s on the 12% of merges that
did not already start it (35 of the last 40 did), measured 2026-09-21.

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
EVENTS = ("pull_request", "push")


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
    assert block is None or "paths" not in block, (
        f"{event} has a paths filter again: {block.get('paths')!r}. This "
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
