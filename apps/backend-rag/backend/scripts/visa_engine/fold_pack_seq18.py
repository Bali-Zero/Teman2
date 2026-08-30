"""fold_pack_seq18.py — widen the OFFICIAL_PORTAL freshness window to 32 days.

One concern, nothing else changes. This fold moves
``freshness_policy.max_age_seconds`` from 604800 (seven days) to 2764800
(thirty-two days) on the eighteen ``OFFICIAL_PORTAL`` source records, and
touches nothing else in the payload — not a stamp, not a rule, not a product.

WHY, AND WHAT IT COSTS
======================
Ordered by Zero on 2026-08-30, after the seven-day window expired unnoticed and
took the Visa Oracle silent on every product for roughly five hours: the portal
records were stamped ``2026-08-23T10:44:48Z`` and went STALE at exactly one
window later, folding every decision to ``HUMAN_REVIEW_REQUIRED`` with an empty
candidate list. seq-17 re-stamped them to ``2026-08-30T13:18:00Z``, which under
the old window would expire again on 2026-09-06.

Thirty-two days puts the next boundary at **2026-10-01T13:18:00Z**, which is
what was asked for.

State the cost plainly, because a widened freshness window is not free: the
engine may now decide on an official immigration portal that was last read a
MONTH ago. Seven days was not arbitrary — it was the assertion that these pages
change often enough to matter. Nothing about that changed; what changed is that
the re-attestation lane meant to honour it does not run, and its alert is deaf,
so the seven-day promise was being kept by nobody. A thirty-two-day window that
is actually honoured is safer than a seven-day window that silently lapses. It
is NOT a substitute for repairing the lane and the alert, and must not be read
as closing either.

WHAT IS DELIBERATELY *NOT* DONE HERE
====================================
No re-stamp. ``verified_at`` and ``verified_by`` keep seq-17's values on every
record, because no one has re-read the pages since. Moving a stamp without a
reading is exactly the false attestation the seq-17 review warned about; this
fold changes a POLICY, and a policy change needs no attestation.

The non-portal authorities (``PRIMARY_LAW``, ``IMPLEMENTING_REGULATION``) are
untouched: their window is already a year and this fold has no opinion on it.

WHAT THIS FOLD FIXES FROM SEQ-17's REVIEW
=========================================
``version`` is set to the fold date. seq-17 inherited seq-16's ``2026.8.26``
while being created on 2026-08-30 — a real finding from the kimi review that
could not be corrected inside a signed, already-active artifact. It is corrected
forward, here, which is the only honest way to correct a signed artifact.

The guard is the fail-closed one seq-17's review produced, imported rather than
re-implemented: an explicit allow-list of what may change, universal equality
for everything else, at both the payload level and the record level.

Usage::

    PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq18 \\
        --seq17-source <path to rulepack-prod-017.source.json> \\
        --output <seq-18 source path>
"""

from __future__ import annotations

import argparse
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

#: The seq-17 payload digest — the chain anchor, and the digest activated in
#: production on 2026-08-30T15:35:49Z.
SEQ17_PAYLOAD_SHA256 = "97cb964780b114a2fa936230055327102a5af59efb010b6bf04090bb7321890b"

#: Seven days. What every OFFICIAL_PORTAL record carries in seq-17.
OLD_MAX_AGE_SECONDS = 604_800

#: Thirty-two days. Chosen so the boundary lands on 2026-10-01T13:18:00Z given
#: seq-17's stamp of 2026-08-30T13:18:00Z — the date Zero asked for, not a round
#: number picked for tidiness.
NEW_MAX_AGE_SECONDS = 2_764_800

FOLD_CREATED_AT = "2026-08-31T00:00:00Z"
FOLD_CREATED_BY = "agent.air-m5.backend-rag.visa-freshness-window.fold-2026-08-31"

#: Set on the payload, unlike seq-17 which inherited a stale value. See the
#: module docstring.
FOLD_VERSION = "2026.8.31"

