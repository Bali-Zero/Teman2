"""CI-safe frozen acceptance-gate test (§1.4) — pins the Phase-0 gate VERDICT so a
regression trips, WITHOUT needing the vault PDF.

The vault-gated integration test (`test_bps_crosswalk_parser.py`) proves the parser
reproduces the whole 1,559-code relation from the real PDF; this test closes the loop
CI-side by re-scoring the tracked, deterministic parser-edge fixtures against the
tracked conductor eye-read truth and asserting the same PASS the shipped
`gate_report.json` records. All inputs are tracked in-repo — no network, no PDF — so
CI (where the vault is absent) still enforces the gate rather than skipping it.

The three digests (parse artifact, holdout draw, eye-read truth) must agree: scoring a
holdout drawn under a different parse, or truth read against a different digest, is a
silent-mismatch class we refuse structurally, not by trust.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from kbli_filiera import bps_phase0_gate as gate  # noqa: E402
from kbli_filiera import holdout_truth_compile as truthmod  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PHASE0 = _REPO_ROOT / "data" / "kbli-filiera" / "phase0"
_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "holdout_edges"


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def artifact() -> dict:
    return _load(_PHASE0 / "bps_crosswalk.json")


@pytest.fixture(scope="module")
def draw_plan() -> dict:
    return _load(_PHASE0 / "holdout_draw.json")


@pytest.fixture(scope="module")
def truth() -> dict:
    return truthmod.build()


class TestDigestsAgree:
    def test_draw_matches_artifact(self, artifact, draw_plan):
        assert draw_plan["parser_run_digest"] == artifact["manifest"]["output_relation_digest"]

    def test_truth_matches_artifact(self, artifact, truth):
        assert truth["parser_run_digest"] == artifact["manifest"]["output_relation_digest"]

    def test_truth_compiler_matches_shipped_json(self, truth):
        # the tracked JSON the gate CLI consumes is exactly what the compiler emits
        shipped = _load(_PHASE0 / "holdout_truth.json")
        assert shipped == truth


class TestFrozenHoldoutScores:
    def _rescore(self, draw_plan, truth):
        pages = (draw_plan["draws"]["5"]["holdout_pdf_pages"]
                 + draw_plan["draws"]["10"]["holdout_pdf_pages"])
        truth_edges = truth["truth_edges_per_page"]
        scores = []
        for pg in sorted(pages):
            key = str(pg)
            assert key in truth_edges, f"holdout page {pg} has no eye-read truth"
            fixture = _FIXTURES / f"parser_edges_p{pg:04d}.json"
            parser_edges = {tuple(e) for e in json.loads(fixture.read_text())}
            t = {tuple(e) for e in truth_edges[key]}
            scores.append(gate.score_page(parser_edges, t))
        return gate.aggregate_scores(scores), pages

    def test_all_ten_holdout_pages_have_a_fixture(self, draw_plan):
        pages = (draw_plan["draws"]["5"]["holdout_pdf_pages"]
                 + draw_plan["draws"]["10"]["holdout_pdf_pages"])
        assert len(pages) == 10
        for pg in pages:
            assert (_FIXTURES / f"parser_edges_p{pg:04d}.json").exists()

    def test_gate_passes_precision_recall_one(self, draw_plan, truth):
        agg, _ = self._rescore(draw_plan, truth)
        assert agg["passes"] is True
        assert agg["precision"] == 1.0
        assert agg["recall"] == 1.0
        assert agg["holdout_edge_error_rate"] == 0.0
        assert agg["fp"] == 0 and agg["fn"] == 0

    def test_recomputed_verdict_matches_shipped_report(self, draw_plan, truth):
        agg, _ = self._rescore(draw_plan, truth)
        report = _load(_PHASE0 / "gate_report.json")
        assert report["verdict"] == ("PASS" if agg["passes"] else "FAIL")
        assert report["aggregate"]["precision"] == agg["precision"]
        assert report["aggregate"]["recall"] == agg["recall"]
        assert report["aggregate"]["tp"] == agg["tp"]


class TestItem10AqlDefault:
    def test_zero_error_rate_yields_tightest_aql_in_report(self):
        report = _load(_PHASE0 / "gate_report.json")
        aql = report["tier4_aql_default_item10"]
        assert aql["aql_class_percent"] == 0.010
        assert "Zero accepts-or-overrides" in aql["status"]
        # derivation is a pure function of the measured rate — re-derive and match
        assert gate.derive_tier4_aql(0.0)["aql_class_percent"] == aql["aql_class_percent"]
