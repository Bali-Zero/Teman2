"""fold_pack_seq23.py — seq-23, the pack's human-review holds become named
dead ends. CANDIDATE ONLY: this fold is never signed or activated by itself.

WHAT THIS FOLD IS
==================
Slice A8-1 (``MANDATE-vo.md``, DRAFT-SPEC-A8-1.v2 §1). Eight ``REQUIRE_REVIEW``
rules that today stop an applicant at ``HUMAN_REVIEW_REQUIRED`` are RETIRED
and replaced by eleven ``HARD_FILTER``/``EXCLUDE`` rules that name the same
fact pattern as a DEAD END instead — the applicant reads a reason and, where
the underlying fact is unknown, is asked for it (``on_unknown: NEEDS_INPUT``)
rather than being told a human will look at it. Four existing ``HARD_FILTER``
rules that already reached this shape keep their ``when``/``effect`` byte for
byte and only flip ``on_unknown`` from ``HUMAN_REVIEW`` to ``NEEDS_INPUT`` —
an unknown fact ahead of a hard filter is a question to ask, not a reason to
hold. One ``REQUIRE_REVIEW`` rule, ``review.e33.below-threshold-studio``
(D23 "OPTION B-STUDIO"), is brought forward BYTE-IDENTICAL: it routes to the
Second Home Studio, not to a consultant, and staying ``HUMAN_REVIEW`` is the
state machine's own non-terminal outcome for that redesign — see
``fold_pack_seq22.py``'s DEFECT 3 for why. After this fold, exactly one
``HUMAN_REVIEW``-stage rule remains in the candidate pack, and no rule's
``on_unknown`` is ``HUMAN_REVIEW`` (A8.4).

ANCHOR: seq-22, SIGNED and ACTIVE
==================================
``previous_payload_sha256`` = the seq-22 SIGNED artifact's own payload digest
(``rulepack-prod-022.signed.json``), verified against the public production
trust store exactly as every prior fold verifies its own anchor
(``assert_anchor_is_a_verified_signed_artifact``) — never taken on the digest
constant alone.

    previous_payload_sha256 = 3d7555afcc9496b451bc86235624b4a88d35aabb9df354778dcf9b0b3b276e37

THE DISPOSITION TABLE (DRAFT-SPEC-A8-1.v2 §1)
==============================================
Eight ``review.*`` ids REMOVED, eleven ``hf.*`` ids INSERTED, four ``hf.*``
ids MODIFIED IN PLACE. Every retired/replaced rule's ``when`` is COPIED from
the rule it replaces — read at fold time from the input payload, never
retyped — so a bound or a nationality list cannot silently drift between the
REVIEW shape and its HARD_FILTER successor. The three genuinely NEW rules
(no ``review.*`` predecessor) derive their conditions from the SUPPORT rule
they negate — ``el.e30-student-support`` for the STUDY hold,
``el.e33e.retirement``/``el.e33f.retirement`` for the two RETIREMENT holds —
for the identical reason ``fold_pack_seq22.py``'s ``_e33_studio_bounds``
reads its two bounds from their own donor SUPPORT rules rather than typing
them a second time.

REMOVED (8, all today ``stage: HUMAN_REVIEW`` / ``effect: REQUIRE_REVIEW``)::

    review.calling-visa                -> hf.calling-visa-nationality
    review.citizenship-conflict        -> hf.b1.voa-dual-nationality (branch 1 only;
                                           branch 2 is subsumed by the GLOBAL
                                           calling-visa rule above)
    review.active-overstay             -> hf.active-overstay
    review.minor-without-guardian      -> hf.minor-without-confirmed-sponsor
    review.bridging.adverse-history    -> hf.bridging.adverse-history
    review.e33.work-rangkap-kegiatan   -> hf.e33.employment-not-covered
    review.e33g.local-market           -> hf.e33g.local-market
    review.e33g.local-company-ownership -> hf.e33g.local-company-ownership

INSERTED, no predecessor (3, fallback rules, ``on_unknown: NO_EFFECT`` — the
SUPPORT rule they negate owns the unknown path)::

    hf.study.admission-or-sponsor-unconfirmed  (negates el.e30-student-support)
    hf.e33e.retirement-income-below-minimum    (negates el.e33e.retirement)
    hf.e33f.retirement-income-below-minimum    (negates el.e33f.retirement)

MODIFIED IN PLACE (4, ``on_unknown`` only: ``HUMAN_REVIEW`` -> ``NEEDS_INPUT``,
every other field byte-identical)::

    hf.bridging.offshore
    hf.bridging.from-visit-itk
    hf.bridging.to-bridging
    hf.b1.not-voa-nationality

BROUGHT FORWARD, BYTE-IDENTICAL::

    review.e33.below-threshold-studio  (D23 "OPTION B-STUDIO", stays REQUIRE_REVIEW)

ANTIBODIES CARRIED FORWARD (A8.3)
==================================
``assert_no_hard_filter_reads_a_synthesised_twin_basis_fact`` — copied from
``fold_pack_seq22.py`` verbatim in spirit (same four guarded facts, same
guilt/innocence shape) and run on THIS fold's output: none of the eleven new
``HARD_FILTER`` rules may read a Second-Home twin-basis fact
(``secondhome.bank_deposit_usd``, ``secondhome.bank_deposit_at_state_bank``,
``secondhome.bank_deposit_in_own_name``, ``secondhome.qualifying_property_
value_usd``) — the two retirement HARD_FILTERs read
``secondhome.passive_monthly_income_usd`` instead, which ``fact-mapper.ts``
never synthesises for either basis. ``_assert_e33e_e33f_retirement_bounds_
are_equal`` mirrors ``_e33_studio_bounds``'s own guard: the two RETIREMENT
HARD_FILTERs' threshold is READ from their own donor SUPPORT rules and
asserted equal (3000 today), never typed twice.

USAGE::

    PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq23 \\
        --seq22-source backend/services/visa_engine/contracts/packs/rulepack-prod-022.source.json \\
        --output backend/services/visa_engine/contracts/packs/rulepack-prod-023.source.json
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

#: H22 — the seq-22 SIGNED artifact's own payload digest (the anchor).
SEQ22_PAYLOAD_SHA256 = (
    "3d7555afcc9496b451bc86235624b4a88d35aabb9df354778dcf9b0b3b276e37"  # pragma: allowlist secret
)

FOLD_CREATED_AT = "2026-09-23T00:00:00Z"
FOLD_CREATED_BY = "agent.air-m5.backend-rag.visa-oracle-seq23.fold-2026-09-23"
FOLD_VERSION = "2026.9.23"

NEW_RULE_VALID_FROM = FOLD_CREATED_AT

_RULE_PACK_ID_URL_PREFIX = (
    "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/"
)

# ---------------------------------------------------------------------------
# The disposition table's identifiers.
# ---------------------------------------------------------------------------

#: The 8 retired REQUIRE_REVIEW ids -> the hf.* id that replaces each.
REMOVED_TO_INSERTED: dict[str, str] = {
    "review.calling-visa": "hf.calling-visa-nationality",
    "review.citizenship-conflict": "hf.b1.voa-dual-nationality",
    "review.active-overstay": "hf.active-overstay",
    "review.minor-without-guardian": "hf.minor-without-confirmed-sponsor",
    "review.bridging.adverse-history": "hf.bridging.adverse-history",
    "review.e33.work-rangkap-kegiatan": "hf.e33.employment-not-covered",
    "review.e33g.local-market": "hf.e33g.local-market",
    "review.e33g.local-company-ownership": "hf.e33g.local-company-ownership",
}
REMOVED_RULE_IDS: frozenset[str] = frozenset(REMOVED_TO_INSERTED)

#: The 3 genuinely new hf.* ids — no review.* predecessor, each the negation
#: of a SUPPORT rule's own conjuncts.
NO_PREDECESSOR_INSERTED_RULE_IDS: tuple[str, ...] = (
    "hf.study.admission-or-sponsor-unconfirmed",
    "hf.e33e.retirement-income-below-minimum",
    "hf.e33f.retirement-income-below-minimum",
)

INSERTED_RULE_IDS: frozenset[str] = frozenset(
    set(REMOVED_TO_INSERTED.values()) | set(NO_PREDECESSOR_INSERTED_RULE_IDS)
)

#: The 4 existing HARD_FILTER ids whose `on_unknown` flips HUMAN_REVIEW ->
#: NEEDS_INPUT and nothing else.
MODIFIED_RULE_IDS: frozenset[str] = frozenset(
    {
        "hf.bridging.offshore",
        "hf.bridging.from-visit-itk",
        "hf.bridging.to-bridging",
        "hf.b1.not-voa-nationality",
    }
)

#: Brought forward byte-identical — D23 "OPTION B-STUDIO". Named here so a
#: test can assert on the constant instead of the literal string.
STUDIO_RULE_ID = "review.e33.below-threshold-studio"

#: The SUPPORT rules the 3 no-predecessor hf.* rules each negate.
STUDY_SUPPORT_RULE_ID = "el.e30-student-support"
E33E_SUPPORT_RULE_ID = "el.e33e.retirement"
E33F_SUPPORT_RULE_ID = "el.e33f.retirement"

RETIREMENT_INCOME_FACT = "secondhome.passive_monthly_income_usd"

#: Mirror of `fold_pack_seq22.py`'s own guarded set — the four Second-Home
#: facts `fact-mapper.ts` SYNTHESISES for whichever basis the visitor did not
#: choose. No new rule in this fold may let a HARD_FILTER/EXCLUDE read one.
SYNTHESISED_TWIN_BASIS_FACTS: tuple[str, ...] = (
    "secondhome.bank_deposit_usd",
    "secondhome.bank_deposit_at_state_bank",
    "secondhome.bank_deposit_in_own_name",
    "secondhome.qualifying_property_value_usd",
)

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
    raise SystemExit(f"fold_pack_seq23: {message}")


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
            f"cannot verify the seq-22 anchor's signature: {exc}. Export the "
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
        _fail(f"the seq-22 signed bundle does not verify: {exc}")

    signed_digest = verified.payload_sha256.hex()
    if signed_digest != digest:
        _fail(
            f"the seq-22 SOURCE digest {digest} is not the digest of the signed "
            f"seq-22 artifact ({signed_digest}) — the source on disk and the "
            "artifact production verifies are two different payloads."
        )
    if verified.pack.payload.sequence != 22:
        _fail(
            "the signed bundle handed in as the seq-22 anchor carries sequence "
            f"{verified.pack.payload.sequence}"
        )


def _require_rule(payload: dict[str, Any], rule_id: str) -> dict[str, Any]:
    rule = _rules_by_id(payload).get(rule_id)
    if rule is None:
        _fail(f"rule {rule_id!r} is not in the base pack — the edit set is stale")
    return rule


def _assert_removed_rules_are_dormant(payload: dict[str, Any]) -> None:
    """Pre-fold sanity: every rule §1 says to remove really is, today, the
    REQUIRE_REVIEW shape this fold's docstring claims it is."""
    for rule_id in REMOVED_RULE_IDS:
        rule = _require_rule(payload, rule_id)
        if rule["stage"] != "HUMAN_REVIEW" or rule["effect"]["type"] != "REQUIRE_REVIEW":
            _fail(
                f"{rule_id!r} is {rule['stage']}/{rule['effect']['type']}, not "
                "HUMAN_REVIEW/REQUIRE_REVIEW — the edit set is stale"
            )


