"""W42 (2026-05-23) — tests for lint_migration_rollback.py.

Locks the contract: find_missing_rollback() must agree with
BaseMigration.__init__'s enforcement (number > 111 + no marker = fail).
Drift between the two would re-open the W42 class.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "lint_migration_rollback.py"


def _load_lint():
    spec = importlib.util.spec_from_file_location("lint_mig_rb", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def lint():
    return _load_lint()


def _mk(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content)
    return p


def test_post_cutoff_with_marker_clean(lint, tmp_path):
    f = _mk(tmp_path, "195_test.sql", "CREATE TABLE x();\n-- === ROLLBACK ===\nDROP TABLE x;\n")
    assert lint.find_missing_rollback([f]) == []


def test_post_cutoff_without_marker_flagged(lint, tmp_path):
    f = _mk(tmp_path, "195_test.sql", "CREATE TABLE x();\n")
    offenders = lint.find_missing_rollback([f])
    assert len(offenders) == 1
    assert offenders[0].name == "195_test.sql"


def test_pre_cutoff_without_marker_grandfathered(lint, tmp_path):
    f = _mk(tmp_path, "092_legacy.sql", "CREATE TABLE old();\n")
    assert lint.find_missing_rollback([f]) == []


def test_cutoff_boundary_111_grandfathered(lint, tmp_path):
    f = _mk(tmp_path, "111_boundary.sql", "CREATE TABLE b();\n")
    assert lint.find_missing_rollback([f]) == []


def test_cutoff_boundary_112_requires_marker(lint, tmp_path):
    f = _mk(tmp_path, "112_post_boundary.sql", "CREATE TABLE p();\n")
    offenders = lint.find_missing_rollback([f])
    assert len(offenders) == 1


def test_non_numeric_filename_ignored(lint, tmp_path):
    f = _mk(tmp_path, "README.sql", "-- documentation\n")
    assert lint.find_missing_rollback([f]) == []


def test_w37_actual_case_flagged(lint, tmp_path):
    """Reproduce the W37 195_organism_incident_ledger PRE-fix state."""
    f = _mk(
        tmp_path,
        "195_organism_incident_ledger.sql",
        "CREATE TABLE incidents (id SERIAL PRIMARY KEY);\n",
    )
    offenders = lint.find_missing_rollback([f])
    assert len(offenders) == 1
    assert "195" in offenders[0].name


def test_2d864e402_fix_state_clean(lint, tmp_path):
    """Reproduce the post-fix state with inline marker."""
    f = _mk(
        tmp_path,
        "195_organism_incident_ledger.sql",
        "CREATE TABLE incidents (id SERIAL PRIMARY KEY);\n\n"
        "-- === ROLLBACK ===\n"
        "DROP TABLE IF EXISTS incidents CASCADE;\n",
    )
    assert lint.find_missing_rollback([f]) == []


def test_marker_regex_strict(lint, tmp_path):
    """Marker must match the canonical regex.

    Note: canonical regex `^\\s*--\\s*===\\s*ROLLBACK\\s*===\\s*$` allows
    ZERO whitespace between segments (\\s* matches empty), so the form
    `--===ROLLBACK===` IS valid — it's a legal SQL comment + matches the
    pattern. We only flag truly malformed markers: missing `===`,
    lowercase, trailing tokens.
    """
    bad_variants = [
        "-- ROLLBACK\n",               # missing ===
        "-- === rollback ===\n",       # lowercase (regex is case-sensitive)
        "-- === ROLLBACK === extra\n", # trailing tokens after $
    ]
    for i, content in enumerate(bad_variants):
        f = _mk(tmp_path, f"199_bad_{i}.sql", f"CREATE TABLE x();\n{content}DROP TABLE x;\n")
        offenders = lint.find_missing_rollback([f])
        assert len(offenders) == 1, f"variant {i!r} should be flagged: {content!r}"


def test_marker_regex_accepts_zero_whitespace(lint, tmp_path):
    """Sanity: --===ROLLBACK=== (no spaces) IS accepted by canonical regex."""
    f = _mk(tmp_path, "201_zerows.sql", "CREATE TABLE x();\n--===ROLLBACK===\nDROP TABLE x;\n")
    assert lint.find_missing_rollback([f]) == []


def test_marker_regex_lenient_on_whitespace(lint, tmp_path):
    """Marker tolerates leading/trailing horizontal whitespace per canonical regex."""
    good_variants = [
        "-- === ROLLBACK ===\n",
        "  -- === ROLLBACK ===\n",   # leading spaces
        "-- === ROLLBACK ===   \n",  # trailing spaces
    ]
    for i, content in enumerate(good_variants):
        f = _mk(tmp_path, f"200_ok_{i}.sql", f"CREATE TABLE x();\n{content}DROP TABLE x;\n")
        offenders = lint.find_missing_rollback([f])
        assert offenders == [], f"variant {i!r} should be accepted: {content!r}"


def test_main_exits_0_on_live_repo(capsys):
    """Live state should be green post-2d864e402."""
    mod = _load_lint()
    rc = mod.main()
    captured = capsys.readouterr()
    assert rc == 0, f"live migrations_v2 has missing rollback markers:\n{captured.out}{captured.err}"
    assert "all have ROLLBACK marker" in captured.out


def test_main_exits_1_on_synthetic_missing(lint, tmp_path, monkeypatch, capsys):
    _mk(tmp_path, "199_synth.sql", "CREATE TABLE x();\n")
    monkeypatch.setattr(lint, "MIGRATIONS_DIR", tmp_path)
    rc = lint.main()
    captured = capsys.readouterr()
    assert rc == 1
    assert "missing" in captured.out + captured.err


def test_drift_check_vs_canonical(lint, tmp_path):
    """Contract: our regex matches BaseMigration.__init__'s regex byte-for-byte."""
    import re
    canonical = re.compile(r"^\s*--\s*===\s*ROLLBACK\s*===\s*$", re.MULTILINE)
    assert lint.ROLLBACK_MARKER_RE.pattern == canonical.pattern
    assert lint.ROLLBACK_MARKER_RE.flags == canonical.flags

    test_strings = [
        "-- === ROLLBACK ===",
        "  -- === ROLLBACK ===",
        "-- === rollback ===",
        "--===ROLLBACK===",
        "CREATE TABLE x();\n-- === ROLLBACK ===\nDROP",
    ]
    for s in test_strings:
        assert bool(lint.ROLLBACK_MARKER_RE.search(s)) == bool(canonical.search(s)), s
