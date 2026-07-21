"""Tests for the GARUDA-FILIERA Fase 1 canonical cure compiler.

Covers the v2 extension (2026-07-17): the compiler now also rewrites the
client-facing ``intel_2026.whatYouNeed`` to an honest-gap text, IN ADDITION to
the per_skala detach. The two parts must be independently idempotent — the 7
codes are already detached (#2589), so a whatYouNeed-only apply must NOT clobber
the preserved disputed block.

The whatYouNeed texts were authored from each code's image-verified data_note and
passed a 3-round Codex cross-family adversarial gate; ``_honest_gap_violations``
pins that discipline (guilt + innocence per scar #3) so a future edit that
reintroduces a forbidden pattern (an unproven "100%", a stale risk assertion,
a missing verify-with-team pointer) fails CI.
"""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

import pytest

FILIERA = Path(__file__).resolve().parents[1]
if str(FILIERA) not in sys.path:
    sys.path.insert(0, str(FILIERA))

import cure_canonical_collisions as cure  # noqa: E402

DISPUTED_KEY = "per_skala_disputed_pp28_collision"


def _honest_gap_violations(text: str) -> list[str]:
    """Return the list of honest-gap rule violations in a whatYouNeed text.

    Empty list == compliant. Encodes the rules the Codex gate enforced:
    no unproven ownership %, no retained/asserted risk tier, must preserve
    PMA-open, must declare the gap, must route the client to verification.
    """
    v: list[str] = []
    low = text.lower()
    if "100%" in text or "100 %" in text:
        v.append("asserts an unproven ownership percentage")
    # a CURRENT risk-tier assertion (the stale collision-derived value) — the
    # cured text may only say risk is NOT defined, never state a tier.
    if re.search(r"(medium[- ]high|medium[- ]low|high risk|low risk|menengah|tinggi|rendah)", low):
        v.append("asserts/retains a specific risk tier")
    if "pma" not in low:
        v.append("drops the preserved PMA-open status")
    if not re.search(r"(not yet reliably defined|cannot reliably be applied|unconfirmed)", low):
        v.append("does not declare the risk/licensing gap")
    if "bali zero team" not in low:
        v.append("does not route the client to team verification")
    if len(text) < 120:
        v.append("too short to be a real disclosure")
    return v


def test_spec_ships_honest_gap_whatyouneed_for_every_code() -> None:
    spec = cure.load_spec(cure.DEFAULT_SPEC)
    codes = {e["code"]: e for e in spec["codes"]}
    # 6, not 7 (2026-07-18): 49213 graduated from detach to a per-ancestor
    # RESTORE (cure_restore_per_ancestor.py + cure_specs/restore_49213.json)
    # and was removed from this spec's codes — see this file's own "GRADUATION"
    # note in _doc.
    assert len(codes) == 6, "Fase 1 spec should carry exactly the 6 remaining quarantined codes"
    assert "49213" not in codes, "49213 graduated to the restore compiler — must not remain here"
    for code, entry in codes.items():
        wyn = entry.get("whatYouNeed")
        assert isinstance(wyn, str) and wyn, f"{code}: spec missing whatYouNeed"
        violations = _honest_gap_violations(wyn)
        assert not violations, f"{code}: honest-gap violations {violations}\n---\n{wyn}"


def test_guilt_a_bad_text_is_flagged() -> None:
    # INNOCENCE control for the guard: a legit honest-gap text passes (above);
    # GUILT: a text that reintroduces the disease must be caught.
    bad = (
        "Nationally, this activity is 100% open to foreign ownership. It is "
        "classified as medium-high risk, so expect closer scrutiny. Register via NIB."
    )
    violations = _honest_gap_violations(bad)
    assert "asserts an unproven ownership percentage" in violations
    assert "asserts/retains a specific risk tier" in violations
    assert "does not route the client to team verification" in violations


def _record(*, per_skala, whatYouNeed="stale prose", disputed=False):
    rec = {
        "kode_kbli_2025": "51103",
        "judul": "X",
        "per_skala": per_skala,
        "pma_status": "TERBUKA",
        "intel_2026": {"whatItMeans": "keep", "whatYouNeed": whatYouNeed},
    }
    if disputed:
        rec[DISPUTED_KEY] = [{"kategori_risiko": "Tinggi"}]
    return rec


