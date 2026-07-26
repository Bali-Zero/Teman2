"""Guilt + innocence for the whatChanged language/enum cure.

Every guard here is paired: a GUILT case proving the rule fires on the real
defect, and an INNOCENCE case proving it does NOT fire on the legitimate
neighbour. A guard with only guilt tests is how superscar #3 keeps recurring —
eight instances on one hook, because each fix was proven to catch and never
proven to spare.
"""

from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE = REPO_ROOT / "scripts" / "kbli_filiera" / "cure_l23_whatchanged_language.py"
SPEC = REPO_ROOT / "scripts" / "kbli_filiera" / "cure_specs" / "l23_whatchanged_language.json"
CANONICAL = REPO_ROOT / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"


def _load_module():
    spec = importlib.util.spec_from_file_location("cure_l23", MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_module()


@pytest.fixture(scope="module")
def rules(mod):
    return mod.load_rules(SPEC)


def cure(mod, rules, text: str) -> str:
    return mod.cure_text(text, rules, Counter())


# --------------------------------------------------------------------------
# GUILT — each rule fires on the defect as it really appears in the dataset
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "before, must_contain, must_not_contain",
    [
        ("KBLI 2020→2025 mapping: codice rinumerato.", "code renumbered", "codice rinumerato"),
        ("KBLI 2020→2025 mapping: match con aggregazione.", "matched with aggregation", "match con aggregazione"),
        ("PP28 usa codice KBLI 2020 01270 (Pertanian).", "PP28 uses KBLI 2020 code 01270", "usa codice"),
        ("Aggregation: Dati da 01116 + 1 codici figli PP28", "data from 01116 + 1 PP28 child code(s)", "codici figli"),
        (
            "Verifica e aggiornamento NIB ora richiesti dopo la chiusura della finestra di giugno 2026.",
            "NIB verification and update are now required",
            "Verifica e aggiornamento",
        ),
        (
            "Verifica e aggiornamento OSS da eseguire ora dopo la chiusura della finestra di giugno 2026.",
            "OSS verification and update are now required",
            "da eseguire ora",
        ),
        ("Direct match from KBLI 2020 (MATCH_LANGSUNG).", "Direct match from KBLI 2020.", "MATCH_LANGSUNG"),
        ("MATCH_LANGSUNG — direct match from KBLI 2020.", "Direct match from KBLI 2020.", "MATCH_LANGSUNG"),
        ("MATCH_LANGSUNG.", "Unchanged from KBLI 2020", "MATCH_LANGSUNG"),
        ("CODICE_RINUMERATO.", "Renumbered from KBLI 2020", "CODICE_RINUMERATO"),
        ("MATCH_CON_AGGREGAZIONE.", "consolidates multiple KBLI 2020 activities", "MATCH_CON_AGGREGAZIONE"),
        ("BPS_ONLY.", "New in KBLI 2025", "BPS_ONLY"),
        ("it didn't exist in 2020 (BPS_ONLY status). Created to capture", "it didn't exist in 2020.", "BPS_ONLY"),
        ("CODICE_RINUMERATO from KBLI 2020 code 62012.", "Renumbered from KBLI 2020 code 62012", "CODICE_RINUMERATO"),
        ("MATCH_CON_AGGREGAZIONE from KBLI 2020 codes 62011.", "Consolidated from KBLI 2020 codes", "MATCH_CON_AGGREGAZIONE"),
        ("The MATCH_CON_AGGREGAZIONE mapping means some activities moved.", "The aggregated mapping means", "MATCH_CON_AGGREGAZIONE"),
        ("Cleaned: removed invalid ['01270'] Aggregation: x", "Aggregation: x", "removed invalid"),
        # gold-only forms — found by running the residue probe on the SECOND
        # surface rather than assuming gold mirrored canonical's diagnosis
        ("CODICE_RINUMERATO from 68130 (which was broader).", "Renumbered from KBLI 2020 code 68130", "CODICE_RINUMERATO"),
        ("New code in KBLI 2025 (BPS_ONLY with PP28 data).", "new in KBLI 2025, with PP28 data", "BPS_ONLY"),
        ("This is a BPS_ONLY code — it exists in 2025.", "a code new in KBLI 2025", "BPS_ONLY"),
        ("maintains the classification as BPS_ONLY, meaning detail is absent.", "as new in KBLI 2025", "BPS_ONLY"),
        # ---- L2.4: the same leak OUTSIDE whatChanged (whatYouNeed / baliContext /
        # zantaraOpener). Every `before` below is lifted verbatim from the real
        # corpus, not invented — these are sentences clients were reading.
        (
            "**BPS_ONLY** — no PP28/2025 licensing data exists yet.",
            "**New in KBLI 2025** — ",
            "BPS_ONLY",
        ),
        (
            "This code is marked **BPS_ONLY**. It is a new KBLI 2025 classification.",
            "marked **new in KBLI 2025**",
            "BPS_ONLY",
        ),
        (
            "**BPS_ONLY code** — no `per_skala` data in KBLI 2025 JSON. This means the OSS pathway is undefined.",
            "no PP28/2025 risk classification is published for this code yet.",
            "per_skala",
        ),
        (
            "Since it's BPS_ONLY (no PP28 licensing data yet), the requirements are pending.",
            "Since it's new in KBLI 2025 (",
            "BPS_ONLY",
        ),
        (
            "The BPS_ONLY status makes this a 'watch and wait' code.",
            "The new-in-2025 status",
            "BPS_ONLY",
        ),
        (
            "- **BPS_ONLY code means uncertainty:** 72201 is a new code without defined licensing.",
            "**New code, so licensing is still uncertain:**",
            "BPS_ONLY",
        ),
        (
            "72201 is the code. BPS_ONLY for now, so expect NIB-only registration.",
            "It is new in KBLI 2025, so expect",
            "BPS_ONLY",
        ),
        (
            "82400 is the BPS_ONLY intermediation code — no PP28 requirements yet.",
            "the new-in-2025 intermediation code",
            "BPS_ONLY",
        ),
        (
            "The local status is BLOCCATO_CLASSE_RISCHIO, meaning a moratorium prevents registration.",
            "The local status is a risk-class block, meaning a moratorium prevents",
            "BLOCCATO_CLASSE_RISCHIO",
        ),
        (
            "expect NIB-only for now (BPS_ONLY code) for the moment",
            "(new in KBLI 2025)",
            "BPS_ONLY",
        ),
    ],
)
def test_guilt_rule_fires_on_the_real_defect(mod, rules, before, must_contain, must_not_contain):
    after = cure(mod, rules, before)
    assert must_contain in after, f"rule did not produce the English rendering: {after!r}"
    assert must_not_contain not in after, f"defect survived the cure: {after!r}"


