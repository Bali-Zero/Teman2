"""Tests for scripts/ci/check_sweep_junit_liveness.py.

The one step in scripts-tests-sweep.yml (task #16) allowed to fail — see
that script's own docstring for why. Guilt+innocence per
cicatrix-superscar.md #3: innocence proves a real, healthy junit report
passes; guilt proves the infra-dead shapes (missing file, near-zero
collection, unparseable content) fail, without ever asserting on
individual test pass/fail counts (deliberately out of scope for this
script).

Run:  python3 -m pytest scripts/tests/test_check_sweep_junit_liveness.py -q
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = REPO_ROOT / "scripts" / "ci" / "check_sweep_junit_liveness.py"
_spec = importlib.util.spec_from_file_location("check_sweep_junit_liveness", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)  # type: ignore[union-attr]


def _write_junit(tmp_path: Path, tests: int, *, suites: int = 1) -> Path:
    suite_xml = "".join(
        f'<testsuite name="s{i}" tests="{tests // suites}" failures="0" errors="0" skipped="0"></testsuite>'
        for i in range(suites)
    )
    report = tmp_path / "report.xml"
    report.write_text(f'<?xml version="1.0" encoding="utf-8"?><testsuites>{suite_xml}</testsuites>')
    return report


def test_innocence_healthy_report_above_floor(tmp_path: Path) -> None:
    """Real-shaped report, well above the floor (baseline measured 2026-07-26:
    4729) -> passes regardless of the value being far from that baseline in
    either direction, as long as it clears the floor."""
    report = _write_junit(tmp_path, tests=4729)
    assert mod.main([str(report)]) == 0


def test_innocence_report_exactly_at_floor(tmp_path: Path) -> None:
    report = _write_junit(tmp_path, tests=mod.MIN_EXPECTED_TESTS)
    assert mod.main([str(report)]) == 0


def test_innocence_multiple_suites_summed(tmp_path: Path) -> None:
    """A junit report with several <testsuite> children (e.g. from a
    --junit-xml run that groups by module) must sum across all of them, not
    just the first."""
    report = _write_junit(tmp_path, tests=2000, suites=4)
    assert mod.main([str(report)]) == 0


def test_guilt_report_one_below_floor(tmp_path: Path) -> None:
    report = _write_junit(tmp_path, tests=mod.MIN_EXPECTED_TESTS - 1)
    assert mod.main([str(report)]) == 1


def test_guilt_zero_tests_collected(tmp_path: Path) -> None:
    report = _write_junit(tmp_path, tests=0)
    assert mod.main([str(report)]) == 1


def test_guilt_missing_report_file(tmp_path: Path) -> None:
    assert mod.main([str(tmp_path / "does-not-exist.xml")]) == 1


def test_guilt_unparseable_content(tmp_path: Path) -> None:
    report = tmp_path / "garbage.xml"
    report.write_text("not xml at all")
    assert mod.main([str(report)]) == 1


def test_guilt_no_argv() -> None:
    """No path given at all -> fail loud, never silently pass."""
    assert mod.main([]) == 1


def test_edge_bare_testsuite_root_not_wrapped_in_testsuites(tmp_path: Path) -> None:
    """pytest's --junit-xml normally emits <testsuites><testsuite>...</testsuite></testsuites>,
    but a bare <testsuite> root (some tooling emits this) must still parse."""
    report = tmp_path / "bare.xml"
    report.write_text(
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<testsuite name="pytest" tests="{mod.MIN_EXPECTED_TESTS + 1}" failures="0" errors="0" skipped="0"></testsuite>'
    )
    assert mod.main([str(report)]) == 0
