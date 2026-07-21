"""Determinism (task TDD item #6): the same ``ApplicantFacts`` + compiled
pack + instants must produce a byte-identical ``Decision`` on every call —
``evaluator.evaluate`` is PURE (no I/O, no independent wall-clock reads), so
``decision_id``/``public_id``/``facts_fingerprint`` must all be DERIVED from
the inputs, never randomly generated (see ``evaluator.py``'s module
docstring divergence #5).

``assessment_id`` binding (round-3 graft from the sibling
``visa-evaluator-hardening`` PR, 2026-07-20): ``decision_id``/``public_id``
are now also derived from ``facts.assessment_id``, so ``_run`` below pins a
FIXED assessment_id by default — otherwise two "repeated calls" in the same
test would each get ``_gold_fixtures.applicant_facts``'s own default (a
fresh random UUID per call) and legitimately diverge, which would defeat the
point of a determinism test. Tests that specifically exercise the new
assessment_id-uniqueness behavior pass distinct assessment_ids explicitly.

Note: this file intentionally does NOT port
``visa-evaluator-hardening``'s ``test_caller_supplied_hmac_key_controls_fingerprint``
— that test asserts control over the fingerprint via a mandatory
``fingerprint_hmac_key``/``fingerprint_key_id`` kwarg on every ``evaluate()``
call, an API this module's injectable ``identity_provider`` design does not
have (and, per the round-3 graft decision, deliberately does not adopt).
The equivalent guarantee for THIS design — a caller-supplied provider fully
controls ``decision_id``/``public_id``/``facts_fingerprint`` — is already
covered by
``test_evaluator_gate_round1.py::TestPlaceholderIdentityEnvironmentGuard::test_production_environment_pack_succeeds_with_an_injected_real_provider``.
"""

from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timezone

import pytest

from backend.services.visa_engine.evaluator import evaluate
from backend.tests.services.visa_engine import _gold_fixtures as gf

#: Fixed (not random) assessment_id for tests whose intent is "same logical
#: assessment replayed twice must match" — ``_gold_fixtures.applicant_facts``
#: defaults to a fresh ``uuid.uuid4()`` per call when not given one, which is
#: correct for fixture ergonomics but wrong for a determinism test now that
#: ``assessment_id`` is a load-bearing identity input (round-3 graft).
_FIXED_ASSESSMENT_ID = uuid.UUID("a0b0c0d0-e0f0-4000-8000-000000000001")


@pytest.fixture(scope="module")
def compiled_gold_pack():
    return gf.build_gold_compiled_pack()


def _run(compiled_gold_pack, overrides: dict, assessment_id: uuid.UUID | None = None):
    facts = gf.applicant_facts(
        assessment_id=assessment_id or _FIXED_ASSESSMENT_ID, overrides=overrides
    )
    return evaluate(
        facts,
        compiled_gold_pack,
        effective_at=gf.GOLD_EFFECTIVE_AT,
        observed_at=gf.GOLD_EFFECTIVE_AT,
    )


class TestDeterministicReplay:
    def test_repeated_calls_produce_byte_identical_json(self, compiled_gold_pack) -> None:
        overrides = {
            "intent.purposes": gf.known(["REMOTE_WORK"]),
            "work.employer_is_indonesian_entity": gf.known(False),
            "work.serves_indonesian_clients": gf.known(False),
            "work.indonesia_source_compensation": gf.known(False),
        }
        first = _run(compiled_gold_pack, overrides)
        second = _run(compiled_gold_pack, copy.deepcopy(overrides))

        first_json = first.model_dump_json()
        second_json = second.model_dump_json()
        assert first_json == second_json

    def test_new_datetime_object_instances_with_the_same_value_still_match(
        self, compiled_gold_pack
    ) -> None:
        """A fresh ``datetime`` object (same wall value, different Python
        object identity) must not perturb the result — determinism is about
        VALUE equality of the inputs, not object identity."""
        facts_a = gf.applicant_facts(overrides={"person.nationalities": gf.known(["ID"])})
        facts_b = gf.applicant_facts(
            assessment_id=facts_a.assessment_id,
            overrides={"person.nationalities": gf.known(["ID"])},
        )
        # Force a distinct (but value-equal) datetime object for effective_at.
        effective_at_a = gf.GOLD_EFFECTIVE_AT
        effective_at_b = datetime(2026, 7, 17, 0, 0, 0, tzinfo=timezone.utc)
        assert effective_at_a is not effective_at_b
        assert effective_at_a == effective_at_b

        decision_a = evaluate(
            facts_a, compiled_gold_pack, effective_at=effective_at_a, observed_at=effective_at_a
        )
        decision_b = evaluate(
            facts_b, compiled_gold_pack, effective_at=effective_at_b, observed_at=effective_at_b
        )
        assert decision_a.model_dump_json() == decision_b.model_dump_json()

    def test_decision_id_and_public_id_are_derived_not_random(self, compiled_gold_pack) -> None:
        overrides = {"intent.purposes": gf.known(["TOURISM"])}
        first = _run(compiled_gold_pack, overrides)
        second = _run(compiled_gold_pack, dict(overrides))
        assert first.decision_id == second.decision_id
        assert first.public_id == second.public_id
        assert first.facts_fingerprint.digest == second.facts_fingerprint.digest

    def test_different_facts_produce_different_decision_ids(self, compiled_gold_pack) -> None:
        tourist = _run(compiled_gold_pack, {"intent.purposes": gf.known(["TOURISM"])})
        citizen = _run(compiled_gold_pack, {"person.nationalities": gf.known(["ID"])})
        assert tourist.decision_id != citizen.decision_id
        assert tourist.facts_fingerprint.digest != citizen.facts_fingerprint.digest

    def test_distinct_assessments_with_identical_facts_have_distinct_ids(
        self, compiled_gold_pack
    ) -> None:
        """Round-3 graft (2026-07-20, from ``visa-evaluator-hardening``):
        two DISTINCT assessments — different ``assessment_id`` — carrying
        byte-identical ``ApplicantFactsData`` must NOT collide on
        ``decision_id``/``public_id``. Before the graft, ``_deterministic_ids``
        derived its seed only from ``rule_pack_id``/``sequence``/
        ``facts_digest``/``effective_at`` — none of which vary here — so
        this pair used to come out with the SAME decision identity despite
        being two different assessments. ``facts_fingerprint`` legitimately
        stays equal (it fingerprints the DATA, not the assessment)."""
        overrides = {"intent.purposes": gf.known(["TOURISM"])}
        first = _run(compiled_gold_pack, overrides, assessment_id=uuid.uuid4())
        second = _run(compiled_gold_pack, dict(overrides), assessment_id=uuid.uuid4())

        assert first.facts_fingerprint.digest == second.facts_fingerprint.digest
        assert first.decision_id != second.decision_id
        assert first.public_id != second.public_id

    def test_json_round_trip_preserves_full_equality(self, compiled_gold_pack) -> None:
        decision = _run(compiled_gold_pack, {"person.nationalities": gf.known(["AF"])})
        dumped = decision.model_dump(mode="json", by_alias=True)
        round_tripped = json.loads(json.dumps(dumped, sort_keys=True))
        re_dumped = json.loads(json.dumps(dumped, sort_keys=True))
        assert round_tripped == re_dumped
        # And the model itself re-validates cleanly from its own dump.
        from backend.services.visa_engine.models import Decision

        rebuilt = Decision.model_validate(dumped)
        assert rebuilt.model_dump_json() == decision.model_dump_json()
