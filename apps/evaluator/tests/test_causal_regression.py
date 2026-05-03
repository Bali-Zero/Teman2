"""Tests for the causal regression harness.

Covers:
  * commit_walker on a synthetic 5-commit repo
  * causal_diff classification on hand-crafted snapshots
  * report generator HTML sections and JSON schema
  * end-to-end CLI run on the real worktree
  * determinism (two runs -> byte-identical JSON)
  * binary KB file graceful skip
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterator

import pytest

from apps.evaluator.causal_regression._types import (
    CausalDiff,
    CommitSnapshot,
    QueryResult,
    RetrievedChunk,
    RootCause,
)
from apps.evaluator.causal_regression.causal_diff import diff_snapshots
from apps.evaluator.causal_regression.commit_walker import walk_range
from apps.evaluator.causal_regression.regression_report import (
    ReportInputs,
    build_html,
    build_json,
    write_report,
)
from apps.evaluator.causal_regression.replay_engine import (
    EvalRow,
    reconstruct_kb,
    run_eval_set,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).parent / "fixtures" / "causal"


def _git(args: list[str], cwd: Path) -> None:
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "Causal Test"
    env["GIT_AUTHOR_EMAIL"] = "causal@test.local"
    env["GIT_COMMITTER_NAME"] = "Causal Test"
    env["GIT_COMMITTER_EMAIL"] = "causal@test.local"
    subprocess.run(["git", *args], cwd=str(cwd), check=True, env=env, capture_output=True)


@pytest.fixture
def synth_repo(tmp_path: Path) -> Iterator[Path]:
    """A throwaway git repo with 5 commits touching a fake KB."""
    repo = tmp_path / "synth"
    repo.mkdir()
    _git(["init", "-q", "-b", "main"], repo)
    kb = repo / "apps" / "backend-rag" / "backend" / "kb" / "visa"
    kb.mkdir(parents=True)

    # Commit 1: initial KB with two docs
    (kb / "kitas.md").write_text("# kitas\nKITAS is a residence permit for expats.\n")
    (kb / "bpjs.md").write_text("# bpjs\nBPJS kesehatan applies to expats with KITAS.\n")
    _git(["add", "."], repo)
    _git(["commit", "-q", "-m", "initial kb"], repo)

    # Commit 2: add a new noise doc
    (kb / "visa_news.md").write_text("# news\nSome unrelated news about telex and permits.\n")
    _git(["add", "."], repo)
    _git(["commit", "-q", "-m", "add noise doc"], repo)

    # Commit 3: edit kitas.md
    (kb / "kitas.md").write_text("# kitas\nKITAS overview without the keyword residence.\n")
    _git(["add", "."], repo)
    _git(["commit", "-q", "-m", "edit kitas content"], repo)

    # Commit 4: remove bpjs.md
    (kb / "bpjs.md").unlink()
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "remove bpjs doc"], repo)

    # Commit 5: change a retriever config file
    cfg_dir = repo / "apps" / "backend-rag" / "backend" / "services" / "rag"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "hybrid_search.py").write_text("TOP_K = 5\n")
    _git(["add", "."], repo)
    _git(["commit", "-q", "-m", "tweak retriever"], repo)

    yield repo


def test_commit_walker_5commit_synthetic(synth_repo: Path) -> None:
    snaps = walk_range("HEAD~4..HEAD", str(synth_repo))
    assert len(snaps) == 4, "range excludes the very first commit by construction"
    # Order is oldest-first
    assert [s.order_index for s in snaps] == [0, 1, 2, 3]

    # Commit with added noise
    add_snap = next(s for s in snaps if "noise" in s.subject)
    assert any("visa_news.md" in p for p in add_snap.added_kb_files)

    # Commit with edit
    edit_snap = next(s for s in snaps if "edit kitas" in s.subject)
    assert any("kitas.md" in p for p in edit_snap.changed_kb_files)

    # Commit with removal
    rm_snap = next(s for s in snaps if "remove bpjs" in s.subject)
    assert any("bpjs.md" in p for p in rm_snap.removed_kb_files)

    # Commit with retriever cfg
    cfg_snap = next(s for s in snaps if "retriever" in s.subject)
    assert cfg_snap.changed_retriever_cfg, "retriever cfg must be flagged"


def _mk_snapshot(
    sha: str,
    *,
    added: list[str] = None,
    removed: list[str] = None,
    changed: list[str] = None,
    prompts: list[str] = None,
    retriever: list[str] = None,
    llm: list[str] = None,
    order: int = 0,
) -> CommitSnapshot:
    return CommitSnapshot(
        sha=sha,
        short_sha=sha[:7],
        parent_sha=None,
        subject=f"test {sha}",
        order_index=order,
        added_kb_files=added or [],
        removed_kb_files=removed or [],
        changed_kb_files=changed or [],
        changed_prompts=prompts or [],
        changed_retriever_cfg=retriever or [],
        changed_llm_cfg=llm or [],
    )


def _mk_result(
    sha: str,
    qid: str,
    *,
    hits: list[tuple[str, float, int]],
    expected: list[str],
    covered: list[str],
    passed: bool,
) -> QueryResult:
    top_k = [
        RetrievedChunk(doc_path=p, score=s, rank=r, snippet=f"snippet for {p}")
        for (p, s, r) in hits
    ]
    coverage = len(covered) / max(len(expected), 1)
    return QueryResult(
        commit_sha=sha,
        query_id=qid,
        query="q",
        expected_keywords=expected,
        top_k=top_k,
        covered_keywords=covered,
        coverage=coverage,
        passed=passed,
    )


def test_causal_diff_classifies_added_noise() -> None:
    prev = _mk_snapshot("a" * 40, order=0)
    curr = _mk_snapshot(
        "b" * 40,
        added=["apps/backend-rag/backend/kb/noise.md"],
        order=1,
    )
    prev_res = [
        _mk_result(
            "a" * 40,
            "Q1",
            hits=[("kitas.md", 5.0, 1)],
            expected=["kitas", "permit"],
            covered=["kitas", "permit"],
            passed=True,
        )
    ]
    curr_res = [
        _mk_result(
            "b" * 40,
            "Q1",
            hits=[
                ("apps/backend-rag/backend/kb/noise.md", 8.0, 1),
                ("kitas.md", 2.0, 2),
            ],
            expected=["kitas", "permit"],
            covered=[],
            passed=False,
        )
    ]
    diffs = diff_snapshots(prev, curr, prev_res, curr_res)
    assert len(diffs) == 1
    d = diffs[0]
    assert d.prev_passed and not d.curr_passed
    assert d.root_cause == RootCause.KB_ADDED_NOISE
    # retrieval_delta contains the new doc and the movement of kitas
    paths = [m["doc_path"] for m in d.retrieval_delta]
    assert "apps/backend-rag/backend/kb/noise.md" in paths
    assert "kitas.md" in paths


def test_causal_diff_classifies_kb_removed() -> None:
    prev = _mk_snapshot("c" * 40, order=0)
    curr = _mk_snapshot(
        "d" * 40,
        removed=["apps/backend-rag/backend/kb/bpjs.md"],
        order=1,
    )
    prev_res = [
        _mk_result(
            "c" * 40,
            "Q2",
            hits=[("apps/backend-rag/backend/kb/bpjs.md", 5.0, 1)],
            expected=["bpjs", "kesehatan"],
            covered=["bpjs", "kesehatan"],
            passed=True,
        )
    ]
    curr_res = [
        _mk_result(
            "d" * 40,
            "Q2",
            hits=[],
            expected=["bpjs", "kesehatan"],
            covered=[],
            passed=False,
        )
    ]
    diffs = diff_snapshots(prev, curr, prev_res, curr_res)
    assert diffs[0].root_cause == RootCause.KB_REMOVED


def test_report_generator_html_has_required_sections(tmp_path: Path) -> None:
    snap_a = _mk_snapshot("a" * 40, order=0)
    snap_b = _mk_snapshot(
        "b" * 40, added=["apps/backend-rag/backend/kb/noise.md"], order=1
    )
    prev_res = _mk_result(
        "a" * 40,
        "Q1",
        hits=[("kitas.md", 5.0, 1)],
        expected=["kitas"],
        covered=["kitas"],
        passed=True,
    )
    curr_res = _mk_result(
        "b" * 40,
        "Q1",
        hits=[
            ("apps/backend-rag/backend/kb/noise.md", 8.0, 1),
            ("kitas.md", 2.0, 2),
        ],
        expected=["kitas"],
        covered=[],
        passed=False,
    )
    diffs = diff_snapshots(snap_a, snap_b, [prev_res], [curr_res])
    inputs = ReportInputs(
        range_expr="a..b",
        snapshots=[snap_a, snap_b],
        results=[prev_res, curr_res],
        diffs=diffs,
        warnings=[],
        kb_root="apps/backend-rag/backend/kb",
    )
    html = build_html(inputs)
    assert '<table class="flamegraph">' in html
    assert '<div class="legend">' in html
    assert "KB_ADDED_NOISE" in html
    assert "Top regressions" in html

    paths = write_report(inputs, tmp_path)
    assert paths["json"].exists()
    assert paths["html"].exists()
    # JSON parses cleanly
    data = json.loads(paths["json"].read_text())
    assert data["metadata"]["range"] == "a..b"
    assert data["top_regressions"][0]["root_cause"] == "KB_ADDED_NOISE"


def test_build_json_is_deterministic() -> None:
    snap_a = _mk_snapshot("a" * 40, order=0)
    snap_b = _mk_snapshot(
        "b" * 40, added=["apps/backend-rag/backend/kb/noise.md"], order=1
    )
    prev_res = _mk_result(
        "a" * 40, "Q1", hits=[("x.md", 5.0, 1)],
        expected=["x"], covered=["x"], passed=True,
    )
    curr_res = _mk_result(
        "b" * 40, "Q1",
        hits=[("apps/backend-rag/backend/kb/noise.md", 8.0, 1), ("x.md", 2.0, 2)],
        expected=["x"], covered=[], passed=False,
    )
    diffs = diff_snapshots(snap_a, snap_b, [prev_res], [curr_res])
    inputs = ReportInputs(
        range_expr="a..b",
        snapshots=[snap_a, snap_b],
        results=[prev_res, curr_res],
        diffs=diffs,
        warnings=[],
        kb_root="apps/backend-rag/backend/kb",
    )
    a = json.dumps(build_json(inputs), sort_keys=True)
    b = json.dumps(build_json(inputs), sort_keys=True)
    assert a == b
    # No timestamp keys
    assert "timestamp" not in a
    assert "generated_at" not in a


def test_binary_kb_file_skipped_with_warning(synth_repo: Path, tmp_path: Path) -> None:
    # Add a fake binary KB file
    kb = synth_repo / "apps" / "backend-rag" / "backend" / "kb" / "visa"
    (kb / "scan.png").write_bytes(b"\x89PNG\x00\x00\x00\x00fake binary data")
    _git(["add", "-A"], synth_repo)
    _git(["commit", "-q", "-m", "add binary kb file"], synth_repo)

    snaps = walk_range("HEAD~1..HEAD", str(synth_repo))
    assert len(snaps) == 1
    snap = snaps[0]
    docs, warnings = reconstruct_kb(
        snap.sha,
        str(synth_repo),
        "apps/backend-rag/backend/kb",
        cache_root=tmp_path / "cache",
    )
    # The binary is skipped but not fatal
    assert any("binary_skipped" in w and "scan.png" in w for w in warnings)
    assert "apps/backend-rag/backend/kb/visa/scan.png" not in docs


def test_replay_retriever_finds_expected_chunks(
    synth_repo: Path, tmp_path: Path
) -> None:
    # HEAD has: kitas.md edited to omit "residence", bpjs.md removed
    shas = walk_range("HEAD~4..HEAD", str(synth_repo))
    first = shas[0]  # "initial kb" — kitas.md has "residence"
    eval_rows = [
        EvalRow(
            query_id="Q1",
            query="What is a KITAS permit",
            expected_keywords=["kitas", "residence"],
        )
    ]
    results, warnings = run_eval_set(
        first,
        eval_rows,
        repo=str(synth_repo),
        kb_root="apps/backend-rag/backend/kb",
        cache_root=tmp_path / "cache",
    )
    assert results[0].passed, f"initial commit should pass: {results[0].to_dict()}"
    assert "residence" in results[0].covered_keywords


def _run_cli(argv: list[str], repo: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    return subprocess.run(
        [sys.executable, "-m", "apps.evaluator.causal_regression", *argv],
        cwd=str(repo),
        env=env,
        capture_output=True,
        text=True,
    )


def test_e2e_cli_on_real_repo(tmp_path: Path) -> None:
    """End-to-end: invoke the CLI against the real worktree.

    Uses `--path-filter=""` so the test is robust to whichever subset of
    recent commits touch backend-rag — it simply walks the last five
    commits unconditionally and runs the full pipeline.
    """
    out_dir = tmp_path / "out"
    eval_set = FIXTURES / "eval_tiny.jsonl"
    result = _run_cli(
        [
            "--range",
            "HEAD~5..HEAD",
            "--eval-set",
            str(eval_set),
            "--out",
            str(out_dir),
            "--kb-root",
            "apps/backend-rag/backend/kb",
            "--path-filter",
            "",
            "--quiet",
        ],
        REPO_ROOT,
    )
    assert result.returncode == 0, f"stderr={result.stderr}"
    assert (out_dir / "causal_report.json").exists()
    assert (out_dir / "causal_report.html").exists()
    data = json.loads((out_dir / "causal_report.json").read_text())
    assert data["metadata"]["range"] == "HEAD~5..HEAD"
    # We expect at least 1 snapshot (range with only 1 commit is valid)
    assert data["metadata"]["commit_count"] >= 1


def test_e2e_determinism_two_runs(tmp_path: Path) -> None:
    """Two identical CLI runs must produce byte-identical JSON."""
    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"
    eval_set = FIXTURES / "eval_tiny.jsonl"
    common = [
        "--range",
        "HEAD~5..HEAD",
        "--eval-set",
        str(eval_set),
        "--kb-root",
        "apps/backend-rag/backend/kb",
        "--path-filter",
        "",
        "--quiet",
    ]
    r1 = _run_cli([*common, "--out", str(out1)], REPO_ROOT)
    r2 = _run_cli([*common, "--out", str(out2)], REPO_ROOT)
    assert r1.returncode == 0
    assert r2.returncode == 0
    a = (out1 / "causal_report.json").read_bytes()
    b = (out2 / "causal_report.json").read_bytes()
    assert a == b, "JSON output must be byte-identical across runs"
