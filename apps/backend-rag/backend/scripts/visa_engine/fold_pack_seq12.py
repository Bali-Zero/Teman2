"""fold_pack_seq12.py — assemble RulePack seq-12 from seq-11 + the inc5
freshness re-stamps. One concern, nothing else changes:

**Source re-stamp only.** All 18 OFFICIAL_PORTAL source_records get
``verified_at``/``verified_by`` bumped, each backed by a live QW-5-method
re-verification (inc5-pack-edits/freshness-restamp-2026-08-20.md — 17
CURRENT + 1 CURRENT-with-standing-exception, 0 CHANGED, 0 UNREACHABLE,
zero drops). ``content_sha256`` is untouched on every record: no page
changed semantically, so the description stays; only the attestation
clock moves. This is the weekly re-attestation lane (Zero GO 2026-08-20)
that keeps the active pack's portal sources inside their 7-day
``freshness_policy`` window — without it, production trips
``DECISIVE_SOURCE_STALE`` and abstains on ~2026-08-26.

No rule edits, no product edits, no drops. ``_assert_untouched`` holds
``rules`` and ``products`` to whole-collection canonical equality with
seq-11 — there is no carve-out to make.

The restamped set is derived from the payload by ENTITY, never from a
frozen id list: it must equal exactly the set of records whose
``authority_type`` is ``OFFICIAL_PORTAL`` (all of which carry the 7-day
policy). The count 18 is additionally pinned as a drift tripwire — if the
pack gains or loses a portal source, this fold was authored against a
different world and must abort, not adapt.

Every input is read from disk at run time. The chain hash is read LIVE
from ``rulepack-prod-011.signed.json`` and asserted against the expected
anchor; the seq-11 source bytes are additionally re-hashed (RFC 8785 JCS)
and must equal that same value — a source/signed mismatch aborts the
fold. Every restamp carries ledger-drift guards ({current_value,
new_value} pairs asserted against the seq-11 bytes before mutating).
Deterministic: fixed timestamps, no ``datetime.now()`` — re-running is
byte-identical.

Usage::

    PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq12
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

from backend.services.visa_engine.bundle import canonicalize_json
from backend.services.visa_engine.models import RulePackPayload

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_THIS_FILE = Path(__file__).resolve()
_BACKEND_ROOT = _THIS_FILE.parents[2]  # apps/backend-rag/backend
_REPO_ROOT = _THIS_FILE.parents[5]

_PACKS_DIR = _BACKEND_ROOT / "services" / "visa_engine" / "contracts" / "packs"
_SEQ11_SOURCE = _PACKS_DIR / "rulepack-prod-011.source.json"
_SEQ11_SIGNED = _PACKS_DIR / "rulepack-prod-011.signed.json"
_SEQ12_SOURCE = _PACKS_DIR / "rulepack-prod-012.source.json"

_INC5_EDITS_DIR = _REPO_ROOT / "research" / "visa" / "doctrine-factory" / "e5" / "inc5-pack-edits"
_RESTAMP_EDITS = _INC5_EDITS_DIR / "source-restamp-edits.json"

_PRETTIER_BIN = _REPO_ROOT / "node_modules" / ".bin" / "prettier"

# ---------------------------------------------------------------------------
# seq-12 identity (the uuid5 anchor is verified, never assumed)
# ---------------------------------------------------------------------------

_SEQ12_SEQUENCE = 12
_SEQ12_VERSION = "2026.8.20"  # same-day precedent: seq-2/seq-3 shared 2026.8.8
_SEQ12_RULE_PACK_ID_URL = (
    "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/12"
)
_EXPECTED_SEQ12_RULE_PACK_ID = uuid.UUID("dd98e153-4f89-5176-b32e-d936b7bb2351")

# The signed seq-11 payload hash this pack must chain to. Read LIVE from the
# signed file at run time AND asserted equal to this anchor AND equal to the
# recomputed canonical hash of the seq-11 SOURCE bytes — three independent
# derivations of one value, any mismatch aborts.
_EXPECTED_SEQ11_PAYLOAD_SHA256 = (
    "836acc511bcadd41c28284e7f00bd8be27c6109ebcc5536f7053c3f61eaa2865"
)

# Fixed (not datetime.now()) so re-running this script is byte-identical.
_SEQ12_CREATED_AT = "2026-08-20T07:00:00Z"
_SEQ12_CREATED_BY = "agent.air-m5.backend-rag.visa-seq12-restamp.fold-2026-08-20"

# Drift tripwire on the restamp batch size: the QW-5 capture doc attests
# exactly 18 portal records. A different count means the pack (or the edit
# file) drifted from what this fold was authored against — abort, don't adapt.
_EXPECTED_RESTAMP_COUNT = 18
_PORTAL_AUTHORITY_TYPE = "OFFICIAL_PORTAL"


class FoldPackError(RuntimeError):
    """A fail-loud gate inside the fold tripped — never silently degrade."""


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Identity + chain
# ---------------------------------------------------------------------------


def _verify_rule_pack_id() -> uuid.UUID:
    computed = uuid.uuid5(uuid.NAMESPACE_URL, _SEQ12_RULE_PACK_ID_URL)
    if computed != _EXPECTED_SEQ12_RULE_PACK_ID:
        raise FoldPackError(
            f"seq-12 rule_pack_id convention drifted: uuid5(NAMESPACE_URL, "
            f"{_SEQ12_RULE_PACK_ID_URL!r}) = {computed}, expected "
            f"{_EXPECTED_SEQ12_RULE_PACK_ID} — do not hand-adjust either side"
        )
    return computed


def _chain_hash(seq11_source: dict[str, Any]) -> str:
    signed = _load_json(_SEQ11_SIGNED)
    declared = signed.get("payload_sha256")
    if declared != _EXPECTED_SEQ11_PAYLOAD_SHA256:
        raise FoldPackError(
            f"{_SEQ11_SIGNED} declares payload_sha256={declared!r}, expected "
            f"{_EXPECTED_SEQ11_PAYLOAD_SHA256!r} — the signed seq-11 on disk is "
            "not the one this fold was authored against"
        )
    recomputed = hashlib.sha256(canonicalize_json(seq11_source)).hexdigest()
    if recomputed != declared:
        raise FoldPackError(
            f"seq-11 SOURCE bytes re-hash to {recomputed}, but the signed file "
            f"declares {declared} — source/signed mismatch, refusing to chain"
        )
    return declared


def _apply_identity(payload: dict[str, Any], seq11_source: dict[str, Any]) -> None:
    payload["sequence"] = _SEQ12_SEQUENCE
    payload["version"] = _SEQ12_VERSION
    payload["rule_pack_id"] = str(_verify_rule_pack_id())
    payload["previous_payload_sha256"] = _chain_hash(seq11_source)
    payload["created_at"] = _SEQ12_CREATED_AT
    payload["created_by"] = _SEQ12_CREATED_BY
    # rollback_of_payload_sha256 stays null; top-level valid_period untouched
    # (not in _IDENTITY_KEYS, so the byte-invariance sweep asserts it equals
    # seq-11's).


# ---------------------------------------------------------------------------
# The one edit — verified_at/verified_by re-stamps on the 18 portal records
# ---------------------------------------------------------------------------


def _apply_restamps(payload: dict[str, Any]) -> int:
    edits = _load_json(_RESTAMP_EDITS)
    records_by_id = {r["source_record_id"]: r for r in payload["source_records"]}

    restamps = edits["restamps"]
    if len(restamps) != _EXPECTED_RESTAMP_COUNT:
        raise FoldPackError(
            f"expected exactly {_EXPECTED_RESTAMP_COUNT} restamps, edit file "
            f"carries {len(restamps)}"
        )

    # Entity check, not a frozen id list: the restamped set must be exactly
    # the set of OFFICIAL_PORTAL records in the pack — every portal record
    # re-attested, no non-portal record touched. A frozen list here would be
    # a W106 measurement that silently rots when the pack's source roster
    # changes; the authority_type IS the entity this lane exists to serve.
    portal_ids = {
        r["source_record_id"]
        for r in payload["source_records"]
        if r.get("authority_type") == _PORTAL_AUTHORITY_TYPE
    }
    restamp_ids = {e["source_record_id"] for e in restamps}
    if restamp_ids != portal_ids:
        missing = sorted(portal_ids - restamp_ids)
        extra = sorted(restamp_ids - portal_ids)
        raise FoldPackError(
            "restamp set is not exactly the OFFICIAL_PORTAL set — "
            f"portal records not restamped: {missing}; "
            f"restamps naming non-portal/unknown records: {extra}"
        )

    for edit in restamps:
        sid = edit["source_record_id"]
        record = records_by_id.get(sid)
        if record is None:
            raise FoldPackError(f"restamp names unknown source_record_id {sid!r}")
        if record.get("verified_at") != edit["current_verified_at"] or record.get(
            "verified_by"
        ) != edit["current_verified_by"]:
            raise FoldPackError(
                f"source_record {sid!r} verified_at/verified_by do not match the "
                "edit file's declared current values — ledger drift, not applying blind"
            )
        # Re-attestation moves the clock forward: both stamps are
        # "YYYY-MM-DDTHH:MM:SSZ" UTC, so lexicographic order is chronological.
        if not edit["new_verified_at"] > record["verified_at"]:
            raise FoldPackError(
                f"source_record {sid!r}: new verified_at "
                f"{edit['new_verified_at']!r} does not advance past the current "
                f"{record['verified_at']!r} — a re-stamp that moves time backward "
                "or holds it still is not an attestation"
            )
        record["verified_at"] = edit["new_verified_at"]
        record["verified_by"] = edit["new_verified_by"]

    return len(restamps)


# ---------------------------------------------------------------------------
# Byte-invariance sweep — everything not declared touched must match seq-11
# ---------------------------------------------------------------------------

#: Top-level payload keys this fold is ALLOWED to differ from seq-11 on.
_IDENTITY_KEYS = frozenset(
    {"sequence", "version", "rule_pack_id", "previous_payload_sha256", "created_at", "created_by"}
)

#: The ONLY per-record fields the restamp is allowed to change.
_RESTAMP_FIELDS = frozenset({"verified_at", "verified_by"})


def _assert_untouched(
    payload: dict[str, Any], seq11: dict[str, Any], restamped_ids: set[str]
) -> None:
    for key in set(seq11) | set(payload):
        if key in _IDENTITY_KEYS or key == "source_records":
            continue
        if _canon(payload.get(key)) != _canon(seq11.get(key)):
            raise FoldPackError(
                f"top-level payload key {key!r} drifted from seq-11 — this fold "
                "declares no edit there"
            )
    # The loop above already covers "rules" and "products" as whole
    # collections — this fold declares ZERO edits in either, so there is no
    # carve-out to make and no per-item sweep to run.

    seq11_records = {r["source_record_id"]: r for r in seq11["source_records"]}
    new_records = {r["source_record_id"]: r for r in payload["source_records"]}
    if set(new_records) != set(seq11_records):
        raise FoldPackError(
            "source_record set (by source_record_id) drifted from seq-11 — this "
            "fold declares no record add/remove/drop"
        )
    for sid, record in new_records.items():
        baseline = seq11_records[sid]
        if sid in restamped_ids:
            b = {k: v for k, v in baseline.items() if k not in _RESTAMP_FIELDS}
            c = {k: v for k, v in record.items() if k not in _RESTAMP_FIELDS}
            if _canon(b) != _canon(c):
                raise FoldPackError(
                    f"source_record {sid!r} changed beyond verified_at/verified_by "
                    "— content_sha256 and every other field must ride through "
                    "untouched on a pure re-stamp"
                )
        elif _canon(record) != _canon(baseline):
            raise FoldPackError(
                f"source_record {sid!r} drifted from seq-11 outside the declared "
                "restamp set"
            )


# ---------------------------------------------------------------------------
# Write (atomic + prettier — fold_pack.py's Codex-finding-7 shape)
# ---------------------------------------------------------------------------


def _write_pack(payload: dict[str, Any], out_path: Path) -> None:
    if not _PRETTIER_BIN.exists():
        raise FoldPackError(
            f"prettier binary not found at {_PRETTIER_BIN} — run `npm install` at repo root"
        )

    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(
        prefix=f"{out_path.stem}.tmp.", suffix=out_path.suffix, dir=str(out_path.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        with open(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        result = subprocess.run(
            [str(_PRETTIER_BIN), "--write", str(tmp_path)],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise FoldPackError(
                f"prettier --write {tmp_path} failed (rc={result.returncode}):\n"
                f"{result.stdout}\n{result.stderr}"
            )
        tmp_path.replace(out_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def assemble_payload() -> dict[str, Any]:
    seq11_original = _load_json(_SEQ11_SOURCE)
    payload = copy.deepcopy(seq11_original)

    _apply_identity(payload, seq11_original)
    restamp_count = _apply_restamps(payload)
    restamped_ids = {
        e["source_record_id"] for e in _load_json(_RESTAMP_EDITS)["restamps"]
    }
    if restamp_count != len(restamped_ids):
        raise FoldPackError(
            f"restamp edit file carries duplicate source_record_ids — "
            f"{restamp_count} entries but {len(restamped_ids)} distinct ids"
        )
    _assert_untouched(payload, seq11_original, restamped_ids)

    try:
        RulePackPayload.model_validate(payload)
    except Exception as exc:  # re-raised loud with context
        raise FoldPackError(
            f"assembled seq-12 payload failed RulePackPayload validation: {exc}"
        ) from exc

    return payload


def main(argv: list[str] | None = None) -> int:
    del argv  # no CLI flags — deterministic single-purpose script
    try:
        payload = assemble_payload()
    except FoldPackError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    _write_pack(payload, _SEQ12_SOURCE)
    print(
        f"wrote {_SEQ12_SOURCE} — {len(payload['rules'])} rule(s), "
        f"{len(payload['products'])} product(s), {len(payload['source_records'])} source_record(s)"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
