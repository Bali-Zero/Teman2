"""A CVE exception suppresses the CVE it names IN THE PACKAGE it names, and nowhere else.

THE DEFECT. `package` is a REQUIRED field of the exception schema — check_cve_exceptions.py
refuses an entry without it — and neither scanner filter ever read it back. Both keyed the
accepted set on the CVE id alone. Measured 2026-09-05 with an exception scoped to `foo` and
a HIGH finding for the same CVE in `bar`:

    Accepted (in .security/exceptions.yaml):
      - CVE-2024-9999 in bar (severity=high)
    ✅ No blocking CVEs.                                    exit 0

Both scanners, and the filter PRINTED the package it did not check. A CVE triaged as
acceptable in one dependency was acceptable in every other dependency carrying it,
including ones where the vulnerable path is reachable and the triage reasoning does not
apply. A required field that no consumer reads is not a control; it is a field.

Both directions are pinned (superscar #3): the over-match here would be spelling —
`ruamel.yaml` vs `ruamel-yaml` are the same distribution, and comparing raw strings would
BLOCK a legitimate exception and get a wildcard escape hatch reinvented.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

_spec = importlib.util.spec_from_file_location(
    "nuzantara_cve_exceptions", REPO_ROOT / "scripts" / "lib" / "cve_exceptions.py"
)
assert _spec is not None and _spec.loader is not None
cve = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cve)

EXCEPTION = """exceptions:
  - cve_id: "CVE-2024-9999"
    package: "{package}"
    version: "1.0.0"
    reason: "fixture"
    approved_by: "test"
    approved_at: "2026-09-01"
    expires_at: "2026-11-01"
"""


def _exceptions(tmp_path: Path, package: str = "foo") -> Path:
    target = tmp_path / "exceptions.yaml"
    target.write_text(EXCEPTION.format(package=package), encoding="utf-8")
    return target


def _snyk(tmp_path: Path, package: str) -> Path:
    target = tmp_path / "snyk.json"
    target.write_text(json.dumps({"vulnerabilities": [{
        "id": "SNYK-1", "identifiers": {"CVE": ["CVE-2024-9999"]},
        "packageName": package, "version": "1.0.0", "severity": "high", "title": "fixture",
    }]}), encoding="utf-8")
    return target


def _safety(tmp_path: Path, package: str) -> Path:
    target = tmp_path / "safety.json"
    target.write_text(json.dumps({"vulnerabilities": [{
        "vulnerability_id": "S1", "CVE": "CVE-2024-9999",
        "package_name": package, "severity": "high",
    }]}), encoding="utf-8")
    return target


def _run(script: str, report: Path, exceptions: Path) -> subprocess.CompletedProcess:
    """The real script as CI runs it — a subprocess, not an imported function."""
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / script), str(report)],
        capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "CVE_EXCEPTIONS_PATH": str(exceptions)},
    )


# ------------------------------------------------------------------------- guilt

@pytest.mark.parametrize(
    "script,builder", [("filter_snyk_findings.py", _snyk), ("filter_safety_findings.py", _safety)]
)
def test_guilt_an_exception_for_one_package_does_not_excuse_another(tmp_path, script, builder):
    """The measured defect, on both scanners."""
    result = _run(script, builder(tmp_path, "bar"), _exceptions(tmp_path, "foo"))
    assert result.returncode == 1, result.stdout
    assert "bar" in result.stdout
    assert "Blocking" in result.stdout


@pytest.mark.parametrize(
    "script,builder", [("filter_snyk_findings.py", _snyk), ("filter_safety_findings.py", _safety)]
)
def test_guilt_a_finding_with_no_package_name_cannot_inherit_a_triage(tmp_path, script, builder):
    """An unidentifiable dependency is the last thing that should inherit someone else's triage."""
    result = _run(script, builder(tmp_path, ""), _exceptions(tmp_path, "foo"))
    assert result.returncode == 1, result.stdout


def test_guilt_an_exception_with_no_package_is_unusable_not_universal(tmp_path):
    """Skipping a malformed entry must mean "cannot scope", never "scopes to everything"."""
    target = tmp_path / "exceptions.yaml"
    target.write_text('exceptions:\n  - cve_id: "CVE-2024-9999"\n', encoding="utf-8")
    assert cve.load_accepted(target) == set()
    assert cve.is_accepted(cve.load_accepted(target), "CVE-2024-9999", "foo") is False


def test_guilt_there_is_no_wildcard_package(tmp_path):
    """A `*` escape hatch would become the shape every future exception takes."""
    accepted = cve.load_accepted(_exceptions(tmp_path, "*"))
    assert cve.is_accepted(accepted, "CVE-2024-9999", "anything") is False


# --------------------------------------------------------------------- innocence