def test_apply_sets_whatyouneed_on_already_detached_without_clobbering_disputed() -> None:
    original_disputed = [{"kategori_risiko": "Tinggi", "src": "collision"}]
    rec = {
        "kode_kbli_2025": "51103",
        "per_skala": [],
        DISPUTED_KEY: copy.deepcopy(original_disputed),
        "pma_status": "TERBUKA",
        "intel_2026": {"whatItMeans": "keep me", "whatYouNeed": "STALE medium-high risk"},
        "_data_note": "old note",
    }
    entry = {"code": "51103", "data_note": "new note", "whatYouNeed": "GAP text"}
    out = cure.apply_cure(rec, entry, DISPUTED_KEY)

    assert out["per_skala"] == []
    assert out[DISPUTED_KEY] == original_disputed, "disputed block must NOT be clobbered with []"
    assert out["intel_2026"]["whatYouNeed"] == "GAP text"
    assert out["intel_2026"]["whatItMeans"] == "keep me", "other intel_2026 fields preserved"
    assert out["_data_note"] == "new note"


def test_apply_detach_and_whatyouneed_together_when_not_yet_detached() -> None:
    rec = _record(per_skala=[{"kategori_risiko": "Tinggi"}])
    entry = {"code": "51103", "data_note": "note", "whatYouNeed": "GAP text"}
    out = cure.apply_cure(rec, entry, DISPUTED_KEY)
    assert out["per_skala"] == []
    assert out[DISPUTED_KEY] == [{"kategori_risiko": "Tinggi"}], "current per_skala preserved in disputed key"
    assert out["intel_2026"]["whatYouNeed"] == "GAP text"
    assert out["_data_note"] == "note"


def test_plan_apply_when_detached_but_whatyouneed_differs() -> None:
    rec = _record(per_skala=[], whatYouNeed="stale", disputed=True)
    entry = {"code": "51103", "data_note": "n", "whatYouNeed": "fresh gap"}
    plan = cure.plan_cure(rec, entry, DISPUTED_KEY)
    assert plan.status == "apply"
    assert plan.needs_whatyouneed is True
    assert plan.needs_detach is False


def test_plan_already_cured_when_detached_and_whatyouneed_matches() -> None:
    rec = _record(per_skala=[], whatYouNeed="fresh gap", disputed=True)
    entry = {"code": "51103", "data_note": "n", "whatYouNeed": "fresh gap"}
    plan = cure.plan_cure(rec, entry, DISPUTED_KEY)
    assert plan.status == "already-cured"


def test_plan_ambiguous_skip_when_empty_and_no_disputed_key() -> None:
    rec = _record(per_skala=[], whatYouNeed="stale", disputed=False)
    entry = {"code": "51103", "data_note": "n", "whatYouNeed": "fresh gap"}
    plan = cure.plan_cure(rec, entry, DISPUTED_KEY)
    assert plan.status == "ambiguous-skip", "unrecognised prior state must not be touched"


def test_apply_raises_when_intel_missing_but_whatyouneed_requested() -> None:
    rec = {"kode_kbli_2025": "51103", "per_skala": []}
    entry = {"code": "51103", "data_note": "n", "whatYouNeed": "gap"}
    with pytest.raises(cure.CureError):
        cure.apply_cure(rec, entry, DISPUTED_KEY)


# ---------------------------------------------------------------------------
# Batch A Lot 2 extension (2026-07-18): status_mapping_correction /
# whatChanged_correction — the mapping_metadata_false class (e.g. 47771).
# ---------------------------------------------------------------------------


def test_plan_flags_status_mapping_and_whatchanged_correction() -> None:
    rec = _record(per_skala=[{"kategori_risiko": "Rendah"}])
    rec["status_mapping"] = "MATCH_LANGSUNG"
    rec["intel_2026"]["whatChanged"] = "Unchanged from KBLI 2020 — direct match."
    entry = {
        "code": "51103",
        "data_note": "n",
        "whatYouNeed": "gap",
        "status_mapping_correction": "MATCH_CON_AGGREGAZIONE",
        "whatChanged_correction": "Merged from multiple KBLI 2020 codes.",
    }
    plan = cure.plan_cure(rec, entry, DISPUTED_KEY)
    assert plan.status == "apply"
    assert plan.needs_detach is True
    assert plan.needs_status_mapping is True
    assert plan.needs_whatchanged is True


