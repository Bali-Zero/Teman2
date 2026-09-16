"""Gates for seq-22 (``fold_pack_seq22.py``): the E23V cure, folded onto the
REAL signed seq-20 and carrying no HARD_FILTER that reads a synthesised fact.

Ground: ``fold_pack_seq22.py``'s own docstring — what the three seq-21
defects were, which two are cured here, which one is DELETED rather than
reshaped, and the measurement behind each call.

Unlike seq-21's own gates, nothing here is synthetic. The anchor is the
production ``rulepack-prod-020.signed.json`` on disk, verified against the
pinned production public key (a PUBLIC key — never a secret), exactly as
``fold_pack_seq22.py`` verifies it when an operator runs it. If either
on-disk artifact is missing these tests FAIL; they never skip, because a
green suite that ran no witness is the shape cicatrix #2 is named after.

Every behavioural witness is stated TWICE — guilt (the defect is present and
refused) and innocence (the legitimate outcome the same guard still allows).
The two that matter most:

``test_guilt_reinserting_e23v_aborts_the_fold`` puts E23V back into
``EMPLOYMENT_SPONSOR_PRODUCT_CODES`` — seq-21's first defect — and proves the
fold refuses rather than silently reproducing it.

``test_guilt_a_hard_filter_on_a_twin_basis_fact_aborts_the_fold`` puts
seq-21's third defect back — an EXCLUDE reading
``secondhome.bank_deposit_usd`` — and proves the fold refuses. That defect
broke E33, the Second Home product that works and sells today, on a deposit
figure the interview never asked for.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine.compile_pack import wrap_as_unsigned_pack
from backend.scripts.visa_engine.fold_pack_seq22 import (
    CURED_PRODUCT_CODE,
    DELETED_SEQ21_RULE_ID,
    EMPLOYMENT_SPONSOR_PRODUCT_CODES,
    EMPLOYMENT_SPONSOR_RULE_ID,
    NEW_RULE_IDS,
    RETIRED_REVIEW_RULES,
    SEQ20_PAYLOAD_SHA256,
    SUPPORT_RULE_IDS,
    SYNTHESISED_TWIN_BASIS_FACTS,
    _assert_e23v_stays_cured,
    _rule_pack_id,
    _rules_by_id,
    assert_no_hard_filter_reads_a_synthesised_twin_basis_fact,
    fold,
)
from backend.scripts.visa_engine.gold_replay_driver import (
    _offline_identity_provider,
    build_persona_request,
)
from backend.services.visa_engine import compiler, evaluate_path, evaluator
from backend.services.visa_engine.bundle import canonicalize_json
from backend.services.visa_engine.compiler import DEFAULT_FACT_REGISTRY
from backend.services.visa_engine.models import DecisionState, RulePackPayload
from backend.tests.services.visa_engine.gold_replay import _decision_actual
from backend.tests.services.visa_engine.test_evaluator_gold import Persona

_PACKS_DIR = (
    Path(__file__).resolve().parents[3] / "services" / "visa_engine" / "contracts" / "packs"
)
_SEQ20_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-020.source.json"
_SEQ20_SIGNED_PATH = _PACKS_DIR / "rulepack-prod-020.signed.json"
_SEQ22_SOURCE_PATH = _PACKS_DIR / "rulepack-prod-022.source.json"
_CORPUS_DIR = Path(__file__).resolve().parent / "gold_coverage" / "fixtures" / "walks"
_E23V_DEFECT_WALK_PATH = (
    _CORPUS_DIR / "offshore_work_sponsor_government_trade_office_only_employer_no.json"
)
_SECOND_HOME_PROPERTY_WALK_PATH = _CORPUS_DIR / "offshore_second_home_property.json"

#: The pinned production Ed25519 PUBLIC key — the same constant
#: ``test_seq20_signed_bundle.py`` verifies seq-20 with. A public key is not a
#: secret; it is what makes the anchor check real instead of a digest compare.
PROD_TRUST_STORE_JSON = json.dumps(
    [
        {
            "kid": "prod-2026-07-1",
            "public_key": "gZoo1nzMsRpwWgw4HCzV_2YYxU0Vbt5FMfLWeOzAchA",
            "environment": "PRODUCTION",
            "valid_from": "2026-07-19T00:00:00Z",
            "valid_to": None,
            "revoked_at": None,
        }
    ]
)

#: Shortly after seq-20's own ``signed_at`` — fixed, never ``datetime.now()``,
#: so this file never rots into a time-dependent red.
OBSERVED_AT = datetime(2026, 9, 16, 0, 30, 0, tzinfo=timezone.utc)

#: The nine products seq-21 unlocked and seq-22 carries forward.
UNLOCKED_PRODUCT_CODES = (
    "E23U",
    "E23V",
    "E28B",
    "E28C",
    "E28D",
    "E28F",
    "E33A",
    "E33B",
    "E33C",
)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AssertionError(
            f"{path.name} does not exist on disk. This must FAIL, not skip: a "
            "witness that never ran proves nothing (cicatrix #2)."
        )
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def seq20_source() -> dict[str, Any]:
    return _read_json(_SEQ20_SOURCE_PATH)


@pytest.fixture(scope="module")
def seq20_signed() -> dict[str, Any]:
    return _read_json(_SEQ20_SIGNED_PATH)


@pytest.fixture
def prod_trust_store_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", PROD_TRUST_STORE_JSON)


@pytest.fixture
def seq22_source(
    seq20_source: dict[str, Any],
    seq20_signed: dict[str, Any],
    prod_trust_store_env: None,
) -> dict[str, Any]:
    return fold(seq20_source, seq20_signed, observed_at=OBSERVED_AT)


def _compiled(payload_dict: dict[str, Any]) -> compiler.CompiledRulePack:
    payload = RulePackPayload.model_validate(payload_dict)
    return compiler.build_compiled_pack(
        wrap_as_unsigned_pack(payload), fact_registry=DEFAULT_FACT_REGISTRY
    )


@pytest.fixture
def seq22_compiled(seq22_source: dict[str, Any]) -> compiler.CompiledRulePack:
    return _compiled(seq22_source)


def _decide(
    pack: compiler.CompiledRulePack, overrides: dict[str, Any], label: str
) -> dict[str, Any]:
    """The applicant-facing outcome: compile -> evaluate ->
    ``apply_public_policy_adapters``, the same path ``gold_coverage_eval``
    walks — mirrors ``test_seq21_pack.py``'s own ``_decide`` exactly, so the
    two files cannot silently diverge on what "evaluate" means."""
    persona = Persona(
        id=0, label=label, overrides=overrides, expected_state=DecisionState.NEEDS_INPUT
    )
    request = build_persona_request(persona)
    facts = request.applicant_facts()
    decision = evaluator.evaluate(
        facts,
        pack,
        effective_at=OBSERVED_AT,
        observed_at=OBSERVED_AT,
        identity_provider=_offline_identity_provider,
    )
    decision = evaluate_path.apply_public_policy_adapters(
        decision, facts, pack, disclosed_review_flags=request.effective_review_flags()
    )
    return _decision_actual(decision)


def _product_versions(payload: dict[str, Any]) -> dict[str, str]:
    return {p["product_code"]: p["product_version_id"] for p in payload["products"]}


# ---------------------------------------------------------------------------
# Fold integrity — the anchor, the chain, the shape of the edit.
# ---------------------------------------------------------------------------


class TestFoldIntegrity:
    def test_fold_refuses_without_a_verifiable_anchor(
        self,
        seq20_source: dict[str, Any],
        seq20_signed: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("VISA_ENGINE_TRUST_STORE_KEYS_JSON", raising=False)
        with pytest.raises(SystemExit) as excinfo:
            fold(seq20_source, seq20_signed, observed_at=OBSERVED_AT)
        assert "verify" in str(excinfo.value)

    def test_fold_refuses_a_source_that_is_not_the_signed_digest(
        self,
        seq20_source: dict[str, Any],
        seq20_signed: dict[str, Any],
        prod_trust_store_env: None,
    ) -> None:
        tampered = {**seq20_source, "version": "9999.9.9-tampered"}
        with pytest.raises(SystemExit) as excinfo:
            fold(tampered, seq20_signed, observed_at=OBSERVED_AT)
        assert "not the activated artifact" in str(excinfo.value)

    def test_fold_chains_to_seq20_not_to_seq21(self, seq22_source: dict[str, Any]) -> None:
        """The decision that governs this whole pack: seq-21 stopped before
        activation, so seq-22 anchors on seq-20's own measured digest. A
        folded sequence may stop — ``rulepack-prod-014`` and ``-015`` are the
        precedent, sources that were never signed."""
        assert seq22_source["previous_payload_sha256"] == SEQ20_PAYLOAD_SHA256
        assert (
            SEQ20_PAYLOAD_SHA256
            == "df02287b7fc8f572a9e6674fdf3445a2131c428e8a1492ab8a388dee5bf01a4d"
        )

    def test_fold_identity_fields(self, seq22_source: dict[str, Any]) -> None:
        assert seq22_source["sequence"] == 22
        assert seq22_source["rule_pack_id"] == str(_rule_pack_id(22))
        assert seq22_source["rollback_of_payload_sha256"] is None

    def test_fold_retires_nine_and_inserts_ten(
        self, seq20_source: dict[str, Any], seq22_source: dict[str, Any]
    ) -> None:
        before = set(_rules_by_id(seq20_source))
        after = set(_rules_by_id(seq22_source))
        assert before - after == set(RETIRED_REVIEW_RULES)
        assert after - before == set(NEW_RULE_IDS)
        assert len(RETIRED_REVIEW_RULES) == 9
        assert len(SUPPORT_RULE_IDS) == 9
        assert len(NEW_RULE_IDS) == 10

    def test_fold_edits_no_surviving_rule(
        self, seq20_source: dict[str, Any], seq22_source: dict[str, Any]
    ) -> None:
        before = _rules_by_id(seq20_source)
        after = _rules_by_id(seq22_source)
        for rule_id, rule in after.items():
            if rule_id in set(NEW_RULE_IDS):
                continue
            assert canonicalize_json(rule) == canonicalize_json(before[rule_id]), rule_id

    def test_fold_touches_no_other_top_level_key(
        self, seq20_source: dict[str, Any], seq22_source: dict[str, Any]
    ) -> None:
        for key in set(seq20_source) - {
            "sequence",
            "version",
            "rule_pack_id",
            "created_at",
            "created_by",
            "previous_payload_sha256",
            "rollback_of_payload_sha256",
            "rules",
        }:
            assert canonicalize_json(seq22_source[key]) == canonicalize_json(
                seq20_source[key]
            ), key

    def test_fold_is_deterministic(
        self,
        seq20_source: dict[str, Any],
        seq20_signed: dict[str, Any],
        prod_trust_store_env: None,
    ) -> None:
        first = fold(seq20_source, seq20_signed, observed_at=OBSERVED_AT)
        second = fold(seq20_source, seq20_signed, observed_at=OBSERVED_AT)
        assert first == second

    def test_the_emitted_source_on_disk_is_what_this_fold_produces(
        self, seq22_source: dict[str, Any]
    ) -> None:
        """The artifact committed to the repo is the fold's own output, byte
        for byte under JCS — never a hand-edited copy that drifted from the
        module that claims to generate it."""
        on_disk = _read_json(_SEQ22_SOURCE_PATH)
        assert canonicalize_json(on_disk) == canonicalize_json(seq22_source)


# ---------------------------------------------------------------------------
# Defect 1 — E23V leaves the employment exclusion; E23 and E33B stay.
# ---------------------------------------------------------------------------


class TestTheEditsContent:
    def test_e23v_is_removed_from_the_employment_exclusion(
        self, seq22_source: dict[str, Any]
    ) -> None:
        """INNOCENCE: the cure this fold exists to ship."""
        products = _product_versions(seq22_source)
        rule = _rules_by_id(seq22_source)[EMPLOYMENT_SPONSOR_RULE_ID]
        assert products["E23V"] not in rule["product_version_ids"]

    def test_e23_and_e33b_stay_inside_the_employment_exclusion(
        self, seq22_source: dict[str, Any]
    ) -> None:
        """INNOCENCE: this fold narrows a scope, it does not empty it. E33B's
        qualifying fact names a collaboration with an INDONESIAN government
        body, so an E33B applicant answering "my employer is not an
        Indonesian entity" contradicts their own qualification — see the
        module docstring, DEFECT 2."""
        products = _product_versions(seq22_source)
        rule = _rules_by_id(seq22_source)[EMPLOYMENT_SPONSOR_RULE_ID]
        assert products["E23"] in rule["product_version_ids"]
        assert products["E33B"] in rule["product_version_ids"]
        assert sorted(rule["product_version_ids"]) == sorted(
            products[code] for code in EMPLOYMENT_SPONSOR_PRODUCT_CODES
        )

    def test_source_refs_are_the_union_of_the_scoped_products_own_citations(
        self, seq20_source: dict[str, Any], seq22_source: dict[str, Any]
    ) -> None:
        """The citation list must be built from E23's and E33B's OWN catalogue
        ``source_refs`` — never E23V's refs left behind by a hand edit."""
        products = {p["product_code"]: p for p in seq20_source["products"]}
        expected: list[str] = []
        for code in EMPLOYMENT_SPONSOR_PRODUCT_CODES:
            for ref in products[code]["source_refs"]:
                if ref not in expected:
                    expected.append(ref)
        rule = _rules_by_id(seq22_source)[EMPLOYMENT_SPONSOR_RULE_ID]
        assert rule["source_refs"] == sorted(expected)

    def test_the_nine_unlocked_products_each_gain_an_eligibility_rule(
        self, seq22_source: dict[str, Any]
    ) -> None:
        """The pack's product content: the nine zero-SUPPORT products seq-21
        unlocked are carried forward unchanged by this fold."""
        products = _product_versions(seq22_source)
        rules = _rules_by_id(seq22_source)
        for code in UNLOCKED_PRODUCT_CODES:
            backing = [
                rule
                for rule_id, rule in rules.items()
                if rule_id in set(SUPPORT_RULE_IDS)
                and products[code] in rule.get("product_version_ids", [])
            ]
            assert backing, f"{code} gained no ELIGIBILITY rule"
            for rule in backing:
                assert rule["stage"] == "ELIGIBILITY"
                assert rule["effect"]["type"] == "SUPPORT"


