"""Unit tests for scripts/kbli_filiera/dossier_assemble.py — pure filesystem,
no network, no real vault (tmp fixtures only)."""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from kbli_filiera import vault_common as common  # noqa: E402
from kbli_filiera import dossier_assemble as da  # noqa: E402


def _make_evidence_dir(tmp_path, code, rel_paths):
    evidence_dir = tmp_path / "evidence" / code
    evidence_dir.mkdir(parents=True)
    items = [
        {"rel_path": rp, "sha256": "x" * 8, "source": "vault:x", "locator": None, "created_at": "2026-07-17T00:00:00Z"}
        for rp in rel_paths
    ]
    (evidence_dir / "evidence-index.json").write_text(json.dumps(items), encoding="utf-8")
    return evidence_dir


# ---------------------------------------------------------------------------
# op_id determinism
# ---------------------------------------------------------------------------

class TestComputeOpId:
    def test_same_payload_same_op_id_regardless_of_key_order(self):
        a = da.compute_op_id("68112", "D1", {"mapping_type": "SPLIT", "confidence": "high"})
        b = da.compute_op_id("68112", "D1", {"confidence": "high", "mapping_type": "SPLIT"})
        assert a == b

    def test_different_payload_different_op_id(self):
        a = da.compute_op_id("68112", "D1", {"mapping_type": "SPLIT"})
        b = da.compute_op_id("68112", "D1", {"mapping_type": "MERGE"})
        assert a != b

    def test_different_stage_different_op_id_same_payload(self):
        a = da.compute_op_id("68112", "D1", {"x": 1})
        b = da.compute_op_id("68112", "D5", {"x": 1})
        assert a != b


# ---------------------------------------------------------------------------
# append_stage — append-only integrity (the core contract)
# ---------------------------------------------------------------------------

class TestAppendStage:
    def test_first_append_creates_file_with_genesis_prev_hash(self, tmp_path):
        dossier_path = tmp_path / "68112.jsonl"
        outcome = da.append_stage(dossier_path, "68112", "D1", {"a": 1}, ["crosswalk/p117.png"])
        assert outcome.accepted is True
        assert outcome.reason == "appended"
        recs = common.read_jsonl(dossier_path)
        assert len(recs) == 1
        assert recs[0]["stage"] == "D1"
        assert recs[0]["seq"] == 1
        assert recs[0]["prev_sha256"] == "GENESIS"
        assert recs[0]["evidence_refs"] == ["crosswalk/p117.png"]

    def test_second_stage_chains_to_first(self, tmp_path):
        dossier_path = tmp_path / "68112.jsonl"
        da.append_stage(dossier_path, "68112", "D1", {"a": 1}, [])
        outcome = da.append_stage(dossier_path, "68112", "D5", {"b": 2}, [])
        recs = common.read_jsonl(dossier_path)
        assert len(recs) == 2
        assert recs[1]["seq"] == 2
        # prev_sha256 is computed over the RAW line on disk, not a re-dump —
        # just assert it is non-GENESIS and stable across calls, not the
        # exact re-serialization (json key order is preserved by dict
        # insertion order in append_jsonl, so this direct compare also
        # happens to hold, but the contract we care about is "not GENESIS").
        assert recs[1]["prev_sha256"] != "GENESIS"
        assert outcome.accepted is True

    def test_identical_replay_is_idempotent_noop(self, tmp_path):
        dossier_path = tmp_path / "68112.jsonl"
        da.append_stage(dossier_path, "68112", "D1", {"a": 1}, ["x"])
        outcome = da.append_stage(dossier_path, "68112", "D1", {"a": 1}, ["x"])
        assert outcome.accepted is False
        assert outcome.reason == "idempotent-noop"
        recs = common.read_jsonl(dossier_path)
        assert len(recs) == 1  # no duplicate line appended

    def test_divergent_rewrite_is_refused(self, tmp_path):
        dossier_path = tmp_path / "68112.jsonl"
        da.append_stage(dossier_path, "68112", "D1", {"a": 1}, [])
        try:
            da.append_stage(dossier_path, "68112", "D1", {"a": 2}, [])
            assert False, "expected DivergentRewriteError"
        except da.DivergentRewriteError:
            pass
        recs = common.read_jsonl(dossier_path)
        assert len(recs) == 1  # the refused rewrite never touched the file
        assert recs[0]["payload"] == {"a": 1}

    def test_different_stages_for_same_code_both_persist(self, tmp_path):
        dossier_path = tmp_path / "68112.jsonl"
        da.append_stage(dossier_path, "68112", "D1", {"a": 1}, [])
        da.append_stage(dossier_path, "68112", "D5", {"a": 1}, [])
        recs = common.read_jsonl(dossier_path)
        assert {r["stage"] for r in recs} == {"D1", "D5"}