def _assert_modified_rules_are_the_expected_shape(payload: dict[str, Any]) -> None:
    """Pre-fold sanity: every rule §1 says to modify in place really is,
    today, a HARD_FILTER/EXCLUDE with `on_unknown: HUMAN_REVIEW`."""
    for rule_id in MODIFIED_RULE_IDS:
        rule = _require_rule(payload, rule_id)
        if rule["stage"] != "HARD_FILTER" or rule["effect"]["type"] != "EXCLUDE":
            _fail(f"{rule_id!r} is {rule['stage']}/{rule['effect']['type']}, not HARD_FILTER/EXCLUDE")
        if rule["on_unknown"] != "HUMAN_REVIEW":
            _fail(f"{rule_id!r} on_unknown is {rule['on_unknown']!r}, expected HUMAN_REVIEW")


def _assert_studio_rule_is_present_and_unchanged_from(payload: dict[str, Any]) -> None:
    if STUDIO_RULE_ID not in _rules_by_id(payload):
        _fail(f"{STUDIO_RULE_ID!r} is missing from the base pack — the edit set is stale")


def build_carried_hard_filter(
    *,
    rule_id: str,
    when: dict[str, Any],
    scope: str,
    product_version_ids: list[str] | None,
    reason_code: str,
    on_unknown: str,
    source_refs: list[str],
    safety_critical: bool,
) -> dict[str, Any]:
    """One shape, used by every §1 row: a HARD_FILTER/EXCLUDE whose `when` is
    COPIED from the rule it replaces (or derived from a SUPPORT donor), never
    retyped. `source_refs`/`safety_critical` are copied from the rule this
    replaces (or, for a no-predecessor rule, from the SUPPORT rule it
    negates) per DRAFT-SPEC-A8-1.v2 §1's own convention."""

    return {
        "when": when,
        "scope": scope,
        "stage": "HARD_FILTER",
        "effect": {"type": "EXCLUDE", "reason_code": reason_code},
        "rule_id": rule_id,
        "priority": 100,
        "on_unknown": on_unknown,
        "source_refs": list(source_refs),
        "valid_period": {"to": None, "from": NEW_RULE_VALID_FROM},
        "required_facts": _required_facts(when),
        "explanation_key": f"explain.{rule_id}",
        "safety_critical": safety_critical,
        "product_version_ids": product_version_ids,
    }