# ---------------------------------------------------------------------------
# Defect 3 — no EXCLUDE may read a fact the interview never asked for.
# ---------------------------------------------------------------------------


class TestNoExcludeReadsASynthesisedFact:
    def test_the_seq21_rule_is_absent(self, seq22_source: dict[str, Any]) -> None:
        """INNOCENCE: ``hf.e33.guarantee-below-threshold`` is deliberately not
        carried forward. Both of its thresholds already live inside seq-20's
        SUPPORT rules, so it filtered nothing — measured, its only observable
        effect was adding a no-path reason naming a deposit the visitor was
        never asked for."""
        assert DELETED_SEQ21_RULE_ID not in _rules_by_id(seq22_source)

    def test_the_thresholds_it_duplicated_are_still_enforced_by_support_rules(
        self, seq20_source: dict[str, Any], seq22_source: dict[str, Any]
    ) -> None:
        """The reason deleting it costs nothing: the same two bounds are
        already ``gte`` conditions inside SUPPORT rules that seq-22 carries
        forward untouched."""
        for pack in (seq20_source, seq22_source):
            rules = _rules_by_id(pack)
            deposit = rules["el.e33.deposit-basis"]
            prop = rules["el.e33.property-basis"]
            assert deposit["stage"] == "ELIGIBILITY"
            assert prop["stage"] == "ELIGIBILITY"
            assert {"op": "gte", "fact": "secondhome.bank_deposit_usd", "value": 130000} in (
                deposit["when"]["args"]
            )
            assert {
                "op": "gte",
                "fact": "secondhome.qualifying_property_value_usd",
                "value": 1000000,
            } in prop["when"]["args"]

    def test_innocence_the_real_pack_passes_the_fold_time_guard(
        self, seq22_source: dict[str, Any]
    ) -> None:
        assert_no_hard_filter_reads_a_synthesised_twin_basis_fact(seq22_source)

    @pytest.mark.parametrize("fact", SYNTHESISED_TWIN_BASIS_FACTS)
    def test_guilt_a_hard_filter_on_a_twin_basis_fact_aborts_the_fold(
        self, seq22_source: dict[str, Any], fact: str
    ) -> None:
        """GUILT, one witness per guarded fact: reintroduce seq-21's third
        defect — an EXCLUDE reading a fact ``fact-mapper.ts`` synthesises for
        the basis the visitor did not choose — and the fold refuses."""
        tampered = copy.deepcopy(seq22_source)
        tampered["rules"].append(
            {
                **copy.deepcopy(_rules_by_id(seq22_source)[EMPLOYMENT_SPONSOR_RULE_ID]),
                "rule_id": "hf.synthetic.guilt-witness",
                "when": {"op": "all", "args": [{"op": "lt", "fact": fact, "value": 1}]},
            }
        )
        with pytest.raises(SystemExit) as excinfo:
            assert_no_hard_filter_reads_a_synthesised_twin_basis_fact(tampered)
        assert "hf.synthetic.guilt-witness" in str(excinfo.value)

    def test_guilt_an_eq_false_on_a_twin_basis_fact_aborts_the_fold(
        self, seq22_source: dict[str, Any]
    ) -> None:
        """GUILT: a synthesised ``known(false)`` is not an answer, so no rule
        at ANY stage may compare one of the four with ``eq false``."""
        tampered = copy.deepcopy(seq22_source)
        support = copy.deepcopy(_rules_by_id(seq22_source)["el.e33.deposit-basis"])
        support["rule_id"] = "el.synthetic.eq-false-witness"
        support["when"] = {
            "op": "all",
            "args": [
                {"op": "eq", "fact": "secondhome.bank_deposit_at_state_bank", "value": False}
            ],
        }
        tampered["rules"].append(support)
        with pytest.raises(SystemExit) as excinfo:
            assert_no_hard_filter_reads_a_synthesised_twin_basis_fact(tampered)
        assert "el.synthetic.eq-false-witness" in str(excinfo.value)

    def test_guilt_a_pack_nobody_reads_those_facts_in_aborts_the_fold(
        self, seq22_source: dict[str, Any]
    ) -> None:
        """GUARD THE GUARD (cicatrix #2): if the traversal finds no reader at
        all, the two checks above would pass vacuously. Strip every reader and
        the guard must refuse rather than report clean."""
        guarded = set(SYNTHESISED_TWIN_BASIS_FACTS)
        stripped = copy.deepcopy(seq22_source)
        stripped["rules"] = [
            rule
            for rule in stripped["rules"]
            if not any(fact in json.dumps(rule["when"]) for fact in guarded)
        ]
        with pytest.raises(SystemExit) as excinfo:
            assert_no_hard_filter_reads_a_synthesised_twin_basis_fact(stripped)
        assert "not measuring what it claims" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Behaviour — the applicant-facing outcomes the two cures are worth.
