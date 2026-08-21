#!/usr/bin/env python3
"""Guilt + innocence corpus for the L4 content-identity skip clause.

L4 (2026-08-21, token-ceremony CI-critical-path audit,
research/operations/2026-08-21-token-ceremony-ci-system-audit.md §7): `Backend
Tests (Python)` in .github/workflows/tests.yml runs the full ~21,430-test
suite on BOTH `pull_request` and `merge_group` — median ~29min either event,
measured on 121 paired runs 2026-08-20/21. Verdict divergence between the two
events was 0/63 real flips in that sample (only 2 ambiguous `None`-conclusion
cases): once a PR's own run is green, the queue's re-run of the IDENTICAL
tree essentially never disagrees. When the tree really is byte-identical
(main did not move between the PR run and the queue run — measured 3/63,
~4.8%), re-running it is provably redundant, not merely likely-redundant.

The `changes` job now computes `backend_tests_tree_sha` (the git tree hash of
the checked-out commit — for `pull_request` this is GitHub's own
`refs/pull/<N>/merge` test-merge commit, empirically confirmed via a live
job's checkout log, so it is directly comparable to what `merge_group` later
tests) and restores a cache keyed on that hash to produce
`backend_tests_tree_verified`. `backend-tests`' own `if:` gets ONE tail
clause: skip only when `event_name == 'merge_group' AND
backend_tests_tree_verified == 'true'`.

This is NOT a textual substring guard (cicatrix-superscar.md family #3's
usual target — `infra/guard-conformance/registry.json`) — it is an exact
cryptographic tree-hash equality check, so it cannot over-match on a
"looks similar" text pattern. The risk class here is closer to family #2
(esiste != armato — a skip that fires when it should not) and family #9
(a proxy that lies) than family #3, hence a standalone guilt+innocence
corpus in this file rather than a `infra/guard-conformance/` registration
(that registry is scoped to `_guard_*`-prefixed textual reply guards).

`pull_request` is DELIBERATELY never eligible to skip via this clause — see
`test_innocence_pull_request_never_skips_even_if_verified` below. It is the
run that establishes ground truth in the first place, and it is not merely
redundant work: 3 of the 5 real `pull_request` `Backend Tests (Python)`
failures in the same 2026-08-20/21 sample were in the big "Run unit tests"
step itself (the other 2 were in earlier, faster steps) — a PR-side skip
would defer most of today's fast catches to the far more disruptive queue
(ejection = +60min for that PR per the audit's own estimate). Only
`merge_group` — the run this repo's doctrine already treats as THE gate,
never the PR run — is eligible, and only on a provable exact match.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

WORKFLOW_PATH = (
    Path(__file__).resolve().parents[2] / ".github" / "workflows" / "tests.yml"
)


def backend_tests_tree_verified_expr(cache_hit: str | None) -> str:
    """Mirrors `changes.outputs.backend_tests_tree_verified` verbatim:

        ${{ steps.tree-cache.outputs.cache-hit == 'true' && 'true' || 'false' }}

    GitHub Actions expressions here are string-typed: only the EXACT string
    'true' ever yields 'true'. Every other value — missing, empty, 'True',
    'TRUE', '1' — yields 'false'. Fail-open by construction: nothing this
    function can be called with produces a skip except an exact 'true'.
    """
    return "true" if cache_hit == "true" else "false"


def should_skip_backend_tests(event_name: str, tree_verified: str | None) -> bool:
    """Mirrors ONLY the L4 tail clause added to `backend-tests`' `if:`:

        !(github.event_name == 'merge_group' &&
          needs.changes.outputs.backend_tests_tree_verified == 'true')

    Returns True when that clause evaluates to False — i.e. when it is the
    clause, not the pre-existing run-condition, that causes the job to skip.
    The clause is AND-ed onto the existing `if:`, so it can only ever REMOVE
    a reason to run, never add one — every other clause in the `if:` is
    untouched by this function.
    """
    return event_name == "merge_group" and tree_verified == "true"


class BackendTestsTreeSkipTests(unittest.TestCase):
    # ---- guilt: the ONE case this clause exists for ----

    def test_guilt_merge_group_with_verified_tree_skips(self) -> None:
        self.assertTrue(should_skip_backend_tests("merge_group", "true"))

    # ---- innocence: every adjacent case must still run ----

    def test_innocence_pull_request_never_skips_even_if_verified(self) -> None:
        # See module docstring: pull_request establishes ground truth and
        # measurably catches real regressions the queue run does not need
        # to re-discover — this clause must never touch it, regardless of
        # what the tree-verified output says.
        self.assertFalse(should_skip_backend_tests("pull_request", "true"))

    def test_innocence_merge_group_without_verified_tree_runs(self) -> None:
        self.assertFalse(should_skip_backend_tests("merge_group", "false"))

    def test_innocence_merge_group_missing_output_runs(self) -> None:
        self.assertFalse(should_skip_backend_tests("merge_group", None))

    def test_innocence_merge_group_malformed_output_runs(self) -> None:
        # Fail-open on anything that is not the exact string 'true' — a
        # value that merely LOOKS truthy ('True', 'TRUE', '1', 'yes') must
        # never satisfy this, or the guard would over-match on shape instead
        # of the one literal value the cache-restore step can actually emit.
        for bogus in ("True", "TRUE", "1", "yes", "", "null"):
            with self.subTest(bogus=bogus):
                self.assertFalse(should_skip_backend_tests("merge_group", bogus))

    def test_innocence_other_events_never_reach_the_clause(self) -> None:
        # push/schedule/workflow_dispatch already run unconditionally via
        # the pre-existing first OR-branch of backend-tests' if: — this
        # clause only narrows pull_request/merge_group, it cannot turn an
        # always-run event off.
        for event in ("push", "schedule", "workflow_dispatch"):
            with self.subTest(event=event):
                self.assertFalse(should_skip_backend_tests(event, "true"))

    def test_tree_verified_output_defaults_false_on_missing_cache_hit(self) -> None:
        self.assertEqual(backend_tests_tree_verified_expr(None), "false")
        self.assertEqual(backend_tests_tree_verified_expr(""), "false")
        self.assertEqual(backend_tests_tree_verified_expr("false"), "false")

    def test_tree_verified_output_true_only_on_exact_cache_hit(self) -> None:
        self.assertEqual(backend_tests_tree_verified_expr("true"), "true")

    # ---- self-conformance: the mirror above must match the LIVE workflow,
    # so an edit to the real YAML that silently changes this logic breaks
    # this test, not just the mirror's own internal consistency (W65-class:
    # a corpus that only tests itself proves nothing about the artifact).

    def test_workflow_contains_the_exact_skip_clause(self) -> None:
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "!(github.event_name == 'merge_group' && "
            "needs.changes.outputs.backend_tests_tree_verified == 'true')",
            text,
            "backend-tests' if: no longer contains the L4 tail clause "
            "verbatim — either it was edited (re-verify guilt+innocence "
            "still hold above) or removed (this file now tests a clause "
            "that does not exist).",
        )

    def test_workflow_tail_clause_is_and_not_or(self) -> None:
        # The clause must be impossible to OR in: an OR here could widen
        # the skip far beyond the one intended case (family #3's over-match
        # shape, even though this guard itself is not textual).
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        match = re.search(
            r"\)\s*(&&|\|\|)\s*\n\s*!\(github\.event_name == 'merge_group'",
            text,
        )
        self.assertIsNotNone(
            match, "could not locate the tail clause's join operator"
        )
        assert match is not None  # mypy/type-narrowing for the line below
        self.assertEqual(
            match.group(1),
            "&&",
            f"tail clause is joined with {match.group(1)!r}, not '&&' — an "
            "OR here could make the job skip in cases far beyond the one "
            "intended",
        )

    def test_workflow_tree_verified_output_expression_unchanged(self) -> None:
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "backend_tests_tree_verified: ${{ steps.tree-cache.outputs."
            "cache-hit == 'true' && 'true' || 'false' }}",
            text,
        )

    def test_workflow_restore_step_is_continue_on_error(self) -> None:
        # A cache-service hiccup on the restore must fail OPEN (job still
        # runs), never silently propagate as an unset/errored output that
        # some future refactor might misread as a hit.
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        section_start = text.index("Check prior verdict for this exact backend-tests tree")
        section = text[section_start : section_start + 300]
        self.assertIn("continue-on-error: true", section)


if __name__ == "__main__":
    unittest.main(verbosity=2)
