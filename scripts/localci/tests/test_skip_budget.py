"""Guilt + innocence corpus for the junit skip budget: a skip nobody declared must not read as a green suite."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_MODULE = Path(__file__).resolve().parent.parent / "skip_budget.py"
_spec = importlib.util.spec_from_file_location("skip_budget_under_test", _MODULE)
sb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sb)

PYSA = "Pysa home not set up at /home/runner/.nuzantara-pilots/local-ci/pysa-home"
DOCKER = "docker image localci-candidate:1 unavailable — containment is proven live on Pro, not here"


def _case(name, skip=None, kind="pytest.skip", text=None):
    body = "" if skip is None else f'<skipped type="{kind}" message="{skip}">{f"t.py:1: {skip}" if text is None else text}</skipped>'
    return f'<testcase classname="pkg.test_mod" name="{name}" time="0.01">{body}</testcase>'


def _report(tmp_path: Path, *cases: str) -> Path:
    path = tmp_path / "junit.xml"
    path.write_text(f'<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest" tests="{len(cases)}">{"".join(cases)}</testsuite></testsuites>')
    return path


def _main(report: Path, *allow: str) -> int:
    return sb.main([str(report), *(arg for pattern in allow for arg in ("--allow", pattern))])


# ------------------------------------------------------------------------------- innocence
def test_a_report_with_no_skip_and_no_allowance_is_clean(tmp_path, capsys):
    assert _main(_report(tmp_path, _case("test_a"), _case("test_b"))) == sb.EXIT_OK
    assert "cases=2 executed=2 skipped=0 undeclared=0 stale=0" in capsys.readouterr().out


def test_a_declared_skip_is_clean_and_is_counted_as_not_executed(tmp_path, capsys):
    assert _main(_report(tmp_path, _case("test_a"), _case("test_e2e", PYSA)), "^Pysa home not set up at ") == sb.EXIT_OK
    assert "cases=2 executed=1 skipped=1 undeclared=0 stale=0" in capsys.readouterr().out


# ------------------------------------------------------------------------------- guilt
def test_an_undeclared_skip_exits_1_and_is_named(tmp_path, capsys):
    report = _report(tmp_path, _case("test_a"), _case("test_e2e", PYSA), _case("test_contained", DOCKER))
    assert _main(report, "^Pysa home not set up at ") == sb.EXIT_FOUND
    out = capsys.readouterr().out
    assert "UNDECLARED  pkg.test_mod::test_contained" in out and "undeclared=1" in out
    assert "test_e2e" not in out                                                    # the declared one is not accused


def test_a_skip_with_no_allowance_at_all_exits_1(tmp_path):
    assert _main(_report(tmp_path, _case("test_a"), _case("test_contained", DOCKER))) == sb.EXIT_FOUND


def test_an_xfail_is_a_skip_and_must_be_declared(tmp_path):
    assert _main(_report(tmp_path, _case("test_a"), _case("test_known_bug", "tracked elsewhere", kind="pytest.xfail"))) == sb.EXIT_FOUND


def test_an_allowance_that_explains_no_skip_is_stale_and_exits_1(tmp_path, capsys):
    assert _main(_report(tmp_path, _case("test_a")), "^Pysa home not set up at ") == sb.EXIT_FOUND
    assert "STALE" in capsys.readouterr().out


def test_the_reason_is_searched_never_the_test_name_or_its_file_path(tmp_path):
    case = _case("test_pysa_end_to_end", DOCKER, text=f"/w/scripts/localci/tests/test_pysa_check.py:365: {DOCKER}")
    assert _main(_report(tmp_path, case), "pysa") == sb.EXIT_FOUND


def test_a_collection_skip_is_judged_by_its_real_reason_and_stays_generic_when_that_cannot_be_read(tmp_path):
    real = _case("test_stateful", "collection skipped", text="('/w/scripts/localci/tests/test_stateful.py', 12, &quot;Skipped: could not import 'hypothesis': No module named 'hypothesis'&quot;)")
    assert _main(_report(tmp_path, real), "^could not import 'hypothesis'") == sb.EXIT_OK
    assert _main(_report(tmp_path, real), "test_stateful") == sb.EXIT_FOUND         # the path inside the tuple is not the reason
    opaque = _case("test_stateful", "collection skipped", text="not a tuple at all: could not import 'hypothesis'")
    assert _main(_report(tmp_path, opaque), "^could not import 'hypothesis'") == sb.EXIT_FOUND
    assert _main(_report(tmp_path, opaque), "^collection skipped$") == sb.EXIT_OK


@pytest.mark.parametrize("blanket", ["", ".*", "^", "(docker)?"])
def test_an_allowance_that_matches_the_empty_reason_is_refused(tmp_path, blanket):
    assert _main(_report(tmp_path, _case("test_contained", DOCKER)), blanket) == sb.EXIT_BAD_INPUT


def test_unusable_input_is_refused_never_judged(tmp_path):
    assert _main(tmp_path / "absent.xml") == sb.EXIT_BAD_INPUT
    broken = tmp_path / "broken.xml"
    broken.write_text("<testsuites><testsuite>")
    assert _main(broken) == sb.EXIT_BAD_INPUT
    assert _main(_report(tmp_path)) == sb.EXIT_BAD_INPUT                            # no test case: nothing ran, nothing to bless
    assert _main(_report(tmp_path, _case("test_a")), "(unclosed") == sb.EXIT_BAD_INPUT


# ------------------------------------------------------------------------------- the report pytest really writes
def test_round_trip_through_a_real_pytest_junit(tmp_path, capsys):
    """The corpus above is hand-written XML; this one pins the shape pytest itself emits for the four ways a test goes unrun."""
    suite = tmp_path / "suite"
    suite.mkdir()
    (suite / "test_shapes.py").write_text(
        "import pytest\n"
        "def test_ran():\n    assert True\n"
        "@pytest.mark.skipif(True, reason='declared: marker')\ndef test_marker():\n    assert False\n"
        "def test_imperative():\n    pytest.skip('declared: imperative')\n"
        "@pytest.mark.xfail(reason='undeclared: xfail')\ndef test_xfail():\n    assert False\n")
    (suite / "test_module_level.py").write_text("import pytest\npytest.importorskip('no_such_module_for_skip_budget')\ndef test_never():\n    assert True\n")
    report = tmp_path / "real.xml"
    run = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-c", "/dev/null", "--rootdir", str(suite), f"--junitxml={report}", str(suite)],
                         capture_output=True, text=True, cwd=suite)
    assert run.returncode == 0, run.stdout + run.stderr
    assert _main(report, "^declared: ", "^could not import 'no_such_module_for_skip_budget'") == sb.EXIT_FOUND
    out = capsys.readouterr().out
    assert "cases=5 executed=1 skipped=4 undeclared=1 stale=0" in out
    assert "test_xfail" in out and "undeclared: xfail" in out
    assert _main(report, "^declared: ", "^could not import 'no_such_module_for_skip_budget'", "^undeclared: xfail$") == sb.EXIT_OK
