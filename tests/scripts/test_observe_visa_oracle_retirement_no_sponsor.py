"""Unit tests for scripts/ci/observe_visa_oracle_retirement_no_sponsor.py."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "ci"))

from observe_visa_oracle_retirement_no_sponsor import (  # noqa: E402
    pack_scan_offenders,
    summary_ok,
)


@pytest.mark.parametrize(
    "line",
    [
        "      Tests  3 skipped (3)",
        "      Tests  2 passed (2)",
        "      Tests  4 passed (4)",
        "      Tests  1 failed | 2 passed (3)",
        "      Tests  3 passed | 1 skipped (4)",
        "      Tests  3 passed | 1 todo (4)",
        "      Tests  2 passed (3)",
        "",
        None,
    ],
)
def test_rejects_anything_but_exactly_the_guard_tests(line):
    assert summary_ok(line) is False


def test_accepts_exactly_the_guard_tests_passing():
    assert summary_ok("      Tests  3 passed (3)") is True


def _write(tmp_path, n, payload, name=None):
    path = tmp_path / (name or f"rulepack-prod-{n:03d}.signed.json")
    path.write_text(json.dumps({"payload": payload}), encoding="utf-8")


def _payload(seq, rule_versions, *, retirement=("E33E", "E33F")):
    products = [
        {
            "product_code": code,
            "product_version_id": f"v-{code}",
            "covered_purposes": ["RETIREMENT"] if code in retirement else ["TOURISM"],
        }
        for code in ("E33E", "E33F", "E1")
    ]
    return {
        "sequence": seq,
        "products": products,
        "rules": [
            {
                "rule_id": "r1",
                "scope": "PRODUCTS",
                "product_version_ids": rule_versions,
                "required_facts": ["sponsor.type"],
            }
        ],
    }


def test_real_newest_pack_is_clean():
    assert pack_scan_offenders() == []


def test_a_retirement_rule_reading_sponsor_type_is_named(tmp_path):
    _write(tmp_path, 5, _payload(5, ["v-E33F"]))
    assert pack_scan_offenders(tmp_path) == ["r1"]


def test_a_non_retirement_sponsor_rule_is_clean(tmp_path):
    _write(tmp_path, 5, _payload(5, ["v-E1"]))
    assert pack_scan_offenders(tmp_path) == []


def test_sequence_mismatch_in_newest_pack_is_untrustworthy(tmp_path):
    _write(tmp_path, 5, _payload(5, ["v-E1"]))
    _write(tmp_path, 6, {"products": [], "rules": []})
    assert pack_scan_offenders(tmp_path) is None


def test_missing_retirement_product_is_untrustworthy(tmp_path):
    _write(tmp_path, 5, _payload(5, ["v-E1"], retirement=("E33E",)))
    assert pack_scan_offenders(tmp_path) is None


def test_no_pack_is_untrustworthy(tmp_path):
    assert pack_scan_offenders(tmp_path) is None
