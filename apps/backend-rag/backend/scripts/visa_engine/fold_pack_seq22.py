"""fold_pack_seq22.py — seq-22, folded DIRECTLY onto signed seq-20.

WHAT THIS FOLD IS, AND WHY IT SKIPS A NUMBER
=============================================
seq-21 was folded, signed under a throwaway ceremony and then STOPPED before
activation: three defects were found in it, and a signed pack is never
amended — the sequence halts and the next fold carries the cure. Its source
(``rulepack-prod-021.source.json``) stays on disk as the record of what was
proposed; its SIGNED bundle never enters this repo, and it will never be
activated. A folded sequence may stop even after signing — precedent for the
weaker case, a source that stops before ever reaching a signature at all:
``rulepack-prod-014`` and ``-015`` exist as sources and were never signed.
A folded sequence may stop.

So this fold chains to seq-20, not to seq-21::

    previous_payload_sha256 = df02287b7fc8f572a9e6674fdf3445a2131c428e8a1492ab8a388dee5bf01a4d

and carries seq-21's CONTENT with two of its three defects cured and the
third one REDESIGNED, not deleted (owner decision D23 "OPTION B-STUDIO",
2026-09-16 — see DEFECT 3 below).

EDITS
=====
1. Retire nine ``REQUIRE_REVIEW`` rules — the same set seq-21 retired.
2. Insert nine ``ELIGIBILITY``/``SUPPORT`` rules — the same nine zero-SUPPORT
   products seq-21 unlocked: E23U E23V E28B E28C E28D E28F E33A E33B E33C.
3. Insert ONE ``HARD_FILTER`` — ``hf.employment-without-indonesian-sponsor``,
   scoped to ``EMPLOYMENT_SPONSOR_PRODUCT_CODES = ("E23", "E33B")``.
4. Insert ONE ``REQUIRE_REVIEW`` — ``review.e33.below-threshold-studio``,
   the B-STUDIO redesign of DEFECT 3.

DEFECT 1 — E23V, CURED HERE
============================
seq-21 scoped ``hf.employment-without-indonesian-sponsor`` to
``("E23", "E23V", "E33B")``. The SAME pack adds ``el.e23v.trade-office``,
which makes E23V recommendable on ``sponsor.type == GOVERNMENT`` AND
``sponsor.trade_office == true`` — but E23V is the visa for someone employed
BY that FOREIGN trade or economic representative office. Their employer is by
definition not an Indonesian entity, so the honest answer to
``work.employer_is_indonesian_entity`` (``false``) EXCLUDED the applicant from
the very product the SUPPORT rule exists to grant. MEASURED against the
seq-21 candidate: UNKNOWN -> ``SUPPORTED_CANDIDATES [E23V]``; ``FALSE`` (the
honest answer) -> EXCLUDED, reason ``PAID_ACTIVITY_WITHOUT_INDONESIAN_SPONSOR``;
``TRUE`` -> ``SUPPORTED_CANDIDATES [E23V]``. Reachable in the public interview:
``flow.ts``'s `work` category asks `work_payer` on every sponsor branch,
including the ``GOVERNMENT`` arm that already asks `sponsor_trade_office`.

THE PRECEDENT THIS FOLLOWS: E23U — E23's other zero-SUPPORT sibling from the
same fold — was DELIBERATELY kept out of this exact exclusion for the
identical reason (its employer is a foreign diplomatic mission). E23V was
simply forgotten from that same reasoning.

DEFECT 2 — E33B, CHECKED AND NOT CURED
=======================================
E33B stays inside the exclusion. ``sponsor.government_collaboration`` is
defined (``enums.FactPath``, Pasal 58) as a collaboration commitment WITH AN
INDONESIAN government body. Unlike E23V's foreign trade office, the
institution E33B's own qualification names is by that definition an
Indonesian one. An applicant who genuinely qualifies for E33B and answers
``work.employer_is_indonesian_entity == false`` is contradicting their own
qualification, not being wrongly turned away.

DEFECT 3 — hf.e33.guarantee-below-threshold: HARD_FILTER STAYS OUT, its
THRESHOLDS COME BACK as a REQUIRE_REVIEW (owner decision D23 "OPTION
B-STUDIO", 2026-09-16)
=====================================================================
seq-21 added a ``HARD_FILTER``/``EXCLUDE`` firing on
``secondhome.bank_deposit_usd < 130000`` AND
``secondhome.qualifying_property_value_usd < 1000000``. A visitor who chooses
the "property" basis is NEVER asked about the deposit (``flow.ts``'s
``second_home`` branch) and ``fact-mapper.ts`` SYNTHESISES
``secondhome.bank_deposit_usd = known(0)`` so the SUPPORT twins resolve
instead of stalling on ``NEEDS_INPUT``. ``0 < 130000`` is therefore always
true, and ``on_unknown: NO_EFFECT`` does not protect anything because the
fact is KNOWN, not unknown. ``engine-adapter.test.ts``'s twin-basis guard
exists precisely for this: it forbids ANY rule with stage
``HARD_FILTER``/``EXCLUDE`` (or effect ``EXCLUDE``) from naming one of the
four synthesised Second-Home facts.

The first fold's answer was to DELETE the rule outright; the owner's D23
ruling REJECTS that outcome — a below-threshold visitor should not read a
dead end (``NO_SUPPORTED_PATH``, the catalogue sentence), they should be
routed to the **Second Home Studio**
(``https://balizero.com/visa/second-home/studio``), where they see the
routes and the numbers for their own case. Human review is explicitly NOT
the redesign: the copy behind ``SECOND_HOME_BELOW_THRESHOLD_STUDIO`` never
says a consultant reviews anything (``engine-adapter.ts``); the stage is
``HUMAN_REVIEW``/``REQUIRE_REVIEW`` only because that is the state machine's
one non-terminal, revisitable outcome — the SAME reason B-STUDIO's own
brief calls it "not NO_PATH".

``review.e33.below-threshold-studio`` (``build_e33_studio_review_rule``)
reinstates the exact ``when`` seq-21's HARD_FILTER carried —
``intent.purposes intersects [SECOND_HOME]`` AND both thresholds, READ from
seq-20's own SUPPORT rules at fold time exactly as ``_e33_guarantee_bounds``
did for seq-21 (never typed twice, so a moved bound aborts the fold instead
of drifting silently) — but as ``stage: HUMAN_REVIEW`` /
``effect: {type: REQUIRE_REVIEW, reason_code:
SECOND_HOME_BELOW_THRESHOLD_STUDIO}`` instead of ``HARD_FILTER``/``EXCLUDE``.

Why this is STILL "declared facts only", the same guarantee the deletion
used to make: the conjunction fires only when NO basis clears its own
threshold. For the basis the visitor did NOT choose, ``fact-mapper.ts``
synthesises ``known(0)`` — so that conjunct (``< threshold``) is TRIVIALLY
true regardless of what the visitor said, and the rule's truth value
collapses onto the ONE conjunct that is never synthesised: the DECLARED
basis's own figure against its own threshold. A property-basis visitor at
400_000 fires it on their own declared 400_000 < 1_000_000; the untouched,
synthesised deposit conjunct (``known(0) < 130000``) is along for the ride,
not the cause. Because the stage is ``HUMAN_REVIEW`` — never
``HARD_FILTER``/``EXCLUDE`` — and the rule contains no ``eq false`` on a
synthesised fact, ``assert_no_hard_filter_reads_a_synthesised_twin_basis_fact``
below and ``engine-adapter.test.ts``'s twin-basis guard both stay GREEN: the
antibody was written against the SHAPE (an EXCLUDE reading a synthesised
fact), not against the two numbers, and this redesign never reintroduces
that shape.

``assert_no_hard_filter_reads_a_synthesised_twin_basis_fact`` below is the
antibody: this fold still REFUSES to emit a pack in which a ``HARD_FILTER``/
``EXCLUDE`` reintroduces the shape, so the ORIGINAL defect cannot come back
through a later fold that copies this one — it says nothing about the
REQUIRE_REVIEW rule this fold adds, by design.

ANCHOR: seq-20 (previous_payload_sha256 =
df02287b7fc8f572a9e6674fdf3445a2131c428e8a1492ab8a388dee5bf01a4d)

USAGE::

    PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq22 \\
        --seq20-source backend/services/visa_engine/contracts/packs/rulepack-prod-020.source.json \\
        --output backend/services/visa_engine/contracts/packs/rulepack-prod-022.source.json
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn

from backend.services.visa_engine.bundle import (
    RulePackVerificationError,
    StaticTrustStore,
    canonicalize_json,
    verify_rule_pack,
)
from backend.services.visa_engine.models import RulePackPayload

SEQ20_PAYLOAD_SHA256 = (
    "df02287b7fc8f572a9e6674fdf3445a2131c428e8a1492ab8a388dee5bf01a4d"  # pragma: allowlist secret
)

FOLD_CREATED_AT = "2026-09-16T00:00:00Z"
FOLD_CREATED_BY = "agent.air-m5.backend-rag.visa-oracle-seq22.fold-2026-09-16"
FOLD_VERSION = "2026.9.16"

NEW_RULE_VALID_FROM = FOLD_CREATED_AT

_RULE_PACK_ID_URL_PREFIX = (
    "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/"
)

REQUESTED_PRODUCT_FACT = "intent.requested_product_code"
DEPOSIT_FACT = "secondhome.bank_deposit_usd"
PROPERTY_FACT = "secondhome.qualifying_property_value_usd"
EMPLOYER_IS_INDONESIAN_FACT = "work.employer_is_indonesian_entity"

# Identical to seq-21
RETIRED_REVIEW_RULES: dict[str, str] = {
    "review.e23u.requested-product": "E23U",
    "review.e23v.requested-product": "E23V",
    "review.e28b.usd-threshold-manual": "E28B",
    "review.e28c.usd-threshold-manual": "E28C",
    "review.e28d.usd-threshold-turnover-manual": "E28D",
    "review.e28f.ikn-threshold-manual": "E28F",
    "review.e33a.central-government-invitation": "E33A",
    "review.e33b.expertise-qualification": "E33B",
    "review.e33c.central-government-invitation": "E33C",
}

# Identical to seq-21
SUPPORT_RULES: tuple[dict[str, Any], ...] = (
    {
        "rule_id": "el.e23u.diplomatic-household",
        "product_code": "E23U",
        "purposes": ["EMPLOYMENT"],
        "premises": [{"op": "eq", "fact": "sponsor.type", "value": "INDIVIDUAL"}],
        "qualifying_fact": "sponsor.diplomatic_household",
        "reason_code": "E23U_DIPLOMATIC_HOUSEHOLD_ELIGIBLE",
    },
    {
        "rule_id": "el.e23v.trade-office",
        "product_code": "E23V",
        "purposes": ["EMPLOYMENT"],
        "premises": [{"op": "eq", "fact": "sponsor.type", "value": "GOVERNMENT"}],
        "qualifying_fact": "sponsor.trade_office",
        "reason_code": "E23V_TRADE_OFFICE_ELIGIBLE",
    },
    {
        "rule_id": "el.e33a.government-invitation",
        "product_code": "E33A",
        "purposes": ["EMPLOYMENT"],
        "premises": [{"op": "eq", "fact": "sponsor.type", "value": "GOVERNMENT"}],
        "qualifying_fact": "sponsor.government_invitation",
        "reason_code": "E33A_GOVERNMENT_INVITATION_ELIGIBLE",
    },
    {
        "rule_id": "el.e33b.government-collaboration",
        "product_code": "E33B",
        "purposes": ["EMPLOYMENT"],
        "premises": [{"op": "eq", "fact": "sponsor.type", "value": "NONE"}],
        "qualifying_fact": "sponsor.government_collaboration",
        "reason_code": "E33B_GOVERNMENT_COLLABORATION_ELIGIBLE",
    },
    {
        "rule_id": "el.e33c.world-figure-invitation",
        "product_code": "E33C",
        "purposes": ["INVESTMENT"],
        "premises": [{"op": "eq", "fact": "sponsor.type", "value": "GOVERNMENT"}],
        "qualifying_fact": "sponsor.world_figure_invitation",
        "reason_code": "E33C_WORLD_FIGURE_INVITATION_ELIGIBLE",
    },
    {
        "rule_id": "el.e28b.company-establishment",
        "product_code": "E28B",
        "purposes": ["INVESTMENT"],
        "premises": [
            {"op": "eq", "fact": "investment.establishes_indonesian_company", "value": True},
        ],
        "qualifying_fact": "investment.meets_published_threshold",
        "reason_code": "E28B_COMPANY_ESTABLISHMENT_ELIGIBLE",
    },
    {
        "rule_id": "el.e28c.capital-market",
        "product_code": "E28C",
        "purposes": ["INVESTMENT"],
        "premises": [
            {"op": "eq", "fact": "investment.capital_market_only", "value": True},
        ],
        "qualifying_fact": "investment.meets_published_threshold",
        "reason_code": "E28C_CAPITAL_MARKET_ELIGIBLE",
    },
    {
        "rule_id": "el.e28d.branch-or-subsidiary",
        "product_code": "E28D",
        "purposes": ["INVESTMENT"],
        "premises": [
            {"op": "eq", "fact": "investment.foreign_branch_or_subsidiary", "value": True},
        ],
        "qualifying_fact": "investment.meets_published_threshold",
        "reason_code": "E28D_BRANCH_OR_SUBSIDIARY_ELIGIBLE",
    },
    {
        "rule_id": "el.e28f.ikn-subsidiary",
        "product_code": "E28F",
        "purposes": ["INVESTMENT"],
        "premises": [
            {"op": "eq", "fact": "investment.ikn_subsidiary", "value": True},
        ],
        "qualifying_fact": "investment.meets_published_threshold",
        "reason_code": "E28F_IKN_SUBSIDIARY_ELIGIBLE",
    },
)

SUPPORT_RULE_IDS: tuple[str, ...] = tuple(row["rule_id"] for row in SUPPORT_RULES)

#: The rule seq-21 added and this fold DELIBERATELY does not carry. Named
#: here — not merely absent — so the anti-regression test can assert on the
#: constant instead of on a string typed twice. See the module docstring,
#: "DEFECT 3".
DELETED_SEQ21_RULE_ID = "hf.e33.guarantee-below-threshold"

#: D23 "OPTION B-STUDIO" (2026-09-16): the REQUIRE_REVIEW rule that carries
#: seq-21's two E33 thresholds back in, on the SAME `when` shape, at
#: `stage: HUMAN_REVIEW` instead of `HARD_FILTER`/`EXCLUDE`. See the module
#: docstring, "DEFECT 3".
E33_STUDIO_RULE_ID = "review.e33.below-threshold-studio"
E33_STUDIO_REASON = "SECOND_HOME_BELOW_THRESHOLD_STUDIO"
#: The two SUPPORT rules whose own `gte` bounds this fold reads rather than
#: types — the same donor rules `fold_pack_seq21.py`'s
#: `_e33_guarantee_bounds` read for the HARD_FILTER this rule replaces.
E33_DEPOSIT_DONOR_RULE_ID = "el.e33.deposit-basis"
E33_PROPERTY_DONOR_RULE_ID = "el.e33.property-basis"

#: The four Second-Home facts ``fact-mapper.ts`` SYNTHESISES for whichever
#: basis the visitor did not choose. Mirror of ``GUARDED_FACTS`` in
#: ``engine-adapter.test.ts``'s twin-basis guard — kept here so the BACKEND
#: fold refuses the shape at emission time, not only the frontend suite after
#: the signature lands.
SYNTHESISED_TWIN_BASIS_FACTS: tuple[str, ...] = (
    DEPOSIT_FACT,
    "secondhome.bank_deposit_at_state_bank",
    "secondhome.bank_deposit_in_own_name",
    PROPERTY_FACT,
)

# SEQ-22 CHANGE: E23V removed from this scope
EMPLOYMENT_SPONSOR_RULE_ID = "hf.employment-without-indonesian-sponsor"
EMPLOYMENT_SPONSOR_REASON = "PAID_ACTIVITY_WITHOUT_INDONESIAN_SPONSOR"
#: The product seq-21 wrongly swept into the employment exclusion, and which
#: this fold takes back out. Named as a constant so the guard below reads the
#: cure instead of a string typed twice.
CURED_PRODUCT_CODE = "E23V"

#: SEQ-22 CHANGE: E23V removed — see the module docstring, DEFECT 1.
EMPLOYMENT_SPONSOR_PRODUCT_CODES: tuple[str, ...] = ("E23", "E33B")

HARD_FILTER_RULE_IDS: tuple[str, ...] = (EMPLOYMENT_SPONSOR_RULE_ID,)
#: D23 "OPTION B-STUDIO": the one REQUIRE_REVIEW rule this fold adds.
REVIEW_RULE_IDS: tuple[str, ...] = (E33_STUDIO_RULE_ID,)
NEW_RULE_IDS: tuple[str, ...] = SUPPORT_RULE_IDS + HARD_FILTER_RULE_IDS + REVIEW_RULE_IDS

TARGET_PRODUCT_CODES: tuple[str, ...] = tuple(row["product_code"] for row in SUPPORT_RULES)

_IDENTITY_KEYS = frozenset(
    {
        "sequence",
        "version",
        "rule_pack_id",
        "created_at",
        "created_by",
        "previous_payload_sha256",
        "rollback_of_payload_sha256",
    }
)


def _rule_pack_id(sequence: int) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"{_RULE_PACK_ID_URL_PREFIX}{sequence}")


def _fail(message: str) -> NoReturn:
    raise SystemExit(f"fold_pack_seq22: {message}")


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _nodes(node: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(node, dict):
        out.append(node)
        for value in node.values():
            out.extend(_nodes(value))
    elif isinstance(node, list):
        for value in node:
            out.extend(_nodes(value))
    return out


def _rules_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {rule["rule_id"]: rule for rule in payload["rules"]}


def _products_by_code(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {product["product_code"]: product for product in payload["products"]}


def _required_facts(when: dict[str, Any]) -> list[str]:
    facts = {node["fact"] for node in _nodes(when) if isinstance(node.get("fact"), str)}
    return sorted(facts)


def assert_anchor_is_a_verified_signed_artifact(
    signed_envelope: dict[str, Any],
    digest: str,
    *,
    observed_at: datetime | None = None,
) -> None:
    try:
        trust_store = StaticTrustStore.from_env()
    except RulePackVerificationError as exc:
        _fail(
            f"cannot verify the seq-20 anchor's signature: {exc}. Export the "
            "production trust store (the public key, e.g. "
            'VISA_ENGINE_TRUST_STORE_KEYS_JSON=\'[{"kid": "prod-2026-07-1", ...}]\') '
            "and re-run — the anchor is never taken on a digest constant alone."
        )
    try:
        verified = verify_rule_pack(
            signed_envelope,
            trust_store=trust_store,
            observed_at=observed_at or datetime.now(timezone.utc),
        )
    except RulePackVerificationError as exc:
        _fail(f"the seq-20 signed bundle does not verify: {exc}")

    signed_digest = verified.payload_sha256.hex()
    if signed_digest != digest:
        _fail(
            f"the seq-20 SOURCE digest {digest} is not the digest of the signed "
            f"seq-20 artifact ({signed_digest}) — the source on disk and the "
            "artifact production verifies are two different payloads."
        )
    if verified.pack.payload.sequence != 20:
        _fail(
            "the signed bundle handed in as the seq-20 anchor carries sequence "
            f"{verified.pack.payload.sequence}"
        )


def _eligibility_rule_ids_for_product(payload: dict[str, Any], product_code: str) -> set[str]:
    products = _products_by_code(payload)
    if product_code not in products:
        _fail(f"product {product_code!r} is not in the catalogue")
    version_id = products[product_code]["product_version_id"]
    return {
        rule["rule_id"]
        for rule in payload["rules"]
        if rule["stage"] == "ELIGIBILITY" and version_id in rule.get("product_version_ids", [])
    }


def _assert_target_products_have_no_eligibility_rule(payload: dict[str, Any]) -> None:
    for code in TARGET_PRODUCT_CODES:
        existing = _eligibility_rule_ids_for_product(payload, code)
        if existing:
            _fail(
                f"product {code!r} already carries ELIGIBILITY rule(s) "
                f"{sorted(existing)} in the base pack"
            )


def _assert_retired_review_rules_are_dormant(payload: dict[str, Any]) -> None:
    rules_by_id = _rules_by_id(payload)
    products = _products_by_code(payload)
    for rule_id, product_code in RETIRED_REVIEW_RULES.items():
        rule = rules_by_id.get(rule_id)
        if rule is None:
            _fail(f"rule {rule_id!r} is not in the base pack — the edit set is stale")
        if rule["effect"]["type"] != "REQUIRE_REVIEW":
            _fail(f"{rule_id!r} is a {rule['effect']['type']} rule, not REQUIRE_REVIEW")
        if REQUESTED_PRODUCT_FACT not in (rule.get("required_facts") or []):
            _fail(
                f"{rule_id!r} no longer reads {REQUESTED_PRODUCT_FACT} — it can now "
                "fire from the browser"
            )
        version_id = products[product_code]["product_version_id"]
        if version_id not in rule.get("product_version_ids", []):
            _fail(
                f"{rule_id!r} is not scoped to {product_code} — the declared "
                "rule/product pairing is stale"
            )


def _bound_nodes(rule: dict[str, Any], fact: str, op: str) -> list[dict[str, Any]]:
    return [
        node
        for node in _nodes(rule.get("when"))
        if node.get("fact") == fact and node.get("op") == op
    ]


def _e33_studio_bounds(payload: dict[str, Any]) -> tuple[int, int]:
    """``(deposit_usd_minimum, property_usd_minimum)``, READ from the two E33
    SUPPORT rules that already encode them — mirrors
    ``fold_pack_seq21.py``'s ``_e33_guarantee_bounds`` exactly, for the same
    reason: typing the bound here a second time could drift from the number
    the SUPPORT rule uses, and the review rule would fire on a threshold the
    product itself no longer enforces. See the module docstring, DEFECT 3.
    """
    rules_by_id = _rules_by_id(payload)
    bounds: list[int] = []
    for rule_id, fact in (
        (E33_DEPOSIT_DONOR_RULE_ID, DEPOSIT_FACT),
        (E33_PROPERTY_DONOR_RULE_ID, PROPERTY_FACT),
    ):
        rule = rules_by_id.get(rule_id)
        if rule is None:
            _fail(f"rule {rule_id!r} is missing — cannot derive the E33 studio bound")
        nodes = _bound_nodes(rule, fact, "gte")
        if len(nodes) != 1:
            _fail(
                f"rule {rule_id!r} carries {len(nodes)} '{fact} gte' bounds; exactly "
                "one is required to mirror it unambiguously"
            )
        value = nodes[0]["value"]
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            _fail(f"rule {rule_id!r}'s '{fact} gte' bound is {value!r}, not a positive integer")
        bounds.append(value)
    return bounds[0], bounds[1]


def _assert_e23v_stays_cured(codes: tuple[str, ...]) -> None:
    """Refuse to fold if E23V is back inside the employment exclusion.

    This is seq-21's first defect, stated as a guard rather than as a
    comment: E23V is the visa for someone employed BY a FOREIGN trade or
    economic representative office, so ``work.employer_is_indonesian_entity
    == false`` is the CORRECT answer for a genuine applicant. A scope that
    excludes E23V on that answer turns the honest reply into a rejection.
    E23U — E23's other zero-SUPPORT sibling, whose employer is a foreign
    diplomatic mission — was kept out of this same exclusion deliberately;
    E23V was simply forgotten from the same reasoning.
    """
    if CURED_PRODUCT_CODE in codes:
        _fail(
            f"{CURED_PRODUCT_CODE} is back inside {EMPLOYMENT_SPONSOR_RULE_ID!r}'s "
            "scope — that is the seq-21 defect this fold exists to cure; see "
            "this module's docstring, DEFECT 1"
        )


def _assert_employment_sponsor_scope_is_coherent(payload: dict[str, Any]) -> None:
    products = _products_by_code(payload)
    for code in EMPLOYMENT_SPONSOR_PRODUCT_CODES:
        if code not in products:
            _fail(f"product {code!r} is not in the catalogue")
        covered = products[code].get("covered_purposes") or []
        if "EMPLOYMENT" not in covered:
            _fail(f"product {code!r} does not cover EMPLOYMENT ({covered})")
    if EMPLOYER_IS_INDONESIAN_FACT not in {
        node.get("fact") for rule in payload["rules"] for node in _nodes(rule.get("when"))
    }:
        _fail(f"no rule in the base pack reads {EMPLOYER_IS_INDONESIAN_FACT}")


def _sponsor_premise_values(row: dict[str, Any]) -> set[str] | None:
    for node in row["premises"]:
        if node.get("fact") != "sponsor.type":
            continue
        if node["op"] == "eq":
            return {node["value"]}
        if node["op"] == "in":
            return set(node["values"])
        _fail(f"{row['rule_id']}: unsupported sponsor.type premise op {node['op']!r}")
    return None


def _assert_sponsor_premises_follow_the_catalogue(payload: dict[str, Any]) -> None:
    products = _products_by_code(payload)
    for row in SUPPORT_RULES:
        admitted = _sponsor_premise_values(row)
        if admitted is None:
            continue
        catalogue = set(products[row["product_code"]]["sponsor_types"])
        if not admitted <= catalogue:
            _fail(
                f"{row['rule_id']} admits sponsor.type {sorted(admitted - catalogue)} that "
                f"{row['product_code']}'s catalogue sponsor_types {sorted(catalogue)} does not name"
            )


def build_support_rule(payload: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    products = _products_by_code(payload)
    code = row["product_code"]
    if code not in products:
        _fail(f"product {code!r} is not in the catalogue — cannot build {row['rule_id']!r}")
    product = products[code]
    purposes = list(row["purposes"])
    unknown = [
        purpose for purpose in purposes if purpose not in (product.get("covered_purposes") or [])
    ]
    if unknown:
        _fail(
            f"{row['rule_id']!r} would cover {unknown} for {code}, which the product "
            f"catalogue does not list among its covered_purposes"
        )
    when = {
        "op": "all",
        "args": [
            {"op": "intersects", "fact": "intent.purposes", "values": purposes},
            *copy.deepcopy(row["premises"]),
            {"op": "eq", "fact": row["qualifying_fact"], "value": True},
        ],
    }
    return {
        "when": when,
        "scope": "PRODUCTS",
        "stage": "ELIGIBILITY",
        "effect": {
            "type": "SUPPORT",
            "reason_code": row["reason_code"],
            "covered_purposes": purposes,
        },
        "rule_id": row["rule_id"],
        "priority": 100,
        "on_unknown": "NEEDS_INPUT",
        "source_refs": list(product["source_refs"]),
        "valid_period": {"to": None, "from": NEW_RULE_VALID_FROM},
        "required_facts": _required_facts(when),
        "explanation_key": f"explain.{row['rule_id']}",
        "safety_critical": False,
        "product_version_ids": [product["product_version_id"]],
    }


def build_employment_sponsor_rule(payload: dict[str, Any]) -> dict[str, Any]:
    products = _products_by_code(payload)
    when = {
        "op": "all",
        "args": [
            {"op": "intersects", "fact": "intent.purposes", "values": ["EMPLOYMENT"]},
            {"op": "eq", "fact": EMPLOYER_IS_INDONESIAN_FACT, "value": False},
        ],
    }
    source_refs: list[str] = []
    for code in EMPLOYMENT_SPONSOR_PRODUCT_CODES:
        for ref in products[code]["source_refs"]:
            if ref not in source_refs:
                source_refs.append(ref)
    return {
        "when": when,
        "scope": "PRODUCTS",
        "stage": "HARD_FILTER",
        "effect": {"type": "EXCLUDE", "reason_code": EMPLOYMENT_SPONSOR_REASON},
        "rule_id": EMPLOYMENT_SPONSOR_RULE_ID,
        "priority": 100,
        "on_unknown": "NO_EFFECT",
        "source_refs": sorted(source_refs),
        "valid_period": {"to": None, "from": NEW_RULE_VALID_FROM},
        "required_facts": _required_facts(when),
        "explanation_key": f"explain.{EMPLOYMENT_SPONSOR_RULE_ID}",
        "safety_critical": False,
        "product_version_ids": [
            products[code]["product_version_id"] for code in EMPLOYMENT_SPONSOR_PRODUCT_CODES
        ],
    }


def build_e33_studio_review_rule(payload: dict[str, Any]) -> dict[str, Any]:
    """D23 "OPTION B-STUDIO": the REQUIRE_REVIEW rule that carries seq-21's
    two E33 thresholds back in, at ``stage: HUMAN_REVIEW`` instead of
    ``HARD_FILTER``/``EXCLUDE``. See the module docstring, DEFECT 3."""
    deposit_min, property_min = _e33_studio_bounds(payload)
    products = _products_by_code(payload)
    product = products["E33"]
    when = {
        "op": "all",
        "args": [
            {"op": "intersects", "fact": "intent.purposes", "values": ["SECOND_HOME"]},
            {"op": "lt", "fact": DEPOSIT_FACT, "value": deposit_min},
            {"op": "lt", "fact": PROPERTY_FACT, "value": property_min},
        ],
    }
    return {
        "when": when,
        "scope": "PRODUCTS",
        "stage": "HUMAN_REVIEW",
        "effect": {"type": "REQUIRE_REVIEW", "reason_code": E33_STUDIO_REASON},
        "rule_id": E33_STUDIO_RULE_ID,
        "priority": 100,
        "on_unknown": "NO_EFFECT",
        "source_refs": list(product["source_refs"]),
        "valid_period": {"to": None, "from": NEW_RULE_VALID_FROM},
        "required_facts": _required_facts(when),
        "explanation_key": f"explain.{E33_STUDIO_RULE_ID}",
        "safety_critical": False,
        "product_version_ids": [product["product_version_id"]],
    }


def build_new_rules(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        *(build_support_rule(payload, row) for row in SUPPORT_RULES),
        build_employment_sponsor_rule(payload),
        build_e33_studio_review_rule(payload),
    ]


def assert_no_hard_filter_reads_a_synthesised_twin_basis_fact(
    payload: dict[str, Any],
) -> None:
    """Refuse to emit a pack in which an EXCLUDE reads a fact the interview
    never asked for.

    ``fact-mapper.ts`` synthesises ``known(0)``/``known(false)`` for the
    Second-Home basis the visitor did NOT choose, so that the SUPPORT twins
    resolve instead of stalling the interview. That synthesis is innocent
    only while every rule reading those four facts is SUPPORT-only: the
    moment a ``HARD_FILTER``/``EXCLUDE`` reads one, a synthesised "known 0"
    stops meaning "not claimed here" and starts EXCLUDING someone who was
    never asked the question. ``engine-adapter.test.ts`` guards this from the
    frontend, but only once a SIGNED bundle is on disk — this runs at FOLD
    time, on the source, which is where the shape is actually introduced.

    An ``eq false`` comparison on one of the four is refused at any stage,
    for the same reason and on the same terms as the frontend guard.
    """
    guarded = set(SYNTHESISED_TWIN_BASIS_FACTS)

    def _fact_nodes(node: Any, out: list[dict[str, Any]]) -> None:
        if isinstance(node, list):
            for item in node:
                _fact_nodes(item, out)
            return
        if not isinstance(node, dict):
            return
        if isinstance(node.get("fact"), str) and node["fact"] in guarded:
            out.append(node)
        if isinstance(node.get("args"), list):
            _fact_nodes(node["args"], out)
        if node.get("arg") is not None:
            _fact_nodes(node["arg"], out)

    readers = 0
    offending_stage: list[str] = []
    offending_eq_false: list[str] = []
    for rule in payload.get("rules", []):
        nodes: list[dict[str, Any]] = []
        _fact_nodes(rule.get("when"), nodes)
        if not nodes:
            continue
        readers += 1
        effect_type = (rule.get("effect") or {}).get("type")
        if rule.get("stage") in {"HARD_FILTER", "EXCLUDE"} or effect_type == "EXCLUDE":
            offending_stage.append(str(rule.get("rule_id")))
        for node in nodes:
            if node.get("op") == "eq" and node.get("value") is False:
                offending_eq_false.append(str(rule.get("rule_id")))

    # Guard the guard: a traversal that silently found nothing would make the
    # two checks below vacuously pass (cicatrix #2, green-but-dead).
    if readers == 0:
        _fail(
            "no rule in the pack reads any Second-Home twin-basis fact — the "
            "traversal found nothing, which means it is not measuring what it "
            "claims to measure"
        )
    if offending_stage:
        _fail(
            f"{sorted(set(offending_stage))} EXCLUDE on a fact the interview "
            "may never have asked (fact-mapper.ts synthesises it) — see this "
            "module's docstring, DEFECT 3"
        )
    if offending_eq_false:
        _fail(
            f"{sorted(set(offending_eq_false))} compare a synthesised "
            "twin-basis fact with 'eq false' — a synthesised false is not an "
            "answer"
        )


def assert_only_expected_changes(before: dict[str, Any], after: dict[str, Any]) -> None:
    if set(after) != set(before):
        _fail(
            "the payload's top-level key set changed "
            f"(added {sorted(set(after) - set(before))}, "
            f"removed {sorted(set(before) - set(after))})"
        )
    for key in set(before) - _IDENTITY_KEYS - {"rules"}:
        if _canon(after.get(key)) != _canon(before.get(key)):
            _fail(f"{key} changed — this fold retires and inserts rules and nothing else")

    before_rules = _rules_by_id(before)
    after_rules = _rules_by_id(after)

    missing = set(before_rules) - set(after_rules)
    if missing != set(RETIRED_REVIEW_RULES):
        _fail(f"removed-rule set mismatch: {sorted(missing)} != {sorted(RETIRED_REVIEW_RULES)}")
    added = set(after_rules) - set(before_rules)
    if added != set(NEW_RULE_IDS):
        _fail(f"added-rule set mismatch: {sorted(added)} != {sorted(NEW_RULE_IDS)}")

    for rule_id, rule in after_rules.items():
        if rule_id in set(NEW_RULE_IDS):
            continue
        if _canon(rule) != _canon(before_rules[rule_id]):
            _fail(
                f"rule {rule_id!r} drifted from seq-20 — this fold edits NO existing "
                "rule, it only retires nine and inserts eleven"
            )


def assert_changed_fields_hold_their_expected_values(
    after: dict[str, Any], *, expected_new_rules: list[dict[str, Any]]
) -> None:
    expected: dict[str, Any] = {
        "sequence": 22,
        "rule_pack_id": str(_rule_pack_id(22)),
        "version": FOLD_VERSION,
        "created_at": FOLD_CREATED_AT,
        "created_by": FOLD_CREATED_BY,
        "previous_payload_sha256": SEQ20_PAYLOAD_SHA256,
        "rollback_of_payload_sha256": None,
    }
    for key, want in expected.items():
        got = after.get(key)
        if got != want:
            _fail(f"{key} is {got!r}, expected {want!r}")

    rules_by_id = _rules_by_id(after)
    for rule_id in RETIRED_REVIEW_RULES:
        if rule_id in rules_by_id:
            _fail(f"rule {rule_id!r} should have been retired but is still present")

    by_id = {rule["rule_id"]: rule for rule in expected_new_rules}
    for rule_id in NEW_RULE_IDS:
        if _canon(rules_by_id.get(rule_id)) != _canon(by_id[rule_id]):
            _fail(f"{rule_id!r} in the output is not the rule this fold built")

    for row in SUPPORT_RULES:
        product_code = row["product_code"]
        version_id = _products_by_code(after)[product_code]["product_version_id"]
        for rule in after["rules"]:
            if (
                rule["rule_id"] == row["rule_id"]
                and rule["stage"] == "ELIGIBILITY"
                and version_id in rule.get("product_version_ids", [])
            ):
                break
        else:
            _fail(f"no ELIGIBILITY rule for {product_code} found")


def fold(
    seq20: dict[str, Any], seq20_signed: dict[str, Any], *, observed_at: datetime | None = None
) -> dict[str, Any]:
    digest = hashlib.sha256(canonicalize_json(seq20)).hexdigest()
    if digest != SEQ20_PAYLOAD_SHA256:
        _fail(
            f"the seq-20 source is not the activated artifact: recomputed JCS "
            f"digest {digest} != {SEQ20_PAYLOAD_SHA256}"
        )
    assert_anchor_is_a_verified_signed_artifact(seq20_signed, digest, observed_at=observed_at)
    if seq20.get("sequence") != 20:
        _fail(f"expected sequence 20, got {seq20.get('sequence')!r}")

    inherited_id = seq20.get("rule_pack_id")
    expected_20_id = str(_rule_pack_id(20))
    if inherited_id != expected_20_id:
        _fail(
            f"the seq-20 payload carries rule_pack_id={inherited_id!r}, but the "
            f"uuid5 convention yields {expected_20_id!r}"
        )

    _assert_target_products_have_no_eligibility_rule(seq20)
    _assert_retired_review_rules_are_dormant(seq20)
    _assert_sponsor_premises_follow_the_catalogue(seq20)
    _assert_e23v_stays_cured(EMPLOYMENT_SPONSOR_PRODUCT_CODES)
    _assert_employment_sponsor_scope_is_coherent(seq20)

    out = json.loads(json.dumps(seq20))
    new_rules = build_new_rules(seq20)

    existing_rules = out.get("rules", [])
    retired_ids = set(RETIRED_REVIEW_RULES.keys())
    filtered_rules = [rule for rule in existing_rules if rule["rule_id"] not in retired_ids]
    out["rules"] = filtered_rules + new_rules

    out["sequence"] = 22
    out["rule_pack_id"] = str(_rule_pack_id(22))
    out["version"] = FOLD_VERSION
    out["created_at"] = FOLD_CREATED_AT
    out["created_by"] = FOLD_CREATED_BY
    out["previous_payload_sha256"] = SEQ20_PAYLOAD_SHA256

    out["rollback_of_payload_sha256"] = None

    assert_only_expected_changes(seq20, out)
    assert_changed_fields_hold_their_expected_values(out, expected_new_rules=new_rules)
    assert_no_hard_filter_reads_a_synthesised_twin_basis_fact(out)
    RulePackPayload.model_validate(out)
    return out


def _assert_output_does_not_collide_with_inputs(output: Path, input_paths: dict[str, Path]) -> None:
    resolved_output = output.resolve()
    for flag, path in input_paths.items():
        if resolved_output == path.resolve():
            _fail(f"--output {output} resolves to the same file as {flag} ({path})")
    if resolved_output.name.endswith(".signed.json"):
        _fail(
            f"--output {output} ends in '.signed.json' — refusing to write unsigned bytes to a signed path"
        )


def main(argv: list[str] | None = None, *, observed_at: datetime | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fold RulePack seq-22 from seq-20.")
    parser.add_argument("--seq20-source", required=True, type=Path)
    parser.add_argument(
        "--seq20-signed",
        type=Path,
        default=None,
        help="the signed seq-20 envelope; defaults to the .signed.json sibling of --seq20-source",
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    if args.seq20_signed is not None:
        signed_path = args.seq20_signed
    else:
        source_str = str(args.seq20_source)
        if not source_str.endswith(".source.json"):
            _fail(
                f"--seq20-source {source_str!r} does not end in '.source.json' — "
                "cannot derive the signed sibling path; pass --seq20-signed explicitly"
            )
        signed_path = Path(source_str[: -len(".source.json")] + ".signed.json")
    if signed_path == args.seq20_source or not signed_path.exists():
        _fail(f"no signed seq-20 bundle at {signed_path} — pass --seq20-signed")

    _assert_output_does_not_collide_with_inputs(
        args.output,
        {"--seq20-source": args.seq20_source, "--seq20-signed": signed_path},
    )

    seq20 = json.loads(args.seq20_source.read_text(encoding="utf-8"))
    seq20_signed = json.loads(signed_path.read_text(encoding="utf-8"))
    seq22 = fold(seq20, seq20_signed, observed_at=observed_at)
    args.output.write_text(json.dumps(seq22, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    digest = hashlib.sha256(canonicalize_json(seq22)).hexdigest()
    print(f"fold_pack_seq22: wrote {args.output}")
    print(f"fold_pack_seq22: seq-22 payload_sha256 = {digest}")
    print("fold_pack_seq22: retired 9 REQUIRE_REVIEW rules")
    print(
        "fold_pack_seq22: inserted 9 ELIGIBILITY/SUPPORT rules + 1 HARD_FILTER rule "
        "+ 1 REQUIRE_REVIEW rule"
    )
    print(f"fold_pack_seq22: removed E23V from {EMPLOYMENT_SPONSOR_RULE_ID!r}")
    print(f"fold_pack_seq22: added {E33_STUDIO_RULE_ID!r} (D23 OPTION B-STUDIO)")
    print("fold_pack_seq22: NOT SIGNED, NOT ACTIVATED — see sign_pack.py / activate_pack.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
