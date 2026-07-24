"""The gold RulePack + persona-facts builders for the PR5 evaluator acceptance
suite (``test_evaluator_gold_personas.py``).

Not collected as tests (no ``test_`` prefix / no test functions) — same
convention as ``_builders.py``.

Builds ONE canonical RulePack covering 5 products (C1 tourism, E23 employment,
E31 family, E33G remote-work, E28A investment) and every rule the 20 gold
personas in ``research/visa/2026-07-17-visa-oracle-v2-round2-codex-engine-
concretization.md`` §7 exercise. These are synthetic engine-test policy
(spec's own §7 framing: "Gold fixture constants are synthetic engine-test
policy, not production Indonesian legal assertions") — the specific
thresholds/roles/conditions below exist to make the 20 personas resolve to
their documented expected states, not to encode real Bali Zero legal advice.

# Design notes (why the rules look the way they do)

- **A product's own ``covered_purposes`` deliberately includes TOURISM for
  every limited-stay product** (E23/E31/E33G/E28A all declare
  ``[<primary>, "TOURISM"]``, never just ``[<primary>]``) — a KITAS-class
  permit holder is not barred from ordinary tourism activity, so a combined
  purpose set like ``["TOURISM","REMOTE_WORK"]`` can be fully covered by a
  SINGLE product (E33G) without needing two separate candidates. This is
  what makes personas 14/15 resolve to exactly one candidate ("never C1")
  rather than either an impossible multi-product SUPPORTED_CANDIDATES or an
  UNSUPPORTED outcome. C1 itself covers ONLY TOURISM — a bare short-stay
  visa does not extend to any other purpose.
- **Every specific disqualifying condition is modeled as a named
  HARD_FILTER (EXCLUDE) or HUMAN_REVIEW (REQUIRE_REVIEW) rule with its own
  ``reason_code``**, never left as a bare "no rule supported this purpose"
  gap — this is what gives personas 9/16 (NO_SUPPORTED_PATH) a specific,
  cited reason (``DIRECT_ONSHORE_CONVERSION_UNSUPPORTED``/
  ``INVESTMENT_CAPITAL_BELOW_FIXTURE_MINIMUM``) instead of an uninformative
  fallback. ``evaluator._NO_PRODUCT_SUPPORTS_DECLARED_PURPOSES`` (the
  evaluator's own fallback) is never reached by any of the 20 personas —
  it exists only for a genuinely rule-less pack (see
  ``test_evaluator_edge_cases.py``).
- **``hf.onshore-gate`` is a narrow, single-persona-scoped fixture rule**
  (persona 20 only): it forces BOTH ``immigration.current_status_code`` and
  ``immigration.overstay_days`` into a rule's ``unknown_facts`` via an
  ``eq(fact, <impossible sentinel>)`` comparison (never TRUE for a real
  known value, genuinely UNKNOWN when the fact itself is unknown) — this is
  a legitimate "force this fact into the tri-state evaluation as a
  comparison, not a presence check" pattern, but combined under a single
  Kleene ``all`` it only reliably surfaces BOTH facts when BOTH are
  unknown *simultaneously* (Kleene ``all`` is FALSE-dominant: if only one
  of the two sentinel comparisons is FALSE — i.e. that one fact is
  known — the whole rule is FALSE, not UNKNOWN, and the OTHER fact's
  unknown-ness is not surfaced via *this* rule alone). Persona 20 needs
  exactly the both-unknown-together case, so this narrower shape is
  sufficient for it; a real production rule pack would author two
  independent single-fact gates instead. ``immigration.overstay_days``
  alone is independently covered by ``review.active-overstay`` regardless
  of this rule.

# Gate round 1 (2026-07-19) — per-persona distinguishing-fact influence audit

The gate flagged 6 personas whose stated "distinguishing fact" did not
actually drive their outcome (a metamorphic flip of that fact left the
result unchanged). Disposition per persona, fixed where fixing was the
correct/safe move and documented as intentional otherwise:

- **#6 ``family.sponsor_status_code``** and **#7
  ``family.sponsor_nationalities``**: FIXED — ``el.e31.family`` now requires
  the CHILD branch's sponsor to hold a status in a small fixture allow-list
  (``in(family.sponsor_status_code, ["E23","E28A"])``) and the SPOUSE
  branch's sponsor to include Indonesian nationality
  (``intersects(family.sponsor_nationalities, ["ID"])``). Both personas'
  own fact values already satisfy the new constraint (no persona-6/7
  regression); flipping either fact now genuinely changes the outcome (see
  ``test_evaluator_gold.py``'s metamorphic differential tests).
- **#8 "does not really replicate #7"**: FIXED, twice. Round 1 fixed the
  first cause (persona 8's overrides omitted ``family.sponsor_nationalities``,
  silently falling back to the shared baseline's UNKNOWN and inflating
  ``expected_missing``) but introduced a SECOND one: it added an explicit
  ``family.sponsor_status_code`` override to neutralize a dead-branch
  unknown-fact leak (round-1's own P0-A-adjacent CHILD-branch wiring meant
  persona 8's SPOUSE-path result unioned in the CHILD branch's own unknown
  leaf) — which made persona 8 differ from #7 by TWO facts, not the one it
  claims to test. Gate round 2 parziale item 2 fixes the ROOT CAUSE instead
  of masking it on persona 8's side: the shared baseline's
  ``family.sponsor_status_code`` is now a concrete ``KNOWN("NONE")``
  sentinel (guaranteed outside the CHILD branch's allow-list) rather than
  UNKNOWN, so the dead-branch leak cannot happen for ANY persona that
  doesn't explicitly ask for it (persona 6 still does, to test the CHILD
  path itself). Persona 8's overrides no longer need the extra fact at
  all — it is now a genuine, pure single-fact differential from #7
  (``family.marriage_registered`` only).
- **#11 ``work.employer_country_code``**: NOT wired into any rule —
  documented, not fixed. ``el.e33g.remote-work`` already gates on
  ``work.employer_is_indonesian_entity`` (a boolean derived from the same
  underlying fact in any real pack); adding a second, redundant condition on
  the raw country code here would either duplicate that check pointlessly or
  invent an untested, uncalibrated legal constraint (e.g. "which specific
  countries count") this synthetic engine-test fixture has no basis for
  asserting. The fact stays in persona 11's overrides as case-narrative
  context (the persona's prose names a country), not as a rule input.
- **#17 ``commercial.service_fee_budget_idr``**: FIXED via ``rank.budget-
  covers-fee`` below — this fact is *supposed* to influence RANKING only,
  never eligibility (spec §4.4, this persona's own label: "low budget never
  filters") — wiring it into a dedicated ranking rule makes it genuinely
  influential on ``Candidate.score`` while leaving the legal SUPPORTED/
  UNSUPPORTED state untouched, which is a MORE precise demonstration of the
  claim than an inert fact would be (see the differential ranking tests).
- **#20 impossible sentinels**: NOT changed (fixture/rule), documentation
  CORRECTED (gate round 2, 2026-07-20 — Codex sol xhigh's EXECUTED probe
  found the round-1 claim below false). Round 1 claimed "flipping EITHER
  ``immigration.current_status_code`` or ``immigration.overstay_days`` to
  KNOWN changes the outcome away from NEEDS_INPUT" — that is true for
  ``overstay_days`` alone (``eq(overstay_days, <impossible sentinel>)``
  becomes a definite FALSE, so the whole ``_all`` inside ``hf.onshore-gate``
  resolves FALSE regardless of ``current_status_code`` still being
  UNKNOWN, and nothing else in this pack makes ``current_status_code``'s
  unknown-ness surface on its own — the state resolves all the way to
  ``SUPPORTED_CANDIDATES`` on C1) but FALSE for ``current_status_code``
  alone (knowing only that value still leaves ``overstay_days`` itself
  unknown and required, so the state stays ``NEEDS_INPUT`` — only its
  ``missing_facts`` set shrinks from both facts down to
  ``overstay_days`` alone). Both facts ARE genuinely influential on the
  MISSING-FACTS set either way; only ``overstay_days`` (alone, or paired
  with ``current_status_code``) is influential on the STATE itself. See
  ``test_evaluator_gold.py``'s persona-20 asymmetric-influence regression
  test for the exact 4-way empirical matrix (both unknown / status-only
  known / overstay-only known / both known).
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from backend.services.visa_engine import ast as ast_module
from backend.services.visa_engine import models as M
from backend.services.visa_engine.compiler import CompiledRulePack, build_compiled_pack

GOLD_EFFECTIVE_AT = datetime(2026, 7, 17, 0, 0, 0, tzinfo=timezone.utc)
GOLD_CALLING_COUNTRIES: tuple[str, ...] = ("AF",)
GOLD_INVESTOR_MIN_IDR = 10_000_000_000

_OPEN_PERIOD = {"from": GOLD_EFFECTIVE_AT, "to": None}

#: Fixed namespace for deterministic UUID generation — readable, stable
#: across test runs, never meant as a secret.
_NS = uuid.UUID("11111111-1111-1111-1111-111111111111")


def _id(label: str) -> uuid.UUID:
    return uuid.uuid5(_NS, label)


SOURCE_ID = _id("source.gold-v1")

PRODUCT_CODES = ("C1", "E23", "E31", "E33G", "E28A")
PRODUCT_IDS: Mapping[str, uuid.UUID] = {code: _id(f"product.{code}") for code in PRODUCT_CODES}


def _source_record() -> dict[str, Any]:
    return {
        "source_record_id": str(SOURCE_ID),
        "source_key": "gold.synthetic.v1",
        "version": 1,
        "authority_type": "BALI_ZERO_POLICY",
        "status": "VERIFIED",
        "jurisdiction": "ID",
        "title": "Gold harness synthetic policy (engine-test only)",
        "publisher": "Bali Zero engineering",
        "canonical_url": "https://example.invalid/gold-v1",
        "language": "en",
        "document_number": None,
        "locators": [],
        "content_sha256": "a" * 64,
        "legal_period": _OPEN_PERIOD,
        "recorded_period": _OPEN_PERIOD,
        "retrieved_at": GOLD_EFFECTIVE_AT,
        "verified_at": GOLD_EFFECTIVE_AT,
        "verified_by": "gold.harness",
        "supersedes_source_record_id": None,
    }


def _product(
    *,
    code: str,
    covered_purposes: Sequence[str],
    legacy_codes: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "product_version_id": str(PRODUCT_IDS[code]),
        "product_code": code,
        "legacy_codes": list(legacy_codes),
        "legacy_slugs": [],
        "names": {"id": f"Visa {code}", "en": f"{code} visa"},
        "category": "SHORT_STAY" if code == "C1" else "LIMITED_STAY",
        "status": "ACTIVE",
        "valid_period": _OPEN_PERIOD,
        "covered_purposes": list(covered_purposes),
        "prohibited_activities": [],
        "sponsor_types": ["NONE"],
        "entry_policy": {"entry_count": "MULTIPLE"},
        "stay_policy": {"kind": "FIXED_DAYS", "minimum_days": 1, "maximum_days": 365},
        "extension_policy": {"allowed": True, "maximum_extensions": 1, "days_per_extension": 30},
        "clock_policy": {"available": False, "anchor": "NOT_APPLICABLE", "checkpoints": []},
        "pricing_key": {"category": "visa", "item_key": f"{code.lower()}_gold"},
        "source_refs": [str(SOURCE_ID)],
        "public_catalog": True,
    }


def _when_and_facts(condition: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Parse ``condition`` and compute its ``required_facts`` via
    ``ast.collect_fact_paths`` — avoids hand-enumerating/duplicating fact
    paths per rule (and the drift-prone ``REQUIRED_FACTS_MISMATCH`` bugs
    that duplication invites)."""
    parsed = ast_module.parse_condition(condition)
    return condition, sorted(ast_module.collect_fact_paths(parsed))


