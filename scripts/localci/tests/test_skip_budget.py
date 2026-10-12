"""Guilt + innocence corpus for the junit skip budget: undeclared skips, missing required tests and a missed floor must not read as green."""
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


def _raw(tmp_path: Path, xml: str) -> Path:
    path = tmp_path / "raw.xml"
    path.write_text(xml)
    return path


def _main(report: Path, *args: str) -> int:
    return sb.main([str(report), *args])


ALLOW_PYSA = ("--allow", r"test_mod::test_e2e$", "^Pysa home not set up at ")


# ------------------------------------------------------------------------------- innocence
def test_a_report_with_no_skip_and_no_allowance_is_clean(tmp_path, capsys):
    assert _main(_report(tmp_path, _case("test_a"), _case("test_b"))) == sb.EXIT_OK
    assert "cases=2 executed=2 skipped=0 undeclared=0 stale=0 overused=0 missing=0 ambiguous=0" in capsys.readouterr().out


def test_a_declared_skip_bound_to_its_test_id_is_clean_and_counted_as_not_executed(tmp_path, capsys):
    assert _main(_report(tmp_path, _case("test_a"), _case("test_e2e", PYSA)), *ALLOW_PYSA) == sb.EXIT_OK
    assert "cases=2 executed=1 skipped=1 undeclared=0 stale=0 overused=0 missing=0 ambiguous=0" in capsys.readouterr().out


def test_a_require_that_matches_an_executed_test_is_clean(tmp_path):
    assert _main(_report(tmp_path, _case("test_a"), _case("test_b")), "--require", "test_mod::test_b$", "--min-executed", "2") == sb.EXIT_OK


# ------------------------------------------------------------------------------- guilt: skips
def test_an_undeclared_skip_exits_1_and_is_named(tmp_path, capsys):
    report = _report(tmp_path, _case("test_a"), _case("test_e2e", PYSA), _case("test_contained", DOCKER))
    assert _main(report, *ALLOW_PYSA) == sb.EXIT_FOUND
    out = capsys.readouterr().out
    assert "UNDECLARED  pkg.test_mod::test_contained" in out and "undeclared=1" in out
    assert "test_e2e" not in out                                                    # the declared one is not accused


def test_a_skip_with_no_allowance_at_all_exits_1(tmp_path):
    assert _main(_report(tmp_path, _case("test_a"), _case("test_contained", DOCKER))) == sb.EXIT_FOUND


def test_the_same_reason_on_a_different_test_id_is_undeclared(tmp_path, capsys):
    assert _main(_report(tmp_path, _case("test_a"), _case("test_other", PYSA)), *ALLOW_PYSA) == sb.EXIT_FOUND
    out = capsys.readouterr().out
    assert "UNDECLARED  pkg.test_mod::test_other" in out and "STALE" in out         # and the allowance of the absent test is stale


def test_two_skips_explained_by_one_allowance_are_overused(tmp_path, capsys):
    report = _report(tmp_path, _case("test_a"), _case("test_e2e", PYSA), _case("test_e2e_again", PYSA))
    assert _main(report, "--allow", "test_mod::test_e2e", "^Pysa home") == sb.EXIT_FOUND
    out = capsys.readouterr().out
    assert "OVERUSED" in out and "test_e2e_again" in out and "overused=1" in out


def test_a_whole_module_skipped_with_one_reason_is_not_covered_by_one_allowance(tmp_path):
    report = _report(tmp_path, _case("test_a"), *(_case(f"test_{i}", PYSA) for i in range(3)))
    assert _main(report, "--allow", "test_mod::", "^Pysa home") == sb.EXIT_FOUND


def test_a_skip_explained_by_two_allowances_is_ambiguous(tmp_path, capsys):
    report = _report(tmp_path, _case("test_a"), _case("test_e2e", PYSA))
    assert _main(report, *ALLOW_PYSA, "--allow", "test_e2e$", "^Pysa home") == sb.EXIT_FOUND
    out = capsys.readouterr().out
    assert "AMBIGUOUS   pkg.test_mod::test_e2e is explained by 2 allowances, not one" in out and "ambiguous=1" in out