def test_apply_sets_status_mapping_and_whatchanged_together_with_detach() -> None:
    rec = _record(per_skala=[{"kategori_risiko": "Rendah"}])
    rec["status_mapping"] = "MATCH_LANGSUNG"
    rec["intel_2026"]["whatChanged"] = "Unchanged from KBLI 2020 — direct match."
    entry = {
        "code": "51103",
        "data_note": "n",
        "whatYouNeed": "gap",
        "status_mapping_correction": "MATCH_CON_AGGREGAZIONE",
        "whatChanged_correction": "Merged from multiple KBLI 2020 codes.",
    }
    out = cure.apply_cure(rec, entry, DISPUTED_KEY)
    assert out["per_skala"] == []
    assert out[DISPUTED_KEY] == [{"kategori_risiko": "Rendah"}]
    assert out["status_mapping"] == "MATCH_CON_AGGREGAZIONE"
    assert out["intel_2026"]["whatChanged"] == "Merged from multiple KBLI 2020 codes."
    assert out["intel_2026"]["whatYouNeed"] == "gap"


def test_plan_metadata_only_correction_when_already_detached() -> None:
    """A record already detached (prior lot) can still need a metadata-only
    correction with no further per_skala change — needs_detach stays False."""
    rec = _record(per_skala=[], whatYouNeed="gap", disputed=True)
    rec["status_mapping"] = "MATCH_LANGSUNG"
    entry = {
        "code": "51103",
        "data_note": "n",
        "whatYouNeed": "gap",
        "status_mapping_correction": "MATCH_CON_AGGREGAZIONE",
    }
    plan = cure.plan_cure(rec, entry, DISPUTED_KEY)
    assert plan.status == "apply"
    assert plan.needs_detach is False
    assert plan.needs_whatyouneed is False
    assert plan.needs_status_mapping is True

    out = cure.apply_cure(rec, entry, DISPUTED_KEY)
    assert out["per_skala"] == []
    assert out[DISPUTED_KEY] == [{"kategori_risiko": "Tinggi"}], "prior disputed block untouched"
    assert out["status_mapping"] == "MATCH_CON_AGGREGAZIONE"


def test_plan_already_cured_when_metadata_correction_matches() -> None:
    rec = _record(per_skala=[], whatYouNeed="gap", disputed=True)
    rec["status_mapping"] = "MATCH_CON_AGGREGAZIONE"
    entry = {
        "code": "51103",
        "data_note": "n",
        "whatYouNeed": "gap",
        "status_mapping_correction": "MATCH_CON_AGGREGAZIONE",
    }
    plan = cure.plan_cure(rec, entry, DISPUTED_KEY)
    assert plan.status == "already-cured"


def test_apply_raises_when_intel_missing_but_whatchanged_requested() -> None:
    rec = {"kode_kbli_2025": "51103", "per_skala": []}
    entry = {"code": "51103", "data_note": "n", "whatChanged_correction": "x"}
    with pytest.raises(cure.CureError):
        cure.apply_cure(rec, entry, DISPUTED_KEY)


def test_lot1_and_fase1_specs_unaffected_by_absent_metadata_keys() -> None:
    """Entries with no status_mapping_correction/whatChanged_correction keys
    (every Fase 1 and Lot 1 entry) must behave exactly as before — pure no-op
    on the new fields."""
    rec = _record(per_skala=[], whatYouNeed="gap", disputed=True)
    rec["status_mapping"] = "MATCH_LANGSUNG"
    entry = {"code": "51103", "data_note": "n", "whatYouNeed": "gap"}
    plan = cure.plan_cure(rec, entry, DISPUTED_KEY)
    assert plan.status == "already-cured"
    assert plan.needs_status_mapping is False
    assert plan.needs_whatchanged is False
    out = cure.apply_cure(rec, entry, DISPUTED_KEY)
    assert out["status_mapping"] == "MATCH_LANGSUNG", "untouched when spec supplies no correction"


