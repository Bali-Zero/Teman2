"""fold_pack_generic.py — derive pack N+1 (portal re-stamp) from a read ledger, for any anchor.

The sequence-agnostic successor of ``fold_pack_seq25``. Nothing is a constant of
one sequence: the anchor is a SIGNED bundle verified against the trust store, its
sequence and payload digest are read from that verified bundle, the next
sequence is anchor+1, and the previous portal stamp every receipt must postdate
is the anchor's own ``OFFICIAL_PORTAL`` ``verified_at`` (all must agree).

Every guard of the seq-25 fold is kept in semantics: each successful receipt is
validated (HTTP 200, key phrase, the record's own canonical URL, not in the
future, after the previous stamp), the saved text carries a receipt's
fingerprint, each judgement falls between the first read and now, ``changed``
needs a disposition by id (and, given ``--baseline-ledger-dir``, is refused on a text whose
fingerprint equals the baseline's), and ``checked_sentence`` is a substring of the saved
text. ``verified_at`` is the earliest successful read. Only identity fields and
the portal stamps move.

The ledger loader and the diff guard are imported from ``fold_pack_seq25``
(unchanged, they hold no sequence constants); error text from those helpers keeps
that module's prefix. The saved text is resolved HERE, from each receipt's own
``text_file`` (``text/<basename>``, so a ledger moved between worktrees still
reads; ``text/<8id>.txt`` when a receipt names none), because a per-fetch ledger
(``text/<8id>-<fetched_at>.txt``) has no single file per record. A ledger id that
is not an anchor OFFICIAL_PORTAL record aborts, and ``created_at`` may not
precede the latest read or judgement it dates.

Usage::

    PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_generic \\
        --anchor-source <packs>/rulepack-prod-024.source.json \\
        --anchor-signed <packs>/rulepack-prod-024.signed.json \\
        --ledger-dir research/visa/<date>-<slug> --output <packs>/rulepack-prod-025.source.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn

from backend.scripts.visa_engine.baseline_ledger import baseline_fingerprint
from backend.scripts.visa_engine.fold_pack_seq25 import (
    JUDGEMENT_VERDICTS,
    PORTAL_AUTHORITY,
    UTC_FORMAT,
    Ledger,
    _parse_utc,
    _rule_pack_id,
    _successful_receipts,
    assert_only_expected_changes,
    load_ledger,
)
from backend.scripts.visa_engine.ledger_paths import (
    LedgerPathError,
    read_receipt_text,
)
from backend.scripts.visa_engine.portal_read_receipt import fingerprint as text_fingerprint
from backend.services.visa_engine.bundle import (
    StaticTrustStore,
    canonicalize_json,
    verify_rule_pack,
)
from backend.services.visa_engine.errors import RulePackVerificationError
from backend.services.visa_engine.models import RulePackPayload


def _fail(message: str) -> NoReturn:
    raise SystemExit(f"fold_pack_generic: {message}")


def _real_now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _fmt(instant: datetime) -> str:
    return instant.strftime(UTC_FORMAT)


def verify_anchor(
    anchor: dict[str, Any],
    signed_envelope: dict[str, Any],
    *,
    trust_store: StaticTrustStore,
    observed_at: datetime,
) -> tuple[int, str]:
    """Verify the signed anchor; return (its sequence, its payload digest).

    ``RulePackVerificationError`` propagates untouched: a bad signature is not a
    formatting problem to be softened into an exit message.
    """
    verified = verify_rule_pack(signed_envelope, trust_store=trust_store, observed_at=observed_at)
    signed_digest = verified.payload_sha256.hex()
    source_digest = hashlib.sha256(canonicalize_json(anchor)).hexdigest()
    if source_digest != signed_digest:
        _fail(
            f"the anchor source digest {source_digest} is not the signed artifact's {signed_digest}"
        )
    sequence = verified.pack.payload.sequence
    if anchor.get("sequence") != sequence:
        _fail(
            f"the anchor source says sequence {anchor.get('sequence')!r}, the signed bundle {sequence}"
        )
    return sequence, signed_digest


def anchor_portal_stamp(portals: list[dict[str, Any]]) -> str:
    if not portals:
        _fail(f"the anchor carries no {PORTAL_AUTHORITY} record — nothing to re-stamp")
    stamps: dict[str, list[str]] = {}
    for record in portals:
        stamps.setdefault(str(record.get("verified_at")), []).append(record["source_record_id"][:8])
    if len(stamps) != 1:
        detail = "; ".join(f"{stamp}: {ids}" for stamp, ids in sorted(stamps.items()))
        _fail(
            f"the anchor's portal stamps disagree — someone already moved part of the set ({detail})"
        )
    return next(iter(stamps))


def _receipt_text(ledger: Ledger, receipt: dict[str, Any]) -> str | None:
    assert ledger.text_dir is not None
    try:
        return read_receipt_text(ledger.text_dir, receipt)
    except LedgerPathError as exc:
        _fail(str(exc))


def _own_text(ledger: Ledger, receipt: dict[str, Any]) -> str | None:
    """The saved text of ONE receipt if it carries the fingerprint that receipt recorded."""
    saved = _receipt_text(ledger, receipt)
    if saved is None:
        return None
    body = saved[:-1] if saved.endswith("\n") else saved
    return saved if text_fingerprint(body) == receipt.get("visible_text_sha256") else None


def _bound_receipt(
    successes: list[dict[str, Any]], judgement: dict[str, Any], judged_at: datetime, label: str
) -> dict[str, Any]:
    """The ONE receipt a judgement read: the latest success with ``fetched_at <= judged_at``.

    A judgement that names ``receipt_fetched_at`` / ``text_sha256`` must match that receipt;
    old ledgers name neither and fall back to the rule alone.
    """
    eligible = [r for r in successes if _parse_utc(r["fetched_at"], what="fetched_at") <= judged_at]
    if not eligible:
        _fail(f"{label}: no successful read precedes this judgement")
    bound = max(eligible, key=lambda r: r["fetched_at"])
    named = judgement.get("receipt_fetched_at")
    if named is not None and named != bound["fetched_at"]:
        _fail(
            f"{label}: judgement says it read the fetch of {named!r}, the receipt it binds to "
            f"is {bound['fetched_at']!r}"
        )
    fingerprint = judgement.get("text_sha256")
    if fingerprint is not None and fingerprint != bound.get("visible_text_sha256"):
        _fail(f"{label}: judgement text_sha256 is not the bound receipt's visible_text_sha256")
    return bound


def _assert_ledger_ids_are_portal_records(ledger: Ledger, portals: list[dict[str, Any]]) -> None:
    known = {r["source_record_id"] for r in portals}
    for kind, rows in (("receipt", ledger.receipts), ("judgement", ledger.judgements)):
        for row in rows:
            if row.get("source_record_id") not in known:
                _fail(
                    f"a {kind} names source_record_id {row.get('source_record_id')!r}, not an {PORTAL_AUTHORITY} record of the anchor"
                )


def latest_evidence(ledger: Ledger, portals: list[dict[str, Any]]) -> datetime:
    """The latest successful read or judgement instant — the pack may not be dated before it."""
    instants = [
        _parse_utc(str(row[key]), what=f"{key}")
        for record in portals
        for rows, key in (
            (_successful_receipts(ledger, record["source_record_id"]), "fetched_at"),
            (
                [
                    j
                    for j in ledger.judgements
                    if j.get("source_record_id") == record["source_record_id"]
                ],
                "judged_at",
            ),
        )
        for row in rows
    ]
    return max(instants)


def attestation_instant(
    ledger: Ledger,
    portals: list[dict[str, Any]],
    *,
    previous_stamp: str,
    now: datetime,
    baseline_dir: Path | None = None,
) -> str:
    """The ``verified_at`` the ledger supports (earliest successful read), or abort."""
    previous = _parse_utc(previous_stamp, what="previous portal stamp")
    _assert_ledger_ids_are_portal_records(ledger, portals)
    earliest: datetime | None = None
    for record in portals:
        record_id = record["source_record_id"]
        label = f"{record_id[:8]} ({record['source_key']})"
        successes = _successful_receipts(ledger, record_id)
        if not successes:
            _fail(
                f"{label}: no receipt with HTTP 200 and the key phrase found — not successfully read"
            )
        first_read: datetime | None = None
        for receipt in successes:
            if receipt.get("canonical_url") != record["canonical_url"]:
                _fail(
                    f"{label}: a receipt names {receipt.get('canonical_url')!r}, not the record's canonical_url"
                )
            instant = _parse_utc(receipt["fetched_at"], what=f"{record_id[:8]} fetched_at")
            if instant > now:
                _fail(f"{label}: receipt fetched_at {receipt['fetched_at']!r} is in the future")
            if instant <= previous:
                _fail(
                    f"{label}: receipt fetched_at {receipt['fetched_at']!r} is not after the previous stamp {previous_stamp}"
                )
            if first_read is None or instant < first_read:
                first_read = instant
        assert first_read is not None
        judged = [j for j in ledger.judgements if j.get("source_record_id") == record_id]
        if not judged:
            _fail(f"{label}: fetched but never judged")
        for judgement in judged:
            judged_at = _parse_utc(
                str(judgement.get("judged_at")), what=f"{record_id[:8]} judged_at"
            )
            if judged_at < first_read or judged_at > now:
                _fail(
                    f"{label}: judged_at {judgement.get('judged_at')!r} is not between the first "
                    f"successful read ({_fmt(first_read)}) and now"
                )
            verdict = judgement.get("semantic_change")
            if verdict not in JUDGEMENT_VERDICTS:
                _fail(
                    f"{label}: judgement verdict {verdict!r} is not one of {sorted(JUDGEMENT_VERDICTS)}"
                )
            if verdict == "unsure":
                _fail(f"{label}: a reader is unsure — resolve before stamping")
            if verdict == "changed" and baseline_dir is not None:
                base_fp = baseline_fingerprint(baseline_dir, record_id)
                judged_fp = _bound_receipt(successes, judgement, judged_at, label).get(
                    "visible_text_sha256"
                )
                if base_fp is not None and base_fp == judged_fp:
                    _fail(
                        f"{label}: the judgement says the page changed, but the text it judged has "
                        f"fingerprint {judged_fp}, identical to the baseline ledger's {base_fp} — "
                        "a contradictory judgement, not a changed page"
                    )
            if verdict == "changed" and record_id not in ledger.accepted_changed:
                _fail(
                    f"{label}: a reader reports the page changed and disposition.json does not accept it by id"
                )
            bound = _bound_receipt(successes, judgement, judged_at, label)
            bound_text = _own_text(ledger, bound)
            if bound_text is None:
                _fail(
                    f"{label}: the saved visible text of the read this judgement binds to "
                    f"({bound['fetched_at']}) is missing or does not carry that receipt's fingerprint"
                )
            sentence = judgement.get("checked_sentence")
            if not isinstance(sentence, str) or not sentence.strip() or sentence not in bound_text:
                _fail(
                    f"{label}: checked_sentence is not a substring of the text of the read it binds to "
                    f"({bound['fetched_at']})"
                )
        if earliest is None or first_read < earliest:
            earliest = first_read
    assert earliest is not None
    return _fmt(earliest)


def assert_wall_clock_sanity(
    payload: dict[str, Any], *, now: datetime, evidence_until: datetime | None = None
) -> None:
    created_at = _parse_utc(payload["created_at"], what="created_at")
    if created_at > now:
        _fail(f"created_at {payload['created_at']!r} is in the future")
    if evidence_until is not None and created_at < evidence_until:
        _fail(
            f"created_at {payload['created_at']!r} precedes the ledger's latest evidence {_fmt(evidence_until)}"
        )
    for record in payload["source_records"]:
        verified_at = _parse_utc(
            record["verified_at"], what=f"{record['source_record_id'][:8]} verified_at"
        )
        if verified_at > created_at:
            _fail(
                f"{record['source_record_id'][:8]}: verified_at {record['verified_at']!r} is after created_at"
            )


def fold(
    anchor: dict[str, Any],
    anchor_signed: dict[str, Any],
    ledger: Ledger,
    *,
    trust_store: StaticTrustStore,
    version: str,
    created_at: str,
    created_by: str,
    verified_by: str,
    observed_at: datetime | None = None,
    allow_fake_reader: bool = False,
    baseline_dir: Path | None = None,
) -> dict[str, Any]:
    """Return the payload of pack anchor+1, or abort loudly."""
    now = observed_at or _real_now_utc()
    anchor_sequence, anchor_digest = verify_anchor(
        anchor, anchor_signed, trust_store=trust_store, observed_at=now
    )
    if anchor.get("rule_pack_id") != str(_rule_pack_id(anchor_sequence)):
        _fail(
            "the anchor's rule_pack_id does not follow the uuid5 convention — refusing to mint the next"
        )

    portals = [r for r in anchor["source_records"] if r.get("authority_type") == PORTAL_AUTHORITY]
    previous_stamp = anchor_portal_stamp(portals)
    if not allow_fake_reader:
        fakes = sorted(
            {
                str(j.get("reader"))
                for j in ledger.judgements
                if str(j.get("reader")).startswith("fake")
            }
        )
        if fakes:
            _fail(
                f"judgements by a rehearsal reader {fakes} cannot stamp a pack (--allow-fake-reader is for rehearsals only)"
            )
    verified_at = attestation_instant(
        ledger, portals, previous_stamp=previous_stamp, now=now, baseline_dir=baseline_dir
    )

    out = json.loads(json.dumps(anchor))
    for record in out["source_records"]:
        if record.get("authority_type") == PORTAL_AUTHORITY:
            record["verified_at"] = verified_at
            record["verified_by"] = verified_by
    out["sequence"] = anchor_sequence + 1
    out["rule_pack_id"] = str(_rule_pack_id(anchor_sequence + 1))
    out["version"] = version
    out["created_at"] = created_at
    out["created_by"] = created_by
    out["previous_payload_sha256"] = anchor_digest
    out["rollback_of_payload_sha256"] = None

    assert_only_expected_changes(anchor, out)
    assert_wall_clock_sanity(out, now=now, evidence_until=latest_evidence(ledger, portals))
    RulePackPayload.model_validate(out)
    return out


def main(argv: list[str] | None = None, *, observed_at: datetime | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fold pack N+1 (portal re-stamp) from a signed anchor and a read ledger."
    )
    parser.add_argument("--anchor-source", required=True, type=Path)
    parser.add_argument("--anchor-signed", required=True, type=Path)
    parser.add_argument("--ledger-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--version", default=None, help="YYYY.M.D, default today UTC")
    parser.add_argument("--created-by", default="agent.fold-pack")
    parser.add_argument(
        "--verified-by", default=None, help="default: agent.fold-pack.live-recheck:<reader names>"
    )
    parser.add_argument(
        "--allow-fake-reader", action="store_true", help="rehearsal only: accept fake* readers"
    )
    parser.add_argument(
        "--created-at", default=None, help="ISO Z, default now rounded to the minute"
    )
    parser.add_argument(
        "--baseline-ledger-dir",
        type=Path,
        default=None,
        help="earlier attested ledger: a `changed` verdict on a text with its fingerprint is refused",
    )
    parser.add_argument("--trust-store-env", default="VISA_ENGINE_TRUST_STORE_KEYS_JSON")
    args = parser.parse_args(argv)

    if args.output in {args.anchor_source, args.anchor_signed}:
        _fail("--output collides with an input")
    now = observed_at or _real_now_utc()
    version = args.version or f"{now.year}.{now.month}.{now.day}"
    created_at = args.created_at or _fmt(now.replace(second=0, microsecond=0))
    try:
        trust_store = StaticTrustStore.from_env(args.trust_store_env)
    except RulePackVerificationError as exc:
        _fail(f"cannot verify the anchor's signature: {exc}")
    anchor = json.loads(args.anchor_source.read_text(encoding="utf-8"))
    anchor_signed = json.loads(args.anchor_signed.read_text(encoding="utf-8"))
    ledger = load_ledger(args.ledger_dir)
    readers = sorted({str(j.get("reader")) for j in ledger.judgements})
    verified_by = args.verified_by or f"agent.fold-pack.live-recheck:{'+'.join(readers)}"
    try:
        out = fold(
            anchor,
            anchor_signed,
            ledger,
            trust_store=trust_store,
            version=version,
            created_at=created_at,
            created_by=args.created_by,
            verified_by=verified_by,
            observed_at=observed_at,
            allow_fake_reader=args.allow_fake_reader,
            baseline_dir=args.baseline_ledger_dir,
        )
    except RulePackVerificationError as exc:
        _fail(f"the anchor does not verify: {exc}")
    args.output.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    digest = hashlib.sha256(canonicalize_json(out)).hexdigest()
    print(f"fold_pack_generic: wrote {args.output}")
    print(f"fold_pack_generic: seq-{out['sequence']} payload_sha256 = {digest}")
    print(
        f"fold_pack_generic: chained to seq-{out['sequence'] - 1} {out['previous_payload_sha256']}"
    )
    print("fold_pack_generic: NOT SIGNED, NOT ACTIVATED — see sign_pack.py / activate_pack.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
