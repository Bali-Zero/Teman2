"""seq-27 — the negative and boundary side of the visit family (B1, C1, C6, D12).

Prior coverage, stated exactly. ``test_seq23_pack.py`` already carries an engine witness and a
mutation/revert proof for ``ACTIVE_OVERSTAY_SETTLE_FIRST`` (one C1 case, 5 days, on the seq-23
candidate pack), and the interview-walk census already walks the D12 no-route explorer to its dead
end (``NO_SUPPORTED_PATH``, no candidate) -- but it pins a state and a candidate list, never the
reason code. The gold-coverage corpus (``gold_coverage/personas/``) is positive-only by design.
What was still missing, and is added here for the SIGNED seq-27 pack:

* B1 ``intent.stay_days <= 60`` -- 60 offered, 61 not;
* C1 ``intent.stay_days <= 180`` -- 180 offered, 181 not;
* C6 ``intent.stay_days <= 180`` AND ``family.sponsor_confirmed == true`` -- the sponsor-false
  and the unknown-sponsor/unknown-stay sides, each on its own;
* D12 ``hf.d12-onshore-conversion-excluded`` -- the named cause ``D12_NOT_CONVERTIBLE``, and the
  twin that proves the cause is the conversion answer and nothing else;
* the two global overstay filters, at 0 / 1 / 60 / 61 days and through C1, C6 and D12:
  ``overstay_days > 0`` -> ``ACTIVE_OVERSTAY_SETTLE_FIRST``, ``overstay_days > 60`` ->
  ``OVERSTAY_EXCEEDS_60_DAYS`` (no other test in the visa_engine suite names it). The overstay
  cases use an ONSHORE applicant on a compatible visit-class status: an overstay describes a
  person in Indonesia (UU 6/2011 art. 78), and an offshore base with an overstay is a contradiction
  the API boundary flags with ``CONFLICTING_IMMIGRATION_STATUS_CONDITION`` -- asserted absent.

Every case is evaluated against the SIGNED seq-27 pack by name -- not "the highest pack on disk"
-- at a fixed instant inside its freshness window, so the file stays a statement about seq-27
after a later pack is signed. Cases are built from the corpus's own persona and walk JSON with
ONE fact changed, so a passing twin and its failing sibling differ in exactly that fact (the
onshore overstay bases first move the person into Indonesia and are proven supported on their own).

What this file does NOT pin, on purpose: the ride-along reasons that appear next to a named cause
(``BRIDGING_ONSHORE_ONLY`` beside a C6 miss, ``BVK_NATIONALITY_ONLY``/``AGE_BELOW_55`` beside a
tourist's miss). Several of them are known copy defects awaiting a later pack; pinning them would
turn a defect into a requirement. Only the named cause is asserted, as a subset.

A missing artifact FAILS (``_read_json``), it never skips (cicatrix #2).
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from backend.scripts.visa_engine.gold_replay_driver import (
    PACKS_DIR,
    _offline_identity_provider,
    _repository_trust_store,
    build_persona_request,
)
from backend.services.visa_engine import evaluate_path, evaluator
from backend.services.visa_engine.bundle import verify_rule_pack
from backend.services.visa_engine.compiler import CompiledRulePack, build_compiled_pack
from backend.services.visa_engine.enums import DecisionState
from backend.tests.services.visa_engine.gold_replay import _decision_actual
from backend.tests.services.visa_engine.test_evaluator_gold import Persona

_CORPUS = Path(__file__).resolve().parent / "gold_coverage"
_SEQ27_SIGNED = PACKS_DIR / "rulepack-prod-027.signed.json"
#: After seq-27's ``signed_at`` (2026-10-10T03:42:26Z) and 30 days before its 32-day portal
#: sources go stale (2026-11-09T13:21:22Z): the pack verifies and no source is held.
AT = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)

Facts = dict[str, dict[str, Any]]
Actual = dict[str, Any]


def _known(value: Any) -> dict[str, Any]:
    return {"status": "KNOWN", "value": value}


_UNKNOWN: dict[str, Any] = {"status": "UNKNOWN", "reason": "NOT_ASKED"}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise AssertionError(
            f"{path.name} does not exist on disk — a witness that never ran proves nothing"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _overrides(*parts: str) -> Facts:
    return _read_json(_CORPUS.joinpath(*parts))["overrides"]


def _with(base: Facts, **changes: dict[str, Any]) -> Facts:
    """``base`` with ONE or more facts replaced; ``__`` in a keyword stands for the dot."""
    facts = copy.deepcopy(base)
    for key, value in changes.items():
        path = key.replace("__", ".")
        assert path in facts, f"{path} is not a fact of this base — the twin would add, not change"
        facts[path] = value
    return facts


@pytest.fixture(scope="module")
def seq27() -> CompiledRulePack:
    verified = verify_rule_pack(
        _read_json(_SEQ27_SIGNED), trust_store=_repository_trust_store(), observed_at=AT
    )
    compiled = build_compiled_pack(verified.pack)
    assert compiled.sequence == 27
    return compiled


@pytest.fixture(scope="module")
def decide(seq27: CompiledRulePack) -> Any:
    def _decide(facts: Facts) -> Actual:
        persona = Persona(
            id=0, label="visit-seq27", overrides=facts, expected_state=DecisionState.NEEDS_INPUT
        )
        request = build_persona_request(persona)
        applicant = request.applicant_facts()
        decision = evaluator.evaluate(
            applicant,
            seq27,
            effective_at=AT,
            observed_at=AT,
            identity_provider=_offline_identity_provider,
        )
        decision = evaluate_path.apply_public_policy_adapters(
            decision,
            applicant,
            seq27,
            disclosed_review_flags=request.effective_review_flags(),
        )
        return _decision_actual(decision)

    return _decide


# Bases: the corpus's own positive persona/walk for each product, untouched.
@pytest.fixture(scope="module")
def tourist() -> Facts:
    """Italian (VOA list) adult, tourism, offshore, 121 days -> C1 only."""
    return _overrides("fixtures", "walks", "offshore_tourism.json")


@pytest.fixture(scope="module")
def c6_persona() -> Facts:
    return _overrides("personas", "C6.json")


@pytest.fixture(scope="module")
def d12_persona() -> Facts:
    return _overrides("personas", "D12.json")


@pytest.fixture(scope="module")
def d12_no_route() -> Facts:
    """The explorer who converts onshore with no sponsor and no investor route."""
    return _overrides("fixtures", "walks", "offshore_business_exploring_sponsor_no_no_route.json")


def test_the_bases_are_the_supported_twins(
    decide: Any, tourist: Facts, c6_persona: Facts, d12_persona: Facts
) -> None:
    """Every boundary below is "one fact away from a supported base" — prove the base first."""
    assert decide(tourist)["candidates"] == ["C1"]
    assert decide(c6_persona)["candidates"] == ["C6"]
    assert decide(d12_persona)["candidates"] == ["D12"]


# ---------------------------------------------------------------------------
# B1 and C1 — the stay-day ceilings
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("stay_days", "candidates"),
    [(30, ["B1", "C1"]), (60, ["B1", "C1"]), (61, ["C1"]), (180, ["C1"])],
)
def test_b1_is_offered_up_to_60_days_and_not_at_61(
    decide: Any, tourist: Facts, stay_days: int, candidates: list[str]
) -> None:
    actual = decide(_with(tourist, intent__stay_days=_known(stay_days)))
    assert actual["state"] == "SUPPORTED_CANDIDATES"
    assert actual["candidates"] == candidates


def test_c1_is_offered_at_180_days_and_nothing_is_offered_at_181(
    decide: Any, tourist: Facts
) -> None:
    at_cap = decide(_with(tourist, intent__stay_days=_known(180)))
    assert (at_cap["state"], at_cap["candidates"]) == ("SUPPORTED_CANDIDATES", ["C1"])
    past_cap = decide(_with(tourist, intent__stay_days=_known(181)))
    assert (past_cap["state"], past_cap["candidates"]) == ("NO_SUPPORTED_PATH", [])


def test_a_tourist_with_no_stay_length_is_asked_not_decided(decide: Any, tourist: Facts) -> None:
    actual = decide(_with(tourist, intent__stay_days=_UNKNOWN))
    assert actual["state"] == "NEEDS_INPUT"
    assert actual["candidates"] == []
    assert "intent.stay_days" in actual["missing_facts"]


# ---------------------------------------------------------------------------
# C6 — stay ceiling and sponsor
# ---------------------------------------------------------------------------


def test_c6_is_offered_at_180_days_and_not_at_181(decide: Any, c6_persona: Facts) -> None:
    at_cap = decide(_with(c6_persona, intent__stay_days=_known(180)))
    assert (at_cap["state"], at_cap["candidates"]) == ("SUPPORTED_CANDIDATES", ["C6"])
    past_cap = decide(_with(c6_persona, intent__stay_days=_known(181)))
    assert (past_cap["state"], past_cap["candidates"]) == ("NO_SUPPORTED_PATH", [])


def test_c6_without_a_confirmed_sponsor_is_not_offered(decide: Any, c6_persona: Facts) -> None:
    actual = decide(_with(c6_persona, family__sponsor_confirmed=_known(False)))
    assert (actual["state"], actual["candidates"]) == ("NO_SUPPORTED_PATH", [])


@pytest.mark.parametrize(
    ("fact", "change"),
    [
        ("family.sponsor_confirmed", {"family__sponsor_confirmed": _UNKNOWN}),
        ("intent.stay_days", {"intent__stay_days": _UNKNOWN}),
    ],
)
def test_c6_with_an_unknown_decisive_fact_asks_for_that_fact(
    decide: Any, c6_persona: Facts, fact: str, change: dict[str, Any]
) -> None:
    actual = decide(_with(c6_persona, **change))
    assert actual["state"] == "NEEDS_INPUT"
    assert actual["candidates"] == []
    assert fact in actual["missing_facts"]


# ---------------------------------------------------------------------------
# D12 — the named cause of the onshore-conversion dead end
# ---------------------------------------------------------------------------


def test_d12_onshore_conversion_with_no_investor_route_ends_on_its_named_cause(
    decide: Any, d12_no_route: Facts
) -> None:
    actual = decide(d12_no_route)
    assert (actual["state"], actual["candidates"]) == ("NO_SUPPORTED_PATH", [])
    assert "D12_NOT_CONVERTIBLE" in actual["no_path_reason_codes"]


def test_d12_not_convertible_is_the_conversion_answer_and_nothing_else(
    decide: Any, d12_no_route: Facts
) -> None:
    """Guilt/innocence twin: flip ONLY the conversion answer and D12 is offered."""
    offshore_application = decide(
        _with(d12_no_route, process__wants_onshore_conversion=_known(False))
    )
    assert (offshore_application["state"], offshore_application["candidates"]) == (
        "SUPPORTED_CANDIDATES",
        ["D12"],
    )
    assert "D12_NOT_CONVERTIBLE" not in offshore_application["no_path_reason_codes"]


def test_d12_with_an_unanswered_conversion_question_asks_it(
    decide: Any, d12_persona: Facts
) -> None:
    actual = decide(d12_persona | {"process.wants_onshore_conversion": _UNKNOWN})
    assert actual["state"] == "NEEDS_INPUT"
    assert "process.wants_onshore_conversion" in actual["missing_facts"]


# ---------------------------------------------------------------------------
# The two global overstay filters, through each product's own base
# ---------------------------------------------------------------------------


#: A person who is physically in Indonesia on a visit-class stay is the only person an overstay
#: can describe (UU 6/2011 art. 78: staying in Indonesian territory past the permit's expiry). The
#: offshore corpus bases carry ``currently_in_indonesia == false``; changing only the overstay on
#: them builds a contradictory applicant that the API boundary flags
#: (``CONFLICTING_IMMIGRATION_STATUS_CONDITION``) -- not the person the filters are about.
_CONFLICT_NOTICE = "CONFLICTING_IMMIGRATION_STATUS_CONDITION"


def _onshore(base: Facts, status_code: str) -> Facts:
    """``base`` for someone already in Indonesia on a visit-class stay (``status_code``)."""
    return base | {
        "immigration.currently_in_indonesia": _known(True),
        "immigration.current_status_code": _known(status_code),
        "immigration.overstay_days": _known(0),
    }


@pytest.fixture(scope="module")
def bases(tourist: Facts, c6_persona: Facts, d12_persona: Facts) -> dict[str, Facts]:
    """Each product's corpus base, moved onshore on a compatible visit-class status."""
    return {
        "C1": _onshore(tourist, "C1"),
        "C6": _onshore(c6_persona, "C6"),
        "D12": _onshore(d12_persona, "C1"),
    }