def _build_replaced_rule(payload: dict[str, Any], removed_id: str, reason_code: str) -> dict[str, Any]:
    """The 7 straightforward §1 rows: the new hf.* rule's `when`, `scope`,
    `product_version_ids`, `source_refs` and `safety_critical` are all copied
    verbatim from the review.* rule it replaces. `on_unknown` is always
    NEEDS_INPUT in the output — whether that is a flip (the removed rule's
    own `on_unknown` was HUMAN_REVIEW) or a carry (it was already
    NEEDS_INPUT) is a fact about the INPUT, not a choice this builder makes."""

    donor = _require_rule(payload, removed_id)
    return build_carried_hard_filter(
        rule_id=REMOVED_TO_INSERTED[removed_id],
        when=copy.deepcopy(donor["when"]),
        scope=donor["scope"],
        product_version_ids=copy.deepcopy(donor.get("product_version_ids")),
        reason_code=reason_code,
        on_unknown="NEEDS_INPUT",
        source_refs=donor["source_refs"],
        safety_critical=donor["safety_critical"],
    )


def build_hf_calling_visa_nationality(payload: dict[str, Any]) -> dict[str, Any]:
    return _build_replaced_rule(
        payload, "review.calling-visa", "CALLING_VISA_NATIONALITY_NOT_ASSESSED"
    )


