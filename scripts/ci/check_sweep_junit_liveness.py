#!/usr/bin/env python3
"""check_sweep_junit_liveness.py — the ONE step in scripts-tests-sweep.yml
that is allowed to fail (task #16, hardened 2026-07-26 after pr3165-cure's
review: a job where EVERY step tolerates its own failure can never report
anything but success to GitHub, which means the reactive workflow_run
watcher — once this workflow's name is registered in
main-push-failure-watch.yml's `workflows:` list — would have nothing to
ever catch. Cicatrix-superscar #2 (exists != armed) applied to this
report-only tool itself).

DELIBERATELY NARROW: this does NOT fail on individual test failures among
the 174 previously-orphaned scripts/tests/ files (11 failed / 4 errors
measured in the first real local run, 2026-07-26 — EXPECTED and tracked
for Stage-2 triage, not yet actionable). Alerting every night on a known,
not-yet-fixed condition would be exactly the "un allarme IDENTICO
ripetuto = affaticamento" fatigue pattern this same session already
diagnosed elsewhere tonight. It fails ONLY if the run itself did not
meaningfully happen: no junit report produced/parseable, or a
suspiciously low collected-test count — the signal for "the sweep step
crashed before collecting", "dependency install failed silently", or
"the run was truncated", none of which are the same fact as "some tests
failed".

Baseline measured 2026-07-26 (first-ever full local run, unloaded):
4729 test items collected across the 235 files in scripts/tests/. The
floor here (1000) is chosen only to catch a catastrophic near-zero
collection, with wide headroom for legitimate future growth/shrink in
the suite — it is not a target to defend.

Exit 0 = the sweep ran and collected a plausible number of tests
(regardless of how many passed). Exit 1 = infra-level dead run.

Run:
    python3 scripts/ci/check_sweep_junit_liveness.py scripts-tests-report.xml
"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET  # noqa: S314 — see note below
from pathlib import Path

# security-guidance note: this parses scripts-tests-report.xml, which is
# generated moments earlier BY THIS SAME JOB via `pytest --junit-xml=`, on
# the same runner — it is our own trusted tool's output, not attacker-
# controlled/external input, so this is outside the XXE/billion-laughs
# threat model that guidance targets. Left on stdlib `ElementTree` rather
# than adding `defusedxml` as a new dependency (not currently in
# requirements.lock.txt) for one small CI-internal check — that would be
# the opposite of the "smallest set" instruction this file exists under
# (task #16). `ElementTree`'s expat backend also does not resolve
# external entities by default in modern CPython, unlike `xml.dom.minidom`
# or a permissively-configured `lxml`, which is where XXE historically
# bit Python code.

MIN_EXPECTED_TESTS = 1000  # baseline 2026-07-26: 4729 collected, wide headroom


def main(argv: list[str]) -> int:
    if not argv:
        print("::error::check_sweep_junit_liveness: no junit report path given", file=sys.stderr)
        return 1

    report_path = Path(argv[0])
    if not report_path.is_file():
        print(
            f"::error::sweep infra liveness FAILED — no junit report at {report_path} "
            "(the sweep step likely crashed before it could write one)",
            file=sys.stderr,
        )
        return 1

    try:
        tree = ET.parse(report_path)
    except ET.ParseError as exc:
        print(f"::error::sweep infra liveness FAILED — junit report unparseable: {exc}", file=sys.stderr)
        return 1

    root = tree.getroot()
    suites = [root] if root.tag == "testsuite" else root.findall(".//testsuite")
    total = sum(int(s.get("tests", 0)) for s in suites)

    print(f"sweep infra liveness: {total} test item(s) collected across {len(suites)} suite(s)")
    if total < MIN_EXPECTED_TESTS:
        print(
            f"::error::sweep infra liveness FAILED — only {total} test items collected, "
            f"expected >= {MIN_EXPECTED_TESTS} (baseline 4729, 2026-07-26). This is an "
            "infra-level signal (crash before collection / silent dependency-install "
            "failure / truncated run) — deliberately NOT the same check as individual "
            "test failures among the 235 files, which this script ignores by design.",
            file=sys.stderr,
        )
        return 1

    print("sweep infra liveness: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
