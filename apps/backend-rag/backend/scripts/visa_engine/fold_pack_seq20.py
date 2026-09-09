"""fold_pack_seq20.py — the decisiveness fold: lawful stay-day totals, E33G
unmasked, unaskable gates made NO_EFFECT, BRIDGING support made explicit, and
CL-D2-01's local-compensation prohibition finally compiled.

WHY, AND WHAT IT COSTS
======================
``research/visa/2026-09-06-visa-oracle-decisiveness-investigation.md`` measured
the live funnel on the signed seq-19 pack and found it correct and almost never
decisive: 36 of 43 real interview walks end in ``NEEDS_INPUT`` on a fact the
interview has no question for. Three layers cause that; §2.3 of the
investigation isolates the layer that lives in the PACK, and this fold is that
layer's repair. It is PR-1 of a five-PR wave and ships SOURCE ONLY — the owner
signs on M5, a session activates, neither happens here.

The five edits below are the §4 "PR-1" list, and each of the two that are legal
claims rather than mechanics was RULED by the owner on 2026-09-06 ("seguo le tue
raccomandazioni, go", §5 Rulings): decision 1 (caps encode the lawful extendable
total) and decision 2 (CL-D2-01 compiled as EXCLUDE, not REQUIRE_REVIEW), plus
decision 5 (no browser certification of an ITAS sponsor's status code — the
eight blocking rules become ``NO_EFFECT``).

THE FIVE EDITS, BY RULE ID
==========================
1. **Stay-day caps → the lawful extendable total** (owner decision 1). The
   ``intent.stay_days lte`` bounds in seq-19 encode the FIRST GRANT, not the
   total a holder may lawfully reach by extension, so five complete-fact
   personas are told "no path" for a stay Indonesian practice grants
   (investigation §3.1). Seven SUPPORT rules gate the visit-visa family —
   ``el.b1.tourism`` 30→60, ``el.c1.tourism-family`` / ``el.c2.business`` /
   ``el.c6.social`` / ``el.d1-multi-entry-support`` / ``el.d2-multi-entry-support``
   60→180, ``el.d12-multi-entry-support`` 180→360 — but the D1/D2/D12
   document-requirement siblings carry the SAME old bound. They do not block
   support (``hit_policy.eligibility = COVER_ALL_DECLARED_PURPOSES`` only needs
   the covering rule), yet leaving them behind silently drops the document
   checklist for a 121-day applicant, so all 22 move together.

   ``el.a1.tourism`` is the 23rd rule carrying such a bound and is
   DELIBERATELY NOT MOVED: A1 is the visa-exemption (BVK) entry, whose 30 days
   are non-extendable by regulation — its cap already IS the lawful total, and
   the investigation's own edit list (§4 PR-1 edit 1) names seven rules, never
   A1. :func:`_assert_stay_day_cap_census` makes that exemption explicit rather
   than accidental: a future rule that grows a ``stay_days`` bound and is
   neither bumped nor named here aborts the fold.

2. **``review.e33g.income-evidence`` retired.** Its ``when`` is a byte-for-byte
   copy of ``el.e33g.remote-work``'s four-clause conjunction, so it fires on
   the product's own success condition and REVIEW beats SUPPORTED
   (evaluator.py's state precedence). E33G — the pack's only REMOTE_WORK
   product — can therefore never be recommended. The copy relationship is the
   whole justification, so it is CHECKED at fold time
   (:func:`_assert_retired_rule_is_a_copy_of_its_support_twin`), not asserted
   in this docstring: if a future base pack gives the review rule a
   discriminating condition of its own, this fold refuses rather than deleting
   a rule that had become real.

3. **The eight ``family.sponsor_status_code`` rules → ``on_unknown: NO_EFFECT``**
   (owner decision 5). ``fact-mapper.ts`` deliberately returns
   ``unknownFact(UNVERIFIED)`` for every answer to that question — a
   self-declared status label must never satisfy ``op: known`` — so the fact
   can never be KNOWN from the browser and ``NEEDS_INPUT`` is a request the
   funnel cannot honour. ``NO_EFFECT`` on a SUPPORT rule is fail-CLOSED: the
   rule simply does not fire, E31B/E31E/E31H/E31J stay out of the candidate
   set exactly as they are today, and the rest of the decision proceeds
   instead of dying with them. ``el.e31j-dependency-age`` reads the same fact
   and is ALREADY ``NO_EFFECT`` — it is the ninth reader and is not in the
   edit set; :func:`_assert_sponsor_status_census` derives the split from the
   pack rather than trusting this comment.

4. **The four BRIDGING rules conjoin ``known``.** Each is
   ``effect.type: SUPPORT`` guarded on
   ``intent.requested_product_code neq "BRIDGING"``, and ``neq`` is TRUE for
   any value other than that literal — so any KNOWN value would manufacture
   support with reason ``BRIDGING_DESTINATION_STATED``, a claim that a
   destination product was named when none was. Today the fact is permanently
   UNKNOWN, which makes the hazard latent rather than live (investigation §6
   R2 measured it firing). Conjoining
   ``{"fact": "intent.requested_product_code", "op": "known"}`` states the
   premise the reason code already asserts, and — because a presence test on
   an absent fact is a DEFINITE FALSE under Kleene ``all`` (ast.py's
   ``PresenceCondition``) — it also stops ``el.bridging.destination-stated``
   from blocking on a fact nothing can supply.

5. **New rule ``hf.d2.indonesia-source-compensation``** (owner decision 2).
   Nothing in seq-19 compiles CL-D2-01's "absolute prohibition on subordinate
   employment or local compensation"
   (``research/visa/doctrine-factory/claims/e2a-claim-ledger.md``): the
   ledger's own ``Backs:`` line names only ``el.d2-multi-entry-support``,
   which reads ``intent.purposes`` and ``intent.stay_days`` and nothing else.
   Measured consequence today: BUSINESS_MEETINGS + 60d +
   ``work.indonesia_source_compensation = true`` returns
   ``SUPPORTED_CANDIDATES [D2]`` with no review. The new HARD_FILTER/EXCLUDE
   is scoped to C2/D1/D2 and guarded on the purpose, so it is definitely FALSE
   — never UNKNOWN — for every non-business interview.

WHAT IS DELIBERATELY *NOT* DONE HERE
=====================================
No signing, no activation: this script only ever writes the unsigned SOURCE
file (``sign_pack.py`` is the owner's offline ceremony, ``activate_pack.py`` a
separate later act). No evaluator change (that is PR-2), no interview change
(PR-3), no review-flag change (PR-4). Nothing in ``products``,
``source_records`` or the other 100 rules moves — ``assert_only_expected_changes``
requires universal equality for every key this fold does not name, so a field
added by some future sequence is guarded automatically instead of escaping an
allow-list.

Usage::

    PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq20 \\
        --seq19-source <path to rulepack-prod-019.source.json> \\
        --output <seq-20 source path>

``--seq19-signed`` defaults to the ``.signed.json`` sibling of
``--seq19-source`` and the fold refuses to run without one: the anchor is
verified by SIGNATURE, never by a digest constant alone.
``VISA_ENGINE_TRUST_STORE_KEYS_JSON`` (the production PUBLIC key) must be
exported — its absence is a refusal, not a skipped check.

The ceremony is fold-THEN-prettier: after this script writes the source file,
run ``npx prettier --write`` on it FROM THE REPO ROOT (so the project's own
``.prettierignore``/config resolution applies rather than whatever a stray cwd
would pick up), because that is the shape every pack on ``main`` already
carries — ``rulepack-prod-018.source.json`` and ``rulepack-prod-019.source.json``
are both prettier-clean. It is safe because the payload digest is the SHA-256 of
:func:`~backend.services.visa_engine.bundle.canonicalize_json` over the PARSED
document and prettier's JSON printer is semantics-preserving, so reformatting
the bytes does not move it. That is a contingent invariant, not a mathematical
one, so it is CHECKED rather than trusted:
``test_seq20_pack.py::TestIdentity::test_payload_digest_survives_reformatting_of_the_file``
pins the digest, and ``test_fold_is_deterministic_and_matches_disk`` compares
the fold's output to the PARSED file, so a reformat that changed content fails
loudly instead of surfacing at signing time.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.services.visa_engine.bundle import (
    RulePackVerificationError,
    StaticTrustStore,
    canonicalize_json,
    verify_rule_pack,
)
from backend.services.visa_engine.models import RulePackPayload

#: The seq-19 payload digest — this fold's chain anchor, and the digest
#: production is serving now. Measured this session from
#: ``rulepack-prod-019.signed.json``'s own ``payload_sha256`` AND by
#: re-hashing ``rulepack-prod-019.source.json`` (both agree); the
#: investigation's three live probes read the same value back off
#: ``nuzantara-rag.fly.dev``.
SEQ19_PAYLOAD_SHA256 = "bac5da8e4727e7f639c947c50211e6f95e15c1403cf6aef0dd57a92014d6e6ea"

FOLD_CREATED_AT = "2026-09-06T00:00:00Z"
FOLD_CREATED_BY = "agent.air-m5.backend-rag.visa-oracle-decisiveness-seq20.fold-2026-09-06"
FOLD_VERSION = "2026.9.6"

_RULE_PACK_ID_URL_PREFIX = (
    "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/"
)

STAY_DAYS_FACT = "intent.stay_days"
REQUESTED_PRODUCT_FACT = "intent.requested_product_code"
SPONSOR_STATUS_FACT = "family.sponsor_status_code"

#: Edit 1. ``rule_id -> (bound seq-19 must currently carry, bound seq-20 sets)``.
#: The old value is declared, not discovered, so a base pack whose bound has
#: already moved aborts instead of being silently overwritten.
STAY_DAY_CAPS: dict[str, tuple[int, int]] = {
    # The seven SUPPORT rules that gate the visit-visa family.
    "el.b1.tourism": (30, 60),
    "el.c1.tourism-family": (60, 180),
    "el.c2.business": (60, 180),
    "el.c6.social": (60, 180),
    "el.d1-multi-entry-support": (60, 180),
    "el.d2-multi-entry-support": (60, 180),
    "el.d12-multi-entry-support": (180, 360),
    # The fifteen document-requirement siblings that carry the same bound and
    # would otherwise drop the checklist for a long-stay applicant.
    "el.d1-passport-validity": (60, 180),
    "el.d1-funds-usd-2000": (60, 180),
    "el.d1-cv-required": (60, 180),
    "el.d1-itinerary-required": (60, 180),
    "el.d1-support-letter": (60, 180),
    "el.d2-passport-validity": (60, 180),
    "el.d2-funds-usd-2000": (60, 180),
    "el.d2-cv-required": (60, 180),
    "el.d2-itinerary-required": (60, 180),
    "el.d2-support-letter": (60, 180),
    "el.d12-passport-validity": (180, 360),
    "el.d12-funds-usd-5000": (180, 360),
    "el.d12-cv-required": (180, 360),
    "el.d12-itinerary-required": (180, 360),
    "el.d12-support-letter": (180, 360),
}

#: The one rule carrying a ``stay_days`` bound that this fold must NOT move:
#: A1 is the visa-exemption (BVK) entry and its 30 days are not extendable, so
#: its cap already encodes the lawful total. Named here so the census check
#: distinguishes "deliberately exempt" from "forgotten".
STAY_DAY_CAP_EXEMPT_RULE_IDS: frozenset[str] = frozenset({"el.a1.tourism"})

#: Edit 2. Retired because its ``when`` is a byte-copy of its SUPPORT twin's.
REMOVED_RULE_IDS: frozenset[str] = frozenset({"review.e33g.income-evidence"})
#: ``retired rule -> the SUPPORT rule it must be a byte-copy of``.
RETIRED_RULE_SUPPORT_TWIN: dict[str, str] = {
    "review.e33g.income-evidence": "el.e33g.remote-work",
}

#: Edit 3. The eight rules that read a fact the browser can never certify and
#: block the whole decision on it.
SPONSOR_STATUS_NO_EFFECT_RULE_IDS: tuple[str, ...] = (
    "el.e31b-spouse-itas-support",
    "el.e31b-sponsor-itas-itap",
    "el.e31e-child-itas-support",
    "el.e31e-sponsor-itas-itap",
    "el.e31h-parent-itas-child-support",
    "el.e31h-sponsor-itas-itap",
    "el.e31j-sibling-itas-support",
    "el.e31j-sponsor-itas-itap",
)

#: Edit 4. The four SUPPORT rules guarded on ``neq "BRIDGING"``.
BRIDGING_RULE_IDS: tuple[str, ...] = (
    "el.bridging.destination-stated",
    "el.bridging.t3-window-manual",
    "el.bridging.overstay-shield-payment",
    "el.bridging.source-status-verify",
)

#: Edit 5.
NEW_RULE_ID = "hf.d2.indonesia-source-compensation"
NEW_RULE_PRODUCT_CODES: tuple[str, ...] = ("C2", "D1", "D2")
#: The rule whose ``source_refs`` the new rule inherits: CL-D2-01's ``Backs:``
#: line names exactly this rule, so its citations are the claim's citations.
#: Copied from the pack, never hand-authored here.
NEW_RULE_SOURCE_DONOR_RULE_ID = "el.d2-multi-entry-support"
NEW_RULE_VALID_FROM = "2026-09-06T00:00:00Z"

EDITED_RULE_IDS: tuple[str, ...] = (
    tuple(STAY_DAY_CAPS) + SPONSOR_STATUS_NO_EFFECT_RULE_IDS + BRIDGING_RULE_IDS
)

#: Which fields each edit is allowed to move, keyed by rule id. Per-rule-id
#: rather than a union across the whole edit set, so a stray ``on_unknown``
#: drift on a cap rule (or a stray ``when`` drift on a sponsor rule) is caught
#: instead of being excluded from comparison for everybody.
_ALLOWED_MOVED_FIELDS: dict[str, frozenset[str]] = {
    **{rule_id: frozenset({"when"}) for rule_id in STAY_DAY_CAPS},
    **{rule_id: frozenset({"on_unknown"}) for rule_id in SPONSOR_STATUS_NO_EFFECT_RULE_IDS},
    **{rule_id: frozenset({"when"}) for rule_id in BRIDGING_RULE_IDS},
}

#: The only top-level keys this fold may move; `rules` moves too (retire +
#: edit + insert) but is diffed at the rule level, not by whole-value equality.
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


def _fail(message: str) -> None:
    raise SystemExit(f"fold_pack_seq20: {message}")


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


def assert_anchor_is_a_verified_signed_artifact(
    signed_envelope: dict[str, Any],
    digest: str,
    *,
    observed_at: datetime | None = None,
) -> None:
    """Require the chain anchor to be a SIGNED seq-19 pack, not just a digest.

    Same shape as ``fold_pack_seq19.assert_anchor_is_a_verified_signed_artifact``
    — that one is pinned to sequence 18 by its own final check, so it is
    reproduced here pinned to 19 rather than parameterised after the fact.
    """
    try:
        trust_store = StaticTrustStore.from_env()
    except RulePackVerificationError as exc:
        _fail(
            f"cannot verify the seq-19 anchor's signature: {exc}. Export the "
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
        _fail(f"the seq-19 signed bundle does not verify: {exc}")

    signed_digest = verified.payload_sha256.hex()
    if signed_digest != digest:
        _fail(
            f"the seq-19 SOURCE digest {digest} is not the digest of the signed "
            f"seq-19 artifact ({signed_digest}) — the source on disk and the "
            "artifact production verifies are two different payloads."
        )
    if verified.pack.payload.sequence != 19:
        _fail(
            "the signed bundle handed in as the seq-19 anchor carries sequence "
            f"{verified.pack.payload.sequence}"
        )


# ---------------------------------------------------------------------------
# Pre-flight census checks — each edit's premise, verified against the base
# pack rather than trusted from the docstring.
# ---------------------------------------------------------------------------


def _stay_days_bound_nodes(rule: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        node
        for node in _nodes(rule.get("when"))
        if node.get("fact") == STAY_DAYS_FACT and node.get("op") == "lte"
    ]


def _assert_stay_day_cap_census(payload: dict[str, Any]) -> None:
    """Every rule carrying an ``intent.stay_days lte`` bound must be either
    bumped by this fold or NAMED as exempt.

    The failure this prevents is the one edit 1's own note calls a trap: the
    document-requirement siblings carry the same bound as the covering SUPPORT
    rule, do not block support, and so move a 121-day applicant's checklist
    without moving their verdict. An allow-list of ids to bump cannot see a
    sibling somebody adds later; a census of ids that CARRY the bound can.
    """
    carriers = {rule["rule_id"] for rule in payload["rules"] if _stay_days_bound_nodes(rule)}
    accounted = set(STAY_DAY_CAPS) | STAY_DAY_CAP_EXEMPT_RULE_IDS
    unaccounted = carriers - accounted
    if unaccounted:
        _fail(
            f"rule(s) {sorted(unaccounted)} carry an '{STAY_DAYS_FACT} lte' bound "
            "but are neither in STAY_DAY_CAPS nor named exempt — a stay-day cap "
            "this fold does not decide about is a checklist (or a verdict) left "
            "at the first-grant number. Bump it or name it exempt, with a reason."
        )
    missing = accounted - carriers
    if missing:
        _fail(
            f"rule(s) {sorted(missing)} are declared here but carry no "
            f"'{STAY_DAYS_FACT} lte' bound in the base pack — the edit set is "
            "stale against the pack it is being folded onto."
        )


def _assert_retired_rule_is_a_copy_of_its_support_twin(
    rules_by_id: dict[str, dict[str, Any]],
) -> None:
    """Retire ``review.e33g.income-evidence`` only while it remains a
    byte-copy of ``el.e33g.remote-work``'s ``when``.

    That copy relationship IS the justification: a review rule whose condition
    is its product's own success condition is an unconditional veto, not a
    legal finding. If a future base pack gives the review rule a discriminating
    condition (an income floor, say), it has become a real rule and deleting it
    would be a fail-OPEN — so this refuses instead.
    """
    for retired_id, twin_id in RETIRED_RULE_SUPPORT_TWIN.items():
        retired = rules_by_id.get(retired_id)
        twin = rules_by_id.get(twin_id)
        if retired is None or twin is None:
            _fail(
                f"cannot check the retirement of {retired_id!r}: it or its "
                f"SUPPORT twin {twin_id!r} is missing from the base pack"
            )
        if _canon(retired["when"]) != _canon(twin["when"]):
            _fail(
                f"{retired_id!r}'s `when` is no longer byte-identical to "
                f"{twin_id!r}'s — it has acquired a discriminating condition of "
                "its own, so retiring it would drop a real review gate. Refusing."
            )
        if retired["effect"]["type"] != "REQUIRE_REVIEW":
            _fail(f"{retired_id!r} is not a REQUIRE_REVIEW rule — refusing to retire it")


def _assert_sponsor_status_census(payload: dict[str, Any]) -> None:
    """The set of rules reading ``family.sponsor_status_code`` with a blocking
    ``on_unknown`` must be EXACTLY the eight this fold names.

    Derived from the pack, not trusted: a ninth reader
    (``el.e31j-dependency-age``) is already ``NO_EFFECT`` and must stay out of
    the edit set, and a tenth added by a future fold must not be silently left
    blocking a fact the browser cannot certify.
    """
    blocking = {
        rule["rule_id"]
        for rule in payload["rules"]
        if SPONSOR_STATUS_FACT in (rule.get("required_facts") or [])
        and rule["on_unknown"] != "NO_EFFECT"
    }
    declared = set(SPONSOR_STATUS_NO_EFFECT_RULE_IDS)
    if blocking != declared:
        _fail(
            f"the rules blocking on {SPONSOR_STATUS_FACT} are {sorted(blocking)}, "
            f"not the declared {sorted(declared)} — the edit set is stale"
        )
    for rule_id in declared:
        rule = _rules_by_id(payload)[rule_id]
        if rule["effect"]["type"] != "SUPPORT":
            _fail(
                f"{rule_id!r} is a {rule['effect']['type']} rule — NO_EFFECT is "
                "fail-closed for SUPPORT and this fold makes no claim about any "
                "other effect type"
            )


def _bridging_neq_nodes(rule: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        node
        for node in _nodes(rule.get("when"))
        if node.get("fact") == REQUESTED_PRODUCT_FACT and node.get("op") == "neq"
    ]


def _assert_bridging_census(payload: dict[str, Any]) -> None:
    """Every SUPPORT rule guarded on ``requested_product_code neq`` must be one
    of the four this fold conjoins ``known`` onto, and each must not already
    carry a presence test on that fact."""
    guarded = {
        rule["rule_id"]
        for rule in payload["rules"]
        if rule["effect"]["type"] == "SUPPORT" and _bridging_neq_nodes(rule)
    }
    declared = set(BRIDGING_RULE_IDS)
    if guarded != declared:
        _fail(
            f"the SUPPORT rules guarded on '{REQUESTED_PRODUCT_FACT} neq' are "
            f"{sorted(guarded)}, not the declared {sorted(declared)} — a SUPPORT "
            "rule that can manufacture support from an unstated request is "
            "exactly what edit 4 exists to close, so refusing to fold past it"
        )
    rules_by_id = _rules_by_id(payload)
    for rule_id in declared:
        rule = rules_by_id[rule_id]
        if rule["when"].get("op") != "all":
            _fail(
                f"{rule_id!r}'s `when` is a {rule['when'].get('op')!r} node, not "
                "`all` — conjoining a premise onto it is only sound for `all`"
            )
        already = [
            node
            for node in _nodes(rule["when"])
            if node.get("fact") == REQUESTED_PRODUCT_FACT and node.get("op") in ("known", "unknown")
        ]
        if already:
            _fail(f"{rule_id!r} already carries a presence test on {REQUESTED_PRODUCT_FACT}")


def _freshness_horizon(source: dict[str, Any]) -> datetime:
    """The instant a source record stops being CURRENT.

    Only ``MAX_AGE_SINCE_VERIFIED_AT`` is understood; any other policy kind is
    a refusal rather than a guess, because guessing here would silently weaken
    the check :func:`_assert_new_rule_shortens_no_freshness_horizon` performs.
    """
    policy = source.get("freshness_policy") or {}
    if policy.get("kind") != "MAX_AGE_SINCE_VERIFIED_AT":
        _fail(
            f"source {source['source_record_id']} carries freshness policy "
            f"{policy.get('kind')!r}, which this fold does not model — refusing "
            "to reason about the safety-critical staleness horizon"
        )
    verified_at = source.get("verified_at")
    if not verified_at:
        _fail(f"source {source['source_record_id']} has no verified_at")
    return datetime.fromisoformat(verified_at.replace("Z", "+00:00")) + timedelta(
        seconds=policy["max_age_seconds"]
    )


def _assert_new_rule_shortens_no_freshness_horizon(
    payload: dict[str, Any], new_source_refs: list[str]
) -> None:
    """``_apply_safety_critical_source_hold`` (evaluate_path.py) is GLOBAL: it
    unions the ``source_refs`` of every ACTIVE safety-critical rule, fired or
    not, and abstains for the whole decision if any of them is not CURRENT.

    So adding a ``safety_critical: true`` rule adds its citations to that
    union, and a citation with an earlier staleness horizon than the union's
    current minimum would make the entire engine start returning
    HUMAN_REVIEW_REQUIRED sooner than it does today — the opposite of this
    wave's purpose, and invisible until the day it fires. Measured this run
    rather than argued: the new rule's refs must not shorten the horizon.
    """
    sources = {source["source_record_id"]: source for source in payload["source_records"]}
    existing_refs: set[str] = set()
    for rule in payload["rules"]:
        if rule["safety_critical"]:
            existing_refs.update(rule["source_refs"])
    if not existing_refs:
        _fail("the base pack has no safety-critical rule — this check cannot calibrate")
    current_floor = min(_freshness_horizon(sources[ref]) for ref in existing_refs)
    for ref in new_source_refs:
        source = sources.get(ref)
        if source is None:
            _fail(f"{NEW_RULE_ID} cites source {ref}, which is not in the pack")
        horizon = _freshness_horizon(source)
        if horizon < current_floor:
            _fail(
                f"{NEW_RULE_ID} cites source {ref}, whose freshness horizon "
                f"({horizon.isoformat()}) is EARLIER than the safety-critical "
                f"union's current floor ({current_floor.isoformat()}) — adding it "
                "would make the global source hold start abstaining sooner than "
                "it does today. Re-verify that source first."
            )


# ---------------------------------------------------------------------------
# The edits themselves.
# ---------------------------------------------------------------------------


def _bump_stay_day_caps(rules_by_id: dict[str, dict[str, Any]]) -> None:
    for rule_id, (old, new) in STAY_DAY_CAPS.items():
        rule = rules_by_id.get(rule_id)
        if rule is None:
            _fail(f"rule {rule_id!r} not found — cannot bump its stay-day cap")
        bounds = _stay_days_bound_nodes(rule)
        if len(bounds) != 1:
            _fail(
                f"rule {rule_id!r} carries {len(bounds)} '{STAY_DAYS_FACT} lte' "
                "bounds; exactly one is required to bump it unambiguously"
            )
        if bounds[0]["value"] != old:
            _fail(
                f"rule {rule_id!r}'s stay-day bound is {bounds[0]['value']!r}, not "
                f"the declared {old!r} — the base pack has already moved it"
            )
        bounds[0]["value"] = new


def _make_sponsor_rules_no_effect(rules_by_id: dict[str, dict[str, Any]]) -> None:
    for rule_id in SPONSOR_STATUS_NO_EFFECT_RULE_IDS:
        rules_by_id[rule_id]["on_unknown"] = "NO_EFFECT"


def _conjoin_requested_product_known(rules_by_id: dict[str, dict[str, Any]]) -> None:
    """Append the presence premise to each BRIDGING rule's TOP-LEVEL ``all``.

    Three of the four nest a second ``all`` around the ``neq``; conjunction is
    associative, so appending at the top level is the same predicate and does
    not require this fold to understand each rule's internal shape.
    """
    for rule_id in BRIDGING_RULE_IDS:
        rule = rules_by_id[rule_id]
        rule["when"]["args"] = list(rule["when"]["args"]) + [
            {"op": "known", "fact": REQUESTED_PRODUCT_FACT}
        ]


def build_new_rule(payload: dict[str, Any]) -> dict[str, Any]:
    """CL-D2-01 as an EXCLUDE, with its scope and citations DERIVED from the
    pack (product version ids from the catalog, source refs from the rule the
    ledger's own ``Backs:`` line names) rather than hand-transcribed."""
    versions = {
        product["product_code"]: product["product_version_id"] for product in payload["products"]
    }
    missing = [code for code in NEW_RULE_PRODUCT_CODES if code not in versions]
    if missing:
        _fail(f"product code(s) {missing} are not in the catalog — cannot scope {NEW_RULE_ID}")
    donor = _rules_by_id(payload).get(NEW_RULE_SOURCE_DONOR_RULE_ID)
    if donor is None:
        _fail(
            f"{NEW_RULE_SOURCE_DONOR_RULE_ID!r} is missing — it is the rule "
            "CL-D2-01 declares it backs, and the new rule inherits its citations"
        )
    return {
        "when": {
            "op": "all",
            "args": [
                {
                    "op": "intersects",
                    "fact": "intent.purposes",
                    "values": ["BUSINESS_MEETINGS"],
                },
                {
                    "op": "eq",
                    "fact": "work.indonesia_source_compensation",
                    "value": True,
                },
            ],
        },
        "scope": "PRODUCTS",
        "stage": "HARD_FILTER",
        "effect": {
            "type": "EXCLUDE",
            "reason_code": "BUSINESS_LOCAL_COMPENSATION_NOT_ALLOWED",
        },
        "rule_id": NEW_RULE_ID,
        "priority": 100,
        "on_unknown": "NEEDS_INPUT",
        "source_refs": list(donor["source_refs"]),
        "valid_period": {"to": None, "from": NEW_RULE_VALID_FROM},
        "required_facts": [
            "intent.purposes",
            "work.indonesia_source_compensation",
        ],
        "explanation_key": f"explain.{NEW_RULE_ID}",
        "safety_critical": True,
        "product_version_ids": [versions[code] for code in NEW_RULE_PRODUCT_CODES],
    }


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
            _fail(f"{key} changed — this fold edits/retires/inserts rules and nothing else")

    before_rules = _rules_by_id(before)
    after_rules = _rules_by_id(after)

    missing = set(before_rules) - set(after_rules)
    if missing != REMOVED_RULE_IDS:
        _fail(f"removed-rule set mismatch: {sorted(missing)} != {sorted(REMOVED_RULE_IDS)}")
    added = set(after_rules) - set(before_rules)
    if added != {NEW_RULE_ID}:
        _fail(f"added-rule set mismatch: {sorted(added)} != [{NEW_RULE_ID!r}]")

    for rule_id, rule in after_rules.items():
        if rule_id == NEW_RULE_ID:
            continue
        before_rule = before_rules[rule_id]
        if rule_id in _ALLOWED_MOVED_FIELDS:
            if _canon(rule) == _canon(before_rule):
                _fail(f"rule {rule_id!r} is byte-identical to seq-19 — its edit did not land")
            allowed = _ALLOWED_MOVED_FIELDS[rule_id]
            # Union of both sides, not just ``set(rule)``: a field the base HAD
            # and an edit silently DROPPED would otherwise never enter the loop.
            for field in (set(rule) | set(before_rule)) - allowed:
                if _canon(rule.get(field)) != _canon(before_rule.get(field)):
                    _fail(
                        f"rule {rule_id!r} field {field!r} moved — only "
                        f"{sorted(allowed)} may move on this rule"
                    )
        elif _canon(rule) != _canon(before_rule):
            _fail(f"rule {rule_id!r} drifted from seq-19 — it is not in the declared edit set")


def assert_changed_fields_hold_their_expected_values(
    after: dict[str, Any], *, expected_new_rule: dict[str, Any]
) -> None:
    """:func:`assert_only_expected_changes` names what MAY move and excludes it
    from comparison — silent on whether it moved to the RIGHT thing. Pinned
    separately, per the lesson seq-18's review recorded: a guard whose
    fail-closedness holds only while the code above it stays correct is not a
    guard, it is a comment."""
    expected: dict[str, Any] = {
        "sequence": 20,
        "rule_pack_id": str(_rule_pack_id(20)),
        "version": FOLD_VERSION,
        "created_at": FOLD_CREATED_AT,
        "created_by": FOLD_CREATED_BY,
        "previous_payload_sha256": SEQ19_PAYLOAD_SHA256,
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

    for rule_id, (_old, new) in STAY_DAY_CAPS.items():
        bounds = _stay_days_bound_nodes(rules_by_id[rule_id])
        if len(bounds) != 1 or bounds[0]["value"] != new:
            _fail(f"rule {rule_id!r}'s stay-day bound is not the expected {new!r}")
    for rule_id in STAY_DAY_CAP_EXEMPT_RULE_IDS:
        if rule_id in rules_by_id and not _stay_days_bound_nodes(rules_by_id[rule_id]):
            _fail(f"exempt rule {rule_id!r} lost its stay-day bound")

    for rule_id in SPONSOR_STATUS_NO_EFFECT_RULE_IDS:
        if rules_by_id[rule_id]["on_unknown"] != "NO_EFFECT":
            _fail(f"rule {rule_id!r} is not NO_EFFECT")

    for rule_id in BRIDGING_RULE_IDS:
        when = rules_by_id[rule_id]["when"]
        presence = [
            node
            for node in _nodes(when)
            if node.get("fact") == REQUESTED_PRODUCT_FACT and node.get("op") == "known"
        ]
        if len(presence) != 1:
            _fail(f"rule {rule_id!r} does not carry exactly one `known` premise")
        if not _bridging_neq_nodes(rules_by_id[rule_id]):
            _fail(f"rule {rule_id!r} lost its `neq BRIDGING` guard")

    if _canon(rules_by_id.get(NEW_RULE_ID)) != _canon(expected_new_rule):
        _fail(f"{NEW_RULE_ID!r} in the output is not the rule this fold built")


def fold(
    seq19: dict[str, Any],
    seq19_signed: dict[str, Any],
    *,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Return the seq-20 payload, or abort loudly.

    ``seq19_signed`` is the signed seq-19 envelope and is REQUIRED, not
    optional — see :func:`assert_anchor_is_a_verified_signed_artifact`.
    ``observed_at`` is threaded into that signature check's clock so a test
    pinning it is not left real-clock-dependent.
    """
    digest = hashlib.sha256(canonicalize_json(seq19)).hexdigest()
    if digest != SEQ19_PAYLOAD_SHA256:
        _fail(
            "the seq-19 source is not the activated artifact: recomputed JCS "
            f"digest {digest} != {SEQ19_PAYLOAD_SHA256}. Everything below would "
            "otherwise be built on a payload production never ran."
        )
    assert_anchor_is_a_verified_signed_artifact(seq19_signed, digest, observed_at=observed_at)
    if seq19.get("sequence") != 19:
        _fail(f"expected sequence 19, got {seq19.get('sequence')!r}")

    inherited_id = seq19.get("rule_pack_id")
    expected_19_id = str(_rule_pack_id(19))
    if inherited_id != expected_19_id:
        _fail(
            f"the seq-19 payload carries rule_pack_id={inherited_id!r}, but the "
            f"uuid5 convention yields {expected_19_id!r} — the anchor is verified, "
            "never assumed."
        )
    if NEW_RULE_ID in _rules_by_id(seq19):
        _fail(f"{NEW_RULE_ID!r} already exists in seq-19 — this fold declares it as an INSERT")

    _assert_stay_day_cap_census(seq19)
    _assert_retired_rule_is_a_copy_of_its_support_twin(_rules_by_id(seq19))
    _assert_sponsor_status_census(seq19)
    _assert_bridging_census(seq19)

    new_rule = build_new_rule(seq19)
    _assert_new_rule_shortens_no_freshness_horizon(seq19, list(new_rule["source_refs"]))

    out = json.loads(json.dumps(seq19))
    out["rules"] = [rule for rule in out["rules"] if rule["rule_id"] not in REMOVED_RULE_IDS]
    rules_by_id = _rules_by_id(out)
    _bump_stay_day_caps(rules_by_id)
    _make_sponsor_rules_no_effect(rules_by_id)
    _conjoin_requested_product_known(rules_by_id)
    out["rules"].append(copy.deepcopy(new_rule))

    out["sequence"] = 20
    out["rule_pack_id"] = str(_rule_pack_id(20))
    out["version"] = FOLD_VERSION
    out["created_at"] = FOLD_CREATED_AT
    out["created_by"] = FOLD_CREATED_BY
    out["previous_payload_sha256"] = SEQ19_PAYLOAD_SHA256
    out["rollback_of_payload_sha256"] = None

    assert_only_expected_changes(seq19, out)
    assert_changed_fields_hold_their_expected_values(out, expected_new_rule=new_rule)
    RulePackPayload.model_validate(out)
    return out


def _assert_output_does_not_collide_with_inputs(output: Path, input_paths: dict[str, Path]) -> None:
    """Refuse to write ``--output`` onto any input path, and refuse an output
    path that merely LOOKS like a signed artifact.

    A copy-pasted flag could otherwise point ``--output`` at
    ``--seq19-signed`` — the SIGNED production anchor — and overwrite it with
    unsigned fold bytes. Paths are ``resolve()``d before comparison so a
    relative path and its absolute twin are not mistaken for "different".
    """
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
    parser = argparse.ArgumentParser(description="Fold RulePack seq-20.")
    parser.add_argument("--seq19-source", required=True, type=Path)
    parser.add_argument(
        "--seq19-signed",
        type=Path,
        default=None,
        help=(
            "the signed seq-19 envelope; defaults to the .signed.json sibling "
            "of --seq19-source. Its signature is verified — the anchor is "
            "never taken on the digest constant alone."
        ),
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    if args.seq19_signed is not None:
        signed_path = args.seq19_signed
    else:
        source_str = str(args.seq19_source)
        # Suffix-anchored, not `str.replace` (which substitutes every
        # occurrence, so a path with `.source.json` as a DIRECTORY component
        # would silently resolve somewhere else).
        if not source_str.endswith(".source.json"):
            _fail(
                f"--seq19-source {source_str!r} does not end in '.source.json' — "
                "cannot derive the signed sibling path; pass --seq19-signed explicitly"
            )
        signed_path = Path(source_str[: -len(".source.json")] + ".signed.json")
    if signed_path == args.seq19_source or not signed_path.exists():
        _fail(f"no signed seq-19 bundle at {signed_path} — pass --seq19-signed")

    _assert_output_does_not_collide_with_inputs(
        args.output,
        {"--seq19-source": args.seq19_source, "--seq19-signed": signed_path},
    )

    seq19 = json.loads(args.seq19_source.read_text(encoding="utf-8"))
    seq19_signed = json.loads(signed_path.read_text(encoding="utf-8"))
    seq20 = fold(seq19, seq19_signed, observed_at=observed_at)
    args.output.write_text(json.dumps(seq20, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    digest = hashlib.sha256(canonicalize_json(seq20)).hexdigest()
    print(f"fold_pack_seq20: wrote {args.output}")
    print(f"fold_pack_seq20: seq-20 payload_sha256 = {digest}")
    print(f"fold_pack_seq20: bumped stay-day caps on {len(STAY_DAY_CAPS)} rules")
    print(f"fold_pack_seq20: retired {sorted(REMOVED_RULE_IDS)}")
    print(f"fold_pack_seq20: NO_EFFECT on {sorted(SPONSOR_STATUS_NO_EFFECT_RULE_IDS)}")
    print(f"fold_pack_seq20: conjoined `known` on {sorted(BRIDGING_RULE_IDS)}")
    print(f"fold_pack_seq20: inserted {NEW_RULE_ID}")
    print("fold_pack_seq20: NOT SIGNED, NOT ACTIVATED — see sign_pack.py / activate_pack.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
