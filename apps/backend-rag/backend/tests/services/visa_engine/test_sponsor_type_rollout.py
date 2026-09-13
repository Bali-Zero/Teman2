"""Tripwires for the transitional defaults on ``ApplicantFactsData``.

``sponsor.type`` was the first fact field to get a transitional default; it
is a rollout mechanism with an end date, not a design choice.
``models.py``'s comment on the field says this test exists and names it —
these are the assertions that make that comment true rather than
decorative.

2026-08-23: three more fields (``family.stepchild_marriage_certificate_
confirmed``, ``family.stepchild_birth_certificate_confirmed``,
``family.sponsor_permit_basis``) joined the same mechanism for the same
reason — the fact-vocabulary-extension mandate that added them requires
"a request that omits the new facts must still work, yielding UNKNOWN",
and ``ApplicantFactsData`` IS ``VisaOracleEvaluateRequest.facts``
(``api_models.py``), so a newly-required key breaks every already-deployed
40/41/42/43-key caller exactly the way the ``sponsor_type`` comment
describes. The set below is now four wide, not one, and
``TestSponsorTypeRolloutDefault`` no longer asserts it is the only member —
see ``TestFactVocabularyExtensionRolloutDefaults0823`` for the other three.

Why the default has to exist at all: ``VisaOracleEvaluateRequest`` IS
``ApplicantFacts`` (``api_models.py``), so the HTTP body and the closed
internal vocabulary are the same object. A required 41st key breaks BOTH
deploy directions — the already-deployed interview sends 40 and fails
``Field required``; a frontend that ships first sends 41 and fails
``extra_forbidden`` — and the second direction is not fixable from this side.
The evaluate call is awaited on the render path for every visitor
(``OracleShell.tsx``), so neither window is silent.

What must stay true while the window is open, and what must go red when it
closes, is exactly what is pinned below.
"""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError

from backend.services.visa_engine import enums
from backend.services.visa_engine import models as M
from backend.services.visa_engine.compiler import compile_rule_pack
from backend.tests.services.visa_engine.gold_harness import loader

_UNKNOWN = {"status": "UNKNOWN", "reason": "NOT_ASKED"}


def _all_unknown_facts() -> dict[str, dict[str, str]]:
    """Every applicant fact, built STRUCTURALLY from the vocabulary.

    Deliberately not a literal dict: a literal would have to be edited every
    time a fact is added, which is the very drift these tests are about.
    """
    return {path.value: dict(_UNKNOWN) for path in enums.APPLICANT_FACT_PATHS}


