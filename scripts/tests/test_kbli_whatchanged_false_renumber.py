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
    PASS_FALSE_CONTINUITY,
    PASS_TRUNCATED,
    WhatChangedError,
    claims_ambiguous_continuity,
    contradicted_predecessors,
    has_no_recorded_predecessor,
    is_truncated_midword,
    number_is_discontinuous,
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
# PASS D — "your number is unchanged" where the crosswalk says it changed
# ---------------------------------------------------------------------------
#
# The client-facing shape of this one: a business reads "Unchanged from KBLI
# 2020 — direct match" on /kbli/90130 and concludes its existing NIB number
# still classifies it. Our own crosswalk records 90021/90029/90030/90090 as that
# code's 2020 origin — the number did NOT carry over, and "no action needed" is
# the wrong inference to hand someone. Measured on the shipped catalogue
# 2026-08-05: 17 (code, surface) pairs across 14 codes.

CONTINUITY_TEXT = "Unchanged from KBLI 2020 — direct match."


def _discontinuous(what_changed=CONTINUITY_TEXT):
    """A record whose own code (99999) is in NO layer — the number changed."""
    return _record(what_changed=what_changed, bps_2020_ancestors={"codes": ["11111", "22222"]})


def test_d_fires_when_the_records_own_code_is_in_no_layer():
    assert _passes(_discontinuous()) == [PASS_FALSE_CONTINUITY]


def test_d_does_not_fire_when_the_code_carried_over_for_real():
    # The innocence case that carries the pass: a record whose 2020 origin IS
    # itself. Most "unchanged" sentences in the catalogue are TRUE, and a cure
    # that deleted them would destroy correct prose on the majority to fix 14.
    rec = _record(what_changed=CONTINUITY_TEXT, bps_2020_ancestors={"codes": ["99999", "11111"]})
    assert _passes(rec) == []
    assert number_is_discontinuous(rec) is False


def test_d_does_not_fire_on_a_text_that_claims_no_continuity():
    rec = _discontinuous(what_changed="Split from a broader 2020 activity. Verify your NIB.")
    assert _passes(rec) == []


def test_d_refuses_when_no_layer_holds_anything():
    # Nothing on file cannot contradict anything. Pass A owns the "no
    # predecessor recorded" statement; convicting here would delete prose
    # against zero evidence.
    rec = _record(what_changed=CONTINUITY_TEXT)
    assert _passes(rec) == []
    assert number_is_discontinuous(rec) is False


def test_d_refuses_when_the_layer_rows_are_unreadable():
    # Rows on file that yield no code: UNDECIDABLE, which is not CLEAN. Same
    # standing rule as pass C — this pass has no basis to delete.
    rec = _record(what_changed=CONTINUITY_TEXT, bps_2020_ancestors={"note": "locator only"})
    assert _passes(rec) == []
    assert number_is_discontinuous(rec) is False


def test_d_names_no_2020_code_at_all():
    # The strongest constraint on this pass, and the one that cost the most to
    # learn: an earlier draft enumerated the record's recorded predecessors, and
    # on 4 of the 14 live codes that enumeration contradicted the BPS crosswalk
    # (91212's record says 91012, BPS says 91022). Those records hold only the
    # weaker layer, so the function could not see the disagreement. The negative
    # — this number is not its own 2020 predecessor — is what survives an
    # independent check, so it is all the sentence may assert.
    rec = _discontinuous()
    out, passes = plan_text(CONTINUITY_TEXT, rec)
    assert passes == [PASS_FALSE_CONTINUITY]
    # No carve-out on this assertion: the replacement must not contain the
    # trigger phrase at all. An earlier version subtracted "carrying over
    # unchanged from KBLI 2020" before checking — working around the collision
    # instead of seeing it, which is exactly how the non-idempotence shipped.
    assert "unchanged from KBLI 2020" not in out.lower()
    assert "11111" not in out and "22222" not in out
    assert "99999" in out  # the code being described, never a substitute for it
    assert "unconfirmed" in out


