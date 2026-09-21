#!/usr/bin/env python3
"""A guard must start on everything it scans.

catE-sovereignty-lint.yml is the only consumer of the ban-family lints in this
tree, and it shipped with a path filter narrower than their scanners: nine
suffixes read, five started on, identically on both events. The Gear-3 gate on
PR #6968 computed that set (`.jsx .mjs .yaml .yml`) and called it condition 1.
A PR whose changed set fell entirely inside it never started the workflow, so
the blocking step never ran and nothing downstream ever looked again — the push
filter repeats the pull_request one, and a later run only ever sees its own
diff.

The gap is the kind that returns: it opens by ADDING a suffix to a scanner, in
a diff that has no reason to mention a workflow. So the two sets are compared
here rather than re-audited by hand, and the failure message names what to add.

Three bindings, all in the same direction — the trigger may be wider than the
scanners, never narrower:

  1. every suffix the scanners read has a `**<suffix>` entry on BOTH events;
  2. every DATA file a step reads is covered on both events (the pardon list
     is read by the blocking step and judged by --base-ref, and a PR that grew
     it while touching nothing else started nothing). Covered, not "listed
     literally": the vendor fence declares its registry as the directory glob
     `infra/vendor-authorizations/**`, which is coverage of the file below it,
     so both spellings are accepted and nothing else is;
  3. the push-time whole-tree scan enumerates the prose scanner's own suffixes,
     since that list is a third transcription of the same set;
  4. no filter entry is a NEGATION. The three bindings above test PRESENCE, and
     presence equals coverage only while nothing takes coverage back: a `!`
     pattern after a positive one excludes what the positive one admitted, and
     every assertion here would still pass (refuting seat, finding 2 — measured,
     seven of seven tests green with `!**.yml` appended). So the convention is
     declared rather than inferred: this filter carries no exclusions.

`**<suffix>` is the required spelling and `**/*<suffix>` is NOT accepted as an
equivalent, because it is not one — GitHub's `**` matches any characters
including `/`, so `**/*.yml` demands a slash and never matches a yml at the
repository root, while `**.yml` matches both (official filter-pattern cheat
sheet, re-read by a council seat rather than remembered).

Plus condition 2 of the same verdict: the count the prose freezes must equal
the count on disk. It was written 16 against a list of 11 — a sentence
contradicted by the file beside it, inside the lane whose entire subject is
sentences that lie about code.
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
DATA_FILES = (
    "infra/ban-prose/grandfathered.json",
    "scripts/tests/fixtures/paid_llm_entity/bench_cases.json",
    # Not this lane's guard and listed here on purpose (PR #6989): the vendor
    # authorization registry is read by scripts/typesafe_client.py, which the
    # workflow runs, and a PR that adds a vendor to it touches nothing else.
    # A cure that only defends the caller's own steps leaves the next lane to
    # rediscover the same hole, so the binding covers the guard next door too.
    "infra/vendor-authorizations/authorized_endpoints.json",
)

EVENTS = ("pull_request", "push")


def _module(name: str, relative: str):
    path = REPO / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"cannot load {relative}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_prose = _module("lint_ban_prose", "scripts/lint/lint_ban_prose.py")
_entity = _module("lint_paid_llm_entity", "scripts/lint_paid_llm_entity.py")

SCANNED_SUFFIXES = set(_prose.ALL_PROSE_SUFFIXES) | set(_entity.SOURCE_SUFFIXES)


def _triggers() -> dict:
    document = yaml.safe_load(WORKFLOW.read_text())
    # YAML 1.1 reads a bare `on` as the boolean true, which is why this is not
    # simply document["on"].
    triggers = document.get("on", document.get(True))
    assert isinstance(triggers, dict), "the workflow header did not parse"
    return triggers


def _paths(event: str) -> list[str]:
    block = _triggers()[event]
    assert isinstance(block, dict) and "paths" in block, f"{event} has no paths filter"
    return list(block["paths"])


@pytest.mark.parametrize("event", EVENTS)
def test_every_scanned_suffix_starts_the_workflow(event: str) -> None:
    declared = set(_paths(event))
    missing = sorted(s for s in SCANNED_SUFFIXES if f"**{s}" not in declared)
    assert not missing, (
        f"the scanners read {missing} but {event} does not start on them — "
        f"add {[f'**{s}' for s in missing]} to the filter, or narrow the "
        "scanner and say why in the same diff"
    )


def _covers(entry: str, path: str) -> bool:
    """Does one filter entry start the workflow for `path`?

    Two shapes only, and an entry this reader cannot evaluate is NOT coverage:
    the literal path, and a `dir/**` prefix (GitHub's `**` matches any
    characters including `/`, so the glob covers every file beneath dir). A
    filter entry in any other shape makes this test red rather than green,
    which is the direction a fail-closed reader has to lean.
    """
    if entry == path:
        return True
    return entry.endswith("/**") and path.startswith(entry[: -len("**")])


@pytest.mark.parametrize("event", EVENTS)
def test_the_data_a_step_reads_starts_the_workflow(event: str) -> None:
    declared = set(_paths(event))
    missing = sorted(
        f for f in DATA_FILES if not any(_covers(e, f) for e in declared)
    )
    assert not missing, (
        f"{missing} is read by a step but does not start {event}: a PR that "
        "edits only that file is exactly the PR the check cannot see"
    )


def test_the_two_events_carry_the_same_filter() -> None:
    # Sorted, not positional: a council seat swapped two entries inside one
    # event — identical coverage, cosmetic — and this test called it a hole in
    # the tree. What matters is the SET; the order of a filter list means
    # nothing to GitHub.
    pull_request, push = (sorted(_paths(e)) for e in EVENTS)
    assert pull_request == push, (
        "pull_request and push filters cover different sets — a hole in one of "
        "them is a hole in the tree, because the push run is what catches what "
        "the PR run never started on"
    )


def _executable_lines() -> str:
    # Comments only: a reader that accepts them can be satisfied by a STALE
    # comment while the live command drifts — measured by a council seat, which
    # removed a glob from the command, left the old line commented above it, and
    # watched all seven tests pass (finding 4).
    return "\n".join(
        ln for ln in WORKFLOW.read_text().splitlines() if not ln.strip().startswith("#")
    )


@pytest.mark.parametrize("event", EVENTS)
def test_no_filter_entry_takes_coverage_back(event: str) -> None:
    negations = [p for p in _paths(event) if p.startswith("!")]
    assert not negations, (
        f"{event} carries exclusion pattern(s) {negations}. Every other test "
        "here proves a pattern is PRESENT, which equals coverage only while "
        "nothing subtracts from it — so this filter carries no exclusions"
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
