"""Guardrails for scripts/memory/recall_eval.py (the LAYER 2 recall-quality
eval bench). This bench was written months ago, lived only in an abandoned,
unmerged worktree, and rotted silently while mos_recall_sessionstart.py's API
moved on under it (MEMDIR_DEFAULT -> resolve_memdir()) with nothing to catch
the drift. These tests exist so the next API move fails loudly here instead
of rotting a bench nobody runs. Fixtures live entirely in tmp_path; nothing
under ~/.claude or the operator's real memdir is touched.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import os
import subprocess
import sys

SCRIPTS_MEMORY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "memory")
sys.path.insert(0, SCRIPTS_MEMORY)

import mos_recall_sessionstart as mos  # noqa: E402
import recall_eval  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(SCRIPTS_MEMORY))


def test_the_bench_api_surface_it_depends_on_still_exists():
    """recall_eval.py imports mos_recall_sessionstart and calls a handful of its
    names directly (mos.recall, mos.format_output, mos.resolve_memdir). This bench
    lived only in an unmerged worktree for months while that module's API moved on
    underneath it (MEMDIR_DEFAULT was renamed to resolve_memdir()) and nothing
    caught the rename until the bench was actually run again. Pin the exact
    callables and parameter names the bench calls so the next rename over there
    breaks a test HERE, loudly, instead of silently rotting an eval bench again.

    DEFECT 5: name-only pinning (checking a param name is present *somewhere* in the
    signature) is both too strict and too loose against the REAL call shape.
    run_prototype() calls `mos.recall(memdir, cache_path, query, topk=k,
    use_cache=True)` -- the first three arguments POSITIONALLY, in that order, and
    `topk`/`use_cache` as keywords. `mos.format_output(results)` passes `results`
    positionally. `resolve_memdir()` is called with zero arguments as a CLI default
    (`ap.add_argument("--memdir", default=mos.resolve_memdir())`). A signature change
    that keeps every name but makes `memdir` keyword-only, or reorders the first
    three params, would still satisfy the old name-only assertions while breaking the
    bench at runtime with a TypeError. `inspect.signature(...).bind(...)` reproduces
    the actual call shape and raises TypeError itself if it no longer fits.
    """
    for name in ("recall", "format_output", "resolve_memdir"):
        assert callable(getattr(mos, name, None)), (
            f"recall_eval.py calls mos.{name}(...); it is missing or not callable "
            "on mos_recall_sessionstart -- a rename here silently rots the bench."
        )

    recall_sig = inspect.signature(mos.recall)
    recall_param_names = list(recall_sig.parameters)
    assert recall_param_names[:3] == ["memdir", "cache_path", "query"], (
        "run_prototype() calls mos.recall(memdir, cache_path, query, ...) "
        "POSITIONALLY in that exact order; mos.recall's first three parameters "
        "are no longer (memdir, cache_path, query) in that order -- a reorder here "
        "silently rots the bench (wrong values bound to the wrong names)."
    )
    try:
        recall_sig.bind("dummy_memdir", "dummy_cache_path", "dummy_query", topk=6, use_cache=True)
    except TypeError as e:
        raise AssertionError(
            "recall_eval.py's run_prototype() calls "
            "mos.recall(memdir, cache_path, query, topk=k, use_cache=True) -- that "
            "exact call shape no longer binds against mos.recall's signature "
            f"({e}); a rename/reorder/keyword-only change here silently rots the "
            "bench."
        ) from e

    format_output_sig = inspect.signature(mos.format_output)
    try:
        format_output_sig.bind("dummy_results")
    except TypeError as e:
        raise AssertionError(
            "recall_eval.py calls mos.format_output(results) positionally; "
            f"mos.format_output's first parameter no longer accepts a positional "
            f"argument ({e}) -- a rename here silently rots the bench."
        ) from e

    try:
        inspect.signature(mos.resolve_memdir).bind()
    except TypeError as e:
        raise AssertionError(
            "recall_eval.py calls mos.resolve_memdir() with zero arguments as a "
            f"CLI default; that no longer binds ({e}) -- a new required parameter "
            "here silently rots the bench."
        ) from e


def test_the_twelve_scenario_set_matches_what_the_live_threshold_cites():
    """mos_recall_sessionstart.py:43 defines DEFAULT_RELEVANCE_THRESHOLD = 0.35 with
    the comment 'tuned against the 12-scenario eval set' -- citing THIS module's
    SCENARIOS list as the justification for a live production constant. If the count
    drifts from 12 (a scenario added/removed without re-tuning), that comment's
    stated tuning basis is silently invalidated while still reading as authoritative.
    Also guards the shape every row must have: a non-empty query string paired with
    a non-empty expected memory filename.
    """
    assert len(recall_eval.SCENARIOS) == 12, (
        "mos_recall_sessionstart.py's DEFAULT_RELEVANCE_THRESHOLD comment cites a "
        "'12-scenario eval set' as its tuning justification; SCENARIOS no longer has "
        "12 entries, so that constant's stated basis is now silently wrong."
    )
    for query, expected in recall_eval.SCENARIOS:
        assert isinstance(query, str) and query.strip()
        assert isinstance(expected, str) and expected.strip()
        assert expected.endswith(".md")


SYNTHETIC_FRONT = """---
name: {name}
description: {desc}
metadata:
  type: {typ}
