"""Guilt, innocence and freshness for gold_risk_dispute_relation.py.

The guards in this module were each grown from a REAL sentence that changed the
count when it was finally read (2026-08-07 session lesson: the number is not
the finding, the sentence is). Those sentences are pinned here verbatim so the
guard that excludes them cannot silently rot — and so a "better" regex that
re-convicts them fails loudly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gold_risk_dispute_relation import (  # noqa: E402
    ARTIFACT,
    CANONICAL,
    GOLD,
    bali_depends_on_tier,
    build_artifact,
    compute_disputes,
    gold_claims,
    load_canonical,
    load_gold,
    record_tiers,
    sentence_claims,
    universal_claims,
    _serialize,
)


def _record(code: str, tiers: list[str]) -> dict:
    return {
        "kode_kbli_2025": code,
        "per_skala": [{"kategori_risiko": t} for t in tiers],
    }


# ---------------------------------------------------------------------------
# sentence_claims — the entity is the sentence, not the substring
# ---------------------------------------------------------------------------


class TestSentenceClaims:
    def test_guilt_plain_assertion(self):
        s = "**All scales (Mikro/Kecil/Menengah/Besar)**: Low risk (Rendah)"
        assert sentence_claims(s, "82990") == {"Rendah"}

    def test_guilt_compound_never_double_counts_as_simple(self):
        s = "Single scale in PP 28/2025 data: Medium-High risk (Menengah Tinggi)"
        assert sentence_claims(s, "79110") == {"Menengah Tinggi"}

    def test_innocence_negation_46206_verbatim(self):
        # Gold DENIES the tier and thereby AGREES with the record. Convicting
        # this sentence was the first false positive the raw pattern produced.
        s = (
            "this is DIFFERENT from the other 46xxx agricultural wholesale codes "
            "in this session — Rendah/Otomatis does NOT apply here"
        )
        assert sentence_claims(s, "46206") == set()

    def test_innocence_hedged_forecast_60390_verbatim(self):
        # A prediction on a code whose same text says no assignment exists yet.
        s = (
            "Likely will be classified as High Risk when PP28 integration "
            "occurs, given content moderation obligations"
        )
        assert sentence_claims(s, "60390") == set()

    def test_innocence_other_codes_tier(self):
        # 70202's baliContext recommends a DIFFERENT code and states ITS tier.
        s = "you're better off with 70203 (Low risk, automatic licensing)"
        assert sentence_claims(s, "70202") == set()

    def test_own_code_in_sentence_still_claims(self):
        s = "register on oss.go.id, select 82990 — low risk at every scale"
        assert sentence_claims(s, "82990") == {"Rendah"}

    def test_innocence_population_talk(self):
        s = "most consulting codes are Low risk, but the qualifier pushes this up"
        assert sentence_claims(s, "70202") == set()

    # -- CONDITIONAL guard (2026-08-07 gate finding #4) --------------------

    def test_guilt_unconditional_assertion_still_convicts(self):
        # Paired with the innocence test below: same facts, no "if" branch —
        # proves the CONDITIONAL guard isn't over-matching plain assertions.
        s = "OSS treats your scope as High Risk, so you will need a Standard Certificate"
        assert sentence_claims(s, "12345") == {"Tinggi"}

    def test_innocence_conditional_if_clause_does_not_convict(self):
        # A hypothetical branch, not an assertion of this code's actual tier.
        s = "If OSS treats your scope as High Risk, you will need a Standard Certificate"
        assert sentence_claims(s, "12345") == set()

    def test_innocence_conditional_unless_clause_does_not_convict(self):
        s = "Unless OSS reclassifies this as High Risk, no Standard Certificate is required"
        assert sentence_claims(s, "12345") == set()

    def test_innocence_conditional_where_applicable_does_not_convict(self):
        s = "Sector permits apply for High Risk activities, where applicable"
        assert sentence_claims(s, "12345") == set()


# ---------------------------------------------------------------------------
# gold_claims — clause splitting (2026-08-07 gate finding #4): a guard fires
# on its OWN clause, never a sibling clause of the same sentence.
# ---------------------------------------------------------------------------


class TestClauseSplitting:
    def test_guilt_second_clause_convicts_past_a_semicolon(self):
        # "The automatic Low-Risk route does not apply; this activity is High
        # Risk." — one sentence, two clauses. The negation in clause 1 must
        # not reach clause 2's Tinggi assertion.
        entry = {
            "whatYouNeed": (
                "The automatic Low-Risk route does not apply; this activity "
                "is High Risk."
            )
        }
        assert gold_claims(entry, "12345") == {"Tinggi": ["whatYouNeed"]}

    def test_innocence_first_clause_negation_still_guards_its_own_clause(self):
        # Same sentence as above: Rendah must NOT survive — the negation
        # still guards the clause it actually sits in.
        entry = {
            "whatYouNeed": (
                "The automatic Low-Risk route does not apply; this activity "
                "is High Risk."
            )
        }
        assert "Rendah" not in gold_claims(entry, "12345")

    def test_guilt_em_dash_also_splits_clauses(self):
        entry = {
            "whatYouNeed": "Low-Risk does not apply here — this is High Risk instead."
        }
        assert gold_claims(entry, "12345") == {"Tinggi": ["whatYouNeed"]}


# ---------------------------------------------------------------------------
# compute_disputes — zero-overlap semantics
# ---------------------------------------------------------------------------


class TestDisputeSemantics:
    def test_guilt_zero_overlap_fires(self):
        canonical = [_record("99999", ["Tinggi"])]
        gold = {"99999": {"whatYouNeed": "Single-tier claim: Low risk (Rendah)."}}
        disputes = compute_disputes(canonical, gold)
        assert disputes["99999"]["record"] == ["Tinggi"]
        assert disputes["99999"]["kind"] == "zero_overlap"
        assert disputes["99999"]["editorial_mentions"] == {"Rendah": ["whatYouNeed"]}
        assert disputes["99999"]["baliDependsOnTier"] is False

    def test_innocence_partial_overlap_is_not_reported(self):
        # On a multi-tier record a partial overlap can be two truths about two
        # scopes — the no-arbiter zone. Deliberately NOT a dispute.
        canonical = [_record("99999", ["Tinggi", "Rendah"])]
        gold = {"99999": {"whatYouNeed": "Low risk (Rendah) for the basic scope."}}
        assert compute_disputes(canonical, gold) == {}

    def test_innocence_empty_record_is_a_gap_not_a_contradiction(self):
        canonical = [_record("99999", [])]
        gold = {"99999": {"whatYouNeed": "Low risk (Rendah)."}}
        assert compute_disputes(canonical, gold) == {}

    def test_innocence_gold_without_tier_talk(self):
        canonical = [_record("99999", ["Tinggi"])]
        gold = {"99999": {"whatYouNeed": "NIB via OSS, then sector permits."}}
        assert compute_disputes(canonical, gold) == {}

    def test_innocence_gold_code_missing_from_canonical(self):
        # Phantom-class: a gold entry with no canonical record is a different
        # disease with its own ledger — never a risk dispute.
        gold = {"99999": {"whatYouNeed": "Low risk (Rendah)."}}
        assert compute_disputes([], gold) == {}


# ---------------------------------------------------------------------------
# universal_claims / compute_disputes — the universal-quantifier rule
# (2026-08-07 gate finding #2): a "this code is X at every scale" claim is
# false on ANY other tier in the record, even when X itself also overlaps —
# the exact gap the zero-overlap rule leaves open.
# ---------------------------------------------------------------------------


class TestUniversalClaimDispute:
    def test_guilt_46100_all_scales_hides_other_tiers(self, real_disputes):
        # Gold: "All scales (Mikro/Kecil/Menengah/Besar): Low Risk (Rendah)".
        # Record holds four tiers, including Tinggi — the Rendah overlap is
        # exactly what let this slip past the zero-overlap rule.
        entry = real_disputes["46100"]
        assert entry["kind"] == "universal_claim"
        assert set(entry["record"]) == {
            "Menengah Rendah",
            "Menengah Tinggi",
            "Rendah",
            "Tinggi",
        }
        assert "Rendah" in entry["editorial_mentions"]

    def test_innocence_universal_claim_matching_the_records_only_tier(self):
        # X equals the record's ONLY tier — nothing else to contradict it.
        canonical = [_record("99999", ["Rendah"])]
        gold = {"99999": {"whatYouNeed": "All scales: Low risk (Rendah)."}}
        assert compute_disputes(canonical, gold) == {}

    def test_guilt_universal_claim_synthetic_multi_tier_record(self):
        canonical = [_record("99999", ["Rendah", "Tinggi"])]
        gold = {"99999": {"whatYouNeed": "All scales: Low risk (Rendah)."}}
        disputes = compute_disputes(canonical, gold)
        assert disputes["99999"]["kind"] == "universal_claim"

    def test_innocence_no_universal_quantifier_no_universal_claim(self):
        entry = {"whatYouNeed": "Low risk (Rendah) for this scope."}
        assert universal_claims(entry, "12345") == set()


# ---------------------------------------------------------------------------
# bali_depends_on_tier — 2026-08-07 gate finding #3: the Bali (L4) verdict on
# a disputed code can itself be derived FROM the disputed tier.
# ---------------------------------------------------------------------------


class TestBaliDependsOnTier:
    def test_guilt_tier_derived_status(self):
        record = {"l4_bali": {"status": "OK_or_HIGHER_RISK"}}
        assert bali_depends_on_tier(record) is True

    def test_guilt_all_four_tier_derived_statuses(self):
        for status in (
            "OK_or_HIGHER_RISK",
            "APERTO_BALI_RISCHIO_ALTO",
            "BLOCCATO_CLASSE_RISCHIO",
            "CHIUSO_MORATORIA_BALI",
        ):
            assert bali_depends_on_tier({"l4_bali": {"status": status}}) is True, status

    def test_innocence_pma_or_sector_derived_status(self):
        # These statuses hold regardless of which tier wins the dispute.
        for status in (
            "CHIUSO_PMA_NO_BESAR",
            "TERTUTUP",
            "CHIUSO_REGOLATORE_SETTORIALE",
        ):
            assert bali_depends_on_tier({"l4_bali": {"status": status}}) is False, status

    def test_innocence_missing_l4_bali(self):
        assert bali_depends_on_tier({}) is False

    def test_82990_is_tier_derived_in_the_real_catalogue(self):
        records = {r["kode_kbli_2025"]: r for r in load_canonical()}
        assert bali_depends_on_tier(records["82990"]) is True


# ---------------------------------------------------------------------------
# The real catalogue — pins on adjudicated members and non-members
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_disputes():
    return compute_disputes(load_canonical(), load_gold())


class TestRealCatalogue:
    def test_82990_is_a_dispute(self, real_disputes):
        # The page that motivated this module: panel says Tinggi, editorial
        # says low risk at every scale.
        entry = real_disputes["82990"]
        assert entry["record"] == ["Tinggi"]
        assert entry["kind"] == "zero_overlap"
        assert "Rendah" in entry["editorial_mentions"]

    def test_46206_negation_is_not_a_dispute(self, real_disputes):
        assert "46206" not in real_disputes

    def test_60390_hedged_forecast_is_not_a_dispute(self, real_disputes):
        assert "60390" not in real_disputes

    def test_record_side_never_empty(self, real_disputes):
        # The frontend renders the record tiers; an empty list would render
        # an empty disclosure.
        for code, entry in real_disputes.items():
            assert entry["record"], code
            assert entry["editorial_mentions"], code

    def test_47901_and_71109_are_also_universal_claim_disputes(self, real_disputes):
        # 47901: "All scales (Micro, Small, Medium, Large): Low risk (Rendah)"
        # on a record that also holds Tinggi. 71109: "All scales (Mikro
        # through Besar): Medium-High Risk" on a record that also holds
        # Tinggi. Both new members of the population added by the
        # universal-quantifier rule (2026-08-07 gate finding #2).
        assert real_disputes["47901"]["kind"] == "universal_claim"
        assert real_disputes["71109"]["kind"] == "universal_claim"

    def test_population_count(self, real_disputes):
        # Pinned so a future change to the guards is forced to explain a
        # membership shift here, not just in the artifact diff.
        assert len(real_disputes) == 33


# ---------------------------------------------------------------------------
# Artifact freshness — the arm that makes silence impossible
# ---------------------------------------------------------------------------


class TestArtifactFreshness:
    def test_emitted_artifact_matches_recomputation(self):
        # Any edit to gold or canonical that shifts the population goes red
        # here until --emit runs in the same change. This is the invariant the
        # module exists for: a NEW contradiction cannot reach the page without
        # its disclosure riding along.
        recomputed = _serialize(build_artifact(compute_disputes(load_canonical(), load_gold())))
        assert ARTIFACT.exists(), f"run gold_risk_dispute_relation.py --emit ({ARTIFACT})"
        assert ARTIFACT.read_text() == recomputed, (
            "kbli-risk-disputes.json is stale — re-run "
            "scripts/kbli_filiera/gold_risk_dispute_relation.py --emit and "
            "commit it with the data change"
        )

    def test_artifact_never_renders_editorial_tiers_note(self):
        # The consumer contract lives in _meta so a future reader meets it
        # before the data.
        meta = json.loads(ARTIFACT.read_text())["_meta"]
        assert "never render it" in meta["note"]

    def test_sources_exist(self):
        assert CANONICAL.exists() and GOLD.exists()
