"""Tripwire: seed script's canonical visa_types `name` vs. the LATEST
data-hygiene migration that touched the same code (CLAUDE.md §9 class,
cicatrix family #2 "Esiste != Armato" applied to a data row instead of a
code path).

Born 2026-08-17 from E28D (CF-13,
`research/visa/doctrine-factory/e28-consumer-map.md`, PR #4259): the
law-aligned text for E28D existed in THREE places on disk (the seed script,
the active RulePack, a dedicated factbase research doc) and was never armed
onto the live Postgres `visa_types` row. E28F, its sibling code, got the fix
(migration_125, PR #2859, 2026-07-19) — E28D did not, for ~a month, with no
CI signal catching the divergence. migration_126 (this PR) closes E28D.

What this test pins, concretely: for every `code` that ANY `migration_NNN_*.py`
under `backend/migrations/` declares a `VISA_FIXES`-shaped correction for,
the LATEST such migration's `name` (by highest migration number) must equal
the seed script's canonical `name` for that same code. If a future migration
writes a `name` that then drifts from what the seed script says is canonical
— or a fix is written into the seed script but never armed as a migration
(the exact E28D failure shape) — this test is the thing that has to be
updated in the same PR, not something a research batch discovers nine months
later.

DECLARED LIMIT (intentional, not a gap someone forgot): this does NOT diff
every one of the ~150+ codes in the seed script against the live DB — that
would require either a live DB connection in CI (this repo's test suite is
DB-optional by design) or treating "seed says X, no migration ever
mentioned this code" as an automatic pass, which is exactly the state E28D
was already in for a month with zero signal. What IS a hard, false-positive-
free signal without a live DB is the migration side: whenever a human
DELIBERATELY writes a `migration_NNN_*.py` VISA_FIXES correction for a code,
that correction's `name` must not silently diverge from the seed script's
`name` for the same code. Codes no migration has ever touched are out of
this test's reach by construction (documented, not hidden) — closing that
wider gap needs either a live-DB CI job or a periodic research sweep, not a
unit test. E28D + E28F are pinned explicitly below as named sentinels so the
two codes this incident was actually about can never silently disappear
from coverage even if the generic scan's regex/parsing breaks.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


def _repo_root() -> Path:
    p = Path(__file__).resolve()
    while p != p.parent:
        if (p / "apps").is_dir():
            return p
        p = p.parent
    raise AssertionError("repo root (dir containing apps/) not found from test file")


def _migrations_dir() -> Path:
    return _repo_root() / "apps/backend-rag/backend/migrations"


def _seed_script_path() -> Path:
    return _migrations_dir() / "scripts" / "seed_visa_types_complete_2026.py"


def _find_dict_literal_assignment(tree: ast.Module, var_name: str) -> ast.expr | None:
    """Find `<var_name> = <literal>` at module top level and return the RHS node."""
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == var_name:
                    return node.value
    return None


def _seed_names_by_code() -> dict[str, str]:
    """code -> canonical `name` from VISA_TYPES in the seed script."""
    path = _seed_script_path()
    assert path.exists(), f"seed script missing at {path}"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    node = _find_dict_literal_assignment(tree, "VISA_TYPES")
    assert node is not None, (
        f"VISA_TYPES assignment not found in {path} — the seed script's shape "
        "changed and this tripwire is blind. Update the parser."
    )
    entries = ast.literal_eval(node)
    assert isinstance(entries, list) and len(entries) >= 50, (
        f"VISA_TYPES parsed to {len(entries) if isinstance(entries, list) else type(entries)} "
        "entries — expected 100+ visa codes. The scan looks blind (parser broke or "
        "file was gutted), not that the catalogue actually shrank this much."
    )
    out: dict[str, str] = {}
    for e in entries:
        code = e.get("code")
        name = e.get("name")
        if code and name:
            out[code] = name
    return out


def _latest_migration_fix_names_by_code() -> dict[str, tuple[int, str, str]]:
    """code -> (migration_number, migration_filename, name) for the HIGHEST-
    numbered migration_NNN_*.py that declares a `VISA_FIXES` dict correction
    with a `name` key for that code.

    Only `backend/migrations/migration_NNN_*.py` files are scanned (NOT the
    `scripts/` subdirectory, which holds the seed script and other one-off
    utilities, not corrections) — this is the same ad-hoc data-hygiene
    convention migration_125 (E28F fix) and migration_126 (E28D fix) both
    live in; see either file's own docstring for why this is a separate
    convention from the Squawk-linted `db/migrations_v2/*.sql` runner.
    """
    latest: dict[str, tuple[int, str, str]] = {}
    for path in sorted(_migrations_dir().glob("migration_*.py")):
        # Migration numbers are the leading digits after "migration_"
        # (e.g. "migration_114a_..." -> 114). Non-numeric-prefixed files are
        # skipped — none exist today, but a future oddly-named file should
        # not crash the scan.
        stem = path.stem  # e.g. "migration_125_fix_visa_family_descendant_hygiene"
        num_str = stem[len("migration_") :].split("_", 1)[0]
        num_str = "".join(ch for ch in num_str if ch.isdigit())
        if not num_str:
            continue
        num = int(num_str)

        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        node = _find_dict_literal_assignment(tree, "VISA_FIXES")
        if node is None:
            continue
        try:
            fixes = ast.literal_eval(node)
        except (ValueError, SyntaxError):
            continue
        if not isinstance(fixes, dict):
            continue

        for code, data in fixes.items():
            if not isinstance(data, dict) or "name" not in data:
                continue
            name = data["name"]
            prior = latest.get(code)
            if prior is None or num > prior[0]:
                latest[code] = (num, path.name, name)

    return latest


def test_no_migration_file_has_an_unparseable_visa_fixes() -> None:
    """Every `migration_NNN_*.py` whose SOURCE mentions the literal token
    `VISA_FIXES` must be scannable by `_latest_migration_fix_names_by_code`
    as a module-level, `ast.literal_eval`-able dict.

    Without this, a future migration written as `VISA_FIXES: dict = {...}`
    (annotated assignment) or `VISA_FIXES = dict(E28D={...})` (call, not a
    dict literal) would silently vanish from the scan — the file exists, the
    correction runs against prod, but this tripwire never sees it and the
    `>= 8` blindness guard only trips if the TOTAL count drops, which a
    single new invisible file does not cause. This test closes that gap by
    checking presence-of-the-token vs. presence-in-the-scan for every file,
    not just today's known set.
    """
    unparseable = []
    for path in sorted(_migrations_dir().glob("migration_*.py")):
        src = path.read_text(encoding="utf-8")
        if "VISA_FIXES" not in src:
            continue
        tree = ast.parse(src, filename=str(path))
        node = _find_dict_literal_assignment(tree, "VISA_FIXES")
        if node is None:
            unparseable.append((path.name, "no module-level `VISA_FIXES = {...}` Assign found"))
            continue
        try:
            fixes = ast.literal_eval(node)
        except (ValueError, SyntaxError) as e:
            unparseable.append((path.name, f"not literal-evaluable: {e}"))
            continue
        if not isinstance(fixes, dict):
            unparseable.append((path.name, f"VISA_FIXES is a {type(fixes).__name__}, not a dict"))

    assert not unparseable, (
        "File(s) mention VISA_FIXES but the AST scan can't read it as a plain "
        "module-level dict literal, so they are INVISIBLE to every other test "
        "in this file: "
        + "; ".join(f"{name} ({reason})" for name, reason in unparseable)
        + ". Rewrite as `VISA_FIXES = {...}` (plain Assign, literal values only) "
        "to match migration_125/migration_126's convention."
    )


def test_scan_finds_the_known_migration_fixes() -> None:
    """Blindness guard (scars W82/W97): if the AST scan stops finding the
    migrations we KNOW exist on disk today (125 fixed 8 codes incl. E28F,
    126 fixes E28D), the parser broke — that must fail loudly, not pass
    green over an empty scan.
    """
    latest = _latest_migration_fix_names_by_code()
    assert len(latest) >= 8, (
        f"Only {len(latest)} migration-fixed visa code(s) found: {sorted(latest)} — "
        "expected at least 8: the 7 name-bearing codes from migration_125's 8 "
        "(E23A has allowed_activities only, no `name` key, so it isn't findable "
        "by this name-keyed scan) plus E28D from migration_126. The AST scan "
        "looks blind (VISA_FIXES shape changed, or migration files moved) — fix "
        "this test before trusting a green."
    )
    assert "E28D" in latest, "migration_126 (E28D fix) not found by the scan."
    assert "E28F" in latest, "migration_125 (E28F fix) not found by the scan."


@pytest.mark.parametrize("code", ["E28D", "E28F"])
def test_pinned_e28_sentinel_seed_matches_latest_migration(code: str) -> None:
    """Named sentinels for the two codes this incident was actually about.

    Kept explicit (not only covered by the generic sweep below) so E28D/E28F
    coverage survives even if the generic scan's parsing regresses.
    """
    seed_names = _seed_names_by_code()
    latest = _latest_migration_fix_names_by_code()

    assert code in seed_names, f"{code} missing from the seed script entirely."
    assert code in latest, (
        f"{code} has no migration_NNN_*.py VISA_FIXES correction on disk — expected "
        f"migration_125 (E28F) / migration_126 (E28D)."
    )

    seed_name = seed_names[code]
    mig_num, mig_file, mig_name = latest[code]
    assert mig_name == seed_name, (
        f"{code}: latest migration ({mig_file}, #{mig_num}) writes name="
        f"{mig_name!r}, but the seed script's canonical name is {seed_name!r}. "
        "This is the exact 'fix written in seed, never armed as migration' "
        "divergence class (CF-13/E28D) — reconcile which one is authoritative "
        "and update the other in this same PR."
    )


def test_every_migration_fixed_code_matches_the_seed_script() -> None:
    """The general form of the pinned E28 sentinels above, over every code any
    migration_NNN_*.py has ever corrected — not just E28D/E28F.

    See module docstring's DECLARED LIMIT: this only covers codes a migration
    actually touched, not the full ~150-code catalogue (that half needs a
    live-DB check, out of scope for a DB-optional unit test).

    A migration-fixed code that is entirely ABSENT from the seed catalogue is
    ALSO a hard failure here, not a silent skip. A typo'd/retired code in a
    future `VISA_FIXES` (e.g. `"E28DD"`) would UPDATE 0 rows in prod — the
    exact "wrong code, zero CI signal" shape this PR exists to close — so
    treating "not in seed" as "a different invariant, not my concern" would
    reopen the same hole one layer up. If a migration ever needs to touch a
    genuinely retired/seed-absent code on purpose, add it to
    `_KNOWN_SEED_ABSENT_CODES` below with a one-line reason — don't silently
    widen this test's blind spot.
    """
    _KNOWN_SEED_ABSENT_CODES: set[str] = set()

    seed_names = _seed_names_by_code()
    latest = _latest_migration_fix_names_by_code()

    orphans = []
    mismatches = []
    for code, (mig_num, mig_file, mig_name) in latest.items():
        seed_name = seed_names.get(code)
        if seed_name is None:
            if code not in _KNOWN_SEED_ABSENT_CODES:
                orphans.append((code, mig_file, mig_num))
            continue
        if mig_name != seed_name:
            mismatches.append((code, mig_file, mig_num, mig_name, seed_name))

    assert not orphans, (
        "Migration(s) correct a visa code that does not exist anywhere in the "
        "seed script's VISA_TYPES: "
        + "; ".join(f"{code} ({mig_file}#{mig_num})" for code, mig_file, mig_num in orphans)
        + ". Either the code is a typo (the migration silently UPDATEs 0 rows in "
        "prod), or it's a deliberately seed-absent/retired code — if the latter, "
        "add it to `_KNOWN_SEED_ABSENT_CODES` in this test with a one-line reason."
    )

    assert not mismatches, (
        "Migration-vs-seed name divergence for: "
        + "; ".join(
            f"{code} ({mig_file}#{mig_num} says {mig_name!r}, seed says {seed_name!r})"
            for code, mig_file, mig_num, mig_name, seed_name in mismatches
        )
    )