def build_hf_b1_voa_dual_nationality(payload: dict[str, Any]) -> dict[str, Any]:
    """The one row that is NOT a straight copy: only branch 1 of
    `review.citizenship-conflict`'s `any` (the VOA-list / non-VOA-list dual
    nationality conflict) survives — branch 2 (the calling-visa dual
    nationality conflict) is SUBSUMED by `hf.calling-visa-nationality`, which
    already excludes on the calling-visa list alone, dual nationality or not.
    Scope narrows from GLOBAL to B1 PRODUCTS: the donor's own product is read
    from `hf.b1.not-voa-nationality`'s scope, never retyped, since that is
    the rule this new one shares a product with."""

    donor = _require_rule(payload, "review.citizenship-conflict")
    when = donor["when"]
    if when.get("op") != "any" or len(when.get("args", [])) != 2:
        _fail(
            "review.citizenship-conflict's `when` is not the expected "
            "2-branch `any` — the branch-1-only extraction is stale"
        )
    branch_1 = copy.deepcopy(when["args"][0])
    b1_filter = _require_rule(payload, "hf.b1.not-voa-nationality")
    return build_carried_hard_filter(
        rule_id="hf.b1.voa-dual-nationality",
        when=branch_1,
        scope="PRODUCTS",
        product_version_ids=copy.deepcopy(b1_filter["product_version_ids"]),
        reason_code="VOA_DUAL_NATIONALITY_NOT_ASSESSED",
        on_unknown="NEEDS_INPUT",
        source_refs=donor["source_refs"],
        safety_critical=donor["safety_critical"],
    )


def build_hf_active_overstay(payload: dict[str, Any]) -> dict[str, Any]:
    return _build_replaced_rule(payload, "review.active-overstay", "ACTIVE_OVERSTAY_SETTLE_FIRST")


def build_hf_minor_without_confirmed_sponsor(payload: dict[str, Any]) -> dict[str, Any]:
    return _build_replaced_rule(
        payload, "review.minor-without-guardian", "MINOR_SPONSOR_NOT_CONFIRMED"
    )