def _rule(
    *,
    rule_id: str,
    stage: str,
    scope: str,
    when: dict[str, Any],
    effect: dict[str, Any],
    on_unknown: str = "NEEDS_INPUT",
    product_codes: Sequence[str] = (),
    safety_critical: bool = False,
    priority: int = 100,
) -> dict[str, Any]:
    condition, required_facts = _when_and_facts(when)
    rule: dict[str, Any] = {
        "rule_id": rule_id,
        "stage": stage,
        "scope": scope,
        "priority": priority,
        "valid_period": _OPEN_PERIOD,
        "when": condition,
        "effect": effect,
        "on_unknown": on_unknown,
        "required_facts": required_facts,
        "source_refs": [str(SOURCE_ID)],
        "explanation_key": f"{rule_id}.explanation",
        "safety_critical": safety_critical,
    }
    if scope == "PRODUCTS":
        rule["product_version_ids"] = [str(PRODUCT_IDS[code]) for code in product_codes]
    return rule


def _exclude(reason_code: str) -> dict[str, str]:
    return {"type": "EXCLUDE", "reason_code": reason_code}


def _review(reason_code: str) -> dict[str, str]:
    return {"type": "REQUIRE_REVIEW", "reason_code": reason_code}


def _support(reason_code: str, covered_purposes: Sequence[str]) -> dict[str, Any]:
    return {
        "type": "SUPPORT",
        "reason_code": reason_code,
        "covered_purposes": list(covered_purposes),
    }


