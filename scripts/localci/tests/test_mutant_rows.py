"""B36: the mutant table takes append-only fragments (mutants/rows/*.py), so a LocalCI PR no longer appends at the tail of the one dict.

The loader merges rows files in sorted filename order into MUTANTS and stops the run on a duplicate name or a malformed row."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent / "mutants" / "merger_mutants.py"


@pytest.fixture
def mm(monkeypatch):
    spec = importlib.util.spec_from_file_location("merger_mutants_under_test", SRC)
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, mod)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "MUTANTS", dict(mod.MUTANTS))
    monkeypatch.delitem(sys.modules, "merger_mutants", raising=False)
    return mod


def row(tag: str = "x") -> str:
    return f'("scripts/localci/merger.py", "old-{tag}", "new-{tag}", ("scripts/localci/tests/test_merger.py",))'


def put(d: Path, fname: str, body: str) -> None:
    d.mkdir(exist_ok=True)
    (d / fname).write_text(body)


def test_b36_rows_merge_in_sorted_filename_order_after_the_inline_rows(mm, tmp_path):
    put(tmp_path, "b.py", f"ROWS = {{'b36-second': {row('2')}}}\n")
    put(tmp_path, "a.py", f"ROWS = {{'b36-first': {row('1')}}}\n")
    inline = list(mm.MUTANTS)
    got = mm.merge_rows(tmp_path)
    assert list(got) == inline + ["b36-first", "b36-second"]


def test_b36_an_absent_or_empty_rows_dir_changes_nothing(mm, tmp_path):
    before = dict(mm.MUTANTS)
    assert mm.merge_rows(tmp_path / "nope") == before
    assert mm.merge_rows(tmp_path) == before


def test_b36_a_name_in_two_rows_files_stops_the_run_naming_both(mm, tmp_path):
    put(tmp_path, "a.py", f"ROWS = {{'dup': {row()}}}\n")
    put(tmp_path, "b.py", f"ROWS = {{'dup': {row()}}}\n")
    with pytest.raises(SystemExit, match=r"b\.py.*duplicate.*'dup'.*a\.py"):
        mm.merge_rows(tmp_path)


def test_b36_a_name_already_inline_stops_the_run(mm, tmp_path):
    inline = next(iter(mm.MUTANTS))
    put(tmp_path, "a.py", f"ROWS = {{{inline!r}: {row()}}}\n")
    with pytest.raises(SystemExit, match="duplicate.*inline"):
        mm.merge_rows(tmp_path)


@pytest.mark.parametrize("bad", ["('t', 'o', 'n')", "('t', 'o', 'n', 'not-a-tuple')", "('t', 'o', 'n', ())", "('t', '', 'n', ('x',))",
                                 "('t', 'o', 3, ('x',))", "['t', 'o', 'n', ('x',)]"])
def test_b36_a_malformed_row_stops_the_run(mm, tmp_path, bad):
    put(tmp_path, "a.py", f"ROWS = {{'bad': {bad}}}\n")
    with pytest.raises(SystemExit, match="malformed"):
        mm.merge_rows(tmp_path)


def test_b36_a_file_without_a_rows_dict_stops_the_run(mm, tmp_path):
    put(tmp_path, "a.py", "ROW = {}\n")
    with pytest.raises(SystemExit, match="ROWS"):
        mm.merge_rows(tmp_path)


def test_b36_a_rows_file_may_import_the_helpers_of_the_table(mm, tmp_path):
    put(tmp_path, "a.py", f"from merger_mutants import PY, cq\nROWS = {{'b36-helper': (PY, 'o', 'n', cq('t'))}}\n")
    assert mm.merge_rows(tmp_path)["b36-helper"][0] == mm.PY


def test_b36_main_loads_the_rows_so_list_and_only_see_them(mm, tmp_path, monkeypatch, capsys):
    put(tmp_path, "a.py", f"ROWS = {{'b36-listed': {row()}}}\n")
    monkeypatch.setattr(mm, "ROWS_DIR", tmp_path)
    assert mm.main(["--list", "--only", "b36-listed"]) == 0
    assert capsys.readouterr().out.split()[0] == "b36-listed"