def test_an_overstay_set_on_an_offshore_base_is_the_contradiction_the_boundary_flags(
    decide: Any, tourist: Facts
) -> None:
    """Why the overstay cases below move the base onshore: offshore + overstay is not a person."""
    actual = decide(_with(tourist, immigration__overstay_days=_known(61)))
    assert _CONFLICT_NOTICE in actual["notice_codes"]


@pytest.mark.parametrize("product", ["C1", "C6", "D12"])
def test_the_onshore_bases_are_consistent_and_supported_without_an_overstay(
    decide: Any, bases: dict[str, Facts], product: str
) -> None:
    actual = decide(bases[product])
    assert (actual["state"], actual["candidates"]) == ("SUPPORTED_CANDIDATES", [product])
    assert _CONFLICT_NOTICE not in actual["notice_codes"]


@pytest.mark.parametrize("product", ["C1", "C6", "D12"])
def test_no_overstay_is_the_supported_twin(
    decide: Any, bases: dict[str, Facts], product: str
) -> None:
    actual = decide(_with(bases[product], immigration__overstay_days=_known(0)))
    assert (actual["state"], actual["candidates"]) == ("SUPPORTED_CANDIDATES", [product])
    assert _CONFLICT_NOTICE not in actual["notice_codes"]


@pytest.mark.parametrize("overstay_days", [1, 60])
@pytest.mark.parametrize("product", ["C1", "C6", "D12"])
def test_any_overstay_up_to_60_days_says_settle_it_first_and_offers_nothing(
    decide: Any, bases: dict[str, Facts], product: str, overstay_days: int
) -> None:
    actual = decide(_with(bases[product], immigration__overstay_days=_known(overstay_days)))
    assert (actual["state"], actual["candidates"]) == ("NO_SUPPORTED_PATH", [])
    assert "ACTIVE_OVERSTAY_SETTLE_FIRST" in actual["no_path_reason_codes"]
    assert "OVERSTAY_EXCEEDS_60_DAYS" not in actual["no_path_reason_codes"]
    assert _CONFLICT_NOTICE not in actual["notice_codes"]


@pytest.mark.parametrize("product", ["C1", "C6", "D12"])
def test_an_overstay_past_60_days_adds_its_own_named_cause(
    decide: Any, bases: dict[str, Facts], product: str
) -> None:
    actual = decide(_with(bases[product], immigration__overstay_days=_known(61)))
    assert (actual["state"], actual["candidates"]) == ("NO_SUPPORTED_PATH", [])
    assert {"ACTIVE_OVERSTAY_SETTLE_FIRST", "OVERSTAY_EXCEEDS_60_DAYS"} <= set(
        actual["no_path_reason_codes"]
    )
    assert _CONFLICT_NOTICE not in actual["notice_codes"]


@pytest.mark.parametrize("product", ["C1", "C6", "D12"])
def test_an_undeclared_overstay_is_asked_never_read_as_zero(
    decide: Any, bases: dict[str, Facts], product: str
) -> None:
    actual = decide(_with(bases[product], immigration__overstay_days=_UNKNOWN))
    assert actual["state"] == "NEEDS_INPUT"
    assert actual["candidates"] == []
    assert "immigration.overstay_days" in actual["missing_facts"]
