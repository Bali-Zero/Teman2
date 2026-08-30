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
from pathlib import Path
from typing import Any

from backend.services.visa_engine.bundle import canonicalize_json
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


def fold(seq17: dict[str, Any]) -> dict[str, Any]:
    """Return the seq-18 payload, or abort loudly."""
    digest = hashlib.sha256(canonicalize_json(seq17)).hexdigest()
    if digest != SEQ17_PAYLOAD_SHA256:
        _fail(
            "the seq-17 source is not the activated artifact: recomputed JCS "
            f"digest {digest} != {SEQ17_PAYLOAD_SHA256}. Everything below would "
            "otherwise be built on a payload production never ran."
        )
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
    RulePackPayload.model_validate(out)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fold RulePack seq-18.")
    parser.add_argument("--seq17-source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    seq17 = json.loads(args.seq17_source.read_text(encoding="utf-8"))
    seq18 = fold(seq17)
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
