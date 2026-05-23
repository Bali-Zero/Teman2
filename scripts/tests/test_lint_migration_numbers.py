"""W41 (2026-05-23) — tests for lint_migration_numbers.py.

Locks the contract: the inlined find_duplicates() must produce the SAME
verdict as `backend.db.migration_manager._assert_unique_migration_numbers`.
Drift between the two would re-open the W40 class.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "lint_migration_numbers.py"


def _load_lint():
    spec = importlib.util.spec_from_file_location("lint_mignum", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def lint():
    return _load_lint()


def _mk(tmp_path: Path, *names: str) -> list[Path]:
    out: list[Path] = []
    for n in names:
        p = tmp_path / n
        p.write_text("-- empty\n")
        out.append(p)
    return out


def test_no_files_returns_empty(lint, tmp_path):
    assert lint.find_duplicates(_mk(tmp_path)) == {}


def test_unique_prefixes_clean(lint, tmp_path):
    files = _mk(tmp_path, "192_a.sql", "193_b.sql", "194_c.sql")
    assert lint.find_duplicates(files) == {}


def test_w40_collision_caught(lint, tmp_path):
    """The actual W40 case: 194_organism_incident_ledger vs 194_reconcile_107."""
    files = _mk(
        tmp_path,
        "194_organism_incident_ledger.sql",
        "194_reconcile_107_bridge_outbox_tracking.sql",
    )
    dups = lint.find_duplicates(files)
    assert 194 in dups
    assert len(dups[194]) == 2


def test_2026_04_29_legacy_pattern_caught(lint, tmp_path):
    """The original P0-7 cicatrix: dup 129 + dup 130."""
    files = _mk(
        tmp_path,
        "129_a.sql",
        "129_b.sql",
        "130_x.sql",
        "130_y.sql",
        "131_solo.sql",
    )
    dups = lint.find_duplicates(files)
    assert set(dups.keys()) == {129, 130}
    assert len(dups[129]) == 2
    assert len(dups[130]) == 2


def test_non_numeric_prefix_ignored(lint, tmp_path):
    files = _mk(tmp_path, "194_real.sql", "rollback_one.sql", "README.sql")
    assert lint.find_duplicates(files) == {}


def test_triple_collision_lists_all(lint, tmp_path):
    files = _mk(tmp_path, "200_a.sql", "200_b.sql", "200_c.sql")
    dups = lint.find_duplicates(files)
    assert 200 in dups
    assert len(dups[200]) == 3


def test_main_exits_0_on_live_repo(capsys, monkeypatch):
    """Live state should be green post-W40."""
    mod = _load_lint()
    rc = mod.main()
    captured = capsys.readouterr()
    assert rc == 0, f"live migrations_v2 has duplicate prefixes:\n{captured.out}"
    assert "all unique prefixes" in captured.out


def test_main_exits_1_on_synthetic_collision(lint, tmp_path, monkeypatch, capsys):
    """Point MIGRATIONS_DIR at a tmp_path with a duplicate."""
    _mk(tmp_path, "194_a.sql", "194_b.sql", "195_c.sql")
    monkeypatch.setattr(lint, "MIGRATIONS_DIR", tmp_path)
    rc = lint.main()
    captured = capsys.readouterr()
    assert rc == 1
    assert "duplicate prefixes" in captured.out + captured.err


def test_main_exits_0_on_synthetic_clean(lint, tmp_path, monkeypatch, capsys):
    _mk(tmp_path, "194_a.sql", "195_b.sql", "196_c.sql")
    monkeypatch.setattr(lint, "MIGRATIONS_DIR", tmp_path)
    rc = lint.main()
    captured = capsys.readouterr()
    assert rc == 0
    assert "all unique prefixes" in captured.out


def test_drift_check_vs_canonical(lint, tmp_path):
    """Contract: find_duplicates must agree with the manager's algorithm.

    We re-implement the manager's algorithm here verbatim (6 lines, the
    same as inlined in the lint script) and assert the two produce
    identical results on a stressed input set.
    """
    files = _mk(
        tmp_path,
        "1_a.sql", "2_b.sql", "2_c.sql", "10_d.sql",
        "100_e.sql", "100_f.sql", "100_g.sql",
        "weird.sql", "rollback_old.sql",
    )

    def canonical(sql_files):
        seen: dict[int, str] = {}
        duplicates: dict[int, list[str]] = {}
        for sql_file in sql_files:
            try:
                num = int(sql_file.stem.split("_")[0])
            except (ValueError, IndexError):
                continue
            if num in seen:
                duplicates.setdefault(num, [seen[num]]).append(sql_file.name)
            else:
                seen[num] = sql_file.name
        return duplicates

    assert lint.find_duplicates(files) == canonical(files)