PORTAL_AUTHORITY = "OFFICIAL_PORTAL"
EXPECTED_PORTAL_COUNT = 18
EXPECTED_SEQ17_STAMP = "2026-08-30T13:18:00Z"

_RULE_PACK_ID_URL_PREFIX = (
    "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/"
)

#: The only top-level keys this fold may move.
CHANGED_TOP_LEVEL_KEYS = frozenset(
    {
        "sequence",
        "rule_pack_id",
        "version",
        "created_at",
        "created_by",
        "previous_payload_sha256",
        "rollback_of_payload_sha256",
        "source_records",
    }
)

#: The only field that may move inside a portal source record.
CHANGED_RECORD_FIELDS = frozenset({"freshness_policy"})


def _rule_pack_id(sequence: int) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"{_RULE_PACK_ID_URL_PREFIX}{sequence}")


def _fail(message: str) -> None:
    raise SystemExit(f"fold_pack_seq18: {message}")


def assert_changed_fields_hold_their_expected_values(after: dict[str, Any]) -> None:
    """Abort unless every field this fold is ALLOWED to move holds the value it
    is supposed to move to.

    ``assert_only_expected_changes`` names what MAY change and then excludes
    exactly those fields from comparison — which means it is silent about
    whether they changed to the RIGHT thing. Adversarial review of this diff
    demonstrated the gap concretely: ``max_age_seconds = 1``, ``sequence = 19``,
    ``version = "2026.9.99"``, ``created_at = "2099-01-01T00:00:00Z"``, a
    fabricated ``previous_payload_sha256`` and a spurious
    ``rollback_of_payload_sha256`` all passed both the guard and
    ``RulePackPayload.model_validate`` — the model accepts any positive window
    and binds none of these to this fold's intent.

    Nothing today reaches those states, because ``fold()`` writes the values
    itself. That is precisely why this is worth pinning: the guard is *claimed*
    to be fail-closed, and a claim that only holds while the code above it stays
    correct is not a guard, it is a comment.
    """
    expected: dict[str, Any] = {
        "sequence": 18,
        "rule_pack_id": str(_rule_pack_id(18)),
        "version": FOLD_VERSION,
        "created_at": FOLD_CREATED_AT,
        "created_by": FOLD_CREATED_BY,
        "previous_payload_sha256": SEQ17_PAYLOAD_SHA256,
        "rollback_of_payload_sha256": None,
    }
    for key, want in expected.items():
        got = after.get(key)
        if got != want:
            _fail(f"{key} is {got!r}, expected {want!r}")

    portals = [r for r in after["source_records"] if r.get("authority_type") == PORTAL_AUTHORITY]
    if len(portals) != EXPECTED_PORTAL_COUNT:
        _fail(f"expected {EXPECTED_PORTAL_COUNT} portal records in the output, got {len(portals)}")
    windows = {r["freshness_policy"]["max_age_seconds"] for r in portals}
    if windows != {NEW_MAX_AGE_SECONDS}:
        _fail(
            f"portal windows are {sorted(windows)}, expected every one to be "
            f"{NEW_MAX_AGE_SECONDS}"
        )