# ---------------------------------------------------------------------------
# Standalone metadata-fix extension (2026-07-19): "action": "metadata_only"
# and pp28_sources_correction — for OSS-native codes (52101/46100/10433)
# whose HEALTHY, non-empty per_skala must NEVER be detached even though a
# crosswalk-metadata defect needs curing.
# ---------------------------------------------------------------------------


def test_plan_metadata_only_action_forces_needs_detach_false_on_healthy_per_skala() -> None:
    """Without action='metadata_only', a non-empty per_skala ALWAYS triggers
    needs_detach (existing behavior, unaffected). WITH it, needs_detach must
    stay False even though per_skala is non-empty and healthy."""
    healthy_rows = [{"skala_usaha": ["Mikro"], "kategori_risiko": "Rendah"}]
    rec = _record(per_skala=healthy_rows)
    rec["status_mapping"] = "MATCH_LANGSUNG"
    entry = {
        "code": "51103",
        "action": "metadata_only",
        "data_note": "n",
        "status_mapping_correction": "MATCH_CON_AGGREGAZIONE",
    }
    plan = cure.plan_cure(rec, entry, DISPUTED_KEY)
    assert plan.status == "apply"
    assert plan.needs_detach is False
    assert plan.metadata_only is True
    assert plan.needs_status_mapping is True


def test_apply_metadata_only_leaves_healthy_per_skala_byte_invariant() -> None:
    """The core guilt+innocence guarantee: per_skala must be byte-identical
    before and after a metadata_only apply, even though status_mapping and
    pp28_sources are corrected in the same call."""
    healthy_rows = [
        {"skala_usaha": ["Mikro"], "kategori_risiko": "Rendah", "persyaratan": ["NIB"]},
        {"skala_usaha": ["Kecil"], "kategori_risiko": "Menengah Rendah", "persyaratan": ["NIB", "SS"]},
    ]
    original_rows = copy.deepcopy(healthy_rows)
    rec = _record(per_skala=healthy_rows)
    rec["status_mapping"] = "MATCH_LANGSUNG"
    rec["pp28_sources"] = ["52101"]
    entry = {
        "code": "51103",
        "action": "metadata_only",
        "data_note": "n",
        "status_mapping_correction": "MATCH_CON_AGGREGAZIONE",
        "whatChanged_correction": "Merged from multiple KBLI 2020 codes.",
    }
    out = cure.apply_cure(rec, entry, DISPUTED_KEY)
    assert out["per_skala"] == original_rows, "per_skala must be byte-invariant under metadata_only"
    assert DISPUTED_KEY not in out, "metadata_only must never write a disputed key"
    assert out["status_mapping"] == "MATCH_CON_AGGREGAZIONE"
    assert out["intel_2026"]["whatChanged"] == "Merged from multiple KBLI 2020 codes."
    assert out["pp28_sources"] == ["52101"], "pp28_sources untouched when no pp28_sources_correction given"


def test_plan_pp28_sources_correction_flags_needs_pp28_sources() -> None:
    rec = _record(per_skala=[{"kategori_risiko": "Rendah"}])
    rec["pp28_sources"] = ["10433", "10490"]
    entry = {
        "code": "51103",
        "action": "metadata_only",
        "data_note": "n",
        "pp28_sources_correction": ["10433"],
    }
    plan = cure.plan_cure(rec, entry, DISPUTED_KEY)
    assert plan.status == "apply"
    assert plan.needs_detach is False
    assert plan.needs_pp28_sources is True


def test_apply_pp28_sources_correction_sets_new_list_and_leaves_per_skala_untouched() -> None:
    healthy_rows = [{"skala_usaha": ["Mikro"], "kategori_risiko": "Menengah"}]
    original_rows = copy.deepcopy(healthy_rows)
    rec = _record(per_skala=healthy_rows)
    rec["pp28_sources"] = ["10433", "10490"]
    entry = {
        "code": "10433",
        "action": "metadata_only",
        "data_note": "10490 belongs to 10419, not 10433",
        "pp28_sources_correction": ["10433"],
    }
    out = cure.apply_cure(rec, entry, DISPUTED_KEY)
    assert out["pp28_sources"] == ["10433"]
    assert out["per_skala"] == original_rows
    assert DISPUTED_KEY not in out
    assert out["_data_note"] == "10490 belongs to 10419, not 10433"


