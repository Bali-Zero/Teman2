"""fold_pack_seq19.py — transplant seq-15's E31 fail-open repairs onto the
signed seq-18 payload, the pack the engine actually serves today.

WHY, AND WHAT IT COSTS
======================
``research/operations/2026-09-05-consuls-ground-visaoracle-engine.md`` (Q3),
confirmed byte-for-byte by an independent refuter
(``...-visaoracle-refutation.md``), established that seq-15's repair of the
2026-08-15 BLOCK-DEFECT gold divergence (personas #6/#7, E31B/E31D fail-open)
never reached the line that got signed: seq-16 re-parented onto seq-13 —
bypassing the unsigned 14→15 candidate line — and seq-17/seq-18 chain from
seq-16. seq-15's three repairs are therefore ABSENT from the pack in
production RIGHT NOW, even though seq-15 was authored on 2026-08-29 (per
PENDING-ARMS.md's own "seq-15 authored" row) — it was never itself signed;
only `rulepack-prod-015.source.json` exists on disk, no `.signed.json`
sibling (see ``fold_pack_seq15.py``'s docstring for the repair's own
rationale — this fold does not re-litigate it, only re-lands it).

This fold does exactly one thing: chain a fresh sequence from the CURRENT
production anchor (seq-18, signed) and TRANSPLANT seq-15's repaired bytes
onto it, verbatim — never re-deriving or re-authoring the predicate shapes.
Every rule this fold does not name, and every product/source_record, stays
byte-identical to seq-18.

THE REPAIR, TRANSPLANTED (not re-authored):
1. Four rule ids retired — present (un-retired) in seq-17/seq-18 because the
   chain that reached production skipped the line that removed them:
   ``el.e31d-step-parent-relation``, ``el.e31d-sponsor-mixed-marriage``
   (byte-duplicate intent-only E31D SUPPORT rules) and
   ``review.e23u.requested-product``, ``review.e23v.requested-product``
   (seq-14's carried-forward review-rule retirements).
2. The nine ``*-itas-*`` sponsor rules' terminal
   ``{"fact": "family.sponsor_status_code", "op": "known"}`` (fail-open,
   accepts ANY answered value including ``"NONE"``) becomes seq-15's
   ``op: "in"`` closed stay-permit set — copied as the exact ``when`` tree
   seq-15 carries for each rule id, not re-derived from today's catalog.
3. ``el.e31d-stepchild-support``'s ``when``/``required_facts`` become
   seq-15's 5-arg full conjunction (STEPCHILD relation + both stepchild
   evidence facts + ``sponsor_confirmed``), again copied verbatim.

Verified this run, by pack bytes (not assumed): all ten of these rule ids are
byte-identical between seq-13 and seq-18 — the intervening seq-16 "E23
tourism fold" and the seq-17/seq-18 freshness folds never touched the E31
family — so seq-15's edit against seq-13 (``when``, plus ``required_facts``
on the stepchild rule only) transplants onto seq-18 without any adaptation.

WHAT IS DELIBERATELY *NOT* DONE HERE
=====================================
No re-authoring: every transplanted byte is read from
``rulepack-prod-015.source.json`` and copied, never hand-written here. No
opinion on KITAP representability or on which person may sponsor an E31D
stepchild path — both are Zero's pending doctrine calls, exactly as
``fold_pack_seq15.py`` states them, and this fold does not touch anything
seq-15 itself did not touch (products, source_records, the other 97 rules).

NOT SIGNED, NOT ACTIVATED by this script. Signing is the consul's ceremony
(``sign_pack.py``, an operator-supplied Ed25519 key); activation is a
separate, later act. This script only ever writes the unsigned SOURCE file.

Usage::

    PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq19 \\
        --seq18-source <path to rulepack-prod-018.source.json> \\
        --seq18-signed <path to rulepack-prod-018.signed.json> \\
        --seq15-source <path to rulepack-prod-015.source.json> \\
        --seq13-source <path to rulepack-prod-013.source.json> \\
        --output <seq-19 source path>

`--seq18-signed` defaults to the `.signed.json` sibling of `--seq18-source`,
and the fold refuses to run without one: the anchor is verified by
SIGNATURE, never by a digest constant alone.
`VISA_ENGINE_TRUST_STORE_KEYS_JSON` (the production PUBLIC key) must be
exported — its absence is a refusal, not a skipped check.
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

#: The seq-18 payload digest — the chain anchor, and the digest active in
#: production as of this fold's authoring.
SEQ18_PAYLOAD_SHA256 = "5a24472d187f85c54628f23d6e37b2a4b814e54762478c099472f0437d255849"

#: seq-13's payload digest — same constant `fold_pack_seq15.py` pins as its
#: own chain anchor. Used here only to confirm the `--seq13-source` file this
#: fold is handed for its drift check is the real thing, not a stand-in.
SEQ13_PAYLOAD_SHA256 = "b9edb809930ab486e49a4af7804fbae7f072caa3b6459b78a94ecb7f6bfe14f8"

#: seq-15's own payload digest. seq-15 was authored (2026-08-29) but NEVER
#: itself signed — no `.signed.json` exists for it on disk, so there is no
#: Ed25519 envelope to verify the donor against, unlike the seq-18 anchor.
#: This pinned digest is the substitute chain-of-custody check: without it,
#: `fold()` accepted ANY file merely declaring `"sequence": 15`, which an
#: adversarial review (tp1-qwen3.8-max) named as a real gap — a stale copy
#: or a mis-named file at `--seq15-source` could inject arbitrary `when`
#: trees into a production rule pack with no cryptographic check at all.
SEQ15_PAYLOAD_SHA256 = "876100fbce41b1ae2b717ad446d6b359e15c43dc326ef849fb800850632d4153"

FOLD_CREATED_AT = "2026-09-05T00:00:00Z"
FOLD_CREATED_BY = "agent.air-m5.backend-rag.e31-failopen-repair-seq19.fold-2026-09-05"
FOLD_VERSION = "2026.9.5"

_RULE_PACK_ID_URL_PREFIX = (
    "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/"
)

#: Retired here because the 13->16->17->18 chain that reached production
#: never dropped them — see the module docstring, point 1.
REMOVED_RULE_IDS: frozenset[str] = frozenset(
    {
        "el.e31d-step-parent-relation",
        "el.e31d-sponsor-mixed-marriage",
        "review.e23u.requested-product",
        "review.e23v.requested-product",
    }
)

#: The nine sponsor rules whose fail-open `op:known` terminal seq-15 closed.
SPONSOR_TERMINAL_RULE_IDS: tuple[str, ...] = (
    "el.e31b-spouse-itas-support",
    "el.e31b-sponsor-itas-itap",
    "el.e31e-child-itas-support",
    "el.e31e-sponsor-itas-itap",
    "el.e31h-parent-itas-child-support",
    "el.e31h-sponsor-itas-itap",
    "el.e31j-sibling-itas-support",
    "el.e31j-sponsor-itas-itap",
    "el.e31j-dependency-age",
)
STEPCHILD_RULE_ID = "el.e31d-stepchild-support"
EDITED_RULE_IDS: tuple[str, ...] = SPONSOR_TERMINAL_RULE_IDS + (STEPCHILD_RULE_ID,)

#: The only top-level keys this fold may move; `rules` moves too (retirement
#: + transplant) but is diffed at the rule level, not by whole-value equality.
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
    raise SystemExit(f"fold_pack_seq19: {message}")


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def assert_anchor_is_a_verified_signed_artifact(
    signed_envelope: dict[str, Any],
    digest: str,
    *,
    observed_at: datetime | None = None,
) -> None:
    """Require the chain anchor to be a SIGNED seq-18 pack, not just a digest.

    Same shape as ``fold_pack_seq18.assert_anchor_is_a_verified_signed_artifact``
    — imported logic would be cleaner, but that function is pinned to
    sequence 17 by design (its own final check), so it is reproduced here
    pinned to 18 rather than parameterized after the fact.
    """
    try:
        trust_store = StaticTrustStore.from_env()
    except RulePackVerificationError as exc:
        _fail(
            f"cannot verify the seq-18 anchor's signature: {exc}. Export the "
            "production trust store (the public key, e.g. "
            "VISA_ENGINE_TRUST_STORE_KEYS_JSON='[{\"kid\": \"prod-2026-07-1\", ...}]') "
            "and re-run — the anchor is never taken on a digest constant alone."
        )
    try:
        verified = verify_rule_pack(
            signed_envelope,
            trust_store=trust_store,
            observed_at=observed_at or datetime.now(timezone.utc),
        )
    except RulePackVerificationError as exc:
        _fail(f"the seq-18 signed bundle does not verify: {exc}")

    signed_digest = verified.payload_sha256.hex()
    if signed_digest != digest:
        _fail(
            f"the seq-18 SOURCE digest {digest} is not the digest of the signed "
            f"seq-18 artifact ({signed_digest}) — the source on disk and the "
            "artifact production verifies are two different payloads."
        )
    if verified.pack.payload.sequence != 18:
        _fail(
            "the signed bundle handed in as the seq-18 anchor carries sequence "
            f"{verified.pack.payload.sequence}"
        )


def _assert_edited_rules_unchanged_since_seq13(
    seq18_rules_by_id: dict[str, Any], seq13_rules_by_id: dict[str, Any]
) -> None:
    """Refuse the transplant unless every rule id it is about to overwrite is
    STILL byte-identical, in seq-18, to its seq-13 shape.

    seq-15's repair is a delta computed against seq-13 (``fold_pack_seq15.py``
    edited ``when``/``required_facts`` on top of seq-13's rule bytes, nothing
    else). Transplanting that delta onto seq-18 is only safe because — this
    run, verified byte-for-byte — none of these ten rule ids drifted between
    seq-13 and seq-18 (seq-16's "E23 tourism fold" and the seq-17/seq-18
    freshness folds never touched the E31 family). That is a fact about
    TODAY's packs, not a law the model enforces on its own; a future base
    pack that legitimately changed one of these rules for an unrelated
    reason would have that change silently DISCARDED by a blind transplant
    (the donor's `when` would overwrite it, and every other field is copied
    from the base — so nothing is lost there, but `when`/`required_facts`
    specifically would revert to seq-15's frozen 2026-08-29 shape). Checked
    here, at fold time, rather than only asserted in a docstring — found by
    adversarial review of this diff (kimi-code/k3).
    """
    for rule_id in EDITED_RULE_IDS:
        seq18_rule = seq18_rules_by_id.get(rule_id)
        seq13_rule = seq13_rules_by_id.get(rule_id)
        if seq18_rule is None or seq13_rule is None:
            _fail(f"rule {rule_id!r} missing from seq-18 or seq-13 — cannot verify transplant safety")
        if _canon(seq18_rule) != _canon(seq13_rule):
            _fail(
                f"rule {rule_id!r} has DRIFTED from seq-13 in seq-18 — seq-15's "
                "repair is a delta against seq-13 and is no longer safe to "
                "transplant blindly onto a base that has independently changed "
                "this rule. Re-derive the repair against the current base instead "
                "of re-running this fold unmodified."
            )


_STAY_PERMIT_PREFIX = "E"


def _stay_permit_codes(payload: dict[str, Any]) -> frozenset[str]:
    return frozenset(
        p["product_code"] for p in payload["products"] if p["product_code"].startswith(_STAY_PERMIT_PREFIX)
    )


def _assert_product_catalog_unchanged_since_seq13(
    seq18: dict[str, Any], seq13: dict[str, Any]
) -> None:
    """The nine sponsor rules' transplanted ``op:"in"`` closed set is the
    list of E-prefix stay-permit PRODUCT CODES that ``fold_pack_seq15.py``
    derived from seq-13's own catalog at fold time (never hand-authored —
    see that script's docstring). Transplanting those `values` verbatim onto
    seq-18 is only safe if seq-18 offers the exact same set of stay-permit
    codes as seq-13; otherwise a sponsor holding a NEWER stay permit would be
    silently excluded by a closed set that reflects an older catalog.

    Scoped to the CODE SET, not the full product objects: seq-16's "E23
    tourism fold" changed `E23.covered_purposes` (confirmed this run —
    `E23` is the only product whose bytes differ between seq-13 and seq-18,
    and `covered_purposes` is the only field that moved), which is
    unrelated to whether E23 remains a valid stay-permit CODE in the closed
    set. An earlier draft of this check compared whole product objects and
    would have refused a safe transplant on that unrelated drift — found by
    running it against the real packs before trusting it (adversarial
    review, kimi-code/k3, prompted the check; the over-broad first draft was
    this session's own mistake, caught before commit).
    """
    seq18_codes = _stay_permit_codes(seq18)
    seq13_codes = _stay_permit_codes(seq13)
    if seq18_codes != seq13_codes:
        _fail(
            "seq-18's stay-permit (E-prefix) product code set has drifted from "
            f"seq-13: added {sorted(seq18_codes - seq13_codes)}, removed "
            f"{sorted(seq13_codes - seq18_codes)} — the transplanted sponsor-rule "
            "closed sets were derived from seq-13's code set and are no longer "
            "guaranteed to cover every stay-permit code seq-18 actually offers. "
            "Re-derive the closed set against the current catalog instead of "
            "transplanting it."
        )


def _transplant_repairs(rules: list[dict[str, Any]], seq15_rules_by_id: dict[str, Any]) -> None:
    """Copy seq-15's exact ``when`` (and, for the stepchild rule,
    ``required_facts``) onto the matching rule id — never re-derive or
    hand-author the shape."""
    rules_by_id = {r["rule_id"]: r for r in rules}
    for rule_id in EDITED_RULE_IDS:
        if rule_id not in rules_by_id:
            _fail(f"rule {rule_id!r} not found in seq-18 — cannot transplant a repair onto it")
        if rule_id not in seq15_rules_by_id:
            _fail(f"rule {rule_id!r} not found in seq-15 — cannot source the repair bytes")
    for rule_id in EDITED_RULE_IDS:
        rule = rules_by_id[rule_id]
        donor = seq15_rules_by_id[rule_id]
        rule["when"] = copy.deepcopy(donor["when"])
        if rule_id == STEPCHILD_RULE_ID:
            rule["required_facts"] = copy.deepcopy(donor["required_facts"])


def assert_only_expected_changes(before: dict[str, Any], after: dict[str, Any]) -> None:
    """Fail-closed on both axes: name what MAY move (the identity keys and
    `rules`, at the rule-diff granularity below) and require universal
    equality for everything else, so a key added in some future sequence is
    guarded automatically rather than escaping an allow-list of things to
    leave alone."""
    if set(after) != set(before):
        _fail(
            "the payload's top-level key set changed "
            f"(added {sorted(set(after) - set(before))}, "
            f"removed {sorted(set(before) - set(after))})"
        )
    for key in set(before) - _IDENTITY_KEYS - {"rules"}:
        if _canon(after.get(key)) != _canon(before.get(key)):
            _fail(f"{key} changed — this fold retires/repairs rules and nothing else")

    before_rules = {r["rule_id"]: r for r in before["rules"]}
    after_rules = {r["rule_id"]: r for r in after["rules"]}

    missing = set(before_rules) - set(after_rules)
    if missing != REMOVED_RULE_IDS:
        _fail(f"removed-rule set mismatch: {sorted(missing)} != {sorted(REMOVED_RULE_IDS)}")
    added = set(after_rules) - set(before_rules)
    if added:
        _fail(f"rule(s) added — this fold declares no insertion: {sorted(added)}")

    for rule_id, rule in after_rules.items():
        before_rule = before_rules[rule_id]
        if rule_id in EDITED_RULE_IDS:
            if _canon(rule) == _canon(before_rule):
                _fail(f"rule {rule_id!r} is byte-identical to seq-18 — the transplant did not land")
            # `required_facts` may move ONLY on the stepchild rule — narrowed
            # per-rule-id, not uniformly across all ten edited ids, so a stray
            # `required_facts` drift on one of the nine sponsor rules is
            # caught here rather than silently excluded (adversarial review,
            # tp1-qwen3.8-max: the uniform exclusion made this guard blind to
            # exactly the field `_transplant_repairs` never touches there).
            allowed_fields = (
                {"when", "required_facts"} if rule_id == STEPCHILD_RULE_ID else {"when"}
            )
            # Union of both sides, not just `set(rule)`: a field the base HAD
            # and the transplant silently DROPPED would otherwise never enter
            # this loop at all (found by adversarial review, kimi-code/k3 —
            # a guard is supposed to be independent of what the code above it
            # does or doesn't do, and `_transplant_repairs` never deletes a
            # field today, but "the code above never does X" is exactly the
            # claim a guard exists to not have to trust).
            other_fields = (set(rule) | set(before_rule)) - allowed_fields
            for field in other_fields:
                if _canon(rule.get(field)) != _canon(before_rule.get(field)):
                    _fail(
                        f"rule {rule_id!r} field {field!r} moved — only `when` "
                        "(and `required_facts` on the stepchild rule) may move"
                    )
        elif _canon(rule) != _canon(before_rule):
            _fail(f"rule {rule_id!r} drifted from seq-18 — it is not in the declared edit set")


def assert_changed_fields_hold_their_expected_values(
    after: dict[str, Any], *, seq15_rules_by_id: dict[str, Any]
) -> None:
    """`assert_only_expected_changes` names what MAY move and excludes it
    from comparison — silent on whether it moved to the RIGHT thing. Pinned
    separately, per the lesson seq-18's own review recorded (its docstring):
    a guard whose fail-closedness holds only while the code above it stays
    correct is not a guard, it is a comment."""
    expected: dict[str, Any] = {
        "sequence": 19,
        "rule_pack_id": str(_rule_pack_id(19)),
        "version": FOLD_VERSION,
        "created_at": FOLD_CREATED_AT,
        "created_by": FOLD_CREATED_BY,
        "previous_payload_sha256": SEQ18_PAYLOAD_SHA256,
        "rollback_of_payload_sha256": None,
    }
    for key, want in expected.items():
        got = after.get(key)
        if got != want:
            _fail(f"{key} is {got!r}, expected {want!r}")

    after_rules_by_id = {r["rule_id"]: r for r in after["rules"]}
    for rule_id in REMOVED_RULE_IDS:
        if rule_id in after_rules_by_id:
            _fail(f"rule {rule_id!r} should have been retired but is still present")
    for rule_id in EDITED_RULE_IDS:
        if rule_id not in after_rules_by_id:
            _fail(f"rule {rule_id!r} is missing from the output — cannot verify its transplant")
        if rule_id not in seq15_rules_by_id:
            _fail(f"rule {rule_id!r} is missing from the seq-15 donor — cannot verify its transplant")
        donor = seq15_rules_by_id[rule_id]
        rule = after_rules_by_id[rule_id]
        if _canon(rule["when"]) != _canon(donor["when"]):
            _fail(f"rule {rule_id!r}'s `when` is not seq-15's exact transplanted bytes")
        if rule_id == STEPCHILD_RULE_ID and _canon(rule["required_facts"]) != _canon(
            donor["required_facts"]
        ):
            _fail(f"rule {rule_id!r}'s `required_facts` is not seq-15's exact transplanted bytes")


def fold(
    seq18: dict[str, Any],
    seq18_signed: dict[str, Any],
    seq15: dict[str, Any],
    seq13: dict[str, Any],
    *,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Return the seq-19 payload, or abort loudly.

    ``seq18_signed`` is the signed seq-18 envelope and is REQUIRED, not
    optional — see :func:`assert_anchor_is_a_verified_signed_artifact`.
    ``seq15`` is the repair DONOR: its bytes are copied, never re-derived.
    ``seq13`` is the delta's own base (seq-15 was folded FROM seq-13) —
    required so the transplant can refuse if any of the ten rules it is
    about to overwrite has drifted from seq-13 in seq-18 (see
    :func:`_assert_edited_rules_unchanged_since_seq13`; found by
    adversarial review of this diff, kimi-code/k3).
    ``observed_at`` is threaded into the signature-verification clock check
    (:func:`assert_anchor_is_a_verified_signed_artifact`); defaults to the
    real wall clock via ``datetime.now(timezone.utc)`` so callers never have
    to pass it, but a test pinning it is not left real-clock-dependent.
    """
    digest = hashlib.sha256(canonicalize_json(seq18)).hexdigest()
    if digest != SEQ18_PAYLOAD_SHA256:
        _fail(
            "the seq-18 source is not the activated artifact: recomputed JCS "
            f"digest {digest} != {SEQ18_PAYLOAD_SHA256}. Everything below would "
            "otherwise be built on a payload production never ran."
        )
    assert_anchor_is_a_verified_signed_artifact(seq18_signed, digest, observed_at=observed_at)
    if seq18.get("sequence") != 18:
        _fail(f"expected sequence 18, got {seq18.get('sequence')!r}")

    inherited_id = seq18.get("rule_pack_id")
    expected_18_id = str(_rule_pack_id(18))
    if inherited_id != expected_18_id:
        _fail(
            f"the seq-18 payload carries rule_pack_id={inherited_id!r}, but the "
            f"uuid5 convention yields {expected_18_id!r} — the anchor is verified, "
            "never assumed."
        )
    if seq15.get("sequence") != 15:
        _fail(f"the repair donor is not sequence 15, got {seq15.get('sequence')!r}")
    seq15_digest = hashlib.sha256(canonicalize_json(seq15)).hexdigest()
    if seq15_digest != SEQ15_PAYLOAD_SHA256:
        _fail(
            f"--seq15-source re-hashes to {seq15_digest}, expected "
            f"{SEQ15_PAYLOAD_SHA256} — seq-15 was never signed, so this pinned "
            "digest is the only chain-of-custody check available for the donor; "
            "refusing rather than transplanting bytes from an unverified file"
        )
    if seq13.get("sequence") != 13:
        _fail(f"the drift-check base is not sequence 13, got {seq13.get('sequence')!r}")
    seq13_digest = hashlib.sha256(canonicalize_json(seq13)).hexdigest()
    if seq13_digest != SEQ13_PAYLOAD_SHA256:
        _fail(
            f"--seq13-source re-hashes to {seq13_digest}, expected "
            f"{SEQ13_PAYLOAD_SHA256} — this is not the real signed seq-13 payload"
        )

    seq15_rules_by_id = {r["rule_id"]: r for r in seq15["rules"]}
    seq13_rules_by_id = {r["rule_id"]: r for r in seq13["rules"]}
    present_removed = {r["rule_id"] for r in seq18["rules"]} & REMOVED_RULE_IDS
    if present_removed != REMOVED_RULE_IDS:
        _fail(
            f"expected to retire {sorted(REMOVED_RULE_IDS)}, found "
            f"{sorted(present_removed)} present in seq-18 — someone already retired part of it"
        )
    seq18_rules_by_id = {r["rule_id"]: r for r in seq18["rules"]}
    _assert_edited_rules_unchanged_since_seq13(seq18_rules_by_id, seq13_rules_by_id)
    _assert_product_catalog_unchanged_since_seq13(seq18, seq13)

    out = json.loads(json.dumps(seq18))
    out["rules"] = [r for r in out["rules"] if r["rule_id"] not in REMOVED_RULE_IDS]
    _transplant_repairs(out["rules"], seq15_rules_by_id)

    out["sequence"] = 19
    out["rule_pack_id"] = str(_rule_pack_id(19))
    out["version"] = FOLD_VERSION
    out["created_at"] = FOLD_CREATED_AT
    out["created_by"] = FOLD_CREATED_BY
    out["previous_payload_sha256"] = SEQ18_PAYLOAD_SHA256
    out["rollback_of_payload_sha256"] = None

    assert_only_expected_changes(seq18, out)
    assert_changed_fields_hold_their_expected_values(out, seq15_rules_by_id=seq15_rules_by_id)
    RulePackPayload.model_validate(out)
    return out


