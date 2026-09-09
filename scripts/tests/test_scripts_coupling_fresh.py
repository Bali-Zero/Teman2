#!/usr/bin/env python3
"""Nightly-swept tripwire for SCRIPTS_COUPLING staleness (2026-09-05).

NOT a per-PR gate. scripts/tests/ is collected only by
`.github/workflows/scripts-tests-sweep.yml`'s report-only nightly cron
(`continue-on-error: true` on the whole job, per that workflow's own header
comment) — never by a pull_request-triggered job. Say it plainly rather than
implying a blocking guarantee this file cannot provide.

WHY THIS EXISTS, SEPARATE FROM scripts/ci/test_change_map.py's OWN
test_scripts_coupling_census_is_not_stale: that test now WARNS (does not
fail) when it detects it is running inside tests.yml's flat trusted-
classifier extraction, because a stale census there is a FLEET-WIDE data-
freshness fact (some OTHER merged PR touched scripts/**) unrelated to
whatever diff a given PR is actually judging — treating it as THIS PR's own
failure forced every PR's classifier to fall back to run_all=true the moment
main's census drifted (diagnosed 2026-09-05, the 18:46Z outage). Removing
that blocking effect from the per-PR trust check means staleness still needs
SOMEWHERE to be caught — this file is that place, on the nightly cadence,
honestly scoped as advisory rather than pretending to be a per-PR gate it
structurally cannot be without a workflow change (the per-PR annotation of
staleness in the Change map job itself is a deferred Gear-3 follow-up, not
shipped here).
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CENSUS = REPO / "scripts" / "ci" / "scripts_coupling_census.py"


class ScriptsCouplingFreshnessTests(unittest.TestCase):
    def test_scripts_coupling_is_fresh(self) -> None:
        self.assertTrue(
            CENSUS.is_file(),
            f"{CENSUS} does not exist — this checkout is not a real repo root "
            "(REPO derived from __file__.parents[2], never cwd/GITHUB_WORKSPACE: "
            "this file is only ever collected in place by the nightly sweep, "
            "never flat-extracted, so that ambiguity does not apply here).",
        )
        completed = subprocess.run(
            [sys.executable, str(CENSUS), "--check"],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            completed.returncode,
            0,
            "SCRIPTS_COUPLING is stale — run "
            "`python3 scripts/ci/scripts_coupling_census.py --write`.\n"
            f"stdout: {completed.stdout}\nstderr: {completed.stderr}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