# ---------------------------------------------------------------------------


class TestTheCureIsReachable:
    def test_e23v_defect_walk_is_supported_on_the_cured_pack(
        self, seq22_compiled: compiler.CompiledRulePack
    ) -> None:
        """The objective, measured: the walk added alongside this fold
        (``offshore/work/sponsor_government/trade_office_only/employer_no``)
        — NO_SUPPORTED_PATH on signed seq-20 and on the seq-21 candidate — is
        SUPPORTED_CANDIDATES [E23V] on the cured seq-22 pack."""
        spec = _read_json(_E23V_DEFECT_WALK_PATH)
        actual = _decide(seq22_compiled, spec["overrides"], spec["label"])
        assert actual["state"] == "SUPPORTED_CANDIDATES"
        assert "E23V" in actual["candidates"]

    def test_e33b_stays_excluded_on_a_genuinely_incoherent_answer(
        self, seq22_compiled: compiler.CompiledRulePack
    ) -> None:
        """INNOCENCE for the E33B verdict: an applicant who answers
        ``work.employer_is_indonesian_entity = false`` while qualifying on a
        collaboration with an Indonesian government body is contradicting
        their own qualification. The exclusion firing here is correct, and
        this fold must not touch it."""
        walks = {
            str(_read_json(path)["label"]): _read_json(path)
            for path in _CORPUS_DIR.glob("*.json")
        }
        overrides = dict(walks["offshore/work"]["overrides"])
        overrides["work.employer_is_indonesian_entity"] = {"status": "KNOWN", "value": False}
        actual = _decide(seq22_compiled, overrides, "offshore/work/employer_no (synthetic)")
        assert actual["state"] == "NO_SUPPORTED_PATH"
        assert "PAID_ACTIVITY_WITHOUT_INDONESIAN_SPONSOR" in actual["no_path_reason_codes"]
        assert "E23V" not in actual["candidates"]
        assert "E33B" not in actual["candidates"]

    @pytest.mark.parametrize(
        ("property_value", "expected_state"),
        [
            (400_000, "NO_SUPPORTED_PATH"),
            (500_000, "NO_SUPPORTED_PATH"),
            (1_500_000, "SUPPORTED_CANDIDATES"),
        ],
    )
    def test_the_property_basis_visitor_is_never_judged_on_an_unasked_deposit(
        self,
        seq22_compiled: compiler.CompiledRulePack,
        property_value: int,
        expected_state: str,
    ) -> None:
        """DEFECT 3, stated as behaviour rather than as pack structure.

        A visitor who chose the property basis is never asked about a bank
        deposit, and ``fact-mapper.ts`` maps the unasked deposit facts to
        ``known(0)``/``known(false)`` so the SUPPORT twins resolve. These
        overrides are that mapping, verbatim. On seq-22 the outcome follows
        from the property figure alone, and no reason on the sheet names a
        deposit threshold."""
        overrides = dict(_read_json(_SECOND_HOME_PROPERTY_WALK_PATH)["overrides"])
        overrides["secondhome.qualifying_property_value_usd"] = {
            "status": "KNOWN",
            "value": property_value,
        }
        overrides["secondhome.bank_deposit_usd"] = {"status": "KNOWN", "value": 0}
        overrides["secondhome.bank_deposit_at_state_bank"] = {"status": "KNOWN", "value": False}
        overrides["secondhome.bank_deposit_in_own_name"] = {"status": "KNOWN", "value": False}

        actual = _decide(
            seq22_compiled, overrides, f"second_home/property/{property_value} (synthesised)"
        )
        assert actual["state"] == expected_state
        assert "SECOND_HOME_GUARANTEE_BELOW_THRESHOLD" not in actual["no_path_reason_codes"]
        if expected_state == "SUPPORTED_CANDIDATES":
            assert "E33" in actual["candidates"]


# ---------------------------------------------------------------------------
# Guilt — the regression this fold exists to prevent.
# ---------------------------------------------------------------------------


class TestGuilt:
    def test_guilt_reinserting_e23v_aborts_the_fold(self) -> None:
        """GUILT: put E23V back into the employment-sponsor exclusion scope —
        seq-21's first defect — and the fold-time guard refuses rather than
        silently reproducing it."""
        with pytest.raises(SystemExit) as excinfo:
            _assert_e23v_stays_cured(("E23", CURED_PRODUCT_CODE, "E33B"))
        assert CURED_PRODUCT_CODE in str(excinfo.value)

    def test_innocence_the_real_scope_passes_the_same_guard(self) -> None:
        _assert_e23v_stays_cured(EMPLOYMENT_SPONSOR_PRODUCT_CODES)
        assert CURED_PRODUCT_CODE not in EMPLOYMENT_SPONSOR_PRODUCT_CODES
