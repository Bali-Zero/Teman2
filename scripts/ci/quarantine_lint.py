#!/usr/bin/env python3
"""quarantine_lint.py — Merge-OS v3 step 6 slice 1 judge (Codex F6 disposition).

Spec: research/operations/2026-08-14-merge-os-v3-research-council.md §5 row
"Codex F6 (vacuous critical marker)" + §6 step 6. Today the pytest `critical`
marker registered in apps/backend-rag/pytest.ini is used by ZERO tests
(verified: `grep -rn "pytest.mark.critical" apps/backend-rag/` -> no hits) —
an unused marker that a quarantine mechanism would have excluded FROM is not
a barrier, it is the appearance of one (cicatrix-superscar.md family #2,
"esiste != armato"). The fix inverts the polarity to default-deny:

  - infra/merge-os/quarantine.d/*.yaml  — a protected ALLOWLIST. A test is
    excused from blocking CI ONLY by an explicit, owned, time-boxed entry
    here. Absence of an entry = blocking (the correct default).
  - infra/merge-os/critical-floor.d/*.yaml — a POSITIVE, populated manifest
    of test categories that can NEVER be quarantined, regardless of any
    grant. Never the complement of the (unused, now-irrelevant) `critical`
    marker.

This script is the judge over both. See infra/merge-os/quarantine.d/SCHEMA.md
and infra/merge-os/critical-floor.d/SCHEMA.md for the full field contract —
this docstring covers what gets CHECKED, not what the fields mean.

WHAT IT CHECKS:

  1. Every quarantine entry has all 9 required fields (node_id, owner,
     issue, failure_fingerprint, first_seen, expires_at, sample_size,
     observed_flake_rate, reason), non-empty, correctly typed. Missing/
     malformed field(s) -> FAIL, naming the file and the field(s).
  2. `first_seen` is a valid ISO date and not in the future (relative to
     `--now`, default today).
  3. `expires_at` is a valid ISO date, and `expires_at - first_seen <= 14
     days` — the structural grant-length cap declared in the schema.
  4. `expires_at < now` -> FAIL ("expired quarantine = test goes back to
     blocking" — an expired grant is a VIOLATION, not a silently-renewing
     excuse; this is the check that makes the 14-day cap actually bite).
  5. No quarantined `node_id` (file-path portion, before the first `::`)
     matches ANY critical-floor pattern -> FAIL if it does. The floor wins
     even against an otherwise well-formed quarantine grant.
  6. Every critical-floor entry has its required fields (id, category,
     patterns non-empty).
  7. Every critical-floor pattern/path matches >= 1 real file under
     `--repo-root` -> FAIL if a pattern is ORPHANED (anti-decorative: a
     floor category protecting zero real files is the exact same defect,
     `critical` marker included, dressed in YAML instead of a pytest mark).

Patterns/paths (both directories) are resolved relative to `--repo-root`.
A `patterns` entry containing `*` is treated as a `pathlib.Path.glob()`
pattern (supports `**`); an entry with no `*` is treated as a literal file
path that must exist.

FAIL-VISIBLE, stdlib + PyYAML only (no repo imports — this must be runnable
standalone, e.g. from a hot workflow or a pre-commit hook, without pulling
in the backend's own dependency tree).

Exit codes:
  0  clean — every entry (both directories) valid, no floor collisions, no
     orphan patterns. An EMPTY quarantine.d/ (no grants at all) is the
     normal, valid, zero-entry case — not an error.
  1  a violation was found (any of checks 1-7 above failed for at least one
     entry).
  2  cannot verify — a YAML file failed to parse, PyYAML is unavailable, or
     `--repo-root`/one of the two manifest directories does not exist as a
     directory at all (an empty SWEEP is not a clean pass, W84 — a swept-zero
     result from a directory that never existed is indistinguishable from a
     genuinely empty, valid manifest unless this is a distinct exit code).

This PR ships ONLY this validator + the manifests + its own test corpus.
Nothing in tests.yml invokes this script yet — wiring the verdict into CI
(actually skipping/soft-failing a quarantined node_id, and hard-failing a
build when this script exits 1) is a declared follow-up PR (tests.yml is a
hot file with a sibling PR already in the merge queue; built here, armed
later — scar family #2, declared not silently assumed).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # handled explicitly in main() -> exit 2, never a silent skip


QUARANTINE_REQUIRED_FIELDS = (
    "node_id",
    "owner",
    "issue",
    "failure_fingerprint",
    "first_seen",
    "expires_at",
    "sample_size",
    "observed_flake_rate",
    "reason",
)
FLOOR_REQUIRED_FIELDS = ("id", "category", "patterns")
MAX_QUARANTINE_DAYS = 14


@dataclass
class Violation:
    file: str
    message: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.file}: {self.message}"


@dataclass
class LintResult:
    violations: list[Violation] = field(default_factory=list)
    cannot_verify: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations and not self.cannot_verify


# ---------------------------------------------------------------------------
# Pure functions (no I/O) — the judgment logic, independently testable.
# ---------------------------------------------------------------------------


def node_id_path(node_id: str) -> str:
    """The file-path portion of a node_id — everything before the first
    `::` (pytest nodeid separator). A bare file path is returned unchanged."""
    return node_id.split("::", 1)[0]


def path_matches_any_pattern(path: str, patterns: list[str], repo_root: Path) -> bool:
    """True if `path` (relative to repo_root) is matched by any entry in
    `patterns` — glob (contains `*`) matched via Path.glob() against
    repo_root, literal (no `*`) matched by exact relative-path equality."""
    target = (repo_root / path).resolve()
    for pattern in patterns:
        if "*" in pattern:
            for hit in repo_root.glob(pattern):
                if hit.resolve() == target:
                    return True
        else:
            if (repo_root / pattern).resolve() == target:
                return True
    return False


def validate_quarantine_entry(
    entry: dict[str, Any], filename: str, now: date
) -> list[Violation]:
    """All structural checks for one quarantine entry (checks 1-4 in the
    module docstring). Does NOT check the floor collision (check 5) — that
    needs the floor manifest, checked separately by the caller."""
    violations: list[Violation] = []

    missing = [f for f in QUARANTINE_REQUIRED_FIELDS if not entry.get(f) and entry.get(f) != 0]
    if missing:
        violations.append(
            Violation(filename, f"missing/empty required field(s): {', '.join(missing)}")
        )
        return violations  # further checks need the fields to exist

    first_seen_raw = entry["first_seen"]
    expires_at_raw = entry["expires_at"]
    try:
        first_seen = _coerce_date(first_seen_raw)
    except (TypeError, ValueError) as exc:
        violations.append(Violation(filename, f"unparseable first_seen {first_seen_raw!r}: {exc}"))
        return violations
    try:
        expires_at = _coerce_date(expires_at_raw)
    except (TypeError, ValueError) as exc:
        violations.append(Violation(filename, f"unparseable expires_at {expires_at_raw!r}: {exc}"))
        return violations

    if first_seen > now:
        violations.append(
            Violation(filename, f"first_seen {first_seen.isoformat()} is in the future (now={now.isoformat()})")
        )

    if (expires_at - first_seen).days > MAX_QUARANTINE_DAYS:
        violations.append(
            Violation(
                filename,
                f"expires_at {expires_at.isoformat()} is more than {MAX_QUARANTINE_DAYS} days "
                f"after first_seen {first_seen.isoformat()} — quarantine grants are capped",
            )
        )

    if expires_at < now:
        violations.append(
            Violation(
                filename,
                f"quarantine EXPIRED (expires_at={expires_at.isoformat()}, now={now.isoformat()}) "
                "— the test is blocking again; renew with a fresh entry or fix it",
            )
        )

    sample_size = entry["sample_size"]
    if not isinstance(sample_size, int) or isinstance(sample_size, bool) or sample_size < 1:
        violations.append(Violation(filename, f"sample_size must be an integer >= 1, got {sample_size!r}"))

    flake_rate = entry["observed_flake_rate"]
    if not isinstance(flake_rate, (int, float)) or isinstance(flake_rate, bool) or not (0.0 <= float(flake_rate) <= 1.0):
        violations.append(Violation(filename, f"observed_flake_rate must be a number in [0.0, 1.0], got {flake_rate!r}"))

    return violations


def validate_floor_entry(entry: dict[str, Any], filename: str, repo_root: Path) -> list[Violation]:
    """Checks 6-7: required fields present, and every pattern matches >= 1
    real file under repo_root (anti-decorative — no orphan patterns)."""
    violations: list[Violation] = []

    missing = [f for f in FLOOR_REQUIRED_FIELDS if not entry.get(f)]
    if missing:
        violations.append(
            Violation(filename, f"missing/empty required field(s): {', '.join(missing)}")
        )
        return violations

    patterns = entry["patterns"]
    if not isinstance(patterns, list) or not patterns:
        violations.append(Violation(filename, "patterns must be a non-empty list"))
        return violations

    for pattern in patterns:
        if not isinstance(pattern, str):
            violations.append(
                Violation(filename, f"non-string pattern entry (must be a path/glob string): {pattern!r}")
            )
            continue
        if "*" in pattern:
            hits = list(repo_root.glob(pattern))
        else:
            hits = [repo_root / pattern] if (repo_root / pattern).is_file() else []
        if not hits:
            violations.append(
                Violation(filename, f"orphan pattern (matches 0 real files): {pattern!r}")
            )

    return violations


def _coerce_date(value: Any) -> date:
    """YAML's safe_load already turns `YYYY-MM-DD` scalars into `date`
    objects by default — accept that AND a plain string, so a quoted date
    in the manifest (`"2026-08-14"`) still works, never silently coerced
    from something else (e.g. an int)."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"expected a date, got {type(value).__name__}")


