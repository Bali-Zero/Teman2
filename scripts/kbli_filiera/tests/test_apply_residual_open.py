"""Guilt + innocence for `apply_residual_open.py` (naso residual lot 1, 2026-09-18).

The compiler relabels the RESIDUAL-open records `declared_gap -> located` and
names Pasal 3(1)(d)+(2) as the locator. The tests pin (a) the dataset state the
PR delivers, on the REAL canonical, and (b) the refusal surface on a sandbox —
where the load-bearing property is that the population is RE-DERIVED from the
instrument, so the spec can neither widen the class (a listed code the rule does
not reach) nor narrow it (a reached code the spec omits).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
FILIERA = REPO_ROOT / "scripts" / "kbli_filiera"
if str(FILIERA) not in sys.path:
    sys.path.insert(0, str(FILIERA))

import apply_residual_open as R  # noqa: E402

CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
SPEC = json.loads(R.SPEC.read_text(encoding="utf-8"))
SPEC2 = json.loads(
    (FILIERA / "cure_specs" / "residual_open_naso_2026_09_21_lot2.json").read_text(
        encoding="utf-8"
    )
)

# The lot's deferred groups, as the spec declares them. Pinned here because the
# arithmetic is the honest half of the claim, and it has two axes: the rule
# REACHES 507 codes, of which 329 ship and 178 are withheld (61 + 67 + 29 + 19
# + 2); the other 537 never enter the reach at all (Bali 331, legacy prose 36,
# no Besar row 12, no PP 28 rows 158). A lot that quietly grew breaks this
# first. The 2 and the 67 (not 68) are one change, not two: `50143` moved from
# the unswept-statute leg to the title-collision leg, which claims it earlier
# and hands the reader the capped row instead of the unread-statute caution.
# `instrument_reached_sibling` withholds nothing at all — it is a 135-code class
# measured and found EMPTY of true positives, declared here so the next lane
# inherits the negative result instead of re-running the same search.
DEFERRED = {
    "adjudicated_sibling": 29,
    "annex_title_collision": 2,
    "bali_attenzione_fascia": 272,
    "bali_bloccato_dipende_scope": 31,
    "bali_chiuso_bali": 22,
    "bali_other": 6,
    "body_stated_category": 19,
    "instrument_reached_sibling": 135,
    "legacy_pma_prose": 36,
    "residual_besar_absent": 12,
    "residual_besar_unobserved": 158,
    "sector_law_referral_pasal_11_2": 61,
    "sector_statute_unswept": 67,
}

# The sector legs, pinned by DIVISION and by count. Two different claims, kept
# apart on purpose: `instrument_referral` is the Perpres saying in its own text
# that it does not govern finance/banking (Pasal 11(2)); `unswept_sector_statute`
# is US saying we never read the sector's own statute. Neither means "closed".
# divisions -> how many codes of the residual class live in them. That is 4 and
# 2 MORE than the deferred counts below, because 65131 65132 65203 65204 and
# 50127 50139 were already withheld by the hand-exclusion and sibling legs: a
# code can be withheld twice, and the lot only removes it once.
SECTOR_LEGS = {
    "instrument_referral": ({"64", "65", "66"}, 65),
    "unswept_sector_statute": ({"09", "35", "49", "50", "51", "52", "53", "61"}, 70),
}
SECTOR_DIVISIONS = {d for divs, _ in SECTOR_LEGS.values() for d in divs}

# The reach's title collisions. 50143 is in the sector divisions too and would
# be withheld either way; 58120 is the one code NO other leg sees, which is why
# it is named here and not folded into a count.
COLLISION_WITHHELD = {"50143", "58120"}

# The codes the rule REACHES and the lot withholds anyway, because absence is
# only evidence of openness where no instrument is in the neighbourhood.
SIBLING_WITHHELD = {
    "01282", "01284", "01285", "01286", "10302", "10303", "10304", "10306",
    "10723", "10729", "13131", "21024", "22122", "22123", "22129", "50127",
    "50139", "55204", "65203", "65204", "79121", "79129", "85102", "85202",
    "85312", "85316", "85322", "85402", "86105",
}


@pytest.fixture(scope="module")
def records() -> list[dict]:
    return json.loads(CANONICAL.read_text(encoding="utf-8"))["data"]


@pytest.fixture(scope="module")
def by_code(records) -> dict[str, dict]:
    return {str(r["kode_kbli_2025"]): r for r in records}


# ---------------------------------------------------------------- dataset state


def test_the_lot_is_329_codes_and_the_deferred_arithmetic_is_declared():
    codes = [str(c) for c in SPEC["items"]]
    assert len(codes) == 329 and len(set(codes)) == 329
    assert {k: v["codes"] for k, v in SPEC["deferred"].items()} == DEFERRED
    assert SPEC["lot"] == 1 and SPEC["vintage"] == "2021-05-25"
    # 329 shipped + 61 Pasal 11(2) + 67 unswept statute + 29 sibling
    # + 19 hand-excluded + 2 title collision = the 507 the rule reaches.
    # `instrument_reached_sibling` is deliberately NOT a term: it withholds
    # nothing, so adding it would double-count 135 shipped codes.
    withheld_count = (
        DEFERRED["sector_law_referral_pasal_11_2"]
        + DEFERRED["sector_statute_unswept"]
        + DEFERRED["annex_title_collision"]
    )
    assert (
        len(codes) + withheld_count + len(SIBLING_WITHHELD) + len(SPEC["excluded_codes"])
        == 507
    )
    assert not any(c[:2] in SECTOR_DIVISIONS for c in codes)


def test_the_sector_referral_blocks_say_which_claim_they_are_making():
    blocks = {b["kind"]: b for b in SPEC["sector_referral"]}
    assert set(blocks) == set(SECTOR_LEGS)
    for kind, (divisions, _) in SECTOR_LEGS.items():
        assert set(blocks[kind]["divisions"]) == divisions
        assert len(blocks[kind]["why"]) > 200
    # The instrument leg must quote the article it rests on; the unswept leg
    # must NOT pretend to — it names statutes nobody here has read.
    assert "Pasal 11 ayat (2)" in blocks["instrument_referral"]["instrument"]
    assert "Bidang Usaha keuangan" in blocks["instrument_referral"]["why"]
    assert "UU 17/2008" in blocks["unswept_sector_statute"]["instrument"]
    assert "until a lane actually reads the statute" in blocks["unswept_sector_statute"]["why"]


def test_banking_is_withheld_and_says_pasal_11_2(records):
    # The defect two independent council seats found on round 1: 64121 —
    # conventional commercial banking — was shipped residual-open with a
    # verified 100% cap, under a basis string asserting that no Pasal 11(2)
    # carve-out reaches it. The instrument says the opposite in its own text.
    reach = R.reached(SPEC, records)
    held = R.withheld(SPEC, records, reach)
    assert "64121" in reach and "64121" in held
    assert held["64121"].startswith("instrument_referral: Perpres 10/2021 Pasal 11 ayat (2)")
    assert "64121" not in SPEC["items"]


def test_the_withheld_are_withheld_and_still_say_not_verified(records, by_code):
    # Both subtractions, checked the same way: the rule must still REACH them
    # (otherwise the exclusion is decoration) and the canonical must still
    # withhold the claim.
    reach = R.reached(SPEC, records)
    held = R.withheld(SPEC, records, reach)
    sector = {c for c in reach if c[:2] in SECTOR_DIVISIONS}
    assert (
        set(held)
        == SIBLING_WITHHELD | set(SPEC["excluded_codes"]) | sector | COLLISION_WITHHELD
    )
    for kind, (divisions, in_reach) in SECTOR_LEGS.items():
        assert len({c for c in reach if c[:2] in divisions}) == in_reach, kind
    for code in held:
        assert code in reach, code
        assert code not in SPEC["items"], code
        assert by_code[code]["pma_verification_status"] == "declared_gap", code


def test_the_five_declared_non_adjudications_are_not_in_this_lot(by_code):
    # Each is pinned by ANOTHER suite as untouched: 11030 by
    # `test_the_verdict_flips_are_not_taken_here` (a pending TERBUKA→TERTUTUP
    # flip that is Zero's call), the four 65xxx by
    # `test_excluded_neighbors_are_byte_untouched` (the PP 14/2018 cure left
    # `cap_verified` unset on purpose). A lot that swallowed them would publish
    # a verdict the repo has already declared unsettled.
    for code in ("11030", "65131", "65132", "65203", "65204"):
        assert code not in SPEC["items"], code
        assert by_code[code]["pma_verification_status"] == "declared_gap", code


def test_the_body_stated_categories_are_named_one_by_one():
    # A category exclusion is an assertion about a class of codes, so the spec
    # has to say which class and why for EACH code — a bare list would be an
    # unaudited hole in a lot whose whole premise is absence.
    excluded = SPEC["excluded_codes"]
    assert len(excluded) == 19
    for code, why in excluded.items():
        assert len(why) > 80, code
    assert "alkohol" in excluded["11030"] and "alkohol" in excluded["56301"]
    assert "tobacco" in excluded["12001"] and "tobacco" in excluded["01150"]
    assert "Menhan" in excluded["33112"] and "Menhan" in excluded["20292"]
    assert "CITES" in excluded["03214"]
    assert "penjaminan" in excluded["65131"]


def test_every_lot_code_is_located_open_and_cites_the_residual_article(by_code):
    for code in SPEC["items"]:
        r = by_code[code]
        assert (r["pma_status"], r["pma_max_asing"]) == ("TERBUKA", 100), code
        assert r["pma_verification_status"] == "located", code
        assert r["pma_cap_verified"] is True, code
        assert r["pma_source_vintage"] == "2021-05-25", code
        assert r["pma_official_basis"] == R.BASIS, code


def test_the_basis_declares_what_it_does_not_prove():
    # A reader who takes "located" to mean "an instrument names this code" must
    # be corrected by the string itself, and both sector limits must be in it:
    # the one the Perpres states about itself (Pasal 11(2), by SECTOR and not by
    # the six codes the carve-out artifact lists) and the one we state about our
    # own sweep (statutes outside the Perpres, whose divisions are withheld).
    assert "No instrument maps the 5-digit code" in R.BASIS
    assert "sector statutes OUTSIDE the" in R.BASIS
    assert "Pasal 3(1)(d) + 3(2)" in R.BASIS
    assert "max foreign 100%" in R.BASIS
    assert "Pasal 11(2) sector-law referral reaches its SECTOR" in R.BASIS
    assert "divisions 64, 65 and 66" in R.BASIS
    assert "divisions 09, 35, 49-53, 61" in R.BASIS


def test_no_lot_member_publishes_legacy_pma_prose(by_code):
    # The compiler writes no condition and no cap note; this pins the other
    # half — that no member ARRIVED carrying one. Once a record is `located`,
    # `pma_kondisi`/`pma_nota` print directly under `- Official basis:` on the
    # chat, document and Qdrant surfaces, so a generator-era string would read
    # as part of the Perpres basis this lot writes.
    for code in SPEC["items"]:
        assert R.legacy_prose(by_code[code]) == [], code


def test_the_36_prose_records_stayed_behind_and_still_say_not_verified(by_code):
    # Guilt's mirror: the deferral is only honest if those records are still
    # withheld. 02101 carries the community-partnership string, 06100 the
    # mining divestiture note, 01131 `pma_prioritas` on a non-Lampiran-I code.
    for code in ("02101", "02103", "03120", "06100", "08101", "01131", "62209"):
        r = by_code[code]
        assert code not in SPEC["items"], code
        assert r["pma_verification_status"] == "declared_gap", code
        assert R.legacy_prose(r), code


def test_the_deferred_groups_are_still_declared_gap(by_code):
    # One exemplar per deferred group — the lot must not have leaked into them.
    # 38110 is bucket residual-besar-absent (no Besar row + CHIUSO_MORATORIA_BALI
    # on the withdrawn no-Besar inference); 20119 is a declared_gap control.
    # The legacy-prose group has its own test above.
    for code in ("38110", "20119"):
        assert by_code[code]["pma_verification_status"] == "declared_gap", code


def test_rerun_on_the_shipped_canonical_is_a_clean_noop(records):
    todo, refusals = R.check(SPEC, records)
    assert (todo, refusals) == ([], [])


# ---------------------------------------------------------------- refusal surface

# `99991`/`99992` are absent from every Lampiran, from the body lists and from
# the sector-law carve-out, so `classify()` puts them in the residual bucket and
# `besar_state()` decides which one from `per_skala` alone.
RESIDUAL = "99991"
SIBLING = "99992"


def rec(code, status="TERBUKA", maxa=100, state="declared_gap",
        bali="OK_or_HIGHER_RISK", blocked=False, besar=True):
    return {
        "kode_kbli_2025": code,
        "judul": f"Sintetico {code}",
        "pma_status": status,
        "pma_max_asing": maxa,
        "pma_verification_status": state,
        "per_skala": [{"skala_usaha": ["Besar" if besar else "Kecil"]}],
        "l4_bali": {"status": bali, "blocked": blocked},
    }


def mini_spec(items):
    """The real spec, re-pointed at the sandbox — minus the hand-written
    exclusions, whose codes do not exist here (a stale exclusion is a refusal,
    which is the behaviour `test_a_stale_hand_exclusion_refuses…` pins). The
    `adjudicated_sibling_prefix` rule is KEPT: it is re-derived per dataset, so
    it is inert until a test supplies an adjudicated sibling.
    """
    spec = json.loads(json.dumps(SPEC))
    spec["items"] = items
    spec["excluded_codes"] = {}
    # Same reason as the exclusions: `marked_codes` is a census of the REAL
    # catalogue, and the sandbox is not it. Emptying it keeps the probe armed —
    # a synthetic record carrying a marker is still withheld, which is what
    # `test_a_code_carrying_a_category_marker_is_withheld…` pins.
    for block in spec.get("category_closure_probe", []):
        block["marked_codes"] = []
    # Same again for the title-collision census. Emptying it keeps the probe
    # ARMED — a synthetic record whose title is a capped row's activity is still
    # withheld, which `test_a_title_that_is_a_capped_rows_activity…` pins.
    # `sector_law_closures` is NOT touched: its staleness is checked against the
    # catalogue on disk, so the real four codes stay meaningful in the sandbox.
    for block in spec.get("annex_title_collision_probe", []):
        block["collided_codes"] = []
    return spec


def test_an_eligible_residual_record_is_relabelled_and_nothing_else_moves():
    spec = mini_spec([RESIDUAL])
    records = [rec(RESIDUAL)]
    todo, refusals = R.check(spec, records)
    assert (todo, refusals) == ([RESIDUAL], [])
    patch = R.patch_for(spec)
    assert set(patch) == {
        "pma_verification_status",
        "pma_official_basis",
        "pma_source_vintage",
        "pma_cap_verified",
    }
    assert patch["pma_verification_status"] == "located"


def test_a_code_the_rule_reaches_but_the_spec_omits_blocks_the_write():
    # INNOCENCE side of the two-way check: a guard that only inspects the codes
    # it was handed cannot tell a lot from a hand-picked subset.
    spec = mini_spec([RESIDUAL])
    _, refusals = R.check(spec, [rec(RESIDUAL), rec(SIBLING)])
    assert refusals == [f"{SIBLING}: reached by the lot rule but not listed"]


def test_a_listed_code_the_rule_does_not_reach_is_refused():
    spec = mini_spec([RESIDUAL])
    _, refusals = R.check(spec, [rec(RESIDUAL, status="TERBATAS", maxa=49)])
    assert refusals and "the rule does not reach it" in refusals[0]
    assert "TERBATAS/49" in refusals[0]


def test_a_blocked_bali_overlay_keeps_a_code_out_of_lot_1():
    # The lot is cut on the Bali axis precisely so that relabelling never
    # unveils a provincial closure as a side effect.
    spec = mini_spec([RESIDUAL])
    _, refusals = R.check(
        spec, [rec(RESIDUAL, bali="CHIUSO_MORATORIA_BALI", blocked=True)]
    )
    assert refusals and "CHIUSO_MORATORIA_BALI/True" in refusals[0]


def test_an_adjudicated_sibling_withholds_the_code_and_says_why():
    # Guilt for the UNDER-match subtraction: `classify()` cannot see a closure
    # the Perpres states by description, but a 4-digit neighbour an instrument
    # DID reach is the evidence that it is in this neighbourhood.
    spec = mini_spec([RESIDUAL])
    sibling = rec(SIBLING, status="TERTUTUP", maxa=0, state="located")
    _, refusals = R.check(spec, [rec(RESIDUAL), sibling])
    assert refusals == [
        f"{RESIDUAL}: listed in the lot but withheld — adjudicated 4-digit "
        f"sibling(s) {SIBLING} — an instrument reaches this subgolongan, so "
        "absence is not evidence of openness"
    ]


def test_an_unadjudicated_sibling_withholds_nothing():
    # INNOCENCE: `declared_gap` on the neighbour is the state of most of the
    # catalogue. Reading it as evidence would empty the lot.
    spec = mini_spec([RESIDUAL])
    sibling = rec(SIBLING, status="TERTUTUP", maxa=0, state="declared_gap")
    assert R.check(spec, [rec(RESIDUAL), sibling]) == ([RESIDUAL], [])
    # And a neighbour outside the 4-digit prefix is not a sibling at all.
    far = rec("99881", status="TERBATAS", maxa=49, state="located")
    assert R.check(spec, [rec(RESIDUAL), far]) == ([RESIDUAL], [])


def test_a_stale_hand_exclusion_refuses_instead_of_looking_like_protection():
    spec = mini_spec([RESIDUAL])
    spec["excluded_codes"] = {"99999": "a code the rule never reaches"}
    _, refusals = R.check(spec, [rec(RESIDUAL)])
    assert refusals == [
        "99999: excluded_codes lists it but the rule does not reach it — "
        "stale exclusion, remove it or fix the rule"
    ]


def test_a_hand_excluded_code_cannot_be_listed_in_the_lot():
    spec = mini_spec([RESIDUAL])
    spec["excluded_codes"] = {RESIDUAL: "the body names this category in prose"}
    todo, refusals = R.check(spec, [rec(RESIDUAL)])
    assert todo == []
    assert refusals == [
        f"{RESIDUAL}: listed in the lot but withheld — the body names this "
        "category in prose"
    ]


def test_a_code_with_no_besar_row_is_not_in_this_bucket_at_all():
    # `residual-besar-absent`/`-unobserved` are different buckets; a record
    # without a Besar row cannot enter the lot even when everything else fits.
    # An EMPTY known bucket is an empty population, so the reader gets the
    # accurate refusal instead of "cannot re-derive the population".
    spec = mini_spec([RESIDUAL])
    _, refusals = R.check(spec, [rec(RESIDUAL, besar=False)])
    assert refusals and "the rule does not reach it" in refusals[0]


def test_a_bucket_name_classify_cannot_emit_refuses_instead_of_writing():
    # Two guards in sequence, and the OUTER one answers now: `REQUIRED_RULE`
    # pins the bucket before the population is derived at all, so a spec can no
    # longer select which class this compiler writes. `reached()` keeps its own
    # KNOWN_BUCKETS check for a caller that builds a rule in code — pinned
    # directly below, because a guard nothing exercises rots.
    spec = mini_spec([RESIDUAL])
    spec["rule"]["bucket"] = "residual-besar-typo"
    todo, refusals = R.check(spec, [rec(RESIDUAL)])
    assert todo == []
    assert refusals == [
        "rule.bucket is 'residual-besar-typo', not 'residual-besar-observed' — "
        "this compiler only writes the residual class, and a spec cannot widen it"
    ]


def test_the_inner_bucket_guard_still_names_an_impossible_bucket():
    spec = mini_spec([RESIDUAL])
    spec["rule"]["bucket"] = "residual-besar-typo"
    with pytest.raises(R.CannotVerify) as exc:
        R.reached(spec, [rec(RESIDUAL)])
    assert "is not one classify() can emit" in str(exc.value)


def test_a_record_carrying_legacy_pma_prose_is_refused_field_by_field():
    # One case per field, because the disclosure gate publishes all four and a
    # guard that only knows `pma_kondisi` would let the other three through.
    for field, value in (
        ("pma_kondisi", "Kemitraan dengan masyarakat setempat"),
        ("pma_nota", "Tunduk pada ketentuan divestasi dan IUP"),
        ("pma_prioritas", True),
        ("pma_cap_note", "max=100 inferred from lampiran-absence"),
    ):
        spec = mini_spec([RESIDUAL])
        r = rec(RESIDUAL)
        r[field] = value
        _, refusals = R.check(spec, [r])
        assert refusals, field
        assert "the rule does not reach it" in refusals[0], field
        assert f"legacy prose {field}" in refusals[0], field


def test_an_empty_or_false_legacy_field_is_not_prose():
    # UNDER-match's mirror: `pma_prioritas: false` and `pma_nota: null` are the
    # normal shape of 507 records — reading them as prose would empty the lot.
    r = rec(RESIDUAL)
    r.update({"pma_prioritas": False, "pma_nota": None, "pma_kondisi": ""})
    assert R.legacy_prose(r) == []
    assert R.check(mini_spec([RESIDUAL]), [r]) == ([RESIDUAL], [])


def test_an_unknown_verification_state_is_refused_not_overwritten():
    spec = mini_spec([RESIDUAL])
    r = rec(RESIDUAL, state="pending_adjudication")
    # The rule's own predicate keeps it out; the write is blocked either way.
    _, refusals = R.check(spec, [r])
    assert refusals and RESIDUAL in refusals[0]


def test_already_located_under_another_basis_is_refused_and_same_basis_is_a_noop():
    spec = mini_spec([RESIDUAL])
    r = rec(RESIDUAL, state="located")
    r["pma_official_basis"] = "somebody else's instrument"
    _, refusals = R.check(spec, [r])
    assert refusals and "the rule does not reach it" in refusals[0]
    r.update(R.patch_for(spec))
    assert R.check(spec, [r]) == ([], [])


def test_a_half_applied_record_is_refused_not_reported_as_a_clean_noop():
    # The basis is right and every other patch field is stale. Checking the
    # basis alone would call this "already applied" and walk away from a record
    # the compiler never finished writing.
    spec = mini_spec([RESIDUAL])
    for field in ("pma_source_vintage", "pma_cap_verified"):
        r = rec(RESIDUAL, state="located")
        r.update(R.patch_for(spec))
        r[field] = "2019-01-01" if field == "pma_source_vintage" else False
        _, refusals = R.check(spec, [r])
        assert refusals, field
        assert "half applied" in refusals[0] and field in refusals[0], refusals


def test_the_already_counter_counts_records_and_never_goes_negative(tmp_path, capsys):
    # One code, two refusals (listed twice AND not reached): the old
    # `total - todo - refusals` arithmetic printed "already applied -1".
    dataset = tmp_path / "canonical.json"
    spec_path = tmp_path / "spec.json"
    dataset.write_text(
        json.dumps(
            {"metadata": {}, "data": [rec(RESIDUAL, status="TERTUTUP", maxa=0)]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    spec_path.write_text(
        json.dumps(mini_spec([RESIDUAL, RESIDUAL])), encoding="utf-8"
    )
    assert R.main(["--dataset", str(dataset), "--spec", str(spec_path)]) == R.EXIT_REFUSED
    line = capsys.readouterr().out.splitlines()[0]
    assert "already applied 0" in line, line


def test_a_duplicate_listing_is_refused():
    spec = mini_spec([RESIDUAL, RESIDUAL])
    _, refusals = R.check(spec, [rec(RESIDUAL)])
    assert f"{RESIDUAL}: listed twice" in refusals


def test_a_spec_with_no_sector_referral_block_refuses():
    # Not a style rule: a residual lot IS "the annexes do not name it", and that
    # reading is only available where the Perpres governs the sector at all. A
    # spec that never states which sectors it hands back has not done the check.
    spec = mini_spec([RESIDUAL])
    del spec["sector_referral"]
    _, refusals = R.check(spec, [rec(RESIDUAL)])
    assert any("no sector_referral block" in r for r in refusals)


def test_a_sector_referral_must_declare_which_kind_of_claim_it_makes():
    spec = mini_spec([RESIDUAL])
    spec["sector_referral"][0]["kind"] = "sector_law"
    _, refusals = R.check(spec, [rec(RESIDUAL)])
    assert any("kind 'sector_law' is not one of" in r for r in refusals)


def test_a_sector_referral_is_stated_per_division_not_per_code():
    spec = mini_spec([RESIDUAL])
    spec["sector_referral"][0]["divisions"] = ["64121"]
    _, refusals = R.check(spec, [rec(RESIDUAL)])
    assert any("is not a 2-digit" in r for r in refusals)


def test_an_empty_referral_field_refuses_instead_of_matching_nothing():
    spec = mini_spec([RESIDUAL])
    spec["sector_referral"][0]["why"] = ""
    _, refusals = R.check(spec, [rec(RESIDUAL)])
    assert any("empty why" in r for r in refusals)


def test_the_referral_reason_names_the_kind_so_the_two_are_never_read_as_one():
    # The finance leg is the INSTRUMENT's own sentence; the transport leg is our
    # own caution. A reader who confuses them either over-trusts a gap we
    # declared, or under-trusts an article that actually says this.
    assert R.sector_referral("64121", SPEC).startswith("instrument_referral:")
    assert R.sector_referral("49123", SPEC).startswith("unswept_sector_statute:")
    assert R.sector_referral("56101", SPEC) is None


def test_apply_writes_the_patch_and_leaves_the_verdict_alone(tmp_path):
    dataset = tmp_path / "canonical.json"
    spec_path = tmp_path / "spec.json"
    original = rec(RESIDUAL)
    original["pma_source"] = "Perpres 10/2021, 49/2021"
    original["uraian"] = "prosa da non toccare"
    dataset.write_text(
        json.dumps({"metadata": {}, "data": [original]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    spec_path.write_text(json.dumps(mini_spec([RESIDUAL])), encoding="utf-8")

    assert R.main(["--apply", "--dataset", str(dataset), "--spec", str(spec_path)]) == 0
    after = json.loads(dataset.read_text(encoding="utf-8"))["data"][0]
    assert after["pma_verification_status"] == "located"
    assert after["pma_official_basis"] == R.BASIS
    assert after["pma_source_vintage"] == "2021-05-25"
    assert after["pma_cap_verified"] is True
    assert (after["pma_status"], after["pma_max_asing"]) == ("TERBUKA", 100)
    assert after["uraian"] == "prosa da non toccare"
    assert after["pma_source"] == "Perpres 10/2021, 49/2021"
    assert "pma_kondisi" not in after and "pma_cap_note" not in after

    # Idempotent: the rule no longer reaches the record, and the already-applied
    # branch recognises its own basis instead of refusing.
    assert R.main(["--apply", "--dataset", str(dataset), "--spec", str(spec_path)]) == 0


# --- Pasal 2(2): the closure that names no code -------------------------------
# Raised by kimi-code/k3 HIGH (3), council round 1: the lot ships 13 chemical
# manufacturing codes, and Pasal 2(2)(e)/(f) close «industri pembuatan senjata
# kimia» and «industri bahan kimia industri dan industri bahan perusak lapisan
# ozon» by CATEGORY, naming no code — so no annex leg and no sibling leg can
# see them. Folded as an ENFORCED probe on the state's own per-code marker
# rather than as a hand exclusion, because excluding codes the rule never
# reaches would have been a claim about nothing (a stale exclusion).
CATEGORY_MARKED = {"20115", "20116", "20119", "20121"}
PERSYARATAN = (
    "Melampirkan Surat Pernyataan tidak memproduksi senjata kimia dan industri "
    "yang menghasilkan Bahan Perusak Ozon/BPO"
)


def test_the_category_probe_is_pinned_to_the_codes_the_state_actually_marks(by_code):
    block = SPEC["category_closure_probe"][0]
    assert set(block["marked_codes"]) == CATEGORY_MARKED
    marked = {
        code
        for code, record in by_code.items()
        if R.category_markers(record, block["markers"])
    }
    assert marked == CATEGORY_MARKED


def test_not_one_marked_code_is_in_the_lot_and_the_rule_cannot_reach_them(by_code):
    # And not because this spec excluded them: the Perpres partition already
    # owns all four — 20115 is named in an annex, 20116/20119/20121 are
    # Lampiran I priority — so they are outside the residual bucket entirely.
    assert CATEGORY_MARKED.isdisjoint(set(SPEC["items"]))
    assert CATEGORY_MARKED.isdisjoint(set(SPEC["excluded_codes"]))
    for code in sorted(CATEGORY_MARKED):
        assert by_code[code]["pma_verification_status"] == "declared_gap"


def test_no_lot_member_carries_a_category_marker(by_code):
    markers = SPEC["category_closure_probe"][0]["markers"]
    offenders = {
        code: R.category_markers(by_code[code], markers)
        for code in SPEC["items"]
        if R.category_markers(by_code[code], markers)
    }
    assert offenders == {}


def test_the_probe_is_blind_to_the_basis_the_compiler_writes_itself(by_code):
    # The basis quotes the closed category verbatim, so a probe reading the
    # whole record matches every member it has already shipped, against itself.
    # Measured: the first run after the basis was extended withheld all 330.
    shipped = by_code[SPEC["items"][0]]
    assert "senjata kimia" in shipped["pma_official_basis"].lower()
    assert R.category_markers(shipped, ["senjata kimia", "perusak ozon"]) == []
    assert "pma_official_basis" in R.PROBE_BLIND_FIELDS


def test_the_basis_says_how_the_category_items_were_tested():
    assert "Pasal 2(2) items close an ACTIVITY and name no code" in R.BASIS
    assert "Bahan Perusak Ozon/BPO" in R.BASIS
    assert "does not clear a closed ACTIVITY carried on under an open code" in R.BASIS


def test_a_code_carrying_a_category_marker_is_withheld_not_published():
    spec = mini_spec([RESIDUAL])
    # The census must AGREE first — a marked code is pinned and then withheld;
    # pinning it is not permission to publish it.
    spec["category_closure_probe"][0]["marked_codes"] = [RESIDUAL]
    marked = rec(RESIDUAL)
    marked["per_skala"] = [
        {"skala_usaha": ["Besar"], "persyaratan": [PERSYARATAN]},
    ]
    _, refusals = R.check(spec, [marked])
    assert refusals and "category-closure probe" in refusals[0]
    assert "never publish it open by absence" in refusals[0]


def test_a_spec_with_no_category_probe_refuses():
    spec = mini_spec([RESIDUAL])
    del spec["category_closure_probe"]
    _, refusals = R.check(spec, [rec(RESIDUAL)])
    assert any("no category_closure_probe block" in r for r in refusals)


def test_an_empty_marker_list_refuses_instead_of_probing_nothing():
    spec = mini_spec([RESIDUAL])
    spec["category_closure_probe"][0]["markers"] = []
    _, refusals = R.check(spec, [rec(RESIDUAL)])
    assert any("markers must be a non-empty list" in r for r in refusals)


def test_an_empty_probe_field_refuses_instead_of_looking_documented():
    spec = mini_spec([RESIDUAL])
    spec["category_closure_probe"][0]["finding"] = ""
    _, refusals = R.check(spec, [rec(RESIDUAL)])
    assert any("empty finding" in r for r in refusals)


def test_the_category_census_refuses_when_the_catalogue_drifts():
    # A code that ENTERS the closed category after the finding was written must
    # stop the run, not be published under a finding that predates it.
    spec = mini_spec([RESIDUAL])
    spec["category_closure_probe"][0]["marked_codes"] = [SIBLING]
    _, refusals = R.check(spec, [rec(RESIDUAL)])
    assert any("the catalogue marks [] but the spec pins" in r for r in refusals)


def test_a_patch_field_the_probe_still_reads_is_refused():
    # The blindness list and the patch must move together: a new written field
    # the probe still reads would let our own prose count as government evidence.
    spec = mini_spec([RESIDUAL])
    original = R.PROBE_BLIND_FIELDS
    R.PROBE_BLIND_FIELDS = tuple(f for f in original if f != "pma_official_basis")
    try:
        _, refusals = R.check(spec, [rec(RESIDUAL)])
    finally:
        R.PROBE_BLIND_FIELDS = original
    assert any("PROBE_BLIND_FIELDS does not list it" in r for r in refusals)


# --- the annex title collision leg -------------------------------------------
# Why it exists: every other leg reasons about the code NUMBER, and BPS re-scopes
# numbers between vintages while a Perpres cap attaches to the ACTIVITY the annex
# names. 2020-58120 was «Penerbitan Direktori dan Mailing List»; in 2025 it IS
# «Penerbitan Surat Kabar», the activity Lampiran III entry #33 caps at 0% at
# establishment under the number 58130. The first candidate shipped it TERBUKA
# with a VERIFIED 100% — caught on disk by the gate, not by any suite.

PRESS_ROW_ACTIVITY = "Penerbitan surat kabar, majalah, dan buletin (pers)"


def test_the_press_code_is_out_of_the_lot_and_the_capped_row_is_why(records):
    reach = R.reached(SPEC, records)
    held = R.withheld(SPEC, records, reach)
    assert "58120" in reach, "the rule still reaches it — this leg is what holds it"
    assert "58120" not in SPEC["items"]
    why = held["58120"]
    assert why.startswith("annex title collision: Lampiran III entry #33")
    assert "0%" in why and "58130" in why


def test_the_collision_census_is_pinned_and_reads_only_the_capped_annex(by_code):
    (block,) = SPEC["annex_title_collision_probe"]
    assert block["artifact"] == "data/kbli-filiera/perpres-foreign-caps.json"
    measured = {c for c, r in by_code.items() if R.annex_title_collision(c, r)}
    assert measured == set(block["collided_codes"])
    # Eight of the nine are the division 50/53 sea-transport renumbering, which
    # the unswept-statute leg already covers by division: the probe corroborates
    # a class the compiler knew, and adds exactly one code nothing else saw.
    assert {c for c in measured if c[:2] in {"50", "53"}} == measured - {"58120"}


def test_a_title_that_is_a_capped_rows_activity_is_withheld_and_names_the_row():
    spec = mini_spec([])
    spec["annex_title_collision_probe"][0]["collided_codes"] = [RESIDUAL]
    r = rec(RESIDUAL)
    r["judul"] = PRESS_ROW_ACTIVITY.upper()
    held = R.withheld(spec, [r], {RESIDUAL})
    assert "annex title collision: Lampiran III entry #33" in held[RESIDUAL]
    assert "58130" in held[RESIDUAL] and "0%" in held[RESIDUAL]
    # Case and punctuation are the only things that differ between the two
    # vintages of this name, so the match must survive both.
    assert R.check(spec, [r]) == ([], [])


def test_listing_a_collided_code_refuses_instead_of_shipping_it():
    spec = mini_spec([RESIDUAL])
    spec["annex_title_collision_probe"][0]["collided_codes"] = [RESIDUAL]
    r = rec(RESIDUAL)
    r["judul"] = PRESS_ROW_ACTIVITY
    todo, refusals = R.check(spec, [r])
    assert todo == [] and refusals


def test_the_probe_ignores_the_row_filed_under_the_code_itself(by_code):
    # 58130's own Lampiran III row must not withhold 58130: being NAMED by an
    # annex is what `named-in-annex` is for, and reading it as a collision would
    # turn every correctly-capped code into a refusal.
    assert R.annex_title_collision("58130", {"judul": PRESS_ROW_ACTIVITY}) is None
    assert R.annex_title_collision(RESIDUAL, {"judul": "Sintetico"}) is None
    assert R.annex_title_collision(RESIDUAL, {"judul": ""}) is None


def test_a_moved_collision_census_refuses_instead_of_writing():
    spec = mini_spec([RESIDUAL])
    spec["annex_title_collision_probe"][0]["collided_codes"] = ["00000"]
    _, refusals = R.check(spec, [rec(RESIDUAL)])
    assert any("the catalogue collides on" in x for x in refusals), refusals


def test_a_probe_pointed_at_another_annex_refuses():
    spec = mini_spec([RESIDUAL])
    spec["annex_title_collision_probe"][0]["artifact"] = (
        "data/kbli-filiera/perpres-umkm-reservation.json"
    )
    _, refusals = R.check(spec, [rec(RESIDUAL)])
    assert any("this probe reads the foreign-cap annex" in x for x in refusals), refusals


def test_removing_the_probe_refuses_rather_than_shipping_the_class():
    spec = mini_spec([RESIDUAL])
    spec.pop("annex_title_collision_probe")
    _, refusals = R.check(spec, [rec(RESIDUAL)])
    assert any("no annex_title_collision_probe block" in x for x in refusals), refusals


# --- the sector-law closure guard --------------------------------------------
# Not a subtraction: an INVARIANT over whatever leg is doing the subtracting.
# 58120 is held by the probe above and 60101/60201/69104 are out of reach on the
# Bali and eligibility filters — i.e. by accident. Lot 2 lifts the Bali filter.


def test_the_closure_guard_names_the_four_codes_and_their_statutes():
    (block,) = SPEC["sector_law_closures"]
    assert block["codes"] == ["58120", "60101", "60201", "69104"]
    for statute in ("UU 40/1999", "UU 32/2002", "UU 30/2004"):
        assert statute in block["instrument"]
    assert not set(block["codes"]) & {str(c) for c in SPEC["items"]}


def test_a_closure_code_listed_as_a_lot_member_refuses(records):
    spec = json.loads(json.dumps(SPEC))
    spec["items"] = [*spec["items"], "58120"]
    _, refusals = R.check(spec, records)
    assert any("58120: sector_law_closures[0] names it" in x for x in refusals), refusals


def test_a_closure_code_reached_with_nothing_holding_it_refuses():
    # The gate's standing finding, made executable: when a later lot lifts the
    # Bali cut, 60101 becomes eligible and no leg covers division 60.
    spec = mini_spec([RESIDUAL])
    records = [rec(RESIDUAL), rec("60101")]
    _, refusals = R.check(spec, records)
    assert any(
        "60101: sector_law_closures[0] names it and the rule now REACHES it" in x
        for x in refusals
    ), refusals


def test_the_closure_guard_is_silent_while_something_else_holds_the_code(records):
    # Innocence, and the reason the guard is an invariant and not a leg: today
    # 58120 IS reached, and the run is clean because the probe holds it.
    todo, refusals = R.check(SPEC, records)
    assert refusals == []
    assert "58120" not in todo


def test_a_closure_naming_a_code_kbli_2025_does_not_have_is_stale():
    spec = mini_spec([RESIDUAL])
    spec["sector_law_closures"][0]["codes"] = ["99999"]
    _, refusals = R.check(spec, [rec(RESIDUAL)])
    assert any("99999 is not in KBLI 2025" in x for x in refusals), refusals


def test_removing_the_closure_guard_refuses():
    spec = mini_spec([RESIDUAL])
    spec.pop("sector_law_closures")
    _, refusals = R.check(spec, [rec(RESIDUAL)])
    assert any("no sector_law_closures block" in x for x in refusals), refusals



def test_the_spacecraft_code_ships_because_an_adjudication_says_the_annex_misses_it():
    """The on-disk gate's HIGH on PR #6783, answered in the NEGATIVE.

    30303 «Industri Wahana Antariksa» descends from KBLI-2020 30300, which
    Lampiran III entry #7 caps at 49%. It ships here at TERBUKA/100 anyway, and
    the licence for that is not absence — it is a hand adjudication in the tree
    saying the annex activity is a NEIGHBOUR of this code, not inside it. That
    is a load-bearing dependency of this lot, so it is pinned: delete the
    adjudication or reword its reason and this test goes red BEFORE the lot
    silently starts resting on nothing.
    """
    from perpres_slice_disclosure_relation import ADJACENT_NOT_CONTAINED

    assert "30303" in SPEC["items"]
    assert "30303" in ADJACENT_NOT_CONTAINED
    reason = ADJACENT_NOT_CONTAINED["30303"]
    assert "spacecraft" in reason and "military aircraft" in reason
    # The ancestor link is real — the exclusion is a reading of the annex TEXT,
    # not a missing crosswalk row. If the ancestry were absent the adjudication
    # would be answering a question nobody asked.
    caps = {str(r["kbli_2020"]) for r in json.loads(R.CAPS.read_text(encoding="utf-8"))["rows"]}
    assert "30300" in caps


def test_the_sibling_class_is_declared_and_measured_empty(by_code):
    """`instrument_reached_sibling`: 135 codes, 3 cap-linked, 0 true positives.

    A negative result is worth shipping only if it says how it was measured,
    so the block names all three and this test re-derives the discriminator:
    a 4-digit PREFIX sibling is not a lineage relation, and only the lineage
    one can carry an annex row down.
    """
    block = SPEC["deferred"]["instrument_reached_sibling"]
    assert block["codes"] == 135
    for code in ("10762", "30112", "30303"):
        assert code in block["why"] and code in SPEC["items"]
    # 10762 and 30112 do not descend from the capped code that shares their
    # first four digits; 30303 does, which is why only it needed adjudicating.
    assert by_code["10762"]["bps_2020_ancestors"]["codes"] == ["10763"]
    assert by_code["30112"]["bps_2020_ancestors"]["codes"] == ["30112"]
    assert by_code["30303"]["bps_2020_ancestors"]["codes"] == ["30300"]


# ---------------------------------------------------------------- lot 2 (ATTENZIONE_FASCIA_BALI)

# The lot cuts on the Bali axis (module docstring, "WHY A LOT"): lot 1 unveils
# OK_or_HIGHER_RISK, lot 2 unveils ATTENZIONE_FASCIA_BALI. Every other rule
# predicate is identical — REQUIRED_RULE_BY_LOT pins that, and these tests pin
# that a spec cannot smuggle a widened predicate past the per-lot pin.

LOT2_DEFERRED = {
    "adjudicated_sibling": 6,
    "annex_title_collision": 0,
    "body_stated_category": 0,
    "instrument_referral_pasal_11_2": 1,
    "legacy_pma_prose": 1,
    "unswept_sector_statute": 4,
}

LOT2_SIBLING_WITHHELD = {"16222", "21023", "32202", "59132", "91112", "91122"}
LOT2_UNSWEPT_WITHHELD = {"35133", "35159", "49297", "52213"}
LOT2_REFERRAL_WITHHELD = {"64210"}


def mini_spec2(items):
    """`mini_spec`'s lot-2 twin, built off the real lot-2 spec instead of lot 1."""
    spec = json.loads(json.dumps(SPEC2))
    spec["items"] = items
    spec["excluded_codes"] = {}
    for block in spec.get("category_closure_probe", []):
        block["marked_codes"] = []
    for block in spec.get("annex_title_collision_probe", []):
        block["collided_codes"] = []
    return spec


