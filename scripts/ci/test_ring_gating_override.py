#!/usr/bin/env python3
"""Guilt + innocence corpus for the ring-gating manual kill switch.

Merge-OS v2 round-2 Cure #1 (adapted 2026-08-18 — PENDING-ARMS.md "Wave 2
of Merge-OS v2 may be armed ONLY with the four round-2 cures incorporated").
Two layers, both exercised here:

1. The SCRIPT's own truth table (`ring_gating_override.sh`), invoked as a
   real subprocess — never a Python re-implementation of its shell logic,
   which would only prove the two copies agree with each other (the exact
   self-referential-guard trap cicatrix-superscar.md family #3 warns about).
2. The WIRED shape in `.github/workflows/tests.yml` — round-2's third cure
   ("guilt corpus must test the WIRED needs:-based shape, not only the bare
   expression, else a skipped classifier job silently skips its dependents",
   W117-class) demanded exactly this: proving the override script is truly
   consulted by the `changes` job's `if:` conditions, not merely correct in
   isolation. A script that behaves perfectly but was never wired into an
   `if:` would pass every test in layer 1 and gate nothing.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

import yaml

SCRIPT = Path(__file__).with_name("ring_gating_override.sh")
WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "tests.yml"

GATED_STEP_IDS = ("extract", "classifier-tests", "classify")
EXPECTED_GATE = "steps.override.outputs.active != 'true'"


def _run(value: str | None) -> str:
    env = {}
    if value is not None:
        env["MERGEOS_RING_GATING_DISABLED"] = value
    completed = subprocess.run(
        ["bash", str(SCRIPT)],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()


class RingGatingOverrideScriptTests(unittest.TestCase):
    """Layer 1 — the script's own truth table, executed for real."""

    def test_guilt_exact_true_activates_override(self) -> None:
        self.assertEqual(_run("true"), "active=true")

    def test_innocence_unset_stays_inactive(self) -> None:
        self.assertEqual(_run(None), "active=false")

    def test_innocence_empty_string_stays_inactive(self) -> None:
        self.assertEqual(_run(""), "active=false")

    def test_innocence_literal_false_stays_inactive(self) -> None:
        self.assertEqual(_run("false"), "active=false")

    def test_innocence_case_variant_stays_inactive(self) -> None:
        # Case-sensitivity is a deliberate safety property, not an oversight:
        # only the exact lowercase literal "true" may widen the suite. Any
        # near-miss must fail toward the classifier's own already-fail-open
        # default, never toward a silently-neutralized override.
        self.assertEqual(_run("TRUE"), "active=false")
        self.assertEqual(_run("True"), "active=false")

    def test_innocence_typo_stays_inactive(self) -> None:
        for typo in ("1", "yes", "on", "  true  ", "true "):
            self.assertEqual(
                _run(typo),
                "active=false",
                msg=f"typo value {typo!r} must not activate the override",
            )


class RingGatingOverrideWiringTests(unittest.TestCase):
    """Layer 2 — the WIRED shape (round-2 Cure #3's demand, adapted)."""

    @classmethod
    def setUpClass(cls) -> None:
        with WORKFLOW.open(encoding="utf-8") as handle:
            cls.workflow = yaml.safe_load(handle)
        cls.changes_steps = cls.workflow["jobs"]["changes"]["steps"]

    def _step(self, step_id: str) -> dict:
        for step in self.changes_steps:
            if step.get("id") == step_id:
                return step
        self.fail(f"no step with id={step_id!r} found in changes job")

    def test_guilt_override_step_exists_before_gated_steps(self) -> None:
        ids = [s.get("id") for s in self.changes_steps if s.get("id")]
        self.assertIn("override", ids)
        override_index = ids.index("override")
        for gated_id in GATED_STEP_IDS:
            self.assertIn(gated_id, ids)
            self.assertLess(
                override_index,
                ids.index(gated_id),
                msg=f"{gated_id} step must run after the override step",
            )

    def test_guilt_every_classifier_step_is_gated_by_the_override(self) -> None:
        # This is the exact hazard round-2 named: an override script that is
        # correct in isolation but whose `if:` was never actually attached
        # to the steps it is supposed to bypass would leave this assertion
        # failing while every Layer-1 test above stays green.
        for step_id in GATED_STEP_IDS:
            step = self._step(step_id)
            self.assertEqual(
                step.get("if"),
                EXPECTED_GATE,
                msg=f"step id={step_id!r} is not gated by the override output",
            )

    def test_innocence_override_step_itself_is_ungated(self) -> None:
        # The override step must always run (it decides for everyone else) —
        # gating it on its own output would be a guard that can disable
        # itself, exactly the pattern cicatrix-superscar.md family #3 forbids.
        override_step = self._step("override")
        self.assertNotIn("if", override_step)

    def test_guilt_publish_step_distinguishes_override_from_failure(self) -> None:
        publish = next(
            s
            for s in self.changes_steps
            if s.get("name") == "Publish change-map decision"
        )
        run_text = publish["run"]
        self.assertIn("manual_override_disabled", run_text)
        self.assertIn("classifier_runtime_failure", run_text)
        self.assertIn("OVERRIDE_ACTIVE", publish.get("env", {}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