def _add_score(reason_code: str, points: int) -> dict[str, Any]:
    return {"type": "ADD_SCORE", "reason_code": reason_code, "points": points}


def _all(*args: dict[str, Any]) -> dict[str, Any]:
    return {"op": "all", "args": list(args)}


def _any(*args: dict[str, Any]) -> dict[str, Any]:
    return {"op": "any", "args": list(args)}


def _eq(fact: str, value: Any) -> dict[str, Any]:
    return {"op": "eq", "fact": fact, "value": value}


def _neq(fact: str, value: Any) -> dict[str, Any]:
    return {"op": "neq", "fact": fact, "value": value}


def _gt(fact: str, value: Any) -> dict[str, Any]:
    return {"op": "gt", "fact": fact, "value": value}


def _gte(fact: str, value: Any) -> dict[str, Any]:
    return {"op": "gte", "fact": fact, "value": value}


def _lt(fact: str, value: Any) -> dict[str, Any]:
    return {"op": "lt", "fact": fact, "value": value}


def _lte(fact: str, value: Any) -> dict[str, Any]:
    return {"op": "lte", "fact": fact, "value": value}


def _in(fact: str, values: Sequence[Any]) -> dict[str, Any]:
    return {"op": "in", "fact": fact, "values": list(values)}


def _intersects(fact: str, values: Sequence[Any]) -> dict[str, Any]:
    return {"op": "intersects", "fact": fact, "values": list(values)}


