"""B31-prime: the predicate census is generated from the source and the table must match it row for row (docs/specs/localci-sovereign-2026-10-07.md)."""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from .fixture_repo import runner  # noqa: F401 — puts scripts/localci on sys.path like its siblings
from localci import predicate_census as pc  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]


def _mutants() -> dict:
    spec = importlib.util.spec_from_file_location("b31_mm", ROOT / "scripts/localci/tests/mutants/merger_mutants.py")
    mm = importlib.util.module_from_spec(spec)
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
    assert not [k for k in by_key if k not in set(keys)], "a conditional has no row: add a mutant or an argued equivalence"
    assert not [k for k in keys if k not in by_key], "a row names a conditional that no longer exists"


def test_every_row_names_a_mutant_that_changes_its_text_or_argues_an_equivalence(census):
    conds, by_key, table = census
    mutants = _mutants()
    hit = pc.rows_hit_by(conds, pc.mutant_spans(mutants, ROOT))
    for r in table:
        key = (r["file"], r["cond"], r["occ"])
        if r.get("mutants"):
            for name in r["mutants"]:
                assert name in mutants and name.startswith("b31-"), f"{key}: unknown mutant {name}"
                assert name in hit[key], f"{key}: mutant {name} does not change this conditional"
                assert mutants[name][3], f"{key}: mutant {name} has no killing test file"
        else:
            assert len(r.get("equivalent", "")) >= 60, f"{key}: no mutant and no argued equivalence"


def test_the_table_is_what_the_sources_and_the_mutants_say_today(census):
    """The generator is the author of the mutant lists: a hand-edited list that drifted from the mutants' real positions fails here."""
    conds, _, table = census
    drafted = {(r["file"], r["cond"], r["occ"]): r["mutants"] for r in pc.draft(_mutants())}
    for r in table:
        key = (r["file"], r["cond"], r["occ"])
        assert r.get("mutants", []) == drafted[key], f"{key}: run `python3 scripts/localci/predicate_census.py --draft`"


def test_the_extractor_sees_each_construct():
    sh = pc.extract_bash('''
case "$X" in ''|*[!0-9]*|0) A=1 ;; esac
if [ "$a" = 1 ] && ! grep -q x; then b=${V:-d}; fi
[ "$r" -eq 0 ] || [ "$r" -eq 1 ] && break
for ((i = 1; i <= N; i++)); do :; done
while [ "$k" -lt 3 ]; do :; done
# if this comment is not a conditional && neither is this
x=1 # nor this || that
''')
    texts = [(t, k) for t, _s, _e, k in sh]
    assert ('case "$X" in \'\'', "case-arm") in texts and ('case "$X" in *[!0-9]*', "case-arm") in texts and ('case "$X" in 0', "case-arm") in texts
    assert ('[ "$a" = 1 ] && ! grep -q x', "if") in texts and ('[ "$a" = 1 ]', "if-operand") in texts and ("${V:-d}", "default") in texts
    assert ('[ "$r" -eq 0 ]', "chain") in texts and ('[ "$r" -eq 1 ]', "chain") in texts and ("break", "chain") in texts
    assert ("i <= N", "for") in texts and ('[ "$k" -lt 3 ]', "while") in texts
    assert not [t for t, _ in texts if "comment" in t or "nor this" in t]


def test_the_extractor_sees_each_python_construct():
    py = pc.extract_python("def f(a, b):\n    if a and not b:\n        return [x for x in a if x]\n    return a or {}\n")
    texts = {t for t, *_ in py}
    assert {"a and not b", "a", "not b", "x", "a or {}"} <= texts and "{}" not in texts


def test_a_conditional_looking_line_the_extractor_cannot_parse_is_an_error_not_a_silence():
    with pytest.raises(ValueError):
        pc.extract_bash("if [ \"$a\" = 1 ] \\\n  && [ \"$b\" = 2 ]; then :; fi\n")


def test_every_scope_file_is_covered_by_the_hosted_workflow_filter():
    import yaml
    wf = yaml.safe_load((ROOT / ".github/workflows/localci-tests.yml").read_text())
    paths = (wf.get("on") or wf.get(True))["pull_request"]["paths"]
    inputs = {rel for rel, *_ in pc.SCOPE} | {"scripts/merge_queue_rule.sh", "scripts/tests/test_signal_merge_intent.sh",
                                              "apps/bali-intel-scraper/scripts/post_publish_poller.py", "scripts/ci/queue_rearm_population.sh"}
    uncovered = [f for f in sorted(inputs) if not any(f == p or (p.endswith("/**") and f.startswith(p[:-2])) for p in paths)]
    assert not uncovered, uncovered
