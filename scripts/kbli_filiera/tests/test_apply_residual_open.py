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

# The lot's deferred groups, as the spec declares them. Pinned here because the
# arithmetic is the honest half of the claim, and it has two axes: the rule
# REACHES 507 codes, of which 330 ship and 177 are withheld (61 + 68 + 29 + 19);
# the other 537 never enter the reach at all (Bali 331, legacy prose 36, no
# Besar row 12, no PP 28 rows 158). A lot that quietly grew breaks this first.
DEFERRED = {
    "adjudicated_sibling": 29,
    "bali_attenzione_fascia": 272,
    "bali_bloccato_dipende_scope": 31,
    "bali_chiuso_bali": 22,
    "bali_other": 6,
    "body_stated_category": 19,
    "legacy_pma_prose": 36,
    "residual_besar_absent": 12,
    "residual_besar_unobserved": 158,
    "sector_law_referral_pasal_11_2": 61,
    "sector_statute_unswept": 68,
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


def test_the_lot_is_330_codes_and_the_deferred_arithmetic_is_declared():
    codes = [str(c) for c in SPEC["items"]]
    assert len(codes) == 330 and len(set(codes)) == 330
    assert {k: v["codes"] for k, v in SPEC["deferred"].items()} == DEFERRED
    assert SPEC["lot"] == 1 and SPEC["vintage"] == "2021-05-25"
    # 330 shipped + 61 Pasal 11(2) + 68 unswept statute + 29 sibling
    # + 19 hand-excluded = the 507 the rule reaches.
    withheld_count = (
        DEFERRED["sector_law_referral_pasal_11_2"] + DEFERRED["sector_statute_unswept"]
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
    assert set(held) == SIBLING_WITHHELD | set(SPEC["excluded_codes"]) | sector
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