---

Body text about {topic}, distinct vocabulary: {topic} {topic} {topic}.
"""

SYNTHETIC_MEMORIES = [
    ("discovery_zephyr_octagon_2026_01_01.md", "discovery-zephyr", "zephyr octagon finding", "discovery", "zephyr octagon"),
    ("decision_quokka_ledger_2026_01_02.md", "decision-quokka", "quokka ledger decision", "decision", "quokka ledger"),
    ("fact_marmalade_turbine_2026_01_03.md", "fact-marmalade", "marmalade turbine fact", "fact", "marmalade turbine"),
    ("project_ultraviolet_kayak_2026_01_04.md", "project-ultraviolet", "ultraviolet kayak project", "project", "ultraviolet kayak"),
    ("discovery_flamingo_abacus_2026_01_05.md", "discovery-flamingo", "flamingo abacus finding", "discovery", "flamingo abacus"),
    ("fact_penguin_xylophone_2026_01_06.md", "fact-penguin", "penguin xylophone fact", "fact", "penguin xylophone"),
]


def test_the_bench_runs_end_to_end_on_a_synthetic_memdir(tmp_path):
    """Full subprocess smoke test: the bench must run clean against a throwaway
    memdir that has real memory-file shape but (deliberately, for 11 of the 12
    scenarios) none of the SCENARIOS' expected filenames.

    DEFECT 1: the previous version of this test only asserted shape (exit code,
    report-file existence, its keys, "12 missing") -- never that mos.recall()
    actually ran and returned anything. Replacing run_prototype()'s body with
    `return [], 0, "", {}` still passed all of that. Plant ONE scenario's real
    expected file -- read live_query/live_expected from recall_eval.SCENARIOS at
    RUNTIME rather than hardcoding a filename here, so this stays honest if
    SCENARIOS ever changes -- with body text built from that scenario's own query
    string, so there is a genuine, high-overlap BM25 match to find. A stubbed
    run_prototype returns zero results for every scenario, which flips both
    assertions below: missing_expected_files would stay at 12 (the planted file
    would never be "found" by a dead recall) and hit_at_6 would stay at 0.
    """
    memdir = tmp_path / "memdir"
    memdir.mkdir()
    for filename, name, desc, typ, topic in SYNTHETIC_MEMORIES:
        (memdir / filename).write_text(
            SYNTHETIC_FRONT.format(name=name, desc=desc, typ=typ, topic=topic), encoding="utf-8"
        )

    live_query, live_expected = recall_eval.SCENARIOS[0]
    (memdir / live_expected).write_text(
        "---\n"
        "name: live-scenario\n"
        f"description: {live_query}\n"
        "metadata:\n"
        "  type: discovery\n"
        "---\n\n"
        f"Body text about {live_query}, distinct vocabulary: "
        f"{live_query} {live_query} {live_query}.\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    cache_path = tmp_path / "cache.json"
    proc = subprocess.run(
        [
            sys.executable,
            os.path.join(SCRIPTS_MEMORY, "recall_eval.py"),
            "--memdir", str(memdir),
            "--cache-path", str(cache_path),
            "--out", str(out_dir),
            "--skip-baseline",
        ],
        capture_output=True, text=True, timeout=60, cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, f"bench exited nonzero: stdout={proc.stdout!r} stderr={proc.stderr!r}"

    report_path = out_dir / "recall_eval_report.json"
    assert report_path.exists()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    for key in ("n_scenarios", "prototype", "missing_expected_files", "pii_findings"):
        assert key in report

    assert len(report["missing_expected_files"]) == 11, (
        "11 of SCENARIOS' 12 expected filenames are genuinely absent from this "
        "synthetic memdir; only the one planted above (SCENARIOS[0]'s expected "
        "file) is present. The bench must report exactly 11 missing -- 12 would "
        "mean the planted file was never found, which is what a dead/stubbed "
        "run_prototype() would also produce."
    )
    assert report["prototype"]["hit_at_6"] >= 1, (
        "the planted file carries genuine query-matching vocabulary for "
        "SCENARIOS[0] and should land inside the prototype's top 6; a stubbed "
        "run_prototype() (`return [], 0, \"\", {}`) returns zero results for every "
        "scenario and would leave hit_at_6 at 0 -- this is the assertion DEFECT 1 "
        "found missing."
    )
    assert report["pii_findings"] == [], (
        "DEFECT 4: the synthetic corpus carries no PII, so pii_findings must "
        "genuinely be empty, not merely present as a report key."
    )


def _write_synthetic_memdir(memdir):
    for filename, name, desc, typ, topic in SYNTHETIC_MEMORIES:
        (memdir / filename).write_text(
            SYNTHETIC_FRONT.format(name=name, desc=desc, typ=typ, topic=topic), encoding="utf-8"
        )


def _snapshot_dir(d):
    """(size, mtime_ns, sha256) per file -- strict enough to catch a content OR a
    timestamp-only mutation (e.g. an in-place re-save with identical bytes)."""
    snap = {}
    for p in sorted(d.iterdir()):
        st = p.stat()
        snap[p.name] = (st.st_size, st.st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())
    return snap


def test_the_bench_never_writes_into_the_memory_dir(tmp_path):
    """recall_eval.py measures the operator's REAL memories (or, in tests, a
    synthetic stand-in) and is read-only on --memdir by contract -- it may only
    write inside the scratchpad dir given via --out / --cache-path.

    DEFECT 3: the previous version of this test statically grepped source lines for
    `args.memdir` sitting next to `open(`/`"w"` -- that catches nothing real, because
    the actual write path is indirect: mos.recall(..., use_cache=True) calls
    build_or_refresh_index() -> save_cache(cache_path, index), and cache_path is a
    CLI flag value, never a literal expression containing the string "args.memdir"
    anywhere in this file's source. Replace the static scan with a BEHAVIOURAL one:
    snapshot every file under a synthetic memdir, run the bench for real with
    --out/--cache-path OUTSIDE it (as the contract requires), and assert the memdir
    is byte-identical afterwards with no new file added.
    """
    memdir = tmp_path / "memdir"
    memdir.mkdir()
    _write_synthetic_memdir(memdir)

    before = _snapshot_dir(memdir)

    out_dir = tmp_path / "out"
    cache_path = tmp_path / "cache.json"  # deliberately OUTSIDE memdir
    proc = subprocess.run(
        [
            sys.executable,
            os.path.join(SCRIPTS_MEMORY, "recall_eval.py"),
            "--memdir", str(memdir),
            "--cache-path", str(cache_path),
            "--out", str(out_dir),
            "--skip-baseline",
        ],
        capture_output=True, text=True, timeout=60, cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, f"bench exited nonzero: stdout={proc.stdout!r} stderr={proc.stderr!r}"

    after = _snapshot_dir(memdir)
    assert after == before, (
        "memdir contents (size/mtime/sha256) changed after a bench run that "
        "declares itself read-only on --memdir -- a genuine mutation, not just a "
        "static-scan miss."
    )
    assert set(after) == set(before), "a new file appeared inside memdir during a bench run."


def test_the_bench_refuses_a_cache_path_inside_memdir(tmp_path):
    """DEFECT 2's companion: asserts the guard added to recall_eval.py's main()
    actually fires. mos.recall(..., use_cache=True) writes an UNREDACTED cache
    (memory name/description/body preview) to --cache-path via save_cache() -- a
    --cache-path resolving inside --memdir is a concrete content leak back into the
    memory dir this bench is supposed to only measure. Without a test that exercises
    the guard end-to-end (not just reads its source), a later refactor could move the
    check after the write, or drop it, and nothing would catch it -- the same way the
    read-only contract itself rotted silently before DEFECT 3's fix.
    """
    memdir = tmp_path / "memdir"
    memdir.mkdir()
    _write_synthetic_memdir(memdir)

    out_dir = tmp_path / "out"
    bad_cache_path = memdir / ".recall_cache.json"  # INSIDE memdir -- the leak DEFECT 2 fixes
    proc = subprocess.run(
        [
            sys.executable,
            os.path.join(SCRIPTS_MEMORY, "recall_eval.py"),
            "--memdir", str(memdir),
            "--cache-path", str(bad_cache_path),
            "--out", str(out_dir),
            "--skip-baseline",
        ],
        capture_output=True, text=True, timeout=60, cwd=REPO_ROOT,
    )
    assert proc.returncode != 0, (
        "recall_eval.py must refuse to run (non-zero exit) when --cache-path "
        f"resolves inside --memdir (stdout={proc.stdout!r} stderr={proc.stderr!r})"
    )
    assert not bad_cache_path.exists(), (
        "the read-only-on-memdir guard fired too late -- a cache file was still "
        "written inside memdir before the process exited."
    )
