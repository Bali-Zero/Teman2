"""fold_pack_seq21.py — the qualification fold: the nine products with no
SUPPORT rule become recommendable on the fact each one actually names, and the
three generic dead ends get a cause.

WHY, AND WHAT IT REPLACES
=========================
Nine of the pack's 38 products — ``E23U``, ``E23V``, ``E28B``, ``E28C``,
``E28D``, ``E28F``, ``E33A``, ``E33B``, ``E33C`` — carry ZERO ``ELIGIBILITY``
rules in seq-20, so ``evaluate_product``'s ``declared_coverage`` is empty for
them and they are structurally unrecommendable: no interview answer, however
complete, can reach them. Each one instead carries a dormant
``REQUIRE_REVIEW`` rule keyed on ``intent.requested_product_code``, a fact
``fact-mapper.ts`` hard-codes to ``UNKNOWN(NOT_ASKED)``. The measured effect is
"route to a human", and the owner's ruling of 2026-09-13 is the opposite:
«portare 38 prodotti su 38 raggiungibili dal percorso senza rimandare a
revisione umana ma spiegati deterministicamente».

This fold is the PACK half of that ruling. It SUPERSEDES the seq-21 candidate
of PR #6362, which reached the same five sponsor products by keying three of
its rules on ``sponsor.type = GOVERNMENT`` ALONE — ``el.e33a``, ``el.e33b`` and
``el.e23v`` shared one byte-identical ``when``, so a visitor declaring
employment with a government sponsor received E23V + E33A + E33B together with
nothing having established an invitation, a collaboration or a trade office.
``enums.FactPath``'s own ``sponsor.type`` comment had already recorded why that
cannot work ("sponsor.type alone does not supply a safe eligibility gate for
any of the three... Unblocking any of them needs new, legally grounded
discriminator facts"). Those discriminators are the ten wire facts registered
alongside this fold, and every SUPPORT rule below depends on ONE of them.

THE EDITS, BY RULE ID
=====================
1. **Nine dormant ``review.*`` rules RETIRED.** Each is a HUMAN_REVIEW rule
   whose ``when`` conjoins ``intent.requested_product_code eq "<code>"`` — the
   fact the browser never sets — and whose review question is exactly the
   qualification the new SUPPORT rule now establishes as a fact:
   ``GOVT_INVITATION_REQUIRED`` becomes ``sponsor.government_invitation``,
   ``E33B_EXPERTISE_QUALIFICATION_CHECK`` becomes
   ``sponsor.government_collaboration``, the four E28 threshold checks become
   ``investment.meets_published_threshold`` plus a route boolean, and the two
   E23 staff reviews become ``sponsor.diplomatic_household`` /
   ``sponsor.trade_office``.

   They are RETIRED rather than flipped to ``on_unknown: NO_EFFECT`` — the
   shape PR #6362 used and the dossier of 2026-09-13 §4 named as a fail-open:
   ``NO_EFFECT`` on a REQUIRE_REVIEW rule leaves a rule in the pack that still
   claims to police a qualification while never being able to block anything,
   which is strictly worse than not having it. Retiring is also NOT optional
   here and this is the causal fact the dossier measured: ``evaluate_product``
   tests ``review_input_unknowns`` BEFORE ``purposes <= covered``, so a
   REQUIRE_REVIEW rule that is UNKNOWN on ``intent.requested_product_code``
   makes its product ``BLOCKED_UNKNOWN`` even when every eligibility fact is
   present. Left in place, the nine new SUPPORT rules could never produce a
   single SUPPORTED product. :func:`_assert_retired_review_rules_are_dormant`
   checks the premise instead of trusting this paragraph: each one must be a
   REQUIRE_REVIEW rule reading ``intent.requested_product_code``, and its
   product must have no ELIGIBILITY rule yet.

2. **Nine new ``ELIGIBILITY``/``SUPPORT`` rules, one per product**, each
   conjoining its product's sponsor/route premise AND its own qualifying
   fact, with ``on_unknown: NEEDS_INPUT``. ``NEEDS_INPUT`` (not the
   fail-CLOSED ``NO_EFFECT``) because the owner's doctrine for an unasked
   qualification is to ASK it — the outcome vocabulary is
   ``SUPPORTED_CANDIDATES`` / ``NO_SUPPORTED_PATH`` / ``NEEDS_INPUT``, and a
   qualification the interview has not yet asked is a question, not a denial.
   That choice is only safe because every rule's ``when`` is an ``all`` whose
   FIRST premises (purpose, sponsor type / route) are DEFINITE FALSE for
   applicants the product does not concern — Strong-Kleene ``all`` makes the
   whole condition FALSE, never UNKNOWN, so no unrelated walk is turned into
   a question. :func:`_assert_no_walk_regresses_is_the_tests_job` is not a
   function; that invariant is pinned by ``test_seq21_pack.py``'s census
   replay, because it is a property of the 84-walk corpus rather than of this
   payload.

3. **Two new ``HARD_FILTER``/``EXCLUDE`` rules that NAME a cause.** Three of
   the fifteen dead-end walks answer with
   ``OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES`` —
   ``evaluator._fallback_no_path_reason``, emitted only when no
   purpose-feasible product carries an exclusion reason. Both rules below
   exist to replace that sentence with a reason the visitor can act on:

   * ``hf.e33.guarantee-below-threshold`` — the two ``offshore/invest/
     {bank_deposit,property}/below_threshold`` walks declare SECOND_HOME with
     a deposit under the pack's own USD 130,000 bound and a property under its
     own USD 1,000,000 bound. Both numbers are EXTRACTED from
     ``el.e33.deposit-basis`` / ``el.e33.property-basis`` at fold time
     (:func:`_e33_guarantee_bounds`), never typed here, so a pack whose bound
     has moved aborts the fold instead of shipping a stale threshold.
   * ``hf.employment-without-indonesian-sponsor`` — the
     ``offshore/other/paid/employer_no`` walk declares paid EMPLOYMENT and
     ``work.employer_is_indonesian_entity = false``. Scoped to the three
     products whose EMPLOYMENT coverage structurally requires an Indonesian
     employing or collaborating entity (E23, E23V, E33B). E23U is
     DELIBERATELY out of scope: its employer is a foreign diplomatic mission,
     which is legitimately not an Indonesian entity. E33A is deliberately out
     of scope too — ``hf.e33a.sponsor-not-government`` already excludes it on
     that walk, and adding a second TRUE hard filter would only duplicate the
     exclusion without adding information.

   Both carry ``on_unknown: NO_EFFECT``: an EXCLUDE that fires on an UNKNOWN
   fact would deny a product to an applicant who never answered, which is the
   opposite of a named cause.

WHAT IS DELIBERATELY *NOT* DONE HERE
====================================
No signing, no activation (``sign_pack.py`` is the owner's offline ceremony,
``activate_pack.py`` a separate later act). No evaluator, ``models.py`` rule
or interview change — the QUESTIONS that fill the ten new facts are W-VO-Q's
lane and read ``evidence/<pack>/FACTS-FOR-THE-TREE.md``. **No figure is
invented**: the E28 Golden Visa USD minimums appear in NO ``source_record`` of
this pack (the catalogue record carries PAGE locators and no amount), so the
four E28 rules depend on a DECLARED
``investment.meets_published_threshold`` and cite the record the figure must
be read from, rather than comparing ``investment.investment_amount_usd``
against a number this fold would have had to make up. The day a source record
states the figures, a later fold can replace the boolean with the comparison.
Nothing in ``products`` or ``source_records`` moves —
:func:`assert_only_expected_changes` requires universal equality for every key
this fold does not name.

Usage::

    PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq21 \\
        --seq20-source <path to rulepack-prod-020.source.json> \\
        --output <seq-21 source path>

``--seq20-signed`` defaults to the ``.signed.json`` sibling of
``--seq20-source`` and the fold refuses to run without one: the anchor is
verified by SIGNATURE, never by a digest constant alone.
``VISA_ENGINE_TRUST_STORE_KEYS_JSON`` (the production PUBLIC key) must be
exported — its absence is a refusal, not a skipped check.

Ceremony, identical to seq-20's: fold, THEN ``npx prettier --write`` on the
output FROM THE REPO ROOT. Safe because the payload digest is the SHA-256 of
:func:`~backend.services.visa_engine.bundle.canonicalize_json` over the PARSED
document and prettier's JSON printer is semantics-preserving — and CHECKED,
not trusted, by ``test_seq21_pack.py``'s digest and re-fold tests.
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
from typing import Any

from backend.services.visa_engine.bundle import (
    RulePackVerificationError,
    StaticTrustStore,
    canonicalize_json,
    verify_rule_pack,
)
from backend.services.visa_engine.models import RulePackPayload

#: The seq-20 payload digest — this fold's chain anchor, and the digest
#: production is serving now. Measured from ``rulepack-prod-020.signed.json``'s
#: own ``payload_sha256`` AND by re-hashing ``rulepack-prod-020.source.json``
#: (both agree, checked again at every fold by :func:`fold`).
SEQ20_PAYLOAD_SHA256 = "df02287b7fc8f572a9e6674fdf3445a2131c428e8a1492ab8a388dee5bf01a4d"

FOLD_CREATED_AT = "2026-09-13T00:00:00Z"
FOLD_CREATED_BY = "agent.air-m5.backend-rag.visa-oracle-qualification-seq21.fold-2026-09-13"
FOLD_VERSION = "2026.9.13"

#: The pack's own validity window opens AFTER the signature is expected, so a
#: replay of this candidate is never evaluated at an instant the rules were not
#: yet in force — the exact false-negative that made the first seq-21 census
#: report "0 walks moved" (it evaluated at seq-20's ``signed_at``, before the
#: candidate's own ``valid_period.from``). Every new rule below carries the
#: same ``from``.
PACK_VALID_FROM = "2026-09-15T00:00:00Z"

_RULE_PACK_ID_URL_PREFIX = (
    "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/"
)

REQUESTED_PRODUCT_FACT = "intent.requested_product_code"
DEPOSIT_FACT = "secondhome.bank_deposit_usd"
PROPERTY_FACT = "secondhome.qualifying_property_value_usd"
EMPLOYER_IS_INDONESIAN_FACT = "work.employer_is_indonesian_entity"

#: Edit 1. ``retired rule id -> the product code whose qualification it asked a
#: human to establish``. The product code is declared so
#: :func:`_assert_retired_review_rules_are_dormant` can check that the product
#: really had no eligibility rule before this fold — i.e. that retiring the
#: rule removes a gate on a product nothing could reach anyway.
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

#: Edit 2. One row per product: the rule id, the purposes its SUPPORT covers
#: and gates on, the sponsor/route premises that must be DEFINITE for an
#: applicant the product does not concern, the ONE qualifying fact, and the
#: reason code the visitor reads.
#:
#: ``premises`` is a list of condition nodes prepended to the qualifying
#: fact's ``eq ... true``, in this order, inside one ``all``. Order is
#: cosmetic (Strong-Kleene ``all`` is commutative) and chosen so the rule
#: reads purpose -> who -> qualification.
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
        # E33B's catalogue ``sponsor_types`` is ["NONE"] and its own hard
        # filter admits GOVERNMENT or NONE, so the premise mirrors the hard
        # filter rather than narrowing it: the collaboration, not the sponsor
        # category, is what this product turns on.
        "premises": [
            {"op": "in", "fact": "sponsor.type", "values": ["GOVERNMENT", "NONE"]},
        ],
        "qualifying_fact": "sponsor.government_collaboration",
        "reason_code": "E33B_GOVERNMENT_COLLABORATION_ELIGIBLE",
    },
    {
        "rule_id": "el.e33c.world-figure-invitation",
        "product_code": "E33C",
        "purposes": ["INVESTMENT"],
        "premises": [
            {"op": "in", "fact": "sponsor.type", "values": ["GOVERNMENT", "NONE"]},
        ],
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

#: Edit 3. The two named-cause hard filters.
E33_GUARANTEE_RULE_ID = "hf.e33.guarantee-below-threshold"
E33_GUARANTEE_REASON = "SECOND_HOME_GUARANTEE_BELOW_THRESHOLD"
#: The two SUPPORT rules whose bounds the EXCLUDE must mirror exactly — read
#: from the pack, never typed here.
E33_DEPOSIT_DONOR_RULE_ID = "el.e33.deposit-basis"
E33_PROPERTY_DONOR_RULE_ID = "el.e33.property-basis"

EMPLOYMENT_SPONSOR_RULE_ID = "hf.employment-without-indonesian-sponsor"
EMPLOYMENT_SPONSOR_REASON = "PAID_ACTIVITY_WITHOUT_INDONESIAN_SPONSOR"
EMPLOYMENT_SPONSOR_PRODUCT_CODES: tuple[str, ...] = ("E23", "E23V", "E33B")

HARD_FILTER_RULE_IDS: tuple[str, ...] = (E33_GUARANTEE_RULE_ID, EMPLOYMENT_SPONSOR_RULE_ID)
NEW_RULE_IDS: tuple[str, ...] = SUPPORT_RULE_IDS + HARD_FILTER_RULE_IDS

#: The nine products this fold makes recommendable.
TARGET_PRODUCT_CODES: tuple[str, ...] = tuple(row["product_code"] for row in SUPPORT_RULES)

#: The only top-level keys this fold may move; `rules` moves too (retire +
#: insert) but is diffed at the rule level, not by whole-value equality.
_IDENTITY_KEYS = frozenset(
    {
        "sequence",
        "version",
        "rule_pack_id",
        "created_at",
        "created_by",
        "valid_period",
        "previous_payload_sha256",
        "rollback_of_payload_sha256",
    }
)


def _rule_pack_id(sequence: int) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"{_RULE_PACK_ID_URL_PREFIX}{sequence}")


def _fail(message: str) -> None:
    raise SystemExit(f"fold_pack_seq21: {message}")


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _nodes(node: Any) -> list[dict[str, Any]]:
    """Every dict in a condition tree, in a deterministic pre-order."""
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
    """The sorted, de-duplicated fact paths a condition tree reads.

    Derived from the built condition rather than declared beside it, because
    the compiler's ``_check_required_facts_match_condition`` compares exactly
    these two and a hand-written list is one edit away from disagreeing.
    """
    facts = {node["fact"] for node in _nodes(when) if isinstance(node.get("fact"), str)}
    return sorted(facts)


def assert_anchor_is_a_verified_signed_artifact(
    signed_envelope: dict[str, Any],
    digest: str,
    *,
    observed_at: datetime | None = None,
) -> None:
    """Require the chain anchor to be a SIGNED seq-20 pack, not just a digest.

    Same shape as ``fold_pack_seq20.assert_anchor_is_a_verified_signed_artifact``
    — that one is pinned to sequence 19 by its own final check, so it is
    reproduced here pinned to 20 rather than parameterised after the fact.
    """
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


# ---------------------------------------------------------------------------
# Pre-flight census checks — each edit's premise, verified against the base
# pack rather than trusted from the docstring.
# ---------------------------------------------------------------------------


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
    """The nine products this fold unblocks must currently carry ZERO
    ELIGIBILITY rules.

    That is the whole claim — "structurally unrecommendable, because
    ``declared_coverage`` is empty". If a base pack has meanwhile given one of
    them a SUPPORT rule, this fold would be adding a SECOND, differently-keyed
    route to the same product without anyone comparing the two; refuse instead.
    """
    for code in TARGET_PRODUCT_CODES:
        existing = _eligibility_rule_ids_for_product(payload, code)
        if existing:
            _fail(
                f"product {code!r} already carries ELIGIBILITY rule(s) "
                f"{sorted(existing)} in the base pack — this fold's premise is "
                "that the nine target products have none, so it refuses rather "
                "than adding a second, unreconciled route to the same product"
            )


def _assert_retired_review_rules_are_dormant(payload: dict[str, Any]) -> None:
    """Every rule this fold retires must be a REQUIRE_REVIEW rule gated on
    ``intent.requested_product_code``, scoped to the product it is declared
    against.

    The retirement's justification is that the rule is dormant BY
    CONSTRUCTION (``fact-mapper.ts`` never sets that fact) and that its review
    question is now a fact the new SUPPORT rule tests. If a future base pack
    gives one of them a condition that can actually fire from the browser,
    retiring it would drop a live gate — so this refuses rather than deleting.
    """
    rules_by_id = _rules_by_id(payload)
    products = _products_by_code(payload)
    for rule_id, product_code in RETIRED_REVIEW_RULES.items():
        rule = rules_by_id.get(rule_id)
        if rule is None:
            _fail(f"rule {rule_id!r} is not in the base pack — the edit set is stale")
        if rule["effect"]["type"] != "REQUIRE_REVIEW":
            _fail(
                f"{rule_id!r} is a {rule['effect']['type']} rule, not REQUIRE_REVIEW — "
                "refusing to retire it under an edit that only claims to retire "
                "dormant review gates"
            )
        if REQUESTED_PRODUCT_FACT not in (rule.get("required_facts") or []):
            _fail(
                f"{rule_id!r} no longer reads {REQUESTED_PRODUCT_FACT} — it can now "
                "fire from the browser, so retiring it would drop a live gate"
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


def _e33_guarantee_bounds(payload: dict[str, Any]) -> tuple[int, int]:
    """``(deposit_usd_minimum, property_usd_minimum)``, READ from the two E33
    SUPPORT rules that already encode them.

    The named-cause EXCLUDE this fold adds says "below the threshold". If the
    number it uses were typed here it could drift from the number the SUPPORT
    rule uses, and the pack would simultaneously deny a product for being
    below X and grant it at Y. Extracting both makes that impossible and turns
    a moved bound into a fold abort.
    """
    rules_by_id = _rules_by_id(payload)
    bounds: list[int] = []
    for rule_id, fact in (
        (E33_DEPOSIT_DONOR_RULE_ID, DEPOSIT_FACT),
        (E33_PROPERTY_DONOR_RULE_ID, PROPERTY_FACT),
    ):
        rule = rules_by_id.get(rule_id)
        if rule is None:
            _fail(f"rule {rule_id!r} is missing — cannot derive the E33 guarantee bound")
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


def _assert_employment_sponsor_scope_is_coherent(payload: dict[str, Any]) -> None:
    """Every product the employment EXCLUDE is scoped to must declare
    EMPLOYMENT among its ``covered_purposes``.

    A hard filter conditioned on ``intent.purposes intersects [EMPLOYMENT]``
    that is scoped to a product which cannot cover EMPLOYMENT in the first
    place is dead weight at best and a misleading exclusion reason at worst.
    """
    products = _products_by_code(payload)
    for code in EMPLOYMENT_SPONSOR_PRODUCT_CODES:
        if code not in products:
            _fail(
                f"product {code!r} is not in the catalogue — cannot scope {EMPLOYMENT_SPONSOR_RULE_ID}"
            )
        covered = products[code].get("covered_purposes") or []
        if "EMPLOYMENT" not in covered:
            _fail(
                f"product {code!r} does not cover EMPLOYMENT ({covered}) — "
                f"{EMPLOYMENT_SPONSOR_RULE_ID} would be scoped to a product its own "
                "condition can never concern"
            )
    if EMPLOYER_IS_INDONESIAN_FACT not in {
        node.get("fact") for rule in payload["rules"] for node in _nodes(rule.get("when"))
    }:
        _fail(
            f"no rule in the base pack reads {EMPLOYER_IS_INDONESIAN_FACT} — the "
            "fact this exclusion turns on is not one the interview establishes, "
            "so the new rule could never fire"
        )


# ---------------------------------------------------------------------------
# The edits themselves.
# ---------------------------------------------------------------------------


def build_support_rule(payload: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    """One ELIGIBILITY/SUPPORT rule, with its scope, covered purposes and
    citations DERIVED from the product catalogue rather than transcribed."""
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
            f"catalogue does not list among its covered_purposes "
            f"({product.get('covered_purposes')})"
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
        "valid_period": {"to": None, "from": PACK_VALID_FROM},
        "required_facts": _required_facts(when),
        "explanation_key": f"explain.{row['rule_id']}",
        "safety_critical": False,
        "product_version_ids": [product["product_version_id"]],
    }


def build_e33_guarantee_rule(payload: dict[str, Any]) -> dict[str, Any]:
    deposit_min, property_min = _e33_guarantee_bounds(payload)
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
        "stage": "HARD_FILTER",
        "effect": {"type": "EXCLUDE", "reason_code": E33_GUARANTEE_REASON},
        "rule_id": E33_GUARANTEE_RULE_ID,
        "priority": 100,
        "on_unknown": "NO_EFFECT",
        "source_refs": list(product["source_refs"]),
        "valid_period": {"to": None, "from": PACK_VALID_FROM},
        "required_facts": _required_facts(when),
        "explanation_key": f"explain.{E33_GUARANTEE_RULE_ID}",
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
        "valid_period": {"to": None, "from": PACK_VALID_FROM},
        "required_facts": _required_facts(when),
        "explanation_key": f"explain.{EMPLOYMENT_SPONSOR_RULE_ID}",
        "safety_critical": False,
        "product_version_ids": [
            products[code]["product_version_id"] for code in EMPLOYMENT_SPONSOR_PRODUCT_CODES
        ],
    }


def build_new_rules(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        *(build_support_rule(payload, row) for row in SUPPORT_RULES),
        build_e33_guarantee_rule(payload),
        build_employment_sponsor_rule(payload),
    ]


# ---------------------------------------------------------------------------
# Post-conditions.
# ---------------------------------------------------------------------------


def assert_only_expected_changes(before: dict[str, Any], after: dict[str, Any]) -> None:
    """Fail-closed on both axes: name what MAY move and require universal
    equality for everything else, so a key added in some future sequence is
    guarded automatically rather than escaping an allow-list."""
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
    """:func:`assert_only_expected_changes` names what MAY move and excludes it
    from comparison — silent on whether it moved to the RIGHT thing. Pinned
    separately, per the lesson seq-18's review recorded: a guard whose
    fail-closedness holds only while the code above it stays correct is not a
    guard, it is a comment."""
    expected: dict[str, Any] = {
        "sequence": 21,
        "rule_pack_id": str(_rule_pack_id(21)),
        "version": FOLD_VERSION,
        "created_at": FOLD_CREATED_AT,
        "created_by": FOLD_CREATED_BY,
        "valid_period": {"to": None, "from": PACK_VALID_FROM},
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

    # Every target product now has exactly one ELIGIBILITY rule, and it reads
    # that product's own qualifying fact. Stated as an OUTPUT census rather
    # than as nine assertions, so a row added to SUPPORT_RULES without a
    # matching product is caught here too.
    for row in SUPPORT_RULES:
        eligibility = _eligibility_rule_ids_for_product(after, row["product_code"])
        if eligibility != {row["rule_id"]}:
            _fail(
                f"product {row['product_code']!r} ends the fold with ELIGIBILITY "
                f"rules {sorted(eligibility)}, expected exactly [{row['rule_id']!r}]"
            )
        facts = rules_by_id[row["rule_id"]]["required_facts"]
        if row["qualifying_fact"] not in facts:
            _fail(
                f"{row['rule_id']!r} does not read its qualifying fact "
                f"{row['qualifying_fact']!r} — a SUPPORT rule keyed on sponsor "
                "category alone is the exact defect this fold exists to cure"
            )


def fold(
    seq20: dict[str, Any],
    seq20_signed: dict[str, Any],
    *,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Return the seq-21 payload, or abort loudly.

    ``seq20_signed`` is the signed seq-20 envelope and is REQUIRED, not
    optional — see :func:`assert_anchor_is_a_verified_signed_artifact`.
    ``observed_at`` is threaded into that signature check's clock so a test
    pinning it is not left real-clock-dependent.
    """
    digest = hashlib.sha256(canonicalize_json(seq20)).hexdigest()
    if digest != SEQ20_PAYLOAD_SHA256:
        _fail(
            "the seq-20 source is not the activated artifact: recomputed JCS "
            f"digest {digest} != {SEQ20_PAYLOAD_SHA256}. Everything below would "
            "otherwise be built on a payload production never ran."
        )
    assert_anchor_is_a_verified_signed_artifact(seq20_signed, digest, observed_at=observed_at)
    if seq20.get("sequence") != 20:
        _fail(f"expected sequence 20, got {seq20.get('sequence')!r}")

    inherited_id = seq20.get("rule_pack_id")
    expected_20_id = str(_rule_pack_id(20))
    if inherited_id != expected_20_id:
        _fail(
            f"the seq-20 payload carries rule_pack_id={inherited_id!r}, but the "
            f"uuid5 convention yields {expected_20_id!r} — the anchor is verified, "
            "never assumed."
        )
    collisions = sorted(set(NEW_RULE_IDS) & set(_rules_by_id(seq20)))
    if collisions:
        _fail(f"rule(s) {collisions} already exist in seq-20 — this fold declares them as INSERTs")

    _assert_target_products_have_no_eligibility_rule(seq20)
    _assert_retired_review_rules_are_dormant(seq20)
    _assert_employment_sponsor_scope_is_coherent(seq20)

    new_rules = build_new_rules(seq20)

    out = json.loads(json.dumps(seq20))
    out["rules"] = [rule for rule in out["rules"] if rule["rule_id"] not in RETIRED_REVIEW_RULES]
    out["rules"].extend(copy.deepcopy(rule) for rule in new_rules)

    out["sequence"] = 21
    out["rule_pack_id"] = str(_rule_pack_id(21))
    out["version"] = FOLD_VERSION
    out["created_at"] = FOLD_CREATED_AT
    out["created_by"] = FOLD_CREATED_BY
    out["valid_period"] = {"to": None, "from": PACK_VALID_FROM}
    out["previous_payload_sha256"] = SEQ20_PAYLOAD_SHA256
    out["rollback_of_payload_sha256"] = None

    assert_only_expected_changes(seq20, out)
    assert_changed_fields_hold_their_expected_values(out, expected_new_rules=new_rules)
    RulePackPayload.model_validate(out)
    return out


