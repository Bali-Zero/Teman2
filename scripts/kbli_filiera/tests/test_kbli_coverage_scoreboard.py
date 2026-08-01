"""Tests for the completion scoreboard and its one-way ratchet.

Guilt + innocence per scar #3, on tiny synthetic fixtures (pure-stdlib, no 37 MB
canonical — the real dataset is exercised by the workflow's `--check` step, not
by unit tests).

The innocence cases carry most of the weight here. A coverage gate that
mis-classifies an honest state as a defect gets muted within a week, and a muted
gate is worse than no gate (family #2) — so every honest state gets a test that
proves it does NOT count against the score.

Note what is deliberately NOT asserted: any specific coverage number for the live
catalogue. A test that pins "PMA is at 15/1559" would go red the day F2 improves
it, i.e. it would punish exactly the work it exists to encourage — the mirror of
"a guard whose guilt depends on production still being broken" (corner §1 L2.4).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

FILIERA = Path(__file__).resolve().parents[1]
if str(FILIERA) not in sys.path:
    sys.path.insert(0, str(FILIERA))

import _coverage_basis as B  # noqa: E402
import kbli_coverage_scoreboard as S  # noqa: E402


def rec(code: str, **kwargs) -> dict:
    base = {B.CODE_FIELD: code, "per_skala": [], "pma_status": "TERBUKA"}
    base.update(kwargs)
    return base


# --------------------------------------------------------------------------
# LICENSING axis
# --------------------------------------------------------------------------


def test_guilt_licensing_rows_without_a_named_source_are_bare():
    """THE defect: permit rows asserted to a client with nothing on the record
    saying where they came from."""
    assert B.classify_licensing(rec("99999", per_skala=[{"skala_usaha": "Besar"}])) == B.LIC_BARE


def test_innocence_oss_2025_rows_are_sourced():
    record = rec("01111", per_skala=[{"skala_usaha": "Besar"}], _l2_source=B.OSS_2025_SOURCE)
    assert B.classify_licensing(record) == B.LIC_SOURCED_OSS_2025


def test_innocence_detached_rows_are_a_declared_gap_not_a_defect():
    """`per_skala == []` is this programme's honesty primitive. Scoring it as a
    defect would make every cured code look like a regression."""
    assert B.classify_licensing(rec("68112", per_skala=[])) == B.LIC_DECLARED_GAP


def test_innocence_pp28_rows_are_located_but_flagged_vintage_pending():
    """The 5 Batch-A codes that kept their PP28 rows: the source IS named, so
    they are not bare — but they must never be conflated with the 2025-native
    class, because PP28 is KBLI-2020 vintage."""
    record = rec("93111", per_skala=[{"skala_usaha": "Besar"}], _l2_status=B.NO_OSS_RISK, pp28_sources=["93111"])
    assert B.classify_licensing(record) == B.LIC_SOURCED_PP28_VINTAGE_PENDING


def test_guilt_no_oss_rows_without_pp28_sources_are_bare():
    """Innocence's twin: `no_oss_risk` alone does not confer provenance — a row
    kept with NO source named at all is still bare."""
    record = rec("93111", per_skala=[{"skala_usaha": "Besar"}], _l2_status=B.NO_OSS_RISK, pp28_sources=[])
    assert B.classify_licensing(record) == B.LIC_BARE


def test_guilt_unrecognised_l2_source_does_not_earn_provenance():
    """EXACT match, never substring: a marker nobody has vetted must fall
    through to bare rather than be granted a vintage it did not earn."""
    record = rec("01111", per_skala=[{"skala_usaha": "Besar"}], _l2_source="OSS_RBA_resiko_2025_DRAFT")
    assert B.classify_licensing(record) == B.LIC_BARE


# --------------------------------------------------------------------------
# PMA axis
# --------------------------------------------------------------------------


def test_guilt_pma_verdict_without_a_basis_is_bare():
    assert B.classify_pma(rec("01111", pma_max_asing=100)) == B.PMA_BARE


def test_innocence_pma_with_official_basis_is_located():
    record = rec("50111", pma_official_basis="Perpres 10/2021 Lampiran III line 4202")
    assert B.classify_pma(record) == B.PMA_LOCATED


def test_innocence_pma_declared_unverified_is_honest():
    """A record that says "we have not verified this cap" is honest by this
    programme's own definition of DONE, even though it has no locator."""
    assert B.classify_pma(rec("02101", pma_cap_verified=False)) == B.PMA_DECLARED_UNVERIFIED