def test_d_leaves_the_ambiguous_wording_alone_when_it_stands_by_itself():
    # "Direct match from KBLI 2020" can mean the same NUMBER or a clean 1:1
    # ACTIVITY mapping onto a different one — 49213's own prose resolves it the
    # second way. Alone, it is not evidence of the defect and is never cured.
    rec = _discontinuous(what_changed="Direct match from KBLI 2020. Verify your NIB.")
    assert _passes(rec) == []
    assert claims_ambiguous_continuity(str(rec["intel_2026"]["whatChanged"])) is True


def test_d_removes_the_ambiguous_wording_once_the_narrow_pattern_convicts():
    # 96210, measured: "Direct match from KBLI 2020. Same code, same scope. …"
    # Leaving sentence one behind publishes the overturned rationale next to the
    # correction, in one breath. Guilt is decided narrow; removal takes both.
    text = "Direct match from KBLI 2020. Same code, same scope. Hair salons are stable."
    rec = _discontinuous(what_changed=text)
    out, passes = plan_text(text, rec)
    assert passes == [PASS_FALSE_CONTINUITY]
    assert "Direct match from KBLI 2020" not in out
    assert "Same code, same scope" not in out
    assert out.endswith("Hair salons are stable.")  # unrelated prose survives verbatim


def test_d_and_c_compose_when_one_sentence_carries_both_claims():
    # Pass C takes the sentence first; pass D must then find nothing and say so
    # by not claiming a pass, instead of raising on a text that is now correct.
    text = "KBLI 2020: 46415 — unchanged from KBLI 2020."
    rec = _record(what_changed=text, bps_2020_ancestors={"codes": ["11111"]})
    out, passes = plan_text(text, rec)
    assert PASS_CONTRADICTED_PREDECESSOR in passes
    assert PASS_FALSE_CONTINUITY not in passes
    assert "unchanged from KBLI 2020" not in out.lower()