def test_two_allowances_over_two_distinct_skips_each_matched_by_one_are_clean(tmp_path, capsys):
    report = _report(tmp_path, _case("test_a"), _case("test_e2e", PYSA), _case("test_contained", DOCKER))
    assert _main(report, *ALLOW_PYSA, "--allow", "test_contained$", "^docker image") == sb.EXIT_OK
    assert "ambiguous=0" in capsys.readouterr().out


def test_an_allowance_that_explains_no_skip_is_stale_and_exits_1(tmp_path, capsys):
    assert _main(_report(tmp_path, _case("test_a")), *ALLOW_PYSA) == sb.EXIT_FOUND
    assert "STALE" in capsys.readouterr().out


def test_deleting_the_allowed_test_does_not_keep_the_allowance_alive_for_a_reused_reason(tmp_path):
    assert _main(_report(tmp_path, _case("test_a"), _case("test_renamed", PYSA)), *ALLOW_PYSA) == sb.EXIT_FOUND


def test_an_xfail_is_a_skip_and_must_be_declared(tmp_path):
    report = _report(tmp_path, _case("test_a"), _case("test_known_bug", "tracked elsewhere", kind="pytest.xfail"))
    assert _main(report) == sb.EXIT_FOUND
    assert _main(report, "--allow", "test_known_bug$", "^tracked elsewhere$") == sb.EXIT_OK


def test_the_reason_is_searched_never_the_test_name_or_its_file_path(tmp_path):
    case = _case("test_pysa_end_to_end", DOCKER, text=f"/w/scripts/localci/tests/test_pysa_check.py:365: {DOCKER}")
    assert _main(_report(tmp_path, case, _case("test_a")), "--allow", "test_pysa_end_to_end$", "pysa") == sb.EXIT_FOUND


def test_a_collection_skip_is_judged_by_its_real_reason_and_stays_generic_when_that_cannot_be_read(tmp_path):
    real = _case("test_stateful", "collection skipped", text="('/w/scripts/localci/tests/test_stateful.py', 12, &quot;Skipped: could not import 'hypothesis': No module named 'hypothesis'&quot;)")
    ok = _case("test_a")
    assert _main(_report(tmp_path, real, ok), "--allow", "test_stateful$", "^could not import 'hypothesis'") == sb.EXIT_OK
    assert _main(_report(tmp_path, real, ok), "--allow", "test_stateful$", "test_stateful.py") == sb.EXIT_FOUND   # the path inside the tuple is not the reason
    opaque = _case("test_stateful", "collection skipped", text="not a tuple at all: could not import 'hypothesis'")
    assert _main(_report(tmp_path, opaque, ok), "--allow", "test_stateful$", "^could not import 'hypothesis'") == sb.EXIT_FOUND
    assert _main(_report(tmp_path, opaque, ok), "--allow", "test_stateful$", "^collection skipped$") == sb.EXIT_OK


# ------------------------------------------------------------------------------- guilt: what did not run
def test_a_require_whose_only_match_was_skipped_is_missing(tmp_path, capsys):
    assert _main(_report(tmp_path, _case("test_a"), _case("test_e2e", PYSA)), *ALLOW_PYSA, "--require", "test_e2e") == sb.EXIT_FOUND
    assert "MISSING     --require 'test_e2e'" in capsys.readouterr().out


def test_a_require_with_no_matching_case_is_missing_the_deselection_case(tmp_path, capsys):
    assert _main(_report(tmp_path, _case("test_ran")), "--require", "test_deselected") == sb.EXIT_FOUND
    assert "missing=1" in capsys.readouterr().out


def test_with_the_default_floor_one_allowed_skip_and_nothing_executed_is_not_clean(tmp_path, capsys):
    assert _main(_report(tmp_path, _case("test_e2e", PYSA)), *ALLOW_PYSA) == sb.EXIT_FOUND
    assert "TOO FEW     executed=0 < min-executed=1" in capsys.readouterr().out


def test_an_explicit_floor_above_the_executed_count_is_not_clean(tmp_path):
    report = _report(tmp_path, _case("test_a"), _case("test_b"))
    assert _main(report, "--min-executed", "2") == sb.EXIT_OK
    assert _main(report, "--min-executed", "3") == sb.EXIT_FOUND


