#!/usr/bin/env python3
"""P1 STRATO-2 (2026-06-07) — falsifiable tests for mutation_incremental.py.

Locks the four load-bearing contracts of the incremental mutation driver:

  (a) changed-lines extraction from a KNOWN diff is correct (AST-aware: only
      executable statement lines, not blanks/comments/signatures);
  (b) a hidden canary mutant that a WEAK suite fails to kill → gate FAILS;
  (c) a canary that a STRONG suite kills → gate PASSES;
  (d) the driver degrades cleanly when mutmut is ABSENT (SKIP, never crash,
      never a false PASS) — and the canary self-test still runs.

These are written so that if the driver's discriminating power regresses (e.g.
someone weakens a canary or breaks the diff parser), a test goes RED.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parent / "mutation_incremental.py"


def _load():
    spec = importlib.util.spec_from_file_location("mutation_incremental", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Register in sys.modules BEFORE exec so dataclass string-annotation
    # resolution (PEP 563 / `from __future__ import annotations`) can find the
    # module's namespace; without this, @dataclass raises AttributeError.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mut():
    return _load()


# --------------------------------------------------------------------------- #
# (a) changed-lines extraction                                                #
# --------------------------------------------------------------------------- #
def test_parse_diff_added_lines_basic(mut):
    diff = (
        "diff --git a/scripts/foo.py b/scripts/foo.py\n"
        "--- a/scripts/foo.py\n"
        "+++ b/scripts/foo.py\n"
        "@@ -1,2 +1,4 @@\n"
        " import os\n"
        "+x = 1\n"
        "+y = x + 2\n"
        " print(x)\n"
    )
    added = mut.parse_diff_added_lines(diff)
    # new-side: line1 ctx(import), line2 '+x=1', line3 '+y=x+2', line4 ctx(print)
    assert added == {"scripts/foo.py": {2, 3}}


def test_parse_diff_handles_deletion_only_hunk(mut):
    diff = (
        "--- a/scripts/foo.py\n"
        "+++ b/scripts/foo.py\n"
        "@@ -1,3 +1,2 @@\n"
        " a = 1\n"
        "-b = 2\n"
        " c = 3\n"
    )
    added = mut.parse_diff_added_lines(diff)
    # a pure deletion adds NO new-side lines
    assert added == {"scripts/foo.py": set()}


def test_parse_diff_new_file(mut):
    diff = (
        "--- /dev/null\n"
        "+++ b/scripts/new.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+m = 1\n"
        "+n = 2\n"
    )
    added = mut.parse_diff_added_lines(diff)
    assert added == {"scripts/new.py": {1, 2}}


def test_executable_statement_lines_excludes_noise(mut):
    source = (
        "import os\n"  # 1 import → excluded
        "\n"  # 2 blank → excluded
        "# a comment\n"  # 3 comment → excluded
        "def f(x):\n"  # 4 signature → excluded
        '    """doc."""\n'  # 5 docstring → excluded
        "    y = x + 1\n"  # 6 assignment → KEEP
        "    return y\n"  # 7 return → KEEP
    )
    lines = mut._executable_statement_lines(source)
    assert 6 in lines
    assert 7 in lines
    assert 1 not in lines  # import
    assert 2 not in lines  # blank
    assert 3 not in lines  # comment
    assert 4 not in lines  # def signature
    assert 5 not in lines  # docstring


def test_compute_changed_target_intersects_ast(mut):
    # diff adds lines 1 (import) and 2,3 (statements) — only 2,3 are mutable.
    source = "import os\nx = os.getpid()\ny = x + 1\n"
    diff = (
        "--- a/scripts/z.py\n"
        "+++ b/scripts/z.py\n"
        "@@ -0,0 +1,3 @@\n"
        "+import os\n"
        "+x = os.getpid()\n"
        "+y = x + 1\n"
    )
    target = mut.compute_changed_target(diff, read_source=lambda p: source)
    assert target.by_file["scripts/z.py"] == frozenset({2, 3})
    assert target.total() == 2


def test_compute_changed_target_skips_non_py_and_out_of_scope(mut):
    diff = (
        "--- a/README.md\n+++ b/README.md\n@@ -0,0 +1,1 @@\n+hello\n"
        "--- a/vendor/lib.py\n+++ b/vendor/lib.py\n@@ -0,0 +1,1 @@\n+q = 1\n"
    )
    target = mut.compute_changed_target(diff, read_source=lambda p: "q = 1\n")
    # README.md not .py; vendor/ not in include_glob (apps/ scripts/ packages/)
    assert target.is_empty()


# --------------------------------------------------------------------------- #
# (b) + (c) canary anti-cheat: weak suite FAILS, strong suite PASSES          #
# --------------------------------------------------------------------------- #
def test_canary_survives_under_weak_suite_gate_fails(mut):
    """A suite too weak to catch the mutation → canary SURVIVES → must FAIL."""
    # A canary on a comparison boundary.
    canary = mut.CanaryMutant(
        id="weak_demo",
        operator="ComparisonOperatorReplacement",
        original="over = amount > threshold",
        mutated="over = amount >= threshold",
        description="boundary off-by-one",
    )
    subject = "def charge(amount, threshold):\n    over = amount > threshold\n    return over\n"
    # WEAK suite: never probes the boundary (5 vs 5), so > and >= look identical.
    weak_suite = "def run(mod):\n    assert mod.charge(9, 5) is True\n"
    results = mut.run_canary_selftest(
        subject_source=subject, suite_source=weak_suite, canaries=[canary]
    )
    assert len(results) == 1
    assert results[0].killed is False, "weak suite must let the canary SURVIVE"
    # and the reporter must translate that into a gate-fail signal
    assert mut._report_canaries(results) is False


def test_canary_killed_under_strong_suite_gate_passes(mut):
    """A suite that probes the boundary → canary KILLED → gate PASSES."""
    canary = mut.CanaryMutant(
        id="strong_demo",
        operator="ComparisonOperatorReplacement",
        original="over = amount > threshold",
        mutated="over = amount >= threshold",
        description="boundary off-by-one",
    )
    subject = "def charge(amount, threshold):\n    over = amount > threshold\n    return over\n"
    # STRONG suite: pins the exact boundary case (5 > 5 is False, 5 >= 5 is True).
    strong_suite = (
        "def run(mod):\n"
        "    assert mod.charge(5, 5) is False\n"  # this assertion breaks under >=
        "    assert mod.charge(6, 5) is True\n"
    )
    results = mut.run_canary_selftest(
        subject_source=subject, suite_source=strong_suite, canaries=[canary]
    )
    assert results[0].killed is True, "strong suite must KILL the canary"
    assert mut._report_canaries(results) is True


def test_frozen_canary_set_is_self_killing(mut):
    """The driver's OWN frozen canary set + self-test subject must all kill."""
    results = mut.run_canary_selftest()
    survived = [r for r in results if not r.killed]
    assert not survived, f"frozen canaries survived self-test (driver broken): {survived}"
    assert mut._report_canaries(results) is True