def _unknown(fact: str) -> dict[str, Any]:
    return {"op": "unknown", "fact": fact}


def _build_rules() -> list[dict[str, Any]]:
    return [
        # --- GLOBAL hard filters --------------------------------------------------
        _rule(
            rule_id="hf.citizen",
            stage="HARD_FILTER",
            scope="GLOBAL",
            when=_eq("derived.has_indonesian_citizenship", True),
            effect=_exclude("APPLICANT_IS_INDONESIAN_CITIZEN"),
            safety_critical=True,
        ),
        _rule(
            rule_id="hf.onshore-gate",
            stage="HARD_FILTER",
            scope="GLOBAL",
            when=_all(
                _eq("immigration.currently_in_indonesia", True),
                _eq("process.wants_onshore_conversion", True),
                _eq("immigration.overstay_days", -1),
                _eq("immigration.current_status_code", "NONE"),
            ),
            effect=_exclude("ONSHORE_CONVERSION_REQUIRES_CURRENT_STATUS"),
            safety_critical=True,
        ),
        # --- GLOBAL human-review triggers ------------------------------------------
        _rule(
            rule_id="review.citizenship-conflict",
            stage="HUMAN_REVIEW",
            scope="GLOBAL",
            when=_unknown("person.nationalities"),
            effect=_review("CITIZENSHIP_EVIDENCE_CONFLICT"),
            on_unknown="NO_EFFECT",
            safety_critical=True,
        ),
        _rule(
            rule_id="review.calling-visa",
            stage="HUMAN_REVIEW",
            scope="GLOBAL",
            when=_intersects("person.nationalities", list(GOLD_CALLING_COUNTRIES)),
            effect=_review("CALLING_VISA_REVIEW"),
            safety_critical=True,
        ),
        _rule(
            rule_id="review.active-overstay",
            stage="HUMAN_REVIEW",
            scope="GLOBAL",
            when=_gt("immigration.overstay_days", 0),
            effect=_review("ACTIVE_OVERSTAY"),
            safety_critical=True,
        ),
        _rule(
            rule_id="review.minor-no-guardian",
            stage="HUMAN_REVIEW",
            scope="GLOBAL",
            when=_all(
                _eq("derived.is_minor", True),
                _eq("family.sponsor_confirmed", False),
            ),
            effect=_review("MINOR_WITHOUT_CONFIRMED_GUARDIAN"),
            safety_critical=True,
        ),
        # --- E28A (investment) -----------------------------------------------------
        _rule(
            rule_id="hf.e28a.onshore-conversion",
            stage="HARD_FILTER",
            scope="PRODUCTS",
            product_codes=("E28A",),
            when=_all(
                _intersects("intent.purposes", ["INVESTMENT"]),
                _eq("process.application_channel", "ONSHORE_CONVERSION"),
            ),
            effect=_exclude("DIRECT_ONSHORE_CONVERSION_UNSUPPORTED"),
        ),
        _rule(
            rule_id="hf.e28a.capital-below-min",
            stage="HARD_FILTER",
            scope="PRODUCTS",
            product_codes=("E28A",),
            when=_all(
                _intersects("intent.purposes", ["INVESTMENT"]),
                _lt("investment.investment_capital_idr", GOLD_INVESTOR_MIN_IDR),
            ),
            effect=_exclude("INVESTMENT_CAPITAL_BELOW_FIXTURE_MINIMUM"),
        ),
        _rule(
            rule_id="review.e28a.status-bridging",
            stage="HUMAN_REVIEW",
            scope="PRODUCTS",
            product_codes=("E28A",),
            when=_all(
                _intersects("intent.purposes", ["INVESTMENT"]),
                _eq("process.application_channel", "STATUS_BRIDGING"),
            ),
            effect=_review("STATUS_BRIDGING_REVIEW"),
        ),
        _rule(
            rule_id="el.e28a.investment",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_codes=("E28A",),
            when=_all(
                _intersects("intent.purposes", ["INVESTMENT"]),
                _gte("investment.investment_capital_idr", GOLD_INVESTOR_MIN_IDR),
                _eq("investment.pt_pma_committed", True),
                _in(
                    "investment.proposed_role",
                    ["SHAREHOLDER_DIRECTOR", "SHAREHOLDER_COMMISSIONER"],
                ),
            ),
            effect=_support("INVESTMENT_ELIGIBLE", ["INVESTMENT", "TOURISM"]),
        ),
        # --- E31 (family) ------------------------------------------------------------
        # Gate round 1 (2026-07-19): CHILD branch now requires the sponsor to
        # hold a status in this fixture allow-list (persona 6's
        # ``family.sponsor_status_code`` distinguishing fact — previously
        # unwired, see module docstring); SPOUSE branch now requires an
        # Indonesian-national sponsor (persona 7's
        # ``family.sponsor_nationalities`` distinguishing fact — same
        # reason).
        _rule(
            rule_id="el.e31.family",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_codes=("E31",),
            when=_any(
                _all(
                    _intersects("intent.purposes", ["FAMILY"]),
                    _eq("family.relation_to_sponsor", "CHILD"),
                    _in("family.sponsor_status_code", ["E23", "E28A"]),
                    _eq("family.sponsor_confirmed", True),
                ),
                _all(
                    _intersects("intent.purposes", ["FAMILY"]),
                    _eq("family.relation_to_sponsor", "SPOUSE"),
                    _intersects("family.sponsor_nationalities", ["ID"]),
                    _eq("family.marriage_registered", True),
                    _eq("family.sponsor_confirmed", True),
                ),
            ),
            effect=_support("FAMILY_ELIGIBLE", ["FAMILY", "TOURISM"]),
        ),
        # --- E23 (employment) --------------------------------------------------------
        _rule(
            rule_id="el.e23.employment",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_codes=("E23",),
            when=_all(
                _intersects("intent.purposes", ["EMPLOYMENT"]),
                _eq("work.employer_is_indonesian_entity", True),
                _eq("work.indonesian_work_sponsor_confirmed", True),
            ),
            effect=_support("EMPLOYMENT_ELIGIBLE", ["EMPLOYMENT", "TOURISM"]),
        ),
        # --- E33G (remote work) -------------------------------------------------------
        _rule(
            rule_id="el.e33g.remote-work",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_codes=("E33G",),
            when=_all(
                _intersects("intent.purposes", ["REMOTE_WORK"]),
                _eq("work.employer_is_indonesian_entity", False),
                _eq("work.serves_indonesian_clients", False),
                _eq("work.indonesia_source_compensation", False),
            ),
            effect=_support("REMOTE_WORK_ELIGIBLE", ["REMOTE_WORK", "TOURISM"]),
        ),
        _rule(
            rule_id="review.e33g.local-market",
            stage="HUMAN_REVIEW",
            scope="PRODUCTS",
            product_codes=("E33G",),
            when=_all(
                _intersects("intent.purposes", ["REMOTE_WORK"]),
                _eq("work.serves_indonesian_clients", True),
            ),
            effect=_review("LOCAL_MARKET_ACTIVITY_REVIEW"),
        ),
        # --- C1 (tourism) --------------------------------------------------------------
        _rule(
            rule_id="el.c1.tourism",
            stage="ELIGIBILITY",
            scope="PRODUCTS",
            product_codes=("C1",),
            when=_all(
                _intersects("intent.purposes", ["TOURISM"]),
                _lte("intent.stay_days", 30),
            ),
            effect=_support("TOURISM_ELIGIBLE", ["TOURISM"]),
        ),
        # --- GLOBAL ranking (commercial budget never filters, spec §4.4) --------------
        # Gate round 1 fix (2026-07-19): the boost must bind to the VALUE
        # (wants a quote), not mere presence of an answer — the previous
        # `{"op": "known", ...}` fired the boost even when the applicant had
        # explicitly answered False, which is not "wants a quote" at all.
        _rule(
            rule_id="rank.wants-quote",
            stage="RANKING",
            scope="GLOBAL",
            when=_eq("commercial.wants_quote", True),
            effect=_add_score("WANTS_QUOTE_BOOST", 5),
            on_unknown="NO_EFFECT",
        ),
        # Gate round 1 addition (2026-07-19, persona 17 fix): wires
        # `commercial.service_fee_budget_idr` into ranking-only influence —
        # never eligibility (see module docstring's per-persona audit).
        _rule(
            rule_id="rank.budget-covers-fee",
            stage="RANKING",
            scope="GLOBAL",
            when=_gte("commercial.service_fee_budget_idr", 1_000_000),
            effect=_add_score("BUDGET_COVERS_FEE", 3),
            on_unknown="NO_EFFECT",
        ),
    ]