def test_an_unknown_lot_refuses():
    spec = mini_spec2([RESIDUAL])
    spec["lot"] = 99
    _, refusals = R.check(spec, [rec(RESIDUAL, bali="ATTENZIONE_FASCIA_BALI")])
    assert refusals == [
        "spec lot 99 is not a known lot — REQUIRED_RULE_BY_LOT has [1, 2], and an "
        "unknown lot cannot be trusted to pin the right predicates"
    ]


def test_a_lot_1_spec_whose_rule_drifts_to_the_lot_2_bali_status_refuses():
    # Guilt: a lot cannot widen ANY predicate just because it is allowed to
    # name a different Bali status — the whole rule is pinned per lot, not one
    # field of it.
    spec = mini_spec([RESIDUAL])
    spec["rule"]["l4_bali_status"] = "ATTENZIONE_FASCIA_BALI"
    _, refusals = R.check(spec, [rec(RESIDUAL, bali="ATTENZIONE_FASCIA_BALI")])
    assert refusals == [
        "rule.l4_bali_status is 'ATTENZIONE_FASCIA_BALI', not 'OK_or_HIGHER_RISK' "
        "— this compiler only writes the residual class, and a spec cannot widen it"
    ]


def test_a_lot_2_spec_whose_rule_drifts_to_the_lot_1_bali_status_refuses():
    spec = mini_spec2([RESIDUAL])
    spec["rule"]["l4_bali_status"] = "OK_or_HIGHER_RISK"
    _, refusals = R.check(spec, [rec(RESIDUAL, bali="OK_or_HIGHER_RISK")])
    assert refusals == [
        "rule.l4_bali_status is 'OK_or_HIGHER_RISK', not 'ATTENZIONE_FASCIA_BALI' "
        "— this compiler only writes the residual class, and a spec cannot widen it"
    ]


