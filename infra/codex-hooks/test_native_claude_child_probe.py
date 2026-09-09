"""Regression cases for the native child probe's parent/child discrimination.

The probe shipped a default invocation that could not pass on any host: it
selected child observations by a `claude-<family>-` model prefix, and the parent
dispatcher runs `claude-haiku-4-5` while `--model` defaults to `haiku`, so the
parent's own SessionStart observation was counted as a child. `transport_passed`
requires `len(child_observations) == args.children`; with the parent included the
count was always one too high. R2 was accepted on a diff check without a native
run, which is why this went unmeasured.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from native_claude_child_probe import select_child_observations

PARENT = {
    "hook_event_name": "SessionStart",
    "model": "claude-haiku-4-5",
    "capacity_scope": "scope-a",
}
CHILD = {
    "hook_event_name": "SubagentStop",
    "model": "claude-haiku-4-5-20251001",
    "capacity_scope": "scope-a",
}


def test_parent_sharing_the_child_family_is_not_counted_as_a_child():
    # The exact shape of the default invocation: both sides are haiku, so any
    # model-prefix filter returns 2 here. Only the event discriminates.
    assert select_child_observations([PARENT, CHILD]) == [CHILD]


def test_a_prefix_filter_would_have_returned_the_parent_too():
    # Pins WHY the event is the discriminator: this is the old predicate, and it
    # is still true of the parent. If this assertion ever fails, the prefix filter
    # became safe again and this test's premise needs revisiting.
    assert PARENT["model"].startswith("claude-haiku-")
    assert CHILD["model"].startswith("claude-haiku-")


def test_child_count_matches_children_for_a_parallel_dispatch():
    observations = [PARENT] + [dict(CHILD) for _ in range(4)]
    assert len(select_child_observations(observations)) == 4


def test_an_unlabelled_observation_is_not_a_child():
    # Defensive: a snapshot that lost its event tag must not silently pass as a
    # child. Cannot-verify is not a verdict.
    assert select_child_observations([{"model": "claude-haiku-4-5-20251001"}]) == []


def test_a_child_on_a_different_model_is_still_a_child():
    # Selection is by event; the MODEL is asserted separately by the probe, so a
    # child answering on the wrong model must reach that assertion rather than
    # vanish from the count.
    other = dict(CHILD, model="claude-sonnet-5")
    assert select_child_observations([PARENT, other]) == [other]