def test_canary_integrity_hash_is_deterministic_and_changes_on_tamper(mut):
    h1 = mut.canary_integrity_hash()
    h2 = mut.canary_integrity_hash()
    assert h1 == h2 and len(h1) == 64  # stable sha256
    # Tampering with a canary (weakening it) must change the pinned hash.
    tampered = list(mut._CANARY_MUTANTS)
    tampered[0] = mut.CanaryMutant(
        id=tampered[0].id,
        operator=tampered[0].operator,
        original="amount > threshold",
        mutated="amount > threshold",  # no-op mutation = weakened canary
        description="tampered",
    )
    import hashlib

    h = hashlib.sha256()
    for c in tampered:
        h.update(f"{c.id}\0{c.operator}\0{c.original}\0{c.mutated}\0".encode("utf-8"))
    assert h.hexdigest() != h1, "weakening a canary must change the integrity hash"


# --------------------------------------------------------------------------- #
# (d) graceful mutmut-absent degradation                                      #
# --------------------------------------------------------------------------- #
def test_skip_when_mutmut_absent_and_changes_present(mut, monkeypatch):
    """mutmut absent + changed lines + no --allow-skip → EXIT_SKIP, not crash/pass."""
    monkeypatch.setattr(mut, "mutmut_available", lambda: False)
    monkeypatch.setattr(
        mut,
        "git_diff",
        lambda *a, **k: (
            "--- a/scripts/z.py\n+++ b/scripts/z.py\n@@ -0,0 +1,1 @@\n+x = 1 + 2\n"
        ),
    )
    monkeypatch.setattr(mut, "compute_changed_target", lambda diff, **k: mut.ChangedLines({"scripts/z.py": frozenset({1})}))
    rc = mut.main([])
    assert rc == mut.EXIT_SKIP