def test_basis_outranks_a_stale_unverified_flag():
    record = rec("50122", pma_official_basis="Perpres 10/2021 Lampiran III", pma_cap_verified=False)
    assert B.classify_pma(record) == B.PMA_LOCATED


def test_guilt_blank_basis_string_is_not_a_basis():
    assert B.classify_pma(rec("01111", pma_official_basis="   ")) == B.PMA_BARE


def test_the_layer_wide_pma_source_string_never_confers_provenance():
    """`pma_source` reads the same on all 1,559 records, so it is a layer
    annotation and can never explain a per-code verdict — the shape that made
    `moratorium.rule` useless as evidence on 111 pages."""
    record = rec("01111", pma_source="Perpres 10/2021, 49/2021", pma_max_asing=100)
    assert B.classify_pma(record) == B.PMA_BARE


# --------------------------------------------------------------------------
# CROSSWALK axis
# --------------------------------------------------------------------------


def test_innocence_mechanical_ancestor_with_a_locator_is_located():
    record = rec(
        "01111",
        bps_2020_ancestors={
            "codes": ["01111"],
            "source_locator": [{"lampiran": 10, "printed_page": 311}],
            "inheritance_verdict": "not-adjudicated",
        },
    )
    assert B.classify_crosswalk(record) == B.XW_LOCATED
    assert B.crosswalk_is_adjudicated(record) is False


def test_guilt_ancestor_claim_without_a_locator_is_not_located():
    """Ancestor codes alone are a claim; the lampiran reference is what makes
    the claim checkable."""
    record = rec("01111", bps_2020_ancestors={"codes": ["01111"], "source_locator": []})
    assert B.classify_crosswalk(record) == B.XW_ABSENT


def test_innocence_explicit_no_ancestor_marker_is_a_declared_gap():
    record = rec("01287", bps_2020_ancestors={"no_ancestor_recorded": True})
    assert B.classify_crosswalk(record) == B.XW_DECLARED_GAP


def test_adjudicated_submetric_counts_only_real_verdicts():
    adjudicated = rec(
        "01111",
        bps_2020_ancestors={"source_locator": [{"lampiran": 10}], "inheritance_verdict": "transfers"},
    )
    assert B.crosswalk_is_adjudicated(adjudicated) is True


# --------------------------------------------------------------------------
# scoreboard assembly
# --------------------------------------------------------------------------


def test_every_record_lands_in_exactly_one_state_per_axis():
    """An invisible population is how a selector hides a defect. The builder
    asserts honest + defect == total; this proves the assertion is live."""
    records = [
        rec("01111", per_skala=[{"x": 1}], _l2_source=B.OSS_2025_SOURCE),
        rec("68112"),
        rec("99999", per_skala=[{"x": 1}]),
    ]
    board = S.build_scoreboard(records)
    for axis in board["axes"].values():
        assert axis["honest"] + axis["defect"] == 3
    assert board["axes"]["licensing"]["defect_codes"] == ["99999"]


def test_build_scoreboard_refuses_a_mismatched_partition():
    """If a future edit adds a state to a classifier but forgets to declare
    whether it is honest, the builder must raise rather than quietly score it."""
    original = B.AXES["licensing"]
    S.AXES["licensing"] = (lambda r: "a_state_nobody_declared", frozenset())
    try:
        board = S.build_scoreboard([rec("01111")])
        # Undeclared states are counted as defects, never silently dropped.
        assert board["axes"]["licensing"]["defect"] == 1
    finally:
        S.AXES["licensing"] = original


# --------------------------------------------------------------------------
# the ratchet
# --------------------------------------------------------------------------


def _board(honest: int, defect: int, codes: list[str]) -> dict:
    return {
        "total_codes": honest + defect,
        "axes": {"pma": {"total": honest + defect, "honest": honest, "defect": defect, "states": {}, "defect_codes": codes}},
    }