class TestSponsorTypeRolloutDefault:
    def test_a_forty_key_body_still_validates_and_yields_a_real_unknown_fact(self) -> None:
        """The deployed interview's payload — the whole point of the default.

        Asserting the TYPE, not just truthiness, is load-bearing: this model
        does not validate defaults, so a dict literal in ``models.py`` would
        construct happily here and only surface as an ``AttributeError`` in a
        consumer reading ``.status`` — on production traffic, during the one
        window the default exists to protect.
        """
        body = _all_unknown_facts()
        del body["sponsor.type"]
        assert "sponsor.type" not in body

        facts = M.ApplicantFactsData.model_validate(body)

        assert isinstance(facts.sponsor_type, M.UnknownFact)
        assert facts.sponsor_type.status == "UNKNOWN"
        assert facts.sponsor_type.reason == enums.UnknownReason.NOT_ASKED

    def test_the_default_asserts_unknown_and_never_a_value(self) -> None:
        """An absent fact must become a QUESTION, never a silent answer.

        This is the invariant the closed vocabulary exists to protect, and the
        one a tolerant default could quietly destroy: defaulting to, say,
        ``NONE`` would make the engine offer products on an answer nobody gave.
        """
        assert isinstance(M._SPONSOR_TYPE_ROLLOUT_DEFAULT, M.UnknownFact)
        assert M._SPONSOR_TYPE_ROLLOUT_DEFAULT.status == "UNKNOWN"
        assert not hasattr(M._SPONSOR_TYPE_ROLLOUT_DEFAULT, "value")

    def test_a_supplied_value_is_honoured_and_not_clobbered(self) -> None:
        """Innocence: the default must not overwrite a caller who DID answer."""
        body = _all_unknown_facts()
        body["sponsor.type"] = {"status": "KNOWN", "value": "GOVERNMENT"}

        facts = M.ApplicantFactsData.model_validate(body)

        assert facts.sponsor_type.status == "KNOWN"
        assert facts.sponsor_type.value == enums.SponsorType.GOVERNMENT

    def test_the_enum_is_still_enforced_on_a_supplied_value(self) -> None:
        """Tolerating ABSENCE must not tolerate a wrong value."""
        body = _all_unknown_facts()
        body["sponsor.type"] = {"status": "KNOWN", "value": "BENEFACTOR"}

        with pytest.raises(ValidationError):
            M.ApplicantFactsData.model_validate(body)

    def test_extra_forbidden_still_bites(self) -> None:
        """The one optional field must not have loosened the closed object."""
        body = _all_unknown_facts()
        body["sponsor.typo"] = dict(_UNKNOWN)

        with pytest.raises(ValidationError):
            M.ApplicantFactsData.model_validate(body)

    def test_sponsor_type_is_one_of_a_named_finite_set_of_optional_fields(self) -> None:
        """The rollout transition is a NAMED, finite set, and each closes.

        Renamed from "is the only optional field" (2026-08-23): the set
        widened from one to four that day (three more transitional fields
        under the fact-vocabulary-extension mandate, see the module
        docstring and ``TestFactVocabularyExtensionRolloutDefaults0823``),
        then to five on 2026-08-24 (``immigration_renewal_paid``, F4 — see
        ``TestFactVocabularyExtensionRolloutDefault0824``), then to six on
        2026-09-13 (``investment_amount_usd``, PR-D4c-1 — see
        ``TestFactVocabularyExtensionRolloutDefaultD4c1``). Widening is
        deliberate and tracked HERE — this stops a field from
        silently acquiring a default under cover of an existing one without
        anyone updating the expected set. When any one field's interview
        ships and its default is removed, this test goes red for that
        field and is the thing that tells whoever removed it the follow-up
        is complete: drop that field from the expected set (and, once the
        set is empty, delete this test along with the 40-key test above).

        Why ``investment_amount_usd`` is a legitimate transitional exception
        here and not a loosening of "every fact is required": the interview
        that will ALWAYS send this key ships in a following lane, D4c-2 (the
        mapper + the question itself); PR-D4c-1 is contract-only — it
        declares the wire key so D4c-2 can exist, but asks nothing yet. The
        expected removal: once D4c-2 ships and is verified live on Vercel
        (SERVITA), a PR of its own — straight after, no other work folded in
        — drops the ``default=`` from ``investment_amount_usd`` in
        ``models.py`` and removes the field from the set below.
        """
        optional = {
            name
            for name, field in M.ApplicantFactsData.model_fields.items()
            if not field.is_required()
        }
        assert optional == {
            "sponsor_type",
            "family_stepchild_marriage_certificate_confirmed",
            "family_stepchild_birth_certificate_confirmed",
            "family_sponsor_permit_basis",
            "immigration_renewal_paid",
            "investment_amount_usd",
        }, (
            "ApplicantFactsData's optional-field set changed. If you added a "
            "field with a default, don't: every fact is required so that an "
            "unasked question is UNKNOWN by declaration rather than by "
            "omission. If you REMOVED a NAMED field's default because its "
            "interview now asks it, this test has done its job — drop that "
            "field from the expected set above (and delete this test plus "
            "the 40-key test once the set is empty)."
        )