# ------------------------------------------------------------------------------- refusals
@pytest.mark.parametrize("blanket", ["", ".*", "^", "(docker)?", "(?=.)", ".", ".+"])
@pytest.mark.parametrize("position", ["allow-test", "allow-reason", "require"])
def test_a_blanket_pattern_is_refused_in_every_position(tmp_path, blanket, position):
    args = {"allow-test": ("--allow", blanket, "^docker"), "allow-reason": ("--allow", "test_contained$", blanket), "require": ("--require", blanket)}[position]
    assert _main(_report(tmp_path, _case("test_contained", DOCKER), _case("test_a")), *args) == sb.EXIT_BAD_INPUT


def test_a_pattern_that_does_not_compile_is_refused(tmp_path):
    report = _report(tmp_path, _case("test_a"))
    assert _main(report, "--allow", "(unclosed", "x") == sb.EXIT_BAD_INPUT
    assert _main(report, "--require", "(unclosed") == sb.EXIT_BAD_INPUT


def test_a_skipped_element_outside_a_test_case_is_refused(tmp_path, capsys):
    xml = ('<testsuites><testsuite name="pytest" tests="1"><testcase classname="p.t" name="test_a"/>'
           '<skipped type="pytest.skip" message="stray"/></testsuite></testsuites>')
    assert _main(_raw(tmp_path, xml)) == sb.EXIT_BAD_INPUT
    assert "outside a test case" in capsys.readouterr().err


def test_a_report_whose_testsuites_do_not_add_up_to_its_test_cases_is_refused(tmp_path):
    xml = '<testsuites><testsuite name="pytest" tests="5"><testcase classname="p.t" name="test_a"/></testsuite></testsuites>'
    assert _main(_raw(tmp_path, xml)) == sb.EXIT_BAD_INPUT


def test_unusable_input_is_refused_never_judged(tmp_path):
    assert _main(tmp_path / "absent.xml") == sb.EXIT_BAD_INPUT
    broken = tmp_path / "broken.xml"
    broken.write_text("<testsuites><testsuite>")
    assert _main(broken) == sb.EXIT_BAD_INPUT
    assert _main(_report(tmp_path)) == sb.EXIT_BAD_INPUT                            # no test case: nothing ran, nothing to bless


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

    def run_pytest(report: Path, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-c", "/dev/null", "--rootdir", str(suite), f"--junitxml={report}", *extra, str(suite)],
                              capture_output=True, text=True, cwd=suite)

    report = tmp_path / "real.xml"
    run = run_pytest(report)
    assert run.returncode == 0, run.stdout + run.stderr
    allowed = ("--allow", "test_shapes::test_marker$", "^declared: marker", "--allow", "test_shapes::test_imperative$", "^declared: imperative",
               "--allow", "test_module_level", "^could not import 'no_such_module_for_skip_budget'")
    assert _main(report, *allowed) == sb.EXIT_FOUND
    out = capsys.readouterr().out
    assert "cases=5 executed=1 skipped=4 undeclared=1 stale=0 overused=0 missing=0 ambiguous=0" in out
    assert "test_xfail" in out and "undeclared: xfail" in out
    assert _main(report, *allowed, "--allow", "test_shapes::test_xfail$", "^undeclared: xfail$", "--require", "test_shapes::test_ran$") == sb.EXIT_OK
    deselected = tmp_path / "deselected.xml"
    run = run_pytest(deselected, "-k", "test_ran")                                  # pytest is green; deselected tests are absent from junit
    assert run.returncode == 0, run.stdout + run.stderr
    assert _main(deselected, "--require", "test_shapes::test_marker$") == sb.EXIT_FOUND
    selected = ("--allow", "test_module_level", "^could not import ", "--require", "test_shapes::test_ran$")
    assert _main(deselected, *selected, "--min-executed", "2") == sb.EXIT_FOUND
    assert "TOO FEW     executed=1 < min-executed=2" in capsys.readouterr().out
    assert _main(deselected, *selected, "--min-executed", "1") == sb.EXIT_OK        # omitted non-required tests are invisible once the floor holds
