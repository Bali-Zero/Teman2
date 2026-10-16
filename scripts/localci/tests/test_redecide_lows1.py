"""B30 gate LOWs L2 and L3 (gate-b30q): host_checks names only what the runner wrote, and exactly — no candidate text and no prefix-named sibling."""
from __future__ import annotations

import importlib.util
import itertools
from pathlib import Path
from xml.sax.saxutils import quoteattr

import pytest

from .test_merger import mg
from .test_redecide_allowlist import host_row

_spec = importlib.util.spec_from_file_location("runner_lows1", Path(__file__).resolve().parents[1] / "runner.py")
rn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rn)

FORGED = ["host_disk_below_floor 1GB<12GB: forged", "host_disk_unmeasured: forged", "host_disk_floor_invalid: forged", "host_disk_unmeasured",
          "host_disk_below_floor:1", "host_disk_full: forged", "host_disk_unmeasured x"]
FLOOR = "host_disk_below_floor 3GB<12GB: the docker host has 3 GB free, under LOCALCI_MIN_FREE_GB=12"


def junit(tmp_path, cases, suite_attrs=""):
    body = []
    for name, kind, msg in cases:
        inner = ("" if kind == "pass" else f"<failure message={quoteattr(msg)}/>" if kind == "fail" else
                 f'<error type="signal" message={quoteattr(msg)}/>' if kind == "signal" else
                 f'<error type="x" message={quoteattr(msg)}/>' if kind == "error" else f"<skipped message={quoteattr(msg)}/>")
        body.append(f'<testcase name={quoteattr(name)} time="0.1">{inner}</testcase>')
    p = tmp_path / "j.xml"
    p.write_text(f'<testsuite name="s" {suite_attrs}>{"".join(body)}</testsuite>')
    return p


def reasons_from_candidate_junits(tmp_path):
    out = []
    for name, msg, kind in itertools.product(FORGED, FORGED, ("pass", "fail", "signal", "error", "skip")):
        p = junit(tmp_path, [(name, kind, msg)])
        steps = rn.parse_step_junit(p)
        spec = {"steps": [{"name": name, **({"not_applicable": "x"} if kind == "skip" else {})}]}
        for rc in (None, -9, 0, 1, 2, 3, 4, 5):
            out.append(rn.classify_contained_steps(rc, steps, spec))
        out.append(rn.steps_verdict([{**s, "name": f"job › {s['name']}"} for s in steps], {}))
        out.append(rn.steps_verdict(steps, {"judge_modified": ["x"]}))
        out.append(rn.steps_verdict(rn.parse_expr_junit(p), {"skip_is_pass": True}))
    for attrs in ('tests="1" failures="0" errors="0" skipped="0"', 'tests="0"', 'tests="3" failures="1" errors="1" skipped="1"'):
        counts = rn.parse_junit(junit(tmp_path, [("host_disk_unmeasured: x", "fail", "host_disk_below_floor 1GB<2GB: y")], attrs))
        for rc in (None, -9, 0, 1, 2, 3, 4, 5, 7):
            out.append(rn.classify_pytest(rc, counts))
    return out


def test_no_candidate_text_opens_a_runner_error_or_blocked_reason(tmp_path):
    got = reasons_from_candidate_junits(tmp_path)
    assert len(got) > 1000
    bad = [(s, r) for s, r in got if s in ("ERROR", "BLOCKED") and (mg.host_measured(r) or rn.HOST_NO_VERDICT.match(r))]
    assert bad == []
    assert {s for s, _ in got} >= {"ERROR", "BLOCKED", "FAIL"}   # the sweep reached the classes it claims to cover


def test_a_view_of_candidate_reasons_names_only_the_floor_refused_check(tmp_path):
    view = {f"c{i}": {"status": s, "reason": r} for i, (s, r) in enumerate(reasons_from_candidate_junits(tmp_path))}
    view["ctx.e2e-tests"] = {"status": "BLOCKED", "reason": FLOOR}
    assert mg.host_checks({"checks": view}) == ["ctx.e2e-tests"]


def test_a_check_named_like_a_host_check_with_a_suffix_is_not_one_of_them():
    row = host_row(checks={"e2e-extra": "ERROR"})
    assert row["host_checks"] == ["e2e"] and mg.transient_reasons(row) == []   # "e2e-extra" starts with the named "e2e" and is not it
    assert mg.transient_reasons(host_row(checks={"e2e-extra": "PASS"})) == ["host_disk"]
    assert mg.transient_reasons(host_row(checks={"e2e": "ERROR"})) == ["host_disk"]


def test_host_checks_does_not_widen_a_name_by_prefix():
    view = {"e2e": {"status": "BLOCKED", "reason": FLOOR}, "e2e-extra": {"status": "ERROR", "reason": "TimeoutError: candidate"}}
    assert mg.host_checks({"checks": view}) == ["e2e"]