def test_the_lot_1_spec_still_validates_byte_for_byte_against_pin_1(records):
    # Innocence: the per-lot pin did not move lot 1's own behaviour at all.
    assert R.check(SPEC, records) == ([], [])
    assert SPEC["rule"] == R.REQUIRED_RULE_BY_LOT[1]


def test_the_lot_2_spec_is_260_codes_and_the_deferred_arithmetic_is_declared():
    codes = [str(c) for c in SPEC2["items"]]
    assert len(codes) == 260 and len(set(codes)) == 260
    assert SPEC2["lot"] == 2 and SPEC2["vintage"] == "2021-05-25"
    assert {k: v["codes"] for k, v in SPEC2["deferred"].items()} == LOT2_DEFERRED
    # 260 shipped + 6 sibling + 4 unswept statute + 1 finance referral = the
    # 271 the rule reaches; the 272-vs-271 gap (62900, legacy prose) is its
    # own deferred entry, not a term of the reach arithmetic.
    withheld_count = (
        LOT2_DEFERRED["adjudicated_sibling"]
        + LOT2_DEFERRED["unswept_sector_statute"]
        + LOT2_DEFERRED["instrument_referral_pasal_11_2"]
    )
    assert len(codes) + withheld_count == 271
    assert SPEC2["excluded_codes"] == {}


