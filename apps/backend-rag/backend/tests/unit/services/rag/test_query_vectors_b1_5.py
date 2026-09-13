"""Tests for the B1.5 bounded embedding batch artifact
(research/operations/2026-09-11-bot-staff-room/B1-design.md §4 B1.5).

No network call anywhere in this file. The artifact these tests load is
produced by
``apps/backend-rag/backend/tests/benchmarks/evidence_sufficiency/build_query_vectors.py
--execute``, run ONLY after README queue item 7's authorization and ONLY by
the Dux — this test module never invokes ``--execute``. Until that artifact
exists on this worktree, the "loads the real artifact" test below is
SKIPPED, loudly, with a reason that says exactly why.

The harness module is loaded by file path (importlib), not by package
import, so this test does not depend on
``backend/tests/benchmarks/evidence_sufficiency`` carrying an
``__init__.py`` or being importable as ``backend.tests.benchmarks...`` —
this worktree may predate B1.3's manifest package landing on main.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

_HARNESS_DIR = Path(__file__).resolve().parents[3] / "benchmarks" / "evidence_sufficiency"
_HARNESS_FILE = _HARNESS_DIR / "build_query_vectors.py"
_ARTIFACT_PATH = _HARNESS_DIR / "query_vectors_b1_5.json"


def _load_harness() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "b1_5_build_query_vectors",
        _HARNESS_FILE,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


harness = _load_harness()


# ---------------------------------------------------------------------------
# Real artifact — skip (not fail) when it does not exist yet
# ---------------------------------------------------------------------------
def test_real_artifact_loads_and_verifies_or_is_skipped() -> None:
    if not _ARTIFACT_PATH.exists():
        pytest.fail(
            f"B1.5 artifact not present at {_ARTIFACT_PATH} — "
            "build_query_vectors.py --execute has not been run yet (it "
            "requires README queue item 7's recorded authorization and "
            "runs ONLY once, ONLY by the Dux). Skipping, not failing.",
        )

    with _ARTIFACT_PATH.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    problems = harness.verify_artifact(data, ceiling=40)
    assert not problems, f"artifact verification failed: {problems}"

    # Every vector's dimension equals the recorded dimension.
    for key, vector in data["vectors"].items():
        assert len(vector) == data["dimension"], f"{key}: dimension mismatch"

    # Mapping keys equal the recorded query list (sha256 recomputed).
    recomputed = harness.list_sha256(data["query_list"])
    assert recomputed == data["list_sha256"]
    expected_keys = {harness.mapping_key(e) for e in data["query_list"]}
    assert set(data["vectors"].keys()) == expected_keys

    # Attempts never exceed the ceiling.
    assert data["attempts_made"] <= 40


# ---------------------------------------------------------------------------
# Tiny synthetic fixture: proves the verifier rejects guilt and accepts
# innocence, independent of whether the real artifact exists.
# ---------------------------------------------------------------------------
_SYNTHETIC_QUERY_LIST = [
    {"query_lang": "EN", "query": "alpha query"},
    {"query_lang": "EN", "query": "beta query"},
    {"query_lang": "ID", "query": "gamma pertanyaan"},
]


def _make_synthetic_artifact(
    *,
    break_dimension: bool = False,
    break_mapping: bool = False,
) -> dict:
    dimension = 4
    vectors = {
        harness.mapping_key(entry): [0.1, 0.2, 0.3, 0.4]
        for entry in _SYNTHETIC_QUERY_LIST
    }
    if break_dimension:
        first_key = next(iter(vectors))
        vectors[first_key] = vectors[first_key][:-1]  # 3-dim vector, wrong
    if break_mapping:
        stolen_key = next(iter(vectors))
        vectors["NOT-A-REAL-QUERY-KEY"] = vectors.pop(stolen_key)
    return {
        "schema_version": 1,
        "synthetic": True,
        "query_list": _SYNTHETIC_QUERY_LIST,
        "list_sha256": harness.list_sha256(_SYNTHETIC_QUERY_LIST),
        "vectors": vectors,
        "model": "text-embedding-3-small",
        "dimension": dimension,
        "language_coverage": ["EN", "ID"],
        "approval_reference": "test-fixture, not a real authorization",
        "attempts_made": 3,
        "failures": [],
        "handoff": "test",
        "base_sha": "0" * 40,
        "generated_at_utc": "2026-01-01T00:00:00+00:00",
    }


def test_verify_artifact_accepts_a_correct_fixture_innocence() -> None:
    artifact = _make_synthetic_artifact()
    problems = harness.verify_artifact(artifact, ceiling=40)
    assert problems == []


def test_verify_artifact_rejects_wrong_dimension_guilt() -> None:
    artifact = _make_synthetic_artifact(break_dimension=True)
    problems = harness.verify_artifact(artifact, ceiling=40)
    assert any("dimension" in p for p in problems), problems


def test_verify_artifact_rejects_mismatched_mapping_guilt() -> None:
    artifact = _make_synthetic_artifact(break_mapping=True)
    problems = harness.verify_artifact(artifact, ceiling=40)
    assert any("mapping keys mismatch" in p for p in problems), problems


def test_verify_artifact_rejects_attempts_over_ceiling_guilt() -> None:
    artifact = _make_synthetic_artifact()
    artifact["attempts_made"] = 41
    problems = harness.verify_artifact(artifact, ceiling=40)
    assert any("exceeds ceiling" in p for p in problems), problems


# ---------------------------------------------------------------------------
# The ceiling is a TOTAL across every receipt in the evidence directory, not a
# fresh 40 per invocation. Added after the B1.5 council (Gemini 3.1 Pro,
# finding 1): the refusal to rerun keys on ONE filename, so a receipt kept
# under any other name — as ruling I24a required for the aborted attempt —
# would otherwise reset the budget to zero.
# ---------------------------------------------------------------------------
def _write(directory: Path, name: str, payload: object) -> None:
    (directory / name).write_text(json.dumps(payload), encoding="utf-8")


def test_consumed_attempts_sum_completion_and_resolution(tmp_path: Path) -> None:
    _write(tmp_path, "b1-5-precall.json", {"completion": {"attempts": 23}})
    _write(tmp_path, "b1-5-precall-aborted.json", {"resolution": {"provider_attempts": 0}})
    consumed, receipts = harness.attempts_already_consumed(tmp_path)
    assert consumed == 23
    assert len(receipts) == 2


def test_a_receipt_with_no_attempt_count_costs_the_whole_ceiling(tmp_path: Path) -> None:
    _write(tmp_path, "b1-5-precall-mystery.json", {"list_sha256": "abc"})
    consumed, receipts = harness.attempts_already_consumed(tmp_path)
    assert consumed == harness.CEILING
    assert "counted as the full ceiling" in receipts[0]


def test_an_unreadable_receipt_costs_the_whole_ceiling(tmp_path: Path) -> None:
    (tmp_path / "b1-5-precall-broken.json").write_text("{not json", encoding="utf-8")
    consumed, _ = harness.attempts_already_consumed(tmp_path)
    assert consumed == harness.CEILING


def test_an_unrelated_file_is_not_counted(tmp_path: Path) -> None:
    _write(tmp_path, "pack.yml", {"completion": {"attempts": 39}})
    consumed, receipts = harness.attempts_already_consumed(tmp_path)
    assert consumed == 0
    assert receipts == []


# ---------------------------------------------------------------------------
# A query whose provider call failed carries no vector, by design (the batch is
# never retried). Council finding 2: verify_artifact used to reject that valid
# artifact as a mapping mismatch.
# ---------------------------------------------------------------------------
def _artifact_with_one_failure() -> dict:
    query_list = [
        {"query_lang": "EN", "query": "alpha"},
        {"query_lang": "ID", "query": "beta"},
    ]
    return {
        "query_list": query_list,
        "list_sha256": harness.list_sha256(query_list),
        "vectors": {"EN::alpha": [0.0, 1.0]},
        "dimension": 2,
        "attempts_made": 2,
        "failures": [{"query_lang": "ID", "query": "beta", "error": "APITimeoutError"}],
    }


def test_a_recorded_failure_explains_its_missing_vector_innocence() -> None:
    assert harness.verify_artifact(_artifact_with_one_failure()) == []


def test_a_missing_vector_with_no_recorded_failure_is_still_a_mismatch_guilt() -> None:
    artifact = _artifact_with_one_failure()
    artifact["failures"] = []
    problems = harness.verify_artifact(artifact)
    assert any("mapping keys mismatch" in p and "ID::beta" in p for p in problems)


# ---------------------------------------------------------------------------
# Council finding (Codex, B1.5 round 1): the artifact's own list_sha256 is
# self-referential — it hashes whatever query list the harness was handed, so
# it cannot prove the queries came from the FROZEN B1.3 manifest. This derives
# the selection from the manifest on disk and compares. No network, no
# regeneration of the artifact.
# ---------------------------------------------------------------------------
_MANIFEST_PATH = _HARNESS_DIR / "manifest_mandatory.json"


def test_the_artifact_holds_exactly_the_frozen_manifests_selection() -> None:
    assert _MANIFEST_PATH.exists(), f"the frozen manifest is missing at {_MANIFEST_PATH}"
    with _MANIFEST_PATH.open("r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    expected = harness.select_queries(manifest)

    with _ARTIFACT_PATH.open("r", encoding="utf-8") as fh:
        artifact = json.load(fh)

    assert artifact["query_list"] == expected, (
        "the artifact's query list is not the selection the frozen manifest yields"
    )
    assert artifact["list_sha256"] == harness.list_sha256(expected)
    assert set(artifact["vectors"]) == {harness.mapping_key(e) for e in expected}
    assert artifact["attempts_made"] <= harness.CEILING
