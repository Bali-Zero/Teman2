"""fold_pack_seq24.py — seq-24, a retiree without a confirmed sponsor becomes an
E33F candidate. This fold never signs or activates anything by itself; its
output was signed as ``rulepack-prod-024.signed.json`` on 2026-09-27 (see
"SIGNED" below).

WHAT THIS FOLD IS
==================
One semantic change, for one product: E33F (Second Home Visa, retirement basis,
``product_version_id`` 7c1da88f-f7cd-571a-95c2-7da32463d3e6). RULED by Zero on
2026-09-27: an applicant who takes the RETIREMENT route and has NOT confirmed a
sponsor is no longer a named dead end (``SPONSOR_REQUIRED``) — they are an E33F
candidate on the strength of the two facts that carry the route (age and
passive income), and the sponsor question is no longer asked ahead of it. The
note that tells the applicant a sponsor may still be needed lives in the mouth
(Option A) — no new reason code is minted here.

Two edits, both against the signed seq-23 rule set, nothing else::

    RETIRED   hf.e33f.sponsor-required   (HARD_FILTER / EXCLUDE / SPONSOR_REQUIRED
                                          on family.sponsor_confirmed == false;
                                          the ONLY emitter of SPONSOR_REQUIRED)
    MODIFIED  el.e33f.retirement         (SUPPORT E33F_RETIREMENT_ELIGIBLE) —
                                          the third conjunct
                                          ``family.sponsor_confirmed == true``
                                          is dropped from the ``all`` and
                                          ``family.sponsor_confirmed`` leaves
                                          ``required_facts``; ``valid_period``
                                          is untouched, exactly as seq-23's
                                          own in-place edits left theirs.

STAYS, byte for byte: ``hf.e33f.age-below-55``,
``hf.e33f.retirement-income-below-minimum`` and the four other rules that read
``family.sponsor_confirmed`` (``el.c2.business``, ``el.c6.social``,
``el.e31d-stepchild-support``, ``hf.minor-without-confirmed-sponsor``).

ANCHOR: seq-23, SIGNED and ACTIVE
==================================
``previous_payload_sha256`` = the seq-23 SIGNED artifact's own payload digest
(``rulepack-prod-023.signed.json``), verified against the public production
trust store exactly as every prior fold verifies its own anchor
(``assert_anchor_is_a_verified_signed_artifact``) — never taken on the digest
constant alone.

    previous_payload_sha256 = e5f791b5232fd1369ef3b94ca7bb5f349f9bb6eb4073895aa9f7deb682e72204

SIGNED (2026-09-27)
====================
``rulepack-prod-024.source.json`` was signed OFFLINE on M5 as
``rulepack-prod-024.signed.json`` (kid ``prod-2026-07-1``, ``signed_at``
2026-09-27T01:31:02Z), payload_sha256 =
5a569091f84a858f1957cdf96086ee7212f67d13a8225d64492a7212093cd272 — byte-identical
to this fold's output under JCS. Signed, NOT activated: the runtime stays on the
DB-active pack until a separate activation. The signed-bundle ties and the
signature check live in ``test_seq24_pack.py::TestSignedBundleTiesToSource``.

ROLLBACK is seq-25, a new pack whose ``rollback_of_payload_sha256`` names this
one — never a rewrite of seq-24.

ANTIBODIES CARRIED FORWARD
===========================
* ``assert_no_hard_filter_reads_a_synthesised_twin_basis_fact`` — copied from
  ``fold_pack_seq23.py`` (same four guarded facts, same guilt/innocence shape)
  and run on THIS fold's output.
* ``_assert_candidate_review_inventory`` — exactly one ``HUMAN_REVIEW``-stage
  rule (the Studio rule) and zero ``on_unknown: HUMAN_REVIEW`` escalations.
* ``_assert_sponsor_readers`` — the set of rules that read
  ``family.sponsor_confirmed`` after the fold is EXACTLY the four the ruling
  keeps: the sponsor question is dropped from E33F and nowhere else.
* ``_assert_no_rule_emits_sponsor_required`` — the retired rule was the only
  emitter of ``SPONSOR_REQUIRED`` before the fold (a second emitter would mean
  the ruling is under-specified) and nothing emits it after.

USAGE::

    VISA_ENGINE_TRUST_STORE_KEYS_JSON='<public trust store, key-ceremony runbook>' \\
    PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq24 \\
        --seq23-source backend/services/visa_engine/contracts/packs/rulepack-prod-023.source.json \\
        --output backend/services/visa_engine/contracts/packs/rulepack-prod-024.source.json
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

#: H23 — the seq-23 SIGNED artifact's own payload digest (the anchor).
SEQ23_PAYLOAD_SHA256 = (
    "e5f791b5232fd1369ef3b94ca7bb5f349f9bb6eb4073895aa9f7deb682e72204"  # pragma: allowlist secret
)

#: Must precede the instant seq-24 is signed at — the signing ceremony runs
#: after this fold is merged, so a fixed past instant is always earlier.
FOLD_CREATED_AT = "2026-09-26T21:00:00Z"
FOLD_CREATED_BY = "agent.pro.backend-rag.visa-oracle-seq24.fold-2026-09-27"
FOLD_VERSION = "2026.9.27"

_RULE_PACK_ID_URL_PREFIX = (
    "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/"
)

# ---------------------------------------------------------------------------
# The disposition table's identifiers.
# ---------------------------------------------------------------------------

E33F_PRODUCT_VERSION_ID = "7c1da88f-f7cd-571a-95c2-7da32463d3e6"

#: The single HARD_FILTER this fold retires. Its reason code has no other
#: emitter in seq-23 (asserted at fold time).
SPONSOR_REQUIRED_RULE_ID = "hf.e33f.sponsor-required"
SPONSOR_REQUIRED_REASON_CODE = "SPONSOR_REQUIRED"
REMOVED_RULE_IDS: frozenset[str] = frozenset({SPONSOR_REQUIRED_RULE_ID})

#: The single SUPPORT rule this fold edits in place.
E33F_RETIREMENT_RULE_ID = "el.e33f.retirement"
MODIFIED_RULE_IDS: frozenset[str] = frozenset({E33F_RETIREMENT_RULE_ID})

#: Nothing is inserted: seq-24 mints no rule and no reason code (Option A).
INSERTED_RULE_IDS: frozenset[str] = frozenset()

SPONSOR_FACT = "family.sponsor_confirmed"
#: The conjunct this fold drops, spelled out so a donor that has drifted is a
#: fold-time failure and not a silently different edit.
_SPONSOR_CONJUNCT: dict[str, Any] = {"op": "eq", "fact": SPONSOR_FACT, "value": True}

#: The four rules that keep reading ``family.sponsor_confirmed`` after the fold.
SPONSOR_READERS_AFTER_FOLD: frozenset[str] = frozenset(
    {
        "el.c2.business",
        "el.c6.social",
        "el.e31d-stepchild-support",
        "hf.minor-without-confirmed-sponsor",
    }
)

#: Brought forward untouched — the E33F age and income filters stay.
E33F_AGE_RULE_ID = "hf.e33f.age-below-55"
E33F_INCOME_RULE_ID = "hf.e33f.retirement-income-below-minimum"

#: The one HUMAN_REVIEW rule that survives (D23 "OPTION B-STUDIO").
STUDIO_RULE_ID = "review.e33.below-threshold-studio"

#: Mirror of `fold_pack_seq23.py`'s own guarded set — the four Second-Home
#: facts `fact-mapper.ts` SYNTHESISES for whichever basis the visitor did not
#: choose. No rule in this pack may let a HARD_FILTER/EXCLUDE read one.
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
    raise SystemExit(f"fold_pack_seq24: {message}")


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


def _required_facts(when: dict[str, Any]) -> list[str]:
    facts = {node["fact"] for node in _nodes(when) if isinstance(node.get("fact"), str)}
    return sorted(facts)


def _require_rule(payload: dict[str, Any], rule_id: str) -> dict[str, Any]:
    rule = _rules_by_id(payload).get(rule_id)
    if rule is None:
        _fail(f"rule {rule_id!r} is not in the base pack — the edit set is stale")
    return rule


def _rules_reading_fact(payload: dict[str, Any], fact: str) -> set[str]:
    return {
        rule["rule_id"]
        for rule in payload["rules"]
        if any(node.get("fact") == fact for node in _nodes(rule.get("when")))
    }


def _rules_emitting_reason_code(payload: dict[str, Any], reason_code: str) -> set[str]:
    return {
        rule["rule_id"]
        for rule in payload["rules"]
        if (rule.get("effect") or {}).get("reason_code") == reason_code
    }


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
            f"cannot verify the seq-23 anchor's signature: {exc}. Export the "
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
        _fail(f"the seq-23 signed bundle does not verify: {exc}")

    signed_digest = verified.payload_sha256.hex()
    if signed_digest != digest:
        _fail(
            f"the seq-23 SOURCE digest {digest} is not the digest of the signed "
            f"seq-23 artifact ({signed_digest}) — the source on disk and the "
            "artifact production verifies are two different payloads."
        )
    if verified.pack.payload.sequence != 23:
        _fail(
            "the signed bundle handed in as the seq-23 anchor carries sequence "
            f"{verified.pack.payload.sequence}"
        )


def _assert_retired_rule_is_the_expected_shape(payload: dict[str, Any]) -> None:
    """Pre-fold sanity: the rule the ruling retires is, today, the E33F
    sponsor gate this fold's docstring says it is — and the sole emitter of
    its reason code."""

    rule = _require_rule(payload, SPONSOR_REQUIRED_RULE_ID)
    if rule["stage"] != "HARD_FILTER" or rule["effect"]["type"] != "EXCLUDE":
        _fail(
            f"{SPONSOR_REQUIRED_RULE_ID!r} is {rule['stage']}/{rule['effect']['type']}, "
            "not HARD_FILTER/EXCLUDE — the edit set is stale"
        )
    if rule["effect"].get("reason_code") != SPONSOR_REQUIRED_REASON_CODE:
        _fail(
            f"{SPONSOR_REQUIRED_RULE_ID!r} emits {rule['effect'].get('reason_code')!r}, "
            f"not {SPONSOR_REQUIRED_REASON_CODE!r}"
        )
    if rule.get("product_version_ids") != [E33F_PRODUCT_VERSION_ID]:
        _fail(
            f"{SPONSOR_REQUIRED_RULE_ID!r} is scoped to {rule.get('product_version_ids')!r}, "
            f"not to E33F alone ({E33F_PRODUCT_VERSION_ID})"
        )
    emitters = _rules_emitting_reason_code(payload, SPONSOR_REQUIRED_REASON_CODE)
    if emitters != {SPONSOR_REQUIRED_RULE_ID}:
        _fail(
            f"{SPONSOR_REQUIRED_REASON_CODE} is emitted by {sorted(emitters)}, not by "
            f"{SPONSOR_REQUIRED_RULE_ID!r} alone — retiring it would leave a second "
            "emitter behind; the ruling did not cover that"
        )


def build_modified_e33f_retirement(rule: dict[str, Any]) -> dict[str, Any]:
    """The seq-24 form of ``el.e33f.retirement``: a deep copy of the seq-23
    rule with the sponsor conjunct removed from the top-level ``all`` and the
    sponsor fact removed from ``required_facts``. Every other field —
    ``valid_period`` included — is the seq-23 rule's own."""

    if rule.get("scope") != "PRODUCTS" or rule.get("product_version_ids") != [
        E33F_PRODUCT_VERSION_ID
    ]:
        _fail(f"{E33F_RETIREMENT_RULE_ID!r} is not the E33F-only rule the edit set expects")
    when = rule.get("when")
    if not isinstance(when, dict) or when.get("op") != "all":
        _fail(f"{E33F_RETIREMENT_RULE_ID!r}'s `when` is not a top-level `all`")
    args = when.get("args")
    if not isinstance(args, list) or len(args) != 3:
        _fail(
            f"{E33F_RETIREMENT_RULE_ID!r}'s `all` carries "
            f"{len(args) if isinstance(args, list) else args!r} conjuncts, expected 3 "
            "(purposes, income, sponsor)"
        )
    if _canon(args[2]) != _canon(_SPONSOR_CONJUNCT):
        _fail(
            f"{E33F_RETIREMENT_RULE_ID!r}'s third conjunct is {args[2]!r}, expected "
            f"{_SPONSOR_CONJUNCT!r} — the edit set is stale"
        )
    if SPONSOR_FACT not in rule["required_facts"]:
        _fail(f"{E33F_RETIREMENT_RULE_ID!r}'s required_facts does not list {SPONSOR_FACT!r}")

    out = copy.deepcopy(rule)
    out["when"]["args"] = out["when"]["args"][:2]
    out["required_facts"] = [fact for fact in out["required_facts"] if fact != SPONSOR_FACT]
    if out["required_facts"] != _required_facts(out["when"]):
        _fail(
            f"{E33F_RETIREMENT_RULE_ID!r}'s required_facts {out['required_facts']!r} "
            f"no longer matches the facts its `when` reads {_required_facts(out['when'])!r}"
        )
    return out


