"""fold_pack_seq17.py — assemble RulePack seq-17 from the LIVE seq-16 payload
plus the 2026-08-30 freshness re-stamps. One concern, nothing else changes.

**Source re-stamp only.** All 18 ``OFFICIAL_PORTAL`` source records get
``verified_at``/``verified_by`` bumped, each backed by a live re-verification
performed 2026-08-30 (three parallel readers, six records each, plus two
independent orchestrator spot-checks — E31A and the VOA country list).
``content_sha256`` is untouched on every record: no page changed semantically,
so the description stays and only the attestation clock moves. No rule edits,
no product edits, no drops.

WHY THIS FOLD IS A REPAIR, NOT A SCHEDULED CYCLE
================================================
The earlier folds in this lane were PRE-EXPIRY re-stamps with a zero abstain
gap. This one is not: the 18 portal stamps expired at 2026-08-30T10:44:48Z and
production has been tripping ``DECISIVE_SOURCE_STALE`` ever since — every visa
product answering ``HUMAN_REVIEW_REQUIRED`` with an empty candidate list. The
weekly re-attestation lane did not run. The freshness sentinel DID fire, and
its alert was swallowed by the Telegram gateway's dedup on key
``visa-freshness:approaching:16`` — only the 04:43Z run was delivered.

WHY THE ANCHOR IS READ FROM THE DATABASE, NOT FROM DISK
=======================================================
Every earlier fold read its chain anchor from the previous
``rulepack-prod-0NN.signed.json`` **on this branch**. seq-16 is not there:
``contracts/packs/`` tops out at seq-15 on ``main``, while production has been
running seq-16 since 2026-08-26. So the anchor is the live payload, read from
the active activation in Postgres and re-hashed here (RFC 8785 JCS) before
anything is built on it. That the export is byte-faithful is not assumed: the
recomputed digest must equal ``visa_rule_packs.payload_sha256`` for the active
row, or this fold aborts.

CORRECTED 2026-08-30, after an adversarial review of this very diff: an earlier
draft of this docstring said seq-16 "does not exist in this repository at all".
That is FALSE, and the false version was propagated into the PR's brief and
evidence pack before the refuter caught it. The signed bundle **does** exist, on
the unmerged branch ``origin/feature/visa-oracle``, carrying exactly the digest
of the row that was active
(``ef17dc122380d1e5ca7a7360c21d64fbfea05681bf30b1447f6c14026bc94100``) — verified
with ``git show``, not assumed. Reading the anchor from the database was still
the right call, because the database is what production actually ran and a
branch is not evidence of that; but "absent from version control" was a claim
nobody had checked. The real gap is narrower and still open: a signed artifact
reached production while its source never reached ``main``.

DRIFT GUARDS
============
The restamped set is derived by ENTITY, never from a frozen id list: it must
equal exactly the records whose ``authority_type`` is ``OFFICIAL_PORTAL``. The
count 18 is pinned separately as a tripwire — if the pack gained or lost a
portal source, this fold was authored against a different world and aborts
rather than adapting. ``rules`` and ``products`` are held to whole-collection
equality with seq-16; there is no carve-out to make.

Deterministic: the stamp instant is a constant, never ``datetime.now()``, so
re-running produces byte-identical output.

Usage::

    PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq17 \\
        --seq16-payload <path to the DB export> --output <seq-17 source path>
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

#: The active seq-16 payload digest, as recorded in ``visa_rule_packs`` for the
#: activation whose ``system_period`` is still open. Read 2026-08-30 via the
#: read-only production role.
SEQ16_PAYLOAD_SHA256 = "ef17dc122380d1e5ca7a7360c21d64fbfea05681bf30b1447f6c14026bc94100"

#: The instant these 18 pages were actually fetched and read. Chosen AFTER the
#: last reader returned (13:16:40Z) and before the fold ran — never rounded
#: forward, because the stamp is a claim about when someone looked.
RESTAMP_VERIFIED_AT = "2026-08-30T13:18:00Z"

RESTAMP_VERIFIED_BY = (
    "agent.air-m5.backend-rag.visa-freshness-restamp.live-recheck-2026-08-30"
)

FOLD_CREATED_AT = "2026-08-30T13:20:00Z"
FOLD_CREATED_BY = "agent.air-m5.backend-rag.visa-freshness-restamp.fold-2026-08-30"

PORTAL_AUTHORITY = "OFFICIAL_PORTAL"
EXPECTED_PORTAL_COUNT = 18
EXPECTED_SEQ16_STAMP = "2026-08-23T10:44:48Z"

#: The ONLY top-level keys this fold may move. Everything else in the payload
#: is held to equality with seq-16 — see the guard in ``fold()`` for why this
#: is an allow-list of CHANGES rather than a list of things to leave alone.
CHANGED_TOP_LEVEL_KEYS = frozenset(
    {
        "sequence",
        "rule_pack_id",
        "created_at",
        "created_by",
        "previous_payload_sha256",
        "rollback_of_payload_sha256",
        "source_records",
    }
)

#: The ONLY fields that may move inside a portal source record.
RESTAMPED_RECORD_FIELDS = frozenset({"verified_at", "verified_by"})

# seq-16/seq-17 identity (the uuid5 anchor is VERIFIED against the pack being
# folded, never assumed). ``rule_pack_id`` is the primary key of
# ``visa_rule_packs`` and packs are immutable there: carrying seq-16's id into
# seq-17 makes the row a mutation of an existing pack, and ``activate_pack``
# rejects it — measured live 2026-08-30 ("already holds ... with a DIFFERENT
# payload_sha256"). Nothing was written; the guard is the reason.
_RULE_PACK_ID_URL_PREFIX = (
    "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/"
)


def _rule_pack_id(sequence: int) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"{_RULE_PACK_ID_URL_PREFIX}{sequence}")


def _fail(message: str) -> None:
    raise SystemExit(f"fold_pack_seq17: {message}")


def fold(seq16: dict[str, Any]) -> dict[str, Any]:
    """Return the seq-17 payload, or abort loudly."""
    digest = hashlib.sha256(canonicalize_json(seq16)).hexdigest()
    if digest != SEQ16_PAYLOAD_SHA256:
        _fail(
            "the seq-16 export is not byte-faithful: recomputed JCS digest "
            f"{digest} != the payload_sha256 recorded for the active activation "
            f"({SEQ16_PAYLOAD_SHA256}). Re-export before folding — everything "
            "below would otherwise be built on a payload production never ran."
        )
    if seq16.get("sequence") != 16:
        _fail(f"expected sequence 16, got {seq16.get('sequence')!r}")

    records = seq16["source_records"]
    portals = [r for r in records if r.get("authority_type") == PORTAL_AUTHORITY]
    if len(portals) != EXPECTED_PORTAL_COUNT:
        _fail(
            f"expected {EXPECTED_PORTAL_COUNT} {PORTAL_AUTHORITY} records, found "
            f"{len(portals)} — this fold was authored against a different pack"
        )
    stamps = {r.get("verified_at") for r in portals}
    if stamps != {EXPECTED_SEQ16_STAMP}:
        _fail(
            "the portal records do not all carry the expected seq-16 stamp "
            f"{EXPECTED_SEQ16_STAMP}; found {sorted(str(s) for s in stamps)}. "
            "Re-read the ledger before restamping — a mixed set means someone "
            "already moved part of it."
        )

    out = json.loads(json.dumps(seq16))
    restamped = 0
    for record in out["source_records"]:
        if record.get("authority_type") != PORTAL_AUTHORITY:
            continue
        record["verified_at"] = RESTAMP_VERIFIED_AT
        record["verified_by"] = RESTAMP_VERIFIED_BY
        restamped += 1
    if restamped != EXPECTED_PORTAL_COUNT:
        _fail(f"restamped {restamped}, expected {EXPECTED_PORTAL_COUNT}")

    inherited_id = seq16.get("rule_pack_id")
    expected_seq16_id = str(_rule_pack_id(16))
    if inherited_id != expected_seq16_id:
        _fail(
            f"the seq-16 payload carries rule_pack_id={inherited_id!r}, but the "
            f"uuid5 convention yields {expected_seq16_id!r} — the anchor is "
            "verified, never assumed; refusing to mint seq-17's id from a "
            "convention this pack does not follow."
        )

    out["sequence"] = 17
    out["rule_pack_id"] = str(_rule_pack_id(17))
    out["created_at"] = FOLD_CREATED_AT
    out["created_by"] = FOLD_CREATED_BY
    out["previous_payload_sha256"] = SEQ16_PAYLOAD_SHA256
    out["rollback_of_payload_sha256"] = None

    assert_only_expected_changes(seq16, out)

    # Last: the result must still be a valid RulePackPayload. The fold operates
    # on plain dicts for byte-fidelity, which means nothing until now has
    # checked the output against the contract the engine will parse it with.
    RulePackPayload.model_validate(out)

    return out


def assert_only_expected_changes(before: dict[str, Any], after: dict[str, Any]) -> None:
    """Abort unless ``after`` differs from ``before`` in exactly the ways a
    re-stamp is allowed to differ.

    Extracted from :func:`fold` so it can be exercised on hand-built pairs. It
    could not be tested through ``fold`` at all: every mutation injected into
    the INPUT is caught first by the chain-anchor digest check, so a test that
    mutates the input proves the digest gate works and says NOTHING about this
    one. That is how the first attempt at a guilt test came back green while
    testing nothing.

    FAIL-CLOSED, both axes. The first version of this guard listed the keys
    that must NOT move; an adversarial review of this very diff (codex
    gpt-5.6-sol, 2026-08-30) showed the list left ``version``, ``environment``,
    ``jurisdiction``, ``decision_domain`` and the three ``engine_*_version``
    keys unguarded — a fold could have changed any of them and still reported
    "nothing else changed". The committed artifact was in fact clean; the
    PROMISE was not. So the polarity is inverted: name what MAY move, and
    require universal equality for everything else. A key added to the payload
    in some future sequence is then guarded automatically instead of silently
    escaping an allow-list.
    """
    if set(after) != set(before):
        _fail(
            "the payload's top-level key set changed "
            f"(added {sorted(set(after) - set(before))}, "
            f"removed {sorted(set(before) - set(after))}) — this fold restamps "
            "sources and nothing else"
        )
    for key in set(before) - CHANGED_TOP_LEVEL_KEYS:
        if json.dumps(after.get(key), sort_keys=True) != json.dumps(
            before.get(key), sort_keys=True
        ):
            _fail(f"{key} changed — this fold restamps sources and nothing else")

    # Same inversion inside the records. The old check compared only the
    # NON-portal records, so any field of a portal record — `content_sha256`
    # above all, the one field whose drift would pair a fresh attestation with
    # a stale fingerprint — could move unnoticed.
    before_records = before["source_records"]
    after_records = after["source_records"]
    if len(after_records) != len(before_records):
        _fail("the source_records list changed length — only stamps move here")
    for new, old in zip(after_records, before_records, strict=True):
        if set(new) != set(old):
            _fail(f"a source record's field set changed: {old.get('source_record_id')!r}")
        allowed = (
            RESTAMPED_RECORD_FIELDS
            if old.get("authority_type") == PORTAL_AUTHORITY
            else frozenset()
        )
        for field in set(old) - allowed:
            if json.dumps(new.get(field), sort_keys=True) != json.dumps(
                old.get(field), sort_keys=True
            ):
                _fail(
                    f"source record {old.get('source_record_id')!r} changed "
                    f"field {field!r} — only {sorted(RESTAMPED_RECORD_FIELDS)} may "
                    "move, and only on portal records"
                )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fold RulePack seq-17.")
    parser.add_argument("--seq16-payload", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    seq16 = json.loads(args.seq16_payload.read_text(encoding="utf-8"))
    seq17 = fold(seq16)
    args.output.write_text(
        json.dumps(seq17, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    digest = hashlib.sha256(canonicalize_json(seq17)).hexdigest()
    print(f"fold_pack_seq17: wrote {args.output}")
    print(f"fold_pack_seq17: seq-17 payload_sha256 = {digest}")
    print(f"fold_pack_seq17: chained to seq-16 {SEQ16_PAYLOAD_SHA256}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
