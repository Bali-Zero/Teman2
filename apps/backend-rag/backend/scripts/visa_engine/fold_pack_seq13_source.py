"""fold_pack_seq13_source.py — the seq-13 JOIN: combine the RULES-ONLY half
(``rulepack-prod-013.rules-only.json``, ``fold_pack_seq13_rules.py``) with
the source-freshness half (an 18-record ``verified_at``/``verified_by``
re-attestation of the OFFICIAL_PORTAL ``source_records``, the seq-12
pattern applied to seq-13) into the actual, signable
``rulepack-prod-013.source.json``.

Two lanes, two disjoint concerns, one join. Neither half's own fold owns
identity (``sequence``/``version``/``rule_pack_id``/
``previous_payload_sha256``/``created_at``/``created_by``) — both leave it
at seq-12's own values by design (see each fold's module docstring). This
module is where identity is actually assigned and where the chain anchors
to seq-12's SIGNED payload hash.

**Complement-of-the-rules-fold's guard.** ``fold_pack_seq13_rules.py``'s
own ``_assert_untouched`` holds ``products``/``source_records`` (and every
top-level key outside its declared rule edits) to whole-collection
equality with seq-12 — the rules-only lane owns neither. This module
enforces the complement: ``rules`` comes ONLY from the rules-only half
(taken wholesale, cross-checked that the rules-only payload's own
non-``rules`` content is untouched from seq-12 — i.e. the rules lane kept
its promise), and ``source_records`` comes ONLY from the freshness half
(the restamp applied to seq-12's own source_records, entity-derived as
the OFFICIAL_PORTAL set — never a frozen id list, the seq-12 pattern).
Every other top-level key must equal seq-12 canonically. If either half
smuggled a change outside its own lane, this fold aborts rather than
silently carrying it forward.

**On the freshness half's identical-timestamp shape — and the trend behind
it.** All 18 restamps in the freshness input currently carry the SAME
``verified_at`` value — a disclosed pass-level proxy timestamp (see that
file's own ``verified_at_caveat``), not 18 independently observed
per-source fetch times (none were logged). This fold does **not** reject
that shape: a script cannot manufacture 18 honest independent timestamps
out of one that were never captured, and inventing artificial jitter
would be *less* honest, not more.

But "seq-12 did the same thing" — this module's own first-draft framing,
corrected by the team-lead reading the actual bytes rather than trusting
that claim — is the wrong reference point. ``source-restamp-edits.json``
(seq-12's own restamp ledger) shows a DESCENDING staircase, not a stable
convention: the batch seq-12 itself replaced (inherited from seq-10/
seq-11) carried **7 distinct, second-precision values** — real per-fetch
times (``2026-08-18T21:41:23Z`` through ``2026-08-19T04:31:03Z``, verified
by reading the file directly). seq-12's own fold then rounded that down to
**2** (4 records at ``06:14:00Z``, 14 at ``06:15:00Z``). This freshness
input proposes **1**. Each restamp has been coarser than the last, and
nothing in this fold family has ever noticed, because every gate asserts
*advance*, never *resolution*. "What good looks like" is seq-10's 7
distinct values, not seq-12's 2 — citing seq-12 as the bar would enshrine
one step of degradation as acceptable practice.

What this fold DOES enforce mechanically, per record: the new
``verified_at`` strictly advances past the value it replaces (a real
ledger-drift guard, checked against the freshness file's own declared
prior value AND cross-checked against seq-12's actual bytes), and is not
later than this pack's own ``created_at`` (no fabricated future
attestation). Those are real teeth; distinctness-across-records is not,
and a guard that pretended otherwise would be worse engineering than
naming the gap plainly. So the shape is FLAGGED, never rejected and never
silently absorbed: a non-fatal note on stderr, mechanically testable,
that reports the actual three-point resolution trend (this pass vs. the
batch it replaces vs. the batch seq-12 itself replaced, the last read
best-effort from ``source-restamp-edits.json`` — informational only,
never a hard dependency of this fold; its absence degrades the note, not
the join).

**``content_sha256`` is never touched, never recomputed, never
"verified" here.** Ditjen pages embed a per-request CSRF token, so two
fetches of unchanged content hash differently — there is no
canonical-extraction script in this repo. Verification of those 18
sources is by verbatim quotation (the QW-5 report), not by hash
recomputation. This fold's only hash-side check on ``content_sha256`` is
that it rides through byte-identical from seq-12 on every restamped
record — the same "did anything besides the declared field change"
guard every sibling fold in this family runs.

Every input is read from disk at run time. The chain hash is read LIVE
from ``rulepack-prod-012.signed.json`` and asserted against the expected
anchor; the seq-12 source bytes are additionally re-hashed (RFC 8785 JCS)
and must equal that same value — a source/signed mismatch aborts the
fold. Deterministic: fixed timestamps, no ``datetime.now()`` — re-running
is byte-identical. Both input halves are read from disk at fixed paths;
either being absent raises a clear ``FoldPackError``, never an unhandled
crash — the rules-only half ships in PR #4660 (not yet merged as of this
module's authoring) and the freshness half is still being corrected by
its own lane as of this module's authoring.

Usage::

    PYTHONPATH=. python -m backend.scripts.visa_engine.fold_pack_seq13_source
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
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
_SEQ12_SOURCE = _PACKS_DIR / "rulepack-prod-012.source.json"
_SEQ12_SIGNED = _PACKS_DIR / "rulepack-prod-012.signed.json"
_SEQ13_RULES_ONLY = _PACKS_DIR / "rulepack-prod-013.rules-only.json"
_SEQ13_SOURCE_OUT = _PACKS_DIR / "rulepack-prod-013.source.json"

# Where the s13-fresh lane's re-attestation lands. Matches the file already
# on disk in that lane's own worktree at the time this fold was authored
# (research/visa/2026-08-23-seq13-restamp-source-records.json) — a research
# capture next to its own report (2026-08-23-freshness-restamp-seq13.md),
# not yet committed as of this module's authoring.
_FRESHNESS_INPUT = _REPO_ROOT / "research" / "visa" / "2026-08-23-seq13-restamp-source-records.json"

# Informational only, never a hard dependency: seq-12's OWN restamp ledger,
# read purely to report the resolution-trend NOTE (see module docstring).
# Its absence degrades the note (that segment is simply omitted), never the
# join — this path is deliberately not run through `_load_json`'s
# raise-on-missing behavior.
_SEQ12_RESTAMP_HISTORY = (
    _REPO_ROOT
    / "research"
    / "visa"
    / "doctrine-factory"
    / "e5"
    / "inc5-pack-edits"
    / "source-restamp-edits.json"
)

_PRETTIER_BIN = _REPO_ROOT / "node_modules" / ".bin" / "prettier"

# ---------------------------------------------------------------------------
# seq-13 identity (the uuid5 anchor is verified, never assumed)
# ---------------------------------------------------------------------------

_SEQ13_SEQUENCE = 13
_SEQ13_VERSION = "2026.8.23"
_SEQ13_RULE_PACK_ID_URL = (
    "https://balizero.com/visa-oracle/rule-pack/PRODUCTION/ID/IMMIGRATION_VISA/13"
)
_EXPECTED_SEQ13_RULE_PACK_ID = uuid.UUID("79b62b85-829e-59f8-a058-c38c065b8cb5")

# The signed seq-12 payload hash this pack must chain to. Read LIVE from the
# signed file at run time AND asserted equal to this anchor AND equal to the
# recomputed canonical hash of the seq-12 SOURCE bytes — three independent
# derivations of one value, any mismatch aborts. Same anchor
# fold_pack_seq13_rules.py chains against (both halves fold off the same
# seq-12 baseline).
_EXPECTED_SEQ12_PAYLOAD_SHA256 = (
    "ff43d55e79e833a91820c4b68dd9ffdd086e7969b3b3a44dbd80747aa451406d"
)

# Fixed (not datetime.now()) so re-running this script is byte-identical,
# and so the freshness half's "not in the future" guard has a fixed
# reference rather than depending on wall-clock at run time.
_SEQ13_CREATED_AT = "2026-08-23T20:00:00Z"
_SEQ13_CREATED_BY = "agent.air-m5.backend-rag.visa-seq13-source-join.fold-2026-08-23"

# Drift tripwire on the restamp batch size — same convention as seq-12's
# fold: a different count means this fold was authored against a different
# world and must abort, not adapt.
_EXPECTED_RESTAMP_COUNT = 18
_PORTAL_AUTHORITY_TYPE = "OFFICIAL_PORTAL"

_IDENTITY_KEYS = frozenset(
    {"sequence", "version", "rule_pack_id", "previous_payload_sha256", "created_at", "created_by"}
)
_RESTAMP_FIELDS = frozenset({"verified_at", "verified_by"})
_UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class FoldPackError(RuntimeError):
    """A fail-loud gate inside the fold tripped — never silently degrade."""


def _load_json(path: Path, *, what: str) -> Any:
    if not path.exists():
        raise FoldPackError(
            f"{what} not found at {path} — this join cannot run without it. "
            "Merge/land that lane's artifact first, then re-run this fold."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _historical_restamp_distinct_count(record_ids: set[str]) -> int | None:
    """Best-effort, informational only: how many distinct ``verified_at``
    values the batch seq-12 ITSELF replaced (``source-restamp-edits.json``'s
    own ``current_verified_at`` — inherited from seq-10/seq-11) carried,
    restricted to ``record_ids``. Returns ``None`` on anything short of a
    clean read (missing file, unexpected shape, empty overlap) — this feeds
    the resolution-trend NOTE only, never a guard, and must never become a
    third hard dependency of this fold."""

    try:
        if not _SEQ12_RESTAMP_HISTORY.exists():
            return None
        data = json.loads(_SEQ12_RESTAMP_HISTORY.read_text(encoding="utf-8"))
        values = {
            e["current_verified_at"]
            for e in data["restamps"]
            if e.get("source_record_id") in record_ids
        }
        return len(values) if values else None
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return None


def _parse_utc(value: str) -> datetime:
    try:
        return datetime.strptime(value, _UTC_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise FoldPackError(f"timestamp {value!r} is not the fixed UTC shape {_UTC_FORMAT!r}") from exc


# ---------------------------------------------------------------------------
# Identity + chain
# ---------------------------------------------------------------------------


def _verify_rule_pack_id() -> uuid.UUID:
    computed = uuid.uuid5(uuid.NAMESPACE_URL, _SEQ13_RULE_PACK_ID_URL)
    if computed != _EXPECTED_SEQ13_RULE_PACK_ID:
        raise FoldPackError(
            f"seq-13 rule_pack_id convention drifted: uuid5(NAMESPACE_URL, "
            f"{_SEQ13_RULE_PACK_ID_URL!r}) = {computed}, expected "
            f"{_EXPECTED_SEQ13_RULE_PACK_ID} — do not hand-adjust either side"
        )
    return computed


def _chain_hash(seq12_source: dict[str, Any]) -> str:
    signed = _load_json(_SEQ12_SIGNED, what="rulepack-prod-012.signed.json")
    declared = signed.get("payload_sha256")
    if declared != _EXPECTED_SEQ12_PAYLOAD_SHA256:
        raise FoldPackError(
            f"{_SEQ12_SIGNED} declares payload_sha256={declared!r}, expected "
            f"{_EXPECTED_SEQ12_PAYLOAD_SHA256!r} — the signed seq-12 on disk is "
            "not the one this fold was authored against"
        )
    recomputed = hashlib.sha256(canonicalize_json(seq12_source)).hexdigest()
    if recomputed != declared:
        raise FoldPackError(
            f"seq-12 SOURCE bytes re-hash to {recomputed}, but the signed file "
            f"declares {declared} — source/signed mismatch, refusing to chain"
        )
    return declared


def _apply_identity(payload: dict[str, Any], seq12_source: dict[str, Any]) -> None:
    payload["sequence"] = _SEQ13_SEQUENCE
    payload["version"] = _SEQ13_VERSION
    payload["rule_pack_id"] = str(_verify_rule_pack_id())
    payload["previous_payload_sha256"] = _chain_hash(seq12_source)
    payload["created_at"] = _SEQ13_CREATED_AT
    payload["created_by"] = _SEQ13_CREATED_BY
    # rollback_of_payload_sha256 stays null; top-level valid_period untouched
    # (not in _IDENTITY_KEYS, so the byte-invariance sweep asserts it equals
    # seq-12's).


# ---------------------------------------------------------------------------
# Rules half — taken wholesale, cross-checked that it kept its own promise
# ---------------------------------------------------------------------------


def _apply_rules(payload: dict[str, Any], seq12_source: dict[str, Any]) -> dict[str, Any]:
    rules_only = _load_json(_SEQ13_RULES_ONLY, what="rulepack-prod-013.rules-only.json")

    # The rules-only fold's own docstring promises it changes NOTHING but
    # `rules` — identity stays at seq-12's own values, products and
    # source_records are untouched. Verify that promise was kept before
    # trusting its `rules` at all: a rules-only artifact that silently
    # smuggled a product or source_record edit must abort here, not ride
    # into the combined pack disguised as "the rules half".
    for key in _IDENTITY_KEYS:
        if rules_only.get(key) != seq12_source.get(key):
            raise FoldPackError(
                f"rulepack-prod-013.rules-only.json's {key!r} = "
                f"{rules_only.get(key)!r} differs from seq-12's {seq12_source.get(key)!r} "
                "— the rules-only fold declares no identity change; this artifact "
                "does not match its own contract"
            )
    for key in ("products", "source_records"):
        if _canon(rules_only.get(key)) != _canon(seq12_source.get(key)):
            raise FoldPackError(
                f"rulepack-prod-013.rules-only.json's {key!r} drifted from seq-12 — "
                "the rules-only lane owns neither products nor source_records; "
                "this join refuses to inherit a change outside that lane's own "
                "declared territory"
            )
    for key in set(seq12_source) | set(rules_only):
        if key in _IDENTITY_KEYS or key in ("rules", "products", "source_records"):
            continue
        if _canon(rules_only.get(key)) != _canon(seq12_source.get(key)):
            raise FoldPackError(
                f"rulepack-prod-013.rules-only.json's top-level key {key!r} drifted "
                "from seq-12 outside its declared rules-only edit"
            )

    payload["rules"] = copy.deepcopy(rules_only["rules"])
    return rules_only


# ---------------------------------------------------------------------------
# Freshness half — 18-record OFFICIAL_PORTAL restamp, entity-derived
# ---------------------------------------------------------------------------


def _apply_freshness(payload: dict[str, Any], seq12_source: dict[str, Any]) -> set[str]:
    freshness = _load_json(_FRESHNESS_INPUT, what="seq-13 freshness restamp JSON")

    # The freshness input is a bespoke research-capture document, not a
    # RulePackPayload fragment — it must not carry rule/product edits at
    # all. This is the complement half of the rules-fold cross-check above:
    # each half is refused the other's territory even if its SHAPE changed
    # to make that possible.
    for forbidden_key in ("rules", "products"):
        if forbidden_key in freshness:
            raise FoldPackError(
                f"the freshness input declares a {forbidden_key!r} key — the "
                "freshness lane owns only source_records; refusing to consume "
                "a change outside its territory"
            )

    records = freshness.get("restamped_source_records")
    if records is None:
        raise FoldPackError("freshness input is missing 'restamped_source_records'")
    if len(records) != _EXPECTED_RESTAMP_COUNT:
        raise FoldPackError(
            f"expected exactly {_EXPECTED_RESTAMP_COUNT} restamps, freshness input "
            f"carries {len(records)}"
        )

    payload_records_by_id = {r["source_record_id"]: r for r in payload["source_records"]}

    # Entity check, not a frozen id list — the restamped set must be exactly
    # the set of OFFICIAL_PORTAL records already in the payload (seq-12's,
    # untouched at this point). The seq-12 pattern, one generation later.
    portal_ids = {
        sid
        for sid, r in payload_records_by_id.items()
        if r.get("authority_type") == _PORTAL_AUTHORITY_TYPE
    }
    restamp_ids = {r["source_record_id"] for r in records}
    if len(restamp_ids) != len(records):
        raise FoldPackError("freshness input names a duplicate source_record_id")
    if restamp_ids != portal_ids:
        missing = sorted(portal_ids - restamp_ids)
        extra = sorted(restamp_ids - portal_ids)
        raise FoldPackError(
            "freshness restamp set is not exactly the OFFICIAL_PORTAL set — "
            f"portal records not restamped: {missing}; "
            f"restamps naming non-portal/unknown records: {extra}"
        )

    created_at_dt = _parse_utc(_SEQ13_CREATED_AT)
    new_stamps: list[str] = []
    replaced_stamps: list[str] = []

    for fresh_record_raw in records:
        sid = fresh_record_raw["source_record_id"]
        baseline = payload_records_by_id.get(sid)
        if baseline is None:
            raise FoldPackError(f"freshness restamp names unknown source_record_id {sid!r}")

        prior_verified_at = fresh_record_raw.get("_prior_verified_at")
        prior_verified_by = fresh_record_raw.get("_prior_verified_by")
        if prior_verified_at is None or prior_verified_by is None:
            raise FoldPackError(
                f"freshness record {sid!r} is missing _prior_verified_at/_prior_verified_by "
                "— cannot ledger-drift-check a restamp without its declared prior value"
            )
        if baseline.get("verified_at") != prior_verified_at or baseline.get("verified_by") != prior_verified_by:
            raise FoldPackError(
                f"source_record {sid!r}: seq-12's actual verified_at/verified_by "
                f"({baseline.get('verified_at')!r}, {baseline.get('verified_by')!r}) does not "
                f"match the freshness input's declared prior value ({prior_verified_at!r}, "
                f"{prior_verified_by!r}) — ledger drift, refusing to apply blind"
            )

        # Full-content parity: strip verified_at/verified_by (the only
        # fields a restamp may change) AND the leading-underscore ledger
        # metadata (not part of the pack schema) from the freshness
        # record, then require canonical equality against seq-12's own
        # record. This is what makes "content_sha256 never touched" a
        # mechanical guard rather than a promise: any drift on
        # content_sha256, title, locators, etc. fails here, loud.
        cleaned = {
            k: v for k, v in fresh_record_raw.items() if k not in _RESTAMP_FIELDS and not k.startswith("_")
        }
        baseline_stripped = {k: v for k, v in baseline.items() if k not in _RESTAMP_FIELDS}
        if _canon(cleaned) != _canon(baseline_stripped):
            raise FoldPackError(
                f"freshness record {sid!r} changed beyond verified_at/verified_by — "
                "content_sha256 and every other field must ride through untouched "
                "on a pure re-stamp"
            )

        new_verified_at = fresh_record_raw["verified_at"]
        new_verified_by = fresh_record_raw["verified_by"]

        new_dt = _parse_utc(new_verified_at)
        prior_dt = _parse_utc(prior_verified_at)
        if not new_dt > prior_dt:
            raise FoldPackError(
                f"source_record {sid!r}: new verified_at {new_verified_at!r} does not "
                f"advance past the prior {prior_verified_at!r} — a re-stamp that moves "
                "time backward or holds it still is not an attestation"
            )
        if new_dt > created_at_dt:
            raise FoldPackError(
                f"source_record {sid!r}: new verified_at {new_verified_at!r} is after "
                f"this pack's own created_at {_SEQ13_CREATED_AT!r} — a re-stamp cannot "
                "attest to a fetch that (per this pack's own clock) hasn't happened yet"
            )

        baseline["verified_at"] = new_verified_at
        baseline["verified_by"] = new_verified_by
        new_stamps.append(new_verified_at)
        replaced_stamps.append(prior_verified_at)

    # FLAGGED, not rejected — see module docstring for the reasoning. A
    # batch of identical-to-the-second stamps is a disclosed pass-level
    # proxy, not per-source observation; the per-record guards above
    # (advance + not-future + ledger-drift) are the actual evidentiary
    # teeth, not timestamp cardinality. But this fold family's resolution
    # has been getting COARSER, not holding steady — report the trend, not
    # just the current number, so a reader sees the coarsening rather than
    # mistaking a prior degradation for an established convention.
    current_distinct = len(set(new_stamps))
    if current_distinct < len(new_stamps):
        replaced_distinct = len(set(replaced_stamps))
        historical_distinct = _historical_restamp_distinct_count(restamp_ids)

        trend = [f"{current_distinct} now"]
        trend.append(f"{replaced_distinct} in the batch this replaces (seq-12's own restamp)")
        if historical_distinct is not None:
            trend.append(
                f"{historical_distinct} in the batch seq-12 itself replaced "
                "(inherited from seq-10/seq-11, real second-precision per-fetch times)"
            )

        print(
            f"NOTE: {len(new_stamps)} freshness restamps carry only {current_distinct} "
            "distinct verified_at value(s) — a disclosed pass-level proxy timestamp, "
            "not independently observed per-source fetch times. Flagged, not rejected: "
            "a script cannot manufacture per-source fetch times that were never "
            "captured. But this is a DESCENDING resolution trend, not a stable "
            f"convention — distinct-verified_at-count, newest first: {' <- '.join(trend)}. "
            "What good looks like is the oldest figure in that chain, not the most "
            "recent one. Evidentiary backing for each source is the QW-5 "
            "verbatim-quote report, not timestamp cardinality — but the coarsening "
            "itself is worth naming, not just excusing.",
            file=sys.stderr,
        )

    return restamp_ids


# ---------------------------------------------------------------------------
# Byte-invariance sweep — everything not declared touched must match seq-12
# ---------------------------------------------------------------------------


def _assert_untouched(
    payload: dict[str, Any], seq12: dict[str, Any], restamped_ids: set[str]
) -> None:
    for key in set(seq12) | set(payload):
        if key in _IDENTITY_KEYS or key in ("rules", "source_records"):
            continue
        if _canon(payload.get(key)) != _canon(seq12.get(key)):
            raise FoldPackError(
                f"top-level payload key {key!r} drifted from seq-12 — this join "
                "declares no edit there"
            )

    seq12_records = {r["source_record_id"]: r for r in seq12["source_records"]}
    new_records = {r["source_record_id"]: r for r in payload["source_records"]}
    if set(new_records) != set(seq12_records):
        raise FoldPackError(
            "source_record set (by source_record_id) drifted from seq-12 — this "
            "join declares no record add/remove/drop"
        )
    for sid, record in new_records.items():
        baseline = seq12_records[sid]
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
                f"source_record {sid!r} drifted from seq-12 outside the declared "
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
    seq12_original = _load_json(_SEQ12_SOURCE, what="rulepack-prod-012.source.json")
    payload = copy.deepcopy(seq12_original)

    _apply_identity(payload, seq12_original)
    _apply_rules(payload, seq12_original)
    restamped_ids = _apply_freshness(payload, seq12_original)
    _assert_untouched(payload, seq12_original, restamped_ids)

    try:
        RulePackPayload.model_validate(payload)
    except Exception as exc:  # re-raised loud with context
        raise FoldPackError(
            f"assembled seq-13 payload failed RulePackPayload validation: {exc}"
        ) from exc

    return payload


def main(argv: list[str] | None = None) -> int:
    del argv  # no CLI flags — deterministic single-purpose script
    try:
        payload = assemble_payload()
    except FoldPackError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    _write_pack(payload, _SEQ13_SOURCE_OUT)
    print(
        f"wrote {_SEQ13_SOURCE_OUT} — {len(payload['rules'])} rule(s), "
        f"{len(payload['products'])} product(s), {len(payload['source_records'])} source_record(s)"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
