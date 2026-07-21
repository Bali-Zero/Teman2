"""Tests for the Batch A membership compiler (P0 precondition).

Pins: the reason-code predicates (plan §1), the in-scope split (as of the
Lot 10 cure: 5 A-serving extracted, 216 A-empty watchlist -- see the history
comment on test_census_and_in_scope_on_real_canonical for how this number
moves lot-by-lot), and the deliberate exclusion of the two OSS-sourced cured
codes (20111, 49213) — they carry `_l2_source` so they are NOT part of the
no-scope/PP28-fill population Batch A targets, even though the pilot cured
them. A silent inclusion or a census drift must fail here.
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
    # Census AFTER the Lot 7 cure (kbli/lot7-data-apply, batch_a_lot7.json)
    # landed on main. Post-Lot-6 baseline was 36/0/185 (in-scope 36, per this
    # test's own prior history, #2843). The Lot 7 cure's 13-code detach
    # (per_skala -> []) is the ONLY contributor to this census (no other
    # merged commit between the Lot 6 re-emit and this one touches per_skala,
    # pp28_sources, _l2_source, or _l2_status). Unlike Lot 6 (12 pp28 + 1
    # orphan), THIS lot's shift IS the naive 36-13=23: verified directly
    # against the pre-cure canonical (not inferred) by reading each of the
    # 13 codes' pp28_sources/per_skala/_l2_source/_l2_status through
    # emit_batch_membership._classify()'s own predicate BEFORE running
    # cure_canonical_collisions.py --apply -- all 13 codes (85403, 85404,
    # 86109, 86201, 86202, 86203, 85330, 85401, 86102, 91212, 90111, 91222,
    # 91424) classified A-serving/pp28 pre-cure, ZERO were A-serving/orphan
    # (every one of the 13 already carries a non-empty pp28_sources in the
    # cure spec itself -- 6 self-referencing health/education codes, plus
    # multi-parent/collision-citation codes, but none with an empty array).
    # Net: pp28 loses the full 13 (36-13=23), orphan stays at its Lot-6 floor
    # of 0 (no orphan existed pre-cure to lose), gap gains the full 13
    # (185+13=198), summing to the full -13 in-scope shift (36-13=23).
    #
    # Lot 8 cure (fix(kbli): Lot 8 cure -- apply batch_a_lot8.json, commit
    # d50d5f33ca, 9-code detach-only) shifted it AGAIN, down to 14: this
    # assertion was never refreshed after that lot landed -- a real gap in
    # this program's per-lot ritual (every one of Lots 2/4/5/6/7 bundled a
    # "re-emit membership + refresh census expectations" commit; Lot 8 did
    # not). Verified directly by diffing _classify() per-code between
    # d50d5f33ca^ and d50d5f33ca: all 9 codes (91425, 93113, 93115, 93121,
    # 93122, 93123, 93124, 93125, 93126) flip A-serving/pp28 -> A-empty/gap,
    # zero orphans involved. Net: pp28 23-9=14, gap 198+9=207.
    #
    # Lot 9 cure (commit 39c94f78f5, batch_a_lot9.json, 8-code Group-A
    # detach) shifted it a third time, down to 6. Verified directly by
    # diffing _classify() per-code between 9acc7fa3d4 (Lot 8 Appendix A tip,
    # pre-Lot-9) and 39c94f78f5: all 8 codes (93127, 93128, 93129, 93192,
    # 93194, 93195, 93197, 93199) flip A-serving/pp28 -> A-empty/gap, zero
    # orphans involved. Net: pp28 14-8=6, gap 207+8=215. (93191/93193 were
    # the 2 tier-scoped-held members of Lot 9 -- per_skala untouched THAT
    # lot, so they did not flip census then; only status_mapping/whatChanged
    # changed for them at Lot 9, which _classify() does not read.)
    #
    # Lot 10 cure (research/operations/2026-07-21-kbli-batch-a-lot10-conductor-gate.md,
    # batch_a_lot10.json) shifts it a fourth time, down to 5 -- the FIRST lot
    # to use the tier-scoped partial_detach primitive (PR #2921). 93114 and
    # 93191 each go from a 2-tier to a 1-tier per_skala via partial_detach --
    # still NON-EMPTY, so _classify() keeps both A-serving/pp28 (no census
    # flip for either). 93193 goes from 2 tiers to a plain full detach
    # (per_skala -> []) -- THIS is the one code that flips A-serving/pp28 ->
    # A-empty/gap. Net: pp28 6-1=5, gap 215+1=216. Verified directly by
    # diffing _classify() per-code between the Lot 9 tip and the Lot 10
    # cure commit.
    #
    # Total population is invariant at 221 across all four lots (detach-only
    # cures never remove a record, only zero or shrink its per_skala).
    records = _load_real()
    members = m.build_members(records)
    cen = m.census(members)
    assert cen["A-serving/pp28"] == 5
    # census() only inserts a reason_code key when >=1 member has it (plain
    # dict accumulation, no defaultdict) -- orphan has hit exactly zero since
    # Lot 6 (80190 was the last orphan, detached by Lot 6; #2843), so the key
    # is genuinely absent, not present-and-zero. Use .get() here, matching
    # how main() already prints it (`cen.get(k, 0)`).
    assert cen.get("A-serving/orphan", 0) == 0
    assert cen["A-empty/gap"] == 216
    assert cen["_in_scope_total"] == 5
    assert cen["_total"] == 221
    by = {x["kode_kbli_2025"]: x for x in members}
    # the two OSS-sourced cured codes are absent
    assert "20111" not in by and "49213" not in by
    # 80190 was the Lot 6 cure's lone pre-cure orphan (empty pp28_sources);
    # it is now detached like the rest of Lot 6, no longer serving/orphan.
    assert by["80190"]["reason_code"] == m.REASON_EMPTY_GAP
    assert by["80190"]["in_scope"] is False
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
    # every Lot 6 cured code migrated to the gap watchlist (out of scope) --
    # 80190 included, per the pre-cure-orphan history note above.
    lot6 = ["72101", "72103", "72105", "75001", "75002", "75009", "77397",
            "78109", "82911", "85321", "85323", "85324", "80190"]
    for code in lot6:
        assert by[code]["reason_code"] == m.REASON_EMPTY_GAP, code
        assert by[code]["in_scope"] is False, code
    # every Lot 7 cured code migrated to the gap watchlist (out of scope) --
    # all 13 were pre-cure A-serving/pp28 (none orphan), per the history
    # note above.
    lot7 = ["85403", "85404", "86109", "86201", "86202", "86203", "85330",
            "85401", "86102", "91212", "90111", "91222", "91424"]
    for code in lot7:
        assert by[code]["reason_code"] == m.REASON_EMPTY_GAP, code
        assert by[code]["in_scope"] is False, code
    # every Lot 8 cured code migrated to the gap watchlist (out of scope) --
    # all 9 were pre-cure A-serving/pp28 (none orphan), verified directly
    # against d50d5f33ca^/d50d5f33ca above.
    lot8 = ["91425", "93113", "93115", "93121", "93122", "93123", "93124",
            "93125", "93126"]
    for code in lot8:
        assert by[code]["reason_code"] == m.REASON_EMPTY_GAP, code
        assert by[code]["in_scope"] is False, code
    # every Lot 9 Group-A detached code migrated to the gap watchlist (out of
    # scope) -- all 8 were pre-cure A-serving/pp28 (none orphan), verified
    # directly against 9acc7fa3d4/39c94f78f5 above. (93191/93193, the 2
    # tier-scoped-held members AT LOT 9, were untouched on per_skala at that
    # lot and not asserted here then -- Lot 10 below now cures both.)
    lot9 = ["93127", "93128", "93129", "93192", "93194", "93195", "93197",
            "93199"]
    for code in lot9:
        assert by[code]["reason_code"] == m.REASON_EMPTY_GAP, code
        assert by[code]["in_scope"] is False, code
    # Lot 10: 93193's contaminated Tier 1 + independently-unconfirmable
    # Tier 2 both moved (plain full detach, zero sound tiers remain per
    # research/operations/2026-07-21-kbli-batch-a-lot10-conductor-gate.md
    # §2.1/§3.2) -- per_skala is now [], so it migrates to the gap watchlist
    # like every other lot's full-detach codes.
    lot10_full_detach = ["93193"]
    for code in lot10_full_detach:
        assert by[code]["reason_code"] == m.REASON_EMPTY_GAP, code
        assert by[code]["in_scope"] is False, code
    # 93114 and 93191 are Lot 10's OTHER two cure targets, but they used
    # partial_detach (one tier removed, one sound tier kept) -- per_skala is
    # non-empty afterward, so _classify() keeps them A-serving/pp28,
    # deliberately NOT migrated to the watchlist. Asserted explicitly here
    # (not just "not in lot10_full_detach") so a future regression that
    # accidentally empties either code's per_skala is caught by THIS test,
    # not only by test_kbli_batch_a_lot10_registry.py.
    lot10_partial_detach_still_serving = ["93114", "93191"]
    for code in lot10_partial_detach_still_serving:
        assert by[code]["reason_code"] == m.REASON_SERVING_PP28, code
        assert by[code]["in_scope"] is True, code


def test_members_sorted_deterministic():
    records = _load_real()
    codes = [x["kode_kbli_2025"] for x in m.build_members(records)]
    assert codes == sorted(codes)


def _load_real():
    import json

    return json.loads(m.CANONICAL.read_text(encoding="utf-8"))["data"]
