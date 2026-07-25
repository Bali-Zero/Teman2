"""Unit tests for scripts/kbli_filiera/bps_phase0_gate.py — the frozen holdout
draw, edge scoring, and the item-10 AQL derivation. Pure logic, no PDF.

The load-bearing invariants: the draw is byte-reproducible from a fixed digest
(so it can be pre-registered, never cherry-picked); the stratified fill honors
the ≥3 wrapped / ≥3 N:M floors; and the AQL derivation implements the frozen
"smallest standard AQL ≥ measured error" rule, edge cases included.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from kbli_filiera import bps_phase0_gate as gate  # noqa: E402


def _pages(n, wrapped_idx=(), nm_idx=()):
    """n synthetic page strata starting at pdf_page 131; membership by index."""
    return [{"pdf_page": 131 + i, "wrapped": i in wrapped_idx, "nm": i in nm_idx,
             "edge_count": 5} for i in range(n)]


class TestPageRankKey:
    def test_deterministic(self):
        a = gate.page_rank_key("digestX", "10", 385)
        b = gate.page_rank_key("digestX", "10", 385)
        assert a == b and len(a) == 64

    def test_changes_with_digest(self):
        assert gate.page_rank_key("d1", "10", 385) != gate.page_rank_key("d2", "10", 385)

    def test_changes_with_page_and_lampiran(self):
        assert gate.page_rank_key("d", "10", 385) != gate.page_rank_key("d", "10", 386)
        assert gate.page_rank_key("d", "5", 385) != gate.page_rank_key("d", "10", 385)

    def test_zero_padded_printed_page(self):
        # printed page is zero-padded to 4 digits in the hash material (REV-4b)
        material_ok = "d:10:0017"
        import hashlib
        assert gate.page_rank_key("d", "10", 17) == hashlib.sha256(material_ok.encode()).hexdigest()


class TestRankPages:
    def test_sorted_ascending_and_stable(self):
        pages = _pages(20, wrapped_idx=range(20), nm_idx=range(20))
        r1 = gate.rank_pages(pages, "digest", "5")
        r2 = gate.rank_pages(pages, "digest", "5")
        assert [p["pdf_page"] for p in r1] == [p["pdf_page"] for p in r2]
        assert [p["rank"] for p in r1] == sorted(p["rank"] for p in r1)


class TestGreedyStratifiedDraw:
    def test_size_and_strata_floors_met_when_all_qualify(self):
        pages = _pages(30, wrapped_idx=range(30), nm_idx=range(30))
        ranked = gate.rank_pages(pages, "d", "5")
        drawn = gate.greedy_stratified_draw(ranked)
        assert len(drawn) == 10
        assert sum(p["wrapped"] for p in drawn) >= 3
        assert sum(p["nm"] for p in drawn) >= 3
        assert len({p["pdf_page"] for p in drawn}) == 10  # no page twice

    def test_scarce_strata_are_prioritized(self):
        # only 3 wrapped and 3 nm pages exist; all must be pulled into the draw
        pages = _pages(30, wrapped_idx=(0, 1, 2), nm_idx=(3, 4, 5))
        ranked = gate.rank_pages(pages, "d", "5")
        drawn = gate.greedy_stratified_draw(ranked)
        drawn_pdf = {p["pdf_page"] for p in drawn}
        assert {131, 132, 133}.issubset(drawn_pdf)  # the 3 wrapped
        assert {134, 135, 136}.issubset(drawn_pdf)  # the 3 nm
        assert len(drawn) == 10

    def test_overlap_page_counts_for_both_strata(self):
        # a single page that is BOTH wrapped and nm satisfies both floors
        pages = _pages(10, wrapped_idx=(0,), nm_idx=(0,))
        ranked = gate.rank_pages(pages, "d", "5")
        drawn = gate.greedy_stratified_draw(ranked, min_wrapped=1, min_nm=1, size=3)
        assert any(p["wrapped"] and p["nm"] for p in drawn)

    def test_fails_loud_when_wrapped_stratum_unsatisfiable(self):
        # only 2 wrapped pages exist but the floor is 3 → refuse, never under-fill
        pages = _pages(10, wrapped_idx=(0, 1), nm_idx=range(10))
        ranked = gate.rank_pages(pages, "d", "5")
        with pytest.raises(ValueError, match="stratum floor unmet"):
            gate.greedy_stratified_draw(ranked)

    def test_fails_loud_when_nm_stratum_unsatisfiable(self):
        pages = _pages(10, wrapped_idx=range(10), nm_idx=(0, 1))
        ranked = gate.rank_pages(pages, "d", "5")
        with pytest.raises(ValueError, match="stratum floor unmet"):
            gate.greedy_stratified_draw(ranked)


class TestTuningHoldoutSplit:
    def test_odd_positions_tuning_even_holdout(self):
        drawn = [{"pdf_page": p, "rank": f"{i:02d}"} for i, p in enumerate([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])]
        tuning, holdout = gate.tuning_holdout_split(drawn)
        assert [p["pdf_page"] for p in tuning] == [1, 3, 5, 7, 9]
        assert [p["pdf_page"] for p in holdout] == [2, 4, 6, 8, 10]


class TestScoring:
    def test_perfect_match(self):
        s = gate.score_page({("a", "b"), ("c", "d")}, {("a", "b"), ("c", "d")})
        assert s["tp"] == 2 and s["fp"] == 0 and s["fn"] == 0

    def test_false_positive_and_negative(self):
        s = gate.score_page({("a", "b"), ("x", "y")}, {("a", "b"), ("c", "d")})
        assert s["tp"] == 1 and s["fp"] == 1 and s["fn"] == 1

    def test_aggregate_precision_recall(self):
        agg = gate.aggregate_scores([
            {"tp": 10, "fp": 0, "fn": 0}, {"tp": 5, "fp": 1, "fn": 2},
        ])
        assert agg["tp"] == 15 and agg["fp"] == 1 and agg["fn"] == 2
        assert abs(agg["precision"] - 15 / 16) < 1e-9
        assert abs(agg["recall"] - 15 / 17) < 1e-9

    def test_pass_threshold_boundary(self):
        # both P and R exactly 0.995 passes; a hair below fails
        agg = gate.aggregate_scores([{"tp": 199, "fp": 1, "fn": 1}])
        assert agg["precision"] == 199 / 200 and agg["recall"] == 199 / 200
        assert agg["passes"] is True
        # 990/1000 = 0.990 recall < 0.995 -> fail
        assert gate.aggregate_scores([{"tp": 990, "fp": 0, "fn": 10}])["passes"] is False

    def test_vacuous_empty_holdout_does_not_pass(self):
        # zero truth edges -> precision/recall vacuously 1.0, but the evidence
        # floor forbids a PASS on no evidence (adversarial review, 2026-07-24).
        agg = gate.aggregate_scores([{"tp": 0, "fp": 0, "fn": 0}])
        assert agg["precision"] == 1.0 and agg["recall"] == 1.0
        assert agg["truth_edges"] == 0
        assert agg["passes"] is False

    def test_below_evidence_floor_does_not_pass(self):
        # a perfect but too-small holdout is not a meaningful acceptance signal
        agg = gate.aggregate_scores([{"tp": gate.MIN_HOLDOUT_TRUTH_EDGES - 1, "fp": 0, "fn": 0}])
        assert agg["precision"] == 1.0 and agg["passes"] is False

    def test_at_evidence_floor_can_pass(self):
        agg = gate.aggregate_scores([{"tp": gate.MIN_HOLDOUT_TRUTH_EDGES, "fp": 0, "fn": 0}])
        assert agg["passes"] is True


class TestDeriveTier4AQL:
    def test_zero_error_maps_to_tightest_aql(self):
        d = gate.derive_tier4_aql(0.0)
        assert d["aql_class_percent"] == 0.010
        assert d["inspection_level"] == "General Inspection Level II"
        assert d["inspection_start"] == "normal"

    def test_smallest_standard_aql_at_or_above_measured(self):
        # 0.5% measured error -> smallest standard AQL >= 0.5 is 0.65
        assert gate.derive_tier4_aql(0.005)["aql_class_percent"] == 0.65
        # 1.2% -> 1.5
        assert gate.derive_tier4_aql(0.012)["aql_class_percent"] == 1.5
        # exactly a grid point stays on it (0.10% -> 0.10)
        assert gate.derive_tier4_aql(0.001)["aql_class_percent"] == 0.10

    def test_ratification_status_is_conductor_proposed(self):
        assert "Zero accepts-or-overrides" in gate.derive_tier4_aql(0.0)["status"]