# --------------------------------------------------------------------------
# INNOCENCE — the legitimate neighbours the rules must SPARE
# --------------------------------------------------------------------------

def test_innocence_a_quoted_historical_label_is_never_rewritten(mod, rules):
    """The one that would have corrupted an audit trail.

    A record carries an English correction note citing the OLD Italian label as
    history. Every rule is anchored on its full template context precisely so a
    bare phrase match cannot reach inside this citation.
    """
    text = (
        "KBLI 2020->2025 mapping: direct 1:1 match (10433->10433). "
        "Corrected 2026-07-19 — the previous 'match con aggregazione' "
        "status_mapping/label was stale: it depended on a second parent."
    )
    after = cure(mod, rules, text)
    assert "'match con aggregazione'" in after, "the cure rewrote a quoted historical label"
    assert after == text, f"an already-English record was mutated: {after!r}"


def test_innocence_legitimate_acronyms_survive(mod, rules):
    """NIB / OSS / KBLI / PMA are real acronyms on these pages. The enum rules
    enumerate four tokens literally rather than matching an ALL-CAPS shape; a
    shape-matcher would eat these."""
    text = "Register the NIB via OSS for this KBLI code under PMA rules. See NPWP too."
    assert cure(mod, rules, text) == text


def test_innocence_already_english_text_is_untouched(mod, rules):
    text = "Unchanged from KBLI 2020 — direct match. Verify your activity maps correctly."
    assert cure(mod, rules, text) == text


