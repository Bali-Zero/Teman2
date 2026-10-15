"""B36: the mutant table takes append-only fragments (mutants/rows/*.py), so a LocalCI PR no longer appends at the tail of the one dict.

The loader merges rows files in sorted filename order into MUTANTS and stops the run on a duplicate name or a malformed row."""
from __future__ import annotations

import ast
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
    monkeypatch.setitem(sys.modules, "merger_mutants", mod)   # what a rows file's `from merger_mutants import ...` resolves to
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "MUTANTS", dict(mod.MUTANTS))
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


REAL_ROWS = SRC.parent / "rows"


def mutates_the_table(source: str) -> list[str]:
    """What in a rows file touches MUTANTS itself: a binding, an item or attribute write, a method call, a global."""
    bad = []
    for node in ast.walk(ast.parse(source)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, (ast.AugAssign, ast.AnnAssign)) else \
            node.targets if isinstance(node, ast.Delete) else []
        for t in targets:
            base = t.value if isinstance(t, (ast.Subscript, ast.Attribute)) else t
            if isinstance(base, ast.Name) and base.id == "MUTANTS":
                bad.append(f"line {node.lineno}: writes MUTANTS")
        if isinstance(node, ast.Global) and "MUTANTS" in node.names:
            bad.append(f"line {node.lineno}: global MUTANTS")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "MUTANTS":
            bad.append(f"line {node.lineno}: MUTANTS.{node.func.attr}()")
    return bad


def test_b36_the_real_rows_directory_resolves_and_holds_a_file(mm):
    assert mm.ROWS_DIR.resolve() == REAL_ROWS.resolve() and REAL_ROWS.is_dir()
    assert list(REAL_ROWS.glob("*.py"))


def test_b36_a_plain_import_exposes_every_row_of_every_rows_file(mm):
    """What a harness that iterates MUTANTS without calling main() sees: the rows are there at import."""
    for f in sorted(REAL_ROWS.glob("[!_]*.py")):
        ns: dict = {}
        exec(compile(f.read_text(), str(f), "exec"), ns)
        assert ns["ROWS"] and set(ns["ROWS"]) <= set(mm.MUTANTS), f.name
    assert "b36-duplicate-check-dropped" in mm.MUTANTS


def test_b36_a_second_merge_is_a_no_op_and_a_real_duplicate_is_still_loud(mm, tmp_path):
    before = dict(mm.MUTANTS)
    assert mm.merge_rows() == before == mm.merge_rows()
    put(tmp_path, "z.py", f"ROWS = {{'b36-duplicate-check-dropped': {row()}}}\n")
    with pytest.raises(SystemExit, match="duplicate"):
        mm.merge_rows(tmp_path)


def test_b36_a_file_named_with_an_underscore_is_not_a_rows_file(mm, tmp_path):
    put(tmp_path, "_shared.py", "raise RuntimeError('a helper module must never be executed as rows')\n")
    put(tmp_path, "a.py", f"ROWS = {{'b36-after-helper': {row()}}}\n")
    assert "b36-after-helper" in mm.merge_rows(tmp_path)


def test_b36_the_table_cannot_be_written_from_a_rows_file():
    for src in ("MUTANTS['x'] = 1", "MUTANTS.update(ROWS)", "MUTANTS = {}", "MUTANTS |= ROWS", "del MUTANTS['x']", "global MUTANTS"):
        assert mutates_the_table(src), src
    assert not mutates_the_table("from merger_mutants import MUTANTS as M\nROWS = {n: r for n, r in M.items()}")


def test_b36_no_real_rows_file_writes_the_table():
    for f in REAL_ROWS.glob("*.py"):
        assert mutates_the_table(f.read_text()) == [], f.name