def _assert_output_does_not_collide_with_inputs(
    output: Path, input_paths: dict[str, Path]
) -> None:
    """Fail-closed guard: refuse to write `--output` onto any input path, and
    refuse an output path that merely LOOKS like a signed artifact.

    A careless invocation (a copy-pasted flag, a shell-history mistake) could
    otherwise point `--output` at `--seq18-source`, `--seq15-source`,
    `--seq13-source` or — the sharpest edge — `--seq18-signed`, the SIGNED
    production anchor, and silently overwrite it with unsigned fold bytes.
    Paths are `resolve()`d before comparison so a relative path and its
    absolute twin, or a `..`-laden path, are not mistaken for "different"
    (found by adversarial review of this diff, codex terra).
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
    parser = argparse.ArgumentParser(description="Fold RulePack seq-19.")
    parser.add_argument("--seq18-source", required=True, type=Path)
    parser.add_argument(
        "--seq18-signed",
        type=Path,
        default=None,
        help=(
            "the signed seq-18 envelope; defaults to the .signed.json sibling "
            "of --seq18-source. Its signature is verified — the anchor is "
            "never taken on the digest constant alone."
        ),
    )
    parser.add_argument("--seq15-source", required=True, type=Path)
    parser.add_argument(
        "--seq13-source",
        required=True,
        type=Path,
        help=(
            "the signed seq-13 payload (source file) — seq-15's own repair base. "
            "Used to refuse the transplant if any of the ten edited rule ids has "
            "drifted from seq-13 in --seq18-source (see "
            "_assert_edited_rules_unchanged_since_seq13's docstring)."
        ),
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    if args.seq18_signed is not None:
        signed_path = args.seq18_signed
    else:
        source_str = str(args.seq18_source)
        # Suffix-anchored, not `str.replace` (which substitutes every
        # occurrence, not just the trailing one — a path containing
        # `.source.json` as a DIRECTORY component, not just the filename
        # suffix, would silently resolve somewhere else; adversarial review,
        # tp1-qwen3.8-max).
        if not source_str.endswith(".source.json"):
            _fail(
                f"--seq18-source {source_str!r} does not end in '.source.json' — "
                "cannot derive the signed sibling path; pass --seq18-signed explicitly"
            )
        signed_path = Path(source_str[: -len(".source.json")] + ".signed.json")
    if signed_path == args.seq18_source or not signed_path.exists():
        _fail(f"no signed seq-18 bundle at {signed_path} — pass --seq18-signed")

    _assert_output_does_not_collide_with_inputs(
        args.output,
        {
            "--seq18-source": args.seq18_source,
            "--seq15-source": args.seq15_source,
            "--seq13-source": args.seq13_source,
            "--seq18-signed": signed_path,
        },
    )

    seq18 = json.loads(args.seq18_source.read_text(encoding="utf-8"))
    seq18_signed = json.loads(signed_path.read_text(encoding="utf-8"))
    seq15 = json.loads(args.seq15_source.read_text(encoding="utf-8"))
    seq13 = json.loads(args.seq13_source.read_text(encoding="utf-8"))
    seq19 = fold(seq18, seq18_signed, seq15, seq13, observed_at=observed_at)
    args.output.write_text(
        json.dumps(seq19, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    digest = hashlib.sha256(canonicalize_json(seq19)).hexdigest()
    print(f"fold_pack_seq19: wrote {args.output}")
    print(f"fold_pack_seq19: seq-19 payload_sha256 = {digest}")
    print(f"fold_pack_seq19: retired {sorted(REMOVED_RULE_IDS)}")
    print(f"fold_pack_seq19: transplanted seq-15 repairs onto {sorted(EDITED_RULE_IDS)}")
    print("fold_pack_seq19: NOT SIGNED, NOT ACTIVATED — see sign_pack.py / activate_pack.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