def build_hf_bridging_adverse_history(payload: dict[str, Any]) -> dict[str, Any]:
    return _build_replaced_rule(
        payload, "review.bridging.adverse-history", "BRIDGING_ADVERSE_HISTORY_NOT_ASSESSED"
    )


def build_hf_e33_employment_not_covered(payload: dict[str, Any]) -> dict[str, Any]:
    return _build_replaced_rule(
        payload, "review.e33.work-rangkap-kegiatan", "E33_EMPLOYMENT_NOT_COVERED"
    )


def build_hf_e33g_local_market(payload: dict[str, Any]) -> dict[str, Any]:
    return _build_replaced_rule(
        payload, "review.e33g.local-market", "E33G_LOCAL_MARKET_NOT_ALLOWED"
    )


def build_hf_e33g_local_company_ownership(payload: dict[str, Any]) -> dict[str, Any]:
    return _build_replaced_rule(
        payload, "review.e33g.local-company-ownership", "E33G_LOCAL_COMPANY_NOT_ALLOWED"
    )


def _support_rule_boolean_conjuncts(support_rule: dict[str, Any]) -> list[dict[str, Any]]:
    """The `eq ... true` conjuncts of a SUPPORT rule's top-level `all`,
    excluding the leading `intersects intent.purposes` conjunct. Read from
    the rule itself so a donor that gains or loses a conjunct is a fold-time
    failure, not a silent drift between the SUPPORT rule and its negation."""

    when = support_rule["when"]
    if when.get("op") != "all":
        _fail(f"{support_rule['rule_id']!r}'s `when` is not a top-level `all`")
    conjuncts = [
        arg
        for arg in when["args"]
        if not (arg.get("op") == "intersects" and arg.get("fact") == "intent.purposes")
    ]
    for arg in conjuncts:
        if arg.get("op") != "eq" or arg.get("value") is not True:
            _fail(
                f"{support_rule['rule_id']!r} carries a conjunct this negation "
                f"does not know how to invert: {arg!r}"
            )
    if len(conjuncts) < 2:
        _fail(
            f"{support_rule['rule_id']!r} carries {len(conjuncts)} boolean "
            "conjunct(s) after the purposes check; the STUDY negation expects "
            "at least 2"
        )
    return conjuncts


def build_hf_study_admission_or_sponsor_unconfirmed(payload: dict[str, Any]) -> dict[str, Any]:
    """The negation of `el.e30-student-support`'s own conjuncts
    (`study.admission_confirmed`, `study.sponsor_confirmed`): a STUDY
    applicant who has declared either one FALSE is a named dead end. An
    UNKNOWN conjunct stays with the SUPPORT rule's own `on_unknown:
    NEEDS_INPUT` — this rule's `on_unknown` is `NO_EFFECT` so it never races
    that question."""

    donor = _require_rule(payload, STUDY_SUPPORT_RULE_ID)
    conjuncts = _support_rule_boolean_conjuncts(donor)
    negated_any = {
        "op": "any",
        "args": [{"op": "eq", "fact": c["fact"], "value": False} for c in conjuncts],
    }
    when = {
        "op": "all",
        "args": [
            {"op": "intersects", "fact": "intent.purposes", "values": ["STUDY"]},
            negated_any,
        ],
    }
    return build_carried_hard_filter(
        rule_id="hf.study.admission-or-sponsor-unconfirmed",
        when=when,
        scope="PRODUCTS",
        product_version_ids=copy.deepcopy(donor["product_version_ids"]),
        reason_code="STUDY_ADMISSION_OR_SPONSOR_NOT_CONFIRMED",
        on_unknown="NO_EFFECT",
        source_refs=donor["source_refs"],
        safety_critical=False,
    )


def _retirement_income_bound(payload: dict[str, Any], rule_id: str) -> int:
    rule = _require_rule(payload, rule_id)
    nodes = [
        node
        for node in _nodes(rule.get("when"))
        if node.get("fact") == RETIREMENT_INCOME_FACT and node.get("op") == "gte"
    ]
    if len(nodes) != 1:
        _fail(
            f"rule {rule_id!r} carries {len(nodes)} '{RETIREMENT_INCOME_FACT} gte' "
            "bounds; exactly one is required to mirror it unambiguously"
        )
    value = nodes[0]["value"]
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        _fail(f"rule {rule_id!r}'s '{RETIREMENT_INCOME_FACT} gte' bound is {value!r}")
    return value


