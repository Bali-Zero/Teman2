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
