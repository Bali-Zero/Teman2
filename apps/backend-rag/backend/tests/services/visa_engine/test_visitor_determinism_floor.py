"""The Oracle answers every visitor, and holds exactly one of them.

RULED 2026-09-13 (`docs/rules/RULINGS.md`), Zero in two sentences that only
mean something together: *«non va mai a revisione umana ma c'è sempre risposta
deterministica»* and *«1 se ci sono questioni penali, revisione umana»*.

This module is the guard for BOTH halves, and the halves need different kinds
of test, which is why they are separated below rather than folded into one
"it works" assertion:

* the DETERMINISM half is a census claim — replay every gold persona through
  the real public chain and count the review outcomes. A census is the only
  honest instrument here: the failure it guards against is a path nobody
  thought to enumerate, and an example-based test can only ever prove the
  examples somebody did think of;
* the EXCEPTION half is a guilt/innocence pair — a disclosed criminal matter
  MUST still hold (guilt: remove the exception and this goes red), and no
  other disclosure may (innocence: widen the allowlist and this goes red).

Deliberately NOT asserted here: that `DecisionState.HUMAN_REVIEW_REQUIRED` is
unreachable in the engine. It is reachable, it stays reachable, and the ruling
says so — `evaluator.evaluate` still produces it for a REQUIRE_REVIEW rule
unless the caller asks for `review_as_conditions=True`, and rows already in
`visa_decisions` still carry it. The claim under test is narrower and is the
one that matters to a person: nothing a VISITOR is handed says "a human will
look at this" unless a criminal matter was disclosed.

This file is intentionally independent of the walk corpus: the disclosure-flag
fixtures are `vo-h-schema`'s (#6442) to add, and a guard that cannot run until
another PR merges is a guard that does not run. It supplies the flags itself.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from backend.scripts.visa_engine import gold_replay_driver as driver
from backend.services.visa_engine import evaluate_path, evaluator
from backend.services.visa_engine.api_models import DisclosedReviewFlag
from backend.services.visa_engine.bundle import verify_rule_pack
from backend.services.visa_engine.compiler import build_compiled_pack
from backend.services.visa_engine.conditions import (
    CRIMINAL_MATTER_REVIEW_CODE,
    SOURCE_INTEGRITY_HOLD_CODES,
)
from backend.services.visa_engine.enums import ConditionNextStep, DecisionState
from backend.services.visa_engine.evaluate_path import VISITOR_REVIEW_CAUSE_ALLOWLIST
from backend.services.visa_engine.models import Reason

#: Inside `rulepack-prod-020`'s validity window and after seq-21's own
#: `valid_period.from`. Pinned rather than "now" so this file cannot start
#: failing on a calendar boundary nobody changed.
_AS_OF = dt.datetime(2026, 9, 13, 0, 0, tzinfo=dt.timezone.utc)


@pytest.fixture(scope="module")
def compiled() -> Any:
    _pack_path, raw = driver.select_highest_repository_pack(driver.PACKS_DIR)
    verified = verify_rule_pack(
        raw, trust_store=driver._repository_trust_store(), observed_at=_AS_OF
    )
    return build_compiled_pack(verified.pack)


def _visitor_decision(
    persona: Any,
    compiled: Any,
    *,
    extra_flags: tuple[DisclosedReviewFlag, ...] = (),
) -> Any:
    """One persona through the REAL visitor chain.

    `review_as_conditions=True` is not a test convenience: it is the exact
    argument `evaluate_path`'s endpoint passes at line-of-business runtime, so
    a divergence between this test and production is a divergence in one
    literal, greppable place rather than in a reimplemented pipeline.
    """

    request = driver.build_persona_request(persona)
    facts = request.applicant_facts()
    decision = evaluator.evaluate(
        facts,
        compiled,
        effective_at=_AS_OF,
        observed_at=_AS_OF,
        identity_provider=driver._offline_identity_provider,
        review_as_conditions=True,
    )
    return evaluate_path.apply_public_policy_adapters(
        decision,
        facts,
        compiled,
        disclosed_review_flags=tuple(
            sorted({*request.effective_review_flags(), *extra_flags}, key=lambda f: f.value)
        ),
    )


def test_no_gold_persona_reaches_a_visitor_review_outcome(compiled: Any) -> None:
    """The census. Measured 2026-09-13 on `rulepack-prod-020.signed.json`:
    before this window 8 of the 20 gold personas ended in
    `HUMAN_REVIEW_REQUIRED` through this same chain (7 raised by the engine's
    own REQUIRE_REVIEW rules, 1 by `_apply_minor_privacy_hold`); after it, 0.
    """

    held = [
        persona
        for persona in driver.PERSONAS
        if _visitor_decision(persona, compiled).state is DecisionState.HUMAN_REVIEW_REQUIRED
    ]
    assert held == [], (
        "these personas are still handed a human-review outcome with no "
        f"criminal disclosure: {[p.id for p in held]}"
    )


def test_every_persona_outcome_is_one_of_the_three_deterministic_states(
    compiled: Any,
) -> None:
    """Stronger than the census above and for a specific reason: "not review"
    could be satisfied by an outage, and an outage is not an answer either.
    """

    deterministic = {
        DecisionState.SUPPORTED_CANDIDATES,
        DecisionState.NEEDS_INPUT,
        DecisionState.NO_SUPPORTED_PATH,
    }
    offenders = {
        persona.id: _visitor_decision(persona, compiled).state.value
        for persona in driver.PERSONAS
        if _visitor_decision(persona, compiled).state not in deterministic
    }
    assert offenders == {}, offenders


def test_the_visitor_review_allowlist_is_exactly_these_three_causes() -> None:
    """The closed list the ruling pins, written out rather than derived, so a
    fourth way to say "a human will look at this" has to be a deliberate edit
    to THIS line and cannot arrive as a side effect somewhere else.

    Two kinds, and the difference is the whole design: ONE visitor disclosure
    (Zero's criminal-matter exception) and TWO engine-integrity failures,
    where the citation under the verdict has gone away. Freshness is
    deliberately NOT here — a source we have not re-verified recently enough
    is still the law, and holding a proven verdict over our own overdue
    paperwork is the behaviour this window removed.
    """

    assert VISITOR_REVIEW_CAUSE_ALLOWLIST == {
        "CRIMINAL_MATTER_DISCLOSED",
        "DECISIVE_PRIMARY_SOURCE_NOT_APPLICABLE",
        "SAFETY_CRITICAL_PRIMARY_SOURCE_NOT_APPLICABLE",
    }
    assert CRIMINAL_MATTER_REVIEW_CODE in VISITOR_REVIEW_CAUSE_ALLOWLIST
    assert SOURCE_INTEGRITY_HOLD_CODES < VISITOR_REVIEW_CAUSE_ALLOWLIST
    stale = {
        "DECISIVE_SOURCE_STALE",
        "DECISIVE_SOURCE_FRESHNESS_UNKNOWN",
        "SAFETY_CRITICAL_SOURCE_STALE",
        "SAFETY_CRITICAL_SOURCE_FRESHNESS_UNKNOWN",
    }
    assert stale.isdisjoint(VISITOR_REVIEW_CAUSE_ALLOWLIST)


def test_a_disclosed_criminal_matter_still_holds_and_explains_itself(
    compiled: Any,
) -> None:
    """GUILT for the exception. Persona 11 is a clean remote worker who is
    SUPPORTED on E33G with no disclosure at all — so everything this test sees
    is caused by the flag it adds, not by the persona's own facts.
    """

    persona = next(p for p in driver.PERSONAS if p.id == 11)
    clean = _visitor_decision(persona, compiled)
    assert clean.state is DecisionState.SUPPORTED_CANDIDATES

    held = _visitor_decision(persona, compiled, extra_flags=(DisclosedReviewFlag.CRIMINAL_RECORD,))
    assert held.state is DecisionState.HUMAN_REVIEW_REQUIRED
    assert [reason.code for reason in held.review_reasons] == [CRIMINAL_MATTER_REVIEW_CODE]
    # The hold is EXPLAINED, which is the half of the exception that is easy
    # to lose: a bare `HUMAN_REVIEW_REQUIRED` would satisfy the state
    # assertion above and still be the shutter Zero asked us to remove.
    criminal = [c for c in held.conditions if c.code == CRIMINAL_MATTER_REVIEW_CODE]
    assert len(criminal) == 1
    assert criminal[0].next_step is ConditionNextStep.CONSULTANT_REVIEW
    # A disclosure is not a regulatory claim and must never borrow a citation.
    assert criminal[0].source_refs == ()


@pytest.mark.parametrize(
    "flag",
    [
        DisclosedReviewFlag.HEALTH_CONCERN,
        DisclosedReviewFlag.PRIOR_VISA_REFUSAL,
        DisclosedReviewFlag.PEP_OR_SANCTIONS,
        DisclosedReviewFlag.SOURCE_OF_FUNDS_UNCLEAR,
        DisclosedReviewFlag.DIPLOMATIC_PASSPORT,
        DisclosedReviewFlag.NOT_CERTAIN,
        DisclosedReviewFlag.MULTI_PURPOSE_TRIP,
        DisclosedReviewFlag.ACTIVITY_BOUNDARY,
        DisclosedReviewFlag.AMBIGUOUS_SPONSOR,
        DisclosedReviewFlag.CONFLICTING_IMMIGRATION_STATUS,
    ],
)
def test_no_other_disclosure_deletes_the_verdict(compiled: Any, flag: DisclosedReviewFlag) -> None:
    """INNOCENCE for the exception, and the measured heart of this window.

    Every one of these flags used to empty `candidates`, `quotes` and
    `missing_facts` and return a hold. Each must now leave the verdict exactly
    where it was and add one named condition instead. The candidate list is
    compared element-by-element, not by length: "still SUPPORTED, but with
    different products" would be a worse failure than a hold, and a length
    check would pass it.
    """

    persona = next(p for p in driver.PERSONAS if p.id == 11)
    clean = _visitor_decision(persona, compiled)
    flagged = _visitor_decision(persona, compiled, extra_flags=(flag,))

    assert flagged.state is clean.state
    assert [c.product_code for c in flagged.candidates] == [
        c.product_code for c in clean.candidates
    ]
    added = {c.code for c in flagged.conditions} - {c.code for c in clean.conditions}
    assert len(added) == 1, added
    condition = next(c for c in flagged.conditions if c.code in added)
    assert condition.explanation_key.startswith("oracle.condition.")
    assert condition.source_refs == ()


def test_the_floor_converts_an_engine_mode_review_for_an_offline_caller(
    compiled: Any,
) -> None:
    """The NET, tested as a net. An offline caller (`gold_coverage_eval`,
    `gold_replay_driver`) evaluates in the engine's default mode, so a
    REQUIRE_REVIEW rule can still hand `apply_public_policy_adapters` a review
    decision — and it must not come out the other side.

    Persona 4 is the fixture because it is a REAL engine-raised review
    (`ACTIVE_OVERSTAY`, a GLOBAL rule), not a synthetic one: if the pack ever
    stops raising it, this test's own premise assertion fails loudly instead
    of the test quietly passing on a decision that was never held.
    """

    persona = next(p for p in driver.PERSONAS if p.id == 4)
    request = driver.build_persona_request(persona)
    facts = request.applicant_facts()
    raw = evaluator.evaluate(
        facts,
        compiled,
        effective_at=_AS_OF,
        observed_at=_AS_OF,
        identity_provider=driver._offline_identity_provider,
    )
    assert raw.state is DecisionState.HUMAN_REVIEW_REQUIRED, "premise lost: see docstring"

    public = evaluate_path.apply_public_policy_adapters(
        raw, facts, compiled, disclosed_review_flags=request.effective_review_flags()
    )
    assert public.state is DecisionState.NO_SUPPORTED_PATH
    assert {c.code for c in public.conditions} == {r.code for r in raw.review_reasons}


def test_an_allowlisted_hold_survives_a_non_allowlisted_cause_beside_it(
    compiled: Any,
) -> None:
    """Council round 1: a review carrying BOTH an allowlisted and a
    non-allowlisted cause must keep the hold on the allowlisted one, never be
    converted wholesale. Persona 4 is a real engine-mode review
    (ACTIVE_OVERSTAY); the criminal cause is added beside it by hand, the
    shape an offline caller could produce."""

    persona = next(p for p in driver.PERSONAS if p.id == 4)
    facts = driver.build_persona_request(persona).applicant_facts()
    raw = evaluator.evaluate(
        facts,
        compiled,
        effective_at=_AS_OF,
        observed_at=_AS_OF,
        identity_provider=driver._offline_identity_provider,
    )
    assert raw.state is DecisionState.HUMAN_REVIEW_REQUIRED, "premise lost"
    mixed = raw.model_copy(
        update={
            "review_reasons": (
                *raw.review_reasons,
                Reason(code=CRIMINAL_MATTER_REVIEW_CODE, rule_ids=(), source_refs=()),
            )
        }
    )
    floored = evaluate_path._apply_visitor_determinism_floor(mixed)
    assert floored.state is DecisionState.HUMAN_REVIEW_REQUIRED
    assert [r.code for r in floored.review_reasons] == [CRIMINAL_MATTER_REVIEW_CODE]
    assert {r.code for r in raw.review_reasons} <= {c.code for c in floored.conditions}


def test_a_criminal_hold_keeps_the_review_causes_it_replaces_as_conditions(
    compiled: Any,
) -> None:
    """Council round 2: an engine-mode review (persona 4, ACTIVE_OVERSTAY)
    that also discloses a criminal matter must hold on the criminal cause and
    still NAME the review cause it replaces, never drop it."""

    persona = next(p for p in driver.PERSONAS if p.id == 4)
    facts = driver.build_persona_request(persona).applicant_facts()
    raw = evaluator.evaluate(
        facts,
        compiled,
        effective_at=_AS_OF,
        observed_at=_AS_OF,
        identity_provider=driver._offline_identity_provider,
    )
    assert raw.state is DecisionState.HUMAN_REVIEW_REQUIRED, "premise lost"
    held = evaluate_path._apply_disclosed_review_flags(raw, (DisclosedReviewFlag.CRIMINAL_RECORD,))
    assert held.state is DecisionState.HUMAN_REVIEW_REQUIRED
    assert [r.code for r in held.review_reasons] == [CRIMINAL_MATTER_REVIEW_CODE]
    assert {r.code for r in raw.review_reasons} <= {c.code for c in held.conditions}


def test_a_review_rule_named_as_a_condition_is_an_applied_effect_in_the_trace(
    compiled: Any,
) -> None:
    """Council round 3: under ``review_as_conditions`` a per-product review
    rule that fires becomes a condition; the evaluation trace (whose digest is
    ``trace_sha256``) must record it as applied, never as a rule that fired
    and did nothing."""

    fired = []
    for persona in driver.PERSONAS:
        facts = driver.build_persona_request(persona).applicant_facts()
        result = evaluator.evaluate_with_trace(
            facts,
            compiled,
            effective_at=_AS_OF,
            observed_at=_AS_OF,
            identity_provider=driver._offline_identity_provider,
            review_as_conditions=True,
        )
        fired.extend(
            node
            for node in result.trace.ordered_nodes
            if node.evaluation_scope == "PRODUCT_PROOF"
            and node.stage.value == "HUMAN_REVIEW"
            and node.condition_result.value == "TRUE"
            # an EXCLUDED proof returns at the hard filter: its review rules
            # were evaluated but never applied, and carry no condition
            and node.product_proof_status != "EXCLUDED"
        )
    assert fired, "premise lost: no gold persona fires a per-product review rule"
    assert [node.rule_id for node in fired if node.applied_effect is None] == []


def test_the_floor_is_the_last_adapter_in_the_chain() -> None:
    """Order is behaviour here. Any adapter running AFTER the floor could hand
    a visitor the review state the floor just removed, so the floor's position
    is part of the guarantee and not a style choice.
    """

    assert evaluate_path.PUBLIC_POLICY_ADAPTER_NAMES[-1] == "_apply_visitor_determinism_floor"