def test_pp28_sources_correction_is_deep_copied_not_aliased() -> None:
    """A mutation of the spec's list after the fact must not leak into the
    applied record (defensive copy, same discipline as the detach fold)."""
    rec = _record(per_skala=[{"kategori_risiko": "Rendah"}])
    rec["pp28_sources"] = ["10433", "10490"]
    target = ["10433"]
    entry = {
        "code": "10433",
        "action": "metadata_only",
        "data_note": "n",
        "pp28_sources_correction": target,
    }
    out = cure.apply_cure(rec, entry, DISPUTED_KEY)
    target.append("MUTATED")
    assert out["pp28_sources"] == ["10433"], "output must not alias the spec's list object"


def test_plan_already_cured_metadata_only_when_all_corrections_match() -> None:
    rec = _record(per_skala=[{"kategori_risiko": "Rendah"}], disputed=False)
    rec["status_mapping"] = "MATCH_CON_AGGREGAZIONE"
    rec["pp28_sources"] = ["10433"]
    entry = {
        "code": "10433",
        "action": "metadata_only",
        "data_note": "n",
        "status_mapping_correction": "MATCH_CON_AGGREGAZIONE",
        "pp28_sources_correction": ["10433"],
    }
    plan = cure.plan_cure(rec, entry, DISPUTED_KEY)
    assert plan.status == "already-cured"


def test_metadata_only_skips_ambiguous_check_even_when_per_skala_already_empty() -> None:
    """A metadata_only entry never touches per_skala, so the ambiguous-skip
    guard (which exists only to protect an about-to-detach write) must never
    fire for it — even if per_skala happens to already be [] with no
    disputed key present."""
    rec = {
        "kode_kbli_2025": "51103",
        "per_skala": [],
        "status_mapping": "MATCH_LANGSUNG",
        "intel_2026": {"whatItMeans": "keep"},
    }
    entry = {
        "code": "51103",
        "action": "metadata_only",
        "data_note": "n",
        "status_mapping_correction": "MATCH_CON_AGGREGAZIONE",
    }
    plan = cure.plan_cure(rec, entry, DISPUTED_KEY)
    assert plan.status == "apply"
    assert plan.needs_detach is False
    out = cure.apply_cure(rec, entry, DISPUTED_KEY)
    assert out["per_skala"] == []
    assert DISPUTED_KEY not in out
    assert out["status_mapping"] == "MATCH_CON_AGGREGAZIONE"


def test_non_metadata_only_entry_on_healthy_per_skala_still_detaches_as_before() -> None:
    """INNOCENCE control for the new action flag: an entry with NO 'action'
    key, on a record with non-empty per_skala, must still detach exactly as
    every Fase-1/Lot-1/Lot-2/Lot-3 entry always has — the new capability is
    strictly opt-in."""
    rec = _record(per_skala=[{"kategori_risiko": "Rendah"}])
    entry = {"code": "51103", "data_note": "n", "status_mapping_correction": "MATCH_CON_AGGREGAZIONE"}
    plan = cure.plan_cure(rec, entry, DISPUTED_KEY)
    assert plan.needs_detach is True
    assert plan.metadata_only is False
    out = cure.apply_cure(rec, entry, DISPUTED_KEY)
    assert out["per_skala"] == []
    assert out[DISPUTED_KEY] == [{"kategori_risiko": "Rendah"}]



# ---------------------------------------------------------------------------
# Tier-scoped partial detach extension (2026-07-21, PENDING-ARMS L8 gate
# §3.4/§5.1b) — "action": "partial_detach" + "tier_selector". Unblocks curing
# multi-tier records with one sound + one defective tier (93114/93191/93193)
# without destroying verified provenance in the sound tier.
# ---------------------------------------------------------------------------