class TestFactVocabularyExtensionRolloutDefaults0823:
    """Same mechanism as ``TestSponsorTypeRolloutDefault``, for the three
    facts the 2026-08-23 fact-vocabulary-extension mandate added:
    ``family.stepchild_marriage_certificate_confirmed``,
    ``family.stepchild_birth_certificate_confirmed`` (boolean evidence
    facts) and ``family.sponsor_permit_basis`` (closed-enum fact). The
    mandate's own wire-compatibility requirement — "a request that omits
    the new facts must still work, yielding UNKNOWN" — is exactly what
    these assertions pin.
    """

    _BOOLEAN_FIELDS = (
        "family.stepchild_marriage_certificate_confirmed",
        "family.stepchild_birth_certificate_confirmed",
    )

    @pytest.mark.parametrize("wire_key", _BOOLEAN_FIELDS)
    def test_a_body_omitting_the_new_boolean_key_still_validates(self, wire_key: str) -> None:
        body = _all_unknown_facts()
        del body[wire_key]
        assert wire_key not in body

        facts = M.ApplicantFactsData.model_validate(body)

        python_name = wire_key.replace(".", "_")
        fact = getattr(facts, python_name)
        assert isinstance(fact, M.UnknownFact)
        assert fact.status == "UNKNOWN"
        assert fact.reason == enums.UnknownReason.NOT_ASKED

    def test_a_body_omitting_sponsor_permit_basis_still_validates(self) -> None:
        body = _all_unknown_facts()
        del body["family.sponsor_permit_basis"]
        assert "family.sponsor_permit_basis" not in body

        facts = M.ApplicantFactsData.model_validate(body)

        assert isinstance(facts.family_sponsor_permit_basis, M.UnknownFact)
        assert facts.family_sponsor_permit_basis.status == "UNKNOWN"
        assert facts.family_sponsor_permit_basis.reason == enums.UnknownReason.NOT_ASKED

    def test_all_three_new_defaults_assert_unknown_and_never_a_value(self) -> None:
        for default in (
            M._STEPCHILD_MARRIAGE_CERTIFICATE_CONFIRMED_ROLLOUT_DEFAULT,
            M._STEPCHILD_BIRTH_CERTIFICATE_CONFIRMED_ROLLOUT_DEFAULT,
            M._SPONSOR_PERMIT_BASIS_ROLLOUT_DEFAULT,
        ):
            assert isinstance(default, M.UnknownFact)
            assert default.status == "UNKNOWN"
            assert not hasattr(default, "value")

    @pytest.mark.parametrize("wire_key", _BOOLEAN_FIELDS)
    def test_a_supplied_boolean_value_is_honoured_and_not_clobbered(self, wire_key: str) -> None:
        body = _all_unknown_facts()
        body[wire_key] = {"status": "KNOWN", "value": True}

        facts = M.ApplicantFactsData.model_validate(body)

        fact = getattr(facts, wire_key.replace(".", "_"))
        assert fact.status == "KNOWN"
        assert fact.value is True

    def test_a_supplied_sponsor_permit_basis_is_honoured_and_not_clobbered(self) -> None:
        body = _all_unknown_facts()
        body["family.sponsor_permit_basis"] = {"status": "KNOWN", "value": "FAMILY_REUNIFICATION"}

        facts = M.ApplicantFactsData.model_validate(body)

        assert facts.family_sponsor_permit_basis.status == "KNOWN"
        assert facts.family_sponsor_permit_basis.value == enums.SponsorPermitBasis.FAMILY_REUNIFICATION

    def test_sponsor_permit_basis_enum_is_still_enforced_on_a_supplied_value(self) -> None:
        """Tolerating ABSENCE must not tolerate a wrong value (mirrors
        ``TestSponsorTypeRolloutDefault``'s equivalent test)."""
        body = _all_unknown_facts()
        body["family.sponsor_permit_basis"] = {"status": "KNOWN", "value": "BENEFACTOR"}

        with pytest.raises(ValidationError):
            M.ApplicantFactsData.model_validate(body)

    @pytest.mark.parametrize("wire_key", _BOOLEAN_FIELDS)
    def test_boolean_type_is_still_enforced_on_a_supplied_value(self, wire_key: str) -> None:
        body = _all_unknown_facts()
        body[wire_key] = {"status": "KNOWN", "value": "yes"}  # a string, not a bool

        with pytest.raises(ValidationError):
            M.ApplicantFactsData.model_validate(body)

    def test_extra_forbidden_still_bites_for_the_new_fields_too(self) -> None:
        body = _all_unknown_facts()
        body["family.stepchild_marriage_certificate_confirmedx"] = dict(_UNKNOWN)

        with pytest.raises(ValidationError):
            M.ApplicantFactsData.model_validate(body)