def test_d_replacement_speaks_about_our_records_not_about_the_regulator():
    out, _ = plan_text(CONTINUITY_TEXT, _discontinuous())
    assert "Our records do not support" in out
    for forbidden in ("was renumbered to", "is now", "BPS abolished", "you must re-register"):
        assert forbidden.lower() not in out.lower()


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
    # Pass D was added to this list AFTER it shipped a replacement sentence that
    # contained its own trigger phrase ("…carrying over unchanged from KBLI
    # 2020"). The cure re-convicted its own output, so a successful `--apply`
    # left the live-file organs red — the only visible symptom, because every
    # unit test still passed. A pass whose cured text is not in this loop is a
    # pass that can quietly do that again.
    for text, rec in (
        (NAMED_TEXT, _record(what_changed=NAMED_TEXT, kbli_2020_source="46694")),
        (cure.FALSE_CLAIM + " body.", _record(what_changed=cure.FALSE_CLAIM + " body.")),
        (CONTINUITY_TEXT, _discontinuous()),
        ("Direct match from KBLI 2020. Same code, same scope.", _discontinuous(
            what_changed="Direct match from KBLI 2020. Same code, same scope."
        )),
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


def test_the_kg_spec_is_byte_stable_and_already_in_the_repo_json_shape():
    """A committed compiler artifact must not depend on who ran it last.

    `json.dumps` puts every array element on its own line; the repo's pre-commit
    prettier collapses short ones. If the compiler emitted the first shape,
    every emit would be followed by a hand `prettier --write` and the file's
    bytes would drift with the operator. So the compiler emits prettier's shape
    itself — and the same input must produce the same bytes (G16)."""
    spec = {
        "spec_id": "kg_whatchanged",
        "entries": [
            {"entity_id": "kbli:64995", "passes": ["false_renumbering_claim", "midword_truncation"]},
            {"entity_id": "kbli:46415", "passes": ["contradicted_predecessor"]},
        ],
    }
    rendered = cure.render_spec_json(spec)
    assert rendered == cure.render_spec_json(spec)
    assert rendered.endswith("\n") and not rendered.endswith("\n\n")
    assert '"passes": ["contradicted_predecessor"]' in rendered
    assert '"passes": ["false_renumbering_claim", "midword_truncation"]' in rendered
    assert json.loads(rendered) == spec  # the reshaping must never change the DATA


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


BPS_EDGES = [
    REPO_ROOT / "data" / "kbli-filiera" / "bps-crosswalk" / "edges-lampiran5.json",
    REPO_ROOT / "data" / "kbli-filiera" / "bps-crosswalk" / "edges-lampiran10.json",
]


def _bps_self_edges() -> set[str]:
    """Codes the government crosswalk maps to THEMSELVES — the ones that really did
    carry over. Not "codes present on the 2020 side": a first version of this organ
    used that and failed on 4 records, correctly. A 2020 code can be re-used as a
    2025 code for a different activity while its own 2025 heir is a new number —
    a shuffle, where "unchanged" is still false. The only edge that refutes the
    verdict is X(2020) → X(2025)."""
    self_edges: set[str] = set()
    for path in BPS_EDGES:
        for row in json.loads(path.read_text(encoding="utf-8")):
            old, new = row.get("kbli_2020"), row.get("kbli_2025")
            if old and new and str(old) == str(new):
                self_edges.add(str(old))
    return self_edges


def test_pass_d_never_convicts_a_code_the_government_crosswalk_maps_to_itself():
    # The innocence organ for pass D, and the only check here that asks a source
    # OTHER than the record's own fields. The pass reads the record, so a
    # record-derived check would only agree with itself (W100); these edge files
    # are the transcription of Peraturan BPS 7/2025 lampiran 5 + 10. Measured
    # 2026-08-05: 908 codes carry a self-edge, 454 records are marked
    # discontinuous, and the intersection is EMPTY — the verdict is corroborated
    # for the whole population, not only the 14 this cure rewrites.
    self_edges = _bps_self_edges()
    assert len(self_edges) > 500, "the edge files did not load — a blind pass is not a clean one"

    records = _canonical_records()
    guilty = {str(r[cure.CODE_FIELD]) for r in records if number_is_discontinuous(r)}
    assert guilty, "no record is discontinuous — the predicate is inert, not innocent"
    overlap = sorted(guilty & self_edges)
    assert overlap == [], (
        f"{len(overlap)} code(s) are marked discontinuous by their own record yet the BPS "
        f"crosswalk maps them to themselves: {overlap[:10]} — pass D would delete a TRUE sentence"
    )


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


# ---------------------------------------------------------------------------
# update_sidecar() — the field name IS the contract
# ---------------------------------------------------------------------------
#
# 2026-07-25: this function wrote a bare "sha256" key while the sidecar
# schema (and apps/mouth/src/lib/kbli-dataset-version.test.ts) reads
# "datasetSha256" — the write succeeded, the file changed, and the vitest
# guard still went red on a merged PR because it was checking a field the
# write never touched. Guilt: a wrong key name must fail. Innocence: the
# right key name, with an unrelated key already present, must pass and must
# not disturb that unrelated key.


def _run_update_sidecar(tmp_path: Path, dataset_bytes: bytes, sidecar_before: dict) -> dict:
    import hashlib

    dataset_path = tmp_path / "KBLI_2025_FINAL_CLEAN.json"
    dataset_path.write_bytes(dataset_bytes)
    sidecar_path = tmp_path / "kbli-dataset-version.json"
    sidecar_path.write_text(json.dumps(sidecar_before), encoding="utf-8")

    original_dataset_path = cure.SIDECAR_DATASET_PATH
    original_sidecar_path = cure.SIDECAR_PATH
    cure.SIDECAR_DATASET_PATH = dataset_path
    cure.SIDECAR_PATH = sidecar_path
    try:
        cure.update_sidecar()
    finally:
        cure.SIDECAR_DATASET_PATH = original_dataset_path
        cure.SIDECAR_PATH = original_sidecar_path

    after = json.loads(sidecar_path.read_text(encoding="utf-8"))
    expected = f"sha256:{hashlib.sha256(dataset_bytes).hexdigest()}"
    return after, expected


def test_update_sidecar_writes_datasetSha256_not_a_lookalike_key(tmp_path: Path):
    after, expected = _run_update_sidecar(
        tmp_path,
        b'{"data": ["fixture content A"]}',
        {"lastModified": "2020-01-01", "datasetSha256": "sha256:stale", "note": "keep me"},
    )
    assert after["datasetSha256"] == expected
    assert "sha256" not in after, "a stray top-level 'sha256' key means the wrong field was written"
    assert after["note"] == "keep me", "update_sidecar must not disturb unrelated keys"


def test_update_sidecar_is_guilty_of_the_2026_07_25_regression_if_it_reappears():
    # Direct guilt check on the shipped function body, not a fixture: prove the
    # exact wrong key name from the incident is not the one being written.
    import inspect

    source = inspect.getsource(cure.update_sidecar)
    assert 'sidecar["sha256"]' not in source, (
        "update_sidecar() writes sidecar['sha256'] again — the field the vitest "
        "guard and the sidecar schema actually read is 'datasetSha256'"
    )


def test_live_sidecar_datasetSha256_matches_the_live_dataset_hash():
    """Python-side mirror of apps/mouth/src/lib/kbli-dataset-version.test.ts.

    Two independent runtimes (Python here, vitest in CI) checking the same
    invariant on the same committed files — neither can silently drift
    without both going red.
    """
    import hashlib

    dataset = (REPO_ROOT / "apps" / "mouth" / "data" / "KBLI_2025_FINAL_CLEAN.json").read_bytes()
    sha = hashlib.sha256(dataset).hexdigest()
    sidecar = json.loads(
        (REPO_ROOT / "apps" / "mouth" / "data" / "kbli-dataset-version.json").read_text(encoding="utf-8")
    )
    assert sidecar["datasetSha256"] == f"sha256:{sha}", (
        "sidecar datasetSha256 is stale — run cure.update_sidecar() or bump it by hand"
    )


# ---------------------------------------------------------------------------
# Pass D — the wording census was measured on TWO surfaces, and the third
# spoke differently (2026-08-05)
# ---------------------------------------------------------------------------

# The nine shapes below are LIVE `kg_nodes.properties.whatChanged` values, read
# from prod on 2026-08-05. All nine sat on records where `number_is_discontinuous`
# was already True, on codes whose website copy had ALREADY been cured — so the
# site told the truth while WhatsApp and webchat kept saying the number carried
# over. The narrow pattern of #3602 was written from canonical + gold wordings
# and was blind to every one of them.
LIVE_KG_ASSERTIONS = (
    "Direct 1:1 match from KBLI 2020 — code and scope unchanged.",
    "Direct match from KBLI 2020. No structural changes. Web portals and "
    "information services keep the same code and scope.",
)

# …and the two the widening still refuses, on purpose. Neither asserts the
# DIGITS carried over: the first names a different number in the same breath,
# the second speaks about the activity classification.
LIVE_KG_REFUSALS = (
    "Direct match from KBLI 2020, but the PP28 source code is 68200 — the old "
    "general real estate services code.",
    "Direct match from KBLI 2020. Traditional health services classification unchanged.",
)


@pytest.mark.parametrize("text", LIVE_KG_ASSERTIONS)
def test_pass_d_convicts_the_live_kg_wordings_it_used_to_read_as_innocent(text):
    """GUILT. A pattern written from the instances you looked at catches the
    instances you looked at — these are the ones nobody had looked at."""
    record = {"kode_kbli_2025": "74199", "kbli_2020_source": "74190"}
    assert number_is_discontinuous(record), "premise: the record must be discontinuous"
    _, passes = plan_text(text, record)
    assert PASS_FALSE_CONTINUITY in passes, f"still innocent to the guard: {text!r}"


@pytest.mark.parametrize("text", LIVE_KG_ASSERTIONS)
def test_pass_d_leaves_the_same_wordings_alone_when_the_number_really_did_carry_over(text):
    """INNOCENCE. The conjunction is what protects the ~908 codes the government
    crosswalk maps to themselves: identical prose, continuous record, no verdict."""
    record = {"kode_kbli_2025": "01111", "kbli_2020_source": "01111"}
    assert not number_is_discontinuous(record), "premise: the record must be continuous"
    _, passes = plan_text(text, record)
    assert PASS_FALSE_CONTINUITY not in passes


@pytest.mark.parametrize("text", LIVE_KG_REFUSALS)
def test_pass_d_still_refuses_the_two_shapes_that_assert_something_narrower(text):
    """The declared limit stays declared — these are census rows, not cures."""
    record = {"kode_kbli_2025": "68210", "kbli_2020_source": "68200"}
    assert number_is_discontinuous(record)
    _, passes = plan_text(text, record)
    assert PASS_FALSE_CONTINUITY not in passes
    assert claims_ambiguous_continuity(text), "…and it must still be REPORTED by the census"


# ---------------------------------------------------------------------------
# …and a quotation of the claim is not an assertion of it
# ---------------------------------------------------------------------------

# Verbatim from canonical `52101` on 2026-08-05. A hand-written correction that
# QUOTES the label it corrects. The first draft of the widening matched inside
# that quotation and spliced the replacement into the middle of a dangling
# quote — output that was not merely a false positive but gibberish, and that
# would have overwritten an image-verified five-parent merge with "the mapping
# is unconfirmed". W113: the probe judged by FORM and caught the citation living
# inside the retraction.
SCAR_52101 = (
    "Renumbered/merged from KBLI 2020 52108 + fishery post-harvest services codes "
    "— activity scope from 52108, code number reused (corrected 2026-07-19 — the "
    "previous 'Direct 1:1 match... code and scope unchanged' label was a false "
    "narrative)."
)


def test_a_correction_that_quotes_the_claim_is_not_convicted_of_making_it():
    record = {"kode_kbli_2025": "52101", "kbli_2020_source": "52108"}
    assert number_is_discontinuous(record), "premise: 52101 is not its own predecessor"
    cured, passes = plan_text(SCAR_52101, record)
    assert PASS_FALSE_CONTINUITY not in passes
    assert cured == SCAR_52101, "the text must come back untouched, not merely unconvicted"


def test_the_live_52101_record_is_not_convicted_by_the_shipped_predicates():
    """Scar pin on the real file, not on a fixture: if a future widening starts
    convicting this record again, this goes red before it reaches a client."""
    records = _canonical_records()
    record = next(
        r for r in records if str(r.get(cure.CODE_FIELD) or "") == "52101"
    )
    text = (record.get("intel_2026") or {}).get("whatChanged") or record.get("whatChanged") or ""
    assert "code and scope unchanged" in text, (
        "premise gone: 52101 no longer quotes the label it corrects, so this pin "
        "is testing nothing — re-anchor it or delete it"
    )
    _, passes = plan_text(text, record)
    assert PASS_FALSE_CONTINUITY not in passes


def test_an_unbalanced_quote_masks_nothing_and_an_apostrophe_fabricates_nothing():
    """Both directions of the twin the quotation guard could have birthed (W94):
    a greedy quote scan that swallows the rest of the text hides real claims,
    and treating every `'` as a delimiter turns "don't … it's" into a region."""
    record = {"kode_kbli_2025": "74199", "kbli_2020_source": "74190"}
    unbalanced = "a stray ' quote opens here and code and scope unchanged follows"
    apostrophes = "We don't say it's settled: code and scope unchanged."
    both_quoted_and_bare = (
        "A note reading 'code and scope unchanged' — and separately, code and scope unchanged."
    )
    for text in (unbalanced, apostrophes, both_quoted_and_bare):
        _, passes = plan_text(text, record)
        assert PASS_FALSE_CONTINUITY in passes, f"masked by the quotation guard: {text!r}"


def test_a_surface_with_nothing_to_rewrite_is_not_written_at_all():
    """A run that reports "wrote 0 gold entry(ies)" must leave the bytes alone.

    It did not: re-serialising the untouched surface stripped the trailing
    newline from `kbli-gold-all.json`, so the diff carried a file the run had
    just declared untouched and `prettier --check` failed on a change nobody
    made. Pinned on the SOURCE because the effect is an absence — there is no
    output to assert against.
    """
    import inspect

    source = inspect.getsource(cure.main)
    assert "if gold_plan:" in source and "if canonical_plan:" in source, (
        "main() writes a surface unconditionally again — a cure with an empty "
        "plan for one surface must not touch that surface's file"
    )
