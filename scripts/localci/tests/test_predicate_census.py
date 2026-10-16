"""B31'': the predicate census of the label helper is generated from the Python source and the table must match it row for row (docs/specs/localci-sovereign-2026-10-07.md)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from .fixture_repo import runner  # noqa: F401 — puts scripts/localci on sys.path like its siblings
from localci import predicate_census as pc  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]


def _mutants() -> dict:
    spec = importlib.util.spec_from_file_location("b31_mm", ROOT / "scripts/localci/tests/mutants/merger_mutants.py")
    mm = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mm
    spec.loader.exec_module(mm)
    return mm.MUTANTS


@pytest.fixture(scope="module")
def census():
    conds = pc.extract(ROOT)
    return conds, {c.key: c for c in conds}, pc.load_table()


def test_the_table_has_exactly_the_extracted_conditionals(census):
    conds, by_key, table = census
    keys = [(r["file"], r["cond"], r["occ"]) for r in table]
    assert len(keys) == len(set(keys)), "a row appears twice"
    assert not [k for k in by_key if k not in set(keys)], "a conditional has no row: run `python3 scripts/localci/predicate_census.py --draft`"
    assert not [k for k in keys if k not in by_key], "a row names a conditional that no longer exists"


def test_every_conditional_has_its_own_generated_mutant_and_the_table_names_it(census):
    conds, _, table = census
    mutants = _mutants()
    hit = pc.rows_hit_by(conds, pc.mutant_spans(mutants, ROOT))
    own = {c.key: [n for n in hit[c.key] if n.startswith("b31-ast-")] for c in conds}
    assert not [k for k, v in own.items() if len(v) != 1], "a conditional must have exactly one generated mutant"
    for r in table:
        key = (r["file"], r["cond"], r["occ"])
        assert r["mutants"] == sorted(hit[key]), f"{key}: the table is stale: run `python3 scripts/localci/predicate_census.py --draft`"
        assert own[key][0] in r["mutants"]
        for name in r["mutants"]:
            assert mutants[name][3], f"{key}: mutant {name} has no killing test file"


def test_a_generated_mutant_changes_exactly_its_conditional():
    mutants = {n: v for n, v in _mutants().items() if n.startswith("b31-ast-")}
    assert mutants
    for name, (rel, old, new, _tests) in mutants.items():
        assert (ROOT / rel).read_text().count(old) == 1 and old != new, name
        assert any(m in new for m in ("(not (", "ZeroDivisionError", "False", "next(iter(")), name


# ---- the extractor's own tests: gate-b31p's python constructs. Every atom is a row, or the extractor raises (never silent).
ATTACKS = [
    ("P01-ternary-return", "def gp1(x):\n    return 1 if x else 0\n", ["x"]),
    ("P02-any", "def gp2(prs):\n    return any(p.get('isDraft') for p in prs)\n", ["p.get('isDraft')"]),
    ("P03-all", "def gp3(prs):\n    return all(isinstance(p, dict) for p in prs)\n", ["isinstance(p, dict)"]),
    ("P04-early-return", "def gp4(prs):\n    if not prs:\n        return []\n    return prs\n", ["not prs"]),
    ("P05-try-except", "def gp5(p):\n    try:\n        return p['number']\n    except KeyError:\n        return None\n", ["KeyError"]),
    ("P06-or-assign", "def gp6(p):\n    t = p.get('title') or ''\n    return t\n", ["p.get('title')"]),
    ("P07-fstring-ifexp", "def gp7(x):\n    return f\"{'a' if x else 'b'}\"\n", ["x"]),
    ("P08-lambda-ifexp", "gp8 = lambda p: p.get('number') if p else 0\n", ["p"]),
    ("P09-match", "def gp9(p):\n    match p.get('state'):\n        case 'OPEN':\n            return True\n        case _:\n            return False\n", ["'OPEN'"]),
    ("P10-assert", "def gp10(p):\n    assert isinstance(p, dict)\n    return p\n", ["isinstance(p, dict)"]),
    ("P11-filter-lambda", "def gp11(prs):\n    return list(filter(lambda p: p.get('isDraft'), prs))\n", ["p.get('isDraft')"]),
    ("P12-return-not", "def gp12(r):\n    return not r\n", ["not r"]),
    ("P13-return-bool", "def gp13(r):\n    return bool(r)\n", ["bool(r)"]),
    ("P14-return-startswith", "def gp14(r):\n    return r.startswith(('a', 'b'))\n", ["r.startswith(('a', 'b'))"]),
    ("P15-return-isinstance", "def gp15(p):\n    return isinstance(p, dict)\n", ["isinstance(p, dict)"]),
    ("P16-suppress", "def gp16(p):\n    import contextlib\n    with contextlib.suppress(KeyError):\n        return p['number']\n    return None\n", ["KeyError"]),
    ("P17-for-else", "def gp17(xs):\n    for x in xs:\n        if x:\n            break\n    else:\n        return 0\n    return 1\n", ["x"]),
    ("P18-match-guard", "def gp18(p):\n    match p:\n        case {'n': n} if n:\n            return n\n    return 0\n", ["n"]),
    ("P19-while", "def gp19(n):\n    while n > 0:\n        n -= 1\n    return n\n", ["n > 0"]),
    ("P20-walrus", "def gp20(xs):\n    if (n := len(xs)) > 2:\n        return n\n    return 0\n", ["n"]),
    ("P21-bare-except", "def gp21(p):\n    try:\n        return p['n']\n    except:\n        return 0\n", ["except"]),
    ("P22-comparison-chain", "def gp22(a, b, c):\n    return a < b < c\n", ["a < b < c"]),
    ("P23-in-set", "def gp23(a):\n    return a in {1, 2}\n", ["a in {1, 2}"]),
    ("P24-and-or-mix", "def gp24(a, b, c):\n    return a and b or c\n", ["a and b or c", "a and b", "c"]),
    ("P25-not-in-if", "def gp25(a):\n    if not a.get('x'):\n        return 1\n    return 0\n", ["not a.get('x')"]),
    ("P26-nested-ternary", "def gp26(a, b):\n    return 1 if a else (2 if b else 3)\n", ["a", "b"]),
    ("P27-await", "async def gp27(a):\n    return await a\n", ["a"]),
    ("P28-global", "def gp28():\n    global G\n    G = 1\n", ["G"]),
    ("P29-syntax-error", "def gp29(:\n", ["x"]),
    ("Q01-for-else", "def q1(xs):\n    for x in xs:\n        pass\n    else:\n        return 0\n    return 1\n", ["x"]),
    ("Q02-while-else", "def q2(n):\n    while n:\n        n -= 1\n    else:\n        return 0\n    return 1\n", ["n"]),
    ("Q03-try-finally", "def q3(p):\n    try:\n        return p['n']\n    except KeyError:\n        return 0\n    finally:\n        pass\n", ["KeyError"]),
    ("Q04-dict-dispatch", "def q4(k):\n    d = {'a': 1, 'b': 2}\n    return d[k]\n", ["d[k]"]),
    ("Q05-bool-index", "def q5(a, b, c):\n    return [a, b][c]\n", ["c"]),
    ("Q06-min", "def q6(a, b):\n    return min(a, b)\n", ["min(a, b)"]),
    ("Q07-max", "def q7(a, b):\n    return max(a, b)\n", ["max(a, b)"]),
    ("Q08-getattr", "def q8(a):\n    return getattr(a, 'x', None)\n", ["getattr(a, 'x', None)"]),
    ("Q09-dict-literal-index", "def q9(k):\n    return {'a': 1}[k]\n", ["k"]),
    ("Q10-isnumeric", "def q10(s):\n    return s.isnumeric()\n", ["s.isnumeric()"]),
    ("Q11-try-else", "def q11(f, g):\n    try:\n        f()\n    except OSError:\n        pass\n    else:\n        g()\n", ["OSError"]),
    ("Q12-module-dict-dispatch", "D = {'a': 1}\n\n\ndef q12(k):\n    return D[k]\n", ["D[k]"]),
    ("Q13-bitwise-and", "def q13(a, b):\n    return a & b\n", ["a"]),
    ("Q14-annotation-union", "def q14(a: int | None) -> int | None:\n    return a if a else 1\n", ["a"]),
    ("P30-except-tuple", "def gp30(p):\n    try:\n        return p['n']\n    except (KeyError, ValueError):\n        return 0\n", ["(KeyError, ValueError)"]),
]


@pytest.mark.parametrize("name, src, atoms", ATTACKS, ids=[a[0] for a in ATTACKS])
def test_every_atom_of_a_construct_is_a_row_or_the_extractor_raises(name, src, atoms):
    try:
        rows = pc.extract_python(src)
    except ValueError:
        return   # loud: the right answer for a construct the census does not model
    texts = {t for t, *_ in rows}
    missing = [a for a in atoms if a not in texts]
    assert not missing, f"{name}: silent miss {missing} in {sorted(texts)}"


RAISES = {"P08-lambda-ifexp", "P09-match", "P10-assert", "P11-filter-lambda", "P16-suppress", "P17-for-else", "P18-match-guard", "P20-walrus", "P21-bare-except", "P27-await",
          "P28-global", "P29-syntax-error", "Q01-for-else", "Q02-while-else", "Q03-try-finally", "Q05-bool-index", "Q09-dict-literal-index", "Q11-try-else", "Q13-bitwise-and"}


def test_the_denied_constructs_raise_and_the_modelled_ones_do_not():
    for name, src, _ in ATTACKS:
        if name in RAISES:
            with pytest.raises(ValueError):
                pc.extract_python(src)
        else:
            assert pc.extract_python(src), name
