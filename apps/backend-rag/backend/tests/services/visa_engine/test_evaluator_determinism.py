"""Determinism (task TDD item #6): the same ``ApplicantFacts`` + compiled
pack + instants must produce a byte-identical ``Decision`` on every call —
``evaluator.evaluate`` is PURE (no I/O, no independent wall-clock reads), so
``decision_id``/``public_id``/``facts_fingerprint`` must all be DERIVED from
the inputs, never randomly generated (see ``evaluator.py``'s module
docstring divergence #5).
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone

import pytest

from backend.services.visa_engine.evaluator import evaluate
from backend.tests.services.visa_engine import _gold_fixtures as gf


@pytest.fixture(scope="module")
def compiled_gold_pack():
    return gf.build_gold_compiled_pack()


def _run(compiled_gold_pack, overrides: dict):
    facts = gf.applicant_facts(overrides=overrides)
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
