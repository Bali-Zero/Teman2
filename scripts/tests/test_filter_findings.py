"""Tests for filter_snyk_findings.py and filter_safety_findings.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from textwrap import dedent

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import filter_safety_findings as safety_mod  # type: ignore[import-not-found]
import filter_snyk_findings as snyk_mod  # type: ignore[import-not-found]


# ---------------------------------------------------------------------------
# Snyk filter
# ---------------------------------------------------------------------------

def _write_snyk(tmp_path: Path, vulns: list[dict]) -> Path:
    report = {"vulnerabilities": vulns}
    path = tmp_path / "snyk.json"
    path.write_text(json.dumps(report))
    return path


def test_snyk_no_findings_passes(tmp_path: Path, monkeypatch) -> None:
    report = _write_snyk(tmp_path, [])
    monkeypatch.setenv("CVE_EXCEPTIONS_PATH", str(tmp_path / "no_such_file.yaml"))
    assert snyk_mod.main(["prog", str(report)]) == 0


def test_snyk_blocks_on_high_severity(tmp_path: Path, monkeypatch) -> None:
    report = _write_snyk(tmp_path, [{
        "severity": "high",
        "packageName": "requests",
        "identifiers": {"CVE": ["CVE-2025-00001"]},
    }])
    monkeypatch.setenv("CVE_EXCEPTIONS_PATH", str(tmp_path / "no_such_file.yaml"))
    assert snyk_mod.main(["prog", str(report)]) == 1


def test_snyk_honours_exception(tmp_path: Path, monkeypatch) -> None:
    exceptions = tmp_path / "exceptions.yaml"
    exceptions.write_text(dedent("""\
        exceptions:
          - cve_id: CVE-2025-00001
            package: requests
            version: "2.0.0"
            reason: Waiting on upstream
            approved_by: zero
            approved_at: 2026-04-01
            expires_at: 2026-06-01
    """))
    report = _write_snyk(tmp_path, [{
        "severity": "high",
        "packageName": "requests",
        "identifiers": {"CVE": ["CVE-2025-00001"]},
    }])
    monkeypatch.setenv("CVE_EXCEPTIONS_PATH", str(exceptions))
    assert snyk_mod.main(["prog", str(report)]) == 0


def test_snyk_medium_is_ignored(tmp_path: Path, monkeypatch) -> None:
    report = _write_snyk(tmp_path, [{
        "severity": "medium",
        "packageName": "requests",
        "identifiers": {"CVE": ["CVE-2025-00002"]},
    }])
    monkeypatch.setenv("CVE_EXCEPTIONS_PATH", str(tmp_path / "no_such_file.yaml"))
    assert snyk_mod.main(["prog", str(report)]) == 0


def test_snyk_missing_cve_id_fails(tmp_path: Path, monkeypatch) -> None:
    # A HIGH finding without CVE id cannot be accepted via exception — fail closed.
    report = _write_snyk(tmp_path, [{
        "severity": "critical",
        "packageName": "mystery-pkg",
        "identifiers": {"CVE": []},
    }])
    monkeypatch.setenv("CVE_EXCEPTIONS_PATH", str(tmp_path / "no_such_file.yaml"))
    assert snyk_mod.main(["prog", str(report)]) == 1


def test_snyk_missing_report_file_lenient_passes(tmp_path: Path, monkeypatch) -> None:
    """Default: missing report passes (lenient — Snyk outage ≠ CVE)."""
    monkeypatch.setenv("CVE_EXCEPTIONS_PATH", str(tmp_path / "no_such_file.yaml"))
    monkeypatch.delenv("FILTER_REQUIRE_REPORT", raising=False)
    assert snyk_mod.main(["prog", str(tmp_path / "does_not_exist.json")]) == 0


def test_snyk_missing_report_file_strict_fails(tmp_path: Path, monkeypatch) -> None:
    """Strict mode: FILTER_REQUIRE_REPORT=1 → missing report fails."""
    monkeypatch.setenv("CVE_EXCEPTIONS_PATH", str(tmp_path / "no_such_file.yaml"))
    monkeypatch.setenv("FILTER_REQUIRE_REPORT", "1")
    assert snyk_mod.main(["prog", str(tmp_path / "does_not_exist.json")]) == 1


def test_snyk_multiproject_list(tmp_path: Path, monkeypatch) -> None:
    # Snyk --all-projects returns a list.
    report_data = [
        {"vulnerabilities": [{"severity": "high", "packageName": "a",
                              "identifiers": {"CVE": ["CVE-2025-01"]}}]},
        {"vulnerabilities": []},
    ]
    path = tmp_path / "snyk.json"
    path.write_text(json.dumps(report_data))
    monkeypatch.setenv("CVE_EXCEPTIONS_PATH", str(tmp_path / "no_such_file.yaml"))
    assert snyk_mod.main(["prog", str(path)]) == 1


# ---------------------------------------------------------------------------
# Safety filter
# ---------------------------------------------------------------------------

def _write_safety(tmp_path: Path, vulns: list[dict]) -> Path:
    path = tmp_path / "safety.json"
    path.write_text(json.dumps({"vulnerabilities": vulns}))
    return path


def test_safety_no_findings_passes(tmp_path: Path, monkeypatch) -> None:
    path = _write_safety(tmp_path, [])
    monkeypatch.setenv("CVE_EXCEPTIONS_PATH", str(tmp_path / "no_such_file.yaml"))
    assert safety_mod.main(["prog", str(path)]) == 0


def test_safety_blocks_on_high(tmp_path: Path, monkeypatch) -> None:
    path = _write_safety(tmp_path, [{
        "package_name": "pyyaml",
        "CVE": "CVE-2025-00010",
        "severity": "high",
        "vulnerability_id": "56789",
    }])
    monkeypatch.setenv("CVE_EXCEPTIONS_PATH", str(tmp_path / "no_such_file.yaml"))
    assert safety_mod.main(["prog", str(path)]) == 1


def test_safety_honours_exception(tmp_path: Path, monkeypatch) -> None:
    exceptions = tmp_path / "exceptions.yaml"
    exceptions.write_text(dedent("""\
        exceptions:
          - cve_id: CVE-2025-00010
            package: pyyaml
            version: "6.0.1"
            reason: Waiting on upstream
            approved_by: zero
            approved_at: 2026-04-01
            expires_at: 2026-06-01
    """))
    path = _write_safety(tmp_path, [{
        "package_name": "pyyaml",
        "CVE": "CVE-2025-00010",
        "severity": "high",
        "vulnerability_id": "56789",
    }])
    monkeypatch.setenv("CVE_EXCEPTIONS_PATH", str(exceptions))
    assert safety_mod.main(["prog", str(path)]) == 0


def test_safety_empty_file_passes(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "safety.json"
    path.write_text("")
    monkeypatch.setenv("CVE_EXCEPTIONS_PATH", str(tmp_path / "no_such_file.yaml"))
    assert safety_mod.main(["prog", str(path)]) == 0


def test_safety_missing_report_lenient_passes(tmp_path: Path, monkeypatch) -> None:
    """Default: missing Safety report passes (lenient — scanner outage ≠ CVE)."""
    monkeypatch.setenv("CVE_EXCEPTIONS_PATH", str(tmp_path / "no_such_file.yaml"))
    monkeypatch.delenv("FILTER_REQUIRE_REPORT", raising=False)
    assert safety_mod.main(["prog", str(tmp_path / "does_not_exist.json")]) == 0


def test_safety_missing_report_strict_fails(tmp_path: Path, monkeypatch) -> None:
    """Strict mode: FILTER_REQUIRE_REPORT=1 → missing report fails."""
    monkeypatch.setenv("CVE_EXCEPTIONS_PATH", str(tmp_path / "no_such_file.yaml"))
    monkeypatch.setenv("FILTER_REQUIRE_REPORT", "1")
    assert safety_mod.main(["prog", str(tmp_path / "does_not_exist.json")]) == 1