def _two_tier_rows():
    """A synthetic two-tier per_skala shaped like a real multi-tier record
    (e.g. 93114): one Menengah Rendah tier (the sound one) and one Tinggi
    tier (the one flagged for detach). Fixture data only — not a real code."""
    return [
        {
            "skala_usaha": ["Mikro", "Kecil", "Menengah"],
            "kategori_risiko": "Menengah Rendah",
            "perizinan": "NIB dan Sertifikat Standar",
            "fiktif_positif": True,
        },
        {
            "skala_usaha": ["Menengah", "Besar"],
            "kategori_risiko": "Tinggi",
            "perizinan": "NIB dan Izin",
            "fiktif_positif": True,
        },
    ]


TIER_SELECTOR_TINGGI = {"kategori_risiko": "Tinggi", "skala_usaha": ["Besar", "Menengah"]}


def test_guilt_full_detach_on_multitier_record_still_detaches_fully() -> None:
    """INNOCENCE control for the new action flag: an entry with NO 'action'
    key (or action absent), on a MULTI-tier per_skala, must still detach the
    WHOLE array exactly as before — the new partial_detach capability must
    never leak into the default code path."""
    rows = _two_tier_rows()
    rec = _record(per_skala=rows)
    entry = {"code": "51103", "data_note": "n", "whatYouNeed": "gap"}
    plan = cure.plan_cure(rec, entry, DISPUTED_KEY)
    assert plan.status == "apply"
    assert plan.needs_detach is True
    assert plan.partial_detach is False
    out = cure.apply_cure(rec, entry, DISPUTED_KEY)
    assert out["per_skala"] == [], "full detach empties per_skala entirely, both tiers included"
    assert out[DISPUTED_KEY] == rows, "both tiers preserved verbatim in the disputed key"


def test_plan_partial_detach_flags_only_matched_tier() -> None:
    rows = _two_tier_rows()
    rec = _record(per_skala=rows)
    entry = {
        "code": "93114",
        "action": "partial_detach",
        "tier_selector": TIER_SELECTOR_TINGGI,
        "data_note": "Tinggi/golf tier has zero PP28 backing",
    }
    plan = cure.plan_cure(rec, entry, DISPUTED_KEY)
    assert plan.status == "apply"
    assert plan.needs_detach is True
    assert plan.partial_detach is True
    assert plan.current_row_count == 1, "only the ONE matched row, not both tiers"


def test_apply_partial_detach_moves_only_flagged_tier_sound_tier_byte_identical() -> None:
    """The core guilt+innocence guarantee for this primitive: the flagged
    (Tinggi) tier moves to the disputed key; the sound (Menengah Rendah) tier
    survives in per_skala BYTE-IDENTICAL (same dict content, untouched)."""
    rows = _two_tier_rows()
    sound_tier = copy.deepcopy(rows[0])
    defective_tier = copy.deepcopy(rows[1])
    rec = _record(per_skala=rows)
    entry = {
        "code": "93114",
        "action": "partial_detach",
        "tier_selector": TIER_SELECTOR_TINGGI,
        "data_note": "Tinggi/golf tier has zero PP28 backing",
    }
    out = cure.apply_cure(rec, entry, DISPUTED_KEY)

    assert out["per_skala"] == [sound_tier], "sound tier survives alone in per_skala, byte-identical"
    assert out[DISPUTED_KEY] == [defective_tier], "only the flagged tier moved to the disputed key"
    assert out["_data_note"] == "Tinggi/golf tier has zero PP28 backing"
    # the input record itself must never be mutated (defensive-copy discipline)
    assert rec["per_skala"] == rows, "apply_cure must not mutate its input record in place"


def test_partial_detach_is_idempotent_second_run_is_a_noop() -> None:
    rows = _two_tier_rows()
    sound_tier = copy.deepcopy(rows[0])
    defective_tier = copy.deepcopy(rows[1])
    rec = _record(per_skala=rows)
    entry = {
        "code": "93114",
        "action": "partial_detach",
        "tier_selector": TIER_SELECTOR_TINGGI,
        "data_note": "n",
    }
    once = cure.apply_cure(rec, entry, DISPUTED_KEY)
    plan_again = cure.plan_cure(once, entry, DISPUTED_KEY)
    assert plan_again.status == "already-cured", "re-run must recognise the prior partial detach"
    twice = cure.apply_cure(once, entry, DISPUTED_KEY)
    assert twice["per_skala"] == [sound_tier]
    assert twice[DISPUTED_KEY] == [defective_tier], "second run must not duplicate the moved tier"


