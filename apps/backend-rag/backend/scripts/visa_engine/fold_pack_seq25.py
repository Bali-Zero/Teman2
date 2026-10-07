"""fold_pack_seq25.py — re-stamp the 18 OFFICIAL_PORTAL sources from a read ledger.

One concern, nothing else changes: ``verified_at``/``verified_by`` move on the
eighteen ``OFFICIAL_PORTAL`` records, plus the identity fields every fold moves
(``sequence``, ``rule_pack_id``, ``version``, ``created_at``, ``created_by``,
``previous_payload_sha256``). No rule, no product, no ``content_sha256`` moves.

WHY THIS FOLD EXISTS
====================
The 18 portal stamps of the active pack (seq-23 in the database, carried
unchanged into the signed-but-never-activated seq-24) read
``2026-08-30T13:18:00Z`` under the 32-day window seq-18 set, so they went
STALE at 2026-10-01T13:18:00Z and every Visa Oracle product has answered
``HUMAN_REVIEW_REQUIRED`` with an empty candidate list since (reason
``DECISIVE_SOURCE_STALE``). Second occurrence of the 2026-08-30 incident; the
weekly re-attestation lane still does not exist as a scheduled organ, and the
sentinel's alert was lost in the 2026-09-22→10-06 Telegram outage.

WHAT IS DIFFERENT FROM seq-17 (the previous re-stamp)
=====================================================
seq-17's attestation (``research/visa/2026-08-30-freshness-restamp-seq17-
attestation.md``) named its own defect: ``verified_at`` was a constant in a
Python file, and nothing on disk proved anyone had looked. Its rule — *write
the ledger during the reading* — is what this fold consumes. The stamp is not
typed here. It is DERIVED from a ledger directory produced while the pages
were read:

* ``*-receipts.jsonl`` — one line per fetch, written by
  ``portal_read_receipt.py`` at the instant of the request: URL, HTTP status,
  ``fetched_at``, whether the record's key phrase was found, the visible-text
  fingerprint, and the path of the saved visible text.
* ``*-judgements.jsonl`` — one line per record, written by a reader AFTER
  reading the saved text: a verbatim ``checked_sentence`` and a
  ``semantic_change`` verdict (``none`` / ``changed`` / ``unsure``).
* ``disposition.json`` — the orchestrator's named acceptance of every
  ``changed`` verdict (a page offering more than the pack models is not page
  drift, but someone has to say so, by id, with a reason).

The fold refuses unless, for EVERY portal record: at least one receipt is a
200 with the key phrase found; at least one judgement is not ``unsure``; every
``changed`` is dispositioned; and every ``checked_sentence`` is a substring of
the saved visible text it claims to quote. ``verified_at`` is then the
EARLIEST successful ``fetched_at`` across the whole ledger — the most
conservative claim about when someone looked (the attestation's second rule).

ANCHOR: seq-24, SIGNED and the next pack to activate
====================================================
Activation requires ``previous_payload_sha256`` to equal the hash of the pack
that is active at that instant (``bundle.validate_activation``). seq-24 is
signed by the owner and ruled (2026-09-27, E33F) but was never activated, so
the ceremony is two activations in order: seq-24, then this pack. The anchor is
the signed seq-24 artifact, verified against the production trust store the
way seq-24 verified seq-23 — never a digest constant alone.

``content_sha256`` is a quotation fingerprint, never a fetch hash (Ditjen pages
embed a per-request CSRF token); it is deliberately untouched, exactly as in
seq-13/seq-17. Deterministic: given the same ledger and anchor the output is
byte-identical; the only clock read is for validation (nothing may be stamped
in the future).

Usage::

    PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq25 \\
        --seq24-source backend/services/visa_engine/contracts/packs/rulepack-prod-024.source.json \\
        --ledger-dir research/visa/2026-10-07-freshness-restamp-seq25 \\
        --output backend/services/visa_engine/contracts/packs/rulepack-prod-025.source.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn

from backend.scripts.visa_engine.portal_read_receipt import fingerprint as text_fingerprint
from backend.services.visa_engine.bundle import (
    StaticTrustStore,
    canonicalize_json,
    verify_rule_pack,
)
from backend.services.visa_engine.errors import RulePackVerificationError
from backend.services.visa_engine.models import RulePackPayload

#: The signed seq-24 artifact's payload digest (``rulepack-prod-024.signed.json``,
#: kid ``prod-2026-07-1``, signed 2026-09-27T01:31:02Z). The anchor is verified
#: against the trust store at fold time; this constant only pins WHICH pack.
SEQ24_PAYLOAD_SHA256 = (
    "5a569091f84a858f1957cdf96086ee7212f67d13a8225d64492a7212093cd272"  # pragma: allowlist secret
)

RESTAMP_VERIFIED_BY = "agent.air-m5.backend-rag.visa-freshness-restamp.live-recheck-2026-10-07"
FOLD_CREATED_AT = "2026-10-07T13:38:00Z"
FOLD_CREATED_BY = "agent.air-m5.backend-rag.visa-freshness-restamp.fold-2026-10-07"
#: seq-17 inherited seq-16's version and the attestation asked the next fold to
#: set it; seq-24 set ``2026.9.27``. Same convention: the fold date.
FOLD_VERSION = "2026.10.7"

PORTAL_AUTHORITY = "OFFICIAL_PORTAL"
EXPECTED_PORTAL_COUNT = 18
EXPECTED_SEQ24_STAMP = "2026-08-30T13:18:00Z"
UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

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
RESTAMPED_RECORD_FIELDS = frozenset({"verified_at", "verified_by"})
JUDGEMENT_VERDICTS = frozenset({"none", "changed", "unsure"})

_RULE_PACK_ID_URL_PREFIX = "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/"


def _rule_pack_id(sequence: int) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"{_RULE_PACK_ID_URL_PREFIX}{sequence}")


def _fail(message: str) -> NoReturn:
    raise SystemExit(f"fold_pack_seq25: {message}")


def _parse_utc(value: str, *, what: str) -> datetime:
    try:
        return datetime.strptime(value, UTC_FORMAT).replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        _fail(f"{what} {value!r} is not a {UTC_FORMAT} instant")


def _real_now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# The read ledger
# ---------------------------------------------------------------------------


@dataclass
class Ledger:
    receipts: list[dict[str, Any]] = field(default_factory=list)
    judgements: list[dict[str, Any]] = field(default_factory=list)
    accepted_changed: dict[str, str] = field(default_factory=dict)
    text_dir: Path | None = None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            _fail(f"{path.name}:{number} is not JSON: {exc}")
        if not isinstance(row, dict):
            _fail(f"{path.name}:{number} is not an object")
        rows.append(row)
    return rows


def load_ledger(ledger_dir: Path) -> Ledger:
    if not ledger_dir.is_dir():
        _fail(f"ledger dir {ledger_dir} does not exist — the pages were not read")
    ledger = Ledger(text_dir=ledger_dir / "text")
    for path in sorted(ledger_dir.glob("*-receipts.jsonl")):
        ledger.receipts.extend(_read_jsonl(path))
    for path in sorted(ledger_dir.glob("*-judgements.jsonl")):
        ledger.judgements.extend(_read_jsonl(path))
    disposition_path = ledger_dir / "disposition.json"
    if disposition_path.exists():
        disposition = json.loads(disposition_path.read_text(encoding="utf-8"))
        accepted = disposition.get("accepted_changed", {})
        if not isinstance(accepted, dict) or any(
            not isinstance(k, str) or not isinstance(v, str) or not v.strip()
            for k, v in accepted.items()
        ):
            _fail("disposition.json accepted_changed must map source_record_id -> non-empty reason")
        ledger.accepted_changed = dict(accepted)
    if not ledger.receipts:
        _fail(f"no *-receipts.jsonl under {ledger_dir} — nothing was fetched")
    if not ledger.judgements:
        _fail(f"no *-judgements.jsonl under {ledger_dir} — nothing was judged")
    return ledger


def _successful_receipts(ledger: Ledger, record_id: str) -> list[dict[str, Any]]:
    return [
        r
        for r in ledger.receipts
        if r.get("source_record_id") == record_id
        and r.get("http_status") == 200
        and r.get("key_phrase_found") is True
        and isinstance(r.get("fetched_at"), str)
    ]


def _quote_is_in_saved_text(ledger: Ledger, judgement: dict[str, Any]) -> bool:
    sentence = judgement.get("checked_sentence")
    if not isinstance(sentence, str) or not sentence.strip() or ledger.text_dir is None:
        return False
    text_path = ledger.text_dir / f"{judgement['source_record_id'][:8]}.txt"
    if not text_path.exists():
        return False
    return sentence in text_path.read_text(encoding="utf-8")


def _saved_text_matches_a_receipt(ledger: Ledger, record_id: str, successes: list[dict[str, Any]]) -> bool:
    """The saved visible text must carry the fingerprint SOME successful receipt
    recorded at request time — a text file edited after the fetch (or written by
    nothing) cannot be quoted from (Gemini review finding 1, 2026-10-07)."""
    if ledger.text_dir is None:
        return False
    text_path = ledger.text_dir / f"{record_id[:8]}.txt"
    if not text_path.exists():
        return False
    saved = text_path.read_text(encoding="utf-8")
    if saved.endswith("\n"):
        saved = saved[:-1]
    actual = text_fingerprint(saved)
    return any(r.get("visible_text_sha256") == actual for r in successes)


def attestation_instant(ledger: Ledger, portal_records: list[dict[str, Any]]) -> str:
    """The ``verified_at`` the ledger supports, or abort naming the gap."""
    earliest: datetime | None = None
    for record in portal_records:
        record_id = record["source_record_id"]
        successes = _successful_receipts(ledger, record_id)
        if not successes:
            _fail(
                f"{record_id[:8]} ({record['source_key']}): no receipt with HTTP 200 and the "
                "key phrase found — this page was not successfully read; it cannot be re-stamped"
            )
        if not _saved_text_matches_a_receipt(ledger, record_id, successes):
            _fail(
                f"{record_id[:8]} ({record['source_key']}): the saved visible text does not carry the "
                "fingerprint of any successful receipt — it is not what was served at a recorded read"
            )
        judged = [j for j in ledger.judgements if j.get("source_record_id") == record_id]
        if not judged:
            _fail(f"{record_id[:8]} ({record['source_key']}): fetched but never judged")
        for judgement in judged:
            verdict = judgement.get("semantic_change")
            if verdict not in JUDGEMENT_VERDICTS:
                _fail(f"{record_id[:8]}: judgement verdict {verdict!r} is not one of {sorted(JUDGEMENT_VERDICTS)}")
            if verdict == "unsure":
                _fail(f"{record_id[:8]} ({record['source_key']}): a reader is unsure — resolve before stamping")
            if verdict == "changed" and record_id not in ledger.accepted_changed:
                _fail(
                    f"{record_id[:8]} ({record['source_key']}): a reader reports the page changed and "
                    "disposition.json does not accept it by id with a reason"
                )
            if not _quote_is_in_saved_text(ledger, judgement):
                _fail(
                    f"{record_id[:8]}: checked_sentence is not a substring of the saved visible text — "
                    "the quote does not come from what was served"
                )
        for receipt in successes:
            instant = _parse_utc(receipt["fetched_at"], what=f"{record_id[:8]} fetched_at")
            if earliest is None or instant < earliest:
                earliest = instant
    assert earliest is not None
    return earliest.strftime(UTC_FORMAT)


# ---------------------------------------------------------------------------
# The anchor
# ---------------------------------------------------------------------------


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
            f"cannot verify the seq-24 anchor's signature: {exc}. Export the production "
            "trust store (VISA_ENGINE_TRUST_STORE_KEYS_JSON) and re-run — the anchor is never "
            "taken on a digest constant alone."
        )
    try:
        verified = verify_rule_pack(
            signed_envelope,
            trust_store=trust_store,
            observed_at=observed_at or _real_now_utc(),
        )
    except RulePackVerificationError as exc:
        _fail(f"the seq-24 signed bundle does not verify: {exc}")
    signed_digest = verified.payload_sha256.hex()
    if signed_digest != digest:
        _fail(
            f"the seq-24 SOURCE digest {digest} is not the digest of the signed seq-24 artifact "
            f"({signed_digest}) — two different payloads"
        )
    if verified.pack.payload.sequence != 24:
        _fail(f"the signed bundle handed in as the seq-24 anchor carries sequence {verified.pack.payload.sequence}")


# ---------------------------------------------------------------------------
# The fold
# ---------------------------------------------------------------------------


def assert_only_expected_changes(before: dict[str, Any], after: dict[str, Any]) -> None:
    """Allow-list of CHANGES; universal equality for everything else (seq-17's
    inverted-polarity guard, verbatim in spirit)."""
    if set(after) != set(before):
        _fail(
            "the payload's top-level key set changed "
            f"(added {sorted(set(after) - set(before))}, removed {sorted(set(before) - set(after))}) "
            "— this fold restamps sources and nothing else"
        )
    for key in set(before) - CHANGED_TOP_LEVEL_KEYS:
        if json.dumps(after.get(key), sort_keys=True) != json.dumps(before.get(key), sort_keys=True):
            _fail(f"{key} changed — this fold restamps sources and nothing else")
    before_records = before["source_records"]
    after_records = after["source_records"]
    if len(after_records) != len(before_records):
        _fail("the source_records list changed length — only stamps move here")
    for new, old in zip(after_records, before_records, strict=True):
        if set(new) != set(old):
            _fail(f"a source record's field set changed: {old.get('source_record_id')!r}")
        allowed = RESTAMPED_RECORD_FIELDS if old.get("authority_type") == PORTAL_AUTHORITY else frozenset()
        for name in set(old) - allowed:
            if json.dumps(new.get(name), sort_keys=True) != json.dumps(old.get(name), sort_keys=True):
                _fail(
                    f"source record {old.get('source_record_id')!r} changed field {name!r} — only "
                    f"{sorted(RESTAMPED_RECORD_FIELDS)} may move, and only on portal records"
                )


def assert_wall_clock_sanity(payload: dict[str, Any], *, now: datetime | None = None) -> None:
    real_now = now or _real_now_utc()
    created_at = _parse_utc(payload["created_at"], what="created_at")
    if created_at > real_now:
        _fail(f"created_at {payload['created_at']!r} is in the future — fix FOLD_CREATED_AT")
    for record in payload["source_records"]:
        verified_at = _parse_utc(record["verified_at"], what=f"{record['source_record_id'][:8]} verified_at")
        if verified_at > created_at:
            _fail(
                f"{record['source_record_id'][:8]}: verified_at {record['verified_at']!r} is after this "
                f"pack's created_at {payload['created_at']!r} — a pack cannot attest to a read that "
                "(per its own clock) has not happened yet"
            )


def fold(
    seq24: dict[str, Any],
    seq24_signed: dict[str, Any],
    ledger: Ledger,
    *,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    """Return the seq-25 payload, or abort loudly."""
    digest = hashlib.sha256(canonicalize_json(seq24)).hexdigest()
    if digest != SEQ24_PAYLOAD_SHA256:
        _fail(
            f"the seq-24 source is not the signed artifact: recomputed JCS digest {digest} != "
            f"{SEQ24_PAYLOAD_SHA256}"
        )
    assert_anchor_is_a_verified_signed_artifact(seq24_signed, digest, observed_at=observed_at)
    if seq24.get("sequence") != 24:
        _fail(f"expected sequence 24, got {seq24.get('sequence')!r}")
    if seq24.get("rule_pack_id") != str(_rule_pack_id(24)):
        _fail("the seq-24 payload's rule_pack_id does not follow the uuid5 convention — refusing to mint seq-25's")

    portals = [r for r in seq24["source_records"] if r.get("authority_type") == PORTAL_AUTHORITY]
    if len(portals) != EXPECTED_PORTAL_COUNT:
        _fail(f"expected {EXPECTED_PORTAL_COUNT} {PORTAL_AUTHORITY} records, found {len(portals)}")
    stamps = {r.get("verified_at") for r in portals}
    if stamps != {EXPECTED_SEQ24_STAMP}:
        _fail(
            f"the portal records do not all carry the expected seq-24 stamp {EXPECTED_SEQ24_STAMP}; "
            f"found {sorted(str(s) for s in stamps)} — someone already moved part of the set"
        )

    verified_at = attestation_instant(ledger, portals)
    if _parse_utc(verified_at, what="verified_at") <= _parse_utc(EXPECTED_SEQ24_STAMP, what="seq-24 stamp"):
        _fail(f"the ledger's earliest read {verified_at} is not after the seq-24 stamp {EXPECTED_SEQ24_STAMP}")

    out = json.loads(json.dumps(seq24))
    restamped = 0
    for record in out["source_records"]:
        if record.get("authority_type") != PORTAL_AUTHORITY:
            continue
        record["verified_at"] = verified_at
        record["verified_by"] = RESTAMP_VERIFIED_BY
        restamped += 1
    if restamped != EXPECTED_PORTAL_COUNT:
        _fail(f"restamped {restamped}, expected {EXPECTED_PORTAL_COUNT}")

    out["sequence"] = 25
    out["rule_pack_id"] = str(_rule_pack_id(25))
    out["version"] = FOLD_VERSION
    out["created_at"] = FOLD_CREATED_AT
    out["created_by"] = FOLD_CREATED_BY
    out["previous_payload_sha256"] = SEQ24_PAYLOAD_SHA256
    out["rollback_of_payload_sha256"] = None

    assert_only_expected_changes(seq24, out)
    assert_wall_clock_sanity(out, now=observed_at)
    RulePackPayload.model_validate(out)
    return out


def main(argv: list[str] | None = None, *, observed_at: datetime | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fold RulePack seq-25 (portal re-stamp) from seq-24.")
    parser.add_argument("--seq24-source", required=True, type=Path)
    parser.add_argument("--seq24-signed", type=Path, default=None)
    parser.add_argument("--ledger-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    signed_path = args.seq24_signed
    if signed_path is None:
        source_str = str(args.seq24_source)
        if not source_str.endswith(".source.json"):
            _fail("--seq24-source does not end in '.source.json' — pass --seq24-signed explicitly")
        signed_path = Path(source_str[: -len(".source.json")] + ".signed.json")
    if not signed_path.exists():
        _fail(f"no signed seq-24 bundle at {signed_path}")
    if args.output in {args.seq24_source, signed_path}:
        _fail("--output collides with an input")

    seq24 = json.loads(args.seq24_source.read_text(encoding="utf-8"))
    seq24_signed = json.loads(signed_path.read_text(encoding="utf-8"))
    ledger = load_ledger(args.ledger_dir)
    seq25 = fold(seq24, seq24_signed, ledger, observed_at=observed_at)
    args.output.write_text(json.dumps(seq25, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    digest = hashlib.sha256(canonicalize_json(seq25)).hexdigest()
    stamp = next(r["verified_at"] for r in seq25["source_records"] if r["authority_type"] == PORTAL_AUTHORITY)
    print(f"fold_pack_seq25: wrote {args.output}")
    print(f"fold_pack_seq25: seq-25 payload_sha256 = {digest}")
    print(f"fold_pack_seq25: chained to seq-24 {SEQ24_PAYLOAD_SHA256}")
    print(f"fold_pack_seq25: 18 portal records re-stamped verified_at={stamp} (earliest successful read)")
    print("fold_pack_seq25: NOT SIGNED, NOT ACTIVATED — see sign_pack.py / activate_pack.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