def test_the_lot_2_spec_validates_against_the_real_canonical(records):
    # Lot 2 is already shipped on this canonical (same PR that adds this
    # test applies it) — a clean no-op, exactly like lot 1's own
    # `test_rerun_on_the_shipped_canonical_is_a_clean_noop`.
    assert R.check(SPEC2, records) == ([], [])


def test_every_lot_2_item_is_attenzione_fascia_bali_and_unblocked(by_code):
    for code in SPEC2["items"]:
        record = by_code[str(code)]
        bali = record.get("l4_bali") or {}
        assert bali.get("status") == "ATTENZIONE_FASCIA_BALI", code
        assert bali.get("blocked") is False, code
        assert R.legacy_prose(record) == [], code
        assert record.get("pma_status") == "TERBUKA", code
        assert record.get("pma_max_asing") == 100, code


def test_lot_1_and_lot_2_partition_on_the_bali_axis(by_code):
    lot1 = {str(c) for c in SPEC["items"]}
    lot2 = {str(c) for c in SPEC2["items"]}
    assert not (lot1 & lot2)
    # And every lot-2 member's Bali status genuinely differs from lot 1's own
    # rule, re-derived from the canonical rather than assumed from disjointness.
    for code in lot2:
        assert by_code[code]["l4_bali"]["status"] != "OK_or_HIGHER_RISK"
    for code in lot1:
        assert by_code[code]["l4_bali"]["status"] != "ATTENZIONE_FASCIA_BALI"