def test_guilt_ratchet_fires_when_honest_coverage_falls():
    problems = S.ratchet_regressions(_board(10, 5, ["a"]), _board(12, 3, []))
    assert problems and "honest coverage fell" in problems[0]


def test_guilt_ratchet_fires_when_a_bare_fact_appears():
    """Honest coverage is held CONSTANT so this asserts the bare-count arm on
    its own — a fixture that moves both dimensions proves neither."""
    problems = S.ratchet_regressions(_board(10, 2, ["x", "y"]), _board(10, 1, ["x"]))
    assert len(problems) == 1, problems
    assert "bare facts rose" in problems[0]
    assert "y" in problems[0], "the report must name what became bare"


def test_innocence_ratchet_is_silent_on_improvement():
    assert S.ratchet_regressions(_board(14, 1, ["x"]), _board(10, 5, ["x", "a", "b", "c", "d"])) == []


def test_innocence_ratchet_is_silent_on_a_brand_new_axis():
    """Adding an axis must not read as a regression of the axes that existed."""
    current = _board(10, 5, ["a"])
    current["axes"]["brand_new"] = {"total": 15, "honest": 0, "defect": 15, "states": {}, "defect_codes": []}
    assert S.ratchet_regressions(current, _board(10, 5, ["a"])) == []


def test_guilt_ratchet_fires_when_an_axis_disappears():
    problems = S.ratchet_regressions({"axes": {}}, _board(10, 5, ["a"]))
    assert problems and "disappeared" in problems[0]


# --------------------------------------------------------------------------
# CLI contract
# --------------------------------------------------------------------------


def test_unreadable_canonical_is_cannot_verify_not_regression(tmp_path, capsys):
    """"I could not measure" must never be reported as "it regressed" — an
    healer acting on a mis-attributed failure spends a session on a false
    premise (W106b)."""
    rc = S.main(["--canonical", str(tmp_path / "nope.json"), "--check"])
    assert rc == S.EXIT_CANNOT_VERIFY
    assert "CANNOT VERIFY" in capsys.readouterr().out


def test_unreadable_baseline_is_cannot_verify(tmp_path, capsys):
    canonical = tmp_path / "c.json"
    canonical.write_text(json.dumps({"data": [rec("01111")]}), encoding="utf-8")
    rc = S.main(["--canonical", str(canonical), "--baseline", str(tmp_path / "nope.json"), "--check"])
    assert rc == S.EXIT_CANNOT_VERIFY


def test_check_round_trips_against_a_freshly_written_baseline(tmp_path):
    canonical = tmp_path / "c.json"
    canonical.write_text(
        json.dumps({"data": [rec("01111", per_skala=[{"x": 1}], _l2_source=B.OSS_2025_SOURCE)]}),
        encoding="utf-8",
    )
    baseline = tmp_path / "b.json"
    assert S.main(["--canonical", str(canonical), "--baseline", str(baseline), "--update-baseline"]) == S.EXIT_OK
    assert S.main(["--canonical", str(canonical), "--baseline", str(baseline), "--check"]) == S.EXIT_OK


def test_check_fails_when_the_dataset_regresses_against_its_baseline(tmp_path):
    canonical = tmp_path / "c.json"
    good = rec("01111", per_skala=[{"x": 1}], _l2_source=B.OSS_2025_SOURCE)
    canonical.write_text(json.dumps({"data": [good]}), encoding="utf-8")
    baseline = tmp_path / "b.json"
    S.main(["--canonical", str(canonical), "--baseline", str(baseline), "--update-baseline"])

    # the source marker is dropped — the rows stay, the provenance does not
    canonical.write_text(json.dumps({"data": [rec("01111", per_skala=[{"x": 1}])]}), encoding="utf-8")
    assert S.main(["--canonical", str(canonical), "--baseline", str(baseline), "--check"]) == S.EXIT_REGRESSION


def test_empty_canonical_is_refused(tmp_path):
    canonical = tmp_path / "c.json"
    canonical.write_text(json.dumps({"data": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        S.load_records(canonical)