def assert_only_expected_changes(before: dict[str, Any], after: dict[str, Any]) -> None:
    """Abort unless ``after`` differs from ``before`` in exactly the ways a
    window change is allowed to differ.

    Fail-closed on both axes, as seq-17's adversarial review established: name
    what MAY move and require universal equality for everything else, so a key
    added in some future sequence is guarded automatically rather than escaping
    an allow-list of things to leave alone.

    Extracted so it can be tested at all: mutating a fold's INPUT is caught
    first by the chain-anchor digest check, so a test that does that proves the
    digest gate works and says nothing about this guard.
    """
    if set(after) != set(before):
        _fail(
            "the payload's top-level key set changed "
            f"(added {sorted(set(after) - set(before))}, "
            f"removed {sorted(set(before) - set(after))})"
        )
    for key in set(before) - CHANGED_TOP_LEVEL_KEYS:
        if json.dumps(after.get(key), sort_keys=True) != json.dumps(
            before.get(key), sort_keys=True
        ):
            _fail(f"{key} changed — this fold widens the portal window and nothing else")

    before_records = before["source_records"]
    after_records = after["source_records"]
    if len(after_records) != len(before_records):
        _fail("the source_records list changed length")
    for new, old in zip(after_records, before_records, strict=True):
        if set(new) != set(old):
            _fail(f"a source record's field set changed: {old.get('source_record_id')!r}")
        allowed = (
            CHANGED_RECORD_FIELDS
            if old.get("authority_type") == PORTAL_AUTHORITY
            else frozenset()
        )
        for field in set(old) - allowed:
            if json.dumps(new.get(field), sort_keys=True) != json.dumps(
                old.get(field), sort_keys=True
            ):
                _fail(
                    f"source record {old.get('source_record_id')!r} changed field "
                    f"{field!r} — only freshness_policy may move, and only on "
                    "portal records"
                )
        # Inside freshness_policy, only the window may move: `kind` is the
        # closed discriminator and must survive untouched.
        if old.get("authority_type") == PORTAL_AUTHORITY:
            if new["freshness_policy"].get("kind") != old["freshness_policy"].get("kind"):
                _fail("a portal record's freshness_policy.kind changed")
            if set(new["freshness_policy"]) != set(old["freshness_policy"]):
                _fail("a portal record's freshness_policy field set changed")