def _assert_e33e_e33f_retirement_bounds_are_equal(payload: dict[str, Any]) -> int:
    """GUILT: change one donor's bound and the two rules' thresholds no
    longer agree — the fold aborts rather than emit two RETIREMENT
    HARD_FILTERs that disagree on what "below minimum" means."""

    e33e_bound = _retirement_income_bound(payload, E33E_SUPPORT_RULE_ID)
    e33f_bound = _retirement_income_bound(payload, E33F_SUPPORT_RULE_ID)
    if e33e_bound != e33f_bound:
        _fail(
            f"{E33E_SUPPORT_RULE_ID!r} reads {RETIREMENT_INCOME_FACT} gte "
            f"{e33e_bound}, but {E33F_SUPPORT_RULE_ID!r} reads {e33f_bound} — "
            "the two RETIREMENT thresholds must be the same number"
        )
    return e33e_bound


def _build_retirement_hard_filter(
    payload: dict[str, Any], *, rule_id: str, support_rule_id: str, bound: int
) -> dict[str, Any]:
    donor = _require_rule(payload, support_rule_id)
    when = {
        "op": "all",
        "args": [
            {"op": "intersects", "fact": "intent.purposes", "values": ["RETIREMENT"]},
            {"op": "lt", "fact": RETIREMENT_INCOME_FACT, "value": bound},
        ],
    }
    return build_carried_hard_filter(
        rule_id=rule_id,
        when=when,
        scope="PRODUCTS",
        product_version_ids=copy.deepcopy(donor["product_version_ids"]),
        reason_code="RETIREMENT_INCOME_BELOW_THRESHOLD",
        on_unknown="NO_EFFECT",
        source_refs=donor["source_refs"],
        safety_critical=False,
    )


def build_hf_e33e_retirement_income_below_minimum(
    payload: dict[str, Any], *, bound: int
) -> dict[str, Any]:
    return _build_retirement_hard_filter(
        payload,
        rule_id="hf.e33e.retirement-income-below-minimum",
        support_rule_id=E33E_SUPPORT_RULE_ID,
        bound=bound,
    )


def build_hf_e33f_retirement_income_below_minimum(
    payload: dict[str, Any], *, bound: int
) -> dict[str, Any]:
    return _build_retirement_hard_filter(
        payload,
        rule_id="hf.e33f.retirement-income-below-minimum",
        support_rule_id=E33F_SUPPORT_RULE_ID,
        bound=bound,
    )


def build_new_rules(payload: dict[str, Any]) -> list[dict[str, Any]]:
    retirement_bound = _assert_e33e_e33f_retirement_bounds_are_equal(payload)
    return [
        build_hf_calling_visa_nationality(payload),
        build_hf_b1_voa_dual_nationality(payload),
        build_hf_active_overstay(payload),
        build_hf_minor_without_confirmed_sponsor(payload),
        build_hf_bridging_adverse_history(payload),
        build_hf_e33_employment_not_covered(payload),
        build_hf_e33g_local_market(payload),
        build_hf_e33g_local_company_ownership(payload),
        build_hf_study_admission_or_sponsor_unconfirmed(payload),
        build_hf_e33e_retirement_income_below_minimum(payload, bound=retirement_bound),
        build_hf_e33f_retirement_income_below_minimum(payload, bound=retirement_bound),
    ]