def test_idempotent_second_pass_changes_nothing(mod, rules):
    once = cure(mod, rules, "KBLI 2020→2025 mapping: codice rinumerato. MATCH_LANGSUNG.")
    assert cure(mod, rules, once) == once


# --------------------------------------------------------------------------
# Contract-level guards
# --------------------------------------------------------------------------

def test_spec_with_no_rules_is_an_error_not_a_silent_noop(mod, tmp_path):
    """A cure that silently cures nothing is indistinguishable from one that
    worked — which is how a disarmed gate ships (W102). It must raise."""
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"version": 1, "rules": []}), encoding="utf-8")
    with pytest.raises(mod.CureError):
        mod.load_rules(empty)


def test_missing_spec_fails_loudly(mod, tmp_path):
    with pytest.raises(mod.CureError):
        mod.load_rules(tmp_path / "does-not-exist.json")


def test_residue_probe_does_not_reuse_the_cure_rules(mod, rules):
    """If the success-metric were the cure's own rule set it would report zero
    by construction. The probe must be able to see something the cure leaves."""
    leftover = "Il KBLI 2025 mantiene 46442 separato da 46441."
    assert cure(mod, rules, leftover) == leftover, "this sample must be OUT of cure scope"
    assert mod.residue_markers(leftover), "the probe is blind to uncured Italian"


def test_residue_probe_ignores_quoted_citations(mod):
    """...but the probe must not over-match either: the preserved citation is
    not residue. Measured 54 flagged before this strip, 5 after."""
    assert not mod.residue_markers("the previous 'match con aggregazione' label was stale")


