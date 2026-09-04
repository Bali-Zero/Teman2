"""Guardrails for scripts/memory/recall_eval.py (the LAYER 2 recall-quality
eval bench). This bench was written months ago, lived only in an abandoned,
unmerged worktree, and rotted silently while mos_recall_sessionstart.py's API
moved on under it (MEMDIR_DEFAULT -> resolve_memdir()) with nothing to catch
the drift. These tests exist so the next API move fails loudly here instead
of rotting a bench nobody runs. Fixtures live entirely in tmp_path; nothing
under ~/.claude or the operator's real memdir is touched.
"""
from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys

import pytest

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
    """
    for name in ("recall", "format_output", "resolve_memdir"):
        assert callable(getattr(mos, name, None)), (
            f"recall_eval.py calls mos.{name}(...); it is missing or not callable "
            "on mos_recall_sessionstart -- a rename here silently rots the bench."
        )

    recall_params = set(inspect.signature(mos.recall).parameters)
    for p in ("memdir", "cache_path", "query", "topk", "use_cache"):
        assert p in recall_params, (
            f"recall_eval.py calls mos.recall(...) with a '{p}' argument; it is no "
            "longer in mos.recall's signature -- a rename here silently rots the bench."
        )

    format_output_params = set(inspect.signature(mos.format_output).parameters)
    assert "results" in format_output_params, (
        "recall_eval.py calls mos.format_output(results); 'results' is no longer in "
        "mos.format_output's signature -- a rename here silently rots the bench."
    )


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
    memdir that has real memory-file shape but none of the SCENARIOS' expected
    filenames. This does NOT assert a hit rate -- a synthetic corpus legitimately
    can't hit real expected files, so every scenario should legitimately miss. What
    it proves instead is that the bench correctly REPORTS a memdir that lacks its
    corpus (missing_expected_files has all 12 entries) rather than silently scoring
    an empty or broken run as if it were a real result.
    """
    memdir = tmp_path / "memdir"
    memdir.mkdir()
    for filename, name, desc, typ, topic in SYNTHETIC_MEMORIES:
        (memdir / filename).write_text(
            SYNTHETIC_FRONT.format(name=name, desc=desc, typ=typ, topic=topic), encoding="utf-8"
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

    assert len(report["missing_expected_files"]) == 12, (
        "synthetic memdir carries none of SCENARIOS' expected filenames; the bench "
        "must report all 12 as missing rather than silently scoring the run as if "
        "the real corpus were present."
    )


def test_the_bench_never_writes_into_the_memory_dir():
    """recall_eval.py measures the operator's REAL memories (or, in tests, a
    synthetic stand-in) and is read-only on --memdir by contract -- it may only
    write inside the scratchpad dir given via --out. A bench that ever opens a
    path derived from args.memdir in a write mode could corrupt or fabricate
    entries in the operator's actual memory corpus, which is exactly the kind of
    irreversible action this repo treats as off-limits without explicit care.
    Static-scan the source rather than the running process: cheap, and it catches
    the mistake even in a code path this test's own runs never exercise.
    """
    src_path = os.path.join(SCRIPTS_MEMORY, "recall_eval.py")
    with open(src_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for i, line in enumerate(lines, start=1):
        if "args.memdir" in line:
            assert '"w"' not in line and "open(" not in line, (
                f"recall_eval.py:{i} appears to open a path derived from args.memdir "
                "in a write mode -- the bench is READ-ONLY on MEMDIR by contract "
                "(it measures the operator's real memories) and may only write "
                "inside --out."
            )
