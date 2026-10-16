"""B36 gate L1/L2: a rows file can only ADD names through ROWS — checked at run time, whatever alias it reached MUTANTS by — and the loader
registers the table under `merger_mutants` so that a rows file importing it also loads when the table runs as a script."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent / "mutants" / "merger_mutants.py"


@pytest.fixture
def mm(monkeypatch):
    spec = importlib.util.spec_from_file_location("merger_mutants_under_test", SRC)
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, mod)
    monkeypatch.setitem(sys.modules, "merger_mutants", mod)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "MUTANTS", dict(mod.MUTANTS))
    return mod


ROW = '("scripts/localci/merger.py", "old", "new", ("scripts/localci/tests/test_merger.py",))'
EXISTING = "pi-default-python"


def rows_file(tmp_path, body: str) -> Path:
    (tmp_path / "evil.py").write_text(body + f"\nROWS = {{'lows1-fresh': {ROW}}}\n")
    return tmp_path


# every shape the AST guard of test_mutant_rows.py misses; each overwrites a pre-existing entry
ALIAS_WRITES = {
    "assigned-alias": "import merger_mutants\nT = merger_mutants.MUTANTS\nT[{k!r}] = {r}",
    "from-import-as": "from merger_mutants import MUTANTS as M\nM[{k!r}] = {r}",
    "module-alias-attribute": "import merger_mutants as mm\nmm.MUTANTS[{k!r}] = {r}",
    "getattr": "import merger_mutants as mm\ngetattr(mm, 'MUTANTS')[{k!r}] = {r}",
    "vars": "import merger_mutants as mm\nvars(mm)['MUTANTS'][{k!r}] = {r}",
    "sys-modules": "import sys\nsys.modules['merger_mutants'].MUTANTS[{k!r}] = {r}",
    "update-through-alias": "from merger_mutants import MUTANTS as M\nM.update({{{k!r}: {r}}})",
}


@pytest.mark.parametrize("shape", list(ALIAS_WRITES), ids=list(ALIAS_WRITES))
def test_an_entry_overwritten_through_any_alias_stops_the_run_naming_the_file(mm, tmp_path, shape):
    assert EXISTING in mm.MUTANTS
    rows_file(tmp_path, ALIAS_WRITES[shape].format(k=EXISTING, r=ROW))
    with pytest.raises(SystemExit, match=r"evil\.py.*wrote MUTANTS.*changed \['pi-default-python'\]"):
        mm.merge_rows(tmp_path)


@pytest.mark.parametrize("body,what", [
    ("from merger_mutants import MUTANTS as M\nM.pop({k!r})", "removed"),
    ("from merger_mutants import MUTANTS as M\ndel M[{k!r}]", "removed"),
    ("from merger_mutants import MUTANTS as M\nM['smuggled'] = " + ROW, "added"),
], ids=["pop", "del", "smuggled-new-name"])
def test_an_entry_removed_or_added_behind_the_loader_stops_the_run(mm, tmp_path, body, what):
    rows_file(tmp_path, body.format(k=EXISTING))
    with pytest.raises(SystemExit, match=rf"evil\.py.*wrote MUTANTS.*{what} \['"):
        mm.merge_rows(tmp_path)


def test_rebinding_the_table_stops_the_run(mm, tmp_path):
    rows_file(tmp_path, "import merger_mutants as mm\nmm.MUTANTS = {}")
    with pytest.raises(SystemExit, match=r"evil\.py.*rebinds MUTANTS"):
        mm.merge_rows(tmp_path)


def test_a_write_to_the_module_table_is_seen_when_the_loader_merges_into_another_dict(mm, tmp_path):
    rows_file(tmp_path, "from merger_mutants import MUTANTS as M\nM[" + repr(EXISTING) + "] = " + ROW)
    with pytest.raises(SystemExit, match=r"evil\.py.*wrote MUTANTS"):
        mm.merge_rows(tmp_path, into={})


def test_a_normal_rows_file_still_loads_and_leaves_every_entry_as_it_was(mm, tmp_path):
    before = dict(mm.MUTANTS)
    (tmp_path / "ok.py").write_text(f"from merger_mutants import PY, MERGER_T\nREADONLY = list(__import__('merger_mutants').MUTANTS)\nROWS = {{'lows1-fresh': {ROW}}}\n")
    got = mm.merge_rows(tmp_path)
    assert got["lows1-fresh"] == eval(ROW) and all(got[k] is v for k, v in before.items()) and len(got) == len(before) + 1


def test_the_loader_registers_the_table_so_a_rows_file_can_import_it(mm, tmp_path, monkeypatch):
    monkeypatch.delitem(sys.modules, "merger_mutants")
    (tmp_path / "ok.py").write_text(f"from merger_mutants import PY\nROWS = {{'lows1-fresh': {ROW}}}\n")
    assert "lows1-fresh" in mm.merge_rows(tmp_path) and sys.modules["merger_mutants"] is mm


def test_run_as_a_script_in_isolated_mode_the_table_lists_its_rows(tmp_path):
    """`python -I merger_mutants.py --list`: the script's directory is not on sys.path, so b36.py's `from merger_mutants import ...` resolves only
    through the registration under __main__."""
    out = subprocess.run([sys.executable, "-I", str(SRC), "--list"], capture_output=True, text=True, cwd=tmp_path)
    assert out.returncode == 0, out.stderr
    assert "b36-duplicate-check-dropped" in out.stdout and EXISTING in out.stdout
