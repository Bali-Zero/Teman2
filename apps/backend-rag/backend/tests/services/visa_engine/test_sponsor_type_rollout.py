"""Tripwires for the ONE transitional default on ``ApplicantFactsData``.

``sponsor.type`` is the only fact field that is not required, and that is a
rollout mechanism with an end date, not a design choice. ``models.py``'s
comment on the field says this test exists and names it; these are the
assertions that make that comment true rather than decorative.

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

    def test_sponsor_type_is_the_only_optional_field(self) -> None:
        """The transition is ONE field wide, and closes.

        Two independent duties. While the window is open this stops a second
        field from acquiring a default under cover of this one — the way a
        temporary exception becomes the house style. When the interview ships
        and the default is removed, this test goes red and is the thing that
        tells whoever removed it that the follow-up is now complete: replace
        the expected set with ``set()`` and delete this class's first test.
        """
        optional = {
            name
            for name, field in M.ApplicantFactsData.model_fields.items()
            if not field.is_required()
        }
        assert optional == {"sponsor_type"}, (
            "ApplicantFactsData's optional-field set changed. If you added a "
            "field with a default, don't: every fact is required so that an "
            "unasked question is UNKNOWN by declaration rather than by "
            "omission. If you REMOVED sponsor_type's default because the "
            "interview now asks it, this test has done its job — assert "
            "`optional == set()` here and drop the 40-key test above."
        )


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