def assert_anchor_is_a_verified_signed_artifact(
    signed_envelope: dict[str, Any],
    digest: str,
    *,
    observed_at: datetime | None = None,
) -> None:
    """Require the chain anchor to be a SIGNED seq-17 pack, not just a digest.

    Recomputing the digest of the source file and comparing it to
    ``SEQ17_PAYLOAD_SHA256`` proves only that the input matches a constant
    written in THIS file — an author who pinned the digest of a valid but
    never-signed pack would sail through it. So the signed seq-17 bundle is
    opened, its Ed25519 signature verified against the SAME trust store
    production uses (``VISA_ENGINE_TRUST_STORE_KEYS_JSON``, a public key, not
    a secret), and its verified ``payload_sha256`` required to equal the
    digest recomputed from the source.

    What this still does NOT prove is ACTIVATION — a signed pack and an active
    pack are different claims, and only the production catalog can settle the
    second. That receipt lives in the evidence pack, deliberately, not here.
    """
    try:
        trust_store = StaticTrustStore.from_env()
    except RulePackVerificationError as exc:
        _fail(
            f"cannot verify the seq-17 anchor's signature: {exc}. Export the "
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
        _fail(f"the seq-17 signed bundle does not verify: {exc}")

    signed_digest = verified.payload_sha256.hex()
    if signed_digest != digest:
        _fail(
            f"the seq-17 SOURCE digest {digest} is not the digest of the signed "
            f"seq-17 artifact ({signed_digest}) — the source on disk and the "
            "artifact production verifies are two different payloads."
        )
    if verified.pack.payload.sequence != 17:
        _fail(
            "the signed bundle handed in as the seq-17 anchor carries sequence "
            f"{verified.pack.payload.sequence}"
        )


def fold(seq17: dict[str, Any], seq17_signed: dict[str, Any]) -> dict[str, Any]:
    """Return the seq-18 payload, or abort loudly.

    ``seq17_signed`` is the signed seq-17 envelope and is REQUIRED, not
    optional: an anchor check a caller can skip is not a check. See
    :func:`assert_anchor_is_a_verified_signed_artifact`.
    """
    digest = hashlib.sha256(canonicalize_json(seq17)).hexdigest()
    if digest != SEQ17_PAYLOAD_SHA256:
        _fail(
            "the seq-17 source is not the activated artifact: recomputed JCS "
            f"digest {digest} != {SEQ17_PAYLOAD_SHA256}. Everything below would "
            "otherwise be built on a payload production never ran."
        )
    assert_anchor_is_a_verified_signed_artifact(seq17_signed, digest)
    if seq17.get("sequence") != 17:
        _fail(f"expected sequence 17, got {seq17.get('sequence')!r}")

    inherited_id = seq17.get("rule_pack_id")
    expected = str(_rule_pack_id(17))
    if inherited_id != expected:
        _fail(
            f"the seq-17 payload carries rule_pack_id={inherited_id!r}, but the "
            f"uuid5 convention yields {expected!r} — the anchor is verified, "
            "never assumed."
        )

    records = seq17["source_records"]
    portals = [r for r in records if r.get("authority_type") == PORTAL_AUTHORITY]
    if len(portals) != EXPECTED_PORTAL_COUNT:
        _fail(
            f"expected {EXPECTED_PORTAL_COUNT} {PORTAL_AUTHORITY} records, found "
            f"{len(portals)} — this fold was authored against a different pack"
        )
    if {r.get("verified_at") for r in portals} != {EXPECTED_SEQ17_STAMP}:
        _fail(
            "the portal records do not all carry seq-17's stamp "
            f"{EXPECTED_SEQ17_STAMP} — someone already moved part of the ledger"
        )
    windows = {r["freshness_policy"]["max_age_seconds"] for r in portals}
    if windows != {OLD_MAX_AGE_SECONDS}:
        _fail(
            f"expected every portal window to be {OLD_MAX_AGE_SECONDS}, found "
            f"{sorted(windows)} — refusing to widen a set that is not uniform"
        )

    out = json.loads(json.dumps(seq17))
    widened = 0
    for record in out["source_records"]:
        if record.get("authority_type") != PORTAL_AUTHORITY:
            continue
        record["freshness_policy"]["max_age_seconds"] = NEW_MAX_AGE_SECONDS
        widened += 1
    if widened != EXPECTED_PORTAL_COUNT:
        _fail(f"widened {widened}, expected {EXPECTED_PORTAL_COUNT}")

    out["sequence"] = 18
    out["rule_pack_id"] = str(_rule_pack_id(18))
    out["version"] = FOLD_VERSION
    out["created_at"] = FOLD_CREATED_AT
    out["created_by"] = FOLD_CREATED_BY
    out["previous_payload_sha256"] = SEQ17_PAYLOAD_SHA256
    out["rollback_of_payload_sha256"] = None

    assert_only_expected_changes(seq17, out)
    assert_changed_fields_hold_their_expected_values(out)
    RulePackPayload.model_validate(out)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fold RulePack seq-18.")
    parser.add_argument("--seq17-source", required=True, type=Path)
    parser.add_argument(
        "--seq17-signed",
        type=Path,
        default=None,
        help=(
            "the signed seq-17 envelope; defaults to the .signed.json sibling "
            "of --seq17-source. Its signature is verified — the anchor is never "
            "taken on the digest constant alone."
        ),
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    signed_path = args.seq17_signed or Path(
        str(args.seq17_source).replace(".source.json", ".signed.json")
    )
    if signed_path == args.seq17_source or not signed_path.exists():
        _fail(f"no signed seq-17 bundle at {signed_path} — pass --seq17-signed")

    seq17 = json.loads(args.seq17_source.read_text(encoding="utf-8"))
    seq17_signed = json.loads(signed_path.read_text(encoding="utf-8"))
    seq18 = fold(seq17, seq17_signed)
    args.output.write_text(
        json.dumps(seq18, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    digest = hashlib.sha256(canonicalize_json(seq18)).hexdigest()
    print(f"fold_pack_seq18: wrote {args.output}")
    print(f"fold_pack_seq18: seq-18 payload_sha256 = {digest}")
    print(f"fold_pack_seq18: portal window {OLD_MAX_AGE_SECONDS} -> {NEW_MAX_AGE_SECONDS}s")
    print("fold_pack_seq18: next portal boundary = 2026-10-01T13:18:00Z")
    return 0


if __name__ == "__main__":
    sys.exit(main())
