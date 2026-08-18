#!/usr/bin/env python3
"""Guilt + innocence corpus for `npm_audit_gate.py`.

Runs standalone (`python3 scripts/ci/test_npm_audit_gate.py`) and under pytest.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from npm_audit_gate import evaluate, main  # noqa: E402

GRAY_MATTER = "node_modules/gray-matter/node_modules/js-yaml"
WAIVE = {
    "GHSA-legacy-anypath": None,
    "GHSA-scoped": {GRAY_MATTER},
}


def vuln(severity="high", ids=("GHSA-scoped",), nodes=(GRAY_MATTER,)):
    return {
        "severity": severity,
        "via": [{"url": f"https://github.com/advisories/{i}"} for i in ids],
        "nodes": list(nodes),
    }


def run_cli(payload, raw=None):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        fh.write(raw if raw is not None else json.dumps(payload))
        path = fh.name
    return main(["npm_audit_gate.py", path])


# --- guilt ------------------------------------------------------------------

def test_a_non_waived_high_blocks():
    bad = evaluate({"vulnerabilities": {"lodash": vuln(ids=("GHSA-unknown",))}}, WAIVE)
    assert len(bad) == 1 and bad[0][3] == "not waived", bad


def test_a_waived_advisory_on_an_undeclared_path_still_blocks():
    """The whole point of path-scoping: same id, different arrival."""
    bad = evaluate(
        {"vulnerabilities": {"js-yaml": vuln(nodes=("node_modules/js-yaml",))}}, WAIVE
    )
    assert len(bad) == 1 and "unexpected paths" in bad[0][3], bad


def test_a_waived_advisory_blocks_on_the_extra_path_even_when_the_good_one_is_present():
    bad = evaluate(
        {"vulnerabilities": {"js-yaml": vuln(nodes=(GRAY_MATTER, "node_modules/js-yaml"))}},
        WAIVE,
    )
    assert len(bad) == 1 and "node_modules/js-yaml" in bad[0][3], bad


def test_a_shapeless_report_is_cannot_verify_not_clean():
    """`npm audit … || true` leaves a file behind when the audit itself dies."""
    assert run_cli({}) == 2
    assert run_cli({"error": "ENOTFOUND registry.npmjs.org"}) == 2


def test_an_unreadable_report_is_cannot_verify():
    assert run_cli(None, raw="not json at all") == 2


# --- innocence --------------------------------------------------------------

def test_the_waived_advisory_on_its_declared_path_passes():
    assert evaluate({"vulnerabilities": {"js-yaml": vuln()}}, WAIVE) == []


def test_a_legacy_any_path_waiver_passes_anywhere():
    bad = evaluate(
        {
            "vulnerabilities": {
                "find-my-way": vuln(ids=("GHSA-legacy-anypath",), nodes=("node_modules/somewhere/else",))
            }
        },
        WAIVE,
    )
    assert bad == [], bad


def test_moderate_severity_does_not_block():
    bad = evaluate(
        {"vulnerabilities": {"x": vuln(severity="moderate", ids=("GHSA-unknown",))}}, WAIVE
    )
    assert bad == [], bad


def test_a_genuinely_clean_report_passes():
    assert run_cli({"vulnerabilities": {}}) == 0


# --- scar pin: the live shape this gate was written for ---------------------

def test_the_real_gray_matter_finding_passes_with_the_shipped_waiver():
    """Uses the SHIPPED WAIVE, not the fixture — pins the actual production set."""
    payload = {
        "vulnerabilities": {
            "js-yaml": {
                "severity": "high",
                "via": [{"url": "https://github.com/advisories/GHSA-5p4m-2wfm-xmqj"}],
                "nodes": [GRAY_MATTER],
            }
        }
    }
    assert run_cli(payload) == 0


def test_the_same_advisory_on_a_production_path_we_never_vetted_blocks():
    payload = {
        "vulnerabilities": {
            "js-yaml": {
                "severity": "high",
                "via": [{"url": "https://github.com/advisories/GHSA-5p4m-2wfm-xmqj"}],
                "nodes": ["node_modules/some-future-prod-dep/node_modules/js-yaml"],
            }
        }
    }
    assert run_cli(payload) == 1


# --- carrier packages: block, but name the right cause ----------------------
#
# A package whose `via` holds only bare NAMES has no advisory of its own — it
# merely carries someone else's. It must still block; the bug being pinned here
# is the REASON it used to give.


def carrier(severity="high", via=("deepmerge-ts",), nodes=("node_modules/prisma",)):
    """The live 2026-08-17 shape: `via` is strings, so advisory_ids() is empty."""
    return {"severity": severity, "via": list(via), "nodes": list(nodes)}


def test_a_carrier_still_blocks():
    bad = evaluate({"vulnerabilities": {"prisma": carrier()}}, WAIVE)
    assert len(bad) == 1, bad


def test_a_carrier_does_not_claim_a_waiver_that_was_never_granted():
    """The scar: it read 'waived, but on unexpected paths' with WAIVE untouched."""
    bad = evaluate({"vulnerabilities": {"prisma": carrier()}}, WAIVE)
    assert "waiv" not in bad[0][3], bad
    assert "deepmerge-ts" in bad[0][3], bad


def test_a_carrier_blocks_even_when_its_node_is_a_waived_path():
    """Path-shape must not rescue it: with no ids, no waiver can apply."""
    bad = evaluate({"vulnerabilities": {"prisma": carrier(nodes=(GRAY_MATTER,))}}, WAIVE)
    assert len(bad) == 1 and "waiv" not in bad[0][3], bad


def test_a_carrier_with_no_recorded_nodes_now_blocks():
    """DELIBERATE behaviour change — pinned, not asserted away.

    The old code reached the waiver branch and computed `stray` over
    `nodes`; with no nodes there was nothing stray, so it appended NOTHING and a
    high-severity carrier passed the gate. Measured old-vs-new on 2026-08-18:
    False -> True for both `nodes: []` and absent `nodes`. Blocking is the right
    answer — "npm recorded no path" is not evidence of no path — but it IS a
    change, so it gets a test instead of a sentence.
    """
    assert len(evaluate({"vulnerabilities": {"prisma": carrier(nodes=())}}, WAIVE)) == 1
    no_nodes = {"severity": "high", "via": ["deepmerge-ts"]}
    assert len(evaluate({"vulnerabilities": {"prisma": no_nodes}}, WAIVE)) == 1


def test_a_carrier_below_the_threshold_is_still_ignored():
    """Innocence: the new branch sits AFTER the severity filter, not before it."""
    assert evaluate({"vulnerabilities": {"prisma": carrier(severity="moderate")}}, WAIVE) == []


def test_a_real_advisory_still_reads_not_waived():
    """Innocence: the new branch must not swallow the ordinary unwaived case."""
    bad = evaluate({"vulnerabilities": {"lodash": vuln(ids=("GHSA-unknown",))}}, WAIVE)
    assert bad[0][3] == "not waived", bad


def test_a_genuinely_stray_path_still_says_unexpected_paths():
    """Innocence: the message that IS correct for a real waiver survives."""
    bad = evaluate(
        {"vulnerabilities": {"js-yaml": vuln(nodes=("node_modules/js-yaml",))}}, WAIVE
    )
    assert "unexpected paths" in bad[0][3], bad


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  ok   {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"  FAIL {fn.__name__}: {exc}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
