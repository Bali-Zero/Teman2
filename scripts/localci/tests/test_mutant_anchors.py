"""A mutant whose anchor text no longer occurs exactly once in its target is never applied: it silently covers nothing. Every table of
every mutant sweep is held to that here, without running a single mutant, so a rename in the code fails the suite the day it lands.
Sweeps and tables are discovered, not listed: any `mutants/*_mutants.py` and any module-level dict named `*MUTANTS` is covered."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_DIR = Path(__file__).resolve().parent / "mutants"
ROOT = Path(__file__).resolve().parents[3]


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(f"{path.stem}_anchor_check", path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))   # the sweeps import `merger_mutants` by name
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(path.parent))
    return mod


def _rule(mod, label: str, value) -> tuple[str, str, str]:
    """(target file, old text, new text) from the three shapes the tables use: (file, old, new[, tests]), (old, new, tests), (old, new)."""
    if len(value) == 4 or (len(value) == 3 and isinstance(value[2], str)):
        return value[0], value[1], value[2]
    target = getattr(mod, "ANCHOR_TARGET", None)
    if target is None:
        raise AssertionError(f"{label}: rule without a file needs ANCHOR_TARGET in {mod.__name__}")
    return target, value[0], value[1]


def rules(directory: Path = _DIR) -> list[tuple[str, str, str, str, str]]:
    """(table, name, target file, old text, new text) for every rule of every table of every sweep."""
    out = []
    for path in sorted(directory.glob("*_mutants.py")):
        mod = _load(path)
        for attr in sorted(a for a in vars(mod) if a.endswith("MUTANTS") and isinstance(getattr(mod, a), dict)):
            for name, value in getattr(mod, attr).items():
                label = f"{path.stem}.{attr}:{name}"
                f, old, new = _rule(mod, label, value)
                out.append((f"{path.stem}.{attr}", name, f, old, new))
    return out


def stale(rows, root: Path) -> list[str]:
    texts: dict = {}
    bad = []
    for table, name, f, old, new in rows:
        text = texts.setdefault(f, (root / f).read_text())
        if text.count(old) != 1:
            bad.append(f"{table}:{name} — anchor occurs {text.count(old)} times in {f}, must be exactly 1")
        elif old == new:
            bad.append(f"{table}:{name} — anchor equals its replacement in {f}")
    return bad


def test_every_mutant_anchor_occurs_exactly_once_in_its_target():
    rows = rules()
    assert len({r[0] for r in rows}) >= 5 and len(rows) > 700   # the sweep was not silently emptied
    assert stale(rows, ROOT) == []


def test_the_check_names_an_anchor_that_moved_and_one_that_became_ambiguous(tmp_path):
    (tmp_path / "t.py").write_text("a = 1\nb = 2\nb = 2\n")
    rows = [("x", "gone", "t.py", "c = 3", "c = 4"), ("x", "twice", "t.py", "b = 2", "b = 3"), ("x", "once", "t.py", "a = 1", "a = 9"), ("x", "noop", "t.py", "a = 1", "a = 1")]
    bad = stale(rows, tmp_path)
    assert [s.split(" ")[0] for s in bad] == ["x:gone", "x:twice", "x:noop"]
    assert "0 times" in bad[0] and "2 times" in bad[1]


def test_a_table_added_later_is_discovered_without_a_list(tmp_path):
    (tmp_path / "new_mutants.py").write_text("ANCHOR_TARGET = 'f.py'\nMUTANTS = {'a': ('x', 'y', ('t',))}\nOTHER_MUTANTS = {'b': ('g.py', 'x', 'y')}\n")
    assert [(r[0], r[1], r[2]) for r in rules(tmp_path)] == [("new_mutants.MUTANTS", "a", "f.py"), ("new_mutants.OTHER_MUTANTS", "b", "g.py")]


def test_a_short_rule_with_no_target_fails_loudly(tmp_path):
    (tmp_path / "bad_mutants.py").write_text("MUTANTS = {'a': ('x', 'y')}\n")
    with pytest.raises(AssertionError, match="bad_mutants.MUTANTS:a.*ANCHOR_TARGET"):
        rules(tmp_path)