def assert_no_hard_filter_reads_a_synthesised_twin_basis_fact(
    payload: dict[str, Any],
) -> None:
    """A8.3's antibody — same shape as `fold_pack_seq22.py`'s guard of the
    same name, re-run here so a HARD_FILTER this fold inserts cannot
    reintroduce the shape it refuses: an EXCLUDE (or an `eq false`, at any
    stage) reading a fact `fact-mapper.ts` synthesises for the Second-Home
    basis the visitor did not choose.
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

    if readers == 0:
        _fail(
            "no rule in the pack reads any Second-Home twin-basis fact — the "
            "traversal found nothing, which means it is not measuring what it "
            "claims to measure"
        )
    if offending_stage:
        _fail(
            f"{sorted(set(offending_stage))} EXCLUDE on a fact the interview "
            "may never have asked (fact-mapper.ts synthesises it)"
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
            _fail(f"{key} changed — this fold retires, inserts and modifies rules and nothing else")

    before_rules = _rules_by_id(before)
    after_rules = _rules_by_id(after)

    missing = set(before_rules) - set(after_rules)
    if missing != REMOVED_RULE_IDS:
        _fail(
            "removed-rule set mismatch: "
            f"not retired {sorted(REMOVED_RULE_IDS - missing)}, "
            f"retired unexpectedly {sorted(missing - REMOVED_RULE_IDS)}"
        )
    added = set(after_rules) - set(before_rules)
    if added != INSERTED_RULE_IDS:
        _fail(
            "added-rule set mismatch: "
            f"not inserted {sorted(INSERTED_RULE_IDS - added)}, "
            f"inserted unexpectedly {sorted(added - INSERTED_RULE_IDS)}"
        )

    for rule_id, rule in after_rules.items():
        if rule_id in INSERTED_RULE_IDS:
            continue
        before_rule = before_rules[rule_id]
        if rule_id in MODIFIED_RULE_IDS:
            if before_rule.get("on_unknown") != "HUMAN_REVIEW":
                _fail(f"{rule_id!r}: expected on_unknown HUMAN_REVIEW before the fold")
            if rule.get("on_unknown") != "NEEDS_INPUT":
                _fail(f"{rule_id!r}: expected on_unknown NEEDS_INPUT after the fold")
            reconstructed = {**before_rule, "on_unknown": "NEEDS_INPUT"}
            if _canon(reconstructed) != _canon(rule):
                _fail(f"rule {rule_id!r} changed a field other than on_unknown")
            continue
        if _canon(rule) != _canon(before_rule):
            _fail(
                f"rule {rule_id!r} drifted from seq-22 — this fold retires 8, "
                "inserts 11 and modifies on_unknown on 4, nothing else"
            )


def assert_changed_fields_hold_their_expected_values(
    after: dict[str, Any], *, expected_new_rules: list[dict[str, Any]]
) -> None:
    expected: dict[str, Any] = {
        "sequence": 23,
        "rule_pack_id": str(_rule_pack_id(23)),
        "version": FOLD_VERSION,
        "created_at": FOLD_CREATED_AT,
        "created_by": FOLD_CREATED_BY,
        "previous_payload_sha256": SEQ22_PAYLOAD_SHA256,
        "rollback_of_payload_sha256": None,
    }
    for key, want in expected.items():
        got = after.get(key)
        if got != want:
            _fail(f"{key} is {got!r}, expected {want!r}")

    rules_by_id = _rules_by_id(after)
    for rule_id in REMOVED_RULE_IDS:
        if rule_id in rules_by_id:
            _fail(f"rule {rule_id!r} should have been retired but is still present")

    by_id = {rule["rule_id"]: rule for rule in expected_new_rules}
    for rule_id in INSERTED_RULE_IDS:
        if _canon(rules_by_id.get(rule_id)) != _canon(by_id[rule_id]):
            _fail(f"{rule_id!r} in the output is not the rule this fold built")


def _assert_candidate_review_inventory(payload: dict[str, Any]) -> None:
    """A8.4: the derived inventory target. Imported lazily — this module is
    imported by `review_hold_inventory.py`'s own tests, and a top-level
    import cycle is not worth the two functions this needs."""

    from backend.scripts.visa_engine.review_hold_inventory import (
        pack_review_rules,
        pack_unknown_escalations,
    )

    validated = RulePackPayload.model_validate(payload)
    review_rules = pack_review_rules(validated)
    if len(review_rules) != 1 or review_rules[0].rule_id != STUDIO_RULE_ID:
        _fail(
            f"pack_review_rules returned {[e.rule_id for e in review_rules]!r}, "
            f"expected exactly [{STUDIO_RULE_ID!r}]"
        )
    escalations = pack_unknown_escalations(validated)
    if escalations:
        _fail(
            f"pack_unknown_escalations returned {[e.rule_id for e in escalations]!r}, "
            "expected none — every on_unknown: HUMAN_REVIEW producer must be gone"
        )


def fold(
    seq22: dict[str, Any], seq22_signed: dict[str, Any], *, observed_at: datetime | None = None
) -> dict[str, Any]:
    digest = hashlib.sha256(canonicalize_json(seq22)).hexdigest()
    if digest != SEQ22_PAYLOAD_SHA256:
        _fail(
            f"the seq-22 source is not the activated artifact: recomputed JCS "
            f"digest {digest} != {SEQ22_PAYLOAD_SHA256}"
        )
    assert_anchor_is_a_verified_signed_artifact(seq22_signed, digest, observed_at=observed_at)
    if seq22.get("sequence") != 22:
        _fail(f"expected sequence 22, got {seq22.get('sequence')!r}")

    inherited_id = seq22.get("rule_pack_id")
    expected_22_id = str(_rule_pack_id(22))
    if inherited_id != expected_22_id:
        _fail(
            f"the seq-22 payload carries rule_pack_id={inherited_id!r}, but the "
            f"uuid5 convention yields {expected_22_id!r}"
        )

    _assert_removed_rules_are_dormant(seq22)
    _assert_modified_rules_are_the_expected_shape(seq22)
    _assert_studio_rule_is_present_and_unchanged_from(seq22)

    out = json.loads(json.dumps(seq22))
    new_rules = build_new_rules(seq22)

    existing_rules = out.get("rules", [])
    filtered_rules = [rule for rule in existing_rules if rule["rule_id"] not in REMOVED_RULE_IDS]
    for rule in filtered_rules:
        if rule["rule_id"] in MODIFIED_RULE_IDS:
            rule["on_unknown"] = "NEEDS_INPUT"
    out["rules"] = filtered_rules + new_rules

    out["sequence"] = 23
    out["rule_pack_id"] = str(_rule_pack_id(23))
    out["version"] = FOLD_VERSION
    out["created_at"] = FOLD_CREATED_AT
    out["created_by"] = FOLD_CREATED_BY
    out["previous_payload_sha256"] = SEQ22_PAYLOAD_SHA256
    out["rollback_of_payload_sha256"] = None

    assert_only_expected_changes(seq22, out)
    assert_changed_fields_hold_their_expected_values(out, expected_new_rules=new_rules)
    assert_no_hard_filter_reads_a_synthesised_twin_basis_fact(out)
    _assert_candidate_review_inventory(out)
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
    parser = argparse.ArgumentParser(description="Fold RulePack seq-23 (candidate) from seq-22.")
    parser.add_argument("--seq22-source", required=True, type=Path)
    parser.add_argument(
        "--seq22-signed",
        type=Path,
        default=None,
        help="the signed seq-22 envelope; defaults to the .signed.json sibling of --seq22-source",
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    if args.seq22_signed is not None:
        signed_path = args.seq22_signed
    else:
        source_str = str(args.seq22_source)
        if not source_str.endswith(".source.json"):
            _fail(
                f"--seq22-source {source_str!r} does not end in '.source.json' — "
                "cannot derive the signed sibling path; pass --seq22-signed explicitly"
            )
        signed_path = Path(source_str[: -len(".source.json")] + ".signed.json")
    if signed_path == args.seq22_source or not signed_path.exists():
        _fail(f"no signed seq-22 bundle at {signed_path} — pass --seq22-signed")

    _assert_output_does_not_collide_with_inputs(
        args.output,
        {"--seq22-source": args.seq22_source, "--seq22-signed": signed_path},
    )

    seq22 = json.loads(args.seq22_source.read_text(encoding="utf-8"))
    seq22_signed = json.loads(signed_path.read_text(encoding="utf-8"))
    seq23 = fold(seq22, seq22_signed, observed_at=observed_at)
    args.output.write_text(json.dumps(seq23, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    digest = hashlib.sha256(canonicalize_json(seq23)).hexdigest()
    print(f"fold_pack_seq23: wrote {args.output}")
    print(f"fold_pack_seq23: seq-23 payload_sha256 = {digest}")
    print(f"fold_pack_seq23: retired {len(REMOVED_RULE_IDS)} REQUIRE_REVIEW rules")
    print(f"fold_pack_seq23: inserted {len(INSERTED_RULE_IDS)} HARD_FILTER rules")
    print(f"fold_pack_seq23: modified on_unknown on {len(MODIFIED_RULE_IDS)} existing HARD_FILTER rules")
    print("fold_pack_seq23: NOT SIGNED, NOT ACTIVATED — see sign_pack.py / activate_pack.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
