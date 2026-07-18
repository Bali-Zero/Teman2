"""Tests for the Batch A membership compiler (P0 precondition).

Pins: the reason-code predicates (plan §1), the in-scope split (114 A-serving
extracted, 107 A-empty watchlist), and the deliberate exclusion of the two
OSS-sourced cured codes (20111, 49213) — they carry `_l2_source` so they are
NOT part of the no-scope/PP28-fill population Batch A targets, even though the
pilot cured them. A silent inclusion or a census drift must fail here.
"""

from __future__ import annotations

import sys
from pathlib import Path

FILIERA = Path(__file__).resolve().parents[1]
if str(FILIERA) not in sys.path:
    sys.path.insert(0, str(FILIERA))

import emit_batch_membership as m  # noqa: E402


def _rec(code, *, per_skala, l2_status=None, l2_source=None, pp28=None):
    r = {"kode_kbli_2025": code, "per_skala": per_skala, "sektor_id": "A", "judul": code}
    if l2_status is not None:
        r["_l2_status"] = l2_status
    if l2_source is not None:
        r["_l2_source"] = l2_source
    if pp28 is not None:
        r["pp28_sources"] = pp28
    return r


def test_classify_serving_pp28():
    r = _rec("11111", per_skala=[{"x": 1}], pp28=["PP28:1"])
    assert m._classify(r) == m.REASON_SERVING_PP28


def test_classify_serving_orphan_no_pp28():
    r = _rec("80190", per_skala=[{"x": 1}], pp28=[])
    assert m._classify(r) == m.REASON_SERVING_ORPHAN


def test_classify_empty_gap_needs_no_oss_risk_status():
    assert m._classify(_rec("22222", per_skala=[], l2_status="no_oss_risk")) == m.REASON_EMPTY_GAP


def test_oss_sourced_detached_code_is_excluded():
    # 20111/49213 shape: per_skala detached to [] BUT carrying an OSS source and
    # no no_oss_risk status -> matches NO predicate -> not a Batch A member.
    r = _rec("20111", per_skala=[], l2_status=None, l2_source="OSS_RBA_resiko_2025")
    assert m._classify(r) is None


def test_serving_code_with_l2_source_is_not_serving():
    # an OSS-sourced code that still serves rows is OSS-native, not Batch A.
    r = _rec("33333", per_skala=[{"x": 1}], l2_source="OSS_RBA_resiko_2025", pp28=["PP28:9"])
    assert m._classify(r) is None


def test_census_and_in_scope_on_real_canonical():
    # Census AFTER the Lot 5 cure (kbli/lot5-data-apply): the 13 Lot 5
    # quarantined codes were detached (per_skala -> []), migrating
    # A-serving/pp28 -> A-empty/gap. Post-Lot-4 baseline was 61/1/159
    # (in-scope 62, per test_kbli_batch_a_lot4_registry.py's own history);
    # this lot's --apply does not touch any OSS-sourced code, so the
    # migration is a clean 13-code shift. 61-13=48, 159+13=172, 62-13=49.
    # Total population is invariant at 221.
    records = _load_real()
    members = m.build_members(records)
    cen = m.census(members)
    assert cen["A-serving/pp28"] == 48
    assert cen["A-serving/orphan"] == 1
    assert cen["A-empty/gap"] == 172
    assert cen["_in_scope_total"] == 49
    assert cen["_total"] == 221
    by = {x["kode_kbli_2025"]: x for x in members}
    # the two OSS-sourced cured codes are absent
    assert "20111" not in by and "49213" not in by
    # the orphan is in scope
    assert by["80190"]["reason_code"] == m.REASON_SERVING_ORPHAN
    assert by["80190"]["in_scope"] is True
    # a no-scope cured pilot code is present but OUT of scope (watchlist)
    assert by["51103"]["reason_code"] == m.REASON_EMPTY_GAP
    assert by["51103"]["in_scope"] is False
    # every Lot 1 cured code migrated to the gap watchlist (out of scope)
    lot1 = ["01287", "01700", "02201", "02402", "02409", "05102", "05200",
            "08920", "19206", "36003", "38122", "38222", "39001"]
    for code in lot1:
        assert by[code]["reason_code"] == m.REASON_EMPTY_GAP, code
        assert by[code]["in_scope"] is False, code
    # every Lot 2 cured code migrated to the gap watchlist (out of scope)
    lot2 = ["42999", "47771", "49233", "49296", "50113", "52103", "52105",
            "52211", "52219", "52232", "52239", "52299", "59131"]
    for code in lot2:
        assert by[code]["reason_code"] == m.REASON_EMPTY_GAP, code
        assert by[code]["in_scope"] is False, code
    # every Lot 3 cured code migrated to the gap watchlist (out of scope)
    lot3 = ["60101", "60103", "60201", "60203", "60311", "61905", "61909",
            "64110", "64220", "64320", "64330", "64920", "64940"]
    for code in lot3:
        assert by[code]["reason_code"] == m.REASON_EMPTY_GAP, code
        assert by[code]["in_scope"] is False, code
    # every Lot 4 cured code migrated to the gap watchlist (out of scope)
    lot4 = ["64955", "64996", "64997", "66113", "66116", "66123", "66124",
            "66129", "66131", "66132", "66149", "66153", "66159"]
    for code in lot4:
        assert by[code]["reason_code"] == m.REASON_EMPTY_GAP, code
        assert by[code]["in_scope"] is False, code
    # every Lot 5 cured code migrated to the gap watchlist (out of scope)
    lot5 = ["66192", "66197", "66211", "66224", "66292", "66299", "66309",
            "68123", "68125", "68126", "68127", "68129", "70100"]
    for code in lot5:
        assert by[code]["reason_code"] == m.REASON_EMPTY_GAP, code
        assert by[code]["in_scope"] is False, code


def test_members_sorted_deterministic():
    records = _load_real()
    codes = [x["kode_kbli_2025"] for x in m.build_members(records)]
    assert codes == sorted(codes)


def _load_real():
    import json

    return json.loads(m.CANONICAL.read_text(encoding="utf-8"))["data"]
