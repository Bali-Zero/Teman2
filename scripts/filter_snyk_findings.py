#!/usr/bin/env python3
"""Filter Snyk JSON output against the CVE exception list.

Usage: ``python scripts/filter_snyk_findings.py <snyk.json>``

Reads the Snyk JSON report at ``<snyk.json>`` and compares the list of
HIGH+CRITICAL findings against ``.security/exceptions.yaml``. Any finding
whose CVE id is listed (and the exception has not expired — the pre-deploy
check already verified that) is ignored. Any remaining finding fails the job.

Exit codes
----------
0   no un-accepted HIGH/CRITICAL findings
1   at least one un-accepted finding — job should fail
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


def _iter_snyk_findings(report: Any) -> list[dict[str, Any]]:
    """Snyk's JSON output is inconsistent — single-project is an object, multi
    is a list of objects. Both have a ``vulnerabilities`` list per project.
    """
    projects = report if isinstance(report, list) else [report]
    vulns: list[dict[str, Any]] = []
    for project in projects:
        if not isinstance(project, dict):
            continue
        for v in project.get("vulnerabilities") or []:
            if isinstance(v, dict):
                vulns.append(v)
    return vulns


def _cve_ids(finding: dict[str, Any]) -> list[str]:
    """A single Snyk vulnerability can map to multiple CVE ids via
    ``identifiers.CVE`` (list). We match on any of them.
    """
    identifiers = finding.get("identifiers") or {}
    cves = identifiers.get("CVE") if isinstance(identifiers, dict) else None
    if isinstance(cves, list):
        return [c for c in cves if isinstance(c, str)]
    return []


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write("usage: filter_snyk_findings.py <snyk.json>\n")
        return 1

    report_path = Path(argv[1])
    if not report_path.is_file():
        # Snyk didn't produce a report — treat as fail (scanner crashed).
        sys.stderr.write(f"Snyk report not found: {report_path}. Scanner likely failed — investigate before merging.\n")
        return 1

    try:
        report = json.loads(report_path.read_text())
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"Failed to parse {report_path}: {exc}\n")
        return 1

    exceptions_path = Path(os.environ.get("CVE_EXCEPTIONS_PATH", ".security/exceptions.yaml"))
    accepted = _load_accepted_cves(exceptions_path)

    unaccepted: list[tuple[str, str, str]] = []  # (cve, package, severity)
    accepted_hits: list[tuple[str, str, str]] = []

    for finding in _iter_snyk_findings(report):
        severity = (finding.get("severity") or "").lower()
        if severity not in BLOCKING_SEVERITIES:
            continue
        cves = _cve_ids(finding)
        package = finding.get("packageName") or finding.get("moduleName") or "(unknown)"
        if not cves:
            # No CVE id → cannot be accepted by exception — fail.
            unaccepted.append(("(no CVE id)", package, severity))
            continue
        if any(cve in accepted for cve in cves):
            accepted_hits.append((cves[0], package, severity))
        else:
            unaccepted.append((cves[0], package, severity))

    if accepted_hits:
        print("Accepted (in .security/exceptions.yaml):")
        for cve, pkg, sev in accepted_hits:
            print(f"  - {cve} in {pkg} (severity={sev})")

    if unaccepted:
        print("\n❌ Blocking CVEs (HIGH+ and not in .security/exceptions.yaml):")
        for cve, pkg, sev in unaccepted:
            print(f"  - {cve} in {pkg} (severity={sev})")
        print(
            "\nEither patch the dependency or add a well-formed exception per "
            "docs/security/CVE_TRIAGE_POLICY.md."
        )
        return 1

    print("✅ No blocking CVEs.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