def _products() -> list[dict[str, Any]]:
    return [
        _product(code="C1", covered_purposes=["TOURISM"], legacy_codes=["B211A"]),
        _product(code="E23", covered_purposes=["EMPLOYMENT", "TOURISM"]),
        _product(code="E31", covered_purposes=["FAMILY", "TOURISM"]),
        _product(code="E33G", covered_purposes=["REMOTE_WORK", "TOURISM"]),
        _product(code="E28A", covered_purposes=["INVESTMENT", "TOURISM"]),
    ]


def build_gold_rule_pack() -> M.RulePack:
    """Build + Pydantic-validate the full gold RulePack envelope (unsigned —
    signature/trust verification is ``bundle.py``'s PR2 concern, orthogonal
    to the evaluator this fixture feeds; ``compiler.compile_rule_pack`` takes
    a plain ``models.RulePack``, never a ``bundle.VerifiedRulePack``)."""
    payload = {
        "rule_pack_id": str(_id("rule_pack.gold-v1")),
        "sequence": 1,
        "version": "1.0.0",
        "environment": "TEST",
        "jurisdiction": "ID",
        "decision_domain": "IMMIGRATION_VISA",
        "engine_contract_version": "1.0.0",
        "engine_min_version": "1.0.0",
        "engine_max_version": "1.0.0",
        "valid_period": _OPEN_PERIOD,
        "created_at": GOLD_EFFECTIVE_AT,
        "created_by": "gold.harness",
        "previous_payload_sha256": None,
        "rollback_of_payload_sha256": None,
        "hit_policy": {
            "hard_filter": "COLLECT_ALL",
            "eligibility": "COVER_ALL_DECLARED_PURPOSES",
            "human_review": "COLLECT_ALL",
            "ranking": "SUM_TRUE_INTEGER_WEIGHTS",
        },
        "source_records": [_source_record()],
        "products": _products(),
        "rules": _build_rules(),
    }
    envelope = {
        "canonicalization": "RFC8785",
        "protected": {
            "domain": "balizero.visa-rulepack.v1",
            "alg": "Ed25519",
            "kid": "gold-harness-key-1",
            "signed_at": GOLD_EFFECTIVE_AT,
            "schema_version": "1.0.0",
            "environment": "TEST",
        },
        "payload": payload,
        "payload_sha256": "b" * 64,
        "signature": "c" * 86,
    }
    return M.RulePack.model_validate(envelope)