def test_plan_partial_detach_ambiguous_skip_when_selector_matches_nothing() -> None:
    """Same no-clobber discipline as the full-detach guard: if the selector
    matches no row AND there is no pre-existing disputed key, refuse to
    touch the record (a spec/selector bug must not silently no-op)."""
    rec = _record(per_skala=[_two_tier_rows()[0]])  # only the sound tier present
    entry = {
        "code": "93114",
        "action": "partial_detach",
        "tier_selector": TIER_SELECTOR_TINGGI,
        "data_note": "n",
    }
    plan = cure.plan_cure(rec, entry, DISPUTED_KEY)
    assert plan.status == "ambiguous-skip"


def test_partial_detach_requires_tier_selector() -> None:
    rec = _record(per_skala=_two_tier_rows())
    entry = {"code": "93114", "action": "partial_detach", "data_note": "n"}
    with pytest.raises(cure.CureError):
        cure.plan_cure(rec, entry, DISPUTED_KEY)
    with pytest.raises(cure.CureError):
        cure.apply_cure(rec, entry, DISPUTED_KEY)


def test_partial_detach_rejects_per_skala_legacy_combination() -> None:
    rec = _record(per_skala=_two_tier_rows())
    rec["per_skala_legacy"] = [{"kategori_risiko": "old"}]
    entry = {
        "code": "93114",
        "action": "partial_detach",
        "tier_selector": TIER_SELECTOR_TINGGI,
        "data_note": "n",
    }
    with pytest.raises(cure.CureError):
        cure.plan_cure(rec, entry, DISPUTED_KEY)
    with pytest.raises(cure.CureError):
        cure.apply_cure(rec, entry, DISPUTED_KEY)


def test_apply_partial_detach_appends_to_existing_disputed_list() -> None:
    """A second partial_detach on the same record (a later lot curing a
    second tier) must APPEND to the existing disputed list, never overwrite
    it — the first tier's preserved provenance must survive."""
    rows = _two_tier_rows()
    prior_disputed_tier = {"kategori_risiko": "Rendah", "skala_usaha": ["Mikro"], "src": "prior lot"}
    rec = _record(per_skala=rows)
    rec[DISPUTED_KEY] = [prior_disputed_tier]
    entry = {
        "code": "93114",
        "action": "partial_detach",
        "tier_selector": TIER_SELECTOR_TINGGI,
        "data_note": "n",
    }
    out = cure.apply_cure(rec, entry, DISPUTED_KEY)
    assert out[DISPUTED_KEY] == [prior_disputed_tier, rows[1]], "appended, prior entry preserved"
    assert out["per_skala"] == [rows[0]]


def test_apply_partial_detach_raises_on_incompatible_existing_disputed_shape() -> None:
    rows = _two_tier_rows()
    rec = _record(per_skala=rows)
    rec[DISPUTED_KEY] = {"per_skala": rows, "per_skala_legacy": []}  # legacy-fold shape, not a list
    entry = {
        "code": "93114",
        "action": "partial_detach",
        "tier_selector": TIER_SELECTOR_TINGGI,
        "data_note": "n",
    }
    with pytest.raises(cure.CureError):
        cure.apply_cure(rec, entry, DISPUTED_KEY)


def test_tier_selector_skala_usaha_matches_regardless_of_order() -> None:
    """skala_usaha is compared as a SET — a reordered array (e.g. a re-pull
    that changed serialization order) must still match the same tier."""
    rows = _two_tier_rows()
    rows[1]["skala_usaha"] = list(reversed(rows[1]["skala_usaha"]))  # ["Besar", "Menengah"]
    rec = _record(per_skala=rows)
    entry = {
        "code": "93114",
        "action": "partial_detach",
        "tier_selector": {"kategori_risiko": "Tinggi", "skala_usaha": ["Menengah", "Besar"]},
        "data_note": "n",
    }
    plan = cure.plan_cure(rec, entry, DISPUTED_KEY)
    assert plan.status == "apply"
    assert plan.current_row_count == 1