@pytest.mark.parametrize(
    "script,builder", [("filter_snyk_findings.py", _snyk), ("filter_safety_findings.py", _safety)]
)
def test_innocence_the_exception_still_excuses_its_own_package(tmp_path, script, builder):
    """A filter that excused nothing would be safe and useless."""
    result = _run(script, builder(tmp_path, "foo"), _exceptions(tmp_path, "foo"))
    assert result.returncode == 0, result.stdout
    assert "Accepted" in result.stdout


@pytest.mark.parametrize(
    "written,reported",
    [("ruamel.yaml", "ruamel-yaml"), ("Django", "django"), ("zope_interface", "zope.interface")],
)
def test_guilt_a_DIFFERENT_SPELLING_is_a_different_package(tmp_path, written, reported):
    """The first draft folded `-`, `_` and `.` per PEP 503. That is right for PyPI and
    WRONG for npm: `sha.js` and `querystring.es3` are real packages, `@scope/a.b` and
    `@scope/a-b` are different ones, and security.yml:436 runs the Snyk filter on
    snyk-node.json. Folding would have made one npm exception silently cover another —
    this module's own defect, reintroduced inside its fix (kimi-code/k3, 2026-09-05).

    Exactness costs a reviewer nothing: the blocking output prints the scanner's own
    spelling, which is the string to paste. Blocking loudly on a spelling beats
    suppressing quietly across packages.
    """
    accepted = cve.load_accepted(_exceptions(tmp_path, written))
    assert cve.is_accepted(accepted, "CVE-2024-9999", reported) is False


def test_innocence_the_scanners_own_spelling_matches_itself(tmp_path):
    for name in ("ruamel.yaml", "@scope/pkg", "com.google.guava:guava", "Django"):
        accepted = cve.load_accepted(_exceptions(tmp_path, name))
        assert cve.is_accepted(accepted, "CVE-2024-9999", name) is True, name


def test_innocence_a_different_cve_in_the_right_package_is_still_blocked(tmp_path):
    accepted = cve.load_accepted(_exceptions(tmp_path, "foo"))
    assert cve.is_accepted(accepted, "CVE-2024-0000", "foo") is False


def test_innocence_the_shipped_exceptions_file_still_parses():
    """It carries zero entries today, which is why tightening this now narrows nothing.

    `== set()` alone pinned NOTHING: a loader that dropped every entry and a correct one
    are indistinguishable on an empty file (kimi-code/k3). So the same loader is also run
    against a populated fixture in the same test, and must come back non-empty.
    """
    shipped = REPO_ROOT / ".security" / "exceptions.yaml"
    assert shipped.is_file()
    assert cve.load_accepted(shipped) == set()
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        populated = Path(tmp) / "exceptions.yaml"
        populated.write_text(EXCEPTION.format(package="foo"), encoding="utf-8")
        assert cve.load_accepted(populated) == {("CVE-2024-9999", "foo")}


def test_this_battery_and_the_orphaned_schema_test_are_both_armed():
    """superscar #2. test_check_cve_exceptions.py existed and NO workflow ran it.

    Substring presence in the file is NOT arming: a filename appears in the changed-paths
    TRIGGER filter as well, so the first version of this test stayed green while the
    actual unit-test loop dropped both entries (kimi-code/k3). It now reads the loop.
    """
    workflow = (REPO_ROOT / ".github" / "workflows" / "immune-enforcement.yml").read_text(
        encoding="utf-8"
    )
    marker = "Unit tests (guilt + innocence per tool)"
    assert marker in workflow
    loop = workflow[workflow.index(marker):]
    loop = loop[: loop.index("\n      - name:")] if "\n      - name:" in loop else loop
    for test in (
        "scripts/tests/test_cve_exception_package_scope.py",
        "scripts/tests/test_check_cve_exceptions.py",
    ):
        assert test in loop, f"{test} is not in the unit-test loop, only in the trigger filter"


# --------------------------------- what an adversarial review broke the first draft on


def test_guilt_the_display_placeholder_is_not_a_wildcard(tmp_path):
    """Both filters print "(unknown)" when the scanner omits a package name.

    An exception written `package: "(unknown)"` passed the schema checker and matched
    EVERY packageless finding on both scanners — a wildcard made of a display string, in
    a gate whose design refuses wildcards (kimi-code/k3). Reproduced end to end, through
    the real script, not through the matcher alone.
    """
    exceptions = tmp_path / "exceptions.yaml"
    exceptions.write_text(EXCEPTION.format(package="(unknown)"), encoding="utf-8")
    report = tmp_path / "snyk.json"
    report.write_text(json.dumps({"vulnerabilities": [{
        "id": "S1", "identifiers": {"CVE": ["CVE-2024-9999"]}, "severity": "high",
    }]}), encoding="utf-8")
    result = _run("filter_snyk_findings.py", report, exceptions)
    assert result.returncode == 1, result.stdout
    assert cve.load_accepted(exceptions) == set()


@pytest.mark.parametrize("package", ["*", "", "   ", "all packages", "(unknown)", "?"])
def test_guilt_a_package_that_is_not_an_identifier_is_unusable(tmp_path, package):
    exceptions = tmp_path / "exceptions.yaml"
    exceptions.write_text(EXCEPTION.format(package=package), encoding="utf-8")
    assert cve.load_accepted(exceptions) == set()


