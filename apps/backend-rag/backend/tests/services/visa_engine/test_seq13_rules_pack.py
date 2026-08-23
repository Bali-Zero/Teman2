"""E5 increment 6 — gates for the RULES-ONLY half of seq-13
(``rulepack-prod-013.rules-only.json``, see
``backend.scripts.visa_engine.fold_pack_seq13_rules``).

This module SKIPS cleanly (not error, not red) while
``rulepack-prod-013.rules-only.json`` does not exist on disk — the
combining fold that folds this half together with the source-freshness
half has not run yet. Once the rules-only fold has run and the file
exists, these checks run, each verified against the real files on disk or
the real evaluator:

(a) chain gate — the rules-only payload's ``previous_payload_sha256``
    (still seq-12's own value, since this fold declares no identity
    change — see the fold's module docstring) equals the RECOMPUTED
    SHA256(JCS(...)) of seq-12's own signed payload declaration, cross-
    checked against a fresh re-hash of the seq-12 SOURCE bytes.
(b) rule-set delta — mechanically diffed against seq-12, TWICE: once
    data-driven (derived from ``cure-seq13-rule-tightenings.json`` via the
    fold's own ``_edited_rule_ids``/``_inserted_rule_ids`` helpers, so it
    covers whatever fixes the cure file declares without editing this
    test), once as a named pin of the four specific fixes this session
    graded — never eyeballed either way.
(c) zero lint findings — ``lint_duplicate_subtree`` /
    ``lint_unsatisfiable_condition`` run over every seq-13 rule (house
    pattern, ``test_seq10_pack.py``).
(d) ``compile_pack`` compiles the rules-only payload with zero errors.
(e) idempotence — calling ``assemble_payload()`` twice yields
    canonical-JSON-identical output.
(f) evaluator witnesses (house pattern ``test_seq10_pack.py``'s
    ``TestE31CMarriageGateWitnesses`` — per-product ``evaluate_product``,
    never the aggregated Decision): E31C nationality-leg
    guilt/pinned-seq12-defect/innocence/tri-state/non-contamination, the
    identical five-part pattern for D12's ``pt_pma_committed`` conjunct
    PLUS the team-lead's own mutation claim reproduced independently (all 7
    D12 rules resolve FALSE for a ``pt_pma_committed=True`` applicant), and
    the sponsor-status value check across all 4 products (E31B/E31E/E31H/
    E31J): guilt + pinned-seq12-defect per product (4 each), innocence per
    product PER valid status value (12 — the stricter standard the
    team-lead named for a 9-rule tightening), and tri-state per product.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine.compile_claims import (
    lint_duplicate_subtree,
    lint_unsatisfiable_condition,
)
from backend.scripts.visa_engine.compile_pack import (
    compile_rule_pack,
    load_rule_pack_payload,
    wrap_as_unsigned_pack,
)
from backend.scripts.visa_engine.fold_pack_seq13_rules import (
    FoldPackError,
    assemble_payload,
)
from backend.services.visa_engine import compiler, evaluator
from backend.services.visa_engine.bundle import canonicalize_json
from backend.services.visa_engine.enums import FactPath
from backend.services.visa_engine.evaluator import ProductProof, ProductProofStatus
from backend.services.visa_engine.fact_registry import DEFAULT_FACT_REGISTRY
from backend.tests.services.visa_engine import _gold_fixtures as gf

_REPO_ROOT = Path(__file__).resolve().parents[6]
_PACKS_DIR = (
    _REPO_ROOT
    / "apps"
    / "backend-rag"
    / "backend"
    / "services"
    / "visa_engine"
    / "contracts"
    / "packs"
)
_SEQ12_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-012.source.json"
_SEQ12_SIGNED_PATH = _PACKS_DIR / "rulepack-prod-012.signed.json"
_SEQ13_RULES_ONLY_PATH = _PACKS_DIR / "rulepack-prod-013.rules-only.json"

_INSERTED_RULE_ID = "hf.e31c-sponsor-not-indonesian"
_EDITED_E31C_RULE_ID = "el.e31c-child-mixed-marriage-support"
_EDITED_D12_RULE_ID = "el.d12-multi-entry-support"
_ALL_D12_RULE_IDS = (
    "el.d12-multi-entry-support",
    "el.d12-passport-validity",
    "el.d12-funds-usd-5000",
    "el.d12-cv-required",
    "el.d12-itinerary-required",
    "el.d12-support-letter",
    "hf.d12-onshore-conversion-excluded",
)

# Any instant on/after the inserted rule's valid_period.from
# (2026-08-23T00:00:00Z) and inside every inherited rule's window.
AT = datetime(2026, 8, 23, 12, 0, 0, tzinfo=timezone.utc)

pytestmark = pytest.mark.skipif(
    not _SEQ13_RULES_ONLY_PATH.exists(),
    reason=(
        "rulepack-prod-013.rules-only.json does not exist yet — run "
        "`PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq13_rules` "
        "first. This module SKIPS, not reds, until then."
    ),
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


@pytest.fixture(scope="module")
def seq12_source() -> dict[str, Any]:
    return _read_json(_SEQ12_SOURCE_PATH)


@pytest.fixture(scope="module")
def seq13_rules_only() -> dict[str, Any]:
    return _read_json(_SEQ13_RULES_ONLY_PATH)


def _compiled(name: str) -> compiler.CompiledRulePack:
    payload = load_rule_pack_payload(_PACKS_DIR / name)
    return compiler.build_compiled_pack(
        wrap_as_unsigned_pack(payload), fact_registry=DEFAULT_FACT_REGISTRY
    )


@pytest.fixture(scope="module")
def seq13(seq13_rules_only: dict[str, Any]) -> compiler.CompiledRulePack:
    del seq13_rules_only  # ensures the skip guard has already run
    return _compiled("rulepack-prod-013.rules-only.json")


@pytest.fixture(scope="module")
def seq12() -> compiler.CompiledRulePack:
    return _compiled("rulepack-prod-012.source.json")


def _known(value: Any) -> dict[str, Any]:
    return {"status": "KNOWN", "value": value}


def _proof(
    compiled: compiler.CompiledRulePack, product_code: str, overrides: dict[str, Any]
) -> ProductProof:
    facts = gf.applicant_facts(overrides=overrides)
    snapshot = DEFAULT_FACT_REGISTRY.derive(facts, effective_at=AT)
    product = next(p for p in compiled.products if p.product_code == product_code)
    rules = compiled.rules_for(product, effective_at=AT)
    purposes = frozenset(snapshot.values[FactPath.INTENT_PURPOSES].value)
    return evaluator.evaluate_product(
        product=product,
        rules=rules,
        facts=snapshot,
        purposes=purposes,
        fact_registry=DEFAULT_FACT_REGISTRY,
    )


def _reason_codes(proof: ProductProof) -> set[str]:
    return {r.code for r in proof.reasons}


# ---------------------------------------------------------------------------
# (a) chain gate
# ---------------------------------------------------------------------------


class TestChainGate:
    def test_previous_payload_sha256_chains_to_recomputed_seq12(
        self, seq12_source: dict[str, Any], seq13_rules_only: dict[str, Any]
    ) -> None:
        recomputed = hashlib.sha256(canonicalize_json(seq12_source)).hexdigest()
        seq12_signed = _read_json(_SEQ12_SIGNED_PATH)
        assert seq12_signed["payload_sha256"] == recomputed
        # The rules-only fold declares no identity change (module docstring
        # of fold_pack_seq13_rules.py: the combining fold owns identity) —
        # `previous_payload_sha256` still carries seq-12's own value.
        assert seq13_rules_only["previous_payload_sha256"] == seq12_source["previous_payload_sha256"]

    def test_sequence_and_rule_pack_id_unchanged_by_this_fold(
        self, seq12_source: dict[str, Any], seq13_rules_only: dict[str, Any]
    ) -> None:
        assert seq13_rules_only["sequence"] == seq12_source["sequence"] == 12
        assert seq13_rules_only["rule_pack_id"] == seq12_source["rule_pack_id"]


# ---------------------------------------------------------------------------
# (b) rule-set delta — mechanical, never eyeballed
# ---------------------------------------------------------------------------


class TestRuleSetDelta:
    def test_delta_matches_exactly_what_the_cure_file_declares(
        self, seq12_source: dict[str, Any], seq13_rules_only: dict[str, Any]
    ) -> None:
        """Data-driven, not hardcoded: the expected added/changed sets are
        derived from ``cure-seq13-rule-tightenings.json`` via the SAME
        ``_edited_rule_ids``/``_inserted_rule_ids`` helpers the fold itself
        uses for its own ``_assert_untouched`` guard — so a fix added as
        cure/manifest data (never as code) is automatically covered here
        too, and an accidental Nth change nobody declared fails this test
        exactly the way it fails the fold."""
        from backend.scripts.visa_engine.fold_pack_seq13_rules import (
            _CURE_FILE,
            _edited_rule_ids,
            _inserted_rule_ids,
        )

        cure = _read_json(_CURE_FILE)
        expected_added = set(_inserted_rule_ids(cure))
        expected_changed = set(_edited_rule_ids(cure))
        assert expected_added.isdisjoint(expected_changed), (
            "a rule_id declared as both an insertion and an edit — cure file is malformed"
        )

        r12 = {r["rule_id"]: r for r in seq12_source["rules"]}
        r13 = {r["rule_id"]: r for r in seq13_rules_only["rules"]}

        added = set(r13) - set(r12)
        removed = set(r12) - set(r13)
        changed = {rid for rid in (set(r12) & set(r13)) if _canon(r12[rid]) != _canon(r13[rid])}

        assert added == expected_added
        assert removed == set()
        assert changed == expected_changed
        assert len(r13) == len(r12) + len(expected_added)

    #: The 9 sponsor-status-check rule_ids that would change under FIX 4
    #: (family.sponsor_status_code op:known -> op:in). FIX 4 is HELD as of
    #: 2026-08-23 (team-lead: the closed 3-value enum may have no slot for
    #: a lawfully-pending ITAS renewal, Pasal 116/180 — see
    #: HELD-fix4-sponsor-status-2026-08-23.json for the full disclosure and
    #: the three open questions gating re-arming). This fold contains
    #: THREE fixes, not four, until that hold lifts.
    _HELD_FIX4_RULE_IDS = frozenset(
        {
            "el.e31b-spouse-itas-support",
            "el.e31b-sponsor-itas-itap",
            "el.e31e-child-itas-support",
            "el.e31e-sponsor-itas-itap",
            "el.e31h-parent-itas-child-support",
            "el.e31h-sponsor-itas-itap",
            "el.e31j-sibling-itas-support",
            "el.e31j-sponsor-itas-itap",
            "el.e31j-dependency-age",
        }
    )

    def test_the_three_fixes_this_session_shipped_are_present(
        self, seq12_source: dict[str, Any], seq13_rules_only: dict[str, Any]
    ) -> None:
        """Named-fix pin, complementary to the data-driven test above (which
        would pass even if every fix were replaced by a different one) —
        this one pins the SPECIFIC rule_ids the team-lead's mandate named,
        so a fix silently vanishing from the cure file still fails loud.

        Renamed from `..._four_fixes_..._present` on 2026-08-23: this fold
        ships THREE fixes (E31C nationality leg, D12 conjunct removal, and
        nothing else) — FIX 4 (sponsor-status value check) is HELD, not
        shipped, pending team-lead's independent read (see
        `_HELD_FIX4_RULE_IDS`'s docstring). The old name and its 4-fix
        assertion were themselves the bug this test exists to catch: the
        artifact contained FIX 4's 9 rule_ids and 45/45 tests were green
        against it, because this test's own expected set still included
        them. A green test suite that asserts the wrong thing is exactly
        as blind as no test at all.

        FIX 3 was REVERSED 2026-08-23 (see TestD12ConjunctRemovedWitnesses'
        header comment): `_EDITED_D12_RULE_ID`
        (`el.d12-multi-entry-support`) is no longer one of the changed
        rule_ids — it was never touched in either direction after the
        correction. The 5 siblings that actually changed (conjunct
        REMOVED) replace it here."""
        r12 = {r["rule_id"]: r for r in seq12_source["rules"]}
        r13 = {r["rule_id"]: r for r in seq13_rules_only["rules"]}
        changed = {rid for rid in (set(r12) & set(r13)) if _canon(r12[rid]) != _canon(r13[rid])}
        added = set(r13) - set(r12)

        assert _EDITED_D12_RULE_ID not in changed, (
            "el.d12-multi-entry-support must stay untouched post-reversal"
        )
        assert added == {_INSERTED_RULE_ID}
        assert changed == {
            _EDITED_E31C_RULE_ID,
            "el.d12-passport-validity",
            "el.d12-funds-usd-5000",
            "el.d12-cv-required",
            "el.d12-itinerary-required",
            "el.d12-support-letter",
        }

        # The guard that would have caught the artifact/message mismatch by
        # itself: none of FIX 4's 9 rule_ids may appear in `changed` while
        # the hold stands, and every one of them must be BYTE-IDENTICAL to
        # seq-12 -- not merely "not in the changed set" (which `changed` at
        # the line above already implies), but independently re-diffed here
        # so this assertion still fails loud even if `changed`'s
        # computation itself were ever wrong.
        assert self._HELD_FIX4_RULE_IDS.isdisjoint(changed), (
            "FIX 4 is HELD — none of its 9 rule_ids may differ from seq-12"
        )
        for rid in self._HELD_FIX4_RULE_IDS:
            assert rid in r12 and rid in r13, rid
            assert _canon(r12[rid]) == _canon(r13[rid]), (
                f"{rid} must be byte-identical to seq-12 while FIX 4 is held"
            )

    def test_products_and_source_records_are_byte_identical(
        self, seq12_source: dict[str, Any], seq13_rules_only: dict[str, Any]
    ) -> None:
        assert _canon(seq13_rules_only["products"]) == _canon(seq12_source["products"])
        assert _canon(seq13_rules_only["source_records"]) == _canon(seq12_source["source_records"])

    def test_no_other_top_level_key_drifted(
        self, seq12_source: dict[str, Any], seq13_rules_only: dict[str, Any]
    ) -> None:
        identity_keys = {
            "sequence",
            "version",
            "rule_pack_id",
            "previous_payload_sha256",
            "created_at",
            "created_by",
        }
        for key in set(seq12_source) | set(seq13_rules_only):
            if key in identity_keys or key == "rules":
                continue
            assert _canon(seq13_rules_only.get(key)) == _canon(seq12_source.get(key)), key


# ---------------------------------------------------------------------------
# (c) zero lint findings over every seq-13 rule
# ---------------------------------------------------------------------------


class TestZeroLintFindings:
    def test_duplicate_subtree_and_unsatisfiable_condition_are_clean(
        self, seq13_rules_only: dict[str, Any]
    ) -> None:
        findings = []
        for rule in seq13_rules_only["rules"]:
            when = rule["when"]
            findings.extend(lint_duplicate_subtree(rule_id=rule["rule_id"], when=when))
            unsat_findings, _skip_note = lint_unsatisfiable_condition(
                rule_id=rule["rule_id"], when=when
            )
            findings.extend(unsat_findings)
        assert findings == []


# ---------------------------------------------------------------------------
# (d) compile_pack RC 0
# ---------------------------------------------------------------------------


class TestCompilePackCompilesClean:
    def test_compile_rule_pack_reports_zero_errors(self) -> None:
        payload = load_rule_pack_payload(_SEQ13_RULES_ONLY_PATH)
        report = compile_rule_pack(wrap_as_unsigned_pack(payload))
        assert report.ok, "; ".join(f"{e.code}: {e.message}" for e in report.errors)


# ---------------------------------------------------------------------------
# (e) idempotence
# ---------------------------------------------------------------------------


class TestFoldIsIdempotent:
    def test_assemble_payload_twice_is_byte_identical(self) -> None:
        first = assemble_payload()
        second = assemble_payload()
        assert _canon(first) == _canon(second)


# ---------------------------------------------------------------------------
# (f) evaluator witnesses — E31C nationality leg (Fix 1)
# ---------------------------------------------------------------------------

_E31C_BASE = {
    "intent.purposes": _known(["FAMILY"]),
    "family.relation_to_sponsor": _known("PARENT"),
    "family.marriage_registered": _known(True),
}


class TestE31CNationalityGateWitnesses:
    def test_guilt_two_foreign_parents_is_excluded(
        self, seq13: compiler.CompiledRulePack
    ) -> None:
        """The exact defect SKILL.md's 2026-08-23 LIVE STATE entry proved
        live: FAMILY + PARENT + marriage registered + sponsor
        nationalities NOT including ID (two foreign parents) — before this
        fix, `el.e31c-child-mixed-marriage-support` alone carried this to
        SUPPORTED."""
        proof = _proof(
            seq13,
            "E31C",
            {**_E31C_BASE, "family.sponsor_nationalities": _known(["US"])},
        )
        assert proof.status is ProductProofStatus.EXCLUDED
        assert "REQ_PARENT_SPONSOR_INDONESIAN" in _reason_codes(proof)

    def test_pinned_seq12_defect_same_facts_reached_supported(
        self, seq12: compiler.CompiledRulePack
    ) -> None:
        """Pinned so the fix is measurable — if this ever starts failing,
        seq-12's bytes changed. Reproduces SKILL.md's own positive control:
        FAMILY intent + PARENT relation + marriage registered + US
        sponsor_nationalities -> SUPPORTED via
        `el.e31c-child-mixed-marriage-support` alone on seq-12."""
        proof = _proof(
            seq12,
            "E31C",
            {**_E31C_BASE, "family.sponsor_nationalities": _known(["US"])},
        )
        assert proof.status is ProductProofStatus.SUPPORTED
        assert {r.rule_id for r in proof.support_rules} == {_EDITED_E31C_RULE_ID}

    def test_innocence_indonesian_sponsor_parent_is_supported(
        self, seq13: compiler.CompiledRulePack
    ) -> None:
        """The legitimate applicant E31C actually serves: an Indonesian
        sponsor parent, marriage registered. Must still reach SUPPORTED,
        unchanged, via BOTH SUPPORT rules independently."""
        proof = _proof(
            seq13,
            "E31C",
            {**_E31C_BASE, "family.sponsor_nationalities": _known(["ID"])},
        )
        assert proof.status is ProductProofStatus.SUPPORTED
        support_ids = {r.rule_id for r in proof.support_rules}
        assert _EDITED_E31C_RULE_ID in support_ids
        assert "el.e31c-mixed-marriage-parents" in support_ids

    def test_tristate_unknown_nationality_blocks_never_excludes(
        self, seq13: compiler.CompiledRulePack
    ) -> None:
        proof = _proof(
            seq13,
            "E31C",
            {**_E31C_BASE, "family.sponsor_nationalities": gf.unknown("NOT_ASKED")},
        )
        assert proof.status is ProductProofStatus.BLOCKED_UNKNOWN
        assert proof.status is not ProductProofStatus.EXCLUDED

    def test_non_family_applicant_is_not_contaminated(
        self, seq12: compiler.CompiledRulePack, seq13: compiler.CompiledRulePack
    ) -> None:
        """Same scoping discipline as hf.e31c-marriage-not-registered
        (seq-10, Codex refuter finding 1): the new HARD_FILTER must be
        strong-Kleene FALSE (silent) outside the FAMILY+PARENT shape, never
        BLOCKED_UNKNOWN for an unrelated applicant whose nationality
        happens to be unasked."""
        overrides = {
            "intent.purposes": _known(["STUDY"]),
            "family.relation_to_sponsor": _known("OTHER"),
            "family.sponsor_nationalities": gf.unknown("NOT_ASKED"),
        }
        for pack in (seq12, seq13):
            proof = _proof(pack, "E31C", overrides)
            assert proof.status is ProductProofStatus.UNSUPPORTED
            assert FactPath.FAMILY_SPONSOR_NATIONALITIES not in proof.missing_facts


# ---------------------------------------------------------------------------
# (f) evaluator witnesses -- D12 pt_pma_committed conjunct REMOVED (Fix 3,
#     REVERSED 2026-08-23). Original direction of this fold ADDED the
#     conjunct to el.d12-multi-entry-support; team-lead + v2-d12's handoff
#     (d12-removal-handoff.md) established the owner ruling excludes on
#     ACTIVE STAY PERMIT, not committed capital, and that D12's 5 siblings
#     carried an ungrounded conjunct no claim ever backed (D1/D2 -- the same
#     "docs rule" family from the same authoring pass -- carry it on ZERO of
#     their 12 combined rules). The correction strips the conjunct from the
#     5 siblings; el.d12-multi-entry-support was never touched in either
#     direction. This class replaces the pre-reversal
#     TestD12PtPmaCommittedGateWitnesses, whose own mutation proof encoded
#     the WRONG direction as a passing test -- team-lead's own words apply:
#     "a mutation proof licenses the mechanism, never the correctness."
# ---------------------------------------------------------------------------

_D12_BASE = {
    "intent.purposes": _known(["INVESTMENT"]),
    "intent.stay_days": _known(90),
}

_D12_ELIGIBILITY_SUPPORT_RULE_IDS = {
    "el.d12-multi-entry-support",
    "el.d12-passport-validity",
    "el.d12-funds-usd-5000",
    "el.d12-cv-required",
    "el.d12-itinerary-required",
    "el.d12-support-letter",
}


class TestD12ConjunctRemovedWitnesses:
    def test_pinned_seq12_defect_checklist_incomplete_for_committed_investor(
        self, seq12: compiler.CompiledRulePack
    ) -> None:
        """UNCHANGED behavior, asserted against the untouched seq-12 pack --
        this documents the actual defect the reversal fixes. A PMA-committed
        applicant already reaches SUPPORTED on seq-12 via
        el.d12-multi-entry-support ALONE (union coverage: that rule never
        gated on pt_pma_committed), while the 5 document-requirement
        siblings sit silent because THEY carried the wrong gate -- so the
        applicant was told they qualify for D12 with zero attached document
        requirements (no passport-validity, funds, CV, itinerary, or
        support-letter reason code)."""
        proof = _proof(
            seq12,
            "D12",
            {**_D12_BASE, "investment.pt_pma_committed": _known(True)},
        )
        assert proof.status is ProductProofStatus.SUPPORTED
        assert {r.rule_id for r in proof.support_rules} == {_EDITED_D12_RULE_ID}

    def test_fix_committed_investor_now_gets_the_full_checklist(
        self, seq13: compiler.CompiledRulePack
    ) -> None:
        """The reversal's actual, and only, effect: the SAME applicant, the
        SAME status (SUPPORTED -- per the handoff's key mechanism finding,
        this fix changes ZERO eligibility outcomes for anyone), but now via
        ALL 6 D12 ELIGIBILITY rules instead of 1, because none of them gate
        on pt_pma_committed any more. This is a checklist-completeness fix,
        not an inclusion/exclusion fix."""
        proof = _proof(
            seq13,
            "D12",
            {**_D12_BASE, "investment.pt_pma_committed": _known(True)},
        )
        assert proof.status is ProductProofStatus.SUPPORTED
        assert {r.rule_id for r in proof.support_rules} == _D12_ELIGIBILITY_SUPPORT_RULE_IDS

    def test_innocence_uncommitted_investor_is_still_supported(
        self, seq13: compiler.CompiledRulePack
    ) -> None:
        """The legitimate applicant D12 actually serves: a pre-investment
        visitor who has NOT yet committed PT PMA capital. Must still reach
        SUPPORTED, unchanged, via every one of the 6 ELIGIBILITY rules --
        this was already true before the reversal and stays true after,
        since this applicant never tripped the removed conjunct either
        way."""
        proof = _proof(
            seq13,
            "D12",
            {**_D12_BASE, "investment.pt_pma_committed": _known(False)},
        )
        assert proof.status is ProductProofStatus.SUPPORTED
        assert {r.rule_id for r in proof.support_rules} == _D12_ELIGIBILITY_SUPPORT_RULE_IDS

    def test_unknown_commitment_no_longer_gates_d12_at_all(
        self, seq13: compiler.CompiledRulePack
    ) -> None:
        """Direct, worth-pinning consequence of the reversal: since no D12
        ELIGIBILITY rule references investment.pt_pma_committed any more,
        an applicant who was never asked (UNKNOWN) is fully SUPPORTED via
        all 6 rules -- the tri-state BLOCKED_UNKNOWN gate this fact used to
        impose on D12 is GONE, not merely relaxed. This is the doctrinally
        correct outcome per D12.md Sec.3.15 ("no capital-commitment fact
        gates it") and is pinned here so a future regression that
        re-introduces the conjunct on any D12 rule is caught immediately."""
        proof = _proof(
            seq13,
            "D12",
            {**_D12_BASE, "investment.pt_pma_committed": gf.unknown("NOT_ASKED")},
        )
        assert proof.status is ProductProofStatus.SUPPORTED
        assert {r.rule_id for r in proof.support_rules} == _D12_ELIGIBILITY_SUPPORT_RULE_IDS

    def test_non_investment_applicant_is_not_contaminated(
        self, seq12: compiler.CompiledRulePack, seq13: compiler.CompiledRulePack
    ) -> None:
        overrides = {
            "intent.purposes": _known(["TOURISM"]),
            "investment.pt_pma_committed": gf.unknown("NOT_ASKED"),
        }
        for pack in (seq12, seq13):
            proof = _proof(pack, "D12", overrides)
            assert proof.status is ProductProofStatus.UNSUPPORTED
            assert FactPath.INVESTMENT_PT_PMA_COMMITTED not in proof.missing_facts

    def test_mechanism_proof_all_six_eligibility_rules_now_fire_true(
        self, seq13: compiler.CompiledRulePack
    ) -> None:
        """Correct-direction replacement for the pre-reversal (wrong-
        direction) mutation proof. Independently reproduces
        d12-removal-handoff.md Sec.5's mechanism finding via the trace sink:
        for a PMA-committed applicant, all 6 D12 ELIGIBILITY rules evaluate
        strong-Kleene TRUE and fire their SUPPORT effect -- not merely that
        the product proof is SUPPORTED (which the union-coverage 6th rule
        alone would already produce), but that the 5 siblings specifically
        are no longer gated out. hf.d12-onshore-conversion-excluded (the
        7th D12-scoped rule, an unrelated HARD_FILTER) is excluded from the
        firing assertion on purpose -- it was never part of this fix."""
        facts = gf.applicant_facts(
            overrides={**_D12_BASE, "investment.pt_pma_committed": _known(True)}
        )
        snapshot = DEFAULT_FACT_REGISTRY.derive(facts, effective_at=AT)
        product = next(p for p in seq13.products if p.product_code == "D12")
        rules = seq13.rules_for(product, effective_at=AT)
        d12_scoped_rules = {r for r in rules if r.rule_id in _ALL_D12_RULE_IDS}
        assert {r.rule_id for r in d12_scoped_rules} == set(_ALL_D12_RULE_IDS)

        from backend.services.visa_engine.enums import TruthValue

        trace: list[Any] = []
        proof = evaluator.evaluate_product(
            product=product,
            rules=rules,
            facts=snapshot,
            purposes=frozenset(snapshot.values[FactPath.INTENT_PURPOSES].value),
            fact_registry=DEFAULT_FACT_REGISTRY,
            _trace_sink=trace,
        )
        assert proof.status is ProductProofStatus.SUPPORTED
        assert {r.rule_id for r in proof.support_rules} == _D12_ELIGIBILITY_SUPPORT_RULE_IDS

        d12_trace_entries = [
            t for t in trace if t.rule.rule_id in _D12_ELIGIBILITY_SUPPORT_RULE_IDS
        ]
        assert {t.rule.rule_id for t in d12_trace_entries} == _D12_ELIGIBILITY_SUPPORT_RULE_IDS
        for entry in d12_trace_entries:
            assert entry.result.truth is TruthValue.TRUE, entry.rule.rule_id
            assert entry.applied_effect is not None, entry.rule.rule_id


# ---------------------------------------------------------------------------
# Fold-level fail-loud checks (ledger drift, chain mismatch)
# ---------------------------------------------------------------------------


class TestFoldFailsLoudOnDrift:
    def test_wrong_expected_seq12_hash_aborts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import backend.scripts.visa_engine.fold_pack_seq13_rules as mod

        monkeypatch.setattr(mod, "_EXPECTED_SEQ12_PAYLOAD_SHA256", "0" * 64)
        with pytest.raises(FoldPackError, match="not the one this fold was authored against"):
            mod.assemble_payload()
