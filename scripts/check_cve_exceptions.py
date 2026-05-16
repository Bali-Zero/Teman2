#!/usr/bin/env python3
"""Verify .security/exceptions.yaml before deploy.

Fails the CI step if any accepted CVE exception has an ``expires_at`` in the
past. Used by ``.github/workflows/fly-deploy.yml`` as a pre-deploy gate.

The schema is documented in ``docs/security/CVE_TRIAGE_POLICY.md``. This
script deliberately re-validates the schema instead of importing a shared
helper — CI runs with a minimal dependency set, and the checks here are
obvious enough to keep in one file.

Exit codes
----------
0   all exceptions are well-formed and non-expired
1   one or more exceptions are expired, malformed, or duplicated
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover — installed in CI
    sys.stderr.write("PyYAML is required (pip install pyyaml)\n")
    sys.exit(1)


REQUIRED_FIELDS = ("cve_id", "package", "version", "reason", "approved_by", "approved_at", "expires_at")
MAX_EXCEPTION_DAYS = 90


def _parse_date(raw: Any, field: str, idx: int) -> date:
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, str):
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError as exc:
            raise SystemExit(
                f"Entry #{idx}: field '{field}'='{raw}' is not a valid YYYY-MM-DD date ({exc})"
            ) from exc
    raise SystemExit(f"Entry #{idx}: field '{field}' must be a date or YYYY-MM-DD string, got {type(raw).__name__}")


def _validate_entry(entry: dict[str, Any], idx: int, today: date) -> list[str]:
    errors: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in entry or entry[field] in (None, ""):
            errors.append(f"Entry #{idx}: missing required field '{field}'")

    if errors:
        return errors

    approved_at = _parse_date(entry["approved_at"], "approved_at", idx)
    expires_at = _parse_date(entry["expires_at"], "expires_at", idx)

    window = (expires_at - approved_at).days
    if window < 0:
        errors.append(
            f"Entry #{idx} ({entry['cve_id']}): expires_at {expires_at} is before approved_at {approved_at}"
        )
    elif window > MAX_EXCEPTION_DAYS:
        errors.append(
            f"Entry #{idx} ({entry['cve_id']}): window {window}d exceeds the {MAX_EXCEPTION_DAYS}d cap "
            f"(approved_at={approved_at}, expires_at={expires_at})"
        )

    if expires_at < today:
        days_ago = (today - expires_at).days
        errors.append(
            f"Entry #{idx} ({entry['cve_id']}): expired on {expires_at} ({days_ago} day(s) ago). "
            "Upgrade the package, renew the exception, or roll back the PR that introduced it."
        )

    return errors


def check(path: Path, today: date | None = None) -> int:
    """Return 0 on success, 1 on any problem. Prints diagnostics to stderr."""
    today = today or date.today()

    if not path.is_file():
        sys.stderr.write(f"{path} does not exist — create it (even empty) per CVE triage policy.\n")
        return 1

    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        sys.stderr.write(f"Failed to parse {path}: {exc}\n")
        return 1

    if not isinstance(data, dict):
        sys.stderr.write(f"{path}: top-level must be a mapping with an 'exceptions' key\n")
        return 1

    raw = data.get("exceptions")
    if raw is None or raw == [] or raw == [None]:
        print(f"{path}: no active CVE exceptions — good.")
        return 0

    if not isinstance(raw, list):
        sys.stderr.write(f"{path}: 'exceptions' must be a list, got {type(raw).__name__}\n")
        return 1

    all_errors: list[str] = []
    seen_cves: dict[str, int] = {}
    active = 0

    for idx, entry in enumerate(raw, start=1):
        if entry is None:
            continue
        if not isinstance(entry, dict):
            all_errors.append(f"Entry #{idx}: must be a mapping, got {type(entry).__name__}")
            continue
        cve = entry.get("cve_id")
        if isinstance(cve, str):
            if cve in seen_cves:
                all_errors.append(f"Entry #{idx}: duplicate cve_id '{cve}' (also at entry #{seen_cves[cve]})")
            else:
                seen_cves[cve] = idx
        all_errors.extend(_validate_entry(entry, idx, today))
        active += 1

    if all_errors:
        sys.stderr.write("\n".join(all_errors) + "\n")
        return 1

    # Warn (non-fatal) on exceptions expiring within a week.
    soon = today + timedelta(days=7)
    for idx, entry in enumerate(raw, start=1):
        if not isinstance(entry, dict):
            continue
        expires_at = _parse_date(entry["expires_at"], "expires_at", idx)
        if today <= expires_at <= soon:
            print(
                f"⚠️  {entry['cve_id']} expires on {expires_at} — renew before deploy-blocking.",
                file=sys.stderr,
            )

    print(f"{path}: {active} active exception(s), all within policy.")
    return 0


def main() -> int:
    default_path = Path(os.environ.get("CVE_EXCEPTIONS_PATH", ".security/exceptions.yaml"))
    return check(default_path)


if __name__ == "__main__":
    sys.exit(main())
