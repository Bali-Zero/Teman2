"""Named conditions — the deterministic replacement for a human-review verdict.

RULED 2026-09-13 (``docs/rules/RULINGS.md``), Zero verbatim: *«non va mai a
revisione umana ma c'è sempre risposta deterministica»*. Before that ruling the
Visa Oracle had four ways to answer a visitor with "a person will look at
this", and every one of them did the same violent thing on the way out: it
**deleted the verdict the signed pack had already proved** — candidates,
quotes, missing facts, citations, all emptied — and replaced it with a hold.

A condition is the opposite move. The verdict survives; the thing that would
have hidden it is NAMED, in EN and ID, with its own citations and one
explicit next step. Honesty is not preserved by withholding the answer, it is
preserved by saying what still has to be true.

THE ONE PLACE the mapping lives. ``evaluator.py`` (pack rules whose effect is
``REQUIRE_REVIEW``) and ``evaluate_path.py`` (the four public abstention
adapters) both mint conditions, and if each carried its own table they would
drift — the visitor would read one sentence for a stale source raised by the
decisive-source gate and a different one for the same stale source raised by
the safety-critical gate. There is no second table.

WHAT A CONDITION MAY NOT DO, and why the rules are shaped this way:

* it may not carry applicant text. ``explanation_key`` is an i18n KEY resolved
  by the mouth, so no sentence — and therefore no disclosed fact about a
  person — is ever minted into a decision that gets sealed, hashed, persisted
  and replayed;
* it may not borrow a citation. A condition describing an applicant
  DISCLOSURE has no regulatory source, and lending it one from the pack would
  be a false claim of provenance. ``source_refs=()`` on those is deliberate
  and is asserted by a test;
* it may not resurrect a product. Conditions ride on a verdict, they never
  create one. Nothing here can add a candidate.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from types import MappingProxyType

from backend.services.visa_engine.enums import ConditionNextStep
from backend.services.visa_engine.models import DecisionCondition, Reason

#: i18n key namespace. Derived from the code rather than tabulated so a pack
#: that introduces a new reason code still produces a WELL-FORMED condition;
#: the mouth renders an explicit sentence when it knows the key and a generic
#: one naming the code when it does not, so a new code degrades to "less
#: specific", never to "silently dropped".
CONDITION_KEY_PREFIX = "oracle.condition."

#: The ONE review cause a visitor may still receive (Zero, 2026-09-13
#: ~23:05 WITA: «1 se ci sono questioni penali, revisione umana»). Named
#: here, in the conditions module, precisely because this is where every
#: OTHER hold was converted: the exception lives beside the rule it excepts.
CRIMINAL_MATTER_REVIEW_CODE = "CRIMINAL_MATTER_DISCLOSED"

#: The two source-integrity causes that KEEP the hold (RULED 2026-09-13,
#: imperator's binding correction). The distinction is not severity, it is
#: WHOSE problem it is. A source that is merely STALE or of UNKNOWN
#: freshness is still the law — our re-verification of it is overdue, and
#: withholding a proven verdict over our own paperwork would be the exact
#: thing the ruling forbids. A source that is NOT_APPLICABLE has been
#: revoked, superseded, has expired, is not yet in force, is not a primary
#: authority, or does not resolve at all: the verdict then rests on
#: nothing, and there is no honest deterministic answer to give. That is
#: an ENGINE-INTEGRITY failure, not a visitor disclosure, and the applicant
#: is told so rather than handed a recommendation with no floor under it.
SOURCE_INTEGRITY_HOLD_CODES: frozenset[str] = frozenset(
    {
        "DECISIVE_PRIMARY_SOURCE_NOT_APPLICABLE",
        "SAFETY_CRITICAL_PRIMARY_SOURCE_NOT_APPLICABLE",
    }
)

#: Next step per condition code. The DEFAULT is deliberately
#: ``BRING_TO_CONSULTATION`` and not ``NO_ACTION_NEEDED``: an unlisted code is
#: a condition nobody has triaged yet, and the safe reading of an untriaged
#: condition is "a person should see this", never "ignore it".
DEFAULT_NEXT_STEP = ConditionNextStep.BRING_TO_CONSULTATION

_NEXT_STEP_BY_CODE: Mapping[str, ConditionNextStep] = MappingProxyType(
    {
        # --- applicant disclosures (evaluate_path, no citation by design) ---
        # DISCLOSED_CRIMINAL_RECORD_REVIEW is deliberately ABSENT. Zero,
        # 2026-09-13 ~23:05 WITA, verbatim: «1 se ci sono questioni penali,
        # revisione umana». A disclosed criminal matter is the one
        # disclosure that does NOT become a condition — it keeps
        # HUMAN_REVIEW_REQUIRED, under the named cause
        # CRIMINAL_MATTER_DISCLOSED. Putting it back in this table would
        # silently re-open the path the owner closed, so its absence is
        # pinned by a test, not left to a reader noticing a gap.
        # The criminal cause DOES get a next step, because the owner asked
        # for the hold to be EXPLAINED rather than bare: the review reason
        # names the cause, and this condition, minted beside it, carries the
        # EN/ID sentence that says who looks at it and what happens next.
        CRIMINAL_MATTER_REVIEW_CODE: ConditionNextStep.CONSULTANT_REVIEW,
        "DISCLOSED_HEALTH_CONCERN_REVIEW": ConditionNextStep.BRING_TO_CONSULTATION,
        "DISCLOSED_PRIOR_VISA_REFUSAL_REVIEW": ConditionNextStep.BRING_TO_CONSULTATION,
        "DISCLOSED_PEP_OR_SANCTIONS_REVIEW": ConditionNextStep.BRING_TO_CONSULTATION,
        "DISCLOSED_SOURCE_OF_FUNDS_REVIEW": ConditionNextStep.BRING_TO_CONSULTATION,
        "DISCLOSED_DIPLOMATIC_PASSPORT_REVIEW": ConditionNextStep.BRING_TO_CONSULTATION,
        "CONFLICTING_IMMIGRATION_STATUS_REVIEW": ConditionNextStep.BRING_TO_CONSULTATION,
        # An unresolved answer is the one class the TREE can still cure, so it
        # is the one class whose next step is "answer it again".
        "DISCLOSED_UNCERTAINTY_REVIEW": ConditionNextStep.ANSWER_AGAIN,
        "DISCLOSED_AMBIGUOUS_SPONSOR_REVIEW": ConditionNextStep.ANSWER_AGAIN,
        "DISCLOSED_ACTIVITY_BOUNDARY_REVIEW": ConditionNextStep.ANSWER_AGAIN,
        # Two declared purposes are two real purposes, not an error: the
        # candidates below already cover them, so there is nothing to do.
        "DISCLOSED_MULTI_PURPOSE_TRIP_REVIEW": ConditionNextStep.NO_ACTION_NEEDED,
        # --- source integrity and freshness (evaluate_path) ------------------
        # All six keep their ORIGINAL codes rather than collapsing into one
        # SOURCE_REFRESH_PENDING: `engine-adapter.ts` already carries
        # reviewed EN/ID copy for every one of them, and the freshness
        # sentinel and telemetry already read them apart. Renaming would
        # have thrown away working bilingual copy to gain a shorter list.
        "DECISIVE_SOURCE_STALE": ConditionNextStep.AWAIT_SOURCE_REFRESH,
        "DECISIVE_SOURCE_FRESHNESS_UNKNOWN": ConditionNextStep.AWAIT_SOURCE_REFRESH,
        "SAFETY_CRITICAL_SOURCE_STALE": ConditionNextStep.AWAIT_SOURCE_REFRESH,
        "SAFETY_CRITICAL_SOURCE_FRESHNESS_UNKNOWN": (ConditionNextStep.AWAIT_SOURCE_REFRESH),
        "DECISIVE_PRIMARY_SOURCE_NOT_APPLICABLE": ConditionNextStep.AWAIT_SOURCE_REFRESH,
        "SAFETY_CRITICAL_PRIMARY_SOURCE_NOT_APPLICABLE": (ConditionNextStep.AWAIT_SOURCE_REFRESH),
        # --- pack rules whose effect is REQUIRE_REVIEW (evaluator) -----------
        "E28B_USD_THRESHOLD_MANUAL_CHECK": ConditionNextStep.ASSISTED_APPLICATION,
        "E28C_USD_THRESHOLD_AND_INSTRUMENT_CHECK": ConditionNextStep.ASSISTED_APPLICATION,
        "E28D_USD_THRESHOLD_AND_TURNOVER_CHECK": ConditionNextStep.ASSISTED_APPLICATION,
        "E28F_IKN_THRESHOLD_MANUAL_CHECK": ConditionNextStep.ASSISTED_APPLICATION,
        "E33B_EXPERTISE_QUALIFICATION_CHECK": ConditionNextStep.ASSISTED_APPLICATION,
        "E23U_DIPLOMATIC_HOUSEHOLD_STAFF_REVIEW": ConditionNextStep.ASSISTED_APPLICATION,
        "E23V_TRADE_OFFICE_STAFF_REVIEW": ConditionNextStep.ASSISTED_APPLICATION,
        "GOVT_INVITATION_REQUIRED": ConditionNextStep.ASSISTED_APPLICATION,
        "E33_WORK_RANGKAP_KEGIATAN_GATED": ConditionNextStep.ASSISTED_APPLICATION,
        "E33G_EXCLUDES_LOCAL_COMPANY_OWNERSHIP": ConditionNextStep.BRING_TO_CONSULTATION,
        "LOCAL_MARKET_ACTIVITY_REVIEW": ConditionNextStep.BRING_TO_CONSULTATION,
        "ACTIVE_OVERSTAY": ConditionNextStep.BRING_TO_CONSULTATION,
        "CALLING_VISA_REVIEW": ConditionNextStep.BRING_TO_CONSULTATION,
        "CITIZENSHIP_LIST_DIVERGENCE": ConditionNextStep.BRING_TO_CONSULTATION,
        "BRIDGING_ADVERSE_HISTORY": ConditionNextStep.BRING_TO_CONSULTATION,
        "MINOR_WITHOUT_CONFIRMED_GUARDIAN": ConditionNextStep.APPLY_THROUGH_GUARDIAN,
        # The PUBLIC cause `_apply_minor_privacy_hold` mints, as opposed to
        # the pack rule above. Both exist and both must map, or the applicant
        # facing half of the privacy hold silently falls to the untriaged
        # default and tells a parent to "bring it to the consultation".
        "GUARDIAN_MUST_APPLY": ConditionNextStep.APPLY_THROUGH_GUARDIAN,
    }
)


def condition_explanation_key(code: str) -> str:
    """The i18n key for one condition code. Total, deterministic, lowercase."""

    return f"{CONDITION_KEY_PREFIX}{code.lower()}"


def condition_next_step(code: str) -> ConditionNextStep:
    """The declared next step for one code, or the untriaged default."""

    return _NEXT_STEP_BY_CODE.get(code, DEFAULT_NEXT_STEP)


def condition_from_reason(reason: Reason) -> DecisionCondition:
    """Lift one ``Reason`` into a ``DecisionCondition``, citations and rule ids kept.

    Provenance survives the lift on purpose: a condition raised by a signed
    pack rule still points at the rule and the source record that justify it,
    which is what lets the applicant-facing sentence say *who* assesses the
    case and *under what*.
    """

    return DecisionCondition(
        code=reason.code,
        rule_ids=reason.rule_ids,
        source_refs=reason.source_refs,
        explanation_key=condition_explanation_key(reason.code),
        next_step=condition_next_step(reason.code),
    )


def conditions_from_reasons(reasons: Iterable[Reason]) -> tuple[DecisionCondition, ...]:
    """``condition_from_reason`` over a sequence, first-seen order preserved."""

    return tuple(condition_from_reason(reason) for reason in reasons)


def dedupe_conditions(conditions: Iterable[DecisionCondition]) -> tuple[DecisionCondition, ...]:
    """One condition per CODE, first occurrence wins, order preserved.

    Deliberately NOT a union-merge of rule ids the way ``merge_reasons_by_code``
    works for reasons: two conditions sharing a code render the same sentence
    and the same next step, so the second one adds a duplicate paragraph to the
    applicant and nothing else. Order is the caller's (global first, then
    per-product) so the rendering is stable across replays.
    """

    seen: set[str] = set()
    out: list[DecisionCondition] = []
    for condition in conditions:
        if condition.code in seen:
            continue
        seen.add(condition.code)
        out.append(condition)
    return tuple(out)


__all__ = [
    "CONDITION_KEY_PREFIX",
    "CRIMINAL_MATTER_REVIEW_CODE",
    "DEFAULT_NEXT_STEP",
    "SOURCE_INTEGRITY_HOLD_CODES",
    "condition_explanation_key",
    "condition_from_reason",
    "condition_next_step",
    "conditions_from_reasons",
    "dedupe_conditions",
]