def test_allow_skip_turns_skip_into_pass(mut, monkeypatch):
    monkeypatch.setattr(mut, "mutmut_available", lambda: False)
    monkeypatch.setattr(mut, "compute_changed_target", lambda diff, **k: mut.ChangedLines({"scripts/z.py": frozenset({1})}))
    monkeypatch.setattr(mut, "git_diff", lambda *a, **k: "")
    rc = mut.main(["--allow-skip"])
    assert rc == mut.EXIT_PASS


def test_no_changes_passes_without_mutmut(mut, monkeypatch):
    """Empty diff → mutmut leg not needed → PASS on canary alone."""
    monkeypatch.setattr(mut, "git_diff", lambda *a, **k: "")
    rc = mut.main([])
    assert rc == mut.EXIT_PASS


def test_surviving_canary_hard_fails_even_without_mutmut(mut, monkeypatch):
    """A broken (surviving) canary overrides skip/pass → EXIT_FAIL."""
    bad = mut.CanaryResult("broken", killed=False, detail="SURVIVED")
    monkeypatch.setattr(mut, "run_canary_selftest", lambda **k: [bad])
    monkeypatch.setattr(mut, "git_diff", lambda *a, **k: "")
    rc = mut.main([])
    assert rc == mut.EXIT_FAIL


# --------------------------------------------------------------------------- #
# survivor evaluation gate                                                     #
# --------------------------------------------------------------------------- #
def test_new_unexplained_survivor_fails(mut):
    survivors = [mut.Survivor(key="scripts/z.py#3", explanation=None)]
    ok, reasons = mut.evaluate_survivors(survivors, baseline=set())
    assert ok is False
    assert any("without explanation" in r for r in reasons)


def test_new_explained_survivor_allowed(mut):
    survivors = [mut.Survivor(key="scripts/z.py#3", explanation="log-only mutant, not behaviour")]
    ok, _ = mut.evaluate_survivors(survivors, baseline=set())
    assert ok is True


def test_baselined_survivor_allowed(mut):
    survivors = [mut.Survivor(key="scripts/z.py#3", explanation=None)]
    ok, _ = mut.evaluate_survivors(survivors, baseline={"scripts/z.py#3"})
    assert ok is True


def test_load_baseline_reads_accepted_survivors(mut, tmp_path):
    bl = tmp_path / "baseline.json"
    bl.write_text(json.dumps({"accepted_survivors": ["a#1", "b#2"]}), encoding="utf-8")
    assert mut.load_baseline(bl) == {"a#1", "b#2"}


def test_load_baseline_missing_file_is_empty(mut, tmp_path):
    assert mut.load_baseline(tmp_path / "nope.json") == set()


def test_parse_mutmut_survivors(mut, tmp_path, monkeypatch):
    monkeypatch.setattr(mut, "REPO_ROOT", tmp_path)
    stdout = "Some header\n#7 survived\n#8 killed\n#9 Survived\n"
    survivors = mut._parse_mutmut_survivors(stdout, "scripts/z.py")
    keys = {s.key for s in survivors}
    assert keys == {"scripts/z.py#7", "scripts/z.py#9"}
