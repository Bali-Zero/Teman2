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
        # ---- Bali-status symbols. Found only after the probe stopped being
        # shape-based: OK_or_HIGHER_RISK is not SCREAMING_SNAKE (lower-case
        # "or"), so a \b[A-Z]{3,}(?:_[A-Z]+)+\b matcher walks straight past the
        # most common internal symbol in the catalogue.
        (
            "the activity is not blocked by a local moratorium (OK_or_HIGHER_RISK), but the ban stands.",
            "not blocked by a local moratorium, but the ban stands.",
            "OK_or_HIGHER_RISK",
        ),
        (
            "the moratorium does not block this code (OK_or_HIGHER_RISK, medium-high risk), so there is no extra wall.",
            "(medium-high risk), so there is no extra wall.",
            "OK_or_HIGHER_RISK",
        ),
        (
            "Bali's current assessment lists it as OK_or_HIGHER_RISK — it is not blocked by the moratorium.",
            "lists it as registrable in Bali",
            "OK_or_HIGHER_RISK",
        ),
        (
            "classifying this retail trade as 'BLOCCATO_CLASSE_RISCHIO'.",
            "as blocked in Bali by the risk-class moratorium.",
            "BLOCCATO_CLASSE_RISCHIO",
        ),
        # ---- L2.6: the last Italian left in whatChanged after L2.3 cured the
        # templates. These are FREE PROSE, not machine templates, which is why
        # the earlier template map never reached them. Every `before` is the
        # stored value verbatim.
        (
            "Renumbered/adjusted from KBLI 2020. 46411 stabile.",
            "46411 is unchanged.",
            "stabile",
        ),
        (
            "Renumbered/adjusted from KBLI 2020. KBLI 64910 invariato 2020→2025.",
            "KBLI 64910 is unchanged from 2020 to 2025.",
            "invariato",
        ),
        (
            "Il KBLI 2025 mantiene 46442 separato da 46441, rafforzando la distinzione regolatorio-ministeriale introdotta in KBLI 2020.",
            "KBLI 2025 keeps 46442 separate from 46441, reinforcing the regulatory/ministerial distinction introduced in KBLI 2020.",
            "mantiene",
        ),
        (
            "Eredita parte del vecchio 46421 KBLI 2020. In KBLI 2025 scorporato in 46451 (alat tulis) e 46452 (percetakan). Verificare mapping NIB per non perdere licenze API-U esistenti.",
            "it was split into 46451 (alat tulis — stationery) and 46452 (percetakan — printing)",
            "scorporato",
        ),
        (
            "Questo è il codice KBLI 2025 per il vecchio 46444 (alat kesehatan). Non confondere con 46430 (ottica consumer): lenti correttive e dispositivi diagnostici appartengono qui, non lì.",
            "corrective lenses and diagnostic devices belong here, not there.",
            "confondere",
        ),
        (
            "Codice completamente nuovo in KBLI 2025 (parte nuova Categoria V — Carbon & Environment). Nessuna migrazione da KBLI 2020 necessaria. Solo nuova registrazione.",
            "No migration from KBLI 2020 is needed — only a fresh registration.",
            "migrazione",
        ),
        (
            "Transizione puramente amministrativa. UU P2SK framework sovraordinato.",
            "The UU P2SK framework is the overarching legal structure.",
            "sovraordinato",
        ),
        (
            "POJK 46/2024 è norma di riferimento principale entrata in vigore fine 2024.",
            "POJK 46/2024 is the principal reference regulation, in force since late 2024.",
            "norma di riferimento",
        ),
        (
            "POJK 40/2024 framework attuale (sostituisce POJK 10/2022). UU P2SK base legislativa.",
            "superseding POJK 10/2022, with UU P2SK as the legislative basis.",
            "sostituisce",
        ),
        (
            "KBLI 66125 invariato 2020→2025 (sotto categoria 6612 — Aktivitas Perantara Transaksi).",
            "(under subgroup 6612 — Aktivitas Perantara Transaksi, transaction intermediary activities)",
            "sotto categoria",
        ),
        (
            "BI regolatore esclusivo tramite PBI 6/2024.",
            "Bank Indonesia is the sole regulator, under PBI 6/2024.",
            "regolatore esclusivo",
        ),
        # ---- L2.6 truncations. Each `before` ends exactly where the stored
        # value ends: mid-word.
        (
            "POJK 46/2024 in force. Licenze esistenti v",
            "POJK 46/2024 in force.",
            "Licenze esistenti",
        ),
        (
            "the June 2026 window. Verifica aggiornamento l",
            "the June 2026 window.",
            "Verifica aggiornamento",
        ),
        (
            "Bank Indonesia is the sole regulator, under PBI 6/2024 e PADG cor",
            "under PBI 6/2024.",
            "PADG",
        ),
        (
            "following the closure of the June 2026 window. POJK 3/2024 (ITSK) gove",
            "Also cited for this code: POJK 3/2024 (ITSK — Financial Sector Technology Innovation).",
            "(ITSK) gove",
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


def test_probe_innocence_the_italian_citation_is_still_not_residue(mod):
    """The over-match the Italian strip exists to prevent must stay prevented.

    Deleting that strip to fix the under-match would corrupt an audit trail: a
    record CITES the old Italian label as history, and that citation is preserved
    text. Both signs of superscar #3 held by one pair of tests.

    NOTE the asymmetry, which is deliberate and was corrected on measurement:
    quoting exempts an ITALIAN LABEL from residue_markers, but it does NOT exempt
    an internal ENUM token from enum_residue — see the next test.
    """
    assert not mod.residue_markers("the previous 'match con aggregazione' label was stale")


def test_probe_vocabulary_is_not_smaller_than_the_defect(mod):
    """L2.6 GUILT on the PROBE. It reported 2 residual records; there were 9.

    Every sentence below is a real client-facing value the probe walked past
    because none of its 11 original markers appeared in it. A bound that is
    smaller than the defect is not conservative — the line "residue: 2" reads as
    "almost done" and is why this field stayed Italian for three lots.
    """
    missed = [
        "KBLI 64910 invariato 2020→2025.",
        "Eredita parte del vecchio 46421 KBLI 2020.",
        "In KBLI 2025 scorporato in 46451 (alat tulis).",
        "Non confondere con 46430 (ottica consumer).",
        "Codice completamente nuovo in KBLI 2025.",
        "Nessuna migrazione da KBLI 2020 necessaria.",
        "POJK 46/2024 è norma di riferimento principale.",
        "UU P2SK framework sovraordinato.",
        "POJK 40/2024 framework attuale (sostituisce POJK 10/2022).",
        "(sotto categoria 6612 — Aktivitas Perantara Transaksi)",
        "BI regolatore esclusivo tramite PBI 6/2024.",
        "lenti correttive e dispositivi diagnostici appartengono qui",
        "rafforzando la distinzione regolatorio-ministeriale introdotta in KBLI 2020",
        "Verificare mapping NIB per non perdere licenze API-U esistenti.",
    ]
    blind = [s for s in missed if not mod.residue_markers(s)]
    assert blind == [], f"the probe is still blind to real Italian: {blind}"


def test_probe_innocence_english_prose_is_not_italian_residue(mod):
    """The under-match fix must not ship its own over-match twin.

    These markers are matched as SUBSTRINGS, so a bare "eredita" would fire
    inside the English word "hereditary" — the same form-vs-entity error, at the
    opposite sign, inside the list written to cure an under-match. The marker is
    anchored to "eredita parte" for exactly this reason, and this test is what
    stops a future tidy-up from shortening it back.
    """
    innocent = [
        "Hereditary land rights are governed separately.",
        "The licensee must renew before expiry.",
        "This is a new code, completely separate from the old one.",
        "Verify the NIB mapping before you register.",
    ]
    guilty = [s for s in innocent if mod.residue_markers(s)]
    assert guilty == [], f"the probe now over-matches English prose: {guilty}"


def test_probe_a_scare_quoted_enum_is_a_leak_not_a_citation(mod):
    """Quoting does not make an internal symbol client-appropriate.

    The first version of enum_residue skipped any immediately-wrapped token, by
    analogy with the Italian citation above. Measured across all four cured
    fields on both surfaces, exactly ONE immediately-quoted enum token existed —
    canonical 47249.whatYouNeed, "classifying this retail trade as
    'BLOCCATO_CLASSE_RISCHIO'" — and it was scare-quotes in client prose, not
    evidence. The exemption protected nothing and hid a real leak.
    """
    leak = "classifying this retail trade as 'BLOCCATO_CLASSE_RISCHIO'."
    assert mod.enum_residue(leak) == ["BLOCCATO_CLASSE_RISCHIO"]


def test_probe_sees_symbols_that_are_not_screaming_snake(mod):
    """OK_or_HIGHER_RISK is the most common internal symbol in the catalogue and
    a \\b[A-Z]{3,}(?:_[A-Z]+)+\\b matcher cannot see it — the lower-case "or"
    breaks the shape. Three real prose leaks (84111, 84144, 84146) hid behind
    exactly that assumption. Shape is not entity; this is the third time in this
    lane that mistake surfaced."""
    assert mod.enum_residue("the moratorium does not block it (OK_or_HIGHER_RISK)") == [
        "OK_or_HIGHER_RISK"
    ]
    # ...and the shape catch-all still works for tokens nobody has catalogued
    assert mod.enum_residue("status is SOME_FUTURE_SYMBOL now") == ["SOME_FUTURE_SYMBOL"]


def test_the_probe_agrees_with_the_frontend_about_what_an_internal_symbol_is(mod):
    """Two tools that must agree should not each invent an answer.

    apps/mouth/src/lib/kbli-status-labels.ts is the AUTHORITY: BaliStatusBadge,
    TransitionBadge and the render-layer cure all read it. This test parses that
    file and asserts every symbol it lists is visible to enum_residue, so the
    Python mirror cannot silently drift from the TypeScript source. Terms of art
    (TERBUKA/TERTUTUP/TERBATAS) are excluded there by design — they are the
    official Indonesian vocabulary the product deliberately teaches — so they are
    excluded here too, and asserted to be SPARED.
    """
    import re

    src = (REPO_ROOT / "apps" / "mouth" / "src" / "lib" / "kbli-status-labels.ts").read_text(
        encoding="utf-8"
    )
    block = src[src.index("BALI_STATUS_CONFIG") : src.index("MAPPING_STATUS_LABELS")]
    terms_of_art = {"TERBUKA", "TERTUTUP", "TERBATAS"}
    symbols = [k for k in re.findall(r"^\s{2}([A-Za-z0-9_]+):\s*\{", block, re.M)]
    symbols += ["MATCH_LANGSUNG", "CODICE_RINUMERATO", "MATCH_CON_AGGREGAZIONE", "BPS_ONLY"]
    watched = [s for s in symbols if s not in terms_of_art]
    assert len(watched) >= 15, f"parsed too few symbols ({len(watched)}) — the parse broke, not the code"

    blind = [s for s in watched if mod.enum_residue(f"status is {s} today") != [s]]
    assert not blind, f"enum_residue cannot see these internal symbols: {blind}"

    # INNOCENCE: the terms of art must NOT be flagged — they are vocabulary.
    for term in terms_of_art:
        assert mod.enum_residue(f"ownership is {term} at 100%") == []


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


# ==========================================================================
# L2.5 — the top-level fields. `whatChanged` EMBEDS `mapping_note`, but they
# are two independent stored copies, so curing one left the other Italian.
# ==========================================================================

def test_top_level_field_policy_is_explicit(mod):
    policy = dict(mod.TOP_LEVEL_FIELDS)
    assert policy == {"mapping_note": True, "aggregation_note": True}
    # These are single-line machine output, so normalisation is safe — the
    # opposite call from whatYouNeed, and made on measurement rather than taste.
    assert all(policy.values())


@pytest.mark.parametrize(
    "before, expected",
    [
        (
            "PP28 usa codice KBLI 2020 01122 (Pertanian Padi Inbrida...). Match: 80%",
            "PP28 uses KBLI 2020 code 01122 (Pertanian Padi Inbrida...). Match: 80%",
        ),
        ("Dati da 01116 + 1 codici figli PP28", "data from 01116 + 1 PP28 child code(s)"),
        # The whole value is pipeline debris — a Python list literal — and it was
        # rendered to clients verbatim. Emptying is correct, not lossy: which 2020
        # codes a record does and does not carry lives structurally in
        # pp28_sources / kbli_2020_source, which is where an audit trail belongs.
        ("Cleaned: removed invalid ['01272']", ""),
    ],
)
def test_top_level_guilt_on_the_real_values(mod, rules, before, expected):
    assert mod.cure_text(before, rules, Counter(), normalize_whitespace=True) == expected


def test_the_debris_records_render_nothing_rather_than_a_dangling_dash(mod):
    """Emptying `mapping_note` must not leave "— " on the page.

    Asserted against the FRONTEND SOURCE, not assumed: both consumers guard on
    truthiness, so an empty string renders nothing. If either guard is ever
    removed, 88 pages would show a bare em-dash and this test says so.
    """
    page = (REPO_ROOT / "apps" / "mouth" / "src" / "app" / "kbli" / "[code]" / "page.tsx").read_text(
        encoding="utf-8"
    )
    faq = (REPO_ROOT / "apps" / "mouth" / "src" / "lib" / "kbli-faq.ts").read_text(encoding="utf-8")
    assert "kbli.transition.mappingNote && (" in page, "the crosswalk row lost its truthiness guard"
    assert "code.transition.mappingNote ?" in faq, "the FAQ answer lost its truthiness guard"


def test_top_level_pass_is_canonical_only_because_gold_has_no_such_fields(mod, gold_payload):
    """Measured, not assumed — the reason cure_top_level is never handed gold."""
    present = [
        (code, field)
        for code, intel in mod.gold_pairs(gold_payload)
        if isinstance(intel, dict)
        for field, _ in mod.TOP_LEVEL_FIELDS
        if isinstance(intel.get(field), str) and intel[field]
    ]
    assert not present, f"gold unexpectedly carries top-level fields: {present[:5]}"


def test_the_fields_deliberately_left_alone_are_not_in_scope(mod):
    """status_mapping / _data_note / uraian must never enter either field list.

    Each has a live reason: status_mapping is the machine field TransitionBadge
    renders (curing it breaks the badge on 1,558 records); _data_note is evidence
    rendered verbatim and is pinned as an INNOCENCE case in
    kbli-internal-leak.test.ts; uraian is the official BPS Indonesian text.
    This test is the tripwire against a future "let's finish the sweep".
    """
    in_scope = {f for f, _ in mod.FIELDS} | {f for f, _ in mod.TOP_LEVEL_FIELDS}
    for forbidden in ("status_mapping", "_data_note", "uraian", "ruang_lingkup"):
        assert forbidden not in in_scope, f"{forbidden} must never be cured — see the comment on TOP_LEVEL_FIELDS"


def test_the_two_stored_copies_no_longer_contradict_each_other(mod, rules, canonical_records):
    """The client-visible symptom this lot exists for.

    `whatChanged` embeds `mapping_note` verbatim, but they are independent
    copies: L2.3 cured the embedded one and left the source Italian, so a page
    rendered an English block and an Italian crosswalk row about the same fact.
    After this cure, wherever the embedding relation holds, the cured
    `mapping_note` must still appear inside the cured `whatChanged`.
    """
    broken = []
    for rec in canonical_records:
        mn = rec.get("mapping_note")
        wc = (rec.get("intel_2026") or {}).get("whatChanged")
        if not isinstance(mn, str) or not mn or not isinstance(wc, str):
            continue
        cured_mn = mod.cure_text(mn, rules, Counter(), normalize_whitespace=True)
        cured_wc = mod.cure_text(wc, rules, Counter(), normalize_whitespace=True)
        # only assert on records where the embedding relation actually holds
        if mn.strip() and mn.strip() in wc and cured_mn and cured_mn not in cured_wc:
            broken.append(rec.get("kode_kbli_2025"))
    assert not broken, f"cured mapping_note no longer matches its embedded copy in whatChanged: {broken[:6]}"
