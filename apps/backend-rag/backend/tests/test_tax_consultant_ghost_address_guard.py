"""Guard: no source file under backend/ may hard-code either ghost
tax-consultant address.

Migration 319 (migrations_v2/319_align_tax_consultant_allowlist_to_team_
members.sql) retired 'veronika.tax@balizero.com' and
'faisha.tax@balizero.com' (note the I) — neither exists in team_members,
the canonical staff table. Four independent Python copies of the tax-team
allowlist (crm_clients.py, lkpm.py, lkpm_deadline_notifier.py, and the
legacy migration_093 module) each carried one or both, and none of the four
noticed the other three had drifted the same way — that silent multiplicity
is exactly what let two ghost addresses reach production CHECK constraints
while two real staff addresses were rejected. This sweep is the backstop:
it fails the moment either ghost string reappears anywhere under backend/,
except SETTLED HISTORY (a migration that already ran against production
before this fix existed) and this guard itself, which must hold the
literal strings to know what to look for.
"""

from __future__ import annotations

from pathlib import Path

GHOST_STRINGS: tuple[str, ...] = ("veronika.tax@", "faisha.tax@")

BACKEND_ROOT = Path(__file__).resolve().parents[1]

# Relative to BACKEND_ROOT. Each is historical, not live code:
#   - 319_...sql: this fix's own migration. Its header prose names the
#     retired ghosts, and its rollback section restores the pre-319
#     constraint, which allowed them — both legitimate.
#   - migration_093_...py: the legacy manual-tier tracker (grandfathered
#     into LEGACY_NO_ROLLBACK_WHITELIST, migration_base.py). It already ran
#     against production under the ghost list; rewriting its literal tuple
#     would misrepresent what actually shipped.
#   - 110_lkpm_allowlist_krisna.sql: applied to production 2026-04-16, five
#     months before this fix. Same "settled history" reasoning as 093 —
#     not named in the original mandate's exclusion list, added here after
#     the sweep found it (see REPORT-RC.md item 6).
_EXCLUDED_RELATIVE_PATHS: frozenset[str] = frozenset(
    {
        "db/migrations_v2/319_align_tax_consultant_allowlist_to_team_members.sql",
        "migrations/migration_093_lkpm_assigns_and_oss_creds.py",
        "db/migrations_v2/110_lkpm_allowlist_krisna.sql",
    }
)

_SCANNED_SUFFIXES: frozenset[str] = frozenset({".py", ".sql"})


def _iter_source_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts:
            continue
        if path.suffix not in _SCANNED_SUFFIXES:
            continue
        yield path


def find_ghost_violations(
    root: Path, *, excluded: frozenset[str] = frozenset()
) -> list[tuple[Path, str]]:
    """Return (file, ghost_string) for every hard-coded ghost occurrence
    under `root`, skipping paths (relative to `root`) listed in `excluded`.
    """
    violations: list[tuple[Path, str]] = []
    for path in _iter_source_files(root):
        rel = path.relative_to(root).as_posix()
        if rel in excluded:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for ghost in GHOST_STRINGS:
            if ghost in text:
                violations.append((path, ghost))
    return violations


def test_sweep_visits_a_nonzero_number_of_files() -> None:
    """An empty sweep (broken BACKEND_ROOT, wrong suffix set) must not be
    able to silently 'pass' by scanning nothing."""
    scanned = list(_iter_source_files(BACKEND_ROOT))
    assert len(scanned) > 100, (
        f"expected the backend/ sweep to visit hundreds of files, got "
        f"{len(scanned)} — BACKEND_ROOT ({BACKEND_ROOT}) is probably wrong"
    )


def test_real_backend_tree_has_no_ghost_addresses() -> None:
    this_file_rel = Path(__file__).resolve().relative_to(BACKEND_ROOT).as_posix()
    excluded = _EXCLUDED_RELATIVE_PATHS | {this_file_rel}
    violations = find_ghost_violations(BACKEND_ROOT, excluded=excluded)
    assert violations == [], (
        "ghost tax-consultant address hard-coded outside settled history: "
        f"{[(str(p), g) for p, g in violations]}"
    )


def test_guilt_control_synthetic_ghost_is_caught(tmp_path: Path) -> None:
    """A fabricated file carrying the ghost string MUST be caught."""
    guilty = tmp_path / "guilty.py"
    guilty.write_text("ASSIGNEE = 'veronika.tax@balizero.com'\n", encoding="utf-8")
    violations = find_ghost_violations(tmp_path)
    assert violations == [(guilty, "veronika.tax@")]


def test_innocence_control_real_addresses_are_not_flagged(tmp_path: Path) -> None:
    """The two REAL addresses this migration introduced must NOT be flagged
    — proves the sweep matches the ghost strings only, not '.tax@balizero'
    in general."""
    innocent = tmp_path / "innocent.py"
    innocent.write_text(
        "TAX_MANAGER = 'tax@balizero.com'\n"
        "TAX_FAISHA = 'faysha.tax@balizero.com'\n"
        "TAX_ANGEL = 'angel.tax@balizero.com'\n",
        encoding="utf-8",
    )
    assert find_ghost_violations(tmp_path) == []
