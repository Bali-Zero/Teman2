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