class TestFactVocabularyExtensionRolloutDefault0824:
    """Same mechanism again, for the one fact the 2026-08-24 F4 mandate
    added: ``immigration.renewal_paid`` (boolean — payment, not filing, per
    the owner ruling; see ``fact_registry.py``'s
    ``_derive_has_active_stay_permit`` docstring for the verbatim text).
    Wire-compatibility requirement is identical to the 2026-08-23 set: "a
    request that omits the new fact must still work, yielding UNKNOWN".
    """

    _WIRE_KEY = "immigration.renewal_paid"

    def test_a_body_omitting_renewal_paid_still_validates(self) -> None:
        body = _all_unknown_facts()
        del body[self._WIRE_KEY]
        assert self._WIRE_KEY not in body

        facts = M.ApplicantFactsData.model_validate(body)

        assert isinstance(facts.immigration_renewal_paid, M.UnknownFact)
        assert facts.immigration_renewal_paid.status == "UNKNOWN"
        assert facts.immigration_renewal_paid.reason == enums.UnknownReason.NOT_ASKED

    def test_the_default_asserts_unknown_and_never_a_value(self) -> None:
        assert isinstance(M._RENEWAL_PAID_ROLLOUT_DEFAULT, M.UnknownFact)
        assert M._RENEWAL_PAID_ROLLOUT_DEFAULT.status == "UNKNOWN"
        assert not hasattr(M._RENEWAL_PAID_ROLLOUT_DEFAULT, "value")

    def test_a_supplied_true_value_is_honoured_and_not_clobbered(self) -> None:
        body = _all_unknown_facts()
        body[self._WIRE_KEY] = {"status": "KNOWN", "value": True}

        facts = M.ApplicantFactsData.model_validate(body)

        assert facts.immigration_renewal_paid.status == "KNOWN"
        assert facts.immigration_renewal_paid.value is True

    def test_a_supplied_false_value_is_honoured_and_not_clobbered(self) -> None:
        """False is a real, meaningful answer here (unpaid renewal / no
        renewal at all) — not a state that collapses into UNKNOWN."""
        body = _all_unknown_facts()
        body[self._WIRE_KEY] = {"status": "KNOWN", "value": False}

        facts = M.ApplicantFactsData.model_validate(body)

        assert facts.immigration_renewal_paid.status == "KNOWN"
        assert facts.immigration_renewal_paid.value is False

    def test_boolean_type_is_still_enforced_on_a_supplied_value(self) -> None:
        body = _all_unknown_facts()
        body[self._WIRE_KEY] = {"status": "KNOWN", "value": "yes"}  # a string, not a bool

        with pytest.raises(ValidationError):
            M.ApplicantFactsData.model_validate(body)

    def test_extra_forbidden_still_bites_for_this_field_too(self) -> None:
        body = _all_unknown_facts()
        body["immigration.renewal_paidx"] = dict(_UNKNOWN)

        with pytest.raises(ValidationError):
            M.ApplicantFactsData.model_validate(body)


class TestFactVocabularyExtensionRolloutDefaultD4c1:
    """Same mechanism again, for the one fact PR-D4c-1 (2026-09-13) added:
    ``investment.investment_amount_usd`` (a ``MoneyFact``, same shape as the
    two existing IDR amounts — contract-only, no question/mapper/rule yet;
    D4c-2 adds those). Wire-compatibility requirement is identical to the
    2026-08-24 set: "a request that omits the new fact must still work,
    yielding UNKNOWN".
    """

    _WIRE_KEY = "investment.investment_amount_usd"

    def test_a_body_omitting_investment_amount_usd_still_validates(self) -> None:
        body = _all_unknown_facts()
        del body[self._WIRE_KEY]
        assert self._WIRE_KEY not in body

        facts = M.ApplicantFactsData.model_validate(body)

        assert isinstance(facts.investment_amount_usd, M.UnknownFact)
        assert facts.investment_amount_usd.status == "UNKNOWN"
        assert facts.investment_amount_usd.reason == enums.UnknownReason.NOT_ASKED

    def test_the_default_asserts_unknown_and_never_a_value(self) -> None:
        assert isinstance(M._INVESTMENT_AMOUNT_USD_ROLLOUT_DEFAULT, M.UnknownFact)
        assert M._INVESTMENT_AMOUNT_USD_ROLLOUT_DEFAULT.status == "UNKNOWN"
        assert not hasattr(M._INVESTMENT_AMOUNT_USD_ROLLOUT_DEFAULT, "value")

    def test_a_supplied_value_is_honoured_and_not_clobbered(self) -> None:
        """Innocence: the default must not overwrite a caller who DID answer.

        A KNOWN zero is deliberately exercised too: it is a real, meaningful
        answer (an applicant with a confirmed-zero committed amount), not a
        state the default mechanism may collapse into UNKNOWN — the same
        distinction ``immigration_renewal_paid``'s KNOWN-False test makes for
        booleans.
        """
        body = _all_unknown_facts()
        body[self._WIRE_KEY] = {"status": "KNOWN", "value": 50_000}

        facts = M.ApplicantFactsData.model_validate(body)

        assert facts.investment_amount_usd.status == "KNOWN"
        assert facts.investment_amount_usd.value == 50_000

        body[self._WIRE_KEY] = {"status": "KNOWN", "value": 0}
        facts_zero = M.ApplicantFactsData.model_validate(body)
        assert facts_zero.investment_amount_usd.status == "KNOWN"
        assert facts_zero.investment_amount_usd.value == 0

    def test_integer_type_is_still_enforced_on_a_supplied_value(self) -> None:
        body = _all_unknown_facts()
        body[self._WIRE_KEY] = {"status": "KNOWN", "value": "a lot"}  # a string, not an int

        with pytest.raises(ValidationError):
            M.ApplicantFactsData.model_validate(body)

    def test_negative_amount_is_still_rejected(self) -> None:
        """Tolerating ABSENCE must not tolerate a nonsensical value —
        ``KnownMoney.value`` is ``ge=0`` regardless of currency."""
        body = _all_unknown_facts()
        body[self._WIRE_KEY] = {"status": "KNOWN", "value": -1}

        with pytest.raises(ValidationError):
            M.ApplicantFactsData.model_validate(body)

    def test_extra_forbidden_still_bites_for_this_field_too(self) -> None:
        body = _all_unknown_facts()
        body["investment.investment_amount_usdx"] = dict(_UNKNOWN)

        with pytest.raises(ValidationError):
            M.ApplicantFactsData.model_validate(body)