def assert_no_hard_filter_reads_a_synthesised_twin_basis_fact(
    payload: dict[str, Any],
) -> None:
    """A8.3's antibody — same shape as `fold_pack_seq22.py`/`fold_pack_seq23.py`'s
    guard of the same name, re-run here on THIS pack: an EXCLUDE (or an
    `eq false`, at any stage) reading a fact `fact-mapper.ts` synthesises for
    the Second-Home basis the visitor did not choose.
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


def _assert_sponsor_readers(payload: dict[str, Any], *, after_fold: bool) -> None:
    """GUILT: a fold that drops the sponsor question from E33F but also
    drops it from another product (or leaves it on E33F) aborts. INNOCENCE:
    the four readers the ruling keeps are exactly what is left."""

    readers = _rules_reading_fact(payload, SPONSOR_FACT)
    expected = set(SPONSOR_READERS_AFTER_FOLD)
    if not after_fold:
        expected |= {SPONSOR_REQUIRED_RULE_ID, E33F_RETIREMENT_RULE_ID}
    if readers != expected:
        _fail(
            f"the rules reading {SPONSOR_FACT} are {sorted(readers)}, expected "
            f"{sorted(expected)} ({'after' if after_fold else 'before'} the fold)"
        )


def _assert_no_rule_emits_sponsor_required(payload: dict[str, Any]) -> None:
    emitters = _rules_emitting_reason_code(payload, SPONSOR_REQUIRED_REASON_CODE)
    if emitters:
        _fail(f"{sorted(emitters)} still emit {SPONSOR_REQUIRED_REASON_CODE} after the fold")


def assert_only_expected_changes(before: dict[str, Any], after: dict[str, Any]) -> None:
    if set(after) != set(before):
        _fail(
            "the payload's top-level key set changed "
            f"(added {sorted(set(after) - set(before))}, "
            f"removed {sorted(set(before) - set(after))})"
        )
    for key in set(before) - _IDENTITY_KEYS - {"rules"}:
        if _canon(after.get(key)) != _canon(before.get(key)):
            _fail(f"{key} changed — this fold retires one rule, edits one and nothing else")

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
        _fail(f"rules were added ({sorted(added)}) — this fold inserts none")

    for rule_id, rule in after_rules.items():
        before_rule = before_rules[rule_id]
        if rule_id in MODIFIED_RULE_IDS:
            if _canon(rule) != _canon(build_modified_e33f_retirement(before_rule)):
                _fail(f"rule {rule_id!r} changed something other than the sponsor conjunct")
            continue
        if _canon(rule) != _canon(before_rule):
            _fail(
                f"rule {rule_id!r} drifted from seq-23 — this fold retires "
                f"{SPONSOR_REQUIRED_RULE_ID!r}, edits {E33F_RETIREMENT_RULE_ID!r}, nothing else"
            )

    before_order = [r["rule_id"] for r in before["rules"] if r["rule_id"] not in REMOVED_RULE_IDS]
    after_order = [r["rule_id"] for r in after["rules"]]
    if before_order != after_order:
        _fail("the surviving rules' order changed — this fold only removes one rule")


def assert_changed_fields_hold_their_expected_values(after: dict[str, Any]) -> None:
    expected: dict[str, Any] = {
        "sequence": 24,
        "rule_pack_id": str(_rule_pack_id(24)),
        "version": FOLD_VERSION,
        "created_at": FOLD_CREATED_AT,
        "created_by": FOLD_CREATED_BY,
        "previous_payload_sha256": SEQ23_PAYLOAD_SHA256,
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
    for rule_id in (E33F_AGE_RULE_ID, E33F_INCOME_RULE_ID, E33F_RETIREMENT_RULE_ID):
        if rule_id not in rules_by_id:
            _fail(f"rule {rule_id!r} must stay in the pack and is gone")


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
    seq23: dict[str, Any], seq23_signed: dict[str, Any], *, observed_at: datetime | None = None
) -> dict[str, Any]:
    digest = hashlib.sha256(canonicalize_json(seq23)).hexdigest()
    if digest != SEQ23_PAYLOAD_SHA256:
        _fail(
            f"the seq-23 source is not the activated artifact: recomputed JCS "
            f"digest {digest} != {SEQ23_PAYLOAD_SHA256}"
        )
    assert_anchor_is_a_verified_signed_artifact(seq23_signed, digest, observed_at=observed_at)
    if seq23.get("sequence") != 23:
        _fail(f"expected sequence 23, got {seq23.get('sequence')!r}")

    inherited_id = seq23.get("rule_pack_id")
    expected_23_id = str(_rule_pack_id(23))
    if inherited_id != expected_23_id:
        _fail(
            f"the seq-23 payload carries rule_pack_id={inherited_id!r}, but the "
            f"uuid5 convention yields {expected_23_id!r}"
        )

    _assert_retired_rule_is_the_expected_shape(seq23)
    _assert_sponsor_readers(seq23, after_fold=False)

    out = json.loads(json.dumps(seq23))
    out["rules"] = [
        build_modified_e33f_retirement(rule) if rule["rule_id"] in MODIFIED_RULE_IDS else rule
        for rule in out["rules"]
        if rule["rule_id"] not in REMOVED_RULE_IDS
    ]

    out["sequence"] = 24
    out["rule_pack_id"] = str(_rule_pack_id(24))
    out["version"] = FOLD_VERSION
    out["created_at"] = FOLD_CREATED_AT
    out["created_by"] = FOLD_CREATED_BY
    out["previous_payload_sha256"] = SEQ23_PAYLOAD_SHA256
    out["rollback_of_payload_sha256"] = None

    assert_only_expected_changes(seq23, out)
    assert_changed_fields_hold_their_expected_values(out)
    _assert_sponsor_readers(out, after_fold=True)
    _assert_no_rule_emits_sponsor_required(out)
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
    parser = argparse.ArgumentParser(description="Fold RulePack seq-24 (candidate) from seq-23.")
    parser.add_argument("--seq23-source", required=True, type=Path)
    parser.add_argument(
        "--seq23-signed",
        type=Path,
        default=None,
        help="the signed seq-23 envelope; defaults to the .signed.json sibling of --seq23-source",
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    if args.seq23_signed is not None:
        signed_path = args.seq23_signed
    else:
        source_str = str(args.seq23_source)
        if not source_str.endswith(".source.json"):
            _fail(
                f"--seq23-source {source_str!r} does not end in '.source.json' — "
                "cannot derive the signed sibling path; pass --seq23-signed explicitly"
            )
        signed_path = Path(source_str[: -len(".source.json")] + ".signed.json")
    if signed_path == args.seq23_source or not signed_path.exists():
        _fail(f"no signed seq-23 bundle at {signed_path} — pass --seq23-signed")

    _assert_output_does_not_collide_with_inputs(
        args.output,
        {"--seq23-source": args.seq23_source, "--seq23-signed": signed_path},
    )

    seq23 = json.loads(args.seq23_source.read_text(encoding="utf-8"))
    seq23_signed = json.loads(signed_path.read_text(encoding="utf-8"))
    seq24 = fold(seq23, seq23_signed, observed_at=observed_at)
    args.output.write_text(json.dumps(seq24, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    digest = hashlib.sha256(canonicalize_json(seq24)).hexdigest()
    print(f"fold_pack_seq24: wrote {args.output}")
    print(f"fold_pack_seq24: seq-24 payload_sha256 = {digest}")
    print(f"fold_pack_seq24: retired {sorted(REMOVED_RULE_IDS)}")
    print(f"fold_pack_seq24: modified in place {sorted(MODIFIED_RULE_IDS)}")
    print("fold_pack_seq24: NOT SIGNED, NOT ACTIVATED — see sign_pack.py / activate_pack.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
