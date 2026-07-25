"""Wave-2 l4_bali disclosure cure — selector + guard, guilt AND innocence.

The wave-1 cure (`l4bali_disclosure_2026_07_19.json`) selected codes by the
presence of a `per_skala_disputed_*` key. That is a MARKER test, and a code
detached without ever receiving a marker is invisible to it — not skipped, not
reported, simply unreachable. Measured on the canonical 2026-07-25: 94 codes
still certified a Bali verdict derived from a gap, 54 of them with no marker.

`emit_l4bali_gap_disclosure_spec.py` selects on the STATE instead. These tests
pin both halves of that selector: it must fire on a verdict whose basis is a
declared gap, and it must NOT fire on a neighbouring verdict whose basis is
intact (cicatrix superscar #3 — a guard shipped with only a guilt corpus is
half a guard).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.kbli_filiera import cure_l4bali_disclosure as cure
from scripts.kbli_filiera import emit_l4bali_gap_disclosure_spec as emit

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "scripts" / "kbli_filiera" / "cure_specs" / "l4bali_gap_disclosure_2026_07_25.json"

MORATORIUM = {
    "rule": "Bali province blocks ALL Low + Medium-Low risk KBLI for PMA",
    "effective": "2026-05-13",
    "source": "Gubernur letter B.27.000/642/PM/DPMPTSP",
}


def _record(**over):
    base = {
        "kode_kbli_2025": "99999",
        "per_skala": [],
        "_l2_status": "no_oss_risk",
        "l4_bali": {
            "status": "OK_or_HIGHER_RISK",
            "reason": "medium-high/high risk → not blocked by moratorium (verify per address)",
            "confidence": "MEDIUM",
            "needs_review": False,
            "blocked": False,
            "moratorium": MORATORIUM,
        },
    }
    l4_over = over.pop("l4", {})
    base.update(over)
    base["l4_bali"].update(l4_over)
    return base


# ---------------------------------------------------------------------------
# GUILT — the selector fires on a verdict resting on a declared gap
# ---------------------------------------------------------------------------

def test_selects_risk_derived_verdict_over_a_no_oss_scope_gap():
    selected, _ = emit.select([_record()])
    assert [s["gap_basis"] for s in selected] == ["no_oss_scope"]


def test_selects_when_rows_were_disowned_into_a_disputed_key():
    rec = _record(per_skala_disputed_pp28_collision=[{"skala_usaha": ["Mikro"]}])
    rec.pop("_l2_status")
    selected, _ = emit.select([rec])
    assert [s["gap_basis"] for s in selected] == ["disputed_key"]


def test_selects_a_blocked_true_verdict_certified_at_high_confidence():
    # The worst shape: the page tells a client a PT PMA cannot register here,
    # stated as settled, on a basis the same record calls unverifiable.
    rec = _record(l4={"status": "CHIUSO_MORATORIA_BALI", "blocked": True, "confidence": "HIGH"})
    selected, _ = emit.select([rec])
    assert len(selected) == 1


# ---------------------------------------------------------------------------
# INNOCENCE — the selector leaves intact bases alone
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status", ["TERTUTUP", "TERBATAS", "CHIUSO_REGOLATORE_SETTORIALE"])
def test_does_not_fire_when_the_verdict_derives_from_another_layer(status):
    # TERTUTUP/TERBATAS come from pma_status; CHIUSO_REGOLATORE_SETTORIALE from
    # a sector regulator. Their basis is not the detached risk layer, so
    # disclosing a derivation defect there would be a false statement.
    selected, _ = emit.select([_record(l4={"status": status})])
    assert selected == []


def test_does_not_fire_when_the_risk_layer_is_present():
    rec = _record(per_skala=[{"skala_usaha": ["Besar"], "kategori_risiko": "Tinggi"}])
    rec["_l2_status"] = None
    selected, _ = emit.select([rec])
    assert selected == []


def test_does_not_fire_on_an_uncorroborated_empty_per_skala():
    # F12: an empty layer with neither a disputed key nor a recorded 404 is not
    # assumed to be a gap. Absence needs a second signal.
    rec = _record()
    rec["_l2_status"] = None
    selected, _ = emit.select([rec])
    assert selected == []


def test_does_not_re_fire_on_an_already_disclosed_record():
    rec = _record(
        l4={
            "reason": cure.DISCLOSURE_PREFIX + "medium-high/high risk → not blocked",
            "confidence": "LOW",
            "needs_review": True,
        }
    )
    selected, _ = emit.select([rec])
    assert selected == []


def test_unclassified_status_fails_loud_instead_of_being_ignored():
    # A status nobody classified means the script cannot know whether its basis
    # is the detached layer. Guessing is how the original defect was born.
    with pytest.raises(SystemExit, match="UNCLASSIFIED"):
        emit.select([_record(l4={"status": "SOME_NEW_STATUS_2027"})])


# ---------------------------------------------------------------------------
# The cure's own guard on the new basis
# ---------------------------------------------------------------------------

def _entry(rec, gap_basis):
    l4 = rec["l4_bali"]
    e = {
        "gap_basis": gap_basis,
        "expected_status": l4["status"],
        "expected_reason": l4["reason"],
        "expected_confidence": l4["confidence"],
        "expected_needs_review": l4["needs_review"],
        "expected_blocked": l4["blocked"],
    }
    if gap_basis == cure.GAP_BASIS_DISPUTED_KEY:
        e["disputed_key"] = "per_skala_disputed_pp28_collision"
    return e


def test_no_oss_scope_entry_is_cured_without_citing_a_disputed_key():
    rec = _record()
    plan = cure.evaluate_code("99999", _entry(rec, "no_oss_scope"), {"99999": rec})
    assert plan.status == "apply"
    reason = plan.new_l4["reason"]
    assert reason.startswith(cure.DISCLOSURE_PREFIX)
    assert rec["l4_bali"]["reason"] in reason  # original preserved as audit trail
    assert "per_skala_disputed" not in reason  # never a fabricated citation
    assert plan.new_l4["confidence"] == "LOW"
    assert plan.new_l4["needs_review"] is True


def test_the_disclosure_sentence_carries_no_raw_field_name():
    # l4_bali.reason is a badge tooltip AND is spliced into a published FAQ
    # answer; adding pipeline keys to it would grow the very debt this
    # programme is paying down.
    rec = _record()
    plan = cure.evaluate_code("99999", _entry(rec, "no_oss_scope"), {"99999": rec})
    for field_name in ("_l2_status", "per_skala", "l4_bali", "_data_note", "pp28_sources"):
        assert field_name not in cure.DISCLOSURE_SUFFIX_NO_OSS_SCOPE, (
            f"{field_name!r} leaked into the reader-facing disclosure sentence"
        )
    assert "no_oss_risk" not in plan.new_l4["reason"]


def test_status_and_blocked_are_never_modified():
    rec = _record(l4={"status": "CHIUSO_MORATORIA_BALI", "blocked": True, "confidence": "HIGH"})
    plan = cure.evaluate_code("99999", _entry(rec, "no_oss_scope"), {"99999": rec})
    assert plan.new_l4["status"] == "CHIUSO_MORATORIA_BALI"
    assert plan.new_l4["blocked"] is True
    assert plan.new_l4["moratorium"] == MORATORIUM


def test_guard_skips_when_the_gap_has_healed_since_the_spec_was_emitted():
    rec = _record()
    entry = _entry(rec, "no_oss_scope")
    rec["per_skala"] = [{"skala_usaha": ["Besar"], "kategori_risiko": "Tinggi"}]
    plan = cure.evaluate_code("99999", entry, {"99999": rec})
    assert plan.status == "skip_guard"
    assert "restored or re-adjudicated" in plan.detail


def test_guard_skips_when_the_no_oss_basis_is_not_corroborated():
    rec = _record()
    entry = _entry(rec, "no_oss_scope")
    rec["_l2_status"] = "oss_risk_present"
    plan = cure.evaluate_code("99999", entry, {"99999": rec})
    assert plan.status == "skip_guard"


def test_unknown_gap_basis_is_a_hard_error():
    rec = _record()
    entry = _entry(rec, "no_oss_scope")
    entry["gap_basis"] = "vibes"
    with pytest.raises(cure.CureError, match="unknown gap_basis"):
        cure.evaluate_code("99999", entry, {"99999": rec})


def test_wave1_specs_without_gap_basis_still_behave_as_disputed_key():
    rec = _record(per_skala_disputed_pp28_collision=[{"skala_usaha": ["Mikro"]}])
    entry = _entry(rec, cure.GAP_BASIS_DISPUTED_KEY)
    entry.pop("gap_basis")  # wave-1 spec shape
    plan = cure.evaluate_code("99999", entry, {"99999": rec})
    assert plan.status == "apply"
    assert rec["l4_bali"]["reason"] in plan.new_l4["reason"]
    # …and it gets the SAME reader-facing sentence as everything else: the basis
    # decides the guard, never a different dialect of prose for the client.
    assert plan.new_l4["reason"].endswith(cure.DISCLOSURE_SUFFIX_DISPUTED_KEY)
    assert "per_skala" not in plan.new_l4["reason"]


# ---------------------------------------------------------------------------
# The emitted spec itself
# ---------------------------------------------------------------------------

def test_spec_exists_and_records_its_selection_and_hard_rule():
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    meta = spec["_meta"]
    assert "no prose matching" in meta["selection"]
    assert "NEVER" in meta["hard_rule"]
    assert spec["codes"], "spec must not be empty"


def test_every_spec_entry_declares_a_known_gap_basis():
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    for code, entry in spec["codes"].items():
        assert entry["gap_basis"] in (
            cure.GAP_BASIS_DISPUTED_KEY,
            cure.GAP_BASIS_NO_OSS_SCOPE,
            cure.GAP_BASIS_DETACHED_TIER,
        ), f"{code}: unknown gap_basis {entry['gap_basis']!r}"
        if entry["gap_basis"] == cure.GAP_BASIS_DISPUTED_KEY:
            assert entry.get("disputed_key"), f"{code}: disputed_key basis with no key"
        else:
            assert "disputed_key" not in entry, f"{code}: no_oss_scope basis must not cite a key"


def test_spec_never_targets_a_verdict_from_an_intact_layer():
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    for code, entry in spec["codes"].items():
        assert entry["expected_status"] in emit.RISK_DERIVED_STATUSES, (
            f"{code}: {entry['expected_status']} does not derive from the risk layer — "
            "disclosing a derivation defect there would be a false statement"
        )


# ---------------------------------------------------------------------------
# The census IS the spec — pin the numbers the docstring states
# ---------------------------------------------------------------------------

def test_spec_census_matches_the_numbers_stated_in_the_emitter_docstring():
    # An earlier hand census of this same population, taken by matching risk
    # words in `l4_bali.reason` prose, said 134/101/64 — it over-counted,
    # because a PMA-derived verdict's reason mentions risk too. A number that
    # lives only in prose rots silently; this pins it to the emitted artefact.
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    codes = spec["codes"]
    by_basis = {
        basis: sum(1 for e in codes.values() if e["gap_basis"] == basis)
        for basis in (
            cure.GAP_BASIS_NO_OSS_SCOPE,
            cure.GAP_BASIS_DISPUTED_KEY,
            cure.GAP_BASIS_DETACHED_TIER,
        )
    }
    blocked = [e for e in codes.values() if e["expected_blocked"] is True]
    assert (
        len(codes),
        by_basis[cure.GAP_BASIS_NO_OSS_SCOPE],
        by_basis[cure.GAP_BASIS_DISPUTED_KEY],
        by_basis[cure.GAP_BASIS_DETACHED_TIER],
    ) == (95, 54, 40, 1)
    assert len(blocked) == 24
    # Every one of the 24 told the client the verdict was settled.
    assert all(
        e["expected_confidence"] == "HIGH" and e["expected_needs_review"] is False for e in blocked
    )


# ---------------------------------------------------------------------------
# IMMUNE ORGAN — measured on the real canonical, not on fixtures
# ---------------------------------------------------------------------------

def test_no_code_in_the_live_canonical_still_certifies_a_gap_derived_verdict():
    # This is the invariant the whole wave exists to establish, and it is
    # measured on the shipped data rather than asserted in a report. It fails
    # LOUD if a later pass re-certifies one of these verdicts, or if a new
    # detach lot lands without its disclosure — which is the point: the next
    # lot must disclose, not inherit silence.
    payload = json.loads(emit.DEFAULT_CANONICAL.read_text(encoding="utf-8"))
    records = payload["data"]
    selected, _ = emit.select(records)
    assert len(records) == 1559
    assert selected == [], (
        f"{len(selected)} codes certify a Bali verdict derived from a declared gap: "
        f"{[s['record'][emit.CODE_FIELD] for s in selected][:10]} — re-emit the spec "
        "and run cure_l4bali_disclosure.py"
    )


# ---------------------------------------------------------------------------
# THIRD SHAPE — partial detach: rows survive, the cited tier does not
#
# PR #2921's `partial_detach` primitive disowns SOME rows and keeps others, so
# `per_skala == []` (the wave-2 selector) is blind to it: the record looks
# intact while the verdict cites a tier that is no longer in it. Found by the
# cross-family adversarial gate on this very diff, then re-measured on the live
# canonical — exactly one code, 93114, and it reads `blocked: false` at HIGH,
# i.e. it tells a client "registrable by a PT PMA in Bali" on a tier the record
# itself disowned.
# ---------------------------------------------------------------------------

def _partial(status, rows, **over):
    rec = _record(l4={"status": status}, **over)
    rec["per_skala"] = rows
    rec["per_skala_disputed_pp28_collision"] = [
        {"skala_usaha": ["Besar"], "kategori_risiko": "Tinggi"}
    ]
    rec.pop("_l2_status", None)
    return rec


BESAR_HIGH = [{"skala_usaha": ["Mikro", "Kecil", "Besar"], "kategori_risiko": "Tinggi"}]
BESAR_LOW = [{"skala_usaha": ["Kecil", "Menengah", "Besar"], "kategori_risiko": "Menengah Rendah"}]
NO_BESAR = [{"skala_usaha": ["Mikro", "Kecil", "Menengah"], "kategori_risiko": "Menengah Rendah"}]


def test_selects_a_verdict_whose_cited_tier_did_not_survive_the_detach():
    # 93114's real shape: "the Besar scale is 'Tinggi'" with no Besar row left.
    selected, _ = emit.select([_partial("APERTO_BALI_RISCHIO_ALTO", NO_BESAR)])
    assert [s["gap_basis"] for s in selected] == [cure.GAP_BASIS_DETACHED_TIER]


@pytest.mark.parametrize(
    "status,rows",
    [
        ("APERTO_BALI_RISCHIO_ALTO", BESAR_HIGH),   # cites a high tier, has one
        ("CHIUSO_MORATORIA_BALI", BESAR_LOW),       # cites a blocked tier, has one
        ("CHIUSO_PMA_NO_BESAR", NO_BESAR),          # cites the absence, absence holds
    ],
)
def test_does_not_fire_when_the_surviving_rows_still_support_the_verdict(status, rows):
    # 93191's real shape: partially detached, but the tier the verdict names is
    # still there. Disclosing a derivation defect here would be a false statement.
    selected, _ = emit.select([_partial(status, rows)])
    assert selected == []


def test_does_not_fire_on_an_inconsistency_with_no_detach_behind_it():
    # Rows present and inconsistent, but nothing was ever disowned — that is a
    # different bug (a stale verdict) and this cure has no evidence for it.
    rec = _partial("APERTO_BALI_RISCHIO_ALTO", NO_BESAR)
    rec.pop("per_skala_disputed_pp28_collision")
    selected, _ = emit.select([rec])
    assert selected == []


def test_statuses_from_the_other_derivation_are_not_re_derived_from_the_besar_row():
    # OK_or_HIGHER_RISK / BLOCCATO_CLASSE_RISCHIO come from the lowest tier across
    # ALL scales (build_kbli_l2_oss_risk.py), not from the Besar row. Re-deriving
    # them here would manufacture false mismatches, so they are undecidable —
    # and undecidable must never be read as "in scope".
    from scripts.kbli_filiera import _l4bali_basis as basis

    rec = _partial("OK_or_HIGHER_RISK", NO_BESAR)
    assert basis.status_matches_surviving_rows("OK_or_HIGHER_RISK", rec) is None
    selected, _ = emit.select([rec])
    assert selected == []


def test_detached_tier_disclosure_cites_no_key_and_no_field_name():
    rec = _partial("APERTO_BALI_RISCHIO_ALTO", NO_BESAR)
    entry = _entry(rec, cure.GAP_BASIS_DETACHED_TIER)
    plan = cure.evaluate_code("99999", entry, {"99999": rec})
    assert plan.status == "apply"
    reason = plan.new_l4["reason"]
    assert rec["l4_bali"]["reason"] in reason
    assert "per_skala" not in reason and "_l2_status" not in reason
    assert plan.new_l4["confidence"] == "LOW" and plan.new_l4["needs_review"] is True
    assert plan.new_l4["status"] == "APERTO_BALI_RISCHIO_ALTO"
    assert plan.new_l4["blocked"] is False


@pytest.mark.parametrize(
    "mutate,expected",
    [
        (lambda r: r.__setitem__("per_skala", BESAR_HIGH), "basis survived"),
        (lambda r: r.__setitem__("per_skala", []), "FULL detach"),
        (lambda r: r.pop("per_skala_disputed_pp28_collision"), "nothing was detached"),
    ],
)
def test_detached_tier_guard_skips_when_the_basis_changed_since_emission(mutate, expected):
    rec = _partial("APERTO_BALI_RISCHIO_ALTO", NO_BESAR)
    entry = _entry(rec, cure.GAP_BASIS_DETACHED_TIER)
    mutate(rec)
    plan = cure.evaluate_code("99999", entry, {"99999": rec})
    assert plan.status == "skip_guard"
    assert expected in plan.detail


def test_the_no_oss_scope_disclosure_never_asserts_an_http_status():
    # An earlier draft said "the scope endpoint returns 404". `_l2_status =
    # no_oss_risk` is also written for a MISSING dump line, any non-200, or
    # success=false (build_kbli_l2_oss_risk.py) — asserting a status code we
    # never observed, in the sentence whose job is honesty, is the disease.
    for forbidden in ("404", "not published", "does not exist"):
        assert forbidden not in cure.DISCLOSURE_SUFFIX_NO_OSS_SCOPE
    assert "could be retrieved" in cure.DISCLOSURE_SUFFIX_NO_OSS_SCOPE


# ---------------------------------------------------------------------------
# R4 — reader-facing prose must not narrate JSON field names
#
# Wave 1's sentence named `per_skala_disputed_pp28_collision (see _data_note)`.
# `l4_bali.reason` is the Bali badge tooltip AND is spliced verbatim into a
# published FAQ answer (apps/mouth/src/lib/kbli-faq.ts), so that was 57 client
# sentences narrating internal keys — the same debt as the catalogue's 392
# raw-key editorial narrations. Fixing it only for the new codes would have left
# a half-fixed class and two dialects, so the migration is catalogue-wide.
# ---------------------------------------------------------------------------

LEGACY_REASON = (
    "Nationally TERBUKA but the Besar scale is 'Menengah Rendah' -> blocked. "
    " — NOTE: the risk tier this verdict was derived from has been detached to "
    "per_skala_disputed_pp28_collision (see _data_note); verdict pending "
    "re-derivation from the true risk tier (GARUDA-FILIERA)."
)


def test_reword_replaces_the_key_naming_sentence_and_keeps_the_verdict_text():
    out = cure.reword_legacy_reason(cure.DISCLOSURE_PREFIX + LEGACY_REASON)
    assert out is not None
    assert out.startswith(cure.DISCLOSURE_PREFIX)
    assert "Nationally TERBUKA but the Besar scale is 'Menengah Rendah' -> blocked." in out
    assert "per_skala_disputed" not in out and "_data_note" not in out
    assert out.endswith(cure.DISCLOSURE_SUFFIX_DISPUTED_KEY)


@pytest.mark.parametrize(
    "reason",
    [
        "medium-high/high risk → not blocked by moratorium (verify per address)",  # never disclosed
        cure.DISCLOSURE_PREFIX + "x" + cure.DISCLOSURE_SUFFIX_DISPUTED_KEY,        # already migrated
        cure.DISCLOSURE_PREFIX + "x" + cure.DISCLOSURE_SUFFIX_NO_OSS_SCOPE,        # other basis
        LEGACY_REASON + " and then somebody appended a sentence.",                 # hand-touched
    ],
)
def test_reword_leaves_everything_it_does_not_recognise_alone(reason):
    # The anchor is end-of-string on purpose: a reason that was hand-edited or
    # double-suffixed is REPORTED, never re-shaped on a guess.
    assert cure.reword_legacy_reason(reason) is None


def test_an_unrecognised_shape_is_reported_not_silently_skipped():
    records = [
        {"kode_kbli_2025": "11111", "l4_bali": {"reason": cure.DISCLOSURE_PREFIX + LEGACY_REASON}},
        {"kode_kbli_2025": "22222", "l4_bali": {"reason": LEGACY_REASON + " trailing edit"}},
    ]
    rewordings, suspicious = cure.plan_legacy_rewording(records)
    assert list(rewordings) == ["11111"]
    assert suspicious == ["22222"]


def test_no_reason_in_the_live_catalogue_narrates_a_json_field_name():
    # Measured on the shipped data, all 1,559 records — not just the ones this
    # wave touched. A reader never sees a pipeline key in a verdict sentence.
    payload = json.loads(emit.DEFAULT_CANONICAL.read_text(encoding="utf-8"))
    offenders = [
        r[emit.CODE_FIELD]
        for r in payload["data"]
        for reason in [str((r.get("l4_bali") or {}).get("reason") or "")]
        if any(
            key in reason
            for key in ("per_skala", "_data_note", "_l2_status", "_l2_source", "pp28_sources", "l4_bali")
        )
    ]
    assert offenders == [], f"{len(offenders)} verdict sentences narrate a JSON key: {offenders[:10]}"


def test_the_three_disclosure_sentences_are_the_only_dialects_in_the_catalogue():
    payload = json.loads(emit.DEFAULT_CANONICAL.read_text(encoding="utf-8"))
    suffixes = {
        cure.DISCLOSURE_SUFFIX_DISPUTED_KEY,
        cure.DISCLOSURE_SUFFIX_NO_OSS_SCOPE,
        cure.DISCLOSURE_SUFFIX_DETACHED_TIER,
    }
    disclosed = [
        str(r["l4_bali"]["reason"])
        for r in payload["data"]
        if str((r.get("l4_bali") or {}).get("reason") or "").startswith(cure.DISCLOSURE_PREFIX)
    ]
    assert len(disclosed) == 152
    assert all(any(reason.endswith(s) for s in suffixes) for reason in disclosed)