def build_gold_compiled_pack() -> CompiledRulePack:
    return build_compiled_pack(build_gold_rule_pack())


# ---------------------------------------------------------------------------
# ApplicantFacts persona builder
# ---------------------------------------------------------------------------

_UNKNOWN_NOT_ASKED = {"status": "UNKNOWN", "reason": "NOT_ASKED"}

#: Every one of the 40 fact paths defaulted to a KNOWN, "safe/neutral" value —
#: a fully-answered, boring baseline applicant (adult, non-calling-country,
#: no violations, offshore, non-onshore-conversion) that no rule in
#: ``_build_rules`` flags. Every persona overrides only its OWN distinguishing
#: facts on top of this baseline (never inherits an UNKNOWN by omission,
#: matching spec §7's "no inheritance or hidden defaults" framing for the
#: real gold fixture — here relaxed to a single shared safe baseline since
#: PR5 authors these personas itself rather than loading a JSON fixture).
_BASELINE_FACTS: dict[str, dict[str, Any]] = {
    "person.birth_date": {"status": "KNOWN", "value": "1990-01-01"},
    "person.nationalities": {"status": "KNOWN", "value": ["FR"]},
    "person.marital_status": {"status": "KNOWN", "value": "SINGLE"},
    "immigration.currently_in_indonesia": {"status": "KNOWN", "value": False},
    "immigration.current_status_code": {"status": "KNOWN", "value": "NONE_ISSUED"},
    "immigration.current_status_expiry": _UNKNOWN_NOT_ASKED,
    "immigration.last_entry_date": _UNKNOWN_NOT_ASKED,
    "immigration.overstay_days": {"status": "KNOWN", "value": 0},
    "immigration.violation_history": {"status": "KNOWN", "value": []},
    "intent.purposes": {"status": "KNOWN", "value": ["TOURISM"]},
    "intent.stay_days": {"status": "KNOWN", "value": 30},
    "intent.desired_entry_date": {"status": "KNOWN", "value": "2026-07-20"},
    "intent.entry_pattern": {"status": "KNOWN", "value": "SINGLE"},
    "intent.requested_product_code": _UNKNOWN_NOT_ASKED,
    "work.employer_country_code": _UNKNOWN_NOT_ASKED,
    "work.employer_is_indonesian_entity": {"status": "KNOWN", "value": False},
    "work.serves_indonesian_clients": {"status": "KNOWN", "value": False},
    "work.indonesia_source_compensation": {"status": "KNOWN", "value": False},
    "work.indonesian_work_sponsor_confirmed": {"status": "KNOWN", "value": False},
    "investment.pt_pma_committed": {"status": "KNOWN", "value": False},
    "investment.investment_capital_idr": {"status": "KNOWN", "value": 0},
    "investment.paid_up_capital_idr": {"status": "KNOWN", "value": 0},
    "investment.proposed_role": {"status": "KNOWN", "value": "NO_OPERATIONAL_ROLE"},
    "family.relation_to_sponsor": _UNKNOWN_NOT_ASKED,
    "family.sponsor_nationalities": _UNKNOWN_NOT_ASKED,
    # Gate round 2 (2026-07-20) parziale item 2: KNOWN("NONE"), not UNKNOWN
    # — a concrete sentinel guaranteed to fall outside `el.e31.family`'s
    # CHILD-branch allow-list (["E23","E28A"]), so this fact is a definite
    # FALSE (not UNKNOWN) for every persona that doesn't explicitly
    # override it. Was `_UNKNOWN_NOT_ASKED` until persona 8's
    # single-fact-differential bug (see ``test_evaluator_gold.py``'s
    # persona-8 docstring): `ast.py`'s condition evaluator unions
    # `unknown_facts` over a WHOLE `_all`/`_any` subtree even for a
    # dead (FALSE-dominated) branch, so this fact's baseline UNKNOWN leaked
    # into any persona whose SPOUSE branch ended up genuinely UNKNOWN for
    # an unrelated reason. A concrete non-matching value removes the leak
    # at its root — the fact is never UNKNOWN unless a persona explicitly
    # asks it to be (persona 6 still overrides it to test the CHILD path).
    "family.sponsor_status_code": {"status": "KNOWN", "value": "NONE"},
    "family.marriage_registered": {"status": "KNOWN", "value": False},
    "family.sponsor_confirmed": {"status": "KNOWN", "value": False},
    "study.level": _UNKNOWN_NOT_ASKED,
    "study.admission_confirmed": _UNKNOWN_NOT_ASKED,
    "study.sponsor_confirmed": _UNKNOWN_NOT_ASKED,
    # secondhome.* (E33 vertical): UNKNOWN by default — no rule in
    # ``_build_rules`` references these paths, so they never influence the
    # evaluator-suite personas; they exist here only because
    # ``ApplicantFactsData`` requires all 40 keys.
    "secondhome.bank_deposit_usd": _UNKNOWN_NOT_ASKED,
    "secondhome.bank_deposit_at_state_bank": _UNKNOWN_NOT_ASKED,
    "secondhome.bank_deposit_in_own_name": _UNKNOWN_NOT_ASKED,
    "secondhome.qualifying_property_value_usd": _UNKNOWN_NOT_ASKED,
    "secondhome.passive_monthly_income_usd": _UNKNOWN_NOT_ASKED,
    "process.application_channel": {"status": "KNOWN", "value": "OFFSHORE"},
    "process.wants_onshore_conversion": {"status": "KNOWN", "value": False},
    "commercial.service_fee_budget_idr": {"status": "KNOWN", "value": 0},
    "commercial.wants_quote": {"status": "KNOWN", "value": False},
}


def applicant_facts(
    *,
    overrides: Mapping[str, dict[str, Any]] | None = None,
    assessment_id: uuid.UUID | None = None,
) -> M.ApplicantFacts:
    """Baseline facts + ``overrides`` (each a raw ``{"status": ..., ...}``
    wire fact dict, keyed by dotted ``FactPath`` string)."""
    facts = dict(_BASELINE_FACTS)
    if overrides:
        facts.update(overrides)
    return M.ApplicantFacts(
        schema_version="1.0.0",
        assessment_id=assessment_id or uuid.uuid4(),
        collected_at=GOLD_EFFECTIVE_AT,
        facts=facts,
    )


def known(value: Any) -> dict[str, Any]:
    return {"status": "KNOWN", "value": value}


def unknown(reason: str) -> dict[str, Any]:
    return {"status": "UNKNOWN", "reason": reason}