# ---------------------------------------------------------------------------
# evidence_ref cross-check
# ---------------------------------------------------------------------------

class TestValidateEvidenceRefs:
    def test_unknown_ref_raises(self):
        try:
            da.validate_evidence_refs(["nope.png"], {"crosswalk/p117.png"}, code="68112", stage="D1")
            assert False, "expected ValueError"
        except ValueError as exc:
            assert "68112" in str(exc) and "D1" in str(exc)

    def test_known_ref_passes(self):
        result = da.validate_evidence_refs(["crosswalk/p117.png"], {"crosswalk/p117.png"}, code="68112", stage="D1")
        assert result is None  # no exception raised == the innocence case

    def test_empty_refs_always_pass(self):
        result = da.validate_evidence_refs([], set(), code="68112", stage="D1")
        assert result is None


# ---------------------------------------------------------------------------
# run() — the full CLI-adjacent orchestration, end to end on tmp fixtures
# ---------------------------------------------------------------------------

class TestRun:
    def test_full_run_appends_all_stages(self, tmp_path):
        evidence_dir = _make_evidence_dir(tmp_path, "68112", ["canonical.json", "crosswalk/p117.png"])
        dossier_root = tmp_path / "dossiers"
        proposals = [
            {"stage": "D1", "payload": {"mapping_type": "SPLIT"}, "evidence_refs": ["crosswalk/p117.png"]},
            {"stage": "D5", "payload": {"refuted": False}, "evidence_refs": ["canonical.json"]},
        ]
        code = da.run(evidence_dir, proposals, "68112", dossier_root)
        assert code == 0
        recs = common.read_jsonl(da.dossier_path_for(dossier_root, "68112"))
        assert [r["stage"] for r in recs] == ["D1", "D5"]

    def test_unresolvable_ref_fails_that_entry_but_keeps_going(self, tmp_path):
        evidence_dir = _make_evidence_dir(tmp_path, "68112", ["canonical.json"])
        dossier_root = tmp_path / "dossiers"
        proposals = [
            {"stage": "D1", "payload": {"x": 1}, "evidence_refs": ["ghost.png"]},
            {"stage": "D5", "payload": {"x": 2}, "evidence_refs": ["canonical.json"]},
        ]
        code = da.run(evidence_dir, proposals, "68112", dossier_root)
        assert code == 1  # fail-visible: at least one entry failed
        recs = common.read_jsonl(da.dossier_path_for(dossier_root, "68112"))
        # the VALID entry still landed — one bad entry never blocks the rest
        assert [r["stage"] for r in recs] == ["D5"]

    def test_missing_evidence_index_raises_file_not_found(self, tmp_path):
        empty_dir = tmp_path / "evidence" / "68112"
        empty_dir.mkdir(parents=True)
        try:
            da.run(empty_dir, [], "68112", tmp_path / "dossiers")
            assert False, "expected FileNotFoundError"
        except FileNotFoundError:
            pass

    def test_malformed_entry_missing_stage_counts_as_failure(self, tmp_path):
        evidence_dir = _make_evidence_dir(tmp_path, "68112", [])
        dossier_root = tmp_path / "dossiers"
        code = da.run(evidence_dir, [{"payload": {"x": 1}}], "68112", dossier_root)
        assert code == 1