class TestSponsorTypeIsUsableByARule:
    """A fact no rule can reference is a fact that was never really shipped.

    Measured against ``rulepack-prod-006``, ``sponsor.type`` plus the purpose
    already collected makes six of the eleven currently unreachable products
    uniquely identifiable: E23U, E23V, E28C, E33A, E33B and E33C. Sponsor
    type alone is not sufficient, while E28B/E28D/E28F and E30E/E30F still
    collide. This is capability evidence, not legal eligibility evidence:
    the rules ship in a later pack and must be grounded independently. The
    reachability sweep must be re-run against that pack rather than freezing
    this snapshot as a permanent count. What has to be true FIRST — and is
    what these assertions prove — is
    that such a rule compiles, and that a typo in it is caught before the
    pack is ever signed rather than at evaluation time.
    """

    @staticmethod
    def _pack_with_sponsor_rule(value: str, rule_id: str) -> M.RulePack:
        raw = copy.deepcopy(loader.load_rule_pack_raw())
        rules = raw["payload"]["rules"] if "payload" in raw else raw["rules"]
        template = copy.deepcopy(next(r for r in rules if r.get("stage") == "ELIGIBILITY"))
        template.update(
            rule_id=rule_id,
            explanation_key=f"explain.{rule_id}",
            required_facts=["sponsor.type"],
            on_unknown="NEEDS_INPUT",
            when={"op": "eq", "fact": "sponsor.type", "value": value},
        )
        rules.append(template)
        return M.RulePack.model_validate(raw)

    def test_a_rule_reading_sponsor_type_compiles(self) -> None:
        report = compile_rule_pack(self._pack_with_sponsor_rule("GOVERNMENT", "el.probe.gov"))
        assert report.ok, [f"{e.code}: {e.message}" for e in report.errors]

    def test_a_value_outside_the_enum_is_rejected_at_COMPILE_time(self) -> None:
        """Before signing, not during an applicant's evaluation.

        ``allowed_values`` on the registry spec is what makes this a compile
        error; without it a typo would sit in a signed pack and simply never
        match, which reads exactly like "this applicant is not eligible".
        """
        report = compile_rule_pack(self._pack_with_sponsor_rule("BENEFACTOR", "el.probe.bad"))

        assert not report.ok
        assert any(e.code == "FACT_LITERAL_NOT_ALLOWED" for e in report.errors), [
            e.code for e in report.errors
        ]

    def test_innocence_the_untouched_gold_pack_still_compiles(self) -> None:
        """Guards against the probe above passing because everything fails."""
        report = compile_rule_pack(M.RulePack.model_validate(loader.load_rule_pack_raw()))
        assert report.ok, [f"{e.code}: {e.message}" for e in report.errors]