# ---------------------------------------------------------------------------
# I/O — loading + orchestration.
# ---------------------------------------------------------------------------


def _load_yaml_dir(dir_path: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Loads every *.yaml file in dir_path (SCHEMA.md is markdown, skipped
    naturally by extension) as {filename: parsed_dict}. Returns
    (entries, cannot_verify_errors). A missing directory is NOT an error —
    the caller decides whether that's valid-empty or CANNOT VERIFY based on
    which directory it is."""
    entries: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    if not dir_path.is_dir():
        return entries, errors
    for path in sorted(dir_path.glob("*.yaml")):
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            errors.append(f"{path}: YAML parse error: {exc}")
            continue
        if doc is None:
            continue  # an empty *.yaml file is not an entry, not an error
        if not isinstance(doc, dict):
            errors.append(f"{path}: expected a mapping at the top level, got {type(doc).__name__}")
            continue
        entries[str(path)] = doc
    return entries, errors


def run_lint(repo_root: Path, quarantine_dir: Path, floor_dir: Path, now: date) -> LintResult:
    result = LintResult()

    if not floor_dir.is_dir():
        result.cannot_verify.append(
            f"critical-floor directory does not exist: {floor_dir} "
            "(an empty sweep from a directory that was never there is not a clean pass)"
        )
        return result

    quarantine_entries, q_errors = _load_yaml_dir(quarantine_dir)
    floor_entries, f_errors = _load_yaml_dir(floor_dir)
    result.cannot_verify.extend(q_errors)
    result.cannot_verify.extend(f_errors)
    if result.cannot_verify:
        return result

    if not floor_entries:
        result.cannot_verify.append(
            f"critical-floor directory has zero valid *.yaml entries: {floor_dir} "
            "(a floor that protects nothing is not a clean pass)"
        )
        return result

    # Floor entries: structural + orphan-pattern checks.
    all_floor_patterns: list[str] = []
    for filename, entry in floor_entries.items():
        result.violations.extend(validate_floor_entry(entry, filename, repo_root))
        patterns = entry.get("patterns")
        if isinstance(patterns, list):
            all_floor_patterns.extend(p for p in patterns if isinstance(p, str))

    # Quarantine entries: structural checks + floor-collision check.
    for filename, entry in quarantine_entries.items():
        entry_violations = validate_quarantine_entry(entry, filename, now)
        result.violations.extend(entry_violations)
        # Floor-collision check only makes sense if node_id itself parsed —
        # i.e. the entry didn't already fail on missing/malformed fields.
        if not entry_violations and "node_id" in entry:
            path = node_id_path(str(entry["node_id"]))
            if path_matches_any_pattern(path, all_floor_patterns, repo_root):
                result.violations.append(
                    Violation(
                        filename,
                        f"node_id {entry['node_id']!r} matches the critical floor — "
                        "this test can never be quarantined",
                    )
                )

    return result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    default_root = Path(__file__).resolve().parent.parent.parent
    parser.add_argument("--repo-root", default=str(default_root), help="default %(default)s")
    parser.add_argument(
        "--quarantine-dir",
        default=None,
        help="default <repo-root>/infra/merge-os/quarantine.d",
    )
    parser.add_argument(
        "--floor-dir",
        default=None,
        help="default <repo-root>/infra/merge-os/critical-floor.d",
    )
    parser.add_argument(
        "--now",
        default=None,
        help="ISO date (YYYY-MM-DD) to treat as 'now' — default: real today (UTC)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if yaml is None:
        print("CANNOT VERIFY: PyYAML is not importable in this environment", file=sys.stderr)
        return 2

    repo_root = Path(args.repo_root).resolve()
    quarantine_dir = Path(args.quarantine_dir) if args.quarantine_dir else repo_root / "infra" / "merge-os" / "quarantine.d"
    floor_dir = Path(args.floor_dir) if args.floor_dir else repo_root / "infra" / "merge-os" / "critical-floor.d"
    if args.now:
        try:
            now = date.fromisoformat(args.now)
        except ValueError as exc:
            print(f"CANNOT VERIFY: --now {args.now!r} is not a valid ISO date: {exc}", file=sys.stderr)
            return 2
    else:
        now = datetime.now(timezone.utc).date()

    result = run_lint(repo_root, quarantine_dir, floor_dir, now)

    if result.cannot_verify:
        for msg in result.cannot_verify:
            print(f"CANNOT VERIFY: {msg}", file=sys.stderr)
        return 2

    if result.violations:
        print(f"{len(result.violations)} quarantine-lint violation(s):", file=sys.stderr)
        for v in result.violations:
            print(f"  {v}", file=sys.stderr)
        return 1

    print(
        f"quarantine-lint: clean "
        f"(quarantine.d valid, critical-floor.d valid, no collisions, no orphan patterns)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
