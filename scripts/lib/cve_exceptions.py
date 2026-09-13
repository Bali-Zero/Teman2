"""Matching rules for `.security/exceptions.yaml`, shared by both scanner filters.

WHY THIS EXISTS. `filter_snyk_findings.py` and `filter_safety_findings.py` each carried
their own copy of the accepted-set builder, and both keyed on the CVE id ALONE:

    return {e["cve_id"] for e in raw if isinstance(e, dict) and "cve_id" in e}

`package` is a REQUIRED field of the exception schema — check_cve_exceptions.py refuses an
entry without it — and neither filter read it back. Measured 2026-09-05 with an exception
scoped to package `foo` and a HIGH finding for the same CVE in `bar`:

    Accepted (in .security/exceptions.yaml):
      - CVE-2024-9999 in bar (severity=high)
    ✅ No blocking CVEs.                                    exit 0

Both scanners, and the filter PRINTED the package it did not check. A required field that
no consumer reads is not a control; it is a field.

THREE DESIGN CHOICES, each of which an adversarial review (kimi-code/k3, 2026-09-05) broke
an earlier draft on. They are recorded here because each looks like over-caution until you
have the input that defeats the alternative.

1. EXACT package comparison, no normalisation. The first draft folded `-`, `_` and `.` per
   PEP 503, which is correct for PyPI and WRONG for npm: `sha.js` and `querystring.es3` are
   real npm packages, `@scope/a.b` and `@scope/a-b` are different packages, and
   security.yml:436 runs the Snyk filter on snyk-node.json. Folding would have made an
   exception for one npm package silently cover another — the very defect this module
   exists to close, reintroduced in the fix. Exactness costs a reviewer nothing: the
   blocking output prints the scanner's own spelling verbatim, which is the string to
   paste.

2. The package must look like an IDENTIFIER. Both filters substitute the literal
   `"(unknown)"` for display when the scanner omits a package name. An exception written
   `package: "(unknown)"` passed the schema checker and matched EVERY packageless finding
   on both scanners — a wildcard made of a display placeholder, in a module whose whole
   design refuses wildcards. Rejected here rather than only at the call sites, so a third
   caller cannot reopen it.

3. EXPIRY is enforced HERE, not only by workflow step ordering. Today check_cve_exceptions.py
   runs as an earlier step in the same job and a failure stops the job before the filter
   runs — so an expired exception never reaches matching. That invariant lives in two YAML
   files and is invisible to this module: a local run, a new workflow, or a reordered job
   would silently honour expired triage. An expired entry is unusable, in the same place
   the matching lives.

NO WILDCARD. A `package: "*"` escape hatch would become the shape every future exception
takes. Two entries are two lines and two reviews — and check_cve_exceptions.py's duplicate
rule was changed in the same PR to key on (cve_id, package), because it forbade exactly the
two-entry usage this design requires. `.security/exceptions.yaml` carries zero entries
today, so nothing in force is narrowed here.
"""

from __future__ import annotations

import datetime as _dt
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

#: A CVE id paired with the package it was triaged in.
AcceptedKey = tuple[str, str]

#: A package name is an identifier: letters, digits, and the separators the ecosystems in
#: play actually use (npm scopes `@scope/name`, Maven `group:artifact`, Go module paths).
#: The point is not to validate a name — it is to refuse the display placeholders and
#: prose that would otherwise become wildcards.
# The leading `@?` is npm scopes (`@scope/name`), which the first regex rejected —
# caught by the innocence half of this module's own battery, which is what that half
# is for: a guard that refused every scoped npm package would have blocked the Node
# gate's legitimate exceptions outright.
_IDENTIFIER = re.compile(r"^@?[A-Za-z0-9][A-Za-z0-9._@/:+-]*$")

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _yaml_strict():
    """The shared strict policy loader, path-loaded under the one canonical name.

    `.security/exceptions.yaml` is a POLICY document: it decides which known
    vulnerabilities do not block a deploy. An earlier draft of this module read it with
    yaml.safe_load — in the same change that armed this file next to yaml_strict.py in
    immune-enforcement.yml's trigger list, and never connected them. safe_load lets a
    duplicate top-level key win in silence, so a second `exceptions:` appended at the
    bottom replaces the entire reviewed list and the diff reads as two added lines.
    """
    module = sys.modules.get("nuzantara_yaml_strict")
    if module is not None:
        return module
    strict_path = _REPO_ROOT / "scripts" / "lib" / "yaml_strict.py"
    spec = importlib.util.spec_from_file_location("nuzantara_yaml_strict", strict_path)
    if spec is None or spec.loader is None or not strict_path.is_file():
        raise RuntimeError(f"strict policy loader not found at {strict_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["nuzantara_yaml_strict"] = module
    spec.loader.exec_module(module)
    return module


def is_package_identifier(name: Any) -> bool:
    """False for display placeholders, prose, globs and anything empty."""
    return isinstance(name, str) and bool(_IDENTIFIER.match(name.strip()))


def _expired(entry: dict[str, Any], today: _dt.date) -> bool:
    """An unparseable or absent `expires_at` counts as EXPIRED.

    check_cve_exceptions.py refuses both, so reaching this branch means the validator did
    not run — which is exactly the case this check exists for. Unusable, never universal.
    """
    raw = entry.get("expires_at")
    if not isinstance(raw, str):
        return True
    try:
        return _dt.date.fromisoformat(raw.strip()) < today
    except ValueError:
        return True


def load_accepted(exceptions_path: Path, *, today: _dt.date | None = None) -> set[AcceptedKey]:
    """(cve_id, package) for every exception that is well-formed AND still in date.

    A missing file yields the empty set: nothing is excused, so every real finding blocks.
    """
    if not exceptions_path.is_file():
        return set()
    document = _yaml_strict().load_policy(exceptions_path)
    raw = document.get("exceptions")
    if not isinstance(raw, list):
        return set()
    today = today or _dt.date.today()
    accepted: set[AcceptedKey] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        cve = entry.get("cve_id")
        package = entry.get("package")
        if not isinstance(cve, str) or not cve.strip():
            continue
        if not is_package_identifier(package):
            continue
        if _expired(entry, today):
            continue
        accepted.add((cve.strip(), package.strip()))
    return accepted


def is_accepted(accepted: set[AcceptedKey], cve: str, package: Any) -> bool:
    """True only if THIS cve was triaged in THIS package, spelled as the scanner spells it.

    A finding whose package the scanner did not report cannot be matched, so it blocks — an
    unidentifiable dependency is the last thing that should inherit someone else's triage.
    """
    if not is_package_identifier(package):
        return False
    return (cve, package.strip()) in accepted