def test_guilt_an_expired_exception_is_not_honoured_by_the_MATCHER(tmp_path):
    """Expiry was enforced only by workflow step ordering, invisible to this module.

    check_cve_exceptions.py runs as an earlier step in the same job, so an expired entry
    never reaches matching today — but that invariant lives in two YAML files, and a local
    run, a new workflow or a reordered job would silently honour expired triage.
    """
    exceptions = tmp_path / "exceptions.yaml"
    exceptions.write_text(
        EXCEPTION.format(package="foo").replace('expires_at: "2026-11-01"', 'expires_at: "2026-01-01"'),
        encoding="utf-8",
    )
    assert cve.load_accepted(exceptions) == set()
    assert _run("filter_snyk_findings.py", _snyk(tmp_path, "foo"), exceptions).returncode == 1


def test_guilt_a_duplicated_exceptions_key_is_refused(tmp_path):
    """`.security/exceptions.yaml` is a POLICY document and is loaded strictly.

    An earlier draft read it with yaml.safe_load — in the same change that armed this file
    next to yaml_strict.py in immune-enforcement.yml's trigger list, and never connected
    them (kimi-code/k3). A second `exceptions:` appended at the bottom replaced the whole
    reviewed list, and the diff read as two added lines.
    """
    exceptions = tmp_path / "exceptions.yaml"
    exceptions.write_text(
        EXCEPTION.format(package="foo") + 'exceptions:\n  - cve_id: "CVE-9999-0001"\n', encoding="utf-8"
    )
    with pytest.raises(Exception, match="duplicate key"):
        cve.load_accepted(exceptions)


def test_guilt_a_finding_carrying_one_unexcused_CVE_still_blocks(tmp_path):
    """`any()` suppressed a whole finding when only one of its CVEs was excused.

    Worse, the accepted line printed cves[0] even when the match was another id — the
    "evidence" named the wrong CVE. The blocking line now names the id a reader must act
    on (kimi-code/k3).
    """
    report = tmp_path / "snyk.json"
    report.write_text(json.dumps({"vulnerabilities": [{
        "id": "S1", "identifiers": {"CVE": ["CVE-2024-9999", "CVE-2025-7777"]},
        "packageName": "foo", "severity": "high",
    }]}), encoding="utf-8")
    result = _run("filter_snyk_findings.py", report, _exceptions(tmp_path, "foo"))
    assert result.returncode == 1, result.stdout
    assert "CVE-2025-7777" in result.stdout


def test_innocence_a_finding_whose_CVEs_are_ALL_excused_is_accepted(tmp_path):
    exceptions = tmp_path / "exceptions.yaml"
    exceptions.write_text(
        EXCEPTION.format(package="foo")
        + EXCEPTION.format(package="foo").replace("exceptions:\n", "").replace(
            "CVE-2024-9999", "CVE-2025-7777"
        ),
        encoding="utf-8",
    )
    report = tmp_path / "snyk.json"
    report.write_text(json.dumps({"vulnerabilities": [{
        "id": "S1", "identifiers": {"CVE": ["CVE-2024-9999", "CVE-2025-7777"]},
        "packageName": "foo", "severity": "high",
    }]}), encoding="utf-8")
    assert _run("filter_snyk_findings.py", report, exceptions).returncode == 0


def test_innocence_the_same_CVE_in_TWO_packages_is_legitimate(tmp_path):
    """The no-wildcard design REQUIRES two entries, and the checker used to forbid them.

    check_cve_exceptions.py keyed its duplicate rule on cve_id alone, so the first genuine
    two-package triage would have failed the build — a direct self-contradiction with the
    module that refuses wildcards on the grounds that "two entries are two lines and two
    reviews" (kimi-code/k3). Reproduced: exit 1 before, exit 0 now.
    """
    exceptions = tmp_path / "exceptions.yaml"
    exceptions.write_text(
        EXCEPTION.format(package="foo")
        + EXCEPTION.format(package="bar").replace("exceptions:\n", ""),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_cve_exceptions.py")],
        capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "CVE_EXCEPTIONS_PATH": str(exceptions)},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert cve.load_accepted(exceptions) == {("CVE-2024-9999", "foo"), ("CVE-2024-9999", "bar")}


def test_guilt_the_same_CVE_in_the_SAME_package_is_still_a_duplicate(tmp_path):
    """The over-match direction of that fix: a real double-entry must still be caught."""
    exceptions = tmp_path / "exceptions.yaml"
    exceptions.write_text(
        EXCEPTION.format(package="foo")
        + EXCEPTION.format(package="foo").replace("exceptions:\n", ""),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_cve_exceptions.py")],
        capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "CVE_EXCEPTIONS_PATH": str(exceptions)},
    )
    assert result.returncode == 1
    assert "duplicate exception" in result.stdout + result.stderr