# --------------------------------------------------------------------------
# Whole-dataset invariants (the claims the PR actually makes)
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def canonical_records():
    payload = json.loads(CANONICAL.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else payload.get("data") or payload.get("codes")


def test_no_raw_enum_token_survives_across_the_whole_catalog(mod, rules, canonical_records):
    import re

    survivors = []
    for rec in canonical_records:
        wc = (rec.get("intel_2026") or {}).get("whatChanged") or ""
        after = cure(mod, rules, wc)
        for tok in re.findall(r"\b[A-Z]{3,}(?:_[A-Z]+)+\b", after):
            survivors.append((rec.get("kode_kbli_2025"), tok))
    assert not survivors, f"raw enum tokens still reach clients: {survivors[:5]}"


def test_the_applied_dataset_is_a_FIXED_POINT_of_the_cure(mod, rules, canonical_records):
    """The cure must find nothing left to do on the committed dataset.

    This replaces an earlier version of this test that asserted ">400 records
    change" against the LIVE canonical. That assertion was self-inverting: it
    held only until the cure was applied, then failed forever — a test whose
    truth depends on the dataset being un-cured cannot survive the cure it
    guards. Non-vacuity is carried instead by the parametrised guilt corpus
    above, which is fixture-based and therefore stable in both directions.

    As a fixed-point check this is also a live regression tripwire: the
    upstream generator (kbli_enrichment_pipeline.build_what_changed) still
    emits these templates, so if the dataset is ever regenerated without
    re-running this cure, the count goes non-zero and this fails.
    """
    residual = [
        rec.get("kode_kbli_2025")
        for rec in canonical_records
        if (wc := (rec.get("intel_2026") or {}).get("whatChanged") or "")
        and cure(mod, rules, wc) != wc
    ]
    assert not residual, f"the committed dataset still has curable records: {residual[:8]}"


def test_the_guilt_corpus_is_not_vacuous(mod, rules):
    """Every rule in the spec must be exercised by at least one guilt case.

    Without this, adding a rule with no test would pass silently — the shape of
    gap that let three separate rules ship half-anchored earlier in this very
    file's history (the 'from KBLI' anchor that missed 'from 68130')."""
    exercised = set()
    for params in test_guilt_rule_fires_on_the_real_defect.pytestmark[0].args[1]:
        before = params[0]
        hits: Counter = Counter()
        mod.cure_text(before, rules, hits)
        exercised |= set(hits)
    declared = {r["id"] for r in rules}
    assert declared - exercised == set(), f"rules with no guilt case: {sorted(declared - exercised)}"


# ==========================================================================
# L2.4 — the cure widened past whatChanged. Each test below pins one thing
# that measurement (not intuition) said would otherwise go wrong.
# ==========================================================================

GOLD = REPO_ROOT / "apps" / "mouth" / "data" / "kbli-gold-all.json"


@pytest.fixture(scope="module")
def gold_payload():
    return json.loads(GOLD.read_text(encoding="utf-8"))


def test_the_field_policy_is_explicit_and_only_whatChanged_normalises(mod):
    """Whitespace normalisation is a per-FIELD property, not a global.

    `whatChanged` is machine-templated single-paragraph text where collapsing
    space runs is safe. The other three are editorial markdown whose two-space
    indentation is structure.
    """
    policy = dict(mod.FIELDS)
    assert policy == {
        "whatChanged": True,
        "whatYouNeed": False,
        "baliContext": False,
        "zantaraOpener": False,
    }


def test_markdown_indentation_survives_on_the_rich_text_fields(mod, rules):
    """The 184-record collateral this cure was redesigned to avoid.

    Measured 2026-07-26: running the rules over the three rich-text fields with
    normalisation ON mutates 184 records that contain NO enum leak at all,
    against 10 real hits — an 18:1 collateral-to-signal ratio, delivered inside
    a PR that claims only to remove enum tokens.
    """
    md = "Licensing:\n  Obligations: keep records\n  Requirements: bukti penguasaan lahan"
    assert mod.cure_text(md, rules, Counter(), normalize_whitespace=False) == md
    # ...and the whatChanged policy is genuinely different, so the test is not vacuous
    assert mod.cure_text(md, rules, Counter(), normalize_whitespace=True) != md


def test_a_record_is_written_only_when_a_rule_fired(mod, rules, gold_payload):
    """Structural guard on top of the whitespace policy.

    "the cure changed it" and "a declared rule changed it" must be the SAME set.
    If they ever diverge, something other than a reviewed rule is rewriting
    client-facing prose.
    """
    import copy

    before = copy.deepcopy(gold_payload)
    after = copy.deepcopy(gold_payload)
    changed, hits, _ = mod.cure_dataset(mod.gold_pairs(after), rules, None, "gold")

    mutated = {
        (code, field)
        for (code, b), (_, a) in zip(mod.gold_pairs(before), mod.gold_pairs(after))
        if isinstance(b, dict) and isinstance(a, dict)
        for field, _ in mod.FIELDS
        if b.get(field) != a.get(field)
    }
    assert len(mutated) == changed, f"collateral: {len(mutated)} mutated vs {changed} reported"
    assert sum(hits.values()) >= changed, "a rewrite happened with no rule firing"


def test_zantaraOpener_is_actually_reached(mod, rules, gold_payload):
    """The field the first census declared empty.

    It measured CANONICAL — where zantaraOpener genuinely never leaks — and
    extrapolated to gold, which leaked there twice (72201, 82400). Gold MASKS
    intel_2026 on /kbli/<code>, so a gold-only leak is a RENDERED leak.

    GUILT IS ON A FIXTURE, deliberately. The first version of this test asserted
    that live gold still contained a zantaraOpener leak — which was true when
    written and false the moment the cure ran, i.e. self-inverting in exactly
    the way test_the_applied_dataset_is_a_FIXED_POINT_of_the_cure warns about
    twenty lines up. Writing that same bug in the same file while fixing the
    field it describes is worth leaving on the record.

    So: the fixture proves the field is IN SCOPE and gets cured, and live gold
    carries the durable claim — nothing leaks there.
    """
    assert "zantaraOpener" in dict(mod.FIELDS)
    normalize = dict(mod.FIELDS)["zantaraOpener"]
    assert normalize is False, "zantaraOpener is editorial prose; it must not be reflowed"

    fixture = "82400 is the BPS_ONLY intermediation code — no PP28 requirements yet."
    assert mod.enum_residue(fixture), "fixture must actually contain the defect"
    cured = mod.cure_text(fixture, rules, Counter(), normalize_whitespace=normalize)
    assert not mod.enum_residue(cured), f"zantaraOpener text was not cured: {cured!r}"

    still = [
        code
        for code, intel in mod.gold_pairs(gold_payload)
        if isinstance(intel, dict)
        and isinstance(intel.get("zantaraOpener"), str)
        and mod.enum_residue(intel["zantaraOpener"])
    ]
    assert not still, f"gold zantaraOpener still leaks for: {still}"


# --------------------------------------------------------------------------
# The residue probe's own guilt and innocence — it was BLIND, and a blind
# probe is worse than none: it certifies.
# --------------------------------------------------------------------------

def test_probe_guilt_a_possessive_apostrophe_no_longer_swallows_the_leak(mod):
    """The exact shape that hid a real leak in gold 82400.baliContext.

    The old strip was `'[^']*'`, which in English prose is not a quote stripper
    but a PROSE stripper: the apostrophe in "Bali's" paired with one 468 chars
    later and swallowed everything between, leak included, reporting CLEAN.
    """
    text = (
        "A platform serving Bali's freelancer economy could operate under 82400. "
        "The BPS_ONLY status means low regulatory overhead. "
        "Think of it as the 'business services marketplace' code."
    )
    assert mod.enum_residue(text) == ["BPS_ONLY"], "the probe is blind to a leak after a possessive"


def test_probe_innocence_a_deliberate_citation_is_still_not_residue(mod):
    """The over-match the strip exists to prevent must stay prevented.

    Fixing the under-match by deleting the strip would corrupt an audit trail:
    one record CITES the old label as history and that citation is preserved
    text, not residue. Both signs of superscar #3 in one pair of tests.
    """
    assert not mod.enum_residue("the previous 'MATCH_CON_AGGREGAZIONE' label was stale")
    assert not mod.enum_residue("the field `BPS_ONLY` is an internal marker")
    assert not mod.residue_markers("the previous 'match con aggregazione' label was stale")


def test_probe_still_sees_italian_residue_after_the_bound(mod):
    """The bounded strip must not have blinded the Italian probe either."""
    assert mod.residue_markers("Il KBLI 2025 mantiene 46442 separato da 46441.")


# --------------------------------------------------------------------------
# Whole-corpus invariants for the widened scope
# --------------------------------------------------------------------------

def test_no_enum_token_survives_on_any_cured_field_either_surface(
    mod, rules, canonical_records, gold_payload
):
    """The claim this lot actually makes, measured in OCCURRENCES not records.

    That distinction is not pedantry: the census counted (record,field) PAIRS
    and reported 34, while the corpus holds 36 TOKENS — gold 72201.whatYouNeed
    carries three. Two leaks survived the first rule set and were caught by the
    probe, not the census. A unit mismatch between what you measure and what you
    fix reads as complete when it is not.
    """
    survivors = []
    for rec in canonical_records:
        intel = rec.get("intel_2026") or {}
        for field, norm in mod.FIELDS:
            v = intel.get(field)
            if isinstance(v, str) and v:
                after = mod.cure_text(v, rules, Counter(), normalize_whitespace=norm)
                survivors += [(rec.get("kode_kbli_2025"), field, t) for t in mod.enum_residue(after)]
    for code, intel in mod.gold_pairs(gold_payload):
        if not isinstance(intel, dict):
            continue
        for field, norm in mod.FIELDS:
            v = intel.get(field)
            if isinstance(v, str) and v:
                after = mod.cure_text(v, rules, Counter(), normalize_whitespace=norm)
                survivors += [(code, field, t) for t in mod.enum_residue(after)]
    assert not survivors, f"internal enum tokens still reach clients: {survivors[:6]}"


def test_no_field_is_left_with_unbalanced_bold_markers(mod, rules, gold_payload):
    """A half-applied bold rule leaves a stray `**` and silently italicises the
    rest of the paragraph. Cheap invariant, catches exactly that class."""
    bad = []
    for code, intel in mod.gold_pairs(gold_payload):
        if not isinstance(intel, dict):
            continue
        for field, norm in mod.FIELDS:
            v = intel.get(field)
            if not isinstance(v, str) or not v:
                continue
            before_n = v.count("**")
            after = mod.cure_text(v, rules, Counter(), normalize_whitespace=norm)
            if after != v and after.count("**") % 2 != before_n % 2:
                bad.append((code, field))
    assert not bad, f"cure changed the bold-marker parity of: {bad[:6]}"