def _assert_output_does_not_collide_with_inputs(output: Path, input_paths: dict[str, Path]) -> None:
    """Refuse to write ``--output`` onto any input path, and refuse an output
    path that merely LOOKS like a signed artifact — verbatim the guard
    ``fold_pack_seq20.py`` carries, for the same reason: a copy-pasted flag
    could otherwise overwrite the SIGNED production anchor with unsigned fold
    bytes."""
    resolved_output = output.resolve()
    for flag, path in input_paths.items():
        if resolved_output == path.resolve():
            _fail(
                f"--output {output} resolves to the same file as {flag} "
                f"({path}) — refusing to overwrite an input (or the signed "
                "production anchor) with unsigned fold output"
            )
    if resolved_output.name.endswith(".signed.json"):
        _fail(
            f"--output {output} ends in '.signed.json' — this script only "
            "ever writes an unsigned SOURCE file (see the module docstring); "
            "refusing to write unsigned bytes to a path that looks signed"
        )


def main(argv: list[str] | None = None, *, observed_at: datetime | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fold RulePack seq-21.")
    parser.add_argument("--seq20-source", required=True, type=Path)
    parser.add_argument(
        "--seq20-signed",
        type=Path,
        default=None,
        help=(
            "the signed seq-20 envelope; defaults to the .signed.json sibling "
            "of --seq20-source. Its signature is verified — the anchor is "
            "never taken on the digest constant alone."
        ),
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
    seq21 = fold(seq20, seq20_signed, observed_at=observed_at)
    args.output.write_text(json.dumps(seq21, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    digest = hashlib.sha256(canonicalize_json(seq21)).hexdigest()
    print(f"fold_pack_seq21: wrote {args.output}")
    print(f"fold_pack_seq21: seq-21 payload_sha256 = {digest}")
    print(f"fold_pack_seq21: retired {sorted(RETIRED_REVIEW_RULES)}")
    print(f"fold_pack_seq21: inserted {sorted(NEW_RULE_IDS)}")
    print("fold_pack_seq21: NOT SIGNED, NOT ACTIVATED — see sign_pack.py / activate_pack.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