def test_a_lot_2_withheld_code_per_leg_is_absent_from_items():
    items = {str(c) for c in SPEC2["items"]}
    for code in (*LOT2_SIBLING_WITHHELD, *LOT2_UNSWEPT_WITHHELD, *LOT2_REFERRAL_WITHHELD):
        assert code not in items, code


def test_a_lot_2_adjudicated_sibling_withholds_the_code_and_says_why():
    spec = mini_spec2([RESIDUAL])
    sibling = rec(SIBLING, status="TERTUTUP", maxa=0, state="located")
    records = [rec(RESIDUAL, bali="ATTENZIONE_FASCIA_BALI"), sibling]
    _, refusals = R.check(spec, records)
    assert refusals == [
        f"{RESIDUAL}: listed in the lot but withheld — adjudicated 4-digit "
        f"sibling(s) {SIBLING} — an instrument reaches this subgolongan, so "
        "absence is not evidence of openness"
    ]


def test_lot_2_apply_writes_the_patch_and_rerun_is_a_clean_noop(tmp_path):
    dataset = tmp_path / "canonical.json"
    spec_path = tmp_path / "spec.json"
    original = rec(RESIDUAL, bali="ATTENZIONE_FASCIA_BALI")
    dataset.write_text(
        json.dumps({"metadata": {}, "data": [original]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    spec_path.write_text(json.dumps(mini_spec2([RESIDUAL])), encoding="utf-8")

    assert R.main(["--apply", "--dataset", str(dataset), "--spec", str(spec_path)]) == 0
    after = json.loads(dataset.read_text(encoding="utf-8"))["data"][0]
    assert after["pma_verification_status"] == "located"
    assert after["pma_official_basis"] == R.BASIS
    assert after["l4_bali"]["status"] == "ATTENZIONE_FASCIA_BALI"

    # Byte-for-byte idempotent on a second apply — the whole point of A1.
    before_bytes = dataset.read_bytes()
    assert R.main(["--apply", "--dataset", str(dataset), "--spec", str(spec_path)]) == 0
    assert dataset.read_bytes() == before_bytes
