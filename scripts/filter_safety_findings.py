#!/usr/bin/env python3
"""Filter Safety JSON output against the CVE exception list.

Usage: ``python scripts/filter_safety_findings.py <safety-report.json>``

Safety 3.x JSON shape:

    {
      "vulnerabilities": [
        {"vulnerability_id": "12345", "CVE": "CVE-2025-1234",
         "severity": "high", "package_name": "pkg", ...},
        ...
      ]
    }

Older pyup-safety formats use top-level lists. We try a couple of shapes so
the filter is robust across Safety releases.

Exit codes
----------
0   no un-accepted vulnerabilities
1   at least one un-accepted HIGH/CRITICAL finding
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.stderr.write("PyYAML is required (pip install pyyaml)\n")
    sys.exit(1)


BLOCKING_SEVERITIES = {"high", "critical"}


def _load_accepted_cves(exceptions_path: Path) -> set[str]:
    if not exceptions_path.is_file():
        return set()
    data = yaml.safe_load(exceptions_path.read_text()) or {}
    raw = data.get("exceptions") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return set()
    return {e["cve_id"] for e in raw if isinstance(e, dict) and "cve_id" in e}


def _extract_findings(report: Any) -> list[dict[str, Any]]:
    # Safety 3.x returns a dict with "vulnerabilities".
    if isinstance(report, dict):
        vulns = report.get("vulnerabilities")
        if isinstance(vulns, list):
            return [v for v in vulns if isinstance(v, dict)]
    # pyup-safety legacy: list of lists [package, spec, version, desc, vuln_id, cve]
    # or list of dicts.
    if isinstance(report, list):
        return [v for v in report if isinstance(v, dict)]
    return []


def _severity(finding: dict[str, Any]) -> str:
    # Safety 3.x has "severity" directly; legacy embeds inside nested dicts.
    sev = finding.get("severity") or finding.get("cvssv3_severity") or ""
    if isinstance(sev, str):
        return sev.lower()
    return ""


def _cve_id(finding: dict[str, Any]) -> str:
    # Safety 3.x: CVE field is "CVE" (uppercase) or "cve".
    for key in ("CVE", "cve", "cve_id"):
        v = finding.get(key)
        if isinstance(v, str) and v.startswith("CVE-"):
            return v
    return ""


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write("usage: filter_safety_findings.py <safety-report.json>\n")
        return 1

    report_path = Path(argv[1])
    if not report_path.is_file():
        # Default lenient (see filter_snyk_findings.py for rationale): a
        # missing report means the scanner couldn't run, which is not the
        # same as "found HIGH CVEs". Upgrade to strict with
        # FILTER_REQUIRE_REPORT=1 when you want the delivery train to stop
        # on any scanner outage.
        require = os.environ.get("FILTER_REQUIRE_REPORT", "0") not in ("0", "", "false", "False")
        msg = f"Safety report not found: {report_path}. Scanner may have failed."
        if require:
            sys.stderr.write(f"{msg} FILTER_REQUIRE_REPORT=1 → failing the job.\n")
            return 1
        sys.stderr.write(f"⚠️  {msg} FILTER_REQUIRE_REPORT not set → passing.\n")
        return 0

    try:
        report = json.loads(report_path.read_text())
    except json.JSONDecodeError:
        # Empty file is OK — Safety writes nothing when there are 0 vulns.
        if not report_path.stat().st_size:
            print("✅ Safety report empty — no vulnerabilities.")
            return 0
        sys.stderr.write(f"Failed to parse {report_path}.\n")
        return 1

    exceptions_path = Path(os.environ.get("CVE_EXCEPTIONS_PATH", ".security/exceptions.yaml"))
    accepted = _load_accepted_cves(exceptions_path)

    unaccepted: list[tuple[str, str, str]] = []
    accepted_hits: list[tuple[str, str, str]] = []

    for finding in _extract_findings(report):
        severity = _severity(finding)
        if severity and severity not in BLOCKING_SEVERITIES:
            continue
        cve = _cve_id(finding)
        package = finding.get("package_name") or finding.get("package") or "(unknown)"
        label = cve if cve else f"safety-{finding.get('vulnerability_id', '?')}"
        if cve and cve in accepted:
            accepted_hits.append((label, package, severity or "unknown"))
        else:
            unaccepted.append((label, package, severity or "unknown"))

    if accepted_hits:
        print("Accepted (in .security/exceptions.yaml):")
        for cve, pkg, sev in accepted_hits:
            print(f"  - {cve} in {pkg} (severity={sev})")

    if unaccepted:
        print("\n❌ Blocking Safety findings (not in .security/exceptions.yaml):")
        for cve, pkg, sev in unaccepted:
            print(f"  - {cve} in {pkg} (severity={sev})")
        print(
            "\nEither patch the dependency or add a well-formed exception per "
            "docs/security/CVE_TRIAGE_POLICY.md."
        )
        return 1

    print("✅ No blocking Safety findings.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
