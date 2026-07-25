"""The `whatChanged` provenance cure — guilt AND innocence, on every surface.

Three defects, three passes, one shared decision function (`plan_text`), and
three live surfaces that must never drift apart. The innocence corpus here is
not decoration: an earlier census of the false-renumbering defect named 8 codes,
and after Batch-B's `bps_2020_ancestors` populate landed (2026-07-24) four of
them acquired a real BPS ancestor with a lampiran locator — their sentence
became plausibly true. A cure that had fired on the stale list would have
deleted four true statements. That is why every pass is decided by re-deriving
the record's state at apply time, and why each pass owns a test proving it does
NOT fire on the legitimate case next door.

The live-file organs at the bottom are measured on the shipped catalogue, not on
fixtures — they are what would catch the next code that acquires this defect.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Everything comes through the compiler module on purpose — see its import
# comment: reaching `_whatchanged_basis` by a second path would give the tests a
# different `WhatChangedError` class than the one the code raises.
from scripts.kbli_filiera import cure_whatchanged_false_renumber as cure
from scripts.kbli_filiera.cure_whatchanged_false_renumber import (
    PASS_CONTRADICTED_PREDECESSOR,
    PASS_FALSE_CLAIM,
    PASS_TRUNCATED,
    WhatChangedError,
    contradicted_predecessors,
    has_no_recorded_predecessor,
    is_truncated_midword,
    plan_text,
    recorded_predecessors,
    trim_to_last_complete_sentence,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
GOLD = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-gold-all.json"

BPS_ANCESTOR = {
    "codes": ["78421"],
    "sebagian": [False],
    "source_locator": [{"lampiran": 10, "pdf_page": 432, "printed_page": 418}],
    "adjudication_status": "mechanical-only",
    "inheritance_verdict": "not-adjudicated",
}

# Gold codes with no canonical record. Inert (generateStaticParams iterates
# canonical and dynamicParams=false, so no page exists for them), but pinned so
# the set cannot grow unnoticed — a row that lives only downstream is the exact
# phantom class every cure tool keyed on "a canonical record exists" is blind to.
KNOWN_GOLD_ORPHANS = [
    "64921",
    "85300",
    "85491",
    "85499",
    "85600",
    "86903",
    "96120",
    "96130",
]


def _record(what_changed: str = cure.FALSE_CLAIM + " Consolidated in BNSP framework.", **over):
    base = {
        "kode_kbli_2025": "99999",
        "status_mapping": "BPS_ONLY",
        "pp28_sources": [],
        "kbli_2020_source": None,
        "bps_2020_ancestors": None,
        "intel_2026": {"whatChanged": what_changed},
    }
    base.update(over)
    return base


def _passes(record):
    return plan_text(str(record["intel_2026"]["whatChanged"]), record)[1]


# ---------------------------------------------------------------------------
# PASS A — a renumbering claim nothing supports
# ---------------------------------------------------------------------------


def test_a_fires_when_no_layer_records_a_predecessor():
    assert _passes(_record()) == [PASS_FALSE_CLAIM]


def test_a_replaces_only_the_first_sentence():
    text = cure.FALSE_CLAIM + " Consolidated in BNSP framework. Four codes cover it."
    out, _ = plan_text(text, _record(text))
    assert out.startswith(cure.HONEST_CLAIM)
    assert out.endswith(" Consolidated in BNSP framework. Four codes cover it.")
    assert cure.FALSE_CLAIM not in out


def test_the_replacement_speaks_about_our_records_not_about_the_regulator():
    # "not recorded" is a statement about our crosswalk. "New in KBLI 2025" would
    # be an inference from absence — the same move that produced the bug (F12).
    assert "recorded" in cure.HONEST_CLAIM
    for forbidden in ("new in KBLI 2025", "did not exist", "was not published", "abolished"):
        assert forbidden.lower() not in cure.HONEST_CLAIM.lower()


@pytest.mark.parametrize(
    "field,value",
    [
        ("bps_2020_ancestors", BPS_ANCESTOR),
        ("kbli_2020_source", "78421"),
        ("pp28_sources", [{"lampiran": 2, "printed_page": 17}]),
    ],
    ids=["bps-ancestor", "direct-2020-source", "pp28-row"],
)
def test_a_does_not_fire_when_any_single_layer_records_a_predecessor(field, value):
    assert PASS_FALSE_CLAIM not in _passes(_record(**{field: value}))


def test_a_does_not_fire_on_a_text_that_makes_no_renumbering_claim():
    assert _passes(_record(what_changed="Unified code for all freshwater aquarium species.")) == []


def test_a_does_not_fire_twice_on_its_own_output():
    first, _ = plan_text(str(_record()["intel_2026"]["whatChanged"]), _record())
    assert plan_text(first, _record(what_changed=first))[1] == []


def test_a_missing_intel_block_is_not_treated_as_a_claim():
    assert plan_text("", {"kode_kbli_2025": "99999", "pp28_sources": []})[1] == []


# ---------------------------------------------------------------------------
# PASS B — mid-word truncation at exactly 216 characters
# ---------------------------------------------------------------------------

TRUNCATED = "A" * 100 + ". Independent digital journalism represents the modern evolution of a press th"


def test_b_signature_is_length_AND_missing_punctuation_not_length_alone():
    exact_but_complete = "B" * (cure.TRUNCATION_LENGTH - 1) + "."
    assert len(exact_but_complete) == cure.TRUNCATION_LENGTH
    assert is_truncated_midword(exact_but_complete) is False
    padded = TRUNCATED.ljust(cure.TRUNCATION_LENGTH, "x")[: cure.TRUNCATION_LENGTH]
    assert is_truncated_midword(padded) is True


def test_b_does_not_claim_a_short_broken_text():
    # Only the 216-char signature is evidence of THIS truncation. Any other
    # unterminated text is an editorial matter, not a mechanical one.
    assert is_truncated_midword("ends mid-wor") is False


def test_b_trim_keeps_every_complete_sentence_and_drops_only_the_fragment():
    assert trim_to_last_complete_sentence("One. Two! Three? and a frag") == "One. Two! Three?"


def test_b_trim_refuses_when_there_is_no_complete_sentence_to_keep():
    assert trim_to_last_complete_sentence("no sentence ends here") is None


def test_b_is_never_applied_when_nothing_complete_would_survive():
    rec = _record(what_changed="x" * cure.TRUNCATION_LENGTH)
    assert is_truncated_midword(rec["intel_2026"]["whatChanged"]) is True
    assert PASS_TRUNCATED not in _passes(rec)


def test_b_never_invents_a_word():
    original = TRUNCATED.ljust(cure.TRUNCATION_LENGTH, "x")[: cure.TRUNCATION_LENGTH]
    trimmed = trim_to_last_complete_sentence(original)
    assert trimmed is not None
    assert original.startswith(trimmed)  # a strict prefix — nothing added, nothing reordered


# ---------------------------------------------------------------------------
# PASS C — a named 2020 predecessor no crosswalk layer holds
# ---------------------------------------------------------------------------

NAMED_TEXT = (
    "Renumbered/adjusted from KBLI 2020. KBLI 2020: 46415 (Perlengkapan Jahit) "
    "→ KBLI 2025: 46415 (confermato). Verifica e aggiornamento NIB richiesti."
)


def test_c_fires_when_the_named_code_is_in_no_layer():
    rec = _record(what_changed=NAMED_TEXT, kbli_2020_source="46694", pp28_sources=["46694"])
    assert PASS_CONTRADICTED_PREDECESSOR in _passes(rec)


def test_c_does_not_fire_when_the_named_code_is_recorded_by_any_layer():
    # The innocence case that matters most: 93299's prose names 93299 and its
    # record holds 93299. Naming a predecessor is normal; naming an unrecorded
    # one is the defect.
    rec = _record(what_changed=NAMED_TEXT, kbli_2020_source="46415")
    assert PASS_CONTRADICTED_PREDECESSOR not in _passes(rec)
    assert contradicted_predecessors(NAMED_TEXT, rec) == set()


def test_c_does_not_fire_on_a_text_that_names_no_predecessor():
    rec = _record(what_changed="Code stable. Kemenkes framework applies.", kbli_2020_source="46694")
    assert PASS_CONTRADICTED_PREDECESSOR not in _passes(rec)


def test_c_never_substitutes_the_recorded_number_for_the_published_one():
    # The layers can disagree with each other (46415: pp28 says 46694, BPS says
    # 46419). Publishing either as THE answer would be us picking a winner —
    # exactly the disease. The cure states both and declares the mapping
    # unconfirmed; the arrow claim must be gone, not corrected.
    rec = _record(
        what_changed=NAMED_TEXT,
        kbli_2020_source="46694",
        pp28_sources=["46694"],
        bps_2020_ancestors={"codes": ["46419"]},
    )
    out, passes = plan_text(NAMED_TEXT, rec)
    assert PASS_CONTRADICTED_PREDECESSOR in passes
    assert "KBLI 2020: 46415" not in out
    assert "→ KBLI 2025: 46415" not in out
    assert "46694" in out and "46419" in out  # both, never one
    assert "unconfirmed" in out
    assert out.endswith("Verifica e aggiornamento NIB richiesti.")  # the rest survives verbatim


def test_c_reports_the_gap_when_the_record_holds_nothing_at_all():
    rec = _record(what_changed=NAMED_TEXT)
    out, _ = plan_text(NAMED_TEXT, rec)
    assert "no crosswalk source on file records any predecessor" in out


def test_recorded_predecessors_reads_all_three_layer_shapes():
    rec = _record(
        kbli_2020_source="11111",
        pp28_sources=["22222", {"kode": "33333"}],
        bps_2020_ancestors={"codes": ["44444"]},
    )
    assert recorded_predecessors(rec) == {"11111", "22222", "33333", "44444"}
    assert has_no_recorded_predecessor(rec) is False


# ---------------------------------------------------------------------------
# COMPOSITION — passes must survive each other
# ---------------------------------------------------------------------------


def test_a_and_b_compose_and_the_trim_runs_last():
    text = (cure.FALSE_CLAIM + " Keep this sentence. and then a cut mid-wor").ljust(
        cure.TRUNCATION_LENGTH, "x"
    )[: cure.TRUNCATION_LENGTH]
    rec = _record(what_changed=text)
    out, passes = plan_text(text, rec)
    assert passes == [PASS_FALSE_CLAIM, PASS_TRUNCATED]
    assert out == cure.HONEST_CLAIM + " Keep this sentence."


def test_detection_uses_the_original_length_not_the_rewritten_one():
    # Pass A changes the text length, so a B-detection done after A would miss
    # the 216 signature entirely. This is the ordering bug the module avoids.
    text = (cure.FALSE_CLAIM + " Keep this. frag").ljust(cure.TRUNCATION_LENGTH, "x")[
        : cure.TRUNCATION_LENGTH
    ]
    rec = _record(what_changed=text)
    cured, passes = plan_text(text, rec)
    assert PASS_TRUNCATED in passes
    assert len(cured) != cure.TRUNCATION_LENGTH


def test_plan_text_is_idempotent_on_every_shape():
    for text, rec in (
        (NAMED_TEXT, _record(what_changed=NAMED_TEXT, kbli_2020_source="46694")),
        (cure.FALSE_CLAIM + " body.", _record(what_changed=cure.FALSE_CLAIM + " body.")),
    ):
        once, first_passes = plan_text(text, rec)
        assert first_passes  # it fired
        twice, second_passes = plan_text(once, rec)
        assert second_passes == [] and twice == once


def test_a_rewrite_refuses_to_fire_on_a_text_it_does_not_own():
    # Each rewrite is only ever reached through plan_text's guard. If a caller
    # gets there anyway, the selection upstream is wrong and it must fail loud
    # rather than silently no-op — a silent no-op is how a cure reports success
    # on a record it never touched.
    with pytest.raises(WhatChangedError):
        cure.swap_false_claim("This text never made a renumbering claim.")
    with pytest.raises(WhatChangedError):
        cure.drop_contradicted_predecessor("no predecessor named here.", _record())
    assert cure.CureError is WhatChangedError  # the compiler's public alias


# ---------------------------------------------------------------------------
# SURFACES — gold is decided by the CANONICAL record, never by itself
# ---------------------------------------------------------------------------


def test_gold_is_judged_by_the_canonical_record_not_by_gold_content():
    # The gold entry carries no crosswalk fields at all — if the decision were
    # taken from the entry itself, every gold text would look predecessor-less
    # and pass A would fire on all 428.
    record = _record(kbli_2020_source="46694")
    record["kode_kbli_2025"] = "46415"
    gold = {"46415": {"whatChanged": cure.FALSE_CLAIM + " body."}}
    planned, orphans = cure.plan_gold(gold, {"46415": record})
    assert planned == [] and orphans == []


def test_a_gold_entry_with_no_canonical_record_is_reported_never_cured():
    gold = {"99999": {"whatChanged": cure.FALSE_CLAIM + " body."}}
    planned, orphans = cure.plan_gold(gold, {})
    assert planned == []
    assert orphans == ["99999"]


def test_gold_accepts_both_the_wrapped_and_the_bare_shape():
    entry = {"whatChanged": "x"}
    assert cure.gold_entries({"data": {"46415": entry}}) == {"46415": entry}
    assert cure.gold_entries({"46415": entry}) == {"46415": entry}


def test_thin_outcomes_names_the_records_left_with_no_body():
    planned = [
        ("46631", "old", cure.FALSE_CLAIM, [PASS_TRUNCATED]),
        ("46442", "old", cure.FALSE_CLAIM + " A full informative sentence survives here.", [PASS_TRUNCATED]),
    ]
    assert cure.thin_outcomes(planned) == ["46631"]


# ---------------------------------------------------------------------------
# IMMUNE ORGANS — measured on the shipped catalogue, not on fixtures
# ---------------------------------------------------------------------------


def _canonical_records():
    return json.loads(CANONICAL.read_text(encoding="utf-8"))["data"]


def _gold():
    return cure.gold_entries(json.loads(GOLD.read_text(encoding="utf-8")))


def test_no_canonical_record_still_carries_any_of_the_three_defects():
    planned = cure.plan_canonical(_canonical_records())
    assert planned == [], (
        f"{len(planned)} canonical records still carry an unsupported provenance claim: "
        f"{[(c, p) for c, _, _, p in planned][:10]} — run cure_whatchanged_false_renumber.py --apply"
    )


def test_no_gold_entry_still_carries_any_of_the_three_defects():
    # Gold WINS over canonical on the rendered page, so a clean canonical proves
    # nothing on its own. This is the organ that would have caught 64995.
    records = _canonical_records()
    planned, _ = cure.plan_gold(_gold(), cure.canonical_index(records))
    assert planned == [], (
        f"{len(planned)} gold entries still carry an unsupported provenance claim: "
        f"{[(c, p) for c, _, _, p in planned][:10]} — gold renders in preference to canonical"
    )


def test_the_set_of_gold_entries_without_a_canonical_record_has_not_grown():
    _, orphans = cure.plan_gold(_gold(), cure.canonical_index(_canonical_records()))
    assert orphans == KNOWN_GOLD_ORPHANS, (
        "gold codes with no canonical record changed. They are inert today only because "
        "generateStaticParams iterates canonical and dynamicParams=false — a new one is a "
        "phantom-class row no canonical-keyed cure tool can reach."
    )


def test_the_gold_organ_is_load_bearing_because_gold_is_not_a_mirror_of_canonical():
    """Proves the second organ cannot be dropped as redundant.

    Gold and canonical hold different VINTAGES of the same field: pre-cure, 5
    codes were defective in canonical and already fine in gold. So "the two
    surfaces agree" is not the invariant — asserting equality would fail on
    healthy data — and equally, a clean canonical is no evidence about what a
    reader sees, because `transformCode` takes `whatChanged` from gold whenever
    a gold entry exists. If this test ever fails, gold has become a byte-copy of
    canonical and someone should ask why."""
    records = _canonical_records()
    by_code = cure.canonical_index(records)
    gold = _gold()
    divergent = [
        code
        for code, entry in gold.items()
        if code in by_code
        and isinstance(entry, dict)
        and str(entry.get("whatChanged") or "")
        != str(((by_code[code].get("intel_2026") or {}).get("whatChanged") or ""))
    ]
    assert divergent, "gold now mirrors canonical exactly — the two-organ split needs re-justifying"
